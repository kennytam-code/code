#!/usr/bin/env python3
"""Extract the pre-IPO revenue / net-profit series from prospectus summary tables.

HK prospectus summaries print a 3-financial-year track record (plus interim stub
periods) as: <label> <FY1> <pct> <FY2> <pct> <FY3> <pct> [<stub> <pct> <stub>].
Values arrive with dot-leader artifacts (/H1118) that are stripped first.

Percentage columns are dropped by shape (<=100.0 with exactly one decimal,
immediately following a magnitude value). The LAST full-year column is taken as
the latest pre-IPO FY; interim stubs after it are recorded separately but never
used as the FY figure. Currency is read from the nearest thousands marker
(RMB'000 / HK$'000 / US$'000); if absent the record is emitted with
currency=null and no HKD conversion, rather than assuming.

Everything here is heuristic column-reading, so each output carries the raw
source line for eyeballing and merges with status "estimated".
"""
import json, re, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scrape" / "pdf_cache"
TEXT = ROOT / "scrape" / "text_cache"
LINKS = ROOT / "data" / "batches" / "hkex_prospectus_links.json"
OUT = ROOT / "data" / "batches" / "extracted_financials.json"

FX = {"RMB": 1.10, "HK$": 1.0, "US$": 7.80}     # to HKD; deal-era approximations
# NOTE: /H1118 is a fixed-width PDF glyph code. A greedy /H\d+ would swallow the
# leading digits of the number that follows it (10,350,986 -> 350,986).
LEADER = re.compile(r"(?:/H\d{4}|\.{3,}|·{3,}|…+)")
NUMTOK = re.compile(r"\(?-?[\d,]+(?:\.\d+)?\)?")
CUR = re.compile(r"(RMB|HK\$|US\$)\s*[^\w\s]?\s*000|(RMB|HK\$|US\$)\s+in\s+thousands", re.I)
REV_LINE = re.compile(r"^\s*(?:Total\s+)?Revenues?(?:\s+from\s+contracts\s+with\s+customers)?(?:\s+and\s+other\s+income)?\s*[^A-Za-z\n]{0,60}?(?=[\d(])", re.M)
NI_LINE = re.compile(
    r"^\s*(?:Net\s+(?:profit|loss)|Profit|Loss|\(Loss\)/profit|Profit/\(loss\))"
    r"(?:\s+and\s+total\s+comprehensive\s+income)?"
    r"(?:\s+for\s+the\s+(?:year|year/period|period))?"
    r"(?:\s+attributable\s+to[\w\s\-']{0,40})?\s*[^A-Za-z\n]{0,60}?(?=[\d(])", re.M)


def tonum(tok):
    neg = tok.startswith("(") and tok.endswith(")")
    v = tok.strip("()").replace(",", "")
    try:
        v = float(v)
    except ValueError:
        return None
    return -v if neg else v


FOOTNOTE = re.compile(r"^\(\d\)$")


def value_columns(tail):
    """Split a table row's numbers into magnitude columns, dropping % columns."""
    toks = NUMTOK.findall(tail)
    # "Net profit (RMB in millions) (3) 135.6 154.8 170.5" — the (3) is a
    # FOOTNOTE MARKER, not minus three. Left in, it shifts every column right and
    # the "latest FY" index lands on the prior year.
    while toks and FOOTNOTE.match(toks[0].strip()):
        toks = toks[1:]
    vals, prev_big = [], False
    for t in toks:
        v = tonum(t)
        if v is None:
            continue
        is_pct = prev_big and abs(v) <= 100.0 and re.fullmatch(r"-?\d{1,3}\.\d", t.strip("()"))
        if is_pct:
            prev_big = False
            continue
        vals.append(v)
        prev_big = abs(v) >= 1000
    return vals


# flat-text fallback: some filings render the summary table without clean line
# starts ("(Loss)/profit for the year — — — — (1,042,781) ..."), so the ^-anchored
# patterns never fire. Scan the whitespace-flattened text and accept the first
# label occurrence that is actually FOLLOWED by figures (>=2 big numbers close by),
# which prose mentions never are.
FLAT_LABELS_NI = [
    r"\(Loss\)/profit for the (?:year|period)", r"Profit/\(loss\) for the (?:year|period)",
    r"Profit and total comprehensive income for the (?:year|period)",
    r"Profit for the (?:year|period)", r"Loss for the (?:year|period)",
    r"Net profit", r"Net loss",
]
FLAT_LABELS_REV = [r"Total revenues?", r"Revenues?(?: from contracts with customers)?"]


def series_from_flat(flat, labels):
    for lab in labels:
        for m in re.finditer(lab, flat, re.I):
            tail = flat[m.end():m.end() + 200]
            vals = value_columns(tail.replace("\u2014", " "))
            if looks_like_years(vals):
                continue
            big = [v for v in vals if abs(v) >= 1000]
            if len(big) >= 2:
                neg = bool(re.match(r"\s*loss", lab, re.I)) or "(" in tail[:40]
                return (vals, re.sub(r"\s+", " ", flat[m.start():m.end() + 160])[:220],
                        flat[max(0, m.start() - 700):m.start()])
    return None, None, None


YEARISH = re.compile(r"^(19[89]\d|20[0-3]\d)$")


def looks_like_years(vals):
    """A 'Revenue' label sitting directly above the table's YEAR header row makes
    the parser return [2017, 2018, 2019] as if it were money.

    Any series that is mostly bare four-digit years in the calendar range is a
    header row, not a financial one — a real revenue line that happened to read
    2,019 would carry a thousands separator and other magnitudes beside it.
    """
    ok = [v for v in vals if v is not None]
    if not ok:
        return False
    yr = sum(1 for v in ok if v == int(v) and YEARISH.match(str(int(v))))
    return yr * 2 >= len(ok)


# "RMB in millions" / "HK$ million" printed beside the row means the figures are
# ALREADY in millions; the default thousands assumption would divide them again
# and turn RMB632.7m of revenue into RMB0.6m.
MILLIONS_CX = re.compile(r"(?:RMB|HK\$|US\$|\$)?\s*(?:in\s+)?millions?\b", re.I)
THOUSANDS_CX = re.compile(r"(?:RMB|HK\$|US\$|\$)\s*[\u2019']000|in\s+thousands", re.I)


# A comma-grouped INTEGER (1,346,214) is a thousands-denominated figure. A
# comma-grouped number carrying a decimal (4,816.4) is a millions figure that
# merely crossed a thousand, so the trailing "." must not count as grouping.
GROUPED = re.compile(r"\d,\d{3}(?:,\d{3})*(?![\d.])")


def unit_of(raw, lead=None, vals=None):
    """'millions' | 'thousands' | None, read from the row and its table header.

    The row's own TYPOGRAPHY decides first and is never wrong: a comma-grouped
    integer (1,346,214) is a thousands-denominated figure, while a millions
    table prints short decimals (632.7). Prose about "millions" elsewhere on the
    page cannot outrank that — a lead-window match alone rescaled two issuers by
    1,000x in the wrong direction.

    Only when the row is unpunctuated does the printed unit marker decide, taken
    from the row itself and then from the COLUMN HEADER just above it.
    """
    # Magnitude first: a figure of 100,000+ in a MILLIONS table would be
    # RMB100bn on one line, and issuers of that size print in thousands anyway.
    if vals and max((abs(v) for v in vals if v is not None), default=0) >= 100_000:
        return "thousands"
    # Then typography, but only across the row's OWN numeric run — scanning the
    # whole 220-char snippet caught a comma-grouped figure from a later column
    # and pushed a genuine millions table (Tianqi) back to thousands.
    if raw and GROUPED.search(raw[:110]):
        return "thousands"
    for scope in (raw, lead):
        if not scope:
            continue
        t = THOUSANDS_CX.search(scope)
        m = MILLIONS_CX.search(scope)
        if t and m:
            return "thousands" if t.start() > m.start() else "millions"
        if t:
            return "thousands"
        if m:
            return "millions"
    return None


def series_from(txt, line_re):
    """txt must already be leader-stripped (see clean_text).

    Scans every label occurrence rather than only the first: in a prospectus the
    word "revenue" appears in narrative prose long before the summary table, and
    the prose match yields page numbers and dates ("30, 2020, 30, 2019").
    """
    for m in line_re.finditer(txt):
        tail = txt[m.end():m.end() + 260].split("\n")[0]
        vals = value_columns(tail)
        if not vals or looks_like_years(vals):
            continue
        raw = re.sub(r"\s+", " ", txt[m.start():m.end() + 160])[:220]
        lead = re.sub(r"\s+", " ", txt[max(0, m.start() - 700):m.start()])
        return vals, raw, lead
    return None, None, None


def clean_text(txt):
    """Remove dot-leader artifacts ('/H1118', '....') that sit between a row label
    and its figures — they contain letters, so they block label matching."""
    return LEADER.sub(" ", txt)


def currency_of(txt):
    """Reporting currency = the most frequent thousands marker in the document."""
    hits = [(a or b).upper() for a, b in CUR.findall(txt)]
    if not hits:
        return None
    return Counter(hits).most_common(1)[0][0]


def main():
    links = json.loads(LINKS.read_text())["deals"]
    recs, hits = [], 0
    for i, e in enumerate(links):
        parts = e.get("parts") or []
        files = [CACHE / p["file"] for p in parts if (CACHE / p["file"]).exists()]
        if not files:
            continue
        # Use the cached FULL text of every part. v2 read 45 pages of a single
        # part, so any filing whose financial summary sat elsewhere (or deeper)
        # was missed entirely — that capped revenue/profit at 62%.
        chunks = []
        for p_ in parts:
            t = TEXT / (p_["file"] + ".txt")
            if t.exists():
                chunks.append(t.read_text(errors="ignore"))
        if not chunks:
            continue
        src = files[0]
        txt = clean_text("\n".join(chunks))
        rev, rev_raw, rev_lead = series_from(txt, REV_LINE)
        ni, ni_raw, ni_lead = series_from(txt, NI_LINE)
        if not rev or not ni:
            flat = re.sub(r"\s+", " ", txt)
            if not ni:
                ni, ni_raw, ni_lead = series_from_flat(flat, FLAT_LABELS_NI)
            if not rev:
                rev, rev_raw, rev_lead = series_from_flat(flat, FLAT_LABELS_REV)
        if not rev and not ni:
            continue
        cur = currency_of(txt)
        rec = {"code": e["code"], "currency": cur, "unit": "thousands",
               "rev_series": rev, "ni_series": ni,
               "rev_raw": rev_raw, "ni_raw": ni_raw, "src_file": src.name}
        # per-row unit, read from the row's own header rather than assumed
        rec["rev_unit"] = unit_of(rev_raw, rev_lead, rev) or "thousands"
        rec["ni_unit"] = unit_of(ni_raw, ni_lead, ni) or "thousands"
        # latest full financial year = 3rd column when a 3-year record is shown
        # accept only the usual track-record shapes (3 FY, +/- interim stubs);
        # anything else means the row was mis-split, so keep raw only
        for key, series in (("rev", rev), ("ni", ni)):
            if series and len(series) <= 6:
                idx = 2 if len(series) >= 3 else len(series) - 1
                v = series[idx]
                rec[f"{key}_latest_native_k"] = v
                if cur:
                    # thousands -> HK$m divides by 1000; a table already printed
                    # in millions is only FX-converted
                    div = 1 if rec[f"{key}_unit"] == "millions" else 1000
                    rec[f"{key}_latest"] = round(v * FX[cur] / div, 1)   # -> HK$m
                rec[f"{key}_fy_index"] = idx
        recs.append(rec)
        hits += 1
        if (i + 1) % 50 == 0:
            print(f"{i+1}/{len(links)} scanned, {hits} with financials", flush=True)
    OUT.write_text(json.dumps(
        {"batch": "extracted_financials",
         "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(recs),
         "with_rev": sum(1 for r in recs if r.get("rev_latest") is not None),
         "with_ni": sum(1 for r in recs if r.get("ni_latest") is not None),
         "deals": recs}, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {len(recs)} deals, "
          f"{sum(1 for r in recs if r.get('rev_latest') is not None)} with revenue, "
          f"{sum(1 for r in recs if r.get('ni_latest') is not None)} with net income")


if __name__ == "__main__":
    main()
