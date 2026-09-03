#!/usr/bin/env python3
"""Refine the proceeds fields of extracted_allotments.json. PIPELINE STAGE.

`extract_prospectus.py allotments` reads only the first 12 pages of each PDF,
and its proceeds regex took whichever "net proceeds ... HK$X million" sentence
came first — which for 50 deals was the GREENSHOE's "additional net proceeds"
(JD Logistics published at HK$3,632m against a real HK$24,113m) or a
use-of-proceeds bucket. This stage re-reads the FULL cached document text
(scrape/text_cache/allot_*.txt) and rewrites net/gross proceeds plus their
snippets. Every other key is left byte-identical, and a value it cannot better
is never blanked.

It runs as `patch-proceeds` in both ipo.py and the desk bundle, AFTER every
other writer of that batch. It began life as a one-off repair; leaving it
outside the pipeline meant the next plain `refresh` silently undid 165
corrected figures, so it is a stage.

Run:  python ipo_lib/patch_proceeds.py [--apply]
Without --apply it only reports what would change.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_prospectus import parse_proceeds          # noqa: E402

TEXT = ROOT / "scrape" / "text_cache"
BATCH = ROOT / "data" / "batches" / "extracted_allotments.json"


def texts_by_code():
    out = defaultdict(list)
    for p in sorted(TEXT.glob("allot_*.txt")):
        m = re.match(r"allot_(\d{4})_", p.name)
        if m:
            out[m.group(1)].append(p)
    return out


def main(apply_it):
    data = json.loads(BATCH.read_text())
    cache = texts_by_code()
    changed, unchanged, no_text = [], 0, []

    for rec in data["deals"]:
        code = rec["code"]
        paths = cache.get(code)
        if not paths:
            no_text.append(code)
            continue
        txt = "\n".join(p.read_text(errors="ignore") for p in paths)
        for key, kind in (("net_proceeds", "net"), ("gross_proceeds", "gross")):
            new, snip = parse_proceeds(txt, kind)
            old = rec.get(key + "_hkdm")
            if new is None:
                continue                      # never blank a value we already have
            if old is None or abs(new - old) / max(new, old) > 0.005:
                changed.append((code, key, old, new))
                if apply_it:
                    rec[key + "_hkdm"] = new
                    rec[key + "_snip"] = snip
            else:
                unchanged += 1

    print(f"deals with cached text: {len(data['deals']) - len(no_text)}"
          f" | no text: {len(no_text)}")
    print(f"values confirmed unchanged: {unchanged}")
    print(f"values corrected: {len(changed)}")
    for code, key, old, new in sorted(changed, key=lambda t: -(t[3] or 0))[:30]:
        ratio = f"x{new/old:,.1f}" if old else "was blank"
        print(f"  {code} {key:15} {str(old):>12} -> {new:>12,.1f}  ({ratio})")
    if len(changed) > 30:
        print(f"  ... {len(changed) - 30} more")

    if apply_it:
        data["proceeds_patch"] = ("net/gross re-parsed from the full-text cache "
                                  "with parse_proceeds(); greenshoe 'additional "
                                  "net proceeds' and use-of-proceeds buckets "
                                  "rejected")
        BATCH.write_text(json.dumps(data, ensure_ascii=False, indent=1))
        print(f"\nwrote {BATCH}")
    else:
        print("\n(dry run — pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main("--apply" in sys.argv))
