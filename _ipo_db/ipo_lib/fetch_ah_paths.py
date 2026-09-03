#!/usr/bin/env python3
"""Daily A/H price paths for the first ~3 months after every A-to-H listing.

The desk's reference notebook (ah_ipo_notebook.ipynb) draws four charts per
pair — native levels on twin axes, both legs in HKD with the premium as a
shaded gap, rebased paths, and the premium line. Those need SERIES, not
snapshots, and the dashboard must work offline on the desk. So this pass
precomputes, per A/H deal, the first 92 calendar days of:

    day offsets (calendar days since listing, H trading days)
    H close (HK$, raw)                    from Tencent kline
    A close (CNY, raw)                    from Tencent kline
    A close converted to HK$              at that day's CNYHKD
    premium % = A_hkd / H - 1

plus the offer price, so the HTML can rebase H exactly the way the notebook
does. Tencent's bare `day` series is unadjusted at source; the FX series comes
from Yahoo's CNYHKD=X daily closes (forward-filled over A-share holidays), and
each pair's FX-at-pricing is cross-checked against the value fetch_ah_ipo.py
stored — a disagreement prints loudly.

Writes data/batches/ah_paths.json (compact arrays, ~100KB for 61 pairs).
Staleness-aware: a pair younger than 92 days at last fetch is refetched.
"""
import json, time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "batches" / "ah_paths.json"
SPAN_DAYS = 92
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def tx_kline(symbol, d1, d2, with_open=False):
    """[(date, close)] raw daily closes from Tencent; with_open adds the open."""
    u = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
         f"param={symbol},day,{d1},{d2},320,")
    r = requests.get(u, headers=UA, timeout=30)
    rows = ((r.json().get("data") or {}).get(symbol) or {}).get("day") or []
    out = []
    for row in rows:
        try:
            out.append((row[0], float(row[2]), float(row[1]))
                       if with_open else (row[0], float(row[2])))
        except (IndexError, ValueError, TypeError):
            continue
    return out


def yahoo_fx(start, end):
    """CNYHKD=X daily closes as {date: rate}."""
    import yfinance as yf
    h = yf.Ticker("CNYHKD=X").history(start=start, end=end, auto_adjust=False)
    return {d.strftime("%Y-%m-%d"): float(c) for d, c in h["Close"].items()}


def a_symbol(a_code):
    num, venue = a_code.split(".")
    return ("sz" if venue == "SZ" else "sh" if venue == "SS" else "bj") + num


def main():
    deals = json.loads((ROOT / "data" / "deals.json").read_text())["deals"]
    pairs = [d for d in deals if d.get("a_share_code") and d.get("final_price")
             and d.get("ipo_date")]
    print(f"{len(pairs)} A/H pairs", flush=True)

    prev = {}
    if OUT.exists():
        old = json.loads(OUT.read_text())
        # v2 added the pre-IPO A-share month; older records refetch once
        if old.get("v") == 3:
            prev = {r["code"]: r for r in old["pairs"]}

    fx_start = min(d["ipo_date"][:10] for d in pairs)
    fx = yahoo_fx((date.fromisoformat(fx_start) - timedelta(days=10)).isoformat(),
                  date.today().isoformat())
    print(f"  FX days: {len(fx)}", flush=True)

    ah_at_ipo = {}
    p = ROOT / "data" / "batches" / "ah_ipo.json"
    if p.exists():
        ah_at_ipo = {r["code"]: r for r in json.loads(p.read_text())["deals"]}

    out, refetched = [], 0
    for i, d in enumerate(pairs):
        code, ipo, fp = d["code"], d["ipo_date"][:10], d["final_price"]
        span_end = (date.fromisoformat(ipo) + timedelta(days=SPAN_DAYS))
        old = prev.get(code)
        # a pair whose full window was already captured never changes again
        if old and old.get("complete"):
            out.append(old)
            continue
        refetched += 1
        rec = {"code": code, "name": d.get("name"), "ipo": ipo, "offer": fp,
               "a_code": d["a_share_code"]}
        try:
            h3 = tx_kline(f"hk{int(code):05d}", ipo, span_end.isoformat(),
                          with_open=True)
            h = [(r_[0], r_[1]) for r_ in h3]
            a3 = tx_kline(a_symbol(d["a_share_code"]),
                          (date.fromisoformat(ipo) - timedelta(days=45)).isoformat(),
                          span_end.isoformat(), with_open=True)
            a_rows = [(r_[0], r_[1]) for r_ in a3]
            a = dict(a_rows)
            # day-0 OPENS for both legs — the "align open to open" rebase and
            # the tradeable-entry premium need the first PRINT, not the close
            h_d0 = next((r_ for r_ in h3 if r_[0] >= ipo), None)
            if h_d0:
                rec["h_open0"] = round(h_d0[2], 4)
                a_d0 = next((r_ for r_ in a3 if r_[0] == h_d0[0]), None)
                if a_d0:
                    rec["a_open0"] = round(a_d0[2], 4)
            # the MONTH BEFORE the H listing — the flow read: was the A line
            # run up into the H pricing, or sold down?
            # EXACTLY the calendar month before the listing: the fetch window is
            # wider (holidays) but the series is clipped to -31..-1 days so the
            # chart's "month before" label is literally true and the run-up is
            # measured over the same span for every pair
            pre = [(dt_, c) for dt_, c in a_rows if dt_ < ipo
                   and (date.fromisoformat(ipo) - date.fromisoformat(dt_)).days <= 31]
            if pre:
                rec["pre_days"] = [(date.fromisoformat(x[0])
                                    - date.fromisoformat(ipo)).days for x in pre]
                rec["a_pre"] = [round(x[1], 3) for x in pre]
                rec["a_pre_from"] = pre[0][0]
                rec["a_pre_to"] = pre[-1][0]
                if len(pre) > 1 and pre[0][1]:
                    rec["a_pre_runup_pct"] = round(
                        100 * (pre[-1][1] / pre[0][1] - 1), 2)
            if not h:
                rec["note"] = "no H history on Tencent"
                out.append(rec)
                continue
            # align on H trading days; A and FX forward-fill across mainland
            # holidays so the premium line has no fake gaps
            last_a, last_fx = None, None
            days, hs, acny, ahkd, prem = [], [], [], [], []
            for dt_, hc in h:
                if dt_ < ipo:
                    continue
                off = (date.fromisoformat(dt_) - date.fromisoformat(ipo)).days
                if off > SPAN_DAYS:
                    break
                last_a = a.get(dt_, last_a)
                last_fx = fx.get(dt_, last_fx)
                days.append(off)
                hs.append(round(hc, 3))
                if last_a is not None and last_fx is not None:
                    ah = last_a * last_fx
                    acny.append(round(last_a, 3))
                    ahkd.append(round(ah, 3))
                    prem.append(round(100 * (ah / hc - 1), 2))
                else:
                    acny.append(None)
                    ahkd.append(None)
                    prem.append(None)
            rec.update({"days": days, "h": hs, "a_cny": acny, "a_hkd": ahkd,
                        "prem": prem})
            rec["v"] = 4
            rec["complete"] = bool(days) and (date.today() > span_end)
            # cross-check: the day-before-listing A_hkd this series implies must
            # match what fetch_ah_ipo computed independently
            chk = ah_at_ipo.get(code, {})
            if chk.get("a_close_hkd") and ahkd and ahkd[0] is not None:
                gap = abs(ahkd[0] - chk["a_close_hkd"]) / chk["a_close_hkd"]
                if gap > 0.06:      # day-0 close vs day-before close differ a bit
                    print(f"  !! {code}: path A_hkd day0 {ahkd[0]} vs at-IPO check "
                          f"{chk['a_close_hkd']} ({100*gap:.1f}%)", flush=True)
        except Exception as e:
            rec["error"] = str(e)[:100]
        out.append(rec)
        if (i + 1) % 15 == 0:
            print(f"  {i+1}/{len(pairs)}", flush=True)
        time.sleep(0.3)

    got = sum(1 for r in out if r.get("days"))
    OUT.write_text(json.dumps(
        {"batch": "ah_paths", "v": 3, "span_days": SPAN_DAYS,
         "method": "Tencent raw daily closes; A leg converted at Yahoo CNYHKD, "
                   "forward-filled over mainland holidays; H rebase base = offer price",
         "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(out), "with_paths": got, "refetched": refetched,
         "pairs": out}, ensure_ascii=False, indent=None))
    print(f"wrote {OUT}: {got}/{len(pairs)} pairs with paths "
          f"({OUT.stat().st_size/1024:.0f} KB, {refetched} refetched)")


if __name__ == "__main__":
    main()
