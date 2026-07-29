# =============================================================================
# PCA HEDGE FINDER — complete source, v75 (Fixes 1-75)
# =============================================================================
# Built 29 Jul 2026 on the 28-Jul pack (Fixes 1-65); this build adds 66-75.
# Four cells below, marked CELL 1 / CELL 2 / CELL A / CELL B. In Updated.ipynb
# CELL 1 + CELL 2 + CELL A live in the first cell and CELL B in the second.
# NOTE: running this .py top-to-bottom executes CELL A, which hits Bloomberg.
#
# What Fixes 66-75 change (each is tagged [Fix nn] at the site):
#   [Fix 66] Pre-downloaded data now only requires every leg of the book to
#            HAVE PRICES, instead of demanding the book equal the book the
#            data was downloaded for. The old check crashed quick_rehedge the
#            moment a churning book added or dropped a leg — its exact use
#            case. Ex-legs become candidates; a note reminds you to re-run
#            CELL A after a MATERIAL book change (new sector/market).
#   [Fix 67] Tickers without an exchange code ("AAPL") are rejected up front
#            with a clear message — they used to die mid-download with a
#            cryptic error. Minimum form: "AAPL US". Single-name targets are
#            normalized through the same path as book legs.
#   [Fix 68] Candidate ranking uses |corr| / |cos| with sign-folded loading
#            distance, so ANTI-correlated instruments (valid hedges held
#            LONG) are no longer buried at the bottom of the ranking. The
#            single-instrument benchmarks already picked by |corr|; the
#            basket now searches the same space. NOTE: this can change
#            selected baskets — eyeball a few recipes on adoption.
#   [Fix 69] Pooled OOS R-squared for the NESTED pipeline (selection re-run
#            before each window, all windows scored as ONE sample) — the
#            honest headline number, printed in [1] and used by the ticket.
#   [Fix 70] Circular block-bootstrap 95% CI on the pooled OOS R-squared and
#            tracking error (blocks preserve serial dependence; deterministic
#            seed). Printed in [1b]; conditions on fitted weights, so read it
#            as a floor on the uncertainty.
#   [Fix 71] Rolling OOS curve: the selected config is walked forward with
#            weight refits every 21 rows; the concatenated daily OOS
#            residuals give rolling TE / R-squared as a CURVE (section [1c]
#            + chart) instead of three noisy window scalars.
#   [Fix 72] Section [0] TRADE TICKET at the top of the report: consolidated
#            go / reduce / no-go verdict with reasons, the recipe with an
#            optional $mm column (notional_mm=), TE in bp/day, worst-window
#            sizing guidance and a TE kill-switch level. The R-squared
#            glossary moved to appendix [A] at the bottom.
#   [Fix 73] The Marchenko-Pastur PC count is always taken on the raw sample
#            spectrum — counting Ledoit-shrunk eigenvalues against the
#            unshrunk edge systematically under-counted factors.
#   [Fix 74] Portfolio size_band compares candidates to the gross-weighted
#            AVERAGE leg cap, not the SUM (which excluded everything for a
#            multi-mega-cap book).
#   [Fix 75] The Jupyter styled-table renderer falls back to the boxed text
#            table on ANY error (e.g. missing jinja2) instead of crashing
#            the report.
#
# Verification (synthetic factor-model data; Bloomberg not required): a
# 56-check suite runs the full report end-to-end on the daily and cross-tz
# 2-day paths, portfolio mode on reused data, quick_rehedge with churned
# legs, ticker validation, sign-aware ranking, MP-count consistency,
# bootstrap determinism and coverage, the 0.45/0.64/0.81 window-dispersion
# case, every verdict gate, both chart figures (Agg) and both table
# renderers. All checks pass. Anything needing live data (request flags,
# real tickers) still needs one CELL A run against a terminal.
# =============================================================================

# =============================================================================
# v77 (29 Jul 2026) — SHORT-WINDOW MODE added as CELL S, IN SAMPLE ONLY.
# CELL 1 and CELL 2 are byte-identical to v75 and find_best_hedge() is
# unchanged. CELL S adds a separate estimator for windows of ~10-25 sessions;
# CELL 3 runs GMD AU Equity over three nested July windows ending 28-Jul.
# Every number CELL S prints is fitted and scored on the same rows: it is an
# attribution of a window that has already happened, not a forecast. See the
# CELL S header for why this could not be done by passing dates into
# find_best_hedge(), and for the two guards that replace the missing hold-out.
# =============================================================================

# =============================================================================
# CELL 1: SETUP (run once)
# =============================================================================

import numpy as np
import pandas as pd
import blpapi
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import RidgeCV
from statsmodels.tsa.stattools import adfuller
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import warnings

warnings.filterwarnings('ignore')

RIDGE_ALPHAS = np.logspace(-4, 2, 25)

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

# [Fix 14] ETF whitelist (short names) auto-generated — always in sync
ETF_SHORT_SET = {t.split(' ')[0] for lst in CONTROL_ETFS.values() for t in lst}

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
    'JP': 6.0,                         # TSE 15:00 JST
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
    from IPython.display import display as _ipy_display
    from IPython import get_ipython as _get_ipython
    _IN_JUPYTER = _get_ipython() is not None
except Exception:
    _IN_JUPYTER = False


def _print_table(headers, rows, indent='  '):
    """[Fix 41/51] Render rows as a table.

    [Fix 41] gave every printed block a boxed unicode layout. [Fix 51] adds a
    styled HTML rendering when the notebook is running inside Jupyter (dark
    header, zebra rows, right-aligned numeric columns, monospace figures) and
    keeps the boxed unicode version as the terminal fallback. Same signature
    and same values as before, so every existing call site is upgraded with
    no other edit."""
    rows = [[str(x) for x in r] for r in rows]
    # [Fix 75] the styled path needs jinja2 (pandas Styler) — present in any
    # real Jupyter install, but if it is missing or the Styler API changes,
    # fall back to the boxed table instead of crashing the report.
    try:
      if _IN_JUPYTER and rows:
        df = pd.DataFrame(rows, columns=list(headers))
        # a column is "numeric" if every cell starts with a digit, sign or $
        num_cols = [h for h in df.columns
                    if df[h].str.match(r'^[+\-$]?\d').all()]
        sty = (df.style.hide(axis='index')
               .set_table_styles([
                   {'selector': '', 'props':
                    'border-collapse:collapse;margin:4px 0 10px 14px'},
                   {'selector': 'th', 'props':
                    'background:#22436a;color:#ffffff;text-align:left;'
                    'padding:5px 12px;font-size:12px;'
                    'font-family:Menlo,Consolas,monospace'},
                   {'selector': 'td', 'props':
                    'padding:4px 12px;font-size:12px;'
                    'font-family:Menlo,Consolas,monospace;'
                    'border-bottom:1px solid #dfe4ea'},
                   {'selector': 'tr:nth-child(even) td', 'props':
                    'background:#f5f7fa'}])
               .set_properties(subset=num_cols, **{'text-align': 'right'}))
        _ipy_display(sty)
        return
    except Exception:
        pass                       # [Fix 75] fall through to the boxed table
    # ── terminal fallback: the original [Fix 41] boxed layout, unchanged ────
    widths = [max(len(headers[i]), max((len(r[i]) for r in rows), default=0))
              for i in range(len(headers))]

    def hline(l, m, r):
        print(indent + l + m.join('─' * (w + 2) for w in widths) + r)

    def prow(vals):
        cells = []
        for i, v in enumerate(vals):
            pad = ' ' * (widths[i] - len(v))
            # right-align $-amount cells, left-align everything else
            if v[:1] == '$':
                cells.append(f' {pad}{v} ')
            else:
                cells.append(f' {v}{pad} ')
        print(indent + '│' + '│'.join(cells) + '│')

    hline('┌', '┬', '┐')
    prow(headers)
    hline('├', '┼', '┤')
    for r in rows:
        prow(r)
    hline('└', '┴', '┘')


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
        req.set("nonTradingDayFillOption", "NON_TRADING_WEEKDAYS")
        req.set("nonTradingDayFillMethod", "PREVIOUS_VALUE")
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
                     'Health Care', 'Energy', 'Consumer Discretionary']:
        if (tgt_bics_lvl2 and key_word.lower() in str(tgt_bics_lvl2).lower()) or \
           (key_word.lower() in str(tgt_gics_sec).lower()):
            sector_key = key_word
            break

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
    peer_matches = []
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
    all_etfs = sorted(set(CONTROL_ETFS.get(market, []) +
                          CONTROL_ETFS.get(country, []) +
                          CONTROL_ETFS.get('FACTOR', []) +   # [Fix 43]
                          CONTROL_ETFS['GLOBAL']))

    if meta is not None:                          # [Fix 49] expose discovery
        meta['index_ticker'] = local_index_ticker  # facts for PIT membership
        meta['non_index_shorts'] = (
            {t.split(' ')[0] for t in peer_matches} |
            {t.split(' ')[0] for t in industry_matches} |
            {t.split(' ')[0] for t in all_etfs})

    # Merge + [Fix 7] dedupe by short name but KEEP full tickers
    # (local members take priority on collision)
    merged, seen_short = [], set()
    for tk in local_members + peer_matches + industry_matches + all_etfs:
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
                if tk.split(' ')[0] in ETF_SHORT_SET:
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


# =============================================================================
# CELL 2: ENGINE
# =============================================================================
# ── [Fix 52] METRICS GLOSSARY ────────────────────────────────────────────────
# The report prints four different R-squared numbers and they are routinely
# confused with each other. They are not competing estimates of one quantity;
# each answers a different question, and the differences between them are the
# most informative part of the report. Printed at the top of section [1].
R2_GLOSSARY = """\
  HOW TO READ THE FOUR R-SQUARED NUMBERS (each answers a different question)
  1) In-sample R2            Fit and scored on the SAME window. Always the
                             highest. A sanity check on the fit, never a
                             measure of the hedge.
  2) Full-data CV OOS R2     Walk-forward: fit on 'lookback' days, score on
                             the NEXT unseen 42d window, averaged over folds.
                             Honest for the WEIGHTS, but the config
                             (lookback / PCs / basket size) was chosen by
                             looking at ALL folds, so the recipe as a whole
                             is still slightly flattered.
  3) THIS config, unseen OOS The chosen config re-fit strictly on data
                             BEFORE each outer window and scored on it.
                             Honest weights AND honest windows; a small
                             selection bias remains because the config was
                             picked using full-data CV.
  4) Pipeline nested OOS     The ENTIRE pipeline (CV -> selection -> refit)
                             re-run using only data before each outer
                             window. Closest to what running this tool live
                             would actually have delivered.
  Expected ordering: (1) >= (2) >= (3) ~= (4). A large (1)-vs-(4) gap means
  overfitting. Trade on (3)/(4); quote (1) only as a caveat."""
# ─────────────────────────────────────────────────────────────────────────────
# [Fix 42] Robust PCA inputs
#   Ordinary PCA on a sample covariance is optimal only for Gaussian data. Daily
#   equity returns are fat-tailed and skewed, so a handful of jump days can
#   dominate the leading components and distort the loading-space "similarity"
#   used to pick candidates. Two low-cost defenses, applied ONLY to the PCA
#   candidate-SELECTION step (never to the RidgeCV hedge ratios, which stay fit
#   on the true returns):
#     • winsorize_pct : clip each column at its pct / 1-pct quantiles before
#       standardizing, so outliers cannot hijack the eigenvectors.
#     • robust_cov='ledoit' : replace the sample covariance with a Ledoit-Wolf
#       shrinkage estimate (well-conditioned when p >> n, the norm here).
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
    """Fit n_pc components on standardized returns. robust_cov='ledoit'
    eigendecomposes a Ledoit-Wolf shrinkage covariance; otherwise ordinary PCA.
    Returns a _PCAShim so downstream loading code is unchanged."""
    X = np.asarray(tr_sc, dtype=float)
    if robust_cov == 'ledoit':
        from sklearn.covariance import LedoitWolf
        cov = LedoitWolf().fit(X).covariance_
        evals, evecs = np.linalg.eigh(cov)
        idx = np.argsort(evals)[::-1][:n_pc]
        evals = np.clip(evals[idx], 1e-12, None)
        comps = evecs[:, idx].T                       # (n_pc x p)
        total = float(np.trace(cov))
        evr = evals / total if total > 0 else np.zeros_like(evals)
        return _PCAShim(comps, evals, evr)
    pca = PCA(n_components=n_pc).fit(X)
    return _PCAShim(pca.components_, pca.explained_variance_,
                    pca.explained_variance_ratio_)


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
        r2s = np.where(sst > 1e-12, 1.0 - sse / sst, np.nan)
    tes = rs.std(axis=1) * ann
    r2s = r2s[np.isfinite(r2s)]
    if not len(r2s):
        return None
    return {'r2_lo': float(np.percentile(r2s, 2.5)),
            'r2_hi': float(np.percentile(r2s, 97.5)),
            'te_lo': float(np.percentile(tes, 2.5)),
            'te_hi': float(np.percentile(tes, 97.5)),
            'block': b, 'n': n, 'n_boot': int(n_boot)}


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
    if not np.isnan(pooled) and pooled > 0:
        z = np.arctanh(min(np.sqrt(pooled), 0.999))
        zsd = 1.96 / np.sqrt(max(n_eff - 3, 1))
        out['band'] = (float(np.tanh(z - zsd) ** 2),
                       float(np.tanh(z + zsd) ** 2))
    band = out['band']
    for _, r in detail.iterrows():
        if band is None:
            out['flags'].append('')
        elif band[0] <= r['r2'] <= band[1]:
            out['flags'].append('noise-range')
        else:
            out['flags'].append('BELOW band' if r['r2'] < band[0]
                                else 'above band')
    if detail['tgt_vol'].nunique() > 1:
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


def _ticket_verdict(quality, worst_r2, overfit_gap, min_sim, trend,
                    ref_pca, ref_simple, roll_breach):
    """[Fix 72] One consolidated go / reduce / no-go verdict for the ticket.

    Gates (heuristics, deliberately conservative — override them with
    judgment, not by re-running until the box says yes):
      ✗  pooled OOS R2 < 0.20 (vol cut under ~11%; costs likely eat it), OR
         in-sample-vs-OOS gap >= 0.35 (clear overfit), OR any window with
         NEGATIVE OOS R2 (the hedge ADDED risk there), OR no OOS evidence.
      △  pooled R2 < 0.45, worst window < 0.15, gap >= 0.15, basket turnover
         across windows (min weight cosine <= 0.5), R2 deteriorating into
         the present, live rolling TE already past the kill-switch, or a
         single instrument matching the basket OOS.
      ✓  none of the above.
    Returns (grade, [reasons])."""
    if quality is None or np.isnan(quality):
        return ('? INSUFFICIENT OOS EVIDENCE',
                ['no valid unseen windows — every number in this report '
                 'should be read as in-sample'])
    reasons, fail, warn = [], False, False
    if quality < 0.20:
        fail = True
        reasons.append(f'pooled OOS R² {quality:.2f} < 0.20 — the hedge '
                       f'explains too little to pay for')
    if not np.isnan(overfit_gap) and overfit_gap >= 0.35:
        fail = True
        reasons.append(f'in-sample vs OOS gap {overfit_gap:.2f} ≥ 0.35 — '
                       f'clearly overfit')
    if not np.isnan(worst_r2) and worst_r2 < 0.0:
        fail = True
        reasons.append(f'worst window OOS R² {worst_r2:.2f} < 0 — the hedge '
                       f'ADDED risk in that window')
    if roll_breach:
        warn = True
        reasons.append('latest rolling TE is already above the kill-switch '
                       'level — do not add risk on this hedge')
    if not fail:
        if quality < 0.45:
            warn = True
            reasons.append(f'pooled OOS R² {quality:.2f} is moderate')
        if not np.isnan(worst_r2) and worst_r2 < 0.15:
            warn = True
            reasons.append(f'worst window OOS R² {worst_r2:.2f} — size off '
                           f'this window, not the average')
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
            reasons.append('R² deteriorates toward the MOST RECENT window — '
                           'trust the newest reading, not the mean')
    if (not np.isnan(ref_pca) and not np.isnan(ref_simple)
            and ref_simple >= ref_pca):
        warn = True
        reasons.append('a single-instrument hedge matches the basket OOS — '
                       'prefer the simple hedge (see [3])')
    grade = ('✗ DO NOT TRADE AS-IS' if fail
             else ('△ TRADE AT REDUCED SIZE' if warn else '✓ TRADE'))
    if not reasons:
        reasons.append('all gates passed: pooled OOS strong, worst window '
                       'acceptable, no overfit signal, weights stable')
    return grade, reasons


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


def _mask_stale(prices, max_flat_days=7):
    """[Fix 56] Mask stale (forward-filled) prices — the suspension guard.

    A-share names halt for weeks at a time; the forward fill keeps the last
    print, producing long runs of identical prices and therefore zero
    returns. Those zeros dilute every correlation and beta the selection
    relies on: a suspended stock looks like a LOW-beta stock and can sneak
    into the basket (or push a genuinely better name out of it). Any price
    unchanged for more than `max_flat_days` consecutive sessions is masked,
    so the complete-window filters downstream exclude the affected stretch
    instead of learning from stale data.

    The default (7) is deliberately longer than any holiday cluster — Golden
    Week and CNY fills are ~5 weekdays — so ordinary market holidays are
    left untouched. Set mask_stale_days=None in find_best_hedge to disable.
    """
    out = prices.copy()
    n_masked = 0
    for c in out.columns:
        s = out[c]
        flat = s.eq(s.shift())
        grp = (~flat).cumsum()            # one group per constant-price run
        run = flat.groupby(grp).cumsum()
        bad_grp = set(grp[run > max_flat_days])
        if bad_grp:
            out[c] = s.mask(grp.isin(bad_grp) & flat)   # mask the whole run
            n_masked += 1
    if n_masked:
        print(f"  [Fix 56] stale-price guard: masked suspension-like flat "
              f"runs (>{max_flat_days} sessions) in {n_masked} names")
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
    return reg, reg.score(X, y), y - reg.predict(X)


def _n_pc_auto(ret_scaled, cap, robust_cov='none'):
    """[Fix 22] Number of significant PCs via the Marchenko-Pastur upper edge.

    [Fix 73] the count is now ALWAYS taken on the raw sample spectrum. The
    MP edge describes the bulk of SAMPLE eigenvalues under a pure-noise
    null; Ledoit-Wolf shrinkage pulls large sample eigenvalues toward the
    grand mean, so the old [Fix 42] branch — shrunk eigenvalues against the
    unshrunk edge — systematically UNDER-counted factors, and
    robust_cov='ledoit' silently ran with fewer PCs than the same data under
    'none'. Shrinkage still stabilizes the eigenVECTORS in _pca_fit (which
    is what the similarity ranking consumes); the eigenvalue COUNT is a
    hypothesis test that belongs on the raw spectrum. `robust_cov` is kept
    in the signature so call sites are unchanged."""
    n, p = ret_scaled.shape
    ev = PCA().fit(ret_scaled).explained_variance_
    mp_edge = (1.0 + np.sqrt(p / n)) ** 2
    k = int(np.sum(ev > mp_edge))
    return int(min(max(2, k), cap, 15))


def download_hedge_data(target, candidates=None, session=None,
                        years=3, min_mktcap_usd_mm=5000, exclude=None,
                        force_include=None, fetch_mktcap_hist=True,
                        fetch_pit_members=True):
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

    return {'target': target, 'target_label': label,
            'portfolio': {'legs': legs, 'weights': pf_w,
                          'is_portfolio': is_portfolio, 'label': label},
            'prices': prices, 'mktcap_usd_mm': mktcap,
            'mktcap_hist': mktcap_hist,
            'pit_members': pit_members,                        # [Fix 49]
            'non_index_shorts': sorted(non_index_shorts)}


def find_best_hedge(
    target_ticker,
    candidates=None,
    data=None,                    # [Fix 31] dict from download_hedge_data()
    session=None,
    lookback_options=(126, 252),
    pc_options='auto',            # 'auto' or a list of ints, e.g. [3, 5, 8]
    basket_size_options=(3, 5, 7),
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
    mask_stale_days=7,            # [Fix 56] mask prices that stay flat for
                                  # more than N consecutive sessions
                                  # (suspensions); None disables the guard
    notional_mm=None,             # [Fix 72] gross book notional in USD mm —
                                  # dollarizes the trade-ticket amounts
    rolling_oos=True,             # [Fix 71] walk-forward rolling OOS curve
                                  # (section [1c] + chart)
    rolling_refit_every=21,       # [Fix 71] rows between weight refits
    rolling_max_windows=12,       # [Fix 71] refit segments to walk back
    boot_n=2000,                  # [Fix 70] bootstrap draws for the CI on
                                  # pooled OOS R2 / TE; 0 disables
    show_plots=True,
):
    outer_window = outer_window or cv_test_window
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
            print(f"  [Fix 66] note: data was downloaded for "
                  f"{data.get('target_label', data.get('target'))} — reusing "
                  f"its universe for {target_short}. Fine for leg churn on "
                  f"the same book; re-run CELL A after a material change.")
        prices = data['prices'].copy()
        print(f"Using pre-downloaded data: {prices.shape[0]} rows × "
              f"{prices.shape[1]} tickers (no API calls)")
    else:
        data = download_hedge_data(target_ticker, candidates=candidates,
                                   session=session or get_session(),
                                   min_mktcap_usd_mm=min_mktcap_usd_mm,
                                   exclude=exclude,
                                   force_include=force_include)  # [Fix 40]
        prices = data['prices'].copy()

    # [Fix 40] Resolve the must-have securities against the downloaded
    # columns BEFORE any filter runs, so every filter below can exempt them.
    forced, fi_unres = _resolve_force_include(force_include, prices.columns,
                                              target_ticker)
    if fi_unres:
        print(f"  ⚠ force_include: {fi_unres} not in the downloaded data — "
              f"re-run download_hedge_data(..., force_include=...) to fetch "
              f"them (they will be ignored this run)")
    if forced:
        print(f"  Force-include active: {', '.join(forced)} will be held in "
              f"every basket (CV folds, nested windows, and final recipe)")

    # [Fix 36] Manual exclusions on COLUMNS — works on pre-downloaded data
    kept_cols, removed_cols = _apply_exclusions(
        [c for c in prices.columns if c not in target_keepset], exclude)
    readd = [c for c in removed_cols if c in forced]       # [Fix 40]
    if readd:
        print(f"  ⚠ {', '.join(readd)} in both exclude= and force_include= — "
              f"force_include wins, keeping")
        kept_cols += readd
        removed_cols = [c for c in removed_cols if c not in forced]
    if removed_cols:
        print(f"  Manual exclusions: dropped {len(removed_cols)} names "
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
        print(f"  [Fix 49] point-in-time index membership active — "
              f"{len(pm_dates)} snapshots, {len(pm_union)} names ever members")
    if min_mktcap_usd_mm and not pit_active:
        # static (current-cap) floor on COLUMNS — used only when point-in-time
        # caps are unavailable or pit_size=False. NOTE: this legacy path carries
        # the "big now / small then" look-ahead that [Fix 44] removes.
        if not caps:
            print("  ⚠ market-cap floor requested but data has no "
                  "'mktcap_usd_mm' — re-run download_hedge_data() to enable it")
        else:
            kept, dropped, unknown = list(target_keepset), 0, 0
            for c in prices.columns:
                if c in target_keepset:
                    continue
                if c.split(' ')[0] in ETF_SHORT_SET or c in forced:
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
                print(f"  Market-cap floor {_fmt_mktcap(min_mktcap_usd_mm)}: "
                      f"dropped {dropped} names"
                      + (f" ({unknown} unknown caps kept)" if unknown else ""))
                prices = prices[_uniq(kept)]
    elif pit_active:
        print(f"  [Fix 44] point-in-time size filtering active — the "
              f"{_fmt_mktcap(min_mktcap_usd_mm)} floor is applied as-of each "
              f"window (no current-cap look-ahead); universe not pre-trimmed")

    prices = prices.ffill()
    if mask_stale_days:                                     # [Fix 56]
        prices = _mask_stale(prices, mask_stale_days)
    prices = prices.dropna(axis=1, thresh=int(len(prices) * 0.85))
    if is_portfolio:                             # [Fix 46]
        _pl = [c for c in pf_legs if c in prices.columns]
        if len(_pl) < 2:
            raise ValueError(
                f"Fewer than 2 portfolio legs have ≥85% price history "
                f"({pf_legs}) — cannot build the book")
    elif target_ticker not in prices.columns:    # [Fix 21]
        raise ValueError(
            f"{target_ticker} has price data for less than 85% of the window — "
            "history too short for this configuration")
    # [Fix 40] a forced name with <85% history cannot be modelled — say so
    # loudly instead of silently forcing NaNs into every window
    lost = [c for c in forced if c not in prices.columns]
    if lost:
        print(f"  ⚠ force_include: {', '.join(lost)} dropped — less than 85% "
              f"price history in the window; cannot be forced into baskets")
        forced = [c for c in forced if c in prices.columns]

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
        print(f"  ⚠ unknown exchange close for {target_ticker} — timezone "
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
        print(f"  Restricting universe to closes within "
              f"{tz_tolerance_hours:.1f}h of the target's "
              f"({len(others)} → {len(keep_tz)} candidates"
              + (f"; {len(keep_tz) - len(same_tz)} kept by force_include"
                 if len(keep_tz) > len(same_tz) else "")
              + "; set restrict_to_target_tz=False to keep global names)")
        prices = prices[_uniq(list(target_keepset) + keep_tz)]
    elif restrict_to_target_tz is True and len(same_tz) == len(others):
        print(f"  All candidates already close within "
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
        print(f"  ⚠ Universe treated as cross-timezone ({reason}) → "
              f"switching to 2-day overlapping returns to correct "
              f"async-trading bias")

    rets = np.log(prices / prices.shift(1))
    if is_portfolio:                             # [Fix 46] synthetic book return
        legs_present = [c for c in pf_legs if c in rets.columns]
        if len(legs_present) < 2:
            raise ValueError(f"Only {len(legs_present)} portfolio legs survived "
                             f"filtering — cannot build the book ({pf_legs})")
        if len(legs_present) < len(pf_legs):
            miss = [c for c in pf_legs if c not in legs_present]
            print(f"  ⚠ portfolio legs dropped by filtering: {miss} — weights "
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

    # ── Data sufficiency check [Fix 15: message matches actual params] ──────
    min_rows = (max(lookback_options) + cv_test_window * cv_n_folds
                + outer_window * outer_folds)
    if len(rets) < min_rows:
        raise ValueError(
            f"Insufficient data for {cv_n_folds}-fold CV + {outer_folds} outer "
            f"validation windows. Required: {min_rows} rows, available: {len(rets)}.\n"
            f"  - reduce lookback_options (current: {list(lookback_options)})\n"
            f"  - reduce cv_n_folds (current: {cv_n_folds}), "
            f"cv_test_window (current: {cv_test_window}), "
            f"or outer_folds (current: {outer_folds})")

    universe = [c for c in prices.columns
                if c not in set(pf_legs) and c != target_ticker]   # [Fix 46]
    forced = [c for c in forced if c in universe]           # [Fix 40]

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
            if c.split(' ')[0] in ETF_SHORT_SET or c in forced:
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
    print(f"  ✓ {len(rets)} return rows, {len(universe) + 1} tickers retained")

    # ── Reusable building blocks ─────────────────────────────────────────────
    def _forced_basket(ranked, ok, bsize):
        """[Fix 40] Assemble a basket that always contains the forced names
        (those usable in this window), topped up with the best-ranked other
        candidates. Forced names OCCUPY SLOTS inside the same basket size,
        so CV metrics measure the basket that would actually be traded; if
        more names are forced than basket_size, the basket grows to hold
        them all."""
        f_ok = [c for c in forced if c in ok]
        rest = [t for t in ranked if t not in f_ok]
        return f_ok + rest[:max(0, bsize - len(f_ok))]

    def _select_and_fit(train_rets, pc_spec, bsize):
        """Select a basket via PCA ranking on train_rets and fit RidgeCV."""
        ok = train_rets.columns[(train_rets.notna().all()) & (train_rets.std() > 1e-6)]
        if target_ticker not in ok:
            raise RuntimeError(f"{target_short} has incomplete data or zero "
                               f"variance in this window — cannot fit.")
        tr = train_rets[ok]
        u = [c for c in _eligible(tr.index[-1]) if c in ok]     # [Fix 44/45] PIT
        pca_cols = [c for c in tr.columns if c != PORTFOLIO_COL]  # [Fix 46]
        tr_w = _winsorize_returns(tr[pca_cols], winsorize_pct)   # [Fix 42]
        sc = StandardScaler()
        tr_sc = pd.DataFrame(sc.fit_transform(tr_w), index=tr.index,
                             columns=pca_cols)
        cap = len(pca_cols) - 1
        n_pc = (_n_pc_auto(tr_sc, cap, robust_cov) if pc_spec == 'auto'
                else int(min(int(pc_spec), cap)))
        pca = _pca_fit(tr_sc, n_pc, robust_cov)                  # [Fix 42]
        # [Fix 23] scale loadings by sqrt(eigenvalue): similarity in factor-
        # exposure space, where PC1 counts far more than higher (noisier) PCs
        lds = pd.DataFrame(pca.components_.T * np.sqrt(pca.explained_variance_),
                           index=pca_cols,
                           columns=[f'PC{i+1}' for i in range(n_pc)])
        lds = _inject_synth_loadings(lds)                        # [Fix 46]
        rank = _rank_scores(lds, tr, target_ticker, u)
        basket = _forced_basket(rank.index.tolist(), ok, bsize)   # [Fix 40]
        if len(basket) < 2:                      # [Fix 21]
            raise RuntimeError("Fewer than 2 valid candidates in this window "
                               "— cannot build a basket.")
        reg, r2, resid = _fit_basket(tr, target_ticker, basket)
        return tr, rank, basket, reg, r2, resid, n_pc, pca, lds

    def _eval_on_window(reg, basket, test_rets):
        """Score a fitted basket on an unseen window → (r2, vol_red) or NaNs."""
        needed = basket + [target_ticker]
        if not all(c in test_rets.columns and test_rets[c].notna().all()
                   for c in needed):
            return np.nan, np.nan
        r2 = reg.score(test_rets[basket].values, test_rets[target_ticker].values)
        resid = (test_rets[target_ticker].values -
                 reg.predict(test_rets[basket].values))
        tgt_std = np.std(test_rets[target_ticker].values) * ann_sqrt
        vr = 1 - (np.std(resid) * ann_sqrt) / tgt_std if tgt_std > 1e-6 else 0.0
        return r2, vr

    pc_grid = ['auto'] if pc_options == 'auto' else list(pc_options)   # [Fix 4]

    def _walk_forward_cv(rets_sub, verbose=False):
        """Run the full walk-forward CV grid on rets_sub → summary DataFrame
        (or None if every fold failed)."""
        results = []
        for lookback in lookback_options:
            if lookback + cv_test_window * cv_n_folds > len(rets_sub):
                if verbose:
                    print(f"  Skipping lookback={lookback} (insufficient data)")
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

                # [Fix 6] complete data + non-zero variance only, no fillna
                ok = ret_tr_all.columns[(ret_tr_all.notna().all()) &
                                        (ret_tr_all.std() > 1e-6)]
                ok = [c for c in ok if ret_te_all[c].notna().all()]
                if target_ticker not in ok:
                    if verbose:
                        print(f"  ⚠ skipping fold {fold} (lookback {lookback}): "
                              f"{target_short} incomplete or zero variance")
                    continue
                ret_tr = ret_tr_all[ok]
                ret_te = ret_te_all[ok]
                if len(ret_tr) < 50 or len(ret_te) < 10:
                    continue
                cur_uni = [c for c in _eligible(ret_tr.index[-1]) if c in ok]  # [Fix 44/45]

                pca_cols = [c for c in ret_tr.columns if c != PORTFOLIO_COL]   # [Fix 46]
                ret_tr_w = _winsorize_returns(ret_tr[pca_cols], winsorize_pct)  # [Fix 42]
                scaler = StandardScaler()
                ret_tr_sc = pd.DataFrame(scaler.fit_transform(ret_tr_w),
                                         index=ret_tr.index, columns=pca_cols)
                cap = len(pca_cols) - 1
                for pc_spec in pc_grid:
                    n_pc = (_n_pc_auto(ret_tr_sc, cap, robust_cov)
                            if pc_spec == 'auto' else int(min(pc_spec, cap)))
                    pca = _pca_fit(ret_tr_sc, n_pc, robust_cov)               # [Fix 42]
                    # [Fix 23] eigenvalue-weighted loadings (see _select_and_fit)
                    loadings = pd.DataFrame(
                        pca.components_.T * np.sqrt(pca.explained_variance_),
                        index=pca_cols,
                        columns=[f'PC{i+1}' for i in range(n_pc)])
                    loadings = _inject_synth_loadings(loadings)              # [Fix 46]
                    ranked = _rank_scores(loadings, ret_tr, target_ticker,
                                          cur_uni).index.tolist()
                    for bsize in basket_size_options:
                        basket = _forced_basket(ranked, ok, bsize)  # [Fix 40]
                        if len(basket) < 2:
                            continue
                        reg, r2_tr, _ = _fit_basket(ret_tr, target_ticker, basket)
                        n, p = len(ret_tr), len(basket)
                        adj_r2 = 1 - (1 - r2_tr) * (n - 1) / max(1, n - p - 1)
                        r2_te, vol_red = _eval_on_window(reg, basket, ret_te)
                        if np.isnan(r2_te):
                            continue
                        results.append({
                            'lookback': lookback, 'pc_spec': str(pc_spec),
                            'n_pcs': n_pc, 'basket_size': bsize, 'fold': fold,
                            'r2_train': r2_tr, 'adj_r2_train': adj_r2,
                            'r2_test': r2_te, 'vol_red_test': vol_red,
                            'gross': float(np.abs(reg.coef_).sum()),  # [Fix 38]
                        })
        if not results:
            return None, None
        cv = pd.DataFrame(results)
        summary = cv.groupby(['lookback', 'pc_spec', 'basket_size']).agg(
            avg_r2_oos=('r2_test', 'mean'), std_r2_oos=('r2_test', 'std'),
            avg_vol_red=('vol_red_test', 'mean'),
            avg_adj_r2=('adj_r2_train', 'mean'),
            avg_gross=('gross', 'mean'),
            n_folds=('fold', 'count')).reset_index()
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
        summary['composite'] = ((summary['avg_r2_oos'] - 0.5 * summary['std_r2_oos']) * 0.6
                                + summary['avg_vol_red'] * 0.4
                                - gross_penalty * summary['avg_gross'])
        if max_gross is not None:
            within = summary[summary['avg_gross'] <= max_gross]
            if len(within):
                summary = within.reset_index(drop=True)
            else:
                print(f"  ⚠ no config satisfies max_gross={max_gross:.1f} — "
                      f"cap ignored for this run")
        return summary, cv

    # ── STEP 3: NESTED WALK-FORWARD VALIDATION [Fix 20] ──────────────────────
    # For each of the last `outer_folds` windows: rerun CV + selection + refit
    # using ONLY data prior to that window, then score on it. This measures
    # the whole pipeline out-of-sample, across multiple periods — not a
    # single-window estimate.
    print(f"\nNested walk-forward validation "
          f"({outer_folds} outer windows × {outer_window}d; "
          f"inner CV: {cv_n_folds} folds × {cv_test_window}d)...")
    nested_rows = []
    nested_y_all, nested_res_all = [], []                     # [Fix 69]
    N = len(rets)
    for j in range(1, outer_folds + 1):
        o_end = N - (j - 1) * outer_window
        o_start = o_end - outer_window
        inner = rets.iloc[:max(0, o_start - purge)]   # [Fix 39] purge gap
        outer_test = rets.iloc[o_start:o_end]
        summary_j, _ = _walk_forward_cv(inner)
        if summary_j is None:
            print(f"  outer window {j}: inner CV failed — skipped")
            continue
        cfg = summary_j.loc[summary_j['composite'].idxmax()]
        lb_j = int(cfg['lookback'])
        try:
            _, _, bkt_j, reg_j, _, _, _, _, _ = _select_and_fit(
                inner.iloc[-lb_j:], cfg['pc_spec'], int(cfg['basket_size']))
            r2_j, vr_j = _eval_on_window(reg_j, bkt_j, outer_test)
        except RuntimeError as e:
            print(f"  outer window {j}: refit failed ({e}) — skipped")
            continue
        if not np.isnan(r2_j):                                # [Fix 69]
            _yo = outer_test[target_ticker].values
            nested_y_all.append(_yo)
            nested_res_all.append(_yo - reg_j.predict(
                outer_test[bkt_j].values))
        nested_rows.append({
            'window': j, 'start': outer_test.index[0], 'end': outer_test.index[-1],
            'lookback': lb_j, 'pc_spec': cfg['pc_spec'],
            'basket_size': int(cfg['basket_size']),
            'r2_oos': r2_j, 'vol_red_oos': vr_j,
        })
        print(f"  outer window {j} ({outer_test.index[0]:%Y-%m-%d} → "
              f"{outer_test.index[-1]:%Y-%m-%d}): OOS R²={r2_j:.3f}, "
              f"vol red={vr_j*100:.1f}%  "
              f"[picked lb={lb_j}, pc={cfg['pc_spec']}, size={int(cfg['basket_size'])}]")
    nested = pd.DataFrame(nested_rows)
    nested_valid = nested.dropna(subset=['r2_oos']) if len(nested) else nested
    if len(nested_valid):
        nested_r2_mean = nested_valid['r2_oos'].mean()
        nested_r2_std = nested_valid['r2_oos'].std(ddof=0)
        nested_vr_mean = nested_valid['vol_red_oos'].mean()
    else:
        nested_r2_mean = nested_r2_std = nested_vr_mean = np.nan
        print("  ⚠ nested validation produced no valid windows")
    # [Fix 69] pooled R² across the CONCATENATED nested windows — the same
    # statistic as [Fix 65]'s pooled figure, but for the HONEST pipeline
    # (selection re-run before each window). This is the headline number.
    nested_pooled = np.nan
    if nested_y_all:
        _yc = np.concatenate(nested_y_all)
        _rc = np.concatenate(nested_res_all)
        _sst = float(np.sum((_yc - _yc.mean()) ** 2))
        if _sst > 1e-12:
            nested_pooled = 1.0 - float(np.sum(_rc ** 2)) / _sst

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
                ok = tr_all.columns[(tr_all.notna().all()) &
                                    (tr_all.std() > 1e-6)]
                if target_ticker not in ok:
                    continue
                tr = tr_all[ok]
                pool = [c for c in ok if c != target_ticker
                        and c not in set(pf_legs) and pool_filter(c)]
                if not pool:
                    continue
                pick = tr[pool].corrwith(tr[target_ticker]).abs().idxmax()
                reg_b, r2_tr, _ = _fit_basket(tr, target_ticker, [pick])
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
        return pd.DataFrame(rows)

    etf_bench = _single_bench(lambda c: c.split(' ')[0] in ETF_SHORT_SET)
    name_bench = _single_bench(lambda c: c.split(' ')[0] not in ETF_SHORT_SET)
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
                test = rets.iloc[os_:oe_]
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
        y_cat = np.concatenate(y_all)
        r_cat = np.concatenate(res_all)
        sst = float(np.sum((y_cat - y_cat.mean()) ** 2))
        pooled = 1.0 - float(np.sum(r_cat ** 2)) / sst if sst > 1e-12 else np.nan
        # [Fix 70] hand back the pooled arrays so the bootstrap CI can
        # resample the exact series the pooled R² was computed on
        return out + (pd.DataFrame(rows), pooled, y_cat, r_cat)

    # ── STEP 4: FULL-DATA CV → SELECT LIVE CONFIG ────────────────────────────
    print(f"\nRunning full-data walk-forward CV for live config selection...")
    summary, cv_df = _walk_forward_cv(rets, verbose=True)
    if summary is None:
        raise RuntimeError("All CV folds failed — the stock likely lacks "
                           "sufficient liquidity or price history.")
    best = summary.loc[summary['composite'].idxmax()]
    best_lookback = int(best['lookback'])
    best_pc_spec = best['pc_spec']
    best_bsize = int(best['basket_size'])

    # ── STEP 5: FINAL REFIT ON FULL DATA (live weights) ──────────────────────
    (returns_final, final_rank, basket_final, reg_f,
     r2_final, resid_final, n_pc_final, pca_f, loadings_f) = _select_and_fit(
        rets.iloc[-best_lookback:], best_pc_spec, best_bsize)   # [Fix 46] lds returned

    # [Fix 40] if a forced name has bad data in the FINAL window it cannot be
    # held — flag it explicitly rather than let the user assume it is inside
    miss_final = [c for c in forced if c not in basket_final]
    if miss_final:
        print(f"  ⚠ force_include: {', '.join(miss_final)} could not be held "
              f"in the final basket (incomplete data or zero variance in the "
              f"final {best_lookback}d window)")

    weights_final = pd.Series(reg_f.coef_, index=basket_final)
    te_final = np.std(resid_final) * ann_sqrt
    tgt_std_final = returns_final[target_ticker].std() * ann_sqrt
    vol_red_final = 1 - te_final / tgt_std_final if tgt_std_final > 1e-6 else 0.0
    try:
        # [Fix 39] overlapping 2-day residuals carry induced MA(1)
        # autocorrelation that makes the ADF p-value anti-conservative;
        # test every 2nd (non-overlapping) residual instead
        resid_adf = resid_final[::2] if two_day else resid_final
        adf_p = adfuller(resid_adf, maxlag=min(20, len(resid_adf) // 5))[1]
    except Exception:
        adf_p = np.nan

    # [Fix 29] single-instrument alternatives chosen by realized hedging
    # power (|corr| with the target in the final window), not by rank_score
    corr_final = returns_final.corr()[target_ticker].drop(
        [target_ticker] + pf_legs, errors='ignore')        # [Fix 46] no self/legs
    best_single = corr_final.abs().idxmax()
    etf_cands = [c for c in corr_final.index if c.split(' ')[0] in ETF_SHORT_SET]
    best_etf = (corr_final[etf_cands].abs().idxmax()
                if etf_cands else best_single)   # [Fix 14]
    reg_s, r2_single, _ = _fit_basket(returns_final, target_ticker, [best_single])
    reg_e, r2_etf, _ = _fit_basket(returns_final, target_ticker, [best_etf])

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

    BASKET_HEADERS = ['ACTION', 'AMOUNT', 'INSTRUMENT', 'FULL TICKER', 'FORCED']

    # ── [Fix 65/70/71/72] PRECOMPUTE OOS EVIDENCE ────────────────────────────
    # Used by the trade ticket, the charts and sections [1]/[1b]/[1c] below.
    # Computed once, up here, so the ticket and the diagnostics can never
    # disagree about the same number.
    (sel_r2m, sel_r2s, sel_vrm, sel_n,
     sel_detail, sel_pooled, sel_y, sel_res) = _config_outer_oos(
        best_lookback, best_pc_spec, best_bsize, detail=True)   # [Fix 65]
    n_eff = max(4, int(outer_window / (2 if two_day else 1)))
    wdisp = _window_dispersion_stats(sel_detail, sel_pooled, n_eff)
    boot = None
    if boot_n and sel_y is not None and len(sel_y):             # [Fix 70]
        boot = _block_bootstrap_ci(sel_y, sel_res, n_boot=int(boot_n),
                                   block=(8 if two_day else None),
                                   ann=ann_sqrt)

    # ── [Fix 71] ROLLING OOS CURVE ───────────────────────────────────────────
    # Three outer windows are three noisy readings. This walks the SELECTED
    # config forward: refit weights every `rolling_refit_every` rows on data
    # available at that point, score the NEXT segment out-of-sample, and
    # concatenate the daily OOS residuals into one series — stability becomes
    # a curve you can see instead of three scalars. The CONFIG was chosen on
    # full data, so the row-(3) selection caveat from [1] applies here too;
    # the WEIGHTS, however, never see their scoring segment.
    rolling_df = pd.DataFrame()
    roll_stats = {}
    if rolling_oos:
        _step = max(5, int(rolling_refit_every))
        _segs_y, _segs_r, _segs_ix, _n_skip = [], [], [], 0
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
            _test_r = rets.iloc[_s:_e]
            _need = _bkt_r + [target_ticker]
            if not all(c in _test_r.columns and _test_r[c].notna().all()
                       for c in _need):
                _n_skip += 1
                continue
            _y_sr = _test_r[target_ticker].values
            _segs_y.append(_y_sr)
            _segs_r.append(_y_sr - _reg_r.predict(_test_r[_bkt_r].values))
            _segs_ix.append(_test_r.index)
        if _segs_y:
            rolling_df = pd.DataFrame(
                {'y': np.concatenate(_segs_y),
                 'resid': np.concatenate(_segs_r)},
                index=pd.DatetimeIndex(
                    np.concatenate([ix.values for ix in _segs_ix])))
            _w_roll = 21
            _sse_r = rolling_df['resid'].pow(2).rolling(_w_roll).sum()
            _sst_r = rolling_df['y'].rolling(_w_roll).var(ddof=0) * _w_roll
            rolling_df['r2_roll'] = 1.0 - _sse_r / _sst_r.where(_sst_r > 1e-12)
            rolling_df['te_roll'] = (rolling_df['resid']
                                     .rolling(_w_roll).std() * ann_sqrt)
            _te_f = rolling_df['te_roll'].dropna()
            _r2_f = rolling_df['r2_roll'].dropna()
            if len(_te_f):
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
                                  if len(_r2_f) else np.nan)}

    # ── [Fix 72] TICKET INPUTS + VERDICT ─────────────────────────────────────
    # quality = the most honest pooled OOS figure available: nested pooled
    # ([Fix 69], selection re-run before each window) first, then the
    # selected config's pooled ([Fix 65], mild selection bias), then the
    # nested mean as a last resort.
    if not np.isnan(nested_pooled):
        _quality, _quality_src = nested_pooled, 'nested pooled — honest'
    elif sel_n and not np.isnan(sel_pooled):
        _quality, _quality_src = sel_pooled, 'selected-config pooled'
    elif not np.isnan(nested_r2_mean):
        _quality, _quality_src = nested_r2_mean, 'nested mean'
    else:
        _quality, _quality_src = np.nan, 'n/a'
    _ref_pca_t = sel_r2m if sel_n else nested_r2_mean
    _simple_pool = [x for x in (etf_r2_mean, name_r2_mean)
                    if not np.isnan(x)]
    _ref_simple_t = max(_simple_pool) if _simple_pool else np.nan
    _overfit_gap = ((r2_final - _quality)
                    if not np.isnan(_quality) else np.nan)
    kill_te = (1.5 * wdisp['worst_te']
               if np.isfinite(wdisp['worst_te']) else np.nan)
    _roll_breach = bool(roll_stats and np.isfinite(kill_te)
                        and roll_stats['te_latest'] > kill_te)
    grade, reasons = _ticket_verdict(
        _quality, wdisp['worst_r2'], _overfit_gap, wdisp['min_sim'],
        wdisp['trend'], _ref_pca_t, _ref_simple_t, _roll_breach)
    ticket_info = {'grade': grade, 'reasons': reasons,
                   'quality_r2': _quality, 'quality_source': _quality_src,
                   'worst_window_r2': wdisp['worst_r2'],
                   'worst_window_te': wdisp['worst_te'],
                   'kill_switch_te': kill_te,
                   'overfit_gap': _overfit_gap}

    # ── STEP 6: CHARTS ───────────────────────────────────────────────────────
    if show_plots:
        fig, axes = plt.subplots(2, 3, figsize=(18, 10))
        ev = pca_f.explained_variance_ratio_
        axes[0, 0].bar(range(1, n_pc_final + 1), ev * 100, color='steelblue', alpha=0.7)
        axes[0, 0].plot(range(1, n_pc_final + 1), np.cumsum(ev) * 100, 'ro-')
        axes[0, 0].set_title(f'Scree ({n_pc_final} PCs, {np.sum(ev)*100:.0f}% var)')
        axes[0, 0].set_xlabel('PC')
        # [Fix 62] label only what matters. Annotating every name is
        # unreadable past ~100 candidates: the target, the basket and the 30
        # best-ranked candidates carry all the information anyone reads this
        # panel for; the rest stay as unlabelled dots.
        lab = set(basket_final) | {target_ticker} | set(final_rank.index[:30])
        for tk in loadings_f.index:
            c = ('red' if tk == target_ticker
                 else ('green' if tk in basket_final else 'steelblue'))
            s = 120 if tk == target_ticker else 40
            axes[0, 1].scatter(loadings_f.loc[tk, 'PC1'],
                               loadings_f.loc[tk, 'PC2'], c=c, s=s)
            if tk in lab:
                axes[0, 1].annotate(disp[tk],
                                    (loadings_f.loc[tk, 'PC1'],
                                     loadings_f.loc[tk, 'PC2']), fontsize=6)
        axes[0, 1].set_title('PC1 vs PC2'); axes[0, 1].set_xlabel('PC1'); axes[0, 1].set_ylabel('PC2')
        corrs = returns_final.corr()[target_ticker].drop(target_ticker).sort_values(ascending=False).head(10)
        colors = ['green' if t in basket_final else 'steelblue' for t in corrs.index]
        axes[0, 2].barh(range(len(corrs)), corrs.values, color=colors)
        axes[0, 2].set_yticks(range(len(corrs)))
        axes[0, 2].set_yticklabels([disp[t] for t in corrs.index], fontsize=7)
        axes[0, 2].set_title(f'Top Correlations with {target_short}')
        spread = pd.Series(resid_final, index=returns_final.index)
        # [Fix 15] true cumulative % = expm1(cumulative log return)
        axes[1, 0].plot(np.expm1(returns_final[target_ticker].cumsum()) * 100, 'r-', label='Unhedged')
        axes[1, 0].plot(np.expm1(spread.cumsum()) * 100, 'g-', label='Hedged')
        axes[1, 0].axhline(0, color='grey', ls='--', alpha=0.5)
        axes[1, 0].legend(); axes[1, 0].set_title('Cumulative Return %')
        w = 20
        axes[1, 1].plot(returns_final[target_ticker].rolling(w).std() * ann_sqrt * 100, 'r-', label='Unhedged')
        axes[1, 1].plot(spread.rolling(w).std() * ann_sqrt * 100, 'g-', label='Hedged')
        axes[1, 1].legend(); axes[1, 1].set_title(f'Rolling {w}-obs Annualized Vol %')
        for lb in summary['lookback'].unique():
            sub = summary[summary['lookback'] == lb].groupby('basket_size')['avg_r2_oos'].mean()
            axes[1, 2].plot(sub.index, sub.values, 'o-', label=f'{int(lb)}d')
        axes[1, 2].set_xlabel('Basket Size'); axes[1, 2].set_ylabel('OOS R²')
        axes[1, 2].legend(); axes[1, 2].set_title('Sensitivity')
        plt.tight_layout(); plt.show()
        # [Fix 71] rolling OOS curve — TE panel with the kill-switch line,
        # R² panel with the pooled level
        if len(rolling_df) and rolling_df['te_roll'].notna().any():
            fig2, ax2 = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
            ax2[0].plot(rolling_df.index, rolling_df['te_roll'] * 100, 'g-')
            if np.isfinite(wdisp['worst_te']):
                ax2[0].axhline(wdisp['worst_te'] * 100, color='orange',
                               ls='--', label='worst validated window')
                ax2[0].axhline(1.5 * wdisp['worst_te'] * 100, color='red',
                               ls='--', label='kill-switch (1.5×)')
                ax2[0].legend(fontsize=8)
            ax2[0].set_title('Rolling 21-row OOS tracking error (%/yr)')
            ax2[1].plot(rolling_df.index,
                        rolling_df['r2_roll'].clip(-0.5, 1.0), 'b-')
            if not np.isnan(sel_pooled):
                ax2[1].axhline(sel_pooled, color='grey', ls='--',
                               label='pooled OOS R²')
                ax2[1].legend(fontsize=8)
            ax2[1].set_title('Rolling 21-row OOS R² (clipped at −0.5)')
            plt.tight_layout(); plt.show()

    # ── STEP 7: READABLE REPORT ──────────────────────────────────────────────
    L = 78
    def hr(c='─'): print(c * L)
    def title(t): print(f"\n{'='*L}\n{t}\n{'='*L}")

    title(f"PCA HEDGE FINDER — {target_short}   ({datetime.now():%Y-%m-%d %H:%M})")
    print(f"Universe: {len(universe)} candidates | return frequency: "
          f"{'2-day overlapping (cross-tz corrected)' if two_day else 'daily'} "
          f"| Ridge alpha: CV-selected")
    if forced:                                              # [Fix 40]
        print(f"Force-included in every basket: "
              f"{', '.join(disp.get(c, c) for c in forced)} (★)")

    # ── [Fix 72] SECTION [0]: TRADE TICKET ───────────────────────────────────
    # Everything a trader needs on one screen, computed from the most honest
    # numbers available. The sections below are the evidence trail.
    title(f"[0] TRADE TICKET — {target_short}")
    print(f"  VERDICT: {grade}")
    for _rsn in reasons[:4]:
        print(f"    · {_rsn}")
    if not np.isnan(ticket_info['quality_r2']):
        print(f"  Quality: pooled OOS R² {ticket_info['quality_r2']:.2f} "
              f"({ticket_info['quality_source']})"
              + (f" | worst window {wdisp['worst_r2']:.2f}"
                 if not np.isnan(wdisp['worst_r2']) else "")
              + (f" | 95% CI [{boot['r2_lo']:.2f}, {boot['r2_hi']:.2f}]"
                 if boot else ""))
    _t_head = ['ACTION', 'AMOUNT/$100', 'INSTRUMENT', 'FULL TICKER']
    if notional_mm:
        _t_head.insert(2, '≈$MM')
    _t_rows = []
    for _tk, _wgt in weights_final.sort_values(
            key=lambda s: -s.abs()).items():
        _row = ['SHORT' if _wgt > 0 else 'LONG',
                '$' + format(abs(_wgt) * 100, '.1f'),
                disp.get(_tk, _tk.split(' ')[0]), _tk]
        if notional_mm:
            _row.insert(2, '$' + format(abs(_wgt) * notional_mm, ',.2f'))
        _t_rows.append(_row)
    print(f"  EXECUTE — per $100 of "
          f"{'gross book' if is_portfolio else 'long ' + target_short}"
          + (f" ($MM column: for ${notional_mm:g}mm gross)"
             if notional_mm else "") + ":")
    _print_table(_t_head, _t_rows)
    _te_bp = te_final * 1e4 / np.sqrt(252)
    _net = weights_final.sum() * 100
    print(f"  Gross ${weights_final.abs().sum()*100:.1f} | net "
          f"{'short' if _net >= 0 else 'long'} ${abs(_net):.1f} | "
          f"est. TE {te_final*100:.1f}%/yr "
          f"≈ {_te_bp:.0f}bp/day (in-sample, final window)")
    if np.isfinite(wdisp['worst_te']):
        print(f"  SIZING : budget risk off the WORST validated window — "
              f"hedged vol {wdisp['worst_te']*100:.1f}%/yr "
              f"(vs {tgt_std_final*100:.1f}%/yr unhedged)")
    if np.isfinite(kill_te):
        print(f"  MONITOR: refit or cut if rolling 21d TE exceeds "
              f"{kill_te*100:.1f}%/yr (1.5× worst validated window)"
              + (f" — latest: {roll_stats['te_latest']*100:.1f}%/yr"
                 if roll_stats else ""))
    print("  Evidence: [1] reliability | [1b] window dispersion | "
          "[1c] rolling OOS | [3] vs simple hedges")

    title("[1] HOW RELIABLE IS THIS HEDGE?  (higher = better)")
    print("  (what the four R² numbers mean → appendix [A] at the bottom "
          "of this report)")                                  # [Fix 52/72]
    hr()
    print(f"  Full-data CV mean OOS R² : {best['avg_r2_oos']:6.3f}  "
          f"(± {best['std_r2_oos']:.3f}, {int(best['n_folds'])} folds)")
    print(f"  Full-data CV vol red     : {best['avg_vol_red']*100:5.1f}%")
    # [Fix 30/72] sel_* precomputed above, before the ticket and charts
    if sel_n:
        print(f"  ★ THIS config, unseen OOS: {sel_r2m:6.3f} ± {sel_r2s:.3f}  "
              f"over {sel_n} windows × {outer_window}d | vol red={sel_vrm*100:.1f}%")
    if not np.isnan(nested_r2_mean):
        print(f"  Pipeline nested OOS R²   : {nested_r2_mean:6.3f} ± {nested_r2_std:.3f}  "
              f"(selection re-run before each window)")
    if not np.isnan(nested_pooled):                            # [Fix 69]
        print(f"  Nested POOLED OOS R²     : {nested_pooled:6.3f}  "
              f"(all nested windows as ONE sample — the headline)")
    # verdict compares the selected config's in-sample vs ITS OWN unseen OOS
    ref_oos = sel_r2m if sel_n else nested_r2_mean
    if not np.isnan(ref_oos):
        gap = r2_final - ref_oos
        verdict = ('✓ generalizes well' if gap < 0.15 else
                   '△ some overfitting — use with caution' if gap < 0.35 else
                   '✗ clearly overfit — do not use as-is')
        print(f"  In-sample R² {r2_final:.3f} vs unseen {ref_oos:.3f} → {verdict}")
    # [Fix 30] consistency check: what did the pipeline pick before each
    # unseen window? If it consistently chose something else, say so.
    if len(nested_valid):
        picks = nested_valid.apply(
            lambda r: f"lb={int(r['lookback'])}, pc={r['pc_spec']}, "
                      f"size={int(r['basket_size'])}", axis=1)
        modal = picks.mode().iloc[0]
        live = f"lb={best_lookback}, pc={best_pc_spec}, size={best_bsize}"
        if modal != live:
            n_modal = int((picks == modal).sum())
            print(f"  ⚠ NOTE: in {n_modal}/{len(picks)} unseen windows the pipeline "
                  f"selected [{modal}],")
            print(f"    not the live selection [{live}] — consider the top-5 "
                  f"section before trading.")
    hr()
    print(f"  Selected params: lookback={best_lookback}d | PCs={best_pc_spec}"
          f"{'' if best_pc_spec != 'auto' else f' (final={n_pc_final})'} "
          f"| basket={best_bsize}")

    # ── [Fix 65/70/72] SECTION [1b]: WINDOW DISPERSION ──────────────────────
    # With the default 3 windows, a mean ± std like "0.63 ± 0.15" over
    # readings of 0.45 / 0.64 / 0.81 hides everything that matters. This
    # section separates the four explanations (sampling noise / vol regime /
    # basket turnover / genuine deterioration) instead of averaging over
    # them. All statistics come from _window_dispersion_stats — the same
    # numbers the ticket used. Raise outer_folds (e.g. 6 windows of 21d) for
    # a finer read, and see [1c] for the rolling-curve view.
    if sel_n >= 2 and len(sel_detail):
        title("[1b] WINDOW DISPERSION — why the OOS windows disagree")
        band = wdisp['band']
        w_rows = []
        for _wi, (_, r) in enumerate(sel_detail.iterrows()):
            w_rows.append([f"{int(r['window'])} "
                           f"({'most recent' if r['window'] == 1 else 'older'})",
                           f"{r['start']:%Y-%m-%d}→{r['end']:%m-%d}",
                           format(r['r2'], '.3f'),
                           format(r['vol_red'] * 100, '.1f') + '%',
                           format(r['tgt_vol'] * 100, '.1f') + '%',
                           wdisp['flags'][_wi]])
        _print_table(['WINDOW', 'DATES', 'OOS R²', 'VOL RED',
                      'TGT VOL (ann)', 'VS NOISE BAND'], w_rows)
        print(f"  Pooled OOS R² (all windows as one sample): "
              f"{sel_pooled:.3f}  |  worst window: "
              f"{wdisp['worst_r2']:.3f}")
        if boot is not None:                                   # [Fix 70]
            print(f"  95% CI (circular block bootstrap, block={boot['block']}, "
                  f"B={boot['n_boot']}): pooled R² "
                  f"[{boot['r2_lo']:.2f}, {boot['r2_hi']:.2f}] | "
                  f"TE [{boot['te_lo']*100:.1f}%, {boot['te_hi']*100:.1f}%]/yr")
            print("  (the CI conditions on the fitted weights — refit noise "
                  "sits on top of it)")
        if band is not None:
            print(f"  A STABLE hedge with this pooled R² would scatter "
                  f"per-window readings inside")
            print(f"  ~[{band[0]:.2f}, {band[1]:.2f}] on {n_eff}-obs windows "
                  f"from sampling noise alone.")
            _below = [str(int(r['window'])) for _wi, (_, r)
                      in enumerate(sel_detail.iterrows())
                      if wdisp['flags'][_wi] == 'BELOW band']
            if not _below:
                print("  ► All windows sit inside (or above) the band — the "
                      "spread is consistent with")
                print("    noise on short windows, NOT with an unstable "
                      "hedge. Trust the pooled number.")
            else:
                print(f"  ► Window(s) {', '.join(_below)} fall BELOW the "
                      f"noise band — the shortfall is not")
                print("    explained by window length. Check the regime and "
                      "stability notes below.")
        # volatility-regime attribution: R² mechanically falls in windows
        # where the target's idiosyncratic variance dominates. If low-R²
        # windows are also low-vol windows, the RELATIONSHIP may be fine —
        # judge those windows by tracking error, not R².
        if np.isfinite(wdisp['reg_corr']) and wdisp['reg_corr'] > 0.5:
            print(f"  Regime note: window R² tracks window target vol "
                  f"(corr {wdisp['reg_corr']:+.2f}) — the weak")
            print("  windows are LOW-VOL windows, where idiosyncratic "
                  "noise dominates and R² is")
            print("  mechanically depressed. The hedge ratios may be "
                  "fine; watch TE instead.")
        # weight stability: are the windows disagreeing because the FITTED
        # HEDGE ITSELF changed?
        if wdisp['min_sim'] is not None:
            _stab = ('stable' if wdisp['min_sim'] > 0.8 else
                     'drifting' if wdisp['min_sim'] > 0.5 else 'UNSTABLE')
            print(f"  Weight stability across windows: min pairwise "
                  f"cosine {wdisp['min_sim']:+.2f} → {_stab}.")
            if wdisp['min_sim'] <= 0.5:
                print("  The windows are scoring materially DIFFERENT "
                      "hedges — dispersion here is")
                print("  basket turnover, not sampling noise. Prefer a "
                      "longer lookback, a smaller")
                print("  basket, or force_include to pin the anchor "
                      "names.")
        if wdisp['trend']:
            print("  ⚠ TREND: R² deteriorates toward the MOST RECENT "
                  "window. Do not average this")
            print("    away — the newest reading is the best estimate "
                  "of the hedge you would run")
            print("    today. Consider a shorter lookback or re-check "
                  "after the next refit.")
        print("  Sizing guidance: budget risk off the WORST window, not "
              "the mean — if realized")
        print("  rolling TE later exceeds ~1.5× the level that window "
              "implies, the hedge has")
        print("  left its validated regime: refit, or cut.")

    # ── [Fix 71] SECTION [1c]: ROLLING OOS CURVE ────────────────────────────
    if roll_stats:
        title(f"[1c] ROLLING OOS CURVE — selected config, weights refit "
              f"every {max(5, int(rolling_refit_every))} rows")
        print(f"  {roll_stats['n_days']} OOS rows over "
              f"{roll_stats['n_segments']} segments"
              + (f" ({roll_stats['n_skipped']} skipped)"
                 if roll_stats['n_skipped'] else "")
              + f", {rolling_df.index[0]:%Y-%m-%d} → "
                f"{rolling_df.index[-1]:%Y-%m-%d}")
        print(f"  Rolling 21-row TE : median {roll_stats['te_median']*100:.1f}%"
              f" | worst {roll_stats['te_worst']*100:.1f}%"
              f" | latest {roll_stats['te_latest']*100:.1f}%  (/yr)")
        print(f"  Rolling 21-row R² : median {roll_stats['r2_median']:.2f}"
              f" | worst {roll_stats['r2_worst']:.2f}"
              f" | latest {roll_stats['r2_latest']:.2f}")
        if np.isfinite(kill_te):
            print(f"  Kill-switch {kill_te*100:.1f}%/yr — "
                  + ("⚠ LATEST TE IS ABOVE IT: do not add risk on this hedge"
                     if _roll_breach else "latest TE is inside it ✓"))
        print("  (TE is the regime-robust metric — R² sags mechanically in "
              "calm tape; see [1b])")
    elif rolling_oos:
        print("\n  ([Fix 71] rolling OOS curve skipped — not enough history "
              "for any refit segment)")

    title(f"[2] HEDGE RECIPE — per $100 long {target_short}, execute:")
    # [Fix 41] boxed table instead of raw columns — values unchanged
    _print_table(BASKET_HEADERS, _basket_rows(weights_final))
    if forced:
        print("  ★ = force-included by user [Fix 40]")
    gross = weights_final.abs().sum() * 100
    net = weights_final.sum() * 100
    print(f"  Gross exposure: ${gross:.1f} | net short exposure: ${net:.1f}")
    print(f"  Hedged metrics: in-sample R²={r2_final:.3f} | "
          f"tracking error={te_final*100:.1f}%/yr | vol reduction={vol_red_final*100:.1f}%")
    adf_verdict = ('residual stationary ✓' if adf_p < 0.05 else
                   'residual may be non-stationary — hedge relationship could drift ⚠')
    print(f"  Residual ADF p-value={adf_p:.4f} ({adf_verdict})")

    # ── [Fix 57] PER-LEG DIAGNOSTICS FOR PORTFOLIO MODE ─────────────────────
    # [Fix 46] hedges the book as ONE synthetic asset, which is the correct
    # minimum-variance hedge of the NET book — but it means the report never
    # showed WHICH leg dominates what is left over. This table gives, per
    # leg: its book weight, its own annualized vol, its beta to the fitted
    # hedge basket, and its correlation with the hedged residual. A leg with
    # a large |CORR w/ RESID| is the one whose idiosyncratic risk survives
    # the hedge — the candidate to hedge separately, trim, or pair off.
    if is_portfolio:
        title("[2b] PER-LEG DIAGNOSTICS — what the NET-book hedge hides")
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
        _print_table(['LEG', 'BOOK W', 'ANN VOL', 'BETA vs HEDGE',
                      'CORR w/ RESID'], leg_rows)
        print("  The basket hedges the NET book: offsetting exposures cancel "
              "BEFORE hedging,")
        print("  and each leg's idiosyncratic risk is unhedged by "
              "construction. For a near-")
        print("  market-neutral book (net ~ 0) judge the hedge by VOL "
              "REDUCTION, not R² —")
        print("  a low-vol spread target makes R² look poor even when the "
              "hedge is fine.")

    # ── [Fix 54] SECTION [3]: one like-for-like comparison table ────────────
    # Previously this section printed IN-SAMPLE single-name and single-ETF R²
    # right next to the basket's out-of-sample numbers. Worse, the instrument
    # was chosen by |corr| on the SAME window it was then scored on — a
    # double bias the basket could not lose against. All four rows below are
    # now scored on the SAME unseen outer windows. The in-sample betas are
    # still shown, because they are the numbers you actually size the trade
    # with, but they are explicitly labelled as indicative and NOT comparable.
    title("[3] BASKET vs SIMPLE HEDGES — all scored on the SAME "
          f"{len(outer_windows)} unseen windows")
    print(f"  Indicative sizing (IN-SAMPLE, final {best_lookback}d window — "
          f"not comparable with the OOS table below):")
    print(f"    best single name {disp[best_single]:<12} "
          f"β={reg_s.coef_[0]:+.3f}  R²={r2_single:.3f}")
    print(f"    best ETF         {disp[best_etf]:<12} "
          f"β={reg_e.coef_[0]:+.3f}  R²={r2_etf:.3f}")
    etf_dir = 'short' if reg_e.coef_[0] > 0 else 'long'
    print(f"    → per $100 of {target_short}, {etf_dir} "
          f"${abs(reg_e.coef_[0])*100:.0f} of {disp[best_etf]} is the "
          f"simplest hedge")
    cmp_rows = []
    if sel_n:
        cmp_rows.append(['PCA basket — this recipe',
                         format(sel_r2m, '.3f') + ' ± ' + format(sel_r2s, '.3f'),
                         format(sel_vrm * 100, '.1f') + '%', str(sel_n)])
    if not np.isnan(nested_r2_mean):
        cmp_rows.append(['PCA pipeline — nested (selection re-run)',
                         format(nested_r2_mean, '.3f') + ' ± '
                         + format(nested_r2_std, '.3f'),
                         format(nested_vr_mean * 100, '.1f') + '%',
                         str(len(nested_valid))])
    if len(etf_bench):
        picks = '/'.join(sorted({e.split(' ')[0]
                                 for e in etf_bench['instrument']}))
        cmp_rows.append(['Best single ETF  [' + picks + ']',
                         format(etf_r2_mean, '.3f'),
                         format(etf_vr_mean * 100, '.1f') + '%',
                         str(len(etf_bench))])
    if len(name_bench):
        picks = '/'.join(sorted({e.split(' ')[0]
                                 for e in name_bench['instrument']}))
        cmp_rows.append(['Best single name [' + picks + ']',
                         format(name_r2_mean, '.3f'),
                         format(name_vr_mean * 100, '.1f') + '%',
                         str(len(name_bench))])
    _print_table(['HEDGE', 'OOS R²', 'OOS VOL RED', 'WINDOWS'], cmp_rows)
    ref_pca = sel_r2m if sel_n else nested_r2_mean
    ref_simple = np.nanmax([etf_r2_mean, name_r2_mean])
    if not (np.isnan(ref_pca) or np.isnan(ref_simple)):
        if ref_simple >= ref_pca:
            print("  ► RECOMMENDATION: a single-instrument hedge is at least "
                  "as robust as the")
            print("    PCA basket out-of-sample — prefer the simple hedge "
                  "until the basket")
            print("    demonstrably adds value.")
        else:
            print("  ► RECOMMENDATION: the PCA basket beats every single-"
                  "instrument hedge on")
            print("    the same unseen windows — the basket adds value here.")

    # ── [Fix 43/47] FACTOR-EXPOSURE LEAKAGE ─────────────────────────────────
    _stock_cols = [c for c in returns_final.columns
                   if c != target_ticker and c not in set(pf_legs)
                   and c.split(' ')[0] not in ETF_SHORT_SET]      # [Fix 47]
    _caps_map = {c: _cap_asof(c, returns_final.index[-1]) for c in _stock_cols}
    fl = _factor_leakage(returns_final, target_ticker, weights_final,
                         caps_map=_caps_map, stock_cols=_stock_cols)
    title("[3b] FACTOR EXPOSURE — what the hedge leaves behind")
    if fl is None:
        print("  (universe too small to build factor-mimicking portfolios — "
              "need\n   ~6+ non-ETF names; add candidates to run this diagnostic)")
    else:
        _print_table(['FACTOR', 'TARGET β', 'RESID β'],
                     [[r['factor'],
                       format(r['target_beta'], '+.3f'),
                       format(r['residual_beta'], '+.3f')]
                      for _, r in fl.iterrows()])
        _lo = fl.loc[fl['residual_beta'].abs().idxmax()]
        print(f"  Largest residual tilt: {_lo['factor']} "
              f"(β={_lo['residual_beta']:+.3f}). Residual β near 0 ⇒ the hedge "
              f"neutralized\n   that factor; near the target β ⇒ it did not. "
              f"MKT/SMB/WML/VOL are built\n   from the universe itself (works with zero "
              f"factor ETFs, e.g. ASX names).\n   [Fix 50] Factors are "
              f"sequentially orthogonalized: each β is the exposure\n   NOT "
              f"already explained by the factors listed above it.")

    # ── [Fix 16/20] TOP 5 BASKETS — FULL DETAIL + multi-window OOS ──────────
    title("[4] TOP 5 BASKETS — FULL DETAIL (ranked by full-data CV composite)")
    top5 = summary.sort_values('composite', ascending=False).head(5)
    for i, (_, cfg) in enumerate(top5.iterrows(), 1):
        lb = int(cfg['lookback'])
        ps = cfg['pc_spec']
        bs = int(cfg['basket_size'])
        selected = (lb == best_lookback and ps == best_pc_spec and bs == best_bsize)
        tag = '  ◄ SELECTED' if selected else ''
        print(f"\n  #{i}  lookback={lb}d | PCs={ps} | basket_size={bs}{tag}")
        print(f"      CV OOS R²={cfg['avg_r2_oos']:.3f} ±{cfg['std_r2_oos']:.3f} | "
              f"CV vol red={cfg['avg_vol_red']*100:.1f}% | "
              f"CV gross={cfg['avg_gross']*100:.0f} | "
              f"composite={cfg['composite']:.3f}")
        # per-config multi-window unbiased estimate [Fix 20/30]
        c_r2m, c_r2s, c_vrm, c_n = _config_outer_oos(lb, ps, bs)
        if c_n:
            print(f"      Unseen-window OOS R²={c_r2m:.3f} ±{c_r2s:.3f} | "
                  f"vol red={c_vrm*100:.1f}%  ({c_n} windows × {outer_window}d)")
        try:
            (_, _, bkt, reg_i, r2_i, resid_i, _, _, _) = _select_and_fit(
                rets.iloc[-lb:], ps, bs)
            te_i = np.std(resid_i) * ann_sqrt
            w_i = pd.Series(reg_i.coef_, index=bkt)
            print(f"      In-sample R²={r2_i:.3f} | TE={te_i*100:.1f}%/yr | "
                  f"gross=${w_i.abs().sum()*100:.1f} | net=${w_i.sum()*100:.1f}")
            print(f"      Weights (per $100 of {target_short}):")
            # [Fix 41] same table layout as the main recipe
            _print_table(BASKET_HEADERS, _basket_rows(w_i), indent='      ')
        except RuntimeError as e:
            print(f"      ⚠ refit failed: {e}")

    title("[A] APPENDIX — how to read the four R-squared numbers")  # [Fix 72]
    print(R2_GLOSSARY)                                        # [Fix 52]

    print(f"\n{'─'*L}")
    print("⚠ Caveats: the universe is built from TODAY's index membership and")
    print("  peers (survivorship bias — historical CV metrics may be optimistic).")
    print("  Weights are statistical hedge ratios; borrow costs and slippage are")
    print("  not included — adjust before trading.")
    if pit_active:                                          # [Fix 44]
        print("  Size filtering is point-in-time (as-of each window); the")
        print("  survivorship note above still applies to INDEX MEMBERSHIP —")
        print("  delisted names are absent from the discovered pool.")
    else:
        print("  Size filter used TODAY's caps (no historical caps available) —")
        print("  names small then but large now can leak in (size look-ahead).")
    if pm_active:                                           # [Fix 49]
        print("  Index membership is point-in-time: past members (incl. delisted")
        print("  names) were added and windows only see names that were members")
        print("  at the time — the survivorship note above is now largely fixed")
        print("  for INDEX-sourced candidates. Peer/industry lists remain as-of-")
        print("  today (Bloomberg has no clean history for those).")
    if is_portfolio:                                        # [Fix 46]
        print("  Portfolio mode: the book is hedged as ONE synthetic asset, so")
        print("  offsetting exposures across legs net out — the basket hedges the")
        print("  NET book, not each leg. Legs are excluded from the candidate pool.")
    if forced:                                              # [Fix 40]
        print("  Force-included names are held by construction, not because the")
        print("  model chose them — compare metrics with and without force_include")
        print("  to see what the constraint costs.")
    print('═' * L)

    return {
        'weights': weights_final, 'basket': basket_final,
        'ranking': final_rank, 'cv_summary': summary, 'cv_detail': cv_df,
        'nested_validation': nested,
        'nested_r2_mean': nested_r2_mean, 'nested_r2_std': nested_r2_std,
        'nested_vol_red_mean': nested_vr_mean,
        'selected_unseen_r2': sel_r2m, 'selected_unseen_r2_std': sel_r2s,
        'selected_unseen_pooled_r2': sel_pooled,       # [Fix 65]
        'outer_window_detail': sel_detail,             # [Fix 65]
        'nested_pooled_r2': nested_pooled,             # [Fix 69]
        'bootstrap_ci': boot,                          # [Fix 70]
        'rolling_oos': rolling_df,                     # [Fix 71]
        'ticket': ticket_info,                         # [Fix 72]
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
                   'basket_size': best_bsize,
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
                   'boot_n': boot_n},                     # [Fix 70]
    }




# ── [Fix 63] FAST RE-HEDGE — for books that change daily ────────────────────
# An index-rebalance book churns as predictions update, and re-running the
# full grid plus nested validation for every intraday change is overkill: the
# expensive part is CONFIG SELECTION, and the config does not change from one
# day to the next. quick_rehedge pins the config that was already validated
# and refits the weights only — seconds, and zero Bloomberg calls. Re-run the
# full find_best_hedge weekly, or whenever the book changes materially.
def quick_rehedge(book, data, prev_result):
    """Refit hedge weights for an updated book using a previously VALIDATED
    config. `prev_result` is the dict returned by a full find_best_hedge run.

    Deliberately reduced validation (cv_n_folds=2, outer_folds=1, no plots):
    the OOS numbers it prints are a sanity check, not a fresh validation —
    the config's credentials come from the full run this inherits from.
    """
    p = prev_result['params']
    return find_best_hedge(
        book, data=data,
        lookback_options=(p['lookback'],),
        pc_options='auto' if p['pc_spec'] == 'auto' else [int(p['pc_spec'])],
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
        boot_n=p.get('boot_n', 2000),                  # [Fix 70]
        rolling_oos=False,                             # [Fix 71] fast path
        cv_n_folds=2, outer_folds=1, show_plots=False)


# =============================================================================
# CELL S: SHORT-WINDOW MODE — v77 add-on to pca_hedge_v75_full.py
# =============================================================================
# Paste this AFTER CELL 2 (the engine). CELL 1 and CELL 2 are untouched and
# find_best_hedge() behaves exactly as it did in v75.
#
# v77 vs v76: IN-SAMPLE ONLY, and windows end on an explicit date (28-Jul)
# rather than "today". The leave-one-out machinery is gone.
#
# WHY A SEPARATE ESTIMATOR AT ALL
# -------------------------------
# find_best_hedge() needs, at its default settings, 378+ return rows before its
# sufficiency check will let it start. July MTD has ~20. So these windows are
# not a harder version of the same job; they are a different job:
#
#   find_best_hedge()      "what is a durable hedge for this name?"    predictive
#   short_window_hedge()   "what has been moving with this name since
#                           the 13th, and how much of its variance does
#                           that explain?"                             descriptive
#
# WHAT IN-SAMPLE ONLY MEANS HERE
# ------------------------------
# Every number below is fitted and scored on the same rows. That is the correct
# tool for ATTRIBUTION — decomposing a window that has already happened — and
# the wrong tool for forecasting. The R-squared is not an estimate of how the
# basket will perform tomorrow; it is a statement about how much of GMD's
# realized July variance these names co-moved with. Both readings are useful.
# Only one of them is a hedge recommendation, and it isn't this one.
#
# Two guards remain, because dropping out-of-sample testing makes them load-
# bearing rather than optional:
#   * ADJUSTED R-squared is reported next to raw R-squared. Raw in-sample R2
#     rises mechanically with every leg added; on 13 rows a 5-leg basket can
#     hit 0.9 while explaining nothing. Adjusted R2 charges for parameters and
#     is the only column that can be compared ACROSS windows with different
#     leg counts.
#   * BASKET SIZE IS CAPPED BY OBSERVATION COUNT (4 rows per leg by default).
#     Without a hold-out to expose it, an oversized basket has nothing to stop
#     it. Raise obs_per_leg to be stricter; you cannot disable the cap.
#   * Tracking error uses ddof = k+1, so the residual spread is not flattered
#     by the parameters that were fitted to shrink it.
#
# READ SECTION [3]. Three nested windows exist so that agreement between them
# can be evidence and disagreement can be evidence. A name that survives all
# three start dates is telling you something an in-sample R-squared cannot.
# =============================================================================

from datetime import datetime   # numpy / pandas already imported in CELL 1


# ─────────────────────────────────────────────────────────────────────────────
# Window specification
# ─────────────────────────────────────────────────────────────────────────────
def _last_bday_before(ts):
    ts = pd.Timestamp(ts).normalize()
    return (ts - pd.tseries.offsets.BDay(1)).normalize()


def default_windows(end=None):
    """The three requested windows, all ending on `end` (default: the last
    business day before today).

      1. month-to-date  : 1st of `end`'s month → end
      2. from the 6th   : 6th  of `end`'s month → end
      3. from the 13th  : 13th of `end`'s month → end

    Returns [(label, start, end), ...]. Edit here to change the dates."""
    end = pd.Timestamp(end).normalize() if end is not None \
        else _last_bday_before(datetime.now())
    y, m = end.year, end.month
    return [
        (f"MTD (01-{end:%b} →)", pd.Timestamp(y, m, 1),  end),
        (f"from 06-{end:%b}",    pd.Timestamp(y, m, 6),  end),
        (f"from 13-{end:%b}",    pd.Timestamp(y, m, 13), end),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Data slicing — zero Bloomberg calls, reuses the CELL A download
# ─────────────────────────────────────────────────────────────────────────────
def slice_data(data, start, end, lead=1):
    """Return a COPY of the CELL A data dict restricted to [start, end].

    `lead` extra price rows are kept BEFORE `start` so the first return inside
    the window is a real return. Without it the 01-Jul close would have no
    30-Jun close to difference against and July MTD would silently begin on the
    2nd. Market-cap paths and membership snapshots are trimmed to `end`."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    px = data['prices']
    idx = px.index
    before = idx[idx < start]
    lead_from = before[-lead] if len(before) >= lead else (
        before[0] if len(before) else start)
    out = dict(data)
    out['prices'] = px.loc[(idx >= lead_from) & (idx <= end)].copy()
    mh = data.get('mktcap_hist')
    if isinstance(mh, pd.DataFrame) and not mh.empty:
        out['mktcap_hist'] = mh.loc[mh.index <= end].copy()
    pm = data.get('pit_members') or {}
    if pm:
        out['pit_members'] = {k: v for k, v in pm.items()
                              if pd.Timestamp(k) <= end}
    out['_window'] = (start, end)
    return out


def _adj_r2(r2, n, k):
    """Adjusted R-squared. Returns NaN when there are not enough residual
    degrees of freedom for the number to mean anything."""
    if n - k - 1 <= 0:
        return np.nan
    return 1.0 - (1.0 - r2) * (n - 1) / (n - k - 1)


# ─────────────────────────────────────────────────────────────────────────────
# The short-window estimator — IN SAMPLE
# ─────────────────────────────────────────────────────────────────────────────
def short_window_hedge(
    target, data, start, end,
    label=None,
    basket_size=None,          # None → auto from the observation count
    max_basket_size=5,
    obs_per_leg=4,             # DOF rule: n_obs >= obs_per_leg * k. Load-bearing
                               # now that nothing out-of-sample checks the fit.
    min_mktcap_usd_mm=1000,
    exclude=None,
    force_include=None,
    restrict_to_target_tz='auto',
    tz_tolerance_hours=3.0,
    winsorize_pct=0.0,         # OFF: with ~15 rows, clipping the 1%/99% tails
                               # clips most of the information there is
    robust_cov='ledoit',       # ON: p >> n here, shrinkage is not optional
    n_pc=None,                 # None → auto, capped at n_obs // 4
    max_zero_frac=0.34,        # drop candidates this often unchanged in-window
                               # (short-window analogue of the stale guard)
    allow_two_day=False,       # 2-day overlapping returns halve an already
                               # tiny sample; opt in explicitly
    notional_mm=None,
    verbose=True,
):
    """Fit a hedge basket for `target` on the rows in [start, end], in sample.

    Returns a dict with: label, start, end, n_obs, basket, weights, gross,
    r2_in, r2_adj, te_bp_day, te_ann, best_single, best_single_r2, returns.

    `weights` is a pd.Series indexed by full ticker, using the SAME sign
    convention as find_best_hedge's recipe: a POSITIVE weight means SHORT that
    many dollars per $100 long the target."""
    legs, pf_w, is_pf, pf_label = _coerce_targets(target)
    start = pd.Timestamp(start).normalize()
    end = pd.Timestamp(end).normalize()
    label = label or f"{start:%d-%b} → {end:%d-%b}"
    say = (lambda *a: print(*a)) if verbose else (lambda *a: None)

    d = slice_data(data, start, end)
    prices = d['prices'].copy()
    missing = [l for l in legs if l not in prices.columns]
    if missing:
        raise ValueError(f"legs {missing} are not in the downloaded data — "
                         f"re-run CELL A (optionally with force_include=)")

    target_keepset = set(legs)
    forced, fi_unres = _resolve_force_include(force_include, prices.columns,
                                              legs[0])
    if fi_unres:
        say(f"    ⚠ force_include {fi_unres} not in the download — ignored")

    kept, dropped_ex = _apply_exclusions(
        [c for c in prices.columns if c not in target_keepset], exclude)
    kept += [c for c in dropped_ex if c in forced]
    prices = prices[list(dict.fromkeys(list(target_keepset) + kept))]

    # ── size floor, applied AS-OF the window start (no current-cap look-ahead)
    caps = data.get('mktcap_usd_mm') or {}
    ch = data.get('mktcap_hist')
    ch = ch if isinstance(ch, pd.DataFrame) else pd.DataFrame()

    def cap_asof(c):
        if not ch.empty and c in ch.columns:
            s = ch[c]
            s = s[s.index <= start].dropna()
            if len(s):
                return float(s.iloc[-1])
        return caps.get(c)

    if min_mktcap_usd_mm:
        keep, n_drop = list(target_keepset), 0
        for c in prices.columns:
            if c in target_keepset or c in forced or c.split(' ')[0] in ETF_SHORT_SET:
                if c not in keep:
                    keep.append(c)
                continue
            mc = cap_asof(c)
            if mc is None or mc >= min_mktcap_usd_mm:
                keep.append(c)          # unknown cap → keep (fail-open)
            else:
                n_drop += 1
        if n_drop:
            say(f"    size floor {_fmt_mktcap(min_mktcap_usd_mm)} as-of "
                f"{start:%d-%b}: dropped {n_drop} names")
            prices = prices[list(dict.fromkeys(keep))]

    # ── timezone: same rule as the main engine ───────────────────────────────
    tgt_close = _close_utc_of(legs[0]) if not is_pf else (
        float(np.mean([_close_utc_of(c) or np.nan for c in legs])))
    others = [c for c in prices.columns if c not in target_keepset]
    if tgt_close is None or np.isnan(tgt_close):
        same_tz, do_restrict = [], False
    else:
        same_tz = [c for c in others
                   if _close_utc_of(c) is not None
                   and _close_gap_hours(_close_utc_of(c), tgt_close)
                   <= tz_tolerance_hours]
        do_restrict = (restrict_to_target_tz is True or
                       (restrict_to_target_tz == 'auto' and len(same_tz) >= 30))
    if do_restrict and len(same_tz) < len(others):
        keep_tz = same_tz + [c for c in list(forced) + legs if c not in same_tz]
        say(f"    timezone restriction: {len(others)} → {len(keep_tz)} "
            f"candidates within {tz_tolerance_hours:.0f}h of the target's close")
        prices = prices[list(dict.fromkeys(list(target_keepset) + keep_tz))]

    closes = [_close_utc_of(c) for c in prices.columns]
    known = sorted({c for c in closes if c is not None})
    max_gap = max((_close_gap_hours(a, b)
                   for i, a in enumerate(known) for b in known[i + 1:]),
                  default=0.0)
    two_day = (any(c is None for c in closes) or max_gap > tz_tolerance_hours)
    if two_day and not allow_two_day:
        say(f"    ⚠ universe is cross-timezone (max close gap {max_gap:.1f}h) "
            f"but the window is too short to spend half of it on 2-day "
            f"overlapping returns — staying on DAILY returns. Async bias is "
            f"NOT corrected; treat any cross-tz name in the basket with "
            f"suspicion, or pass restrict_to_target_tz=True.")
        two_day = False
    ann = np.sqrt(252 / (2 if two_day else 1))

    # ── returns, trimmed to the window ───────────────────────────────────────
    rets = np.log(prices / prices.shift(1))
    if is_pf:
        present = [c for c in legs if c in rets.columns]
        w = pd.Series([pf_w[c] for c in present], index=present)
        w = w / (w.abs().sum() or 1.0)
        rets[PORTFOLIO_COL] = rets[present].mul(w, axis=1).sum(axis=1,
                                                              skipna=False)
        tgt, target_short = PORTFOLIO_COL, pf_label
    else:
        tgt = legs[0]
        target_short = tgt.split(' ')[0]
    if two_day:
        rets = rets.rolling(2).sum()
    rets = rets.loc[rets.index >= start]

    # ── candidate screen ─────────────────────────────────────────────────────
    skipped, ok = {}, []
    for c in rets.columns:
        if c in target_keepset or c == tgt:
            continue
        s = rets[c]
        if s.isna().any():
            skipped['incomplete'] = skipped.get('incomplete', 0) + 1
        elif s.std() < 1e-8:
            skipped['flat'] = skipped.get('flat', 0) + 1
        elif (s.abs() < 1e-9).mean() > max_zero_frac:
            skipped['illiquid'] = skipped.get('illiquid', 0) + 1
        else:
            ok.append(c)
    if tgt not in rets.columns or rets[tgt].isna().any():
        raise ValueError(f"{target_short} has missing prices inside {label} "
                         f"— cannot fit this window")
    rets = rets[[tgt] + ok].dropna()
    n_obs = len(rets)

    # ── degrees of freedom ───────────────────────────────────────────────────
    k_cap = max(1, min(max_basket_size, n_obs // obs_per_leg))
    k = int(basket_size or k_cap)
    if k > k_cap:
        say(f"    ⚠ basket_size={k} requested but {n_obs} observations only "
            f"support {k_cap} legs at {obs_per_leg} obs/leg — using {k_cap}")
        k = k_cap
    f_ok = [c for c in forced if c in ok]
    if len(f_ok) > k:
        say(f"    ⚠ {len(f_ok)} force_include names exceed the {k}-leg budget "
            f"— basket grows to hold them")
        k = len(f_ok)
    if n_obs < 8:
        say(f"    ⚠ {n_obs} observations — below any threshold at which a "
            f"fitted hedge means anything. Reported for completeness only.")

    say(f"    {n_obs} return rows × {len(ok)} candidates → {k}-leg basket"
        + (f"   (skipped: " + ", ".join(f"{v} {kk}" for kk, v in skipped.items())
           + ")" if skipped else ""))

    # ── selection + fit ──────────────────────────────────────────────────────
    npc_cap = max(1, min(n_obs // 4, 5))

    def select(tr):
        cols = [c for c in tr.columns if c != PORTFOLIO_COL]
        trw = _winsorize_returns(tr[cols], winsorize_pct)
        sd = trw.std().replace(0, 1.0)
        tr_sc = (trw - trw.mean()) / sd
        cap = max(1, min(len(cols) - 1, npc_cap))
        npc = int(min(n_pc or npc_cap, cap))
        pca = _pca_fit(tr_sc, npc, robust_cov)
        lds = pd.DataFrame(
            pca.components_.T * np.sqrt(np.clip(pca.explained_variance_, 0, None)),
            index=cols, columns=[f'PC{i+1}' for i in range(npc)])
        if is_pf:
            lin = [c for c in legs if c in lds.index]
            wv = np.array([pf_w[c] for c in lin], dtype=float)
            wv = wv / (np.abs(wv).sum() or 1.0)
            lds.loc[PORTFOLIO_COL] = (lds.loc[lin].values * wv[:, None]).sum(0)
        pool = [c for c in tr.columns if c != tgt and c not in target_keepset]
        rank = _rank_scores(lds, tr, tgt, pool)
        rest = [t for t in rank.index if t not in f_ok]
        return f_ok + rest[:max(0, k - len(f_ok))]

    basket = select(rets)
    if not basket:
        raise ValueError(f"no usable candidates inside {label}")
    reg, r2_in, resid = _fit_basket(rets, tgt, basket)
    kk = len(basket)
    weights = pd.Series(reg.coef_, index=basket)      # +ve = SHORT
    gross = float(weights.abs().sum())
    r2_adj = _adj_r2(float(r2_in), n_obs, kk)

    # residual spread charged for the parameters fitted to shrink it
    dof = max(1, n_obs - kk - 1)
    te_day = float(np.sqrt(np.sum(resid ** 2) / dof))

    # ── best single instrument over the same window, same footing ────────────
    pool_single = [c for c in ok if c.split(' ')[0] in ETF_SHORT_SET] or ok
    corrs = {c: abs(rets[tgt].corr(rets[c])) for c in pool_single}
    corrs = {c: v for c, v in corrs.items() if not np.isnan(v)}
    best_single, bs_r2, bs_adj, bs_beta = None, np.nan, np.nan, np.nan
    if corrs:
        best_single = max(corrs, key=corrs.get)
        reg_s, bs_r2, _ = _fit_basket(rets, tgt, [best_single])
        bs_r2 = float(bs_r2)
        bs_adj = _adj_r2(bs_r2, n_obs, 1)
        bs_beta = float(reg_s.coef_[0])

    return {
        'label': label, 'start': start, 'end': end,
        'target': target_short, 'target_col': tgt,
        'n_obs': n_obs, 'n_candidates': len(ok),
        'basket': basket, 'weights': weights, 'gross': gross,
        'r2_in': float(r2_in), 'r2_adj': r2_adj,
        'te_bp_day': te_day * 1e4, 'te_ann': te_day * ann,
        'tgt_vol_ann': float(np.std(rets[tgt].values, ddof=1) * ann),
        'best_single': best_single, 'best_single_r2': bs_r2,
        'best_single_r2_adj': bs_adj, 'best_single_beta': bs_beta,
        'corr_best_single': corrs.get(best_single, np.nan) if corrs else np.nan,
        'notional_mm': notional_mm, 'two_day': two_day,
        'returns': rets, 'reg': reg, 'skipped': skipped,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Runner: three windows + the stability comparison
# ─────────────────────────────────────────────────────────────────────────────
def run_short_windows(target, data, windows=None, end=None, verbose=True, **kw):
    """Run short_window_hedge over several nested windows and print the
    per-window recipes plus the cross-window stability report.

    windows : list of (label, start, end). Defaults to month-to-date /
              from-the-6th / from-the-13th, all ending on `end`.
    end     : common end date for the default windows (e.g. '2026-07-28').
    **kw    : passed to short_window_hedge (min_mktcap_usd_mm, force_include,
              exclude, basket_size, notional_mm, restrict_to_target_tz, ...).

    Returns {'runs', 'stability', 'summary', 'core', 'errors'}."""
    windows = windows or default_windows(end)
    L = 82
    runs, errs = [], []
    print("=" * L)
    print(f"SHORT-WINDOW HEDGE (IN SAMPLE) — {_coerce_targets(target)[3]}"
          f"   ·   {len(windows)} nested windows")
    print("=" * L)
    for lab, s, e in windows:
        print(f"\n  ▸ {lab}   [{pd.Timestamp(s):%Y-%m-%d} → "
              f"{pd.Timestamp(e):%Y-%m-%d}]")
        try:
            runs.append(short_window_hedge(target, data, s, e, label=lab,
                                           verbose=verbose, **kw))
        except Exception as ex:
            print(f"    ✗ skipped: {ex}")
            errs.append((lab, str(ex)))
    if not runs:
        print("\nNo window produced a fit — nothing to compare.")
        return {'runs': [], 'stability': pd.DataFrame(),
                'summary': pd.DataFrame(), 'core': [], 'errors': errs}

    notional = next((r['notional_mm'] for r in runs if r['notional_mm']), None)

    # ── [1] per-window recipes ───────────────────────────────────────────────
    print("\n" + "=" * L)
    print("[1] RECIPE BY WINDOW   (SHORT $x per $100 long the target)")
    print("=" * L)
    for r in runs:
        print(f"\n  {r['label']}  —  {r['n_obs']} obs, {len(r['basket'])} legs, "
              f"gross ${r['gross'] * 100:.0f} per $100")
        rows = []
        for tk, w in r['weights'].sort_values(key=abs, ascending=False).items():
            cell = [tk.split(' ')[0], 'SHORT' if w > 0 else 'LONG ',
                    f"${abs(w) * 100:6.1f}"]
            if notional:
                cell.append(f"${abs(w) * notional:6.2f}mm")
            rows.append(cell)
        hdr = ['Ticker', 'Side', 'per $100'] + (
            [f'per ${notional:.0f}mm'] if notional else [])
        _print_table(hdr, rows, indent='    ')

    # ── [2] in-sample fit ────────────────────────────────────────────────────
    print("\n" + "=" * L)
    print("[2] IN-SAMPLE FIT   (compare windows on ADJ R2, never on raw R2)")
    print("=" * L)
    srows = []
    for r in runs:
        srows.append([
            r['label'], f"{r['n_obs']}", f"{len(r['basket'])}",
            f"{r['r2_in']:.2f}",
            "n/a" if np.isnan(r['r2_adj']) else f"{r['r2_adj']:+.2f}",
            f"{r['te_bp_day']:.0f}",
            f"{r['tgt_vol_ann'] * 100:.0f}%",
            r['best_single'].split(' ')[0] if r['best_single'] else '—',
            "n/a" if np.isnan(r['best_single_r2']) else f"{r['best_single_r2']:.2f}",
        ])
    _print_table(['Window', 'Obs', 'Legs', 'R2', 'Adj R2', 'TE bp/d',
                  'Tgt vol', 'Best single', 'its R2'], srows, indent='  ')
    print("\n  R2      fitted and scored on the SAME rows. Rises mechanically")
    print("          with every leg added and with every row removed, so it is")
    print("          NOT comparable across these windows.")
    print("  Adj R2  charges for the parameters. This is the comparable column,")
    print("          and it can go negative — meaning the basket explains less")
    print("          than the window mean once its legs are paid for.")
    print("  TE      residual sd at ddof = k+1, so the fitted legs do not")
    print("          flatter it. Still an in-sample floor on live tracking error.")
    print("  Best single = most correlated single instrument, fitted the same")
    print("          way. If the basket's Adj R2 does not clear it, the basket")
    print("          is not earning its extra legs.")

    # ── [3] STABILITY — the reason for running three windows ─────────────────
    print("\n" + "=" * L)
    print("[3] STABILITY ACROSS WINDOWS   ← the load-bearing section")
    print("=" * L)
    allw = pd.DataFrame({r['label']: r['weights'] for r in runs}).fillna(0.0)
    allw = allw.reindex(allw.abs().max(axis=1).sort_values(ascending=False).index)
    n_win = len(runs)
    strows = []
    for tk, row in allw.iterrows():
        nz = row[row != 0]
        signs = {np.sign(v) for v in nz}
        strows.append([tk.split(' ')[0], f"{len(nz)}/{n_win}"]
                      + [("—" if v == 0 else f"{v * 100:+.0f}") for v in row]
                      + [f"{nz.mean() * 100:+.0f}",
                         "yes" if len(signs) == 1 else "FLIPS"])
    _print_table(['Ticker', 'In'] + [r['label'] for r in runs]
                 + ['Mean', 'Same side'], strows, indent='  ')

    core = [tk for tk, row in allw.iterrows()
            if (row != 0).sum() == n_win
            and len({np.sign(v) for v in row if v != 0}) == 1]
    churn = [tk for tk, row in allw.iterrows() if (row != 0).sum() == 1]
    print(f"\n  Persistent core (in all {n_win} windows, same side): "
          + (", ".join(t.split(' ')[0] for t in core) if core else "NONE"))
    if churn:
        print(f"  Appears in one window only: "
              f"{', '.join(t.split(' ')[0] for t in churn)}")
    if not core:
        print("  → No name survives all three start dates. The basket is being")
        print("    driven by which days happen to be in the sample. With no")
        print("    out-of-sample test in this build, section [3] is the ONLY")
        print("    check standing between you and a curve-fit — heed it.")
    else:
        worst = float((allw.loc[core].std(axis=1) * 100).max())
        print(f"  → Core weight dispersion across windows: max {worst:.0f} "
              f"per $100"
              + ("  (tight — the ratio is holding)" if worst < 15 else
                 "  (wide — the NAMES persist but the RATIO does not)"))

    # ── [3b] pin the persistent core in every window ─────────────────────────
    if core:
        print("\n  [3b] PERSISTENT CORE PINNED IN EVERY WINDOW")
        crows = []
        for r in runs:
            rr, tcol = r['returns'], r['target_col']
            usable = [c for c in core if c in rr.columns]
            if not usable:
                continue
            try:
                reg_c, r2c, _ = _fit_basket(rr, tcol, usable)
            except Exception:
                continue
            wc = pd.Series(reg_c.coef_, index=usable)
            crows.append([
                r['label'],
                " / ".join(f"{t.split(' ')[0]} {w * 100:+.0f}"
                           for t, w in wc.items()),
                f"{float(r2c):.2f}",
                (lambda a: "n/a" if np.isnan(a) else f"{a:+.2f}")(
                    _adj_r2(float(r2c), r['n_obs'], len(usable))),
                "n/a" if np.isnan(r['r2_adj']) else f"{r['r2_adj']:+.2f}"])
        if crows:
            _print_table(['Window', 'Core recipe per $100', 'R2',
                          'core Adj R2', 'free-pick Adj R2'], crows, indent='  ')
            print("  The core carries fewer legs, so if its Adj R2 is close to")
            print("  the free pick's, the extra legs were bought with degrees of")
            print("  freedom rather than explanatory power.")

    summary = pd.DataFrame([{
        'window': r['label'], 'obs': r['n_obs'], 'legs': len(r['basket']),
        'r2_in': r['r2_in'], 'r2_adj': r['r2_adj'],
        'te_bp_day': r['te_bp_day'], 'gross': r['gross'],
        'best_single': r['best_single'], 'best_single_r2': r['best_single_r2'],
    } for r in runs]).set_index('window')

    # ── [4] scope ────────────────────────────────────────────────────────────
    print("\n" + "=" * L)
    print("[4] SCOPE OF THESE NUMBERS")
    print("=" * L)
    nmax = max(r['n_obs'] for r in runs)
    print(f"  Largest window here is {nmax} observations, fitted and scored on")
    print(f"  itself. find_best_hedge() wants 378+ rows and reports a NESTED")
    print(f"  out-of-sample R2 over three unseen 42-day windows. Nothing on")
    print(f"  this page is that number, and no number here forecasts anything.")
    print()
    print("  This answers: how much of the target's realized variance over")
    print("  these dates moved with these names — an attribution question.")
    print()
    print("  It does not answer: what will hedge the position tomorrow. For")
    print("  that, run find_best_hedge() on the 3-year download and use these")
    print("  windows to ask whether its basket still appears in section [3].")
    print("  A long-run basket that survives all three July start dates is a")
    print("  much stronger result than any single in-sample R2 above.")
    if errs:
        print(f"\n  Windows that failed: {', '.join(l for l, _ in errs)}")
    return {'runs': runs, 'stability': allw, 'summary': summary,
            'core': core, 'errors': errs}


# =============================================================================
# CELL 3: RUN — GMD AU Equity, three nested July windows, in sample
# =============================================================================
# --- CELL A: download ONCE (the only cell that hits Bloomberg) ---------------
# UNCHANGED from v75. Keep years=3 even though the windows are three weeks
# long: the 3-year pull is what funds universe discovery, the market-cap paths
# and the point-in-time membership snapshots. CELL S slices this object in
# memory and never calls Bloomberg.
data = download_hedge_data('GMD AU Equity', min_mktcap_usd_mm=1000)


# --- CELL B: the three windows — rerun freely, zero API calls ---------------
# 1. July MTD  01-Jul → 28-Jul
# 2.           06-Jul → 28-Jul
# 3.           13-Jul → 28-Jul
short = run_short_windows(
    'GMD AU Equity', data,
    end='2026-07-28',              # common end date for all three windows.
                                   # Omit it and they end on the last business
                                   # day before today instead.
    min_mktcap_usd_mm=1000,        # state it explicitly, as in v75 CELL B
    restrict_to_target_tz='auto',  # 'auto' should fire for an ASX target;
                                   # True forces it — worth comparing
    tz_tolerance_hours=3.0,
    notional_mm=None,              # e.g. 10 → adds a "per $10mm" column
    # basket_size=3,               # leave None: auto-capped by observation
    #                              # count, which is the point (see obs_per_leg)
    # obs_per_leg=4,               # raise to 5-6 to be stricter about legs
    # force_include=['STW AU'],    # e.g. pin the ASX 200 ETF into every basket
    # exclude=['NST'],             # names you cannot borrow / do not want
)
# What you get back:
#   short['runs']       per-window dicts (weights, returns, r2_in, r2_adj, ...)
#   short['stability']  the weight-by-window DataFrame printed in section [3]
#   short['summary']    one row per window
#   short['core']       names present in EVERY window on the SAME side

# --- Custom windows ---------------------------------------------------------
# short = run_short_windows('GMD AU Equity', data, windows=[
#     ('pre-event',  '2026-06-15', '2026-07-05'),
#     ('post-event', '2026-07-06', '2026-07-28')],
#     min_mktcap_usd_mm=1000)

# --- One window on its own --------------------------------------------------
# r = short_window_hedge('GMD AU Equity', data, '2026-07-13', '2026-07-28',
#                        min_mktcap_usd_mm=1000)
# print(r['weights'], r['r2_in'], r['r2_adj'])

# --- RECOMMENDED PAIRING ----------------------------------------------------
# In-sample July numbers are only interpretable against a baseline. Run the
# full v75 pipeline on the same 3-year download, then ask whether its basket
# still appears in section [3] above. If it does, July has not broken the
# relationship. If it has vanished, that is the regime break — and a far
# stronger signal than any three-week in-sample R-squared.
# result = find_best_hedge(
#     'GMD AU Equity', data=data,
#     min_mktcap_usd_mm=1000,
#     restrict_to_target_tz='auto', tz_tolerance_hours=3.0,
#     gross_penalty=0.02, max_gross=None,
#     winsorize_pct=0.01, robust_cov='ledoit',
#     pit_size=True, pit_members=True, mask_stale_days=7,
#     notional_mm=None)
