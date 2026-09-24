#!/usr/bin/env python3
"""etnet's per-deal IPO page: the grey market by venue, and the retail facts.

https://www.etnet.com.hk/www/tc/stocks/ipo-info.php?code=NNNNN is server-
rendered and, for deals from roughly Q4-2024 on, keeps the evening session's
table for all three venues (耀才 Bright Smart, 輝立 Phillip, 富途 Futu):
last price, change %, high, low, volume, one-lot P&L. It also states the
public subscription multiple, the one-lot hit rate (一手中籤率) and the final
HK / international split.

Writes data/batches/etnet_ipo.json, one record per deal:
  grey_venues     {venue: {price, pct, high, low, volume}}
  grey_close      the price at the venue with the most volume (stated in
                  grey_venue), so one deal is one number on one basis
  grey_pct        that venue's change vs the offer price
  grey_lo / grey_hi   the spread of closes across venues
  public_x_etnet, one_lot_hit_pct, hk_pct_etnet, intl_pct_etnet

Supports --only / --new. Polite: ~1 s per page.
"""
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "batches" / "etnet_ipo.json"
UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")}
VENUES = {"耀才": "Bright Smart", "輝立": "Phillip", "富途": "Futu"}
RE_ROW = re.compile(r"(耀才|輝立|富途)\s+([\d,.]+)\s+([+\-−]?[\d,.]+)\s+\(([+\-−]?[\d,.]+)%\)\s+"
                    r"([\d,.]+)\s+([\d,.]+)\s+([\d,]+)")


def fnum(s):
    try:
        return float(str(s).replace(",", "").replace("−", "-"))
    except ValueError:
        return None


def fetch(code, tries=3):
    u = f"https://www.etnet.com.hk/www/tc/stocks/ipo-info.php?code={int(code):05d}"
    for k in range(tries):
        try:
            r = requests.get(u, headers=UA, timeout=30)
            if r.status_code == 200 and len(r.text) > 50000:
                return r.text
        except Exception:
            pass
        time.sleep(2 * (k + 1))
    return ""


def parse(html):
    rec = {}
    # labels and values sit in separate tags; match on the flattened text
    flat = re.sub(r"\s+", " ", BeautifulSoup(html, "html.parser").get_text(" "))
    html_raw, html = html, flat
    m = re.search(r"公開認購倍數\s*([\d,.]+)x", html)
    if m:
        rec["public_x_etnet"] = fnum(m.group(1))
    m = re.search(r"一手中籤率\s*([\d.]+)%", html)
    if m:
        rec["one_lot_hit_pct"] = fnum(m.group(1))
    m = re.search(r"香港發售股份數目\s*[\d,.]+\s*[萬億]?\s*(?:H\s*)?股\s*\(([\d.]+)%\)", html)
    if m:
        rec["hk_pct_etnet"] = fnum(m.group(1))
    m = re.search(r"國際發售股份數目\s*[\d,.]+\s*[萬億]?\s*(?:H\s*)?股\s*\(([\d.]+)%\)", html)
    if m:
        rec["intl_pct_etnet"] = fnum(m.group(1))
    j = html_raw.find("ipo-table greymarket")
    if j > 0:
        txt = re.sub(r"\s+", " ", BeautifulSoup(html_raw[j:j + 6000], "html.parser").get_text(" "))
        venues = {}
        for mm in RE_ROW.finditer(txt):
            v, px, chg, pct, hi, lo, vol = mm.groups()
            venues[VENUES[v]] = {"price": fnum(px), "chg": fnum(chg), "pct": fnum(pct),
                                 "high": fnum(hi), "low": fnum(lo), "volume": fnum(vol)}
        if venues:
            rec["grey_venues"] = venues
            best = max(venues.items(), key=lambda kv: kv[1].get("volume") or 0)
            rec["grey_venue"] = best[0]
            rec["grey_close"] = best[1]["price"]
            rec["grey_pct"] = best[1]["pct"]
            closes = [v["price"] for v in venues.values() if v.get("price")]
            rec["grey_lo"], rec["grey_hi"] = min(closes), max(closes)
        m = re.search(r"暗盤數據更新[:：]\s*(\d{2})/(\d{2})/(\d{4})", html_raw)
        if m:
            rec["grey_date"] = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return rec


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import incremental
    deals = json.loads((ROOT / "data" / "deals.json").read_text())["deals"]
    only = incremental.wanted(OUT, [d["code"] for d in deals])
    rows = [d for d in deals if only is None or d["code"] in only]
    if only is not None:
        print(f"  incremental: {len(rows)} deal(s) to fetch")
    recs, n_grey = [], 0
    for i, d in enumerate(rows):
        html = fetch(d["code"])
        rec = parse(html) if html else {}
        rec["code"] = d["code"]
        recs.append(rec)
        if rec.get("grey_pct") is not None:
            n_grey += 1
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(rows)} fetched, {n_grey} with a grey table", flush=True)
            OUT.write_text(json.dumps({"batch": "etnet_ipo", "partial": True,
                                       "deals": incremental.merge(OUT, recs, only)}, ensure_ascii=False))
        time.sleep(1.0)
    recs = incremental.merge(OUT, recs, only)
    OUT.write_text(json.dumps(
        {"batch": "etnet_ipo", "note": __doc__.split("\n\n")[1].strip(),
         "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(recs), "with_grey": sum(1 for r in recs if r.get("grey_pct") is not None),
         "with_hit_rate": sum(1 for r in recs if r.get("one_lot_hit_pct") is not None),
         "deals": recs}, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {len(recs)} deals | grey table {sum(1 for r in recs if r.get('grey_pct') is not None)} "
          f"| one-lot hit rate {sum(1 for r in recs if r.get('one_lot_hit_pct') is not None)}")


if __name__ == "__main__":
    main()
