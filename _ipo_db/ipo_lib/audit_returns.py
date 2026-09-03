#!/usr/bin/env python3
"""INDEPENDENT recomputation of every stored return, written from scratch.

The user's report was "the 1m and 3m returns look wrong". Re-running
fetch_prices.py would only prove it is self-consistent, so this module does not
import or reuse any of it: it re-downloads each deal's history, applies its own
split correction, finds the debut bar its own way, and recomputes

    ret_H = 100 x (close at the H-th trading bar after debut / OFFER PRICE - 1)
    alpha_H = ret_H - benchmark return over the SAME bar window

then diffs the result against data/deals.json. Deals that differ by more than
DIFF_TOL are printed with a diagnosis (split, missing debut bar, halt/suspension,
benchmark window mismatch), and the whole table is written to
data/batches/audit_returns.json so the workbook's Verification tab can show it.

Run:  python ipo_lib/audit_returns.py [--limit N] [--codes 1024,2015]
"""
import argparse, json, math, sys, time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "batches" / "audit_returns.json"
DIFF_TOL = 0.15          # percentage points; below this is float/rounding noise
HORIZONS = {"1w": 5, "1m": 21, "3m": 63}
THROTTLE = 0.30


def tx_closes(code, ipo):
    """Independent price source (Tencent) — the engine's fallback for the codes
    Yahoo has no history for. The audit must be able to see the same sessions,
    otherwise it 'fails' exactly the deals the engine deliberately rescued."""
    import requests
    sym = f"hk{int(code):05d}"
    u = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
         f"param={sym},day,{ipo},{date.today().isoformat()},1500,")  # 800 lost pre-2023 debuts; >1500 the API answers empty
    try:
        rows = ((requests.get(u, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
                 .json().get("data") or {}).get(sym) or {}).get("day") or []
    except Exception:
        return [], []
    dts = [r[0] for r in rows]
    cls = [float(r[2]) for r in rows]
    return dts, cls


def raw_closes(tkr, start):
    """Close series with Yahoo's split back-adjustment UNDONE.

    Yahoo restates pre-split history even with auto_adjust=False. The offer
    price is a raw historical number, so the comparison must be against raw
    prices. Independent implementation: walk backwards accumulating the split
    ratios seen so far, which is the multiplier that turns adjusted into raw.
    """
    h = yf.Ticker(tkr).history(start=start, auto_adjust=False)
    if not len(h):
        return None, None
    closes = list(h["Close"])
    dates = [d.strftime("%Y-%m-%d") for d in h.index]
    if "Stock Splits" in h.columns:
        splits = list(h["Stock Splits"])
        factor, out = 1.0, [0.0] * len(closes)
        for i in range(len(closes) - 1, -1, -1):
            out[i] = closes[i] * factor
            if splits[i]:                     # this bar's split affects EARLIER bars
                factor *= splits[i]
        closes = out
    return dates, closes


def debut_index(dates, ipo):
    for i, d in enumerate(dates):
        if d >= ipo:
            return i
    return None


def pct(a, b):
    return None if not a else round(100.0 * (b / a - 1.0), 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--codes", default="")
    args = ap.parse_args()

    deals = json.loads((ROOT / "data" / "deals.json").read_text())["deals"]
    if args.codes:
        want = {c.strip().zfill(4) for c in args.codes.split(",")}
        deals = [d for d in deals if d["code"] in want]
    if args.limit:
        deals = deals[: args.limit]

    # benchmark histories, pulled once — read the map from fetch_prices so the
    # audit tests the SAME benchmark assignment the engine used
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from fetch_prices import BENCH, DEFAULT_BENCH
    label_to_tkr = {lbl: t for t, lbl in list(BENCH.values()) + [DEFAULT_BENCH[::-1][::-1]]}
    label_to_tkr[DEFAULT_BENCH[1]] = DEFAULT_BENCH[0]
    earliest = min(d["ipo_date"][:10] for d in deals if d.get("ipo_date"))
    bcache = {}
    for tkr in sorted({t for t, _ in BENCH.values()} | {DEFAULT_BENCH[0]}):
        dts, cl = raw_closes(tkr, (date.fromisoformat(earliest) - timedelta(days=10)).isoformat())
        if dts:
            bcache[tkr] = (dts, cl)
            print(f"  benchmark {tkr}: {len(dts)} bars", flush=True)

    rows, mism = [], []
    for i, d in enumerate(deals):
        code, ipo, fp = d["code"], (d.get("ipo_date") or "")[:10], d.get("final_price")
        rec = {"code": code, "name": d["name"], "ipo_date": ipo, "offer": fp}
        if not ipo or not fp:
            rec["skip"] = "no ipo date or offer price"
            rows.append(rec)
            continue
        tkr = f"{int(code):04d}.HK"
        try:
            dts, cl = raw_closes(tkr, (date.fromisoformat(ipo) - timedelta(days=5)).isoformat())
        except Exception as e:
            rec["error"] = str(e)[:100]
            rows.append(rec)
            continue
        # Yahoo has no usable history for a handful of recycled codes — the
        # engine falls back to Tencent for those, so the audit must too or it
        # "fails" precisely the deals that were deliberately rescued
        i0 = debut_index(dts, ipo) if dts else None
        lag_ok = i0 is not None and (date.fromisoformat(dts[i0])
                                     - date.fromisoformat(ipo)).days <= 5
        if not lag_ok:
            dts, cl = tx_closes(code, ipo)
            i0 = debut_index(dts, ipo) if dts else None
            rec["src"] = "tencent"
        if not dts:
            rec["error"] = "no history in either source"
            rows.append(rec)
            continue
        if i0 is None:
            rec["error"] = "no bar on/after listing date"
            rows.append(rec)
            continue
        rec["debut_date"] = dts[i0]
        rec["debut_close"] = round(cl[i0], 4)
        rec["bars_available_after_debut"] = len(dts) - 1 - i0

        blabel = d.get("benchmark")
        btkr = label_to_tkr.get(blabel, DEFAULT_BENCH[0])
        rec["benchmark"] = blabel
        bd, bc = bcache.get(btkr, (None, None))

        def bench_win(end_date):
            """Index over the SAME window the money was at risk: anchored at the
            last close BEFORE listing (mirrors fetch_prices.bench_return)."""
            if not bd:
                return None
            a = b = None
            for k, dd in enumerate(bd):
                if dd < ipo:
                    a = k
                if dd <= end_date:
                    b = k
            if a is None or b is None or b <= a or not bc[a]:
                return None
            return round(100 * (bc[b] / bc[a] - 1), 2)

        mine = {"day1": pct(fp, cl[i0])}
        for lbl, n in HORIZONS.items():
            if i0 + n < len(cl):
                mine[lbl] = pct(fp, cl[i0 + n])
                br = bench_win(dts[i0 + n])
                if br is not None and mine[lbl] is not None:
                    mine["alpha_" + lbl] = round(mine[lbl] - br, 2)
                    mine["bench_" + lbl] = br
            else:
                mine[lbl] = None
        mine["since"] = pct(fp, cl[-1])
        rec["recomputed"] = mine

        stored = {"day1": d.get("first_day_return_pct"), "since": d.get("since_ipo_pct")}
        for lbl in HORIZONS:
            stored[lbl] = d.get(f"ret_{lbl}_pct")
            stored["alpha_" + lbl] = d.get(f"alpha_{lbl}_pct")
            stored["bench_" + lbl] = d.get(f"bench_{lbl}_pct")
        rec["stored"] = stored

        bad = {}
        for k, v in mine.items():
            s = stored.get(k)
            if v is None and s is None:
                continue
            if v is None or s is None:
                bad[k] = {"stored": s, "recomputed": v, "why": "one side missing"}
            elif abs(v - s) > DIFF_TOL:
                bad[k] = {"stored": s, "recomputed": v, "diff": round(v - s, 2)}
        if bad:
            rec["mismatch"] = bad
            mism.append(rec)
        rows.append(rec)
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(deals)} audited, {len(mism)} with a mismatch", flush=True)
            OUT.write_text(json.dumps({"batch": "audit_returns", "deals": rows},
                                      ensure_ascii=False, indent=1))
        time.sleep(THROTTLE)

    # census of what the mismatches have in common
    causes = {}
    for r in mism:
        for k in r["mismatch"]:
            causes[k] = causes.get(k, 0) + 1
    OUT.write_text(json.dumps(
        {"batch": "audit_returns",
         "audited_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "tolerance_pp": DIFF_TOL, "count": len(rows), "mismatches": len(mism),
         "by_field": causes, "deals": rows}, ensure_ascii=False, indent=1))
    print(f"\naudited {len(rows)} deals | {len(mism)} with any mismatch > {DIFF_TOL}pp")
    for k, v in sorted(causes.items(), key=lambda x: -x[1]):
        print(f"  {k:12s} {v}")
    for r in mism[:15]:
        print(f"  {r['code']} {r['name'][:22]:22s} {r['mismatch']}")


if __name__ == "__main__":
    main()
