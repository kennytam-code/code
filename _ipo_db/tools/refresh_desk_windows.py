"""Exact 30 HK-session lock-up windows; no observations invented for suspensions."""
import json,sys,requests
from pathlib import Path
from datetime import date,timedelta,datetime,timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from review_lockups import window
from corp_actions import load_actions
p=ROOT/'data/batches/lockup_events.json';doc=json.loads(p.read_text());bench=json.loads((ROOT/'data/batches/benchmark_prices.json').read_text())['benchmarks'];cutoff=doc['price_asof'];sessions=sorted({r[0] for b in bench.values() for r in b.get('closes',[]) if r[0]<=cutoff});actions=load_actions(ROOT)
cache=ROOT/'data/lockup_price_cache';cache.mkdir(exist_ok=True)
def run(code,evs):
 lo=(date.fromisoformat(min(e['last_day_locked'] for e in evs))-timedelta(days=95)).isoformat();hi=min(cutoff,(date.fromisoformat(max(e['last_day_locked'] for e in evs))+timedelta(days=95)).isoformat());path=cache/(code+'.json');symbol=f'hk{int(code):05d}';url=f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,{lo},{hi},1500,'
 if path.exists():raw=json.loads(path.read_text())
 else:
  start=int(datetime.fromisoformat(lo).replace(tzinfo=timezone.utc).timestamp());stop=int(datetime.fromisoformat(hi).replace(tzinfo=timezone.utc).timestamp())+86400
  url=f'https://query1.finance.yahoo.com/v8/finance/chart/{int(code):04d}.HK?period1={start}&period2={stop}&interval=1d'
  response=requests.get(url,timeout=30,headers={'User-Agent':'Mozilla/5.0'});response.raise_for_status();obj=response.json()['chart']['result'][0];quote=obj['indicators']['quote'][0];rows=[]
  for i,ts in enumerate(obj.get('timestamp',[])):
   if quote['close'][i] is not None and quote['volume'][i]:rows.append([datetime.fromtimestamp(ts,timezone.utc).date().isoformat(),quote['open'][i],quote['close'][i],quote['high'][i],quote['low'][i],quote['volume'][i]])
  raw={'src':url,'rows':rows,'basis':'Yahoo closing price in split-adjusted share units; no dividend adjustment'};path.write_text(json.dumps(raw,separators=(',',':')))
 prices={r[0]:float(r[2]) for r in raw['rows'] if len(r)>5 and float(r[5])>0}
 for e in evs:
  e.setdefault('windows',{})['30 trading sessions']=window(e['last_day_locked'],sessions,prices,([] if 'basis' in raw else actions.get(code,[])),cutoff,days=30);e['price_url_30']=raw['src'];e['windows']['30 trading sessions']['price_basis']=raw.get('basis','Split-neutral raw closes')
 return code
by={}
for e in doc['events']:
 if e['category']=='Cornerstone' and e.get('last_day_locked') and e['last_day_locked']<=cutoff:by.setdefault(e['code'],[]).append(e)
errors=[]
with ThreadPoolExecutor(max_workers=5) as pool:
 jobs={pool.submit(run,c,es):c for c,es in by.items()}
 for i,t in enumerate(as_completed(jobs),1):
  try:t.result()
  except Exception as ex:errors.append({'code':jobs[t],'error':str(ex)})
  if i%30==0:print('30-session windows',i,'/',len(jobs),'errors',len(errors),flush=True)
for e in doc['events']:
 if e['category']=='Cornerstone' and e.get('last_day_locked') and e['last_day_locked']>cutoff:e.setdefault('windows',{})['30 trading sessions']=window(e['last_day_locked'],sessions,{},[],cutoff,days=30)
doc.update(display_window=30,refresh_errors_30=errors);p.write_text(json.dumps(doc,ensure_ascii=True,indent=1))
print('Done',len(by),'errors',len(errors),flush=True)
