"""Independently fetch raw historical closes, sequentially, for date-verified events.
Never splice providers or apply an unexplained scale factor. This writes evidence,
not acceptance; acceptance follows a comparison with the stored Yahoo observations.
"""
import json,sys,gc
from pathlib import Path
from datetime import date,timedelta
import requests
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from review_lockups import window
from corp_actions import load_actions
OUT=ROOT/'out/lockup_review_20261017';CACHE=OUT/'prices';CACHE.mkdir(exist_ok=True)
B=json.loads((ROOT/'data/batches/lockup_events.json').read_text())
A=json.loads((OUT/'date_audit.json').read_text())
groups={}
for r in A['rows']:
 if r['status'].startswith('verified') and r['hash_matches'] and r['first_day_matches']:
  groups.setdefault(r['code'],[]).append(B['events'][r['index']])
bench=json.loads((ROOT/'data/batches/benchmark_prices.json').read_text())['benchmarks']
cutoff=B['price_asof'];sessions=sorted({r[0] for b in bench.values() for r in b.get('closes',[]) if r[0]<=cutoff})
actions=load_actions(ROOT);session=requests.Session();session.headers['User-Agent']='Mozilla/5.0'
errors=[]
for n,(code,events) in enumerate(groups.items(),1):
 target=CACHE/(code+'.json')
 if target.exists() and json.loads(target.read_text()).get('ok'):continue
 start=(date.fromisoformat(min(e['last_day_locked'] for e in events))-timedelta(days=100)).isoformat()
 end=min(cutoff,(date.fromisoformat(max(e['last_day_locked'] for e in events))+timedelta(days=100)).isoformat())
 symbol=f'hk{int(code):05d}';url=f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,{start},{end},1500,'
 try:
  response=session.get(url,timeout=(10,25));response.raise_for_status()
  raw=response.json()['data'][symbol].get('day',[])
  if not raw:raise ValueError('No daily bars')
  prices={r[0]:float(r[2]) for r in raw if len(r)>5 and float(r[5])>0 and float(r[2])>0}
  result={'ok':True,'code':code,'url':url,'fetched':'2026-10-17','raw_rows':raw,'actions':actions.get(code,[]),'windows':{}}
  for e in events:
   result['windows'][e['last_day_locked']]=window(e['last_day_locked'],sessions,prices,actions.get(code,[]),cutoff,days=30)
  target.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')))
 except Exception as ex:
  errors.append({'code':code,'error':str(ex)});target.write_text(json.dumps({'ok':False,'code':code,'url':url,'error':str(ex)}))
 gc.collect()
 if n%20==0:print('Price files',n,'/',len(groups),'failures',len(errors),flush=True)
(OUT/'price_fetch.json').write_text(json.dumps({'stocks':len(groups),'errors':errors},indent=2))
print('Finished price cross-check fetch',len(groups),'failures',len(errors),flush=True)
