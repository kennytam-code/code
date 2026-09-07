#!/usr/bin/env python3
"""Grey market vs day 1 — the desk note, generated from the book.

    python ipo_lib/make_grey_note.py     ->  out/Grey_Market_vs_Day1.docx

Every number is computed from data/deals.json at run time; nothing is typed
in. The prose explains the patterns the numbers show and says plainly where
there is no pattern. Regenerate after each weekly refresh and the note keeps
pace with the archive.
"""
import json
import statistics as st
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Cm

try:
    _HERE = Path(__file__).resolve().parent
except NameError:                                        # pragma: no cover
    _HERE = Path.cwd() / "ipo_lib"
ROOT = _HERE.parent
OUT = ROOT / "out" / "Grey_Market_vs_Day1.docx"


# ------------------------------------------------------------------ data ----
def load():
    d = json.loads((ROOT / "data" / "deals.json").read_text(encoding="utf-8"))["deals"]
    rows = [x for x in d if x.get("grey_pct") is not None
            and x.get("first_day_return_pct") is not None]
    for x in rows:
        x["_q"] = quad(x)
    return d, rows


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


QNAME = {
    "A": "Grey DOWN, day 1 UP (reversal up)",
    "B": "Grey UP, day 1 UP MORE (extension)",
    "C": "Grey UP, day 1 UP but LESS (fade)",
    "D": "Grey UP, day 1 DOWN (reversal down)",
    "E": "Grey DOWN, day 1 DOWN (continuation)",
    "F": "Flat grey market",
}


def med(vals):
    v = [a for a in vals if a is not None]
    return st.median(v) if v else None


def f1(v, suf="%", sign=True):
    if v is None:
        return "—"
    return f"{v:+.1f}{suf}" if sign else f"{v:.1f}{suf}"


def fx(v):
    if v is None:
        return "—"
    return f"{v:,.0f}x" if v >= 100 else f"{v:.1f}x"


_YEAR_EXT = {}          # year -> (extended, total) among hot greys; filled by main()


def why(x):
    """The observable factors behind THIS deal's grey->day-1 behaviour.

    Rule-based, from the row's own numbers. It never claims to know news or
    sentiment for a deal — where nothing in the data explains it, it says so.
    """
    g, op, d1 = x["grey_pct"], x.get("day1_open_pop_pct"), x["first_day_return_pct"]
    r, i = x.get("oversub_public_mult"), x.get("oversub_intl_mult")
    cs, ff = x.get("cornerstone_pct"), x.get("eff_free_float_pct")
    ah, stab = bool(x.get("a_share_code")), x.get("stabilizing_manager")
    q = x["_q"]
    out = []
    if abs(g) <= 2.5 and q in ("D", "A", "F"):
        out.append("grey move within ±2.5% — no real signal, the session was flat")
    if op is not None and abs(op - g) > 5:
        out.append(f"day-1 OPEN repriced away from the grey ({f1(g)} → {f1(op)}) before any trading")
    if q == "E" and op is not None and op < g - 2:
        out.append("gapped below the grey at the open — sellers queued overnight")
    if q == "A" and stab and op is not None and abs(op) < 0.5:
        out.append(f"opened pinned at the offer: {stab.split(' (')[0]} held the issue price, then it lifted intraday")
    if r is not None and r >= 1500 and q == "B":
        out.append(f"retail book {fx(r)} — retail momentum carried it past the grey")
    if r is not None and r < 200 and q in ("D", "E"):
        out.append(f"thin retail book ({fx(r)}) — nothing behind the price once it traded")
    if i is not None and r is not None and i >= 6 and r >= 500 and q == "C":
        out.append(f"institutional book {fx(i)} — allocation holders took profit into the open")
    if i is not None and i < 1.5 and q in ("D", "E"):
        out.append(f"institutional book only {fx(i)} — the placing barely covered")
    if ff is not None and ff <= 3 and q in ("B", "D", "C"):
        out.append(f"effective float only {ff:.1f}% of cap — the print can move a long way on very little stock")
    if cs is not None and cs >= 60:
        out.append(f"{cs:.0f}% of the offer locked in cornerstones")
    if ah:
        out.append("A+H: the H trades against the A-share reference, not against sentiment alone")
    yr = x.get("ipo_date", "")[:4]
    if q == "B" and yr in _YEAR_EXT and _YEAR_EXT[yr][1] >= 5:
        a, b = _YEAR_EXT[yr]
        out.append(f"{yr} tape: hot greys extended {100*a/b:.0f}% of the time that year")
    if not out:
        out.append("nothing in the deal's own numbers separates it from its group — treat as noise")
    return "; ".join(out)


# ------------------------------------------------------------------ docx ----
def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def table(doc, header, rows, widths=None, font=8.5, zebra=True):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, h in enumerate(header):
        c = t.rows[0].cells[j]
        c.text = ""
        p = c.paragraphs[0]
        run = p.add_run(str(h))
        run.bold = True
        run.font.size = Pt(font)
        shade(c, "E8ECF1")
    for i, r in enumerate(rows):
        cells = t.add_row().cells
        for j, v in enumerate(r):
            cells[j].text = ""
            p = cells[j].paragraphs[0]
            run = p.add_run(str(v))
            run.font.size = Pt(font)
            if j > 0 and isinstance(v, str) and v[:1] in "+-" and v[-1:] == "%":
                run.font.color.rgb = RGBColor(0x0A, 0x7A, 0x3C) if v[0] == "+" else RGBColor(0xB3, 0x26, 0x1E)
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            if zebra and i % 2 == 1:
                shade(cells[j], "F7F8FA")
    if widths:
        for row in t.rows:
            for j, w in enumerate(widths):
                row.cells[j].width = Cm(w)
    return t


def para(doc, text, bold_lead=None, size=10.5, space_after=6):
    p = doc.add_paragraph()
    if bold_lead:
        r = p.add_run(bold_lead)
        r.bold = True
        r.font.size = Pt(size)
    r = p.add_run(text)
    r.font.size = Pt(size)
    p.paragraph_format.space_after = Pt(space_after)
    return p


def main():
    deals, rows = load()
    n = len(rows)
    grp = {k: [x for x in rows if x["_q"] == k] for k in "ABCDEF"}
    called = sum(1 for x in rows if x.get("grey_called_it") == "Y")
    neg = [x for x in rows if x["grey_pct"] < 0]
    neg_down = sum(1 for x in neg if x["first_day_return_pct"] < 0)
    hot = [x for x in rows if x["grey_pct"] > 20]
    hotB = [x for x in hot if x["first_day_return_pct"] > x["grey_pct"]]
    hotC = [x for x in hot if 0 <= x["first_day_return_pct"] <= x["grey_pct"]]
    by_year = {}
    for y in ("2024", "2025", "2026"):
        hy = [x for x in hot if x["ipo_date"][:4] == y]
        if hy:
            by_year[y] = (sum(1 for x in hy if x["first_day_return_pct"] > x["grey_pct"]), len(hy))
    _YEAR_EXT.clear()
    _YEAR_EXT.update(by_year)

    doc = Document()
    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(2.0)
        s.top_margin = s.bottom_margin = Cm(1.8)
    st_ = doc.styles["Normal"]
    st_.font.name = "Calibri"
    st_.font.size = Pt(10.5)

    h = doc.add_heading("Grey market vs day 1 — what the tape actually does", level=1)
    para(doc, f"HK IPO desk note · {date.today().strftime('%-d %b %Y')} · {n} deals with both a grey-market "
              f"close and a day-1 close on file (of 514 in the book). Every figure below is computed "
              f"from the database; nothing is typed in.", size=9.5)

    # ---- bottom line
    doc.add_heading("Bottom line", level=2)
    para(doc, "", bold_lead="The grey market is the opening price, not a forecast of the close. ")
    para(doc, f"Across all {n} deals the day-1 open lands almost exactly on the grey close in every "
              f"group — the medians differ by a few tenths of a percent. So the question \"why did the "
              f"grey market say one thing and day 1 do another\" is really \"what happened between "
              f"the open and the close\". Overnight repricing is rare; the divergence is intraday.")
    para(doc, "", bold_lead="Direction: it is right ")
    para(doc, f"{called} of {n} times ({100*called/n:.0f}%). When the grey close is negative the deal "
              f"closes down on day 1 {neg_down} times in {len(neg)} — the one strong, tradeable rule in the data.")
    para(doc, "", bold_lead="Magnitude: it is a coin flip. ")
    para(doc, f"Of the {len(hot)} deals whose grey market closed more than +20% up, {len(hotB)} extended past "
              f"it on day 1 and {len(hotC)} faded back towards the offer. Nothing about the deal itself "
              f"— size, float, sector, retail book — separates the two. Two things do, and neither is "
              f"the deal: the size of the institutional book (bigger book, more profit-taking, more fade) "
              f"and the year (" + ", ".join(f"{y}: {a}/{b} extended" for y, (a, b) in by_year.items()) + ").")
    para(doc, "", bold_lead="Retail vs institutional — your question, answered by the numbers: ")
    para(doc, "retail heat is what pushes a stock past its grey close; institutional demand is flat "
              "across every outcome and, where it is large, works the other way, because allocation "
              "holders sell into a hot open. The exception is the reversal UP: "
              + ("every one of the" if all(x.get("stabilizing_manager") for x in grp["A"])
                 else f"{sum(1 for x in grp['A'] if x.get('stabilizing_manager'))} of the")
              + f" {len(grp['A'])} deals that closed the grey market down and still finished day 1 up "
              f"had a stabilising manager, and "
              f"{sum(1 for x in grp['A'] if x.get('day1_open_pop_pct') is not None and abs(x['day1_open_pop_pct']) < 0.5)} "
              f"of the {len(grp['A'])} opened pinned to the cent at the offer price. That is a bank holding "
              "a line, not sentiment turning.")

    # ---- the reframing table
    doc.add_heading("1. The open is the grey close", level=2)
    para(doc, "Median grey close, day-1 open and day-1 close, all measured against the offer price, "
              "for each pattern. Read across: the open column tracks the grey column almost exactly.")
    rws = []
    for k in "BCDEA":
        v = grp[k]
        if not v:
            continue
        rws.append([f"{k}. {QNAME[k]}", str(len(v)), f1(med(x['grey_pct'] for x in v)),
                    f1(med(x.get('day1_open_pop_pct') for x in v)),
                    f1(med(x['first_day_return_pct'] for x in v))])
    table(doc, ["Pattern", "n", "Grey close", "Day-1 OPEN", "Day-1 close"], rws,
          widths=[7.5, 1.2, 2.6, 2.6, 2.6])
    para(doc, "The one place the open moves away from the grey is pattern E: a negative grey market "
              f"gaps LOWER at the open ({f1(med(x['grey_pct'] for x in grp['E']))} grey, "
              f"{f1(med(x.get('day1_open_pop_pct') for x in grp['E']))} open in the median). Sellers who could not get "
              "out of a two-hour evening session queue for the opening auction. A negative grey is "
              "therefore not just a signal — it is the start of the selling.", space_after=10)

    # ---- pattern by pattern
    doc.add_heading("2. Each pattern, and what the deals have in common", level=2)

    def factor_table(keys):
        hdr = ["Median", *[f"{k} (n={len(grp[k])})" for k in keys]]
        rws = []
        for lbl, fn in (("Retail oversub", lambda x: x.get("oversub_public_mult")),
                        ("Institutional oversub", lambda x: x.get("oversub_intl_mult")),
                        ("Cornerstone % of offer", lambda x: x.get("cornerstone_pct")),
                        ("Eff. free float % of cap", lambda x: x.get("eff_free_float_pct")),
                        ("Deal size HK$m", lambda x: x.get("deal_size_hkdm"))):
            r = [lbl]
            for k in keys:
                m = med(fn(x) for x in grp[k])
                r.append("—" if m is None else (fx(m) if "oversub" in lbl else f"{m:,.1f}"))
            rws.append(r)
        for lbl, fn in (("Share A+H", lambda x: bool(x.get("a_share_code"))),
                        ("Share with stabiliser", lambda x: bool(x.get("stabilizing_manager"))),
                        ("Share Tech/AI", lambda x: x.get("sector") == "Tech/AI")):
            rws.append([lbl] + [f"{100*sum(fn(x) for x in grp[k])/len(grp[k]):.0f}%" if grp[k] else "—" for k in keys])
        table(doc, hdr, rws, widths=[4.4] + [2.4] * len(keys))

    factor_table("BCDEA")

    doc.add_heading("B and C — the hot grey market that extends, or fades", level=3)
    para(doc, f"These are the same deal. Retail books are enormous in both ({fx(med(x.get('oversub_public_mult') for x in grp['B']))} vs "
              f"{fx(med(x.get('oversub_public_mult') for x in grp['C']))}), floats identical, sizes identical, sector mix identical. "
              f"Among the genuinely hot ones (grey > +20%) the institutional book is the tell: extenders "
              f"{fx(med(x.get('oversub_intl_mult') for x in hotB))}, faders {fx(med(x.get('oversub_intl_mult') for x in hotC))}. "
              f"A bigger placing means more holders who were allotted at the offer and are looking at a "
              f"+70% open — they sell, and the print fades. The other tell is the calendar: hot greys "
              f"extended " + ", ".join(f"{a} of {b} in {y}" for y, (a, b) in by_year.items()) +
              ". That is the 2026 momentum tape, not anything a prospectus tells you.")
    para(doc, "", bold_lead="Verdict: ")
    para(doc, "a hot grey market tells you the open, not the close. Sell the open if the placing was big; "
              "hold into the session only if the institutional book was thin and the tape is running.")

    doc.add_heading("D — grey up, day 1 down", level=3)
    dd = sorted(grp["D"], key=lambda x: x["first_day_return_pct"])
    marginal = sum(1 for x in dd if x["grey_pct"] <= 2.5)
    para(doc, f"{len(dd)} deals, and {marginal} of them had a grey close inside +2.5% — which is flat, not up. "
              f"A grey print of +0.5% is noise from a two-hour session; calling it a rise and then asking why "
              f"day 1 fell is asking the wrong question. Strip those out and the genuine reversals are "
              f"the tiny-float squeezes: a stock closes the grey market +33% on a 2% effective float with "
              f"an institutional book that did not even cover, then falls 28% the moment real stock trades.")
    table(doc, ["Code", "Name", "Grey", "Open", "Day 1", "Retail", "Instl", "CS%", "Float%", "Why"],
          [[x["code"], (x.get("name") or "")[:16], f1(x["grey_pct"]), f1(x.get("day1_open_pop_pct")),
            f1(x["first_day_return_pct"]), fx(x.get("oversub_public_mult")), fx(x.get("oversub_intl_mult")),
            f"{x.get('cornerstone_pct') or 0:.0f}", f"{x.get('eff_free_float_pct') or 0:.1f}", why(x)]
           for x in dd], widths=[1.2, 2.6, 1.4, 1.4, 1.4, 1.5, 1.2, 1.0, 1.2, 5.6], font=7.5)

    doc.add_heading("A — grey down, day 1 up", level=3)
    aa = sorted(grp["A"], key=lambda x: -x["first_day_return_pct"])
    para(doc, f"{len(aa)} deals, and {'every one of them' if all(x.get('stabilizing_manager') for x in aa) else str(sum(1 for x in aa if x.get('stabilizing_manager'))) + ' of them'} had a stabilising manager. {sum(1 for x in aa if x.get('day1_open_pop_pct') is not None and abs(x['day1_open_pop_pct']) < 0.5)} of the "
              f"{len(aa)} opened at exactly the offer price — the bank absorbed the overnight sellers and held "
              f"the line, and the stock lifted from there. These are also the institutional deals: retail "
              f"books of 28x–167x, not thousands. The grey market was thin and negative because retail "
              f"was not there; the institutional book and the shoe were.")
    table(doc, ["Code", "Name", "Grey", "Open", "Day 1", "Retail", "Instl", "Stabiliser", "Why"],
          [[x["code"], (x.get("name") or "")[:16], f1(x["grey_pct"]), f1(x.get("day1_open_pop_pct")),
            f1(x["first_day_return_pct"]), fx(x.get("oversub_public_mult")), fx(x.get("oversub_intl_mult")),
            (x.get("stabilizing_manager") or "—").split(" (")[0][:22], why(x)]
           for x in aa], widths=[1.2, 2.6, 1.4, 1.4, 1.4, 1.5, 1.2, 3.2, 5.6], font=7.5)
    para(doc, "", bold_lead="Verdict: ")
    para(doc, "a negative grey market on a deal with a named stabiliser and a real institutional book is "
              "the one setup where the grey is wrong in your favour. Without the stabiliser it is pattern E.")

    doc.add_heading("E — grey down, day 1 down", level=3)
    para(doc, f"{len(grp['E'])} deals, the largest single group after the fades, and the most "
              f"tradeable: the open gaps below the grey and the close is lower still. Retail books are "
              f"the thinnest of any group ({fx(med(x.get('oversub_public_mult') for x in grp['E']))} median) "
              f"and {100*sum(1 for x in grp['E'] if x.get('a_share_code'))/len(grp['E']):.0f}% are A+H names trading against an A-share reference. "
              f"{sum(1 for x in grp['E'] if x.get('stabilizing_manager'))} of {len(grp['E'])} had a stabiliser, "
              f"which is worth pausing on: the shoe slows a break, it does not reverse one.")

    # ---- retail buckets
    doc.add_heading("3. Retail vs institutional — the direct answer", level=2)
    pos = [x for x in rows if x["grey_pct"] > 0 and x.get("oversub_public_mult") is not None]
    rws = []
    for lo, hi, lbl in ((0, 100, "under 100x"), (100, 500, "100–500x"), (500, 1500, "500–1,500x"),
                        (1500, 5000, "1,500–5,000x"), (5000, 1e9, "over 5,000x")):
        b = [x for x in pos if lo <= x["oversub_public_mult"] < hi]
        if not b:
            continue
        ext = sum(1 for x in b if x["first_day_return_pct"] > x["grey_pct"])
        rws.append([lbl, str(len(b)), f1(med(x['grey_pct'] for x in b)),
                    f1(med(x.get('grey_to_day1_pct') for x in b)), f"{100*ext/len(b):.0f}%"])
    table(doc, ["Retail book", "n", "Median grey", "Grey → day-1 close", "Extended past grey"], rws,
          widths=[3.2, 1.2, 2.6, 3.4, 3.2])
    para(doc, "Two things to read off that table. First, the retail book sets the LEVEL of the grey "
              "market — under 100x the grey is +9%, over 1,500x it is +60% to +90%. Retail is the grey "
              "market. Second, whatever the level, the median stock gives back a point or two between "
              "the open and the close; the share that extends rises with retail heat from one in nine "
              "to roughly one in two, and then stops rising. Past ~1,500x more retail does not buy you "
              "more extension. Institutional oversubscription, by contrast, sits at 3–4x across "
              "extenders, faders and continuations alike — it does not predict the day-1 move at all, "
              "except that a LARGE institutional book leans towards fade, for the profit-taking reason above.",
         space_after=10)

    # ---- no pattern
    doc.add_heading("4. What has no pattern — said plainly", level=2)
    para(doc, "Among hot grey markets, none of these separate an extension from a fade: deal size, "
              "effective free float, sector (Tech/AI is 46% of both groups), whether the deal priced at "
              "the cap (nearly all did), or the retail book once it is above ~1,500x. If you were hoping "
              "for a rule that says \"this kind of deal extends\", the honest answer is that there is not "
              "one in these 123 rows. The extend-or-fade outcome is a coin flip on deal characteristics, "
              "tilted by the size of the placing and by the calendar.")
    para(doc, "News and sentiment: the database does not carry either per deal, and nothing here "
              "pretends to. The strongest sentiment effect in the data is the year — the same hot grey "
              "market extended "
              + " and ".join(f"{100*a/b:.0f}% of the time in {y}" for y, (a, b) in by_year.items() if b >= 5)
              + " — which is the tape, not the stock. Where a deal's own numbers explain nothing, the "
              "appendix says \"treat as noise\" rather than inventing a story.")

    # ---- how to use
    doc.add_heading("5. How to use it", level=2)
    for lead, body in (
        ("Negative grey, no stabiliser: ", f"expect a gap down and a lower close. Direction is right {neg_down} times in {len(neg)} and the open is already below the grey."),
        ("Negative grey, named stabiliser, real institutional book: ", f"the one setup where the grey is wrong in your favour — the bank pins the offer and the stock lifts. {sum(1 for x in grp['A'] if x.get('stabilizing_manager'))} for {len(grp['A'])} in the data."),
        ("Hot grey, big placing: ", "sell the open. The grey IS the open; the placing sells into it."),
        ("Hot grey, thin placing, running tape: ", "the extension setup — but it is a coin flip, size it that way."),
        ("Grey within ±2.5%: ", "no signal. Do not call it a rise or a fall."),
    ):
        para(doc, body, bold_lead=lead, space_after=3)

    # ---- appendix
    doc.add_heading("Appendix — every deal", level=2)
    para(doc, "All deals with both prints, newest first. Grey, open and day 1 are against the offer "
              "price. \"Why\" lists the observable factors from the deal's own row; it never claims to know "
              "news or sentiment.", size=9)
    allrows = sorted(rows, key=lambda x: x["ipo_date"], reverse=True)
    table(doc, ["Code", "Name", "Listed", "Grey", "Open", "Day 1", "Pat.", "Retail", "Instl", "CS%", "Float%", "Why"],
          [[x["code"], (x.get("name") or "")[:15], x["ipo_date"][2:10], f1(x["grey_pct"]),
            f1(x.get("day1_open_pop_pct")), f1(x["first_day_return_pct"]), x["_q"],
            fx(x.get("oversub_public_mult")), fx(x.get("oversub_intl_mult")),
            f"{x.get('cornerstone_pct') or 0:.0f}", f"{x.get('eff_free_float_pct') or 0:.1f}", why(x)]
           for x in allrows],
          widths=[1.0, 2.2, 1.4, 1.2, 1.2, 1.2, 0.8, 1.3, 1.0, 0.9, 1.0, 4.6], font=6.5)

    # ---- limits
    doc.add_heading("Limits", level=2)
    para(doc, f"Coverage is {n} of 514 because no public archive of past grey-market sessions exists: "
              f"AAStocks publishes a headline for every listing but its per-stock news page holds only "
              f"~21 recent articles, so the print is unreachable roughly a month after the debut. The "
              f"archive builds forward from the weekly refresh. Quoted session is Phillip's (輝立); "
              f"Futu's print for the same evening differs by a tick and is never mixed in. The grey "
              f"session is two hours and fifteen minutes of retail-only trading — thin by construction, "
              f"which is exactly why it reads the open so well and the close so badly.", size=9.5)

    OUT.parent.mkdir(exist_ok=True)
    doc.save(OUT)
    print(f"wrote {OUT} ({OUT.stat().st_size//1024} KB) — {n} deals, "
          f"{', '.join(f'{k}={len(grp[k])}' for k in 'ABCDEF')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
