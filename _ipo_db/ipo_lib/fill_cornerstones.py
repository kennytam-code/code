#!/usr/bin/env python3
"""Cornerstone % and names for every deal, read from the filings' own tables.

Three readings, best first:

1. The ALLOTMENT RESULTS table (format since 2023): "Cornerstone Investors /
   Investor / No. of Offer Shares allocated / % of Offer Shares ..." — one row
   per investor and a "Total 23,891,700 44.38% 5.52%" line. It is at the
   FINAL price and after any upsize, so it is the figure of record.
2. The PROSPECTUS: a complete prospectus (> 500k characters of text) that
   mentions a cornerstone section no more than four times has none — the
   phrase recurs dozens of times wherever a cornerstone placing exists (in the
   summary, the structure, the section itself, the lock-up and the risk
   factors). That deal's answer is 0%, "no cornerstone tranche".
3. AAStocks' deal page (機構性投資者): clean names and amounts; % = the
   committed total over the deal size.

Why this exists: the older allotment parser read the "Top 1 / Top 5 / Top 25
placees" CONCENTRATION table as if it were the cornerstone table — "names"
like "are issued) Top" and "Subtotal", and a "cornerstone %" that was really
the largest placee's share (KCASH 2483: 24.7%, 方舟健客 6086: 28.6%, both of
which had no cornerstone investors at all).

Writes data/cornerstone_fill.json (tracked: each value carries its evidence).
merge_batches.py reads it at priority 65 — above every machine parse, below
hand-verified press (70).

usage:
    python ipo_lib/fill_cornerstones.py            # every deal
    python ipo_lib/fill_cornerstones.py 6168 2410  # named deals
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_deep as X          # noqa: E402  (read_cached, HDR_CORNER)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "cornerstone_fill.json"

HDR_TABLE = re.compile(r"Cornerstone\s+Investors?\s*\n\s*(?:Name\s+of\s+|Cornerstone\s+)?Investor\b", re.I)
# the lock-up table lists every cornerstone with the shares it holds; some
# notices (臥安 6600) print the cornerstones ONLY there
HDR_LOCKUP = re.compile(r"Cornerstone\s+Investors?\s*\n\s*Name\s*(?:\([^)]*\))?\s*\n", re.I)
PCT = r"(\d{1,2}(?:\.\d+)?)%?"
NUMB = r"(\d{1,3}(?:,\d{3})+|\d{4,})(?![\d,])"
ROW = re.compile(r"^(.*?)\s*" + NUMB + r"\s*(?:Note\s*\d+\s*)?" + PCT + r"(?:\s+" + PCT + r")?(?:\s|$)")
ROW_LOCK = re.compile(r"^(.*?)\s*" + NUMB + r"\s+(?:(?:\d{1,3}(?:,\d{3})+|\d{4,}|[—–-])\s+)?" + PCT + r"\s")
TOTAL = re.compile(r"^\s*(?:Sub-?total|Total)\s+" + NUMB, re.I)
END = re.compile(r"^(?:Notes?:|Allotees|Placees|Pre-IPO|Controlling|Existing\s+Shareholders?\s+subject|"
                 r"Other\s+placees|Allottees?\s+with\s+(?:Waivers|Consents?|consent)|Lock-up|\d+\.\s)", re.I)
HEADER_WORD = re.compile(r"^(?:No\.|Number|Shares|allocated|Allocated|%|of |Offer|total|issued|capital|"
                         r"after|the Global|Offering|Existing|shareholders|or their|associates|Note|"
                         r"held|in the|Company|subject|to lock|undertakings|upon|listing|Listing|"
                         r"Last day|\(assuming|Over-|allotment|Option|exercised|Approximate|H Shares|"
                         r"Name$|Investor$|shareholding|Relationship)", re.I)
JUNK = re.compile(r"^[\d\s,.%]+$|\bTop\b|Subtotal|are issued\)|upon Listing|^Investor$|^No\. of|"
                  r"Offer\s+Shares|issued share|^Existing|shareholders|associates|^Note\s*\d", re.I)


def clean_name(s):
    s = re.sub(r"\s+", " ", s).strip(" /,;")
    s = re.sub(r"^(?:\(Note\s*\d+\)\s*)+", "", s)
    s = re.sub(r"[–—-]\s*\d{1,3}\s*[–—-]\s*", " ", s)                # page marker "– 5 –"              # "(Note 1) Hong Kong Chuangli…"
    # "Yongcheng No. 2 Hong Kong Limited/࠰ʮ̡" — the Chinese twin after the
    # slash is a garbled font dump; keep the English name
    if "/" in s:
        head, tail = s.split("/", 1)
        if re.search(r"[^\x00-\x7f]", tail) or not re.search(r"[A-Za-z]{3}", tail):
            s = head
    s = re.sub(r"\(\s*[“\"][^)]*[”\"]\s*\)", "", s)          # ( “HongShan Growth” ) alias
    s = re.sub(r"\([^)A-Za-z]*[^\x00-\x7f][^)]*\)", "", s)    # garbled (…) groups
    s = re.sub(r"\s*Note\s*\d+$", "", s)
    s = re.sub(r"\s*\(\d\)$", "", s)                            # trailing footnote "(4)"
    return re.sub(r"\s+", " ", s).strip(" /,;—-")


HEADERISH = re.compile(r"(?:associates?\*?|Relationship|exercised\)|listing|Listing|"
                       r"allocated|Allocated|Offer\s*Shares|share\s+capital|the\s+Company|Global|"
                       r"Offering|undertakings|lock-\s?up|Approximate|Investor|Name|%)\s*(?:\(\d\))?$|"
                       r"^(?:Note\s*\d[\s&\d]*$|No\.|Number|%|of\s|Existing|shareholders|or\s+their|held\s|in\s+the|"
                       r"subject|to\s+lock|upon|Last\s+day|\(assuming|Over-|allotment|Option)", re.I)


REPEAT_HDR = re.compile(r"^(?:No\.\s+of|%\s+of|Investor$|Existing$|Name$|Number\s+of)", re.I)


def _read_table(block, row_re):
    """(rows, total_pcts, header). Each row = (name, shares, [pcts]). A
    "Subtotal" (one per investor group) is skipped; only the final "Total"
    ends the table. A row's name is the lines between the previous row and
    this one — after the header's last line when a header precedes it."""
    lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
    hits, total, first, subtotals = [], None, None, []
    for k, s in enumerate(lines):
        t = TOTAL.match(s)
        if t:
            tail = s[t.end(1):]
            if not re.search(r"\d", tail) and k + 1 < len(lines):
                tail = lines[k + 1]                 # "Subtotal 11,150,000" / "26.76% 4.18%"
            vals = [float(x) for x in re.findall(r"(\d{1,3}(?:\.\d+)?)%?", tail)][:3]
            if re.match(r"\s*Sub-?total", s, re.I):
                subtotals.append(vals)
                continue
            total = vals
            break
        if hits and END.match(s):
            break
        r = row_re.match(s)
        if r:
            hits.append((k, r))
            first = k if first is None else first
    rows, prev = [], None
    for k, r in hits:
        lo = 0 if prev is None else prev + 1
        seg = lines[lo:k]
        if prev is None or any(REPEAT_HDR.match(x) for x in seg):
            start = k
            while start > lo and k - start < 16 and not HEADERISH.search(lines[start - 1]):
                start -= 1
        else:
            start = lo
        prev = k
        nm = clean_name(" ".join(lines[start:k] + [r.group(1)]))
        if nm and not JUNK.search(nm) and len(nm) > 2 and not re.match(r"Sub-?total", nm, re.I):
            rows.append((nm, int(r.group(2).replace(",", "")), [float(g) for g in r.groups()[2:] if g is not None]))
    header = " ".join(lines[:first]) if first is not None else ""
    if total is None and len(subtotals) == 1:
        total = subtotals[0]                        # one group: its subtotal IS the total
    return rows, total, header


def offer_col(header):
    """Index (0/1) of the "% of (Total) Offer Shares" column, or None when the
    table has none (A+H tables print "% of total issued H Shares" instead)."""
    segs = header.split("%")[1:3]
    for k, seg in enumerate(segs):
        seg = seg[:90]
        if re.search(r"of\s+(?:the\s+)?(?:Total\s+)?(?:number\s+of\s+)?Offer\s+Shares", seg, re.I) \
                and not re.search(r"issued", seg[:40], re.I):
            return k
    return None


def allotment_table(txt, offer_shares=None):
    """{pct, names, basis} from the allotment notice's cornerstone table.
    With a "% of Offer Shares" column: the final Total in it, else the sum of
    the rows. Without one: cornerstone shares over the offer shares."""
    for hdr, row_re in ((HDR_TABLE, ROW), (HDR_LOCKUP, ROW_LOCK)):
        for m in hdr.finditer(txt):
            rows, total, header = _read_table(txt[m.end():m.end() + 9000], row_re)
            if not rows:
                continue
            names = [r[0] for r in rows]
            col = offer_col(header) if hdr is HDR_TABLE else None
            kind = "lockup" if hdr is HDR_LOCKUP else None
            if col is not None and total and len(total) > col:
                pct, basis, kind = total[col], "the table's printed total, % of offer shares", "printed"
            elif col is not None and all(len(r[2]) > col for r in rows):
                pct, basis = round(sum(r[2][col] for r in rows), 2), "sum of the rows, % of offer shares"
                kind = kind or "sum"
            elif offer_shares:
                pct = round(100 * sum(r[1] for r in rows) / offer_shares, 2)
                basis = "cornerstone shares over the offer shares (table has no % of offer column)"
                kind = kind or "shares"
            else:
                continue
            # a cornerstone tranche under 1% of the offer is a misread row,
            # not a tranche (沃爾核材 once read 0.01% from lock-up dates)
            if 0 < pct <= 100:
                return {"pct": pct, "names": names, "basis": basis, "kind": kind,
                        "shares": sum(r[1] for r in rows), "rows": rows}
    return None


def main(argv):
    deals = {d["code"]: d for d in json.loads((ROOT / "data" / "deals.json").read_text())["deals"]}
    links = {e["code"]: e for e in json.loads((ROOT / "data" / "batches" /
                                                "hkex_prospectus_links.json").read_text())["deals"]}
    allot = {e["code"]: e for e in json.loads((ROOT / "data" / "batches" /
                                                "hkex_allotment_files.json").read_text())["manifest"]}
    want = [a.zfill(4) for a in argv if a[:1].isdigit()] or sorted(deals)

    def text(m, c):
        return "\n".join(X.read_cached(p["file"] if isinstance(p, dict) else p)
                         for p in (m.get(c, {}).get("parts") or []))

    out = []
    for c in want:
        d = deals.get(c)
        if not d:
            continue
        rec = {"code": c}
        at = text(allot, c)
        tab = allotment_table(at, d.get("offer_shares")) if at else None
        aa_n = len(d.get("cornerstone_aa") or [])
        if tab and tab["kind"] != "printed" and aa_n > len(tab["names"]):
            # a COMPUTED % from a table that found fewer investors than
            # AAStocks lists has missed a row: it would read low (華沿 8 of 9)
            tab = None
        if tab:
            rec.update(cornerstone_pct=tab["pct"], cornerstone_investors=tab["names"],
                       basis_kind=tab["kind"],
                       src=f"HKEX allotment results: cornerstone table ({tab['basis']})")
        else:
            # the prospectus is 1-2 MB of text per deal (and iCloud-evicted):
            # read it only where the book still lacks a trustworthy answer
            psrc = str(((d.get("_prov") or {}).get("cornerstone_pct") or {}).get("src", ""))
            # a value this module wrote last time is re-derived, never trusted
            # as "already answered" (deleting the fill file must not lose it)
            mine = psrc.startswith("filing:")
            if not mine and ((d.get("cornerstone_pct") is not None and d.get("cornerstone_investors")
                              and "deep(allotment)" not in psrc) or d.get("cornerstone_pct") == 0):
                continue
            pt = text(links, c)
            n_hdr = len(X.HDR_CORNER.findall(pt))
            # boilerplate that names the WORD but no investor: "…may
            # participate in Hong Kong IPOs either as placees or cornerstone
            # investors (the "Cross-border Derivatives Trading Regime")"
            at_real = re.sub(r"placees\s+or\s+cornerstone\s+investors", " ", at, flags=re.I)
            at_mentions = len(re.findall(r"cornerstone", at_real, re.I))
            aa = [x.get("name") for x in (d.get("cornerstone_aa") or []) if x.get("name")]
            if len(pt) > 500_000 and n_hdr <= 4 and not aa and at_mentions <= 2:
                rec.update(cornerstone_pct=0, cornerstone_none=True,
                           src=f"prospectus ({len(pt) // 1000}k chars) has no cornerstone section "
                               f"({n_hdr} passing mention{'s' if n_hdr != 1 else ''}); allotment names none")
            elif aa:
                rec["cornerstone_investors"] = aa
                tot, size = d.get("cornerstone_aa_total_hkdm"), d.get("deal_size_hkdm")
                if tot and size and d.get("cornerstone_pct") in (None, 0):
                    rec["cornerstone_pct"] = round(min(100.0, 100 * tot / size), 1)
                rec["src"] = "AAStocks deal page (機構性投資者)"
            elif len(pt) < 200_000 and at and len(at) > 15000 and at_mentions == 0 and not aa:
                # no real prospectus on file (none found, or only an application
                # form), but a complete allotment notice that names no
                # cornerstone investor: none was placed
                # no prospectus text on file, but a complete allotment notice
                # that never mentions a cornerstone: none was placed
                rec.update(cornerstone_pct=0, cornerstone_none=True,
                           src=f"allotment results ({len(at) // 1000}k chars) name no cornerstone investor")
            else:
                continue
        out.append(rec)
    prev = {}
    if OUT.exists() and argv:
        prev = {r["code"]: r for r in json.loads(OUT.read_text()).get("deals", [])}
    for r in out:
        prev[r["code"]] = r
    OUT.write_text(json.dumps({"note": "cornerstone % and names read from the filings' own tables; "
                                       "see ipo_lib/fill_cornerstones.py",
                               "deals": sorted(prev.values(), key=lambda r: r["code"])},
                              ensure_ascii=False, indent=1))
    n_tab = sum(1 for r in prev.values() if "allotment results: cornerstone table" in r.get("src", ""))
    n_none = sum(1 for r in prev.values() if r.get("cornerstone_none"))
    print(f"cornerstone fill: {len(prev)} deals — {n_tab} from the allotment table, "
          f"{n_none} with no cornerstone tranche, {len(prev) - n_tab - n_none} from AAStocks")


if __name__ == "__main__":
    main(sys.argv[1:])
