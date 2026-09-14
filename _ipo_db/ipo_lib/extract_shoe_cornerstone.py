#!/usr/bin/env python3
"""Extract greenshoe exercise status and cornerstone take-up from allotment PDFs.

Writes data/batches/extracted_shoe_cornerstone.json.

greenshoe_exercised  none | full | partial | not-yet   (from the announcement's
    own wording — an IPO-day announcement usually says the option "has not been
    exercised", which means not-yet at that date, NOT that it never was; that
    distinction is preserved rather than flattened to "none".)
cornerstone_pct      cornerstone shares as a % of the offer, read from the
    "representing approximately X% of the Offer Shares" clause inside the
    cornerstone paragraph.
"""
import json, re
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scrape" / "pdf_cache"
SRC = ROOT / "data" / "batches" / "extracted_allotments.json"
OUT = ROOT / "data" / "batches" / "extracted_shoe_cornerstone.json"

NUM = r"\d+(?:\.\d+)?"
SHOE_FULL = re.compile(r"Over-?allotment Option[^.]{0,160}?(?:has been|was) exercised in full", re.I)
SHOE_PART = re.compile(r"Over-?allotment Option[^.]{0,160}?(?:has been|was) partially exercised|"
                       r"partial(?:ly)? exercise[^.]{0,60}?Over-?allotment Option", re.I)
SHOE_NONE = re.compile(r"Over-?allotment Option[^.]{0,200}?(?:has not been|will not be|was not) exercised", re.I)
CORNER_BLOCK = re.compile(r"Cornerstone Investors?\b(.{0,2500})", re.I | re.S)
CORNER_PCT = re.compile(
    rf"representing\s+(?:approximately\s+)?({NUM})\s*%[^.]{{0,120}}?"
    rf"(?:Offer Shares|Shares (?:being )?offered|Global Offering|Share Offer)", re.I | re.S)


def main():
    src = json.loads(SRC.read_text())
    out = []
    import incremental
    only = incremental.wanted(OUT, [r.get("code") for r in src["deals"]])
    rows = [r for r in src["deals"] if only is None or str(r.get("code")) in only]
    if only is not None:
        print(f"  incremental: {len(rows)} deal(s) to parse")
    for i, rec in enumerate(rows):
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
        rec_out = {"code": rec["code"]}
        if SHOE_FULL.search(flat):
            rec_out["greenshoe_exercised"] = "full"
        elif SHOE_PART.search(flat):
            rec_out["greenshoe_exercised"] = "partial"
        elif SHOE_NONE.search(flat):
            # allotment announcements predate the 30-day stabilisation window
            rec_out["greenshoe_exercised"] = "not-yet (at allotment)"
        blk = CORNER_BLOCK.search(flat)
        if blk:
            m = CORNER_PCT.search(blk.group(1))
            if m:
                v = float(m.group(1))
                if 0 < v <= 100:
                    rec_out["cornerstone_pct"] = v
                    rec_out["cornerstone_pct_snip"] = re.sub(
                        r"\s+", " ", blk.group(1)[max(0, m.start() - 120):m.end() + 60])[:240]
        if len(rec_out) > 1:
            out.append(rec_out)
        if (i + 1) % 100 == 0:
            print(f"{i+1}/{len(src['deals'])}", flush=True)
    out = incremental.merge(OUT, out, only)
    OUT.write_text(json.dumps(
        {"batch": "extracted_shoe_cornerstone",
         "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(out),
         "with_shoe": sum(1 for r in out if r.get("greenshoe_exercised")),
         "with_cornerstone": sum(1 for r in out if r.get("cornerstone_pct")),
         "deals": out}, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {len(out)} deals, "
          f"{sum(1 for r in out if r.get('greenshoe_exercised'))} shoe status, "
          f"{sum(1 for r in out if r.get('cornerstone_pct'))} cornerstone %")


if __name__ == "__main__":
    main()
