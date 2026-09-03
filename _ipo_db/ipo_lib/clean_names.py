#!/usr/bin/env python3
"""Normalise cornerstone-investor names pulled out of prospectus tables.

The raw parse is 27% unusable: PDF text extraction leaves table headers
("Top 10"), scenario-clause tails ("...Option) Top"), letter-spacing damage
("Y anlord Investment"), prose fragments ("The Placee group holds A Shares")
and duplicates. Those are fine while the field is only counted, but the field is
now a VISIBLE Database column and a Screener match key, so a name has to be a
name. Anything that cannot be cleaned into one is dropped rather than shown.

Reused by merge_batches.py (writes the clean list) and by the workbook build.
"""
import re

# a table header or scenario tail, never an investor
DROP = re.compile(
    r"^(top\s*\d*|total|sub-?total|name(s)?(\s+of)?.*|placee[s]?|investor[s]?|"
    r"cornerstone\s+investor[s]?|no\.|number|shares?|amount|percentage|approximate|"
    r"n/?a|nil|none|others?|remarks?|notes?)$", re.I)
# A name that is nothing but corporate furniture — "Holdings Limited",
# "Corporation Limited" — is what is left when a line break eats the front of
# the real name. It identifies no one, so it is not a name.
GENERIC = re.compile(
    r"^(the\s+)?(hong\s+kong|holdings?|corporation|company|worldwide|international|group,?|"
    r"investments?|capital|fund[s]?|management|asset[s]?|partners|master\s+fund|"
    r"printing\s+company|open-?ended\s+fund\s+company|limited\s+partners?|"
    r"connected\s+client|pte\.?|co\.?,?|limited|ltd|inc|llc|l\.?p\.?)"
    r"(\s+(holdings?|corporation|company|limited|ltd\.?|inc|llc|fund|l\.?p\.?,?|"
    r"master\s+fund|pte\.?|co\.?,?))*\.?,?$", re.I)
# a verb makes it a sentence, not a name — no corporate word rescues it
VERB = re.compile(r"\b(is|are|was|were|has|have|holds?|owns?|will|shall|"
                  r"acquired|entered|agreed)\b", re.I)
# softer prose markers, which a real company name may legitimately survive
PROSE = re.compile(r"\b(based|assuming|exercised|allotment|represent(s|ing)?|"
                   r"approximately)\b", re.I)
# "(assuming the Over-allotment Option is not exercised in full) Top 10" tails
TAIL = re.compile(r"^[^()]*\)\s*", re.I)
# leading throwaway groups: "(approximate) (approximate) Neptune" -> "Neptune"
LEAD_PAREN = re.compile(r"^(\s*\([^)]{0,30}\)\s*)+")
SPACED = re.compile(r"\b([B-HJ-Zb-hj-z])\s+([a-z]{3,})")   # "Y anlord" (not A/I)
QUOTES = re.compile(r"[“”\"'‘’]")
# strip only a QUOTED short-form in brackets — 'CLSA Limited ("CLSA")'. A plain
# parenthetical such as "(Singapore)" is part of the legal name and stays.
PAREN_ABBREV = re.compile(r"\(\s*[“\"'][^)]{1,24}[”\"']\s*\)")


def clean_investor(raw):
    """One raw cell -> a usable investor name, or None if it never was one."""
    if not raw:
        return None
    s = re.sub(r"\s+", " ", str(raw)).strip()
    # cover-page bleed classes (shared with the bank lists, defined below):
    # section headings, page numbers, and footnote references ("Please refer
    # to Note (1). No" is a pointer, not an investor)
    s = _P_HEADING.sub(" ", s)
    s = _P_PAGENO.sub(" ", s).strip()
    if _P_FOOTREF.match(s):
        return None
    # table-bleed prefixes: the Yes/No column and the row label ride along
    s = re.sub(r"^(?:No|Yes|Cornerstone\s+Investors?)\s+(?=[A-Z])", "", s)
    # the shareholder-table row label and section bleed glue onto names
    # ("Shareholder Norges Bank", "Offering Relationship Guohui")
    s = re.sub(r"^(?:Existing\s+)?Shareholders?\s+(?=[A-Z])", "", s)
    s = re.sub(r"^Offering\s+Relationship\s+(?=[A-Z])", "", s, flags=re.I)
    s = s.lstrip("/·•—– ").strip()
    # a subscription AMOUNT rode into the name cell ("Zhijia No. 1 RMB70,000,000")
    s = re.sub(r"\s*(?:RMB|HK\$|US\$|USD|HKD|CNY|JPY|¥|\$)\s*[\d,]+(?:\.\d+)?"
               r"\s*(?:million|mn|bn|billion)?\s*$", "", s, flags=re.I)
    # a subtotal row or a "... Top" table tail is never an investor
    if re.search(r"\bsub-?totals?\b", s, re.I) or re.search(r"\sTop\s*\d*$", s):
        return None
    # ...and so does the TAIL of the previous row's name ("Limited China Orient
    # Enhanced Income Fund" = "…Limited" + the next investor)
    s = re.sub(r"^(?:Limited|Ltd\.?|Inc\.?|LLC|SPC|SP|L\.P\.?|Company|Corporation)\s+"
               r"(?=[A-Z][a-z])", "", s)
    # a following honorific that belongs to the NEXT row: "Mr. Gong Chaohui Mr"
    s = re.sub(r"\s+(?:Mr|Ms|Mrs|Dr)\.?$", "", s)
    # drop a leading scenario clause that closed mid-cell: "...Option) Top 10"
    if ")" in s and "(" not in s.split(")")[0]:
        s = TAIL.sub("", s).strip()
    s = LEAD_PAREN.sub("", s).strip()
    s = PAREN_ABBREV.sub("", s)                 # 'CLSA Limited ("CLSA")' -> 'CLSA Limited'
    s = QUOTES.sub("", s).strip(" ,.;:-—·")
    s = SPACED.sub(r"\1\2", s)                  # 'Y anlord' -> 'Yanlord'
    # a "/"-joined part with no latin AND no CJK letters is encoding mojibake
    # ("Yang Litie/เᓿ᚛") — bilingual halves both carry real letters and stay
    parts = [p.strip() for p in s.split("/")]
    if len(parts) > 1:
        parts = [p for p in parts if re.search(r"[A-Za-z一-鿿]", p)]
        s = " / ".join(parts)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) < 4 or len(s) > 70:
        return None
    if DROP.match(s) or GENERIC.match(s):
        return None
    if re.match(r"^top\s*\d+", s, re.I):        # "Top 10 shareholders"
        return None
    if VERB.search(s):                          # a sentence, whatever else it holds
        return None
    if PROSE.search(s) and not re.search(r"\b(Investment|Capital|Fund|Asset|Holdings?|"
                                         r"Limited|Ltd|Inc|LLC|Pte|Group|Management|"
                                         r"Partners|Securities|Bank|Insurance)\b", s, re.I):
        return None
    if not re.search(r"[A-Za-z一-鿿]", s):
        return None
    if s[0].islower():                          # a mid-sentence fragment
        return None
    if re.fullmatch(r"[\d\s,.%()-]+", s):
        return None
    # every token <=2 latin chars and no CJK ("BA HM") identifies no one
    toks = s.split()
    if toks and all(len(t) <= 2 for t in toks) \
            and not re.search(r"[一-鿿]", s):
        return None
    return s


def clean_investor_list(raw_list, limit=15):
    """Clean, drop the unusable, dedupe case-insensitively, keep order."""
    out, seen = [], set()
    for raw in raw_list or []:
        n = clean_investor(raw)
        if not n:
            continue
        k = re.sub(r"[^a-z0-9一-鿿]", "", n.lower())
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(n)
        if len(out) >= limit:
            break
    return out


# ------------------------------------------------------------- party bleed ---
# The prospectus COVER page bleeds into the parsed bank/party lists four ways:
# the section heading ("DIRECTORS AND PARTIES INVOLVED IN THE GLOBAL OFFERING"),
# page numbers ("– 176 –", "–1 1 0–", "−8 3−" — en/em/minus dashes), role labels
# glued to the next name ("Managers CLSA Limited", "Sole Representative : ..."),
# and the issuer's US address ("New York, NY 10179 United States of America UBS
# AG..."). Each class is exact and mechanical: the real name is recovered where
# it follows the junk, and an element that never contained one is dropped.
_DASH = "[–—−-]"
_P_HEADING = re.compile(
    rf"(?:{_DASH}\s*[\d\s]{{1,9}}{_DASH}\s*)?DIRECTORS\s+AND\s+PARTIES\s+INVOLVED"
    rf"\s+IN\s+THE\s+(?:GLOBAL\s+OFFERING|SHARE\s+OFFER)\s*"
    rf"(?:{_DASH}\s*[\d\s]{{1,9}}{_DASH})?\s*", re.I)
_P_PAGENO = re.compile(rf"\s+{_DASH}\s*\d[\d\s]{{0,7}}{_DASH}\s+")
_P_ADDRESS = re.compile(
    r"^.{0,90}?\bUnited\s+States(?:\s+of\s+America)?[\s,]+(?=\S)", re.I)
# The "Parties Involved" table interleaves each bank with its OFFICE ADDRESS,
# and the parse glued the tail of one entry's address onto the next entry's
# name — 171 syndicate rows shipped as "Central, Hong Kong CLSA Limited" or
# "Wan Chai, Hong Kong Shanxi Securities ...". The cut is anchored on the
# literal ", Hong Kong " (or ", Kowloon ") marker, and fires ONLY when the
# head reads as an address and the tail reads as a company, because two real
# names must survive intact:
#   * "Central China International Capital Limited" — a genuine house (the HK
#     arm of Central China Securities), no marker, never touched;
#   * "Deutsche Bank AG, Hong Kong Branch" — has the marker, but the head
#     ("Deutsche Bank AG") carries no address evidence, so it is kept whole.
# the tail may open lowercase when the brand does — "uSmart Securities" — so a
# camel-case start ([a-z][A-Z]) is accepted alongside a plain capital
_P_HKADDR_MARK = re.compile(r",\s*(?:Hong\s+Kong|Kowloon)\s+(?=[A-Z(]|[a-z][A-Z])")
_P_ADDR_HEAD = re.compile(
    r"\d|\b(?:Road|Street|Avenue|Floor|Tower|Centre|Center|Building|Plaza|"
    r"Place|Square|Estate|House|Central|Admiralty|Wan\s?Chai|Sheung\s+Wan|"
    r"Causeway\s+Bay|Quarry\s+Bay|North\s+Point|Tsim\s+Sha\s+Tsui|Mong\s+Kok|"
    r"Connaught|Queen'?s(?:way)?|Des\s+Voeux|Gloucester|Harcourt|Gardens?)\b", re.I)
_P_CORP_TAIL = re.compile(
    r"\b(?:Limited|Ltd|L\.?L\.?C|Compan(?:y|ies)|Inc|Incorporated|Securities|"
    r"Capital|Bank|Partners|Group|Markets|Corporation|Branch|International|"
    r"Holdings?|Finance)\b", re.I)


def _strip_hk_address(s):
    """Drop a leading office-address fragment glued ahead of a bank name."""
    for m in reversed(list(_P_HKADDR_MARK.finditer(s))):
        head, tail = s[:m.start()], s[m.end():]
        if len(tail) >= 7 and _P_ADDR_HEAD.search(head) and _P_CORP_TAIL.search(tail):
            return tail
    return s
# "Coor dinators" = observed letter-spacing damage on the cover page;
# "Sponsor-Overall Coordinators" = compound role, dashed with -, – or —
# the prospectus "PARTIES INVOLVED" table lists a dozen NON-bank roles whose
# label glues onto the entity ("Compliance Adviser Rainbow Capital (HK)
# Limited", "Receiving Bank Industrial and Commercial Bank of China (Asia)
# Limited") — ANKER's whole sponsor list was that table
_P_ROLE_WORD = (r"(?:Managers?|Coor\s?dinators?|Representatives?|Bookrunners?|"
                r"Sponsors?|Advis[eo]rs?|Capital\s+Market\s+Interm\w*|"
                r"Compliance\s+Advis[eo]rs?|Receiving\s+Banks?|"
                r"Principal\s+Banks?|Legal\s+Advis[eo]rs?|Auditors?|"
                r"Reporting\s+Accountants?|Share\s+Registrars?|Registrars?|"
                r"Industry\s+Consultants?|Property\s+Valuers?)")
_P_ROLE_ADJ = (r"(?:(?:Joint|Sole|Overall|Global|Lead|Co|Senior|and|the|"
               r"Sponsors?)[\s\-–—]+)*")
_P_GLUED = re.compile(
    rf"^{_P_ROLE_ADJ}{_P_ROLE_WORD}\b"
    rf"(?:(?:\s*,\s*|\s+and\s+){_P_ROLE_ADJ}{_P_ROLE_WORD}\b)*\s*:?\s+")
_P_ROLEONLY = re.compile(rf"^{_P_ROLE_ADJ}{_P_ROLE_WORD}\s*:?$", re.I)
# a footnote reference is a pointer, never a name
_P_FOOTREF = re.compile(r"^(?:please\s+refer|see\s+note|refer\s+to|"
                        r"as\s+(?:disclosed|described))\b", re.I)
# the back half of a name whose front a line break ate — identifies no one
_P_ORPHAN = re.compile(
    r"^(?:\(?(?:hong\s+kong|asia|international)\)?\s+)?"
    r"(?:securities|capital|company|international|markets|finance|brokerage|"
    r"group|holdings?)?\s*(?:limited|ltd\.?|llc|l\.l\.c\.?)$", re.I)


def clean_party_element(raw):
    """One parsed bank/party cell -> a clean name, or None if it never was one."""
    s = re.sub(r"\s+", " ", str(raw or "")).strip()
    s = _P_HEADING.sub(" ", s)
    s = _P_ADDRESS.sub("", s)
    s = _strip_hk_address(s)
    s = _P_PAGENO.sub(" ", s)
    # junk punctuation is stripped BEFORE each role pass — "-Overall
    # Coordinator X" must expose the role label to the ^-anchored regex
    s = re.sub(r"\s+", " ", s).strip(" -:,;·—–")
    for _ in range(3):                          # role labels can stack
        s2 = _P_GLUED.sub("", s).strip(" -:,;·—–")
        if s2 == s:
            break
        s = s2
    s = re.sub(r"\s+", " ", s).strip(" -:,;·—–")
    if (len(s) < 4 or _P_FOOTREF.match(s) or _P_ORPHAN.match(s)
            or _P_ROLEONLY.match(s)):
        return None
    return s


def clean_party_list(items):
    """Clean a bank/party list, dedupe case-insensitively, keep order."""
    out, seen = [], set()
    for it in items or []:
        n = clean_party_element(it)
        if not n:
            continue
        k = re.sub(r"[^a-z0-9一-鿿]", "", n.lower())
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(n)
    return out


# ------------------------------------------------------------------ keys ----
# "GIC Private Limited" and "GIC (Ventures) Pte" must MATCH when screening by
# cornerstone similarity, and "UBS Asset Management (Singapore) Limited" must
# match "UBS AG Hong Kong Branch". Raw-substring search cannot do that, so each
# name is reduced to a deterministic KEY: lowercase, legal/generic/geographic
# tail tokens stripped, first two distinctive tokens kept. The key column in the
# Database is derived 1:1 from the visible list — inspectable, never invented.
_KEY_DROP = {
    "limited", "ltd", "ltd.", "inc", "inc.", "llc", "l.l.c", "l.l.c.", "lp",
    "l.p", "l.p.", "plc", "co", "co.", "company", "corp", "corp.", "corporation",
    "holdings", "holding", "group", "fund", "funds", "spc", "master", "sp",
    "management", "asset", "assets", "investment", "investments", "capital",
    "partners", "advisors", "advisers", "securities", "international",
    "hong", "kong", "hk", "singapore", "asia", "asian", "pacific", "china",
    "cayman", "bvi", "global", "worldwide", "branch", "ag", "sa", "pte", "pte.",
    "the", "of", "and", "a", "ii", "iii", "iv", "vi", "vii", "no.1", "no.2",
}


# leads too common to identify anyone on their own — those keep a second token.
# Includes the common Chinese surnames: "Yang Xiaojie" and "Yang Ning" are
# DIFFERENT people and must not fold into one "yang" key (a bare surname key
# also produced false shared-cornerstone matches in the Screener).
_AMBIG = {"mr", "ms", "mrs", "dr", "china", "chinese", "new", "first", "golden",
          "great", "grand", "sino", "east", "eastern", "south", "southern",
          "north", "west", "central", "national", "state", "beijing", "shanghai",
          "shenzhen", "guangzhou", "hangzhou",
          "wang", "li", "zhang", "liu", "chen", "yang", "huang", "zhao", "wu",
          "zhou", "xu", "sun", "ma", "zhu", "hu", "guo", "he", "gao", "lin",
          "luo", "zheng", "liang", "xie", "tang", "song", "deng", "han", "feng",
          "cao", "peng", "zeng", "xiao", "tian", "dong", "pan", "yuan", "cai",
          "jiang", "yu", "du", "ye", "cheng", "wei", "su", "lu", "ding", "ren",
          "shen", "yao", "fang", "jin", "qiu", "xia", "tan", "shi", "qin",
          "bai", "mao", "jia", "gu", "meng", "qian", "wan", "yan", "kong"}


# hand-curated initialism aliases the mechanics cannot safely infer — the
# book itself carries both forms ("MSIP" and "Morgan Stanley & Co.
# International plc"). Append-only; every entry needs that kind of evidence.
_ALIASES = {"msip": "morgan", "cicc": "china-international",
            "gtja": "guotai", "abci": "agricultural", "bocom": "bank-communications"}


def investor_key(name):
    """One investor name -> its distinctive key ('' if nothing survives).

    First distinctive token only ("gic", "taikang", "hillhouse") so that any
    long form of the same house matches by SEARCH in either direction; a second
    token is kept only when the first is too common to identify anyone
    ("china-structural", "mr-gong"). Distinct brands stay distinct — "HHLR" is
    not folded into "Hillhouse"; equating different names would be invention.
    """
    if not name:
        return ""
    s = re.sub(r"\([^)]*\)", " ", str(name))        # drop parentheticals
    s = re.sub(r"[^A-Za-z0-9一-鿿 ]", " ", s).lower()
    toks = [t for t in s.split() if t not in _KEY_DROP and len(t) > 1]
    if not toks:
        # every token is a generic word ("China International Capital
        # Corporation…", "The Capital Group"). ONE token would key that to a
        # bare "china" — generic enough to collide with any other China-named
        # house and to miss its own short form (CICC). Keep two.
        toks = [t for t in s.split() if len(t) > 1][:2]
        return "-".join(toks) if toks else ""
    if not toks:
        return ""
    n_keep = 2 if toks[0] in _AMBIG and len(toks) > 1 else 1
    k = "-".join(toks[:n_keep])
    return _ALIASES.get(k, k)


def investor_keys(names):
    """List of names -> deduped ';'-joined key string for SEARCH()."""
    out = []
    for n in names or []:
        k = investor_key(n)
        if k and k not in out:
            out.append(k)
    return ";".join(out)


# ------------------------------------------------------- canonical display ---
# The same investor reaches us from three places (prospectus tables, prospectus
# prose, AAStocks EN) and spells itself differently in each: casing
# ("HARVEST GLOBAL INVESTMENTS LIMITED"), lost spaces ("(Secondary Market)Fund"),
# truncation ("GIC Private Li"), Chinese conjunctions ("A及B" = two investors in
# one cell). Those are ONE entity and must display as one name.
#
# What is deliberately NOT merged: different vehicles of the same house
# ("CPE Investment XVI Limited" vs "CPE Redwood Investment Limited"), and names
# that merely share a first word ("Huang River Investment Limited" the company
# vs "Huang Guangwei" the person). Collapsing those would invent a fact. They
# still screen together through investor_key(), which is the matching layer.
_SIG_DROP = re.compile(r"\b(limited|ltd|co|company|corp|corporation|inc|llc|lp|"
                       r"l\.?p|plc|pte|spc|sp|sa|ag|nv|bv)\b\.?", re.I)
_CONJ = re.compile(r"\s*(?:及|、|\band\b)\s*", re.I)
_LEGAL_TAIL = re.compile(r"(limited|ltd\.?|inc\.?|llc|l\.?p\.?|plc|pte\.?|spc|"
                         r"co\.?,?\s*ltd\.?|company|corporation|corp\.?)$", re.I)


def name_signature(name):
    """Identity fingerprint: same signature == same entity, spelled differently."""
    s = re.sub(r"[^A-Za-z0-9一-鿿 ]", " ", str(name or "")).lower()
    s = _SIG_DROP.sub(" ", s)
    return re.sub(r"\s+", "", s)


def split_conjunctions(name):
    """'Value Partners HK Limited及Value Partners Limited' -> two investors.

    Only splits when BOTH sides end in a legal suffix, so company names that
    merely contain "and" survive intact.
    """
    parts = [p.strip() for p in _CONJ.split(str(name or "")) if p.strip()]
    if len(parts) > 1 and all(_LEGAL_TAIL.search(p) for p in parts):
        return parts
    return [str(name or "").strip()]


_FOOTNOTE = re.compile(r"\s*(?:\(?\bnotes?\b\s*\d*\)?|\(\d\)|\[\d\])\s*$", re.I)


def _tidy(name):
    """Drop table footnote markers that rode along ('BlackRock Funds Note')."""
    s = re.sub(r"\s+", " ", str(name or "")).strip(" ,;·")
    for _ in range(2):
        s = _FOOTNOTE.sub("", s).strip()
    return s


def build_canonical_map(all_lists):
    """signature -> the spelling to display everywhere.

    Winner = most frequently filed spelling; ties break to the LONGEST, so an
    abbreviation ('GIC Private Li', filed once) yields to the full name ('GIC
    Private Limited', filed 13x) rather than the other way round.
    """
    import collections
    counts = collections.defaultdict(collections.Counter)
    for names in all_lists:
        for n in names or []:
            for part in split_conjunctions(n):
                part = _tidy(part)
                sig = name_signature(part)
                if sig and part:
                    counts[sig][part] += 1

    def best(counter):
        return max(counter.items(), key=lambda kv: (kv[1], len(kv[0])))[0]

    # absorb truncations FIRST (a truncated spelling makes a LONGER signature:
    # 'gicprivateli' vs 'gicprivate', because 'limited' is a dropped legal word)
    sigs = sorted(counts, key=len)
    merged = {}
    for i, a in enumerate(sigs):
        if a in merged or len(a) < 10:
            continue
        for b in sigs[i + 1:]:
            if b in merged or len(b) - len(a) > 6 or not b.startswith(a):
                continue
            if re.search(r"\d|\bii\b|\biii\b", b[len(a):]):
                continue
            merged[b] = a                       # b is the truncation of a
            counts[a].update(counts[b])
            break
    canon = {sig: best(c) for sig, c in counts.items() if sig not in merged}
    for trunc, full in merged.items():
        canon[trunc] = canon.get(full, best(counts[full]))
    return canon


def canonical_list(names, canon):
    """Apply the map, split conjunctions, drop within-deal duplicates."""
    out, seen = [], set()
    for n in names or []:
        for part in split_conjunctions(n):
            part = _tidy(part)
            sig = name_signature(part)
            if not sig or sig in seen:
                continue
            seen.add(sig)
            disp = canon.get(sig, part)
            # two signatures can resolve to the SAME display name (a truncation
            # and its full form inside one list) — dedupe on what is shown
            if disp not in out:
                out.append(disp)
    # WITHIN one deal, a name whose signature is a prefix of another entry's
    # signature is the same investor read twice ("RIME" + "RIME Capital
    # Limited", "Factorial" + "Factorial Master Fund", "HHLRA" + "HHLR
    # Advisors"). Across deals that inference is unsafe; inside one list the
    # short form is a truncation — keep the fuller spelling only.
    sigs = {d: name_signature(d) for d in out}
    folded = []
    for d in out:
        a = sigs[d]
        dup = any(d2 != d and len(a) >= 4 and len(sigs[d2]) > len(a)
                  and sigs[d2].startswith(a) for d2 in out)
        if not dup:
            folded.append(d)
    return folded


# ------------------------------------------------------------- league -------
def cs_league(deals):
    """AAStocks-style cornerstone league: per INVESTOR (grouped on the same
    normalized key the screener matches with), every deal they anchored and
    the average day-1 pop / 1w / 1m / 3m ex-pop across those deals.

    Pure aggregation of visible fields — computed once here so the Excel
    sheet and the HTML tab can never disagree.
    """
    import collections
    # cross-spelling fold: "hhlra"->"hhlr", "schroders"->"schroder",
    # "southern-am"->"southern". Only where the shorter key is >=4 chars and
    # the extra is <=1 char OR one whole generic token — "al" vs "all"
    # (Al-Rayyan vs All View) are DIFFERENT companies and must not fold.
    _GEN_TOK = {"am", "amc", "hk", "asia", "intl", "sg", "international"}
    all_keys = sorted({k for x in deals
                       for k in map(investor_key,
                                    x.get("cornerstone_investors") or []) if k})
    remap = {}
    for i, a in enumerate(all_keys):
        if a in remap or len(a) < 4:
            continue
        for b in all_keys[i + 1:]:
            if not b.startswith(a):
                break
            if b in remap or a == b:
                continue
            extra = b[len(a):]
            if len(extra) <= 1 or (extra.startswith("-")
                                   and extra[1:] in _GEN_TOK):
                remap[b] = a

    groups = collections.defaultdict(lambda: {"names": collections.Counter(),
                                              "deals": []})
    for x in deals:
        seen_keys = set()               # two spellings of one investor inside
        for nm in (x.get("cornerstone_investors") or []):   # ONE deal count once
            k = investor_key(nm)
            k = remap.get(k, k)
            if not k or k in seen_keys:
                continue
            seen_keys.add(k)
            g = groups[k]
            g["names"][nm] += 1
            g["deals"].append({
                "code": x.get("code"), "name": x.get("name"),
                "ipo_date": x.get("ipo_date"),
                "d1": x.get("first_day_return_pct"),
                # ex-pop legs (from the day-1 close)
                "w1": x.get("aftermkt_1w_pct"),
                "m1": x.get("aftermkt_1m_pct"),
                "m3": x.get("aftermkt_3m_pct"),
                # with-pop legs (vs the offer price — what a cornerstone,
                # who is allotted AT the offer, actually earns)
                "w1p": x.get("ret_1w_pct"),
                "m1p": x.get("ret_1m_pct"),
                "m3p": x.get("ret_3m_pct"),
            })

    def avg(vals):
        vs = [v for v in vals if v is not None]
        return round(sum(vs) / len(vs), 1) if vs else None

    out = []
    for k, g in groups.items():
        ds = g["deals"]
        d1s = [d["d1"] for d in ds if d["d1"] is not None]
        out.append({
            "key": k,
            "investor": g["names"].most_common(1)[0][0],
            "n": len(ds),
            "hit": round(100 * sum(1 for v in d1s if v > 0) / len(d1s), 0)
                   if d1s else None,
            "avg_d1": avg(d["d1"] for d in ds),
            "avg_1w": avg(d["w1"] for d in ds),
            "avg_1m": avg(d["m1"] for d in ds),
            "avg_3m": avg(d["m3"] for d in ds),
            "avg_1w_pop": avg(d["w1p"] for d in ds),
            "avg_1m_pop": avg(d["m1p"] for d in ds),
            "avg_3m_pop": avg(d["m3p"] for d in ds),
            "deals": ds,
        })
    out.sort(key=lambda r: (-r["n"], -(r["avg_d1"] if r["avg_d1"] is not None
                                       else -1e9)))
    return out


if __name__ == "__main__":                      # quick self-check
    cases = [("allotment Option) Top", None), ("Option) Top1", None), ("Top 10", None),
             ("Y anlord Investment", "Yanlord Investment"),
             ('CLSA Limited ( “CLSA”)', "CLSA Limited"),
             ("The Placee group holds A Shares", None),
             ("Dymon Asia Capital (Singapore) Pte. Ltd", "Dymon Asia Capital (Singapore) Pte. Ltd"),
             ("The Capital Group Funds", "The Capital Group Funds"),
             ("(approximate) (approximate) Neptune", "Neptune"),
             ("Hillhouse Capital", "Hillhouse Capital")]
    bad = 0
    for raw, want in cases:
        got = clean_investor(raw)
        ok = "ok " if got == want else "FAIL"
        bad += got != want
        print(f"  {ok} {raw!r:52s} -> {got!r}")
    print(f"{len(cases)-bad}/{len(cases)} pass")


def stab_league(deals):
    """Stabilising-manager league — the sibling of cs_league(), same shape.

    A cornerstone is allotted AT the offer and locked up; the stabilising
    manager is the bank holding the greenshoe and the after-market bid. So the
    two leagues answer different questions: who anchored the deal, versus who
    defended it once it traded. The extra column here is the shoe outcome —
    a manager who exercises in full never had to support the price, and one
    whose option lapsed was buying stock to hold the line.

    Pure aggregation of visible fields, computed once so the Excel sheet and
    the HTML tab cannot disagree.
    """
    import collections

    groups = collections.defaultdict(lambda: {"names": collections.Counter(),
                                              "deals": []})
    for x in deals:
        nm = x.get("stabilizing_manager")
        k = x.get("stabilizing_manager_key") or nm
        if not nm or not k:
            continue
        g = groups[k]
        g["names"][nm] += 1
        g["deals"].append({
            "code": x.get("code"), "name": x.get("name"),
            "ipo_date": x.get("ipo_date"),
            "d1": x.get("first_day_return_pct"),
            # the day-1 session split into its two legs. For a STABILISER this
            # is the whole question: "pop" is where the stock opened against
            # the price it was sold at, and open->close is whether the bank
            # held that level or let it fade. A manager can show a fine close
            # having bought stock all day, or a fine open it gave straight back.
            "d1o": x.get("day1_open_pop_pct"),
            "d1oc": x.get("day1_open_close_pct"),
            # ex-pop legs (from the day-1 close) — what the after-market did
            "w1": x.get("aftermkt_1w_pct"),
            "m1": x.get("aftermkt_1m_pct"),
            "m3": x.get("aftermkt_3m_pct"),
            # with-pop legs (vs the offer price)
            "w1p": x.get("ret_1w_pct"),
            "m1p": x.get("ret_1m_pct"),
            "m3p": x.get("ret_3m_pct"),
            "shoe": x.get("greenshoe_exercised_final"),
            "size": x.get("deal_size_hkdm"),
        })

    def avg(vals):
        vs = [v for v in vals if v is not None]
        return round(sum(vs) / len(vs), 1) if vs else None

    out = []
    for k, g in groups.items():
        ds = g["deals"]
        d1s = [d["d1"] for d in ds if d["d1"] is not None]
        shoes = [str(d["shoe"]).lower() for d in ds if d.get("shoe")]
        full = sum(1 for s in shoes if "full" in s or s == "exercised")
        lapsed = sum(1 for s in shoes if "laps" in s or "not exercised" in s)
        sizes = [d["size"] for d in ds if d.get("size")]
        out.append({
            "key": k,
            "manager": g["names"].most_common(1)[0][0],
            "n": len(ds),
            "hit": round(100 * sum(1 for v in d1s if v > 0) / len(d1s), 0)
                   if d1s else None,
            "avg_d1": avg(d["d1"] for d in ds),
            "avg_1w": avg(d["w1"] for d in ds),
            "avg_1m": avg(d["m1"] for d in ds),
            "avg_3m": avg(d["m3"] for d in ds),
            "avg_1w_pop": avg(d["w1p"] for d in ds),
            "avg_1m_pop": avg(d["m1p"] for d in ds),
            "avg_3m_pop": avg(d["m3p"] for d in ds),
            # day-1 legs: open vs issue (the pop), close vs issue (the return,
            # which is avg_d1 above), and open->close (held or faded)
            "avg_d1_open": avg(d["d1o"] for d in ds),
            "avg_d1_open_close": avg(d["d1oc"] for d in ds),
            "d1_open_known": sum(1 for d in ds if d["d1o"] is not None),
            # the stabilisation-specific dimension
            "shoe_known": len(shoes),
            "shoe_full_pct": round(100 * full / len(shoes), 0) if shoes else None,
            "shoe_lapsed_pct": round(100 * lapsed / len(shoes), 0) if shoes else None,
            "avg_size": round(sum(sizes) / len(sizes), 1) if sizes else None,
            "deals": ds,
        })
    out.sort(key=lambda r: (-r["n"], -(r["avg_d1"] if r["avg_d1"] is not None
                                       else -1e9)))
    return out
