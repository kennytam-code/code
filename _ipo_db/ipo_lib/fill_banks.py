#!/usr/bin/env python3
"""Sponsors and bookrunners for deals whose stored parse has none.

extract_deep reads the prospectus's "PARTIES INVOLVED IN THE GLOBAL OFFERING"
section for the whole book, but a full pass on an iCloud-evicted cache runs
for hours and was killed before it wrote. This reads ONLY the deals that
still lack a list, with the same parser and the same role rules (a
Sponsor-Overall Coordinator is a bookrunner, not a second sponsor), scrubbed by
clean_party_list, and writes data/banks_fill.json (tracked). merge_batches.py
reads it at priority 50: above AAStocks' underwriter fallback, below a
hand-verified list.

usage:
    python ipo_lib/fill_banks.py            # every deal without bookrunners
    python ipo_lib/fill_banks.py 1855 1490  # named deals
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_deep as X                      # noqa: E402
from clean_names import clean_party_list      # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "banks_fill.json"


def banks(txt):
    syn = X.parse_syndicate(txt) or {}
    sp, br = [], []
    for role, names in syn.items():
        if re.search(r"sponsor", role, re.I) and not re.search(
                r"coordinator|bookrunner|lead manager", role, re.I):
            sp += [b for b in names if b not in sp]
        if re.search(r"bookrunner|global coordinator|overall coordinator", role, re.I):
            br += [b for b in names if b not in br]
    return clean_party_list(sp), clean_party_list(br)[:14]


def main(argv):
    deals = {d["code"]: d for d in json.loads((ROOT / "data" / "deals.json").read_text())["deals"]}
    links = {e["code"]: e for e in json.loads((ROOT / "data" / "batches" /
                                                "hkex_prospectus_links.json").read_text())["deals"]}
    want = [a.zfill(4) for a in argv if a[:1].isdigit()] or \
        [c for c, d in deals.items() if not d.get("bookrunners")]
    prev = {r["code"]: r for r in json.loads(OUT.read_text())["deals"]} if OUT.exists() else {}
    got = 0
    for n, c in enumerate(sorted(want)):
        parts = [p["file"] if isinstance(p, dict) else p for p in (links.get(c, {}).get("parts") or [])]
        txt = "\n".join(X.read_cached(f) for f in parts)
        if not txt:
            continue
        sp, br = banks(txt)
        if not (sp or br):
            continue
        rec = {"code": c, "src": "prospectus: Parties involved in the Global Offering"}
        if sp:
            rec["sponsors"] = sp
        if br:
            rec["bookrunners"] = br
        prev[c] = rec
        got += 1
        if n % 20 == 0:
            print(f"  {n}/{len(want)}", flush=True)
    OUT.write_text(json.dumps({"note": "sponsors / bookrunners re-read from each prospectus's parties "
                                       "section; see ipo_lib/fill_banks.py",
                               "deals": sorted(prev.values(), key=lambda r: r["code"])},
                              ensure_ascii=False, indent=1))
    print(f"banks fill: {got} of {len(want)} deals gained a list -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1:])
