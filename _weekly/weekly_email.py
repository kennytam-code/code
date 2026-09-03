#!/usr/bin/env python3
"""
weekly_email.py - build the Monday "week ahead" desk email from a JSON week file.

    python3 weekly_email.py data/week_2026-09-07.json

Writes two files next to out/:

    out/week_ahead_<date>.html   paste straight into Outlook
    out/week_ahead_<date>.md     plain text, for Teams / a quick read

The HTML is deliberately old-fashioned: tables, inline styles, no flexbox, no
grid, no web fonts, no CSS variables. Outlook renders mail through Word, which
throws all of those away. Anything clever here comes back to the reader as an
unstyled wall of text, so nothing clever goes in.

Stdlib only. It runs on the Mac, and it runs on the terminal PC.

WHAT THIS SCRIPT DOES NOT DO
    It does not fetch. Every number in the JSON is typed or pasted by a human.
    See README.md for which fields Bloomberg can fill and which cannot be.
"""

import html
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Palette. Chosen once, used everywhere, inlined into every tag because Outlook
# discards <style> blocks.
# ---------------------------------------------------------------------------
INK = "#111820"     # headings
BODY = "#2C333D"    # running text
MUTED = "#6C757F"   # labels, sources, times
RULE = "#DCE0E5"    # hairlines
BAND = "#F4F6F8"    # table stripe and callout ground
PAPER = "#FFFFFF"
HOT = "#A3301C"     # tier 1 - the things that move the book
RATES = "#1E4E79"   # central banks and rates

SERIF = "Georgia, 'Times New Roman', serif"
SANS = "'Segoe UI', -apple-system, Helvetica, Arial, sans-serif"
MONO = "'Consolas', 'SF Mono', Menlo, monospace"

TIER = {
    1: (HOT, "#F7E9E6", "MOVES THE BOOK"),
    2: (RATES, "#E9EFF5", "WATCH"),
    3: (MUTED, BAND, "NOTED"),
}


def esc(text):
    return html.escape(str(text), quote=True)


# ---------------------------------------------------------------------------
# HTML building blocks
# ---------------------------------------------------------------------------

def h_rule():
    return (
        f'<tr><td style="padding:26px 0 26px 0;">'
        f'<div style="border-top:1px solid {RULE};font-size:0;line-height:0;">&nbsp;</div>'
        f"</td></tr>"
    )


def h_kicker(text):
    return (
        f'<div style="font-family:{SANS};font-size:11px;font-weight:600;'
        f'letter-spacing:1.4px;text-transform:uppercase;color:{MUTED};'
        f'padding-bottom:6px;">{esc(text)}</div>'
    )


def h_heading(text, size=21):
    return (
        f'<div style="font-family:{SERIF};font-size:{size}px;line-height:1.28;'
        f'font-weight:700;color:{INK};padding-bottom:12px;">{esc(text)}</div>'
    )


def h_para(text, top=0):
    return (
        f'<p style="font-family:{SANS};font-size:15px;line-height:1.62;'
        f'color:{BODY};margin:{top}px 0 12px 0;">{esc(text)}</p>'
    )


def h_numbered(steps):
    """Numbered deduction chain. One claim per line, no packed prose."""
    out = []
    for i, step in enumerate(steps, 1):
        out.append(
            f'<tr>'
            f'<td valign="top" width="30" style="font-family:{SERIF};font-size:15px;'
            f'font-weight:700;color:{HOT};padding:0 10px 12px 0;line-height:1.62;">{i}.</td>'
            f'<td valign="top" style="font-family:{SANS};font-size:15px;line-height:1.62;'
            f'color:{BODY};padding:0 0 12px 0;">{esc(step)}</td>'
            f"</tr>"
        )
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">'
        + "".join(out)
        + "</table>"
    )


def h_bullets(items):
    out = []
    for item in items:
        out.append(
            f'<tr>'
            f'<td valign="top" width="18" style="font-family:{SANS};font-size:15px;'
            f'color:{HOT};padding:0 8px 11px 0;line-height:1.62;">&bull;</td>'
            f'<td valign="top" style="font-family:{SANS};font-size:15px;line-height:1.62;'
            f'color:{BODY};padding:0 0 11px 0;">{esc(item)}</td>'
            f"</tr>"
        )
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">'
        + "".join(out)
        + "</table>"
    )


def h_verdict(text):
    """Never leave a section without one."""
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
        f'style="margin-top:6px;"><tr>'
        f'<td bgcolor="{BAND}" style="background-color:{BAND};border-left:3px solid {HOT};'
        f'padding:13px 16px 13px 15px;">'
        f'<span style="font-family:{SANS};font-size:11px;font-weight:700;letter-spacing:1.3px;'
        f'text-transform:uppercase;color:{HOT};">Verdict</span><br>'
        f'<span style="font-family:{SANS};font-size:14.5px;line-height:1.58;color:{INK};">'
        f"{esc(text)}</span>"
        f"</td></tr></table>"
    )


def h_regime(rows):
    """The standing state of the world. Label / value / note, one fact a line."""
    cells = []
    for i, row in enumerate(rows):
        bg = PAPER if i % 2 else BAND
        cells.append(
            f'<tr bgcolor="{bg}">'
            f'<td valign="top" style="background-color:{bg};font-family:{SANS};font-size:11px;'
            f'font-weight:600;letter-spacing:0.7px;text-transform:uppercase;color:{MUTED};'
            f'padding:9px 12px;border-bottom:1px solid {RULE};white-space:nowrap;">'
            f'{esc(row["label"])}</td>'
            f'<td valign="top" style="background-color:{bg};font-family:{SANS};font-size:14px;'
            f'font-weight:600;color:{INK};padding:9px 12px;border-bottom:1px solid {RULE};">'
            f'{esc(row["value"])}</td>'
            f'<td valign="top" style="background-color:{bg};font-family:{SANS};font-size:13px;'
            f'color:{MUTED};padding:9px 12px;border-bottom:1px solid {RULE};">'
            f'{esc(row.get("note", ""))}</td>'
            f"</tr>"
        )
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
        f'style="border-top:2px solid {INK};border-collapse:collapse;">'
        + "".join(cells)
        + "</table>"
    )


def h_calendar(rows):
    """The spine of the email. Grouped by day, tier marked, HKT first."""
    head = (
        f'<tr>'
        f'<td style="font-family:{SANS};font-size:10px;font-weight:700;letter-spacing:1.1px;'
        f'text-transform:uppercase;color:{MUTED};padding:0 10px 7px 0;'
        f'border-bottom:2px solid {INK};" width="62">HKT</td>'
        f'<td style="font-family:{SANS};font-size:10px;font-weight:700;letter-spacing:1.1px;'
        f'text-transform:uppercase;color:{MUTED};padding:0 10px 7px 0;'
        f'border-bottom:2px solid {INK};">Event</td>'
        f'<td style="font-family:{SANS};font-size:10px;font-weight:700;letter-spacing:1.1px;'
        f'text-transform:uppercase;color:{MUTED};padding:0 0 7px 0;'
        f'border-bottom:2px solid {INK};">Consensus / prior and why it matters</td>'
        f"</tr>"
    )

    body = []
    current_day = None
    for row in rows:
        if row["day"] != current_day:
            current_day = row["day"]
            body.append(
                f'<tr><td colspan="3" style="font-family:{SERIF};font-size:15px;'
                f'font-weight:700;color:{INK};padding:16px 0 6px 0;'
                f'border-bottom:1px solid {RULE};">{esc(current_day)}</td></tr>'
            )

        colour, chip_bg, _label = TIER.get(row.get("tier", 3), TIER[3])
        weight = "700" if row.get("tier") == 1 else "600"

        status = row.get("status", "")
        status_colour = MUTED if status == "CONFIRMED" else HOT
        status_html = (
            f'<span style="font-family:{MONO};font-size:10px;letter-spacing:0.5px;'
            f'color:{status_colour};">{esc(status)}</span>'
            if status
            else ""
        )

        detail = []
        if row.get("cons") and row["cons"] != "-":
            detail.append(f'<b style="color:{INK};">Cons:</b> {esc(row["cons"])}')
        if row.get("prior") and row["prior"] != "-":
            detail.append(f'<b style="color:{INK};">Prior:</b> {esc(row["prior"])}')
        detail_html = (
            f'<div style="font-family:{SANS};font-size:12.5px;color:{BODY};'
            f'padding-bottom:3px;">{" &nbsp;|&nbsp; ".join(detail)}</div>'
            if detail
            else ""
        )

        local = row.get("local", "")
        local_html = (
            f'<div style="font-family:{MONO};font-size:10.5px;color:{MUTED};'
            f'padding-top:2px;">{esc(local)}</div>'
            if local and local != "-"
            else ""
        )

        body.append(
            f'<tr>'
            f'<td valign="top" style="padding:9px 10px 9px 0;border-bottom:1px solid {RULE};">'
            f'<div style="font-family:{MONO};font-size:13px;font-weight:700;color:{colour};'
            f'white-space:nowrap;">{esc(row["hkt"])}</div>{local_html}</td>'
            f'<td valign="top" style="padding:9px 10px 9px 0;border-bottom:1px solid {RULE};">'
            f'<span style="font-family:{SANS};font-size:10px;font-weight:700;letter-spacing:0.6px;'
            f'color:{colour};background-color:{chip_bg};padding:2px 5px;">'
            f'{esc(row.get("region", ""))}</span>&nbsp;'
            f'<span style="font-family:{SANS};font-size:14px;font-weight:{weight};color:{INK};">'
            f'{esc(row["event"])}</span></td>'
            f'<td valign="top" style="padding:9px 0 9px 0;border-bottom:1px solid {RULE};">'
            f'{detail_html}'
            f'<div style="font-family:{SANS};font-size:13px;line-height:1.5;color:{BODY};">'
            f'{esc(row.get("why", ""))}</div>'
            f'<div style="padding-top:3px;">{status_html}'
            f'<span style="font-family:{MONO};font-size:10px;color:{MUTED};"> &middot; '
            f'{esc(row.get("src", ""))}</span></div></td>'
            f"</tr>"
        )

    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
        'style="border-collapse:collapse;">' + head + "".join(body) + "</table>"
    )


def h_datatable(table):
    """A plain comp table inside a focus block."""
    head = "".join(
        f'<td style="font-family:{SANS};font-size:10px;font-weight:700;letter-spacing:1px;'
        f'text-transform:uppercase;color:{MUTED};padding:0 10px 7px 0;'
        f'border-bottom:2px solid {INK};">{esc(h)}</td>'
        for h in table["headers"]
    )
    rows = []
    for i, row in enumerate(table["rows"]):
        bg = PAPER if i % 2 else BAND
        cells = []
        for j, cell in enumerate(row):
            weight = "600" if j == 0 else "400"
            colour = INK if j == 0 else BODY
            cells.append(
                f'<td valign="top" style="background-color:{bg};font-family:{SANS};'
                f'font-size:13.5px;font-weight:{weight};color:{colour};padding:8px 10px 8px 0;'
                f'border-bottom:1px solid {RULE};">{esc(cell)}</td>'
            )
        rows.append(f'<tr bgcolor="{bg}">' + "".join(cells) + "</tr>")
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
        'style="border-collapse:collapse;margin:4px 0 16px 0;"><tr>'
        + head
        + "</tr>"
        + "".join(rows)
        + "</table>"
    )


def h_beyond(rows):
    out = []
    for row in rows:
        colour = MUTED if row["status"] == "CONFIRMED" else HOT
        out.append(
            f'<tr>'
            f'<td valign="top" width="150" style="font-family:{MONO};font-size:12px;'
            f'font-weight:700;color:{INK};padding:0 12px 9px 0;white-space:nowrap;">'
            f'{esc(row["when"])}</td>'
            f'<td valign="top" style="font-family:{SANS};font-size:13.5px;line-height:1.5;'
            f'color:{BODY};padding:0 0 9px 0;">{esc(row["what"])} '
            f'<span style="font-family:{MONO};font-size:10px;color:{colour};">'
            f'{esc(row["status"])}</span></td>'
            f"</tr>"
        )
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">'
        + "".join(out)
        + "</table>"
    )


def build_html(d):
    parts = []
    add = parts.append

    # masthead
    add(
        f'<tr><td style="padding-bottom:4px;">'
        f'<div style="font-family:{SANS};font-size:11px;font-weight:700;letter-spacing:2px;'
        f'text-transform:uppercase;color:{HOT};">Week Ahead</div></td></tr>'
    )
    add(
        f'<tr><td style="padding-bottom:6px;">'
        f'<div style="font-family:{SERIF};font-size:27px;line-height:1.2;font-weight:700;'
        f'color:{INK};">{esc(d["week_label"])}</div></td></tr>'
    )
    add(
        f'<tr><td style="padding-bottom:20px;border-bottom:2px solid {INK};">'
        f'<div style="font-family:{SANS};font-size:12.5px;color:{MUTED};">'
        f'Written {esc(d["written"])}. {esc(d["timezone_note"])}</div></td></tr>'
    )

    # thesis
    add(f'<tr><td style="padding-top:24px;">{h_kicker("If you read nothing else")}</td></tr>')
    add(f'<tr><td>{h_numbered(d["thesis"])}</td></tr>')

    # regime
    add(h_rule())
    add(f'<tr><td>{h_kicker("Where the world is standing")}{h_regime(d["regime"])}</td></tr>')

    # calendar
    add(h_rule())
    add(
        f'<tr><td>{h_kicker("The week, hour by hour")}'
        f'{h_heading("Everything that is scheduled")}'
        f'{h_calendar(d["calendar"])}</td></tr>'
    )

    # focus blocks
    for block in d["focus"]:
        add(h_rule())
        inner = h_kicker(block["kicker"]) + h_heading(block["title"])
        if block.get("intro"):
            inner += h_para(block["intro"])
        if block.get("table"):
            inner += h_datatable(block["table"])
        if block.get("steps"):
            inner += h_numbered(block["steps"])
        if block.get("bullets"):
            inner += h_bullets(block["bullets"])
        if block.get("verdict"):
            inner += h_verdict(block["verdict"])
        add(f"<tr><td>{inner}</td></tr>")

    # beyond
    add(h_rule())
    add(
        f'<tr><td>{h_kicker("Already on the horizon")}'
        f'{h_heading("Not next week, but priced next week", 18)}'
        f'{h_beyond(d["beyond"])}</td></tr>'
    )

    # verify
    add(h_rule())
    add(
        f'<tr><td>'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"><tr>'
        f'<td bgcolor="{BAND}" style="background-color:{BAND};border-left:3px solid {MUTED};'
        f'padding:15px 18px;">'
        f'{h_kicker("Check on the terminal before this goes out")}'
        f'{h_bullets(d["verify_before_send"])}'
        f"</td></tr></table></td></tr>"
    )

    add(
        f'<tr><td style="padding-top:28px;border-top:1px solid {RULE};">'
        f'<div style="font-family:{SANS};font-size:11.5px;line-height:1.6;color:{MUTED};">'
        f"Dates marked CONFIRMED come from the issuer or the statistical agency. "
        f"Dates marked ESTIMATED follow the usual monthly pattern and have not been posted. "
        f"Consensus figures left as placeholders are deliberate - they belong on ECO, not in a draft."
        f"</div></td></tr>"
    )

    return (
        f'<div style="background-color:{PAPER};padding:28px 16px;">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="760" '
        f'align="center" style="width:760px;max-width:760px;margin:0 auto;">'
        + "".join(parts)
        + "</table></div>"
    )


# ---------------------------------------------------------------------------
# Markdown twin - for Teams, or for reading in a terminal
# ---------------------------------------------------------------------------

def build_md(d):
    L = []
    L.append(f"# Week Ahead - {d['week_label']}")
    L.append("")
    L.append(f"*Written {d['written']}. {d['timezone_note']}*")
    L.append("")
    L.append("## If you read nothing else")
    L.append("")
    for i, t in enumerate(d["thesis"], 1):
        L.append(f"{i}. {t}")
    L.append("")
    L.append("## Where the world is standing")
    L.append("")
    L.append("| | | |")
    L.append("|---|---|---|")
    for row in d["regime"]:
        L.append(f"| **{row['label']}** | {row['value']} | {row.get('note','')} |")
    L.append("")
    L.append("## The week, hour by hour")
    L.append("")
    day = None
    for row in d["calendar"]:
        if row["day"] != day:
            day = row["day"]
            L.append("")
            L.append(f"### {day}")
            L.append("")
            L.append("| HKT | Local | Event | Consensus / prior | Why it matters | Source |")
            L.append("|---|---|---|---|---|---|")
        detail = []
        if row.get("cons") and row["cons"] != "-":
            detail.append(f"Cons: {row['cons']}")
        if row.get("prior") and row["prior"] != "-":
            detail.append(f"Prior: {row['prior']}")
        mark = "**" if row.get("tier") == 1 else ""
        L.append(
            f"| `{row['hkt']}` | {row.get('local','')} | {mark}[{row.get('region','')}] "
            f"{row['event']}{mark} | {'; '.join(detail) or '-'} | {row.get('why','')} | "
            f"{row.get('status','')} - {row.get('src','')} |"
        )
    L.append("")
    for block in d["focus"]:
        L.append(f"## {block['title']}")
        L.append("")
        L.append(f"*{block['kicker']}*")
        L.append("")
        if block.get("intro"):
            L.append(block["intro"])
            L.append("")
        if block.get("table"):
            t = block["table"]
            L.append("| " + " | ".join(t["headers"]) + " |")
            L.append("|" + "---|" * len(t["headers"]))
            for r in t["rows"]:
                L.append("| " + " | ".join(str(c) for c in r) + " |")
            L.append("")
        if block.get("steps"):
            for i, s in enumerate(block["steps"], 1):
                L.append(f"{i}. {s}")
            L.append("")
        if block.get("bullets"):
            for b in block["bullets"]:
                L.append(f"- {b}")
            L.append("")
        if block.get("verdict"):
            L.append(f"> **Verdict.** {block['verdict']}")
            L.append("")
    L.append("## Not next week, but priced next week")
    L.append("")
    L.append("| When | What | |")
    L.append("|---|---|---|")
    for row in d["beyond"]:
        L.append(f"| {row['when']} | {row['what']} | {row['status']} |")
    L.append("")
    L.append("## Check on the terminal before this goes out")
    L.append("")
    for v in d["verify_before_send"]:
        L.append(f"- [ ] {v}")
    L.append("")
    return "\n".join(L)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    src = sys.argv[1]
    with open(src, encoding="utf-8") as fh:
        d = json.load(fh)

    here = os.path.dirname(os.path.abspath(src))
    out_dir = os.path.join(os.path.dirname(here), "out")
    os.makedirs(out_dir, exist_ok=True)

    stem = re.sub(r"^week_", "week_ahead_", os.path.splitext(os.path.basename(src))[0])

    html_path = os.path.join(out_dir, stem + ".html")
    md_path = os.path.join(out_dir, stem + ".md")

    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(
            "<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>Week Ahead - {esc(d['week_label'])}</title></head>"
            f"<body style='margin:0;padding:0;background-color:{PAPER};'>"
            + build_html(d)
            + "</body></html>"
        )
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(build_md(d))

    print(f"subject: {d['subject']}")
    print(f"wrote  : {html_path}")
    print(f"wrote  : {md_path}")
    print(f"events : {len(d['calendar'])}  focus blocks: {len(d['focus'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
