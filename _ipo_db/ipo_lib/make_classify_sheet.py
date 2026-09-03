#!/usr/bin/env python3
"""Emit a compact one-line-per-deal sheet for sector/subsector classification.

  <code> <short name> | <full name> | <business overview, trimmed>

Classification is a human/analyst judgment against data/taxonomy.json; this
script only assembles the evidence. Output: scratch/classify_input.txt
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "data" / "batches"
OUT = ROOT / "data" / "classify_input.txt"

WIDTH = int(sys.argv[1]) if len(sys.argv) > 1 else 105


def main():
    roster = json.loads((B / "hkex_allotments.json").read_text())["deals"]
    prof = {}
    p = B / "extracted_profiles.json"
    if p.exists():
        prof = {r["code"]: r for r in json.loads(p.read_text())["deals"]}
    lines = []
    for d in sorted([x for x in roster if x["board"] == "Main"],
                    key=lambda x: x["ipo_date_est"]):
        c = d["code"]
        pr = prof.get(c, {})
        full = (pr.get("name_full") or "").strip()
        short = d["stock_name_short"]
        if full and full.upper().replace(" ", "")[:8] == short.upper().replace(" ", "")[:8]:
            full = ""                      # same name twice adds nothing
        ov = re.sub(r"\s+", " ", pr.get("overview") or "")
        ov = re.sub(r"^(?:We are|We were|Our Group is|The Group is|Our Company is)\s+", "", ov)
        lines.append(f"{c} {short[:22]:22s}|{full[:30]:30s}|{ov[:WIDTH]}")
    OUT.write_text("\n".join(lines))
    got = sum(1 for l in lines if l.rsplit("|", 1)[-1].strip())
    print(f"wrote {OUT}: {len(lines)} deals, {got} with an overview")


if __name__ == "__main__":
    main()
