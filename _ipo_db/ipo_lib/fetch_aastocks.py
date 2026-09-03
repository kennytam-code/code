#!/usr/bin/env python3
"""AAStocks per-deal IPO page: syndicate, market cap at listing, cornerstones.

The prospectus parse leaves ~90 deals without a sponsor and ~140 without a
market cap, and its cornerstone-investor lists are damaged by PDF table
extraction. AAStocks publishes the same facts as clean labelled fields:

    每手股數 / 招股價 / 上市市值 (HK$, a range across the price range)
    保薦人      sponsors, separated by  、
    包銷商      the full underwriting syndicate, one per line
    機構性投資者 cornerstone/institutional investors: name, type, amount

The page is rendered by JavaScript, so requests() sees only a shell and this
uses playwright. That makes it a LOCAL-ONLY enrichment step: the desk keeps the
prospectus parser (which needs nothing but requests) for new deals, and picks
these fields up the next time the workbook is rebuilt here.

Writes data/batches/aastocks_deal.json. Resumable — re-running only fetches
codes not already stored.
"""
import json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "batches" / "aastocks_deal.json"
OUT_EN = ROOT / "data" / "batches" / "aastocks_deal_en.json"
URL = ("https://www.aastocks.com/tc/stocks/market/ipo/upcomingipo/"
       "company-summary?symbol={sym}#info")
URL_EN = ("https://www.aastocks.com/en/stocks/market/ipo/upcomingipo/"
          "company-summary?symbol={sym}#info")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

MONEY = re.compile(r"^(.*?)\s+(公司|基金|個人|其他|信託)\s+(美元|港元|人民幣)([\d,.]+)\s*(百萬|億)?\s*$")
FX_TO_HKD = {"港元": 1.0, "美元": 7.80, "人民幣": 1.10}
MULT = {"百萬": 1e6, "億": 1e8, None: 1.0, "": 1.0}
# section headers that terminate a list block
STOP = ("收款銀行", "eIPO", "孖展供應", "機構性投資者", "行業相關公司", "最近新股",
        "同期新股", "保薦人過往表現", "招股日程", "基本公司資料", "招股資料", "銀行 地區 分行")


def field(text, label):
    m = re.search(rf"^{re.escape(label)}\s*(.*)$", text, re.M)
    v = (m.group(1).strip() if m else "") or None
    return None if v in ("N/A", "-", "--", "N/A%") else v


def block(text, label):
    """Lines belonging to a multi-line labelled block (e.g. 包銷商)."""
    m = re.search(rf"^{re.escape(label)}\s*(.*)$", text, re.M)
    if not m:
        return []
    out = []
    if m.group(1).strip():
        out.append(m.group(1).strip())
    for line in text[m.end():].split("\n")[1:]:
        s = line.strip()
        if not s or any(s.startswith(k) for k in STOP):
            break
        if re.match(r"^[一-鿿 A-Za-z0-9()（）．.,\-&'’]+$", s) and len(s) < 60:
            out.append(s)
        else:
            break
    return out


def parse_investors(text):
    """機構性投資者 table -> [{name, kind, ccy, amount_m, amount_hkdm}]."""
    m = re.search(r"^名稱\s+類別\s+總額\s*$", text, re.M)
    if not m:
        return []
    rows = []
    for line in text[m.end():].split("\n")[1:]:
        s = line.strip()
        if not s:
            continue
        if any(s.startswith(k) for k in STOP) or s.startswith("公司名稱"):
            break
        mm = MONEY.match(s)
        if not mm:
            if len(rows) and not re.search(r"[\d]", s):
                break
            continue
        name, kind, ccy, amt, unit = mm.groups()
        try:
            val = float(amt.replace(",", ""))
        except ValueError:
            continue
        native = val * MULT.get(unit or "", 1.0)
        rows.append({"name": name.strip(), "kind": kind, "ccy": ccy,
                     "amount_native": native,
                     "amount_hkdm": round(native * FX_TO_HKD.get(ccy, 1.0) / 1e6, 2)})
    return rows


def parse_page(text):
    rec = {}
    t = re.sub(r"[ \t]+", " ", text)
    t = re.sub(r"\n{2,}", "\n", t)
    # keep only the deal's own section: it starts at 招股日程 and ends before
    # the site-wide comparison tables
    i = t.find("招股日程")
    j = t.find("行業相關公司")
    body = t[i: j if j > i else len(t)] if i >= 0 else t

    mc = field(body, "上市市值")
    if mc:
        nums = [float(x.replace(",", "")) for x in re.findall(r"[\d,]{7,}", mc)]
        if nums:
            rec["mktcap_listing_lo_hkdm"] = round(min(nums) / 1e6, 1)
            rec["mktcap_listing_hi_hkdm"] = round(max(nums) / 1e6, 1)
    px = field(body, "招股價")
    if px:
        try:
            rec["offer_price_aa"] = float(re.findall(r"[\d.]+", px)[0])
        except (IndexError, ValueError):
            pass
    lot = field(body, "每手股數")
    if lot and lot.replace(",", "").isdigit():
        rec["lot_size_aa"] = int(lot.replace(",", ""))
    sp = field(body, "保薦人")
    if sp:
        names = [s.strip() for s in re.split(r"[、,，]", sp) if s.strip() and s.strip() != "N/A"]
        if names:
            rec["sponsors_cn"] = names
    uw = [u for u in block(body, "包銷商") if u != "N/A"]
    if uw:
        rec["underwriters_cn"] = uw
    ind = field(body, "行業")
    if ind:
        rec["industry_aa"] = ind
    bg = field(body, "背景")
    if bg and bg != "N/A":
        rec["background_aa"] = bg
    hkp = field(body, "香港配售股份數目3") or field(body, "香港配售股份數目")
    if hkp:
        mm = re.search(r"\(([\d.]+)%\)", hkp)
        if mm:
            rec["hk_tranche_pct_aa"] = float(mm.group(1))
    inv = parse_investors(t)
    if inv:
        rec["cornerstone_aa"] = inv
        rec["cornerstone_aa_total_hkdm"] = round(sum(x["amount_hkdm"] for x in inv), 1)
    ld = field(body, "上市日期")
    if ld:
        rec["listing_date_aa"] = ld.replace("/", "-")
    return rec


# ---------------------------------------------------------- ENGLISH site ----
# Same page, /en/ path, English labels throughout — the desk wants every name
# in English (the CN scrape stays on disk as a cross-check, never displayed).
EN_STOP = ("Payee Bank", "eIPO", "Margin Supplier", "Institutional Investors",
           "Industry Peer", "Recent IPO", "Same-period", "Sponsor Performance",
           "IPO Timetable", "Basic Company Information", "IPO Info",
           "White Application Form", "Name Type Total", "Sitemap")
EN_MONEY = re.compile(r"^(.*?)\s+(Company|Fund|Individual|Trust|Others?)\s+"
                      r"(USD|HKD|RMB|CNY)\s?([\d,.]+)\s*(M|B|K)?\s*$")
EN_FX = {"HKD": 1.0, "USD": 7.80, "RMB": 1.10, "CNY": 1.10}
EN_MULT = {"M": 1e6, "B": 1e9, "K": 1e3, None: 1.0, "": 1.0}


def _en_field(text, label):
    m = re.search(rf"^{re.escape(label)}\s*(.*)$", text, re.M)
    v = (m.group(1).strip() if m else "") or None
    return None if v in ("N/A", "-", "--") else v


def _en_block(text, label):
    m = re.search(rf"^{re.escape(label)}\s*(.*)$", text, re.M)
    if not m:
        return []
    out = [s.strip() for s in m.group(1).split(",") if s.strip()]
    for line in text[m.end():].split("\n")[1:]:
        s = line.strip()
        if not s or any(s.startswith(k) for k in EN_STOP):
            break
        if re.match(r"^[A-Z][A-Za-z0-9&\-\.,'() ]+$", s) and len(s) < 70:
            out.append(s)
        else:
            break
    return [x for x in out if x and x != "N/A"]


def parse_page_en(text):
    rec = {}
    t = re.sub(r"[ \t]+", " ", text)
    t = re.sub(r"\n{2,}", "\n", t)
    i = t.find("IPO Timetable")
    j = t.find("Industry Peer")
    if j < 0:
        j = t.find("Recent IPO")
    body = t[i: j if j > i else len(t)] if i >= 0 else t
    mc = _en_field(body, "Market Cap")
    if mc:
        nums = [float(x.replace(",", "")) for x in re.findall(r"[\d,]{7,}", mc)]
        if nums:
            rec["mktcap_listing_lo_hkdm"] = round(min(nums) / 1e6, 1)
            rec["mktcap_listing_hi_hkdm"] = round(max(nums) / 1e6, 1)
    px = _en_field(body, "Offer Price")
    if px:
        try:
            rec["offer_price_aa"] = float(re.findall(r"[\d.]+", px)[0])
        except (IndexError, ValueError):
            pass
    lot = _en_field(body, "Lot Size")
    if lot and lot.replace(",", "").isdigit():
        rec["lot_size_aa"] = int(lot.replace(",", ""))
    sp = _en_field(body, "Sponsor(s)")
    if sp:
        names = [s.strip() for s in re.split(r",(?![^()]*\))", sp) if s.strip()]
        if names:
            rec["sponsors_en"] = names[:6]
    uw = _en_block(body, "Underwriter(s)")
    if uw:
        rec["underwriters_en"] = uw[:12]
    ind = _en_field(body, "Industry")
    if ind:
        rec["industry_en"] = ind
    bg = _en_field(body, "Background")
    if bg:
        rec["background_en"] = bg
    for lbl, key in (("Offer Period", "offer_period"), ("Listing Date", "listing_date_aa"),
                     ("Price-set Date", "price_set_date")):
        v = _en_field(body, lbl)
        if v:
            rec[key] = v.replace("/", "-")
    hkp = _en_field(body, "No. of HK Offer Shares3") or _en_field(body, "No. of HK Offer Shares")
    if hkp:
        mm = re.search(r"\(([\d.]+)%\)", hkp)
        if mm:
            rec["hk_tranche_pct_aa"] = float(mm.group(1))
    # Institutional Investors table (EN): "Name Type Total" then rows
    m = re.search(r"^Name\s+Type\s+Total\s*$", t, re.M)
    if m:
        rows = []
        for line in t[m.end():].split("\n")[1:]:
            s = line.strip()
            if not s:
                continue
            if any(s.startswith(k) for k in EN_STOP) or s.startswith("Name "):
                break
            mm = EN_MONEY.match(s)
            if not mm:
                if rows and not re.search(r"\d", s):
                    break
                continue
            name, kind, ccy, amt, unit = mm.groups()
            try:
                val = float(amt.replace(",", ""))
            except ValueError:
                continue
            rows.append({"name": name.strip(), "kind": kind, "ccy": ccy,
                         "amount_hkdm": round(val * EN_MULT.get(unit or "", 1.0)
                                              * EN_FX.get(ccy, 1.0) / 1e6, 2)})
        if rows:
            rec["cornerstone_aa"] = rows
            rec["cornerstone_aa_total_hkdm"] = round(sum(x["amount_hkdm"] for x in rows), 1)
    return rec


def fetch_english(codes):
    prev = {}
    if OUT_EN.exists():
        prev = {r["code"]: r for r in json.loads(OUT_EN.read_text())["deals"]}
    todo = [c for c in codes if c not in prev]
    print(f"EN: {len(prev)} cached, fetching {len(todo)}", flush=True)
    if todo:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=UA)
            page.set_default_timeout(45000)
            for i, code in enumerate(todo):
                rec = {"code": code}
                try:
                    page.goto(URL_EN.format(sym=code.zfill(5)),
                              wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(3000)
                    rec.update(parse_page_en(page.inner_text("body")))
                except Exception as e:
                    rec["error"] = str(e)[:90]
                prev[code] = rec
                if (i + 1) % 10 == 0:
                    print(f"  {i+1}/{len(todo)} | sponsors "
                          f"{sum(1 for r in prev.values() if r.get('sponsors_en'))}", flush=True)
                    _write_en(prev)
                time.sleep(0.4)
            browser.close()
    _write_en(prev)
    print(f"wrote {OUT_EN}: sponsors "
          f"{sum(1 for r in prev.values() if r.get('sponsors_en'))} | underwriters "
          f"{sum(1 for r in prev.values() if r.get('underwriters_en'))} | industry "
          f"{sum(1 for r in prev.values() if r.get('industry_en'))} | cornerstones "
          f"{sum(1 for r in prev.values() if r.get('cornerstone_aa'))}")


def _write_en(prev):
    OUT_EN.write_text(json.dumps(
        {"batch": "aastocks_deal_en", "source": "aastocks.com /en/ IPO company-summary",
         "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(prev), "deals": list(prev.values())}, ensure_ascii=False, indent=1))


PL_URL = ("https://www.aastocks.com/tc/stocks/market/ipo/upcomingipo/"
          "profit-loss?symbol={sym}#info")
PL_FX = {"人民幣": 1.10, "港元": 1.0, "港幣": 1.0, "美元": 7.80}
PL_UNIT = {"千": 1e3, "百萬": 1e6, "萬": 1e4, "億": 1e8}


def parse_pl(text, listing_date):
    """The IPO subsite's 損益表: pick the last FY that ENDED BEFORE listing.

    The table shows the five most recent fiscal years — for older listings the
    pre-IPO year has scrolled out, and then this source honestly returns
    nothing rather than a post-IPO figure dressed up as an at-IPO one.
    """
    t = re.sub(r"[ \t]+", " ", text)
    m = re.search(r"綜合損益表[^\n]*\n(.*?)主要項目", t, re.S)
    if not m:
        return {}
    body = m.group(1)
    years = re.search(r"^年份\s+(.+)$", body, re.M)
    ccy = re.search(r"^貨幣\s+(.+)$", body, re.M)
    unit = re.search(r"^單位\s+(.+)$", body, re.M)
    if not years:
        return {}
    ys = years.group(1).split()
    fx = PL_FX.get((ccy.group(1).split() or ["?"])[0] if ccy else "?", None)
    mult = PL_UNIT.get((unit.group(1).split() or ["?"])[0] if unit else "?", None)
    if fx is None or mult is None:
        return {}

    def row(label):
        mm = re.search(rf"^{label}\s+(.+)$", body, re.M)
        if not mm:
            return []
        out = []
        for tok in mm.group(1).split():
            tok = tok.replace(",", "")
            try:
                out.append(float(tok))
            except ValueError:
                out.append(None)
        return out

    rev, ni = row("營業額"), row("股東應佔溢利")
    # pick the newest FY column that closed before the listing date
    pick = None
    for k, y in enumerate(ys):
        mm = re.match(r"(\d{4})/(\d{2})", y)
        if not mm:
            continue
        fy_end = f"{mm.group(1)}-{mm.group(2)}-28"
        if fy_end <= listing_date:
            pick = k
            break                       # columns are newest-first
    if pick is None:
        return {"pl_note": "pre-IPO fiscal year not in AAStocks' 5-year window"}
    out = {"fin_year_aa": ys[pick]}
    if pick < len(rev) and rev[pick] is not None:
        out["rev_latest_aa_hkdm"] = round(rev[pick] * mult * fx / 1e6, 1)
    if pick < len(ni) and ni[pick] is not None:
        out["ni_latest_aa_hkdm"] = round(ni[pick] * mult * fx / 1e6, 1)
    return out


def fetch_financials(codes):
    """Second pass: only the deals whose NI/revenue the prospectus never gave up."""
    out_path = ROOT / "data" / "batches" / "aastocks_pl.json"
    prev = {}
    if out_path.exists():
        prev = {r["code"]: r for r in json.loads(out_path.read_text())["deals"]}
    deals = {d["code"]: d for d in
             json.loads((ROOT / "data" / "deals.json").read_text())["deals"]}
    todo = [c for c in codes if c not in prev]
    print(f"P&L: {len(prev)} cached, fetching {len(todo)}", flush=True)
    if todo:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=UA)
            for i, code in enumerate(todo):
                rec = {"code": code}
                try:
                    page.goto(PL_URL.format(sym=code.zfill(5)),
                              wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(3000)
                    rec.update(parse_pl(page.inner_text("body"),
                                        (deals[code].get("ipo_date") or "9999")[:10]))
                except Exception as e:
                    rec["error"] = str(e)[:90]
                prev[code] = rec
                if (i + 1) % 10 == 0:
                    got = sum(1 for r in prev.values() if r.get("ni_latest_aa_hkdm") is not None)
                    print(f"  {i+1}/{len(todo)} | NI filled {got}", flush=True)
                    out_path.write_text(json.dumps(
                        {"batch": "aastocks_pl", "deals": list(prev.values())},
                        ensure_ascii=False, indent=1))
                time.sleep(0.4)
            browser.close()
    out_path.write_text(json.dumps(
        {"batch": "aastocks_pl", "source": "aastocks IPO 損益表 (pre-IPO FY only)",
         "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(prev), "deals": list(prev.values())}, ensure_ascii=False, indent=1))
    print(f"wrote {out_path}: NI "
          f"{sum(1 for r in prev.values() if r.get('ni_latest_aa_hkdm') is not None)} | rev "
          f"{sum(1 for r in prev.values() if r.get('rev_latest_aa_hkdm') is not None)} | "
          f"window-missed {sum(1 for r in prev.values() if r.get('pl_note'))}")


def fetch_planned():
    """擬上市新股 — the planned-IPO watchlist: Chinese names + industry tags.

    A monthly rumor roll, so no sizes or sponsors — but it is the one public
    place that pairs the pipeline's ENGLISH applicants with their Chinese names
    and an industry word (梅卡曼德機器人 = Mech-Mind, 希音國際 = Shein), which the
    Pipeline tab and watch queue otherwise lack entirely.
    """
    out_path = ROOT / "data" / "batches" / "aastocks_planned.json"
    from playwright.sync_api import sync_playwright
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA)
        page.goto("https://www.aastocks.com/tc/stocks/market/ipo/plannedipo.aspx",
                  wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3500)
        text = re.sub(r"[ \t]+", " ", page.inner_text("body"))
        browser.close()
    month = None
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    for i, ln in enumerate(lines):
        m = re.match(r"綜合(\d+)月份消息", ln)
        if m:
            month = m.group(1)
            continue
        # entries come in (name, industry) line pairs after a month header
        if month and i + 1 < len(lines) and re.search(r"[一-鿿]|Limited|Company", ln) \
                and not re.match(r"綜合", lines[i + 1]) \
                and len(lines[i + 1]) < 20 and re.search(r"[一-鿿]", lines[i + 1]) \
                and not re.search(r"股份有限公司|有限公司|Limited|Company", lines[i + 1]):
            rows.append({"name": ln, "industry": lines[i + 1], "month": month})
    out_path.write_text(json.dumps(
        {"batch": "aastocks_planned",
         "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(rows), "rows": rows}, ensure_ascii=False, indent=1))
    print(f"wrote {out_path}: {len(rows)} planned-IPO names")


def main():
    codes = [d["code"] for d in
             json.loads((ROOT / "data" / "deals.json").read_text())["deals"]]
    if len(sys.argv) > 1 and sys.argv[1] == "english":
        try:
            import playwright  # noqa: F401
        except ImportError:
            print("  playwright not installed — skipping the EN re-scrape.")
            return
        want = codes if len(sys.argv) < 3 else [c.zfill(4) for c in sys.argv[2].split(",")]
        fetch_english(want)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "planned":
        try:
            import playwright  # noqa: F401
        except ImportError:
            print("  playwright not installed — skipping the planned-IPO scrape.")
            return
        fetch_planned()
        return
    if len(sys.argv) > 1 and sys.argv[1] == "financials":
        deals = json.loads((ROOT / "data" / "deals.json").read_text())["deals"]
        want = [d["code"] for d in deals
                if d.get("ni_latest") is None or d.get("rev_latest") is None]
        try:
            import playwright  # noqa: F401
        except ImportError:
            print("  playwright not installed — skipping the AAStocks P&L pass.")
            return
        fetch_financials(want)
        return
    if len(sys.argv) > 1 and sys.argv[1] != "--all":
        codes = [c.zfill(4) for c in sys.argv[1].split(",")]
    prev = {}
    if OUT.exists():
        prev = {r["code"]: r for r in json.loads(OUT.read_text())["deals"]}
    todo = [c for c in codes if c not in prev]
    print(f"{len(prev)} cached, fetching {len(todo)}", flush=True)
    if not todo:
        return

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        # These pages are rendered by JavaScript, so there is no requests-only
        # path. The desk does not have playwright and does not need it: the
        # prospectus parser covers new deals, and these columns arrive with the
        # next workbook built on the machine that does.
        print("  playwright not installed — skipping the AAStocks enrichment. "
              "Existing values in aastocks_deal.json are kept.")
        return
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA)
        page.set_default_timeout(45000)
        for i, code in enumerate(todo):
            rec = {"code": code}
            try:
                page.goto(URL.format(sym=code.zfill(5)),
                          wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3200)
                rec.update(parse_page(page.inner_text("body")))
            except Exception as e:
                rec["error"] = str(e)[:90]
            prev[code] = rec
            if (i + 1) % 10 == 0:
                got = sum(1 for r in prev.values() if r.get("sponsors_cn"))
                print(f"  {i+1}/{len(todo)} | sponsors {got} | "
                      f"cornerstones {sum(1 for r in prev.values() if r.get('cornerstone_aa'))}",
                      flush=True)
                _write(prev)
            time.sleep(0.4)
        browser.close()
    _write(prev)
    n = len(prev)
    print(f"wrote {OUT}: {n} codes | sponsors "
          f"{sum(1 for r in prev.values() if r.get('sponsors_cn'))} | underwriters "
          f"{sum(1 for r in prev.values() if r.get('underwriters_cn'))} | mktcap "
          f"{sum(1 for r in prev.values() if r.get('mktcap_listing_lo_hkdm'))} | cornerstone "
          f"{sum(1 for r in prev.values() if r.get('cornerstone_aa'))}")


def _write(prev):
    OUT.write_text(json.dumps(
        {"batch": "aastocks_deal", "source": "aastocks.com IPO company-summary",
         "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(prev), "deals": list(prev.values())}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
