# ============================================================================
# v33 — HK ADR BASKET BOOK. This file REPLACES the single-name HK strategy
# (v32_hk_full.py, kept on disk as reference only). Every design decision
# below is tagged [B..]; the lessons imported from the legacy post-mortem are
# tagged [L..]. Grep "[B" / "[L" to walk them in order.
# ----------------------------------------------------------------------------
# WHAT THIS BOOK TRADES
#   A BASKET of HK-listed Hang Seng TECH constituents that also have liquid
#   US ADRs. When the WHOLE basket trades rich/cheap vs fair value (breadth-
#   gated, see [B3]), one package goes on:
#       SHORT package (basket rich):  sell ADRs / buy ordinaries
#       LONG  package (basket cheap): buy ADRs / short ordinaries
#   Each name is paired against its OWN ordinary at the mechanical ADS ratio.
#   Hang Seng TECH futures (HTI) are used ONLY as an overnight BRIDGE: the
#   two legs of the package cannot be traded at the same wall-clock time
#   (ADRs at the US close, ordinaries at the next HK open), so HTI carries
#   the market delta across the gap — held ~overnight, never for the life
#   of the trade.
#
# THE CLOCK (all times HKT; UTC in brackets; HK has no DST)
#   03:00 (19:00Z)  HTI T+1-session close — the LAST tradable index print
#                   of the calendar day, and where the entry bridge fills.
#   04:00/05:00     US cash close (20:00Z summer / 21:00Z winter). ADR legs
#                   fill at/into the close alongside the bridge ([B2a]).
#   09:15-09:30     HTI day session opens 09:15 (01:15Z); HK stock opening
#                   auction 09:30 (01:30Z): ordinary legs fill here, the
#                   bridge comes off — the pair is LOCKED before the
#                   19:00-19:30 HKT slot where these names usually report.
#
# ENTRY / EXIT ([B4] — hybrid z + cost floor, settled 2026-07-31)
#   basket z >= +Z_ENTRY (rolling N_WINDOW)  -> SHORT package
#   basket z <= -Z_ENTRY                     -> LONG  package
#   ... AND the deviation in bps must clear the cost-anchored floor
#   (auto-derived from the cost model; the user's original +55/-60 pair is
#   the 'manual' option and sits almost exactly ON the auto floor).
#   Exit on z crossing EXIT_Z (default 0), time stop, or regime gate.
#   Deviation = basket premium minus its own rolling mean, so each name's
#   STRUCTURAL discount/premium is stripped before aggregation.
#
# FAIR VALUE ([B2]) is carried across time zones by the HTI FUTURES snaps
#   (capture job files), not by any single-stock future.
#
# [B2a] SIGNAL CLOCK vs EXECUTION CLOCK — the load-bearing design choice.
#   The premium is OBSERVED where both sides are fresh (the US close, both
#   legs at most ~2h stale) and the package goes on THE SAME NIGHT, ADR
#   side first (user decision 2026-07-31 — this replaced an earlier
#   next-HK-close design whose bridge window straddled the 19:00-19:30 HKT
#   earnings slot):
#       SIGNAL (t, ~19:00-21:00Z):
#           fair_ord_i = Ord_i(t 16:00 close) x (1 + beta_i x
#                        HTI(08:00Z t -> 19:00Z t))
#           prem_i(t) = ADR_i(t) x USDHKD / ratio_i / fair_ord_i - 1
#       EXECUTION, two timings ([HKX], compared head-to-head every run):
#         'hti_close' (DEFAULT — the user's stated flow): ADR legs fill
#             ~3pm ET alongside the HTI bridge at the 19:00Z T+1 close —
#             ZERO naked window. Bridge rides overnight; at the next HK
#             open (09:15-09:30 HKT) the ordinaries fill at the opening
#             auction and the bridge comes off. Pair locked by 09:30 HKT
#             — BEFORE the typical China-ADR earnings slot (pre-US-open
#             = 19:00-19:30 HKT), so a locked pair eats the print, not a
#             one-legged package.
#         'us_close': ADR legs fill MOC at 20:00/21:00Z — but the HTI T+1
#             session shut at 19:00Z, so there is NO bridge: the ADR legs
#             ride NAKED ~5h to the HK open, then the ordinaries lock the
#             pair. Saves the bridge costs (~5 bps), eats the overnight
#             gap. (With daily data both timings fill the ADR at the
#             close print; the 19:00Z-vs-MOC gap is reported staleness.)
#       EXITS mirror the entries: ADRs unwind at the US close with (or
#       without) the bridge, ordinaries unwind at the next HK open.
#   ONE SIGN CONVENTION EVERYWHERE (the house one): prem > 0 means the
#   ADR SIDE is RICH vs the HK line -> SHORT-package territory once the
#   basket deviation clears +55 bps; prem < 0 (ADR discount) mirrors into
#   the LONG package at -60.
#
# HEDGE RATIOS ([B5]) — three estimators, selectable, compared side by side:
#   'ols_shrunk' (DEFAULT)  per-name rolling OLS/EWMA beta of ordinary
#                           returns on HTI returns, shrunk to a per-name
#                           prior and clamped — the bridge is held hours, so
#                           robustness beats cleverness here.
#   'pca'                   PC1 of the ordinary-return panel maps the basket
#                           onto the common factor, and PC1 is regressed on
#                           HTI to size the bridge. Catches the complex
#                           moving as ONE factor with non-index weights.
#   'coint'                 Engle-Granger per name (log ADR-in-HKD vs log
#                           ord). NOT a trade ratio — the pair ratio is the
#                           mechanical ADS ratio [L1] — it is an INCLUSION
#                           gate: a name whose premium fails stationarity is
#                           excluded from the basket until it passes again.
#
# LESSONS FROM THE LEGACY BOOK (reference only — the code they refer to is
# NOT carried forward):
#   [L1] The index future is NEVER the pair leg. The legacy index_fut mode
#        held HTI against a single name for the whole trade and its ~50/50
#        win rate was exactly the index-vs-name mismatch dressed up as a
#        strategy. Here HTI exposure exists only inside the entry/exit
#        bridge windows (hours), and the pair leg is the name's own
#        ordinary at the mechanical ratio.
#   [L2] One PnL convention: two_leg. Every leg (each ADR, each ordinary,
#        each bridge crossing, FX) is marked off its own fills. The legacy
#        'convergence' mode is kept ONLY as a per-trade diagnostic column,
#        and [B8] prints the leg-by-leg reconciliation, so any gap between
#        the two is ATTRIBUTABLE (basis, residual window, costs) instead of
#        a mystery disparity.
#   [L3] No ETF hedge mode. The legacy us_etf PnL was abnormally small
#        because the ETF leg's tracking PnL swallowed the premium PnL.
#        Deleted, not switched off.
#   [L4] No contradictory timing combos. Legacy allowed index_fut +
#        stock_open_only, which hedged with an index the strategy said it
#        would not hold. v33 timing is ONE explicit package timeline.
#   [L5] Audit blocks run on the SAME series and the SAME data structures
#        the engine uses. (The legacy [W4] audit indexed a tuple with a
#        string and ran gamma on the wrong series — fixed there as [X16],
#        structurally impossible here because there is exactly one
#        gate-series builder, gate_series().)
#
# DATA
#   Bloomberg daily BDH per name (ADR PX_LAST/PX_OPEN, ord PX_LAST/PX_OPEN),
#   USDHKD, HSTECH Index; the SHARED HTI capture snaps
#   HST_front_month_0800utc.csv / _1900utc.csv (same files, same loader,
#   same timestamp validation as before). DATA_MODE='auto' falls back to a
#   SYNTHETIC panel (loud banner) when blpapi is absent, so the whole file
#   runs end-to-end on any machine — the synthetic generator plants known
#   dislocations, which doubles as the engine's self-test [B9].
# ============================================================================

# ============================================================================
# ██ QUICK SETTINGS — the knobs you actually change, all in ONE place. ██
# ============================================================================
# [B4] ENTRY RULE — hybrid, two conditions answering different questions
# (settled 2026-07-31 when the user clarified the original n=55/-60 spec
# assumed the z-score rolling-window machinery):
#   1. TIMING, regime-adaptive: the basket z over rolling N_WINDOW must
#      clear Z_ENTRY on the entered side. z alone is scale-free — it
#      cannot see costs (the [S1] lesson), so it never trades alone.
#   2. ECONOMICS, cost-anchored: |basket dev| in bps must clear the
#      deviation floor. 'auto' DERIVES it from the cost model each run
#      (RT cost x MIN_EDGE_HARD — tracks fees instead of going stale);
#      'manual' uses the pair below — the user's original +55/-60, which
#      sit almost exactly ON the auto floor for the screen-only stack.
# The [B4] sweep grid is N_GRID x Z_GRID (the house N x Z table).
N_WINDOW = 30               # rolling window: per-name mean + z sigma
Z_ENTRY_SHORT = 1.5         # short the package when basket z >= +1.5 ...
Z_ENTRY_LONG = 1.5          # ... long it when basket z <= -1.5 (AND floor)
DEV_FLOOR_MODE = 'auto'     # 'auto' (cost-derived) | 'manual' (pair below)
DEV_FLOOR_SHORT_BPS = 55.0
DEV_FLOOR_LONG_BPS = -60.0
EXIT_Z = 0.0                # exit when z crosses this (0 = full reversion)
TIME_STOP = 20              # calendar days, hard cap
NOTIONAL_BASKET = 1_000_000  # USD package size (split across names by weight)
EXEC_TIMING = 'hti_close'   # [B2a] 'hti_close' (bridged, zero naked window)
                            #       | 'us_close' (MOC, no bridge, ~5h naked)
HEDGE_RATIO_MODE = 'static_prior'  # [B5] 'static_prior' (DEFAULT: one
                            # number per name from UNIVERSE, zero runtime
                            # estimation) | 'beta_one' (bridge = 1.0 x
                            # notional; ~10-15 bps/window extra mean-zero
                            # noise from overhedging these ~0.7-0.9-beta
                            # names) | 'ols' (rolling estimate; the [B5]
                            # table prints it vs the priors every run
                            # regardless, so priors stay honest)
SIZING_MODE = 'z_scaled'    # 'z_scaled': size = min(|z|/Z_ENTRY, SIZE_CAP);
                            # 'fixed': every package 1.0x
SIZE_CAP = 2.0
DIRECTION_FILTER = 'both'   # 'both' | 'long_only' | 'short_only'
BREADTH_MIN = 0.60          # [B3] fraction of live names agreeing in sign
CORR_MIN = 0.40             # [B5c] name joins the basket only if rolling
                            # corr(ord, HTI) clears this
# [B10] DEPOSITARY CONVERSION — REFERENCE ONLY (user 2026-07-31: the desk
# does not use the channel, so the ENGINE never books it). These names are
# fungible dual listings, and a conversion exit (deliver ords into ADS
# creation / cancel ADSs into the ord short) would cap the exit at roughly
# the depositary fee + slip instead of re-crossing spread + stamp — the
# [B8] header prints what that would be worth so the option stays visible.
CONV_FEE_USD_PER_ADS = 0.05      # depositary issuance/cancellation fee
CONV_SLIP_BPS = 5.0              # settlement-window buffer — desk quote
EARNINGS_SOURCE = 'auto'         # [B6] 'auto': pull announcement dates per
                                 # name from Bloomberg (ERN_ANN_DT_AND_PER
                                 # bulk field) — NO manual lists needed;
                                 # manual UNIVERSE entries are MERGED in if
                                 # present. 'manual': UNIVERSE lists only.
                                 # NOTE the hti_close flow is structurally
                                 # immune to the usual pre-US-open slot
                                 # (pair locked by 09:30 HKT); the gate
                                 # covers post-US-close prints and fill-day
                                 # releases.
DATA_MODE = 'auto'          # 'auto' | 'bloomberg' | 'synthetic'
SYNTH_SEED = 7              # synthetic panel seed (reproducibility)
IDX_FILE_PREFIX = r"G:\FIN_COMM\DeltaOne\Kenny\ADR\HST_front_month_"
HTML_OUTPUT = True          # notebook tables; plain text always printed too
CHART_FILE = 'v33_basket_charts.png'   # None = no chart file
# ============================================================================
import os
import math
import warnings
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

try:                                    # ADF is optional: the default gate
    from statsmodels.tsa.stattools import adfuller   # is gamma/half-life
    _HAVE_SM = True
except Exception:
    adfuller = None
    _HAVE_SM = False

warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=RuntimeWarning)

# ============================================================================
# [B0] UNIVERSE — HS Tech constituents with US-listed ADRs. Per-name fields:
#   adr / ord     Bloomberg tickers (the ONLY place tickers live — every
#                 label anywhere in the output derives from these)
#   ratio         ordinary shares per ADS — VERIFY EVERY ONE ON DES before
#                 trusting a live run; a wrong ratio manufactures a premium
#   lot           HK board lot (shares) — ord clips snap DOWN to whole lots
#   beta_prior    anchor for the rolling beta [B5]; refreshed from data
#   adv_usd       ADR average daily $ volume — sets basket weights [B3]
#   borrow_bps    annualised borrow for SHORTING the ordinary (long package)
#   earnings      'YYYY-MM-DD' announcement dates (entry block [B6]);
#                 EMPTY = that gate is OFF for the name (warned once)
#   divs          (HK ex-date, HKD/share) manual dividend list for the
#                 premium carry correction [B6b]; empty = correction off
# TCEHY/700 is deliberately ABSENT: the ADR is OTC, no closing auction, so
# the package's ADR-MOC leg does not exist for it.
# ============================================================================
UNIVERSE = {
    'BABA': dict(adr='BABA US Equity', ord='9988 HK Equity', ratio=8.0,
                 lot=100, beta_prior=0.70, adv_usd=740e6, borrow_bps=100,
                 earnings=[], divs=[]),
    'JD':   dict(adr='JD US Equity',   ord='9618 HK Equity', ratio=2.0,
                 lot=50,  beta_prior=0.75, adv_usd=300e6, borrow_bps=100,
                 earnings=[], divs=[]),
    'BIDU': dict(adr='BIDU US Equity', ord='9888 HK Equity', ratio=8.0,
                 lot=50,  beta_prior=0.75, adv_usd=250e6, borrow_bps=100,
                 earnings=[], divs=[]),
    'NTES': dict(adr='NTES US Equity', ord='9999 HK Equity', ratio=5.0,
                 lot=100, beta_prior=0.60, adv_usd=150e6, borrow_bps=100,
                 earnings=[], divs=[]),
    'TCOM': dict(adr='TCOM US Equity', ord='9961 HK Equity', ratio=1.0,
                 lot=50,  beta_prior=0.60, adv_usd=180e6, borrow_bps=100,
                 earnings=[], divs=[]),
    'BILI': dict(adr='BILI US Equity', ord='9626 HK Equity', ratio=1.0,
                 lot=20,  beta_prior=1.10, adv_usd=120e6, borrow_bps=150,
                 earnings=[], divs=[]),
    'XPEV': dict(adr='XPEV US Equity', ord='9868 HK Equity', ratio=2.0,
                 lot=100, beta_prior=1.20, adv_usd=150e6, borrow_bps=150,
                 earnings=[], divs=[]),
    'LI':   dict(adr='LI US Equity',   ord='2015 HK Equity', ratio=2.0,
                 lot=100, beta_prior=1.00, adv_usd=120e6, borrow_bps=150,
                 earnings=[], divs=[]),
    'NIO':  dict(adr='NIO US Equity',  ord='9866 HK Equity', ratio=1.0,
                 lot=10,  beta_prior=1.20, adv_usd=200e6, borrow_bps=200,
                 earnings=[], divs=[]),
}
NAMES = list(UNIVERSE.keys())
W_CAP = 0.25                # [B3] no name above 25% of the package
MIN_NAMES_LIVE = 5          # fewer live names than this -> no basket that day

# ---- market constants ------------------------------------------------------
FX_TICKER = 'USDHKD Curncy'         # pegged 7.75-7.85, deliverable
FX_SANE_BAND = (7.70, 7.90)
IDX_TICKER = 'HSTECH Index'         # marking spine / beta regressor
IDX_FUT_MULTIPLIER = 50             # HK$ per HTI point (~US$28k a contract)
SNAP_LOCAL_CLOSE_PATH = IDX_FILE_PREFIX + "0800utc.csv"   # 16:00 HKT
SNAP_T1_CLOSE_PATH = IDX_FILE_PREFIX + "1900utc.csv"      # 03:00 HKT T+1 end
SNAPSHOT_TIME_TOL_MIN = 20
LOOKBACK_DAYS = 1825

# ---- cost model ([B8]; per-leg, per-direction, charged on the leg's own
# notional; the [S1]-style floor check prints these against the entry
# thresholds so a threshold below cost is VISIBLE) ---------------------------
ORD_STAMP_BPS = 10.0        # HK stamp 0.1% PER SIDE, stock legs only
ORD_LEVIES_BPS = 1.1        # SFC + AFRC levies + exchange fee, per side
ORD_HALF_SPREAD_BPS = 5.0   # close-auction effective half-spread (measure!)
ADR_FEE_BPS = 2.0           # per side: commission + SEC fee headroom
ADR_HALF_SPREAD_BPS = 1.5   # MOC effective half-spread
ADR_BORROW_ANN_BPS = 50     # short-ADR borrow (SHORT package)
FUT_FEE_BPS = 1.0           # HTI per side (exchange + levy, ~HK$7/contract)
FUT_HALF_SPREAD_BPS = 2.5   # T+1 tail book — measured on the QR screen
FUT_HALF_SPREAD_DAY_BPS = 2.0   # day session (16:00 bridge fill)
FX_HALF_SPREAD_BPS = 1.0    # deliverable pegged spot
FUNDING_ANN_BPS = 480       # cash funding on the LONG leg over the hold
# [S1] lesson, split in two so the configured +55/-60 thresholds are not
# silently overridden: the HARD gate refuses entries below MIN_EDGE_HARD x
# the RT cost; MIN_EDGE_ADVISORY is the margin the header RECOMMENDS —
# when a threshold sits between the two, the run WARNs loudly but still
# trades it. HARD is 0.9, not 1.0, deliberately: screen-only RT (~55 bps)
# sits almost exactly ON the configured +55 threshold, and a 1.0 floor
# would silently strangle the user's own setting — the scorecard tells the
# truth about breakeven instead.
MIN_EDGE_HARD = 0.9
MIN_EDGE_ADVISORY = 1.5
BRIDGE_RESID_HOURS = 1.5    # [B7] 19:00Z bridge-lift -> 20:00/21:00Z ADR MOC

# ---- regime gate ([B6]; identical mathematics to the legacy engine, one
# builder so the engine and every audit read the SAME series [L5]) ----------
GATE_MODE = 'halflife_drift'    # 'halflife_drift' | 'adf_deviation' | 'off'
GATE_WINDOW = 60
ADF_DETREND_N = 20
ADF_PVALUE = 0.10
HL_MAX_DAYS = 15.0
DRIFT_MAX_SIGMA = 0.50
EARNINGS_BLOCK_DAYS = 1         # [B6] with the hti_close flow the exposed
                                # window is only signal night -> next HK
                                # open, so blocking the announcement day
                                # and the signal day before it suffices
MAX_ENTRY_GAP_DAYS = 4          # no fresh entry into a long holiday gap

# ---- beta / PCA / coint estimation [B5] -----------------------------------
BETA_WINDOW = 90
BETA_HALFLIFE = 45
BETA_SHRINK_W = 0.6             # weight on the rolling estimate vs the prior
BETA_MIN, BETA_MAX = 0.2, 1.6
CORR_WINDOW = 60
COINT_WINDOW = 250
COINT_PMAX = 0.10               # EG residual ADF p to count as cointegrated
COINT_GATE = 'report'           # 'report' | 'exclude'  (exclude = hard gate)

# ---- [B4] N x Z sweep grid (the house table; floor always on) -------------
N_GRID = [20, 30, 45, 60]
Z_GRID = [1.0, 1.5, 2.0, 2.5]

# ============================================================================
# DISPLAY HELPERS — compact port of the house style: styled HTML tables in a
# notebook, the SAME numbers as aligned plain text in a terminal, and every
# instrument label derived from the UNIVERSE tickers (nothing hard-coded).
# ============================================================================
HTML_FILE = 'v33_basket_tables.html'
_HTML_STARTED = False
_CSS = ("<style>.v33tbl{border-collapse:collapse;margin:10px 0;"
        "font:12.5px -apple-system,'Segoe UI',Roboto,Arial,sans-serif;"
        "color:#212b36;border:1px solid #e3e6ea}"
        ".v33tbl th{background:#f7f8fa;color:#42505c;font-size:11px;"
        "font-weight:600;text-transform:uppercase;padding:6px 10px;"
        "border-bottom:1px solid #e3e6ea;text-align:right}"
        ".v33tbl td{padding:5px 10px;text-align:right;white-space:nowrap;"
        "border-bottom:1px solid #eef1f4;font-variant-numeric:tabular-nums}"
        ".v33tbl th:first-child,.v33tbl td:first-child{text-align:left}"
        ".v33tbl caption{caption-side:top;text-align:left;color:#1c2733;"
        "font-weight:600;padding:5px 2px}"
        ".v33note{font:11.5px -apple-system,'Segoe UI',Roboto,Arial;"
        "color:#5f6b76;margin:2px 0 12px;max-width:860px}</style>")

def _in_jupyter():
    try:
        from IPython import get_ipython
        ip = get_ipython()
        if ip is None or type(ip).__name__ == 'TerminalInteractiveShell':
            return False
        return True
    except Exception:
        return False

def _html_to_file(html):
    global _HTML_STARTED
    if not HTML_FILE:
        return
    try:
        mode = 'a' if _HTML_STARTED else 'w'
        with open(HTML_FILE, mode, encoding='utf-8') as f:
            if not _HTML_STARTED:
                f.write("<html><head><meta charset='utf-8'>"
                        "<title>v33 basket tables</title></head><body>" + _CSS)
            f.write(html)
        if not _HTML_STARTED:
            _HTML_STARTED = True
            print(f"  [note] HTML tables also written to "
                  f"{os.path.abspath(HTML_FILE)}")
    except Exception as e:
        print(f"  [note] could not write {HTML_FILE}: {e}")

def show_table(frame, title='', note='', fmt='{:,.0f}'):
    """Styled table in a notebook; the SAME formatted numbers as plain text
    otherwise (never raw to_string dumps — 3am readability rule)."""
    plain = frame.copy()
    for c in plain.columns:
        f = fmt.get(c) if isinstance(fmt, dict) else fmt
        if not f:
            continue
        num = pd.to_numeric(plain[c], errors='coerce')
        vals = []
        for i, v in enumerate(num):
            if pd.isna(v):
                orig = plain[c].iloc[i]
                vals.append('\u2014' if pd.isna(orig) else orig)
            else:
                try:
                    vals.append(f.format(v))
                except Exception:
                    vals.append(str(plain[c].iloc[i]))
        plain[c] = vals
    if HTML_OUTPUT and _in_jupyter():
        try:
            from IPython.display import display, HTML
            sty = frame.style.set_table_attributes('class="v33tbl"')
            if isinstance(fmt, (str, dict)):
                sty = sty.format(fmt, na_rep='\u2014')
            if title:
                sty = sty.set_caption(title)
            html = _CSS + sty.to_html()
            if note:
                html += f"<div class='v33note'>{note}</div>"
            display(HTML(html))
            _html_to_file(html)
            return
        except Exception:
            pass
    if title:
        print(f"\n  {title}")
    txt = plain.to_string()
    print('  ' + txt.replace('\n', '\n  '))
    if note:
        print(f"  NOTE: {note}")
    if HTML_FILE:
        try:
            sty = frame.style.set_table_attributes('class="v33tbl"')
            if isinstance(fmt, (str, dict)):
                sty = sty.format(fmt, na_rep='\u2014')
            if title:
                sty = sty.set_caption(title)
            html = sty.to_html()
            if note:
                html += f"<div class='v33note'>{note}</div>"
            _html_to_file(html)
        except Exception:
            pass

_SCORECARD = []
def sc(level, key, value):
    """Collect a header-scorecard line: level in INFO/WARN/FAIL."""
    _SCORECARD.append((level, key, value))

def print_scorecard():
    if not _SCORECARD:
        return
    print("\n" + "=" * 76)
    print("  RUN SCORECARD — read the FAILs before believing any number below")
    print("=" * 76)
    order = {'FAIL': 0, 'WARN': 1, 'INFO': 2}
    for lv, k, v in sorted(_SCORECARD, key=lambda r: order.get(r[0], 3)):
        print(f"  [{lv:<4}] {k:<34} {v}")

def _short(tkr):
    """'BABA US Equity' -> 'BABA US'."""
    p = str(tkr).split()
    return ' '.join(p[:2]) if len(p) >= 2 else str(tkr)

def is_us_dst(d):
    """Second Sunday of March -> first Sunday of November."""
    ts = pd.Timestamp(d)
    y = ts.year
    mar = pd.Timestamp(y, 3, 1)
    mar2nd_sun = mar + pd.Timedelta(days=(6 - mar.dayofweek) % 7 + 7)
    nov = pd.Timestamp(y, 11, 1)
    nov1st_sun = nov + pd.Timedelta(days=(6 - nov.dayofweek) % 7)
    return mar2nd_sun <= ts < nov1st_sun

# ============================================================================
# DATA LAYER. Three modes:
#   'bloomberg'  the real thing (blpapi + capture CSVs), same request shape
#                and the same [H1] snapshot-timestamp validation as before.
#   'synthetic'  factor-model panel with PLANTED dislocations [B9] — runs
#                anywhere, doubles as the engine self-test.
#   'auto'       bloomberg if blpapi imports AND the session starts, else
#                synthetic with a loud banner.
# Output of either path is ONE dict of aligned DataFrames (see build_panel).
# ============================================================================
def _load_snapshot_csv(path, price_name, expected_utc=None):
    """Capture-CSV loader (port of the validated house loader): cols
    [Date, ?, price, capture-timestamp?, contract?]; rows whose capture
    timestamp sits outside expected_utc +- tolerance are dropped LOUDLY."""
    try:
        try:
            raw = pd.read_csv(path, header=None, usecols=[0, 2, 3, 4],
                              names=['Date', price_name, 'CapTS', 'Contract'])
        except Exception:
            raw = pd.read_csv(path, header=None, usecols=[0, 2, 3],
                              names=['Date', price_name, 'CapTS'])
    except Exception:
        raw = pd.read_csv(path, header=None, usecols=[0, 2],
                          names=['Date', price_name])
        raw['CapTS'] = np.nan
    raw['Date'] = pd.to_datetime(raw['Date'], format='%m/%d/%Y',
                                 errors='coerce')
    raw[price_name] = pd.to_numeric(raw[price_name], errors='coerce')
    nbad = int(raw[['Date', price_name]].isna().any(axis=1).sum())
    if nbad:
        print(f"[QC] {path}: {nbad} unparseable rows dropped")
    raw = raw.dropna(subset=['Date', price_name])
    if raw['CapTS'].notna().any() and expected_utc:
        try:
            ts = pd.to_datetime(raw['CapTS'], errors='coerce',
                                format='ISO8601')
        except (TypeError, ValueError):
            ts = pd.to_datetime(raw['CapTS'], errors='coerce')
        hh, mm = (int(x) for x in expected_utc.split(':'))
        target = hh * 60 + mm
        cap = ts.dt.hour * 60 + ts.dt.minute
        diff = (cap - target).abs()
        diff = np.minimum(diff, 1440 - diff)
        ok = (diff <= SNAPSHOT_TIME_TOL_MIN) & ts.notna()
        stale = int((~ok).sum())
        if stale:
            print(f"[QC] {path}: dropped {stale} rows captured outside "
                  f"{expected_utc}Z +-{SNAPSHOT_TIME_TOL_MIN}min")
        raw = raw.loc[ok]
    raw['Date'] = raw['Date'].dt.strftime('%Y-%m-%d')
    return raw[['Date', price_name]].drop_duplicates('Date', keep='last')

def load_bloomberg():
    """Daily BDH pulls per name + FX + index, and the shared HTI snaps.
    Raises on session failure so 'auto' can fall back."""
    import blpapi
    opts = blpapi.SessionOptions()
    opts.setServerHost('localhost')
    opts.setServerPort(8194)
    session = blpapi.Session(opts)
    if not session.start():
        raise RuntimeError('blpapi session failed to start')
    session.openService('//blp/refdata')
    svc = session.getService('//blp/refdata')
    end = datetime.today().strftime('%Y%m%d')
    start = (datetime.today() - timedelta(days=LOOKBACK_DAYS)).strftime('%Y%m%d')

    def hist(security, field):
        req = svc.createRequest('HistoricalDataRequest')
        req.getElement('securities').appendValue(security)
        req.getElement('fields').appendValue(field)
        req.set('startDate', start)
        req.set('endDate', end)
        req.set('periodicitySelection', 'DAILY')
        # ACTIVE_DAYS_ONLY: never forward-fill a holiday — a stale HK print
        # on a US trading day manufactures a fake premium
        req.set('nonTradingDayFillOption', 'ACTIVE_DAYS_ONLY')
        session.sendRequest(req)
        rec = []
        while True:
            ev = session.nextEvent(500)
            for msg in ev:
                if not msg.hasElement('securityData'):
                    continue
                sd = msg.getElement('securityData')
                if sd.hasElement('securityError'):
                    print(f"[QC] Bloomberg securityError for {security}")
                if sd.hasElement('fieldData'):
                    arr = sd.getElement('fieldData')
                    for i in range(arr.numValues()):
                        fd = arr.getValueAsElement(i)
                        if not fd.hasElement(field):
                            continue
                        rec.append({'Date': fd.getElementAsString('date'),
                                    'px': fd.getElementAsFloat(field)})
            if ev.eventType() == blpapi.Event.RESPONSE:
                break
        if not rec:
            print(f"[QC] WARNING: no data for {security}/{field}")
        return pd.DataFrame(rec)

    def earnings_dates(security):
        """[B6] announcement-date HISTORY via the ERN_ANN_DT_AND_PER bulk
        field — no manual lists. Returns ['YYYY-MM-DD', ...] (may be [])."""
        try:
            req = svc.createRequest('ReferenceDataRequest')
            req.getElement('securities').appendValue(security)
            req.getElement('fields').appendValue('ERN_ANN_DT_AND_PER')
            session.sendRequest(req)
            out = []
            while True:
                ev = session.nextEvent(500)
                for msg in ev:
                    if not msg.hasElement('securityData'):
                        continue
                    sarr = msg.getElement('securityData')
                    for i in range(sarr.numValues()):
                        sd = sarr.getValueAsElement(i)
                        if not sd.hasElement('fieldData'):
                            continue
                        fd = sd.getElement('fieldData')
                        if not fd.hasElement('ERN_ANN_DT_AND_PER'):
                            continue
                        bulk = fd.getElement('ERN_ANN_DT_AND_PER')
                        for j in range(bulk.numValues()):
                            row = bulk.getValueAsElement(j)
                            try:
                                out.append(str(row.getElementAsString(
                                    'Announcement Date')))
                            except Exception:
                                try:
                                    out.append(str(row.getElement(0)
                                                   .getValueAsString()))
                                except Exception:
                                    pass
                if ev.eventType() == blpapi.Event.RESPONSE:
                    break
            return sorted({d[:10] for d in out if d and d[0].isdigit()})
        except Exception as e:
            print(f"[B6] WARNING: earnings pull failed for {security} "
                  f"({e}) — gate weakened for this name")
            return []

    data = {'names': {}}
    for nm, u in UNIVERSE.items():
        d = {}
        d['adr_close'] = hist(u['adr'], 'PX_LAST')
        d['adr_open'] = hist(u['adr'], 'PX_OPEN')
        d['ord_close'] = hist(u['ord'], 'PX_LAST')
        d['ord_open'] = hist(u['ord'], 'PX_OPEN')
        if EARNINGS_SOURCE == 'auto':
            d['earnings'] = sorted(set(earnings_dates(u['adr'])
                                       ) | set(u['earnings']))
        else:
            d['earnings'] = list(u['earnings'])
        data['names'][nm] = d
        print(f"[DATA] {nm}: ADR {_short(u['adr'])} {len(d['adr_close'])} rows, "
              f"ord {_short(u['ord'])} {len(d['ord_close'])} rows, "
              f"{len(d['earnings'])} earnings dates")
    data['fx'] = hist(FX_TICKER, 'PX_LAST')
    data['idx'] = hist(IDX_TICKER, 'PX_LAST')
    data['idx_open'] = hist(IDX_TICKER, 'PX_OPEN')   # marks the bridge OFF
    data['hti_0800'] = _load_snapshot_csv(SNAP_LOCAL_CLOSE_PATH,
                                          'HTI_0800', '08:00')
    data['hti_1900'] = _load_snapshot_csv(SNAP_T1_CLOSE_PATH,
                                          'HTI_1900', '19:00')
    data['mode'] = 'bloomberg'
    return data

def load_synthetic(seed=SYNTH_SEED, n_days=1100):
    """[B9] Factor-model panel with PLANTED dislocations.
    One HTI factor with intraday nodes (0800Z close-of-HK, 1900Z T+1 end,
    2000Z US close); each ordinary = beta x factor + idio; each ADR = its
    fair value AT ITS OWN CLOCK TIME x (1 + premium), premium a per-name
    AR(1) plus ~1-per-2-month +-80-150bp shocks that then mean-revert —
    exactly what the strategy claims to monetise. The engine finding and
    fading THESE (and only these) is the self-test."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range('2022-01-03', periods=n_days)
    # skip fabricated holidays independently per market (~6/yr each) to
    # exercise the calendar-alignment QC
    hk_hol = set(rng.choice(n_days, size=n_days // 40, replace=False))
    us_hol = set(rng.choice(n_days, size=n_days // 40, replace=False))
    F = 5000.0
    rows = []
    prem = {nm: rng.normal(0, 8e-4) for nm in NAMES}
    prem_mean = {nm: rng.normal(-2e-3, 2e-3) for nm in NAMES}  # structural
    phi = 0.88
    # COMPLEX-WIDE premium factor: what the basket strategy actually
    # trades. AR(1) around zero plus a +-100-180bp shock roughly every
    # three months that then mean-reverts with a ~9-10 day half-life
    # (phi 0.93 — calibrated to how real ADR-premium episodes behave:
    # the BABA book's real entries sat at 100-300bp dev and held 3-14
    # days, not 1-2). The engine finding and fading THESE, and mostly
    # ignoring the per-name idio shocks, is the test.
    common = 0.0
    phi_c = 0.93
    common_path = []
    for t in range(n_days):
        c_shock = 0.0
        if rng.random() < 1 / 60:
            c_shock = rng.choice([-1, 1]) * rng.uniform(0.010, 0.018)
        common = phi_c * common + rng.normal(0, 1.2e-4) + c_shock
        common_path.append(common)
    for t in range(n_days):
        # factor path: four intraday nodes, daily vol ~1.9%
        r1a = rng.normal(0, 0.010)           # 1900Z(t-1) -> 0130Z(t) HK open
        r1b = rng.normal(0, 0.008)           # 0130Z -> 0800Z (HK session)
        r2 = rng.normal(0, 0.011)            # 0800Z -> 1900Z
        r3 = rng.normal(0, 0.004)            # 1900Z -> 2000Z (US tail)
        F0130 = F * (1 + r1a)
        F0800 = F0130 * (1 + r1b)
        F1900 = F0800 * (1 + r2)
        F2000 = F1900 * (1 + r3)
        F = F1900                             # next day's anchor
        row = {'Date': dates[t].strftime('%Y-%m-%d'),
               'hk_open': t not in hk_hol, 'us_open': t not in us_hol,
               'F0130': F0130, 'F0800': F0800, 'F1900': F1900,
               'F2000': F2000}
        rows.append(row)
    fac = pd.DataFrame(rows)
    fx0 = 7.80
    fac['fx'] = fx0 + np.cumsum(rng.normal(0, 0.002, n_days)).clip(-0.04, 0.04)
    data = {'names': {}, 'mode': 'synthetic'}
    for nm in NAMES:
        u = UNIVERSE[nm]
        beta_true = u['beta_prior'] * rng.uniform(0.9, 1.1)
        px0 = rng.uniform(40, 400)
        ords, ord_opens, adrs, ados = [], [], [], []
        level = px0
        f08 = fac['F0800'].values
        f0130 = fac['F0130'].values
        for t in range(n_days):
            # the ordinary's own close-to-close return loads on the FULL
            # 0800Z->0800Z factor move — an earlier draft used only the
            # overnight segment, which pushed the (common) intraday factor
            # move into the measured premium as non-diversifiable noise and
            # the engine correctly "traded" garbage. The self-test caught it.
            f_r = f08[t] / f08[t - 1] - 1 if t else 0.0
            idio = rng.normal(0, 0.009)
            # opening print: previous close moved by the overnight factor
            # segment plus partial idio — the engine's ord fills live here
            f_on = f0130[t] / f08[t - 1] - 1 if t else 0.0
            ord_opens.append(level * (1 + beta_true * f_on
                                      + rng.normal(0, 0.005)))
            level = level * (1 + beta_true * f_r + idio)
            # premium = structural mean + COMMON complex factor + own AR(1)
            # with occasional idio shocks (1 per ~90d, half the common size)
            shock = 0.0
            if rng.random() < 1 / 90:
                shock = rng.choice([-1, 1]) * rng.uniform(0.004, 0.008)
            prem[nm] = (prem_mean[nm] + phi * (prem[nm] - prem_mean[nm])
                        + rng.normal(0, 2.5e-4) + shock)
            prem_eff = prem[nm] + common_path[t]
            ords.append(level)
            # ADR closes at 2000Z: fair = ord projected 0800->2000 by beta
            proj = level * (1 + beta_true * (fac['F2000'].iloc[t]
                                             / fac['F0800'].iloc[t] - 1))
            # ord rich vs ADR by prem  ->  ADR price = proj/(1+prem) x ratio
            adr_px = proj / (1 + prem_eff) * u['ratio'] / fac['fx'].iloc[t]
            adrs.append(adr_px)
            ados.append(adr_px * (1 + rng.normal(0, 0.004)))
        dd = pd.DataFrame({'Date': fac['Date']})
        d = {}
        hk_ok = fac['hk_open'].values
        us_ok = fac['us_open'].values
        d['ord_close'] = dd.assign(px=ords)[['Date', 'px']][hk_ok]
        d['ord_open'] = dd.assign(px=ord_opens)[['Date', 'px']][hk_ok]
        d['adr_close'] = dd.assign(px=adrs)[['Date', 'px']][us_ok]
        d['adr_open'] = dd.assign(px=ados)[['Date', 'px']][us_ok]
        # synthetic earnings: one date per ~quarter, so the [B6] gate and
        # the auto-pull plumbing get exercised end-to-end
        qtr = list(range(30 + int(rng.integers(0, 10)), n_days, 63))
        d['earnings'] = [fac['Date'].iloc[q] for q in qtr]
        data['names'][nm] = d
    data['fx'] = fac.assign(px=fac['fx'])[['Date', 'px']]
    data['idx'] = fac.assign(px=fac['F0800'])[['Date', 'px']]
    data['idx_open'] = fac.assign(px=fac['F0130'])[['Date', 'px']]
    both = fac['hk_open'].values
    data['hti_0800'] = fac.assign(HTI_0800=fac['F0800'])[
        ['Date', 'HTI_0800']][both]
    data['hti_1900'] = fac.assign(HTI_1900=fac['F1900'])[
        ['Date', 'HTI_1900']][both]
    return data

def load_data():
    if DATA_MODE == 'synthetic':
        print("=" * 76)
        print("  SYNTHETIC DATA MODE — factor panel with planted dislocations")
        print("  [B9]. NOTHING below is a market result; this run exercises")
        print("  the engine end-to-end and self-tests the machinery.")
        print("=" * 76)
        sc('WARN', 'data', 'SYNTHETIC panel — engine self-test, not a market run')
        return load_synthetic()
    if DATA_MODE == 'bloomberg':
        return load_bloomberg()
    try:
        d = load_bloomberg()
        sc('INFO', 'data', 'Bloomberg BDH + HTI capture snaps')
        return d
    except Exception as e:
        print("=" * 76)
        print(f"  blpapi unavailable ({type(e).__name__}: {e})")
        print("  -> SYNTHETIC DATA MODE (see [B9] in the header). Set")
        print("     DATA_MODE='bloomberg' on the desk box for the real run.")
        print("=" * 76)
        sc('WARN', 'data', 'SYNTHETIC fallback — blpapi unavailable here')
        return load_synthetic()

# ============================================================================
# [B1] PANEL BUILD + CALENDAR. Master calendar = dates where the US traded,
# HK traded, and BOTH HTI snaps validated. A NAME joins a date only if its
# own four prices exist there ('live'); a date survives if >= MIN_NAMES_LIVE
# names are live. Per-name gaps DROP THE NAME, not the date — a basket book
# must not lose a month because one name halted. [QC] prints the coverage.
# ============================================================================
def build_panel(data):
    fx = data['fx'].rename(columns={'px': 'FX'})
    fx['Date'] = fx['Date'].astype(str)
    idx = data['idx'].rename(columns={'px': 'IDX_close'})
    idx['Date'] = idx['Date'].astype(str)
    idxo = data.get('idx_open')
    if idxo is not None and len(idxo):
        idxo = idxo.rename(columns={'px': 'IDX_open'})
        idxo['Date'] = idxo['Date'].astype(str)
    else:
        idxo = None
        sc('WARN', 'index open [B7]',
           'no HSTECH PX_OPEN series — the bridge-off leg marks at the '
           '16:00 snap instead of the 09:30 open (conservative but wrong '
           'clock)')
    h08 = data['hti_0800'].copy()
    h19 = data['hti_1900'].copy()
    h08['Date'] = h08['Date'].astype(str)
    h19['Date'] = h19['Date'].astype(str)
    base = pd.merge(h08, h19, on='Date', how='inner')
    base = pd.merge(base, fx, on='Date', how='inner')
    base = pd.merge(base, idx, on='Date', how='left')
    if idxo is not None:
        base = pd.merge(base, idxo, on='Date', how='left')
    bad_fx = ~base['FX'].between(*FX_SANE_BAND)
    if bad_fx.any():
        print(f"[QC] {int(bad_fx.sum())} FX prints outside the peg band "
              f"{FX_SANE_BAND} — dropped:")
        print(base.loc[bad_fx, ['Date', 'FX']].head(5).to_string(index=False))
        base = base.loc[~bad_fx]
    panel = {'base': base.sort_values('Date').reset_index(drop=True)}
    cov = []
    for nm in NAMES:
        d = data['names'][nm]
        m = None
        for key, col in (('adr_close', 'ADR_close'), ('adr_open', 'ADR_open'),
                         ('ord_close', 'ORD_close'), ('ord_open', 'ORD_open')):
            f = d[key].rename(columns={'px': col}).copy()
            f['Date'] = f['Date'].astype(str)
            f = f.drop_duplicates('Date', keep='last')
            m = f if m is None else pd.merge(m, f, on='Date', how='outer')
        m = m.sort_values('Date').reset_index(drop=True)
        panel[nm] = m
        cov.append({'name': nm,
                    'ADR rows': int(m['ADR_close'].notna().sum()),
                    'ord rows': int(m['ORD_close'].notna().sum()),
                    'both': int((m['ADR_close'].notna()
                                 & m['ORD_close'].notna()).sum())})
    show_table(pd.DataFrame(cov).set_index('name'),
               title='[QC] raw per-name coverage (rows with data)',
               fmt='{:,.0f}')
    return panel

def build_matrices(panel):
    """Wide matrices indexed by the master calendar: ords, ADRs, live mask,
    plus the base (FX + HTI snap) frame. Everything downstream is numpy on
    these — one construction, no per-block re-merging [L5]."""
    base = panel['base'].copy()
    cal = base['Date']
    mats = {}
    for col in ('ADR_close', 'ADR_open', 'ORD_close', 'ORD_open'):
        m = pd.DataFrame({'Date': cal})
        for nm in NAMES:
            f = panel[nm][['Date', col]]
            m = pd.merge(m, f.rename(columns={col: nm}), on='Date',
                         how='left')
        mats[col] = m.set_index('Date')
    live = mats['ADR_close'].notna() & mats['ORD_close'].notna()
    # a date needs BOTH markets: ords traded (ORD side) and ADRs traded
    n_live = live.sum(axis=1)
    keep = n_live >= MIN_NAMES_LIVE
    dropped = int((~keep).sum())
    if dropped:
        print(f"[QC] {dropped} dates dropped: fewer than {MIN_NAMES_LIVE} "
              f"names live (holiday mismatch or data holes)")
    base = base.set_index('Date').loc[keep.values].reset_index()
    for k in mats:
        mats[k] = mats[k].loc[keep.values]
    live = live.loc[keep.values]
    sc('INFO', 'calendar', f"{len(base)} aligned dates | median live names "
                           f"{int(live.sum(axis=1).median())} of {len(NAMES)}")
    mats['live'] = live
    mats['base'] = base
    return mats

# ============================================================================
# [B2] FAIR VALUE AND THE PREMIUM PANELS — HTI futures carry the clock in
# BOTH directions (see the [B2a] header block for the two-clock design):
#   signal clock (US close):   prem   = ADRxFX/ratio vs ord projected
#                                       08:00Z->19:00Z by beta x HTI
#   execution clock (16:00):   prem16 = ADR(t-1) projected 19:00Z->08:00Z
#                                       vs the live ord close
# ============================================================================
def rolling_beta_panel(mats):
    """[B5] Per-name rolling beta of ordinary returns on HTI 0800->0800
    returns: plain rolling-OLS cov/var over BETA_WINDOW rows, shrunk
    BETA_SHRINK_W toward the per-name prior, clamped to [BETA_MIN,
    BETA_MAX]. Shifted one day — the beta used on day t is estimated
    through t-1 (no look-ahead). Deliberately boring: the bridge holds for
    hours, so estimator robustness beats estimator cleverness."""
    # HTI series re-indexed onto the SAME Date index as the price matrices —
    # pandas aligns on index, and a stray integer index silently NaNs every
    # rolling corr/cov (found by the synthetic self-test [B9])
    hti = pd.Series(mats['base']['HTI_0800'].values,
                    index=mats['ORD_close'].index)
    hti_ret = hti.pct_change()
    betas, corrs = {}, {}
    for nm in NAMES:
        r = mats['ORD_close'][nm].pct_change()
        cov = r.rolling(BETA_WINDOW, min_periods=BETA_WINDOW // 2
                        ).cov(hti_ret)
        var = hti_ret.rolling(BETA_WINDOW, min_periods=BETA_WINDOW // 2
                              ).var()
        raw = cov / var.replace(0, np.nan)
        prior = UNIVERSE[nm]['beta_prior']
        shr = (BETA_SHRINK_W * raw + (1 - BETA_SHRINK_W) * prior
               ).fillna(prior)
        betas[nm] = shr.clip(BETA_MIN, BETA_MAX).shift(1)
        corrs[nm] = r.rolling(CORR_WINDOW,
                              min_periods=CORR_WINDOW // 2
                              ).corr(hti_ret).shift(1)
    return pd.DataFrame(betas), pd.DataFrame(corrs)

def build_premium_panel(mats, beta_df):
    """[B2a] TWO premium panels, one sign convention (ADR rich = +):
      prem    — SIGNAL clock (US close t): fresh ADR vs same-day ord
                projected 08:00Z -> 19:00Z by beta x HTI. Max ~2h stale.
      prem16  — EXECUTION clock (16:00 HKT t): ord live, ADR t-1 projected
                19:00Z(t-1) -> 08:00Z(t). ~18h-stale ADR: far noisier, so
                it CONFIRMS fills [B2b], it never originates signals."""
    base = mats['base']
    fx = base['FX'].values
    gap_us = (base['HTI_1900'] / base['HTI_0800'] - 1.0).values   # intraday
    gap_on = (base['HTI_0800'] / base['HTI_1900'].shift(1) - 1.0).values
    prem, prem16, fair = {}, {}, {}
    for nm in NAMES:
        u = UNIVERSE[nm]
        b = beta_df[nm].values
        ordc = mats['ORD_close'][nm].values
        adrc = mats['ADR_close'][nm].values
        f_us = ordc * (1.0 + b * gap_us)                 # ord fair at ~US close
        p_us = adrc * fx / u['ratio'] / f_us - 1.0
        prem[nm] = pd.Series(p_us, index=mats['ORD_close'].index)
        fair[nm] = pd.Series(f_us, index=mats['ORD_close'].index)
        adr_prev = mats['ADR_close'][nm].shift(1).values
        f16 = adr_prev * fx / u['ratio'] * (1.0 + b * gap_on)
        prem16[nm] = pd.Series(f16 / ordc - 1.0,
                               index=mats['ORD_close'].index)
    prem = pd.DataFrame(prem)
    prem16 = pd.DataFrame(prem16)
    # [B6b] manual dividend carry correction: between the HK ex-date and the
    # ADR ex-date the two prices step at different times; subtract the known
    # div from the premium inside that window. Empty lists = off (warned).
    n_div = sum(len(UNIVERSE[nm]['divs']) for nm in NAMES)
    if n_div == 0:
        sc('WARN', 'dividend carry [B6b]',
           'no manual dividend lists — ex-date premium spikes are NOT '
           'corrected; check the [QC] spike table before trusting entries '
           'near ex-dates')
    else:
        for nm in NAMES:
            for exd, hkd in UNIVERSE[nm]['divs']:
                if exd in prem.index:
                    px = mats['ORD_close'].loc[exd, nm]
                    if np.isfinite(px) and px > 0:
                        # from HK ex-date until ~the ADR ex-date (approx 1w)
                        loc = prem.index.get_loc(exd)
                        stop = min(loc + 5, len(prem))
                        rows = prem.index[loc:stop]
                        prem.loc[rows, nm] -= hkd / px
                        prem16.loc[rows, nm] -= hkd / px
    return prem, prem16, pd.DataFrame(fair)

def spike_qc(prem):
    """[QC] largest one-day premium JUMPS — ex-dates, wrong ratios and bad
    prints all look like this; eyeball before believing entries there."""
    j = prem.diff().abs()
    rows = []
    for nm in NAMES:
        s = j[nm].dropna()
        if not len(s):
            continue
        d = s.idxmax()
        rows.append({'name': nm, 'worst 1d jump (bps)': s.max() * 1e4,
                     'date': d,
                     'p99 jump (bps)': s.quantile(0.99) * 1e4})
    show_table(pd.DataFrame(rows).set_index('name'),
               title='[QC] premium jump audit — ex-dates / ratio errors '
                     'look like this',
               fmt={'worst 1d jump (bps)': '{:,.0f}',
                    'p99 jump (bps)': '{:,.0f}'})

# ============================================================================
# [B3] BASKET AGGREGATION — split in two so the [B4] N x Z grid can rebuild
# the window-dependent series cheaply while inclusion/weights stay fixed:
#   build_inclusion : who is IN each day (live + corr gate [B5c] + earnings
#                     gate [B6] + coint gate) and at what capped-ADV weight.
#   basket_series   : for a window n —
#       dev_i = prem_i - rolling_mean_n(prem_i)  (per-name structural
#           premium stripped BEFORE aggregation)
#       basket_dev = sum(w_i x dev_i)
#       basket_z   = basket_dev / rolling_sd_n(basket_prem changes...) —
#           precisely: sd of the WEIGHTED premium over the same window,
#           shifted one day. The z TIMES the entry (regime-adaptive), the
#           bps FLOOR funds it (cost-anchored) — [B4].
#       breadth = share of included names agreeing in sign with basket_dev.
# ============================================================================
def build_inclusion(mats, corr_df, coint_ok, earnings_map):
    live = mats['live']
    incl = live.copy()
    incl &= corr_df >= CORR_MIN
    if COINT_GATE == 'exclude':
        incl &= coint_ok
    # [B6] earnings block: a name inside its window is dropped from the
    # basket (weights renormalise) — dates come from the Bloomberg pull
    # (EARNINGS_SOURCE='auto'), merged with any manual UNIVERSE entries
    dates = pd.Index(mats['base']['Date'])
    n_dates_total = 0
    for nm in NAMES:
        e = earnings_map.get(nm, [])
        n_dates_total += len(e)
        if not e:
            continue
        block = np.zeros(len(dates), dtype=bool)
        for ed in e:
            loc = dates.searchsorted(str(ed)[:10])
            block[max(0, loc - EARNINGS_BLOCK_DAYS):loc + 1] = True
        incl[nm] &= ~pd.Series(block, index=incl.index)
    if n_dates_total == 0:
        sc('WARN', 'earnings gate [B6]',
           'NO earnings dates (auto-pull empty and no manual lists) — the '
           'gate is OFF; China ADRs gap hard on prints')
    else:
        sc('INFO', 'earnings gate [B6]',
           f'{n_dates_total} announcement dates across {len(NAMES)} names '
           f'({EARNINGS_SOURCE})')
    w_raw = pd.Series({nm: UNIVERSE[nm]['adv_usd'] for nm in NAMES})
    w_capped = np.minimum(w_raw / w_raw.sum(), W_CAP)
    W = pd.DataFrame(np.tile(w_capped.values, (len(incl), 1)),
                     index=incl.index, columns=NAMES)
    W = W.where(incl, 0.0)
    W = W.div(W.sum(axis=1).replace(0, np.nan), axis=0)
    return W

def basket_series(prem, prem16, W, n):
    """Window-dependent basket series for z window n (see [B3] header)."""
    Wd = W.where(prem.notna(), 0.0)
    Wd = Wd.div(Wd.sum(axis=1).replace(0, np.nan), axis=0)
    dev = prem - prem.rolling(n).mean().shift(1)
    dev16 = prem16 - prem16.rolling(n).mean().shift(1)
    basket_dev = (Wd * dev).sum(axis=1, min_count=1)
    basket_dev16 = (Wd * dev16).sum(axis=1, min_count=1)
    # weighted RAW premium — the drift gate runs on THIS series' rolling
    # mean (basket_dev's own mean is ~0 by construction, a null test), and
    # its rolling sd is the z denominator
    basket_prem = (Wd * prem).sum(axis=1, min_count=1)
    sd = basket_prem.rolling(n).std(ddof=0).shift(1).replace(0, np.nan)
    basket_z = basket_dev / sd
    n_incl = (Wd > 0).sum(axis=1)
    agree = ((np.sign(dev) == np.sign(basket_dev.values[:, None]))
             & (Wd > 0)).sum(axis=1)
    breadth = agree / n_incl.replace(0, np.nan)
    return pd.DataFrame({'basket_dev': basket_dev,
                         'basket_dev16': basket_dev16,
                         'basket_prem': basket_prem, 'basket_z': basket_z,
                         'n_incl': n_incl, 'breadth': breadth}), dev, Wd

# ============================================================================
# [B5d] COINTEGRATION DIAGNOSTIC (Engle-Granger per name): log(ADR x FX /
# ratio) vs log(ord) over COINT_WINDOW; the residual's ADF p-value and
# implied half-life. The ADS conversion mechanism SHOULD make every name
# pass; a failure flags a broken ratio, a conversion-window change, or a
# genuinely re-rating listing — exclude it (COINT_GATE) or investigate.
# ============================================================================
def coint_table(mats):
    base = mats['base']
    fx = base['FX'].values
    ok = {}
    rows = []
    for nm in NAMES:
        u = UNIVERSE[nm]
        a = np.log(mats['ADR_close'][nm].values * fx / u['ratio'])
        o = np.log(mats['ORD_close'][nm].values)
        n = len(a)
        pass_ser = np.full(n, True)
        p_last, hl_last, b_last = np.nan, np.nan, np.nan
        m = np.isfinite(a) & np.isfinite(o)
        if m.sum() >= COINT_WINDOW:
            aw = a[m][-COINT_WINDOW:]
            ow = o[m][-COINT_WINDOW:]
            X = np.column_stack([np.ones(len(ow)), ow])
            bhat, *_ = np.linalg.lstsq(X, aw, rcond=None)
            resid = aw - X @ bhat
            b_last = bhat[1]
            if _HAVE_SM:
                try:
                    p_last = adfuller(resid, maxlag=int(len(resid) ** 0.4)
                                      )[1]
                except Exception:
                    p_last = np.nan
            d = np.diff(resid)
            lag = resid[:-1] - resid[:-1].mean()
            den = np.dot(lag, lag)
            g = np.dot(d, lag) / den if den > 0 else 0.0
            hl_last = (np.log(0.5) / np.log(1 + max(g, -0.999))
                       if g < 0 else np.inf)
            if np.isfinite(p_last):
                pass_ser[:] = p_last <= COINT_PMAX
        ok[nm] = pd.Series(pass_ser, index=mats['ADR_close'].index)
        rows.append({'name': nm, 'EG slope (log-log)': b_last,
                     'resid ADF p': p_last, 'resid half-life (d)':
                         min(hl_last, 999) if np.isfinite(hl_last) else np.nan,
                     'verdict': ('n/a (statsmodels absent)' if not _HAVE_SM
                                 else 'PASS' if (np.isfinite(p_last)
                                                 and p_last <= COINT_PMAX)
                                 else 'CHECK')})
    show_table(pd.DataFrame(rows).set_index('name'),
               title=f'[B5d] per-name cointegration (Engle-Granger, last '
                     f'{COINT_WINDOW} aligned days)',
               note='The conversion mechanism should make every name PASS '
                    'with slope ~1. A CHECK is a broken ratio, a halted '
                    'line, or a genuine re-rating — investigate before '
                    'letting it into the basket. COINT_GATE=' + COINT_GATE,
               fmt={'EG slope (log-log)': '{:+.3f}', 'resid ADF p': '{:.3f}',
                    'resid half-life (d)': '{:,.1f}'})
    return pd.DataFrame(ok)

# ============================================================================
# [B6] REGIME GATE on the BASKET deviation series — one builder, used by the
# engine AND every audit [L5]. gamma = AR(1) slope of daily changes on the
# de-trended series; gate ON iff gamma < 0 and implied half-life <=
# HL_MAX_DAYS, plus the 5-day mean-shift drift test at DRIFT_MAX_SIGMA.
# ============================================================================
_STATS_CACHE = {}
def gate_series(basket_dev):
    """The series the gate statistics run on (de-trended deviation)."""
    s = basket_dev
    return (s - s.rolling(ADF_DETREND_N).mean().shift(1)).fillna(0.0)

def signal_stats(series_values):
    key = series_values.tobytes()
    if key in _STATS_CACHE:
        return _STATS_CACHE[key]
    n = len(series_values)
    adf_p = np.full(n, np.nan)
    gamma = np.full(n, np.nan)
    for t in range(GATE_WINDOW, n):
        w = series_values[t - GATE_WINDOW:t]
        if _HAVE_SM and GATE_MODE == 'adf_deviation':
            try:
                adf_p[t] = adfuller(w, maxlag=int(np.sqrt(GATE_WINDOW)))[1]
            except Exception:
                adf_p[t] = 1.0
        d = w - w.mean()
        lag = d[:-1]
        delta = np.diff(w)
        den = np.dot(lag, lag)
        gamma[t] = np.dot(delta, lag) / den if den > 0 else 0.0
    out = (adf_p, gamma)          # TUPLE — unpack it, never index by name
    _STATS_CACHE[key] = out
    return out

def gate_state(basket, t, gamma, adf_p, drift):
    """One verdict function for engine and audits: (on?, reason-if-shut)."""
    if GATE_MODE == 'off':
        return True, ''
    if GATE_MODE == 'adf_deviation':
        p = adf_p[t]
        if not np.isfinite(p):
            return False, 'no ADF yet'
        return (p < ADF_PVALUE), f'ADF p {p:.2f} >= {ADF_PVALUE}'
    g = gamma[t]
    if not np.isfinite(g):
        return False, 'no gamma yet (warm-up)'
    if g >= 0:
        return False, f'gamma {g:+.3f} >= 0 (no reversion)'
    hl = np.log(0.5) / np.log(1.0 + max(g, -0.999))
    if hl > HL_MAX_DAYS:
        return False, f'half-life {hl:.1f}d > {HL_MAX_DAYS:.0f}d'
    dr = drift[t]
    if np.isfinite(dr) and dr > DRIFT_MAX_SIGMA:
        return False, f'drift {dr:.2f} > {DRIFT_MAX_SIGMA:.2f} (repricing)'
    return True, ''

# ============================================================================
# [B8] COST MODEL — charged leg by leg on each leg's own notional.
#   ADR side (per crossing): fee + close half-spread.
#   Ord side (per crossing): stamp + levies + OPENING-auction half-spread
#       + FX on the HKD flows.
#   Bridge (hti_close timing only, per overnight window): futures fees both
#       ways + the 19:00Z T+1-tail half-spread in + the day-open half-spread
#       out, on bridge-ratio x notional. us_close timing has NO bridge.
# Borrow accrues daily on whichever leg is short; funding on the long leg.
# NOTE [B10]: the depositary-conversion exit (deliver ords into ADS
# creation / cancel ADSs) would cap the exit at conv_exit_cost_bps() —
# roughly 12 bps vs ~25 for a screen exit — but the user's desk does not
# use the channel, so the ENGINE never books it; the [B8] header line only
# REPORTS what the channel would be worth.
# ============================================================================
def adr_side_cost_bps():
    return ADR_FEE_BPS + ADR_HALF_SPREAD_BPS

def ord_side_cost_bps():
    return (ORD_STAMP_BPS + ORD_LEVIES_BPS + ORD_HALF_SPREAD_BPS
            + 2 * FX_HALF_SPREAD_BPS)

def bridge_window_cost_bps(timing=None):
    if (EXEC_TIMING if timing is None else timing) != 'hti_close':
        return 0.0
    return (2 * FUT_FEE_BPS + FUT_HALF_SPREAD_BPS
            + FUT_HALF_SPREAD_DAY_BPS) * 0.8    # ~avg bridge ratio ex ante

def entry_side_cost_bps(timing=None):
    """One side of the round trip (the entry, or the mirror-image exit)."""
    return (adr_side_cost_bps() + ord_side_cost_bps()
            + bridge_window_cost_bps(timing))

def conv_exit_cost_bps(adr_px_typ=100.0):
    """[B10] REFERENCE ONLY (see the cost-model note): what a depositary-
    conversion exit would cost. Per-ADS cash fees are huge in bps for
    low-priced ADRs — the [X2] lesson."""
    fee_bps = CONV_FEE_USD_PER_ADS / max(adr_px_typ, 1e-9) * 1e4
    return fee_bps + CONV_SLIP_BPS + 2 * FX_HALF_SPREAD_BPS

def package_rt_cost_bps(timing=None):
    """Ex-ante round trip in bps of package notional (screen both ways)."""
    return 2 * entry_side_cost_bps(timing)

def dev_floor_bps():
    """[B4] the cost-anchored deviation floor: 'auto' derives it from the
    live cost model (so it moves when fees/spreads/timing move); 'manual'
    is the user's original +55/-60 pair. Returns (short_floor, long_floor),
    short positive, long negative."""
    if DEV_FLOOR_MODE == 'manual':
        return float(DEV_FLOOR_SHORT_BPS), float(DEV_FLOOR_LONG_BPS)
    f = package_rt_cost_bps() * MIN_EDGE_HARD
    return f, -f

# ============================================================================
# [B7] THE ENGINE — the [B2a] timeline, ADR side first. One package position
# at a time; legs frozen at the entry signal (that day's names/weights).
#   entry signal day e (US close): z + floor + gates pass ->
#       ADR legs fill at ADR_close(e); hti_close: bridge on at HTI_1900(e).
#   e+1 HK open: ord legs fill at ORD_open(e+1); bridge off at IDX_open(e+1)
#       — pair locked by 09:30 HKT, BEFORE the pre-US-open earnings slot.
#   exit signal day x (US close): z crossed EXIT_Z / time stop / gate shut ->
#       ADR legs unwind at ADR_close(x); hti_close: bridge on at HTI_1900(x)
#       covering the now-one-legged ord side overnight.
#   x+1 HK open: ord legs unwind at ORD_open(x+1); bridge off; trade booked.
# us_close timing: identical fills, NO bridge — each one-legged window
# rides naked ~5h and the overnight gap lands in the REAL fills, so it is
# IN the PnL, not assumed away. The [B2a] robustness table compares the two
# timings on identical signals.
# PnL is two_leg ONLY [L2]. Daily marks: ord legs at ORD_close, ADR legs at
# ADR_close, at the day's FX — real basis moves show in the marks.
# ============================================================================
def run_basket_backtest(mats, basket, W, beta_df, z_short=None, z_long=None,
                        cost_mult=1.0, collect_audit=False,
                        exec_timing=None):
    z_short = Z_ENTRY_SHORT if z_short is None else z_short
    z_long = Z_ENTRY_LONG if z_long is None else z_long
    timing = EXEC_TIMING if exec_timing is None else exec_timing
    bridged = (timing == 'hti_close')
    base = mats['base']
    dates = base['Date'].values
    dts = pd.to_datetime(base['Date'])
    gap_next = np.r_[np.diff(dts.values) / np.timedelta64(1, 'D'), 999.0]
    fx = base['FX'].values
    h19 = base['HTI_1900'].values
    idxo = (base['IDX_open'].values if 'IDX_open' in base.columns
            else np.full(len(base), np.nan))
    idxo = np.where(np.isfinite(idxo), idxo, base['HTI_0800'].values)
    bd = basket['basket_dev'].values
    bz = basket['basket_z'].values
    breadth = basket['breadth'].values
    n_incl = basket['n_incl'].values
    ord_open_px = mats['ORD_open'].values
    ord_close_px = mats['ORD_close'].values
    adr_px = mats['ADR_close'].values
    Wv = W.values
    prior_arr = np.array([UNIVERSE[nm]['beta_prior'] for nm in NAMES])
    lot_arr = np.array([float(UNIVERSE[nm]['lot']) for nm in NAMES])
    ratio_arr = np.array([UNIVERSE[nm]['ratio'] for nm in NAMES])
    borrow_arr = np.array([float(UNIVERSE[nm]['borrow_bps'])
                           for nm in NAMES])
    n = len(dates)
    gs = gate_series(basket['basket_dev']).values
    adf_p, gamma = signal_stats(gs)
    # [Z3]-faithful drift gate: the RAW premium's rolling-mean repricing in
    # trend-free daily-change sigmas (basket_dev's own mean is ~0 by
    # construction — running drift there is a null test)
    _bp = basket['basket_prem']
    mu5 = _bp.rolling(N_WINDOW).mean().shift(1)
    chg_sd = _bp.diff().rolling(N_WINDOW).std(ddof=0).shift(1)
    drift = ((mu5 - mu5.shift(5)).abs() / (chg_sd * np.sqrt(5.0))).values
    floor_s, floor_l = dev_floor_bps()

    # state 0 flat | 1 ADR+bridge on, ords fill THIS row's open | 2 full |
    # 3 ADRs unwound, ords lift THIS row's open
    state, pos = 0, 0
    equity = np.zeros(n)
    realized = 0.0
    trades, audit = [], []
    leg_ord_sh = leg_adr_sh = leg_w = None
    e_sig = x_sig = -1
    entry_dev = entry_z = exit_dev = 0.0
    pkg_notional = 0.0
    trade_costs = 0.0
    adr_entry_val = ord_entry_val = 0.0
    bridge_pnl = 0.0
    br_used = 0.0
    exit_why = ''

    def bridge_ratio(sig_t):
        if not bridged:
            return 0.0
        if HEDGE_RATIO_MODE == 'beta_one':
            return 1.0
        if HEDGE_RATIO_MODE == 'ols':
            b = np.nansum(Wv[sig_t] * beta_df.values[sig_t])
        else:                                   # 'static_prior' (default)
            b = np.nansum(Wv[sig_t] * prior_arr)
        return float(np.clip(b if np.isfinite(b) else 0.8,
                             BETA_MIN, BETA_MAX))

    def bridge_leg_cost():
        if not bridged or br_used <= 0:
            return 0.0
        return (pkg_notional * br_used
                * (2 * FUT_FEE_BPS + FUT_HALF_SPREAD_BPS
                   + FUT_HALF_SPREAD_DAY_BPS) / 1e4 * cost_mult)

    def carry_usd(upto_t):
        days = max((dts[upto_t] - dts[e_sig]).days, 0)
        side = (np.nansum(borrow_arr * np.maximum(leg_w, 0))
                if pos == +1 else ADR_BORROW_ANN_BPS)
        return (-pkg_notional * (FUNDING_ANN_BPS + side) / 1e4 / 365 * days)

    def mark(t, ord_on):
        m = np.nansum(leg_adr_sh * adr_px[t]) - adr_entry_val
        if ord_on:
            m += (np.nansum(leg_ord_sh * ord_close_px[t] / fx[t])
                  - ord_entry_val)
        return m + bridge_pnl + carry_usd(t)

    def book(t, ord_exit_val, why):
        nonlocal state, pos, realized, bridge_pnl
        adr_pnl = np.nansum(leg_adr_sh * adr_px[x_sig]) - adr_entry_val
        ord_pnl = ord_exit_val - ord_entry_val
        carry = carry_usd(t)
        net = adr_pnl + ord_pnl + bridge_pnl + carry - trade_costs
        realized += net
        trades.append({
            'entry_day': e_sig, 'exit_day': t,
            'entry_date': dates[e_sig], 'exit_date': dates[t],
            'dir': 'SHORT pkg' if pos == -1 else 'LONG pkg',
            'entry_dev_bps': entry_dev, 'entry_z': entry_z,
            'exit_dev_bps': exit_dev,
            'hold_d': (dts[t] - dts[e_sig]).days,
            'notional': pkg_notional,
            'ord_pnl': ord_pnl, 'adr_pnl': adr_pnl,
            'bridge_pnl': bridge_pnl, 'carry': carry,
            'costs': trade_costs, 'net_after_all': net,
            'exit_reason': why,
            # [L2] convergence DIAGNOSTIC only, never the headline
            'conv_pnl_diag': pos * (exit_dev - entry_dev) / 1e4
                             * pkg_notional,
            'n_legs': int((np.abs(leg_adr_sh) > 0).sum()),
        })
        state, pos = 0, 0
        bridge_pnl = 0.0
        equity[t] = realized

    for t in range(N_WINDOW + 1, n):
        d_bps = bd[t] * 1e4 if np.isfinite(bd[t]) else np.nan
        z_t = bz[t] if np.isfinite(bz[t]) else np.nan

        # ---- state 1: ord legs fill at THIS row's opening auction ----
        if state == 1:
            for i in range(len(NAMES)):
                if leg_ord_sh[i] != 0 and not np.isfinite(ord_open_px[t, i]):
                    leg_ord_sh[i] = 0     # halted at the open: leg dropped
                    leg_adr_sh[i] = 0     # its ADR twin is scratched below
            if bridged:
                bridge_pnl += ((-pos) * br_used * pkg_notional
                               * (idxo[t] / h19[e_sig] - 1.0))
            if not np.any(leg_ord_sh):
                # nothing fillable: scratch — ADRs back out at tonight's
                # close; only ADR + bridge costs were and are paid
                x_sig = t
                exit_dev = d_bps
                trade_costs += (pkg_notional * adr_side_cost_bps() / 1e4
                                * cost_mult)
                ord_entry_val = 0.0
                book(t, 0.0, 'scratched: no fillable ord legs')
                continue
            ord_entry_val = np.nansum(leg_ord_sh * ord_open_px[t] / fx[t])
            trade_costs += (pkg_notional * ord_side_cost_bps() / 1e4
                            * cost_mult)
            state = 2
            equity[t] = realized + mark(t, True) - trade_costs
            continue

        # ---- state 3: ord legs lift at THIS row's open; trade books ----
        if state == 3:
            ord_exit_val = 0.0
            for i in range(len(NAMES)):
                if leg_ord_sh[i] == 0:
                    continue
                px = ord_open_px[t, i]
                if not np.isfinite(px):
                    px = ord_close_px[t, i]   # halted open: close instead
                ord_exit_val += leg_ord_sh[i] * px / fx[t]
            if bridged:
                bridge_pnl += (pos * br_used * pkg_notional
                               * (idxo[t] / h19[x_sig] - 1.0))
            trade_costs += (pkg_notional * ord_side_cost_bps() / 1e4
                            * cost_mult)
            book(t, ord_exit_val, exit_why)
            continue

        # ---- state 2: full package — mark, and watch for an exit ----
        if state == 2:
            held = (dts[t] - dts[e_sig]).days
            why = ''
            if np.isfinite(z_t) and ((pos == -1 and z_t <= EXIT_Z)
                                     or (pos == +1 and z_t >= EXIT_Z)):
                why = 'z crossed exit'
            elif held >= TIME_STOP:
                why = f'time stop {TIME_STOP}d'
            else:
                on, greason = gate_state(basket, t, gamma, adf_p, drift)
                if not on and 'warm-up' not in greason:
                    why = f'gate shut ({greason})'
            if why:
                if t + 1 < n:
                    x_sig = t
                    exit_dev = d_bps
                    exit_why = why
                    trade_costs += (pkg_notional * adr_side_cost_bps()
                                    / 1e4 * cost_mult)
                    if bridged:
                        br_used = bridge_ratio(t)
                        trade_costs += bridge_leg_cost()
                    state = 3
                    equity[t] = realized + mark(t, True) - trade_costs
                    continue
                # last row: full unwind at today's closes
                x_sig = t
                exit_dev = d_bps
                trade_costs += (pkg_notional * (adr_side_cost_bps()
                                + ord_side_cost_bps()) / 1e4 * cost_mult)
                book(t, np.nansum(leg_ord_sh * ord_close_px[t] / fx[t]),
                     why + ' (end of data)')
                continue
            equity[t] = realized + mark(t, True) - trade_costs
            continue

        # ---- state 0: flat — look for an entry signal (tonight's close)
        want = 0
        if np.isfinite(z_t):
            if z_t >= z_short:
                want = -1
            elif z_t <= -z_long:
                want = +1
        if want and DIRECTION_FILTER == 'long_only' and want == -1:
            want = 0
        if want and DIRECTION_FILTER == 'short_only' and want == +1:
            want = 0
        reason = ''
        if want:
            on, reason = gate_state(basket, t, gamma, adf_p, drift)
            if not on:
                want = 0
            elif not (np.isfinite(breadth[t]) and breadth[t] >= BREADTH_MIN):
                want, reason = 0, (f'breadth {breadth[t]:.0%} < '
                                   f'{BREADTH_MIN:.0%}')
            elif n_incl[t] < MIN_NAMES_LIVE:
                want, reason = 0, f'only {int(n_incl[t])} names live'
            elif t + 1 >= n or gap_next[t] > MAX_ENTRY_GAP_DAYS:
                want, reason = 0, 'no next session inside the gap limit'
            elif not np.isfinite(d_bps) or (want == -1 and d_bps < floor_s) \
                    or (want == +1 and d_bps > floor_l):
                want, reason = 0, (f'[B4] dev floor: dev inside '
                                   f'+{floor_s:.0f}/{floor_l:.0f} bps '
                                   f'({DEV_FLOOR_MODE})')
        if collect_audit and np.isfinite(z_t) and (z_t >= z_short
                                                   or z_t <= -z_long):
            audit.append({'date': dates[t], 'dev_bps': d_bps, 'z': z_t,
                          'action': 'ENTER' if want else 'blocked',
                          'why': reason})
        if want:
            thr = z_short if want == -1 else z_long
            size = (min(abs(z_t) / thr, SIZE_CAP)
                    if SIZING_MODE == 'z_scaled' else 1.0)
            pkg_notional = NOTIONAL_BASKET * size
            leg_w = Wv[t].copy()
            leg_ord_sh = np.zeros(len(NAMES))
            leg_adr_sh = np.zeros(len(NAMES))
            for i in range(len(NAMES)):
                if leg_w[i] <= 0:
                    continue
                ocx = ord_close_px[t, i]     # sizing proxy (fills at open)
                acx = adr_px[t, i]
                if not (np.isfinite(ocx) and np.isfinite(acx)):
                    leg_w[i] = 0.0
                    continue
                usd_i = pkg_notional * leg_w[i]
                sh_o = math.floor(usd_i * fx[t] / ocx / lot_arr[i]
                                  ) * lot_arr[i]
                sh_a = round(sh_o / ratio_arr[i])
                # +1 package = long ADR / short ord
                leg_ord_sh[i] = -want * sh_o
                leg_adr_sh[i] = want * sh_a
            if not np.any(leg_adr_sh):
                if collect_audit:
                    audit.append({'date': dates[t], 'dev_bps': d_bps,
                                  'z': z_t, 'action': 'blocked',
                                  'why': 'no fillable legs'})
                equity[t] = realized
                continue
            pos = want
            e_sig = t
            entry_dev, entry_z = d_bps, z_t
            br_used = bridge_ratio(t)
            adr_entry_val = np.nansum(leg_adr_sh * adr_px[t])
            ord_entry_val = 0.0
            bridge_pnl = 0.0
            trade_costs = (pkg_notional * adr_side_cost_bps() / 1e4
                           * cost_mult) + bridge_leg_cost()
            state = 1
            equity[t] = realized + mark(t, False) - trade_costs
            continue
        equity[t] = realized

    # data ended mid-trade: force the remaining legs out at the last closes
    if state in (1, 2, 3):
        t_last = n - 1
        if state != 3:
            x_sig = t_last
            trade_costs += (pkg_notional * adr_side_cost_bps() / 1e4
                            * cost_mult)
        exit_dev = bd[t_last] * 1e4 if np.isfinite(bd[t_last]) else np.nan
        if state == 1:
            leg_ord_sh = np.zeros(len(NAMES))
            ord_entry_val = 0.0
            ord_exit_val = 0.0
        else:
            trade_costs += (pkg_notional * ord_side_cost_bps() / 1e4
                            * cost_mult)
            ord_exit_val = np.nansum(leg_ord_sh * ord_close_px[t_last]
                                     / fx[t_last])
        book(t_last, ord_exit_val,
             (exit_why + ' ' if state == 3 else '') + '(end of data)')
    eq = pd.Series(equity, index=base['Date'])
    res = summarize(trades, eq)
    res['trades'] = trades
    res['equity'] = eq
    res['audit'] = audit
    return res

def summarize(trades, eq):
    out = {'n_trades': len(trades)}
    if not trades:
        out.update({'net': 0.0, 'win_rate': np.nan, 'sharpe': np.nan,
                    'max_dd': 0.0, 'avg_hold': np.nan, 'tstat': np.nan})
        return out
    nets = np.array([t['net_after_all'] for t in trades])
    out['net'] = float(nets.sum())
    out['win_rate'] = float((nets > 0).mean() * 100)
    out['avg_hold'] = float(np.mean([t['hold_d'] for t in trades]))
    d = eq.diff().dropna()
    d = d[d != 0]
    out['sharpe'] = (float(d.mean() / d.std() * np.sqrt(252))
                     if len(d) > 10 and d.std() > 0 else np.nan)
    peak = eq.cummax()
    out['max_dd'] = float((eq - peak).min())
    out['tstat'] = (float(nets.mean() / nets.std() * np.sqrt(len(nets)))
                    if len(nets) > 2 and nets.std() > 0 else np.nan)
    return out

# ============================================================================
# MAIN RUN
# ============================================================================
def main():
    t_start = datetime.now()
    print("=" * 76)
    print("  v33 HK ADR BASKET BOOK — HS Tech pairs, HTI overnight bridge")
    print(f"  entry: basket z >= +{Z_ENTRY_SHORT:.2f} -> SHORT package | "
          f"z <= -{Z_ENTRY_LONG:.2f} -> LONG package (N={N_WINDOW})")
    print(f"  timing: {EXEC_TIMING} | hedge ratio: {HEDGE_RATIO_MODE} | "
          f"basket US${NOTIONAL_BASKET:,.0f} | {len(NAMES)} names")
    print("=" * 76)

    data = load_data()
    panel = build_panel(data)
    mats = build_matrices(panel)
    beta_df, corr_df = rolling_beta_panel(mats)
    prem, prem16, fair = build_premium_panel(mats, beta_df)
    spike_qc(prem)
    coint_ok = coint_table(mats)
    earnings_map = {nm: data['names'][nm].get('earnings',
                                              UNIVERSE[nm]['earnings'])
                    for nm in NAMES}
    W = build_inclusion(mats, corr_df, coint_ok, earnings_map)
    basket, dev, Wd = basket_series(prem, prem16, W, N_WINDOW)

    # ---- per-name snapshot: the basket today ----
    rows = []
    prior_arr = {nm: UNIVERSE[nm]['beta_prior'] for nm in NAMES}
    for nm in NAMES:
        u = UNIVERSE[nm]
        rows.append({
            'name': f"{_short(u['adr'])} / {_short(u['ord'])}",
            'ratio': u['ratio'],
            'beta prior': prior_arr[nm],
            'beta (rolling)': beta_df[nm].iloc[-1],
            'corr vs HTI': corr_df[nm].iloc[-1],
            'weight': Wd.iloc[-1][nm],
            'struct prem (bps)': prem[nm].rolling(N_WINDOW).mean().iloc[-1]
                                 * 1e4,
            'dev today (bps)': dev[nm].iloc[-1] * 1e4,
        })
    show_table(pd.DataFrame(rows).set_index('name'),
               title=f'[B0] the basket today — weights, betas, deviations '
                     f'(N={N_WINDOW}) | basket z {basket["basket_z"].iloc[-1]:+.2f}',
               note='dev = premium minus the name\'s own rolling mean: '
                    'positive = the ADR side rich vs the HK line. [B5] the '
                    'bridge is sized off the static PRIORS by default — the '
                    'rolling column exists so a drifted prior is VISIBLE '
                    '(update the UNIVERSE number when they diverge), not '
                    'because the engine needs it.',
               fmt={'ratio': '{:.0f}', 'beta prior': '{:.2f}',
                    'beta (rolling)': '{:.2f}', 'corr vs HTI': '{:.2f}',
                    'weight': '{:.1%}', 'struct prem (bps)': '{:+,.0f}',
                    'dev today (bps)': '{:+,.0f}'})

    # ---- cost stack vs the deviation floor ([S1] lesson) ----
    rt = package_rt_cost_bps()
    floor_s, floor_l = dev_floor_bps()
    adv = rt * MIN_EDGE_ADVISORY
    lvl = 'INFO' if min(floor_s, abs(floor_l)) >= adv else 'WARN'
    sc(lvl, 'dev floor vs costs [S1]',
       f"RT ~{rt:.0f} bps ({EXEC_TIMING}) | floor +{floor_s:.0f}/"
       f"{floor_l:.0f} ({DEV_FLOOR_MODE}) | advisory {adv:.0f}")
    print(f"\n[B8] package costs, bps of notional, per side: ADRs "
          f"{adr_side_cost_bps():.0f} + ords {ord_side_cost_bps():.0f} "
          f"(stamp {ORD_STAMP_BPS:.0f} is the big one) + bridge "
          f"{bridge_window_cost_bps():.0f} = {entry_side_cost_bps():.0f} "
          f"-> round trip ~{rt:.0f}")
    print(f"      [B4] deviation floor ({DEV_FLOOR_MODE}): entries need "
          f"dev >= +{floor_s:.0f} / <= {floor_l:.0f} bps ON TOP of the z "
          f"threshold | advisory x{MIN_EDGE_ADVISORY} = {adv:.0f} bps")
    print(f"      [B10] reference: a depositary-conversion exit would cost "
          f"~{conv_exit_cost_bps():.0f} bps vs {entry_side_cost_bps():.0f} "
          f"screen — worth revisiting if the desk ever gets the channel")

    # ---- [TZ1] does tonight's signal survive to tomorrow's ord fill? ----
    both = pd.DataFrame({'sig': basket['basket_dev'] * 1e4,
                         'fill': basket['basket_dev16'].shift(-1) * 1e4
                         }).dropna()
    if len(both) > 50:
        bins = [-1e9, floor_l, -25, 25, floor_s, 1e9]
        labs = [f'<= {floor_l:.0f}', f'({floor_l:.0f},-25]', '(-25,+25)',
                f'[+25,+{floor_s:.0f})', f'>= +{floor_s:.0f}']
        both['bucket'] = pd.cut(both['sig'], bins=bins, labels=labs)
        tz = both.groupby('bucket', observed=False).agg(
            days=('fill', 'size'), mean_next_16h=('fill', 'mean'),
            median=('fill', 'median'))
        show_table(tz, title='[TZ1] US-close signal dev vs the 16:00-HKT '
                             're-measure NEXT day (bps)',
                   note='The time-zone claim, quantified: a night-time '
                        'dislocation must still be there through the next '
                        'HK session for the ord side to have entered at '
                        'sensible levels. If the outer rows collapse toward '
                        'zero, the opening fills are giving the edge back.',
                   fmt={'days': '{:,.0f}', 'mean_next_16h': '{:+,.0f}',
                        'median': '{:+,.0f}'})

    # ---- base run at the configured cell ----
    res = run_basket_backtest(mats, basket, Wd, beta_df, collect_audit=True)
    print(f"\n{'=' * 76}")
    print(f"  BASE RUN — N={N_WINDOW}, z +{Z_ENTRY_SHORT:.2f}/"
          f"-{Z_ENTRY_LONG:.2f}, floor +{floor_s:.0f}/{floor_l:.0f} bps, "
          f"exit z={EXIT_Z:.1f}, stop {TIME_STOP}d, {EXEC_TIMING}")
    print(f"{'=' * 76}")
    if res['n_trades']:
        print(f"  trades {res['n_trades']} | net ${res['net']:,.0f} | win "
              f"{res['win_rate']:.1f}% | Sharpe {res['sharpe']:.2f} | "
              f"t-stat {res['tstat']:.2f} | maxDD ${res['max_dd']:,.0f} | "
              f"avg hold {res['avg_hold']:.1f}d")
    else:
        print("  NO TRADES — see the entry audit below")

    if res['trades']:
        tr = pd.DataFrame(res['trades'])
        show = tr[['entry_date', 'exit_date', 'dir', 'entry_z',
                   'entry_dev_bps', 'exit_dev_bps', 'hold_d', 'n_legs',
                   'ord_pnl', 'adr_pnl', 'bridge_pnl', 'carry', 'costs',
                   'net_after_all', 'exit_reason']].copy()
        show.columns = ['entry', 'exit', 'dir', 'z in', 'in dev', 'out dev',
                        'days', 'legs', 'ord PnL', 'ADR PnL', 'bridge',
                        'carry', 'costs', 'NET', 'exit why']
        show_table(show.tail(20).set_index('entry'),
                   title='[B7] last 20 package trades — leg-by-leg [L2]',
                   note='entry = the night the ADR legs went on (with the '
                        'bridge under hti_close); the ords locked the pair '
                        'at the NEXT HK open; exit = the morning the ords '
                        'came off.',
                   fmt={'z in': '{:+.2f}', 'in dev': '{:+,.0f}',
                        'out dev': '{:+,.0f}', 'days': '{:,.0f}',
                        'legs': '{:,.0f}', 'ord PnL': '{:+,.0f}',
                        'ADR PnL': '{:+,.0f}', 'bridge': '{:+,.0f}',
                        'carry': '{:+,.0f}', 'costs': '{:,.0f}',
                        'NET': '{:+,.0f}'})
        conv = tr['conv_pnl_diag'].sum()
        two = (tr['net_after_all'].sum() + tr['costs'].sum()
               - tr['carry'].sum())
        print(f"\n[L2] reconciliation: two_leg GROSS ${two:,.0f} vs "
              f"convergence diagnostic ${conv:,.0f} — the difference is "
              f"basis (bridge residual + overnight windows + FX), NOT a "
              f"mystery. Costs ${tr['costs'].sum():,.0f} and carry "
              f"${tr['carry'].sum():+,.0f} take the net to "
              f"${tr['net_after_all'].sum():,.0f}.")
        er = tr.groupby('exit_reason')['net_after_all'].agg(['size', 'sum',
                                                             'mean'])
        er.columns = ['n', 'net $', 'avg $']
        show_table(er, title='exit-reason tally',
                   fmt={'n': '{:,.0f}', 'net $': '{:+,.0f}',
                        'avg $': '{:+,.0f}'})

    if res['audit']:
        au = pd.DataFrame(res['audit'])
        blocked = au[au['action'] == 'blocked']
        if len(blocked):
            show_table(blocked['why'].value_counts().to_frame('days'),
                       title='[B6] z-crossing days BLOCKED by a gate, '
                             'tallied',
                       note='Every day here cleared the z threshold. A '
                            'dominant single reason deserves an eyeball: '
                            'gates exist to refuse REGIME moves, not to '
                            'strangle the strategy.',
                       fmt='{:,.0f}')

    # ---- [B4] the house N x Z grid (dev floor always on) ----
    print(f"\n[B4] N x Z sweep, net $ (configured cell N={N_WINDOW}, "
          f"Z={Z_ENTRY_SHORT})")
    grid_net = pd.DataFrame(index=[f"N={n_}" for n_ in N_GRID],
                            columns=[f"Z={z_}" for z_ in Z_GRID],
                            dtype=float)
    grid_tr = grid_net.copy()
    for n_ in N_GRID:
        bkN, devN, WdN = basket_series(prem, prem16, W, n_)
        for z_ in Z_GRID:
            r = run_basket_backtest(mats, bkN, WdN, beta_df,
                                    z_short=z_, z_long=z_)
            grid_net.loc[f"N={n_}", f"Z={z_}"] = r['net']
            grid_tr.loc[f"N={n_}", f"Z={z_}"] = r['n_trades']
    show_table(grid_net, title='net PnL by (N window, Z entry) — dev floor '
                               f'+{floor_s:.0f}/{floor_l:.0f} bps applies '
                               'in every cell',
               fmt='{:,.0f}')
    show_table(grid_tr, title='trade count by cell', fmt='{:,.0f}')

    # ---- robustness: timing, hedge-ratio mode, costs, drop-one, halves --
    rows = []
    for tm in ('hti_close', 'us_close'):
        r = run_basket_backtest(mats, basket, Wd, beta_df, exec_timing=tm)
        rows.append({'variant': f'timing {tm}', 'trades': r['n_trades'],
                     'net $': r['net'], 'win %': r['win_rate'],
                     'Sharpe': r['sharpe']})
    for cm in (0.5, 1.5, 2.0):
        r = run_basket_backtest(mats, basket, Wd, beta_df, cost_mult=cm)
        rows.append({'variant': f'costs x{cm:.1f}', 'trades': r['n_trades'],
                     'net $': r['net'], 'win %': r['win_rate'],
                     'Sharpe': r['sharpe']})
    show_table(pd.DataFrame(rows).set_index('variant'),
               title='robustness — execution timing (identical signals) '
                     'and cost multiplier',
               note='hti_close pays the bridge (~5 bps/side x beta) to '
                    'sleep flat; us_close saves it and rides each '
                    'one-legged window naked ~5h. The gap between the two '
                    'rows is the realised price of the overnight windows.',
               fmt={'trades': '{:,.0f}', 'net $': '{:,.0f}',
                    'win %': '{:.1f}', 'Sharpe': '{:.2f}'})

    # drop-one-name: a basket that dies without one name is that name in
    # disguise — the whole point of the basket is that it should NOT be
    rows = []
    for drop in NAMES:
        W2 = W.copy()
        W2[drop] = 0.0
        W2 = W2.div(W2.sum(axis=1).replace(0, np.nan), axis=0)
        bk2, dev2, Wd2 = basket_series(prem, prem16, W2, N_WINDOW)
        r = run_basket_backtest(mats, bk2, Wd2, beta_df)
        rows.append({'without': drop, 'trades': r['n_trades'],
                     'net $': r['net'], 'win %': r['win_rate']})
    show_table(pd.DataFrame(rows).set_index('without'),
               title='robustness — drop-one-name (basket must survive '
                     'every amputation)',
               fmt={'trades': '{:,.0f}', 'net $': '{:,.0f}',
                    'win %': '{:.1f}'})

    half = len(mats['base']) // 2
    for lbl, sl in (('first half', slice(0, half)),
                    ('second half', slice(half, None))):
        b3 = basket.copy()
        mask = ~basket.index.isin(basket.index[sl])
        b3.loc[mask, 'basket_z'] = np.nan
        r = run_basket_backtest(mats, b3, Wd, beta_df)
        print(f"  {lbl:<12} trades {r['n_trades']:>4} | net "
              f"${r['net']:>12,.0f} | win "
              f"{r['win_rate'] if r['n_trades'] else float('nan'):.1f}%")

    # ---- charts (optional) ----
    if CHART_FILE:
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(3, 1, figsize=(13, 11), sharex=True)
            x = pd.to_datetime(basket.index)
            ax[0].plot(x, basket['basket_dev'] * 1e4, lw=0.8,
                       label='basket dev (bps)')
            ax[0].axhline(floor_s, color='r', ls='--', lw=0.8,
                          label=f'+{floor_s:.0f}')
            ax[0].axhline(floor_l, color='g', ls='--', lw=0.8,
                          label=f'{floor_l:.0f}')
            for t_ in res['trades']:
                ax[0].axvspan(pd.Timestamp(t_['entry_date']),
                              pd.Timestamp(t_['exit_date']), alpha=0.12,
                              color=('tab:red'
                                     if t_['dir'].startswith('SHORT')
                                     else 'tab:green'))
            ax[0].legend(loc='upper left', fontsize=8)
            ax[0].set_title('basket deviation, floor lines & package holds')
            ax[1].plot(x, basket['basket_z'], lw=0.8)
            ax[1].axhline(Z_ENTRY_SHORT, color='r', ls='--', lw=0.8)
            ax[1].axhline(-Z_ENTRY_LONG, color='g', ls='--', lw=0.8)
            ax[1].set_title(f'basket z (N={N_WINDOW}) & entry thresholds')
            ax[2].plot(x, res['equity'].values, lw=1.0)
            ax[2].set_title('package equity (USD, realised + marked)')
            fig.tight_layout()
            fig.savefig(CHART_FILE, dpi=110)
            plt.close(fig)
            print(f"\n  charts -> {os.path.abspath(CHART_FILE)}")
        except Exception as e:
            print(f"\n  (charts skipped: {type(e).__name__}: {e})")

    print_scorecard()
    print(f"\n  run finished in {(datetime.now() - t_start).seconds}s | "
          f"mode={data['mode']} | {len(mats['base'])} dates | "
          f"{len(NAMES)} names")
    return res

if __name__ == '__main__' or _in_jupyter():
    RESULT = main()
