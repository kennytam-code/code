"""Reconcile primary evidence, independent endpoint math, source bars and payload."""
import calendar,copy,gzip,hashlib,json,math,re,sys,zipfile,base64
from datetime import date,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from historical_lockups import historical_events,event_key
from review_lockups import events_from_pages
REVIEW=ROOT/'data/lockup_review_20261017'
B=json.loads((ROOT/'data/batches/lockup_events.json').read_text())
before=json.loads(gzip.decompress((REVIEW/'baseline_events.json.gz').read_bytes()))
verified=json.loads((ROOT/'data/lockup_date_review.json').read_text())['events']
listing={r['code']:r for r in json.loads((REVIEW/'listing_date_audit.json').read_text())}
visible=historical_events(B,ROOT,today='2026-10-17')
blocked=json.loads((ROOT/'data/lockup_amendments.json').read_text())['blocked_codes']
assert not ({e['code'] for e in visible}&set(blocked))
assert visible and len(B['events'])==len(before['events'])
bench=json.loads((ROOT/'data/batches/benchmark_prices.json').read_text())['benchmarks']
sessions=sorted({p[0] for b in bench.values() for p in b['closes'] if p[0]<=B['price_asof']})
assert all(date.fromisoformat(d).weekday()<5 for d in sessions)
for closed in ['2021-10-13','2023-07-17','2023-09-01','2023-09-08','2024-09-06']:assert closed not in sessions
for half in ['2024-12-24','2024-12-31','2025-01-28','2025-12-24','2025-12-31','2026-02-16']:assert half in sessions
observations=0
with zipfile.ZipFile(REVIEW/'primary_source_pages.zip') as sources,zipfile.ZipFile(REVIEW/'price_sources.zip') as prices:
 for e in visible:
  review=verified[event_key(e)];assert review['confirmed'] and listing[e['code']]['ok']
  key=hashlib.sha256(e['url'].encode()).hexdigest()[:20]
  doc=json.loads(sources.read(key+'.json'));assert doc['sha256']==e['sha256']
  pages=doc.get('ordered_pages',doc['pages']);near=[v for k,v in sorted(pages.items(),key=lambda x:int(x[0])) if abs(int(k)-e['page'])<=2]
  if review['status']=='verified printed date':assert e['last_day_locked'] in {x['last_day_locked'] for x in events_from_pages(near,review['ipo_date']) if x['category']=='Cornerstone'},(e['code'],e['last_day_locked'])
  else:
   assert review['clause'] and review['clause'] in '\n'.join(near)
   d=date.fromisoformat(review['ipo_date']);mon=d.month+6;year=d.year+(mon-1)//12;mon=(mon-1)%12+1
   anniversary=date(year,mon,min(d.day,calendar.monthrange(year,mon)[1]));assert e['last_day_locked']==(anniversary-timedelta(days=1)).isoformat()
  assert review['first_unlocked_day']==(date.fromisoformat(e['last_day_locked'])+timedelta(days=1)).isoformat()
  w=e['windows']['30 trading sessions'];assert e['last_day_locked']<'2026-10-17' and w['status']=='Complete'
  at=max(i for i,d in enumerate(sessions) if d<=e['last_day_locked'])
  assert [w[k] for k in ['pre_start','anchor','post_end']]==[sessions[at-30],sessions[at],sessions[at+30]]
  assert len(w['path'])==61 and w['post_end']<=B['price_asof']
  assert [p[:2] for p in w['path']]==[[i-30,sessions[at+i-30]] for i in range(61)]
  source=json.loads(prices.read(e['code']+'.json'));raw={p[0]:float(p[2]) for p in source['raw_rows'] if float(p[5])>0 and float(p[2])>0}
  for offset,day,close in w['path']:
   expected=raw.get(day)
   if expected is not None:expected*=math.prod(float(a['ratio']) for a in source['actions'] if a['date']<=day)
   assert close==expected;observations+=1
  for key,i in [('pre_start_close',0),('anchor_close',30),('post_end_close',60)]:assert w[key]==w['path'][i][2]>0
  assert abs(w['before_pct']-100*(w['anchor_close']/w['pre_start_close']-1))<1e-9
  assert abs(w['after_pct']-100*(w['post_end_close']/w['anchor_close']-1))<1e-9
  old=next(x for x in before['events'] if x['category']=='Cornerstone' and event_key(x)==event_key(e))['windows']['30 trading sessions']
  prior={p[1]:p[2] for p in old['path'] if p[2]};ratios=[prior[p[1]]/p[2] for p in w['path'] if p[2] and p[1] in prior]
  assert len(ratios)>=10 and max(ratios)/min(ratios)-1<1e-6
 # Regression: an earlier cornerstone allocation roster cannot own the
 # controller expiry table on page 3 (6911).
 bad=next(e for e in B['events'] if e['code']=='6911' and e.get('last_day_locked')=='2024-12-21')
 assert bad['category']=='Controller'
 doc=json.loads(sources.read(hashlib.sha256(bad['url'].encode()).hexdigest()[:20]+'.json'))
 parsed=events_from_pages([v for k,v in sorted(doc['ordered_pages'].items(),key=lambda x:int(x[0]))],'2023-12-22')
 assert {e['last_day_locked'] for e in parsed if e['category']=='Cornerstone'}=={'2024-06-21'}
# Presentation payload equals the checked sample, and does not sneak unknown
# source/date combinations or future/incomplete histories back into the UI.
html=(ROOT/'out/hk_ipo_dashboard.html').read_text();encoded=re.search(r'<script id="ipo-payload" type="application/octet-stream">([^<]+)',html)[1]
data=json.loads(gzip.decompress(base64.b64decode(encoded)));actual=data['lockups']['events']
assert {(e['code'],e['last_day_locked']) for e in actual}=={(e['code'],e['last_day_locked']) for e in visible}
assert all(e['window']['before_pct'] is not None and e['window']['after_pct'] is not None for e in actual)
assert '%%LOCKUPSNAPSHOT%%' not in html
probe=copy.deepcopy(B);probe['events']=[copy.deepcopy(visible[0])]
probe['events'][0]['last_day_locked']='2099-01-01';assert not historical_events(probe,ROOT)
probe['events'][0]=copy.deepcopy(visible[0]);probe['events'][0]['sha256']='unreviewed';assert not historical_events(probe,ROOT)
probe['events'][0]=copy.deepcopy(visible[0]);probe['events'][0]['windows']['30 trading sessions']['status']='Missing close / suspended';assert not historical_events(probe,ROOT)
release=json.loads((ROOT/'data/release_state.json').read_text())
assert hashlib.sha256((ROOT/'TO_NOMURA/HK_IPO_Database_v1.xlsx').read_bytes()).hexdigest()==release['deliverables']['HK_IPO_Database_v1.xlsx']['sha256']
print(f'PASS {len(visible)} historical events / {observations} session slots: filed dates, listing inputs, holder boundaries, raw prices, split factors, exact ±30 endpoints, return math, payload and delivered Excel hash')
