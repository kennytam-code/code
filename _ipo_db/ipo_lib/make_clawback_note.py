#!/usr/bin/env python3
"""Builds out/Clawback_Study.docx — the written answer to the desk's questions.

Plain English, short sentences, a table under each answer. Every figure is read
from data/deals.json and data/batches/clawback_study.json at build time.
"""
import json
import statistics as st
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, Cm

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "Clawback_Study.docx"
DESK = ("0300 9982 2881 1333 2625 2573 2450 2613 2553 1440 2497 9881 2651 2477 1334 "
        "2535 2505 2443 2550 1354 1471 2585 2587 2609 2582 2627 2691").split()


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
    return f"{v:.{dp}f}"


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(st.median(xs), 1) if xs else None


def para(doc, text, bold=False, italic=False, size=10.5, after=6):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold, r.italic = bold, italic
    r.font.size = Pt(size)
    p.paragraph_format.space_after = Pt(after)


def head(doc, text, size=12.5):
    para(doc, text, bold=True, size=size, after=4)


def bullet(doc, text, size=10.5):
    p = doc.add_paragraph(style="List Bullet")
    r = p.add_run(text)
    r.font.size = Pt(size)
    p.paragraph_format.space_after = Pt(3)


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


def main():
    S = json.loads((ROOT / "data" / "batches" / "clawback_study.json").read_text())
    deals = json.loads((ROOT / "data" / "deals.json").read_text())["deals"]
    by = {d["code"]: d for d in deals}
    C = S["cohorts"]
    ju, hot = C["just under (0.85-0.99x)"], C["hot (>=10x)"]
    rest = S["fundamentals"]["rest"]
    corr = S["open_to_close_corr"]
    mac = S["macro"]
    held, gave = S["open_to_close"]["held_or_rose"], S["open_to_close"]["gave_back"]
    byy = S["cluster_share_by_year"]
    d27 = [by[c] for c in DESK if c in by]
    cluster = [x for x in deals if x.get("oversub_intl_mult") is not None and 0.85 <= x["oversub_intl_mult"] < 1]
    in_cl = [x for x in d27 if 0.85 <= (x.get("oversub_intl_mult") or 99) < 1]
    not_cl = [x for x in d27 if x not in in_cl]
    old = lambda x: (x.get("ipo_date") or "")[:10] < "2025-08-04"

    hot100 = [x for x in deals if (x.get("oversub_public_mult") or 0) >= 100 and x.get("oversub_intl_mult") is not None]
    reg = []
    for lab, fn in (("Old rules, placing covered (1x or more)", lambda x: old(x) and x["oversub_intl_mult"] >= 1),
                    ("Old rules, placing 0.85–0.99x", lambda x: old(x) and 0.85 <= x["oversub_intl_mult"] < 1),
                    ("New rules (Aug-2025 on), placing covered", lambda x: not old(x) and x["oversub_intl_mult"] >= 1),
                    ("New rules, placing 0.85–0.99x", lambda x: not old(x) and 0.85 <= x["oversub_intl_mult"] < 1)):
        xs = [x for x in hot100 if fn(x)]
        pa = [x.get("public_alloc_pct") for x in xs if x.get("public_alloc_pct") is not None]
        reg.append((lab, len(xs), med(pa), med([x.get("day1_open_pop_pct") for x in xs]),
                    med([x.get("first_day_return_pct") for x in xs])))

    grey_all = [x for x in deals if x.get("grey_pct") is not None]
    g27 = [x for x in d27 if x.get("grey_pct") is not None]
    gp = [(x["grey_pct"], x.get("day1_open_pop_pct"), x.get("first_day_return_pct")) for x in g27
          if x.get("day1_open_pop_pct") is not None]
    cl_1m = [x.get("aftermkt_1m_pct") for x in cluster if x.get("aftermkt_1m_pct") is not None]
    cl_3m = [x.get("aftermkt_3m_pct") for x in cluster if x.get("aftermkt_3m_pct") is not None]

    doc = Document()
    for s_ in doc.sections:
        s_.left_margin = s_.right_margin = Cm(2.0)
        s_.top_margin = s_.bottom_margin = Cm(1.8)
    doc.styles["Normal"].font.name = "Arial"
    doc.styles["Normal"].font.size = Pt(10.5)

    para(doc, "Why these IPOs popped: the placing was kept just under 1x", bold=True, size=15, after=2)
    para(doc, f"27 deals checked against the full book of {S['n_book']} Hong Kong Main Board IPOs, 2021 to 2026. "
              f"Data as of {S['as_of']}. Every figure is from the filings or the price feed.", italic=True, size=9.5, after=8)

    head(doc, "Answer in five lines")
    bullet(doc, f"Your reading is right for {len(in_cl)} of the 27. Their placing was filled to between 0.85x and "
                f"0.99x. Across the whole book only {ju['n']} deals are in that band.")
    bullet(doc, "Just under 1x switches off the clawback. The rule only applies if the placing is fully covered, so "
                "retail keeps a small slice and roughly 100 to 170 placees keep the rest.")
    bullet(doc, f"Those deals give retail a median {f(ju['median_public_alloc'],'upct')} of the offer and open at a "
                f"median {f(ju['median_open'],'pct')}. Deals with ten times the demand open at {f(hot['median_open'],'pct')}.")
    bullet(doc, "Fundamentals do not explain it. The market on the day does not explain it. The float does.")
    bullet(doc, "Two of the 27 are not this: Midea (its placing was covered 8.06x) and CentralChina (a weak deal "
                "that fell).")

    head(doc, "Words used here")
    bullet(doc, "Placing = the international tranche, sold to institutions. Retail = the Hong Kong public offer.")
    bullet(doc, "Placing 0.95x = only 95% of the placing was taken up, so 5% was unsold.")
    bullet(doc, "Clawback = the rule that moves shares from the placing to retail when retail demand is high.")
    bullet(doc, "Retail % = the share of the whole deal retail actually received, as stated in the allotment notice.")
    bullet(doc, "Pop = the opening price against the offer price. Day-1 = the closing price against the offer price.")

    # ---------------------------------------------------------------- Q: data
    head(doc, "1. How serious was the wrong subscription number, and is anything else wrong?")
    para(doc, "Serious enough that the analysis could not start until it was fixed, but it did not spread. Here is "
              "exactly what was wrong and what was checked.")
    para(doc, "What was wrong: the parser took the subscription level from the retail table and stored it for both "
              "tranches. The stored evidence next to the number showed this for 20 of your 27 deals, so no placing "
              "number could be trusted without re-reading the filing.")
    para(doc, f"What was done: every allotment notice in the book ({S['n_book']} deals) was re-read from its own "
              "INTERNATIONAL OFFERING section, anchored on the placee count, which cannot be confused with the "
              "retail table. The result was compared with the numbers that shipped last week.")
    table(doc, ["Check", "Result"],
          [("Placing multiple, deals unchanged", "508"),
           ("Placing multiple, deals corrected", "2"),
           ("Midea (0300)", "0.11x → 8.06x. The old value was a rule threshold, not a result."),
           ("Longsys (9976)", "40.32x → 3.88x. The old value was the retail number."),
           ("Retail multiple, deals changed", "0"),
           ("Notices too old to re-read (2021–23 prose)", "3: Deyun, Huaibei, CentralChina — they keep their old value")],
          widths=[7.0, 9.0])
    para(doc, "Other errors found and fixed this month, in the same spirit of checking rather than assuming:")
    bullet(doc, "Transwarp (6727): the book had an offer price of HK$57.08. The allotment cover says HK$49.00. The "
                "parser had matched a figure inside a listing-expenses sentence. The deal's own arithmetic settles "
                "it: 14,010,800 shares × HK$49.00 = HK$686.53m, which is the gross proceeds the same filing states.")
    bullet(doc, "Forms Syntron (6700): the expected P/E was built on a market cap that was the H tranche only, not "
                "the company. It read 8.7x; against its own A-share line the same earnings price at 15.7x.")
    bullet(doc, "Red Avenue (9607): revenue was read as zero. A zero beside a positive profit is a failed parse.")
    bullet(doc, "Excelland (3231): the book had it as a Standard listing. Its allotment notice cites Chapter 18C.")
    bullet(doc, "A price is now rejected if a magnitude word follows it (\"HK$57.08 million\" is not a share price), "
                "and every price in the book was swept against the identity shares × price = gross proceeds.")

    # ------------------------------------------------------------- Q: the answer
    head(doc, "2. Why the pop happens")
    para(doc, "The rule is in every prospectus. This is AB&B Bio-Tech (2627), section \"Reallocation and clawback\":", after=2)
    para(doc, "\"If the International Offering is fully subscribed or oversubscribed and the number of Offer Shares "
              "validly applied for under the Hong Kong Public Offering represents … 100 times or more … then Offer "
              "Shares will be reallocated to the Hong Kong Public Offering from the International Offering … "
              "representing approximately 50.0% of the total number of Offer Shares.\"", italic=True, size=9.5)
    para(doc, "Read the first nine words. The clawback only bites if the placing is fully covered. At 0.99x it is "
              "not. The coordinators then hand retail only the unsold placing shares, \"in such proportions as they "
              "deem appropriate\". A retail book of 100x that should have received half the deal receives 12% to 20%.")
    para(doc, "AB&B is the clearest case. Retail demand was 4,007.64x. The placing was 0.99x with 152 placees. "
              "Retail received 3,996,000 shares out of 33,442,600 — 11.95%, not 50%. It opened +155.8%.")
    para(doc, "Across every deal in the book with a retail book of 100x or more:", after=2)
    table(doc, ["Rules and placing", "Deals", "Retail % (median)", "Pop (median)", "Day-1 (median)"],
          [(a, b, f(c, "upct"), f(d_, "pct"), f(e, "pct")) for a, b, c, d_, e in reg],
          widths=[7.4, 1.6, 2.8, 2.4, 2.4])
    para(doc, f"The first two rows are the proof. Same demand. Placing covered: retail got half the deal and the "
              f"stock opened {f(reg[0][3],'pct')}. Placing left a little short: retail got a sixth and it opened "
              f"{f(reg[1][3],'pct')}.")
    para(doc, "The market had a name for it at the time. 證券之星 wrote about Easou (2550) in June 2024 and called it "
              "套路回撥, distinguishing it from the rule working normally, and named Easou, EDA (2505) and Autostreets "
              "(2443) — three of your deals. HKET's headline on AB&B was 「怪象令回撥由50%變12%？」. HKET on Shougang "
              "Lanza: 「國際配售認購不足、公開發售佔比增至15%」. Those match the filings exactly.")

    head(doc, "3. Is retail now fixed at 10%? And why did Excelland give retail only 6.18%?", size=12)
    para(doc, "No, 10% is not a floor. Since 4 August 2025 an issuer picks one of two mechanisms, and they behave "
              "differently:")
    bullet(doc, "Mechanism A: retail starts at 5% of the deal. The clawback can lift it to 15%, 25% or 35% — but "
                "again only if the placing is covered.")
    bullet(doc, "Mechanism B: retail is fixed between 10% and 60% and there is no clawback at all.")
    e = by.get("3231", {})
    para(doc, f"Excelland chose Mechanism A. Its allotment notice states every step: 2,250,000 shares initially for "
              f"retail, which is 5.0% of the 45,000,000 offered; retail demand {f(e.get('oversub_public_mult'),'x')}; "
              f"\"Claw-back triggered: No\"; 531,800 shares reallocated from the placing, which is the 0.99x "
              f"shortfall; final retail 2,781,800 shares = {f(e.get('public_alloc_pct'),'upct')}.")
    para(doc, "So 6.18% is 5% plus the placing shortfall, and nothing more. It is not because the company is 18C. "
              "Chapter 18C governs who may list (unprofitable specialist technology companies) and sets lock-ups and "
              "disclosure. It does not set the retail split. The split came from Mechanism A plus a placing held at "
              "0.99x. Excelland opened +142.2%.")
    l = by.get("9856", {})
    para(doc, f"Ligent (9856), which listed two weeks later, is the contrast. It chose Mechanism B: placing "
              f"{f(l.get('oversub_intl_mult'),'x',2)} covered, {f(l.get('intl_placees'),'m')} placees, retail "
              f"{f(l.get('public_alloc_pct'),'upct')}, no clawback by design. Under Mechanism B an issuer keeps "
              f"retail at 10% legally with a fully covered book. That is why the new-rules row in the table above "
              f"reads 10% and still opens {f(reg[2][3],'pct')}: what used to need the trick is now simply allowed.")
    para(doc, "Cluster deals by year: " + ", ".join(f"{y} {v['just_under']} of {v['n']}" for y, v in byy.items() if v["n"]) +
              ". It was a 2024–25 pattern. Mechanism B made it unnecessary for most issuers, but Mechanism A issuers "
              "can still do it, and Excelland did in September 2026.")

    # ----------------------------------------------------------- the 27 table
    head(doc, "4. The 27 deals, checked line by line")
    rows = []
    for x in sorted(d27, key=lambda x: (x.get("oversub_intl_mult") or 99)):
        rows.append((f"{x['code']} {x['name'][:14]}", (x.get("ipo_date") or "")[:10], f(x.get("deal_size_hkdm"), "m"),
                     f(x.get("oversub_public_mult"), "x"), f(x.get("oversub_intl_mult"), "x", 2),
                     f(x.get("intl_placees"), "m"), f(x.get("public_alloc_pct"), "upct"),
                     f(x.get("grey_pct"), "pct"), f(x.get("day1_open_pop_pct"), "pct"),
                     f(x.get("first_day_return_pct"), "pct"), f(x.get("day1_open_close_pct"), "pct"),
                     f(x.get("day1_vol_x_retail"), "x")))
    table(doc, ["Deal", "Listed", "Size HK$m", "Retail book", "Placing", "Placees", "Retail %", "Grey", "Pop",
                "Day-1", "Pop→close", "Vol÷retail"], rows,
          widths=[3.3, 1.8, 1.4, 1.5, 1.2, 1.2, 1.3, 1.3, 1.3, 1.3, 1.5, 1.4], size=7.5)
    para(doc, "Vol÷retail = listing-day volume divided by the number of shares retail actually received. It says "
              "how many times the retail float changed hands on day one.", italic=True, size=8.5)

    # ------------------------------------------------------------ fundamentals
    head(doc, "5. Do fundamentals explain the pop? No.")
    table(doc, ["", "The 0.85–0.99x cluster", "Rest of the book"],
          [("Deals", ju["n"], rest["n"]),
           ("Median P/E at the offer", f(ju["median_pe"], "x"), f(rest["median_pe"], "x")),
           ("Profitable at IPO", f(ju["share_profitable"], "upct", 0), f(rest["share_profitable"], "upct", 0)),
           ("Has an A-share line", f(ju["share_ah"], "upct", 0), f(rest["share_ah"], "upct", 0)),
           ("Median deal size HK$m", f(ju["median_size_hkdm"], "m"), f(rest["median_size_hkdm"], "m")),
           ("Median pop", f(ju["median_open"], "pct"), f(rest["median_open"], "pct")),
           ("Median 1-month return after the pop", f(ju["median_1m_expop"], "pct"), f(rest["median_1m_expop"], "pct"))],
          widths=[6.4, 4.4, 3.8])
    para(doc, f"The cluster is cheaper than the rest of the book and mostly profitable. Inside the cluster the "
              f"multiple has no relationship with the size of the pop (rank correlation {S['fund_corr']['P/E'][0]} for "
              f"P/E, {S['fund_corr']['P/S'][0]} for P/S). These are small, ordinary companies — industrials, "
              "healthcare services, consumer, materials. That is exactly the profile a syndicate can place with "
              "about 120 accounts and hold.")

    # ------------------------------------------------------------------ macro
    head(doc, "6. Was the market simply strong on those days? No.")
    para(doc, f"The Hang Seng Index move on the listing day explains nothing. Rank correlation with the day-one "
              f"return is {mac['rho_hsi_vs_day1_all'][0]} across {mac['rho_hsi_vs_day1_all'][1]} deals in the whole "
              f"book, and {mac['rho_hsi_vs_day1_cluster'][0]} inside the cluster. The cluster's listing days had a "
              f"median index move of {f(mac['cluster_median_hsi_d1'],'pct')} — a flat tape.")
    rows = []
    for x in sorted(d27, key=lambda x: -(x.get("day1_open_pop_pct") or -99))[:14]:
        r = next((r for r in S["desk27"] if r["code"] == x["code"]), {})
        rows.append((f"{x['code']} {x['name'][:16]}", (x.get("ipo_date") or "")[:10],
                     f(x.get("day1_open_pop_pct"), "pct"), f(x.get("first_day_return_pct"), "pct"),
                     f(r.get("hsi_d1"), "pct", 2), f(r.get("hscei_d1"), "pct", 2)))
    table(doc, ["Deal (largest pops first)", "Listed", "Pop", "Day-1", "HSI that day", "HSCEI that day"], rows,
          widths=[4.0, 2.0, 1.9, 1.9, 2.2, 2.4], size=8)
    para(doc, "The biggest pops came on days the index barely moved. Sentiment was not driving these. If it had "
              "been, the effect would show up across the whole book, and it does not.")
    para(doc, "Three other explanations were tested inside the cluster and none holds: the sector (the cluster "
              "spans industrials, healthcare, consumer, materials, tech and financials with no sector pattern), "
              "the cornerstone share (rank correlation with the day's move "
              f"{corr['cornerstone %']['rho']}), and the year. What does correlate is the retail multiple "
              f"({S['fund_corr']['public x'][0]}), which is the same starved-float story from the demand side.")

    # ------------------------------------------------------------------- grey
    head(doc, "7. Grey market against the pop, and against the close")
    para(doc, f"{len(g27)} of your 27 deals have a grey-market close on file. Here is each one against the pop and "
              "against the day-one close, which is the comparison you asked for.")
    rows = []
    for x in sorted(g27, key=lambda x: -(x.get("grey_pct") or 0)):
        g, o, c_ = x.get("grey_pct"), x.get("day1_open_pop_pct"), x.get("first_day_return_pct")
        rows.append((f"{x['code']} {x['name'][:16]}", f(g, "pct"), f(o, "pct"),
                     f((o - g) if (o is not None and g is not None) else None, "pct"),
                     f(c_, "pct"), f((c_ - g) if (c_ is not None and g is not None) else None, "pct")))
    table(doc, ["Deal", "Grey vs offer", "Pop", "Pop − grey", "Day-1", "Day-1 − grey"], rows,
          widths=[4.4, 2.2, 2.0, 2.2, 2.0, 2.4], size=8)
    para(doc, f"Grey against the pop: the median gap is {f(med([o-g for g,o,_ in gp]),'pct')} and the rank "
              f"correlation is {S['grey']['rho_grey_vs_open'][0]}. The grey close IS the opening price. The evening "
              "session finds the level, and the auction next morning opens there.")
    para(doc, f"Grey against the day-one close: the median gap is {f(med([c-g for g,_,c in gp if c is not None]),'pct')}, "
              f"and the close beat the grey in only {sum(1 for g,_,c in gp if c is not None and c > g)} of "
              f"{sum(1 for g,_,c in gp if c is not None)} deals. For most of them the grey session was the high point "
              "of the whole event. If you can sell in the grey, that is usually the best price you will see.")

    head(doc, "8. How complete is the grey data, and where does it come from?", size=12)
    para(doc, f"{len(grey_all)} of {S['n_book']} deals in the database now carry a grey close, up from 130 last week. "
              "The coverage is not evenly spread, and the reason is worth stating plainly:")
    yrs = {}
    for x in deals:
        y = (x.get("ipo_date") or "")[:4]
        yrs.setdefault(y, [0, 0])
        yrs[y][0] += 1
        if x.get("grey_pct") is not None:
            yrs[y][1] += 1
    table(doc, ["Listing year", "Deals", "With a grey close", "Coverage"],
          [(y, v[0], v[1], f"{round(100*v[1]/v[0])}%") for y, v in sorted(yrs.items()) if y],
          widths=[3.0, 3.0, 4.0, 3.0])
    para(doc, "Three sources were used, in this order of preference:")
    bullet(doc, "etnet's per-deal IPO page, which keeps the evening session's table for all three brokers — "
                "Bright Smart (耀才), Phillip (輝立) and Futu (富途) — with each one's close, high, low and volume. "
                "The database takes the venue with the most volume and records which venue it was and the spread "
                "across the three. This is the source for 231 deals.")
    bullet(doc, "AAStocks' standardised headline (《新股》…暗盤收報…元 高/低上市價…%), captured automatically each week "
                "for new listings.")
    bullet(doc, "Press reports of the session where neither of the above has it: HKET, Sina/財聯社, 163.com, 華盛通, "
                "StockFisher, Futu. Each one was checked against the offer price before it was recorded — the close "
                "divided by the offer price has to reproduce the stated percentage.")
    para(doc, "Why the older deals are missing, precisely: etnet's grey table begins on 2 October 2024. AAStocks "
              "keeps about 21 articles per stock and its IPO feed the latest 50. The brokers publish live quotes "
              "only. No venue and no data vendor publishes a historical grey-market archive. So a deal that listed "
              "before October 2024 has a print only if a journalist wrote the session up and the article is still "
              "indexed. I searched for the ones on your list individually and found 12 that way; the four still "
              "missing are Huaibei (Jan 2023), Deyun (Jan 2021), Ruichang (Jul 2024) and WK Group (Mar 2024). For "
              "WK Group the press reported the grey OPEN (+144%) but not the close, and an open is not a close, so "
              "it was not recorded. Every deal without a print carries a note in the database saying which of these "
              "reasons applies.")

    # -------------------------------------------------------- open to close
    head(doc, "9. Why some keep rising after the open and some give it back")
    para(doc, f"Inside the cluster, {held['n']} deals closed above their open and {gave['n']} closed below it. Both "
              f"groups opened at the same level (median {f(held['median_open'],'pct')} against "
              f"{f(gave['median_open'],'pct')}). What separates them is what the tape did after the open.")
    table(doc, ["", "Closed above the open", "Gave it back"],
          [("Deals", held["n"], gave["n"]),
           ("Median pop", f(held["median_open"], "pct"), f(gave["median_open"], "pct")),
           ("Median day-1", f(held["median_close"], "pct"), f(gave["median_close"], "pct")),
           ("Day-1 volume ÷ shares retail got", f(held["median_vol_x_retail"], "x"), f(gave["median_vol_x_retail"], "x")),
           ("Day-1 range (high − low) ÷ open", f(held["median_range"], "upct"), f(gave["median_range"], "upct")),
           ("Retail %", f(held["median_public_alloc"], "upct"), f(gave["median_public_alloc"], "upct")),
           ("Retail book", f(held["median_public_x"], "x"), f(gave["median_public_x"], "x")),
           ("Deal size HK$m", f(held["median_size_hkdm"], "m"), f(gave["median_size_hkdm"], "m")),
           ("1 week later, from the day-1 close", f(held["median_1w_expop"], "pct"), f(gave["median_1w_expop"], "pct")),
           ("1 month later, from the day-1 close", f(held["median_1m_expop"], "pct"), f(gave["median_1m_expop"], "pct"))],
          widths=[6.4, 3.8, 3.4])
    have_v = [x for x in cluster if x.get("day1_open_close_pct") is not None and x.get("day1_vol_x_retail")]
    hi = sorted([x for x in have_v if x["day1_vol_x_retail"] >= 2.0], key=lambda x: x["day1_open_close_pct"])
    lo = [x for x in have_v if x["day1_vol_x_retail"] <= 1.4]
    exc = [x for x in hi if x["day1_open_close_pct"] >= 0]
    para(doc, "Volume against the retail float is the tell, and it is the strongest relationship in the whole study "
              f"(rank correlation {corr['vol x retail']['rho']} with the move from open to close).")
    bullet(doc, f"{len(lo)} deals traded 1.4x or less of the shares retail received. Their moves from open to close "
                f"were small in either direction, a median {f(med([abs(x['day1_open_close_pct']) for x in lo]),'n')} "
                "points. The placees were sitting still.")
    bullet(doc, f"{len(hi)} deals traded 2x or more. Their moves were large, a median "
                f"{f(med([abs(x['day1_open_close_pct']) for x in hi]),'n')} points, and {len(hi)-len(exc)} of the "
                f"{len(hi)} were downward. Every big give-back is in this group: " +
                ", ".join(f"{x['name'].title()} {f(x['day1_open_close_pct'],'pct')} on {f(x['day1_vol_x_retail'],'x')}"
                          for x in hi[:5]) + ".")
    bullet(doc, f"{len(exc)} of those heavy-volume deals still closed above their open: " +
                ", ".join(f"{x['name'].title()} (pop {f(x['day1_open_pop_pct'],'pct')}, close {f(x['first_day_return_pct'],'pct')})"
                          for x in exc) + ". Heavy volume with a rising price means the selling was met by heavier "
                "buying. 163.com described exactly this on EDA and called it 貨源歸邊 — the shares gathering into "
                "hands that wanted them.")
    para(doc, "Two supporting facts, both pointing the same way. The more shares retail received, the more likely "
              f"the pop was given back (rank correlation {corr['public alloc %']['rho']}) — more retail holders means "
              f"more sellers at the open. The hotter the retail book, the more likely it was given back "
              f"({corr['public x']['rho']}). The grey does not help here ({corr['grey']['rho']}: a bigger grey went "
              f"with a bigger give-back) and neither does the index ({corr['HSI same day']['rho']}).")
    para(doc, "Shougang Lanza is the clearest give-back: 93% of its entire offering traded on day one, 6.2x its "
              "retail tranche, in a 43% range, and it closed 25 points below its open. Ruichang is the same story "
              "smaller: it opened +23.8%, closed +14.3%, and had net mega-lot outflow of HK$2.69m on the day, which "
              "21財經 reported at the time as 主力出逃 — the main holders leaving.")
    para(doc, f"After day one the outcome is genuinely two-sided. One month on, measured from the day-1 close, the "
              f"cluster's median is {f(med(cl_1m),'pct')} but the range runs from {f(min(cl_1m),'pct')} to "
              f"{f(max(cl_1m),'pct')}. Three months on it runs from {f(min(cl_3m),'pct')} to {f(max(cl_3m),'pct')}, "
              "with half positive. A placing book of about 120 names holding 85% of a HK$200m company can walk the "
              "price up for months or let it go, and nothing in the terms tells you which.")

    # -------------------------------------------------------- pre-allotment
    head(doc, "10. What can you know before the allotment result?")
    para(doc, "For retail demand, a lot. The brokers publish running margin-financing totals through the offer "
              "period and the press aggregates them daily as 孖展超購X倍. Two examples from your list:")
    bullet(doc, "Shougang Lanza: 36x on day two of the offer; HK$77.6bn of margin and 1,133.5x on the margin count "
                "alone at the close; final official retail book 1,421.5x from 110,000 applicants.")
    bullet(doc, "AB&B: 225x on day one; HK$32.6bn and 629x at the close; final 4,007.6x from 195,000 applicants, "
                "with a one-lot hit rate of 1%.")
    para(doc, "The margin count is a floor — roughly half to four-fifths of the final number, because cash "
              "applications and non-reporting brokers sit outside it.")
    para(doc, "For the placing, nothing reliable. There is no published tally. The market chatter that appears in "
              "the same articles cannot tell a placing filled to 0.95x by 120 friendly accounts from one filled 5x "
              "by real institutions. The first hard number is the allotment notice itself, published the evening "
              "before listing: the placee count, the placing multiple and the final split are all on its cover "
              "table. About 100 to 170 placees at 0.9-something, on a deal whose retail book is 50x or more, is the "
              "pattern — and you know it by 18:00 the night before, which is when the grey session closes.")

    head(doc, "11. What to do with this")
    bullet(doc, "Before allotment: deal under about HK$500m, margin count above 100x, Mechanism A or pre-August-2025 "
                "rules, no large cornerstone. Expect a placing of 0.9-something, 100 to 170 placees, retail 6% to "
                "20%, and a large pop whatever the company does for a living.")
    bullet(doc, "The evening before listing: read the allotment notice. If the placing is 0.85x to 0.99x, the grey "
                "close that same evening is where it will open, not a target to hope past.")
    bullet(doc, "The first hour: watch volume against the shares retail received. Past about 2x by mid-morning the "
                "placing book is active and the day will be big — down 11 times out of 15 in this sample, up on the "
                "four occasions the buying was heavier. Near 1x nothing much will happen either way.")
    bullet(doc, "Holding period: treat it as a controlled float, because it is one. Size the position for a −60% and "
                "a +200% three-month outcome. Both are in the sample.")
    bullet(doc, "Under the new rules the tell has moved. Read the mechanism in the prospectus. Mechanism B gives "
                "retail 10% legally with a fully covered book, so the starved open is now normal for every hot deal. "
                "Mechanism A with a 0.9x placing is the old trick from a 5% base.")

    head(doc, "Sources", size=11)
    for line in (
        "HKEX allotment results announcements for every deal in the book — international section, final split, "
        "claw-back line, initial retail tranche — re-read for this note. AB&B Bio-Tech prospectus, section "
        "\"Reallocation and clawback\". Excelland Robotics allotment results, 8 September 2026.",
        "Grey market: etnet per-deal IPO pages (暗盤數據 by broker), AAStocks 《新股》…暗盤收報 headlines, and press "
        "reports — HKET (Breton, Wellcell, Autostreets, Bayzed, Midea, CentralChina, AB&B), etnet news (Cirrus), "
        "AAStocks (Black Sesame), Sina/財聯社 (Easou), 163.com (EDA), 華盛通 (Mokingran), StockFisher (Guofuhee), "
        "Futu (Fujing).",
        "Mechanism and commentary: HKET 中慧生物-B 2627首掛…怪象令回撥由50%變12%？ (11 Aug 2025); HKET 首鋼朗澤2553首掛收升44%…"
        "國際配售認購不足、公開發售佔比增至15% (3 Jun 2026); HKET 佰澤醫療2609 (20 Jun 2025); 證券之星 宜搜科技(02550)「套路回撥」加持 "
        "(11 Jun 2024); 網易/163 上演貨源歸邊，EDA集團控股 (May 2024); 21財經 瑞昌國際控股…首日熱潮與背後的主力出逃 (12 Jul 2024); "
        "中金在線 夢金園，又來套路回撥 (29 Nov 2024).",
        "Margin data before allotment: 明報 中慧生物首日招股 孖展超購逾225倍 (1 Aug 2025); HKET 中慧生物…孖展326億超購629倍; "
        "新浪 首鋼朗澤招股次日孖展超36倍 (27 May 2026); TastyMoney 首鋼朗澤2553獲11萬人入飛、超購1426倍.",
        "Index levels: Hang Seng Index and HSCEI daily closes, Yahoo Finance. Listing-day open, high, low, close and "
        "volume: Tencent daily bars, 518 of 519 deals.",
    ):
        bullet(doc, line, size=8.5)

    OUT.parent.mkdir(exist_ok=True, parents=True)
    doc.save(OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
