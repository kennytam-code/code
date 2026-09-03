#!/usr/bin/env python3
"""Stage 2: extract structured fields from downloaded allotment/prospectus PDFs.

  allotments  -> data/batches/extracted_allotments.json
  prospectus  -> data/batches/extracted_prospectus.json

Every extracted number carries a short source snippet so verification agents /
the merge step can sanity-check without reopening PDFs. Missing = null, never
guessed. Money left in the units the document states (captured in snippet).
"""
import json, re, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scrape" / "pdf_cache"
BATCHES = ROOT / "data" / "batches"

NUM = r"[\d,]+(?:\.\d+)?"


def fnum(s):
    return float(s.replace(",", "")) if s else None


def snip(txt, m, w=180):
    a, b = max(0, m.start() - w // 2), min(len(txt), m.end() + w)
    return re.sub(r"\s+", " ", txt[a:b]).strip()


def pdf_text(path, max_pages=12):
    try:
        r = PdfReader(str(path))
        return "\n".join((pg.extract_text() or "")
                         for pg in r.pages[:max_pages])
    except Exception as e:
        print(f"  unreadable {path.name}: {e}", file=sys.stderr)
        return ""


# Final price: the document repeats it many times in several phrasings, so collect
# every candidate and take the consensus (mode) rather than trusting one phrasing.
RE_FINAL_ALL = [
    re.compile(rf"(?:Final\s+)?Offer\s+Price\s*[::]\s*HK\$({NUM})", re.I),
    re.compile(rf"Based\s+on\s+the\s+Offer\s+Price\s+of\s+HK\$({NUM})", re.I),
    re.compile(rf"Offer\s+Price\s+(?:has\s+been|is|was)\s+(?:determined|fixed|set)"
               rf"(?:\s+\w+){{0,3}}?\s+at\s+HK\$({NUM})", re.I),
    re.compile(rf"Offer\s+Price\s+of\s+HK\$({NUM})\s+per\s+(?:Offer|H)?\s*Share", re.I),
    re.compile(rf"(?:Offer|Subscription)\s+Price\s+of\s+HK\$({NUM})", re.I),
]
RE_RANGE_ALL = [
    re.compile(rf"indicative\s+(?:Offer\s+)?Price\s+range\s+of\s+HK\$({NUM})\s*(?:to|-|and)\s*HK\$({NUM})", re.I),
    re.compile(rf"HK\$({NUM})\s+(?:to|and)\s+HK\$({NUM})\s+per\s+(?:Offer|H|International Offer)?\s*Share", re.I),
    re.compile(rf"between\s+HK\$({NUM})\s+and\s+HK\$({NUM})", re.I),
]
# prospectus cover states the cap first, then the floor
RE_RANGE_CAP = re.compile(
    rf"not\s+more\s+than\s+HK\$({NUM}).{{0,200}}?not\s+less\s+than\s+HK\$({NUM})", re.I | re.S)
RE_SHARES = re.compile(
    rf"(?:Offer Price of HK\${NUM}[^.]{{0,120}}?|total(?:\s+number)?\s+of\s+)({NUM})\s+"
    r"(?:Offer|H)\s+Shares", re.S)
RE_TIMES = re.compile(
    rf"(?:approximately|about|around)?\s*({NUM})\s+times(?:\s+(?:of|the))?", re.S)
RE_PUBLIC_BLOCK = re.compile(r"(?:Hong Kong )?Public Offer(?:ing)?.{0,1200}?times", re.S)
RE_INTL_BLOCK = re.compile(r"(?:International Offer(?:ing)?|Placing).{0,1200}?times", re.S)
RE_NETPRO = re.compile(
    rf"net\s+proceeds[^.]{{0,300}}?HK\$({NUM})\s*(million|billion)", re.S | re.I)
RE_GROSSPRO = re.compile(
    rf"gross\s+proceeds[^.]{{0,300}}?HK\$({NUM})\s*(million|billion)", re.S | re.I)

# --- proceeds: three sentences say "net proceeds ... HK$X million" ----------
# An allotment announcement states the figure three ways, and the naive
# first-match regex above picked the WRONG one on 50 deals:
#   1. THE DEAL      "The net proceeds from the Global Offering, after
#                     deducting ... are estimated to be approximately
#                     HK$24,113 million"          <- the one we want
#   2. THE GREENSHOE "If the Over-allotment Option is exercised in full, we
#                     will receive ADDITIONAL net proceeds of approximately
#                     HK$3,632 million"           <- ~15% of the deal
#   3. A BUCKET      "approximately 55% of the net proceeds, or approximately
#                     HK$13,262 million, is expected to be used for..."
# JD Logistics was published at HK$3,632m against a real HK$24,113m because
# the shoe sentence came first in the file. The base sentence also runs past
# 300 characters, so the window has to be wider than the old regex allowed.
# Anchors first, values second. Running a value pattern over a whole 60KB
# announcement backtracks for ~2 seconds per deal (the documents are full of
# long digit-and-comma runs); anchoring on the cheap literal and then scanning
# a bounded window is ~200x faster and matches identically.
RE_PRO_ANCHOR = re.compile(r"(net|gross)\s+proceeds", re.I)
RE_PRO_VALUE = re.compile(rf"HK\$({NUM})\s*(million|billion)", re.I)
RE_PRO_BUCKET = re.compile(
    rf"(\d{{1,3}}(?:\.\d+)?)\s*%[^%]{{0,80}}?HK\$({NUM})\s*(million|billion)", re.I)
WINDOW = 600          # chars after the anchor to look for the figure


def _scale(v, unit):
    return v * 1000 if unit.lower() == "billion" else v


def parse_proceeds(txt, kind):
    """Best 'HK$X million' figure for the WHOLE offering, or (None, None).

    Ranked, not first-come: an explicit "are estimated to be approximately"
    statement beats a bare mention, and both beat nothing. Greenshoe and
    use-of-proceeds-bucket sentences are rejected outright rather than ranked
    down, because they answer a different question.
    """
    best = None
    for a in RE_PRO_ANCHOR.finditer(txt):
        if a.group(1).lower() != kind:
            continue
        lead = txt[max(0, a.start() - 12):a.start()]
        # (2) the greenshoe sentence: "additional net proceeds of ~HK$X"
        if re.search(r"additional\s*$", lead, re.I):
            continue
        win = txt[a.end():a.end() + WINDOW]
        win = win.split(".")[0] if "." in win[:2] else win
        # the figure has to be inside the same sentence; periods inside
        # decimals ("HK$1,081.5") must not end it, so cut on ". " instead
        stop = re.search(r"\.\s", win)
        if stop:
            win = win[:stop.start()]
        m = RE_PRO_VALUE.search(win)
        if not m:
            continue
        span = win[:m.end()]
        # (3) a use-of-proceeds bucket: "approximately 55% of the net
        # proceeds, or approximately HK$13,262 million"
        if re.search(r"\d\s*%", span):
            continue
        # the shoe sentence in other phrasings; "assuming the Over-allotment
        # Option is NOT exercised" is the base case and must survive
        if re.search(r"upon\s+(?:the\s+)?exercise\s+of\s+the\s+Over-?allotment",
                     span, re.I):
            continue
        val = _scale(fnum(m.group(1)), m.group(2))
        if not val:
            continue
        rank = 2 if re.search(r"estimated\s+to\s+be|amount\s+to|will\s+be\s+approximately",
                              span, re.I) else 1
        if best is None or rank > best[0]:
            off = a.end() + m.start()
            best = (rank, val, re.sub(r"\s+", " ",
                                      txt[max(0, a.start() - 110):off + 60]).strip())
    if best:
        return best[1], best[2]
    # Last resort, NET ONLY: recover the total from labelled buckets ("55% ...
    # HK$13,262 million" -> 24,113). A use-of-proceeds table allocates the NET
    # proceeds, so running this for gross fills gross with the net number —
    # which is exactly what happened: Fenbi came out gross 120.0 / net 119.9,
    # and shares x price then exceeded "gross" on 55 deals.
    if kind != "net":
        return None, None
    # Only when at least two buckets agree to 2%, so a stray percentage next
    # to a number cannot invent a total.
    tot = []
    for m in RE_PRO_BUCKET.finditer(txt):
        pct = float(m.group(1))
        if 5 <= pct <= 95:
            tot.append(_scale(fnum(m.group(2)), m.group(3)) / (pct / 100))
    if len(tot) >= 2 and (max(tot) - min(tot)) / max(tot) <= 0.02:
        return round(sum(tot) / len(tot), 1), (
            f"recovered from {len(tot)} use-of-proceeds buckets that agree "
            f"within 2% (no explicit total sentence in the document)")
    return None, None
RE_LISTDATE = re.compile(
    r"commence[^.]{0,120}?on\s+(?:[A-Z][a-z]+day,?\s+)?(\d{1,2}\s+[A-Z][a-z]+,?\s+\d{4})", re.S)
RE_GREENSHOE = re.compile(r"[Oo]ver-?allotment [Oo]ption[^.]{0,400}\.", re.S)
RE_CORNER = re.compile(r"[Cc]ornerstone [Ii]nvestors?[^.]{0,400}\.", re.S)
MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}


def parse_listdate(s):
    m = re.match(r"(\d{1,2})\s+([A-Z][a-z]+),?\s+(\d{4})", s.strip())
    if not m or m.group(2) not in MONTHS:
        return None
    return f"{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"


# HKEX standardised allotment summary table (2025+ announcements): label followed
# by the value on the same line, no colon. Authoritative — beats the prose regexes.
TBL = {
    "final_price": rf"Final\s+Offer\s+Price\s+HK\$({NUM})",
    "price_range_hi": rf"Maximum\s+Offer\s+Price\s+HK\$({NUM})",
    "price_range_lo_tbl": rf"Minimum\s+Offer\s+Price\s+HK\$({NUM})",
    "offer_shares": rf"Number\s+of\s+Offer\s+Shares\s+({NUM})",
    "shares_outstanding": rf"Number\s+of\s+issued\s+Shares\s+upon\s+Listing\s+({NUM})",
    "overallot_shares": rf"No\.\s+of\s+Offer\s+Shares\s+over-allocated\s+({NUM})",
}
RE_DEALDATE = re.compile(
    r"Dealings\s+commencement\s+date\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})", re.I)


def extract_table(txt):
    """Structured fields from the standardised summary table (empty dict if absent)."""
    out = {}
    for key, pat in TBL.items():
        m = re.search(pat, txt, re.I)
        if m:
            v = fnum(m.group(1))
            if v:
                out[key] = v
                out[key + "_snip"] = snip(txt, m, 80)
    m = RE_DEALDATE.search(txt)
    if m:
        try:
            out["listing_date"] = datetime.strptime(m.group(1), "%B %d, %Y").date().isoformat()
            out["listing_date_snip"] = snip(txt, m, 60)
        except ValueError:
            pass
    return out


def extract_common(txt):
    out = {}
    cands, first = [], None
    for r in RE_FINAL_ALL:
        for m in r.finditer(txt):
            v = fnum(m.group(1))
            if v and 0.01 <= v <= 10000:
                cands.append(v)
                first = first or m
    if cands:
        out["final_price"] = Counter(cands).most_common(1)[0][0]
        out["final_price_n_mentions"] = len(cands)
        out["final_price_snip"] = snip(txt, first)
    for r in RE_RANGE_ALL:
        m = r.search(txt)
        if m:
            lo, hi = fnum(m.group(1)), fnum(m.group(2))
            if lo and hi and lo < hi <= lo * 4:
                out["price_range_lo"], out["price_range_hi"] = lo, hi
                out["price_range_snip"] = snip(txt, m)
                break
    if "price_range_lo" not in out:
        m = RE_RANGE_CAP.search(txt)
        if m:
            hi, lo = fnum(m.group(1)), fnum(m.group(2))
            if lo and hi and lo < hi <= lo * 4:
                out["price_range_lo"], out["price_range_hi"] = lo, hi
                out["price_range_snip"] = snip(txt, m)
    m = RE_SHARES.search(txt)
    if m:
        out["offer_shares"] = fnum(m.group(1))
        out["offer_shares_snip"] = snip(txt, m)
    for key, blockre in (("oversub_public", RE_PUBLIC_BLOCK),
                         ("oversub_intl", RE_INTL_BLOCK)):
        b = blockre.search(txt)
        if b:
            t = RE_TIMES.search(b.group(0))
            if t:
                out[key + "_mult"] = fnum(t.group(1))
                out[key + "_snip"] = snip(b.group(0), t, 120)
    for key, kind in (("net_proceeds", "net"), ("gross_proceeds", "gross")):
        v, sn = parse_proceeds(txt, kind)
        if v is not None:
            out[key + "_hkdm"] = v
            out[key + "_snip"] = sn
    m = RE_LISTDATE.search(txt)
    if m:
        d = parse_listdate(m.group(1))
        if d:
            out["listing_date"] = d
            out["listing_date_snip"] = snip(txt, m, 100)
    m = RE_GREENSHOE.search(txt)
    if m:
        out["greenshoe_snip"] = snip(txt, m, 320)
    m = RE_CORNER.search(txt)
    if m:
        out["cornerstone_snip"] = snip(txt, m, 320)
    return out


def run(kind):
    manifest_file = ("hkex_allotment_files.json" if kind == "allotments"
                     else "hkex_prospectus_links.json")
    data = json.loads((BATCHES / manifest_file).read_text())
    entries = data.get("manifest") or data.get("deals")
    results, missing = [], 0
    for i, e in enumerate(entries):
        # A deal with no parts is skipped. Where the per-stock search came up
        # empty for a brand-new code, fetch_hkex_filings.attach_cached_newlist
        # has already put the offering-window copy of the prospectus into the
        # manifest, so the rescue is upstream of here and every consumer of
        # this manifest gets it — not just this parser.
        files = [p["file"] for p in e.get("parts", [])]
        if not files:
            missing += 1
            continue
        txt = "\n".join(pdf_text(CACHE / f) for f in files)
        if len(txt) < 200:
            missing += 1
            continue
        rec = {"code": e["code"], "files": files}
        rec.update(extract_common(txt))
        rec.update(extract_table(txt))          # table wins where present
        if rec.pop("price_range_lo_tbl", None):
            rec["price_range_lo"] = rec.get("price_range_lo_tbl")
        results.append(rec)
        if (i + 1) % 50 == 0:
            print(f"{i+1}/{len(entries)} parsed")
    out = BATCHES / f"extracted_{kind}.json"
    got_price = sum(1 for r in results if r.get("final_price"))
    out.write_text(json.dumps(
        {"batch": f"extracted_{kind}",
         "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "parsed": len(results), "no_text": missing,
         "with_final_price": got_price, "deals": results},
        ensure_ascii=False, indent=1))
    print(f"wrote {out}: {len(results)} parsed, {got_price} with final price, {missing} without text")


if __name__ == "__main__":
    run(sys.argv[1])
