#!/usr/bin/env python3
"""Deep parse of the full prospectus / allotment text.

v1 read only the first 12 pages of each ~600-page prospectus, which is why
sponsors came out 0% and cornerstone 12%: the parties section sits at pp.81-190
and the cornerstone table at pp.268-365. This module caches each document's FULL
text once (scrape/text_cache/) and then parses sections out of the cache, so
re-parsing is instant.

Sources, in the order they are trusted:
  cornerstone  allotment announcement table (FINAL allocations at the struck
               price, with an existing-shareholder flag) > prospectus table
               (estimated at the maximum price)
  syndicate    prospectus "DIRECTORS[, SUPERVISORS] AND PARTIES INVOLVED IN THE
               GLOBAL OFFERING" (GEM: "... IN THE SHARE OFFER"). NOT the cover
               page - there the bank identities are logos, not text.
  max price    prospectus page-2 field block "(Maximum) Offer Price : HK$X"
  share count  "SHARE CAPITAL" section -> shares in issue on listing

pypdf injects stray intra-word spaces ("P ARTIES INVOL VED", "Y ue Xiu"), so
headings are matched with a letter-tolerant regex built by loose().
"""
import json, re, sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scrape" / "pdf_cache"
TEXT = ROOT / "scrape" / "text_cache"
OUT = ROOT / "data" / "batches" / "extracted_deep.json"

LEADER = re.compile(r"(?:/H\d{4}|\.{3,}|·{3,}|…+)")
NUM = r"[\d,]+(?:\.\d+)?"


def loose(phrase):
    """Regex tolerating the stray spaces pypdf inserts inside words."""
    out = []
    for ch in phrase:
        out.append(r"\s+" if ch == " " else re.escape(ch) + r"\s?")
    return "".join(out)


HDR_PARTIES = re.compile(
    loose("PARTIES INVOLVED IN THE") + r"\s*(?:GLOBAL OFFERING|SHARE OFFER|OFFERING)", re.I)
HDR_CORNER = re.compile(
    r"(?:OUR|THE)\s+CORNERSTONE\s+INVESTORS?|CORNERSTONE\s+PLACING|CORNERSTONE\s+INVESTORS?", re.I)
ROLE = re.compile(
    r"\b(Joint Sponsors?|Sole Sponsor|Co-Sponsors?|Sponsor-Overall Coordinators?|"
    r"Overall Coordinators?|Joint Global Coordinators?|Joint Bookrunners?|"
    r"Joint Lead Managers?|Sole Global Coordinator|Sole Bookrunner)\b", re.I)
BANK = re.compile(
    r"\b([A-Z][A-Za-z'&.\-]*(?:\s+[A-Z(][A-Za-z'&.()\-]*){0,7}\s+"
    r"(?:Limited|Ltd\.?|L\.L\.C\.|LLC|Inc\.|Corporation|Company Limited|"
    r"Securities|Branch|Co\., Ltd\.))")
STOP_PARTY = re.compile(r"legal advis|auditor|reporting account|receiving bank|"
                        r"industry consultant|compliance adviser", re.I)
# Only true name ENDINGS. "Corporation", "Securities" and "Company" occur
# mid-name ("China International Capital Corporation Hong Kong Securities
# Limited"), so treating them as terminators split banks in half.
TERMINATOR = re.compile(r"(?:Limited|Ltd\.?|L\.L\.C\.?|LLC|Inc\.?|Branch|plc|"
                        r"Corp\.)\s*$", re.I)
ADDRESS = re.compile(r"^\d|\b(?:Floor|/F|Road|Street|Avenue|Tower|Centre|Center|"
                     r"Building|Plaza|District|Kowloon|Queen'?s|Connaught|Harbour|"
                     r"Finance Centre)\b|^(?:Hong Kong|China|Central|Singapore|PRC)\s*$", re.I)

# Greenshoe SIZE as stated in the offer structure ("up to 15% of the number of
# Offer Shares initially available"). Distinct from whether it was exercised.
SHOE_PCT = re.compile(
    rf"[Oo]ver-?allotment\s+[Oo]ption[^.]{{0,220}}?(?:up\s+to\s+)?({NUM})\s*%|"
    rf"(?:up\s+to\s+)?({NUM})\s*%[^.]{{0,120}}?[Oo]ver-?allotment\s+[Oo]ption", re.S)
# The AUTHORITATIVE total offer-share count, labelled in both document styles.
# The old loose regex grabbed tranche or issued-share figures instead (Kuaishou
# read 165m vs the true 365,218,600), which forced 137 deals onto net proceeds.
_SHARECOUNT = r"\d[\d,]{5,}"          # >= 6 digits, never an empty match
OFFER_SHARES_TOTAL = [
    re.compile(rf"Number\s+of\s+Offer\s+Shares\s+under\s+the\s+Global\s+Offering\s*[::]?\s*({_SHARECOUNT})", re.I),
    re.compile(rf"Number\s+of\s+Offer\s+Shares\s*(?:\(subject[^)]{{0,60}}\))?\s*[::]?\s*({_SHARECOUNT})", re.I),
    re.compile(rf"total\s+number\s+of\s+Offer\s+Shares\s+(?:initially\s+)?(?:available\s+)?"
               rf"under\s+the\s+Global\s+Offering[^\d]{{0,40}}({_SHARECOUNT})", re.I),
]
# indicative price range — stated in the cornerstone/offering tables as
# "HK$X (being the low-end of the indicative Offer Price Range)"
RANGE_LO = re.compile(rf"HK\$({NUM})\s*\(?being\s+the\s+low[- ]end", re.I)
RANGE_HI = re.compile(rf"HK\$({NUM})\s*\(?being\s+the\s+high[- ]end", re.I)
# issuer-stated expected market capitalisation
MKTCAP_STATED = re.compile(
    rf"market\s+capitali[sz]ation[^.]{{0,200}}?"
    rf"HK\$({NUM})\s*(million|billion)?(?:[^.]{{0,80}}?(?:to|and)\s+HK\$({NUM})\s*(million|billion)?)?",
    re.I | re.S)
# cornerstone aggregate wording, both documents
CS_AGG_PCT = re.compile(
    rf"representing\s+(?:\([a-z]\)\s*)?(?:approximately\s+)?({NUM})\s*%[^.]{{0,140}}?"
    rf"(?:of\s+the\s+)?Offer\s+Shares", re.I | re.S)
CS_AGG_USD = re.compile(rf"aggregate\s+amount\s+of\s+(?:approximately\s+)?"
                        rf"(?:US\$|HK\$)({NUM})\s*(million|billion)", re.I)
# allotment cornerstone table row: <name> <shares> <pct>% <pct>%
CS_ROW = re.compile(
    rf"([A-Z][^\n]{{3,70}}?)\s+({NUM})\s+({NUM})\s*%\s+({NUM})\s*%", re.M)
MAXPX = re.compile(rf"(?:Maximum\s+(?:Public\s+)?)?Offer\s+Price\s*[::]\s*"
                   rf"(?:Not\s+more\s+than\s+)?HK\$({NUM})", re.I)
# The enlarged-share-capital percentage is stated far more reliably than any
# absolute share count, and it yields market cap directly:
#   market cap = gross proceeds / (offer % of enlarged capital / 100)
OFFER_PCT = re.compile(
    rf"(?:representing|represent)\s+(?:approximately\s+)?({NUM})\s*%\s+of\s+"
    rf"(?:our|the)\s+(?:total\s+)?enlarged\s+(?:issued\s+)?share\s+capital", re.I)
SHARES_LISTING = re.compile(
    rf"(?:total\s+)?number\s+of\s+(?:issued\s+)?[HA]?\s*[Ss]hares\s+"
    rf"(?:in\s+issue\s+)?(?:immediately\s+)?(?:up)?on\s+(?:completion\s+of\s+the\s+)?"
    rf"[Ll]isting[^\d]{{0,80}}({NUM})", re.I | re.S)


def clean(s):
    return re.sub(r"\s+", " ", LEADER.sub(" ", s or "")).strip()


def cache_text(pdf_name):
    """Extract full text of one PDF into text_cache (skip if already cached)."""
    dest = TEXT / (pdf_name + ".txt")
    if dest.exists() and dest.stat().st_size > 500:
        return dest.name, "cached"
    try:
        r = PdfReader(str(CACHE / pdf_name))
        txt = "\n".join((p.extract_text() or "") for p in r.pages)
        dest.write_text(txt, errors="ignore")
        return dest.name, f"{len(r.pages)}pp"
    except Exception as e:
        return dest.name, f"ERR {e}"


def read_cached(pdf_name):
    p = TEXT / (pdf_name + ".txt")
    return p.read_text(errors="ignore") if p.exists() else ""


# ------------------------------------------------------------------ parsers --
def best_block(txt, header_re, signal_re, span):
    """The heading also appears in the table of contents, where it is followed by
    dot leaders and a page number. Score every occurrence by how much real
    content follows and take the winner."""
    best, best_score = None, 0
    for m in header_re.finditer(txt):
        blk = txt[m.end():m.end() + span]
        score = len(signal_re.findall(blk))
        if score > best_score:
            best, best_score = blk, score
    return best


def parse_syndicate(txt):
    """{role: [banks]} from the parties-involved section.

    Scoring on bank names alone picked the DEFINITIONS section (it is full of
    bank names but has no role labels), so score on ROLE labels instead and take
    a wider window — the sponsor line can sit well above the bookrunners.
    """
    # Parse EVERY occurrence of the heading and keep the richest result — one
    # scoring rule cannot win for both layouts (some filings repeat the heading
    # in the table of contents, the definitions and the real section).
    best, best_score = None, 0
    for m in HDR_PARTIES.finditer(txt):
        cand = _parse_parties_block(txt[m.end():m.end() + 16000])
        if cand:
            score = sum(len(v) for v in cand.values()) + 3 * len(cand)
            if score > best_score:
                best, best_score = cand, score
    return best


def _parse_parties_block(block):
    if not block:
        return None
    stop = STOP_PARTY.search(block)
    if stop and stop.start() > 400:
        block = block[:stop.start()]
    # Each entry is "<role> / <bank name, often wrapped over 2 lines> / <address>".
    # Accumulate lines until one ends in a company terminator (that is the bank),
    # and drop the buffer on an address line so the address never merges into the
    # next bank's name.
    out, cur, buf = {}, None, []
    for raw in block.split("\n"):
        line = clean(raw)
        if not line:
            continue
        r = ROLE.search(line)
        if r:
            cur, buf = re.sub(r"\s+", " ", r.group(1)).title(), []
            line = clean(line[r.end():])
            if not line:
                continue
        if cur is None:
            continue
        if ADDRESS.search(line):
            buf = []
            continue
        buf.append(line)
        cand = " ".join(buf)
        if TERMINATOR.search(cand):
            name = re.sub(r"\s+", " ", cand).strip(" ,.")
            # drop any role wording that ran into the buffer
            name = re.sub(r"^.*?\(in alphabetical order\)\s*", "", name, flags=re.I)
            name = re.sub(r"^(?:and\s+)?(?:Capital Market Intermediar\w+|Overall "
                          r"Coordinators?|Joint [A-Za-z ]+?)\s+(?=[A-Z])", "", name)
            if 8 < len(name) < 90:
                out.setdefault(cur, [])
                if name not in out[cur]:
                    out[cur].append(name)
            buf = []
        elif len(buf) > 3:
            buf = []
    return out or None


def cornerstone_block(txt, span):
    """Pick the region that actually holds the cornerstone economics. Scoring on
    bare percentages picked the wrong section (a 600-page prospectus is full of
    them), so score on cornerstone-specific evidence instead."""
    best, best_score = None, 0
    for m in HDR_CORNER.finditer(txt):
        blk = txt[m.start():m.start() + span]
        # The sentence that states the cornerstone tranche in money ("aggregate
        # amount of approximately US$562.0 million") is the single most reliable
        # marker of the real section, so it outranks any number of table-shaped
        # lines elsewhere in the document. Weighting it at 10 let a cross-
        # reference window full of CS_ROW-looking lines win instead, and Sanhua
        # then read its RETAIL CLAWBACK percentage as the cornerstone tranche.
        score = (100 * len(CS_AGG_USD.findall(blk))
                 + 5 * len(CS_AGG_PCT.findall(blk))
                 + len(CS_ROW.findall(blk)))
        if score > best_score:
            best, best_score = blk, score
    return best


def parse_cornerstone(txt, is_allotment):
    """Aggregate % of the offer, total amount, and investor names."""
    block = cornerstone_block(txt, 14000 if not is_allotment else 9000)
    if not block:
        return None
    # prospectuses repeat the table for each price scenario (low/mid/high x
    # with/without greenshoe); keep only the FIRST scenario or every investor
    # is counted 2-3x and the sum blows past 100%
    scen = [m.start() for m in re.finditer(r"Based on the Offer Price", block)]
    if len(scen) >= 2:
        block = block[:scen[1]]
    res = {}
    # "representing approximately X% of the Offer Shares" is also how the
    # prospectus states the HK PUBLIC OFFERING clawback allocation, and that
    # sentence can fall inside the cornerstone window: Sanhua's cornerstone
    # tranche read 10.0% when 10.0% was the retail reallocation. Accept a match
    # only when its own sentence is about the Cornerstone Investors and is not
    # a reallocation clause.
    for p in CS_AGG_PCT.finditer(block):
        v = float(p.group(1).replace(",", ""))
        if not 0 < v <= 100:
            continue
        ctx = clean(block[max(0, p.start() - 420):p.end() + 60])
        sent = ctx.rsplit(".", 1)[-1] if ctx.count(".") else ctx
        if not re.search(r"Cornerstone\s+Investor", ctx, re.I):
            continue
        if re.search(r"Public\s+Offering|reallocat|clawback|initially\s+available",
                     sent, re.I):
            continue
        res["cornerstone_pct"] = v
        res["cornerstone_pct_snip"] = clean(block[max(0, p.start() - 110):p.end() + 40])[:230]
        break
    a = CS_AGG_USD.search(block)
    if a:
        val = float(a.group(1).replace(",", ""))
        res["cornerstone_amt_m"] = val * (1000 if a.group(2).lower() == "billion" else 1)
        res["cornerstone_amt_ccy"] = "USD" if "US$" in a.group(0) else "HKD"
    # Table rows come in many layouts (amount column first, currency prefixes,
    # footnote markers, wrapped names). Per LINE: a name start, then a share
    # count (>=5 digits), then the FIRST percentage = % of Offer Shares.
    names, pcts, total_pct = [], [], None
    prev = ""
    for raw in block.split("\n"):
        line = clean(raw)
        if not line:
            continue
        if re.match(r"Total\b", line, re.I):
            if total_pct is None:
                t = re.search(rf"({NUM})\s*%", line)
                if t:
                    v = float(t.group(1).replace(",", ""))
                    if 0 < v <= 100:
                        total_pct = v
            prev = ""
            continue
        m = re.match(r"([A-Z(][^%]*?)\s[\d,()\sUSHK$.]*?([\d,]{5,})\s*(?:\(\d+\)\s*)?"
                     rf"({NUM})\s*%", line)
        if not m:
            prev = line if not re.search(r"\d", line) else ""
            continue
        nm = re.sub(r"[\s.]*(?:\(Note.*?\)|\(\d+\))?[\s.]*$", "",
                    re.sub(r"\s+", " ", m.group(1))).strip(" .")
        nm = re.sub(r"\s*(?:US\$|HK\$).*$", "", nm).strip(" .")
        # a name wrapped over two lines leaves its first half on the previous
        # (digit-free) line: "Zhongsheng Holdings / Company Limited (Note 2) ..."
        if prev and (len(nm) < 12 or nm[0].islower()
                     or re.match(r"(?:Company|Co\.|Limited|Management|Holdings?|"
                                 r"Investment|International)\b", nm)):
            nm = (prev + " " + nm).strip()
        prev = ""
        pct = float(m.group(3).replace(",", ""))
        if (4 <= len(nm) <= 80 and 0 < pct <= 100
                and not re.search(r"offer share|issued share|price|investor|"
                                  r"subscription|percentage|amount|^total", nm, re.I)):
            names.append(nm)
            pcts.append(pct)
    if names:
        res["cornerstone_investors"] = names[:15]
        res["cornerstone_n"] = len(names)
    # aggregate preference: explicit Total row > sum of rows > prose statement.
    # Guard: the rows are only "% of Offer Shares" if the table header says so —
    # allotment announcements carry a look-alike CONNECTED-CLIENTS table whose
    # first % column is "% of total issued H Shares" (Mixue read 5% instead of
    # ~45% from it).
    # decide by which column header comes FIRST: an offer-shares header means a
    # true cornerstone table; an issued-shares header first means the look-alike
    # connected-clients table (prose later in the block must not rescue it)
    m_off = re.search(r"(?:%|percentage)\s*of\s*(?:the\s*)?(?:total\s*)?"
                      r"(?:number\s*of\s*)?Offer\s*Shares", block, re.I)
    m_iss = re.search(r"(?:%|percentage)\s*of\s*(?:the\s*)?total\s*issued", block, re.I)
    header_ok = bool(m_off) and (not m_iss or m_off.start() < m_iss.start())
    agg = None
    if not header_ok:
        pcts = []
    if total_pct and header_ok:
        agg, how = total_pct, "table Total row"
    elif pcts and sum(pcts) <= 100:
        agg, how = round(sum(pcts), 1), "sum of table rows"
    if agg:
        if is_allotment:
            res["cornerstone_pct"] = agg
            res["cornerstone_pct_snip"] = f"allotment table ({how})"
        elif "cornerstone_pct" not in res:
            res["cornerstone_pct"] = agg
            res["cornerstone_pct_snip"] = f"prospectus table ({how}, at range low-end)"
    return res or None


def parse_offer_shares_total(txt):
    """Total Offer Shares under the Global Offering, from the labelled statement."""
    for r in OFFER_SHARES_TOTAL:
        m = r.search(txt)
        if m:
            v = float(m.group(1).replace(",", ""))
            if 1e5 <= v <= 5e10:
                return v, clean(txt[max(0, m.start() - 40):m.end() + 40])[:180]
    return None, None


def parse_greenshoe_pct(txt):
    """Stated greenshoe size. HK deals are almost always 15%; anything outside
    5-20% is a mis-read (a stray percentage in the same sentence) and dropped."""
    for m in SHOE_PCT.finditer(txt):
        raw = m.group(1) or m.group(2)
        if not raw:
            continue
        v = float(raw.replace(",", ""))
        if 5 <= v <= 20:
            return v, clean(txt[max(0, m.start() - 80):m.end() + 40])[:200]
    return None, None


def parse_price_range(txt):
    """Indicative range from the 'low-end / high-end' statements in the body."""
    lo = hi = None
    m = RANGE_LO.search(txt)
    if m:
        lo = float(m.group(1).replace(",", ""))
    m = RANGE_HI.search(txt)
    if m:
        hi = float(m.group(1).replace(",", ""))
    if lo and hi and lo < hi <= lo * 4:
        return lo, hi
    return (lo if lo and 0.01 <= lo <= 10000 else None), (hi if hi and 0.01 <= hi <= 10000 else None)


def parse_mktcap_stated(txt):
    """Issuer-stated expected market capitalisation; midpoint when a range."""
    best = None
    for m in MKTCAP_STATED.finditer(txt):
        def val(g_num, g_unit):
            if not g_num:
                return None
            v = float(g_num.replace(",", ""))
            u = (g_unit or "").lower()
            if u == "billion":
                v *= 1000
            elif u != "million":
                if v > 1e8:
                    v /= 1e6          # raw dollars
                elif v > 1e5:
                    v /= 1000         # thousands
            return v
        a = val(m.group(1), m.group(2))
        b = val(m.group(3), m.group(4))
        v = (a + b) / 2 if (a and b) else a
        # THRESHOLDS ARE NOT CAPS. The eligibility paragraph says "our expected
        # market capitalization at the time of Listing ... exceeds HK$4 billion
        # as required by Rule 8.05(3)" — company-sized, so the size guard below
        # never caught it, and because the largest match wins it beat the real
        # figure on four issuers at once. Reject the sentence by its wording.
        # Only what comes BEFORE the figure counts: "...is approximately
        # HK$9.95 billion, and the minimum prescribed public float..." is a
        # genuine statement whose next clause merely says "minimum".
        lead = txt[max(0, m.start() - 130):m.start()]
        if re.search(r"exceed|at\s+least|not\s+less\s+than|minimum|"
                     r"as\s+required\s+by|Rule\s+8\.05|Rule\s+8A\.06|requirement",
                     lead, re.I):
            continue
        # a listing-rule boilerplate mentions "not less than HK$125,000,000" (=125m);
        # real statements are company-sized, so keep the LARGEST plausible value
        if v and 200 <= v <= 5_000_000 and (best is None or v > best[0]):
            best = (v, clean(txt[max(0, m.start() - 60):m.end() + 30])[:220], bool(b))
    if not best:
        return None, None, None
    return best


def parse_offer_price_cap(txt):
    m = MAXPX.search(txt[:12000])
    if m:
        v = float(m.group(1).replace(",", ""))
        if 0.01 <= v <= 10000:
            return v, clean(txt[max(0, m.start() - 60):m.end() + 40])[:160]
    return None, None


def parse_offer_pct_of_capital(txt):
    """Smallest plausible value wins: the same sentence pattern is also used for
    individual cornerstone stakes, which are much smaller than the whole offer."""
    vals = []
    for m in OFFER_PCT.finditer(txt):
        v = float(m.group(1).replace(",", ""))
        if 1.0 <= v <= 60.0:
            vals.append((v, clean(txt[max(0, m.start() - 130):m.end() + 20])[:210]))
    if not vals:
        return None, None
    # the offer itself is the LARGEST such percentage in the document
    v, snip = max(vals, key=lambda t: t[0])
    return v, snip


def parse_shares_on_listing(txt):
    for m in SHARES_LISTING.finditer(txt[:400000]):
        v = float(m.group(1).replace(",", ""))
        if 1e6 <= v <= 1e12:
            return v, clean(m.group(0))[:180]
    return None, None


# --------------------------------------------------------------------- main --
def main():
    TEXT.mkdir(exist_ok=True)
    links = json.loads((ROOT / "data" / "batches" / "hkex_prospectus_links.json").read_text())["deals"]
    allot = json.loads((ROOT / "data" / "batches" / "hkex_allotment_files.json").read_text())["manifest"]

    # ALL prospectus parts per deal, in filing order. A split filing spreads the
    # summary / parties / cornerstone / financial sections across separate part
    # PDFs, so parsing only the biggest single part misses most sections.
    prosp_of, allot_of = {}, {}
    for e in links:
        files = [p["file"] for p in e.get("parts", []) if (CACHE / p["file"]).exists()]
        if files:
            prosp_of[e["code"]] = files
    for e in allot:
        files = [p["file"] for p in e.get("parts", []) if (CACHE / p["file"]).exists()]
        if files:
            allot_of[e["code"]] = files

    todo = sorted({f for v in prosp_of.values() for f in v}
                  | {f for v in allot_of.values() for f in v})
    print(f"caching text for {len(todo)} PDFs (parallel)...", flush=True)
    done = 0
    with ProcessPoolExecutor(max_workers=8) as ex:
        for _name, status in ex.map(cache_text, todo, chunksize=4):
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(todo)}", flush=True)

    print("parsing sections...", flush=True)
    recs = []
    for code in sorted(set(prosp_of) | set(allot_of)):
        rec = {"code": code}
        ptxt = "\n".join(read_cached(f) for f in prosp_of.get(code, []))
        if ptxt and len(ptxt) > 400_000 and not HDR_CORNER.search(ptxt):
            # full document, no cornerstone section anywhere: the deal HAD no
            # cornerstone tranche — that is data, not a gap
            rec["cornerstone_pct"] = 0
            rec["cornerstone_none"] = True
            rec["cornerstone_src"] = "prospectus (no cornerstone section)"
        if ptxt:
            syn = parse_syndicate(ptxt)
            if syn:
                rec["syndicate"] = syn
                for role, banks in syn.items():
                    if re.search(r"sponsor", role, re.I) and not re.search(
                            r"coordinator|bookrunner|lead manager", role, re.I):
                        rec.setdefault("sponsors", [])
                        rec["sponsors"] += [b for b in banks if b not in rec["sponsors"]]
                brs = []
                for role, banks in syn.items():
                    if re.search(r"bookrunner|global coordinator", role, re.I):
                        brs += [b for b in banks if b not in brs]
                if brs:
                    rec["bookrunners"] = brs[:12]
            cs = parse_cornerstone(ptxt, is_allotment=False)
            if cs:
                rec.update({k: v for k, v in cs.items() if k != "cornerstone_pct_snip"})
                rec["cornerstone_src"] = "prospectus"
            gs, gsnip = parse_greenshoe_pct(ptxt)
            if gs:
                rec["greenshoe_pct_stated"] = gs
                rec["greenshoe_pct_snip"] = gsnip
            lo, hi = parse_price_range(ptxt)
            if lo:
                rec["range_lo"] = lo
            if hi:
                rec["range_hi"] = hi
            mkt, msnip, was_range = parse_mktcap_stated(ptxt)
            if mkt:
                rec["mktcap_stated_hkdm"] = round(mkt, 1)
                rec["mktcap_stated_snip"] = msnip
            cap, snip = parse_offer_price_cap(ptxt)
            if cap:
                rec["offer_price_cap"] = cap
                rec["offer_price_cap_snip"] = snip
            sh, ssnip = parse_shares_on_listing(ptxt)
            if sh:
                rec["shares_on_listing"] = sh
                rec["shares_on_listing_snip"] = ssnip
            op, opsnip = parse_offer_pct_of_capital(ptxt)
            if op:
                rec["offer_pct_of_capital"] = op
                rec["offer_pct_of_capital_snip"] = opsnip
        atxt = "\n".join(read_cached(f) for f in allot_of.get(code, []))
        if atxt:
            osh, osnip = parse_offer_shares_total(atxt)
            if osh:
                rec["offer_shares_total"] = osh
                rec["offer_shares_total_snip"] = osnip
            cs = parse_cornerstone(atxt, is_allotment=True)
            if cs and cs.get("cornerstone_pct") is not None:
                rec.update(cs)                       # final allocation wins
                rec["cornerstone_src"] = "allotment"
            elif cs and "cornerstone_pct" not in rec:
                rec.update(cs)
                rec["cornerstone_src"] = "allotment"
        if len(rec) > 1:
            recs.append(rec)

    n = len(recs)
    OUT.write_text(json.dumps(
        {"batch": "extracted_deep",
         "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": n,
         "with_sponsors": sum(1 for r in recs if r.get("sponsors")),
         "with_bookrunners": sum(1 for r in recs if r.get("bookrunners")),
         "with_cornerstone_pct": sum(1 for r in recs if r.get("cornerstone_pct")),
         "with_cornerstone_names": sum(1 for r in recs if r.get("cornerstone_investors")),
         "with_cap": sum(1 for r in recs if r.get("offer_price_cap")),
         "with_shares": sum(1 for r in recs if r.get("shares_on_listing")),
         "with_offer_pct": sum(1 for r in recs if r.get("offer_pct_of_capital")),
         "with_range_lo": sum(1 for r in recs if r.get("range_lo")),
         "with_mktcap_stated": sum(1 for r in recs if r.get("mktcap_stated_hkdm")),
         "cornerstone_none": sum(1 for r in recs if r.get("cornerstone_none")),
         "with_greenshoe_pct": sum(1 for r in recs if r.get("greenshoe_pct_stated")),
         "with_offer_shares_total": sum(1 for r in recs if r.get("offer_shares_total")),
         "deals": recs}, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {n} deals | sponsors {sum(1 for r in recs if r.get('sponsors'))} | "
          f"bookrunners {sum(1 for r in recs if r.get('bookrunners'))} | "
          f"cornerstone% {sum(1 for r in recs if r.get('cornerstone_pct'))} | "
          f"cs-names {sum(1 for r in recs if r.get('cornerstone_investors'))} | "
          f"cap {sum(1 for r in recs if r.get('offer_price_cap'))} | "
          f"shares {sum(1 for r in recs if r.get('shares_on_listing'))} | "
          f"offer%cap {sum(1 for r in recs if r.get('offer_pct_of_capital'))}")


if __name__ == "__main__":
    main()
