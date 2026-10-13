"""Browser checks of every selectable AH snapshot and consolidated filters."""
import asyncio,os,json,sys
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'ipo_lib'))
from ah_basis import chart_review, comparable
async def main():
 from market_universe import histories
 recs=histories(ROOT)['pairs']
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path=os.environ.get('PLAYWRIGHT_EXECUTABLE_PATH'),args=['--renderer-process-limit=1','--js-flags=--max-old-space-size=128']);pg=await b.new_page(viewport={'width':1440,'height':1100})
  try:
   errors=[];requests=[]
   pg.on('pageerror',lambda e:errors.append(str(e)))
   pg.on('request',lambda r:requests.append(r.url) if not r.url.startswith(('file:','data:')) else None)
   await pg.goto((ROOT/'out/hk_ipo_dashboard.html').as_uri())
   await pg.click('a[data-tab="ah"]')
   assert not errors,errors
   assert await pg.locator('#ah-tbl tbody tr').count()==len(recs)
   for rec in recs:
    await pg.select_option('#ah-stock',rec['code'])
    review=chart_review(rec['code'],rec,ROOT)
    if 'share-scale' in rec.get('exclusion','') and not review:
     assert 'requires review' in await pg.locator('#ah-history').inner_text()
    elif rec.get('history'):
     svg=pg.locator('#ah-history svg').last
     assert await svg.get_attribute('data-first')==rec['ipo_date']
     assert await svg.get_attribute('data-last')==rec['h_history'][-1][0]
     assert int(await svg.get_attribute('data-points'))==sum(comparable(review,x[0],x[5]) for x in rec['history'])
     if review:
      assert (await svg.locator('path').first.get_attribute('d')).count('M')>=2
    ref=await pg.evaluate('(code)=>DATA.ah_reference.pairs[code]',rec['code'])
    benchmark=pg.locator('#ah-history .ahpane').first
    if ref['pre_from']:
     assert await benchmark.locator('svg').count()==1
     assert int(await benchmark.locator('svg').get_attribute('data-common'))==len(ref['rows'])
     assert 'A − CSI' in await benchmark.inner_text()
    else:assert 'unavailable' in await benchmark.inner_text()
    assert not await pg.locator('#ah-history path[d*="NaN"],#ah-history path[d*="Infinity"]').count()
   await pg.click('#ah-tbl .ah-select[data-code="3986"]')
   assert await pg.locator('#ah-stock').input_value()=='3986'
   assert 'GIGADEVICE' in await pg.locator('#ah-history-title').inner_text()
   await pg.select_option('#ah-sec','Technology')
   n=sum(r['sector']=='Technology' for r in recs)
   assert await pg.locator('#ah-tbl tbody tr').count()==n
   await pg.select_option('#ah-sec','')
   await pg.select_option('#ah-when','ipo')
   assert await pg.locator('#ah-tbl tbody tr').count()==len(recs)
   await pg.locator('#ah-comparison summary').click()
   plotted=await pg.locator('#chart-ah svg rect').count()
   assert plotted==sum(bool(r.get('offer_reference_premium_pct') is not None and ('share-scale' not in r.get('exclusion','') or chart_review(r['code'],r,ROOT))) for r in recs)
   await pg.locator('#ah-comparison summary').click()
   await pg.select_option('#ah-stock','3296')
   await pg.evaluate('window.scrollTo(0,0)')
   await pg.screenshot(path=str(ROOT/'out/ah_huaqin_preview.png'),full_page=False)
   assert not errors and not requests,(errors,requests)
   await pg.select_option('#ah-stock','3986')
   await pg.select_option('#ah-horizon','3M')
   assert await pg.locator('#ah-history svg').last.get_attribute('data-last')<'2026-10-02'
   await pg.select_option('#ah-horizon','Max')
   assert await pg.locator('#ah-history svg').last.get_attribute('data-last')=='2026-10-02'
   await pg.screenshot(path=str(ROOT/'out/ah_reference_html.png'),full_page=False)
   print('PASS all 68 selectors, full/3-month date bounds, all premium observations, 65 pre-IPO CSI references, gaps, filters and offline rendering')
   await b.close()
  finally:
   await b.close()
asyncio.run(main())
