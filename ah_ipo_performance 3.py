"""
A/H performance & premium analysis for China semiconductor A+H listings
=======================================================================
Jupyter-friendly version.

Quick start in a notebook
-------------------------
    %run ah_ipo_performance.py          # defines everything, runs nothing
    px = pull()                         # hits Bloomberg once, caches to parquet
    res, tbl = run(px)                  # analytics + all charts inline

Re-chart later without a terminal:
    px = pull(offline=True)

Charts produced per stock
-------------------------
    1. Native price levels : A in CNY (left axis), H in HKD (right axis)
    2. Common currency     : both legs in HKD on one axis, gap shaded
                             (the visual version of the A/H premium)
    3. Rebased             : both = 100 at listing-day close
    4. A/H premium         : %, through time

Plus, across the group: an all-names price grid, an event-time overlay,
a premium heatmap, and A/H return bars by horizon.

Requirements
------------
    Bloomberg Terminal running and logged in
    pip install blpapi --index-url https://blpapi.bloomberg.com/repository/releases/python/simple/
    pip install pandas numpy matplotlib python-dateutil openpyxl pyarrow
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from matplotlib import font_manager
from matplotlib.backends.backend_pdf import PdfPages

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

OUTDIR = "ah_output"
CACHE = os.path.join(OUTDIR, "px_cache.parquet")

BBG_HOST, BBG_PORT = "localhost", 8194

# PX_LAST = clean price. TOT_RETURN_INDEX_GROSS_DVDS = total return basis.
FIELD = "PX_LAST"

# CNYHKD quotes HKD per 1 CNY, so A_hkd = A_cny * CNYHKD.
# Switch to "CNHHKD Curncy" if your desk convention is offshore.
FX_TICKER = "CNYHKD Curncy"

HORIZONS = {
    "1d": ("trading_days", 1),
    "1w": ("calendar", relativedelta(days=7)),
    "2w": ("calendar", relativedelta(days=14)),
    "1M": ("calendar", relativedelta(months=1)),
    "2M": ("calendar", relativedelta(months=2)),
}


@dataclass
class Pair:
    name: str
    cn_name: str
    a_tkr: str
    h_tkr: str
    ipo: str
    offer_px: Optional[float] = None

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
# FONTS -- fixes the "Glyph missing from current font" warnings
# ---------------------------------------------------------------------------

def setup_fonts() -> bool:
    """Register a CJK-capable font if one is installed. Returns True if the
    Chinese names can be rendered; callers fall back to English-only labels
    if False, which is what actually silences the warnings."""
    candidates = [
        "Microsoft YaHei", "Microsoft JhengHei", "SimHei", "SimSun",   # Windows
        "PingFang SC", "Hiragino Sans GB", "Arial Unicode MS",         # macOS
        "Noto Sans CJK SC", "Noto Sans SC", "Source Han Sans SC",      # Linux
        "WenQuanYi Zen Hei",
    ]
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for c in candidates:
        if c in installed:
            plt.rcParams["font.sans-serif"] = [c, "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False
            print(f"CJK font: {c}")
            return True
    print("No CJK font found -- Chinese names omitted from chart labels.\n"
          "  On Windows, if you expect 'Microsoft YaHei' to be there, rebuild "
          "the font cache:\n"
          "    from matplotlib import font_manager\n"
          "    font_manager._load_fontmanager(try_read_cache=False)")
    return False


HAS_CJK = setup_fonts()

A_COL, H_COL, P_COL = "#c0392b", "#1f4e79", "#7d6608"
plt.rcParams.update({
    "font.size": 9,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
    "figure.dpi": 110,
})


def label(pair: "Pair") -> str:
    return f"{pair.name} ({pair.cn_name})" if HAS_CJK else pair.name


# ---------------------------------------------------------------------------
# BLOOMBERG
# ---------------------------------------------------------------------------

def fetch_history(securities: List[str], fields: List[str],
                  start: dt.date, end: dt.date, chunk: int = 10) -> pd.DataFrame:
    """HistoricalDataRequest -> long DataFrame [date, security, field, value]."""
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
            req.set("adjustmentSplit", True)
            req.set("adjustmentAbnormal", False)
            req.set("adjustmentNormal", False)

            print(f"  requesting {len(batch)} securities...")
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
                        print(f"  !! securityError {sec}: {sd.getElement('securityError')}")
                        continue
                    if sd.hasElement("fieldExceptions"):
                        fx = sd.getElement("fieldExceptions")
                        for j in range(fx.numValues()):
                            print(f"  !! fieldException {sec}: {fx.getValue(j)}")

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


def pull(offline: bool = False, end=None, field: str = FIELD) -> pd.DataFrame:
    """Get the wide price panel (index=date, columns=security)."""
    os.makedirs(OUTDIR, exist_ok=True)
    end = pd.Timestamp(end).date() if end else dt.date.today()
    start = (min(p.ipo_date for p in PAIRS) - pd.Timedelta(days=45)).date()

    if offline:
        if not os.path.exists(CACHE):
            raise FileNotFoundError(f"No cache at {CACHE}; run pull() first.")
        long_df = pd.read_parquet(CACHE)
        print(f"Loaded cache: {len(long_df):,} rows")
    else:
        secs = [p.a_tkr for p in PAIRS] + [p.h_tkr for p in PAIRS] + [FX_TICKER]
        print(f"Pulling {len(secs)} securities, {start} -> {end}")
        long_df = fetch_history(secs, [field], start, end)
        if long_df.empty:
            raise RuntimeError("Bloomberg returned nothing. Check tickers / entitlements.")
        long_df.to_parquet(CACHE)
        print(f"Cached {len(long_df):,} rows -> {CACHE}")

    sub = long_df[long_df["field"] == field]
    return sub.pivot_table(index="date", columns="security", values="value").sort_index()


# ---------------------------------------------------------------------------
# ANALYTICS
# ---------------------------------------------------------------------------

def asof(series: pd.Series, when: pd.Timestamp) -> float:
    """Last observation at or before `when`. NaN if the target date is beyond
    the sample, so unreached horizons stay blank instead of snapping to the
    most recent print."""
    s = series.dropna()
    if s.empty or when < s.index[0]:
        return np.nan
    if when > s.index[-1] + pd.Timedelta(days=7):
        return np.nan
    return float(s.asof(when))


def nth_trading_day(series: pd.Series, t0: pd.Timestamp, n: int):
    idx = series.dropna().index
    idx = idx[idx >= t0]
    return idx[n] if len(idx) > n else None


def horizon_dates(a: pd.Series, h: pd.Series, t0: pd.Timestamp):
    out = {}
    for lab, (kind, spec) in HORIZONS.items():
        if kind == "trading_days":
            d = nth_trading_day(h, t0, spec)
            if d is None:
                d = nth_trading_day(a, t0, spec)
            if d is not None:
                out[lab] = d
        else:
            out[lab] = t0 + spec
    return out


def analyse(pair: Pair, a_px: pd.Series, h_px: pd.Series, fx: pd.Series) -> Dict:
    t0 = pair.ipo_date
    a_idx = a_px.dropna().index[a_px.dropna().index >= t0]
    h_idx = h_px.dropna().index[h_px.dropna().index >= t0]
    if len(a_idx) == 0 or len(h_idx) == 0:
        return {}
    a0, h0 = float(a_px.asof(a_idx[0])), float(h_px.asof(h_idx[0]))

    row: Dict[str, object] = {
        "Name": pair.name,
        "CN": pair.cn_name,
        "A ticker": pair.a_tkr.replace(" Equity", ""),
        "H ticker": pair.h_tkr.replace(" Equity", ""),
        "IPO date": t0.date(),
        "Offer px (HKD)": pair.offer_px,
        "Day1 close (HKD)": round(h0, 2),
        "IPO pop %": round((h0 / pair.offer_px - 1) * 100, 1) if pair.offer_px else np.nan,
    }

    targets = horizon_dates(a_px, h_px, t0)

    # post-IPO windows for charting
    a_post = a_px[a_px.index >= t0].dropna()
    h_post = h_px[h_px.index >= t0].dropna()
    fx_post = fx.reindex(a_post.index.union(h_post.index)).ffill()
    a_hkd = (a_post * fx_post.reindex(a_post.index)).dropna()

    # premium on the intersection of the two trading calendars
    common = a_post.index.intersection(h_post.index)
    prem = pd.Series(dtype=float)
    if len(common):
        prem = ((a_post.reindex(common) * fx_post.reindex(common))
                / h_post.reindex(common) - 1.0) * 100.0
        prem = prem.dropna()

    prem0 = float(prem.iloc[0]) if len(prem) else np.nan
    row["A/H prem t0 %"] = round(prem0, 1) if prem0 == prem0 else np.nan

    for lab in HORIZONS:
        if lab not in targets:
            for k in (f"A {lab} %", f"H {lab} %", f"prem {lab} %", f"d-prem {lab} pp"):
                row[k] = np.nan
            continue
        tgt = targets[lab]
        a1, h1 = asof(a_px, tgt), asof(h_px, tgt)
        row[f"A {lab} %"] = round((a1 / a0 - 1) * 100, 1) if a1 == a1 else np.nan
        row[f"H {lab} %"] = round((h1 / h0 - 1) * 100, 1) if h1 == h1 else np.nan
        p = asof(prem, tgt) if len(prem) else np.nan
        row[f"prem {lab} %"] = round(p, 1) if p == p else np.nan
        row[f"d-prem {lab} pp"] = (round(p - prem0, 1)
                                   if (p == p and prem0 == prem0) else np.nan)

    return {
        "pair": pair,
        "row": row,
        "a_px": a_post,      # CNY
        "h_px": h_post,      # HKD
        "a_hkd": a_hkd,      # A leg converted to HKD
        "a_reb": a_post / a0 * 100,
        "h_reb": h_post / h0 * 100,
        "prem": prem,
        "targets": targets,
        "t0": t0,
    }


# ---------------------------------------------------------------------------
# CHARTS
# ---------------------------------------------------------------------------

def _mark_horizons(ax, targets):
    """Vertical guides at each horizon. Labels are staggered vertically
    because 1d/1w/2w sit close together and would otherwise overlap."""
    for k, (lab, d) in enumerate(targets.items()):
        if d is None:
            continue
        ax.axvline(d, color="0.65", lw=0.7, ls=":", zorder=0)
        ax.annotate(lab, xy=(d, 1), xycoords=("data", "axes fraction"),
                    xytext=(2, -10 - 9 * (k % 3)), textcoords="offset points",
                    fontsize=7, color="0.45")


def _datefmt(ax):
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b-%y"))


def chart_pair(res: Dict, pdf: Optional[PdfPages] = None, show: bool = True):
    """Four-panel per-stock view: native prices, common-currency prices,
    rebased, premium."""
    pair = res["pair"]
    fig, axes = plt.subplots(2, 2, figsize=(13, 7.5), constrained_layout=True)
    (ax_nat, ax_ccy), (ax_reb, ax_prem) = axes

    # --- 1. native price levels, twin axis (units differ) ------------------
    ax_nat.plot(res["a_px"].index, res["a_px"].values, color=A_COL, lw=1.6)
    ax_nat.set_ylabel("A share, CNY", color=A_COL)
    ax_nat.tick_params(axis="y", labelcolor=A_COL)
    ax_nat2 = ax_nat.twinx()
    ax_nat2.plot(res["h_px"].index, res["h_px"].values, color=H_COL, lw=1.6)
    ax_nat2.set_ylabel("H share, HKD", color=H_COL)
    ax_nat2.tick_params(axis="y", labelcolor=H_COL)
    ax_nat2.grid(False)
    ax_nat2.spines["right"].set_visible(True)
    ax_nat.set_title("Price levels, native currency (twin axes)",
                     loc="left", fontsize=9.5)
    _mark_horizons(ax_nat, res["targets"])
    _datefmt(ax_nat)

    # --- 2. both legs in HKD, one axis -- the gap IS the premium -----------
    ax_ccy.plot(res["a_hkd"].index, res["a_hkd"].values, color=A_COL, lw=1.6,
                label="A, converted to HKD")
    ax_ccy.plot(res["h_px"].index, res["h_px"].values, color=H_COL, lw=1.6,
                label="H, HKD")
    common = res["a_hkd"].index.intersection(res["h_px"].index)
    if len(common):
        a_c = res["a_hkd"].reindex(common).values
        h_c = res["h_px"].reindex(common).values
        ax_ccy.fill_between(common, a_c, h_c, where=a_c >= h_c,
                            color=A_COL, alpha=0.12, interpolate=True)
        ax_ccy.fill_between(common, a_c, h_c, where=a_c < h_c,
                            color=H_COL, alpha=0.12, interpolate=True)
    ax_ccy.set_ylabel("HKD")
    ax_ccy.legend(frameon=False, fontsize=8)
    ax_ccy.set_title("Common currency -- shaded gap = A/H premium",
                     loc="left", fontsize=9.5)
    _datefmt(ax_ccy)

    # --- 3. rebased --------------------------------------------------------
    ax_reb.plot(res["a_reb"].index, res["a_reb"].values, color=A_COL, lw=1.6,
                label=f"A  {pair.a_tkr.split()[0]}")
    ax_reb.plot(res["h_reb"].index, res["h_reb"].values, color=H_COL, lw=1.6,
                label=f"H  {pair.h_tkr.split()[0]}")
    ax_reb.axhline(100, color="0.4", lw=0.8)
    ax_reb.set_ylabel("t0 close = 100")
    ax_reb.legend(frameon=False, fontsize=8)
    ax_reb.set_title("Rebased to listing-day close", loc="left", fontsize=9.5)
    _mark_horizons(ax_reb, res["targets"])
    _datefmt(ax_reb)

    # --- 4. premium --------------------------------------------------------
    p = res["prem"]
    ax_prem.plot(p.index, p.values, color=P_COL, lw=1.5)
    ax_prem.axhline(0, color="0.4", lw=0.8)
    if len(p):
        ax_prem.fill_between(p.index, 0, p.values, where=p.values >= 0,
                             color=A_COL, alpha=0.15)
        ax_prem.fill_between(p.index, 0, p.values, where=p.values < 0,
                             color=H_COL, alpha=0.15)
    ax_prem.set_ylabel("%")
    ax_prem.set_title("A/H premium (positive = A above H)", loc="left", fontsize=9.5)
    _mark_horizons(ax_prem, res["targets"])
    _datefmt(ax_prem)

    fig.suptitle(f"{label(pair)}   |   H-share IPO {res['t0'].date()}",
                 fontweight="bold", fontsize=12, x=0.01, ha="left")

    fig.savefig(os.path.join(OUTDIR, f"{pair.name.replace(' ', '_')}.png"),
                dpi=150, bbox_inches="tight")
    if pdf:
        pdf.savefig(fig, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig)


def chart_price_grid(results: Dict[str, Dict], pdf=None, show=True):
    """All names, native price levels, one small multiple each."""
    n = len(results)
    ncol = 3
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(13, 3.1 * nrow),
                             constrained_layout=True)
    axes = np.atleast_1d(axes).ravel()

    for ax, (name, res) in zip(axes, results.items()):
        ax.plot(res["a_px"].index, res["a_px"].values, color=A_COL, lw=1.3)
        ax.tick_params(axis="y", labelcolor=A_COL, labelsize=7)
        ax2 = ax.twinx()
        ax2.plot(res["h_px"].index, res["h_px"].values, color=H_COL, lw=1.3)
        ax2.tick_params(axis="y", labelcolor=H_COL, labelsize=7)
        ax2.grid(False)
        ax.set_title(f"{name}  (IPO {res['t0'].date()})", loc="left", fontsize=9)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b-%y"))
        ax.tick_params(axis="x", labelsize=7)

    for ax in axes[n:]:
        ax.set_visible(False)

    fig.suptitle("A share (red, CNY, left axis)  vs  H share (blue, HKD, right axis)",
                 fontweight="bold", fontsize=11, x=0.01, ha="left")
    fig.savefig(os.path.join(OUTDIR, "price_grid.png"), dpi=150, bbox_inches="tight")
    if pdf:
        pdf.savefig(fig, bbox_inches="tight")
    plt.show() if show else plt.close(fig)


def chart_event_time(results: Dict[str, Dict], pdf=None, show=True):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    cmap = plt.get_cmap("tab10")
    for i, (name, res) in enumerate(results.items()):
        c = cmap(i % 10)
        h, p = res["h_reb"], res["prem"]
        ax1.plot(range(len(h)), h.values, lw=1.3, color=c, label=name)
        ax2.plot(range(len(p)), p.values, lw=1.3, color=c, label=name)

    ax1.axhline(100, color="0.4", lw=0.8)
    ax1.set_title("H share, rebased to listing-day close", loc="left", fontweight="bold")
    ax1.set_xlabel("Trading days since IPO")
    ax1.set_ylabel("t0 = 100")
    ax1.set_xlim(0, 45)

    ax2.axhline(0, color="0.4", lw=0.8)
    ax2.set_title("A/H premium since listing", loc="left", fontweight="bold")
    ax2.set_xlabel("Trading days since IPO")
    ax2.set_ylabel("%")
    ax2.set_xlim(0, 45)
    ax2.legend(frameon=False, fontsize=7, ncol=2)

    fig.savefig(os.path.join(OUTDIR, "event_time_overlay.png"),
                dpi=150, bbox_inches="tight")
    if pdf:
        pdf.savefig(fig, bbox_inches="tight")
    plt.show() if show else plt.close(fig)


def chart_summary_bars(tbl: pd.DataFrame, pdf=None, show=True):
    labels = list(HORIZONS)
    names = tbl["Name"].tolist()
    x = np.arange(len(names))
    w = 0.8 / len(labels)

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), constrained_layout=True)
    for ax, leg in zip(axes, ("A", "H")):
        shades = plt.get_cmap("Reds" if leg == "A" else "Blues")(
            np.linspace(0.35, 0.85, len(labels)))
        for k, lab in enumerate(labels):
            ax.bar(x + k * w - 0.4 + w / 2,
                   tbl[f"{leg} {lab} %"].values.astype(float), w,
                   label=lab, color=shades[k], edgecolor="white", linewidth=0.5)
        ax.axhline(0, color="0.3", lw=0.9)
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=20, ha="right")
        ax.set_ylabel("Return from listing-day close, %")
        ax.set_title(f"{leg}-share performance since H-share IPO",
                     loc="left", fontweight="bold")
        ax.legend(frameon=False, ncol=len(labels), fontsize=8)

    fig.savefig(os.path.join(OUTDIR, "return_bars.png"), dpi=150, bbox_inches="tight")
    if pdf:
        pdf.savefig(fig, bbox_inches="tight")
    plt.show() if show else plt.close(fig)


def chart_premium_heatmap(tbl: pd.DataFrame, pdf=None, show=True):
    cols = ["A/H prem t0 %"] + [f"prem {l} %" for l in HORIZONS]
    m = tbl.set_index("Name")[cols].astype(float)

    # constrained_layout, not tight_layout -- colorbars break tight_layout
    fig, ax = plt.subplots(figsize=(8.5, 4.8), constrained_layout=True)
    finite = m.values[np.isfinite(m.values)]
    lim = float(np.abs(finite).max()) if finite.size else 1.0
    im = ax.imshow(m.values, cmap="RdYlGn_r", vmin=-lim, vmax=lim, aspect="auto")
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(["t0"] + list(HORIZONS))
    ax.set_yticks(range(len(m)))
    ax.set_yticklabels(m.index)
    ax.grid(False)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = m.values[i, j]
            ax.text(j, i, "n/a" if v != v else f"{v:.0f}", ha="center",
                    va="center", fontsize=8, color="0.15" if v == v else "0.6")
    ax.set_title("A/H premium, % (A above H = positive)", loc="left", fontweight="bold")
    fig.colorbar(im, ax=ax, shrink=0.85, label="%")

    fig.savefig(os.path.join(OUTDIR, "premium_heatmap.png"),
                dpi=150, bbox_inches="tight")
    if pdf:
        pdf.savefig(fig, bbox_inches="tight")
    plt.show() if show else plt.close(fig)


# ---------------------------------------------------------------------------
# DRIVER
# ---------------------------------------------------------------------------

def run(wide: pd.DataFrame, show: bool = True, save_pdf: bool = True):
    """Analytics + charts. Returns (results dict, summary DataFrame)."""
    os.makedirs(OUTDIR, exist_ok=True)

    if FX_TICKER not in wide.columns:
        raise KeyError(f"{FX_TICKER} missing from the pull.")
    fx = wide[FX_TICKER].ffill()

    results, rows = {}, []
    for p in PAIRS:
        if p.a_tkr not in wide.columns or p.h_tkr not in wide.columns:
            print(f"  skip {p.name}: a leg is missing from the data")
            continue
        res = analyse(p, wide[p.a_tkr].dropna(), wide[p.h_tkr].dropna(), fx)
        if not res:
            print(f"  skip {p.name}: no prices at/after {p.ipo}")
            continue
        results[p.name] = res
        rows.append(res["row"])

    tbl = pd.DataFrame(rows)

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 60)
    print("\n" + "=" * 100)
    print("RETURNS FROM H-SHARE LISTING-DAY CLOSE")
    print("=" * 100)
    print(tbl[["Name", "IPO pop %"] +
              [c for l in HORIZONS for c in (f"A {l} %", f"H {l} %")]
              ].to_string(index=False))
    print("\n" + "=" * 100)
    print("A/H PREMIUM")
    print("=" * 100)
    print(tbl[["Name", "A/H prem t0 %"] +
              [c for l in HORIZONS for c in (f"prem {l} %", f"d-prem {l} pp")]
              ].to_string(index=False))

    xlsx = os.path.join(OUTDIR, "ah_ipo_performance.xlsx")
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        tbl.to_excel(xw, sheet_name="summary", index=False)
        for name, res in results.items():
            pd.DataFrame({
                "A_px_CNY": res["a_px"],
                "H_px_HKD": res["h_px"],
                "A_px_HKD": res["a_hkd"],
                "A_rebased": res["a_reb"],
                "H_rebased": res["h_reb"],
                "AH_premium_pct": res["prem"],
            }).to_excel(xw, sheet_name=name[:28])
    print(f"\nWrote {xlsx}")

    pdf = PdfPages(os.path.join(OUTDIR, "ah_ipo_charts.pdf")) if save_pdf else None
    try:
        chart_price_grid(results, pdf, show)
        chart_event_time(results, pdf, show)
        chart_premium_heatmap(tbl, pdf, show)
        chart_summary_bars(tbl, pdf, show)
        for p in PAIRS:
            if p.name in results:
                chart_pair(results[p.name], pdf, show)
    finally:
        if pdf:
            pdf.close()
            print(f"Wrote {os.path.join(OUTDIR, 'ah_ipo_charts.pdf')}")

    return results, tbl


if __name__ == "__main__":
    run(pull(offline="--offline" in sys.argv), show=False)
