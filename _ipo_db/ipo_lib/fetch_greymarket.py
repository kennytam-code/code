#!/usr/bin/env python3
"""Grey-market (暗盤) close per deal, from AAStocks' own news headline.

WHAT THE GREY MARKET IS. The evening before a HK listing, brokers run an
off-exchange session (16:15-18:30) in the new stock. Its close is the single
best read on where the deal opens: the book is done, the allocations are out,
and anyone who wants out can leave before the exchange opens. A deal that
closes the grey market below its offer price has, in practice, already broken
issue.

THE SOURCE. AAStocks publishes one standardised headline per deal:

    《新股》希音－Ｗ暗盤收報42.2元 低上市價13.1%
    《新股》梅卡曼德機器人暗盤收報100.6元 低上市價1.1%

That is machine-readable and it is the SAME source the desk reads, so it can
be checked by eye. The quoted session is Phillip's (輝立) platform, which is
what AAStocks reports; Futu's own print differs by a tick or two (SHEIN closed
42.2 on Phillip against 42.12 on Futu), so the venue is recorded, never mixed.

THE HONEST LIMIT — READ THIS BEFORE ASKING WHY COVERAGE IS LOW. There is no
public archive of historical HK grey-market closes anywhere:
  * AAStocks' greymarket.aspx ignores its own ?symbol= parameter and always
    renders TODAY's session; the live quotes arrive over a websocket, and no
    REST endpoint serves a past one.
  * The per-stock news list is server-rendered only for RECENT items; older
    pages are JS-paginated and eight pages deep still does not reach a listing
    six weeks old.
  * etnet's calendar is likewise today-only, and its news search 404s.
So this module captures what is reachable NOW and CACHES IT FOREVER. Run it
weekly (it is part of `ipo.py refresh`) and the archive builds itself from
here on: every future listing is captured in the days around its debut, which
is exactly when the headline is still on page one. A value already in the
cache is never re-fetched and never overwritten.

Writes data/batches/greymarket.json.
Run:  python ipo_lib/fetch_greymarket.py [--limit N] [--codes 0625,9615]
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    _HERE = Path(__file__).resolve().parent
except NameError:                                        # pragma: no cover
    _HERE = Path.cwd() / "ipo_lib"
ROOT = _HERE.parent
OUT = ROOT / "data" / "batches" / "greymarket.json"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
NEWS = ("https://www.aastocks.com/tc/stocks/analysis/stock-aafn/"
        "{sym}/0/hk-stock-news/1")
THROTTLE = 0.35

# 《新股》NAME暗盤收報PRICE元 高/低上市價PCT%      ("平" = flat, no pct)
RE_GM = re.compile(
    r"《新股》\s*([^《》]{1,40}?)\s*暗盤收報\s*([\d.]+)\s*元\s*"
    r"(?:(高|低)上市價\s*([\d.]+)\s*%|(平)(?:上市價)?)")
# the timestamp AAStocks writes beside each headline
RE_DT = re.compile(r"ConvertToLocalTime\(\{dt:'(20\d\d/\d\d/\d\d) \d\d:\d\d'\}\)")


def parse(html):
    """(close, pct_signed, grey_date_iso, headline_name) or None.

    pct is signed against the OFFER price: 低 -> negative, 高 -> positive,
    平 -> 0.0. The sign is taken from the headline's own word, never inferred
    by comparing prices, because the headline is the published record.
    """
    m = RE_GM.search(html)
    if not m:
        return None
    name, px, updown, pct, flat = m.groups()
    close = float(px)
    if flat:
        signed = 0.0
    else:
        signed = float(pct) * (1 if updown == "高" else -1)
    # the dated stamp nearest the headline: scan the slice before it
    head = html[:m.start()]
    dts = RE_DT.findall(head)
    gdate = dts[-1].replace("/", "-") if dts else None
    return close, signed, gdate, name.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--codes", default="")
    ap.add_argument("--refresh-all", action="store_true",
                    help="re-fetch codes already cached (default: skip them)")
    a, _ = ap.parse_known_args()

    deals = json.loads((ROOT / "data" / "deals.json").read_text(encoding="utf-8"))["deals"]
    cache = {}
    if OUT.exists():
        cache = {r["code"]: r for r in
                 json.loads(OUT.read_text(encoding="utf-8")).get("deals", [])}

    want = [d for d in deals if d.get("code")]
    if a.codes:
        keep = {c.strip().zfill(4) for c in a.codes.split(",")}
        want = [d for d in want if d["code"] in keep]
    if not a.refresh_all:
        # a captured value is permanent — the headline scrolls off page one
        # within days, so re-fetching can only ever LOSE data
        want = [d for d in want if not (cache.get(d["code"], {}).get("grey_close"))]
    want.sort(key=lambda d: d.get("ipo_date") or "", reverse=True)   # newest first
    if a.limit:
        want = want[:a.limit]

    print(f"{len(cache)} cached ({sum(1 for r in cache.values() if r.get('grey_close'))} "
          f"with a grey-market close), fetching {len(want)}", flush=True)
    got = 0
    for i, d in enumerate(want):
        code = d["code"]
        try:
            r = requests.get(NEWS.format(sym=code.zfill(5)), headers=UA, timeout=25)
            hit = parse(r.text) if r.status_code == 200 else None
        except Exception:
            hit = None
        time.sleep(THROTTLE)
        rec = cache.get(code) or {"code": code}
        if hit:
            close, pct, gdate, nm = hit
            rec.update({"grey_close": close, "grey_pct": round(pct, 2),
                        "grey_date": gdate, "grey_name_cn": nm,
                        "grey_venue": "Phillip (輝立), as published by AAStocks",
                        "grey_src": f"AASTOCKS news headline: 《新股》{nm}暗盤收報"
                                    f"{close}元 {'高' if pct > 0 else '低' if pct < 0 else '平'}"
                                    f"上市價{abs(pct)}%"})
            got += 1
            print(f"  {code} {nm} -> {close} ({pct:+.1f}%)", flush=True)
        else:
            rec.setdefault("grey_miss", True)
        cache[code] = rec
        if (i + 1) % 40 == 0:
            print(f"  {i+1}/{len(want)} scanned, {got} found", flush=True)
            _write(cache)
    _write(cache)
    n_have = sum(1 for r in cache.values() if r.get("grey_close"))
    print(f"wrote {OUT}: {n_have} deals with a grey-market close "
          f"({got} new this run)")
    return 0


def _write(cache):
    OUT.write_text(json.dumps(
        {"batch": "greymarket",
         "note": ("Grey-market (暗盤) close from the AAStocks news headline, the "
                  "evening session before listing. ACCUMULATING CACHE: a captured "
                  "value is never re-fetched, because the headline leaves page one "
                  "within days and no public archive of past sessions exists. "
                  "pct is signed against the offer price and taken from the "
                  "headline's own 高/低/平 wording."),
         "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "with_close": sum(1 for r in cache.values() if r.get("grey_close")),
         "deals": sorted(cache.values(), key=lambda r: r["code"])},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
