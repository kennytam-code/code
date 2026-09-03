#!/usr/bin/env python3
"""Chinese names for every stock code, from HKEX's own listed-securities feed.

Prospectus covers only yielded name_cn for ~47% of deals (many covers render the
Chinese name as an image). HKEX publishes the full bilingual securities list as
plain JSON — active + inactive — which resolves essentially every code:

    /ncms/script/eds/activestock_sehk_c.json    17,900+ rows  {"c":"00001","n":"長和"}
    /ncms/script/eds/inactivestock_sehk_c.json  delisted/renamed

Writes data/batches/names_cn.json.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "batches" / "names_cn.json"
BASE = "https://www1.hkexnews.hk/ncms/script/eds"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def rows(name):
    r = requests.get(f"{BASE}/{name}.json", headers={"User-Agent": UA}, timeout=45)
    r.raise_for_status()
    d = r.json()
    return d if isinstance(d, list) else next(iter(d.values()))


def main():
    names = {}
    for feed in ("activestock_sehk_c", "inactivestock_sehk_c"):
        try:
            for row in rows(feed):
                code = str(row.get("c", "")).lstrip("0").zfill(4)
                nm = (row.get("n") or "").strip()
                if code and nm and code not in names:
                    names[code] = nm
        except Exception as e:
            print(f"  {feed}: {e}")
    roster = json.loads((ROOT / "data" / "batches" / "hkex_allotments.json").read_text())
    ours = {d["code"] for d in roster["deals"]}
    hit = {c: n for c, n in names.items() if c in ours}
    OUT.write_text(json.dumps(
        {"batch": "names_cn", "source": "hkexnews activestock/inactivestock _c feeds",
         "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(hit), "names": hit}, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {len(hit)}/{len(ours)} roster codes matched "
          f"({len(names)} codes in the feed)")


if __name__ == "__main__":
    main()
