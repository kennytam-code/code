# ============================================================================
# v31.11 — CHANGES FROM v31.10.  Every edit is tagged [X..] in the body so you
# can grep for it. Search "[X" to see all of them in order.
# ----------------------------------------------------------------------------
# CRASHES
#  [X1]  `import os` was MISSING. Only `import os as _os` existed, but
#        get_manual_context() and _read_ledger() call os.path.*, so
#        setup_manual() raised NameError on any fresh kernel. It only ever
#        worked because another notebook cell had imported os.
#  [X15] add_days() did `out += add_day(...)`, and add_day returns None by
#        design ([W3]). `[] += None` -> TypeError. The documented backfill
#        path died on its first row.
#
# THE PAPER DESK DISAGREED WITH THE BACKTEST
#  [X9]  COST MODEL. fill_cost_bps was the literal 2 + 2 + 2 x FX half = 12 bps
#        a fill, i.e. 24 bps a round trip, against a backtest round trip of
#        ~103 bps for UMC. Excluding spread and impact is right (your typed
#        fills already crossed them) but the 32 bps ADR OUT FEE is not a
#        spread and was silently dropped, and funding / borrow / margin carry
#        were absent entirely. Now built from the same constants
#        compute_exec_cost() uses, via one _trade_cost() both the daily card
#        and exit_pos call — the card used to charge ONE fill while the exit
#        charged TWO, so every mark was 12 bps rosier than the exit it led to.
#  [X13] DEVIATION GATE. `dev = prem - hist_mean`, where hist_mean is the last
#        value of a 30-row rolling mean FROZEN at the final backtest date. The
#        backtest gates on the LIVE rolling n-mean, which _zstats had already
#        returned as `mu` and which was thrown away. The desk's cost floor
#        drifted away from the tested one as soon as the premium level moved.
#  [X10] REGIME GATE. _gate ran the AR(1) gamma on the RAW PREMIUM LEVEL while
#        run_backtest runs it on the DE-TRENDED deviation — despite the
#        docstring claiming they were identical. For a trending premium,
#        level-gamma sits far closer to zero, so the desk read "gate shut" on
#        days the backtest had traded.
#  [X11] DIVIDEND CARRY. _fair() ignored the [U5] adjustment, so between the
#        Taiwan ex-date and the later ADR ex-date the desk showed the full
#        fake premium spike (+738 bps on UMC vs a ~120 bps sigma) that the
#        backtest removes — while scoring it against a hist_premium series
#        that IS adjusted. add_day(..., div_carry=) now applies it.
#  [X12] GAMMA EXIT. The backtest's EXIT 3 (leave when expected daily
#        reversion < daily carry) did not exist on the desk at all.
#  [X8]  The desk hardcoded 'close' rows everywhere regardless of EXEC_TIMING.
#
# SILENT DATA CORRUPTION
#  [X7]  side / notional / net were round-tripped through the free-text
#        `note`: direction from `'SHORT' in note.upper()`, size from the last
#        `$`-prefixed token. So note='vs $7.20 ADR' set the position size to
#        $7.20 and note='no shortfall' flipped a LONG to a SHORT. They are
#        real columns now, with the note-scan kept only to load old ledgers.
#        Realised P&L also stopped being stored in a column called
#        premium_bps. [X14] scopes the row-replace to the instrument.
#
# DIAGNOSTICS THAT WERE STRUCTURALLY BLIND
#  [X4]  [K6] tests fut_gap_raw = Fut_2130/Fut_1330, a SAME-DAY RATIO, so the
#        contract cancels and it CANNOT see a month-start roll step. The step
#        only exists in FAIR_MODE='futures', which uses the futures LEVEL.
#        [X4] tests the premium itself, in both fair modes, and reports the
#        excess in units of the deviation sigma.
#  [X6]  why_no_trades(start, end) — [W4] audits the 15 largest deviations in
#        the whole SAMPLE, which by construction tells you nothing about a
#        quiet window. This tallies the blocking reason for EVERY row between
#        two dates. Runs automatically on the trailing 6 months.
#  [X2]  Per-leg fees are now per-instrument overridable, and the run prints
#        the implied cents-per-share. A depositary fee is CASH per share, so
#        32 bps means ~8.0c on a $250 ADR and ~2.2c on a $7 one — the shared
#        constant cannot be right for both.
#
# LOOK-AHEAD / HYGIENE
#  [X3]  The de-trended gate series was .fillna(0.0)'d, so the FIRST gamma
#        window contained ~20 synthetic zeros. GATE_WARMUP_STRICT=True pushes
#        the first tradable row out by ADF_DETREND_N. THIS CHANGES RESULTS —
#        set it False to reproduce v31.10 numbers exactly.
#  [X5]  mfe_bps was initialised twice in two places.
# ============================================================================
import os          # [X1] BUGFIX: the paper desk calls os.path.* (get_manual_context,
                   # _read_ledger). Previously only `import os as _os` existed, further
                   # down at the FILE_PREFIX block, so setup_manual() raised NameError
                   # on any fresh kernel that had not imported os in another cell.
import time
import blpapi
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from statsmodels.tsa.stattools import adfuller
 
# ############################################################################
# [Y16]  INSTRUMENT SWITCH — THE ONLY LINE TO EDIT TO CHANGE UNDERLYING
# ############################################################################
INSTRUMENT = 'TSMC'          # 'TSMC' | 'UMC'
# ############################################################################
 
# ============================================================================
# [Y4][Y5] HTML OUTPUT LAYER — defined UP HERE (not at the end) so every
#          section below can render through it as it runs.
# ============================================================================
HTML_OUTPUT = True    # [Y4] False = the v31.11 plain-text output everywhere
 
import re
import numpy as _np
import pandas as _pd
 
SHOW_PNL_MATH = True     # [Y9h][Y11] print the substituted P&L formulas
GUARD_FUT_TOL = 0.12     # [Y9a] snapshot SSF may sit at most 12% off the 13:30 anchor
GUARD_ORD_TOL = 0.10     # [Y9a] 13:30 SSF vs ordinary basis tolerance
GUARD_Z_MAX   = 8.0      # [Y9a] |z| beyond this = implausible input, refuse
GUARD_PREM_MAX_BPS = 3000.0   # [Y9a] |premium| beyond this = implausible, refuse
# [Y29] WHICH FX THE PAPER DESK MARKS WITH.
#   'fixing'  (DEFAULT, and what the BACKTEST does): every fair price, every
#             premium, every z and every mark uses the 13:30 TW-close fixing
#             typed as `fx`. The backtest converts the futures leg at
#             fx[entry]/fx[t] on that same TW-close series [D2], so this is
#             the only setting where the paper desk and the grid agree.
#   'snapshot': if fx_open / fx_1945 / fx_close are also typed, MARKS use the
#             FX of that snapshot. Closer to a live screen, but no longer the
#             backtested convention; the difference is intraday FX noise.
# In BOTH settings the SIGNAL uses the fixing, and NEITHER is the fill: under
# FX_EXEC_MODE='spot_next_open' the hedge converts at the NEXT TW open, which
# does not exist yet when you score the day — record it later with fx_fill().
FX_MARK_MODE = 'fixing'       # 'fixing' | 'snapshot'
 
# ============================================================================
# [Y4] HTML HELPERS
# ============================================================================
# [Y4b] WHY YOU MAY HAVE SEEN NO TABLES: v31.12's first cut only recognised
# a classic notebook kernel (ZMQInteractiveShell) and fell back to plain text
# EVERYWHERE else — silently. A plain `python v31_12.py` run, Spyder, a
# terminal IPython, VS Code and Colab all took the text path with no notice.
# Now: inline HTML wherever a rich display exists, and where one does NOT,
# every table is still WRITTEN TO AN HTML FILE you can open in a browser, so
# the tables always exist somewhere. HTML_FILE=None turns the file off.
HTML_FILE = 'v31_12_tables.html'
_HTML_FILE_STARTED = False
 
def _in_jupyter():
    """True if a RICH display front-end is attached (notebook, VS Code,
    Colab, Spyder, qtconsole). A bare terminal shell returns False."""
    try:
        from IPython import get_ipython
        ip = get_ipython()
        if ip is None:
            return False
        _cls = type(ip).__name__
        if _cls == 'TerminalInteractiveShell':      # no HTML in a terminal
            return False
        return _cls in ('ZMQInteractiveShell',      # jupyter / VS Code / nbclassic
                        'Shell',                    # google colab
                        'SpyderShell') or hasattr(ip, 'kernel')
    except Exception:
        return False
 
def _html_to_file(html):
    """[Y4b] Append a rendered table to HTML_FILE so a non-notebook run still
    gets the tables. Prints the path once, the first time it writes."""
    global _HTML_FILE_STARTED
    if not HTML_FILE:
        return
    try:
        _mode = 'a' if _HTML_FILE_STARTED else 'w'
        with open(HTML_FILE, _mode, encoding='utf-8') as _f:
            if not _HTML_FILE_STARTED:
                _f.write("<html><head><meta charset='utf-8'>"
                         "<title>v31.12 tables</title></head><body>"
                         + _CSS)
            _f.write(html)
        if not _HTML_FILE_STARTED:
            _HTML_FILE_STARTED = True
            print(f"\n  [Y4b] not a notebook front-end, so the HTML tables are "
                  f"being written to {_os.path.abspath(HTML_FILE)}"
                  f" — open it in a browser for the heat maps.")
    except Exception as _e:
        print(f"  [Y4b] could not write {HTML_FILE}: {_e}")
 
_CSS = ("<style>"
  ".v31tbl{border-collapse:separate;border-spacing:0;margin:10px 0;"
  "font:12.5px/1.5 -apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
  "color:#212b36;border:1px solid #e3e6ea;border-radius:8px;overflow:hidden;"
  "box-shadow:0 1px 2px rgba(16,24,40,.05)}"
  ".v31tbl thead th{background:#f7f8fa;color:#42505c;font-size:11px;"
  "font-weight:600;letter-spacing:.4px;text-transform:uppercase;"
  "text-align:right;padding:7px 12px;border-bottom:1px solid #e3e6ea;"
  "white-space:nowrap}"
  # [Y28] the INDEX column renders as <th> in a pandas Styler, which
  # inherited the bold uppercase header style — that is the "bold and
  # packed" look. Row labels are DATA, so they get body styling.
  ".v31tbl tbody th{background:transparent;color:#212b36;font-size:12.5px;"
  "font-weight:500;letter-spacing:0;text-transform:none;text-align:left;"
  "padding:6px 14px 6px 12px;border-bottom:1px solid #eef1f4;"
  "white-space:nowrap;vertical-align:top}"
  ".v31tbl tbody tr:last-child th{border-bottom:none}"
  ".v31tbl th:first-child,.v31tbl td:first-child{text-align:left}"
  ".v31tbl td{padding:6px 12px;text-align:right;white-space:nowrap;"
  "border-bottom:1px solid #eef1f4;font-variant-numeric:tabular-nums}"
  ".v31tbl tbody tr:last-child td{border-bottom:none}"
  ".v31tbl tbody tr:hover td{background:#fafbfc}"
  ".v31tbl caption{caption-side:top;text-align:left;color:#1c2733;"
  "font:600 13.5px/1.4 -apple-system,'Segoe UI',Roboto,Arial;padding:6px 2px}"
  ".vb{display:inline-block;padding:1px 8px;border-radius:10px;"
  "font-size:11px;font-weight:600;white-space:nowrap}"
  ".vb.ok{background:#e6f4ea;color:#1e7e34}"
  ".vb.bad{background:#fdecea;color:#c62828}"
  ".vb.warn{background:#fff4e5;color:#b26a00}"
  ".vb.mut{background:#eef1f4;color:#5f6b76}"
  ".v31note{font:11.5px/1.5 -apple-system,'Segoe UI',Roboto,Arial;"
  "color:#5f6b76;margin:2px 0 14px;max-width:860px}"
  ".v31pre{font:11.5px/1.55 ui-monospace,Consolas,Menlo,monospace;"
  "background:#f7f8fa;border:1px solid #e3e6ea;border-radius:8px;"
  "padding:8px 12px;margin:6px 0 12px;color:#42505c;white-space:pre;"
  "overflow-x:auto}"
  "</style>")
 
def _badge(text, kind='mut'):
    """[Y4] status pill: kind in ok / bad / warn / mut."""
    return f"<span class='vb {kind}'>{text}</span>"
 
def _heat_styles(dfm):
    """[Y4] Soft per-table diverging tint (no matplotlib): light red below
    the table median, light green above, deeper at the extremes. Text stays
    dark so the numbers remain readable — unlike a saturated colormap."""
    import numpy as _n2
    v = dfm.apply(_pd.to_numeric, errors='coerce').values.astype(float)
    out = _pd.DataFrame('', index=dfm.index, columns=dfm.columns)
    fin = _n2.isfinite(v)
    if fin.sum() < 2:
        return out
    lo, hi = _n2.nanmin(v), _n2.nanmax(v)
    md = _n2.nanmedian(v)
    for i in range(v.shape[0]):
        for j in range(v.shape[1]):
            x = v[i, j]
            if not _n2.isfinite(x):
                continue
            if x >= md:
                a = 0.0 if hi <= md else (x - md) / (hi - md)
                out.iat[i, j] = f'background-color:rgba(46,160,67,{0.06 + 0.24 * a:.3f})'
            else:
                a = 0.0 if md <= lo else (md - x) / (md - lo)
                out.iat[i, j] = f'background-color:rgba(220,53,69,{0.06 + 0.22 * a:.3f})'
    return out
 
def _style(frame, title='', heat=False, fmt='{:,.0f}'):
    sty = frame.style.set_table_attributes('class="v31tbl"')
    if isinstance(fmt, (str, dict)):
        sty = sty.format(fmt, na_rep='\u2014')
    if title:
        sty = sty.set_caption(title)
    if heat:
        try:
            sty = sty.apply(_heat_styles, axis=None)
        except Exception:
            pass
    return sty
 
def show_html_table(frame, title='', note='', heat=False, fmt='{:,.0f}',
                    cmap=None):
    """[Y4] Render a DataFrame as a styled HTML table wherever a rich display
    exists; identical plain-text print (plus the [Y4b] HTML file) elsewhere.
    heat=True adds a soft diverging tint per table. Cell values may contain
    _badge(...) HTML — the Styler does not escape."""
    if (not HTML_OUTPUT) or (not _in_jupyter()):
        # [Y30] the terminal path now applies the SAME `fmt` the HTML path
        # does. It used to dump raw to_string(), so a notebook showed
        # "500,000" and "+1.07" while a terminal showed "500000.0" and
        # "1.074647" for the identical table — the numbers were right but
        # unreadable, which is the same thing at 3am.
        # [Y30] strip badge HTML for the text terminal. pandas renamed
        # DataFrame.applymap -> .map in 2.1 and REMOVED applymap in 3.0,
        # so try both — falling through silently used to leak raw
        # <span> tags into the plain output.
        def _strip_html(x):
            return re.sub(r'<[^>]+>', '', x) if isinstance(x, str) else x
        try:
            _plain = frame.map(_strip_html)          # pandas >= 2.1
        except (AttributeError, TypeError):
            try:
                _plain = frame.applymap(_strip_html)  # pandas < 2.1
            except (AttributeError, TypeError):
                _plain = frame.copy()
        try:
            for _c in _plain.columns:
                _f = (fmt.get(_c) if isinstance(fmt, dict)
                      else fmt if isinstance(fmt, str) else None)
                if not _f:
                    continue
                _num = _pd.to_numeric(_plain[_c], errors='coerce')
                _plain[_c] = [(_f.format(v) if _np.isfinite(v) else '\u2014')
                              if _np.isreal(v) and _pd.notna(v) else _plain[_c].iloc[i]
                              for i, v in enumerate(_num)]
        except Exception:
            pass
        if title:
            print('\n  ' + str(title))
            print('  ' + '\u2500' * min(max(len(str(title)), 20), 76))
        print(_plain.to_string())
        if note:
            print('  ' + note)
        if HTML_OUTPUT:
            try:
                _html_to_file(_style(frame, title, heat, fmt).to_html()
                              + (f"<div class='v31note'>{note}</div>"
                                 if note else ''))
            except Exception:
                _html_to_file(f"<h4>{title}</h4>" + frame.to_html(border=0,
                                                                  escape=False))
        return
    from IPython.display import display, HTML
    try:
        display(HTML(_CSS + _style(frame, title, heat, fmt).to_html()))
    except Exception:
        display(HTML(_CSS + f"<table class='v31tbl'><caption>{title}</caption>"
                     + frame.to_html(border=0, escape=False) + "</table>"))
    if note:
        display(HTML(_CSS + f"<div class='v31note'>{note}</div>"))
 
# ============================================================================
# [Y30] PRESENTATION PRIMITIVES — banners, menus, note blocks, run log.
# ----------------------------------------------------------------------------
# The run prints a lot. Without structure it reads as one undifferentiated
# wall and the three lines that actually need a human get lost in it. These
# four helpers give every message a rank, in BOTH front-ends (HTML card in a
# notebook, aligned box in a terminal), so scanning works:
#   banner(...)     — a section starts here
#   menu(...)       — "here is what you can run", commands aligned
#   note_block(...) — a short bordered aside that must not scroll past
#   say(...)        — one ranked line: 'ok' quiet, 'warn'/'bad' loud
# Rule of thumb used throughout: raw print() is for genuine warnings and
# forensic detail; anything that is "status" goes through these or through
# kv_table/show_html_table, so a clean run is short and a dirty one is loud.
# ============================================================================
_W = 78
_SAY_ICON = {'ok': '✓', 'info': '·', 'warn': '!', 'bad': '✗'}
_SAY_CSS = {'ok': '#1e7e34', 'info': '#5f6b76', 'warn': '#b26a00', 'bad': '#c62828'}
def _hr(ch='─'):
    return ch * _W
def banner(title, sub='', ch='═'):
    """[Y30] Section header. One per major stage of the run."""
    if HTML_OUTPUT and _in_jupyter():
        from IPython.display import display, HTML
        display(HTML(
            _CSS + f"<div style='margin:18px 0 6px;padding:8px 12px;"
            f"border-left:3px solid #42505c;background:#f7f8fa;"
            f"border-radius:0 6px 6px 0;font:600 14px/1.4 -apple-system,"
            f"\"Segoe UI\",Roboto,Arial;color:#1c2733'>{title}"
            + (f"<div style='font-weight:400;font-size:12px;color:#5f6b76;"
               f"margin-top:2px'>{sub}</div>" if sub else '')
            + "</div>"))
        return
    print('\n' + _hr(ch))
    print(f"  {title}")
    if sub:
        print(f"  {sub}")
    print(_hr(ch))
def say(text, level='info', detail=''):
    """[Y30] One ranked status line. 'ok' is quiet, 'warn'/'bad' stand out."""
    if HTML_OUTPUT and _in_jupyter():
        from IPython.display import display, HTML
        display(HTML(
            _CSS + f"<div style='font:12.5px/1.6 -apple-system,\"Segoe UI\","
            f"Roboto,Arial;color:{_SAY_CSS.get(level, '#42505c')};margin:1px 0'>"
            f"{_SAY_ICON.get(level, '·')} {text}"
            + (f" <span style='color:#8a949e'>{detail}</span>" if detail else '')
            + "</div>"))
        return
    print(f"  {_SAY_ICON.get(level, '.')} {text}" + (f"  {detail}" if detail else ''))
def menu(items, title='WHAT TO RUN NEXT'):
    """[Y30] Aligned command list — commands left, one-line purpose right."""
    if HTML_OUTPUT and _in_jupyter():
        from IPython.display import display, HTML
        _rows = ''.join(
            f"<tr><td style='padding:4px 14px 4px 0;white-space:nowrap;"
            f"font:12px ui-monospace,Consolas,Menlo,monospace;color:#1c2733'>"
            f"{c}</td><td style='padding:4px 0;font:12.5px -apple-system,"
            f"\"Segoe UI\",Roboto,Arial;color:#5f6b76'>{d}</td></tr>"
            for c, d in items)
        display(HTML(
            _CSS + f"<div style='margin:10px 0'><div style='font:600 12px "
            f"-apple-system,\"Segoe UI\",Roboto,Arial;letter-spacing:.4px;"
            f"text-transform:uppercase;color:#42505c;margin-bottom:4px'>"
            f"{title}</div><table style='border-collapse:collapse'>"
            f"{_rows}</table></div>"))
        return
    print(f"\n  {title}")
    _w = min(max((len(c) for c, _ in items), default=0), 44)
    for _c, _d in items:
        if len(_c) <= _w:
            print(f"    {_c.ljust(_w)}   {_d}")
        else:
            print(f"    {_c}")
            print(f"    {' ' * _w}   {_d}")
def note_block(title, lines):
    """[Y30] A short bordered aside that must not be scrolled past."""
    if HTML_OUTPUT and _in_jupyter():
        from IPython.display import display, HTML
        _b = '<br>'.join(lines)
        display(HTML(
            _CSS + f"<div style='margin:10px 0;padding:9px 12px;"
            f"border:1px solid #e3e6ea;border-left:3px solid #b26a00;"
            f"border-radius:0 6px 6px 0;background:#fffdf9;font:12.5px/1.6 "
            f"-apple-system,\"Segoe UI\",Roboto,Arial;color:#42505c'>"
            f"<b style='color:#1c2733'>{title}</b><br>{_b}</div>"))
        return
    _inner = _W - 4                       # width between the │ borders
    print('\n  ┌' + '─' * _inner + '┐')
    print('  │ ' + title[:_inner - 2].ljust(_inner - 1) + '│')
    print('  ├' + '─' * _inner + '┤')
    for _l in lines:
        print('  │ ' + str(_l)[:_inner - 2].ljust(_inner - 1) + '│')
    print('  └' + '─' * _inner + '┘')
# ============================================================================
# [Y5] GRID MATRICES AS HEAT MAPS — call show_grid_html() after the run
# ============================================================================
def kv_table(title, rows, note='', col='reading'):
    """[Y28] Render a list of (label, value) — or (label, value, note) —
    as one table, with the plain-text fallback aligned. This is the shape
    almost every diagnostic block wants: a label column and a reading."""
    _rows = [tuple(r) + ('',) * (3 - len(r)) for r in rows]
    if HTML_OUTPUT and _in_jupyter():
        _df = _pd.DataFrame(_rows, columns=['', col, 'note']).set_index('')
        if not any(r[2] for r in _rows):
            _df = _df.drop(columns=['note'])
        show_html_table(_df, title=title, fmt='{}', note=note)
        return
    print('\n  ' + str(title))
    print('  ' + '\u2500' * min(max(len(str(title)), 20), 76))
    _w = max((len(str(r[0])) for r in _rows), default=10)
    for _a, _b, _c in _rows:
        print(f"  {str(_a):<{_w}}  {_b}" + (f"   {_c}" if _c else ''))
    if note:
        print(f"  {note}")
 
def show_grid_html():
    """[Y5] The three grid matrices (PnL / win rate / trades) plus Sharpe as
    heat-mapped HTML tables. Reads the results_* arrays the grid search left
    in globals — run the backtest first."""
    _g = globals()
    _idx = [f"N={n}" for n in N_VALUES]
    _col = [f"Z={z}" for z in THRESHOLD_VALUES]
    for _name, _arr, _fmt in (
            ('NET PnL ($)', _g['results_pnl'], '{:,.0f}'),
            ('SHARPE', _g['results_sharpe'], '{:.2f}'),
            ('WIN RATE (%)', _g['results_winrate'], '{:.1f}'),
            ('TRADES', _g['results_trades'], '{:.0f}')):
        show_html_table(_pd.DataFrame(_arr, index=_idx, columns=_col),
                        title=_name, heat=True, fmt=_fmt)
    show_html_table(
        _pd.DataFrame({'plateau mean (Z>=1.5, >=15tr)':
                       {'Net PnL': f"${_np.nan_to_num(_g['results_pnl']).mean():,.0f} (see [33] for the exact mask)"}}).T,
        title='', note="Read the heat maps for STABLE REGIONS, not single "
        "bright cells — the honest expectation is the plateau mean ([33]), "
        "not the argmax.")
 
# ============================================================================
# [Y7] SUSPECT-GAP TERMINAL CARD
# ============================================================================
def gap_check_card():
    """[Y22] retired — the heuristic it reported on is removed. Overnight
    gaps are real market information (both files hold the same-date
    contract, user-verified); only the exact [K7] label test can flag."""
    print('[Y22] retired: overnight gaps are treated as REAL. Only an exact '
          '[K7] contract-label mismatch flags a row, and that prints in the '
          'data section.')
 
# ============================================================
# CONFIG — ALL TUNABLES IN ONE PLACE  [12]
# ============================================================
# Every path, ticker-independent constant and magic number lives here.
# Nothing below this block should need editing for normal use.
VERBOSE = False   # [9] True = full trade logs, all matrices, deep dives
# ============================================================
# [U0] INSTRUMENT SWITCH — change THIS ONE LINE to swap underlying.
# Everything instrument-specific (tickers, ADR ratio, order-book cost
# parameters, vol fallbacks, notional, dividends, earnings) lives in
# the INSTRUMENTS dict below. Everything MARKET-wide (the HK/US
# conventions this whole file is built on) sits in the block after it.
# ============================================================
INSTRUMENT = globals().get('INSTRUMENT', 'BABA')   # [Y16] set AT THE TOP
MARKET = 'HK'          # this file IS the HK book — see the header
# ============================================================
# [HK0] WHAT MAKES THE HK BOOK DIFFERENT FROM THE TAIWAN ONE.
# These are not options; they are the reason this file exists apart
# from v32_tw_full.py. Every one of them is FIRST-CLASS here — there
# is no `if MARKET == 'HK'` anywhere in this file.
#
#  1. NO PER-NAME NIGHT HEDGE. HKEX single stock futures do not trade
#     the T+1 (after-hours) session; only INDEX futures do. The hedge
#     is therefore Hang Seng TECH futures (HTI, HK$50/pt, ~US$28k a
#     contract), and it is IMPERFECT: beta(BABA)~0.7, beta(Tencent)
#     ~0.57. beta comes from a rolling regression [HKB], never 1.0,
#     and the unhedged idio residual — not FX staleness — is what
#     sets the entry floor [HK-H2].
#  2. THE HEDGE PRINT IS STALE AT THE US CLOSE. The T+1 session ends
#     03:00 HKT = 19:00 UTC, BEFORE the US close (20:00 UTC summer /
#     21:00 winter). The 2000/2100 UTC snaps are re-reads of that
#     frozen close: 1h stale in summer, 2h in winter. Quantified by
#     [HK2]; it is a signal-noise fact, not a loader bug. The real
#     hedge is worked into the T+1 close (or the next session) — see
#     HEDGE_TIMING.
#  3. ONE SHARED SNAPSHOT SET. The HTI files serve EVERY HK name, so
#     they live under IDX_FILE_PREFIX, not per-instrument paths.
#  4. PEGGED FX. USDHKD 7.75-7.85, deliverable, ~1bp half-spread. No
#     NDF, no forward points, no carry sign to argue about. The
#     [P1]/[H2] FX diagnostics stay ON and should read ~nil — proving
#     that is the point.
#  5. STAMP DUTY, BUT NOT YET. HK charges 10 bps PER SIDE on STOCK
#     transfers. Phase 1 is ADR-only (US-listed, no stamp) hedged
#     with index futures (exempt), so the constants below are present
#     and zero-weighted; the Phase-2 conversion / HK-leg exit prices
#     itself off them.
#  6. DIVIDENDS LIVE IN THE BASIS. An index future is not a TAIFEX
#     stock future: there is no margin-account dividend credit and no
#     per-name ex-date behaviour to vote on. The [T1]/[T3] cash
#     mechanism and the [R5] vote are DELETED from this file, not
#     switched off. What survives is [U5]: the HK ex-date and the ADS
#     ex-date differ, so the SIGNAL still needs the carry correction.
#  7. EARNINGS GAP RISK. China ADRs move violently on quarterly
#     prints released around the US pre-open, so a stretched z into
#     an announcement is more likely informed positioning than noise.
#     [HKE] blocks those entries.
# ============================================================
FX_TICKER = 'USDHKD Curncy'          # fair-price FX (pegged)
FX_SPOT_TICKER = 'USDHKD Curncy'     # next-open conversion print
FX_SPOT_FIELD = 'PX_OPEN'
FX_SANE_BAND = (7.70, 7.90)          # peg band + headroom
HEDGE_SPINE_TICKER = 'HSTECH Index'  # [HKS] marks the hedge leg. A PRICE
                                     # index level is correct: the futures'
                                     # dividend discount is slow-moving and
                                     # cancels in the same-day gap ratio.
ETF_PROXY_TICKER = 'KTEC US Equity'  # HSTECH tracker (index-matched)
ETF_PROXY_ALT = 'KWEB US Equity'     # more liquid, different index
ETF_BORROW_ANN_BPS = 75              # us_etf mode: short-ETF borrow
# [HK0.3] SHARED across every HK name — one HTI capture serves the whole
# complex. Same naming convention as the Taiwan captures
# (TSMC_front_month_1330.csv / _2000utc.csv), so the capture job needs no
# new logic, only a new symbol:
#     HST_front_month_0800utc.csv   16:00 HKT = HK stock close
#     HST_front_month_2000utc.csv   US close, summer (DST)
#     HST_front_month_2100utc.csv   US close, winter (STD)  <- ADD THIS
IDX_FILE_PREFIX = r"G:\FIN_COMM\DeltaOne\Kenny\ADR\HST_front_month_"
IDX_FUT_MULTIPLIER = 50              # HK$ per index point
# ---- how the hedge is put on ------------------------------------
#   'index_fut' : HTI, beta-sized [HKB]. The DEFAULT and the thing the
#                 user already captures. Caveat [HK0.2]: the fill is
#                 worked into the 03:00-HKT T+1 close, 1-2h before the
#                 ADR MOC, so entry and exit each carry a short
#                 unhedged index window (mean-zero, sized by [HK2]).
#   'us_etf'    : KTEC/KWEB at the US close — live through the WHOLE
#                 US session, so no staleness and no sequencing gap;
#                 USD-denominated (no FX leg); stamp-exempt; MOC-able.
#                 Costs a different tracking error (ETF vs HTI) and
#                 the short borrow. The natural challenger — [HK1]
#                 scores it head-to-head on identical entries.
#   'none'      : naked ADR. beta_hedge=0 zeroes the hedge leg in
#                 every formula (PnL, costs, margin, FX). The baseline
#                 every hedged variant must beat risk-adjusted.
HEDGE_MODE = 'index_fut'
# ---- [HKT] WHEN AND WITH WHAT THE HEDGE IS HELD -----------------
# Three executable timings, compared head-to-head by hedge_timing_compare()
# on IDENTICAL entries (the signal never changes):
#   'index_all'        1. HSTech futures for the WHOLE hold — the base
#                         case. Entry hedge worked into the 03:00-HKT T+1
#                         close; carries the index-only hedge (idio
#                         residual [HK-H2]) for the full hold.
#   'index_then_stock' 2. HSTech futures OVERNIGHT ONLY: at the next HK
#                         open (09:30 HKT = 01:30 UTC) the futures are
#                         bought/sold back and REPLACED with the local
#                         stock at its opening auction. From then on the
#                         position is a TRUE ADR-vs-ordinary pair — the
#                         premium is locked, idio risk gone. Pays: a full
#                         futures round trip, the stock's stamp+levies+
#                         spread both ways, and borrow when the stock leg
#                         is short.
#   'stock_open_only'  3. NO overnight hedge: the ADR rides NAKED from
#                         the US close to the next HK open (~5.5h), then
#                         the local stock goes on at the open and locks
#                         the pair. Cheapest hedge stack, biggest
#                         overnight risk.
# DATA each needs: 1. nothing new; 2. the HTI print AT THE HK OPEN —
# add HST_front_month_0130utc.csv (09:30 HKT; HK has no DST so ONE file
# year-round) to the capture job; 3. the ordinary's PX_OPEN (already
# pulled from Bloomberg — no capture needed).
HEDGE_TIMING = 'index_all'
ORD_HALF_SPREAD_BPS = 5.0     # 9988 touch is tight; measure per name
BORROW_ORD_ANN_BPS = 100      # borrowing the HK line (long spread shorts it)
GAP_SOURCE = 'hti'           # DEFAULT — exactly like the Taiwan book: the
                             # overnight gap comes from the CAPTURE-JOB
                             # SNAPSHOT CSVs and nothing else. Same file
                             # family, same loader, same [H1] timestamp
                             # validation, same hard failure if a file is
                             # missing. Two opt-in extensions exist for
                             # BACKFILL ONLY, and neither is on by default:
                             #   'hist_file'    also read HIST_IDX_PATH, an
                             #                  external long tick/bar
                             #                  history, for dates the
                             #                  capture job never covered;
                             #   'proxy_splice' additionally estimate the
                             #                  gap from a US ETF for dates
                             #                  neither source reaches.
                             # They are TIERS: capture snaps always win,
                             # then the history file, then the proxy. Set
                             # the DEEPEST tier you are willing to accept.
# ---- [HKH] OPTIONAL: external index history for BACKFILL ---------
# Only consulted when GAP_SOURCE is 'hist_file' or 'proxy_splice'. The
# capture job is the primary source; this exists because Bloomberg keeps
# only ~140 days of intraday bars, so if you want years of history BEFORE
# the capture job started, a downloaded HSTECH/HTI tick or bar file is
# the honest way to get it. Same folder and naming family as the snaps:
#     HST_front_month_hist.csv
# WHAT IT EXTRACTS, and why those two times:
#   08:00 UTC (16:00 HKT) — the HK stock close, the fair-price anchor;
#   19:00 UTC (03:00 HKT) — the END of the T+1 session, the LAST tradable
#       index print of the day. The 20:00/21:00 UTC capture snaps are
#       re-reads of exactly this frozen price [HK0.2], so taking 19:00
#       from a history file reproduces them rather than approximating.
# FORMAT: any delimited text with a timestamp column and a price column;
# both auto-detected, and what was detected is printed so a wrong guess
# is visible rather than silent.
# DEFAULT None — there is no such file today, and nothing invents one.
# The capture-job snapshots above are the source, exactly as in the
# Taiwan book. If you later download a long HSTECH/HTI history, drop it
# beside the snaps and point this at it, e.g.
#     HIST_IDX_PATH = IDX_FILE_PREFIX + "hist.csv"
# and set GAP_SOURCE = 'hist_file'.
HIST_IDX_PATH = None
HIST_IDX_TZ = 'HKT'           # what the file's timestamps are in: 'HKT' | 'UTC'
HIST_IDX_DT_COL = None        # None = auto-detect
HIST_IDX_PX_COL = None        # None = auto-detect (prefers close/last/price)
HIST_IDX_TOL_MIN = 30         # a snap may be at most this stale vs its target
ORD_STAMP_BPS = 10.0        # HK stamp 0.1%/side, STOCK leg only (Phase 2)
ORD_LEVIES_BPS = 1.1        # SFC + AFRC levies + exchange trading fee
HEDGE_STAMP_BPS = 0.0       # index futures & ETFs are exempt
EARNINGS_BLOCK_DAYS = 2     # [HKE] rows before a print blocked for ENTRY
SNAP_UTC_LOCAL_CLOSE = '08:00'   # 16:00 HKT = HK STOCK close. The HTI day
                                 # session runs to 16:30, so this snap
                                 # shares the stock close's timestamp —
                                 # the clean-basis property the TW 13:30
                                 # snap has for TAIFEX.
# ---- rolling beta [HKB] -----------------------------------------
BETA_EST = 'ewma'           # 'ewma' | 'ols'
BETA_HALFLIFE = 45          # EWMA half-life, rows
BETA_WINDOW = 90            # flat-OLS window, rows
BETA_SHRINK_W = 0.6         # weight on the ROLLING estimate; (1-w) on the prior
BETA_MIN, BETA_MAX = 0.2, 1.5
INSTRUMENTS = {
    'BABA': dict(
        # [HK1a] Alibaba — BABA US ADS vs 9988 HK. FIRST name: the most
        # liquid ADR and HK line of the complex, dual-primary listed,
        # a real NASDAQ closing auction (so EXEC_TIMING='close' MOC
        # fills exist), and the highest index beta (~0.7).
        ADR_TICKER='BABA US Equity',
        ORD_TICKER='9988 HK Equity',
        ADR_RATIO=8.0,                  # 1 ADS = 8 ord — VERIFY on DES
        FILE_PREFIX=r"G:\FIN_COMM\DeltaOne\Kenny\ADR\BABA_",
                                        # charts/ledger ONLY — the futures
                                        # snaps come from IDX_FILE_PREFIX
        CHART_NAME='baba_backtest_charts.png',
        FUT_CONTRACT_SHARES=IDX_FUT_MULTIPLIER,   # [HKC] the slot is reused
                                        # as the index multiplier, so
                                        # contract_usd = 50 x HTI / USDHKD
                                        # (~US$28k) everywhere the TW code
                                        # computed 2000 x SSF / USDTWD
        NOTIONAL=500_000,               # ~12-13 HTI contracts at beta~0.7
        K_ADR_FALLBACK=250,             # ~2.5%/day — refresh from data
        K_FUT_FALLBACK=180,             # HTI ~1.8%/day — refresh from data
        # ADR book: the BABA closing auction is enormous, half-spread
        # ~1c on ~$120. HTI book: PLACEHOLDERS pending the QR read of
        # the T+1 tail (02:00-03:00 HKT) — the [P6] procedure.
        ADR_HALF_SPREAD_OPEN_BPS=1.5,  FUT_HALF_SPREAD_OPEN_BPS=5.0,
        FUT_L1_BID_OPEN=40,  FUT_L1_ASK_OPEN=40,  FUT_REPLENISH_OPEN=10,
        ADR_WINDOW_VOL_OPEN_USD=250_000_000,
        FUT_WINDOW_VOL_OPEN_USD=30_000_000,
        ADR_HALF_SPREAD_CLOSE_BPS=1.0, FUT_HALF_SPREAD_CLOSE_BPS=6.0,
        FUT_L1_BID_CLOSE=15, FUT_L1_ASK_CLOSE=15, FUT_REPLENISH_CLOSE=2.0,
        ADR_WINDOW_VOL_CLOSE_USD=1_000_000_000,
        FUT_WINDOW_VOL_CLOSE_USD=10_000_000,
        MIN_ENTRY_DEV_BPS_INST=0,    # set from [HK-H2] x the multiplier the
                                     # [HK-1A] study justifies. The TW "2x
                                     # the FX floor" convention does NOT
                                     # transfer: part of this residual is
                                     # real news, not measurement noise.
        MANUAL_DIVIDENDS=[],         # (HK ex-date, HKD/share) if 9988's TR
                                     # field turns out price-only
        DIV_MAX_ONE_DAY=0.05,
        DIV_YIELD_EXPECTED_ANN=0.012,   # ~1%/yr regular + specials
        DRIFT_MAX_SIGMA_INST=0.50,   # China ADRs re-rate hard — start tight
        ADR_FEE_OUT_BPS_INST=2,      # on-market exit. The 32bps depositary
                                     # CANCELLATION fee belongs to the
                                     # Phase-2 conversion exit, not here.
        FUT_FEE_IN_BPS_INST=1, FUT_FEE_OUT_BPS_INST=1,   # HTI fees+levy on
                                     # a ~US$28k contract are <1bp
        BETA_PRIOR_INST=0.70,        # user-measured anchor; refreshed at
                                     # runtime by the 2y daily regression
        MANUAL_EARNINGS=[],          # quarterly announcement dates
                                     # 'YYYY-MM-DD', ~20 rows for 5y.
                                     # EMPTY = gate OFF (prints a warning).
    ),
    # ---- Phase 2 names: fill the book/vol/dividend fields the same
    # way BABA's were, verify every ADR_RATIO on DES, then run.
    # TCEHY goes LAST: it is OTC with NO closing auction, so
    # EXEC_TIMING='close' MOC fills do not exist for it.
    'JD': dict(
        ADR_TICKER='JD US Equity', ORD_TICKER='9618 HK Equity',
        ADR_RATIO=2.0, CHART_NAME='jd_backtest_charts.png',
        FILE_PREFIX=r"G:\FIN_COMM\DeltaOne\Kenny\ADR\JD_",
        FUT_CONTRACT_SHARES=IDX_FUT_MULTIPLIER, NOTIONAL=300_000,
        K_ADR_FALLBACK=280, K_FUT_FALLBACK=180,
        ADR_HALF_SPREAD_OPEN_BPS=2.0, FUT_HALF_SPREAD_OPEN_BPS=5.0,
        FUT_L1_BID_OPEN=40, FUT_L1_ASK_OPEN=40, FUT_REPLENISH_OPEN=10,
        ADR_WINDOW_VOL_OPEN_USD=80_000_000, FUT_WINDOW_VOL_OPEN_USD=30_000_000,
        ADR_HALF_SPREAD_CLOSE_BPS=1.5, FUT_HALF_SPREAD_CLOSE_BPS=6.0,
        FUT_L1_BID_CLOSE=15, FUT_L1_ASK_CLOSE=15, FUT_REPLENISH_CLOSE=2.0,
        ADR_WINDOW_VOL_CLOSE_USD=300_000_000, FUT_WINDOW_VOL_CLOSE_USD=10_000_000,
        MIN_ENTRY_DEV_BPS_INST=0, MANUAL_DIVIDENDS=[], DIV_MAX_ONE_DAY=0.06,
        DIV_YIELD_EXPECTED_ANN=0.020, DRIFT_MAX_SIGMA_INST=0.50,
        ADR_FEE_OUT_BPS_INST=2, FUT_FEE_IN_BPS_INST=1, FUT_FEE_OUT_BPS_INST=1,
        BETA_PRIOR_INST=0.75, MANUAL_EARNINGS=[],
    ),
}
globals().update(INSTRUMENTS[INSTRUMENT])
BETA_PRIOR = globals().get('BETA_PRIOR_INST', 0.7)
MANUAL_EARNINGS = globals().get('MANUAL_EARNINGS', [])
# margin funding + contract-roll machinery apply to FUTURES hedges only
_HEDGE_IS_FUT = HEDGE_MODE == 'index_fut'
# file paths derived from FILE_PREFIX (same capture-job naming per name)
# [HK0] HK names read the SHARED index-futures snaps instead: one HTI
# capture serves every HK instrument. Naming: HTI_0800utc.csv (16:00 HKT
# = HK stock close) and HTI_2000utc/2100utc.csv (US close, DST/STD).
# NOTE the 2000/2100 UTC prints are re-reads of the FROZEN 03:00-HKT
# T+1-session close (19:00 UTC): 1h stale in summer, 2h in winter.
# That is a SIGNAL-NOISE fact quantified by [HK2], not a loader problem.
FUT_US_OPEN_DST_PATH = IDX_FILE_PREFIX + "1330utc.csv"   # 13:30 UTC (US summer open)
FUT_US_OPEN_STD_PATH = IDX_FILE_PREFIX + "1430utc.csv"   # 14:30 UTC (US winter open)
FUT_LOCAL_CLOSE_PATH = IDX_FILE_PREFIX + "0800utc.csv"   # 16:00 HKT = HK close
# NOTE the two similar names: "1330.csv" is the 13:30 TAIPEI snapshot (the
# Taiwan-session anchor), while "1330utc.csv" above is 13:30 UTC = the US
# summer OPEN. Different files. If that is too easy to mix up in the capture
# job, rename this one to "1330tpe.csv" and change the line above to match.
FUT_US_CLOSE_DST_PATH = IDX_FILE_PREFIX + "2000utc.csv"  # 20:00 UTC (US summer close)
FUT_US_CLOSE_STD_PATH = IDX_FILE_PREFIX + "2100utc.csv"  # 21:00 UTC (US winter close)
FUT_HK_OPEN_PATH = IDX_FILE_PREFIX + "0130utc.csv"       # [HKT] 09:30 HKT =
                                                         # HK stock open; no
                                                         # DST -> one file
SNAP_UTC_HK_OPEN = '01:30' 
                                                      # [HK] ADD the 2100 file to
                                                      # the HTI capture job BEFORE
                                                      # 2026-11-01 (US DST end)
import os as _os
CHART_PATH = _os.path.join(_os.path.dirname(FILE_PREFIX), CHART_NAME)
# [P2] PRE-CLOSE (15:45 ET) SNAPSHOTS — the decisive implementability
# test: SIGNAL at 15:45 ET, FILL at the 16:00 MOC. Default OFF until
# the capture job produces the files (same CSV format: Date, price in
# col 3, full ISO-UTC capture timestamp in col 4; same [H1] filtering).
# 15:45 ET = 19:45 UTC in US summer, 20:45 UTC in winter.
PRECLOSE_ENABLED = False
PRECLOSE_FUT_DST_PATH = FILE_PREFIX + "1945utc.csv"      # SSF @ 15:45 ET (summer)
PRECLOSE_FUT_STD_PATH = FILE_PREFIX + "2045utc.csv"      # SSF @ 15:45 ET (winter)
PRECLOSE_ADR_DST_PATH = FILE_PREFIX + "adr_1945utc.csv"  # ADR @ 15:45 ET (summer)
PRECLOSE_ADR_STD_PATH = FILE_PREFIX + "adr_2045utc.csv"  # ADR @ 15:45 ET (winter)
SNAP_UTC_PRECLOSE_DST = '19:45'
SNAP_UTC_PRECLOSE_STD = '20:45'
# [35] EXEC_TIMING: 'open' = signal & fills at the US open (original
# design); 'close' = signal & fills at the US CLOSE. Close mode is
# executable via MOC orders into the closing auction (solves the
# observe-and-fill problem and the open-print noise), but needs the
# extra snapshot file(s) below and measures a DIFFERENT edge — the
# open dislocation partly decays intraday, so test, don't assume.
EXEC_TIMING = 'close'   # [R2] user default: MOC, not the open
# [H1] SNAPSHOT TIMESTAMP VALIDATION — the snapshot CSVs carry the
# capture timestamp in the 4th column (UTC, e.g.
# '2024-09-24T13:29:58.428784' for the 21:30-TW/13:30-UTC snap). The
# old stale filter dropped rows purely on Fut_2130 == Fut_1330 exact
# equality — but the user spot-checked some of those days and the
# night price genuinely hadn't moved, i.e. the heuristic over-drops.
# v19 validates the TIME instead: a row is trusted when its capture
# timestamp sits within SNAPSHOT_TIME_TOL_MIN of the file's intended
# snap time (13:28/13:31-style jitter is fine); rows captured at the
# WRONG time are the truly stale ones and are dropped with a report.
# When timestamps validate, price-equality rows are KEPT and only
# REPORTED for spot-checking (equal price + right time can still be
# an untraded night session echoing the day close — check a few on
# QR). Files without a parseable 4th column fall back to the old
# equality heuristic.
SNAPSHOT_TIME_TOL_MIN = 20
SNAP_UTC_US_OPEN_DST = '13:30'
SNAP_UTC_US_OPEN_STD = '14:30'
SNAP_UTC_US_CLOSE_DST = '20:00'
SNAP_UTC_US_CLOSE_STD = '21:00'
# [K6][HK0] 08:00 UTC = 16:00 HKT — set once in the [HK0] block above;
# NOT re-derived here (an earlier draft re-resolved it to the Taiwan
# 05:30 and silently dropped every HK-close snap as 'stale').
                                 # the capture job
                                 # snaps at the TWSE STOCK close (13:30),
                                 # not the 13:30 futures close. GOOD:
                                 # the SSF print then shares the exact
                                 # timestamp of the 2330 close used in
                                 # the fair price (clean basis).
SNAPSHOT_TS_VALIDATED = {}       # loader registry: path -> bool
ALLOW_1330_FALLBACK_IN_WINTER = False   # True = use the (1h-early) 13:30
                                        # print on winter dates missing
                                        # from the 14:30 file; False =
                                        # drop those dates (clean data)
# (ADR_RATIO, CHART_PATH: from the INSTRUMENTS dict [U0])
# ============================================================
# [Y31] DISPLAY LABELS — what the RUN CALLS THINGS.
# ------------------------------------------------------------
# The dataframe column names are fixed generic SLOTS inherited from the
# Taiwan book ('TSM US (Close)', '2330 TT (Close)', 'TWD (Last)',
# 'Fut_1330', 'Fut_2130'). They are deliberately NOT renamed — hundreds
# of lines depend on them and the slots are market-agnostic by design.
# But nothing the USER READS should say "TSM" or "SSF" while you are
# running BABA against HTI. Every label below is derived from the
# instrument actually selected, and every print that names an instrument
# uses these instead of a literal.
def _short(tkr, default='?'):
    """'BABA US Equity' -> 'BABA US'; '9988 HK Equity' -> '9988 HK'."""
    if not tkr:
        return default
    _p = str(tkr).split()
    return ' '.join(_p[:2]) if len(_p) >= 2 else str(tkr)
ADR_LBL = _short(ADR_TICKER)            # e.g. 'BABA US' / 'JD US'
ORD_LBL = _short(ORD_TICKER)            # e.g. '9988 HK' / '9618 HK'
NAME_LBL = INSTRUMENT                   # e.g. 'BABA'
FX_LBL = 'USDHKD'
FX_SRC_LBL = f"'{FX_TICKER}' (pegged 7.75-7.85)"
HEDGE_LBL = {'index_fut': 'HTI', 'us_etf': _short(ETF_PROXY_TICKER),
             'none': 'NO HEDGE'}.get(HEDGE_MODE, 'HEDGE')
HEDGE_LONG_LBL = {
    'index_fut': 'Hang Seng TECH index futures (HTI)',
    'us_etf': f'{_short(ETF_PROXY_TICKER)} ETF at the US close',
    'none': 'no hedge (naked ADR)'}.get(HEDGE_MODE, 'hedge')
EXCH_LBL = 'HKEX'
LOCAL_LBL = 'Hong Kong'
LOCAL_CLOSE_LBL = '16:00 HKT'
LOCAL_CCY = 'HKD'
# ---- Cost model (v14) --------------------------------------------
# [C1] FIXED FEES: the old single FIXED_FEES_BPS=40 lump is REMOVED and
# replaced with explicit per-leg, per-direction fees, charged on the
# LEG'S OWN notional:
#     ADR (TSM US) : IN 2 bps, OUT 32 bps
#     SSF (TAIFEX) : IN 2 bps, OUT  2 bps
# "IN" = opening trade of that leg, "OUT" = closing trade of that leg
# (whichever side that happens to be). Round-trip fee total for a
# beta=1 trade is 2+32+2+2 = 38 bps of NOTIONAL.
# SIDE = IN/OUT (user-confirmed): IN charged ONCE at entry, OUT ONCE
# at exit, each on that leg's own notional — never doubled, never per
# buy/sell. A roll [I3] closes+reopens the SSF leg, so each roll
# charges SSF IN+OUT (and the SSF spread) again; the ADR leg is
# untouched by rolls.
# [X2] THESE ARE NOW PER-INSTRUMENT OVERRIDABLE. Reason: a depositary
# (DR) cancellation fee is a fixed CASH amount per ADR — typically
# $0.02-$0.05 a share — so its value in BPS scales INVERSELY with the
# ADR price. 32 bps on a $250 TSM ADR is ~8.0c/share; the SAME 32 bps
# on a ~$7 UMC ADR is only ~2.2c/share. One of the two is wrong, and
# because the constant used to live in the SHARED block both names were
# forced to use whichever one was calibrated. Put ADR_FEE_OUT_BPS_INST
# in the INSTRUMENTS dict for any name whose ADR price is far from the
# one these were measured on. The [X2] print below shows the implied
# cents-per-share for the CURRENT name so the error is visible.
ADR_FEE_IN_BPS = globals().get('ADR_FEE_IN_BPS_INST', 2)
ADR_FEE_OUT_BPS = globals().get('ADR_FEE_OUT_BPS_INST', 32)
FUT_FEE_IN_BPS = globals().get('FUT_FEE_IN_BPS_INST', 2)
FUT_FEE_OUT_BPS = globals().get('FUT_FEE_OUT_BPS_INST', 2)
# [C3][D1] FX (TWD NDF) — split into TWO separate things:
#   (a) TRANSACTION cost: you cross the NDF bid/ask twice (hedge on at
#       entry, hedge off at exit), paying the 2 bps HALF-spread each
#       time -> 4 bps round trip on the hedged (futures-leg) notional.
#       Direction-INDEPENDENT: both sides pay the spread.
#   (b) CARRY (forward points): direction-DEPENDENT and SIGNED.
#       LONG spread  (buy ADR / short SSF): the package is net long
#         TWD through the ADR -> the hedge SELLS TWD forward (buys
#         USD forward). With USD rates above TWD rates the USD trades
#         at a forward DISCOUNT, so this side typically EARNS carry
#         (~ the rate differential, distorted by the NDF market).
#       SHORT spread (sell ADR / long {HEDGE_LBL}): the exact opposite side
#         of the same forward -> carry flips sign (typically PAYS).
#     Convention here: FX_CARRY_LONG_SPREAD_ANN_BPS is the annualised
#     carry EARNED (+) or PAID (-) by the LONG-spread hedge; the
#     short-spread hedge automatically gets the NEGATIVE of it.
#     GET THE REAL NDF POINTS FROM YOUR FX DESK — the TWD NDF is
#     notoriously off-CIP, the sign is NOT guaranteed.
FX_NDF_HALF_SPREAD_BPS = 2
FX_CARRY_LONG_SPREAD_ANN_BPS = 0   # + = long-spread hedge EARNS; short pays the same
# [O1] FX EXECUTION MODE (user request): instead of an NDF at trade
# time, convert the TWD flows in ONSHORE SPOT at the NEXT Taiwan
# morning open, paying an 8 bps HALF-spread each way (user-quoted,
# presumably including the bank's conversion markup) -> 16 bps round
# trip on the futures-leg notional, replacing the NDF's 4 bps.
#   'spot_next_open' : cost = 2 x FX_SPOT_HALF_SPREAD_BPS; NO forward
#                      -point carry (deliverable spot); the trade-to-
#                      conversion window (US print -> 09:00 Taipei,
#                      ~5h in close mode / ~11.5h in open mode) is
#                      UNHEDGED FX drift — mean-zero, sigma reported
#                      at the header from the data.
# [HKS] there is no 'ndf_immediate' alternative in this book: USDHKD is
# a deliverable pegged rate, so the hedge FX simply converts in spot.
# TICKER: 'USDHKD Curncy' PX_OPEN — the next HK morning's print. Two
# ways to get it: (a) daily PX_OPEN of USDHKD via
# BDH — VERIFY on FLDS that PX_OPEN is populated and check on DES
# which session its 'open' stamps; (b) safer: add a 01:0x UTC
# 'USDTWD REGN Curncy' snap to the existing capture job. Do NOT use
# 'TWD F093' (TW-close BFIX) for this — wrong time of day.
FX_EXEC_MODE = 'spot_next_open'   # [HKS] the ONLY mode here — USDHKD
                                  # is deliverable and pegged; the NDF
                                  # path is deleted from this book
FX_SPOT_HALF_SPREAD_BPS = 1       # [HK0] pegged deliverable HKD -> 2 bps RT
# [P1] the actual next-morning conversion rate, pulled via blpapi:
# [HK0] FX_SPOT_TICKER / FX_SPOT_FIELD are set in the [HK0] block above
# ('USDHKD Curncy' / 'PX_OPEN') and deliberately NOT re-resolved here.
                                        # next HK morning's open print; if the QC
                                        # below reports it unpopulated, add a
                                        # 01:0x UTC snap to the capture job
                                        # instead
# [O2] FUTURES MARGIN FUNDING (user request): funding the margin
# posted at TAIFEX, 24 bps ANNUALISED on the futures-leg notional,
# charged on CALENDAR days held, BOTH directions (margin is posted
# whether the leg is long or short).
# [R2] Two conventions, pick with FUT_MARGIN_MODE:
#   'flat_bps' : an all-in desk quote — FUT_MARGIN_ANN_BPS on the
#                futures-leg notional (current: 24).
#   'sofr_plus': the usual dealer arithmetic — you post MARGIN_PCT of
#                notional as collateral, fund it at (FUNDING_RATE_ANN
#                + MARGIN_SPREAD_BPS) and receive MARGIN_DEPOSIT_ANN
#                on the deposit:
#                cost_ann = MARGIN_PCT x (FUNDING + spread - deposit).
#                With 13.5% margin, SOFR+24 funding and 0 deposit
#                interest that is ~13.5% x 5.0% = ~67 bps ann — very
#                different from a flat 24. CONFIRM WITH THE DESK which
#                number the 24 actually is.
# Charged on the futures leg in BOTH directions (long or short — the
# margin is posted either way), calendar days.
FUT_MARGIN_MODE = 'flat_bps'   # 'flat_bps' | 'sofr_plus'
FUT_MARGIN_ANN_BPS = globals().get('FUT_MARGIN_ANN_BPS_INST', 24)   # [HK0] per-inst
MARGIN_PCT = 0.135             # TAIFEX SSF initial margin class — verify
MARGIN_SPREAD_BPS = 24         # funding spread over FUNDING_RATE_ANN
MARGIN_DEPOSIT_ANN = 0.0       # interest earned on the posted margin
def margin_ann_bps(funding_rate=None):
    _f = FUNDING_RATE_ANN if funding_rate is None else funding_rate
    if FUT_MARGIN_MODE == 'sofr_plus':
        return MARGIN_PCT * (_f + MARGIN_SPREAD_BPS / 1e4
                             - MARGIN_DEPOSIT_ANN) * 1e4
    return float(FUT_MARGIN_ANN_BPS)
# [R6] SHORT-PROCEEDS REBATE — short spread sells the ADR; the cash
# proceeds normally EARN (funding minus the borrow fee) at the PB.
# Ignoring it (0.0) is conservative; set the annualised rate the desk
# actually pays to credit it.
SHORT_REBATE_ANN = 0.0
# [C5][E3][F2] MICROSTRUCTURE — read off the ORDER BOOK screenshots
# (07/14/26, 21:40:32-40 HKT, just after the US open), RE-EXAMINED
# carefully this time. What the book ACTUALLY shows:
#   SSF quotes (TWD): the spread ALTERNATES between 1 and 2 TWD —
#     2466/2467 and 2465/2466 (1 TWD = ~4 bps full) but also
#     2465/2467 (2 TWD = ~8 bps full) -> HALF-spread 2-4 bps,
#     modelled at 3 bps.
#   SSF depth is ASYMMETRIC and time-varying: in one window the BID
#     shows only 9-14 contracts while the ASK shows 37-52; minutes
#     later the BID shows 51-55 and the ASK 20-72. So each SIDE is
#     modelled separately, conservatively at its observed THIN state:
#     bid L1 ~10, ask L1 ~20. NOTE a round trip crosses EACH side
#     once (long spread: SELL futures at entry -> bid side, BUY back
#     at exit -> ask side; short spread the mirror), so each ONE-WAY
#     is tested against ITS OWN side's capacity — the total is
#     direction-independent under a static book.
#   SSF tape: 15 contracts trade in ~5s at the open burst; sustained
#     replenishment modelled at 5 contracts/min (conservative).
#   ADR tape (USD): ~38 prints totalling ~3,500 shares (~$1.5M) in
#     ~2 SECONDS, sizes 1-500 sh. Touch spread 1-3c (0.2-0.7 bp) but
#     prints DISPERSE 425.01-425.34 (~8 bps) within seconds — that
#     dispersion is short-horizon volatility while you work the
#     order, not spread; it is what the buffer is for.
# UNITS (explicit): SSF quoted in TWD, ADR in USD. 1 contract =
# FUT_CONTRACT_SHARES x price(TWD) / USDTWD = 2,000 x ~2,466 / ~32 =
# ~US$152k — computed per-day from actual data, never hard-coded.
# COST_MODEL:
#   'book' (default): a one-way leg that FITS inside its side's
#     supply over the window (L1 + replenishment) pays HALF-SPREAD +
#     buffer, nothing else; an oversized leg falls back to sqrt law.
#   'sqrt': the v14 parametric model (sensitivity checks).
COST_MODEL = 'book'
# (FUT_CONTRACT_SHARES and ALL order-book numbers: INSTRUMENTS dict [U0])
BOOK_BUFFER_FUT_BPS = 0.5    # adverse-selection/slippage buffer beyond half-spread
BOOK_BUFFER_ADR_BPS = 0.5    # covers the observed intra-second print dispersion
EXEC_WINDOW_MIN = 10
# Order-book microstructure (half-spreads, L1 depth, replenishment,
# window volumes) is PER-INSTRUMENT — see the INSTRUMENTS dict [U0].
# The measured-book provenance notes live there too, kept short.
EXEC_WINDOW_CLOSE_MIN = 20        # night tail allows patient legging (shared)
IMPACT_ETA = 0.5              # sqrt-law coefficient (0.3-1.0 typical)
PARTICIPATION_WARN = 0.10     # warn if we'd need >10% of window volume
# [Z2] SHORT-SPREAD FUNDING LOGIC, for the record: a short sells the
# ADR and RECEIVES cash — there is no cash borrowing, hence funding=0
# on shorts is CORRECT, not missing. In real practice those proceeds
# even EARN a rebate (~SOFR minus the GC spread); we ignore that
# (SHORT_REBATE_ANN=0) which makes short-side costs CONSERVATIVE.
# 50 bps borrow is realistic for a GC mega-cap ADR like TSM; smaller
# names can be specials — confirm per name with the SBL desk.
BORROW_ANN_BPS = globals().get('BORROW_ANN_BPS_INST', 50)   # borrow, flat (per
                              # user); [HK0] per-instrument overridable —
                              # needed later for BILI, which can be special
FUNDING_RATE_ANN = 0.050      # [T1] fallback ONLY (used if the SOFR pull
                              # fails) — raised from 4.7% to 5.0%. The
                              # LIVE funding is the daily SOFR series
                              # PLUS FUNDING_SPREAD_ANN below.
FUNDING_SPREAD_ANN = 0.012    # [T1][T4] applies to FUNDING ONLY (SOFR +
                              # 1.2%). Does NOT touch borrow (flat 50 bps)
                              # or margin (flat 24 bps) — those are fixed.
FUNDING_TICKER = 'SOFRRATE Index'   # daily USD SOFR; verify on the
                                    # terminal. Value is a percent
                                    # (e.g. 5.31), converted /100, then
                                    # + FUNDING_SPREAD_ANN.
STRESS_MULT = 1.2
# (K_ADR_FALLBACK / K_FUT_FALLBACK: from the INSTRUMENTS dict [U0])
# ---- Strategy parameters ----
N_VALUES = [10, 15, 20, 25, 30, 35, 40]   # [G3][M4]
THRESHOLD_VALUES = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0]  # [G3] extended
ADF_WINDOW = 125
# [Q3] WARM-UP. The backtest cannot trade until row max(window, n_zscore),
# because the regime gate needs history. With ADF_WINDOW=125 that burns
# 125 rows — on UMC's 334-row sample that is 37% of the data, which is
# why the first UMC trade only appeared in Aug 2025 despite data from
# Dec 2024. It is NOT a data problem and NOT the gate switching off.
# The 125 length exists to make an ADF p-value meaningful, but
# GATE_MODE='halflife_drift' never reads that p-value: it uses the AR(1)
# gamma (fine on ~60 rows, and more responsive) and a 5-row mean shift.
# So when the gate is not an adf_* mode, use the shorter window.
GATE_WINDOW = 60
# [X3] BUGFIX (warm-up contamination). For every gate mode except
# 'adf_level' the gamma/ADF series is computed on the DE-TRENDED
# deviation, built as
#     level - level.rolling(ADF_DETREND_N).mean().shift(1)
# whose first ADF_DETREND_N values are NaN and were .fillna(0.0)'d. The
# first gamma window (rows 0..GATE_WINDOW-1) therefore contained ~20
# SYNTHETIC ZEROS, so the gate's very first verdicts were driven partly
# by padding rather than by data. True = push the first tradable row out
# by ADF_DETREND_N so every gamma window is real data.
# NOTE: this CHANGES results — it costs ~20 rows of sample and can add
# or remove the earliest trade. Set False to reproduce the old numbers.
GATE_WARMUP_STRICT = True
def gate_window():
    # [U1] the warm-up the GATE needs. ADF modes need the long window for
    # a meaningful p-value; the halflife/drift gate needs GATE_WINDOW for
    # the AR(1) gamma; 'none' reads no history so it adds no warm-up and
    # only n_zscore binds the start. Answers the 'does the reference
    # window push the start date' question: only the parts the gate
    # actually consumes do — not the display references.
    if GATE_MODE in ('adf_level', 'adf_deviation'):
        return ADF_WINDOW
    if GATE_MODE == 'none':
        return 0
    return GATE_WINDOW
def first_tradable_row(n_zscore):
    """[X3] The single definition of the warm-up, used by run_backtest, the
    [Q3] header print and the [W4]/[X6] audits so all three can never
    disagree. Adds ADF_DETREND_N when the gate reads a DE-TRENDED series,
    because that series' first ADF_DETREND_N values are padding."""
    _pad = (ADF_DETREND_N if (GATE_WARMUP_STRICT and GATE_MODE != 'adf_level'
                              and gate_window() > 0) else 0)
    return max(gate_window() + _pad, n_zscore)
# [W2] ADF stationarity gate policy:
#   ADF_PVALUE       : p-value below which the pair counts as
#                      cointegrated/stationary (gate ON). 0.05 is
#                      strict; premium-mode series often need 0.10-0.20.
#   ADF_EXIT_POLICY  : what a mid-hold ADF turn-OFF does —
#     'entry_only' (DEFAULT): ADF gates NEW ENTRIES only; an open
#                   position is NOT force-closed on ADF off (exits come
#                   from z-cross / time-stop / gamma). Stops the
#                   on/off churn that bleeds P&L in premium mode.
#     'force_exit' : the old behaviour — ADF off flushes the position.
#     'ignore'     : ADF ignored entirely (entry gated only by z).
ADF_PVALUE = 0.05
ADF_EXIT_POLICY = 'entry_only'
# [Z1] WHAT the ADF tests. The old design ran ADF on the raw signal
# LEVEL over 125d — but the strategy never trades the level; it trades
# DEVIATIONS from a short rolling mean (the z-score de-means it). For
# TSM the premium LEVEL genuinely is non-stationary over 2024-26 (a
# structural re-rating from ~8% to ~25%), so a level-ADF correctly
# says "unit root" and switches the gate OFF for months — even while
# the DEVIATIONS the strategy actually trades revert fine. Testing the
# level while trading the deviation is a statistical mismatch; the
# gate should test the traded object:
#   'deviation' (DEFAULT): ADF + AR(1)-gamma run on
#                (spread - rolling ADF_DETREND_N mean), the de-trended
#                object the z-score trades. Fixes the premium-mode
#                "ADF always OFF" problem for trending names.
#   'level'    : the old behaviour, kept for comparison.
ADF_TEST_ON = 'deviation'   # 'deviation' | 'level' (used by the adf_* gate modes)
ADF_DETREND_N = 20          # fixed de-trend window (NOT the grid's n_zscore,
                            # so the ADF object is stable across the grid)
# [Z3] REGIME GATE REDESIGN. Correct signal-processing objection (user):
# a rolling-mean residual is HIGH-PASS FILTERED — any integrated series'
# residual is stationary BY CONSTRUCTION, so 'adf_deviation' degenerates
# toward always-ON and a longer de-trend window only shrinks, not fixes,
# that bias. What we actually want a red light for is (i) deviations
# that stop mean-reverting fast enough to beat carry, and (ii) a mean
# that is itself MOVING (a re-rating / one-way crash you must not
# fade). So the recommended gate tests those two things directly:
#   'halflife_drift' (DEFAULT):
#       ON iff  gamma < 0  AND  implied half-life <= HL_MAX_DAYS
#            AND |rolling mean(t) - rolling mean(t-5)| <= DRIFT_MAX_SIGMA
#                x current sigma      (drift-to-noise repricing filter)
#       -> economically meaningful thresholds instead of a p-value;
#          goes RED in one-way repricings even though the filtered
#          residual would still 'pass' an ADF.
#   'adf_deviation' : the (weak) p-value test on the residual.
#   'adf_level'     : the original level test (OFF for months on TSM).
#   'off'           : no regime gate; z-band + cost band only.
GATE_MODE = 'halflife_drift'
HL_MAX_DAYS = 15            # reversion must be faster than the TIME_STOP
DRIFT_MAX_SIGMA = globals().get('DRIFT_MAX_SIGMA_INST', 0.75)   # [M7] per-name
_DRIFT_DOC = """[Z4] 5-row mean shift vs sqrt(5) x daily-
                            # change sigma. Synthetic calibration on a
                            # TSM-paced re-rating (20 bps/day for 3m):
                            #   1.00 -> calm 100% ON / repricing 89% ON (too lax)
                            #   0.75 -> calm 100% / repricing 42%  (default)
                            #   0.50 -> calm  99% / repricing 15%  (aggressive)
                            # Calibrate on REAL data with the [Z4]
                            # drift-ratio diagnostic printed below."""
# (NOTIONAL: from the INSTRUMENTS dict [U0])
# [J5] SUSPECT OVERNIGHT-GAP GUARD. fut_gap_ret = Fut_2130/Fut_1330-1
# assumes BOTH files quote the SAME contract. In close mode the 2130
# print is captured at 20:00/21:00 UTC = 04:00/05:00 TAIPEI THE NEXT
# DAY, so a 'front month = next month' capture job can roll one session
# EARLIER than the 13:30 job. On such a row the ratio is a CALENDAR
# SPREAD between two contracts, not an overnight move — and because
# the same wrong price becomes entry_fut_raw, the next day's 'recovery'
# to the correct contract books a large FAKE hedge profit, with the
# signal pointing whichever way makes that profit. Bias is toward fake
# gains in BOTH directions, so it must be neutralised.
#   'block_entry' (DEFAULT): row kept for marking, but NO new entry
#   'drop_row'   : row removed entirely — safest once you have
#                  confirmed the flagged rows are capture artefacts and
#                  not genuine limit-up/down days
#   'keep'       : old behaviour (not recommended)
# [J6] DIRECTION FILTER. The top-deviation decomposition suggests the
# two directions are NOT symmetric for a re-rating name like TSM:
#   LONG spread  (buy ADR / short SSF) = buying a COMPRESSED premium,
#     usually created by a US-session selloff the Taiwan side has not
#     repriced yet. Time-zone driven, reverts in days.
#   SHORT spread (sell ADR / long {HEDGE_LBL}) = selling an EXPANDED premium,
#     which during a structural re-rating means fading the trend — the
#     loss mode that produces the big losers.
# Test both directions separately before trading either.
DIRECTION_FILTER = 'both'   # 'both' | 'long_only' | 'short_only'
# [M5] PARAMETER SELECTION. 'best_pnl' = the old max-PnL-with-min-trades
# rule (ignores drawdown entirely). 'risk_aware' = highest 3x3
# neighbourhood Calmar among cells that clear a minimum win rate and a
# maximum drawdown, i.e. efficient AND stable AND inside a risk limit.
SELECT_MODE = 'composite'       # [Y6] 'composite' | 'risk_aware' | 'best_pnl'
# [Y6] COMPOSITE weights — 'more trades, higher win rate, higher PnL' is a
# WEIGHTED preference, not a single metric, so state it explicitly. Each
# constraint-passing cell is scored on its PERCENTILE RANK within each
# metric (scale-free), then averaged with these weights.
COMPOSITE_WEIGHTS = dict(pnl=2.0, win=2.0,        # what you optimise FOR
                         sharpe=1.0, trades=1.0,  # quality / evidence count
                         calmar=0.5, lb=0.5)      # risk qualifiers
# [Y14] the selected cell must carry at least the GRID-AVERAGE trade count
# (mean of results_trades over the selectable N rows). A cell below the
# grid's own average frequency is a thin corner even if its stats shine.
MIN_TRADES_GRID_MEAN = True
MIN_WIN_RATE_SELECT = 65.0      # %
# [U6] shortest lookback the selector may choose. A z-score window has to
# hold enough points to estimate a mean and a sigma that are not themselves
# noise. With a measured deviation half-life of ~2-3 days, N=10 is only ~4
# half-lives: the rolling mean chases the very move you are trying to fade,
# so the z-score looks dramatic on cells that are really just short-window
# artefacts. It also wins the risk-aware rank too easily, because a fast mean
# produces small drawdowns. 15 is a defensible floor; set 0 to disable.
MIN_N_SELECT = 15
# [V3] HOW CANDIDATES ARE RANKED.
#   'calmar' = PnL / |MaxDD| over a 3x3 neighbourhood. Efficient, but it
#             quietly prefers FEW trades: a cell that trades 6 times has
#             little chance to draw down, so it scores high on almost no
#             evidence.
#   'tstat'  = mean trade PnL / (sd / sqrt(n)) over the same neighbourhood.
#             It answers "could this be luck?", which is the right question,
#             and it is far more stable than a drawdown ratio when n is
#             small. It does NOT, however, mechanically prefer more trades:
#             a tight cluster of 4 winners can out-score 25 mixed ones
#             (measured: t=26 on 4 trades vs t=6 on 25). No single metric
#             forces frequency.
# So if you want MORE TRADES, the honest lever is the hard floor below, not
# the ranking metric. MIN_TRADES_PER_YEAR removes low-frequency cells from
# selection outright; the ranking then picks the best of what remains.
# Every candidate prints t-stat, Calmar, trades/year and a conservative
# lower bound, so the trade-off is visible rather than buried.
SELECT_RANK = 'tstat'           # 'tstat' | 'calmar' | 'lb'
MIN_TRADES_PER_YEAR = 6.0       # frequency floor; 0 = off
MAX_DD_SELECT_PCT = 0.20        # [N1] |MaxDD| <= 20% of the notional
                                # ACTUALLY DEPLOYED (average trade clip),
                                # so the limit scales with size: $1m
                                # deployed -> $200k, $0.5m -> $100k.
                                # All figures in this model are USD.
# [L1] SCORECARD collector — the run prints a lot of detail; every
# check that matters for a go/no-go also files a one-line verdict here,
# and the whole thing is re-printed as a compact scorecard at the END.
SCORECARD = []
def sc(level, key, value):
    """level: 'PASS' | 'WARN' | 'FAIL' | 'INFO'"""
    SCORECARD.append((level, key, str(value)))
# [M6] CAPACITY CAP. z_scaled can double the clip on exactly the days
# liquidity is worst. The v31 run showed the consequence: TSM filled 21
# contracts against a ~12-per-side book on the 2025-04-07 limit-down
# day, and UMC filled 246 contracts against a ~50/75 book. Cap the
# futures leg at a fraction of the visible+replenished book so sizing
# can never exceed what the book could actually absorb. 0 = no cap.
MAX_BOOK_PARTICIPATION = 0.50   # cap contracts at 50% of one side's supply
SUSPECT_GAP_PCT = 0.04        # absolute floor for "implausible overnight move"
SUSPECT_GAP_SIGMA = 4.0       # [K1] ADAPTIVE: also flag |gap| beyond this many
                              # rolling std of the gap itself, so a quiet name
                              # (TSM: basis band ~0.4%) gets a tighter test than
                              # a noisy one (UMC). A row is suspect if it trips
                              # EITHER test.
# [K5] POLICY. 'block_entry' only stops NEW positions — it does NOT
# undo the damage, because the corrupted 2130 print still feeds the
# fair price (hence the signal) and still becomes the hedge mark for
# any position already open. 'repair' actually neutralises it:
#   Fut_2130 := Fut_1330 on the suspect row, i.e. "we have no valid
#   overnight information for this row, so assume no overnight move".
#   That removes the fake gap from the fair price, removes the fake
#   hedge growth, and gives a real (correct-contract) price if the row
#   is used as a fill. It DISCARDS information rather than inventing
#   it, and entries stay blocked on those rows as well.
SUSPECT_GAP_POLICY = 'repair'   # 'repair' | 'block_entry' | 'drop_row' | 'keep'
ROLL_BLOCK_DAYS = 0           # [K1] deterministic belt-and-braces: block ALL
                              # entries within this many calendar days of a
                              # month boundary (0 = off). Set 2 once you have
                              # confirmed the capture job rolls on Taipei date
                              # rather than the file's own date — that makes
                              # month-end rows structurally untrustworthy
                              # regardless of how big the gap looks.
# [S2] PROFIT TAKING. The z-cross-0 rule waits for the spread to cross
# the mean, so a trade that is already well in profit can give it all
# back. PROFIT_TARGET_BPS exits as soon as the two-leg UNREALIZED gain
# reaches X bps of notional. 0 = OFF (pure z-cross exits). Whether it
# is on or off, the [S3] scan below always reports what each target
# WOULD have done, using each trade's maximum favourable excursion.
PROFIT_TARGET_BPS = 0
HARD_STOP_BPS = 0   # [G6] unrealized loss (bps of notional) that force-
                    # exits next check; 0 = OFF. Suggested test: 250-400.
                    # Caps the big losers (re-rating trades that ride the
                    # full TIME_STOP); costs a little in whipsaw re-entries.
# [R5] When True the futures path used for HEDGE VALUATION is scaled up
# by (1 + dividend) from each detected ex-date onward, so the hedge leg
# carries no dividend step. This keeps basis dynamics intact (unlike
# valuing the hedge off the spot TR spine) while removing the
# double-count against the ADR leg's dividend cash.
# THEORY (correct, and the reason this must NOT default to True): a
# futures already trades at S - PV(dividend), so on the ex-date the SPOT
# drops and the FUTURES does not. On that basis the raw futures path is
# ALREADY dividend-neutral and adjusting it would DOUBLE-correct.
# The only reason to adjust is if THIS DATA disagrees with the theory —
# e.g. the captured series is a near-dated contract that has already
# converged, or the print is stale/suspect around the ex-date. So:
#   'auto'  (DEFAULT) : the [R5] diagnostic measures the futures' own
#                       1-day move on every detected ex-date. Adjust
#                       ONLY if the futures actually dropped by more
#                       than half the dividend on most ex-dates.
#   True / False      : force it, after reading the [R5] output.
# [T1][HKS] THE TAIFEX MARGIN-ACCOUNT DIVIDEND DOES NOT EXIST HERE.
# A Taiwan single stock future settles the cash dividend through the
# margin account (long credited, short debited), so the TW file books
# that cash on the hedge leg. An INDEX future has no such mechanism —
# the dividends of its constituents are discounted in the basis and
# nothing is ever paid to the position. Both switches are therefore
# CONSTANTS in this book, not options:
FUT_DIV_CASH = False    # no margin-account dividend on an index hedge
HEDGE_DIV_ADJ = False   # the hedge price path is never rescaled [R5]
# [R7] AND THE MORE LIKELY EXPLANATION. If a contract spans the ex-date it
# must trade at spot - PV(dividend) BEFORE it, so the decisive test is the
# BASIS on the day before, not the drop itself. Worked example, UMC 2025
# ex-date (~06/24): spot before 47.0, dividend ~3.2 (6.8%); a spanning
# contract should print ~43.8 (-6.8%), but the captured print was 47.5 =
# +1.1% CONTANGO — no dividend in it at all. After the ex-date: spot 43.8
# vs futures 43.6, back at parity. So the pre print belongs to a contract
# expiring BEFORE the ex-date and the post print to a later one: the
# -8.2% is a ROLL DISCONTINUITY, not a dividend the hedge paid. The right
# treatment is the [I3] spine splice, which only triggers when the
# contract id changes — and a month-based id misses a break like this.
# So detect breaks from the data: a 1-day futures move the ordinary does
# NOT corroborate is a contract change.
CONTRACT_BREAK_PCT = 0.04   # |fut 1d - ordinary 1d| above this = break; 0 = off
# [S5] Optional ex-date entry guard, default OFF. The one residual risk
# around an ex-date is not economic but a CALENDAR mismatch: the Taiwan
# and ADR ex-dates usually fall on different days, so for a day or two
# the computed premium carries a spurious swing of roughly the dividend
# size. The two-leg P&L nets that out correctly PROVIDED both dividend
# series are detected on the right dates, so it is a data-alignment
# issue, not an exposure. See the [R5] alignment line.
BLOCK_ENTRY_EXDATE_DAYS = 0   # OFF. The exposure this was meant to avoid does
                              # not exist: TAIFEX settles the cash dividend
                              # through the margin account [T1], so both legs
                              # are dividend-neutral. Kept as a switch only.
# [R9] PROFIT TAKING. The only profit exit today is "z crosses 0", which
# waits for FULL mean reversion and — because the decision is daily —
# routinely overshoots (observed exit z of -1.4 on a short entered at
# +1.55). Two optional earlier exits; both default OFF so the base case
# is unchanged, and the [R8] MFE report below tells you what they would
# have been worth before you turn either on.
#   PROFIT_TARGET_BPS : close once the two-leg unrealised gain reaches
#                       this many bps of the trade's notional.
#   PROFIT_TARGET_Z   : close once |z| falls back inside this band, i.e.
#                       bank partial reversion instead of waiting for 0.
PROFIT_TARGET_BPS = 0       # e.g. 150; 0 = off
PROFIT_TARGET_Z = 0.0       # e.g. 0.5; 0 = off
TIME_STOP = 25   # [R1] calendar days, hard cap (user-set; was 15). With
                 # carry ~1.3bp/day (long) / ~0.2bp/day (short) versus
                 # ~38bps of round-trip fees, patience is cheap and
                 # re-entry is expensive; let the gamma exit decide
OOS_SPLIT_DATE = None    # [33] e.g. '2025-01-01': select parameters
                         # on data BEFORE this date, report PnL after
                         # it. None = full-sample (headline stays
                         # in-sample; see plateau stats)
# [34][C3] FX_HEDGE_ANN_BPS removed in v14 — the NDF hedge is now a
# two-way TRANSACTION cost (FX_NDF_HALF_SPREAD_BPS above), plus the
# optional FX_CARRY_ANN_BPS if your desk quotes real forward-point carry.
MAX_ENTRY_GAP_DAYS = 5   # [25] no NEW entry if the next data row
                         # is more than this many calendar days away
# [D3] DYNAMIC SIZING — scale notional with signal strength: rich
# spread -> bigger clip, marginal spread -> base clip. size_mult =
# min(|z_entry| / threshold, SIZE_CAP), so a bare-threshold entry
# trades 1.0x NOTIONAL and a 2x-threshold entry trades up to SIZE_CAP.
# 'fixed' keeps every trade at 1.0x (comparable to earlier versions).
# NOTE: participation stays trivial even at the cap (see [COST] line).
SIZING_MODE = 'z_scaled'   # [R5] ON per user: richer signal -> bigger clip
                           # ('fixed' = every trade 1.0x)
SIZE_CAP = 2.0
# [E2] Align each trade's notional to a WHOLE number of SSF contracts,
# using that day's ACTUAL futures price (TWD) and FX: contract_usd =
# 2,000 x Fut(TWD) / USDTWD. Both legs are then sized off the snapped
# notional, so the ~9%% hedge mismatch of trading 3.29 -> 3 contracts
# disappears (the mismatch moves into a slightly different notional,
# which is harmless). Not rigid: the snap is to the NEAREST contract.
ALIGN_TO_CONTRACTS = True
# [H2] LIVING WITH THE STALE (TW-CLOSE) FX — user confirmed there is
# no Bloomberg historical series for a US-hours USDTWD. Three-part
# answer built into the strategy:
#   (1) PnL is already FX-immune: the NDF hedge locks the rate for
#       the LIFE of the trade; the stale fixing only adds NOISE to
#       the entry/exit SIGNAL (fair price uses yesterday-afternoon
#       FX). Overnight USDTWD sigma is roughly 0.2-0.3%, i.e. a
#       ~15-25 bp noise floor on the spread.
#   (2) The [F1] diagnostic now QUANTIFIES that floor from the data
#       and prints it next to the signal's own deviation sigma.
#   (3) MIN_ENTRY_DEV_BPS gates entries: on top of |z| > threshold,
#       require the deviation |spread - rolling mean| to clear this
#       many bps of ADR price, so pure FX noise cannot trigger a
#       trade. 0 = off; set ~2x the printed FX-noise floor.
# NOTE the asymmetry: LIVE trading does not have this problem at all
# — at 21:30 HKT the live NDF is on screen and the live fair value
# uses it. The stale fixing degrades only the BACKTEST, making it
# CONSERVATIVE relative to the implementable signal. And from TODAY,
# add a 'USDTWD BGN Curncy' snap to the SAME capture job that writes
# the futures CSVs — the history you cannot buy, you can accumulate.
# [H4] set PER INSTRUMENT in the INSTRUMENTS dict as ~2x the [H2]
# measured FX-noise floor (TSMC 31bps -> 62; UMC 40bps -> 80). A
# deviation smaller than that is indistinguishable from the FX timing
# mismatch between the TW-close fixing and the US-close ADR print.
# The dict value overrides this; 0 = no floor.
MIN_ENTRY_DEV_BPS = globals().get('MIN_ENTRY_DEV_BPS_INST', 0)
# [S1] COST-AWARE FLOOR. The FX-noise floor above only says "this
# deviation is bigger than the measurement error". It does NOT say the
# trade can pay for itself. A worked example from the UMC run: a short
# entered on a +79 bps deviation against a 103-111 bps round trip — even
# a PERFECT convergence to zero loses ~24 bps before any adverse move.
# The floor must therefore also clear the round-trip cost:
#     floor = max(FX-noise floor, RT cost x MIN_EDGE_MULT)
# MIN_EDGE_MULT = 1.0 means "break even at perfect convergence", which is
# still too thin; 1.5 asks for a 50% margin over cost. Set 0 to disable
# and keep only the FX-noise floor.
MIN_EDGE_MULT = 1.5
# [M1] FAIR-PRICE ANCHOR. 2026-06-30 exposed a weakness of the
# spot-anchored fair: the 2330 closing auction printed 2410 while the
# July future traded 2455/2460 with 140+ lots BOTH sides at the same
# minute (next day spot opened 2495 — the future was right, the
# auction print was the outlier, likely half-year-end rebalance flow).
# Fair = spot x (1+gap) x 5/FX anchors to that auction print and
# overstated the day's spread by ~2%. Since the tradable pair is
# ADR vs the FUTURE, the arbitrage-consistent fair is the future
# itself:
#   'futures'  : Fair = Fut_2130 x ADR_RATIO / FX   (recommended test)
#   'spot_gap' : Fair = spot x (1+gap) x ADR_RATIO / FX  (v23 default,
#                kept for comparability)
# 'futures' removes auction noise and the spot middleman entirely;
# the residual spot-futures basis (carry/dividend, ~+-0.3% for a
# next-month contract) is slow-moving and absorbed by the z-score
# de-meaning. [C2] prints BOTH fairs on extreme days so the anchor
# effect is visible.
# [HK0] FAIR_MODE is FIXED at 'spot_gap' here and is not a switch. The
# snap is an INDEX future: Fair = Fut x ratio / FX ('futures' mode)
# would price the ADR off the index itself, which is meaningless. The
# only fair price is the ordinary close projected by beta x index gap.
FAIR_MODE = 'spot_gap'
# [V1] SIGNAL_MODE — what the z-score is computed on:
#   'dollar'  : Spread = ADR - Fair  (absolute USD; the original, kept
#               so every earlier backtest stays comparable).
#   'premium' : Spread = (ADR / Fair - 1) * 10000  (premium in BPS,
#               scale-invariant). Recommended when the underlying has a
#               large price trend: a fixed dollar spread is a shrinking
#               % dislocation as the price rises, so a dollar z-score
#               drifts with the price level; a premium z-score does
#               not. Ex-dividend note: this does NOT need any dividend
#               add-back — the signal already uses the RAW ordinary
#               price (or the futures fair), and the futures leg's
#               ex-date is dividend-neutral by construction, so there
#               is no ex-date step to 'fix' (that suggestion mis-read
#               the code). PnL dividend handling is unchanged [Q1].
# Both modes share the same z-score machinery downstream; this only
# changes the units of the Spread column. A/B them on Sharpe.
SIGNAL_MODE = 'premium'  # [H3] DEFAULT (scale-invariant); 'dollar' kept for A/B
# [D2][I1] FX — SETTLED: the only USDTWD history available is the
# TW-close BFIX ('TWD F093'); the US-hours BFIX codes are stale (the
# user verified: fixed at the TW close, never updated), so v20 REMOVES
# the US-open BFIX pull entirely. The fair price always uses the
# TW-close fixing. The consequences are handled, not hidden:
#   - [F1] behaviour test verifies what the series really is,
#   - [H2] quantifies the resulting FX-noise floor on the signal and
#     MIN_ENTRY_DEV_BPS gates entries above it,
#   - PnL itself is FX-immune (NDF hedge locks the rate per trade),
#   - and from today, snap 'USDTWD BGN Curncy' at 21:30/22:30 HKT in
#     the SAME capture job as the futures files — accumulate the
#     history that cannot be bought.
def vprint(*args, **kwargs):
    if VERBOSE:
        print(*args, **kwargs)
def is_us_dst(d):
    """[10] True if date is in US daylight saving (2nd Sun Mar - 1st Sun Nov).
    In DST the US opens 21:30 HKT; otherwise 22:30 HKT."""
    ts = pd.Timestamp(d)
    y = ts.year
    mar = pd.Timestamp(y, 3, 1)
    dst_start = mar + pd.Timedelta(days=(6 - mar.dayofweek) % 7 + 7)   # 2nd Sunday
    nov = pd.Timestamp(y, 11, 1)
    dst_end = nov + pd.Timedelta(days=(6 - nov.dayofweek) % 7)          # 1st Sunday
    return dst_start <= ts < dst_end
 
# ============================================================================
# [HKG] THE PAPER DESK IS **NOT IN THIS FILE** — Phase 2.
# ============================================================================
# The Taiwan book ships a full manual desk (v32_tw_full.py: setup_manual /
# add_day / enter / exit_pos / status / form / zchart). It is not merely
# "not yet tested" for HK — it is built on conventions this book does not
# have, and every one of them would produce a WRONG mark rather than an
# error:
#   * its fair price is the same-name SSF with beta == 1; here the fair
#     needs the rolling beta [HKB] and an INDEX gap;
#   * it books the TAIFEX margin-account dividend [T1][T3], which does
#     not exist on an index future;
#   * its guards assume a TWD band and an SSF-vs-ordinary basis
#     tolerance — meaningless against HTI;
#   * its FX workflow is the TWD next-open NDF/spot dance; USDHKD is a
#     deliverable peg.
# Rather than ship 1,500 lines that raise on use, the desk is simply
# absent. Phase 2 ports it properly (beta term in the fair decomposition,
# HKD guard bands, index-hedge P&L, the 03:00-HKT hedge-timing reminder).
# Until then, run the BACKTEST and the [HK*] diagnostics from this file
# and keep paper trading in the TW book only.
# ============================================================================
_MANUAL = dict(ctx=None, days=[], pos=None, marks=[], closed=[])
def _desk_not_ported(*_a, **_k):
    raise NotImplementedError(
        "[HKG] the manual paper desk is not ported to the HK book yet "
        "(Phase 2). It would mark an index-hedged, rolling-beta, HKD "
        "position with Taiwan SSF conventions and give you plausible but "
        "WRONG numbers. Use the backtest + [HK1]/[HK2]/[HK-H2] "
        "diagnostics here; paper-trade in v32_tw_full.py.")
setup_manual = add_day = add_days = enter = exit_pos = _desk_not_ported
status = form = show_ledger = replay = help_manual = _desk_not_ported
set_dividend = scrub_ledger = fx_fill = cancel_entry = _desk_not_ported
delete_day = position_health = _desk_not_ported
# ============================================================
# SESSION SETUP & DATA PULL
# ============================================================
sessionOptions = blpapi.SessionOptions()
sessionOptions.setServerHost('localhost')
sessionOptions.setServerPort(8194)
session = blpapi.Session(sessionOptions)
session.start()
session.openService('//blp/refdata')
refDataService = session.getService('//blp/refdata')
end_date = datetime.today().strftime('%Y%m%d')
start_date = (datetime.today() - timedelta(days=1825)).strftime('%Y%m%d')
def get_historical_data(session, service, security, field, start, end):
    request = service.createRequest('HistoricalDataRequest')
    request.getElement('securities').appendValue(security)
    request.getElement('fields').appendValue(field)
    request.set('startDate', start)
    request.set('endDate', end)
    request.set('periodicitySelection', 'DAILY')
    # ACTIVE_DAYS_ONLY: do NOT forward-fill holidays. Stale HK prices on
    # HK holidays (while the US trades) create fake spreads. Inner merge
    # below then keeps only dates where BOTH markets actually traded.
    request.set('nonTradingDayFillOption', 'ACTIVE_DAYS_ONLY')
    session.sendRequest(request)
    records = []
    while True:
        event = session.nextEvent(500)
        for msg in event:
            if msg.hasElement('securityData'):
                secData = msg.getElement('securityData')
                if secData.hasElement('securityError'):   # [29]
                    print(f"[QC] Bloomberg securityError for {security} — "
                          f"check the ticker / entitlement")
                if secData.hasElement('fieldData'):
                    fieldDataArray = secData.getElement('fieldData')
                    for i in range(fieldDataArray.numValues()):
                        fieldData = fieldDataArray.getValueAsElement(i)
                        date = fieldData.getElementAsString('date')
                        # [R3] fields like PX_OPEN can be absent on some
                        # days; getElementAsFloat on a missing element
                        # THROWS and kills the whole pull — skip instead
                        if not fieldData.hasElement(field):
                            continue
                        px = fieldData.getElementAsFloat(field)
                        records.append({'Date': date, 'px': px})
        if event.eventType() == blpapi.Event.RESPONSE:
            break
    if not records:   # [29] fail loudly instead of a silent empty merge
        print(f"[QC] WARNING: Bloomberg returned NO data for {security} / {field}")
    return pd.DataFrame(records)
df_TSM_open = get_historical_data(session, refDataService,
                                  ADR_TICKER, 'PX_OPEN',
                                  start_date, end_date).rename(columns={'px': 'TSM US (Open)'})
df_TSM_close = get_historical_data(session, refDataService,
                                   ADR_TICKER, 'PX_LAST',
                                   start_date, end_date).rename(columns={'px': 'TSM US (Close)'})
# FX: kept from your original script. Confirm this ticker is the fix you
# want (TWD per USD, ~32); 'USDTWD Curncy' is the plain alternative.
# [HK0] USDHKD (pegged, so any daily print is fine). The column KEEPS
# the generic 'TWD (Last)' slot name, like every other reused slot.
df_twd = get_historical_data(session, refDataService,
                             FX_TICKER, 'PX_LAST',
                             start_date, end_date).rename(columns={'px': 'TWD (Last)'})
df_2330 = get_historical_data(session, refDataService,
                              ORD_TICKER, 'PX_LAST',
                              start_date, end_date).rename(columns={'px': '2330 TT (Close)'})
# ============================================================
# [HK0] HK-ONLY PULLS — all plain daily BDH, no capture job needed:
#   - HEDGE_SPINE_TICKER (HSTECH Index) level: the [26]-style marking
#     spine for the index-futures hedge leg [HKS] AND the long-window
#     beta-prior regressor [HKB]. A PRICE index is correct here — the
#     futures' dividend discount is slow-moving and cancels in the
#     same-day gap ratio the spine formula uses.
#   - ETF proxy (KTEC, fallback KWEB): extends the overnight index-gap
#     series back through the full BDH history [HKP] where the HTI
#     snapshot capture does not reach.
#   - ordinary PX_OPEN: the [HK-1A] next-session convergence study and
#     the Phase-2 HK-session exit both need it.
# ============================================================
df_idx_spine = None
df_etf_gap = None
df_ord_open = None
try:
    df_idx_spine = get_historical_data(
        session, refDataService, HEDGE_SPINE_TICKER, 'PX_LAST',
        start_date, end_date).rename(columns={'px': 'IDX_close'})
    print(f"[HK0] pulled {len(df_idx_spine)} rows of {HEDGE_SPINE_TICKER}")
except Exception as _e:
    print(f"[HK0] WARNING: could not pull {HEDGE_SPINE_TICKER} ({_e}) — "
          f"the hedge spine will fall back to the snap ratio only")
    df_idx_spine = None
for _etf_tkr in (ETF_PROXY_TICKER, ETF_PROXY_ALT):
    if not _etf_tkr:
        continue
    try:
        _eo = get_historical_data(session, refDataService, _etf_tkr,
                                  'PX_OPEN', start_date, end_date
                                  ).rename(columns={'px': 'ETF_open'})
        _ec = get_historical_data(session, refDataService, _etf_tkr,
                                  'PX_LAST', start_date, end_date
                                  ).rename(columns={'px': 'ETF_close'})
        if len(_ec) > 100:
            _eo['Date'] = _eo['Date'].astype(str)
            _ec['Date'] = _ec['Date'].astype(str)
            df_etf_gap = pd.merge(_ec, _eo, on='Date', how='left')
            df_etf_gap.attrs['ticker'] = _etf_tkr
            print(f"[HKP] gap-proxy ETF: {_etf_tkr}, {len(df_etf_gap)} rows")
            break
        print(f"[HKP] {_etf_tkr}: only {len(_ec)} rows — trying fallback")
    except Exception as _e:
        print(f"[HKP] WARNING: could not pull {_etf_tkr} ({_e})")
if df_etf_gap is None and GAP_SOURCE == 'proxy_splice':
    print("[HKP] WARNING: NO ETF proxy series — GAP_SOURCE falls back "
          "to 'hti' (real snapshots only; short history)")
    GAP_SOURCE = 'hti'
try:
    df_ord_open = get_historical_data(
        session, refDataService, ORD_TICKER, 'PX_OPEN',
        start_date, end_date).rename(columns={'px': '2330 TT (Open)'})
    print(f"[HK0] pulled {len(df_ord_open)} rows of {ORD_TICKER} PX_OPEN")
except Exception as _e:
    print(f"[HK0] WARNING: no ordinary PX_OPEN ({_e}) — the [HK-1A] "
          f"convergence study loses its next-open leg")
    df_ord_open = None
# [26] Daily total-return fields (Bloomberg returns PERCENT). Used to
# build a dividend-correct hedge spine and to credit/debit the ADR's
# dividend cash across a hold. If the field is unavailable the code
# falls back to price-only with a warning.
# [J3] TR FIELD FALLBACK CHAIN. Bloomberg's TR coverage varies by
# ticker: for some TWSE names DAY_TO_DAY_TOT_RETURN_GROSS_DVDS returns
# price-only. So pull EVERY candidate and let the dividend-detection
# validation downstream pick the first one that actually contains
# dividends. 'pct' = one-day % return; 'level' = an index level (the
# shape [G1] prefers, since a level survives row-dropping).
TR_FIELD_CANDIDATES = [
    ('DAY_TO_DAY_TOT_RETURN_GROSS_DVDS', 'pct'),
    ('DAY_TO_DAY_TOT_RETURN_NET_DVDS',   'pct'),
    ('TOT_RETURN_INDEX_GROSS_DVDS',      'level'),
    ('TOT_RETURN_INDEX_NET_DVDS',        'level'),
]
_tr_pulls = {'hedge': {}, 'adr': {}}
for _leg, _tkr in (('hedge', ORD_TICKER), ('adr', ADR_TICKER)):
    for _fi, (_fld, _shape) in enumerate(TR_FIELD_CANDIDATES):
        _col = f'TRc{_fi}_{_leg}'
        try:
            _d = get_historical_data(session, refDataService, _tkr, _fld,
                                     start_date, end_date
                                     ).rename(columns={'px': _col})
            if _d is not None and len(_d):
                if _shape == 'pct':      # [M1] cumprod BEFORE any merge
                    _v = pd.to_numeric(_d[_col], errors='coerce').fillna(0.0)
                    _d[_col + '_lvl'] = (1.0 + _v / 100.0).cumprod()
                else:
                    _d[_col + '_lvl'] = pd.to_numeric(_d[_col], errors='coerce')
                _tr_pulls[_leg][_fi] = _d
                print(f"[J3] {_tkr} {_fld}: {len(_d)} rows")
            else:
                print(f"[J3] {_tkr} {_fld}: EMPTY")
        except Exception as _e:
            print(f"[J3] {_tkr} {_fld}: unavailable ({_e})")
# keep the legacy names pointing at candidate 0 so nothing downstream breaks
df_tr_hedge = (_tr_pulls['hedge'].get(0).rename(columns={'TRc0_hedge': 'TR_hedge'})
               if 0 in _tr_pulls['hedge'] else None)
df_tr_adr = (_tr_pulls['adr'].get(0).rename(columns={'TRc0_adr': 'TR_adr'})
             if 0 in _tr_pulls['adr'] else None)
# [P1] next-morning onshore FX for the spot_next_open conversion —
# pulled while the session is open; merged and QC'd after the merge.
# [S2] daily USD funding series (SOFR) — pulled while the session is
# open; per-row funding replaces the single FUNDING_RATE_ANN constant.
df_sofr = None
try:
    df_sofr = get_historical_data(session, refDataService, FUNDING_TICKER,
                                  'PX_LAST', start_date, end_date
                                  ).rename(columns={'px': 'sofr_pct'})
    print(f"[S2] pulled {len(df_sofr)} rows of {FUNDING_TICKER}")
except Exception as _e:
    print(f"[S2] WARNING: could not pull {FUNDING_TICKER} ({_e}) — falling "
          f"back to the flat {FUNDING_RATE_ANN*100:.1f}% funding constant")
    df_sofr = None
df_fx_regn = None
_regn_ok = False
if FX_EXEC_MODE == 'spot_next_open':
    try:
        df_fx_regn = get_historical_data(session, refDataService,
                                         FX_SPOT_TICKER, FX_SPOT_FIELD,
                                         start_date, end_date
                                         ).rename(columns={'px': 'TWD_regn_open'})
        _regn_ok = len(df_fx_regn) > 0
        print(f"[P1] pulled {len(df_fx_regn)} rows of {FX_SPOT_TICKER} "
              f"{FX_SPOT_FIELD}")
    except Exception as _e:
        print(f"[P1] WARNING: could not pull {FX_SPOT_TICKER} {FX_SPOT_FIELD} "
              f"({_e}) — conversion-rate diagnostics will be skipped; check "
              f"the field on FLDS or snap 01:0x UTC in the capture job")
        df_fx_regn = None
# [G1] CRITICAL FIX — TR must be chained into cumulative INDEX LEVELS
# on the FULL Bloomberg calendar BEFORE any merging/filtering. The
# aligned df later DROPS rows (inner-merge mismatches + stale-snapshot
# filters — ~16% of days in the live run), and chaining ONE-DAY TR
# returns across the surviving rows silently LOSES the dropped days'
# returns, while every PRICE level (ADR, futures) correctly spans the
# gap. Symptoms in the v17 run: the 'TR vs price correlate poorly'
# warning, a systematic ~-$3.5k/trade two-leg-vs-convergence drag,
# and dividends on dropped ex-dates vanishing. A LEVEL survives row
# dropping: growth between any two surviving rows = the index RATIO,
# which includes every intermediate day by construction.
for _trdf, _tr_col, _idx_col in ((df_tr_hedge, 'TR_hedge', 'TRidx_hedge'),
                                 (df_tr_adr, 'TR_adr', 'TRidx_adr')):
    if _trdf is not None and len(_trdf):
        _trdf.sort_values('Date', inplace=True)
        _trdf[_idx_col] = (1.0 + pd.to_numeric(_trdf[_tr_col], errors='coerce')
                           .fillna(0.0) / 100.0).cumprod()
# keep the FULL ADR close series for diagnostics ([C2] true prev close)
_adr_close_full = df_TSM_close.copy().sort_values('Date').reset_index(drop=True)
# ============================================================
# LOAD FUTURES SNAPSHOT FILES  [17][19]
# ============================================================
def load_snapshot_csv(path, price_name, expected_utc=None):
    """[17][H1] Robust loader. If expected_utc ('HH:MM') is given and
    the file's 4th column carries the UTC capture timestamp (e.g.
    '2024-09-24T13:29:58.428784'), each row's capture TIME is checked
    against the intended snap time: within SNAPSHOT_TIME_TOL_MIN ->
    trusted; outside -> genuinely stale capture, dropped + reported.
    Also flags rows whose timestamp DATE disagrees with the Date
    column. Registers path -> True in SNAPSHOT_TS_VALIDATED so the
    downstream price-equality filter knows to only REPORT, not drop."""
    try:
        # [K7] try a 5th column carrying the CONTRACT label/ticker. If the
        # capture job writes it, contract mismatch between the two files
        # becomes an EXACT check instead of a heuristic — strongly
        # recommended (see the note at [K7] below).
        try:
            raw = pd.read_csv(path, header=None, usecols=[0, 2, 3, 4],
                              names=['Date', price_name, 'CapTS',
                                     price_name + '_contract'])
        except Exception:
            raw = pd.read_csv(path, header=None, usecols=[0, 2, 3],
                              names=['Date', price_name, 'CapTS'])
    except Exception:
        raw = pd.read_csv(path, header=None, usecols=[0, 2],
                          names=['Date', price_name])
        raw['CapTS'] = np.nan
    raw['Date'] = pd.to_datetime(raw['Date'], format='%m/%d/%Y', errors='coerce')
    raw[price_name] = pd.to_numeric(raw[price_name], errors='coerce')
    n_bad = int(raw[['Date', price_name]].isna().any(axis=1).sum())
    if n_bad:
        print(f"[QC] {path}: {n_bad} unparseable rows dropped")
    raw = raw.dropna(subset=['Date', price_name])
    # [H1][I2] the 4th column carries the FULL ISO capture timestamp,
    # e.g. '2023-09-01T04:29:57.884544' (UTC, microseconds included) —
    # NOT a bare 'HH:MM'. Parse it as ISO; the format= keyword needs
    # pandas >= 2.0, so fall back to the auto-detecting parser (which
    # handles this exact ISO shape on every pandas version).
    if raw['CapTS'].notna().any():
        try:
            _ts = pd.to_datetime(raw['CapTS'], errors='coerce', format='ISO8601')
        except (TypeError, ValueError):
            _ts = pd.to_datetime(raw['CapTS'], errors='coerce')
    else:
        _ts = pd.Series(pd.NaT, index=raw.index)
    _ts_active = expected_utc is not None and _ts.notna().mean() > 0.5
    SNAPSHOT_TS_VALIDATED[path] = bool(_ts_active)
    if _ts_active:
        _hh, _mm = (int(x) for x in expected_utc.split(':'))
        _target_min = _hh * 60 + _mm
        _cap_min = _ts.dt.hour * 60 + _ts.dt.minute + _ts.dt.second / 60.0
        _diff = (_cap_min - _target_min).abs()
        _diff = np.minimum(_diff, 1440 - _diff)          # wrap-around safe
        _time_ok = (_diff <= SNAPSHOT_TIME_TOL_MIN) & _ts.notna()
        _date_mismatch = _ts.notna() & (_ts.dt.date != raw['Date'].dt.date)
        if _date_mismatch.any():
            _md = raw.loc[_date_mismatch, 'Date'].dt.strftime('%Y-%m-%d').tolist()
            print(f"[QC][H1] {path}: {int(_date_mismatch.sum())} rows whose "
                  f"capture-timestamp DATE differs from the Date column "
                  f"(e.g. {_md[:3]}) — treated as stale")
            _time_ok &= ~_date_mismatch
        _n_stale = int((~_time_ok).sum())
        if _n_stale:
            _bad = raw.loc[~_time_ok]
            print(f"[QC][H1] {path}: dropping {_n_stale} rows captured OUTSIDE "
                  f"{expected_utc} UTC +-{SNAPSHOT_TIME_TOL_MIN}min "
                  f"(genuinely stale captures). Examples:")
            for _, _r in _bad.head(4).iterrows():
                print(f"        {_r['Date'].strftime('%Y-%m-%d')}  "
                      f"captured at {_r['CapTS']}")
        else:
            print(f"[QC][H1] {path}: all {len(raw)} capture timestamps within "
                  f"{expected_utc} UTC +-{SNAPSHOT_TIME_TOL_MIN}min")
        raw = raw.loc[_time_ok]
    elif expected_utc is not None:
        print(f"[QC][H1] {path}: no usable timestamp column — falling back to "
              f"the price-equality stale heuristic downstream")
    n_dup = int(raw['Date'].duplicated().sum())
    if n_dup:
        print(f"[QC] {path}: {n_dup} duplicate dates deduped (kept last)")
    raw = raw.drop_duplicates('Date', keep='last').sort_values('Date')
    raw['Date'] = raw['Date'].dt.strftime('%Y-%m-%d')
    _keep = ['Date', price_name]
    if price_name + '_contract' in raw.columns:      # [K7]
        _keep.append(price_name + '_contract')
    return raw[_keep].reset_index(drop=True)
# [19][35] Build the US-session snapshot from the DST-correct file per
# date. Used for the open (13:30/14:30 UTC) or the close (see CONFIG)
# depending on EXEC_TIMING.
# ============================================================
# [I3][J1] CONTRACT IDENTITY — NEXT-MONTH FILES, MONTH-START ROLL
# ============================================================
# USER-CONFIRMED convention (v21, overriding v20's wrong guess): the
# snapshot files quote the rolling NEXT-month contract — in February
# the March future, in April the May future — and the file switches
# at the MONTH START. The original v13 logic was therefore correct
# and is restored:
#   contract_id(d) = year*12 + month  (same calendar month = same
#                    file contract), exactly the old ym_arr.
# Key economics of this convention: a position entered in month M
# holds the M+1 contract. When the file rolls at the start of M+1,
# the REAL position does NOT roll — the held contract is still alive
# (it expires the 3rd Wednesday of M+1, and a TIME_STOP=15cd hold
# entered in M can never reach that). So crossing the file's roll
# boundary is only a MARKING-SOURCE switch (raw prices -> TR spine),
# NOT a trade: NO roll cost is charged under this rule. n_rolls /
# roll_cost stay in the trade record but are zero.
# ROLL_RULE='expiry_3rd_wed' is kept as an option should any file
# ever be a true front-month series (that rule rolls mid-month and
# DOES charge roll costs).
ROLL_RULE = 'month_start'   # 'month_start' (next-month files, CONFIRMED) | 'expiry_3rd_wed'
def third_wednesday_day(y, m):
    """Day-of-month of the 3rd Wednesday of (y, m)."""
    _first_dow = datetime(y, m, 1).weekday()      # Mon=0 ... Wed=2
    return 1 + (2 - _first_dow) % 7 + 14
def contract_id(dt):
    """Integer id of the FRONT contract at date dt (consecutive across
    rolls, so id differences count roll boundaries crossed)."""
    _base = dt.year * 12 + dt.month
    if ROLL_RULE == 'month_start':
        return _base
    return _base if dt.day <= third_wednesday_day(dt.year, dt.month) else _base + 1
def is_expiry_day(dt):
    return (ROLL_RULE == 'expiry_3rd_wed'
            and dt.day == third_wednesday_day(dt.year, dt.month))
def build_dst_composite_frames(_a, _b, label):
    """[E1] Core DST-composite from two already-loaded frames with
    columns ['Date', 'Fut_dst'] / ['Date', 'Fut_std'] (Date as str).
    Used for the futures CSVs and for the Bloomberg BFIX FX pulls."""
    _a = _a.copy(); _b = _b.copy()
    _a['Date'] = _a['Date'].astype(str)
    _b['Date'] = _b['Date'].astype(str)
    _c = pd.merge(_a, _b, on='Date', how='outer').sort_values('Date')
    _c['is_dst'] = _c['Date'].map(is_us_dst)
    _c['Fut_2130'] = np.where(_c['is_dst'], _c['Fut_dst'], _c['Fut_std'])
    _wm = (~_c['is_dst']) & _c['Fut_std'].isna()
    _sm = _c['is_dst'] & _c['Fut_dst'].isna()
    if _wm.any():
        if ALLOW_1330_FALLBACK_IN_WINTER:
            _c.loc[_wm, 'Fut_2130'] = _c.loc[_wm, 'Fut_dst']
            print(f"[QC] WARNING: {int(_wm.sum())} winter dates missing from the "
                  f"{label} winter file — FALLING BACK to the 1h-early print")
        else:
            print(f"[QC] {int(_wm.sum())} winter dates missing from the "
                  f"{label} winter file dropped (no clean print)")
    if _sm.any():
        print(f"[QC] {int(_sm.sum())} summer dates missing from the "
              f"{label} summer file dropped")
    print(f"[QC] {label} snapshot: "
          f"{int((_c['is_dst'] & _c['Fut_2130'].notna()).sum())} summer dates "
          f"(DST file), {int(((~_c['is_dst']) & _c['Fut_2130'].notna()).sum())} "
          f"winter dates (STD file)")
    return _c.loc[_c['Fut_2130'].notna(), ['Date', 'Fut_2130']].reset_index(drop=True)
def build_dst_composite(dst_path, std_path, label,
                        dst_utc=None, std_utc=None):
    return build_dst_composite_frames(
        load_snapshot_csv(dst_path, 'Fut_dst', expected_utc=dst_utc),
        load_snapshot_csv(std_path, 'Fut_std', expected_utc=std_utc),
        label)
_SNAPS_TOLERANT = GAP_SOURCE in ('proxy_splice', 'off')
try:
    if EXEC_TIMING == 'open':
        df_fut2130 = build_dst_composite(FUT_US_OPEN_DST_PATH,
                                         FUT_US_OPEN_STD_PATH, 'US-open',
                                         dst_utc=SNAP_UTC_US_OPEN_DST,
                                         std_utc=SNAP_UTC_US_OPEN_STD)
    else:
        # [35] close mode (TSM): DST-correct US-close snapshot
        df_fut2130 = build_dst_composite(FUT_US_CLOSE_DST_PATH,
                                         FUT_US_CLOSE_STD_PATH, 'US-close',
                                         dst_utc=SNAP_UTC_US_CLOSE_DST,
                                         std_utc=SNAP_UTC_US_CLOSE_STD)
    df_fut1330 = load_snapshot_csv(FUT_LOCAL_CLOSE_PATH, 'Fut_1330',
                                   expected_utc=SNAP_UTC_LOCAL_CLOSE)
except Exception as _e:
    # [HKP] an HK run in proxy mode may legitimately have NO capture
    # history yet — the splice below builds the whole gap series from
    # the ETF proxy, uncalibrated, so the backtest can run TODAY and
    # self-calibrate as real snaps accumulate. Any other market/mode:
    # a missing file is still a hard error, exactly as in v31.12.
    if not _SNAPS_TOLERANT:
        raise
    print(f"[HKP] snapshot files unavailable ({_e}) — continuing with an "
          f"EMPTY real-snap set (GAP_SOURCE='{GAP_SOURCE}')")
    df_fut2130 = pd.DataFrame({'Date': pd.Series(dtype=str),
                               'Fut_2130': pd.Series(dtype=float)})
    df_fut1330 = pd.DataFrame({'Date': pd.Series(dtype=str),
                               'Fut_1330': pd.Series(dtype=float)})
# ============================================================
# [HKP] GAP-SOURCE SPLICE (HK only). The real HTI snaps cover only the
# capture window (+ ~140-240d of intraday backfill); the BDH history is
# ~5y. 'proxy_splice' extends the OVERNIGHT INDEX GAP series back with
# an ETF-implied estimate:
#     gap_hat_t = a + b x etf_ret_t
# fitted on the overlap window against the REAL snap gap, candidate
# regressors being the ETF's US-session (open->close) and full
# close-to-close returns — whichever fits better. Synthetic rows are
# built as LEVELS so every downstream consumer (gap ratio [K5], fair
# price, Hedge Idx, fills) works unchanged:
#     Fut_1330 := HSTECH cash close (the 08:00 UTC anchor)
#     Fut_2130 := HSTECH close x (1 + gap_hat)
# Real rows always win on overlap; proxy rows are flagged in
# df['gap_is_proxy'] and counted in every headline so a proxy-heavy
# sample cannot masquerade as measured data. The fit's residual sigma
# doubles as the [HK2] staleness+tracking bound: it contains BOTH the
# ETF-vs-index tracking noise AND the 19:00->20:00/21:00 UTC last-hour
# window the frozen T+1 print cannot see.
# GAP_SOURCE='off': gap forced to ZERO on every BDH date (fair = FX-
# converted ordinary close) — only for cross-sectional/premium-export
# work, never for the hedged backtest.
# ============================================================
# ============================================================
# [HKH] EXTERNAL INDEX-HISTORY LOADER — beats the ETF proxy whenever
# you have it. Bloomberg's intraday window is ~140 days; a downloaded
# HSTECH/HTI history is not limited that way, so this is the honest
# way to get YEARS of the real overnight gap instead of an ETF-implied
# estimate. Rows produced here are REAL index data and are excluded
# from the proxy flag.
# ============================================================
def load_external_index_history(path, tz=None, dt_col=None, px_col=None,
                                tol_min=None):
    """[HKH] Read a long intraday index history and reduce it to the two
    daily prints this book needs: the 16:00-HKT (08:00 UTC) stock close
    and the 03:00-HKT (19:00 UTC) T+1 session close. Returns
    (df_hk_close, df_us_close) with columns ['Date', price].
    Tolerant by design — any delimited text with a timestamp column and
    a price column works; the sniffing is reported so a wrong guess is
    visible rather than silent."""
    _tz = (tz or HIST_IDX_TZ or 'HKT').upper()
    _tol = int(tol_min if tol_min is not None else HIST_IDX_TOL_MIN)
    _raw = None
    for _sep in (None, ',', '\t', ';', r'\s+'):
        try:
            _raw = pd.read_csv(path, sep=_sep, engine='python')
            if _raw.shape[1] >= 2:
                break
        except Exception:
            continue
    if _raw is None or _raw.shape[1] < 2:
        raise RuntimeError(f"[HKH] could not parse {path} as delimited text")
    _cols = list(_raw.columns)
    # --- timestamp column: named, else the first that parses as dates
    _dt = dt_col
    if _dt is None:
        for _c in _cols:
            if str(_c).strip().lower() in ('datetime', 'date_time', 'timestamp',
                                           'time', 'date', 'dt'):
                _dt = _c
                break
    if _dt is None:
        for _c in _cols:
            _try = pd.to_datetime(_raw[_c], errors='coerce')
            if _try.notna().mean() > 0.9:
                _dt = _c
                break
    if _dt is None:
        raise RuntimeError(f"[HKH] no timestamp column found in {path}; "
                           f"set HIST_IDX_DT_COL. Columns: {_cols[:8]}")
    _ts = pd.to_datetime(_raw[_dt], errors='coerce')
    # a separate date + time column pair is common in exported tick files
    if _ts.dt.hour.nunique() <= 1:
        for _c in _cols:
            if _c == _dt:
                continue
            if str(_c).strip().lower() in ('time', 'hhmm', 'hh:mm'):
                _ts2 = pd.to_datetime(_raw[_dt].astype(str) + ' '
                                      + _raw[_c].astype(str), errors='coerce')
                if _ts2.notna().mean() > 0.9:
                    _ts = _ts2
                break
    # --- price column: prefer close/last/price, else the last numeric one
    _px = px_col
    if _px is None:
        for _pref in ('close', 'last', 'px_last', 'price', 'settle', 'value'):
            for _c in _cols:
                if str(_c).strip().lower() == _pref:
                    _px = _c
                    break
            if _px is not None:
                break
    if _px is None:
        _nums = [_c for _c in _cols
                 if _c != _dt and pd.to_numeric(_raw[_c], errors='coerce'
                                                ).notna().mean() > 0.9]
        if not _nums:
            raise RuntimeError(f"[HKH] no numeric price column in {path}; "
                               f"set HIST_IDX_PX_COL. Columns: {_cols[:8]}")
        _px = _nums[-1]
    _d = pd.DataFrame({'ts': _ts,
                       'px': pd.to_numeric(_raw[_px], errors='coerce')}).dropna()
    if not len(_d):
        raise RuntimeError(f"[HKH] {path} parsed but produced no usable rows")
    if _tz == 'HKT':                       # HKT = UTC+8, no DST, ever
        _d['ts'] = _d['ts'] - pd.Timedelta(hours=8)
    _d = _d.sort_values('ts').reset_index(drop=True)
    _d['utc_date'] = _d['ts'].dt.strftime('%Y-%m-%d')
    _d['min_of_day'] = _d['ts'].dt.hour * 60 + _d['ts'].dt.minute
    print(f"[HKH] {path}: {len(_d):,} rows | timestamp col '{_dt}' | price "
          f"col '{_px}' | tz {_tz} | {_d['ts'].min()} .. {_d['ts'].max()} UTC")

    def _snap_at(target_min, name):
        """LAST print at or before target, within tol — i.e. the session's
        closing price as of that moment, which is what a capture job
        snapping at that time would have recorded."""
        _e = _d[(_d['min_of_day'] <= target_min)
                & (_d['min_of_day'] >= target_min - _tol)]
        _g = _e.groupby('utc_date', as_index=False).last()
        return _g[['utc_date', 'px']].rename(
            columns={'utc_date': 'Date', 'px': name})

    _hk = _snap_at(8 * 60, 'Fut_1330')       # 16:00 HKT stock close
    _us = _snap_at(19 * 60, 'Fut_2130')      # 03:00 HKT T+1 close
    print(f"[HKH] built {len(_hk):,} HK-close (08:00 UTC) and {len(_us):,} "
          f"T+1-close (19:00 UTC) prints — the 19:00 print IS what the "
          f"20:00/21:00 capture snaps re-read [HK0.2]")
    if len(_hk) < 100 or len(_us) < 100:
        print(f"[HKH] WARNING: thin extraction — check HIST_IDX_TZ (is the "
              f"file really {_tz}?) and HIST_IDX_TOL_MIN (currently {_tol}min)")
    return _hk, _us
_HIST_DATES = set()
if HIST_IDX_PATH and GAP_SOURCE in ('hist_file', 'proxy_splice'):
    try:
        _h_hk, _h_us = load_external_index_history(
            HIST_IDX_PATH, HIST_IDX_TZ, HIST_IDX_DT_COL, HIST_IDX_PX_COL)
        _have0 = set(df_fut1330['Date']) & set(df_fut2130['Date'])
        _h_both = set(_h_hk['Date']) & set(_h_us['Date'])
        _h_new = _h_both - _have0            # real capture snaps always win
        if _h_new:
            df_fut1330 = pd.concat(
                [df_fut1330, _h_hk[_h_hk['Date'].isin(_h_new)]],
                ignore_index=True).sort_values('Date')
            df_fut2130 = pd.concat(
                [df_fut2130, _h_us[_h_us['Date'].isin(_h_new)]],
                ignore_index=True).sort_values('Date')
            _HIST_DATES = set(_h_new)
        print(f"[HKH] merged {len(_h_new):,} day(s) of REAL index history "
              f"({len(_h_both & _have0):,} already covered by capture snaps)")
    except Exception as _e:
        print(f"[HKH] WARNING: could not use {HIST_IDX_PATH} ({_e}) — falling "
              f"back to the ETF proxy for pre-capture history")
elif GAP_SOURCE == 'hist_file' and not HIST_IDX_PATH:
    print("[HKH] GAP_SOURCE='hist_file' but HIST_IDX_PATH is None — nothing "
          "to load; only real capture snaps will be used")
_PROXY_DATES = set()
_HKP_MIN_OVERLAP = 40
_HKP_FIT = None            # (label, a, b, r2, resid_sigma_bps, n_overlap)
if GAP_SOURCE in ('proxy_splice', 'off') \
        and df_idx_spine is not None and len(df_idx_spine):
    _idx = df_idx_spine.copy()
    _idx['Date'] = _idx['Date'].astype(str)
    _idx = _idx.sort_values('Date').reset_index(drop=True)
    if GAP_SOURCE == 'off':
        _syn = _idx.rename(columns={'IDX_close': 'Fut_1330'}).copy()
        _syn['Fut_2130'] = _syn['Fut_1330']
        _have = set(df_fut1330['Date']) & set(df_fut2130['Date'])
        _syn = _syn[~_syn['Date'].isin(_have)]
        _PROXY_DATES = set(_syn['Date'])
        df_fut1330 = pd.concat([df_fut1330, _syn[['Date', 'Fut_1330']]],
                               ignore_index=True).sort_values('Date')
        df_fut2130 = pd.concat([df_fut2130, _syn[['Date', 'Fut_2130']]],
                               ignore_index=True).sort_values('Date')
        print(f"[HKP] GAP_SOURCE='off': {len(_syn)} zero-gap rows appended "
              f"— fair carries NO overnight index information")
    elif df_etf_gap is not None and len(df_etf_gap):
        _e = df_etf_gap.copy()
        _e['Date'] = _e['Date'].astype(str)
        _e = _e.sort_values('Date').reset_index(drop=True)
        _e['etf_oc'] = _e['ETF_close'] / _e['ETF_open'] - 1.0
        _e['etf_cc'] = _e['ETF_close'] / _e['ETF_close'].shift(1) - 1.0
        _real = pd.merge(df_fut1330[['Date', 'Fut_1330']],
                         df_fut2130[['Date', 'Fut_2130']],
                         on='Date', how='inner')
        _real['gap_real'] = _real['Fut_2130'] / _real['Fut_1330'] - 1.0
        _ov = pd.merge(_real[['Date', 'gap_real']],
                       _e[['Date', 'etf_oc', 'etf_cc']], on='Date',
                       how='inner').dropna()
        _a_fit, _b_fit, _cand_lbl, _r2_fit, _sig_fit = 0.0, 1.0, 'etf_oc', np.nan, np.nan
        if len(_ov) >= _HKP_MIN_OVERLAP:
            _best = None
            for _cand in ('etf_oc', 'etf_cc'):
                _x = _ov[_cand].values
                _y = _ov['gap_real'].values
                _m = np.isfinite(_x) & np.isfinite(_y)
                if _m.sum() < _HKP_MIN_OVERLAP:
                    continue
                _b = (np.cov(_x[_m], _y[_m])[0, 1] / np.var(_x[_m])
                      if np.var(_x[_m]) > 0 else np.nan)
                _a = float(np.mean(_y[_m]) - _b * np.mean(_x[_m]))
                _res = _y[_m] - (_a + _b * _x[_m])
                _r2 = 1.0 - np.var(_res) / np.var(_y[_m]) if np.var(_y[_m]) > 0 else 0.0
                if np.isfinite(_b) and (_best is None or _r2 > _best[3]):
                    _best = (_cand, _a, float(_b), float(_r2),
                             float(np.std(_res) * 1e4), int(_m.sum()))
            if _best is not None:
                _cand_lbl, _a_fit, _b_fit, _r2_fit, _sig_fit, _n_ov = _best
                _HKP_FIT = _best
                print(f"[HKP] proxy fit on {_n_ov} overlap rows: gap = "
                      f"{_a_fit*1e4:+.1f}bps + {_b_fit:.2f} x {_cand_lbl} | "
                      f"R2 {_r2_fit:.2f} | residual sigma {_sig_fit:.0f} bps")
                print(f"[HKP][HK2] that residual sigma IS the proxy's "
                      f"tracking + last-hour staleness bound — carry it "
                      f"into the entry-floor arithmetic alongside [HK-H2]")
        else:
            print(f"[HKP] WARNING: only {len(_ov)} overlap rows (<"
                  f"{_HKP_MIN_OVERLAP}) — proxy mapping UNCALIBRATED "
                  f"(a=0, b=1 on {_cand_lbl}). Treat every proxy-row "
                  f"statistic as provisional until snaps accumulate.")
        _syn = pd.merge(_idx, _e[['Date', _cand_lbl]], on='Date', how='inner')
        _syn = _syn[np.isfinite(_syn[_cand_lbl])]
        _have = set(df_fut1330['Date']) & set(df_fut2130['Date'])
        _syn = _syn[~_syn['Date'].isin(_have)]
        _syn['Fut_1330'] = _syn['IDX_close']
        _syn['Fut_2130'] = _syn['IDX_close'] * (1.0 + _a_fit
                                                + _b_fit * _syn[_cand_lbl])
        _PROXY_DATES = set(_syn['Date'])
        df_fut1330 = pd.concat([df_fut1330, _syn[['Date', 'Fut_1330']]],
                               ignore_index=True).sort_values('Date')
        df_fut2130 = pd.concat([df_fut2130, _syn[['Date', 'Fut_2130']]],
                               ignore_index=True).sort_values('Date')
        _n_cap = len(_have) - len(_HIST_DATES & _have)
        kv_table('[HKP] WHERE THE OVERNIGHT INDEX GAP COMES FROM',
                 [('capture snaps (best)', f"{_n_cap:,} rows",
                   'the real 08:00 / 20:00-21:00 UTC HTI prints'),
                  ('external history [HKH]', f"{len(_HIST_DATES):,} rows",
                   'real index data from HIST_IDX_PATH — beats any proxy, '
                   'and is not limited to Bloomberg\'s ~140 intraday days'),
                  ('ETF proxy (last resort)', f"{len(_syn):,} rows",
                   f"{df_etf_gap.attrs.get('ticker', '?')} via {_cand_lbl}; "
                   f"flagged in gap_is_proxy and excluded from any headline "
                   f"that claims measured data")],
                 note='Tiers, not alternatives: a date is filled by the best '
                      'source available for it. Proxy rows carry the fit '
                      'residual as extra noise — see [HK2].')
elif GAP_SOURCE in ('proxy_splice', 'off'):
    print("[HKP] WARNING: no index level series — cannot build proxy rows; "
          "running on real snaps only")
# [HKT] the HTI print at the HK OPEN (09:30 HKT = 01:30 UTC) — needed
# only by HEDGE_TIMING mode 2 ('index_then_stock': that is the moment the
# futures are unwound and the stock goes on). Missing file = mode 2 is
# reported as unavailable; everything else runs.
df_fut0130 = None
try:
    df_fut0130 = load_snapshot_csv(FUT_HK_OPEN_PATH, 'Fut_0130',
                                   expected_utc=SNAP_UTC_HK_OPEN)
    print(f"[HKT] HK-open futures snap: {len(df_fut0130)} rows")
except Exception as _e:
    print(f"[HKT] no HK-open futures snap ({_e}) — hedge-timing mode "
          f"'index_then_stock' will be reported as unavailable; add "
          f"{FUT_HK_OPEN_PATH} to the capture job to enable it")
    df_fut0130 = None
# [P2] pre-close (15:45 ET) snapshots — loaded only when enabled; the
# exact same DST-composite + [H1] timestamp validation as the close
# files, expected minutes 19:45 (summer) / 20:45 (winter).
df_fut_pre = None
df_adr_pre = None
if PRECLOSE_ENABLED:
    try:
        df_fut_pre = build_dst_composite(PRECLOSE_FUT_DST_PATH,
                                         PRECLOSE_FUT_STD_PATH, 'pre-close SSF',
                                         dst_utc=SNAP_UTC_PRECLOSE_DST,
                                         std_utc=SNAP_UTC_PRECLOSE_STD
                                         ).rename(columns={'Fut_2130': 'Fut_pre'})
        df_adr_pre = build_dst_composite(PRECLOSE_ADR_DST_PATH,
                                         PRECLOSE_ADR_STD_PATH, 'pre-close ADR',
                                         dst_utc=SNAP_UTC_PRECLOSE_DST,
                                         std_utc=SNAP_UTC_PRECLOSE_STD
                                         ).rename(columns={'Fut_2130': 'ADR_pre'})
        print(f"[P2] pre-close snapshots loaded: {HEDGE_LBL} {len(df_fut_pre)} rows, "
              f"ADR {len(df_adr_pre)} rows")
    except Exception as _e:
        print(f"[P2] WARNING: pre-close snapshot load failed ({_e}) — the "
              f"15:45-signal variant will be skipped. Expected files:")
        print(f"     {PRECLOSE_FUT_DST_PATH} / {PRECLOSE_FUT_STD_PATH}")
        print(f"     {PRECLOSE_ADR_DST_PATH} / {PRECLOSE_ADR_STD_PATH}")
        df_fut_pre = df_adr_pre = None
# [17] explicit cross-file date alignment report
_only_open = set(df_fut2130['Date']) - set(df_fut1330['Date'])
_only_close = set(df_fut1330['Date']) - set(df_fut2130['Date'])
if _only_open:
    _wknd_only = [d for d in _only_open
                  if pd.Timestamp(d).dayofweek >= 5]
    _wk_note = (f" ({len(_wknd_only)} are Sat/Sun — weekend captures with "
                f"frozen prices, correctly killed by the trading-day merge)"
                if _wknd_only else "")
    print(f"[QC] {len(_only_open)} dates only in the US-session snapshot files{_wk_note} "
          f"(dropped by the inner merge), e.g. {sorted(_only_open)[:3]}")
if _only_close:
    print(f"[QC] {len(_only_close)} dates only in the {LOCAL_CLOSE_LBL} file "
          f"(dropped by the inner merge), e.g. {sorted(_only_close)[:3]}")
# ============================================================
# MERGE ALL DATA (inner joins ensure date alignment)
# ============================================================
df_TSM_open['Date'] = df_TSM_open['Date'].astype(str)
df_TSM_close['Date'] = df_TSM_close['Date'].astype(str)
df_twd['Date'] = df_twd['Date'].astype(str)
df_2330['Date'] = df_2330['Date'].astype(str)
df = pd.merge(df_TSM_open, df_TSM_close, on='Date', how='inner')
df = pd.merge(df, df_twd, on='Date', how='inner')
df = pd.merge(df, df_2330, on='Date', how='inner')
df = pd.merge(df, df_fut2130, on='Date', how='inner')
for _leg in ('hedge', 'adr'):            # [J3] merge all TR candidates
    for _fi, _d in _tr_pulls[_leg].items():
        _dd = _d.copy(); _dd['Date'] = _dd['Date'].astype(str)
        _cols = ['Date'] + [c for c in _dd.columns if c != 'Date']
        df = pd.merge(df, _dd[_cols], on='Date', how='left')
for _trdf in (df_tr_hedge, df_tr_adr):   # [26] LEFT merges — TR may be sparse
    if len(_trdf):
        _trdf['Date'] = _trdf['Date'].astype(str)
        df = pd.merge(df, _trdf, on='Date', how='left')
for _c in ('TR_hedge', 'TR_adr', 'TRidx_hedge', 'TRidx_adr'):
    if _c not in df.columns:
        df[_c] = np.nan
df = pd.merge(df, df_fut1330, on='Date', how='inner')
# [HK0] LEFT merges (a sparse series must not shrink the aligned
# calendar): the index level (hedge spine + beta prior), the ETF proxy
# prints, the ordinary open, and the proxy-row flag [HKP].
for _hkdf in (df_idx_spine, df_etf_gap, df_ord_open):
    if _hkdf is not None and len(_hkdf):
        _hkd = _hkdf.copy()
        _hkd['Date'] = _hkd['Date'].astype(str)
        df = pd.merge(df, _hkd, on='Date', how='left')
if df_fut0130 is not None and len(df_fut0130):
    _f0 = df_fut0130.copy()
    _f0['Date'] = _f0['Date'].astype(str)
    df = pd.merge(df, _f0[['Date', 'Fut_0130']], on='Date', how='left')
df['gap_is_proxy'] = df['Date'].isin(_PROXY_DATES) \
    if _PROXY_DATES else False
if PRECLOSE_ENABLED and df_fut_pre is not None and df_adr_pre is not None:
    df = pd.merge(df, df_fut_pre, on='Date', how='left')   # [P2]
    df = pd.merge(df, df_adr_pre, on='Date', how='left')
df = df.sort_values('Date').reset_index(drop=True)
df['Date_dt'] = pd.to_datetime(df['Date'])
df['is_dst'] = df['Date_dt'].map(is_us_dst)
if len(df) < 250:   # [29]
    raise RuntimeError(f'Merged dataset only {len(df)} rows — check '
                       f'tickers, entitlements and snapshot file paths')
# ------------------------------------------------------------
# STALE-DATA FILTERS  (both are needed — do not remove)
# ------------------------------------------------------------
# (a) TW-holiday stale rows: 2330 close AND the 13:30 SSF both
#     exactly unchanged vs the prior row.
stale_hk = (
    (df['2330 TT (Close)'] == df['2330 TT (Close)'].shift(1)) &
    (df['Fut_1330'] == df['Fut_1330'].shift(1))
)
# (b)[H1] US-open print EXACTLY equal to the TW-close print. The v18
#     rule dropped these outright (79 rows in the live run) — but the
#     user spot-checked days and found some are REAL: the night price
#     simply had not moved. The equality heuristic cannot tell a
#     failed capture from a quiet session; the capture TIMESTAMP can.
#     So: when the US-open files' timestamps were validated by the
#     loader (SNAPSHOT_TS_VALIDATED), the genuinely stale rows have
#     ALREADY been dropped there, and equality rows that survived are
#     KEPT — reported below for spot-checking (equal price at a valid
#     time can still be an untraded session echoing the day close;
#     verify a few on QR). Only when timestamps were unavailable does
#     the old equality drop apply.
eq_2130 = np.isclose(df['Fut_2130'], df['Fut_1330'], rtol=0.0, atol=1e-9)
_ts_open_ok = (SNAPSHOT_TS_VALIDATED.get(FUT_US_OPEN_DST_PATH, False)
               and SNAPSHOT_TS_VALIDATED.get(FUT_US_OPEN_STD_PATH, False)) \
    if EXEC_TIMING == 'open' else \
    (SNAPSHOT_TS_VALIDATED.get(FUT_US_CLOSE_DST_PATH, False)
     and SNAPSHOT_TS_VALIDATED.get(FUT_US_CLOSE_STD_PATH, False))
n_hk = int(stale_hk.sum())
n_eq = int((eq_2130 & ~stale_hk).sum())
if n_hk > 0:
    print(f"[QC] Dropping {n_hk} stale TW-holiday rows (repeated TW prices)")
n_stale_dropped = 0 if _ts_open_ok else n_eq   # [K1] for the summary print
if _ts_open_ok:
    stale_2130 = pd.Series(False, index=df.index)
    if n_eq > 0:
        print(f"[QC][H1] {n_eq} rows where Fut_2130 == Fut_1330 exactly BUT the "
              f"capture timestamps are valid — KEPT as real (quiet night "
              f"session). Spot-check a few on QR:")
        print("     " + ", ".join(df.loc[eq_2130 & ~stale_hk, 'Date'].tolist()[:12])
              + (" ..." if n_eq > 12 else ""))
else:
    stale_2130 = eq_2130
    if n_eq > 0:
        print(f"[QC] Dropping {n_eq} stale US-open snapshot rows "
              f"(Fut_2130 == Fut_1330 exactly; no timestamps to verify). Dates:")
        print("     " + ", ".join(df.loc[eq_2130 & ~stale_hk, 'Date'].tolist()))
df = df[~(stale_hk | stale_2130)].reset_index(drop=True)
# ============================================================
# [C4] DATA-INTEGRITY AUDIT — deep checks on every input series
# ============================================================
# Runs ALWAYS. Each check prints only when something is suspicious, so
# a clean dataset produces a short "all clear" line. These are checks,
# not silent fixes: nothing is dropped here — flagged dates should be
# verified manually on the terminal before you trust the backtest.
banner("[C4] DATA-INTEGRITY AUDIT")
_audit_flags = 0
_audit_msgs = []   # [I4] collected for the consolidated list at the end
_QC_MOVES = []          # [Y4] rows for the DATA CLEANSING html table
_INPUT_ROWS = []        # [Y27] one 'INPUT DIAGNOSTICS' table at the end
 
def _inp(check, reading, note='', level=None):
    """[Y27] Collect a one-line input diagnostic instead of printing a
    paragraph. level in None/'ok'/'warn'/'bad' adds a badge."""
    _INPUT_ROWS.append((check,
                        (_badge(reading, level) + ' ' if level else '')
                        + ('' if level else reading), note))
    if not (HTML_OUTPUT and _in_jupyter()):
        print(f"  {check:<34} {reading}" + (f"   {note}" if note else ''))
 
def _audit(msg):
    global _audit_flags
    _audit_flags += 1
    _audit_msgs.append(msg.split(' — ')[0].split(':')[0] + ' — ' +
                       (msg.split(' — ')[1].split(':')[0]
                        if ' — ' in msg else 'see detail above'))
    # [Y23] in HTML mode the flags land in the DATA INTEGRITY table and the
    # outliers in the DATA CLEANSING table — no inline chatter in between.
    if not (HTML_OUTPUT and _in_jupyter()):
        print(f"  [AUDIT] {msg}")
# (1) calendar sanity: strictly increasing, no duplicates, no weekends
if not df['Date_dt'].is_monotonic_increasing:
    _audit("dates are NOT strictly increasing after the merge — sort bug")
if df['Date_dt'].duplicated().any():
    _audit(f"{int(df['Date_dt'].duplicated().sum())} duplicate dates survived the merge")
_wknd = df['Date_dt'].dt.dayofweek >= 5
if _wknd.any():
    _audit(f"{int(_wknd.sum())} WEEKEND rows (bad timestamps?): "
           f"{df.loc[_wknd, 'Date'].tolist()[:5]}")
# (2) per-series: zeros/negatives, extreme day-over-day moves, stale runs
_series_checks = {
    'TSM US (Open)': 0.15, 'TSM US (Close)': 0.15,
    '2330 TT (Close)': 0.105,        # TW 10% daily limit
    'Fut_1330': 0.105, 'Fut_2130': 0.15,
    'TWD (Last)': 0.02,              # >2%/day in USDTWD is a red flag
}
for _col, _lim in _series_checks.items():
    _v = pd.to_numeric(df[_col], errors='coerce')
    _npos = int(((_v <= 0) | ~np.isfinite(_v)).sum())
    if _npos:
        _audit(f"{_col}: {_npos} zero/negative/non-finite values")
    _mv_signed = _v.pct_change()          # [K2] keep the SIGN for display
    _mv = _mv_signed.abs()
    _big = _mv > _lim
    if _big.any():
        # [L1] pct_change is vs the previous SURVIVING row, which can be
        # days back (TW holidays drop rows via the inner merge — e.g.
        # 2025-04-07 vs 2025-04-02 across the Qingming break read as a
        # -19.4% "day-over-day"). Print the prev date + calendar gap so
        # a multi-day span is self-evident and not mistaken for a bad
        # print.
        _prev_date = df['Date'].shift(1)
        _gap_cd_s = (df['Date_dt'] - df['Date_dt'].shift(1)).dt.days
        _worst = df.loc[_big, ['Date']].assign(
            move=_mv_signed[_big] * 100,
            prev=_prev_date[_big],
            gapcd=_gap_cd_s[_big])
        _audit(f"{_col}: {int(_big.sum())} day-over-day moves > {_lim*100:.1f}% "
               f"— verify on the terminal:")
        _worst['absmove'] = _worst['move'].abs()
        for _, _r in _worst.nlargest(5, 'absmove').iterrows():   # [Y4] also tabled below
            _QC_MOVES.append({'series': _col, 'date': _r['Date'],
                              'move %': _r['move'], 'vs prev': _r['prev'],
                              'gap cd': (int(_r['gapcd'])
                                         if np.isfinite(_r['gapcd']) else 0),
                              'limit %': _lim * 100})
        if not (HTML_OUTPUT and _in_jupyter()):     # [Y23] table instead
            for _, _r in _worst.nlargest(5, 'absmove').iterrows():
                _g = int(_r['gapcd']) if np.isfinite(_r['gapcd']) else 0
                _gap_note = f" vs {_r['prev']} ({_g}cd gap - holiday rows dropped)" \
                    if _g > 3 else f" vs {_r['prev']}"
                print(f"           {_r['Date']}  {_r['move']:+.2f}%{_gap_note}")
    # stale runs: same value 4+ rows in a row (FX fixings and captures
    # CAN legitimately repeat 2-3 days; 4+ smells like a dead feed)
    _same = (_v == _v.shift(1))
    _run = _same.groupby((~_same).cumsum()).cumsum()
    if (_run >= 3).any():
        _d0 = df.loc[_run >= 3, 'Date'].tolist()
        _audit(f"{_col}: value unchanged 4+ consecutive rows ending at "
               f"{_d0[:4]}{'...' if len(_d0) > 4 else ''} — possible stale feed")
# (3) FX plausibility band (USDTWD has lived ~27-34 for two decades)
_fx = pd.to_numeric(df['TWD (Last)'], errors='coerce')
_fx_bad = (_fx < 25) | (_fx > 36)
if _fx_bad.any():
    _audit(f"TWD (Last): {int(_fx_bad.sum())} values outside 25-36 — wrong "
           f"quote convention or corrupt data: "
           f"{df.loc[_fx_bad, ['Date', 'TWD (Last)']].head(5).to_string(index=False)}")
# (4)[G5] ADR parity: TSM_close x FX / (2330_close x 5). The v17 rule
#     flagged |parity| > 8% absolute and fired on 482/484 rows — WRONG
#     TEST: the TSM ADR trades at a PERSISTENT structural premium
#     (~+19% mean in the live sample; real, driven by index demand
#     and conversion frictions, and the very thing this strategy
#     mean-reverts). What indicates a DATA ERROR is a single day
#     JUMPING away from the prevailing premium, so v18 flags
#     deviations from the 60d rolling MEDIAN premium instead.
# [K3] REFINED (the v21 60d-median test flagged 111 rows — nearly all
# were the premium's H1-2024 structural RE-RATING trending away from a
# lagging median, not bad prints; user confirmed benign). A data ERROR
# has a distinct signature: the premium JUMPS on one day and REVERTS
# the next (spike-and-revert). Only that pattern is flagged now; the
# level/trend stats are printed as information.
_parity = (df['TSM US (Close)'] * _fx) / (df['2330 TT (Close)'] * ADR_RATIO) - 1.0
_QC_SUMMARY = []          # [Y26] one compact table instead of narration
_QC_SUMMARY.append(('ADR parity (premium)',
                    f"mean {_parity.mean()*100:+.2f}%, sd "
                    f"{_parity.std()*100:.2f}%, range "
                    f"{_parity.min()*100:+.2f}% to {_parity.max()*100:+.2f}%",
                    'a persistent premium is REAL, not an error'))
if not (HTML_OUTPUT and _in_jupyter()):
    print(f"  ADR parity: mean {_parity.mean()*100:+.2f}% | sd "
          f"{_parity.std()*100:.2f}% | range {_parity.min()*100:+.2f}% to "
          f"{_parity.max()*100:+.2f}%")
_pj = _parity.diff()                      # day-over-day premium change
_pj_next = _pj.shift(-1)
_spike = ((_pj > 0.04) & (_pj_next < -0.04)) | ((_pj < -0.04) & (_pj_next > 0.04))
if _spike.any():
    _audit(f"{int(_spike.sum())} one-day premium SPIKE-AND-REVERT rows "
           f"(jump >4% then reverse >4% next day) — the classic bad-print "
           f"signature, check these:")
    _show = df.loc[_spike, ['Date', 'TSM US (Close)', '2330 TT (Close)',
                            'TWD (Last)']].copy()
    _show['premium%'] = (_parity[_spike] * 100).round(2)
    _show['jump%'] = (_pj[_spike] * 100).round(2)
    if HTML_OUTPUT and _in_jupyter():
        show_html_table(_show.head(8).set_index('Date'),
                        title='spike-and-revert candidates (bad-print '
                              'signature)',
                        fmt={'premium%': '{:+.2f}', 'jump%': '{:+.2f}'})
    else:
        print(_show.head(8).to_string(index=False))
# (5) [HKS] BASIS AT THE SAME TIMESTAMP. The Taiwan book compares the
#     same-name SSF against the ordinary, because they track the same
#     underlying and a front-month basis is inside ~+/-3%. An INDEX
#     future must be compared against ITS OWN underlying — the cash
#     INDEX — not against the single stock: HTI vs 9988 is a level
#     ratio of two unrelated scales (thousands of index points vs a
#     ~HK$80 share) and would flag literally every row.
if 'IDX_close' in df.columns and df['IDX_close'].notna().mean() > 0.5:
    _basis_ref, _basis_lbl = df['IDX_close'].ffill(), f'cash {HEDGE_SPINE_TICKER}'
else:
    _basis_ref, _basis_lbl = df['Fut_1330'], 'itself (no index series — check pulled)'
_basis = df['Fut_1330'] / _basis_ref - 1.0
_bas_bad = _basis.abs() > 0.03
_QC_SUMMARY.append((f'{HEDGE_LBL} {LOCAL_CLOSE_LBL} vs {_basis_lbl}',
                    f"mean {_basis.mean()*100:+.2f}%, max |.| "
                    f"{_basis.abs().max()*100:.2f}%",
                    'the futures basis to its own index; should sit inside '
                    '+/-3% (carry minus expected dividends)'))
if not (HTML_OUTPUT and _in_jupyter()):
    print(f"  {HEDGE_LBL} basis vs {_basis_lbl}: mean {_basis.mean()*100:+.2f}% "
          f"| max |.| {_basis.abs().max()*100:.2f}%")
if _bas_bad.any():
    _audit(f"{int(_bas_bad.sum())} rows with |{HEDGE_LBL} basis| > 3% vs the "
           f"cash index — wrong contract in the snapshot file? Dates:")
    if not (HTML_OUTPUT and _in_jupyter()):
        print(df.loc[_bas_bad, ['Date', 'IDX_close', 'Fut_1330']]
              .head(8).to_string(index=False)
              if 'IDX_close' in df.columns else
              df.loc[_bas_bad, ['Date', 'Fut_1330']].head(8).to_string(index=False))
# (6) coverage per year — spot silent holes in the capture jobs
_per_yr = df['Date_dt'].dt.year.value_counts().sort_index()
_QC_SUMMARY.append(('coverage',
                    ", ".join(f"{y}: {c}" for y, c in _per_yr.items()),
                    f"{len(df)} aligned rows, "
                    f"{df['Date_dt'].iloc[0].date()} to "
                    f"{df['Date_dt'].iloc[-1].date()}"))
if not (HTML_OUTPUT and _in_jupyter()):
    print("  Rows per year: " + ", ".join(f"{y}:{c}"
                                          for y, c in _per_yr.items()))
# [Y1] BOTH ends can be partial: the sample starts mid-year as well as
# ending mid-year, so a year is only "full" if the data spans all of it.
_y_first, _y_last = df['Date_dt'].iloc[0], df['Date_dt'].iloc[-1]
_full_years = [_y for _y in _per_yr.index
               if _y_first <= pd.Timestamp(year=int(_y), month=1, day=10)
               and _y_last >= pd.Timestamp(year=int(_y), month=12, day=20)]
_thin = [int(_y) for _y in _full_years if _per_yr.loc[_y] < 180]
if _thin:
    _audit(f"FULL year(s) {_thin} have <180 aligned rows — a capture job "
           f"was down for months; the backtest silently skips that period")
else:
    _part = [int(_y) for _y in _per_yr.index if _y not in _full_years]
    if _part and not (HTML_OUTPUT and _in_jupyter()):
        print(f"  ({_part} partial by design — sample runs "
              f"{_y_first.date()} to {_y_last.date()}, not a capture gap)")
# ============================================================
# [Y26] ONE CONCISE DATA-CLEANSING BLOCK. Everything above collected into
# (1) a health summary, (2) the flags worth a terminal check, (3) only the
# rows that need CHECKING — a move measured across a multi-day holiday gap
# is not a day-over-day move, so those are folded into a single count line
# instead of a table of expected artefacts.
_qc_check, _qc_expected = [], 0
if _QC_MOVES:
    _qc_all = pd.DataFrame(_QC_MOVES)
    _exp_mask = _qc_all['gap cd'] > 3
    _qc_expected = int(_exp_mask.sum())
    _qc_check = _qc_all[~_exp_mask].sort_values(
        'move %', key=lambda s_: s_.abs(), ascending=False)
_QC_SUMMARY.insert(0, ('integrity flags',
                       (f"{_audit_flags} flag(s)" if _audit_flags
                        else 'none — all checks passed'),
                       ('verify on the terminal before trusting PnL'
                        if _audit_flags else '')))
_QC_SUMMARY.insert(1, ('outlier moves',
                       f"{len(_qc_check)} to check, {_qc_expected} explained "
                       f"by holiday gaps",
                       'holiday rows are dropped by the inner merge, so '
                       'pct_change spans the break'))
if HTML_OUTPUT and _in_jupyter():
    show_html_table(
        pd.DataFrame(_QC_SUMMARY,
                     columns=['check', 'reading', 'note']).set_index('check'),
        title='DATA CLEANSING — summary', fmt='{}')
    if _audit_flags:
        show_html_table(
            pd.DataFrame({'flag': _audit_msgs},
                         index=[f"#{_k}" for _k in
                                range(1, len(_audit_msgs) + 1)]),
            title=f"flags to verify ({_audit_flags})", fmt='{}',
            note="Flags naming the SAME date are ONE event: when every "
                 "series jumps together across a holiday gap that is a "
                 "market move, not a bad print.")
    if len(_qc_check):
        show_html_table(
            _qc_check[['series', 'date', 'move %', 'vs prev',
                       'limit %']].set_index('date'),
            title='rows to check on the terminal',
            fmt={'move %': '{:+.2f}', 'limit %': '{:.1f}'})
else:
    print("  " + "-" * 66)
    for _k, _v, _n in _QC_SUMMARY:
        print(f"  {_k:<28} {_v}")
    for _k, _m in enumerate(_audit_msgs, 1):
        print(f"    {_k}. {_m}")
# ============================================================
# CONTRACT ROLL HANDLING — NEXT-MONTH FILES, MONTH-START ROLL [I3][J1]
# ============================================================
# USER-CONFIRMED (v21): the files quote the rolling NEXT-month
# contract (Feb -> March future, April -> May future), switching at
# the month start — the original v13 convention, restored. Handling:
#   - two rows are same-contract iff contract_id() matches (under
#     this rule: same calendar month = same file contract),
#   - a hold crossing the month boundary does NOT roll the real
#     position (the held M+1 contract is weeks from expiry), so the
#     boundary is a MARKING-SOURCE switch only: raw prices while the
#     file still quotes the entry contract, TR spine after. No roll
#     cost is charged (n_rolls = 0 under this rule),
#   - the day-over-day SSF return (cost-model vol input only) is
#     winsorized at 5 sigma to cap the file-roll jump,
#   - the same-day gap (Fut_2130 / Fut_1330) is same-contract by
#     construction on EVERY row (both prints are the same next-month
#     contract; it never expires while in the file).
df['ret_fut_daily'] = np.log(df['Fut_1330'] / df['Fut_1330'].shift(1))
# [28] winsorize with TRAILING vol only (the old full-sample std was a
# small look-ahead into the cost model's k input)
_s = df['ret_fut_daily'].rolling(120, min_periods=20).std().shift(1)
df['ret_fut_daily'] = df['ret_fut_daily'].clip(lower=-5 * _s, upper=5 * _s)
# ============================================================
# BETA — FIXED AT 1.0 (hedge is TSMC's OWN single stock future)
# ============================================================
# No regression needed: the future references the same underlying, so
# the correct hedge ratio is 1 share-equivalent per share. Any residual
# is futures basis + FX, not beta.
df['beta'] = 1.0
# ============================================================
# FAIR PRICE CALCULATION  (proportional return, NOT point-add)
# ============================================================
# (ADR_RATIO defined in CONFIG: 1 TSM ADR = 5 shares of 2330 TT)
df['fut_gap_ret'] = df['Fut_2130'] / df['Fut_1330'] - 1.0
# ============================================================
# [K5] CONTRACT-MISMATCH DETECT + REPAIR — must run BEFORE the fair
# price is built, otherwise the corrupted gap is already baked into
# the signal. Mechanism being defended against: in close mode the
# 2130 print is captured at 20:00/21:00 UTC = 04:00/05:00 TAIPEI THE
# NEXT DAY, so a "front month" capture job can resolve to the NEXT
# contract one session earlier than the 13:30 job. The ratio is then a
# CALENDAR SPREAD, not an overnight move — and because that same wrong
# price becomes entry_fut_raw, the next day's "recovery" books a large
# FAKE hedge profit with the signal pointing whichever way produces
# it. The bias is toward fake gains in BOTH directions.
# ============================================================
# [K7] EXACT check when the capture job supplies contract labels.
# HOW TO GET IT: have the capture job write the resolved contract's
# ticker (or its expiry, e.g. 'CDF Q6' / '202608') as a 5th CSV column.
# Then a mismatch is certain, not inferred, and the ROOT FIX is easy:
# pin BOTH jobs to the contract that is front-month as of the TAIPEI
# TRADING DATE of the 13:30 snap, i.e. for the 20:00/21:00 UTC capture
# pass the PREVIOUS Taipei calendar date to the front-month resolver.
_c1 = 'Fut_1330_contract'
_c2 = 'Fut_2130_contract'
if _c1 in df.columns and _c2 in df.columns:
    _mm = (df[_c1].astype(str).str.strip() != df[_c2].astype(str).str.strip())
    print(f"[K7] contract labels present: {int(_mm.sum())} of {len(df)} rows "
          f"have DIFFERENT contracts in the two files "
          f"({_mm.mean()*100:.1f}%) — these are exact, not inferred")
    if _mm.any():
        for _i in df.index[_mm][:8]:
            print(f"       {df['Date'].iloc[_i]}  1330={df[_c1].iloc[_i]} "
                  f"vs 2130={df[_c2].iloc[_i]}")
else:
    _mm = pd.Series(False, index=df.index)
    _inp('contract labels [K7]', 'not in the files',
         f'both jobs resolve the front month by the same {LOCAL_LBL} date, so '
         'same-date rows are the same contract [Y22]; a 5th ticker column '
         'would make that a check rather than an assumption')
df['fut_gap_raw'] = df['fut_gap_ret']      # pre-repair, for reporting
df['Fut_2130_raw'] = df['Fut_2130']
# [Y22] HEURISTIC GAP FLAGGING REMOVED — USER-VERIFIED. Both capture jobs
# resolve the front month by the SAME Taipei trading date, so a same-date
# 13:30/US-close pair is always the SAME contract; the size-based and
# sigma-based gap heuristics were flagging REAL overnight moves (the exact
# rows the strategy exists to trade) and, worse, the 'repair' was
# overwriting REAL US-close fills with the stale 13:30 print. Only the
# [K7] EXACT contract-label test remains: with labels present a mismatch
# is a fact, not an inference; without labels nothing is flagged.
_suspect = _mm.copy()
df['gap_suspect'] = _suspect
if _suspect.any() and SUSPECT_GAP_POLICY == 'repair':
    df.loc[_suspect, 'Fut_2130'] = df.loc[_suspect, 'Fut_1330']
    df['fut_gap_ret'] = df['Fut_2130'] / df['Fut_1330'] - 1.0
    sc('WARN' if int(_suspect.sum()) else 'PASS', 'suspect gaps repaired',
       f"{int(_suspect.sum())} row(s)")
    print(f"[K5] policy=repair -> {int(_suspect.sum())} row(s) with an "
          f"EXACT [K7] contract-label mismatch: Fut_2130 set to Fut_1330 "
          f"before the fair is built; entries blocked on those rows")
elif _suspect.any() and SUSPECT_GAP_POLICY == 'drop_row':
    df = df[~_suspect].reset_index(drop=True)
    print(f"[K5] policy=drop_row -> {int(_suspect.sum())} row(s) removed")
elif _suspect.any():
    print(f"[K5] policy={SUSPECT_GAP_POLICY} -> {int(_suspect.sum())} suspect "
          f"row(s) NOT repaired; the fake gap still drives the fair price")
# ============================================================
# [K6] SYSTEMATIC MONTH-END BIAS — catches a SMALL mismatch that never
# trips the threshold above. If the two capture jobs disagree about the
# contract on month-end rows, those rows carry a systematic offset of
# roughly one calendar spread (carry +/- dividend). For a high-priced
# name that offset can be only 0.2-1.0% of price — invisible to any
# magnitude test, yet still a monthly fake gap of a few thousand
# dollars. The fingerprint is a MEAN SHIFT, not an outlier.
# ============================================================
_perm = df['Date_dt'].dt.to_period('M')
_me_idx = df.groupby(_perm).tail(1).index      # last row of each month
_ms_idx = df.groupby(_perm).head(1).index      # first row of each month
for _lbl, _idx in (('last row of month', _me_idx), ('first row of month', _ms_idx)):
    _sel = df.index.isin(_idx)
    _a = df.loc[_sel, 'fut_gap_raw'].dropna()
    _b = df.loc[~_sel, 'fut_gap_raw'].dropna()
    if len(_a) >= 5 and len(_b) >= 20 and _b.std() > 0:
        _t = (_a.mean() - _b.mean()) / (_b.std() / np.sqrt(len(_a)))
        _msg = ('<- SYSTEMATIC: likely a roll misalignment between the two '
                'capture files' if abs(_t) > 2.5 else '(no material bias)')
        if _lbl.startswith('last'):
            sc('FAIL' if abs(_t) > 2.5 else 'PASS', 'month-end roll alignment',
               f"t={_t:+.1f} ({'systematic mismatch' if abs(_t) > 2.5 else 'aligned'})")
        _inp(f"month-boundary bias [K6], {_lbl}",
             f"{_a.mean()*100:+.3f}% vs {_b.mean()*100:+.3f}% elsewhere, "
             f"t={_t:+.1f}",
             'systematic — check the capture jobs' if abs(_t) > 2.5 else '',
             level=('warn' if abs(_t) > 2.5 else 'ok'))
df['contract_id'] = df['Date_dt'].map(contract_id)          # [I3]
df['is_expiry_day'] = df['Date_dt'].map(is_expiry_day)      # [I3]
_exp_rows = df['is_expiry_day']
if _exp_rows.any():
    _exp_show = df.loc[_exp_rows, ['Date', 'Fut_1330', 'Fut_2130']].copy()
    _exp_show['gap%'] = (df.loc[_exp_rows, 'fut_gap_ret'] * 100).round(2)
    _inp('expiry-day rows [I3]', f"{int(_exp_rows.sum())} (3rd Wednesday)",
         'largest gap '
         f"{df.loc[_exp_rows, 'fut_gap_ret'].abs().max()*100:.2f}%")
bad_gap = df['fut_gap_ret'].abs() > 0.06
if bad_gap.any():
    # [Y22] informational only — these are REAL overnight moves (TW limit
    # days and US-session repricing). Nothing is blocked or repaired.
    _inp(f'large overnight {HEDGE_LBL} moves', f"{int(bad_gap.sum())} row(s) > 6%",
         ', '.join(f"{df['Date'].iloc[_i]} "
                   f"{df['fut_gap_ret'].iloc[_i]*100:+.1f}%"
                   for _i in df.index[bad_gap][:4]))
# [P1] merge the REGN next-morning open and quantify the conversion:
if df_fx_regn is not None and len(df_fx_regn):
    df_fx_regn['Date'] = df_fx_regn['Date'].astype(str)
    df = pd.merge(df, df_fx_regn, on='Date', how='left')
    _pop = df['TWD_regn_open'].notna().mean()
    _band_bad = ((df['TWD_regn_open'] < FX_SANE_BAND[0])
                 | (df['TWD_regn_open'] > FX_SANE_BAND[1])).sum()   # [HK0]
    print(f"[P1] {FX_SPOT_TICKER} {FX_SPOT_FIELD}: populated on "
          f"{_pop*100:.0f}% of aligned days | {int(_band_bad)} values outside "
          f"{FX_SANE_BAND[0]}-{FX_SANE_BAND[1]} band")
    if _pop < 0.8:
        print("[P1] WARNING: PX_OPEN poorly populated — do NOT rely on it; "
              "add a 01:0x UTC 'USDTWD REGN Curncy' snap to the capture job")
    # the conversion for a trade printed on row t happens at the NEXT
    # TW morning open ~= the next aligned row's REGN open (holiday
    # approximation). The move from the row's TW-close fixing to that
    # open is the UNHEDGED window the spot_next_open mode carries:
    _conv_rate = df['TWD_regn_open'].shift(-1)
    _unhedged = (_conv_rate / df['TWD (Last)'] - 1).dropna()
    if len(_unhedged) > 50:
        print(f"[P1] unhedged conversion window ({LOCAL_CLOSE_LBL} fixing -> next {LOCAL_LBL} "
              f"open, REGN): mean {_unhedged.mean()*100:+.3f}% | sigma "
              f"{_unhedged.std()*100:.3f}% of the futures-leg notional per "
              f"conversion (mean-zero risk, NOT a cost; two conversions per "
              f"round trip). Compare: the locked-in spot spread cost is "
              f"{2*FX_SPOT_HALF_SPREAD_BPS} bps RT.")
        if abs(_unhedged.mean()) > 2 * _unhedged.std() / np.sqrt(len(_unhedged)):
            print("[P1] NOTE: the window drift mean is >2 SE from zero — a "
                  "persistent TWD trend over the sample; the 'mean-zero' "
                  "assumption is optimistic in trending FX regimes")
else:
    print("[P1] no REGN open series — conversion diagnostics skipped")
# [D2][I1] FX for the fair price: TW-close BFIX, by decision (no live
# US-hours USDTWD history exists). Overnight TWD moves therefore leak
# into the SIGNAL as a noise floor — measured by [F1]/[H2] below and
# gated by MIN_ENTRY_DEV_BPS; the trade PnL itself is NDF-hedged.
df['FX for Fair'] = df['TWD (Last)']
_inp('fair-price FX [D2]', FX_SRC_LBL,
     'noise floor measured in [H2]; trade PnL is NDF-hedged regardless')
# [P1] REGN next-open conversion rate: merge, QC, and MEASURE the
# unhedged window that spot_next_open actually carries — the FX move
# between the TW-close fixing (proxy for trade-time FX) and the NEXT
# morning's 09:00-Taipei REGN open where the conversion executes.
try:
    _regn_ready = _regn_ok and df_fx_regn is not None and len(df_fx_regn)
except NameError:
    _regn_ready = False
if _regn_ready:
    df_fx_regn['Date'] = df_fx_regn['Date'].astype(str)
    df = pd.merge(df, df_fx_regn, on='Date', how='left')
if _regn_ready and 'TWD_regn_open' in df.columns:   # [R3] belt & braces
    _pop = df['TWD_regn_open'].notna().mean()
    _inp(f'next-open FX [P1]', f"{_pop*100:.0f}% populated",
         f"{FX_SPOT_TICKER} {FX_SPOT_FIELD}",
         level=('ok' if _pop > 0.9 else 'warn'))
    if _pop < 0.7:
        print("[P1] WARNING: PX_OPEN sparsely populated — do NOT rely on it; "
              "add the 01:0x UTC snap to the capture job instead")
    else:
        _bad_band = ((df['TWD_regn_open'] < FX_SANE_BAND[0])
                     | (df['TWD_regn_open'] > FX_SANE_BAND[1]))   # [HK0]
        if (_bad_band & df['TWD_regn_open'].notna()).any():
            print(f"[P1] WARNING: {int(_bad_band.sum())} next-open FX prints "
                  f"outside {FX_SANE_BAND[0]}-{FX_SANE_BAND[1]} — check the "
                  f"quote convention")
        # conversion for a trade on row t = next row's REGN open
        # (next aligned row ~ next TW morning; holiday gaps approximate)
        _conv = df['TWD_regn_open'].shift(-1)
        _drift = (_conv / df['TWD (Last)'] - 1).dropna()
        _inp('unhedged FX window [P1]',
             f"mean {_drift.mean()*1e4:+.0f}bps, sigma "
             f"{_drift.std()*1e4:.0f}bps",
             'TW-close fix -> next 09:00 REGN open; mean-zero RISK, not a '
             'cost, 2 conversions per round trip')
        if abs(_drift.mean()) * 1e4 > 10:
            print("[P1] WARNING: the MEAN gap between F093 and next-open REGN "
                  "is materially non-zero — different quote conventions or a "
                  "systematic session effect; verify both tickers on DES "
                  "before trusting the spot_next_open cost model")
# ============================================================
# [HKB] ROLLING BETA — the heart of the HK fair price. A TW hedge is
# the SAME underlying, so beta=1.0 by identity. An INDEX hedge is not:
# the fair must project the ordinary by only the SYSTEMATIC share of
# the overnight index move. Model, per day t (level-on-return — each
# row is an independent observation anchored at that day's HK close):
#     P_t = alpha + beta x g_t + eps_t
#     P_t = ADR_close x FX / (RATIO x ord_close) - 1   (parity gap)
#     g_t = fut_gap_ret_t                              (overnight index gap,
#                                                       SAME column the fair
#                                                       uses — self-consistent)
# Estimator: EWMA cov/var (half-life BETA_HALFLIFE) or flat rolling OLS
# (BETA_WINDOW), per BETA_EST. Then:
#   - SHRINK toward a prior: BETA_SHRINK_W on the rolling estimate,
#     (1-w) on the prior. The prior is the 2y DAILY ord-vs-index
#     regression when >=120 obs exist (available from day one — plain
#     BDH — even though snap history is short), else BETA_PRIOR_INST.
#   - CLAMP to [BETA_MIN, BETA_MAX].
#   - SHIFT(1): day t trades on the beta known at t-1. No look-ahead.
# df['beta_r2'] is the headline hedge-effectiveness number: the hedge
# removes ~R2 of overnight variance, NOTHING MORE (BABA ~0.5;
# Tencent's 0.57 beta implies far less). df['beta_resid'] is the
# OUT-OF-SAMPLE residual (yesterday's beta) — the [HK-H2] noise floor
# and the honest measure of what the hedge cannot see.
# ============================================================
# [HKB] runs ALWAYS — an index hedge has no identity beta
_y_par = (df['TSM US (Close)'] * df['FX for Fair'] / ADR_RATIO
          / df['2330 TT (Close)'] - 1.0)
_x_gap = df['fut_gap_ret']
_prior = float(BETA_PRIOR)
if 'IDX_close' in df.columns and df['IDX_close'].notna().sum() >= 120:
    _ro = df['2330 TT (Close)'].pct_change().values
    _ri = df['IDX_close'].ffill().pct_change().values
    _mmb = np.isfinite(_ro) & np.isfinite(_ri)
    if _mmb.sum() >= 120 and np.var(_ri[_mmb]) > 0:
        _prior_data = float(np.cov(_ro[_mmb], _ri[_mmb])[0, 1]
                            / np.var(_ri[_mmb]))
        _prior = float(np.clip(_prior_data, BETA_MIN, BETA_MAX))
        print(f"[HKB] beta prior refreshed from {int(_mmb.sum())} daily "
              f"ord-vs-{HEDGE_SPINE_TICKER} obs: {_prior:.2f} "
              f"(dict anchor {BETA_PRIOR:.2f})")
if BETA_EST == 'ewma':
    def _bsm(s):
        return s.ewm(halflife=BETA_HALFLIFE, min_periods=20).mean()
else:
    def _bsm(s):
        return s.rolling(BETA_WINDOW, min_periods=30).mean()
_mx, _my = _bsm(_x_gap), _bsm(_y_par)
_cov_b = _bsm(_x_gap * _y_par) - _mx * _my
_var_x = (_bsm(_x_gap * _x_gap) - _mx ** 2).where(lambda s: s > 0)
_var_y = (_bsm(_y_par * _y_par) - _my ** 2).where(lambda s: s > 0)
_beta_roll = _cov_b / _var_x
_r2_roll = (_cov_b ** 2 / (_var_x * _var_y)).clip(0.0, 1.0)
_beta_shr = (BETA_SHRINK_W * _beta_roll
             + (1.0 - BETA_SHRINK_W) * _prior).clip(BETA_MIN, BETA_MAX)
df['beta'] = _beta_shr.shift(1).fillna(_prior)          # no look-ahead
df['beta_r2'] = _r2_roll.shift(1)
df['beta_resid'] = _y_par - df['beta'] * _x_gap          # OOS residual
print(f"[HKB] rolling beta ({BETA_EST}, hl={BETA_HALFLIFE}, "
      f"shrink w={BETA_SHRINK_W:.1f} to prior {_prior:.2f}): "
      f"last {df['beta'].iloc[-1]:.2f} | mean "
      f"{df['beta'].mean():.2f} | rolling R2 mean "
      f"{np.nanmean(df['beta_r2']):.2f} — the hedge removes ~R2 of "
      f"overnight variance, the rest is [HK-H2] residual")
df['Fair (spot_gap)'] = (df['2330 TT (Close)'] * (1.0 + df['beta'] * df['fut_gap_ret'])
                         * ADR_RATIO / df['FX for Fair'])
df['Fair (futures)'] = df['Fut_2130'] * ADR_RATIO / df['FX for Fair']   # [M1]
df['Fair Price'] = (df['Fair (futures)'] if FAIR_MODE == 'futures'
                    else df['Fair (spot_gap)'])
_inp('fair mode [M1]', f"'{FAIR_MODE}'",
     f"mean |spot_gap - futures| diff "
     f"{(df['Fair (spot_gap)'] / df['Fair (futures)'] - 1).abs().mean()*100:.2f}%"
     f" = spot-auction anchor noise")
# ------------------------------------------------------------
# [24] ROLL-SAFE HEDGE INDEX
# ------------------------------------------------------------
# The snapshot files ROLL contracts (monthly for next-month files,
# at expiry for front-month files). A futures-leg PnL computed as
# Fut_2130[exit] / Fut_2130[entry] across a roll date compares TWO
# DIFFERENT CONTRACTS and books the calendar-spread jump as phantom
# PnL — but the real position holds ONE contract through the trade.
# Fix: the hedge PnL is computed on a spliced index that never
# crosses contracts:
#     Hedge Idx_t = Spot_close_t x (Fut_2130_t / Fut_close_t)
# Every ratio is same-contract, same-day; day-over-day changes are
# spot moves plus same-day gap changes — roll-free by construction.
# What this drops: intra-contract basis decay over a <=12cd hold
# (negligible) and the calendar-spread crossing cost of an actual
# roll (execution-level, covered by the cost model's spread terms).
# [32] Date-convention guard: timestamps are wall-clock UTC (user
# confirmed), so the same-calendar-day pairing of the US-open and
# local-close prints is valid. The residual risk is the capture job
# resolving a DIFFERENT contract for the evening print around the
# month boundary; that shows up as a gap outlier, checked here.
_gstd = df['fut_gap_ret'].rolling(60, min_periods=20).std().shift(1)
_gout = df['fut_gap_ret'].abs() > 4.0 * _gstd
if _gout.any():
    # [Y22] reported, never acted on: a >4-sigma overnight SSF move is a
    # REAL repricing (TW limit days, US-session shocks), and the strategy
    # exists to trade exactly those rows.
    _od = df.loc[_gout, ['Date', 'fut_gap_ret']]
    _inp(f'overnight {HEDGE_LBL} outliers', f"{int(_gout.sum())} row(s) > 4 sigma",
         ', '.join(f"{_r['Date']} {_r['fut_gap_ret']*100:+.2f}%"
                   for _, _r in _od.head(4).iterrows()))
# [Y22] the old [J5] suspect-row report and terminal card are GONE with the
# heuristic. If [K7] labels ever flag an exact mismatch it is listed above.
if ROLL_BLOCK_DAYS > 0:   # off by default; contracts are same-date consistent
    _rb = ((df['Date_dt'].dt.day <= ROLL_BLOCK_DAYS)
           | (df['Date_dt'].dt.day >= 29 - ROLL_BLOCK_DAYS + 1))
    df['gap_suspect'] = df['gap_suspect'] | _rb
if df['gap_suspect'].any():
    print(f"[K7] entries blocked on {int(df['gap_suspect'].sum())} row(s) "
          f"(exact contract-label mismatch only)")
 
# ============================================================
# [J4] TR CANDIDATE SELECTION — pick the field that really has dividends
# ============================================================
def _tr_index_from(col, shape):
    """[M1] Return the candidate's cumulative TR INDEX LEVEL.
    CRITICAL: for 'pct' candidates the cumprod is done PRE-MERGE (in the
    pull loop, column '<col>_lvl'), never here. Chaining one-day returns
    over the SURVIVING rows loses every dropped day's return, so the TR
    path drifts away from the price path and the dividend detector reads
    that drift as phantom ex-dates — the exact [G1] failure. The v31
    result showed this clearly: the two INDEX candidates gave TSM 8
    ex-dates / 3.09% (right) while the two DAY_TO_DAY candidates, chained
    post-merge, gave 14 / 8.41% and 21 / 20.53% (phantom)."""
    _lvl = col + '_lvl'
    if _lvl in df.columns:            # pre-merged level (pct candidates)
        _v = pd.to_numeric(df[_lvl], errors='coerce')
    elif col in df.columns and shape == 'level':
        _v = pd.to_numeric(df[col], errors='coerce')
    else:
        return None
    if _v.notna().mean() < 0.5:
        return None
    return _v.ffill()
def _div_content(idx_ser, price_ser):
    """Count ex-dates and total yield implied by (TR return - price
    return), using the instrument's one-day cap [J2]."""
    if idx_ser is None:
        return (-1, 0.0)
    _d = (idx_ser.pct_change() - price_ser.pct_change()).clip(lower=0.0).fillna(0.0)
    _d[_d > DIV_MAX_ONE_DAY] = 0.0
    return (int((_d > 0.0005).sum()), float(_d.sum()))
# [M1] SELECT BY PLAUSIBILITY, not by count. Picking "most ex-dates
# detected" rewards the noisiest series; the right test is whether the
# implied ANNUAL yield matches what the company actually pays.
_yrs = max((pd.to_datetime(df['Date'].iloc[-1])
            - pd.to_datetime(df['Date'].iloc[0])).days / 365.25, 0.2)
print(f"\n[J4] TR field selection (expected yield ~"
      f"{DIV_YIELD_EXPECTED_ANN*100:.1f}%/yr; sample {_yrs:.1f}y):")
_tr_choice = {}
_J4_ROWS = []                          # [Y27] one table for both legs
for _leg, _pxcol in (('hedge', '2330 TT (Close)'), ('adr', 'TSM US (Close)')):
    _cands = []
    for _fi, (_fld, _shape) in enumerate(TR_FIELD_CANDIDATES):
        _idx = _tr_index_from(f'TRc{_fi}_{_leg}', _shape)
        _n, _y = _div_content(_idx, df[_pxcol])
        _ann = _y / _yrs if _n >= 0 else float('nan')
        _ok = (_n > 0 and 0.2 * DIV_YIELD_EXPECTED_ANN <= _ann
               <= 3.0 * DIV_YIELD_EXPECTED_ANN)
        _tag = ('not pulled' if _n < 0 else
                f'{_n} ex-date(s), {_y*100:5.2f}% total = {_ann*100:4.2f}%/yr '
                f"{'[plausible]' if _ok else '[REJECTED: implausible yield]'}")
        _J4_ROWS.append({
            'leg': _leg, 'field': _fld,
            'ex-dates': ('\u2014' if _n < 0 else f"{_n}"),
            'total %': (float('nan') if _n < 0 else _y * 100),
            '%/yr': (float('nan') if _n < 0 else _ann * 100),
            'verdict': (_badge('not pulled', 'mut') if _n < 0
                        else _badge('plausible', 'ok') if _ok
                        else _badge('rejected — implausible yield', 'bad'))})
        if not (HTML_OUTPUT and _in_jupyter()):
            print(f"     {_leg:5s} {_fld:36s}: {_tag}")
        if _ok:
            _cands.append((abs(_ann - DIV_YIELD_EXPECTED_ANN), _shape != 'pct',
                           _fi, _shape, _idx, _n, _ann))
    if _cands:
        _cands.sort(key=lambda x: (x[0], not x[1]))   # closest yield, prefer level
        _c = _cands[0]
        _tr_choice[_leg] = (_c[2], _c[3], _c[4])
        for _r4 in _J4_ROWS:
            if (_r4['leg'] == _leg
                    and _r4['field'] == TR_FIELD_CANDIDATES[_c[2]][0]):
                _r4['verdict'] = _badge('SELECTED', 'ok')
        print(f"     -> {_leg}: using {TR_FIELD_CANDIDATES[_c[2]][0]} "
              f"({_c[5]} ex-dates, {_c[6]*100:.2f}%/yr)")
    else:
        print(f"     -> {_leg}: NO candidate has a plausible yield. Using "
              f"price-only; set MANUAL_DIVIDENDS or the hedge spine and the "
              f"ADR dividend cash will both be wrong.")
# overwrite the legacy index columns with the winners so every
# downstream consumer ([G1] spine, ADR dividend cash) uses the best field
if HTML_OUTPUT and _in_jupyter() and _J4_ROWS:
    show_html_table(
        _pd.DataFrame(_J4_ROWS).set_index('leg'),
        title=f"[J4] TOTAL-RETURN FIELD SELECTION "
              f"(expect ~{DIV_YIELD_EXPECTED_ANN*100:.1f}%/yr over "
              f"{_yrs:.1f}y)",
        fmt={'total %': '{:.2f}', '%/yr': '{:.2f}'},
        note='The winner is the plausible field whose yield sits closest to '
             'expectation, preferring INDEX levels over chained daily '
             'returns — chaining over surviving rows loses every dropped '
             "day and the detector reads that drift as phantom ex-dates.")
if 'hedge' in _tr_choice:
    df['TRidx_hedge'] = _tr_choice['hedge'][2]
if 'adr' in _tr_choice:
    df['TRidx_adr'] = _tr_choice['adr'][2]
# [26][G1] the spine is TOTAL-RETURN based (a real futures position
# does NOT drop on the underlying's ex-date — the dividend is already
# in the basis), and is now built from the PRE-MERGE cumulative TR
# INDEX LEVELS ('TRidx_hedge'), NOT from chaining one-day returns over
# the surviving rows. With ~16% of rows dropped by the merge/stale
# filters, return-chaining silently loses the dropped days' moves
# (that is what fired the old 'TR vs price correlate poorly' warning
# and biased the futures leg by ~-$3.5k/trade in the v17 run); a
# LEVEL ratio between two surviving rows spans the gap correctly.
_pr_spot = df['2330 TT (Close)'].pct_change()   # spans gaps (level-based)
if df['TRidx_hedge'].notna().mean() < 0.5:
    print("[QC] WARNING: total-return index unavailable for the hedge spine — "
          "falling back to PRICE levels; hedge PnL will book fake moves on "
          "ex-dividend dates a hold straddles")
    _spine = df['2330 TT (Close)'] / df['2330 TT (Close)'].iloc[0]
else:
    _spine = (df['TRidx_hedge'].ffill()
              / df['TRidx_hedge'].ffill().iloc[0])
    _tr_span = _spine.pct_change()              # spans gaps too, now comparable
    _corr_span = _pr_spot.corr(_tr_span)
    if _corr_span < 0.95:
        print(f"[QC] WARNING: gap-spanning TR vs price returns correlate at "
              f"{_corr_span:.3f} (<0.95) — genuine TR data problem "
              f"(units/quality), NOT a row-drop artefact")
    else:
        _inp('hedge spine [QC]', f"TR vs price corr {_corr_span:.3f}",
             'gap-spanning; <0.95 would mean a real TR data problem',
             level='ok')
df['Hedge Idx'] = _spine * (df['Fut_2130'] / df['Fut_1330'])
# ============================================================
# [HKS] GENERIC HEDGE COLUMNS — the hedge-mode abstraction. run_backtest
# binds these instead of hard-wiring the SSF columns:
#   'Hedge Px'   : the FILL price series of the hedge instrument
#   'Hedge Idx'  : the roll-safe MARKING spine [24]
#   'hedge_fx'   : FX the hedge leg's PnL converts through (1.0 = USD)
#   'beta_hedge' : sizing beta of the hedge leg (0.0 = naked)
# TW ('ssf'): identical VALUES to v31.12 — Hedge Px = Fut_2130,
# hedge_fx = TWD, beta_hedge = beta = 1.0. Bit-identical output.
# HK 'index_fut': the spine is REPOINTED to the cash index level. This
# is MANDATORY, not cosmetic: the [26] spine above is the ORDINARY's TR
# path, and marking an HTI hedge off 9988's path would book the stock's
# idiosyncratic moves into the hedge leg — a silent, plausible-looking
# bug. The cash index needs no TR field (the futures' dividend discount
# cancels in the same-day gap ratio).
# HK 'us_etf': hedge = the proxy ETF itself at the US close — live all
# US hours (none of the T+1 sequencing gap), USD-denominated
# (hedge_fx=1.0), no contract rolls (the spine IS the price series, so
# _hedge_growth degenerates to a plain ratio). beta_hedge comes from
# its own regression (ADR daily returns on ETF daily returns).
# HK 'none': beta_hedge=0 zeroes the hedge leg in every formula it
# appears in (PnL, costs, margin, fees, FX) — the naked baseline.
# ============================================================
df['Hedge Px'] = df['Fut_2130']
df['hedge_fx'] = df['TWD (Last)']
df['beta_hedge'] = df['beta']
if HEDGE_MODE == 'index_fut':
    if 'IDX_close' in df.columns and df['IDX_close'].notna().mean() > 0.5:
        _idx_spine = df['IDX_close'].ffill()
        df['Hedge Idx'] = ((_idx_spine / _idx_spine.iloc[0])
                           * (df['Fut_2130'] / df['Fut_1330']))
        _inp('hedge spine [HKS]', f'{HEDGE_SPINE_TICKER} level x gap',
             'index-futures hedge marks off the INDEX path, not the '
             'ordinary', level='ok')
    else:
        print("[HKS] WARNING: no index level series — Hedge Idx still "
              "rides the ORDINARY's TR path, which books the stock's "
              "idio moves into the hedge marks. Fix the "
              f"{HEDGE_SPINE_TICKER} pull before trusting hedge PnL.")
elif HEDGE_MODE == 'us_etf':
    if 'ETF_close' in df.columns and df['ETF_close'].notna().mean() > 0.5:
        _etf_px = df['ETF_close'].ffill()
        df['Hedge Px'] = _etf_px
        df['Hedge Idx'] = _etf_px / _etf_px.iloc[0]
        df['hedge_fx'] = 1.0                      # USD instrument
        _ra_e = df['TSM US (Close)'].pct_change()
        _re_e = _etf_px.pct_change()
        _mx_e, _my_e = _bsm(_re_e), _bsm(_ra_e)   # [HKB] same smoother
        _cov_e = _bsm(_re_e * _ra_e) - _mx_e * _my_e
        _var_e = (_bsm(_re_e * _re_e) - _mx_e ** 2).where(lambda s: s > 0)
        df['beta_hedge'] = ((BETA_SHRINK_W * (_cov_e / _var_e)
                             + (1.0 - BETA_SHRINK_W) * 1.0)
                            .clip(BETA_MIN, BETA_MAX)
                            .shift(1).fillna(1.0))
        print(f"[HKS] us_etf hedge: beta_hedge last "
              f"{df['beta_hedge'].iloc[-1]:.2f} vs signal beta "
              f"{df['beta'].iloc[-1]:.2f}")
    else:
        raise RuntimeError("[HKS] HEDGE_MODE='us_etf' but no ETF price "
                           "series was pulled — check ETF_PROXY_TICKER")
elif HEDGE_MODE == 'none':
    df['beta_hedge'] = 0.0
    print("[HKS] HEDGE_MODE='none': naked ADR — beta_hedge=0 zeroes the "
          "hedge leg (PnL, costs, margin, FX) everywhere")
# [S2] per-row funding rate (decimal). Merge the SOFR series, forward-
# fill the odd missing print, fall back to the constant if unavailable.
if 'df_sofr' in dir() and df_sofr is not None and len(df_sofr):
    df_sofr['Date'] = df_sofr['Date'].astype(str)
    df = pd.merge(df, df_sofr, on='Date', how='left')
    _sofr = (pd.to_numeric(df['sofr_pct'], errors='coerce') / 100.0).ffill().bfill()
    if _sofr.isna().all():
        df['funding_rate'] = FUNDING_RATE_ANN + FUNDING_SPREAD_ANN   # [T1]
    else:
        df['funding_rate'] = _sofr + FUNDING_SPREAD_ANN              # [T1] SOFR + spread
    _inp('funding [S2][T1]', f"SOFR + {FUNDING_SPREAD_ANN*100:.2f}%",
         f"min {df['funding_rate'].min()*100:.2f}% / max "
         f"{df['funding_rate'].max()*100:.2f}% / last "
         f"{df['funding_rate'].iloc[-1]*100:.2f}%")
else:
    df['funding_rate'] = FUNDING_RATE_ANN + FUNDING_SPREAD_ANN       # [T1]
    print(f"[S2][T1] funding: flat {(FUNDING_RATE_ANN+FUNDING_SPREAD_ANN)*100:.2f}% "
          f"(SOFR+{FUNDING_SPREAD_ANN*100:.1f}%; SOFR pull unavailable)")
# [L2] DIVIDEND-DETECTION GUARD — the spine corr prints 1.000 in a
# HEALTHY sample (TR return == price return on every non-ex-date; the
# handful of ex-dates differ by only ~0.5-1%, so corr ~0.9999 -> 1.000
# at 3dp). But corr = 1.000 is ALSO what a BROKEN, dividend-less TR
# field would print (TR literally == price return every day). The two
# cases are distinguished by counting the dividends actually
# extracted: 2330 pays quarterly cash, so expect roughly 4 ex-dates
# and ~1.5-2.5% of yield per year. Zero detected => the TR field is
# price-only and every dividend in the backtest silently vanishes.
_spine_div = (_spine.pct_change() - _pr_spot).clip(lower=0.0).fillna(0.0)
_spine_div[_spine_div > DIV_MAX_ONE_DAY] = 0.0   # [J2]
# [W1] NOISE FLOOR. TR minus price return is a difference of two nearly
# identical series, so on every ordinary day it leaves floating-point dust
# of order 1e-6. clip(lower=0) keeps the positive dust, and because the
# [T3] margin-dividend accrual has no threshold of its own, that dust was
# being banked day after day — the symptom was a trade reporting a TAIFEX
# margin dividend of "$+2" on a $500k notional (4e-6 x 500k) where a real
# TSM quarter should be ~$2,250. Anything below the floor is not a
# dividend, it is arithmetic residue.
DIV_MIN_ONE_DAY = 0.0015        # 15 bps: below this it is noise, not a dividend
_n_dust = int(((_spine_div > 0) & (_spine_div < DIV_MIN_ONE_DAY)).sum())
_dust_tot = float(_spine_div[_spine_div < DIV_MIN_ONE_DAY].sum())
_spine_div[_spine_div < DIV_MIN_ONE_DAY] = 0.0
if _n_dust:
    _inp('TR residue zeroed [W1]',
         f"{_n_dust} sub-{DIV_MIN_ONE_DAY*1e4:.0f}bps entries "
         f"({_dust_tot*1e4:.1f} bps total)",
         'TR-minus-price dust, not ex-dates — must not accrue cash')
df['div_ret_hedge'] = _spine_div.fillna(0.0)   # [R5] for the hedge adjustment
# [R7][S4] CONTRACT-BREAK DETECTOR — now that the dividend series
# exists, compare the futures' 1-day move against the ordinary's
# DIVIDEND-ADJUSTED (TR) 1-day move. This matters because the classic
# splice happens ON the ex-date itself: the ordinary drops ~6.8%
# (ex-div) while the spliced futures print drops ~8.2% — a raw price
# comparison sees only a 1.4% difference and misses it, but against
# the TR return (~0% on the ex-date) the 8.2% sticks out. On normal
# days TR == price return, so behaviour elsewhere is unchanged; on a
# genuine crash both legs fall together and no break is flagged.
# [T2] compare against the ordinary's RAW price return, because on an
# ex-date BOTH the spot and the futures legitimately fall (the dividend
# is settled in cash, not priced in) — so a raw comparison shows no
# break, which is correct. Comparing against the TR return instead
# would flag every ex-date as a splice and remove a price move that
# really happened. Ex-date rows are also excluded explicitly.
_f1d = df['Fut_1330'].pct_change()
# [HKS] the break test compares the future against ITS OWN underlying:
# the ordinary for a same-name SSF, the CASH INDEX for an index future
# (HTI vs 9988 differ by idio moves >4% routinely — comparing against
# the ordinary would flag real stock moves as contract breaks).
if 'IDX_close' in df.columns and df['IDX_close'].notna().mean() > 0.5:
    _o1d = df['IDX_close'].ffill().pct_change()
else:
    _o1d = df['2330 TT (Close)'].pct_change()
df['contract_break'] = (((_f1d - _o1d).abs() > CONTRACT_BREAK_PCT)
                        & (CONTRACT_BREAK_PCT > 0)
                        & (df['div_ret_hedge'] <= 0.0005)).fillna(False)
if df['contract_break'].any():
    print(f"[R7] {int(df['contract_break'].sum())} contract-break row(s): the "
          f"futures moved but the ordinary did not ->")
    for _i in df.index[df['contract_break']]:
        _bs = (df['Fut_1330'].iloc[_i] / df['2330 TT (Close)'].iloc[_i] - 1) * 100
        print(f"       {df['Date'].iloc[_i]}  fut 1d {_f1d.iloc[_i]*100:+.2f}% vs "
              f"ord 1d {_o1d.iloc[_i]*100:+.2f}% | basis after {_bs:+.2f}% "
              f"-> hedge spliced via the TR spine here [I3]")
else:
    _inp('contract continuity [R7]', 'no breaks',
         f"at the {CONTRACT_BREAK_PCT*100:.0f}% threshold — the 13:30 "
         f"series is continuous", level='ok')
# [S5] flag the rows sitting just before a detected ex-date
df['pre_exdate'] = False
if BLOCK_ENTRY_EXDATE_DAYS > 0:
    for _i in df.index[df['div_ret_hedge'] > 0.0005]:
        df.loc[max(_i - BLOCK_ENTRY_EXDATE_DAYS, 0):_i, 'pre_exdate'] = True
    for _i in df.index[df['div_ret_adr'] > 0.0005]:
        df.loc[max(_i - BLOCK_ENTRY_EXDATE_DAYS, 0):_i, 'pre_exdate'] = True
    if df['pre_exdate'].any():
        print(f"[S5] {int(df['pre_exdate'].sum())} row(s) blocked for entry: "
              f"within {BLOCK_ENTRY_EXDATE_DAYS} rows of a detected ex-date "
              f"(hedge or ADR). Set BLOCK_ENTRY_EXDATE_DAYS=0 once you have "
              f"confirmed the SSF contract is dividend-adjusted.")
# ============================================================
# [HKE] EARNINGS ENTRY BLOCK (new for HK; inert for TW where
# EARNINGS_BLOCK_DAYS=0). China ADRs gap hard on quarterly prints,
# usually released around the US PRE-OPEN — so the dangerous entry is
# the US close BEFORE the announcement: a stretched z into earnings is
# far more likely informed positioning than noise. Rows within
# [E - EARNINGS_BLOCK_DAYS, E] of each MANUAL_EARNINGS date E are
# blocked for NEW ENTRIES only; an open position HOLDS through the
# print (consistent with ADF_EXIT_POLICY='entry_only' — with
# TIME_STOP=25cd some holds will span one; the trade log flags them).
# ============================================================
df['earnings_block'] = False
if EARNINGS_BLOCK_DAYS > 0 and MANUAL_EARNINGS:
    _earn_dts = pd.to_datetime(pd.Series(list(MANUAL_EARNINGS)),
                               errors='coerce').dropna()
    for _ed in _earn_dts:
        _dd_e = (_ed - df['Date_dt']).dt.days
        df.loc[(_dd_e >= 0) & (_dd_e <= EARNINGS_BLOCK_DAYS),
               'earnings_block'] = True
    _in_sample_e = int(((_earn_dts >= df['Date_dt'].iloc[0])
                        & (_earn_dts <= df['Date_dt'].iloc[-1])).sum())
    print(f"[HKE] earnings gate: {int(df['earnings_block'].sum())} row(s) "
          f"blocked around {_in_sample_e} in-sample announcement date(s) "
          f"(window: {EARNINGS_BLOCK_DAYS} row(s) before each print, "
          f"entries only — open positions hold)")
elif EARNINGS_BLOCK_DAYS > 0:
    print(f"[HKE][QC] WARNING: EARNINGS_BLOCK_DAYS={EARNINGS_BLOCK_DAYS} but "
          f"MANUAL_EARNINGS is EMPTY — the earnings gate is OFF. Fill the "
          f"quarterly announcement dates in the INSTRUMENTS dict (~20 rows "
          f"for 5y; ERN <GO> / company IR) before trusting entries that sit "
          f"within 2 days of a print.")
_n_ex_spine = int((_spine_div > 0.0005).sum())
_yield_spine = float(_spine_div.sum())
_n_years = max((df['Date_dt'].iloc[-1] - df['Date_dt'].iloc[0]).days / 365.25, 0.1)
_inp('ordinary dividends [L2]',
     f"{_n_ex_spine} ex-date(s), {_yield_spine*100:.2f}% over "
     f"{_n_years:.1f}y",
     f"expect ~{DIV_YIELD_EXPECTED_ANN*100:.1f}%/yr for this name")
if _n_ex_spine == 0:
    print("[QC][L2] WARNING: ZERO dividends in the TR spine — the TR field is "
          "probably PRICE-ONLY; ex-date drops will book fake hedge PnL")
    print("[H6] FIX PATH, in order of preference:")
    print("     1. On FLDS check the TR field for this ticker. If")
    print("        DAY_TO_DAY_TOT_RETURN_GROSS_DVDS is empty, try")
    print("        TOT_RETURN_INDEX_GROSS_DVDS (an index level, which is")
    print("        what [G1] wants anyway) or the NET_DVDS variant.")
    print("     2. If no TR field populates, fill MANUAL_DIVIDENDS in the")
    print(f"        INSTRUMENTS dict with (ex_date, cash per share in {LOCAL_CCY})")
    print("        from DVD / the exchange notice — one row per year is")
    print("        enough for an annual payer.")
    print("     3. Until then treat this name's PnL as UNRELIABLE: an")
    print("        annual ~5% dividend books a ~5% fake hedge loss/gain on")
    print("        the one ex-date any hold straddles.")
if MANUAL_DIVIDENDS:
    # [H6] graft manual ex-dates onto the spine: scale the spine from the
    # ex-date onward by (1 + div/price) so the hedge leg sees a
    # dividend-adjusted (total-return) path exactly as [G1] intends.
    _md_applied = 0
    for _exd, _amt in MANUAL_DIVIDENDS:
        _hit = df.index[df['Date'] == str(_exd)]
        if len(_hit) and _amt > 0:
            _i = int(_hit[0])
            _px = float(df['2330 TT (Close)'].iloc[_i])
            if _px > 0:
                _spine.iloc[_i:] = _spine.iloc[_i:] * (1.0 + _amt / _px)
                _md_applied += 1
    print(f"[H6] MANUAL_DIVIDENDS: {_md_applied} of {len(MANUAL_DIVIDENDS)} "
          f"ex-date(s) grafted onto the hedge spine")
# [26][G1] ADR dividend cash from LEVELS: over the span between two
# consecutive SURVIVING rows, div yield = TR-index growth minus price
# growth — so an ex-date falling on a DROPPED row is still credited
# (the old one-day version lost it). Long receives, short pays.
if df['TRidx_adr'].notna().mean() < 0.5:
    df['div_ret_adr'] = 0.0
    print("[QC] WARNING: total-return index unavailable for the ADR — "
          "dividend cash across holds will NOT be credited/debited")
else:
    _tr_adr_span = df['TRidx_adr'].ffill().pct_change()
    _pr_adr_span = df['TSM US (Close)'].pct_change()
    df['div_ret_adr'] = (_tr_adr_span - _pr_adr_span).clip(lower=0.0).fillna(0.0)
    # [P3] cap is PER-INSTRUMENT: a hardcoded 0.05 silently deleted
    # UMC's ~6% single-day annual ADR dividend (the [J4] selector saw 1
    # ex-date / 6.01% on the chosen index, yet [L2] reported 0 — this
    # line was the reason). TSM quarterly ~0.5% was unaffected.
    df.loc[df['div_ret_adr'] > DIV_MAX_ONE_DAY, 'div_ret_adr'] = 0.0
    df.loc[df['div_ret_adr'] < DIV_MIN_ONE_DAY, 'div_ret_adr'] = 0.0   # [W1]
# ============================================================================
# [U5] DIVIDEND-CARRY ADJUSTMENT — removes a FAKE signal spike worth ~700 bps
# ----------------------------------------------------------------------------
# The Taiwan ex-date and the ADR ex-date are DIFFERENT days (the depositary
# sets the ADR one, usually later). Between them:
#     the ordinary has already dropped by the dividend
#     the ADR still carries the dividend right
# The fair price is built from the ordinary, so it drops while the ADR does
# not, and the computed premium JUMPS by roughly the dividend. Measured on
# UMC's ~6.8% annual dividend that is a +738 bps spike out of a series whose
# sigma is ~120 bps — it detonates the z-score, fires a SHORT-spread signal,
# and poisons the rolling mean and sigma for the next N days.
# It is NOT a mispricing: short the ADR and you will owe that dividend, long
# the SSF and you were credited it, so the two cancel and all you keep is the
# round-trip cost. A guaranteed loser dressed up as the biggest signal of the
# year.
# FIX: carry the dividend on the fair price from the TW ex-date until the ADR
# ex-date, i.e. value the ordinary CUM-dividend for as long as the ADR still
# is. Applies to the SIGNAL only; the two-leg P&L already books both cash
# flows separately ([T3] margin credit + the ADR dividend charge).
# ============================================================================
DIV_CARRY_ADJ = True          # False reproduces the old (spiking) behaviour
DIV_CARRY_MAX_ROWS = 30       # safety: release the carry after this many rows
                              # even if no ADR ex-date was detected
if DIV_CARRY_ADJ:
    _carry = np.zeros(len(df))
    _c, _age = 0.0, 0
    for _i in range(len(df)):
        _dh = float(df['div_ret_hedge'].iloc[_i] or 0.0)
        _da = float(df['div_ret_adr'].iloc[_i] or 0.0)
        if _dh > 0.0005:                     # Taiwan went ex: ordinary lost it
            _c += _dh
            _age = 0
        if _da > 0.0005 and _c > 0:          # ADR went ex: both stripped now
            _c, _age = 0.0, 0
        if _c > 0:
            _age += 1
            if _age > DIV_CARRY_MAX_ROWS:
                _c, _age = 0.0, 0
        _carry[_i] = _c
    df['div_carry'] = _carry
    _n_adj = int((df['div_carry'] > 0).sum())
    if _n_adj:
        _pk = float(df['div_carry'].max()) * 1e4
        df['Fair (spot_gap)'] = df['Fair (spot_gap)'] * (1.0 + df['div_carry'])
        df['Fair (futures)'] = df['Fair (futures)'] * (1.0 + df['div_carry'])
        df['Fair Price'] = (df['Fair (futures)'] if FAIR_MODE == 'futures'
                            else df['Fair (spot_gap)'])
        print(f"[U5] dividend carry applied on {_n_adj} row(s); peak carry "
              f"{_pk:.0f} bps — that is the fake premium spike removed from the "
              f"signal (the two-leg P&L is unaffected, it books both cash flows)")
        for _i in df.index[(df['div_carry'] > 0)
                           & (df['div_carry'].shift(1).fillna(0) == 0)]:
            _end = _i
            while _end + 1 < len(df) and df['div_carry'].iloc[_end + 1] > 0:
                _end += 1
            print(f"     {df['Date'].iloc[_i]} .. {df['Date'].iloc[_end]}  "
                  f"carry {df['div_carry'].iloc[_i]*1e4:.0f} bps "
                  f"({_end - _i + 1} rows)")
    else:
        df['div_carry'] = 0.0
        _inp('dividend-carry windows [U5]', 'none',
             'every TW ex-date has a matching ADR ex-date, so the premium '
             'carries no dividend step — div_carry stays 0', level='ok')
else:
    df['div_carry'] = 0.0
    print(f"[U5] DIV_CARRY_ADJ=False — a TW ex-date without a matching ADR "
          f"ex-date WILL spike the premium by roughly the dividend")
    _n_ex_adr = int((df['div_ret_adr'] > 0.0005).sum())
    _yield_adr = float(df['div_ret_adr'].sum())
    _inp('ADR dividends [L2]',
         f"{_n_ex_adr} ex-date(s), {_yield_adr*100:.2f}% over the sample",
         'zero detected would mean a TR field problem')
# ============================================================
# [R5][HKS] EX-DATE BEHAVIOUR — DELETED IN THE HK BOOK.
# ============================================================
# The Taiwan file votes, on each ordinary ex-date, on whether the
# same-name SSF fell with the spot, and switches a price-path
# adjustment on that evidence. Against an INDEX future the question is
# not merely unanswerable, it is a trap: HTI does not react to one
# constituent going ex, so any apparent "follow" is a coincidence that
# would switch a dividend correction on for no reason.
# In this book the hedge carries dividends in its BASIS, there is no
# margin-account cash credit ([T1] is TAIFEX-only, deleted), and the
# hedge price path is never rescaled:
HEDGE_DIV_ADJ_ON = False
_n_ex_ord = int((df["div_ret_hedge"] > 0.0005).sum())
_inp("hedge dividend treatment [R5][HKS]",
     "index basis — no adjustment, no cash credit",
     f"{_n_ex_ord} ordinary ex-date(s) still drive the [U5] SIGNAL carry "
     f"and the ADR dividend cash on the stock leg", level="ok")
# ============================================================
# EXECUTION PRICE  ([14] VWAP fills removed in v6)
# ============================================================
# The v5 attempt to fill at the 09:30-09:35 ET VWAP (Bloomberg 'VWAP'
# field with time-window overrides, one request per date) returned 0%
# coverage on this terminal after ~1,000 slow requests, so it is
# REMOVED. Fills are at the open print. The execution-reality checks
# are now the EXECUTION-LAG test plus the noise diagnostics in the
# summary. True intraday validation (does the deviation survive the
# first minutes after the open?) must be done outside this script —
# e.g. IntradayBarRequest (Bloomberg keeps only ~140 days of bars) or
# exchange TAQ data for the specific top-PnL dates.
session.stop()   # [7] all Bloomberg requests done
# [35] the ADR price at the chosen execution time
df['ADR Ref Px'] = df['TSM US (Open)'] if EXEC_TIMING == 'open' else df['TSM US (Close)']
df['Exec Px'] = df['ADR Ref Px']
# [V1] signal definition switch. 'dollar' = ADR - Fair (USD);
# 'premium' = (ADR/Fair - 1) in bps (scale-invariant). Everything
# downstream (z-score, entry/exit, gamma) inherits whichever this is.
if SIGNAL_MODE == 'premium':
    df['Spread (Signal)'] = (df['ADR Ref Px'] / df['Fair Price'] - 1.0) * 10000.0
else:
    df['Spread (Signal)'] = df['ADR Ref Px'] - df['Fair Price']
df['Spread (Exec)'] = df['Spread (Signal)']   # decision and fill both at the open
# ============================================================
# [X4] MONTH-START ROLL STEP IN THE SIGNAL — the test [K6] cannot do.
# ------------------------------------------------------------
# [K6] tests fut_gap_raw = Fut_2130 / Fut_1330, a SAME-DAY RATIO of two
# prints of the SAME contract. The contract cancels, so [K6] is
# structurally BLIND to a roll step and passing it says nothing about
# FAIR_MODE='futures'.
#   FAIR_MODE='spot_gap' inherits that cancellation and is roll-immune.
#   FAIR_MODE='futures' uses the futures LEVEL, which jumps by one
#   calendar spread on the first row of each month.
# So test the premium itself: is |1-day premium change| systematically
# bigger on roll rows than elsewhere? Report the EXCESS in units of the
# deviation sigma — that, not the raw roll-row mean, is what the z-score
# actually feels.
# ============================================================
_x4_roll = df['contract_id'] != df['contract_id'].shift(1)
_x4_dsig = float((df['Spread (Signal)']
                  - df['Spread (Signal)'].rolling(30, min_periods=10)
                  .mean().shift(1)).std())
print(f"\n[X4] month-start roll-step test ({int(_x4_roll.sum())} roll rows of "
      f"{len(df)}); deviation sigma = {_x4_dsig:.0f} bps")
for _x4_lbl, _x4_fair in (('futures ', df['Fair (futures)']),
                          ('spot_gap', df['Fair (spot_gap)'])):
    _x4_p = (df['ADR Ref Px'] / _x4_fair - 1.0) * 1e4
    _x4_d = _x4_p.diff().abs()
    _x4_a, _x4_b = _x4_d[_x4_roll].dropna(), _x4_d[~_x4_roll].dropna()
    if len(_x4_a) >= 3 and _x4_b.std() > 0:
        _x4_t = ((_x4_a.mean() - _x4_b.mean())
                 / (_x4_b.std() / np.sqrt(len(_x4_a))))
        _x4_ex = (_x4_a.mean() - _x4_b.mean()) / _x4_dsig if _x4_dsig > 0 else np.nan
        _x4_v = ('ROLL STEP CONFIRMED — splice the fair at each contract_id '
                 'change' if abs(_x4_t) > 2.5 else 'no significant step')
        _inp(f"roll step [X4], FAIR_MODE='{_x4_lbl.strip()}'",
             f"{_x4_a.mean():.0f}bps on roll rows vs {_x4_b.mean():.0f} "
             f"elsewhere, excess {_x4_ex:+.2f} sigma (t={_x4_t:+.1f})",
             _x4_v, level=('warn' if abs(_x4_t) > 2.5 else 'ok'))
        if _x4_lbl.strip() == FAIR_MODE:
            sc('FAIL' if abs(_x4_t) > 2.5 else 'PASS', 'roll step in the signal',
               f"excess {_x4_ex:+.2f} sigma, t={_x4_t:+.1f}")
_inp('roll-step power [X4]', f"~12 roll rows/year",
     'low power: read the excess-sigma column, not the t verdict. Under '
     '~0.3 sigma the step is not worth engineering around either way')
# [Z4] drift-ratio diagnostic (representative N=20): how often would
# the repricing filter fire at various thresholds — calibrate
# DRIFT_MAX_SIGMA from THIS, not from the synthetic table above.
_zs = df['Spread (Signal)']
_m20 = _zs.rolling(20).mean().shift(1)
_c20 = _zs.diff().rolling(20).std(ddof=0).shift(1)
_dr = ((_m20 - _m20.shift(5)).abs() / (_c20 * np.sqrt(5.0))).replace([np.inf, -np.inf], np.nan).dropna()
if len(_dr):
    _inp('drift ratio [Z4], N=20',
         f"p50 {_dr.quantile(0.5):.2f} / p90 {_dr.quantile(0.9):.2f} / "
         f"p99 {_dr.quantile(0.99):.2f}",
         f"the repricing filter stands aside on "
         f"{(_dr > DRIFT_MAX_SIGMA).mean()*100:.0f}% of days at "
         f"DRIFT_MAX_SIGMA={DRIFT_MAX_SIGMA}")
# [Y27] ONE INPUT-DIAGNOSTICS TABLE for everything collected above
if HTML_OUTPUT and _in_jupyter() and _INPUT_ROWS:
    show_html_table(
        pd.DataFrame(_INPUT_ROWS,
                     columns=['check', 'reading', 'note']).set_index('check'),
        title='INPUT DIAGNOSTICS — FX, fair price, dividends, contracts',
        fmt='{}',
        note='Every line here is a property of the DATA, not a result. '
             'Nothing in this block blocks a trade.')
_wu = first_tradable_row(max(N_VALUES))   # [X3]
kv_table(f"RUN CONFIG — {NAME_LBL}: {ADR_LBL} vs {ORD_LBL} "
         f"(1 ADR = {ADR_RATIO:.0f} ordinary)",
         [('hedge', f"{HEDGE_LBL}", HEDGE_LONG_LBL),
          ('signal', f"{SIGNAL_MODE}",
           'premium ratio in bps' if SIGNAL_MODE == 'premium'
           else 'absolute USD spread'),
          ('fair price', f"{FAIR_MODE}", ''),
          ('fill timing', f"{EXEC_TIMING}",
           'closing auction / MOC' if EXEC_TIMING == 'close'
           else 'open print'),
          ('gate', f"{GATE_MODE} / {ADF_EXIT_POLICY}",
           'entry_only: the gate never forces an exit — see [Y24] position '
           'health' if ADF_EXIT_POLICY == 'entry_only' else ''),
          ('sizing', f"{SIZING_MODE}", f"cap {SIZE_CAP:.1f}x"),
          ('notional', f"${NOTIONAL:,.0f}", ''),
          ('warm-up [Q3]',
           (f"{_wu} of {len(df)} rows ({_wu/len(df)*100:.0f}%)"
            if len(df) > _wu else 'n/a'),
           (f"gate window {gate_window()} rows -> no trade before "
            f"{df['Date'].iloc[_wu]}; a lower GATE_WINDOW recovers sample "
            f"at the cost of a noisier AR(1) gamma" if len(df) > _wu else '')),
          ('sections',
           '1 QC -> 2 spikes -> 3 cost/regime -> 4 grid -> 5 forensics '
           '-> 6 execution realism -> 7 robustness -> 8 charts', '')])
# ============================================================
# [C2][G2] SPREAD-SPIKE VERIFICATION — is the second chart's spike real?
# ============================================================
# v18 fixes two things the live run exposed:
#   (1) PREV CLOSE WAS WRONG when rows in between had been dropped:
#       shift(1) on the FILTERED df returned the previous SURVIVING
#       row (e.g. for 2025-10-02 it showed 273.36 = the 09/26 close,
#       because 09/29-10/01 were dropped by the stale filters), not
#       the previous TRADING day. The true prev close now comes from
#       the FULL pre-merge ADR series, with its date printed.
#   (2) RANKING BY RAW SPREAD IS MEANINGLESS FOR TSM: the ADR trades
#       at a PERSISTENT structural premium (~+19% mean in this
#       sample), so the top raw spreads are just the highest-premium
#       days — every day is "+2200 bps". What the strategy actually
#       trades (and what a bad print actually distorts) is the
#       DEVIATION of the premium from its rolling mean, so extremes
#       are now ranked by |spread - rolling mean| (the z numerator).
banner("SPREAD-SPIKE VERIFICATION — top 15 deviation days [C2][G2]")
_C2_ROWS = []                      # [Y23] collected, rendered as ONE table
# [V1] _sb_chk is a premium-in-bps view for the diagnostics. In
# 'premium' mode the Spread column IS already bps; in 'dollar' mode
# convert by dividing by the ADR price.
if SIGNAL_MODE == 'premium':
    _sb_chk = df['Spread (Signal)']
    _sb_mean = df['Spread (Signal)'].rolling(30, min_periods=10).mean().shift(1)
    _sb_dev = df['Spread (Signal)'] - _sb_mean
else:
    _sb_chk = df['Spread (Signal)'] / df['ADR Ref Px'] * 10000
    _sb_mean = df['Spread (Signal)'].rolling(30, min_periods=10).mean().shift(1)
    _sb_dev = (df['Spread (Signal)'] - _sb_mean) / df['ADR Ref Px'] * 10000
print(f"  Structural premium mean {_sb_chk.mean():+.0f} bps is a LEVEL, not an "
      f"error — ranked below by DEVIATION from the 30d rolling mean.")
_fx_chg = df['TWD (Last)'].pct_change()
# [K4] cross-check the ref print against the OTHER same-day print: in
# open mode ref=open -> compare vs same-day close; in close mode
# ref=close -> compare vs same-day open (v21 compared close vs itself,
# printing a useless '+0.00% open-to-close' on every row)
if EXEC_TIMING == 'open':
    _adr_vs_other = df['ADR Ref Px'] / df['TSM US (Close)'] - 1.0
    _other_col, _other_lbl, _move_lbl = 'TSM US (Close)', 'same-day ADR close', 'open-to-close'
    _ret_lbl = 'overnight'
else:
    _adr_vs_other = df['ADR Ref Px'] / df['TSM US (Open)'] - 1.0
    _other_col, _other_lbl, _move_lbl = 'TSM US (Open)', 'same-day ADR open', 'open-to-close'
    _ret_lbl = 'close-to-close'
# true previous trading day from the FULL (pre-merge, pre-filter) series
_full = _adr_close_full[['Date', 'TSM US (Close)']].copy()
_full.columns = ['Date', '_close_full']
_full = _full.dropna().sort_values('Date').reset_index(drop=True)
def _true_prev_close(date_str):
    _prior = _full[_full['Date'] < date_str]
    if len(_prior) == 0:
        return np.nan, 'n/a'
    _r = _prior.iloc[-1]
    return float(_r['_close_full']), _r['Date']
_top_idx = _sb_dev.abs().nlargest(15).index
for _i in _top_idx:
    _r = df.loc[_i]
    _pc, _pc_date = _true_prev_close(_r['Date'])
    _on_ret = _r['ADR Ref Px'] / _pc - 1.0 if np.isfinite(_pc) else np.nan
    _verdict = []
    _prev_df_date = df['Date'].shift(1).loc[_i]
    if isinstance(_prev_df_date, str):
        _gap_cd = (pd.to_datetime(_r['Date']) - pd.to_datetime(_prev_df_date)).days
        if _gap_cd > 4:
            _verdict.append(f"previous SURVIVING row ({_prev_df_date}) is "
                            f"{_gap_cd}cd back — rows were dropped in between, "
                            f"so the z-score/rolling context spans a gap; the "
                            f"printed overnight move (vs the TRUE prev close "
                            f"above) is still correct")
    if abs(_fx_chg.loc[_i]) > 0.01:
        _verdict.append("FX moved >1% on the day — check the FX print first")
    if abs(_r['Fut_1330'] / _r['2330 TT (Close)'] - 1.0) > 0.02:
        _verdict.append(f"{HEDGE_LBL} {LOCAL_CLOSE_LBL} print >2% off the "
                            f"index close — check the print")
    if abs(_r['fut_gap_ret']) > 0.04:
        # [Y22] a big overnight SSF move is REAL information, not a mismatch
        _verdict.append("large overnight SSF move — real dislocation candidate")
    if (np.isfinite(_on_ret) and abs(_adr_vs_other.loc[_i]) > 0.03
            and abs(_on_ret) > 0.03):
        _verdict.append(f"ADR ref print >3% off BOTH its prev close and the "
                        f"{_other_lbl} — suspect a bad print")
    if not _verdict:
        _verdict.append("inputs individually sane — likely a REAL dislocation "
                        "(ADR moved; the SSF gap did not follow). Confirm the "
                        "open print on intraday quotes before trusting it.")
    _C2_ROWS.append({
        'date': _r['Date'], 'dev bps': float(_sb_dev.loc[_i]),
        'level bps': float(_sb_chk.loc[_i]),
        f'ADR {EXEC_TIMING}': float(_r['ADR Ref Px']),
        'prev close': f"{_pc:.2f} ({_pc_date})",
        _ret_lbl: (f"{_on_ret*100:+.2f}%" if np.isfinite(_on_ret) else '\u2014'),
        'ord close': float(_r['2330 TT (Close)']),
        'SSF 13:30': float(_r['Fut_1330']),
        f'SSF {EXEC_TIMING}': float(_r['Fut_2130']),
        'o/n SSF': f"{_r['fut_gap_ret']*100:+.2f}%",
        'FX d/d': f"{_fx_chg.loc[_i]*100:+.2f}%",
        'verdict': (_badge('inputs sane — real dislocation', 'ok')
                    if _verdict and _verdict[0].startswith('inputs individually')
                    else ' '.join(_badge(v, 'warn') for v in _verdict))})
    if not (HTML_OUTPUT and _in_jupyter()):
        print(f"  {_r['Date']}  dev {_sb_dev.loc[_i]:+.0f}bps  "
              + "; ".join(_verdict))
if HTML_OUTPUT and _in_jupyter() and _C2_ROWS:
    show_html_table(
        pd.DataFrame(_C2_ROWS).set_index('date'),
        title='SPREAD-SPIKE VERIFICATION — top 15 deviation days',
        fmt={'dev bps': '{:+,.0f}', 'level bps': '{:+,.0f}',
             f'ADR {EXEC_TIMING}': '{:,.2f}', 'ord close': '{:,.1f}',
             'SSF 13:30': '{:,.1f}', f'SSF {EXEC_TIMING}': '{:,.1f}'},
        note="Sane inputs are necessary, not sufficient — for the top-PnL "
             "dates pull the first-10-minute ET tape and confirm the print "
             "was hittable in size. Large overnight SSF moves are REAL "
             "information [Y22], not flags.")
# [D2][F1] FX-SOURCE BEHAVIOUR TEST — you may THINK you are pulling a
# US-hours BFIX, but the SERIES can still be a TW-close value (fixing
# published then never updated, discontinued code, or a code whose
# snap time is not what you assumed). Rather than trusting the ticker
# name, test how the DATA behaves:
#   test 1 — liveness: a genuine NDF-based fixing changes essentially
#     every business day; a large fraction of unchanged days means
#     the fixing is NOT updating (dead/stale code).
#   test 2 — timestamp fingerprint: the overnight TWD move between
#     the TW close and the US open lands in the NEXT day's TW-close
#     fixing. So if the FX series is TW-CLOSE, corr(spread_t,
#     FX-change_{t+1}) is materially NEGATIVE (TWD appreciates
#     overnight -> ADR up in USD, stale-FX fair unchanged -> spread
#     positive; next fixing prints the drop). If the series is truly
#     US-OPEN concurrent, that move is already inside FX-change_t and
#     BOTH correlations sit near zero.
_fx_chg_t = df['TWD (Last)'].pct_change()
_fx_next_chg = _fx_chg_t.shift(-1)
_fx_flat_frac = float((_fx_chg_t.dropna() == 0).mean())
_c_next = _sb_chk.corr(_fx_next_chg)
_c_same = _sb_chk.corr(_fx_chg_t)
print(f"\n  [D2][F1] FX-source behaviour test on {FX_LBL}:")
print(f"    unchanged d/d: {_fx_flat_frac*100:.1f}% of days | "
      f"corr(spread, FX chg same-day): {_c_same:+.3f} | "
      f"corr(spread, FX chg next-day): {_c_next:+.3f}")
if _fx_flat_frac > 0.10:
    print("    -> VERDICT: the fixing is NOT updating on many days — the code")
    print("       is stale/dead. Confirm the snap time on BFIX <GO> and check")
    print("       the ticker's last-update timestamp on DES; a live NDF-based")
    print("       fixing should print a fresh value every business day.")
elif _c_next < -0.15 and abs(_c_next) > abs(_c_same):
    print("    -> VERDICT: the series BEHAVES like a TW-CLOSE fixing (the")
    print("       spread predicts the NEXT fixing change). Whatever the ticker")
    print("       name says, this is not US-open-concurrent FX. Fix: find the")
    print("       true 13:30/14:30 UTC code on BFIX <GO> (check its history is")
    print("       actually populated at those times), or snapshot USDTWD BGN")
    print("       intraday in the same capture job as the futures files.")
elif abs(_c_next) <= 0.15:
    print("    -> VERDICT: consistent with US-open-concurrent (or FX simply is")
    print("       not a material spread driver in this sample).")
else:
    print("    -> unexpected sign: check the quote convention (TWD per USD?)")
    print("       before anything else.")
# ============================================================
# [HK-H2] THE ENTRY FLOOR — RESIDUAL, NOT FX NOISE.
# ============================================================
# In the Taiwan book the floor under MIN_ENTRY_DEV_BPS is FX staleness:
# the fair carries yesterday-afternoon USDTWD, so the overnight TWD move
# is pure measurement noise in the signal and 2x its sigma is a fair
# floor. Neither half of that applies here:
#   * USDHKD is PEGGED — the FX contribution is ~nil (proved, not
#     assumed, by the [P1]/[D2][F1] diagnostics above);
#   * the real floor is the part of the overnight move the INDEX HEDGE
#     CANNOT SEE: resid = y - beta_{t-1} x g_t, i.e. the name's
#     idiosyncratic overnight return. It is measured out-of-sample
#     (yesterday's beta), so it is the honest number.
# CRITICAL DIFFERENCE, and the reason the TW "2x" convention must NOT be
# copied blindly: FX staleness is measurement error and reverts by
# construction; this residual is REAL NEWS about the company, and the
# HK open may ratify it rather than revert it. How much of it is
# tradable is exactly what the [HK-1A] convergence study answers. Until
# that study is run, treat the multiplier as UNKNOWN and lean on the
# [S1] cost-aware floor, which is the binding one anyway at these
# spreads.
_resid = (df['beta_resid'] if 'beta_resid' in df.columns
          else pd.Series(np.nan, index=df.index))
_resid_bps = float(_resid.std() * 1e4) if _resid.notna().sum() > 30 else float('nan')
_hedge_r2 = float(np.nanmean(df['beta_r2'])) if 'beta_r2' in df.columns else float('nan')
_raw_on_bps = float((df['TSM US (Close)'] * df['FX for Fair'] / ADR_RATIO
                     / df['2330 TT (Close)'] - 1.0).std() * 1e4)
_dev_raw = (df['Spread (Signal)']
            - df['Spread (Signal)'].rolling(30, min_periods=10).mean().shift(1))
_dev_sigma_bps = float((_dev_raw if SIGNAL_MODE == 'premium'      # [Y1] already bps
                        else _dev_raw / df['ADR Ref Px'] * 10000).std())
_fx_on_sigma = float(df['TWD (Last)'].pct_change().std())
kv_table(
    '[HK-H2] WHAT SETS THE ENTRY FLOOR',
    [('unhedged overnight sigma', f"{_raw_on_bps:,.0f} bps",
      'the whole HK-close -> US-close move of the parity gap'),
     ('hedge R2 [HKB]', f"{_hedge_r2:.2f}" if np.isfinite(_hedge_r2) else '—',
      'share of that variance the index hedge removes'),
     ('RESIDUAL sigma (the floor)',
      f"{_resid_bps:,.0f} bps" if np.isfinite(_resid_bps) else '—',
      'idiosyncratic, out-of-sample (yesterday\'s beta) — what the hedge '
      'cannot see'),
     ('signal deviation sigma', f"{_dev_sigma_bps:,.0f} bps",
      'the object the z-score trades'),
     ('FX contribution', f"{_fx_on_sigma*1e4:,.0f} bps",
      'pegged — should be negligible; if not, check the quote convention'),
     ('MIN_ENTRY_DEV_BPS now', f"{MIN_ENTRY_DEV_BPS:,.0f} bps",
      'set it from the residual ONCE [HK-1A] says how much of the '
      'residual reverts — do NOT default to 2x as the TW book does')],
    note='The Taiwan floor is measurement error. This one is real news '
         'that may or may not revert, so its multiplier is an empirical '
         'question, not a convention.')
if np.isfinite(_resid_bps) and _dev_sigma_bps > 0:
    sc('WARN' if MIN_ENTRY_DEV_BPS == 0 else 'INFO', 'entry floor [HK-H2]',
       f"residual {_resid_bps:.0f}bps vs deviation sigma "
       f"{_dev_sigma_bps:.0f}bps; floor currently {MIN_ENTRY_DEV_BPS:.0f}")
# ============================================================
# [HK2] THE LAST HOUR NOBODY CAN SEE.
# ============================================================
# The HTI T+1 session ends 03:00 HKT = 19:00 UTC. The US close is
# 20:00 UTC (summer) / 21:00 (winter). So the index information in the
# fair price is 1-2 HOURS OLD at the moment the ADR prints, and the
# hedge is marked off that same frozen print. Two consequences, both
# real and both mean-zero rather than directional:
#   (a) SIGNAL: part of what looks like a premium deviation is simply
#       index movement after 19:00 UTC that the fair never saw;
#   (b) HEDGE: the fill is worked into the T+1 close, so entry and
#       exit each carry that window unhedged.
# Best available estimate without an extra capture: the ETF proxy
# residual from [HKP] bounds (a)+(b) together, since KTEC/KWEB trade
# through the whole US session. A dedicated 19:55 UTC index-proxy snap
# would separate them; until then the bound is what we have.
if _HKP_FIT is not None:
    _lbl_f, _a_f, _b_f, _r2_f, _sig_f, _n_f = _HKP_FIT
    kv_table(
        '[HK2] STALENESS OF THE HEDGE PRINT',
        [('T+1 session ends', '03:00 HKT = 19:00 UTC', 'last tradable index print'),
         ('US close', '20:00 UTC summer / 21:00 winter',
          'when the ADR leg fills — 1h / 2h later'),
         ('proxy-residual sigma', f"{_sig_f:,.0f} bps",
          f'ETF({_lbl_f}) vs real snap gap, {_n_f} overlap rows — an UPPER '
          f'bound on staleness + tracking'),
         ('proxy fit R2', f"{_r2_f:.2f}", 'how well the ETF explains the gap'),
         ('hedge timing', HEDGE_TIMING,
          "mode 1 works the hedge into the 03:00 HKT close (this window "
          "unhedged both ends); modes 2/3 switch to the stock at the HK "
          "open — see [HKT]")],
        note="us_etf hedge mode removes this entirely (it fills at the same "
             "MOC as the ADR) — that is what [HK1] is for.")
else:
    _inp('[HK2] staleness bound', 'not measurable yet',
         'needs real HTI snaps overlapping the ETF series; until then the '
         '1-2h window is a known unquantified noise term', level='warn')

# ------------------------------------------------------------
# [25] DATA-COMPLETENESS GATE
# ------------------------------------------------------------
# A trade may only be entered on a day where EVERY required input is
# present and sane. After the inner merges this should always hold;
# this gate is the explicit guarantee (and drops anything that slips
# through, with a report).
_req_pos_cols = [c for c in df.columns if c in (
    'TSM US (Open)', 'TSM US (Close)', '2330 TT (Close)', 'TWD (Last)',
    'Fut_2130', 'Fut_1330', 'Fair Price', 'Hedge Idx', 'Exec Px')]
_valid = np.ones(len(df), dtype=bool)
for _c in _req_pos_cols:
    _v = pd.to_numeric(df[_c], errors='coerce')
    _valid &= np.isfinite(_v.values) & (_v.values > 0)
if (~_valid).any():
    print(f"[QC] Dropping {int((~_valid).sum())} rows with missing/invalid "
          f"required inputs: {df.loc[~_valid, 'Date'].tolist()[:10]}")
    df = df[_valid].reset_index(drop=True)
# Calendar-gap report: long holes in the aligned calendar (holidays,
# dropped rows). Entries are BLOCKED inside the backtest when the next
# data row is more than MAX_ENTRY_GAP_DAYS away — you cannot manage a
# position through a hole in the data.
_gaps = df['Date_dt'].diff().dt.days
_big = df.loc[_gaps > MAX_ENTRY_GAP_DAYS, 'Date']
if len(_big):
    print(f"[QC] {len(_big)} calendar gaps > {MAX_ENTRY_GAP_DAYS}cd in the "
          f"aligned data (entries blocked on the eve of each), largest around: "
          f"{df.loc[_gaps.nlargest(3).index, 'Date'].tolist()}")
print(f"[QC] Data: {df['Date'].iloc[0]} to {df['Date'].iloc[-1]} "
      f"({len(df)} aligned trading days) | Avg beta: {df['beta'].mean():.2f}")
# ============================================================
# COMPUTE RETURNS & ROLLING VOLATILITY
# ============================================================
# (K fallbacks are defined in the CONFIG block at the top)
df['ret_TSM'] = np.log(df['TSM US (Close)'] / df['TSM US (Close)'].shift(1))
df['k_fut'] = df['ret_fut_daily'].rolling(20, min_periods=10).std() * 10000
df['k_adr'] = df['ret_TSM'].rolling(20, min_periods=10).std() * 10000
df['k_fut'] = df['k_fut'].fillna(K_FUT_FALLBACK)
df['k_adr'] = df['k_adr'].fillna(K_ADR_FALLBACK)
# ============================================================
# COST MODEL v14 — PER-LEG FEES + 10-MIN WORKED EXECUTION [C1][C3][C5]
# ============================================================
# One-way cost per leg = half-spread + sqrt-law impact on the 10-min
# execution window (you WORK the order over EXEC_WINDOW_MIN, you do
# not dump it in one clip):
#     impact_bps = IMPACT_ETA * k_daily * sqrt(window/390)
#                             * sqrt(leg_notional / window_volume)
# Fees are per leg, per direction (IN/OUT), on that leg's notional.
# FX: the NDF half-spread is crossed twice (hedge on + hedge off) on
# the futures-leg notional — a genuinely TWO-WAY spread cost.
_TRADING_DAY_MIN = 390.0
def _window_params():
    """Half-spreads, per-SIDE book depth/replenishment, window volume
    AND window length for the configured execution time. [M2] The
    close window is longer (night session runs to 05:00 Taipei after
    the ADR MOC), which is how the thin night-tail book still clears
    the futures leg without impact."""
    if EXEC_TIMING == 'open':
        return (ADR_HALF_SPREAD_OPEN_BPS, FUT_HALF_SPREAD_OPEN_BPS,
                ADR_WINDOW_VOL_OPEN_USD, FUT_WINDOW_VOL_OPEN_USD,
                FUT_L1_BID_OPEN, FUT_L1_ASK_OPEN, FUT_REPLENISH_OPEN,
                EXEC_WINDOW_MIN)
    return (ADR_HALF_SPREAD_CLOSE_BPS, FUT_HALF_SPREAD_CLOSE_BPS,
            ADR_WINDOW_VOL_CLOSE_USD, FUT_WINDOW_VOL_CLOSE_USD,
            FUT_L1_BID_CLOSE, FUT_L1_ASK_CLOSE, FUT_REPLENISH_CLOSE,
            EXEC_WINDOW_CLOSE_MIN)
def _sqrt_impact(k_daily, leg_notional, window_vol, window_min):
    """v14 parametric fallback: sqrt law on the execution window."""
    return (IMPACT_ETA * k_daily * np.sqrt(window_min / _TRADING_DAY_MIN)
            * np.sqrt(leg_notional / window_vol))
def compute_exec_cost(notional, is_stress, k_adr, k_fut, beta,
                      cost_mult=1.0, fut_px_twd=2466.0, fx=32.4):
    """Round-trip execution cost ($). Futures leg sized beta x notional.
    fut_px_twd / fx: that day's SSF price (TWD) and USDTWD — the
    contract value converts through FX (contract_usd =
    FUT_CONTRACT_SHARES x TWD price / FX), nothing hard-coded.
    COST_MODEL='book' [E3][F2], SIDE-AWARE: the SSF book is
    asymmetric (bid 9-14 vs ask 20-72 in the screenshots), and every
    round trip crosses EACH side exactly once — long spread sells
    futures at entry (bid side) and buys back at exit (ask side);
    short spread is the mirror. So the two futures one-ways are
    tested against the BID and ASK capacities separately; whichever
    side is too thin pushes THAT one-way onto the sqrt fallback. The
    total is therefore direction-independent under a static book.
    cost_mult scales SPREAD + IMPACT only; fees and the FX spread are
    contractual and are NOT scaled."""
    mult = STRESS_MULT if is_stress else 1.0
    fut_notional = beta * notional
    (adr_hs, fut_hs, adr_wv, fut_wv,
     fut_bid_l1, fut_ask_l1, fut_refill, win_min) = _window_params()
    contract_usd = FUT_CONTRACT_SHARES * fut_px_twd / fx
    if COST_MODEL == 'book':
        q_contracts = fut_notional / contract_usd
        cap_bid = fut_bid_l1 + fut_refill * win_min
        cap_ask = fut_ask_l1 + fut_refill * win_min
        _fut_impacts = []
        for _cap in (cap_bid, cap_ask):     # one one-way per side
            if q_contracts <= _cap:
                _fut_impacts.append(BOOK_BUFFER_FUT_BPS)
            else:
                _fut_impacts.append(max(BOOK_BUFFER_FUT_BPS,
                                        _sqrt_impact(k_fut, fut_notional,
                                                     fut_wv, win_min)))
        fut_two_way_impact = sum(_fut_impacts)
        if notional <= PARTICIPATION_WARN * adr_wv:
            adr_two_way_impact = 2 * BOOK_BUFFER_ADR_BPS
        else:
            adr_two_way_impact = 2 * max(BOOK_BUFFER_ADR_BPS,
                                         _sqrt_impact(k_adr, notional,
                                                      adr_wv, win_min))
    else:
        fut_two_way_impact = 2 * _sqrt_impact(k_fut, fut_notional, fut_wv, win_min)
        adr_two_way_impact = 2 * _sqrt_impact(k_adr, notional, adr_wv, win_min)
    adr_two_way_bps = (2 * adr_hs + adr_two_way_impact) * mult
    fut_two_way_bps = (2 * fut_hs + fut_two_way_impact) * mult
    spread_impact_cost = (adr_two_way_bps / 10000 * notional
                          + fut_two_way_bps / 10000 * fut_notional)
    spread_impact_cost *= cost_mult
    # [C1] per-leg, per-direction fees — ONE-SIDED each: IN charged
    # ONCE at entry, OUT charged ONCE at exit, on that leg's notional.
    fee_cost = ((ADR_FEE_IN_BPS + ADR_FEE_OUT_BPS) / 10000 * notional
                + (FUT_FEE_IN_BPS + FUT_FEE_OUT_BPS) / 10000 * fut_notional)
    # [HKC] STAMP DUTY. HK charges 10 bps PER SIDE on STOCK transfers.
    # Phase 1 never trades the HK stock leg — the ADR is US-listed (no
    # stamp) and index futures / ETFs are exempt — so HEDGE_STAMP_BPS
    # is 0 for every current mode and this term is structurally zero.
    # It exists so the Phase-2 conversion / HK-leg exit can price
    # itself with ORD_STAMP_BPS + ORD_LEVIES_BPS on the ordinary leg.
    if HEDGE_STAMP_BPS:
        fee_cost += 2 * HEDGE_STAMP_BPS / 10000 * fut_notional
    # [C3][O1] FX conversion cost, both ways, on the futures-leg
    # notional: NDF spread if hedging immediately, onshore-spot spread
    # (incl. bank markup) if converting at the next TW open.
    # [HKC] a USD-denominated hedge (us_etf) has NO conversion leg.
    _fx_half = (FX_SPOT_HALF_SPREAD_BPS if FX_EXEC_MODE == 'spot_next_open'
                else FX_NDF_HALF_SPREAD_BPS)
    fx_cost = 2 * _fx_half / 10000 * fut_notional
    if HEDGE_MODE == 'us_etf':
        fx_cost = 0.0
    dollar_cost = spread_impact_cost + fee_cost + fx_cost
    total_bps = dollar_cost / notional * 10000
    return dollar_cost, total_bps
def report_participation(notional, fut_px_twd, fx):
    """[C5][E3][F2] Sanity print with EXPLICIT units and PER-SIDE
    book capacity (the bid and ask are NOT the same size)."""
    (adr_hs, fut_hs, adr_wv, fut_wv,
     fut_bid_l1, fut_ask_l1, fut_refill, win_min) = _window_params()
    contract_usd = FUT_CONTRACT_SHARES * fut_px_twd / fx
    n_c = notional / contract_usd
    cap_bid = fut_bid_l1 + fut_refill * win_min
    cap_ask = fut_ask_l1 + fut_refill * win_min
    print(f"[COST] 1 {HEDGE_LBL} contract = {FUT_CONTRACT_SHARES:,} x index "
          f"{fut_px_twd:,.0f} = {LOCAL_CCY} "
          f"{FUT_CONTRACT_SHARES * fut_px_twd / 1e6:.2f}M "
          f"/ {fx:.2f} = US${contract_usd / 1e3:,.0f}k")
    print(f"[COST] {win_min}-min worked execution | {HEDGE_LBL} leg "
          f"{n_c:.1f} contracts vs supply: BID side ~{cap_bid:.0f} "
          f"(L1 {fut_bid_l1} + {fut_refill}/min), ASK side ~{cap_ask:.0f} "
          f"(L1 {fut_ask_l1} + {fut_refill}/min) | ADR leg "
          f"{notional / adr_wv * 100:.2f}% of ${adr_wv / 1e6:.0f}M window")
    if n_c > min(cap_bid, cap_ask):
        print(f"[COST] WARNING: {HEDGE_LBL} leg exceeds the THIN side's supply — "
              f"sqrt fallback engaged on that one-way; extend the window or cut size")
    if notional > PARTICIPATION_WARN * adr_wv:
        print(f"[COST] WARNING: ADR leg above {PARTICIPATION_WARN*100:.0f}% "
              f"window participation — sqrt fallback engaged")
# (strategy parameters are defined in the CONFIG block at the top)
# ============================================================
# VAR CALCULATION FUNCTION
# ============================================================
def compute_var_metrics(daily_equity, first_day):
    equity_active = daily_equity[first_day:]
    daily_pnl = np.diff(equity_active)
    daily_pnl_active = daily_pnl[daily_pnl != 0]
    if len(daily_pnl_active) < 10:
        return {'var_95': 0.0, 'var_99': 0.0, 'cvar_95': 0.0, 'cvar_99': 0.0,
                'worst_day': 0.0, 'n_active_days': len(daily_pnl_active)}
    var_95 = np.percentile(daily_pnl_active, 5)
    var_99 = np.percentile(daily_pnl_active, 1)
    cvar_95 = daily_pnl_active[daily_pnl_active <= var_95].mean() if (daily_pnl_active <= var_95).any() else var_95
    cvar_99 = daily_pnl_active[daily_pnl_active <= var_99].mean() if (daily_pnl_active <= var_99).any() else var_99
    return {'var_95': var_95, 'var_99': var_99, 'cvar_95': cvar_95, 'cvar_99': cvar_99,
            'worst_day': daily_pnl_active.min(), 'n_active_days': len(daily_pnl_active)}
# ============================================================
# [11] SIGNAL-STATS PRECOMPUTATION & CACHE
# ============================================================
# The rolling ADF p-value and gamma (AR(1) slope) depend ONLY on the
# signal-spread series and ADF_WINDOW — not on n_zscore, threshold,
# cost multipliers, or fill lag. v4 recomputed adfuller inside the
# daily loop of every backtest run (~40,000+ calls across the grid and
# robustness reruns, a ~20-25x redundancy). v5 computes each unique
# signal series ONCE and caches it; every grid cell and rerun reuses
# the same arrays. Results are bit-identical to per-day recomputation.
_SIGNAL_STATS_CACHE = {}
def precompute_signal_stats(spreads_signal, adf_window):
    n = len(spreads_signal)
    adf_p = np.full(n, 1.0)
    gamma = np.zeros(n)
    for t in range(adf_window, n):
        w = spreads_signal[t - adf_window: t]
        try:
            adf_p[t] = adfuller(w, maxlag=int(np.sqrt(adf_window)))[1]
        except Exception:
            adf_p[t] = 1.0
        d = w - w.mean()
        lagv = d[:-1]
        delta = np.diff(w)
        den = np.dot(lagv, lagv)
        gamma[t] = np.dot(delta, lagv) / den if den > 0 else 0.0
    return adf_p, gamma
def get_signal_stats(spreads_signal):
    _w = gate_window()          # [Q3]
    key = (spreads_signal.tobytes(), _w)
    if key not in _SIGNAL_STATS_CACHE:
        _SIGNAL_STATS_CACHE[key] = precompute_signal_stats(spreads_signal, _w)
    return _SIGNAL_STATS_CACHE[key]
# ============================================================
# BACKTEST FUNCTION
# ============================================================
# PnL convention  [22]:
#   You trade BOTH legs at entry and exit: the ADR and the futures.
#   pnl_mode='two_leg' (DEFAULT — matches the actual trade):
#     ADR leg     = position x (ADR_exit - ADR_entry) x shares
#     Futures leg = -position x beta_entry x NOTIONAL
#                   x (Fut_exit / Fut_entry - 1)
#     using the actual US-open futures snapshot (Fut_2130) for the
#     futures fills. Daily marks, VaR, MaxDD and Sharpe therefore
#     include the REAL basis risk between the single stock and the
#     hedge over the holding period.
#   pnl_mode='convergence' (the old v1-v7 convention, kept for
#     comparison): pnl = position x (exit_spread - entry_spread) x
#     shares, i.e. it implicitly assumes the hedge tracks the stock's
#     fair value perfectly — correct in expectation, but it HIDES the
#     stock-vs-hedge idiosyncratic noise during the hold.
#   Long spread  (position=+1): buy TSM ADR, sell 1x notional TSMC SSF.
#   Short spread (position=-1): sell TSM ADR, buy 1x notional TSMC SSF.
#   Funding charged only when LONG the ADR; borrow only when SHORT.
#   Futures-leg PnL is treated as USD on the entry notional (the TWD
#   conversion effect on the PnL amount is second-order and ignored;
#   the notional-level TWD exposure remains unmodeled, see header).
#   cost_mult : scales execution cost (sensitivity analysis, [4])
#   lag_exec  : False = same-bar fills; True = ALL fills slip to t+1;
#                'entry_only' = only ENTRIES slip to t+1, exits fill
#                same-bar — decomposes the lag decay into the entry
#                side vs the exit side ([G4])
def run_backtest(df, n_zscore, threshold, track_adf=False,
                 cost_mult=1.0, lag_exec=False, pnl_mode='two_leg'):
    spreads_signal = df['Spread (Signal)'].values
    spreads_exec = df['Spread (Exec)'].values
    dates_dt = df['Date_dt'].values
    k_adr_arr = df['k_adr'].values
    k_fut_arr = df['k_fut'].values
    # [HKS] hedge-leg bindings go through the generic columns. For TW
    # they hold the SAME VALUES as the old hard-wired ones (beta_hedge =
    # beta = 1.0, Hedge Px = Fut_2130, hedge_fx = TWD) — bit-identical.
    beta_arr = (df['beta_hedge'].values if 'beta_hedge' in df.columns
                else df['beta'].values)
    exec_px_arr = df['Exec Px'].values
    fut_arr = (df['Hedge Px'].values if 'Hedge Px' in df.columns
               else df['Fut_2130'].values)  # hedge fills (was Fut_2130)
    hedge_arr = df['Hedge Idx'].values  # [24][26] roll-safe TR spine
    adr_close_arr = df['TSM US (Close)'].values
    fx_arr = (df['TWD (Last)'].values if 'TWD (Last)' in df.columns
              else np.full(len(df), 32.4))   # [E2] contract-value FX
    # [HKS] FX the HEDGE LEG converts through: the local currency for a
    # futures hedge (TW: = fx_arr exactly), 1.0 for a USD hedge (us_etf)
    hfx_arr = (df['hedge_fx'].values.astype(float)
               if 'hedge_fx' in df.columns else fx_arr)
    earn_arr = (df['earnings_block'].values if 'earnings_block' in df.columns
                else np.zeros(len(df), dtype=bool))   # [HKE]
    gprox_arr = (df['gap_is_proxy'].values if 'gap_is_proxy' in df.columns
                 else np.zeros(len(df), dtype=bool))  # [HKP] proxy-row flag
    div_hedge_arr = (df['div_ret_hedge'].values if 'div_ret_hedge' in df.columns
                     else np.zeros(len(df)))   # [T3]
    suspect_arr = (df['gap_suspect'].values if 'gap_suspect' in df.columns
                   else np.zeros(len(df), dtype=bool))   # [J5]
    preex_arr = (df['pre_exdate'].values if 'pre_exdate' in df.columns
                 else np.zeros(len(df), dtype=bool))     # [S5]
    fund_arr = (df['funding_rate'].values if 'funding_rate' in df.columns
                else np.full(len(df), FUNDING_RATE_ANN))   # [S2] daily SOFR
    div_adr_arr = df['div_ret_adr'].values if 'div_ret_adr' in df.columns \
        else np.zeros(len(df))
    _di = pd.DatetimeIndex(dates_dt)
    ym_arr = (df['contract_id'].values if 'contract_id' in df.columns
              else (_di.year * 12 + _di.month).values)   # [I3]
    # [R5][V2][HKS] neither dividend treatment applies to an index hedge:
    # no margin-account cash (FUT_DIV_CASH=False) and no price-path
    # rescaling (HEDGE_DIV_ADJ=False), so the futures path is used raw.
    # _divf stays flat and is kept only so _hedge_growth reads the same
    # in both books.
    _divf = np.ones(len(df))
    fut_adj_arr = fut_arr * _divf
    # [R7] fold detected breaks into the contract id so _hedge_growth
    # splices across them exactly as it does at a genuine roll
    if 'contract_break' in df.columns and df['contract_break'].any():
        ym_arr = ym_arr + np.cumsum(df['contract_break'].values.astype(int)) * 1000
    def _hedge_growth(t, e_fut_raw, e_ym):
        """[27][I3][J1] Hybrid hedge valuation, CONTRACT-aware. While
        the file still quotes the ENTRY's contract (same contract_id;
        under the confirmed next-month convention that means the same
        calendar month), raw prices are the actual fills (exact). Once
        the file has rolled to the next contract, growth is spliced:
        exact raw up to the last same-contract row, TR spine [26]
        after. Under month_start the REAL position has NOT rolled (its
        contract is weeks from expiry) — the splice is only a change
        of marking source, so no roll cost; under expiry_3rd_wed the
        position genuinely rolls and the cost is charged at exit."""
        _e_adj = e_fut_raw * _divf[entry_day]   # [R5] same adjusted path
        if ym_arr[t] == e_ym:
            return fut_adj_arr[t] / _e_adj
        b = t
        while ym_arr[b] != e_ym:
            b -= 1
        return (fut_adj_arr[b] / _e_adj) * (hedge_arr[t] / hedge_arr[b])
    _dd = np.diff(dates_dt) / np.timedelta64(1, 'D')
    gap_next = np.r_[_dd.astype(int), 999]  # [25] days to the next data row
    n_days = len(df)
    first_day = first_tradable_row(n_zscore)   # [Q3][X3]
    trades = []
    adf_log = []
    daily_equity = np.zeros(n_days)
    cumulative_realized = 0.0
    position = 0
    entry_spread = 0.0
    entry_price = 0.0
    entry_fut_raw = 0.0
    entry_ym = 0
    entry_beta = 1.0
    entry_day = 0
    div_accrued = 0.0
    fut_div_cash = 0.0   # [T3]
    trade_notional = NOTIONAL   # [D3] per-trade size (scaled at entry)
    size_mult = 1.0
    n_contracts = 0
    mae_bps = 0.0   # [H5]
    mfe_bps = 0.0   # [R8][S2][X5] max FAVOURABLE excursion (was assigned twice)
    capped_notional_events = 0      # [M6]
    capped_notional_usd = 0.0
    # [11] cached ADF/gamma; [11] vectorized z-score inputs (ddof=0 to
    # match the previous numpy .std(); shift(1) = window ends at t-1,
    # identical to the old spreads_signal[t-n:t] slice).
    # [Z1] build the series the ADF/gamma actually test: the de-trended
    # deviation (default) or the raw level (legacy)
    if GATE_MODE == 'adf_level':
        _test_ser = spreads_signal
    else:   # deviation object for adf_deviation AND halflife_drift
        _lvl = pd.Series(spreads_signal)
        _test_ser = (_lvl - _lvl.rolling(ADF_DETREND_N).mean().shift(1)
                     ).fillna(0.0).values
    adf_p_arr, gamma_arr = get_signal_stats(_test_ser)
    _sig = pd.Series(spreads_signal)
    zmu_arr = _sig.rolling(n_zscore).mean().shift(1).values
    zsd_arr = _sig.rolling(n_zscore).std(ddof=0).shift(1).values
    # [Z4] trend-free noise scale for the drift filter: the std of DAILY
    # CHANGES. A persistent trend shifts the MEAN of changes, not their
    # std — so this denominator does not get inflated by the very trend
    # we are trying to detect (zsd does, which made the v-Z3 drift
    # ratio self-defeating).
    chgsd_arr = _sig.diff().rolling(n_zscore).std(ddof=0).shift(1).values
    for t in range(first_day, n_days):
        adf_pval = adf_p_arr[t]
        if ADF_EXIT_POLICY == 'ignore' or GATE_MODE == 'off':
            system_on = True
        elif GATE_MODE == 'halflife_drift':                       # [Z3]
            _g = gamma_arr[t]
            _hl_ok = (np.isfinite(_g) and _g < 0
                      and np.log(0.5) / np.log(1.0 + max(_g, -0.999))
                      <= HL_MAX_DAYS)
            _drift_ok = True
            if (t >= 5 and np.isfinite(zmu_arr[t]) and np.isfinite(zmu_arr[t - 5])
                    and np.isfinite(chgsd_arr[t]) and chgsd_arr[t] > 0):
                # [Z4] 5-row mean shift vs the sqrt(5)-scaled daily-change
                # sigma: >DRIFT_MAX_SIGMA means the mean itself is moving
                # faster than noise explains -> a repricing, stand aside
                _drift_ok = (abs(zmu_arr[t] - zmu_arr[t - 5])
                             / (chgsd_arr[t] * np.sqrt(5.0))
                             <= DRIFT_MAX_SIGMA)
            system_on = _hl_ok and _drift_ok
        else:                                                      # adf_* modes
            system_on = (adf_pval < ADF_PVALUE)
        gamma_coeff = gamma_arr[t]
        if track_adf:
            adf_log.append({'day': t, 'date': df['Date'].iloc[t], 'adf_pval': adf_pval,
                            'system_on': system_on, 'gamma': gamma_coeff})
        mu = zmu_arr[t]
        sigma = zsd_arr[t]
        z_today = ((spreads_signal[t] - mu) / sigma
                   if (not np.isnan(sigma)) and sigma > 0 else 0.0)
        if position == 0:
            # [H2] deviation gate: |spread - rolling mean| must clear
            # MIN_ENTRY_DEV_BPS of ADR price, so the FX-stale noise
            # floor alone cannot trigger an entry (0 = gate off)
            _dev_bps_ok = True
            if MIN_ENTRY_DEV_BPS > 0 and np.isfinite(mu):
                _dev_now = abs(spreads_signal[t] - mu)          # [Y2] mode-aware
                if SIGNAL_MODE != 'premium':                    # dollar -> convert to bps
                    _dev_now = _dev_now / exec_px_arr[t] * 10000
                _dev_bps_ok = _dev_now >= MIN_ENTRY_DEV_BPS
            if (system_on and abs(z_today) > threshold and _dev_bps_ok
                    and not suspect_arr[t]              # [J5] no entry on a
                                                        # contract-mismatch row
                    and not preex_arr[t]                # [S5] not into an ex-date
                    and not earn_arr[t]                 # [HKE] not into earnings
                    and gap_next[t] <= MAX_ENTRY_GAP_DAYS):  # [25][H2]
                if lag_exec and t + 1 >= n_days:
                    # [D4] lag mode at the last row: no tomorrow to fill
                    # on — SKIP the entry (v14 silently filled same-day)
                    daily_equity[t] = cumulative_realized
                    continue
                _want = -1 if z_today > threshold else 1
                if ((DIRECTION_FILTER == 'long_only' and _want == -1)
                        or (DIRECTION_FILTER == 'short_only' and _want == 1)):
                    daily_equity[t] = cumulative_realized   # [J6] skip
                    continue
                fill_t = t + 1 if lag_exec else t   # True OR 'entry_only' both slip entries
                position = _want
                # [D3] size with the signal: bare-threshold entry = 1.0x,
                # richer dislocation up to SIZE_CAP x. Costs, carry and
                # both legs all scale off trade_notional below.
                if SIZING_MODE == 'z_scaled':
                    size_mult = min(abs(z_today) / threshold, SIZE_CAP)
                else:
                    size_mult = 1.0
                trade_notional = NOTIONAL * size_mult
                # [M6] CAPACITY CAP — the futures leg cannot exceed a
                # fraction of the book that is actually there. Uses the
                # same book parameters the cost model uses, so sizing
                # and costing agree instead of the cost model silently
                # absorbing an impossible clip via the sqrt fallback.
                if MAX_BOOK_PARTICIPATION > 0 and HEDGE_MODE != 'none':
                    # [HKS] no hedge leg -> no futures book to cap against
                    _win = (EXEC_WINDOW_CLOSE_MIN if EXEC_TIMING == 'close'
                            else EXEC_WINDOW_MIN)
                    # [R4] DIRECTION-AWARE: a LONG spread SELLS the SSF and
                    # therefore consumes the BID; a SHORT spread BUYS it and
                    # consumes the ASK. Using min(bid, ask) charged every
                    # trade the thinner side and under-sized the whole book.
                    if EXEC_TIMING == 'close':
                        _l1 = (FUT_L1_BID_CLOSE if position == 1
                               else FUT_L1_ASK_CLOSE)
                    else:
                        _l1 = (FUT_L1_BID_OPEN if position == 1
                               else FUT_L1_ASK_OPEN)
                    _rep = (FUT_REPLENISH_CLOSE if EXEC_TIMING == 'close'
                            else FUT_REPLENISH_OPEN)
                    _supply = _l1 + _rep * _win
                    _c_usd0 = (FUT_CONTRACT_SHARES * fut_arr[fill_t]
                               / hfx_arr[fill_t])   # [HKS] hedge-leg FX
                    # [HKC] the book constrains the HEDGE leg (beta x
                    # notional), so convert the contract cap into the
                    # TRADE notional it implies before comparing.
                    _cap_hedge = MAX_BOOK_PARTICIPATION * _supply * _c_usd0
                    _beta_cap = (float(beta_arr[fill_t])
                                 if np.isfinite(beta_arr[fill_t]) else 0.0)
                    _cap_usd = (_cap_hedge / _beta_cap if _beta_cap > 0
                                else float('inf'))
                    if np.isfinite(_cap_usd) and _cap_usd > 0 \
                            and trade_notional > _cap_usd:
                        capped_notional_events += 1
                        capped_notional_usd += trade_notional - _cap_usd
                        trade_notional = _cap_usd
                        size_mult = trade_notional / NOTIONAL
                # [E2][HKC] SNAP TO WHOLE CONTRACTS — ON THE HEDGE LEG.
                # This is a REAL difference from the Taiwan book, not a
                # cosmetic one. There beta == 1, so the hedge notional IS
                # the trade notional and snapping the trade to whole SSF
                # contracts leaves the hedge exactly N contracts. Here the
                # hedge is beta x notional with beta ~0.7, so snapping the
                # TRADE to whole contracts would leave the HEDGE at 0.7N —
                # a fractional number of index futures, which cannot be
                # traded. You would silently be under- or over-hedged by up
                # to half a contract (~US$14k) on every trade.
                # So: choose the whole number of contracts the HEDGE needs,
                # then back out the trade notional that hedge exactly
                # covers. The ADR clip moves a little; the hedge is exact.
                _c_usd = (FUT_CONTRACT_SHARES * fut_arr[fill_t]
                          / hfx_arr[fill_t])   # [HKS] hedge-leg FX
                _beta_h = float(beta_arr[fill_t]) if np.isfinite(
                    beta_arr[fill_t]) else 0.0
                if ALIGN_TO_CONTRACTS and HEDGE_MODE != 'none' and _beta_h > 0:
                    n_contracts = max(1, int(round(_beta_h * trade_notional
                                                   / _c_usd)))
                    trade_notional = n_contracts * _c_usd / _beta_h
                elif HEDGE_MODE == 'none':
                    n_contracts = 0            # naked: nothing to snap
                else:
                    n_contracts = _beta_h * trade_notional / _c_usd
                entry_spread = spreads_exec[fill_t]
                entry_price = exec_px_arr[fill_t]
                entry_fut_raw = fut_arr[fill_t]
                entry_ym = ym_arr[fill_t]
                div_accrued = 0.0
                fut_div_cash = 0.0   # [T3]
                entry_beta = (beta_arr[fill_t]
                              if not np.isnan(beta_arr[fill_t]) else 1.0)
                entry_day = fill_t
                z_at_entry = z_today   # [Q2] signal strength at entry
                mae_bps = 0.0          # [H5] reset per trade
                mfe_bps = 0.0          # [R8][S2][X5] reset per trade (was twice)
            daily_equity[t] = cumulative_realized
        else:
            if t < entry_day:   # lag mode: fill is tomorrow
                daily_equity[t] = cumulative_realized
                continue
            current_spread = spreads_exec[t]
            shares = trade_notional / entry_price
            # [W1] USD-per-share spread for the convergence-PnL and
            # gamma-exit paths, valid in BOTH signal modes:
            #   dollar : spread already USD/share
            #   premium: spread is bps -> /1e4 x price = USD/share
            if SIGNAL_MODE == 'premium':
                cur_spread_usd = current_spread / 10000.0 * exec_px_arr[t]
                ent_spread_usd = entry_spread / 10000.0 * entry_price
            else:
                cur_spread_usd = current_spread
                ent_spread_usd = entry_spread
            if t > entry_day:   # [26] accrue ADR dividend cash during the hold
                div_accrued += (position * shares
                                * adr_close_arr[t - 1] * div_adr_arr[t])
                # [T3][HKS] no margin-account dividend on an index hedge —
                # fut_div_cash stays 0 and is kept only so the trade
                # record keeps the same shape as the TW book.
            if pnl_mode == 'two_leg':
                adr_leg = (position * (exec_px_arr[t] - entry_price) * shares
                           + div_accrued)
                fut_leg = (-position * entry_beta * trade_notional
                           * (_hedge_growth(t, entry_fut_raw, entry_ym) - 1.0)
                           * (hfx_arr[entry_day] / hfx_arr[t]))   # [HKS]
                fut_leg += fut_div_cash   # [T3] margin-account dividend
                unrealized_pnl = adr_leg + fut_leg
            else:
                unrealized_pnl = position * (cur_spread_usd - ent_spread_usd) * shares
            daily_equity[t] = cumulative_realized + unrealized_pnl
            # [H5] max adverse excursion: worst unrealized point of the
            # hold, in bps of notional. Calibrate HARD_STOP_BPS above
            # the WINNERS' MAE distribution so the stop only cuts
            # trades that never recovered.
            _u_bps = unrealized_pnl / trade_notional * 1e4
            mae_bps = min(mae_bps, _u_bps)
            mfe_bps = max(mfe_bps, _u_bps)   # [S2] max FAVOURABLE excursion
            exit_signal = False
            exit_reason = ''
            calendar_days = (pd.Timestamp(dates_dt[t]) - pd.Timestamp(dates_dt[entry_day])).days
            # EXIT 1: Z crossed zero
            if position == -1 and z_today <= 0:
                exit_signal = True
                exit_reason = 'Z crossed 0'
            elif position == 1 and z_today >= 0:
                exit_signal = True
                exit_reason = 'Z crossed 0'
            # [S2] PROFIT TARGET: bank the gain instead of waiting for z=0
            if not exit_signal and PROFIT_TARGET_BPS > 0 and \
                    _u_bps >= PROFIT_TARGET_BPS:
                exit_signal = True
                exit_reason = f'Profit target {PROFIT_TARGET_BPS}bps'
            # [G6] HARD STOP: two-leg unrealized loss beyond the cap
            if not exit_signal and HARD_STOP_BPS > 0:
                _adr_u = position * (exec_px_arr[t] - entry_price) \
                         * (trade_notional / entry_price)
                _fut_u = (-position * entry_beta * trade_notional
                          * (_hedge_growth(t, entry_fut_raw, entry_ym) - 1.0)
                          * (hfx_arr[entry_day] / hfx_arr[t]))   # [HKS]
                if (_adr_u + _fut_u) / trade_notional * 1e4 < -HARD_STOP_BPS:
                    exit_signal = True
                    exit_reason = f'Hard stop {HARD_STOP_BPS}bps'
            # EXIT 2 [W2]: ADF turn-off flushes the position ONLY under
            # the 'force_exit' policy. Default 'entry_only' leaves exits
            # to z-cross / time-stop / gamma, avoiding on/off churn.
            if ADF_EXIT_POLICY == 'force_exit' and not system_on:
                exit_signal = True
                exit_reason = 'ADF OFF'
            # Position-correct daily carry ([C3] FX spread moved to exec_cost)
            if position == 1:
                daily_carry = trade_notional * (fund_arr[t] / 360)   # [S2]
            else:
                daily_carry = trade_notional * ((BORROW_ANN_BPS / 10000
                                                 - SHORT_REBATE_ANN) / 360)  # [R6]
            # [O2][S2] margin funding, both directions, at row t's SOFR
            # [HKS] futures hedges only; a us_etf hedge posts no margin but
            # carries the CASH position instead: long spread SHORTS the ETF
            # (pays borrow), short spread is LONG the ETF (funds it).
            if _HEDGE_IS_FUT:
                daily_carry += (entry_beta * trade_notional
                                * (margin_ann_bps() / 10000) / 360)   # [T4] flat 24bps
            elif HEDGE_MODE == 'us_etf':
                _h_rate = (ETF_BORROW_ANN_BPS / 10000 if position == 1
                           else fund_arr[t])
                daily_carry += entry_beta * trade_notional * _h_rate / 360
            # [C3][D1][O1][HKS] no FX carry term at all: USDHKD is
            # pegged and deliverable, so the hedge conversion has no
            # forward points to earn or pay. The hurdle is still
            # floored at 0 so a net POSITIVE carry can never
            # manufacture a fake gamma exit.
            daily_carry = max(daily_carry, 0.0)
            # EXIT 3: Gamma-based — tomorrow's expected profit < carry.
            # [13] gamma is the AR(1) slope of the demeaned spread — a
            # discrete OU mean-reversion estimate (implied half-life =
            # ln(0.5)/ln(1+gamma)). Deliberately simple; the refinement
            # here is a clamp at -1: an AR(1) slope below -1 means
            # one-day OVERSHOOT, and using |gamma| > 1 would overstate
            # tomorrow's expected reversion and delay this exit.
            if (not exit_signal and gamma_coeff < 0
                    and (not np.isnan(sigma)) and sigma > 0):
                gamma_eff = max(gamma_coeff, -1.0)
                # [W1] sigma is in the SIGNAL's units (USD in dollar mode,
                # bps in premium mode). Convert the one-step expected
                # move to USD/share before multiplying by shares, else
                # premium mode inflates it ~1e4 x and the exit never
                # fires.
                current_gap = abs(z_today) * sigma
                if SIGNAL_MODE == 'premium':
                    current_gap_usd = current_gap / 10000.0 * exec_px_arr[t]
                else:
                    current_gap_usd = current_gap
                expected_profit_tomorrow = abs(gamma_eff) * current_gap_usd * shares
                # [N1] the "next mark" can be 3+ calendar days away
                # (weekend/holiday) and funding accrues on CALENDAR
                # days — so the hurdle is daily carry x days to the
                # next row, not one day flat (v24 under-fired the
                # gamma exit on every Friday).
                _days_to_next = max(int(gap_next[t]) if gap_next[t] < 999 else 1, 1)
                carry_to_next = daily_carry * _days_to_next
                if expected_profit_tomorrow < carry_to_next:
                    exit_signal = True
                    exit_reason = (f'Gamma exit (profit {expected_profit_tomorrow:.0f} '
                                   f'< carry {carry_to_next:.0f}'
                                   + (f' over {_days_to_next}cd' if _days_to_next > 1 else '')
                                   + ')')
            # [R9] EXIT 3b: profit targets (checked before the time stop
            # so a target that fires on the same row wins the label)
            if not exit_signal and PROFIT_TARGET_BPS > 0 and _u_bps >= PROFIT_TARGET_BPS:
                exit_signal = True
                exit_reason = f'Profit target {PROFIT_TARGET_BPS}bps'
            if (not exit_signal and PROFIT_TARGET_Z > 0
                    and np.isfinite(z_today) and abs(z_today) <= PROFIT_TARGET_Z):
                exit_signal = True
                exit_reason = f'Profit target |z|<={PROFIT_TARGET_Z}'
            # EXIT 4: Time stop (hard safety cap)
            if calendar_days >= TIME_STOP:
                exit_signal = True
                exit_reason = 'Time stop'
            if exit_signal:
                fill_t = (t + 1 if (lag_exec is True and t + 1 < n_days)
                          else t)   # [G4] 'entry_only' exits same-bar
                # [K4] do not FILL on a print we do not trust either: a
                # corrupt futures price at exit books fake PnL just as
                # badly as at entry. Defer by at most one row.
                if suspect_arr[fill_t] and fill_t + 1 < n_days:
                    fill_t += 1
                exit_spread = spreads_exec[fill_t]
                hold_days_trading = fill_t - entry_day
                calendar_days = (pd.Timestamp(dates_dt[fill_t])
                                 - pd.Timestamp(dates_dt[entry_day])).days
                if exit_reason == 'Time stop':
                    exit_reason = f'Time stop (cap {TIME_STOP}cd, held {calendar_days}cd)'
                # [R6] INTEGRITY: a hold longer than TIME_STOP should be
                # impossible (the cap is tested on every visited row).
                # If it ever happens, something deferred the fill — do
                # not let it pass silently.
                # [Y28] measure the tolerance against the ACTUAL spacing into
                # the exit row (a TW/US holiday or a dropped row can carry the
                # hold past the cap with nothing wrong), and if it still trips,
                # print the spacing so it is diagnosable instead of "investigate".
                _prev_row = max(fill_t - 1, entry_day)
                _step_cd = (pd.Timestamp(dates_dt[fill_t])
                            - pd.Timestamp(dates_dt[_prev_row])).days
                if calendar_days > TIME_STOP + max(_step_cd, 1):
                    print(f"[R6] hold {calendar_days}cd > TIME_STOP "
                          f"{TIME_STOP}cd | entered "
                          f"{df['Date'].iloc[entry_day]}, exit "
                          f"{df['Date'].iloc[fill_t]} ({exit_reason}) | the "
                          f"previous aligned row was "
                          f"{df['Date'].iloc[_prev_row]}, {_step_cd}cd "
                          f"earlier — if that step is large the cap simply "
                          f"had no row to fire on (holiday / dropped row), "
                          f"which is expected; if it is 1-3cd the cap logic "
                          f"or a deferred fill needs a look")
                if pnl_mode == 'two_leg':
                    if fill_t > t:   # lag mode: accrue the fill day's dividend
                        div_accrued += (position * shares
                                        * adr_close_arr[fill_t - 1]
                                        * div_adr_arr[fill_t])
                    adr_leg_pnl = (position * (exec_px_arr[fill_t] - entry_price)
                                   * shares + div_accrued)
                    # [Q1] the SSF leg is TWD-denominated. Its return
                    # _hedge_growth-1 is a TWD return; the USD PnL is
                    # that TWD return on a TWD notional, converted back
                    # at the EXIT FX. v26 used entry FX implicitly (a
                    # 1st-order approximation ~4 bps); this makes it
                    # exact by scaling with the FX ratio over the hold.
                    _fx_ratio = hfx_arr[entry_day] / hfx_arr[fill_t]   # [HKS]
                    fut_leg_pnl = (-position * entry_beta * trade_notional
                                   * (_hedge_growth(fill_t, entry_fut_raw,
                                                    entry_ym) - 1.0) * _fx_ratio)
                    fut_leg_pnl += fut_div_cash   # [T3]
                    gross_pnl = adr_leg_pnl + fut_leg_pnl
                else:
                    adr_leg_pnl = np.nan
                    fut_leg_pnl = np.nan
                    if SIGNAL_MODE == 'premium':   # [W1] USD/share
                        _exit_sp_usd = exit_spread / 10000.0 * exec_px_arr[fill_t]
                        _entry_sp_usd = entry_spread / 10000.0 * entry_price
                    else:
                        _exit_sp_usd = exit_spread
                        _entry_sp_usd = entry_spread
                    gross_pnl = position * (_exit_sp_usd - _entry_sp_usd) * shares
                is_stress = ('ADF OFF' in exit_reason)
                k_adr_today = k_adr_arr[fill_t] if not np.isnan(k_adr_arr[fill_t]) else K_ADR_FALLBACK
                k_fut_today = k_fut_arr[fill_t] if not np.isnan(k_fut_arr[fill_t]) else K_FUT_FALLBACK
                # [HKC] costs are charged on the hedge the trade ACTUALLY
                # carries: entry_beta sized it at entry and it never
                # re-sizes mid-hold, so the exit leg is the same size.
                # (beta_arr[fill_t] here would price the round trip off
                # whatever beta drifted to by the exit date.) The contract
                # value converts through the HEDGE leg's FX.
                exec_cost, exec_cost_bps = compute_exec_cost(
                    trade_notional, is_stress, k_adr_today, k_fut_today,
                    entry_beta, cost_mult=cost_mult,
                    fut_px_twd=fut_arr[fill_t], fx=hfx_arr[fill_t])
                funding_cost = 0.0
                borrow_cost = 0.0
                # [S2] average SOFR over the actual hold (trading rows
                # entry_day..fill_t), applied to calendar days held
                _fslice = fund_arr[entry_day:fill_t + 1]
                _favg = float(np.nanmean(_fslice)) if len(_fslice) else fund_arr[entry_day]
                if position == 1:
                    funding_cost = trade_notional * (_favg / 360) * calendar_days
                else:
                    borrow_cost = (trade_notional
                                   * (BORROW_ANN_BPS / 10000 - SHORT_REBATE_ANN)
                                   / 360 * calendar_days)   # [R6] net of rebate
                # [O2][S2] margin funding over the hold at the average SOFR
                # [HKS] futures hedges post margin; a us_etf hedge instead
                # carries the cash ETF position (borrow when short / funding
                # when long) — booked in the same margin_cost slot so every
                # downstream report stays one column.
                if _HEDGE_IS_FUT:
                    margin_cost = (entry_beta * trade_notional
                                   * (margin_ann_bps() / 10000 / 360)
                                   * calendar_days)   # [T4] flat 24bps, not SOFR-linked
                elif HEDGE_MODE == 'us_etf':
                    _h_rate_x = (ETF_BORROW_ANN_BPS / 10000 if position == 1
                                 else _favg)
                    margin_cost = (entry_beta * trade_notional
                                   * (_h_rate_x / 360) * calendar_days)
                else:
                    margin_cost = 0.0
                fx_hedge_cost = 0.0   # [HKS] pegged deliverable FX: no
                                      # forward-point carry, only the spot
                                      # half-spread inside exec_cost
                # [I3][J1] ROLL COST — only under the expiry-roll rule
                # (true front-month files). Under the CONFIRMED
                # month-start / next-month convention the real position
                # never rolls within a hold (the held M+1 contract is
                # weeks from expiry), so n_rolls = 0 and no cost.
                n_rolls = (int(max(ym_arr[fill_t] - ym_arr[entry_day], 0))
                           if ROLL_RULE == 'expiry_3rd_wed' else 0)
                _f_hs = (FUT_HALF_SPREAD_OPEN_BPS if EXEC_TIMING == 'open'
                         else FUT_HALF_SPREAD_CLOSE_BPS)
                roll_cost = n_rolls * entry_beta * trade_notional * (
                    (2 * (_f_hs + BOOK_BUFFER_FUT_BPS)
                     + FUT_FEE_IN_BPS + FUT_FEE_OUT_BPS) / 10000)
                total_cost = (exec_cost + funding_cost + borrow_cost
                              + fx_hedge_cost + roll_cost + margin_cost)
                net_pnl = gross_pnl - total_cost
                cumulative_realized += net_pnl
                if fill_t == t:
                    daily_equity[t] = cumulative_realized
                # [31] lag mode fills at t+1: today keeps the unrealized
                # mark; the realized level books on the next row
                trades.append({
                    'entry_day': entry_day, 'exit_day': fill_t,
                    'direction': position,
                    'entry_spread': entry_spread, 'exit_spread': exit_spread,
                    'hold_days_trading': hold_days_trading,
                    'hold_days_calendar': calendar_days,
                    'gross_pnl': gross_pnl,
                    'adr_leg_pnl': adr_leg_pnl,
                    'fut_leg_pnl': fut_leg_pnl,
                    'entry_beta': entry_beta,
                    'size_mult': size_mult,
                    'trade_notional': trade_notional,
                    'n_contracts': n_contracts,
                    'n_rolls': n_rolls,
                    'roll_cost': roll_cost,
                    'margin_cost': margin_cost,
                    'div_pnl': (div_accrued if pnl_mode == 'two_leg' else np.nan),
                    'fut_div_cash': (fut_div_cash if pnl_mode == 'two_leg'
                                     else np.nan),   # [T3]
                    'exec_cost': exec_cost,
                    'exec_cost_bps': exec_cost_bps,
                    'funding_cost': funding_cost,
                    'borrow_cost': borrow_cost,
                    'fx_hedge_cost': fx_hedge_cost,
                    'total_cost': total_cost,
                    'net_pnl': net_pnl,
                    'entry_date': df['Date'].iloc[entry_day],
                    'exit_date': df['Date'].iloc[fill_t],
                    'exit_reason': exit_reason,
                    'is_stress': is_stress,
                    # [HKE] a TIME_STOP=25cd hold can span a quarterly print
                    # — flag it so earnings-driven PnL is attributable
                    'spans_earnings': bool(earn_arr[entry_day:fill_t + 1].any()),
                    # [HKP] True when either fill sits on an ETF-proxy gap
                    # row — that trade's fair (and hedge mark) is estimated,
                    # not measured; exclude these when quoting live-ready PnL
                    'gap_proxy': bool(gprox_arr[entry_day] or gprox_arr[fill_t]),
                    'gamma_at_exit': gamma_coeff,
                    # [Q2] fields for the top-5 human-readable detail
                    'entry_px': entry_price,
                    'exit_px': exec_px_arr[fill_t],
                    'entry_fut': entry_fut_raw,
                    'exit_fut': fut_arr[fill_t],
                    'entry_z': z_at_entry,
                    'exit_z': ((spreads_signal[fill_t] - zmu_arr[fill_t])
                               / zsd_arr[fill_t]
                               if (not np.isnan(zsd_arr[fill_t])) and zsd_arr[fill_t] > 0
                               else np.nan),   # [T3] z at the exit fill
                    'entry_spread_bps': (spreads_signal[entry_day]
                                         if SIGNAL_MODE == 'premium' else
                                         spreads_signal[entry_day]
                                         / entry_price * 1e4),   # [T3][Y3]
                    'exit_spread_bps': (spreads_signal[fill_t]
                                        if SIGNAL_MODE == 'premium' else
                                        spreads_signal[fill_t]
                                        / exec_px_arr[fill_t] * 1e4),   # [T3][Y3]
                    'shares': shares,
                    'mae_bps': mae_bps,   # [H5]
                    'mfe_bps': mfe_bps,   # [R8]
                    'mfe_bps': mfe_bps,   # [S2]
                })
                position = 0
    var_metrics = compute_var_metrics(daily_equity, first_day)
    if position != 0:
        # [QC] real exposure the trade list does not show — say so loudly
        print(f"[QC] NOTE: the sample ENDS with a position still OPEN "
              f"(entered {df['Date'].iloc[entry_day]}, "
              f"{'LONG' if position == 1 else 'SHORT'} spread "
              f"${trade_notional:,.0f}). Its unrealized mark rides in the "
              f"equity curve but it is NOT a row in the trade list.")
    if len(trades) == 0:
        return {'net_pnl': 0, 'sharpe': 0, 'sharpe_active': 0, 'win_rate': 0,
                'max_dd_mtm': 0, 'max_dd_pct_avg': 0.0,
                'max_dd_pct_peak': 0.0, 'avg_notional': float(NOTIONAL),
                'peak_notional': float(NOTIONAL),
                'n_trades': 0, 'avg_hold_trading': 0, 'avg_hold_calendar': 0,
                'trades': [], 'daily_equity': daily_equity, 'adf_log': adf_log,
                'var_95': 0.0, 'var_99': 0.0, 'cvar_95': 0.0, 'cvar_99': 0.0,
                'worst_day': 0.0, 'n_active_days': 0}
    net_pnls = [tr['net_pnl'] for tr in trades]
    total_net_pnl = sum(net_pnls)
    avg_hold_trading = np.mean([tr['hold_days_trading'] for tr in trades])
    avg_hold_calendar = np.mean([tr['hold_days_calendar'] for tr in trades])
    equity_active = daily_equity[first_day:]
    daily_rets = np.diff(equity_active) / NOTIONAL
    annual_return = np.mean(daily_rets) * 252
    annual_vol = np.std(daily_rets) * np.sqrt(252)
    sharpe = annual_return / annual_vol if annual_vol > 0 else 0
    _act = daily_rets[daily_rets != 0]
    sharpe_active = ((_act.mean() * 252) / (_act.std() * np.sqrt(252))
                     if len(_act) > 2 and _act.std() > 0 else 0.0)
    winners = sum(1 for p in net_pnls if p > 0)
    win_rate = winners / len(net_pnls) * 100
    running_max_mtm = np.maximum.accumulate(equity_active)
    max_dd_mtm = (equity_active - running_max_mtm).min()
    # [N1] MaxDD as a share of the capital ACTUALLY deployed, not of the
    # base NOTIONAL. With z_scaled the clip varies trade to trade, so a
    # dollar drawdown means different things at different sizes. The
    # denominator is the AVERAGE trade notional (a drawdown normally
    # accumulates across several trades); the peak-notional version is
    # also reported so both readings are visible.
    _tn = [t['trade_notional'] for t in trades]
    _avg_tn = float(np.mean(_tn)) if _tn else float(NOTIONAL)
    _peak_tn = float(np.max(_tn)) if _tn else float(NOTIONAL)
    max_dd_pct_avg = max_dd_mtm / _avg_tn if _avg_tn > 0 else 0.0
    max_dd_pct_peak = max_dd_mtm / _peak_tn if _peak_tn > 0 else 0.0
    return {'net_pnl': total_net_pnl, 'sharpe': sharpe,
            'sharpe_active': sharpe_active, 'win_rate': win_rate,
            'max_dd_mtm': max_dd_mtm, 'n_trades': len(trades),
            'max_dd_pct_avg': max_dd_pct_avg,      # [N1]
            'max_dd_pct_peak': max_dd_pct_peak,
            'avg_notional': _avg_tn, 'peak_notional': _peak_tn,
            'avg_hold_trading': avg_hold_trading, 'avg_hold_calendar': avg_hold_calendar,
            'trades': trades, 'daily_equity': daily_equity, 'adf_log': adf_log,
            'var_95': var_metrics['var_95'], 'var_99': var_metrics['var_99'],
            'cvar_95': var_metrics['cvar_95'], 'cvar_99': var_metrics['cvar_99'],
            'worst_day': var_metrics['worst_day'], 'n_active_days': var_metrics['n_active_days'],
            'capped_events': capped_notional_events,          # [M6]
            'capped_usd': capped_notional_usd}
def classify_loser(trade):
    """[2] One-line explanation of WHY a losing trade lost."""
    gross = trade['gross_pnl']
    exec_c = trade['exec_cost']
    carry_c = (trade['funding_cost'] + trade['borrow_cost']
               + trade.get('fx_hedge_cost', 0.0)
               + trade.get('roll_cost', 0.0)
               + trade.get('margin_cost', 0.0))   # [I3][O2]
    reason = str(trade['exit_reason'])
    if gross > 0:
        if gross < exec_c:
            return (f"EXEC-COST-KILLED: gross edge ${gross:,.0f} < round-trip "
                    f"execution cost ${exec_c:,.0f}.")
        return (f"CARRY-KILLED: gross ${gross:,.0f} covered execution "
                f"(${exec_c:,.0f}) but {trade['hold_days_calendar']}cd of "
                f"financing (${carry_c:,.0f}) tipped it negative.")
    if 'ADF OFF' in reason:
        move = trade['exit_spread'] - trade['entry_spread']   # [W1] bps if premium, USD if dollar
        return f"ADF FORCED EXIT: spread moved ${move:.2f} the wrong way."
    if 'Gamma exit' in reason:
        return "GAMMA EXIT: expected daily profit < daily carry."
    if 'Time stop' in reason:
        return (f"TIME STOP: held {trade['hold_days_calendar']}cd with the "
                f"spread still against the position.")
    move = trade['exit_spread'] - trade['entry_spread']
    return f"Z crossed 0 but the $ spread moved the wrong way (${move:.2f})."
# ============================================================
# RUN GRID SEARCH
# ============================================================
banner(f"GRID SEARCH — {ADR_LBL} vs {ORD_LBL}, hedged with {HEDGE_LONG_LBL}")
_fut_px_now = float(df['Fut_2130'].iloc[-1])
_fx_now = float(pd.to_numeric(df['hedge_fx'], errors='coerce').iloc[-1])
# [HKC] the headline round trip is priced at the CURRENT hedge beta, not
# 1.0 — with beta ~0.7 the hedge-leg spread/fees/FX are ~30% smaller
# than a beta=1 quote, and the [S1] cost floor keys off this number.
_beta_now = float(df['beta_hedge'].iloc[-1]) \
    if np.isfinite(df['beta_hedge'].iloc[-1]) else float(BETA_PRIOR)
exec_normal, bps_normal = compute_exec_cost(NOTIONAL, False, K_ADR_FALLBACK,
                                            K_FUT_FALLBACK, _beta_now,
                                            fut_px_twd=_fut_px_now, fx=_fx_now)
# [S1] raise the entry floor to whichever is larger: the FX-noise floor
# or a multiple of the measured round-trip cost.
if MIN_EDGE_MULT > 0:
    _cost_floor = bps_normal * MIN_EDGE_MULT
    if _cost_floor > MIN_ENTRY_DEV_BPS:
        print(f"[S1] MIN_ENTRY_DEV_BPS raised {MIN_ENTRY_DEV_BPS:.0f} -> "
              f"{_cost_floor:.0f} bps = {MIN_EDGE_MULT:.2f}x the {bps_normal:.0f} bps "
              f"round trip (the FX-noise floor alone does not make a trade "
              f"pay for itself)")
        MIN_ENTRY_DEV_BPS = _cost_floor
    else:
        print(f"[S1] MIN_ENTRY_DEV_BPS stays {MIN_ENTRY_DEV_BPS:.0f} bps "
              f"(already above {MIN_EDGE_MULT:.2f}x the {bps_normal:.0f} bps round trip)")
    _p95 = float(_sb_dev.abs().quantile(0.95)) if '_sb_dev' in dir() else float('nan')
    if np.isfinite(_p95):
        _frac = float((_sb_dev.abs() > MIN_ENTRY_DEV_BPS).mean())
        print(f"[S1] only {_frac*100:.1f}% of days have |deviation| above the "
              f"floor (p95 of |deviation| = {_p95:.0f} bps) — if that is near "
              f"zero the name cannot pay for its own costs at this size")
exec_stress, bps_stress = compute_exec_cost(NOTIONAL, True, K_ADR_FALLBACK,
                                            K_FUT_FALLBACK, _beta_now,
                                            fut_px_twd=_fut_px_now, fx=_fx_now)
# [HKC] the futures book absorbs the HEDGE leg (beta x notional), so the
# participation sanity-check must look at that notional, not the clip
report_participation(_beta_now * NOTIONAL, _fut_px_now, _fx_now)   # [C5][E3]
_fee_sum = (ADR_FEE_IN_BPS + ADR_FEE_OUT_BPS + FUT_FEE_IN_BPS
            + FUT_FEE_OUT_BPS
            + 2 * (FX_SPOT_HALF_SPREAD_BPS if FX_EXEC_MODE == 'spot_next_open'
                   else FX_NDF_HALF_SPREAD_BPS))
if HTML_OUTPUT and _in_jupyter():          # [Y23] one settings table
    show_html_table(pd.DataFrame([
        {'setting': 'Fills', 'value': f"{EXEC_TIMING.upper()} "
         + ('print' if EXEC_TIMING == 'open' else '(MOC-executable)')},
        {'setting': 'Round trip (typical / stress)',
         'value': f"{bps_normal:.0f} / {bps_stress:.0f} bps"},
        {'setting': f'of which fees (ADR+{HEDGE_LBL}+FX)',
         'value': f"{_fee_sum:.0f} bps "
                  f"(ADR {ADR_FEE_IN_BPS}+{ADR_FEE_OUT_BPS}, "
                  f"SSF {FUT_FEE_IN_BPS}+{FUT_FEE_OUT_BPS}, FX 2x"
                  f"{FX_SPOT_HALF_SPREAD_BPS if FX_EXEC_MODE == 'spot_next_open' else FX_NDF_HALF_SPREAD_BPS:g})"},
        {'setting': 'of which spread + impact',
         'value': f"{bps_normal - _fee_sum:.1f} bps"},
        {'setting': 'Funding (long ADR)',
         'value': f"SOFR + {FUNDING_SPREAD_ANN*100:.1f}% (daily series)"},
        {'setting': 'Borrow (short ADR)', 'value': f"{BORROW_ANN_BPS} bps flat"},
        {'setting': f'{HEDGE_LBL} margin drag', 'value': f"{FUT_MARGIN_ANN_BPS} bps flat"},
        ]).set_index('setting'),
        title=f"GRID SEARCH — {NAME_LBL}: {ADR_LBL} vs {ORD_LBL} "
                    f"({HEDGE_LBL} hedge)", fmt='{}')
else:
    print(f"Fills: {EXEC_TIMING.upper()} "
          f"{'print' if EXEC_TIMING == 'open' else '(MOC-executable)'} | "
          f"Typical RT cost={bps_normal:.0f}bps | Stress={bps_stress:.0f}bps | "
          f"Funding=SOFR+{FUNDING_SPREAD_ANN*100:.1f}% (daily series) "
          f"| Borrow={BORROW_ANN_BPS}bps flat "
          f"| Margin={FUT_MARGIN_ANN_BPS}bps flat")
if not (HTML_OUTPUT and _in_jupyter()):
    print(f"Cost anatomy [C1][C3][C5] (RT, bps of notional, beta=1): "
          f"fees ADR {ADR_FEE_IN_BPS}+{ADR_FEE_OUT_BPS} | {HEDGE_LBL} {FUT_FEE_IN_BPS}+{FUT_FEE_OUT_BPS} | "
          f"FX {'spot ' + str(FX_SPOT_HALF_SPREAD_BPS) if FX_EXEC_MODE == 'spot_next_open' else 'NDF ' + str(FX_NDF_HALF_SPREAD_BPS)}x2 | "
          f"spread+impact {bps_normal - (ADR_FEE_IN_BPS + ADR_FEE_OUT_BPS + FUT_FEE_IN_BPS + FUT_FEE_OUT_BPS + 2*(FX_SPOT_HALF_SPREAD_BPS if FX_EXEC_MODE == 'spot_next_open' else FX_NDF_HALF_SPREAD_BPS)):.1f}")
# [X2] make the fee calibration visible. A DR cancellation fee is CASH per
# share, so the same bps figure means a wildly different cents-per-share on
# a $7 ADR than on a $250 one. If the number below does not look like a real
# depositary fee (~2-5 c/share), set ADR_FEE_OUT_BPS_INST for this name.
_x2_px = float(df['ADR Ref Px'].iloc[-1])
_x2_hs_a, _x2_hs_f = ((ADR_HALF_SPREAD_OPEN_BPS, FUT_HALF_SPREAD_OPEN_BPS)
                      if EXEC_TIMING == 'open'
                      else (ADR_HALF_SPREAD_CLOSE_BPS, FUT_HALF_SPREAD_CLOSE_BPS))
_x2_parts = [(f'{HEDGE_LBL} half-spread x2', 2 * _x2_hs_f),
             ('ADR fee OUT', ADR_FEE_OUT_BPS),
             ('FX spread x2', 2 * (FX_SPOT_HALF_SPREAD_BPS
                                   if FX_EXEC_MODE == 'spot_next_open'
                                   else FX_NDF_HALF_SPREAD_BPS)),
             ('ADR half-spread x2', 2 * _x2_hs_a),
             (f'{HEDGE_LBL} fees IN+OUT', FUT_FEE_IN_BPS + FUT_FEE_OUT_BPS),
             ('ADR fee IN', ADR_FEE_IN_BPS)]
_x2_parts.sort(key=lambda kv: -kv[1])
# [Y28] the round trip, ranked, as its own small table — the ACTIONABLE
# term should be obvious rather than buried in a 200-character line.
if HTML_OUTPUT and _in_jupyter():
    _x2_tbl = pd.DataFrame(
        [{'component': _k, 'bps': _v,
          '% of RT': _v / max(bps_normal, 1e-9) * 100,
          'cash equivalent': (f"{_v/1e4*_x2_px*100:.2f} c/share"
                              if 'fee' in _k and 'ADR' in _k else '')}
         for _k, _v in _x2_parts]).set_index('component')
    show_html_table(
        _x2_tbl, title=f"[X2] ROUND TRIP RANKED — {bps_normal:.0f} bps "
                       f"(ex-impact)",
        fmt={'bps': '{:.0f}', '% of RT': '{:.0f}'}, heat=True,
        note=f"The top two are {_x2_parts[0][1] + _x2_parts[1][1]:.0f} of "
             f"{bps_normal:.0f} bps, and the entry floor is "
             f"{MIN_EDGE_MULT:.2f}x the round trip — so CUTTING COST, not "
             f"cutting the floor, is the only honest way to trade more. "
             f"A depositary fee is FLAT CASH per share (usually 2-5 c), so "
             f"the c/share column is the one to sanity-check: "
             f"ADR OUT here is {ADR_FEE_OUT_BPS/1e4*_x2_px*100:.2f} c/share "
             f"on a ${_x2_px:,.2f} ADR"
             + (" — WAY above a real depositary fee; set "
                "ADR_FEE_OUT_BPS_INST for this name"
                if ADR_FEE_OUT_BPS / 1e4 * _x2_px * 100 > 8 else "."))
else:
    print(f"[X2] round trip ranked (bps, ex-impact): " + " | ".join(
        f"{_k} {_v:.0f}" for _k, _v in _x2_parts))
    print(f"[X2] ADR OUT {ADR_FEE_OUT_BPS} bps on a ${_x2_px:,.2f} ADR = "
          f"{ADR_FEE_OUT_BPS/1e4*_x2_px*100:.2f} c/share (usually 2-5, FLAT)")
if FX_EXEC_MODE == 'spot_next_open':
    try:
        _fx_win_sig = float((df['TWD_regn_open'].shift(-1) / df['TWD (Last)'] - 1)
                            .dropna().std()) if 'TWD_regn_open' in df.columns else \
            float(df['TWD (Last)'].pct_change().std())
    except Exception:
        _fx_win_sig = float(df['TWD (Last)'].pct_change().std())
    _fx_rows = [
        ('FX execution [O1]', f"deliverable SPOT at the next {LOCAL_LBL} open "
                              f"('{FX_SPOT_TICKER}', {FX_SPOT_FIELD})",
         f"half-spread {FX_SPOT_HALF_SPREAD_BPS} bps x2 = "
         f"{2*FX_SPOT_HALF_SPREAD_BPS} bps RT cost"),
        ('unhedged window', f"sigma ~{_fx_win_sig*100:.2f}% per conversion",
         'mean-zero RISK, not a cost; 2 conversions per round trip [P1]'),
        ('FX carry [T2]', '0 by construction',
         'the HKD peg is deliverable spot — no forward points exist to '
         'earn or pay on the hedge conversion')]
else:
    _fx_rows = [
        ('FX execution [D1]', 'NDF at trade time',
         f"carry long {FX_CARRY_LONG_SPREAD_ANN_BPS:+d} / short "
         f"{-FX_CARRY_LONG_SPREAD_ANN_BPS:+d} bps ann"
         + (" (0 = awaiting the FX desk's real points)"
            if FX_CARRY_LONG_SPREAD_ANN_BPS == 0 else " (desk-supplied)"))]
kv_table("COST & REGIME SETTINGS",
         _fx_rows + [
             ('margin funding [O2]', f"{FUT_MARGIN_ANN_BPS} bps ann",
              'on the futures leg, calendar days, both directions'),
             ('sizing [D3]', f"{SIZING_MODE}"
              + (f" (cap {SIZE_CAP:.1f}x)" if SIZING_MODE == 'z_scaled'
                 else ''), ''),
             ('cost model [E3]', f"{COST_MODEL}",
              'order-book based' if COST_MODEL == 'book' else 'parametric'),
             ('contract align [E2]',
              'ON' if ALIGN_TO_CONTRACTS else 'OFF',
              f'notional snapped to whole {HEDGE_LBL} contracts'),
             ('exits', f"z-cross-0, gamma (profit < carry), time stop "
                       f"{TIME_STOP}cd", 'plus stops when enabled'),
             ('grid', f"N={N_VALUES} x Z={THRESHOLD_VALUES}", '')])
vprint(f"Exit: Z-cross-0, ADF OFF, Gamma (profit<carry), Time stop {TIME_STOP}cd")
vprint(f"Grid: N={N_VALUES} x Z={THRESHOLD_VALUES}")
_grid_t0 = time.time()
results_pnl = np.zeros((len(N_VALUES), len(THRESHOLD_VALUES)))
results_sharpe = np.zeros((len(N_VALUES), len(THRESHOLD_VALUES)))
results_winrate = np.zeros((len(N_VALUES), len(THRESHOLD_VALUES)))
results_maxdd = np.zeros((len(N_VALUES), len(THRESHOLD_VALUES)))
results_ddpct = np.zeros((len(N_VALUES), len(THRESHOLD_VALUES)))     # [N1]
results_tstat = np.full((len(N_VALUES), len(THRESHOLD_VALUES)), np.nan)  # [V3]
results_tpy = np.zeros((len(N_VALUES), len(THRESHOLD_VALUES)))           # [V3]
results_lb = np.full((len(N_VALUES), len(THRESHOLD_VALUES)), np.nan)     # [V3]
_T_CRIT_95 = {2: 2.92, 3: 2.35, 4: 2.13, 5: 2.02, 6: 1.94, 7: 1.89, 8: 1.86,
              9: 1.83, 10: 1.81, 12: 1.78, 15: 1.75, 20: 1.72, 25: 1.71,
              30: 1.70}   # one-sided 95%, by degrees of freedom (n-1)
_T_CRIT_95 = {k: _T_CRIT_95[min([d for d in _T_CRIT_95 if d >= k], default=30)]
              for k in range(1, 31)}
_years_sample = max((pd.to_datetime(df['Date'].iloc[-1])
                     - pd.to_datetime(df['Date'].iloc[0])).days / 365.25, 0.25)
results_avgnot = np.zeros((len(N_VALUES), len(THRESHOLD_VALUES)))
results_trades = np.zeros((len(N_VALUES), len(THRESHOLD_VALUES)))
results_var95 = np.zeros((len(N_VALUES), len(THRESHOLD_VALUES)))
results_cvar95 = np.zeros((len(N_VALUES), len(THRESHOLD_VALUES)))
results_hold = np.zeros((len(N_VALUES), len(THRESHOLD_VALUES)))
for i, n in enumerate(N_VALUES):
    for j, thresh in enumerate(THRESHOLD_VALUES):
        result = run_backtest(df, n, thresh)
        results_pnl[i, j] = result['net_pnl']
        results_sharpe[i, j] = result['sharpe']
        # [V3] t-stat of the MEAN TRADE P&L and the trade frequency. The
        # t-stat is the direct answer to "could this cell be luck?", and its
        # sqrt(n) term means more trades score better, not worse.
        _pn = [t['net_pnl'] for t in result['trades']]
        if len(_pn) >= 3:
            _m = float(np.mean(_pn))
            _s = float(np.std(_pn, ddof=1))
            _se = _s / np.sqrt(len(_pn))
            results_tstat[i, j] = (_m / _se) if _se > 0 else 0.0
            # [V3] 95% one-sided lower bound on the ANNUAL P&L. The t
            # critical value grows fast as n shrinks (n=4 -> 3.18,
            # n=25 -> 2.06), so this is the number that charges a real
            # price for a thin sample.
            _tc = _T_CRIT_95.get(min(len(_pn) - 1, 30), 1.70)
            results_lb[i, j] = ((_m - _tc * _se) * len(_pn)
                                / max(_years_sample, 0.25))
        else:
            results_tstat[i, j] = np.nan
            results_lb[i, j] = np.nan
        results_tpy[i, j] = len(_pn) / max(_years_sample, 0.25)
        results_winrate[i, j] = result['win_rate']
        results_maxdd[i, j] = result['max_dd_mtm']
        results_ddpct[i, j] = result['max_dd_pct_avg']       # [N1]
        results_avgnot[i, j] = result['avg_notional']
        results_trades[i, j] = result['n_trades']
        results_var95[i, j] = result['var_95']
        results_cvar95[i, j] = result['cvar_95']
        results_hold[i, j] = result['avg_hold_calendar']
        vprint(f"  N={n:2d}, Thresh={thresh:.2f} | PnL: ${result['net_pnl']:>10,.0f} | "
               f"Sharpe: {result['sharpe']:>6.2f} | Win: {result['win_rate']:>5.1f}% | "
               f"MaxDD: ${result['max_dd_mtm']:>10,.0f} | VaR95: ${result['var_95']:>8,.0f} | "
               f"Trades: {result['n_trades']:>3d} | "
               f"Hold: {result['avg_hold_trading']:>3.1f}td/{result['avg_hold_calendar']:>4.1f}cd")
print(f"Grid completed in {time.time() - _grid_t0:.1f}s "
      f"(ADF precomputed once per signal series and cached — [11])")
def show_matrix(title, mat, always=False, fmt=",.0f"):
    """[Y5] Every grid matrix now renders as a HEAT-MAPPED HTML table when
    running in Jupyter (HTML_OUTPUT=True); identical plain text otherwise, so
    nothing is lost in a terminal or a log file. Read the heat maps for STABLE
    REGIONS rather than single bright cells."""
    _show = always or VERBOSE
    dfm = pd.DataFrame(mat, index=[f'N={n}' for n in N_VALUES],
                       columns=[f'Z={t}' for t in THRESHOLD_VALUES])
    _f = {',.0f': '{:,.0f}', '.1f': '{:.1f}',
          '.2f': '{:.2f}'}.get(fmt, '{:,.0f}')
    if _show and HTML_OUTPUT and _in_jupyter():
        show_html_table(dfm, title=title, heat=True, fmt=_f)
        return
    printer = print if _show else vprint
    printer("\n" + "=" * 70)
    printer(title)
    printer("=" * 70)
    printer(dfm.to_markdown(floatfmt=fmt))
    if _show and HTML_OUTPUT:
        # [Y4b] no rich front-end: the markdown above is what you read in the
        # console, and the SAME matrix goes to HTML_FILE as a heat map.
        try:
            _html_to_file(_style(dfm, title, heat=True, fmt=_f).to_html())
        except Exception:
            _html_to_file(f"<h4>{title}</h4>" + dfm.to_html(border=0))
# [16] PnL, WIN RATE and TRADES always shown; the rest under VERBOSE.
show_matrix("NET PnL MATRIX ($)", results_pnl, always=True)
show_matrix("WIN RATE MATRIX (%)", results_winrate, always=True, fmt=".1f")
show_matrix("NUMBER OF TRADES MATRIX", results_trades.astype(int), always=True)
show_matrix("SHARPE MATRIX", results_sharpe, fmt=".2f")
show_matrix("MAX DRAWDOWN MTM MATRIX ($)", results_maxdd)
show_matrix("95% VaR MATRIX ($ daily)", results_var95)
show_matrix("95% CVaR MATRIX ($ daily)", results_cvar95)
show_matrix("AVG HOLD MATRIX (calendar days)", results_hold, fmt=".1f")
# ---------- [15][G3] TOP 5 PARAMETER SETS, human-readable ----------
# The live run exposed an inconsistency: NO cell reached 15 trades, so
# the TOP-5 table silently printed NOTHING while 'BEST ROBUST (>=15)'
# quietly fell back to the unconstrained argmax (14 trades) with a
# label that claimed otherwise. v18: ONE threshold, auto-relaxed with
# an explicit printed warning, used by the table, the robust pick AND
# the plateau guard alike.
MIN_TRADES_ROBUST = 15
_eff_min_trades = MIN_TRADES_ROBUST
if not (results_trades >= _eff_min_trades).any():
    _eff_min_trades = max(5, int(results_trades.max()) // 2)
    print(f"\n[G3] WARNING: no grid cell reaches {MIN_TRADES_ROBUST} trades "
          f"(max {int(results_trades.max())}) — the sample is too thin for "
          f"robust selection. Relaxing the floor to {_eff_min_trades} trades; "
          f"treat EVERYTHING below as indicative, not conclusive.")
# ------------------------------------------------------------
# [Y14] TRADES FLOOR = GRID MEAN. "min trades at least the mean of all
# the threshold cells": the floor becomes the mean trade count across
# every cell in the selectable N rows (N >= MIN_N_SELECT), when that is
# higher than the [G3] floor. If no cell reaches it (a top-heavy grid),
# keep the old floor with a printed warning rather than selecting nothing.
if MIN_TRADES_GRID_MEAN:
    _sel_rows_y14 = [_ii for _ii, _nv in enumerate(N_VALUES)
                     if _nv >= MIN_N_SELECT] or list(range(len(N_VALUES)))
    _grid_mean_tr = float(np.nanmean(results_trades[_sel_rows_y14, :]))
    _floor_y14 = int(np.ceil(_grid_mean_tr))
    if _floor_y14 > _eff_min_trades:
        if (results_trades[_sel_rows_y14, :] >= _floor_y14).any():
            print(f"\n[Y14] trades floor raised {_eff_min_trades} -> "
                  f"{_floor_y14} (grid mean {_grid_mean_tr:.1f} across the "
                  f"selectable N rows) — the chosen cell must be at least as "
                  f"active as the average cell, so a thin high-Z corner "
                  f"cannot win on a handful of lucky trades")
            _eff_min_trades = _floor_y14
        else:
            print(f"\n[Y14] grid-mean trades floor would be {_floor_y14} "
                  f"but NO selectable cell reaches it — keeping "
                  f"{_eff_min_trades}. The grid is top-heavy; extend "
                  f"THRESHOLD_VALUES downward.")
banner(f"TOP 5 PARAMETER SETS (ranked by Net PnL, min {_eff_min_trades} trades)")
_rows = []
for _flat in np.argsort(results_pnl, axis=None)[::-1]:
    _i, _j = divmod(int(_flat), len(THRESHOLD_VALUES))
    if results_trades[_i, _j] >= _eff_min_trades:
        _rows.append({'N': N_VALUES[_i], 'Z': f'{THRESHOLD_VALUES[_j]:.2f}',
                      'Net PnL $': f'{results_pnl[_i, _j]:,.0f}',
                      'Sharpe': f'{results_sharpe[_i, _j]:.2f}',
                      'Win %': f'{results_winrate[_i, _j]:.1f}',
                      'Trades': int(results_trades[_i, _j]),
                      'MaxDD $': f'{results_maxdd[_i, _j]:,.0f}',
                      'VaR95 $': f'{results_var95[_i, _j]:,.0f}',
                      'Hold cd': f'{results_hold[_i, _j]:.1f}'})
    if len(_rows) == 5:
        break
if _rows:
    if HTML_OUTPUT and _in_jupyter():
        show_html_table(pd.DataFrame(_rows).set_index('N'),
                        title=f"TOP 5 PARAMETER SETS — by Net PnL, "
                              f"min {_eff_min_trades} trades", fmt='{}')
    else:
        print(pd.DataFrame(_rows).to_markdown(index=False))
else:
    print("  (no qualifying cells)")
# ============================================================
# OPTIMAL PARAMETER SELECTION
# ============================================================
best_pnl_idx = np.unravel_index(np.argmax(results_pnl), results_pnl.shape)
mask = results_trades >= _eff_min_trades   # [G3] same floor everywhere
masked_pnl = np.where(mask, results_pnl, -np.inf)
best_robust_idx = np.unravel_index(np.argmax(masked_pnl), masked_pnl.shape)
best_n = N_VALUES[best_robust_idx[0]]
best_thresh = THRESHOLD_VALUES[best_robust_idx[1]]
banner("OPTIMAL PARAMETER SELECTION")
print(f"  Best by Net PnL: N={N_VALUES[best_pnl_idx[0]]}, Z={THRESHOLD_VALUES[best_pnl_idx[1]]} "
      f"(${results_pnl[best_pnl_idx]:,.0f})")
# [G5] PLATEAU selection: rank each cell by the MEAN Sharpe of its 3x3
# parameter neighborhood (edges truncated) so an isolated lucky cell
# cannot win — persuasive because performance must be locally STABLE.
# [Y3] _n_ok MOVED UP: v31.11 defined it BELOW, so the PLATEAU line ranked
# cells the selector then refused to use (it advertised N=10 / Z=2.0 and
# then excluded N=10 for MIN_N_SELECT). Same mask, both places.
_n_ok = np.array([[(_nv >= MIN_N_SELECT) for _tv in THRESHOLD_VALUES]
                  for _nv in N_VALUES])          # [U6]
 
def _nbhd_mean(_arr, _i, _j, _min_cells=3):
    """[Y3] 3x3 neighbourhood mean with DUPLICATE-CELL DE-DUP. Adjacent
    thresholds very often hold the IDENTICAL trade list (e.g. N=25 at
    Z=0.50 and Z=0.75 here), and averaging the same result twice is not
    evidence of stability — it is the same evidence counted twice."""
    _blk = _arr[max(_i - 1, 0):_i + 2, max(_j - 1, 0):_j + 2]
    _v = _blk[np.isfinite(_blk)]
    if _v.size < _min_cells:
        return np.nan
    return float(np.mean(np.unique(np.round(_v, 6))))
 
_sh = np.where((results_trades >= _eff_min_trades) & _n_ok,
               results_sharpe, np.nan)           # [Y3] same mask as SELECT
_nbhd = np.full_like(_sh, np.nan)
for _i in range(_sh.shape[0]):
    for _j in range(_sh.shape[1]):
        _nbhd[_i, _j] = _nbhd_mean(_sh, _i, _j)
if np.isfinite(_nbhd).any():
    _pi = np.unravel_index(np.nanargmax(_nbhd), _nbhd.shape)
    print(f"  PLATEAU (3x3-neighborhood mean Sharpe, dedup + selectable "
          f"cells only [Y3]): N={N_VALUES[_pi[0]]}, "
          f"Z={THRESHOLD_VALUES[_pi[1]]} | nbhd Sharpe {_nbhd[_pi]:.2f} | own "
          f"PnL ${results_pnl[_pi]:,.0f}")
# ============================================================
# [M5] RISK-AWARE SELECTION — max PnL alone ignores how much pain got
# you there. Filter on the constraints you actually care about (enough
# trades, a win rate you can live with, a drawdown inside your limit)
# and then rank by NEIGHBOURHOOD-MEAN Calmar (PnL / |MaxDD|), so the
# winner must be both efficient AND locally stable.
# ============================================================
# [V3] the constraint mask, then the chosen ranking metric on top of it
_pass = ((results_trades >= _eff_min_trades)
         & _n_ok
         & (results_tpy >= MIN_TRADES_PER_YEAR)
         & (results_winrate >= MIN_WIN_RATE_SELECT)
         & (np.abs(results_ddpct) <= MAX_DD_SELECT_PCT)   # [N1] % of deployed
         & (results_pnl > 0))
_calmar_raw = results_pnl / np.maximum(np.abs(results_maxdd), 1.0)
_metric = (results_tstat if SELECT_RANK == 'tstat'
           else results_lb if SELECT_RANK == 'lb' else _calmar_raw)
_cal = np.where(_pass, _metric, np.nan)
_cn = np.full_like(_cal, np.nan)
for _i in range(_cal.shape[0]):
    for _j in range(_cal.shape[1]):
        _cn[_i, _j] = _nbhd_mean(_cal, _i, _j)   # [Y3] de-duplicated
if MIN_N_SELECT > 0 and min(N_VALUES) < MIN_N_SELECT:
    _blocked = [f"N={_n}" for _n in N_VALUES if _n < MIN_N_SELECT]
    print(f"\n  [U6] lookbacks {', '.join(_blocked)} are excluded from SELECTION "
          f"(MIN_N_SELECT={MIN_N_SELECT}) — too few points to estimate the "
          f"rolling mean/sigma; they remain in the matrices above for reference")
_rank_lbl = {'tstat': 't-STAT', 'lb': '95% LOWER BOUND/yr'}.get(
    SELECT_RANK, 'CALMAR')        # [Y28] the dict literal used to PRINT
print(f"\n  [M5] RISK-AWARE candidates, ranked by 3x3 mean {_rank_lbl} [V3]")
_M5_ROWS = []
if np.isfinite(_cn).any():
    # [P4] a cell only qualifies if IT PASSES the constraints itself
    # (np.isfinite(_cal)); v31's first cut ranked by the neighbourhood
    # mean alone, letting a 62%-win cell win under a 65% filter because
    # its NEIGHBOURS passed.
    _flat = [(_cn[a, b], a, b) for a in range(_cn.shape[0])
             for b in range(_cn.shape[1])
             if np.isfinite(_cn[a, b]) and np.isfinite(_cal[a, b])]
    _flat.sort(reverse=True)
    _mid_date = df['Date'].iloc[len(df) // 2]
    for _k, (_v, _a, _b) in enumerate(_flat[:5], 1):
        # [P5] regime consistency: PnL split at the sample midpoint —
        # a real edge should not be one half funding the other
        _rr = run_backtest(df, N_VALUES[_a], THRESHOLD_VALUES[_b])
        _h1 = sum(t['net_pnl'] for t in _rr['trades'] if t['entry_date'] < _mid_date)
        _h2 = sum(t['net_pnl'] for t in _rr['trades'] if t['entry_date'] >= _mid_date)
        _half_tag = 'both halves +' if (_h1 > 0 and _h2 > 0) else 'ONE-SIDED'
        _M5_ROWS.append({
            '#': _k, 'N': N_VALUES[_a], 'Z': THRESHOLD_VALUES[_b],
            't': results_tstat[_a, _b], 'Calmar': _calmar_raw[_a, _b],
            'nbhd': _v, 'PnL': results_pnl[_a, _b],
            'Sharpe': results_sharpe[_a, _b],
            'win %': results_winrate[_a, _b],
            'MaxDD %': results_ddpct[_a, _b] * 100,
            'LB/yr': results_lb[_a, _b],
            'trades': int(results_trades[_a, _b]),
            'tr/yr': results_tpy[_a, _b],
            'H1 / H2': (f"${_h1:,.0f} / ${_h2:,.0f} "
                        + (_badge('both halves +', 'ok') if _half_tag ==
                           'both halves +' else _badge('ONE-SIDED', 'warn')))})
        if not (HTML_OUTPUT and _in_jupyter()):
            print(f"     {_k}. N={N_VALUES[_a]:<3} Z={THRESHOLD_VALUES[_b]:<5} "
                  f"| t {results_tstat[_a, _b]:>5.2f} | PnL "
                  f"${results_pnl[_a, _b]:>9,.0f} | Sharpe "
                  f"{results_sharpe[_a, _b]:4.2f} | win "
                  f"{results_winrate[_a, _b]:4.1f}% | "
                  f"{int(results_trades[_a, _b])} tr | {_half_tag}")
    if HTML_OUTPUT and _in_jupyter() and _M5_ROWS:
        show_html_table(
            pd.DataFrame(_M5_ROWS).set_index('#'),
            title=f"[M5] RISK-AWARE CANDIDATES — ranked by 3x3 mean "
                  f"{_rank_lbl}",
            fmt={'Z': '{:.2f}', 't': '{:.2f}', 'Calmar': '{:.2f}',
                 'nbhd': '{:.2f}', 'PnL': '${:,.0f}', 'Sharpe': '{:.2f}',
                 'win %': '{:.1f}', 'MaxDD %': '{:.1f}',
                 'LB/yr': '${:,.0f}', 'tr/yr': '{:.1f}'},
            note=f"Constraints: >= {_eff_min_trades} trades, win >= "
                 f"{MIN_WIN_RATE_SELECT:.0f}%, |MaxDD| <= "
                 f"{MAX_DD_SELECT_PCT*100:.0f}% of the notional ACTUALLY "
                 f"DEPLOYED [N1], >= {MIN_TRADES_PER_YEAR:.0f} trades/yr. "
                 f"H1/H2 splits the sample at its midpoint: a real edge is "
                 f"not one half funding the other. A cell qualifies only if "
                 f"IT passes — not merely its neighbours [P4].")
    _rk = _flat[0]
    if SELECT_MODE == 'risk_aware':
        best_robust_idx = (_rk[1], _rk[2])
        print(f"     -> SELECT_MODE='risk_aware' -> using N={N_VALUES[_rk[1]]}, "
              f"Z={THRESHOLD_VALUES[_rk[2]]}")
    else:
        print(f"     -> SELECT_MODE='{SELECT_MODE}' (set 'risk_aware' to use "
              f"candidate 1 above)")
else:
    print(f"     none pass the constraints — loosen MIN_WIN_RATE_SELECT / "
          f"MAX_DD_SELECT_PCT, or accept that no cell is both profitable and "
          f"inside your risk limit")
# ============================================================
# [Y6] COMPOSITE SELECTION — "more trades, higher win rate, higher PnL"
# ============================================================
# No cell dominates on every axis (here N=25/Z=0.50 has the trades and the
# PnL, N=20/Z=1.75 the t-stat, Sharpe and win rate), so ranking by ONE
# metric always throws away the others. This scores every cell that PASSES
# the constraints on its PERCENTILE RANK inside each metric — scale-free,
# so a $ figure and a % and a count can be combined honestly — averages
# them with COMPOSITE_WEIGHTS, and then applies the SAME de-duplicated 3x3
# stability requirement. Edge-of-grid winners are flagged, because an
# optimum sitting on the first or last column may really live OFF the grid.
def _pct_rank(_m, _valid):
    """percentile rank in [0,1] over the valid cells; ties share the rank"""
    _out = np.full(_m.shape, np.nan)
    _v = _m[_valid]
    if _v.size == 0:
        return _out
    _lo, _hi = np.nanmin(_v), np.nanmax(_v)
    if not np.isfinite(_lo) or _hi <= _lo:
        _out[_valid] = 0.5
        return _out
    _out[_valid] = (_m[_valid] - _lo) / (_hi - _lo)
    return _out
 
_comp = np.full(results_pnl.shape, np.nan)
if _pass.any():
    _w = COMPOSITE_WEIGHTS
    _parts = {'pnl': results_pnl, 'sharpe': results_sharpe,
              'win': results_winrate, 'trades': results_trades,
              'calmar': _calmar_raw, 'lb': results_lb}
    _tot_w = sum(_w.get(_k, 0.0) for _k in _parts)
    _acc = np.zeros(results_pnl.shape)
    for _k, _m in _parts.items():
        _r = _pct_rank(np.asarray(_m, dtype=float), _pass)
        _acc += _w.get(_k, 0.0) * np.nan_to_num(_r)
    _comp[_pass] = (_acc / max(_tot_w, 1e-9))[_pass]
_cmp_n = np.full_like(_comp, np.nan)
for _i in range(_comp.shape[0]):
    for _j in range(_comp.shape[1]):
        _cmp_n[_i, _j] = _nbhd_mean(_comp, _i, _j)
print(f"\n  [Y6] COMPOSITE candidates — weights "
      + ", ".join(f"{_k} {_v:g}" for _k, _v in COMPOSITE_WEIGHTS.items())
      + " (percentile rank per metric, then 3x3 stability):")
if np.isfinite(_cmp_n).any():
    _cf = [(_cmp_n[a, b], a, b) for a in range(_cmp_n.shape[0])
           for b in range(_cmp_n.shape[1])
           if np.isfinite(_cmp_n[a, b]) and np.isfinite(_comp[a, b])]
    _cf.sort(reverse=True)
    for _k, (_v, _a, _b) in enumerate(_cf[:5], 1):
        _edge = ('  <-- EDGE OF GRID'
                 if _b in (0, len(THRESHOLD_VALUES) - 1)
                 or _a in (0, len(N_VALUES) - 1) else '')
        print(f"     {_k}. N={N_VALUES[_a]:<3} Z={THRESHOLD_VALUES[_b]:<5} | "
              f"score {_comp[_a, _b]:.3f} (nbhd {_v:.3f}) | PnL "
              f"${results_pnl[_a, _b]:>9,.0f} | Sharpe "
              f"{results_sharpe[_a, _b]:4.2f} | win "
              f"{results_winrate[_a, _b]:4.1f}% | "
              f"{int(results_trades[_a, _b])} tr "
              f"({results_tpy[_a, _b]:.1f}/yr) | LB/yr "
              f"${results_lb[_a, _b]:>8,.0f}{_edge}")
    if HTML_OUTPUT and _in_jupyter():
        _ct = pd.DataFrame([{
            'N': N_VALUES[_a], 'Z': THRESHOLD_VALUES[_b],
            'score': _comp[_a, _b], 'nbhd': _v,
            'PnL': results_pnl[_a, _b], 'Sharpe': results_sharpe[_a, _b],
            'win %': results_winrate[_a, _b],
            'trades': int(results_trades[_a, _b]),
            'tr/yr': results_tpy[_a, _b], 'LB/yr': results_lb[_a, _b],
            'MaxDD %': results_ddpct[_a, _b] * 100,
            'edge of grid': ('YES' if (_b in (0, len(THRESHOLD_VALUES) - 1)
                                       or _a in (0, len(N_VALUES) - 1))
                             else '')}
            for _v, _a, _b in _cf[:8]]).set_index('N')
        show_html_table(_ct, title='[Y6] COMPOSITE CANDIDATES (ranked)',
                        fmt={'score': '{:.3f}', 'nbhd': '{:.3f}',
                             'PnL': '${:,.0f}', 'Sharpe': '{:.2f}',
                             'win %': '{:.1f}', 'tr/yr': '{:.1f}',
                             'LB/yr': '${:,.0f}', 'MaxDD %': '{:.1f}',
                             'Z': '{:.2f}', 'trades': '{:.0f}'},
                        note='No cell dominates on every axis — that is why '
                             'this is a weighted score and why the plateau '
                             'mean, not this row, is the honest expectation.')
    if SELECT_MODE == 'composite':
        best_robust_idx = (_cf[0][1], _cf[0][2])
        print(f"     -> SELECT_MODE='composite' -> using "
              f"N={N_VALUES[_cf[0][1]]}, Z={THRESHOLD_VALUES[_cf[0][2]]}")
        if (_cf[0][2] in (0, len(THRESHOLD_VALUES) - 1)
                or _cf[0][1] in (0, len(N_VALUES) - 1)):
            print(f"     [Y6] WARNING: the winner sits on the EDGE of the "
                  f"grid, so the true optimum may be OFF it. Extend "
                  f"THRESHOLD_VALUES (add cells below "
                  f"{min(THRESHOLD_VALUES)} / above {max(THRESHOLD_VALUES)}) "
                  f"or N_VALUES and re-run before trusting this cell.")
        print(f"     [Y6] with {int(results_trades[best_robust_idx])} trades "
              f"the top candidates are within noise of each other — quote the "
              f"PLATEAU statistic below, not this cell's headline.")
else:
    print("     none pass the constraints — same remedy as [M5] above")
best_n = N_VALUES[best_robust_idx[0]]
best_thresh = THRESHOLD_VALUES[best_robust_idx[1]]
print(f"  SELECTED [{SELECT_MODE}] (>={_eff_min_trades} trades): N={best_n}, Z={best_thresh} | "
      f"PnL=${results_pnl[best_robust_idx]:,.0f} | Trades={int(results_trades[best_robust_idx])} | "
      f"Win={results_winrate[best_robust_idx]:.0f}% | MaxDD=${results_maxdd[best_robust_idx]:,.0f} | "
      f"VaR95=${results_var95[best_robust_idx]:,.0f}")
result_base = run_backtest(df, best_n, best_thresh)
# ============================================================
# [33] SELECTION-BIAS GUARDS
# ============================================================
# The headline cell is an in-sample argmax over 36 cells, so its PnL /
# Sharpe carry selection bias. The honest expectation is the PLATEAU
# statistic (all robust cells in the stable region), not the best cell.
banner("SELECTION-BIAS GUARDS [33]")
_pl_pnl, _pl_sh = [], []
for _i in range(len(N_VALUES)):
    for _j, _z in enumerate(THRESHOLD_VALUES):
        if _z >= 1.5 and results_trades[_i, _j] >= _eff_min_trades:
            _pl_pnl.append(results_pnl[_i, _j])
            _pl_sh.append(results_sharpe[_i, _j])
if _pl_pnl:
    print(f"  Plateau (all {len(_pl_pnl)} cells with Z>=1.5 and >={_eff_min_trades} trades):")
    print(f"    Net PnL: mean ${np.mean(_pl_pnl):,.0f} | median ${np.median(_pl_pnl):,.0f} | "
          f"min ${np.min(_pl_pnl):,.0f} | best cell ${np.max(_pl_pnl):,.0f}")
    print(f"    Sharpe:  mean {np.mean(_pl_sh):.2f} | median {np.median(_pl_sh):.2f}")
    print(f"  -> Quote the plateau MEAN, not the best cell. If the mean is far")
    print(f"     below the best cell, the best cell is mostly selection luck.")
if OOS_SPLIT_DATE:
    _df_is = df[df['Date'] < OOS_SPLIT_DATE].reset_index(drop=True)
    if len(_df_is) > ADF_WINDOW + 60:
        _best, _bp = -np.inf, (best_n, best_thresh)
        for _n in N_VALUES:
            for _z in THRESHOLD_VALUES:
                _r = run_backtest(_df_is, _n, _z)
                if _r['n_trades'] >= 10 and _r['net_pnl'] > _best:
                    _best, _bp = _r['net_pnl'], (_n, _z)
        _r_full = run_backtest(df, _bp[0], _bp[1])
        _oos = [t for t in _r_full['trades'] if t['entry_date'] >= OOS_SPLIT_DATE]
        print(f"\n  OUT-OF-SAMPLE HOLDOUT (params chosen on data before {OOS_SPLIT_DATE}):")
        print(f"    Chosen in-sample: N={_bp[0]}, Z={_bp[1]} (IS PnL ${_best:,.0f})")
        if _oos:
            _op = sum(t['net_pnl'] for t in _oos)
            _ow = sum(1 for t in _oos if t['net_pnl'] > 0) / len(_oos) * 100
            print(f"    OOS: {len(_oos)} trades | net ${_op:,.0f} | win {_ow:.0f}%")
            print(f"    -> With only ~10 trades/year OOS is noisy; treat a small")
            print(f"       positive as 'not falsified', not as proof.")
        else:
            print(f"    OOS: no trades after the split date")
    else:
        print(f"  OOS split leaves too little in-sample data — skipped")
# ============================================================
# [Q2][R4] TRADE DETAIL PRINTER — full arithmetic per trade
# ============================================================
_PREM_MEAN_BPS = float(_sb_chk.mean()) if '_sb_chk' in dir() else float('nan')
def print_trade_details(trades_list, title, thresh):
    """Every number the backtest used, laid out so each leg and cost
    line can be re-derived by hand.
    [Y4] In Jupyter a SUMMARY TABLE is rendered first — the per-trade
    re-derivation below it is unchanged, because the whole point of that
    block is that it can be checked line by line."""
    banner(title)
    if not trades_list:
        print("  (no trades)")
        return
    if HTML_OUTPUT and _in_jupyter():
        def _xr_badge(r):
            r = str(r)
            if 'Z crossed' in r:
                return _badge('z crossed 0', 'ok')
            if 'Gamma' in r:
                return _badge('gamma exit', 'warn')
            if 'Time stop' in r:
                return _badge('time stop', 'warn')
            if 'Hard stop' in r or 'stop' in r.lower():
                return _badge(r, 'bad')
            return _badge(r, 'mut')
        _rows = []
        for _k2, _t in enumerate(trades_list, 1):
            _net = _t['net_pnl']
            _rows.append({
                '#': _k2, 'entry': _t['entry_date'], 'exit': _t['exit_date'],
                'cd': _t['hold_days_calendar'],
                'side': (_badge('LONG', 'ok') if _t['direction'] == 1
                         else _badge('SHORT', 'bad')),
                'z in\u2192out': f"{_t['entry_z']:+.2f} \u2192 "
                              f"{_t.get('exit_z', float('nan')):+.2f}",
                'notional': _t['trade_notional'],
                'ADR leg': _t.get('adr_leg_pnl', float('nan')),
                'SSF leg': _t.get('fut_leg_pnl', float('nan')),
                'costs': _t.get('total_cost', float('nan')),
                'NET': (_badge(f"${_net:+,.0f}", 'ok' if _net > 0 else 'bad')),
                'bps': _net / max(_t['trade_notional'], 1.0) * 1e4,
                'exit': _xr_badge(_t.get('exit_reason', ''))})
        show_html_table(
            pd.DataFrame(_rows).set_index('#'), title=title,
            fmt={'notional': '{:,.0f}', 'ADR leg': '{:+,.0f}',
                 'SSF leg': '{:+,.0f}', 'costs': '{:,.0f}',
                 'bps': '{:+,.0f}', 'cd': '{:.0f}'},
            note='Full per-trade re-derivation: VERBOSE=True prints it '
                 'line by line.')
        if not VERBOSE:
            return                     # [Y23] the table IS the report
    for _k, _t in enumerate(trades_list, 1):
        _dir = f'LONG spread (buy ADR / short {HEDGE_LBL})' if _t['direction'] == 1 \
            else f'SHORT spread (sell ADR / long {HEDGE_LBL})'
        print(f"\n  #{_k}  {_t['entry_date']} -> {_t['exit_date']}  "
              f"({_t['hold_days_calendar']}cd / {_t['hold_days_trading']}td)  {_dir}")
        _ez = _t.get('exit_z', float('nan'))
        _ebps = _t.get('entry_spread_bps', float('nan'))
        _xbps = _t.get('exit_spread_bps', float('nan'))
        print(f"      SIGNAL    : entry z {_t['entry_z']:+.2f} -> exit z {_ez:+.2f} "
              f"(threshold {thresh:+.2f}; entry should be past it, exit near 0)")
        _cap = _t['direction'] * (_xbps - _ebps)   # [Y5] signed by direction
        print(f"                  spread {_ebps:+.0f} bps -> {_xbps:+.0f} bps "
              f"(captured {_cap:+.0f} bps after direction; the level shown "
              f"includes this name's structural premium, mean "
              f"{_PREM_MEAN_BPS:+.0f} bps — the trade earns only the CHANGE)")
        print(f"                  size {_t['size_mult']:.2f}x -> notional "
              f"${_t['trade_notional']:,.0f} = {_t['n_contracts']} {HEDGE_LBL} contracts")
        print(f"      ADR leg   : {_t['shares']:.0f} sh, "
              f"{_t['entry_px']:.2f} -> {_t['exit_px']:.2f} USD  "
              f"=> ${_t['adr_leg_pnl']:,.0f}"
              + (f" (+div ${_t['div_pnl']:,.0f})"
                 if np.isfinite(_t.get('div_pnl', np.nan)) and _t['div_pnl'] else ""))
        _fut_ret = _t['exit_fut'] / _t['entry_fut'] - 1
        _straddle = (pd.Timestamp(_t['entry_date']).year * 12
                     + pd.Timestamp(_t['entry_date']).month) != \
                    (pd.Timestamp(_t['exit_date']).year * 12
                     + pd.Timestamp(_t['exit_date']).month)
        _roll_note = ("  [ROLL-STRADDLE: leg PnL uses the spliced hedge (raw "
                      "-> TR spine across the month roll [I3]), so it will NOT "
                      "equal the raw entry_fut->exit_fut ratio above]"
                      if _straddle else "")
        print(f"      {HEDGE_LBL} leg   : {_t['entry_fut']:.1f} -> {_t['exit_fut']:.1f} "
              f"({_fut_ret*100:+.2f}% raw) x FX(entry/exit)  =>  "
              f"${_t['fut_leg_pnl']:,.0f}{_roll_note}")
        if _t.get('fut_div_cash') is not None and abs(_t.get('fut_div_cash') or 0) > 0.5:
            print(f"                  + hedge-leg dividend "
                  f"${_t['fut_div_cash']:+,.0f} [T3] (long SSF is credited the "
                  f"cash dividend, short is debited — this is why the quoted "
                  f"futures may fall on the ex-date without the hedge losing)")
        print(f"      GROSS     : ADR ${_t['adr_leg_pnl']:,.0f} + {HEDGE_LBL} "
              f"${_t['fut_leg_pnl']:,.0f} "
              f"= ${_t['gross_pnl']:,.0f}")
        print(f"      costs     : exec ${_t['exec_cost']:,.0f} ({_t['exec_cost_bps']:.0f}bps) "
              f"| fund ${_t['funding_cost']:,.0f} | borrow ${_t['borrow_cost']:,.0f} "
              f"| margin ${_t.get('margin_cost', 0):,.0f} | fxcarry ${_t['fx_hedge_cost']:,.0f} "
              f"| roll ${_t.get('roll_cost', 0):,.0f}  = ${_t['total_cost']:,.0f}")
        print(f"      NET       : ${_t['gross_pnl']:,.0f} - ${_t['total_cost']:,.0f} "
              f"= ${_t['net_pnl']:,.0f}  ({_t['net_pnl']/_t['trade_notional']*1e4:+.0f} bps) "
              f"| exit: {_t['exit_reason']}")
    print("\n  Re-derivation: ADR leg = shares x (exit-entry px) x sign;")
    print(f"  {HEDGE_LBL} leg = -dir x beta x notional x "
          f"(exit/entry - 1) x FX(entry)/FX(exit)")
    print(f"            (an index hedge pays no dividend cash — [R5][HKS])")
    print("            [EXCEPT roll-straddling trades: those use the spliced")
    print("             hedge growth, flagged inline above];")
    print(f"  net = ADR + {HEDGE_LBL} + div - all costs. Any NON-straddle line that")
    print("  doesn't tie out flags that trade for investigation.")
print_trade_details(sorted(result_base['trades'], key=lambda t: t['net_pnl'],
                           reverse=True)[:5],
                    f"[Q2] TOP 5 TRADES BY NET PnL — N={best_n}, Z={best_thresh}",
                    best_thresh)
# ============================================================
# [H5] MAX ADVERSE EXCURSION — how to set HARD_STOP_BPS from data
# ============================================================
# [J6] direction asymmetry — the single most actionable diagnostic
_lg = [t for t in result_base['trades'] if t['direction'] == 1]
_sh = [t for t in result_base['trades'] if t['direction'] == -1]
_j6 = []
for _lbl, _grp in ((f'LONG spread (buy ADR / short {HEDGE_LBL})', _lg),
                   (f'SHORT spread (sell ADR / long {HEDGE_LBL})', _sh)):
    if _grp:
        _p = [t['net_pnl'] for t in _grp]
        _j6.append({'side': _lbl, 'trades': len(_grp), 'net': sum(_p),
                    'win %': sum(1 for x in _p if x > 0) / len(_p) * 100,
                    'best': max(_p), 'worst': min(_p),
                    'avg': sum(_p) / len(_p)})
    else:
        _j6.append({'side': _lbl, 'trades': 0, 'net': 0.0, 'win %': float('nan'),
                    'best': float('nan'), 'worst': float('nan'),
                    'avg': float('nan')})
if HTML_OUTPUT and _in_jupyter():
    show_html_table(
        pd.DataFrame(_j6).set_index('side'),
        title='[J6] DIRECTION SPLIT — is the edge symmetric?',
        fmt={'net': '${:+,.0f}', 'best': '${:+,.0f}', 'worst': '${:+,.0f}',
             'avg': '${:+,.0f}', 'win %': '{:.0f}', 'trades': '{:.0f}'},
        note="If one side carries the PnL and the other carries the tail, "
             "re-run with DIRECTION_FILTER='long_only' (or 'short_only') — "
             "but treat a one-sided result with suspicion first: on a "
             "structurally-premium ADR the short-spread side is short the "
             "re-rating, so an asymmetry can be the sample, not the edge.")
else:
    banner("[J6] DIRECTION SPLIT — is the edge symmetric?")
    for _r6 in _j6:
        print(f"  {_r6['side']:<38} {_r6['trades']:3d} trades | net "
              f"${_r6['net']:>9,.0f} | win {_r6['win %']:3.0f}%")
# ============================================================
# [S3] PROFIT-TAKING SCAN — what a target WOULD have done
# ============================================================
# For every trade we know its maximum favourable excursion (MFE, the
# best unrealized point of the hold, in bps of that trade's notional).
# If a target sits below the MFE the trade would have been closed there;
# otherwise it runs to its actual outcome. This is a FIRST-ORDER
# estimate: closing early frees capital and can enable a re-entry the
# scan does not model, so treat it as a direction, not a forecast.
_tr_all = result_base['trades']
if _tr_all and 'mfe_bps' in _tr_all[0]:
    banner(f"[S3] PROFIT-TAKING SCAN — N={best_n}, Z={best_thresh} "
           f"(current PROFIT_TARGET_BPS={PROFIT_TARGET_BPS})")
    _mf = [t['mfe_bps'] for t in _tr_all]
    _act = [t['net_pnl'] / t['trade_notional'] * 1e4 for t in _tr_all]
    _base_pnl = sum(t['net_pnl'] for t in _tr_all)
    _s3 = []
    for _tg in (50, 100, 150, 200, 300, 400):
        _tot, _hit = 0.0, 0
        for _t in _tr_all:
            if _t['mfe_bps'] >= _tg:
                _hit += 1
                _tot += _tg / 1e4 * _t['trade_notional']
            else:
                _tot += _t['net_pnl']
        _s3.append({'target bps': _tg, 'trades reaching it': _hit,
                    'of': len(_tr_all), 'est. PnL': _tot,
                    'vs actual': _tot - _base_pnl,
                    'verdict': (_badge('better than z-cross', 'ok')
                                if _tot > _base_pnl
                                else _badge('worse than z-cross', 'mut'))})
    if HTML_OUTPUT and _in_jupyter():
        show_html_table(
            pd.DataFrame(_s3).set_index('target bps'),
            title=f"[S3] PROFIT-TAKING SCAN — N={best_n}, Z={best_thresh} "
                  f"(PROFIT_TARGET_BPS={PROFIT_TARGET_BPS} now)",
            fmt={'est. PnL': '${:,.0f}', 'vs actual': '${:+,.0f}',
                 'trades reaching it': '{:.0f}', 'of': '{:.0f}'},
            note=f"MFE across {len(_tr_all)} trades: median "
                 f"{np.median(_mf):+.0f} / p75 {np.percentile(_mf, 75):+.0f} "
                 f"/ p90 {np.percentile(_mf, 90):+.0f} / max {max(_mf):+.0f} "
                 f"bps, vs realised median {np.median(_act):+.0f} bps — that "
                 f"gap is what is given back. Actual (z-cross / time / gamma) "
                 f"${_base_pnl:,.0f}. FIRST-ORDER only: it assumes the target "
                 f"fills the day it is touched and ignores the re-entry the "
                 f"freed capital might have taken, so set "
                 f"PROFIT_TARGET_BPS and re-run for the real number.")
    else:
        print(f"  MFE median {np.median(_mf):+.0f} | realised median "
              f"{np.median(_act):+.0f} bps | actual ${_base_pnl:,.0f}")
        for _r3 in _s3:
            print(f"  {_r3['target bps']:>6} bps {_r3['trades reaching it']:>5}"
                  f" {_r3['est. PnL']:>12,.0f} {_r3['vs actual']:>+11,.0f}")
_wm = [t['mae_bps'] for t in result_base['trades'] if t['net_pnl'] > 0]
_lm = [t['mae_bps'] for t in result_base['trades'] if t['net_pnl'] <= 0]
if _wm and _lm:
    _sug = abs(np.percentile(_wm, 10)) * 1.2
    _h5 = [('winners', len(_wm), np.median(_wm), np.percentile(_wm, 10),
            min(_wm)),
           ('losers', len(_lm), np.median(_lm), np.percentile(_lm, 10),
            min(_lm))]
    if HTML_OUTPUT and _in_jupyter():
        show_html_table(
            pd.DataFrame(_h5, columns=['trades', 'n', 'median MAE bps',
                                       'p10 MAE bps',
                                       'worst MAE bps']).set_index('trades'),
            title='[H5] MAX ADVERSE EXCURSION — worst unrealised point per '
                  'trade',
            fmt={'n': '{:.0f}', 'median MAE bps': '{:+,.0f}',
                 'p10 MAE bps': '{:+,.0f}', 'worst MAE bps': '{:+,.0f}'},
            note=f"A stop must sit BELOW the WINNERS' drawdowns or it cuts "
                 f"trades that would have paid. Winners' 10th-percentile MAE "
                 f"is {np.percentile(_wm, 10):+.0f} bps, so HARD_STOP_BPS "
                 f"around {_sug:.0f} (1.2x that) keeps ~90% of winners intact "
                 f"while capping the tail. Currently "
                 + ('OFF — the [Y24] position-health carry test is the only '
                    'thing watching a losing trade.'
                    if HARD_STOP_BPS == 0
                    else f"{HARD_STOP_BPS} bps, which would have cut "
                         f"{sum(1 for m in _wm if m < -HARD_STOP_BPS)} of "
                         f"{len(_wm)} winners."))
    else:
        print("\n[H5] MAX ADVERSE EXCURSION")
        for _n5, _c5, _m5, _p5, _w5 in _h5:
            print(f"  {_n5:<9} n={_c5:<4} median {_m5:+.0f} | p10 {_p5:+.0f} "
                  f"| worst {_w5:+.0f} bps")
        print(f"  -> HARD_STOP_BPS ~ {_sug:.0f} keeps ~90% of winners")
# ============================================================
# [R8] WHAT WAS ON THE TABLE — max favourable excursion vs captured
# ============================================================
_tr_all = result_base['trades']
if _tr_all:
    _mfe = np.array([t['mfe_bps'] for t in _tr_all])
    _cap = np.array([t['net_pnl'] / t['trade_notional'] * 1e4 for t in _tr_all])
    _give = _mfe - _cap
    banner("[R8] PROFIT LEFT ON THE TABLE (peak unrealised vs what was booked)")
    _r8 = [('peak unrealised (MFE)', np.median(_mfe),
            np.percentile(_mfe, 75), _mfe.max()),
           ('actually captured', np.median(_cap),
            np.percentile(_cap, 75), _cap.max()),
           ('given back', np.median(_give),
            np.percentile(_give, 75), _give.max())]
    if HTML_OUTPUT and _in_jupyter():
        show_html_table(
            pd.DataFrame(_r8, columns=['bps of notional', 'median', 'p75',
                                       'best']).set_index('bps of notional'),
            title='[R8] PROFIT LEFT ON THE TABLE — peak unrealised vs booked',
            fmt={'median': '{:+,.0f}', 'p75': '{:+,.0f}', 'best': '{:+,.0f}'},
            note=f"The median trade gave back {np.median(_give):+.0f} bps, "
                 f"{np.median(_give)/max(np.median(_mfe), 1)*100:.0f}% of its "
                 f"peak, and {(_give > 20).sum()} of {len(_tr_all)} trades "
                 f"peaked above their result. The [S3] table above scans what "
                 f"a target would have banked — same first-order caveat: it "
                 f"assumes the target fills the day it is touched and ignores "
                 f"the re-entry the freed capital might have taken.")
    else:
        print(f"  MFE median {np.median(_mfe):+.0f} | captured "
              f"{np.median(_cap):+.0f} | given back {np.median(_give):+.0f} "
              f"bps ({np.median(_give)/max(np.median(_mfe), 1)*100:.0f}% of "
              f"the peak)")
# ============================================================
# [W4] WHY DIDN'T IT TRADE THERE? For the biggest deviations in the sample,
# check every gate in turn and name the one that blocked the entry. A chart
# showing an obvious spike with no marker on it is either a correct refusal
# or a bug, and this is how you tell which.
# ============================================================
_stats_w4 = get_signal_stats(df['Spread (Signal)'].values)
_zmu_w4 = df['Spread (Signal)'].rolling(best_n).mean().shift(1)
_zsd_w4 = df['Spread (Signal)'].rolling(best_n).std(ddof=0).shift(1)
_z_w4 = (df['Spread (Signal)'] - _zmu_w4) / _zsd_w4.replace(0, np.nan)
_entry_days = {t['entry_day'] for t in result_base['trades']}
_hold_days = set()
for _t in result_base['trades']:
    _hold_days.update(range(_t['entry_day'], _t.get('exit_day', _t['entry_day']) + 1))
_first_w4 = first_tradable_row(best_n)   # [X3]
banner(f"[W4] MISSED-ENTRY AUDIT at the selected N={best_n} Z={best_thresh} "
       f"(15 largest |deviation| days)")
_w4_rows = []          # [Y4] collected, rendered once below
for _i in _sb_dev.abs().nlargest(15).index:
    _dv = float(_sb_dev.loc[_i]); _zz = float(_z_w4.loc[_i]) if _i in _z_w4.index else np.nan
    if _i in _entry_days:
        _v = "TRADED (entry here)"
    elif _i < _first_w4:
        _v = f"warm-up (row {_i} < {_first_w4})"
    elif _i in _hold_days:
        _v = "already in a position"
    elif not np.isfinite(_zz) or abs(_zz) < best_thresh:
        _v = f"|z| {abs(_zz):.2f} < {best_thresh:.2f} threshold"
    elif abs(_dv) < MIN_ENTRY_DEV_BPS:
        _v = f"|dev| {abs(_dv):.0f} < {MIN_ENTRY_DEV_BPS:.0f}bps cost floor"
    elif bool(df['gap_suspect'].iloc[_i]) if 'gap_suspect' in df.columns else False:
        _v = "suspect overnight gap [J5]"
    else:
        _gam = _stats_w4['gamma'][_i]
        _hl = (np.log(0.5) / np.log(1 + max(_gam, -0.999))
               if np.isfinite(_gam) and _gam < 0 else np.inf)
        if not np.isfinite(_gam):
            _v = "gate: no gamma yet"
        elif _gam >= 0:
            _v = f"GATE SHUT: gamma {_gam:+.3f} >= 0 (no reversion)"
        elif _hl > HL_MAX_DAYS:
            _v = f"GATE SHUT: half-life {_hl:.1f}d > {HL_MAX_DAYS}d"
        else:
            _mu_n = _zmu_w4.iloc[_i]; _mu_p = _zmu_w4.iloc[max(_i - 5, 0)]
            _csd = df['Spread (Signal)'].diff().rolling(best_n).std(ddof=0).shift(1).iloc[_i]
            _dr = (abs(_mu_n - _mu_p) / (_csd * np.sqrt(5.0))
                   if np.isfinite(_csd) and _csd > 0 else np.nan)
            _v = (f"GATE SHUT: drift {_dr:.2f} > {DRIFT_MAX_SIGMA:.2f} "
                  f"(the mean itself was repricing)" if np.isfinite(_dr)
                  and _dr > DRIFT_MAX_SIGMA else "no entry (check by hand)")
    _w4_rows.append((df['Date'].iloc[_i], _dv, _zz, _v))
if HTML_OUTPUT and _in_jupyter():
    def _w4_badge(v):
        if v.startswith('TRADED'):
            return _badge('TRADED', 'ok')
        if 'already in a position' in v:
            return _badge('IN POSITION', 'warn') + ' see run_backtest_lots [Y12]'
        if 'GATE SHUT' in v:
            return _badge('GATE SHUT', 'bad') + ' ' + v.split(':', 1)[1].strip()
        if 'suspect' in v:
            return _badge('SUSPECT GAP', 'warn') + ' [J5]'
        return _badge('NO ENTRY', 'mut') + ' ' + v
    show_html_table(
        pd.DataFrame([{'date': d_, 'dev bps': dv_, 'z': zz_,
                       'verdict': _w4_badge(v_)}
                      for d_, dv_, zz_, v_ in _w4_rows]).set_index('date'),
        title=f"[W4] MISSED-ENTRY AUDIT — 15 largest |deviation| days "
              f"(N={best_n}, Z={best_thresh})",
        fmt={'dev bps': '{:+,.0f}', 'z': '{:+.2f}'},
        note="Large |dev| with small |z| = the rolling sigma was already "
             "wide (big in bps, ordinary for the regime). Blocked by drift "
             "= the premium was RE-RATING, not oscillating — exactly what "
             "the gate exists to refuse.")
else:
    print(f"  {'date':<12}{'dev':>7}{'z':>7}  verdict")
    for _d4, _dv4, _zz4, _v4 in _w4_rows:
        print(f"  {_d4:<12}{_dv4:>+7.0f}{_zz4:>+7.2f}  {_v4}")
print("  A spike with a large |dev| but a small |z| means the ROLLING SIGMA was")
print("  already wide — the move was big in bps but ordinary for that regime.")
print("  A spike blocked by drift means the premium was RE-RATING, not")
print("  oscillating, which is exactly what the gate exists to refuse.")
# ============================================================
# [X6] WHY WAS THIS WHOLE STRETCH EMPTY? [W4] audits the 15 largest
# deviations in the SAMPLE, which tells you nothing about a specific quiet
# window — the whole point of a quiet window is that it holds none of them.
# This runs the same verdict logic over EVERY row between two dates and
# TALLIES the reasons, so "nothing traded for six months" resolves to a
# percentage split instead of a guess. Call it for any window:
#     why_no_trades('2025-07-01', '2025-12-31')
# ============================================================
def why_no_trades(start, end, n=None, thresh=None, show=10):
    """[X6] Per-row entry verdict over [start, end]. Returns the tally dict."""
    _n = int(n if n is not None else best_n)
    _th = float(thresh if thresh is not None else best_thresh)
    _w = df[(df['Date'] >= str(start)) & (df['Date'] <= str(end))]
    banner(f"[X6] ENTRY VERDICT PER ROW  {start} .. {end}  (N={_n}, Z={_th})")
    if not len(_w):
        print("  no aligned rows in that window — the hole is in the DATA, not "
              "the gates. Check the [QC] merge/stale/timestamp drops above.")
        return {}
    _sig = df['Spread (Signal)']
    _mu = _sig.rolling(_n).mean().shift(1)
    _z = (_sig - _mu) / _sig.rolling(_n).std(ddof=0).shift(1).replace(0, np.nan)
    _dev_s = _sig - _mu          # [Y2] keep the SIGN for display
    _dev = _dev_s.abs()          #      magnitude for the gate/sort
    _chg = _sig.diff().rolling(_n).std(ddof=0).shift(1)
    _gam = get_signal_stats(_sig.values if GATE_MODE == 'adf_level' else
                            (_sig - _sig.rolling(ADF_DETREND_N).mean().shift(1)
                             ).fillna(0.0).values)[1]
    _first = first_tradable_row(_n)
    _ent = {t['entry_day'] for t in result_base['trades']}
    _held = set()
    for _t in result_base['trades']:
        _held.update(range(_t['entry_day'], _t.get('exit_day', _t['entry_day']) + 1))
    _gapn = np.r_[np.diff(df['Date_dt'].values) / np.timedelta64(1, 'D'), 999]
    tally, rows = {}, []
    for _i in _w.index:
        if _i in _ent:
            _v = 'TRADED'
        elif _i < _first:
            _v = f'warm-up (row {_i} < {_first})'
        elif _i in _held:
            _v = 'already in a position'
        elif not np.isfinite(_z.iloc[_i]) or abs(_z.iloc[_i]) <= _th:
            _v = f'|z| <= {_th}'
        elif _dev.iloc[_i] < MIN_ENTRY_DEV_BPS:
            _v = f'|dev| < {MIN_ENTRY_DEV_BPS:.0f}bps COST FLOOR'
        elif bool(df['gap_suspect'].iloc[_i]):
            _v = 'contract-label mismatch [K7]'
        elif bool(df['pre_exdate'].iloc[_i]):
            _v = 'pre-ex-date block [S5]'
        elif ('earnings_block' in df.columns
              and bool(df['earnings_block'].iloc[_i])):
            _v = 'earnings block [HKE]'
        elif _gapn[_i] > MAX_ENTRY_GAP_DAYS:
            _v = f'next row > {MAX_ENTRY_GAP_DAYS}cd away'
        else:
            _g = _gam[_i]
            _hl = (np.log(0.5) / np.log(1 + max(_g, -0.999))
                   if np.isfinite(_g) and _g < 0 else np.inf)
            _dr = (abs(_mu.iloc[_i] - _mu.iloc[max(_i - 5, 0)])
                   / (_chg.iloc[_i] * np.sqrt(5.0))
                   if np.isfinite(_chg.iloc[_i]) and _chg.iloc[_i] > 0 else np.nan)
            if not np.isfinite(_g):
                _v = 'GATE: no gamma yet'
            elif _g >= 0:
                _v = 'GATE SHUT: gamma >= 0'
            elif _hl > HL_MAX_DAYS:
                _v = f'GATE SHUT: half-life > {HL_MAX_DAYS}d'
            elif np.isfinite(_dr) and _dr > DRIFT_MAX_SIGMA:
                _v = f'GATE SHUT: drift > {DRIFT_MAX_SIGMA}'
            else:
                _v = 'ALL GATES PASSED — investigate by hand'
        tally[_v] = tally.get(_v, 0) + 1
        rows.append((df['Date'].iloc[_i], float(_dev_s.iloc[_i]),
                     float(_z.iloc[_i]), _v))   # [Y2] signed
    _out = _dev.drop(_w.index)
    _closest = sorted([r for r in rows if r[3] != 'TRADED'],
                      key=lambda r: -abs(r[1]))[:show]      # [Y2]
    if HTML_OUTPUT and _in_jupyter():
        def _vb(v):
            if v == 'TRADED':
                return _badge('TRADED', 'ok')
            if 'already in a position' in v:
                return (_badge('IN POSITION', 'warn')
                        + ' — see run_backtest_lots [Y12]')
            if 'GATE' in v:
                return _badge(v.replace('GATE SHUT: ', ''), 'bad')
            if 'COST FLOOR' in v:
                return _badge('below cost floor', 'mut') + ' ' + v
            return _badge(v, 'mut')
        show_html_table(
            pd.DataFrame([{'reason': _vb(_v), 'rows': _c,
                           '% of window': _c / len(_w) * 100}
                          for _v, _c in sorted(tally.items(),
                                               key=lambda kv: -kv[1])]
                         ).set_index('reason'),
            title=f"[X6] WHY NO TRADE OPENED — {start} .. {end} "
                  f"(N={_n}, Z={_th}, {len(_w)} rows)",
            fmt={'rows': '{:.0f}', '% of window': '{:.0f}'})
        show_html_table(
            pd.DataFrame([{'date': _d, 'dev bps': _dv, 'z': _zz,
                           'blocked by': _vb(_v)}
                          for _d, _dv, _zz, _v in _closest]).set_index('date'),
            title='closest calls — largest |dev| that still did not enter',
            fmt={'dev bps': '{:+,.0f}', 'z': '{:+.2f}'},
            note=f"|dev| in this window: p50 "
                 f"{_dev.loc[_w.index].median():.0f} / p90 "
                 f"{_dev.loc[_w.index].quantile(0.90):.0f} / max "
                 f"{_dev.loc[_w.index].max():.0f} bps, against a floor of "
                 f"{MIN_ENTRY_DEV_BPS:.0f}; elsewhere p50 {_out.median():.0f}"
                 f" / p90 {_out.quantile(0.90):.0f} / max {_out.max():.0f}. "
                 f"If the in-window p90 sits BELOW the floor the premium was "
                 f"simply quiet and the refusal was correct — not a block to "
                 f"remove.")
    else:
        print(f"  {len(_w)} rows. Why each one did not OPEN a trade:\n")
        for _v, _c in sorted(tally.items(), key=lambda kv: -kv[1]):
            print(f"     {_c:>4}  ({_c/len(_w)*100:>4.0f}%)  {_v}")
        print(f"\n  closest calls (largest |dev| that still did not enter):")
        for _d, _dv, _zz, _v in _closest:
            print(f"     {_d}  dev {_dv:>+7.0f}  z {_zz:>+6.2f}  {_v}")
        print(f"\n  |dev| in window p50 {_dev.loc[_w.index].median():.0f} | "
              f"p90 {_dev.loc[_w.index].quantile(0.90):.0f} | floor "
              f"{MIN_ENTRY_DEV_BPS:.0f}")
    return tally
# run it automatically on the trailing 6 months so a live drought is never
# a mystery you have to go looking for
try:
    _x6_end = str(df['Date'].iloc[-1])
    _x6_start = str((pd.Timestamp(_x6_end) - pd.Timedelta(days=183)).date())
    why_no_trades(_x6_start, _x6_end)
except Exception as _e:
    print(f"[X6] window audit skipped ({_e})")
print_trade_details(sorted(result_base['trades'], key=lambda t: t['net_pnl'])[:5],
                    f"[R4] WORST 5 TRADES BY NET PnL — N={best_n}, Z={best_thresh}",
                    best_thresh)
# ============================================================
# [22] PNL MODE COMPARISON — actual two-leg vs convergence
# ============================================================
# Same signals, same trades; only the PnL accounting differs. The gap
# per trade IS the realized stock-vs-hedge noise your futures hedge
# leaves uncovered during the hold.
banner(f"PNL MODE COMPARISON — N={best_n}, Z={best_thresh}")
result_conv = run_backtest(df, best_n, best_thresh, pnl_mode='convergence')
if HTML_OUTPUT and _in_jupyter():
    show_html_table(
        pd.DataFrame([
            {'accounting': 'two-leg (ADR + futures fills, ACTUAL)',
             'net PnL': result_base['net_pnl'], 'Sharpe': result_base['sharpe'],
             'MaxDD': result_base['max_dd_mtm'], 'VaR95': result_base['var_95']},
            {'accounting': 'convergence (perfect fair-value hedge)',
             'net PnL': result_conv['net_pnl'], 'Sharpe': result_conv['sharpe'],
             'MaxDD': result_conv['max_dd_mtm'], 'VaR95': result_conv['var_95']},
        ]).set_index('accounting'),
        title=f"PNL MODE COMPARISON — N={best_n}, Z={best_thresh}",
        fmt={'net PnL': '${:,.0f}', 'Sharpe': '{:.2f}', 'MaxDD': '${:,.0f}',
             'VaR95': '${:,.0f}'},
        note='Same signals and same trades — only the accounting differs. '
             'The per-trade gap IS the stock-vs-hedge noise the futures hedge '
             'leaves uncovered during the hold, and the two-leg row is the '
             'one that reflects fills you can actually get.')
else:
    print(f"  two-leg      ${result_base['net_pnl']:>10,.0f} "
          f"(Sharpe {result_base['sharpe']:.2f})")
    print(f"  convergence  ${result_conv['net_pnl']:>10,.0f} "
          f"(Sharpe {result_conv['sharpe']:.2f})")
if result_base['trades'] and result_conv['trades'] \
        and len(result_base['trades']) == len(result_conv['trades']):
    _d = (pd.DataFrame(result_base['trades'])['gross_pnl'].values
          - pd.DataFrame(result_conv['trades'])['gross_pnl'].values)
    print(f"  Per-trade gap (two-leg minus convergence): mean ${_d.mean():,.0f} | "
          f"std ${_d.std():,.0f}")
    # [G4] the v17 note unconditionally claimed "mean near 0 = unbiased"
    # even when the live run showed a SYSTEMATIC -$3.5k/trade drag
    # (caused by the return-chained spine losing dropped days' moves —
    # fixed by [G1]). Judge the mean against its own standard error:
    _gap_se = _d.std() / max(np.sqrt(len(_d)), 1.0)
    if abs(_d.mean()) <= 2 * _gap_se:
        print("  -> mean within 2 SE of 0 = hedge noise looks unbiased; the std")
        print("     is the extra per-trade risk the convergence view was hiding.")
    else:
        print(f"  -> mean is {abs(_d.mean())/_gap_se:.1f} SE from 0 = a SYSTEMATIC")
        print("     drag on the futures leg. If this persists AFTER the [G1]")
        print("     spine fix, investigate the roll section and the gap dates.")
# ============================================================
# [24] ROLL IMPACT ON THE FUTURES LEG — best parameters
# ============================================================
# Quantifies the phantom PnL the v8 raw-file accounting would have
# booked on trades that straddled a contract roll in the snapshot
# files (the roll-safe hedge index removes it).
banner(f"ROLL IMPACT ON THE FUTURES LEG — N={best_n}, Z={best_thresh}")
if result_base['trades']:
    _fr = df['Fut_2130'].values
    _hg = df['Hedge Idx'].values
    _tot_raw = _tot_safe = 0.0
    _n_straddle = 0
    _worst = 0.0
    for _t in result_base['trades']:
        _e, _x, _b, _p = _t['entry_day'], _t['exit_day'], _t['entry_beta'], _t['direction']
        _raw = -_p * _b * NOTIONAL * (_fr[_x] / _fr[_e] - 1.0)
        _safe = -_p * _b * NOTIONAL * (_hg[_x] / _hg[_e] - 1.0)
        _tot_raw += _raw
        _tot_safe += _safe
        if _t.get('n_rolls', 0) > 0 or (df['contract_id'].iloc[_x]
                                        != df['contract_id'].iloc[_e]):
            _n_straddle += 1
        _worst = max(_worst, abs(_raw - _safe))
    _roll_lbl = ('file month-start roll' if ROLL_RULE == 'month_start'
                 else '3rd-Wed expiry roll')
    _booked = sum(t['fut_leg_pnl'] for t in result_base['trades']
                  if not np.isnan(t['fut_leg_pnl']))
    kv_table(f"ROLL IMPACT ON THE FUTURES LEG — N={best_n}, Z={best_thresh}",
             [(f'trades straddling the {_roll_lbl}',
               f"{_n_straddle} of {len(result_base['trades'])}", ''),
              ('roll cost charged',
               f"${sum(t.get('roll_cost', 0.0) for t in result_base['trades']):,.0f}",
               '0 by design — the real position never rolls under the '
               'next-month convention' if ROLL_RULE == 'month_start' else ''),
              ('futures leg, raw file series', f"${_tot_raw:,.0f}", ''),
              ('futures leg, booked (hybrid [27])', f"${_booked:,.0f}", ''),
              ('roll contamination avoided', f"${_tot_raw - _booked:,.0f}",
               f"largest single trade ${_worst:,.0f}")],
             note='Same-CONTRACT trades book the RAW file prices (the exact '
                  'actual fills); only roll-straddling trades splice onto the '
                  'TR spine across the file roll. For same-contract trades '
                  'booked == raw by construction, so any difference there '
                  'would flag a bug [27][I3][J1].')
# ============================================================
# [4] COST SENSITIVITY — best parameters
# ============================================================
banner(f"COST SENSITIVITY — N={best_n}, Z={best_thresh}")
cost_sens, _cs_rows = {}, []
for m in [0.50, 0.75, 1.00, 1.25, 1.50]:
    r = run_backtest(df, best_n, best_thresh, cost_mult=m)
    cost_sens[m] = r['net_pnl']
    _cs_rows.append({'cost multiple': f"{m:.2f}x", 'net PnL': r['net_pnl'],
                     'Sharpe': r['sharpe'], 'win %': r['win_rate']})
if HTML_OUTPUT and _in_jupyter():
    show_html_table(
        pd.DataFrame(_cs_rows).set_index('cost multiple'),
        title=f"COST SENSITIVITY — N={best_n}, Z={best_thresh}",
        fmt={'net PnL': '${:,.0f}', 'Sharpe': '{:.2f}', 'win %': '{:.1f}'},
        heat=True,
        note='1.00x is the measured round trip. If the edge dies between '
             '1.00x and 1.50x, the cost inputs are the whole trade — verify '
             'them with the desk before sizing.')
else:
    print(f"  {'CostMult':>8} | {'Net PnL':>12} | {'Sharpe':>7} | {'Win%':>6}")
    for _r in _cs_rows:
        print(f"  {_r['cost multiple']:>8} | ${_r['net PnL']:>10,.0f} | "
              f"{_r['Sharpe']:>7.2f} | {_r['win %']:>5.1f}%")
# ============================================================
# [5] EXECUTION-LAG ROBUSTNESS — best parameters
# ============================================================
banner(f"EXECUTION-LAG ROBUSTNESS — N={best_n}, Z={best_thresh}")
result_lag = run_backtest(df, best_n, best_thresh, lag_exec=True)
result_lag_e = run_backtest(df, best_n, best_thresh, lag_exec='entry_only')  # [G4]
# [18] Close-fill variant: DECIDE on the open-print signal, FILL both
# legs at the same day's US close. Bounds reality from below far more
# tightly than the next-day row. Approximation: the hedge is marked at
# the open-time futures snapshot (no futures print exists at the US
# close — the T+1 session ends 03:00 HKT), so 1-2h of hedge drift is
# embedded; the systematic open-vs-close level offset cancels in PnL
# differences and is absorbed by the z-score de-meaning.
if EXEC_TIMING == 'close':
    # [L3] HONEST close-mode framing. As backtested, the SIGNAL is
    # computed from the 21:00-UTC close print AND the fill is at that
    # same print — but a real MOC must be committed ~15:50 ET, BEFORE
    # the closing print exists. So base is a SAME-BAR result. The
    # lag-1 row (decide today, fill NEXT day) is the other extreme.
    # If lag-1 destroys the PnL, the edge decays fast and the truth
    # depends entirely on how much decays in the ~15 MINUTES between
    # a 15:45 ET signal and the 16:00 close — which THIS dataset
    # cannot measure. The decisive test: add 19:45/20:45 UTC snapshot
    # columns (ADR + SSF), compute the signal there, fill at the
    # close. Until then treat base as an upper bound, not an edge.
    result_close = result_base
    _lbl1, _lbl2, _lbl3 = ('Same-bar CLOSE signal+fill',
                           '(close mode: same as base)',
                           'Next-day fill (lag 1)')
else:
    df_closefill = df.copy()
    df_closefill['Exec Px'] = df_closefill['TSM US (Close)']
    if SIGNAL_MODE == 'premium':                     # [V1] match the signal units
        df_closefill['Spread (Exec)'] = (df_closefill['Exec Px']
                                         / df_closefill['Fair Price'] - 1.0) * 10000.0
    else:
        df_closefill['Spread (Exec)'] = (df_closefill['Exec Px']
                                         - df_closefill['Fair Price'])
    result_close = run_backtest(df_closefill, best_n, best_thresh)
    _lbl1, _lbl2, _lbl3 = ('Same-day OPEN fill (base)',
                           'Same-day CLOSE fill [18]',
                           'Next-day OPEN fill (lag 1)')
if HTML_OUTPUT and _in_jupyter():
    show_html_table(
        pd.DataFrame([
            {'variant': _lbl1, 'net PnL': result_base['net_pnl'],
             'Sharpe': result_base['sharpe'], 'win %': result_base['win_rate']},
            {'variant': _lbl2, 'net PnL': result_close['net_pnl'],
             'Sharpe': result_close['sharpe'], 'win %': result_close['win_rate']},
            {'variant': _lbl3, 'net PnL': result_lag['net_pnl'],
             'Sharpe': result_lag['sharpe'], 'win %': result_lag['win_rate']},
            {'variant': 'entry T+1, exit same-bar [G4]',
             'net PnL': result_lag_e['net_pnl'],
             'Sharpe': result_lag_e['sharpe'],
             'win %': result_lag_e['win_rate']},
        ]).set_index('variant'),
        title=f"EXECUTION-LAG ROBUSTNESS — N={best_n}, Z={best_thresh}",
        fmt={'net PnL': '${:,.0f}', 'Sharpe': '{:.2f}', 'win %': '{:.0f}'},
        note='Decomposition: (base - entry T+1) is the ENTRY-side decay; '
             '(entry T+1 - both T+1) is the EXIT-side decay. In close mode '
             'the base is a SAME-BAR result — a real MOC is committed before '
             'the closing print exists — so it is an upper bound until the '
             '19:45/20:45 UTC snapshots exist [L3].')
else:
    for _lb, _rr in ((_lbl1, result_base), (_lbl2, result_close),
                     (_lbl3, result_lag),
                     ('Entry T+1, exit same-bar [G4]', result_lag_e)):
        print(f"  {_lb:<30}: ${_rr['net_pnl']:>10,.0f} "
              f"(Sharpe {_rr['sharpe']:.2f}, Win {_rr['win_rate']:.0f}%)")
print(f"  -> decomposition: (base - entryT+1) = the ENTRY-side decay; "
      f"(entryT+1 - bothT+1) = the EXIT-side decay")
# [R4] the lag run's own trades, trade by trade — compare entry px/z
# against the base run to see exactly where the same-bar profit lives
print_trade_details(sorted(result_lag['trades'], key=lambda t: t['net_pnl'],
                           reverse=True)[:5],
                    f"[R4] NEXT-DAY-FILL RUN — TOP 5 (N={best_n}, Z={best_thresh})",
                    best_thresh)
print_trade_details(sorted(result_lag['trades'], key=lambda t: t['net_pnl'])[:5],
                    f"[R4] NEXT-DAY-FILL RUN — WORST 5 (N={best_n}, Z={best_thresh})",
                    best_thresh)
# ============================================================
# [T3] BASE vs NEXT-DAY-FILL — SAME entry dates, side by side
# ============================================================
# The clearest way to see WHY the lag run differs: match trades by
# entry signal date and show, for each, the entry z (same in both by
# construction) and what the SPREAD had done by the time each run
# actually filled. Same-bar fills at the signal-day print; lag fills
# one trading day later — the z has usually already reverted, so the
# captured move (and PnL) collapses. This makes the decay concrete.
def _by_entry(trs):
    d = {}
    for t in trs:
        d.setdefault(t['entry_date'], t)
    return d
_bmap, _lmap = _by_entry(result_base['trades']), _by_entry(result_lag['trades'])
_common = sorted(set(_bmap) & set(_lmap),
                 key=lambda dt: _bmap[dt]['net_pnl'], reverse=True)
banner(f"[T3] BASE (same-bar) vs LAG (next-day) — matched by entry date")
if not _common:
    print("  (no entry dates common to both runs — the lag shifted every")
    print("   fill onto a different signal; compare the two lists above)")
else:
    print(f"  {'entry date':<12} {'entry z':>8} | "
          f"{'BASE fill':>10} {'BASE net':>10} | {'LAG fill':>10} {'LAG net':>10}")
    print("  " + "-" * 74)
    for _dt in _common[:12]:
        _b, _l = _bmap[_dt], _lmap[_dt]
        print(f"  {_dt:<12} {_b['entry_z']:>+8.2f} | "
              f"{_b['entry_date']:>10} ${_b['net_pnl']:>8,.0f} | "
              f"{_l['exit_date'] if False else _l['entry_date']:>10} "
              f"${_l['net_pnl']:>8,.0f}")
    _bt = sum(_bmap[d]['net_pnl'] for d in _common)
    _lt = sum(_lmap[d]['net_pnl'] for d in _common)
    print("  " + "-" * 74)
    print(f"  matched-total base ${_bt:,.0f} vs lag ${_lt:,.0f} "
          f"-> {(1-_lt/_bt)*100 if _bt else float('nan'):.0f}% of the profit is")
    print(f"  in the FIRST bar. That first-bar chunk is the part a real")
    print(f"  MOC/next-open workflow does NOT capture — the honest edge is")
    print(f"  the LAG column, not the base column.")
# ============================================================
# [P2] THE DECISIVE VARIANT — signal at 15:45 ET, fill at the MOC.
# This is the point on the decay curve a real workflow can trade:
# observe the 15:45 prints, submit MOC before the cutoff, fill at
# 16:00. Runs only when PRECLOSE_ENABLED and the snapshots loaded.
# ============================================================
if PRECLOSE_ENABLED and 'ADR_pre' in df.columns and df['ADR_pre'].notna().sum() > 50:
    banner(f"[P2] PRE-CLOSE SIGNAL (15:45 ET) -> MOC FILL — N={best_n}, Z={best_thresh}")
    _pre_cov = df['ADR_pre'].notna().mean() * 100
    print(f"  pre-close coverage: {_pre_cov:.0f}% of aligned days "
          f"(days without it fall back to NO ENTRY that day)")
    df_pre = df.copy()
    # fair at 15:45: same FAIR_MODE construction, futures leg from the
    # 15:45 SSF print
    _gap_pre = df_pre['Fut_pre'] / df_pre['Fut_1330'] - 1.0
    _fair_pre_sg = (df_pre['2330 TT (Close)'] * (1.0 + df_pre['beta'] * _gap_pre)
                    * ADR_RATIO / df_pre['FX for Fair'])
    _fair_pre_fu = df_pre['Fut_pre'] * ADR_RATIO / df_pre['FX for Fair']
    _fair_pre = _fair_pre_fu if FAIR_MODE == 'futures' else _fair_pre_sg
    if SIGNAL_MODE == 'premium':
        df_pre['Spread (Signal)'] = (df_pre['ADR_pre'] / _fair_pre - 1.0) * 10000.0
    else:
        df_pre['Spread (Signal)'] = df_pre['ADR_pre'] - _fair_pre
    # rows without the pre-close print: kill the signal (no entry)
    df_pre.loc[df_pre['ADR_pre'].isna() | df_pre['Fut_pre'].isna(),
               'Spread (Signal)'] = np.nan
    # FILL at the close prints (Exec Px / Spread (Exec) already are the
    # close in close mode; in open mode use the close columns)
    df_pre['Exec Px'] = df_pre['TSM US (Close)']
    if SIGNAL_MODE == 'premium':
        df_pre['Spread (Exec)'] = (df_pre['Exec Px'] / df_pre['Fair Price']
                                   - 1.0) * 10000.0
    else:
        df_pre['Spread (Exec)'] = df_pre['Exec Px'] - df_pre['Fair Price']
    result_pre = run_backtest(df_pre, best_n, best_thresh)
    print(f"  15:45 signal -> MOC fill : ${result_pre['net_pnl']:>10,.0f} "
          f"(Sharpe {result_pre['sharpe']:.2f}, Win {result_pre['win_rate']:.0f}%, "
          f"{result_pre['n_trades']} trades)")
    print(f"  vs same-bar (upper bound): ${result_base['net_pnl']:>10,.0f} | "
          f"vs next-day (lower bound): ${result_lag['net_pnl']:>10,.0f}")
    print(f"  -> THIS row is the tradeable edge. Positive and a decent")
    print(f"     fraction of same-bar = implementable; ~zero = the edge")
    print(f"     lives inside the closing print itself.")
    print_trade_details(sorted(result_pre['trades'], key=lambda t: t['net_pnl'],
                               reverse=True)[:5],
                        f"[P2] PRECLOSE RUN — TOP 5 (N={best_n}, Z={best_thresh})",
                        best_thresh)
    print_trade_details(sorted(result_pre['trades'], key=lambda t: t['net_pnl'])[:5],
                        f"[P2] PRECLOSE RUN — WORST 5 (N={best_n}, Z={best_thresh})",
                        best_thresh)
elif PRECLOSE_ENABLED:
    print("\n[P2] pre-close variant skipped: snapshots missing or <50 rows")
_decay = (1 - result_lag['net_pnl'] / result_base['net_pnl']) * 100 \
    if result_base['net_pnl'] else float('nan')
if EXEC_TIMING == 'close':
    print(f"  -> [L3] {_decay:.0f}% of the base PnL is GONE by the next print. "
          f"The measured edge lives inside the same bar; how much survives a "
          f"15:45-ET-signal -> MOC-fill workflow is UNMEASURED here. Add the "
          f"19:45/20:45 UTC snapshots and rerun before sizing anything.")
else:
    print("  -> A real fill (minutes after the open) sits between rows 1 and 2.")
close_retention = (result_close['net_pnl'] / result_base['net_pnl'] * 100
                   if result_base['net_pnl'] > 0 else np.nan)
lag_retention = (result_lag['net_pnl'] / result_base['net_pnl'] * 100
                 if result_base['net_pnl'] > 0 else np.nan)
# ============================================================
# [6] PNL CONCENTRATION + [10] DST SPLIT — best parameters
# ============================================================
banner(f"PNL CONCENTRATION & DST SPLIT — N={best_n}, Z={best_thresh}")
top5_share = np.nan
winter_pnl = summer_pnl = 0.0
n_winter = n_summer = 0
if result_base['trades']:
    df_tr = pd.DataFrame(result_base['trades'])
    df_conc = df_tr.sort_values('net_pnl', ascending=False)
    total = df_conc['net_pnl'].sum()
    top5 = df_conc.head(5)
    if total > 0:
        top5_share = top5['net_pnl'].sum() / total * 100
    _conc_line = (f"${top5['net_pnl'].sum():,.0f} of ${total:,.0f} "
                  f"({top5_share:.0f}%)")
    vprint(top5[['entry_date', 'exit_date', 'entry_spread', 'exit_spread',
                 'gross_pnl', 'net_pnl', 'exit_reason']].to_markdown(index=False))
    # [10] DST split: winter entries = US opens 22:30 HKT. If the
    # snapshot job is pegged to 21:30 HKT year-round, winter spreads
    # contain 1h of real index movement -> inflated fake dislocations.
    df_tr['dst'] = df_tr['entry_date'].map(is_us_dst)
    winter = df_tr[~df_tr['dst']]
    summer = df_tr[df_tr['dst']]
    n_winter, n_summer = len(winter), len(summer)
    winter_pnl, summer_pnl = winter['net_pnl'].sum(), summer['net_pnl'].sum()
    w_avg = winter['net_pnl'].mean() if n_winter else 0.0
    s_avg = summer['net_pnl'].mean() if n_summer else 0.0
    kv_table(f"PNL CONCENTRATION & DST SPLIT — N={best_n}, Z={best_thresh}",
             [('top 5 trades', _conc_line,
               'above ~50% means the result rests on a handful of dates — '
               'check the tape on those before sizing'),
              ('winter (US opens 22:30 HKT)',
               f"{n_winter} trades, ${winter_pnl:,.0f} "
               f"(${w_avg:,.0f}/trade)", ''),
              ('summer (US opens 21:30 HKT)',
               f"{n_summer} trades, ${summer_pnl:,.0f} "
               f"(${s_avg:,.0f}/trade)", '')],
             note='[19] The US-open snapshot uses the 13:30 UTC file in US '
                  'summer and the 14:30 UTC file in winter (09:30 ET '
                  'year-round), so a remaining seasonal gap is genuine '
                  'seasonality, not a snapshot-timing artefact.')
# ============================================================
# [15] OPTIMAL PARAMETERS — TRADE ANATOMY (human-readable)
# ============================================================
banner(f"TRADE ANATOMY — N={best_n}, Z={best_thresh}")
if result_base['trades']:
    _dt = pd.DataFrame(result_base['trades'])
    _car = (_dt['funding_cost'] + _dt['borrow_cost']
            + _dt['fx_hedge_cost']).mean()
    _dt['reason_short'] = _dt['exit_reason'].str.split(' \\(').str[0]
    _rc = _dt.groupby('reason_short').agg(
        n=('net_pnl', 'size'), total_net=('net_pnl', 'sum'),
        avg_net=('net_pnl', 'mean'))
    _dt['year'] = _dt['entry_date'].str[:4]
    _yr = _dt.groupby('year').agg(n=('net_pnl', 'size'),
                                  net=('net_pnl', 'sum'),
                                  win=('net_pnl', lambda x: (x > 0).mean()*100))
    _dt['yy'] = _dt['entry_date'].str[:4]
    _dt['mm'] = _dt['entry_date'].str[5:7]
    _piv = _dt.pivot_table(values='net_pnl', index='yy', columns='mm',
                           aggfunc='sum').fillna(0.0)
    _piv = _piv.reindex(columns=sorted(_piv.columns))
    if HTML_OUTPUT and _in_jupyter():
        kv_table(f"TRADE ANATOMY — N={best_n}, Z={best_thresh}",
                 [('per trade (avg)',
                   f"gross ${_dt['gross_pnl'].mean():,.0f} \u2192 exec "
                   f"${_dt['exec_cost'].mean():,.0f} \u2192 carry "
                   f"${_car:,.0f} \u2192 NET ${_dt['net_pnl'].mean():,.0f}",
                   f"median net ${_dt['net_pnl'].median():,.0f}"),
                  ('hold', f"{_dt['hold_days_calendar'].mean():.1f}cd avg",
                   f"{int(_dt['hold_days_calendar'].max())}cd max"),
                  ('leg split (avg)',
                   (f"ADR ${_dt['adr_leg_pnl'].mean():,.0f} / SSF "
                    f"${_dt['fut_leg_pnl'].mean():,.0f}"
                    if _dt['adr_leg_pnl'].notna().any() else 'n/a'),
                   f"avg hedge beta {_dt['entry_beta'].mean():.2f}")])
        show_html_table(
            _rc.rename(columns={'n': 'trades', 'total_net': 'total net',
                                'avg_net': 'avg net'}),
            title='exit reasons',
            fmt={'trades': '{:.0f}', 'total net': '${:+,.0f}',
                 'avg net': '${:+,.0f}'},
            note='A large negative total against few trades is where the '
                 'strategy bleeds — that is what [Y24] position health '
                 'watches for while a trade is still open.')
        show_html_table(
            _yr.rename(columns={'n': 'trades', 'net': 'net PnL',
                                'win': 'win %'}),
            title='by entry year',
            fmt={'trades': '{:.0f}', 'net PnL': '${:+,.0f}', 'win %': '{:.0f}'},
            note='PnL concentrated in one or two years is regime-luck; look '
                 'for a reasonably steady per-year contribution.')
        show_html_table(_piv, title='monthly net PnL by entry month ($)',
                        fmt='{:+,.0f}', heat=True)
    else:
        print(f"  Per trade (avg): gross ${_dt['gross_pnl'].mean():,.0f} | "
              f"exec ${_dt['exec_cost'].mean():,.0f} | carry ${_car:,.0f} | "
              f"net ${_dt['net_pnl'].mean():,.0f}")
        print(f"  Hold {_dt['hold_days_calendar'].mean():.1f}cd avg | "
              f"{int(_dt['hold_days_calendar'].max())}cd max")
        print("\n  Exit reasons:")
        for _r, _row in _rc.iterrows():
            print(f"    {_r:<14} : {int(_row['n']):>3} trades | total "
                  f"${_row['total_net']:>10,.0f}")
        print("\n  By year:")
        for _y, _row in _yr.iterrows():
            print(f"    {_y}: {int(_row['n']):>3} trades | net "
                  f"${_row['net']:>10,.0f} | win {_row['win']:.0f}%")
        print("\n  Monthly net PnL ($):")
        print(_piv.to_markdown(floatfmt=",.0f"))
 
# ============================================================
# TRADE LOGS (VERBOSE) + loss breakdown (always, optimal only)
# ============================================================
losers_all = [tr for tr in result_base['trades'] if tr['net_pnl'] < 0]
n_exec_killed = sum(1 for tr in losers_all
                    if tr['gross_pnl'] > 0 and tr['gross_pnl'] < tr['exec_cost'])
n_carry_killed = sum(1 for tr in losers_all
                     if tr['gross_pnl'] > 0 and tr['gross_pnl'] >= tr['exec_cost'])
n_wrong_way = len(losers_all) - n_exec_killed - n_carry_killed
print(f"\n  Losers at optimal: {len(losers_all)} of {result_base['n_trades']} "
      f"({n_exec_killed} exec-cost-killed, {n_carry_killed} carry-killed, "
      f"{n_wrong_way} wrong-way)")
if VERBOSE:
    scenarios = [
        (best_n, best_thresh, "OPTIMAL ROBUST"),
        (15, 0.5, "MOST TRADES (aggressive)"),
        (20, 1.5, "MEDIUM"),
        (25, 2.0, "CONSERVATIVE"),
    ]
    for s_n, s_thresh, s_label in scenarios:
        print(f"\n{'='*70}")
        print(f"TRADE LOG: {s_label} — N={s_n}, Z={s_thresh}")
        print(f"{'='*70}")
        result_s = run_backtest(df, s_n, s_thresh)
        print(f"  Trades: {result_s['n_trades']} | Net PnL: ${result_s['net_pnl']:,.0f} | "
              f"Win: {result_s['win_rate']:.0f}% | MaxDD(MTM): ${result_s['max_dd_mtm']:,.0f}")
        print(f"  VaR95: ${result_s['var_95']:,.0f} | CVaR95: ${result_s['cvar_95']:,.0f} | "
              f"Worst Day: ${result_s['worst_day']:,.0f} | Active Days: {result_s['n_active_days']}")
        if result_s['trades']:
            df_t = pd.DataFrame(result_s['trades'])
            df_t['direction_label'] = df_t['direction'].map({1: 'Long', -1: 'Short'})
            print(df_t[['entry_date', 'exit_date', 'direction_label', 'entry_spread',
                        'exit_spread', 'hold_days_trading', 'hold_days_calendar',
                        'exit_reason', 'gross_pnl', 'exec_cost', 'total_cost',
                        'net_pnl', 'gamma_at_exit']].to_markdown(index=False))
            losers = df_t[df_t['net_pnl'] < 0]
            if len(losers) > 0:
                print(f"\n  LOSING TRADES ({len(losers)}):")
                for _, trade in losers.iterrows():
                    print(f"    {trade['entry_date']} -> {trade['exit_date']} | "
                          f"{trade['exit_reason']} | Gross=${trade['gross_pnl']:,.0f} | "
                          f"Cost=${trade['total_cost']:,.0f} | Net=${trade['net_pnl']:,.0f}")
                    print(f"      -> {classify_loser(trade)}")
    # Deep dive on optimal losers
    print(f"\n{'='*70}")
    print(f"DEEP DIVE: LOSING TRADES — OPTIMAL N={best_n}, Z={best_thresh}")
    print(f"{'='*70}")
    for trade in losers_all:
        print(f"\n  {'-'*60}")
        dir_label = 'Long Spread' if trade['direction'] == 1 else 'Short Spread'
        print(f"  {trade['entry_date']} -> {trade['exit_date']} | {dir_label} | "
              f"{trade['exit_reason']}")
        print(f"  Spread ${trade['entry_spread']:.2f} -> ${trade['exit_spread']:.2f} | "
              f"gamma {trade['gamma_at_exit']:.3f}")
        print(f"  Gross ${trade['gross_pnl']:,.0f} | Cost ${trade['total_cost']:,.0f} "
              f"(exec ${trade['exec_cost']:,.0f} / funding ${trade['funding_cost']:.0f} "
              f"/ borrow ${trade['borrow_cost']:.0f}) | Net ${trade['net_pnl']:,.0f}")
        entry_idx, exit_idx = trade['entry_day'], trade['exit_day']
        context = df.iloc[max(0, entry_idx-2):min(len(df), exit_idx+2)][
            ['Date', 'TSM US (Open)', 'Exec Px', 'Fair Price',
             'Spread (Exec)', 'fut_gap_ret', 'beta']].copy()
        context['Note'] = ''
        context.loc[context.index == entry_idx, 'Note'] = '<ENTRY'
        context.loc[context.index == exit_idx, 'Note'] = '<EXIT'
        print(context.to_string(index=False))
        print(f"  WHY IT LOST: {classify_loser(trade)}")
# ============================================================
# ADF DIAGNOSTIC (values always computed; detail verbose)
# ============================================================
result_best = run_backtest(df, best_n, best_thresh, track_adf=True)
adf_log = result_best['adf_log']
adf_on_pct = gamma_on = np.nan
if adf_log:
    df_adf = pd.DataFrame(adf_log)
    adf_on_pct = df_adf['system_on'].mean() * 100
    if df_adf['system_on'].any():
        gamma_on = df_adf[df_adf['system_on']]['gamma'].mean()
    vprint("\n" + "=" * 70)
    vprint("ADF DIAGNOSTIC")
    vprint("=" * 70)
    vprint(f"  System ON: {adf_on_pct:.1f}% of {len(df_adf)} days | "
           f"Avg gamma when ON: {gamma_on:.4f}")
    if VERBOSE:
        df_adf['month'] = pd.to_datetime(df_adf['date']).dt.to_period('M')
        monthly = df_adf.groupby('month')['system_on'].agg(['sum', 'count'])
        monthly['pct_on'] = (monthly['sum'] / monthly['count'] * 100).round(1)
        for month, row in monthly.iterrows():
            bar = '#' * int(row['pct_on'] / 5) + '.' * (20 - int(row['pct_on'] / 5))
            print(f"    {month}: {bar} {row['pct_on']:>5.1f}%")
# ======================================================================
# SIGNAL / SPREAD DIAGNOSTICS (values always computed; detail verbose)
# ======================================================================
signal = df['Spread (Signal)'].dropna()
exec_spread = df['Spread (Exec)'].dropna()
common = signal.index.intersection(exec_spread.index)
signal = signal.loc[common]
exec_spread = exec_spread.loc[common]
# Signal vs exec gap = the measured open-print noise (0 where no VWAP)
sig_exec_gap = exec_spread - signal
lag1_ac = exec_spread.diff().dropna().autocorr(lag=1)
spread_bps = (df['Spread (Signal)'] if SIGNAL_MODE == 'premium'   # [Y4]
              else df['Spread (Signal)'] / df['ADR Ref Px'] * 10000)
# [K5] HEDGE-QUALITY METRIC FIXED. The old version correlated
#   (ADR ref / same-day local parity - 1)   <- that is the PREMIUM
#                                              LEVEL (~+19%, a level)
# against beta x fut_gap_ret               <- a daily RETURN (~+-1.5%)
# A level correlated with a return reads ~0.4-0.5 no matter how good
# the hedge is — the 0.49 was an artifact of the metric, NOT a data
# problem. The meaningful test is return-vs-return: does the FAIR
# price (2330 close grown by the SSF gap, FX-converted) MOVE with the
# ADR ref day over day? If the hedge tracks, this is high (~0.9+) and
# the residual std IS the daily spread vol the strategy trades.
adr_ret_dd = df['ADR Ref Px'].pct_change()
fair_ret_dd = df['Fair Price'].pct_change()
valid = adr_ret_dd.notna() & fair_ret_dd.notna()
corr_hedge = adr_ret_dd[valid].corr(fair_ret_dd[valid])
resid_std = (adr_ret_dd[valid] - fair_ret_dd[valid]).std()
if VERBOSE:
    banner("DIAGNOSTIC: SIGNAL / SPREAD QUALITY")
    z_threshold, N_zscore = 1.75, 30
    rolling_mean = signal.rolling(N_zscore).mean()
    rolling_std = signal.rolling(N_zscore).std()
    z_scores = ((signal - rolling_mean) / rolling_std).dropna()
    signal_days = z_scores[z_scores.abs() > z_threshold]
    exec_at_signal = exec_spread.loc[signal_days.index]
    exec_next = exec_spread.shift(-1).loc[signal_days.index]
    predicted_dir = -np.sign(signal_days)
    actual_move = exec_next - exec_at_signal
    correct = ((predicted_dir * actual_move) > 0).dropna()
    if len(correct) > 0:
        print(f"  Predictive power (|Z|>{z_threshold}): {len(correct)} days, "
              f"correct next day {correct.mean()*100:.1f}%")
    adf_exec = adfuller(exec_spread.iloc[-250:].dropna(), maxlag=5)
    print(f"  ADF last 250d: p={adf_exec[1]:.4f} "
          f"({'STATIONARY' if adf_exec[1] < 0.05 else 'NON-STATIONARY'})")
    for lag_ in [1, 2, 5]:
        ac = exec_changes = exec_spread.diff().dropna().autocorr(lag=lag_)
        print(f"  Spread-change autocorr lag {lag_}: {ac:.4f}")
    print(f"  Spread bps: mean {spread_bps.mean():.1f} | std {spread_bps.std():.1f} | "
          f"p95 |bps| {spread_bps.abs().quantile(0.95):.1f} (vs cost {bps_normal:.0f}bps)")
    print(f"  Hedge quality [K5]: corr(ADR ref ret, Fair ret) = {corr_hedge:.3f} "
          f"(return-vs-return; ~0.9+ = hedge tracks) | residual std "
          f"{resid_std*100:.2f}%/day (= the tradable spread vol)")
# [13] implied OU half-life from avg gamma (system ON)
if -1.0 < gamma_on < 0:
    _hl = np.log(0.5) / np.log(1.0 + gamma_on)
    hl_str = f"{_hl:.1f}d"
elif gamma_on <= -1.0:
    hl_str = "<1d (overshoot)"
else:
    hl_str = "n/a"
# ============================================================
# [9][15] EXECUTIVE SUMMARY & VERDICT CHECKLIST
# ============================================================
avg_net_per_trade = (result_base['net_pnl'] / result_base['n_trades']
                     if result_base['n_trades'] else 0.0)
w_per = winter_pnl / max(n_winter, 1)
s_per = summer_pnl / max(n_summer, 1)
# --- verdict checklist (heuristic thresholds — judgement aids, not law) ---
checks = []
if np.isnan(lag_retention):
    checks.append(('INFO', 'Next-day fill retention: n/a (base PnL <= 0)'))
elif lag_retention >= 50:
    checks.append(('OK', f'Next-day fill retention {lag_retention:.0f}% — a real, '
                         f'persistent basis would look like this'))
elif lag_retention >= 20:
    checks.append(('WARN', f'Next-day fill retention {lag_retention:.0f}% — much of '
                           f'the edge decays within a day'))
else:
    checks.append(('FAIL', f'Next-day fill retention {lag_retention:.0f}% — PnL lives '
                           f'almost entirely in the same-day open print, which you '
                           f'cannot reliably hit'))
if np.isnan(close_retention):
    checks.append(('INFO', 'Close-fill retention: n/a (base PnL <= 0)'))
elif close_retention >= 60:
    checks.append(('OK', f'Close-fill retention {close_retention:.0f}% — most of the '
                         f'dislocation is still there at the US close'))
elif close_retention >= 20:
    checks.append(('WARN', f'Close-fill retention {close_retention:.0f}% — a large part '
                           f'of the deviation is gone within the session'))
else:
    checks.append(('FAIL', f'Close-fill retention {close_retention:.0f}% — the deviation '
                           f'is gone by the close; only fast fills near the open '
                           f'could ever capture it'))
if hl_str.startswith('n/a'):
    checks.append(('INFO', 'Implied half-life: n/a (gamma not in (-1, 0))'))
elif hl_str.startswith('<1') or (('d' in hl_str) and hl_str[0] == '0'):
    checks.append(('FAIL', f'Implied half-life {hl_str} — deviations vanish intraday '
                           f'(noise signature)'))
elif float(hl_str.rstrip('d')) < 2:
    checks.append(('WARN', f'Implied half-life {hl_str} — very fast reversion; '
                           f'execution speed decides everything'))
else:
    checks.append(('OK', f'Implied half-life {hl_str} — slow enough to trade at '
                         f'daily frequency'))
if not np.isnan(top5_share) and top5_share > 55:
    checks.append(('FAIL', f'Top-5 trades = {top5_share:.0f}% of PnL — verify those '
                           f'specific prints were tradeable before believing the total'))
elif not np.isnan(top5_share) and top5_share > 35:
    checks.append(('WARN', f'Top-5 trades = {top5_share:.0f}% of PnL — concentrated; '
                           f'check the tape on those dates'))
elif not np.isnan(top5_share):
    checks.append(('OK', f'Top-5 trades = {top5_share:.0f}% of PnL — well spread'))
if cost_sens.get(1.50, 0) > 0:
    checks.append(('OK', f'Still +${cost_sens[1.50]:,.0f} at 1.5x execution cost'))
else:
    checks.append(('WARN', f'PnL flips negative by 1.5x execution cost — verify '
                           f'window-volume/half-spread inputs against the tape'))
if n_winter >= 8 and n_summer >= 8:
    if s_per > 0 and w_per / s_per > 1.5:
        checks.append(('WARN', f'Winter/trade ${w_per:,.0f} vs summer ${s_per:,.0f} '
                               f'({w_per/s_per:.1f}x) on DST-corrected data — investigate '
                               f'whether winter seasonality is real or residual data issues'))
    else:
        checks.append(('OK', f'Winter/trade ${w_per:,.0f} vs summer ${s_per:,.0f} — '
                             f'no obvious DST timing artifact'))
else:
    checks.append(('INFO', f'DST split sample too small ({n_winter}/{n_summer} '
                           f'trades) to judge snapshot timing'))
n_fail = sum(1 for s, _ in checks if s == 'FAIL')
n_warn = sum(1 for s, _ in checks if s == 'WARN')
banner("EXECUTIVE SUMMARY")
print(f"""
DATA
  Sample: {df['Date'].iloc[0]} to {df['Date'].iloc[-1]} | {len(df)} days after filters
  Stale rows dropped: {n_hk} TW-holiday + {n_stale_dropped} equality-dropped snapshots{' (timestamps validated: ' + str(n_eq) + ' equal-price rows KEPT as real)' if _ts_open_ok else ''}
  Fills: {EXEC_TIMING} ({'open print' if EXEC_TIMING == 'open' else 'closing auction / MOC'})
HEADLINE — best robust N={best_n}, Z={best_thresh}
  Net PnL ${result_base['net_pnl']:,.0f} over {result_base['n_trades']} trades \
(${avg_net_per_trade:,.0f}/trade) | Sharpe {result_base['sharpe']:.2f} \
(active-days {result_base['sharpe_active']:.2f}) | Win {result_base['win_rate']:.0f}%
  NOTE: the headline cell is an in-sample argmax — see SELECTION-BIAS
  GUARDS for the plateau statistics (the honest expectation)
  MaxDD ${result_base['max_dd_mtm']:,.0f} | VaR95 ${result_base['var_95']:,.0f} | \
CVaR95 ${result_base['cvar_95']:,.0f} | Worst day ${result_base['worst_day']:,.0f}
  Losers: {n_exec_killed} exec-cost-killed / {n_carry_killed} carry-killed / \
{n_wrong_way} wrong-way
  Net PnL at 1.00x / 1.25x / 1.50x exec cost: \
${cost_sens.get(1.00, 0):,.0f} / ${cost_sens.get(1.25, 0):,.0f} / ${cost_sens.get(1.50, 0):,.0f}
  PnL accounting: two-leg (actual fills) ${result_base['net_pnl']:,.0f} vs \
convergence ${result_conv['net_pnl']:,.0f} — the risk metrics above are two-leg
SIGNAL CHARACTER
  Spread: std {spread_bps.std():.0f}bps, p95 {spread_bps.abs().quantile(0.95):.0f}bps \
vs RT cost {bps_normal:.0f}bps — only the tail clears cost
  Lag-1 autocorr of spread changes: {lag1_ac:.2f} | Avg gamma (ON): {gamma_on:.2f} | \
Half-life: {hl_str}
  ADF gate ON {adf_on_pct:.0f}% of days | Hedge corr {corr_hedge:.2f} \
({HEDGE_LBL} vs the ADR; an INDEX hedge is EXPECTED to be well below the ~0.95 a same-name future gives — that gap is the idiosyncratic residual [HK-H2], not a data problem) | residual {resid_std*100:.2f}%/day
VERDICT CHECKLIST ({n_fail} FAIL / {n_warn} WARN)""")
if HTML_OUTPUT and _in_jupyter():          # [Y27] headline + checklist tables
    show_html_table(
        pd.DataFrame([
            ('sample', f"{df['Date'].iloc[0]} to {df['Date'].iloc[-1]}, "
                       f"{len(df)} days after filters"),
            ('fills', f"{EXEC_TIMING} "
                      + ('(open print)' if EXEC_TIMING == 'open'
                         else '(closing auction / MOC)')),
            ('parameters', f"N={best_n}, Z={best_thresh} "
                           f"\u2014 in-sample argmax; the plateau statistic "
                           f"is the honest expectation"),
            ('net PnL', f"${result_base['net_pnl']:,.0f} over "
                        f"{result_base['n_trades']} trades "
                        f"(${avg_net_per_trade:,.0f}/trade)"),
            ('Sharpe / win', f"{result_base['sharpe']:.2f} "
                             f"(active-days {result_base['sharpe_active']:.2f})"
                             f" / {result_base['win_rate']:.0f}%"),
            ('risk', f"MaxDD ${result_base['max_dd_mtm']:,.0f} | VaR95 "
                     f"${result_base['var_95']:,.0f} | CVaR95 "
                     f"${result_base['cvar_95']:,.0f} | worst day "
                     f"${result_base['worst_day']:,.0f}"),
            ('losers', f"{n_exec_killed} exec-cost-killed / "
                       f"{n_carry_killed} carry-killed / {n_wrong_way} "
                       f"wrong-way"),
            ('cost sensitivity', f"1.00x ${cost_sens.get(1.00, 0):,.0f} | "
                                 f"1.25x ${cost_sens.get(1.25, 0):,.0f} | "
                                 f"1.50x ${cost_sens.get(1.50, 0):,.0f}"),
            ('accounting', f"two-leg ${result_base['net_pnl']:,.0f} vs "
                           f"convergence ${result_conv['net_pnl']:,.0f} "
                           f"\u2014 risk metrics are two-leg"),
            ('signal', f"spread sd {spread_bps.std():.0f}bps, p95 "
                       f"{spread_bps.abs().quantile(0.95):.0f}bps vs RT cost "
                       f"{bps_normal:.0f}bps \u2014 only the tail clears cost"),
            ('reversion', f"lag-1 autocorr {lag1_ac:.2f} | gamma (ON) "
                          f"{gamma_on:.2f} | half-life {hl_str}"),
            ('gate / hedge', f"gate ON {adf_on_pct:.0f}% of days | hedge corr "
                             f"{corr_hedge:.2f} | residual "
                             f"{resid_std*100:.2f}%/day"),
        ], columns=['', 'reading']).set_index(''),
        title=f"EXECUTIVE SUMMARY \u2014 {INSTRUMENT}", fmt='{}')
    show_html_table(
        pd.DataFrame([{'check': _t.split('\u2014')[0].strip()
                       if '\u2014' in _t else _t,
                       'verdict': _badge(_s, {'FAIL': 'bad', 'WARN': 'warn',
                                              'OK': 'ok'}.get(_s, 'mut')),
                       'detail': (_t.split('\u2014', 1)[1].strip()
                                  if '\u2014' in _t else '')}
                      for _s, _t in checks]).set_index('check'),
        title=f"VERDICT CHECKLIST \u2014 {n_fail} FAIL / {n_warn} WARN",
        fmt='{}')
else:
    for _s, _t in checks:
        print(f"  [{_s:<4}] {_t}")
print(f"""
BOTTOM LINE
  {'The backtest arithmetic is consistent, but the FAIL items above mean the measured edge is not yet demonstrably capturable at real fills. Validate the top-PnL dates on intraday quotes before sizing anything.' if n_fail > 0 else 'No hard failures. Verify cost inputs and the flagged WARN items, then consider a small pilot sizing from the robust plateau, not the single best cell.'}
""")
# ============================================================
# [20] VISUALIZATION — optimal parameters (always on)
# ============================================================
_tr = pd.DataFrame(result_base['trades']) if result_base['trades'] else pd.DataFrame()
# [W5] the z-score sits directly BELOW the spread panel and shares its
# x-axis, so an entry marker on the spread lines up vertically with the
# z-score that produced it — no flipping between two figures.
fig, axes = plt.subplots(6, 1, figsize=(14, 26),
                         gridspec_kw={'height_ratios': [1, 1.35, 0.85, 1, 0.6, 1]})
# Panel 1: ADR open vs futures-implied fair price
ax = axes[0]
ax.plot(df['Date_dt'], df['ADR Ref Px'], label=f'ADR {EXEC_TIMING} price', lw=0.8)
ax.plot(df['Date_dt'], df['Fair Price'], label='Futures-implied fair price', lw=0.8, alpha=0.8)
ax.set_title(f'ADR {EXEC_TIMING} vs {FAIR_MODE} fair price')
ax.legend(loc='upper left')
ax.grid(alpha=0.3)
# Panel 2: spread in bps with entries/exits and the round-trip cost band
ax = axes[1]
_sb = (df['Spread (Signal)'] if SIGNAL_MODE == 'premium'      # [W3] already bps
       else df['Spread (Signal)'] / df['ADR Ref Px'] * 10000)
ax.plot(df['Date_dt'], _sb, lw=0.6, color='gray',
        label=f"Spread (bps of ADR{'' if SIGNAL_MODE=='premium' else ', from $'})")
ax.axhline(0, color='black', lw=0.6)
ax.axhline(bps_normal, color='red', ls='--', lw=0.8, label=f'RT cost {bps_normal:.0f}bps')
ax.axhline(-bps_normal, color='red', ls='--', lw=0.8)
if len(_tr):
    _ed = df['Date_dt'].iloc[_tr['entry_day']].values
    _eb = _sb.iloc[_tr['entry_day']].values
    _long = (_tr['direction'] == 1).values
    ax.scatter(_ed[_long], _eb[_long], marker='^', color='green', s=45,
               zorder=5, label='Entry long spread')
    ax.scatter(_ed[~_long], _eb[~_long], marker='v', color='red', s=45,
               zorder=5, label='Entry short spread')
    _xd = df['Date_dt'].iloc[_tr['exit_day']].values
    _xb = _sb.iloc[_tr['exit_day']].values
    ax.scatter(_xd, _xb, marker='x', color='blue', s=35, zorder=5, label='Exit')
    # [U7] integrity: a marker can only vanish if the spread is NaN on that
    # row, so count what actually got drawn and say so on the chart.
    _n_e = int(np.isfinite(_eb).sum())
    _n_x = int(np.isfinite(_xb).sum())
    ax.text(0.005, 0.02, f"{len(_tr)} trades: {_n_e} entry / {_n_x} exit markers "
            f"drawn ({int(_long.sum())} long, {int((~_long).sum())} short)",
            transform=ax.transAxes, fontsize=8, color='#333',
            bbox=dict(fc='white', ec='#bbb', alpha=0.85, pad=2))
    if _n_e < len(_tr) or _n_x < len(_tr):
        print(f"[U7] WARNING: chart drew {_n_e}/{len(_tr)} entry and "
              f"{_n_x}/{len(_tr)} exit markers — the spread series is NaN on "
              f"the missing rows")
    else:
        print(f"[U7] chart panel 2: all {len(_tr)} trades plotted "
              f"({int(_long.sum())} long / {int((~_long).sum())} short)")
ax.set_title(f'Spread [{SIGNAL_MODE}] with entries/exits — a tradeable edge '
             f'must clear the red cost band ({bps_normal:.0f} bps RT)')
ax.legend(loc='upper left', ncol=3, fontsize=8)
ax.grid(alpha=0.3)
# Panel 3: equity curve and drawdown at optimal parameters
# [W5] Panel 3: rolling z-score, x-axis shared with the spread panel above
ax = axes[2]
_sigz = pd.Series(df['Spread (Signal)'].values)
_zmuz = _sigz.rolling(best_n).mean().shift(1)
_zsdz = _sigz.rolling(best_n).std(ddof=0).shift(1)
_zz = (_sigz - _zmuz) / _zsdz.replace(0, np.nan)
ax.plot(df['Date_dt'], _zz, lw=0.7, color='#444')
for _t in (best_thresh, -best_thresh):
    ax.axhline(_t, color='red', ls='--', lw=0.9)
ax.axhline(0, color='black', lw=0.7)
ax.fill_between(df['Date_dt'], -best_thresh, best_thresh, color='green',
                alpha=0.06, label=f'no-trade band +/-{best_thresh}')
if not _tr.empty:
    _zed = df['Date_dt'].iloc[_tr['entry_day']].values
    _zeb = _zz.iloc[_tr['entry_day']].values
    _zlong = (_tr['direction'] == 1).values
    ax.scatter(_zed[_zlong], _zeb[_zlong], marker='^', color='green', s=42, zorder=5)
    ax.scatter(_zed[~_zlong], _zeb[~_zlong], marker='v', color='red', s=42, zorder=5)
ax.set_title(f'Rolling z-score (N={best_n}) with the +/-{best_thresh} entry band'
             f' — same x-axis as the panel above')
ax.set_ylabel('z'); ax.grid(alpha=0.3); ax.legend(fontsize=8, loc='upper left')
ax.set_xlim(axes[1].get_xlim())
# Panel 4: equity curve and drawdown at optimal parameters
ax = axes[3]
_eq = result_base['daily_equity']
ax.plot(df['Date_dt'], _eq, color='navy', lw=1.0, label='Equity ($)')
_dd = _eq - np.maximum.accumulate(_eq)
ax2 = ax.twinx()
ax2.fill_between(df['Date_dt'], _dd, 0, color='red', alpha=0.25, label='Drawdown ($)')
ax.set_title(f'Equity curve & drawdown — N={best_n}, Z={best_thresh}')
ax.legend(loc='upper left')
ax2.legend(loc='lower left')
ax.grid(alpha=0.3)
# Panel 5: [23] ADF gate — when was the system ON/OFF over the period
ax = axes[4]
if result_best['adf_log']:
    _al = pd.DataFrame(result_best['adf_log'])
    _ad = df['Date_dt'].iloc[_al['day']].values
    _on = _al['system_on'].astype(int).values
    ax.fill_between(_ad, 0, _on, step='mid', color='seagreen', alpha=0.6,
                    label='ADF ON (tradeable)')
    ax.fill_between(_ad, _on, 1, step='mid', color='indianred', alpha=0.5,
                    label=('ADF OFF (no new entries'
                           + ('; positions force-closed)'
                              if ADF_EXIT_POLICY == 'force_exit'
                              else '; open positions kept)')))
    ax.set_ylim(-0.05, 1.05)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(['OFF', 'ON'])
    _pct_on = _on.mean() * 100
    # [Z5] ADF kept as a CHECK (not gating unless GATE_MODE=adf_*):
    _adf_pass = (_al['adf_pval'] < ADF_PVALUE).mean() * 100
    print(f"[Z5] ADF check (informational): p<{ADF_PVALUE} on "
          f"{_adf_pass:.0f}% of days on the "
          f"{'level' if GATE_MODE == 'adf_level' else 'deviation'} object | "
          f"gate actually used: {GATE_MODE} (ON {_pct_on:.0f}%)")
    ax.set_title(f'Regime gate [{GATE_MODE}, {ADF_EXIT_POLICY}] — ON {_pct_on:.0f}% of days')
    ax.legend(loc='lower left', fontsize=8)
    # shade the OFF spans on the spread panel too
    _off_runs = []
    _in_off = False
    for _k in range(len(_on)):
        if _on[_k] == 0 and not _in_off:
            _start = _ad[_k]
            _in_off = True
        elif _on[_k] == 1 and _in_off:
            _off_runs.append((_start, _ad[_k]))
            _in_off = False
    if _in_off:
        _off_runs.append((_start, _ad[-1]))
    for _s, _e in _off_runs:
        axes[1].axvspan(_s, _e, color='red', alpha=0.10)
# Panel 6: per-trade net PnL, winter entries highlighted
ax = axes[5]
if len(_tr):
    _tr['dst'] = _tr['entry_date'].map(is_us_dst)
    _cols = np.where(_tr['dst'], 'steelblue', 'darkorange')
    ax.bar(pd.to_datetime(_tr['exit_date']), _tr['net_pnl'], width=6, color=_cols)
    ax.axhline(0, color='black', lw=0.6)
ax.set_title('Per-trade net PnL (blue = summer entry, orange = winter entry)')
ax.grid(alpha=0.3)
plt.tight_layout()
try:
    plt.savefig(CHART_PATH, dpi=150, bbox_inches='tight')
    print(f"\n[CHART] Saved 4-panel chart to {CHART_PATH}")
except Exception as e:
    print(f"\n[CHART] Could not save chart ({e}); showing only.")
plt.show()
# [W5] the standalone z-score figure was merged into panel 3 above so it
# lines up with the entry markers; nothing is plotted twice.
# ============================================================
# [L1] DECISION SCORECARD — read THIS first, detail above is evidence
# ============================================================
print("\n\n" + "#" * 70)
print(f"#  DECISION SCORECARD — {INSTRUMENT}  ({ADR_TICKER} vs {ORD_TICKER})")
print("#" * 70)
# --- data health ---
sc('INFO', 'sample', f"{df['Date'].iloc[0]} to {df['Date'].iloc[-1]} "
   f"({len(df)} aligned days)")
try:
    sc('PASS' if _n_ex_spine > 0 else 'FAIL', 'hedge-leg dividends',
       f"{_n_ex_spine} ex-date(s), {_yield_spine*100:.2f}%")
except Exception:
    pass
# --- signal ---
try:
    sc('INFO', 'premium level / dev sigma',
       f"{_sb_chk.mean():+.0f} bps level, {_dev_sigma_bps:.0f} bps deviation sigma")
    _fxpct = _fx_floor_bps / _dev_sigma_bps * 100 if _dev_sigma_bps else float('nan')
    sc('PASS' if _fxpct < 20 else 'WARN', 'FX noise share of signal',
       f"{_fxpct:.0f}% (floor set to {MIN_ENTRY_DEV_BPS} bps)")
except Exception:
    pass
# --- cost vs signal: the single most important economic ratio ---
try:
    _ratio = bps_normal / _dev_sigma_bps
    sc('PASS' if _ratio < 0.5 else 'WARN' if _ratio < 0.8 else 'FAIL',
       'round-trip cost / deviation sigma',
       f"{bps_normal:.0f} / {_dev_sigma_bps:.0f} = {_ratio:.2f} sigma")
except Exception:
    pass
# --- headline result ---
_w = [t['net_pnl'] for t in result_base['trades']]
sc('INFO', f'best params (plateau-checked)', f"N={best_n}, Z={best_thresh}")
sc('PASS' if result_base['net_pnl'] > 0 else 'FAIL', 'net PnL (same-bar)',
   f"${result_base['net_pnl']:,.0f} | Sharpe {result_base['sharpe']:.2f} "
   f"(active {result_base.get('sharpe_active', float('nan')):.2f}) | "
   f"win {result_base['win_rate']:.0f}% | {result_base['n_trades']} trades")
if _w:
    sc('WARN' if abs(min(_w)) > 0.5 * max(_w) else 'PASS', 'tail risk',
       f"worst trade ${min(_w):,.0f} vs best ${max(_w):,.0f} | "
       f"maxDD ${result_base['max_dd_mtm']:,.0f}")
# --- the viability question ---
try:
    sc('PASS' if result_lag['net_pnl'] > 0 else 'FAIL',
       'IMPLEMENTABILITY (fills one day later)',
       f"same-bar ${result_base['net_pnl']:,.0f} -> entry-T+1 "
       f"${result_lag_e['net_pnl']:,.0f} -> both-T+1 ${result_lag['net_pnl']:,.0f}")
except Exception:
    pass
try:
    sc('PASS' if result_pre['net_pnl'] > 0 else 'FAIL',
       '15:45 signal -> MOC fill [P2]', f"${result_pre['net_pnl']:,.0f}")
except Exception:
    sc('INFO', '15:45 signal -> MOC fill [P2]',
       'not run (PRECLOSE_ENABLED=False or files missing)')
# --- direction asymmetry ---
try:
    _lp = sum(t['net_pnl'] for t in result_base['trades'] if t['direction'] == 1)
    _sp = sum(t['net_pnl'] for t in result_base['trades'] if t['direction'] == -1)
    sc('INFO', 'direction split',
       f"LONG spread ${_lp:,.0f} vs SHORT spread ${_sp:,.0f}")
except Exception:
    pass
_order = {'FAIL': 0, 'WARN': 1, 'PASS': 2, 'INFO': 3}
_rank = {'FAIL': 'bad', 'WARN': 'warn', 'PASS': 'ok', 'INFO': 'info'}
for _lv, _k, _v in sorted(SCORECARD, key=lambda x: _order.get(x[0], 9)):
    say(f"{_k:<38} {_v}", _rank.get(_lv, 'info'))
_nf = sum(1 for l, _, _ in SCORECARD if l == 'FAIL')
_nw = sum(1 for l, _, _ in SCORECARD if l == 'WARN')
if _nf:
    note_block(f"VERDICT — {_nf} FAIL / {_nw} WARN", [
        "Do NOT size this up until the FAIL lines are resolved. Each maps",
        "to a numbered block in the detail above ([K5]/[K6]/[L2]/[P2]).",
    ])
elif _nw:
    note_block(f"VERDICT — 0 FAIL / {_nw} WARN", [
        "Mechanically sound; the WARN lines are the honest caveats to put",
        "in front of a reviewer.",
    ])
else:
    say("VERDICT: all checks pass at these parameters.", 'ok')
# [U3] Unicode glyphs as CONSTANTS so no f-string ever contains a backslash
# (Python <=3.11 rejects "\uXXXX" inside an f-string expression; using names
# keeps the desk output identical on every interpreter version).
_BOX = dict(tl="\u250c", tr="\u2510", bl="\u2514", br="\u2518",
            h="\u2500", v="\u2502", ml="\u251c", mr="\u2524")
# ############################################################################
# v31.12 — CHANGES FROM v31.11
# ############################################################################
# Everything below this banner is tagged [Y..] so it can be grepped.
#
# FIXED IN PLACE (above, inside the v31.11 body):
#   [Y1] rows-per-year audit raised a false positive on the FIRST partial
#        year (2024 has 11 rows because the sample STARTS 2024-12-16). The
#        old test excluded only the LAST year. A year is now "full" only if
#        the sample actually spans it.
#   [Y2] why_no_trades printed |dev| with a forced '+', so a negative
#        deviation displayed as a positive one (2026-07-02 read "dev +454"
#        when the true deviation was -447, next to z -2.77). The signed
#        value is now carried through; the sort still uses the magnitude.
#   [Y3] the PLATEAU line ranked cells WITHOUT the MIN_N_SELECT mask that
#        the selector then applies, so it advertised N=10 / Z=2.0 and the
#        selector refused it. Same mask both places. Both 3x3 neighbourhood
#        means are now DE-DUPLICATED: adjacent thresholds often hold the
#        identical trade list (N=25 at Z=0.50 and Z=0.75 do), and averaging
#        one result twice is not evidence of stability.
#   [Y6] COMPOSITE selection (SELECT_MODE='composite') — "more trades,
#        higher win rate, higher PnL" scored as an explicit weighted
#        percentile rank, with an EDGE-OF-GRID warning, because Z=0.50 is
#        the bottom of THRESHOLD_VALUES and the real optimum may be off it.
#
# ADDED BELOW:
#   [Y4]  HTML table layer, DEFINED AT THE TOP OF THE FILE and WIRED IN, so
#         the output is tables without calling anything: show_matrix() now
#         renders every grid matrix as a HEAT MAP, the data-cleansing
#         outliers and the DATA INTEGRITY action list render as tables, the
#         composite candidates render as a table, print_trade_details()
#         leads with a summary table, and gap_check_card() fires itself
#         after the [J5] report. HTML_OUTPUT=False restores plain text, and
#         outside Jupyter every one of them falls back to the old print.
#   [Y5]  show_grid_html()      the matrices again, on demand
#   [Y7]  retired in [Y22] — see below
#   [Y8]  setup_manual()        HTML card
#   [Y9]  add_day()             FULL REPLACEMENT:
#           [Y9a] INPUT SANITY GUARDS. Refuses to score a snapshot whose SSF
#                 print is >12% off the 13:30 anchor, whose |premium| >
#                 3,000bps or whose |z| > 8, and prints the fair-price
#                 decomposition so a fat finger is visible immediately. This
#                 is the 2026-07-28 US-open row: fair 36,308.64 x 32.293 / 5
#                 implies an SSF input of 234,503 = 2,345.03 typed without
#                 the decimal point. It now REFUSES instead of printing
#                 "ENTER LONG, edge +11,162bps" off a z of -47.
#           [Y9b] gamma exit uses the LEVEL sigma (the z-window sd), as
#                 run_backtest does; v31.11 used the CHANGE sigma from _gate.
#           [Y9c] gamma hurdle is carry x days-to-next-mark (Fri -> 3).
#           [Y9d] entry needs |z| > thr (strict), as run_backtest.
#           [Y9e] ENTER hints away from the exec point are tagged INDICATIVE
#                 (the grid was fit on CLOSE fills; [L3] showed 45% of the
#                 edge is gone by the next print).
#           [Y9f] the hint prints the z-scaled notional, snapped to whole
#                 SSF contracts, like [D3]/[E2].
#           [Y9h] the MARK block prints the substituted P&L arithmetic.
#           [Y9i] the ENTER hint prints BOTH hurdles — the round trip AND
#                 the min_dev_bps floor that actually gates the entry.
#   [Y10] set_dividend()        enter TW ex-date / ADR ex-date / % ONCE;
#                               div_carry (SIGNAL correction, never cash) and
#                               div_cash (REAL TAIFEX cash, ex-date only) are
#                               then filled automatically.
#   [Y11] exit_pos()            prints every substituted formula so each
#                               paper P&L can be checked by hand.
#   [Y12] run_backtest_lots()   sizing up / partial unwind while already in a
#                               position (45% of rows were blocked by
#                               "already in a position"). SELF-TEST: with
#                               max_adds=0 it MUST reproduce run_backtest.
#   [Y13] scrub_ledger()        find + remove fat-fingered ledger rows (a
#                               saved bad print poisons mu/sd for N rows)
#   [Y14] trades floor = the GRID-MEAN trade count across selectable rows;
#                               COMPOSITE_WEIGHTS now put PnL and WIN RATE
#                               at double weight
#   [Y15] the whole paper desk is DEFINED BEFORE THE RUN — a report-section
#                               exception (UMC path) can no longer leave
#                               setup_manual()/form() undefined
#   [Y16] INSTRUMENT switch moved to the VERY TOP of the file
#   [Y17] per-snapshot execution FX (fx_open/fx_1945/fx_close + form
#                               fields): SIGNAL stays on the 13:30 fixing
#                               [D2], EXECUTION uses the USDTWD you trade at
#   [Y18] add_day renders as an HTML DAY CARD in Jupyter (header, snapshot
#                               table with action badges, copyable command
#                               block, collapsible full detail)
#   [Y19] form(): edit-a-day guidance, Delete-this-date / Ledger buttons —
#                               re-scoring a date OVERWRITES it by design
#   [Y20] zchart()              rolling premium + N-mean + entry band and
#                               the rolling z itself, your typed days and
#                               fills marked, backtest window convention
#   [Y21] fx_fill(date, fx)     spot_next_open reality: the hedge FX deals
#                               at the NEXT TW open, which does not exist
#                               when you record the fill. enter/exit accept
#                               a PROVISIONAL fx and remind you; fx_fill
#                               amends it next morning and adjusts closed
#                               P&L by the exact SSF-leg delta. The SIGNAL
#                               always stays on the 13:30 fixing [D2].
#   [Y22] SUSPECT-GAP HEURISTICS REMOVED (user-verified: both capture jobs
#                               resolve the front month by the same Taipei
#                               trading date, so same-date rows are always
#                               the same contract; overnight gaps are REAL
#                               moves). No more gap-based entry blocking,
#                               no 'repair' overwriting real US-close
#                               fills, no [J5] report, no gap card. Only
#                               the EXACT [K7] contract-label test remains.
#   [Y24] POSITION HEALTH — the regime gate is ENTRY-ONLY
#                               (ADF_EXIT_POLICY='entry_only'), so nothing
#                               watched a trade after it was on. Every day
#                               in a position the desk now compares GATE,
#                               HALF-LIFE, MEAN DRIFT (re-rating), Z PATH
#                               and CARRY-vs-EDGE-LEFT against the state at
#                               ENTRY, and grades HEALTHY / WATCH /
#                               DETERIORATING. ADVISORY ONLY: it adds no
#                               exit rule, because an untested exit has an
#                               unknown win rate and drawdown. If a hint
#                               keeps proving right, put it in
#                               run_backtest, re-run the grid, and look at
#                               what it does to the numbers first.
#   [Y25] MARK TO MARKET table — every P&L line substituted (shares, SSF
#                               contracts, ADR leg, SSF leg, dividend,
#                               gross, fees, carry, net-if-closed) so a
#                               mark can be checked by hand, in the card
#                               and in the text fallback.
#   [Y29] FX, SIMPLIFIED + BOTH FAIR MODES VERIFIED. FX_MARK_MODE='fixing'
#                               (default) makes the desk mark exactly as the
#                               backtest does — the 13:30 TW-close fixing for
#                               fair, premium, z AND marks — so the optional
#                               per-snapshot FX boxes change nothing unless
#                               you opt into 'snapshot'. The only other FX
#                               you need is the next TW open, entered after
#                               the fact with fx_fill(). _fair() now carries
#                               the line-by-line equivalence proof for
#                               FAIR_MODE='futures' and 'spot_gap', and the
#                               warning that a non-1.0 beta would break the
#                               spot_gap equivalence.
#   [Y28] THIRD READABILITY PASS — every remaining wall of prints becomes a
#                               table: RUN CONFIG, COST & REGIME SETTINGS,
#                               [X2] round trip RANKED (with the c/share
#                               sanity column), [M5] risk-aware candidates,
#                               [J6] direction split, [S3] profit-taking
#                               scan, [H5] MAE, [R8] profit left on the
#                               table, [X6] entry verdicts + closest calls,
#                               PnL-mode, roll impact, cost sensitivity,
#                               execution lag, trade anatomy (economics /
#                               exit reasons / by year / monthly heat map)
#                               and the DST split. New kv_table() helper for
#                               the label+reading shape. Also: the Styler
#                               INDEX column was inheriting the bold
#                               uppercase HEADER style — that is the "bold
#                               and packed" look in the executive summary —
#                               so row labels now get body styling; and the
#                               [R6] time-stop warning prints the actual row
#                               spacing (a holiday or dropped row can carry
#                               a hold past the cap with nothing wrong)
#                               instead of just saying "investigate".
#   [Y27] SECOND READABILITY PASS on the input-diagnostics wall: [K6][K7],
#                               [P1][D2][M1], [S2][T1], [W1], [R7], [L2],
#                               [U5], [X4] and [Z4] all collect into ONE
#                               'INPUT DIAGNOSTICS' table (check / reading /
#                               note) instead of two dozen loose prints;
#                               [J4] TR-field selection is one table with a
#                               SELECTED badge; [R5] ex-date behaviour is
#                               one row per ex-date instead of three lines;
#                               the executive summary and verdict checklist
#                               are tables. Gap-outlier lines no longer say
#                               'possible contract mismatch' — per [Y22]
#                               they are real moves and nothing acts on
#                               them.
#   [Y26] data cleansing compressed to a summary table, a flags table and
#                               a rows-to-check table; outliers explained
#                               by holiday gaps are one count, not a list.
#   [Y23] READABILITY PASS: the C4 audit stops chattering inline (flags +
#                               outliers land in two tables), the top-15
#                               deviation days render as ONE table, the
#                               grid-search cost header is a settings
#                               table, and the [Q2]/[R4] trade lists show
#                               the summary table only (VERBOSE=True for
#                               the line-by-line re-derivation).
# ############################################################################
 
 
# ============================================================================
# [Y6] MULTI-CRITERIA PLATEAU SELECTION
# ============================================================================
# (COMPOSITE_WEIGHTS lives in the CONFIG block above — the selection itself
#  now runs inline in OPTIMAL PARAMETER SELECTION. This is the POST-HOC
#  version: re-rank with different weights without re-running the grid.)
 
def select_composite(weights=None, show=8, rerun=False):
    """[Y6] Rank every constraint-passing cell by a WEIGHTED PERCENTILE-RANK
    COMPOSITE of Net PnL, Sharpe, win rate, trade count, Calmar and the 95%
    lower bound — i.e. exactly the "more trades, higher win rate, higher PnL"
    ask, made explicit — then require LOCAL STABILITY via the 3x3
    neighbourhood mean of that composite, with two fixes v31.11's ranking
    did not have:
 
      1. DUPLICATE-CELL DE-DUP.  N=25 Z=0.50 and Z=0.75 hold the IDENTICAL
         trade list (same PnL, same count) — v31.11's neighbourhood mean
         counted that one result twice and called it stability. Duplicate
         (pnl, trades) pairs inside a block now count once.
      2. EDGE REPORT.  If the winner sits on the grid BOUNDARY the true
         optimum may be off-grid; the function says so and names the axis to
         extend (e.g. THRESHOLD_VALUES below 0.5) instead of silently
         accepting the edge.
 
    Constraints reuse the run's own mask: >= max(MIN_TRADES, ..) trades,
    N >= MIN_N_SELECT, >= MIN_TRADES_PER_YEAR, win >= MIN_WIN_RATE_SELECT,
    |MaxDD| <= MAX_DD_SELECT_PCT of deployed, PnL > 0.
 
    rerun=True re-runs run_backtest on the chosen cell and prints its
    headline so you can adopt it without re-running the whole grid.
    Returns (n, z)."""
    _g = globals()
    w = dict(COMPOSITE_WEIGHTS)
    w.update(weights or {})
    _n_ok = _np.array([[(nv >= MIN_N_SELECT) for _tv in THRESHOLD_VALUES]
                       for nv in N_VALUES])
    _pass = ((_g['results_trades'] >= _g['_eff_min_trades']) & _n_ok
             & (_g['results_tpy'] >= MIN_TRADES_PER_YEAR)
             & (_g['results_winrate'] >= MIN_WIN_RATE_SELECT)
             & (_np.abs(_g['results_ddpct']) <= MAX_DD_SELECT_PCT)
             & (_g['results_pnl'] > 0))
    _cal = _g['results_pnl'] / _np.maximum(_np.abs(_g['results_maxdd']), 1.0)
    _metrics = dict(pnl=_g['results_pnl'], sharpe=_g['results_sharpe'],
                    win=_g['results_winrate'], trades=_g['results_trades'],
                    calmar=_cal, lb=_g['results_lb'])
    # percentile-rank each metric over the PASSING cells only
    _flatpass = _np.where(_pass)
    if len(_flatpass[0]) == 0:
        print('[Y6] no cell passes the constraints — loosen them first')
        return None
    _score = _np.full(_g['results_pnl'].shape, _np.nan)
    _vals = {k: m[_pass] for k, m in _metrics.items()}
    for a, b in zip(*_flatpass):
        s, tw = 0.0, 0.0
        for k, m in _metrics.items():
            v = _vals[k]
            if len(v) > 1 and _np.nanstd(v) > 0:
                pr = float((v <= m[a, b]).mean())    # percentile rank in [0,1]
            else:
                pr = 0.5
            s += w[k] * pr
            tw += w[k]
        _score[a, b] = s / tw
    # neighbourhood mean with duplicate de-dup
    _nb = _np.full_like(_score, _np.nan)
    for a in range(_score.shape[0]):
        for b in range(_score.shape[1]):
            if not _np.isfinite(_score[a, b]):
                continue
            seen, vals = set(), []
            for i in range(max(a - 1, 0), min(a + 2, _score.shape[0])):
                for j in range(max(b - 1, 0), min(b + 2, _score.shape[1])):
                    if not _np.isfinite(_score[i, j]):
                        continue
                    key = (round(float(_g['results_pnl'][i, j]), 2),
                           int(_g['results_trades'][i, j]))
                    if key in seen:
                        continue           # identical trade list — count once
                    seen.add(key)
                    vals.append(_score[i, j])
            if len(vals) >= 2:
                _nb[a, b] = float(_np.mean(vals))
    _flat = sorted([( _nb[a, b], _score[a, b], a, b)
                    for a in range(_nb.shape[0]) for b in range(_nb.shape[1])
                    if _np.isfinite(_nb[a, b])], reverse=True)
    rows = []
    for _v, _own, a, b in _flat[:show]:
        rows.append(dict(N=N_VALUES[a], Z=THRESHOLD_VALUES[b],
                         nbhd_score=round(_v, 3), own_score=round(_own, 3),
                         PnL=round(float(_g['results_pnl'][a, b])),
                         Sharpe=round(float(_g['results_sharpe'][a, b]), 2),
                         win_pct=round(float(_g['results_winrate'][a, b]), 1),
                         trades=int(_g['results_trades'][a, b]),
                         Calmar=round(float(_cal[a, b]), 2),
                         LB_yr=round(float(_g['results_lb'][a, b]))))
    show_html_table(_pd.DataFrame(rows).set_index(['N', 'Z']),
                    title='[Y6] COMPOSITE plateau candidates '
                          f'(weights {w})',
                    fmt={'PnL': '{:,.0f}', 'LB_yr': '{:,.0f}',
                         'nbhd_score': '{:.3f}', 'own_score': '{:.3f}',
                         'Sharpe': '{:.2f}', 'win_pct': '{:.1f}',
                         'Calmar': '{:.2f}', 'trades': '{:.0f}'},
                    note='Score = weighted percentile rank of PnL / Sharpe / '
                         'win / trades / Calmar / LB over the passing cells; '
                         'ranked by its de-duplicated 3x3 neighbourhood mean. '
                         'With only ~24 trades the top candidates are within '
                         'noise of each other — treat a swap as taste, not '
                         'edge, and quote the plateau mean ([33]) either way.')
    _v, _own, a, b = _flat[0]
    n_sel, z_sel = N_VALUES[a], THRESHOLD_VALUES[b]
    _edges = []
    if a in (0, len(N_VALUES) - 1):
        _edges.append(f"N={n_sel} is the grid's {'lowest' if a == 0 else 'highest'} "
                      f"lookback — extend N_VALUES {'below' if a == 0 else 'above'} it")
    if b in (0, len(THRESHOLD_VALUES) - 1):
        _edges.append(f"Z={z_sel} is the grid's {'lowest' if b == 0 else 'highest'} "
                      f"threshold — extend THRESHOLD_VALUES "
                      f"{'below' if b == 0 else 'above'} it (and add midpoints: "
                      f"neighbouring Z cells often hold IDENTICAL trades, so the "
                      f"grid is coarser than it looks)")
    print(f"[Y6] composite pick: N={n_sel}, Z={z_sel}")
    for _e in _edges:
        print(f"     EDGE WARNING: {_e} and re-run before trusting this cell")
    if rerun:
        _r = run_backtest(df, n_sel, z_sel)
        _tp = sum(t['net_pnl'] for t in _r['trades'])
        _wr = (100.0 * sum(t['net_pnl'] > 0 for t in _r['trades'])
               / max(len(_r['trades']), 1))
        print(f"     re-run: PnL ${_tp:,.0f} | {len(_r['trades'])} trades | "
              f"win {_wr:.0f}%")
    return n_sel, z_sel
 
# ============================================================================
# [HKG] [Y8]/[Y9]/[Y10]/[Y11] DESK LAYER — absent by design (see [HKG] above).
# ============================================================================
# ============================================================================
# [Y12] run_backtest_lots — PYRAMIDING / PARTIAL UNWIND
# ============================================================================
# Design (kept deliberately close to run_backtest so it can be validated):
#   * A position is a list of LOTS. The first lot enters exactly like
#     run_backtest (same gates, floor, sizing, capacity cap, contract snap).
#   * ADD:    while in a position and len(lots) < 1 + MAX_ADDS, a new lot is
#             added when the signal EXTENDS: same sign, |z| >= |z at the last
#             lot| + ADD_STEP_Z, the dev floor and all entry gates pass, and
#             the row is not suspect. Lot size = z-scaled size x
#             ADD_SIZE_FRAC, capacity-capped and contract-snapped.
#   * UNWIND: if UNWIND_FRAC > 0 and more than one lot is open, the NEWEST
#             lot (LIFO) is closed when |z| retraces inside
#             threshold x UNWIND_AT_Z_FRAC. (LIFO because the add was the
#             marginal, highest-cost risk.)
#   * EXIT:   z-cross-0 / time stop (clock starts at the FIRST lot) / gamma /
#             hard stop close ALL remaining lots, same rules as run_backtest.
#   * COSTS:  every lot pays its own full round trip (its entry and its exit
#             both cross the book) plus carry for the days IT was held. This
#             is the crucial economics of pyramiding here: each add-on costs
#             another ~103 bps RT, so an add needs its own >=124 bps of
#             expected convergence — the dev floor is therefore applied to
#             ADDS too.
#   * Each lot books like a run_backtest trade (same two-leg arithmetic and
#     the same [27][I3] roll-straddle splice), so print_trade_details and the
#     forensics re-derivation lines still tie out per lot.
#
# SELF-TEST BEFORE USE (drop the lots runner's 'End of sample' row first —
# KNOWN boundary: when the sample ends with a position still open,
# run_backtest leaves it OUT of the trade list (its unrealized mark rides
# in daily_equity only) while the lots runner books it as 'End of sample'.
# Same entries, different bookkeeping of the final open trade):
#   r0 = run_backtest(df, best_n, best_thresh)
#   r1 = run_backtest_lots(df, best_n, best_thresh, max_adds=0, unwind_frac=0)
#   t1 = [t for t in r1['trades'] if t['exit_reason'] != 'End of sample']
#   assert len(r0['trades']) == len(t1)
#   assert abs(sum(t['net_pnl'] for t in r0['trades'])
#            - sum(t['net_pnl'] for t in t1)) < 1.0
# If that passes, raise max_adds and compare. Expect: more capital deployed
# on the fattest dislocations (the [W4] "already in a position" days: e.g.
# 2026-06-01, 2026-05-18, 2026-01-09 all had |z| > 2 while a position was
# on), at the price of an extra RT cost per add and fatter tails — judge it
# on the drawdown and the LB/yr, not the headline PnL.
# ============================================================================
def run_backtest_lots(df, n_zscore, threshold, max_adds=2, add_step_z=1.0,
                      add_size_frac=0.5, unwind_at_z_frac=0.0,
                      unwind_frac=0.0, cost_mult=1.0):
    spreads_signal = df['Spread (Signal)'].values
    exec_px_arr = df['Exec Px'].values
    # [HKS] hedge-column bindings, same as run_backtest (TW: identical
    # values). NOTE: fx_arr here is used ONLY on the hedge leg + contract
    # sizing, so it binds hedge_fx directly; exact for 'ssf'/'index_fut'
    # (and TW), approximate for 'us_etf' (lots-runner is an analysis tool).
    fut_arr = (df['Hedge Px'].values if 'Hedge Px' in df.columns
               else df['Fut_2130'].values)
    hedge_arr = df['Hedge Idx'].values
    adr_close_arr = df['TSM US (Close)'].values
    fx_arr = (df['hedge_fx'].values.astype(float) if 'hedge_fx' in df.columns
              else df['TWD (Last)'].values if 'TWD (Last)' in df.columns
              else _np.full(len(df), 32.4))
    earn_arr = (df['earnings_block'].values if 'earnings_block' in df.columns
                else _np.zeros(len(df), dtype=bool))   # [HKE]
    div_hedge_arr = (df['div_ret_hedge'].values if 'div_ret_hedge' in df.columns
                     else _np.zeros(len(df)))
    suspect_arr = (df['gap_suspect'].values if 'gap_suspect' in df.columns
                   else _np.zeros(len(df), dtype=bool))
    preex_arr = (df['pre_exdate'].values if 'pre_exdate' in df.columns
                 else _np.zeros(len(df), dtype=bool))
    fund_arr = (df['funding_rate'].values if 'funding_rate' in df.columns
                else _np.full(len(df), FUNDING_RATE_ANN))
    div_adr_arr = (df['div_ret_adr'].values if 'div_ret_adr' in df.columns
                   else _np.zeros(len(df)))
    beta_arr = (df['beta_hedge'].values if 'beta_hedge' in df.columns
                else df['beta'].values)   # [HKS]
    dates_dt = df['Date_dt'].values
    _di = pd.DatetimeIndex(dates_dt)
    ym_arr = (df['contract_id'].values if 'contract_id' in df.columns
              else (_di.year * 12 + _di.month).values)
    if 'contract_break' in df.columns and df['contract_break'].any():
        ym_arr = ym_arr + _np.cumsum(df['contract_break'].values.astype(int)) * 1000
    k_adr_arr = df['k_adr'].values
    k_fut_arr = df['k_fut'].values
    _divf = _np.ones(len(df))
    fut_adj_arr = fut_arr * _divf
    _dd = _np.diff(dates_dt) / _np.timedelta64(1, 'D')
    gap_next = _np.r_[_dd.astype(int), 999]
    n_days = len(df)
    first_day = first_tradable_row(n_zscore)
    _sig = pd.Series(spreads_signal)
    zmu_arr = _sig.rolling(n_zscore).mean().shift(1).values
    zsd_arr = _sig.rolling(n_zscore).std(ddof=0).shift(1).values
    chgsd_arr = _sig.diff().rolling(n_zscore).std(ddof=0).shift(1).values
    if GATE_MODE == 'adf_level':
        _test_ser = spreads_signal
    else:
        _lvl = pd.Series(spreads_signal)
        _test_ser = (_lvl - _lvl.rolling(ADF_DETREND_N).mean().shift(1)
                     ).fillna(0.0).values
    adf_p_arr, gamma_arr = get_signal_stats(_test_ser)
 
    def _hedge_growth(t, e_fut_raw, e_ym, e_day):
        _e_adj = e_fut_raw * _divf[e_day]
        if ym_arr[t] == e_ym:
            return fut_adj_arr[t] / _e_adj
        b = t
        while ym_arr[b] != e_ym:
            b -= 1
        return (fut_adj_arr[b] / _e_adj) * (hedge_arr[t] / hedge_arr[b])
 
    def _cap_and_snap(want_notional, t, direction):
        # [HKC] SAME beta-aware arithmetic as run_backtest: the book cap
        # and the whole-contract snap both bind on the HEDGE leg
        # (beta x notional), not the trade notional — with beta ~0.7 the
        # old trade-notional snap left a fractional, untradeable hedge
        # and made this runner disagree with the main loop wholesale.
        _bt = beta_arr[t] if not _np.isnan(beta_arr[t]) else 0.0
        if MAX_BOOK_PARTICIPATION > 0 and HEDGE_MODE != 'none' and _bt > 0:
            _win = (EXEC_WINDOW_CLOSE_MIN if EXEC_TIMING == 'close'
                    else EXEC_WINDOW_MIN)
            if EXEC_TIMING == 'close':
                _l1 = FUT_L1_BID_CLOSE if direction == 1 else FUT_L1_ASK_CLOSE
                _rep = FUT_REPLENISH_CLOSE
            else:
                _l1 = FUT_L1_BID_OPEN if direction == 1 else FUT_L1_ASK_OPEN
                _rep = FUT_REPLENISH_OPEN
            _supply = _l1 + _rep * _win
            _c0 = FUT_CONTRACT_SHARES * fut_arr[t] / fx_arr[t]
            _cap = MAX_BOOK_PARTICIPATION * _supply * _c0 / _bt
            if _cap > 0:
                want_notional = min(want_notional, _cap)
        _c_usd = FUT_CONTRACT_SHARES * fut_arr[t] / fx_arr[t]
        if ALIGN_TO_CONTRACTS and HEDGE_MODE != 'none' and _bt > 0:
            _nc = max(1, int(round(_bt * want_notional / _c_usd)))
            return _nc * _c_usd / _bt
        return want_notional
 
    def _lot_pnl(lot, t):
        sh = lot['notional'] / lot['entry_px']
        adr_leg = (lot['dir'] * (exec_px_arr[t] - lot['entry_px']) * sh
                   + lot['div_accrued'])
        fut_leg = (-lot['dir'] * lot['beta'] * lot['notional']
                   * (_hedge_growth(t, lot['entry_fut'], lot['ym'],
                                    lot['day']) - 1.0)
                   * (fx_arr[lot['day']] / fx_arr[t]))
        fut_leg += lot['fut_div_cash']
        return adr_leg, fut_leg
 
    def _lot_carry(lot, t):
        cd = (pd.Timestamp(dates_dt[t]) - pd.Timestamp(dates_dt[lot['day']])).days
        if lot['dir'] == 1:
            _r = float(_np.mean(fund_arr[lot['day']:t + 1])) / 360
        else:
            _r = (BORROW_ANN_BPS / 1e4 - SHORT_REBATE_ANN) / 360
        return lot['notional'] * max(_r, 0.0) * cd \
            + lot['beta'] * lot['notional'] * (margin_ann_bps() / 1e4) / 360 * cd
 
    def _close_lot(lot, t, reason):
        adr_leg, fut_leg = _lot_pnl(lot, t)
        gross = adr_leg + fut_leg
        _ka = k_adr_arr[t] if not _np.isnan(k_adr_arr[t]) else K_ADR_FALLBACK
        _kf = k_fut_arr[t] if not _np.isnan(k_fut_arr[t]) else K_FUT_FALLBACK
        # [HKC] the lot's hedge was sized at ITS entry beta and never
        # re-sizes — cost the round trip on that, not on today's beta
        exec_cost = compute_exec_cost(
            lot['notional'], False, _ka, _kf, lot['beta'],
            cost_mult=cost_mult, fut_px_twd=fut_arr[t], fx=fx_arr[t])[0]
        carry = _lot_carry(lot, t)
        net = gross - exec_cost - carry
        return dict(entry_date=df['Date'].iloc[lot['day']],
                    exit_date=df['Date'].iloc[t],
                    entry_day=lot['day'], exit_day=t,
                    direction=lot['dir'], notional=lot['notional'],
                    lot_kind=lot['kind'], entry_z=lot['z'],
                    adr_leg=adr_leg, fut_leg=fut_leg, gross=gross,
                    exec_cost=exec_cost, carry=carry, net_pnl=net,
                    exit_reason=reason)
 
    trades, lots = [], []
    daily_equity = _np.zeros(n_days)
    realized = 0.0
    position = 0
    for t in range(first_day, n_days):
        mu, sigma = zmu_arr[t], zsd_arr[t]
        z = ((spreads_signal[t] - mu) / sigma
             if (not _np.isnan(sigma)) and sigma > 0 else 0.0)
        _g = gamma_arr[t]
        if GATE_MODE == 'halflife_drift':
            _hl_ok = (_np.isfinite(_g) and _g < 0
                      and _np.log(0.5) / _np.log(1.0 + max(_g, -0.999))
                      <= HL_MAX_DAYS)
            _dr_ok = True
            if (t >= 5 and _np.isfinite(zmu_arr[t]) and _np.isfinite(zmu_arr[t - 5])
                    and _np.isfinite(chgsd_arr[t]) and chgsd_arr[t] > 0):
                _dr_ok = (abs(zmu_arr[t] - zmu_arr[t - 5])
                          / (chgsd_arr[t] * _np.sqrt(5.0)) <= DRIFT_MAX_SIGMA)
            system_on = _hl_ok and _dr_ok
        elif GATE_MODE == 'off' or ADF_EXIT_POLICY == 'ignore':
            system_on = True
        else:
            system_on = adf_p_arr[t] < ADF_PVALUE
        _dev_ok = True
        if MIN_ENTRY_DEV_BPS > 0 and _np.isfinite(mu):
            _dv = abs(spreads_signal[t] - mu)
            if SIGNAL_MODE != 'premium':
                _dv = _dv / exec_px_arr[t] * 1e4
            _dev_ok = _dv >= MIN_ENTRY_DEV_BPS
        _entry_ok = (system_on and _dev_ok and not suspect_arr[t]
                     and not preex_arr[t] and not earn_arr[t]   # [HKE]
                     and gap_next[t] <= MAX_ENTRY_GAP_DAYS)
 
        if position == 0:
            if _entry_ok and abs(z) > threshold:
                _want = -1 if z > threshold else 1
                if ((DIRECTION_FILTER == 'long_only' and _want == -1)
                        or (DIRECTION_FILTER == 'short_only' and _want == 1)):
                    daily_equity[t] = realized
                    continue
                _mult = (min(abs(z) / threshold, SIZE_CAP)
                         if SIZING_MODE == 'z_scaled' else 1.0)
                _nt = _cap_and_snap(NOTIONAL * _mult, t, _want)
                position = _want
                lots = [dict(dir=_want, notional=_nt, day=t,
                             entry_px=exec_px_arr[t], entry_fut=fut_arr[t],
                             ym=ym_arr[t],
                             beta=(beta_arr[t] if not _np.isnan(beta_arr[t])
                                   else 1.0),
                             z=z, kind='BASE', div_accrued=0.0,
                             fut_div_cash=0.0)]
            daily_equity[t] = realized
            continue
 
        # ---- in a position ------------------------------------------------
        for lot in lots:
            if t > lot['day']:
                sh = lot['notional'] / lot['entry_px']
                lot['div_accrued'] += (lot['dir'] * sh * adr_close_arr[t - 1]
                                       * div_adr_arr[t])
                # [T3][HKS] no margin-account dividend on an index hedge
        unreal = sum(sum(_lot_pnl(l, t)) for l in lots)
        tot_nt = sum(l['notional'] for l in lots)
        daily_equity[t] = realized + unreal
        cd0 = (pd.Timestamp(dates_dt[t])
               - pd.Timestamp(dates_dt[lots[0]['day']])).days
 
        # ADD: signal extended
        if (max_adds > 0 and len(lots) < 1 + max_adds and _entry_ok
                and _np.sign(z) == -position     # same trade direction sign
                and abs(z) >= abs(lots[-1]['z']) + add_step_z):
            _mult = (min(abs(z) / threshold, SIZE_CAP)
                     if SIZING_MODE == 'z_scaled' else 1.0)
            _nt = _cap_and_snap(NOTIONAL * _mult * add_size_frac, t, position)
            lots.append(dict(dir=position, notional=_nt, day=t,
                             entry_px=exec_px_arr[t], entry_fut=fut_arr[t],
                             ym=ym_arr[t],
                             beta=(beta_arr[t] if not _np.isnan(beta_arr[t])
                                   else 1.0),
                             z=z, kind=f'ADD@z{z:+.2f}', div_accrued=0.0,
                             fut_div_cash=0.0))
 
        # PARTIAL UNWIND (LIFO) on z retracement
        if (unwind_frac > 0 and len(lots) > 1
                and abs(z) <= threshold * unwind_at_z_frac):
            trades.append(_close_lot(lots.pop(), t, 'Partial unwind (z retrace)'))
            realized += trades[-1]['net_pnl']
 
        # FULL EXIT tests (identical family to run_backtest)
        exit_all, reason = False, ''
        if (position == -1 and z <= 0) or (position == 1 and z >= 0):
            exit_all, reason = True, 'Z crossed 0'
        _u_bps = unreal / max(tot_nt, 1.0) * 1e4
        if not exit_all and HARD_STOP_BPS > 0 and _u_bps < -HARD_STOP_BPS:
            exit_all, reason = True, f'Hard stop {HARD_STOP_BPS}bps'
        if not exit_all and PROFIT_TARGET_BPS > 0 and _u_bps >= PROFIT_TARGET_BPS:
            exit_all, reason = True, f'Profit target {PROFIT_TARGET_BPS}bps'
        if not exit_all and _np.isfinite(_g) and _g < 0 \
                and (not _np.isnan(sigma)) and sigma > 0:
            gap_usd = (abs(z) * sigma / 1e4 * exec_px_arr[t]
                       if SIGNAL_MODE == 'premium' else abs(z) * sigma)
            # [V32-FIX5] shares are FIXED AT ENTRY (notional / entry px),
            # exactly as run_backtest computes them — dividing by TODAY'S
            # price made the two engines disagree about the same exit on
            # the same day whenever the price had drifted.
            exp_prof = (abs(max(_g, -1.0)) * gap_usd
                        * sum(l['notional'] / l['entry_px'] for l in lots))
            if position == 1:
                dcar = tot_nt * fund_arr[t] / 360
            else:
                dcar = tot_nt * (BORROW_ANN_BPS / 1e4 - SHORT_REBATE_ANN) / 360
            # [HKC] hedge-leg carry EXACTLY as run_backtest charges it:
            # margin on beta x notional for a futures hedge (the old
            # beta-less tot_nt margin overcharged the hurdle by ~1/beta
            # and fired this exit days early), ETF borrow/funding for
            # us_etf, nothing when naked.
            _bsum = sum(l['beta'] * l['notional'] for l in lots)
            if _HEDGE_IS_FUT:
                dcar += _bsum * (margin_ann_bps() / 1e4) / 360
            elif HEDGE_MODE == 'us_etf':
                _hr = (ETF_BORROW_ANN_BPS / 1e4 if position == 1
                       else fund_arr[t])
                dcar += _bsum * _hr / 360
            dcar = max(dcar, 0.0)
            _dtn = max(int(gap_next[t]) if gap_next[t] < 999 else 1, 1)
            if exp_prof < dcar * _dtn:
                exit_all, reason = True, 'Gamma exit'
        if not exit_all and cd0 >= TIME_STOP:
            exit_all, reason = True, f'Time stop (cap {TIME_STOP}cd, held {cd0}cd)'
        if exit_all:
            fill_t = t
            if suspect_arr[fill_t] and fill_t + 1 < n_days:
                fill_t += 1                      # [K4] defer off a bad print
            for lot in lots:
                trades.append(_close_lot(lot, fill_t, reason))
                realized += trades[-1]['net_pnl']
            lots, position = [], 0
            daily_equity[t] = realized
    # force-close anything still open at the sample end
    if lots:
        for lot in lots:
            trades.append(_close_lot(lot, n_days - 1, 'End of sample'))
            realized += trades[-1]['net_pnl']
    return dict(trades=trades, daily_equity=daily_equity,
                total_pnl=realized)
 
def lots_report(res, title='PYRAMIDING RUN'):
    """[Y12] Compact per-lot HTML report for a run_backtest_lots result."""
    if not res['trades']:
        print('no trades'); return
    fr = _pd.DataFrame(res['trades'])
    fr['dir'] = fr['direction'].map({1: 'LONG', -1: 'SHORT'})
    cols = ['entry_date', 'exit_date', 'dir', 'lot_kind', 'entry_z',
            'notional', 'gross', 'exec_cost', 'carry', 'net_pnl',
            'exit_reason']
    show_html_table(fr[cols].set_index('entry_date'),
                    title=f"{title} — {len(fr)} lot(s), net "
                          f"${res['total_pnl']:,.0f}",
                    fmt={'notional': '{:,.0f}', 'gross': '{:+,.0f}',
                         'exec_cost': '{:,.0f}', 'carry': '{:,.0f}',
                         'net_pnl': '{:+,.0f}', 'entry_z': '{:+.2f}'},
                    note='Every ADD pays its own full round trip — judge '
                         'pyramiding on MaxDD and LB/yr, not the headline.')
 
# ============================================================================
# [HKG] [Y13]/[Y24]/[Y21] DESK HELPERS — absent by design (see [HKG] above).
# ============================================================================
 
# ============================================================================
# [HK1] HEDGE-MODE COMPARISON — the decision this book exists to make.
# ============================================================================
# The SIGNAL is identical in every mode (the fair always uses the rolling
# beta on the index gap), so the entries are matched by construction and
# the only thing that changes is what the hedge leg does to the P&L. That
# makes this a clean read on one question: does the index hedge earn its
# costs, or is the naked premium trade better risk-adjusted?
# What to look at, in order:
#   1. sigma of trade P&L — the hedge's ONLY job is to shrink this. If it
#      does not, nothing else matters.
#   2. net P&L — the hedge costs fees + margin + FX + the [HK2] window.
#   3. Sharpe / t-stat — the honest combination of the two.
# An index hedge with beta ~0.7 and R2 ~0.5 removes about half the
# overnight variance; whether that is worth ~10-15 bps of round-trip cost
# is an empirical question this table answers rather than a principle.
def hedge_mode_compare(n=None, z=None, modes=('index_fut', 'us_etf', 'none')):
    """[HK1] Re-run the SAME (n, z) with each hedge mode. Returns a dict of
    mode -> result. The signal is untouched; only the hedge columns move."""
    global HEDGE_MODE, _HEDGE_IS_FUT
    _n = int(n if n is not None else best_n)
    _z = float(z if z is not None else best_thresh)
    _keep = (HEDGE_MODE, _HEDGE_IS_FUT,
             df['Hedge Px'].copy(), df['Hedge Idx'].copy(),
             df['hedge_fx'].copy(), df['beta_hedge'].copy())
    _out, _rows = {}, []
    try:
        for _m in modes:
            if _m == 'us_etf' and ('ETF_close' not in df.columns
                                   or df['ETF_close'].notna().mean() <= 0.5):
                print(f"[HK1] skipping 'us_etf' — no ETF price series")
                continue
            HEDGE_MODE = _m
            _HEDGE_IS_FUT = (_m == 'index_fut')
            if _m == 'index_fut':
                df['Hedge Px'], df['Hedge Idx'] = _keep[2], _keep[3]
                df['hedge_fx'], df['beta_hedge'] = _keep[4], _keep[5]
            elif _m == 'us_etf':
                _e = df['ETF_close'].ffill()
                df['Hedge Px'] = _e
                df['Hedge Idx'] = _e / _e.iloc[0]
                df['hedge_fx'] = 1.0
                _ra, _re = df['TSM US (Close)'].pct_change(), _e.pct_change()
                _mx, _my = _bsm(_re), _bsm(_ra)
                _cv = _bsm(_re * _ra) - _mx * _my
                _vr = (_bsm(_re * _re) - _mx ** 2).where(lambda s: s > 0)
                df['beta_hedge'] = ((BETA_SHRINK_W * (_cv / _vr)
                                     + (1.0 - BETA_SHRINK_W) * 1.0)
                                    .clip(BETA_MIN, BETA_MAX).shift(1).fillna(1.0))
            else:                              # 'none'
                df['Hedge Px'], df['Hedge Idx'] = _keep[2], _keep[3]
                df['hedge_fx'] = _keep[4]
                df['beta_hedge'] = 0.0
            _r = run_backtest(df, _n, _z)
            _out[_m] = _r
            _t = _r['trades']
            _pn = [x['net_pnl'] for x in _t]
            _sd = float(np.std(_pn, ddof=1)) if len(_pn) > 1 else float('nan')
            _mu = float(np.mean(_pn)) if _pn else float('nan')
            _rows.append({
                'hedge': _m,
                'trades': len(_t),
                'net PnL': sum(_pn),
                'PnL sigma/trade': _sd,
                't-stat': (_mu / (_sd / np.sqrt(len(_pn)))
                           if len(_pn) > 1 and _sd > 0 else float('nan')),
                'win %': (100.0 * sum(p > 0 for p in _pn) / len(_pn)
                          if _pn else float('nan')),
                'hedge leg $': sum(x.get('fut_leg_pnl') or 0.0 for x in _t),
                'cost $': sum(x['total_cost'] for x in _t)})
    finally:
        (HEDGE_MODE, _HEDGE_IS_FUT, df['Hedge Px'], df['Hedge Idx'],
         df['hedge_fx'], df['beta_hedge']) = _keep
    if _rows:
        _bd = _pd.DataFrame(_rows).set_index('hedge')
        show_html_table(
            _bd, title=f'[HK1] HEDGE-MODE COMPARISON — N={_n}, Z={_z} '
                       f'(identical entries)',
            fmt={'net PnL': '{:+,.0f}', 'PnL sigma/trade': '{:,.0f}',
                 't-stat': '{:+.2f}', 'win %': '{:.0f}', 'hedge leg $': '{:+,.0f}',
                 'cost $': '{:,.0f}'},
            note="Read PnL sigma/trade FIRST — variance reduction is the "
                 "hedge's whole job. 'none' is the baseline; 'us_etf' pays "
                 "tracking error but avoids the [HK2] 1-2h stale window that "
                 "'index_fut' carries at both ends.")
        _bst = min(_rows, key=lambda r: (r['PnL sigma/trade']
                                         if np.isfinite(r['PnL sigma/trade'])
                                         else 9e18))
        sc('INFO', 'hedge mode [HK1]',
           f"lowest per-trade sigma: {_bst['hedge']} "
           f"(${_bst['PnL sigma/trade']:,.0f})")
    return _out
# ============================================================================
# [HKT] HEDGE-TIMING COMPARISON — futures all the way, futures-then-stock,
# or naked-then-stock. Same signal, same entries, same ADR leg; ONLY the
# hedge leg's instrument, window and cost stack change.
# ============================================================================
# The real-world timeline per trade (entry day e, exit day x):
#   US close e      ADR fills at the MOC. Mode 1+2 also put on the HTI
#                   hedge (worked into the 03:00-HKT T+1 close). Mode 3
#                   holds the ADR NAKED overnight.
#   HK open e+1     (09:30 HKT = 01:30 UTC) Mode 2 unwinds the futures at
#                   the Fut_0130 print and shorts/buys the ORDINARY at its
#                   opening auction — the position becomes a true
#                   ADR-vs-ordinary pair, premium locked, idio risk gone.
#                   Mode 3 puts the stock on here too.
#   US close x      ADR exits at the MOC (the signal's exit). The stock
#                   leg cannot trade now (HK is shut) —
#   HK open x+1     — so it unwinds at the next opening auction. That
#                   ~5.5h stock-leg tail, like mode 3's naked overnight,
#                   is real risk the table shows rather than hides.
# COSTS per mode (constant-bps arithmetic; impact terms are already in the
# base run's exec_cost and identical across modes on the ADR leg):
#   1  futures RT + margin over the hold                      (= base run)
#   2  futures RT + 1cd margin + stock RT incl. STAMP both ways
#      + borrow when the stock leg is short (long spread)
#   3  stock RT incl. stamp + borrow — no futures costs at all
# ENTRY/EXIT DATES COME FROM THE BASE RUN: gates and exits were decided on
# the index-hedged path. That is the honest framing — this table answers
# "given the SAME trades, which hedge would you rather have carried?"
def hedge_timing_compare(trades=None):
    """[HKT] Recompute each base-run trade's hedge leg under the three
    timings. Pure arithmetic on already-loaded columns — no new backtests.
    Returns {mode: [per-trade dicts]}."""
    _tr = trades if trades is not None else result_base['trades']
    if not _tr:
        say('[HKT] no trades to compare', 'warn')
        return {}
    _f2130 = df['Fut_2130'].values
    _f0130 = (df['Fut_0130'].values if 'Fut_0130' in df.columns
              else np.full(len(df), np.nan))
    _oopen = (pd.to_numeric(df['2330 TT (Open)'], errors='coerce').values
              if '2330 TT (Open)' in df.columns
              else np.full(len(df), np.nan))
    _oclose = df['2330 TT (Close)'].values
    _hfx = pd.to_numeric(df['hedge_fx'], errors='coerce').values
    _n = len(df)
    _stock_rt_bps = 2 * (ORD_STAMP_BPS + ORD_LEVIES_BPS + ORD_HALF_SPREAD_BPS)
    _fut_rt_bps = (2 * (FUT_HALF_SPREAD_CLOSE_BPS + BOOK_BUFFER_FUT_BPS)
                   + FUT_FEE_IN_BPS + FUT_FEE_OUT_BPS
                   + 2 * FX_SPOT_HALF_SPREAD_BPS)
    out = {m: [] for m in ('index_all', 'index_then_stock', 'stock_open_only')}
    _skip2 = 0
    for t in _tr:
        e, x = t['entry_day'], t['exit_day']
        d, N, be = t['direction'], t['trade_notional'], t['entry_beta']
        # stock leg window: next HK open after entry -> next HK open after
        # exit (fallback to the close where an open print is missing)
        def _open_or_close(i):
            if i < _n and np.isfinite(_oopen[i]):
                return _oopen[i], i
            i2 = min(i, _n - 1)
            return _oclose[i2], i2
        _po, _ie = _open_or_close(e + 1)
        _px_, _ix = _open_or_close(min(x + 1, _n - 1))
        stock_leg = (-d * N * (_px_ / _po - 1.0) * (_hfx[_ie] / _hfx[_ix]))
        stock_days = max(int((pd.Timestamp(df['Date_dt'].iloc[_ix])
                              - pd.Timestamp(df['Date_dt'].iloc[_ie])).days), 0)
        _borrow = (N * (BORROW_ORD_ANN_BPS / 1e4) / 360 * stock_days
                   if d == 1 else 0.0)          # long spread SHORTS the stock
        stock_cost = _stock_rt_bps / 1e4 * N + _borrow
        # ---- mode 1: exactly the base run's hedge leg + its costs
        out['index_all'].append(dict(
            hedge_pnl=(t['fut_leg_pnl'] if t['fut_leg_pnl'] == t['fut_leg_pnl']
                       else 0.0),
            extra_cost=0.0, net=t['net_pnl']))
        # ---- mode 2: futures overnight only, then the stock
        if e + 1 < _n and np.isfinite(_f0130[e + 1]):
            legA = (-d * be * N * (_f0130[e + 1] / _f2130[e] - 1.0)
                    * (_hfx[e] / _hfx[e + 1]))
            _margin1 = be * N * (margin_ann_bps() / 1e4) / 360 * 1
            _d_cost = (stock_cost + _margin1
                       - (t.get('margin_cost') or 0.0))   # base margin refunded
            out['index_then_stock'].append(dict(
                hedge_pnl=legA + stock_leg, extra_cost=_d_cost,
                net=(t['net_pnl'] - t['fut_leg_pnl'] + legA + stock_leg
                     - _d_cost)))
        else:
            _skip2 += 1
        # ---- mode 3: naked overnight, then the stock; no futures costs
        _fut_cost_refund = (_fut_rt_bps / 1e4 * be * N
                            + (t.get('margin_cost') or 0.0))
        out['stock_open_only'].append(dict(
            hedge_pnl=stock_leg, extra_cost=stock_cost - _fut_cost_refund,
            net=(t['net_pnl'] - t['fut_leg_pnl'] + stock_leg
                 - stock_cost + _fut_cost_refund)))
    _rows = []
    _lbl = {'index_all': f'1. {HEDGE_LBL} futures all the way',
            'index_then_stock': f'2. {HEDGE_LBL} overnight -> stock at HK open',
            'stock_open_only': '3. naked overnight -> stock at HK open'}
    for m, lst in out.items():
        if not lst:
            _rows.append({'timing': _lbl[m], 'trades': 0, 'net PnL': np.nan,
                          'sigma/trade': np.nan, 't-stat': np.nan,
                          'win %': np.nan, 'extra cost $': np.nan})
            continue
        _pn = [r['net'] for r in lst]
        _sd = float(np.std(_pn, ddof=1)) if len(_pn) > 1 else float('nan')
        _mu = float(np.mean(_pn))
        _rows.append({
            'timing': _lbl[m], 'trades': len(lst),
            'net PnL': sum(_pn), 'sigma/trade': _sd,
            't-stat': (_mu / (_sd / np.sqrt(len(_pn)))
                       if len(_pn) > 1 and _sd > 0 else float('nan')),
            'win %': 100.0 * sum(v > 0 for v in _pn) / len(_pn),
            'extra cost $': sum(r['extra_cost'] for r in lst)})
    show_html_table(
        _pd.DataFrame(_rows).set_index('timing'),
        title=f'[HKT] HEDGE-TIMING COMPARISON — same {len(_tr)} entries, '
              f'only the hedge leg changes',
        fmt={'net PnL': '{:+,.0f}', 'sigma/trade': '{:,.0f}',
             't-stat': '{:+.2f}', 'win %': '{:.0f}', 'extra cost $': '{:+,.0f}'},
        note='Once the stock is on (2 and 3) the pair is LOCKED — the idio '
             'residual [HK-H2] is gone for the rest of the hold, which is '
             'why their sigma can beat mode 1 even after the stamp. Mode 2 '
             'pays both hedge stacks; mode 3 rides ~5.5h naked overnight. '
             'Entries/exits are the base run\'s; extra cost is vs mode 1 '
             '(negative = cheaper). Stock legs also unwind at the open '
             'AFTER the ADR exit — that tail risk is included, not hidden.')
    if _skip2:
        say(f"[HKT] {_skip2} trade(s) missing the Fut_0130 print — excluded "
            f"from mode 2 (add {FUT_HK_OPEN_PATH} coverage)", 'warn')
    _stamp_total = _stock_rt_bps / 1e4 * sum(t['trade_notional'] for t in _tr)
    say(f"stock-leg round trip = {_stock_rt_bps:.1f} bps "
        f"(stamp {2*ORD_STAMP_BPS:.0f} + levies {2*ORD_LEVIES_BPS:.1f} + "
        f"spread {2*ORD_HALF_SPREAD_BPS:.0f}) -> ${_stamp_total:,.0f} across "
        f"these trades if every hold switched to stock", 'info')
    return out
# ============================================================================
# [HK-1A] DOES THE SIGNAL EXIST? — the go/no-go this book must pass first.
# ============================================================================
# Taiwan is a SEGMENTED market: FINI rules keep the ADR and the ordinary
# from being freely exchanged, so a premium can persist and revert. BABA
# and 9988 are FREELY FUNGIBLE and dual-primary listed. That means the US
# close may simply BE price discovery — and a deviation vs the beta-fair
# would then be real news that the HK open RATIFIES rather than reverts.
# If that is the case, no amount of cost engineering saves the trade, and
# it is far cheaper to learn it here than after building a capture job.
# The test: for each day, does today's deviation predict the ordinary's
# NEXT-SESSION move in the direction of convergence?
#   deviation > 0 (ADR rich)  -> convergence needs 9988 UP or ADR DOWN
# We measure the ordinary's overnight response, next open and next close.
# A convergence beta near 0 means "HK ratifies" (no trade); a materially
# POSITIVE coefficient means the gap closes from the HK side (tradable).
def signal_existence(min_obs=100):
    """[HK-1A] Regress the ordinary's next-session return on today's
    deviation. Positive slope = the HK session closes the gap."""
    _sig = df['Spread (Signal)']
    _dev = (_sig - _sig.rolling(30, min_periods=10).mean().shift(1)) / 1e4
    _ord_c = df['2330 TT (Close)']
    _tests = [('next HK close', _ord_c.shift(-1) / _ord_c - 1.0)]
    if '2330 TT (Open)' in df.columns and df['2330 TT (Open)'].notna().mean() > 0.5:
        _tests.insert(0, ('next HK open',
                          df['2330 TT (Open)'].shift(-1) / _ord_c - 1.0))
    _adr = df['TSM US (Close)']
    _tests.append(('ADR next close (own reversal)', _adr.shift(-1) / _adr - 1.0))
    _rows = []
    for _lbl, _fwd in _tests:
        _m = np.isfinite(_dev.values) & np.isfinite(_fwd.values)
        if _m.sum() < min_obs:
            _rows.append({'horizon': _lbl, 'obs': int(_m.sum()),
                          'slope': float('nan'), 't-stat': float('nan'),
                          'reading': _badge('too few obs', 'mut')})
            continue
        _x, _y = _dev.values[_m], _fwd.values[_m]
        _b = float(np.cov(_x, _y)[0, 1] / np.var(_x))
        _a = float(np.mean(_y) - _b * np.mean(_x))
        _res = _y - (_a + _b * _x)
        _se = float(np.sqrt(np.var(_res, ddof=2) / (np.var(_x) * _m.sum())))
        _t = _b / _se if _se > 0 else float('nan')
        # ADR's own next move should be NEGATIVE on a rich deviation
        _want_pos = not _lbl.startswith('ADR')
        _good = (_t > 2.0) if _want_pos else (_t < -2.0)
        _rows.append({
            'horizon': _lbl, 'obs': int(_m.sum()), 'slope': _b, 't-stat': _t,
            'reading': _badge('CONVERGES', 'ok') if _good
                       else _badge('ratified — no reversion', 'bad')
                       if abs(_t) < 2.0 else _badge('wrong sign', 'warn')})
    show_html_table(
        _pd.DataFrame(_rows).set_index('horizon'),
        title='[HK-1A] SIGNAL EXISTENCE — does the gap close, or is it news?',
        fmt={'slope': '{:+.3f}', 't-stat': '{:+.2f}'},
        note='Slope = fraction of today\'s deviation recovered by that '
             'session. Near zero on EVERY row means the US close is price '
             'discovery and the HK session simply agrees — in which case '
             'this strategy has no edge on this name, whatever the costs '
             'look like. This is the cheapest possible go/no-go.')
    return _rows

# [HK-1A] auto-run: the go/no-go is cheap (three regressions, no backtest)
# and must confront you at the END of every run, not wait to be invoked.
try:
    banner("[HK-1A] SIGNAL EXISTENCE — the verdict this run must survive")
    _hk1a_rows = signal_existence()
    _n_prox_tr = sum(1 for t in result_base['trades'] if t.get('gap_proxy'))
    if _n_prox_tr:
        say(f"{_n_prox_tr} of {len(result_base['trades'])} headline trades "
            f"filled on ETF-PROXY gap rows — their fair was estimated, not "
            f"measured", 'warn')
except Exception as _e:
    say(f"[HK-1A] auto-run skipped: {_e}", 'warn')
# [HKT] auto-run: pure per-trade arithmetic, no extra backtests — the
# three hedge timings belong in front of you at the end of every run.
try:
    banner("[HKT] WHICH HEDGE WOULD YOU RATHER HAVE CARRIED?")
    _hkt_out = hedge_timing_compare()
except Exception as _e:
    say(f"[HKT] auto-run skipped: {_e}", 'warn')
banner("v32 HK — EXTRAS LOADED", sub=f"{INSTRUMENT}: {ADR_TICKER} vs {ORD_TICKER}")
menu([
    ("signal_existence()", "[HK-1A] GO/NO-GO: does the gap close, or does "
                           "the HK session just ratify the US close?"),
    ("hedge_mode_compare()", "[HK1] index_fut vs us_etf vs naked on IDENTICAL "
                             "entries — read PnL sigma/trade first"),
    ("hedge_timing_compare()", "[HKT] futures all the way vs futures->stock "
                               "vs naked->stock at the HK open"),
    ("why_no_trades(start, end)", "[X6] per-row entry verdict over a window"),
    ("show_grid_html()", "the grid matrices as heat maps"),
    ("select_composite()", "re-rank the plateau with other weights"),
    ("run_backtest_lots(df, best_n, best_thresh, max_adds=2)",
     "pyramiding — SELF-TEST FIRST: max_adds=0, unwind_frac=0 must "
     "reproduce run_backtest exactly"),
], title="WHAT TO RUN NEXT")
print()
note_block("PAPER DESK", [
    "Not in this book — see [HKG]. The TW desk marks with beta=1, TAIFEX",
    "dividend cash and TWD conventions, so it would give plausible but",
    "WRONG numbers here. Paper-trade in v32_tw_full.py; the HK desk is",
    "Phase 2.",
])
note_block("BEFORE YOU TRUST A NUMBER", [
    "1. [HK-1A] must show convergence. If the HK session ratifies the US",
    "   close, nothing downstream matters.",
    "2. MIN_ENTRY_DEV_BPS is 0 until you set it from [HK-H2] — and the TW",
    "   '2x the floor' convention does NOT transfer (see the block).",
    "3. MANUAL_EARNINGS is empty until you fill it; the [HKE] gate is off",
    "   while it is.",
    "4. The HTI book numbers in INSTRUMENTS are PLACEHOLDERS — measure the",
    "   02:00-03:00 HKT tail on the QR before sizing.",
    "5. Add HTI_2100utc.csv before the US switches off DST.",
])
 
