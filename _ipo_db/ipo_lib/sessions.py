#!/usr/bin/env python3
"""The real Hong Kong trading calendar, derived from the book itself.

The kline feed inserts a PLACEHOLDER bar on days the exchange never opened —
it repeats the previous close for every stock. Typhoon Talim shut HKEX for
the whole of 2023-07-17 and Saola for 2023-09-01, and both days carry bars.

Two things went wrong because of that:
  * counting a placeholder as a session shifts every trading-bar horizon by
    a day (Yahoo, which omits those days, was right all along);
  * a listing scheduled INTO a closed day gets a placeholder bar at the offer
    price, which reads as a debut that closed exactly flat. New Media Lab's
    listing was postponed to the next session by the typhoon.

The test needs no external calendar: on a closed day EVERY stock's bar
repeats its prior close, so a date where several deals have bars and NONE of
them moved was not a trading day.
"""
from datetime import date, timedelta

MIN_BARS = 5          # enough stocks to judge the day at all


def _dated(rec):
    """[(offset, close), ...] -> [(iso_date, close), ...]"""
    ipo = (rec.get("ipo") or "")[:10]
    if not ipo:
        return []
    d0 = date.fromisoformat(ipo)
    return [((d0 + timedelta(days=off)).isoformat(), v)
            for off, v in (rec.get("closes") or []) if v]


def closed_days(path_records):
    """Dates the exchange did not open, inferred from book-wide flatness."""
    same, moved, seen = {}, {}, {}
    for rec in path_records:
        rows = _dated(rec)
        for i in range(1, len(rows)):
            d, v = rows[i]
            seen[d] = seen.get(d, 0) + 1
            if abs(v - rows[i - 1][1]) < 1e-9:
                same[d] = same.get(d, 0) + 1
            else:
                moved[d] = moved.get(d, 0) + 1
    return {d for d, n in seen.items()
            if n >= MIN_BARS and moved.get(d, 0) == 0 and same.get(d, 0) == n}


def real_sessions(rec, closed):
    """A deal's bars with placeholder days removed, as (iso_date, close)."""
    return [(d, v) for d, v in _dated(rec) if d not in closed]
