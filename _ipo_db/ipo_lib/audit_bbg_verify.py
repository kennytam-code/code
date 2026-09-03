#!/usr/bin/env python3
"""Reconcile EVERY number against the desk Bloomberg terminal.

The desk ran the Verify (BBG) tab on 2026-08-26 and returned Bloomberg's own
PX_LAST for each deal's listing session. Those readings are frozen in
data/batches/bbg_verify_results.json and reconciled here on every build, so a
disagreement with Bloomberg can never sit unnoticed again.

The comparison is on BLOOMBERG'S BASIS, which is not ours:

    our raw listing-day print  ÷  cumulative BBG factor  ==  BBG's print

where the factor compounds (a) price-scale actions — subdivisions,
consolidations, bonus issues, which re-scale the traded print — and (b)
entitlement issues — rights and open offers, which do NOT re-scale the print
but which Bloomberg back-adjusts by the TERP ratio. Both are held in the
JSON files corp_actions.py loads.

This gate is what caught WellCell: the loader was replacing one corporate
action with another instead of compounding them, and Bloomberg's number was
the evidence (2.640 / 8 = 0.330, not 2.640 / 4).

Rows Bloomberg could not price (Invalid Security / no history) are reported
and skipped, never counted as agreement.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from corp_actions import load_actions, load_entitlements, bbg_factor  # noqa: E402

TOL = 0.005          # 0.5% — covers Bloomberg's own rounding to 3dp


def main():
    fx = ROOT / "data" / "batches" / "bbg_verify_results.json"
    if not fx.exists():
        print("audit_bbg_verify: no terminal fixture on file — skipping")
        return 0
    fixture = json.loads(fx.read_text())
    deals = {d["code"]: d for d in
             json.loads((ROOT / "data" / "deals.json").read_text())["deals"]}
    acts, ent = load_actions(ROOT), load_entitlements(ROOT)

    checked = agreed = 0
    unpriceable, mismatch, missing = [], [], []

    for row in fixture["listing_close"] + fixture["action_close"]:
        c = row["code"]
        d = deals.get(c)
        bbg = row.get("bbg")
        if bbg is None:
            unpriceable.append(f"{c} {row['name'][:16]}: Bloomberg returned no price")
            continue
        if not d:
            missing.append(f"{c} {row['name'][:16]}: not in the book")
            continue
        fp, d1 = d.get("final_price"), d.get("first_day_return_pct")
        if fp is None or d1 is None:
            missing.append(f"{c} {row['name'][:16]}: no offer price / day-1 on file")
            continue
        ours_raw = fp * (1 + d1 / 100)             # our listing-day close
        f = bbg_factor(c, acts, ent)
        expected = ours_raw / f
        checked += 1
        if abs(expected / bbg - 1) <= TOL:
            agreed += 1
        else:
            mismatch.append(
                f"{c} {d['name'][:16]}: ours {ours_raw:,.3f} ÷ {f:g} = "
                f"{expected:,.3f} vs Bloomberg {bbg:,.3f} "
                f"(implied factor {ours_raw / bbg:.4f})")
        # the stored listing DATE must equal the one the terminal priced
        if row.get("date") and d.get("ipo_date", "")[:10] != row["date"]:
            mismatch.append(f"{c} {d['name'][:16]}: listing date {d.get('ipo_date')} "
                            f"vs terminal {row['date']}")

    print(f"audit_bbg_verify: {checked} rows reconciled against the terminal "
          f"({fixture.get('asof')})")
    print(f"  AGREE  {agreed}/{checked}")
    for m in mismatch:
        print(f"  FAIL   {m}")
    for m in missing[:6]:
        print(f"  note   {m}")
    if unpriceable:
        print(f"  note   {len(unpriceable)} rows Bloomberg could not price "
              f"(delisted / recycled codes) — skipped, not counted as agreement")
    print("  RESULT:", "CLEAN" if not mismatch else f"{len(mismatch)} PROBLEMS")
    return 1 if mismatch else 0


if __name__ == "__main__":
    sys.exit(main())
