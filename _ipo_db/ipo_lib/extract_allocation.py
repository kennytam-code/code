#!/usr/bin/env python3
"""The allocation outcome of every deal: who actually got the shares.

Reads each Allotment Results announcement for the four facts the subscription
multiples alone do not tell you:

  intl_x            international / placing subscription level, read from the
                    INTERNATIONAL OFFERING section itself (the generic parser
                    was taking the public table's number for both tranches)
  intl_placees      number of placees in the international tranche
  public_pct_final  the public tranche's share of the offering AFTER
                    reallocation - the number that decides how starved the
                    day-1 tape is
  clawback          whether the announcement says the claw-back was triggered,
                    and how many shares were reallocated from the
                    international offering

Why it matters: a public book of 300x normally forces the clawback (50% of the
deal to retail under the pre-Aug-2025 rules, 35% under Mechanism A after). The
clawback proviso lapses when the international tranche is not fully subscribed
- then only the SHORTFALL is passed to retail. Filling the placing book to just
under 1x therefore keeps ~80% of a deal in ~100 chosen hands and starves the
public tranche, which is the pattern behind the 0.92-0.99x cluster.

Writes data/batches/extracted_allocation.json. Supports --only / --new.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scrape" / "pdf_cache"
MANIFEST = ROOT / "data" / "batches" / "hkex_allotment_files.json"
OUT = ROOT / "data" / "batches" / "extracted_allocation.json"

NUM = r"[\d,]+(?:\.\d+)?"


def fnum(s):
    try:
        return float(str(s).replace(",", ""))
    except ValueError:
        return None


def text_of(code, parts, pages=18):
    t = ""
    for p in parts:
        f = CACHE / p["file"]
        if not f.exists():
            continue
        try:
            r = PdfReader(str(f))
            t += "\n".join((pg.extract_text() or "") for pg in r.pages[:pages])
        except Exception as e:
            print(f"  unreadable {f.name}: {e}", file=sys.stderr)
    return re.sub(r"\s+", " ", t)


# --- the international tranche, from its own section --------------------------
# headings seen: INTERNATIONAL OFFERING / INTERNATIONAL OFFER / INTERNATIONAL
# PLACING / PLACING; "Subscription Level (before taking into account the Offer
# Size Adjustment Option) 8.06 times" carries a parenthetical (Midea)
RE_INTL_TABLE = re.compile(
    r"(?:INTERNATIONAL\s+(?:OFFER(?:ING)?|PLACING)|\bPLACING)\b.{0,400}?"
    r"(?:No\.|Number)\s+of\s+placees\s+([\d,]+).{0,160}?"
    r"Subscription\s+[Ll]evel\s*(?:\([^)]{0,140}\))?\s*(" + NUM + r")\s*times", re.S)
# 2021-23 prose: "allotted to a total of 218 placees under the Placing"
RE_PLACEES_PROSE = re.compile(r"(?:a\s+total\s+of\s+)?([\d,]+)\s+placees", re.I)
RE_INTL_PROSE = [
    # "the International Offering was (moderately|significantly) over-subscribed
    #  ... approximately 3.2 times"
    re.compile(r"International\s+(?:Offer(?:ing)?|Placing)[^.]{0,120}?(?:over|under)-?subscribed"
               r"[^.]{0,80}?(?:approximately\s+)?(" + NUM + r")\s*times", re.I),
    # "... representing approximately 3.2 times of the total number of
    #  International Offer Shares"
    re.compile(r"(?:approximately\s+)?(" + NUM + r")\s*times\s+(?:of\s+)?the\s+(?:total\s+)?"
               r"(?:number\s+of\s+)?International\s+(?:Offer|Placing)\s+Shares", re.I),
]
RE_INTL_UNDER = re.compile(
    r"International\s+(?:Offer(?:ing)?|Placing)[^.]{0,160}?(?:has\s+been\s+|was\s+|were\s+)?"
    r"(?:under-?subscribed|not\s+fully\s+subscribed)", re.I)

# --- the final split ---------------------------------------------------------
RE_PUB_FINAL = [
    re.compile(r"Number\s+of\s+Offer\s+Shares\s+in\s+(?:the\s+)?(?:Hong\s+Kong\s+)?Public\s+Offer"
               r"(?:ing)?\s*\(after[^)]{0,140}\)\s*([\d,]{5,})", re.I),
    re.compile(r"Final\s+no\.\s+of\s+Offer\s+Shares\s+under\s+the\s+(?:Hong\s+Kong\s+)?Public\s+Offer"
               r"(?:ing)?\s*(?:\([^)]{0,140}\))?\s*([\d,]{5,})", re.I),
    re.compile(r"Number\s+of\s+(?:Hong\s+Kong\s+|Public\s+)Offer\s+Shares?\s*:?\s*([\d,]{5,})\s+(?:H\s+)?Shares"
               r"\s*\((?:as\s+adjusted\s+)?after[^)]{0,80}\)", re.I),
    re.compile(r"(?:a\s+total\s+of\s+)?([\d,]{5,})\s+Hong\s+Kong\s+Offer\s+Shares[^.]{0,80}?"
               r"representing\s+(?:approximately\s+)?(" + NUM + r")\s*%", re.I),
]
RE_INTL_FINAL = [
    re.compile(r"Number\s+of\s+offer\s+shares\s+in\s+(?:the\s+)?International\s+Offer(?:ing)?"
               r"\s*\(after[^)]{0,140}\)\s*([\d,]{5,})", re.I),
    re.compile(r"Final\s+no\.\s+of\s+Offer\s+Shares\s+under\s+the\s+International\s+Offer(?:ing)?"
               r"\s*(?:\([^)]{0,140}\))?\s*([\d,]{5,})", re.I),
    re.compile(r"Number\s+of\s+(?:International\s+Offer|Placing)\s+Shares?\s*:?\s*([\d,]{5,})\s+(?:H\s+)?Shares"
               r"\s*\((?:as\s+adjusted\s+)?after[^)]{0,80}\)", re.I),
]
# the notice's own percentage line, where it prints one (EDA: "% of Offer
# Shares under the Hong Kong Public Offer to the Global Offering 15.20%")
RE_PUB_PCT_DIRECT = re.compile(
    r"%\s+of\s+Offer\s+Shares\s+under\s+the\s+(?:Hong\s+Kong\s+)?Public\s+Offer(?:ing)?\s+to\s+the\s+"
    r"Global\s+Offering\s*[:：]?\s*(" + NUM + r")\s*%", re.I)
RE_TOTAL = [
    # full-width colons appear in some notices ("Global Offering ： 97,625,000")
    re.compile(r"Number\s+of\s+Offer\s+Shares\s+(?:under\s+the\s+Global\s+Offering\s*)?[:：]?\s*([\d,]{5,})", re.I),
    re.compile(r"Number\s+of\s+Offer\s+Shares\s+([\d,]{5,})\s+Number\s+of\s+Offer\s+Shares\s+in", re.I),
]
RE_CLAW = re.compile(r"Claw-?back\s+triggered\s*:?\s*(Yes|No|N/?A)", re.I)
RE_REALLOC = re.compile(
    r"(?:No\.|Number)\s+of\s+Offer\s+Shares\s+reallocated\s+from\s+the\s+International\s+Offering"
    r"[^\d]{0,40}([\d,]{4,})", re.I)
RE_CLAW_PROSE = re.compile(
    r"claw-?back\s+(?:mechanism|arrangement)[^.]{0,120}?(?:has\s+been\s+|was\s+)?(?:triggered|applied|not\s+triggered|will\s+not)[^.]{0,80}", re.I)
RE_MECH = re.compile(r"Mechanism\s+([AB])\b")
RE_PUB_X = re.compile(
    r"HONG\s+KONG\s+PUBLIC\s+OFFER(?:ING)?.{0,400}?Subscription\s+[Ll]evel\s+(" + NUM + r")\s*times", re.S)


def parse(flat):
    rec = {}
    m = RE_INTL_TABLE.search(flat)
    if m:
        rec["intl_placees"] = int(fnum(m.group(1)) or 0) or None
        rec["intl_x"] = fnum(m.group(2))
        rec["intl_src"] = "table"
    else:
        for r in RE_INTL_PROSE:
            m = r.search(flat)
            if m:
                v = fnum(m.group(1))
                if v and 0.05 <= v <= 5000:
                    rec["intl_x"], rec["intl_src"] = v, "prose"
                    break
    if RE_INTL_UNDER.search(flat):
        rec["intl_undersubscribed_stated"] = True
    if "intl_placees" not in rec:
        m = RE_PLACEES_PROSE.search(flat)
        if m:
            rec["intl_placees"] = int(fnum(m.group(1)) or 0) or None
    m = RE_PUB_X.search(flat)
    if m:
        rec["public_x"] = fnum(m.group(1))
    for r in RE_TOTAL:
        m = r.search(flat)
        if m:
            rec["offer_shares_total"] = fnum(m.group(1))
            break
    for r in RE_PUB_FINAL:
        m = r.search(flat)
        if m:
            rec["public_shares_final"] = fnum(m.group(1))
            if r.groups == 2:
                rec["public_pct_final"] = fnum(m.group(2))
            break
    for r in RE_INTL_FINAL:
        m = r.search(flat)
        if m:
            rec["intl_shares_final"] = fnum(m.group(1))
            break
    m = RE_PUB_PCT_DIRECT.search(flat)
    if m and "public_pct_final" not in rec:
        rec["public_pct_final"] = fnum(m.group(1))
    pub, intl = rec.get("public_shares_final"), rec.get("intl_shares_final")
    tot = rec.get("offer_shares_total")
    # a "total" no bigger than the public tranche is a mis-read; the two
    # tranches summed is the fallback, and a public share above 70% of any
    # total is left unstated rather than published as a 100% retail deal
    if pub and tot and tot <= pub and intl:
        tot = pub + intl
    if pub and not tot and intl:
        tot = pub + intl
    if pub and tot and tot > pub and "public_pct_final" not in rec:
        pct = round(100 * pub / tot, 2)
        if pct <= 70:
            rec["public_pct_final"] = pct
    m = RE_CLAW.search(flat)
    if m:
        rec["clawback"] = m.group(1).upper().replace("N/A", "NA")
    else:
        m = RE_CLAW_PROSE.search(flat)
        if m:
            s = m.group(0).lower()
            rec["clawback"] = "NO" if ("not" in s or "will not" in s) else "YES"
            rec["clawback_src"] = "prose"
    m = RE_REALLOC.search(flat)
    if m:
        rec["reallocated_from_intl"] = fnum(m.group(1))
    m = RE_MECH.search(flat)
    if m:
        rec["mechanism"] = m.group(1)
    return rec


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import incremental
    manifest = json.loads(MANIFEST.read_text())["manifest"]
    only = incremental.wanted(OUT, [m["code"] for m in manifest])
    rows = manifest if only is None else [m for m in manifest if str(m["code"]) in only]
    if only is not None:
        print(f"  incremental: {len(rows)} deal(s) to parse")
    recs = []
    for i, m in enumerate(rows):
        flat = text_of(m["code"], m.get("parts", []))
        if len(flat) < 300:
            continue
        rec = parse(flat)
        rec["code"] = m["code"]
        recs.append(rec)
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(rows)} parsed", flush=True)
    recs = incremental.merge(OUT, recs, only)
    OUT.write_text(json.dumps(
        {"batch": "extracted_allocation",
         "note": __doc__.split("\n\n")[1].strip(),
         "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(recs),
         "with_intl_x": sum(1 for r in recs if r.get("intl_x") is not None),
         "with_public_pct_final": sum(1 for r in recs if r.get("public_pct_final") is not None),
         "with_clawback": sum(1 for r in recs if r.get("clawback")),
         "deals": recs}, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {len(recs)} deals | intl_x {sum(1 for r in recs if r.get('intl_x') is not None)} "
          f"| public_pct_final {sum(1 for r in recs if r.get('public_pct_final') is not None)} "
          f"| clawback {sum(1 for r in recs if r.get('clawback'))}")


if __name__ == "__main__":
    main()
