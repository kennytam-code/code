#!/usr/bin/env python3
"""Stage 5: snapshot A/H prices + premium from the AAStocks A+H table.
Writes data/batches/ah_snapshot.json. Premium = H/(A x FX) - 1, % (negative =
H cheap vs A), as published by the table; sign convention verified vs known
pairs (e.g. First Tractor deep H discount).

Each pair is then enriched from the Tencent A-line quote:
  a_total_mktcap_bn_cny  field 45 = ALL share classes x A price (ICBC control:
                         356.4bn shares implied = A+H total capital, not A-only)
  a_float_mktcap_bn_cny  field 44 = A-float x A price
  a_total_shares         field 45 / price — post-offer total share capital,
                         which is what a company-level market cap needs
  a_pe_ttm               field 47 (field 39 is the "dynamic" annualised PE)
"""
import json, re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUT = Path(__file__).resolve().parent.parent / "data" / "batches" / "ah_snapshot.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def fnum(s):
    s = re.sub(r"[+,%]", "", s).strip()
    try:
        return float(s)
    except ValueError:
        return None


def enrich_from_tencent(pairs):
    """Add total/float market cap, total share count and PE TTM from the
    Tencent A-line quote, plus one CNYHKD print. Batched ~40 symbols per
    request; a failed batch leaves those pairs unenriched (never fabricated)."""
    syms = {}
    for p in pairs:
        num, venue = (p.get("a_code") or ".").split(".")
        if num.isdigit():
            syms[("sh" if venue == "SS" else "sz") + num] = p
    fx = None
    try:
        fxq = requests.get("https://qt.gtimg.cn/q=whHKDCNY",
                           headers={"User-Agent": UA}, timeout=20).text
        fx = round(1.0 / float(fxq.split("~")[3]), 4)   # CNY -> HKD
    except Exception as e:
        print(f"  fx quote failed: {e}")
    keys = list(syms)
    done = 0
    for i in range(0, len(keys), 40):
        chunk = keys[i:i + 40]
        try:
            q = requests.get("https://qt.gtimg.cn/q=" + ",".join(chunk),
                             headers={"User-Agent": UA}, timeout=30).text
        except Exception as e:
            print(f"  quote batch {i//40} failed: {e}")
            continue
        for line in q.split(";"):
            m = re.search(r"v_(s[hz]\d{6})=\"(.*)", line)
            if not m or m.group(1) not in syms:
                continue
            f = m.group(2).split("~")
            p = syms[m.group(1)]
            try:
                px = float(f[3])
                if px <= 0:
                    continue
                if p.get("a_price") is None:
                    p["a_price"] = px
                p["a_float_mktcap_bn_cny"] = round(float(f[44]) / 10, 2)
                p["a_total_mktcap_bn_cny"] = round(float(f[45]) / 10, 2)
                p["a_total_shares"] = round(float(f[45]) * 1e8 / px)
                if fnum(f[47]):
                    p["a_pe_ttm"] = float(f[47])
                done += 1
            except (IndexError, ValueError):
                continue
    print(f"  tencent enrich: {done}/{len(syms)} A-lines, cnyhkd={fx}")
    return fx


def main():
    r = requests.get("http://www.aastocks.com/en/stocks/market/ah.aspx",
                     headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    pairs = []
    for t in soup.find_all("table"):
        for tr in t.find_all("tr"):
            c = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if len(c) < 8:
                continue
            mh = re.search(r"(\d{5})\.HK", c[1])
            ma = re.search(r"(\d{6})\.(SH|SZ)", c[4])
            if not (mh and ma):
                continue
            pairs.append({
                "code": mh.group(1).lstrip("0").zfill(4),
                "name": c[0],
                "h_price": fnum(c[2]),
                "a_code": f"{ma.group(1)}.{'SS' if ma.group(2) == 'SH' else 'SZ'}",
                "a_price": fnum(c[5]),
                "premium_pct": fnum(c[7]),
            })
    # The AAStocks table lags brand-new H listings (Luxshare/SG Micro/CCTC
    # showed up weeks late), so union in the book's own A/H map: those codes
    # still get the Tencent A-side enrichment; H price/premium stay None.
    try:
        amap = json.loads((OUT.parent / "ah_map.json").read_text())
        have = {p["code"] for p in pairs}
        for r in amap.get("ah_pairs", []):
            c = str(r.get("code", "")).lstrip("0").zfill(4)
            if c not in have and r.get("a_share_code"):
                pairs.append({"code": c, "name": r.get("name"),
                              "h_price": None, "a_code": r["a_share_code"],
                              "a_price": None, "premium_pct": None,
                              "from_ah_map": True})
    except Exception as e:
        print(f"  ah_map union skipped: {e}")
    fx = enrich_from_tencent(pairs)
    OUT.write_text(json.dumps(
        {"batch": "ah_snapshot", "source": "aastocks ah.aspx + tencent A-line quotes",
         "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "cnyhkd": fx,
         "count": len(pairs), "pairs": pairs}, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {len(pairs)} A/H pairs")


if __name__ == "__main__":
    main()
