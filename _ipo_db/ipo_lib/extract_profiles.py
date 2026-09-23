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
                   r"highly competitive(?:\s+and\s+\w+)?\s+(?:industry|market)|compete against|market entrants|"
                   r"are paid by our customers|risk factors|"
                   # "market acceptance ... remains uncertain" is a risk
                   # factor opener, not a description of the business
                   r"market acceptance|remains uncertain|no operating history|"
                   # tax and jurisdiction boilerplate opens "We are a PRC enterprise…"
                   # and "We are a company incorporated under the laws of…", which the
                   # business-description candidates match but which describe no business
                   r"subject to PRC tax|PRC tax resident|withholding tax|"
                   r"incorporated under the laws|established under the laws|"
                   r"assets are located in|reside in the PRC|effect service of process|"
                   r"enforce judgments|judgments obtained|"
                   # accounting-presentation boilerplate reads like a business
                   # description and says nothing about the business: "We are a
                   # PRC-based company with our principal operations in Chinese
                   # Mainland... our financial statements are presented in RMB"
                   r"financial statements are (?:presented|prepared)|reporting currency|"
                   r"presented in (?:RMB|Renminbi|HK\$|US\$)|"
                   # production-footprint prose ("We produce and assemble our
                   # products primarily at our manufacturing facilities...")
                   # matches the "We produce" candidate and names no product
                   r"manufacturing (?:facilit|centre|center|plant|base)|"
                   r"production (?:facilit|base|line)s? (?:are|is|located)", re.I)
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


def _mend_split_words(s, full):
    """Undo pypdf's mid-word space, and only where the document proves it.

    "a leading local supplier of semicondu ctor photoresists" is a kerning
    artifact, not a typo to reproduce in a shipped file. A pair is joined ONLY
    when the joined token appears elsewhere in the same document, so nothing
    is invented and real two-word phrases ("end market") are left alone.

    Walks EVERY adjacent pair: a regex sub consumes both words of a match, so
    "sale reve nue" tested "sale"+"reve", failed, and never tried "reve"+"nue".
    """
    low = full.lower()
    toks = re.split(r"(\s+)", s)          # keep the separators
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        if (i + 2 < len(toks) and toks[i + 1].isspace() and toks[i + 1] == " "
                # a single stray letter is the commonest artifact of the lot
                # ("h igh-performance", "t he"), and the joined word still has
                # to be proven by the document before anything is merged
                and re.fullmatch(r"[A-Za-z]+", t)
                and re.fullmatch(r"[A-Za-z][A-Za-z\-]*[.,;:)]?", toks[i + 2])):
            nxt = toks[i + 2]
            tail = ""
            if not nxt[-1].isalpha():
                nxt, tail = nxt[:-1], nxt[-1]
            joined = t + nxt
            # the joined form appearing in the document IS the proof; a
            # "but the split form also appears" guard blocks exactly the case
            # this exists for, because the artifact repeats within the filing
            if len(joined) >= 6 and joined.lower() in low:
                out.append(joined + tail)
                i += 3
                continue
        out.append(t)
        i += 1
    return "".join(out)


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
            return clip_sentence(_mend_split_words(clean(m.group(1)), txt), 700)
        for r in CANDIDATES:
            for m in r.finditer(scope):
                cand = _mend_split_words(clean(m.group(1)), txt)
                if not RISKY.search(cand[:260]):
                    return clip_sentence(cand, 700)
    return None


def main():
    import incremental
    links = json.loads(LINKS.read_text())["deals"]
    only = incremental.wanted(OUT, [e["code"] for e in links])
    if only is not None:
        links = [e for e in links if str(e["code"]) in only]
        print(f"  incremental: {len(links)} deal(s) to parse")
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
        if not ov:
            # the offering-window copy of the same prospectus, downloaded by
            # fetch_newlistings while the deal was open — often the only part
            # on disk for a code that listed days ago
            for nl in sorted(CACHE.glob(f"newlist_{e['code']}_*.pdf")):
                ov = find_overview(text_of(nl, 60))
                if ov:
                    break
        if not en:
            en, cn2 = names_from_cover(text_of(files[0], 2))
            cn = cn or cn2
        recs.append({"code": e["code"], "name_full": en, "name_cn": cn, "overview": ov})
        done += 1
        if done % 50 == 0:
            print(f"{done} profiles", flush=True)
    recs = incremental.merge(OUT, recs, only)
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
