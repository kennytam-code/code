#!/usr/bin/env python3
"""Generate ah_peers.ipynb — the A/H peer charter the desk runs in Jupyter.

Built as notebook JSON rather than written by hand so it can be regenerated
whenever the deal database changes shape. It mirrors ah_ipo_notebook.ipynb's
Bloomberg pull and charts, with three differences the desk asked for:

  * the peer list is CODES typed straight off the Screener, not a hand-built
    PAIRS table — everything else (names, IPO date, offer price, A ticker) is
    looked up in data/deals.json;
  * the H leg is rebased on the OFFER PRICE, so a chart starts where the money
    went in rather than at the first close;
  * charts only, no summary tables.

Writes ah_peers.ipynb next to hk_ipo.py.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _lines(src):
    """nbformat stores source as a list of lines that CONCATENATE to the source,
    so every line but the last must keep its newline. Splitting without them
    collapses the whole cell onto one line and Jupyter reports a SyntaxError."""
    text = src.strip("\n")
    return [ln + "\n" for ln in text.split("\n")[:-1]] + [text.split("\n")[-1]]


def md(src):
    return {"cell_type": "markdown", "metadata": {}, "source": _lines(src)}


def code(src):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": _lines(src)}


CELLS = [
    md("""
# A/H peers — price paths since each listing

Type the codes from the **Screener** comp table into `CODES` below and run every
cell. Everything else — name, listing date, offer price, the A-share ticker — is
looked up in `data/deals.json`, so nothing has to be re-keyed.

* The H leg is rebased on the **offer price**, so day 0 is where the subscription
  money went in, not the first close.
* Peers with no A line still chart — they simply have no premium panel.
* Needs a Bloomberg terminal (`blpapi`). Set `OFFLINE = True` to redraw from the
  cached pull without touching the terminal.
"""),
    md("## 1. What to chart — the only cell you edit"),
    code('''
# Codes exactly as they appear in the Screener (leading zeros optional).
CODES = ["3750", "2015", "9868", "1810"]

# Window per stock, from its own listing day.
MONTHS = 2

# None  -> each stock starts at its own listing date (the usual case)
# "2025-01-02"           -> every stock starts on that date
# {"3750": "2025-06-01"} -> per-stock overrides, others keep their listing date
START = None

OFFLINE = False          # True = redraw from the cached pull, no terminal needed
FIELD   = "PX_LAST"
FX_TICKER = "CNYHKD Curncy"     # HKD per 1 CNY; "CNHHKD Curncy" for offshore
CACHE_PATH = "ah_peers_cache.pkl"
'''),
    md("## 2. Set-up, fonts and the deal lookup"),
    code('''
%matplotlib inline
import datetime as dt, json, warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from matplotlib import font_manager

warnings.filterwarnings("ignore")


def setup_fonts():
    """Pick a font that renders the Chinese names (same idea as the desk's
    ah_ipo_notebook); silently falls back to the default sans if none exist."""
    for name in ("PingFang HK", "PingFang SC", "Microsoft YaHei", "Microsoft JhengHei",
                 "SimHei", "Noto Sans CJK TC", "Heiti TC", "Arial Unicode MS"):
        if any(f.name == name for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = [name, "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False
            return True
    return False


setup_fonts()
plt.rcParams.update({"figure.dpi": 110, "axes.grid": True, "grid.alpha": .25,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 9})
A_COL, H_COL, P_COL = "#C0392B", "#1F4E79", "#6C5B7B"
WINDOW = relativedelta(months=MONTHS)
MARKERS = {"1w": relativedelta(days=7), "2w": relativedelta(days=14),
           "1M": relativedelta(months=1), "2M": relativedelta(months=2)}


def _find_deals_json():
    here = Path.cwd()
    for base in [here, *here.parents]:
        p = base / "data" / "deals.json"
        if p.exists():
            return p
    raise FileNotFoundError("data/deals.json not found — run this notebook from "
                            "the folder that holds hk_ipo.py")


DEALS = {d["code"]: d for d in json.loads(_find_deals_json().read_text())["deals"]}


def bbg_hk(code):
    """0700 -> '700 HK Equity' (Bloomberg carries no leading zeros)."""
    return f"{int(code)} HK Equity"


def bbg_a(a_code):
    """'300223.SZ' -> '300223 CH Equity'."""
    return f"{a_code.split('.')[0]} CH Equity" if a_code else None


class Peer:
    def __init__(self, code):
        self.code = str(code).zfill(4)
        d = DEALS.get(self.code, {})
        self.name = d.get("name") or self.code
        self.name_cn = d.get("name_cn") or ""
        self.offer = d.get("final_price")
        self.h_tkr = bbg_hk(self.code)
        self.a_tkr = bbg_a(d.get("a_share_code"))
        ipo = (d.get("ipo_date") or "")[:10]
        self.ipo = pd.Timestamp(ipo) if ipo else None
        if isinstance(START, dict) and self.code in START:
            self.t0 = pd.Timestamp(START[self.code])
        elif isinstance(START, str):
            self.t0 = pd.Timestamp(START)
        else:
            self.t0 = self.ipo
        # the rebase base is the offer price only when day 0 IS the listing day
        self.rebase_on_offer = bool(self.offer) and self.t0 == self.ipo

    @property
    def label(self):
        bits = [self.name, f"({self.code}.HK)"]
        if self.name_cn:
            bits.insert(1, self.name_cn)
        return " ".join(bits)


PEERS = [Peer(c) for c in CODES]
for p in PEERS:
    if p.t0 is None:
        print(f"  !! {p.code} has no listing date on file — set START for it")
print(f"{len(PEERS)} peers | with an A line: {sum(1 for p in PEERS if p.a_tkr)}")
for p in PEERS:
    print(f"   {p.label:52s} listed {p.ipo.date() if p.ipo is not None else '?'}"
          f"  offer {p.offer}  A: {p.a_tkr or '—'}")
'''),
    md("## 3. Bloomberg pull"),
    code('''
def fetch_history(securities, fields, start, end, chunk=10):
    """HistoricalDataRequest -> long DataFrame [date, security, field, value]."""
    import blpapi

    opts = blpapi.SessionOptions()
    opts.setServerHost("localhost")
    opts.setServerPort(8194)
    session = blpapi.Session(opts)
    if not session.start():
        raise RuntimeError("Could not start blpapi. Is the terminal running and logged in?")
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
            print(f"  requesting {len(batch)} securities ...")
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
                        print(f"  !! {sec}: {sd.getElement('securityError')}")
                        continue
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


def pull(offline=OFFLINE, field=FIELD):
    if offline:
        px = pd.read_pickle(CACHE_PATH)
        print(f"Loaded cache: {px.shape[0]} rows x {px.shape[1]} securities")
        return px
    live = [p for p in PEERS if p.t0 is not None]
    start = (min(p.t0 for p in live) - pd.Timedelta(days=10)).date()
    end = min((max(p.t0 for p in live) + WINDOW).date() + dt.timedelta(days=5),
              dt.date.today())
    secs = [p.h_tkr for p in live] + [p.a_tkr for p in live if p.a_tkr] + [FX_TICKER]
    print(f"Pulling {len(secs)} securities, {start} -> {end}")
    long_df = fetch_history(secs, [field], start, end)
    if long_df.empty:
        raise RuntimeError("Bloomberg returned nothing. Check tickers / entitlements.")
    px = (long_df[long_df["field"] == field]
          .pivot_table(index="date", columns="security", values="value")
          .sort_index())
    px.to_pickle(CACHE_PATH)
    print(f"Cached -> {CACHE_PATH}   ({px.shape[0]} rows x {px.shape[1]} securities)")
    return px


PX = pull()
'''),
    md("""
## 4. Build the per-stock windows

The H leg is indexed to the **offer price** where day 0 is the listing day, so
100 on the rebased chart means "back to what subscribers paid". The A leg is
indexed to its own close on day 0 — there is no offer price for a line that was
already trading.
"""),
    code('''
def build(px):
    fx = px[FX_TICKER].ffill() if FX_TICKER in px.columns else None
    book = {}
    for p in PEERS:
        if p.t0 is None or p.h_tkr not in px.columns:
            print(f"  skip {p.code}: no H prices in the pull")
            continue
        t0, t1 = p.t0, p.t0 + WINDOW
        h_all = px[p.h_tkr].dropna()
        if h_all.empty:
            continue
        end_avail = h_all.index[-1]
        h = h_all.loc[t0:t1]
        if h.empty:
            print(f"  skip {p.code}: no H prices in [{t0.date()}, {t1.date()}]")
            continue
        h_base = p.offer if p.rebase_on_offer else float(h.iloc[0])
        rec = {"peer": p, "t0": t0, "t1": t1, "h": h,
               "h_reb": h / h_base * 100, "h_base": h_base,
               "base_is_offer": p.rebase_on_offer,
               "d_h": (h.index - t0).days.to_numpy(),
               "end_avail": end_avail,
               "days_avail": int((min(end_avail, t1) - t0).days)}
        if p.a_tkr and p.a_tkr in px.columns and fx is not None:
            a_all = px[p.a_tkr].dropna()
            a = a_all.loc[t0:t1]
            if not a.empty:
                a_hkd = a * fx.reindex(a.index).ffill()
                common = a.index.intersection(h.index)
                prem = ((a.reindex(common) * fx.reindex(common).ffill())
                        / h.reindex(common) - 1.0).dropna() * 100.0
                rec.update({"a": a, "a_hkd": a_hkd, "a_reb": a / float(a.iloc[0]) * 100,
                            "prem": prem, "d_a": (a.index - t0).days.to_numpy(),
                            "d_p": (prem.index - t0).days.to_numpy(),
                            "end_avail": min(end_avail, a_all.index[-1])})
        book[p.code] = rec
    return book


BOOK = build(PX)
print(f"{len(BOOK)} peers charted, "
      f"{sum(1 for v in BOOK.values() if 'a' in v)} with an A leg")
'''),
    md("## 5. Per-stock charts"),
    code('''
XMAX = MONTHS * 31 + 2


def _markers(ax, t0, end_avail):
    for k, (lab, off) in enumerate(MARKERS.items()):
        if (t0 + off) > end_avail:
            continue
        n = ((t0 + off) - t0).days
        ax.axvline(n, color="0.65", lw=.7, ls=":", zorder=0)
        ax.annotate(lab, xy=(n, 1), xycoords=("data", "axes fraction"),
                    xytext=(2, -10 - 9 * (k % 2)), textcoords="offset points",
                    fontsize=7, color="0.45")


def chart_stock(v):
    """The reference notebook's 2x2, pane for pane: native levels on twin axes,
    common-currency with the shaded premium gap, rebased (H on the OFFER),
    premium with +/- fills. H-only peers degrade to the two H panes."""
    p, has_a = v["peer"], "a" in v
    base_lbl = ("offer HK$%.2f" % v["h_base"]) if v["base_is_offer"] else "day-0 close"

    if has_a:
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(13, 7.4),
                                                     constrained_layout=True)
        # -- native price levels, twin axis (units differ) -------------------
        ax1.plot(v["d_a"], v["a"].values, color=A_COL, lw=1.7)
        ax1.set_ylabel("A share, CNY", color=A_COL)
        ax1.tick_params(axis="y", labelcolor=A_COL)
        ax1b = ax1.twinx()
        ax1b.plot(v["d_h"], v["h"].values, color=H_COL, lw=1.7)
        ax1b.set_ylabel("H share, HKD", color=H_COL)
        ax1b.tick_params(axis="y", labelcolor=H_COL)
        ax1b.grid(False)
        ax1b.spines["right"].set_visible(True)
        ax1.set_title("Price levels, native currency", loc="left", fontsize=9.5)
        _markers(ax1, v["t0"], v["end_avail"])

        # -- both legs in HKD, one axis: the gap is the premium --------------
        ax2.plot(v["d_a"], v["a_hkd"].values, color=A_COL, lw=1.7, label="A, in HKD")
        ax2.plot(v["d_h"], v["h"].values, color=H_COL, lw=1.7, label="H, HKD")
        dp = v["d_p"]
        a_c = v["a_hkd"].reindex(v["prem"].index).to_numpy()
        h_c = v["h"].reindex(v["prem"].index).to_numpy()
        ax2.fill_between(dp, a_c, h_c, where=a_c >= h_c, color=A_COL, alpha=.12,
                         interpolate=True)
        ax2.fill_between(dp, a_c, h_c, where=a_c < h_c, color=H_COL, alpha=.12,
                         interpolate=True)
        ax2.set_ylabel("HKD")
        ax2.legend(frameon=False, fontsize=8)
        ax2.set_title("Common currency — shaded gap = A/H premium", loc="left",
                      fontsize=9.5)

        # -- rebased ---------------------------------------------------------
        ax3.plot(v["d_a"], v["a_reb"].values, color=A_COL, lw=1.7,
                 label=f"A  {p.a_tkr.split()[0] if p.a_tkr else ''}")
        ax3.plot(v["d_h"], v["h_reb"].values, color=H_COL, lw=1.7,
                 label=f"H  {p.h_tkr.split()[0]} (= {base_lbl})")
        ax3.axhline(100, color="0.4", lw=.8)
        ax3.set_ylabel("day 0 = 100")
        ax3.legend(frameon=False, fontsize=8)
        ax3.set_title(f"Rebased — H on the {base_lbl}", loc="left", fontsize=9.5)
        _markers(ax3, v["t0"], v["end_avail"])

        # -- premium ---------------------------------------------------------
        pv = v["prem"].to_numpy()
        ax4.plot(dp, pv, color=P_COL, lw=1.6)
        ax4.axhline(0, color="0.4", lw=.8)
        ax4.fill_between(dp, 0, pv, where=pv >= 0, color=A_COL, alpha=.15)
        ax4.fill_between(dp, 0, pv, where=pv < 0, color=H_COL, alpha=.15)
        ax4.set_ylabel("%")
        ax4.set_title("A/H premium (positive = A above H)", loc="left", fontsize=9.5)
        _markers(ax4, v["t0"], v["end_avail"])
        panes = (ax1, ax2, ax3, ax4)
    else:
        fig, (ax1, ax3) = plt.subplots(1, 2, figsize=(13, 3.9),
                                       constrained_layout=True)
        ax1.plot(v["d_h"], v["h"].values, color=H_COL, lw=1.7)
        if v["base_is_offer"]:
            ax1.axhline(v["h_base"], color=H_COL, lw=.9, ls="--", alpha=.7)
            ax1.annotate("offer", xy=(XMAX, v["h_base"]), fontsize=7, color=H_COL,
                         ha="right", va="bottom")
        ax1.set_ylabel("H share, HKD")
        ax1.set_title("H price", loc="left", fontsize=9.5)
        _markers(ax1, v["t0"], v["end_avail"])
        ax3.plot(v["d_h"], v["h_reb"].values, color=H_COL, lw=1.7,
                 label=f"H (= {base_lbl})")
        ax3.axhline(100, color="0.4", lw=.8)
        ax3.set_ylabel("day 0 = 100")
        ax3.legend(frameon=False, fontsize=8)
        ax3.set_title(f"Rebased — on the {base_lbl}", loc="left", fontsize=9.5)
        _markers(ax3, v["t0"], v["end_avail"])
        panes = (ax1, ax3)

    for ax in panes:
        ax.set_xlim(0, XMAX)
        ax.set_xlabel("Calendar days since H-share listing")
    partial = ("" if v["t1"] <= v["end_avail"]
               else f"   [only {v['days_avail']} days of data so far]")
    fig.suptitle(f"{p.label}   |   listed {v['t0'].date()}{partial}",
                 fontweight="bold", fontsize=12, x=.01, ha="left")
    plt.show()


for _c in BOOK:
    chart_stock(BOOK[_c])
'''),
    md("""
## 6. GUI — type codes and dates, press Draw

Runs the whole chain (pull → build → charts) from a form, so nothing above needs
re-editing: type the codes, optionally set a common start date and the window,
tick *offline* to redraw from the cache, press **Draw charts**. Needs
`ipywidgets` (ships with Jupyter/Anaconda); if it is missing this cell says so
and the CODES cell above keeps working exactly as before.
"""),
    code('''
def _run_peers(codes, start, months, offline):
    """Rebuild globals from the form and redraw everything."""
    global CODES, START, MONTHS, WINDOW, XMAX, OFFLINE, PEERS, PX, BOOK
    CODES = [c.strip() for c in codes.replace(",", " ").split() if c.strip()]
    if not CODES:
        print("type at least one code"); return
    START = start or None
    MONTHS = months
    WINDOW = relativedelta(months=MONTHS)
    XMAX = MONTHS * 31 + 2
    OFFLINE = offline
    PEERS = [Peer(c) for c in CODES]
    for p in PEERS:
        print(f"   {p.label:52s} day0 {p.t0.date() if p.t0 is not None else '?'}"
              f"  offer {p.offer}  A: {p.a_tkr or '—'}")
    PX = pull(offline=OFFLINE)
    BOOK = build(PX)
    for _c in BOOK:
        chart_stock(BOOK[_c])
    chart_grid(BOOK)
    chart_overlay(BOOK)


try:
    import ipywidgets as W
    from IPython.display import display, clear_output

    w_codes = W.Textarea(value=" ".join(CODES), rows=2,
                         description="Codes", layout=W.Layout(width="480px"),
                         placeholder="e.g. 3750 2015 9868  (Screener codes, spaces or commas)")
    w_start = W.Text(value="" if not isinstance(START, str) else START,
                     description="Start date", placeholder="blank = each stock's IPO date")
    w_months = W.IntSlider(value=MONTHS, min=1, max=12, description="Months")
    w_off = W.Checkbox(value=False, description="offline (reuse cached pull)")
    w_btn = W.Button(description="Draw charts", button_style="primary")
    w_out = W.Output()

    def _click(_b):
        with w_out:
            clear_output()
            try:
                _run_peers(w_codes.value, w_start.value.strip(), w_months.value, w_off.value)
            except Exception as e:
                print(f"!! {type(e).__name__}: {e}")

    w_btn.on_click(_click)
    display(W.VBox([w_codes, W.HBox([w_start, w_months, w_off]), w_btn, w_out]))
except ImportError:
    print("ipywidgets is not installed - the form is unavailable, but everything")
    print("still works: edit CODES / START / MONTHS in cell 1 and run all cells.")
    print("(pip install ipywidgets   enables the form.)")
'''),
    md("## 7. All peers on one axis"),
    code('''
def chart_overlay(book):
    """The reference's three-panel overlay: A rebased | H rebased | premium."""
    withA = {k: v for k, v in book.items() if "a" in v}
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6), constrained_layout=True)
    cmap = plt.get_cmap("tab10")
    for i, (code, v) in enumerate(book.items()):
        c = cmap(i % 10)
        if "a" in v:
            axes[0].plot(v["d_a"], v["a_reb"].values, lw=1.4, color=c,
                         label=v["peer"].name[:20])
        axes[1].plot(v["d_h"], v["h_reb"].values, lw=1.4, color=c,
                     label=v["peer"].name[:20])
        if "prem" in v:
            axes[2].plot(v["d_p"], v["prem"].to_numpy(), lw=1.4, color=c,
                         label=v["peer"].name[:20])
    for ax, ttl, yl, base in [
            (axes[0], "A share, rebased", "Day 0 = 100", 100),
            (axes[1], "H share, rebased on the OFFER", "Day 0 = 100", 100),
            (axes[2], "A/H premium", "%", 0)]:
        ax.axhline(base, color="0.4", lw=.8)
        ax.set_title(ttl, loc="left", fontweight="bold")
        ax.set_xlabel("Calendar days since listing")
        ax.set_ylabel(yl)
        ax.set_xlim(0, XMAX)
    axes[1].legend(frameon=False, fontsize=7, ncol=2)
    if withA:
        axes[2].legend(frameon=False, fontsize=7, ncol=2)
    plt.show()


def chart_grid(book):
    n = len(book)
    if not n:
        return
    ncol = min(3, n)
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.6 * ncol, 3.2 * nrow),
                             constrained_layout=True, squeeze=False)
    flat = axes.ravel()
    for ax, (code, v) in zip(flat, book.items()):
        ax.plot(v["d_h"], v["h"].values, color=H_COL, lw=1.4)
        if v["base_is_offer"]:
            ax.axhline(v["h_base"], color=H_COL, lw=.8, ls="--", alpha=.6)
        if "a_hkd" in v:
            ax.plot(v["d_a"], v["a_hkd"].values, color=A_COL, lw=1.2, alpha=.85)
        ax.set_xlim(0, XMAX)
        ax.tick_params(labelsize=7)
        tag = "" if v["t1"] <= v["end_avail"] else f"  [{v['days_avail']}d]"
        ax.set_title(f"{v['peer'].name[:24]}  {v['t0'].date()}{tag}", loc="left",
                     fontsize=8.5)
    for ax in flat[n:]:
        ax.set_visible(False)
    fig.suptitle("H in HKD (blue, dashed = offer) vs A converted to HKD (red)",
                 fontweight="bold", fontsize=10.5, x=.01, ha="left")
    plt.show()


chart_grid(BOOK)
chart_overlay(BOOK)
'''),
]


def main():
    nb = {"cells": CELLS,
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                      "name": "python3"},
                       "language_info": {"name": "python", "version": "3.11"}},
          "nbformat": 4, "nbformat_minor": 5}
    dest = ROOT / "out" / "ah_peers.ipynb"
    dest.parent.mkdir(exist_ok=True, parents=True)
    dest.write_text(json.dumps(nb, ensure_ascii=False, indent=1))
    print(f"wrote {dest} ({len(CELLS)} cells)")
    return dest


if __name__ == "__main__":
    main()
