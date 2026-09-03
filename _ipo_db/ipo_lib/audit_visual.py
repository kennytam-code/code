#!/usr/bin/env python3
"""Visual gate for the dashboard — the machine version of "look at it".

Per tab, LIGHT and DARK:
  - zero page/console errors while switching and rendering;
  - no NaN / undefined / [object Object] anywhere in the page text;
  - no SVG element carrying a NaN/undefined attribute;
  - no two SVG labels covering >60% of each other (words on words);
  - no container hiding content behind a horizontal scrollbar;
  - text may ellipsize ONLY if the element carries a title tooltip.

Needs playwright + a built dashboard. Where playwright is missing (the desk),
it says so and exits 0 — this gate belongs to the build machine.
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "out" / "hk_ipo_dashboard.html"

SCAN = """() => {
  const bad = {overlaps: 0, nanText: [], nanSvg: 0, hidden: [], bareCut: 0};
  const t = document.body.innerText;
  ['NaN', 'undefined', '[object Object]', 'Infinity'].forEach(k => {
    if (t.includes(k)) bad.nanText.push(k); });
  document.querySelectorAll('svg *').forEach(e => {
    for (const a of e.attributes)
      if (/NaN|undefined/i.test(a.value)) { bad.nanSvg++; break; } });
  document.querySelectorAll('svg').forEach(svg => {
    const ts = [...svg.querySelectorAll('text')]
      .map(x => x.getBoundingClientRect()).filter(r => r.width > 0);
    for (let i = 0; i < ts.length; i++) for (let j = i + 1; j < ts.length; j++) {
      const a = ts[i], b = ts[j];
      const ox = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
      const oy = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
      if (ox * oy > 0.6 * Math.min(a.width * a.height, b.width * b.height))
        bad.overlaps++;
    }});
  document.querySelectorAll('.ahwrap, .scroll').forEach(e => {
    if (e.scrollWidth > e.clientWidth + 20)
      bad.hidden.push(e.className + ' +' + (e.scrollWidth - e.clientWidth) + 'px'); });
  document.querySelectorAll('td, span, div').forEach(e => {
    if (e.children.length || !e.textContent) return;
    const cs = getComputedStyle(e);
    if (cs.textOverflow === 'ellipsis' && e.scrollWidth > e.clientWidth + 3
        && !e.title && !e.closest('[title]')) bad.bareCut++; });
  return bad;
}"""


async def run():
    from playwright.async_api import async_playwright
    fails = []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1440, "height": 1100})
        errs = []
        pg.on("pageerror", lambda e: errs.append("PAGE:" + str(e)[:90]))
        pg.on("console", lambda m: errs.append("CON:" + m.text[:90])
              if m.type == "error" else None)
        await pg.goto(PAGE.as_uri())
        await pg.wait_for_timeout(1400)
        await pg.check("#lab-ashare")            # renders the heavy A/H panes
        await pg.wait_for_timeout(2200)
        for mode in ("light", "dark"):
            if mode == "dark":
                await pg.click("#theme")
                await pg.wait_for_timeout(400)
            for tab in ("screener", "market", "ah", "cs", "pipeline", "table"):
                await pg.click(f'a[data-tab="{tab}"]')
                await pg.wait_for_timeout(500)
                r = await pg.evaluate(SCAN)
                probs = []
                if r["overlaps"]:
                    probs.append(f"{r['overlaps']} label overlaps")
                if r["nanText"]:
                    probs.append(f"literals {r['nanText']}")
                if r["nanSvg"]:
                    probs.append(f"{r['nanSvg']} NaN svg attrs")
                if r["hidden"]:
                    probs.append(f"hidden scroll {r['hidden']}")
                if r["bareCut"]:
                    probs.append(f"{r['bareCut']} cut texts with NO tooltip")
                line = f"  {mode:5} {tab:9} " + ("OK" if not probs else "; ".join(probs))
                print(line)
                if probs:
                    fails.append(line)
        if errs:
            fails.append(f"console/page errors: {errs[:4]}")
            print("  errors:", errs[:4])
        await b.close()
    print("  RESULT:", "CLEAN" if not fails else f"{len(fails)} PROBLEMS")
    return 1 if fails else 0


def main():
    if not PAGE.exists():
        sys.exit(f"no dashboard at {PAGE} — build first")
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("audit_visual: playwright not installed here — visual gate "
              "runs on the build machine only (skipping, not failing)")
        sys.exit(0)
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
