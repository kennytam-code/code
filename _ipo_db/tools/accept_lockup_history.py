"""Accept the 17 October source/price review, without touching the IPO database."""
import json,hashlib,statistics,shutil,sys,zipfile,gzip
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from historical_lockups import event_key,historical_events
OUT=ROOT/'out/lockup_review_20261017';DEST=ROOT/'data/lockup_review_20261017';DEST.mkdir(exist_ok=True)
batch=json.loads((OUT/'baseline_events.json').read_text())
audit=json.loads((OUT/'date_audit.json').read_text())
listing={r['code']:r for r in json.loads((OUT/'listing_date_audit.json').read_text())}
assert len(audit['rows'])==264
review={'reviewed_at':'2026-10-17','method':'Only an explicit printed cornerstone last locked date, or an explicit inclusive six-month clause with a confirmed listing date. Generic six-month terms remain excluded.','events':{}}
price_checks=[];accepted_prices=[]
for row in audit['rows']:
 e=batch['events'][row['index']]
 if not row['status'].startswith('verified') or not row['hash_matches'] or not row['first_day_matches'] or not listing[e['code']]['ok']:continue
 review['events'][event_key(e)]={**{k:row[k] for k in ['code','last_day_locked','ipo_date','url','source_sha256','page','status']},'confirmed':True,'listing_date_source':listing[e['code']]['url'],'first_unlocked_day':row['first_unlocked_day'],'clause':row.get('inclusive_clause')}
 source=json.loads((OUT/'prices'/f"{e['code']}.json").read_text())
 if not source.get('ok'):continue
 old=e.get('windows',{}).get('30 trading sessions',{})
 new=source['windows'][e['last_day_locked']]
 prior={p[1]:p[2] for p in old.get('path',[]) if p[1] and p[2]}
 fresh={p[1]:p[2] for p in new.get('path',[]) if p[1] and p[2]}
 shared=sorted(set(prior)&set(fresh));ratios=[prior[d]/fresh[d] for d in shared]
 scale=statistics.median(ratios) if ratios else None
 deviation=max((abs(x/scale-1) for x in ratios),default=None)
 # Compare returns/relative moves, allowing constant *whole-window* share
 # units. Do not apply that empirical factor to prices or splice providers.
 verified=len(shared)>=10 and deviation<1e-6
 check={'code':e['code'],'expiry':e['last_day_locked'],'overlap_sessions':len(shared),'constant_unit_ratio':scale,'max_relative_deviation':deviation,'verified':verified,'old_status':old.get('status'),'new_status':new['status'],'added_dates':sorted(set(fresh)-set(prior)),'old_only_dates':sorted(set(prior)-set(fresh)),'url':source['url']}
 price_checks.append(check)
 if not verified:continue
 new['price_basis']='Tencent raw daily closes in split-neutral units; cross-checked with stored Yahoo closes; dividends excluded'
 new['missing_sessions']=sum(p[2] is None for p in new['path'])
 e.setdefault('windows',{})['30 trading sessions']=new;e['price_url_30']=source['url'];e['price_review_30']={'reviewed_at':'2026-10-17','overlap_sessions':len(shared),'max_relative_deviation':deviation}
 accepted_prices.append(check)
# The source page is a controller table. A former parser let the earlier
# cornerstone allocation heading bleed into this later holder group.
wrong=next(e for e in batch['events'] if e['code']=='6911' and e['category']=='Cornerstone' and e.get('last_day_locked')=='2024-12-21')
wrong.update(category='Controller',filing_group='Controlling Shareholder Group',review_correction='2026-10-17: HKEX allotment PDF page 3 is the controller table; cornerstone expiry is on page 6 (21 June 2024).')
batch['historical_review']='data/lockup_review_20261017/summary.json'
(ROOT/'data/lockup_date_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
(ROOT/'data/batches/lockup_events.json').write_text(json.dumps(batch,ensure_ascii=True,indent=1)+'\n')
visible=historical_events(batch,ROOT,today='2026-10-17')
visible_keys={event_key(e) for e in visible};exclusions=[]
amendments=json.loads((ROOT/'data/lockup_amendments.json').read_text())
for e in batch['events']:
 if e['category']!='Cornerstone' or e['date_basis']=='No cornerstone tranche':continue
 if event_key(e) in visible_keys:continue
 if e['code'] in amendments['blocked_codes']:reason='Subsequent extension / holder-scope review'
 elif not e.get('last_day_locked'):reason='Undated'
 elif e['last_day_locked']>='2026-10-17':reason='Future expiry'
 elif event_key(e) not in review['events']:reason='Exact date not confirmed'
 else:reason='Incomplete or unverified 30-session price window'
 exclusions.append({'code':e['code'],'expiry':e.get('last_day_locked'),'reason':reason,'date_basis':e['date_basis']})
summary={'review_date':'2026-10-17','price_asof':batch['price_asof'],'primary_files':len(list((OUT/'sources').glob('*.json'))),'historical_dates_checked':len(audit['rows']),'date_confirmed':len(review['events']),'displayed_events':len(visible),'displayed_stocks':len({e['code'] for e in visible}),'exclusions':dict(Counter(e['reason'] for e in exclusions)),'holder_group_corrections':[{'code':'6911','date':'2024-12-21','old':'Cornerstone','new':'Controller','url':wrong['url'],'page':3}],'displayed_source_bases':dict(Counter(review['events'][event_key(e)]['status'] for e in visible)),'displayed_events_with_interior_gaps':sum(e['windows']['30 trading sessions']['missing_sessions']>0 for e in visible),'restored_complete_windows':sum(c['old_status']!='Complete' and c['new_status']=='Complete' and (c['code'],c['expiry']) in {(e['code'],e['last_day_locked']) for e in visible} for c in accepted_prices),'added_displayed_observations':sum(len(c['added_dates']) for c in accepted_prices if (c['code'],c['expiry']) in {(e['code'],e['last_day_locked']) for e in visible}),'price_validation':'All displayed prices have consistent relative moves against overlapping stored Yahoo observations; half-day/missing closes recovered from raw Tencent daily bars. No terminal verification. No interpolation. Full-sample selection requires confirmed dates and complete endpoints; it is not an unbiased universe of every IPO.'}
for name,obj in [('summary',summary),('exclusions',exclusions),('price_checks',price_checks)]:
 (DEST/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
for name in ['date_audit.json','listing_date_audit.json']:shutil.copyfile(OUT/name,DEST/name)
(DEST/'baseline_events.json.gz').write_bytes(gzip.compress((OUT/'baseline_events.json').read_bytes(),mtime=0))
for folder,name in [('sources','primary_source_pages.zip'),('prices','price_sources.zip')]:
 with zipfile.ZipFile(DEST/name,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in sorted((OUT/folder).glob('*.json')):z.write(p,p.name)
print(json.dumps(summary,ensure_ascii=False,indent=2))
