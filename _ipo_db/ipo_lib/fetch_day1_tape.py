#!/usr/bin/env python3
"""The listing-day tape: open, high, low, close and VOLUME for every deal.

The returns batch keeps the open and the close; it never kept the volume,
and volume against the retail float is the one number that separates a
day-one pop that was BOUGHT from one that was DISTRIBUTED. Tencent's raw daily
kline carries it: [date, open, close, high, low, volume(shares)].

Writes data/batches/day1_tape.json:
  day1_open / day1_high / day1_low / day1_close   HK$
  day1_volume                                      shares
  day1_turnover_hkdm                               volume x VWAP-proxy (OHLC mean), HK$m
  day1_range_pct                                   (high - low) / open

Supports --only / --new. One call per deal; ~2 s each on a warm connection.
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "batches" / "day1_tape.json"


def kline_first_bar(symbol, ipo, tries=3):
    import requests
    d1 = ipo
    d2 = ipo
    u = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
         f"param={symbol},day,{d1},{d2},5,")
    for k in range(tries):
        try:
            j = requests.get(u, timeout=20).json()
            node = j["data"][symbol]
            rows = node.get("day") or node.get("qfqday") or []
            if rows:
                return rows
        except Exception:
            pass
        time.sleep(1.5 * (k + 1))
    return []


def yahoo_first_bar(code, ipo):
    """Yahoo's daily bar for the listing day: (open, high, low, close, volume)
    or None. Used when Tencent throttles (it answers HTTP 501 after ~300
    rapid calls) — Yahoo's volume is share volume too, same basis."""
    try:
        import yfinance as yf
        from datetime import datetime, timedelta
        d0 = datetime.fromisoformat(ipo)
        h = yf.Ticker(f"{int(code):04d}.HK").history(
            start=d0.strftime("%Y-%m-%d"), end=(d0 + timedelta(days=4)).strftime("%Y-%m-%d"),
            auto_adjust=False)
        if not len(h):
            return None
        first = h.index[0].strftime("%Y-%m-%d")
        if first != ipo:
            return None
        r = h.iloc[0]
        return (float(r["Open"]), float(r["High"]), float(r["Low"]), float(r["Close"]),
                float(r["Volume"]))
    except Exception:
        return None


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import incremental
    deals = json.loads((ROOT / "data" / "deals.json").read_text())["deals"]
    only = incremental.wanted(OUT, [d["code"] for d in deals])
    rows = [d for d in deals if d.get("ipo_date") and (only is None or d["code"] in only)]
    if only is not None:
        print(f"  incremental: {len(rows)} deal(s) to fetch")
    recs, miss = [], 0
    for i, d in enumerate(rows):
        code, ipo = d["code"], d["ipo_date"][:10]
        bars = kline_first_bar(f"hk{int(code):05d}", ipo)
        bar = next((b for b in bars if str(b[0])[:10] == ipo), None)
        src = "tencent"
        if bar:
            try:
                o, c, h, l, v = (float(bar[1]), float(bar[2]), float(bar[3]), float(bar[4]),
                                 float(bar[5]))
            except (IndexError, ValueError):
                bar = None
        if not bar:
            yb = yahoo_first_bar(code, ipo)
            if not yb:
                miss += 1
                continue
            o, h, l, c, v = yb
            src = "yahoo"
        rec = {"code": code, "date": ipo, "day1_open": o, "day1_high": h, "day1_low": l,
               "day1_close": c, "day1_volume": v, "src": src}
        if v and o:
            rec["day1_turnover_hkdm"] = round(v * (o + h + l + c) / 4 / 1e6, 2)
            rec["day1_range_pct"] = round(100 * (h - l) / o, 2)
        recs.append(rec)
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(rows)}", flush=True)
            OUT.write_text(json.dumps({"batch": "day1_tape", "partial": True,
                                       "deals": incremental.merge(OUT, recs, only)},
                                      ensure_ascii=False))
        time.sleep(0.6)
    recs = incremental.merge(OUT, recs, only)
    OUT.write_text(json.dumps(
        {"batch": "day1_tape", "note": __doc__.split("\n\n")[1].strip(),
         "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(recs), "deals": recs}, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {len(recs)} deals with a listing-day bar, {miss} without")


if __name__ == "__main__":
    main()
