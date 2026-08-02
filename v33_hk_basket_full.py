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
# (depositary conversion is deliberately ABSENT — user 2026-08-02: the desk
# will never use the channel; do not re-add reference costings for it)
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
SOFR_TICKER = 'SOFRRATE Index'   # [B8] dynamic funding benchmark (daily);
SOFR_FALLBACK_PCT = 4.5          # used (with a WARN) when the pull fails
SPIKE_QC_BPS = 500          # [QC] 1d premium jump beyond this AND reversing
                            # next day = suspected bad print; SPIKE_ACTION
SPIKE_ACTION = 'report'     # 'report' (default) | 'exclude' (drop that
                            # name-day from inclusion — surgical, loud)
IDX_FILE_PREFIX = r"G:\FIN_COMM\DeltaOne\Kenny\ADR\HST_front_month_"
HTML_OUTPUT = True          # notebook tables; plain text always printed too
CHART_FILE = 'v33_basket_charts.png'   # None = no chart file
CHART_MODE = 'auto'         # 'auto' (inline in Jupyter, PNG in a terminal)
                            # | 'inline' | 'png' | 'both' | 'off'
OUTPUT_DIR = ''             # '' = the working directory. Every HTML/PNG the
                            # run writes lands HERE (the desk box was
                            # dropping them in the Python install folder)
INCLUDE_OTC = True          # [B0] add the OTC-traded ADRs (TCEHY/MPNGY/
                            # XIACY/KSHTY) — lifts basket coverage of HS
                            # Tech from ~30% to ~60%. No closing auction on
                            # those lines: fills are the last print.
SIGN_FILTER = 'include'     # [B3b] names whose own dev disagrees in sign
                            # with the basket: 'include' (trade the whole
                            # basket — DEFAULT) | 'exclude' (sit them out
                            # of that package). The robustness table prices
                            # the difference, which is the user's question.
RATIO_CHECK_BPS = 500       # [B0] |structural premium| beyond this is the
                            # signature of a WRONG ADS ratio. Measured, so
                            # nobody has to guess how bad that is: a ratio
                            # wrong by a factor k turns the premium into
                            # prem/k + const. The constant washes out of
                            # dev, but the 1/k SCALE does not — that name's
                            # deviations shrink, it stops clearing the bps
                            # floor, it dilutes the basket, and its ADR leg
                            # is sized wrong against its ord leg, which is
                            # a real unhedged stub. z is scale-free so it
                            # will NOT warn you. Verify a flagged ratio.
RUN_MODE = 'backtest'       # 'backtest' (DEFAULT — no trade-today screen;
                            # the run answers ONE question: is this strategy
                            # profitable) | 'today' (adds the composition /
                            # would-be-action screen back — later stage)
BETA_DRIFT_FLAG = 0.20      # |rolling beta - prior| beyond this -> a
                            # suggested UNIVERSE update is printed ([B5]:
                            # the bridge is sized off the PRIOR, so a
                            # drifted prior is a real mis-hedge — the BABA
                            # lesson from the 2026-08 real run)
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

# ---- timing display names — every print that names a timing goes through
# timing_label() so 'naked' is impossible to miss (user 2026-08-02: "The
# timing US close is naked hedge? Be clear!") -------------------------------
TIMING_LABEL = {
    'hti_close': 'hti_close (BRIDGED — ADR legs + HTI overnight, zero '
                 'naked window)',
    'us_close': 'us_close (NAKED ~5h — no bridge; each one-legged window '
                'rides the gap)',
    'hk_close': 'hk_close (ord-first intra-day — HTI bridge 08:00Z->19:00Z, '
                'ADR at the US close)',
    'hk_close_usopen': 'hk_close_usopen (ord-first — bridge off 13:30Z, '
                       'ADR legs at the US open)',
}

def timing_label(t):
    return TIMING_LABEL.get(t, t)

# ---- [QC] data-retention funnel — every filter reports what it ate, so
# over-filtering is visible instead of suspected (user 2026-08-02: "not to
# filter the valid data while filtering the bad data") ----------------------
_FUNNEL = []

def funnel(scope, stage, n_in, n_out, why=''):
    """Record one filter step: scope ('calendar' | a name | a file), the
    stage label, rows in -> rows out, and why the difference was dropped."""
    _FUNNEL.append({'scope': scope, 'stage': stage, 'in': int(n_in),
                    'out': int(n_out), 'dropped': int(n_in) - int(n_out),
                    'why': why})

def print_funnel():
    if not _FUNNEL:
        return
    f = pd.DataFrame(_FUNNEL)
    f = f[f['dropped'] != 0]
    if not len(f):
        print("\n  [QC] retention funnel: no filter dropped anything")
        return
    show_table(f.set_index('scope')[['stage', 'in', 'out', 'dropped',
                                     'why']],
               title='[QC] retention funnel — what each filter ate '
                     '(zero-drop steps hidden)',
               note='warm-up NaNs (rolling windows) are NOT drops and are '
                    'not listed here; this table is only hard filters. '
                    'Check any line whose "dropped" surprises you.',
               fmt={'in': '{:,.0f}', 'out': '{:,.0f}',
                    'dropped': '{:,.0f}'})

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
# [B0b] OTC-TRADED ADRs (INCLUDE_OTC). The listed lines above cover only
# ~30% of HS Tech; these four are the biggest missing weights and take the
# basket to roughly 60%. Two things are genuinely different about them:
#   1. NO CLOSING AUCTION — the "close" is the last print, so an ADR fill
#      is a weaker assumption here than on a listed MOC. The wider assumed
#      half-spread (OTC_ADR_HALF_SPREAD_BPS) is the price of that.
#   2. Thin ADV — the ADV weighting below keeps them small on purpose.
# Ratios confirmed 2026-08-02 against same-day prices in both lines, and
# they matter: a ratio wrong by a factor k shows up as a huge structural
# premium in [B0] (flagged at RATIO_CHECK_BPS), SHRINKS that name's
# deviations by 1/k so it quietly stops contributing, and mis-sizes its
# ADR leg against its ord leg. Verify any flagged name on DES.
OTC_UNIVERSE = {
    'TCEHY': dict(adr='TCEHY US Equity', ord='700 HK Equity', ratio=1.0,
                  lot=100, beta_prior=0.60, adv_usd=40e6, borrow_bps=100,
                  earnings=[], divs=[], venue='otc'),
    'MPNGY': dict(adr='MPNGY US Equity', ord='3690 HK Equity', ratio=2.0,
                  lot=100, beta_prior=0.80, adv_usd=6e6, borrow_bps=150,
                  earnings=[], divs=[], venue='otc'),
    'XIACY': dict(adr='XIACY US Equity', ord='1810 HK Equity', ratio=5.0,
                  lot=200, beta_prior=1.00, adv_usd=10e6, borrow_bps=150,
                  earnings=[], divs=[], venue='otc'),
    'KSHTY': dict(adr='KSHTY US Equity', ord='1024 HK Equity', ratio=0.2,
                  lot=100, beta_prior=0.90, adv_usd=2e6, borrow_bps=200,
                  earnings=[], divs=[], venue='otc'),
}
for _nm, _u in UNIVERSE.items():
    _u.setdefault('venue', 'listed')
if INCLUDE_OTC:
    UNIVERSE.update(OTC_UNIVERSE)
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
SNAP_US_OPEN_PATH = IDX_FILE_PREFIX + "1330utc.csv"       # OPTIONAL: unlocks
                            # the 'hk_close_usopen' timing when the capture
                            # job exists (UTC-fixed 13:30, not 09:30 ET)
SNAPSHOT_TIME_TOL_MIN = 20  # a capture outside this window is a WRONG
                            # capture (user 2026-08-02) — dropped, and the
                            # [QC] block prints what clock the drops were on
LOOKBACK_DAYS = 1825

# ---- [B8] COST MODEL — the DESK'S OWN numbers (user 2026-08-02), charged
# per leg, per direction, on that leg's own notional. The fee figures below
# are FEES ONLY; the bid-ask is added on top (COST_FEES_MODE) because the
# user asked for the spread to be ESTIMATED rather than assumed away.
COST_FEES_MODE = 'fees_plus_spread'   # DESK SPEC: 13/2/2 are fees and the
                            # estimated spread is added on top.
                            # 'all_in' = those figures already include
                            # crossing the spread (one switch, nothing else
                            # changes; the estimate then prints as reference)
ORD_FEE_BPS = 13.0          # HK stock legs, per side (desk's fee stack —
                            # ~stamp 10 + levies 1.1 + commission)
ADR_FEE_BPS = 2.0           # ADR legs, per side (commission + SEC headroom)
FUT_FEE_BPS = 2.0           # HTI per side (exchange + levy + commission)
# --- bid-ask. ORDS are ESTIMATED from daily high/low ([B8b] Corwin-Schultz);
# ADRs are ASSUMED, because this desk has tick data for HK stocks and HTI
# futures only — ADRs are open/close (user 2026-08-02).
SPREAD_MODE = 'assumed'     # 'assumed' (DEFAULT — the figures below, which
                            # are the desk's own observations) | 'estimated'
                            # (ords from daily H/L via Corwin-Schultz).
                            # MEASURED: C-S misses by ~5 bps in EITHER
                            # direction on names that gap like these, and
                            # ~42% of its day-pairs come out negative, so it
                            # runs as a DIAGNOSTIC by default. In
                            # 'estimated' mode it may only RAISE the
                            # assumed figure — see [B8b].
SPREAD_EST_WINDOW = 120     # day-pairs in the rolling median
SPREAD_EST_MIN_OBS = 40     # fewer usable pairs than this -> fall back
ORD_HALF_SPREAD_BPS = 5.0   # ord FALLBACK when H/L are missing or thin
ORD_SPREAD_FLOOR_BPS = 3.0  # clamp: conservative, but not punitive ...
ORD_SPREAD_CAP_BPS = 15.0   # ... and never a runaway estimate
ADR_HALF_SPREAD_BPS = 2.0   # LISTED ADR at the close/MOC — assumed
OTC_ADR_HALF_SPREAD_BPS = 10.0   # OTC ADR — the user's own screen: Tencent
                            # ~10 bps half-spread, sometimes as tight as 3
FUT_HALF_SPREAD_BPS = 2.5   # T+1 tail book — measured on the QR screen
FUT_HALF_SPREAD_DAY_BPS = 2.0   # day session (the 08:00Z / 16:00 HKT fill)
FX_HALF_SPREAD_BPS = 1.0    # deliverable pegged spot
# --- carry. SOFR is a DAILY series (SOFR_TICKER), ACT/360 on CALENDAR days
# (weekends accrue). The long leg PAYS SOFR + spread; the short leg's sale
# proceeds EARN SOFR - spread — a CREDIT, the same convention as the TW book.
FUNDING_SPREAD_BPS = 120    # long leg pays  SOFR + 120 bps
BORROW_SPREAD_BPS = 50      # short leg earns SOFR -  50 bps (rebate CREDIT)
MARGIN_HKD_PER_CONTRACT = 31_574   # HTI initial margin, HK$ per contract
MARGIN_FUND_SPREAD_BPS = 120       # margin cash funded at SOFR + 120
FLOOR_CARRY_DAYS = 0        # days of NET carry folded into the auto floor
                            # (0 = floor is costs only; carry prints as
                            # bps/day so the hurdle stays visible)
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

# ---- [B4] N x Z sweep grid — "PnL under different thresholds" (user
# 2026-08-03). The dev floor stays ON in every cell, so no cell is a
# fantasy that trades below cost. 11 x 8 = 88 backtests. ---------------------
N_GRID = list(range(10, 61, 5))            # 10, 15, 20, ... 60
Z_GRID = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
GRID_SHOW_WIN = True        # third grid table: win % per cell

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

def print_model_explained():
    """[B11] the whole model, one fact per line — asked for 2026-08-02
    ("can you explain the whole model clearly"). Every number here reads
    LIVE from the knobs, so this block cannot go stale."""
    fs, fl = dev_floor_bps()
    lines = [
        "WHAT IS TRADED    a BASKET of HS Tech names; each ADR is paired",
        "                  against its OWN ordinary at the mechanical ratio",
        "SIGN CONVENTION   prem > 0 = ADR side RICH vs the HK line -> SHORT",
        "                  package (sell ADRs / buy ords); prem < 0 -> LONG",
        "PREMIUM (name)    ADR x USDHKD / ratio  vs  ord projected to the",
        "                  same clock by beta x HTI futures capture snaps",
        f"DEV (name)        premium minus its OWN {N_WINDOW}d rolling mean",
        "                  -> each name's STRUCTURAL premium is stripped",
        f"BASKET DEV        ADV-weighted sum of devs (cap {W_CAP:.0%}/name)",
        f"BASKET Z          basket dev / {N_WINDOW}d rolling sd (shifted 1d)",
        f"ENTRY             |z| >= {Z_ENTRY_SHORT:.1f}  AND  |dev| >= floor "
        f"+{fs:.0f}/{fl:.0f} bps ({DEV_FLOOR_MODE})",
        f"GATES             reversion on (half-life <= {HL_MAX_DAYS:.0f}d) | "
        f"drift <= {DRIFT_MAX_SIGMA:.2f} sigma",
        f"                  | breadth >= {BREADTH_MIN:.0%} | earnings block | "
        f">= {MIN_NAMES_LIVE} names live",
        f"EXIT              z crosses {EXIT_Z:.1f} | time stop {TIME_STOP}d | "
        "gate shuts",
        f"EXECUTION         {timing_label(EXEC_TIMING)}",
        "PNL               two_leg ONLY — every leg marked off its own",
        "                  fills; 'convergence' is a labeled diagnostic",
        "COSTS             per-leg fees + spreads + bridge + carry — the",
        "                  full stack with $ and bps is in [B8] below",
    ]
    print("\n" + "=" * 76)
    print("  [B11] MODEL EXPLAINED — one fact per line")
    print("=" * 76)
    for ln in lines:
        print("  " + ln)

def print_beta_prior_suggestions(beta_df):
    """[B5] names whose rolling beta drifted > BETA_DRIFT_FLAG from the
    UNIVERSE prior. The engine sizes the bridge off the PRIOR, so drift is
    a real mis-hedge (the 2026-08 real run: BABA prior 0.70 vs rolling
    1.06 on a 27% weight — and drop-one showed the basket did BETTER
    without BABA)."""
    rows = []
    for nm in NAMES:
        prior = UNIVERSE[nm]['beta_prior']
        roll = beta_df[nm].iloc[-1]
        if np.isfinite(roll) and abs(roll - prior) > BETA_DRIFT_FLAG:
            rows.append((nm, prior, roll))
    if not rows:
        print(f"  [B5] beta priors: all within {BETA_DRIFT_FLAG:.2f} of the "
              f"{BETA_WINDOW}d rolling estimate — no updates suggested")
        return
    print(f"\n  [B5] SUGGESTED beta_prior UPDATES (|rolling - prior| > "
          f"{BETA_DRIFT_FLAG:.2f}; the bridge is sized off the prior):")
    for nm, prior, roll in rows:
        print(f"    {nm:<6} beta_prior {prior:.2f} -> {roll:.2f} "
              f"({BETA_WINDOW}d rolling, shrunk) — edit UNIVERSE to adopt")

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
    fname = os.path.basename(str(path))
    if nbad:
        print(f"[QC] {path}: {nbad} unparseable rows dropped")
        funnel(fname, 'unparseable rows', len(raw), len(raw) - nbad,
               'date/price failed to parse')
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
            # report-only: WHAT clock were the dropped rows on? (the drop
            # rule itself is deliberate — out-of-window rows are junk
            # captures, user 2026-08-02 — this line just lets the user
            # eyeball that nothing legitimate is in the bin)
            bad_ts = ts[~ok]
            n_nat = int(bad_ts.isna().sum())
            by_hr = bad_ts.dropna().dt.strftime('%H:00Z').value_counts()
            parts = [f"{h} x{c}" for h, c in by_hr.head(6).items()]
            if n_nat:
                parts.append(f"no-timestamp x{n_nat}")
            if parts:
                print(f"[QC]   dropped-row capture clocks: "
                      f"{', '.join(parts)}")
            funnel(fname, f'capture time != {expected_utc}Z',
                   len(raw), int(ok.sum()),
                   'junk capture clock (deliberate strict rule)')
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

    def dividends(security):
        """[B6b] dividend HISTORY via the DVD_HIST_ALL bulk field —
        [(ex_date 'YYYY-MM-DD', amount), ...] in the line's own currency.
        Element names vary by terminal version, so the parse is by
        substring ('Ex-Date' / 'Amount')."""
        try:
            req = svc.createRequest('ReferenceDataRequest')
            req.getElement('securities').appendValue(security)
            req.getElement('fields').appendValue('DVD_HIST_ALL')
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
                        if not fd.hasElement('DVD_HIST_ALL'):
                            continue
                        bulk = fd.getElement('DVD_HIST_ALL')
                        for j in range(bulk.numValues()):
                            row = bulk.getValueAsElement(j)
                            exd, amt = None, None
                            for k in range(row.numElements()):
                                el = row.getElement(k)
                                enm = str(el.name())
                                if 'Ex-Date' in enm:
                                    exd = str(el.getValueAsString())[:10]
                                elif 'Amount' in enm and amt is None:
                                    try:
                                        amt = float(el.getValueAsString())
                                    except Exception:
                                        amt = None
                            if exd and exd[0].isdigit() and amt \
                                    and amt > 0:
                                out.append((exd, amt))
                if ev.eventType() == blpapi.Event.RESPONSE:
                    break
            return sorted(out)
        except Exception as e:
            print(f"[B6b] WARNING: dividend pull failed for {security} "
                  f"({e}) — carry correction weakened for this name")
            return []

    data = {'names': {}}
    for nm, u in UNIVERSE.items():
        d = {}
        d['adr_close'] = hist(u['adr'], 'PX_LAST')
        d['adr_open'] = hist(u['adr'], 'PX_OPEN')
        # NOTE: no ADR PX_HIGH/PX_LOW — the desk only has open/close for
        # ADRs (user 2026-08-02); spreads on the ADR side are assumed.
        d['ord_close'] = hist(u['ord'], 'PX_LAST')
        d['ord_open'] = hist(u['ord'], 'PX_OPEN')
        d['ord_high'] = hist(u['ord'], 'PX_HIGH')   # [B8b] C-S spread
        d['ord_low'] = hist(u['ord'], 'PX_LOW')     # estimator inputs
        if EARNINGS_SOURCE == 'auto':
            d['earnings'] = sorted(set(earnings_dates(u['adr'])
                                       ) | set(u['earnings']))
        else:
            d['earnings'] = list(u['earnings'])
        # [B6b] dividends: ord ex-dates+amounts (HKD) drive the premium
        # carry correction; the ADR's own ex-dates bound the window
        d['divs_ord'] = sorted(set(dividends(u['ord'])) | set(u['divs']))
        d['adr_ex'] = [x[0] for x in dividends(u['adr'])]
        data['names'][nm] = d
        print(f"[DATA] {nm}: ADR {_short(u['adr'])} {len(d['adr_close'])} rows, "
              f"ord {_short(u['ord'])} {len(d['ord_close'])} rows, "
              f"{len(d['earnings'])} earnings dates, "
              f"{len(d['divs_ord'])} ord divs")
    data['fx'] = hist(FX_TICKER, 'PX_LAST')
    data['idx'] = hist(IDX_TICKER, 'PX_LAST')
    data['idx_open'] = hist(IDX_TICKER, 'PX_OPEN')   # marks the bridge OFF
    data['sofr'] = hist(SOFR_TICKER, 'PX_LAST')      # [B8] dynamic funding
    data['hti_0800'] = _load_snapshot_csv(SNAP_LOCAL_CLOSE_PATH,
                                          'HTI_0800', '08:00')
    data['hti_1900'] = _load_snapshot_csv(SNAP_T1_CLOSE_PATH,
                                          'HTI_1900', '19:00')
    # OPTIONAL third capture — unlocks the 'hk_close_usopen' timing
    try:
        data['hti_1330'] = _load_snapshot_csv(SNAP_US_OPEN_PATH,
                                              'HTI_1330', '13:30')
    except Exception:
        data['hti_1330'] = None
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
    # rng2 feeds every field added AFTER the v2 baseline (H/L, divs, SOFR,
    # OTC names): the PRIMARY rng draw order must stay bit-identical or the
    # planted-dislocation panel — and every baseline diff — silently shifts
    rng2 = np.random.default_rng(seed + 1)
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
        # ---- planted corporate actions & microstructure (rng2 ONLY) ----
        o_arr = np.array(ord_opens)
        c_arr = np.array(ords)
        adrs = np.array(adrs)
        ados = np.array(ados)
        # DIVIDENDS, the real mechanics: the HK line goes ex FIRST (a
        # permanent step down in the ord), the ADR follows ~5 sessions
        # later. In between, the ord has dropped and the ADR has not, so
        # the measured premium reads rich by ~div/px — precisely the
        # artefact [B6b] must remove, and the reason a run with no
        # dividend data prints entries that are really ex-date noise.
        n_div = max(1, n_days // 300)
        # plant only where the whole [ex, ex+6] window trades in BOTH
        # markets — an ex-date on a dropped calendar row would dodge the
        # correction and make the self-test lie
        bad_days = hk_hol | us_hol
        cand = np.array([t for t in range(60, n_days - 10)
                         if not any((t + k) in bad_days
                                    for k in range(0, 7))])
        div_locs = sorted(int(x) for x in rng2.choice(
            cand, size=min(n_div, len(cand)), replace=False))
        divs_ord, adr_ex = [], []
        for ex in div_locs:
            d_frac = float(rng2.uniform(0.006, 0.015))
            amt = float(c_arr[ex - 1] * d_frac)   # HKD/share off the cum px
            a_ex = min(ex + 5, n_days - 1)
            o_arr[ex:] *= (1.0 - d_frac)          # ord opens ex on the day
            c_arr[ex:] *= (1.0 - d_frac)
            adrs[a_ex:] *= (1.0 - d_frac)         # ADR goes ex ~5d later
            ados[a_ex:] *= (1.0 - d_frac)
            divs_ord.append((fac['Date'].iloc[ex], amt))
            adr_ex.append(fac['Date'].iloc[a_ex])
        # ord H/L with a KNOWN half-spread. The intraday path is a proper
        # Brownian BRIDGE from the open to the close (26 steps) and the
        # high/low are that path's extremes — an ad-hoc "range around
        # open/close" is NOT diffusion-consistent and makes any high/low
        # spread estimator look broken when it is the DATA that is wrong.
        # The extremes then print on the ask and the bid, which is the
        # inflation [B8b] tries to read back out. Built AFTER the ex-steps
        # so high/low agree with the traded prices.
        s_half = float(rng2.uniform(3e-4, 12e-4))
        K = 26
        tg = np.arange(1, K) / K
        inc = rng2.normal(0, np.sqrt(1.0 / K), size=(n_days, K))
        Wp = np.cumsum(inc, axis=1)
        bridge = Wp[:, :-1] - tg * Wp[:, -1][:, None]      # W_t - t*W_1
        logp = (np.log(np.maximum(o_arr, 1e-9))[:, None] * (1 - tg)
                + np.log(np.maximum(c_arr, 1e-9))[:, None] * tg
                + 0.012 * bridge)
        path = np.exp(logp)
        hi_true = np.maximum(path.max(axis=1), np.maximum(o_arr, c_arr))
        lo_true = np.minimum(path.min(axis=1), np.minimum(o_arr, c_arr))
        ord_highs = hi_true * (1 + s_half)
        ord_lows = lo_true * (1 - s_half)
        dd = pd.DataFrame({'Date': fac['Date']})
        d = {}
        hk_ok = fac['hk_open'].values
        us_ok = fac['us_open'].values
        d['ord_close'] = dd.assign(px=c_arr)[['Date', 'px']][hk_ok]
        d['ord_open'] = dd.assign(px=o_arr)[['Date', 'px']][hk_ok]
        d['ord_high'] = dd.assign(px=ord_highs)[['Date', 'px']][hk_ok]
        d['ord_low'] = dd.assign(px=ord_lows)[['Date', 'px']][hk_ok]
        d['adr_close'] = dd.assign(px=adrs)[['Date', 'px']][us_ok]
        d['adr_open'] = dd.assign(px=ados)[['Date', 'px']][us_ok]
        # synthetic earnings: one date per ~quarter, so the [B6] gate and
        # the auto-pull plumbing get exercised end-to-end
        qtr = list(range(30 + int(rng.integers(0, 10)), n_days, 63))
        d['earnings'] = [fac['Date'].iloc[q] for q in qtr]
        d['divs_ord'] = divs_ord
        d['adr_ex'] = adr_ex
        d['planted_half_spread_bps'] = s_half * 1e4
        data['names'][nm] = d
    data['fx'] = fac.assign(px=fac['fx'])[['Date', 'px']]
    # [B8] synthetic SOFR: ~5.30% with two -25 bp steps + 1 bp daily noise
    # (rng2) — exercises the dynamic-carry accrual end to end
    sofr = (5.30
            - 0.25 * (np.arange(n_days) >= n_days // 3)
            - 0.25 * (np.arange(n_days) >= 2 * n_days // 3)
            + rng2.normal(0, 0.01, n_days))
    data['sofr'] = fac.assign(px=sofr)[['Date', 'px']]
    data['idx'] = fac.assign(px=fac['F0800'])[['Date', 'px']]
    data['idx_open'] = fac.assign(px=fac['F0130'])[['Date', 'px']]
    both = fac['hk_open'].values
    data['hti_0800'] = fac.assign(HTI_0800=fac['F0800'])[
        ['Date', 'HTI_0800']][both]
    data['hti_1900'] = fac.assign(HTI_1900=fac['F1900'])[
        ['Date', 'HTI_1900']][both]
    # the OPTIONAL 13:30Z node, drawn from rng2 so the primary path is
    # untouched: a point on the way from 08:00Z to 19:00Z, so the
    # 'hk_close_usopen' timing can be exercised end to end here
    w13 = 0.55 + rng2.normal(0, 0.05, n_days).clip(-0.15, 0.15)
    f1330 = fac['F0800'].values * (1 - w13) + fac['F1900'].values * w13
    data['hti_1330'] = fac.assign(HTI_1330=f1330)[
        ['Date', 'HTI_1330']][both]
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
    # the 13:30Z capture is OPTIONAL and joins LEFT — a missing third
    # capture must never cost a date on the two timings that don't need it
    h13 = data.get('hti_1330')
    if h13 is not None and len(h13):
        h13 = h13.copy()
        h13['Date'] = h13['Date'].astype(str)
        base = pd.merge(base, h13, on='Date', how='left')
    base = pd.merge(base, fx, on='Date', how='inner')
    base = pd.merge(base, idx, on='Date', how='left')
    if idxo is not None:
        base = pd.merge(base, idxo, on='Date', how='left')
    # [QC] the inner joins above are the top false-drop suspect: ONE missing
    # snap kills the date for every name, so account for them explicitly
    funnel('calendar', 'HTI 0800Z snap dates', len(h08), len(h08), '')
    funnel('calendar', 'inner join 0800Z & 1900Z snaps',
           max(len(h08), len(h19)), len(pd.merge(h08, h19, on='Date')),
           'one snap missing kills the whole date')
    n_pre_fx = len(base)
    bad_fx = ~base['FX'].between(*FX_SANE_BAND)
    if bad_fx.any():
        print(f"[QC] {int(bad_fx.sum())} FX prints outside the peg band "
              f"{FX_SANE_BAND} — dropped:")
        print(base.loc[bad_fx, ['Date', 'FX']].head(5).to_string(index=False))
        base = base.loc[~bad_fx]
        funnel('calendar', 'FX outside peg band', n_pre_fx, len(base),
               f'FX not in {FX_SANE_BAND}')
    base = base.sort_values('Date').reset_index(drop=True)
    # ---- [B8] SOFR: the funding/rebate benchmark, as a DAILY series ----
    # publication lag is real (SOFR for day t prints on t+1), so the rate
    # applied on day t is shifted one row, then held over gaps
    sofr_src = data.get('sofr')
    if sofr_src is not None and len(sofr_src):
        s = sofr_src.rename(columns={'px': 'SOFR_pct'}).copy()
        s['Date'] = s['Date'].astype(str)
        s = s.drop_duplicates('Date', keep='last')
        base = pd.merge(base, s, on='Date', how='left')
        base['SOFR_pct'] = base['SOFR_pct'].shift(1).ffill()
        n_miss = int(base['SOFR_pct'].isna().sum())
        base['SOFR_pct'] = base['SOFR_pct'].fillna(SOFR_FALLBACK_PCT)
        got = base['SOFR_pct']
        sc('INFO', 'SOFR series [B8]',
           f"{SOFR_TICKER}: last {got.iloc[-1]:.2f}% | range "
           f"{got.min():.2f}-{got.max():.2f}% | {n_miss} warm-up rows at "
           f"the {SOFR_FALLBACK_PCT:.2f}% fallback")
    else:
        base['SOFR_pct'] = SOFR_FALLBACK_PCT
        sc('WARN', 'SOFR series [B8]',
           f'no {SOFR_TICKER} series — funding/rebate carry runs on the '
           f'flat {SOFR_FALLBACK_PCT:.2f}% fallback, so carry is only as '
           f'good as that guess')
    panel = {'base': base}
    cov = []
    px_cols = [('adr_close', 'ADR_close'), ('adr_open', 'ADR_open'),
               ('ord_close', 'ORD_close'), ('ord_open', 'ORD_open'),
               # ords only — the desk has no ADR high/low (user 2026-08-02)
               ('ord_high', 'ORD_high'), ('ord_low', 'ORD_low')]
    for nm in NAMES:
        d = data['names'][nm]
        m = None
        for key, col in px_cols:
            if key not in d or d[key] is None or not len(d[key]):
                continue
            f = d[key].rename(columns={'px': col}).copy()
            f['Date'] = f['Date'].astype(str)
            f = f.drop_duplicates('Date', keep='last')
            m = f if m is None else pd.merge(m, f, on='Date', how='outer')
        m = m.sort_values('Date').reset_index(drop=True)
        panel[nm] = m
        cov.append({'name': nm,
                    'ADR rows': int(m['ADR_close'].notna().sum()),
                    'ord rows': int(m['ORD_close'].notna().sum()),
                    'ord H/L rows': int(m['ORD_high'].notna().sum())
                    if 'ORD_high' in m.columns else 0,
                    'both': int((m['ADR_close'].notna()
                                 & m['ORD_close'].notna()).sum())})
    show_table(pd.DataFrame(cov).set_index('name'),
               title='[QC] raw per-name coverage (rows with data)',
               note='ord H/L feeds the [B8b] spread estimator; ADRs have no '
                    'high/low on this desk, so ADR spreads are assumed.',
               fmt='{:,.0f}')
    return panel

def build_matrices(panel):
    """Wide matrices indexed by the master calendar: ords, ADRs, live mask,
    plus the base (FX + HTI snap) frame. Everything downstream is numpy on
    these — one construction, no per-block re-merging [L5]."""
    base = panel['base'].copy()
    cal = base['Date']
    mats = {}
    for col in ('ADR_close', 'ADR_open', 'ORD_close', 'ORD_open',
                'ORD_high', 'ORD_low'):
        m = pd.DataFrame({'Date': cal})
        have = False
        for nm in NAMES:
            if col not in panel[nm].columns:
                m[nm] = np.nan
                continue
            have = True
            f = panel[nm][['Date', col]]
            m = pd.merge(m, f.rename(columns={col: nm}), on='Date',
                         how='left')
        if not have and col in ('ORD_high', 'ORD_low'):
            sc('WARN', 'ord high/low [B8b]',
               'no PX_HIGH/PX_LOW series — the spread estimator falls back '
               'to the assumed constants for every name')
        mats[col] = m.set_index('Date')
    live = mats['ADR_close'].notna() & mats['ORD_close'].notna()
    # a date needs BOTH markets: ords traded (ORD side) and ADRs traded
    n_live = live.sum(axis=1)
    keep = n_live >= MIN_NAMES_LIVE
    dropped = int((~keep).sum())
    if dropped:
        print(f"[QC] {dropped} dates dropped: fewer than {MIN_NAMES_LIVE} "
              f"names live (holiday mismatch or data holes)")
    funnel('calendar', f'< {MIN_NAMES_LIVE} names live', len(keep),
           int(keep.sum()), 'holiday mismatch or data holes')
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

def build_premium_panel(mats, beta_df, divs_map=None, adr_ex_map=None):
    """[B2a] TWO premium panels, one sign convention (ADR rich = +):
      prem    — SIGNAL clock (US close t): fresh ADR vs same-day ord
                projected 08:00Z -> 19:00Z by beta x HTI. Max ~2h stale.
      prem16  — 08:00Z clock (16:00 HKT t): ord live, ADR t-1 projected
                19:00Z(t-1) -> 08:00Z(t). ~12h-stale ADR — the signal clock
                for the 'hk_close' timings, and the fill re-measure for the
                US-close ones."""
    base = mats['base']
    fx = base['FX'].values
    # prem16 is observed at 08:00Z; the day's USDHKD PX_LAST is a ~NY-close
    # print (~21:00Z), i.e. AFTER the observation — so the 08:00Z clock uses
    # the PRIOR row's FX. Immaterial under the peg, but prem16 originates
    # signals for hk_close, and a signal clock must not read the future.
    fx_prev = base['FX'].shift(1).values
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
        f16 = adr_prev * fx_prev / u['ratio'] * (1.0 + b * gap_on)
        prem16[nm] = pd.Series(f16 / ordc - 1.0,
                               index=mats['ORD_close'].index)
    prem = pd.DataFrame(prem)
    prem16 = pd.DataFrame(prem16)
    # [B6b] dividend carry correction. Between the HK ex-date and the ADR
    # ex-date the two lines step at DIFFERENT times: the ord has already
    # dropped by the dividend while the ADR has not, so the measured premium
    # reads rich by div/px for that window — subtract it. Dates come from the
    # DVD_HIST_ALL pull (merged with any manual UNIVERSE entries); the ADR's
    # own ex-date closes each window when known, else ~5 sessions.
    divs_map = divs_map or {nm: UNIVERSE[nm]['divs'] for nm in NAMES}
    adr_ex_map = adr_ex_map or {}
    n_div = sum(len(divs_map.get(nm, [])) for nm in NAMES)
    n_applied = 0
    if n_div == 0:
        sc('WARN', 'dividend carry [B6b]',
           'no dividend dates (auto-pull empty and no manual lists) — '
           'ex-date premium spikes are NOT corrected; check the [QC] spike '
           'table before trusting entries near ex-dates')
    else:
        idx = prem.index
        for nm in NAMES:
            adr_ex = sorted(str(x)[:10] for x in adr_ex_map.get(nm, []))
            for exd, amt in divs_map.get(nm, []):
                exd = str(exd)[:10]
                loc = int(idx.searchsorted(exd))
                if loc >= len(idx) or not (amt and amt > 0):
                    continue
                stop = min(loc + 5, len(idx))       # default ~1 week
                # close the window at the ADR's own ex-date when known
                nxt = [a for a in adr_ex if a >= exd]
                if nxt:
                    aloc = int(idx.searchsorted(nxt[0]))
                    if loc < aloc <= loc + 15:
                        stop = min(aloc, len(idx))
                px = mats['ORD_close'][nm].iloc[loc]
                if not (np.isfinite(px) and px > 0) or stop <= loc:
                    continue
                rows = idx[loc:stop]
                prem.loc[rows, nm] -= amt / px
                prem16.loc[rows, nm] -= amt / px
                n_applied += 1
        sc('INFO', 'dividend carry [B6b]',
           f'{n_div} ex-dates across {len(NAMES)} names, {n_applied} '
           f'correction windows applied to the premium panels')
    return prem, prem16, pd.DataFrame(fair)

def spike_qc(prem, divs_map=None):
    """[QC] largest one-day premium JUMPS — ex-dates, wrong ratios and bad
    prints all look like this. Returns a BAD-PRINT mask (a jump beyond
    SPIKE_QC_BPS that REVERSES the next day is a print, not a move); the
    mask is applied to inclusion only when SPIKE_ACTION='exclude'."""
    divs_map = divs_map or {}
    dif = prem.diff()
    j = dif.abs()
    # a spike that comes straight back = a bad print; one that stays = a move
    reverses = (dif * dif.shift(-1) < 0) & (
        dif.shift(-1).abs() >= 0.5 * dif.abs())
    suspect = (j * 1e4 >= SPIKE_QC_BPS) & reverses
    rows = []
    for nm in NAMES:
        s = j[nm].dropna()
        if not len(s):
            continue
        d = s.idxmax()
        ex = sorted(str(x[0])[:10] for x in divs_map.get(nm, []))
        near = any(abs((pd.Timestamp(d) - pd.Timestamp(e)).days) <= 6
                   for e in ex) if ex else False
        rows.append({'name': nm, 'worst 1d jump (bps)': s.max() * 1e4,
                     'date': d,
                     'near ex-date?': 'yes' if near else
                                      ('no' if ex else 'no div data'),
                     'p99 jump (bps)': s.quantile(0.99) * 1e4,
                     f'suspect prints (>{SPIKE_QC_BPS:.0f}bps & reversing)':
                         int(suspect[nm].sum())})
    show_table(pd.DataFrame(rows).set_index('name'),
               title='[QC] premium jump audit — ex-dates / ratio errors / '
                     'bad prints look like this',
               note=f"'suspect' = a jump over {SPIKE_QC_BPS:.0f} bps that "
                    f"REVERSES the next day (a print, not a move). "
                    f"SPIKE_ACTION='{SPIKE_ACTION}'"
                    + (" — those name-days are excluded from the basket."
                       if SPIKE_ACTION == 'exclude'
                       else " — reported only, nothing excluded."),
               fmt={'worst 1d jump (bps)': '{:,.0f}',
                    'p99 jump (bps)': '{:,.0f}',
                    f'suspect prints (>{SPIKE_QC_BPS:.0f}bps & reversing)':
                        '{:,.0f}'})
    n_sus = int(suspect.values.sum())
    if n_sus:
        sc('WARN' if SPIKE_ACTION == 'report' else 'INFO',
           'suspect prints [QC]',
           f'{n_sus} name-days jump >{SPIKE_QC_BPS:.0f} bps and reverse '
           f'next day — SPIKE_ACTION={SPIKE_ACTION}')
    return suspect.fillna(False)

# ============================================================================
# [B8b] BID-ASK — "Do you need order book? Assuming the cost? ... Estimate
# for the bid ask" (user 2026-08-02). There is no order book here, and no
# ADR high/low at all, so the two sides are handled differently AND with
# different confidence:
#   HK ORDS  Corwin-Schultz (2012) two-day high/low estimator, de-gapped by
#            the ACTUAL overnight return (PX_OPEN vs the prior close) — the
#            paper's overlap-only fix is not enough for names that gap this
#            hard. MEASURED BIAS: even on a clean diffusion panel with a
#            known spread, C-S reads ~4-6 bps LOW here and about half its
#            day-pairs come out negative (run this file on synthetic data
#            and read the 'planted vs recovered' columns). So the estimate
#            is a DIAGNOSTIC, and in 'estimated' mode it is only ever
#            allowed to RAISE the assumed cost, never to cut it. A
#            downward-biased spread estimate driving a cost floor would
#            quietly make a losing book look profitable.
#   ADRs     ASSUMED — listed ADR_HALF_SPREAD_BPS, OTC
#            OTC_ADR_HALF_SPREAD_BPS (the user's own screen: Tencent ~10
#            bps, sometimes 3). No ADR high/low exists to estimate from.
# ============================================================================
def _corwin_schultz(hi, lo, op=None, cl=None):
    """Per-day-pair PROPORTIONAL spread S (not halved, not bps), raw and
    UN-floored — the caller aggregates first and clamps after (zeroing
    each pair before aggregating is what collapses the estimate). Element
    t uses days t-1 and t, so the series is already 'as of' t."""
    hi = np.asarray(hi, dtype=float)
    lo = np.asarray(lo, dtype=float)
    out = np.full(len(hi), np.nan)
    if len(hi) < 2:
        return out
    h0, l0 = hi[:-1], lo[:-1]
    h1, l1 = hi[1:].copy(), lo[1:].copy()
    with np.errstate(all='ignore'):
        if op is not None and cl is not None:
            # de-gap: slide day 2's range back onto day 1's close by the
            # REAL overnight return, so the gap cannot masquerade as spread
            op = np.asarray(op, dtype=float)
            cl = np.asarray(cl, dtype=float)
            k_ = cl[:-1] / op[1:]
            k_ = np.where(np.isfinite(k_) & (k_ > 0), k_, 1.0)
            h1, l1 = h1 * k_, l1 * k_
        else:
            gap = np.where(l1 > h0, l1 - h0,
                           np.where(h1 < l0, h1 - l0, 0.0))
            h1, l1 = h1 - gap, l1 - gap
        b = np.log(h0 / l0) ** 2 + np.log(h1 / l1) ** 2
        g = np.log(np.maximum(h0, h1) / np.minimum(l0, l1)) ** 2
        k = 3.0 - 2.0 * np.sqrt(2.0)
        alpha = (np.sqrt(2.0 * b) - np.sqrt(b)) / k - np.sqrt(g / k)
        s = 2.0 * (np.expm1(alpha)) / (1.0 + np.exp(alpha))
    bad = (~np.isfinite(s)) | (h0 <= l0) | (h1 <= l1) | (l0 <= 0) | (l1 <= 0)
    out[1:] = np.where(bad, np.nan, s)
    return out

def estimate_half_spreads(mats, data=None):
    """Per-name, per-date HALF-spread in bps for both legs. Returns
    (ord_hs_df, adr_hs_series) — the ord frame is a full date x name panel
    (shifted, so day t uses information through t-1); the ADR figures are
    per-name constants."""
    idx = mats['ORD_close'].index
    hi_all = mats.get('ORD_high')
    lo_all = mats.get('ORD_low')
    ord_hs, rows = {}, []
    n_raised = 0
    for nm in NAMES:
        u = UNIVERSE[nm]
        fb = float(u.get('half_spread_bps') or ORD_HALF_SPREAD_BPS)
        est_med, n_obs, pct_neg = np.nan, 0, np.nan
        est_ser = None
        if hi_all is not None and lo_all is not None and nm in hi_all.columns:
            hi = hi_all[nm].values
            lo = lo_all[nm].values
            if np.isfinite(hi).any():
                s = _corwin_schultz(hi, lo, mats['ORD_open'][nm].values,
                                    mats['ORD_close'][nm].values)
                fin = s[np.isfinite(s)]
                n_obs = len(fin)
                if n_obs:
                    pct_neg = float((fin < 0).mean() * 100)
                if n_obs >= SPREAD_EST_MIN_OBS:
                    # aggregate the RAW pairs (median: robust to the fat
                    # tails C-S throws), then clamp — never the other way
                    half = pd.Series(s / 2.0 * 1e4, index=idx)
                    est_ser = (half.rolling(SPREAD_EST_WINDOW,
                                            min_periods=SPREAD_EST_MIN_OBS)
                               .median().shift(1))
                    est_med = float(np.nanmedian(half.values))
        # the estimate may only RAISE the assumed figure — C-S reads low on
        # names that gap this hard, and a cost floor built on an
        # understated spread flatters the book
        if SPREAD_MODE == 'estimated' and est_ser is not None:
            ser = np.maximum(est_ser.fillna(fb), fb)
            if float(np.nanmax(est_ser.values)) > fb:
                n_raised += 1
        else:
            if SPREAD_MODE == 'estimated':
                sc('WARN', f'spread est [B8b] {nm}',
                   f'only {n_obs} usable H/L pairs (need '
                   f'{SPREAD_EST_MIN_OBS}) — assumed {fb:.1f} bps used')
            ser = pd.Series(fb, index=idx)
        ord_hs[nm] = pd.Series(ser, index=idx).fillna(fb).clip(
            ORD_SPREAD_FLOOR_BPS, ORD_SPREAD_CAP_BPS)
        planted = ((data or {}).get('names', {}).get(nm, {})
                   .get('planted_half_spread_bps'))
        row = {'name': nm,
               'venue': u.get('venue', 'listed'),
               'ord assumed (bps)': fb,
               'ord C-S est (bps)': est_med,
               'C-S pairs neg %': pct_neg,
               'ord USED (bps)': float(ord_hs[nm].iloc[-1]),
               'ADR assumed (bps)': adr_half_spread_bps(nm)}
        if planted is not None:
            row['synth planted (bps)'] = planted
            row['C-S error (bps)'] = (est_med - planted
                                      if np.isfinite(est_med) else np.nan)
        rows.append(row)
    tbl = pd.DataFrame(rows).set_index('name')
    fmt = {c: '{:,.1f}' for c in tbl.columns if 'bps' in c or '%' in c}
    err_col = 'C-S error (bps)'
    bias_note = ''
    if err_col in tbl.columns:
        mb = float(np.nanmean(tbl[err_col].values))
        bias_note = (f" SELF-TEST on the synthetic panel (known planted "
                     f"spreads): C-S is off by {mb:+.1f} bps on average — "
                     f"this is the documented downward bias on gappy "
                     f"names, and the reason the estimate may only RAISE "
                     f"the assumed figure, never cut it.")
    show_table(tbl, title='[B8b] bid-ask — HALF-spreads, one crossing '
                          f'(SPREAD_MODE={SPREAD_MODE})',
               note='ORDS: Corwin-Schultz on daily high/low, de-gapped by '
                    f'the real overnight return, {SPREAD_EST_WINDOW}d '
                    'rolling median, shifted a day, clamped to '
                    f'[{ORD_SPREAD_FLOOR_BPS:.0f}, '
                    f'{ORD_SPREAD_CAP_BPS:.0f}] bps. ADRS: assumed — this '
                    'desk has no ADR high/low, so there is nothing to '
                    f'estimate from; OTC lines carry '
                    f'{OTC_ADR_HALF_SPREAD_BPS:.0f} bps, listed '
                    f'{ADR_HALF_SPREAD_BPS:.0f}.' + bias_note,
               fmt=fmt)
    if SPREAD_MODE == 'estimated':
        sc('INFO', 'spread estimate [B8b]',
           f'ords: C-S ran on {len(NAMES)} names, raised the assumed '
           f'half-spread on {n_raised} — estimates can only push costs UP '
           f'(C-S is biased low on gappy names)')
    return pd.DataFrame(ord_hs), pd.Series(
        {nm: adr_half_spread_bps(nm) for nm in NAMES})

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
def build_inclusion(mats, corr_df, coint_ok, earnings_map, suspect=None):
    live = mats['live']
    incl = live.copy()
    n_live_days = int(incl.values.sum())
    incl &= corr_df >= CORR_MIN
    funnel('per-name days', f'corr vs HTI < {CORR_MIN:.2f} (or warm-up)',
           n_live_days, int(incl.values.sum()),
           f'{CORR_WINDOW}d rolling corr gate [B5c] incl. its warm-up')
    if COINT_GATE == 'exclude':
        n_pre = int(incl.values.sum())
        incl &= coint_ok
        funnel('per-name days', 'cointegration gate', n_pre,
               int(incl.values.sum()), f'EG residual ADF p > {COINT_PMAX}')
    if suspect is not None and SPIKE_ACTION == 'exclude':
        n_pre = int(incl.values.sum())
        incl &= ~suspect.reindex_like(incl).fillna(False)
        funnel('per-name days', 'suspect print (spike + reversal)', n_pre,
               int(incl.values.sum()), f'>{SPIKE_QC_BPS:.0f} bps and back')
    # [B6] earnings block: a name inside its window is dropped from the
    # basket (weights renormalise) — dates come from the Bloomberg pull
    # (EARNINGS_SOURCE='auto'), merged with any manual UNIVERSE entries
    dates = pd.Index(mats['base']['Date'])
    n_dates_total = 0
    n_pre_ern = int(incl.values.sum())
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
    funnel('per-name days', 'earnings block [B6]', n_pre_ern,
           int(incl.values.sum()),
           f'announcement day +/- {EARNINGS_BLOCK_DAYS}d')
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
    """Window-dependent basket series for z window n (see [B3] header).
    BOTH clocks get the full set — the US-close clock (dev/z/breadth) and
    the 08:00Z clock (dev16/z16/breadth16) — because the 'hk_close' timings
    SIGNAL off the 08:00Z clock, and a signal clock needs its own z, its
    own breadth and its own gate series ([L5]: one builder, fed whichever
    series the timing actually trades)."""
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
    basket_prem16 = (Wd * prem16).sum(axis=1, min_count=1)
    sd16 = basket_prem16.rolling(n).std(ddof=0).shift(1).replace(0, np.nan)
    basket_z16 = basket_dev16 / sd16
    n_incl = (Wd > 0).sum(axis=1)
    agree = ((np.sign(dev) == np.sign(basket_dev.values[:, None]))
             & (Wd > 0)).sum(axis=1)
    breadth = agree / n_incl.replace(0, np.nan)
    agree16 = ((np.sign(dev16) == np.sign(basket_dev16.values[:, None]))
               & (Wd > 0)).sum(axis=1)
    breadth16 = agree16 / n_incl.replace(0, np.nan)
    return pd.DataFrame({'basket_dev': basket_dev,
                         'basket_dev16': basket_dev16,
                         'basket_prem': basket_prem,
                         'basket_prem16': basket_prem16,
                         'basket_z': basket_z, 'basket_z16': basket_z16,
                         'n_incl': n_incl, 'breadth': breadth,
                         'breadth16': breadth16}), dev, Wd

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
# [B8] COST MODEL — the desk's own figures, charged leg by leg on each leg's
# own notional. FEES and SPREAD are separate (COST_FEES_MODE):
#   ADR side (per crossing): 2 bps fee + assumed half-spread (2 listed /
#       10 OTC — this desk has no ADR high/low to estimate from).
#   Ord side (per crossing): 13 bps fee + ESTIMATED half-spread ([B8b])
#       + 2 x FX half-spread on the HKD flows.
#   Bridge (per window, bridged timings): 2 x 2 bps futures fees + the tail
#       and day-session half-spreads, on bridge-ratio x notional, plus the
#       funding of HK$31,574 initial margin per contract while it is posted.
# CARRY: the long leg pays SOFR + 120 bps; the SHORT leg's proceeds EARN
# SOFR - 50 bps (a CREDIT). ACT/360 on calendar days — weekends accrue.
# With matched leg notionals the SOFR level itself very nearly cancels; what
# is left is the ~170 bps/yr spread plus the margin.
# ============================================================================
# weighted half-spreads for the CURRENT run, set by main() once the [B8b]
# estimates exist; the ex-ante cost/floor prints read them (with assumed
# fallbacks) so the floor tracks the measured spread, not a guess
_HS_CTX = {'ord': None, 'adr': None}

def adr_half_spread_bps(nm):
    """ASSUMED ADR half-spread: no ADR high/low on this desk (user
    2026-08-02), so OTC lines carry the wider figure and listed lines the
    tighter one — both overridable per name in UNIVERSE."""
    u = UNIVERSE.get(nm, {})
    if u.get('half_spread_adr_bps'):
        return float(u['half_spread_adr_bps'])
    return (OTC_ADR_HALF_SPREAD_BPS if u.get('venue') == 'otc'
            else ADR_HALF_SPREAD_BPS)

def _ord_hs():
    v = _HS_CTX.get('ord')
    return float(v) if v is not None else float(ORD_HALF_SPREAD_BPS)

def _adr_hs():
    v = _HS_CTX.get('adr')
    if v is not None:
        return float(v)
    return float(np.mean([adr_half_spread_bps(nm) for nm in NAMES]))

def adr_side_cost_bps(hs=None):
    """One ADR crossing, bps of the ADR leg's notional."""
    if COST_FEES_MODE == 'all_in':
        return ADR_FEE_BPS
    return ADR_FEE_BPS + (_adr_hs() if hs is None else float(hs))

def ord_side_cost_bps(hs=None):
    """One ord crossing, bps of the ord leg's notional (FX is a separate
    market, so it is charged in both fee modes)."""
    if COST_FEES_MODE == 'all_in':
        return ORD_FEE_BPS + 2 * FX_HALF_SPREAD_BPS
    return (ORD_FEE_BPS + (_ord_hs() if hs is None else float(hs))
            + 2 * FX_HALF_SPREAD_BPS)

def is_bridged(timing=None):
    return (EXEC_TIMING if timing is None else timing) in (
        'hti_close', 'hk_close', 'hk_close_usopen')

def bridge_window_cost_bps(timing=None, ratio=0.8):
    """One bridge window (on + off) in bps of PACKAGE notional. The two
    half-spreads are the tail book and the day session — which one is paid
    going in depends on the timing, but the pair is the same either way."""
    if not is_bridged(timing):
        return 0.0
    return (2 * FUT_FEE_BPS + FUT_HALF_SPREAD_BPS
            + FUT_HALF_SPREAD_DAY_BPS) * ratio

def margin_window_cost_bps(timing=None, ratio=0.8, nights=1.0,
                           hti=5000.0, fx=7.8):
    """Funding the HTI initial margin for one bridge window, bps of package
    notional. Small, but the user asked for it explicitly."""
    if not is_bridged(timing):
        return 0.0
    ct = max(1.0, round(ratio * 1e6 * fx / (hti * IDX_FUT_MULTIPLIER)))
    margin_usd = ct * MARGIN_HKD_PER_CONTRACT / fx
    cost = margin_usd * (MARGIN_FUND_SPREAD_BPS / 1e4) * max(nights, 1.0) / 360
    return cost / 1e6 * 1e4          # per US$1mm of package, in bps

def entry_side_cost_bps(timing=None):
    """One side of the round trip (the entry, or the mirror-image exit)."""
    return (adr_side_cost_bps() + ord_side_cost_bps()
            + bridge_window_cost_bps(timing)
            + margin_window_cost_bps(timing))

def package_rt_cost_bps(timing=None):
    """Ex-ante round trip in bps of package notional (screen both ways)."""
    return 2 * entry_side_cost_bps(timing)

def net_carry_bps_per_day(sofr_pct=None):
    """Net financing on a matched package, bps of package notional per
    CALENDAR day. The SOFR level cancels between the paying and earning
    legs; what survives is the spread pair."""
    return (FUNDING_SPREAD_BPS + BORROW_SPREAD_BPS) / 360.0

def dev_floor_bps():
    """[B4] the cost-anchored deviation floor: 'auto' derives it from the
    live cost model (so it moves when fees/spreads/timing move); 'manual'
    is the user's original +55/-60 pair. Returns (short_floor, long_floor),
    short positive, long negative."""
    if DEV_FLOOR_MODE == 'manual':
        return float(DEV_FLOOR_SHORT_BPS), float(DEV_FLOOR_LONG_BPS)
    f = (package_rt_cost_bps()
         + FLOOR_CARRY_DAYS * net_carry_bps_per_day()) * MIN_EDGE_HARD
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
#
# ---------------------------------------------------------------------------
# BRIDGE SIGN, THE 2x2 — get this wrong and the hedge doubles the risk it was
# meant to remove, silently. In every window exactly ONE leg is live and the
# bridge must be its OPPOSITE. pos = +1 is LONG ADR / SHORT ord.
#
#   timing       window   leg that is LIVE      bridge must be   code sign
#   hti_close    entry    ADR   (+pos)          -pos x HTI       (-pos)
#   hti_close    exit     ord   (-pos)          +pos x HTI       (+pos)
#   hk_close*    entry    ord   (-pos)          +pos x HTI       (+pos)
#   hk_close*    exit     ADR   (+pos)          -pos x HTI       (-pos)
#
# Read the hk_close entry row concretely: a SHORT package (pos=-1) fills its
# ords LONG at the 08:00Z close, so the bridge is (+pos) = SHORT HTI. The
# ord-first timings are the exact mirror of the ADR-first one.
# ---------------------------------------------------------------------------
# ============================================================================
def run_basket_backtest(mats, basket, W, beta_df, z_short=None, z_long=None,
                        cost_mult=1.0, collect_audit=False,
                        exec_timing=None, ord_hs=None, sign_filter=None,
                        dev=None):
    z_short = Z_ENTRY_SHORT if z_short is None else z_short
    z_long = Z_ENTRY_LONG if z_long is None else z_long
    timing = EXEC_TIMING if exec_timing is None else exec_timing
    bridged = is_bridged(timing)
    # INTRADAY timings signal at the 08:00Z HK close and finish the package
    # the SAME row at the US close — both legs land inside one calendar row,
    # so the pending-leg states (1 and 3) are never used.
    intraday = timing in ('hk_close', 'hk_close_usopen')
    base = mats['base']
    dates = base['Date'].values
    dts = pd.to_datetime(base['Date'])
    gap_next = np.r_[np.diff(dts.values) / np.timedelta64(1, 'D'), 999.0]
    fx = base['FX'].values
    h08 = base['HTI_0800'].values
    h19 = base['HTI_1900'].values
    h1330 = (base['HTI_1330'].values if 'HTI_1330' in base.columns
             else np.full(len(base), np.nan))
    if timing == 'hk_close_usopen' and not np.isfinite(h1330).any():
        # refuse rather than quietly running an UNBRIDGED variant that
        # would look like a bridged one in the table
        raise ValueError(
            "timing 'hk_close_usopen' needs the 13:30Z HTI capture "
            f"({SNAP_US_OPEN_PATH}); clone the 08:00Z/19:00Z job at a "
            "UTC-FIXED 13:30 (not 09:30 ET, which drifts an hour in "
            "winter) and re-run")
    idxo = (base['IDX_open'].values if 'IDX_open' in base.columns
            else np.full(len(base), np.nan))
    idxo = np.where(np.isfinite(idxo), idxo, base['HTI_0800'].values)
    # the timing picks its own signal clock, and every gate reads the SAME
    # series the entries are taken on [L5]
    if intraday:
        bd = basket['basket_dev16'].values
        bz = basket['basket_z16'].values
        breadth = basket['breadth16'].values
        _gate_src = basket['basket_dev16']
        _bp = basket['basket_prem16']
    else:
        bd = basket['basket_dev'].values
        bz = basket['basket_z'].values
        breadth = basket['breadth'].values
        _gate_src = basket['basket_dev']
        _bp = basket['basket_prem']
    n_incl = basket['n_incl'].values
    ord_open_px = mats['ORD_open'].values
    ord_close_px = mats['ORD_close'].values
    adr_px = mats['ADR_close'].values
    adr_open_px = mats['ADR_open'].values
    Wv = W.values
    prior_arr = np.array([UNIVERSE[nm]['beta_prior'] for nm in NAMES])
    lot_arr = np.array([float(UNIVERSE[nm]['lot']) for nm in NAMES])
    ratio_arr = np.array([UNIVERSE[nm]['ratio'] for nm in NAMES])
    n = len(dates)
    # [B8b] per-name half-spreads: ords estimated per DATE, ADRs assumed
    if ord_hs is not None:
        ord_hs_v = ord_hs.reindex(index=mats['ORD_close'].index,
                                  columns=NAMES).values
    else:
        ord_hs_v = np.full((n, len(NAMES)), float(ORD_HALF_SPREAD_BPS))
    adr_hs_v = np.array([adr_half_spread_bps(nm) for nm in NAMES],
                        dtype=float)
    # per-name deviations, only needed by SIGN_FILTER='exclude'
    dev_v = (dev.reindex(index=mats['ORD_close'].index,
                         columns=NAMES).values if dev is not None else None)
    # [B8] carry: SOFR prefix sums, ACT/360 on CALENDAR days. The rate used
    # over (t-1, t] is the one KNOWN at t-1 — SOFR prints a day late, and
    # the panel already shifted it once, so this is belt and braces.
    sofr = (base['SOFR_pct'].values / 100.0 if 'SOFR_pct' in base.columns
            else np.full(n, SOFR_FALLBACK_PCT / 100.0))
    dday = np.r_[0.0, np.diff(dts.values) / np.timedelta64(1, 'D')]
    fund_step = np.r_[0.0, (sofr[:-1] + FUNDING_SPREAD_BPS / 1e4)
                      * dday[1:] / 360.0]
    reb_step = np.r_[0.0, (sofr[:-1] - BORROW_SPREAD_BPS / 1e4)
                     * dday[1:] / 360.0]
    fund_cum = np.cumsum(fund_step)
    reb_cum = np.cumsum(reb_step)
    gs = gate_series(_gate_src).values
    adf_p, gamma = signal_stats(gs)
    # [Z3]-faithful drift gate: the RAW premium's rolling-mean repricing in
    # trend-free daily-change sigmas (basket_dev's own mean is ~0 by
    # construction — running drift there is a null test)
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
    ord_fill_t = -1
    entry_dev = entry_z = exit_dev = 0.0
    pkg_notional = 0.0
    trade_costs = 0.0
    adr_entry_val = ord_entry_val = 0.0
    bridge_pnl = 0.0
    br_used = 0.0
    margin_usd = 0.0
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
        """Futures fees + both half-spreads for ONE bridge window."""
        if not bridged or br_used <= 0:
            return 0.0
        return (pkg_notional * br_used
                * (2 * FUT_FEE_BPS + FUT_HALF_SPREAD_BPS
                   + FUT_HALF_SPREAD_DAY_BPS) / 1e4 * cost_mult)

    def bridge_margin_usd(sig_t, nights=1.0):
        """Funding HK$31,574 of initial margin per HTI contract for the
        window. Charged into CARRY (it is financing, not execution)."""
        if not bridged or br_used <= 0:
            return 0.0
        lvl = h19[sig_t] if np.isfinite(h19[sig_t]) else h08[sig_t]
        if not (np.isfinite(lvl) and lvl > 0 and np.isfinite(fx[sig_t])):
            return 0.0
        ct = max(1.0, round(br_used * pkg_notional * fx[sig_t]
                            / (lvl * IDX_FUT_MULTIPLIER)))
        marg = ct * MARGIN_HKD_PER_CONTRACT / fx[sig_t]
        return -(marg * (MARGIN_FUND_SPREAD_BPS / 1e4)
                 * max(nights, 1.0) / 360.0 * cost_mult)

    def adr_fill_px(t):
        """The ADR fill print for this timing: the US close everywhere
        except 'hk_close_usopen', which fills at the US OPEN."""
        if timing == 'hk_close_usopen':
            px = adr_open_px[t]
            return np.where(np.isfinite(px), px, adr_px[t])
        return adr_px[t]

    def adr_exit_px():
        """Exit prints for the ADR legs, with a last-finite-close fallback:
        a halted ADR must not silently mark to zero (nansum would drop it
        from the exit value while the entry value still counts it)."""
        px = np.array(adr_fill_px(x_sig), dtype=float)
        bad = ~np.isfinite(px) & (np.abs(leg_adr_sh) > 0)
        for i in np.nonzero(bad)[0]:
            col = adr_px[:x_sig + 1, i]
            fin = col[np.isfinite(col)]
            px[i] = fin[-1] if len(fin) else 0.0
        return px

    def ord_cross_cost(t):
        """One ord crossing in USD — fees + the ESTIMATED half-spread of
        the legs actually held, weighted by their own weights."""
        w = np.abs(leg_w) if leg_w is not None else None
        sw = float(np.nansum(w)) if w is not None else 0.0
        hs = (float(np.nansum(w * ord_hs_v[t])) / sw if sw > 0
              else _ord_hs())
        return pkg_notional * ord_side_cost_bps(hs) / 1e4 * cost_mult

    def adr_cross_cost():
        """One ADR crossing in USD — fees + the ASSUMED half-spread."""
        w = np.abs(leg_w) if leg_w is not None else None
        sw = float(np.nansum(w)) if w is not None else 0.0
        hs = (float(np.nansum(w * adr_hs_v)) / sw if sw > 0 else _adr_hs())
        return pkg_notional * adr_side_cost_bps(hs) / 1e4 * cost_mult

    def carry_parts(upto_t):
        """(funding paid, rebate earned, margin funded) in USD. The LONG
        leg pays SOFR + 120; the SHORT leg's proceeds earn SOFR - 50."""
        if e_sig < 0:
            return 0.0, 0.0, 0.0
        fund = reb = 0.0
        if adr_entry_val:
            a = abs(adr_entry_val)
            if pos == +1:                  # long ADRs -> funded
                fund -= a * (fund_cum[upto_t] - fund_cum[e_sig])
            else:                          # short ADRs -> proceeds earn
                reb += a * (reb_cum[upto_t] - reb_cum[e_sig])
        if ord_fill_t >= 0 and ord_entry_val:
            o = abs(ord_entry_val)
            t0 = min(ord_fill_t, upto_t)
            if pos == -1:                  # SHORT pkg = long ords -> funded
                fund -= o * (fund_cum[upto_t] - fund_cum[t0])
            else:                          # LONG pkg = short ords -> earn
                reb += o * (reb_cum[upto_t] - reb_cum[t0])
        return fund, reb, margin_usd

    def carry_usd(upto_t):
        f, r, m = carry_parts(upto_t)
        return f + r + m

    def mark(t, ord_on):
        m = np.nansum(leg_adr_sh * adr_px[t]) - adr_entry_val
        if ord_on:
            m += (np.nansum(leg_ord_sh * ord_close_px[t] / fx[t])
                  - ord_entry_val)
        return m + bridge_pnl + carry_usd(t)

    def book(t, ord_exit_val, why):
        nonlocal state, pos, realized, bridge_pnl
        adr_pnl = np.nansum(leg_adr_sh * adr_exit_px()) - adr_entry_val
        ord_pnl = ord_exit_val - ord_entry_val
        fund_c, reb_c, marg_c = carry_parts(t)
        carry = fund_c + reb_c + marg_c
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
            'funding': fund_c, 'rebate': reb_c, 'margin': marg_c,
            'costs': trade_costs, 'net_after_all': net,
            'exit_reason': why, 'timing': timing,
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
                trade_costs += adr_cross_cost()
                ord_entry_val = 0.0
                book(t, 0.0, 'scratched: no fillable ord legs')
                continue
            ord_entry_val = np.nansum(leg_ord_sh * ord_open_px[t] / fx[t])
            ord_fill_t = t
            trade_costs += ord_cross_cost(t)
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
            trade_costs += ord_cross_cost(t)
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
                x_sig = t
                exit_dev = d_bps
                exit_why = why
                if intraday:
                    # ord legs come off at THIS row's 08:00Z close; the
                    # bridge covers the still-live ADR side across the day
                    # and comes off when the ADR legs unwind at the US
                    # close — one row, one booking
                    ord_exit_val = 0.0
                    for i in range(len(NAMES)):
                        if leg_ord_sh[i] == 0:
                            continue
                        px = ord_close_px[t, i]
                        if not np.isfinite(px):
                            px = ord_open_px[t, i]
                        ord_exit_val += leg_ord_sh[i] * px / fx[t]
                    trade_costs += ord_cross_cost(t) + adr_cross_cost()
                    if bridged:
                        br_used = bridge_ratio(t)
                        trade_costs += bridge_leg_cost()
                        margin_usd += bridge_margin_usd(t, 1.0)
                        off = (h1330[t] if timing == 'hk_close_usopen'
                               else h19[t])
                        if (np.isfinite(off) and np.isfinite(h08[t])
                                and h08[t] > 0):
                            bridge_pnl += ((-pos) * br_used * pkg_notional
                                           * (off / h08[t] - 1.0))
                    book(t, ord_exit_val, why)
                    continue
                if t + 1 < n:
                    trade_costs += adr_cross_cost()
                    if bridged:
                        br_used = bridge_ratio(t)
                        trade_costs += bridge_leg_cost()
                        margin_usd += bridge_margin_usd(
                            t, max(gap_next[t], 1.0))
                    state = 3
                    equity[t] = realized + mark(t, True) - trade_costs
                    continue
                # last row: full unwind at today's closes
                trade_costs += adr_cross_cost() + ord_cross_cost(t)
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
            elif not intraday and (t + 1 >= n
                                   or gap_next[t] > MAX_ENTRY_GAP_DAYS):
                # only the two-row timings need a next session — the
                # intraday ones finish the package on this very row
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
            adr_fill = adr_fill_px(t)
            # [B3b] SIGN_FILTER: a name whose own deviation disagrees in
            # sign with the basket is diluting this package — 'exclude'
            # sits it out and the remaining weights renormalise
            sf = SIGN_FILTER if sign_filter is None else sign_filter
            if sf == 'exclude' and dev_v is not None:
                dsgn = np.sign(dev_v[t])
                keep_i = ~((dsgn != 0) & (dsgn != np.sign(bd[t])))
                if (leg_w * keep_i).sum() > 0:
                    leg_w = np.where(keep_i, leg_w, 0.0)
                    if leg_w.sum() > 0:
                        leg_w = leg_w / leg_w.sum()
            for i in range(len(NAMES)):
                if leg_w[i] <= 0:
                    continue
                ocx = ord_close_px[t, i]     # sizing proxy (fills at open)
                acx = adr_fill[i]
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
            ord_fill_t = -1
            margin_usd = 0.0
            entry_dev, entry_z = d_bps, z_t
            br_used = bridge_ratio(t)
            adr_entry_val = np.nansum(leg_adr_sh * adr_fill)
            ord_entry_val = 0.0
            bridge_pnl = 0.0
            if intraday:
                # ORD-FIRST: the ords fill at THIS row's 08:00Z close (the
                # signal's own print — a same-print fill, flagged in the
                # timing block), the bridge stands in for the ADR side
                # across the day, and the ADR legs land at the US close on
                # the SAME row. Package complete: straight to state 2.
                ord_entry_val = np.nansum(leg_ord_sh * ord_close_px[t]
                                          / fx[t])
                ord_fill_t = t
                trade_costs = ord_cross_cost(t) + adr_cross_cost()
                if bridged:
                    trade_costs += bridge_leg_cost()
                    margin_usd += bridge_margin_usd(t, 1.0)
                    off = (h1330[t] if timing == 'hk_close_usopen'
                           else h19[t])
                    if (np.isfinite(off) and np.isfinite(h08[t])
                            and h08[t] > 0):
                        bridge_pnl += (pos * br_used * pkg_notional
                                       * (off / h08[t] - 1.0))
                state = 2
                equity[t] = realized + mark(t, True) - trade_costs
                continue
            trade_costs = adr_cross_cost() + bridge_leg_cost()
            if bridged:
                margin_usd += bridge_margin_usd(t, max(gap_next[t], 1.0))
            state = 1
            equity[t] = realized + mark(t, False) - trade_costs
            continue
        equity[t] = realized

    # data ended mid-trade: force the remaining legs out at the last closes
    if state in (1, 2, 3):
        t_last = n - 1
        if state != 3:
            x_sig = t_last
            trade_costs += adr_cross_cost()
        exit_dev = bd[t_last] * 1e4 if np.isfinite(bd[t_last]) else np.nan
        if state == 1:
            leg_ord_sh = np.zeros(len(NAMES))
            ord_entry_val = 0.0
            ord_exit_val = 0.0
        else:
            trade_costs += ord_cross_cost(t_last)
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
# CHARTS — printed INLINE in a notebook (user 2026-08-02: "print the chart
# out instead of saving it in drive"), saved as PNG in a terminal.
# The desk box's "Matplotlib is currently using agg" warning came from
# forcing the Agg backend inside Jupyter; _setup_matplotlib() never does
# that. Palette/marks follow the house data-viz rules: one axis per panel
# (never twin y), thin marks, recessive grid, a validated categorical order
# (blue/orange/aqua/violet — checked for colour-blind separation), diverging
# blue-vs-red ONLY for signed things (LONG vs SHORT, profit vs loss), and
# direct labels on any low-contrast series.
# ============================================================================
VIZ = {'surface': '#fcfcfb', 'grid': '#e1e0d9', 'axis': '#c3c2b7',
       'ink': '#0b0b0b', 'ink2': '#52514e', 'faint': '#8a8981',
       's1': '#2a78d6', 's2': '#eb6834', 's3': '#1baf7a', 's4': '#4a3aa7',
       'pos': '#2a78d6', 'neg': '#e34948', 'mid': '#f0efec'}

def _setup_matplotlib():
    """(plt, inline?) — Agg ONLY in a terminal; never inside Jupyter."""
    inline = _in_jupyter()
    import matplotlib
    if not inline:
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        'figure.facecolor': VIZ['surface'], 'axes.facecolor': VIZ['surface'],
        'axes.edgecolor': VIZ['axis'], 'axes.labelcolor': VIZ['ink2'],
        'axes.titlesize': 10.5, 'axes.titleweight': 'semibold',
        'axes.titlecolor': VIZ['ink'], 'axes.titlelocation': 'left',
        'axes.grid': True, 'grid.color': VIZ['grid'], 'grid.linewidth': 0.6,
        'xtick.color': VIZ['ink2'], 'ytick.color': VIZ['ink2'],
        'xtick.labelsize': 8.5, 'ytick.labelsize': 8.5,
        'axes.spines.top': False, 'axes.spines.right': False,
        'legend.frameon': False, 'legend.fontsize': 8.5,
        'font.size': 9.5,
    })
    return plt, inline

def _finish(fig, plt, inline, stem):
    """Show inline, save, or both — per CHART_MODE."""
    mode = CHART_MODE
    if mode == 'auto':
        mode = 'inline' if inline else 'png'
    out = None
    if mode in ('png', 'both') and CHART_FILE:
        out = os.path.join(OUTPUT_DIR or '.', f'v33_{stem}.png')
        fig.savefig(out, dpi=120, facecolor=VIZ['surface'],
                    bbox_inches='tight')
    if mode in ('inline', 'both'):
        if inline:
            from IPython.display import display
            display(fig)
        else:
            plt.show()
    plt.close(fig)
    return out

def render_charts(basket, res, dev, timing_results, grid_net, floors):
    if CHART_MODE == 'off':
        return
    try:
        plt, inline = _setup_matplotlib()
    except Exception as e:
        print(f"\n  (charts skipped: {type(e).__name__}: {e})")
        return
    floor_s, floor_l = floors
    x = pd.to_datetime(basket.index)
    saved = []
    try:
        # ---- FIG 1: the signal, and where the packages sat ----
        fig, ax = plt.subplots(2, 1, figsize=(13, 7.5), sharex=True)
        ax[0].plot(x, basket['basket_dev'] * 1e4, lw=1.3, color=VIZ['s1'],
                   label='basket deviation')
        ax[0].axhline(floor_s, color=VIZ['ink2'], ls='--', lw=1.0)
        ax[0].axhline(floor_l, color=VIZ['ink2'], ls='--', lw=1.0)
        ax[0].axhline(0, color=VIZ['axis'], lw=0.8)
        ax[0].annotate(f'cost floor +{floor_s:.0f}', (x[-1], floor_s),
                       xytext=(4, 2), textcoords='offset points',
                       fontsize=8, color=VIZ['ink2'], va='bottom')
        ax[0].annotate(f'cost floor {floor_l:.0f}', (x[-1], floor_l),
                       xytext=(4, -2), textcoords='offset points',
                       fontsize=8, color=VIZ['ink2'], va='top')
        for t_ in res['trades']:
            ax[0].axvspan(pd.Timestamp(t_['entry_date']),
                          pd.Timestamp(t_['exit_date']), alpha=0.13,
                          lw=0, color=(VIZ['neg']
                                       if t_['dir'].startswith('SHORT')
                                       else VIZ['pos']))
        ax[0].set_title('Basket deviation (bps) — shaded = a package on '
                        '(blue LONG / red SHORT). Entries need the line '
                        'OUTSIDE the dashed floor.')
        ax[0].set_ylabel('bps')
        ax[0].legend(loc='upper left')
        ax[1].plot(x, basket['basket_z'], lw=1.3, color=VIZ['s1'],
                   label=f'basket z (N={N_WINDOW})')
        for lv in (Z_ENTRY_SHORT, -Z_ENTRY_LONG):
            ax[1].axhline(lv, color=VIZ['ink2'], ls='--', lw=1.0)
        ax[1].axhline(EXIT_Z, color=VIZ['axis'], lw=0.8)
        ax[1].set_title(f'Basket z — entry at +/-{Z_ENTRY_SHORT:.1f} '
                        f'(dashed), exit back through {EXIT_Z:.1f}')
        ax[1].set_ylabel('z')
        ax[1].legend(loc='upper left')
        fig.tight_layout()
        saved.append(_finish(fig, plt, inline, 'signal'))

        # ---- FIG 2: equity, drawdown, and the timings side by side ----
        fig, ax = plt.subplots(2, 1, figsize=(13, 7.5))
        eq = res['equity'].values
        ax[0].plot(x, eq, lw=1.6, color=VIZ['s1'])
        peak = pd.Series(eq).cummax().values
        ax[0].fill_between(x, eq, peak, where=(eq < peak), alpha=0.16,
                           lw=0, color=VIZ['neg'])
        ax[0].axhline(0, color=VIZ['axis'], lw=0.8)
        ax[0].annotate(f'${eq[-1]:,.0f}', (x[-1], eq[-1]), xytext=(5, 0),
                       textcoords='offset points', fontsize=9,
                       color=VIZ['ink'], va='center')
        ax[0].set_title(f'Package equity, US$ — realised + marked '
                        f'({timing_label(EXEC_TIMING).split(" (")[0]}); '
                        f'red = drawdown from the running peak')
        ax[0].set_ylabel('US$')
        cols = {'hti_close': VIZ['s1'], 'us_close': VIZ['s2'],
                'hk_close': VIZ['s3'], 'hk_close_usopen': VIZ['s4']}
        for tm, r in timing_results.items():
            lbl = tm + (' (NAKED)' if tm == 'us_close' else '')
            ax[1].plot(x, r['equity'].values, lw=1.4, color=cols.get(tm),
                       label=lbl)
            ax[1].annotate(f"{r['equity'].values[-1]:,.0f}",
                           (x[-1], r['equity'].values[-1]), xytext=(4, 0),
                           textcoords='offset points', fontsize=8,
                           color=VIZ['ink2'], va='center')
        ax[1].axhline(0, color=VIZ['axis'], lw=0.8)
        ax[1].set_title('Same signals, different execution clocks — the '
                        'gap between the curves IS the timing decision')
        ax[1].set_ylabel('US$')
        ax[1].legend(loc='upper left', ncol=2)
        fig.tight_layout()
        saved.append(_finish(fig, plt, inline, 'equity'))

        # ---- FIG 3: every stock on its own (the user asked for this) ----
        nn = len(NAMES)
        ncol = 4 if nn > 9 else 3
        nrow = int(np.ceil(nn / ncol))
        fig, axes = plt.subplots(nrow, ncol, figsize=(3.4 * ncol,
                                                      2.3 * nrow),
                                 sharex=True)
        axes = np.atleast_1d(axes).ravel()
        for i, nm in enumerate(NAMES):
            a = axes[i]
            d = dev[nm] * 1e4
            a.axhspan(floor_l, floor_s, color=VIZ['mid'], lw=0, zorder=0)
            a.plot(x, d, lw=0.9,
                   color=(VIZ['s2'] if UNIVERSE[nm].get('venue') == 'otc'
                          else VIZ['s1']))
            a.axhline(0, color=VIZ['axis'], lw=0.7)
            share = float(np.nanmean(np.abs(d) > floor_s) * 100)
            a.set_title(f"{nm}  {UNIVERSE[nm].get('venue', 'listed')}  "
                        f"{share:.0f}% of days past the floor", fontsize=9)
            a.tick_params(labelsize=7.5)
            if i % ncol == 0:
                a.set_ylabel('dev, bps', fontsize=8)
        for j in range(nn, len(axes)):
            axes[j].axis('off')
        # yearly ticks only — quarterly labels collide into mush at this
        # panel width (the "render it and look at it" step earns its keep)
        import matplotlib.dates as mdates
        for a in axes[:nn]:
            a.xaxis.set_major_locator(mdates.YearLocator())
            a.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
            for lab in a.get_xticklabels():
                lab.set_rotation(0)
        fig.suptitle('Per-name deviation vs the cost floor (grey band = '
                     'inside costs, nothing to trade). Orange = OTC line.',
                     fontsize=10.5, x=0.01, ha='left', color=VIZ['ink'])
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        saved.append(_finish(fig, plt, inline, 'per_name'))

        # ---- FIG 4: PnL under different thresholds ----
        if grid_net is not None and grid_net.size:
            fig, ax = plt.subplots(1, 2, figsize=(13, 4.6),
                                   gridspec_kw={'width_ratios': [1.25, 1]})
            G = grid_net.astype(float)
            lim = float(np.nanmax(np.abs(G.values))) or 1.0
            from matplotlib.colors import LinearSegmentedColormap
            cmap = LinearSegmentedColormap.from_list(
                'v33div', [VIZ['neg'], VIZ['mid'], VIZ['pos']])
            im = ax[0].imshow(G.values, cmap=cmap, vmin=-lim, vmax=lim,
                              aspect='auto')
            ax[0].set_xticks(range(len(G.columns)))
            ax[0].set_xticklabels([c.replace('Z=', '') for c in G.columns])
            ax[0].set_yticks(range(len(G.index)))
            ax[0].set_yticklabels([i.replace('N=', '') for i in G.index])
            ax[0].set_xlabel('z entry threshold')
            ax[0].set_ylabel('N (rolling window, days)')
            ax[0].grid(False)
            for r_ in range(G.shape[0]):
                for c_ in range(G.shape[1]):
                    v = G.values[r_, c_]
                    if np.isfinite(v):
                        ax[0].text(c_, r_, f"{v / 1e3:,.0f}",
                                   ha='center', va='center', fontsize=7,
                                   color=VIZ['ink'])
            ax[0].set_title('Net PnL after all costs, US$ thousands — red '
                            'loses, blue makes money')
            fig.colorbar(im, ax=ax[0], shrink=0.85).outline.set_visible(
                False)
            for k, nlab in enumerate(G.index):
                if k % max(1, len(G.index) // 4) and nlab != f"N={N_WINDOW}":
                    continue
                col = (VIZ['s1'] if nlab == f"N={N_WINDOW}"
                       else VIZ['faint'])
                ax[1].plot([float(c.replace('Z=', '')) for c in G.columns],
                           G.loc[nlab].values, lw=1.8 if col == VIZ['s1']
                           else 1.0, color=col, label=nlab,
                           marker='o', ms=4)
            ax[1].axhline(0, color=VIZ['axis'], lw=0.9)
            ax[1].set_xlabel('z entry threshold')
            ax[1].set_ylabel('net PnL, US$')
            ax[1].set_title('Same thing as lines — a broad plateau is '
                            'edge, a lone spike is fitting')
            ax[1].legend(loc='best')
            fig.tight_layout()
            saved.append(_finish(fig, plt, inline, 'thresholds'))
    except Exception as e:
        print(f"\n  (charts partially rendered: {type(e).__name__}: {e})")
    saved = [s for s in saved if s]
    if saved:
        print(f"\n  charts -> {os.path.dirname(os.path.abspath(saved[0]))}"
              f" ({len(saved)} files)")
    elif _in_jupyter():
        print("\n  charts displayed inline")

# ============================================================================
# MAIN RUN
# ============================================================================
def main():
    t_start = datetime.now()
    print("=" * 76)
    print("  v33 HK ADR BASKET BOOK — HS Tech pairs, HTI overnight bridge")
    print("  sign: prem > 0 = ADR RICH vs HK -> SHORT package | prem < 0 "
          "-> LONG package")
    print(f"  entry: basket z >= +{Z_ENTRY_SHORT:.2f} -> SHORT package | "
          f"z <= -{Z_ENTRY_LONG:.2f} -> LONG package (N={N_WINDOW})")
    print(f"  timing: {timing_label(EXEC_TIMING)}")
    print(f"  hedge ratio: {HEDGE_RATIO_MODE} | basket "
          f"US${NOTIONAL_BASKET:,.0f} | {len(NAMES)} names | "
          f"mode: {RUN_MODE.upper()}")
    print("=" * 76)
    print_model_explained()

    data = load_data()
    panel = build_panel(data)
    mats = build_matrices(panel)
    beta_df, corr_df = rolling_beta_panel(mats)
    divs_map = {nm: data['names'][nm].get('divs_ord', UNIVERSE[nm]['divs'])
                for nm in NAMES}
    adr_ex_map = {nm: data['names'][nm].get('adr_ex', []) for nm in NAMES}
    prem, prem16, fair = build_premium_panel(mats, beta_df, divs_map,
                                             adr_ex_map)
    suspect = spike_qc(prem, divs_map)
    coint_ok = coint_table(mats)
    earnings_map = {nm: data['names'][nm].get('earnings',
                                              UNIVERSE[nm]['earnings'])
                    for nm in NAMES}
    W = build_inclusion(mats, corr_df, coint_ok, earnings_map, suspect)
    print_funnel()
    # [B8b] spreads must exist BEFORE any cost/floor number is printed or
    # any backtest runs — the floor is derived from them
    ord_hs, adr_hs = estimate_half_spreads(mats, data)
    w_last = W.iloc[-1].fillna(0.0)
    w_sum = float(w_last.sum()) or 1.0
    _HS_CTX['ord'] = float((ord_hs.iloc[-1] * w_last).sum() / w_sum)
    _HS_CTX['adr'] = float((adr_hs * w_last).sum() / w_sum)
    basket, dev, Wd = basket_series(prem, prem16, W, N_WINDOW)

    # ---- per-name composition snapshot (latest aligned date) — every
    # statistic column names its own estimation window (user 2026-08-02:
    # the old 'struct prem' read as a 5-year number; the 5y is only the
    # SAMPLE length) ----
    bcol = f'beta (roll {BETA_WINDOW}d)'
    ccol = f'corr HTI ({CORR_WINDOW}d)'
    scol = f'struct prem ({N_WINDOW}d roll, bps)'
    rows = []
    prior_arr = {nm: UNIVERSE[nm]['beta_prior'] for nm in NAMES}
    ratio_flags = []
    for nm in NAMES:
        u = UNIVERSE[nm]
        sp = prem[nm].rolling(N_WINDOW).mean().iloc[-1] * 1e4
        if np.isfinite(sp) and abs(sp) > RATIO_CHECK_BPS:
            ratio_flags.append((nm, sp))
        rows.append({
            'name': f"{_short(u['adr'])} / {_short(u['ord'])}",
            'venue': u.get('venue', 'listed'),
            'ratio': u['ratio'],
            'beta prior': prior_arr[nm],
            bcol: beta_df[nm].iloc[-1],
            ccol: corr_df[nm].iloc[-1],
            'weight': Wd.iloc[-1][nm],
            scol: sp,
            'dev latest (bps)': dev[nm].iloc[-1] * 1e4,
        })
    show_table(pd.DataFrame(rows).set_index('name'),
               title=f'[B0] basket composition & prior drift — latest '
                     f'{basket.index[-1]} (N={N_WINDOW}) | basket z '
                     f'{basket["basket_z"].iloc[-1]:+.2f}',
               note='dev = premium minus the name\'s own '
                    f'{N_WINDOW}d rolling mean: positive = the ADR side '
                    'rich vs the HK line. struct prem is that ROLLING mean '
                    f'— NOT a {LOOKBACK_DAYS // 365}-year average; the '
                    f'{LOOKBACK_DAYS // 365}y lookback is only the sample '
                    'length. [B5] the bridge is sized off the static '
                    'PRIORS — the rolling column exists so a drifted prior '
                    'is VISIBLE, not because the engine needs it.',
               fmt={'ratio': '{:g}', 'beta prior': '{:.2f}',
                    bcol: '{:.2f}', ccol: '{:.2f}',
                    'weight': '{:.1%}', scol: '{:+,.0f}',
                    'dev latest (bps)': '{:+,.0f}'})
    for nm, sp in ratio_flags:
        print(f"  [B0] CHECK RATIO {nm}: structural premium {sp:+,.0f} bps "
              f"(> {RATIO_CHECK_BPS:.0f}) — verify ADS ratio "
              f"{UNIVERSE[nm]['ratio']:g} on DES. A wrong ratio ALSO "
              f"shrinks this name's deviations and mis-sizes its ADR leg; "
              f"z is scale-free and will not warn you.")
    if ratio_flags:
        sc('WARN', 'ADS ratio [B0]',
           f"{len(ratio_flags)} name(s) with |structural premium| > "
           f"{RATIO_CHECK_BPS:.0f} bps: "
           f"{', '.join(n for n, _ in ratio_flags)}")
    print_beta_prior_suggestions(beta_df)

    # ---- [B8] the cost stack, one fact per line, bps AND dollars ----
    rt = package_rt_cost_bps()
    floor_s, floor_l = dev_floor_bps()
    adv = rt * MIN_EDGE_ADVISORY
    lvl = 'INFO' if min(floor_s, abs(floor_l)) >= adv else 'WARN'
    sc(lvl, 'dev floor vs costs [S1]',
       f"RT ~{rt:.0f} bps ({EXEC_TIMING}) | floor +{floor_s:.0f}/"
       f"{floor_l:.0f} ({DEV_FLOOR_MODE}) | advisory {adv:.0f}")
    N0 = NOTIONAL_BASKET
    print("\n" + "=" * 76)
    print(f"  [B8] COST STACK — per side, bps of package notional and $ on "
          f"US${N0:,.0f}")
    print("=" * 76)
    ohs, ahs = _ord_hs(), _adr_hs()
    fee_mode = ('fees + estimated spread' if COST_FEES_MODE ==
                'fees_plus_spread' else 'all-in (spread inside the fee)')
    br_bps = bridge_window_cost_bps()
    mg_bps = margin_window_cost_bps()

    def _cl(label, bps, extra=''):
        print(f"    {label:<34} {bps:>6.2f} bps   "
              f"${bps / 1e4 * N0:>9,.0f}   {extra}")
    print(f"  convention: {fee_mode} | SPREAD_MODE={SPREAD_MODE}")
    _cl('ADR fee', ADR_FEE_BPS, 'desk: 2 bps per side')
    if COST_FEES_MODE != 'all_in':
        _cl('ADR half-spread (assumed)', ahs, 'no ADR high/low on the desk')
    _cl('ord fee', ORD_FEE_BPS, 'desk: 13 bps per side (stamp+levies+comm)')
    if COST_FEES_MODE != 'all_in':
        _cl(f'ord half-spread ({SPREAD_MODE})', ohs,
            '[B8b] desk observation' if SPREAD_MODE == 'assumed'
            else f'Corwin-Schultz, {SPREAD_EST_WINDOW}d median')
    _cl('FX (both HKD flows)', 2 * FX_HALF_SPREAD_BPS, 'pegged spot')
    if br_bps:
        _cl('HTI bridge window', br_bps,
            f'2x{FUT_FEE_BPS:.0f} fee + tail/day spreads x ratio')
        _cl('HTI margin funding', mg_bps,
            f'HK${MARGIN_HKD_PER_CONTRACT:,.0f}/ct at '
            f'{MARGIN_FUND_SPREAD_BPS:.0f} bps')
    _cl('ONE SIDE', entry_side_cost_bps())
    _cl('ROUND TRIP', rt)
    nc = net_carry_bps_per_day()
    print(f"    {'carry, net':<34} {nc:>6.2f} bps/day  "
          f"${nc / 1e4 * N0:>9,.0f}/day   long pays SOFR+"
          f"{FUNDING_SPREAD_BPS:.0f}, short earns SOFR-"
          f"{BORROW_SPREAD_BPS:.0f}")
    print(f"    {'carry over the avg hold':<34} {'':>6}          "
          f"{'':>10}   the SOFR level cancels on matched legs")
    print(f"  [B4] deviation floor ({DEV_FLOOR_MODE}): entry needs dev "
          f">= +{floor_s:.0f} / <= {floor_l:.0f} bps, ON TOP of the z "
          f"threshold")
    print(f"       floor = round trip {rt:.1f} x MIN_EDGE_HARD "
          f"{MIN_EDGE_HARD:.2f} = {rt * MIN_EDGE_HARD:.1f} bps"
          + (f" (+ {FLOOR_CARRY_DAYS}d carry)" if FLOOR_CARRY_DAYS else ""))
    print(f"       advisory margin x{MIN_EDGE_ADVISORY} = {adv:.0f} bps — "
          f"below that, edge is thin vs costs")
    print(f"  per-name borrow_bps in UNIVERSE is REFERENCE ONLY — not "
          f"charged; the SOFR-{BORROW_SPREAD_BPS:.0f} rebate is (HTB names "
          f"would need it back)")
    if INCLUDE_OTC and any(UNIVERSE[nm].get('venue') == 'otc'
                           for nm in NAMES):
        print("  OTC lines have NO closing auction: fills are the last "
              "print, and the wider half-spread above reflects that")

    # ---- [TZ] SIGNAL SURVIVAL: how much of the measured dislocation is
    # still there when the LAST leg actually fills? This is the whole
    # time-zone question, and it decides which timing can work at all.
    bins = [-1e9, floor_l, -25, 25, floor_s, 1e9]
    labs = [f'<= {floor_l:.0f}', f'({floor_l:.0f},-25]', '(-25,+25)',
            f'[+25,+{floor_s:.0f})', f'>= +{floor_s:.0f}']

    def _survival(sig, fill, title, note):
        d = pd.DataFrame({'sig': sig * 1e4, 'fill': fill * 1e4}).dropna()
        if len(d) <= 50:
            return None
        d['bucket'] = pd.cut(d['sig'], bins=bins, labels=labs)
        tz = d.groupby('bucket', observed=False).agg(
            days=('fill', 'size'), signal_bps=('sig', 'mean'),
            at_fill_bps=('fill', 'mean'))
        tz['kept %'] = (tz['at_fill_bps'] / tz['signal_bps'] * 100).where(
            tz['signal_bps'].abs() > 10)
        show_table(tz, title=title, note=note,
                   fmt={'days': '{:,.0f}', 'signal_bps': '{:+,.0f}',
                        'at_fill_bps': '{:+,.0f}', 'kept %': '{:,.0f}'})
        return tz

    _survival(basket['basket_dev'], basket['basket_dev16'].shift(-1),
              '[TZ1] US-CLOSE clock — signal tonight vs the premium at the '
              'NEXT HK close, where the ord legs fill (bps)',
              'The hti_close / us_close claim, quantified. The ADR legs '
              'fill on the signal print itself; this table asks whether '
              'the dislocation is still there for the ORD side. Outer '
              'rows that hold their level = the edge survives to the fill.')
    _survival(basket['basket_dev16'], basket['basket_dev'],
              '[TZ2] HK-CLOSE clock — signal at 08:00Z vs the premium at '
              'the SAME DAY US close, where the ADR legs fill (bps)',
              'The hk_close claim, quantified — and this is the answer to '
              '"should we signal at the HK close instead?". The ADR '
              'RE-PRICING IS THE CONVERGENCE: by the time the ADR leg can '
              'be filled, most of the measured gap has already closed, so '
              'the package goes on at what is left. Compare the kept % '
              'here with [TZ1] before believing any hk_close backtest.')

    # ---- base run at the configured cell ----
    res = run_basket_backtest(mats, basket, Wd, beta_df, collect_audit=True,
                              ord_hs=ord_hs, dev=dev)

    # ---- everything the VERDICT needs, computed BEFORE it is printed ----
    timing_results, cost_results, halves = {}, {}, {}
    for cm in (0.5, 1.0, 1.5, 2.0, 3.0):
        cost_results[cm] = run_basket_backtest(
            mats, basket, Wd, beta_df, cost_mult=cm, ord_hs=ord_hs, dev=dev)
    half_n = len(mats['base']) // 2
    for lbl, sl in (('first half', slice(0, half_n)),
                    ('second half', slice(half_n, None))):
        b3 = basket.copy()
        msk = ~basket.index.isin(basket.index[sl])
        b3.loc[msk, 'basket_z'] = np.nan
        b3.loc[msk, 'basket_z16'] = np.nan
        halves[lbl] = run_basket_backtest(mats, b3, Wd, beta_df,
                                          ord_hs=ord_hs, dev=dev)

    # ---- THE VERDICT — the one question this run exists to answer ----
    print("\n" + "=" * 76)
    print("  VERDICT — is this strategy profitable, after everything?")
    print("=" * 76)
    tr_all = res['trades']
    if not tr_all:
        print("  NO TRADES at the configured cell — nothing to judge.")
        print("  Read the blocked-entry tally below: either the floor is "
              "above anything the")
        print("  premium ever reaches, or a gate is shutting every "
              "crossing.")
    else:
        gross_notional = sum(t['notional'] for t in tr_all)
        net_bps = res['net'] / gross_notional * 1e4
        cost_bps = sum(t['costs'] for t in tr_all) / gross_notional * 1e4
        carry_bps = sum(t['carry'] for t in tr_all) / gross_notional * 1e4
        gross_bps = net_bps + cost_bps - carry_bps
        # where does the cost multiplier take the book through zero?
        be = None
        prev_cm, prev_net = None, None
        for cm in sorted(cost_results):
            nt = cost_results[cm]['net']
            if prev_net is not None and prev_net > 0 >= nt:
                be = prev_cm + (cm - prev_cm) * prev_net / (prev_net - nt)
                break
            prev_cm, prev_net = cm, nt
        print(f"  net after ALL costs      ${res['net']:>12,.0f}   "
              f"{net_bps:>+7.1f} bps per package traded")
        print(f"    gross (before costs)   "
              f"${gross_bps / 1e4 * gross_notional:>12,.0f}   "
              f"{gross_bps:>+7.1f} bps")
        print(f"    execution costs        "
              f"${-cost_bps / 1e4 * gross_notional:>12,.0f}   "
              f"{-cost_bps:>+7.1f} bps")
        print(f"    carry (fund/rebate/mgn)"
              f"${carry_bps / 1e4 * gross_notional:>12,.0f}   "
              f"{carry_bps:>+7.1f} bps")
        print(f"  trades                   {res['n_trades']:>12,}   "
              f"avg hold {res['avg_hold']:.1f} calendar days")
        print(f"  win rate                 {res['win_rate']:>11.1f}%")
        print(f"  t-stat on trade PnL      {res['tstat']:>12.2f}   "
              f"{'>2 = unlikely to be luck' if res['tstat'] and res['tstat'] > 2 else 'BELOW 2 — could be luck'}")
        print(f"  Sharpe                   {res['sharpe']:>12.2f}")
        print(f"  max drawdown             ${res['max_dd']:>12,.0f}")
        h1, h2 = halves['first half'], halves['second half']
        print(f"  first half               ${h1['net']:>12,.0f}   "
              f"{h1['n_trades']} trades, win "
              f"{h1['win_rate'] if h1['n_trades'] else float('nan'):.1f}%")
        print(f"  second half              ${h2['net']:>12,.0f}   "
              f"{h2['n_trades']} trades, win "
              f"{h2['win_rate'] if h2['n_trades'] else float('nan'):.1f}%")
        if h1['net'] > 0 and h2['net'] < h1['net'] * 0.5:
            print("    -> the edge DECAYS across the sample; the second "
                  "half is what to plan on")
        if be:
            print(f"  cost breakeven           x{be:>11.2f}   costs "
                  f"{(be - 1) * 100:.0f}% above the modelled stack wipe "
                  f"the book out")
        else:
            worst = max(cost_results)
            print(f"  cost breakeven           {'not reached':>12}   still "
                  f"${cost_results[worst]['net']:,.0f} at x{worst:.1f} "
                  f"costs")
        fails = [k for lv, k, _ in _SCORECARD if lv == 'FAIL']
        warns = [k for lv, k, _ in _SCORECARD if lv == 'WARN']
        if fails:
            print(f"  READ FIRST: {len(fails)} FAIL(s) in the scorecard — "
                  f"{', '.join(fails[:3])}")
        elif warns:
            print(f"  caveats: {len(warns)} WARN(s) in the scorecard — "
                  f"{', '.join(warns[:3])}")
    print(f"\n{'=' * 76}")
    print(f"  BASE RUN — N={N_WINDOW}, z +{Z_ENTRY_SHORT:.2f}/"
          f"-{Z_ENTRY_LONG:.2f}, floor +{floor_s:.0f}/{floor_l:.0f} bps, "
          f"exit z={EXIT_Z:.1f}, stop {TIME_STOP}d")
    print(f"  {timing_label(EXEC_TIMING)}")
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

    # ---- [B4] PnL UNDER DIFFERENT THRESHOLDS — the N x Z sweep ----
    t_grid = datetime.now()
    print(f"\n{'=' * 76}")
    print(f"  [B4] PnL UNDER DIFFERENT THRESHOLDS — {len(N_GRID)} windows x "
          f"{len(Z_GRID)} z levels = {len(N_GRID) * len(Z_GRID)} backtests")
    print(f"  every cell still pays the full cost stack and still clears "
          f"the +{floor_s:.0f}/{floor_l:.0f} bps floor")
    print(f"{'=' * 76}")
    grid_net = pd.DataFrame(index=[f"N={n_}" for n_ in N_GRID],
                            columns=[f"Z={z_}" for z_ in Z_GRID],
                            dtype=float)
    grid_tr, grid_win = grid_net.copy(), grid_net.copy()
    for n_ in N_GRID:
        bkN, devN, WdN = basket_series(prem, prem16, W, n_)
        for z_ in Z_GRID:
            r = run_basket_backtest(mats, bkN, WdN, beta_df, z_short=z_,
                                    z_long=z_, ord_hs=ord_hs, dev=devN)
            grid_net.loc[f"N={n_}", f"Z={z_}"] = r['net']
            grid_tr.loc[f"N={n_}", f"Z={z_}"] = r['n_trades']
            grid_win.loc[f"N={n_}", f"Z={z_}"] = r['win_rate']
    # mark the configured cell >...< and the best cell *...*
    cfg = (f"N={N_WINDOW}", f"Z={Z_ENTRY_SHORT}")
    flat = grid_net.stack()
    best = flat.idxmax() if len(flat.dropna()) else None
    shown = grid_net.map(lambda v: f"{v:,.0f}" if np.isfinite(v) else '—')
    if cfg[0] in shown.index and cfg[1] in shown.columns:
        shown.loc[cfg[0], cfg[1]] = f">{shown.loc[cfg[0], cfg[1]]}<"
    if best is not None:
        shown.loc[best[0], best[1]] = f"*{shown.loc[best[0], best[1]]}*"
    show_table(shown, title='net PnL after ALL costs, by (N window, Z '
                            'entry)',
               note='>x< = the configured cell | *x* = the best cell in '
                    'this sweep. A best cell far from the configured one, '
                    'or a surface that flips sign across neighbours, is '
                    'FITTING, not edge — prefer a broad plateau. Every '
                    'cell pays the same costs and clears the same floor.',
               fmt=None)
    show_table(grid_tr, title='trade count by cell', fmt='{:,.0f}')
    if GRID_SHOW_WIN:
        show_table(grid_win, title='win % by cell', fmt='{:.0f}')
    print(f"  ({len(N_GRID) * len(Z_GRID)} backtests in "
          f"{(datetime.now() - t_grid).seconds}s)")

    # ---- TIMING COMPARISON — each clock printed on its OWN terms ----
    print(f"\n{'=' * 76}")
    print("  [B2a] EXECUTION TIMINGS — different clocks, DIFFERENT signals")
    print(f"{'=' * 76}")
    TIMING_SPEC = {
        'hti_close': [
            'signal  US close (t): both sides <=2h stale',
            'ADR leg fills at that SAME close  <- same-print fill',
            'bridge  ON at the 19:00Z HTI close, rides overnight',
            'ord leg fills at the next HK opening auction (01:30Z)',
            'naked   none — the bridge covers the whole gap',
            'earnings the pair is locked before the 19:00-19:30 HKT slot',
        ],
        'us_close': [
            'signal  US close (t)',
            'ADR leg fills MOC at 20:00/21:00Z  <- same-print fill',
            'bridge  NONE — the HTI T+1 session shut at 19:00Z',
            'ord leg fills at the next HK opening auction (01:30Z)',
            'naked   ~5h, EVERY entry and EVERY exit, unhedged',
            'the overnight gap lands in the real fills, not assumed away',
        ],
        'hk_close': [
            'signal  HK close 08:00Z (t): ord fresh, ADR ~12h stale',
            'ord leg fills at that SAME close  <- same-print fill',
            'bridge  ON at the 08:00Z HTI print',
            'ADR leg fills at the US close the SAME evening',
            'naked   none, but see [TZ2]: the ADR re-prices BEFORE we fill',
            'earnings the 19:00-19:30 HKT slot is INSIDE the one-leg window',
        ],
        'hk_close_usopen': [
            'signal  HK close 08:00Z (t)',
            'ord leg fills at that SAME close  <- same-print fill',
            'bridge  ON at 08:00Z, OFF at the 13:30Z capture',
            'ADR leg fills at the US OPEN (~6.5h after the signal)',
            'naked   none; needs the 13:30Z capture job to exist',
            'DST     13:30Z is the US open in summer only; ~1h early in '
            'winter',
        ],
    }
    rows = []
    for tm in ('hti_close', 'us_close', 'hk_close', 'hk_close_usopen'):
        try:
            r = run_basket_backtest(mats, basket, Wd, beta_df,
                                    exec_timing=tm, ord_hs=ord_hs, dev=dev)
        except ValueError as e:
            print(f"\n  {timing_label(tm)}")
            print(f"    SKIPPED — {e}")
            sc('INFO', f'timing {tm}', f'skipped: {e}')
            continue
        print(f"\n  {timing_label(tm)}")
        for ln in TIMING_SPEC[tm]:
            print(f"    {ln}")
        if r['n_trades']:
            bps = r['net'] / (NOTIONAL_BASKET * max(r['n_trades'], 1)) * 1e4
            print(f"    RESULT  {r['n_trades']} trades | net "
                  f"${r['net']:,.0f} ({bps:+,.0f} bps per package) | win "
                  f"{r['win_rate']:.1f}% | Sharpe {r['sharpe']:.2f}")
        else:
            print("    RESULT  no trades")
        rows.append({'timing': tm, 'trades': r['n_trades'],
                     'net $': r['net'], 'win %': r['win_rate'],
                     'Sharpe': r['sharpe'],
                     'bridge $': sum(t['bridge_pnl']
                                     for t in r['trades'])})
        timing_results[tm] = r
    show_table(pd.DataFrame(rows).set_index('timing'),
               title='[B2a] timings head to head',
               note='hti_close and us_close share ONE signal clock (the US '
                    'close) so their rows are directly comparable — the '
                    'gap between them is the realised price of the naked '
                    'window. The hk_close rows signal off a DIFFERENT '
                    'clock (08:00Z), so they are a different strategy, not '
                    'a cheaper execution of this one — read [TZ2] first.',
               fmt={'trades': '{:,.0f}', 'net $': '{:,.0f}',
                    'win %': '{:.1f}', 'Sharpe': '{:.2f}',
                    'bridge $': '{:+,.0f}'})

    # ---- ROBUSTNESS ----
    rows = []
    for cm in sorted(cost_results):
        if cm == 1.0:
            continue
        r = cost_results[cm]
        rows.append({'variant': f'costs x{cm:.1f}', 'trades': r['n_trades'],
                     'net $': r['net'], 'win %': r['win_rate'],
                     'Sharpe': r['sharpe']})
    for sf in ('include', 'exclude'):
        r = run_basket_backtest(mats, basket, Wd, beta_df, sign_filter=sf,
                                ord_hs=ord_hs, dev=dev)
        rows.append({'variant': f'SIGN_FILTER {sf}', 'trades': r['n_trades'],
                     'net $': r['net'], 'win %': r['win_rate'],
                     'Sharpe': r['sharpe']})
    show_table(pd.DataFrame(rows).set_index('variant'),
               title='robustness — cost multiplier and sign filter',
               note='SIGN_FILTER answers "if the basket is rich overall '
                    'but one or two names show a discount, should they be '
                    'excluded?" — include = trade the whole basket, '
                    'exclude = those names sit that package out. The '
                    'common premium factor is what the basket monetises, '
                    'so the disagreeing names are dilution, not hedge.',
               fmt={'trades': '{:,.0f}', 'net $': '{:,.0f}',
                    'win %': '{:.1f}', 'Sharpe': '{:.2f}'})

    # ---- [B3b] DISPERSION: how often does the basket disagree with
    # itself? (user 2026-08-02: "one or two stocks are showing discount,
    # they should be excluded or not?") ----
    entry_days = [t['entry_day'] for t in res['trades']]
    if entry_days:
        dv = dev.values
        bdv = basket['basket_dev'].values
        Wv_ = Wd.values
        n_dis, w_dis, rows = [], [], []
        for t_ in entry_days:
            sgn = np.sign(dv[t_])
            bad = (sgn != 0) & (sgn != np.sign(bdv[t_])) & (Wv_[t_] > 0)
            n_dis.append(int(bad.sum()))
            w_dis.append(float(np.nansum(Wv_[t_][bad])))
        n_dis, w_dis = np.array(n_dis), np.array(w_dis)
        rows = [
            {'measure': 'entry days with >=1 disagreeing name',
             'value': float((n_dis >= 1).mean() * 100), 'unit': '%'},
            {'measure': 'entry days with >=2 disagreeing names',
             'value': float((n_dis >= 2).mean() * 100), 'unit': '%'},
            {'measure': 'avg disagreeing names per entry',
             'value': float(n_dis.mean()), 'unit': 'names'},
            {'measure': 'avg weight sitting on the wrong side',
             'value': float(w_dis.mean() * 100), 'unit': '% of package'},
        ]
        show_table(pd.DataFrame(rows).set_index('measure'),
                   title='[B3b] basket dispersion at entry — how much of '
                         'the package disagrees with its own signal',
                   note='These names are not a hedge: the basket earns its '
                        'money from the COMMON premium factor, so a name '
                        'pulling the other way is dilution plus its own '
                        'costs. The breadth gate already refuses days '
                        f'below {BREADTH_MIN:.0%} agreement; SIGN_FILTER '
                        'in the robustness table prices dropping the '
                        'stragglers on the days that do pass.',
                   fmt={'value': '{:,.1f}'})

    # drop-one-name: a basket that dies without one name is that name in
    # disguise — the whole point of the basket is that it should NOT be
    rows = []
    for drop in NAMES:
        W2 = W.copy()
        W2[drop] = 0.0
        W2 = W2.div(W2.sum(axis=1).replace(0, np.nan), axis=0)
        bk2, dev2, Wd2 = basket_series(prem, prem16, W2, N_WINDOW)
        r = run_basket_backtest(mats, bk2, Wd2, beta_df, ord_hs=ord_hs,
                                dev=dev2)
        rows.append({'without': drop, 'trades': r['n_trades'],
                     'net $': r['net'], 'win %': r['win_rate']})
    dropone = pd.DataFrame(rows).set_index('without')
    show_table(dropone,
               title='robustness — drop-one-name (basket must survive '
                     'every amputation)',
               note='A name whose REMOVAL improves the book is carrying '
                    'cost without edge — check its beta prior and its '
                    'weight before the next run.',
               fmt={'trades': '{:,.0f}', 'net $': '{:,.0f}',
                    'win %': '{:.1f}'})

    print("\n  robustness — sample halves (is the edge still there "
          "recently?)")
    for lbl, r in halves.items():
        print(f"  {lbl:<12} trades {r['n_trades']:>4} | net "
              f"${r['net']:>12,.0f} | win "
              f"{r['win_rate'] if r['n_trades'] else float('nan'):.1f}%")

    # ---- charts ----
    render_charts(basket, res, dev, timing_results, grid_net,
                  (floor_s, floor_l))

    # ---- RUN_MODE='today': the screen, kept OFF by default. This file is
    # a BACKTEST at this stage (user 2026-08-03) — the question is whether
    # the strategy is profitable, not what to trade tonight.
    if RUN_MODE == 'today':
        print("\n" + "=" * 76)
        print("  TODAY SCREEN — reference only, NOT a backtested "
              "instruction")
        print("=" * 76)
        last = basket.index[-1]
        z_now = basket['basket_z'].iloc[-1]
        d_now = basket['basket_dev'].iloc[-1] * 1e4
        br_now = basket['breadth'].iloc[-1]
        act = 'FLAT — nothing clears the gates'
        if np.isfinite(z_now) and np.isfinite(d_now):
            if z_now >= Z_ENTRY_SHORT and d_now >= floor_s:
                act = 'SHORT package (sell ADRs / buy ords)'
            elif z_now <= -Z_ENTRY_LONG and d_now <= floor_l:
                act = 'LONG package (buy ADRs / short ords)'
        print(f"  as of                {last}")
        print(f"  basket z             {z_now:+.2f}   (entry at "
              f"+/-{Z_ENTRY_SHORT:.2f})")
        print(f"  basket deviation     {d_now:+,.0f} bps   (floor "
              f"+{floor_s:.0f}/{floor_l:.0f})")
        print(f"  breadth              {br_now:.0%}   (needs "
              f">={BREADTH_MIN:.0%})")
        print(f"  would-be action      {act}")

    print_scorecard()
    print(f"\n  run finished in {(datetime.now() - t_start).seconds}s | "
          f"mode={data['mode']} | {len(mats['base'])} dates | "
          f"{len(NAMES)} names")
    return res

if __name__ == '__main__' or _in_jupyter():
    RESULT = main()
