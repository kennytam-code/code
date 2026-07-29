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
# ============================================================================
# ██ QUICK SETTINGS — the knobs you actually change, all in ONE place. ██
# ----------------------------------------------------------------------------
# Everything here wins over the detailed config blocks further down (they
# read these via globals().get). Deeper machinery — cost model, gates,
# loaders, paths — stays where it is; this block is the daily-driver panel.
# ============================================================================
INSTRUMENT = 'TSMC'            # 'TSMC' | 'UMC' | 'ASX'
FAIR_MODE = 'spot_gap'         # 'spot_gap' | 'futures'  — [M1] user default
                               # changed to spot_gap (v32): fair anchored to
                               # the ordinary close projected by the SSF gap.
                               # 'futures' (the v31.12 default) remains the
                               # arb-consistent alternative — A/B them.
EXEC_TIMING = 'close'          # 'close' (MOC) | 'open'
N_VALUES = [10, 15, 20, 25, 30, 35, 40, 45, 50]
THRESHOLD_VALUES = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0]
TIME_STOP = 20                 # calendar days, hard cap (user-set)
DIRECTION_FILTER = 'both'      # 'both' | 'long_only' | 'short_only'
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
# [Y16] the instrument switch MOVED to QUICK SETTINGS at the very top —
# this line only backstops a missing value and never overrides it.
# ############################################################################
INSTRUMENT = globals().get('INSTRUMENT', 'TSMC')
 
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
    """[Y33] Colour says SIGN first, magnitude second:
      * every value >= 0  -> ONE sequential ramp, light green -> dark green
        (an all-positive table used to paint its weaker half red, which
        read as losses — it never was);
      * every value <= 0  -> light red -> dark red by |value|;
      * genuinely mixed   -> diverging AROUND ZERO (not around the median):
        red only for actual negatives, green for actual positives.
    Text stays dark so the numbers remain readable."""
    import numpy as _n2
    v = dfm.apply(_pd.to_numeric, errors='coerce').values.astype(float)
    out = _pd.DataFrame('', index=dfm.index, columns=dfm.columns)
    fin = _n2.isfinite(v)
    if fin.sum() < 2:
        return out
    lo, hi = _n2.nanmin(v), _n2.nanmax(v)
    _grn = lambda a: f'background-color:rgba(46,160,67,{0.05 + 0.30 * a:.3f})'
    _red = lambda a: f'background-color:rgba(220,53,69,{0.05 + 0.28 * a:.3f})'
    for i in range(v.shape[0]):
        for j in range(v.shape[1]):
            x = v[i, j]
            if not _n2.isfinite(x):
                continue
            if lo >= 0:                       # all positive: green ramp
                a = 0.0 if hi <= lo else (x - lo) / (hi - lo)
                out.iat[i, j] = _grn(a)
            elif hi <= 0:                     # all negative: red ramp
                a = 0.0 if hi <= lo else (hi - x) / (hi - lo)
                out.iat[i, j] = _red(a)
            elif x >= 0:                      # mixed, positive side
                out.iat[i, j] = _grn(x / hi if hi > 0 else 0.0)
            else:                             # mixed, negative side
                out.iat[i, j] = _red(x / lo if lo < 0 else 0.0)
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
                _vals = []
                for _i2, _v2 in enumerate(_num):
                    if _pd.isna(_v2):
                        # NaN that was NaN to begin with -> em-dash, not the
                        # literal 'nan' (warm-up rows used to print '+nan');
                        # a non-numeric string (a label) is left alone.
                        _o2 = _plain[_c].iloc[_i2]
                        _vals.append('\u2014' if _pd.isna(_o2) else _o2)
                    else:
                        _vals.append(_f.format(_v2))
                _plain[_c] = _vals
        except Exception:
            pass
        if title:
            print('\n  ' + str(title))
            print('  ' + '\u2500' * min(max(len(str(title)), 20), 76))
        print(_plain.to_string())
        if note:
            for _wl in _wrap_box(note, _TXT_W - 4, indent=2):   # [Y39]
                print('  ' + _wl)
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
_TXT_W = 100      # [Y39] terminal prose width
def _wrap_box(s, inner, indent=0):
    """[Y39] Split a line to fit INSIDE a box, WRAPPING on word boundaries
    instead of truncating with '...'. The old behaviour cut the day card's
    most important content — the fair-value RESULT and the drift threshold
    both fell off the right edge. Continuation lines get a hanging indent
    so a wrapped formula still reads as one item."""
    import textwrap as _tw
    s = str(s)
    if len(s) <= inner:
        return [s]
    _pad = ' ' * indent
    _out = _tw.wrap(s, width=inner, subsequent_indent=_pad,
                    break_long_words=False, break_on_hyphens=False)
    return [l[:inner] for l in _out] or ['']
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
    _msg = f"{text}" + (f"  {detail}" if detail else '')
    _wl = _wrap_box(_msg, _TXT_W - 6, indent=4)                # [Y39] wrap
    print(f"  {_SAY_ICON.get(level, '.')} {_wl[0]}")
    for _x in _wl[1:]:
        print(f"    {_x}")
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
        for _w in _wrap_box(_l, _inner - 2, indent=2):     # [Y39] wrap
            print('  │ ' + _w.ljust(_inner - 1) + '│')
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
        _head = f"  {str(_a):<{_w}}  {_b}"
        if not _c:
            print(_head)
            continue
        # [Y39] keep a short note INLINE (that reads best); only a note that
        # would run off the edge is wrapped onto hanging-indent lines.
        if len(_head) + 3 + len(str(_c)) <= _TXT_W:
            print(f"{_head}   {_c}")
        else:
            print(_head)
            for _wl in _wrap_box(_c, _TXT_W - _w - 8, indent=0):
                print(f"  {'':<{_w}}    {_wl}")
    if note:
        for _wl in _wrap_box(note, _TXT_W - 4, indent=2):
            print(f"  {_wl}")
 
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
# Everything instrument-specific (tickers, file paths, ADR ratio,
# order-book cost parameters, vol fallbacks, notional) lives in the
# INSTRUMENTS dict below. Strategy logic, fees, FX, funding, gate and
# grid settings are SHARED and sit in the sections after it.
# ============================================================
INSTRUMENT = globals().get('INSTRUMENT', 'TSMC')   # [Y16] set AT THE TOP
INSTRUMENTS = {
    'TSMC': dict(
        ADR_TICKER='TSM US Equity',
        ORD_TICKER='2330 TT Equity',
        ADR_RATIO=5.0,                  # 1 ADR = 5 ord — verify on DES
        FILE_PREFIX=r"G:\FIN_COMM\DeltaOne\Kenny\ADR\TSMC_front_month_",
        CHART_NAME='tsm_backtest_charts.png',
        FUT_CONTRACT_SHARES=2000,       # TAIFEX regular SSF
        NOTIONAL=500_000,               # ~3.2 contracts
        K_ADR_FALLBACK=241,             # ~2.4%/day x 1e4 (sqrt fallback only)
        K_FUT_FALLBACK=188,             # ~1.9%/day x 1e4
        # order book, MEASURED (screenshots) then user-widened for
        # headroom: ADR touch ~0.5bp -> 3; SSF 2-4bp -> 8. Close book
        # from the 2330M mini QR (1 TWD spread ~2bp half at the tail).
        ADR_HALF_SPREAD_OPEN_BPS=3.0,  FUT_HALF_SPREAD_OPEN_BPS=8.0,
        FUT_L1_BID_OPEN=10,  FUT_L1_ASK_OPEN=20,  FUT_REPLENISH_OPEN=5,
        ADR_WINDOW_VOL_OPEN_USD=200_000_000,
        FUT_WINDOW_VOL_OPEN_USD=30_000_000,
        ADR_HALF_SPREAD_CLOSE_BPS=3.0, FUT_HALF_SPREAD_CLOSE_BPS=8.0,
        # [P6] MEASURED 07/21-22/26 =Q6 QR, 15:00-15:55 ET window:
        # quotes 2353/2354-2355 (half 2-4bp; the 8 above keeps headroom),
        # L1 5x4 / 7x6 / 8-9x3, ~40 prints & ~70 contracts per 55 min
        FUT_L1_BID_CLOSE=7,  FUT_L1_ASK_CLOSE=4,  FUT_REPLENISH_CLOSE=1.0,
        ADR_WINDOW_VOL_CLOSE_USD=300_000_000,
        FUT_WINDOW_VOL_CLOSE_USD=8_000_000,
        MIN_ENTRY_DEV_BPS_INST=62,   # [H4] 2x the 31bps FX-noise floor
        MANUAL_DIVIDENDS=[],         # [H6] TR field works for 2330; leave empty
        DIV_MAX_ONE_DAY=0.05,        # [J2] 2330 pays QUARTERLY (~0.5-1%/ex-date)
        DIV_YIELD_EXPECTED_ANN=0.018,  # [M1] TSM ~1.8%/yr — the plausibility anchor
        FUT_DIV_CASH_INST=True,      # [T1] TAIFEX margin-account settlement
        DRIFT_MAX_SIGMA_INST=0.50,   # [M7] TSM DOES re-rate: measured drift
                                     # p99 = 0.68, so 0.75 never fires. 0.50
                                     # excludes the top ~1-2% of repricing days.
    ),
    'ASX': dict(
        # [U2] ASE Technology — ASX US ADR vs 3711 TT ordinary. Same
        # market as TSMC/UMC, so TAIFEX single-stock-future mechanics
        # apply: the SSF is NOT pre-discounted and the cash dividend is
        # settled through the margin account (FUT_DIV_CASH_INST=True).
        # The SSF book below is a first estimate — recalibrate from the
        # 3711 =Q6 QR the same way TSMC/UMC were done.
        ADR_TICKER='ASX US Equity',
        ORD_TICKER='3711 TT Equity',
        ADR_RATIO=2.0,                  # VERIFY on DES (ASX has been 1:2)
        FILE_PREFIX=r"G:\\FIN_COMM\\DeltaOne\\Kenny\\ADR\\ASX_front_month_",
        CHART_NAME='asx_backtest_charts.png',
        FUT_CONTRACT_SHARES=2000,       # TAIFEX regular SSF — VERIFY for 3711
        NOTIONAL=300_000,               # start smaller until the book is known
        K_ADR_FALLBACK=300,             # ~3%/day guess
        K_FUT_FALLBACK=270,
        ADR_HALF_SPREAD_OPEN_BPS=3.0,  FUT_HALF_SPREAD_OPEN_BPS=18.0,
        FUT_L1_BID_OPEN=15,  FUT_L1_ASK_OPEN=15,  FUT_REPLENISH_OPEN=3,
        ADR_WINDOW_VOL_OPEN_USD=30_000_000,
        FUT_WINDOW_VOL_OPEN_USD=6_000_000,
        ADR_HALF_SPREAD_CLOSE_BPS=3.0, FUT_HALF_SPREAD_CLOSE_BPS=18.0,
        FUT_L1_BID_CLOSE=15, FUT_L1_ASK_CLOSE=15, FUT_REPLENISH_CLOSE=3,
        ADR_WINDOW_VOL_CLOSE_USD=40_000_000,
        FUT_WINDOW_VOL_CLOSE_USD=8_000_000,
        MIN_ENTRY_DEV_BPS_INST=85,      # estimate — set to ~2x measured FX floor
        MANUAL_DIVIDENDS=[],
        DIV_MAX_ONE_DAY=0.10,           # 3711 pays ~annually
        DIV_YIELD_EXPECTED_ANN=0.045,   # ASX ~4-5%/yr guess — VERIFY
        DRIFT_MAX_SIGMA_INST=0.75,
        FUT_DIV_CASH_INST=True,         # [T1] TAIFEX margin-account settlement
    ),
    'UMC': dict(
        ADR_TICKER='UMC US Equity',
        ORD_TICKER='2303 TT Equity',
        ADR_RATIO=5.0,                  # VERIFY on DES before first run
        FILE_PREFIX=r"G:\FIN_COMM\DeltaOne\Kenny\ADR\UMC_front_month_",
        CHART_NAME='umc_backtest_charts.png',
        FUT_CONTRACT_SHARES=2000,       # VERIFY 2303 SSF multiplier (TAIFEX)
        NOTIONAL=500_000,               # ~159 contracts (!) — watch the
                                        # participation warnings; shrink
                                        # if the book cannot carry it
        K_ADR_FALLBACK=300,             # ~3%/day — VERIFY from UMC data
        K_FUT_FALLBACK=260,             # ~2.6%/day — VERIFY
        # order book: USER-SET placeholders; MEASURE from the UMC QR
        # (a ~$7 ADR: 1c ~ 14bp; a ~NT$50 future: 1 tick ~ 10bp)
        ADR_HALF_SPREAD_OPEN_BPS=2.5,  FUT_HALF_SPREAD_OPEN_BPS=20.0,
        FUT_L1_BID_OPEN=10,  FUT_L1_ASK_OPEN=35,  FUT_REPLENISH_OPEN=3,
        ADR_WINDOW_VOL_OPEN_USD=15_000_000,
        FUT_WINDOW_VOL_OPEN_USD=5_000_000,
        # [P6] MEASURED 07/16-22/26 =Q6 QR, 15:00-15:55 ET window:
        # spread 0.5-1.0 TWD on ~138.5 = 18-36bp HALF (so 25, was 20);
        # L1 organic 8-12 bid x 34-43 ask PLUS market-maker (DV) quotes
        # 95-101 x 37-43; single prints up to 83 contracts; ~196
        # contracts traded per 55 min; day Vol 43,749, OpInt 106,390.
        # The =Q6 (next-month) book itself is liquid — validates the
        # rolling-next-month assumption too.
        ADR_HALF_SPREAD_CLOSE_BPS=2.5, FUT_HALF_SPREAD_CLOSE_BPS=25.0,
        # [R4] L1 now includes the market-maker (DV-coded) quotes the QR
        # shows standing at 95-101 x 37-43, not just the 8-12 x 34-43
        # organic book. Single prints up to 83 contracts and ~196
        # contracts per 55-min window corroborate this depth.
        FUT_L1_BID_CLOSE=95, FUT_L1_ASK_CLOSE=40, FUT_REPLENISH_CLOSE=4,
        ADR_WINDOW_VOL_CLOSE_USD=20_000_000,
        FUT_WINDOW_VOL_CLOSE_USD=2_000_000,
        MIN_ENTRY_DEV_BPS_INST=80,   # [H4] 2x the 40bps FX-noise floor
        # [H6] 2303's TR field returns PRICE-ONLY -> fill these from DVD
        # (ex-date, cash dividend per share in TWD). UMC pays ANNUALLY,
        # usually ex mid-July, so one row per year covers it.
        MANUAL_DIVIDENDS=[],         # e.g. [('2025-07-16', 1.5)]
        # [J2] CRITICAL for UMC: it pays ANNUALLY (~5-7% in ONE go). The
        # old hard-coded 0.05 cap treated any >5% one-day TR-vs-price
        # divergence as noise and ZEROED it — which silently deletes a
        # working annual dividend and prints 'ZERO dividends detected'.
        DIV_MAX_ONE_DAY=0.12,
        DIV_YIELD_EXPECTED_ANN=0.055,  # [M1] UMC ~5-6%/yr, paid ANNUALLY
        FUT_DIV_CASH_INST=True,      # [T1] TAIFEX margin-account settlement
        DRIFT_MAX_SIGMA_INST=0.75,   # [M7] UMC premium has NO structural
                                     # trend (drift p99 = 0.40), so the filter
                                     # correctly never fires — that is not a bug.
    ),
}
globals().update(INSTRUMENTS[INSTRUMENT])
# file paths derived from FILE_PREFIX (same capture-job naming per name)
FUT_US_OPEN_DST_PATH = FILE_PREFIX + "1330utc.csv"   # 13:30 UTC (US summer open)
FUT_US_OPEN_STD_PATH = FILE_PREFIX + "1430utc.csv"   # 14:30 UTC (US winter open)
FUT_LOCAL_CLOSE_PATH = FILE_PREFIX + "1330.csv"      # 13:30 TAIPEI (05:30 UTC)
# NOTE the two similar names: "1330.csv" is the 13:30 TAIPEI snapshot (the
# Taiwan-session anchor), while "1330utc.csv" above is 13:30 UTC = the US
# summer OPEN. Different files. If that is too easy to mix up in the capture
# job, rename this one to "1330tpe.csv" and change the line above to match.
FUT_US_CLOSE_DST_PATH = FILE_PREFIX + "2000utc.csv"  # 20:00 UTC (US summer close)
FUT_US_CLOSE_STD_PATH = FILE_PREFIX + "2100utc.csv"  # 21:00 UTC (US winter close)
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
EXEC_TIMING = globals().get('EXEC_TIMING', 'close')  # [R2] QUICK SETTINGS wins
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
SNAP_UTC_LOCAL_CLOSE = '05:30'   # [K6] 13:30 Taipei — the capture job
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
# The dataframe column names are fixed generic SLOTS ('TSM US (Close)',
# '2330 TT (Close)', 'TWD (Last)') that every instrument reuses — that is
# deliberate and must not change, or hundreds of lines break. But nothing
# the USER READS should say "TSM" while you are running UMC. Every label
# below is derived from the instrument actually selected, and every print
# that names an instrument uses these instead of a literal.
def _short(tkr, default='?'):
    """'TSM US Equity' -> 'TSM US'; '2330 TT Equity' -> '2330 TT'."""
    if not tkr:
        return default
    _p = str(tkr).split()
    return ' '.join(_p[:2]) if len(_p) >= 2 else str(tkr)
ADR_LBL = _short(ADR_TICKER)            # e.g. 'TSM US'   / 'UMC US'
ORD_LBL = _short(ORD_TICKER)            # e.g. '2330 TT'  / '2303 TT'
NAME_LBL = INSTRUMENT                   # e.g. 'TSMC'     / 'UMC'
FX_LBL = 'USDTWD'                       # the pair, as a human writes it
FX_SRC_LBL = f"TW-close BFIX ('{FX_FAIR_TICKER}')" if 'FX_FAIR_TICKER' in dir() \
    else "TW-close BFIX ('TWD F093')"
HEDGE_LBL = 'SSF'                       # the hedge instrument, short
HEDGE_LONG_LBL = f'{NAME_LBL} single stock future'
EXCH_LBL = 'TAIFEX'
LOCAL_LBL = 'Taiwan'
LOCAL_CLOSE_LBL = '13:30 Taipei'
LOCAL_CCY = 'TWD'
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
#       SHORT spread (sell ADR / long SSF): the exact opposite side
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
#   'ndf_immediate'  : the v25 behaviour (2 bps half x2 + signed carry).
# TICKER [O1]: for the next-open print use 'USDTWD REGN Curncy' — the
# onshore/regional composite (the SAME source the user pulled for the
# May-2025 verification, so it exists on this terminal). Two ways to
# get the 09:00 Taipei print: (a) daily PX_OPEN of USDTWD REGN via
# BDH — VERIFY on FLDS that PX_OPEN is populated and check on DES
# which session its 'open' stamps; (b) safer: add a 01:0x UTC
# 'USDTWD REGN Curncy' snap to the existing capture job. Do NOT use
# 'TWD F093' (TW-close BFIX) for this — wrong time of day.
FX_EXEC_MODE = 'spot_next_open'   # 'spot_next_open' | 'ndf_immediate'
FX_SPOT_HALF_SPREAD_BPS = 4       # [R3] user-set (was 8) -> 8 bps RT
# [P1] the actual next-morning conversion rate, pulled via blpapi:
FX_SPOT_TICKER = 'USDTWD REGN Curncy'   # onshore/regional composite (exists
                                        # on this terminal — used for the
                                        # May-2025 verification)
FX_SPOT_FIELD = 'PX_OPEN'               # 09:00-Taipei open print; if the QC
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
FUT_MARGIN_ANN_BPS = 24
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
BORROW_ANN_BPS = 50           # borrow, flat (per user)
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
N_VALUES = globals().get('N_VALUES',
    [10, 15, 20, 25, 30, 35, 40, 45, 50])   # [G3][M4] QUICK SETTINGS wins
THRESHOLD_VALUES = globals().get('THRESHOLD_VALUES',
    [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0])  # [G3]
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
#   SHORT spread (sell ADR / long SSF) = selling an EXPANDED premium,
#     which during a structural re-rating means fading the trend — the
#     loss mode that produces the big losers.
# Test both directions separately before trading either.
DIRECTION_FILTER = globals().get('DIRECTION_FILTER', 'both')
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
MIN_WIN_RATE_SELECT = 55.0      # % [Y35] was 65 — on the first real BABA
                                # run NO grid cell cleared 65% jointly with
                                # the drawdown cap, so BOTH risk-aware
                                # selectors returned empty and the choice
                                # fell through to the raw PnL argmax — the
                                # exact selection-bias failure the [33]
                                # guards warn about. A 55% floor still
                                # rejects coin-flip cells but leaves the
                                # constrained selectors a live candidate set.
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
# [V32-FIX2] PROFIT_TARGET_BPS was ASSIGNED HERE **AND** in the [R9]
# block below — the second assignment silently won, so setting this one
# did nothing. The single definition now lives at [R9]; this block keeps
# only the rationale.
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
# [T1] CONFIRMED TAIFEX MECHANISM (user, from the contract rules):
# a Taiwan single stock future is NOT pre-discounted for the cash
# dividend. Instead, on the ex-date the exchange settles the dividend
# THROUGH THE MARGIN ACCOUNT — the long is credited the full cash
# dividend and the short is debited it. Because the long is certain to
# receive that cash, the futures has no reason to trade at a discount
# into a high-dividend ex-date, so the quote sits very close to spot
# (a slight contango from carry). This explains the observed basis
# exactly: spot 47.0 vs futures 47.5 = +1.06% the day before a 6.8%
# ex-date — no discount, because the dividend is handled in cash.
# CONSEQUENCES for this model:
#   1. On the ex-date the QUOTED futures price DOES fall with the spot.
#      That fall is real and must stay in the leg's price P&L.
#   2. The margin-account cash must ALSO be booked: + for a long
#      futures, - for a short. The two offset, so the hedge ends up
#      dividend-neutral — but only if BOTH are present.
#   3. So the ex-date is NOT a data error and NOT a contract splice.
#      The old price-path fudge (HEDGE_DIV_ADJ) and the break detector
#      firing on ex-dates were both WRONG; this replaces them.
FUT_DIV_CASH = globals().get('FUT_DIV_CASH_INST', True)   # [T1] margin-account
                        # dividend on the SSF leg. TRUE for TAIFEX (confirmed).
                        # Per-instrument override via FUT_DIV_CASH_INST in the
                        # dict — set FALSE for any market whose futures are
                        # pre-discounted (the standard convention elsewhere).
HEDGE_DIV_ADJ = False   # [T1] superseded by FUT_DIV_CASH. Leave False:
                        # scaling the price path AND booking the cash
                        # would credit the dividend twice.
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
TIME_STOP = globals().get('TIME_STOP', 20)   # [R1] hard cap; QUICK SETTINGS wins. With
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
FAIR_MODE = globals().get('FAIR_MODE', 'spot_gap')  # QUICK SETTINGS wins
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
# [Y15] THE PAPER DESK IS DEFINED **BEFORE THE RUN**. In v31.11 it sat at
#        the very end of the file, so ANY exception in the thousands of
#        report lines above it (and UMC exercises different branches than
#        TSMC) killed the cell before setup_manual()/form() were ever
#        defined — which is exactly "UMC is not having setup_manual and
#        form()". Definitions only; nothing here executes until called.
# ============================================================================
_G = dict(dash="\u2014", bull="\u2022", ge="\u2265", approx="\u2248",
          arrow="\u2192", pm="\u00b1", tri="\u25b6", sigma="\u03c3")
# ============================================================================
# [U3] MANUAL PAPER-TRADING DESK   (Jupyter cells; never touches the backtest)
# ============================================================================
# WHY IT EXISTS. The backtest stops at the last date in the CSVs. This carries
# the SAME strategy forward by hand: you type the prints you see, it applies
# the identical fair-price / z-score / regime-gate / cost logic, tells you
# whether that is an entry, and once you are in a position it marks that
# position daily — unrealised P&L, drawdown, current z, and what an exit
# would net right now.
#
# ONE SOURCE OF TRUTH: the ledger CSV. Everything in memory is DERIVED from
# it, every time. That is what makes corrections safe: fix a row (or call
# delete_day / cancel_entry), and days, the open position and the whole mark
# path are rebuilt consistently. It also means a kernel restart loses nothing.
#
# ISOLATION: your manual prices are never written into `df`. The historical
# CLOSE-based premium series is copied out once, read-only; manual days live
# in a separate list appended after it.
#
# CELLS
#   A  setup_manual()                       once per kernel (also reloads state)
#   B  form()   or   add_day(...)           daily input
#   C  enter(...) / exit_pos(...)           record real fills
#   D  status()                             position, P&L, drawdown
#   E  show_ledger()  / delete_day(...) / cancel_entry()      record + repairs
# ============================================================================
_MANUAL = dict(ctx=None, days=[], pos=None, marks=[], closed=[])
# [X7] BUGFIX. 'side', 'notional', 'net' and 'div_carry' are now FIRST-CLASS
# COLUMNS. They used to be recovered by scanning the free-text `note`:
#     direction  = 'SHORT' in note.upper()
#     notional   = the last token in note starting with '$'
#     realised   = the last token in the EXIT note starting with '$'
# which meant note='vs $7.20 ADR' silently set the position size to $7.20,
# and note='no shortfall here' silently flipped a LONG to a SHORT. The
# note-scanning code is kept ONLY as a fallback so ledgers written by v31.10
# and earlier still load; anything written from now on uses the columns.
_LED_COLS = ['instrument', 'date', 'point', 'side', 'notional',
             # [Y37g] the gate's LEVELS, not just its verdict — gamma is
             # the AR(1) slope of the de-trended deviation, hl the implied
             # half-life in days, drift the [Z4] mean-shift ratio. Logged
             # every day so a TREND in the gate is visible in the ledger.
             'gamma', 'hl', 'drift',
             # [Y32] the integer units of the real ticket — first-class
             # columns so a rebuild reads the fill, never re-derives it
             # (an fx_fill amendment must not flip a rounding boundary)
             'shares', 'contracts', 'ordinary',
             'fut_1330', 'fx', 'adr', 'fut', 'fair', 'premium_bps', 'dev_bps',
             'z', 'n', 'threshold', 'gate', 'div_carry', 'in_position', 'net',
             'note']
def _signal_point():
    """[X8] The execution point the SIGNAL is defined at. The desk used to
    hardcode 'close' rows everywhere, which silently disagreed with the
    backtest whenever EXEC_TIMING was 'open'."""
    return 'close' if EXEC_TIMING == 'close' else 'open'
def _txt(v):
    """[X7] Free-text ledger field -> str. `str(x or '')` did NOT work: a CSV
    blank comes back as float('nan'), which is TRUTHY, so notes printed as
    the literal 'nan'."""
    return '' if v is None or str(v).strip() in ('', 'nan', 'None') else str(v)
def _led_num(row, col, default=None):
    """[X7] Read a numeric ledger field, tolerating '', 'nan' and absence."""
    try:
        _v = row[col]
    except (KeyError, IndexError):
        return default
    if _v is None or str(_v).strip() in ('', 'nan', 'None'):
        return default
    try:
        return float(_v)
    except (TypeError, ValueError):
        return default
def _legacy_from_note(note, fallback_notional):
    """[X7] v31.10-and-earlier fallback: recover side/notional from the note.
    Only used when the dedicated columns are absent or blank."""
    _n = str(note)
    _dir = -1 if 'SHORT' in _n.upper() else 1
    _nt = fallback_notional
    for _tok in _n.replace(',', '').split():
        if _tok.startswith('$'):
            try:
                _nt = float(_tok[1:])
            except ValueError:
                pass
    return _dir, _nt
def get_manual_context():
    """[U3] Read-only snapshot of what the desk needs from the finished run."""
    if 'df' not in globals() or 'Spread (Signal)' not in df.columns:
        raise RuntimeError("Run the backtest first — `df` is not in memory.")
    _h = (df['Spread (Signal)'] if SIGNAL_MODE == 'premium'
          else df['Spread (Signal)'] / df['ADR Ref Px'] * 10000).dropna()
    return dict(
        instrument=INSTRUMENT, adr_ticker=ADR_TICKER, ord_ticker=ORD_TICKER,
        adr_ratio=float(ADR_RATIO), fair_mode=FAIR_MODE,
        hist_premium=[float(x) for x in _h.tolist()],
        hist_last_date=str(df['Date'].iloc[-1]),
        hist_mean=float(_sb_mean.dropna().iloc[-1]) if len(_sb_mean.dropna()) else 0.0,
        n=int(best_n) if 'best_n' in globals() else 20,
        thresh=float(best_thresh) if 'best_thresh' in globals() else 1.5,
        gate_mode=GATE_MODE, gate_window=int(gate_window()),
        hl_max=float(HL_MAX_DAYS), drift_max=float(DRIFT_MAX_SIGMA),
        rt_cost_bps=float(bps_normal) if 'bps_normal' in globals() else 100.0,
        min_dev_bps=float(MIN_ENTRY_DEV_BPS), notional=float(NOTIONAL),
        contract_sh=float(FUT_CONTRACT_SHARES), time_stop=int(TIME_STOP),
        hard_stop_bps=float(HARD_STOP_BPS), pt_bps=float(PROFIT_TARGET_BPS),
        pt_z=float(PROFIT_TARGET_Z),
        # [X9] BUGFIX — THE DESK'S COST MODEL. This used to be the literal
        # 2.0 + 2.0 + 2 x FX_SPOT_HALF_SPREAD_BPS = 12 bps a fill, i.e. 24
        # bps a round trip, against a backtest round trip of ~103 bps for
        # UMC. The stated reason ("your own fill price already contains the
        # spread you crossed") is correct for the SPREAD and for IMPACT —
        # but the 32 bps ADR OUT fee is a FEE, not a spread, and it was
        # silently dropped. Every paper P&L printed by this desk was
        # therefore ~4x too flattering, while the entry card next to it
        # measured edge against the full bps_normal. Now built from the
        # SAME constants compute_exec_cost() uses:
        #     fees = ADR IN+OUT + SSF IN+OUT  (on notional, beta = 1)
        #     FX   = 2 x half-spread
        # and spread/impact are the ONLY things excluded.
        rt_fee_bps=float(ADR_FEE_IN_BPS + ADR_FEE_OUT_BPS
                         + FUT_FEE_IN_BPS + FUT_FEE_OUT_BPS
                         + 2 * (FX_SPOT_HALF_SPREAD_BPS
                                if FX_EXEC_MODE == 'spot_next_open'
                                else FX_NDF_HALF_SPREAD_BPS)),
        # [X9] and the CARRY the desk used to ignore entirely: funding when
        # long the ADR, borrow net of rebate when short, margin either way.
        # Per CALENDAR day, in bps of notional — the backtest's convention.
        carry_long_bpd=float(FUNDING_RATE_ANN / 360 * 1e4
                             + margin_ann_bps() / 360),
        carry_short_bpd=float((BORROW_ANN_BPS / 1e4 - SHORT_REBATE_ANN)
                              / 360 * 1e4 + margin_ann_bps() / 360),
        # [X10] the de-trend window the BACKTEST's gate uses, so _gate can
        # test the same object instead of the raw premium level
        detrend_n=int(ADF_DETREND_N), gate_on_level=(GATE_MODE == 'adf_level'),
        exec_point=_signal_point(),
        ledger=os.path.join(os.path.dirname(FILE_PREFIX),
                            f'{INSTRUMENT}_manual_ledger.csv'))
def _read_ledger():
    c = _MANUAL['ctx']
    if not os.path.exists(c['ledger']):
        return pd.DataFrame(columns=_LED_COLS)
    led = pd.read_csv(c['ledger'])
    for k in _LED_COLS:
        if k not in led.columns:
            led[k] = ''
    return led[_LED_COLS]
def _write_ledger(led):
    led = led.copy()
    led['_d'] = led['date'].astype(str)
    _order = {'open': 0, '1945': 1, 'close': 2, 'ENTRY': 3, 'EXIT': 4}
    led['_p'] = led['point'].map(lambda p: _order.get(str(p), 9))
    led = led.sort_values(['_d', '_p']).drop(columns=['_d', '_p'])
    led.to_csv(_MANUAL['ctx']['ledger'], index=False)
def _pos_from_entry_row(e):
    """[X7] Read side and size from the dedicated columns, falling back to the
    old note-scan only for pre-v31.11 ledgers."""
    c = _MANUAL['ctx']
    _side = str(e['side']).strip().upper() if 'side' in e.index else ''
    _nt = _led_num(e, 'notional')
    if _side in ('LONG', 'SHORT') and _nt is not None:
        _dir = 1 if _side == 'LONG' else -1
    else:
        _dir, _nt = _legacy_from_note(e['note'], c['notional'])
        print(f"[X7] {e['date']}: ENTRY has no side/notional column — "
              f"recovered {'LONG' if _dir == 1 else 'SHORT'} ${_nt:,.0f} from "
              f"the note (legacy ledger). Re-run enter(...) to write it "
              f"properly.")
    return _dir, float(_nt)
def _freeze_regime24(e):
    """[Y24] freeze the REGIME as it was on the (first) entry date so the
    position-health monitor can compare against it later. Rebuilt from the
    ledger every time, so it survives a kernel restart."""
    c = _MANUAL['ctx']
    try:
        _p24 = _MANUAL['pos']
        _s24 = _series_before(str(e['date']))
        _n24 = int(c['n'])
        _p24['entry_mu'] = (float(np.mean(_s24[-_n24:]))
                            if len(_s24) >= 3 else float('nan'))
        _sd24 = (float(np.std(_s24[-_n24:], ddof=0))
                 if len(_s24) >= 3 else float('nan'))
        _prem24 = next((float(_d24['premium'])
                        for _d24 in _MANUAL['days']
                        if str(_d24['date']) == str(e['date'])),
                       float('nan'))
        _p24['entry_z'] = ((_prem24 - _p24['entry_mu']) / _sd24
                           if (_prem24 == _prem24 and _sd24 == _sd24
                               and _sd24 > 0) else float('nan'))
        _ok24, _, _gm24, _ = _gate(_n24, str(e['date']))
        _p24['entry_gate'] = bool(_ok24)
        _p24['entry_hl'] = (np.log(0.5) / np.log(1.0 + max(_gm24, -0.999))
                            if (_gm24 == _gm24 and _gm24 < 0)
                            else float('nan'))
    except Exception:
        pass
def _rebuild():
    """[U3] Derive days / open position / mark path FROM THE LEDGER. Called
    after every write, so memory and file can never disagree."""
    c = _MANUAL['ctx']
    led = _read_ledger()
    led = led[led['instrument'] == c['instrument']]
    # 1. manual days = the SIGNAL-POINT rows, in date order, de-duplicated.
    # [X8] the point follows EXEC_TIMING instead of being hardcoded 'close'.
    _pt = c.get('exec_point', 'close')
    cl = led[led['point'] == _pt].drop_duplicates('date', keep='last')
    cl = cl.sort_values('date')
    _MANUAL['days'] = [dict(date=str(r['date']), premium=float(r['premium_bps']),
                            adr=float(r['adr']), fut=float(r['fut']),
                            fx=float(r['fx']),
                            # [Y37] Taiwan anchors, for the live fair
                            ordinary=_led_num(r, 'ordinary'),
                            fut_1330=_led_num(r, 'fut_1330'))
                       for _, r in cl.iterrows()
                       if str(r['premium_bps']) not in ('', 'nan')]
    # 2. open position = the last ENTRY with no EXIT dated on/after it
    ent = led[led['point'] == 'ENTRY'].sort_values('date')
    ext = led[led['point'] == 'EXIT'].sort_values('date')
    _MANUAL['pos'] = None
    # [Y38] ADD-ON SUPPORT: every ENTRY row dated after the last EXIT is an
    # open LEG (the first is the base clip, later ones are add_to() adds).
    # They blend into ONE position with share-weighted / contract-weighted
    # average entry prices — algebraically EXACT for P&L, because
    #   sum_i sh_i x (now - adr_i)  ==  (sum sh_i) x (now - avg_adr).
    # The time stop anchors on the FIRST leg's date (conservative).
    _last_x = str(ext['date'].astype(str).max()) if len(ext) else ''
    open_ent = ent[ent['date'].astype(str) > _last_x] if len(ent) else ent
    if len(open_ent) > 1:
        _legs = []
        for _, _er in open_ent.iterrows():
            _d_i, _nt_i = _pos_from_entry_row(_er)
            try:
                _sh_i = _led_num(_er, 'shares') if 'shares' in _er.index else None
                _cn_i = (_led_num(_er, 'contracts')
                         if 'contracts' in _er.index else None)
                if _sh_i and _cn_i:
                    _cu = c['contract_sh'] * float(_er['fut']) / float(_er['fx'])
                    _u_i = dict(shares=int(_sh_i), contracts=int(_cn_i),
                                c_usd=_cu,
                                adr_notional=int(_sh_i) * float(_er['adr']),
                                hedge_notional=int(_cn_i) * _cu)
                else:
                    _u_i = _units(_nt_i, float(_er['adr']), float(_er['fut']),
                                  float(_er['fx']))
            except Exception:
                _u_i = _units(_nt_i, float(_er['adr']), float(_er['fut']),
                              float(_er['fx']))
            _legs.append(dict(dir=_d_i, adr=float(_er['adr']),
                              fut=float(_er['fut']), fx=float(_er['fx']),
                              date=str(_er['date']), **_u_i))
        if len({_l['dir'] for _l in _legs}) > 1:
            print("[Y38] WARNING: mixed LONG/SHORT entry legs in the open "
                  "stretch — keeping only legs matching the FIRST one")
            _legs = [_l for _l in _legs if _l['dir'] == _legs[0]['dir']]
        _tsh = sum(_l['shares'] for _l in _legs)
        _tcn = sum(_l['contracts'] for _l in _legs)
        _an = sum(_l['adr_notional'] for _l in _legs)
        _hn = sum(_l['hedge_notional'] for _l in _legs)
        _MANUAL['pos'] = dict(
            date=_legs[0]['date'], dir=_legs[0]['dir'], notional=_an,
            entry_adr=sum(_l['shares'] * _l['adr'] for _l in _legs) / _tsh,
            entry_fut=sum(_l['contracts'] * _l['fut'] for _l in _legs) / _tcn,
            entry_fx=sum(_l['hedge_notional'] * _l['fx'] for _l in _legs) / _hn,
            note=f"{len(_legs)} legs (base + {len(_legs) - 1} add)",
            shares=_tsh, contracts=_tcn, adr_notional=_an, hedge_notional=_hn,
            mismatch=_an - _hn, n_legs=len(_legs),
            c_usd=_hn / _tcn if _tcn else float('nan'))
        e = open_ent.iloc[0]   # [Y24] freeze anchors on the FIRST leg below
    if len(open_ent) == 1:
        e = open_ent.iloc[-1]
        later = ext[ext['date'].astype(str) >= str(e['date'])]
        if not len(later):
            _dir, _nt = _pos_from_entry_row(e)
            _MANUAL['pos'] = dict(date=str(e['date']), dir=_dir, notional=_nt,
                                  entry_adr=float(e['adr']),
                                  entry_fut=float(e['fut']),
                                  entry_fx=float(e['fx']),
                                  note=_txt(e['note']))
            try:   # [Y32] integer units: read the STORED columns when the
                   # row has them (the real ticket); derive from the entry
                   # prices only for legacy ledgers that predate [Y32].
                _sh_led = _led_num(e, 'shares') if 'shares' in e.index else None
                _cn_led = (_led_num(e, 'contracts')
                           if 'contracts' in e.index else None)
                if _sh_led and _cn_led:
                    _c_usd = (c['contract_sh'] * float(e['fut'])
                              / float(e['fx']))
                    _an = int(_sh_led) * float(e['adr'])
                    _hn = int(_cn_led) * _c_usd
                    _MANUAL['pos'].update(dict(
                        shares=int(_sh_led), contracts=int(_cn_led),
                        c_usd=_c_usd, adr_notional=_an, hedge_notional=_hn,
                        mismatch=_an - _hn))
                else:
                    _MANUAL['pos'].update(_units(_nt, float(e['adr']),
                                                 float(e['fut']),
                                                 float(e['fx'])))
            except Exception:
                pass
            _freeze_regime24(e)
    if _MANUAL['pos'] is not None and _MANUAL['pos'].get('n_legs', 1) > 1:
        _freeze_regime24(open_ent.iloc[0])   # [Y38] anchor on the FIRST leg
    # [U4] 3. closed trades: pair each EXIT with the ENTRY before it. This is
    # the paper-trade record — cumulative P&L, win rate, per-trade history.
    _MANUAL['closed'] = []
    for _, x in ext.iterrows():
        _prev = ent[ent['date'].astype(str) <= str(x['date'])]
        if not len(_prev):
            continue
        e = _prev.iloc[-1]
        _dir, _nt = _pos_from_entry_row(e)
        _held = (pd.Timestamp(str(x['date']))
                 - pd.Timestamp(str(e['date']))).days
        _net = _led_num(x, 'net')
        if _net is None:      # [X7] recompute from the prints, fees AND carry
            try:              # [Y32] same integer units the trade really had
                _u = _units(_nt, float(e['adr']), float(e['fut']),
                            float(e['fx']))
                _al = _dir * (float(x['adr']) - float(e['adr'])) * _u['shares']
                _fl = (-_dir * _u['contracts'] * c['contract_sh']
                       * (float(x['fut']) - float(e['fut'])) / float(x['fx']))
                _net = _al + _fl - _trade_cost(
                    _dir, _nt, _held, adr_notional=_u['adr_notional'],
                    hedge_notional=_u['hedge_notional'])
            except Exception:  # legacy fallback, fractional
                _sh = _nt / float(e['adr'])
                _al = _dir * (float(x['adr']) - float(e['adr'])) * _sh
                _fl = (-_dir * _nt * (float(x['fut']) / float(e['fut']) - 1.0)
                       * (float(e['fx']) / float(x['fx'])))
                _net = _al + _fl - _trade_cost(_dir, _nt, _held)
        _MANUAL['closed'].append(dict(
            entry_date=str(e['date']), exit_date=str(x['date']), dir=_dir,
            notional=_nt, net=float(_net), held=_held))
    # 4. marks = signal-point rows on/after the entry date, re-marked
    _MANUAL['marks'] = []
    p = _MANUAL['pos']
    if p is not None:
        for d in _MANUAL['days']:
            if d['date'] >= p['date']:
                m = _mtm(d['adr'], d['fut'], d['fx'])
                if m:
                    _MANUAL['marks'].append(dict(date=d['date'], gross=m['gross'],
                                                 bps=m['bps'],
                                                 premium=d['premium']))
def setup_manual(reload=True):
    """[U3] Cell A. Rebuilds context + restores days, open position and marks.
    [V32-FIX4] NOTE: this function is REDEFINED at [Y8] near the end of the
    file (HTML variant) — the LATE definition wins at runtime. Any edit here
    must land in both copies or they silently diverge."""
    _MANUAL.update(ctx=get_manual_context(), days=[], pos=None, marks=[])
    c = _MANUAL['ctx']
    if reload:
        try:
            _rebuild()
        except Exception as e:
            print(f"[U3] ledger reload failed ({e}) — starting empty")
    W = 92                      # [Y39] wider: the rules block needs it
    def _line(s=''):
        for _w in _wrap_box(s, W - 4, indent=4):   # [Y39] wrap, never cut
            print('\u2502 ' + _w.ljust(W - 4) + ' \u2502')
    def _rule(l='\u251c', r='\u2524'): print(l + '\u2500' * (W - 2) + r)
    print('\u250c' + '\u2500' * (W - 2) + '\u2510')
    _line(f"PAPER DESK READY  {_G['dash']}  {c['instrument']}")
    _line(f"{c['adr_ticker']}  vs  {c['ord_ticker']}   "
          f"(1 ADR = {c['adr_ratio']:.0f} ordinary)")
    _rule()
    _line("WHAT setup_manual() DID  (it never re-runs or writes to the backtest)")
    _line(f"  {_G['bull']} copied {len(c['hist_premium'])} historical CLOSE premiums, read-only")
    _line(f"  {_G['bull']} took the settings the grid search chose")
    _line(f"  {_G['bull']} restored your saved days and any open position from the ledger")
    _rule()
    _line(f"HISTORY    to {c['hist_last_date']}   ({len(c['hist_premium'])} closes)")
    _line("YOUR BOOK  " + (f"{len(_MANUAL['days'])} day(s)   "
          f"{_MANUAL['days'][0]['date']} .. {_MANUAL['days'][-1]['date']}"
          if _MANUAL['days'] else "empty"))
    p = _MANUAL['pos']
    _line("POSITION   " + (f"{'LONG' if p['dir'] == 1 else 'SHORT'} spread since "
          f"{p['date']}, ${p['notional']:,.0f}, {len(_MANUAL['marks'])} mark(s)"
          if p else "flat"))
    _cl = _MANUAL.get('closed') or []
    if _cl:
        _line(f"CLOSED     {len(_cl)} trade(s), paper P&L "
              f"${sum(t['net'] for t in _cl):+,.0f}")
    _rule()
    _line("RULES IN FORCE")
    _line(f"  ENTER  |z| {_G['ge']} {c['thresh']:.2f}   (z from an N={c['n']} lookback)")
    _line(f"    and  |deviation| {_G['ge']} {c['min_dev_bps']:.0f} bps   (cost floor)")
    _line(f"         deviation = premium - the LIVE rolling N-mean [X13],")
    _line(f"         not a mean frozen at the last backtest date")
    _line(f"    and  the {c['gate_mode']} regime gate is open")
    _line(f"  EXIT   z crosses 0, or {c['time_stop']} calendar days, or a stop,")
    _line(f"         or [X12] gamma: expected daily reversion < daily carry")
    _line(f"  fair price from {c['fair_mode']};  backtest round trip "
          f"{_G['approx']}{c['rt_cost_bps']:.0f} bps")
    _line(f"  paper P&L charges {c['rt_fee_bps']:.0f} bps fees + carry "
          f"{c['carry_long_bpd']:.1f}/{c['carry_short_bpd']:.1f} bps per day "
          f"(long/short)")
    _line(f"    [X9] spread and impact are EXCLUDED — your typed fills already")
    _line(f"    crossed them. That is the only difference from the "
          f"{c['rt_cost_bps']:.0f} bps above.")
    _rule()
    _line("FX — YOU ONLY NEED TWO NUMBERS  [Y29]")
    _line(f"  1. the 13:30 TW-close fixing, typed as `fx` every day:")
    _line(f"     it prices the fair, the premium, the z AND the marks")
    _line(f"     (FX_MARK_MODE='{FX_MARK_MODE}')")
    if FX_EXEC_MODE == 'spot_next_open':
        _line(f"  2. the NEXT TW open, once you actually trade:")
        _line(f"     fx_fill('<fill date>', <USDTWD 09:00>) after the fact —")
        _line(f"     TWD spot is shut during US hours, so the hedge cannot")
        _line(f"     convert until the next morning. Everything before that")
        _line(f"     call is marked at the fixing and flagged PROVISIONAL.")
    _line("  the per-snapshot FX boxes in form() are optional; blank = fixing")
    _rule()
    _line("NEXT   form()          fill today's prints in a panel")
    _line("       help_manual()   the cheat sheet")
    _rule('\u2514', '\u2518')
    print(f"  ledger {_G['arrow']} {c['ledger']}")
    # [W3] return NOTHING. In Jupyter a bare `setup_manual()` would otherwise
    # auto-display the returned dict, printing every one of the hundreds of
    # historical premium values. The context lives in _MANUAL; helpers read it
    # from there. Use `_MANUAL['ctx']` if you ever need it directly.
    return None
def _series():
    c = _MANUAL['ctx']
    return c['hist_premium'] + [d['premium'] for d in _MANUAL['days']]
def _series_before(date):
    """Premium history strictly BEFORE `date` — what a rolling window may
    legitimately see when scoring that date."""
    c = _MANUAL['ctx']
    return c['hist_premium'] + [d['premium'] for d in _MANUAL['days']
                                if str(d['date']) < str(date)]
def _zstats(prem_now, n, date=None):
    s = _series_before(date) if date is not None else _series()
    win = s[-n:] if len(s) >= n else s
    if len(win) < 3:
        return float('nan'), float('nan'), float('nan')
    mu = sum(win) / len(win)
    sd = (sum((x - mu) ** 2 for x in win) / len(win)) ** 0.5
    return ((prem_now - mu) / sd if sd > 0 else float('nan')), mu, sd
def _detrended(series, m):
    """[X10] The object the BACKTEST's gate actually tests:
        level - level.rolling(m).mean().shift(1)
    _gate used to run gamma on the RAW premium LEVEL while run_backtest ran
    it on this de-trended deviation, even though the docstring claimed the
    two were identical. For any name whose premium trends, level-gamma sits
    much closer to zero, so the desk read 'gate shut' on days the backtest
    had traded. Same object now."""
    a = np.asarray(series, float)
    if len(a) <= m:
        return None
    out = np.full(len(a), np.nan)
    for i in range(m, len(a)):
        out[i] = a[i] - a[i - m:i].mean()
    return out[m:]
def _gate(n, date=None):
    """[X10] Regime gate — now genuinely the backtest's formula. Returns
    (ok, text, gamma, chg_sigma); gamma/chg_sigma feed the gamma exit."""
    c = _MANUAL['ctx']
    _nan = float('nan')
    if c['gate_mode'] == 'none':
        return True, 'gate off', _nan, _nan
    s = _series_before(date) if date is not None else _series()
    w = c['gate_window']
    m = c.get('detrend_n', 20)
    _need = max(w + (0 if c.get('gate_on_level') else m), n + 6)
    if len(s) < _need:
        return False, f'not enough history ({len(s)} pts, need {_need})', _nan, _nan
    # [X10] gamma on the SAME series the backtest uses
    _base = np.array(s, float) if c.get('gate_on_level') else _detrended(s, m)
    if _base is None or len(_base) < w:
        return False, 'not enough history for the de-trended gamma', _nan, _nan
    a = _base[-w:]
    d = a - a.mean()
    den = float(np.dot(d[:-1], d[:-1]))
    gamma = float(np.dot(np.diff(a), d[:-1]) / den) if den > 0 else 0.0
    f = np.array(s, float)
    chg = np.diff(f[-n - 1:])
    sd = float(chg.std(ddof=0)) if len(chg) > 1 else 0.0
    if gamma >= 0:
        return (False, f'gamma {gamma:+.3f} >= 0 (no mean reversion)', gamma, sd)
    hl = np.log(0.5) / np.log(1.0 + max(gamma, -0.999))
    hl_ok = hl <= c['hl_max']
    if sd > 0 and len(f) >= n + 5:
        drift = abs(f[-n:].mean() - f[-n - 5:-5].mean()) / (sd * np.sqrt(5.0))
        dr_ok = drift <= c['drift_max']
    else:
        drift, dr_ok = _nan, True
    return (hl_ok and dr_ok), (f"gamma {gamma:+.3f}, half-life {hl:.1f}d "
                               f"({'OK' if hl_ok else 'FAIL'} vs {c['hl_max']:.0f}), "
                               f"drift {drift:.2f} "
                               f"({'OK' if dr_ok else 'FAIL'} vs {c['drift_max']:.2f})"
                               ), gamma, sd
def _gate_levels(gamma, gate_txt):
    """[Y37g] (half-life, drift) for the LEDGER, derived from the gate's own
    outputs so the logged levels can never disagree with the verdict. hl
    from gamma directly; drift parsed from the gate text (it is printed
    there to 2dp — the same 2dp lands in the ledger)."""
    import re as _re
    hl = (np.log(0.5) / np.log(1.0 + max(gamma, -0.999))
          if (gamma == gamma and gamma < 0) else float('nan'))
    _m = _re.search(r'drift ([0-9.]+)', str(gate_txt))
    return hl, (float(_m.group(1)) if _m else float('nan'))
def _fair(ordinary, fut_1330, fut_pt, fx, div_carry=0.0):
    """[X11] div_carry: the [U5] DIVIDEND-CARRY ADJUSTMENT, which the desk
    used to omit entirely. Between the TAIWAN ex-date and the (later) ADR
    ex-date the ordinary and the future have already dropped by the dividend
    while the ADR still carries the right, so the raw premium JUMPS by
    roughly the dividend — measured at +738 bps on UMC's ~6.8% annual pay,
    against a series sigma of ~120 bps. It is NOT a mispricing: short the
    ADR and you owe that dividend, long the SSF and you were credited it.
    The backtest removes it; the desk did not, and hist_premium IS already
    adjusted — so the desk was scoring an unadjusted print against an
    adjusted history. Pass div_carry as a DECIMAL (0.068 for 6.8%) on every
    day from the TW ex-date until the ADR goes ex.
 
    [Y29] BOTH FAIR MODES, checked against the backtest line by line:
      FAIR_MODE='futures'   backtest: Fut_2130 x RATIO / FX x (1 + carry)
                            desk    : fut_pt   x RATIO / FX x (1 + carry)
      FAIR_MODE='spot_gap'  backtest: ORD x (1 + beta x gap) x RATIO/FX x k
                            desk    : ORD x (fut_pt/fut_1330) x RATIO/FX x k
    The two spot_gap forms are the SAME expression, because gap =
    fut_pt/fut_1330 - 1 and beta is fixed at 1.0 for a same-stock SSF (the
    hedge is the underlying's own future, so the ratio is 1 by
    construction). If beta is ever made a regression estimate, THIS
    function must take it too or the desk and the grid diverge silently in
    spot_gap mode. In 'futures' mode the ordinary does not enter the fair
    at all — it is only the anchor the [Y9a] guards check the SSF against.
    """
    c = _MANUAL['ctx']
    _k = 1.0 + float(div_carry or 0.0)
    if c['fair_mode'] == 'futures':
        return fut_pt * c['adr_ratio'] / fx * _k
    return ordinary * (fut_pt / fut_1330) * c['adr_ratio'] / fx * _k
def _units(notional_usd, adr, fut, fx):
    """[Y32] REAL-WORLD UNITS. You cannot buy 5,211.2 ADR shares or 13.1
    SSF contracts — fills come in integers. The desk therefore sizes the
    way the real ticket does:
      1. whole SSF contracts nearest the requested clip
         (contract_usd = contract_sh x SSF(TWD) / FX),
      2. whole ADR shares nearest the notional those contracts hedge.
    The two legs then differ by a small unavoidable residue ('mismatch')
    — typically under one contract-half plus one share — which rides
    UNHEDGED and is reported, not hidden. Deterministic: rebuilding from
    the ledger's entry prices reproduces the same units every time.
    (The BACKTEST keeps fractional shares after its own [E2] contract
    snap — a <1bp approximation at these clip sizes; the desk is where
    real fills happen, so the desk is exact.)"""
    c = _MANUAL['ctx']
    _c_usd = c['contract_sh'] * float(fut) / float(fx)
    # [Y32b] YOUR notional is the CEILING, not a suggestion: contracts
    # round DOWN (floor) so the deployed clip never exceeds what you
    # asked for; the ADR share count then converts to the SAME hedge
    # notional (nearest share — a share is ~$100 against ~$40-150k
    # contracts, so the legs stay within one share of each other).
    n_con = max(1, int(float(notional_usd) / _c_usd))          # floor
    hedge_notional = n_con * _c_usd
    shares = max(1, int(round(hedge_notional / float(adr))))
    adr_notional = shares * float(adr)
    return dict(shares=shares, contracts=n_con, c_usd=_c_usd,
                adr_notional=adr_notional, hedge_notional=hedge_notional,
                mismatch=adr_notional - hedge_notional)
def _fee_usd(adr_notional, hedge_notional):
    """[Y32] contractual round-trip fees, each leg on ITS OWN notional:
    ADR fees on the share leg, futures fees + the FX spread on the
    hedge leg. With integer units the two notionals differ slightly, so
    a single lump on one notional is no longer exact."""
    _fxh = (FX_SPOT_HALF_SPREAD_BPS if FX_EXEC_MODE == 'spot_next_open'
            else FX_NDF_HALF_SPREAD_BPS)
    return ((ADR_FEE_IN_BPS + ADR_FEE_OUT_BPS) / 1e4 * adr_notional
            + (FUT_FEE_IN_BPS + FUT_FEE_OUT_BPS + 2 * _fxh) / 1e4
            * hedge_notional)
def _trade_cost(direction, notional, held_days,
                adr_notional=None, hedge_notional=None):
    """[X9] FULL round-trip cost of a paper trade, in dollars: contractual
    fees plus the carry the desk used to ignore. Both the daily 'exit now'
    card and the realised exit_pos number call this, so they can no longer
    disagree (the card used to charge ONE fill and the exit TWO).
    [Y32] when the caller passes the integer-unit leg notionals, fees are
    charged per leg on those; the legacy single-notional path is kept for
    old ledgers."""
    c = _MANUAL['ctx']
    if adr_notional is not None and hedge_notional is not None:
        _fee = _fee_usd(adr_notional, hedge_notional)
        _carry_base = adr_notional
    else:
        _fee = c['rt_fee_bps'] / 1e4 * notional
        _carry_base = notional
    _bpd = c['carry_long_bpd'] if direction == 1 else c['carry_short_bpd']
    _carry = _bpd / 1e4 * _carry_base * max(int(held_days), 0)
    return _fee + _carry
def _mtm(adr_now, fut_now, fx_now, div_cash_pct=0.0):
    """[Y32] Marks off the INTEGER units the position actually holds:
    whole shares on the ADR leg, whole contracts x contract_sh x the TWD
    price move on the futures leg (identical algebra to the old
    notional-ratio form when the notionals line up, exact when they do
    not). Legacy ledgers without units fall back to the old formulas."""
    p = _MANUAL['pos']
    if p is None:
        return None
    c = _MANUAL['ctx']
    sh = p.get('shares') or p['notional'] / p['entry_adr']
    n_con = p.get('contracts')
    adr_leg = p['dir'] * (adr_now - p['entry_adr']) * sh
    if n_con:
        fut_leg = (-p['dir'] * n_con * c['contract_sh']
                   * (fut_now - p['entry_fut']) / fx_now)
        div_leg = (-p['dir'] * p.get('hedge_notional', p['notional'])
                   * div_cash_pct)
    else:
        fut_leg = (-p['dir'] * p['notional'] * (fut_now / p['entry_fut'] - 1.0)
                   * (p['entry_fx'] / fx_now))
        div_leg = -p['dir'] * p['notional'] * div_cash_pct
    g = adr_leg + fut_leg + div_leg
    return dict(adr_leg=adr_leg, fut_leg=fut_leg, div_leg=div_leg, gross=g,
                bps=g / p['notional'] * 1e4, shares=sh, contracts=n_con,
                hedge_notional=p.get('hedge_notional'))
def add_day(date, ordinary, fut_1330, fx, adr_open=None, fut_open=None,
            adr_1945=None, fut_1945=None, adr_close=None, fut_close=None,
            div_cash_pct=0.0, div_carry=0.0, note='', save=True, quiet=False):
    """[U3] The daily call. Re-running the SAME date simply CORRECTS it — the
    old rows are replaced, and days / marks / drawdown are rebuilt from the
    ledger, so nothing is ever double-counted.
    Times: US open 1330/1430z | 15:45 ET 1945/2045z | US close 2000/2100z.
    [X11] div_carry: DECIMAL dividend (0.068 = 6.8%) to carry on the FAIR
    price on every day from the TAIWAN ex-date until the ADR goes ex. Leave
    0.0 except in that window. Without it the premium shows a fake spike of
    roughly the whole dividend — a guaranteed loser that looks like the
    biggest signal of the year. See [U5]."""
    c = _MANUAL['ctx']
    if c is None:
        raise RuntimeError('run setup_manual() first')
    date = str(date)
    n, thr = c['n'], c['thresh']
    gate_ok, gate_txt, _gamma, _chgsd = _gate(n, date)   # [X10][X12]
    _hl_led, _dr_led = _gate_levels(_gamma, gate_txt)    # [Y37g] for the ledger
    p = _MANUAL['pos']
    rows = []
    if not quiet:
        _W = 92                 # [Y39] wider: fair formulas fit now
        def _L(s=''):
            for _w in _wrap_box(s, _W - 4, indent=4):   # [Y39] wrap, never cut
                print('\u2502 ' + _w.ljust(_W - 4) + ' \u2502')
        def _R(l='\u251c', r='\u2524'): print(l + '\u2500' * (_W - 2) + r)
        print('\n\u250c' + '\u2500' * (_W - 2) + '\u2510')
        _L(f"{date}   {c['instrument']}" + (f"   {_G['dash']} {note}" if note else ''))
        _R()
        _L(f"ANCHORS    ordinary {ordinary:>10,.2f}   SSF 13:30 {fut_1330:>9,.2f}"
           f"   FX {fx:>7.4f}")
        _gate_txt = ('OPEN  ' + _G['dash'] + ' entries allowed' if gate_ok
                     else 'SHUT  ' + _G['dash'] + ' no new entry')
        _L(f"GATE       {_gate_txt}")
        _L(f"           {gate_txt}")
        if p:
            _held = (pd.Timestamp(str(date)) - pd.Timestamp(p['date'])).days
            _R()
            _L(f"POSITION   {'LONG' if p['dir'] == 1 else 'SHORT'} spread   "
               f"${p['notional']:,.0f}   opened {p['date']}   "
               f"held {_held}cd / {c['time_stop']}cd")
            _L(f"           entry ADR {p['entry_adr']:.4f}   SSF "
               f"{p['entry_fut']:.2f}   FX {p['entry_fx']:.4f}")
        _R()
    for key, label, a_px, f_px in (
            ('open', 'US open   1330/1430z', adr_open, fut_open),
            ('1945', '15:45 ET  1945/2045z', adr_1945, fut_1945),
            ('close', 'US close  2000/2100z', adr_close, fut_close)):
        if a_px in (None, 0) or f_px in (None, 0) or a_px != a_px or f_px != f_px:
            continue
        fair = _fair(ordinary, fut_1330, f_px, fx, div_carry)   # [X11]
        prem = (a_px / fair - 1.0) * 1e4
        z, mu, sd = _zstats(prem, n, date)
        # [X13] BUGFIX. This was `dev = prem - c['hist_mean']`, where
        # hist_mean is the LAST value of a 30-row rolling mean FROZEN at the
        # final backtest date. The backtest gates on
        #     |spread[t] - rolling(n).mean()[t-1]|
        # i.e. the LIVE rolling mean. _zstats had already computed exactly
        # that as `mu` and the result was thrown away, so the desk's cost
        # floor drifted away from the tested one as soon as the premium
        # level moved — permanently, and silently.
        dev = prem - mu if mu == mu else float('nan')
        if p is None:
            past = (z == z) and abs(z) >= thr
            dev_ok = (dev == dev) and abs(dev) >= c['min_dev_bps']
            can = past and dev_ok and gate_ok
            side = 'SHORT' if z > 0 else 'LONG'
            why = []
            if not past: why.append(f"|z| {abs(z):.2f} < {thr:.2f}")
            if not dev_ok: why.append(f"|dev| {abs(dev):.0f} < {c['min_dev_bps']:.0f}")
            if not gate_ok: why.append(f'gate shut ({gate_txt})')
            if not quiet:
                _L(f"{label}")
                _L(f"   ADR {a_px:>10.4f}   fair {fair:>10.4f}   premium "
                   f"{prem:>+7.0f}bps")
                _L(f"   deviation {dev:>+6.0f}bps      z {z:>+6.2f}   "
                   f"(band {_G['pm']}{thr:.2f})")
                if can:
                    _L(f"   {_G['tri']} ENTER {side} spread   "
                       f"({'sell ADR / long SSF' if side == 'SHORT' else 'buy ADR / short SSF'})")
                    _L(f"     edge over cost {abs(dev) - c['rt_cost_bps']:+.0f}bps"
                       f"   {_G['arrow']} {abs(dev):.0f}bps deviation vs "
                       f"{c['rt_cost_bps']:.0f}bps round trip")
                    _L(f"     enter('{side}', adr=<fill>, fut=<fill>, "
                       f"fx={float(fx):.4f}, date='{date}')")
                else:
                    _L(f"   {_G['dash']} no entry   ({'; '.join(why)})")
        else:
            m = _mtm(a_px, f_px, fx,
                     div_cash_pct if key == c.get('exec_point', 'close') else 0.0)
            held = (pd.Timestamp(date) - pd.Timestamp(p['date'])).days
            # [X9] the SAME cost exit_pos will charge — fees plus carry for
            # the days actually held. The old card charged ONE 12 bps fill
            # while the exit charged TWO, so every mark you looked at was
            # rosier than the exit that followed it.
            xc = _trade_cost(p['dir'], p['notional'], held,
                             adr_notional=p.get('adr_notional'),
                             hedge_notional=p.get('hedge_notional'))
            trig = []
            if (p['dir'] == -1 and z <= 0) or (p['dir'] == 1 and z >= 0):
                trig.append('Z crossed 0')
            if held >= c['time_stop']:
                trig.append(f"time stop {c['time_stop']}cd")
            if c['hard_stop_bps'] > 0 and m['bps'] <= -c['hard_stop_bps']:
                trig.append(f"hard stop {c['hard_stop_bps']:.0f}bps")
            if ((c['pt_bps'] > 0 and m['bps'] >= c['pt_bps'])
                    or (c['pt_z'] > 0 and z == z and abs(z) <= c['pt_z'])):
                trig.append('profit target')
            # [X12] GAMMA EXIT — the backtest's EXIT 3, which the desk did
            # not have at all: leave when tomorrow's EXPECTED reversion is
            # smaller than the carry you pay to wait for it.
            #     expected = |gamma| x |z| x sigma  (bps of premium)
            #     hurdle   = carry per day x days to the next mark
            # Without this the desk holds to the z-cross or the 25cd time
            # stop and bleeds carry the backtest would have cut.
            _gx = ''
            if (_gamma == _gamma and _gamma < 0 and z == z and sd == sd
                    and sd > 0):
                _exp_bps = abs(max(_gamma, -1.0)) * abs(z) * sd
                _bpd = (c['carry_long_bpd'] if p['dir'] == 1
                        else c['carry_short_bpd'])
                if _exp_bps < _bpd:
                    trig.append(f'gamma exit (expect {_exp_bps:.0f}bps/day '
                                f'< carry {_bpd:.1f}bps/day)')
                else:
                    _gx = (f"   gamma {_gamma:+.3f}: expect {_exp_bps:.0f}bps/day "
                           f"vs carry {_bpd:.1f}bps/day")
            if not quiet:
                _L(f"{label}")
                _L(f"   ADR {a_px:>10.4f}   premium {prem:>+7.0f}bps   "
                   f"z {z:>+6.2f}")
                _L(f"   MARK   ADR leg ${m['adr_leg']:>+10,.0f}   SSF leg "
                   f"${m['fut_leg']:>+10,.0f}"
                   + (f"   div ${m['div_leg']:>+9,.0f}" if m['div_leg'] else ""))
                _L(f"          unrealised ${m['gross']:>+10,.0f}  "
                   f"({m['bps']:+.0f}bps of ${p['notional']:,.0f})")
                _L(f"   EXIT NOW would net ${m['gross'] - xc:>+10,.0f}   "
                   f"(after ${xc:,.0f} = {c['rt_fee_bps']:.0f}bps fees + "
                   f"{held}cd carry)")
                if _gx:
                    _L(_gx)
                _L("   \u25b6 EXIT SIGNAL   " + ", ".join(trig) if trig
                   else "   \u2014 hold   (no exit trigger yet)")
                if trig:
                    _L(f"     exit_pos(adr={a_px:.4f}, fut={f_px:.2f}, "
                       f"fx={float(fx):.4f}, "
                       f"date='{date}')")
        rows.append(dict(instrument=c['instrument'], date=date, point=key,
                         side='', notional='',
                         ordinary=ordinary, fut_1330=fut_1330, fx=fx, adr=a_px,
                         fut=f_px, fair=round(fair, 4), premium_bps=round(prem, 2),
                         dev_bps=(round(dev, 1) if dev == dev else ''),
                         z=(round(z, 3) if z == z else ''),
                         gamma=(round(_gamma, 3) if _gamma == _gamma else ''),
                         hl=(round(_hl_led, 1) if _hl_led == _hl_led else ''),
                         drift=(round(_dr_led, 2) if _dr_led == _dr_led else ''),
                         n=n, threshold=thr, gate=('open' if gate_ok else 'shut'),
                         div_carry=div_carry, in_position=bool(p), net='',
                         note=note))
    if save and rows:
        led = _read_ledger()
        keys = {(r['date'], r['point']) for r in rows}
        # [X14] scope the replace to THIS instrument. Harmless today because
        # the ledger path is per-instrument, but the filter read as global.
        led = led[~led.apply(
            lambda r: (str(r['instrument']) == c['instrument']
                       and (str(r['date']), str(r['point'])) in keys), axis=1)]
        _write_ledger(pd.concat([led, pd.DataFrame(rows)], ignore_index=True))
        _rebuild()
        if not quiet:
            _R('\u2514', '\u2518')
            print(f"  saved {len(rows)} row(s); "
                  f"{len(_MANUAL['days'])} manual day(s) in context")
    # [W3] no return value: a bare add_day(...) in a cell would otherwise
    # auto-display the raw row dicts on top of the formatted card
    return None
def add_days(rows_list, save=True):
    """[U3] Backfill several days at once. Processed oldest-first so each
    day's z-window contains only the days genuinely before it.
    [X15] BUGFIX: this did `out += add_day(...)`, but add_day returns None by
    design ([W3], so a bare call in a notebook cell does not dump raw dicts on
    top of the formatted card). `[] += None` raises TypeError, so the
    documented backfill path crashed on its very first row. It now just calls
    add_day and reports how many days landed."""
    _rows = sorted(rows_list, key=lambda x: str(x.get('date')))
    for r in _rows:
        add_day(save=save, **r)
    print(f"[X15] backfilled {len(_rows)} day(s); "
          f"{len(_MANUAL['days'])} manual day(s) now in context")
    return None
def enter(side, adr, fut, fx, date, notional=None, note=''):
    """[U3] Record a real entry fill. Re-run to CORRECT it (the previous
    ENTRY on that date is replaced). side='LONG' or 'SHORT'."""
    c = _MANUAL['ctx']
    d = 1 if str(side).upper().startswith('L') else -1
    _nt_req = float(notional or c['notional'])
    # [Y32] snap the request to REAL units before anything is written: whole
    # SSF contracts, whole ADR shares. The ledger stores the SNAPPED ADR-leg
    # notional so every rebuild reproduces the same integer position.
    _u = _units(_nt_req, float(adr), float(fut), float(fx))
    nt = _u['adr_notional']
    # [X7] side and notional go in their OWN columns now. The note is free
    # text again and can no longer corrupt the position.
    row = dict(instrument=c['instrument'], date=str(date), point='ENTRY',
               side=('LONG' if d == 1 else 'SHORT'), notional=nt,
               # [Y32] the INTEGER units are FIRST-CLASS COLUMNS ([X7]
               # philosophy: real data never rides in free text). Stored,
               # not re-derived, so an fx_fill() that amends the entry FX
               # can never flip a contract count sitting on a rounding
               # boundary — the ticket you actually filled is the ticket
               # the desk marks.
               shares=int(_u['shares']), contracts=int(_u['contracts']),
               ordinary='', fut_1330='', fx=float(fx), adr=float(adr),
               fut=float(fut), fair='', premium_bps='', dev_bps='', z='',
               n=c['n'], threshold=c['thresh'], gate='', div_carry='',
               in_position=True, net='', note=str(note).strip())
    led = _read_ledger()
    led = led[~((led['point'] == 'ENTRY') & (led['date'].astype(str) == str(date)))]
    _write_ledger(pd.concat([led, pd.DataFrame([row])], ignore_index=True))
    _rebuild()
    p = _MANUAL['pos']
    banner(f"ENTRY — {'LONG' if d == 1 else 'SHORT'} spread ${nt:,.0f}",
           sub=f"{date}   ADR {float(adr):,.4f}   {HEDGE_LBL} "
               f"{float(fut):,.2f}   FX {float(fx):,.4f}")
    say(f"requested ${_nt_req:,.0f} -> REAL units: {_u['shares']:,d} ADR "
        f"shares (${_u['adr_notional']:,.0f}) vs {_u['contracts']} "
        f"{HEDGE_LBL} contracts (${_u['hedge_notional']:,.0f}, "
        f"1 = {c['contract_sh']:,.0f} sh x {LOCAL_CCY} {float(fut):,.1f} "
        f"/ {float(fx):.4f})", 'info')
    _mm_bps = abs(_u['mismatch']) / nt * 1e4
    say(f"leg mismatch ${_u['mismatch']:+,.0f} ({_mm_bps:.0f} bps) — the "
        f"rounding residue integer fills cannot avoid; it rides UNHEDGED",
        'info' if _mm_bps < 25 else 'warn')
    _fee0 = _fee_usd(_u['adr_notional'], _u['hedge_notional'])
    say(f"round-trip fees ${_fee0:,.0f} "
        f"({_fee0 / nt * 1e4:.0f} bps, per leg on its own size) + carry "
        f"{(c['carry_long_bpd'] if d == 1 else c['carry_short_bpd']):.1f} bps/day "
        f"({'funding+margin, you are LONG the ADR' if d == 1 else 'borrow+margin, you are SHORT the ADR'})",
        'info')
    _ts_date = (pd.Timestamp(date) + pd.Timedelta(days=c['time_stop'])).date()
    say(f"time stop {c['time_stop']}cd -> {_ts_date}", 'info')
    if _MANUAL['marks']:
        say(f"{len(_MANUAL['marks'])} existing close row(s) on/after this "
            f"date were re-marked against it", 'ok')
    return p
def cancel_entry():
    """[U3] Undo a wrong entry: deletes the open ENTRY row and rebuilds."""
    c = _MANUAL['ctx']
    p = _MANUAL['pos']
    if p is None:
        print('[U3] no open position to cancel'); return
    led = _read_ledger()
    led = led[~((led['point'] == 'ENTRY') & (led['date'].astype(str) == p['date'])
                & (led['instrument'] == c['instrument']))]
    _write_ledger(led)
    _rebuild()
    print(f"[U3] cancelled the ENTRY dated {p['date']} — position is now "
          f"{'flat' if _MANUAL['pos'] is None else 'still open (an earlier entry)'}")
def delete_day(date, point=None):
    """[U3] Remove a manual day (or one execution point of it) and rebuild.
    Use when a print was wrong and you do not have the right one yet."""
    c = _MANUAL['ctx']
    led = _read_ledger()
    m = (led['instrument'] == c['instrument']) & (led['date'].astype(str) == str(date))
    if point:
        m &= (led['point'].astype(str) == str(point))
    nrm = int(m.sum())
    _write_ledger(led[~m])
    _rebuild()
    print(f"[U3] deleted {nrm} row(s) for {date}"
          f"{'/' + point if point else ''} — {len(_MANUAL['days'])} manual day(s) left")
def exit_pos(adr, fut, fx, date, div_cash_pct=0.0, note=''):
    """[U3] Record the exit fill and print realised P&L vs the mark path."""
    c, p = _MANUAL['ctx'], _MANUAL['pos']
    if p is None:
        print('[U3] no open position'); return None
    m = _mtm(float(adr), float(fut), float(fx), div_cash_pct)
    held = (pd.Timestamp(date) - pd.Timestamp(p['date'])).days
    # [X9] identical call to the one the daily card makes, so the mark you
    # acted on and the trade you booked cannot disagree.
    cost = _trade_cost(p['dir'], p['notional'], held,
                       adr_notional=p.get('adr_notional'),
                       hedge_notional=p.get('hedge_notional'))
    _fee = (_fee_usd(p['adr_notional'], p['hedge_notional'])
            if p.get('adr_notional') and p.get('hedge_notional')
            else c['rt_fee_bps'] / 1e4 * p['notional'])   # [Y32]
    net = m['gross'] - cost
    # [X7] realised P&L goes in its own `net` column; premium_bps is left for
    # actual premiums. It used to store the P&L in bps under a column named
    # premium_bps, which is a trap for anyone hand-editing the ledger.
    row = dict(instrument=c['instrument'], date=str(date), point='EXIT',
               side=('LONG' if p['dir'] == 1 else 'SHORT'),
               notional=p['notional'],
               ordinary='', fut_1330='', fx=float(fx), adr=float(adr),
               fut=float(fut), fair='', premium_bps='',
               dev_bps='', z='', n=c['n'], threshold=c['thresh'], gate='',
               div_carry='', in_position=False, net=round(net, 2),
               note=f"held {held}cd {note}".strip())
    led = _read_ledger()
    led = led[~((led['instrument'] == c['instrument'])
                & (led['point'] == 'EXIT')
                & (led['date'].astype(str) == str(date)))]
    _write_ledger(pd.concat([led, pd.DataFrame([row])], ignore_index=True))
    print(f"\n[U3] CLOSED {p['date']} -> {date} ({held}cd) | "
          f"{'LONG' if p['dir'] == 1 else 'SHORT'} spread ${p['notional']:,.0f}")
    print(f"     ADR {p['entry_adr']:.4f} -> {adr} | SSF {p['entry_fut']:.2f} -> {fut}")
    print(f"     ADR leg ${m['adr_leg']:+,.0f} | SSF leg ${m['fut_leg']:+,.0f}"
          + (f" | TAIFEX div ${m['div_leg']:+,.0f}" if m['div_leg'] else ''))
    print(f"     GROSS ${m['gross']:+,.0f} - fees ${_fee:,.0f} "
          f"({c['rt_fee_bps']:.0f}bps) - carry ${cost - _fee:,.0f} ({held}cd) = "
          f"NET ${net:+,.0f} ({net / p['notional'] * 1e4:+.0f}bps)")
    print(f"     reminder: this EXCLUDES bid/ask and impact, on the assumption "
          f"your typed fills already crossed them. The backtest's full round "
          f"trip is {c['rt_cost_bps']:.0f}bps.")
    if _MANUAL['marks']:
        b = [x['bps'] for x in _MANUAL['marks']]
        print(f"     path: best mark {max(b):+.0f}bps | worst {min(b):+.0f}bps | "
              f"banked {net / p['notional'] * 1e4:+.0f}bps"
              + (f"  (gave back {max(b) - net / p['notional'] * 1e4:.0f}bps "
                 f"from the peak)" if max(b) > net / p['notional'] * 1e4 else ''))
    _rebuild()
    return net
def status():
    """[U3][Y30] Position, mark path, drawdown, and where the exits stand.
    Structured so the three questions you actually have — am I in? how is
    it doing? what closes it? — are answered top to bottom without
    hunting through a wall of text."""
    c = _MANUAL['ctx']
    if c is None:
        say('run setup_manual() first', 'bad'); return
    p = _MANUAL['pos']
    banner(f"{c['instrument']} PAPER DESK",
           sub=("FLAT" if p is None else
                f"{'LONG' if p['dir'] == 1 else 'SHORT'} spread since "
                f"{p['date']}, ${p['notional']:,.0f}"))
    # ---- 1. AM I IN, AND WHAT WOULD CLOSE IT? -------------------------
    if p is None:
        gate_ok, gtxt, _, _ = _gate(c['n'])   # [X10]
        say(f"Position: FLAT — the gate is {'OPEN' if gate_ok else 'SHUT'}",
            'ok' if gate_ok else 'info', gtxt)
    else:
        say(f"Entry: ADR {p['entry_adr']:.4f}  {HEDGE_LBL} "
            f"{p['entry_fut']:.2f}  FX {p['entry_fx']:.4f}", 'info')
        if p.get('contracts'):
            say(f"Units: {p['shares']:,d} ADR shares "
                f"(${p['adr_notional']:,.0f}) + {p['contracts']} "
                f"{HEDGE_LBL} contracts (${p['hedge_notional']:,.0f}) | "
                f"leg mismatch ${p['mismatch']:+,.0f} rides unhedged", 'info')
        if _MANUAL['marks']:
            g = [m['gross'] for m in _MANUAL['marks']]
            pk = [max(g[:i + 1]) for i in range(len(g))]
            dd = min(gg - pp for gg, pp in zip(g, pk))
            _last = _MANUAL['marks'][-1]
            say(f"Mark now ${g[-1]:+,.0f} ({_last['bps']:+.0f} bps)",
                'ok' if g[-1] >= 0 else 'warn',
                f"best ${max(g):+,.0f} / worst ${min(g):+,.0f}")
            say(f"Drawdown from peak mark ${dd:+,.0f} "
                f"({dd / p['notional'] * 1e4:+.0f} bps)",
                'warn' if dd / p['notional'] * 1e4 < -100 else 'info')
            held = (pd.Timestamp(_last['date']) - pd.Timestamp(p['date'])).days
            _left = c['time_stop'] - held
            say(f"Time stop: {held}cd used of {c['time_stop']}cd",
                'warn' if _left <= 3 else 'info', f"{_left}cd left")
            show_html_table(
                _pd.DataFrame([{'date': m['date'], 'mark $': m['gross'],
                                'bps': m['bps']}
                               for m in _MANUAL['marks'][-8:]]).set_index('date'),
                title='MARK PATH (last 8)',
                fmt={'mark $': '{:+,.0f}', 'bps': '{:+.0f}'})
    # ---- 2. THE Z CONTEXT THE DECISION RESTS ON -----------------------
    if _MANUAL['days']:
        _zr = []
        for d in _MANUAL['days'][-6:]:
            z, mu, sd = _zstats(d['premium'], c['n'], d['date'])
            _zr.append({'date': d['date'], 'premium bps': d['premium'], 'z': z})
        show_html_table(
            _pd.DataFrame(_zr).set_index('date'),
            title='YOUR LAST DAYS',
            fmt={'premium bps': '{:+,.0f}', 'z': '{:+.2f}'},
            note=f"z-context: {len(c['hist_premium'])} historical closes to "
                 f"{c['hist_last_date']} + {len(_MANUAL['days'])} of your own")
    # ---- 3. THE PAPER RECORD ------------------------------------------
    cl = _MANUAL.get('closed') or []
    if not cl:
        say('Paper P&L: no closed trades yet', 'info')
    else:
        tot = sum(t['net'] for t in cl)
        wins = sum(1 for t in cl if t['net'] > 0)
        _avg_nt = sum(t['notional'] for t in cl) / len(cl)
        _run, _peak, _dd = 0.0, 0.0, 0.0
        for t in cl:
            _run += t['net']; _peak = max(_peak, _run); _dd = min(_dd, _run - _peak)
        kv_table(
            f"PAPER P&L — {len(cl)} CLOSED TRADE(S)",
            [('total', f"${tot:+,.0f}",
              f"{tot / _avg_nt * 1e4:+.0f} bps of the average clip"),
             ('win rate', f"{wins / len(cl) * 100:.0f}%",
              f"avg ${tot / len(cl):+,.0f} per trade"),
             ('best / worst', f"${max(t['net'] for t in cl):+,.0f} / "
                              f"${min(t['net'] for t in cl):+,.0f}",
              f"avg hold {sum(t['held'] for t in cl) / len(cl):.0f}cd"),
             ('equity peak', f"${_peak:+,.0f}",
              f"max drawdown ${_dd:+,.0f}")])
        show_html_table(
            _pd.DataFrame([{'entry': t['entry_date'], 'exit': t['exit_date'],
                            'side': 'LONG' if t['dir'] == 1 else 'SHORT',
                            'notional': t['notional'], 'net $': t['net'],
                            'bps': t['net'] / t['notional'] * 1e4,
                            'cd': t['held']}
                           for t in cl[-6:]]).set_index('entry'),
            title='LAST TRADES',
            fmt={'notional': '{:,.0f}', 'net $': '{:+,.0f}', 'bps': '{:+.0f}',
                 'cd': '{:.0f}'})
    # ---- 4. [Y24] IS THE REGIME STILL THE ONE YOU ENTERED IN? ---------
    try:
        if p is not None and _MANUAL['days']:
            _d_ = _MANUAL['days'][-1]
            _z_, _mu_, _sd_ = _zstats(_d_['premium'], c['n'], str(_d_['date']))
            _ok_, _, _gm_, _ = _gate(c['n'], str(_d_['date']))
            _mk_ = _MANUAL['marks'][-1]['bps'] if _MANUAL['marks'] else None
            _lv_, _hd_, _ln_ = _position_health(_z_, _sd_, _gm_, _ok_,
                                                _d_['date'], _mk_)
            if _lv_:
                note_block(f"POSITION HEALTH [Y24] — {_hd_}", _ln_)
    except Exception as _e:
        say(f"[Y24] health check skipped: {_e}", 'warn')

def show_ledger(tail=40):
    """[U3] The saved record — the single source of truth. You may edit this
    CSV by hand; then run setup_manual() to reload.
    [X7] Columns that MATTER if you hand-edit: side (LONG/SHORT) and notional
    on ENTRY rows drive the position; net on EXIT rows is the realised P&L
    (blank it to force a recompute from the prints); div_carry is the [U5]
    dividend carry as a DECIMAL. `note` is free text and is never parsed."""
    c = _MANUAL['ctx']
    led = _read_ledger()
    if not len(led):
        print('[U3] ledger is empty'); return None
    print(f"[U3] {c['ledger']} — {len(led)} rows")
    try:
        from IPython.display import display
        display(led.tail(tail))
    except Exception:
        print(led.tail(tail).to_string(index=False))
    return led
def form():
    """[U3] Cell B: a fillable panel for daily input. Falls back to a
    copy-paste template if ipywidgets is unavailable."""
    try:
        import ipywidgets as W
        from IPython.display import display, clear_output
    except Exception:
        print("[U3] ipywidgets not installed. Use:\n\n"
              "add_day(date='2026-07-21',\n"
              "        ordinary=2360.0, fut_1330=2361.0, fx=32.30,\n"
              "        adr_open=190.0,  fut_open=2365.0,     # 1330/1430 UTC\n"
              "        adr_1945=192.0,  fut_1945=2400.0,     # 1945/2045 UTC\n"
              "        adr_close=195.0, fut_close=2420.0,    # 2000/2100 UTC\n"
              "        div_carry=0.0)   # [X11] non-zero only between the TW\n"
              "                         # ex-date and the ADR ex-date\n")
        return
    c = _MANUAL['ctx']
    if c is None:
        print('[U3] run setup_manual() first'); return
    L, S = W.Layout(width='158px'), {'description_width': '96px'}
    def F(d, v=None):
        return W.FloatText(value=v, description=d, layout=L, style=S)
    w = dict(date=W.Text(value=str(pd.Timestamp.today().date()),
                         description='Date', layout=W.Layout(width='215px'), style=S),
             note=W.Text(value='', description='Note',
                         layout=W.Layout(width='420px'), style=S),
             ordv=F('Ordinary'), f1330=F('SSF 13:30'), fx=F('FX 13:30'),
             ao=F('ADR'), fo=F('SSF'), fxo=F('FX (opt)'),    # [Y17][Y29]
             a19=F('ADR'), f19=F('SSF'), fx19=F('FX (opt)'),
             ac=F('ADR'), fc=F('SSF'), fxc=F('FX (opt)'),
             # [W6] 0 on ~99% of days. It is ONLY for the day the Taiwan
             # ordinary goes ex-dividend AND you are holding through it:
             # TAIFEX settles that cash through the margin account, crediting
             # a long SSF and debiting a short one. Enter it as a PERCENT of
             # the ordinary price (TSM quarter ~0.45, UMC year ~6.8). A number
             # here on any other day invents cash that never moved.
             div=F('TW ex-div %', 0.0),
             # [X11] the [U5] DIVIDEND CARRY, as a PERCENT. Non-zero ONLY on
             # the days between the TAIWAN ex-date and the (later) ADR
             # ex-date. Without it the premium carries a fake spike of
             # roughly the whole dividend and the z-score detonates.
             dcar=F('Div carry %', 0.0),
             side=W.Dropdown(options=['(none)', 'LONG', 'SHORT'], value='(none)',
                             description='Side', layout=W.Layout(width='190px'),
                             style=S),
             fadr=F('Fill ADR'), ffut=F('Fill SSF'), nt=F('Notional $', c['notional']))
    out = W.Output()
    def v(k):
        x = w[k].value
        return None if x in (None, 0) else float(x)
    def run(fn):
        def _cb(_):
            with out:
                clear_output()
                try:
                    fn()
                except Exception as e:
                    print(f'[U3] error: {e}')
        return _cb
    def _score():
        add_day(date=w['date'].value, ordinary=v('ordv'), fut_1330=v('f1330'),
                fx=v('fx'), adr_open=v('ao'), fut_open=v('fo'),
                adr_1945=v('a19'), fut_1945=v('f19'), adr_close=v('ac'),
                fut_close=v('fc'),
                fx_open=v('fxo'), fx_1945=v('fx19'), fx_close=v('fxc'),
                div_cash_pct=(w['div'].value or 0) / 100.0,
                div_carry=(w['dcar'].value or 0) / 100.0,   # [X11]
                note=w['note'].value)
    def _enter():
        if w['side'].value == '(none)':
            print('[U3] choose LONG or SHORT first'); return
        enter(side=w['side'].value, adr=v('fadr'), fut=v('ffut'), fx=v('fx'),
              date=w['date'].value, notional=v('nt'), note=w['note'].value)
    def _exit():
        exit_pos(adr=v('fadr'), fut=v('ffut'), fx=v('fx'), date=w['date'].value,
                 div_cash_pct=(w['div'].value or 0) / 100.0, note=w['note'].value)
    B = lambda t, s, cb, wd='128px': (
        lambda b: (b.on_click(cb), b)[1])(
        W.Button(description=t, button_style=s, layout=W.Layout(width=wd)))
    def _del_day():
        delete_day(w['date'].value)
    def _resc():
        print(f"[Y19] edit a day = fix the fields above and press Score day "
              f"again with the same date — add_day OVERWRITES that date's "
              f"rows in the ledger, then _rebuild() re-derives everything "
              f"from it. Nothing else to clean up.")
    btns = W.HBox([B('Score day', 'primary', run(_score)),
                   B('Record ENTRY', 'success', run(_enter)),
                   B('Record EXIT', 'warning', run(_exit)),
                   B('Status', '', run(status), '96px'),
                   B('Cancel entry', 'danger', run(cancel_entry), '118px')])
    btns2 = W.HBox([B('How to edit a day', 'info', run(_resc), '140px'),
                    B('Delete this date', 'danger', run(_del_day), '132px'),
                    B('Ledger', '', run(show_ledger), '96px'),
                    B('Chart z', '', run(zchart), '96px')])   # [Y20]
    H = lambda t: W.HTML(f"<b style='color:#666;font-size:11px'>{t}</b>")
    p = _MANUAL['pos']
    display(W.VBox([
        W.HTML(f"<h4 style='margin:2px 0'>{c['instrument']} paper desk"
               f"<span style='font-weight:400;color:#888;font-size:12px'> &nbsp;"
               f"history to {c['hist_last_date']} &middot; N={c['n']} "
               f"Z=±{c['thresh']} &middot; fair={c['fair_mode']} &middot; "
               f"{'POSITION OPEN since ' + p['date'] if p else 'flat'}"
               f"</span></h4>"),
        W.HBox([w['date'], w['note']]),
        H('DAILY ANCHORS &nbsp;(FX 13:30 = the TW fixing the SIGNAL uses [D2])'),
        W.HBox([w['ordv'], w['f1330'], w['fx'], w['dcar']]),
        H('US OPEN &mdash; 1330/1430 UTC &nbsp;(FX now is OPTIONAL and only '
          'affects MARKS when FX_MARK_MODE=\'snapshot\' [Y29] &mdash; leave '
          'it blank and everything uses the 13:30 fixing, exactly like the '
          'backtest)'),
        W.HBox([w['ao'], w['fo'], w['fxo']]),
        H('15:45 ET &mdash; 1945/2045 UTC &nbsp;(your signal / execution moment)'),
        W.HBox([w['a19'], w['f19'], w['fx19']]),
        H('US CLOSE &mdash; 2000/2100 UTC'),
        W.HBox([w['ac'], w['fc'], w['fxc']]),
        W.HBox([w['div'], W.HTML("<span style='color:#999;font-size:11px'>"
                "&larr; leave at 0 unless the Taiwan ordinary went ex-dividend "
                "today AND you are holding through it (TSM quarter &asymp;0.45, "
                "UMC year &asymp;6.8)</span>")]),
        H('YOUR ACTUAL FILL (optional)'),
        W.HBox([w['side'], w['fadr'], w['ffut'], w['nt']]),
        btns, btns2, out]))
def zchart(tail=90, save=None):
    """[Y20] TWO-PANEL VIEW OF THE LIVE SERIES, manual days included.
    Top: the premium — historical tail plus YOUR typed days — with the
         rolling N-mean and the \u00b1Z\u00b7sigma entry band, both computed
         with the BACKTEST convention (window ends the PREVIOUS day, ddof=0),
         so the band on each date is exactly what add_day scored against.
    Bottom: the rolling z itself, with the \u00b1threshold band and zero
         line; your entries/exits from the ledger are marked on both."""
    c = _MANUAL['ctx']
    if c is None:
        print('[U3] run setup_manual() first'); return
    n, thr = c['n'], c['thresh']
    hist = list(c['hist_premium'])
    man = _MANUAL['days']
    ser = pd.Series(hist + [d['premium'] for d in man], dtype=float)
    mu = ser.rolling(n).mean().shift(1)
    sd = ser.rolling(n).std(ddof=0).shift(1)
    zz = (ser - mu) / sd
    lo = max(0, len(ser) - int(tail) - len(man))
    x = _np.arange(len(ser))
    import matplotlib.pyplot as _plt
    fig, (ax1, ax2) = _plt.subplots(2, 1, figsize=(11, 6.4), sharex=True,
                                    gridspec_kw={'height_ratios': [3, 2]})
    ax1.plot(x[lo:len(hist)], ser.iloc[lo:len(hist)], lw=1.1, color='#546e7a',
             label='history (backtest closes)')
    if man:
        xm = x[len(hist):]
        ax1.plot(xm, ser.iloc[len(hist):], 'o-', ms=5, lw=1.4,
                 color='#1565c0', label='your typed days')
        for _xi, _d in zip(xm, man):
            ax1.annotate(str(_d['date'])[5:], (_xi, _d['premium']),
                         textcoords='offset points', xytext=(0, 7),
                         fontsize=7, ha='center', color='#1565c0')
    ax1.plot(x[lo:], mu.iloc[lo:], lw=1.0, color='#ef6c00',
             label=f'rolling mean (N={n}, to prev day)')
    ax1.fill_between(x[lo:], (mu + thr * sd).iloc[lo:],
                     (mu - thr * sd).iloc[lo:], color='#ef6c00', alpha=0.10,
                     label=f'\u00b1{thr:g}\u03c3 entry band')
    ax1.set_ylabel('premium (bps)')
    ax1.legend(loc='best', fontsize=8)
    ax2.plot(x[lo:], zz.iloc[lo:], lw=1.1, color='#37474f')
    if man:
        ax2.plot(x[len(hist):], zz.iloc[len(hist):], 'o', ms=5,
                 color='#1565c0')
    ax2.axhline(0, lw=0.8, color='#90a4ae')
    ax2.axhline(thr, lw=0.9, ls='--', color='#c62828')
    ax2.axhline(-thr, lw=0.9, ls='--', color='#c62828')
    ax2.set_ylabel('rolling z')
    ax2.set_xlabel(f'row (last {len(man)} = your inputs)')
    # entries / exits from the ledger, matched to manual dates
    _dt2x = {str(d['date']): x[len(hist) + i] for i, d in enumerate(man)}
    for t in (_MANUAL.get('closed') or []):
        for _dd, _mk, _cl in ((t.get('entry_date'), '^', '#2e7d32'),
                              (t.get('exit_date'), 'v', '#c62828')):
            if _dd and str(_dd) in _dt2x:
                ax1.axvline(_dt2x[str(_dd)], lw=0.7, ls=':', color=_cl,
                            alpha=0.6)
                ax2.plot(_dt2x[str(_dd)], 0, _mk, ms=8, color=_cl)
    if _MANUAL['pos'] and str(_MANUAL['pos']['date']) in _dt2x:
        ax1.axvline(_dt2x[str(_MANUAL['pos']['date'])], lw=1.0, ls=':',
                    color='#2e7d32')
    fig.suptitle(f"{c['instrument']} — premium & rolling z "
                 f"(N={n}, band \u00b1{thr:g})", fontsize=11)
    fig.tight_layout()
    if save:
        fig.savefig(save, dpi=130, bbox_inches='tight')
        print(f'saved {save}')
    _plt.show()
 
def chart(save=None):
    """[U3] Paper-desk chart: the premium with your manual days appended to the
    historical tail, the entry band, your fill, and the mark path. Purely a
    view — it reads the same read-only history plus your ledger."""
    c = _MANUAL['ctx']
    if c is None:
        print('[U3] run setup_manual() first'); return
    if not _MANUAL['days']:
        print('[U3] no manual days yet — add_day(...) first'); return
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    _tail = 60
    hist = c['hist_premium'][-_tail:]
    man = _MANUAL['days']
    man_x = [pd.Timestamp(d['date']) for d in man]
    man_y = [d['premium'] for d in man]
    # a synthetic x-axis for the historical tail: business days back from the
    # first manual date (exact dates are not needed for a shape view)
    h_x = list(pd.bdate_range(end=man_x[0] - pd.Timedelta(days=1),
                              periods=len(hist)))
    p = _MANUAL['pos']
    n_ax = 2 if (p or _MANUAL.get('closed')) else 1
    fig, axes = plt.subplots(n_ax, 1, figsize=(13, 4.2 * n_ax), sharex=False)
    axes = [axes] if n_ax == 1 else list(axes)
    ax = axes[0]
    ax.plot(h_x, hist, lw=0.8, color='#999', label=f'history (last {len(hist)})')
    ax.plot(man_x, man_y, lw=1.6, color='#1f77b4', marker='o', ms=4,
            label=f'your {len(man)} manual close(s)')
    _mu = float(np.mean(c['hist_premium'][-c['n']:]))
    _sd = float(np.std(c['hist_premium'][-c['n']:]))
    ax.axhline(_mu, color='black', lw=0.7, ls='-', label=f'rolling mean {_mu:+.0f}')
    for _k, _st in ((c['thresh'], '--'), (-c['thresh'], '--')):
        ax.axhline(_mu + _k * _sd, color='red', lw=0.8, ls=_st)
    ax.fill_between([h_x[0], man_x[-1]], _mu - c['thresh'] * _sd,
                    _mu + c['thresh'] * _sd, color='green', alpha=0.06,
                    label='no-trade band (' + _G['pm']
                          + f'{c["thresh"]:.2f}' + _G['sigma'] + ')')
    if p:
        ax.axvline(pd.Timestamp(p['date']), color='#c60', lw=1.4, ls=':')
        _ep = next((d['premium'] for d in man if d['date'] == p['date']), None)
        if _ep is not None:
            ax.scatter([pd.Timestamp(p['date'])], [_ep], s=130, zorder=6,
                       marker='v' if p['dir'] == -1 else '^',
                       color='#c60', edgecolor='k',
                       label=f"your entry ({'SHORT' if p['dir'] == -1 else 'LONG'})")
    ax.set_title(f"{c['instrument']} premium (bps) {_G['dash']} history to "
                 f"{c['hist_last_date']} + your manual days")
    ax.set_ylabel('premium, bps'); ax.grid(alpha=0.3); ax.legend(fontsize=8, loc='best')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    if n_ax == 2:
        ax = axes[1]
        mk = _MANUAL['marks']
        if mk:
            mx = [pd.Timestamp(m['date']) for m in mk]
            my = [m['gross'] for m in mk]
            ax.plot(mx, my, lw=1.6, marker='o', ms=4, color='#2ca02c')
            ax.fill_between(mx, 0, my, alpha=0.15, color='#2ca02c')
            ax.axhline(0, color='black', lw=0.8)
            _held_ch = (pd.Timestamp(mk[-1]['date'])
                        - pd.Timestamp(p['date'])).days
            _xc = _trade_cost(p['dir'], p['notional'], _held_ch,
                              adr_notional=p.get('adr_notional'),
                              hedge_notional=p.get('hedge_notional'))   # [X9]
            ax.axhline(_xc, color='red', ls='--', lw=0.8,
                       label=f'break-even (fees+carry) ${_xc:,.0f}')
            _pk = max(my); _dd = min(v - max(my[:i + 1]) for i, v in enumerate(my))
            ax.set_title(f"open position mark-to-market {_G['dash']} last "
                         f"${my[-1]:+,.0f} ({mk[-1]['bps']:+.0f}bps), peak "
                         f"${_pk:+,.0f}, drawdown ${_dd:+,.0f}")
            ax.legend(fontsize=8)
        cl = _MANUAL.get('closed') or []
        if cl and not mk:
            _run, _c = [], 0.0
            for t in cl:
                _c += t['net']; _run.append(_c)
            ax.bar(range(len(cl)), [t['net'] for t in cl],
                   color=['#2ca02c' if t['net'] > 0 else '#d62728' for t in cl])
            ax.plot(range(len(cl)), _run, color='k', lw=1.4, marker='o', ms=4,
                    label='cumulative')
            ax.axhline(0, color='black', lw=0.8)
            ax.set_title(f"closed paper trades {_G['dash']} {len(cl)} trade(s), total "
                         f"${_c:+,.0f}")
            ax.set_xticks(range(len(cl)))
            ax.set_xticklabels([t['exit_date'][5:] for t in cl], fontsize=7)
            ax.legend(fontsize=8)
        ax.set_ylabel('USD'); ax.grid(alpha=0.3)
    plt.tight_layout()
    if save:
        plt.savefig(save, dpi=140, bbox_inches='tight'); print(f'[U3] saved {save}')
    plt.show()
    return fig
def replay(last=None):
    """[U3] Re-show stored days in order. Nothing is cached, so this always
    reflects the current truth — use it after correcting a day."""
    ds = [d['date'] for d in _MANUAL['days']]
    if last:
        ds = ds[-int(last):]
    if not ds:
        print('[U3] no days stored yet'); return
    led = _read_ledger()
    for dt in ds:
        rows = led[(led['instrument'] == _MANUAL['ctx']['instrument'])
                   & (led['date'].astype(str) == str(dt))]
        _pt = _MANUAL['ctx'].get('exec_point', 'close')   # [X8]
        r = rows[rows['point'] == _pt]
        if not len(r):
            continue
        r = r.iloc[-1]
        _kw = {f'adr_{_pt}': float(r['adr']), f'fut_{_pt}': float(r['fut'])}
        add_day(date=str(dt), ordinary=float(r['ordinary']),
                fut_1330=float(r['fut_1330']), fx=float(r['fx']),
                div_carry=(_led_num(r, 'div_carry', 0.0) or 0.0),   # [X11]
                note=_txt(r.get('note')), save=False, **_kw)
def help_manual():
    """[U3][Y30] The cheat sheet — start here if you have forgotten the
    workflow. Renders as cards in a notebook, as aligned boxes in a
    terminal; same content either way."""
    banner("PAPER DESK — DAILY ROUTINE",
           sub="setup_manual() once per kernel, then one form() a day")
    menu([
        ("setup_manual()", "ONCE per kernel — restores your book from the ledger"),
        ("form()", "EVERY DAY — fill the panel, press 'Score / save day'"),
        ("add_day(date=..., ordinary=..., fut_1330=..., fx=...)",
         "the same thing by hand; adr_close/fut_close optional but wanted"),
        ("add_days([dict(...), dict(...)])", "BACKFILL several days at once"),
        ("enter('SHORT', adr=..., fut=..., fx=..., date=...)",
         "when the card says ENTER"),
        ("exit_pos(adr=..., fut=..., fx=..., date=...)",
         "when the card says EXIT"),
        ("fx_fill('2026-07-21', 32.31)",
         "NEXT MORNING — the REAL hedge FX, replaces the provisional rate"),
    ], title="THE LOOP")
    menu([
        ("status()", "paper book: closed trades, P&L, drawdown, exit verdict"),
        ("chart()", "premium + your days + band + the mark path"),
        ("zchart()", "rolling z + entry band incl. your typed days"),
        ("show_ledger()", "every saved row"),
        ("replay(last=5)", "re-show the last five days"),
    ], title="VIEWS")
    menu([
        ("add_day(...) again for the same date", "wrong price — it overwrites"),
        ("delete_day('2026-07-21')", "wrong date"),
        ("cancel_entry()", "wrong entry, then enter(...) again"),
        ("scrub_ledger(fix=True)", "find and remove fat-fingered rows"),
    ], title="CORRECTIONS — ALWAYS SAFE")
    say("Nothing is cached: a day's z is rebuilt from history + the days "
        "BEFORE it, so fixing Monday fixes Tuesday and everything after.",
        'ok')
    banner("THE THREE TIME POINTS", ch='─')
    menu([
        ("ordinary, fut_1330", "Taiwan anchors: ordinary close + the 13:30 "
                               "TAIPEI SSF print — together they set the gap"),
        ("adr_open, fut_open", "1330z summer / 1430z winter = US 09:30 open"),
        ("adr_1945, fut_1945", "1945z / 2045z = US 15:45, when you look and decide"),
        ("adr_close, fut_close", "2000z / 2100z = US 16:00 close — ONLY this "
                                 "pair feeds the rolling z, matching the backtest"),
    ], title="")
    say("Required every day: ordinary, fut_1330, fx. Any pair you leave "
        "out is simply skipped.", 'info')
    banner("WHAT THE LEDGER COLUMNS MEAN", ch='─')
    menu([
        ("premium_bps", "ADR vs fair, in bps: (ADR/fair - 1) x 10,000"),
        ("dev_bps", "premium MINUS the live rolling N-mean — the z-score's "
                    "NUMERATOR and the object the cost floor [H2] gates. "
                    "Sign kept: +ADR rich / -ADR cheap."),
        ("z", "dev divided by the rolling N-sigma (both lagged one day)"),
        ("gamma / hl / drift", "[Y37g] the gate's LEVELS that day — AR(1) "
                               "slope, implied half-life (days), [Z4] "
                               "mean-shift ratio. gate_history() charts the "
                               "trend."),
        ("gate", "'open'/'shut' — the verdict those levels produced"),
        ("net", "realised P&L, EXIT rows only"),
    ], title="")
    banner("FX — ONLY TWO NUMBERS MATTER  [Y29]", ch='─')
    menu([
        ("fx=", "the 13:30 TW-CLOSE fixing. Prices the fair, the premium, the "
                "z AND the marks — the convention every historical premium "
                "in the z-window was built with [D2]"),
        ("fx_fill(d, r)", "the NEXT TW OPEN, entered the following morning. "
                          "TWD spot is shut during US hours, so the rate on "
                          "your enter()/exit_pos() row is PROVISIONAL until "
                          "this call re-books the SSF leg"),
        ("fx_open/1945/close", "OPTIONAL — they change nothing unless you set "
                               "FX_MARK_MODE='snapshot'"),
    ], title="")
    note_block("[X11] DIVIDEND CARRY — the one input you must not forget", [
        "From the TAIWAN ex-date until the ADR goes ex, pass the dividend",
        "as a DECIMAL:      add_day(..., div_carry=0.068)    # 6.8%",
        "",
        "Why: the ordinary and the SSF have already dropped by the dividend",
        "while the ADR still carries the right, so the RAW premium jumps by",
        "roughly the whole dividend — +738 bps on UMC against a ~120 bps",
        "sigma. It detonates the z and fires a SHORT that cannot win: short",
        "the ADR and you owe the dividend, long the SSF and you were",
        "credited it. The legs cancel; you keep only the round trip.",
        "UMC pays ANNUALLY (ex ~mid-July), so this matters once a year — and",
        "costs you the biggest fake signal of the year if you miss it.",
        "",
        "On the ADR ex-date itself pass the cash instead, and stop the carry:",
        "                   add_day(..., div_cash_pct=0.068)",
    ])
    note_block("[X9] WHAT THE PAPER P&L CHARGES", [
        "fees  = ADR IN+OUT + SSF IN+OUT + 2x FX half-spread  (from config)",
        "carry = funding (long) or borrow-rebate (short) + margin,",
        "        per CALENDAR day",
        "",
        "NOT charged: bid/ask and market impact — the prices you type are",
        "your own fills and already crossed them. That is the ONLY",
        "difference from the backtest's round trip, which setup_manual()",
        "prints next to it. If you type MID prices rather than fills, the",
        "paper P&L is too generous by roughly the full spread.",
    ])

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
df_twd = get_historical_data(session, refDataService,
                             'TWD F093 Curncy', 'PX_LAST',
                             start_date, end_date).rename(columns={'px': 'TWD (Last)'})
df_2330 = get_historical_data(session, refDataService,
                              ORD_TICKER, 'PX_LAST',
                              start_date, end_date).rename(columns={'px': '2330 TT (Close)'})
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
        print(f"[P2] pre-close snapshots loaded: SSF {len(df_fut_pre)} rows, "
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
    print(f"[QC] {len(_only_close)} dates only in the TW-close file "
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
        _h = f"  {check:<34} {reading}"
        if not note:
            print(_h)
        elif len(_h) + 3 + len(str(note)) <= _TXT_W:      # [Y39] inline if it fits
            print(f"{_h}   {note}")
        else:
            print(_h)
            for _wl in _wrap_box(note, _TXT_W - 42, indent=0):
                print(f"  {'':<34}   {_wl}")
 
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
# (5) SSF vs spot basis at the SAME timestamp (13:30 Taipei vs TW close):
#     a front/next-month SSF should sit within ~+-3% of spot.
_basis = df['Fut_1330'] / df['2330 TT (Close)'] - 1.0
_bas_bad = _basis.abs() > 0.03
_QC_SUMMARY.append(('SSF 13:30 vs ordinary basis',
                    f"mean {_basis.mean()*100:+.2f}%, max |.| "
                    f"{_basis.abs().max()*100:.2f}%",
                    'same-timestamp basis should sit inside +/-3%'))
if not (HTML_OUTPUT and _in_jupyter()):
    print(f"  SSF basis: mean {_basis.mean()*100:+.2f}% | max |.| "
          f"{_basis.abs().max()*100:.2f}%")
if _bas_bad.any():
    _audit(f"{int(_bas_bad.sum())} rows with |SSF/spot basis| > 3% — wrong "
           f"contract in the snapshot file? Dates:")
    if not (HTML_OUTPUT and _in_jupyter()):
        print(df.loc[_bas_bad, ['Date', '2330 TT (Close)', 'Fut_1330']]
              .head(8).to_string(index=False))
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
         'both jobs resolve the front month by the same Taipei date, so '
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
    _inp('large overnight SSF moves', f"{int(bad_gap.sum())} row(s) > 6%",
         ', '.join(f"{df['Date'].iloc[_i]} "
                   f"{df['fut_gap_ret'].iloc[_i]*100:+.1f}%"
                   for _i in df.index[bad_gap][:4]))
# [P1] merge the REGN next-morning open and quantify the conversion:
if df_fx_regn is not None and len(df_fx_regn):
    df_fx_regn['Date'] = df_fx_regn['Date'].astype(str)
    df = pd.merge(df, df_fx_regn, on='Date', how='left')
    _pop = df['TWD_regn_open'].notna().mean()
    _band_bad = ((df['TWD_regn_open'] < 25) | (df['TWD_regn_open'] > 36)).sum()
    print(f"[P1] {FX_SPOT_TICKER} {FX_SPOT_FIELD}: populated on "
          f"{_pop*100:.0f}% of aligned days | {int(_band_bad)} values outside "
          f"25-36 band")
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
        print(f"[P1] unhedged conversion window (TW-close fixing -> next TW "
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
_inp('fair-price FX [D2]', "TW-close BFIX ('TWD F093')",
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
        _bad_band = ((df['TWD_regn_open'] < 25) | (df['TWD_regn_open'] > 36))
        if (_bad_band & df['TWD_regn_open'].notna()).any():
            print(f"[P1] WARNING: {int(_bad_band.sum())} REGN opens outside "
                  f"25-36 — check the quote convention")
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
    _inp('overnight SSF outliers', f"{int(_gout.sum())} row(s) > 4 sigma",
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
# [S5][V32-FIX1] the pre-ex-date flag used to be BUILT HERE — but its
# second loop reads df['div_ret_adr'], which is only created a few
# hundred lines below ([26][G1]). It survived because the switch
# defaults to 0; turning it on raised a KeyError. The block now lives
# directly after div_ret_adr is created, just before [U5].
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
    print("        INSTRUMENTS dict with (ex_date, cash per share in TWD)")
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
# [S5][V32-FIX1] flag the rows sitting just before a detected ex-date —
# moved BELOW div_ret_adr's creation so BLOCK_ENTRY_EXDATE_DAYS > 0 no
# longer dies on a missing column.
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
# [R5] EX-DATE BEHAVIOUR OF THE FUTURES — the hedge must be
# dividend-NEUTRAL. Theory: a futures already trades at
# spot - PV(dividend), so on the ex-date the SPOT drops and the FUTURES
# does not. If this data shows the futures dropping too, a long-futures
# hedge held through the ex-date books the dividend as a real loss
# WHILE the short-ADR leg is separately charged the same dividend —
# one cash flow counted twice. Measure it, do not assume it.
# ============================================================
_exd = [i for i in df.index[df['div_ret_hedge'] > 0.0005] if i > 0]
if _exd:
    print(f"[R5] futures behaviour on {len(_exd)} detected ex-date(s):")
    _n_follow = 0
    _R5_ROWS = []                      # [Y27] one table instead of 3 lines/date
    for _i in _exd:
        _dv = df['div_ret_hedge'].iloc[_i]
        _sp = df['2330 TT (Close)'].iloc[_i] / df['2330 TT (Close)'].iloc[_i-1] - 1
        _ft = df['Fut_1330'].iloc[_i] / df['Fut_1330'].iloc[_i-1] - 1
        _fol = _ft < -0.5 * _dv
        # [S2] if [R7] flagged a contract break on/next to this ex-date,
        # the drop is a SPLICE and is already handled by the spine
        # bridge — it must not ALSO vote for the dividend adjustment,
        # or the same step would be corrected twice.
        _brk = bool(df['contract_break'].iloc[max(_i-1, 0):_i+2].any()) \
            if 'contract_break' in df.columns else False
        _n_follow += int(_fol and not _brk)
        # [R7] the decisive reading: does the contract price the dividend?
        _bas = (df['Fut_1330'].iloc[_i-1] / df['2330 TT (Close)'].iloc[_i-1] - 1)
        _spans = _bas < -0.5 * _dv
 
        # [T1] EXPECTED under the confirmed TAIFEX mechanism: basis near
        # parity before the ex-date (no discount is needed, the dividend
        # is paid in cash), and the quoted futures DOES fall with the
        # spot on the ex-date. FUT_DIV_CASH then books the margin credit.
        _par = abs(_bas) < 0.5 * _dv          # no pre-discount = as expected
        _vrd, _lvl5 = (
            ('as expected — cash mechanism', 'ok') if (_par and _fol) else
            ('parity but futures did NOT fall — check the print', 'warn')
            if (_par and not _fol) else
            ('pre-discount + fell — verify it is a TAIFEX stock future', 'warn')
            if (not _par and _fol) else
            ('behaves NON-adjusted — FUT_DIV_CASH would double-count', 'bad'))
        # [R5] TW vs ADR ex-date alignment — the only thing left to watch
        _adr_ex = list(df.index[df['div_ret_adr'] > 0.0005])
        _near = [j for j in _adr_ex if abs(j - _i) <= 10]
        if _near:
            _j = min(_near, key=lambda x: abs(x - _i))
            _lag = int((df['Date_dt'].iloc[_j] - df['Date_dt'].iloc[_i]).days)
            _adr_txt = f"{df['Date'].iloc[_j]} ({_lag:+d}d)"
        else:
            _adr_txt = _badge('none within 10 rows', 'warn')
        _R5_ROWS.append({
            'TW ex-date': df['Date'].iloc[_i], 'div %': _dv * 100,
            'basis prior %': _bas * 100, 'needs %': -_dv * 100,
            'spot 1d %': _sp * 100, 'fut 1d %': _ft * 100,
            'ADR ex-date': _adr_txt, 'reading': _badge(_vrd, _lvl5)})
    if _R5_ROWS:
        show_html_table(
            _pd.DataFrame(_R5_ROWS).set_index('TW ex-date'),
            title='[R5] FUTURES BEHAVIOUR ON EX-DATES',
            fmt={'div %': '{:+.2f}', 'basis prior %': '{:+.2f}',
                 'needs %': '{:.2f}', 'spot 1d %': '{:+.2f}',
                 'fut 1d %': '{:+.2f}'},
            note='TAIFEX settles the dividend in CASH through the margin '
                 'account, so the correct signature is NO pre-discount in the '
                 'basis and the quoted future falling with the spot. '
                 "'needs %' is the discount a dividend-SPANNING contract "
                 'would have to carry instead. Where the TW and ADR ex-dates '
                 'differ, the premium carries a spurious step over that '
                 'window: the two-leg P&L nets it out, the SIGNAL does not '
                 '(that is what div_carry corrects [U5][X11]).')
    _majority = _n_follow > len(_exd) / 2
    if HEDGE_DIV_ADJ == 'auto':
        HEDGE_DIV_ADJ_ON = bool(_majority)
        print(f"[R5] 'auto': {_n_follow} of {len(_exd)} ex-date(s) show the "
              f"futures dropping with the spot -> adjustment "
              f"{'ON' if HEDGE_DIV_ADJ_ON else 'OFF'}. "
              + ("The data contradicts the no-drop theory, so the raw path "
                 "would double-count the dividend against the ADR leg."
                 if HEDGE_DIV_ADJ_ON else
                 "The futures held through the ex-date exactly as theory "
                 "predicts, so the raw path is already dividend-neutral and "
                 "no adjustment is applied."))
    else:
        HEDGE_DIV_ADJ_ON = bool(HEDGE_DIV_ADJ)
        print(f"[R5] HEDGE_DIV_ADJ forced to {HEDGE_DIV_ADJ_ON}")
    if _majority:
        print(f"[R5] NOTE: check whether those ex-date rows are also [K5] "
              f"suspect-gap rows — a stale or wrong-contract print near the "
              f"ex-date can masquerade as the futures 'following' the spot.")
else:
    HEDGE_DIV_ADJ_ON = False
    print("[R5] no ex-dates detected in the hedge spine -> no dividend "
          "adjustment needed")
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
        _verdict.append("SSF 13:30 print >2% off the ordinary close — check the print")
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
print(f"\n  [D2][F1] FX-source behaviour test on 'TWD (Last)':")
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
# [H2] FX-NOISE FLOOR — with only the TW-close fixing available, the
# fair price carries yesterday-afternoon FX and the overnight USDTWD
# move becomes pure NOISE in the spread. Quantify it: the next-day
# fixing change proxies the overnight move; its sigma, scaled by
# Fair/ADR, is the noise floor in bps of ADR price. Compare with the
# signal's own deviation sigma and print a suggested MIN_ENTRY_DEV_BPS
# (~2x the floor). Remember: LIVE trading sees the live NDF at 21:30
# and does NOT have this noise — the backtest is the conservative one.
_fx_on_sigma = float(_fx_next_chg.std())
_fair_over_adr = float((df['Fair Price'] / df['ADR Ref Px']).median())
_fx_floor_bps = _fx_on_sigma * _fair_over_adr * 10000
_dev_raw = (df['Spread (Signal)']
            - df['Spread (Signal)'].rolling(30, min_periods=10).mean().shift(1))
_dev_sigma_bps = float((_dev_raw if SIGNAL_MODE == 'premium'      # [Y1] already bps
                        else _dev_raw / df['ADR Ref Px'] * 10000).std())
print(f"\n  [H2] FX-noise floor: overnight-FX sigma ~{_fx_on_sigma*100:.2f}% "
      f"-> ~{_fx_floor_bps:.0f} bps of spread noise | signal deviation sigma "
      f"~{_dev_sigma_bps:.0f} bps")
if _dev_sigma_bps > 0:
    print(f"       FX noise = {_fx_floor_bps/_dev_sigma_bps*100:.0f}% of the "
          f"signal sigma. Suggested MIN_ENTRY_DEV_BPS ~ "
          f"{2*_fx_floor_bps:.0f} (currently {MIN_ENTRY_DEV_BPS}); live "
          f"trading uses the live NDF and has no such floor.")
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
    # [C3][O1] FX conversion cost, both ways, on the futures-leg
    # notional: NDF spread if hedging immediately, onshore-spot spread
    # (incl. bank markup) if converting at the next TW open.
    _fx_half = (FX_SPOT_HALF_SPREAD_BPS if FX_EXEC_MODE == 'spot_next_open'
                else FX_NDF_HALF_SPREAD_BPS)
    fx_cost = 2 * _fx_half / 10000 * fut_notional
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
    print(f"[COST] 1 SSF contract = {FUT_CONTRACT_SHARES:,} sh x TWD "
          f"{fut_px_twd:,.0f} = TWD {FUT_CONTRACT_SHARES * fut_px_twd / 1e6:.2f}M "
          f"/ {fx:.2f} = US${contract_usd / 1e3:,.0f}k")
    print(f"[COST] {win_min}-min worked execution | futures leg "
          f"{n_c:.1f} contracts vs supply: BID side ~{cap_bid:.0f} "
          f"(L1 {fut_bid_l1} + {fut_refill}/min), ASK side ~{cap_ask:.0f} "
          f"(L1 {fut_ask_l1} + {fut_refill}/min) | ADR leg "
          f"{notional / adr_wv * 100:.2f}% of ${adr_wv / 1e6:.0f}M window")
    if n_c > min(cap_bid, cap_ask):
        print(f"[COST] WARNING: futures leg exceeds the THIN side's supply — "
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
    beta_arr = df['beta'].values
    exec_px_arr = df['Exec Px'].values
    fut_arr = df['Fut_2130'].values     # raw contract prices (EXACT fills)
    hedge_arr = df['Hedge Idx'].values  # [24][26] roll-safe TR spine
    adr_close_arr = df['TSM US (Close)'].values
    fx_arr = (df['TWD (Last)'].values if 'TWD (Last)' in df.columns
              else np.full(len(df), 32.4))   # [E2] contract-value FX
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
    # [R5] dividend-adjusted futures path for hedge valuation
    # [V2] the two dividend treatments are ALTERNATIVES, never both: the cash
    # credit ([T3], correct for TAIFEX) and the price-path scaling
    # (HEDGE_DIV_ADJ, the older fudge) would each add the dividend once, so
    # running both credits it twice. FUT_DIV_CASH wins.
    if (globals().get('HEDGE_DIV_ADJ_ON', False) and FUT_DIV_CASH):
        raise RuntimeError(
            "[V2] FUT_DIV_CASH and HEDGE_DIV_ADJ are both ON — that double-"
            "counts the dividend on the SSF leg. Set HEDGE_DIV_ADJ=False "
            "(correct for TAIFEX, the cash credit handles it) or "
            "FUT_DIV_CASH=False (only for a market whose futures are "
            "pre-discounted).")
    if (globals().get('HEDGE_DIV_ADJ_ON', False)
            and 'div_ret_hedge' in df.columns):
        _divf = (1.0 + df['div_ret_hedge'].fillna(0.0).values).cumprod()
    else:
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
                if MAX_BOOK_PARTICIPATION > 0:
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
                               / fx_arr[fill_t])
                    _cap_usd = MAX_BOOK_PARTICIPATION * _supply * _c_usd0
                    if _cap_usd > 0 and trade_notional > _cap_usd:
                        capped_notional_events += 1
                        capped_notional_usd += trade_notional - _cap_usd
                        trade_notional = _cap_usd
                        size_mult = trade_notional / NOTIONAL
                # [E2] snap to a whole number of SSF contracts using
                # the day's ACTUAL TWD price and FX (contract_usd =
                # 2,000 x Fut(TWD) / USDTWD) — both legs then size off
                # the snapped notional, killing the rounding mismatch
                _c_usd = (FUT_CONTRACT_SHARES * fut_arr[fill_t]
                          / fx_arr[fill_t])
                if ALIGN_TO_CONTRACTS:
                    n_contracts = max(1, int(round(trade_notional / _c_usd)))
                    trade_notional = n_contracts * _c_usd
                else:
                    n_contracts = trade_notional / _c_usd
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
                # [T3] and the SSF margin-account dividend: TAIFEX credits
                # the LONG and debits the SHORT the full cash dividend on
                # the ex-date. The futures position is -position, and the
                # TWD cash is converted at the EX-DATE's rate, not the
                # entry or exit rate.
                if FUT_DIV_CASH:
                    fut_div_cash += (-position * entry_beta * trade_notional
                                     * div_hedge_arr[t]
                                     * fx_arr[entry_day] / fx_arr[t])
            if pnl_mode == 'two_leg':
                adr_leg = (position * (exec_px_arr[t] - entry_price) * shares
                           + div_accrued)
                fut_leg = (-position * entry_beta * trade_notional
                           * (_hedge_growth(t, entry_fut_raw, entry_ym) - 1.0)
                           * (fx_arr[entry_day] / fx_arr[t]))
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
                          * (fx_arr[entry_day] / fx_arr[t]))
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
            daily_carry += (entry_beta * trade_notional
                            * (margin_ann_bps() / 10000) / 360)   # [T4] flat 24bps
            # [C3][D1][O1] NDF carry is SIGNED and flips with direction
            # — but ONLY in ndf_immediate mode; spot conversion at the
            # next TW open has no forward points. Floor the hurdle at
            # 0 so a net POSITIVE carry never manufactures a fake
            # gamma exit.
            if FX_EXEC_MODE == 'ndf_immediate':
                daily_carry -= (position * trade_notional
                                * (FX_CARRY_LONG_SPREAD_ANN_BPS / 10000) / 360)
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
            # [R9] EXIT 3b: z-band profit target. [V32-FIX3] the BPS target
            # was checked HERE a second time — identical condition to the
            # [S2] check above the hard stop, so the duplicate could never
            # fire and is removed; the [S2] one (earlier in the exit chain)
            # is the single check.
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
                    _fx_ratio = fx_arr[entry_day] / fx_arr[fill_t]
                    fut_leg_pnl = (-position * entry_beta * trade_notional
                                   * (_hedge_growth(fill_t, entry_fut_raw,
                                                    entry_ym) - 1.0) * _fx_ratio)
                    if fill_t > t and FUT_DIV_CASH:   # lag: fill-day cash
                        fut_div_cash += (-position * entry_beta * trade_notional
                                         * div_hedge_arr[fill_t]
                                         * fx_arr[entry_day] / fx_arr[fill_t])
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
                exec_cost, exec_cost_bps = compute_exec_cost(
                    trade_notional, is_stress, k_adr_today, k_fut_today,
                    beta_arr[fill_t], cost_mult=cost_mult,
                    fut_px_twd=fut_arr[fill_t], fx=fx_arr[fill_t])
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
                margin_cost = (entry_beta * trade_notional
                               * (margin_ann_bps() / 10000 / 360)
                               * calendar_days)   # [T4] flat 24bps, not SOFR-linked
                # [C3][D1][O1] SIGNED NDF carry (ndf_immediate mode
                # only): positive = COST, negative = CREDIT. In
                # spot_next_open mode there are no forward points —
                # the spot spread sits inside exec_cost.
                fx_hedge_cost = ((-position * trade_notional
                                  * (FX_CARRY_LONG_SPREAD_ANN_BPS / 10000 / 360)
                                  * calendar_days)
                                 if FX_EXEC_MODE == 'ndf_immediate' else 0.0)
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
_fx_now = float(df['TWD (Last)'].iloc[-1])
exec_normal, bps_normal = compute_exec_cost(NOTIONAL, False, K_ADR_FALLBACK, K_FUT_FALLBACK, 1.0,
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
exec_stress, bps_stress = compute_exec_cost(NOTIONAL, True, K_ADR_FALLBACK, K_FUT_FALLBACK, 1.0,
                                            fut_px_twd=_fut_px_now, fx=_fx_now)
report_participation(NOTIONAL, _fut_px_now, _fx_now)   # [C5][E3]
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
        {'setting': 'of which fees (ADR+SSF+FX)',
         'value': f"{_fee_sum:.0f} bps "
                  f"(ADR {ADR_FEE_IN_BPS}+{ADR_FEE_OUT_BPS}, "
                  f"SSF {FUT_FEE_IN_BPS}+{FUT_FEE_OUT_BPS}, FX 2x"
                  f"{FX_SPOT_HALF_SPREAD_BPS if FX_EXEC_MODE == 'spot_next_open' else FX_NDF_HALF_SPREAD_BPS:g})"},
        {'setting': 'of which spread + impact',
         'value': f"{bps_normal - _fee_sum:.1f} bps"},
        {'setting': 'Funding (long ADR)',
         'value': f"SOFR + {FUNDING_SPREAD_ANN*100:.1f}% (daily series)"},
        {'setting': 'Borrow (short ADR)', 'value': f"{BORROW_ANN_BPS} bps flat"},
        {'setting': 'SSF margin drag', 'value': f"{FUT_MARGIN_ANN_BPS} bps flat"},
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
          f"fees ADR {ADR_FEE_IN_BPS}+{ADR_FEE_OUT_BPS} | SSF {FUT_FEE_IN_BPS}+{FUT_FEE_OUT_BPS} | "
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
_x2_parts = [('SSF half-spread x2', 2 * _x2_hs_f),
             ('ADR fee OUT', ADR_FEE_OUT_BPS),
             ('FX spread x2', 2 * (FX_SPOT_HALF_SPREAD_BPS
                                   if FX_EXEC_MODE == 'spot_next_open'
                                   else FX_NDF_HALF_SPREAD_BPS)),
             ('ADR half-spread x2', 2 * _x2_hs_a),
             ('SSF fees IN+OUT', FUT_FEE_IN_BPS + FUT_FEE_OUT_BPS),
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
        ('FX execution [O1]', "onshore SPOT at the next TW open "
                              "('USDTWD REGN', PX_OPEN)",
         f"half-spread {FX_SPOT_HALF_SPREAD_BPS} bps x2 = "
         f"{2*FX_SPOT_HALF_SPREAD_BPS} bps RT cost"),
        ('unhedged window', f"sigma ~{_fx_win_sig*100:.2f}% per conversion",
         'mean-zero RISK, not a cost; 2 conversions per round trip [P1]'),
        ('FX carry [T2]', '0 by construction',
         'deliverable onshore spot has no forward points; carry exists only '
         'in ndf_immediate mode, and only once the desk supplies '
         'FX_CARRY_LONG_SPREAD_ANN_BPS')]
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
              'notional snapped to whole SSF contracts'),
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
# [Y35] AUTO-RELAX: if the joint constraints empty the candidate set, drop
# ONLY the win-rate floor (the softest, most sample-noisy constraint) and
# say so — an empty set otherwise silently degrades the whole selection to
# the raw in-sample argmax, which is the worst of all options.
if not _pass.any():
    _pass = ((results_trades >= _eff_min_trades)
             & _n_ok
             & (results_tpy >= MIN_TRADES_PER_YEAR)
             & (np.abs(results_ddpct) <= MAX_DD_SELECT_PCT)
             & (results_pnl > 0))
    if _pass.any():
        say(f"[Y35] no cell cleared the win-rate floor "
            f"({MIN_WIN_RATE_SELECT:.0f}%) jointly with the other limits — "
            f"floor DROPPED for selection (drawdown/trade floors kept) so "
            f"the risk-aware ranking still runs instead of degrading to "
            f"the raw PnL argmax", 'warn')
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
    # [Y36] no separate banner — the table itself carries the title
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
        _dir = 'LONG spread (buy ADR / short SSF)' if _t['direction'] == 1 \
            else 'SHORT spread (sell ADR / long SSF)'
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
              f"${_t['trade_notional']:,.0f} = {_t['n_contracts']} SSF contracts")
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
        print(f"      SSF leg   : {_t['entry_fut']:.1f} -> {_t['exit_fut']:.1f} TWD "
              f"({_fut_ret*100:+.2f}% TWD raw) x FX(entry/exit)  =>  "
              f"${_t['fut_leg_pnl']:,.0f}{_roll_note}")
        if _t.get('fut_div_cash') is not None and abs(_t.get('fut_div_cash') or 0) > 0.5:
            print(f"                  + TAIFEX margin-account dividend "
                  f"${_t['fut_div_cash']:+,.0f} [T3] (long SSF is credited the "
                  f"cash dividend, short is debited — this is why the quoted "
                  f"futures may fall on the ex-date without the hedge losing)")
        print(f"      GROSS     : ADR ${_t['adr_leg_pnl']:,.0f} + SSF ${_t['fut_leg_pnl']:,.0f} "
              f"= ${_t['gross_pnl']:,.0f}")
        print(f"      costs     : exec ${_t['exec_cost']:,.0f} ({_t['exec_cost_bps']:.0f}bps) "
              f"| fund ${_t['funding_cost']:,.0f} | borrow ${_t['borrow_cost']:,.0f} "
              f"| margin ${_t.get('margin_cost', 0):,.0f} | fxcarry ${_t['fx_hedge_cost']:,.0f} "
              f"| roll ${_t.get('roll_cost', 0):,.0f}  = ${_t['total_cost']:,.0f}")
        print(f"      NET       : ${_t['gross_pnl']:,.0f} - ${_t['total_cost']:,.0f} "
              f"= ${_t['net_pnl']:,.0f}  ({_t['net_pnl']/_t['trade_notional']*1e4:+.0f} bps) "
              f"| exit: {_t['exit_reason']}")
    print("\n  Re-derivation: ADR leg = shares x (exit-entry px) x sign;")
    print("  SSF leg = -dir x notional x (exit_fut/entry_fut - 1) x FX(entry)/FX(exit)")
    print("            + the TAIFEX margin-account cash dividend [T3]")
    print("            [EXCEPT roll-straddling trades: those use the spliced")
    print("             hedge growth, flagged inline above];")
    print("  net = ADR + SSF + div - all costs. Any NON-straddle line that")
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
for _lbl, _grp in (('LONG spread (buy ADR / short SSF)', _lg),
                   ('SHORT spread (sell ADR / long SSF)', _sh)):
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
    _mf = [t['mfe_bps'] for t in _tr_all]
    _act = [t['net_pnl'] / t['trade_notional'] * 1e4 for t in _tr_all]
    _base_pnl = sum(t['net_pnl'] for t in _tr_all)
    _s3 = []
    # [Y34] DYNAMIC TARGET LADDER — the fixed (50..400) ladder stopped
    # exactly where it got interesting: the MFE tail. Extend the ladder
    # to the distribution actually observed: fixed rungs up to 400, then
    # the MFE p90 / p95 / p99 rounded to 50s, capped at the max. A run
    # whose trades peak at +1,000 bps now scans 500/600/800-style rungs
    # instead of stopping at 400.
    _tail_rungs = sorted({int(round(np.percentile(_mf, q) / 50.0) * 50)
                          for q in (90, 95, 99)} | {500, 600})
    _ladder = [t for t in
               sorted(set([50, 100, 150, 200, 300, 400] + _tail_rungs))
               if 0 < t <= max(_mf)]
    for _tg in _ladder:
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
            title=(f"[S3] PROFIT-TAKING SCAN — REFERENCE ONLY "
                   f"(N={best_n}, Z={best_thresh})"),
            fmt={'est. PnL': '${:,.0f}', 'vs actual': '${:+,.0f}',
                 'trades reaching it': '{:.0f}', 'of': '{:.0f}'},
            note=f"NOTHING HERE IS ACTIVE. PROFIT_TARGET_BPS is "
                 f"{PROFIT_TARGET_BPS}"
                 f"{' (OFF — exits stay z-cross / gamma / time stop)' if not PROFIT_TARGET_BPS else ' (ON)'}"
                 f"; this table only reports what each target WOULD have "
                 f"banked. MFE across {len(_tr_all)} trades: median "
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
        # a warm-up row has no z yet — show a dash, not '+nan'
        _z4s = f"{_zz4:+.2f}" if _zz4 == _zz4 else '\u2014'
        print(f"  {_d4:<12}{_dv4:>+7.0f}{_z4s:>7}  {_v4}")
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
(same-stock SSF: expect >0.9; much lower = data problem) | residual {resid_std*100:.2f}%/day
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
# [Y8] setup_manual — HTML card (text fallback preserved)
# ============================================================================
_setup_manual_v31_11 = setup_manual
 
def setup_manual(reload=True):
    """[Y8] Same initialisation as v31.11 (context + ledger restore), but the
    summary renders as one HTML card in Jupyter instead of the 78-column
    box-drawing panel. Outside Jupyter it falls back to the old print.
    [V32-FIX4] NOTE: this SHADOWS the [U3] definition above — edits must
    land in both copies or they silently diverge."""
    if not _in_jupyter():
        return _setup_manual_v31_11(reload=reload)
    _MANUAL.update(ctx=get_manual_context(), days=[], pos=None, marks=[])
    c = _MANUAL['ctx']
    if reload:
        try:
            _rebuild()
        except Exception as e:
            print(f"[U3] ledger reload failed ({e}) — starting empty")
    from IPython.display import display, HTML
    p = _MANUAL['pos']
    _cl = _MANUAL.get('closed') or []
    def _kv(rows):
        return ''.join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows)
    _pos_txt = (f"{'LONG' if p['dir'] == 1 else 'SHORT'} spread since "
                f"{p['date']}, ${p['notional']:,.0f}, "
                f"{len(_MANUAL['marks'])} mark(s)" if p else 'flat')
    _book_txt = (f"{len(_MANUAL['days'])} day(s) "
                 f"{_MANUAL['days'][0]['date']} .. {_MANUAL['days'][-1]['date']}"
                 if _MANUAL['days'] else 'empty')
    html = (_CSS + "<table class='v31tbl'>"
        f"<caption>PAPER DESK READY — {c['instrument']} &nbsp; "
        f"{c['adr_ticker']} vs {c['ord_ticker']} &nbsp; "
        f"(1 ADR = {c['adr_ratio']:.0f} ord)</caption>"
        + _kv([
        ('History', f"to {c['hist_last_date']} ({len(c['hist_premium'])} closes, read-only)"),
        ('Your book', _book_txt),
        ('Position', _pos_txt),
        ('Closed', f"{len(_cl)} trade(s), paper P&amp;L "
                   f"${sum(t['net'] for t in _cl):+,.0f}" if _cl else '—'),
        ('ENTER when', f"|z| &gt; {c['thresh']:.2f} (N={c['n']}) AND "
                       f"|dev| ≥ {c['min_dev_bps']:.0f} bps (live rolling mean "
                       f"[X13]) AND the {c['gate_mode']} gate is open"),
        ('EXIT when', f"z crosses 0, or {c['time_stop']}cd time stop, or "
                      f"[X12] gamma: expected reversion &lt; carry"),
        ('Fair / cost', f"fair from {c['fair_mode']}; backtest round trip "
                        f"≈{c['rt_cost_bps']:.0f} bps"),
        ('Paper P&amp;L charges', f"{c['rt_fee_bps']:.0f} bps fees + carry "
                        f"{c['carry_long_bpd']:.1f}/{c['carry_short_bpd']:.1f} "
                        f"bps/day (long/short). [X9] spread &amp; impact "
                        f"EXCLUDED — your typed fills already crossed them; "
                        f"that is the only difference vs "
                        f"{c['rt_cost_bps']:.0f} bps"),
        ('Next', "form() — fill today's prints &nbsp;·&nbsp; help_manual()"),
        ('Ledger', c['ledger']),
        ]) + "</table>")
    display(HTML(html))
    return None
 
# ============================================================================
# [Y10] DIVIDEND AUTOMATION — answers "div carry % vs TW ex-div %" by making
# the desk fill both fields itself.
#
#   TW ex-div %  (form field 'div' -> div_cash_pct):  REAL CASH. On the day
#     the Taiwan ordinary goes ex, TAIFEX settles the dividend through the
#     SSF margin account: a LONG SSF is CREDITED the cash, a SHORT is
#     DEBITED. Enter it ONLY on the ex-date itself and ONLY if you are
#     holding through it; it books ±dir x notional x pct as P&L ([T3]).
#   Div carry %  (form field 'dcar' -> div_carry):    A SIGNAL CORRECTION,
#     never cash. Between the TW ex-date and the (later) ADR ex-date the
#     ordinary and the future have already dropped by the dividend while the
#     ADR still trades cum-div, so the RAW premium jumps by ~the whole
#     dividend ([U5], +738 bps on UMC vs a ~120 bps sigma). div_carry scales
#     the FAIR up by (1+d) on EVERY day inside that window so the desk does
#     not read the calendar as the trade of the year. Zero outside it.
#   (If the two ex-dates coincide — TSM has been +0 days — the carry window
#    is empty and only the cash field ever applies.)
# ============================================================================
def set_dividend(tw_ex, adr_ex, pct):
    """[Y10] e.g. set_dividend('2026-07-08', '2026-07-15', 6.8).
    add_day then auto-fills div_carry on tw_ex <= date < adr_ex, and reminds
    (and defaults) div_cash_pct on the ex-date itself when in a position.
    Call with pct=0 to clear."""
    if float(pct) == 0.0:
        _MANUAL.pop('dividend', None)
        print('[Y10] dividend window cleared')
        return
    _MANUAL['dividend'] = dict(tw_ex=str(tw_ex), adr_ex=str(adr_ex),
                               pct=float(pct))
    print(f"[Y10] dividend registered: TW ex {tw_ex} | ADR ex {adr_ex} | "
          f"{pct:.2f}% — add_day will apply div_carry inside the window "
          f"and the [T3] cash on the ex-date automatically")
 
def _auto_dividend(date, div_cash_pct, div_carry, in_pos):
    dv = _MANUAL.get('dividend')
    if not dv:
        return div_cash_pct, div_carry, []
    msgs = []
    d, twx, adx, pct = str(date), dv['tw_ex'], dv['adr_ex'], dv['pct'] / 100.0
    if div_carry == 0.0 and twx <= d < adx:
        div_carry = pct
        msgs.append(f"[Y10] div_carry auto-set to {dv['pct']:.2f}% "
                    f"(inside TW-ex {twx} .. ADR-ex {adx})")
    if div_cash_pct == 0.0 and d == twx and in_pos:
        div_cash_pct = pct
        msgs.append(f"[Y10] TW ex-date today and you are holding — [T3] "
                    f"margin-account cash {dv['pct']:.2f}% applied "
                    f"(pass div_cash_pct=0.0 explicitly... to override, "
                    f"call add_day directly)")
    return div_cash_pct, div_carry, msgs
 
# ============================================================================
# [Y9] add_day — FULL REPLACEMENT (guards + backtest-aligned gamma exit +
#                exec-point tagging + suggested sizing + P&L math)
# ============================================================================
def _fair_decomposition(c, ordinary, fut_1330, f_px, fx, div_carry):
    _k = 1.0 + float(div_carry or 0.0)
    if c['fair_mode'] == 'futures':
        return (f"fair = SSF {f_px:,.4g} x ratio {c['adr_ratio']:.0f} "
                f"/ FX {fx:.4f}"
                + (f" x (1+{div_carry:.4f})" if div_carry else '')
                + f" = {f_px * c['adr_ratio'] / fx * _k:,.4f}")
    return (f"fair = ord {ordinary:,.4g} x (SSF {f_px:,.4g} / 13:30 "
            f"{fut_1330:,.4g}) x ratio {c['adr_ratio']:.0f} / FX {fx:.4f}"
            + (f" x (1+{div_carry:.4f})" if div_carry else '')
            + f" = {ordinary * (f_px / fut_1330) * c['adr_ratio'] / fx * _k:,.4f}")
 
def add_day(date, ordinary, fut_1330, fx, adr_open=None, fut_open=None,
            adr_1945=None, fut_1945=None, adr_close=None, fut_close=None,
            fx_open=None, fx_1945=None, fx_close=None,
            div_cash_pct=0.0, div_carry=0.0, note='', save=True, quiet=False,
            force=False):
    """[Y9] v31.12 daily call. Same contract as v31.11 plus:
      force=True                bypass the [Y9a] input sanity guards
      fx_open/fx_1945/fx_close  [Y17] the USDTWD print AT each snapshot.
    [Y17] FX CONVENTION, so it matches the backtest exactly:
      * the SIGNAL (fair, premium, z) always uses the 13:30 TW-close fixing
        `fx` — the [D2][I1] convention every historical premium in the
        z-window was built with. Feeding a US-hours FX into the fair would
        shift today's premium off the scale of its own history.
      * EXECUTION (marks, EXIT-NOW, the enter()/exit_pos() hints and the fx
        stored on each ledger row) uses the snapshot FX when given — the
        rate you actually trade the hedge at. Omitted, it falls back to the
        anchor. The gap between the two is intraday FX noise, which the
        [H2]/[S1] dev floor already prices."""
    c = _MANUAL['ctx']
    if c is None:
        raise RuntimeError('run setup_manual() first')
    date = str(date)
    for _nm, _vv in (('ordinary', ordinary), ('fut_1330', fut_1330), ('fx', fx)):
        if _vv in (None, 0) or _vv != _vv:
            print(f"[Y9a] {_nm} is missing/zero — the anchors are required. "
                  f"Nothing scored.")
            return None
    if not (20.0 <= float(fx) <= 45.0) and not force:
        print(f"[Y9a] FX {fx} is outside 20–45 TWD — check the input "
              f"(force=True to override). Nothing scored.")
        return None
    if abs(fut_1330 / (ordinary * 1.0) - 1.0) > GUARD_ORD_TOL and not force:
        print(f"[Y9a] 13:30 SSF {fut_1330:,.4g} sits "
              f"{(fut_1330/ordinary-1)*100:+.1f}% off the ordinary "
              f"{ordinary:,.4g} — a same-stock SSF basis beyond "
              f"{GUARD_ORD_TOL*100:.0f}% is almost certainly a typo or a "
              f"wrong contract (force=True to override). Nothing scored.")
        return None
    div_cash_pct, div_carry, _dmsgs = _auto_dividend(
        date, div_cash_pct, div_carry, _MANUAL['pos'] is not None)   # [Y10]
    n, thr = c['n'], c['thresh']
    gate_ok, gate_txt, _gamma, _chgsd = _gate(n, date)
    _hl_led, _dr_led = _gate_levels(_gamma, gate_txt)    # [Y37g] for the ledger
    p = _MANUAL['pos']
    rows, _disp, _cmds, _buf = [], [], [], []
    _mtm_detail, _health = [], []          # [Y24][Y25]
    _HT = HTML_OUTPUT and _in_jupyter() and not quiet     # [Y18] card mode
    _W = 92                     # [Y39] wider: fair formulas fit now
    def _L(s=''):
        if quiet:
            return
        s = str(s)
        if _HT:
            _buf.append(s)
            return
        for _w in _wrap_box(s, _W - 4, indent=4):    # [Y39] wrap, never cut
            print('\u2502 ' + _w.ljust(_W - 4) + ' \u2502')
    def _R(l='\u251c', r='\u2524'):
        if not quiet and not _HT:
            print(l + '\u2500' * (_W - 2) + r)
    if not quiet and not _HT:
        print('\n\u250c' + '\u2500' * (_W - 2) + '\u2510')
        _L(f"{date}   {c['instrument']}" + (f"   \u2014 {note}" if note else ''))
        for _m in _dmsgs:
            _L(_m)
        _R()
        _L(f"ANCHORS    ordinary {ordinary:>10,.2f}   SSF 13:30 {fut_1330:>9,.2f}"
           f"   FX {fx:>7.4f}")
        _L(f"GATE       " + ('OPEN  \u2014 entries allowed' if gate_ok
                            else 'SHUT  \u2014 no new entry'))
        _L(f"           {gate_txt}")
        if p:
            _held0 = (pd.Timestamp(str(date)) - pd.Timestamp(p['date'])).days
            _R()
            _L(f"POSITION   {'LONG' if p['dir'] == 1 else 'SHORT'} spread   "
               f"${p['notional']:,.0f}   opened {p['date']}   "
               f"held {_held0}cd / {c['time_stop']}cd")
            _L(f"           entry ADR {p['entry_adr']:.4f}   SSF "
               f"{p['entry_fut']:.2f}   FX {p['entry_fx']:.4f}")
        _R()
    _exec_pt = c.get('exec_point', 'close')
    for key, label, a_px, f_px, _fx_s in (
            ('open', 'US open   1330/1430z', adr_open, fut_open, fx_open),
            ('1945', '15:45 ET  1945/2045z', adr_1945, fut_1945, fx_1945),
            ('close', 'US close  2000/2100z', adr_close, fut_close, fx_close)):
        if a_px in (None, 0) or f_px in (None, 0) or a_px != a_px or f_px != f_px:
            continue
        # [Y17] execution FX for THIS snapshot; signal FX stays the anchor
        fxe = (float(_fx_s)
               if (FX_MARK_MODE == 'snapshot' and _fx_s not in (None, 0)
                   and _fx_s == _fx_s)
               else float(fx))          # [Y29] default: the 13:30 fixing
        _fx_note = f"   exec FX {fxe:.4f}" if fxe != float(fx) else ""
        # ---------------- [Y9a] PER-SNAPSHOT SANITY GUARDS -----------------
        if not force:
            _bad = []
            if abs(f_px / fut_1330 - 1.0) > GUARD_FUT_TOL:
                _bad.append(f"SSF {f_px:,.4g} is "
                            f"{(f_px/fut_1330-1)*100:+.0f}% off the 13:30 "
                            f"anchor {fut_1330:,.4g} (tol "
                            f"{GUARD_FUT_TOL*100:.0f}%)")
            if not (20.0 <= fxe <= 45.0):
                _bad.append(f"exec FX {fxe} outside 20\u201345")
            fair0 = _fair(ordinary, fut_1330, f_px, fx, div_carry)
            prem0 = (a_px / fair0 - 1.0) * 1e4
            z0, _, _ = _zstats(prem0, n, date)
            if abs(prem0) > GUARD_PREM_MAX_BPS:
                _bad.append(f"|premium| {prem0:+,.0f} bps > "
                            f"{GUARD_PREM_MAX_BPS:,.0f}")
            if z0 == z0 and abs(z0) > GUARD_Z_MAX:
                _bad.append(f"|z| {z0:+.1f} > {GUARD_Z_MAX:.0f}")
            if _bad:
                _L(f"{label}")
                _L(f"   \u2716 NOT SCORED — implausible input:")
                for _b in _bad:
                    _L(f"     {_b}")
                _L(f"   {_fair_decomposition(c, ordinary, fut_1330, f_px, fx, div_carry)}")
                _L(f"   fix the print (decimal point? wrong field? wrong "
                   f"contract?) or pass force=True")
                _disp.append({'point': label, 'ADR': a_px, 'SSF': f_px,
                              'FX': fxe, 'fair': fair0, 'prem bps': prem0,
                              'dev bps': float('nan'), 'z': z0,
                              'action': _badge('NOT SCORED', 'bad') + ' '
                                        + _bad[0]})
                continue
        # -------------------------------------------------------------------
        fair = _fair(ordinary, fut_1330, f_px, fx, div_carry)
        prem = (a_px / fair - 1.0) * 1e4
        z, mu, sd = _zstats(prem, n, date)
        dev = prem - mu if mu == mu else float('nan')
        _tag = '' if key == _exec_pt else '   [indicative — grid fit on ' + _exec_pt.upper() + ' fills]'
        _act = ''
        if p is None:
            past = (z == z) and abs(z) > thr          # [Y9d] strict, like run_backtest
            dev_ok = (dev == dev) and abs(dev) >= c['min_dev_bps']
            can = past and dev_ok and gate_ok
            side = 'SHORT' if z > 0 else 'LONG'
            why = []
            if not past: why.append(f"|z| {abs(z):.2f} <= {thr:.2f}")
            if not dev_ok: why.append(f"|dev| {abs(dev):.0f} < {c['min_dev_bps']:.0f}")
            if not gate_ok: why.append(f'gate shut')
            _L(f"{label}{_tag}")
            _L(f"   ADR {a_px:>10.4f}   fair {fair:>10.4f}   premium "
               f"{prem:>+7.0f}bps{_fx_note}")
            if SHOW_PNL_MATH:
                _L(f"   {_fair_decomposition(c, ordinary, fut_1330, f_px, fx, div_carry)}")
            _L(f"   deviation {dev:>+6.0f}bps      z {z:>+6.2f}   "
               f"(band \u00b1{thr:.2f})")
            if can:
                # [Y9f] z-scaled suggested size, contract-snapped ([D3][E2])
                _cap = float(c.get('size_cap', globals().get('SIZE_CAP', 2.0)))
                _szm = (min(abs(z) / thr, _cap)
                        if globals().get('SIZING_MODE', 'z_scaled') == 'z_scaled'
                        else 1.0)
                _c_usd = c['contract_sh'] * f_px / fxe
                _ncon = max(1, int(round(c['notional'] * _szm / _c_usd)))
                _sugg_snap = _ncon * _c_usd
                _L(f"   \u25b6 ENTER {side} spread   "
                   f"({'sell ADR / long SSF' if side == 'SHORT' else 'buy ADR / short SSF'})"
                   + ('' if key == _exec_pt else '  [INDICATIVE]'))
                _L(f"     edge over cost {abs(dev) - c['rt_cost_bps']:+.0f}bps"
                   f"   \u2192 {abs(dev):.0f}bps deviation vs "
                   f"{c['rt_cost_bps']:.0f}bps round trip")
                _L(f"     gates passed: |z| {abs(z):.2f} > {thr:.2f} and "
                   f"|dev| {abs(dev):.0f} >= floor "
                   f"{c['min_dev_bps']:.0f}bps [S1]")
                _L(f"     size {_szm:.2f}x \u2192 ${_sugg_snap:,.0f} = "
                   f"{_ncon} SSF contracts")
                _cmd = (f"enter('{side}', adr=<fill>, fut=<fill>, "
                        f"fx={float(fxe):.4f}, "
                        f"date='{date}', notional={_sugg_snap:.0f})")
                _L(f"     {_cmd}")
                _cmds.append(_cmd + ('' if key == _exec_pt
                                     else '   # INDICATIVE'))
                _act = (_badge(f'ENTER {side}', 'ok')
                        + (' ' + _badge('indicative', 'warn')
                           if key != _exec_pt else '')
                        + f" {_szm:.2f}x = {_ncon} contracts")
            else:
                _L(f"   \u2014 no entry   ({'; '.join(why)})")
                _act = _badge('no entry', 'mut') + ' ' + '; '.join(why)
        else:
            m = _mtm(a_px, f_px, fxe,
                     div_cash_pct if key == _exec_pt else 0.0)   # [Y17] exec fx
            held = (pd.Timestamp(date) - pd.Timestamp(p['date'])).days
            xc = _trade_cost(p['dir'], p['notional'], held,
                             adr_notional=p.get('adr_notional'),
                             hedge_notional=p.get('hedge_notional'))
            trig = []
            if (p['dir'] == -1 and z <= 0) or (p['dir'] == 1 and z >= 0):
                trig.append('Z crossed 0')
            if held >= c['time_stop']:
                trig.append(f"time stop {c['time_stop']}cd")
            if c['hard_stop_bps'] > 0 and m['bps'] <= -c['hard_stop_bps']:
                trig.append(f"hard stop {c['hard_stop_bps']:.0f}bps")
            if ((c['pt_bps'] > 0 and m['bps'] >= c['pt_bps'])
                    or (c['pt_z'] > 0 and z == z and abs(z) <= c['pt_z'])):
                trig.append('profit target')
            # [Y9b][Y9c] gamma exit on the LEVEL sigma, hurdle x days-to-next
            _gx = ''
            if (_gamma == _gamma and _gamma < 0 and z == z and sd == sd
                    and sd > 0):
                _exp_bps = abs(max(_gamma, -1.0)) * abs(z) * sd
                _bpd = (c['carry_long_bpd'] if p['dir'] == 1
                        else c['carry_short_bpd'])
                _dtn = 3 if pd.Timestamp(date).weekday() == 4 else 1
                _hurdle = _bpd * _dtn
                if _exp_bps < _hurdle:
                    trig.append(f'gamma exit ({_exp_bps:.0f} < '
                                f'{_hurdle:.1f}bps carry)')
                else:
                    _gx = (f"   gamma {_gamma:+.3f}: expect {_exp_bps:.0f}"
                           f"bps/day vs carry {_hurdle:.1f}bps"
                           + (f" over {_dtn}cd" if _dtn > 1 else ""))
            _L(f"{label}{_tag}")
            _L(f"   ADR {a_px:>10.4f}   premium {prem:>+7.0f}bps   "
               f"z {z:>+6.2f}{_fx_note}")
            if SHOW_PNL_MATH:                      # [Y9h]
                _dirs = '+1' if p['dir'] == 1 else '-1'
                _L(f"   ADR leg = {_dirs} x {m['shares']:,.0f}sh x "
                   f"({a_px:.4f} - {p['entry_adr']:.4f}) = "
                   f"${m['adr_leg']:+,.0f}")
                _L(f"   SSF leg = -({_dirs}) x ${p['notional']:,.0f} x "
                   f"({f_px:.2f}/{p['entry_fut']:.2f} - 1) x "
                   f"({p['entry_fx']:.4f}/{fxe:.4f}) = ${m['fut_leg']:+,.0f}")
                if m['div_leg']:
                    _L(f"   TAIFEX div = -({_dirs}) x ${p['notional']:,.0f}"
                       f" x {div_cash_pct*100:.2f}% = ${m['div_leg']:+,.0f}")
            _L(f"   MARK   unrealised ${m['gross']:>+10,.0f}  "
               f"({m['bps']:+.0f}bps of ${p['notional']:,.0f})")
            _L(f"   EXIT NOW would net ${m['gross'] - xc:>+10,.0f}   "
               f"(after ${xc:,.0f} = {c['rt_fee_bps']:.0f}bps fees + "
               f"{held}cd carry)")
            if _gx:
                _L(_gx)
            if trig:
                _L("   \u25b6 EXIT SIGNAL   " + ", ".join(trig))
                _cmd = (f"exit_pos(adr={a_px:.4f}, fut={f_px:.2f}, "
                        f"fx={float(fxe):.4f}, "
                        f"date='{date}')")
                _L(f"     {_cmd}")
                _cmds.append(_cmd)
                _act = (_badge('EXIT', 'bad') + ' ' + ', '.join(trig)
                        + f" \u00b7 mark {m['bps']:+.0f}bps, net now "
                          f"${m['gross'] - xc:+,.0f}")
            else:
                _L("   \u2014 hold   (no exit trigger yet)")
                # [Y38] ADD suggestion — the [Y12] rule, desk-side: same
                # side, |z| extended ADD_STEP_Z beyond the entry z, dev
                # floor passed, and not already at MAX_ADDS_DESK legs.
                _ez = p.get('entry_z')
                _legs_now = p.get('n_legs', 1)
                if (_ez == _ez and z == z and _ez is not None
                        and np.sign(z) == np.sign(_ez)
                        and abs(z) >= abs(_ez) + ADD_STEP_Z
                        and (dev != dev or abs(dev) >= c['min_dev_bps'])
                        and _legs_now < 1 + MAX_ADDS_DESK):
                    _L(f"   [+] SPIKE EXTENDED  |z| {abs(z):.2f} vs entry "
                       f"{abs(_ez):.2f} — an ADD is what [Y12] backtests:")
                    _L(f"     add_to(adr={a_px:.4f}, fut={f_px:.2f}, "
                       f"fx={float(fxe):.4f}, date='{date}')")
                _act = (_badge('HOLD', 'mut')
                        + f" mark {m['bps']:+.0f}bps, exit-now net "
                          f"${m['gross'] - xc:+,.0f}")
            if key == _exec_pt or not _mtm_detail:     # [Y25] full arithmetic
                _mtm_detail.clear()
                _bpd25 = (c['carry_long_bpd'] if p['dir'] == 1
                          else c['carry_short_bpd'])
                _fee25 = c['rt_fee_bps'] / 1e4 * p['notional']
                _car25 = xc - _fee25
                _mtm_detail.extend([
                    ('shares held',
                     f"${p['notional']:,.0f} / entry ADR {p['entry_adr']:.4f}",
                     f"{m['shares']:,.1f} ADR shares"),
                    ('SSF contracts',
                     f"${p['notional']:,.0f} / ({c['contract_sh']:.0f} x "
                     f"{p['entry_fut']:.2f} / {p['entry_fx']:.4f})",
                     f"{p['notional']/(c['contract_sh']*p['entry_fut']/p['entry_fx']):,.2f}"),
                    ('ADR leg',
                     f"{'+1' if p['dir'] == 1 else '-1'} x {m['shares']:,.1f}sh"
                     f" x ({a_px:.4f} - {p['entry_adr']:.4f})",
                     f"${m['adr_leg']:+,.2f}"),
                    ('SSF leg',
                     f"{'-1' if p['dir'] == 1 else '+1'} x ${p['notional']:,.0f}"
                     f" x ({f_px:.2f}/{p['entry_fut']:.2f} - 1) x "
                     f"({p['entry_fx']:.4f}/{fxe:.4f})",
                     f"${m['fut_leg']:+,.2f}"),
                    ('TAIFEX dividend',
                     (f"{'-1' if p['dir'] == 1 else '+1'} x "
                      f"${p['notional']:,.0f} x {div_cash_pct*100:.2f}%"
                      if m['div_leg'] else 'no ex-date today'),
                     f"${m['div_leg']:+,.2f}"),
                    ('GROSS mark',
                     "ADR leg + SSF leg" + (" + dividend" if m['div_leg']
                                            else ""),
                     f"${m['gross']:+,.2f}   ({m['bps']:+.0f} bps)"),
                    ('fees if closed now',
                     f"{c['rt_fee_bps']:.0f}bps x ${p['notional']:,.0f} "
                     f"(round trip; spread/impact excluded [X9])",
                     f"-${_fee25:,.2f}"),
                    ('carry accrued',
                     f"{_bpd25:.2f}bps/cd x {held}cd x ${p['notional']:,.0f} "
                     + ("(funding + margin, long ADR)" if p['dir'] == 1
                        else "(borrow - rebate + margin, short ADR)"),
                     f"-${_car25:,.2f}"),
                    ('NET if closed now',
                     f"${m['gross']:+,.2f} - ${_fee25:,.2f} - ${_car25:,.2f}",
                     f"${m['gross'] - xc:+,.2f}   "
                     f"({(m['gross'] - xc) / p['notional'] * 1e4:+.0f} bps)")])
                _hl_lvl, _hl_head, _hl_lines = _position_health(
                    z, sd, _gamma, gate_ok, date, m['bps'])
                _health.clear()
                if _hl_lvl:
                    _health.extend([_hl_lvl, _hl_head, _hl_lines])
                    _L("")
                    _L(f"   POSITION HEALTH [Y24]   {_hl_head}")
                    for _hx in _hl_lines:
                        _L(f"     {_hx}")
        _disp.append({'point': label + ('' if key == _exec_pt else ' *'),
                      'ADR': a_px, 'SSF': f_px, 'FX': fxe, 'fair': fair,
                      'prem bps': prem, 'dev bps': dev, 'z': z,
                      'action': _act})
        rows.append(dict(instrument=c['instrument'], date=date, point=key,
                         side='', notional='',
                         ordinary=ordinary, fut_1330=fut_1330, fx=fxe,
                         adr=a_px,
                         fut=f_px, fair=round(fair, 4), premium_bps=round(prem, 2),
                         dev_bps=(round(dev, 1) if dev == dev else ''),
                         z=(round(z, 3) if z == z else ''),
                         gamma=(round(_gamma, 3) if _gamma == _gamma else ''),
                         hl=(round(_hl_led, 1) if _hl_led == _hl_led else ''),
                         drift=(round(_dr_led, 2) if _dr_led == _dr_led else ''),
                         n=n, threshold=thr, gate=('open' if gate_ok else 'shut'),
                         div_carry=div_carry, in_position=bool(p), net='',
                         note=note))
    # -------------------- [Y18] the DAY CARD (Jupyter) ----------------------
    if _HT:
        from IPython.display import display, HTML
        _gb = (_badge('GATE OPEN', 'ok') if gate_ok
               else _badge('GATE SHUT', 'bad'))
        _pt = ('flat' if p is None else
               f"{'LONG' if p['dir'] == 1 else 'SHORT'} "
               f"${p['notional']:,.0f} since {p['date']}")
        _hd = (f"<table class='v31tbl'><caption>{date} &nbsp; "
               f"{c['instrument']} {_gb}"
               + (f" &nbsp;\u2014 {note}" if note else '') + "</caption>"
               f"<tr><th>ordinary</th><th>SSF 13:30</th><th>FX fixing</th>"
               f"<th>position</th><th>gate detail</th></tr>"
               f"<tr><td>{ordinary:,.2f}</td><td>{fut_1330:,.2f}</td>"
               f"<td>{fx:.4f}</td><td>{_pt}</td>"
               f"<td style='white-space:normal;text-align:left'>{gate_txt}"
               + ("<br>".join([''] + _dmsgs) if _dmsgs else '')
               + "</td></tr></table>")
        display(HTML(_CSS + _hd))
        if _disp:
            show_html_table(
                _pd.DataFrame(_disp).set_index('point'),
                fmt={'ADR': '{:,.4f}', 'SSF': '{:,.2f}', 'FX': '{:.4f}',
                     'fair': '{:,.4f}', 'prem bps': '{:+,.0f}',
                     'dev bps': '{:+,.0f}', 'z': '{:+.2f}'},
                note=('* = away from the ' + _exec_pt.upper() + ' execution '
                      'point the grid was fit on — treat as indicative. '
                      'Signal FX = 13:30 fixing [D2]; FX column = execution '
                      'rate for that snapshot [Y17].'))
        if _mtm_detail:                       # [Y25] full P&L arithmetic
            show_html_table(
                _pd.DataFrame(_mtm_detail,
                              columns=['component', 'how it is computed',
                                       'value']).set_index('component'),
                title='MARK TO MARKET \u2014 every line substituted',
                fmt='{}',
                note='Two-leg convention, identical to run_backtest: the ADR '
                     'leg prices in SHARES, the SSF leg as a RETURN on the '
                     'same notional, converted at entry FX / current FX. Fees '
                     'exclude spread and impact because your typed fills '
                     'already crossed them [X9].')
        if _health:
            _lvl, _head, _lines = _health
            _hrows = []
            for _x in _lines:
                _k, _, _v = _x.partition('  ')
                _hrows.append((_k.strip() if _v else '', (_v or _k).strip()))
            display(HTML(
                _CSS + "<table class='v31tbl'><caption>POSITION HEALTH "
                + _badge(_head, _lvl) + "</caption><tr><th>check</th>"
                "<th style='text-align:left'>reading</th></tr>"
                + "".join(f"<tr><td>{_k}</td><td style='text-align:left;"
                          f"white-space:normal'>{_v}</td></tr>"
                          for _k, _v in _hrows) + "</table>"))
        if _cmds:
            display(HTML(_CSS + "<div class='v31pre'>"
                         + "\n".join(_cmds) + "</div>"))
        if _buf:
            display(HTML(_CSS + "<details><summary style=\"cursor:pointer;"
                         "font:11.5px 'Segoe UI';color:#5f6b76\">full detail "
                         "(formulas, hurdles, decomposition)</summary>"
                         "<div class='v31pre'>"
                         + "\n".join(_x.replace('<', '&lt;') for _x in _buf)
                         + "</div></details>"))
    if save and rows:
        led = _read_ledger()
        keys = {(r['date'], r['point']) for r in rows}
        led = led[~led.apply(
            lambda r: (str(r['instrument']) == c['instrument']
                       and (str(r['date']), str(r['point'])) in keys), axis=1)]
        _write_ledger(pd.concat([led, pd.DataFrame(rows)], ignore_index=True))
        _rebuild()
        if not quiet:
            _R('\u2514', '\u2518')
            print(f"  saved {len(rows)} row(s); "
                  f"{len(_MANUAL['days'])} manual day(s) in context — "
                  f"re-running add_day for the same date OVERWRITES it")
    elif not quiet and not rows:
        _R('\u2514', '\u2518')
        print("  nothing scored (no valid snapshot pairs) — nothing saved")
    return None
 
# ============================================================================
# [Y11] exit_pos — prints every substituted formula
# ============================================================================
def exit_pos(adr, fut, fx, date, div_cash_pct=0.0, note=''):
    """[Y11] Record the exit fill and print the FULL arithmetic so every
    paper P&L can be verified line by line."""
    c, p = _MANUAL['ctx'], _MANUAL['pos']
    if p is None:
        print('[U3] no open position'); return None
    div_cash_pct, _dc, _dmsgs = _auto_dividend(date, div_cash_pct, 0.0, True)
    for _m0 in _dmsgs:
        print(_m0)
    m = _mtm(float(adr), float(fut), float(fx), div_cash_pct)
    held = (pd.Timestamp(date) - pd.Timestamp(p['date'])).days
    cost = _trade_cost(p['dir'], p['notional'], held,
                       adr_notional=p.get('adr_notional'),
                       hedge_notional=p.get('hedge_notional'))
    _fee = (_fee_usd(p['adr_notional'], p['hedge_notional'])
            if p.get('adr_notional') and p.get('hedge_notional')
            else c['rt_fee_bps'] / 1e4 * p['notional'])   # [Y32]
    _bpd = c['carry_long_bpd'] if p['dir'] == 1 else c['carry_short_bpd']
    net = m['gross'] - cost
    row = dict(instrument=c['instrument'], date=str(date), point='EXIT',
               side=('LONG' if p['dir'] == 1 else 'SHORT'),
               notional=p['notional'],
               ordinary='', fut_1330='', fx=float(fx), adr=float(adr),
               fut=float(fut), fair='', premium_bps='',
               dev_bps='', z='', n=c['n'], threshold=c['thresh'], gate='',
               div_carry='', in_position=False, net=round(net, 2),
               note=f"held {held}cd {note}".strip())
    led = _read_ledger()
    led = led[~((led['instrument'] == c['instrument'])
                & (led['point'] == 'EXIT')
                & (led['date'].astype(str) == str(date)))]
    _write_ledger(pd.concat([led, pd.DataFrame([row])], ignore_index=True))
    _d = '+1' if p['dir'] == 1 else '-1'
    _side = 'LONG' if p['dir'] == 1 else 'SHORT'
    _bps_net = net / p['notional'] * 1e4
    banner(f"CLOSED — {_side} spread, {held}cd",
           sub=f"{p['date']} → {date}   ${p['notional']:,.0f}   "
               f"NET ${net:+,.0f} ({_bps_net:+.0f} bps)")
    # ---- the P&L waterfall: every line carries the arithmetic that made
    # it, so any number can be re-derived by hand from the row itself.
    # [Y32] every line is the INTEGER-unit arithmetic a real ticket has:
    # whole shares on the ADR leg, whole contracts x contract_sh x the TWD
    # move on the futures leg. Legacy positions (no units) show the old
    # notional-ratio formulas instead.
    if m.get('contracts'):
        _rows = [
            ('units', f"{m['shares']:,d} sh + {m['contracts']} contracts",
             f"whole shares / whole {HEDGE_LBL} contracts — real fills "
             f"cannot be fractional"),
            (f'{ADR_LBL} leg', f"${m['adr_leg']:+,.2f}",
             f"dir({_d}) x {m['shares']:,d} sh x ({float(adr):.4f} - "
             f"{p['entry_adr']:.4f})"),
            (f'{HEDGE_LBL} leg', f"${m['fut_leg']:+,.2f}",
             f"-dir({_d}) x {m['contracts']} x {c['contract_sh']:,.0f} sh x "
             f"({float(fut):.2f} - {p['entry_fut']:.2f}) {LOCAL_CCY} "
             f"/ FX {float(fx):.4f}"),
        ]
        if m['div_leg']:
            _rows.append((f'{EXCH_LBL} div cash [T3]', f"${m['div_leg']:+,.2f}",
                          f"-dir({_d}) x ${m['hedge_notional']:,.0f} "
                          f"(hedge leg) x {div_cash_pct*100:.2f}%"))
    else:
        _rows = [
            ('shares', f"{m['shares']:,.1f}",
             f"${p['notional']:,.0f} / entry ADR {p['entry_adr']:.4f} "
             f"(LEGACY row — no stored units)"),
            (f'{ADR_LBL} leg', f"${m['adr_leg']:+,.2f}",
             f"dir({_d}) x {m['shares']:,.1f}sh x ({float(adr):.4f} - "
             f"{p['entry_adr']:.4f})"),
            (f'{HEDGE_LBL} leg', f"${m['fut_leg']:+,.2f}",
             f"-dir({_d}) x ${p['notional']:,.0f} x ({float(fut):.2f}/"
             f"{p['entry_fut']:.2f} - 1) x FX {p['entry_fx']:.4f}/{float(fx):.4f}"),
        ]
        if m['div_leg']:
            _rows.append((f'{EXCH_LBL} div cash [T3]', f"${m['div_leg']:+,.2f}",
                          f"-dir({_d}) x ${p['notional']:,.0f} x "
                          f"{div_cash_pct*100:.2f}%"))
    _rows += [
        ('GROSS', f"${m['gross']:+,.2f}",
         f"the legs above, summed  ({m['bps']:+.0f} bps)"),
        ('less fees', f"-${_fee:,.2f}",
         (f"ADR {ADR_FEE_IN_BPS}+{ADR_FEE_OUT_BPS} bps on "
          f"${p['adr_notional']:,.0f} + {HEDGE_LBL}+FX on "
          f"${p['hedge_notional']:,.0f}"
          if p.get('adr_notional') else
          f"{c['rt_fee_bps']:.0f} bps x ${p['notional']:,.0f}")),
        ('less carry', f"-${cost - _fee:,.2f}",
         f"{_bpd:.2f} bps/cd x {held}cd x ${p['notional']:,.0f} — "
         + ('funding + margin (you are LONG the ADR)' if p['dir'] == 1
            else 'borrow - rebate + margin (you are SHORT the ADR)')),
        ('NET', f"${net:+,.2f}",
         f"{_bps_net:+.0f} bps of the ${p['notional']:,.0f} clip"),
    ]
    kv_table('P&L — HOW THIS NUMBER WAS BUILT', _rows, col='amount',
             note='Each line shows the substituted formula that produced '
                  'it, so the whole trade can be re-derived by hand.')
    _note_lines = [
        f"EXCLUDES bid/ask and impact — the prices you typed are your own",
        f"fills and already crossed them. The backtest's full round trip is",
        f"{c['rt_cost_bps']:.0f} bps; if you typed MID prices this P&L is too",
        f"generous by roughly the spread.",
    ]
    if FX_EXEC_MODE == 'spot_next_open':
        _note_lines += [
            "",
            f"[Y21] FX {float(fx):.4f} is PROVISIONAL — the hedge deals at",
            f"tomorrow's {LOCAL_LBL} open. Tomorrow:",
            f"    fx_fill('{date}', <{FX_LBL} 09:00>)",
        ]
    note_block('WHAT THIS P&L DOES AND DOES NOT CHARGE', _note_lines)
    if _MANUAL['marks']:
        b = [x['bps'] for x in _MANUAL['marks']]
        _gave = max(b) - _bps_net
        say(f"Path: best mark {max(b):+.0f} bps | worst {min(b):+.0f} bps | "
            f"banked {_bps_net:+.0f} bps",
            'warn' if _gave > 50 else 'ok',
            f"gave back {_gave:.0f} bps from the peak" if _gave > 0 else '')
    _rebuild()
    return net
 
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
    fut_arr = df['Fut_2130'].values
    hedge_arr = df['Hedge Idx'].values
    adr_close_arr = df['TSM US (Close)'].values
    fx_arr = (df['TWD (Last)'].values if 'TWD (Last)' in df.columns
              else _np.full(len(df), 32.4))
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
    beta_arr = df['beta'].values
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
        if MAX_BOOK_PARTICIPATION > 0:
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
            _cap = MAX_BOOK_PARTICIPATION * _supply * _c0
            if _cap > 0:
                want_notional = min(want_notional, _cap)
        _c_usd = FUT_CONTRACT_SHARES * fut_arr[t] / fx_arr[t]
        if ALIGN_TO_CONTRACTS:
            _nc = max(1, int(round(want_notional / _c_usd)))
            return _nc * _c_usd
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
        _bt = beta_arr[t] if not _np.isnan(beta_arr[t]) else 1.0
        exec_cost = compute_exec_cost(
            lot['notional'], False, _ka, _kf, _bt,
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
                     and not preex_arr[t] and gap_next[t] <= MAX_ENTRY_GAP_DAYS)
 
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
                if FUT_DIV_CASH:
                    lot['fut_div_cash'] += (-lot['dir'] * lot['beta']
                                            * lot['notional'] * div_hedge_arr[t]
                                            * fx_arr[lot['day']] / fx_arr[t])
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
            dcar += tot_nt * (margin_ann_bps() / 1e4) / 360
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
# [Y13] scrub_ledger — the guards stop the NEXT bad print, not the last one
# ============================================================================
# A fat-fingered row does not only mis-score its own day: once it is in the
# ledger it enters hist_premium, so it drags the rolling mean and inflates
# the sigma for every day in the next N-row window. The 2026-07-28 US-open
# row implied an SSF of 234,503 against a 13:30 anchor near 2,345 — if rows
# like that were ever SAVED, the desk's mu and sd are contaminated and every
# z printed since is wrong. This lists them and, with fix=True, removes them.
def scrub_ledger(max_abs_prem_bps=None, fix=False):
    c = _MANUAL['ctx']
    if c is None:
        raise RuntimeError('run setup_manual() first')
    lim = float(max_abs_prem_bps if max_abs_prem_bps is not None
                else GUARD_PREM_MAX_BPS)
    led = _read_ledger()
    _p = _pd.to_numeric(led['premium_bps'], errors='coerce')
    bad = led[(led['instrument'] == c['instrument']) & _p.abs().gt(lim)].copy()
    if not len(bad):
        print(f"[Y13] ledger clean — no row on {c['instrument']} with "
              f"|premium| > {lim:,.0f} bps")
        return bad
    bad['premium_bps'] = _pd.to_numeric(bad['premium_bps'], errors='coerce')
    bad['implied_SSF_input'] = (bad['adr'].astype(float)
                                / (1.0 + bad['premium_bps'] / 1e4)
                                * bad['fx'].astype(float) / c['adr_ratio'])
    show_html_table(
        bad[['date', 'point', 'adr', 'fut', 'fx', 'premium_bps',
             'implied_SSF_input']].set_index('date'),
        title=f"[Y13] {len(bad)} IMPLAUSIBLE LEDGER ROW(S) — |premium| > "
              f"{lim:,.0f} bps",
        fmt={'adr': '{:,.4f}', 'fut': '{:,.4f}', 'fx': '{:.4f}',
             'premium_bps': '{:+,.0f}', 'implied_SSF_input': '{:,.2f}'},
        note="implied_SSF_input is what the fair price says was typed. If it "
             "is ~100x or ~0.01x the 13:30 anchor it is a decimal point. "
             "These rows also poisoned mu and sd for the N rows after them — "
             "re-run with fix=True to drop them, then check the z printed on "
             "those days again.")
    if fix:
        keep = led.drop(bad.index)
        _write_ledger(keep)
        _rebuild()
        print(f"[Y13] removed {len(bad)} row(s); ledger rebuilt. Re-score the "
              f"affected dates with add_day(...) using the correct prints.")
    else:
        print("[Y13] nothing changed — call scrub_ledger(fix=True) to remove "
              "them.")
    return bad
 
# ============================================================================
# [Y24] POSITION HEALTH — the gate is an ENTRY gate, so nothing watches a
#        trade after it is on. This does.
# ============================================================================
# ADF_EXIT_POLICY='entry_only': once you are in, the regime gate is IGNORED
# by design, and the only exits are z-cross-0 / time stop / hard stop /
# gamma. So a trade whose REGIME dies mid-hold — the premium re-rating
# instead of oscillating, the half-life blowing out, the deviation widening
# while carry burns — has nothing watching it until the hard stop, which is
# far away and blunt. That is the gap you felt.
#
# THIS IS ADVISORY. It prints hints; it does NOT add an exit rule, because
# an exit rule that was never in the grid search is an UNTESTED strategy —
# its win rate, its Sharpe and its drawdown are unknown. If a hint keeps
# proving right, the honest path is to add it to run_backtest, re-run the
# grid, and see what it does to the numbers before trusting it live.
#
# The five things it watches, all measured against the trade's OWN entry:
#   1. GATE      open at entry -> shut now = the regime that justified the
#                trade has gone. Biggest single warning.
#   2. HALF-LIFE at entry vs now. Reversion getting slower means the same
#                edge now takes more days of carry to collect.
#   3. DRIFT     the rolling mean itself moving AWAY from your entry side:
#                a re-rating, i.e. the premium finding a new level rather
#                than returning to the old one. This is how a mean-reversion
#                trade turns into a trend loss.
#   4. Z PATH    |z| now vs |z| at entry. Extension is normal early and is
#                what the [Y12] add logic is for — but extension PLUS a
#                dying gate is the bad combination.
#   5. CARRY MATH the honest question: what is left to collect vs what the
#                remaining hold will cost. expected reversion = |gamma| x
#                |z| x sigma (bps/day) against carry bps/day, and the total
#                carry still to run to the time stop.
POS_HEALTH_ON = True
 
def _position_health(z, sd, gamma, gate_ok, date, mark_bps=None):
    """[Y24] Returns (level, headline, [lines]) where level is
    'ok' | 'warn' | 'bad'. Pure diagnosis — no side effects."""
    c, p = _MANUAL['ctx'], _MANUAL['pos']
    if p is None or not POS_HEALTH_ON:
        return None, '', []
    L, flags, score = [], [], 0
    held = (pd.Timestamp(str(date)) - pd.Timestamp(p['date'])).days
    left = max(c['time_stop'] - held, 0)
    _bpd = c['carry_long_bpd'] if p['dir'] == 1 else c['carry_short_bpd']
    # 1. gate
    _g0 = p.get('entry_gate')
    if _g0 is True and not gate_ok:
        score += 2
        flags.append('gate CLOSED since entry')
        L.append(f"gate      OPEN at entry \u2192 SHUT now. The regime that "
                 f"justified this trade is gone; the backtest would not "
                 f"re-enter here (it just does not force an exit either).")
    elif gate_ok:
        L.append(f"gate      open (unchanged since entry)")
    else:
        L.append(f"gate      shut (it was already shut at entry)")
    # 2. half-life
    _hl = (np.log(0.5) / np.log(1.0 + max(gamma, -0.999))
           if (gamma == gamma and gamma < 0) else float('nan'))
    _hl0 = p.get('entry_hl')
    if _hl == _hl:
        if _hl0 == _hl0 and _hl0 and _hl > _hl0 * 1.5:
            score += 1
            flags.append(f'half-life {_hl0:.1f}\u2192{_hl:.1f}d')
            L.append(f"half-life {_hl0:.1f}d at entry \u2192 {_hl:.1f}d now. "
                     f"Reversion is {_hl/_hl0:.1f}x slower, so the same edge "
                     f"now costs {(_hl-_hl0)*_bpd:.0f}bps more carry to "
                     f"collect.")
        else:
            L.append(f"half-life {_hl:.1f}d"
                     + (f" (entry {_hl0:.1f}d)" if _hl0 == _hl0 else ""))
    else:
        score += 1
        flags.append('no mean reversion in the window')
        L.append(f"half-life gamma {gamma:+.3f} \u2265 0 — the window shows "
                 f"NO mean reversion at all right now.")
    # 3. drift of the mean itself
    _mu0 = p.get('entry_mu')
    _s = _series_before(str(date))
    _mu = float(np.mean(_s[-c['n']:])) if len(_s) >= 3 else float('nan')
    if _mu == _mu and _mu0 == _mu0 and sd == sd and sd > 0:
        _dmu = _mu - _mu0
        _away = (_dmu > 0) if p['dir'] == -1 else (_dmu < 0)
        if abs(_dmu) > 0.75 * sd and _away:
            score += 2
            flags.append(f'mean re-rating {_dmu:+.0f}bps against you')
            L.append(f"drift     the rolling mean moved {_dmu:+.0f}bps "
                     f"({abs(_dmu)/sd:.1f}\u03c3) AWAY from your side since "
                     f"entry. That is a RE-RATING, not an oscillation: the "
                     f"level you are short/long of is finding a new home, so "
                     f"z can fall to 0 without the premium ever coming back "
                     f"to where you sold it.")
        else:
            L.append(f"drift     rolling mean {_dmu:+.0f}bps since entry "
                     f"({abs(_dmu)/sd:.1f}\u03c3) — no re-rating")
    # 4. z path
    _z0 = p.get('entry_z')
    if z == z and _z0 == _z0:
        if abs(z) > abs(_z0) + 0.5:
            flags.append(f'z extended {_z0:+.2f}\u2192{z:+.2f}')
            score += 1
            L.append(f"z path    {_z0:+.2f} at entry \u2192 {z:+.2f} now: the "
                     f"dislocation WIDENED. On its own this is the [Y12] "
                     f"add-on case; with a dying gate it is the loss case.")
        else:
            L.append(f"z path    {_z0:+.2f} \u2192 {z:+.2f} "
                     f"({'converging' if abs(z) < abs(_z0) else 'flat'})")
    # 5. carry vs what is left to collect
    if z == z and sd == sd and sd > 0 and gamma == gamma and gamma < 0:
        _exp = abs(max(gamma, -1.0)) * abs(z) * sd
        _tot = abs(z) * sd
        _carry_left = _bpd * left
        L.append(f"carry     expect {_exp:.0f}bps/day of reversion vs "
                 f"{_bpd:.1f}bps/day carry; {_tot:.0f}bps of dislocation "
                 f"left to collect vs {_carry_left:.0f}bps of carry still to "
                 f"run to the {c['time_stop']}cd stop ({left}cd)")
        if _tot < _carry_left:
            score += 2
            flags.append('carry to the stop exceeds the edge left')
            L.append(f"          \u2192 the carry still to run EXCEEDS the "
                     f"whole dislocation left. Holding to the time stop is "
                     f"negative EV even if z goes to 0 perfectly.")
    # 6. drawdown context
    if mark_bps is not None and c['hard_stop_bps'] > 0:
        _room = c['hard_stop_bps'] + mark_bps
        L.append(f"stop      mark {mark_bps:+.0f}bps, hard stop "
                 f"{-c['hard_stop_bps']:.0f}bps \u2192 {_room:.0f}bps of room")
        if mark_bps < -0.6 * c['hard_stop_bps']:
            score += 1
            flags.append('inside 40% of the hard stop')
    _mk = [m['bps'] for m in _MANUAL['marks']] if _MANUAL['marks'] else []
    if _mk and mark_bps is not None:
        L.append(f"path      best {max(_mk):+.0f}bps / worst {min(_mk):+.0f}"
                 f"bps so far"
                 + (f", giving back {max(_mk)-mark_bps:.0f}bps from the peak"
                    if max(_mk) > mark_bps else ""))
    lvl = 'bad' if score >= 4 else ('warn' if score >= 2 else 'ok')
    head = ({'ok': 'HEALTHY', 'warn': 'WATCH', 'bad': 'DETERIORATING'}[lvl]
            + (' \u2014 ' + '; '.join(flags[:3]) if flags else
               ' \u2014 regime unchanged since entry'))
    L.append("advisory only — not a backtested exit rule [Y24]")
    return lvl, head, L
 
# ============================================================================
# [Y21] NEXT-OPEN FX FILL — because the hedge FX does not exist yet
# ============================================================================
# FX_EXEC_MODE='spot_next_open': the TWD spot market is CLOSED during US
# hours, so the FX leg of a fill you make at the US close actually deals at
# the NEXT Taipei morning's USDTWD open (~09:00 TW). That print does not
# exist at the moment you record the fill. The workflow is therefore:
#   1. record enter()/exit_pos() tonight with the best FX you have (the
#      13:30 fixing, or your live indication) — it is PROVISIONAL;
#   2. tomorrow morning, one call:  fx_fill('2026-07-28', 32.31)
#      replaces the provisional FX on that date's ENTRY/EXIT row(s) with the
#      actual open, adjusts any closed-trade P&L by the exact SSF-leg delta,
#      and rebuilds the desk state.
# The SIGNAL never touches any of this — it always uses the 13:30 TW-close
# fixing [D2], the convention every premium in the z-window was built with.
def fx_fill(date, fx, point=None):
    """[Y21] Amend the execution FX on `date`'s ENTRY and/or EXIT ledger
    row(s) to the realised USDTWD next-open print. point='ENTRY'/'EXIT'
    restricts it; default amends whichever exist on that date."""
    c = _MANUAL['ctx']
    if c is None:
        raise RuntimeError('run setup_manual() first')
    fx = float(fx)
    if not (20.0 <= fx <= 45.0):
        print(f"[Y21] FX {fx} outside 20–45 — not applied"); return
    led = _read_ledger()
    _pts = [point] if point else ['ENTRY', 'EXIT']
    _m = ((led['instrument'] == c['instrument'])
          & (led['date'].astype(str) == str(date))
          & (led['point'].isin(_pts)))
    if not _m.any():
        print(f"[Y21] no ENTRY/EXIT row on {date} — nothing to amend")
        return
    for _ix in led.index[_m]:
        _r = led.loc[_ix]
        _old = float(_r['fx'])
        led.loc[_ix, 'fx'] = fx
        print(f"[Y21] {_r['point']} {date}: FX {_old:.4f} -> {fx:.4f}")
        if _r['point'] == 'EXIT' and str(_r['net']) not in ('', 'nan'):
            # exact SSF-leg delta: only the conversion of the futures leg
            # depends on the exit FX
            _ent = led[(led['instrument'] == c['instrument'])
                       & (led['point'] == 'ENTRY')
                       & (led['date'].astype(str) < str(date))]
            if len(_ent):
                _e = _ent.sort_values('date').iloc[-1]
                _dir = 1 if str(_e['side']).upper() == 'LONG' else -1
                _nt = float(_e['notional'])
                _fr = float(_r['fut']) / float(_e['fut'])
                _dlt = (-_dir * _nt * (_fr - 1.0) * float(_e['fx'])
                        * (1.0 / fx - 1.0 / _old))
                led.loc[_ix, 'net'] = round(float(_r['net']) + _dlt, 2)
                print(f"       SSF-leg P&L delta {_dlt:+,.2f} "
                      f"-> net ${float(led.loc[_ix, 'net']):+,.2f}")
    _write_ledger(led)
    _rebuild()
    print(f"[Y21] ledger rebuilt — status() to see the updated position")
 
_enter_v31_11 = enter
def enter(side, adr, fut, fx, date, notional=None, note=''):
    """[Y21] same as v31.11 enter(), plus the next-open FX reminder."""
    _r = _enter_v31_11(side, adr, fut, fx, date, notional=notional, note=note)
    if FX_EXEC_MODE == 'spot_next_open':
        say(f"[Y21] FX {float(fx):,.4f} is PROVISIONAL — the hedge deals at "
            f"TOMORROW'S {LOCAL_LBL} open. Then: "
            f"fx_fill('{date}', <{FX_LBL} 09:00>)", 'warn')
    return _r
 
# ============================================================================
# [Y38] add_to — SCALING INTO A SPIKE THAT KEEPS SPIKING.
# ----------------------------------------------------------------------------
# The BACKTEST has had this for a while (run_backtest_lots [Y12]); the desk
# never did — an entry was one clip, take it or leave it. This adds the
# desk-side version: while a position is open, add_to() books another leg
# at today's prices. The ledger stores each leg as its own ENTRY row
# (note='ADD'); _rebuild blends them into ONE position with share-weighted
# average entry prices — exact for P&L, see [Y38] in _rebuild. The daily
# card suggests an add when the signal EXTENDS (same side, |z| at least
# ADD_STEP_Z beyond the entry z) — the same rule [Y12] backtests, so test
# it there before trusting it here.
# ============================================================================
ADD_STEP_Z = 1.0        # suggest an add when |z| >= |entry z| + this
MAX_ADDS_DESK = 2       # the card stops suggesting beyond this many adds
def add_to(adr, fut, fx, date, notional=None, note=''):
    """[Y38] Add a leg to the OPEN position at today's fills. Same side,
    floor-rounded integer units [Y32b], written as its own ENTRY row."""
    c, p = _MANUAL['ctx'], _MANUAL['pos']
    if c is None:
        say('run setup_manual() first', 'bad'); return None
    if p is None:
        say('no open position — use enter(...) for the first leg', 'bad')
        return None
    _nt_req = float(notional or c['notional'])
    _u = _units(_nt_req, float(adr), float(fut), float(fx))
    _side = 'LONG' if p['dir'] == 1 else 'SHORT'
    row = dict(instrument=c['instrument'], date=str(date), point='ENTRY',
               side=_side, notional=_u['adr_notional'],
               shares=int(_u['shares']), contracts=int(_u['contracts']),
               ordinary='', fut_1330='', fx=float(fx), adr=float(adr),
               fut=float(fut), fair='', premium_bps='', dev_bps='', z='',
               gamma='', hl='', drift='',
               n=c['n'], threshold=c['thresh'], gate='', div_carry='',
               in_position=True, net='',
               note=('ADD ' + str(note)).strip())
    led = _read_ledger()
    led = led[~((led['point'] == 'ENTRY')
                & (led['date'].astype(str) == str(date))
                & (led['note'].astype(str).str.startswith('ADD')))]
    _write_ledger(pd.concat([led, pd.DataFrame([row])], ignore_index=True))
    _rebuild()
    p = _MANUAL['pos']
    banner(f"ADD — leg {p.get('n_legs', 1)} of the {_side} spread",
           sub=f"{date}   +{_u['shares']:,d} sh / +{_u['contracts']} "
               f"{HEDGE_LBL} contracts (${_u['adr_notional']:,.0f})")
    say(f"blended position now: {p['shares']:,d} sh + {p['contracts']} "
        f"contracts = ${p['notional']:,.0f} | avg entry ADR "
        f"{p['entry_adr']:.4f} / {HEDGE_LBL} {p['entry_fut']:.2f}", 'info')
    say(f"time stop still anchors on the FIRST leg ({p['date']}) — an add "
        f"does NOT reset the clock", 'warn')
    return p
def gate_history(tail=15):
    """[Y37g] The gate's LEVELS over the last `tail` typed days — the trend
    view the verdict alone hides. gamma more negative = faster reversion;
    hl in days; drift vs the {c[drift_max]} ceiling."""
    c = _MANUAL['ctx']
    if c is None:
        say('run setup_manual() first', 'bad'); return
    led = _read_ledger()
    led = led[(led['instrument'] == c['instrument'])
              & (led['point'] == c.get('exec_point', 'close'))]
    led = led.drop_duplicates('date', keep='last').sort_values('date').tail(tail)
    if not len(led):
        say('no typed days yet', 'info'); return
    _rows = [{'date': str(r['date']), 'gamma': _led_num(r, 'gamma'),
              'half-life d': _led_num(r, 'hl'), 'drift': _led_num(r, 'drift'),
              'gate': str(r['gate'])} for _, r in led.iterrows()]
    show_html_table(
        _pd.DataFrame(_rows).set_index('date'),
        title=f'GATE LEVELS — last {len(_rows)} day(s)',
        fmt={'gamma': '{:+.3f}', 'half-life d': '{:.1f}', 'drift': '{:.2f}'},
        note=f"gamma is the AR(1) slope of the de-trended deviation "
             f"(negative = mean-reverting), half-life its implied speed, "
             f"drift the [Z4] mean-shift ratio vs the "
             f"{c['drift_max']:.2f} ceiling. A drift GRINDING UP across "
             f"days is a re-rating building — the single most useful trend "
             f"to watch here.")
# ============================================================================
# [Y37] BLOOMBERG PULL & LIVE VIEW — stop typing what the terminal knows.
# ----------------------------------------------------------------------------
# pull_day('2026-07-28')          fetch that day's desk inputs from the
#                                 terminal and PREVIEW them (nothing saved)
# pull_day('2026-07-28', save=True)   same, then books add_day(...) with it
# live_now()                      live premium/z card DURING US hours; says
#                                 so and refuses outside them
# HOW IT WORKS, and the honest limits:
#   * intraday snapshots come from IntradayBarRequest (1-min bars) at the
#     EXACT UTC minutes the capture files use — 05:30 UTC for the Taiwan
#     close anchors, 13:30/14:30, 19:45/20:45 and 19:59/20:59 UTC for the
#     US legs, DST-resolved per date with is_us_dst(). Bloomberg keeps
#     ~140 days of bars: older dates come back empty — type those by hand.
#   * the SSF needs its Bloomberg ticker: set FUT_TICKER_BBG_INST in the
#     INSTRUMENTS dict (e.g. the front-month generic your terminal shows
#     on the QR). Without it the futures fields stay blank in the preview
#     and you type just those two numbers.
#   * FX: the TW-close fixing ('TWD F093') is a DAILY print and pulls
#     fine same-evening. The EXECUTION fx workflow is unchanged — the
#     hedge still deals at TOMORROW'S open and fx_fill() amends it.
#   * every pull is PREVIEWED with source timestamps; save=True is the
#     only thing that writes. The real execution prints (enter/exit_pos)
#     stay MANUAL on purpose — those are your fills, not the terminal's.
# ============================================================================
FUT_TICKER_BBG = globals().get('FUT_TICKER_BBG_INST', None)
def _bbg_open():
    """Fresh short-lived session (the main run's session is long stopped)."""
    _so = blpapi.SessionOptions()
    _so.setServerHost('localhost')
    _so.setServerPort(8194)
    _ss = blpapi.Session(_so)
    if not _ss.start():
        raise RuntimeError('[Y37] cannot start a Bloomberg session — is the '
                           'terminal running on this machine?')
    _ss.openService('//blp/refdata')
    return _ss, _ss.getService('//blp/refdata')
def _bbg_bar_at(ss, svc, ticker, date_str, hh, mm, tol_min=10):
    """LAST 1-min bar CLOSE at/just before hh:mm UTC on date_str.
    Returns (price, 'HH:MM' actually used) or (None, why).
    TIME SEMANTICS (the part that is easy to get wrong):
      * request start/end datetimes are UTC — the refdata service's
        default — and sent as 'YYYY-MM-DDTHH:MM:SS' strings;
      * a bar's `time` stamps its START: the 13:30 bar spans
        13:30:00-13:30:59 and therefore CONTAINS the 09:30:00 ET
        opening auction print, and the 20:00 bar contains the
        16:00:00 ET closing auction (MOC) print. So the right bar for
        a session boundary is the one stamped AT the target minute,
        never the one after — the filter below is `<= target`,
        exactly."""
    _d = pd.Timestamp(date_str)
    _t1 = _d + pd.Timedelta(hours=hh, minutes=mm)
    _t0 = _t1 - pd.Timedelta(minutes=tol_min)
    rq = svc.createRequest('IntradayBarRequest')
    rq.set('security', ticker)
    rq.set('eventType', 'TRADE')
    rq.set('interval', 1)
    rq.set('startDateTime', _t0.strftime('%Y-%m-%dT%H:%M:%S'))
    rq.set('endDateTime', (_t1 + pd.Timedelta(minutes=2)
                           ).strftime('%Y-%m-%dT%H:%M:%S'))
    ss.sendRequest(rq)
    _last = None
    for _spin in range(120):          # [Y37] bounded: ~60s worst case, then
                                      # give up instead of hanging the desk
        ev = ss.nextEvent(500)
        for msg in ev:
            if msg.hasElement('barData'):
                _bt = msg.getElement('barData')
                if _bt.hasElement('barTickData'):
                    _arr = _bt.getElement('barTickData')
                    for _i in range(_arr.numValues()):
                        _b = _arr.getValueAsElement(_i)
                        _bt_time = _b.getElementAsString('time')
                        if pd.Timestamp(_bt_time) <= _t1:   # bar START <= target
                            _last = (_b.getElementAsFloat('close'),
                                     str(_bt_time)[11:16])
        if ev.eventType() == blpapi.Event.RESPONSE:
            break
    else:
        return (None, 'Bloomberg did not answer within ~60s — check the '
                      'terminal session')
    return _last if _last else (None, f'no bars (older than ~140d, or no '
                                      f'trades near {hh:02d}:{mm:02d}Z)')
def _bbg_daily_last(ss, svc, ticker, field, date_str):
    _ymd = pd.Timestamp(date_str).strftime('%Y%m%d')
    rq = svc.createRequest('HistoricalDataRequest')
    rq.getElement('securities').appendValue(ticker)
    rq.getElement('fields').appendValue(field)
    rq.set('startDate', _ymd)
    rq.set('endDate', _ymd)
    rq.set('periodicitySelection', 'DAILY')
    ss.sendRequest(rq)
    _v = None
    for _spin in range(120):          # [Y37] bounded, same reason as above
        ev = ss.nextEvent(500)
        for msg in ev:
            if msg.hasElement('securityData'):
                _sd = msg.getElement('securityData')
                if _sd.hasElement('fieldData'):
                    _fa = _sd.getElement('fieldData')
                    for _i in range(_fa.numValues()):
                        _fd = _fa.getValueAsElement(_i)
                        if _fd.hasElement(field):
                            _v = _fd.getElementAsFloat(field)
        if ev.eventType() == blpapi.Event.RESPONSE:
            break
    return _v
def pull_day(date, save=False):
    """[Y37] Fetch one day's desk inputs from the terminal. PREVIEW by
    default; save=True books add_day(...) with exactly what you saw."""
    c = _MANUAL['ctx']
    if c is None:
        say('run setup_manual() first', 'bad'); return None
    _dst = is_us_dst(date)
    ss, svc = _bbg_open()
    try:
        got, src = {}, {}
        got['ordinary'] = _bbg_daily_last(ss, svc, c['ord_ticker'],
                                          'PX_LAST', date)
        src['ordinary'] = 'daily close (BDH)'
        got['fx'] = _bbg_daily_last(ss, svc, 'TWD F093 Curncy',
                                    'PX_LAST', date)
        src['fx'] = "TW-close fixing 'TWD F093' (BDH)"
        # [Y37] target minutes = the CAPTURE-FILE convention, DST-resolved.
        # Closes aim at the SESSION-CLOSE minute (20:00/21:00): the MOC
        # auction print is timestamped 16:00:00 ET and therefore lives in
        # the bar STAMPED 20:00/21:00 — aiming at 19:59 would fetch the
        # last continuous-trading price instead of the close.
        _legs = [('adr_open', c['adr_ticker'], (13, 30) if _dst else (14, 30)),
                 ('adr_1945', c['adr_ticker'], (19, 45) if _dst else (20, 45)),
                 ('adr_close', c['adr_ticker'], (20, 0) if _dst else (21, 0))]
        if FUT_TICKER_BBG:
            _legs += [('fut_1330', FUT_TICKER_BBG, (5, 30)),
                      ('fut_open', FUT_TICKER_BBG, (13, 30) if _dst else (14, 30)),
                      ('fut_1945', FUT_TICKER_BBG, (19, 45) if _dst else (20, 45)),
                      ('fut_close', FUT_TICKER_BBG, (20, 0) if _dst else (21, 0))]
        for _k, _tk, (_h, _m) in _legs:
            _px, _when = _bbg_bar_at(ss, svc, _tk, date, _h, _m)
            got[_k] = _px
            src[_k] = (f'1-min bar @ {_when}Z' if _px is not None else _when)
    finally:
        ss.stop()
    _rows = [(k, (f"{v:,.4f}" if isinstance(v, float) else '—'), src.get(k, ''))
             for k, v in got.items()]
    kv_table(f"[Y37] PULLED FROM BLOOMBERG — {date} "
             f"({'summer' if _dst else 'winter'} clock)",
             _rows, col='value',
             note='PREVIEW only — nothing saved yet. Eyeball each source '
                  'stamp; then pull_day(date, save=True) books add_day() '
                  'with exactly these numbers. Futures fields blank? Set '
                  'FUT_TICKER_BBG_INST in the INSTRUMENTS dict, or type '
                  'those two numbers by hand.')
    if not save:
        return got
    _need = ('ordinary', 'fx') + (('fut_1330',) if FUT_TICKER_BBG else ())
    _missing = [k for k in _need if got.get(k) is None]
    if 'fut_1330' not in got or got.get('fut_1330') is None:
        say('fut_1330 not pulled — add_day needs it: call add_day(...) '
            'yourself with the SSF anchor typed in, reusing the numbers '
            'above', 'warn')
        return got
    if _missing:
        say(f"missing {_missing} — not saving; pull again or type the day",
            'bad')
        return got
    add_day(date=str(date), ordinary=got['ordinary'],
            fut_1330=got['fut_1330'], fx=got['fx'],
            adr_open=got.get('adr_open'), fut_open=got.get('fut_open'),
            adr_1945=got.get('adr_1945'), fut_1945=got.get('fut_1945'),
            adr_close=got.get('adr_close'), fut_close=got.get('fut_close'))
    say(f"[Y37] saved {date} from the terminal — the FX on any fill is "
        f"still PROVISIONAL until tomorrow's fx_fill()", 'ok')
    return got
def live_now():
    """[Y37] Live premium/z card — ONLY during US trading hours (that is
    when the ADR print is live and the night SSF is quotable). Outside
    them it refuses rather than showing stale numbers."""
    c = _MANUAL['ctx']
    if c is None:
        say('run setup_manual() first', 'bad'); return None
    _now = pd.Timestamp.now('UTC').tz_localize(None)   # [Y37] pandas-4 safe
    _dst = is_us_dst(_now)
    _o = _now.normalize() + (pd.Timedelta(hours=13, minutes=30) if _dst
                             else pd.Timedelta(hours=14, minutes=30))
    _x = _now.normalize() + (pd.Timedelta(hours=20) if _dst
                             else pd.Timedelta(hours=21))
    if not (_o <= _now <= _x):
        say(f"US market is CLOSED (now {_now.strftime('%H:%M')}Z; session "
            f"{_o.strftime('%H:%M')}–{_x.strftime('%H:%M')}Z today) — "
            f"live_now() only works while the ADR is actually trading", 'warn')
        return None
    if not _MANUAL['days']:
        say('type or pull at least one day first — the live card marks '
            'against the latest Taiwan anchors', 'bad'); return None
    _anchor = _MANUAL['days'][-1]
    ss, svc = _bbg_open()
    try:
        _live = {}
        for _k, _tk in [('adr', c['adr_ticker']),
                        ('fx', 'USDTWD BGN Curncy')] \
                + ([('fut', FUT_TICKER_BBG)] if FUT_TICKER_BBG else []):
            rq = svc.createRequest('ReferenceDataRequest')
            rq.getElement('securities').appendValue(_tk)
            rq.getElement('fields').appendValue('PX_LAST')
            ss.sendRequest(rq)
            while True:
                ev = ss.nextEvent(500)
                for msg in ev:
                    if msg.hasElement('securityData'):
                        _sa = msg.getElement('securityData')
                        for _i in range(_sa.numValues()):
                            _se = _sa.getValueAsElement(_i)
                            if _se.hasElement('fieldData'):
                                _fd = _se.getElement('fieldData')
                                if _fd.hasElement('PX_LAST'):
                                    _live[_k] = _fd.getElementAsFloat('PX_LAST')
                if ev.eventType() == blpapi.Event.RESPONSE:
                    break
    finally:
        ss.stop()
    if 'adr' not in _live:
        say('no live ADR print came back — check the terminal', 'bad')
        return None
    _fut_live = _live.get('fut')
    _fx_live = _live.get('fx', _anchor['fx'])
    _fut_for_fair = _fut_live if _fut_live else _anchor['fut']
    # fair_mode-aware live fair:
    #   futures  : straight off the live SSF print
    #   spot_gap : the anchor day's ordinary close, projected by the SSF
    #              move since ITS 13:30 anchor. Type (or pull_day) today's
    #              Taiwan anchors before the US open and the anchor IS
    #              today — the normal workflow.
    if c['fair_mode'] == 'futures':
        fair = _fut_for_fair * c['adr_ratio'] / _fx_live
    else:
        _ord_anchor = _anchor.get('ordinary')
        _f1330_anchor = _anchor.get('fut_1330')
        if not _ord_anchor or not _f1330_anchor:
            say('anchor day has no ordinary/fut_1330 stored — re-add it '
                '(or pull_day it) so the spot_gap live fair has its Taiwan '
                'anchors', 'bad')
            return None
        _gap = _fut_for_fair / _f1330_anchor - 1.0
        fair = _ord_anchor * (1.0 + _gap) * c['adr_ratio'] / _fx_live
    prem = (_live['adr'] / fair - 1.0) * 1e4
    z, mu, sd = _zstats(prem, c['n'])
    gate_ok, gtxt, _, _ = _gate(c['n'])
    banner(f"LIVE — {c['instrument']} {_now.strftime('%H:%M')}Z",
           sub=f"ADR {_live['adr']:,.4f}   {HEDGE_LBL} "
               f"{(_fut_for_fair or float('nan')):,.2f}"
               f"{'' if _fut_live else ' (ANCHOR — no live SSF ticker)'}   "
               f"FX {_fx_live:,.4f}")
    say(f"fair {fair:,.4f} -> premium {prem:+,.0f} bps | z {z:+.2f} "
        f"(band ±{c['thresh']:.2f})",
        'warn' if abs(z) > c['thresh'] else 'info')
    say(f"gate {'OPEN' if gate_ok else 'SHUT'} — {gtxt}",
        'ok' if gate_ok else 'bad')
    if _MANUAL['pos'] is not None and _fut_live:
        m = _mtm(_live['adr'], _fut_live, _fx_live)
        say(f"open position mark: ${m['gross']:+,.0f} ({m['bps']:+.0f} bps)",
            'ok' if m['gross'] >= 0 else 'warn')
    say('reminder: a LIVE z uses the live prints against CLOSE-based '
        'history — indicative, not the booked signal', 'info')
    return dict(adr=_live['adr'], fut=_fut_live, fx=_fx_live,
                fair=fair, prem_bps=prem, z=z)
banner("v32 TW — EXTRAS LOADED", sub=f"{INSTRUMENT}: {ADR_TICKER} vs {ORD_TICKER}")
menu([
    ("setup_manual()", "paper desk — start here each session"),
    ("form()", "the typing form: one row per evening"),
    ("pull_day('2026-07-28')", "[Y37] fetch a day's inputs from Bloomberg "
                               "(preview; save=True books it) — ~140d of "
                               "intraday history"),
    ("live_now()", "[Y37] live premium/z card, US hours only"),
    ("add_to(adr=..., fut=..., fx=..., date=...)",
     "[Y38] add a leg while the spike extends (the card suggests it)"),
    ("gate_history()", "[Y37g] gamma / half-life / drift trend, from the ledger"),
    ("status()", "position, marks, live z and the exit verdict"),
    ("help_manual()", "the whole desk workflow in one screen"),
    ("why_no_trades(start, end)", "[X6] per-row entry verdict over a window"),
    ("show_grid_html()", "the grid matrices as heat maps"),
    ("select_composite()", "re-rank the plateau with other weights"),
    ("zchart()", "rolling z + premium band incl. your typed days"),
    ("run_backtest_lots(df, best_n, best_thresh, max_adds=2)",
     "pyramiding — SELF-TEST FIRST: max_adds=0, unwind_frac=0 must "
     "reproduce run_backtest exactly"),
], title="WHAT TO RUN NEXT")
 
