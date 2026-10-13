"""Exercise every filed event's graph, selector, gaps and displayed returns."""
import asyncio,os
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parent.parent

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path=os.environ.get('PLAYWRIGHT_EXECUTABLE_PATH'),args=['--renderer-process-limit=1','--js-flags=--max-old-space-size=128'])
  try:
   page=await browser.new_page(viewport={'width':1440,'height':1100})
   errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   await page.goto((ROOT/'out/hk_ipo_dashboard.html').as_uri())
   await page.click('a[data-tab="lockup"]')
   result=await page.evaluate('''async () => {
     const fail = (m) => {throw new Error(m);};
     if (document.querySelectorAll('#lockup-stock option').length !== new Set(LOCKUPS.map(e=>e.code)).size) fail('stock coverage');
     if (document.querySelectorAll('#lockup-tbl tbody tr').length !== LOCKUPS.length) fail('event coverage');
     let charts = 0, withheld = 0, gaps = 0;
     for (let i = 0; i < LOCKUPS.length; i++) {
       selectedLockup = i; renderSelectedLockup();
       const e = LOCKUPS[i], w = e.window, svg = document.querySelector('#lockup-history svg');
       const count = (w.path || []).filter(p => Number.isFinite(p[2])).length;
       const wanted = Boolean(w.anchor_close && count);
       if (Boolean(svg) !== wanted) fail(`event ${i} chart availability`);
       if (document.querySelector('#lockup-stock').value !== e.code || Number(document.querySelector('#lockup-event').value) !== i) fail(`event ${i} selectors`);
       for (const k of ['before','after']) {
         const value = w[k+'_pct'], expected = Number.isFinite(value) ? fmt.pct(value) : '—';
         if (document.querySelector('#lockup-'+k).textContent !== expected) fail(`event ${i} ${k} return`);
       }
       if (wanted) {
         charts++;
         if (Number(svg.dataset.points) !== count || svg.dataset.anchor !== w.anchor) fail(`event ${i} observations`);
         let segments=0, started=false;
         for (const p of w.path) {if (!Number.isFinite(p[2])) {started=false; continue;} if (!started) segments++; started=true;}
         const path=svg.querySelector('path').getAttribute('d');
         if ((path.match(/M/g)||[]).length !== segments || /NaN|Infinity|undefined/.test(path)) fail(`event ${i} path gaps`);
         if (segments>1) gaps++;
       } else withheld++;
       if (i%60===0) await new Promise(r=>setTimeout(r,0));
     }
     redrawLockupTab();
     return {events:LOCKUPS.length,stocks:deals.length,charts,withheld,gaps};
   }''')
   for status in ['Complete','Upcoming expiry','After window pending','Missing close / suspended']:
    event=await page.evaluate('(status) => LOCKUPS.findIndex(e=>e.window.status===status)',status)
    if event<0:continue
    code=await page.evaluate('(i) => LOCKUPS[i].code',event)
    await page.select_option('#lockup-stock',code)
    await page.select_option('#lockup-event',str(event))
    assert await page.evaluate('selectedLockup')==event
   await page.locator('.lockup-select').first.click()
   assert await page.evaluate('selectedLockup')==int(await page.locator('.lockup-select').first.get_attribute('data-event'))
   await page.select_option('#lockup-sec','Technology')
   assert await page.evaluate("[...document.querySelectorAll('#lockup-tbl tbody tr')].every(r=>LOCKUPS[Number(r.dataset.event)].sector==='Technology')")
   await page.select_option('#lockup-sec','')
   await page.evaluate('chooseLockup(lockupDefault.code); renderSelectedLockup()')
   await page.evaluate('window.scrollTo(0,0)')
   assert not await page.locator('#lockup-stock-picks').is_visible()
   assert await page.locator('#lockup-before').evaluate('(e)=>getComputedStyle(e).color')=='rgb(181, 57, 57)'
   await page.screenshot(path=str(ROOT/'out/lockup_html_preview.png'),full_page=False)
   await page.click('#theme')
   assert await page.locator('#lockup-history svg').count()==1
   await page.screenshot(path=str(ROOT/'out/lockup_html_dark_preview.png'),full_page=False)
   assert not errors,errors
   print('PASS all HTML event charts/returns, gaps, filters, row clicks and light/dark themes:',result)
   await browser.close()

  finally:
   await browser.close()
asyncio.run(main())
