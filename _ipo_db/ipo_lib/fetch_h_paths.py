#!/usr/bin/env python3
"""Daily H-line closes for the first three months of EVERY deal.

The screener's price-path panels previously existed only for A/H pairs (whose
daily paths ride in ah_paths.json). A comp without an A-share showed nothing —
the user wants the offer→3m price action for every chosen comp. Tencent's raw
kline covers all 511 codes from the true listing day (the same source that
rescued the recycled-code and split-corrupted debuts), so this batch stores a
compact [days-since-ipo, close] series per deal, clipped to ~3 months.

Storage: closes rounded to 4 significant figures; a completed window (>110
calendar days old) is immutable and never refetched.

Cross-check: for a sample of codes the 1m point is compared against yfinance
over the identical date; a systematic mismatch prints loudly instead of being
silently embedded.
"""
import json, math, sys, time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_prices import tencent_kline

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "batches" / "h_paths.json"
WINDOW_DAYS = 100          # calendar span fetched (≈ 3 months of sessions)
DONE_AFTER = 110           # window is closed and the record becomes immutable


def sig4(x):
    if not x:
        return x
    return round(x, max(0, 3 - int(math.floor(math.log10(abs(x))))))


def main():
    deals = json.loads((ROOT / "data" / "deals.json").read_text())["deals"]
    cache = {}
    if OUT.exists():
        cache = {r["code"]: r for r in json.loads(OUT.read_text())["deals"]}
    recs, fetched = [], 0
    for i, d in enumerate(deals):
        code, ipo = d["code"], (d.get("ipo_date") or "")[:10]
        if not ipo:
            continue
        prev = cache.get(code)
        # cache coherence on the LISTING DATE, not just completeness: a record
        # fetched while deals.json still carried the SCHEDULED date of a
        # typhoon-postponed listing is anchored on the exchange's placeholder
        # bar — New Media Lab (1284) cached open0 = 0.92 (the offer echoed
        # back) instead of the real 0.88 first print, and "complete" kept it
        # frozen forever. Once the merge corrects ipo_date, the stored anchor
        # no longer matches and the path must be refetched from the real day.
        if prev and prev.get("complete") and prev.get("ipo") == ipo:
            recs.append(prev)
            continue
        end = (date.fromisoformat(ipo) + timedelta(days=WINDOW_DAYS)).isoformat()
        try:
            tx = tencent_kline(f"hk{int(code):05d}", ipo, end, n=320)
        except Exception:
            tx = []
        rows = [(r_[0], r_[1], (r_[2] if len(r_) > 2 else None))
                for r_ in tx if ipo <= r_[0] <= end]
        # raw Tencent prints carry subdivisions unadjusted (CIDI 1->10) —
        # apply the evidence-backed manual corrections so the path stays in
        # offer terms
        from fetch_prices import MANUAL_SPLITS
        for ev in MANUAL_SPLITS.get(str(code), []):
            rows = [(dt, px * ev["ratio"] if dt >= ev["date"] else px,
                     (op * ev["ratio"] if op and dt >= ev["date"] else op))
                    for dt, px, op in rows]
        rec = {"code": code, "ipo": ipo,
               "closes": [[(date.fromisoformat(dt) - date.fromisoformat(ipo)).days,
                           sig4(px)] for dt, px, _o in rows],
               # the true day-1 OPEN, straight from the same kline row — the
               # ex-pop "tradeable entry" panels rebase on this
               "open0": sig4(rows[0][2]) if rows and rows[0][2] else None,
               "complete": bool(rows)
               and (date.today() - date.fromisoformat(ipo)).days > DONE_AFTER}
        if not rows:
            rec["note"] = "Tencent kline returned no bars in the listing window"
        recs.append(rec)
        cache[code] = rec
        fetched += 1
        if fetched % 25 == 0:
            print(f"  {fetched} fetched ({i+1}/{len(deals)} scanned)", flush=True)
            OUT.write_text(json.dumps({"batch": "h_paths", "deals": recs
                                       + [c for k, c in cache.items()
                                          if k not in {r['code'] for r in recs}]},
                                      ensure_ascii=False))
        time.sleep(0.6)
    OUT.write_text(json.dumps({"batch": "h_paths",
                               "asof": date.today().isoformat(),
                               "deals": recs}, ensure_ascii=False))
    with_data = sum(1 for r in recs if r["closes"])
    print(f"wrote {OUT}: {len(recs)} deals, {with_data} with bars "
          f"({fetched} fetched fresh)")

    # ---- yfinance cross-check on a sample: same code, same calendar date ----
    try:
        import yfinance as yf
        import pandas as pd
        sample = [r for r in recs if len(r["closes"]) >= 22][:400:80]
        bad = 0
        for r in sample:
            off, px = r["closes"][21][:2]
            dt = (date.fromisoformat(r["ipo"]) + timedelta(days=off))
            h = yf.Ticker(f"{int(r['code']):04d}.HK").history(
                start=dt.isoformat(), end=(dt + timedelta(days=1)).isoformat(),
                auto_adjust=False)
            if len(h):
                ypx = float(h["Close"].iloc[0])
                gap = abs(px / ypx - 1) * 100
                tag = "OK" if gap < 3 else "SPLIT/ADJ DIFF" if gap > 20 else "CHECK"
                if tag != "OK":
                    bad += 1
                print(f"  xcheck {r['code']} @{dt}: tencent {px} vs yahoo "
                      f"{round(ypx,3)} ({gap:.2f}% apart) [{tag}]")
        print(f"  cross-check: {len(sample)} sampled, {bad} flagged "
              f"(flags on split-adjusted Yahoo series are expected)")
    except Exception as e:
        print("  cross-check skipped:", str(e)[:80])


if __name__ == "__main__":
    main()
