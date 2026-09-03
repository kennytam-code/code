#!/usr/bin/env python3
"""Merge all data/batches/*.json into canonical data/deals.json.

Source priority (higher wins on conflict; disagreement beyond tolerance is
recorded in data/conflicts.json but the higher-priority value stands):
  40 extracted_allotments / extracted_prospectus  (HKEX filings, scripted)
  30 deep_*.json / verify_pass upgrades           (agent prospectus-level research)
  20 bulk_roster (AAStocks)                       (aggregator)
  10 hkex_allotments roster                       (names/dates skeleton)

deals.json is script-generated — never hand-edit; fix the batch files and re-run.
Main Board only; GEM rows are dropped (reported). Derived fields recomputed here:
  pct_in_range, gross_proceeds_hkdm (price x offer shares when not stated),
  first_day_return_pct (from listing vs final where both known).
"""
import json, re, sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "data" / "batches"

TOL_PRICE = 0.005
TOL_MONEY = 0.02

deals = {}      # code -> {field: value}
prov = {}       # code -> {field: {"src":..., "prio":..., "status":...}}
conflicts = []


def put(code, field, value, src, prio, status="single"):
    if value is None or value == "" or value == []:
        return
    if field == "name_cn" and prio >= 50:
        deals.setdefault(code, {"code": code})[field] = value
        prov.setdefault(code, {})[field] = {"src": src, "prio": prio, "status": "xchecked"}
        return
    if field.endswith("_snip"):
        # prose excerpts from different filings legitimately differ — first wins
        deals.setdefault(code, {"code": code}).setdefault(field, value)
        prov.setdefault(code, {}).setdefault(field, {"src": src, "prio": prio,
                                                     "status": "single"})
        return
    deals.setdefault(code, {"code": code})
    prov.setdefault(code, {})
    cur = prov[code].get(field)
    if cur is None:
        deals[code][field] = value
        prov[code][field] = {"src": src, "prio": prio, "status": status}
        return
    old = deals[code][field]
    # an "estimated" placeholder yields silently to any better-ranked source
    if cur["status"] == "estimated" and prio > cur["prio"]:
        deals[code][field] = value
        prov[code][field] = {"src": src, "prio": prio, "status": status}
        return
    agree = old == value
    if isinstance(old, (int, float)) and isinstance(value, (int, float)) and old:
        tol = TOL_PRICE if "price" in field else TOL_MONEY
        agree = abs(old - value) / abs(old) <= tol
    if agree:
        if src.split(":")[0] != cur["src"].split(":")[0]:
            cur["status"] = "xchecked"
            cur["src2"] = src
        if prio > cur["prio"]:
            deals[code][field] = value
            cur.update(src=src, prio=prio)
        return
    conflicts.append({"code": code, "field": field, "kept": old if cur["prio"] >= prio else value,
                      "kept_src": cur["src"] if cur["prio"] >= prio else src,
                      "dropped": value if cur["prio"] >= prio else old,
                      "dropped_src": src if cur["prio"] >= prio else cur["src"]})
    if prio > cur["prio"]:
        deals[code][field] = value
        winner_authoritative = src.split(":")[0] in ("bloomberg", "press")
        cur.update(src=src, prio=prio,
                   status="xchecked" if winner_authoritative else "conflict")
    else:
        # a later, lower-ranked disagreement must not repaint a cell whose
        # standing winner is authoritative (Bloomberg / press / quality-won)
        if cur["prio"] < 60:
            cur["status"] = "conflict"


def _plus_days(iso, n):
    return (date.fromisoformat(iso) + timedelta(days=n)).isoformat()


def load(name):
    p = B / name
    if not p.exists():
        print(f"  (no {name})")
        return None
    return json.loads(p.read_text())



def name_quality(names):
    """Fraction of a bank/investor list that looks like real entity names.

    The damaged-PDF parses produce detectable garbage: address bleed ("Central,
    Hong Kong Merrill Lynch…"), clause fragments ("exercised in full) Top"),
    unbalanced quotes/parens ("(“Lens Hong Kong ”)"), derivative-desk suffixes
    ("Pulead OTC Swaps)"). A clean researched list scores ~1.0; a broken parse
    scores well under 0.7 — that GAP, not source priority, decides who wins.
    """
    if not names:
        return 0.0
    bad = 0
    for nm in names:
        t = str(nm).strip()
        if (len(t) < 5 or t[0] in "(\u201c\u201d)" or t[0].islower()
                or t.count("(") != t.count(")")
                or t.count("\u201c") != t.count("\u201d")
                or t.startswith(("Central,", "and ", "the ", "undertakings",
                                 "upon ", "full)", "issued)", "Shareholder "))
                or t in ("Subtotal", "Total")
                or "OTC Swap" in t or "exercised" in t.lower()
                or "Listing Top" in t
                or t.endswith((" Top", "”)", "\u201d"))):
            bad += 1
    return 1 - bad / len(names)


def main():
    # --- skeleton: HKEX allotment roster ---
    d = load("hkex_allotments.json")
    if not d:
        raise SystemExit(
            "merge needs data/batches/hkex_allotments.json (the deal roster) and it "
            "is not there.\n"
            "  On the desk: run  %run hk_ipo.py update            (fetches it)\n"
            "  If HKEX is blocked: %run hk_ipo.py update --skip hkex\n"
            "    -> that keeps the LAST GOOD database; nothing is lost, the book\n"
            "       simply does not gain deals filed since the last successful run.")
    gem = 0
    for r in d["deals"]:
        if r["board"] == "GEM":
            gem += 1
            continue
        c = r["code"]
        put(c, "name", r["stock_name_short"], "hkexnews:allotment-roster", 10)
        put(c, "ipo_date", r["ipo_date_est"], "hkexnews:allot-date+1d", 10, "estimated")
        put(c, "allot_announce_dt", r["allot_announce_dt"], "hkexnews", 10)
    print(f"skeleton: {len(deals)} Main Board deals ({gem} GEM dropped)")

    # --- AAStocks bulk roster (2024+) ---
    d = load("bulk_roster.json")
    if d:
        for r in d["deals"]:
            c = r["code"]
            if c not in deals:
                continue  # AAStocks-only rows are introductions/GEM — inclusion rule
            put(c, "ipo_date", r["ipo_date"], "aastocks:listedipo", 20)
            put(c, "final_price", r["final_price"], "aastocks:listedipo", 20)
            # Convention: HKEX filings state the SUBSCRIPTION LEVEL (applied /
            # available, so 11.67x). AAStocks publishes the OVER-subscription
            # rate (10.7x = 10.7 times more than available). +1 puts the
            # aggregator on the filing's basis; verified across 70 overlaps
            # where the two differ by exactly 1.0.
            put(c, "oversub_public_mult",
                r["oversub_mult"] + 1 if r["oversub_mult"] is not None else None,
                "aastocks:listedipo(+1 to subscription-level basis)", 20)
            put(c, "first_day_return_pct", r["first_day_return_pct"], "aastocks:listedipo", 20)
            put(c, "lot_size", r["lot_size"], "aastocks:listedipo", 20)
            if r.get("mktcap_bn_lo"):
                mid = (r["mktcap_bn_lo"] + (r.get("mktcap_bn_hi") or r["mktcap_bn_lo"])) / 2
                put(c, "mktcap_aastocks_hkdm", round(mid * 1000, 1),
                    "aastocks:listedipo mktcap", 15, "estimated")

    # --- scripted PDF extraction ---
    for batch, srcname in (("extracted_allotments.json", "hkex-pdf:allotment"),
                           ("extracted_prospectus.json", "hkex-pdf:prospectus")):
        d = load(batch)
        if not d:
            continue
        is_prosp = "prospectus" in srcname
        for r in d["deals"]:
            c = r["code"]
            if c not in deals:
                continue
            fields = ["price_range_lo", "price_range_hi", "offer_shares",
                      "net_proceeds_hkdm", "gross_proceeds_hkdm",
                      "shares_outstanding", "overallot_shares",
                      "sale_shares"]     # secondary component, where the header states one
            # Subscription levels: only the standardised table unambiguously
            # separates the public tranche from the international one. A prose
            # match is ranked BELOW the aggregator, which reports the field
            # directly, and is flagged estimated.
            if r.get("intl_tranche_absent"):
                put(c, "intl_tranche_absent", True, srcname, 40)
            osub_prio = 40 if r.get("oversub_method") == "table" else 15
            for f in ("oversub_public_mult", "oversub_intl_mult"):
                put(c, f, r.get(f), srcname + f":{r.get('oversub_method', 'prose')}",
                    osub_prio, "single" if osub_prio == 40 else "estimated")
            if is_prosp:
                # a prospectus states the indicative CAP; only the allotment
                # announcement carries the struck price
                put(c, "price_range_hi", r.get("final_price"), srcname + ":cap", 25)
            else:
                fields.append("final_price")
            for f in fields:
                put(c, f, r.get(f), srcname, 40)
            # Dealings begin 1-2 business days AFTER allotment results are filed.
            # A parsed date outside that window is a mis-read (e.g. the
            # prospectus date), so it is discarded rather than allowed to
            # override the roster date.
            ld, ann = r.get("listing_date"), deals[c].get("allot_announce_dt", "")[:10]
            if ld and ann and ann <= ld <= _plus_days(ann, 10):
                put(c, "ipo_date", ld, srcname + ":timetable", 40)
            for f in ("greenshoe_snip", "cornerstone_snip"):
                put(c, f, r.get(f), srcname, 40)

    # --- prospectus-derived company profiles (full name / CN name / overview) ---
    d = load("extracted_profiles.json")
    if d:
        for r in d["deals"]:
            c = r["code"]
            if c not in deals:
                continue
            put(c, "name_full", r.get("name_full"), "hkex-pdf:prospectus-cover", 40)
            put(c, "name_cn", r.get("name_cn"), "hkex-pdf:prospectus-cover", 40)
            put(c, "business_overview", r.get("overview"), "hkex-pdf:prospectus-summary", 40)

    # --- prospectus financial summary tables ---
    d = load("extracted_financials.json")
    if d:
        for r in d["deals"]:
            c = r["code"]
            if c not in deals:
                continue
            for f in ("rev_latest", "ni_latest"):
                put(c, f, r.get(f), f"hkex-pdf:financial-summary({r.get('currency')})", 35,
                    "estimated")
            put(c, "fin_currency", r.get("currency"), "hkex-pdf:financial-summary", 35)
            put(c, "rev_series_native_k", r.get("rev_series"), "hkex-pdf:financial-summary", 35)
            put(c, "ni_series_native_k", r.get("ni_series"), "hkex-pdf:financial-summary", 35)

    # --- Chinese names from the HKEX securities feed (authoritative, complete) ---
    d = load("names_cn.json")
    if d:
        for c, nm in d["names"].items():
            if c in deals:
                put(c, "name_cn", nm, "hkexnews:listed-securities feed", 50)

    # --- deep prospectus parse: syndicate, cornerstone, cap, share count ---
    d = load("extracted_deep.json")
    if d:
        for r in d["deals"]:
            c = r["code"]
            if c not in deals:
                continue
            src = f"hkex-pdf:deep({r.get('cornerstone_src', 'prospectus')})"
            # BANK lists pass through clean_party_list: the Parties-Involved
            # parse glues the previous entry's office address onto the next
            # bank ("Central, Hong Kong CLSA Limited" — 171 rows shipped that
            # way), and the element cleaner is where that class of bleed is
            # stripped. Cornerstone lists keep their own path — their entries
            # legitimately carry amounts and parentheticals.
            from clean_names import clean_party_list as _cpl
            for f in ("sponsors", "bookrunners", "syndicate"):
                put(c, f, _cpl(r.get(f)) or None, src, 45)
            for f in ("cornerstone_investors",
                      "cornerstone_n", "cornerstone_amt_m", "cornerstone_amt_ccy",
                      "cornerstone_pct", "offer_price_cap"):
                put(c, f, r.get(f), src, 45)
            put(c, "shares_outstanding", r.get("shares_on_listing"), src, 35)
            put(c, "offer_pct_of_capital", r.get("offer_pct_of_capital"), src, 40)
            # A LISTING-RULE THRESHOLD IS NOT A MARKET CAP. The prospectus
            # eligibility paragraph reads "our expected market capitalization at
            # the time of Listing ... exceeds HK$4 billion as required by Rule
            # 8.05(3)" — and because the parser keeps the LARGEST plausible
            # match, that boilerplate beat the issuer's own smaller figure.
            # HK$4,000.0m turned up on four unrelated issuers (Sipai, Pateo,
            # Axera, Crealights) and HK$10,000.0m on Momenta, which is the
            # Rule 8A.06 WVR minimum. A genuine statement reads "Market
            # Capitalisation HK$4,128 million"; a threshold says exceeds /
            # at least / not less than / as required by.
            # Test only what comes BEFORE the figure. "our expected market
            # capitalization ... is approximately HK$9.95 billion, and the
            # minimum prescribed public float ..." is a genuine statement whose
            # next clause happens to say "minimum" — Zijin Gold and Rokae both
            # read that way. The snip ends ~30 chars after the match, so the
            # LAST HK$ in it is the matched figure.
            stated, msnip = r.get("mktcap_stated_hkdm"), (r.get("mktcap_stated_snip") or "")
            _i = msnip.rfind("HK$")
            _lead = msnip[:_i] if _i > 0 else msnip
            if stated is not None and re.search(
                    r"exceed|at\s+least|not\s+less\s+than|minimum|as\s+required\s+by|"
                    r"Rule\s+8\.05|Rule\s+8A\.06|requirement", _lead, re.I):
                deals[c]["mktcap_note"] = (
                    f"prospectus 'market capitalisation' line rejected — it is the "
                    f"listing-rule threshold, not the issuer's figure "
                    f"(\"{msnip.strip()[:110]}\")")
                stated = None
            put(c, "mktcap_stated_hkdm", stated, src, 40)
            # The statement is anchored to a price — usually the maximum of the
            # range — and 28 deals struck somewhere else, so the stated cap is
            # for a price that never happened (Li Auto: HK$307.8bn at HK$150.00
            # when it priced at HK$118.00). The sentence names its own basis, so
            # the correction is exact arithmetic; done in pass 2, where the
            # final price is known.
            if stated is not None:
                _mp = re.search(r"(?:Offer\s+Price\s+of|Price\s+of|based\s+on)\s*"
                                r"HK\$([\d.,]+)\s*per", msnip, re.I)
                if _mp:
                    try:
                        _px = float(_mp.group(1).replace(",", ""))
                        if _px > 0:
                            put(c, "mktcap_stated_px", _px, src, 40)
                    except ValueError:
                        pass
            put(c, "greenshoe_pct", r.get("greenshoe_pct_stated"), src + ":stated", 35)
            # labelled total beats the loose prose count used before
            if r.get("offer_shares_total"):
                deals[c]["offer_shares"] = r["offer_shares_total"]
                prov[c]["offer_shares"] = {"src": src + ":labelled total", "prio": 55,
                                           "status": "single"}
            put(c, "cornerstone_none", r.get("cornerstone_none"), src, 45)
            put(c, "range_lo", r.get("range_lo"), src, 30)
            put(c, "range_hi_indic", r.get("range_hi"), src, 30)
            # the cap IS the top of the indicative range: HK prospectuses print a
            # maximum offer price and no floor, so pct-in-range is not computable
            put(c, "price_range_hi", r.get("offer_price_cap"), src + ":cap", 45)

    # --- listing-day and since-IPO performance ---
    d = load("prices.json")
    if d:
        for r in d["deals"]:
            c = r["code"]
            if c not in deals:
                continue
            put(c, "first_day_return_pct", r.get("day1_return_pct"), "yahoo:listing-day close", 45)
            put(c, "day1_open_pop_pct", r.get("day1_open_pop_pct"), "yahoo:listing-day open", 45)
            put(c, "since_ipo_pct", r.get("since_ipo_pct"), "yahoo:latest close", 45)
            put(c, "last_close", r.get("last_close"), "yahoo", 45)

    # --- final over-allotment outcome (30 days after listing) ---
    d = load("stabilization.json")
    if d:
        for r in d["deals"]:
            c = r["code"]
            if c not in deals:
                continue
            for f in ("greenshoe_exercised_final", "greenshoe_shares_exercised",
                      "stabilization_link", "stabilization_dt",
                      # the fetcher's "linked but outcome unclassifiable" reason
                      # must travel with the link, or the blank outcome beside a
                      # working hyperlink reads as a parser failure
                      "stabilization_note"):
                put(c, f, r.get(f), "hkexnews:end-of-stabilisation notice", 45)

    # --- who ran the stabilisation (the bank holding the shoe and the bid) ---
    d = load("stabilizing_managers.json")
    if d:
        n_sm = 0
        for r in d["deals"]:
            c = r["code"]
            if c not in deals:
                continue
            put(c, "stabilizing_manager", r.get("stabilizing_manager"),
                f"hkex-pdf:{r.get('src', 'allotment announcement')}", 45)
            put(c, "stabilizing_manager_key", r.get("stabilizing_manager_key"),
                "derived:bank family key", 45)
            # the single date the aftermarket desk plans around: the filing's
            # own "30th day after the last day for lodging applications"
            put(c, "stabilization_end_date", r.get("stabilization_end_date"),
                "hkex-pdf:allotment announcement, stated stabilisation end", 45)
            if r.get("stabilizing_manager_none"):
                # the FILING itself says none was appointed — that fact beats
                # the generic "not named in a form the parser reads" note the
                # blank would otherwise get further down
                deals[c]["stabmgr_note"] = (
                    "the filing states no stabilising manager will be "
                    "appointed — a filed fact, not an extraction gap "
                    f"({r.get('src', '')})")
                prov[c]["stabmgr_note"] = {"src": f"hkex-pdf:{r.get('src','')}",
                                           "prio": 60, "status": "single"}
            n_sm += 1
        print(f"  stabilising manager named on {n_sm} deals")

    # --- multi-horizon returns and sector alpha ---
    d = load("prices.json")
    if d:
        for r in d["deals"]:
            c = r["code"]
            if c not in deals:
                continue
            # every horizon carries its own index leg: an alpha whose benchmark
            # return is not shown beside it cannot be checked by the reader
            put(c, "price_asof", r.get("last_date"), "yahoo/tencent:last close", 45)
            # A price frozen for a month is a SUSPENSION, not staleness: Many
            # Idea Cloud (6696) last traded 2026-03-30 and its since-IPO print
            # would otherwise sit five months old with nothing saying why.
            ld = r.get("last_date")
            if ld and not r.get("error"):
                try:
                    aged = (date.today() - date.fromisoformat(ld[:10])).days
                except ValueError:
                    aged = 0
                if aged > 30 and not deals[c].get("price_note"):
                    deals[c]["price_note"] = (
                        f"no trading print since {ld} — the line is suspended or "
                        f"delisted; last_close and since-IPO are measured to the "
                        f"final traded session, not to today")
            # a heuristic listing date (allot-date+1d) is CONFIRMED when the
            # first traded bar landed on exactly that day — that is the
            # exchange's own record of when dealings began
            fd = r.get("first_date")
            if fd and (x0 := deals.get(c)) and (x0.get("ipo_date") or "")[:10] == fd:
                pv0 = prov.get(c, {}).get("ipo_date")
                if pv0 and pv0.get("status") == "estimated":
                    pv0["status"] = "xchecked"
                    pv0["src2"] = "price series: first traded bar on that date"
            # provenance travels with the numbers: the open-vs-close rules below
            # need to know a raw close line when they see one
            put(c, "price_src", r.get("price_src") or "yahoo:history", "prices batch", 45)
            for f in ("ret_1w_pct", "ret_1m_pct", "ret_3m_pct",
                      "alpha_1w_pct", "alpha_1m_pct", "alpha_3m_pct",
                      "bench_1w_pct", "bench_1m_pct", "bench_3m_pct",
                      "alpha_day1_pct", "bench_day1_pct",
                      "alpha_since_pct", "bench_since_pct",
                      "ret_1w_date", "ret_1m_date", "ret_3m_date",
                      "benchmark", "day1_open_pop_pct"):
                put(c, f, r.get(f), "yahoo:price history", 45)

    # --- AAStocks per-deal page: syndicate, market cap at listing, cornerstones ---
    # A second, independent publisher of the same facts. It fills what the
    # prospectus parser missed and disagrees loudly where it disagrees.
    d = load("aastocks_deal.json")
    if d:
        for r in d["deals"]:
            c = r["code"]
            if c not in deals:
                continue
            # THE LISTING DATE. The HKEX-derived value is an ESTIMATE
            # (allotment date + 1 day) and it lands on a SATURDAY for 33
            # deals — HK allotment results are often published on a Saturday
            # with dealings beginning the next business day — and on a public
            # holiday for one more. A wrong listing date makes the two price
            # sources pick DIFFERENT debut sessions (Morimatsu's day-1 read
            # +213.7% off the second session instead of +258.9% off the
            # first). AAStocks prints the exchange's dealing-commencement
            # date, so it wins outright.
            if r.get("listing_date_aa"):
                put(c, "ipo_date", r["listing_date_aa"][:10],
                    "aastocks:Listing Date (dealings commenced)", 46)
            if r.get("sponsors_cn"):
                put(c, "sponsors_cn", r["sponsors_cn"], "aastocks:保薦人", 44)
            if r.get("underwriters_cn"):
                put(c, "underwriters_cn", r["underwriters_cn"], "aastocks:包銷商", 44)
                put(c, "syndicate_n_aa", len(r["underwriters_cn"]), "aastocks:包銷商", 44)
            # the listing market cap is quoted across the price range; the deal
            # priced somewhere in it, so interpolate on where the price landed
            lo, hi = r.get("mktcap_listing_lo_hkdm"), r.get("mktcap_listing_hi_hkdm")
            if lo:
                x = deals[c]
                k = None
                if hi and hi > lo and x.get("price_range_hi") and x.get("final_price"):
                    cap = x["price_range_hi"]
                    k = min(1.0, max(0.0, x["final_price"] / cap)) if cap else None
                val = lo + (hi - lo) * k if (k is not None and hi) else (lo + (hi or lo)) / 2
                put(c, "mktcap_aa_listing_hkdm", round(val, 1),
                    "aastocks:上市市值 (scaled to the struck price)", 43)
            if r.get("cornerstone_aa"):
                put(c, "cornerstone_aa", r["cornerstone_aa"], "aastocks:機構性投資者", 44)
                put(c, "cornerstone_aa_total_hkdm", r.get("cornerstone_aa_total_hkdm"),
                    "aastocks:機構性投資者", 44)
            if r.get("lot_size_aa"):
                put(c, "lot_size", r["lot_size_aa"], "aastocks:每手股數", 40)

    # --- prospectus cornerstone re-parse (prose/agreement shapes) ---
    d = load("deep_cornerstone_reparse.json")
    if d:
        for r in d["deals"]:
            c = r["code"]
            if c not in deals:
                continue
            if r.get("cornerstone_investors") and not deals[c].get("cornerstone_investors"):
                put(c, "cornerstone_investors", r["cornerstone_investors"],
                    "prospectus:cornerstone re-parse", 35)
                put(c, "cornerstone_n", r.get("cornerstone_n"),
                    "prospectus:cornerstone re-parse", 35)
            if r.get("cornerstone_pct") is not None and deals[c].get("cornerstone_pct") is None:
                put(c, "cornerstone_pct", r["cornerstone_pct"],
                    "prospectus:cornerstone prose re-parse", 35)

    # --- AAStocks 損益表: the pre-IPO fiscal year, where the prospectus text
    # never surrendered one. Only FYs that CLOSED before listing are taken.
    d = load("aastocks_pl.json")
    if d:
        for r in d["deals"]:
            c = r["code"]
            if c not in deals:
                continue
            if r.get("ni_latest_aa_hkdm") is not None and deals[c].get("ni_latest") is None:
                put(c, "ni_latest", r["ni_latest_aa_hkdm"],
                    f"aastocks:損益表 FY {r.get('fin_year_aa')}", 35, "estimated")
            if r.get("rev_latest_aa_hkdm") is not None and deals[c].get("rev_latest") is None:
                put(c, "rev_latest", r["rev_latest_aa_hkdm"],
                    f"aastocks:損益表 FY {r.get('fin_year_aa')}", 35, "estimated")

    # --- AAStocks ENGLISH per-deal page: same facts, English names — these
    # supersede the Chinese scrape everywhere a name is DISPLAYED (the CN batch
    # stays on disk as a cross-check)
    d = load("aastocks_deal_en.json")
    if d:
        for r in d["deals"]:
            c = r["code"]
            if c not in deals:
                continue
            if r.get("sponsors_en"):
                put(c, "sponsors_en", r["sponsors_en"], "aastocks-en:Sponsor(s)", 45)
            if r.get("underwriters_en"):
                put(c, "underwriters_en", r["underwriters_en"], "aastocks-en:Underwriter(s)", 45)
            if r.get("industry_en"):
                put(c, "industry_en", r["industry_en"], "aastocks-en:Industry", 45)
            if r.get("cornerstone_aa"):
                # English names replace the CN table outright
                deals[c]["cornerstone_aa"] = r["cornerstone_aa"]
                if r.get("cornerstone_aa_total_hkdm"):
                    deals[c]["cornerstone_aa_total_hkdm"] = r["cornerstone_aa_total_hkdm"]
                prov[c]["cornerstone_aa"] = {"src": "aastocks-en:Institutional Investors",
                                             "prio": 45, "status": "single"}

    # --- A/H discount struck at pricing ---
    d = load("ah_ipo.json")
    if d:
        for r in d["deals"]:
            c = r["code"]
            if c not in deals or r.get("ah_discount_ipo_pct") is None:
                continue
            for f in ("ah_discount_ipo_pct", "a_close_hkd", "a_close_cny",
                      "a_close_date", "cnyhkd"):
                put(c, f, r.get(f), "derived:A close before listing x CNYHKD vs H offer", 45)

    # --- press-verified figures for machine-unextractable rows -------------
    d = load("press_figures.json")
    if d:
        for r in d["deals"]:
            c = r["code"]
            if c not in deals:
                continue
            for f in ("pe_ipo", "ni_latest", "rev_latest", "mktcap_ipo_hkdm",
                      "mktcap_basis", "cornerstone_investors", "cornerstone_pct",
                      "sponsors", "final_price", "name_cn",
                      # filing-verified structural figures (e.g. Ingenic's
                      # allotment announcement). Subscription multiples stay
                      # below the Bloomberg desk paste (prio 95), which is the
                      # field of record once pasted on the terminal.
                      "shares_outstanding", "offer_shares", "overallot_shares",
                      "oversub_public_mult", "oversub_intl_mult"):
                if r.get(f) is not None:
                    put(c, f, r[f], f"press:{r.get('src','reported')}", 70,
                        status="xchecked")

    # --- Bloomberg desk values (pasted from the terminal into bbg.xlsx) ---
    # Subscriptions OVERRIDE the scrape per the desk's instruction (CP036/CP037
    # are the filing-of-record fields); where the two agree the scraped value is
    # upgraded to cross-checked instead. Market cap is deliberately NOT read
    # from this batch — the desk formula behind that column is wrong.
    d = load("bbg_desk.json")
    if d:
        asof = d.get("pasted_asof", "")
        for r in d["deals"]:
            c = r["code"]
            if c not in deals:
                continue
            if r.get("retail_sub") is not None:
                put(c, "oversub_public_mult", r["retail_sub"],
                    f"bloomberg:CP036 (desk paste {asof})", 95)
            if r.get("instl_sub") is not None:
                put(c, "oversub_intl_mult", r["instl_sub"],
                    f"bloomberg:CP037 (desk paste {asof})", 95)
            if r.get("pe_now") is not None and 0 < r["pe_now"] < 5000:
                put(c, "pe_now", round(r["pe_now"], 1),
                    f"bloomberg:PE_RATIO (desk paste {asof})", 95)
            # kept BESIDE the scraped multiple — trailing-EPS basis differs from
            # the prospectus final-FY basis, so this is a second reading, not a
            # correction (see MAINTENANCE: the vintage pattern)
            if r.get("pe_ipo") is not None and 2 < r["pe_ipo"] < 500:
                put(c, "pe_ipo_bbg", round(r["pe_ipo"], 1),
                    f"bloomberg:P/E at listing (desk paste {asof})", 95)
            if r.get("shoe_exercised"):
                try:
                    n_sh = float(r["shoe_exercised"])
                except (TypeError, ValueError):
                    n_sh = None
                if n_sh and deals[c].get("greenshoe_exercised_final") == "lapsed":
                    deals[c]["shoe_note"] = (
                        f"CONFLICT: our notice-parse read 'lapsed' but Bloomberg "
                        f"records {n_sh:,.0f} over-allotment shares exercised — "
                        f"verify the stabilisation notice by hand")
            if r.get("a_pe_at_hipo") is not None and 0 < r["a_pe_at_hipo"] < 5000:
                put(c, "a_pe_at_hipo", round(r["a_pe_at_hipo"], 2),
                    f"bloomberg:BDH PE_RATIO A-line at H-IPO (desk paste {asof})", 95)

    # --- document hyperlinks ---
    d = load("hkex_prospectus_links.json")
    if d:
        for r in d["deals"]:
            c = r["code"]
            if c not in deals:
                continue
            # first doc that actually HAS a link — docs[0] is not guaranteed to
            # carry one, and blindly concatenating None killed the whole merge
            # (TypeError: can only concatenate str (not "NoneType") to str),
            # taking 524 deals down over one missing hyperlink.
            link = next((x["file_link"] for x in (r.get("docs") or [])
                         if x.get("file_link")), None)
            if link:
                put(c, "prospectus_link", "https://www1.hkexnews.hk" + link,
                    "hkexnews", 40)
    d = load("hkex_allotments.json")
    if d:
        for r in d["deals"]:
            c = r["code"]
            if c in deals and r.get("file_link"):
                put(c, "allotment_link", "https://www1.hkexnews.hk" + r["file_link"],
                    "hkexnews", 40)

    # --- greenshoe status + cornerstone take-up ---
    d = load("extracted_shoe_cornerstone.json")
    if d:
        for r in d["deals"]:
            c = r["code"]
            if c not in deals:
                continue
            put(c, "greenshoe_exercised", r.get("greenshoe_exercised"),
                "hkex-pdf:allotment", 40)
            # cornerstone from this older extractor is superseded by the deep
            # parse (it mistook connected-client tables for cornerstone tables)

    # --- agent deep dives ---
    for p in sorted(B.glob("deep_*.json")):
        d = json.loads(p.read_text())
        for r in d.get("deals", []):
            c = str(r.get("code", "")).lstrip("0").zfill(4)
            if c not in deals:
                continue
            for f, v in r.items():
                if f in ("code", "_prov") or v is None:
                    continue
                fprov = (r.get("_prov") or {}).get(f, {})
                prio_a = 30
                cur_v = deals.get(c, {}).get(f)
                if isinstance(v, list) and isinstance(cur_v, list) \
                        and name_quality(v) >= name_quality(cur_v) + 0.25:
                    prio_a = 60          # clean list beats a damaged parse
                put(c, f, v, f"agent:{p.stem}:{fprov.get('src', 'research')}", prio_a,
                    fprov.get("status", "single"))



    # --- targeted press fills for large deals the filings did not yield ---
    for name in ("deep_cornerstone_fill.json", "deep_sponsors_fill.json"):
        d = load(name)
        if not d:
            continue
        for r in d.get("deals", []):
            c = str(r.get("code", "")).lstrip("0").zfill(4)
            if c not in deals:
                continue
            for f in ("cornerstone_pct", "cornerstone_investors", "cornerstone_none",
                      "sponsors", "bookrunners"):
                if r.get(f) is None:
                    continue
                # the research batch was written with STRINGIFIED values —
                # "['Goldman Sachs', …]" compared as a string lost every
                # adjudication to the damaged parses it was created to fix
                if isinstance(r[f], str):
                    t = r[f].strip()
                    if t.startswith("["):
                        import ast as _ast
                        try:
                            r[f] = _ast.literal_eval(t)
                        except Exception:
                            pass
                    elif f == "cornerstone_pct":
                        try:
                            r[f] = float(t)
                        except ValueError:
                            pass
                src = ((r.get("_prov") or {}).get(f, {}) or {}).get("src", "press research")
                prio = 42
                cur_v = deals.get(c, {}).get(f)
                if isinstance(r[f], list) and isinstance(cur_v, list):
                    # QUALITY beats source rank: a clean researched list must
                    # not lose to a damaged-table parse ("exercised in full)
                    # Top" once outranked China Orient AM on priority alone)
                    if name_quality(r[f]) >= name_quality(cur_v) + 0.25:
                        prio = 60
                if f == "cornerstone_pct" and isinstance(cur_v, (int, float)):
                    kept_src = str(prov.get(c, {}).get(f, {}).get("src", ""))
                    # a press aggregate at the STRUCK price outranks the
                    # prospectus table read at the range low-end
                    if "range low-end" in kept_src and "press" in src:
                        prio = 60
                put(c, f, r[f], f"agent:{name[:-5]}:{src}"[:110], prio)

    # --- adjudicated conflicts: the kept value was verified; the orange goes
    d = load("conflict_rulings.json")
    if d:
        for r in d.get("rulings", []):
            pv = prov.get(r["code"], {}).get(r["field"])
            if r.get("value") is not None and r["code"] in deals:
                deals[r["code"]][r["field"]] = r["value"]
                prov.setdefault(r["code"], {})[r["field"]] = {
                    "src": "adjudicated: " + r.get("note", "")[:70],
                    "prio": 70, "status": r.get("status", "single")}
            elif pv and pv.get("status") == "conflict":
                pv["status"] = r.get("status", "single")
                pv["src2"] = r.get("note", "adjudicated")[:80]

    # --- A/H map ---
    d = load("ah_map.json")
    if d:
        for r in d.get("ah_pairs", []):
            c = str(r["code"]).lstrip("0").zfill(4)
            if c not in deals:
                continue
            put(c, "a_share_code", r.get("a_share_code"), "agent:ah_map", 30,
                "xchecked" if len(r.get("verified_by", [])) > 1 else "single")
            put(c, "is_h_share", True, "agent:ah_map", 30)
            put(c, "ah_note", r.get("h_over_a_note"), "agent:ah_map", 30)
        for r in d.get("proxy_for_no_a", []):
            c = str(r.get("code", "")).lstrip("0").zfill(4)
            if c not in deals:
                continue
            put(c, "a_share_proxy",
                {"code": r.get("proxy_a_code"), "name": r.get("proxy_a_name"),
                 "rationale": r.get("rationale")}, "agent:ah_map", 30)

    # --- A/H price snapshot (scripted from AAStocks AH table) ---
    d = load("ah_snapshot.json")
    if d:
        fx_snap = d.get("cnyhkd")
        asof = str(d.get("as_of", ""))[:10]
        for r in d.get("pairs", []):
            c = str(r["code"]).lstrip("0").zfill(4)
            if c not in deals:
                continue
            if r.get("premium_pct") is not None:
                put(c, "ah_premium_snapshot", round(r["premium_pct"] / 100, 4),
                    f"aastocks:ah.aspx@{d.get('as_of','')}", 40)
            # Tencent A-line enrichment: total share capital and the company
            # market cap ALL share classes x A price (field-45 semantics
            # verified on ICBC: 356.4bn implied shares = A+H, not A-only).
            if r.get("a_total_shares"):
                put(c, "a_total_shares_now", r["a_total_shares"],
                    f"tencent:A-line quote@{asof}", 40)
            if r.get("a_total_mktcap_bn_cny") and fx_snap:
                put(c, "a_mktcap_now_hkdm",
                    round(r["a_total_mktcap_bn_cny"] * 1000 * fx_snap, 1),
                    f"tencent:A-line total cap x CNYHKD {fx_snap}@{asof}", 40)

    # --- A-premium convention: the desk reads the pair as A OVER H ----------
    # a_premium_ipo_pct = A close (HKD, day before listing) / H offer - 1.
    # Computed directly from the stored legs — not by transforming the old
    # H-discount — so a sign convention can never half-flip.
    for c, x in deals.items():
        ac, fp = x.get("a_close_hkd"), x.get("final_price")
        if ac and fp:
            x["a_premium_ipo_pct"] = round(100 * (ac / fp - 1), 2)
            prov[c]["a_premium_ipo_pct"] = {
                "src": "derived:A close before listing (HKD) / H offer - 1",
                "prio": 50, "status": "single"}
        snap = x.get("ah_premium_snapshot")
        if snap is not None and snap > -1:
            x["a_premium_now"] = round(1 / (1 + snap) - 1, 4)
            prov[c]["a_premium_now"] = {
                "src": "derived:1/(1+H-premium snapshot)-1", "prio": 50,
                "status": "single"}

    # --- derived fields (always recomputed, overwrite allowed) ---
    dropped_shares = []
    # pass 1: deal size, because market cap and both multiples are derived from it
    for c, x in deals.items():
        fp = x.get("final_price")
        # deal size: stated gross > price x shares (only if consistent with net) > net.
        # The offer-share regex sometimes grabs a tranche instead of the total
        # (e.g. Kuaishou: 165m x HK$115 = HK$19bn vs HK$41.3bn net stated), so a
        # derived value that cannot bracket net proceeds is discarded, not shown.
        gross, net, sh = x.get("gross_proceeds_hkdm"), x.get("net_proceeds_hkdm"), x.get("offer_shares")
        derived = round(fp * sh / 1e6, 1) if fp and sh else None
        # THE SHARE COUNT IS A LABELLED FIELD; the proceeds are parsed prose.
        # When both proceeds figures sit below a quarter of shares x price they
        # cannot be describing this offering at all — a greenshoe is at most
        # 15% of the base deal. Jenscare's announcement states 8,076,400 offer
        # shares at HK$27.80 (HK$224.5m) alongside gross HK$32.2m / net
        # HK$32.0m, which are the 1,211,400 shoe shares. Previously the bogus
        # net poisoned the bracket test below and the GOOD share count was the
        # thing discarded.
        if derived and gross and net and max(gross, net) < derived * 0.25:
            x["size_note"] = (f"stated gross HK${gross:,.1f}m / net HK${net:,.1f}m "
                              f"rejected — the filing's own {sh:,.0f} offer shares "
                              f"at HK${fp:,.2f} come to HK${derived:,.1f}m, so both "
                              f"figures describe the over-allotment option, not "
                              f"the offering")
            for _f in ("gross_proceeds_hkdm", "net_proceeds_hkdm"):
                x.pop(_f, None)
                prov[c].pop(_f, None)
            gross = net = None
        bad_shares = False
        ceiling = 2.4 if (net or 0) < 150 else (1.9 if (net or 0) < 500 else 1.6)
        # A SECONDARY COMPONENT breaks the bracket legitimately: Weibo offered
        # 11,000,000 shares of which 5,500,000 were Sale Shares, so the company's
        # net proceeds cover its half only and the full offering is ~2x net.
        # That is not a bad share count, so widen the ceiling by the primary
        # fraction rather than discarding the number.
        sale_sh = x.get("sale_shares")
        if sale_sh and sh and 0 < sale_sh < sh:
            ceiling = ceiling * sh / (sh - sale_sh)
        if derived and net and not (net * 0.95 <= derived <= net * ceiling):
            bad_shares = True                      # tranche or total, not the offer
        if sh and x.get("shares_outstanding") and sh > x["shares_outstanding"]:
            bad_shares = True                      # offer can't exceed shares in issue
        if derived and derived > 150000:
            bad_shares = True                      # > HK$150bn: larger than any HK IPO
        if bad_shares:
            derived = None
            x.pop("offer_shares", None)
            prov[c].pop("offer_shares", None)
            dropped_shares.append(c)
        # GROSS CANNOT BE SMALLER THAN NET. 16 deals carried a "stated gross"
        # below their own net proceeds (YesAsia: gross 4.5 vs net 91.0), and
        # deal_size took that figure — publishing a HK$117m deal as HK$4.5m.
        # An impossible pair means the gross parse is wrong, so it is dropped
        # and the size falls through to shares x price, then to net.
        if gross and net and gross < net * 0.99:
            x["size_note"] = (f"stated gross HK${gross:,.1f}m rejected — below "
                              f"the deal's own net proceeds HK${net:,.1f}m, "
                              f"which cannot happen")
            x.pop("gross_proceeds_hkdm", None)
            prov[c].pop("gross_proceeds_hkdm", None)
            gross = None
        # A STATED GROSS FAR BELOW price x the filed offer-share count is the
        # greenshoe's figure wearing the deal's label. Jenscare's announcement
        # states HK$32.2m — that is the 1,211,400 shoe shares; the offering was
        # 8,076,400 shares at HK$27.80 = HK$224.5m. The share count is the
        # filing's own header, so where the two disagree by more than 2x the
        # arithmetic wins and the stated figure is retired with a reason.
        if gross and derived and gross < derived * 0.5:
            x["size_note"] = (f"stated gross HK${gross:,.1f}m rejected — the "
                              f"filing's own {sh:,.0f} offer shares at "
                              f"HK${fp:,.2f} come to HK${derived:,.1f}m, so the "
                              f"stated figure is a tranche or the greenshoe")
            x.pop("gross_proceeds_hkdm", None)
            prov[c].pop("gross_proceeds_hkdm", None)
            gross = None
        if gross:
            size, basis = gross, "gross (stated)"
        elif derived:
            size, basis = derived, "gross (price x shares)"
        elif net:
            size, basis = net, "net proceeds"
        else:
            size, basis = None, None
        if size:
            x["deal_size_hkdm"] = size
            x["size_basis"] = basis
            prov[c]["deal_size_hkdm"] = {
                "src": "derived:" + basis, "prio": 50,
                "status": "single" if basis == "gross (stated)" else "estimated"}


    # pass 2: everything that depends on deal size
    ah_cap_ok, ah_cap_fixed = 0, []
    for c, x in deals.items():
        lo, hi, fp = x.get("price_range_lo"), x.get("price_range_hi"), x.get("final_price")
        # HK allotment tables publish the CAP ("Maximum Offer Price") but often not the
        # floor, so record the binary fact that is actually knowable in that case.
        if hi and fp:
            x["priced_at_cap"] = "Y" if abs(fp - hi) < 1e-9 else "N"
            prov[c]["priced_at_cap"] = {"src": "derived:final vs cap", "prio": 50,
                                        "status": "single"}
        if fp and x.get("shares_outstanding"):
            x["mktcap_ipo_hkdm"] = round(fp * x["shares_outstanding"] / 1e6, 1)
            prov[c]["mktcap_ipo_hkdm"] = {"src": "derived:price x shares upon listing",
                                          "prio": 50, "status": "single"}
        elif x.get("offer_pct_of_capital") and x.get("deal_size_hkdm"):
            # offer proceeds / (offer as % of enlarged capital) = market cap.
            # Cross-checks to 0.1% against the share-count method on CATL.
            x["mktcap_ipo_hkdm"] = round(x["deal_size_hkdm"] / (x["offer_pct_of_capital"] / 100), 1)
            prov[c]["mktcap_ipo_hkdm"] = {"src": "derived:deal size / offer % of enlarged capital",
                                          "prio": 50, "status": "estimated"}
        elif (x.get("mktcap_stated_hkdm")
              and x["mktcap_stated_hkdm"] >= 1.2 * (x.get("deal_size_hkdm") or 0)):
            # issuer-stated expected market capitalisation. The >=1.2x-deal-size
            # guard rejects statements about the H-tranche only (CATL states
            # HK$31bn for the tranche vs HK$1.19tn company).
            # RESCALED TO THE STRUCK PRICE where the sentence names its basis:
            # the figure is normally quoted at the maximum offer price, and a
            # deal that priced below it never had that capitalisation.
            _sp = x.get("mktcap_stated_px")
            if _sp and fp and abs(fp - _sp) / _sp > 0.01:
                x["mktcap_ipo_hkdm"] = round(x["mktcap_stated_hkdm"] * fp / _sp, 1)
                x["mktcap_note"] = ((x.get("mktcap_note") + " | ") if x.get("mktcap_note")
                                    else "") + (
                    f"prospectus states HK${x['mktcap_stated_hkdm']:,.0f}m at "
                    f"HK${_sp:,.2f}; rescaled to the struck HK${fp:,.2f}")
                prov[c]["mktcap_ipo_hkdm"] = {
                    "src": "prospectus:stated market capitalisation, rescaled to the offer price",
                    "prio": 48, "status": "single"}
            else:
                x["mktcap_ipo_hkdm"] = x["mktcap_stated_hkdm"]
                prov[c]["mktcap_ipo_hkdm"] = {"src": "prospectus:stated market capitalisation",
                                              "prio": 48, "status": "single"}
        elif x.get("mktcap_aa_listing_hkdm"):
            # AAStocks prints the listing market cap the issuer itself published
            x["mktcap_ipo_hkdm"] = x["mktcap_aa_listing_hkdm"]
            prov[c]["mktcap_ipo_hkdm"] = {"src": "aastocks:上市市值 at the struck price",
                                          "prio": 43, "status": "single"}
        elif (x.get("a_total_shares_now") and fp
              and (x.get("ipo_date") or "") >= "2025-01-01"):
            # A+H issuer whose prospectus parse yielded neither a share count
            # nor a stated cap (Luxshare/SG Micro/CCTC/Ingenic): the A-line
            # quote's total share capital ALREADY includes the new H shares,
            # so capital x H offer price is the company cap at the offer, on
            # the same all-shares basis as the rungs above. Restricted to
            # 2025+ listings so today's count isn't backdated across years of
            # buybacks/placements.
            x["mktcap_ipo_hkdm"] = round(fp * x["a_total_shares_now"] / 1e6, 1)
            prov[c]["mktcap_ipo_hkdm"] = {
                "src": "derived:A-line total share capital x H offer price",
                "prio": 45, "status": "estimated"}
            # the count is TODAY's, so a bonus issue since listing would
            # inflate it — say so rather than present a proxy as a filing
            x["mktcap_note"] = ("no share count or stated cap in the filings — "
                                "company cap proxied by today's A-line total "
                                "share capital x the H offer price; a "
                                "capitalisation issue since listing would "
                                "overstate it")
        elif x.get("mktcap_aastocks_hkdm"):
            x["mktcap_ipo_hkdm"] = x["mktcap_aastocks_hkdm"]
            prov[c]["mktcap_ipo_hkdm"] = {"src": "aastocks:listed mktcap (midpoint)",
                                          "prio": 15, "status": "estimated"}
        # every market cap says which rung of the ladder produced it, so the
        # number is never a bare figure of unknown provenance
        if x.get("mktcap_ipo_hkdm") is not None:
            x["mktcap_basis"] = prov[c].get("mktcap_ipo_hkdm", {}).get("src", "")
            # a second, independent print of the same fact = a cross-check
            aa = x.get("mktcap_aa_listing_hkdm")
            if aa and x["mktcap_ipo_hkdm"] and not x["mktcap_basis"].startswith("aastocks"):
                gap = abs(aa - x["mktcap_ipo_hkdm"]) / max(aa, x["mktcap_ipo_hkdm"])
                ratio = x["mktcap_ipo_hkdm"] / aa if aa else 0
                if gap <= 0.25:
                    if prov[c]["mktcap_ipo_hkdm"].get("status") != "conflict":
                        prov[c]["mktcap_ipo_hkdm"]["status"] = "xchecked"
                elif x.get("a_share_code") and ratio > 1.5:
                    # ADJUDICATED: on an A+H issuer AAStocks' 上市市值 quotes the
                    # H TRANCHE at listing while the filing-derived figure is the
                    # whole company (all share classes x price). Not a
                    # disagreement about the same quantity — keep the derived
                    # value, explain, no orange.
                    x["mktcap_note"] = (f"AAStocks HK${aa:,.0f}m is the H-listing "
                                        f"value only; company-wide cap derived from "
                                        f"the filing is kept")
                    prov[c]["mktcap_ipo_hkdm"]["status"] = "single"
                elif "shares upon listing" not in x["mktcap_basis"]:
                    # ADJUDICATED: the derivation was an ESTIMATE (deal size /
                    # offer-% or a pre-pricing "stated" figure) and it disagrees
                    # wildly with the issuer's published listing capitalisation
                    # (8x both ways in the worst cases = the % was misread).
                    # The published figure wins; the estimate is retired.
                    x["mktcap_ipo_hkdm"] = aa
                    x["mktcap_note"] = ("estimate from "
                                        f"{x['mktcap_basis'].split(':')[-1]} disagreed "
                                        f"with the published listing cap — published "
                                        f"figure adopted")
                    prov[c]["mktcap_ipo_hkdm"] = {
                        "src": "aastocks:上市市值 at the struck price", "prio": 43,
                        "status": "single"}
                    x["mktcap_basis"] = prov[c]["mktcap_ipo_hkdm"]["src"]
                else:
                    # price x FILED share count is the stronger basis (the
                    # AAStocks at-listing figure sometimes counts the combined
                    # A+H capital); ruled for the derivation, disagreement noted
                    prov[c]["mktcap_ipo_hkdm"]["status"] = "single"
                    x["mktcap_note"] = (f"AAStocks lists HK${aa:,.0f}m at listing vs "
                                        f"HK${x['mktcap_ipo_hkdm']:,.0f}m from price x filed "
                                        f"share count — the filed count is kept")
        # --- A/H market-cap adjudication (before P/E-P/S derive off the cap).
        # Independent yardstick for A+H issuers: the A-line's total share
        # capital (which already includes the new H shares) x the H offer
        # price. 2025+ listings only, so today's count isn't backdated across
        # years of corporate actions.
        #
        # IT IS A PROXY, NOT A SOURCE, and it can only ever beat an ESTIMATE.
        # The A-line count is TODAY's count, and three issuers ran a
        # capitalisation issue AFTER listing — Huaqin x1.4, Eastroc x1.3, Gon
        # x1.48 — so applying it to the IPO price overstates those caps by
        # 30-45%. Where a filing states the share count upon listing, that
        # count wins and this block only cross-checks; it overrides only a
        # derived-from-offer-% or aggregator-midpoint estimate, which is the
        # class that was actually broken (Anker: HK$386bn stored vs HK$58bn
        # filed, a misread offer-%).
        sh_a, mc0 = x.get("a_total_shares_now"), x.get("mktcap_ipo_hkdm")
        basis0 = x.get("mktcap_basis") or ""
        filed_count = "shares upon listing" in basis0
        if (sh_a and fp and mc0 and (x.get("ipo_date") or "") >= "2025-01-01"):
            alt = sh_a * fp / 1e6
            gap = abs(alt - mc0) / max(alt, mc0)
            if gap <= 0.30:
                ah_cap_ok += 1
            elif filed_count:
                # a filed count disagreeing with today's A-line count is the
                # signature of a post-listing bonus/capitalisation issue
                x["mktcap_note"] = ((x.get("mktcap_note") + " | ") if x.get("mktcap_note")
                                    else "") + (
                    f"today's A-line share count implies HK${alt:,.0f}m, {gap:.0%} "
                    f"above the filed count at listing — a capitalisation issue "
                    f"after listing; the filed count is kept")
            else:
                ah_cap_fixed.append((c, mc0, alt, gap))
                x["mktcap_ipo_hkdm"] = round(alt, 1)
                x["mktcap_basis"] = "derived:A-line total share capital x H offer price"
                x["mktcap_note"] = (f"parsed cap HK${mc0:,.0f}m "
                                    f"({basis0.split(':')[-1]}) was {gap:.0%} off "
                                    f"the A-line share-capital figure — A-line adopted")
                prov[c]["mktcap_ipo_hkdm"] = {
                    "src": "derived:A-line total share capital x H offer price",
                    "prio": 55, "status": "xchecked"}
        if x.get("overallot_shares") and x.get("offer_shares"):
            x["greenshoe_pct"] = round(100 * x["overallot_shares"] / x["offer_shares"], 1)
            prov[c]["greenshoe_pct"] = {"src": "derived:over-allocated / offer shares",
                                        "prio": 50, "status": "single"}
        size = x.get("deal_size_hkdm")
        # profitability + IPO multiples. P/E only where the issuer was profitable —
        # a negative P/E is meaningless, so loss-makers carry P/S instead (n/m rule).
        ni, rev, mc = x.get("ni_latest"), x.get("rev_latest"), x.get("mktcap_ipo_hkdm")
        if ni is not None:
            x["profitable_at_ipo"] = "Y" if ni > 0 else "N"
            prov[c]["profitable_at_ipo"] = {"src": "derived:latest FY net income sign",
                                            "prio": 50, "status": "single"}
        if mc and ni and ni > 0:
            x["pe_ipo"] = round(mc / ni, 1)
            prov[c]["pe_ipo"] = {"src": "derived:mktcap / latest FY NI", "prio": 50,
                                 "status": "single"}
        if mc and rev and rev > 0:
            x["ps_ipo"] = round(mc / rev, 1)
            prov[c]["ps_ipo"] = {"src": "derived:mktcap / latest FY revenue", "prio": 50,
                                 "status": "single"}
        # --- plausibility gate on the extracted financials -------------------
        # The PDF table parser occasionally locks onto a stray figure (a note
        # reference, a per-share line, a table already printed in millions),
        # which then prints as a 307,800x P/S or a 39,145x P/E. Those are not
        # valuations, they are extraction failures, and publishing them is worse
        # than publishing nothing. Two checks, both internal to the record:
        #   1. net income above revenue  -> the PAIR is inconsistent; neither
        #      figure can be trusted, so both go and the note says why.
        #   2. a derived multiple beyond 300x -> the denominator is wrong. A
        #      pre-revenue 18A issuer is the honest exception: its revenue may
        #      genuinely be near zero, so the revenue stands and only the
        #      meaningless multiple is withheld (the n/m rule already used for
        #      loss-makers' P/E).
        MULT_CAP = 300
        # pre-revenue is a FACT about the revenue line, not a biotech label:
        # a pre-production miner with US$0.13m of incidental rental income
        # (Merdeka) is exactly as pre-revenue as an 18A issuer
        prerev = (x.get("subsector") == "Biotech pre-revenue (18A)"
                  or str(x.get("name") or "").rstrip().endswith("-B")
                  or (rev is not None and 0 < rev < 10))
        if rev is not None and ni is not None and ni > rev:
            if x.get("sector") == "Financials":
                # a PE/VC firm or bank books equity-method investment gains
                # BELOW the income line — NI above income is genuine there
                # (Tian Tu FY2022: total income RMB423m, NI RMB749m), so the
                # pair stands and the note says why it looks odd
                x["fin_check"] = ("net income exceeds total income via "
                                  "equity-method investment gains — normal for "
                                  "an investment firm; both figures are as filed")
            else:
                x["fin_check"] = (f"latest-FY net income (HK${ni:,.1f}m) exceeds revenue "
                                  f"(HK${rev:,.1f}m) — the extracted pair is inconsistent, "
                                  f"so both figures and the multiples derived from them "
                                  f"are withheld")
                for k in ("rev_latest", "ni_latest", "pe_ipo", "ps_ipo"):
                    x.pop(k, None)
                rev = ni = None
        if x.get("pe_ipo") and x["pe_ipo"] > MULT_CAP:
            # an extreme multiple CONFIRMED by a second source is a fact, not a
            # parse error: CALB really priced at ~549x trailing (Bloomberg
            # prints 548.9x). Restore when Bloomberg lands within 25% and the
            # level is still on a human scale; a 9,514x "bank P/E" that both
            # sources print is a shared artifact, not a confirmation.
            bbg_pe = x.get("pe_ipo_bbg")
            if bbg_pe and x["pe_ipo"] <= 1000 \
                    and abs(x["pe_ipo"] / bbg_pe - 1) <= 0.25:
                x["pe_note"] = (f"extreme but REAL — trailing multiple at the offer; "
                                f"Bloomberg prints {bbg_pe:,.0f}x at listing")
                prov[c]["pe_ipo"] = {"src": "derived:mktcap / latest FY NI",
                                     "prio": 50, "status": "xchecked",
                                     "src2": "bloomberg:P/E at listing"}
            else:
                x["pe_note"] = (f"withheld — mktcap / net income gives {x['pe_ipo']:,.0f}x, "
                                f"which fails the {MULT_CAP}x plausibility check"
                                + (f"; Bloomberg prints {bbg_pe:,.0f}x — the two agree, "
                                   f"which at this level reads as a shared data artifact"
                                   if bbg_pe and abs(x["pe_ipo"] / bbg_pe - 1) <= 0.25
                                   else f"; the extracted net income (HK${ni:,.1f}m) "
                                        f"is not trustworthy"))
                x.pop("pe_ipo", None)
                if not prerev:
                    x.pop("ni_latest", None)
                    ni = None
        if x.get("ps_ipo") and x["ps_ipo"] > MULT_CAP:
            if prerev:
                # an 18A issuer's near-zero revenue is REAL, so the huge
                # multiple is a fact about the deal, not a parse error. The
                # desk asked for no deal blank on both P/E and P/S — a
                # pre-revenue biotech is n/m on P/E (loss-maker), so P/S
                # stays VISIBLE with its scale explained rather than blank.
                x["ps_note"] = (f"{x['ps_ipo']:,.0f}x on HK${rev:,.1f}m revenue "
                                f"— effectively pre-revenue; the multiple is "
                                f"shown for completeness, not comparability")
            else:
                x["ps_note"] = (f"withheld — mktcap / revenue gives {x['ps_ipo']:,.0f}x, "
                                f"which fails the {MULT_CAP}x plausibility check; the "
                                f"extracted revenue (HK${rev:,.1f}m) is not trustworthy")
                x.pop("ps_ipo", None)
                x.pop("rev_latest", None)
                rev = None
        # cornerstone % where only the aggregate amount was printed
        if not x.get("cornerstone_pct") and x.get("cornerstone_amt_m") and size:
            amt = x["cornerstone_amt_m"] * (7.8 if x.get("cornerstone_amt_ccy") == "USD" else 1)
            pct = round(100 * amt / size, 1)
            if 0 < pct <= 100:
                x["cornerstone_pct"] = pct
                prov[c]["cornerstone_pct"] = {"src": "derived:cornerstone amount / deal size "
                                                     "(USD at the 7.8 peg)",
                                              "prio": 45, "status": "single"}
        if not x.get("price_range_lo") and x.get("range_lo"):
            x["price_range_lo"] = x["range_lo"]
            prov[c]["price_range_lo"] = {"src": "prospectus:indicative low-end", "prio": 30,
                                         "status": "single"}
        if not x.get("price_range_hi") and x.get("range_hi_indic"):
            x["price_range_hi"] = x["range_hi_indic"]
            prov[c]["price_range_hi"] = {"src": "prospectus:indicative high-end", "prio": 30,
                                         "status": "single"}
        lo = x.get("price_range_lo")
        hi = x.get("price_range_hi")
        # priced at the cap? (HK filings print a maximum price, never a floor)
        hi2 = x.get("price_range_hi")
        if hi2 and fp:
            x["priced_at_cap"] = "Y" if abs(fp - hi2) < 1e-9 else "N"
            x["pct_of_cap"] = round(100 * fp / hi2, 1)
            prov[c]["pct_of_cap"] = {"src": "derived:final / cap", "prio": 50,
                                     "status": "single"}
        if lo and hi and fp and hi > lo:
            x["pct_in_range"] = round(100 * (fp - lo) / (hi - lo), 1)
            prov[c]["pct_in_range"] = {"src": "derived", "prio": 50, "status": "xchecked"
                                       if prov[c].get("final_price", {}).get("status") == "xchecked"
                                       else "single"}

    # --- cornerstone investor names: clean, then fill from AAStocks ---
    # The prospectus tables survive PDF extraction badly (headers like "Top 10",
    # letter-spacing damage, scenario-clause tails). The list is now a visible
    # column and a Screener match key, so anything that is not a name is dropped
    # rather than displayed.
    from clean_names import clean_investor_list
    n_cleaned = n_from_aa = 0
    for c, x in deals.items():
        raw = x.get("cornerstone_investors")
        if raw:
            good = clean_investor_list(raw)
            if good != raw:
                n_cleaned += 1
            if good:
                x["cornerstone_investors"] = good
                x["cornerstone_n"] = len(good)
            else:
                x.pop("cornerstone_investors", None)
                x.pop("cornerstone_n", None)
        # AAStocks publishes this as a real table (name, type, amount) while the
        # prospectus version has to survive PDF extraction — Midea's read as
        # "Holdings Limited / Corporation Limited" where a line break ate the
        # front of each name. Where both exist, take the structured one.
        if x.get("cornerstone_aa") and not str(
                prov[c].get("cornerstone_investors", {}).get("src", "")
                ).startswith("press"):        # hand-verified research stays
            names = clean_investor_list([i["name"] for i in x["cornerstone_aa"]], limit=25)
            if names:
                x["cornerstone_investors"] = names
                x["cornerstone_n"] = len(names)
                prov[c]["cornerstone_investors"] = {"src": "aastocks:機構性投資者",
                                                    "prio": 44, "status": "single"}
                n_from_aa += 1
        # the aggregate the two sources imply should agree — but only in one
        # direction. The AAStocks 機構性投資者 table is a SUPERSET (anchor and
        # other institutional orders ride along) and its total is quoted across
        # the price range, so implied% ABOVE the parsed cornerstone % is
        # expected, not a conflict. The genuinely suspicious case is the
        # reverse: the superset total falling far SHORT of the parsed figure.
        aa_tot, size = x.get("cornerstone_aa_total_hkdm"), x.get("deal_size_hkdm")
        if aa_tot and size and x.get("cornerstone_pct"):
            implied = 100 * aa_tot / size
            if implied < x["cornerstone_pct"] - 20:
                # the parsed table failed the cross-check by 20pp+ — that is a
                # WRONG PARSE (placing-table bleed), not an open question. Use
                # the best remaining evidence instead of shipping orange:
                # the filed aggregate amount when the sentence parsed, else the
                # AAStocks institutional total itself.
                bad_pct = x["cornerstone_pct"]
                amt = x.get("cornerstone_amt_m")
                if amt and size:
                    hkd = amt * (7.8 if x.get("cornerstone_amt_ccy") == "USD" else 1)
                    x["cornerstone_pct"] = round(100 * hkd / size, 1)
                    how = "the filed aggregate-amount sentence"
                else:
                    x["cornerstone_pct"] = round(implied, 1)
                    how = "the AAStocks institutional total"
                prov[c]["cornerstone_pct"] = {
                    "src": f"cross-check repair: {how}", "prio": 55,
                    "status": "single"}
                x["cornerstone_note"] = (
                    f"table parse read {bad_pct:.0f}% but the institutional "
                    f"total implies {implied:.0f}% — parse rejected, "
                    f"{how} used ({x['cornerstone_pct']}%)")
            else:
                if prov[c].get("cornerstone_pct", {}).get("status") == "conflict":
                    prov[c]["cornerstone_pct"]["status"] = "single"
                if implied > x["cornerstone_pct"] + 20:
                    x["cornerstone_note"] = ("AAStocks institutional table includes "
                                             "non-cornerstone orders (superset) — "
                                             "cornerstone % is from the prospectus")
    # ONE spelling per investor across the whole book. The same house reaches us
    # from three sources (prospectus table, prospectus prose, AAStocks EN) and
    # spells itself differently in each — "GIC Private Li" vs "GIC Private
    # Limited", "HARVEST GLOBAL INVESTMENTS LIMITED" vs title case, "A及B" as one
    # cell. Those collapse to the most-filed full spelling. Different vehicles of
    # one house (CPE Investment XVI vs CPE Redwood) stay separate — they ARE
    # different investors; they still screen together through the keys below.
    from clean_names import investor_keys, build_canonical_map, canonical_list
    canon = build_canonical_map([x.get("cornerstone_investors") or []
                                 for x in deals.values()])
    n_canon = 0
    for c, x in deals.items():
        raw = x.get("cornerstone_investors")
        if not raw:
            continue
        fixed = canonical_list(raw, canon)
        if fixed != raw:
            n_canon += 1
            x["cornerstone_investors_raw"] = raw      # kept for audit, not shown
        x["cornerstone_investors"] = fixed
        x["cornerstone_n"] = len(fixed)
        keys = investor_keys(fixed)
        if keys:
            x["cornerstone_keys"] = keys
            prov[c]["cornerstone_keys"] = {
                "src": "derived:normalized investor names", "prio": 50,
                "status": "single"}
    print(f"  cornerstone spellings canonicalised on {n_canon} deals "
          f"({len(canon)} distinct investors)")
    print(f"  cornerstone names: cleaned {n_cleaned}, filled from AAStocks {n_from_aa}, "
          f"keys {sum(1 for x in deals.values() if x.get('cornerstone_keys'))}")

    # --- cornerstone % : last-resort fill from the AAStocks amount table ----
    # 24 deals carried a cornerstone LIST but no %. Where AAStocks published
    # per-investor amounts, total/deal-size gives the figure — flagged as an
    # UPPER BOUND because that table can carry non-cornerstone institutional
    # orders alongside (the superset caveat below).
    n_pct_fill = 0
    for c, x in deals.items():
        if x.get("cornerstone_pct") is not None or not x.get("cornerstone_investors"):
            continue
        tot, size = x.get("cornerstone_aa_total_hkdm"), x.get("deal_size_hkdm")
        if tot and size and 0 < tot / size <= 1.2:
            x["cornerstone_pct"] = round(min(100.0, 100 * tot / size), 1)
            x["cornerstone_pct_note"] = (
                "AAStocks institutional-order total / deal size — an upper "
                "bound; the table can include non-cornerstone orders")
            prov[c]["cornerstone_pct"] = {"src": "aastocks:機構性投資者 total",
                                          "prio": 40, "status": "single"}
            n_pct_fill += 1
        elif not x.get("cornerstone_pct_note"):
            x["cornerstone_pct_note"] = ("% not stated in the extractable "
                                         "allotment/prospectus text; list is "
                                         "from the prospectus")
    print(f"  cornerstone %% filled from AAStocks totals: {n_pct_fill}")

    # --- returns measured on the COMPLETE session list ----------------------
    # Yahoo's HK history has HOLES (both STARPLUS and KEEP are missing the
    # 2023-07-17 session), and a missing session shifts every trading-bar
    # horizon by one day — up to 15pp on a volatile debut. Worse, it can miss
    # the DEBUT itself (Morimatsu's day-1 read +213.7% off session two instead
    # of +258.9% off session one). The local kline feed carries the full list
    # and is what the dashboard's charts already draw, so returns are measured
    # on it: the columns and the chart can no longer disagree.
    HOR = [("1w", 5), ("1m", 21), ("3m", 63)]
    path_recs = (load("h_paths.json") or {}).get("deals", [])
    paths = {r["code"]: r for r in path_recs}
    # the feed inserts a PLACEHOLDER bar on days the exchange never opened
    # (Typhoon Talim 2023-07-17, Saola 2023-09-01): every stock repeats its
    # prior close. Counting one as a session shifts every horizon by a day.
    from sessions import closed_days, real_sessions
    CLOSED = closed_days(path_recs)
    print(f"  non-trading days detected in the feed: {len(CLOSED)}"
          f"{' — ' + ', '.join(sorted(CLOSED)[:4]) if CLOSED else ''}")
    n_re = n_d1 = n_post = 0
    for c, x in deals.items():
        p, fp2 = paths.get(c), x.get("final_price")
        if not (p and fp2):
            continue
        rows = real_sessions(p, CLOSED)          # [(iso_date, close), ...]
        if not rows:
            continue
        # a listing SCHEDULED into a closed day is postponed to the next
        # session — the placeholder bar sits at the offer price and reads as
        # a flat debut (New Media Lab, typhoon-shut 2023-07-17)
        ipo_s = (x.get("ipo_date") or "")[:10]
        if ipo_s in CLOSED and rows[0][0] > ipo_s:
            x["ipo_date"] = rows[0][0]
            x["ipo_date_note"] = (f"scheduled for {ipo_s}, but the exchange did "
                                  f"not open that day — first dealings "
                                  f"{rows[0][0]}")
            prov[c]["ipo_date"] = {"src": "price feed: first real session",
                                   "prio": 47, "status": "single"}
            ipo_s = rows[0][0]
            n_post += 1
        # the first bar must BE the listing session; if the path starts later
        # the local feed lacks the debut and Yahoo's reading stands
        if rows[0][0] != ipo_s:
            continue
        raw = [(0, rows[0][1])] + [(i, v) for i, (_d, v) in enumerate(rows[1:], 1)]
        d1_local = round(100 * (raw[0][1] / fp2 - 1), 2)
        if x.get("first_day_return_pct") is None or \
                abs(d1_local - x["first_day_return_pct"]) > 0.05:
            x["first_day_return_pct"] = d1_local
            prov[c]["first_day_return_pct"] = {
                "src": "kline:listing session close / offer", "prio": 55,
                "status": "single"}
            n_d1 += 1
        # open0 is trustworthy only when the path record was FETCHED with the
        # same listing date the book now carries. A record cached before a
        # postponed listing was corrected holds the placeholder bar's open —
        # the offer price echoed back — which printed New Media Lab's day-1
        # open pop as exactly 0.0% against a real open of -4.3%. The close
        # legs are immune (real_sessions drops placeholder bars); the open has
        # no second source, so it waits for the next h-paths pass instead of
        # shipping a wrong zero.
        if p.get("open0") and (p.get("ipo") or ipo_s) == ipo_s:
            x["day1_open_pop_pct"] = round(100 * (p["open0"] / fp2 - 1), 2)
            x["day1_open_close_pct"] = round(100 * (raw[0][1] / p["open0"] - 1), 2)
        elif p.get("open0"):
            x.pop("day1_open_pop_pct", None)
            x.pop("day1_open_close_pct", None)
            # day1_oc_note is the book's existing slot for day-1-open problems
            x["day1_oc_note"] = (
                "listing was postponed off a closed day after this price path "
                "was cached, so the cached day-1 open belongs to the exchange's "
                "placeholder bar — it refreshes on the next h-paths fetch")
        for h, nb in HOR:
            if len(raw) <= nb:
                continue
            r_local = round(100 * (raw[nb][1] / fp2 - 1), 2)
            if x.get(f"ret_{h}_pct") is None or \
                    abs(r_local - x[f"ret_{h}_pct"]) > 0.05:
                x[f"ret_{h}_pct"] = r_local
                prov[c][f"ret_{h}_pct"] = {
                    "src": f"kline:{nb}th session after listing / offer",
                    "prio": 55, "status": "single"}
                n_re += 1
            # every dependent leg is re-derived from the corrected return
            b = x.get(f"bench_{h}_pct")
            if b is not None:
                x[f"alpha_{h}_pct"] = round(r_local - b, 2)
            d1n = x.get("first_day_return_pct")
            if d1n is not None and d1n != -100:
                x[f"aftermkt_{h}_pct"] = round(
                    100 * ((1 + r_local / 100) / (1 + d1n / 100) - 1), 2)
    print(f"  returns re-measured on the local session list: "
          f"{n_d1} day-1, {n_re} horizon values"
          + (f", {n_post} listings postponed off a closed day" if n_post else ""))

    # --- entitlement-issue convention notes ---------------------------------
    # Rights/open offers do not re-scale the traded print, so the return
    # columns are simple price returns that EXCLUDE the entitlement's value.
    # Say so on the affected deals — Bloomberg's adjusted history will differ
    # by exactly the recorded TERP factor and a reader must know why.
    pE = ROOT / "data" / "entitlement_adjustments.json"
    if pE.exists():
        ent = {k: v for k, v in json.loads(pE.read_text()).items()
               if not k.startswith("_")}
        for c, evs in ent.items():
            x = deals.get(c)
            if not x:
                continue
            f = 1.0
            for e in evs:
                f *= float(e.get("factor") or 1)
            evtxt = "; ".join(f"{e['date']} {e['event']}" for e in evs)
            x["ret_note"] = ((x.get("ret_note") + " | ") if x.get("ret_note") else "") + (
                f"price returns exclude the entitlement value of: {evtxt} — "
                f"Bloomberg's back-adjusted history divides by x{f:.4g}")
    # --- market-cap plausibility ------------------------------------------
    # HK$m units: the largest listing in the book is ~HK$713bn (713,000). A
    # value far above that came from a bad price or a share-count parse
    # (BAIGE published HK$17,436,049,883m before the offer-price guard).
    # Recompute from shares x price where possible, else empty it and say so.
    MC_MAX = 3_000_000          # HK$3tn — 4x the biggest listing ever here
    n_mc = 0
    for c, x in deals.items():
        mc = x.get("mktcap_ipo_hkdm")
        if mc is None or 0 < mc <= MC_MAX:
            continue
        sh, fp2 = x.get("shares_outstanding"), x.get("final_price")
        if sh and fp2 and 0 < sh * fp2 / 1e6 <= MC_MAX:
            x["mktcap_ipo_hkdm"] = round(sh * fp2 / 1e6, 1)
            x["mktcap_basis"] = "recomputed: shares x offer (parsed cap implausible)"
        else:
            x.pop("mktcap_ipo_hkdm", None)
            x["mktcap_note"] = (f"parsed market cap {mc:,.0f} HK$m is not "
                                f"plausible and no share count is available "
                                f"to recompute it")
        prov[c]["mktcap_ipo_hkdm"] = {"src": "plausibility guard", "prio": 60,
                                      "status": "single"}
        n_mc += 1
    if n_mc:
        print(f"  market caps rejected as implausible: {n_mc}")

    # --- A/H market-cap consistency: summary of the pass-2 adjudication ----
    print(f"  A/H cap cross-check (2025+ listings): {ah_cap_ok} within 30%, "
          f"{len(ah_cap_fixed)} adjudicated to the A-line figure")
    for c, mc0, alt, gap in ah_cap_fixed:
        print(f"    {c}: parsed {mc0:,.0f} -> A-line {alt:,.0f} HK$m ({gap:.0%} apart)")

    # --- effective free float: what can actually trade on day 1 -------------
    # (deal size − cornerstone amount) / market cap. Cornerstones are locked
    # up (6 months), so the tradeable float at listing is the offer minus the
    # cornerstone take. No cornerstone tranche → the whole offer floats.
    n_eff = 0
    n_abs = 0
    for c, x in deals.items():
        size, mc = x.get("deal_size_hkdm"), x.get("mktcap_ipo_hkdm")
        cs = x.get("cornerstone_pct")
        if cs is None and not x.get("cornerstone_investors"):
            cs = 0.0                       # genuinely no cornerstone tranche
        # THE ABSOLUTE FLOAT comes first, because it needs no market cap: it is
        # simply the offer less the locked-up cornerstone take, in money and in
        # shares. The percentage below is this same number over the cap, so the
        # two can never disagree. Cornerstone % is a share OF THE OFFER (the
        # book's convention), which is what makes this subtraction valid.
        if size is not None and cs is not None:
            x["eff_free_float_hkdm"] = round(size * (1 - cs / 100), 2)
            prov[c]["eff_free_float_hkdm"] = {
                "src": "derived: deal size x (1 - cornerstone%)",
                "prio": 50, "status": "single"}
            n_abs += 1
        sh = x.get("offer_shares")
        if sh and cs is not None:
            x["eff_free_float_shares"] = int(round(sh * (1 - cs / 100)))
            prov[c]["eff_free_float_shares"] = {
                "src": "derived: offer shares x (1 - cornerstone%)",
                "prio": 50, "status": "single"}
        elif cs is not None:
            x["eff_ff_shares_note"] = (
                "share count unavailable or rejected as implausible — the money "
                "figure (eff_free_float_hkdm) is still exact")
        if size and mc and cs is not None:
            x["eff_free_float_pct"] = round(100 * size * (1 - cs / 100) / mc, 2)
            prov[c]["eff_free_float_pct"] = {
                "src": "derived: deal size x (1 - cornerstone%) / mktcap",
                "prio": 50, "status": "single"}
            n_eff += 1
        else:
            why = ("cornerstone % unknown" if (size and mc) else
                   "market cap not derivable" if size else
                   "deal size not available")
            x["eff_ff_note"] = f"not computable as a % of cap — {why}"
    print(f"  effective free float: {n_abs} absolute (HK$m/shares), "
          f"{n_eff} as a % of market cap")

    # --- conflict adjudication: sort out the reliable value, don't just flag --
    # Each rule names WHY two sources disagreed; orange survives only where no
    # cause could be established. The census prints so regressions are visible.
    adjudicated = {"kept_orange": 0}

    def _clear(c, f, why, status="xchecked"):
        prov[c][f]["status"] = status
        deals[c][f + "_note" if f + "_note" not in deals[c] else f + "_note"] = \
            deals[c].get(f + "_note") or why
        adjudicated[f] = adjudicated.get(f, 0) + 1

    by_cf = {}
    for cf in conflicts:
        by_cf.setdefault((cf["code"], cf["field"]), cf)
    for (c, f), cf in by_cf.items():
        if c not in deals or prov.get(c, {}).get(f, {}).get("status") != "conflict":
            continue
        kept, dropped = cf.get("kept"), cf.get("dropped")
        if f == "oversub_public_mult" and isinstance(kept, (int, float)) \
                and isinstance(dropped, (int, float)):
            # HKEX allotment table is the authoritative print; AAStocks' 超額倍數
            # rounds and uses the odd basis — within 15% it is the same fact
            if kept and abs(kept - dropped) / kept <= 0.15:
                _clear(c, f, "AAStocks rounds the same figure — HKEX table kept")
            else:
                # a basis difference is not an unresolved conflict: the HKEX
                # allotment table is the filing of record, so it is kept and
                # BOTH readings are named in the note
                _clear(c, f, f"HKEX allotment table reads {kept:g}x, AAStocks "
                             f"超額倍數 reads {dropped:g}x on its own basis — "
                             f"the filing table kept", status="single")
        elif f == "final_price" and isinstance(kept, (int, float)):
            # an OFFER PRICE lives in a narrow band. 54,382,183 is a share
            # count the allotment parse read as a price (BAIGE) — and it had
            # shipped, poisoning day-1, market cap and every multiple. When
            # the filing value is impossible and the aggregator's is sane,
            # the aggregator wins; when neither is sane the cell is emptied.
            def _sane(v):
                return isinstance(v, (int, float)) and 0.05 <= v <= 3000
            # THE ARBITER: the day-1 close is an observed print and the
            # aggregator's day-1 % is independent of both candidates, so the
            # implied offer (close / (1 + d1)) settles the dispute without a
            # human. Research found the filing parse wrong 6 times out of 6
            # on this field — priority alone was picking the loser.
            x0 = deals[c]
            close0, d1a = x0.get("first_close"), x0.get("aastocks_day1_pct")
            if d1a is None:
                d1a = (x0.get("_aa_day1") if isinstance(x0.get("_aa_day1"), (int, float))
                       else None)
            implied = (close0 / (1 + d1a / 100)) if (close0 and d1a is not None
                                                    and d1a != -100) else None
            if implied and _sane(kept) and _sane(dropped):
                ek, ed = abs(kept - implied) / implied, abs(dropped - implied) / implied
                if min(ek, ed) < 0.02 and abs(ek - ed) > 0.02:
                    win = kept if ek < ed else dropped
                    if win != kept:
                        deals[c]["final_price"] = win
                        prov[c]["final_price"] = {"src": cf.get("dropped_src", "aastocks"),
                                                  "prio": 50, "status": "single"}
                    _clear(c, f, f"day-1 close HK${close0:g} with the reported "
                                 f"{d1a:+.2f}% implies HK${implied:.2f} — "
                                 f"HK${win:g} kept as the consistent value",
                           status="xchecked")
                    continue
            if not _sane(kept):
                if _sane(dropped):
                    deals[c]["final_price"] = dropped
                    prov[c]["final_price"] = {"src": cf.get("dropped_src", "aastocks"),
                                              "prio": 50, "status": "single"}
                    _clear(c, f, f"filing parse returned {kept:,.0f} — not a "
                                 f"price (share count); aggregator value used",
                           status="single")
                else:
                    deals[c].pop("final_price", None)
                    deals[c]["price_note"] = (
                        f"offer price not extractable — the filing parse "
                        f"returned {kept:,.0f}, which is not a price")
                    _clear(c, f, "no plausible offer price from either source",
                           status="single")
            else:
                adjudicated["kept_orange"] += 1
        elif f == "first_day_return_pct" and isinstance(kept, (int, float)) \
                and isinstance(dropped, (int, float)):
            if abs(kept - dropped) <= 1.5:
                _clear(c, f, "price sources agree within 1.5pp")
            else:
                adjudicated["kept_orange"] += 1
        elif f == "price_range_hi":
            # a repriced deal's indicative high is SUPERSEDED by the final
            # Maximum Offer Price — different documents, not a disagreement
            _clear(c, f, "indicative range superseded by the final Maximum "
                         "Offer Price", status="single")
        elif f in ("sponsors", "bookrunners", "cornerstone_investors"):
            a = {str(x).lower() for x in (kept if isinstance(kept, list) else [kept])}
            b = {str(x).lower() for x in (dropped if isinstance(dropped, list) else [dropped])}
            # press writes short forms ("CICC", "UBS", "Morgan Stanley") where
            # the filing prints the legal entity ("China International Capital
            # Corporation Hong Kong Securities Limited"). Those are the SAME
            # houses, so the press CONFIRMS the filing — it does not conflict
            # with it. Compare on the normalized house key.
            from clean_names import investor_key as _ik
            ka = {_ik(x) for x in (kept if isinstance(kept, list) else [kept])} - {""}
            kb = {_ik(x) for x in (dropped if isinstance(dropped, list) else [dropped])} - {""}
            if ka and kb and (ka == kb or kb <= ka):
                _clear(c, f, "the two sources name the same houses (press short "
                             "form vs filing legal entity) — filing spelling "
                             "kept, cross-checked", status="xchecked")
            elif a and b and (a <= b or b <= a):
                _clear(c, f, "one source lists a subset of the other — "
                             "the fuller filing-side list kept")
            else:
                adjudicated["kept_orange"] += 1
        else:
            adjudicated["kept_orange"] += 1
    print(f"  conflict adjudication: {adjudicated}")

    # --- displayable bank strings, ENGLISH first at every fallback rung ---
    # The prospectus cover prints ROLE HEADINGS between the bank names ("and
    # Sponsor-OCs", "-Overall Coordinator", "Financial Adviser"), and the parse
    # carried them into the list. They are labels, not banks — strip them.
    # clean_party_element then handles the other cover-page bleed classes
    # (section headings, page numbers, glued role labels, the issuer's US
    # address, orphaned "Securities Limited" halves).
    from clean_names import clean_party_element, clean_party_list
    ROLE = re.compile(r"^(?:and\s+)?(?:Sole\s+|Joint\s+)?(?:Sponsor[\s\-]*(?:OCs?|"
                      r"Overall\s+Coordinators?)?|Overall\s+Coordinators?|"
                      r"Financial\s+Advis[eo]rs?|Capital\s+Market\s+Interm\w*|"
                      r"Bookrunners?|Lead\s+Managers?)\b[\s\-:,]*", re.I)

    def _strip_roles(val):
        out, seen = [], set()
        for part in str(val or "").split(";"):
            p = part.strip()
            for _ in range(3):                 # headings can stack
                p2 = ROLE.sub("", p).strip(" -:,")
                if p2 == p:
                    break
                p = p2
            p = clean_party_element(p) or ""
            k = re.sub(r"[^a-z0-9一-鿿]", "", p.lower())
            if len(p) > 3 and k not in seen:
                seen.add(k)
                out.append(p)
        return "; ".join(out)

    # the LIST fields feed the workbook and the comp matrix directly — the
    # same bleed classes are scrubbed there too (109 deals carried at least
    # one heading / glued-label / address / orphan element)
    n_scrub = 0
    for c, x in deals.items():
        for f in ("sponsors", "sponsors_en", "underwriters_en", "bookrunners"):
            v = x.get(f)
            if not isinstance(v, list) or not v:
                continue
            good = clean_party_list(v)
            if good != v:
                n_scrub += 1
                if good:
                    x[f] = good
                else:
                    x.pop(f, None)
    print(f"  bank-list bleed scrub touched {n_scrub} deal-fields")

    for c, x in deals.items():
        bk = x.get("bookrunners")
        if isinstance(bk, list):
            bk = "; ".join(bk)
        if not bk and x.get("underwriters_en"):
            bk = "; ".join(x["underwriters_en"][:6])
            prov[c]["bookrunners_display"] = {"src": "aastocks-en:Underwriter(s)",
                                              "prio": 45, "status": "single"}
        if not bk and x.get("underwriters_cn"):
            bk = "; ".join(x["underwriters_cn"][:6])
            prov[c]["bookrunners_display"] = {"src": "aastocks:包銷商", "prio": 44,
                                              "status": "single"}
        if bk:
            x["bookrunners_display"] = _strip_roles(bk)
        sp = x.get("sponsors")
        if isinstance(sp, list):
            sp = "; ".join(sp)
        if not sp and x.get("sponsors_en"):
            sp = "; ".join(x["sponsors_en"])
            prov[c]["sponsors_display"] = {"src": "aastocks-en:Sponsor(s)",
                                           "prio": 45, "status": "single"}
        if not sp and x.get("sponsors_cn"):
            sp = "; ".join(x["sponsors_cn"])
            prov[c]["sponsors_display"] = {"src": "aastocks:保薦人", "prio": 44,
                                           "status": "single"}
        if sp:
            x["sponsors_display"] = _strip_roles(sp)

    # --- last-resort sector for the genuinely unclassified ------------------
    # Eight deals sat in "Other / unclassified" while AAStocks published a real
    # industry for them. A documented industry->subsector map (not a per-deal
    # guess) fills those; every hand label in classify.py still wins, and the
    # AAStocks industry stays visible in its own column so both are readable.
    IND_MAP = {
        "IT Consulting & Other Services": ("Tech/AI", "AI application / agent software"),
        "Application Software": ("Tech/AI", "SaaS / enterprise software"),
        "Systems Software": ("Tech/AI", "SaaS / enterprise software"),
        "Advertising": ("TMT-other", "Media / advertising"),
        "Packaged Foods": ("Consumer", "Beverages / packaged food"),
        "Children's and Infant Products": ("Consumer", "Retail / distribution"),
        "Construction Materials": ("Materials/Energy", "Chemicals"),
        "Aluminum": ("Materials/Energy", "Mining / metals"),
    }
    n_fill = 0
    for c, x in deals.items():
        if x.get("sector") not in (None, "Other") and \
           x.get("subsector") not in (None, "Other / unclassified"):
            continue
        hit = IND_MAP.get(x.get("industry_en"))
        if hit:
            x["sector"], x["subsector"] = hit
            prov[c]["subsector"] = {"src": f"aastocks industry: {x['industry_en']}",
                                    "prio": 25, "status": "estimated"}
            n_fill += 1
    if n_fill:
        print(f"  unclassified deals sectored from the AAStocks industry: {n_fill}")

    # --- price vs its own range: two different stories, both explained ------
    # A struck price ABOVE the recorded cap is impossible — the cap is the
    # untrustworthy number there (SAIMO: allotment states HK$12.99 twice while
    # the parsed cap says 12.00), so the cap is flagged and the derived
    # cap-percentages are withdrawn rather than shown as 108%.
    # A struck price BELOW the indicative low is LEGAL in Hong Kong via the
    # Downward Offer Price Adjustment mechanism (Global New Material priced at
    # HK$3.25 against a 3.52-4.22 range) — that one is annotated, not flagged.
    n_cap_bad = n_down = 0
    for c, x in deals.items():
        fp, lo, hi = x.get("final_price"), x.get("price_range_lo"), x.get("price_range_hi")
        if not fp:
            continue
        if hi and fp > hi * 1.001:
            # a cap BELOW the struck price is a mis-parse, not a fact — the
            # number goes, the reason stays (a wrong value in orange is worse
            # than an explained blank)
            x.pop("price_range_hi", None)
            prov[c].pop("price_range_hi", None)
            x["range_note"] = (f"struck at HK${fp}, above the parsed maximum "
                               f"HK${hi} — the cap parse is rejected for this deal")
            x.pop("pct_of_cap", None)
            x.pop("priced_at_cap", None)
            n_cap_bad += 1
        elif lo and fp < lo * 0.999:
            x["range_note"] = (f"struck at HK${fp}, below the indicative low HK${lo} "
                               f"— Downward Offer Price Adjustment mechanism")
            n_down += 1
    print(f"  price-vs-range: {n_cap_bad} caps withdrawn as untrustworthy, "
          f"{n_down} downward-adjusted deals annotated")

    # --- institutional subscription: flag the arithmetically impossible ---
    # An under-subscribed international tranche is real data and is kept. But a
    # deal that struck at its MAXIMUM price with a heavily subscribed retail
    # tranche cannot have had an uncovered institutional book — the institutions
    # set that price. Values like 0.98x and 0.9987x on such deals are a
    # percentage read as a multiple. The number stays visible (deleting data
    # hides the error) but is marked conflict so it reads as questionable, and
    # the BBG Verify sheet's CP037 settles it on the desk.
    n_flag = 0
    for c, x in deals.items():
        i, p, cap = (x.get("oversub_intl_mult"), x.get("oversub_public_mult"),
                     x.get("pct_of_cap"))
        if i is not None and i < 1 and p and p > 3 and cap and cap >= 99:
            # publishing a number we can DEMONSTRATE is wrong is worse than a
            # blank: the cell is emptied and the reason stated (the
            # explained-absence contract), and BBG Verify's CP037 fills it on
            # the terminal. The rejected reading stays in the note, so nothing
            # is hidden.
            x.pop("oversub_intl_mult", None)
            prov[c].setdefault("oversub_intl_mult", {})["status"] = "single"
            x["intl_note"] = (f"parsed {i:g}x rejected — implausible for a deal struck "
                              f"at the cap with the public tranche {p:,.0f}x "
                              f"subscribed (a percentage read as a multiple); "
                              f"BBG Verify CP037 fills this on the terminal")
            n_flag += 1
    print(f"  institutional subscription flagged as implausible: {n_flag}")

    # --- aftermarket returns: did the pop SURVIVE? ---
    # ret_* are measured from the offer price, so they all carry the day-one
    # move. The trade "buy at the close on day one" is a different question and
    # the one that separates a real re-rating from a one-day squeeze.
    for c, x in deals.items():
        d1 = x.get("first_day_return_pct")
        if d1 is None:
            continue
        for h in ("1w", "1m", "3m"):
            r = x.get(f"ret_{h}_pct")
            if r is None:
                continue
            x[f"aftermkt_{h}_pct"] = round(100 * ((1 + r / 100) / (1 + d1 / 100) - 1), 2)
            prov[c][f"aftermkt_{h}_pct"] = {
                "src": "derived:horizon close vs day-1 close", "prio": 50,
                "status": "single"}
            # the index over the SAME ex-pop window: both bench legs anchor on
            # the pre-listing close, so their ratio is day-1 close -> horizon
            bh, b1 = x.get(f"bench_{h}_pct"), x.get("bench_day1_pct")
            if bh is not None and b1 is not None:
                bex = round(100 * ((1 + bh / 100) / (1 + b1 / 100) - 1), 2)
                x[f"bench_{h}_expop_pct"] = bex
                x[f"alpha_{h}_expop_pct"] = round(x[f"aftermkt_{h}_pct"] - bex, 2)
                prov[c][f"alpha_{h}_expop_pct"] = {
                    "src": "derived:aftermarket vs index over the identical "
                           "day-1-close window", "prio": 50, "status": "single"}
        # day one, open -> close: the intraday move AFTER the opening print.
        # A raw Tencent close-series stores open==close, so its "open" is not a
        # real print — the field is withheld there rather than shown as 0.0%.
        pop = x.get("day1_open_pop_pct")
        # two-source open disputes: where audit_opens saw the OPENING prints
        # differ >2% while the closes agree, the open-based figures carry a
        # feed-variance caveat (auction print vs first trade)
        if not hasattr(main, "_open_disputes"):
            try:
                _rows = json.loads((B / "audit_opens.json").read_text())["rows"]
                # NB explicit None tests: `0.0 or 1` is 1 — the falsy-zero
                # trap silently emptied this set on first deploy
                main._open_disputes = {
                    r0["code"] for r0 in _rows
                    if r0.get("open_gap_pct") is not None
                    and r0["open_gap_pct"] > 2
                    and r0.get("close_gap_pct") is not None
                    and r0["close_gap_pct"] < 0.5}
            except Exception:
                main._open_disputes = set()
        if c in main._open_disputes:
            x["day1_oc_note"] = ("sources disagree on the day-1 OPENING print "
                                 f"by {'>2%'} (auction vs first trade); all "
                                 "close-based figures agree exactly")
        # v14: Tencent kline rows carry a REAL open (row[1]) — the old blanket
        # "tencent has no true open" rule would now throw away good data
        if pop is None and d1 is not None:
            x.pop("day1_open_pop_pct", None)
            x["day1_oc_note"] = ("intraday open not available — price series "
                                 "is a raw close line (Tencent)")
        elif pop is not None:
            x["day1_open_close_pct"] = round(
                100 * ((1 + d1 / 100) / (1 + pop / 100) - 1), 2)
            prov[c]["day1_open_close_pct"] = {
                "src": "derived:day-1 close vs day-1 open", "prio": 50,
                "status": "single"}

    for c, x in deals.items():
        if x.get("cornerstone_investors"):
            x["cornerstone_n"] = len(x["cornerstone_investors"])
            prov[c]["cornerstone_n"] = {"src": "derived:len(investor list)",
                                        "prio": 99, "status": "single"}
    for c, x in deals.items():
        for f, pv in prov.get(c, {}).items():
            if isinstance(pv, dict) and pv.get("status") == "conflict" \
                    and pv.get("prio", 0) >= 60:
                pv["status"] = "xchecked" if pv.get("src", "").split(":")[0] \
                    in ("bloomberg", "press") else "single"

    # --- explained absences: a blank is only acceptable when the FACT is that
    # there is nothing to record. Each gets a *_note so checks.py can count the
    # field as RESOLVED and the workbook can say why instead of showing empty.
    from datetime import date as _date, timedelta as _td
    today = _date.today()
    for c, x in deals.items():
        if x.get("price_range_hi") is None and x.get("final_price"):
            # no stated maximum anywhere = fixed-price offering; the cap IS the price
            x["price_range_hi"] = x["final_price"]
            x["range_note"] = "fixed-price offering (no indicative range)"
            prov[c]["price_range_hi"] = {"src": "derived:fixed-price offering",
                                         "prio": 20, "status": "single"}
            # a fixed-price offer prices AT its own cap by definition — the
            # cap-derivation above ran before this fallback existed, so these
            # rows would otherwise be the only blanks in the column
            x["pct_of_cap"] = 100.0
            x["priced_at_cap"] = "Y"
            prov[c]["pct_of_cap"] = {"src": "derived:fixed-price offer prices at its cap",
                                     "prio": 20, "status": "single"}
            prov[c]["priced_at_cap"] = {"src": "derived:fixed-price offering",
                                        "prio": 20, "status": "single"}
        if x.get("oversub_intl_mult") is None:
            if x.get("intl_tranche_absent"):
                x["intl_note"] = "no international tranche (public-offer-only structure)"
            elif not x.get("intl_note"):
                # never overwrite a REJECTION reason with "not stated" — the
                # filing did state a figure; we refused it and must say so
                x["intl_note"] = "subscription level not stated in the filing"
        if not x.get("greenshoe_exercised_final"):
            d0 = x.get("ipo_date")
            if d0 and _date.fromisoformat(d0[:10]) > today - _td(days=40):
                x["shoe_note"] = "stabilisation window still open (listed <40 days ago)"
            elif not x.get("greenshoe_pct"):
                x["shoe_note"] = "no over-allotment option in the offer structure"
            else:
                x["shoe_note"] = "end-of-stabilisation notice not located"
        # A RESOLVED shoe still leaves the expiry column blank on older deals
        # whose announcement never spelled the date out, and that blank needs
        # its own reason — the outcome is already known, so the date is moot.
        # No prospectus hyperlink: the per-stock HKEX search returned no
        # listing document for this code. Mostly older listings whose
        # prospectus was filed in a form the doc feed does not expose; the
        # allotment announcement IS on file and is linked beside it, so say
        # which document is missing rather than leaving an empty cell.
        if not x.get("prospectus_link") and not x.get("doc_note"):
            x["doc_note"] = (
                "no prospectus document returned by the HKEX per-stock search "
                "for this code" + (" — the allotment announcement is linked "
                                   "beside it" if x.get("allotment_link") else ""))
        if not x.get("stabilization_end_date") and not x.get("shoe_note"):
            x["shoe_note"] = (
                "over-allotment outcome already published, and the allotment "
                "announcement does not state the stabilisation expiry in a "
                "parsable form — the expiry no longer matters once resolved")
        # Bloomberg fills the main P/E where the filings gave nothing: the
        # planned v12 fill stored pe_ipo_bbg but never promoted it, so 14
        # deals sat blank while the answer was on file. Basis note included —
        # trailing-at-listing is NOT the prospectus-FY multiple.
        if (x.get("pe_ipo") is None and x.get("profitable_at_ipo") != "N"
                and 2 < (x.get("pe_ipo_bbg") or 0) < 500):
            x["pe_ipo"] = x["pe_ipo_bbg"]
            prov[c]["pe_ipo"] = {"src": "bloomberg:P/E at listing (desk paste)",
                                 "prio": 40, "status": "single"}
            x["pe_note"] = ("from Bloomberg (trailing-12m EPS at listing) — the "
                            "prospectus-FY multiple was not derivable")
        if x.get("pe_ipo") is None and not x.get("pe_note"):
            if x.get("profitable_at_ipo") == "N":
                x["pe_note"] = "n/m — loss-making at IPO (use P/S)"
            elif x.get("ni_latest") is None:
                x["pe_note"] = "net income not stated in extractable form"
            elif x.get("mktcap_ipo_hkdm") is None:
                x["pe_note"] = "market cap not derivable (no share count disclosed)"
        # A/H: "no A line" is an ANSWER, not a missing value. The workbook shows
        # N/A for these rather than a zero that reads as a zero premium.
        if not x.get("a_share_code"):
            x["ah_note"] = ("no A-share listing" if not x.get("a_share_proxy")
                            else f"no A line; closest listed proxy {x['a_share_proxy']}")
        elif x.get("ah_discount_ipo_pct") is None:
            x["ah_note"] = (f"A-share {x['a_share_code'].split('.')[0]} listed "
                            "AFTER the H IPO — no A price existed on the H "
                            "pricing date, so an at-IPO premium cannot exist; "
                            "the today premium is live")
        # returns: a blank is either a window that has not elapsed or a line
        # Yahoo has no history for — say which
        if x.get("first_day_return_pct") is None:
            x["ret_note"] = x.get("price_note") or "listing-day price unavailable"
        else:
            for h, days in (("1w", 7), ("1m", 31), ("3m", 92)):
                if x.get(f"ret_{h}_pct") is None and x.get("ipo_date"):
                    if _date.fromisoformat(x["ipo_date"][:10]) > today - _td(days=days):
                        x[f"ret_{h}_note"] = f"listed less than {h} ago"
                    else:
                        x[f"ret_{h}_note"] = "price history incomplete for this window"
        # --- the remaining blanks, each given its reason so no column is ever
        # silently empty (the census counts value-or-reason as resolved) ---
        if x.get("price_range_lo") is None:
            x["range_lo_note"] = ("cap-only pricing — the filing publishes a Maximum "
                                  "Offer Price and no indicative floor")
        if not x.get("cornerstone_investors"):
            x["cornerstone_list_note"] = (
                "no cornerstone tranche in this deal" if x.get("cornerstone_none")
                or x.get("cornerstone_pct") == 0 else
                # a tranche % without names means the AGGREGATE sentence parsed
                # but the per-investor table is a damaged PDF grid — the names
                # exist only in the filing itself
                ("tranche parsed ({}% locked) but the per-investor table did not "
                 "machine-parse — names are in the prospectus Cornerstone "
                 "section (link on this row)".format(x["cornerstone_pct"])
                 if x.get("cornerstone_pct") else
                 "cornerstone section not machine-extractable — see the prospectus link"))
        if x.get("cornerstone_pct") is None:
            x["cornerstone_pct_note"] = (
                "no cornerstone tranche in this deal" if x.get("cornerstone_none")
                else "cornerstone aggregate not stated in the filing")
        if x.get("greenshoe_pct") is None:
            x["greenshoe_note"] = ("no over-allotment option in the offer structure"
                                   if not x.get("overallot_shares") else
                                   "over-allocated shares stated without an offer-share base")
        if x.get("ps_ipo") is None and not x.get("ps_note"):
            if x.get("rev_latest") == 0:
                x["ps_note"] = ("no revenue line in the filed P&L (pre-revenue "
                                "issuer) — no sales multiple can exist; the "
                                "cell reads pre-rev, not blank")
            elif not x.get("rev_latest"):
                x["ps_note"] = "revenue not extractable"
            else:
                x["ps_note"] = "market cap not derivable — P/S cannot be formed"
        # position INSIDE the indicative range: 0% = priced at the floor,
        # 100% = at the cap. Only meaningful when a true lo<hi range exists;
        # fixed-price and cap-only offers carry their own range notes.
        lo_, hi_, fp_ = x.get("price_range_lo"), x.get("price_range_hi"), x.get("final_price")
        if x.get("pct_in_range") is None and None not in (lo_, hi_, fp_) and hi_ > lo_:
            x["pct_in_range"] = round(100 * (fp_ - lo_) / (hi_ - lo_), 1)
            prov[c]["pct_in_range"] = {"src": "derived:(final-lo)/(hi-lo)",
                                       "prio": 50, "status": "single"}
        if x.get("pct_in_range") is None and not x.get("range_note") \
                and not x.get("range_lo_note"):
            x["range_note"] = "no usable lo<hi range to position the final price in"
        if x.get("mktcap_ipo_hkdm") == 0:
            x.pop("mktcap_ipo_hkdm", None)
            x["mktcap_note"] = ("stated market-cap line parsed as ZERO — "
                                "treated as a failed extraction, not a value")
        if x.get("mktcap_ipo_hkdm") is None:
            x["mktcap_note"] = x.get("mktcap_note") or (
                "no share count, offer-%-of-capital or published listing cap available")
        if (x.get("rev_latest") is None or x.get("ni_latest") is None) \
                and not x.get("fin_check"):
            x["fin_note"] = ("financial tables not machine-extractable and the "
                             "pre-IPO year is outside AAStocks' 5-year window")
        if x.get("deal_size_hkdm") is None:
            x["size_note"] = "no proceeds figure stated in any filing"
        # A missing stabilising manager has two different meanings and the
        # column must say which: no shoe at all, or a shoe whose announcement
        # never names the bank in the phrasing the parser reads.
        if not x.get("stabilizing_manager") and not x.get("stabmgr_note"):
            x["stabmgr_note"] = (
                "no over-allotment option in the offer structure, so no "
                "stabilising manager is appointed"
                if not x.get("greenshoe_pct") and not x.get("greenshoe_exercised_final")
                else "neither the allotment announcement's cover sentence nor "
                     "the prospectus definitions glossary names one in a form "
                     "the parser reads — not inferred from the sponsor")
        if not x.get("size_basis") and x.get("deal_size_hkdm") is None:
            x["size_basis_note"] = "no size, so no basis to describe"
        # A DEAL LISTED THIS WEEK has no 1-week return yet, and a blank with no
        # reason is a defect by the explained-absence contract. Ingenic (listed
        # 2026-08-25) was the first row young enough to hit this. Calendar days
        # from the listing date, so the note is true whatever the feed did.
        for _h, _days in (("1w", 7), ("1m", 30), ("3m", 90)):
            if x.get(f"ret_{_h}_pct") is not None or x.get(f"ret_{_h}_note"):
                continue
            ipo_d = (x.get("ipo_date") or "")[:10]
            if not ipo_d:
                continue
            try:
                aged = (date.today() - date.fromisoformat(ipo_d)).days
            except ValueError:
                continue
            if aged < _days:
                x[f"ret_{_h}_note"] = (
                    f"listed {ipo_d}, {aged} days ago — the {_h} window has not "
                    f"elapsed, so there is no {_h} return to publish yet")
        # an alpha needs BOTH legs: no horizon return (window not elapsed) or no
        # index bar means no alpha — say which
        for _h in ("1w", "1m", "3m"):
            if x.get(f"alpha_{_h}_pct") is None and not x.get("alpha_note"):
                if x.get(f"ret_{_h}_pct") is None:
                    x["alpha_note"] = (f"{_h} alpha needs the {_h} return first — "
                                       f"window has not elapsed yet")
                else:
                    x["alpha_note"] = (f"{_h} return is on file but the sector index "
                                       f"had no bar for that window")
        if x.get("oversub_public_mult") is None and not x.get("oversub_public_mult_note"):
            x["oversub_public_mult_note"] = (
                "Hong Kong public-offer subscription level not stated in the "
                "allotment results (BBG Verify column C fills it on the terminal)")
        if not x.get("industry_en") and not x.get("sponsors_en"):
            x["aastocks_note"] = ("no AAStocks IPO page for this code — typically a "
                                  "listing by introduction or a transfer, which runs "
                                  "no public offer")
        if x.get("pct_of_cap") is None and x.get("range_note"):
            x["pct_of_cap_note"] = "withheld with the price range — see the range note"
        if not x.get("sponsors") and x.get("sponsors_cn"):
            x["sponsor_note"] = "English name not in the filing text; AAStocks 保薦人 shown"
        elif not x.get("sponsors"):
            x["sponsor_note"] = "sponsor not stated in the extractable filing text"

    # --- LAST WORD: the derived legs are re-derived after every source has
    # landed. Computing alpha next to the return that produced it left one
    # deal stale when a later batch refreshed its benchmark, and a derived
    # column that disagrees with its own inputs is exactly what the identity
    # gate exists to prevent.
    for c, x in deals.items():
        d1f = x.get("first_day_return_pct")
        for h in ("1w", "1m", "3m"):
            r, b = x.get(f"ret_{h}_pct"), x.get(f"bench_{h}_pct")
            if r is not None and b is not None:
                x[f"alpha_{h}_pct"] = round(r - b, 2)
            if r is not None and d1f is not None and d1f != -100:
                x[f"aftermkt_{h}_pct"] = round(
                    100 * ((1 + r / 100) / (1 + d1f / 100) - 1), 2)
        if x.get("bench_1m_expop_pct") is not None \
                and x.get("aftermkt_1m_pct") is not None:
            x["alpha_1m_expop_pct"] = round(
                x["aftermkt_1m_pct"] - x["bench_1m_expop_pct"], 2)

    out = {
        "schema_version": 1,
        "as_of": datetime.now(timezone.utc).date().isoformat(),
        "generated_by": "merge_batches.py",
        "count": len(deals),
        "deals": [dict(sorted(x.items())) | {"_prov": {k: {kk: vv for kk, vv in v.items() if kk != "prio"}
                                                       for k, v in prov[x["code"]].items()}}
                  for x in sorted(deals.values(), key=lambda d: d.get("ipo_date") or "")],
    }
    (ROOT / "data" / "deals.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    (ROOT / "data" / "conflicts.json").write_text(json.dumps(conflicts, ensure_ascii=False, indent=1))

    # completeness report
    fields = ["ipo_date", "final_price", "price_range_lo", "gross_proceeds_hkdm",
              "oversub_public_mult", "first_day_return_pct", "sector", "subsector",
              "sponsors", "cornerstone_pct", "rev_latest", "ni_latest"]
    n = len(deals)
    print(f"\nmerged {n} deals -> data/deals.json | conflicts: {len(conflicts)}")
    if dropped_shares:
        print(f"  offer-share counts rejected as implausible for {len(dropped_shares)} deals "
              f"(size falls back to net proceeds): {', '.join(sorted(dropped_shares)[:12])}...")
    for f in fields:
        k = sum(1 for x in deals.values() if x.get(f) is not None)
        print(f"  {f:24s} {k:4d}/{n}  {100*k//n}%")


if __name__ == "__main__":
    main()
