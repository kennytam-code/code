"""Refresh incomplete filed event windows; completed exact windows are stable.
Prices use raw daily bars and the common action loader. Missing closes stay gaps.
"""
import json,time
from datetime import date,timedelta
from pathlib import Path
import requests
from review_lockups import window
from corp_actions import load_actions
ROOT=Path(__file__).resolve().parent.parent
def main():
 path=ROOT/'data/batches/lockup_events.json';data=json.loads(path.read_text());doc=json.loads((ROOT/'data/deals.json').read_text());D={d['code']:d for d in doc['deals']}
 benchmarks=json.loads((ROOT/'data/batches/benchmark_prices.json').read_text())['benchmarks']
 sessions=sorted({r[0] for b in benchmarks.values() for r in b.get('closes',[]) if r[0]<=doc['as_of']})
 if not sessions:raise SystemExit('No completed HK benchmark sessions; event returns retained.')
 cutoff=sessions[-1];actions=load_actions(ROOT);by={};errors=[]
 for e in data['events']:
  dt=e.get('last_day_locked')
  if not dt or dt>cutoff:continue
  w=e.get('windows',{}).get('Trading sessions',{})
  c=e.get('windows',{}).get('Calendar days',{})
  if w.get('status')=='Complete' and c.get('status')=='Complete' and w.get('path'):continue
  by.setdefault(e['code'],[]).append(e)
 for code,events in by.items():
  start=(date.fromisoformat(min(e['last_day_locked'] for e in events))-timedelta(days=25)).isoformat();end=min(cutoff,(date.fromisoformat(max(e['last_day_locked'] for e in events))+timedelta(days=25)).isoformat());symbol=f'hk{int(code):05d}'
  url=f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,{start},{end},1500,'
  try:
   response=requests.get(url,timeout=30);response.raise_for_status();raw=response.json().get('data',{}).get(symbol,{}).get('day',[])
   if not raw:raise ValueError('No raw daily bars')
   prices={r[0]:float(r[2]) for r in raw if len(r)>5 and float(r[5])>0}
   for e in events:
    e['windows']={m:window(e['last_day_locked'],sessions,prices,actions.get(code,[]),cutoff,m) for m in ['Trading sessions','Calendar days']};e['price_url']=url;e['price_asof']=cutoff
  except Exception as ex:errors.append({'code':code,'error':str(ex)})
  time.sleep(.3)
 data['price_asof']=cutoff;data['refresh_errors']=errors;data['stock_count']=len(D);path.write_text(json.dumps(data,ensure_ascii=True,indent=1));print('Event-window stocks refreshed',len(by),'errors',len(errors),'completed session',cutoff)
if __name__=='__main__':main()
