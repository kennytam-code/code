#!/usr/bin/env python3
"""etnet's news wire, read by article ID: the grey market for deals before Oct-2024.

etnet's per-deal 暗盤數據 table (fetch_etnet_ipo.py) starts 2024-10-02. Its
news wire goes back much further, and every article on it resolves by ID:

    https://www.etnet.com.hk/www/tc/stocks/ipo-news-article/{YYYYMMDD}{NNN}/x

The ID is the date plus a three-digit sequence (001-999). The sequence is NOT
in time order, so a whole day is read by title (the first ~2 KB of the page).
Only titles containing 暗盤 are then read in full. On the evening of a grey
session the wire carries two stories per deal:

    藥師幫暗盤報25.6元,高招股價28%        輝立暗盤現報 ...   (mid-session)
    藥師幫暗盤收高30%,每手賺1200元        輝立暗盤收報26元   (the close)

The print is Phillip's (輝立) close, which is what the story reports as closed.
The other venues' quotes in the same story are live quotes, not closes, and are
kept only as context. Through mid-2021 the wire reported only the grey OPEN
(開報/開市價), and an open is not a close: those deals get a note, not a number.

Writes data/grey_market_etnet_news.json (tracked, because the capture is the
archive): per deal the close, the date, the venue, the offer price the story
quoted, and the article URL. merge_batches.py reads it at priority 55 and
re-checks close / offer - 1 against the filed offer price.

usage:
    python ipo_lib/fetch_etnet_grey_news.py            # every deal without a grey print
    python ipo_lib/fetch_etnet_grey_news.py 2410 9885  # named deals only
    python ipo_lib/fetch_etnet_grey_news.py --parse    # re-read the cache, no fetching
    python ipo_lib/fetch_etnet_grey_news.py --parse --refetch-empty   # + re-read empty bodies

Cost: about 30 s per session date with 64 threads (999 title reads). The
title cache lives in scrape/etnet_news/{date}.json, so a rerun only re-reads
the articles.
"""
import bisect
import html
import json
import re
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "grey_market_etnet_news.json"
CACHE = ROOT / "scrape" / "etnet_news"
URL = "https://www.etnet.com.hk/www/tc/stocks/ipo-news-article/{}/x"
UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")}
VEN = {"輝立": "Phillip", "耀才": "Bright Smart", "富途": "Futu"}
NUM = r"(\d+(?:\.\d+)?)"
# one clause: venue ... verb price元. The verb says whether it is a close.
RE_CLAUSE = re.compile(r"(輝立|耀才|富途)[^。;]{0,24}?(收市報|收市價為?|收報|收於|收市|收|"
                       r"開市價為?|開報|開市報|開|現報|暫報|暫高報?|報)\s*" + NUM + r"\s*元")
# the 2021 wording puts the venue in its own clause: "據輝立交易場顯示,醫渡暗盤價收報58.25元"
RE_CLOSE_ANY = re.compile(r"(?:收市報|收市價為?|收報|收於)\s*" + NUM + r"\s*元")
RE_OFFER = re.compile(r"較(?:該行顯示的)?招股價(?:每股)?\s*" + NUM + r"\s*元")
RE_CODE = re.compile(r"\((\d{4,5})\)")
RE_TITLE = re.compile(r"<title>(.*?)\|", re.S)
SIDEBAR = re.compile(r"(認購中\(|延遲最少|即將解禁|十大保薦人|最活躍保薦人|熱門行業|首日表現最|累積表現最|一手難求)")

S = requests.Session()
S.headers.update(UA)
S.mount("https://", requests.adapters.HTTPAdapter(pool_connections=64, pool_maxsize=64))


def nf(s):
    return unicodedata.normalize("NFKC", html.unescape(s)).strip()


def title(i, tries=3):
    """The headline only: stream the page and stop at </title>."""
    for k in range(tries):
        try:
            with S.get(URL.format(i), timeout=20, stream=True) as r:
                buf = b""
                for ch in r.iter_content(1024):
                    buf += ch
                    if b"</title>" in buf or len(buf) > 6000:
                        break
            m = RE_TITLE.search(buf.decode("utf-8", "ignore"))
            return nf(m.group(1)) if m else ""
        except Exception:
            time.sleep(1 + k)
    return None


def article(i, tries=3):
    for k in range(tries):
        try:
            h = S.get(URL.format(i), timeout=30).text
            break
        except Exception:
            time.sleep(1 + k)
    else:
        return None
    t = RE_TITLE.search(h)
    body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S)
    txt = nf(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)))
    head = nf(t.group(1)) if t else ""
    k = txt.find("《經濟通通訊社")
    if k < 0 and head:
        # a story carried from another paper (《香港經濟日報》) has no wire
        # dateline: the body follows the headline's LAST appearance
        k = txt.rfind(head[:12])
        k = k + len(head) if k >= 0 else -1
    art = SIDEBAR.split(txt[k:k + 2500])[0] if k >= 0 else ""
    return {"id": i, "title": head, "body": art}


def scan_day(dt, hi, ex):
    """Every headline of one day; the 暗盤 stories read in full. Cached."""
    fn = CACHE / f"{dt}.json"
    if fn.exists():
        j = json.loads(fn.read_text())
        if j.get("hi", 0) >= hi and "hits" in j:
            return j
    ymd = dt.replace("-", "")
    ids = [int(f"{ymd}{s:03d}") for s in range(1, hi)]
    res = list(zip(ids, ex.map(title, ids)))
    grey = [i for i, t in res if t and "暗盤" in t]
    j = {"date": dt, "hi": hi, "nonempty": sum(1 for _, t in res if t),
         "failed": sum(1 for _, t in res if t is None),
         "titles": {str(i): t for i, t in res if t}, "hits": [article(i) for i in grey]}
    CACHE.mkdir(parents=True, exist_ok=True)
    fn.write_text(json.dumps(j, ensure_ascii=False))
    return j


RE_PCT = re.compile(r"^[^。;%]{0,30}?(高|低|升|跌)(?:出|約|近|逾|少於|超過)?\s*(\d+(?:\.\d+)?)\s*(%|倍)")
SUFFIX = re.compile(r"[-－]?\s*[ＢＷＳＰＷBWSP]$|－ＰＦ$|-PF$")
STOP2 = {"中國", "香港", "上海", "北京", "深圳", "廣州", "國際", "新股"}


def anchors(d):
    """Where a story can name a deal: its code, its name, its short name."""
    c5, c4 = f"({int(d['code']):05d})", f"({int(d['code'])})"
    nm = SUFFIX.sub("", nf(d.get("name_cn") or "")).replace(" ", "")
    out = {c5, c4}
    if len(nm) >= 2:
        out.add(nm)
        if len(nm) >= 4:
            out.add(nm[:4])
        if nm[:2] not in STOP2:
            out.add(nm[:2])
    return out


def identity_ok(px, body_after, offer):
    """The story's own percentage, where it gives one, must come out of px/offer."""
    m = RE_PCT.search(body_after)
    if not m or not offer:
        return True, None
    stated = float(m.group(2)) * (100 if m.group(3) == "倍" else 1)
    stated = -stated if m.group(1) in ("低", "跌") else stated
    implied = 100 * (px / offer - 1)
    loose = any(q in body_after[:m.end()] for q in ("近", "逾", "約", "少於", "超過")) or m.group(3) == "倍"
    return abs(implied - stated) <= (6.0 if m.group(3) == "倍" else 2.5 if loose else 0.6), stated


def clauses(dt, hit, days, deals):
    """Every venue quote in one story, typed close / open / live, each tied to its deal."""
    body = SIDEBAR.split(hit["body"])[0]
    text = hit["title"] + " 。 " + body
    gdate = dt
    if "昨日" in body[:120] or "昨晚" in body[:120]:      # a listing-morning recap
        gdate = days[bisect.bisect_left(days, dt) - 1]
    # the deal is one that LISTS the next trading day: a spin-off story names
    # its parent first ("微創醫療(00853)分拆旗下心通醫療(02160)"), a wrap-up
    # names several; each quote belongs to the nearest listing deal before it
    # "next trading day" from the index calendar, but a day the index skipped
    # (13-Oct-2021: typhoon, no morning session, no HSI bar) still listed deals
    k = bisect.bisect_right(days, gdate)
    nxt = days[k] if k < len(days) else "9999"
    pos = []
    for c, d in deals.items():
        if not gdate < (d.get("ipo_date") or "")[:10] <= nxt:
            continue
        for a in anchors(d):
            pos += [(m.start(), c) for m in re.finditer(re.escape(a), text)]
    if not pos:
        return []
    pos.sort()

    def owner(at):
        prior = [c for p0, c in pos if p0 <= at]
        return prior[-1] if prior else pos[0][1]

    out, seen = [], set()
    off = len(hit["title"]) + 3
    for c in RE_CLAUSE.finditer(body):
        verb, px = c.group(2), float(c.group(3))
        o = RE_OFFER.search(body[c.end():c.end() + 40])
        code = owner(off + c.start())
        offer = float(o.group(1)) if o else deals[code].get("final_price")
        ok, stated = identity_ok(px, body[c.end():c.end() + 60], offer)
        out.append({"code": code, "venue": VEN[c.group(1)], "verb": verb, "px": px, "ok": ok, "stated_pct": stated,
                    "kind": "close" if verb.startswith("收") else "open" if verb.startswith("開") else "live",
                    "art_offer": float(o.group(1)) if o else None,
                    "id": hit["id"], "date": gdate, "title": hit["title"]})
        seen.add(c.end())
    # a close whose venue sits earlier in the sentence: "據輝立交易場顯示,該股
    # 暗盤價最高見257元,較招股價252元,升1.98%,收報254.8元,升1.11%"
    for c in RE_CLOSE_ANY.finditer(body):
        if c.end() in seen:
            continue
        sent = re.split(r"[。;]", body[:c.start()])[-1]
        vs = [(sent.rfind(v), v) for v in VEN if v in sent]
        if not vs:
            continue                              # no venue named: not used
        v = max(vs)[1]
        code = owner(off + c.start())
        near = body[max(0, c.start() - 80):c.end() + 40]
        o = RE_OFFER.search(near)
        offer = float(o.group(1)) if o else deals[code].get("final_price")
        ok, stated = identity_ok(float(c.group(1)), body[c.end():c.end() + 60], offer)
        out.append({"code": code, "venue": VEN[v], "verb": "收報", "px": float(c.group(1)), "ok": ok,
                    "stated_pct": stated, "kind": "close", "art_offer": float(o.group(1)) if o else None,
                    "id": hit["id"], "date": gdate, "title": hit["title"]})
    return out


def build(deals, days):
    """One record per deal: Phillip's close, else any venue's stated close; opens noted."""
    per = {}
    for fn in sorted(CACHE.glob("*.json")):
        j = json.loads(fn.read_text())
        for hit in j.get("hits") or []:
            if not hit:
                continue
            for q in clauses(j["date"], hit, days, deals):
                if q["ok"]:
                    per.setdefault(q["code"], []).append(q)
    out = []
    for code, rows in sorted(per.items()):
        d = deals[code]
        offer = d.get("final_price")
        closes = [r for r in rows if r["kind"] == "close"]
        pick = ([r for r in closes if r["venue"] == "Phillip"] or closes)
        rec = {"code": code, "name": d.get("name_cn") or d.get("name"), "offer": offer}
        if pick:
            r = max(pick, key=lambda r: r["id"])
            rec.update(grey_close=r["px"], grey_date=r["date"], grey_venue=r["venue"],
                       art_offer=r["art_offer"], title=r["title"],
                       src=URL.format(r["id"]).rstrip("x"),
                       others={f"{q['venue']} {q['kind']}": q["px"] for q in rows
                               if q is not r and q["id"] == r["id"]})
            if offer:
                rec["grey_pct"] = round(100 * (r["px"] / offer - 1), 2)
        else:
            opens = [r for r in rows if r["kind"] == "open"] or rows
            if not opens:
                continue
            r = min(opens, key=lambda r: r["id"])
            rec.update(open_only=True, grey_open=r["px"], grey_date=r["date"], grey_venue=r["venue"],
                       art_offer=r["art_offer"], title=r["title"], kind=r["kind"],
                       src=URL.format(r["id"]).rstrip("x"))
            if offer:
                rec["grey_open_pct"] = round(100 * (r["px"] / offer - 1), 2)
        out.append(rec)
    return out


def main(argv):
    deals = {d["code"]: d for d in json.loads((ROOT / "data" / "deals.json").read_text())["deals"]}
    days = [d for d, _ in json.loads((ROOT / "data" / "batches" / "index_daily.json").read_text())["^HSI"]]
    if "--parse" not in argv:
        want = [a.zfill(4) for a in argv if a[:1].isdigit()]
        tgt = [d for c, d in deals.items() if d.get("ipo_date")
               and (c in want if want else d.get("grey_pct") is None)]
        dates = {}
        for d in tgt:
            g = days[bisect.bisect_left(days, d["ipo_date"]) - 1]
            dates[g] = max(dates.get(g, 0), 1000)              # the evening: whole day
            dates[d["ipo_date"]] = max(dates.get(d["ipo_date"], 0), 260)  # listing morning
        with ThreadPoolExecutor(64) as ex:
            for n, dt in enumerate(sorted(dates, reverse=True)):
                t0 = time.time()
                j = scan_day(dt, dates[dt], ex)
                print(f"  {n + 1}/{len(dates)} {dt}: {len(j['hits'])} grey stories "
                      f"({j['failed']} failed reads, {time.time() - t0:.0f}s)", flush=True)
    if "--refetch-empty" in argv:
        # stories cached before the no-dateline fallback existed
        for fn in sorted(CACHE.glob("*.json")):
            j = json.loads(fn.read_text())
            hits = j.get("hits") or []
            if any(h and not h.get("body") for h in hits):
                j["hits"] = [article(h["id"]) if h and not h.get("body") else h for h in hits]
                fn.write_text(json.dumps(j, ensure_ascii=False))
    recs = build(deals, days)
    OUT.write_text(json.dumps({"note": "grey-market prints read from etnet's news wire by article ID; "
                                       "see ipo_lib/fetch_etnet_grey_news.py", "deals": recs},
                              ensure_ascii=False, indent=1))
    n_c = sum(1 for r in recs if "grey_close" in r)
    print(f"etnet news: {n_c} closes, {len(recs) - n_c} open-only -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1:])
