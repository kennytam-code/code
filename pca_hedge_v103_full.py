# October 2026 revision: broad basket/single search and portable setup.
# Historical notes below describe earlier revisions; their synthetic
# experiment claims are not validation results for this revision.
# =============================================================================
# PCA HEDGE FINDER — complete source, v105 (Fixes 1-123)
# =============================================================================
# Built 30 Jul 2026; v104 pass 1 Aug 2026; v105 pass 16 Aug 2026.
#
# ── v105 — WHAT THE TOOL COULD NOT SEE ──────────────────────────────────────
# Prompted by a live hedge that underperformed. The estimation core turned out
# to be fine; the gaps were in what could enter the universe and what the
# report was allowed to conclude.
#
# [Fix 119] THE UNIVERSE HAD NO IDEA WHAT THE TARGET WAS EXPOSED TO. CONTROL_ETFS
#           held broad-market and style wrappers only — across the whole file
#           there was not one commodity, rates or sector instrument. A gold
#           miner was hedged with other equities, an airline got no fuel leg, a
#           REIT no duration leg. Measured (synthetic ASX-miner universe, 250
#           paired seeds, 63-day OOS): supplying the missing exposure cut
#           tracking error 22.76% → 21.28%/yr, 7% relative, winning 240 of 250.
#           Hard-coding one market's gold ETFs would have fixed one ticker, so
#           instead the BICS/GICS taxonomy this file ALREADY pulls now decides
#           which exposures a target carries (HEDGE_EXPOSURES) and each resolves
#           to an instrument listed in the target's own market
#           (MARKET_INSTRUMENTS). Everything is an ETF on purpose: no ticker
#           formatter change, no timezone cost, and the market-cap exemption
#           applies. An exposure with no instrument for that market is REPORTED
#           — "the hedge was built WITHOUT that leg" — because a universe that
#           quietly lacks the thing the target moves with is the failure this
#           whole pass exists to stop. The instrument tables are stamped into
#           the download fingerprint, so a cache from before an edit says so
#           instead of silently serving yesterday's universe.
# [Fix 118] ETF MEMBERSHIP BY FULL TICKER. The cap floor, the PIT gate and the
#           single-instrument benchmark all asked "is this an ETF?" of the SHORT
#           NAME. Safe while the list held only broad wrappers; not once local
#           instruments are added, because short names collide across exchanges.
#           'GOLD US Equity' is Barrick Gold — adding an ASX bullion ETF named
#           GOLD would have made BARRICK read as an ETF everywhere: exempt from
#           the cap floor, exempt from point-in-time membership, and eligible to
#           win the "best single ETF" benchmark the report is framed against.
# [Fix 120] LOOK-AHEAD IN CANDIDATE ELIGIBILITY. _walk_forward_cv required a
#           name to have complete data in the TEST window before it could enter
#           the basket — a name was admitted only if it had prices in the
#           stretch it was about to be graded on. _select_and_fit never did
#           this, so the live path and the scoring path disagreed about who was
#           eligible. Eligibility is now decided on training data alone.
# [Fix 121] THE HEDGED BOOK'S DRIFT WAS COMPUTED, USED, THEN THROWN AWAY.
#           RidgeCV fits an intercept and reg.predict() subtracts it in every
#           scored window, but the traded recipe is reg_f.coef_ alone. Since TE
#           is a standard deviation, a constant never appears in it: the risk
#           figures described dispersion around a mean that had been removed.
#           Measured (400 seeds, 63-day hold): at 30%/yr relative drift the
#           reported 1σ stayed flat at 8.64% while realised mean P&L was 6.98%.
#           Now reported, never subtracted, and explicitly not a forecast.
# [Fix 122] NOTHING IN THE FILE CONDITIONED ON THE MARKET FALLING. Every
#           statistic was a symmetric second moment, and the ridge loss prices
#           an up-day and a down-day error identically. Correlations rise in the
#           left tail (Ang-Chen 2002; Longin-Solnik 2001), so a hedge fitted on
#           the average day can under-protect on the day it is held for while TE
#           barely moves: lifting the hedge's beta only in the worst 20% of days
#           moved TE 15.8% → 16.9%/yr while the worst-decile residual went
#           -0.04% → -0.72% PER DAY. Reported, not optimised — selecting on a
#           semivariance halves the sample to estimate a noisier quantity, the
#           trap [Fix 112] already refused.
# [Fix 123] MAX DRAWDOWN. The hedged cumulative series was built solely to be
#           drawn on a chart and then discarded, so no peak-to-trough number
#           existed anywhere. A 1σ figure says how wide the spread scatters; it
#           does not say how far it went against a holder before recovering.
#
# ── v104 — READABILITY, RE-ENTRY, AND TWO STATISTICAL QUESTIONS ─────────────
# [Fix 104] EVERY BLOCK IS A TABLE, AND EVERY NUMBER CARRIES ITS MEANING.
#           The report mixed three renderers — styled HTML tables, bare
#           print() key-value lines, and print() rules — so in a notebook half
#           of it was a table and half was raw <pre> at the browser's default
#           monospace. The ticket lines were the worst: a 26-char label and
#           then an unbroken run of numbers, units and conditional clauses.
#           Everything now goes through _section / _kv_block / _print_table
#           with one font stack, and the dense ticket lines (SIZING, RIGHT
#           NOW, n-day HOLDS, HORIZON, refits, MONITOR) gained a WHAT IT MEANS
#           column that states the DECISION, not just the measurement.
# [Fix 105] WHY ROLLING R² GOES NEGATIVE WHILE TE LOOKS FINE. Reported on an
#           equal-weighted AAPL/TSLA/SK-Hynix basket: rolling R² ≈ -0.4 for
#           one stretch, +0.8 for the next. Not a bug — an asymmetry in the
#           standard definition. R² = 1 - Σresid²/Σ(y-ȳ)² removes the mean
#           from the DENOMINATOR but not the numerator, so directional drift
#           is charged in full; TE uses .std(), which removes it. A hedge that
#           halves the vol but drifts one target-sigma scores R² = -0.25 with
#           a perfectly healthy TE. Both are now computed and shown side by
#           side (strict R², variance-only R², and the drift penalty that is
#           exactly the gap), with a count of how many negative windows still
#           cut variance. On the synthetic reproduction: 9 of 13.
#           [Fix 105] also adds the HEDGEABLE CEILING — the share of the
#           target no combination of the candidates can span. For a
#           concentrated book that ceiling, not the model, is what limits R².
# [Fix 106] ONE ACTION AT A TIME. Clicking RUN or DOWNLOAD twice queued a
#           second full run (and a second Bloomberg download). Two causes:
#           nothing was disabled, and _run_engine buffered the engine's stdout
#           to the END of the run, so a multi-minute job showed a blank cell
#           and clicking again was reasonable. Now: single-flight guard,
#           buttons grey out, output streams live, elapsed time reported.
# [Fix 107] The form renders at the end of CELL 1 — no second cell.
# [Fix 108] RECENCY. The composite averages OOS R² over ALL folds, so a config
#           that decayed could still win on the mean; deterioration was only
#           WARNED about afterwards. Now every config carries its recent-fold
#           score and its per-fold decay slope, [1b] reports what a
#           recent-folds-only selection WOULD have picked, and recency_weight
#           lets the selection act on it. Default stays 0 on purpose — see the
#           reasoning at the code site.
# [Fix 109] ALTERNATIVES get the pick's full evidence: exact executable
#           weights, unseen-window OOS, rolling TE/R² through time, and the
#           recency split — so a challenger can actually be judged.
# [Fix 110] A SETTINGS table stating what each knob affected, including the
#           two that are routinely misread: book size is DISPLAY ONLY, and
#           hedge duration changes the REPORT but not the weights.
#
# ── v104.1 — THE DEFAULTS AND THE HORIZON, MEASURED ─────────────────────────
# Both were open questions rather than reported faults, so they were tested
# rather than argued. Synthetic worlds, paired seeds, honest nested OOS.
#
# [Fix 111] The horizon variance ratio may RAISE the reported risk, never
#           lower it. VR was clipped to [0.25, 4.0] and applied both ways, so
#           a VR of 0.25 HALVED the reported h-day risk. Measured, VR has
#           essentially no out-of-sample persistence — corr(VR_in, VR_out)
#           = -0.32..+0.18 — while the true ratio matters enormously
#           (corr(VR_out, realised) = +0.54..+0.86). Shrinking a risk number
#           on an estimate with no forecasting power is not defensible;
#           raising one is merely conservative. Now floored at 1.0.
# [Fix 112] The horizon stays OUT of the selection — now for a stronger
#           reason than [Fix 100] had. A horizon-scaled criterion (daily TE x
#           sqrt(VR_h)) needs no extra data, so it dodges [Fix 100]'s
#           objection entirely. Built and measured against realised
#           non-overlapping h-day TE: it is WORSE than plain daily selection
#           at h = 21/63/126, in both worlds, winning only 4-11 of 25 seeds,
#           and the damage GROWS with the horizon. Selecting on an
#           unforecastable quantity maximises its estimation error. Full
#           numbers at the code site.
# [Fix 114] REVIEW PASS on v104/104.1 — three defects found in my own work:
#           (a) _KVCTX is module-level, and nothing reset it. A run that
#               raised part-way through the report left its buffered rows
#               behind, and since the UI catches exceptions and lets you
#               re-run, the NEXT report opened with rows from the failed one.
#               Now reset at entry, and the two diagnostic try/excepts flush
#               rather than abandon their buffer.
#           (b) the [Fix 108] slope used groupby.apply(include_groups=False),
#               which only exists from pandas 2.2 — on an older kernel a
#               purely DIAGNOSTIC column would have taken the whole selection
#               down with a TypeError. Replaced with an explicit loop.
#           (c) the SHORT-SAMPLE path (sample_window='3m' etc.) still had its
#               own print()-based title/kv, so the one documented workflow
#               most likely to be read by someone in a hurry still produced
#               the packed monospace report [Fix 104] existed to remove — and
#               it is the tier where the reader most needs to be told what a
#               number means, because none of them are validated. Rebuilt on
#               the shared renderer with implications.
#           Also: both new diagnostics now say so when they fail instead of
#           vanishing. Measured and left alone: the per-alternative
#           walk-forwards cost +2.5s on a 254-name universe — cheap enough
#           that shrinking their window count (which would make them
#           incomparable to the pick) is not worth it.
# [Fix 113] The lookback grid is now data-aware. Measured: adding a 504-row
#           lookback is worth +0.015 nested R² (t=+3.2) on a concentrated
#           target — but ONLY with 4+ years of data. At the default 3-year
#           download it is chosen 0 times in 20 because it cannot be trained
#           before each validation window. The report says which case you are
#           in. Related: history beyond the walk-forward's fixed budget is
#           never read at all (2.5y and 5y give bit-identical picks), so a
#           longer LOOKBACK is the only thing more history buys.
#
# HOW TO USE (notebook): paste the whole file into ONE cell and run it. The
# form comes up by itself — there is no second cell any more ([Fix 107]).
# Set HEDGE_UI_AUTOSTART = False above it if you want the scripted path only,
# or call hedge_ui() by hand at any time.
#
# EXPORTING A HEDGE  [Fix 103]
#   The Export button (and export_result() from code) writes the finished
#   hedge as a WORD DOCUMENT — verdict, the trade as a table, risk and
#   monitoring levels, out-of-sample evidence, the exact settings, and the
#   full text report as an appendix — plus weights .csv for execution.
#   Destination: HEDGE_EXPORT_DIR, set in CELL 1 and editable in the form's
#   Data tab. Default:
#         G:\FIN_COMM\DeltaOne\Kenny\PCA
#   Needs `pip install python-docx`; without it a .txt report is written
#   instead so an export never silently fails. If the drive is not mapped
#   (or the notebook runs off Windows) it falls back to ./hedge_reports and
#   says so — note a Windows path is a LEGAL filename on macOS/Linux, so the
#   exporter checks the platform rather than trusting makedirs.
#
# v96-v102 statistical work, both of which overturned an earlier claim of
# mine and are documented at the code sites:
#   [Fix 97]  The "is it working now" check used to fire on the single
#             latest reading (TE > 1.25x its median). Measured on stable
#             synthetic hedges it downgraded 17% of them — one good hedge in
#             six, for nothing. It now scores a BLOCK of recent readings
#             against the hedge's own historical distribution and requires
#             persistence plus two independent signals: 0% false alarms,
#             92% detection of hedges that genuinely broke.
#   [Fix 100] hedge_horizon_days no longer re-cuts the validation windows.
#             Tested (train 600 rows, score the same weights on held-out
#             63-row blocks, 8 paired trials per regime): iid residuals
#             16.39% vs 16.43% (t=+0.44), AR(1) 0.6 residuals 20.57% vs
#             20.58% (t=+0.09) — no detectable benefit, and it costs
#             evidence. A hedge ratio is a covariance property, so daily
#             data targets the same quantity with ~60x more observations.
#             The horizon now scales reported risk, reports what holds of
#             that length actually delivered, and checks the refit need.
#             horizon_sets_windows=True restores the old behaviour.
#
# Verification (synthetic; Bloomberg not required): 65-check feature suite,
# 33-check adversarial suite, window-isolation proof (corrupting all
# pre-window history leaves basket and weights bit-identical), now-cast
# error-rate measurement, the horizon experiment, and a 21-check export
# suite. All passing. Live Bloomberg request flags still need one download
# run against a terminal.
# =============================================================================

# Revised from PCA.docx on 2026-10-11. See PCA_fix_notes.md.
# =============================================================================
# CELL 1: SETUP (run once)
# =============================================================================

import numpy as np
import pandas as pd
try:
    import blpapi
except ImportError:
    blpapi = None  # Cached analyses work without a Bloomberg connection.
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import RidgeCV
from statsmodels.tsa.stattools import adfuller
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as _mdates
import warnings
import re
import html as _html
import textwrap as _textwrap

# Keep numerical and compatibility warnings visible.

RIDGE_ALPHAS = np.logspace(-4, 2, 25)
MIN_RETURN_STD = 1e-12
PCA_REVISION = '2026-10-13-printed-report'
MIN_TRAIN_COVERAGE = 0.90


def _supported_plot_style(style, rc_params=None):
    """Keep only settings supported by the installed Matplotlib version."""
    params = plt.rcParams if rc_params is None else rc_params
    return {key: value for key, value in style.items() if key in params}


def _window_problem(frame, target, min_rows=2):
    """Describe data failures without confusing missing observations with flat returns."""
    if target not in frame.columns:
        return f'{target}: column missing'
    series = frame[target]
    if len(series) < min_rows:
        return f'{target}: only {len(series)} rows; need {min_rows}'
    bad = ~np.isfinite(series.to_numpy(dtype=float))
    if bad.any():
        dates = ', '.join(str(d.date()) for d in series.index[bad][:5])
        return f'{target}: {int(bad.sum())}/{len(series)} non-finite returns (dates: {dates})'
    sd = float(series.std(ddof=0))
    if sd <= MIN_RETURN_STD:
        return (f'{target}: constant/nearly constant returns; std={sd:.3g}, '
                f'{series.nunique()} distinct returns over {len(series)} rows')
    return None



def _training_rows(frame, target, min_rows=5):
    """Omit isolated missing TARGET rows from training, jointly across columns.

    Calendar boundaries remain fixed before cleaning. No price/return is
    imputed. Evaluation callers must apply this same target mask to EVERY
    candidate and must never drop basket-specific test gaps.
    Require at least 90% target coverage and the supplied retained-row floor.
    Returns (cleaned frame, problem or None, omitted dates).
    """
    if target not in frame:
        return frame, _window_problem(frame, target, min_rows), []
    good = np.isfinite(frame[target].to_numpy(dtype=float))
    omitted = list(frame.index[~good])
    clean = frame.loc[good]
    if len(frame) and good.mean() < MIN_TRAIN_COVERAGE:
        return clean, (f'{target}: only {int(good.sum())}/{len(frame)} finite '
                       f'target returns; need {MIN_TRAIN_COVERAGE:.0%} coverage'), omitted
    return clean, _window_problem(clean, target, min_rows), omitted

def _decision_fields(weights, grade):
    """Retain diagnostic weights, but provide no trade weights after a failed verdict."""
    eligible = str(grade).startswith(('✓', '△'))
    return {'trade_eligible': eligible,
            'recommended_action': ('REVIEW_CANDIDATE' if eligible else 'NO_VALIDATED_HEDGE'),
            'candidate_weights': weights.copy(),
            'trade_weights': weights.copy() if eligible else weights.iloc[:0].copy()}


def _trade_risk(y, spread, ann_sqrt):
    """Risk of the coefficient-only spread versus holding the target unhedged.

    An estimated regression intercept is not a traded instrument. These
    supplementary metrics therefore use y - X @ coefficients, not predict(X).
    Values use the existing log-return approximation and exclude trading costs.
    """
    y, spread = np.asarray(y, dtype=float), np.asarray(spread, dtype=float)
    if len(y) < 2 or not np.isfinite(y).all() or not np.isfinite(spread).all():
        return {}
    target_sd, spread_sd = float(np.std(y)), float(np.std(spread))
    if target_sd <= MIN_RETURN_STD:
        return {}
    return {'unhedged_vol_ann': target_sd * ann_sqrt,
            'hedged_vol_ann': spread_sd * ann_sqrt,
            'vol_reduction': 1.0 - spread_sd / target_sd,
            'variance_reduction': 1.0 - (spread_sd / target_sd) ** 2,
            'spread_mean_per_observation': float(np.mean(spread)),
            'n_observations': len(y)}


def _spread_path_stats(spread, two_day=False, source='coefficient-only spread'):
    """Descriptive log-spread path proxy, including the starting zero level.

    Two-day returns overlap; take one non-overlapping phase before cumulating.
    This is not exact self-financing portfolio P&L or a future drawdown forecast.
    """
    series = spread.dropna().iloc[::2] if two_day else spread.dropna()
    if not len(series):
        return {}
    cumulative = series.cumsum()
    running_peak = cumulative.cummax().clip(lower=0.0)
    drawdown = np.expm1(cumulative - running_peak)
    trough = drawdown.idxmin()
    before = cumulative.loc[:trough]
    peak = before.idxmax() if float(before.max()) > 0 else None
    # Five calendar trading days cannot be represented exactly by 2-day observations.
    worst_5d = (float(np.expm1(series.rolling(5).sum()).min())
                if not two_day and len(series) >= 5 else np.nan)
    return {'max_drawdown': float(drawdown.min()), 'peak': peak, 'trough': trough,
            'worst_5d': worst_5d, 'source': source, 'n_observations': len(series),
            'non_overlapping': True, 'path_proxy': True}

# ─────────────────────────────────────────────────────────────────────────────
# INDEX MAP: (market_code, sector_keyword) → Bloomberg Index Ticker
# [Fix 19] The key is the LISTING MARKET of the target (derived from its
# exchange code), except for ADRs where country-of-risk is used as fallback.
# ─────────────────────────────────────────────────────────────────────────────
INDEX_MAP = {
    # US — official S&P 500 sector indices (INDX_MEMBERS friendly)
    ('US', 'Broad'):                 'SPX Index',
    ('US', 'Technology'):            'NDX Index',
    ('US', 'Communication'):         'S5TELS Index',
    ('US', 'Financials'):            'S5FINL Index',
    ('US', 'Health Care'):           'S5HLTH Index',
    ('US', 'Energy'):                'S5ENRS Index',
    ('US', 'Consumer Discretionary'): 'S5COND Index',
    # CN — used for onshore listings AND as the ADR fallback
    # (US-listed China names → HXC, the Nasdaq Golden Dragon index)
    ('CN', 'Broad'):                 'SHSZ300 Index',   # CSI 300 (onshore)
    ('CN', 'Technology'):            'HXC Index',
    ('CN', 'Communication'):         'HXC Index',
    ('CN', 'Consumer Discretionary'): 'HXC Index',
    # HK — HK-listed names (incl. CN-domiciled ones like Tencent/Meituan)
    ('HK', 'Broad'):                 'HSI Index',       # Hang Seng
    ('HK', 'Technology'):            'HSTECH Index',    # Hang Seng Tech
    ('HK', 'Communication'):         'HSTECH Index',
    ('HK', 'Consumer Discretionary'): 'HSTECH Index',
    ('HK', 'Financials'):            'HSI Index',
    # Europe
    ('EU', 'Broad'):                 'SXXP Index',      # Stoxx Europe 600
    ('DE', 'Broad'):                 'DAX Index',
    ('FR', 'Broad'):                 'CAC Index',
    ('GB', 'Broad'):                 'UKX Index',
    # Japan — TOPIX (broader, cap-weighted) instead of Nikkei
    ('JP', 'Broad'):                 'TPX Index',
    ('JP', 'Technology'):            'TPX Index',
    ('JP', 'Financials'):            'TPNBNK Index',
    # Korea, India, Australia, Taiwan
    ('KR', 'Broad'):                 'KOSPI2 Index',
    ('KR', 'Technology'):            'KOSPI2 Index',
    ('IN', 'Broad'):                 'NIFTY Index',
    ('IN', 'Technology'):            'NIFTY Index',
    ('IN', 'Financials'):            'NIFTY Index',
    ('AU', 'Broad'):                 'AS51 Index',
    # [Fix 37] TW50 INDX_MEMBERS is licence-gated on many terminals and
    # returns 0 members — which silently stripped every TAIEX large cap
    # (2330 TT included) from the universe. Values may now be a tuple of
    # fallbacks, tried in order until one returns members.
    ('TW', 'Broad'):                 ('TW50 Index', 'TWSE Index'),
    ('TW', 'Technology'):            ('TW50 Index', 'TWSE Index'),
}

# ─────────────────────────────────────────────────────────────────────────────
# CONTROL ETFS by market (added to the universe as benchmark hedges)
# Each market lists US-listed wrappers AND locally-listed ETFs. Locally-listed
# ETFs trade in the same timezone and currency as local targets, so they avoid
# the async-trading bias and FX mismatch that US-listed wrappers carry.
# ─────────────────────────────────────────────────────────────────────────────
CONTROL_ETFS = {
    'CN': [
        # US-listed wrappers
        'KWEB US Equity', 'FXI US Equity', 'MCHI US Equity',
        'ASHR US Equity', 'CQQQ US Equity', 'GXC US Equity',
        # locally listed
        '510300 CH Equity',   # Huatai-PB CSI 300 ETF (Shanghai)
        '510050 CH Equity',   # ChinaAMC SSE 50 ETF (Shanghai)
        # [Fix 61] mid/small-cap onshore wrappers. Single A-share borrow is
        # scarce and expensive, so these are the practical short-side
        # instruments in China; they also proxy the IC / IM / STAR futures
        # complex, and they are the only way the engine can express a
        # small-cap tilt against an onshore target.
        '510500 CH Equity',   # ChinaAMC CSI 500 — mid cap (IC proxy)
        '512100 CH Equity',   # CSI 1000 — small cap (IM proxy)
        '588000 CH Equity',   # STAR 50
        '159915 CH Equity',   # ChiNext (Shenzhen)
        '2823 HK Equity',     # iShares FTSE China A50 (HK)
        '3188 HK Equity'],    # ChinaAMC CSI 300 (HK)
    'US': [
        # broad / size
        'SPY US Equity', 'QQQ US Equity', 'IWM US Equity', 'DIA US Equity',
        # style factors
        'MTUM US Equity', 'VLUE US Equity', 'QUAL US Equity',
        'USMV US Equity', 'VUG US Equity',
        # core sectors
        'XLK US Equity', 'XLF US Equity', 'XLV US Equity', 'XLE US Equity',
        'XLY US Equity', 'XLC US Equity', 'XLI US Equity'],
    'JP': ['EWJ US Equity', 'DXJ US Equity', 'BBJP US Equity',
           '1306 JT Equity',   # NEXT FUNDS TOPIX ETF (Tokyo)
           '1321 JT Equity'],  # NEXT FUNDS Nikkei 225 ETF (Tokyo)
    'HK': ['EWH US Equity', 'FLHK US Equity',
           '2800 HK Equity',   # Tracker Fund of Hong Kong (HSI)
           '2828 HK Equity',   # Hang Seng China Enterprises ETF
           '3033 HK Equity'],  # CSOP Hang Seng TECH ETF
    'KR': ['EWY US Equity', 'FLKR US Equity',
           '069500 KS Equity'],  # Samsung KODEX 200 (Seoul)
    'TW': ['0050 TT Equity',     # Yuanta Taiwan Top 50 (Taipei)
           '006208 TT Equity'],  # Fubon Taiwan 50 (Taipei)
    'IN': ['INDA US Equity', 'EPI US Equity', 'SMIN US Equity',
           'NIFTYBEES IN Equity'],  # Nippon India Nifty 50 BeES (NSE)
    'DE': ['EWG US Equity',
           'EXS1 GR Equity'],   # iShares Core DAX UCITS (Xetra)
    'GB': ['EWU US Equity',
           'ISF LN Equity',     # iShares Core FTSE 100 (London)
           'VUKE LN Equity'],   # Vanguard FTSE 100 (London)
    'FR': ['EWQ US Equity',
           'CAC FP Equity'],    # Amundi CAC 40 UCITS (Paris)
    'AU': ['EWA US Equity',
           'STW AU Equity',     # SPDR S&P/ASX 200 (ASX)
           'IOZ AU Equity'],    # iShares Core S&P/ASX 200 (ASX)
    # [Fix 43] cross-market style-factor wrappers, added to EVERY universe
    # so momentum / size / value / quality / low-vol have candidates even
    # for non-US targets (US-listed -> treated as async, 2-day returns).
    'FACTOR': ['MTUM US Equity', 'VLUE US Equity', 'QUAL US Equity',
               'USMV US Equity', 'SIZE US Equity', 'IWM US Equity',
               'SPY US Equity', 'IMTM US Equity', 'IVLU US Equity',
               'IQLT US Equity', 'ACWV US Equity'],
    'GLOBAL': ['ACWI US Equity', 'EEM US Equity', 'EFA US Equity', 'URTH US Equity'],
}

# Broad-market instruments are executable ETF proxies, never raw Index levels.
# Listing venue controls this map, including US-listed ADRs. Country-of-risk
# and sector discovery remain separate. Taiwan 50 is NOT the full TAIEX.
BROAD_MARKET_HEDGES = {
    'US': ('S&P 500', ('SPY US Equity',)),
    'HK': ('Hang Seng Index', ('2800 HK Equity',)),
    'TW': ('Taiwan 50 large-cap proxy for the Taiwan market',
           ('0050 TT Equity', '006208 TT Equity')),
    'JP': ('TOPIX', ('1306 JP Equity',)),
    'CN': ('CSI 300 large-cap A shares', ('510300 CH Equity',)),
    'KR': ('KOSPI 200 large caps', ('069500 KS Equity',)),
    'IN': ('Nifty 50 large caps', ('NIFTYBEES IN Equity',)),
    'DE': ('DAX large caps', ('EXS1 GR Equity',)),
    'GB': ('FTSE 100 large caps', ('ISF LN Equity', 'VUKE LN Equity')),
    'FR': ('CAC 40 large caps', ('CAC FP Equity',)),
    'AU': ('S&P/ASX 200', ('STW AU Equity', 'IOZ AU Equity')),
}


def _broad_market_spec(target):
    market = EXCH_TO_MARKET.get(_exch_of(target))
    label, instruments = BROAD_MARKET_HEDGES.get(market, ('No local proxy mapped', ()))
    return {'market': market, 'benchmark': label, 'instruments': list(instruments)}


# [Fix 14] ETF whitelist (short names) auto-generated — always in sync.
# [Fix 118] SUPERSEDED as a membership test by _is_etf() below, which matches on
# the full ticker; kept because external scripts may import it.
ETF_SHORT_SET = {t.split(' ')[0] for lst in CONTROL_ETFS.values() for t in lst}

# ─────────────────────────────────────────────────────────────────────────────
# [Fix 119] WHAT IS THIS TARGET ACTUALLY EXPOSED TO?
#
# CONTROL_ETFS holds broad-market and style wrappers only, so until now the
# candidate universe contained no commodity, rates or sector instrument at all.
# A gold miner was hedged with other equities, an airline got no fuel leg, a
# REIT got no duration leg. Measured on a synthetic ASX-miner universe (250
# paired seeds, 63-day OOS), supplying the missing exposure cut tracking error
# 22.76% → 21.28%/yr — 7% relative, winning 240 of 250 seeds.
#
# Hard-coding one market's gold ETFs would fix exactly one ticker. Instead the
# BICS/GICS taxonomy already pulled in auto_discover_universe decides WHICH
# exposures a target carries, and MARKET_INSTRUMENTS resolves each to the
# locally-listed instrument for that market.
#
# Everything here is an ' Equity' line (an ETF), which is deliberate on three
# counts: _fmt_bbg_ticker needs no change; a local listing closes with the
# target so the run never flips to 2-day overlapping returns; and _is_etf below
# exempts it from the market-cap floor. A 'Comdty'/'Curncy' ticker would do the
# opposite — _exch_of reads parts[-2], which on a two-token ticker returns the
# root symbol, so _close_utc_of returns None and has_unknown drops the WHOLE
# universe to 2-day returns.
#
# Keyword → exposure tags. Substring-matched, case-insensitive, against BICS
# levels 2/3/4 and the GICS sub-industry/industry names. Tags are unioned, so a
# diversified miner can carry two.
# ─────────────────────────────────────────────────────────────────────────────
HEDGE_EXPOSURES = {
    'gold':               ('GOLD',),
    'precious metal':     ('GOLD',),
    'silver':             ('GOLD',),
    'copper':             ('BASE_METALS',),
    'iron':               ('BASE_METALS',),
    'steel':              ('BASE_METALS',),
    'aluminum':           ('BASE_METALS',),
    'aluminium':          ('BASE_METALS',),
    'nickel':             ('BASE_METALS',),
    'zinc':               ('BASE_METALS',),
    'diversified mining': ('BASE_METALS',),
    'diversified metal':  ('BASE_METALS',),
    'metals & mining':    ('BASE_METALS',),
    'coal':               ('ENERGY',),
    'oil':                ('ENERGY',),
    'gas':                ('ENERGY',),
    'refin':              ('ENERGY',),
    'petroleum':          ('ENERGY',),
    'airline':            ('ENERGY',),     # jet fuel is the dominant cost line
    'semiconductor':      ('SEMIS',),
    'reit':               ('RATES', 'PROPERTY'),
    'real estate':        ('RATES', 'PROPERTY'),
    'bank':               ('RATES',),
    'insurance':          ('RATES',),
    'utilit':             ('RATES',),
    'homebuild':          ('RATES',),
    'home build':         ('RATES',),
    'uranium':            ('URANIUM',),
    'lithium':            ('BATTERY',),
}

# (market, exposure tag) → locally-listed instruments, most representative
# first. Resolution order is (market, tag) → (country, tag) → unresolved, and an
# unresolved tag is REPORTED rather than silently skipped: a hedge built without
# the leg its target most depends on is exactly the case the desk needs told.
#
# ⚠ EVERY MNEMONIC BELOW NEEDS ONE TERMINAL VERIFICATION PASS. A ticker that
# does not resolve returns no price data and its column is dropped silently by
# the 85%-history rule, so a typo degrades the hedge without ever erroring.
MARKET_INSTRUMENTS = {
    # ── Australia (ASX) ──────────────────────────────────────────────────────
    ('AU', 'GOLD'):         ['PMGOLD AU Equity'],   # Global X Gold Bullion
    ('AU', 'BASE_METALS'):  ['MVR AU Equity',       # VanEck Aus Resources
                             'OZR AU Equity'],      # SPDR ASX 200 Resources
    ('AU', 'ENERGY'):       ['FUEL AU Equity'],     # BetaShares Global Energy
    ('AU', 'RATES'):        ['IAF AU Equity'],      # iShares Core Comp Bond
    ('AU', 'PROPERTY'):     ['SLF AU Equity'],      # SPDR ASX 200 Property
    ('AU', 'URANIUM'):      ['ATOM AU Equity'],     # Global X Uranium
    ('AU', 'BATTERY'):      ['ACDC AU Equity'],     # Global X Battery/Lithium
    # ── United States ────────────────────────────────────────────────────────
    ('US', 'GOLD'):         ['GLD US Equity', 'GDX US Equity'],
    ('US', 'BASE_METALS'):  ['XME US Equity', 'COPX US Equity'],
    ('US', 'ENERGY'):       ['XLE US Equity', 'USO US Equity'],
    ('US', 'SEMIS'):        ['SMH US Equity', 'SOXX US Equity'],
    ('US', 'RATES'):        ['TLT US Equity', 'IEF US Equity'],
    ('US', 'PROPERTY'):     ['VNQ US Equity'],
    ('US', 'URANIUM'):      ['URA US Equity'],
    ('US', 'BATTERY'):      ['LIT US Equity'],
    # ── Hong Kong ────────────────────────────────────────────────────────────
    ('HK', 'GOLD'):         ['2840 HK Equity'],     # SPDR Gold Trust (HK line)
    # ── Japan ────────────────────────────────────────────────────────────────
    ('JP', 'GOLD'):         ['1540 JT Equity'],     # MUFJ Physical Gold
    ('JP', 'RATES'):        ['1482 JT Equity'],     # iShares Core JGB
    # ── United Kingdom ───────────────────────────────────────────────────────
    ('GB', 'GOLD'):         ['SGLN LN Equity'],     # iShares Physical Gold
    ('GB', 'RATES'):        ['IGLT LN Equity'],     # iShares Core UK Gilts
    # ── Taiwan / Korea / India / Europe: add as they are verified. An absent
    #    (market, tag) is not a failure — it prints the "built WITHOUT it" line.
}

# ─────────────────────────────────────────────────────────────────────────────
# Exchange code mappings
# ─────────────────────────────────────────────────────────────────────────────
EXCH_MAP = {
    'UQ': 'US', 'UW': 'US', 'UN': 'US', 'US': 'US', 'UA': 'US', 'UP': 'US',
    'HK': 'HK', 'LN': 'LN', 'JT': 'JP', 'GR': 'GR', 'GY': 'GR',
    'FP': 'FP', 'IM': 'IM', 'SM': 'SM', 'AU': 'AU', 'AV': 'AV',
    'IN': 'IN', 'IB': 'IN', 'SJ': 'SJ', 'KS': 'KS', 'KP': 'KS',
    'TT': 'TT', 'SP': 'SP', 'MK': 'MK', 'CH': 'CH',
    # [Fix 32] previously-unmapped codes. 'AT' (ASX single-exchange code,
    # e.g. 'ELS AT Equity') fell through to 'OTHER' while the AU-listed ETFs
    # ('STW AU') mapped to APAC — so Australian stocks and their own local
    # ETFs landed in DIFFERENT timezone groups.
    'AT': 'AU', 'AH': 'AU',            # ASX
    'KQ': 'KS',                        # KOSDAQ
    'C1': 'CH', 'C2': 'CH',            # China Connect lines
    'NA': 'NA', 'SW': 'SW', 'SE': 'SW',  # Amsterdam, SIX
}

# [Fix 19] Normalized exchange code → market key used in INDEX_MAP/CONTROL_ETFS
EXCH_TO_MARKET = {
    'US': 'US', 'HK': 'HK', 'JP': 'JP', 'CH': 'CN', 'KS': 'KR', 'TT': 'TW',
    'IN': 'IN', 'AU': 'AU', 'GR': 'DE', 'LN': 'GB', 'FP': 'FR',
    'IM': 'EU', 'SM': 'EU', 'AV': 'EU', 'SJ': 'EU',
    'NA': 'EU', 'SW': 'EU',            # [Fix 32]
}

# [Fix 32] Approximate cash-session CLOSING HOUR in UTC per normalized
# exchange code (standard time; the ~1h DST drift is absorbed by the
# tolerance). This replaces the old AMER/EMEA/APAC buckets, which were too
# coarse in both directions: Taipei (05:30 UTC) and Mumbai (10:00 UTC) were
# called synchronous because both were 'APAC', while any unmapped exchange
# fell into an 'OTHER' bucket that the async-bias check silently ignored.
EXCH_CLOSE_UTC = {
    'US': 21.0,                        # NYSE / Nasdaq 16:00 ET
    'LN': 16.5,                        # LSE 16:30
    'GR': 16.5, 'FP': 16.5, 'IM': 16.5, 'SM': 16.5, 'AV': 16.5,
    'NA': 16.5, 'SW': 16.5,            # continental Europe ~17:30 CET
    'SJ': 15.0,                        # JSE 17:00 SAST
    'TT': 5.5,                         # TWSE 13:30
    'JP': 6.5,                         # TSE 15:30 JST since November 2024
    'AU': 6.0,                         # ASX 16:00 AEST
    'KS': 6.5,                         # KRX 15:30 KST
    'CH': 7.0,                         # SSE / SZSE 15:00 CST
    'HK': 8.0,                         # HKEX 16:00
    'SP': 9.0, 'MK': 9.0,              # SGX / Bursa 17:00 local
    'IN': 10.0,                        # NSE / BSE 15:30 IST
}


def _exch_of(full_ticker):
    """'700 HK Equity' → 'HK' (normalized via EXCH_MAP; 'JT' → 'JP' etc.)."""
    parts = full_ticker.split(' ')
    if len(parts) >= 2:
        return EXCH_MAP.get(parts[-2], parts[-2])
    return 'US'


# ─────────────────────────────────────────────────────────────────────────────
# [Fix 118] ETF membership by FULL TICKER, not by short name.
#
# The market-cap floor, the PIT-membership gate and the single-instrument
# benchmark all ask "is this an ETF?", and until now all three asked it of the
# short name alone. That was safe while the list held only broad wrappers; it
# stops being safe the moment locally-listed instruments are added, because
# short names collide ACROSS exchanges and the failure is silent and backwards.
# Concretely: 'GOLD US Equity' is Barrick Gold. Adding an ASX bullion ETF whose
# short name is also GOLD would have made BARRICK register as an ETF everywhere
# — exempt from the cap floor, exempt from point-in-time membership, eligible to
# win the "best single ETF" benchmark the whole report is framed against, and
# dropped from _stock_cols in the factor diagnostic.
#
# Full ticker first; the short name is honoured only when it is unambiguous
# across the listed instruments. Behaviour is identical for every ticker listed
# today (all are three-token, so _exch_of resolves normally).
# ─────────────────────────────────────────────────────────────────────────────
ETF_FULL_SET = ({t for lst in CONTROL_ETFS.values() for t in lst}
                | {t for _, lst in BROAD_MARKET_HEDGES.values() for t in lst}
                | {t for lst in MARKET_INSTRUMENTS.values() for t in lst})
_ETF_SHORT_EXCH = {}
for _t in ETF_FULL_SET:
    _ETF_SHORT_EXCH.setdefault(_t.split(' ')[0], set()).add(_exch_of(_t))
del _t


import hashlib as _hashlib

# [Fix 119] A cached download predates any edit to the tables above, and
# check_cache_fit only ever asked whether the LEGS were present — so adding a
# gold leg to MARKET_INSTRUMENTS would appear to do nothing at all, because the
# cache silently supplied yesterday's universe. Stamp the tables into the
# fingerprint so an out-of-date cache announces itself.
_INSTRUMENT_MAP_HASH = _hashlib.md5(
    repr(sorted((str(k), tuple(v)) for k, v in MARKET_INSTRUMENTS.items())
         + sorted((str(k), tuple(v)) for k, v in CONTROL_ETFS.items())
         + sorted((str(k), tuple(v)) for k, v in BROAD_MARKET_HEDGES.items())
         ).encode()).hexdigest()[:12]


def _is_etf(tk):
    """True when `tk` is one of the control / market instruments. Full-ticker
    match first, short name only where that short name maps to exactly one
    exchange across the lists above."""
    if tk in ETF_FULL_SET:
        return True
    exs = _ETF_SHORT_EXCH.get(str(tk).split(' ')[0])
    return bool(exs) and _exch_of(tk) in exs


def _exposure_tags(*taxonomy_strings):
    """[Fix 119] Exposure tags implied by a target's BICS/GICS descriptors.
    Substring match, case-insensitive, union across every string supplied."""
    tags = set()
    for s in taxonomy_strings:
        if not s:
            continue
        low = str(s).lower()
        for key, tg in HEDGE_EXPOSURES.items():
            if key in low:
                tags.update(tg)
    return tags


def _resolve_exposures(tags, market, country):
    """[Fix 119] Map exposure tags to locally-listed instruments.

    Returns (instruments, resolved{tag: [tickers]}, unresolved{tag: hint}).
    `hint` names a US-listed instrument when one exists for the tag, so the
    report can say the leg EXISTS but is not synchronous with this market
    rather than leaving the omission unexplained."""
    instruments, resolved, unresolved = [], {}, {}
    for tag in sorted(tags):
        hit = (MARKET_INSTRUMENTS.get((market, tag))
               or MARKET_INSTRUMENTS.get((country, tag)))
        if hit:
            resolved[tag] = list(hit)
            instruments.extend(hit)
        else:
            alt = MARKET_INSTRUMENTS.get(('US', tag))
            unresolved[tag] = (alt[0] if alt else None)
    return instruments, resolved, unresolved


def _close_utc_of(full_ticker):
    """[Fix 32] Approximate closing hour (UTC) of the ticker's exchange,
    or None when the exchange is unknown."""
    return EXCH_CLOSE_UTC.get(_exch_of(full_ticker))


def _close_gap_hours(a, b):
    """[Fix 32] Circular distance in hours between two closing times
    (a 23h gap is really a 1h gap on the clock)."""
    d = abs(a - b) % 24.0
    return min(d, 24.0 - d)


def _fmt_mktcap(mm):
    """[Fix 35] Format a USD-millions floor as '$750mm' / '$5.0bn'. The old
    message divided by 1000 and always printed 'bn', so a 50mm floor showed
    up as '$0bn'."""
    return f"${mm / 1000:.1f}bn" if mm >= 1000 else f"${mm:.0f}mm"


def _apply_exclusions(tickers, exclude):
    """[Fix 36] Manual filter-out of securities the user does not want as
    hedge candidates. Entries match the full ticker ('3156 JP Equity',
    case-insensitive, ' Equity' optional) or the bare short name ('3156').
    Returns (kept, removed)."""
    if not exclude:
        return list(tickers), []
    ex = {str(e).upper().replace(' EQUITY', '').strip() for e in exclude}
    kept, removed = [], []
    for tk in tickers:
        cu = tk.upper().replace(' EQUITY', '').strip()
        if cu in ex or cu.split(' ')[0] in ex:
            removed.append(tk)
        else:
            kept.append(tk)
    return kept, removed


def _resolve_force_include(force_include, columns, target_ticker):
    """[Fix 40] Resolve the user's must-have securities against the
    downloaded price columns. Entries match the full ticker
    ('0050 TT Equity', case-insensitive, ' Equity' optional) or the bare
    short name ('0050'). The target itself is ignored.
    Returns (resolved_full_tickers, unresolved_entries)."""
    if not force_include:
        return [], []
    resolved, unresolved = [], []
    for f in force_include:
        fu = str(f).upper().replace(' EQUITY', '').strip()
        hit = None
        for c in columns:
            cu = c.upper().replace(' EQUITY', '').strip()
            if cu == fu or cu.split(' ')[0] == fu:
                hit = c
                break
        if hit is None:
            unresolved.append(f)
        elif hit != target_ticker:
            resolved.append(hit)
    out, seen = [], set()
    for r in resolved:                 # dedupe, keep user order
        if r not in seen:
            out.append(r)
            seen.add(r)
    return out, unresolved


# [Fix 51] Jupyter detection — used by _print_table to pick a renderer.
try:
    from IPython.display import display as _ipy_display, HTML as _HTML
    from IPython import get_ipython as _get_ipython
    _IN_JUPYTER = _get_ipython() is not None
except Exception:                      # [Fix 87] _HTML kept defined either way
    _IN_JUPYTER = False
    _HTML = None


# ─────────────────────────────────────────────────────────────────────────────
# [Fix 115] REPORT TYPOGRAPHY — ONE renderer, one type scale, one grammar.
# ─────────────────────────────────────────────────────────────────────────────
# [Fix 104] set out to unify the report and only got half way: it introduced
# _kv_block (hand-built HTML) but left _print_table on the pandas Styler. Two
# renderers meant two looks on one page — Styler sized tables to their content
# while kv tables ran to 1100px, Styler set EVERY cell in monospace including
# the prose ones, and the two disagreed about zebra striping. Against the raw
# stdout <pre> that the engine's progress lines still landed in, the page
# carried three fonts and three widths. That is the reported "the font and
# tables are ugly, the structure is messy".
#
# What this pass changes:
#   · ONE table renderer. _print_table and _kv_block both build their markup
#     through _html_table, so every table on the page shares a header band,
#     rules, padding, row rhythm and measure. The pandas Styler path is gone
#     (and with it the jinja2 dependency that [Fix 75] had to guard).
#   · COLUMNS ARE TYPED, not uniformly monospaced. A column of numbers gets
#     tabular figures, right alignment and no wrapping; readings and prose get
#     the UI font. Monospace on a sentence was the ugliest thing on the page.
#   · ONE FACT PER LINE. Readings are written as 'a · b · c'; they are now
#     broken at the '·' so each fact sits on its own line instead of reflowing
#     into a grey block.
#   · PROSE HAS A HIERARCHY. The first sentence of a WHAT IT MEANS cell is the
#     claim and is set in ink; the rest is set muted and a step smaller, so the
#     page can be read at two depths instead of one.
#   · NO INTERNAL TAGS. '[Fix 108]' and friends are changelog markers for
#     whoever maintains this file. They meant nothing to a reader and made the
#     output look like debug spew; they are scrubbed at render time, so no call
#     site can leak one again.
#   · A PLAIN-TEXT TRANSCRIPT. In a notebook the report is displayed as HTML
#     and never touches stdout, so the Word export used to receive only the few
#     progress lines that were still bare print()s. Every renderer now also
#     records a text copy, and Export gets the whole report.
_RF_UI = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,"
          "'Helvetica Neue',Arial,sans-serif")
_RF_NUM = _RF_UI
_RF_INK = '#1c2733'          # body text / the claim
_RF_MUTE = '#5b6b7c'         # supporting prose
_RF_FAINT = '#8a97a6'        # captions, notes, sub-labels
_RF_HEAD = '#1f3f66'         # header band
_RF_RULE = '#e4e9ef'         # hairlines
_RF_ZEBRA = '#fafbfc'
_RF_MAXW = '1120px'          # one measure for every block on the page
_TXT_W = 96                  # terminal fallback: total table width budget

# Changelog markers ('[Fix 104]', '[Fix 89/95]') are for maintainers of this
# file, never for the reader of a hedge report. Scrubbed at render time.
_FIXTAG = re.compile(r'\[Fix\s*\d+(?:\s*[/,]\s*\d+)*\]\s*')


def _clean(s):
    """Text as it should reach the reader: no internal tags, no double spaces."""
    return re.sub(r'[ \t]{2,}', ' ', _FIXTAG.sub('', str(s))).strip()


# ── plain-text transcript ────────────────────────────────────────────────────
# Populated by every renderer below whichever path it takes, so there is always
# a faithful text copy of what was shown — for the Word export, for a log file,
# and for anyone reading a saved run.
_REPORT_TX = []


def _tx(*lines):
    _REPORT_TX.extend(lines)


def transcript_reset():
    del _REPORT_TX[:]


def transcript_text():
    """The report as plain text, exactly as it was rendered."""
    return '\n'.join(_REPORT_TX)


# ── column typing ────────────────────────────────────────────────────────────
# Typing the COLUMN rather than the cell is deliberate: a column reads as a
# column only when every cell in it is set the same way, and one stray 'n/a'
# should not knock a numeric column back into prose.
_NUMISH = re.compile(r'^[+\-±$<>~≈#]*\s*[\d.,]+')


def _col_kind(cells):
    """'num' | 'prose' | 'text' — decides font, alignment and wrapping."""
    vals = [c.strip() for c in cells if c.strip() and c.strip().lower() != 'n/a']
    if not vals:
        return 'text'
    if sum(bool(_NUMISH.match(v)) for v in vals) >= 0.7 * len(vals):
        return 'num'
    if max(len(v) for v in vals) > 46:
        return 'prose'
    return 'text'


def _facts(s):
    """Split a reading written as 'a · b · c' into its facts.

    The convention throughout this file is to join related readings with ' · '.
    Rendered as one string they reflow into an unreadable run; one per line
    they read like a ticket."""
    parts = [p.strip() for p in re.split(r'\s+·\s+', str(s)) if p.strip()]
    return parts or ['']


def _lede(s):
    """(claim, rest) — the first sentence of an explanation, and the rest.

    Every WHAT IT MEANS cell is written claim-first, so setting the first
    sentence in ink and the remainder muted gives the page a skim layer
    without deleting the detail underneath it."""
    s = _clean(s)
    if not s:
        return '', ''
    m = re.search(r'(?<=[.!?])\s+(?=[A-Z(“"])', s)
    return (s[:m.start()], s[m.end():]) if m else (s, '')


# ── the single HTML table renderer ───────────────────────────────────────────
def _html_table(headers, rows, kinds, title='', note=''):
    n = len(headers)
    # a table carrying an explanation column stretches to the page measure; a
    # data table (a ticket, a weights list, a two-column readout) sizes to its
    # content instead of sitting in a field of white space
    wide = 'prose' in kinds
    th = (f'background:{_RF_HEAD};color:#fff;text-align:left;'
          f'padding:9px 12px;font-size:11.5px;font-weight:600;'
          f'letter-spacing:.06em;text-transform:uppercase;'
          f'font-family:{_RF_UI};white-space:nowrap')
    out = [f'<table style="border-collapse:collapse;border-spacing:0;'
           f'margin:4px 0 14px 0;font-family:{_RF_UI};'
           f'width:100%;max-width:{_RF_MAXW}">']
    widths = None
    if list(headers) == ['ACTION', 'PER $100 TARGET', 'INSTRUMENT']:
        widths = [12, 20, 68]
    elif list(headers) == ['ACTION', 'PER $100 TARGET', 'INSTRUMENT', 'UNSEEN R²', 'VOL CUT']:
        widths = [12, 18, 42, 14, 14]
    if widths:
        out.append('<colgroup>' + ''.join(f'<col style="width:{w}%">' for w in widths) + '</colgroup>')
    if title:
        out.append(f'<caption style="caption-side:top;text-align:left;'
                   f'font-family:{_RF_UI};font-size:11px;font-weight:700;'
                   f'letter-spacing:.06em;text-transform:uppercase;'
                   f'color:{_RF_HEAD};padding:2px 0 6px 1px;'
                   f'white-space:nowrap">'
                   f'{_html.escape(_clean(title))}</caption>')
    out.append('<tr>' + ''.join(
        f'<th style="{th}{";text-align:right" if kinds[i] == "num" else ""}">'
        f'{_html.escape(_clean(h))}</th>' for i, h in enumerate(headers))
        + '</tr>')
    for ri, row in enumerate(rows):
        sub = str(row[0]).startswith('  ')     # '  label' → a sub-row
        bg = f'background:{_RF_ZEBRA};' if (ri % 2) else ''
        out.append('<tr>')
        for ci in range(n):
            cell, kind = str(row[ci]), kinds[ci]
            td = (f'padding:6px 12px;vertical-align:top;'
                  f'border-bottom:1px solid {_RF_RULE};{bg}')
            if kind == 'num':
                out.append(f'<td style="{td}text-align:right;'
                           f'font-family:{_RF_NUM};font-size:13.5px;'
                           f'font-variant-numeric:tabular-nums;'
                           f'white-space:nowrap;color:{_RF_INK}">'
                           f'{_html.escape(_clean(cell))}</td>')
            elif kind == 'label':
                # [Fix 116] a label may be written as two lines: what the row
                # tells you, then the technical name for it. The reader who
                # does not know the method reads the first line; the reader
                # who does gets the term they were looking for.
                _l1, _, _l2 = str(cell).partition('\n')
                body = _html.escape(_clean(_l1))
                if _l2.strip():
                    body += (f'<div style="font-weight:400;font-size:10.5px;'
                             f'color:{_RF_FAINT};margin-top:2px;'
                             f'letter-spacing:.01em">'
                             f'{_html.escape(_clean(_l2))}</div>')
                out.append(
                    f'<td style="{td}white-space:nowrap;font-size:'
                    f'{12 if sub else 13.5}px;font-weight:{400 if sub else 600};'
                    f'color:{_RF_FAINT if sub else _RF_INK};'
                    f'padding-left:{26 if sub else 12}px">{body}</td>')
            elif kind == 'prose':
                claim, rest = _lede(cell)
                body = (f'<span style="color:{_RF_INK}">'
                        f'{_html.escape(claim)}</span>')
                if rest:
                    body += (f' <span style="color:{_RF_MUTE};'
                             f'font-size:11.5px">{_html.escape(rest)}</span>')
                out.append(f'<td style="{td}font-size:12px;line-height:1.5;'
                           f'width:46%">{body}</td>')
            else:                              # 'read' / 'text'
                # only a READING is broken into one fact per line; doing it to
                # every text column turned 'lb 252 · pc auto · k 3' in the
                # ALTERNATIVES summary into three lines and made a scan table
                # three times as tall
                parts = (_facts(_clean(cell)) if kind == 'read'
                         else [_clean(cell)])
                body = '<br>'.join(_html.escape(f) for f in parts)
                # a short label ('◄ chosen', 'normal') is a tag, not prose —
                # letting it wrap mid-phrase reads as a layout accident
                _nw = ('white-space:nowrap;'
                       if max((len(x) for x in parts), default=0) <= 22
                       else '')
                out.append(f'<td style="{td}{_nw}font-size:13.5px;'
                           f'line-height:1.5;font-variant-numeric:tabular-nums;'
                           f'color:{_RF_INK}">{body}</td>')
        out.append('</tr>')
    out.append('</table>')
    if note:
        out.append(f'<div style="font-family:{_RF_UI};font-size:11px;'
                   f'color:{_RF_FAINT};margin:-10px 0 14px 2px;'
                   f'max-width:{_RF_MAXW}">{_html.escape(_clean(note))}</div>')
    return ''.join(out)


def _text_table(headers, rows, kinds, title='', note='', indent='  '):
    """Terminal fallback — the boxed layout, with every cell wrapped so a table
    cannot run off the side of the terminal."""
    n = len(headers)
    cells = [[_facts(_clean(r[i])) if kinds[i] == 'read'
              else ([_clean(x) for x in str(r[i]).split('\n')]  # [Fix 116]
                    if kinds[i] == 'label' else [_clean(r[i])])
              for i in range(n)] for r in rows]
    w = [max([1, len(_clean(headers[i]))]
             + [max((len(x) for x in row[i]), default=0) for row in cells])
         for i in range(n)]
    budget = _TXT_W - len(indent) - 3 * n - 1
    # Prose gives up width first, but only down to a readable measure; after
    # that every wrappable column shrinks widest-first. Shrinking prose alone
    # produced tables with a 72-char reading column beside a 14-char ribbon of
    # explanation — technically inside the budget, unreadable in practice.
    while sum(w) > budget:
        cand = [i for i in range(n) if kinds[i] != 'num'
                and w[i] > max(len(_clean(headers[i])), 12)]
        if not cand:
            break
        wide_prose = [i for i in cand if kinds[i] == 'prose' and w[i] > 30]
        w[max(wide_prose or cand, key=lambda j: w[j])] -= 1

    def wrap(cell, width):
        out = []
        for piece in cell:
            out += _textwrap.wrap(piece, width) or ['']
        return out

    def rule(l, m, r):
        return indent + l + m.join('─' * (x + 2) for x in w) + r

    def band(vals):
        cols = [wrap(v, w[i]) for i, v in enumerate(vals)]
        out = []
        for k in range(max(len(c) for c in cols)):
            parts = []
            for i, c in enumerate(cols):
                s = c[k] if k < len(c) else ''
                pad = ' ' * (w[i] - len(s))
                parts.append(f' {pad}{s} ' if kinds[i] == 'num'
                             else f' {s}{pad} ')
            out.append(indent + '│' + '│'.join(parts) + '│')
        return out

    lines = ['', f"{indent}{_clean(title).upper()}"] if title else []
    lines.append(rule('┌', '┬', '┐'))
    lines += band([[_clean(h)] for h in headers])
    lines.append(rule('├', '┼', '┤'))
    for row in cells:
        lines += band(row)
    lines.append(rule('└', '┴', '┘'))
    if note:
        lines += [indent + x for x in
                  _textwrap.wrap(_clean(note), _TXT_W - len(indent))]
    return lines


def _emit_table(headers, rows, kinds, title='', note='', indent='  '):
    """The one entry point for both renderers, so a table can look only one
    way. Both paths are fed the same headers/rows/kinds."""
    _kv_flush()                    # ordering — see the note on _KVCTX below
    lines = _text_table(headers, rows, kinds, title=title, note=note,
                        indent=indent)
    _tx(*lines)
    try:
        if _IN_JUPYTER:
            _ipy_display(_HTML(_html_table(headers, rows, kinds, title=title,
                                           note=note)))
            return
    except Exception:
        pass                       # never lose a block to a display problem
    for ln in lines:
        print(ln)


# [Fix 104] ORDERING. kv() buffers its rows so a run of them renders as ONE
# table. Anything else that writes to the report must therefore flush that
# buffer first, or the table jumps ahead of the prose above it. Rather than
# police ~44 call sites by hand, the buffer lives at module level and the
# writers (_section, _emit_table, _P) flush it on entry — so the ordering is
# correct by construction and stays correct when lines are added.
_KV_HEADERS = ('', 'READING', 'WHAT IT MEANS')
_KVCTX = {'title': None, 'note': '', 'rows': [], 'headers': _KV_HEADERS}


def _kv_flush():
    if _KVCTX['rows']:
        _rows, _title = list(_KVCTX['rows']), _KVCTX['title']
        _note, _hdr = _KVCTX['note'], _KVCTX['headers']
        # [Fix 115] clear the context BEFORE rendering — that makes the
        # _kv_flush() at the top of _emit_table a no-op instead of a recursion,
        # and it clears `headers`, which the old version left behind. Leaving
        # them behind is how [1] VALIDATION came to be headed 'WATCH / THIS RUN
        # / WHY AT THIS HORIZON' — inherited from the block above it — with an
        # empty third column under the third heading.
        _kv_reset()
        _kv_block(_title, _rows, note=_note, headers=_hdr)


def _kv_open(title=None, headers=_KV_HEADERS, note=''):
    _kv_flush()
    _KVCTX.update(title=title, headers=headers, note=note, rows=[])


def _kv_reset():
    """[Fix 114] Drop any half-built table WITHOUT rendering it.

    _KVCTX is module-level, so a run that raises part-way through the report
    leaves its buffered rows sitting there — and the UI catches exceptions and
    lets you re-run, so the next run's first table would silently open with
    rows from the failed one. Discarding is right, not flushing: those rows
    describe a run that did not finish."""
    _KVCTX.update(title=None, note='', rows=[], headers=_KV_HEADERS)


def _P(*a, **k):
    """print() for the report — flushes any pending kv table first.
    In Jupyter a bare line renders as styled prose rather than raw <pre>."""
    _kv_flush()
    if not a:
        _tx('')
        if not _IN_JUPYTER:
            print()
        return
    _raw = ' '.join(str(x) for x in a).strip('\n')
    _lead = len(_raw) - len(_raw.lstrip())
    _txt = _clean(_raw)
    if not _txt:
        return
    # '►' takeaways and '⚠' warnings are the lines a reader is meant to stop
    # on; everything else at this level is connective tissue.
    _key = _txt[:1] in '►⚠✓✗△'
    # the text copy is wrapped: it is what the Word appendix and any saved log
    # get, and a 160-column paragraph is unreadable in both
    _pad = ' ' * (_lead + 2)
    _wrapped = _textwrap.wrap(_txt, _TXT_W - len(_pad) - 2,
                              subsequent_indent='  ') or ['']
    _tx(*[_pad + ln for ln in _wrapped])
    try:
        if _IN_JUPYTER and k.pop('html', True):
            _ipy_display(_HTML(
                f'<div style="font-family:{_RF_UI};font-size:13.5px;'
                f'color:{_RF_INK if _key else _RF_MUTE};'
                f'font-weight:{600 if _key else 400};line-height:1.5;'
                f'margin:3px 0 3px {8 + _lead * 3}px;max-width:{_RF_MAXW}">'
                f'{_html.escape(_txt)}</div>'))
            return
    except Exception:
        pass
    for _ln in _wrapped:
        print(_pad + _ln, **k)


def _section(title, subtitle=''):
    """A report section header — styled in Jupyter, ruled in text."""
    _kv_flush()
    title, subtitle = _clean(title), _clean(subtitle)
    _tx('', '═' * _TXT_W, f" {title}")
    if subtitle:
        _tx(f" {subtitle}")
    _tx('═' * _TXT_W)
    try:
        if _IN_JUPYTER:
            _ipy_display(_HTML(
                f'<div style="margin:26px 0 8px 0;padding:0 0 5px 0;'
                f'border-bottom:2px solid {_RF_HEAD};font-family:{_RF_UI};'
                f'max-width:{_RF_MAXW}">'
                f'<span style="font-size:16.5px;font-weight:700;'
                f'letter-spacing:.03em;color:{_RF_HEAD}">'
                f'{_html.escape(title)}</span>'
                + (f'<span style="font-size:12px;color:{_RF_FAINT};'
                   f'margin-left:10px">{_html.escape(subtitle)}</span>'
                   if subtitle else '')
                + '</div>'))
            return
    except Exception:
        pass
    print(f"\n{'═' * _TXT_W}\n {title}" + (f"\n {subtitle}" if subtitle else '')
          + f"\n{'═' * _TXT_W}")


def _kv_block(title, rows, note='', headers=_KV_HEADERS):
    """The workhorse: rows of (label, reading, implication).

    Every ticket line used to be `kv('SIZING', <one long sentence>)` — a
    26-char label and then an unbroken run of numbers and prose that the eye
    cannot parse and that wraps unpredictably. Splitting the implication into
    its own column is the single biggest readability win, and it forces each
    number to come with a statement of what to DO about it.

    rows may be 2-tuples (label, reading) or 3-tuples with the implication.
    A row whose label starts with '  ' renders as a sub-row (indented, muted).
    """
    rows = [list(r) + [''] * (3 - len(r)) for r in rows if r is not None]
    if not rows:
        return
    headers, kinds = list(headers), ['label', 'read', 'prose']
    if not any(str(r[2]).strip() for r in rows):     # no implications → 2 cols
        headers, rows, kinds = headers[:2], [r[:2] for r in rows], kinds[:2]
    _emit_table(headers, rows, kinds, title=title, note=note)


def _print_table(headers, rows, indent='  ', wrap_last=None, title='',
                 note=''):
    """Render rows as a table. `wrap_last` is kept for call-site compatibility
    and ignored — wrapping is decided per column now, by _col_kind."""
    headers, rows = list(headers), [[str(x) for x in r] for r in rows]
    kinds = [_col_kind([r[i] for r in rows]) for i in range(len(headers))]
    for i, header in enumerate(headers):
        if str(header).lower() in ('instrument', 'full ticker', 'candidate', 'method'):
            kinds[i] = 'text'
    _emit_table(headers, rows, kinds, title=title, note=note, indent=indent)


def _market_of(target_ticker, country_iso):
    """[Fix 19] Market key for index/ETF lookups.

    Rule: use the LISTING market derived from the exchange code. The only
    exception is a US listing whose country of risk is not the US (an ADR,
    e.g. BABA US with COUNTRY_ISO=CN) — there the country mapping is the
    right 'local' universe (HXC = US-listed China names).

    Examples: 700 HK (Tencent, COUNTRY_ISO=CN) → 'HK' → HSTECH/HSI.
              BABA US (COUNTRY_ISO=CN)        → 'CN' → HXC.
              005930 KS (Samsung)             → 'KR' → KOSPI2.
    """
    exch = _exch_of(target_ticker)
    market = EXCH_TO_MARKET.get(exch)
    if exch == 'US' and country_iso != 'US':
        return country_iso
    return market or country_iso


def _fmt_bbg_ticker(raw):
    """[Fix 1] Normalize 'XXX YY' or 'XXX YY Equity' → 'XXX <exch> Equity'."""
    parts = raw.replace(' Equity', '').split(' ')
    if len(parts) >= 2 and parts[0]:
        return f"{parts[0]} {EXCH_MAP.get(parts[-1], parts[-1])} Equity"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Bloomberg helper functions
# ─────────────────────────────────────────────────────────────────────────────
def bbg_connect(host='localhost', port=8194):
    if blpapi is None:
        raise RuntimeError('Bloomberg blpapi is not installed in this Python environment. '
                           'Install the Bloomberg Python API to download data, or load a saved cache.')
    opts = blpapi.SessionOptions()
    opts.setServerHost(host)
    opts.setServerPort(port)
    s = blpapi.Session(opts)
    # [Fix 13] explicit raise instead of assert (assert is stripped under -O)
    if not s.start():
        raise ConnectionError(
            f"Bloomberg session failed to start ({host}:{port}) — "
            "check that the terminal is logged in")
    if not s.openService("//blp/refdata"):
        raise ConnectionError("Failed to open //blp/refdata service")
    print(f"✓ Bloomberg connected ({host}:{port})")
    return s


# [Fix 3] Lazy session: reconnectable, not frozen into a default argument
SESSION = None

def get_session():
    global SESSION
    if SESSION is None:
        SESSION = bbg_connect()
    return SESSION


def _drain_events(session, on_message, timeout_ms=60000):
    """[Fix 2] Shared event loop: raises on TIMEOUT instead of spinning forever."""
    while True:
        ev = session.nextEvent(timeout_ms)
        if ev.eventType() == blpapi.Event.TIMEOUT:
            raise TimeoutError(
                f"Bloomberg request timed out after {timeout_ms} ms — "
                "check terminal connectivity or reduce the batch size")
        for msg in ev:
            on_message(msg)
        if ev.eventType() == blpapi.Event.RESPONSE:
            break


def bbg_hist_field(session, tickers, field, start, end):
    """[Fix 44] Generic historical BDH for a single numeric field (e.g.
    'CUR_MKT_CAP'). Same batching / draining as bbg_hist; returns a DataFrame
    keyed by full ticker. Used to build point-in-time market-cap paths so the
    size filter can be applied as-of each backtest window instead of with
    today's cap (look-ahead for names that have changed size)."""
    svc = session.getService("//blp/refdata")
    data, bad = {}, []
    batch = 100
    for i in range(0, len(tickers), batch):
        req = svc.createRequest("HistoricalDataRequest")
        for t in tickers[i:i + batch]:
            req.getElement("securities").appendValue(t)
        req.getElement("fields").appendValue(field)
        req.set("periodicitySelection", "DAILY")
        req.set("startDate", start)
        req.set("endDate", end)
        req.set("nonTradingDayFillOption", "NON_TRADING_WEEKDAYS")
        req.set("nonTradingDayFillMethod", "PREVIOUS_VALUE")
        session.sendRequest(req)

        def on_msg(msg):
            if not msg.hasElement("securityData"):
                return
            sd = msg.getElement("securityData")
            sec = sd.getElementAsString("security")
            if sd.hasElement("securityError"):
                bad.append(sec)
                return
            fda = sd.getElement("fieldData")
            recs = []
            for k in range(fda.numValues()):
                fd = fda.getValueAsElement(k)
                try:
                    recs.append({'date': fd.getElementAsDatetime("date"),
                                 'val': fd.getElementAsFloat(field)})
                except Exception:
                    continue
            if recs:
                df = pd.DataFrame(recs)
                df['date'] = pd.to_datetime(df['date'])
                data[sec] = df.set_index('date')['val']

        _drain_events(session, on_msg)
    return pd.DataFrame(data)


def bbg_hist(session, tickers, start, end):
    """Historical PX_LAST. Returns a DataFrame keyed by full ticker.
    Invalid tickers are reported, not silently dropped."""
    svc = session.getService("//blp/refdata")
    data, bad = {}, []
    batch = 100  # keep historical requests reasonably sized
    for i in range(0, len(tickers), batch):
        req = svc.createRequest("HistoricalDataRequest")
        for t in tickers[i:i + batch]:
            req.getElement("securities").appendValue(t)
        req.getElement("fields").appendValue("PX_LAST")
        req.set("periodicitySelection", "DAILY")
        req.set("startDate", start)
        req.set("endDate", end)
        req.set("nonTradingDayFillOption", "ACTIVE_DAYS_ONLY")
        # Do not ask Bloomberg to manufacture repeated prices on inactive days.
        # [Fix 58] Make the price adjustment EXPLICIT. Without these three
        # lines HistoricalDataRequest inherits whatever DPDF the local
        # terminal happens to be set to — on most desks that is split-
        # adjusted but NOT dividend-adjusted, so every ex-div date shows up
        # as a spurious negative return. ETFs and HK/China high-payout names
        # distribute 2-6% a year, which quietly biases betas and hedge
        # ratios. Setting them here also means two colleagues running this
        # notebook on different terminals finally get identical numbers.
        req.set("adjustmentSplit", True)       # splits / rights issues
        req.set("adjustmentNormal", True)      # regular cash dividends
        req.set("adjustmentAbnormal", True)    # special distributions
        session.sendRequest(req)

        def on_msg(msg):
            if not msg.hasElement("securityData"):
                return
            sd = msg.getElement("securityData")
            sec = sd.getElementAsString("security")
            if sd.hasElement("securityError"):          # [Fix 13/15]
                bad.append(sec)
                return
            fda = sd.getElement("fieldData")
            recs = []
            for k in range(fda.numValues()):
                fd = fda.getValueAsElement(k)
                try:
                    recs.append({'date': fd.getElementAsDatetime("date"),
                                 'px': fd.getElementAsFloat("PX_LAST")})
                except Exception:
                    continue
            if recs:
                df = pd.DataFrame(recs)
                df['date'] = pd.to_datetime(df['date'])
                data[sec] = df.set_index('date')['px']

        _drain_events(session, on_msg)
    if bad:
        print(f"  ⚠ {len(bad)} invalid tickers dropped (e.g. {bad[:5]})")
    return pd.DataFrame(data)


def bbg_bulk(session, ticker, field, overrides=None):
    """BDS bulk field — returns a list of dicts (one per row).
    [Fix 49] optional overrides, e.g. {'END_DATE_OVERRIDE': '20240630'} to
    read INDX_MWEIGHT_HIST as of a past date."""
    svc = session.getService("//blp/refdata")
    req = svc.createRequest("ReferenceDataRequest")
    req.getElement("securities").appendValue(ticker)
    req.getElement("fields").appendValue(field)
    if overrides:
        ovr = req.getElement("overrides")
        for k, v in overrides.items():
            o = ovr.appendElement()
            o.setElement("fieldId", k)
            o.setElement("value", str(v))
    session.sendRequest(req)
    rows = []

    def on_msg(msg):
        if not msg.hasElement("securityData"):
            return
        arr = msg.getElement("securityData")
        for i in range(arr.numValues()):
            sd = arr.getValueAsElement(i)
            if sd.hasElement("securityError"):
                continue
            fd = sd.getElement("fieldData")
            if fd.hasElement(field):
                bulk = fd.getElement(field)
                for j in range(bulk.numValues()):
                    row = bulk.getValueAsElement(j)
                    d = {}
                    for k in range(row.numElements()):
                        e = row.getElement(k)
                        d[str(e.name())] = str(e.getValue())
                    rows.append(d)

    _drain_events(session, on_msg)
    return rows


def bbg_ref_multi(session, tickers, fields, overrides=None):
    """BDP reference data for many tickers → {full_ticker: {field: value}}.
    [Fix 25] `overrides` is an optional {fieldId: value} dict."""
    svc = session.getService("//blp/refdata")
    result = {}
    batch = 300
    for i in range(0, len(tickers), batch):
        req = svc.createRequest("ReferenceDataRequest")
        for t in tickers[i:i + batch]:
            req.getElement("securities").appendValue(t)
        for f in fields:
            req.getElement("fields").appendValue(f)
        if overrides:
            ovr = req.getElement("overrides")
            for k, v in overrides.items():
                o = ovr.appendElement()
                o.setElement("fieldId", k)
                o.setElement("value", str(v))
        session.sendRequest(req)

        def on_msg(msg):
            if not msg.hasElement("securityData"):
                return
            arr = msg.getElement("securityData")
            for j in range(arr.numValues()):
                sd = arr.getValueAsElement(j)
                sec = sd.getElementAsString("security")
                if sd.hasElement("securityError"):
                    continue
                fd = sd.getElement("fieldData")
                result[sec] = {}
                for f in fields:
                    if fd.hasElement(f):
                        try:
                            result[sec][f] = fd.getElementAsString(f)
                        except Exception:
                            try:
                                result[sec][f] = fd.getElementAsFloat(f)
                            except Exception:
                                pass

        _drain_events(session, on_msg)
    return result


def bbg_ref_single(session, ticker, fields):
    return bbg_ref_multi(session, [ticker], fields).get(ticker, {})


# ─────────────────────────────────────────────────────────────────────────────
# Universe discovery
# ─────────────────────────────────────────────────────────────────────────────
def _index_members(session, spec):
    """[Fix 37] `spec` is one index ticker or a tuple of fallbacks. Returns
    (ticker_used, members) from the first index that yields any members —
    an index that loads but returns 0 members (licence-gated INDX_MEMBERS)
    now falls through instead of silently emptying a universe leg."""
    tickers = [spec] if isinstance(spec, str) else list(spec or [])
    for n, idx_ticker in enumerate(tickers):
        members = []
        try:
            for r in bbg_bulk(session, idx_ticker, 'INDX_MEMBERS'):
                tk = _fmt_bbg_ticker(r.get('Member Ticker and Exchange Code', ''))
                if tk:
                    members.append(tk)
        except Exception as e:
            print(f"    ⚠ failed to read {idx_ticker} members: {e}")
            continue
        if members:
            return idx_ticker, members
        more = " — trying fallback" if n + 1 < len(tickers) else ""
        print(f"    ⚠ {idx_ticker} returned 0 members (licence-gated?){more}")
    return None, []


def _pit_index_membership(session, index_tickers, start, end, freq_days=91):
    """[Fix 49] Point-in-time index-membership snapshots via INDX_MWEIGHT_HIST
    with an END_DATE_OVERRIDE, roughly quarterly across [start, end]. Returns
    {Timestamp: frozenset(full tickers)} (union across the given indices).
    GRACEFUL FALLBACK: some indices licence-gate this field (e.g. certain
    TW/Asia benchmarks) — any snapshot that fails is skipped, and if NOTHING
    comes back an empty dict is returned with a warning, so the pipeline
    silently reverts to today's-members behavior (survivorship caveat then
    still applies)."""
    idxs = [i for i in dict.fromkeys(index_tickers or []) if i]
    if not idxs:
        return {}
    d0 = pd.Timestamp(datetime.strptime(start, '%Y%m%d'))
    d1 = pd.Timestamp(datetime.strptime(end, '%Y%m%d'))
    dates = list(pd.date_range(d0, d1, freq=f'{freq_days}D'))
    if not dates or dates[-1] != d1:
        dates.append(d1)
    snaps = {}
    for dt in dates:
        members = set()
        for idx in idxs:
            try:
                rows = bbg_bulk(session, idx, 'INDX_MWEIGHT_HIST',
                                overrides={'END_DATE_OVERRIDE':
                                           dt.strftime('%Y%m%d')})
            except Exception:
                continue                      # this snapshot/index: give up
            for r in rows:
                raw = r.get('Index Member') or next(iter(r.values()), '')
                tk = _fmt_bbg_ticker(raw)
                if tk:
                    members.add(tk)
        if members:
            snaps[dt] = frozenset(members)
    if not snaps:
        print(f"    ⚠ INDX_MWEIGHT_HIST unavailable for {idxs} "
              f"(licence-gated?) — point-in-time membership skipped; "
              f"falling back to today's members (survivorship caveat applies)")
    return snaps


def auto_discover_universe(session, target_ticker, max_first_degree_peers=10,
                           min_mktcap_usd_mm=5000, meta=None):
    print(f"  Auto-discovering universe for {target_ticker}...")

    ref_fields = [
        'COUNTRY_ISO',
        'BICS_LEVEL_2_INDUSTRY_GROUP_NAME',
        'BICS_LEVEL_3_INDUSTRY_NAME',
        'BICS_LEVEL_4_SUB_INDUSTRY_NAME',
        'GICS_SECTOR_NAME',
        'GICS_INDUSTRY_NAME',
        'GICS_SUB_INDUSTRY_NAME',   # [Fix 1] correct field name
        'CUR_MKT_CAP',
        'AVERAGE_VOLUME_30D',
    ]
    tgt_ref = bbg_ref_single(session, target_ticker, ref_fields)
    country = (str(tgt_ref.get('COUNTRY_ISO') or 'US'))[:2].upper()

    # [Fix 19] market = listing venue (Tencent 700 HK → 'HK', not 'CN');
    # country-of-risk only kicks in for US-listed ADRs (BABA US → 'CN')
    market = _market_of(target_ticker, country)

    tgt_bics_lvl4 = tgt_ref.get('BICS_LEVEL_4_SUB_INDUSTRY_NAME')
    tgt_bics_lvl3 = tgt_ref.get('BICS_LEVEL_3_INDUSTRY_NAME')
    tgt_bics_lvl2 = tgt_ref.get('BICS_LEVEL_2_INDUSTRY_GROUP_NAME')
    tgt_gics_sub = tgt_ref.get('GICS_SUB_INDUSTRY_NAME')
    tgt_gics_ind = tgt_ref.get('GICS_INDUSTRY_NAME')
    tgt_gics_sec = tgt_ref.get('GICS_SECTOR_NAME') or 'Broad'

    sector_key = 'Broad'
    for key_word in ['Technology', 'Communication', 'Financials',
                     'Health Care', 'Energy', 'Consumer Discretionary',
                     'Materials']:            # [Fix 119] miners were 'Broad'
        if (tgt_bics_lvl2 and key_word.lower() in str(tgt_bics_lvl2).lower()) or \
           (key_word.lower() in str(tgt_gics_sec).lower()):
            sector_key = key_word
            break

    # ── [Fix 119] WHAT THIS TARGET IS EXPOSED TO ────────────────────────────
    # The taxonomy above was fetched anyway and then used for one six-word
    # match. Read it properly: derive the exposures the target carries, and
    # resolve each to an instrument listed in ITS OWN market so the candidate
    # set contains the thing the target actually moves with.
    _tags = _exposure_tags(tgt_bics_lvl4, tgt_bics_lvl3, tgt_bics_lvl2,
                           tgt_gics_sub, tgt_gics_ind)
    exp_instruments, exp_resolved, exp_unresolved = _resolve_exposures(
        _tags, market, country)
    if _tags:
        print(f"    ├─ exposures required: {', '.join(sorted(_tags))}")
        if exp_resolved:
            print(f"    ├─ resolved: "
                  + ', '.join(t.split(' ')[0] + ' ' + _exch_of(t)
                              for t in exp_instruments))
        for _tag, _alt in sorted(exp_unresolved.items()):
            print(f"    ⚠ {_tag} — no {market}-listed instrument mapped; the "
                  f"hedge is built WITHOUT it"
                  + (f" (US-listed {_alt.split(' ')[0]} exists but is not "
                     f"synchronous with {market}; add it via force_include and "
                     f"the run drops to 2-day returns)" if _alt else ''))
    else:
        print(f"    ├─ no specific commodity/rates exposure implied by the "
              f"taxonomy — broad-market candidates only")

    # 1. Local index mapping — keyed by listing market [Fix 19/37]
    idx_spec = (INDEX_MAP.get((market, sector_key))
                or INDEX_MAP.get((market, 'Broad'))
                or INDEX_MAP.get((country, 'Broad')))
    local_index_ticker, local_members = _index_members(session, idx_spec)
    print(f"    ├─ market={market}, sector={sector_key} → local index "
          f"{local_index_ticker or 'NONE'}: {len(local_members)} names")

    # 2. Global cross-country super pool [Fix 37: fallback-aware]
    broad_specs = sorted({(v if isinstance(v, str) else tuple(v))
                          for k, v in INDEX_MAP.items() if k[1] == 'Broad'},
                         key=str)
    global_super_pool = []
    for spec in broad_specs:
        _, members = _index_members(session, spec)
        global_super_pool.extend(members)
    global_super_pool = sorted(set(global_super_pool))

    pool_ref_data = bbg_ref_multi(session, global_super_pool, ref_fields)

    # 3. Dual-taxonomy matching (BICS OR GICS)
    industry_matches = []
    print(f"    ├─ running BICS + GICS dual-taxonomy cross-country search...")
    for tk, d in pool_ref_data.items():
        if tk == target_ticker:
            continue
        bics_match = (tgt_bics_lvl4 and d.get('BICS_LEVEL_4_SUB_INDUSTRY_NAME') == tgt_bics_lvl4) or \
                     (tgt_bics_lvl3 and d.get('BICS_LEVEL_3_INDUSTRY_NAME') == tgt_bics_lvl3)
        gics_match = (tgt_gics_sub and d.get('GICS_SUB_INDUSTRY_NAME') == tgt_gics_sub) or \
                     (tgt_gics_ind and d.get('GICS_INDUSTRY_NAME') == tgt_gics_ind)
        if bics_match or gics_match:
            industry_matches.append(tk)
    print(f"    ├─ industry matches captured: {len(industry_matches)} names")

    # 4. Bloomberg official peers + second-degree peers
    #    [Fix 1: proper formatting + capped API calls]
    peer_matches, first_degree = [], []
    try:
        first_degree = []
        for r in bbg_bulk(session, target_ticker, 'BLOOMBERG_PEERS'):
            tk = _fmt_bbg_ticker(r.get('Peer Ticker', ''))
            if tk:
                first_degree.append(tk)
        peer_matches.extend(first_degree)
        for peer in first_degree[:max_first_degree_peers]:
            try:
                for r in bbg_bulk(session, peer, 'BLOOMBERG_PEERS'):
                    tk = _fmt_bbg_ticker(r.get('Peer Ticker', ''))
                    if tk:
                        peer_matches.append(tk)
            except Exception:
                continue
        print(f"    ├─ Bloomberg peers (incl. 2nd degree): {len(set(peer_matches))} names")
    except Exception as e:
        print(f"    ⚠ failed to read peers: {e}")

    # 5. Control ETFs — from BOTH listing market and country of risk [Fix 19]
    broad_spec = _broad_market_spec(target_ticker)
    all_etfs = sorted(set(broad_spec['instruments'] + CONTROL_ETFS.get(market, []) +
                          CONTROL_ETFS.get(country, []) +
                          CONTROL_ETFS.get('FACTOR', []) +   # [Fix 43]
                          CONTROL_ETFS['GLOBAL']))

    if meta is not None:                          # [Fix 49] expose discovery
        meta['target'] = target_ticker
        meta['peer_tickers'] = sorted(set(first_degree + industry_matches) - {target_ticker})
        meta['broad_market'] = broad_spec
        meta['index_ticker'] = local_index_ticker  # facts for PIT membership
        meta['non_index_shorts'] = (
            {t.split(' ')[0] for t in peer_matches} |
            {t.split(' ')[0] for t in industry_matches} |
            {t.split(' ')[0] for t in all_etfs} |
            {t.split(' ')[0] for t in exp_instruments})      # [Fix 119]
        meta['exposure_tags'] = sorted(_tags)                # [Fix 119]
        meta['exposures_resolved'] = exp_resolved
        meta['exposures_unresolved'] = exp_unresolved

    # Merge + [Fix 7] dedupe by short name but KEEP full tickers
    # (local members take priority on collision)
    # [Fix 119] exposure instruments go FIRST. They were resolved for THIS
    # target from its own taxonomy, so on a short-name collision they must beat
    # a generic peer — the reverse of the old order, where all_etfs came last
    # and a colliding foreign listing silently displaced the local instrument.
    merged, seen_short = [], set()
    for tk in (exp_instruments + local_members + peer_matches
               + industry_matches + all_etfs):
        if tk == target_ticker:
            continue
        short = tk.split(' ')[0]
        if short == target_ticker.split(' ')[0]:
            continue
        if short not in seen_short:
            merged.append(tk)
            seen_short.add(short)

    # [Fix 25] Liquidity filter: drop non-ETF names below the USD market-cap
    # floor. Without this, microcaps could enter a mega-cap's basket on
    # spurious loading similarity. CRNCY_ADJ_MKT_CAP with a USD override is
    # reported in USD millions; parse failures are kept (fail-open) so a
    # field-permission issue cannot wipe out the universe.
    if min_mktcap_usd_mm and merged:
        try:
            liq = bbg_ref_multi(session, merged, ['CRNCY_ADJ_MKT_CAP'],
                                overrides={'EQY_FUND_CRNCY': 'USD'})
            kept, dropped, unknown = [], 0, 0
            for tk in merged:
                if _is_etf(tk):
                    kept.append(tk)
                    continue
                try:
                    mc = float(liq.get(tk, {}).get('CRNCY_ADJ_MKT_CAP'))
                except (TypeError, ValueError):
                    unknown += 1
                    kept.append(tk)      # unknown → keep (fail-open)
                    continue
                if mc >= min_mktcap_usd_mm:
                    kept.append(tk)
                else:
                    dropped += 1
            # [Fix 35] correct units in the message ('$50mm', not '$0bn') and
            # report how many names passed only because their cap was unknown
            if dropped or unknown:
                print(f"    ├─ liquidity filter: dropped {dropped} names below "
                      f"{_fmt_mktcap(min_mktcap_usd_mm)} market cap"
                      + (f" ({unknown} unknown caps kept)" if unknown else ""))
            merged = kept
        except Exception as e:
            print(f"    ⚠ liquidity filter skipped ({e})")

    print(f"    ✓ final merged universe: {len(merged)} candidates")
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# [Fix 88] DOWNLOAD CACHE — Bloomberg pulls are slow, rate-limited and lost on
# every kernel restart. download_hedge_data() now writes its result to disk and
# it can be reloaded with zero API calls, days later, from another session.
# Files are plain pickles of the returned dict (DataFrames + dicts) under
# HEDGE_CACHE_DIR. Note: a pickle is tied to your pandas version — if you
# upgrade pandas and a load fails, just re-download.
# ─────────────────────────────────────────────────────────────────────────────
import os as _os
import pickle as _pickle
import glob as _glob
import re as _re
import json as _json

HEDGE_CACHE_DIR = _os.environ.get('HEDGE_CACHE_DIR', _os.path.join(_os.getcwd(), 'hedge_data_cache'))

# [Fix 103] Where exported hedge reports go. Set once here, or override per
# call / in the form's Export folder box. If the drive is not mapped on the
# machine running the notebook, the exporter falls back to a local folder and
# says so rather than failing.
HEDGE_EXPORT_DIR = _os.environ.get('HEDGE_EXPORT_DIR', _os.path.join(_os.getcwd(), 'hedge_exports'))


def _slug(text):
    return _re.sub(r'[^A-Za-z0-9]+', '-', str(text)).strip('-')[:60] or 'data'


def save_hedge_data(data, label=None, cache_dir=None):
    """[Fix 88] Persist a download_hedge_data() result. Returns the path.

    [Fix 90] also writes a small JSON sidecar holding the fingerprint (legs,
    download filters, coverage dates, ticker list) so the catalogue and the
    GUI can judge whether a cached set still fits the book you are hedging
    WITHOUT unpickling every file."""
    d = cache_dir or HEDGE_CACHE_DIR
    _os.makedirs(d, exist_ok=True)
    lab = _slug(label or data.get('target_label') or 'data')
    stamp = datetime.now().strftime('%Y%m%d-%H%M')
    path = _os.path.join(d, f"{lab}__{stamp}.pkl")
    with open(path, 'wb') as fh:
        _pickle.dump(data, fh, protocol=4)
    try:                                                   # [Fix 90]
        px = data.get('prices')
        fp = dict(data.get('fingerprint') or {})
        fp.update({
            'label': data.get('target_label'),
            'legs': sorted((data.get('portfolio') or {}).get('legs') or []),
            'first_date': str(px.index[0].date()) if px is not None else None,
            'last_date': str(px.index[-1].date()) if px is not None else None,
            'n_rows': int(px.shape[0]) if px is not None else 0,
            'n_tickers': int(px.shape[1]) if px is not None else 0,
            'columns': sorted(map(str, px.columns)) if px is not None else []})
        with open(path[:-4] + '.json', 'w') as fh:
            _json.dump(fp, fh)
    except Exception:
        pass                       # sidecar is an optimization, never fatal
    print(f"  ✓ data cached → {path}")
    return path


def list_hedge_data(cache_dir=None):
    """[Fix 88/90] Cached downloads, newest first, with the coverage each one
    carries (read from the JSON sidecar — no unpickling)."""
    d = cache_dir or HEDGE_CACHE_DIR
    rows = []
    for p in sorted(_glob.glob(_os.path.join(d, '*.pkl')),
                    key=_os.path.getmtime, reverse=True):
        base = _os.path.basename(p)[:-4]
        lab, _, stamp = base.partition('__')
        rec = {'label': lab, 'saved': stamp,
               'MB': round(_os.path.getsize(p) / 1e6, 1), 'path': p,
               'last_date': None, 'n_tickers': None}
        try:                                               # [Fix 90]
            with open(p[:-4] + '.json') as fh:
                fp = _json.load(fh)
            rec['last_date'] = fp.get('last_date')
            rec['n_tickers'] = fp.get('n_tickers')
            rec['_fp'] = fp
        except Exception:
            pass
        rows.append(rec)
    return pd.DataFrame(rows)


def _busdays_since(date_str):
    """[Fix 90] Business days between a YYYY-MM-DD string and today."""
    if not date_str:
        return None
    try:
        return int(np.busday_count(pd.Timestamp(date_str).date(),
                                   datetime.now().date()))
    except Exception:
        return None


def check_cache_fit(target, data=None, fingerprint=None, stale_after=5):
    """[Fix 90] Is a cached download still the right one for THIS book?

    A download is reusable when every leg you want to hedge has prices in it
    — the engine excludes legs from the candidate pool and treats ex-legs as
    candidates ([Fix 66]), so leg churn inside the same book is fine. What is
    NOT fine is a leg that was never downloaded, or prices that stop before
    the period you care about. Returns a dict with 'status' in
    {'exact', 'compatible', 'stale', 'mismatch'} and a one-line 'message'.
    """
    legs = _coerce_targets(target)[0]
    if data is not None:
        cols = set(map(str, data['prices'].columns))
        fp_legs = sorted((data.get('portfolio') or {}).get('legs') or [])
        last = str(data['prices'].index[-1].date())
        fp = dict(data.get('fingerprint') or {})       # [Fix 119]
    else:
        fp = fingerprint or {}
        cols = set(fp.get('columns') or [])
        fp_legs = sorted(fp.get('legs') or [])
        last = fp.get('last_date')
    # [Fix 119] the hedging instruments changed since this was downloaded, so
    # the cached universe cannot contain them. Said plainly, because the
    # symptom otherwise is a hedge quietly built without the leg it needs.
    if fp.get('instrument_map') != _INSTRUMENT_MAP_HASH:
        return {'status': 'mismatch', 'missing': [], 'last_date': last,
                'message': ('needs a fresh download — the hedging-instrument '
                            'map changed since this was cached, so the saved '
                            'universe cannot contain the new instruments')}
    missing = [l for l in legs if l not in cols]
    if missing:
        return {'status': 'mismatch', 'missing': missing, 'last_date': last,
                'message': (f"needs a fresh download — "
                            f"{', '.join(m.split(' ')[0] for m in missing)} "
                            f"{'is' if len(missing) == 1 else 'are'} not in "
                            f"this dataset")}
    age = _busdays_since(last)
    same = sorted(legs) == fp_legs
    if age is not None and age > stale_after:
        return {'status': 'stale', 'missing': [], 'last_date': last,
                'age': age,
                'message': (f"prices stop at {last} — {age} business days "
                            f"old; re-download to include recent sessions")}
    base = ("matches this book exactly" if same
            else "covers every leg of this book (the book changed, the "
                 "universe still fits)")
    return {'status': ('exact' if same else 'compatible'), 'missing': [],
            'last_date': last, 'age': age,
            'message': f"{base} · prices through {last}"
                       + (f" ({age} business day{'s' if age != 1 else ''} "
                          f"old)" if age else " (current)")}


def load_hedge_data(which=0, cache_dir=None):
    """[Fix 88] Reload a cached download — zero API calls.

    `which` may be a path, a label fragment ('AAPL'), or an integer index
    into list_hedge_data() (0 = most recent)."""
    if isinstance(which, str) and which.endswith('.pkl') and _os.path.exists(which):
        path = which
    else:
        cat = list_hedge_data(cache_dir)
        if not len(cat):
            raise FileNotFoundError(
                f"[Fix 88] no cached downloads in "
                f"{cache_dir or HEDGE_CACHE_DIR}")
        if isinstance(which, int):
            if which >= len(cat):
                raise IndexError(f"[Fix 88] only {len(cat)} cached downloads")
            path = cat.iloc[which]['path']
        else:
            hit = cat[cat['label'].str.contains(str(which), case=False,
                                                regex=False)]
            if not len(hit):
                raise FileNotFoundError(
                    f"[Fix 88] nothing cached matching {which!r}. Available: "
                    f"{list(cat['label'])}")
            path = hit.iloc[0]['path']
    with open(path, 'rb') as fh:
        data = _pickle.load(fh)
    px = data.get('prices')
    print(f"  ✓ loaded {_os.path.basename(path)} — "
          f"{px.shape[0]} rows × {px.shape[1]} tickers, no API calls")
    return data


# =============================================================================
# CELL 2: ENGINE
# =============================================================================
# ── [Fix 52] METRICS GLOSSARY ────────────────────────────────────────────────
# The report prints four different R-squared numbers and they are routinely
# confused with each other. They are not competing estimates of one quantity;
# each answers a different question, and the differences between them are the
# most informative part of the report. Printed at the top of section [1].
# [Fix 115] was a hand-aligned block of text passed to print(). Hand alignment
# survives a terminal and nothing else — in a notebook the whole thing
# collapsed into one paragraph. It is data, so it is now rows, and it renders
# through the same table as everything else.
R2_GLOSSARY_ROWS = [
    ('1 · Fitted and scored on the\n    same days  (in-sample R²)',
     'flattered — a sanity check only',
     'Describes the fitted training data; it is not a forecast. Raw R² from '
     'this Ridge fit with an intercept should be nonnegative on nonconstant '
     'training data. The adjusted heuristic can be negative.'),
    ('2 · Fitted on the past, scored\n    on what came next',
     'honest weights, flattered recipe',
     'Fit on the last N days, score on the days that follow, repeat, average. '
     'The WEIGHTS never see the days they are graded on — but the recipe was '
     'chosen by looking at all of them.'),
    ('3 · This recipe, re-fitted\n    before each test stretch',
     'honest weights AND honest days',
     'The chosen recipe re-fitted strictly on data from before each held-back '
     'stretch. A small bias remains, because the recipe itself was picked '
     'using all the data.'),
    ('4 · The whole method re-run\n    from scratch each time',
     'the number to trade on',
     'Everything — choosing the recipe and fitting the weights — redone using '
     'only data from before each held-back stretch. This is closest to what '
     'running this tool live would actually have delivered.'),
]
R2_GLOSSARY_NOTE = ('These scores need not fall in a fixed order: they use '
                    'different windows and sometimes different configurations. '
                    'Prefer nested unseen evidence. Negative OOS R² means '
                    'worse squared return-tracking error than the test-window '
                    'mean; it does not by itself prove that volatility rose. '
                    'Check volatility reduction separately. Adjusted R² here '
                    'uses nominal regressor count, an OLS-style Ridge heuristic.')

# [Fix 116] The report is read by people who do not build these models. Where a
# term is unavoidable — it is on a chart axis, in a column header, or it is what
# a desk would actually say out loud — it is defined here once, in the appendix,
# where it costs nothing to a reader who does not need it.
WORDS_USED = [
    ('Hedge / basket', 'the set of names you trade against your position',
     'Shorting the basket is meant to cancel the part of your position that '
     'moves with the rest of the market.'),
    ('Return-tracking R²', 'squared error relative to the evaluated target mean',
     '1 means exact fitted-return tracking; 0 matches the error from the '
     'evaluated target mean; negative is worse. Zero does not imply zero '
     'correlation. Volatility reduction measures risk removed separately.'),
    ('Drift / tracking error', 'the part the hedge does NOT cancel',
     'Quoted as %/yr. This is what you actually carry, and what a risk limit '
     'should be set against.'),
    ('Unseen data / out-of-sample', 'days the model had never looked at',
     'The only honest test. Any score measured on the days a model was fitted '
     'to is a description of the past, not a forecast.'),
    ('Its own data / in-sample', 'the days the model WAS fitted on',
     'Useful as a fit diagnostic. It is not a guaranteed ceiling on later '
     'scores and not an expectation of future hedge performance.'),
    ('Test stretch / window', 'a block of consecutive days held back',
     'The model is fitted on everything before it and graded on it, then the '
     'block moves forward.'),
    ('Lookback', 'how many days of history each refit is fitted on',
     'Short adapts faster and is noisier; long is steadier and staler.'),
    ('Gross / net', 'total position size vs the direction left over',
     'Gross $74 per $100 means you trade $74 of hedge for every $100 of book. '
     'Borrow and financing scale with gross.'),
    ('Market drivers', 'the shared movements pulled out of the universe',
     'Formally principal components. The first one is usually "the whole '
     'market went up"; later ones are sector or style moves.'),
    ('Refit', 'recomputing the weights on newer data',
     'The RE-HEDGE button. Weights go stale as relationships move.'),
    ('1 standard deviation', 'a typical, not a worst, outcome',
     'A dispersion measure. Gaussian coverage rules are approximations and '
     'need not hold for heavy-tailed financial returns.'),
]
# ─────────────────────────────────────────────────────────────────────────────
# [Fix 42] Robust PCA inputs
#   Ordinary PCA minimizes squared reconstruction error without requiring
#   Gaussian observations. Daily
#   equity returns are fat-tailed and skewed, so a handful of jump days can
#   dominate the leading components and distort the loading-space "similarity"
#   used to pick candidates. Two low-cost defenses, applied ONLY to the PCA
#   candidate-SELECTION step (never to the RidgeCV hedge ratios, which stay fit
#   on the true returns):
#     • winsorize_pct : clip each column at its pct / 1-pct quantiles before
#       standardizing, so outliers cannot hijack the eigenvectors.
#     • robust_cov='ledoit' : regularize covariance eigenvalues using isotropic
#       Ledoit-Wolf shrinkage (well-conditioned when p >> n). This does not
#       change sample eigenvectors and is not an outlier-robust estimator.
# ─────────────────────────────────────────────────────────────────────────────
def _winsorize_returns(df, pct):
    """Clip every column to its [pct, 1-pct] quantiles. pct=0 -> no-op
    (exact pre-Fix-42 behavior)."""
    if not pct or pct <= 0:
        return df
    lo = df.quantile(pct)
    hi = df.quantile(1.0 - pct)
    return df.clip(lower=lo, upper=hi, axis=1)


class _PCAShim:
    """Uniform PCA result (ordinary or Ledoit-Wolf) exposing the same three
    attributes the rest of the code reads off a fitted sklearn PCA object."""
    __slots__ = ('components_', 'explained_variance_', 'explained_variance_ratio_')

    def __init__(self, components_, explained_variance_, explained_variance_ratio_):
        self.components_ = components_
        self.explained_variance_ = explained_variance_
        self.explained_variance_ratio_ = explained_variance_ratio_


def _pca_fit(tr_sc, n_pc, robust_cov='none'):
    """Thin SVD PCA, without a p-by-p covariance eigendecomposition/inverse.

    Isotropic Ledoit-Wolf shrinkage leaves sample eigenvectors unchanged.
    Its leading eigenvalues are (1-shrinkage)*sample + shrinkage*mu.
    Trace/Frobenius identities compute the same shrinkage from the smaller
    sample Gram matrix when p > n; no approximation to the covariance is used.
    For a fully isotropic estimate, sample directions provide a deterministic
    basis for the tied eigenspace. Ordinary PCA retains its n-1 normalization.
    """
    X = np.asarray(tr_sc, dtype=float)
    X = X - X.mean(axis=0)
    n, p = X.shape
    count = int(min(n_pc, p, n - 1))
    if count < 1:
        raise ValueError('PCA needs at least two observations and one feature')
    _, singular, vectors = np.linalg.svd(X, full_matrices=False)
    if robust_cov == 'ledoit':
        row_sq = np.sum(X * X, axis=1)
        mu = float(row_sq.sum() / (n * p))
        gram = X @ X.T if p > n else X.T @ X
        delta_raw = float(np.sum(gram * gram) / n**2)
        beta = (float(np.dot(row_sq, row_sq)) / n - delta_raw) / (p * n)
        delta = (delta_raw - p * mu**2) / p
        shrinkage = float(np.clip(beta / delta, 0, 1)) if delta > 0 else 0.0
        evals = (1 - shrinkage) * singular[:count]**2 / n + shrinkage * mu
        total = p * mu
    else:
        evals = singular[:count]**2 / (n - 1)
        total = float(np.sum(singular**2) / (n - 1))
    evr = evals / total if total > 0 else np.zeros_like(evals)
    return _PCAShim(vectors[:count], evals, evr)


# ─────────────────────────────────────────────────────────────────────────────
# [Fix 43] Style-factor proxies for the factor-leakage diagnostic. Each factor
# maps to a preferred US proxy and an international fallback; the diagnostic uses
# whichever is actually present in the retained universe.
# ─────────────────────────────────────────────────────────────────────────────
FACTOR_PROXIES = {
    'Market':   ('SPY', 'ACWI'),
    'Size(SC)': ('IWM', 'SIZE'),
    'Momentum': ('MTUM', 'IMTM'),
    'Value':    ('VLUE', 'IVLU'),
    'Quality':  ('QUAL', 'IQLT'),
    'LowVol':   ('USMV', 'ACWV'),
}


def _build_universe_factors(returns, caps_map, stock_cols,
                            mom_skip=21, min_names=6):
    """[Fix 47] Build returns-based factor-mimicking portfolios FROM the
    downloaded universe itself, so factor diagnostics work in EVERY market —
    including markets with no factor ETFs at all (e.g. an ASX name like GMD AU,
    where the US factor ETFs are dropped by the timezone filter).
      MKT(univ) : equal-weight mean of the universe stocks (local market proxy)
      SMB(univ) : small-cap minus big-cap tercile return  (size)   [needs caps]
      WML(univ) : winners minus losers tercile by trailing return  (momentum)
      VOL(univ) : high-vol minus low-vol tercile by realized vol  (volatility)
                  [Fix 48]
      REV(univ) : losers minus winners on the prior 21d return  (short-term
                  reversal, rolling) — the dominant A-share effect  [Fix 55]
    Returns a DataFrame (whichever of MKT/SMB/WML could be built) aligned to
    returns.index; empty if the universe is too small."""
    cols = [c for c in stock_cols if c in returns.columns]
    out = {}
    if len(cols) >= 2:
        out['MKT(univ)'] = returns[cols].mean(axis=1)
    capped = [(c, caps_map.get(c)) for c in cols]
    capped = [(c, m) for c, m in capped
              if m is not None and np.isfinite(m) and m > 0]
    if len(capped) >= min_names:
        capped.sort(key=lambda x: x[1])
        k = max(1, len(capped) // 3)
        small = [c for c, _ in capped[:k]]
        big = [c for c, _ in capped[-k:]]
        out['SMB(univ)'] = (returns[small].mean(axis=1)
                            - returns[big].mean(axis=1))
    if len(cols) >= min_names and len(returns) > mom_skip + 20:
        trail = returns[cols].iloc[:-mom_skip].sum().dropna().sort_values()
        if len(trail) >= min_names:
            k = max(1, len(trail) // 3)
            los = trail.index[:k].tolist()
            win = trail.index[-k:].tolist()
            out['WML(univ)'] = (returns[win].mean(axis=1)
                                - returns[los].mean(axis=1))
    if len(cols) >= min_names:                      # [Fix 48] volatility factor
        vol = returns[cols].std().dropna().sort_values()
        if len(vol) >= min_names:
            k = max(1, len(vol) // 3)
            lowv = vol.index[:k].tolist()
            highv = vol.index[-k:].tolist()
            out['VOL(univ)'] = (returns[highv].mean(axis=1)
                                - returns[lowv].mean(axis=1))
    # [Fix 55] REV(univ) — short-term (1-month) reversal.
    #   In A-shares 12-1 momentum (the WML factor above) is famously weak or
    #   outright inverted, while one-month reversal is the dominant
    #   cross-sectional effect. Without this factor the leakage diagnostic
    #   has no way to report the single largest style exposure an onshore
    #   China basket can carry. Unlike the static WML/VOL sorts this factor
    #   is formed on a ROLLING basis — each day, losers-minus-winners on the
    #   PRIOR 21d return, shifted by one day so nothing is known in advance.
    #   The first ~22 rows are NaN; _factor_leakage's finite-mask handles it.
    if len(cols) >= min_names and len(returns) > 42:
        past = returns[cols].rolling(21).sum().shift(1)
        lo_q = past.quantile(1.0 / 3.0, axis=1)
        hi_q = past.quantile(2.0 / 3.0, axis=1)
        rev = (returns[cols].where(past.le(lo_q, axis=0)).mean(axis=1)
               - returns[cols].where(past.ge(hi_q, axis=0)).mean(axis=1))
        out['REV(univ)'] = rev
    return pd.DataFrame(out)


def _factor_leakage(returns, target, weights, caps_map=None, stock_cols=None):
    """[Fix 43/47] Returns-based factor-exposure check. Regress the target AND
    the hedged residual (target - basket.weights) on a set of factors, and
    compare the betas: a residual beta near 0 means the hedge neutralized that
    factor; near the target beta means it did not.

    [Fix 47] Market / Size / Momentum come from factor-mimicking portfolios
    BUILT FROM THE UNIVERSE (so they exist in every market, ETF or not);
    Value / Quality / LowVol come from style ETFs when those survive in the
    universe. [Fix 50] Factors are sequentially orthogonalized before the
    regression so collinearity (e.g. SMB vs VOL) cannot inflate the betas.
    Returns a DataFrame, or None if fewer than two factors are available."""
    present = {}
    for fac in ('Value', 'Quality', 'LowVol'):          # ETF-only factors
        for p in FACTOR_PROXIES[fac]:
            hit = next((c for c in returns.columns
                        if c.split(' ')[0] == p and c != target), None)
            if hit is not None:
                present[fac] = returns[hit]
                break
    if caps_map is not None and stock_cols is not None:  # [Fix 47] local factors
        uf = _build_universe_factors(returns, caps_map, stock_cols)
        for name in uf.columns:
            present[name] = uf[name]
    if len(present) < 2:                                 # fallback: ETF market/size/mom
        for fac in ('Market', 'Size(SC)', 'Momentum'):
            for p in FACTOR_PROXIES[fac]:
                hit = next((c for c in returns.columns
                            if c.split(' ')[0] == p and c != target), None)
                if hit is not None:
                    present[fac] = returns[hit]
                    break
    if len(present) < 2:
        return None
    # [Fix 50] sequential orthogonalization. The factors overlap heavily —
    # small caps ARE more volatile (SMB ~ VOL), style ETFs share market beta —
    # and collinear regressors inflate/destabilize individual betas (this is
    # why adding global factor ETFs can make the printed betas JUMP UP).
    # Regress each factor on the ones before it (fixed order) and keep the
    # residual: each beta then reads as the INCREMENTAL exposure not already
    # explained by the factors listed above it. Diagnostics only — hedge
    # selection and weights are untouched.
    # [Fix 55] REV(univ) sits AFTER WML so its beta reads as reversal exposure
    # not already explained by market / size / momentum.
    _ORDER = ['MKT(univ)', 'SMB(univ)', 'WML(univ)', 'REV(univ)', 'VOL(univ)',
              'Value', 'Quality', 'LowVol', 'Market', 'Size(SC)', 'Momentum']
    names = ([k for k in _ORDER if k in present]
             + [k for k in present if k not in _ORDER])
    y_t = returns[target].values
    basket = [c for c in weights.index if c in returns.columns]
    resid = y_t - returns[basket].values.dot(weights.reindex(basket).values)
    Fraw = np.column_stack([np.asarray(present[n], dtype=float) for n in names])
    m = np.isfinite(Fraw).all(axis=1) & np.isfinite(y_t) & np.isfinite(resid)
    Fo = np.empty((int(m.sum()), len(names)))
    for j in range(len(names)):
        f = Fraw[m, j]
        if j:
            Xp = np.column_stack([np.ones(len(f)), Fo[:, :j]])
            f = f - Xp @ np.linalg.lstsq(Xp, f, rcond=None)[0]
        Fo[:, j] = f
    Xc = np.column_stack([np.ones(len(Fo)), Fo])
    bt = np.linalg.lstsq(Xc, y_t[m], rcond=None)[0][1:]
    br = np.linalg.lstsq(Xc, resid[m], rcond=None)[0][1:]
    return pd.DataFrame({'factor': names,
                         'target_beta': np.round(bt, 3),
                         'residual_beta': np.round(br, 3)})


PORTFOLIO_COL = '__PORTFOLIO__'   # [Fix 46] synthetic column for a multi-name book


def _coerce_targets(target):
    """[Fix 46/64] Normalize the target argument into a hedging job.

    THE FORMAT CONTRACT — three accepted shapes:

      1. str                       single-name hedge
           'AAPL US Equity'

      2. list / tuple of str       EQUAL-WEIGHT LONG book (all legs long,
           ['AAPL US Equity',      same size). Short tickers are fine —
            'NVDA US Equity',      'AAPL' / 'NVDA US' / '700 HK' are
            'MSFT US Equity']      resolved by _fmt_bbg_ticker.

      3. dict {ticker: weight}     WEIGHTED book. Weights are RELATIVE
           {'AAPL US Equity': +0.5,   NOTIONALS in any consistent unit —
            'NVDA US Equity': +0.3,   dollars, percent of book, or plain
            'MSFT US Equity': -0.2}   ratios; sign = direction (+ long,
                                      - short). They do NOT need to sum
                                      to 1: everything is normalized by
                                      GROSS (sum of |w|), which keeps a
                                      market-neutral book well defined
                                      (net-sum normalization would divide
                                      by ~0).

    What the engine then does with it: the book becomes ONE synthetic
    return series, sum(w_i * r_i) per day, and every downstream number —
    R², vol reduction, and the hedge recipe itself — refers to that NET
    series. "per $100" in the recipe means per $100 of GROSS book value.
    So for {'AAPL': +50, 'NVDA': +30, 'MSFT': -20} the book is normalized
    to (+0.5, +0.3, -0.2) and a recipe line of "short $80 QQQ" means:
    for every $100 of gross notional you hold across the three legs,
    short $80 of QQQ against the NET exposure.

    Returns (legs, weights_dict, is_portfolio, label)."""
    if isinstance(target, str):
        # [Fix 67] normalize AND validate. A bare short name ('AAPL') has no
        # exchange code, cannot be resolved by Bloomberg, and used to sail
        # through here only to die inside bbg_hist with a cryptic "no price
        # data" error. Minimum viable form: 'AAPL US'.
        tk = _fmt_bbg_ticker(target)
        if tk is None:
            raise ValueError(
                f"[Fix 67] '{target}' has no exchange code — Bloomberg "
                f"needs one: write 'AAPL US', 'AAPL US Equity' or '700 HK'")
        return [tk], {}, False, tk.split(' ')[0]
    # [Fix 64] fail loudly on malformed books instead of mid-pipeline
    if isinstance(target, dict):
        if not target:
            raise ValueError("[Fix 64] portfolio dict is empty")
        _bad = [str(k) for k in target if _fmt_bbg_ticker(str(k)) is None]
        if _bad:                                              # [Fix 67]
            raise ValueError(
                f"[Fix 67] ticker(s) {_bad} have no exchange code — "
                f"Bloomberg needs one: write 'AAPL US', 'AAPL US Equity' "
                f"or '700 HK', never a bare short name")
        try:
            items = [(_fmt_bbg_ticker(str(k)), float(v))
                     for k, v in target.items()]
        except (TypeError, ValueError):
            raise ValueError(
                "[Fix 64] portfolio dict values must be numbers "
                "(relative notionals, sign = direction) — got "
                f"{ {k: type(v).__name__ for k, v in target.items()} }")
        if all(v == 0.0 for _, v in items):
            raise ValueError("[Fix 64] all portfolio weights are zero")
    elif isinstance(target, (list, tuple)):
        if not target:
            raise ValueError("[Fix 64] portfolio list is empty")
        if not all(isinstance(k, str) for k in target):
            raise ValueError(
                "[Fix 64] a portfolio LIST must contain tickers only "
                "(equal-weight long book). For custom weights or shorts "
                "use a dict: {'AAPL US Equity': +0.5, 'MSFT US Equity': "
                "-0.5}")
        _bad = [str(k) for k in target if _fmt_bbg_ticker(str(k)) is None]
        if _bad:                                              # [Fix 67]
            raise ValueError(
                f"[Fix 67] ticker(s) {_bad} have no exchange code — "
                f"Bloomberg needs one: write 'AAPL US', 'AAPL US Equity' "
                f"or '700 HK', never a bare short name")
        items = [(_fmt_bbg_ticker(str(k)), 1.0) for k in target]
    else:
        raise ValueError(
            f"[Fix 64] target must be a str, list of str, or dict of "
            f"ticker->weight — got {type(target).__name__}")
    legs = [k for k, _ in items]
    if len(set(legs)) != len(legs):
        raise ValueError(f"[Fix 64] duplicate legs after ticker "
                         f"normalization: {legs}")
    if len(legs) == 1:
        # a one-leg "book" is just a single-name hedge — treat it as one
        return [legs[0]], {}, False, legs[0].split(' ')[0]
    gross = sum(abs(v) for _, v in items) or 1.0
    weights = {k: v / gross for k, v in items}
    label = 'PF[' + '+'.join(k.split(' ')[0] for k in legs) + ']'
    return legs, weights, True, label


def _validation_tier(rows, lookback_options, cv_test_window, cv_n_folds,
                     outer_window, outer_folds, purge, basket_size_options,
                     rolling_refit_every, strict_basket_sizes=False):
    """[Fix 77/85] Resolve the validation protocol for a window of `rows`
    return rows. Extracted verbatim from find_best_hedge in [Fix 85] so that
    preview_window() and the GUI describe the protocol that will ACTUALLY
    run — a second copy of this logic would drift from the engine.

      FULL      enough rows — the full walk-forward + nested protocol.
      REDUCED   walk-forward CV + outer windows with shorter lookbacks /
                test windows and fewer folds. Wider error bars.
      HOLDOUT   too short for walk-forward: fit once on the first ~80%,
                score ONCE on the held-out tail. Thin but honest.
      IN-SAMPLE under ~60 rows: no OOS evidence is possible. Descriptive
                only; the basket is capped and the ticket says so loudly.

    Returns a dict of resolved settings plus 'notes' (lines to print)."""
    if rows < 8:
        raise ValueError(f"[Fix 77] only {rows} return rows in the window — "
                         f"need at least 8 even for a descriptive fit")
    need_full = (max(lookback_options) + cv_test_window * cv_n_folds
                 + outer_window * outer_folds)
    t = {'mode': 'FULL', 'rows': rows, 'need_full': need_full, 'hold_rows': 0,
         'lookback_options': tuple(lookback_options),
         'cv_test_window': cv_test_window, 'cv_n_folds': cv_n_folds,
         'outer_window': outer_window, 'outer_folds': outer_folds,
         'min_train_rows': 50,          # [Fix 80] inner-CV minimum train block
         'rolling_refit_every': rolling_refit_every,
         'basket_size_options': tuple(basket_size_options), 'notes': []}
    if rows < need_full:
        _tw = int(np.clip(rows // 8, 10, cv_test_window))
        _nf = int(min(cv_n_folds, 3))
        _of = int(min(outer_folds, 2))
        _lb_max = rows - (_tw + purge) * (_nf + _of)
        if _lb_max >= 30:
            t['mode'] = 'REDUCED'
            t['cv_test_window'] = t['outer_window'] = _tw
            t['cv_n_folds'], t['outer_folds'] = _nf, _of
            t['lookback_options'] = tuple(sorted({max(30, _lb_max // 2),
                                                  _lb_max}))
            # [Fix 80] the inner CV skips folds whose training block is
            # shorter than min_train_rows; with REDUCED lookbacks the fixed
            # 50-row floor rejected every fold. Track the tier's own floor.
            t['min_train_rows'] = min(50, max(5, int(np.ceil(
                MIN_TRAIN_COVERAGE * min(t['lookback_options'])))))
            t['rolling_refit_every'] = min(int(rolling_refit_every), _tw)
            t['notes'] += [
                f"  [Fix 77] validation mode REDUCED — {rows} rows < "
                f"{need_full} needed for the full protocol",
                f"    → lookbacks {t['lookback_options']}, CV {_nf}×{_tw}d,"
                f" outer {_of}×{_tw}d; fewer/shorter windows ⇒ wider error"
                f" bars — mind the CI"]
        elif rows >= 60:
            t['mode'] = 'HOLDOUT'
            t['hold_rows'] = max(12, rows // 5)
            t['notes'] += [
                f"  [Fix 77] validation mode HOLDOUT — {rows} rows is too "
                f"short for walk-forward CV",
                f"    → fit on the first {rows - t['hold_rows'] - purge} "
                f"rows, score ONCE on the last {t['hold_rows']} unseen rows"]
        else:
            t['mode'] = 'IN-SAMPLE'
            t['notes'].append(
                f"  [Fix 77] validation mode IN-SAMPLE — {rows} rows: no "
                f"out-of-sample evidence is possible at this length; treat "
                f"every number as descriptive")
    # cap the basket so the fit window keeps ≥ ~8 obs per regressor
    _fit_len = (min(rows, max(t['lookback_options']))
                if t['mode'] in ('FULL', 'REDUCED') else rows - t['hold_rows'])
    _bs_cap = max(2, _fit_len // 8)
    if not strict_basket_sizes and max(basket_size_options) > _bs_cap:
        sizes = tuple(b for b in basket_size_options if b <= _bs_cap)
        if not sizes or (any(b >= 2 for b in basket_size_options) and not any(b >= 2 for b in sizes)):
            raise ValueError(f'History supports basket sizes up to {_bs_cap} under the default '
                             'sample rule. Choose smaller sizes or explicitly set basket_size_range '
                             'for a descriptive regularized fit.')
        t['basket_size_options'] = sizes
        t['notes'].append(f'Unsupported sizes above {_bs_cap} omitted; requested sizes are exact.')
    return t


TIER_MEANING = {
    'FULL': 'walk-forward CV and nested selection windows; inspect the actual scores and coverage',
    'REDUCED': 'CV and nested evaluation on shorter or fewer windows; evidence is more limited',
    'HOLDOUT': 'one reserved test period; limited evidence, not a multi-window stability test',
    'IN-SAMPLE': 'fitted descriptive evidence only; no unseen validation was available',
}


def preview_window(data, sample_window=None, lookback_options=(126, 252),
                   cv_test_window=42, cv_n_folds=5, outer_window=None,
                   outer_folds=3, basket_size_options=(1, 2, 3, 5, 7),
                   quiet=False, basket_size_range=None):
    """[Fix 85] What will this sample_window actually buy me? Reports the
    session count and the validation tier BEFORE you spend minutes on a run,
    using the same _validation_tier the engine uses. Cheap and API-free."""
    basket_size_options = _basket_sizes(basket_size_options, basket_size_range)
    idx = data['prices'].index
    if sample_window is not None:
        s, e = _parse_sample_window(sample_window, idx)
        sub = idx[(idx >= s) & (idx <= e)]
    else:
        sub = idx
    ow = outer_window or cv_test_window
    out = {'sessions': len(sub),
           'start': (sub[0] if len(sub) else None),
           'end': (sub[-1] if len(sub) else None)}
    if len(sub) < 10:
        out['mode'] = None
        if not quiet:
            print(f"  ⚠ only {len(sub)} sessions in that window — the engine "
                  f"needs ≥ 10 (and ≥ 8 return rows).")
        return out
    modes = {}
    for pu, lab in ((0, 'daily'), (1, '2-day (cross-timezone)')):
        try:
            t = _validation_tier(len(sub) - 1 - pu, lookback_options,
                                 cv_test_window, cv_n_folds, ow, outer_folds,
                                 pu, basket_size_options, 21,
                                 strict_basket_sizes=basket_size_range is not None)
            modes[lab] = t['mode']
        except ValueError:
            modes[lab] = None
    out['mode'] = modes.get('daily')
    out['mode_two_day'] = modes.get('2-day (cross-timezone)')
    if not quiet:
        print(f"  {out['sessions']} sessions "
              f"({out['start']:%d %b %Y} → {out['end']:%d %b %Y})")
        if out['mode'] == out['mode_two_day']:
            print(f"  → validation tier: {out['mode']}")
        else:
            print(f"  → validation tier: {out['mode']} (daily) / "
                  f"{out['mode_two_day']} if the universe is cross-timezone")
        for m in dict.fromkeys(v for v in modes.values() if v):
            print(f"     {m:<9} {TIER_MEANING[m]}")
    return out


def _parse_sample_window(sample_window, idx):
    """[Fix 76] Resolve `sample_window` into (start, end) Timestamps.

    Accepted forms:
      '3m' / '90d' / '26w' / '1y'      last N months/days/weeks/years up to
                                       the END of the downloaded data
      (start, end) tuple               absolute dates; each entry is anything
                                       pd.Timestamp parses ('2026-07-13',
                                       '13-Jul-2026', a Timestamp) or None
                                       for "no bound on this side"
    """
    import re as _re
    if isinstance(sample_window, str):
        m = _re.match(r'^\s*(\d+)\s*([dwmy])\s*$', sample_window.lower())
        if not m:
            raise ValueError(
                f"[Fix 76] sample_window string must look like '3m', '90d', "
                f"'26w' or '1y' — got {sample_window!r}. For absolute dates "
                f"pass a (start, end) tuple.")
        n, u = int(m.group(1)), m.group(2)
        end = idx[-1]
        off = {'d': pd.Timedelta(days=n), 'w': pd.Timedelta(weeks=n),
               'm': pd.DateOffset(months=n), 'y': pd.DateOffset(years=n)}[u]
        return pd.Timestamp(end - off), pd.Timestamp(end)
    if isinstance(sample_window, (tuple, list)) and len(sample_window) == 2:
        s, e = sample_window
        try:
            start = pd.Timestamp(s) if s is not None else pd.Timestamp(idx[0])
            end = pd.Timestamp(e) if e is not None else pd.Timestamp(idx[-1])
        except (ValueError, TypeError):
            raise ValueError(f"[Fix 76] cannot parse sample_window dates "
                             f"{sample_window!r} — use e.g. "
                             f"('2026-07-13', '2026-07-28')")
        if start >= end:
            raise ValueError(f"[Fix 76] sample_window start {start:%Y-%m-%d} "
                             f"is not before end {end:%Y-%m-%d}")
        return start, end
    raise ValueError(f"[Fix 76] sample_window must be a string like '3m' or "
                     f"a (start, end) tuple — got "
                     f"{type(sample_window).__name__}")


def _verdict_banner(grade, reasons, subtitle=''):
    """[Fix 87] Colour-coded verdict banner in Jupyter; plain text elsewhere.
    Any rendering failure falls through to the text version, so the report
    can never be lost to a display problem.

    [Fix 115] Was set in monospace, which made the one block a reader looks at
    first the least legible thing on the page. It now uses the report's own
    type scale, and it records itself into the transcript like every other
    block."""
    _kv_flush()
    pal = {'✓': ('#1b6b3a', '#edf7f0'), '△': ('#8a5a00', '#fff8ea'),
           '✗': ('#8c1c1c', '#fdeeee'), '?': ('#3d4650', '#eff2f5')}
    grade, subtitle = _clean(grade), _clean(subtitle)
    reasons = [_clean(r) for r in reasons[:4]]
    fg, bg = pal.get(grade[:1], pal['?'])
    _tx('', f"  VERDICT   {grade}")
    if subtitle:
        _tx(f"            {subtitle}")
    _tx(*[f"            · {r}" for r in reasons])
    try:
        if _IN_JUPYTER:
            li = ''.join(
                f'<li style="margin:2px 0">{_html.escape(r)}</li>'
                for r in reasons)
            _ipy_display(_HTML(
                f'<div style="border-left:5px solid {fg};background:{bg};'
                f'padding:12px 16px;margin:10px 0 14px 0;border-radius:3px;'
                f'font-family:{_RF_UI};max-width:{_RF_MAXW}">'
                f'<div style="font-size:17px;font-weight:700;color:{fg};'
                f'letter-spacing:.01em">{_html.escape(grade)}</div>'
                + (f'<div style="font-size:12.5px;color:{_RF_INK};'
                   f'margin-top:3px;line-height:1.5">'
                   f'{_html.escape(subtitle)}</div>' if subtitle else '')
                + f'<ul style="margin:8px 0 0 0;padding-left:18px;'
                  f'font-size:12px;color:{_RF_MUTE};line-height:1.5">'
                  f'{li}</ul></div>'))
            return
    except Exception:
        pass
    print(f"\n  VERDICT   {grade}")
    if subtitle:
        print(f"            {subtitle}")
    for r in reasons:
        print(f"            · {r}")


def _fmt_money_mm(x_mm):
    """[Fix 101] Format a USD-millions figure the way a desk reads it:
    $2.51mm, $316k, $8.40. Avoids '$2,506k'."""
    a = abs(float(x_mm))
    if a >= 1.0:
        return f"${a:,.2f}mm"
    if a >= 0.001:
        return f"${a*1e3:,.0f}k"
    return f"${a*1e6:,.0f}"


def _ordinal(n):
    """[Fix 101] 1st / 2nd / 3rd / 33rd / 11th."""
    n = int(round(n))
    if 10 <= n % 100 <= 20:
        suf = 'th'
    else:
        suf = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suf}"


def _horizon_sigma(resid, h, te_ann, two_day):
    """[Fix 92] Expected 1-sigma hedge slippage over an h-row holding period.

    The naive answer is te_ann * sqrt(h/252) — correct only if residuals are
    serially uncorrelated. If they trend (an under-hedged drifting factor),
    h-day risk is LARGER than the daily numbers imply. The variance ratio
    VR = Var(sum of h residuals) / (h * Var(single residual)), estimated on
    overlapping h-row sums, corrects this; VR>1 means residuals compound.
    For 2-day overlapping rows the construction already double-counts, so
    only the iid scaling is used there (VR would be biased). Returns
    (sigma_over_h, vr) with vr=NaN when not estimable."""
    base = te_ann * np.sqrt(h / 252.0)
    r = np.asarray(resid, dtype=float)
    r = r[np.isfinite(r)]
    if two_day or h < 2 or len(r) < max(3 * h, 40):
        return base, np.nan
    s = pd.Series(r)
    rh = s.rolling(h).sum().dropna().values
    v1 = float(np.var(r))
    if v1 <= 1e-18 or len(rh) < 20:
        return base, np.nan
    vr = float(np.var(rh) / (h * v1))
    vr = float(np.clip(vr, 0.25, 4.0))          # tail-guard the estimate
    # ── [Fix 111] THE VR MAY RAISE THE RISK NUMBER, NEVER LOWER IT ─────────
    # Measured (synthetic, 1000 basket/seed pairs, train 500 rows, score the
    # next 500): the in-sample variance ratio has essentially NO
    # out-of-sample persistence —
    #     corr(VR_in, VR_out)     = -0.32 .. +0.18   across h = 21/63/126
    # while the TRUE ratio matters a great deal —
    #     corr(VR_out, realised)  = +0.54 .. +0.86
    # so the quantity is real and large (p10-p90 spans 0.67-1.24 at h=21 and
    # 0.32-1.32 at h=126) but is NOT forecastable from the sample in hand.
    #
    # For SELECTION that is fatal, and it is why the horizon deliberately
    # does not enter the config search — see the [Fix 100]/[Fix 112] note in
    # find_best_hedge. For REPORTING there is no winner's curse, so a noisy
    # estimate is tolerable in the conservative direction only:
    #   vr > 1  keep it. Residuals that compounded are a warning, and a
    #           warning that turns out to be unnecessary costs nothing.
    #   vr < 1  DISCARD it. This is the dangerous branch: a vr of 0.25 —
    #           inside the old clip — HALVED the reported h-day risk on the
    #           strength of an estimate with zero forecasting power. There is
    #           no version of prudent risk reporting in which that is right.
    # The raw estimate is still returned so the report can show it.
    return base * np.sqrt(max(vr, 1.0)), vr


def _block_bootstrap_ci(y, resid, n_boot=2000, block=None, seed=0, ann=1.0):
    """[Fix 70] Circular block bootstrap CI for the pooled OOS R-squared and
    the annualized tracking error. Hedge residuals are serially dependent
    (volatility clustering; 2-day overlapping returns are MA(1) by
    construction), so an iid bootstrap understates uncertainty. Contiguous
    blocks of (target, residual) PAIRS are resampled with wrap-around, which
    preserves both the dependence and the y-vs-residual pairing. Block length
    defaults to ~n^(1/3) (Politis-Romano rate) floored at 5; pass block=8+
    for 2-day overlapping returns. Percentile intervals; the seed is fixed so
    two runs of the same report print the same CI. NOTE: the CI conditions on
    the fitted weights — refit noise sits ON TOP of this interval, so read it
    as a floor on the uncertainty, not the whole of it. Returns dict or None
    (series too short / degenerate)."""
    y = np.asarray(y, dtype=float)
    r = np.asarray(resid, dtype=float)
    n = len(y)
    if n < 30 or len(r) != n:
        return None
    b = int(block) if block else max(5, int(round(n ** (1.0 / 3.0))))
    b = min(b, n)
    k = int(np.ceil(n / b))
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(int(n_boot), k))
    idx = (starts[:, :, None] + np.arange(b)[None, None, :]) % n
    idx = idx.reshape(int(n_boot), -1)[:, :n]
    ys, rs = y[idx], r[idx]
    sst = ((ys - ys.mean(axis=1, keepdims=True)) ** 2).sum(axis=1)
    sse = (rs ** 2).sum(axis=1)
    with np.errstate(divide='ignore', invalid='ignore'):
        r2s = np.where(sst > MIN_RETURN_STD ** 2, 1.0 - sse / sst, np.nan)
    tes = rs.std(axis=1) * ann
    r2s = r2s[np.isfinite(r2s)]
    if not len(r2s):
        return None
    return {'r2_lo': float(np.percentile(r2s, 2.5)),
            'r2_hi': float(np.percentile(r2s, 97.5)),
            'te_lo': float(np.percentile(tes, 2.5)),
            'te_hi': float(np.percentile(tes, 97.5)),
            'block': b, 'n': n, 'n_boot': int(n_boot),
            'r2_point': 1 - float(np.sum(r**2)) / float(np.sum((y-y.mean())**2))}


def _window_dispersion_stats(detail, pooled, n_eff):
    """[Fix 72] Pure computation behind section [1b] and the trade ticket:
    noise band, per-window flags, vol-regime correlation, weight-stability
    cosine, deterioration trend, worst-window R-squared and tracking error.
    Split out of the print block so the ticket can consume the SAME numbers
    the diagnostics print — no chance of the two drifting apart."""
    out = {'band': None, 'flags': [], 'reg_corr': np.nan, 'min_sim': None,
           'trend': False, 'worst_r2': np.nan, 'worst_te': np.nan}
    if detail is None or not len(detail):
        return out
    out['worst_r2'] = float(detail['r2'].min())
    te_w = detail['tgt_vol'] * (1.0 - detail['vol_red'])
    out['worst_te'] = float(te_w.max())
    out['flags'] = ['negative' if q < 0 else '' for q in detail['r2']]
    # No Fisher-z confidence band: predictive R² need not equal correlation².
    if detail['tgt_vol'].nunique() > 1 and detail['r2'].nunique() > 1:
        out['reg_corr'] = float(np.corrcoef(detail['tgt_vol'],
                                            detail['r2'])[0, 1])
    if len(detail) >= 2:
        names = sorted(set().union(*[set(w.index)
                                     for w in detail['weights']]))
        W = np.array([w.reindex(names).fillna(0.0).values
                      for w in detail['weights']])
        sims = []
        for a in range(len(W)):
            for b in range(a + 1, len(W)):
                na, nb = np.linalg.norm(W[a]), np.linalg.norm(W[b])
                if na > 1e-12 and nb > 1e-12:
                    sims.append(float(W[a].dot(W[b]) / (na * nb)))
        if sims:
            out['min_sim'] = min(sims)
    if len(detail) >= 3:
        tr = float(np.corrcoef(detail['window'], detail['r2'])[0, 1])
        out['trend'] = bool(tr > 0.7 and detail.loc[
            detail['window'] == 1, 'r2'].iloc[0] == detail['r2'].min())
    return out


def _tracking_ticket_verdict(quality, worst_r2, overfit_gap, min_sim, trend,
                    ref_pca, ref_simple, roll_breach):
    """[Fix 72] One consolidated go / reduce / no-go verdict for the ticket.

    Gates (heuristics, deliberately conservative — override them with
    judgment, not by re-running until the box says yes):
      ✗  pooled OOS R2 < 0.20 (vol cut under ~11%; costs likely eat it), OR
         in-sample-vs-OOS gap >= 0.35 (clear overfit), OR any window with
         NEGATIVE OOS R2 (tracking error worse than the target mean), OR
         no OOS evidence. Negative R2 alone does not prove volatility rose.
      △  pooled R2 < 0.45, worst window < 0.15, gap >= 0.15, basket turnover
         across windows (min weight cosine <= 0.5), R2 deteriorating into
         the present, live rolling TE already past the kill-switch, or a
         single instrument matching the basket OOS.
      ✓  none of the above.
    Returns (grade, [reasons])."""
    if quality is None or np.isnan(quality):
        return ('? INSUFFICIENT OOS EVIDENCE',
                ['no valid unseen windows — read every number here as '
                 'in-sample'])
    reasons, fail, warn = [], False, False
    if quality < 0.20:
        fail = True
        reasons.append(f'pooled OOS R² {quality:.2f} is below the chosen 0.20 tracking threshold')
    if not np.isnan(overfit_gap) and overfit_gap >= 0.35:
        fail = True
        reasons.append(f'in-sample vs OOS gap {overfit_gap:.2f} ≥ 0.35 — '
                       f'clearly overfit')
    if not np.isnan(worst_r2) and worst_r2 < 0.0:
        fail = True
        reasons.append(f'worst window OOS R² {worst_r2:.2f} < 0 — the hedge '
                       f'tracked returns worse than that window’s mean; '
                       f'check volatility reduction separately')
    if roll_breach:
        warn = True
        reasons.append('latest rolling TE is already above the kill level — '
                       'do not add risk on this hedge today')
    if not fail:
        if quality < 0.45:
            warn = True
            reasons.append(f'pooled OOS R² {quality:.2f} is moderate')
        if not np.isnan(worst_r2) and worst_r2 < 0.15:
            warn = True
            reasons.append(f'worst window OOS R² {worst_r2:.2f} — size off '
                           f'that window, not the average')
        if not np.isnan(overfit_gap) and overfit_gap >= 0.15:
            warn = True
            reasons.append(f'in-sample vs OOS gap {overfit_gap:.2f} — some '
                           f'overfitting')
        if min_sim is not None and min_sim <= 0.5:
            warn = True
            reasons.append(f'windows fitted materially different baskets '
                           f'(min weight cosine {min_sim:+.2f})')
        if trend:
            warn = True
            reasons.append('R² deteriorates toward the LATEST window — '
                           'trust the newest reading, not the mean')
    if (not np.isnan(ref_pca) and not np.isnan(ref_simple)
            and ref_simple >= ref_pca):
        reasons.append('a single-instrument reference matches the basket OOS; '
                       'the primary choice remains the basket (see [2])')
    grade = ('✗ DO NOT TRADE AS-IS' if fail
             else ('△ TRADE AT REDUCED SIZE' if warn else '✓ TRADE'))
    if not reasons:
        reasons.append('all gates passed — OOS strong, worst window fine, '
                       'no overfit, stable basket')
    return grade, reasons


def _ticket_verdict(quality, worst_r2, overfit_gap, min_sim, trend,
                    ref_pca, ref_simple, roll_breach, vol_red=None,
                    worst_vol_red=None, objective='variance',
                    ref_vol_pca=None, ref_vol_simple=None):
    """Judge a hedge by its selected mandate, keeping R2 visible as a diagnostic."""
    if objective == 'tracking':
        return _tracking_ticket_verdict(quality, worst_r2, overfit_gap, min_sim,
                                       trend, ref_pca, ref_simple, roll_breach)
    if vol_red is None or not np.isfinite(vol_red):
        return '? INSUFFICIENT OOS EVIDENCE', ['no valid unseen volatility comparison']
    if vol_red <= 0:
        return '✗ NO VALIDATED RISK REDUCTION', [
            f'unseen coefficient-only spread volatility reduction {vol_red*100:.1f}% '
            'versus the unhedged target; no improvement before costs']
    reasons = [f'unseen coefficient-only spread reduced volatility {vol_red*100:.1f}% '
               'before costs']
    cautions = []
    if quality is not None and np.isfinite(quality) and quality < 0:
        cautions.append(f'pooled return-tracking R² {quality:.2f} is negative; '
                        'inspect directional drift although volatility fell')
    if np.isfinite(worst_r2) and worst_r2 < 0:
        cautions.append('negative tracking R² in at least one window; '
                        'this is a tracking caution, not an automatic risk-reduction failure')
    if worst_vol_red is not None and np.isfinite(worst_vol_red) and worst_vol_red < 0:
        cautions.append(f'worst unseen window volatility reduction '
                        f'{worst_vol_red*100:.1f}%; the hedge increased risk in that window')
    if np.isfinite(overfit_gap) and overfit_gap >= .35:
        cautions.append('large training-versus-unseen tracking gap; review fit stability')
    if min_sim is not None and np.isfinite(min_sim) and min_sim <= .5:
        cautions.append('basket weights changed materially between windows')
    if trend:
        cautions.append('tracking deteriorated toward the latest window')
    if roll_breach:
        cautions.append('latest rolling tracking error breached the monitoring level')
    if (ref_vol_pca is not None and ref_vol_simple is not None
            and np.isfinite(ref_vol_pca) and np.isfinite(ref_vol_simple)
            and ref_vol_simple >= ref_vol_pca):
        reasons.append('a single-instrument reference matched basket volatility '
                       'reduction on the same unseen windows; the basket remains primary')
    reasons.extend(cautions)
    return ('△ RISK REDUCTION WITH CAUTIONS' if cautions
            else '✓ RISK REDUCTION SUPPORTED'), reasons


def _rank_scores(loadings, returns, target, universe):
    """[Fix 10] z-score eucl / cos / corr before combining into rank_score
    (lower = better hedge candidate).

    [Fix 68] rank on |corr| and |cos|, with the loading distance folded over
    the sign (min of the distance to +v and to -v). Ridge assigns negative
    weights happily and the recipe prints LONG legs, yet the old score sent
    a perfectly ANTI-correlated candidate to the bottom of the ranking
    (corr entered signed with weight -2, so corr=-0.9 read as the worst
    possible evidence) while the single-instrument benchmarks pick by
    |corr| — the basket was denied instruments the benchmarks were allowed.
    The returned 'corr' column stays SIGNED so direction is visible."""
    tgt_load = loadings.loc[target].values
    tgt_norm = np.linalg.norm(tgt_load)
    raw = {}
    for tk in universe:
        if tk not in loadings.index:
            continue
        v = loadings.loc[tk].values
        # [Fix 68] fold the sign: an anti-correlated name sits near -v
        eucl = min(np.linalg.norm(tgt_load - v), np.linalg.norm(tgt_load + v))
        cos = abs(float(np.dot(tgt_load, v) /
                        (tgt_norm * np.linalg.norm(v) + 1e-10)))
        corr = returns[target].corr(returns[tk])
        raw[tk] = {'eucl': eucl, 'cos': cos, 'corr': 0.0 if pd.isna(corr) else corr}
    if not raw:
        return pd.DataFrame(columns=['eucl', 'cos', 'corr', 'rank_score'])
    df = pd.DataFrame(raw).T
    zin = df.assign(corr=df['corr'].abs())        # [Fix 68] rank on |corr|
    z = (zin - zin.mean()) / zin.std(ddof=0).replace(0, 1.0)
    # [Fix 24] realized correlation is the most direct evidence of hedging
    # power — give it double weight so the two (noisier) loading-space
    # metrics cannot outvote it
    df['rank_score'] = z['eucl'] - z['cos'] - 2.0 * z['corr']
    return df.sort_values('rank_score')


def _mask_stale(prices, max_flat_days=7, observed=None):
    """Bound forward fills by observation age, never by unchanged price value.

    A real quote at the same price is still an observation. `observed` is the
    raw price frame before forward filling. Mask only once the count of absent
    observations exceeds the limit, using information available on each date.
    The caller separately masks the return on resumption so an entire missing
    interval cannot be labelled as a one-day move. Earlier dates are never
    reclassified using a later quote.
    Bloomberg-filled legacy caches cannot identify inactive days: re-download
    with this revision for ACTIVE_DAYS_ONLY observation provenance.
    """
    if max_flat_days is None:
        return prices.copy()
    limit = int(max_flat_days)
    if limit < 1:
        raise ValueError('mask_stale_days must be a positive integer or None')
    raw = prices if observed is None else observed.reindex_like(prices)
    out, affected = prices.copy(), 0
    for column in out.columns:
        valid = raw[column].notna()
        groups = valid.cumsum()
        absent_age = (~valid).groupby(groups).cumsum()
        bad = (~valid) & (absent_age > limit)
        if bad.any():
            out[column] = out[column].mask(bad)
            affected += 1
    if affected:
        print(f'  Observation guard: bounded missing-price fills '
              f'in {affected} names; reported unchanged prices retained')
    return out


def _fit_basket(returns, target, basket):
    """[Fix 11/59] RidgeCV handles the highly collinear baskets this method
    produces. Returns (model, in-sample R², residuals).

    [Fix 59] The regressors are vol-standardized before the fit. RidgeCV
    applies ONE penalty to all coefficients, so on raw returns a 45-vol small
    cap and an 11-vol index ETF face very different EFFECTIVE shrinkage and
    the penalty quietly tilts baskets toward high-vol names. Scaling each
    column by its own standard deviation equalizes the penalty; dividing the
    fitted coefficients by the same scale afterwards gives an EXACTLY
    equivalent model in raw-return space, so .predict / .score and every
    downstream call site (weights, gross, per-$100 sizing) are unchanged in
    meaning — only the shrinkage is fairer."""
    X = returns[basket].values
    y = returns[target].values
    sd = X.std(axis=0)
    sd[sd < 1e-12] = 1.0                  # constant column → no rescaling
    reg = RidgeCV(alphas=RIDGE_ALPHAS).fit(X / sd, y)
    reg.coef_ = reg.coef_ / sd            # map back to raw-return space
    raw_r2 = float(reg.score(X, y))
    if not np.isfinite(raw_r2) or raw_r2 < -1e-8:
        raise RuntimeError(f'Unexpected raw fitted R²={raw_r2}: check return '
                           'alignment, finite inputs and coefficient scaling')
    return reg, raw_r2, y - reg.predict(X)



class _SingleRidgeFit:
    """A one-feature ridge fit with the prediction interface used by the engine."""
    def __init__(self, coef, intercept, alpha):
        self.coef_ = np.array([float(coef)])
        self.intercept_ = float(intercept)
        self.alpha_ = float(alpha)

    def predict(self, X):
        return np.asarray(X, dtype=float) @ self.coef_ + self.intercept_

    def score(self, X, y):
        from sklearn.metrics import r2_score
        return float(r2_score(y, self.predict(X)))


def _fit_single_candidates(returns, target, candidates):
    """Exact single-feature RidgeCV LOOCV, batched across all candidates.

    Centering includes an unpenalized intercept. H_ii = 1/n + z_i²/(n+alpha)
    for each unit-variance feature, and the leave-one-out error is e_i/(1-H_ii).
    All alpha choices use training data only, matching _fit_basket's RidgeCV.
    """
    if not candidates:
        return {}
    X = returns[candidates].to_numpy(dtype=float)
    y = returns[target].to_numpy(dtype=float)
    n = len(y)
    mean, sd = X.mean(axis=0), X.std(axis=0)
    sd = np.where(sd < 1e-12, 1.0, sd)
    Z = (X - mean) / sd
    yc = y - y.mean()
    norm = np.sum(Z * Z, axis=0)
    dot = Z.T @ yc
    errors = []
    for alpha in RIDGE_ALPHAS:
        beta = dot / (norm + alpha)
        denom = 1 - 1/n - Z**2 / (norm + alpha)
        loo = (yc[:, None] - Z * beta) / denom
        errors.append(np.mean(loo * loo, axis=0))
    best = np.argmin(np.asarray(errors), axis=0)
    alpha = RIDGE_ALPHAS[best]
    coef = dot / (norm + alpha) / sd
    fits = {}
    sst = float(yc @ yc)
    for j, ticker in enumerate(candidates):
        model = _SingleRidgeFit(coef[j], y.mean() - mean[j]*coef[j], alpha[j])
        resid = y - model.predict(X[:, j:j+1])
        raw = 1 - float(resid @ resid) / sst
        fits[ticker] = (model, raw, resid)
    return fits

def _n_pc_auto(ret_scaled, cap, robust_cov='none'):
    """[Fix 22] Heuristic PC count using the Marchenko-Pastur ideal-noise upper edge.

    [Fix 73] the count is now ALWAYS taken on the raw sample spectrum. The
    MP edge describes the bulk of SAMPLE eigenvalues under a pure-noise
    null; Ledoit-Wolf shrinkage pulls large sample eigenvalues toward the
    grand mean, so the old [Fix 42] branch — shrunk eigenvalues against the
    unshrunk edge — systematically UNDER-counted factors, and
    robust_cov='ledoit' silently ran with fewer PCs than the same data under
    'none'. Isotropic shrinkage changes eigenvalues, not eigenvectors, so
    it changes loading-space weighting; the eigenvalue COUNT is a
    heuristic that belongs on the raw spectrum, not a formal significance test
    for dependent or heavy-tailed financial returns. `robust_cov` is kept
    in the signature so call sites are unchanged."""
    n, p = ret_scaled.shape
    X = np.asarray(ret_scaled, dtype=float)
    X = X - X.mean(axis=0)
    gram = X @ X.T if p > n else X.T @ X
    ev = np.linalg.eigvalsh(gram) / (n - 1)
    mp_edge = (1.0 + np.sqrt(p / n)) ** 2
    k = int(np.sum(ev > mp_edge))
    return int(min(max(2, k), cap, 15, n - 1, p))


def _download_hedge_data_impl(target, candidates=None, session=None,
                        years=3, min_mktcap_usd_mm=5000, exclude=None,
                        force_include=None, fetch_mktcap_hist=True,
                        fetch_pit_members=True, cache=True):
    """[Fix 31] CELL A for Jupyter: universe discovery + the single Bloomberg
    download. Run once; feed the returned dict to find_best_hedge(..., data=...).
    [Fix 35] Stores current USD market caps so the cap floor can be retuned with
    no API calls (min_mktcap_usd_mm in USD MILLIONS; 5000 = $5bn).
    [Fix 36] `exclude` drops names before download. [Fix 40] `force_include`
    guarantees names are downloaded so they can be forced into every basket.
    [Fix 44] Also fetches HISTORICAL market-cap PATHS (approx-USD) so the size
    filter can be applied point-in-time (as-of each window) instead of with
    today's cap. Set fetch_mktcap_hist=False to skip that extra download.
    [Fix 46] `target` may be a single ticker, an equal-weight list, or a
    weighted dict {'AAPL US Equity': 0.6, '700 HK': 0.4} (a whole book). For a
    book the universe is the UNION of each leg's universe, every leg is removed
    from the candidate pool, and all legs are downloaded."""
    session = session or get_session()
    legs, pf_w, is_portfolio, label = _coerce_targets(target)      # [Fix 46]
    leg_shorts = {l.split(' ')[0] for l in legs}
    disc_meta = []                                                 # [Fix 49]

    if candidates is None:
        if is_portfolio:
            print(f"  Portfolio target {label}: discovering the union of "
                  f"{len(legs)} legs' universes...")
            uni, disc_meta = [], []
            for leg in legs:
                m = {}
                uni += auto_discover_universe(
                    session, leg, min_mktcap_usd_mm=min_mktcap_usd_mm, meta=m)
                disc_meta.append(m)
            seen, candidates = set(), []
            for c in uni:                       # dedupe; never a leg's own name
                s = c.split(' ')[0]
                if s in leg_shorts or s in seen:
                    continue
                candidates.append(c)
                seen.add(s)
        else:
            m = {}
            candidates = auto_discover_universe(
                session, legs[0], min_mktcap_usd_mm=min_mktcap_usd_mm, meta=m)
            disc_meta = [m]

    candidates, removed = _apply_exclusions(candidates, exclude)   # [Fix 36]
    if removed:
        print(f"  Manual exclusions: dropped {len(removed)} names before "
              f"download ({', '.join(t.split(' ')[0] for t in removed[:12])}"
              f"{', ...' if len(removed) > 12 else ''})")
    for f in (force_include or []):                               # [Fix 40]
        tk = _fmt_bbg_ticker(str(f))
        if tk is None:
            print(f"  ⚠ force_include entry '{f}' has no exchange code — "
                  f"cannot download it; pass e.g. '0050 TT'")
            continue
        if tk in removed:
            print(f"  ⚠ {tk} is in both exclude= and force_include= — "
                  f"force_include wins, keeping it")
        if tk not in candidates and tk not in legs:
            candidates.append(tk)

    seen, dedup = set(leg_shorts), []            # dedupe, exclude every leg
    for c in candidates:
        s = c.split(' ')[0]
        if s not in seen:
            dedup.append(c)
            seen.add(s)

    end_dt = datetime.now().strftime('%Y%m%d')
    start_dt = (datetime.now() - timedelta(days=int(years * 365))).strftime('%Y%m%d')
    # [Fix 49] point-in-time index membership — graceful: {} when the field
    # is unavailable for this index (then everything behaves exactly as before)
    pit_members, non_index_shorts = {}, set()
    if fetch_pit_members and disc_meta:
        for m in disc_meta:
            non_index_shorts |= m.get('non_index_shorts', set())
        pit_members = _pit_index_membership(
            session, [m.get('index_ticker') for m in disc_meta],
            start_dt, end_dt)
        if pit_members:
            ever = set().union(*pit_members.values())
            known = {c.split(' ')[0] for c in dedup} | leg_shorts
            extra = sorted(t for t in ever if t.split(' ')[0] not in known)
            extra, _ = _apply_exclusions(extra, exclude)
            if extra:
                print(f"  [Fix 49] adding {len(extra)} PAST index members "
                      f"missing from today's universe (delisted / dropped "
                      f"names — survivorship fix)")
                dedup += extra
            print(f"  ✓ point-in-time membership: {len(pit_members)} "
                  f"snapshots, {len(ever)} names ever members")
    elif fetch_pit_members:
        print("  (candidates were user-supplied — no index discovered, "
              "point-in-time membership skipped)")

    all_tickers = legs + dedup                                    # [Fix 46]
    print(f"Downloading {len(all_tickers)} tickers ({start_dt} → {end_dt})...")
    prices = bbg_hist(session, all_tickers, start_dt, end_dt)
    present_legs = [l for l in legs if l in prices.columns]
    if is_portfolio:
        if len(present_legs) < 2:
            raise ValueError(
                f"Only {len(present_legs)} of {len(legs)} portfolio legs "
                f"returned prices — check the tickers ({legs})")
        if len(present_legs) < len(legs):
            print(f"  ⚠ portfolio legs with no price data: "
                  f"{[l for l in legs if l not in present_legs]}")
    elif legs[0] not in prices.columns:
        raise ValueError(f"No price data for {legs[0]} — check the ticker spelling")
    print(f"  ✓ {prices.shape[0]} price rows × {prices.shape[1]} tickers")

    # [Fix 35] current USD market caps (fail-open)
    mktcap = {}
    try:
        liq = bbg_ref_multi(session, list(prices.columns),
                            ['CRNCY_ADJ_MKT_CAP'],
                            overrides={'EQY_FUND_CRNCY': 'USD'})
        for tk, d_ in liq.items():
            try:
                mktcap[tk] = float(d_.get('CRNCY_ADJ_MKT_CAP'))
            except (TypeError, ValueError):
                continue
        print(f"  ✓ USD market caps stored for {len(mktcap)} tickers")
    except Exception as e:
        print(f"  ⚠ market-cap download skipped ({e}) — the cap filter will "
              f"be unavailable in find_best_hedge")

    # [Fix 44] historical market-cap PATHS (local ccy from Bloomberg), rescaled
    # to approx-USD by matching each name's latest point to its current USD cap.
    mktcap_hist = pd.DataFrame()
    if fetch_mktcap_hist:
        try:
            hist_local = bbg_hist_field(session, list(prices.columns),
                                        'CUR_MKT_CAP', start_dt, end_dt)
            scaled = {}
            for c in hist_local.columns:
                s = hist_local[c].dropna()
                if s.empty:
                    continue
                cur_usd = mktcap.get(c)
                last_local = float(s.iloc[-1])
                if cur_usd and last_local:
                    scaled[c] = hist_local[c] * (cur_usd / last_local)   # ≈ USD
                else:
                    scaled[c] = hist_local[c]        # fail-open: local ccy path
            mktcap_hist = pd.DataFrame(scaled)
            print(f"  ✓ point-in-time market-cap paths for "
                  f"{mktcap_hist.shape[1]} tickers")
        except Exception as e:
            print(f"  ⚠ historical market-cap download skipped ({e}) — the size "
                  f"filter will fall back to today's caps (look-ahead)")

    # [Fix 119] carry the exposure verdict with the data. Merged across legs so
    # a book reports the union of what its legs need.
    _exp = {'tags': set(), 'resolved': {}, 'unresolved': {}}
    for _m in disc_meta:
        _exp['tags'].update(_m.get('exposure_tags') or [])
        _exp['resolved'].update(_m.get('exposures_resolved') or {})
        _exp['unresolved'].update(_m.get('exposures_unresolved') or {})
    _exp['tags'] = sorted(_exp['tags'])

    out = {'target': target, 'target_label': label,
           'portfolio': {'legs': legs, 'weights': pf_w,
                         'is_portfolio': is_portfolio, 'label': label},
           'peer_tickers_by_target': {m['target']: m['peer_tickers'] for m in disc_meta},
           'broad_markets': [m['broad_market'] for m in disc_meta],
           'prices': prices, 'price_observations': 'ACTIVE_DAYS_ONLY',
           'mktcap_usd_mm': mktcap,
           'mktcap_hist': mktcap_hist,
           'pit_members': pit_members,                        # [Fix 49]
           'non_index_shorts': sorted(non_index_shorts),
           'exposures': _exp,                                 # [Fix 119]
           'downloaded_at': datetime.now(),                   # [Fix 88]
           'fingerprint': {'legs': sorted(legs), 'years': years,  # [Fix 90]
                           'min_mktcap_usd_mm': min_mktcap_usd_mm,
                           'exclude': sorted(map(str, exclude or [])),
                           'instrument_map': _INSTRUMENT_MAP_HASH,  # [Fix 119]
                           'force_include': sorted(map(str,
                                                       force_include or []))}}
    if cache:                                                 # [Fix 88]
        try:
            save_hedge_data(out)
        except Exception as e:
            print(f"  ⚠ could not cache this download ({e}) — it is still "
                  f"returned in memory")
    return out


from functools import wraps as _wraps


@_wraps(_download_hedge_data_impl)
def download_hedge_data(*args, verbose=False, **kwargs):
    """Same download API; verbose=True exposes the full discovery log."""
    if verbose:
        return _download_hedge_data_impl(*args, **kwargs)
    import io
    from contextlib import redirect_stdout
    print('Discovering candidates and downloading Bloomberg history…')
    capture = io.StringIO()
    with redirect_stdout(capture):
        result = _download_hedge_data_impl(*args, **kwargs)
    result['download_log'] = capture.getvalue()
    warnings = [_clean(line) for line in result['download_log'].splitlines() if '⚠' in line]
    print(f"Downloaded {result['prices'].shape[0]} price rows for {result['prices'].shape[1]} instruments.")
    for warning in warnings[:3]:
        print(warning)
    if len(warnings) > 3:
        print(f'{len(warnings)-3} further data warnings are in the detailed download log.')
    return result


def _adf_pvalue(values, **kwargs):
    """Use the tuple API explicitly where supported, including older statsmodels."""
    import inspect
    if 'result_object' in inspect.signature(adfuller).parameters:
        kwargs['result_object'] = False
    return float(adfuller(values, **kwargs)[1])


def _forward_order(returns, target, universe, forced=(), max_size=7):
    """Greedy partial-correlation selection on training data only.

    Residualize every remaining instrument against the selected set. This
    allows complementary exposures to enter even when marginal correlation
    is weak. All eligible instruments are considered; this is a deterministic
    heuristic rather than an exhaustive search over every subset.
    """
    pool = list(dict.fromkeys(c for c in universe if c != target))
    selected = [c for c in forced if c in pool]
    y = returns[target].to_numpy(dtype=float)
    y = y - y.mean()
    X = returns[pool].to_numpy(dtype=float)
    X = X - X.mean(axis=0)
    for _ in range(max(0, int(max_size) - len(selected))):
        remaining = [c for c in pool if c not in selected]
        if not remaining:
            break
        ids = [pool.index(c) for c in remaining]
        xr, yr = X[:, ids], y
        if selected:
            xs = X[:, [pool.index(c) for c in selected]]
            xr = xr - xs @ np.linalg.lstsq(xs, xr, rcond=None)[0]
            yr = yr - xs @ np.linalg.lstsq(xs, yr, rcond=None)[0]
        denom = np.sum(xr * xr, axis=0)
        gain = np.full(len(remaining), -np.inf)
        usable = denom > MIN_RETURN_STD ** 2 * len(y)
        gain[usable] = (xr[:, usable].T @ yr) ** 2 / denom[usable]
        if not np.isfinite(gain).any():
            break
        selected.append(remaining[int(np.argmax(gain))])
    return selected


def _config_family(spec, size):
    if str(spec).startswith('single:'):
        return 'single_etf' if _is_etf(str(spec)[7:]) else 'single_stock'
    return 'single' if int(size) == 1 else 'basket'


def _family_configs(summary, family, market_tickers=()):
    if family == 'single_market':
        return summary.loc[summary['pc_spec'].isin(['single:' + t for t in market_tickers])]
    kinds = summary['family']
    mask = kinds.str.startswith('single') if family == 'single' else kinds.eq(family)
    return summary.loc[mask]


def _alternative_evidence(weights, raw_r2, ys, residuals, spreads, ann,
                          expected_windows, mode, config, objective):
    """Summarize a family's selection test without selecting on its test results."""
    quality, risk = np.nan, {}
    if ys:
        y, residual = np.concatenate(ys), np.concatenate(residuals)
        denom = float(np.sum((y - y.mean()) ** 2))
        if denom > MIN_RETURN_STD ** 2:
            quality = 1 - float(np.sum(residual ** 2)) / denom
        risk = _trade_risk(y, np.concatenate(spreads), ann)
    complete = bool(expected_windows and len(ys) == expected_windows)
    within_cap = config.get('max_gross') is None or weights.abs().sum() <= config['max_gross']
    if mode == 'IN-SAMPLE':
        status = 'INDICATIVE — fitted history only'
    elif not complete or not np.isfinite(quality):
        status = 'INSUFFICIENT — incomplete unseen evidence'
    elif not within_cap:
        status = 'FAILED — final weights exceed gross cap'
    elif quality < 0:
        status = 'FAILED — negative unseen tracking R²'
    elif risk.get('vol_reduction', 0) <= 0:
        status = 'FAILED — no unseen volatility reduction'
    else:
        status = 'SUPPORTED — historical unseen test'
    return {'weights': weights.copy(), 'in_sample_r2': float(raw_r2),
            'unseen_r2': quality, 'trade_risk': risk,
            'validation_mode': mode, 'n_unseen_windows': len(ys),
            'expected_unseen_windows': expected_windows,
            'status': status, 'qualified': status.startswith('SUPPORTED'),
            'config': config, 'hedge_objective': objective}


def _show_hedge_comparison(alternatives, selected_family, search):
    rows = []
    labels = {'basket': 'Best basket', 'single_stock': 'Best single stock · reference',
              'single_etf': 'Best single ETF · reference'}
    for family, label in labels.items():
        item = alternatives.get(family)
        if item is None:
            rows.append([label, '—', '—', '—', '—', 'Unavailable under these settings'])
            continue
        w = item['weights']
        recipe = '; '.join(f'{"SHORT" if x > 0 else "LONG"} ${abs(x)*100:.1f} {tk}'
                           for tk, x in w.items())
        risk = item['trade_risk']
        q = item['unseen_r2']
        rows.append([label + (' · selected' if family == selected_family else ''),
                     recipe, f"{item['in_sample_r2']:.3f}",
                     f'{q:.3f}' if np.isfinite(q) else '—',
                     f"{risk['vol_reduction']*100:.1f}%" if risk else '—', item['status']])
    _section('BEST BASKET AND SINGLE-INSTRUMENT HEDGES',
             'basket is primary; single instruments are references')
    _print_table(['CANDIDATE', 'HEDGE PER $100 TARGET', 'FITTED R²', 'UNSEEN R²',
                  'UNSEEN VOL CUT', 'EVIDENCE'], rows,
                 note='Winners are selected using training/CV data. Unseen scores test each '
                      'selection procedure, with instruments and weights refitted before each '
                      'test window; they do not backtest today’s fixed weights. Failed candidates '
                      'remain references and are excluded from recommendations. '
                      'Single instruments do not replace the primary basket.')
    _P(f"  Search: {search['single_instruments_scored']} single instruments scored; "
       f"{search['configurations_scored']} configurations scored; "
       'basket methods: ' + ', '.join(search['basket_methods']) + '.')


def _basket_sizes(options, size_range=None):
    """Inclusive hard range; equal bounds request an exact cardinality."""
    if size_range is not None:
        if len(size_range) != 2:
            raise ValueError('basket_size_range must be (minimum, maximum)')
        lo, hi = size_range
        if isinstance(lo, bool) or isinstance(hi, bool) or int(lo) != lo or int(hi) != hi:
            raise ValueError('Basket range bounds must be whole numbers')
        if not 2 <= int(lo) <= int(hi) <= 50:
            raise ValueError('Basket range must satisfy 2 <= minimum <= maximum <= 50')
        return tuple(range(int(lo), int(hi) + 1))
    values = tuple(options)
    if not values or any(isinstance(k, bool) or int(k) != k or not 1 <= int(k) <= 50 for k in values):
        raise ValueError('basket_size_options must contain whole numbers from 1 to 50')
    return tuple(sorted(set(map(int, values))))


def _filter_candidate_scope(data, legs, columns, scope, include_market, peers=None, forced=None):
    """Filter by verified identity before PCA and every validation window.

    Direct Bloomberg peers and same BICS/GICS industry peers are eligible.
    Second-degree-only names and arbitrary index constituents are not peers.
    Relationships are current discovery metadata, not historical classifications.
    """
    def canonical(t):
        return _fmt_bbg_ticker(str(t).upper().replace(' EQUITY', '')) or str(t)

    broad = [_broad_market_spec(t) for t in legs]
    market_ids = {canonical(t) for m in broad for t in m['instruments']}
    market_tickers = [c for c in columns if canonical(c) in market_ids and c not in legs]
    if scope == 'peers':
        manual_peers = peers is not None
        if peers is None:
            by_target = data.get('peer_tickers_by_target') or {}
            if any(t not in by_target for t in legs):
                raise ValueError('Peers-only needs verified peer metadata for this target. '
                                 'Download again, or enter the peer tickers explicitly for this cache.')
            peers = [p for t in legs for p in by_target[t]]
        ids = {canonical(t) for t in peers}
        if peers:
            resolved, missing = _resolve_force_include(peers, columns, legs[0])
            if missing:
                # Auto discovery can contain peers without licensed price series;
                # a manual peer list must be actionable and fully understood.
                if manual_peers:
                    raise ValueError('Peer tickers are not in the downloaded data: ' + ', '.join(missing))
            ids.update(canonical(t) for t in resolved)
        if include_market:
            ids |= market_ids
        candidates = [c for c in columns if canonical(c) in ids and c not in legs]
    else:
        candidates = [c for c in columns if c not in legs and
                      (include_market or canonical(c) not in market_ids)]
    resolved_forced, _ = _resolve_force_include(forced, columns, legs[0])
    outside = [t for t in resolved_forced if t not in candidates and t not in legs]
    if outside:
        raise ValueError('Required instruments conflict with the candidate filter: '
                         + ', '.join(outside) + '. Change the filter or required instruments.')
    return {'columns': list(dict.fromkeys(list(legs) + candidates)),
            'market_tickers': [c for c in market_tickers if c in candidates],
            'broad_markets': broad, 'candidate_scope': scope,
            'include_broad_market': bool(include_market)}


def _find_best_hedge_impl(
    target_ticker,
    candidates=None,
    data=None,                    # [Fix 31] dict from download_hedge_data()
    session=None,
    lookback_options=(126, 252),
    pc_options='auto',            # 'auto' or a list of ints, e.g. [3, 5, 8]
    basket_size_options=(2, 3, 5, 7),
    cv_test_window=42,
    cv_n_folds=5,
    outer_folds=3,                # [Fix 20] nested outer validation windows
    outer_window=None,            # defaults to cv_test_window
    async_adjust='auto',          # [Fix 5] 'auto' / True / False
    restrict_to_target_tz='auto',  # [Fix 26/33] 'auto' / True / False
    tz_tolerance_hours=3.0,       # [Fix 32/33] closes within this many hours
                                  # of the target's count as synchronous
    min_mktcap_usd_mm=5000,       # [Fix 25/35] market-cap floor, USD MILLIONS
                                  # (5000 = $5bn); now also works with data=
    exclude=None,                 # [Fix 36] securities to filter out, e.g.
                                  # ['002230', '3156 JP Equity']
    force_include=None,           # [Fix 40] securities that MUST be held in
                                  # every basket, in ALL outputs — e.g.
                                  # ['0050 TT'] or ['2317 TT Equity']; they
                                  # bypass the cap floor / tz restriction /
                                  # exclude, and occupy basket slots in every
                                  # CV fold, nested window, and final refit
    recency_weight=0.0,           # [Fix 108] 0 = every CV fold counts equally
                                  # (the pre-v104 behaviour). >0 tilts the
                                  # selection toward RECENT folds: a fold f
                                  # folds back in time gets weight
                                  # exp(-recency_weight * f). 0.35 ≈ the
                                  # newest fold counting ~2x the one two
                                  # folds older. See the [Fix 108] note in
                                  # the selection block before using it.
    gross_penalty=0.02,           # [Fix 38] composite penalty per 1.0x gross
    max_gross=None,               # [Fix 38] e.g. 3.0 → discard configs whose
                                  # avg CV gross exceeds $300 per $100 target
    winsorize_pct=0.01,           # [Fix 42] clip returns at 1%/99% before PCA
                                  # (candidate selection only; 0 = old numbers)
    robust_cov='none',            # [Fix 42] 'ledoit' → shrinkage-covariance PCA
    pit_size=True,                # [Fix 44] apply the size floor point-in-time
                                  # (as-of each window) using historical caps
    pit_members=True,             # [Fix 49] restrict index-sourced candidates
                                  # to names that were ACTUALLY members as-of
                                  # each window (needs pit data; off if absent)
    size_band=None,               # [Fix 45] (lo, hi) → keep candidates whose cap
                                  # is within lo–hi × the target's cap; overrides
                                  # the flat floor when set, e.g. (0.3, 3.0)
    size_override=None,           # [Fix 45] forward-looking cap views, e.g.
                                  # {'XYZ': 'large'} or {'XYZ': 8000} (USD mm)
    mask_stale_days=7,            # maximum age of forward-filled missing quotes
                                  # reported unchanged prices are retained
                                  # None disables the observation-age guard
    notional_mm=None,             # [Fix 72] gross book notional in USD mm —
                                  # dollarizes the trade-ticket amounts
    rolling_oos=True,             # [Fix 71] walk-forward rolling OOS curve
                                  # (section [1c] + chart)
    rolling_refit_every=21,       # [Fix 71] rows between weight refits
    rolling_max_windows=12,       # [Fix 71] refit segments to walk back
    boot_n=2000,                  # [Fix 70] bootstrap draws for the CI on
                                  # pooled OOS R2 / TE; 0 disables
    hedge_horizon_days=None,      # [Fix 91/100] how long you intend to HOLD
                                  # this hedge, in trading days. Scales the
                                  # reported risk to that horizon, reports
                                  # what holds of that length actually
                                  # delivered, and compares the horizon with
                                  # the measured rebalance cadence.
    horizon_sets_windows=False,   # [Fix 100] re-cut the OOS windows to the
                                  # horizon. OFF by default — measured, it
                                  # does not improve realized horizon
                                  # performance and costs evidence. See the
                                  # note at the top of STEP 1.
    sample_window=None,           # [Fix 76] restrict the analysis window:
                                  # '3m' / '90d' / '26w' / '1y' (last N up to
                                  # the end of the data) or an absolute
                                  # (start, end) tuple, e.g. ('2026-07-13',
                                  # '2026-07-28') / ('13-Jul-2026', None).
                                  # Validation auto-adapts — see [Fix 77].
    report='compact',             # [Fix 79] 'compact' (default) or 'full'
                                  # (adds long-form explanations and per-
                                  # config weight tables)
    show_plots=True,
    _rehedge_of=None,             # [Fix 115] set by quick_rehedge so the
                                  # report can say what it inherited and what
                                  # it did not re-validate
    hedge_objective='variance',   # 'variance' (risk reduction) or 'tracking' (strict R2)
    broad_search=True,            # select a basket; score all eligible singles as references
    candidate_scope='all',        # 'all' or verified direct/industry peers
    include_broad_market=None,    # default: on for all, off for peers only
    peer_tickers=None,            # manual peer list for older caches
    basket_size_range=None,       # inclusive (min, max); exact number when equal
    alternative_baskets=5,       # distinct additional recipes to display (1–20)
):
    if (isinstance(alternative_baskets, bool)
            or not isinstance(alternative_baskets, (int, np.integer))
            or not 1 <= alternative_baskets <= 20):
        raise ValueError('alternative_baskets must be an integer from 1 to 20')
    basket_size_options = _basket_sizes(basket_size_options, basket_size_range)
    if candidate_scope not in ('all', 'peers'):
        raise ValueError("candidate_scope must be 'all' or 'peers'")
    if include_broad_market is None:
        include_broad_market = candidate_scope == 'all'
    if hedge_objective not in ('variance', 'tracking'):
        raise ValueError("hedge_objective must be 'variance' or 'tracking'")
    if broad_search and not any(int(size) >= 2 for size in basket_size_options):
        raise ValueError('The primary hedge is a basket. Include a basket size >= 2; '
                         'single stocks and ETFs are evaluated as references. '
                         'Use broad_search=False only for an explicitly pinned configuration.')
    outer_window = outer_window or cv_test_window
    _kv_reset()             # [Fix 114] never inherit a failed run's rows
    transcript_reset()      # [Fix 115] this run's text copy starts empty
    # Holding duration is an optional risk-report input. The default fit
    # minimizes daily (or asynchronous two-day) return risk. With serial
    # dependence, an optimal multi-period hedge can differ; this model does
    # not optimize the covariance of horizon-aggregated returns. Recutting
    # validation windows alone is not such an optimization. The explicit
    # horizon_sets_windows option changes the validation design only and
    # is retained for compatibility; the form uses the ordinary defaults.
    if hedge_horizon_days:
        _h = int(hedge_horizon_days)
        if _h < 1:
            raise ValueError('[Fix 91] hedge_horizon_days must be >= 1')
        if horizon_sets_windows:
            cv_test_window = outer_window = int(np.clip(_h, 10, 63))
            _P(f"  [Fix 100] horizon_sets_windows=True → OOS windows set "
                  f"to {cv_test_window} rows (this also changes the validation design)")
    # [Fix 46] single-name vs portfolio ---------------------------------------
    pf_legs, pf_w, is_portfolio, pf_label = _coerce_targets(target_ticker)
    _uniq = lambda seq: list(dict.fromkeys(seq))
    if is_portfolio:
        target_short = pf_label
        target_keepset = set(pf_legs)
        target_ticker_single = None
    else:
        target_ticker = pf_legs[0]            # canonical full ticker string
        target_ticker_single = target_ticker
        target_short = target_ticker.split(' ')[0]
        target_keepset = {target_ticker}

    _P(f'Engine revision: {PCA_REVISION}')

    # ── STEP 1+2: GET PRICES (pre-downloaded data or fresh download) ─────────
    if data is not None:
        # [Fix 66] The old [Fix 46] check demanded the book EQUAL the book
        # the data was downloaded for — which made quick_rehedge crash the
        # moment a churning book added or dropped a leg, the exact use case
        # it was built for. The real requirement is only that every leg has
        # downloaded prices: legs are excluded from the candidate pool
        # downstream, and ex-legs simply become candidates (legitimate — and
        # often the best hedges for a rebalance book). Universe DISCOVERY
        # ran for the original book, so after a MATERIAL change (new sector
        # or market) re-run CELL A; for leg churn this is exactly right.
        _have = set(data['prices'].columns)
        _missing = [l for l in pf_legs if l not in _have]
        if _missing:
            raise ValueError(
                f"[Fix 66] legs {_missing} are not in the downloaded data — "
                f"re-run download_hedge_data() for this book, or pass them "
                f"via force_include= there so they are fetched")
        if set(_coerce_targets(data.get('target'))[0]) != set(pf_legs):
            _P(f"  [Fix 66] note: data was downloaded for "
                  f"{data.get('target_label', data.get('target'))} — reusing "
                  f"its universe for {target_short}. Fine for leg churn on "
                  f"the same book; re-run CELL A after a material change.")
        prices = data['prices'].copy()
        _P(f"Using data already downloaded: {prices.shape[0]} days of "
              f"prices for {prices.shape[1]} names (nothing fetched)")
    else:
        data = download_hedge_data(target_ticker, candidates=candidates,
                                   session=session or get_session(),
                                   min_mktcap_usd_mm=min_mktcap_usd_mm,
                                   exclude=exclude,
                                   force_include=force_include)  # [Fix 40]
        prices = data['prices'].copy()

    scope = _filter_candidate_scope(data, pf_legs, prices.columns, candidate_scope,
                                    include_broad_market, peer_tickers, force_include)
    prices = prices[scope['columns']]
    market_tickers = scope['market_tickers']

    # [Fix 40] Resolve the must-have securities against the downloaded
    # columns BEFORE any filter runs, so every filter below can exempt them.
    forced, fi_unres = _resolve_force_include(force_include, prices.columns,
                                              target_ticker)
    if fi_unres:
        raise ValueError(f'force_include entries {fi_unres} are not in the downloaded data. '
                         'Re-run download_hedge_data(..., force_include=...) to fetch them; '
                         'required instruments cannot be ignored.')
    if forced:
        _P(f"  Force-include active: {', '.join(forced)} will be held in "
              f"every basket (CV folds, nested windows, and final recipe)")

    primary_sizes = [k for k in basket_size_options if k >= 2]
    if broad_search and forced and not any(k >= len(forced) for k in primary_sizes):
        raise ValueError('The forced instrument count exceeds every requested basket size.')

    # [Fix 36] Manual exclusions on COLUMNS — works on pre-downloaded data
    kept_cols, removed_cols = _apply_exclusions(
        [c for c in prices.columns if c not in target_keepset], exclude)
    readd = [c for c in removed_cols if c in forced]       # [Fix 40]
    if readd:
        _P(f"  ⚠ {', '.join(readd)} in both exclude= and force_include= — "
              f"force_include wins, keeping")
        kept_cols += readd
        removed_cols = [c for c in removed_cols if c not in forced]
    if removed_cols:
        _P(f"  Manual exclusions: dropped {len(removed_cols)} names "
              f"({', '.join(t.split(' ')[0] for t in removed_cols[:12])}"
              f"{', ...' if len(removed_cols) > 12 else ''})")
    if removed_cols or readd:
        prices = prices[_uniq(list(target_keepset) + kept_cols)]

    # [Fix 35] Market-cap floor on COLUMNS — the old code only consumed
    # min_mktcap_usd_mm on the fresh-download path, so with data= the
    # parameter was silently ignored no matter what value was passed.
    caps = data.get('mktcap_usd_mm') or {}
    caps_hist = (data.get('mktcap_hist')
                 if isinstance(data.get('mktcap_hist'), pd.DataFrame)
                 else pd.DataFrame())
    pit_active = bool(pit_size) and not caps_hist.empty        # [Fix 44]
    pm_snaps = (data.get('pit_members') or {}) if pit_members else {}  # [Fix 49]
    pm_dates = sorted(pm_snaps.keys())
    pm_union = set().union(*pm_snaps.values()) if pm_snaps else set()
    pm_exempt = set(data.get('non_index_shorts') or [])
    pm_active = bool(pm_snaps)
    if pm_active:
        _P(f"  [Fix 49] point-in-time index membership active — "
              f"{len(pm_dates)} snapshots, {len(pm_union)} names ever members")
    if min_mktcap_usd_mm and not pit_active:
        # static (current-cap) floor on COLUMNS — used only when point-in-time
        # caps are unavailable or pit_size=False. NOTE: this legacy path carries
        # the "big now / small then" look-ahead that [Fix 44] removes.
        if not caps:
            _P("  ⚠ market-cap floor requested but data has no "
                  "'mktcap_usd_mm' — re-run download_hedge_data() to enable it")
        else:
            kept, dropped, unknown = list(target_keepset), 0, 0
            for c in prices.columns:
                if c in target_keepset:
                    continue
                if _is_etf(c) or c in forced:
                    kept.append(c)
                    continue
                mc = caps.get(c)
                if mc is None:
                    unknown += 1
                    kept.append(c)       # unknown → keep (fail-open)
                    continue
                if mc >= min_mktcap_usd_mm:
                    kept.append(c)
                else:
                    dropped += 1
            if dropped:
                _P(f"  Market-cap floor {_fmt_mktcap(min_mktcap_usd_mm)}: "
                      f"dropped {dropped} names"
                      + (f" ({unknown} unknown caps kept)" if unknown else ""))
                prices = prices[_uniq(kept)]
    elif pit_active:
        _P(f"  the {_fmt_mktcap(min_mktcap_usd_mm)} size floor is applied "
              f"using what each name was worth AT THE TIME, not what it is "
              f"worth today — so a name that grew into the filter cannot "
              f"flatter the backtest")

    prices = prices.apply(pd.to_numeric, errors='coerce').sort_index()
    if prices.index.has_duplicates:
        raise ValueError('Price dates are duplicated; repair the input data before modelling')
    prices = prices.where(np.isfinite(prices) & (prices > 0))
    if (data or {}).get('price_observations') == 'ACTIVE_DAYS_ONLY':
        if len({_exch_of(c) for c in pf_legs}) == 1:
            exchange = _exch_of(pf_legs[0])
            peers = [c for c in prices.columns
                     if c not in target_keepset and _exch_of(c) == exchange]
            if len(peers) >= 2:
                closed = prices[pf_legs + peers].isna().all(axis=1)
                if closed.any():
                    _P(f'  Removed {int(closed.sum())} shared exchange-closure rows')
                    prices = prices.loc[~closed]
    else:
        _P('  Legacy/supplied price data: reported flat prices are retained. '
           'Bloomberg-filled inactive days cannot be distinguished from real '
           'quotes; re-download once for active-day provenance.')
    observed_prices = prices.copy()
    prices = prices.ffill()
    if mask_stale_days:
        prices = _mask_stale(prices, mask_stale_days, observed=observed_prices)
    if sample_window is not None:                           # [Fix 76]
        _sw0, _sw1 = _parse_sample_window(sample_window, prices.index)
        _avail = (prices.index[0], prices.index[-1])
        prices = prices.loc[_sw0:_sw1]
        if len(prices) < 10:
            raise ValueError(
                f"[Fix 76] sample window {_sw0:%Y-%m-%d} → {_sw1:%Y-%m-%d} "
                f"leaves {len(prices)} sessions (data spans "
                f"{_avail[0]:%Y-%m-%d} → {_avail[1]:%Y-%m-%d}) — need ≥ 10")
        _P(f"  [Fix 76] sample window: {prices.index[0]:%Y-%m-%d} → "
              f"{prices.index[-1]:%Y-%m-%d} ({len(prices)} sessions)")
    # Per-fit eligibility is determined on training rows. Remove only columns
    # with no usable observations anywhere; a later gap cannot exclude an
    # otherwise valid instrument from an earlier historical fit.
    prices = prices.dropna(axis=1, how='all')
    if is_portfolio:                             # [Fix 46]
        _pl = [c for c in pf_legs if c in prices.columns]
        if len(_pl) < 2:
            raise ValueError(
                f"Fewer than 2 portfolio legs have any valid price observations "
                f"({pf_legs}) — cannot build the book")
    elif target_ticker not in prices.columns:    # [Fix 21]
        raise ValueError(
            f"{target_ticker} has no valid price data in the window — "
            "history too short for this configuration")
    # [Fix 40] a forced name with <85% history cannot be modelled — say so
    # loudly instead of silently forcing NaNs into every window
    lost = [c for c in forced if c not in prices.columns]
    if lost:
        raise ValueError(f'force_include instruments {lost} have no valid price history '
                         'in this window; required instruments cannot be dropped.')

    # [Fix 26/31/32/33] Timezone restriction by CLOSING-TIME GAP, applied to
    # COLUMNS so one global download supports both restricted and
    # unrestricted runs. Two listings count as synchronous when their cash
    # closes are within tz_tolerance_hours of each other (circular clock
    # distance). The old AMER/EMEA/APAC buckets meant restrict=True could
    # never separate e.g. Taipei from Mumbai (both 'APAC', closes 4.5h
    # apart), and unmapped exchanges ('AT' etc.) fell into 'OTHER'.
    # Note: with the default 'auto', restriction already fires whenever the
    # target's own close-time group has >= 30 candidates — so passing True
    # explicitly only changes anything when that group is small.
    if is_portfolio:                             # [Fix 46] book close = legs' if synchronous
        _lc = [_close_utc_of(c) for c in pf_legs]
        if all(x is not None for x in _lc) and (
                max((_close_gap_hours(a, b) for i, a in enumerate(_lc)
                     for b in _lc[i + 1:]), default=0.0) <= tz_tolerance_hours):
            tgt_close = float(np.mean(_lc))
        else:
            tgt_close = None                     # spans tz / unknown → conservative
    else:
        tgt_close = _close_utc_of(target_ticker)
    others = [c for c in prices.columns if c not in target_keepset]
    if tgt_close is None:
        _P(f"  ⚠ unknown exchange close for {target_ticker} — timezone "
              f"restriction unavailable; universe treated as cross-timezone")
        same_tz, do_restrict = [], False
    else:
        same_tz = [c for c in others
                   if _close_utc_of(c) is not None
                   and _close_gap_hours(_close_utc_of(c), tgt_close)
                   <= tz_tolerance_hours]
        do_restrict = (restrict_to_target_tz is True or
                       (restrict_to_target_tz == 'auto' and len(same_tz) >= 30))
    if do_restrict and len(same_tz) < len(others):
        # [Fix 40] forced names survive the restriction; if a forced name is
        # cross-timezone the async detection below flips to 2-day returns
        keep_tz = same_tz + [c for c in list(forced) + pf_legs
                             if c not in same_tz]   # [Fix 46] legs kept
        _P(f"  Restricting universe to closes within "
              f"{tz_tolerance_hours:.1f}h of the target's "
              f"({len(others)} → {len(keep_tz)} candidates"
              + (f"; {len(keep_tz) - len(same_tz)} kept by force_include"
                 if len(keep_tz) > len(same_tz) else "")
              + "; set restrict_to_target_tz=False to keep global names)")
        prices = prices[_uniq(list(target_keepset) + keep_tz)]
    elif restrict_to_target_tz is True and len(same_tz) == len(others):
        _P(f"  All candidates already close within "
              f"{tz_tolerance_hours:.1f}h of the target — nothing to drop")

    # ── Cross-timezone detection → 2-day overlapping returns [Fix 5/34] ─────
    # Trigger when any retained pair of closes is further apart than the
    # tolerance, or when any exchange close is unknown (conservative). The
    # old check compared bucket labels and EXCLUDED unknown ('OTHER')
    # exchanges, so a genuinely async pair could pass undetected.
    closes = [_close_utc_of(c) for c in prices.columns]
    known = sorted({c for c in closes if c is not None})
    has_unknown = any(c is None for c in closes)
    max_gap = max((_close_gap_hours(a, b)
                   for i, a in enumerate(known) for b in known[i + 1:]),
                  default=0.0)
    if async_adjust == 'auto':
        two_day = has_unknown or max_gap > tz_tolerance_hours
    else:
        two_day = bool(async_adjust)
    ann_sqrt = np.sqrt(252 / (2 if two_day else 1))
    if two_day:
        reason = ("unknown exchange close present"
                  if has_unknown and max_gap <= tz_tolerance_hours
                  else f"max close gap {max_gap:.1f}h > "
                       f"{tz_tolerance_hours:.1f}h tolerance")
        _P(f"  ⚠ Universe treated as cross-timezone ({reason}) → "
              f"switching to 2-day overlapping returns to correct "
              f"async-trading bias")

    rets = np.log(prices / prices.shift(1))
    raw_observed = observed_prices.reindex_like(prices).notna()
    resumed = raw_observed & ~raw_observed.shift(1, fill_value=True)
    # Neither a missing quote nor its multi-session resumption is a measured
    # daily return. Keep both unavailable instead of inventing a zero return.
    rets = rets.mask(~raw_observed | resumed)
    rets = rets.replace([np.inf, -np.inf], np.nan)
    if is_portfolio:                             # [Fix 46] synthetic book return
        legs_present = [c for c in pf_legs if c in rets.columns]
        if len(legs_present) < 2:
            raise ValueError(f"Only {len(legs_present)} portfolio legs survived "
                             f"filtering — cannot build the book ({pf_legs})")
        if len(legs_present) < len(pf_legs):
            miss = [c for c in pf_legs if c not in legs_present]
            _P(f"  ⚠ portfolio legs dropped by filtering: {miss} — weights "
                  f"renormalized over the {len(legs_present)} remaining legs")
        _wser = pd.Series([pf_w[c] for c in legs_present], index=legs_present)
        _wser = _wser / (_wser.abs().sum() or 1.0)
        rets[PORTFOLIO_COL] = rets[legs_present].mul(_wser, axis=1).sum(
            axis=1, skipna=False)
    if two_day:
        rets = rets.rolling(2).sum()
    rets = rets.iloc[2 if two_day else 1:]      # drop the leading NaN rows
    if is_portfolio:                             # [Fix 46] from here, hedge the book
        target_ticker = PORTFOLIO_COL

    # [Fix 39] Overlapping 2-day returns make ADJACENT rows share one daily
    # return, so every train/test boundary below gets a 1-row purge gap —
    # otherwise the last training row leaks half of the first test row and
    # every OOS statistic is slightly optimistic.
    purge = 1 if two_day else 0

    # ── [Fix 77/85] ADAPTIVE VALIDATION TIERS ───────────────────────────────
    # The protocol degrades explicitly rather than hard-failing on short
    # windows; _validation_tier holds the rules ([Fix 85]) so preview_window
    # and the GUI cannot promise a protocol other than the one that runs.
    rows = len(rets)
    _tier = _validation_tier(rows, lookback_options, cv_test_window,
                             cv_n_folds, outer_window, outer_folds, purge,
                             basket_size_options, rolling_refit_every,
                             strict_basket_sizes=basket_size_range is not None)
    val_mode = _tier['mode']
    hold_rows = _tier['hold_rows']
    lookback_options = _tier['lookback_options']
    cv_test_window = _tier['cv_test_window']
    cv_n_folds = _tier['cv_n_folds']
    outer_window = _tier['outer_window']
    outer_folds = _tier['outer_folds']
    min_train_rows = _tier['min_train_rows']
    rolling_refit_every = _tier['rolling_refit_every']
    basket_size_options = _tier['basket_size_options']
    for _note in _tier['notes']:
        _P(_note)

    universe = [c for c in prices.columns
                if c not in set(pf_legs) and c != target_ticker]   # [Fix 46]
    forced = [c for c in forced if c in universe]           # [Fix 40]
    market_tickers = [c for c in market_tickers if c in universe]
    if broad_search and not any(2 <= k <= len(universe) for k in basket_size_options):
        raise ValueError(f'At least two eligible instruments are required. Requested basket sizes {basket_size_options} require more '
                         f'eligible instruments than available ({len(universe)}).')

    # [Fix 44/45] point-in-time eligibility: size floor / size band / overrides
    _sz_over = {}
    for k, v in (size_override or {}).items():
        base = str(k).upper().replace(' EQUITY', '').strip()
        _sz_over[_fmt_bbg_ticker(str(k)) or base] = v
        _sz_over[base] = v
        _sz_over[base.split(' ')[0]] = v

    def _cap_asof(c, asof):
        for key in (c, c.split(' ')[0]):
            if key in _sz_over:
                v = _sz_over[key]
                if isinstance(v, str):
                    return np.inf if v.lower().startswith('l') else 0.0
                return float(v)
        if pit_active and c in caps_hist.columns:
            s = caps_hist[c]
            s = s[s.index <= asof].dropna()
            if len(s):
                return float(s.iloc[-1])
        return caps.get(c)                        # fallback: current USD cap

    def _eligible(asof):
        if not min_mktcap_usd_mm and not size_band and not pm_active:
            return universe
        tgt_cap = None
        if size_band:
            if is_portfolio:
                # [Fix 74] compare candidates to the GROSS-WEIGHTED AVERAGE
                # leg cap, not the SUM of leg caps. For a book of three mega
                # caps the sum (~$8tn for AAPL+NVDA+MSFT) made lo x cap
                # exceed every listed stock, so the band silently kept only
                # ETFs and forced names.
                _num = _den = 0.0
                for _lc in pf_legs:
                    _v = _cap_asof(_lc, asof)
                    _w = abs(pf_w.get(_lc, 0.0))
                    if _v is not None and np.isfinite(_v) and _w > 0:
                        _num += _w * float(_v)
                        _den += _w
                tgt_cap = (_num / _den) if _den > 0 else None
            else:
                tgt_cap = _cap_asof(target_ticker_single, asof)
        out = []
        for c in universe:
            if _is_etf(c) or c in forced:
                out.append(c)
                continue
            if pm_active and c in pm_union \
                    and c.split(' ')[0] not in pm_exempt:      # [Fix 49]
                snap = pm_snaps[pm_dates[0]]
                for dtt in reversed(pm_dates):
                    if dtt <= asof:
                        snap = pm_snaps[dtt]
                        break
                if c not in snap:
                    continue          # not an index member as-of this window
            mc = _cap_asof(c, asof)
            if mc is None:
                out.append(c)                     # fail-open
                continue
            if size_band and tgt_cap:
                lo, hi = size_band
                if lo * tgt_cap <= mc <= hi * tgt_cap:
                    out.append(c)
            elif mc >= (min_mktcap_usd_mm or 0):
                out.append(c)
        return out

    def _inject_synth_loadings(lds):
        """[Fix 46] Give the synthetic book a loading row = weighted sum of its
        legs' loadings (portfolio factor exposure is linear in the legs)."""
        if not is_portfolio:
            return lds
        legs_in = [c for c in pf_legs if c in lds.index]
        if not legs_in:
            raise RuntimeError("no portfolio legs present in this window")
        w = np.array([pf_w[c] for c in legs_in], dtype=float)
        w = w / (np.abs(w).sum() or 1.0)
        lds.loc[PORTFOLIO_COL] = (lds.loc[legs_in].values * w[:, None]).sum(axis=0)
        return lds
    _P(f"  ✓ {len(rets)} days of returns across {len(universe) + 1} names")

    # ── Reusable building blocks ─────────────────────────────────────────────
    def _forced_basket(ranked, ok, bsize):
        """[Fix 40] Assemble a basket that always contains the forced names
        (those usable in this window), topped up with the best-ranked other
        candidates. Requested cardinality is exact; an unavailable or
        conflicting size is skipped rather than enlarged or shrunk."""
        if any(c not in ok for c in forced) or len(forced) > int(bsize):
            return []
        f_ok = list(forced)
        rest = list(dict.fromkeys(t for t in ranked if t not in f_ok and t in ok))
        basket = f_ok + rest[:max(0, int(bsize) - len(f_ok))]
        return basket if len(basket) == int(bsize) else []

    training_diagnostics, training_notices = [], set()
    evaluation_diagnostics, evaluation_notices = [], set()
    training_cache = {}

    def _prepare_training(frame, required_rows):
        clean, problem, omitted = _training_rows(frame, target_ticker, required_rows)
        key = (frame.index[0], frame.index[-1], tuple(omitted))
        if omitted and key not in training_notices:
            training_notices.add(key)
            training_diagnostics.append({'start': frame.index[0], 'end': frame.index[-1],
                'calendar_rows': len(frame), 'retained_rows': len(clean),
                'omitted_dates': omitted, 'accepted': problem is None})
            dates = ', '.join(str(d.date()) for d in omitted[:5])
            _P(f'  Training data {frame.index[0]:%Y-%m-%d} → {frame.index[-1]:%Y-%m-%d}: '
               f'{len(omitted)} non-finite target rows '
               f'{"omitted jointly" if problem is None else "rejected"} ({dates}); '
               f'test dates unchanged')
        return clean, problem

    def _prepare_evaluation(frame, min_rows=2):
        """Use a COMMON observed-target mask, never a basket-specific test mask.

        Missing-target dates cannot be evaluated for any candidate. At least
        90% target coverage is required; missing hedge returns still fail the
        entire candidate fold. Calendar slices are chosen before this mask.
        """
        clean, problem, omitted = _training_rows(frame, target_ticker, min_rows)
        key = (frame.index[0], frame.index[-1], tuple(omitted), min_rows)
        if omitted and key not in evaluation_notices:
            evaluation_notices.add(key)
            evaluation_diagnostics.append({'start': frame.index[0], 'end': frame.index[-1],
                'calendar_rows': len(frame), 'retained_rows': len(clean),
                'omitted_dates': omitted, 'accepted': problem is None})
            dates = ', '.join(str(d.date()) for d in omitted[:5])
            _P(f'  Validation data {frame.index[0]:%Y-%m-%d} → {frame.index[-1]:%Y-%m-%d}: '
               f'{len(omitted)} non-finite target rows '
               f'{"unavailable for EVERY candidate" if problem is None else "window rejected"} '
               f'({dates}); coverage {1-len(omitted)/len(frame):.1%}')
        return (frame if problem else clean), problem

    def _training_context(train_rets, required_rows):
        # All callers slice the immutable rets within this run. Index identity
        # therefore also identifies the data; never share this cache across runs.
        key = (tuple(train_rets.index), tuple(train_rets.columns))
        if key in training_cache:
            ctx = training_cache[key]
            problem = _window_problem(ctx['tr'], target_ticker, required_rows)
            if problem:
                raise RuntimeError(problem)
            return ctx
        clean, problem = _prepare_training(train_rets, required_rows)
        if problem:
            raise RuntimeError(f'Training window {train_rets.index[0]:%Y-%m-%d} '
                               f'→ {train_rets.index[-1]:%Y-%m-%d}: {problem}')
        ok = list(clean.columns[np.isfinite(clean).all() & (clean.std() > MIN_RETURN_STD)])
        tr = clean[ok]
        u = [c for c in _eligible(train_rets.index[-1]) if c in ok]
        corr = tr[u].corrwith(tr[target_ticker])
        rank = pd.DataFrame({'corr': corr, 'rank_score': -corr.abs()}).sort_values('rank_score')
        ctx = {'tr': tr, 'ok': ok, 'u': u, 'corr_rank': rank, 'pca': {},
               'single_fits': None, 'forward': None, 'scaled': None}
        if len(training_cache) >= 16:
            training_cache.pop(next(iter(training_cache)))
        training_cache[key] = ctx
        return ctx

    def _context_pca(ctx, pc_spec):
        if pc_spec in ctx['pca']:
            return ctx['pca'][pc_spec]
        tr = ctx['tr']
        if ctx['scaled'] is None:
            cols = [c for c in tr.columns if c != PORTFOLIO_COL]
            w = _winsorize_returns(tr[cols], winsorize_pct)
            ctx['scaled'] = pd.DataFrame(StandardScaler().fit_transform(w),
                                         index=tr.index, columns=cols)
        scaled = ctx['scaled']
        cap = min(len(scaled.columns) - 1, len(tr) - 1)
        n_pc = (_n_pc_auto(scaled, cap, robust_cov) if pc_spec == 'auto'
                else int(min(int(pc_spec), cap)))
        pca = _pca_fit(scaled, n_pc, robust_cov)
        lds = pd.DataFrame(pca.components_.T * np.sqrt(pca.explained_variance_),
                           index=scaled.columns,
                           columns=[f'PC{i+1}' for i in range(n_pc)])
        lds = _inject_synth_loadings(lds)
        rank = _rank_scores(lds, tr, target_ticker, ctx['u'])
        ctx['pca'][pc_spec] = (rank, n_pc, pca, lds)
        return ctx['pca'][pc_spec]

    def _select_and_fit(train_rets, pc_spec, bsize, enforce_gross=True):
        required_rows = (max(5, int(bsize) + 2)
                         if val_mode in ('HOLDOUT', 'IN-SAMPLE') else min_train_rows)
        ctx = _training_context(train_rets, required_rows)
        tr, ok, u = ctx['tr'], ctx['ok'], ctx['u']
        if any(c not in ok for c in forced):
            raise RuntimeError('Required instruments lack complete training returns: '
                               + ', '.join(c for c in forced if c not in ok))
        rank, n_pc, pca, lds = ctx['corr_rank'], 0, None, pd.DataFrame()
        if str(pc_spec).startswith('single:'):
            ticker = str(pc_spec)[7:]
            if ticker not in u or any(c != ticker for c in forced):
                raise RuntimeError(f'Single hedge {ticker} is ineligible or conflicts with forced names')
            ranked = [ticker]
        elif pc_spec == 'correlation' or (int(bsize) == 1 and not forced):
            ranked = rank.index.tolist()
        elif pc_spec == 'forward':
            if ctx['forward'] is None:
                ctx['forward'] = _forward_order(tr, target_ticker, u, forced,
                                                max(basket_size_options))
            ranked = ctx['forward']
        else:
            rank, n_pc, pca, lds = _context_pca(ctx, pc_spec)
            ranked = rank.index.tolist()
        basket = _forced_basket(ranked, ok, bsize)
        if not basket:
            raise RuntimeError('No valid hedge candidates in this window')
        if len(basket) == 1:
            if ctx['single_fits'] is None:
                ctx['single_fits'] = _fit_single_candidates(tr, target_ticker, u)
            reg, r2, resid = ctx['single_fits'][basket[0]]
        else:
            reg, r2, resid = _fit_basket(tr, target_ticker, basket)
        if enforce_gross and max_gross is not None and np.abs(reg.coef_).sum() > max_gross:
            raise RuntimeError('Refit exceeds the requested gross cap')
        return tr, rank, basket, reg, r2, resid, n_pc, pca, lds

    def _eval_on_window(reg, basket, test_rets):
        """Score a fitted basket on an unseen window → (r2, vol_red) or NaNs."""
        test_rets, problem = _prepare_evaluation(test_rets)
        needed = basket + [target_ticker]
        if problem or _window_problem(test_rets, target_ticker):
            return np.nan, np.nan
        if not all(c in test_rets.columns and np.isfinite(test_rets[c]).all()
                   for c in needed):
            return np.nan, np.nan
        r2 = reg.score(test_rets[basket].values, test_rets[target_ticker].values)
        resid = (test_rets[target_ticker].values -
                 reg.predict(test_rets[basket].values))
        tgt_std = np.std(test_rets[target_ticker].values) * ann_sqrt
        vr = 1 - (np.std(resid) * ann_sqrt) / tgt_std if tgt_std > MIN_RETURN_STD else 0.0
        return r2, vr

    pc_grid = ['auto'] if pc_options == 'auto' else list(pc_options)   # [Fix 4]

    def _extra_baskets(train, eligible, ok):
        entries = []
        if broad_search:
            for ticker in eligible:
                if not forced or forced == [ticker]:
                    entries.append(('single:' + ticker, 1, [ticker], 0))
        for spec in pc_grid:
            if str(spec).startswith('single:'):
                ticker = str(spec)[7:]
                if ticker in eligible and (not forced or forced == [ticker]):
                    entries.append((str(spec), 1, [ticker], 0))
        methods = [m for m in ('correlation', 'forward') if broad_search or m in pc_grid]
        if methods:
            corr_rank = train[eligible].corrwith(train[target_ticker]).abs().sort_values(ascending=False).index.tolist()
            forward_rank = _forward_order(train, target_ticker, eligible, forced, max(basket_size_options))
            for method in methods:
                ranked = corr_rank if method == 'correlation' else forward_rank
                for size in basket_size_options:
                    if int(size) < 2:
                        continue
                    basket = _forced_basket(ranked, ok, int(size))
                    if len(basket) >= 2:
                        entries.append((method, int(size), basket, 0))
        return entries

    def _search_metadata(summary, detail):
        specs = detail['pc_spec'].astype(str)
        return {'broad_search': broad_search,
                'selection_scope': 'basket' if broad_search else 'pinned configuration',
                'single_role': 'reference',
                'single_instruments_scored': int(specs[specs.str.startswith('single:')].nunique()),
                'configurations_scored': len(summary),
                'basket_methods': (['PCA', 'correlation', 'forward selection']
                                   if broad_search else ['pinned configuration']),
                'scope': 'eligible downloaded universe; baskets use three deterministic search heuristics'}

    def _walk_forward_cv(rets_sub, verbose=False):
        """Run the full walk-forward CV grid on rets_sub → summary DataFrame
        (or None if every fold failed)."""
        results = []
        for lookback in lookback_options:
            if lookback + cv_test_window * cv_n_folds > len(rets_sub):
                if verbose:
                    _P(f"  Skipping lookback={lookback} (insufficient data)")
                continue
            for fold in range(cv_n_folds):
                te = len(rets_sub) - fold * cv_test_window
                ts = te - cv_test_window
                tr_e = ts - purge                     # [Fix 39] purge gap
                tr_s = max(0, tr_e - lookback)
                if tr_s >= tr_e or ts >= te:
                    continue
                ret_tr_all = rets_sub.iloc[tr_s:tr_e]
                ret_te_all = rets_sub.iloc[ts:te]

                clean, train_problem = _prepare_training(ret_tr_all, min_train_rows)
                ret_te_common, test_problem = _prepare_evaluation(ret_te_all, 10)
                if train_problem or test_problem:
                    if verbose:
                        _P(f'  Skipping fold {fold} (lookback {lookback}): '
                           f'{"TRAIN " + train_problem if train_problem else "TEST " + test_problem}')
                    continue
                # Candidate eligibility uses cleaned TRAINING observations only.
                ok = list(clean.columns[np.isfinite(clean).all() & (clean.std() > MIN_RETURN_STD)])
                ret_tr, ret_te = clean[ok], ret_te_common[ok]
                cur_uni = [c for c in _eligible(ret_tr_all.index[-1]) if c in ok]
                _P(f'  CV lookback {lookback}, fold {fold+1}/{cv_n_folds}: '
                   f'{len(ret_tr)} training rows; scoring {len(cur_uni)} singles and basket methods')
                entries = _extra_baskets(ret_tr, cur_uni, ok)
                pca_cols = [c for c in ret_tr.columns if c != PORTFOLIO_COL]
                ret_tr_w = _winsorize_returns(ret_tr[pca_cols], winsorize_pct)
                scaler = StandardScaler()
                ret_tr_sc = pd.DataFrame(scaler.fit_transform(ret_tr_w),
                                        index=ret_tr.index, columns=pca_cols)
                cap = min(len(pca_cols) - 1, len(ret_tr) - 1)
                for pc_spec in pc_grid:
                    if str(pc_spec).startswith('single:') or pc_spec in ('correlation', 'forward'):
                        continue
                    n_pc = (_n_pc_auto(ret_tr_sc, cap, robust_cov)
                            if pc_spec == 'auto' else int(min(int(pc_spec), cap)))
                    pca = _pca_fit(ret_tr_sc, n_pc, robust_cov)
                    loadings = pd.DataFrame(pca.components_.T * np.sqrt(pca.explained_variance_),
                                            index=pca_cols)
                    loadings = _inject_synth_loadings(loadings)
                    ranked = _rank_scores(loadings, ret_tr, target_ticker, cur_uni).index.tolist()
                    for bsize in basket_size_options:
                        if broad_search and int(bsize) == 1:
                            continue  # all singles are explicit competing configurations above
                        rank_for_size = ranked
                        if int(bsize) == 1 and not forced:
                            rank_for_size = ret_tr[cur_uni].corrwith(ret_tr[target_ticker]).abs().sort_values(ascending=False).index.tolist()
                        basket = _forced_basket(rank_for_size, ok, int(bsize))
                        if basket:
                            entries.append((str(pc_spec), int(bsize), basket, n_pc))
                single_fits = _fit_single_candidates(ret_tr, target_ticker, cur_uni)
                seen = set()
                for spec, size, basket, n_pc in entries:
                    key = (spec, size)
                    if key in seen:
                        continue
                    seen.add(key)
                    reg, r2_tr, _ = (single_fits[basket[0]] if len(basket) == 1
                                      else _fit_basket(ret_tr, target_ticker, basket))
                    if max_gross is not None and np.abs(reg.coef_).sum() > max_gross:
                        continue
                    r2_te, vol_red = _eval_on_window(reg, basket, ret_te)
                    if not np.isfinite(r2_te):
                        continue
                    n, p = len(ret_tr), len(basket)
                    adj_r2 = 1 - (1 - r2_tr) * (n - 1) / max(1, n - p - 1)
                    results.append({'lookback': lookback, 'pc_spec': spec,
                                    'n_pcs': n_pc, 'basket_size': size, 'fold': fold,
                                    'family': _config_family(spec, len(basket)),
                                    'r2_train': r2_tr, 'adj_r2_train': adj_r2,
                                    'r2_test': r2_te, 'vol_red_test': vol_red,
                                    'gross': float(np.abs(reg.coef_).sum())})
        if not results:
            return None, None
        cv = pd.DataFrame(results)
        summary = cv.groupby(['lookback', 'pc_spec', 'basket_size']).agg(
            family=('family', 'first'),
            avg_r2_oos=('r2_test', 'mean'), std_r2_oos=('r2_test', 'std'),
            avg_vol_red=('vol_red_test', 'mean'),
            std_vol_red=('vol_red_test', 'std'),
            avg_adj_r2=('adj_r2_train', 'mean'),
            avg_gross=('gross', 'mean'),
            n_folds=('fold', 'count')).reset_index()
        # Compare configurations on the requested complete set of folds.
        # A basket must not win just because its bad-data test windows vanished.
        summary = summary.loc[summary['n_folds'] == cv_n_folds].copy()
        if summary.empty:
            if verbose:
                _P(f'  No configuration completed all {cv_n_folds} CV folds; '
                   'partial evidence is not ranked as a validated hedge.')
            return None, cv
        # Sanitize NaN-able metrics so idxmax() always finds something
        summary['std_r2_oos'] = summary['std_r2_oos'].fillna(0)
        summary['avg_r2_oos'] = summary['avg_r2_oos'].fillna(-1)
        summary['avg_vol_red'] = summary['avg_vol_red'].fillna(0)
        summary['avg_gross'] = summary['avg_gross'].fillna(0)
        # [Fix 28] lower-confidence-bound composite: penalize dispersion
        # instead of rewarding it. The old 1/std "stability" bonus let a
        # reliably-useless config outrank a noisy-but-useful one.
        # [Fix 38] gross-exposure penalty: ridge on near-collinear ETFs
        # happily builds $500+-gross long/short recipes whose extra R² is a
        # multicollinearity artifact (e.g. short QQQ / long XLK offsets).
        # Penalize by average gross, in units of the $100 target notional
        # (avg_gross=2.6 means $260 gross), and optionally hard-cap it.
        # ── [Fix 108] RECENCY — "if it deteriorates, why is it the best?" ──
        # The composite averages OOS R² over ALL folds with equal weight, so
        # a config that was excellent two years ago and mediocre last quarter
        # can still win on the mean. The old build only NOTICED that after
        # the fact (a WARN in the ticket: "R² deteriorates toward the most
        # recent window"); nothing in the selection ever acted on it. That is
        # a fair criticism of the logic, and there are two honest halves to
        # the answer:
        #   1. It is DELIBERATE that the default does not chase recency. A
        #      hedge ratio is a covariance estimate; with cv_test_window=42
        #      each fold is ~2 months, so "the last two folds" is a handful
        #      of independent observations. Selecting on those alone swaps a
        #      known bias (stale regime) for a much larger variance (picking
        #      noise). Measured across configs the fold-to-fold spread of R²
        #      is routinely ±0.15 — bigger than most real deterioration.
        #   2. But the user should SEE the trade-off rather than have it
        #      hidden. So the recency figures are now computed for every
        #      config, always, and section [1b] reports what a
        #      recent-folds-only selection WOULD have chosen and what it
        #      would have scored. recency_weight>0 acts on it.
        _nf = int(cv['fold'].max()) + 1 if len(cv) else 1
        _recent_k = max(1, int(np.ceil(_nf / 2.0)))     # newest half of folds
        _rec = (cv[cv['fold'] < _recent_k]
                .groupby(['lookback', 'pc_spec', 'basket_size'])
                .agg(recent_r2=('r2_test', 'mean'),
                     recent_vol_red=('vol_red_test', 'mean'),
                     n_recent=('fold', 'count')).reset_index())
        summary = summary.merge(_rec, on=['lookback', 'pc_spec',
                                          'basket_size'], how='left')
        # per-config slope of R² against fold index. fold 0 is the NEWEST, so
        # a POSITIVE slope means R² rises as you go back = deteriorating now.
        # [Fix 114] computed with an explicit loop rather than
        # groupby.apply(..., include_groups=False): that keyword only exists
        # from pandas 2.2, and without it 2.2+ emits a DeprecationWarning
        # while <2.2 raises TypeError outright. A purely diagnostic column
        # must not be able to take the whole selection down on an older
        # kernel, and the loop is over a handful of configs either way.
        _sl_rows = []
        for _key, _g in cv.groupby(['lookback', 'pc_spec', 'basket_size']):
            _sl_rows.append({
                'lookback': _key[0], 'pc_spec': _key[1],
                'basket_size': _key[2],
                'r2_slope_per_fold': (
                    float(np.polyfit(_g['fold'].values,
                                     _g['r2_test'].values, 1)[0])
                    if _g['fold'].nunique() >= 3 else np.nan)})
        _sl = pd.DataFrame(_sl_rows)
        summary = summary.merge(_sl, on=['lookback', 'pc_spec',
                                         'basket_size'], how='left')
        # the score the ranking actually uses
        if recency_weight and recency_weight > 0:
            _w = np.exp(-float(recency_weight) * cv['fold'].values)
            _cvw = cv.assign(_w=_w, _r2w=cv['r2_test'].values * _w,
                             _vrw=cv['vol_red_test'].values * _w)
            _wm = (_cvw.groupby(['lookback', 'pc_spec', 'basket_size'])
                   .agg(_sw=('_w', 'sum'), _sr=('_r2w', 'sum'),
                        _sv=('_vrw', 'sum')).reset_index())
            _wm['w_r2'] = _wm['_sr'] / _wm['_sw']
            _wm['w_vr'] = _wm['_sv'] / _wm['_sw']
            summary = summary.merge(_wm[['lookback', 'pc_spec', 'basket_size',
                                         'w_r2', 'w_vr']],
                                    on=['lookback', 'pc_spec', 'basket_size'],
                                    how='left')
            _r2_use = summary['w_r2'].fillna(summary['avg_r2_oos'])
            _vr_use = summary['w_vr'].fillna(summary['avg_vol_red'])
        else:
            _r2_use, _vr_use = summary['avg_r2_oos'], summary['avg_vol_red']
        summary['composite'] = ((_r2_use - 0.5 * summary['std_r2_oos']) * 0.6
                                + _vr_use * 0.4
                                - gross_penalty * summary['avg_gross'])
        if hedge_objective == 'variance':
            summary['composite'] = (_vr_use
                                    - .5 * summary['std_vol_red'].fillna(0)
                                    - gross_penalty * summary['avg_gross'])
        # the same score computed on the RECENT folds only — never used for
        # the live pick, always reported, so the alternative is visible
        summary['composite_recent'] = (
            (summary['recent_r2'].fillna(-1)) * 0.6
            + summary['recent_vol_red'].fillna(0) * 0.4
            - gross_penalty * summary['avg_gross'])
        if hedge_objective == 'variance':
            summary['composite_recent'] = (summary['recent_vol_red'].fillna(0)
                                           - gross_penalty * summary['avg_gross'])
        if max_gross is not None:
            within = summary[summary['avg_gross'] <= max_gross]
            if len(within):
                summary = within.reset_index(drop=True)
            else:
                return None, cv  # A user-specified cap is never silently ignored.
        return summary, cv


    # ── [Fix 77] SHORT-SAMPLE FLOW (HOLDOUT / IN-SAMPLE) ────────────────────
    # Too little data for the walk-forward machinery: fit once, score the
    # held-out tail if there is one, print an honest mini-report in the
    # [Fix 79] layout, and return the same result-dict shape as a full run.
    def _short_sample_result(val_mode, hold_rows, fallback_reason=None,
                             cv_summary=None, cv_detail=None, prior_nested=None):
        fit_rets = rets.iloc[:rows - hold_rows - (purge if hold_rows else 0)]
        short_context = _training_context(fit_rets, max(5, min(basket_size_options) + 2))
        fit_rets = short_context['tr']
        short_trials, short_errors = [], []
        short_specs = [(str(pc), int(size)) for pc in pc_grid for size in basket_size_options
                       if not (broad_search and int(size) == 1)]
        _short_ok = list(fit_rets.columns[fit_rets.notna().all() & (fit_rets.std() > MIN_RETURN_STD)])
        _short_u = [c for c in _eligible(fit_rets.index[-1]) if c in _short_ok]
        short_specs += [(spec, size) for spec, size, _, _ in _extra_baskets(fit_rets, _short_u, _short_ok)]
        short_specs = list(dict.fromkeys(short_specs))
        _P(f'  Short-history search: {len(short_specs)} configurations; '
           'single-instrument ridge fits are batched; PCA is shared across basket sizes')
        for trial_no, (short_pc, short_size) in enumerate(short_specs, 1):
            if trial_no == 1 or trial_no % 250 == 0 or trial_no == len(short_specs):
                _P(f'  Short-history search {trial_no}/{len(short_specs)}')
            try:
                fitted = _select_and_fit(fit_rets, short_pc, int(short_size))
            except RuntimeError as error:
                short_errors.append(str(error))
                continue
            _, _, _, short_reg, short_r2, short_resid, _, _, _ = fitted
            target_sd = float(np.std(fit_rets[target_ticker].values))
            short_vr = 1 - float(np.std(short_resid)) / target_sd
            measure = short_vr if hedge_objective == 'variance' else short_r2
            gross = float(np.abs(short_reg.coef_).sum())
            if max_gross is not None and gross > max_gross:
                continue
            score = measure - gross_penalty * gross
            short_trials.append((score, short_pc, int(short_size), fitted))
        if not short_trials:
            raise ValueError(f'Cannot fit on {len(fit_rets)} rows: '
                             + '; '.join(short_errors[:3]))
        primary_trials = ([t for t in short_trials if len(t[3][2]) >= 2]
                          if broad_search else short_trials)
        if not primary_trials:
            raise ValueError('No usable primary basket under these settings. '
                             'At least two eligible instruments with complete training returns '
                             'are required; single references cannot replace the basket.')
        _, _ps0, _bs0, fitted = max(primary_trials, key=lambda item: (item[0], -item[2]))
        (_, s_rank, s_basket, s_reg, s_r2_in, s_resid, s_npc, s_pca, s_loadings) = fitted
        _P(('  Fitted basket reference: ' if fallback_reason else '  Short sample: ')
           + 'configuration selected on training data only; '
           'the holdout, if available, is scored afterwards. In-sample choices '
           'are indicative, not independently validated.')
        s_w = pd.Series(s_reg.coef_, index=s_basket)
        # [Fix 83] adjusted R² — with k regressors on a short window the raw
        # in-sample R² is inflated by construction, and this tier is exactly
        # where that bites. A NEGATIVE adjusted R² means the fit explains
        # less than its degrees of freedom cost.
        _n_fit, _k_fit = len(fit_rets), len(s_basket)
        s_r2_adj = (1 - (1 - s_r2_in) * (_n_fit - 1) / max(1, _n_fit - _k_fit - 1)
                    if _n_fit > _k_fit + 1 else np.nan)
        s_te_in = float(np.std(s_resid) * ann_sqrt)
        s_tvol = float(fit_rets[target_ticker].std(ddof=0) * ann_sqrt)
        s_vr_in = 1 - s_te_in / s_tvol if s_tvol > MIN_RETURN_STD else 0.0
        # single-instrument comparison on the SAME basis
        _okc = fit_rets.columns[(fit_rets.notna().all())
                                & (fit_rets.std() > MIN_RETURN_STD)]
        _pool = [c for c in _okc if c in short_context['u']
                 and (not forced or forced == [c])]
        _acorr = (fit_rets[_pool].corrwith(fit_rets[target_ticker]).abs()
                  if _pool else pd.Series(dtype=float))
        _etf_p = [c for c in _pool if _is_etf(c)]
        _etf_c = _acorr[_etf_p].dropna() if _etf_p else pd.Series(dtype=float)
        s_best_etf = _etf_c.idxmax() if len(_etf_c) else None  # [Fix 83]
        s_r2e = np.nan
        s_reg_e = None
        if s_best_etf is not None:
            s_reg_e, s_r2e, _ = _fit_basket(fit_rets, target_ticker,
                                            [s_best_etf])
        s_r2_h = s_vr_h = s_te_h = s_r2e_h = np.nan
        if hold_rows:
            s_test, _ = _prepare_evaluation(rets.iloc[rows - hold_rows:])
            s_r2_h, s_vr_h = _eval_on_window(s_reg, s_basket, s_test)
            if not np.isnan(s_r2_h):
                _rh = (s_test[target_ticker].values
                       - s_reg.predict(s_test[s_basket].values))
                s_te_h = float(np.std(_rh) * ann_sqrt)
            if s_reg_e is not None:
                s_r2e_h, _ = _eval_on_window(s_reg_e, [s_best_etf], s_test)
        # verdict — honest about how thin the evidence is
        if val_mode == 'HOLDOUT':
            _gap_s = (s_r2_in - s_r2_h) if not np.isnan(s_r2_h) else np.nan
            grade, reasons = _ticket_verdict(
                s_r2_h, s_r2_h, _gap_s, None, False, s_r2_h, s_r2e_h, False,
                vol_red=s_vr_h, worst_vol_red=s_vr_h, objective=hedge_objective)
            if grade.startswith('✓'):
                grade = '△ LIMITED EVIDENCE — REVIEW CANDIDATE'
            reasons.insert(0, f'single {hold_rows}-row holdout — thin '
                              f'evidence; compare with a longer analysis window')
        else:
            grade = '? IN-SAMPLE ONLY — DO NOT SIZE OFF THIS'
            reasons = [
                fallback_reason or f'{rows} rows: no unseen validation was available',
                f'{len(s_basket)} regressors on {len(fit_rets)} obs — the '
                f'fitted R² is not independent evidence',
                'use for exposure identification; validate on a longer '
                'window before trading']
        if np.isfinite(s_r2_h) and s_r2_h < 0:
            grade = '✗ NO VALIDATED HEDGE'
            reasons.insert(0, 'negative unseen tracking R²; candidate retained for reference only')
        # display names (built later in the full flow — needed here)
        _shorts = pd.Series({c: c.split(' ')[0] for c in fit_rets.columns})
        _dup = _shorts[_shorts.duplicated(keep=False)].index
        disp = {c: (c if c in _dup else _shorts[c])
                for c in fit_rets.columns}
        if is_portfolio:
            disp[target_ticker] = pf_label
        # mini-report in the [Fix 79] layout
        L = 78
        # [Fix 114] SHORT-SAMPLE PATH — same renderer as the full report.
        # This branch kept its own print()-based title/kv, so a user who set
        # sample_window='3m' (a documented workflow) still got the packed
        # monospace layout the whole [Fix 104] pass existed to remove. It is
        # also the tier where the reader most needs to be told what a number
        # means, because none of these numbers are properly validated.
        title = _section
        def kv(label, value, implication=''):
            _KVCTX['rows'].append((label, value, implication))
        kvo = _kv_open
        title(f"PCA HEDGE — {target_short}   ·   "
              f"{datetime.now():%Y-%m-%d %H:%M}")
        _P(f"  Objective: {hedge_objective} · {val_mode} validation · {len(universe)} names considered · "
           f"{'2-day overlapping' if two_day else 'daily'} returns · "
           f"{rows} rows ({rets.index[0]:%d%b%y}→{rets.index[-1]:%d%b%y})")
        title("[0] TICKET")
        _verdict_banner(grade, reasons,                        # [Fix 87]
                        f"{val_mode} tier — {TIER_MEANING[val_mode]}")
        _P(f"  INDICATIVE CANDIDATE RECIPE   per $100 of "
           f"{'gross book' if is_portfolio else 'long ' + target_short}"
           + (f"  ($MM column: ${notional_mm:g}mm gross)"
              if notional_mm else ""))
        _t_head = ['ACTION', '$/100', 'INSTRUMENT', 'FULL TICKER', '★']
        if notional_mm:
            _t_head.insert(2, '≈$MM')
        _t_rows = []
        for _tk, _wgt in s_w.sort_values(key=lambda s: -s.abs()).items():
            _row = ['SHORT' if _wgt > 0 else 'LONG',
                    '$' + format(abs(_wgt) * 100, '.1f'),
                    disp.get(_tk, _tk.split(' ')[0]), _tk,
                    '★' if _tk in forced else '']
            if notional_mm:
                _row.insert(2, '$' + format(abs(_wgt) * notional_mm, ',.2f'))
            _t_rows.append(_row)
        _print_table(_t_head, _t_rows)
        _net = s_w.sum() * 100
        _gr = s_w.abs().sum() * 100
        kvo('THE POSITION')
        kv('Exposure', f"gross ${_gr:.1f} · net "
                       f"{'short' if _net >= 0 else 'long'} ${abs(_net):.1f}",
           f"You put on ${_gr:.0f} of hedge per $100 of book. Financing and "
           f"borrow scale with this and are not modelled.")
        kv('Hedged (in-sample)', f"vol {s_tvol*100:.1f}% → "
           f"{s_te_in*100:.1f}%/yr ({s_vr_in*100:.0f}% cut) · "
           f"R² {s_r2_in:.2f}",
           'Fit and scored on the SAME rows. On a window this short that is '
           'a weak basis for forecasting. Later performance can be either '
           'better or worse; use the unseen evidence when available.')
        if notional_mm:                                        # [Fix 86]
            _te_s = s_te_h if np.isfinite(s_te_h) else s_te_in
            kv('RISK ($)', f"±{_fmt_money_mm(_te_s*notional_mm)}/yr · "
                           f"±{_fmt_money_mm(_te_s*notional_mm/np.sqrt(252))}"
                           f"/day",
               f"1σ residual P&L on ${notional_mm:g}mm gross"
               + (' — priced off the holdout.' if np.isfinite(s_te_h)
                  else ' — priced IN-SAMPLE, so treat it as a FLOOR on the '
                       'real risk, not an estimate of it.'))
        title("[1] EVIDENCE — all of it")
        kvo('EVIDENCE', note=f"{val_mode} tier: "
            f"{TIER_MEANING[val_mode]} Everything here is descriptive; "
            f"nothing on this path has survived a walk-forward.")
        kv('In-sample R²', f"{s_r2_in:.3f} on {len(fit_rets)} rows "
           f"({len(s_basket)} names, PCs {s_npc})"
           + (f" · complexity score {s_r2_adj:.3f} (heuristic)" if np.isfinite(s_r2_adj) else ""),
           'The adjusted figure penalizes nominal regressor count. It is an '
           'OLS-style heuristic for Ridge, not effective degrees of freedom '
           'and not out-of-sample evidence. A negative value can be legitimate.')
        if np.isfinite(s_r2_adj) and s_r2_adj < 0.1:
            kv('  ⚠ Ridge complexity score', f"{s_r2_adj:.3f}",
               'On this window the fit barely beats its own '
               'degrees-of-freedom cost. Treat the basket as a HYPOTHESIS, '
               'not a hedge — re-run on a longer window before trading it.')
        if hold_rows:
            kv('Holdout OOS R²',
               (f"{s_r2_h:.3f} · vol red {s_vr_h*100:.1f}% · TE "
                f"{s_te_h*100:.1f}%/yr"
                if not np.isnan(s_r2_h)
                else 'n/a (incomplete data in the holdout)'),
               f"The only number here the fit did not see: the last "
               f"{hold_rows} rows. One window, so it is an anecdote — but it "
               f"is the only honest anecdote on the page.")
        if s_best_etf is not None:
            kv('Correlation-picked ETF', f"{disp.get(s_best_etf, s_best_etf)}: "
               f"in-sample R² {s_r2e:.2f}"
               + (f" · holdout {s_r2e_h:.2f}"
                  if not np.isnan(s_r2e_h) else ''),
               'Reference only. Its score does not replace or approve the primary basket.')
        if fallback_reason:
            kv('Basket validation', 'No basket completed every CV fold', fallback_reason)
        kv('Next step', ('inspect the data and requested basket settings' if fallback_reason
                         else 'needs ≥ ~150 rows for the full protocol'),
           ('Inspect the failed fold diagnostics and eligible basket instruments. '
            'A fitted reference does not repair missing validation data.' if fallback_reason else
            "For CV, nested windows and the rolling curve, give the model "
            "more data — e.g. sample_window='1y', or drop sample_window entirely."))
        if show_plots:
            kv('Charts', 'fitted diagnostics',
               'Short-window charts describe the training fit; they do not add unseen evidence.')
        _kv_flush()
        alternatives = {}
        for family in ('basket', 'single', 'single_stock', 'single_etf', 'single_market'):
            trials = [t for t in short_trials
                      if (str(t[1]).removeprefix('single:') in market_tickers
                          if family == 'single_market' else
                          _config_family(t[1], len(t[3][2])).startswith('single')
                          if family == 'single' else _config_family(t[1], len(t[3][2])) == family)]
            if not trials:
                continue
            trial = max(trials, key=lambda t: (t[0], -t[2]))
            _, spec, size, fitted_alt = trial
            _, _, basket_alt, reg_alt, raw_alt, _, _, _, _ = fitted_alt
            ys, residuals, spreads = [], [], []
            if hold_rows:
                test_alt, _ = _prepare_evaluation(rets.iloc[-hold_rows:])
                q_alt, _ = _eval_on_window(reg_alt, basket_alt, test_alt)
                if np.isfinite(q_alt):
                    y_alt = test_alt[target_ticker].to_numpy()
                    ys.append(y_alt)
                    residuals.append(y_alt - reg_alt.predict(test_alt[basket_alt].values))
                    spreads.append(y_alt - test_alt[basket_alt].values @ reg_alt.coef_)
            alternatives[family] = _alternative_evidence(
                pd.Series(reg_alt.coef_, index=basket_alt), raw_alt, ys, residuals, spreads,
                ann_sqrt, 1 if hold_rows else 0, val_mode,
                {'lookback': len(fit_rets), 'pc_spec': spec, 'basket_size': size,
                 'selection_score': trial[0], 'max_gross': max_gross}, hedge_objective)
            alternatives[family]['reference_only'] = family.startswith('single')
        selected_family = _config_family(_ps0, len(s_basket))
        primary_item = alternatives.get(selected_family)
        if primary_item is not None and val_mode != 'IN-SAMPLE':
            primary_item['qualified'] = _decision_fields(s_w, grade)['trade_eligible']
            if not primary_item['qualified']:
                primary_item['status'] = grade
        search = {'broad_search': broad_search,
                  'selection_scope': 'basket' if broad_search else 'pinned configuration',
                  'single_role': 'reference',
                  'single_instruments_scored': len({t[1] for t in short_trials if str(t[1]).startswith('single:')}),
                  'configurations_scored': len(short_trials),
                  'basket_methods': ['PCA', 'correlation', 'forward selection'] if broad_search else ['pinned configuration']}
        selected_family = _config_family(_ps0, len(s_basket))
        _show_hedge_comparison(alternatives, selected_family, search)

        # Retain useful fitted exposure/path diagnostics even in short history.
        # They do not upgrade the validation tier or qualify the basket.
        short_spread = pd.Series(fit_rets[target_ticker].values
                                 - fit_rets[s_basket].values @ s_w.values, index=fit_rets.index)
        short_path = _spread_path_stats(short_spread, two_day, 'fitted coefficient-only spread')
        target_fit = fit_rets[target_ticker]
        worst = short_spread[target_fit <= target_fit.quantile(.1)]
        best = short_spread[target_fit >= target_fit.quantile(.9)]
        short_tail = ({'worst_decile_mean': float(worst.mean()), 'best_decile_mean': float(best.mean()),
                       'gap_bp_day': float((worst.mean()-best.mean())*1e4), 'n_worst': len(worst)}
                      if len(worst) >= 5 and len(best) >= 5 else {})
        stock_cols = [c for c in fit_rets if c != target_ticker and c not in set(pf_legs) and not _is_etf(c)]
        short_factors = _factor_leakage(fit_rets, target_ticker, s_w,
                          caps_map={c: _cap_asof(c, fit_rets.index[-1]) for c in stock_cols},
                          stock_cols=stock_cols)
        short_candidates, short_seen = [], set()
        ordered_trials = sorted(primary_trials, key=lambda t: (t[1] == _ps0 and t[2] == _bs0, t[0]), reverse=True)
        for trial in ordered_trials:
            _, spec, size, fitted_alt = trial
            w_alt = pd.Series(fitted_alt[3].coef_, index=fitted_alt[2])
            key = tuple(sorted((tk, round(float(x), 5)) for tk, x in w_alt.items()))
            if len(w_alt) < 2 or key in short_seen:
                continue
            short_seen.add(key)
            short_candidates.append(dict(cfg={'avg_r2_oos': np.nan}, lb=len(fit_rets), ps=spec,
                bs=size, sel=spec == _ps0 and size == _bs0, r2m=np.nan, vrm=np.nan, n=0,
                w=w_alt, r2_in=fitted_alt[4]))
            if len(short_candidates) >= alternative_baskets + 1:
                break
        if show_plots and s_pca is None:
            _, _, s_pca, s_loadings = _context_pca(short_context, 'auto')
        return {
            'training_data_diagnostics': pd.DataFrame(training_diagnostics),
            'evaluation_data_diagnostics': pd.DataFrame(evaluation_diagnostics),
            'engine_revision': PCA_REVISION,
            'basket_candidates': short_candidates,
            'chart_pca': s_pca, 'chart_loadings': s_loadings,
            'primary_hedge_family': selected_family,
            'hedge_alternatives': alternatives, 'search': search,
            'best_basket_hedge': alternatives.get('basket'),
            'best_single_hedge': alternatives.get('single'),
            'best_single_stock_hedge': alternatives.get('single_stock'),
            'best_single_etf_hedge': alternatives.get('single_etf'),
            **_decision_fields(s_w, grade),
            'unhedged_baseline': {'vol_reduction': 0.0, 'variance_reduction': 0.0},
            'weights': s_w, 'basket': s_basket, 'ranking': s_rank,
            'cv_summary': cv_summary, 'cv_detail': cv_detail,
            'fallback_reason': fallback_reason,
            'prior_nested_validation': prior_nested,
            'nested_validation': pd.DataFrame(),
            'nested_r2_mean': np.nan, 'nested_r2_std': np.nan,
            'nested_vol_red_mean': np.nan, 'nested_pooled_r2': np.nan,
            'selected_unseen_r2': s_r2_h, 'selected_unseen_r2_std': np.nan,
            'selected_unseen_pooled_r2': s_r2_h,
            'outer_window_detail': pd.DataFrame(),
            'bootstrap_ci': None, 'rolling_oos': pd.DataFrame(),
            'decay': {}, 'turnover': {},
            'drift_ann': (float(s_reg.intercept_) * 252.0    # [Fix 121]
                          / (2 if two_day else 1)),
            'asymmetry': short_tail, 'path': short_path,
            'exposures': (data or {}).get('exposures') or {},  # [Fix 119]
            'ticket': {'grade': grade, 'reasons': reasons,
                       'hedge_objective': hedge_objective,
                       'quality_r2': (s_r2_h if hold_rows else np.nan),
                       'quality_source': ('holdout' if hold_rows
                                          else 'in-sample only'),
                       'worst_window_r2': np.nan, 'worst_window_te': np.nan,
                       'kill_switch_te': np.nan, 'overfit_gap': np.nan,
                       'rebalance_rows': None},
            'nowcast': {}, 'horizon': {},                  # [Fix 91/93]
            'target_label': target_short,              # [Fix 103] for export
            'analysis_span': (rets.index[0], rets.index[-1], rows),  # [Fix 99]
            'holdout_r2': s_r2_h, 'holdout_vol_red': s_vr_h,
            'holdout_te': s_te_h, 'in_sample_r2': s_r2_in,
            'trade_risk': (primary_item or {}).get('trade_risk', {}),
            'in_sample_r2_adj': s_r2_adj,                  # [Fix 83]
            'validation_mode': val_mode,
            'etf_benchmark': pd.DataFrame(), 'etf_nested_r2_mean': np.nan,
            'name_benchmark': pd.DataFrame(), 'name_nested_r2_mean': np.nan,
            'best_single': None, 'best_etf': s_best_etf,
            'returns': fit_rets, 'prices': prices,
            'two_day_returns': two_day,
            'excluded': removed_cols, 'force_included': forced,
            'is_portfolio': is_portfolio,
            'portfolio_legs': pf_legs, 'portfolio_weights': pf_w,
            'factor_leakage': short_factors,
            'pit_size_active': pit_active, 'pit_members_active': pm_active,
            'params': {'lookback': len(fit_rets), 'pc_spec': _ps0,
                       'basket_size': _bs0, 'hedge_objective': hedge_objective, 'broad_search': broad_search,
                       'recency_weight': recency_weight,
                       'tz_tolerance_hours': tz_tolerance_hours,
                       'min_mktcap_usd_mm': min_mktcap_usd_mm,
                       'gross_penalty': gross_penalty, 'max_gross': max_gross,
                       'force_include': force_include,
                       'winsorize_pct': winsorize_pct,
                       'robust_cov': robust_cov,
                       'pit_size': pit_size, 'pit_members': pit_members,
                       'size_band': size_band,
                       'size_override': size_override,
                       'mask_stale_days': mask_stale_days,
                       'notional_mm': notional_mm, 'boot_n': boot_n,
                       'sample_window': sample_window, 'report': report},
        }

    if val_mode in ('HOLDOUT', 'IN-SAMPLE'):
        return _short_sample_result(val_mode, hold_rows)

    # ── STEP 3: NESTED WALK-FORWARD VALIDATION [Fix 20] ──────────────────────
    # For each of the last `outer_folds` windows: rerun CV + selection + refit
    # using ONLY data prior to that window, then score on it. This measures
    # the whole pipeline out-of-sample, across multiple periods — not a
    # single-window estimate.
    _P(f"Nested walk-forward validation — the whole pipeline on data it has "
          f"never seen: {outer_folds} unseen "
          f"window{'s' if outer_folds != 1 else ''} of {outer_window}d, with "
          f"the config re-chosen from scratch before each one on "
          f"{cv_n_folds} earlier fold{'s' if cv_n_folds != 1 else ''}...")
    nested_rows = []
    nested_y_all, nested_res_all = [], []                     # [Fix 69]
    nested_trade_res_all = []
    nested_index_all = []
    family_tests = {f: {'y': [], 'residual': [], 'spread': []}
                    for f in ('basket', 'single', 'single_stock', 'single_etf', 'single_market')}
    N = len(rets)
    for j in range(1, outer_folds + 1):
        o_end = N - (j - 1) * outer_window
        o_start = o_end - outer_window
        inner = rets.iloc[:max(0, o_start - purge)]   # [Fix 39] purge gap
        outer_test, _ = _prepare_evaluation(rets.iloc[o_start:o_end])
        summary_j, _ = _walk_forward_cv(inner)
        if summary_j is None:
            _P(f"  outer window {j}: inner CV failed — skipped")
            continue
        for family, evidence in family_tests.items():
            choices = _family_configs(summary_j, family, market_tickers)
            if choices.empty:
                continue
            choice = choices.loc[choices['composite'].idxmax()]
            try:
                _, _, fb, fr, _, _, _, _, _ = _select_and_fit(
                    inner.iloc[-int(choice['lookback']):], choice['pc_spec'], int(choice['basket_size']))
                if max_gross is not None and np.abs(fr.coef_).sum() > max_gross:
                    raise RuntimeError('Outer refit exceeds the requested gross cap')
                fq, _ = _eval_on_window(fr, fb, outer_test)
                if np.isfinite(fq):
                    fy = outer_test[target_ticker].to_numpy()
                    evidence['y'].append(fy)
                    evidence['residual'].append(fy - fr.predict(outer_test[fb].values))
                    evidence['spread'].append(fy - outer_test[fb].values @ fr.coef_)
            except RuntimeError:
                pass
        primary_choices = _family_configs(summary_j, 'basket') if broad_search else summary_j
        if primary_choices.empty:
            _P(f'  outer window {j}: no basket completed inner CV — '
               'single references cannot replace the primary basket')
            continue
        cfg = primary_choices.loc[primary_choices['composite'].idxmax()]
        lb_j = int(cfg['lookback'])
        try:
            _, _, bkt_j, reg_j, _, _, _, _, _ = _select_and_fit(
                inner.iloc[-lb_j:], cfg['pc_spec'], int(cfg['basket_size']))
            if max_gross is not None and np.abs(reg_j.coef_).sum() > max_gross:
                raise RuntimeError('Outer refit exceeds the requested gross cap')
            r2_j, vr_j = _eval_on_window(reg_j, bkt_j, outer_test)
        except RuntimeError as e:
            _P(f"  outer window {j}: refit failed ({e}) — skipped")
            continue
        if not np.isnan(r2_j):                                # [Fix 69]
            _yo = outer_test[target_ticker].values
            nested_index_all.append(outer_test.index)
            nested_y_all.append(_yo)
            nested_trade_res_all.append(_yo - outer_test[bkt_j].values @ reg_j.coef_)
            nested_res_all.append(_yo - reg_j.predict(
                outer_test[bkt_j].values))
        nested_rows.append({
            'window': j, 'start': outer_test.index[0], 'end': outer_test.index[-1],
            'lookback': lb_j, 'pc_spec': cfg['pc_spec'],
            'basket_size': int(cfg['basket_size']),
            'r2_oos': r2_j, 'vol_red_oos': vr_j,
            'tgt_vol': float(outer_test[target_ticker].std(ddof=0) * ann_sqrt),
            'weights': pd.Series(reg_j.coef_, index=bkt_j),
        })
        _P(f"  window {j} ({outer_test.index[0]:%d %b %Y} → "
              f"{outer_test.index[-1]:%d %b %Y}): OOS R² {r2_j:.3f} · "
              f"vol red {vr_j*100:.1f}%   [picked lb={lb_j}, "
              f"pc={cfg['pc_spec']}, k={int(cfg['basket_size'])}]")
    nested = pd.DataFrame(nested_rows, columns=[
        'window', 'start', 'end', 'lookback', 'pc_spec', 'basket_size',
        'r2_oos', 'vol_red_oos', 'tgt_vol', 'weights'])
    nested_valid = nested.dropna(subset=['r2_oos']) if len(nested) else nested
    if len(nested_valid):
        nested_r2_mean = nested_valid['r2_oos'].mean()
        nested_r2_std = nested_valid['r2_oos'].std(ddof=0)
        nested_vr_mean = nested_valid['vol_red_oos'].mean()
    else:
        nested_r2_mean = nested_r2_std = nested_vr_mean = np.nan
        _P("  ⚠ nested validation produced no valid windows")
    # [Fix 69] pooled R² across the CONCATENATED nested windows — the same
    # statistic as [Fix 65]'s pooled figure, but for the HONEST pipeline
    # (selection re-run before each window). This is the headline number.
    nested_pooled = np.nan
    if nested_y_all:
        _yc = np.concatenate(nested_y_all)
        _rc = np.concatenate(nested_res_all)
        _sst = float(np.sum((_yc - _yc.mean()) ** 2))
        if _sst > MIN_RETURN_STD ** 2:
            nested_pooled = 1.0 - float(np.sum(_rc ** 2)) / _sst

    trade_risk = (_trade_risk(np.concatenate(nested_y_all),
                              np.concatenate(nested_trade_res_all), ann_sqrt)
                  if nested_y_all else {})
    trade_risk['source'] = 'nested unseen coefficient-only spread'
    nested_detail = nested_valid.rename(columns={'r2_oos': 'r2', 'vol_red_oos': 'vol_red'})
    nested_disp = _window_dispersion_stats(nested_detail, nested_pooled, outer_window)
    nested_unseen = (pd.DataFrame({
        'target': np.concatenate(nested_y_all[::-1]),
        'regression_residual': np.concatenate(nested_res_all[::-1]),
        'traded_spread': np.concatenate(nested_trade_res_all[::-1])},
        index=pd.DatetimeIndex(np.concatenate([ix.to_numpy() for ix in nested_index_all[::-1]])))
        if nested_y_all else pd.DataFrame())

    # ── [Fix 27/53] HONESTY BENCHMARKS: simplest hedges, same windows ──────
    # [Fix 27] scored a single best-correlated ETF on the outer windows.
    # [Fix 53] extends it in two ways, because section [3] used to quote
    # IN-SAMPLE single-name and single-ETF R² next to out-of-sample basket
    # numbers — a comparison the basket could not lose:
    #   1. there is now a single-NAME benchmark, not only a single-ETF one;
    #   2. the instrument AND the lookback are both chosen using only data
    #      BEFORE each outer window (per lookback take the best-|corr|
    #      candidate, keep the pair with the highest TRAIN R²). The old code
    #      hard-wired lookback = min(lookback_options), which handed the
    #      simple hedge a worse config than the basket was allowed to search.
    # Both benchmarks are scored on the SAME unseen outer windows as the PCA
    # numbers, so section [3] can compare like with like.
    def _single_bench(pool_filter):
        rows = []
        for j in range(1, outer_folds + 1):
            o_end = N - (j - 1) * outer_window
            o_start = o_end - outer_window
            best = None                      # (train_r2, pick, lookback, reg)
            for lb in lookback_options:
                tr_all = rets.iloc[max(0, o_start - purge - lb):o_start - purge]
                tr_clean, tr_problem = _prepare_training(tr_all, min_train_rows)
                if tr_problem:
                    continue
                ok = tr_clean.columns[np.isfinite(tr_clean).all() &
                                      (tr_clean.std() > MIN_RETURN_STD)]
                if target_ticker not in ok:
                    continue
                tr = tr_clean[ok]
                eligible = set(_eligible(tr_all.index[-1]))
                pool = [c for c in ok if c in eligible and c != target_ticker
                        and c not in set(pf_legs) and pool_filter(c)
                        and (not forced or forced == [c])]
                if not pool:
                    continue
                pick = tr[pool].corrwith(tr[target_ticker]).abs().idxmax()
                reg_b, r2_tr, _ = _fit_basket(tr, target_ticker, [pick])
                if max_gross is not None and np.abs(reg_b.coef_).sum() > max_gross:
                    continue
                if best is None or r2_tr > best[0]:
                    best = (r2_tr, pick, lb, reg_b)
            if best is None:
                continue
            _, pick, lb, reg_b = best
            r2_b, vr_b = _eval_on_window(reg_b, [pick],
                                         rets.iloc[o_start:o_end])
            if not np.isnan(r2_b):
                rows.append({'window': j, 'instrument': pick, 'lookback': lb,
                             'r2_oos': r2_b, 'vol_red_oos': vr_b})
        return pd.DataFrame(rows, columns=['window', 'instrument', 'lookback',
                                           'r2_oos', 'vol_red_oos'])

    etf_bench = _single_bench(lambda c: _is_etf(c))
    name_bench = _single_bench(lambda c: not _is_etf(c))
    etf_r2_mean = etf_bench['r2_oos'].mean() if len(etf_bench) else np.nan
    etf_vr_mean = etf_bench['vol_red_oos'].mean() if len(etf_bench) else np.nan
    name_r2_mean = name_bench['r2_oos'].mean() if len(name_bench) else np.nan
    name_vr_mean = name_bench['vol_red_oos'].mean() if len(name_bench) else np.nan

    # [Fix 30] evaluate ANY config on the outer windows (trained strictly on
    # data preceding each window) — used for the selected config in [1] and
    # for every basket in the top-5 section
    outer_windows = [(N - j * outer_window, N - (j - 1) * outer_window)
                     for j in range(1, outer_folds + 1)]

    def _config_outer_oos(lb, ps, bs, detail=False):
        """[Fix 30] mean OOS stats for a config on the outer windows.
        [Fix 65] detail=True additionally returns per-window rows (dates,
        R², vol red, target vol, fitted weights) plus pooled residual /
        target arrays, so section [1b] can diagnose WHY the windows
        disagree instead of hiding the spread inside a mean ± std."""
        r2s, vrs, rows, res_all, y_all = [], [], [], [], []
        for wi, (os_, oe_) in enumerate(outer_windows, start=1):
            try:
                _, _, bkt_w, reg_w, _, _, _, _, _ = _select_and_fit(
                    rets.iloc[max(0, os_ - purge - lb):os_ - purge],
                    ps, bs)                           # [Fix 39] purge gap
                if max_gross is not None and np.abs(reg_w.coef_).sum() > max_gross:
                    continue
                test, _ = _prepare_evaluation(rets.iloc[os_:oe_])
                r2_w, vr_w = _eval_on_window(reg_w, bkt_w, test)
                if not np.isnan(r2_w):
                    r2s.append(r2_w)
                    vrs.append(vr_w)
                    if detail:
                        y_w = test[target_ticker].values
                        res_w = y_w - reg_w.predict(test[bkt_w].values)
                        rows.append({
                            'window': wi,           # 1 = most recent
                            'start': test.index[0], 'end': test.index[-1],
                            'r2': r2_w, 'vol_red': vr_w,
                            'tgt_vol': float(np.std(y_w) * ann_sqrt),
                            'weights': pd.Series(reg_w.coef_, index=bkt_w)})
                        res_all.append(res_w)
                        y_all.append(y_w)
            except RuntimeError:
                continue
        if not r2s:
            return ((np.nan, np.nan, np.nan, 0, pd.DataFrame(),
                     np.nan, None, None)
                    if detail else (np.nan, np.nan, np.nan, 0))
        out = (float(np.mean(r2s)), float(np.std(r2s)),
               float(np.mean(vrs)), len(r2s))
        if not detail:
            return out
        # [Fix 65] pooled OOS R²: one R² over the CONCATENATED windows.
        # Each per-window R² rests on ~outer_window observations and is a
        # noisy statistic; the pooled figure rests on all of them at once
        # and is the more stable headline of the two.
        y_cat = np.concatenate(y_all[::-1])
        r_cat = np.concatenate(res_all[::-1])
        sst = float(np.sum((y_cat - y_cat.mean()) ** 2))
        pooled = 1.0 - float(np.sum(r_cat ** 2)) / sst if sst > MIN_RETURN_STD ** 2 else np.nan
        # [Fix 70] hand back the pooled arrays so the bootstrap CI can
        # resample the exact series the pooled R² was computed on
        return out + (pd.DataFrame(rows), pooled, y_cat, r_cat)

    def _roll_stats_for(lb, ps, bs, max_windows=None, step=None):
        """[Fix 109] Walk-forward rolling OOS for ANY config, not just the
        selected one.

        The rolling curve was computed inline for the winner only, so the
        [4] ALTERNATIVES table could show a config's average OOS R² but not
        how it BEHAVED through time — which is the number that decides
        whether a challenger is really better. Factored out here so the
        alternatives are judged on the same evidence as the pick.

        Returns dict(te_median, te_worst, te_latest, r2_median, r2_worst,
        r2_latest, r2var_median, n_neg, n_rows) or None.
        """
        _st = max(5, int(step or rolling_refit_every))
        _nw = int(max_windows or rolling_max_windows)
        _ys, _rs = [], []
        for _i in range(_nw, 0, -1):
            _e = len(rets) - (_i - 1) * _st
            _s = _e - _st
            if _s < 0 or _s - purge - lb < 0:
                continue
            try:
                _, _, _bk, _rg, _, _, _, _, _ = _select_and_fit(
                    rets.iloc[_s - purge - lb:_s - purge], ps, bs)
            except RuntimeError:
                continue
            _te_r, _ = _prepare_evaluation(rets.iloc[_s:_e])
            _need = _bk + [target_ticker]
            if not all(c in _te_r.columns and _te_r[c].notna().all()
                       for c in _need):
                continue
            _yv = _te_r[target_ticker].values
            _ys.append(_yv)
            _rs.append(_yv - _rg.predict(_te_r[_bk].values))
        if not _ys:
            return None
        _df = pd.DataFrame({'y': np.concatenate(_ys),
                            'resid': np.concatenate(_rs)})
        _w = 21
        if len(_df) < _w + 1:
            return None
        _sse = _df['resid'].pow(2).rolling(_w).sum()
        _sst = (_df['y'].rolling(_w).var(ddof=0) * _w).where(
            lambda s: s > MIN_RETURN_STD ** 2)
        _r2 = (1.0 - _sse / _sst).dropna()
        _r2v = (1.0 - (_df['resid'].rolling(_w).var(ddof=0) * _w)
                / _sst).dropna()
        _te = (_df['resid'].rolling(_w).std() * ann_sqrt).dropna()
        if not len(_te):
            return None
        return {'te_median': float(_te.median()),
                'te_worst': float(_te.max()),
                'te_latest': float(_te.iloc[-1]),
                'r2_median': float(_r2.median()) if len(_r2) else np.nan,
                'r2_worst': float(_r2.min()) if len(_r2) else np.nan,
                'r2_latest': float(_r2.iloc[-1]) if len(_r2) else np.nan,
                'r2var_median': (float(_r2v.median()) if len(_r2v)
                                 else np.nan),
                'n_neg': int((_r2 < 0).sum()),
                'n_scored': int(len(_r2)),
                'n_rows': int(len(_df))}

    # ── STEP 4: FULL-DATA CV → SELECT LIVE CONFIG ────────────────────────────
    _P('Full-data walk-forward CV — choosing the candidate configuration...')
    summary, cv_df = _walk_forward_cv(rets, verbose=True)
    if summary is None:
        raise RuntimeError(
            'All CV folds failed or no configuration met the requested gross cap. Read the TRAIN/TEST diagnostics above: '
            'missing returns, constant target returns, too few candidates, '
            'or insufficient history are different problems. Reported flat '
            'prices are no longer deleted. Check the cached target column and '
            're-download active-day prices if necessary; do not replace '
            'missing test returns with zero.')
    primary_summary = _family_configs(summary, 'basket') if broad_search else summary
    if primary_summary.empty:
        reason = ('No basket completed every requested CV fold under the data and '
                  'exposure constraints. The fitted basket below is an unvalidated '
                  'reference, not a recommendation. Single instruments cannot replace it.')
        _P('  ' + reason)
        return _short_sample_result('IN-SAMPLE', 0, fallback_reason=reason,
                                    cv_summary=summary, cv_detail=cv_df, prior_nested=nested)
    best = primary_summary.loc[primary_summary['composite'].idxmax()]
    best_lookback = int(best['lookback'])
    best_pc_spec = best['pc_spec']
    best_bsize = int(best['basket_size'])

    # ── STEP 5: FINAL REFIT ON FULL DATA (live weights) ──────────────────────
    try:
        (returns_final, final_rank, basket_final, reg_f,
         r2_final, resid_final, n_pc_final, pca_f, loadings_f) = _select_and_fit(
            rets.iloc[-best_lookback:], best_pc_spec, best_bsize, enforce_gross=False)  # final screen reports cap failure
    except RuntimeError as _e_final:                       # [Fix 81]
        _tail = rets.iloc[-best_lookback:][target_ticker]
        _nan = int(_tail.isna().sum())
        raise ValueError(
            f"[Fix 81] cannot fit the FINAL {best_lookback}d window: "
            f"{_e_final}\n"
            f"  {target_short} has {_nan}/{len(_tail)} missing returns there"
            + (" — inspect those dates in the raw Bloomberg price data. "
               "Missing quotes, inactive days and suspensions need different "
               "handling; re-download active-day data or choose a complete "
               "window. Do not manufacture zero returns."
               if _nan else
               " — the name may have zero variance (limit-locked or "
               "untraded).\n  Try a longer lookback or a different "
               "sample_window."))

    # [Fix 40] if a forced name has bad data in the FINAL window it cannot be
    # held — flag it explicitly rather than let the user assume it is inside
    miss_final = [c for c in forced if c not in basket_final]
    if miss_final:
        _P(f"  ⚠ force_include: {', '.join(miss_final)} could not be held "
              f"in the final basket (incomplete data or zero variance in the "
              f"final {best_lookback}d window)")

    weights_final = pd.Series(reg_f.coef_, index=basket_final)
    te_final = np.std(resid_final) * ann_sqrt
    tgt_std_final = returns_final[target_ticker].std(ddof=0) * ann_sqrt
    vol_red_final = 1 - te_final / tgt_std_final if tgt_std_final > MIN_RETURN_STD else 0.0
    # ── [Fix 121] THE DRIFT THE TICKET NEVER SHOWED ─────────────────────────
    # RidgeCV fits an intercept (nothing in this file passes
    # fit_intercept=False), and reg.predict() subtracts it in EVERY scored
    # window — but the traded recipe is reg_f.coef_ alone, so the desk carries
    # a spread whose expected drift the tool computed and then dropped. TE is a
    # standard deviation, so a constant never shows up in it: the risk figures
    # describe dispersion around a mean that was quietly removed.
    #   Measured (400 seeds, 63-day hold): at a 30%/yr relative drift the
    #   reported 63-day 1σ stayed flat at 8.64% while the realised mean P&L was
    #   6.98% — 0.81σ of omission, growing past 1σ by 45%/yr.
    # The column scaling in _fit_basket divides X only (no centering), so the
    # intercept is already in raw-return space and is directly the daily drift.
    # It is reported, never subtracted and never forecast — see [Fix 111] on
    # what may and may not be done with an estimate that has no persistence.
    drift_ann = float(reg_f.intercept_) * 252.0 / (2 if two_day else 1)
    asym_stats, path_stats = {}, {}     # [Fix 122/123] filled in section [3]
    try:
        # [Fix 39] overlapping 2-day residuals carry induced MA(1)
        # autocorrelation that makes the ADF p-value anti-conservative;
        # test every 2nd (non-overlapping) residual instead
        resid_adf = resid_final[::2] if two_day else resid_final
        adf_p = _adf_pvalue(resid_adf, maxlag=min(20, len(resid_adf) // 5))
    except Exception:
        adf_p = np.nan

    # [Fix 29] single-instrument alternatives chosen by realized hedging
    # power (|corr| with the target in the final window), not by rank_score
    final_single_pool = [c for c in _eligible(returns_final.index[-1])
                         if c in returns_final and (not forced or forced == [c])]
    corr_final = returns_final[final_single_pool].corrwith(returns_final[target_ticker]).dropna()
    best_single = corr_final.abs().idxmax() if len(corr_final) else None
    etf_cands = [c for c in corr_final.index if _is_etf(c)]
    best_etf = corr_final[etf_cands].abs().idxmax() if etf_cands else None
    reg_e = None
    if best_etf is not None:
        reg_e, _, _ = _fit_basket(returns_final, target_ticker, [best_etf])
        if max_gross is not None and np.abs(reg_e.coef_).sum() > max_gross:
            best_etf, reg_e = None, None

    # ── Display names: short name; fall back to full ticker on collision ────
    shorts = pd.Series({c: c.split(' ')[0] for c in returns_final.columns})
    dup = shorts[shorts.duplicated(keep=False)].index
    disp = {c: (c if c in dup else shorts[c]) for c in returns_final.columns}
    if is_portfolio:                                       # [Fix 46]
        disp[target_ticker] = pf_label

    # [Fix 41] shared table renderer for every basket printout: same values
    # as before (ACTION / AMOUNT / name / full ticker), now in a boxed table,
    # plus a ★ marker on force-included names [Fix 40]
    def _basket_rows(weights):
        return [['SHORT' if wgt > 0 else 'LONG',
                 '$' + format(abs(wgt) * 100, '.1f'),
                 disp.get(tk, tk.split(' ')[0]), tk,
                 '★' if tk in forced else '']
                for tk, wgt in weights.sort_values(key=lambda s: -s.abs()).items()]

    BASKET_HEADERS = ['BUY / SELL', 'PER $100', 'NAME', 'FULL TICKER',
                      'PINNED']

    # ── [Fix 65/70/71/72] PRECOMPUTE OOS EVIDENCE ────────────────────────────
    # Used by the trade ticket, the charts and sections [1]/[1b]/[1c] below.
    # Computed once, up here, so the ticket and the diagnostics can never
    # disagree about the same number.
    (sel_r2m, sel_r2s, sel_vrm, sel_n,
     sel_detail, sel_pooled, sel_y, sel_res) = _config_outer_oos(
        best_lookback, best_pc_spec, best_bsize, detail=True)   # [Fix 65]
    n_eff = max(4, int(outer_window / (2 if two_day else 1)))
    wdisp = _window_dispersion_stats(sel_detail, sel_pooled, n_eff)
    boot = selected_boot = None
    if boot_n:
        if sel_y is not None and len(sel_y):
            selected_boot = _block_bootstrap_ci(sel_y, sel_res, n_boot=int(boot_n),
                                                block=(8 if two_day else None), ann=ann_sqrt)
        if np.isfinite(nested_pooled) and len(nested_unseen):
            boot = _block_bootstrap_ci(nested_unseen['target'].values,
                                      nested_unseen['regression_residual'].values,
                                      n_boot=int(boot_n), block=(8 if two_day else None), ann=ann_sqrt)
            if boot:
                boot['source'] = 'nested unseen selection procedure'
        # No selected-config interval substitutes for unavailable nested evidence.
        if selected_boot:
            selected_boot['source'] = 'selected configuration; selection bias remains'
            selected_boot['conditional_on_observed_fits'] = True
        if boot:
            boot['conditional_on_observed_fits'] = True

    # ── [Fix 71] ROLLING OOS CURVE ───────────────────────────────────────────
    # Three outer windows are three noisy readings. This walks the SELECTED
    # config forward: refit weights every `rolling_refit_every` rows on data
    # available at that point, score the NEXT segment out-of-sample, and
    # concatenate the daily OOS residuals into one series — stability becomes
    # a curve you can see instead of three scalars. The CONFIG was chosen on
    # full data, so the row-(3) selection caveat from [1] applies here too;
    # the WEIGHTS, however, never see their scoring segment.
    rolling_df = pd.DataFrame()
    roll_stats, decay_stats, turnover_stats = {}, {}, {}      # [Fix 78]
    if rolling_oos:
        _step = max(5, int(rolling_refit_every))
        _segs_y, _segs_r, _segs_spread, _segs_ix, _n_skip = [], [], [], [], 0
        _dec_map, _bskts = {}, []                             # [Fix 84]
        for _i in range(int(rolling_max_windows), 0, -1):
            _e = len(rets) - (_i - 1) * _step
            _s = _e - _step
            if _s < 0 or _s - purge - best_lookback < 0:
                _n_skip += 1
                continue
            try:
                _, _, _bkt_r, _reg_r, _, _, _, _, _ = _select_and_fit(
                    rets.iloc[_s - purge - best_lookback:_s - purge],
                    best_pc_spec, best_bsize)
            except RuntimeError:
                _n_skip += 1
                continue
            _test_r, _ = _prepare_evaluation(rets.iloc[_s:_e])
            _need = _bkt_r + [target_ticker]
            if not all(c in _test_r.columns and _test_r[c].notna().all()
                       for c in _need):
                _n_skip += 1
                continue
            _y_sr = _test_r[target_ticker].values
            _segs_y.append(_y_sr)
            _segs_r.append(_y_sr - _reg_r.predict(_test_r[_bkt_r].values))
            _segs_spread.append(_y_sr - _test_r[_bkt_r].values @ _reg_r.coef_)
            _segs_ix.append(_test_r.index)
            # [Fix 84] PAIRED staleness measurement. Fixes 78/82, which
            # bucketed residuals by raw row-age: with a fixed refit step,
            # each age bucket always landed on the same calendar offsets
            # (mod step), so the buckets differed by WHICH DAYS they
            # covered as much as by weight age — an abrupt regime break
            # produced a perfectly flat curve. Now every calendar row is
            # scored by SEVERAL vintages of weights (0, 1, 2 refits stale)
            # and only rows carrying all three are compared, so the groups
            # are identical in calendar terms and differ only in staleness.
            # This also states the answer in the trader's own units: what
            # does TE become if I skip a refit?
            _bskts.append((set(_bkt_r),
                           pd.Series(_reg_r.coef_, index=_bkt_r)))
            _H = 3 * _step
            if _s + _H <= len(rets):
                _hz = rets.iloc[_s:_s + _H]
                _okh = _hz[_need].notna().all(axis=1).values
                if _okh.any():
                    _sub = _hz.loc[_okh]
                    _rv = (_sub[target_ticker].values
                           - _reg_r.predict(_sub[_bkt_r].values))
                    _pos = np.arange(_s, _s + _H)[_okh]
                    _ago = (_pos - _s) // _step        # 0 / 1 / 2 refits old
                    for _p, _a, _r1 in zip(_pos, _ago, _rv):
                        _dec_map.setdefault(int(_p), {})[int(_a)] = float(_r1)
        if _segs_y:
            rolling_df = pd.DataFrame(
                {'y': np.concatenate(_segs_y),
                 'resid': np.concatenate(_segs_r),
                 'traded_spread': np.concatenate(_segs_spread)},
                index=pd.DatetimeIndex(
                    np.concatenate([ix.values for ix in _segs_ix])))
            _w_roll = 21
            # ── [Fix 105] WHY ROLLING R² GOES DEEPLY NEGATIVE ──────────────
            # Reported case: an equal-weighted AAPL / TSLA / SK Hynix basket
            # showed rolling R² ≈ -0.4 for one stretch and ≈ +0.8 for the
            # next. That is not a bug, but the old single number could not
            # tell you WHY, and it disagreed with the TE printed beside it.
            #
            # The reason is an asymmetry in the standard R² definition (the
            # one sklearn's .score() uses, so it was consistent across this
            # file, just not self-explanatory):
            #     R² = 1 - Σ(resid)² / Σ(y - ȳ)²
            # The DENOMINATOR removes the window mean from the target. The
            # NUMERATOR does not remove anything from the residual. So if the
            # hedge drifts — the target grinds away from the basket over the
            # window, which is exactly what an idiosyncratic run in one leg
            # does — that drift is charged in full to the numerator and the
            # benchmark it is measured against never pays it. Writing the
            # residual as mean m and standard deviation s:
            #     R² = 1 - (s² + m²)/σ_y²
            # A hedge that HALVES the target's vol (s = 0.5σ_y, a good hedge)
            # but drifts one target-sigma over the window (m = σ_y) scores
            #     R² = 1 - (0.25 + 1.00) = -0.25.
            # Meanwhile TE = s·√252 is computed with .std(), which DOES
            # demean — so the same window prints a perfectly healthy TE. That
            # is the contradiction: R² was measuring level tracking and TE
            # was measuring variance tracking, and both were called "how good
            # is the hedge".
            #
            # Measured on the synthetic reproduction of the reported case, 9
            # of the 13 windows with negative R² had the hedge genuinely
            # CUTTING variance; the negative sign was pure drift.
            #
            # Neither number is wrong — they answer different questions — so
            # both are now computed and both are shown:
            #   r2_roll      unchanged, the strict definition (level + shape)
            #   r2_var_roll  demeaned BOTH sides = pure variance reduction,
            #                the question "did hedging reduce my P&L swing?"
            #   drift_pen    m²·n / Σ(y-ȳ)², the gap between them = the share
            #                of R² lost purely to directional drift
            _resid_r = rolling_df['resid']
            _sse_r = _resid_r.pow(2).rolling(_w_roll).sum()
            _sst_r = rolling_df['y'].rolling(_w_roll).var(ddof=0) * _w_roll
            _sstw = _sst_r.where(_sst_r > 1e-12)
            rolling_df['r2_roll'] = 1.0 - _sse_r / _sstw
            rolling_df['r2_var_roll'] = 1.0 - (
                _resid_r.rolling(_w_roll).var(ddof=0) * _w_roll) / _sstw
            rolling_df['drift_pen'] = (
                _resid_r.rolling(_w_roll).mean().pow(2) * _w_roll) / _sstw
            rolling_df['spread_vol_roll'] = (rolling_df['traded_spread']
                                                    .rolling(_w_roll).std() * ann_sqrt)
            rolling_df['te_roll'] = (_resid_r
                                     .rolling(_w_roll).std() * ann_sqrt)
            rolling_df['tgt_vol_roll'] = (rolling_df['y']
                                          .rolling(_w_roll).std() * ann_sqrt)
            _te_f = rolling_df['te_roll'].dropna()
            _r2_f = rolling_df['r2_roll'].dropna()
            _r2v_f = rolling_df['r2_var_roll'].dropna()
            if len(_te_f):
                _neg = rolling_df.dropna(subset=['r2_roll'])
                _neg = _neg[_neg['r2_roll'] < 0]
                roll_stats = {
                    'n_days': int(len(rolling_df)),
                    'n_segments': len(_segs_y), 'n_skipped': _n_skip,
                    'te_median': float(_te_f.median()),
                    'te_worst': float(_te_f.max()),
                    'te_latest': float(_te_f.iloc[-1]),
                    'r2_median': (float(_r2_f.median())
                                  if len(_r2_f) else np.nan),
                    'r2_worst': (float(_r2_f.min())
                                 if len(_r2_f) else np.nan),
                    'r2_latest': (float(_r2_f.iloc[-1])
                                  if len(_r2_f) else np.nan),
                    # [Fix 105] the variance-only twin and the drift split
                    'r2var_median': (float(_r2v_f.median())
                                     if len(_r2v_f) else np.nan),
                    'r2var_worst': (float(_r2v_f.min())
                                    if len(_r2v_f) else np.nan),
                    'r2var_latest': (float(_r2v_f.iloc[-1])
                                     if len(_r2v_f) else np.nan),
                    'n_neg': int(len(_neg)),
                    'n_scored': int(len(_r2_f)),
                    # of the negative windows, how many still cut variance?
                    'n_neg_but_cut': int((_neg['r2_var_roll'] > 0).sum())
                    if len(_neg) else 0,
                    'drift_median': (float(rolling_df['drift_pen']
                                           .dropna().median())
                                     if rolling_df['drift_pen'].notna().any()
                                     else np.nan)}
        # [Fix 78] TE by weight age → recommended rebalance cadence. Each
        # refit's weights are scored on the NEXT 1..63 rows; pooling the
        # residuals by age answers "how fast do fitted weights go stale?".
        # The recommended cadence is the longest age bucket whose TE is
        # still within 15% of fresh-weight TE. Ages are rows (≈ trading
        # days; 2-day overlapping rows in cross-tz mode).
        # [Fix 84] compare vintages on the SAME calendar rows
        _common = sorted(p for p, d in _dec_map.items() if len(d) == 3)
        if len(_common) >= 30:
            _te_ago = []
            for _a in range(3):
                _v = np.array([_dec_map[p][_a] for p in _common])
                _te_ago.append(((_a + 1) * _step,
                                float(np.std(_v) * ann_sqrt)))
            _fresh = _te_ago[0][1]
            _rec = _te_ago[0][0]
            for _iv, _te in _te_ago[1:]:
                if _te <= 1.15 * _fresh:
                    _rec = _iv
                else:
                    break
            decay_stats = {'te_by_interval': _te_ago, 'fresh_te': _fresh,
                           'rec_rows': _rec, 'n_rows': len(_common)}
        if len(_bskts) >= 2:                                  # [Fix 78]
            _js, _cs = [], []
            for (_sa, _wa), (_sb, _wb) in zip(_bskts[:-1], _bskts[1:]):
                _js.append(len(_sa & _sb) / max(1, len(_sa | _sb)))
                _names = sorted(_sa | _sb)
                _va = _wa.reindex(_names).fillna(0.0).values
                _vb = _wb.reindex(_names).fillna(0.0).values
                _na, _nb = np.linalg.norm(_va), np.linalg.norm(_vb)
                if _na > 1e-12 and _nb > 1e-12:
                    _cs.append(float(_va.dot(_vb) / (_na * _nb)))
            turnover_stats = {'mean_jaccard': float(np.mean(_js)),
                              'mean_cosine': (float(np.mean(_cs))
                                              if _cs else np.nan),
                              'n_refits': len(_bskts)}

    # ── [Fix 72] TICKET INPUTS + VERDICT ─────────────────────────────────────
    # The primary verdict uses nested evidence only. Selected-config evidence
    # is a separate diagnostic; it cannot substitute for a failed nested test.
    if not np.isnan(nested_pooled):
        _quality, _quality_src = nested_pooled, 'nested pooled — honest'
    else:
        _quality, _quality_src = np.nan, 'nested validation unavailable'
    _ref_pca_t = nested_r2_mean
    _simple_pool = [float(b['r2_oos'].mean()) for b in (etf_bench, name_bench)
                    if len(b) and set(b['window']) == set(nested_valid['window'])]
    _ref_simple_t = max(_simple_pool) if _simple_pool else np.nan
    _overfit_gap = ((r2_final - _quality)
                    if not np.isnan(_quality) else np.nan)
    kill_te = (1.5 * wdisp['worst_te']
               if np.isfinite(wdisp['worst_te']) else np.nan)
    _roll_breach = bool(roll_stats and np.isfinite(kill_te)
                        and roll_stats['te_latest'] > kill_te)
    # ── [Fix 93/97] NOW-CAST — "I need to hedge NOW; is it working lately?"
    # The pooled numbers say how the hedge has behaved ON AVERAGE. This asks
    # about the present. But reacting to "the latest reading" is itself a
    # bias: one window carries only ~outer_window observations and scatters
    # widely, so a threshold on the newest point cries wolf on hedges that
    # are perfectly fine. Measured on stable synthetic hedges, the [Fix 93]
    # rule (latest TE > 1.25x its median, or ANY single signal) downgraded
    # 17% of them — one good hedge in six, for nothing.
    #
    # [Fix 97] makes it evidence-weighted instead:
    #   · judge a BLOCK of recent readings (the last ~horizon rows), not one
    #     point, so a single noisy day cannot move the verdict;
    #   · score that block against the hedge's OWN historical distribution
    #     of the same statistic (an empirical percentile), instead of an
    #     arbitrary ratio — "unusual for this hedge", not "above 1.25";
    #   · require PERSISTENCE (most of the block elevated), and either two
    #     independent signals or one extreme (>=95th pct) one;
    #   · it can only ever LOWER a tick from ✓ to △, never raise a grade,
    #     and it never replaces the pooled evidence.
    nowcast = {}
    if roll_stats or (sel_n and len(sel_detail)):
        _sig, _why = [], []
        # signal 1 — recent block of rolling TE vs its own history
        _pct = _persist = np.nan
        _blk = np.nan
        if len(rolling_df) and rolling_df['te_roll'].notna().sum() >= 12:
            _te_s = rolling_df['te_roll'].dropna()
            _k = int(min(max(10, outer_window), max(5, len(_te_s) // 3)))
            _recent, _hist = _te_s.iloc[-_k:], _te_s.iloc[:-_k]
            if len(_hist) >= 8:
                _blk = float(_recent.median())
                _pct = float((_hist <= _blk).mean())
                _persist = float((_recent > _hist.median()).mean())
                if _pct >= 0.85 and _persist >= 0.6:
                    _sig.append('te_block')
                    _why.append(
                        f"recent tracking error sits in the top "
                        f"{100*(1-_pct):.0f}% of this hedge's own history "
                        f"({_blk*100:.1f}%/yr) and stays there")
        # signal 2 — newest unseen window below the sampling-noise band
        _lw_r2 = _lw_flag = None
        if sel_n and len(sel_detail):
            _lw_r2 = float(sel_detail.iloc[0]['r2'])       # window 1 = latest
            _lw_flag = wdisp['flags'][0] if wdisp['flags'] else ''
            if _lw_flag == 'negative':
                _sig.append('window')
                _why.append(f"newest unseen window R² {_lw_r2:.2f} is negative")
        # signal 3 — monotone deterioration toward the present
        if wdisp['trend']:
            _sig.append('trend')
            _why.append('R² has deteriorated steadily toward the present')
        # Heuristic condition flag: two possibly related signals, or an extreme TE block.
        _strong = (np.isfinite(_pct) and _pct >= 0.95 and _persist >= 0.6)
        if len(_sig) >= 2 or _strong:
            _cond = 'DEGRADED'
        elif (np.isfinite(_pct) and _pct <= 0.40 and not _sig):
            _cond = 'GOOD'
        else:
            _cond = 'NORMAL'
            if _sig:                       # one weak signal: note, don't act
                _why = [w + " (single signal — not acted on)" for w in _why]
        # sizing reference: the more conservative of the worst validated
        # window and current conditions — conservative by construction,
        # NOT "the latest reading is the truth"
        _te_now = max([x for x in (
            (_blk if np.isfinite(_blk) else None),
            (wdisp['worst_te'] if np.isfinite(wdisp['worst_te']) else None))
            if x is not None] or [np.nan])
        nowcast = {'condition': _cond, 'why': _why, 'signals': _sig,
                   'latest_window_r2': _lw_r2, 'latest_flag': _lw_flag,
                   'te_block': (float(_blk) if np.isfinite(_blk) else np.nan),
                   'te_pctile': (float(_pct) if np.isfinite(_pct) else np.nan),
                   'persistence': (float(_persist) if np.isfinite(_persist)
                                   else np.nan),
                   'sizing_te_now': _te_now}
    grade, reasons = _ticket_verdict(
        _quality, nested_disp['worst_r2'], _overfit_gap, nested_disp['min_sim'],
        nested_disp['trend'], _ref_pca_t, _ref_simple_t, _roll_breach,
        vol_red=trade_risk.get('vol_reduction'),
        worst_vol_red=(float(nested_valid['vol_red_oos'].min())
                       if len(nested_valid) else np.nan),
        objective=hedge_objective,
        ref_vol_pca=nested_vr_mean,
        ref_vol_simple=max(
            [float(b['vol_red_oos'].mean()) for b in (etf_bench, name_bench)
             if len(b) and set(b['window']) == set(nested_valid['window'])]
            or [np.nan]))
    if np.isfinite(_quality) and _quality < 0:
        grade = '✗ NO VALIDATED HEDGE'
        reasons.insert(0, 'negative unseen tracking R²; candidate retained for reference only')
    if max_gross is not None and weights_final.abs().sum() > max_gross:
        grade = '✗ NO VALIDATED HEDGE'
        reasons.insert(0, 'final fitted weights exceed the requested gross exposure cap')
    if trade_risk.get('vol_reduction', np.nan) <= 0:
        grade = '✗ DO NOT TRADE AS-IS'
        reasons.insert(0, 'coefficient-only nested unseen spread did not reduce '
                       'volatility relative to the unhedged target')
    if len(nested_valid) < outer_folds and str(grade).startswith(('✓', '△')):
        grade = '? INSUFFICIENT OOS EVIDENCE'
        reasons.insert(0, f'only {len(nested_valid)}/{outer_folds} nested unseen '
                       'windows could be scored; this is partial evidence')
    if evaluation_diagnostics:
        reasons.append('validation is conditional on observed target returns; '
                       'missing dates and coverage are listed in the data diagnostics')
    if nowcast.get('condition') == 'DEGRADED':            # [Fix 93]
        if grade.startswith('✓'):
            grade = '△ RECENT DETERIORATION — REVIEW CANDIDATE'
        for _w93 in nowcast['why']:
            if _w93 not in reasons:
                reasons.append(_w93)

    # ── [Fix 91/92] HORIZON — risk stated over the holding period ───────────
    horizon_info = {}
    if hedge_horizon_days:
        _h = int(hedge_horizon_days)
        _te_src = (nowcast.get('sizing_te_now')
                   if nowcast and np.isfinite(nowcast.get('sizing_te_now',
                                                          np.nan))
                   else (wdisp['worst_te'] if np.isfinite(wdisp['worst_te'])
                         else te_final))
        _res_src = (sel_res if sel_res is not None and len(sel_res)
                    else resid_final)
        _sig_h, _vr = _horizon_sigma(_res_src, _h, float(_te_src), two_day)
        _refits = (int(np.ceil(_h / decay_stats['rec_rows'])) - 1
                   if decay_stats else None)
        # [Fix 98] What did a hold of THIS length actually deliver? Split
        # the walk-forward OOS residuals into consecutive NON-OVERLAPPING
        # blocks of the horizon and report the realized spread. This is the
        # direct answer to "make it best over my 3-month horizon": it is the
        # empirical distribution of 3-month outcomes, not an annualized
        # abstraction, and it is what the config search was scored on.
        _blocks = None
        if len(rolling_df) >= 2 * _h:
            _res_b = rolling_df['resid'].values
            _y_b = rolling_df['y'].values
            _nb = len(_res_b) // _h
            _tes, _helped = [], 0
            for _i98 in range(_nb):
                _sl = slice(_i98 * _h, (_i98 + 1) * _h)
                _rt = float(np.std(_res_b[_sl]) * ann_sqrt)
                _yt = float(np.std(_y_b[_sl]) * ann_sqrt)
                _tes.append(_rt)
                if _yt > 1e-9 and _rt < _yt:
                    _helped += 1
            if _nb >= 2:
                _blocks = {'n': _nb, 'te_median': float(np.median(_tes)),
                           'te_worst': float(np.max(_tes)),
                           'te_best': float(np.min(_tes)),
                           'share_helped': _helped / _nb}
        horizon_info = {'days': _h, 'sigma_pct': float(_sig_h),
                        'vr': _vr, 'te_source': float(_te_src),
                        'refits_needed': _refits, 'blocks': _blocks}
    ticket_info = {'grade': grade, 'reasons': reasons,
                   'trade_eligible': _decision_fields(weights_final, grade)['trade_eligible'],
                   'trade_risk': trade_risk,
                   'hedge_objective': hedge_objective,
                   'quality_r2': _quality, 'quality_source': _quality_src,
                   'worst_window_r2': nested_disp['worst_r2'],
                   'worst_window_te': nested_disp['worst_te'],
                   'worst_window_source': 'nested selection procedure',
                   'selected_config_worst_window_r2': wdisp['worst_r2'],
                   'selected_config_worst_window_te': wdisp['worst_te'],
                   'kill_switch_te': kill_te,
                   'overfit_gap': _overfit_gap,
                   'rebalance_rows': decay_stats.get('rec_rows'),  # [Fix 78]
                   'nowcast': nowcast,                    # [Fix 93]
                   'horizon': horizon_info}               # [Fix 91]

    # ── STEP 6: CHARTS ───────────────────────────────────────────────────────
    # [Fix 117] Charts lead the output, as they always did. [Fix 115] moved them
    # below the report on the theory that the verdict should come first; that
    # was wrong for how this is actually used — the pictures are what you scan
    # to decide whether the ticket below is worth reading. They keep the
    # [Fix 115] restyling (report type scale, readable date ticks) and lose the
    # relocation.
    def _draw_charts():
        if not show_plots or report == 'compact':
            return
        _CLR = {'tgt': '#c0392b', 'hedged': '#1b6b3a', 'pick': '#1f3f66',
                'other': '#9fb3c8', 'warn': '#b7791f', 'kill': '#8c1c1c'}
        _rc = {'font.size': 9, 'axes.titlesize': 11, 'axes.titleweight': 'bold',
               'axes.labelsize': 9, 'axes.labelcolor': _RF_MUTE,
               'axes.edgecolor': '#c8d2dd', 'axes.titlecolor': _RF_HEAD,
               'axes.grid': True, 'grid.color': '#eef1f5',
               'grid.linewidth': .8, 'axes.axisbelow': True,
               'xtick.color': _RF_MUTE, 'ytick.color': _RF_MUTE,
               'xtick.labelsize': 8, 'ytick.labelsize': 8,
               'legend.fontsize': 8, 'legend.frameon': False,
               'figure.facecolor': 'white', 'axes.spines.top': False,
               'axes.spines.right': False, 'lines.linewidth': 1.4}
        with plt.rc_context(_supported_plot_style(_rc)):
            fig, axes = plt.subplots(2, 3, figsize=(16, 8.5))
            chart_pca, chart_loadings, chart_npc = pca_f, loadings_f, n_pc_final
            if chart_pca is None:
                ctx = _training_context(rets.iloc[-best_lookback:], min_train_rows)
                _, chart_npc, chart_pca, chart_loadings = _context_pca(ctx, 'auto')
            ev = chart_pca.explained_variance_ratio_
            axes[0, 0].bar(range(1, chart_npc + 1), ev * 100,
                           color=_CLR['pick'], alpha=.75)
            axes[0, 0].plot(range(1, chart_npc + 1), np.cumsum(ev) * 100,
                            'o-', color=_CLR['tgt'], ms=4)
            axes[0, 0].set_title(f'Scree (descriptive) — {chart_npc} PCs, '
                                 f'{np.sum(ev)*100:.0f}% of variance')
            axes[0, 0].set_xlabel('principal component')
            axes[0, 0].set_ylabel('% of variance')
            # [Fix 62] label only what matters. Annotating every name is
            # unreadable past ~100 candidates: the target, the basket and the 30
            # best-ranked candidates carry all the information anyone reads this
            # panel for; the rest stay as unlabelled dots.
            lab = set(basket_final) | {target_ticker} | set(final_rank.index[:30])
            for tk in chart_loadings.index:
                c = (_CLR['tgt'] if tk == target_ticker
                     else (_CLR['hedged'] if tk in basket_final
                           else _CLR['other']))
                s = 130 if tk == target_ticker else 34
                axes[0, 1].scatter(chart_loadings.loc[tk, 'PC1'],
                                   chart_loadings.loc[tk, 'PC2'], c=c, s=s,
                                   edgecolors='white', linewidths=.5, zorder=3)
                if tk in lab:
                    axes[0, 1].annotate(disp[tk],
                                        (chart_loadings.loc[tk, 'PC1'],
                                         chart_loadings.loc[tk, 'PC2']),
                                        fontsize=6.5, color=_RF_MUTE,
                                        xytext=(3, 3),
                                        textcoords='offset points')
            axes[0, 1].set_title('PC1 vs PC2 — red = target, green = basket')
            axes[0, 1].set_xlabel('PC1'); axes[0, 1].set_ylabel('PC2')
            corrs = (returns_final.corr()[target_ticker].drop(target_ticker)
                     .sort_values(ascending=False).head(10))
            colors = [_CLR['hedged'] if t in basket_final else _CLR['other']
                      for t in corrs.index]
            axes[0, 2].barh(range(len(corrs)), corrs.values, color=colors)
            axes[0, 2].invert_yaxis()
            axes[0, 2].set_yticks(range(len(corrs)))
            axes[0, 2].set_yticklabels([disp[t] for t in corrs.index],
                                       fontsize=7.5)
            axes[0, 2].set_title(f'Top correlations with {target_short} '
                                 f'— green = in the basket')
            axes[0, 2].set_xlabel('correlation')
            spread = pd.Series(
                returns_final[target_ticker].values
                - returns_final[basket_final].values @ reg_f.coef_,
                index=returns_final.index)
            # Two-day returns overlap. Use the same non-overlapping phase for both paths.
            _path_target = returns_final[target_ticker].iloc[::2] if two_day else returns_final[target_ticker]
            _path_spread = spread.iloc[::2] if two_day else spread
            axes[1, 0].plot(np.expm1(_path_target.cumsum()) * 100,
                            color=_CLR['tgt'], label='unhedged')
            axes[1, 0].plot(np.expm1(_path_spread.cumsum()) * 100,
                            color=_CLR['hedged'], label='hedged')
            axes[1, 0].axhline(0, color='#b0bcc8', ls='--', lw=.9)
            axes[1, 0].legend(); axes[1, 0].set_ylabel('%')
            axes[1, 0].set_title('Cumulative log-spread proxy — fitted, non-overlapping')
            w = 20
            axes[1, 1].plot(returns_final[target_ticker].rolling(w).std()
                            * ann_sqrt * 100, color=_CLR['tgt'],
                            label='unhedged')
            axes[1, 1].plot(spread.rolling(w).std() * ann_sqrt * 100,
                            color=_CLR['hedged'], label='hedged')
            axes[1, 1].legend(); axes[1, 1].set_ylabel('%/yr')
            axes[1, 1].set_title(f'Rolling {w}-obs annualized vol %')
            for lb in summary['lookback'].unique():
                sub = (summary[summary['lookback'] == lb]
                       .groupby('basket_size')['avg_r2_oos'].mean())
                axes[1, 2].plot(sub.index, sub.values, 'o-', ms=4,
                                label=f'lookback {int(lb)}d')
            axes[1, 2].set_xlabel('basket size')
            axes[1, 2].set_ylabel('Mean CV R²')
            axes[1, 2].legend()
            axes[1, 2].set_title('Basket-size sensitivity — selected CV configurations')
            # date axes: matplotlib's default tick density overlapped the
            # labels into an unreadable smear on the two time-series panels
            for _ax in (axes[1, 0], axes[1, 1]):
                _ax.xaxis.set_major_locator(_mdates.AutoDateLocator(maxticks=7))
                _ax.xaxis.set_major_formatter(_mdates.DateFormatter('%b %y'))
            for _axis in axes.flat:
                _axis.title.set_color(_RF_HEAD)
                _axis.spines['top'].set_visible(False)
                _axis.spines['right'].set_visible(False)
            fig.tight_layout(pad=1.6)
            plt.show()
            # [Fix 71] rolling OOS curve — TE panel with the kill-switch line,
            # R² panel with the pooled level
            if len(rolling_df) and rolling_df['te_roll'].notna().any():
                fig2, ax2 = plt.subplots(2, 1, figsize=(13, 6), sharex=True)
                ax2[0].plot(rolling_df.index, rolling_df['te_roll'] * 100,
                            color=_CLR['hedged'])
                if np.isfinite(wdisp['worst_te']):
                    ax2[0].axhline(wdisp['worst_te'] * 100, color=_CLR['warn'],
                                   ls='--', label='selected-config worst window')
                    ax2[0].axhline(1.5 * wdisp['worst_te'] * 100,
                                   color=_CLR['kill'], ls='--',
                                   label='monitoring threshold (1.5×)' )
                    # headroom + an opaque box, or the legend sits on top of
                    # the kill-switch line it is labelling
                    ax2[0].margins(y=.22)
                    ax2[0].legend(loc='lower left', frameon=True,
                                  facecolor='white', edgecolor='#dfe4ea',
                                  framealpha=.95)
                ax2[0].set_ylabel('%/yr')
                ax2[0].set_title('Selected-config rolling tracking error — heuristic threshold')
                ax2[1].plot(rolling_df.index,
                            rolling_df['r2_roll'],
                            color=_CLR['pick'])
                if not np.isnan(sel_pooled):
                    ax2[1].axhline(sel_pooled, color='#8a97a6', ls='--',
                                   label='selected-config pooled R²')
                    ax2[1].legend(loc='lower left')
                ax2[1].set_title('Rolling 21-row OOS R² (negative values retained)')
                ax2[1].xaxis.set_major_locator(
                    _mdates.AutoDateLocator(maxticks=9))
                ax2[1].xaxis.set_major_formatter(
                    _mdates.DateFormatter('%b %y'))
                for _axis in ax2:
                    _axis.title.set_color(_RF_HEAD)
                    _axis.spines['top'].set_visible(False)
                    _axis.spines['right'].set_visible(False)
                fig2.tight_layout(pad=1.4)
                plt.show()

    _draw_charts()                                          # [Fix 117] up top

    # ── STEP 7: REPORT [Fix 79] ─────────────────────────────────────────────
    # One visual grammar: banner → [0] TICKET → [1] VALIDATION →
    # [2] COMPARISON → [3] DIAGNOSTICS → [4] ALTERNATIVES → [A] APPENDIX.
    # Sections are ordered by decision relevance; every diagnostic ends in a
    # one-line "►" takeaway. report='compact' (default) keeps every number
    # that changes the trade; report='full' adds the long-form explanations
    # and per-config weight tables.
    full_rep = (str(report).lower() == 'full')
    L = 78
    def hr(c='─'):
        _kv_flush()
        if not _IN_JUPYTER:
            _P(' ' + c * (L - 2))
    # [Fix 104] title/kv/print now route through the shared renderers. kv()
    # BUFFERS into the current block so a run of kv() calls comes out as ONE
    # table instead of 20 loose prints; _section/_print_table/_P flush it.
    # NOTE: `print` is NOT rebound here — find_best_hedge prints from the CV
    # and nested-validation loops long before this point, and a local rebind
    # would make every one of those an UnboundLocalError. The report body's
    # own print() call sites are written as _P() instead.
    title = _section
    def kv(label, value, implication=''):
        _KVCTX['rows'].append((label, value, implication))
    kvo = _kv_open

    title(f"PCA HEDGE — {target_short}"
          + ("  ·  RE-HEDGE" if _rehedge_of else '')
          + f"   ·   {datetime.now():%Y-%m-%d %H:%M}")
    if _rehedge_of:                                        # [Fix 115]
        _pp = _rehedge_of.get('params') or {}
        _P(f"  ► RE-HEDGE: weights refit on today's data using the config "
           f"already validated by the last full run "
           f"(lookback {_pp.get('lookback')}d · PCs {_pp.get('pc_spec')} · "
           f"basket {_pp.get('basket_size')}). The config was NOT re-searched.")
        _P(f"  the validation below re-runs on {outer_folds} outer window"
           f"{'s' if outer_folds != 1 else ''} rather than the full 3 — it is "
           f"a sanity check on the refit, not a fresh validation. The "
           f"config's credentials come from the run it inherits from. Press "
           f"RUN HEDGE (or pass full_validation=True) for the full protocol.")
    _P(f"  Objective: {hedge_objective} · {val_mode} validation · {len(universe)} names considered · "
          f"{len(rets)} days of history "
          f"({rets.index[0]:%d %b %Y} → {rets.index[-1]:%d %b %Y})"
          + ("  ·  returns paired over 2 days because the markets close at "
             "different times" if two_day else ""))
    if sample_window is not None:                          # [Fix 99]
        _P(f"  period locked: every number below uses ONLY "
              f"{rets.index[0]:%d %b %Y} → {rets.index[-1]:%d %b %Y}. "
              f"Nothing outside it is fitted on, chosen on or scored on.")
    if hedge_horizon_days:                             # [Fix 91/100]
        _P(f"  you plan to hold this for {int(hedge_horizon_days)} trading "
              f"days, so risk is quoted over that period and [0] shows what "
              f"holds of that length actually delivered")
    if forced:
        _P(f"  names you pinned into every basket (★): "
              f"{', '.join(disp.get(c, c) for c in forced)}")

    # ── [0] TICKET ──────────────────────────────────────────────────────────
    # [Fix 116] PLAIN ENGLISH FIRST. Every label in this report used to be the
    # NAME OF A STATISTIC — 'Evidence', 'Exposure', 'Nested pooled OOS R²'. A
    # reader who does not already know the method cannot decode any of those,
    # and this section is the one everybody reads. Labels are now written as
    # two lines: what the row TELLS you, then the technical term underneath in
    # small type for anyone who wants it. Nothing computed changed — only the
    # words the numbers are filed under.
    title("[0] TICKET", "candidate hedge and historical evidence")
    _sub = ''
    if not np.isnan(ticket_info['quality_r2']):
        # [Fix 86] plain English: R² is "share of the target's moves the
        # hedge tracks", vol reduction is the risk actually removed.
        _sub = (f"return-tracking OOS R² {ticket_info['quality_r2']:.3f}")
        _nested_vr = trade_risk.get('vol_reduction', np.nan)
        if np.isfinite(_nested_vr):
            _sub += f", nested volatility reduction {_nested_vr*100:.1f}%"
    # ── [Fix 117] THE TICKET, DE-DUPLICATED ────────────────────────────────
    # Measured on the previous build's own output: 73% appeared 7 times, 72%
    # five times, and 21.5% / 18.5% / 32.2% / 17.4% three times each — inside
    # ONE section. Three blocks were restating each other:
    #   QUALITY          repeated the verdict banner's subtitle verbatim, and
    #                    [1]'s headline row.
    #   AT A n-DAY HOLD  restated four rows that HOW TO RUN IT had already
    #                    printed two rows above, plus one from [3].
    #   THE POSITION     quoted the in-sample TE that SIZING then quoted again
    #                    as its "best case" comparison.
    # Both redundant blocks are gone. What is left is two blocks with no
    # overlap at all: WHAT YOU ARE PUTTING ON, then HOW TO RUN IT. Every
    # number in the ticket now appears exactly once, which is the only way the
    # eye can find the one it came for.
    #
    # Vocabulary: standard desk terms (R², TE, gross/net, OOS, bp) are used
    # plainly as labels — a trader reads them faster than any paraphrase. The
    # second, smaller label line is reserved for the things that are specific
    # to THIS tool and genuinely need saying: which window a number came from,
    # what "condition" means, what the stop is measured on.
    _verdict_banner(grade, reasons, _sub)                     # [Fix 87]
    if trade_risk.get('n_observations'):
        _P(f"  Actual coefficient-only nested unseen spread: volatility "
           f"{trade_risk['unhedged_vol_ann']*100:.1f}% → "
           f"{trade_risk['hedged_vol_ann']*100:.1f}%/yr; "
           f"{trade_risk['vol_reduction']*100:.1f}% volatility reduction "
           f"versus the unhedged baseline (0% reduction). No intercept is "
           f"traded; costs are excluded.")
    _P(f"  {'CANDIDATE RECIPE — NOT APPROVED' if not str(grade).startswith(('✓', '△')) else 'CANDIDATE RECIPE'} — per $100 of "
          f"{'gross book' if is_portfolio else 'long ' + target_short}"
          + (f", and on the ${notional_mm:g}mm entered" if notional_mm else ""))
    _t_head = ['SIDE', '$/100', 'NAME', 'FULL TICKER', '★']
    if notional_mm:
        _t_head.insert(2, '≈$MM')
    _t_rows = []
    for _tk, _wgt in weights_final.sort_values(key=lambda s: -s.abs()).items():
        _row = ['SHORT' if _wgt > 0 else 'LONG',
                '$' + format(abs(_wgt) * 100, '.1f'),
                disp.get(_tk, _tk.split(' ')[0]), _tk,
                '★' if _tk in forced else '']
        if notional_mm:
            _row.insert(2, '$' + format(abs(_wgt) * notional_mm, ',.2f'))
        _t_rows.append(_row)
    _print_table(_t_head, _t_rows)
    _net = weights_final.sum() * 100
    _te_bp = te_final * 1e4 / np.sqrt(252)
    _gross = weights_final.abs().sum() * 100

    # ── what you are putting on ────────────────────────────────────────────
    kvo('WHAT YOU ARE PUTTING ON')
    kv('Gross / net',
       f"${_gross:.1f} gross · ${abs(_net):.1f} net "
       f"{'short' if _net >= 0 else 'long'} per $100",
       (f"Above $200 gross usually means the ridge paired off near-duplicate "
        f"names rather than hedging real risk — see [4] for a cheaper config."
        if _gross > 200 else
        f"A normal single-layer hedge. Borrow and financing scale with gross "
        f"and are NOT priced here."))
    _qbits = []
    if not np.isnan(ticket_info['quality_r2']):
        _qbits.append(f"{ticket_info['quality_r2']:.2f} pooled")
    if boot:
        _qbits.append(f"CI {boot['r2_lo']:.2f}–{boot['r2_hi']:.2f}")
    if not np.isnan(nested_disp['worst_r2']):
        _qbits.append(f"{nested_disp['worst_r2']:.2f} worst nested window")
    if _qbits:
        kv('OOS R²\nnested pooled — the honest one', ' · '.join(_qbits),
           'Judge the hedge on the worst window, not the pooled average. '
           'Full breakdown in [1].')
    kv('Vol cut\nIN-SAMPLE — descriptive',
       f"{tgt_std_final*100:.1f}% → {te_final*100:.1f}%/yr · "
       f"{vol_red_final*100:.0f}% cut · {_te_bp:.0f} bp/day",
       'Fitted and scored on the same rows. Describes this history; it does '
       'not establish future performance or an upper bound on hedge quality.')

    # ── how to run it ──────────────────────────────────────────────────────
    kvo('RISK AND MONITORING REFERENCES', note='Selected-configuration diagnostics; '
        'these readings do not override the nested validation verdict.')
    if np.isfinite(wdisp['worst_te']):
        kv('RISK REFERENCE\nworst selected-config window TE',
           f"{wdisp['worst_te']*100:.1f}%/yr",
           f"Not the {te_final*100:.1f}% in-sample figure above. This is what "
           f"the hedge did when it was working hardest, and it is what you "
           f"have to survive.")
    if notional_mm:                                           # [Fix 86]
        # dollarize the risk: a %/yr tracking error means little at the desk
        # until it is the 1-sigma P&L swing on the actual ticket size.
        _te_use = (wdisp['worst_te'] if np.isfinite(wdisp['worst_te'])
                   else te_final)
        _rl = (f"±{_fmt_money_mm(_te_use*notional_mm)}/yr · "
               f"±{_fmt_money_mm(_te_use*notional_mm/np.sqrt(252))}/day")
        if horizon_info:
            _rl += (f" · ±{_fmt_money_mm(horizon_info['sigma_pct']*notional_mm)}"
                    f" over the {horizon_info['days']}d hold "
                    f"(±{horizon_info['sigma_pct']*100:.1f}%)")
        kv('RISK ($)\n1σ residual P&L, priced off the worst window', _rl,
           f"On ${notional_mm:g}mm gross. These are dispersion estimates, not "
           f"guaranteed coverage or loss limits. [Fix 121] These "
           f"are dispersion around the hedge's own drift ({drift_ann*100:+.1f}"
           f"%/yr, see [3]), not around zero.")
    elif horizon_info:
        kv(f"RISK over the {horizon_info['days']}d hold\n1σ residual",
           f"±{horizon_info['sigma_pct']*100:.2f}%",
           'Historical dispersion estimate; financial returns need not obey '
           'Gaussian coverage rules. This is not a guaranteed loss limit.')
    if nowcast:                                        # [Fix 93/97]
        _nc = nowcast['condition']
        # [Fix 115] '·' is the separator the renderer splits readings on, so a
        # '·' used as a status glyph came out as a fact of its own.
        _mark = {'GOOD': '✓', 'NORMAL': '•', 'DEGRADED': '⚠'}[_nc]
        _bits = []
        if np.isfinite(nowcast.get('te_pctile', np.nan)):
            _bits.append(f"TE {nowcast['te_block']*100:.1f}%/yr "
                         f"({_ordinal(nowcast['te_pctile']*100)} pctile of its "
                         f"own history)")
        if nowcast.get('latest_window_r2') is not None:
            _bits.append(f"newest window R² "
                         f"{nowcast['latest_window_r2']:.2f}"
                         + (f" ({nowcast['latest_flag']})"
                            if nowcast.get('latest_flag') else ''))
        kv('CONDITION NOW\nlatest readings vs this hedge’s own history',
           f"{_mark} {_nc} · " + ' · '.join(_bits),
           ('Selected-config tracking error is low relative to its own history.'
            if _nc == 'GOOD' else
            ('Selected-config tracking error is within its usual range.'
             if _nc == 'NORMAL' else
             'Selected-config tracking error has worsened relative to its own history.'))
           + (' The hedge failed validation; this condition is not a recommendation.'
              if not ticket_info['trade_eligible'] else
              ' This descriptive condition does not establish future hedge quality.'))
    if horizon_info and horizon_info.get('blocks'):        # [Fix 98]
        _hb = horizon_info['blocks']
        kv(f"{horizon_info['days']}-DAY HOLDS\nthe only evidence on your "
           f"actual horizon",
           f"{_hb['n']} holds · TE {_hb['te_median']*100:.1f}% median / "
           f"{_hb['te_worst']*100:.1f}% worst · cut risk in "
           f"{_hb['share_helped']*100:.0f}%",
           ('Below ~70% means the hedge is a coin-flip over a hold this long.'
            if _hb['share_helped'] < 0.7 else
            'Plan for the worst of those, not the median.'))
    if horizon_info and np.isfinite(horizon_info['vr']):
        _hh = horizon_info
        if _hh['vr'] > 1.15:
            kv('  horizon risk is padded\n  residuals trended',
               f"×{np.sqrt(_hh['vr']):.2f}",
               'A daily figure would understate a hold this long. The uplift '
               'is already in the RISK row. Treat it as a floor.')
        elif _hh['vr'] < 0.85:
            kv('  no discount taken\n  residuals mean-reverted',
               f"×{np.sqrt(_hh['vr']):.2f} available",
               'Would justify a smaller RISK number. Deliberately not taken — '
               'the effect does not repeat reliably enough to size on.')
    if np.isfinite(kill_te):
        _mon = f"kill at {kill_te*100:.1f}%/yr"
        if roll_stats:
            _mon += (f" · {roll_stats['te_latest']*100:.1f}% now"
                     + (' ⚠ ABOVE' if _roll_breach else ' ✓'))
        if decay_stats:
            _mon += f" · refit every {decay_stats['rec_rows']} rows"
        if horizon_info and horizon_info.get('refits_needed'):
            _mon += f" · ~{horizon_info['refits_needed']} refit(s) inside the hold"
        kv('STOP / REFIT\nrolling 21-row TE vs the kill level', _mon,
           (f"Above {kill_te*100:.1f}%/yr the hedge is no longer doing what it "
            f"was validated to do — refit or cut."
            + (' It is ALREADY above: do not add risk today.'
               if _roll_breach else '')
            + (f" Separately, refit every ~{decay_stats['rec_rows']} rows — "
               f"past that the weights decay faster than a refit costs."
               if decay_stats else '')))
    # [Fix 117] the horizon block that used to sit here restated four rows
    # printed immediately above it. Its one real contribution was telling you
    # WHICH of them dominates at your holding period — that is one line, not a
    # table.
    if hedge_horizon_days:
        _P(f'  Holding-period dispersion reference: {int(hedge_horizon_days)} trading days. '
           'It does not change the historical analysis window or override validation.')

    # ── [1] VALIDATION ──────────────────────────────────────────────────────
    title("[1] VALIDATION", "how good is this hedge, really?")
    # [Fix 115] this block used to open with a bare kv() and inherit whatever
    # headers the previous block had left in _KVCTX — most often the horizon
    # block's 'WATCH / THIS RUN / WHY AT THIS HORIZON', so the validation
    # numbers came out under a promise of a third column that was never filled.
    # [Fix 117] R² is R² — a trader reads the term faster than a paraphrase of
    # it, and the four flavours below only make sense NAMED, because the whole
    # point of the block is that they answer four different questions. The
    # small second label line says which question each one answers; the
    # appendix spells the four out side by side.
    kvo(headers=('MEASURE', 'THIS RUN', ''))
    if trade_risk.get('n_observations'):
        kv('► Unseen volatility reduction\ncoefficient-only spread versus target',
           f"{trade_risk['vol_reduction']*100:.1f}%",
           'Primary hedge objective; measured before costs on nested unseen data.')
    if not np.isnan(nested_pooled):
        kv('Nested pooled tracking R²\nwhole pipeline re-run',
           f"{nested_pooled:.3f}   (selection re-run before each window, so "
           f"nothing downstream ever saw the scoring data)")
    if boot:
        kv('95% conditional block-bootstrap interval',
           f"R² {boot['r2_lo']:.2f}–{boot['r2_hi']:.2f} · {boot['source']}",
           'Resamples the errors from the stated evidence source. It does not rerun '
           'the full fit/search, so it omits additional selection and fitting uncertainty.')
    if sel_n:
        kv('This config, unseen OOS\nweights honest, config not',
           f"{sel_r2m:.3f} ± {sel_r2s:.3f} over {sel_n}×{outer_window}d · "
           f"pooled {sel_pooled:.3f}"
           + (f" · CI {selected_boot['r2_lo']:.2f}–{selected_boot['r2_hi']:.2f}" if selected_boot else ''))
        kv('Selected-config volatility reduction\nselection bias remains',
           f"{sel_vrm*100:.1f}%"
           + (f" · TE CI {selected_boot['te_lo']*100:.1f}–{selected_boot['te_hi']*100:.1f}%/yr"
              if selected_boot else ''))
    kv('Full-data CV tracking R²\nselection diagnostic',
       f"{best['avg_r2_oos']:.3f} ± {best['std_r2_oos']:.3f} "
       f"({int(best['n_folds'])} folds) — used for configuration selection; "
       f"the winning score is optimistic and is not independent validation")
    _ref_oos = nested_pooled
    if not np.isnan(_ref_oos):
        _gap = r2_final - _ref_oos
        _gv = ('small fitted-to-nested gap' if _gap < 0.15 else
               'moderate fitted-to-nested gap' if _gap < 0.35 else 'large fitted-to-nested gap')
        kv('In-sample vs unseen\nthe overfit check',
           f"{r2_final:.3f} vs {_ref_oos:.3f} (gap {_gap:+.2f}) → {_gv}")
    kv('Selected config', f"lookback {best_lookback}d · PCs {best_pc_spec}"
       f"{f' ({n_pc_final})' if best_pc_spec == 'auto' else ''} · "
       f"basket {best_bsize}")
    if len(nested_valid):
        _picks = nested_valid.apply(
            lambda r: f"lb={int(r['lookback'])}, pc={r['pc_spec']}, "
                      f"size={int(r['basket_size'])}", axis=1)
        _modal = _picks.mode().iloc[0]
        _live = f"lb={best_lookback}, pc={best_pc_spec}, size={best_bsize}"
        if _modal != _live:
            _P(f"  ⚠ the pipeline picked [{_modal}] in "
                  f"{int((_picks == _modal).sum())}/{len(_picks)} unseen "
                  f"windows, not the live [{_live}] — see [4]")
    if sel_n >= 2 and len(sel_detail):
        _P()
        w_rows = []
        for _wi, (_, r) in enumerate(sel_detail.iterrows()):
            w_rows.append([f"{int(r['window'])}"
                           f"{' (latest)' if r['window'] == 1 else ''}",
                           f"{r['start']:%d%b}–{r['end']:%d%b%y}",
                           format(r['r2'], '.3f'),
                           format(r['vol_red'] * 100, '.1f') + '%',
                           format(r['tgt_vol'] * 100, '.1f') + '%',
                           wdisp['flags'][_wi]])
        _print_table(['WIN', 'DATES', 'OOS R²', 'VOL RED', 'TGT VOL',
                      'TRACKING FLAG'], w_rows,
                     title='SELECTED CONFIGURATION WINDOWS — SELECTION BIAS REMAINS',
                     note='TGT VOL is the target\'s volatility in that window. '
                          'A negative tracking score is a descriptive failure flag; '
                          'window-to-window differences are not a significance test.')
        _band = wdisp['band']
        _below = [str(int(r['window'])) for _wi, (_, r)
                  in enumerate(sel_detail.iterrows())
                  if wdisp['flags'][_wi] == 'BELOW band']
        if _band is not None:
            if not _below:
                _P(f"  ► the spread between those stretches is no more than "
                      f"chance would produce ({_band[0]*100:.0f}–"
                      f"{_band[1]*100:.0f}%) — it is not instability, so "
                      f"trust the combined number")
            else:
                _P(f"  ► stretch(es) {', '.join(_below)} came in BELOW what "
                      f"chance alone explains ({_band[0]*100:.0f}–"
                      f"{_band[1]*100:.0f}%) — something real went wrong "
                      f"there, not just a short sample")
        if np.isfinite(wdisp['reg_corr']) and wdisp['reg_corr'] > 0.5:
            _P('  ► In these windows, lower tracking R² coincided with lower '
               'target volatility. This is a descriptive association; review '
               'tracking error and volatility reduction alongside R².')
        if wdisp['min_sim'] is not None:
            _stab = ('the same basket every time' if wdisp['min_sim'] > 0.8
                     else 'a drifting basket' if wdisp['min_sim'] > 0.5
                     else 'a DIFFERENT basket each time')
            _msg = (f"  ► holding this configuration fixed, refits produced "
                    f"{_stab} ({wdisp['min_sim']*100:+.0f}% weight cosine at worst). "
                    'This does not measure stability of the full search.')
            if wdisp['min_sim'] <= 0.5:
                _msg += ' Basket changes may contribute to performance differences.'
            _P(_msg)
        if wdisp['trend']:
            _P('  ► Selected-config tracking worsened in the most recent stretches; '
               'this describes the observed windows and is not a forecast.')
        # ── [Fix 108] IS THE WINNER STILL THE WINNER *NOW*? ────────────────
        # The selection maximises the composite over ALL CV folds. If the
        # hedge is decaying, that average is partly historical. This block
        # states the trade-off explicitly instead of leaving the user to
        # infer it: how fast this config is decaying, what a recent-folds-
        # only selection would have picked instead, and what that
        # alternative scored on the SAME recent folds.
        try:
            _bkey = ['lookback', 'pc_spec', 'basket_size']
            _srt = primary_summary.sort_values('composite', ascending=False)
            _cur = _srt.iloc[0]
            _rsrt = primary_summary.sort_values('composite_recent', ascending=False)
            _alt = _rsrt.iloc[0]
            _same = all(_cur[k] == _alt[k] for k in _bkey)
            _slope = _cur.get('r2_slope_per_fold', np.nan)
            kvo('RECENCY — is this still the right config TODAY?',
                note='The config was picked across the available CV folds. '
                     'The recent-fold comparison is another selection diagnostic, '
                     'not independent evidence that the alternative will work better.')
            if np.isfinite(_slope):
                kv('Decay of the pick\nR² slope per fold',
                   f"{-_slope:+.3f} per {cv_test_window}-row fold",
                   ('HOLDING UP — its OOS R² is flat or improving as the folds '
                    'get newer.' if _slope <= 0.005 else
                    f"Observed R² fell ~{_slope:.3f} per fold toward the present, or "
                    f"~{_slope * max(int(_cur.get('n_folds', 1)) - 1, 1):.2f} "
                    f"across the {int(_cur.get('n_folds', 0))} folds measured. "
                    f"The headline average is flattered by the older folds; "
                    f"These readings describe history and do not establish tomorrow's performance."))
            if np.isfinite(_cur.get('recent_r2', np.nan)):
                kv('  all folds vs recent',
                   f"{_cur['avg_r2_oos']:.3f} all · {_cur['recent_r2']:.3f} "
                   f"newest {int(_cur.get('n_recent', 0))} folds",
                   'The gap between these two IS the question. Small means the '
                   'average is a fair summary; large means you are trading on '
                   'mostly historical evidence.')
            if _same:
                kv('  recency-only pick', 'SAME config',
                   'Selecting on the newest folds alone lands on this same '
                   'config, so the ranking is not an artifact of averaging '
                   'over old regimes.')
            else:
                kv('  recency-only pick',
                   f"lb {int(_alt['lookback'])} · pc {_alt['pc_spec']} · "
                   f"k {int(_alt['basket_size'])}",
                   f"A DIFFERENT config leads on the newest "
                   f"{int(_alt.get('n_recent', 0))} folds "
                   f"({_alt.get('recent_r2', float('nan')):.3f} vs "
                   f"{_cur.get('recent_r2', float('nan')):.3f}). Not chosen, "
                   f"on purpose — a handful of recent folds usually buys "
                   f"noise. Treat it as a challenger: run it from [4], or set "
                   f"recency_weight=0.35 and re-run.")
            if recency_weight:
                kv('  recency_weight', f"{recency_weight:g} (ACTIVE)",
                   f"The pick above already discounts older folds. The scores "
                   f"in the table at the top of [1] are unaffected — they "
                   f"never reweight anything.")
        except Exception as _e108:
            # [Fix 114] never swallow a diagnostic silently — a section that
            # just is not there reads as "nothing to report", which is the
            # opposite of the truth. Also flush whatever rows were already
            # buffered, or they surface inside the NEXT block.
            kv('  recency check', 'unavailable',
               f"could not be computed ({type(_e108).__name__}: {_e108}) — "
               f"the rest of the report is unaffected")
        _kv_flush()
    if roll_stats:
        kvo('ROLLING OOS — 21-row walk-forward',
            note='Every 21 trading days the weights are refit and scored on '
                 'the days that follow. The first three rows answer different '
                 'questions — when they disagree, the "cost of one-way drift" '
                 'row is the whole difference.')
        kv('Tracking error', f"median {roll_stats['te_median']*100:.1f}% · "
           f"worst {roll_stats['te_worst']*100:.1f}% · latest "
           f"{roll_stats['te_latest']*100:.1f}%/yr",
           'Sets the risk budget and the kill level.')
        kv('R² (strict)\ndrift charged', f"median "
           f"{roll_stats['r2_median']:+.2f} · worst "
           f"{roll_stats['r2_worst']:+.2f} · latest "
           f"{roll_stats['r2_latest']:+.2f}",
           'Charges BOTH mistracking and directional drift, so it can go '
           'negative while the hedge is still cutting risk — the next two '
           'rows say why.')
        if np.isfinite(roll_stats.get('r2var_median', np.nan)):
            kv('Explained variance\nmean mismatch removed', f"median "
               f"{roll_stats['r2var_median']:+.2f} · worst "
               f"{roll_stats['r2var_worst']:+.2f} · latest "
               f"{roll_stats['r2var_latest']:+.2f}",
               'Same windows, mean removed from both sides: purely "did '
               'hedging shrink the swing?". The twin of the TE row.')
        if roll_stats.get('n_neg'):
            _nn, _nc2 = roll_stats['n_neg'], roll_stats['n_neg_but_cut']
            kv('  negative-R² windows',
               f"{_nn} of {roll_stats['n_scored']}"
               + (f" · {_nc2} still CUT variance" if _nn else ''),
               (f"In {_nc2} of those {_nn}, the hedge genuinely did shrink the "
                f"swing while a mean-return mismatch made tracking R² negative. "
                f"These still failed the return-tracking test. The other {_nn - _nc2} "
                f"also failed to reduce variance: the hedge "
                f"made things worse."
                if _nc2 else
                f"In all {_nn} the hedge genuinely made the swing BIGGER. "
                f"Those are real failures, not an artifact of the measure."))
        if np.isfinite(roll_stats.get('drift_median', np.nan)):
            kv('  drift penalty',
               f"median {roll_stats['drift_median']:+.2f} R²",
               'The gap between the two rows above. Big here means the hedge '
               'tracks the SHAPE of the target but slides against its LEVEL — '
               'usually one leg running on its own story.')
        kv('  coverage', f"{roll_stats['n_days']} OOS rows across "
           f"{roll_stats['n_segments']} refits, "
           f"{rolling_df.index[0]:%d%b%y}→{rolling_df.index[-1]:%d%b%y}",
           'Read this block as STEADINESS, not as a clean score — the weights '
           'are honest but the recipe saw all the data. The clean score is in '
           'the table at the top of [1].')
    if decay_stats:                                            # [Fix 84]
        _dstr = ' · '.join(f"every {_iv}r {_te*100:.1f}%"
                           for _iv, _te in decay_stats['te_by_interval'])
        kv('TE vs refit interval', _dstr)
        _pen = (decay_stats['te_by_interval'][-1][1]
                / decay_stats['fresh_te'] - 1) * 100
        kv('Rebalance cadence',
           f"refit every ~{decay_stats['rec_rows']} rows · stretching to "
           f"{decay_stats['te_by_interval'][-1][0]}r "
           + (f"costs {_pen:.0f}% more TE" if _pen >= 0.5 else
              "costs nothing measurable"))
        kv('  basis', f"{decay_stats['n_rows']} rows, each scored by fresh, "
           f"one-refit-old and two-refit-old weights — paired, same days")
    if turnover_stats:
        kv('Basket turnover',
           f"consecutive refits share {turnover_stats['mean_jaccard']*100:.0f}%"
           f" of names · weight cosine {turnover_stats['mean_cosine']:+.2f} "
           f"({turnover_stats['n_refits']} refits)")

    # ── [2] COMPARISON ──────────────────────────────────────────────────────
    title("[2] COMPARISON",
          'single instruments are references; the basket remains primary')
    if reg_e is not None:
        _etf_dir = 'short' if reg_e.coef_[0] > 0 else 'long'
        _P(f'  Correlation-picked ETF reference: {_etf_dir} '
           f'${abs(reg_e.coef_[0])*100:.0f} of {disp[best_etf]} per $100 of book')
    else:
        _P('  No eligible correlation-picked ETF reference under these settings.')
    cmp_rows = []
    if sel_n:
        cmp_rows.append(['Selected hedge — this config',
                         f"{sel_r2m:.3f} ± {sel_r2s:.3f}",
                         f"{sel_vrm*100:.1f}%", str(sel_n)])
    if not np.isnan(nested_r2_mean):
        cmp_rows.append(['Primary basket search — nested' if broad_search else 'Pinned hedge — nested',
                         f"{nested_r2_mean:.3f} ± {nested_r2_std:.3f}",
                         f"{nested_vr_mean*100:.1f}%",
                         str(len(nested_valid))])
    if len(etf_bench):
        _p = '/'.join(sorted({e.split(' ')[0]
                              for e in etf_bench['instrument']}))
        cmp_rows.append([f'Correlation-picked ETF [{_p}]', f"{etf_r2_mean:.3f}",
                         f"{etf_vr_mean*100:.1f}%", str(len(etf_bench))])
    if len(name_bench):
        _p = '/'.join(sorted({e.split(' ')[0]
                              for e in name_bench['instrument']}))
        cmp_rows.append([f'Correlation-picked stock [{_p}]', f"{name_r2_mean:.3f}",
                         f"{name_vr_mean*100:.1f}%", str(len(name_bench))])
    if cmp_rows:
        _print_table(['HEDGE', 'OOS R²', 'VOL RED', 'WINDOWS'], cmp_rows,
                     note='Each row reports its available unseen windows. Compare scores '
                          'only when the window sets match. Single instruments are '
                          'references and do not replace the primary basket.')
    _ref_pca = nested_vr_mean if hedge_objective == 'variance' else nested_r2_mean
    matched_simple = [b for b in (etf_bench, name_bench)
                      if len(b) and set(b['window']) == set(nested_valid['window'])]
    _simple_col = 'vol_red_oos' if hedge_objective == 'variance' else 'r2_oos'
    _ref_simple = max([float(b[_simple_col].mean()) for b in matched_simple] or [np.nan])
    if not (np.isnan(_ref_pca) or np.isnan(_ref_simple)):
        _P("  ► " + ("the selected hedge beat the correlation-picked single benchmarks "
                     "on these unseen stretches"
                     if _ref_pca > _ref_simple else
                     'a single-instrument reference held up at least as well; '
                     'the basket remains the primary candidate'))

    # ── [3] DIAGNOSTICS ─────────────────────────────────────────────────────
    title("[3] DIAGNOSTICS", "what is left after the hedge, and why")
    kvo()                     # [Fix 115] no 'DIAGNOSTICS' caption under a
    kv('Residual return ADF\ndescriptive fitted diagnostic',
       f"p={adf_p:.4f}" if np.isfinite(adf_p) else 'unavailable',
       'Unit-root test on fitted return residuals. It does not establish price-spread '
       'cointegration, zero expected drift or unseen hedge quality; selection is not '
       'accounted for in this fitted diagnostic.')
    # ── [Fix 105] HOW MUCH OF THIS TARGET IS HEDGEABLE AT ALL ──────────────
    # The reported AAPL/TSLA/SK-Hynix case raised the right question: does
    # basket hedging even make sense for a concentrated book? A hedge built
    # from other listed instruments can only remove risk the universe SPANS.
    # Whatever is left — one name's own story — is unhedgeable by
    # construction, and it sets a CEILING on R² that no amount of config
    # search can beat. Reporting that ceiling turns "the hedge is bad" into
    # "the hedge is at 0.62 of a possible 0.68 — the gap is not the model".
    #
    # The ceiling is estimated as the in-sample R² of the target on ALL
    # principal components of the candidate universe (not just the k the
    # basket uses). That is generous — it is fitted, so it is an upper bound
    # in the strict sense — which is the right side to err on for a ceiling.
    try:
        _uni_cols = [c for c in returns_final.columns
                     if c != target_ticker and c not in set(pf_legs)]
        if len(_uni_cols) >= 5:
            _Xc = returns_final[_uni_cols].values
            _Xc = (_Xc - _Xc.mean(0)) / np.where(_Xc.std(0) < 1e-12, 1.0,
                                                 _Xc.std(0))
            _npc_ceil = int(min(len(_uni_cols), len(returns_final)-1,
                                max(3, len(rets) // 20), 20))
            # _pca_fit returns a _PCAShim (components only, no .transform),
            # so project by hand: scores = X · Wᵀ
            _shim = _pca_fit(_Xc, _npc_ceil, robust_cov)
            _pcs = _Xc @ np.asarray(_shim.components_).T
            _yc = returns_final[target_ticker].values
            _reg_ceil = RidgeCV(alphas=RIDGE_ALPHAS).fit(_pcs, _yc)
            _ceil = float(max(0.0, _reg_ceil.score(_pcs, _yc)))
            _got = float(ticket_info['quality_r2']) if np.isfinite(
                ticket_info.get('quality_r2', np.nan)) else np.nan
            _msg = (f'In-sample fit using {_npc_ceil} candidate-universe '
                    f'components: R² {_ceil:.2f}. This measures historical '
                    'association within the downloaded universe. It does not '
                    'establish a hard ceiling or prove remaining risk is '
                    'unhedgeable. Judge deployable baskets on unseen data.')
            kv('Exploratory factor fit\ntraining data only',
               f'in-sample R² {_ceil:.2f}', _msg)
    except Exception as _e105:
        kv('Exploratory factor fit', 'unavailable',              # [Fix 114]
           f"could not be estimated ({type(_e105).__name__}: {_e105}). "
           f"Without it there is no reading on how much of this target is "
           f"hedgeable at all — judge the hedge by how far it drifts, not by "
           f"the share of moves it tracks.")

    # ── [Fix 121] DRIFT ─────────────────────────────────────────────────────
    kv('Hedge drift\nwhat the spread earned per year, not its wobble',
       f"{drift_ann*100:+.1f}%/yr"
       + (f" · {drift_ann*hedge_horizon_days/252*100:+.1f}% over the "
          f"{int(hedge_horizon_days)}d hold" if hedge_horizon_days else ''),
       'The fitted intercept — the level the hedged book ground at while it '
       'was tracking. Every risk figure above is dispersion AROUND this, not '
       'around zero. It is what the hedge HAS drifted, not a forecast: read '
       'it as a warning when it is large, never size on it.')

    # ── [Fix 122] ASYMMETRY AND PATH ────────────────────────────────────────
    # Every other statistic in this report is a symmetric second moment: TE,
    # R², vol reduction, the drift penalty, the bootstrap band and the ridge
    # loss itself all price an up-day error and a down-day error identically.
    # Correlations rise in the left tail (Ang-Chen 2002; Longin-Solnik 2001),
    # so a hedge fitted on the average day can under-protect on the day it is
    # held for while TE barely moves. Measured (300 seeds): lifting the hedge's
    # beta only in the worst 20% of days moved TE 15.8% → 16.9%/yr while the
    # worst-decile residual went -0.04% → -0.72% PER DAY.
    # Reported only. Selecting on a semivariance would halve the sample to
    # estimate a noisier quantity — the trap [Fix 112] already refused.
    try:
        _dn_src = pd.Series(returns_final[target_ticker].values
                            - returns_final[basket_final].values @ weights_final.values,
                            index=returns_final.index)
        _tgt_d = returns_final[target_ticker]
        _q = _tgt_d.quantile(0.10)
        _worst = _dn_src[_tgt_d <= _q]
        _best = _dn_src[_tgt_d >= _tgt_d.quantile(0.90)]
        if len(_worst) >= 5 and len(_best) >= 5:
            _wm, _bm = float(_worst.mean()), float(_best.mean())
            asym_stats = {'worst_decile_mean': _wm, 'best_decile_mean': _bm,
                          'gap_bp_day': (_wm - _bm) * 1e4,
                          'n_worst': int(len(_worst))}
            kv('Worst-day behaviour',
               f"{_wm*1e4:+.1f} bp/observation vs {_bm*1e4:+.1f} bp on the best 10%",
               'Fitted coefficient-only spread averages on target-tail observations. '
               'Descriptive and sample-dependent; they do not establish crisis protection.')
    except Exception as _e122:
        kv('Worst-day behaviour', 'unavailable',
           f"could not be computed ({type(_e122).__name__}: {_e122}) — the "
           f"report then says nothing about how this hedge behaves in a "
           f"sell-off, so treat the TE above as an average-day figure.")

    # Path risk. The hedged series was built only to be drawn on a chart and
    # then discarded, so no peak-to-trough number existed anywhere. Prefer the
    # walk-forward residual (honest weights, refit through time) over the
    # in-sample one; returns are logs, hence expm1 on the cumulative.
    try:
        if len(rolling_df) and rolling_df['traded_spread'].notna().any():
            _dd_src = rolling_df['traded_spread'].dropna()
            _dd_lbl = 'selected-configuration walk-forward spread'
        else:
            _dd_src = pd.Series(returns_final[target_ticker].values
                                - returns_final[basket_final].values @ weights_final.values,
                                index=returns_final.index)
            _dd_lbl = 'fitted coefficient-only spread'
        path_stats = _spread_path_stats(_dd_src, two_day, _dd_lbl)
        _mdd, _peak, _trough = (path_stats[k] for k in ('max_drawdown', 'peak', 'trough'))
        _w5 = path_stats['worst_5d']
        kv('Hedged drawdown\nworst peak-to-trough of the hedged book',
           f"{_mdd*100:.1f}% ({_peak.strftime('%d%b%y') if _peak is not None else 'start'}→{_trough:%d%b%y})"
           + (f" · worst 5 days {_w5*100:.1f}%" if np.isfinite(_w5) else ''),
           f"On the {_dd_lbl}, using non-overlapping returns. A 1σ figure says how wide the spread "
           f"scatters; this says how far it actually went against a holder "
           f"before recovering. This log-spread path is a proxy, not financed portfolio P&L.")
    except Exception as _e123:
        kv('Hedged drawdown', 'unavailable',
           f"could not be computed ({type(_e123).__name__}: {_e123}) — with no "
           f"path figure, judge survivability from the worst-window TE alone.")

    # ── [Fix 119] WHAT THE UNIVERSE COULD NOT OFFER ─────────────────────────
    _exp_info = (data or {}).get('exposures') or {}
    if _exp_info.get('tags'):
        _res = _exp_info.get('resolved') or {}
        _unres = _exp_info.get('unresolved') or {}
        _held = [t for t in basket_final
                 if any(t in v for v in _res.values())]
        # [Fix 115] '·' is the separator the renderer splits readings on, so
        # the tag list joins on a comma — a '·' there split "GOLD · SEMIS →
        # holding PMGOLD" across lines and made SEMIS look like the thing held.
        kv('Exposures this target carries\nfrom its BICS / GICS taxonomy',
           ', '.join(_exp_info['tags'])
           + (f" · holding {', '.join(disp.get(t, t) for t in _held)}"
              if _held else " · none held in the final basket"),
           ('Every exposure the taxonomy implies has an instrument in the '
            'candidate set; whether the model chose it is a separate question '
            'answered by the basket above.' if not _unres else
            'MISSING: ' + ', '.join(sorted(_unres))
            + ' — no instrument is mapped for this market, so the hedge was '
              'built without that leg. Add one to MARKET_INSTRUMENTS and '
              're-download, or expect it in the residual.'))

    if is_portfolio:
        hedge_ret = returns_final[basket_final].values.dot(
            weights_final.values)
        hvar = float(np.var(hedge_ret))
        leg_rows = []
        for leg in [c for c in pf_legs if c in returns_final.columns]:
            lr = returns_final[leg].values
            b_h = (float(np.cov(lr, hedge_ret)[0, 1] / hvar)
                   if hvar > 1e-12 else np.nan)
            rc = float(np.corrcoef(resid_final, lr)[0, 1])
            leg_rows.append([disp.get(leg, leg),
                             format(pf_w.get(leg, 0.0), '+.2f'),
                             format(np.std(lr) * ann_sqrt * 100, '.1f') + '%',
                             format(b_h, '+.2f'), format(rc, '+.2f')])
        _P()
        _P("  PER-LEG — what the net-book hedge hides:")
        _print_table(['LEG', 'BOOK W', 'ANN VOL', 'β vs HEDGE',
                      'CORR w/ RESID'], leg_rows)
        _P("  ► the basket hedges the NET book; the leg with the largest "
              "|corr w/ resid| is the")
        _P("    one whose idio risk survives — hedge it separately, trim, "
              "or pair it off")
    _stock_cols = [c for c in returns_final.columns
                   if c != target_ticker and c not in set(pf_legs)
                   and not _is_etf(c)]                          # [Fix 47]
    _caps_map = {c: _cap_asof(c, returns_final.index[-1])
                 for c in _stock_cols}
    fl = _factor_leakage(returns_final, target_ticker, weights_final,
                         caps_map=_caps_map, stock_cols=_stock_cols)
    if fl is None:
        _P("  (factor diagnostics need ~6+ non-ETF names in the "
              "universe)")
    else:
        _print_table(['FACTOR', 'TARGET β', 'RESIDUAL β'],
                     [[r['factor'], format(r['target_beta'], '+.3f'),
                       format(r['residual_beta'], '+.3f')]
                      for _, r in fl.iterrows()],
                     title='FACTOR EXPOSURE — target vs hedged residual',
                     note='Factors are sequentially orthogonalized. Residual '
                          'β ≈ 0 means the hedge neutralized that factor; a '
                          'large one is a tilt you are still carrying.')
        _lo = fl.loc[fl['residual_beta'].abs().idxmax()]
        _P(f"  ► largest surviving tilt: {_lo['factor']} "
              f"(residual β {_lo['residual_beta']:+.3f})")

    # ── [4] ALTERNATIVES ────────────────────────────────────────────────────
    # [Fix 109] Every alternative now carries the SAME evidence as the pick:
    # exact executable weights, unseen-window OOS, rolling TE / R² through
    # time, the recency split, and gross. Previously an alternative showed a
    # CV average and a truncated holdings string, so there was no way to tell
    # whether #2 was genuinely comparable or merely close on one statistic —
    # which is the only thing this section exists to answer.
    title("[4] ALTERNATIVES",
          "the next-best recipes, judged on exactly the same evidence")
    top5 = primary_summary.assign(_chosen=(
        (primary_summary['lookback'] == best_lookback) &
        (primary_summary['pc_spec'].astype(str) == str(best_pc_spec)) &
        (primary_summary['basket_size'] == best_bsize))).sort_values(
            ['_chosen', 'composite'], ascending=False)
    _alt_cache, _alt_seen = [], set()
    for _, cfg in top5.iterrows():
        _lb5, _ps5, _bs5 = int(cfg['lookback']), cfg['pc_spec'], int(cfg['basket_size'])
        _is_sel = bool(cfg['_chosen'])
        try:
            (_, _, _bkt5, _reg5, _r25, _, _, _, _) = _select_and_fit(
                rets.iloc[-_lb5:], _ps5, _bs5)
            _w5 = pd.Series(_reg5.coef_, index=_bkt5)
        except RuntimeError:
            continue
        _key5 = tuple(sorted((tk, round(float(x), 5)) for tk, x in _w5.items()))
        if len(_w5) < 2 or _key5 in _alt_seen:
            continue
        _alt_seen.add(_key5)
        _c_r2m, _c_r2s, _c_vrm, _c_n = _config_outer_oos(_lb5, _ps5, _bs5)
        _rs5 = (roll_stats if (_is_sel and roll_stats)
                else (_roll_stats_for(_lb5, _ps5, _bs5) if rolling_oos else None))
        _alt_cache.append(dict(i=len(_alt_cache)+1, cfg=cfg, lb=_lb5, ps=_ps5, bs=_bs5,
                               sel=_is_sel, r2m=_c_r2m, r2s=_c_r2s,
                               vrm=_c_vrm, n=_c_n, roll=_rs5, w=_w5, r2_in=_r25))
        if len(_alt_cache) >= alternative_baskets + 1:
            break
    # ── summary table: one row per config, every headline side by side ─────
    _hd = ['', 'CONFIG', 'CV R²', 'UNSEEN R²', 'ROLL TE med/worst',
           'ROLL R² med', 'RECENT R²', 'VOL RED', 'GROSS', '']
    _rows5 = []
    for _a in _alt_cache:
        _rr = _a['roll']
        _rows5.append([
            f"#{_a['i']}",
            f"lb {_a['lb']} · pc {_a['ps']} · k {_a['bs']}",
            f"{_a['cfg']['avg_r2_oos']:.3f}",
            (f"{_a['r2m']:.3f} ± {_a['r2s']:.3f}" if _a['n'] else 'n/a'),
            (f"{_rr['te_median']*100:.1f}% / {_rr['te_worst']*100:.1f}%"
             if _rr else 'n/a'),
            (f"{_rr['r2_median']:+.2f}" if _rr else 'n/a'),
            (f"{_a['cfg']['recent_r2']:.3f}"
             if np.isfinite(_a['cfg'].get('recent_r2', np.nan)) else 'n/a'),
            f"{_a['cfg']['avg_vol_red']*100:.0f}%",
            f"${_a['cfg']['avg_gross']*100:.0f}",
            ('◄ chosen' if _a['sel'] else '')])
    _print_table(_hd, _rows5,
                 note='These are basket configuration diagnostics. Outer and rolling '
                      'scores retain configuration-selection bias; choosing a new winner '
                      'after seeing them is not independent validation. Config = '
                      'lookback days · PCs · basket size.')
    # ── per-config detail: the exact ticket each alternative would produce ──
    # [Fix 115] This used to repeat the SAME four explanation rows under every
    # config — five configs × four paragraphs of identical prose, ~20 rows of
    # boilerplate for four distinct sentences. The explanations are a property
    # of the COLUMNS, not of any one config, so they are stated once here and
    # each config below shows only its own numbers.
    _P("  ► each block below is the ticket that recipe would produce, and "
       "how it scored on exactly the same evidence as the one chosen")
    _kv_open('WHAT THE FOUR MEASURES BELOW MEAN')  # stated once, not per row
    kv('gross / in-sample', 'candidate position and its training fit',
       'The second figure is the fit scored on its own data. Never size off it.')
    kv('unseen windows', 'refit before each window, scored on it',
       'Weights are refitted before scoring; configuration-selection bias remains.')
    kv('rolling OOS', '21-row walk-forward TE and R²',
       'Read stability here — a config with a similar median but a much worse '
       'worst case is the more dangerous one.')
    kv('recency', 'all folds vs the newest folds',
       'Recent above all-fold means improving; the reverse means decaying.')
    _kv_flush()
    for _a in _alt_cache:
        _tagsel = '   ◄ THIS IS THE ONE IN THE TICKET' if _a['sel'] else ''
        if _a['w'] is None:
            _P(f"  #{_a['i']}  fits on {_a['lb']} days, {_a['bs']} names "
               f"— refit failed, no weights available")
            continue
        _P(f"  #{_a['i']}   fits on {_a['lb']} days, {_a['bs']} names in "
           f"the basket{_tagsel}")
        _print_table(BASKET_HEADERS, _basket_rows(_a['w']), indent='      ')
        _rr = _a['roll']
        _det = [('gross / in-sample',
                 f"${_a['w'].abs().sum()*100:.0f} per $100 · in-sample R² "
                 f"{_a['r2_in']:.2f}")]
        if _a['n']:
            _det.append(('unseen windows',
                         f"R² {_a['r2m']:.3f} ± {_a['r2s']:.3f} · vol red "
                         f"{_a['vrm']*100:.0f}% · {_a['n']} windows"))
        if _rr:
            _det.append((
                'rolling OOS',
                f"TE {_rr['te_median']*100:.1f}% med / "
                f"{_rr['te_worst']*100:.1f}% worst / "
                f"{_rr['te_latest']*100:.1f}% latest · R² "
                f"{_rr['r2_median']:+.2f} med / {_rr['r2_worst']:+.2f} worst "
                f"/ {_rr['r2_latest']:+.2f} latest · "
                + (f"{_rr['n_neg']} of {_rr.get('n_scored', 0)} windows "
                   f"NEGATIVE" if _rr.get('n_neg') else
                   f"0 of {_rr.get('n_scored', 0)} windows negative")))
        if np.isfinite(_a['cfg'].get('recent_r2', np.nan)):
            _det.append((
                'recency',
                f"all folds {_a['cfg']['avg_r2_oos']:.3f} · recent "
                f"{_a['cfg']['recent_r2']:.3f}"
                + (f" · slope {-_a['cfg']['r2_slope_per_fold']:+.3f}/fold"
                   if np.isfinite(_a['cfg'].get('r2_slope_per_fold', np.nan))
                   else '')))
        _kv_block(None, _det, headers=('MEASURE', 'THIS CONFIG'))

    # ── [A] APPENDIX ────────────────────────────────────────────────────────
    title("[A] APPENDIX", "settings, definitions and caveats")
    # ── [Fix 110] WHICH KNOBS ACTUALLY MOVED ANYTHING ──────────────────────
    # Two questions kept coming back — "does the hedge duration change the
    # analysis?" and "does the book size?" — and the report gave no way to
    # answer either without reading the source. Every setting that can change
    # a NUMBER is now listed with what it touched, and, just as importantly,
    # the ones that touch nothing are listed as touching nothing.
    _rows_a = []
    _rows_a.append((
        'Book size\nnotional_mm',
        f"${notional_mm:g}mm" if notional_mm else 'not set',
        'DISPLAY ONLY — it does not affect the model. A hedge ratio is a '
        'ratio: the weights, the recipe search, the testing and every score '
        'are identical at $1mm and $100mm. All this does is turn them into '
        'dollars. (What book size DOES change in real life — market impact '
        'and whether you can borrow the stock — is not modelled here at all; '
        'see the notes at the end.)'))
    _rows_a.append((
        'Hedge duration\nhedge_horizon_days',
        f"{int(hedge_horizon_days)} trading days" if hedge_horizon_days
        else 'not set',
        ('DOES affect the report, NOT the weights. It scales the risk to '
         'your holding period, reports what holds of that length actually '
         'delivered, and checks whether the weights go stale before the hold '
         'ends. It deliberately does NOT change which stretches are held back '
         'for testing. horizon_sets_windows=True restores the old '
         'behaviour and WILL change which recipe wins.'
         if hedge_horizon_days else
         'Not set, so risk is quoted annualised and the "holds" evidence is '
         'skipped. Set it to the number of trading days you intend to hold '
         '— it costs nothing and adds the only figures measured on your '
         'actual horizon.')))
    # ── [Fix 112] HOW MUCH OF THE HISTORY IS ACTUALLY READ ─────────────────
    # The walk-forward consumes a FIXED budget of rows, set by the fold
    # counts and the longest lookback — not by how much data you downloaded:
    #     max(lookback) + cv_test_window x cv_n_folds
    #                   + outer_window x outer_folds + purge
    # Everything older than that is never touched. Measured directly
    # (synthetic, 10 seeds, default settings): 2.5y / 3y / 4y / 5y of history
    # produce BIT-IDENTICAL results. So "download more history" is not a way
    # to stabilise the selection — it does nothing at all. Raising the fold
    # counts IS the way to consume more, and measured that did not help
    # either (cv_n_folds 5->10 and outer_folds 3->6 at 5y: paired
    # d = -0.011 nested R², t = -1.29, better in 4 of 10 — the extra folds
    # reach back into older, less relevant regimes).
    _need = (max(lookback_options) + cv_test_window * cv_n_folds
             + outer_window * outer_folds + purge * 2)
    _spare = len(rets) - _need
    _rows_a.append((
        'How much history was read\nof what you downloaded',
        f"≈{min(_need, len(rets))} of {len(rets)} rows"
        + (f" · {_spare} unused" if _spare > 0 else ''),
        (f"The main grid and nested tests require about {_need} recent rows at these settings. "
         f"Older rows may still enter other diagnostics and data-aware defaults. More history "
         f"lets you test longer lookbacks or more folds, but does not guarantee a better hedge."
         if _spare > 20 else
         f"The requested tests need about {_need} rows and have {len(rets)}. "
         f"More history can provide additional validation; short samples use a simpler evidence tier.")))
    _rows_a.append((
        'Basket sizes tried\nnames per basket', str(tuple(basket_size_options)),
        'Requested baskets compete for the primary recipe; every eligible single instrument is evaluated as a reference. '
        'Baskets are built by PCA, correlation and forward selection. '
        'This broad search remains a finite set of heuristics rather than an exhaustive subset optimizer.'))
    # ── [Fix 113] IS THERE ROOM FOR A LONGER LOOKBACK? ─────────────────────
    # A lookback is only worth offering if the NESTED validation can still
    # train it — the oldest outer window's inner CV needs
    #     lb + cv_test_window*cv_n_folds  rows of data before it.
    # Below that, the option is either dropped or (worse) available to the
    # live pick but not to the validation, so you could select something you
    # never validated.
    # Measured (synthetic, 20 paired seeds, nested pooled OOS R²):
    #     adding 504 with 5y of data   concentrated +0.0146 (t=+3.19)
    #                                  well-spanned  +0.0031 (t=+2.28)
    #     adding 504 with 3y of data   504 is chosen 0/20 times — no effect,
    #                                  because there is not enough history to
    #                                  train it before each window.
    # So the default (126, 252) is right for the default 3-year download, and
    # a longer lookback is worth adding ONLY together with more history. That
    # is the one thing extra history genuinely buys — see 'History READ'.
    _lb_room = (len(rets) - outer_folds * outer_window - purge
                - cv_test_window * cv_n_folds)
    _lb_hint = ''
    if 504 > max(lookback_options):
        if 504 <= _lb_room:
            _lb_hint = ' There is enough history to test a 504-row lookback if you choose to include it.'
        else:
            _lb_hint = f' A 504-row lookback needs about {504 - _lb_room} additional rows for nested validation.'
    _rows_a.append((
        'Lookbacks tried\ndays of history per refit', str(tuple(lookback_options)),
        # [Fix 115] this row was a 120-word essay. The measured finding stays,
        # because it answers the question this row actually gets asked; the
        # recital of the experiment does not.
        'The training-history length used at each refit. Shorter windows can adapt faster '
        'and have noisier estimates; longer windows include more history and can span older regimes. '
        'The selection compares the specified lengths using earlier CV folds.' + _lb_hint))
    _rows_a.append((
        'Outlier clipping\nwinsorize', f"{winsorize_pct:.1%}" if winsorize_pct else 'off',
        'Clips returns before the PCA that SELECTS candidates — never '
        'before the ridge that sets the hedge ratios, so no fitted number '
        'is computed on doctored data. 1% keeps a handful of observations '
        'per tail from steering the eigenvectors. Raising it much further '
        'starts deleting genuine crisis co-movement, which is exactly the '
        'behaviour a hedge exists to capture.'))
    _rows_a.append((
        'Penalty on a big position\ngross_penalty',
        f"{gross_penalty:g} per 1.0x gross"
        + (f" · hard cap {max_gross:g}x" if max_gross else ' · no hard cap'),
        f"Costs a recipe {gross_penalty*100:.0f} points in the ranking per "
        f"$100 of position. This chosen basket runs "
        f"${weights_final.abs().sum()*100:.0f} per $100, so it paid "
        f"{gross_penalty*weights_final.abs().sum():.3f}. The penalty is a "
        f"proxy, not a cost model — borrow, financing and impact are NOT "
        f"priced anywhere in this tool. If gross matters to you "
        f"economically, set max_gross (3.0 is a common desk limit) rather "
        f"than relying on the penalty to hold it down."))
    _rows_a.append((
        'How much recent data counts extra\nrecency_weight',
        f"{recency_weight:g}" + (' (ACTIVE)' if recency_weight else
                                 ' — every test stretch counts the same'),
        'At 0 the search gives equal weight to the available CV folds. '
        'See "IS THIS STILL THE RIGHT RECIPE '
        'TODAY?" in [1] for what that cost on this run, and what choosing on '
        'recent data alone would have picked instead.'))
    _kv_block('SETTINGS — what each knob actually did', _rows_a,
              headers=('SETTING', 'THIS RUN', 'WHAT IT AFFECTS'),
              note='Reference material — nothing here changes unless you '
                   'change it. The rows that say DISPLAY ONLY genuinely do '
                   'not move a single number in the model.')
    _kv_block('WORDS USED IN THIS REPORT', WORDS_USED,   # [Fix 116]
              headers=('TERM', 'IN ONE LINE', 'A BIT MORE'))
    _kv_block('FOUR WAYS OF SCORING A HEDGE — and why they differ',
              R2_GLOSSARY_ROWS, note=R2_GLOSSARY_NOTE,   # [Fix 52]
              headers=('HOW IT WAS MEASURED', 'WHAT IT IS WORTH',
                       'WHAT IT ACTUALLY TELLS YOU'))
    hr()
    _P("  Read before trading:")
    _P("  · the candidate list comes from today's index members and peers"
          + (" — but membership is checked as of each date, so delisted names "
             "are included where they belong ✓" if pm_active else
             ". Names that have since delisted are missing, which flatters "
             "every backtest here"))
    _P("  · the size floor uses "
          + ("what each name was worth at the time ✓" if pit_active else
             "what each name is worth TODAY — a name that grew into the "
             "filter can flatter the backtest"))
    _P("  · these are statistical ratios only. Borrow cost, slippage and FX "
          "are NOT priced anywhere in this tool, and returns are in each "
          "name's own currency")
    if is_portfolio:
        _P("  · your book is hedged as ONE combined position, not leg by "
              "leg. The names you hold are excluded from the candidate list")
    if forced:
        _P("  · ★ names were pinned in by you, not chosen by the model — "
              "run it once without them to see what they cost")
    _P('═' * L)

    alternatives = {}
    for family, evidence in family_tests.items():
        choices = _family_configs(summary, family, market_tickers)
        if choices.empty:
            continue
        choice = choices.loc[choices['composite'].idxmax()]
        try:
            _, _, fb, fr, raw_alt, _, _, _, _ = _select_and_fit(
                rets.iloc[-int(choice['lookback']):], choice['pc_spec'], int(choice['basket_size']))
        except RuntimeError:
            continue
        alternatives[family] = _alternative_evidence(
            pd.Series(fr.coef_, index=fb), raw_alt, evidence['y'], evidence['residual'], evidence['spread'],
            ann_sqrt, outer_folds, val_mode,
            {'lookback': int(choice['lookback']), 'pc_spec': choice['pc_spec'],
             'basket_size': int(choice['basket_size']), 'selection_score': float(choice['composite']),
             'max_gross': max_gross}, hedge_objective)
        alternatives[family]['reference_only'] = family.startswith('single')
    search = _search_metadata(summary, cv_df)
    selected_family = _config_family(best_pc_spec, len(basket_final))
    primary_item = alternatives.get(selected_family)
    if primary_item is not None:
        primary_item['qualified'] = _decision_fields(weights_final, grade)['trade_eligible']
        if not primary_item['qualified']:
            primary_item['status'] = grade
    _show_hedge_comparison(alternatives, selected_family, search)

    chart_pca, chart_loadings = pca_f, loadings_f
    if show_plots and chart_pca is None:
        ctx = _training_context(rets.iloc[-best_lookback:], min_train_rows)
        _, _, chart_pca, chart_loadings = _context_pca(ctx, 'auto')
    return {
        'training_data_diagnostics': pd.DataFrame(training_diagnostics),
        'evaluation_data_diagnostics': pd.DataFrame(evaluation_diagnostics),
        'engine_revision': PCA_REVISION,
        'primary_hedge_family': selected_family,
        'hedge_alternatives': alternatives, 'search': search,
        'best_basket_hedge': alternatives.get('basket'),
        'best_single_hedge': alternatives.get('single'),
        'best_single_stock_hedge': alternatives.get('single_stock'),
        'best_single_etf_hedge': alternatives.get('single_etf'),
        **_decision_fields(weights_final, grade),
        'trade_risk': trade_risk,
        'unhedged_baseline': {'vol_reduction': 0.0, 'variance_reduction': 0.0},
        'in_sample_r2': r2_final,
        'basket_candidates': _alt_cache,
        'chart_pca': chart_pca, 'chart_loadings': chart_loadings,
        'weights': weights_final, 'basket': basket_final,
        'ranking': final_rank, 'cv_summary': summary, 'cv_detail': cv_df,
        'nested_validation': nested,
        'nested_r2_mean': nested_r2_mean, 'nested_r2_std': nested_r2_std,
        'nested_vol_red_mean': nested_vr_mean,
        'selected_unseen_r2': sel_r2m, 'selected_unseen_r2_std': sel_r2s,
        'selected_unseen_pooled_r2': sel_pooled,       # [Fix 65]
        'outer_window_detail': sel_detail,             # [Fix 65]
        'nested_pooled_r2': nested_pooled,             # [Fix 69]
        'selected_config_bootstrap_ci': selected_boot,
        'nested_unseen_returns': nested_unseen,
        'bootstrap_ci': boot,                          # [Fix 70]
        'rolling_oos': rolling_df,                     # [Fix 71]
        'rolling_stats': roll_stats,
        'ticket': ticket_info,                         # [Fix 72]
        'nowcast': nowcast,                            # [Fix 93]
        'target_label': target_short,                  # [Fix 103] for export
        'analysis_span': (rets.index[0], rets.index[-1], len(rets)),  # [Fix 99]
        'horizon': horizon_info,                       # [Fix 91]
        'validation_mode': val_mode,                   # [Fix 77]
        'decay': decay_stats,                          # [Fix 78]
        'turnover': turnover_stats,                    # [Fix 78]
        'drift_ann': drift_ann,                        # [Fix 121]
        'asymmetry': asym_stats,                       # [Fix 122]
        'path': path_stats,                            # [Fix 123]
        'exposures': (data or {}).get('exposures') or {},   # [Fix 119]
        'etf_benchmark': etf_bench,
        'etf_nested_r2_mean': etf_r2_mean,
        'name_benchmark': name_bench,                  # [Fix 53]
        'name_nested_r2_mean': name_r2_mean,           # [Fix 53]
        'best_single': best_single, 'best_etf': best_etf,
        'returns': returns_final, 'prices': prices,
        'two_day_returns': two_day,
        'excluded': removed_cols,                      # [Fix 36]
        'force_included': forced,                      # [Fix 40]
        'is_portfolio': is_portfolio,                  # [Fix 46]
        'portfolio_legs': pf_legs, 'portfolio_weights': pf_w,
        'factor_leakage': fl,                          # [Fix 43]
        'pit_size_active': pit_active,                 # [Fix 44]
        'pit_members_active': pm_active,               # [Fix 49]
        'params': {'lookback': best_lookback, 'pc_spec': best_pc_spec,
                   'basket_size': best_bsize, 'hedge_objective': hedge_objective, 'broad_search': broad_search,
                       'recency_weight': recency_weight,
                   'tz_tolerance_hours': tz_tolerance_hours,
                   'min_mktcap_usd_mm': min_mktcap_usd_mm,
                   'gross_penalty': gross_penalty, 'max_gross': max_gross,
                   'force_include': force_include,
                   'winsorize_pct': winsorize_pct, 'robust_cov': robust_cov,
                   'pit_size': pit_size, 'pit_members': pit_members,
                   'size_band': size_band,
                   'size_override': size_override,
                   'mask_stale_days': mask_stale_days,    # [Fix 56]
                   'notional_mm': notional_mm,            # [Fix 72]
                   'boot_n': boot_n,                      # [Fix 70]
                   'sample_window': sample_window,        # [Fix 76]
                   'hedge_horizon_days': hedge_horizon_days,  # [Fix 91]
                   'horizon_sets_windows': horizon_sets_windows,  # [Fix 100]
                   'report': report},                     # [Fix 79]
    }




def _report_figures(result):
    """Fitted diagnostics and conditional rolling charts; no extra validation."""
    frame, weights = result['returns'], result['weights']
    target = PORTFOLIO_COL if result.get('is_portfolio') else result['portfolio_legs'][0]
    target_returns = frame[target]
    spread = target_returns - frame[weights.index] @ weights
    two_day = result.get('two_day_returns', False)
    annualisation = np.sqrt(252 / (2 if two_day else 1))
    colour = {'target': '#b36b58', 'hedged': '#287b6f', 'pick': '#315a69', 'other': '#b6cbc7'}
    style = {'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.titlesize': 10,
             'axes.titleweight': 'bold', 'axes.labelsize': 8,
             'axes.edgecolor': '#d9e3df', 'axes.labelcolor': '#52666f',
             'axes.grid': True, 'grid.color': '#eef3f0', 'axes.axisbelow': True,
             'figure.facecolor': 'white', 'legend.frameon': False,
             'legend.fontsize': 8, 'xtick.labelsize': 8, 'ytick.labelsize': 8,
             'lines.linewidth': 1.5}
    figures = []
    with plt.rc_context(_supported_plot_style(style)):
        fig, axes = plt.subplots(2, 3, figsize=(16, 8.5))
        pca, loadings = result.get('chart_pca'), result.get('chart_loadings')
        if pca is not None:
            ev = pca.explained_variance_ratio_ * 100
            axes[0, 0].bar(np.arange(1, len(ev)+1), ev, color=colour['pick'])
            axes[0, 0].plot(np.arange(1, len(ev)+1), np.cumsum(ev), 'o-', color=colour['target'])
            axes[0, 0].set_xticks(np.arange(1, len(ev)+1))
            axes[0, 0].set_xlabel('Principal component'); axes[0, 0].set_ylabel('Variance (%)')
        axes[0, 0].set_title('PCA variance explained · descriptive')
        if isinstance(loadings, pd.DataFrame) and {'PC1', 'PC2'} <= set(loadings):
            labels = set(weights.index) | {target}
            for ticker, row in loadings.iterrows():
                c = colour['target'] if ticker == target else colour['hedged'] if ticker in weights else colour['other']
                axes[0, 1].scatter(row['PC1'], row['PC2'], color=c, s=80 if ticker == target else 24, zorder=3)
                if ticker in labels:
                    axes[0, 1].annotate(ticker.split(' ')[0], (row['PC1'], row['PC2']),
                                        fontsize=6.5, xytext=(3,3), textcoords='offset points')
            axes[0, 1].set_xlabel('PC1'); axes[0, 1].set_ylabel('PC2')
        else:
            axes[0, 1].text(.5, .5, 'Two PCA directions unavailable', ha='center', transform=axes[0, 1].transAxes)
        axes[0, 1].set_title('PCA map · terracotta target, teal basket')
        correlations = frame.drop(columns=target).corrwith(target_returns).sort_values(ascending=False).head(10)
        axes[0, 2].barh(np.arange(len(correlations)), correlations,
                       color=[colour['hedged'] if c in weights else colour['other'] for c in correlations.index])
        axes[0, 2].set_yticks(np.arange(len(correlations)))
        axes[0, 2].set_yticklabels([c.split(' ')[0] for c in correlations.index])
        axes[0, 2].invert_yaxis(); axes[0, 2].set_xlabel('Correlation')
        axes[0, 2].set_title('Fitted correlations · teal basket instruments')
        phase = slice(None, None, 2) if two_day else slice(None)
        axes[1, 0].plot(np.expm1(target_returns.iloc[phase].cumsum())*100,
                        color=colour['target'], label='Target')
        axes[1, 0].plot(np.expm1(spread.iloc[phase].cumsum())*100,
                        color=colour['hedged'], label='Hedged spread')
        axes[1, 0].axhline(0, color='#bccbc6', ls='--', lw=.8)
        axes[1, 0].legend(); axes[1, 0].set_ylabel('Log-spread proxy (%)')
        axes[1, 0].set_title('Fitted paths · non-overlapping observations')
        count = max(5, min(20, len(frame)//3))
        for values, label, c in [(target_returns, 'Target', colour['target']), (spread, 'Hedged spread', colour['hedged'])]:
            axes[1, 1].plot(values.rolling(count).std()*annualisation*100, label=label, color=c)
        axes[1, 1].legend(); axes[1, 1].set_ylabel('Annualised volatility (%)')
        axes[1, 1].set_title(f'Fitted rolling {count}-row volatility')
        summary = result.get('cv_summary')
        if isinstance(summary, pd.DataFrame) and len(summary) and 'avg_r2_oos' in summary:
            baskets = summary[summary['basket_size'] >= 2]
            for lb in baskets['lookback'].unique():
                values = baskets[baskets['lookback'] == lb].groupby('basket_size')['avg_r2_oos'].mean()
                axes[1, 2].plot(values.index, values.values, 'o-', label=f'{int(lb)}-row lookback')
            if len(baskets): axes[1, 2].legend()
            axes[1, 2].set_ylabel('Mean CV R²'); axes[1, 2].set_xlabel('Basket size')
            axes[1, 2].set_title('Basket-size sensitivity · CV selection diagnostic')
        else:
            candidates = result.get('basket_comparison') or []
            axes[1, 2].bar([str(r['number']) for r in candidates], [r['in_sample_r2'] for r in candidates], color=colour['pick'])
            axes[1, 2].set_ylabel('In-sample R²'); axes[1, 2].set_xlabel('Basket recipe')
            axes[1, 2].set_title('Short-window basket fits · no CV evidence')
        date_format = '%d %b' if (frame.index[-1] - frame.index[0]).days < 150 else '%b %y'
        for ax in (axes[1, 0], axes[1, 1]):
            ax.xaxis.set_major_locator(_mdates.AutoDateLocator(maxticks=6))
            ax.xaxis.set_major_formatter(_mdates.DateFormatter(date_format))
        figures.append(('PCA, fitted hedge behaviour and basket-size sensitivity', fig))

        fig2, ax2 = plt.subplots(1, 2, figsize=(13, 4.2))
        ax2[0].barh([c.split(' ')[0] for c in weights.index], weights.values*100,
                     color=[colour['hedged'] if x >= 0 else colour['target'] for x in weights])
        ax2[0].invert_yaxis(); ax2[0].axvline(0, color='#b6c8c2', lw=.8)
        ax2[0].set_xlabel('Per $100 target · positive SHORT, negative LONG')
        ax2[0].set_title('Current basket hedge weights')
        candidates = result.get('basket_comparison') or []
        use_cv = any(np.isfinite(r['cv_r2']) for r in candidates)
        field = 'cv_r2' if use_cv else 'in_sample_r2'
        ax2[1].bar([str(r['number']) for r in candidates], [r[field] for r in candidates],
                   color=[colour['hedged'] if r['selected'] else colour['other'] for r in candidates])
        for i, candidate in enumerate(candidates):
            value = candidate[field]
            if np.isfinite(value):
                ax2[1].annotate(f'{value:.3f}', (i, value), xytext=(0, 4 if value >= 0 else -12),
                                textcoords='offset points', ha='center', fontsize=8)
        ax2[1].margins(y=.12)
        ax2[1].axhline(0, color='#b6c8c2', lw=.8); ax2[1].set_xlabel('Basket recipe · teal selected')
        ax2[1].set_ylabel('Mean CV R²' if use_cv else 'In-sample R²')
        ax2[1].set_title('Alternative baskets · selection diagnostic')
        figures.append(('Basket weights and alternative-basket comparison', fig2))

        rolling = result.get('rolling_oos')
        if isinstance(rolling, pd.DataFrame) and len(rolling) and rolling['te_roll'].notna().any():
            fig3, ax3 = plt.subplots(2, 1, figsize=(13, 6), sharex=True)
            ax3[0].plot(rolling.index, rolling['te_roll']*100, color=colour['hedged'])
            threshold = result['ticket'].get('selected_config_worst_window_te', np.nan)
            if np.isfinite(threshold):
                ax3[0].axhline(threshold*100, color='#b28b4c', ls='--', label='Selected-config worst window')
                ax3[0].axhline(threshold*150, color=colour['target'], ls='--', label='Monitoring threshold (1.5× heuristic)')
                ax3[0].legend(loc='lower left'); ax3[0].margins(y=.22)
            ax3[0].set_title('Rolling regression tracking error · selected configuration')
            ax3[0].set_ylabel('Annualised error (%)')
            ax3[1].plot(rolling.index, rolling['r2_roll'], color=colour['pick'])
            pooled = result.get('selected_unseen_pooled_r2', np.nan)
            if np.isfinite(pooled):
                ax3[1].axhline(pooled, color='#97aaa4', ls='--', label='Selected-config pooled R²')
                ax3[1].legend(loc='lower left')
            ax3[1].axhline(0, color='#bccbc6', lw=.8)
            ax3[1].set_title('Rolling tracking R² · negative values remain visible')
            ax3[1].set_ylabel('R²')
            ax3[1].xaxis.set_major_locator(_mdates.AutoDateLocator(maxticks=8))
            ax3[1].xaxis.set_major_formatter(_mdates.DateFormatter('%b %y'))
            figures.append(('Rolling stability · conditional on the selected configuration', fig3))
        for _, figure in figures:
            for ax in figure.axes:
                ax.title.set_color('#315a69'); ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
            figure.tight_layout(pad=1.6)
    return figures


def _report_chart_assets(result, show=False):
    import base64
    import io
    assets = []
    for title, figure in _report_figures(result):
        try:
            buffer = io.BytesIO()
            figure.savefig(buffer, format='png', dpi=170, bbox_inches='tight', facecolor='white')
            assets.append({'title': title, 'png': base64.b64encode(buffer.getvalue()).decode('ascii')})
            if show:
                import warnings
                plt.figure(figure.number)
                with warnings.catch_warnings():
                    warnings.filterwarnings('ignore', message='FigureCanvasAgg is non-interactive.*', category=UserWarning)
                    plt.show()
        finally:
            plt.close(figure)
    return assets


def _report_number(value, percent=False):
    if value is None or not np.isfinite(value):
        return '—'
    return f'{value*100:.1f}%' if percent else f'{value:.3f}'


def _market_reference_duplicates_etf(result):
    alternatives = result.get('hedge_alternatives') or {}
    etf, market = alternatives.get('single_etf'), alternatives.get('single_market')
    if etf is None or market is None:
        return False
    return (etf['weights'].equals(market['weights'])
            and np.allclose(etf['unseen_r2'], market['unseen_r2'], equal_nan=True))


def _basket_report_rows(result):
    """Distinct current recipes, ordered by training/CV selection score.

    Alternative outer scores are conditional configuration diagnostics, never
    relabelled as independent nested selection results or new recommendations.
    """
    rows, seen = [], set()
    for entry in result.get('basket_candidates') or []:
        weights = entry.get('w')
        if weights is None or len(weights) < 2:
            continue
        fingerprint = tuple(sorted((t, round(float(x), 5)) for t, x in weights.items()))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        rows.append({'number': len(rows) + 1, 'selected': bool(entry.get('sel')),
                     'weights': weights.copy(), 'lookback': entry['lb'],
                     'method': str(entry['ps']), 'basket_size': len(weights),
                     'cv_r2': float(entry['cfg'].get('avg_r2_oos', np.nan)),
                     'conditional_r2': entry.get('r2m', np.nan),
                     'conditional_vol_reduction': entry.get('vrm', np.nan),
                     'n_windows': entry.get('n', 0),
                     'in_sample_r2': entry.get('r2_in', np.nan),
                     'cv_std': entry['cfg'].get('std_r2_oos', np.nan),
                     'cv_vol_cut': entry['cfg'].get('avg_vol_red', np.nan),
                     'rolling': entry.get('roll') or {},
                     'gross': float(weights.abs().sum())})
    return rows



def _report_method(spec):
    label = str(spec)
    if label in ('forward', 'correlation'):
        return {'forward': 'Forward selection', 'correlation': 'Correlation'}[label]
    if label == 'auto':
        return 'PCA auto PCs'
    if label.startswith('single:'):
        return 'Single instrument'
    return f'PCA {label} PCs'

def _report_blocks(result):
    """Shared notebook and Word analysis, with explicit evidence sources."""
    blocks = []
    def title(text): blocks.append(dict(kind='title', text=text))
    def section(text): blocks.append(dict(kind='section', text=text))
    def text(value, muted=False): blocks.append(dict(kind='text', text=value, muted=muted))
    def table(headers, rows, label=None, widths=None):
        if rows:
            blocks.append(dict(kind='table', headers=headers, rows=rows, title=label, widths=widths))
    def recipe(weights, label=None):
        table(['ACTION', 'PER $100 TARGET', 'INSTRUMENT'], [
            ['SHORT' if x > 0 else 'LONG', f'${abs(x)*100:.1f}', t]
            for t, x in weights.sort_values(key=lambda x: -x.abs()).items()], label, [1.0, 1.35, 4.65])
    p, t = result['params'], result['ticket']
    fmt = _report_number
    risk = result.get('trade_risk') or {}
    span = result.get('analysis_span')
    window = p.get('sample_window') or 'all downloaded history'
    title(f"Hedge analysis for {result['target_label']}")
    if result.get('illustrative_sample'):
        text('ILLUSTRATIVE SAMPLE — simulated prices and instruments, not live market data or a hedge recommendation.')
    if span:
        text(f"Analysis window {window} · {span[0]:%d %b %Y} to {span[1]:%d %b %Y} · {span[2]} return rows", True)
    if result.get('report_charts'):
        section('Charts')
        for chart in result['report_charts']:
            blocks.append(dict(kind='chart', **chart))
        section('Summary')
    text(t['grade'])
    for reason in t.get('reasons') or []:
        text(reason)
    table(['EVIDENCE', 'UNSEEN R²', 'VOLATILITY CUT', 'IN-SAMPLE R²'], [[
        result['validation_mode'], fmt(t.get('quality_r2')),
        fmt(risk.get('vol_reduction'), True), fmt(result.get('in_sample_r2'))]])
    scope = 'Peers only' if p['candidate_scope'] == 'peers' else 'All eligible candidates'
    if p['candidate_scope'] == 'peers' and p['include_broad_market']:
        scope = 'Peers plus local market ETF'
    text(f"Universe: {scope} · Basket sizes: {', '.join(map(str, result['requested_basket_sizes']))}", True)
    section(('Primary basket' if result['primary_hedge_family'] == 'basket' else 'Pinned hedge reference')
            if result.get('trade_eligible') else 'Candidate recipe — not approved')
    if result.get('fallback_reason'):
        text(result['fallback_reason'])
    recipe(result['weights'])
    text(f"Gross hedge ${result['weights'].abs().sum()*100:.1f} per $100 target · "
         f"Net hedge coefficient {result['weights'].sum():+.3f} · "
         f"Method {_report_method(p.get('pc_spec'))} · Training rows {p.get('lookback')}", True)

    summary = result.get('cv_summary')
    if isinstance(summary, pd.DataFrame) and len(summary) and 'avg_vol_red' in summary:
        current = summary[(summary['lookback'] == p['lookback']) &
                          (summary['pc_spec'].astype(str) == str(p['pc_spec'])) &
                          (summary['basket_size'] == p['basket_size'])]
        if len(current):
            selected = current.iloc[0]
            table(['TRAINING SELECTION DIAGNOSTIC', 'VALUE'], [
                ['Mean CV volatility reduction', fmt(selected.get('avg_vol_red'), True)],
                ['CV volatility reduction standard deviation', fmt(selected.get('std_vol_red'), True)],
                ['Mean CV tracking R²', fmt(selected.get('avg_r2_oos'))],
                ['Recent CV tracking R²', fmt(selected.get('recent_r2'))],
                ['Recent CV volatility reduction', fmt(selected.get('recent_vol_red'), True)],
                ['Selection score after penalties', fmt(selected.get('composite'))]])
            text('These CV scores selected the current configuration; the independent evaluation appears below. '
                 'The score is a ranking heuristic, not a probability or confidence bound.', True)
    section('Validation and residual risk')
    mode = result['validation_mode']
    text(f"{mode}: {TIER_MEANING.get(mode, 'inspect the available validation evidence')}", True)
    quality = t.get('quality_r2')
    if quality is not None and np.isfinite(quality) and quality < 0:
        text('Negative unseen tracking R²: prediction errors exceeded the test-period average-return '
             'benchmark. This candidate is not a recommended hedge.')
    if risk.get('n_observations'):
        table(['RISK MEASURE', 'VALUE'], [
            ['Unhedged target volatility annualised', fmt(risk.get('unhedged_vol_ann'), True)],
            ['Coefficient-only spread volatility annualised', fmt(risk.get('hedged_vol_ann'), True)],
            ['Volatility reduction', fmt(risk.get('vol_reduction'), True)],
            ['Variance reduction', fmt(risk.get('variance_reduction'), True)],
            ['Mean spread return per observation', f"{risk['spread_mean_per_observation']*1e4:+.1f} bp"],
            ['Scored unseen observations', risk.get('n_observations', '—')]])
    nested = result.get('nested_validation')
    if isinstance(nested, pd.DataFrame) and len(nested):
        table(['TEST DATES', 'ROWS IN FIT', 'NAMES', 'UNSEEN R²', 'VOL CUT'], [
            [f"{row['start']:%d %b %y}–{row['end']:%d %b %y}", row['lookback'], row['basket_size'],
             fmt(row['r2_oos']), fmt(row['vol_red_oos'], True)]
            for _, row in nested.sort_values('start').iterrows()], 'Nested selection windows', [2.0, 1.25, .7, 1.5, 1.55])
        text('Each nested window repeats selection and fitting using earlier data. The headline R² pools '
             'the unseen errors; it is not the average of these window scores.', True)
    elif np.isfinite(result.get('holdout_r2', np.nan)):
        text(f"One reserved holdout: R² {fmt(result['holdout_r2'])}. This is limited evidence from one test period.", True)
    else:
        text('No complete unseen validation is available. The fitted basket is a reference for further investigation.', True)
    if np.isfinite(t.get('worst_window_r2', np.nan)):
        text(f"Worst nested window R² {fmt(t['worst_window_r2'])} · "
             f"Worst nested window tracking error {fmt(t.get('worst_window_te'), True)} annualised", True)
    boot = result.get('bootstrap_ci')
    if boot:
        text(f"Nested R² 95% block-bootstrap interval [{boot['r2_lo']:.3f}, {boot['r2_hi']:.3f}]. "
             'It resamples the observed errors and does not rerun model selection or establish future certainty.', True)
    adj = result.get('in_sample_r2_adj', np.nan)
    if np.isfinite(adj):
        text(f"Adjusted fitted complexity score {adj:.3f}: nominal regressor-count penalty, "
             'not Ridge effective degrees of freedom or unseen evidence.', True)

    candidates = result.get('basket_comparison') or []
    if candidates:
        section('Alternative baskets')
        text(f"{sum(not row['selected'] for row in candidates)} distinct alternatives available · "
             f"Requested up to {p.get('alternative_baskets', 5)}. Repeated recipes are removed.", True)
        if mode in ('IN-SAMPLE', 'HOLDOUT'):
            text('Short-window baskets are ranked on fitted training data; the reserved holdout, when '
                 'available, is not used to rank alternatives. No CV or independent alternative scores exist.', True)
            table(['BASKET', 'NAMES', 'TRAINING ROWS', 'METHOD', 'IN-SAMPLE R²'], [
                [str(row['number']) + (' selected' if row['selected'] else ''), row['basket_size'],
                 row['lookback'], _report_method(row['method']), fmt(row['in_sample_r2'])] for row in candidates])
        else:
            text('Ranked using training and CV data. Diagnostic R² is the mean of fixed-configuration '
                 'test windows; selection bias remains. A displayed alternative is not independently approved.', True)
            table(['BASKET', 'NAMES', 'METHOD', 'CV VOL CUT', 'CV R²', 'DIAGNOSTIC R²'], [
                [str(row['number']) + (' selected' if row['selected'] else ''), row['basket_size'],
                 _report_method(row['method']), fmt(row['cv_vol_cut'], True), fmt(row['cv_r2']), fmt(row['conditional_r2'])]
                for row in candidates], widths=[1.2, .6, 1.5, 1.1, 1.0, 1.6])
        for row in candidates:
            if row['selected']:
                continue
            recipe(row['weights'], f"Alternative basket {row['number']}")
            text(f"Training rows {row['lookback']} · Gross {row['gross']:.2f}× · Fitted R² {fmt(row['in_sample_r2'])} · "
                 + (f"Diagnostic mean vol cut {fmt(row['conditional_vol_reduction'], True)} · "
                    f"Complete diagnostic windows {row['n_windows']}" if mode not in ('IN-SAMPLE', 'HOLDOUT')
                    else 'Fitted training reference only'), True)

    section('Best basket and single-instrument hedges')
    text('The basket is the primary hedge; single instruments are references. Scores use the same '
         'test periods and repeat each family’s selection before the test.', True)
    text(result['market_reference_status'], True)
    for family, label in [('single_stock', 'Best single stock'), ('single_etf', 'Best single ETF'),
                          ('single_market', 'Local broad market ETF')]:
        if _market_reference_duplicates_etf(result):
            if family == 'single_market': continue
            if family == 'single_etf': label = 'Best single ETF and local market reference'
        item = result.get('hedge_alternatives', {}).get(family)
        if item is None:
            if family != 'single_market': text(label + ': unavailable under these settings', True)
            continue
        table(['ACTION', 'PER $100', 'INSTRUMENT', 'UNSEEN R²', 'VOL CUT'], [
            ['SHORT' if x > 0 else 'LONG', f'${abs(x)*100:.1f}', name, fmt(item['unseen_r2']),
             fmt(item['trade_risk'].get('vol_reduction'), True)] for name, x in item['weights'].items()],
            label, [.8, 1.0, 3.0, 1.1, 1.1])
        text(item['status'], True)

    section('Stability and recent conditions')
    roll = result.get('rolling_stats') or {}
    if roll:
        table(['SELECTED CONFIGURATION', 'LATEST', 'MEDIAN', 'WORST'], [
            ['Rolling tracking R²', fmt(roll.get('r2_latest')), fmt(roll.get('r2_median')), fmt(roll.get('r2_worst'))],
            ['Rolling regression tracking error', fmt(roll.get('te_latest'), True), fmt(roll.get('te_median'), True), fmt(roll.get('te_worst'), True)]],
            widths=[2.8, 1.4, 1.4, 1.4])
        text(f"{roll['n_days']} scored rows · {roll['n_segments']} refits · {roll['n_skipped']} skipped segments. "
             'Rolling weights are fitted before each segment; the configuration was selected using the full analysis window.', True)
        frame = result['rolling_oos']
        spread_vol = frame.get('spread_vol_roll', pd.Series(dtype=float)).dropna()
        if len(spread_vol):
            text(f"Latest rolling coefficient-only spread volatility {fmt(spread_vol.iloc[-1], True)} annualised. "
                 'Regression error removes a fitted intercept and can differ across refits.', True)
    else:
        text('Rolling stability is unavailable or disabled; short windows may have insufficient history.', True)
    now = result.get('nowcast') or {}
    if now:
        text(f"Condition flag {now['condition']} · Latest selected-configuration test R² {fmt(now.get('latest_window_r2'))}. "
             'This descriptive flag is a heuristic; its signals can be related.', True)
        for reason in now.get('why') or []: text(reason, True)
    turn = result.get('turnover') or {}
    if turn:
        text(f"Name overlap {fmt(turn['mean_jaccard'], True)} · Coefficient similarity {fmt(turn['mean_cosine'])} · "
             f"{turn['n_refits']} refits. These measure stability, not execution costs.", True)
    decay = result.get('decay') or {}
    if decay:
        table(['WEIGHT AGE ROWS', 'TRACKING ERROR ANNUALISED'],
              [[age, fmt(te, True)] for age, te in decay['te_by_interval']], 'Weight staleness on matched dates')
        text(f"Compared on {decay['n_rows']} common rows. Indicative refit interval {decay['rec_rows']} rows "
             'uses a 15% deterioration threshold, a chosen heuristic.', True)

    section('Remaining exposures and downside behaviour')
    factors = result.get('factor_leakage')
    if isinstance(factors, pd.DataFrame) and len(factors):
        table(['FACTOR', 'TARGET BETA', 'SPREAD BETA'], [
            [r['factor'], f"{r['target_beta']:+.3f}", f"{r['residual_beta']:+.3f}"]
            for _, r in factors.iterrows()])
        text('Fitted diagnostic using sequentially orthogonalised factors from this universe. '
             'Betas depend on factor construction and ordering; they are not causal or unseen estimates.', True)
    else:
        text('Factor diagnostics unavailable: too few eligible factor instruments or stock peers.', True)
    exposure = result.get('exposures') or {}
    if exposure.get('tags'):
        text('Taxonomy exposures: ' + ', '.join(exposure['tags']), True)
    if exposure.get('unresolved'):
        text('Missing mapped exposure instruments: ' + ', '.join(sorted(exposure['unresolved'])), True)
    tail = result.get('asymmetry') or {}
    if tail:
        text(f"Fitted spread on target’s worst 10% of observations: {tail['worst_decile_mean']*1e4:+.1f} bp "
             f"vs {tail['best_decile_mean']*1e4:+.1f} bp on its best 10% · {tail['n_worst']} worst observations. "
             'Descriptive tail averages do not establish crisis protection.', True)
    path = result.get('path') or {}
    if path:
        text(f"Spread path drawdown {fmt(path['max_drawdown'], True)} · Source {path['source']} · "
             f"{path['n_observations']} non-overlapping observations. A log-spread proxy, not financed portfolio P&L.", True)
        if np.isfinite(path.get('worst_5d', np.nan)):
            text(f"Worst five-day spread proxy {fmt(path['worst_5d'], True)}", True)
    if not tail and not path:
        text('Tail and path statistics unavailable for this run.', True)

    section('Search settings and data quality')
    search = result.get('search') or {}
    table(['SETTING', 'THIS RUN'], [
        ['Candidate scope', scope],
        ['Selection objective', 'Volatility reduction' if p['hedge_objective'] == 'variance' else 'Return tracking with risk reduction'],
        ['Recency weighting', p.get('recency_weight', 0)],
        ['Configurations scored', search.get('configurations_scored', '—')],
        ['Single instruments scored as references', search.get('single_instruments_scored', '—')],
        ['Basket search methods', ', '.join(search.get('basket_methods') or [])],
        ['PCA covariance', p.get('robust_cov', '—')],
        ['PCA selection outlier clipping', fmt(p.get('winsorize_pct'), True)],
        ['Gross penalty and cap', f"{p.get('gross_penalty', 0):g} per 1×; cap {p.get('max_gross') or 'off'}"],
        ['Returns', 'Overlapping two-day observations' if result.get('two_day_returns') else 'Daily observations'],
        ['Historical size and membership filters', f"Size {'active' if result.get('pit_size_active') else 'inactive'}; "
         f"membership {'active' if result.get('pit_members_active') else 'inactive'}"]])
    affected = False
    for field, label in [('training_data_diagnostics', 'Training'), ('evaluation_data_diagnostics', 'Validation')]:
        audit = result.get(field)
        if isinstance(audit, pd.DataFrame) and len(audit):
            affected = True
            text(f"{label}: {len(audit)} data-quality audit records. Missing target observations "
                 'use a common date mask; incomplete candidate windows remain failures. Full dates and reasons are retained in result diagnostics.', True)
    if not affected: text('No missing-target window audit records on this run.', True)
    removed = result.get('excluded') or []
    if removed: text(f"Excluded instruments: {len(removed)}; retained in result['excluded'].", True)
    text('Search is limited to the supplied eligible universe and tested configurations. PCA finds shared '
         'return directions; it does not guarantee the best possible hedge. Unseen evaluation is kept separate '
         'from the data used to select the current recipe.', True)
    text('Alternative basket scores retain selection bias. Prices use each instrument’s own currency; '
         'costs, borrow, financing and FX conversion are not modelled. Current universe discovery can introduce '
         'survivorship bias even when historical filters are enabled.', True)
    text(f"Engine revision {result.get('engine_revision')}", True)
    return _tidy_report_blocks(blocks)


_BRIEF_METHODOLOGY = (
    'In-sample R² describes the current training fit; unseen scores test earlier selection and refitting. '
    'Alternative and rolling scores are conditional diagnostics. Spread paths approximate log-return hedges; '
    'costs, borrow, financing and FX conversion are excluded. Factor, condition and refit-interval diagnostics are descriptive.')


def _tidy_report_blocks(blocks):
    """Keep information visible and gather repeated explanations in one place."""
    result, notes = [], []
    explanatory = ('These CV scores selected', 'Each nested window repeats',
                   'Fitted diagnostic using sequentially', 'Search is limited to',
                   'Alternative basket scores retain', 'Engine revision')
    splits = ('. It resamples', ': nominal regressor-count', '. Regression error',
              '. This descriptive flag', '. These measure stability',
              '. Descriptive tail averages', '. A log-spread proxy')
    for original in blocks:
        block = dict(original)
        if block['kind'] != 'text':
            if block.get('headers') == ['FACTOR', 'TARGET BETA', 'SPREAD BETA']:
                block['title'] = 'Factor exposure in the current fit'
            result.append(block)
            continue
        value = block['text']
        if value.startswith(explanatory):
            notes.append(value)
            continue
        if value.startswith('Ranked using training and CV data.'):
            notes.append(value)
            block['text'] = 'Training and CV ranking · Alternative test scores are conditional diagnostics.'
        elif value.startswith('Short-window baskets are ranked'):
            notes.append(value)
            block['text'] = 'Training-fit ranking · Short-window alternatives are indicative.'
        elif value.startswith('The basket is the primary hedge;'):
            notes.append(value)
            block['text'] = 'The basket is the primary hedge; single instruments are references.'
        else:
            for marker in splits:
                if marker in value:
                    left, right = value.split(marker, 1)
                    notes.append(marker.lstrip('. :') + right)
                    block['text'] = left + (' (heuristic)' if marker.startswith(': nominal') else '')
                    break
            if 'Rolling weights are fitted before' in block['text']:
                left, right = block['text'].split('Rolling weights are fitted before', 1)
                block['text'] = left.rstrip('. ')
                notes.append('Rolling weights are fitted before' + right)
            if "retained in result['excluded']" in block['text']:
                block['text'] = block['text'].split(';')[0] + '; full list in diagnostics.'
        result.append(block)
    result.append(dict(kind='notes', text='Methodology and coverage', notes=notes))
    return result


def _render_compact_sections(result):
    for block in _report_blocks(result):
        if block['kind'] in ('title', 'section'):
            _section(block['text'].upper())
        elif block['kind'] == 'text':
            _P(block['text'])
        elif block['kind'] == 'chart':
            _P(block['title'])
        elif block['kind'] == 'notes':
            _section(block['text'].upper())
            for note in block['notes']:
                _P(note)
        else:
            _print_table(block['headers'], block['rows'], title=block.get('title'))


def _report_html(result):
    """A self-contained report with a quiet palette and one expandable notes area."""
    escape = lambda value: _html.escape(str(value))
    css = '''
.pca-sheet{font-family:Aptos,"Segoe UI","Helvetica Neue",Arial,sans-serif;color:#263c48;background:#fff;max-width:1060px;margin:16px auto;padding:28px 32px;border:1px solid #e1e8e6;border-radius:12px;line-height:1.5;box-sizing:border-box}
.pca-sheet h1{font-size:28px;line-height:1.2;font-weight:650;letter-spacing:-.4px;color:#203d47;margin:0 0 14px}
.pca-sheet h2{font-size:19px;color:#226c67;font-weight:650;margin:28px 0 12px;letter-spacing:-.15px}
.pca-sheet p{font-size:14px;margin:8px 0;color:#344d58}.pca-sheet .meta{color:#637780;font-size:13px}
.pca-sheet .verdict{display:inline-block;font-size:13px;font-weight:650;border-radius:5px;padding:7px 12px;background:#edf5f2;color:#27695b;margin:8px 0}.pca-sheet .caution{background:#fbf3e2;color:#806124}.pca-sheet .failed{background:#faeeeb;color:#9a4c3c}
.pca-sheet .sample{background:#fbf3e2;padding:10px 14px;border-radius:6px;font-size:13px;color:#806124}
.pca-sheet .metric-grid{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:12px;margin:18px 0 16px}
.pca-sheet .metric{padding:14px 16px;border:1px solid #dde8e5;border-radius:8px;background:#f5f9f8}.pca-sheet .metric-label{font-size:11px;letter-spacing:.55px;color:#567470;font-weight:600}.pca-sheet .metric-value{font-size:27px;line-height:1.25;font-weight:600;color:#205d58;margin-top:7px}.pca-sheet .metric:first-child .metric-value{font-size:19px;margin-top:11px}
.pca-sheet .table-wrap{overflow-x:auto;margin:8px 0 16px}.pca-sheet table{width:100%;border-collapse:collapse;font-size:14px;line-height:1.45}.pca-sheet th{text-align:left;background:#eaf2f1;color:#315e5a;font-size:11px;font-weight:650;letter-spacing:.4px;padding:10px 12px;white-space:nowrap;border-bottom:1px solid #d1e1de}.pca-sheet td{padding:9px 12px;border-bottom:1px solid #e7eeec;vertical-align:top}.pca-sheet tr:nth-child(even) td{background:#f8faf9}.pca-sheet td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.pca-sheet tr.selected td{background:#edf6f2}.pca-sheet caption{text-align:left;font-size:14px;font-weight:600;color:#334f58;padding:8px 0 9px}
.pca-sheet .chart{margin:20px 0}.pca-sheet .chart img{width:100%;height:auto;display:block}.pca-sheet figcaption{font-size:14px;font-weight:600;color:#334f58;margin-bottom:8px}
.pca-sheet details{margin-top:26px;border-top:1px solid #dce7e4;padding:16px 0 0;color:#60757c}.pca-sheet summary{cursor:pointer;font-size:13px;font-weight:600;color:#426c66}.pca-sheet details p{font-size:13px;color:#60757c;margin:12px 0}
@media(max-width:680px){.pca-sheet{padding:20px 16px}.pca-sheet .metric-grid{grid-template-columns:repeat(2,1fr)}}
'''
    parts = ['<style>'+css+'</style><article class="pca-sheet">']
    for block in _report_blocks(result):
        kind = block['kind']
        if kind == 'title':
            parts.append('<h1>'+escape(block['text'])+'</h1>')
        elif kind == 'section':
            parts.append('<h2>'+escape(block['text'])+'</h2>')
        elif kind == 'chart':
            parts.append('<figure class="chart"><figcaption>'+escape(block['title'])+'</figcaption>'
                         '<img alt="'+escape(block['title'])+'" src="data:image/png;base64,'+block['png']+'"></figure>')
        elif kind == 'notes':
            parts.append('<details><summary>Methodology and coverage</summary>')
            parts.extend('<p>'+escape(note)+'</p>' for note in block['notes'])
            parts.append('</details>')
        elif kind == 'text':
            value = block['text']
            style = 'meta' if block.get('muted') else ''
            if value.startswith(('✓','△','✗','?')):
                style = 'verdict' + (' caution' if value.startswith(('△','?')) else ' failed' if value.startswith('✗') else '')
            elif value.startswith('ILLUSTRATIVE SAMPLE'):
                style = 'sample'
            parts.append(f'<p class="{style}">'+escape(value)+'</p>')
        elif block['headers'] == ['EVIDENCE', 'UNSEEN R²', 'VOLATILITY CUT', 'IN-SAMPLE R²']:
            labels = ['Evidence', 'Unseen R²', 'Unseen volatility cut', 'In-sample R²']
            parts.append('<div class="metric-grid">')
            for label, value in zip(labels, block['rows'][0]):
                parts.append('<div class="metric"><div class="metric-label">'+escape(label.upper())+
                             '</div><div class="metric-value">'+escape(value)+'</div></div>')
            parts.append('</div>')
        else:
            parts.append('<div class="table-wrap"><table>')
            if block.get('title'):
                parts.append('<caption>'+escape(block['title'])+'</caption>')
            parts.append('<thead><tr>'+''.join('<th>'+escape(h)+'</th>' for h in block['headers'])+'</tr></thead><tbody>')
            for row in block['rows']:
                chosen = 'selected' if 'selected' in str(row[0]) else ''
                parts.append(f'<tr class="{chosen}">')
                for value in row:
                    is_number = bool(re.fullmatch(r'[+$−\-]?\d+(?:[.,]\d+)*(?:%|×)?', str(value)))
                    parts.append('<td'+(' class="num"' if is_number else '')+'>'+escape(value)+'</td>')
                parts.append('</tr>')
            parts.append('</tbody></table></div>')
    parts.append('</article>')
    return ''.join(parts)


def _render_compact_report(result):
    global _IN_JUPYTER
    if not _IN_JUPYTER:
        return _render_compact_sections(result)
    import contextlib
    import io
    old = _IN_JUPYTER
    printed = io.StringIO()
    _IN_JUPYTER = False
    try:
        # Keep the complete export transcript and collect the console copy.
        with contextlib.redirect_stdout(printed):
            _render_compact_sections(result)
    finally:
        _IN_JUPYTER = old
    try:
        # Charts and the styled report lead the notebook output.
        _ipy_display(_HTML(_report_html(result)))
    except Exception:
        # A rich-display failure must not hide a completed analysis.
        pass
    text = printed.getvalue()
    notes_header = (f"\n{'═' * _TXT_W}\n METHODOLOGY AND COVERAGE\n"
                    f"{'═' * _TXT_W}\n")
    body, separator, _ = text.partition(notes_header)
    if separator:
        text = body + separator + '\n'.join(
            '  ' + line for line in _textwrap.wrap(_BRIEF_METHODOLOGY, _TXT_W - 4)) + '\n'
    print(text, end='')



from functools import wraps as _wraps


@_wraps(_find_best_hedge_impl)
def find_best_hedge(*args, **kwargs):
    """Existing API with a structured default report and an optional diagnostic log."""
    import contextlib
    import inspect
    import io
    global _IN_JUPYTER
    bound = inspect.signature(_find_best_hedge_impl).bind(*args, **kwargs)
    bound.apply_defaults()
    options = bound.arguments
    if options['report'] not in ('compact', 'full'):
        raise ValueError("report must be 'compact' or 'full'")
    compact = options['report'] == 'compact'
    old_jupyter, capture = _IN_JUPYTER, io.StringIO()
    if compact:
        _IN_JUPYTER = False
    try:
        from IPython.utils.capture import capture_output
    except ImportError:
        capture_output = None
    rich_capture = (capture_output(stdout=False, stderr=False, display=True)
                    if compact and capture_output else contextlib.nullcontext())
    try:
        with rich_capture as rich:
            with contextlib.redirect_stdout(capture) if compact else contextlib.nullcontext():
                result = _find_best_hedge_impl(*args, **kwargs)
    finally:
        _IN_JUPYTER = old_jupyter
    result['full_report'] = transcript_text()
    result['diagnostic_log'] = capture.getvalue() if compact else result['full_report']
    scope = options['candidate_scope']
    market = options['include_broad_market']
    market = scope == 'all' if market is None else bool(market)
    result['params'].update(candidate_scope=scope, include_broad_market=market,
                            peer_tickers=options['peer_tickers'],
                            basket_size_range=options['basket_size_range'],
                            restrict_to_target_tz=options['restrict_to_target_tz'],
                            exclude=options['exclude'],
                            alternative_baskets=options['alternative_baskets'],
                            show_plots=options['show_plots'])
    result['requested_basket_sizes'] = _basket_sizes(options['basket_size_options'], options['basket_size_range'])
    result['basket_comparison'] = _basket_report_rows(result)
    result['broad_markets'] = [_broad_market_spec(t) for t in result['portfolio_legs']]
    result['broad_market_hedge'] = result.get('hedge_alternatives', {}).get('single_market')
    benchmark = '; '.join(dict.fromkeys(m['benchmark'] for m in result['broad_markets']))
    if not market:
        status = 'Local broad market ETF: disabled for this run'
    elif result['broad_market_hedge'] is not None:
        status = 'Local broad market ETF: ' + benchmark
    else:
        status = 'Local broad market ETF unavailable after data and eligibility filters: ' + benchmark
    result['market_reference_status'] = status
    if options['show_plots']:
        result['report_charts'] = _report_chart_assets(result, show=compact and not old_jupyter)
    if compact:
        transcript_reset()
        _kv_reset()
        _render_compact_report(result)
        for output in getattr(rich, 'outputs', ()):
            output.display()
    result['report_text'] = transcript_text()
    return result


# ── [Fix 63] FAST RE-HEDGE — for books that change daily ────────────────────
# An index-rebalance book churns as predictions update, and re-running the
# full grid plus nested validation for every intraday change is overkill: the
# expensive part is CONFIG SELECTION, and the config does not change from one
# day to the next. quick_rehedge pins the config that was already validated
# and refits the weights only — seconds, and zero Bloomberg calls. Re-run the
# full find_best_hedge weekly, or whenever the book changes materially.
def quick_rehedge(book, data, prev_result, show_plots=True, rolling_oos=True,
                  full_validation=False):
    """Refit hedge weights for an updated book using a previously VALIDATED
    config. `prev_result` is the dict returned by a full find_best_hedge run.

    The config is NOT re-searched — that is the point of this path, and it is
    what makes it seconds instead of minutes. What you can choose:

      show_plots       draw the charts (default True)
      rolling_oos      compute the rolling walk-forward curve (default True)
      full_validation  re-run the same number of validation windows as a full
                       run (3 outer × 5 inner) instead of the fast 1 × 2

    [Fix 115] show_plots and rolling_oos used to be hard-wired OFF here, so a
    re-hedge silently dropped every chart the full run had drawn and reported
    a single outer window with no explanation of why. Both are now the
    caller's choice, defaulting ON, and the report says in [0] exactly what
    was and was not re-validated.
    """
    p = prev_result['params']
    return find_best_hedge(
        book, data=data,
        lookback_options=(p['lookback'],),
        pc_options='auto' if p['pc_spec'] == 'auto' else [p['pc_spec']],
        broad_search=False,
        candidate_scope=p.get('candidate_scope', 'all'),
        include_broad_market=p.get('include_broad_market'),
        peer_tickers=p.get('peer_tickers'),
        basket_size_range=(p['basket_size'], p['basket_size']) if p.get('basket_size_range') else None,
        basket_size_options=(p['basket_size'],),
        min_mktcap_usd_mm=p['min_mktcap_usd_mm'],
        tz_tolerance_hours=p['tz_tolerance_hours'],
        gross_penalty=p['gross_penalty'], max_gross=p['max_gross'],
        force_include=p['force_include'],
        winsorize_pct=p['winsorize_pct'], robust_cov=p['robust_cov'],
        pit_size=p['pit_size'], pit_members=p['pit_members'],
        size_band=p['size_band'], size_override=p['size_override'],
        mask_stale_days=p.get('mask_stale_days', 7),
        notional_mm=p.get('notional_mm'),              # [Fix 72]
        hedge_objective=p.get('hedge_objective', 'variance'),
        boot_n=p.get('boot_n', 2000),                  # [Fix 70]
        rolling_oos=rolling_oos,                       # [Fix 71]
        sample_window=p.get('sample_window'),          # [Fix 76]
        hedge_horizon_days=p.get('hedge_horizon_days'),  # [Fix 91]
        horizon_sets_windows=p.get('horizon_sets_windows', False),
        report=p.get('report', 'compact'),             # [Fix 79]
        cv_n_folds=5 if full_validation else 2,
        outer_folds=3 if full_validation else 1,
        show_plots=show_plots,
        _rehedge_of=prev_result)                       # [Fix 115] for the note


# =============================================================================
# CELL 3: FRONT END — [Fix 89/95/96] hedge_ui()
# =============================================================================
# A point-and-click form covering EVERY engine option, so the tool is driven
# without reading or editing code. It is a THIN layer: each button calls the
# same download_hedge_data / find_best_hedge / quick_rehedge a code user
# would call, with the same arguments — the model, validation and report are
# byte-for-byte identical to the scripted path. The form only assembles
# arguments; it never re-implements logic.
#
# What it gives you beyond the scripted path:
#   · live preview of the validation tier for the chosen window BEFORE a run
#     (engine's own _validation_tier, [Fix 85] — cannot drift);
#   · cached downloads with a live fit check ([Fix 88/90]) — it refuses to
#     run when a leg was never downloaded, and flags stale prices;
#   · one-click EXPORT of weights (CSV), the full report (TXT) and the run
#     settings (JSON) under hedge_reports/;
#   · RE-HEDGE (fast): quick_rehedge pinned to the last validated config;
#   · "Show code": the exact scripted equivalent of any run, so nothing done
#     in the GUI is unreproducible;
#   · results always in UI_STATE ('result', 'report_text', 'code').
#
# If ipywidgets is missing it prints the install command and a code template
# instead of failing.
# =============================================================================

UI_STATE = {'data': None, 'result': None, 'code': '', 'report_text': '',
            'loaded_from': None}

_UI_CSS = """
<style>
/* [Fix 96/102] typography + spacing. ipywidgets defaults are cramped and
   mix fonts; this gives one type scale, roomy rows and grouped sections. */
.hedge-ui, .hedge-ui .widget-label, .hedge-ui input, .hedge-ui select,
.hedge-ui textarea, .hedge-ui .widget-button, .hedge-ui .widget-dropdown {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter',
               'Helvetica Neue', Arial, sans-serif !important;
  -webkit-font-smoothing: antialiased;
}
.hedge-ui { color: #1d2b3a; line-height: 1.45; }
.hedge-ui .widget-label {
  font-size: 12.5px !important; color: #33506d !important;
  font-weight: 600 !important; letter-spacing: .01em;
}
.hedge-ui input, .hedge-ui select, .hedge-ui textarea {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif !important;
  font-size: 12.5px !important; color: #16222e !important;
  border: 1px solid #cfd8e3 !important; border-radius: 5px !important;
  padding: 3px 7px !important; background: #fdfefe !important;
}
.hedge-ui input:focus, .hedge-ui textarea:focus, .hedge-ui select:focus {
  border-color: #4a7fb5 !important; outline: none !important;
  box-shadow: 0 0 0 2px rgba(74,127,181,.15) !important;
}
.hedge-ui .widget-hbox, .hedge-ui .widget-vbox { margin: 0 !important; }
.hedge-ui .widget-text, .hedge-ui .widget-dropdown,
.hedge-ui .widget-textarea, .hedge-ui .widget-checkbox,
.hedge-ui .widget-datepicker { margin: 3px 0 !important; }
.hedge-ui .widget-button {
  font-weight: 600 !important; font-size: 12.5px !important;
  border-radius: 5px !important; letter-spacing: .01em;
  margin: 0 8px 0 0 !important;
}
.hedge-ui .p-TabBar-tabLabel, .hedge-ui .lm-TabBar-tabLabel {
  font-size: 13px; font-weight: 650; letter-spacing: .02em;
}
.hedge-ui .p-TabPanel-stackedPanel, .hedge-ui .lm-TabPanel-stackedPanel {
  padding: 6px 10px 10px 10px;
}
.hedge-ui .hui-h {
  font-size: 11px; font-weight: 700; color: #33506d;
  border-bottom: 1px solid #e2e8f0; margin: 16px 0 8px 0;
  padding-bottom: 4px; text-transform: uppercase; letter-spacing: .07em;
}
.hedge-ui .hui-h:first-child { margin-top: 4px; }
.hedge-ui .hui-help {
  font-size: 11.5px; color: #6b7a8c; margin: 0 0 8px 2px;
  line-height: 1.45; max-width: 560px;
}
.hedge-ui .hui-title {
  font-size: 18px; font-weight: 700; color: #16324b;
  letter-spacing: -.01em; margin: 2px 0 1px 0;
}
.hedge-ui .hui-sub {
  font-size: 12px; color: #6b7a8c; margin-bottom: 10px;
}
.hedge-ui .widget-output { margin-top: 8px; }
</style>"""

def _ui_parse_book(text):
    """Parse the target box into a str / list / dict for _coerce_targets.

    One entry per line or comma-separated. 'TICKER' or 'TICKER, weight'.
    A single line with no weight → single-name hedge. Several lines with no
    weights → equal-weight long book. Any weight present → weighted book
    (missing weights default to 1.0)."""
    entries = []
    for raw in str(text).replace(';', '\n').splitlines():
        raw = raw.strip()
        if not raw:
            continue
        if ',' in raw:
            parts = [p.strip() for p in raw.split(',')]
            if len(parts) >= 2 and _ui_isnum(parts[-1]):
                entries.append((' '.join(parts[:-1]).strip(),
                                float(parts[-1])))
                continue
            for p in parts:                      # 'AAPL US, MSFT US'
                if p:
                    entries.append((p, None))
            continue
        bits = raw.split()
        if len(bits) >= 2 and _ui_isnum(bits[-1]):
            entries.append((' '.join(bits[:-1]), float(bits[-1])))
        else:
            entries.append((raw, None))
    if not entries:
        raise ValueError("no ticker entered")
    if len(entries) == 1 and entries[0][1] is None:
        return entries[0][0]
    if all(w is None for _, w in entries):
        return [t for t, _ in entries]
    return {t: (1.0 if w is None else w) for t, w in entries}


def _ui_isnum(s):
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


def _ui_ints(text, default):
    """'3,5,7' → (3, 5, 7); blank → default."""
    vals = [int(float(v)) for v in str(text).replace(' ', '').split(',')
            if v not in ('', None)]
    return tuple(vals) if vals else tuple(default)


def _ui_list(text):
    """'2330 TT, 0050 TT' → ['2330 TT', '0050 TT']; blank → None."""
    vals = [v.strip() for v in str(text).replace('\n', ',').split(',')
            if v.strip()]
    return vals or None


def _ui_code(target, window, kw, loaded_from=None):
    """Render the equivalent Python so any GUI run can be reproduced."""
    def fmt(v):
        return f"'{v}'" if isinstance(v, str) else repr(v)
    lines = ["# equivalent code for this run:"]
    if loaded_from:
        lines.append(f"data = load_hedge_data({fmt(loaded_from)})")
    else:
        lines.append(f"data = download_hedge_data({fmt(target)},"
                     f" min_mktcap_usd_mm={kw.get('min_mktcap_usd_mm', 5000)})")
    args = [f"    {k}={fmt(v)}," for k, v in sorted(kw.items())
            if v is not None]
    if window is not None:
        args.insert(0, f"    sample_window={fmt(window)},")
    lines.append(f"result = find_best_hedge({fmt(target)}, data=data,")
    lines += args
    lines.append(")")
    return '\n'.join(lines)


def _export_folder(out_dir=None):
    """[Fix 103] Resolve the export folder, creating it if possible. Falls
    back to ./hedge_reports when the configured drive is not mapped on this
    machine (e.g. running off-network) — never fails the export."""
    import os as _o
    import re as _r
    want = out_dir or HEDGE_EXPORT_DIR
    # A Windows path such as G:\FIN_COMM\... is a perfectly LEGAL single
    # filename on macOS/Linux, so makedirs would happily create a junk
    # folder whose name contains backslashes instead of failing. Detect the
    # drive-letter form and refuse it off Windows.
    if _o.name != 'nt' and _r.match(r'^[A-Za-z]:[\\/]', want):
        fb = _o.path.join(_o.getcwd(), 'hedge_reports')
        _o.makedirs(fb, exist_ok=True)
        return fb, (f"{want} is a Windows path and this machine is not "
                    f"Windows — wrote to {fb} instead")
    try:
        _o.makedirs(want, exist_ok=True)
        if _o.path.isdir(want):
            return want, None
    except Exception as e:
        err = str(e)
    else:
        err = 'not a directory'
    fb = _o.path.join(_o.getcwd(), 'hedge_reports')
    _o.makedirs(fb, exist_ok=True)
    return fb, (f"{want} is not reachable ({err}) — wrote to {fb} instead; "
                f"map the drive or set HEDGE_EXPORT_DIR")


def _docx_hedge_report(result, report_text, path):
    """Structured desk report. Detailed transcript appendix is opt-in via full report."""
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    doc = Document()
    section = doc.sections[0]
    section.top_margin = section.bottom_margin = Inches(.65)
    section.left_margin = section.right_margin = Inches(.75)
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    base = doc.styles['Normal']
    base.font.name, base.font.size = 'Calibri', Pt(10.5)
    base.font.color.rgb = RGBColor.from_string('243447')
    base.paragraph_format.space_after = Pt(6)
    base.paragraph_format.line_spacing = 1.12
    for style in ('Title', 'Heading 1', 'Heading 2'):
        doc.styles[style].font.name = 'Calibri'
        props = doc.styles[style].element.get_or_add_pPr()
        for border in list(props.findall(qn('w:pBdr'))):
            props.remove(border)
    doc.styles['Title'].font.color.rgb = RGBColor(0, 0, 0)
    doc.styles['Title'].font.size = Pt(24)
    doc.styles['Heading 1'].font.color.rgb = RGBColor.from_string('226C67')
    doc.styles['Heading 1'].font.size = Pt(15)
    doc.styles['Heading 1'].paragraph_format.space_before = Pt(14)
    doc.styles['Heading 1'].paragraph_format.space_after = Pt(6)

    def paragraph(text, muted=False):
        p = doc.add_paragraph(text)
        if muted:
            for run in p.runs:
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor.from_string('5B6B7C')
        return p

    def heading(text):
        return doc.add_paragraph(text, style='Heading 1')

    def table(headers, rows, widths):
        t = doc.add_table(rows=1, cols=len(headers))
        t.autofit = False
        for col, width in zip(t.columns, widths):
            col.width = Inches(width)
        for cell, value in zip(t.rows[0].cells, headers):
            cell.text = str(value)
        for values in rows:
            for cell, value in zip(t.add_row().cells, values):
                cell.text = str(value)
        for row_no, row in enumerate(t.rows):
            tr = row._tr.get_or_add_trPr()
            tr.append(OxmlElement('w:cantSplit'))
            if row_no == 0:
                tr.append(OxmlElement('w:tblHeader'))
            for cell, width in zip(row.cells, widths):
                cell.width = Inches(width)
                props = cell._tc.get_or_add_tcPr()
                shade = OxmlElement('w:shd')
                shade.set(qn('w:fill'), 'E8F1F0' if row_no == 0 else ('F7F9F9' if row_no % 2 else 'FFFFFF'))
                props.append(shade)
                margins = OxmlElement('w:tcMar')
                for edge in ('top', 'left', 'bottom', 'right'):
                    margin = OxmlElement('w:' + edge)
                    margin.set(qn('w:w'), '80')
                    margin.set(qn('w:type'), 'dxa')
                    margins.append(margin)
                props.append(margins)
                for p in cell.paragraphs:
                    p.paragraph_format.space_after = Pt(0)
                    p.paragraph_format.line_spacing = 1.05
                    # Keep short comparison tables intact at a page boundary.
                    p.paragraph_format.keep_with_next = len(t.rows) <= 14 and row_no < len(t.rows) - 1
                    for run in p.runs:
                        run.font.name = 'Calibri'
                        run.font.size = Pt(9.5)
                        run.font.bold = row_no == 0
                        run.font.color.rgb = RGBColor.from_string('22544F' if row_no == 0 else '243447')
        doc.add_paragraph().paragraph_format.space_after = Pt(0)
        return t

    def recipe(weights):
        w = weights.sort_values(key=lambda x: -x.abs())
        table(['Action', 'Per $100 target', 'Instrument'],
              [['SHORT' if x > 0 else 'LONG', f'${abs(x)*100:.1f}', t] for t, x in w.items()],
              [1.0, 1.35, 4.65])

    params = result.get('params') or {}
    report_blocks = _report_blocks(result)
    for block_no, block in enumerate(report_blocks):
        kind = block['kind']
        if kind == 'title':
            p = doc.add_paragraph(block['text'], style='Title')
            p.paragraph_format.space_after = Pt(6)
        elif kind == 'section':
            h = heading(block['text'].replace(' — ', ' ').replace('-', ' '))

        elif kind == 'text':
            p = paragraph(block['text'], muted=block.get('muted', False))
            next_block = report_blocks[block_no + 1] if block_no + 1 < len(report_blocks) else {}
            if (next_block.get('kind') == 'table' and not next_block.get('title')) or next_block.get('kind') == 'text':
                p.paragraph_format.keep_with_next = True
        elif kind == 'chart':
            import base64
            import io
            caption = paragraph(block['title'])
            caption.paragraph_format.keep_with_next = True
            for run in caption.runs:
                run.font.bold = True
            doc.add_picture(io.BytesIO(base64.b64decode(block['png'])), width=Inches(7.0))
        elif kind == 'notes':
            heading('Methodology and coverage')
            paragraph(_BRIEF_METHODOLOGY, muted=True)
        else:
            if block.get('title'):
                p = paragraph(block['title'])
                p.paragraph_format.keep_with_next = True
                for run in p.runs:
                    run.font.bold = True
            count = len(block['headers'])
            widths = block.get('widths') or ([2.9, 4.1] if count == 2 else [7.0 / count] * count)
            created = table(block['headers'], block['rows'], widths)
            next_block = report_blocks[block_no + 1] if block_no + 1 < len(report_blocks) else {}
            if len(created.rows) <= 14 and next_block.get('kind') == 'text' and next_block.get('text', '').startswith(
                    ('Training rows', 'Gross hedge')):
                for cell in created.rows[-1].cells:
                    for paragraph_in_cell in cell.paragraphs:
                        paragraph_in_cell.paragraph_format.keep_with_next = True
                doc.paragraphs[-1].paragraph_format.keep_with_next = True
    if params.get('notional_mm'):
        paragraph(f"Optional target book size ${params['notional_mm']:g} million.", muted=True)
    if params.get('report') == 'full' and report_text:
        doc.add_page_break()
        heading('Diagnostic report appendix')
        for line in report_text.splitlines():
            p = doc.add_paragraph(line)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1
            for run in p.runs:
                run.font.name, run.font.size = 'Courier New', Pt(6.5)
    doc.save(path)
    return path


def export_result(result, report_text='', out_dir=None, also_csv=True):
    r"""[Fix 95/103] Export a finished hedge as a WORD DOCUMENT.

    Writes PCA_hedge_<label>_<timestamp>.docx into HEDGE_EXPORT_DIR (default
    ./hedge_exports), or into `out_dir` when given. The
    document carries the verdict, the trade as a table, risk and monitoring
    levels, the out-of-sample evidence, the exact settings, and the full
    text report as an appendix. `also_csv` additionally drops weights.csv
    next to it as labelled candidate/reference weights.

    Needs python-docx (pip install python-docx); without it the report is
    written as .txt instead so an export never silently fails. Returns the
    path actually written."""
    import os as _o
    # [Fix 115] In a notebook the report renders as HTML and never reaches
    # stdout, so a caller that captured stdout handed us only the progress
    # lines. The renderers keep their own text copy; prefer it.
    report_text = report_text or result.get('report_text') or transcript_text()
    folder, warn = _export_folder(out_dir)
    if warn:
        print(f"  ⚠ {warn}")
    label = _slug(result.get('target_label') or 'hedge')
    stamp = datetime.now().strftime('%Y%m%d-%H%M')
    stem = _o.path.join(folder, f"PCA_hedge_{label}_{stamp}")
    written = None
    try:
        written = _docx_hedge_report(result, report_text, stem + '.docx')
    except ImportError:
        print("  ⚠ python-docx not installed (pip install python-docx) — "
              "writing a text report instead")
    except Exception as e:
        print(f"  ⚠ Word export failed ({e}) — writing a text report instead")
    if written is None:
        written = stem + '.txt'
        with open(written, 'w', encoding='utf-8') as fh:
            fh.write(report_text or 'no report text captured')
    if also_csv:
        try:
            w = result['weights']
            pd.DataFrame({
                'ticker': w.index,
                'action': ['SHORT' if x > 0 else 'LONG' for x in w.values],
                'weight_per_100_gross': w.values.round(6),  # legacy coefficient field
                'dollars_per_100_target': np.abs(w.values) * 100,
                'trade_eligible': bool(result.get('trade_eligible', False)),
                'evidence_status': (result.get('ticket') or {}).get('grade', 'UNVALIDATED'),
                'notional_mm': ([abs(x) * result['params']['notional_mm']
                                 for x in w.values]
                                if (result.get('params') or {}).get('notional_mm')
                                else [None] * len(w)),
                'forced': [t in (result.get('force_included') or [])
                           for t in w.index],
            }).to_csv(stem + '.csv', index=False)
        except Exception as e:
            print(f"  ⚠ weights CSV not written ({e})")
    print(f"  ✓ exported → {written}")
    if also_csv and result.get('hedge_alternatives'):
        rows = []
        for family in ('basket', 'single_stock', 'single_etf', 'single_market'):
            item = result['hedge_alternatives'].get(family)
            if item is None:
                continue
            for ticker, weight in item['weights'].items():
                rows.append({'candidate_type': family, 'ticker': ticker,
                             'reference_only': item.get('reference_only', family.startswith('single')),
                             'action': 'SHORT' if weight > 0 else 'LONG',
                             'dollars_per_100_target': abs(float(weight)) * 100,
                             'unseen_r2': item['unseen_r2'], 'status': item['status'],
                             'qualified': item['qualified']})
        pd.DataFrame(rows).to_csv(stem + '_alternatives.csv', index=False)
    return written


def hedge_ui(data=None):
    """[Fix 89/95] Point-and-click front end. Run this cell, use the form.

    `data` optionally seeds the form with an already-downloaded dataset;
    otherwise use the Data tab (download once → cached to disk forever)."""
    try:
        import ipywidgets as W
        from IPython.display import display, clear_output, HTML as _H
    except Exception:
        print("ipywidgets is not installed — the form cannot be shown.\n"
              "  install:  pip install ipywidgets    (then restart the "
              "kernel)\n\nScripted path meanwhile:\n"
              "  data   = download_hedge_data('AAPL US Equity', "
              "min_mktcap_usd_mm=1000)\n"
              "  result = find_best_hedge('AAPL US Equity', data=data, "
              "notional_mm=10, hedge_horizon_days=21)")
        return None

    if data is not None:
        UI_STATE['data'] = data

    LBL = {'description_width': '148px'}
    FULL = W.Layout(width='460px')
    HALF = W.Layout(width='225px')

    def H(txt):
        return W.HTML(f"<div class='hui-h'>{txt}</div>")

    def HELP(txt):
        return W.HTML(f"<div class='hui-help'>{txt}</div>")

    # ── Trade tab ───────────────────────────────────────────────────────────
    w_target = W.Textarea(
        value=(data['target'] if data and isinstance(data.get('target'), str) else 'AAPL US Equity'),
        placeholder=("single name:   AAPL US Equity\n"
                     "book (one leg per line, weight optional):\n"
                     "AAPL US Equity, 50\nNVDA US Equity, 30\n"
                     "MSFT US Equity, -20"),
        description='Target / book', style=LBL,
        layout=W.Layout(width='460px', height='96px'))
    w_parsed = W.HTML()
    # ── [Fix 115] CUSTOM VALUES YOU CAN ACTUALLY TYPE INTO ──────────────────
    # Reported: "I can select custom for hedge duration and analysis window
    # but at least please let me enter WHAT custom? After running once the
    # custom box pops up — this is not good."
    # The boxes were created with layout.display='none' and only revealed by an
    # observer, so picking 'Custom…' left nothing to type into until some later
    # event forced a re-layout — by which time the run had already gone off
    # with the wrong horizon. Hiding an input to express "not applicable" is
    # the bug: it hides the ONE control the user just asked for.
    # They are now ALWAYS visible and always show the value that will actually
    # be used. Pick a preset and the box mirrors it (read-only); pick 'Custom…'
    # and the same box becomes editable. Nothing appears, disappears or moves.
    w_horizon = W.Dropdown(
        options=[('— not set —', 0), ('1 week (5d)', 5), ('2 weeks (10d)', 10),
                 ('1 month (21d)', 21), ('2 months (42d)', 42),
                 ('3 months (63d)', 63), ('Custom…', -1)],
        value=0, description='Hedge duration', style=LBL, layout=FULL)
    w_horizon_n = W.BoundedIntText(
        value=21, min=1, max=756, step=1, description='trading days',
        style=LBL, layout=HALF)
    w_horizon_hint = W.HTML()
    w_win = W.Dropdown(
        options=[('Full downloaded history', 'none'), ('Last 1 month', '1m'),
                 ('Last 2 months', '2m'), ('Last 3 months', '3m'),
                 ('Last 6 months', '6m'), ('Last 1 year', '1y'),
                 ('Last 2 years', '2y'), ('Custom dates…', 'custom')],
        value='none', description='Analysis window', style=LBL, layout=FULL)
    w_from = W.DatePicker(description='from', style=LBL, layout=HALF)
    w_to = W.DatePicker(description='to', style=LBL, layout=HALF)
    w_dates = W.HBox([w_from, w_to])
    w_dates_hint = W.HTML()
    w_tier = W.HTML()
    w_notional = W.FloatText(value=0.0, description='Book size ($mm)',
                             style=LBL, layout=FULL)

    optional_sizing = W.Accordion(children=[W.VBox([
        HELP('Optional display settings. Neither changes the selected instruments or weights.'),
        w_notional, w_horizon, w_horizon_n, w_horizon_hint])], selected_index=None)
    optional_sizing.set_title(0, 'Optional sizing and holding-period risk')
    tab_trade = W.VBox([
        H('Target'), w_target, w_parsed,
        H('Past analysis window'), w_win, w_dates, w_dates_hint, w_tier,
        optional_sizing])

    # ── Universe tab ────────────────────────────────────────────────────────
    w_mktcap = W.FloatText(value=1000.0, description='Min mkt cap ($mm)',
                           style=LBL, layout=FULL)
    w_scope = W.Dropdown(options=[('All eligible candidates', 'all'), ('Peers only', 'peers')],
                         value='all', description='Candidate universe', style=LBL, layout=FULL)
    w_market = W.Checkbox(value=True, description='Include local broad market ETF', indent=False)
    w_peers = W.Text(value='', description='Manual peer list', style=LBL, layout=FULL,
                     placeholder='Optional for older caches: 2910 TT, 2911 TT')
    w_basket_mode = W.Dropdown(options=[('Automatic sizes', 'auto'), ('Require a range or exact size', 'range')],
                               value='auto', description='Basket size', style=LBL, layout=FULL)
    w_basket = W.Text(value='2,3,5,7', description='Automatic choices', style=LBL, layout=FULL)
    w_basket_min = W.BoundedIntText(value=2, min=2, max=50, description='Minimum names', style=LBL, layout=HALF)
    w_basket_max = W.BoundedIntText(value=5, min=2, max=50, description='Maximum names', style=LBL, layout=HALF)
    w_look = W.Text(value='126,252', description='Lookbacks (days)',
                    style=LBL, layout=FULL)
    w_force = W.Text(value='', placeholder='0050 TT, 2330 TT',
                     description='Force include', style=LBL, layout=FULL)
    w_excl = W.Text(value='', placeholder='002230, 3156 JP Equity',
                    description='Exclude', style=LBL, layout=FULL)
    w_tz = W.Dropdown(options=[('Auto', 'auto'),
                               ('Force same timezone', True),
                               ('Allow global', False)],
                      value='auto', description='Timezone', style=LBL,
                      layout=FULL)
    w_stale = W.IntText(value=7, description='Missing-price limit', style=LBL,
                        layout=FULL)
    tab_uni = W.VBox([
        H('Candidate universe'), w_scope, w_market,
        HELP('Peers only uses direct Bloomberg peers and matching industry peers. '
             'The local market ETF is optional. Older caches need a new download or a manual peer list.'),
        w_peers, w_mktcap, w_tz, w_stale,
        H('Basket construction'), w_basket_mode, w_basket, W.HBox([w_basket_min, w_basket_max]),
        HELP('Equal minimum and maximum request an exact number. Required sizes are never shrunk. '
             'Single instruments remain references.'), w_look,
        H('Manual overrides'),
        HELP('force include = held in every basket (★); exclude = never a '
             'candidate. Short names or full tickers.'),
        w_force, w_excl])

    # ── Model tab (factor / fitting knobs) ─────────────────────────────────
    w_objective = W.Dropdown(
        options=[('Reduce volatility', 'variance'), ('Track returns (strict R²)', 'tracking')],
        value='variance', description='Hedge objective', style=LBL, layout=FULL)
    w_cov = W.Dropdown(options=[('Ledoit-Wolf shrinkage', 'ledoit'),
                                ('Ordinary PCA', 'none')],
                       value='ledoit', description='PCA covariance',
                       style=LBL, layout=FULL)
    w_pcs = W.Text(value='auto', description='PCs (auto or list)',
                   style=LBL, layout=FULL)
    w_wins = W.FloatText(value=0.01, step=0.005,
                         description='Winsorize (0=off)', style=LBL,
                         layout=FULL)
    w_gross = W.FloatText(value=0.02, step=0.01,
                          description='Gross penalty', style=LBL, layout=FULL)
    w_maxgross = W.FloatText(value=0.0, description='Max gross (0=off)',
                             style=LBL, layout=FULL)
    w_boot = W.IntText(value=2000, description='Bootstrap draws',
                       style=LBL, layout=FULL)
    w_report = W.Dropdown(options=[('Structured desk analysis', 'compact'), ('Full diagnostic report', 'full')],
                          value='compact', description='Report', style=LBL,
                          layout=FULL)
    w_alternatives = W.BoundedIntText(value=5, min=1, max=20, description='Alternative baskets', style=LBL, layout=FULL)
    w_plots = W.Checkbox(value=True, description='Charts', indent=False)
    w_roll = W.Checkbox(value=True, description='Rolling OOS + cadence',
                        indent=False)
    # [Fix 115] "after rehedge... only one outer window?" — that was hard-wired
    # and unexplained. It is a real trade-off (seconds vs a full re-validation),
    # so it becomes a choice, and the report states which one ran.
    w_requick = W.Dropdown(
        options=[('Fast — 1 validation window', 'fast'),
                 ('Full — same 3 windows as RUN HEDGE', 'full')],
        value='fast', description='RE-HEDGE depth', style=LBL, layout=FULL)
    tab_model = W.VBox([
        H('Hedge objective'), w_objective,
        HELP('Risk reduction ranks unseen volatility improvement; R² remains a diagnostic. '
             'Tracking uses the former stricter R² screen.'),
        H('Factor model'),
        HELP('these shape candidate SELECTION only; hedge weights always '
             'come from ridge on real returns'),
        w_cov, w_pcs, w_wins,
        H('Penalties'), w_gross, w_maxgross,
        H('Output'), w_boot, w_report, w_alternatives, W.HBox([w_plots, w_roll]),
        H('Re-hedging'),
        HELP('RE-HEDGE never re-searches the config — that is what makes it '
             'fast. This only sets how many windows it re-validates the refit '
             'on. Charts and Rolling OOS above apply to RE-HEDGE too.'),
        w_requick])

    # ── Data tab ────────────────────────────────────────────────────────────
    w_cache = W.Dropdown(options=[('(no cached downloads)', None)],
                         description='Cached data', style=LBL,
                         layout=W.Layout(width='620px'))
    b_load = W.Button(description='Load selected', icon='folder-open')
    b_refresh = W.Button(description='Refresh list', icon='refresh')
    w_years = W.IntText(value=3, description='Years of history', style=LBL,
                        layout=FULL)
    w_pit1 = W.Checkbox(value=True, indent=False,
                        description='Point-in-time market caps')
    w_pit2 = W.Checkbox(value=True, indent=False,
                        description='Point-in-time index membership')
    b_dl = W.Button(description='Download from Bloomberg',
                    button_style='warning', icon='cloud-download',
                    layout=W.Layout(width='240px'))
    w_expdir = W.Text(value=HEDGE_EXPORT_DIR, description='Export folder',
                      style=LBL, layout=W.Layout(width='620px'))
    w_expcsv = W.Checkbox(value=True, indent=False,
                          description='also write weights .csv')
    tab_data = W.VBox([
        H('Cached downloads — reload with zero API calls'),
        HELP('✓ fits the current book · △ stale prices · ✗ a leg is missing'),
        W.HBox([w_cache]), W.HBox([b_load, b_refresh]),
        H('New download — the only action that touches Bloomberg'),
        HELP('discovers the universe for the book in the Trade tab, pulls '
             'prices and caps, and caches everything to disk automatically'),
        w_years, W.HBox([w_pit1, w_pit2]), b_dl,
        H('Where Export writes'),
        HELP('the Export button writes a Word report (plus weights .csv) '
             'here. If the drive is not mapped on this machine it falls '
             'back to a local hedge_reports folder and tells you.'),
        w_expdir, w_expcsv])

    tabs = W.Tab(children=[tab_trade, tab_uni, tab_model, tab_data])
    for i, t in enumerate(('Analysis', 'Candidates', 'Advanced', 'Data')):
        tabs.set_title(i, t)

    w_fit = W.HTML()
    w_status = W.HTML()
    b_run = W.Button(description='RUN HEDGE', button_style='success',
                     icon='play',
                     layout=W.Layout(width='190px', height='42px'))
    b_quick = W.Button(description='RE-HEDGE (fast)', icon='bolt',
                       tooltip='refit weights only, pinned to the last '
                               'validated config — seconds, no API calls',
                       layout=W.Layout(width='170px', height='42px'))
    b_export = W.Button(description='Export Word', icon='file-word-o',
                        tooltip='writes a Word report of this hedge to the '
                                'Export folder on the Data tab',
                        layout=W.Layout(width='150px', height='42px'))
    b_code = W.Button(description='Show code', icon='code',
                      layout=W.Layout(width='130px', height='42px'))
    out = W.Output()

    # ── helpers ─────────────────────────────────────────────────────────────
    # [Fix 115] The number box is the single source of truth for the horizon:
    # a preset writes into it, Custom… lets you edit it, and _horizon_arg only
    # ever reads it. That is what makes the displayed value and the value the
    # engine receives impossible to disagree about.
    _SYNC = {'busy': False}          # guard: preset → box → preset feedback

    def _horizon_arg():
        if w_horizon.value == 0:
            return None
        return int(w_horizon_n.value) or None

    def _window_arg():
        if w_win.value == 'none':
            return None
        if w_win.value == 'custom':
            if not (w_from.value or w_to.value):
                return None
            return (str(w_from.value) if w_from.value else None,
                    str(w_to.value) if w_to.value else None)
        return w_win.value

    def _on_horizon_preset(_=None):
        """Preset picked → mirror it into the box and lock the box."""
        if _SYNC['busy']:
            return
        _SYNC['busy'] = True
        try:
            custom = (w_horizon.value == -1)
            w_horizon_n.disabled = not custom
            if w_horizon.value > 0:
                w_horizon_n.value = int(w_horizon.value)
        finally:
            _SYNC['busy'] = False
        _horizon_hint()

    def _on_horizon_typed(_=None):
        """Typed a number → switch the dropdown to Custom… unless it matches
        a preset. Typing is an intent, so it wins."""
        if _SYNC['busy'] or w_horizon.value == 0:
            return
        _SYNC['busy'] = True
        try:
            _preset = {5, 10, 21, 42, 63}
            w_horizon.value = (int(w_horizon_n.value)
                               if int(w_horizon_n.value) in _preset else -1)
            w_horizon_n.disabled = (w_horizon.value != -1)
        finally:
            _SYNC['busy'] = False
        _horizon_hint()

    def _horizon_hint(_=None):
        h = _horizon_arg()
        if not h:
            w_horizon_hint.value = (
                "<div class='hui-help'>no horizon set — risk is quoted "
                "annualised and the per-hold evidence is skipped</div>")
            return
        w_horizon_hint.value = (
            f"<div class='hui-help'>using <b>{h} trading days</b> "
            f"(≈{h/21:.1f} months)"
            + ('' if w_horizon.value == -1 else
               ' — choose <b>Custom…</b> above to type your own')
            + "</div>")

    def _dates_hint(_=None):
        custom = (w_win.value == 'custom')
        w_from.disabled = w_to.disabled = not custom
        if not custom:
            w_dates_hint.value = (
                "<div class='hui-help'>choose <b>Custom dates…</b> above to "
                "enable these and type an exact range</div>")
            return
        if not (w_from.value or w_to.value):
            w_dates_hint.value = (
                "<div class='hui-help' style='color:#8a5a00'>pick a "
                "<b>from</b> and/or <b>to</b> date — until you do, the full "
                "downloaded history is used</div>")
            return
        w_dates_hint.value = (
            f"<div class='hui-help'>window: "
            f"<b>{w_from.value or 'start of data'}</b> → "
            f"<b>{w_to.value or 'end of data'}</b></div>")

    def _seed_dates():
        """Pre-fill the pickers with the loaded data's real span, so 'Custom
        dates…' starts from the range that actually exists rather than empty
        boxes with no clue what is valid."""
        d = UI_STATE.get('data')
        if d is None or w_from.value or w_to.value:
            return
        try:
            idx = d['prices'].index
            w_from.value, w_to.value = idx[0].date(), idx[-1].date()
        except Exception:
            pass

    def _status(msg, kind='info'):
        col = {'info': '#24435f', 'ok': '#1b6b3a', 'warn': '#8a5a00',
               'err': '#8c1c1c', 'busy': '#8a5a00'}[kind]
        _spin = ('<span style="display:inline-block;margin-right:6px">⏳</span>'
                 if kind == 'busy' else '')
        w_status.value = (f"<div style='color:{col};font-family:{_RF_UI};"
                          f"font-size:12px;margin-top:4px;font-weight:"
                          f"{700 if kind in ('busy', 'err') else 400}'>"
                          f"{_spin}{msg}</div>")

    # ── [Fix 106] ONE ACTION AT A TIME ──────────────────────────────────────
    # Reported: "I clicked several times of running or downloading, it re-ran
    # and re-downloaded — I thought it was not running so it kept running."
    # Two separate causes, both fixed here:
    #   1. NOTHING WAS DISABLED. ipywidgets fires on_click once per click and
    #      queues the callbacks, so a second click during a 4-minute run
    #      scheduled a SECOND full run (and, on the Data tab, a second
    #      Bloomberg download — the expensive one).
    #   2. NOTHING MOVED WHILE IT RAN. _run_engine redirected the engine's
    #      stdout into a StringIO and printed the whole thing at the END, so
    #      between "running…" and the report there were minutes of a blank
    #      cell. There was no way to tell a running job from a dead one, so
    #      clicking again was the reasonable thing to do.
    # Now: a busy flag rejects re-entry, every action button greys out for
    # the duration, and the engine's output streams line by line as it is
    # produced with an elapsed-time counter.
    _ACTION_BTNS = []                     # filled in after the buttons exist

    def _set_busy(on, label=''):
        UI_STATE['busy'] = bool(on)
        for _b in _ACTION_BTNS:
            try:
                _b.disabled = bool(on)
            except Exception:
                pass
        if on:
            _status(f"{label} — running… (buttons disabled until it "
                    f"finishes; do NOT click again)", 'busy')

    def _guard(fn, label, name):
        """Wrap a button handler: reject re-entry, disable, always restore."""
        def _cb(_b):
            if UI_STATE.get('busy'):
                with out:
                    print(f"\n[Fix 106] '{name}' ignored — {UI_STATE.get('busy_what', 'a job')} "
                          f"is still running. Watch the elapsed-time counter; "
                          f"the buttons re-enable when it finishes.")
                return
            UI_STATE['busy_what'] = name
            _set_busy(True, label)
            try:
                fn(_b)
            finally:
                _set_busy(False)
                UI_STATE['busy_what'] = None
        return _cb

    def _best_cache_for(target):
        try:
            cat = list_hedge_data()
        except Exception:
            return None
        for _, r in cat.iterrows():
            fp = r.get('_fp')
            if not fp:
                continue
            try:
                if check_cache_fit(target,
                                   fingerprint=fp)['status'] != 'mismatch':
                    return r['path']
            except Exception:
                continue
        return None

    def _refresh_cache(_=None):
        try:
            cat = list_hedge_data()
        except Exception:
            cat = pd.DataFrame()
        if len(cat):
            try:
                tgt = _ui_parse_book(w_target.value)
            except Exception:
                tgt = None
            opts = []
            for _, r in cat.iterrows():
                mark = ''
                if tgt is not None and r.get('_fp'):
                    try:
                        st = check_cache_fit(
                            tgt, fingerprint=r['_fp'])['status']
                        mark = {'exact': '✓ ', 'compatible': '✓ ',
                                'stale': '△ ', 'mismatch': '✗ '}[st]
                    except Exception:
                        pass
                opts.append((f"{mark}{r['label']}  ·  to "
                             f"{r['last_date'] or r['saved']}  ·  "
                             f"{r['n_tickers'] or '?'} tickers  ·  "
                             f"{r['MB']}MB", r['path']))
            w_cache.options = opts
        else:
            w_cache.options = [('(no cached downloads)', None)]

    def _refresh_parsed(_=None):
        try:
            tgt = _ui_parse_book(w_target.value)
            legs, wts, isp, lab = _coerce_targets(tgt)
            if isp:
                body = ' · '.join(f"{k.split(' ')[0]} {v:+.0%}"
                                  for k, v in wts.items())
                w_parsed.value = (f"<span style='color:#1b6b3a;font-size:"
                                  f"12px'>book {lab}: {body} "
                                  f"(gross-normalized)</span>")
            else:
                w_parsed.value = (f"<span style='color:#1b6b3a;font-size:"
                                  f"12px'>single name: {legs[0]}</span>")
        except Exception as e:
            w_parsed.value = (f"<span style='color:#8c1c1c;font-size:12px'>"
                              f"{e}</span>")
        _refresh_fit()

    def _refresh_fit(_=None):
        if UI_STATE['data'] is None:
            w_fit.value = ("<div style='color:#8a5a00;font-size:12px'>"
                           "no data loaded — open the <b>Data</b> tab</div>")
            return
        try:
            tgt = _ui_parse_book(w_target.value)
        except Exception:
            w_fit.value = ''
            return
        try:
            fit = check_cache_fit(tgt, data=UI_STATE['data'])
        except Exception as e:
            w_fit.value = (f"<div style='color:#8c1c1c;font-size:12px'>{e}"
                           f"</div>")
            return
        col = {'exact': '#1b6b3a', 'compatible': '#1b6b3a',
               'stale': '#8a5a00', 'mismatch': '#8c1c1c'}[fit['status']]
        mark = {'exact': '✓', 'compatible': '✓', 'stale': '△',
                'mismatch': '✗'}[fit['status']]
        extra = ''
        if fit['status'] == 'mismatch':
            hit = _best_cache_for(tgt)
            extra = ('<br>a cached set that fits: <b>'
                     + _os.path.basename(hit) + '</b> — pick it in the Data '
                     'tab' if hit else
                     '<br>press <b>Download from Bloomberg</b> in the Data '
                     'tab')
        w_fit.value = (f"<div style='color:{col};font-size:12px;"
                       f"font-family:Arial,sans-serif;margin-top:4px'>{mark} "
                       f"data: {fit['message']}{extra}</div>")

    def _refresh_tier(_=None):
        # [Fix 115] no widget is shown or hidden here any more — the custom
        # inputs are permanent and _on_horizon_preset / _dates_hint enable or
        # disable them in place.
        if UI_STATE['data'] is None:
            w_tier.value = ("<span style='color:#8a5a00;font-size:12px'>"
                            "load or download data to preview the "
                            "validation tier</span>")
            return
        try:
            import io as _io
            from contextlib import redirect_stdout as _rso
            size_options, size_range = _basket_args()
            legs = _coerce_targets(_ui_parse_book(w_target.value))[0]
            filtered = _filter_candidate_scope(UI_STATE['data'], legs,
                UI_STATE['data']['prices'].columns, w_scope.value, w_market.value,
                _ui_list(w_peers.value), _ui_list(w_force.value))
            sizes = _basket_sizes(size_options, size_range)
            available = len(filtered['columns']) - len(legs)
            if not any(2 <= k <= available for k in sizes):
                raise ValueError(f'Only {available} candidates; requested basket sizes cannot be filled.')
            cvw = 42
            with _rso(_io.StringIO()):
                pv = preview_window(
                    UI_STATE['data'], _window_arg(),
                    lookback_options=_ui_ints(w_look.value, (126, 252)),
                    cv_test_window=cvw,
                    basket_size_options=size_options, basket_size_range=size_range)
            mode = pv.get('mode')
            if mode is None:
                w_tier.value = ("<span style='color:#8c1c1c;font-size:12px'>"
                                f"only {pv['sessions']} sessions — need ≥10"
                                "</span>")
                return
            col = {'FULL': '#1b6b3a', 'REDUCED': '#1b6b3a',
                   'HOLDOUT': '#8a5a00', 'IN-SAMPLE': '#8c1c1c'}[mode]
            w_tier.value = (
                f"<div style='color:{col};font-size:12px;font-family:Arial,"
                f"sans-serif'>{pv['sessions']} sessions "
                f"({pv['start']:%d %b %Y} → {pv['end']:%d %b %Y}) → "
                f"<b>{mode}</b><br><span style='color:#555'>"
                f"{TIER_MEANING[mode]}</span></div>")
        except Exception as e:
            w_tier.value = (f"<span style='color:#8c1c1c;font-size:12px'>"
                            f"{e}</span>")

    def _basket_args():
        if w_basket_mode.value == 'range':
            bounds = (int(w_basket_min.value), int(w_basket_max.value))
            _basket_sizes((2,), bounds)
            return (2,), bounds
        return _ui_ints(w_basket.value, (2, 3, 5, 7)), None

    def _scope_changed(_=None):
        w_market.value = w_scope.value == 'all'
        _refresh_tier()

    def _size_changed(_=None):
        forced_range = w_basket_mode.value == 'range'
        w_basket.disabled = forced_range
        w_basket_min.disabled = w_basket_max.disabled = not forced_range
        _refresh_tier()

    def _kwargs():
        size_options, size_range = _basket_args()
        mg = w_maxgross.value or None
        pcs = str(w_pcs.value).strip().lower()
        return {'hedge_objective': w_objective.value,
                'min_mktcap_usd_mm': w_mktcap.value,
                'notional_mm': (w_notional.value or None),
                'hedge_horizon_days': _horizon_arg(),
                'candidate_scope': w_scope.value,
                'include_broad_market': w_market.value,
                'peer_tickers': _ui_list(w_peers.value),
                'basket_size_options': size_options,
                'basket_size_range': size_range,
                'lookback_options': _ui_ints(w_look.value, (126, 252)),
                'pc_options': ('auto' if pcs in ('', 'auto')
                               else list(_ui_ints(pcs, (3,)))),
                'winsorize_pct': w_wins.value,
                'force_include': _ui_list(w_force.value),
                'exclude': _ui_list(w_excl.value),
                'restrict_to_target_tz': w_tz.value,
                'robust_cov': w_cov.value,
                'gross_penalty': w_gross.value,
                'max_gross': (mg if mg and mg > 0 else None),
                'mask_stale_days': (w_stale.value or None),
                'boot_n': int(w_boot.value),
                'report': w_report.value,
                'rolling_oos': w_roll.value,
                'show_plots': w_plots.value,
                'alternative_baskets': w_alternatives.value}

    def _run_engine(fn, *args, **kw):
        """[Fix 106] Run the engine with its output STREAMING to the cell.

        The old version redirected stdout into a StringIO for the whole run
        and printed it at the end, purely so the text could be captured for
        export. On a multi-minute run that produced a silent cell — the
        direct cause of the repeated clicking. A real tee keeps the capture
        AND shows progress as it happens; the HTML blocks the report emits
        via _ipy_display are unaffected (they were never on stdout).
        """
        import io as _io, sys as _sys, time as _time
        buf = _io.StringIO()

        class _Tee:
            def __init__(self, *sinks):
                self._sinks = sinks
            def write(self, s):
                for _s in self._sinks:
                    try:
                        _s.write(s)
                    except Exception:
                        pass
                return len(s)
            def flush(self):
                for _s in self._sinks:
                    try:
                        _s.flush()
                    except Exception:
                        pass

        _t0 = _time.time()
        _old = _sys.stdout
        _sys.stdout = _Tee(_old, buf)
        try:
            res = fn(*args, **kw)
        finally:
            _sys.stdout = _old
        # [Fix 115] in a notebook the report is displayed as HTML and never
        # goes near stdout, so the tee only ever caught stray print()s. The
        # renderers keep a faithful text copy — use it, and keep the tee as
        # the fallback for anything printed outside them.
        UI_STATE['report_text'] = transcript_text() or buf.getvalue()
        UI_STATE['last_seconds'] = _time.time() - _t0
        return res

    # ── actions ─────────────────────────────────────────────────────────────
    def on_load(_):
        with out:
            clear_output()
            if not w_cache.value:
                _status('nothing cached yet — download first', 'warn')
                return
            try:
                UI_STATE['data'] = load_hedge_data(w_cache.value)
                UI_STATE['loaded_from'] = w_cache.value
                _status(f"loaded · {UI_STATE['data']['prices'].shape[0]} "
                        f"rows × {UI_STATE['data']['prices'].shape[1]} "
                        f"tickers (no API calls)", 'ok')
                _refresh_tier()
                _refresh_fit()
            except Exception as e:
                _status(f"load failed: {e}", 'err')

    def on_download(_):
        with out:
            clear_output()
            try:
                tgt = _ui_parse_book(w_target.value)
            except Exception as e:
                _status(f"target: {e}", 'err')
                return
            _status('downloading from Bloomberg — this can take minutes…',
                    'info')
            try:
                UI_STATE['data'] = download_hedge_data(
                    tgt, years=int(w_years.value),
                    min_mktcap_usd_mm=w_mktcap.value,
                    exclude=_ui_list(w_excl.value),
                    force_include=_ui_list(w_force.value),
                    fetch_mktcap_hist=w_pit1.value,
                    fetch_pit_members=w_pit2.value)
                UI_STATE['loaded_from'] = None
                _status(f"downloaded and cached · "
                        f"{UI_STATE['data']['prices'].shape[0]} rows × "
                        f"{UI_STATE['data']['prices'].shape[1]} tickers",
                        'ok')
                _refresh_cache()
                _refresh_tier()
                _refresh_fit()
            except Exception as e:
                _status(f"download failed: {e}", 'err')

    def _pre_run():
        if UI_STATE['data'] is None:
            _status('no data yet — use the Data tab to download or load a '
                    'cached set', 'warn')
            return None
        try:
            tgt = _ui_parse_book(w_target.value)
        except Exception as e:
            _status(f"target: {e}", 'err')
            return None
        fit = check_cache_fit(tgt, data=UI_STATE['data'])     # [Fix 90]
        if fit['status'] == 'mismatch':
            _status(f"cannot run — {fit['message']}", 'err')
            return None
        if fit['status'] == 'stale':
            print(f"  △ {fit['message']}\n")
        return tgt

    def on_run(_):
        with out:
            clear_output()
            tgt = _pre_run()
            if tgt is None:
                return
            kw = _kwargs()
            win = _window_arg()
            UI_STATE['code'] = _ui_code(
                tgt, win, {k: v for k, v in kw.items()
                           if k != 'show_plots'}, UI_STATE['loaded_from'])
            _status('running…', 'info')
            try:
                UI_STATE['result'] = _run_engine(
                    find_best_hedge, tgt, data=UI_STATE['data'],
                    sample_window=win, **kw)
                _status(f"done in {UI_STATE.get('last_seconds', 0):.0f}s · "
                        f"UI_STATE['result'] holds everything — Export "
                        f"writes the Word report", 'ok')
            except Exception as e:
                _status(f"run failed: {e}", 'err')
                print(f"\n{type(e).__name__}: {e}")

    def on_quick(_):
        with out:
            clear_output()
            if UI_STATE['result'] is None:
                _status('run a full hedge first — RE-HEDGE pins its '
                        'validated config', 'warn')
                return
            tgt = _pre_run()
            if tgt is None:
                return
            _full = (w_requick.value == 'full')
            _status('re-hedging on the pinned config…', 'info')
            try:
                # [Fix 115] the Charts and Rolling-OOS checkboxes apply here
                # too. They used to be forced off inside quick_rehedge, so a
                # re-hedge silently threw away every chart the full run drew.
                UI_STATE['result'] = _run_engine(
                    quick_rehedge, tgt, UI_STATE['data'],
                    UI_STATE['result'], show_plots=w_plots.value,
                    rolling_oos=w_roll.value, full_validation=_full)
                _status('re-hedged · weights refit, config unchanged · '
                        + ('full validation re-run' if _full else
                           '1 validation window (fast) — see the note at the '
                           'top of the report'), 'ok')
            except Exception as e:
                _status(f"re-hedge failed: {e}", 'err')

    def on_export(_):
        with out:
            if UI_STATE['result'] is None:
                _status('nothing to export yet', 'warn')
                return
            try:
                path = export_result(UI_STATE['result'],
                                     UI_STATE.get('report_text', ''),
                                     out_dir=(w_expdir.value.strip() or None),
                                     also_csv=w_expcsv.value)
                _status(f"exported → {path}", 'ok')
            except Exception as e:
                _status(f"export failed: {e}", 'err')

    def on_code(_):
        with out:
            clear_output()
            if not UI_STATE['code']:
                _status('run something first — then this shows the exact '
                        'code for it', 'warn')
                return
            print(UI_STATE['code'])

    # [Fix 106] every action goes through _guard: single-flight, buttons
    # disabled for the duration, elapsed time reported. b_refresh and b_code
    # are instant and read-only, so they stay unguarded.
    _ACTION_BTNS.extend([b_load, b_dl, b_run, b_quick, b_export])
    b_load.on_click(_guard(on_load, 'loading cache', 'Load selected'))
    b_refresh.on_click(_refresh_cache)
    b_dl.on_click(_guard(on_download, 'downloading from Bloomberg',
                         'Download from Bloomberg'))
    b_run.on_click(_guard(on_run, 'running the hedge', 'RUN HEDGE'))
    b_quick.on_click(_guard(on_quick, 're-hedging', 'RE-HEDGE (fast)'))
    b_export.on_click(_guard(on_export, 'writing the report', 'Export Word'))
    b_code.on_click(on_code)
    w_scope.observe(_scope_changed, names='value')
    w_basket_mode.observe(_size_changed, names='value')
    for wdg in (w_win, w_from, w_to, w_look, w_basket, w_basket_min, w_basket_max,
                w_market, w_peers, w_force):
        wdg.observe(_refresh_tier, names='value')
    # [Fix 115] preset ⇄ number box, and the date pickers' enabled state
    w_horizon.observe(_on_horizon_preset, names='value')
    w_horizon_n.observe(_on_horizon_typed, names='value')
    w_win.observe(_dates_hint, names='value')
    for wdg in (w_from, w_to):
        wdg.observe(_dates_hint, names='value')
    w_target.observe(_refresh_parsed, names='value')

    _refresh_cache()
    _refresh_parsed()
    _on_horizon_preset()
    _seed_dates()
    _dates_hint()
    _size_changed()
    _refresh_fit()
    root = W.VBox([
        W.HTML(_UI_CSS),
        W.HTML("<div class='hui-title'>PCA Hedge Finder</div>"
               "<div class='hui-sub'>Set the trade up, press "
               "<b>RUN</b>. Results stay in <code>UI_STATE['result']</code>; "
               "<b>Export Word</b> writes the hedge report to the "
               "folder set on the Data tab.</div>"),
        tabs, w_fit,
        W.HBox([b_run, b_quick, b_export, b_code],
               layout=W.Layout(margin='12px 0 2px 0')),
        w_status, out])
    root.add_class('hedge-ui')
    UI_STATE['widgets'] = {'candidate_scope': w_scope, 'include_broad_market': w_market,
                           'basket_mode': w_basket_mode, 'basket_min': w_basket_min,
                           'basket_max': w_basket_max, 'analysis_window': w_win,
                           'hedge_horizon': w_horizon, 'notional': w_notional,
                           'target': w_target, 'run_button': b_run,
                           'validation_preview': w_tier, 'form': root}
    display(root)
    return UI_STATE


# =============================================================================
# CELL 4 (OPTIONAL): SCRIPTED API — for power users and reproducibility
# =============================================================================
# The GUI in CELL 3 covers everything below; this cell exists so a run can be
# scripted, diffed or scheduled. Everything is commented out on purpose — the
# "Show code" button in the form prints the exact equivalent of whatever you
# just ran, ready to paste here.
#
#   preview_window(data, '3m')        # what will this window buy me?
#   list_hedge_data()                 # what downloads are cached?
#   data = load_hedge_data(0)         # reload the newest, zero API calls
#   check_cache_fit(book, data=data)  # is that download still right for me?
# =============================================================================

# =============================================================================
# CELL 3: RUN — Jupyter workflow [Fix 31]
# =============================================================================
# --- CELL A: download ONCE (the only cell that hits Bloomberg) ---------------
# Discovery + prices + USD market caps. min_mktcap_usd_mm is in USD MILLIONS
# and only shapes the DISCOVERED universe; you can tighten it again in CELL B.
# [Fix 40] pass force_include here too so the names are guaranteed downloaded.
# [Fix 44] download_hedge_data now ALSO fetches historical market-cap PATHS so
#          the size floor can be applied point-in-time (as-of each window)
#          instead of with today's cap — set fetch_mktcap_hist=False to skip it.
# [Fix 49] It ALSO pulls point-in-time INDEX MEMBERSHIP (INDX_MWEIGHT_HIST):
#          past members incl. delisted names get downloaded, and each backtest
#          window only sees names that were members at the time. If the index
#          licence-gates the field (e.g. some TW benchmarks) it just prints a
#          warning and falls back to today's members — nothing breaks.
#          Set fetch_pit_members=False to skip.
# [Fix 46] `target` may be a single name, an equal-weight list, or a weighted
#          dict (a whole book) — see the portfolio example below.
# data = download_hedge_data('GMD AU Equity', min_mktcap_usd_mm=1000)
# data = download_hedge_data('2303 TT Equity', min_mktcap_usd_mm=0,
#                            force_include=['2330 TT', '0050 TT'])
#
# [Fix 46] PORTFOLIO download — union of each leg's universe, legs auto-excluded
# data = download_hedge_data({'AAPL US Equity': 0.5,     # 50% long AAPL
#                             'MSFT US Equity': 0.3,     # 30% long MSFT
#                             'NVDA US Equity': 0.2},    # 20% long NVDA
#                            min_mktcap_usd_mm=5000)

# --- CELL B: model — rerun freely while tuning, zero API calls ---------------
# [Fix 60] TWO CONFIG TRAPS were live in the previous version of this cell:
#   (a) size_band=(0.7, 1.3) was ACTIVE while its own comment said "0.3x-3x".
#       A 0.7-1.3x band is brutally tight and silently guts the universe —
#       ETFs and force-included names are exempt, but every other candidate
#       had to sit within ±30% of the target's market cap.
#   (b) min_mktcap_usd_mm was commented out, so the function DEFAULT of 5000
#       ($5bn) applied — even though CELL A downloaded with a $1bn floor.
#       Whenever size_band is off, that silent $5bn floor filters everything.
# Never rely on the default here: state the floor explicitly so CELL A and
# CELL B agree, and if you use size_band, keep it wide.
# result = find_best_hedge(
#     'GMD AU Equity', data=data,
#     min_mktcap_usd_mm=1000,         # [Fix 35/60] USD MILLIONS — matches the
#                                     # CELL A download floor. Explicit on
#                                     # purpose; the default is 5000 ($5bn).
#     restrict_to_target_tz='auto',   # [Fix 33] 'auto' / True / False
#     tz_tolerance_hours=3.0,         # [Fix 32] closes within 3h = synchronous
#     # exclude=['002230', '3156 JP Equity'],   # [Fix 36] manual filter-out:
#     #                                 # short names or full tickers, any mix
#     # force_include=['2330 TT'],      # [Fix 40] must-have names — held in
#     #                                 # EVERY basket and marked ★ in all
#     #                                 # outputs; short names or full tickers
#     gross_penalty=0.02,             # [Fix 38] composite penalty per 1.0x gross
#     max_gross=None,                 # [Fix 38] e.g. 3.0 caps gross at $300/$100
#     winsorize_pct=0.01,             # [Fix 42] clip at 1%/99% before PCA
#     robust_cov='ledoit',            # [Fix 42] shrinkage-covariance PCA
#     pit_size=True,                  # [Fix 44] point-in-time size floor
#     pit_members=True,               # [Fix 49] point-in-time index membership
#     mask_stale_days=7,              # [Fix 56] suspension guard — mask prices
#                                     # missing for >7 rows; None disables
#     notional_mm=None,               # [Fix 72] e.g. 10 → the trade ticket adds
#                                     # a $mm column sized for $10mm gross
#     # sample_window='3m',           # [Fix 76] restrict the analysis window:
#     #                               # '3m'/'90d'/'26w'/'1y' = last N up to the
#     #                               # end of the data, or absolute dates:
#     # sample_window=('2026-07-13', '2026-07-28'),
#     #                               # [Fix 77] validation AUTO-ADAPTS to the
#     #                               # window: FULL → REDUCED → HOLDOUT →
#     #                               # IN-SAMPLE (short windows can only give
#     #                               # descriptive numbers — the ticket says
#     #                               # which tier ran and what it proves)
#     # report='full',                # [Fix 79] long-form report (adds per-
#     #                               # config weight tables + explanations)
#     # rolling_oos=True,             # [Fix 71] ON by default: walk-forward OOS
#     #                               # curve + [Fix 78] rebalance-cadence and
#     #                               # basket-turnover diagnostics
#     # boot_n=2000,                  # [Fix 70] bootstrap CI draws; 0 disables
#     # size_band=(0.3, 3.0),         # [Fix 45/60] OFF by default. If you use
#     #                               # it, keep it WIDE (0.3x-3x the target's
#     #                               # cap). It overrides the flat floor.
#     # size_override={'XYZ': 'large'},  # [Fix 45] forward-looking cap views
# )

# --- Portfolio / multi-name books [Fix 46/64] --------------------------------
# The target can be a book instead of a single name. Three accepted formats:
#
#   result = find_best_hedge('AAPL US Equity', data=data)          # 1 name
#
#   result = find_best_hedge(                       # equal-weight LONG book
#       ['AAPL US Equity', 'NVDA US Equity', 'MSFT US Equity'],
#       data=data)
#
#   result = find_best_hedge(                       # weighted book: values =
#       {'AAPL US Equity': +0.5,                    # relative notionals in
#        'NVDA US Equity': +0.3,                    # any unit ($mm, %, ...);
#        'MSFT US Equity': -0.2},                   # sign = direction.
#       data=data)                                  # Normalized by GROSS.
#
# Weights need NOT sum to 1 — {'AAPL US': 50, 'NVDA US': 30, 'MSFT US': -20}
# (e.g. $mm notionals) is normalized to (+0.5, +0.3, -0.2) internally.
# [Fix 67] every ticker MUST carry an exchange code ('AAPL US' at minimum) —
# a bare 'AAPL' now raises immediately instead of dying mid-download. The book is
# hedged as ONE synthetic return series (the NET book), the recipe's
# "per $100" means per $100 of GROSS book value, and section [2b] shows the
# per-leg residual attribution. NOTE: the legs must be in the CELL A
# download — pass the same book (or its tickers) to download_hedge_data.
#
# --- Re-hedging an updated book without a full re-run [Fix 63/66] ------------
# For an index-rebalance book that churns daily, pin the validated config and
# refit weights only (seconds, no API calls). Re-run the full find_best_hedge
# weekly or whenever the book changes materially.
# [Fix 66] the new book's legs MAY differ from the downloaded book — the only
# requirement is that every leg exists in the downloaded data (new names can
# be guaranteed via force_include= in CELL A). Ex-legs become candidates.
# new_book = {'AAA AU Equity': 0.5, 'BBB AU Equity': -0.5}
# result2 = quick_rehedge(new_book, data, result)



def compare_history_windows(target, data, windows=('1m', '2m', '3m', '6m', '1y'),
                            require_positive_tracking=True, **kwargs):
    """A senior-facing comparison using each PAST period as the analysis window.

    This is a history comparison, not a forecast of future holding-period
    performance. Negative unseen tracking candidates are omitted from the
    recommended hedge columns when require_positive_tracking=True. Failed
    candidates and scores remain in diagnostic_results/reports. Very short
    periods may provide only an indicative fitted candidate, clearly labelled.
    """
    import contextlib
    import io
    try:
        from IPython.utils.capture import capture_output
    except ImportError:
        capture_output = None
    results, reports, records, weight_rows = {}, {}, [], []
    alternative_rows, alternative_weights = [], []
    for period in windows:
        options = dict(kwargs)
        options.update(sample_window=period, show_plots=False,
                       hedge_objective='variance')
        options.setdefault('rolling_oos', False)
        options.setdefault('boot_n', 0)
        output = io.StringIO()
        context = capture_output() if capture_output else contextlib.redirect_stdout(output)
        try:
            with context as captured:
                result = find_best_hedge(target, data=data, **options)
            results[period] = result
            reports[period] = (captured.stdout if capture_output else output.getvalue())
        except (ValueError, RuntimeError) as error:
            reports[period] = output.getvalue() + str(error)
            records.append({'period': period, 'hedge': '', 'weights_per_100': '',
                            'vol_reduction': np.nan, 'tracking_oos_r2': np.nan,
                            'evidence': 'Cannot fit', 'status': str(error)})
            continue
        for family in ('basket', 'single_stock', 'single_etf', 'single_market'):
            item = result.get('hedge_alternatives', {}).get(family)
            if item is None:
                continue
            reference = item['validation_mode'] == 'IN-SAMPLE'
            show = item['qualified'] or reference
            w = item['weights'] if show else item['weights'].iloc[:0]
            recipe = '; '.join(f'{tk}: {(-x*100):+.1f}' for tk, x in w.items())
            risk = item.get('trade_risk') or {}
            alternative_rows.append({'period': period, 'candidate_type': family,
                'reference_only': item.get('reference_only', family.startswith('single')),
                'hedge': '; '.join(w.index), 'weights_per_100': recipe,
                'tracking_oos_r2': item['unseen_r2'] if show else np.nan,
                'vol_reduction': risk.get('vol_reduction', np.nan) if show else np.nan,
                'status': item['status'], 'qualified': item['qualified']})
            for tk, x in w.items():
                alternative_weights.append({'period': period, 'candidate_type': family,
                    'reference_only': item.get('reference_only', family.startswith('single')),
                    'ticker': tk, 'side': 'SHORT' if x > 0 else 'LONG',
                    'dollars_per_100_target': abs(float(x))*100, 'indicative_only': reference})
        mode = result['validation_mode']
        q = result['ticket'].get('quality_r2', np.nan)
        risk = result.get('trade_risk') or {}
        vr = risk.get('vol_reduction', result.get('holdout_vol_red', np.nan))
        indicative = mode == 'IN-SAMPLE'
        eligible = result.get('trade_eligible', False)
        if require_positive_tracking and np.isfinite(q) and q < 0:
            eligible = False
            status = 'No qualifying hedge; negative unseen tracking R²'
        elif indicative:
            status = 'Indicative candidate only; no unseen validation'
        elif eligible:
            status = result['ticket']['grade']
        else:
            status = 'No qualifying hedge; see diagnostics'
        show_candidate = bool(eligible or indicative)
        weights = result['weights'] if show_candidate else result['weights'].iloc[:0]
        if indicative:
            vr = np.nan
        description = '; '.join(f'{"SHORT" if w > 0 else "LONG"} {tk}'
                                for tk, w in weights.items())
        recipe = '; '.join(f'{tk}: {(-w*100):+.1f}' for tk, w in weights.items())
        records.append({'period': period, 'hedge': description,
                        'weights_per_100': recipe,
                        'vol_reduction': vr if show_candidate else np.nan,
                        'tracking_oos_r2': q if show_candidate else np.nan,
                        'evidence': mode, 'status': status})
        for ticker, weight in weights.items():
            weight_rows.append({'period': period, 'ticker': ticker,
                                'side': 'SHORT' if weight > 0 else 'LONG',
                                'dollars_per_100_target': abs(float(weight))*100,
                                'indicative_only': indicative})
    summary = pd.DataFrame(records)
    display_rows = [[r['period'], r['hedge'] or 'No qualifying hedge',
                     r['weights_per_100'] or '—',
                     f"{r['vol_reduction']*100:.1f}%" if np.isfinite(r['vol_reduction']) else '—',
                     f"{r['tracking_oos_r2']:.3f}" if np.isfinite(r['tracking_oos_r2']) else '—',
                     r['evidence'], r['status']] for r in records]
    _print_table(['HISTORY', 'HEDGE', 'SIGNED $/100', 'UNSEEN VOL CUT',
                  'UNSEEN R²', 'EVIDENCE', 'STATUS'], display_rows,
                 title=f'Primary basket hedges for {target}',
                 note='Negative dollar amounts are shorts; positive amounts are longs. '
                      'IN-SAMPLE rows are indicative candidates, not validated recommendations. '
                      'Negative/failed candidates remain in diagnostic_results. '
                      'Single instruments appear in the reference comparison only.')
    alternative_summary = pd.DataFrame(alternative_rows)
    if len(alternative_summary):
        _print_table(['HISTORY', 'FORM', 'SIGNED $/100', 'EVIDENCE'],
                     [[row['period'], row['candidate_type'], row['weights_per_100'] or '—', row['status']]
                      for row in alternative_rows], title='Basket and single references by history window',
                     note='The basket is primary; single instruments are references. '
                          'Failed candidates have no recommendation weights. In-sample recipes are indicative.')
    return {'summary': summary, 'weights_table': pd.DataFrame(weight_rows),
            'alternatives_summary': alternative_summary,
            'alternative_weights_table': pd.DataFrame(alternative_weights),
            'diagnostic_results': results, 'reports': reports,
            'interpretation': 'past analysis windows',
            'require_positive_tracking': require_positive_tracking}

# =============================================================================
# [Fix 107] AUTO-LAUNCH — the form comes up with CELL 1, no second cell
# =============================================================================
# Until now the workflow was "paste CELL 1, run it, then type hedge_ui() in a
# second cell". That second cell is pure ceremony: there is nothing you can
# usefully do with this module that does not start at the form. It also made
# the tool look broken on first use — CELL 1 runs, prints a few import lines,
# and nothing appears.
#
# The form now renders at the end of CELL 1. Guards, in order:
#   · only inside a notebook (a script/CLI import must stay silent);
#   · only when ipywidgets is importable — otherwise hedge_ui() would print
#     its install banner on every import, which is noise for scripted users;
#   · HEDGE_UI_AUTOSTART = False before the cell (or in the same cell, above
#     this line) suppresses it;
#   · exceptions are swallowed to a one-line hint. Auto-launch is a
#     convenience — it must never stop the module from loading, or a widget
#     problem would take the whole scripted API down with it.
# Re-running the cell re-renders the form, which is the expected notebook
# behaviour; UI_STATE (data, result, report) persists across renders, so a
# re-render costs nothing and loses nothing.
HEDGE_UI_AUTOSTART = globals().get('HEDGE_UI_AUTOSTART', True)

if HEDGE_UI_AUTOSTART and _IN_JUPYTER:
    try:
        import ipywidgets as _W_probe          # noqa: F401  (availability probe)
        hedge_ui()
    except ImportError:
        print("[Fix 107] hedge_ui() not auto-started: ipywidgets is missing.\n"
              "          pip install ipywidgets  (then restart the kernel), "
              "or use the scripted path in CELL 4.")
    except Exception as _e_ui:                 # never break the import
        print(f"[Fix 107] hedge_ui() auto-start failed ({type(_e_ui).__name__}"
              f": {_e_ui}). The module is loaded and usable — call hedge_ui() "
              f"yourself, or use the scripted path in CELL 4.")
