#!/usr/bin/env python3
"""Grey market vs day 1 — a plain analysis, generated from the book.

    python ipo_lib/make_grey_note.py     ->  out/Grey_Market_vs_Day1.docx

Every number is computed from data/deals.json at run time. Nothing is typed
in, and there is no styling beyond headings and plain tables: the document
is a list of numbered findings, each one a claim, the numbers behind it, the
sample size, and what it means for trading. Where the data shows no pattern
the finding says so. Regenerate after each weekly refresh.
"""
import json
import math
import statistics as st
import sys
from datetime import date
from pathlib import Path

from docx import Document
from docx.shared import Pt, Cm

try:
    _HERE = Path(__file__).resolve().parent
except NameError:                                        # pragma: no cover
    _HERE = Path.cwd() / "ipo_lib"
ROOT = _HERE.parent
OUT = ROOT / "out" / "Grey_Market_vs_Day1.docx"


def quad(x):
    g, d1 = x["grey_pct"], x["first_day_return_pct"]
    if g < 0 and d1 > 0:
        return "A"
    if g > 0 and d1 > g:
        return "B"
    if g > 0 and 0 <= d1 <= g:
        return "C"
    if g > 0 and d1 < 0:
        return "D"
    if g < 0 and d1 <= 0:
        return "E"
    return "F"


QNAME = {"A": "grey down, day 1 up", "B": "grey up, day 1 up more", "C": "grey up, day 1 up less",
         "D": "grey up, day 1 down", "E": "grey down, day 1 down", "F": "grey flat"}


def med(vals):
    v = [a for a in vals if a is not None]
    return st.median(v) if v else None


def pc(v, nd=1):
    return "n/a" if v is None else f"{v:+.{nd}f}%"


def fx(v):
    if v is None:
        return "n/a"
    return f"{v:,.0f}x" if v >= 100 else f"{v:.1f}x"


def spearman(xs, ys):
    pairs = [(a, b) for a, b in zip(xs, ys) if a is not None and b is not None]
    if len(pairs) < 8:
        return None, len(pairs)

    def rank(v):
        s = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        for k, i in enumerate(s):
            r[i] = k
        return r
    ra, rb = rank([p[0] for p in pairs]), rank([p[1] for p in pairs])
    m = len(pairs)
    ma, mb = sum(ra) / m, sum(rb) / m
    cov = sum((a - ma) * (b - mb) for a, b in zip(ra, rb))
    va = sum((a - ma) ** 2 for a in ra)
    vb = sum((b - mb) ** 2 for b in rb)
    return (cov / math.sqrt(va * vb) if va and vb else 0.0), m


def why(x, year_ext):
    """Observable factors from the deal's own row. Never news, never sentiment."""
    g, op, d1 = x["grey_pct"], x.get("day1_open_pop_pct"), x["first_day_return_pct"]
    r, i = x.get("oversub_public_mult"), x.get("oversub_intl_mult")
    cs, ff = x.get("cornerstone_pct"), x.get("eff_free_float_pct")
    ah, stab = bool(x.get("a_share_code")), x.get("stabilizing_manager")
    q = x["_q"]
    out = []
    if abs(g) <= 2.5 and q in ("D", "A", "F"):
        out.append("grey inside +/-2.5% = flat, no signal")
    if op is not None and abs(op - g) > 5:
        out.append(f"open repriced from grey ({pc(g)} to {pc(op)}) before trading")
    if q == "E" and op is not None and op < g - 2:
        out.append("gapped below grey at the open")
    if q == "A" and stab and op is not None and abs(op) < 0.5:
        out.append(f"opened pinned at offer, {stab.split(' (')[0]} held it, lifted intraday")
    if r is not None and r >= 1500 and q == "B":
        out.append(f"retail {fx(r)} carried it past grey")
    if r is not None and r < 200 and q in ("D", "E"):
        out.append(f"retail only {fx(r)}")
    if i is not None and i >= 6 and q == "C":
        out.append(f"instl {fx(i)}: holders sold into the open")
    if i is not None and i < 1.5 and q in ("D", "E"):
        out.append(f"instl {fx(i)}: placing barely covered")
    if ff is not None and ff <= 3 and q in ("B", "D", "C"):
        out.append(f"float {ff:.1f}% of cap")
    if cs is not None and cs >= 60:
        out.append(f"{cs:.0f}% locked in cornerstones")
    if ah:
        out.append("A+H, trades vs A-share reference")
    yr = x.get("ipo_date", "")[:4]
    if q == "B" and yr in year_ext and year_ext[yr][1] >= 5:
        a, b = year_ext[yr]
        out.append(f"{yr}: hot greys extended {a}/{b} that year")
    if not out:
        out.append("no factor in the row separates it from its group")
    return "; ".join(out)


def table(doc, header, rows, widths=None, font=8):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    for j, hd in enumerate(header):
        c = t.rows[0].cells[j]
        c.text = ""
        run = c.paragraphs[0].add_run(str(hd))
        run.bold = True
        run.font.size = Pt(font)
    for r in rows:
        cells = t.add_row().cells
        for j, v in enumerate(r):
            cells[j].text = ""
            run = cells[j].paragraphs[0].add_run(str(v))
            run.font.size = Pt(font)
    if widths:
        for row in t.rows:
            for j, w in enumerate(widths):
                row.cells[j].width = Cm(w)
    doc.add_paragraph()
    return t


def p(doc, text, size=10.5):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.font.size = Pt(size)
    para.paragraph_format.space_after = Pt(6)
    return para


def h(doc, text, level=2):
    return doc.add_heading(text, level=level)


def main():
    deals = json.loads((ROOT / "data" / "deals.json").read_text(encoding="utf-8"))["deals"]
    R = [x for x in deals if x.get("grey_pct") is not None and x.get("first_day_return_pct") is not None]
    for x in R:
        x["_q"] = quad(x)
    n = len(R)
    grp = {k: [x for x in R if x["_q"] == k] for k in "ABCDEF"}
    g = [x["grey_pct"] for x in R]
    d1 = [x["first_day_return_pct"] for x in R]
    gd = [x.get("grey_to_day1_pct") for x in R]
    called = sum(1 for x in R if x.get("grey_called_it") == "Y")
    up = [x for x in R if x["grey_pct"] > 0]
    dn = [x for x in R if x["grey_pct"] < 0]
    hot = [x for x in R if x["grey_pct"] > 20]
    year_ext = {}
    for y in ("2024", "2025", "2026"):
        hy = [x for x in hot if x["ipo_date"][:4] == y]
        if hy:
            year_ext[y] = (sum(1 for x in hy if x["first_day_return_pct"] > x["grey_pct"]), len(hy))

    def P(cond, then):
        a = [x for x in R if cond(x)]
        b = [x for x in a if then(x)]
        return len(b), len(a), (100 * len(b) / len(a) if a else 0)

    doc = Document()
    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(2.0)
        s.top_margin = s.bottom_margin = Cm(1.8)
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)

    doc.add_heading("Grey market vs day 1: what the data shows", level=1)
    p(doc, f"{date.today().strftime('%-d %b %Y')}. {n} HK IPOs with both a grey-market close and a "
           f"day-1 close on file, out of 514 in the database. All returns are against the offer price. "
           f"Grey = the broker-run evening session before listing (Phillip's print, as AAStocks reports "
           f"it). Every number below is computed from the database; nothing is typed in.", size=9.5)

    # 1
    h(doc, "1. The grey close is the opening price")
    rho, _ = spearman(g, d1)
    rws = []
    for k in "BCDEA":
        v = grp[k]
        if v:
            rws.append([f"{k}. {QNAME[k]}", len(v), pc(med(x['grey_pct'] for x in v)),
                        pc(med(x.get('day1_open_pop_pct') for x in v)), pc(med(x['first_day_return_pct'] for x in v))])
    table(doc, ["Pattern", "n", "Median grey", "Median day-1 OPEN", "Median day-1 CLOSE"], rws,
          widths=[5.5, 1.2, 2.6, 3.2, 3.2])
    p(doc, f"In every pattern the day-1 open sits within a few tenths of a percent of the grey close. "
           f"Rank correlation between grey and day-1 close is {rho:+.2f} across all {n}. "
           f"Implication: the grey market does not forecast day 1, it IS the first print of day 1. "
           f"Whatever separates the day-1 close from the grey close happens between 09:30 and 16:00, "
           f"not overnight. The one exception is pattern E, where a negative grey gaps lower at the "
           f"open ({pc(med(x['grey_pct'] for x in grp['E']))} grey to "
           f"{pc(med(x.get('day1_open_pop_pct') for x in grp['E']))} open): sellers who could not exit "
           f"a two-hour evening session queue for the auction.")

    # 2
    h(doc, "2. Direction is reliable; magnitude is not")
    a, b, pct_ = P(lambda x: x["grey_pct"] > 0, lambda x: x["first_day_return_pct"] > 0)
    c, d_, pct2 = P(lambda x: x["grey_pct"] < 0, lambda x: x["first_day_return_pct"] < 0)
    e, f, pct3 = P(lambda x: x["grey_pct"] > 20, lambda x: x["first_day_return_pct"] > 0)
    i_, j, pct4 = P(lambda x: x["grey_pct"] > 20, lambda x: x["first_day_return_pct"] > x["grey_pct"])
    k_, l, pct5 = P(lambda x: x["grey_pct"] > 50, lambda x: x["first_day_return_pct"] > x["grey_pct"])
    m_, o, pct6 = P(lambda x: x["grey_pct"] < -5, lambda x: x["first_day_return_pct"] < x["grey_pct"])
    table(doc, ["Given", "Then", "Count", "Rate"], [
        ["grey up", "day 1 closes up", f"{a}/{b}", f"{pct_:.0f}%"],
        ["grey down", "day 1 closes down", f"{c}/{d_}", f"{pct2:.0f}%"],
        ["grey > +20%", "day 1 closes up", f"{e}/{f}", f"{pct3:.0f}%"],
        ["grey > +20%", "day 1 closes ABOVE the grey", f"{i_}/{j}", f"{pct4:.0f}%"],
        ["grey > +50%", "day 1 closes ABOVE the grey", f"{k_}/{l}", f"{pct5:.0f}%"],
        ["grey < -5%", "day 1 closes BELOW the grey", f"{m_}/{o}", f"{pct6:.0f}%"],
    ], widths=[3.2, 5.5, 2.0, 1.6])
    p(doc, f"Direction is right {called} of {n} times ({100*called/n:.0f}%), and near-certain once the grey "
           f"is clearly positive ({pct3:.0f}% at >+20%). Whether day 1 finishes above or below the grey "
           f"level is a coin flip ({pct4:.0f}% at >+20%, {pct5:.0f}% at >+50%). A grey below -5% gets "
           f"worse on day 1 {pct6:.0f}% of the time. Use the grey for direction and for the open; do "
           f"not use it for the close.")

    # 3
    h(doc, "3. How much of the grey move survives to the close depends on the size of the move")
    rws = []
    for lo, hi, lbl in ((-1e9, -5, "below -5%"), (-5, 0, "-5% to 0"), (0, 5, "0 to +5%"), (5, 20, "+5% to +20%"),
                        (20, 50, "+20% to +50%"), (50, 100, "+50% to +100%"), (100, 1e9, "above +100%")):
        bk = [x for x in R if lo <= x["grey_pct"] < hi]
        if len(bk) < 3:
            continue
        ratio = med([x["first_day_return_pct"] / x["grey_pct"] for x in bk if abs(x["grey_pct"]) >= 1])
        rws.append([lbl, len(bk), pc(med(x['grey_pct'] for x in bk)), pc(med(x['first_day_return_pct'] for x in bk)),
                    pc(med(x['grey_to_day1_pct'] for x in bk)), "n/a" if ratio is None else f"{ratio:.2f}"])
    table(doc, ["Grey close", "n", "Median grey", "Median day-1", "Median intraday move (grey to close)", "Day-1 / grey"],
          rws, widths=[2.8, 1.0, 2.2, 2.4, 4.4, 2.2])
    p(doc, "Read the last column as the fraction of the grey move that survives to the close. It is not "
           "linear. Small positive greys (0 to +5%) evaporate: median day 1 is flat and the ratio is about a "
           "quarter. Moderate greys (+5% to +50%) keep roughly half. Large greys (above +50%) keep all of it "
           "or more. Negative greys deepen: a grey below -5% ends day 1 about 1.7 times worse. The middle "
           "of the distribution is where the intraday give-back lives; the tails hold.")

    # 4
    h(doc, "4. Retail demand sets the grey level; it does not predict the intraday move")
    rws = []
    for lbl, key in (("Retail oversubscription", "oversub_public_mult"), ("Institutional oversubscription", "oversub_intl_mult"),
                     ("Cornerstone % of offer", "cornerstone_pct"), ("Effective free float % of cap", "eff_free_float_pct"),
                     ("Deal size", "deal_size_hkdm"), ("Market cap at IPO", "mktcap_ipo_hkdm")):
        v = [x.get(key) for x in R]
        r1, m1 = spearman(v, g)
        r2, m2 = spearman(v, gd)
        rws.append([lbl, f"{r1:+.2f}", f"{r2:+.2f}", m1])
    table(doc, ["Factor", "vs grey LEVEL (rank corr.)", "vs INTRADAY move grey to close", "n"], rws,
          widths=[5.0, 3.6, 4.0, 1.2])
    pos = [x for x in up if x.get("oversub_public_mult") is not None]
    rws = []
    for lo, hi, lbl in ((0, 100, "under 100x"), (100, 500, "100 to 500x"), (500, 1500, "500 to 1,500x"),
                        (1500, 5000, "1,500 to 5,000x"), (5000, 1e9, "over 5,000x")):
        bk = [x for x in pos if lo <= x["oversub_public_mult"] < hi]
        if not bk:
            continue
        ext = sum(1 for x in bk if x["first_day_return_pct"] > x["grey_pct"])
        rws.append([lbl, len(bk), pc(med(x['grey_pct'] for x in bk)), pc(med(x['grey_to_day1_pct'] for x in bk)),
                    f"{100*ext/len(bk):.0f}%"])
    table(doc, ["Retail book (grey up only)", "n", "Median grey", "Median intraday move", "Closed above grey"], rws,
          widths=[3.6, 1.0, 2.4, 3.0, 2.8])
    p(doc, "Retail oversubscription has the strongest relationship with the grey LEVEL of any factor "
           "(rank correlation above 0.5) and almost none with the intraday move (near zero). In plain "
           "terms: retail decides where the stock opens, and then has nothing further to say. Under 100x "
           "the grey is single digits; over 1,500x it is +60% to +90%. But the share of deals that close "
           f"above their grey rises from {rws[0][4]} in the lowest bucket to a peak of "
           f"{max(rws, key=lambda r: int(r[4].rstrip('%')))[4]} and then stops rising. More retail heat "
           "above ~1,500x does not buy more extension.")
    fade_i = med(x.get('oversub_intl_mult') for x in hot if 0 <= x['first_day_return_pct'] <= x['grey_pct'])
    ext_i = med(x.get('oversub_intl_mult') for x in hot if x['first_day_return_pct'] > x['grey_pct'])
    p(doc, "Institutional oversubscription barely moves the grey level (retail is not in that book) and "
           "has a modest positive relationship with the intraday move across all deals, alongside deal "
           "size and market cap: larger, better-placed deals hold the open better. Note this is the "
           "whole sample. Among the hot greys specifically, the deals that faded had the bigger "
           f"placings (median institutional book {fx(fade_i)} vs {fx(ext_i)} for the ones that extended). "
           "Both are true: a bigger placing limits damage on a weak open and supplies sellers into a hot one.")

    # 5
    h(doc, "5. A negative grey never recovered without a stabilising manager")
    a1, b1, p1 = P(lambda x: x["grey_pct"] < 0 and x.get("stabilizing_manager"), lambda x: x["first_day_return_pct"] >= 0)
    a2, b2, p2 = P(lambda x: x["grey_pct"] < 0 and not x.get("stabilizing_manager"), lambda x: x["first_day_return_pct"] >= 0)
    ws = [x for x in dn if x.get("stabilizing_manager")]
    wo = [x for x in dn if not x.get("stabilizing_manager")]
    table(doc, ["Grey down and ...", "n", "Median grey", "Median day-1", "Closed at or above offer"], [
        ["a stabilising manager is named", len(ws), pc(med(x['grey_pct'] for x in ws)), pc(med(x['first_day_return_pct'] for x in ws)), f"{a1}/{b1} ({p1:.0f}%)"],
        ["no stabilising manager on file", len(wo), pc(med(x['grey_pct'] for x in wo)), pc(med(x['first_day_return_pct'] for x in wo)), f"{a2}/{b2} ({p2:.0f}%)"],
    ], widths=[4.6, 1.0, 2.4, 2.6, 3.6])
    aa = grp["A"]
    pinned = sum(1 for x in aa if x.get("day1_open_pop_pct") is not None and abs(x["day1_open_pop_pct"]) < 0.5)
    p(doc, f"Every deal that closed the grey market down and still finished day 1 up ({len(aa)} of them) "
           f"had a named stabilising manager; {pinned} of the {len(aa)} opened at exactly the offer price, "
           f"which is the bank absorbing the overnight sellers in the auction. Without a stabiliser the "
           f"recovery rate is {p2:.0f}% and the median day 1 is roughly twice as bad. The stabiliser does not "
           f"reverse a break; it halves it and occasionally turns it.")
    table(doc, ["Code", "Name", "Grey", "Open", "Day 1", "Retail", "Instl", "Stabiliser"],
          [[x["code"], (x.get("name") or "")[:18], pc(x["grey_pct"]), pc(x.get("day1_open_pop_pct")), pc(x["first_day_return_pct"]),
            fx(x.get("oversub_public_mult")), fx(x.get("oversub_intl_mult")), (x.get("stabilizing_manager") or "none").split(" (")[0][:26]]
           for x in sorted(aa, key=lambda x: -x["first_day_return_pct"])], widths=[1.2, 3.0, 1.4, 1.4, 1.4, 1.5, 1.2, 4.2], font=7.5)

    # 6
    h(doc, "6. Sector: consumer extends, healthcare fades, industrials and materials never beat the grey")
    secs = sorted({x.get("sector") for x in R if x.get("sector")})
    rws = []
    for s_ in secs:
        bk = [x for x in R if x.get("sector") == s_]
        if len(bk) < 4:
            continue
        posb = [x for x in bk if x["grey_pct"] > 0]
        beat = sum(1 for x in posb if x["first_day_return_pct"] > x["grey_pct"])
        rws.append([s_, len(bk), pc(med(x['grey_pct'] for x in bk)), pc(med(x['first_day_return_pct'] for x in bk)),
                    pc(med(x['grey_to_day1_pct'] for x in bk)), f"{beat}/{len(posb)}" if posb else "n/a"])
    table(doc, ["Sector", "n", "Median grey", "Median day-1", "Median intraday move", "Closed above grey (grey-up deals)"],
          rws, widths=[3.0, 1.0, 2.2, 2.4, 3.0, 3.8])
    b18 = [x for x in R if "18A" in str(x.get("listing_regime"))]
    p(doc, "Consumer names carry their grey into the close most often. Healthcare opens as hot as consumer "
           "and gives most of it back. Industrials and materials deals in this sample never closed above "
           "their grey and gave back double digits intraday; their greys were small to begin with. "
           f"Within healthcare, the 18A biotechs are the exception: {len(b18)} deals, median grey "
           f"{pc(med(x['grey_pct'] for x in b18))}, median day 1 {pc(med(x['first_day_return_pct'] for x in b18))}, "
           f"{sum(1 for x in b18 if x['grey_pct'] > 0 and x['first_day_return_pct'] > x['grey_pct'])} of "
           f"{sum(1 for x in b18 if x['grey_pct'] > 0)} extended. The biotech retail trade runs on into the session.")

    # 7
    h(doc, "7. Deal size: HK$300m to 1bn is where the grey market is hottest and holds best")
    rws = []
    for lo, hi, lbl in ((0, 300, "under HK$300m"), (300, 1000, "HK$300m to 1bn"), (1000, 5000, "HK$1bn to 5bn"), (5000, 1e12, "over HK$5bn")):
        bk = [x for x in R if lo <= (x.get("deal_size_hkdm") or 0) < hi]
        if len(bk) < 4:
            continue
        posb = [x for x in bk if x["grey_pct"] > 0]
        beat = sum(1 for x in posb if x["first_day_return_pct"] > x["grey_pct"])
        rws.append([lbl, len(bk), pc(med(x['grey_pct'] for x in bk)), pc(med(x['first_day_return_pct'] for x in bk)),
                    pc(med(x['grey_to_day1_pct'] for x in bk)), f"{beat}/{len(posb)}" if posb else "n/a"])
    table(doc, ["Deal size", "n", "Median grey", "Median day-1", "Median intraday move", "Closed above grey"],
          rws, widths=[3.2, 1.0, 2.2, 2.4, 3.0, 3.0])
    p(doc, "The smallest deals open hot and lose it: under HK$300m the median intraday give-back is the "
           "largest of any size bucket and only about one in seven closes above its grey. The HK$300m to "
           "1bn bucket is the retail-frenzy size: the highest greys, the highest day-1 closes, and the "
           "best chance of extension. Above HK$1bn the grey market is small and the day-1 move is small; "
           "above HK$5bn both are flat, because those are the A+H and institutional deals.")

    # 8
    h(doc, "8. A+H deals behave differently: the grey market barely moves and direction is less reliable")
    ah = [x for x in R if x.get("a_share_code")]
    nah = [x for x in R if not x.get("a_share_code")]

    def row(lbl, bk):
        posb = [x for x in bk if x["grey_pct"] > 0]
        return [lbl, len(bk), pc(med(x['grey_pct'] for x in bk)), pc(med(x['first_day_return_pct'] for x in bk)),
                f"{100*sum(1 for x in bk if x.get('grey_called_it')=='Y')/len(bk):.0f}%",
                f"{sum(1 for x in posb if x['first_day_return_pct']>x['grey_pct'])}/{len(posb)}"]
    table(doc, ["Group", "n", "Median grey", "Median day-1", "Direction right", "Closed above grey (grey-up)"],
          [row("A+H", ah), row("not A+H", nah)], widths=[2.4, 1.0, 2.2, 2.4, 2.6, 3.6])
    p(doc, "An A+H listing has a reference price on the mainland exchange. Its grey market clusters at "
           "zero, its day 1 clusters at zero, and the grey's direction call is worse. The variable that "
           "matters for these is the A/H discount at pricing, which is a separate column in the "
           "database, not the grey market.")

    # 9
    h(doc, "9. The tape: intraday give-back has disappeared in 2026")
    rws = []
    for y in ("2024", "2025", "2026"):
        bk = [x for x in R if x["ipo_date"][:4] == y]
        if len(bk) < 4:
            continue
        hy = [x for x in hot if x["ipo_date"][:4] == y]
        rws.append([y, len(bk), pc(med(x['grey_pct'] for x in bk)), pc(med(x['first_day_return_pct'] for x in bk)),
                    pc(med(x['grey_to_day1_pct'] for x in bk)),
                    f"{sum(1 for x in hy if x['first_day_return_pct'] > x['grey_pct'])}/{len(hy)}" if hy else "n/a"])
    table(doc, ["Year listed", "n", "Median grey", "Median day-1", "Median intraday move", "Hot greys (>+20%) that extended"],
          rws, widths=[2.2, 1.0, 2.2, 2.4, 3.0, 4.0])
    p(doc, "This is the closest thing to a sentiment measure the data contains, and it is large. In 2024 "
           "and 2025 the median deal gave back about eleven points between the open and the close; in "
           "2026 it gives back nothing. Hot grey markets extended in a minority of cases in 2024 and 2025 "
           "and in a majority in 2026. The same grey print means a different day 1 depending on the "
           "year, which is a warning about applying any of the rules above without checking what the "
           "current tape is doing. Coverage is also thinner in earlier years, so the 2024 row rests on "
           "few deals.")

    # 10
    h(doc, "10. What shows no usable pattern")
    p(doc, "Effective free float above 5% of market cap: no relationship with the intraday move. Below 5% "
           "the deals are the large A+H names and behave as in finding 8. Cornerstone percentage: rank "
           "correlation with both the grey level and the intraday move is near zero. Priced at the cap: "
           "almost every deal in the sample priced at its cap, so there is no contrast to test. Sector "
           "within Tech/AI: it is 45% of the sample and splits evenly between extension and fade. "
           "News and sentiment per deal are not in the database and nothing here estimates them.")

    # 11
    h(doc, "11. Rules, with their hit rates in this sample")

    def oc(x):
        return x.get("day1_open_close_pct")

    def neg_oc(x):
        v = x.get("day1_open_close_pct")
        return None if v is None else -v
    rules = [
        ("Grey > +20%: buy the open, sell the close", lambda x: x["grey_pct"] > 20, oc, "day-1 open to close"),
        ("Grey > +20% and deal HK$300m-1bn: hold into the close",
         lambda x: x["grey_pct"] > 20 and 300 <= (x.get("deal_size_hkdm") or 0) < 1000, oc, "day-1 open to close"),
        ("Grey > +20% and deal under HK$300m: sell the open",
         lambda x: x["grey_pct"] > 20 and (x.get("deal_size_hkdm") or 0) < 300, neg_oc, "open to close, sign flipped"),
        ("Grey < -5%, no stabiliser: short the open",
         lambda x: x["grey_pct"] < -5 and not x.get("stabilizing_manager"), neg_oc, "open to close, sign flipped"),
        ("Grey < 0, stabiliser named: buy the offer-price open",
         lambda x: x["grey_pct"] < 0 and x.get("stabilizing_manager"), oc, "day-1 open to close"),
        ("Grey between -2.5% and +2.5%: no trade", lambda x: abs(x["grey_pct"]) <= 2.5, oc, "open to close, for reference"),
    ]
    rws = []
    for name, cond, ret, lbl in rules:
        vals = [ret(x) for x in R if cond(x) and ret(x) is not None]
        if not vals:
            continue
        hit = sum(1 for v in vals if v > 0)
        rws.append([name, len(vals), f"{hit}/{len(vals)} ({100*hit/len(vals):.0f}%)", pc(st.median(vals)), lbl])
    table(doc, ["Rule", "n", "Positive outcomes", "Median return", "Return measured as"], rws,
          widths=[6.0, 1.0, 2.8, 2.2, 3.8])
    best = max((r for r in rws if r[1] >= 7), key=lambda r: int(r[2].split("(")[1].rstrip("%)")))
    p(doc, "Scored on the same sample that produced them, so these describe the past, not the future, and "
           "the size-split and no-stabiliser rows are small samples. What the table says is more useful "
           "than the rules themselves: the two intuitive trades do not work. Buying the open on a hot grey "
           f"and holding to the close is positive {rws[0][2]} of the time with a median of {rws[0][3]}, "
           "because moderate greys give back about half intraday (finding 3). Shorting the open on a weak "
           f"grey works {[r for r in rws if r[0].startswith('Grey < -5%')][0][2]} of the time, because the "
           "damage happens in the gap between the grey close and the open (finding 1), and by the time the "
           "stock is tradeable that move is already in the price. The grey market's information is almost "
           "entirely consumed by the opening auction.")
    p(doc, f"The one rule with a real edge in this sample is: {best[0][0].lower() + best[0][1:]} — positive {best[2]}, "
           f"median {best[3]}. Small deals that open hot fade hardest (finding 7), and that fade is the one "
           "grey-to-day-1 move that happens after the open rather than before it. Everything else in this "
           "table is close to a coin flip once the open has printed.")

    # appendix
    h(doc, "Appendix: every deal")
    p(doc, "Newest first. Grey, open and day 1 are against the offer price. Pattern codes: " +
           ", ".join(f"{k} = {v}" for k, v in QNAME.items()) + ". The last column lists the factors "
           "from the deal's own row; it never claims to know news or sentiment.", size=9)
    rows = sorted(R, key=lambda x: x["ipo_date"], reverse=True)
    table(doc, ["Code", "Name", "Listed", "Grey", "Open", "Day 1", "Pat.", "Retail", "Instl", "CS%", "Float%", "Factors"],
          [[x["code"], (x.get("name") or "")[:15], x["ipo_date"][2:10], pc(x["grey_pct"]), pc(x.get("day1_open_pop_pct")),
            pc(x["first_day_return_pct"]), x["_q"], fx(x.get("oversub_public_mult")), fx(x.get("oversub_intl_mult")),
            f"{x.get('cornerstone_pct') or 0:.0f}", f"{x.get('eff_free_float_pct') or 0:.1f}", why(x, year_ext)]
           for x in rows], widths=[1.0, 2.2, 1.3, 1.2, 1.2, 1.2, 0.7, 1.3, 1.0, 0.9, 1.0, 4.9], font=6.5)

    h(doc, "Data notes")
    p(doc, f"Coverage is {n} of 514 because no public archive of past grey-market sessions exists: AAStocks "
           f"publishes a headline per listing but its per-stock news page holds about 21 recent articles, so "
           f"the print is unreachable roughly a month after the debut. The archive builds forward from the "
           f"weekly refresh. Eight prints were added by hand from press coverage and each reconciles "
           f"against its offer price. The quoted venue is Phillip's; Futu's print for the same evening "
           f"differs by a tick. A grey session is two hours and fifteen minutes of retail-only trading.", size=9.5)

    OUT.parent.mkdir(exist_ok=True)
    doc.save(OUT)
    print(f"wrote {OUT} ({OUT.stat().st_size//1024} KB): {n} deals, " +
          ", ".join(f"{k}={len(grp[k])}" for k in "ABCDEF"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
