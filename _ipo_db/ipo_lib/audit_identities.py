#!/usr/bin/env python3
"""Data-level gate: the arithmetic relationships that must hold BY CONSTRUCTION.

Every violation here is a data error by definition — no judgment involved:
  day-1        (1+d1)      == (1+open_pop) x (1+open_close)
  ex-pop       (1+ret_h)   == (1+d1) x (1+aftermkt_h)
  alpha        ret_h       == bench_h + alpha_h
  A-premium    a_close_hkd == final_price x (1+a_prem_ipo/100)
  P/E          pe_ipo      == mktcap / NI     (non-Bloomberg rows)

Plus: no NaN text anywhere in deals.json, no numeric zero market caps, no
day-1 beyond +/-400% (raw-print sanity), and EVERY blank cell must carry a
stated reason (the explained-absence contract).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_xlsx as B

ROOT = Path(__file__).resolve().parent.parent

AH = {"a_premium_ipo_pct", "a_close_hkd", "is_h_share", "a_share_code",
      "a_premium_now", "a_mktcap_now_hkdm"}
NOTEMAP = {
    "pe_ipo": "pe_note", "ps_ipo": "ps_note", "oversub_intl_mult": "intl_note",
    "greenshoe_exercised_final": "shoe_note", "greenshoe_pct": "greenshoe_note",
    "stabilizing_manager": "stabmgr_note",
    "stabilizing_manager_key": "stabmgr_note",
    "cornerstone_investors": "cornerstone_list_note",
    "cornerstone_keys": "cornerstone_list_note",
    "cornerstone_pct": "cornerstone_pct_note",
    "rev_latest": "fin_note", "ni_latest": "fin_note",
    "mktcap_ipo_hkdm": "mktcap_note", "mktcap_basis": "mktcap_note",
    "sponsors": "sponsor_note", "deal_size_hkdm": "size_note",
    "ret_3m_pct": "ret_3m_note", "ret_1m_pct": "ret_1m_note",
    "ret_1w_pct": "ret_1w_note",
    "aftermkt_3m_pct": "ret_3m_note", "aftermkt_1m_pct": "ret_1m_note",
    "aftermkt_1w_pct": "ret_1w_note",
    "price_range_lo": "range_lo_note", "day1_open_close_pct": "day1_oc_note",
    "day1_open_pop_pct": "day1_oc_note", "profitable_at_ipo": "fin_note",
    "size_basis": "size_basis_note",
    "oversub_public_mult": "oversub_public_mult_note",
    "industry_en": "aastocks_note", "sponsors_en": "aastocks_note",
    "underwriters_en": "aastocks_note", "bookrunners_display": "aastocks_note",
    "pct_of_cap": "pct_of_cap_note", "priced_at_cap": "range_note",
    "pct_in_range": "range_note",
    "eff_free_float_pct": "eff_ff_note",
    "eff_free_float_hkdm": "eff_ff_note",
    "eff_free_float_shares": "eff_ff_shares_note",
    # blank where the filing never states the expiry in a parsable form, or
    # the deal ran no shoe at all — shoe_note carries both reasons
    "stabilization_end_date": "shoe_note",
    "prospectus_link": "doc_note",
}
ALT = {
    "rev_latest": "fin_check", "ni_latest": "fin_check",
    "profitable_at_ipo": "fin_check",
    "a_premium_ipo_pct": "ah_note", "a_close_hkd": "ah_note",
    "a_premium_now": "ah_note",
    "alpha_1w_pct": "alpha_note", "alpha_1m_pct": "alpha_note",
    "alpha_3m_pct": "alpha_note", "alpha_1m_expop_pct": "alpha_note",
    "bench_1m_pct": "alpha_note", "bench_1m_expop_pct": "alpha_note",
    "pct_in_range": "range_lo_note",
    "eff_free_float_shares": "eff_ff_note",
}
# columns whose blank IS the design: they resolve live on the terminal (BBG
# Verify formulas) and never carry local data — ps_now joined in v26
SKIP_BLANK = {"pe_ipo_bbg", "pe_now", "a_pe_at_hipo", "valuation_notes",
              "ps_now"}


def main():
    raw = (ROOT / "data" / "deals.json").read_text()
    deals = json.loads(raw)["deals"]
    bad = []

    if "NaN" in raw:
        bad.append(f"deals.json contains {raw.count('NaN')} NaN literals")

    for x in deals:
        c, n = x["code"], x["name"][:14]
        d1 = x.get("first_day_return_pct")
        pop, oc = x.get("day1_open_pop_pct"), x.get("day1_open_close_pct")
        if None not in (d1, pop, oc) and \
                abs((1 + d1 / 100) - (1 + pop / 100) * (1 + oc / 100)) > 0.005:
            bad.append(f"{c} {n}: day-1 identity broken")
        if d1 is not None and abs(d1) > 400:
            bad.append(f"{c} {n}: day-1 {d1}% beyond the raw-print sanity band")
        for h in ("1w", "1m", "3m"):
            r, a = x.get(f"ret_{h}_pct"), x.get(f"aftermkt_{h}_pct")
            if None not in (r, a, d1) and d1 != -100 and \
                    abs((1 + r / 100) / (1 + d1 / 100) - (1 + a / 100)) > 0.005:
                bad.append(f"{c} {n}: {h} ex-pop identity broken")
            r2, al, bn = (x.get(f"ret_{h}_pct"), x.get(f"alpha_{h}_pct"),
                          x.get(f"bench_{h}_pct"))
            if None not in (r2, al, bn) and abs(r2 - bn - al) > 0.02:
                bad.append(f"{c} {n}: alpha {h} != ret - bench")
        ac, ap, fp = (x.get("a_close_hkd"), x.get("a_premium_ipo_pct"),
                      x.get("final_price"))
        if None not in (ac, ap, fp) and fp and abs((ac / fp - 1) * 100 - ap) > 0.1:
            bad.append(f"{c} {n}: A-premium-at-IPO identity broken")
        mc, ni, pe = (x.get("mktcap_ipo_hkdm"), x.get("ni_latest"),
                      x.get("pe_ipo"))
        if None not in (mc, ni, pe) and ni > 0:
            src = str((x.get("_prov") or {}).get("pe_ipo", {}).get("src", ""))
            if "bloomberg" not in src and abs(mc / ni - pe) > max(0.2, pe * 0.02):
                bad.append(f"{c} {n}: P/E != mktcap/NI")
        if x.get("mktcap_ipo_hkdm") == 0:
            bad.append(f"{c} {n}: market cap ZERO published as a value")
        # an offer price outside this band is a share count or a proceeds
        # figure read as a price (BAIGE shipped 54,382,183 once)
        if fp is not None and not (0.05 <= fp <= 3000):
            bad.append(f"{c} {n}: offer price {fp:,.2f} outside the plausible band")
        mc2 = x.get("mktcap_ipo_hkdm")
        if mc2 is not None and mc2 > 3_000_000:
            bad.append(f"{c} {n}: market cap {mc2:,.0f} HK$m implausible")
        eff, size2, mc2 = (x.get("eff_free_float_pct"), x.get("deal_size_hkdm"),
                           x.get("mktcap_ipo_hkdm"))
        if eff is not None:
            cs2 = x.get("cornerstone_pct") or 0.0
            if not (size2 and mc2):
                bad.append(f"{c} {n}: eff free float published without size+cap")
            elif abs(eff - 100 * size2 * (1 - cs2 / 100) / mc2) > 0.06:
                bad.append(f"{c} {n}: eff-free-float identity broken")
            elif not (0 <= eff <= 100):
                bad.append(f"{c} {n}: eff free float {eff}% outside [0,100]")

    # explained-absence contract: a blank with no reason is a defect
    unexplained = 0
    for _b, _h, f, _fmt, _w in B.DB_COLS:
        if f.startswith("_") or f in SKIP_BLANK:
            continue
        for x in deals:
            if x.get(f) not in (None, "", []):
                continue
            if f in AH and not x.get("a_share_code"):
                continue
            if x.get(NOTEMAP.get(f, "")) or x.get(ALT.get(f, "")):
                continue
            if f == "stabilization_link" and x.get("shoe_note"):
                continue
            unexplained += 1
    if unexplained:
        bad.append(f"{unexplained} blank cells carry NO stated reason")

    print(f"audit_identities: {len(deals)} deals, "
          f"{len(B.DB_COLS)} columns checked")
    for b in bad[:12]:
        print("  FAIL:", b)
    print("  RESULT:", "CLEAN" if not bad else f"{len(bad)} PROBLEMS")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
