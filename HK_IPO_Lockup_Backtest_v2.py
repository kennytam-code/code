"""HK IPO lock-up backtest. Copy this ENTIRE file into ONE Jupyter cell and run.

Requires an entitled Bloomberg Desktop API workstation with Bloomberg logged in.
Ticker/date inputs and primary-source review are embedded. No companion files.
Gross short price returns only. No assumed fees or borrow costs.
Prints date checks, strategy results, coverage and charts; exports Excel/CSV/HTML.
HKEX historical full lists mark exchange short-sale eligibility at T0 minus 21
HK sessions. Verified HKEX history is embedded; online refresh extends coverage.
Historical checks must all resolve to Yes/No before final export. No borrow availability is inferred.
The current Hong Kong daily bar is excluded. No substitute price provider.
Live Bloomberg transport/entitlements require verification on your workstation.
"""
from __future__ import annotations

# SETTINGS — defaults use your supplied workbook and Hong Kong trading sessions.
AS_OF = "2026-10-28"
DAY_BASIS = "sessions"           # One month = 21 HK trading sessions
T0_CONVENTION = "first_unlocked" # T0 = first unlocked HK trading session
EXTENDED_COMBINATIONS = False    # True adds pre-expiry entry to T+7 / T+21 exits
REFRESH_HKEX = False             # True refreshes dated files; verified embedded archive covers outages
REFRESH_BLOOMBERG = False        # True ignores the exact-request Bloomberg cache
SELECTED_TICKER = "3750 HK Equity"
WORKBOOK_PATH = None             # Optional path to an updated .xlsm; never executes macros
OUTPUT_ROOT = "lockup_backtest_results"

import sys, importlib.util, subprocess
_packages = {"pandas":"pandas>=2.2,<3", "numpy":"numpy>=1.26,<3",
             "matplotlib":"matplotlib>=3.8,<4", "openpyxl":"openpyxl>=3.1,<4"}
_missing = [spec for name,spec in _packages.items() if importlib.util.find_spec(name) is None]
if _missing:
    print("Installing missing packages in this Jupyter kernel:", _missing)
    subprocess.check_call([sys.executable, "-m", "pip", "install", *_missing])

from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import html
import json
import re
import time
import warnings
from datetime import datetime, date

import numpy as np
import pandas as pd

VERSION = "2.2.0"
PRICE_FIELDS = ("PX_OPEN", "PX_LAST", "PX_VOLUME")


@dataclass(frozen=True)
class Settings:
    asof: str = "2026-10-28"
    day_basis: str = "sessions"       # sessions or calendar
    anchor: str = "first_unlocked"    # last_locked or first_unlocked
    borrow_rate: float = 0.0           # No assumed costs in the requested price study
    fee_bps_per_leg: float = 0.0
    borrow_day_count: int = 365
    intraday_borrow_days: int = 1
    require_locate: bool = False       # True requires dated shortability + borrow evidence
    require_complete_30: bool = False
    bootstrap_draws: int = 2000
    random_seed: int = 20261028

    def __post_init__(self):
        cutoff=pd.Timestamp(self.asof)
        if pd.isna(cutoff) or cutoff.tzinfo is not None or cutoff != cutoff.normalize():
            raise ValueError("asof must be a valid date without a timezone or time component")
        if self.day_basis not in {"sessions", "calendar"}:
            raise ValueError("day_basis must be sessions or calendar")
        if self.anchor not in {"last_locked", "first_unlocked"}:
            raise ValueError("anchor must be last_locked or first_unlocked")
        for k in ("borrow_rate", "fee_bps_per_leg"):
            if not np.isfinite(getattr(self, k)) or getattr(self, k) < 0:
                raise ValueError(f"{k} must be finite and nonnegative")
        if self.borrow_day_count <= 0 or self.intraday_borrow_days < 0:
            raise ValueError("Invalid borrow day-count convention")
        if self.bootstrap_draws < 100:
            raise ValueError("Use at least 100 bootstrap draws")


@dataclass(frozen=True)
class Strategy:
    key: str
    entry_offset: int
    exit_offset: int
    entry_field: str = "PX_LAST"
    exit_field: str = "PX_LAST"

    @property
    def label(self):
        def leg(n, field):
            return f"T{n:+d}".replace("T+0", "T0") + (" open" if field == "PX_OPEN" else " close")
        return f"{leg(self.entry_offset, self.entry_field)} → {leg(self.exit_offset, self.exit_field)}"

    def label_for(self, basis):
        return self.label if basis == "sessions" else self.label.replace("T-21", "T−1m").replace("T+21", "T+1m")


def make_strategies(extended=False):
    """19 requested/core combinations, including the explicitly invalid zero hold.

    T-1 close to T-1 close is retained in the audit and is NOT a zero-return trade.
    extended=True additionally holds the seven pre-expiry entries to T+7/T+21.
    """
    ans = [Strategy(f"pre_{n}_{x}", -n, x)
           for n in (21, 14, 10, 7, 3, 2, 1) for x in (-1, 0)
           if not (n == 1 and x == -1)]
    ans += [Strategy("expiry_intraday", 0, 0, "PX_OPEN")]
    ans += [Strategy(f"post_close_{n}", 0, n) for n in (7, 21)]
    ans += [Strategy(f"post_open_{n}", 0, n, "PX_OPEN") for n in (7, 21)]
    if extended:
        ans += [Strategy(f"cross_{n}_{x}", -n, x)
                for n in (21, 14, 10, 7, 3, 2, 1) for x in (7, 21)]
    return ans


def normalize_ticker(value):
    m = re.fullmatch(r"\s*0*(\d{1,5})\s+HK\s+EQUITY\s*", str(value), re.I)
    if not m or not 0 < int(m[1]) < 100000:
        raise ValueError(f"Not an explicit Hong Kong equity ticker: {value!r}")
    return f"{int(m[1])} HK Equity"


def parse_dates(value):
    """This workbook uses US m/d/yyyy. No locale inference or day/month guessing."""
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return [pd.Timestamp(value).normalize()]
    if value is None or not str(value).strip():
        raise ValueError("Missing expiry")
    parts = re.split(r"[,;\n]+", str(value))
    result = []
    for token in parts:
        token = token.strip()
        if not token:
            continue
        fmt = "%Y-%m-%d" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", token) else "%m/%d/%Y"
        result.append(pd.Timestamp(datetime.strptime(token, fmt)).normalize())
    if not result:
        raise ValueError("Missing expiry")
    return result


def read_workbook(path, sheet="Sheet1"):
    """Read cached cells only. No macros, formulas or workbook instructions execute."""
    import openpyxl
    rows, issues = [], []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True, keep_links=False)
        try:
            if sheet not in wb.sheetnames:
                raise ValueError(f"Missing sheet {sheet!r}")
            ws = wb[sheet]
            header = list(next(ws.iter_rows(min_row=1, max_row=1, max_col=3, values_only=True)))
            if header != ["Name", "Lock-Up / Quiet Info", "Ticker"]:
                raise ValueError(f"Unexpected input header: {header}")
            for row, (name, raw, ticker) in enumerate(ws.iter_rows(min_row=4, max_col=3, values_only=True), 4):
                if not ticker and not raw and not name:
                    continue
                try:
                    normalized = normalize_ticker(ticker)
                    days = parse_dates(raw)
                except (ValueError, TypeError) as exc:
                    issues.append(dict(source_row=row, raw_ticker=ticker, raw_dates=raw, reason=str(exc)))
                    continue
                for seq, d in enumerate(days, 1):
                    rows.append(dict(input_id=f"Sheet1:{row}:{seq}", source_row=row,
                                     name=str(name or ""), ticker=normalized,
                                     input_date=d.date().isoformat(), raw_dates=str(raw)))
        finally:
            wb.close()
    events = pd.DataFrame(rows, columns=["input_id", "source_row", "name", "ticker", "input_date", "raw_dates"])
    if events.empty:
        raise ValueError("No usable ticker/date rows")
    events["duplicate_input"] = events.duplicated(["ticker", "input_date"], keep="first")
    return events, pd.DataFrame(issues, columns=["source_row", "raw_ticker", "raw_dates", "reason"])


def true_mask(series):
    return series.astype(str).str.lower().isin(["true", "1", "yes"])


def select_events(inputs, review, settings):
    """Exact ticker + supplied-date join. Corrections require an explicit review row."""
    required = {"ticker", "input_date", "last_day_locked", "category", "confirmed",
                "amendment_blocked", "source_url", "publication_date", "review_note"}
    if not required <= set(review.columns):
        raise ValueError(f"Review missing columns: {sorted(required - set(review.columns))}")
    a, r = inputs.copy().reset_index(drop=True), review.copy().reset_index(drop=True)
    for frame in (a, r):
        frame["ticker"] = frame.ticker.map(normalize_ticker)
        frame["input_date"] = pd.to_datetime(frame.input_date, errors="raise").dt.strftime("%Y-%m-%d")
        if frame.input_date.isna().any():
            raise ValueError("Input and review keys must have nonmissing ticker/date values")
    if r.duplicated(["ticker", "input_date"]).any():
        raise ValueError("Ambiguous review: multiple decisions for the same ticker/date")
    audit = a.merge(r, on=["ticker", "input_date"], how="left", validate="many_to_one")
    # Stage 1 filter removed: admit all supplied historical events regardless of review/category/amendment status.
    # Fall back to input_date when last_day_locked is not filled in review.
    audit["last_day_locked"] = pd.to_datetime(audit.last_day_locked, errors="coerce").fillna(
        pd.to_datetime(audit.input_date, errors="coerce")
    )
    audit["publication_date"] = pd.to_datetime(audit.publication_date, errors="coerce").fillna(
        pd.Timestamp("1990-01-01")
    )
    audit["status"] = "Eligible date"
    future = audit.last_day_locked.ge(pd.Timestamp(settings.asof))
    audit.loc[future, "status"] = "Future or current-day restriction"
    duplicates = a.duplicated(["ticker", "input_date"], keep="first")
    audit.loc[duplicates, "status"] = "Duplicate input ticker/date"
    accepted = audit[audit.status.eq("Eligible date")].copy()
    accepted["event_id"] = accepted.ticker + "|" + accepted.last_day_locked.dt.strftime("%Y-%m-%d")
    duplicates = accepted.duplicated("event_id", keep="first")
    audit.loc[accepted.index[duplicates], "status"] = "Duplicate corrected event"
    accepted = accepted[~duplicates].copy()
    return audit, accepted


def validate_prices(prices):
    required = {"ticker", "date", *PRICE_FIELDS}
    if not required <= set(prices.columns):
        raise ValueError(f"Prices missing columns: {sorted(required - set(prices.columns))}")
    p = prices.copy()
    p["ticker"] = p.ticker.map(normalize_ticker)
    p["date"] = pd.to_datetime(p.date, errors="raise").dt.normalize()
    if p.date.isna().any() or p.duplicated(["ticker", "date"]).any():
        raise ValueError("Missing or duplicate ticker/date price keys")
    for field in PRICE_FIELDS:
        p[field] = pd.to_numeric(p[field], errors="raise")
        if np.isinf(p[field]).any():
            raise ValueError(f"Infinite {field}")
        if (p[field].dropna() < 0).any():
            raise ValueError(f"Negative {field}")
    # Zero and NaN prices stay missing. Repeated real closes are NOT presumed stale.
    for field in ("PX_OPEN", "PX_LAST"):
        p.loc[p[field].eq(0), field] = np.nan
    return p.sort_values(["ticker", "date"]).reset_index(drop=True)


def validate_sessions(sessions):
    days = pd.DatetimeIndex(pd.to_datetime(sessions, errors="raise")).normalize()
    if days.empty or days.hasnans or days.has_duplicates or not days.is_monotonic_increasing:
        raise ValueError("Sessions must be nonempty, unique and chronological")
    if (days.dayofweek > 4).any():
        raise ValueError("A weekend was included as an HK session")
    return days


def anchor_position(days, locked, convention):
    d = pd.Timestamp(locked).normalize()
    if d < days[0] or d > days[-1]:
        raise ValueError("Restriction outside session coverage")
    k = days.searchsorted(d, side="right")
    pos = k - 1 if convention == "last_locked" else k
    if not 0 <= pos < len(days):
        raise ValueError("No session for event anchor")
    return int(pos)


def offset_position(days, anchor, offset, basis):
    if basis == "sessions":
        pos = anchor + offset
    else:
        d = days[anchor]
        # In calendar mode only ±21 denotes a calendar month; other numbers are days.
        target = d + (pd.DateOffset(months=1 if offset > 0 else -1)
                      if abs(offset) == 21 else pd.Timedelta(days=offset))
        if target < days[0] or target > days[-1]:
            raise ValueError("Calendar target outside session coverage")
        pos = days.searchsorted(target, side="right") - 1  # previous actual HK session
    if not 0 <= pos < len(days):
        raise ValueError("Offset outside session coverage")
    return int(pos)


def _positive(value):
    return pd.notna(value) and np.isfinite(value) and value > 0


def backtest(events, prices, sessions, strategies=None, settings=None,
             benchmark=None, locates=None, dividends=None, dividend_coverage=None):
    """Every eligible event × strategy produces either a result or a specific skip.

    Prices must use consistent split/capital-change units, without cash-dividend
    adjustments. Dividend inputs, if supplied, must use those same per-share units.
    A daily locate row is evidence for ENTRY only; recalls and intra-hold changes
    are not modeled. This remains a fixed-share event study, not a portfolio.
    """
    cfg = settings or Settings()
    strategies = make_strategies() if strategies is None else list(strategies)
    if len({s.key for s in strategies}) != len(strategies):
        raise ValueError("Strategy keys must be unique")
    p = validate_prices(prices)
    days = validate_sessions(sessions)
    asof = pd.Timestamp(cfg.asof)
    days = days[days <= asof]
    if days.empty:
        raise ValueError("No sessions before the as-of date")
    groups = {t: g.set_index("date") for t, g in p.groupby("ticker")}
    b = None
    if benchmark is not None and not benchmark.empty:
        b = benchmark.copy()
        b["date"] = pd.to_datetime(b.date).dt.normalize()
        if b.date.duplicated().any():
            raise ValueError("Duplicate benchmark dates")
        b = b.set_index("date")
    l = None
    if locates is not None and not locates.empty:
        l = locates.copy()
        l["date"] = pd.to_datetime(l.date).dt.normalize()
        if l.duplicated(["ticker", "date"]).any():
            raise ValueError("Duplicate locate rows")
        l = l.set_index(["ticker", "date"])
    div = None
    if dividends is not None and not dividends.empty:
        div = dividends.copy()
        div["date"] = pd.to_datetime(div.date).dt.normalize()
        div["cash_per_adjusted_share"] = pd.to_numeric(div.cash_per_adjusted_share, errors="raise")
        if (div.cash_per_adjusted_share < 0).any() or not np.isfinite(div.cash_per_adjusted_share).all():
            raise ValueError("Invalid cash dividends")
    coverage = None
    if dividend_coverage is not None and not dividend_coverage.empty:
        coverage = dividend_coverage.copy()
        for col in ("start", "end"):
            coverage[col] = pd.to_datetime(coverage[col]).dt.normalize()
        if (coverage.start > coverage.end).any():
            raise ValueError("Reversed dividend coverage")
        if dividends is None:
            raise ValueError("Dividend coverage needs a dividend ledger, even if empty")
    results = []
    for e in events.itertuples(index=False):
        locked = pd.Timestamp(e.last_day_locked)
        publication = pd.Timestamp(e.publication_date)
        g = groups.get(e.ticker)
        event_problem, anchor = "", None
        try:
            if locked >= asof:
                raise ValueError("Future or current-day restriction")
            anchor = anchor_position(days, locked, cfg.anchor)
            # Admission always checks ±30 around last-locked anchor, independent of UI T0.
            reference = anchor_position(days, locked, "last_locked")
            if cfg.require_complete_30:
                if reference < 30 or reference + 30 >= len(days):
                    raise ValueError("Incomplete ±30-session study window")
                if g is None:
                    raise ValueError("No price history")
                ends = g.reindex([days[reference - 30], days[reference], days[reference + 30]])
                if not ends.PX_LAST.map(_positive).all() or not ends.PX_VOLUME.map(_positive).all():
                    raise ValueError("Missing or nontraded ±30-session endpoint")
        except ValueError as exc:
            event_problem = str(exc)
        for s in strategies:
            row = dict(event_id=e.event_id, ticker=e.ticker, name=e.name,
                       input_date=e.input_date, last_day_locked=locked,
                       t0=days[anchor] if anchor is not None else pd.NaT,
                       strategy=s.key, strategy_label=s.label_for(cfg.day_basis), entry_offset=s.entry_offset,
                       exit_offset=s.exit_offset, entry_field=s.entry_field, exit_field=s.exit_field,
                       status="Skipped", reason=event_problem, entry_date=pd.NaT, exit_date=pd.NaT,
                       entry_price=np.nan, exit_price=np.nan, gross_return=np.nan,
                       after_cost_price_return=np.nan, net_return=np.nan,
                       borrow_cost=np.nan, transaction_cost=np.nan, dividend_cost=np.nan,
                       benchmark_return=np.nan, short_plus_hsi_return=np.nan,
                       calendar_days=np.nan, sessions_held=np.nan, path_missing_sessions=np.nan,
                       worst_mark_return=np.nan, best_mark_return=np.nan,
                       borrow_rate_used=cfg.borrow_rate, locate_status="Not verified",
                       source_url=e.source_url)
            if event_problem:
                results.append(row)
                continue
            try:
                i = offset_position(days, anchor, s.entry_offset, cfg.day_basis)
                j = offset_position(days, anchor, s.exit_offset, cfg.day_basis)
                entry, end = days[i], days[j]
                row.update(entry_date=entry, exit_date=end)
                if j < i or (j == i and not (s.entry_field == "PX_OPEN" and s.exit_field == "PX_LAST")):
                    raise ValueError("No positive holding interval")
                if end > asof:
                    raise ValueError("Exit after as-of date")
                if g is None:
                    raise ValueError("No price history")
                if entry not in g.index or end not in g.index:
                    raise ValueError("Missing exact entry or exit session")
                a, z = g.loc[entry], g.loc[end]
                pa, pz = a[s.entry_field], z[s.exit_field]
                if not _positive(pa) or not _positive(pz):
                    raise ValueError("Missing exact entry or exit price")
                rate = cfg.borrow_rate
                if l is not None and (e.ticker, entry) in l.index:
                    locate = l.loc[(e.ticker, entry)]
                    known = (str(locate.shortable).lower() in {"true", "1", "yes"}
                             and str(locate.borrow_available).lower() in {"true", "1", "yes"})
                    row["locate_status"] = "Entry evidence available" if known else "Entry not shortable/borrowable"
                    if cfg.require_locate and not known:
                        raise ValueError("Entry not shortable/borrowable")
                    if known and pd.notna(locate.get("borrow_rate", np.nan)):
                        rate = float(locate.borrow_rate)
                        if not np.isfinite(rate) or rate < 0:
                            raise ValueError("Invalid event borrow rate")
                elif cfg.require_locate:
                    raise ValueError("Missing dated entry shortability/borrow evidence")
                held = (end - entry).days
                days_charged = max(held, cfg.intraday_borrow_days)
                borrow = rate * days_charged / cfg.borrow_day_count
                # Fees are charged on both traded notionals, not twice initial notional.
                fee = cfg.fee_bps_per_leg / 10000 * (1 + pz / pa)
                gross = 1 - pz / pa
                path = g.reindex(days[i:j + 1])
                missing = int((~path.PX_LAST.map(_positive) | ~path.PX_VOLUME.map(_positive)).sum())
                marks = 1 - path.PX_LAST / pa
                worst = min(0.0, float(marks.min())) if missing == 0 else np.nan
                best = max(0.0, float(marks.max())) if missing == 0 else np.nan
                divcost, net = np.nan, np.nan
                covered = coverage is not None and ((coverage.ticker == e.ticker)
                           & (coverage.start <= entry) & (coverage.end >= end)).any()
                if covered:
                    # Ex-date entitlement attaches before the open: (entry, exit] for
                    # either open/close entry. A T0 open sale does not owe a T0 ex dividend.
                    amount = 0.0 if div is None else div.loc[(div.ticker == e.ticker)
                             & (div.date > entry) & (div.date <= end), "cash_per_adjusted_share"].sum()
                    divcost = float(amount / pa)
                    net = gross - fee - borrow - divcost
                benchret = np.nan
                if b is not None and entry in b.index and end in b.index:
                    ba, bz = b.loc[entry].get(s.entry_field), b.loc[end].get(s.exit_field)
                    if _positive(ba) and _positive(bz):
                        benchret = bz / ba - 1
                row.update(status="Completed", reason="", entry_price=float(pa), exit_price=float(pz),
                           gross_return=float(gross), after_cost_price_return=float(gross-fee-borrow),
                           borrow_cost=float(borrow), transaction_cost=float(fee), dividend_cost=divcost,
                           net_return=net, calendar_days=held, sessions_held=j-i,
                           path_missing_sessions=missing, worst_mark_return=worst, best_mark_return=best,
                           benchmark_return=benchret, short_plus_hsi_return=gross+benchret,
                           borrow_rate_used=rate)
            except ValueError as exc:
                row["reason"] = str(exc)
            results.append(row)
    return pd.DataFrame(results)


def summarize(trades, settings=None, common_sample=False):
    """Equal issuer weight: average repeated events within each issuer first.

    Confidence intervals resample issuer averages, not correlated event rows.
    They do not correct market-date dependence or multiple-strategy selection.
    """
    cfg = settings or Settings()
    if trades.empty:
        return pd.DataFrame()
    good = trades[trades.status.eq("Completed")].copy()
    if good.empty:
        return pd.DataFrame()
    # Exclude only structural zero-hold strategies from the common-cohort definition.
    meaningful = trades.loc[~((trades.entry_offset == trades.exit_offset)
                       & (trades.entry_field == trades.exit_field)), "strategy"].unique()
    if common_sample:
        counts = good.groupby("event_id").strategy.nunique()
        good = good[good.event_id.isin(counts[counts == len(meaningful)].index)]
    rng, out = np.random.default_rng(cfg.random_seed), []
    for key, g in good.groupby("strategy", sort=False):
        issuer = g.groupby("ticker").agg(gross=("gross_return", "mean"),
                                         after=("after_cost_price_return", "mean"),
                                         win=("gross_return", lambda x: (x > 0).mean()))
        x = issuer.gross.to_numpy()
        if len(x) >= 2:
            # Bounded loop avoids a potentially large bootstrap matrix.
            boot = np.array([rng.choice(x, len(x), replace=True).mean()
                             for _ in range(cfg.bootstrap_draws)])
            lo, hi = np.quantile(boot, [.025, .975])
        else:
            lo, hi = np.nan, np.nan
        out.append(dict(strategy=key, strategy_label=g.strategy_label.iloc[0],
                        events=len(g), issuers=len(issuer), mean_gross=float(x.mean()),
                        mean_after_cost_price=float(issuer.after.mean()),
                        median_issuer_gross=float(np.median(x)),
                        win_rate=float(issuer.win.mean()), ci_low=lo, ci_high=hi,
                        worst_event=float(g.gross_return.min()), best_event=float(g.gross_return.max()),
                        p05_event=float(g.gross_return.quantile(.05)),
                        average_calendar_days=float(g.calendar_days.mean()),
                        events_with_path_gaps=int(g.path_missing_sessions.gt(0).sum()),
                        sample="Common completed cohort" if common_sample else "Available per strategy"))
    return pd.DataFrame(out)


def sensitivity(trades, rates=(0, .05, .10, .20), fees=(0, 10, 25), settings=None):
    cfg = settings or Settings()
    if trades.empty:
        return pd.DataFrame()
    g = trades[trades.status.eq("Completed")].copy()
    out = []
    for rate in rates:
        for bps in fees:
            g["scenario_return"] = (g.gross_return - rate * g.calendar_days.clip(lower=cfg.intraday_borrow_days)
                                     / cfg.borrow_day_count - bps / 10000 * (1+g.exit_price/g.entry_price))
            for key, rows in g.groupby("strategy", sort=False):
                out.append(dict(strategy=key, borrow_rate=rate, fee_bps_per_leg=bps,
                                mean_after_cost_price=rows.groupby("ticker").scenario_return.mean().mean(),
                                issuers=rows.ticker.nunique(), events=len(rows)))
    return pd.DataFrame(out)


def event_paths(events, prices, sessions, settings=None, half_window=21):
    cfg = settings or Settings()
    days, p = validate_sessions(sessions), validate_prices(prices)
    groups = {t: g.set_index("date") for t, g in p.groupby("ticker")}
    records = []
    for e in events.itertuples(index=False):
        g = groups.get(e.ticker)
        if g is None:
            continue
        try:
            k = anchor_position(days, e.last_day_locked, cfg.anchor)
        except ValueError:
            continue
        if k < half_window:
            continue
        end_idx = min(len(days), k + half_window + 1)
        dates = days[k-half_window:end_idx]
        offsets = range(-half_window, end_idx - k)
        path = g.reindex(dates)
        base = path.PX_LAST.iloc[0]
        if not _positive(base):
            continue
        for offset, d, close in zip(offsets, dates, path.PX_LAST):
            value = 1-close/base if _positive(close) else np.nan
            records.append(dict(event_id=e.event_id, ticker=e.ticker, name=e.name,
                                last_day_locked=e.last_day_locked, offset=offset, date=d,
                                short_return_from_Tminus21=value))
    return pd.DataFrame(records)


def plot_results(summary, trades, paths, output_dir=None, settings=None):
    """Return four professional figures; save high-resolution PNGs when requested."""
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    cfg = settings or Settings()
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.edgecolor": "#c8c8c8", "axes.labelcolor": "#333333",
                         "figure.facecolor": "white", "axes.facecolor": "white"})
    figures = {}
    if summary.empty:
        return figures
    s = summary.iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(11, max(6, len(s)*.34)), layout="constrained")
    y = np.arange(len(s))
    ax.barh(y, s.mean_gross, height=.6, color=np.where(s.mean_gross >= 0, "#23745b", "#CB2125"))
    valid = s.ci_low.notna() & s.ci_high.notna()
    # Draw intervals by endpoints; no assumption that percentile CI straddles estimate.
    ax.hlines(y[valid], s.loc[valid, "ci_low"], s.loc[valid, "ci_high"], color="#333333", lw=1.2)
    ax.set_yticks(y, [f"{r.strategy_label}   (n={r.issuers})" for r in s.itertuples()])
    ax.axvline(0, color="#999999", lw=.7)
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.set_title("Short price returns by strategy", loc="left", fontweight="bold", pad=14)
    ax.set_xlabel("P&L / initial short notional · equal issuer weight · 95% issuer-bootstrap interval")
    ax.grid(axis="x", alpha=.15)
    figures["strategy_comparison"] = fig

    g = trades[trades.status.eq("Completed")]
    pre = g[(g.entry_offset < 0) & g.exit_offset.isin([-1, 0])]
    if not pre.empty:
        issuer = pre.groupby(["entry_offset", "exit_offset", "ticker"]).gross_return.mean().reset_index()
        grid = issuer.groupby(["entry_offset", "exit_offset"]).gross_return.mean().unstack().reindex([-21,-14,-10,-7,-3,-2,-1])
        counts = issuer.groupby(["entry_offset", "exit_offset"]).ticker.nunique().unstack().reindex(grid.index)
        fig, ax = plt.subplots(figsize=(7, 5), layout="constrained")
        vmax = max(.01, float(np.nanmax(np.abs(grid.to_numpy()))))
        im = ax.imshow(grid, cmap="RdYlGn", vmin=-vmax, vmax=vmax, aspect="auto")
        ax.set_yticks(range(len(grid)), ["T−1m close" if cfg.day_basis == "calendar" and n == -21 else f"T{n} close" for n in grid.index])
        ax.set_xticks(range(len(grid.columns)), [f"T{n:+d} close".replace("T+0", "T0") for n in grid.columns])
        for i in range(len(grid)):
            for j in range(len(grid.columns)):
                val = grid.iloc[i,j]
                label = f"{val:+.2%}\nn={int(counts.iloc[i,j])}" if pd.notna(val) else "No holding interval"
                ax.text(j, i, label, ha="center", va="center", fontsize=10, color="#202020")
        ax.set_title("Entry timing versus exit timing", loc="left", fontweight="bold", pad=14)
        ax.set_ylabel("Short entry")
        ax.set_xlabel("Cover · mean short price return, equal issuer weight")
        fig.colorbar(im, ax=ax, format=PercentFormatter(1), shrink=.75)
        figures["entry_exit_matrix"] = fig

    if not paths.empty:
        by_stock = paths.groupby(["offset", "ticker"]).short_return_from_Tminus21.mean().reset_index()
        curve = by_stock.groupby("offset").short_return_from_Tminus21.agg(["mean", "count"])
        fig, (ax, axn) = plt.subplots(2, 1, figsize=(10, 5.5), sharex=True,
                                     gridspec_kw={"height_ratios": [4,1]}, layout="constrained")
        ax.plot(curve.index, curve["mean"], color="#153954", lw=2, label="Selected average · one weight per issuer")
        ax.axvline(0, color="#CB2125", lw=1, linestyle="--", label="T0")
        ax.axhline(0, color="#aaaaaa", lw=.7)
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.set_ylabel("Short price P&L / initial notional")
        ax.set_title("Event study: enter at T−21 close", loc="left", fontweight="bold", pad=12)
        ax.legend(frameon=False, loc="best")
        ax.grid(alpha=.15)
        axn.bar(curve.index, curve["count"], color="#b5bbc2")
        axn.set_ylabel("Issuers")
        axn.set_xlabel("Hong Kong trading sessions from T0 · available observations at each offset")
        figures["event_study"] = fig

    selected = [key for key in summary.strategy if key in set(g.strategy)]
    if selected:
        fig, ax = plt.subplots(figsize=(11, 6), layout="constrained")
        values = [g.loc[g.strategy.eq(key), "gross_return"].to_numpy() for key in selected]
        import inspect
        orientation = {"orientation":"horizontal"} if "orientation" in inspect.signature(ax.boxplot).parameters else {"vert":False}
        ax.boxplot(values, **orientation, showfliers=True, flierprops={"markersize": 2, "alpha": .45})
        ax.set_yticks(range(1, len(selected)+1), [summary.set_index("strategy").loc[key,"strategy_label"] for key in selected])
        ax.axvline(0, color="#CB2125", lw=.8)
        ax.xaxis.set_major_formatter(PercentFormatter(1))
        ax.set_xlabel("Individual-event short price return · outliers retained")
        ax.set_title("Dispersion and adverse outcomes", loc="left", fontweight="bold", pad=12)
        figures["return_distribution"] = fig
    if output_dir:
        d = Path(output_dir)
        d.mkdir(parents=True, exist_ok=True)
        for name, fig in figures.items():
            fig.savefig(d / f"{name}.png", dpi=160, facecolor="white", bbox_inches="tight")
    return figures


def plot_stocks(paths, tickers, page=1):
    """Individual stock paths only, six event lines per page, complete legends."""
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    chosen = {normalize_ticker(t) for t in tickers}
    p = paths[paths.ticker.isin(chosen)]
    keys = list(p.event_id.unique())
    if not keys:
        raise ValueError("No observed paths for selected tickers")
    pages = (len(keys)+5)//6
    if not 1 <= page <= pages:
        raise ValueError(f"Choose page 1 to {pages}")
    fig, ax = plt.subplots(figsize=(10,6), layout="constrained")
    for event_id in keys[(page-1)*6:page*6]:
        g = p[p.event_id.eq(event_id)].sort_values("offset")
        r = g.iloc[0]
        label = f"{r.ticker} · {r['name']} · locked through {pd.Timestamp(r.last_day_locked):%d %b %Y}"
        ax.plot(g.offset, g.short_return_from_Tminus21, lw=1.7, label=label)
    ax.axvline(0, color="#999999", ls="--", lw=.8)
    ax.axhline(0, color="#bbbbbb", lw=.7)
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set(title=f"Selected stock events · page {page}/{pages}", xlabel="HK trading sessions from T0",
           ylabel="Short price return from T−21 close")
    ax.legend(loc="upper center", bbox_to_anchor=(.5,-.12), frameon=False, fontsize=9)
    return fig


class BloombergClient:
    """Synchronous Desktop API, one request at a time, bounded waits and disk cache.

    A running entitled Desktop API session is required. This is not a BQL client.
    No cache is used unless its exact request signature and data SHA256 match.
    """
    def __init__(self, cache_dir="cache/bloomberg", host="localhost", port=8194, timeout=60):
        self.cache_dir = Path(cache_dir)
        self.host, self.port, self.timeout = host, port, timeout
        self.session = None

    def __enter__(self):
        try:
            import blpapi
        except ImportError as exc:
            raise RuntimeError("blpapi is not installed in this Jupyter kernel. See setup instructions.") from exc
        self.api = blpapi
        options = blpapi.SessionOptions()
        options.setServerHost(self.host)
        options.setServerPort(self.port)
        options.setConnectTimeout(min(int(self.timeout*1000), 30000))
        self.session = blpapi.Session(options)
        if not self.session.start():
            self.session.stop()
            raise RuntimeError("Cannot start Bloomberg Desktop API. Log in on the entitled terminal workstation.")
        if not self.session.openService("//blp/refdata"):
            self.session.stop()
            raise RuntimeError("Cannot open //blp/refdata. Check API entitlements.")
        self.service = self.session.getService("//blp/refdata")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, *args):
        if self.session:
            self.session.stop()

    @staticmethod
    def parse_message(msg, fields):
        """Parse security-level historical responses without converting errors to zero."""
        if msg.hasElement("responseError"):
            raise RuntimeError("Bloomberg responseError: " + str(msg.getElement("responseError")))
        if not msg.hasElement("securityData"):
            return [], []
        sec = msg.getElement("securityData")
        security = sec.getElementAsString("security")
        errors, rows = [], []
        if sec.hasElement("securityError"):
            return [], [dict(ticker=security, field="*", error=str(sec.getElement("securityError")))]
        if sec.hasElement("fieldExceptions"):
            ex = sec.getElement("fieldExceptions")
            for i in range(ex.numValues()):
                item = ex.getValueAsElement(i)
                errors.append(dict(ticker=security, field=item.getElementAsString("fieldId"),
                                   error=str(item.getElement("errorInfo"))))
        if sec.hasElement("fieldData"):
            data = sec.getElement("fieldData")
            for i in range(data.numValues()):
                item = data.getValueAsElement(i)
                row = dict(ticker=security, date=pd.Timestamp(item.getElementAsDatetime("date")).date().isoformat())
                for field in fields:
                    row[field] = (item.getElementAsFloat(field)
                                  if item.hasElement(field) and not item.getElement(field).isNull() else np.nan)
                rows.append(row)
        return rows, errors

    def history(self, tickers, start, end, fields=PRICE_FIELDS, refresh=False):
        if not self.session:
            raise RuntimeError("Use BloombergClient inside a with block")
        securities = sorted(set(tickers))
        if not securities or len(securities) > 20:
            raise ValueError("Request between 1 and 20 securities at a time")
        start, end = pd.Timestamp(start).strftime("%Y%m%d"), pd.Timestamp(end).strftime("%Y%m%d")
        params = dict(periodicitySelection="DAILY", periodicityAdjustment="ACTUAL",
                      nonTradingDayFillOption="ACTIVE_DAYS_ONLY", nonTradingDayFillMethod="NIL_VALUE",
                      adjustmentFollowDPDF=False, adjustmentSplit=True,
                      adjustmentNormal=False, adjustmentAbnormal=False)
        signature = dict(version=VERSION, securities=securities, fields=list(fields), start=start, end=end, options=params)
        key = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
        csv, meta = self.cache_dir / (key+".csv"), self.cache_dir / (key+".json")
        if not refresh and csv.exists() and meta.exists():
            info = json.loads(meta.read_text())
            if info.get("request") != signature or info.get("sha256") != hashlib.sha256(csv.read_bytes()).hexdigest():
                raise ValueError("Bloomberg cache metadata/hash mismatch")
            return pd.read_csv(csv), pd.DataFrame(info["errors"])
        req = self.service.createRequest("HistoricalDataRequest")
        for ticker in securities:
            req.getElement("securities").appendValue(ticker)
        for field in fields:
            req.getElement("fields").appendValue(field)
        req.set("startDate", start)
        req.set("endDate", end)
        for k, v in params.items():
            req.set(k, v)
        queue = self.api.EventQueue()
        cid = self.session.sendRequest(req, eventQueue=queue)
        deadline, records, errors = time.monotonic()+self.timeout, [], []
        while True:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                self.session.cancel(cid)
                raise TimeoutError("Bloomberg history timed out; incomplete response not cached")
            event = queue.nextEvent(min(1000, max(1, int(remaining*1000))))
            kind = event.eventType()
            if kind == self.api.Event.REQUEST_STATUS:
                for msg in event:
                    if str(msg.messageType()) == "RequestFailure":
                        raise RuntimeError("Bloomberg RequestFailure: "+str(msg))
            if kind in (self.api.Event.PARTIAL_RESPONSE, self.api.Event.RESPONSE):
                for msg in event:
                    rr, ee = self.parse_message(msg, fields)
                    records.extend(rr)
                    errors.extend(ee)
                if kind == self.api.Event.RESPONSE:
                    break
        frame = pd.DataFrame(records, columns=["ticker", "date", *fields])
        represented = set(frame.ticker) | {e['ticker'] for e in errors}
        errors.extend(dict(ticker=t, field="*", error="No rows returned in requested historical interval")
                      for t in securities if t not in represented)
        if not frame.empty and frame.duplicated(["ticker", "date"]).any():
            raise ValueError("Bloomberg returned duplicate security/date records")
        frame.to_csv(csv, index=False)
        meta.write_text(json.dumps(dict(request=signature, errors=errors,
                             downloaded_utc=pd.Timestamp.now(tz="UTC").isoformat(),
                             sha256=hashlib.sha256(csv.read_bytes()).hexdigest()), indent=2))
        return frame, pd.DataFrame(errors)


def completed_history_cutoff(asof, now=None):
    """Never request the current HK daily bar, even if a terminal returns a live last."""
    stamp=pd.Timestamp.now(tz="Asia/Hong_Kong") if now is None else pd.Timestamp(now)
    stamp=stamp.tz_localize("Asia/Hong_Kong") if stamp.tzinfo is None else stamp.tz_convert("Asia/Hong_Kong")
    previous_day=stamp.normalize().tz_localize(None)-pd.Timedelta(days=1)
    return min(pd.Timestamp(asof).normalize(),previous_day)


def download_bloomberg(events, settings, cache_dir, refresh=False):
    """Pull only reviewed historic events; one security/window at a time.

    HSI actual daily observations supply the common session calendar. Missing HSI
    data are not silently replaced by generic Monday–Friday business days.
    """
    if events.empty:
        raise ValueError("No reviewed historical events to download")
    asof = completed_history_cutoff(settings.asof)
    print(f"Bloomberg completed-history cutoff: {asof:%Y-%m-%d} (current HK day excluded)")
    oldest = pd.to_datetime(events.last_day_locked).min()-pd.Timedelta(days=130)
    latest = min(asof, pd.to_datetime(events.last_day_locked).max()+pd.Timedelta(days=130))
    frames, error_frames = [], []
    with BloombergClient(cache_dir) as client:
        bench, errors = client.history(["HSI Index"], oldest, latest, fields=("PX_OPEN","PX_LAST"), refresh=refresh)
        if not errors.empty or bench.empty:
            raise RuntimeError("HSI calendar request is incomplete: "+errors.to_string(index=False))
        bench["date"] = pd.to_datetime(bench.date)
        if not bench.PX_LAST.map(_positive).all():
            raise ValueError("HSI calendar has missing/invalid observations")
        sessions = validate_sessions(bench.sort_values("date").date)
        # Dated session source is exportable and can be compared with an approved HK calendar.
        for n, (ticker, g) in enumerate(events.groupby("ticker"), 1):
            first = pd.to_datetime(g.last_day_locked).min()-pd.Timedelta(days=130)
            last = min(asof, pd.to_datetime(g.last_day_locked).max()+pd.Timedelta(days=130))
            frame, errors = client.history([ticker], first, last, refresh=refresh)
            if not frame.empty:
                # Keep missing numeric fields as float NaN and omit empty responses.
                # This avoids pandas' ambiguous empty/all-NA concatenation behavior.
                frame=frame.copy()
                for field in PRICE_FIELDS:
                    frame[field]=pd.to_numeric(frame[field],errors="raise").astype(float)
                frames.append(frame)
            if not errors.empty:
                error_frames.append(errors)
            if n % 20 == 0:
                print(f"Bloomberg: processed {n}/{events.ticker.nunique()} reviewed tickers")
    prices = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["ticker","date",*PRICE_FIELDS])
    errors = pd.concat(error_frames, ignore_index=True) if error_frames else pd.DataFrame(columns=["ticker","field","error"])
    return validate_prices(prices), sessions, bench.drop(columns="ticker"), errors


# Historical HKEX short-selling designation. This is NOT a borrow/locate feed.
HKEX_INDEX_URL = "https://www.hkex.com.hk/Services/Trading/Securities/Securities-Lists/Designated-Securities-Eligible-for-Short-Selling?sc_lang=en"
HKEX_COLUMNS = ["hkex_eligible_tminus21", "hkex_check_date", "hkex_effective_date",
                "hkex_update_date", "hkex_source_url", "hkex_check_reason",
                "hkex_stock_name", "hkex_list_count", "hkex_source_sha256",
                "hkex_retrieved_utc"]
HKEX_COMPACT = HKEX_COLUMNS[:5]


def _hkex_url(url):
    from urllib.parse import urlparse
    p = urlparse(url)
    if p.scheme != "https" or p.hostname not in {"www.hkex.com.hk", "hkex.com.hk"}:
        raise ValueError("The historical list link is not an official HKEX HTTPS URL")
    return url


def parse_hkex_index(raw):
    """Read dated FULL snapshots from the official table, never infer dates from URLs."""
    from html.parser import HTMLParser
    from urllib.parse import urljoin, urlparse

    class Rows(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.rows, self.cells, self.links, self.cell = [], None, [], None
            self.link, self.link_text = None, []

        def handle_starttag(self, tag, attrs):
            if tag == "tr":
                self.cells, self.links = [], []
            elif tag in {"td", "th"} and self.cells is not None:
                self.cell = []
            elif tag == "a" and self.cells is not None:
                self.link, self.link_text = dict(attrs).get("href", ""), []

        def handle_data(self, data):
            if self.cell is not None:
                self.cell.append(data)
            if self.link is not None:
                self.link_text.append(data)

        def handle_endtag(self, tag):
            if tag == 'a' and self.link is not None:
                if ''.join(self.link_text).strip():
                    self.links.append(self.link)
                self.link = None
            if tag in {"td", "th"} and self.cell is not None:
                self.cells.append("".join(self.cell))
                self.cell = None
            elif tag == "tr" and self.cells is not None:
                self.rows.append((self.cells, self.links))
                self.cells, self.cell = None, None

    parser = Rows()
    parser.feed(raw.decode("utf-8-sig"))
    records = []
    for cells, links in parser.rows:
        csv_links = [urljoin(HKEX_INDEX_URL, u) for u in links
                     if urlparse(u).path.lower().endswith(".csv")]
        # Ignore the header's explanatory CSV, but never skip a malformed dated row.
        if not csv_links or not cells or "effective date" in cells[0].lower():
            continue
        if len(cells) < 3 or len(set(csv_links)) != 1:
            raise ValueError("HKEX index has an ambiguous dated list row")
        dates = []
        for cell in cells[:2]:
            token = re.sub(r"\s+", "", cell)
            if not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", token):
                raise ValueError("HKEX effective/update date could not be parsed: " + repr(cell))
            dates.append(pd.Timestamp(datetime.strptime(token, "%d/%m/%Y")))
        online = [urljoin(HKEX_INDEX_URL, u) for u in links
                  if urlparse(u).path.lower().endswith(('.htm', '.html'))]
        if len(set(online)) > 1:
            raise ValueError('HKEX index has ambiguous View Online links')
        records.append(dict(effective_date=dates[0], update_date=dates[1],
                            url=_hkex_url(csv_links[0]),
                            html_url=_hkex_url(online[0]) if online else ''))
    if not records:
        raise ValueError("No dated HKEX snapshots were found; the page layout may have changed")
    return (pd.DataFrame(records).drop_duplicates()
            .sort_values(["effective_date", "update_date", "url"]).reset_index(drop=True))


def choose_hkex_snapshot(index, check_date):
    """Point-in-time selection. A failed applicable snapshot never falls back to an older one."""
    check = pd.Timestamp(check_date).normalize()
    effective = index[index.effective_date.le(check)]
    if effective.empty:
        raise ValueError("Check date predates available HKEX archive coverage")
    effective = effective[effective.effective_date.eq(effective.effective_date.max())]
    published = effective[effective.update_date.le(check)]
    if published.empty:
        raise ValueError("Applicable HKEX list was updated after the check date")
    chosen = published[published.update_date.eq(published.update_date.max())]
    if len(chosen) != 1:
        raise ValueError("Multiple conflicting HKEX snapshots have the same effective/update date")
    row = chosen.iloc[0]
    if (index.url.eq(row.url) & index.update_date.gt(check)).any():
        raise ValueError("Historical URL was reused by a later revision; original membership is unverified")
    return row


def parse_hkex_snapshot(raw, expected_date):
    """Validate a full numbered CSV before interpreting absence as 'No'."""
    import csv, io
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    if not text.endswith(("\n", "\r")):
        raise ValueError("HKEX CSV may be truncated")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or "list of designated securities eligible for short selling" not in " ".join(rows[0]).lower():
        raise ValueError("Response is not a full HKEX designated-securities CSV")
    effective = re.search(r"effective\s*date\s*:\s*(\d{1,2}/\d{1,2}/\d{4})", text[:2000], re.I)
    if not effective or pd.Timestamp(datetime.strptime(effective[1], "%d/%m/%Y")) != pd.Timestamp(expected_date):
        raise ValueError("HKEX CSV effective date does not match its index row")
    header = next((i for i, row in enumerate(rows) if "Stock Code" in [c.strip() for c in row]), None)
    if header is None:
        raise ValueError("HKEX CSV Stock Code header is missing")
    fields = [c.strip() for c in rows[header]]
    required = ["No.", "Stock Code", "Stock Short Name", "Currency", "Type"]
    if any(fields.count(c) != 1 for c in required):
        raise ValueError("HKEX CSV required columns are missing or ambiguous")
    positions = [fields.index(c) for c in required]
    members = {}
    for row in rows[header + 1:]:
        if not any(c.strip() for c in row):
            continue
        if len(row) <= max(positions):
            raise ValueError("HKEX CSV contains an incomplete data row")
        number, code, name, currency, kind = [row[i].strip() for i in positions]
        if not number.isdigit() or int(number) != len(members) + 1:
            raise ValueError("HKEX CSV row numbering is incomplete or duplicated")
        if not re.fullmatch(r"\d{1,5}", code) or int(code) == 0 or not all([name, currency, kind]):
            raise ValueError("HKEX CSV contains an invalid stock record")
        key = str(int(code))  # 00388 and 388 match; 80388 remains a separate counter.
        if key in members:
            raise ValueError("HKEX CSV contains duplicate stock codes")
        members[key] = name
    if len(members) < 100:
        raise ValueError("HKEX CSV is too short to validate as a full historical list")
    return members


def parse_hkex_online(raw, expected_date):
    """Validate HKEX's same-date View Online full list as a CSV transport fallback."""
    from html.parser import HTMLParser
    class Table(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.rows=[];self.cells=None;self.cell=None;self.text=[]
        def handle_starttag(self,tag,attrs):
            if tag=='tr':self.cells=[]
            elif tag in {'td','th'} and self.cells is not None:self.cell=[]
        def handle_data(self,text):
            self.text.append(text)
            if self.cell is not None:self.cell.append(text)
        def handle_endtag(self,tag):
            if tag in {'td','th'} and self.cell is not None:
                self.cells.append(' '.join(''.join(self.cell).split()));self.cell=None
            elif tag=='tr' and self.cells is not None:
                self.rows.append(self.cells);self.cells=None;self.cell=None
    try:text=raw.decode('utf-8-sig')
    except UnicodeDecodeError:text=raw.decode('cp1252')
    if '</html>' not in text.lower():raise ValueError('HKEX online list appears truncated')
    p=Table();p.feed(text)
    plain=' '.join(' '.join(p.text).split())
    if 'List of Designated Securities Eligible for Short Selling' not in plain:
        raise ValueError('Response is not a full HKEX online designated-securities list')
    date=re.search(r'Effective\s*Date\s*:\s*(\d{1,2}/\d{1,2}/\d{4})',plain,re.I)
    if not date or pd.Timestamp(datetime.strptime(date[1],'%d/%m/%Y'))!=pd.Timestamp(expected_date):
        raise ValueError('HKEX online effective date does not match the index row')
    header=next((i for i,r in enumerate(p.rows) if 'Stock Code' in r and 'No.' in r),None)
    if header is None:raise ValueError('HKEX online stock-code table is missing')
    positions=[p.rows[header].index(c) for c in ['No.','Stock Code','Stock Short Name']]
    members={}
    for row in p.rows[header+1:]:
        if not any(row):continue
        if len(row)<=max(positions):raise ValueError('HKEX online list has an incomplete record')
        n,code,name=[row[i] for i in positions]
        if not n.isdigit() or int(n)!=len(members)+1:raise ValueError('HKEX online numbering is incomplete')
        if not re.fullmatch(r'\d{1,5}',code) or not int(code) or not name:
            raise ValueError('HKEX online list has an invalid stock record')
        code=str(int(code))
        if code in members:raise ValueError('HKEX online list has duplicate codes')
        members[code]=name
    if len(members)<100:raise ValueError('HKEX online list is too short to validate as a full list')
    return members


def fetch_hkex_bytes(url):
    """Up to three HTTPS attempts for transient failures; certificates stay verified."""
    from urllib.request import Request,urlopen
    from urllib.error import HTTPError,URLError
    import http.client
    for attempt in range(3):
        try:
            request=Request(_hkex_url(url),headers={'User-Agent':'Mozilla/5.0 HKIPOLockupResearch/2.2'})
            with urlopen(request,timeout=15) as response:
                _hkex_url(response.geturl());raw=response.read(8*1024*1024+1)
                expected=response.headers.get('Content-Length')
                if expected is not None and len(raw)!=int(expected):
                    raise ValueError('incomplete HKEX response (Content-Length mismatch)')
            if not raw or len(raw)>8*1024*1024:raise ValueError('HKEX response is empty or exceeds the size limit')
            return raw
        except (HTTPError,URLError,OSError,http.client.HTTPException,ValueError) as exc:
            if isinstance(exc,HTTPError) and exc.code in {400,401,403,404,410}:raise
            if attempt==2:raise
            time.sleep(.5*(attempt+1))


def retrieve_hkex_snapshot(snap, cache_dir, fetcher=None, refresh=False):
    """Try the exact dated CSV, then its linked same-date HTML; never an older list."""
    import base64
    fetch=fetcher or fetch_hkex_bytes
    key=hashlib.sha256(f"{snap.url}|{snap.effective_date}|{snap.update_date}".encode()).hexdigest()
    path=Path(cache_dir)/(key+'.json');path.parent.mkdir(parents=True,exist_ok=True)
    sources=[(snap.url,'csv')]
    if getattr(snap,'html_url',''):sources.append((snap.html_url,'html'))
    allowed=dict(sources)
    if path.exists() and not refresh:
        try:
            record=json.loads(path.read_text(encoding='utf-8'))
            raw=base64.b64decode(record['body'],validate=True)
            assert record['url'] in allowed
            assert record['format']==allowed[record['url']]
            assert record['sha256']==hashlib.sha256(raw).hexdigest()
            assert record['retrieved_utc']
            parse=parse_hkex_snapshot if record['format']=='csv' else parse_hkex_online
            return parse(raw,snap.effective_date),record
        except Exception:pass
    errors=[]
    for url,kind in sources:
        try:
            raw=fetch(url)
            parse=parse_hkex_snapshot if kind=='csv' else parse_hkex_online
            members=parse(raw,snap.effective_date)
            record={'url':url,'format':kind,'sha256':hashlib.sha256(raw).hexdigest(),
                    'retrieved_utc':pd.Timestamp.now(tz='UTC').isoformat(),
                    'body':base64.b64encode(raw).decode('ascii')}
            temp=path.with_suffix('.tmp');temp.write_text(json.dumps(record),encoding='utf-8');temp.replace(path)
            return members,record
        except Exception as exc:errors.append(f'{kind}: {exc}')
    raise RuntimeError('Both official representations failed. '+'; '.join(errors))


class HKEXCheckError(RuntimeError):
    """A required historical check could not be completed; no final report is allowed."""
    def __init__(self, message, audit=None):
        super().__init__(message)
        self.audit = audit


def historical_hkex_rows(audit, settings):
    cutoff=min(pd.Timestamp(settings.asof),pd.Timestamp.now(tz='Asia/Hong_Kong').normalize().tz_localize(None))
    return pd.to_datetime(audit.last_day_locked).lt(cutoff)


def read_hkex_archive():
    """Verified official snapshot data are embedded so historical checks survive outages."""
    import base64,zlib
    raw=zlib.decompress(base64.b64decode(_HKEX_ARCHIVE_B64))
    if hashlib.sha256(raw).hexdigest()!=_HKEX_ARCHIVE_SHA256:
        raise HKEXCheckError('Embedded HKEX archive integrity check failed. Restore the complete Python file.')
    return json.loads(raw)


def _bundled_hkex_members(archive, snap):
    key=(str(snap.effective_date.date()),str(snap.update_date.date()),snap.url)
    found=[r for r in archive['records'] if (r['effective_date'],r['update_date'],r['url'])==key]
    if not found:return None
    if len(found)!=1:raise ValueError('Embedded HKEX source key is ambiguous')
    record=found[0]
    members={str(archive['securities'][i][0]):archive['securities'][i][1] for i in record['security_ids']}
    if len(members)!=record['count'] or len(record['security_ids'])!=record['count']:
        raise ValueError('Embedded HKEX membership count does not match the validated source')
    return members,{'url':record['source_url'],'format':record['format'],
                    'sha256':record['source_sha256'],'retrieved_utc':record['retrieved_utc']}


def ensure_hkex_complete(audit, settings):
    required=historical_hkex_rows(audit,settings)
    if 'hkex_eligible_tminus21' not in audit:
        raise HKEXCheckError('Historical HKEX checks have not been run.',audit)
    missing=required & ~audit.hkex_eligible_tminus21.isin(['Yes','No'])
    if missing.any():
        raise HKEXCheckError(f'{int(missing.sum())} historical HKEX checks are incomplete. Final Excel export stopped.',audit)


def check_hkex_shortability(audit, sessions, settings, cache_dir, output_dir=None, fetcher=None, archive=None):
    """Every historical event receives Yes/No, or the final report is stopped.

    Current/future events stay in Inputs with a blank eligibility cell and an explicit
    out-of-scope reason. Existing v2 price admission/calculations remain unchanged.
    T-21 uses Bloomberg HSI-observed HK sessions and the selected v2 T0 convention.
    """
    fetch=fetcher or fetch_hkex_bytes
    days=validate_sessions(sessions)
    result=audit.drop(columns=HKEX_COLUMNS,errors='ignore').copy()
    for col in HKEX_COLUMNS:result[col]=pd.NaT if col.endswith('_date') else ''
    result['hkex_list_count']=pd.Series(pd.NA,index=result.index,dtype='Int64')
    required=historical_hkex_rows(result,settings)
    result.loc[~required,'hkex_check_reason']='Current/future event excluded from the historical study'
    for idx,row in result[required].iterrows():
        try:
            anchor=anchor_position(days,row.last_day_locked,settings.anchor)
            result.at[idx,'hkex_check_date']=days[offset_position(days,anchor,-21,'sessions')]
        except (ValueError,TypeError) as exc:
            result.at[idx,'hkex_check_reason']='Bloomberg session coverage: '+str(exc)
    def fail(message):
        if output_dir is not None:
            out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
            failed=result[required & ~result.hkex_eligible_tminus21.isin(['Yes','No'])]
            failed.to_csv(out/'hkex_check_errors.csv',index=False)
        raise HKEXCheckError(message,result)
    if result.loc[required,'hkex_check_date'].isna().any():
        fail('Bloomberg session coverage cannot establish T−21 for every historical event. See hkex_check_errors.csv.')
    if archive is None:archive=read_hkex_archive()
    meta={'index_url':HKEX_INDEX_URL,'check_basis':'T0 minus 21 Bloomberg HSI-observed HK sessions',
          't0_convention':settings.anchor,'filters_backtest':False,
          'meaning':'HKEX designation only; actual borrow/locate is not checked',
          'outside_historical_scope':int((~required).sum()),'historical_rows':int(required.sum()),
          'archive_verified_through':archive.get('verified_through','')}
    if not required.any():return result,meta
    try:
        raw=fetch(HKEX_INDEX_URL);index=parse_hkex_index(raw)
        meta.update(index_source='Live HKEX index',index_retrieved_utc=pd.Timestamp.now(tz='UTC').isoformat(),
                    index_sha256=hashlib.sha256(raw).hexdigest())
        if output_dir is not None:
            out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
            (out/'hkex_index_used.html').write_bytes(raw)
    except Exception as exc:
        covered=archive.get('verified_through') and result.loc[required,'hkex_check_date'].max()<=pd.Timestamp(archive['verified_through'])
        if not covered or not archive.get('records'):
            result.loc[required,'hkex_check_reason']='HKEX index unavailable: '+str(exc)[:200]
            fail('HKEX index is unavailable and the embedded archive does not cover the required dates. Final report stopped.')
        index=pd.DataFrame([{k:r.get(k,'') for k in ['effective_date','update_date','url','html_url']} for r in archive['records']])
        for col in ['effective_date','update_date']:index[col]=pd.to_datetime(index[col])
        meta.update(index_source='Embedded official HKEX archive',index_retrieved_utc=archive['fetched_utc'],
                    index_sha256=archive['index_sha256'],online_refresh_error=str(exc)[:240])
        print('HKEX website unavailable: using the validated embedded official archive, verified through '+archive['verified_through']+'.',flush=True)
    if output_dir is not None:index.to_csv(Path(output_dir)/'hkex_snapshot_index.csv',index=False)
    loaded={};bundled_count=0;external_count=0
    for idx,row in result[required].iterrows():
        try:
            snap=choose_hkex_snapshot(index,row.hkex_check_date)
            result.at[idx,'hkex_effective_date']=snap.effective_date
            result.at[idx,'hkex_update_date']=snap.update_date
            result.at[idx,'hkex_source_url']=snap.url
            key=(snap.url,snap.effective_date,snap.update_date)
            if key not in loaded:
                bundled=_bundled_hkex_members(archive,snap)
                if bundled is not None and not REFRESH_HKEX:
                    loaded[key]=bundled;bundled_count+=1
                else:
                    try:
                        loaded[key]=retrieve_hkex_snapshot(snap,cache_dir,fetcher=fetch,refresh=REFRESH_HKEX)
                        external_count+=1
                    except Exception:
                        if bundled is None:raise
                        loaded[key]=bundled;bundled_count+=1
                        print(f'HKEX refresh failed for {snap.effective_date:%Y-%m-%d}; its validated embedded snapshot is used.',flush=True)
                if len(loaded)%20==0:print(f'HKEX: resolved {len(loaded)} applicable historical lists',flush=True)
            members,record=loaded[key]
            code=normalize_ticker(row.ticker).split()[0]
            result.at[idx,'hkex_eligible_tminus21']='Yes' if code in members else 'No'
            result.at[idx,'hkex_stock_name']=members.get(code,'')
            result.at[idx,'hkex_list_count']=len(members)
            result.at[idx,'hkex_source_url']=record['url']
            result.at[idx,'hkex_source_sha256']=record['sha256']
            result.at[idx,'hkex_retrieved_utc']=record['retrieved_utc']
        except Exception as exc:
            result.at[idx,'hkex_check_reason']=str(exc)[:240]
            fail(f'HKEX check failed for {row.ticker}, T−21 {row.hkex_check_date:%Y-%m-%d}: {exc}. Final report stopped.')
    ensure_hkex_complete(result,settings)
    meta.update(distinct_lists_used=len(loaded),embedded_lists_used=bundled_count,external_lists_used=external_count,
                historical_checks_complete=True)
    return result,meta


def with_hkex_columns(frame, audit, columns=None):
    """Join by ticker AND event date, never ticker alone; preserve row count/order."""
    columns = HKEX_COLUMNS if columns is None else columns
    columns = [c for c in columns if c in audit]
    if not columns or frame.empty:
        return frame
    keys = ["ticker", "last_day_locked"]
    lookup = audit[keys + columns].drop_duplicates()
    if lookup.duplicated(keys).any():
        raise ValueError("Conflicting HKEX checks for the same ticker/event date")
    return frame.drop(columns=columns, errors="ignore").merge(lookup, on=keys, how="left", validate="many_to_one", sort=False)
def export_results(output_dir, audit, trades, summary, common_summary, paths, settings, metadata=None):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = dict(input_audit=audit, trades=trades, strategy_summary=summary,
                 common_sample_summary=common_summary, event_paths=paths)
    if not trades.empty:
        files["skipped_trades"] = trades[~trades.status.eq("Completed")]
        files["per_event_returns"] = with_hkex_columns(
            trades.pivot(index=["event_id","ticker","last_day_locked"],
                         columns="strategy", values="gross_return").reset_index(), audit, HKEX_COMPACT)
    for name, df in files.items():
        df = price_only_columns(df)
        df.to_csv(out / f"{name}.csv", index=False, float_format="%.12g")
    info = dict(version=VERSION, settings=asdict(settings), **(metadata or {}))
    info["csv_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob("*.csv"))}
    (out / "run_manifest.json").write_text(json.dumps(info, indent=2, default=str))
    return out


def price_only_columns(frame):
    """The delivered report contains gross price results, with no assumed-cost view."""
    return frame.drop(columns=['after_cost_price_return','net_return','borrow_cost',
                              'transaction_cost','dividend_cost','borrow_rate_used',
                              'mean_after_cost_price','mean_net_if_covered'], errors='ignore')


def export_excel(path, audit, trades, summary, common_summary, prices, paths, settings=None, metadata=None):
    """Create the requested Python-generated Excel snapshot after each notebook run.

    Python owns the calculations; the XLSX is a dated results export, not a second
    calculation engine. Native charts reference the visible numeric result cells.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.chart import BarChart, LineChart, Reference
    from openpyxl.chart.shapes import GraphicalProperties
    from openpyxl.chart.label import DataLabelList
    from openpyxl.chart.marker import DataPoint
    from openpyxl.utils import get_column_letter
    cfg, meta = settings or Settings(), metadata or {}
    if "hkex_eligible_tminus21" in audit:
        ensure_hkex_complete(audit,cfg)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Summary'
    grey, ink, green, red = 'EDEFF1', '24282B', '23745B', 'CB2125'
    thin = Side(style='thin', color='D9DDE1')
    pct = '0.00%;[Red](0.00%);"—"'
    rate_columns = {'mean_gross','mean_after_cost_price','median_issuer_gross','win_rate',
                    'ci_low','ci_high','worst_event','best_event','p05_event',
                    'gross_return','after_cost_price_return','net_return','borrow_cost',
                    'transaction_cost','dividend_cost','benchmark_return','short_plus_hsi_return',
                    'worst_mark_return','best_mark_return','borrow_rate_used','borrow_rate',
                    'short_return_from_Tminus21','Mean return'}
    labels = {'strategy_label':'Strategy','events':'Events','issuers':'Issuers',
              'mean_gross':'Mean gross return','mean_after_cost_price':'After assumed costs',
              'win_rate':'Win rate','ci_low':'95% interval low','ci_high':'95% interval high',
              'worst_event':'Worst event','median_issuer_gross':'Median issuer return',
              'ticker':'Ticker','name':'Company','last_day_locked':'Last day locked',
              'input_date':'Supplied date','source_row':'Source row','t0':'T0 session',
              'entry_date':'Entry date','exit_date':'Exit date','entry_price':'Entry price',
              'exit_price':'Exit price','gross_return':'Gross return',
              'after_cost_price_return':'After-cost price return','net_return':'After dividends and costs',
              'status':'Status','reason':'Exclusion reason','date':'Date',
              'PX_OPEN':'Open','PX_LAST':'Close','PX_VOLUME':'Volume',
              'source_url':'Primary source','category':'Holder category','borrow_rate':'Assumed annual borrow',
              'fee_bps_per_leg':'Fee per leg (bps)'}
    labels.update(dict(zip(HKEX_COLUMNS, [
        'HKEX eligible at T−21', 'HKEX check date (T−21)', 'HKEX list effective',
        'HKEX list updated', 'HKEX historical list', 'HKEX check detail',
        'Name on HKEX list', 'Securities in list', 'HKEX source SHA-256', 'HKEX retrieved (UTC)'])))
    if not trades.empty:
        labels.update(trades.drop_duplicates('strategy').set_index('strategy').strategy_label.to_dict())

    def value(x):
        if x is None or (not isinstance(x,(list,dict)) and pd.isna(x)):
            return None
        if isinstance(x,pd.Timestamp):
            return x.to_pydatetime().replace(tzinfo=None)
        if isinstance(x,np.generic):
            return x.item()
        return x

    def sheet_style(s):
        s.sheet_view.showGridLines = False
        s.freeze_panes = 'C2'
        s.sheet_properties.pageSetUpPr.fitToPage = True
        s.page_setup.orientation = 'landscape'
        s.page_setup.paperSize = s.PAPERSIZE_A3
        s.page_setup.fitToWidth = 1
        s.page_setup.fitToHeight = 0
        s.print_options.horizontalCentered = True
        s.sheet_properties.outlinePr.summaryRight = False

    def write_table(s, df, start_row=1, start_col=1, filters=True):
        if len(df.columns)==0:
            s.cell(start_row,start_col,'No observations')
            return start_row
        for j,col in enumerate(df.columns,start_col):
            cell=s.cell(start_row,j,labels.get(col,str(col).replace('_',' ').capitalize()))
            cell.font=Font(name='Arial',size=10,bold=True,color=ink)
            cell.fill=PatternFill('solid',fgColor=grey)
            cell.alignment=Alignment(horizontal='left',vertical='center',wrap_text=True)
            cell.border=Border(bottom=thin)
            width=42 if col in {'strategy_label','name','reason','status'} else 17
            if col.startswith(('pre_','post_','cross_','expiry_')):
                width=24
            if col in {'hkex_eligible_tminus21','hkex_source_url'}:
                width=23
            if col in {'hkex_check_reason','hkex_source_sha256'}:
                width=42
            if col=='hkex_retrieved_utc':
                width=30
            if col in {'source_url','event_id','input_id'}:
                width=38
            s.column_dimensions[get_column_letter(j)].width=width
        s.row_dimensions[start_row].height=32
        for i,row in enumerate(df.itertuples(index=False,name=None),start_row+1):
            for j,(col,x) in enumerate(zip(df.columns,row),start_col):
                x=value(x)
                cell=s.cell(i,j,x)
                if isinstance(x,str):
                    cell.data_type='s'  # Literal strings cannot become executable formulas.
                cell.font=Font(name='Arial',size=10,color=ink)
                cell.alignment=Alignment(vertical='center',horizontal='left' if isinstance(x,str) else 'right')
                if isinstance(x,(datetime,date)):
                    cell.number_format='dd-mmm-yyyy'
                elif col in rate_columns or col.startswith(('pre_','post_','cross_','expiry_')):
                    cell.number_format=pct
                elif col=='PX_VOLUME':
                    cell.number_format='#,##0'
                elif isinstance(x,(float,np.floating)):
                    cell.number_format='#,##0.0000'
                elif isinstance(x,(int,np.integer)):
                    cell.number_format='#,##0'
                if col in {'source_url','hkex_source_url'} and isinstance(x,str) and x.startswith('https://'):
                    cell.hyperlink=x
                    cell.value=('HKEX dated list' if col=='hkex_source_url' else
                                'HKEX filing' if 'hkexnews.hk/' in x else 'Primary filing')
                    cell.font=Font(name='Arial',size=10,color='245577',underline='single')
                if col=='hkex_eligible_tminus21':
                    cell.font=Font(name='Arial',size=10,bold=True,
                                   color={'Yes':green,'No':red}.get(x,ink))
            s.row_dimensions[i].height=18
        last=start_row+len(df)
        if filters and len(df):
            s.auto_filter.ref=f'{get_column_letter(start_col)}{start_row}:{get_column_letter(start_col+len(df.columns)-1)}{last}'
            s.print_title_rows=f'{start_row}:{start_row}'
        for j,col in enumerate(df.columns,start_col):
            if col in rate_columns or col.startswith(('pre_','post_','cross_','expiry_')):
                area=f'{get_column_letter(j)}{start_row+1}:{get_column_letter(j)}{max(last,start_row+1)}'
                s.conditional_formatting.add(area,CellIsRule(operator='lessThan',formula=['0'],font=Font(color=red)))
                s.conditional_formatting.add(area,CellIsRule(operator='greaterThan',formula=['0'],font=Font(color=green)))
        return last

    def dates(df):
        d=df.copy()
        for col in d.columns:
            if col in {'input_date','last_day_locked','t0','entry_date','exit_date','date',
                       'hkex_check_date','hkex_effective_date','hkex_update_date'}:
                d[col]=pd.to_datetime(d[col],errors='coerce')
        return d

    sheet_style(ws)
    ws.freeze_panes='B6'
    # Compact result context, no title banner or Notes tab.
    for row,(key,x) in enumerate([
        ('Data',meta.get('data_source','')),
        ('As of',pd.Timestamp(cfg.asof)),
        ('T0', 'Last session on/before last day locked' if cfg.anchor=='last_locked' else 'First session after last day locked'),
        ('Return basis','Gross short price P&L / initial notional')],1):
        ws.cell(row,1,key).font=Font(name='Arial',size=10,bold=True,color=ink)
        c=ws.cell(row,2,value(x)); c.font=Font(name='Arial',size=10,color=ink)
        if row==2:c.number_format='dd-mmm-yyyy'
    ws['L2']='Days'; ws['M2']='HK sessions; month = 21' if cfg.day_basis=='sessions' else 'Calendar days / calendar month'
    if 'hkex_eligible_tminus21' in audit:
        counts=audit.drop_duplicates(['ticker','last_day_locked']).hkex_eligible_tminus21.value_counts()
        ws['L3']='HKEX at T−21'
        ws['M3']='; '.join(f'{s}: {int(counts.get(s,0))}' for s in ['Yes','No'])
    columns=['strategy_label','events','issuers','mean_gross',
             'win_rate','median_issuer_gross','worst_event','ci_low','ci_high']
    available=summary[[c for c in columns if c in summary]]
    last=write_table(ws,available,start_row=5,filters=False)
    common_start=last+4
    ws.cell(common_start-1,1,'Common completed cohort').font=Font(name='Arial',size=10,bold=True,color=ink)
    write_table(ws,common_summary[[c for c in columns if c in common_summary]],start_row=common_start,filters=False)
    ws.column_dimensions['A'].width=38
    for col in 'BC': ws.column_dimensions[col].width=12
    if not summary.empty:
        chart=BarChart()
        chart.type='bar'; chart.style=2; chart.title='Mean short returns'
        chart.y_axis.title='Return / initial notional'
        chart.y_axis.numFmt='0%'
        chart.add_data(Reference(ws,min_col=4,max_col=4,min_row=5,max_row=last),titles_from_data=True)
        chart.set_categories(Reference(ws,min_col=1,min_row=6,max_row=last))
        chart.legend=None
        chart.width=24; chart.height=15
        for series,color in zip(chart.series,['23745B','153954']):
            series.graphicalProperties.solidFill=color
            series.graphicalProperties.line.solidFill=color
            series.data_points=[DataPoint(idx=i,spPr=GraphicalProperties(
                solidFill='23745B' if v>=0 else 'CB2125')) for i,v in enumerate(summary.mean_gross)]
        ws.add_chart(chart,'L5')
    if not paths.empty:
        issuer=paths.groupby(['offset','ticker']).short_return_from_Tminus21.mean().reset_index()
        curve=issuer.groupby('offset').short_return_from_Tminus21.agg(['mean','count']).reset_index()
        curve.columns=['Session offset','Mean return','Issuers observed']
        curve_start=common_start+len(common_summary)+4
        end=write_table(ws,curve,start_row=curve_start,filters=False)
        chart=LineChart(); chart.title='Event study from T−21 close'; chart.style=13
        chart.y_axis.title='Short price return'; chart.y_axis.numFmt='0%'
        chart.x_axis.title='HK sessions from T0'; chart.legend=None
        chart.add_data(Reference(ws,min_col=2,min_row=curve_start,max_row=end),titles_from_data=True)
        chart.set_categories(Reference(ws,min_col=1,min_row=curve_start+1,max_row=end))
        chart.series[0].graphicalProperties.line.solidFill='153954'
        chart.series[0].graphicalProperties.line.width=24000
        chart.smooth=False
        chart.series[0].smooth=False
        chart.width=24; chart.height=12; chart.display_blanks='gap'
        ws.add_chart(chart,'L35')

    if not trades.empty:
        event=trades.pivot(index=['event_id','ticker','name','input_date','last_day_locked','t0'],
                          columns='strategy',values='gross_return').reset_index()
        # Omit events with no completed strategy from the return grid; all remain in Trades/Inputs.
        event=event[event.event_id.isin(trades.loc[trades.status.eq('Completed'),'event_id'])]
    else:
        event=pd.DataFrame()
    event=with_hkex_columns(event,audit,HKEX_COMPACT)
    if not event.empty and 'hkex_eligible_tminus21' in event:
        front=['event_id','ticker','name','input_date','last_day_locked','t0']
        event=event[front+HKEX_COMPACT+[c for c in event if c not in front+HKEX_COMPACT]]
    input_cols=['source_row','ticker','name','input_date','last_day_locked']+HKEX_COLUMNS+['category','status','source_url']
    trade_cols=['ticker','name','last_day_locked','t0']+HKEX_COMPACT+['strategy_label','status','reason',
                'entry_date','exit_date','entry_price','exit_price','gross_return',
                'after_cost_price_return','net_return','borrow_cost','transaction_cost','dividend_cost',
                'calendar_days','sessions_held','path_missing_sessions','worst_mark_return','best_mark_return',
                'benchmark_return','short_plus_hsi_return','locate_status','borrow_rate_used',
                'input_date','entry_field','exit_field','event_id','source_url']
    datasets=[('By event',event),('Trades',trades[[c for c in trade_cols if c in trades]]),
              ('Inputs',audit[[c for c in input_cols if c in audit]]),
              ('Prices',prices)]
    for name,df in datasets:
        df=price_only_columns(df)
        s=wb.create_sheet(name); sheet_style(s); write_table(s,dates(df))
        if 'hkex_eligible_tminus21' in df:
            from openpyxl.comments import Comment
            s.cell(1,list(df.columns).index('hkex_eligible_tminus21')+1).comment=Comment(
                'Exchange designation at T0 minus 21 HK sessions. Yes/No requires a validated applicable full HKEX list. '
                'Historical checks must all be Yes/No before export. Blank cells are current/future events outside the historical study. Actual borrow/locate is not checked. '
                'This annotation does not filter the return study or confirm the supplied lock-up date.', 'HKEX check')
        s.sheet_properties.tabColor={'By event':'23745B','Trades':'153954','Inputs':'888888',
                                    'Prices':'888888','Cost scenarios':'BA9846'}[name]
        if name=='By event':
            s.column_dimensions['A'].hidden=True
            s.freeze_panes='D2'
    ws.sheet_properties.tabColor=red
    wb.active=0
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    wb.save(path)
    wb.close()
    return path


def write_html_report(output, audit, trades, summary, common, figures, metadata, settings=None):
    """Standalone readable report with embedded PNGs. No remote scripts or fonts."""
    import base64
    import io
    cfg = settings or Settings()
    anchor_text = ("the last Hong Kong session on or before the confirmed last day locked"
                   if cfg.anchor == "last_locked" else "the first Hong Kong session strictly after the confirmed last day locked")
    basis_text = ("Hong Kong trading sessions; one month is 21 sessions" if cfg.day_basis == "sessions"
                  else "calendar days, mapped to the preceding Hong Kong session; one month is a calendar month")
    def table(df, percent_cols=()):
        d = df.copy()
        for col in percent_cols:
            if col in d:
                d[col] = d[col].map(lambda x: f"{x:+.2%}" if pd.notna(x) else "Unavailable")
        return d.to_html(index=False, border=0, escape=True, na_rep="Unavailable")
    n = 0 if trades.empty else int(trades.status.eq("Completed").sum())
    s = summary.rename(columns={"strategy_label":"Strategy", "events":"Events", "issuers":"Issuers",
                               "mean_gross":"Mean price return", "mean_after_cost_price":"After assumed costs",
                               "win_rate":"Win rate", "worst_event":"Worst event"})
    cols = [c for c in ["Strategy","Events","Issuers","Mean price return","Win rate","Worst event"] if c in s]
    parts = ["<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
             "<title>HK IPO lock-up backtest</title><style>body{font:15px/1.55 Arial,sans-serif;color:#282828;max-width:1180px;margin:36px auto;padding:0 24px}h1{font-size:25px;border-bottom:3px solid #CB2125;padding-bottom:10px}h2{font-size:18px;margin-top:32px}.meta{color:#5a5a5a}.table{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th{background:#eceef0;text-align:right}td,th{padding:9px 10px;border-bottom:1px solid #ddd;white-space:nowrap}td:first-child,th:first-child{text-align:left}td{text-align:right}img{display:block;max-width:100%;height:auto;margin:28px 0}a{color:#234f70}code{background:#eee;padding:2px 4px}details{margin:16px 0}summary{cursor:pointer;font-weight:bold}</style></head><body>",
             "<h1>HK IPO lock-up backtest</h1>",
             f"<p class='meta'>{html.escape(str(metadata.get('data_source','')))} · {n:,} completed event–strategy observations</p>",
             f"<p>T0 is {anchor_text}. Offsets are {basis_text}. Positive returns mean the short made money.</p>",
             "<p>Gross short price returns only. No assumed costs are deducted. Dividends, borrow, fees and execution constraints are outside this price study. Returns use initial short notional, not margin capital.</p>",
             "<h2>Strategy comparison</h2><div class='table'>",
             table(s[cols], ["Mean price return","After assumed costs","Win rate","Worst event"]), "</div>",
             "<p>Each issuer has one weight; repeated expiry events are averaged within issuer. Strategies can have different samples. The common-cohort CSV is provided for a like-for-like comparison. Testing many timings is exploratory and does not establish an out-of-sample trading edge.</p>"]
    for name, fig in figures.items():
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=130, bbox_inches="tight")
        parts.append(f"<img alt='{html.escape(name)}' src='data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}'>")
    counts = audit.status.value_counts().rename_axis("Input review status").reset_index(name="Dates")
    parts += ["<h2>Coverage</h2><div class='table'>", table(counts), "</div>",
              "<p>Input rows are a supplied snapshot. The admitted subset has primary-reviewed cornerstone dates and completed ±30-session endpoints. This retrospective selection can introduce survivorship and look-ahead selection effects; it is not every IPO.</p>"]
    if not trades.empty:
        skipped = trades.loc[~trades.status.eq("Completed"),"reason"].value_counts().rename_axis("Skipped reason").reset_index(name="Event–strategy rows")
        parts += ["<details><summary>Skipped observations</summary><div class='table'>",table(skipped),"</div></details>"]
    parts += ["<p>Open the companion notebook to inspect each event, change settings, pull Bloomberg data, and export the full audit and trade ledger.</p></body></html>"]
    Path(output).write_text("\n".join(parts), encoding="utf-8")

# Embedded source snapshot: date/ticker rows and primary-review decisions only.
# No market prices are embedded. SHA256 verifies the snapshot before it is read.
_EMBEDDED_INPUTS_B64 = (
    'eNrsveuOXEeSJvgqif41BaRKbmZu5u7T/3YumMHs7hRmdv8VUPBrF9EUqSGpri7sn3mH3SecJ1nzc4k4zPAgmalzMpgpCRJlzJMR'
    'x83NL3b97P/5h/ov9d2nv3yo//Km/u2P+eO//MO/vfuHT2/yP9cP92/e/fzLp7+U+Knev40fO/X3v7x9r4/KfdYf/tP7D3+/z+/f'
    'tTcfftIfxZ/qu/JT/7K0/NLH9798yPUvv3x4u5If/xqRZf3bz/Gf6v3Pv6S3b/Tr3rx/N79qHspn9Lv3Sn+MP/38tv4l/7X2L/8L'
    'GhQw6HUo78qb/tt/aW/e6oNOftz8dDOK8xDnH3788zv9Cnv3n/7L3X/4H7+8+fT3e/1W/MHov/b+/v9+98/v3v/t3f1/jG8/1uXP'
    '/k9/8w9gfgB3/3++v6v/GvOnu58/vPkpfvj7D/OAa7nrr777KX7Kf/3Hu/L+Tjm4e/Ou1Q938e7jm3/94af37z79VT/785sPf//j'
    '+t1//fTp54//9scf//a3v8Ef//rP9V/f1b99VOLHt28+fqolv58InXH98Y8fqz7QocCPBo2dqE4YY8j+8a+ffrof8QY/GP86eCPH'
    '5nPe+AeAHyBsyX/3/sO7+uHjJ/3W+//rwy8ro08aC/9oGMJEdcIAsvvjz6Xdm8JeBxNLTLla8cmYxpIiUs4t9T/B60otAQywSU5K'
    'TaWRCz5ZihbvQeYxG16GP0lAV/a/P81z/Xj36a/1blrgd30vqgz+fjdvs39cBdQfv3n3T3fLDrl7/+4O/d1/zZ/eJ5VN/94/zrNw'
    'nqG7f7OZoj/sPDEqJHMhI0M/nPidyD1lZH80AWSiOmFMYJiGcg/8v/7n/6uLuj/6wYRlDOtE/+nzCdSlq0fSm09v/363HG8f70Du'
    '/o/4If+1zyP/491pL0QdwB/v9Atyvfvbm3fl/d/u3nxctsQks1h+evNJR3z3Mf6L/pmjiucf7/63t+/f/6Ri+Sf9Jp2dD7UsstmZ'
    '8T+/Q+TwuRCkzzyGLbnzRgm4rAclDDnvp7GEmmpjX0LQxZ8w+MjWgoPQJEKRHGqDYrMxhVwmLFCCiyEmZleKINyvm1vlh8+1UZYZ'
    '6hvl3acP79++1d/4X//z/+sLo/9VD8VPep/o5XX3c/3w5n35wz/eff6p8/Zan4RHfd/OQtAFIeAvbjzu0/hybgVGN98KSuitAOut'
    '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'
)
_EMBEDDED_INPUTS_SHA256 = 'f3bc6619f59b97655dec647b3fc6bc51136a0bb995db01b9e2e1e437b82d36f1'

def _read_embedded_inputs():
    import base64, zlib
    raw=zlib.decompress(base64.b64decode(_EMBEDDED_INPUTS_B64))
    if hashlib.sha256(raw).hexdigest()!=_EMBEDDED_INPUTS_SHA256:
        raise ValueError("Embedded input snapshot failed its integrity check. Copy the complete original file again.")
    return json.loads(raw)


# Verified official HKEX history. Public stock codes/names only; no market prices.
_HKEX_ARCHIVE_SHA256 = '6938cffea5ba221537f9beb38a2bb8383db59e6607b1eabaf03e40006ba28714'
_HKEX_ARCHIVE_B64 = (
    'eNrsvXuP41aSL/hVCP9RMxc3syy+SQOLBUVRElMUqeIjlarBoJHPdmHc7YHt7p6Li/3uG784cR6Uyp6aHu+OfUeAbTiDFHl4HhHx'
    'i+f//urTn19e/+0Pf/nhu6+++erbn3761x+/+frrv/3tb++//ZfXf3v//P2f6H++Hl5/+Oun59cfvx5/eHz59Oc/EuH5Lz98+ukT'
    'kez/3jaffvzpx69Xrz9++uOfH396fbl1rlXfffrjp6fvXm/fvv/hdvj2+x9+oqvffUcP+79/fP7Dd49//uP/9frnr25kOD9++xjE'
    'CY1o4T8/LsL88TENnrLo5fn5KXmLH1/yIHgJguc0SsPsLVq8RcHj89tbFOdPi9eX1/gtDBbJ40vwFtAT315/ev729eUPf/npmR4Y'
    'LILk1l/cBvnoR99EyTdx/j5OF9Fi8T8Xi28WC/rBX19/+PT2iX7x07c/fP+XP37r/iqj6z+ar/rqm3/6J//mq3K39bZds6rbzfDV'
    'P9/8U0Ck5jAjhTdfbXfeO6/c1m3hbQomRjdfHbdFv57dGdOdw7Kc0ZKbrw7dseq9YhiqkUkZkcryiP/1F/STot14zUT/2fTddGCy'
    'L+Shov8si3bHVBrctmpXVT90rdcU7YqpNJTtaShab1XdM4FeOdCID4eR/0xvvmqro3fs+mZl7snpnmPdV96hKOt1XXoFf/0Cn1VV'
    'TVfyGwP6drzd69ZeRV9Qq7voO8ttdV80NX1X3Y7/0DA5ARlztO/GrveWk5pRev+maIqHk1e1PKKAJmCsacBFy/Pr698VVd8NNKCK'
    'yVgK+nu4pXn+R0zp/2Ayfe6uOzZdZz44pPGsK6/s2qHrRwyIxxPSa9Z1P4ze2BcljYiJOV7mLat6VWwnmmJeTBrBpq+K0auKTVN5'
    'WybSt5fvD++9Q7c7bGWyI0x2UZUd/4H13r0baL3HqlE7YMGbZV31/cmzg455PftlN/VeSbPQ8xfG9IXrou6PXbfiPcNEeu1m6srO'
    '7oYYL+0O1bFqGnsfzXbR0AqssND0rh2/KaFn0ue2w0GmQq1NQo/YVKPX1mpyE/r1fqTBdD3dWIx1x0uRYFtg4/X1bVOYBU9p+Pu6'
    'L/ZFr76VifT1p/fje48mrhlPvLF5Jb3ufvA2XldWNAwm05juffs9GX3iULed2cJZrHdA1VTl2KvBZNjHU+ttcTR2Re2pWc+we/DX'
    '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'
    '5FdEfkXkV0R+ReRXRH5F5FdEfkXkX4zIcyDuKyq/ovL/7qg8+Plc8uC33hmdGN2vjMqD31MuefCFueTRY5Y+Lh5fn6PXl7fFglSa'
    'OHkixYPOWvRIiuPr8+I5T9MXP356eiSl84UUwFcC5tniiVD8s/9FqDx6T2p5HqdXP/kVlV9R+RWVX1H5FZVfUfkVlV9R+RWVX1H5'
    'F6PyKyK/IvL85xF59ptH5Pmvjcjz3xMiz78MkdPeJBXy6SVJHwluEerKEaROu+vpicQKIS9ShvP0Mcvfshfaf4/h4vXlJXwm9dSP'
    '3tKXty9E5MSG6FReNjVProj8isiviPyKyK+I/IrIr4j8isj/eyDynO/5ZVSe4xn/TZB5jrn6naDzHM9xEHqOZ/4MSs+BNK9I/XeP'
    '1HMfe5Q0cj679Ax6f473/wKCz2lsOcYmSD7HGP9ONJ8Hc0Sfo768g+pzfON/BNn/bOc0Dfp/y9j21+6clvyeOqclX9o5LQ6e/eD5'
    'KXld0H+C1+enR5KYj9nTG6H9t5fAf1m8xPmTnz89EpKJn9/it+fHOHh7Jb0t958fvywCPn5PMJE0tEtkH1+R/RXZX5H9/8vevaDF'
    'jWtbAB5R+LT11pmNnvMfwlkqEqBTZUoQAzase/t0BwoMBmlrrz+2zGTPZM9kz2TPZH/GZM9Uz1TPVM9Uf4pUH5DeN1I9Xjr6fe2Y'
    '5Pum+nnA06T657O/dwW9FEQFV7pVuQU1YswI8rZivnvfczcd3SMKSxytS0N31swoaABb92pkvZrqsbShC2GqZ6pnqmeqZ6pnqmeq'
    'Z6pnqmeqZ6r/4ak+4WfLVP+JqV5kO9Uf/Sp8TOidUz0OeJ5U/3T29/6uPl7yvEkFK14woyJo2You2ureER7mze9dZ13QELghdhTV'
    'Gxq/2HXsPfqlVO8fEAPRhTHVM9V/aapPmqmeqZ6pnqmeqZ6pnqmeqZ6pnqn+h6V6rTZTvRz9CnxM1p1TvT7RFfjPZ38n1fvSfI5u'
    '2FoQL/wwuWbpPXvV+kBThrWgVFfwjlGNb1jaFNq0FmX43pRKi6kebRa6netUH5jqmeqZ6pnqmeqZ6pnqmeqZ6pnqmepXUn0yTPVX'
    'qR6/l7+TfZrpnen+RrrfvhJfH/5KfL33lfj6TFfi68Ur8aUYM1LWeqDjUL2htraB4tjR2Hdjh+TY0e/YgYUAtbZryWhbuiltXqLv'
    'ZTHdo7yhS2G6Z7pnume6Z7pnume6Z7pnume6Z7pnume6/5J0n7bT/eGvyN97X/xwpn3xw+q++A1FxvqM4Zpbnjvn9a7QX5vQVUsV'
    'VaKNglqJ0tB6SajwpbrepMZWfB/aLqX78ID4hJHNffGZ7pnume6Z7pnume6Z7pnuv026Z7JnsmeyP0myj7+3ybuR7PGSPXiyx0Da'
    'N9nPA54m2T+f/Z1kj/64qpJqzkVajqE1nVFXom4m6ZyGqQltCGZdRZrTteK9aNWKHS4PzF9ZTPYoqejCr5O9YbJnsmeyZ7Jnsmey'
    'Z7Jnsv+uyZ6p/vNSvTDNM80zzf8d2UVvp/mjX4WPgbJzmscBz5Pmn87+3vPrvWmjIo1IwdJR0O4js6MZsF2N1JpHbEcb1lHOtO01'
    'dST+rPB/A4PbquaW0nx8UMgx4XrnPP8Rf0//tVE+zQX3Mc5fZ/mnIP+Y4l9GeL0U4V+L72nG7VcjvPrUGJ/m53xGjN+M8O+J72+P'
    '7mnG7eX4vmdsj18c3Z9jezJ/R3ZZju3pEqHfE91vx/Zk0u/ofi+2f0ZkfxHX3xHT0/z+bkb112L6+yJ6msXwZUzfjOgr8RzF7FJZ'
    'PzueYyzOY78S09P8uu+K6j8jpqdLJN8/qt+N6fg9Maozqp8tqqdLPN8/rqd5jMXInubXYmy/RPZk0yW2pxmpN2J7cvKNY3vajO0S'
    'Dx/b096xPZ0pti9eXh8rukjla07JDo8ZWVx3w2TkQ5NqCAOTUXXjMhYsW7FSOFOtUljqMdJGM4uxHS0qVvvvF9vTXB6Z25nbmduZ'
    '25nbmduZ25nbmduZ25nbmdu/LLfr7Yvn9eEvntd7Xzyvz3TxvF68eH7klmLIqeecfa1oFXNDrc0lt1iVINbX2kuPreiUReOjM9q1'
    '1KofI2GSLOZ2lCOsbsztzO3M7cztzO0fltvTzLnM7cztzO3M7cztzO3M7T8vtxvZzO2XxHbo5Gp2fsD8POB5crtZfMA8MhSyeUP7'
    '0LPJPSHEj9YVprgtqBEpptayDdUj3KMf6VirlPIVmR2V28W+lNvTg8LHmsjcztzO3M7cztz+bXJ7mpmauZ25nbmduZ25nbmduf2r'
    'c3v6pbauk8dLR79OHoVg39w+D3ia3P589ndye8kpI0e15pouaWDo6lZra0WlOJDnQ2jD5452K6VhdW3d+pGa7gorew9xMbej1ULl'
    'u87tjrmduZ25nbmduZ25nbmduZ25/U9uZ2ZnZmdmZ2Z/Y2YXu5nZxRw9s4vdObPjgOfJ7E9nf+/RcQ0jtFc/esJQaTKqQusyXEbx'
    '8mpE01PJXjfV0BGH0lps3ufsffFdDdcWMzumL1IMMzszOzM7MzszOzM7MzszOzM7MzszOzP7npl95uWfnNm1bGZ2ffTr4/GD3zmz'
    '6xNdH/989veuj0fALk1C7iUgJ7pSclVYjDoKG/r8IaYiYrnaFGaxpGyzTtkV74dqoeqyktmdekDcS/7Gfe2WmZ2ZnZmdmZ2ZnZmd'
    'mZ2ZnZmdmZ2ZfSWzM68zr/8dyuN2Xg+Hz+tx77wez5TX4+JD3G3B0PUd4zFj3e8NC3o1dSDvtdrMGFgEc20d60TDeqN988Z3g9De'
    'ME1GXszrWGKVSryfnXmdeZ15nXmdeZ15nXmdeZ15nXmdeX01r2McP2V2F5jbb+Z2JC9lNnP70fehQ+4xu+b2ywHPkttfnP29+9lj'
    'Cy6HbKoZWCsQgTqmKEasy830UpGdkM7j8FnPJ8EV5JaE8Sehxjzft5jbMa3Q/fLaeOZ25nbmduZ25nbmdub23XI7MzszOzM7Mzsz'
    '+y8Vbmf2+ZI/fGYPe2f2cKbMHhYzOxY+9OGmoWGWmFDSkOaCHqVLz6Hk6rL3Ayknt2FdxdDsVveCoI80gQV7KbPLA+IMOhxeG8/M'
    'zszOzM7Mzsy+e2ZnXmdeZ15nXmdeZ17/oXldZDuvh6PndZGd87rIifK6LN7LHoeyzUjrCC+Y1xn9iMlz07mhspeOJdgr35TurmN4'
    'zbvZ82jNplEqpk2si3kdyym60Ou8HpnXmdeZ15nXmdf/La+n+T0wrzOvM68zrzOvM69/h7w+fz6zyf47t2MMJ/zMmN/v5Xe7md+P'
    'vn88so/dO7/bM+X3xf3jUf8QR9ABFKw81pdWWkqhuhJzq6KHljhGEN2LLsgHoSD0qCr4ADW3l3OL+R3LF7rvq/yOwcj8zvzO/M78'
    'zvzO/M78zvzO/M78zvzO/P4V+R2/g5sZfv5eVnL8JYM/Zvk0c/jR8rzevn5eH/76eb339fP6TNfP68Xr59GfDFtyjaUXvCuWYdD6'
    'o6plJBUERz+KyEDHhoZAKqo40n4c2aAGu5Iud1Hcz/P6Ae0pujLm+Y/N8z4wzzPPM88zzzPPM88zzzPPM88zzzPPM88/hnazfX39'
    '47b0R060Zu/r682Zrq83i9fXOwxyb1vquvWahhrFKSdlFOVqaKVH093Agu87qlBxprpWq2oop2Nm/7SY51FSsZJe53neD888zzzP'
    'PM88zzzPPM88/+3yfJqtADM9Mz0z/c/J9D4dOdfL5t708yV98Fwve+9NL2fam15W96ZHbewlSyo9NfTALvXQmjKhj2JGTbqhmY/d'
    'l4ZG3ecaSk2h+T607aaZurbPnXlAHEMl5t/TM9cz1zPXM9cz1zPX75Lrmel/SqZnnmeeZ55nnv+HPL+5Dx7yvD16nt97Hzw50z54'
    'sroPXnZVIaNIRpEYaNalNpfTGArhaJhhvOtVGlZ63VVLqriMqmkzWqBYrM9pMc+jFUIXcp3nDfM88zzzPPM88zzz/BHyfLp8LDM9'
    'Mz0zPTM9Mz0z/XfL9HYz0z/G/UOnWrt3prdnyvSLe+OhF4k1NLTP6EZRpFuPKcwL7UdK0Zeiug2tlmKqajVno2rLWH98blFGsnUx'
    '02P6o0tkpmemZ6ZnpmemP3ymT0GY6ZnpmemZ6ZnpmemZ6b9Npo/bmT4cPtPHvTN9PFOmj4t/T1+tqWYY2yT7UaWYMVJH92VGGjaO'
    'UVIOqRspqOLRFNdtya3ZWlFp7Vj7e3r7gDiSkrvK9PHbZXq/HuvNJdn/FetRVcI70v1XJXv8FB/T/Xayl1nV7qX7NyX7G6keP9WX'
    'yT7N9P+fdB/emfDlXSl/Jvw0U/FM+R+e8P+b7tNM4v+Y8NMlyb895af5/nck/TSPdTft278S/2tpPy4kfv9K6v+CxI+fu8HP/P3J'
    'f/4c01/JX31M+p8V8q/0n2YCviMAj+l/h+T/SupPM4X/J/WvJf40C/JM6rP+2nmOj+n/OfnfT/0JY/4tyT/Nj/3m6T/NpH0RgMf0'
    'n2bqviMACT+3OJP3ThKQ5gI7E/47RSBd/vtHBSgCZxKBNNPqaVVgTxF4RQPuSsAHK8CSAOyb/pn8X0n+evuOe334O+713nfc6zPd'
    'ca8X77ivprY2sOJhQqH/UrFVLIs545/uutMFDXILffgy3NwMH+sXhnppdeBfOuvF5I+2AJ3EdfL3TP5M/kz+TP5M/kz+TP5M/kz+'
    'TP57J3/L9M/0/zHpH+f9GQKQkv9CBdi+pl+bwyvA3tf06zNd068Xr+nXLffSvfjWMRyGqRldNgJX1bGNWlpJ3efsYy8m2qYG+gXE'
    'gtZQb0PzLS4qAIYvEhgVgApABaACUAGoAFQAKgAV4LcCpJlwT6IAaSbxOwqQ5s9mrsFq/oA+iAFwcLnrAPggfRcC8EGGEkAJOJUE'
    'YNDaT6SA7VsBtDs8Bex9K4A+060AevFWAB+HM6mHiLife0Z+iqogKWJhypiU6BVsTcP04acC1Lkrfxiuor9ByYtu7fZ+96AxBi0p'
    'gBRACiAFkAL2pADUB0cLoAXQAmgBtABaAC2AFvABFmDUtgWko1uAUTtbAA54Hgt4Ovt7W/3pUbCIoS9RzetW0AyhSXa1Syyjm5AL'
    'loyYbdZdx6JyF9eczS0MSU1LXrQAl+YXubaAQAugBdACaAG0AFoALYAWQAugBZzUAnAQTxAgCHxbENC/lNsAAbx09N0C0L/vCwLz'
    'gKcBgeezv7dbQMeagr6zF+tKHKUN0aUI6lhEd5tasGUkGUgDsWtXpfmRc4q9y1AYNm0RBFB3EEAJAgQBggBBgCBAEDgGCOCHFygC'
    'FAGKAEWAIkARoAjcEYG4LQLh8CIQ9xaBeCYRWLxdIJjsg8qlYDZK7hWrCeaEycqo4WLOvtrqCqbLUFg4WhXJWVVJffTYcwxLIuAf'
    '0LoiKV2LQKQIUAQoAhQBigBFgCKwnwjgxCJJgCRAEjgSCeADEl2ALnByF5C06QLij+4CknZ2ARzwPC7wdPZ3XMBhNGrVVEPsVGh0'
    'UGibH1jYkNmbKkFqykE1lFNRHVGpZq97GKnrgXampEUXwNzFwkwXoAvQBegCdAG6AF2ALkAXoAvQBegCdIFzucDjQwVvuoCWo7uA'
    '1ju7AA54Hhd4Ovu72wv6gRLeW+xoShH0Swq9oZ20rWTkWxQRlNWWcgxlNFeTa05qi77UhuKzdgdBeEBIU7eeNEAXoAt8lguo2X0R'
    'BggDhAHCAGGAMHBeGMBaJpQBygBlgDLwNTKwfSfB4Z9BqPd+8IA+04MH9OqDB1Di0Y3HOqLLraA/VN235kytLaNSd2SuUn0diD6q'
    'dqNGM3gBq11PJSdJizKAVkMZ/T1lAMs0bYA2QBugDdAGaAO0AdoAbYA2QBugDXxnG9i+m+CRDQ6djve+m0Cf6W4CvXg3AcYPsrwa'
    'yZecFd7C4q50Tqpma3PNJWT0IQXdvUIn3myTXkJNuvYURtJ50QYwT7DQXNuA0AZoA7QB2gBtgDZAG6AN0AYOZwN/TGBXD1i1AOZ/'
    '5n/m/y/K/5sPItTHfxCh3vtBhPpMDyLUqw8iFDuKtJZsNbmhb1atabTviFa5qSQI/xUppaNrRjVtvqfcUk0yXM7oxG1cyv/xAYkI'
    'tf8q/6MqMv8z/zP/M/8z/zP/M/8z/zP//5j8/6bsz9zP3M/c/+G5P/xS8kvd/Hv/x5eOvYtgQIu/69/7Px7wJLn/5dnfe95gyiaj'
    'B/a9WTeCbsgOHSVbJVuLMSr1gCpoq6uhmNIxLpPqNRdtKnobpxdzP1oAdAfM/cz9zP3M/cz9zP3M/cz9zP3M/cz9zP3M/UfK/fqX'
    'Mhu5Hy/pg+d+9Or75v55wNPk/uezv5f7Cwp7sXoMVZE3Y8ZiOqrYUi2CfnZFGSfVteLNyLE2r9uoyBgS2ih5pMXcj2UtMfcz9zP3'
    'M/cz9zP3M/cz939q7kftNwz+DP4M/scO/hjWlsn/65N/3E7+4fDJP+6d/OOZkv/iLoBZhayw/JcYGlZWFUZROnb03CqmWnpq0jwK'
    'ZPfNe9XQmmmp2YvvOWIRHUvJPz0YNKvhOvmj9DD5M/kz+TP5M/kz+TP5M/kz+TP5M/kz+a8kf3ywY/z/sPgv6sTxX9TO8V/UieK/'
    'LN7oX2tD45yyDVWbgkW3I5/o1ju6JWWNqzO3KxSiivWvtdJS6qkPpNDcO/LVYvxHXUXj8Hf8nwN0//jv3iwAKCP+wgDvMAB8brgN'
    'AXgr/kUBckMD8GHpQgLqVRV4IgFRlz57/lf+GQfUFIAjCIHCF3kiAjW/2oITyCx+K1ag5rf+BwyU3laDm2KAzwj/ZQM1T/8f7QAH'
    'SXcBAb9Q9awIc7C/UxJwIFniBHygvjIFvNNcYAF/sF+qC/gG3IcTA76IvzgD/hCesAFvvC4O+ID0JnbAVMUHzQp1wx/w4jzdOWnU'
    '7CgWKQIfbI/hEWZG4UWTwHe9P0z8QYktkMAX9ZsqgRfDh9DES5bAF4n/sQm8I70NKFDq1UUp8Ic5XuZXnP1dUh9mFvgiW3CxhhY4'
    'gP06uXipFvhO3IfSBb6Af5Nf4BPCK4hxyQDfVTJweuSM78gZ8mbS+GjOQHd8+deccPPLfoBu4MCzDicyx9GZw20yh9jDM4fbmznc'
    'mZjDrTEHyhXW0OKzaSpnzNTU2lCm6Hx5wmG1VUmxxeZaoq6m9ab0QODNcWgzwsK+BuZ/Sj0oTHVF5iBzkDnIHGQOMsd5mAN11NI5'
    '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'
    'IErQuSXIXkb2Xxz0+Cea0IoJpd+7Ot8wIfxz9NvEktrvNrF5rNOY0POJ3zEhNeZqWk2sQUbtzmc0P8ohmpbWKiZ7bTW2mobybWBC'
    '+xLqUBWTNavqoyyaEA4Y7fVj2k2kCdGEaEI0IZoQTYgmRBOiCdGEaEI0IZrQzzChy06fhKEzwpCkTRiSo18shDGwHwzJiS4Wej7x'
    'OzA0JDfXw+jFqawkjlKdwlutu1BdzQPTTFK1rbmGkOqiiWgiU+upDRWqXYQhdKVocq9hKBGGCEOEIcIQYYgwRBgiDBGGCEOEIcIQ'
    'YegHwVBw1KGT6tDmpkLp+JsKpR03FUpn2lQorW4qFIctY+hYSre9tjYm/qieVS6p9G6KZKy5XY/Q6gioUjaUljr6Ao+lJaklHTIP'
    'WMKwgF3pEJYX6hB1iDpEHaIOUYeoQ9Qh6hB1iDpEHaIOUYde1yF7+dIkoq8nIqNOTERG7UdEONZ5iOjpxO8QkQ015eA76kBDilQd'
    '3Y9JI2Sda3WxqYaa22xBVMVn2JJNGNmiVtiei/JlkYiwyqN+XxORkIhIRCQiEhGJiEREIjoPET2OPjoRnYhORCeiE9GJ6EQ/2IkQ'
    '91W87URPLx2XS2YfspcTXY51Fid6ceL3LiWyOUspzcbR0HJEWxUW4tK8yXmY0DF6bKoqZtNQz6prvqAV8kF3nWWUtV2p7QMO6q3j'
    'pUR0IjoRnYhORCeiE9GJ6ER0IjrRhzgRjYhGRCOiEX2SEaUzG1Ha0YjSmYxocTMiNzAIbHV1NEQgk6vzBXXYDqyoKBn2clOZLVY1'
    'aTW3qkxPflQ1MARR18eiESEbJa9oRDQiGhGNiEZEI6IR0YhoRDQiGtE/GpFcygqRiEhEJPqhSITvNn2xEmnZVCI5vBJp2U+JcKzz'
    'KNHTid9Rou6Kk1D0aEg+VlWjRhpuhIaaYlQ2WTyWOskIh5iPrRXnesb898Om2KtbVCKUHnvjWWZUIioRlYhKRCWiElGJqERUIirR'
    't1Ki2YpQiahEVKK9lSgKlehISmQ3lUibwyuR3VGJ7JmUyK4pkZSAaq6wnGgzsmlZNy1dmskYdNHo6tCctqRrSao03WIq9v/s3Ql2'
    '27qyBdARxQt982YDoFDzH8I7pG+cRmJEO3RM2uet/PzElBlTAqrZlwTMxC+VYsbct+N9fEKHhzB8q0SOSkQlohJRiahEVCIqEZWI'
    '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'
    'l1S4YcM2wIz9Wzz9RQ7D9nnpFz6UGW43Q5QZdP8CifqRpL6nJsrMRiRFkuJbSFFmxPmLKz6Sor7Big4/9+0rfTFfPMgWMbJ5D2DE'
    'ZR+ujBjT/0KNeHv9vjfiOwuvB0eZlPXp6jhzdNwy+XfXx62B+StBimzV/Lkdcnvj3oiReC/SW0XSkSVPwpLid1lS3NlZUvxxLImx'
    'rsOSTxd+9zASdF6jR2uLVSVKQU7LkxyQdkexVtlcWjUoLmS0VuvQubqUWxl1NNfyIktGlMgq3GDJQJYkS5IlyZJkSbIkWZIsSZYk'
    'S5IlyZIvWVJmIUabpE3SJu/YpGztCoGSQHkhoJRtjH9TSvND7d08iZfMyZUSyfgwpZxjXUYpny/8jlKKcaVar12OOmvJxWZnep5F'
    'L4pDP1AEhTJyN/Nmyt5TjjV6l6odNbvUx5JSpgdjUECnG0rpqZRUSiollZJKSaWkUlIpqZRUSiollZJKeV6lpFBSKCmUFMqTCKU2'
    'u0Kp5exCqc1xQomxriOUTxd+7/Hu7ksK0iWLKcoVzDztWy+6Ic1hIuXhPSaca5gd1dTUh8UnDXR5KfZW1KJQhhkTPO+jpFBSKCmU'
    'FEoKJYWSQkmhpFBSKL+BUMojJpApyZRkSjIlmZJMeThThn2mtKdnynAgU4YrMWVYvJHSd9fQjNXQAoqgilWMhkjHHGqutmBKto4m'
    'M+bW+qhDtxxNwTrr2hSt89JJNFo96FmIm2/NlLKhBJmSTEmmvMeU2xtMpiRTkinJlGRKMiWZkkxJpiRTkinJlGRKMuVLphS9y5Si'
    'zs6Uoo9jSox1HaZ8uvA7TDl0G6mlUEasbhpB97O2cxnNNMJmz7PziVKa6dJSy6oazLNuvBtBVI+LTImEKsneYEpHpiRTkinJlKdj'
    'SpHNIuiUdEo65Zd2SholjZJGSaOkUdIoaZQ0yhMaJX1y3yf396N8pMtTM92B+1HKlfajlMX9KHMMJbYxayndQ5SG2K26QVnXWlJN'
    'im+5orBVUk2ZdomeqWSnMV1Qn9iw6JOYrmggXvokYgt9kj5Jn6RP0ifpk/RJ+iR9kj5Jn6RP0ifpk7/7JH784SdSymPE2dqqmVGS'
    'umuWW3JJ2z/N92ybWMl9VcyUrdTbmo7ZdeCXdALglFkRySxvZKY6mY2QmMcfPOWT8nky+Yz78hlOL5/xQPmMV5LPuCafFTWaVXFg'
    'TeTqZcReMYfQZPcgTWJRLSOVtjpUqCFlq7JJJY0WW5Heo12ST/0ww4u98QA5sjflk/JJ+aR8Uj4pn5RPyiflk/JJ+aR87sknVpEj'
    'f5I/yZ/kT/In+fOd+dP85cH0eHb+NAc+mG6u9GC6WXww3Q1fbSoR1ZAOuaAI0z7XmNFmFOQOG0pBFZ6woOZWmiaZlkKO0TtXc8ri'
    'F/nTzyQWb/An988kf5I/yZ/kT/In+ZP8Sf4kf5I/vzJ/mjm9XmWgkzhlq5KoodRQaig1lBpKDf0MDbU/1N5pQnjJnFxDrTruNKE5'
    '1mU09PnC72goFjbCCoqnNDMj6hOUUAMZuGP96VBjQwIJ1aC2DcX64oPv1rcUcy++6qoWNRQJF0X2DQ2N1FBqKDWUGkoNpYZSQ6mh'
    '1FBqKDWUGvoKDU0kUZIoSZQkShIliX4IiaZ9Eo2nJ9F0IImmK5FoWiPRkptpZVTMp2pRsjjrulKt5jZ019VnjxBRglNq+wUfiiFV'
    'i9UYQq46LZGoPKABQgFPEiWJkkRJoiRRkugXJ9GtSyGJkkRJoiRRkihJlCRKEiWJkkRJotcnUdkn0dM/M4/m+TgSlSuRqCySKKab'
    '2FYR13T3vbcgvdWmS88lZIPOuQ90w9XolnJBBLHJ9VCSbUXrkVpYJFGP4lg5kihJ9BaJGk0TpYnSRGmiNFGaKE2UJkoTpYnSRGmi'
    'NFGaKE2UJnoyEzXqwiZq1HEmirGuY6JPF37HRE2sThdXzEBuyegfc28jNPSaCHA+VxdbryGnkX2qpnU9bOyzP0JBPJxqiyaKTt7c'
    'PEaJJkoTpYnSRGmiNFGaKE10x0TFbBGHJkoTpYnSRGmiNFGaKE2UJkoT/XgTxd9yXRNFN3eYic6xLmOizxd+7z5Rm4b3SPpZJd1G'
    'qqPM6d4RYVBRhdgGqrue/KipZyT9kJG9eynVlYowMpZM1DxYNc9joonSRGmiNFGaKE30pYnKnPQ0UZooTZQmShOlidJEaaI0UZoo'
    'TZQmejITjTsm6n4evnRqGowHmmi8konGNRP1WGGxqeCybWi4XM4N8Xa0ipdbLkiP2jVTu8mmhYqooDIazYEQPZpxIy2aaEDdeHM7'
    '0UQTpYnSRGmiNFGaKE2UJkoTpYnSRGmit03UbP01YZQwShgljBJGCaOfCKPpyjCaDoTRdCUYXdxUdPhma0Tt0G1LdSDQZIXUV8SP'
    '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'
    'S4GlwFJgKbAUWArsq8xq9N0Ca87+CFUZqo8rsOZCj1D9/sYfPSCgql6abMtkt127NVVmoW57DnUMWfGnmors1WTACkUWG63JdNXD'
    'KCu+2GZz2Vlgo1057XWBlVuUAkuBpcBSYCmwFFgKLAWWAkuBpcBSYH8tsHb7af+XDGu3a4gWS4ulxV68xdq1cLDbwoEqS5Wlyu6p'
    'svl+lU2nr7L5wCqbr1Rl874q60ofMmHKtDp7LKFN52SUnU2nFrUr1cYeZ+wypPQebJebrSfXm8nFFlk22V1V1j0pGTHCrSrrqbJU'
    'WaosVZYqS5WlylJlqbJUWars162ydntQNGmWNEua/VppNtFn6bP02bf12fxN/ea7ZvPJ+2xWx33X7Hqty/TZ72/80XfNys2fiqy+'
    'YjVzzNxUCaa2IRv+1LUveaTg1kladV0fpsuOLwz5Xz2clW1Y3dlnnazHYqDP0mfps/RZ+ix9lj5Ln6XP0mcP6rPyb5Pps/RZ+ix9'
    '9kv3WVl5KvosfZY++1X6rLlynzUH9llzpT5r9vXZpuuUmX3EUUuUMTKqHGpUabTQsuu96lC7DVWrkmtVPfhiVS1TD19G7H1nn40y'
    'bydNn6XP0mfps/RZ+ix9lj5Ln6XP0mfps/RZ+ix9lj5Ln/2DPmu3sEef/bJ99t7zDeRD6fR9Nh/YZ/OV+uze5xuoIeuoUmRbHEyY'
    'Pdooi4Kmdcuu2T5k7pG1vu05l+BtHjIeyia0jVZqz37kXX3WP8mgmG72Wc79os/SZ+mz9Fn6LH2WPkufpc/SZ79In7XRXCXSbiMN'
    'pZZSS6l9x1JrtyL19lwbPc2WZkuz/S/Man+32Wpz9mar/XHNVl7rOs325Y0/aLaymp6+jjxU7kUGDjVl21bi1LHOJLdBTzIgymTc'
    'Y+yqD1k+2FKc/G+Wf8q4uLPZerlzkqfZ0mxptjRbmi3NlmZLs6XZ0mxptoc1W7Oma5otzZZmS7Ol2dJsabZftNmacLfZGn/2ZmvC'
    'cc1WXus6zfbljT9otl5Na5uqrjc9vB9RVa1rGkF2GDXH2WXGHiMP42v1cUbXRpCb3JcaZix97Gy2sgqQ8fh1s408B4FmS7Ol2dJs'
    'abY0W5otzZZmS7Ol2Z612Zq1HJJ/JOot9ZZ6e+J6u4ZVu93KdFw67qfpuHa7zP+u6N5/csJz7D112DzwyQnmSk9OMDufnOC7bsF1'
    'lXtsSf6PL7FWP3Mpo8stJ2N5dj01GXZS0UWl2VLMU2ZXmadjaWVX0Q1Pcl/LlXqj6AaKLkWXokvRpehSdCm6FF2KLkX3Uxdd+axY'
    'iu7RRdcmsi5Zl6xL1iXrknXJug+zrlX3s+7pDyyz6risK691naz78sYfZN1QbBm959HLGM60IXdNlom/zVZbk21lkhl7TLle9JSh'
    'LdQgt2SpWX6nNrX2nVlXNpvR2BtZl4crkHXJumRdsi5Zl6xL1iXrknXJumTdj8m6dnvRW203BQIvgZfAe5nAa7f3QuWl8lJ5H1Ve'
    'rb5pd7vyrg/Zc1deWeK6oyrv9lpXqbw/vPEHlbcGmTNXWZnTJFdkiFajV92L7KvzkAFgZN9luvOq59iG6qEr1VtN8p+MfGBn5ZW5'
    'Ime+eZfKS+Wl8lJ5qbxUXiovlZfKe/nKS+Al8BJ4CbxfI/DSdmm7tN3dbffMWTfcz7r+9Fk3HJh1w5Wy7s6n7PaSdavGjya7SqWm'
    'k/G9NLnPmlx6arQwgxpq5hZUk1WOHnoNEmotP3pRve3KuvFprem9eZ115cok65J1ybpkXbIuWZesS9Yl65J1ybpk3R+yrt3G73Te'
    'wJsVlZfKe1TltVu+IfW+Z+pdn1N6L733U/ReuyWIQ6NvvB99w+mjbzww+sYrRd+483t5ZXPXq4w2OrbuYiq2uyHTmwy/MjP53oJr'
    'vo02iwtWD6OqXME1ra2bdmX7Zu490Vemtews0ZfoS/Ql+hJ9ib5EX6Iv0Zfo+0+jr1lTE9GX6Ev0JfoSfYm+RF+iL9H3dfQ15m70'
    'Nfrs0deY46KvvNZ1ou/LG3/0nb7Jqiq71xK6TLI+9SkbnbYew6uca6n3qecqtrKn7qFk1WILszu9frn1reDuib6ycpcNMdGX6Ev0'
    'JfoSfYm+RF+iL9GX6Ev0JfoSfT9h9JXPiif6En2JvkRfou/Vou/97/Q17vTR98Dv9DVX+k5fs/M7fYdqsqjLvtoeug91zhR607HK'
    'CKarrA/jlC1ckwlguKKmjDQyl8sFrprtMkP5XdE3PRm5tvWtxzt4oi/Rl+hL9CX6En2JvkRfoi/Rl+hL9D1Z9N1qFOWX8kv5vXr5'
    'zZH8S/79Gvk3p0MasNV3G7BVZ2/AVh/XgOW1rtOAX974gwY8U1d99tFlfJw9jFlij0YXGWZajl0+GuXalZvPlBL9yKrKqBZcmmFU'
    'q/rY2YBD9HLb0oBpwDRgGjANmAZMA6YB04BpwHcasN3qzsc2YKcUDZgGTAOmAdOAacA0YBrwl2zA+pu6/33A9uwPf5AL87AGvF7r'
    'Mg34+xt/0ICjLrKV9HLtdGNK8NkMN5xu3lfZD8i07MbspaUgt2gr8odaH7rmluuUSbaEnQ04y80U3I0GHGjANGAaMA2YBkwDpgHT'
    'gNdOySlCMCGYEEwIJgQTggnBhGBCMCGYEPyxIVi7OyFYPnT2bwaWpehxIVhe6zoh+OWNPwjBZo5oQ1Gxq9a9aevRv6ENl3s3efgp'
    'v1yGcbLJM+v7eafTroxeVvdzzul93wycn2QLGYJ6FYLXwH9YCF4z/K81WP0XhOOvTVhutLCF4XjJNmy3MPljIP6nlTi8uRTLl8fe'
    'KcVa/0ku/oNUrLdtxQG9WK896V9F4+0vvVuO9bvWY7PK7I6E7Ladzu6OLF/q/LuYvJXfuC20dPo5K8tfFX5py/JL8Y8D8y9t+X5W'
    'NtufuNOWw/rwjch8usCct1vxVWQ2Tj6PW2neUstf5eaDSrP8K+nvudlvy6n/krNe/ddvV8O2QXxLfI5rTPypQOt12dzP0Ga99ze1'
    'aL1Gvo8K0nErZG+r0noN9P8sTe+r0n8WpOU22gqyeZim31KlX4K020KQ324Y/5s0bZ9rx50+7baStP6Y0/F1qf4vUrsVptx2BW5b'
    '722TodWNcL01gjv12qxBbCVs+Q9rgltX7K2YrdcET9GmaH/1om3ctoT+46y9NQ3S9p20ve1LbvTtsGbuh5F7XSlvDt17I7dew+x7'
    'lu51IW9H3cVtH5K3MTncDt/rr/4vfpu1/twKuFkL0F8y+KEFfAtbbkuI91O4ex5RH/bwuLYh54/i8n4o4x9RxuUCSZ+gjCu3fXHS'
    'D43crOvwX4fybTVBLb9KLTf6fi2PZ6/l5rhHZ6zXuk4tNzsfnTGKTKCyl5hya8k6uNeo/Wy1yUo/urYemdyGLOl7itXYJpsF2a6m'
    'bnqVMWiOonfWclmTh+xv1PJELaeWU8up5dRyavnnrOVXKuXb1U8uJ5eTy8nl5HJyObmcXE4uJ5eTy98/l8vLO5r5p2jm6W4zN+dv'
    '5unAZp6u1MzTzu8wT3KJhCKr+5JmGbPb3meLPejWppe7u8t0UuyIeYQ5pszSsfgsv6+72pvKe5q5VU9r4MyvHze9lns0c5o5zZxm'
    'TjOnmdPMaeY0c5o5zZxmTjP/V818Wwj/Es6fVz82ktBJ6CT0L5rQ3baTpqPT0b96R3fP0/VfxnTzTdk7MV0+ZE4e02UKOCymr9e6'
    'TEz//sYfxfQQgpsm9S6X2VizQGp6VjenbOm9r7IsDa7r3Lwr2bQ5oq6zR1fT1KorvzOmB1lZhXAjpjtiOjGdmE5MJ6YT04npxHRi'
    'OjGdmP4wphvnFEWdok5Rp6hT1CnqFHWKOkX9IkXd3S/q9vRF3R1Y1N2VivrOB6A32cRVG2vqsao6bWkzWxk5RncuxiHL6lq8rb7F'
    'amKtTVY0qfoxZLVeeuy7TsK0+knuXll0U9Qp6hR1ijpFnaJOUaeoU9Qp6hR1ijpFnaJOUf9tUTfbwpOiTlGnqFPUKepXLurP54be'
    'Lur57EVdq+OKurzWdYr6yxt/UNS7r67Lfrc0Iwt+mci6q7LfLfKfQ4uxlthtGbIYb62H0mJ1TfU6TE9TNg0x7yzqskGQrScPfKGo'
    'U9Qp6hR1ijpFnaJOUaeoU9Qp6hR1ijpFnaJOUaeoU9QPKerE9HPGdH03pj939lM3ZX1gTNdXiuk7TxyVyzOqHLvqLZhqemmypllJ'
    'ocv01n2VYa54We9Z17ovXRUzWitZjRJcKmnujOlRlvjxxomjclMT04npxPTPG9NlG2Co6dR0ajo1nZp+spoug7MlqX/WpO6224eu'
    'Tlenq9PV6eon6OrbjoG4Tlwnrh8Q1+V2Cp+gsPv7hf30j1TX/sDC7q9U2P2+wp5ClSWpHzIoxi7r+GRDn8UOGTKiMV1unxSmblPG'
    '1RG0bmueHLWWZGcd8ku7Crt5Wt1D6xuFPVDYKewUdgo7hZ3CTmGnsFPYKewUdgo7hZ3CTmH/WoWduE5cJ64T179OXDfmflw//bNg'
    'jDkurstrXSeuv7zxR8+C0U25sRZLroWZ/ChD1yIzYpWl4hxyeza5VHvIRe5b3UeWYd/5IXvl6nsYcWdcd7L79Jm4TlwnrhPXievE'
    'deL63rhu1uxGXCeuE9eJ68R14jpxnbhOXCeuE9eJ68T1a8f1+0eXmtMfXWoOPLrUXOnoUrPz6FI7+mhGddtlPWpVaUM26i2lMEfs'
    'vckHo2ozxNKdlv8+W+1NOZkxulzvvuadcT2FINPUjbiuievEdeI6cZ24TlwnrhPXievE9Ttx/YJd/SWpn66m/xzSaeg0dBo6DZ2G'
    'TkOnodPQaehHNfTwTen/nUj6a0N//tC5n/4SlCzqDmroz691kYb+4xt/0NBjainNrqvcqi1MWX9PH6eSkSdMGZdydz2NUL1uMRZZ'
    '/s9euqnV9+ZNkXtnV0O3T+uytre+Qd3Q0GnoNHQaOg2dhv4pGrpZ1wIhnZBOSCekE9IJ6YR0QjohnZBOSCekE9K/bkjX7m5I1/bs'
    'IV2740K6dhcK6XrnN6ObVlUzrehaZMpIfrpQZCqUpbqsIH2LsoQpctcV+X9yb5s6a5VdXJo9yVLFt7AzpPu1uQ+EdEI6IZ2QTkgn'
    'pBPSCekfF9LdepuEdEI6IZ2QTkgnpBPSCemEdEI6IZ2Q/l4h3d8P6e70Id0fGNL9lUL6zvNI3XA1BBkhS3Qj9iq7+aHkV6Jqq9zU'
    'HL1vynfv+3Rr+Os5mmF6VzOX6d3OkC7LfFnq3gjpjpBOSCekE9LfIaTT0GnoNHQaOg2dhv5lG7osfhQNnYZOQ6eh09C/YEN3zzmX'
    'kE5Iv35IN25bnL1vTXfrU/eeSd2o+0k9nz2pG3VcUpfXuk5Sf3njD5K6fNVlnBu29CZbM1Vlqx6nT3WW2U0atTtdwqixBVflN9aS'
    'h64uyK53yp4z7vvedPe0hnhtSOokdZI6SZ2kTlInqZPUSeokdZI6SZ2kTlInqb8tqbutEpPUSeokdZI6Sf1SST3dTeomnj6ppwOT'
    'erpSUk87k3oKvci9EfIsrcg2VK/nv8ieVD7uW5c7RAYrO6oP1Vbl+irwfYYpF1CfchXvTOqyZJKV6o2kHh4mdYI6QZ2gTlAnqBPU'
    'CeoEdYL6ewV1s91GVPVrV3UfSOukddI6aZ20Tlr/Omld3mCkr9/o6++Z1s22E6Kv/01fv38u6XN6P3VmPvBcUnOlc0nNznNJXamy'
    'WuqzyuUew1TyP16F5obcIKZXL3OeXPupuhprkGFW5v5RZCSLrim5HtvOvp5lw+FvPAVGbgX6On2dvk5fp6/T1+nr9HX6On2dvv61'
    '+rpx/jeR3W1bbkr7e5Z2FzS5ndxObj9VbjfbpE9zp7nT3L9Sc7f3HxNjTv+YGHvgY2LslR4TY3c+JkY13+Q3y/YguNKrqV3W2bLh'
    'LFVWINW2NUPKyO+7zD4ypsdRy6h+GFu7td3GXc3dP8nGSCbJG83d0txp7jR3mjvNneZOc6e509wv39xlvWgJ74R3wjvhnfBOeCe8'
    'E96vEt7N2qFR39+tvptt5CTBvyHBm28q3Enw8iF/8gQvl8RhCX691mUS/Pc3/iDB1+hHb7J6rVn5OtUoPYeufTetJBtbmqbZqkbt'
    'XTYIfUQzZ8+1ySwzogydOxN8WDOtupHgeawMCZ4ET4InwZPgSfAkeBI8CZ4ET4Inwe9N8O65ttDh6fB0eDr8MR3ebeMTMZ4YT4z/'
    'oxi/hs33KvJa3S/yZ/+meLl4jyvy+kLfFP/9jT8o8rmMUFLswXW56nuLw1SZcvSobpa4yo4dfZgZuptDFvq5yOAV+hhO11K03VXk'
    'w5NSWVY6N4q8p8hT5CnyFHmKPEWeIk+Rp8hT5CnyFHmKPEWeIk+Rp8hT5Cnyr4s8Mf5Lxnh7N8Y/d/pTN2l7YIy3V4rxdl+MT9Wo'
    'PnXqOrSmlEwoPTdVe7bVDtlhNFNmrlEV57vLaoSewigqzRmKDK5lZ4yXrb699e3x6fAYf3SJV/pjcvzhJX4NwHdrfLZ/meSfM/xL'
    'lw//oMebj2zybk04/yDM34/yRm8JUd7RO+d5s2rN2lW8dPrnRP8wz6/d9O/y/O4y/ydRXq9V/X9l/pcoL/eC+uMyf6Uo/y49fmX2'
    'I6P83/T4s2T4bbv071u8/MOeIMjrVfX+XZVfm6u/SfO3qrzb1sI/p/nvVf57kP99i/8lw7ttuIvhf0HebanK/ybNuzWBvK3Py5/J'
    'z5HerHv7pdSblQV+zvXyS+al2Zvt3n/+VKyL/MeEb9z257bh6SXmb78SP2nN/y/kmzXCUfOp+UfWfPW66MfnxTdV/w+r/o2g/7aW'
    'L6+wjZF5d9V/npffoewbt4XBfXnfbOutHY1/7S3+MvTL3xqOrf1vLf1rOfn73G+2lea/bf5uu+Ifh39H/f+o+r8j/MvX1/4a/o17'
    '/m7Cy4b/I5v/tlv7g/BP87988zf3vwFfm7M3f3PgN+CbK30Dvtn5Dfh9qC6rSrkAU8u5T9lpTZlLw5xeFu2qyDXfZWocVs0mc9hc'
    'O4qyJjcl2++h9zZ/WUrJnHSj+UeaP82f5k/zp/nT/Gn+NH+aP82f5k/zp/nT/P+s+Ru3IvsnDP/bPof6T/2n/lP/qf/U/39R/+Pd'
    '+m/c6et/PLD+xyvV/7iv/svSP8j0olsMdchCaIxgZRHg1ezD2Ckj/bpBZIAOQcfmqvwz19H0MCMO2eftqv/xSYYOuTRv1P/8sfXf'
    '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'
)

def run_lockup_backtest():
    import io
    import matplotlib.pyplot as plt
    plt.close("all")
    try:
        from IPython.display import display, FileLink, HTML
        from IPython import get_ipython
        if get_ipython() is not None:
            get_ipython().run_line_magic("matplotlib", "inline")
    except ImportError:
        def display(value):
            print(value.to_string(index=False) if isinstance(value,pd.DataFrame) else value)
        FileLink = None
        HTML = None

    embedded = _read_embedded_inputs()
    def data_file(name):
        return pd.read_csv(io.StringIO(embedded[name]))
    manifest = json.loads(embedded["input_manifest.json"])
    CFG = Settings(asof=AS_OF, day_basis=DAY_BASIS, anchor=T0_CONVENTION,
                   borrow_rate=0.0, fee_bps_per_leg=0.0, require_complete_30=False)
    strategies = make_strategies(EXTENDED_COMBINATIONS)
    BASE = Path.cwd()
    run_id = pd.Timestamp.now(tz="UTC").strftime("%Y%m%d_%H%M%S_%f")
    OUTPUT = BASE / OUTPUT_ROOT / run_id
    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.max_columns", 18)
    pd.set_option("display.max_colwidth", 65)
    pd.set_option("display.max_rows", 60)
    market_ready = False

    def show_returns(frame):
        view=frame.copy()
        for col in {"mean_gross","median_issuer_gross","win_rate","worst_event","gross_return",
                    "ci_low","ci_high","benchmark_return","short_plus_hsi_return"}.intersection(view.columns):
            view[col]=view[col].map(lambda x:f"{x:+.2%}" if pd.notna(x) else "Unavailable")
        display(view)

    def heading(title):
        if HTML is not None:
            display(HTML("<h3 style='color:#24282b;border-bottom:2px solid #cb2125;padding-bottom:6px'>"+title+"</h3>"))
        else:
            print("\n"+title)

    heading("HK IPO lock-up backtest")
    print("PRICE SOURCE: Bloomberg Desktop API only. Gross short price returns; no assumed costs.")
    print("INPUT: embedded snapshot of your workbook, 451 rows / 448 tickers / 804 date entries.")
    print("OFFSETS:", DAY_BASIS, "| One month = 21 sessions in session mode. Cutoff:", AS_OF)
    print("T0:", "Last HK session on/before the filed last day locked." if CFG.anchor=="last_locked" else "First HK session strictly after the filed last day locked.")
    print("Date confirmation: 13 dates across 8 issuers freshly checked; other accepted dates reuse the 17 October 2026 primary review.")
    print("Your v2 includes supplied historical dates regardless of review status; HKEX eligibility does not validate a lock-up date.")
    print("Gross return = (entry - exit) / entry. Positive means a profitable short; losses can exceed 100%.")
    print("OUTPUT FOLDER:", OUTPUT.resolve())

    heading('Strategies')
    display(pd.DataFrame([{"Strategy":s.key,"Entry and exit":s.label_for(CFG.day_basis)} for s in strategies]))

    heading('Date validation')
    if WORKBOOK_PATH is None:
        inputs = data_file("input_events.csv")
        input_issues = data_file("input_issues.csv")
        input_hash = manifest["input_sha256"]
    else:
        inputs, input_issues = read_workbook(Path(WORKBOOK_PATH))
        input_hash = hashlib.sha256(Path(WORKBOOK_PATH).read_bytes()).hexdigest()
    review = data_file("event_review.csv")
    audit, eligible = select_events(inputs, review, CFG)
    display(audit.status.value_counts().rename_axis("Date review").reset_index(name="Count"))
    if not input_issues.empty:
        display(input_issues)
    sample = data_file("sample_date_review.csv")
    display(sample[["source_row","ticker","input_date","last_day_locked","category","review_note","source_url","source_page"]])
    audit.to_csv(OUTPUT / "input_audit.csv", index=False)
    input_issues.to_csv(OUTPUT / "input_issues.csv", index=False)
    print(f"{len(inputs):,} supplied date entries; {len(eligible):,} historical events admitted by your v2 rules.")
    print("Requested trade endpoints still need to pass the price checks.")

    print("Holder categories and existing source reviews remain in the input audit.")

    heading('Bloomberg prices')
    market_ready = False
    try:
        if eligible.empty:
            raise RuntimeError("No confirmed historical cornerstone dates are eligible. Review the input audit first.")
        if importlib.util.find_spec("blpapi") is None:
            print("Installing Bloomberg's official SDK in this kernel ...")
            subprocess.check_call([sys.executable,"-m","pip","install",
                "--index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/","blpapi"])
            importlib.invalidate_caches()
        prices, sessions, benchmark, provider_errors = download_bloomberg(
            eligible, CFG, BASE / OUTPUT_ROOT / "bloomberg_cache", refresh=REFRESH_BLOOMBERG)
        if prices.empty:
            raise RuntimeError("Bloomberg returned no usable stock prices; inspect the provider errors.")
        market_ready = True
    except (RuntimeError, ImportError, OSError, TimeoutError, subprocess.CalledProcessError) as exc:
        print("BLOOMBERG DATA UNAVAILABLE:", str(exc))
        print("Log in to Bloomberg on an entitled Desktop API workstation and run this notebook there.")
        print("If package installation is blocked, use the IT-approved blpapi installation in this kernel.")
        print("No price backtest was produced. No substitute provider or old report was used.")
        (OUTPUT / "connection_status.txt").write_text("Bloomberg unavailable: " + str(exc), encoding="utf-8")
    except ValueError as exc:
        print("DATA VALIDATION FAILED:", str(exc))
        print("No backtest was produced. Review the returned data and calendar before rerunning.")
        (OUTPUT / "connection_status.txt").write_text("Data validation failed: " + str(exc), encoding="utf-8")
    if market_ready:
        source_description = "Bloomberg Desktop API / exact-request Bloomberg cache"
        prices.to_csv(OUTPUT / "prices_used.csv", index=False)
        pd.DataFrame({"date":sessions}).to_csv(OUTPUT / "sessions_used.csv", index=False)
        benchmark.to_csv(OUTPUT / "benchmark_used.csv", index=False)
        provider_errors.to_csv(OUTPUT / "provider_errors.csv", index=False)
        print(f"Bloomberg: {len(prices):,} stock observations, {prices.ticker.nunique()} tickers, {len(sessions):,} market sessions.")
        print("Actual price date range:", prices.date.min(), "to", prices.date.max())
        if not provider_errors.empty:
            display(provider_errors)

    heading('HKEX short-sale eligibility one month before T0')
    hkex_metadata = {}
    if market_ready:
        try:
            audit, hkex_metadata = check_hkex_shortability(
                audit, sessions, CFG, BASE / OUTPUT_ROOT / "hkex_cache", OUTPUT)
        except HKEXCheckError as exc:
            print('HKEX CHECK NOT COMPLETE:',str(exc))
            print('No final Excel or backtest report was exported. Resolve the specific data issue and rerun.')
            (OUTPUT / 'hkex_check_status.txt').write_text(str(exc),encoding='utf-8')
            if exc.audit is not None:
                audit=exc.audit
                failed=audit[historical_hkex_rows(audit,CFG) & audit.hkex_check_reason.ne('')]
                display(failed[['ticker','last_day_locked','hkex_check_date','hkex_source_url','hkex_check_reason']].head(20))
            return {'output_folder':OUTPUT,'audit':audit,'market_ready':True,'report_ready':False,
                    'short_selling_checks':None,'trades':None,'summary':None}
        checks = audit[['ticker','name','input_date','last_day_locked'] + HKEX_COLUMNS].copy()
        checks.to_csv(OUTPUT / 'hkex_short_selling_checks.csv',index=False)
        audit.to_csv(OUTPUT / 'input_audit.csv',index=False)
        print('SOURCE: official HKEX historical designated-security CSVs. Check = T0 minus 21 HK sessions.')
        print('Yes/No means exchange eligibility at that date. Borrow/locate is untested. Returns remain unfiltered.')
        display(checks.drop_duplicates(['ticker','last_day_locked']).hkex_eligible_tminus21
                .value_counts().reindex(['Yes','No'],fill_value=0)
                .rename_axis('HKEX eligible at T−21').reset_index(name='Distinct ticker/events'))
        display(checks[['ticker','last_day_locked']+HKEX_COMPACT].head(40))
        print('All historical HKEX checks completed. Source:',hkex_metadata['index_source'])
        print(f"{hkex_metadata['outside_historical_scope']} current/future input rows are outside the historical study; their eligibility cells are blank.")
        print('All supplied rows and source links are in Inputs and hkex_short_selling_checks.csv.')
    else:
        checks = None
        print('Waiting for the Bloomberg HK session calendar; no approximate weekday calendar is substituted.')

    heading('Backtest and coverage')
    if market_ready:
        trades = backtest(eligible, prices, sessions, strategies, CFG, benchmark=benchmark)
        trades = with_hkex_columns(trades, audit)
        summary = summarize(trades, CFG)
        common_summary = summarize(trades, CFG, common_sample=True)
        completed = trades[trades.status.eq("Completed")] if not trades.empty else trades
        completed_ids = set(completed.event_id) if not completed.empty else set()
        admitted = eligible[eligible.event_id.isin(completed_ids)]
        paths = event_paths(admitted, prices, sessions, CFG)
        print(f"Completed: {len(completed):,} event–strategy observations, {len(completed_ids)} events, "
              f"{completed.ticker.nunique() if not completed.empty else 0} issuers.")
        if not summary.empty:
            show_returns(summary[["strategy_label","events","issuers","mean_gross",
                                  "median_issuer_gross","win_rate","worst_event","ci_low","ci_high"]])
        else:
            print("No complete trades. The audit and skip reasons explain the missing coverage.")
        if not trades.empty:
            display(trades.loc[~trades.status.eq("Completed"),"reason"].value_counts()
                    .rename_axis("Skip reason").reset_index(name="Event–strategy rows"))
    else:
        print("Backtest waiting for Bloomberg data.")

    print("Missing prices are never filled or shifted. Your v2 does not require complete ±30-session endpoints.")

    heading('Charts and common sample')
    if market_ready:
        figures = plot_results(summary, trades, paths, OUTPUT / "charts", settings=CFG)
        plt.show()
        if not common_summary.empty:
            print("Common completed cohort across every meaningful strategy:")
            show_returns(common_summary[["strategy_label","events","issuers","mean_gross","win_rate"]])
            best = common_summary.loc[common_summary.mean_gross.idxmax()]
            print(f"Highest mean within this common sample: {best.strategy_label}, {best.mean_gross:+.2%}.")
            print("This is an in-sample comparison, not a tested trading signal.")
        else:
            print("No complete common cohort; available-per-strategy results remain separately labelled.")
    else:
        print("Charts waiting for Bloomberg data.")

    print("Means give each issuer one weight. The bootstrap does not correct calendar clustering or multiple testing.")
    print("Retrospective selection and unverified historical borrow/fills prevent interpreting this as executable net P&L.")

    heading('Individual stock')
    if market_ready:
        if not trades.empty:
            detail = trades[trades.ticker.eq(SELECTED_TICKER)]
            show_returns(detail[["ticker","last_day_locked","t0","hkex_eligible_tminus21","hkex_check_date",
                                 "strategy_label","entry_date","exit_date",
                                 "entry_price","exit_price","gross_return","status","reason"]])
        if not paths.empty and SELECTED_TICKER in set(paths.ticker):
            stock_figure = plot_stocks(paths, [SELECTED_TICKER], page=1)
            stock_figure.savefig(OUTPUT / "charts" / "selected_stock.png", dpi=160, bbox_inches="tight")
            plt.show()
        else:
            print("No admitted price path for this ticker; see its input audit and skip reasons.")
    else:
        print("Individual trades waiting for Bloomberg data.")

    heading('Excel and data exports')
    if market_ready:
        run_metadata = {
            "hkex_short_selling":hkex_metadata,
            "data_source":source_description, "input_sha256":input_hash,
            "review_sha256":hashlib.sha256(embedded["event_review.csv"].encode()).hexdigest(),
            "actual_price_last_date":str(pd.to_datetime(prices.date).max().date()),
            "original_input_dates":len(inputs), "completed_events":len(completed_ids),
            "completed_issuers":int(completed.ticker.nunique()) if not completed.empty else 0,
            "bloomberg_session_established":True,
            "return_basis":"Gross short price P&L / initial notional; no assumed cost deduction",
        }
        export_results(OUTPUT,audit,trades,summary,common_summary,paths,CFG,run_metadata)
        excel_path = export_excel(OUTPUT / "HK_IPO_Lockup_Backtest.xlsx",audit,trades,summary,
                                 common_summary,prices,paths,CFG,run_metadata)
        write_html_report(OUTPUT / "backtest_report.html",audit,trades,summary,common_summary,
                          figures,run_metadata,settings=CFG)
        saved_manifest = json.loads((OUTPUT / "run_manifest.json").read_text())
        saved_manifest["excel_sha256"] = hashlib.sha256(excel_path.read_bytes()).hexdigest()
        (OUTPUT / "run_manifest.json").write_text(json.dumps(saved_manifest,indent=2,default=str))
        print("FINISHED: Excel, HTML, full trade ledger, audit, input prices, charts and hashes saved.")
        for filename in ["HK_IPO_Lockup_Backtest.xlsx","backtest_report.html","trades.csv","input_audit.csv","hkex_short_selling_checks.csv"]:
            file = OUTPUT / filename
            if FileLink is not None:
                display(FileLink(str(file.relative_to(BASE))))
            else:
                print(file.resolve())
    else:
        print("DATE REVIEW COMPLETE; PRICE BACKTEST NOT RUN. Resolve the connection or data issue shown above.")
        print("Input audit:", (OUTPUT / "input_audit.csv").resolve())
        print("Primary date checks and links are displayed above and included in the exported input audit.")

    return {"output_folder":OUTPUT, "audit":audit, "market_ready":market_ready,"report_ready":market_ready,
            "short_selling_checks":checks,
            "trades":trades if market_ready else None, "summary":summary if market_ready else None}


if __name__ == "__main__":
    RESULTS = run_lockup_backtest()
