#!/usr/bin/env python3
"""One pipeline row per company — shared by BOTH builders.

SHEIN reached the book twice: a curated watch-list entry ("Shein Group",
no code, hand-classified Technology · Internet platform) and, once its
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

def status_asof(root):
    """Independent pipeline check date; never borrow a price snapshot date."""
    import json
    p = Path(root) / 'data/batches/pipeline_review.json'
    reviewed = json.loads(p.read_text()).get('checked_at', '') if p.exists() else ''
    fetched = []
    for name in ['newlistings.json','phip_pipeline.json']:
        source = Path(root) / 'data/batches' / name
        fetched.append(json.loads(source.read_text()).get('fetched_at', '')[:10] if source.exists() else '')
    return max(reviewed, min(fetched)) or 'Not checked'


def company_key(name):
    """Distinctive key for a company name ('Shein Group' == 'SHEIN Global')."""
    import re
    # City/province prefixes describe the domicile, not the issuer. Keeping
    # "Anhui" or "Zhejiang" as the brand collapses unrelated applicants and
    # can falsely mark a new PHIP as an already listed company.
    name = re.sub(r"^(?:Shenzhen|Shanghai|Beijing|Guangzhou|Zhuhai|Suzhou|"
                  r"Hangzhou|Hefei|Nanjing|Chengdu|Qingdao|Anhui|Zhejiang|Hunan|"
                  r"Hubei|Jiangsu|Jiangxi|Guangdong|Shandong|Fujian|Henan|"
                  r"Hebei|Sichuan|Chongqing|Tianjin)\s+", "", name or "", flags=re.I)
    return investor_key(name)


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
    keys = {company_key(d.get(f)) for d in book for f in ("name", "name_full")
            if d.get(f)}
    return codes, keys - {""}


def merge_pipeline(rows):
    """Collapse duplicate companies. Order is preserved by first appearance;
    a coded row takes the merged slot. Withdrawn offerings are re-labelled —
    the roster keeps their prospectus, so without this they read 'OFFERING
    NOW' forever (EKH was pulled 2026-07-08 and still showed as live)."""
    # A DEAL THAT HAS LISTED IS NO LONGER PIPELINE — it is in the Database,
    # with its filed price, subscription and returns. Drop it here so it can
    # never appear in both tabs at once.
    # Migrate cached provisional labels as well as newly fetched records.
    for row in rows:
        if row.get("subsector") == "AI chips & semis":
            row["subsector"] = ("Semiconductors" if "sinomags" in (row.get("name") or "").lower() else "Semiconductors")
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
        if w and w.get("kind") == "postponed":
            # POSTPONED is not WITHDRAWN: the issuer says a new timetable is
            # being set (Forms Syntron 6700, 2026-09-17)
            r["status"] = f"POSTPONED — offering and listing postponed {w['date']}"
            r["postponed"] = True
            r["expected_timing"] = "Timetable pending"
            r["classification_note"] = (r.get("classification_note") or w.get("src", ""))[:160]
        elif w:
            r["status"] = f"WITHDRAWN — offering pulled {w['date']}"
            r["withdrawn"] = True
            r["expected_timing"] = "Withdrawn " + w['date']
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
