#!/usr/bin/env python3
"""Stage 1b/2: enumerate HK IPOs and fetch filings from hkexnews.hk.

Subcommands:
  roster        Enumerate all 'Allotment Results' announcements 2021-01-01..today
                (quarterly windows) -> data/batches/hkex_allotments.json.
                This is the definitive IPO roster: one announcement per IPO.
  allotments    For each roster entry, fetch the multi-file index and download
                the Cover/Summary parts (offer price, oversub, greenshoe,
                cornerstone) -> pdf_cache/allot_<code>_<pdfname>.pdf
  prospectus    For each roster entry, find its prospectus (Listing Documents
                filed within 75d before allotment) and download the parts that
                matter (Cover, Summary, Expected Timetable, Offering Statistics)
                -> pdf_cache/prosp_<code>_<pdfname>.pdf; index saved to
                data/batches/hkex_prospectus_links.json

API notes (discovered by probing):
  search servlet: /search/titleSearchServlet.do  (GET, JSON)
  Allotment Results: t1code=10000, t2code=15100, t2Gcode=5
  Listing Documents: t1code=30000 (t2 -2 = all)
  stockId for per-stock queries comes from /ncms/script/eds/activestock_sehk_e.json
  and inactivestock_sehk_e.json ({stock code -> internal id}).
"""
import json, os, re, sys, time
from urllib.parse import urlsplit
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scrape" / "pdf_cache"
BATCHES = ROOT / "data" / "batches"
BASE = "https://www1.hkexnews.hk"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
THROTTLE_S = 0.8
CUTOFF = date(2021, 1, 1)

SESS = requests.Session()
SESS.headers["User-Agent"] = UA


def get(url, params=None, binary=False, tries=3):
    for attempt in range(tries):
        try:
            r = SESS.get(url, params=params, timeout=45)
            r.raise_for_status()
            time.sleep(THROTTLE_S)
            return r.content if binary else r.text
        except Exception as e:
            print(f"  retry {attempt+1} {url}: {e}", file=sys.stderr)
            time.sleep(4 * (attempt + 1))
    print(f"  GIVING UP {url}", file=sys.stderr)
    return None


def search(from_d, to_d, t1, t2, t2g, stock_id=-1, row_range=500):
    txt = get(f"{BASE}/search/titleSearchServlet.do", params={
        "sortDir": 0, "sortByOptions": "DateTime", "category": 0,
        "market": "SEHK", "stockId": stock_id, "documentType": -1,
        "fromDate": from_d.strftime("%Y%m%d"), "toDate": to_d.strftime("%Y%m%d"),
        "title": "", "searchType": 1, "t1code": t1, "t2Gcode": t2g,
        "t2code": t2, "rowRange": row_range, "lang": "E"})
    if txt is None:
        return []
    d = json.loads(txt)
    if not d.get("result") or d["result"] == "null":
        return []
    if d.get("hasNextRow"):
        print(f"  WARNING window {from_d}..{to_d} truncated at {row_range}", file=sys.stderr)
    return json.loads(d["result"])


def quarters():
    q = CUTOFF
    today = date.today()
    while q <= today:
        if q.month <= 3:   end = date(q.year, 3, 31)
        elif q.month <= 6: end = date(q.year, 6, 30)
        elif q.month <= 9: end = date(q.year, 9, 30)
        else:              end = date(q.year, 12, 31)
        yield q, min(end, today)
        q = end + timedelta(days=1)


def parse_dt(s):  # "30/03/2022 06:54"
    return datetime.strptime(s, "%d/%m/%Y %H:%M")


def norm_code(s):
    return s.lstrip("0").zfill(4)


NOT_IPO = re.compile(r"rights\s+issue|rights\s+shares?\b|open\s+offer|"
                     r"general\s+mandate|de-?spac|resumption", re.I)
IS_IPO = re.compile(r"allotment|offer\s+price|global\s+offering|share\s+offer|"
                    r"subscription\s+results", re.I)


def cmd_roster():
    recs = []
    for a, b in quarters():
        rows = search(a, b, 10000, 15100, 5)
        keep = [r for r in rows
                if not NOT_IPO.search(r.get("TITLE", ""))
                and IS_IPO.search(r.get("TITLE", ""))]
        print(f"{a}..{b}: {len(rows)} announcements, {len(keep)} IPO")
        recs.extend(keep)
    deals = {}
    for r in recs:
        code = norm_code(r["STOCK_CODE"])
        dt = parse_dt(r["DATE_TIME"])
        item = {
            "code": code,
            "board": "GEM" if code.zfill(5).lstrip("0").startswith("8") else "Main",
            "stock_name_short": r["STOCK_NAME"],
            "allot_announce_dt": dt.isoformat(),
            "ipo_date_est": (dt.date() + timedelta(days=1)).isoformat(),
            "title": r["TITLE"],
            "news_id": r["NEWS_ID"],
            "file_link": r["FILE_LINK"],
            "file_info": r["FILE_INFO"],
        }
        # keep earliest announcement per code (re-listings would be years apart; fine)
        if code not in deals or item["allot_announce_dt"] < deals[code]["allot_announce_dt"]:
            deals[code] = item
    out = {
        "batch": "hkex_allotments",
        "source": "hkexnews titleSearchServlet t2=15100 Allotment Results",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(deals),
        "deals": sorted(deals.values(), key=lambda d: d["allot_announce_dt"]),
    }
    p = BATCHES / "hkex_allotments.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"wrote {p}: {out['count']} unique IPOs")


SKIP_PART = re.compile(r"identification|beneficiary|share certificates|refund", re.I)
WANT_ALLOT = re.compile(r"cover|summary|result|offer price|announcement", re.I)


def doc_parts(file_link):
    """Return [(label, absolute_pdf_url)] from a listconews page (htm index or direct pdf)."""
    if file_link.lower().endswith(".pdf"):
        return [("Document", BASE + file_link)]
    html = get(BASE + file_link)
    if html is None:
        return []
    soup = BeautifulSoup(html, "lxml")
    base_dir = file_link.rsplit("/", 1)[0]
    parts = []
    for a in soup.find_all("a", href=True):
        if a["href"].lower().endswith(".pdf"):
            label = a.get_text(" ", strip=True) or "part"
            href = a["href"]
            url = href if href.startswith("http") else f"{BASE}{base_dir}/{href}"
            parts.append((label, url))
    return parts


def download_parts(prefix, code, parts, want, skip, max_parts=4):
    got = []
    for label, url in parts:
        if skip and skip.search(label):
            continue
        if want and not want.search(label):
            continue
        name = f"{prefix}_{code}_{url.rsplit('/', 1)[-1]}"
        dest = CACHE / name
        if dest.exists() and dest.stat().st_size > 1000:
            got.append({"label": label, "file": name, "url": url})
            continue
        blob = get(url, binary=True)
        if blob and blob[:4] == b"%PDF":
            dest.write_bytes(blob)
            got.append({"label": label, "file": name, "url": url})
        if len(got) >= max_parts:
            break
    return got


def cmd_allotments():
    roster = json.loads((BATCHES / "hkex_allotments.json").read_text())
    manifest = []
    for i, d in enumerate(roster["deals"]):
        parts = doc_parts(d["file_link"])
        # single-file announcements: take the pdf as-is
        want = WANT_ALLOT if len(parts) > 1 else None
        got = download_parts("allot", d["code"], parts, want, SKIP_PART)
        manifest.append({"code": d["code"], "parts": got})
        if (i + 1) % 25 == 0:
            print(f"{i+1}/{roster['count']} allotment docs fetched")
    p = BATCHES / "hkex_allotment_files.json"
    p.write_text(json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(timespec='seconds'),
                             "manifest": manifest}, ensure_ascii=False, indent=1))
    n = sum(1 for m in manifest if m["parts"])
    print(f"wrote {p}: {n}/{len(manifest)} deals with >=1 pdf")


PROSP_TITLE = re.compile(r"prospectus|global offering|share offer|offering", re.I)
WANT_PROSP = re.compile(r"^cover|summary|expected timetable|offering statistics|"
                        r"formal notice", re.I)


def load_stock_ids():
    ids = {}
    for f in ("activestock_sehk_e.json", "inactivestock_sehk_e.json"):
        txt = get(f"{BASE}/ncms/script/eds/{f}")
        if not txt:
            continue
        data = json.loads(txt)
        # format: list of dicts with 'c' (code) and 'i' (id) — probe defensively
        seq = data if isinstance(data, list) else data.get("stockList", [])
        for row in seq:
            if isinstance(row, dict):
                c = row.get("c") or row.get("code") or row.get("STOCK_CODE")
                i = row.get("i") or row.get("id") or row.get("STOCK_ID")
                if c is not None and i is not None:
                    ids[norm_code(str(c))] = str(i)
    return ids


def attach_cached_newlist(links):
    """Give a deal its prospectus back when the per-stock search came up empty.

    A BRAND-NEW code loses a race with itself: `fetch_newlistings` downloads the
    prospectus the day it posts (as `newlist_<code>_*.pdf`), while the search
    above still cannot resolve a code that new and returns nothing — so the
    manifest carries no parts for a document already sitting in the cache.
    SHEIN (0625) listed with its prospectus unparsed for exactly this reason,
    and the merge then labelled its missing sponsors "not stated in the
    extractable filing text", which was untrue: they were in the text nobody
    opened.

    Fixed HERE rather than in each parser because extract_prospectus,
    extract_deep (sponsors, bookrunners) and extract_profiles all read this one
    manifest and all skip a deal with no parts. Returns the codes rescued.
    """
    gaps = [r for r in links if not r.get("parts")]
    if not gaps:
        return []
    # ONE pass over the cache, not one glob per gap: pdf_cache holds thousands
    # of files, and globbing it per deal is ~200k stat calls for nothing.
    by_code = {}
    for name in os.listdir(CACHE):
        if name.startswith("newlist_") and name.endswith(".pdf"):
            by_code.setdefault(name.split("_")[1], []).append(name)
    # The offering-window record holds the CANONICAL hkexnews URL for the very
    # same file, which is what the Database hyperlink is built from.
    nl = {}
    nlp = BATCHES / "newlistings.json"
    if nlp.exists():
        for r in json.loads(nlp.read_text()).get("deals", []):
            urls = [u for u in (r.get("prospectus_links") or []) if u]
            if urls:
                nl[r["code"]] = urls
    rescued = []
    for rec in gaps:
        found = sorted(by_code.get(rec["code"], []))
        if not found:
            continue
        rec["parts"] = [{"file": f, "label": "prospectus (offering-window copy)"}
                        for f in found]
        # docs[0]["file_link"] is concatenated onto the hkexnews host to make
        # the Database's prospectus hyperlink, so it must be a real PATH.
        # Writing None here is what crashed the merge ("can only concatenate
        # str (not NoneType) to str") — never append a doc without a link.
        for u in nl.get(rec["code"], [])[:1]:
            path = urlsplit(u).path
            if path:
                rec.setdefault("docs", []).append(
                    {"title": "Prospectus (offering-window copy)",
                     "dt": None, "file_link": path})
        rescued.append(rec["code"])
    return rescued


def cmd_prospectus():
    roster = json.loads((BATCHES / "hkex_allotments.json").read_text())
    ids = load_stock_ids()
    print(f"stock id map: {len(ids)} codes")
    links, manifest = [], []
    for i, d in enumerate(roster["deals"]):
        sid = ids.get(d["code"])
        rec = {"code": d["code"], "stock_id": sid, "docs": [], "parts": []}
        if sid:
            ann = datetime.fromisoformat(d["allot_announce_dt"]).date()
            rows = search(ann - timedelta(days=75), ann + timedelta(days=3),
                          30000, -2, -2, stock_id=sid, row_range=100)
            cands = [r for r in rows if PROSP_TITLE.search(r.get("TITLE", "") + r.get("LONG_TEXT", ""))] or rows
            for r in cands[:2]:
                rec["docs"].append({"title": r["TITLE"], "dt": r["DATE_TIME"],
                                    "file_link": r["FILE_LINK"]})
                parts = doc_parts(r["FILE_LINK"])
                want = WANT_PROSP if len(parts) > 1 else None
                rec["parts"] += download_parts("prosp", d["code"], parts, want,
                                               SKIP_PART, max_parts=5)
                if rec["parts"]:
                    break
        links.append(rec)
        if (i + 1) % 25 == 0:
            print(f"{i+1}/{roster['count']} prospectuses processed")
    rescued = attach_cached_newlist(links)
    p = BATCHES / "hkex_prospectus_links.json"
    p.write_text(json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(timespec='seconds'),
                             "deals": links}, ensure_ascii=False, indent=1))
    n = sum(1 for m in links if m["parts"])
    print(f"wrote {p}: {n}/{len(links)} deals with prospectus parts")
    if rescued:
        print(f"  {len(rescued)} recovered from the offering-window cache: "
              f"{', '.join(rescued)}")


if __name__ == "__main__":
    CACHE.mkdir(parents=True, exist_ok=True)
    BATCHES.mkdir(parents=True, exist_ok=True)
    {"roster": cmd_roster, "allotments": cmd_allotments,
     "prospectus": cmd_prospectus}[sys.argv[1]]()
