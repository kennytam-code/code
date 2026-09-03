#!/usr/bin/env python3
"""Fetch the FULL prospectus body for deals where only Cover/Summary extracts
(or nothing) were downloaded — 106 deals incl. Kuaishou, JD Logistics, SenseTime.

For deals with a recorded doc index: re-fetch the index and download the LARGE
parts that the original Cover/Summary filter skipped (business, financials,
cornerstone, parties sections all live there). For deals with no doc at all:
re-search the HKEX index with a wider window (120 days before allotment) and no
title filter, preferring the entry whose parts include a large body.

Updates data/batches/hkex_prospectus_links.json in place (adds parts).
"""
import json, re, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_hkex_filings import (BASE, CACHE, doc_parts, get, search,
                                load_stock_ids, SKIP_PART)

ROOT = Path(__file__).resolve().parent.parent
LINKS = ROOT / "data" / "batches" / "hkex_prospectus_links.json"
TEXTS = ROOT / "scrape" / "text_cache"
PROSP_TITLE = re.compile(r"prospectus|global offering|share offer|offering", re.I)


def cached_size(pdf_name):
    f = TEXTS / (pdf_name + ".txt")
    return f.stat().st_size if f.exists() else 0


def total_text(entry):
    """Combined extracted-text size across the deal's parts — PDF byte size lies
    (an image-heavy 28-page Summary weighs more than a 600-page body)."""
    tot = 0
    for p in entry.get("parts", []):
        f = TEXTS / (p["file"] + ".txt")
        if f.exists():
            tot += f.stat().st_size
    return tot


def download_all_parts(code, file_link, existing):
    """Download every non-ID part of a filing (the body sections)."""
    got = []
    have = {p["file"] for p in existing}
    for label, url in doc_parts(file_link):
        if SKIP_PART.search(label):
            continue
        name = f"prosp_{code}_{url.rsplit('/', 1)[-1]}"
        dest = CACHE / name
        if name in have or (dest.exists() and dest.stat().st_size > 1000):
            if name not in have:
                got.append({"label": label, "file": name, "url": url})
            continue
        blob = get(url, binary=True)
        if blob and blob[:4] == b"%PDF":
            dest.write_bytes(blob)
            got.append({"label": label, "file": name, "url": url})
    return got


def main():
    data = json.loads(LINKS.read_text())
    by_code = {e["code"]: e for e in data["deals"]}
    roster = json.loads((ROOT / "data" / "batches" / "hkex_allotments.json").read_text())
    ann_of = {d["code"]: d["allot_announce_dt"] for d in roster["deals"]}

    need = [e for e in data["deals"] if total_text(e) < 700_000]
    print(f"{len(need)} deals lack a full body", flush=True)
    ids = load_stock_ids()

    fixed = 0
    for i, e in enumerate(need):
        code = e["code"]
        added = []
        # path 1: re-walk the already-known doc indexes and take the big parts
        for doc in e.get("docs", []):
            added += download_all_parts(code, doc["file_link"], e.get("parts", []))
        # path 2: nothing on file — search wider
        if not e.get("docs"):
            sid = ids.get(code)
            ann = ann_of.get(code)
            if sid and ann:
                ad = datetime.fromisoformat(ann).date()
                rows = search(ad - timedelta(days=120), ad + timedelta(days=5),
                              30000, -2, -2, stock_id=sid, row_range=100)
                cands = [r for r in rows if PROSP_TITLE.search(
                    r.get("TITLE", "") + r.get("LONG_TEXT", ""))] or rows
                for r in cands[:2]:
                    e.setdefault("docs", []).append(
                        {"title": r["TITLE"], "dt": r["DATE_TIME"],
                         "file_link": r["FILE_LINK"]})
                    added += download_all_parts(code, r["FILE_LINK"], e.get("parts", []))
                    if added:
                        break
        if added:
            e.setdefault("parts", []).extend(added)
            fixed += 1
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(need)} processed, {fixed} gained parts", flush=True)
            LINKS.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    data["bodies_fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    LINKS.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"done: {fixed}/{len(need)} deals gained body parts")


if __name__ == "__main__":
    main()
