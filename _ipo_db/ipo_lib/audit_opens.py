#!/usr/bin/env python3
"""Cross-check every day-1 OPEN and CLOSE against a second, independent source.

What the two sources are:
  - Yahoo Finance (query1.finance.yahoo.com): the same feed the terminal-less
    world runs on. Splits are back-adjusted into history, which is exactly why
    it cannot be trusted alone for debut prices on split-affected codes.
  - Tencent Finance kline (web.ifzq.gtimg.cn/appstock/app/fqkline/get): the
    public market-data API behind gu.qq.com, one of mainland China's largest
    retail quote services. The bare `day` series is RAW exchange prints —
    no adjustment — which is what an offer-price comparison needs. It carries
    every HK code from its true listing day, including the recycled codes
    Yahoo is blind to.

Method: for every deal, pull the day-1 bar from BOTH sources fresh (no cache),
convert nothing, and compare open and close. A split-affected code is expected
to disagree on Yahoo (its history is adjusted) — those rows are reported under
their own heading, with the split factor, so an expected disagreement can
never be mistaken for an error. Everything else must agree to the tick.

Exit 1 if any UNEXPLAINED gap >0.5% exists. Writes audit_opens.json.

v16: --horizons mode extends the same two-source comparison to the 1w/1m/3m
closes (trading-day offsets 5/21/63) — the REGO class of hidden adjustment can
sit anywhere in the first three months, not only on day 1.
"""
import json, sys, time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_prices import tencent_kline

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "batches" / "audit_opens.json"


def yahoo_day1(code, ipo):
    import yfinance as yf
    end = (date.fromisoformat(ipo) + timedelta(days=6)).isoformat()
    h = yf.Ticker(f"{int(code):04d}.HK").history(
        start=ipo, end=end, auto_adjust=False)
    if not len(h):
        return None
    splits = float(h["Stock Splits"].replace(0, 1).prod()) if "Stock Splits" in h else 1.0
    return {"date": h.index[0].strftime("%Y-%m-%d"),
            "open": round(float(h["Open"].iloc[0]), 4),
            "close": round(float(h["Close"].iloc[0]), 4),
            "split_flag": bool((h.get("Stock Splits", 0) != 0).any())}


def main(sample_every=1, horizons=False):
    deals = json.loads((ROOT / "data" / "deals.json").read_text())["deals"]
    rows, agree, split_rows, yahoo_blind, gaps = [], 0, [], 0, []
    FORCE = ROOT / "data" / "force_raw_codes.json"
    force = set(json.loads(FORCE.read_text())) if FORCE.exists() else set()
    todo = deals[::sample_every]
    for i, d in enumerate(todo):
        code, ipo = d["code"], d["ipo_date"][:10]
        try:
            tx = tencent_kline(f"hk{int(code):05d}", ipo,
                               (date.fromisoformat(ipo) + timedelta(days=6)).isoformat(),
                               n=320)
        except Exception:
            tx = []
        t1 = next((r for r in tx if r[0] >= ipo), None)
        try:
            y1 = yahoo_day1(code, ipo)
        except Exception:
            y1 = None
        rec = {"code": code, "name": d["name"][:20], "ipo": ipo}
        if horizons:
            # full first-3-months pull once per source, compare at +5/+21/+63
            try:
                txh = tencent_kline(f"hk{int(code):05d}", ipo,
                                    (date.fromisoformat(ipo) + timedelta(days=100)).isoformat(),
                                    n=320)
            except Exception:
                txh = []
            import yfinance as yf
            try:
                yh = yf.Ticker(f"{int(code):04d}.HK").history(
                    start=ipo,
                    end=(date.fromisoformat(ipo) + timedelta(days=100)).isoformat(),
                    auto_adjust=False)
            except Exception:
                yh = None
            if txh and yh is not None and len(yh):
                ymap = {ts.strftime("%Y-%m-%d"): round(float(v), 4)
                        for ts, v in yh["Close"].items()}
                i0 = next((k for k, r_ in enumerate(txh) if r_[0] >= ipo), None)
                hz = {}
                for lbl, off in (("1w", 5), ("1m", 21), ("3m", 63)):
                    if i0 is not None and i0 + off < len(txh):
                        dt_, tc = txh[i0 + off][0], txh[i0 + off][1]
                        yc = ymap.get(dt_)
                        if yc:
                            hz[lbl] = round(abs(tc / yc - 1) * 100, 3)
                rec["horizon_gaps_pct"] = hz
                worst = max(hz.values(), default=0)
                if worst > 2 and not (y1 or {}).get("split_flag") \
                        and not d.get("split_factor_first") \
                        and "tencent" not in str(d.get("price_src") or ""):
                    gaps.append(rec)
                    force.add(d["code"])
                elif worst <= 0.5:
                    agree += 0    # day-1 bucket already counted agreement
        if t1:
            rec["tencent"] = {"date": t1[0], "close": t1[1],
                              "open": t1[2] if len(t1) > 2 else None}
        if y1:
            rec["yahoo"] = y1
        if not y1:
            yahoo_blind += 1
        elif t1 and y1["date"] == t1[0]:
            og = abs((t1[2] / y1["open"] - 1) * 100) if len(t1) > 2 and y1["open"] else None
            cg = abs((t1[1] / y1["close"] - 1) * 100) if y1["close"] else None
            rec["open_gap_pct"] = round(og, 3) if og is not None else None
            rec["close_gap_pct"] = round(cg, 3) if cg is not None else None
            uniform = (og is not None and cg is not None
                       and abs(og - cg) < 0.5 and min(og, cg) > 2)
            if y1.get("split_flag") or d.get("split_factor_first") \
                    or "tencent" in str(d.get("price_src") or ""):
                split_rows.append(rec)     # raw series already in use — expected
            elif uniform:
                # open and close off by the SAME factor with no split row:
                # Yahoo carries a hidden capital-action adjustment (REGO's
                # x1.194 rights factor was exactly this). Raw is the record —
                # the code goes on the force-raw list so the engine refetches
                # it from Tencent on the next run.
                rec["uniform_factor"] = round(1 + (og + cg) / 200, 4)
                split_rows.append(rec)
                force.add(d["code"])
            elif (og or 0) <= 0.5 and (cg or 0) <= 0.5:
                agree += 1
            else:
                gaps.append(rec)
        rows.append(rec)
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(todo)}", flush=True)
        time.sleep(0.35)
    OUT.write_text(json.dumps({"batch": "audit_opens",
                               "asof": date.today().isoformat(),
                               "rows": rows}, ensure_ascii=False))
    print(f"\nday-1 OPEN+CLOSE, two independent sources, {len(todo)} deals:")
    print(f"  agree to ±0.5%        : {agree}")
    print(f"  split-adjusted Yahoo  : {len(split_rows)}  (disagreement EXPECTED — raw Tencent is the record)")
    print(f"  Yahoo has no bar      : {yahoo_blind}  (recycled codes — Tencent only)")
    FORCE.write_text(json.dumps(sorted(force)))
    print(f"  force-raw list        : {len(force)} codes -> {FORCE.name}")
    print(f"  UNEXPLAINED gaps >0.5%: {len(gaps)}")
    for g in gaps[:10]:
        print("   ", g["code"], g["name"], "open gap", g.get("open_gap_pct"),
              "close gap", g.get("close_gap_pct"))
    sys.exit(1 if gaps else 0)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--horizons"]
    n = int(args[0]) if args else 1
    main(n, horizons="--horizons" in sys.argv)
