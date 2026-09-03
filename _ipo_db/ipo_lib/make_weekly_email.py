#!/usr/bin/env python3
"""The weekly HK IPO email, generated from the book — one command, no AI.

    python ipo_lib/make_weekly_email.py            # 2-week lookback (default)
    python ipo_lib/make_weekly_email.py --weeks 1

Writes out/weekly_ipo_email.html (paste into Outlook: open in a browser,
Cmd-A, Cmd-C, paste) and out/weekly_ipo_email.txt (plain-text fallback), and
prints the text version.

Structure:
  * WHAT'S COMING — offerings live now or listing inside the next ten days,
    with terms, timetable and a line pointing at the attached notes;
  * JUST LISTED — everything that debuted in the lookback window: pricing,
    demand, day-1 open/close, where it stands now, and THE SHOE — who runs
    it, when it dies (the filing's own stated end date), or how it ended.

Numbers come straight from deals.json. The one hand-written layer is
data/weekly_email_notes.json — short colour lines per code ("Street called
the debut …"), appended by the desk, never invented here. A deal without a
note simply gets its numbers.
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_dedupe import merge_pipeline                      # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_HTML = ROOT / "out" / "weekly_ipo_email.html"
OUT_TXT = ROOT / "out" / "weekly_ipo_email.txt"


def load(name):
    """The rows out of a batch file, whatever that batch calls its list —
    newlistings uses "deals", the PHIP feed uses "applications"."""
    p = ROOT / "data" / "batches" / name
    if not p.exists():
        return []
    d = json.loads(p.read_text())
    if isinstance(d, list):
        return d
    for k in ("deals", "applications", "rows", "pipeline"):
        if isinstance(d.get(k), list):
            return d[k]
    return []


def hkd(v, nd=1):
    return "—" if v is None else f"HK${v:,.{nd}f}m"


def pct(v):
    return "—" if v is None else f"{v:+.1f}%"


def x_(v):
    if v is None:
        return "—"
    return f"{v:,.0f}x" if v >= 100 else f"{v:.1f}x"


def ddmmm(iso):
    if not iso:
        return "tbc"
    d = date.fromisoformat(iso[:10])
    return d.strftime("%-d %b")


def sector_of(r):
    """Taxonomy label if the analyst layer has classified it; otherwise the
    filing's own industry string, which a fresh applicant always carries —
    an empty sector cell in a client-facing note reads as a mistake."""
    s, sub = r.get("sector"), r.get("subsector")
    if s:
        return f"{s} / {sub}" if sub else s
    return r.get("industry_en") or r.get("industry_aa") or "sector tbc"


def shoe_line(x, today):
    """The stabilisation story in one line — the date is the point."""
    mgr = x.get("stabilizing_manager")
    outcome = x.get("greenshoe_exercised_final")
    end = x.get("stabilization_end_date")
    if not x.get("greenshoe_pct") and not outcome:
        return "no over-allotment option — nothing to support the price"
    head = f"{mgr} runs the shoe" if mgr else "shoe"
    if outcome:
        o = str(outcome)
        if "full" in o:
            return f"{head} — exercised in full (price never needed support)"
        if "laps" in o:
            return f"{head} — lapsed{' (no over-allocation)' if 'no over' in o else ''}: stock was bought back to hold the line"
        if "partial" in o:
            return f"{head} — partially exercised"
    if end:
        d = date.fromisoformat(end)
        left = (d - today).days
        when = d.strftime("%a %-d %b")
        if left >= 0:
            return f"{head} — support can run until {when} ({left}d left)"
        return f"{head} — window closed {when}; end-of-stabilisation notice not yet located"
    return f"{head} — stabilisation window open (end date not stated in the extractable text)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, default=2, help="lookback for the listed section")
    ap.add_argument("--asof", default=None, help="pretend today is this ISO date")
    a = ap.parse_args()
    today = date.fromisoformat(a.asof) if a.asof else date.today()

    deals = json.loads((ROOT / "data" / "deals.json").read_text())["deals"]
    notes = {}
    np_ = ROOT / "data" / "weekly_email_notes.json"
    if np_.exists():
        notes = json.loads(np_.read_text())

    # ---- recent listings ---------------------------------------------------
    lo = (today - timedelta(days=7 * a.weeks)).isoformat()
    recent = sorted((x for x in deals
                     if lo <= (x.get("ipo_date") or "")[:10] <= today.isoformat()),
                    key=lambda x: x["ipo_date"], reverse=True)

    # ---- upcoming ----------------------------------------------------------
    pipe = merge_pipeline(load("newlistings.json") + load("phip_pipeline.json"))
    hi = (today + timedelta(days=10)).isoformat()
    upcoming, behind = [], []
    for r in pipe:
        if r.get("withdrawn"):
            continue
        ld = (r.get("listing_date") or "")[:10]
        live = "OFFERING" in str(r.get("status") or "").upper()
        if (ld and today.isoformat() <= ld <= hi) or (live and (not ld or ld <= hi)):
            upcoming.append(r)
        elif r.get("name"):
            behind.append(r)
    upcoming.sort(key=lambda r: r.get("listing_date") or "9999")

    monday = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
    up_names = ", ".join((r.get("name") or "").split(" Limited")[0].split(" Co.,")[0]
                         for r in upcoming[:3]) or "quiet week ahead"
    subject = f"HK IPOs — week of {monday.strftime('%-d %b')}: {up_names}"

    # ---------------------------------------------------------------- text --
    T = []
    T.append(subject)
    T.append("=" * len(subject))
    T.append("")
    T.append("Team,")
    T.append("")
    if upcoming:
        T.append("Coming up:")
        for r in upcoming:
            nm, cd = r.get("name") or "?", r.get("code") or "—"
            rng = (f"HK${r['range_lo']:.2f}–{r['range_hi']:.2f}"
                   if r.get("range_lo") and r.get("range_hi")
                   else (f"max HK${r['range_hi']:.2f}" if r.get("range_hi") else "range tbc"))
            bits = [rng]
            if r.get("mktcap_lo_hkdm") and r.get("mktcap_hi_hkdm"):
                bits.append(f"cap {r['mktcap_lo_hkdm']/1000:,.0f}–{r['mktcap_hi_hkdm']/1000:,.0f}bn")
            if r.get("cornerstone_pct"):
                bits.append(f"cornerstones ~{r['cornerstone_pct']:.0f}% of the offer")
            when = []
            if r.get("offer_period"):
                when.append(f"books close {r['offer_period'].split(' - ')[-1][5:].replace('-', '/')}")
            if r.get("listing_date"):
                when.append(f"lists {ddmmm(r['listing_date'])}")
            T.append(f"  {nm} ({cd}) — {sector_of(r)}")
            T.append(f"      {'; '.join(bits)}{('; ' + ', '.join(when)) if when else ''}")
            n = notes.get(str(cd)) or notes.get(nm, {})
            if isinstance(n, dict) and n.get("colour"):
                T.append(f"      {n['colour']}")
        T.append("")
        T.append("My notes and valuation work on "
                 + (", ".join((r.get("name") or "").split(" Limited")[0]
                              for r in upcoming if r.get("code")) or "the above")
                 + " are attached.")
        T.append("")
    else:
        T.append("Nothing launches in the next ten days that we can see; pipeline names below.")
        T.append("")

    if recent:
        T.append(f"Listed in the last {'week' if a.weeks == 1 else f'{a.weeks} weeks'}:")
        T.append("")
        for x in recent:
            nm, cd = x.get("name") or "?", x.get("code")
            px = x.get("final_price")
            T.append(f"  {nm} ({cd}) — listed {ddmmm(x.get('ipo_date'))} at HK${px:,.2f}"
                     + (f", {hkd(x.get('deal_size_hkdm'), 0)} raised" if x.get("deal_size_hkdm") else ""))
            demand = (f"      Book: public {x_(x.get('oversub_public_mult'))}, "
                      f"institutional {x_(x.get('oversub_intl_mult'))}"
                      + (f"; cornerstones {x['cornerstone_pct']:.0f}% of the offer"
                         if x.get("cornerstone_pct") else ""))
            T.append(demand)
            T.append(f"      Tape: opened {pct(x.get('day1_open_pop_pct'))}, "
                     f"day-1 close {pct(x.get('first_day_return_pct'))}, "
                     f"now {pct(x.get('since_ipo_pct'))} vs offer"
                     + (f" (px {x['price_asof'][5:].replace('-', '/')})" if x.get("price_asof") else ""))
            T.append(f"      Shoe: {shoe_line(x, today)}")
            n = notes.get(str(cd), {})
            if isinstance(n, dict) and n.get("colour"):
                T.append(f"      {n['colour']}")
            T.append("")
    if behind:
        nm3 = ", ".join(sorted({(r.get('name') or '?') for r in behind})[:6])
        T.append(f"Behind them: {nm3}.")
        T.append("")
    T.append("Shout if you want the full workbook cut on any of these.")
    T.append("")
    txt = "\n".join(T)

    # ---------------------------------------------------------------- html --
    def esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def sgn(v):
        if v is None:
            return "#666"
        return "#0a7a3c" if v > 0 else ("#b3261e" if v < 0 else "#666")

    H = []
    H.append('<div style="font-family:-apple-system,Segoe UI,Arial,sans-serif;'
             'font-size:14px;color:#1a1a1a;max-width:720px;line-height:1.45">')
    H.append(f'<p style="margin:0 0 2px"><b>{esc(subject)}</b></p>')
    H.append('<p style="margin:10px 0 14px">Team,</p>')

    if upcoming:
        H.append('<p style="margin:0 0 6px"><b>Coming up</b></p>')
        H.append('<table cellpadding="6" cellspacing="0" style="border-collapse:collapse;'
                 'font-size:13px;width:100%">')
        H.append('<tr style="background:#f2f4f7;text-align:left">'
                 '<th style="border:1px solid #d9dde3">Name</th>'
                 '<th style="border:1px solid #d9dde3">Sector</th>'
                 '<th style="border:1px solid #d9dde3">Terms</th>'
                 '<th style="border:1px solid #d9dde3">Timetable</th></tr>')
        for r in upcoming:
            rng = (f"HK${r['range_lo']:.2f}–{r['range_hi']:.2f}"
                   if r.get("range_lo") and r.get("range_hi")
                   else (f"max HK${r['range_hi']:.2f}" if r.get("range_hi") else "tbc"))
            terms = rng
            if r.get("cornerstone_pct"):
                terms += f"<br>cornerstones ~{r['cornerstone_pct']:.0f}%"
            tt = []
            if r.get("offer_period"):
                tt.append("closes " + esc(r["offer_period"].split(" - ")[-1][5:]).replace("-", "/"))
            if r.get("listing_date"):
                tt.append("lists " + ddmmm(r["listing_date"]))
            H.append('<tr>'
                     f'<td style="border:1px solid #d9dde3"><b>{esc(r.get("name") or "?")}</b>'
                     f' <span style="color:#666">{esc(r.get("code") or "")}</span></td>'
                     f'<td style="border:1px solid #d9dde3">{esc(sector_of(r))}</td>'
                     f'<td style="border:1px solid #d9dde3">{terms}</td>'
                     f'<td style="border:1px solid #d9dde3">{"<br>".join(tt) or "tbc"}</td></tr>')
            n = notes.get(str(r.get("code")), {})
            if isinstance(n, dict) and n.get("colour"):
                H.append(f'<tr><td colspan="4" style="border:1px solid #d9dde3;'
                         f'background:#fbfbfd;color:#444">{esc(n["colour"])}</td></tr>')
        H.append("</table>")
        att = ", ".join(esc((r.get("name") or "").split(" Limited")[0])
                        for r in upcoming if r.get("code"))
        H.append(f'<p style="margin:8px 0 16px">My notes and valuation work on '
                 f'<b>{att or "the above"}</b> are attached.</p>')

    if recent:
        H.append(f'<p style="margin:0 0 6px"><b>Listed in the last '
                 f'{"week" if a.weeks == 1 else str(a.weeks) + " weeks"}</b></p>')
        for x in recent:
            cd = x.get("code")
            H.append('<table cellpadding="6" cellspacing="0" style="border-collapse:collapse;'
                     'font-size:13px;width:100%;margin:0 0 10px">')
            H.append(f'<tr style="background:#f2f4f7"><td colspan="4" style="border:1px solid #d9dde3">'
                     f'<b>{esc(x.get("name") or "?")}</b> <span style="color:#666">{esc(cd)}</span>'
                     f' &nbsp;·&nbsp; listed {ddmmm(x.get("ipo_date"))} at HK${x.get("final_price"):,.2f}'
                     + (f' &nbsp;·&nbsp; {hkd(x.get("deal_size_hkdm"), 0)}' if x.get("deal_size_hkdm") else "")
                     + '</td></tr>')
            H.append('<tr>'
                     f'<td style="border:1px solid #d9dde3">Book<br><b>{x_(x.get("oversub_public_mult"))}'
                     f'</b> public / <b>{x_(x.get("oversub_intl_mult"))}</b> instl'
                     + (f'<br>cornerstones {x["cornerstone_pct"]:.0f}%' if x.get("cornerstone_pct") else "")
                     + '</td>'
                     f'<td style="border:1px solid #d9dde3">Day 1<br>'
                     f'open <b style="color:{sgn(x.get("day1_open_pop_pct"))}">{pct(x.get("day1_open_pop_pct"))}</b>, '
                     f'close <b style="color:{sgn(x.get("first_day_return_pct"))}">{pct(x.get("first_day_return_pct"))}</b></td>'
                     f'<td style="border:1px solid #d9dde3">Now vs offer<br>'
                     f'<b style="color:{sgn(x.get("since_ipo_pct"))}">{pct(x.get("since_ipo_pct"))}</b>'
                     + (f' <span style="color:#666">({esc(x["price_asof"][5:]).replace("-", "/")})</span>'
                        if x.get("price_asof") else "")
                     + '</td>'
                     f'<td style="border:1px solid #d9dde3">Shoe<br>{esc(shoe_line(x, today))}</td></tr>')
            n = notes.get(str(cd), {})
            if isinstance(n, dict) and n.get("colour"):
                H.append(f'<tr><td colspan="4" style="border:1px solid #d9dde3;'
                         f'background:#fbfbfd;color:#444">{esc(n["colour"])}</td></tr>')
            H.append("</table>")

    if behind:
        nm3 = ", ".join(sorted({esc(r.get("name") or "?") for r in behind})[:6])
        H.append(f'<p style="margin:6px 0;color:#444">Behind them: {nm3}.</p>')
    H.append('<p style="margin:14px 0 0">Shout if you want the full workbook cut on any of these.</p>')
    H.append("</div>")
    html = "\n".join(H)

    OUT_HTML.parent.mkdir(exist_ok=True)
    OUT_HTML.write_text(html)
    OUT_TXT.write_text(txt)
    print(txt)
    print(f"\n[written: {OUT_HTML.relative_to(ROOT)} + .txt — open the html in a "
          f"browser, select-all, copy, paste into the mail client]")


if __name__ == "__main__":
    main()
