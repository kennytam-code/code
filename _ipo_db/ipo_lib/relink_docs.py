#!/usr/bin/env python3
"""Re-resolve prospectus links for deals whose original per-stock search came up
empty (e.g. ZJ Innolight — listed before the stock-id feed knew the code).
Only touches deals with no recorded docs; ~2 requests each."""
import json, sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_hkex_filings import search, PROSP_TITLE, get, UA
import re as _re


def live_stock_id(code):
    """The bulk feeds map RECYCLED codes to their previous holder (3308 pointed
    at delisted Golden Eagle, not Innolight). The search box's autocomplete
    endpoint returns the CURRENT holder's id."""
    txt = get(f"https://www1.hkexnews.hk/search/prefix.do?callback=cb&lang=EN"
              f"&type=A&name={int(code):04d}&market=SEHK")
    if not txt:
        return None
    m = _re.search(r'"stockId":(\d+),"code":"0*' + str(int(code)) + '"', txt)
    return m.group(1) if m else None

ROOT = Path(__file__).resolve().parent.parent
LINKS = ROOT / "data" / "batches" / "hkex_prospectus_links.json"


def main():
    data = json.loads(LINKS.read_text())
    roster = {d["code"]: d for d in json.loads(
        (ROOT / "data" / "batches" / "hkex_allotments.json").read_text())["deals"]}
    fixed = 0
    for e in data["deals"]:
        if e.get("docs"):
            continue
        code = e["code"]
        sid = live_stock_id(code)
        ann = roster.get(code, {}).get("allot_announce_dt")
        if not (sid and ann):
            continue
        ad = datetime.fromisoformat(ann).date()
        rows = search(ad - timedelta(days=120), ad + timedelta(days=5),
                      30000, -2, -2, stock_id=sid, row_range=100)
        cands = [r for r in rows if PROSP_TITLE.search(
            r.get("TITLE", "") + r.get("LONG_TEXT", ""))] or rows
        for r in cands[:1]:
            e.setdefault("docs", []).append(
                {"title": r["TITLE"], "dt": r["DATE_TIME"], "file_link": r["FILE_LINK"]})
            fixed += 1
    LINKS.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"re-linked {fixed} deals")


if __name__ == "__main__":
    main()
