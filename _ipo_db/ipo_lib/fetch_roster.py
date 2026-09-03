#!/usr/bin/env python3
"""Stage 1: bulk roster of HKEX listed IPOs from AAStocks listedipo pages.

Crawls http://www.aastocks.com/en/stocks/market/ipo/listedipo.aspx?s=3&o=0&page=N
(20 rows/page, sorted by listing date desc) back to CUTOFF, and writes
data/batches/bulk_roster.json.

Columns observed (13 tds/row, first empty):
  [1] Name + Code ("NASN TECH 02261.HK" + optional status suffix text)
  [2] Listing Date yyyy/mm/dd   [3] Lot Size      [4] Market Cap (HK$B, may be range)
  [5] Offer Price               [6] Listing Price [7] Over-sub. rate (x)
  [8] Applied lots for 1 lot    [9] One-lot success rate
  [10] Last                     [11] % Chg on Debut  [12] Acc. % Chg

Semantics fixed downstream by merge/verification; raw strings preserved in _raw.
"""
import json, re, sys, time
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "http://www.aastocks.com/en/stocks/market/ipo/listedipo.aspx?s=3&o=0&page={page}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
CUTOFF = date(2021, 1, 1)
MAX_PAGES = 60
THROTTLE_S = 1.5
OUT = Path(__file__).resolve().parent.parent / "data" / "batches" / "bulk_roster.json"

CODE_RE = re.compile(r"(\d{5})\.HK")
DATE_RE = re.compile(r"(\d{4})/(\d{2})/(\d{2})")


def fnum(s):
    """'2,512.5'->2512.5, '+64.110%'->64.11, 'N/A'/''->None. Ranges handled separately."""
    if s is None:
        return None
    s = s.replace(",", "").replace("%", "").strip()
    if s in ("", "N/A", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_row(cells):
    blob = " ".join(cells)
    mdate = DATE_RE.search(blob)
    mcode = CODE_RE.search(cells[1])
    if not (mdate and mcode):
        return None
    d = date(int(mdate.group(1)), int(mdate.group(2)), int(mdate.group(3)))
    name = cells[1]
    name = CODE_RE.sub("", name).strip()
    # strip AAStocks status suffixes appended to the name cell
    for suffix in ("Sink Below Listing Price", "Rise Above Listing Price"):
        name = name.replace(suffix, "").strip()
    mcap = cells[4].replace(",", "").strip()
    mcap_lo = mcap_hi = None
    if mcap not in ("N/A", ""):
        parts = mcap.split("-")
        mcap_lo = fnum(parts[0])
        mcap_hi = fnum(parts[-1])
    return {
        "code": mcode.group(1).lstrip("0").zfill(4),
        "board": "GEM" if mcode.group(1).lstrip("0").startswith("8") else "Main",
        "name": name,
        "ipo_date": d.isoformat(),
        "lot_size": fnum(cells[3]),
        "mktcap_bn_lo": mcap_lo,
        "mktcap_bn_hi": mcap_hi,
        "final_price": fnum(cells[5]),
        "listing_price": fnum(cells[6]),
        "oversub_mult": fnum(cells[7]),
        "one_lot_success_pct": fnum(cells[9]),
        "first_day_return_pct": fnum(cells[11]),
        "acc_return_pct": fnum(cells[12]),
        "_raw": cells[1:],
    }


def fetch_page(sess, page):
    r = sess.get(BASE.format(page=page), timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    rows = []
    for t in soup.find_all("table"):
        for tr in t.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if len(cells) == 13 and DATE_RE.search(" ".join(cells)):
                parsed = parse_row(cells)
                if parsed:
                    rows.append(parsed)
    return rows


def main():
    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    deals, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        for attempt in range(3):
            try:
                rows = fetch_page(sess, page)
                break
            except Exception as e:
                print(f"page {page} attempt {attempt+1} failed: {e}", file=sys.stderr)
                time.sleep(5 * (attempt + 1))
        else:
            sys.exit(f"giving up on page {page}")
        if not rows:
            print(f"page {page}: no rows, stopping")
            break
        fresh = [r for r in rows if r["code"] not in seen]
        for r in fresh:
            seen.add(r["code"])
        deals.extend(fresh)
        oldest = min(r["ipo_date"] for r in rows)
        print(f"page {page}: {len(rows)} rows ({len(fresh)} new), oldest {oldest}")
        if oldest < CUTOFF.isoformat():
            break
        time.sleep(THROTTLE_S)

    in_window = [d for d in deals if d["ipo_date"] >= CUTOFF.isoformat()]
    out = {
        "batch": "bulk_roster",
        "source": "AAStocks listedipo.aspx (s=3&o=0)",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cutoff": CUTOFF.isoformat(),
        "count": len(in_window),
        "count_main_board": sum(1 for d in in_window if d["board"] == "Main"),
        "deals": sorted(in_window, key=lambda d: d["ipo_date"]),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"wrote {OUT} : {out['count']} deals ({out['count_main_board']} Main Board)")


if __name__ == "__main__":
    main()
