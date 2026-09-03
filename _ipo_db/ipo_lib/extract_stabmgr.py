#!/usr/bin/env python3
"""Stabilising manager per deal, from the deal's own filings.

Every allotment announcement carries the same sentence on its cover pages:

    In connection with the Global Offering, Guotai Junan Securities (Hong Kong)
    Limited as stabilizing manager (the "Stabilizing Manager") (or its
    affiliates or any person acting for it) ... may over-allocate ...

so the name sits between "In connection with the Global Offering," and "as
stabilizing manager". A parties-table form ("Stabilizing Manager: CLSA
Limited") is accepted as a fallback.

THE ALLOTMENT ANNOUNCEMENT IS NOT ALWAYS ENOUGH. Innolight (3308) ran a 15%
over-allotment option and its allotment announcement does not contain the
string "stabilis"/"stabiliz" at ALL — the manager is named only in the
PROSPECTUS, in the definitions glossary:

    "Stabilizing Manager"   Goldman Sachs (Asia) L.L.C.   "State Council" ...

Reading the allotment announcement alone left 110 deals that HAVE a greenshoe
with no manager, which cannot be right: a deal with an over-allotment option
has someone holding it. So the prospectus glossary is a second pass, run only
for deals the announcement did not name, and `src` records which document and
which pattern produced the name. Nothing is ever inferred from the sponsor.

The bank that runs stabilisation is the one holding the greenshoe and the
after-market bid, so grouping returns by it answers a different question from
the sponsor league: not who sold the deal, but who defended it.

Writes data/batches/stabilizing_managers.json.
Run:  python ipo_lib/extract_stabmgr.py
"""
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ipo_lib"))
from clean_names import clean_party_element                      # noqa: E402

TEXT = ROOT / "scrape" / "text_cache"
OUT = ROOT / "data" / "batches" / "stabilizing_managers.json"
HEAD = 40000            # the paragraph is always in the opening pages

# NAME, as stabilizing manager  — the standard cover sentence
#
# The name may CONTAIN periods: SHEIN's stabiliser is "Goldman Sachs (Asia)
# L.L.C.", and a plain [^.;] name class stops dead at the first dot, so the
# match never reaches ", as the stabilizing manager" and the deal comes back
# unnamed. A dot is kept when it is an ABBREVIATION dot and dropped when it
# ends a sentence, on two signals:
#   * a dot NOT followed by whitespace-then-capital ("L.L.C.," / "Ltd. as");
#   * a dot straight after a lone initial, which is what "J.P. Morgan" needs —
#     the P. there IS followed by " Morgan" and would otherwise read as a
#     sentence end, losing every J.P. Morgan-stabilised deal.
# Anything else stops the name, so the match can never run backwards over a
# real sentence boundary into the previous sentence.
RE_INLINE = re.compile(
    r"In connection with the (?:Global Offering|Share Offer|Offering)\s*,?\s+"
    r"(?P<name>[A-Z](?:[^.;]|\.(?!\s+[A-Z])|(?<=\b[A-Z])\.){3,90}?)"
    r"\s*,?\s+(?:as|acting as)\s+(?:the\s+)?stabili[sz]ing\s+manager", re.I)
# "NAME has been appointed as the Stabilising Manager" — Conant Optical's
# allotment announcement names Guotai Junan ONLY in this phrasing, with no
# "In connection with..." sentence anywhere. Same dot-tolerant name class.
RE_APPOINTED = re.compile(
    r"(?:^|[,.;:'’”\"])\s*"
    r"(?P<name>[A-Z](?:[^.;,'’”\"]|\.(?!\s+[A-Z])|(?<=\b[A-Z])\.|,(?=\s+Limited\b)){3,90}?)"
    r"\s+has\s+been\s+appointed\s+as\s+(?:the\s+)?stabili[sz]ing\s+manager", re.I)
# a FILED absence is a fact, not a gap: USAS Building (2671) ran a greenshoe
# and its announcement still says plainly that no stabilising manager exists.
# Recording it stops the deal reading as a parser miss forever.
RE_NONE = re.compile(
    r"No\s+stabili[sz]ing\s+manager\s+(?:will\s+be|has\s+been|was|is)\s+"
    r"(?:appointed|engaged)", re.I)
# WHEN the shoe dies — the single date the aftermarket desk plans around.
# Every allotment announcement states it the same way: "... and on Saturday,
# 26 September 2026, being the 30th day after the last day for lodging
# applications under the Hong Kong Public Offering". Fallback forms accepted:
# "stabilization period ... end(s) on <date>" and "no further stabilizing
# action ... after <date>".
# Both orders occur in real filings: "26 September 2026" (HK/UK house style)
# and "September 26, 2026" (US style, e.g. Mech-Mind).
_DMY = r"\d{1,2}\s+[A-Z][a-z]+\s+20\d{2}"
_MDY = r"[A-Z][a-z]+\s+\d{1,2},\s*20\d{2}"
_DATE = rf"(?P<d>{_DMY}|{_MDY})"
RE_STAB_END = [
    re.compile(rf"{_DATE}\s*,?\s+being\s+the\s+30th\s+day\s+after"),
    re.compile(rf"stabili[sz]ation(?:\s+period)?[^.]{{0,160}}?"
               rf"(?:expire|end)(?:s|d)?\s+on\s+(?:\w+day\s*,?\s+)?{_DATE}", re.I),
    re.compile(rf"no\s+(?:further\s+)?stabili[sz]\w+\s+action[^.]{{0,120}}?"
               rf"after\s+(?:\w+day\s*,?\s+)?{_DATE}", re.I),
    # the date can trail in a parenthetical, with either wording:
    #   "(which is expected to be 23 September 2026)"   [SHEIN style]
    #   "(which is Saturday, September 19, 2026)"       [Ingenic style]
    re.compile(rf"30th\s+day\s+after[^)]{{0,150}}?which\s+is\s+"
               rf"(?:expected\s+to\s+be\s+)?(?:\w+day\s*,?\s+)?{_DATE}", re.I),
]
_MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}


def stab_end_iso(txt):
    """First stated end-of-stabilisation date in the text, as ISO, or None."""
    for rx in RE_STAB_END:
        m = rx.search(txt)
        if not m:
            continue
        parts = m.group("d").replace(",", " ").split()
        if len(parts) != 3:
            continue
        # "26 September 2026" or "September 26 2026"
        if parts[0].isdigit():
            day, mon, yr = parts
        else:
            mon, day, yr = parts
        mo = _MONTHS.get(mon.capitalize())
        if mo:
            return f"{int(yr):04d}-{mo:02d}-{int(day):02d}"
    return None
# a parties table: "Stabilizing Manager: NAME"
RE_LABEL = re.compile(
    r"stabili[sz]ing\s+manager\s*[::]\s*(?P<name>[A-Z][^\n:;]{3,90})", re.I)
# the PROSPECTUS definitions glossary, which is a two-column term/definition
# list flattened to:  "Stabilizing Manager" <NAME> "Next Defined Term"
# The name therefore runs to the next opening quote. Curly quotes are what the
# PDF text actually carries, so both curly and straight forms are accepted.
QUOTE = "“”‘’\"'"
RE_GLOSS = re.compile(
    rf"stabili[sz]ing\s+manager\s*[{QUOTE}]\s*"
    rf"(?:refers?\s+to|means|shall\s+mean|has\s+the\s+meaning[^{QUOTE}]{{0,80}})?\s*"
    rf"(?P<name>[A-Z][^{QUOTE}]{{3,90}}?)\s*[{QUOTE}]", re.I)

# text that means the regex ran off into the boilerplate clause rather than a name
JUNK = re.compile(r"\bshares?\b|such price|such amounts|acting for it|"
                  r"over-?allocate|affiliates|no obligation|there is no", re.I)


def tidy(nm):
    nm = re.sub(r"\s+", " ", nm or "").strip(" ,;:•")
    nm = re.sub(r"^(?:each of|and|the)\s+", "", nm, flags=re.I)
    # a trailing parenthetical defined-term ("(the "Stabilizing Manager")")
    nm = re.sub(r"\s*\(.*$", "", nm).strip(" ,;:")
    # PDF text extraction splits a word after its first letter often enough to
    # matter: Yuen Meta came out "Y uen Meta", which then keys as "Y uen". A
    # lone capital followed by a LOWERCASE continuation is always that
    # artefact — real names put a capital after an initial ("J P Morgan"), so
    # this cannot glue two genuine tokens together.
    nm = re.sub(r"\b([A-Z]) ([a-z])", r"\1\2", nm)
    return clean_party_element(nm) or nm


# entity/geography words that carry no identity on their own
GENERIC = {"limited", "ltd", "llc", "llc.", "inc", "incorporated", "company",
           "co", "securities", "capital", "international", "global", "markets",
           "asia", "pacific", "hong", "kong", "hk", "branch", "plc", "sa", "ag",
           "corporation", "corp", "holdings", "group", "investment",
           "investments", "brokerage", "financial", "finance", "corporate",
           "asset", "management", "banking", "bank"}
# heads that mean nothing alone — "China" is CICC, China Merchants AND China
# Securities, so a one-token key would fold three unrelated houses into one
PREFIX = {"china", "bank", "first", "new", "industrial", "shanghai", "everbright"}


def canonical(nm):
    """Bank family, so 'Goldman Sachs (Asia) L.L.C.' and 'Goldman Sachs
    International' land in the same league row — while keeping CICC, China
    Merchants and China Securities apart.

    Take the leading tokens (three when the first is a prefix word), then trim
    generic tails but never below the minimum that keeps the house identifiable.
    """
    s = re.sub(r"\(.*?\)", " ", nm)                 # drop parentheticals
    # periods bind INSIDE a token ("J.P." -> "JP", "L.L.C." -> "LLC"); commas
    # separate. Replacing both with a space split J.P. Morgan into "J P".
    s = s.replace(".", "").replace(",", " ")
    toks = [t for t in re.split(r"\s+", s) if t]
    if not toks:
        return nm
    lead_is_prefix = toks[0].lower() in PREFIX
    keep = 3 if lead_is_prefix else 2
    toks = toks[:keep]
    floor = 2 if lead_is_prefix else 1
    while len(toks) > floor and toks[-1].lower() in GENERIC:
        toks.pop()
    return " ".join(toks)


def _try(txt, patterns):
    """First pattern that yields a name that survives the junk filter."""
    for rx, tag in patterns:
        m = rx.search(txt)
        if not m:
            continue
        cand = tidy(m.group("name"))
        if not cand or JUNK.search(cand) or len(cand) < 4:
            continue
        return cand, tag
    return None, None


def main():
    allot, prosp = defaultdict(list), defaultdict(list)
    for p in sorted(TEXT.glob("*.txt")):
        m = re.match(r"(allot|prosp|newlist)_(\d{4})_", p.name)
        if not m:
            continue
        (allot if m.group(1) == "allot" else prosp)[m.group(2)].append(p)

    out, misses, filed_none = [], [], 0
    n_end = 0
    for code in sorted(set(allot) | set(prosp)):
        name, how, doc, none_doc = None, None, None, None
        end_date = None
        # PASS 1 — the allotment announcement. Post-pricing and authoritative,
        # and its cover paragraph is only ever in the opening pages.
        for p in allot.get(code, []):
            try:
                txt = re.sub(r"\s+", " ", p.read_text(errors="ignore")[:HEAD])
            except OSError as e:
                print(f"  {code}: unreadable {p.name} ({e}) — skipped",
                      file=sys.stderr)
                continue
            if end_date is None:
                end_date = stab_end_iso(txt)
            name, how = _try(txt, ((RE_INLINE, "cover sentence"),
                                   (RE_APPOINTED, "appointment sentence"),
                                   (RE_LABEL, "parties table")))
            if name:
                doc = "allotment announcement"
                break
            if RE_NONE.search(txt):
                none_doc = "allotment announcement"
        # PASS 2 — the prospectus, for deals the announcement never named. The
        # glossary sits deep in the definitions section, so this reads the whole
        # part rather than a head window; the cheap substring test keeps that
        # from costing anything on the parts that never mention stabilisation.
        if not name and not none_doc:
            for p in prosp.get(code, []):
                # this volume evicts cache files to iCloud and a faulted-in
                # read can die with TimeoutError [Errno 60]; one unreadable
                # file must cost ONE file, not the whole 524-deal pass
                try:
                    raw = p.read_text(errors="ignore")
                except OSError as e:
                    print(f"  {code}: unreadable {p.name} ({e}) — skipped",
                          file=sys.stderr)
                    continue
                if "tabili" not in raw:
                    continue
                txt = re.sub(r"\s+", " ", raw)
                name, how = _try(txt, ((RE_GLOSS, "definitions glossary"),
                                       (RE_INLINE, "cover sentence"),
                                       (RE_APPOINTED, "appointment sentence"),
                                       (RE_LABEL, "parties table")))
                if name:
                    doc = "prospectus"
                    break
                if RE_NONE.search(txt):
                    none_doc = "prospectus"
                    break
        rec_extra = {}
        if end_date:
            rec_extra["stabilization_end_date"] = end_date
            n_end += 1
        if name:
            out.append({"code": code, "stabilizing_manager": name,
                        "stabilizing_manager_key": canonical(name),
                        "src": f"{doc}, {how}", **rec_extra})
        elif none_doc:
            # the FILING says none exists — record the fact so the deal never
            # again reads as an extraction miss
            out.append({"code": code, "stabilizing_manager_none": True,
                        "src": f"{none_doc}: 'no stabilizing manager will be "
                               f"appointed' stated in the filing", **rec_extra})
            filed_none += 1
        elif rec_extra:
            out.append({"code": code, **rec_extra})
            misses.append(code)
        else:
            misses.append(code)

    OUT.write_text(json.dumps(
        {"batch": "stabilizing_managers",
         "note": ("Stabilising manager per deal, two passes: the allotment "
                  "announcement (cover/appointment sentence, parties table), "
                  "then the prospectus (definitions glossary first) for deals "
                  "the announcement never named. stabilizing_manager_none "
                  "records a FILED 'no stabilizing manager will be appointed'. "
                  "Never inferred from the sponsor."),
         "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(out), "no_manager_named": len(misses),
         "filed_none": filed_none,
         "deals": out}, ensure_ascii=False, indent=1))
    named = sum(1 for r in out if r.get("stabilizing_manager"))
    print(f"wrote {OUT}: {named} deals with a named stabilising manager, "
          f"{filed_none} with a FILED 'none appointed', {len(misses)} without, "
          f"{n_end} with a stated stabilisation end date")
    top = Counter(r["stabilizing_manager_key"] for r in out
                  if r.get("stabilizing_manager_key")).most_common(12)
    for k, n in top:
        print(f"   {n:>4}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
