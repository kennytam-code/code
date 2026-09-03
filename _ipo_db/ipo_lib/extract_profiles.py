#!/usr/bin/env python3
"""Extract company identity + business overview from downloaded prospectus PDFs.

Writes data/batches/extracted_profiles.json:
  {code, name_full, name_cn, overview}

Uses pypdf (~6x faster per page than pdfplumber for plain text). 417 of the 466
prospectuses are a single whole-document PDF, so the SUMMARY/OVERVIEW section
sits ~10-25 pages in; separated filings have a labelled "Summary" part which is
preferred when present.

The overview is prospectus prose only — sector/subsector classification is a
judgment made against data/taxonomy.json, never keyword-guessed here.
"""
import json, re, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scrape" / "pdf_cache"
LINKS = ROOT / "data" / "batches" / "hkex_prospectus_links.json"
OUT = ROOT / "data" / "batches" / "extracted_profiles.json"

CN = re.compile(r"[一-鿿]")
NOISE = re.compile(r"\.pdf|Fancy Cover|spine|Project |ai\d{3}|HR\d|\d{2}/\d{2}/\d{2}|"
                   r"IMPORTANT|If you are in any doubt", re.I)
OVERVIEW = re.compile(
    r"(?:^|\n)\s*(?:OVERVIEW|Overview)\s*\n(.{100,1200}?)(?:\n\s*\n|OUR (?:STRENGTHS|MISSION)|"
    r"COMPETITIVE STRENGTH)", re.S)
# Candidates ranked: an HK prospectus describes the business with these stock phrases.
# Risk-factor prose ("we cannot assure you...") matches "We are" too, so it is excluded.
CANDIDATES = [
    re.compile(r"((?:We|Our Company|Our Group)\s+(?:are|is)\s+(?:principally\s+)?engaged\s+in\b.{60,700})", re.S),
    re.compile(r"((?:We|Our Company|Our Group)\s+(?:are|is)\s+(?:a|an|one of)\s+"
               r"(?:the\s+)?(?:leading|largest|major|fast-growing|prominent|established|"
               r"top|PRC|China|Hong Kong|global)\b.{60,700})", re.S),
    re.compile(r"((?:We|Our Company|Our Group)\s+(?:are|is)\s+(?:a|an)\s+"
               r"(?:provider|manufacturer|operator|supplier|developer|producer|distributor|"
               r"platform|company|group|retailer|contractor)\b.{60,700})", re.S),
    re.compile(r"((?:We|Our Group)\s+(?:operate|provide|manufacture|design|develop|produce|"
               r"specialise|specialize)\b.{60,700})", re.S),
]
RISKY = re.compile(r"cannot assure|no assurance|we may not|may be materially|adversely affect|"
                   r"highly competitive industry|are paid by our customers|risk factors|"
                   # tax and jurisdiction boilerplate opens "We are a PRC enterprise…"
                   # and "We are a company incorporated under the laws of…", which the
                   # business-description candidates match but which describe no business
                   r"subject to PRC tax|PRC tax resident|withholding tax|"
                   r"incorporated under the laws|effect service of process|"
                   r"enforce judgments|judgments obtained", re.I)
SUMMARY_HDR = re.compile(r"\n\s*SUMMARY\s*\n")


def text_of(path, pages=30):
    try:
        r = PdfReader(str(path))
        return "\n".join((r.pages[i].extract_text() or "")
                         for i in range(min(pages, len(r.pages))))
    except Exception as e:
        print(f"  unreadable {path.name}: {e}", file=sys.stderr)
        return ""


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def names_from_cover(txt):
    en = cn = None
    for line in txt.split("\n")[:30]:
        line = clean(line)
        if not line or NOISE.search(line):
            continue
        if CN.search(line) and not cn:
            m = re.search(r"[一-鿿][一-鿿A-Za-z0-9（）()·\-]{2,40}", line)
            if m:
                cn = m.group(0)
        if not CN.search(line) and not en and re.search(
                r"(Limited|Ltd\.?|Inc\.?|Holdings|Group|Company|Corporation|Co\.)\s*\*?$", line, re.I):
            en = re.sub(r"\s*\*$", "", line)[:90]
    return en, cn


def find_overview(txt):
    """Business-overview prose, preferring the SUMMARY section and rejecting risk text.

    Ends on a SENTENCE, never mid-word: a card that reads "…decision-making
    and motion pla" looks broken, and a half-sentence tells the reader less
    than a shorter whole one.
    """
    from textclip import clip_sentence
    hdr = SUMMARY_HDR.search(txt)
    scopes = [txt[hdr.end():]] if hdr else []
    scopes.append(txt)
    for scope in scopes:
        m = OVERVIEW.search(scope)
        if m and not RISKY.search(m.group(1)[:200]):
            return clip_sentence(clean(m.group(1)), 700)
        for r in CANDIDATES:
            for m in r.finditer(scope):
                cand = clean(m.group(1))
                if not RISKY.search(cand[:260]):
                    return clip_sentence(cand, 700)
    return None


def main():
    links = json.loads(LINKS.read_text())["deals"]
    recs, done = [], 0
    for e in links:
        parts = e.get("parts") or []
        if not parts:
            continue
        files = [CACHE / p["file"] for p in parts if (CACHE / p["file"]).exists()]
        if not files:
            continue
        labelled = [(p["label"], CACHE / p["file"]) for p in parts]
        cover = next((f for lb, f in labelled if lb.lower().startswith("cover")), files[0])
        summary = next((f for lb, f in labelled if lb.lower().startswith("summary")), None)
        ctxt = text_of(cover, 3)
        en, cn = names_from_cover(ctxt)
        ov = find_overview(text_of(summary, 20) if summary else text_of(files[0], 30))
        if not ov:                       # SUMMARY sits deeper in some filings
            ov = find_overview(text_of(files[0], 70))
        if not en:
            en, cn2 = names_from_cover(text_of(files[0], 2))
            cn = cn or cn2
        recs.append({"code": e["code"], "name_full": en, "name_cn": cn, "overview": ov})
        done += 1
        if done % 50 == 0:
            print(f"{done} profiles", flush=True)
    OUT.write_text(json.dumps(
        {"batch": "extracted_profiles",
         "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(recs),
         "with_overview": sum(1 for r in recs if r["overview"]),
         "with_name": sum(1 for r in recs if r["name_full"]),
         "deals": recs}, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {len(recs)} profiles, "
          f"{sum(1 for r in recs if r['overview'])} overviews, "
          f"{sum(1 for r in recs if r['name_full'])} names")


if __name__ == "__main__":
    main()
