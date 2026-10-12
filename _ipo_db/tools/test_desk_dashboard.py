"""Offline interactions for multi-stock comparisons and the new peer monitor."""
import asyncio,os,json,math
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parent.parent
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path=os.environ.get('PLAYWRIGHT_EXECUTABLE_PATH'));pg=await b.new_page(viewport={'width':1600,'height':1100})
  errors=[];requests=[];pg.on('pageerror',lambda e:errors.append(str(e)));pg.on('request',lambda r:requests.append(r.url) if not r.url.startswith(('file:','data:')) else None)
  await pg.goto((ROOT/'out/hk_ipo_dashboard.html').as_uri());await pg.click('a[data-tab="ah"]')
  assert await pg.locator('#ah-compare-chart svg').get_attribute('data-series')=='3'
  await pg.click('#ah-clear-compare');assert not await pg.locator('#ah-compare-chart svg').count()
  for c in ['3986','3308','3759','3347']:await pg.locator('.ah-compare-pick[data-code="'+c+'"]').check()
  assert await pg.locator('#ah-compare-chart svg').get_attribute('data-series')=='4'
  await pg.select_option('#ah-sec','Technology')
  assert await pg.locator('.ah-compare-pick[data-code="3986"]').is_checked()
  await pg.select_option('#ah-sec','')
  assert await pg.locator('.ah-compare-pick[data-code="3759"]').is_checked()
  n=await pg.locator('#ah-tbl tbody tr').count();assert n==68
  await pg.locator('#ah-compare-chart').screenshot(path=str(ROOT/'out/ah_comparison_html.png'))
  for mode in ['now','ipo']:
   await pg.select_option('#ah-when',mode)
   assert await pg.locator('#ah-tbl tbody tr').count()==68
  # Newly added legacy pairs are selectable but do not extend the canonical screener.
  await pg.select_option('#ah-stock','6690');assert await pg.locator('#ah-history svg').count()==1
  await pg.click('a[data-tab="lockup"]')
  await pg.select_option('#lockup-compare-mode','all')
  for x,v in [('from','2026-01-01'),('to','2026-10-02')]:await pg.locator('#lockup-compare-'+x).fill(v);await pg.locator('#lockup-compare-'+x).dispatch_event('change')
  expected=await pg.evaluate("LOCKUPS.filter(e=>e.last_day_locked>='2026-01-01'&&e.last_day_locked<='2026-10-02'&&e.window.anchor_close>0).length")
  assert int(await pg.locator('#lockup-compare-chart svg').get_attribute('data-series'))==expected+1
  await pg.select_option('#lockup-compare-mode','cohort');assert await pg.locator('#lockup-compare-chart svg').get_attribute('data-series')=='1'
  await pg.locator('#lockup-compare-chart').screenshot(path=str(ROOT/'out/lockup_cohort_html.png'))
  vals=await pg.evaluate("LOCKUPS.map((e,i)=>({e,i})).filter(x=>x.e.last_day_locked>='2026-01-01'&&x.e.last_day_locked<='2026-10-02'&&x.e.window.anchor_close>0).slice(0,3).map(x=>String(x.i))")
  await pg.select_option('#lockup-compare-mode','selected');await pg.select_option('#lockup-compare-stocks',vals)
  assert await pg.locator('#lockup-compare-chart svg').get_attribute('data-series')=='4'
  await pg.click('a[data-tab="peers"]')
  assert await pg.locator('#peer-table tbody tr').count()==6
  pairs=json.loads((ROOT/'data/peer_pairs.json').read_text())['pairs']
  for pair in pairs:
   await pg.select_option('#peer-pair',pair['id']);assert await pg.locator('#peer-performance svg').get_attribute('data-series')=='2'
   assert await pg.locator('#peer-spread svg').get_attribute('data-series')=='1'
   assert pair['name_a'] in await pg.locator('#peer-title').inner_text()
   h=pair['history']
   assert all(math.isclose(x[5],x[3]-x[4],abs_tol=1e-12) for x in h)
  await pg.locator('.peer-pick[data-pair="9856/3308"]').click();assert await pg.locator('#peer-pair').input_value()=='9856/3308'
  await pg.screenshot(path=str(ROOT/'out/peer_html_preview.png'),full_page=True)
  for chart in ['#peer-performance','#peer-spread']:
   await pg.locator(chart+' svg').hover(position={'x':240,'y':150});assert 'spread' in (await pg.locator('.tt').inner_text()).lower() or 'LIGENT' in await pg.locator('.tt').inner_text()
  assert not errors and not requests,(errors,requests)
  saved=ROOT/'out/_browser_saved_review.html';saved.write_text(await pg.content())
  other=await b.new_page();other.on('pageerror',lambda e:errors.append(str(e)));await other.goto(saved.as_uri());await other.click('a[data-tab="peers"]');assert await other.locator('#peer-table tbody tr').count()==6
  assert not errors;await b.close();saved.unlink()
  print('PASS four A/H comparisons and filtered checkboxes, 68-pair roster, expiry cohorts/ranges/selected curves, all six peer charts, math and offline browser-saved reopen')
asyncio.run(main())
