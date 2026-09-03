#!/usr/bin/env python3
"""Last-mile cornerstone extraction for deals the table parser never cracked.

After the prospectus table parse and the AAStocks 機構性投資者 fill there remain
a few dozen deals with a cornerstone SECTION but no investor list — mostly
small-caps whose agreements name individuals ("Mr. Gong Chaohui") in prose, or
one-fund tables whose layout defeated the generic parser. This pass works the
saved snips and the full text cache with three targeted shapes:

  1. prose: "Cornerstone Investment Agreement(s) with A (...), B (...) and C"
  2. prose: "NAME ... subscribed for ... N Offer Shares"
  3. table row: "NAME 2,443,000 24.43% ..."

Names go through clean_names; anything unusable is dropped, never shown.
Writes data/batches/deep_cornerstone_reparse.json.
"""
import json, re, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clean_names import clean_investor_list

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "batches" / "deep_cornerstone_reparse.json"
TEXT = ROOT / "scrape" / "text_cache"

# "with Mr. Gong Chaohui ("Mr. Gong") and Mr. Chen Xiong ("Mr. Chen")"
AGREEMENT = re.compile(
    r"Cornerstone\s+Investment\s+Agreements?\s+(?:entered\s+into\s+)?with\s+"
    r"(.{10,600}?)(?:,\s*the\s+number|pursuant|under\s+which|\.\s)", re.I | re.S)
NAME_TOKEN = re.compile(
    r"((?:Mr\.|Ms\.|Mrs\.|Dr\.|Prof\.)\s+[A-Z][A-Za-z\-]+(?:\s+[A-Z][A-Za-z\-]+){0,3}|"
    r"[A-Z][A-Za-z&\-\.',()]+(?:\s+[A-Z&][A-Za-z&\-\.',()]*){0,6}\s+"
    r"(?:Limited|Ltd\.?|Inc\.?|LLC|L\.P\.?|LP|Fund(?:\s+SPC)?|Company|Co\.,?\s*Ltd\.?|"
    r"Corporation|Management|Capital|Partners|Holdings|International|Securities|"
    r"Investment[s]?|Asset\s+Management|Insurance|Bank))")
# the CATL shape: "... among the Company, Sinopec (Hong Kong) Limited (中文) and
# Goldman Sachs ..., pursuant to which Sinopec (Hong Kong) Limited agreed to
# subscribe for H Shares ... US$500 million; (b) the cornerstone investment
# agreement ..." — the investor is whatever legal name sits right before
# "agreed to subscribe for"
SUBSCRIBED = re.compile(
    r"(.{5,110}?)\s*(?:\([^)]{0,90}\))?\s*(?:has\s+|have\s+|had\s+)?"
    r"agreed\s+to\s+subscribe\s+for", re.I)
TABLE_ROW = re.compile(
    r"([A-Z][A-Za-z&\-\.'()， ]{4,70}?)\s+[\d,]{4,}\s+\d{1,2}\.\d{1,2}%")


def best_name(fragment):
    """The LAST legal-name-shaped run inside a fragment, or None.

    A capture like "pursuant to which Sinopec (Hong Kong) Limited" contains
    clause words the grammar must not keep — validating through NAME_TOKEN and
    taking the final match strips them, and rejects sentence fragments like
    "In addition to the Offer Shares" entirely (no corporate tail, no honorific).
    """
    hits = [m.group(1) for m in NAME_TOKEN.finditer(fragment)]
    return hits[-1] if hits else None


# "the cornerstone investment agreement ... entered into among the Company,
# Sinopec (Hong Kong) Limited (中文) and Goldman Sachs ..." — the INVESTOR is
# the party right after "among the Company," (the last party is the CMI bank);
# stop at the first bracket so nested Chinese parens cannot derail the capture
AMONG = re.compile(r"among\s+(?:the\s+Company|our\s+Company|us)\s*,\s*"
                   r"(.{3,110}?)\s+and\s+", re.I)


def sanitize(text):
    """Strip the CJK name-in-brackets noise that breaks every boundary.

    PDF extraction renders the Chinese legal names as garbled bytes inside
    NESTED parentheses — "Sinopec (Hong Kong) Limited ( ʕͩʷ(࠰ ಥ)ʮ̡)" — and a
    single-level paren-stripper stops at the wrong ')'. Deleting non-ASCII
    first leaves empty parens, which then collapse cleanly, so the harvest
    patterns see "Sinopec (Hong Kong) Limited agreed to subscribe".
    """
    t = re.sub(r"[^\x00-\x7F]+", " ", text)
    for _ in range(3):                       # nested empties collapse in passes
        t = re.sub(r"\(\s*[,;\.\-–—\s]*\)", " ", t)
    return re.sub(r"\s+", " ", t)


def harvest(text):
    text = sanitize(text)
    names = []
    for m in AMONG.finditer(text):
        n = best_name(m.group(1))
        if n:
            names.append(n)
    for m in AGREEMENT.finditer(text):
        blob = re.sub(r"\([^)]{0,60}\)", " ", m.group(1))     # drop defined-term brackets
        for t in re.split(r",|\band\b|、", blob):
            n = best_name(t.strip())
            if n:
                names.append(n)
    for m in SUBSCRIBED.finditer(text):
        n = best_name(m.group(1))
        if n:
            names.append(n)
    for m in TABLE_ROW.finditer(text):
        n = best_name(m.group(1))
        if n:
            names.append(n)
    return clean_investor_list(names, limit=25)


def main():
    deals = json.loads((ROOT / "data" / "deals.json").read_text())["deals"]
    todo = [d for d in deals
            if not d.get("cornerstone_investors") and not d.get("cornerstone_none")]
    print(f"{len(todo)} deals without a cornerstone list", flush=True)
    out = []
    for d in todo:
        chunks = []
        if d.get("cornerstone_snip"):
            chunks.append(d["cornerstone_snip"])
        # the full cached filing text, cornerstone neighbourhood only
        for f in TEXT.glob(f"*_{d['code']}_*.txt"):
            t = f.read_text(errors="ignore")
            # the investor sentences say "agreed to subscribe" — anchor there,
            # not on the word "cornerstone" (a mega-prospectus mentions that
            # 100+ times before the agreement list ever starts; CATL's list sat
            # beyond the old window cap and yielded one name out of 23)
            grabbed = 0
            for m in re.finditer(r"agreed\s+to\s+subscribe", t):
                chunks.append(t[max(0, m.start() - 1500): m.start() + 500])
                grabbed += 1
                if grabbed > 40:
                    break
            grabbed = 0
            for m in re.finditer(r"[Cc]ornerstone", t):
                chunks.append(t[max(0, m.start() - 300): m.start() + 3000])
                grabbed += 1
                if grabbed > 40:
                    break
        blob = "\n".join(chunks)
        if not blob.strip():
            continue
        flat = re.sub(r"\s+", " ", blob)
        names = harvest(flat)
        rec = {"code": d["code"]}
        if names:
            rec["cornerstone_investors"] = names
            rec["cornerstone_n"] = len(names)
            rec["_prov"] = {"cornerstone_investors": {
                "src": "prospectus:cornerstone section re-parse", "status": "single"}}
        # aggregate % rescue while we are here
        if d.get("cornerstone_pct") is None:
            mm = re.search(r"(?:in\s+aggregate\s+|representing\s+)?approximately\s+"
                           r"(\d{1,2}(?:\.\d{1,2})?)%\s+of\s+the\s+(?:total\s+)?Offer\s+Shares",
                           flat, re.I)
            if mm:
                rec["cornerstone_pct"] = float(mm.group(1))
                rec.setdefault("_prov", {})["cornerstone_pct"] = {
                    "src": "prospectus:cornerstone prose re-parse", "status": "single"}
        if len(rec) > 1:
            out.append(rec)
            print(f"  {d['code']} {d['name'][:20]:20s} -> "
                  f"{rec.get('cornerstone_investors', ['(pct only)'])[:3]}")
    OUT.write_text(json.dumps(
        {"batch": "deep_cornerstone_reparse",
         "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(out), "deals": out}, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {len(out)} deals recovered")


if __name__ == "__main__":
    main()
