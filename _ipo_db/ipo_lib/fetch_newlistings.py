#!/usr/bin/env python3
"""Deals in their OFFERING WINDOW — prospectus posted, allotment not yet out.

The www2 "New Listings > New Listing Information > Main Board" page is a plain
server-rendered table: Stock Code · Stock Name · New Listing Announcements ·
PROSPECTUSES · Allotment Results. A row with a prospectus link and an empty
allotment cell is a deal the desk can still subscribe to — the exact moment the
whole tool exists for. Each such prospectus goes through the SAME deep-parse
machinery as the historical book (range, offer shares, cornerstone, syndicate,
lot size, financials), so an offering deal arrives in the Pipeline with real
terms and an EXPECTED P/E at the low/cap of its range.

Once its Allotment Results appear here, the normal roster path picks it up into
the Database and the pipeline dedupe retires the offering row.

Writes data/batches/newlistings.json.
"""
import json, re, sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "batches" / "newlistings.json"
PAGE = ("https://www2.hkexnews.hk/New-Listings/New-Listing-Information/"
        "Main-Board?sc_lang=en")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def rows_from_page():
    t = requests.get(PAGE, headers=UA, timeout=40).text
    soup = BeautifulSoup(t, "lxml")
    table = soup.find("table")
    out = []
    for tr in table.find_all("tr")[1:]:
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        code = tds[0].get_text(strip=True)
        if not code.isdigit():
            continue
        links = {i: [a.get("href") for a in td.find_all("a") if a.get("href")]
                 for i, td in enumerate(tds)}
        out.append({
            "code": code.zfill(4),
            "name": tds[1].get_text(" ", strip=True),
            "announcement_links": links.get(2, []),
            "prospectus_links": links.get(3, []),
            "allotment_links": links.get(4, []),
        })
    return out


def deep_parse(code, url):
    """Full prospectus parse using the exact machinery the Database uses."""
    from fetch_hkex_filings import get
    from pypdf import PdfReader
    import extract_deep as ED
    import extract_financials as EF
    import extract_profiles as EP

    key = f"newlist_{code}_{url.rsplit('/', 1)[-1]}"
    tfile = ROOT / "scrape" / "text_cache" / (key + ".txt")
    if not tfile.exists():
        blob = get(url, binary=True)
        if not blob or blob[:4] != b"%PDF":
            return {}
        pdf = ROOT / "scrape" / "pdf_cache" / (key + ".pdf")
        pdf.write_bytes(blob)
        try:
            r = PdfReader(str(pdf))
            tfile.write_text("\n".join((p.extract_text() or "")
                                       for p in r.pages[:400]), errors="ignore")
        except Exception:
            return {}
    txt = tfile.read_text(errors="ignore")
    if len(txt) < 20000:
        return {"parse_note": "prospectus text too thin (scanned?)"}
    parsed = {}
    syn = ED.parse_syndicate(txt) or {}
    for k in ("sponsors", "bookrunners"):
        if syn.get(k):
            parsed[k] = syn[k]
    cs = ED.parse_cornerstone(txt, is_allotment=False) or {}
    for k in ("cornerstone_pct", "cornerstone_amt_m", "cornerstone_amt_ccy",
              "cornerstone_investors"):
        if cs.get(k) is not None:
            parsed[k] = cs[k]
    flat = re.sub(r"\s+", " ", txt)
    m = re.search(r"Offer\s+Price[^.]{0,120}?HK\$([\d.]+)[^.]{0,60}?"
                  r"(?:to|and|–|-)\s*HK\$([\d.]+)", flat)
    if m:
        lo, hi = sorted([float(m.group(1)), float(m.group(2))])
        parsed["range_lo"], parsed["range_hi"] = lo, hi
    else:
        # cap-only pricing (the common A+H shape): "Maximum Offer Price of HK$X"
        m = re.search(r"Maximum\s+(?:Public\s+)?Offer\s+Price[^.]{0,80}?HK\$([\d.]+)", flat, re.I)
        if m:
            parsed["range_hi"] = float(m.group(1))
            parsed["range_note"] = "maximum price only (final struck at or below)"
    m = re.search(r"(?:board\s+lot|lot\s+size)\s+of\s+([\d,]+)\s+(?:H\s+)?Shares", flat, re.I)
    if m:
        parsed["lot_size"] = int(m.group(1).replace(",", ""))
    m = re.search(r"Global\s+Offering[^.]{0,140}?([\d,]{6,})\s+(?:H\s+)?(?:Offer\s+)?Shares",
                  flat)
    if m:
        parsed["offer_shares"] = float(m.group(1).replace(",", ""))
    for pat, key2 in ((r"market\s+capitali[sz]ation[^.]{0,160}?HK\$([\d,.]+)\s*(million|billion)"
                       r"[^.]{0,80}?HK\$([\d,.]+)\s*(million|billion)", "mktcap_range"),):
        m = re.search(pat, flat, re.I)
        if m:
            def mval(v, u):
                return float(v.replace(",", "")) * (1000 if u.lower() == "billion" else 1)
            a, b = mval(m.group(1), m.group(2)), mval(m.group(3), m.group(4))
            parsed["mktcap_lo_hkdm"], parsed["mktcap_hi_hkdm"] = sorted([a, b])
    fclean = EF.clean_text(txt)
    rev, _, _ = EF.series_from(fclean, EF.REV_LINE)
    ni, _, _ = EF.series_from(fclean, EF.NI_LINE)
    if not ni:
        ni, _, _ = EF.series_from_flat(re.sub(r"\s+", " ", fclean), EF.FLAT_LABELS_NI)
    if not rev:
        rev, _, _ = EF.series_from_flat(re.sub(r"\s+", " ", fclean), EF.FLAT_LABELS_REV)
    cur = EF.currency_of(fclean)
    fxm = {"RMB": 1.10, "HK$": 1.0, "US$": 7.80}.get(cur or "", None)
    for keyn, series in (("rev_latest", rev), ("ni_latest", ni)):
        if series and fxm and len(series) <= 6:
            idx = 2 if len(series) >= 3 else len(series) - 1
            parsed[keyn] = round(series[idx] * fxm / 1000, 1)
    ov = EP.find_overview(txt)
    if ov:
        from textclip import clip_sentence
        parsed["business_overview"] = clip_sentence(ov, 620, hard=760)
    # An offering-window deal must land in the same taxonomy as the book it is
    # compared against, otherwise its card reads "not yet classified" and the
    # subsector-first scorer falls back to sector matching for no reason.
    import auto_classify as AC
    sub = AC.classify_text(" ".join(filter(None, [ov, parsed.get("industry_en"), code])))
    if sub:
        parsed["subsector"] = sub
        parsed["subsector_src"] = "keyword classifier (provisional)"
        # sector comes from the taxonomy the subsector lives in — without it the
        # card reads "sector: None" and the screener loses its sector fallback
        import json as _j
        tax = _j.loads((ROOT / "data" / "taxonomy.json").read_text())
        for _sec, _subs in tax["sectors"].items():
            if any(x["label"] == sub for x in _subs):
                parsed["sector"] = _sec
                break
    # USE OF PROCEEDS — where the money goes. Actual filing shape:
    # "Approximately 50.0% or HK$1,570.6 million will be used to enhance..."
    # The section title also appears in the contents page, so scan every
    # occurrence and keep the first that yields >=2 allocation bullets.
    UP = re.compile(r"[Aa]pproximately\s+(\d{1,2}(?:\.\d)?)%"
                    r"(?:\s*,?\s*or\s+(?:HK|US)\$[\d,.]+\s*(?:million|billion))?"
                    r"[\s,]*(?:will\s+be\s+(?:used|applied)\s+)?(?:for|to(?:wards)?)\s+"
                    r"([a-z][^.;•]{8,110})")
    for m0 in re.finditer(r"USE OF PROCEEDS", flat, re.I):
        sec = flat[m0.start(): m0.start() + 6000]
        from textclip import clip_phrase
        buckets = [f"~{m.group(1)}% {clip_phrase(m.group(2), 96)}"
                   for m in UP.finditer(sec)][:4]
        if len(buckets) >= 2:
            parsed["use_of_proceeds"] = " · ".join(buckets)
            mnp = re.search(r"net\s+proceeds\s+of\s+approximately\s+HK\$([\d,.]+)\s*million",
                            sec, re.I)
            if mnp:
                parsed["expected_net_hkdm"] = float(mnp.group(1).replace(",", ""))
            break
    # expected P/E and P/S across the price range — the number the bet needs
    ni_v, rev_v = parsed.get("ni_latest"), parsed.get("rev_latest")
    mlo, mhi = parsed.get("mktcap_lo_hkdm"), parsed.get("mktcap_hi_hkdm")
    if mlo and mhi:
        if ni_v and ni_v > 0:
            parsed["pe_expected_lo"] = round(mlo / ni_v, 1)
            parsed["pe_expected_hi"] = round(mhi / ni_v, 1)
        elif ni_v is not None:
            parsed["pe_note"] = "n/m — loss-making (use P/S)"
        if rev_v and rev_v > 0:
            parsed["ps_expected_lo"] = round(mlo / rev_v, 1)
            parsed["ps_expected_hi"] = round(mhi / rev_v, 1)
    return parsed


def main():
    rows = rows_from_page()
    offering = [r for r in rows if r["prospectus_links"] and not r["allotment_links"]]
    print(f"{len(rows)} rows on the New Listings page; "
          f"{len(offering)} in the offering window", flush=True)
    # AAStocks EN page for THESE codes (timetable, lot, industry) — offering
    # names are not in the historical roster, so fetch them here directly
    try:
        from fetch_aastocks import fetch_english
        fetch_english([r["code"] for r in offering])
    except Exception as e:
        print(f"  AAStocks EN for offering codes skipped: {e}")
    aa = {}
    p = ROOT / "data" / "batches" / "aastocks_deal_en.json"
    if p.exists():
        aa = {r["code"]: r for r in json.loads(p.read_text())["deals"]}
    out = []
    for r in offering:
        rec = dict(r)
        rec["status"] = "OFFERING NOW"
        try:
            rec.update(deep_parse(r["code"], r["prospectus_links"][0]))
        except Exception as e:
            rec["error"] = str(e)[:120]
        en = aa.get(r["code"], {})
        for k_src, k_dst in (("offer_period", "offer_period"),
                             ("listing_date_aa", "listing_date"),
                             ("lot_size_aa", "lot_size"),
                             ("industry_en", "industry_en")):
            if en.get(k_src) and not rec.get(k_dst):
                rec[k_dst] = en[k_src]
        # A+H applicant: capture the LIVE A price + FX at build time so the
        # dashboard can show an implied H pricing zone off peer discounts
        press = {}
        try:
            pj = json.loads((ROOT / "data" / "batches" / "press_sizes.json").read_text())
            low = (r.get("name") or "").lower()
            press = next((x for x in pj["results"] if x["match"] in low), {})
        except Exception:
            pass
        if press.get("a_share_code"):
            rec["a_share_code"] = press["a_share_code"]
            try:
                num, venue = press["a_share_code"].split(".")
                sym = ("sz" if venue == "SZ" else "sh") + num
                q = requests.get(f"https://qt.gtimg.cn/q={sym}", headers=UA, timeout=20).text
                f = q.split("~")
                px = float(f[3])
                rec["a_price_now"] = px
                # field 45 = total market cap (亿 CNY), 47 = P/E TTM — the
                # A market's own valuation, which is what an A+H offering
                # actually prices against
                try:
                    rec["a_mktcap_bn_cny"] = round(float(f[45]) / 10, 2)   # 亿 -> bn
                    rec["a_pe_ttm"] = float(f[47])
                except (IndexError, ValueError):
                    pass
                fxq = requests.get("https://qt.gtimg.cn/q=whHKDCNY", headers=UA, timeout=20).text
                rec["fx_now"] = round(1.0 / float(fxq.split("~")[3]), 4)
                # H at the cap vs the live A line, and the implied multiple
                if rec.get("range_hi") and rec.get("fx_now"):
                    a_hkd = px * rec["fx_now"]
                    rec["h_cap_vs_a_pct"] = round(100 * (rec["range_hi"] / a_hkd - 1), 1)
                    if rec.get("a_pe_ttm"):
                        rec["pe_at_h_cap"] = round(
                            rec["a_pe_ttm"] * rec["range_hi"] / a_hkd, 1)
            except Exception as e:
                rec["a_quote_note"] = str(e)[:60]
        if rec.get("offer_period"):
            # "2026-08-15 - 2026-08-20" -> the close date is the tail
            close = rec["offer_period"].strip()[-10:]
            rec["status"] = f"OFFERING — closes {close}"
        out.append(rec)
        got = [k for k in ("range_lo", "range_hi", "cornerstone_pct", "sponsors",
                           "ni_latest", "pe_expected_lo", "lot_size") if rec.get(k)]
        print(f"  {r['code']} {r['name'][:30]:30s} parsed: {', '.join(got) or 'links only'}",
              flush=True)
    # NEVER-REGRESS: a re-parse can fail (source page changed, PDF fetch
    # blocked) and must not overwrite a richer cached record with an empty one.
    # Field-level backfill from the previous batch; a fresh non-empty value
    # still wins.
    if OUT.exists():
        try:
            prev = {r.get("code") or r.get("name"): r
                    for r in json.loads(OUT.read_text())["deals"]}
        except Exception:
            prev = {}
        for rec in out:
            old = prev.get(rec.get("code") or rec.get("name"))
            if not old:
                continue
            for k, v in old.items():
                if rec.get(k) in (None, "", []) and v not in (None, "", []):
                    rec[k] = v
    OUT.write_text(json.dumps(
        {"batch": "newlistings", "source": "www2 New Listings Main Board",
         "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(out), "deals": out}, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {len(out)} offering-window deals")


if __name__ == "__main__":
    main()
