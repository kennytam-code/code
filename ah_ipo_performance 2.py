"""
A/H performance & premium analysis for China semiconductor A+H listings
=======================================================================

For each name, measures performance of the A line and the H line over
1d / 1w / 2w / 1M / 2M horizons anchored on the H-share IPO date, and
tracks the A/H premium through time.

Definitions used
----------------
t0                 H-share listing date (first day of HK trading).
Base price         Close on t0, for BOTH legs (A and H), so the two legs
                   are directly comparable. The IPO "pop" (t0 close vs
                   offer price) is reported separately as its own column.
Horizons           1d  = t0 + 1 trading day
                   1w  = t0 + 7  calendar days  -> last trading day <= target
                   2w  = t0 + 14 calendar days
                   1M  = t0 + 1 month (calendar)
                   2M  = t0 + 2 months (calendar)
                   Calendar offsets are used so A and H land on the same
                   wall-clock date despite different trading calendars;
                   each leg then resolves to its own last available close.
A/H premium        (P_A_cny * CNYHKD) / P_H_hkd - 1
                   Positive = A trades above H. The reciprocal view
                   (H discount to A) is also reported.

Requirements
------------
    Bloomberg Terminal running and logged in on this machine
    pip install blpapi --index-url https://blpapi.bloomberg.com/repository/releases/python/simple/
    pip install pandas numpy matplotlib python-dateutil openpyxl pyarrow

Usage
-----
    python ah_ipo_performance.py                # pull from Bloomberg, cache, chart
    python ah_ipo_performance.py --offline      # re-chart from cache, no terminal needed
    python ah_ipo_performance.py --field TOT_RETURN_INDEX_GROSS_DVDS   # total return basis
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from matplotlib.backends.backend_pdf import PdfPages

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

OUTDIR = "ah_output"
CACHE = os.path.join(OUTDIR, "px_cache.parquet")

# Bloomberg host/port. Default is the local terminal API.
BBG_HOST, BBG_PORT = "localhost", 8194

# Price field. PX_LAST = clean price. TOT_RETURN_INDEX_GROSS_DVDS = total return.
DEFAULT_FIELD = "PX_LAST"

# FX: CNYHKD Curncy quotes HKD per 1 CNY, so A_hkd = A_cny * CNYHKD.
FX_TICKER = "CNYHKD Curncy"

# Horizon definitions. ("trading_days", n) or ("calendar", relativedelta)
HORIZONS = {
    "1d": ("trading_days", 1),
    "1w": ("calendar", relativedelta(days=7)),
    "2w": ("calendar", relativedelta(days=14)),
    "1M": ("calendar", relativedelta(months=1)),
    "2M": ("calendar", relativedelta(months=2)),
}


@dataclass
class Pair:
    name: str          # display name
    cn_name: str       # chinese name, for reference
    a_tkr: str         # Bloomberg A-share ticker
    h_tkr: str         # Bloomberg H-share ticker
    ipo: str           # H-share listing date, ISO
    offer_px: Optional[float] = None   # H-share offer price, HKD

    @property
    def ipo_date(self) -> pd.Timestamp:
        return pd.Timestamp(self.ipo)


# Verified against each issuer's "H股挂牌并上市交易" announcement.
# Bloomberg HK tickers carry no leading zeros: 0501.HK -> "501 HK Equity".
PAIRS: List[Pair] = [
    Pair("CFMEE",        "芯碁微装", "688630 CH Equity", "9630 HK Equity", "2026-06-26", 252.73),
    Pair("SG Micro",     "圣邦股份", "300661 CH Equity", "3661 HK Equity", "2026-06-26",  85.20),
    Pair("GigaDevice",   "兆易创新", "603986 CH Equity", "3986 HK Equity", "2026-01-13", 162.00),
    Pair("OmniVision",   "豪威集团", "603501 CH Equity",  "501 HK Equity", "2026-01-12",   None),
    Pair("NOVOSENSE",    "纳芯微",   "688052 CH Equity", "2676 HK Equity", "2025-12-08", 116.00),
    Pair("Fortior",      "峰岹科技", "688279 CH Equity", "1304 HK Equity", "2025-07-09", 120.50),
    Pair("SICC",         "天岳先进", "688234 CH Equity", "2631 HK Equity", "2025-08-20",  42.80),
    Pair("Nexchip",      "晶合集成", "688249 CH Equity", "2249 HK Equity", "2026-07-10",  32.30),
    Pair("Montage Tech", "澜起科技", "688008 CH Equity", "6809 HK Equity", "2026-02-09", 106.89),
]


# ---------------------------------------------------------------------------
# BLOOMBERG
# ---------------------------------------------------------------------------

def fetch_history(securities: List[str],
                  fields: List[str],
                  start: dt.date,
                  end: dt.date,
                  chunk: int = 10) -> pd.DataFrame:
    """HistoricalDataRequest -> long DataFrame [date, security, field, value].

    Securities are chunked because the refdata service caps the number of
    securities per request.
    """
    import blpapi

    opts = blpapi.SessionOptions()
    opts.setServerHost(BBG_HOST)
    opts.setServerPort(BBG_PORT)
    session = blpapi.Session(opts)

    if not session.start():
        raise RuntimeError("Could not start blpapi session. Is the terminal running?")
    try:
        if not session.openService("//blp/refdata"):
            raise RuntimeError("Could not open //blp/refdata")
        svc = session.getService("//blp/refdata")

        rows = []
        for i in range(0, len(securities), chunk):
            batch = securities[i:i + chunk]
            req = svc.createRequest("HistoricalDataRequest")
            for s in batch:
                req.getElement("securities").appendValue(s)
            for f in fields:
                req.getElement("fields").appendValue(f)
            req.set("startDate", start.strftime("%Y%m%d"))
            req.set("endDate", end.strftime("%Y%m%d"))
            req.set("periodicitySelection", "DAILY")
            req.set("periodicityAdjustment", "ACTUAL")
            req.set("nonTradingDayFillOption", "ACTIVE_DAYS_ONLY")
            # Keep the series comparable through corporate actions.
            req.set("adjustmentSplit", True)
            req.set("adjustmentAbnormal", False)
            req.set("adjustmentNormal", False)

            print(f"  requesting {len(batch)} securities...", file=sys.stderr)
            session.sendRequest(req)

            done = False
            while not done:
                ev = session.nextEvent(30_000)
                for msg in ev:
                    if msg.hasElement("responseError"):
                        raise RuntimeError(msg.getElement("responseError"))
                    if not msg.hasElement("securityData"):
                        continue
                    sd = msg.getElement("securityData")
                    sec = sd.getElementAsString("security")

                    if sd.hasElement("securityError"):
                        print(f"  !! securityError {sec}: "
                              f"{sd.getElement('securityError')}", file=sys.stderr)
                        continue
                    if sd.hasElement("fieldExceptions"):
                        fx = sd.getElement("fieldExceptions")
                        for j in range(fx.numValues()):
                            print(f"  !! fieldException {sec}: "
                                  f"{fx.getValue(j)}", file=sys.stderr)

                    fd = sd.getElement("fieldData")
                    for j in range(fd.numValues()):
                        pt = fd.getValue(j)
                        d = pt.getElementAsDatetime("date")
                        for f in fields:
                            if pt.hasElement(f):
                                rows.append((pd.Timestamp(d), sec, f,
                                             pt.getElementAsFloat(f)))
                if ev.eventType() == blpapi.Event.RESPONSE:
                    done = True
        return pd.DataFrame(rows, columns=["date", "security", "field", "value"])
    finally:
        session.stop()


def build_wide(long_df: pd.DataFrame, fld: str) -> pd.DataFrame:
    """Long -> wide: index=date, columns=security."""
    sub = long_df[long_df["field"] == fld]
    wide = sub.pivot_table(index="date", columns="security", values="value")
    return wide.sort_index()


# ---------------------------------------------------------------------------
# ANALYTICS
# ---------------------------------------------------------------------------

def asof(series: pd.Series, when: pd.Timestamp) -> float:
    """Last observation at or before `when`. NaN if none / if `when` is in
    the future relative to the data (so incomplete horizons stay blank
    rather than silently snapping to the latest print)."""
    s = series.dropna()
    if s.empty or when < s.index[0]:
        return np.nan
    if when > s.index[-1] + pd.Timedelta(days=7):
        # target date is genuinely beyond the sample -> horizon not reached
        return np.nan
    return float(s.asof(when))


def nth_trading_day(series: pd.Series, t0: pd.Timestamp, n: int) -> Optional[pd.Timestamp]:
    s = series.dropna()
    idx = s.index[s.index >= t0]
    if len(idx) <= n:
        return None
    return idx[n]


def horizon_dates(a: pd.Series, h: pd.Series, t0: pd.Timestamp) -> Dict[str, pd.Timestamp]:
    """Resolve each horizon label to a target wall-clock date."""
    out = {}
    for label, (kind, spec) in HORIZONS.items():
        if kind == "trading_days":
            # use the H leg's calendar for the t+1 definition; falls back to A
            d = nth_trading_day(h, t0, spec) or nth_trading_day(a, t0, spec)
            if d is not None:
                out[label] = d
        else:
            out[label] = t0 + spec
    return out


def analyse(pair: Pair,
            a_px: pd.Series,
            h_px: pd.Series,
            fx: pd.Series) -> Dict[str, object]:
    """Per-name metrics table row + the time series used for charting."""
    t0 = pair.ipo_date

    # anchor on t0 (or the first available print at/after t0)
    a0_date = a_px.dropna().index[a_px.dropna().index >= t0]
    h0_date = h_px.dropna().index[h_px.dropna().index >= t0]
    if len(a0_date) == 0 or len(h0_date) == 0:
        return {}
    a0, h0 = float(a_px.asof(a0_date[0])), float(h_px.asof(h0_date[0]))

    row: Dict[str, object] = {
        "Name": pair.name,
        "CN": pair.cn_name,
        "A ticker": pair.a_tkr.replace(" Equity", ""),
        "H ticker": pair.h_tkr.replace(" Equity", ""),
        "IPO date": t0.date(),
        "Offer px (HKD)": pair.offer_px,
        "Day1 close (HKD)": round(h0, 2),
        "IPO pop %": (round((h0 / pair.offer_px - 1) * 100, 1)
                      if pair.offer_px else np.nan),
    }

    targets = horizon_dates(a_px, h_px, t0)

    # premium series over the common window
    common = a_px.index.intersection(h_px.index)
    common = common[common >= t0]
    prem = pd.Series(dtype=float)
    if len(common):
        a_hkd = a_px.reindex(common).ffill() * fx.reindex(common).ffill()
        prem = (a_hkd / h_px.reindex(common).ffill() - 1.0) * 100.0

    prem0 = float(prem.iloc[0]) if len(prem) else np.nan
    row["A/H prem t0 %"] = round(prem0, 1) if prem0 == prem0 else np.nan

    for label in HORIZONS:
        if label not in targets:
            row[f"A {label} %"] = np.nan
            row[f"H {label} %"] = np.nan
            row[f"prem {label} %"] = np.nan
            row[f"d-prem {label} pp"] = np.nan
            continue
        tgt = targets[label]
        a1, h1 = asof(a_px, tgt), asof(h_px, tgt)
        row[f"A {label} %"] = round((a1 / a0 - 1) * 100, 1) if a1 == a1 else np.nan
        row[f"H {label} %"] = round((h1 / h0 - 1) * 100, 1) if h1 == h1 else np.nan
        p = asof(prem, tgt) if len(prem) else np.nan
        row[f"prem {label} %"] = round(p, 1) if p == p else np.nan
        row[f"d-prem {label} pp"] = (round(p - prem0, 1)
                                     if (p == p and prem0 == prem0) else np.nan)

    return {
        "row": row,
        "a_reb": (a_px[a_px.index >= t0] / a0 * 100).dropna(),
        "h_reb": (h_px[h_px.index >= t0] / h0 * 100).dropna(),
        "prem": prem.dropna(),
        "targets": targets,
        "t0": t0,
    }


# ---------------------------------------------------------------------------
# CHARTS
# ---------------------------------------------------------------------------

A_COL, H_COL, P_COL = "#c0392b", "#1f4e79", "#7d6608"
plt.rcParams.update({
    "font.size": 9,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
})


def _mark_horizons(ax, targets, t0):
    for label, d in targets.items():
        if d is None:
            continue
        ax.axvline(d, color="0.65", lw=0.7, ls=":", zorder=0)
        ax.annotate(label, xy=(d, 1), xycoords=("data", "axes fraction"),
                    xytext=(2, -10), textcoords="offset points",
                    fontsize=7, color="0.45")


def chart_pair(res: Dict, pair: Pair, pdf: PdfPages):
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(9, 6.2), sharex=True,
        gridspec_kw={"height_ratios": [2, 1], "hspace": 0.12})

    ax1.plot(res["a_reb"].index, res["a_reb"].values, color=A_COL, lw=1.5,
             label=f"A  {pair.a_tkr.split()[0]}")
    ax1.plot(res["h_reb"].index, res["h_reb"].values, color=H_COL, lw=1.5,
             label=f"H  {pair.h_tkr.split()[0]}")
    ax1.axhline(100, color="0.4", lw=0.8)
    _mark_horizons(ax1, res["targets"], res["t0"])
    ax1.set_ylabel("Rebased, t0 close = 100")
    ax1.legend(frameon=False, loc="best")
    ax1.set_title(f"{pair.name}  ({pair.cn_name})   H-share IPO "
                  f"{res['t0'].date()}", loc="left", fontweight="bold")

    ax2.plot(res["prem"].index, res["prem"].values, color=P_COL, lw=1.4)
    ax2.axhline(0, color="0.4", lw=0.8)
    ax2.fill_between(res["prem"].index, 0, res["prem"].values,
                     where=res["prem"].values >= 0, color=P_COL, alpha=0.15)
    ax2.fill_between(res["prem"].index, 0, res["prem"].values,
                     where=res["prem"].values < 0, color=H_COL, alpha=0.15)
    _mark_horizons(ax2, res["targets"], res["t0"])
    ax2.set_ylabel("A/H premium, %")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b-%y"))

    fig.tight_layout()
    pdf.savefig(fig)
    fig.savefig(os.path.join(OUTDIR, f"{pair.name.replace(' ', '_')}.png"), dpi=160)
    plt.close(fig)


def chart_event_time(results: Dict[str, Dict], pdf: PdfPages):
    """All names overlaid on trading days since IPO -- the money chart."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    cmap = plt.get_cmap("tab10")

    for i, (name, res) in enumerate(results.items()):
        c = cmap(i % 10)
        h = res["h_reb"]
        ax1.plot(range(len(h)), h.values, lw=1.3, color=c, label=name)
        p = res["prem"]
        ax2.plot(range(len(p)), p.values, lw=1.3, color=c, label=name)

    ax1.axhline(100, color="0.4", lw=0.8)
    ax1.set_title("H-share, rebased to listing-day close", loc="left", fontweight="bold")
    ax1.set_xlabel("Trading days since IPO")
    ax1.set_ylabel("Index, t0 = 100")
    ax1.set_xlim(0, 45)

    ax2.axhline(0, color="0.4", lw=0.8)
    ax2.set_title("A/H premium since listing", loc="left", fontweight="bold")
    ax2.set_xlabel("Trading days since IPO")
    ax2.set_ylabel("Premium, %")
    ax2.set_xlim(0, 45)
    ax2.legend(frameon=False, fontsize=7, ncol=2)

    fig.tight_layout()
    pdf.savefig(fig)
    fig.savefig(os.path.join(OUTDIR, "event_time_overlay.png"), dpi=160)
    plt.close(fig)


def chart_summary_bars(tbl: pd.DataFrame, pdf: PdfPages):
    labels = list(HORIZONS)
    names = tbl["Name"].tolist()
    x = np.arange(len(names))
    w = 0.8 / len(labels)

    for leg, col in (("A", A_COL), ("H", H_COL)):
        fig, ax = plt.subplots(figsize=(11, 4.4))
        for k, lab in enumerate(labels):
            vals = tbl[f"{leg} {lab} %"].values.astype(float)
            ax.bar(x + k * w - 0.4 + w / 2, vals, w,
                   label=lab, color=col, alpha=0.35 + 0.15 * k,
                   edgecolor="white", linewidth=0.5)
        ax.axhline(0, color="0.3", lw=0.9)
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=20, ha="right")
        ax.set_ylabel("Return from listing-day close, %")
        ax.set_title(f"{leg}-share performance since H-share IPO",
                     loc="left", fontweight="bold")
        ax.legend(frameon=False, ncol=len(labels))
        fig.tight_layout()
        pdf.savefig(fig)
        fig.savefig(os.path.join(OUTDIR, f"bars_{leg}.png"), dpi=160)
        plt.close(fig)


def chart_premium_heatmap(tbl: pd.DataFrame, pdf: PdfPages):
    cols = ["A/H prem t0 %"] + [f"prem {l} %" for l in HORIZONS]
    m = tbl.set_index("Name")[cols].astype(float)

    fig, ax = plt.subplots(figsize=(8, 4.6))
    lim = np.nanmax(np.abs(m.values)) if np.isfinite(m.values).any() else 1
    im = ax.imshow(m.values, cmap="RdYlGn_r", vmin=-lim, vmax=lim, aspect="auto")
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(["t0"] + list(HORIZONS))
    ax.set_yticks(range(len(m)))
    ax.set_yticklabels(m.index)
    ax.grid(False)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = m.values[i, j]
            ax.text(j, i, "n/a" if v != v else f"{v:.0f}",
                    ha="center", va="center", fontsize=8,
                    color="0.15" if v == v else "0.6")
    ax.set_title("A/H premium, % (A above H = positive)",
                 loc="left", fontweight="bold")
    fig.colorbar(im, ax=ax, shrink=0.8, label="%")
    fig.tight_layout()
    pdf.savefig(fig)
    fig.savefig(os.path.join(OUTDIR, "premium_heatmap.png"), dpi=160)
    plt.close(fig)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="skip Bloomberg, read cached prices")
    ap.add_argument("--field", default=DEFAULT_FIELD,
                    help="PX_LAST or TOT_RETURN_INDEX_GROSS_DVDS")
    ap.add_argument("--end", default=None, help="YYYY-MM-DD, default today")
    args = ap.parse_args()

    os.makedirs(OUTDIR, exist_ok=True)

    end = pd.Timestamp(args.end).date() if args.end else dt.date.today()
    start = (min(p.ipo_date for p in PAIRS) - pd.Timedelta(days=45)).date()

    if args.offline:
        if not os.path.exists(CACHE):
            sys.exit(f"No cache at {CACHE}; run once without --offline.")
        long_df = pd.read_parquet(CACHE)
        print(f"Loaded cache: {len(long_df):,} rows")
    else:
        secs = [p.a_tkr for p in PAIRS] + [p.h_tkr for p in PAIRS] + [FX_TICKER]
        print(f"Pulling {len(secs)} securities, {start} -> {end}")
        long_df = fetch_history(secs, [args.field], start, end)
        if long_df.empty:
            sys.exit("Bloomberg returned nothing. Check tickers / entitlements.")
        long_df.to_parquet(CACHE)
        print(f"Cached {len(long_df):,} rows -> {CACHE}")

    wide = build_wide(long_df, args.field)

    if FX_TICKER not in wide.columns:
        sys.exit(f"{FX_TICKER} missing from the pull.")
    fx = wide[FX_TICKER].ffill()

    results, rows = {}, []
    for p in PAIRS:
        if p.a_tkr not in wide.columns or p.h_tkr not in wide.columns:
            print(f"  skip {p.name}: missing a leg in the data")
            continue
        res = analyse(p, wide[p.a_tkr].dropna(), wide[p.h_tkr].dropna(), fx)
        if not res:
            print(f"  skip {p.name}: no prices at/after {p.ipo}")
            continue
        results[p.name] = res
        rows.append(res["row"])

    tbl = pd.DataFrame(rows)

    # ---- output -----------------------------------------------------------
    pd.set_option("display.width", 220, "display.max_columns", 60)
    print("\n" + "=" * 100)
    print(f"A/H PERFORMANCE FROM H-SHARE IPO   (field={args.field}, asof={end})")
    print("=" * 100)
    ret_cols = ["Name", "IPO pop %"] + \
               [c for l in HORIZONS for c in (f"A {l} %", f"H {l} %")]
    print(tbl[ret_cols].to_string(index=False))
    print()
    prem_cols = ["Name", "A/H prem t0 %"] + \
                [c for l in HORIZONS for c in (f"prem {l} %", f"d-prem {l} pp")]
    print(tbl[prem_cols].to_string(index=False))

    xlsx = os.path.join(OUTDIR, "ah_ipo_performance.xlsx")
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        tbl.to_excel(xw, "summary", index=False)
        for name, res in results.items():
            df = pd.DataFrame({"A_rebased": res["a_reb"],
                               "H_rebased": res["h_reb"],
                               "AH_premium_pct": res["prem"]})
            df.to_excel(xw, name[:28])
    print(f"\nWrote {xlsx}")

    pdf_path = os.path.join(OUTDIR, "ah_ipo_charts.pdf")
    with PdfPages(pdf_path) as pdf:
        chart_event_time(results, pdf)
        chart_premium_heatmap(tbl, pdf)
        chart_summary_bars(tbl, pdf)
        for p in PAIRS:
            if p.name in results:
                chart_pair(results[p.name], p, pdf)
    print(f"Wrote {pdf_path} and PNGs in {OUTDIR}/")


if __name__ == "__main__":
    main()
