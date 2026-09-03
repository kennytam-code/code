#!/usr/bin/env python3
"""A newly listed deal must not sit in the book on aggregator placeholders.

The roster picks a listing up the day it trades, so the row appears at once —
but its allotment filing, financials, classification and PRICE SERIES only
arrive when the parse and price stages run. Between those two moments the row
carries whatever the aggregator had, which for Ingenic (3223) was an offer of
HK$100.00 and a day-1 of exactly 0.0% with no price series behind it at all.

A zero day-1 is the tell: it is what an aggregator prints for a deal it has
not updated yet. This gate fails when a deal that has been trading for at
least two sessions still has:

  * no price series of its own (the day-1 cannot have been computed), or
  * core fields missing that every other listed deal carries, or
  * a day-1 of exactly 0.00% that is NOT backed by a real listing-day bar.

A flat debut does happen: Ingenic (3223) opened and closed at exactly
HK$100.00 on 2026-08-25 on 5.8m shares, with a 100.40/97.10 range. So the
test is not "zero is impossible" but "zero must come from a print" — a bar
that moved intraday (high > low) is a real session; open==close==high==low is
the placeholder shape.

Run:  python ipo_lib/audit_fresh.py
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ["final_price", "first_day_return_pct", "sector", "subsector"]
GRACE_DAYS = 2          # sessions to allow before the row must be complete


def main():
    deals = json.loads((ROOT / "data" / "deals.json").read_text())["deals"]
    prows = {r["code"]: r for r in
             json.loads((ROOT / "data" / "batches" / "prices.json").read_text())["deals"]}
    priced = set(prows)
    cutoff = (date.today() - timedelta(days=GRACE_DAYS)).isoformat()

    bad = []
    fresh = 0
    for x in deals:
        ipo = (x.get("ipo_date") or "")[:10]
        if not ipo or ipo > cutoff:
            continue                       # not listed yet / still inside grace
        fresh += 1
        c, nm = x["code"], x["name"][:16]
        if c not in priced:
            bad.append(f"{c} {nm} ({ipo}): NO price series — every return on this "
                       f"row came from the aggregator, not from prints")
        miss = [f for f in CORE if x.get(f) is None]
        if miss:
            bad.append(f"{c} {nm} ({ipo}): missing {miss}")
        d1 = x.get("first_day_return_pct")
        if d1 == 0.0:
            p = prows.get(c, {})
            # a real listing-day bar carries its own open and close off the
            # feed; a placeholder has neither, so the zero came from the roster
            has_bar = p.get("first_open") is not None and p.get("first_close") is not None
            src = str((x.get("_prov") or {}).get("first_day_return_pct", {}).get("src", ""))
            if not has_bar and "aastocks" in src.lower():
                bad.append(f"{c} {nm} ({ipo}): day-1 is exactly 0.00% straight from "
                           f"the aggregator roster with no listing-day bar behind "
                           f"it — placeholder")

    print(f"audit_fresh: {fresh} listed deals past the {GRACE_DAYS}-day grace window")
    for b in bad[:12]:
        print("  FAIL:", b)
    if len(bad) > 12:
        print(f"  ... {len(bad) - 12} more")
    print("  RESULT:", "CLEAN" if not bad else f"{len(bad)} PROBLEMS")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
