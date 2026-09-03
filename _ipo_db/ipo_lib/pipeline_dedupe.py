#!/usr/bin/env python3
"""One pipeline row per company — shared by BOTH builders.

SHEIN reached the book twice: a curated watch-list entry ("Shein Group",
no code, hand-classified Tech/AI · Internet platform) and, once its
prospectus posted, the live offering-window record ("SHEIN Global Holdings
Limited", 0625, classified Consumer · Apparel from the AAStocks industry
string). Two rows, two sectors, and the tabs disagreed with each other.

Rules, in the book's existing precedence:
  * a row carrying a real STOCK CODE supersedes a curated placeholder — it
    has the code, the timetable, the status and the parsed financials;
  * the curated HAND classification still wins over a scraped one, because
    classify.py's taxonomy is the analyst layer (the AAStocks industry
    stays visible in its own column, so both readings remain on screen);
  * anything the live row leaves blank is filled from the curated row.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clean_names import investor_key                        # noqa: E402

# facts that belong to the LIVE record and must never be back-filled from a
# stale curated guess
LIVE_ONLY = {"code", "status", "expected_timing", "doc_link", "prospectus_link"}
# the analyst judgment layer — curated wins
HAND_WINS = ("sector", "subsector")


def company_key(name):
    """Distinctive key for a company name ('Shein Group' == 'SHEIN Global')."""
    return investor_key(name or "")


def _withdrawn():
    import json
    p = Path(__file__).resolve().parent.parent / "data" / "batches" / "withdrawn.json"
    if not p.exists():
        return {}
    return {d["code"]: d for d in json.loads(p.read_text()).get("deals", [])}


def _listed():
    """The book itself: {code, company_key} for every deal that has listed.

    A pipeline row survives its own listing otherwise — SHEIN and Mech-Mind
    listed on 2026-09-01 and would have shown in the Pipeline tab AND the
    Database at once, which is the same double-count the curated/live merge
    above exists to prevent. Matched on code first, then on the company key,
    because the watch-list entry ("Shein Group") carries no code at all.
    """
    import json
    p = Path(__file__).resolve().parent.parent / "data" / "deals.json"
    if not p.exists():
        return set(), set()
    book = json.loads(p.read_text()).get("deals", [])
    codes = {str(d.get("code")) for d in book if d.get("code")}
    keys = {company_key(d.get("name")) for d in book if d.get("name")}
    return codes, keys - {""}


def merge_pipeline(rows):
    """Collapse duplicate companies. Order is preserved by first appearance;
    a coded row takes the merged slot. Withdrawn offerings are re-labelled —
    the roster keeps their prospectus, so without this they read 'OFFERING
    NOW' forever (EKH was pulled 2026-07-08 and still showed as live)."""
    # A DEAL THAT HAS LISTED IS NO LONGER PIPELINE — it is in the Database,
    # with its filed price, subscription and returns. Drop it here so it can
    # never appear in both tabs at once.
    listed_codes, listed_keys = _listed()
    kept = []
    for r in rows:
        c, k = str(r.get("code") or ""), company_key(r.get("name"))
        if (c and c in listed_codes) or (k and k in listed_keys):
            continue
        kept.append(r)
    dropped = len(rows) - len(kept)
    if dropped:
        print(f"  pipeline: {dropped} row(s) dropped — now listed, so they live "
              f"in the Database")
    rows = kept

    wd = _withdrawn()
    for r in rows:
        w = wd.get(str(r.get("code") or ""))
        if w:
            r["status"] = f"WITHDRAWN — offering pulled {w['date']}"
            r["withdrawn"] = True
            r["classification_note"] = (r.get("classification_note") or w.get("src", ""))[:160]
    out, by_key = [], {}
    for r in rows:
        k = company_key(r.get("name"))
        prev = by_key.get(k) if k else None
        if prev is None:
            if k:
                by_key[k] = r
            out.append(r)
            continue
        # decide which of the two is the live record
        live, stale = (r, prev) if (r.get("code") and not prev.get("code")) else (prev, r)
        merged = dict(live)
        for f, v in stale.items():
            if f in LIVE_ONLY or v in (None, "", []):
                continue
            if f in HAND_WINS and stale is not live:
                merged[f] = v                      # curated classification wins
            elif merged.get(f) in (None, "", []):
                merged[f] = v                      # fill only the gaps
        if stale.get("sector") and live.get("sector") \
                and stale["sector"] != live["sector"] and stale is not live:
            merged["classification_note"] = (
                f"taxonomy label kept ({stale['sector']} · "
                f"{stale.get('subsector')}); the filing's industry string reads "
                f"{live.get('industry_en') or live['sector']}")
        by_key[k] = merged
        out[out.index(prev)] = merged
    return out
