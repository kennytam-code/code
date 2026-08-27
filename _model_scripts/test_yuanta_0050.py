#!/usr/bin/env python3
"""Tab-splitting tests for yuanta_0050_pcf.

The real file only contains one index review, so the "a future rebalance opens
its own tab" behaviour cannot be proven from it.  These drive the same functions
with synthetic constituent histories, including a SECOND review.
"""

import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from yuanta_0050_pcf import matrix, persistent, split_regimes   # noqa: E402

D = [dt.date(2026, 6, 1) + dt.timedelta(days=i) for i in range(10)]


def frames_from(members, qty):
    """members: {date: [codes]} -> the (ric, code, ym, zh, en, kind, qty) rows."""
    return {d: [(c, c, "", "", "", "Stock", qty.get((d, c), 1_000_000)) for c in codes]
            + [("TXU6", "TX", "202609", "", "", "Future", 100)]
            for d, codes in members.items()}


def case(name, members, qty=None):
    mem = {d: frozenset(v) for d, v in members.items()}
    dates = sorted(mem)
    groups = split_regimes(dates, mem, mode="auto")
    _, res = persistent(dates, mem)
    frames = frames_from({d: sorted(mem[d]) for d in dates}, qty or {})
    tabs = []
    for g in groups:
        df, dropped = matrix(g, frames, res)
        tabs.append((f"{g[0]:%m%d}-{g[-1]:%m%d}",
                     sorted(r for r in df.RIC if str(r) != "TXU6"), dropped))
    print(f"\n{name}")
    for span, rics, dropped in tabs:
        print(f"  tab {span}: {rics}   dropped={dropped}")
    return tabs


ok = True


def expect(label, got, want):
    global ok
    good = got == want
    ok &= good
    print(f"  [{'PASS' if good else 'FAIL'}] {label}")
    if not good:
        print(f"         got  {got}\n         want {want}")


# ---------------------------------------------------------------- no change --
t = case("no rebalance -> one tab",
         {d: ["A", "B", "C"] for d in D[:5]})
expect("single tab", len(t), 1)
expect("all names kept", t[0][1], ["A", "B", "C"])

# ------------------------------------------------- one review, with residuals --
# D3 is the transition close: adds land in full, deletes linger as tails.
m = {D[0]: ["A", "B", "C"], D[1]: ["A", "B", "C"],
     D[2]: ["A", "B", "C", "D", "E"],
     D[3]: ["A", "D", "E"], D[4]: ["A", "D", "E"]}
t = case("one review -> two tabs, tails dropped", m,
         qty={(D[2], "B"): 900, (D[2], "C"): 700})
expect("two tabs", len(t), 2)
expect("tab 1 = pre-review set", t[0][1], ["A", "B", "C"])
expect("tab 2 opens on the transition date", t[1][0], f"{D[2]:%m%d}-{D[4]:%m%d}")
expect("tab 2 = post-review set only", t[1][1], ["A", "D", "E"])
expect("tails dropped from tab 2", t[1][2], ["B", "C"])
expect("tails NOT dropped from tab 1", t[0][2], [])

# ----------------------------------------------------------- SECOND review ---
m = {D[0]: ["A", "B", "C"], D[1]: ["A", "B", "C"],
     D[2]: ["A", "B", "C", "D", "E"],            # review 1 transition
     D[3]: ["A", "D", "E"], D[4]: ["A", "D", "E"],
     D[5]: ["A", "D", "E", "F"],                 # review 2 transition
     D[6]: ["A", "E", "F"], D[7]: ["A", "E", "F"]}
t = case("two reviews -> three tabs", m)
expect("three tabs", len(t), 3)
expect("tab 1", t[0][1], ["A", "B", "C"])
expect("tab 2", t[1][1], ["A", "D", "E"])
expect("tab 3", t[2][1], ["A", "E", "F"])
expect("review 2 tail dropped", t[2][2], ["D"])

# --------------------------------------------- deletion with no add at all ---
m = {D[0]: ["A", "B", "C"], D[1]: ["A", "B", "C"],
     D[2]: ["A", "B"], D[3]: ["A", "B"]}
t = case("pure deletion (delisting) still opens a tab", m)
expect("two tabs", len(t), 2)
expect("tab 2 drops the delisted name", t[1][1], ["A", "B"])

# ------------------------------------- last date must never look residual ----
m = {D[0]: ["A", "B"], D[1]: ["A", "B"], D[2]: ["A", "B"]}
t = case("final date is never treated as a residual", m)
expect("one tab, nothing dropped", (len(t), t[0][2]), (1, []))

print("\n" + ("ALL TESTS PASSED" if ok else "TEST FAILURES"))
sys.exit(0 if ok else 1)
