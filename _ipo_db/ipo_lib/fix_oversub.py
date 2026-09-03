#!/usr/bin/env python3
"""Re-extract public / international subscription levels into
data/batches/extracted_allotments.json.

Two document layouts exist and both are parsed; the method that produced each
value is recorded in oversub_method so the merge can rank it:

  "table"  standardised summary:  PUBLIC OFFER ... Subscription level <N> times
                                  INTERNATIONAL OFFER ... Subscription Level <N> times
  "prose"  narrative:  "<N> times of the total number of <n> Public Offer Shares"

The first version of this script deleted any value it could not re-match, which
destroyed ~470 good rows. It now only ever writes a value it positively matched
and leaves anything else untouched.
"""
import json, re
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scrape" / "pdf_cache"
TARGET = ROOT / "data" / "batches" / "extracted_allotments.json"

NUM = r"[\d,]+(?:\.\d+)?"
SEC_PUB = re.compile(r"(?:HONG KONG )?PUBLIC OFFER(?:ING)?\b", re.I)
SEC_INT = re.compile(r"INTERNATIONAL (?:OFFER|PLACING)(?:ING)?\b", re.I)
SUBLEVEL = re.compile(rf"Subscription\s+level\s+({NUM})\s+times", re.I)
PROSE_PUB = re.compile(
    rf"({NUM})\s*times\s+(?:of\s+)?the\s+(?:total\s+)?number\s+of\s+[\d,]+\s+"
    rf"(?:Hong\s+Kong\s+)?(?:Public\s+)?Offer\s+Shares", re.I)
# fallback without the explicit share count, still anchored on the HK tranche
PROSE_PUB2 = re.compile(
    rf"({NUM})\s*times\s+(?:of\s+)?the\s+(?:total\s+)?number\s+of\s+"
    rf"(?:the\s+)?(?:Hong\s+Kong\s+)?(?:Public\s+)?Offer\s+Shares\s+initially\s+"
    rf"available[^.]{{0,80}}?(?:Hong\s+Kong\s+Public\s+Offer|Public\s+Offer)", re.I)
PROSE_INT = re.compile(
    rf"({NUM})\s*times\s+(?:of\s+)?the\s+(?:total\s+)?number\s+of\s+[\d,]+\s+"
    rf"(?:International\s+(?:Offer|Placing)|Placing)\s+Shares", re.I)
# The common wording carries no share count: "The Offer Shares initially offered
# under the International Offering have been slightly over-subscribed,
# representing approximately 1.05 times ...". Recovers 141 of 202 misses.
PROSE_INT2 = re.compile(
    rf"(?:International\s+Offering|International\s+Placing|the\s+Placing)"
    rf"[^.]{{0,240}}?(?:over-?\s?subscribed|under-?\s?subscribed|subscribed)"
    rf"[^.]{{0,80}}?representing\s+approximately\s+({NUM})\s*times", re.I)
# under-subscription is DATA, not a gap: "...under-subscribed, representing
# approximately 95.6% of the total number of ... Placing Shares" -> 0.956x
PROSE_INT_UNDER = re.compile(
    rf"(?:International\s+Offering|International\s+Placing|the\s+Placing)"
    rf"[^.]{{0,240}}?under-?\s?subscribed[^.]{{0,90}}?representing\s+"
    rf"(?:approximately\s+)?({NUM})\s*%", re.I)
PROSE_PUB_UNDER = re.compile(
    rf"(?:Hong\s+Kong\s+)?Public\s+Offer(?:ing)?[^.]{{0,240}}?under-?\s?subscribed"
    rf"[^.]{{0,90}}?representing\s+(?:approximately\s+)?({NUM})\s*%", re.I)


def fnum(s):
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def section_value(txt, sec_re, other_re):
    for m in sec_re.finditer(txt):
        block = txt[m.end():m.end() + 1200]
        nxt = other_re.search(block)
        if nxt:
            block = block[:nxt.start()]
        v = SUBLEVEL.search(block)
        if v:
            return fnum(v.group(1))
    return None


def main():
    data = json.loads(TARGET.read_text())
    tbl = prose = 0
    for i, rec in enumerate(data["deals"]):
        txt = ""
        for f in rec.get("files", []):
            p = CACHE / f
            if not p.exists():
                continue
            try:
                r = PdfReader(str(p))
                txt += "\n".join((r.pages[k].extract_text() or "")
                                 for k in range(min(20, len(r.pages))))
            except Exception:
                continue
        if not txt:
            continue
        flat = re.sub(r"\s+", " ", txt)
        pub = section_value(flat, SEC_PUB, SEC_INT)
        itl = section_value(flat, SEC_INT, SEC_PUB)
        method = "table" if (pub is not None or itl is not None) else None
        if pub is None:
            m = PROSE_PUB.search(flat) or PROSE_PUB2.search(flat)
            if m:
                pub, method = fnum(m.group(1)), method or "prose"
        if itl is None:
            m = PROSE_INT.search(flat) or PROSE_INT2.search(flat)
            if m:
                itl, method = fnum(m.group(1)), method or "prose"
        if itl is None:
            m = PROSE_INT_UNDER.search(flat)
            if m:
                v = fnum(m.group(1))
                if v is not None and 0 < v <= 100:
                    itl, method = round(v / 100, 4), method or "prose-under"
        if pub is None:
            m = PROSE_PUB_UNDER.search(flat)
            if m:
                v = fnum(m.group(1))
                if v is not None and 0 < v <= 100:
                    pub, method = round(v / 100, 4), method or "prose-under"
        if pub is not None:
            rec["oversub_public_mult"] = pub
        if itl is not None:
            rec["oversub_intl_mult"] = itl
        if method:
            rec["oversub_method"] = method
            tbl += method == "table"
            prose += method == "prose"
        if (i + 1) % 100 == 0:
            print(f"{i+1}/{len(data['deals'])}", flush=True)
    data["oversub_refixed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    TARGET.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    n = len(data["deals"])
    print(f"patched: {tbl} table-anchored, {prose} prose, "
          f"{sum(1 for x in data['deals'] if x.get('oversub_public_mult'))}/{n} with a public value")


if __name__ == "__main__":
    main()
