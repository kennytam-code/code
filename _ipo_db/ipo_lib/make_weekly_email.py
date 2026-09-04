#!/usr/bin/env python3
"""The weekly HK IPO email, generated from the book — one command, no AI.

FROM JUPYTER (the desk's way — the notebook has a cell for it):

    %run ipo.py email                 # or: sh('ipo.py', 'email')
    %run ipo.py email --weeks 1

FROM A CELL, if you want the email rendered inline underneath it:

    import sys; sys.path.insert(0, 'ipo_lib')
    import make_weekly_email as W
    W.run(weeks=2)                    # returns the text, shows the HTML

FROM A TERMINAL:

    python ipo_lib/make_weekly_email.py --weeks 2

Writes out/weekly_ipo_email.html (paste into Outlook: open in a browser,
Cmd-A, Cmd-C, paste) and out/weekly_ipo_email.txt (plain-text fallback), and
prints the text version.

JUPYTER SAFETY — three things break scripts inside a kernel and all three are
handled here, because "run it in Jupyter" must mean no traceback, ever:
  * the kernel puts its OWN arguments on sys.argv ("-f .../kernel-xxx.json"),
    which argparse rejects with SystemExit(2). We parse KNOWN args only.
  * __file__ is undefined when code is pasted into a cell, so the paths fall
    back to the working directory.
  * a Windows desk defaults to cp1252, and this email is full of en/em dashes
    and →/≫ — write_text() without an explicit encoding raises
    UnicodeEncodeError there. Every read and write below pins utf-8.

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

# __file__ is missing when this is pasted into a notebook cell; fall back to
# the working directory, which the desk's notebook asserts is _ipo_db.
try:
    _HERE = Path(__file__).resolve().parent
except NameError:                                               # pragma: no cover
    _HERE = Path.cwd() / "ipo_lib" if (Path.cwd() / "ipo_lib").is_dir() else Path.cwd()
sys.path.insert(0, str(_HERE))
from pipeline_dedupe import merge_pipeline                      # noqa: E402

ROOT = _HERE.parent
OUT_HTML = ROOT / "out" / "weekly_ipo_email.html"
OUT_TXT = ROOT / "out" / "weekly_ipo_email.txt"


def _soften_console():
    """Make the CONSOLE incapable of killing this run.

    The email is full of en/em dashes. A Windows console on cp437 cannot
    encode them and raises UnicodeEncodeError — and not necessarily in our
    own print: pipeline_dedupe prints "2 row(s) dropped — now listed", so the
    crash lands in an imported module before any local try/except can help.
    Degrading the whole stream once, up front, is the only fix that covers
    every printer. The FILES are always written as utf-8 regardless, so
    nothing is lost — only the console rendering degrades.
    """
    for s in (sys.stdout, sys.stderr):
        try:
            enc = (getattr(s, "encoding", "") or "").lower()
            if enc.replace("-", "") in ("utf8", "utf8mb4"):
                continue
            "—".encode(enc or "ascii")            # can it carry a dash?
        except (LookupError, UnicodeEncodeError, ValueError):
            try:
                s.reconfigure(errors="replace")   # py3.7+
            except Exception:
                pass
        except Exception:
            pass


_soften_console()


def _in_notebook():
    """True inside a Jupyter/IPython kernel (not a plain terminal REPL)."""
    try:
        from IPython import get_ipython
        return get_ipython() is not None and \
            "IPKernelApp" in getattr(get_ipython(), "config", {})
    except Exception:
        return False


def load(name):
    """The rows out of a batch file, whatever that batch calls its list —
    newlistings uses "deals", the PHIP feed uses "applications"."""
    p = ROOT / "data" / "batches" / name
    if not p.exists():
        return []
    d = json.loads(p.read_text(encoding="utf-8"))
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


def run(weeks=2, asof=None, show=None):
    """Build the email. Importable, so a notebook cell can call it directly.

    show=None means "render the HTML inline if we are in a notebook".
    Returns the plain-text email.
    """
    return _build(weeks=weeks, asof=asof, show=show)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, default=2, help="lookback for the listed section")
    ap.add_argument("--asof", default=None, help="pretend today is this ISO date")
    # parse_known_args, NOT parse_args: a Jupyter kernel appends its own
    # "-f /.../kernel-1234.json" to sys.argv, and parse_args would exit(2)
    # on it — the single most common way a working script "fails" in a
    # notebook. Unknown flags are ignored rather than fatal.
    a, _unknown = ap.parse_known_args()
    return _build(weeks=a.weeks, asof=a.asof, show=False)


def _build(weeks=2, asof=None, show=None):
    class a:                                     # noqa: N801 - tiny arg holder
        pass
    a.weeks, a.asof = weeks, asof
    today = date.fromisoformat(a.asof) if a.asof else date.today()

    book = ROOT / "data" / "deals.json"
    if not book.exists():
        msg = (f"deals.json not found at {book}.\n"
               f"Run the database update first:  %run ipo.py refresh\n"
               f"(or, if you only need to rebuild from existing data: "
               f"%run ipo.py build)")
        print(msg)
        return msg
    deals = json.loads(book.read_text(encoding="utf-8"))["deals"]
    notes = {}
    np_ = ROOT / "data" / "weekly_email_notes.json"
    if np_.exists():
        notes = json.loads(np_.read_text(encoding="utf-8"))

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
    # utf-8 pinned: the email carries en/em dashes and arrows, and a Windows
    # desk would otherwise die with UnicodeEncodeError on cp1252.
    OUT_HTML.write_text(html, encoding="utf-8")
    OUT_TXT.write_text(txt, encoding="utf-8")

    nb = _in_notebook() if show is None else show
    if nb:
        # render the real thing under the cell, then hand back the text
        try:
            from IPython.display import HTML, display
            display(HTML(html))
            print(f"[also written: {OUT_HTML.name} + .txt in out/ — open the "
                  f"html and copy-paste it into Outlook]")
            return txt
        except Exception:
            pass                                   # fall through to printing
    try:
        print(txt)
    except UnicodeEncodeError:                     # pragma: no cover
        # a cp1252 console cannot print the dashes; the FILES are still utf-8
        print(txt.encode("ascii", "replace").decode("ascii"))
    print(f"\n[written: {OUT_HTML.relative_to(ROOT)} + .txt — open the html in a "
          f"browser, select-all, copy, paste into the mail client]")
    return txt


if __name__ == "__main__":
    main()
