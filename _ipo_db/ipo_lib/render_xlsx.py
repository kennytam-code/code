"""Look at a workbook tab without Excel: xlsx -> HTML -> PNG.

    python ipo_lib/render_xlsx.py                       # Screener, first 70 rows x 12 cols
    python ipo_lib/render_xlsx.py --tab "SM League" --rows 30 --cols 18
    python ipo_lib/render_xlsx.py --tab Screener --col0 9 --cols 46 --row0 17 --rows 24

Fills, fonts, merges, column widths and wrap are honoured. Conditional formats
are not, and formula cells show as "f" because openpyxl carries no cached
values. Output: out/render/<tab>.html and .png (the PNG needs playwright).
"""
import argparse
import html
import re
import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent


def rgb(c):
    try:
        v = c.rgb
        if isinstance(v, str) and len(v) >= 6:
            return "#" + v[-6:]
    except Exception:
        pass
    return None


def fmt_val(c):
    v = c.value
    if v is None:
        return ""
    if isinstance(v, str):
        return "f" if v.startswith("=") else v
    if isinstance(v, float):
        nf = c.number_format or ""
        if "%" in nf:
            return f"{v:+.1f}%" if "+" in nf else f"{v:.1f}%"
        if "#,##0" in nf:
            return f"{v:,.0f}"
        if "0.0" in nf:
            return f"{v:.1f}"
        return f"{v:.2f}"
    return str(v)


def render(ws, row0, rows, col0, cols):
    merged, skip = {}, set()
    for m in ws.merged_cells.ranges:
        merged[(m.min_row, m.min_col)] = (m.max_row - m.min_row + 1, m.max_col - m.min_col + 1)
        for r in range(m.min_row, m.max_row + 1):
            for cc in range(m.min_col, m.max_col + 1):
                if (r, cc) != (m.min_row, m.min_col):
                    skip.add((r, cc))
    maxr = min(ws.max_row, row0 + rows - 1)
    maxc = min(ws.max_column, col0 + cols - 1)
    widths = [int((ws.column_dimensions[get_column_letter(ci)].width or 8.43) * 7.2)
              for ci in range(col0, maxc + 1)]
    out = []
    for r in range(row0, maxr + 1):
        h = ws.row_dimensions[r].height
        tds = []
        for ci in range(col0, maxc + 1):
            if (r, ci) in skip:
                continue
            c = ws.cell(r, ci)
            st = []
            f = c.font
            if f:
                if f.bold:
                    st.append("font-weight:bold")
                if f.italic:
                    st.append("font-style:italic")
                if f.size:
                    st.append(f"font-size:{f.size}pt")
                col = rgb(f.color) if f.color else None
                if col:
                    st.append(f"color:{col}")
            fill = rgb(c.fill.fgColor) if c.fill and c.fill.fill_type == "solid" else None
            if fill:
                st.append(f"background:{fill}")
            al = c.alignment
            if al:
                if al.horizontal:
                    st.append(f"text-align:{al.horizontal}")
                if al.wrap_text:
                    st.append("white-space:normal")
                if al.vertical:
                    st.append(f"vertical-align:{al.vertical}")
            if c.border and c.border.left and c.border.left.style:
                st.append("border:1px solid #999")
            # Excel lets text spill into an empty neighbour; so does this
            nxt = ws.cell(r, ci + 1).value if ci < maxc else None
            if isinstance(c.value, str) and nxt in (None, "") and not (al and al.wrap_text):
                st.append("overflow:visible;position:relative;z-index:1")
            span = merged.get((r, ci))
            attrs = f' rowspan="{span[0]}" colspan="{span[1]}"' if span else ""
            tds.append(f'<td{attrs} style="{";".join(st)}">{html.escape(fmt_val(c))}</td>')
        hs = f' style="height:{int(h * 1.33)}px"' if h else ""
        out.append(f"<tr{hs}><th class=rn>{r}</th>{''.join(tds)}</tr>")
    colgroup = "".join(f'<col style="width:{w}px">' for w in widths)
    heads = "".join(f"<th>{get_column_letter(i)}</th>" for i in range(col0, maxc + 1))
    total = sum(widths) + 26
    return f"""<!doctype html><meta charset=utf-8><title>{html.escape(ws.title)}</title>
<style>
body{{margin:0;background:#fff;font-family:Arial,Helvetica,sans-serif;font-size:10pt}}
table{{border-collapse:collapse;table-layout:fixed;width:{total}px}}
td{{border:1px solid #e3e3e3;padding:1px 3px;white-space:nowrap;overflow:hidden;height:17px;line-height:15px}}
th{{background:#e9e9e9;color:#555;font-weight:normal;font-size:8pt;border:1px solid #d0d0d0}}
th.rn{{width:26px}}
</style>
<div style="padding:4px 8px;background:#f4f4f4;border-bottom:1px solid #ccc;font-size:9pt">
tab: <b>{html.escape(ws.title)}</b>, rows {row0}-{maxr}, columns {get_column_letter(col0)}-{get_column_letter(maxc)}. f = formula (no cached value)</div>
<table><colgroup><col style="width:26px">{colgroup}</colgroup><tr><th></th>{heads}</tr>{''.join(out)}</table>""", total


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--book", default=str(ROOT / "out" / "HK_IPO_Database_v1.xlsx"))
    ap.add_argument("--tab", default="Screener")
    ap.add_argument("--row0", type=int, default=1)
    ap.add_argument("--rows", type=int, default=70)
    ap.add_argument("--col0", type=int, default=1)
    ap.add_argument("--cols", type=int, default=12)
    ap.add_argument("--out", default=str(ROOT / "out" / "render"))
    a, _ = ap.parse_known_args()
    wb = load_workbook(a.book)
    if a.tab not in wb.sheetnames:
        sys.exit(f"no tab {a.tab!r}; tabs: {', '.join(wb.sheetnames)}")
    page, width = render(wb[a.tab], a.row0, a.rows, a.col0, a.cols)
    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9]+", "_", a.tab).strip("_")
    hpath = outdir / f"{stem}.html"
    hpath.write_text(page, encoding="utf-8")
    print(f"wrote {hpath}")
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("playwright not installed: open the HTML in a browser instead")
        return
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": min(max(width + 40, 900), 4000), "height": 800})
        pg.goto(hpath.as_uri())
        pg.screenshot(path=str(hpath.with_suffix(".png")), full_page=True)
        b.close()
    print(f"wrote {hpath.with_suffix('.png')}")


if __name__ == "__main__":
    main()
