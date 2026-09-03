#!/usr/bin/env python3
"""Find corporate actions that RAW price prints carry unadjusted.

Why this exists: Yahoo back-adjusts history for splits, so whenever it reports
a split for a code we discard its series and rebuild from raw Tencent prints
(Yahoo double-records some actions — the Zhida lesson). But raw prints are
exactly that: RAW. A 1-into-10 subdivision divides every later print by ten,
and nothing put it back. CIDI's "3-month -91%" was that, not a crash.

The detector never trusts one source:
  1. CANDIDATE — Yahoo's split rows dated on/after the listing date.
  2. VERIFY   — the raw Tencent series must actually show a matching jump
                within a few sessions of that date. The jump's own date is
                what gets recorded (prints divide when DEALING in the new
                shares starts, which is days after the "effective" date).
  3. UNVERIFIED candidates are reported and NOT applied — a correction that
     the price series itself cannot demonstrate would be an invention.

Writes data/auto_splits.json. Hand-curated data/manual_splits.json wins on
any code it names.
"""
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_prices import tencent_kline                      # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "auto_splits.json"
NEAR = 12          # sessions either side of the reported date to look in
TOL = 0.25         # measured vs reported ratio agreement


def raw_series(code, ipo):
    try:
        return tencent_kline(f"hk{int(code):05d}", ipo, date.today().isoformat())
    except Exception:
        return []


def find_jump(rows, when, ratio):
    """Locate the session where the raw series changes scale by `ratio`.

    Returns (date, measured_ratio) or None. A subdivision of 10 makes prints
    fall to a tenth, so the measured ratio is prev/next.
    """
    idx = [i for i, r in enumerate(rows) if r[0] >= when]
    if not idx:
        return None
    at = idx[0]
    best = None
    for i in range(max(1, at - NEAR), min(len(rows), at + NEAR + 1)):
        a, b = rows[i - 1][1], rows[i][1]
        if not a or not b:
            continue
        measured = a / b                       # >1 for a subdivision
        want = ratio if ratio >= 1 else 1 / ratio
        got = measured if ratio >= 1 else 1 / measured
        if want and abs(got / want - 1) <= TOL:
            score = abs(got / want - 1)
            if best is None or score < best[2]:
                best = (rows[i][0], measured, score)
    return (best[0], best[1]) if best else None


def main():
    prices = {r["code"]: r for r in
              json.loads((ROOT / "data" / "batches" / "prices.json").read_text())["deals"]}
    deals = {d["code"]: d for d in
             json.loads((ROOT / "data" / "deals.json").read_text())["deals"]}
    # only RAW-print sources can carry an unadjusted action
    codes = sorted(c for c, r in prices.items()
                   if str(r.get("price_src", "")).startswith("tencent"))
    print(f"scanning {len(codes)} raw-print deals for unadjusted corporate actions")
    import yfinance as yf
    out, unverified = {}, []
    for c in codes:
        ipo = (deals.get(c, {}).get("ipo_date") or "")[:10]
        if not ipo:
            continue
        try:
            sp = yf.Ticker(f"{int(c):04d}.HK").splits
        except Exception as e:
            print(f"  {c}: yahoo error {e}")
            continue
        # a code Yahoo does not carry answers None, not an empty series
        cands = ([(str(d.date()), float(v)) for d, v in sp.items()
                  if str(d.date()) >= ipo] if sp is not None and len(sp) else [])
        if not cands:
            continue
        rows = raw_series(c, ipo)
        if len(rows) < 10:
            unverified.append((c, "raw series unavailable", cands))
            continue
        events = []
        for when, ratio in cands:
            hit = find_jump(rows, when, ratio)
            nm = deals.get(c, {}).get("name", "?")[:16]
            if hit:
                seen_date, measured = hit
                events.append({"date": seen_date, "ratio": ratio,
                               "src": f"yahoo split row {when} x{ratio} VERIFIED "
                                      f"against raw kline (prints change scale "
                                      f"{measured:.3f}x on {seen_date})"})
                print(f"  {c} {nm:16s} {when} x{ratio} -> jump seen {seen_date} "
                      f"(measured {measured:.2f}) APPLY")
            else:
                unverified.append((c, when, ratio))
                print(f"  {c} {nm:16s} {when} x{ratio} -> no matching jump in raw "
                      f"prints — NOT applied")
        if events:
            out[c] = events
        time.sleep(0.4)
    payload = {"_note": "AUTO-DETECTED corporate actions that raw prints carry "
                        "unadjusted: Yahoo split row + a verified scale change "
                        "in the raw Tencent series. Regenerate with "
                        "ipo_lib/detect_splits.py. Hand-curated "
                        "data/manual_splits.json wins per code.",
               "_generated": date.today().isoformat(),
               "_unverified": [{"code": u[0], "reported": u[1], "ratio": u[2]}
                               for u in unverified]}
    payload.update(out)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    print(f"\nwrote {OUT}: {len(out)} deals need correction, "
          f"{len(unverified)} unverified candidates left alone")


if __name__ == "__main__":
    main()
