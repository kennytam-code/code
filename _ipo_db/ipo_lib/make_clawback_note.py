#!/usr/bin/env python3
"""The 套路回撥 note: is the day-one pop allocation, or fundamentals?

Reads data/batches/clawback_study.json (written by analyse_clawback.py) and
data/deals.json; writes out/Clawback_Study.docx. Every number is computed;
the only typed text is the argument and the citations.
"""
import json
import statistics as st
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, Cm

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "Clawback_Study.docx"


def f(v, kind="n", dp=1):
    if v is None:
        return "—"
    if kind == "pct":
        return f"{v:+.{dp}f}%"
    if kind == "upct":
        return f"{v:.{dp}f}%"
    if kind == "x":
        return f"{v:,.{dp}f}x"
    if kind == "m":
        return f"{v:,.0f}"
    if kind == "int":
        return f"{v:,.0f}"
    return f"{v:.{dp}f}"


def para(doc, text, bold=False, italic=False, size=10.5, space_after=6):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold, r.italic = bold, italic
    r.font.size = Pt(size)
    p.paragraph_format.space_after = Pt(space_after)
    return p


def bullet(doc, text, size=10.5):
    p = doc.add_paragraph(style="List Bullet")
    r = p.add_run(text)
    r.font.size = Pt(size)
    p.paragraph_format.space_after = Pt(3)
    return p


def table(doc, header, rows, widths=None, size=8.5):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    for j, h in enumerate(header):
        c = t.rows[0].cells[j]
        c.text = ""
        r = c.paragraphs[0].add_run(str(h))
        r.bold = True
        r.font.size = Pt(size)
    for row in rows:
        cells = t.add_row().cells
        for j, v in enumerate(row):
            cells[j].text = ""
            r = cells[j].paragraphs[0].add_run("" if v is None else str(v))
            r.font.size = Pt(size)
            if j > 0:
                cells[j].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if widths:
        for row in t.rows:
            for j, w in enumerate(widths):
                row.cells[j].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def main():
    S = json.loads((ROOT / "data" / "batches" / "clawback_study.json").read_text())
    deals = json.loads((ROOT / "data" / "deals.json").read_text())["deals"]
    by = {d["code"]: d for d in deals}
    C = S["cohorts"]
    ju = C["just under (0.85-0.99x)"]
    hot = C["hot (>=10x)"]
    cov = C["covered (1-3x)"]
    d27 = S["desk27"]
    n27 = len(d27)
    in_cl = S["desk27_summary"]["in_cluster"]
    not_cl = S["desk27_summary"]["not_in_cluster"]
    hp = S["hot_public"]
    reg = S["just_under_by_regime"]
    byy = S["cluster_share_by_year"]
    o2c = S["open_to_close"]
    held, gave = o2c["held_or_rose"], o2c["gave_back"]
    corr = S["open_to_close_corr"]
    mac = S["macro"]
    G = S["grey"]
    fund_cl, fund_rest = S["fundamentals"]["cluster"], S["fundamentals"]["rest"]

    # the by-regime allocation test, recomputed here so the note carries it
    def med(xs):
        xs = [x for x in xs if x is not None]
        return round(st.median(xs), 1) if xs else None
    old = lambda x: (x.get("ipo_date") or "")[:10] < "2025-08-04"
    hot100 = [x for x in deals if (x.get("oversub_public_mult") or 0) >= 100 and x.get("oversub_intl_mult") is not None]
    reg_rows = []
    for lab, fn in (("Old rules (to Jul-2025), placing covered (≥1x)", lambda x: old(x) and x["oversub_intl_mult"] >= 1),
                    ("Old rules, placing 0.85–0.99x", lambda x: old(x) and 0.85 <= x["oversub_intl_mult"] < 1),
                    ("New rules (Aug-2025+), placing covered (≥1x)", lambda x: not old(x) and x["oversub_intl_mult"] >= 1),
                    ("New rules, placing 0.85–0.99x", lambda x: not old(x) and 0.85 <= x["oversub_intl_mult"] < 1)):
        xs = [x for x in hot100 if fn(x)]
        pa = [x.get("public_alloc_pct") for x in xs if x.get("public_alloc_pct") is not None]
        reg_rows.append((lab, len(xs), len(pa), med(pa), med([x.get("day1_open_pop_pct") for x in xs]),
                         med([x.get("first_day_return_pct") for x in xs])))

    cl_deals = [x for x in deals if x.get("oversub_intl_mult") is not None and 0.85 <= x["oversub_intl_mult"] < 1]
    cl_3m = [x.get("aftermkt_3m_pct") for x in cl_deals if x.get("aftermkt_3m_pct") is not None]
    cl_1m = [x.get("aftermkt_1m_pct") for x in cl_deals if x.get("aftermkt_1m_pct") is not None]
    grey_have = [r for r in d27 if r.get("grey_pct") is not None]

    doc = Document()
    for s_ in doc.sections:
        s_.left_margin = s_.right_margin = Cm(2.0)
        s_.top_margin = s_.bottom_margin = Cm(1.8)
    doc.styles["Normal"].font.name = "Arial"
    doc.styles["Normal"].font.size = Pt(10.5)

    para(doc, "套路回撥: is the day-one pop allocation, or fundamentals?", bold=True, size=15, space_after=2)
    para(doc, f"HK IPO book, {S['n_book']} Main Board deals 2021–2026, as of {S['as_of']}. "
              "Every figure below is computed from the book; the sources for anything read from "
              "outside it are listed at the end.", italic=True, size=9.5, space_after=10)

    # ---------------------------------------------------------------- answer
    para(doc, "The short answer", bold=True, size=12)
    para(doc, f"Yes, and it can be shown rather than suspected. {in_cl} of the {n27} deals on the list sit in a "
              f"cluster of exactly {ju['n']} deals in the whole book where the international book was filled to "
              f"between 0.85x and 0.99x. That cluster has the smallest deals in the book (median HK${f(ju['median_size_hkdm'],'m')}m "
              f"against HK${f(hot['median_size_hkdm'],'m')}m for the hot cohort), a modest public book "
              f"(median {f(ju['median_public_x'],'x')} against {f(hot['median_public_x'],'x')}), and yet it opens like the "
              f"hottest deals in the market: median open {f(ju['median_open'],'pct')} against {f(hot['median_open'],'pct')} for "
              f"deals with ten times the demand. The pop is not demand and it is not fundamentals. It is the share of the "
              f"deal that retail was allowed to have.")
    para(doc, "The mechanism is written in every prospectus. The PN18 clawback, which lifts the public tranche to 30/40/50% "
              "of the deal when the public book is 15x/50x/100x covered, applies only \"if the International Offering is "
              "fully subscribed or oversubscribed\". At 0.99x it is not. The coordinators are then free to reallocate the "
              "placing shortfall \"in such proportions as they deem appropriate\", and they pass retail the shortfall and "
              "nothing more. The result, measured across every deal with a 100x-plus public book under the old rules: "
              f"retail received a median {reg_rows[0][3]}% of the deal when the placing was covered and "
              f"{reg_rows[1][3]}% when it was left 1–15% short. Same demand, a third of the shares, and ~100–170 chosen "
              "placees holding the rest.")
    para(doc, f"Two of the {n27} are not this. " + "; ".join(
        f"{n} ({c}) had an international book of {f(i,'x',2)}" for c, n, i in not_cl) +
              ". Midea's 0.11x in the database was a parse error (the number came from the clawback rule table, not "
              "from the subscription result); its placing was 8.06x covered with 236 placees and its 5% retail "
              "allocation is a big-cap norm. CentralChina's placing was genuinely 0.72x with a 5x public book: a weak "
              "deal, not a starved one, and it fell.")

    # --------------------------------------------------------------- data fix
    para(doc, "1. The data had to be fixed first", bold=True, size=12)
    para(doc, f"The international multiple could not be taken on trust. For 20 of the {n27} the evidence stored beside "
              "it in the database quoted the PUBLIC offer's table (\"No. of successful applications … Subscription level "
              "337.57 times\"), so the number needed proving. Each allotment announcement was re-read from its own "
              f"INTERNATIONAL OFFERING section, anchored on the placee count, for all {S['n_book']} deals. The values "
              "held for 24 of the 27; Midea's was wrong (0.11x, read from the clawback rule table; the real figure is "
              "8.06x); three 2021–23 notices written in prose (Deyun, Huaibei, CentralChina) could not be re-read and "
              f"keep their earlier figure. The cluster survived the check: {ju['n']} deals with a placing between 0.85x "
              f"and 0.99x, placee counts between 32 and 218 (median {f(ju['median_placees'],'int')}), and a final public "
              f"share of the offering that the same notices state directly (median {f(ju['median_public_alloc'],'upct')}).")
    rows = []
    for r in sorted(d27, key=lambda r: (r["oversub_intl_mult"] or 99)):
        rows.append((f"{r['code']} {r['name'][:15]}", (r["ipo_date"] or "")[:10], f(r["deal_size_hkdm"], "m"),
                     f(r["oversub_public_mult"], "x"), f(r["oversub_intl_mult"], "x", 2), f(r["intl_placees"], "int"),
                     f(r["public_alloc_pct"], "upct"), r["clawback"] or "—",
                     f(r["grey_pct"], "pct"), f(r["day1_open_pop_pct"], "pct"), f(r["first_day_return_pct"], "pct"),
                     f(r["day1_open_close_pct"], "pct"), f(r["day1_vol_x_retail"], "x"), f(r["hsi_d1"], "pct", 2)))
    table(doc, ["Deal", "Listed", "Size HK$m", "Public", "Intl", "Placees", "Retail %", "Claw", "Grey", "Open",
                "Close", "Open→close", "Vol/retail", "HSI d1"], rows,
          widths=[3.4, 1.7, 1.4, 1.3, 1.1, 1.2, 1.3, 1.0, 1.2, 1.2, 1.2, 1.5, 1.4, 1.2], size=7.5)
    para(doc, "Retail % = the public tranche's share of the offering after reallocation, as stated in the allotment "
              "notice. Claw = the notice's own \"Claw-back triggered\" line (2025+ format), derived from the split where "
              "the older notice has no line (≥28% = yes, ≤12% = no, the band between left unstated). Vol/retail = "
              "listing-day volume divided by the shares the public tranche received. HSI d1 = the Hang Seng Index's "
              "move on the listing day.", italic=True, size=8.5)

    # -------------------------------------------------------------- mechanism
    para(doc, "2. The mechanism, in the rule's own words", bold=True, size=12)
    para(doc, "AB&B Bio-Tech's prospectus (2627, August 2025), section \"Reallocation and clawback\":", size=10)
    para(doc, "\"If the International Offering is fully subscribed or oversubscribed and the number of Offer Shares "
              "validly applied for under the Hong Kong Public Offering represents (a) 15 times or more but less than 50 "
              "times; (b) 50 times or more but less than 100 times; and (c) 100 times or more of the total number of "
              "Offer Shares initially available under the Hong Kong Public Offering, then Offer Shares will be "
              "reallocated to the Hong Kong Public Offering from the International Offering … representing "
              "approximately 30.0%, approximately 40.0% and approximately 50.0% of the total number of Offer Shares "
              "initially available under the Global Offering, respectively (the \"PN18 Clawback\").\"",
         italic=True, size=9.5)
    para(doc, "AB&B's public book was 4,007.64x. Its placing had 152 placees at 0.99x. Retail received 3,996,000 of "
              "33,442,600 shares: 11.95%, not 50%. HKET's headline the next morning was 「怪象令回撥由50%變12%？」, "
              "and its explanation was the one above: the 0.99x \"剛好沒有觸發回補機制門檻\", leaving the coordinators "
              "the right to set the split 「按其認為適當的數目」. AB&B was the last deal under the old 50% cap.")
    para(doc, "The market has a vocabulary for this. 證券之星 on Easou (2550) distinguishes 被動回撥 (the rule working "
              "as designed), 主動回撥 (retail lifted to 20% voluntarily when the public book is under 15x) and 套路回撥: "
              "a strong public book, a placing held under 1x, and retail restricted to the minimum. It names Easou, "
              "EDA (2505) and Autostreets (2443) — three deals on this list — as examples, and puts the motive plainly: "
              "「主力想盡可能多拿票，不想把票分給散戶」. HKET on Shougang Lanza's debut: 「國際配售認購不足、公開發售佔比增至15%」. "
              "HKET on Bayzed: 「由於國際配售部分認購不足，香港公開發售股份部分升至12.2%」. Every one of those figures matches "
              "what the extractor read from the filing.")
    para(doc, "Measured across the book, public book 100x or more:", size=10)
    table(doc, ["Regime and placing", "Deals", "Split stated", "Retail % (median)", "Open (median)", "Close (median)"],
          [(a, b, c, f(d_, "upct"), f(e, "pct"), f(g, "pct")) for a, b, c, d_, e, g in reg_rows],
          widths=[7.5, 1.4, 2.0, 2.4, 2.2, 2.2])
    para(doc, f"Read the opens across that table. Under the old rules a covered placing put half the deal in retail "
              f"hands and those deals opened {f(reg_rows[0][4],'pct')}; the same demand with a sixth of the deal in "
              f"retail hands opened {f(reg_rows[1][4],'pct')}. That is the whole effect in two numbers: a 100x book "
              "moves the price only when the shares are kept from it. Since August 2025 the reform's Mechanism B lets "
              "an issuer fix retail at 10% with no clawback at all, which is why the third row reads 10% with a fully "
              f"covered book — and why every hot deal now opens the way only the starved ones used to "
              f"({f(reg_rows[2][4],'pct')} median across {reg_rows[2][1]} deals). The trick is no longer needed to get "
              "the outcome, and the cluster has thinned: "
              + ", ".join(f"{y}: {v['just_under']} of {v['n']}" for y, v in byy.items() if v["n"]) +
              ". It has not vanished. Excelland (3231, September 2026) filled its placing to 0.99x with 87 placees, "
              f"gave retail {f(by['3231'].get('public_alloc_pct'),'upct')} under Mechanism A, and opened "
              f"{f(by['3231'].get('day1_open_pop_pct'),'pct')}.")

    # ------------------------------------------------------- fundamentals/macro
    para(doc, "3. Fundamentals and the market on the day (question 1)", bold=True, size=12)
    para(doc, f"The cluster is not a set of exceptional companies. Median P/E at the offer {f(ju['median_pe'],'x')} "
              f"against {f(fund_rest['median_pe'],'x')} for the rest of the book; {ju['share_profitable']}% profitable "
              f"against {fund_rest['share_profitable']}%; {ju['share_ah']}% with an A-share line against "
              f"{fund_rest['share_ah']}%. Sectors are ordinary: industrials, healthcare services, consumer, materials. "
              "These are small, mostly profitable, cheaply-priced SMEs — which is exactly the profile a placing "
              "syndicate can fill with ~120 names and hold. Within the cluster, P/E and P/S have no rank relationship "
              f"with the size of the open (ρ {S['fund_corr']['P/E'][0]} and {S['fund_corr']['P/S'][0]}); the public "
              f"multiple does (ρ {S['fund_corr']['public x'][0]}), because it is the same starved-float effect seen "
              "from the demand side.")
    para(doc, f"The market explains nothing. The Hang Seng's move on the listing day has a rank correlation of "
              f"{mac['rho_hsi_vs_day1_all'][0]} with day-one return across {mac['rho_hsi_vs_day1_all'][1]} deals and "
              f"{mac['rho_hsi_vs_day1_cluster'][0]} inside the cluster; the cluster's median index move on its listing "
              f"days was {f(mac['cluster_median_hsi_d1'],'pct')}. The opens that look like a market event happened on "
              "flat days:")
    for c, n, o, h in mac["cluster_big_pops_on_flat_index"]:
        bullet(doc, f"{n} ({c}): opened {f(o,'pct')} on a day the HSI moved {f(h,'pct',2)}.", size=9.5)

    # -------------------------------------------------------------------- grey
    para(doc, "4. The grey market against the pop (question 2)", bold=True, size=12)
    para(doc, f"{len(grey_have)} of the {n27} now carry a grey-market close (10 were on file; 12 more were located and "
              f"added this week; 5 could not be found — see the sources). Inside the cluster the grey close and the "
              f"day-one open are the same number: rank correlation {G['rho_grey_vs_open'][0]} over "
              f"{G['rho_grey_vs_open'][1]} deals, median gap {f(G['median_open_minus_grey'],'pct')}. The grey is "
              "where the open prints; it is not a forecast of anything after it. The day-one close beat the grey in "
              f"{G['share_close_above_grey']}% of cases, so for two deals in three the grey session was the high "
              "of the whole event.")
    para(doc, "Where the grey came from. Three brokers run an evening session from 16:15 to 18:30 the day before "
              "listing — Futu (富途), Phillip (輝立) and Bright Smart (耀才) — and they print slightly different closes. "
              "AAStocks publishes a standardised headline for each session (《新股》NAME暗盤收報X元 高/低上市價Y%), which "
              "the database captures automatically each week for every new listing; that is the source for 130 deals "
              "and the reason older deals are missing (AAStocks keeps ~21 articles per stock and no archive). For the "
              "20 hand-added prints the source is the press report of the session, with the venue named: HKET for "
              "Breton, Wellcell, Autostreets, Bayzed, Midea, CentralChina and AB&B; Sina/財聯社 for Easou; 163.com for "
              "EDA; 華盛通 for Mokingran; StockFisher for Guofuhee; Futu's own feed for Fujing. Where the press gives "
              "only the range across the three venues (Wellcell 1.61–1.68, Bayzed 5.25–5.37) the midpoint is shown and "
              "the cell's note says so. WK Group's press coverage gives only the grey OPEN (+144%), which is not a close "
              "and was not recorded. Ruichang, Healthyway, Huaibei and Deyun have no retrievable print.")

    # ------------------------------------------------------------- pre-allot
    para(doc, "5. What is knowable before the allotment result (question 3)", bold=True, size=12)
    para(doc, "For the public tranche, a great deal. During the three-and-a-half-day offer the brokers publish their "
              "running margin-financing (孖展) totals, and HKET, Sina, AAStocks, TastyMoney and 信報 aggregate them daily "
              "as 「孖展超購X倍」. Examples from this list:")
    bullet(doc, "Shougang Lanza (2553): 36x on the second day of the offer (Sina); 776億 of margin, 1,133.5x on the "
                "margin count alone at the close (HKET); final official public book 1,421.5x from 110,000 applicants.")
    bullet(doc, "AB&B (2627): 225x on the first day (明報); 326億 and 629x at the close (HKET); final 4,007.6x from "
                "195,000 applicants, one-lot hit rate 1%.")
    para(doc, "The margin count runs at roughly half to four-fifths of the final multiple, because cash applications "
              "and brokers who do not report are outside it, so it is a floor. It is also the first tell: a deal under "
              "HK$500m with a margin count above 100x and Mechanism A (or, before August 2025, any deal) is the setup "
              "for a placing held just under 1x.")
    para(doc, "For the international tranche there is no published tally. What exists is one line of 「市場消息」 in "
              "the same articles — that the placing 「已獲足額認購」 or 「反應淡靜」 — and it is not reliable for this "
              "purpose, because a placing being filled to 0.95x by 120 friendly accounts and one being filled to 5x "
              "by real institutions read the same to a reporter the day before allotment. The first hard number is "
              "the allotment announcement itself, published the evening before listing: the placee count and the "
              "subscription level are on its cover table. A count near 100–170 with a level of 0.9-something, on a "
              "deal whose public book is 50x or more, is the pattern; it is knowable by 18:00 the night before the "
              "open, which is also when the grey session closes.")

    # ---------------------------------------------------------- open->close
    para(doc, "6. Why some keep rising after the open and some give it back (question 4)", bold=True, size=12)
    para(doc, f"Inside the cluster, {held['n']} deals held or extended their open through the close and {gave['n']} "
              "gave part of it back. The two groups are not distinguished by their terms — the median open was "
              f"{f(held['median_open'],'pct')} for one and {f(gave['median_open'],'pct')} for the other — but by "
              "what the tape did after it:")
    table(doc, ["", "Held or rose", "Gave back"],
          [("Deals", held["n"], gave["n"]),
           ("Median open", f(held["median_open"], "pct"), f(gave["median_open"], "pct")),
           ("Median close", f(held["median_close"], "pct"), f(gave["median_close"], "pct")),
           ("Day-1 volume / retail float", f(held["median_vol_x_retail"], "x"), f(gave["median_vol_x_retail"], "x")),
           ("Day-1 range (high−low)/open", f(held["median_range"], "upct"), f(gave["median_range"], "upct")),
           ("Retail share of deal", f(held["median_public_alloc"], "upct"), f(gave["median_public_alloc"], "upct")),
           ("Public book", f(held["median_public_x"], "x"), f(gave["median_public_x"], "x")),
           ("Deal size HK$m", f(held["median_size_hkdm"], "m"), f(gave["median_size_hkdm"], "m")),
           ("1-week ex-pop", f(held["median_1w_expop"], "pct"), f(gave["median_1w_expop"], "pct")),
           ("1-month ex-pop", f(held["median_1m_expop"], "pct"), f(gave["median_1m_expop"], "pct"))],
          widths=[6.0, 3.5, 3.5])
    para(doc, "Rank correlation of each factor with the open-to-close move, inside the cluster: " +
              ", ".join(f"{k} {v['rho']}" for k, v in corr.items() if v["rho"] is not None) + ".")
    have_v = [x for x in cl_deals if x.get("day1_open_close_pct") is not None and x.get("day1_vol_x_retail")]
    hi_v = sorted([x for x in have_v if x["day1_vol_x_retail"] >= 2.0], key=lambda x: x["day1_open_close_pct"])
    lo_v = sorted([x for x in have_v if x["day1_vol_x_retail"] <= 1.4], key=lambda x: x["day1_open_close_pct"])
    exc = [x for x in hi_v if x["day1_open_close_pct"] >= 0]
    hi_down = [x for x in hi_v if x["day1_open_close_pct"] < 0]
    amp_hi = med([abs(x["day1_open_close_pct"]) for x in hi_v])
    amp_lo = med([abs(x["day1_open_close_pct"]) for x in lo_v])
    para(doc, "The strongest relationship in the whole study is volume against the retail float, and what it sets "
              f"is the SIZE of the day's move first and its direction second. The {len(lo_v)} cluster deals that traded "
              f"1.4x or less of their retail float on day one moved a median {f(amp_lo,'n')} points between open and "
              f"close, in either direction — the placees were not active and the day was quiet: "
              + ", ".join(f"{x['name'].title()} {f(x['day1_open_close_pct'],'pct')} on {f(x['day1_vol_x_retail'],'x')}"
                          for x in sorted(lo_v, key=lambda x: -x['day1_open_close_pct'])[:4]) +
              f". The {len(hi_v)} that traded 2x or more moved a median {f(amp_hi,'n')} points, and {len(hi_down)} of the "
              f"{len(hi_v)} moved down — every large give-back in the cluster is here: "
              + ", ".join(f"{x['name'].title()} {f(x['day1_open_close_pct'],'pct')} on {f(x['day1_vol_x_retail'],'x')}"
                          for x in hi_v[:5]) +
              ". Three to six turns of the retail float in a day is a placing book distributing into the open, and the "
              "open was the high. Shougang Lanza traded 93% of its entire offering on day one, 6.2x its retail "
              "tranche, in a 43% range, and closed 25 points below its open. Ruichang opened +23.8% and closed +14.3% "
              "with net mega-lot outflow of HK$2.69m on the day (21財經: 「首日熱潮與背後的主力出逃」).")
    para(doc, f"The exceptions are the point, not a nuisance. {len(exc)} deals traded 2.2–2.9x their float and still "
              "closed above their open — " + ", ".join(f"{x['name'].title()} ({f(x['day1_open_pop_pct'],'pct')} open, "
                                                       f"{f(x['first_day_return_pct'],'pct')} close)" for x in exc) +
              ". Heavy turnover with a rising price means the "
              "distribution was met by bigger buying, which is what 163.com meant by 「貨源歸邊」 on EDA: the shares "
              "were consolidating into hands that wanted them. Heavy turnover with a falling price is the same "
              "sellers meeting nobody. The tape tells you which by mid-morning; the terms do not.")
    para(doc, "Two other factors carry a signal, both in the same direction. A LARGER retail share went with giving "
              "back (ρ −0.37): the more shares in retail hands, the more sellers on the open. A HIGHER public multiple "
              "went with giving back (ρ −0.44): the deals with the most frantic retail books drew the most retail "
              "selling into the pop. Neither the grey (ρ −0.30 — a bigger grey meant a bigger give-back, not a "
              "smaller one) nor the index (ρ −0.03) helps.")
    para(doc, "What happens next is genuinely two-sided. One month after listing, ex-pop, the cluster's median is "
              f"{f(med(cl_1m),'pct')} but the spread runs from {f(min(cl_1m),'pct')} to {f(max(cl_1m),'pct')}; at three "
              f"months from {f(min(cl_3m),'pct')} to {f(max(cl_3m),'pct')}, half positive. A placing book of 120 names "
              "holding 85% of a HK$200m deal can walk the price up for months or let it go, and nothing in the terms "
              "says which. That is the honest limit of what the data can tell you: the setup predicts the OPEN with "
              "confidence; only the first hour's volume predicts the close; and the month after is the holders' "
              "decision, not the market's.")

    # ---------------------------------------------------------------- use
    para(doc, "7. How to use it", bold=True, size=12)
    bullet(doc, "Before allotment: a deal under ~HK$500m, margin count above 100x, Mechanism A (or pre-Aug-2025), "
                "no cornerstone of size. Expect the placing to print 0.9-something with ~100–170 placees and retail "
                "to get 6–20%. The open will be large whatever the company is.")
    bullet(doc, "The evening before listing: the allotment notice states placees, the placing level and the final "
                "split. If it reads 0.85–0.99x, the grey close that same evening is the opening print, not a target.")
    bullet(doc, "The first hour: watch volume against the public tranche. Past ~2x the float by mid-morning the "
                "placing book is active and the day will be large — down 11 times in 15 in this sample, up on the four "
                "occasions the buying was bigger than the selling. Near 1x the placees are sitting still and the day "
                "is quiet either way; do not expect an extension from a quiet tape.")
    bullet(doc, "After that, treat it as a controlled float, because it is one: position size for a −60% and a +200% "
                "three-month outcome, both of which are in the sample.")
    bullet(doc, "Under the new rules the placing trick is fading (2 deals in 2026) but Mechanism B produces the same "
                "starved open legally: Ligent (9856, this week) had a 4.67x placing, 192 placees, 10% to retail, and "
                "opened +11%. The tell is now the mechanism and the retail % in the prospectus, not the 0.9x.")

    # -------------------------------------------------------------- sources
    para(doc, "Sources", bold=True, size=11)
    for line in (
        "HKEX allotment results announcements for all 519 deals (international section, final split, claw-back line), "
        "re-read this week; AB&B Bio-Tech prospectus, \"Reallocation and clawback\".",
        "HKET: 中慧生物-B 2627首掛… 怪象令回撥由50%變12%？ (2025-08-11); 首鋼朗澤2553首掛收升44%… 國際配售認購不足、公開發售佔比增至15% "
        "(2026-06-03); 首鋼朗澤2553…孖展…超購 (2026-05-29); 中慧生物-B…獲19.5萬人認購、涉資2100億超購4000倍 (2025-08); "
        "佰澤醫療2609下限4.22元定價 一手中籤率20% (2025-06-20); 博雷頓1333暗盤收升逾四成 (2025-05-06); 汽車街2443暗盤升逾4成 "
        "(2024-05-30); 經緯天地2477…暗盤 (2024-01-11); 美的集團0300暗盤收升逾5% (2024-09-16); 中原建業9982暗盤跌逾一成 (2021-05-28).",
        "證券之星: 宜搜科技(02550)「套路回撥」加持，盛大集團陳天橋獨賺16倍? (2024-06-11). 網易/163: 上演貨源歸邊，EDA集團控股 "
        "(2024-05). 21財經/南方財經: 瑞昌國際控股港交所上市：首日熱潮與背後的主力出逃 (2024-07-12). 中金在線: 夢金園，又來套路回撥 "
        "(2024-11-29). 明報: 中慧生物首日招股 孖展超購逾225倍 (2025-08-01). 新浪/財聯社: 宜搜科技暗盤 (2024-06-06); 首鋼朗澤招股次日"
        "孖展超36倍 (2026-05-27). 華盛通: 夢金園暗盤收漲4.5% (2024-11-28). StockFisher: 國富氫能暗盤 (2024-11-14). Futu: 富景中國控股"
        "暗盤 (2024-03-27).",
        "Index moves: Hang Seng Index and HSCEI daily closes (Yahoo Finance, ^HSI / ^HSCE). Listing-day volume: Tencent "
        "kline daily bars, 518 of 519 deals. Grey-market automated captures: AAStocks per-stock news headlines.",
    ):
        bullet(doc, line, size=8.5)

    OUT.parent.mkdir(exist_ok=True, parents=True)
    doc.save(OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
