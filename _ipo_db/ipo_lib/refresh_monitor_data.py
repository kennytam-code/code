"""Refresh saved peer histories, then rederive all monitor/reference datasets."""
import json,runpy,time
from pathlib import Path
from datetime import datetime,timezone,date
import requests
from market_universe import histories
ROOT=Path(__file__).resolve().parent.parent
def refresh_peers(root,cutoff,get=requests.get):
 path=root/'data/peer_pairs.json';data=json.loads(path.read_text());errors=[]
 if data.get('asof','')>=cutoff and not data.get('refresh_errors'):return errors
 cache=root/'data/peer_price_cache';cache.mkdir(exist_ok=True)
 for code in sorted({p[k] for p in data['pairs'] for k in ['code_a','code_b']}):
  try:
   # Refetch the complete supported window so a new split also restates older closes.
   end=date.fromisoformat(cutoff);start=end.replace(year=end.year-5) if end.month!=2 or end.day!=29 else end.replace(year=end.year-5,day=28)
   p1=int(datetime.combine(start,datetime.min.time(),timezone.utc).timestamp());p2=int(datetime.combine(end,datetime.min.time(),timezone.utc).timestamp())+86400
   url=f'https://query1.finance.yahoo.com/v8/finance/chart/{int(code):04d}.HK?period1={p1}&period2={p2}&interval=1d'
   response=get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=25);response.raise_for_status();obj=response.json()['chart']['result'][0];q=obj['indicators']['quote'][0];rows=[]
   for i,ts in enumerate(obj.get('timestamp',[])):
    dt=datetime.fromtimestamp(ts,timezone.utc).date().isoformat()
    if dt<=cutoff and q['close'][i] is not None and q['volume'][i]:rows.append([dt,q['open'][i],q['close'][i],q['high'][i],q['low'][i],q['volume'][i]])
   if not rows:raise ValueError('No observed prices')
   (cache/(code+'.json')).write_text(json.dumps({'src':url,'rows':rows,'basis':'Split-adjusted close; cash dividends excluded'},separators=(',',':')))
  except Exception as exc:errors.append({'code':code,'error':str(exc)})
  time.sleep(.1)
 data['asof']=cutoff;data['refresh_errors']=errors;path.write_text(json.dumps(data,ensure_ascii=False,indent=1));return errors
def refresh_legacy(root,cutoff,get=requests.get):
 """Refresh the six saved legacy A/H pairs sequentially, preserving failures."""
 path=root/'data/batches/ah_market_supplement.json';data=json.loads(path.read_text())
 if data.get('asof','')>=cutoff and not data.get('errors'):return []
 from market_universe import load
 from analyse_ah_study import make_pair
 from fetch_ah_paths import a_symbol
 from corp_actions import load_actions
 roster={d['code']:d for d in load(root)};cache=root/'data/ah_study_cache';fx=json.loads((cache/'cnyhkd.json').read_text());errors=[];rebuilt=[]
 for old in data['pairs']:
  code=old['code'];d=roster[code]
  try:
   legs=[]
   for kind,symbol in [('h',f'hk{int(code):05d}'),('a',a_symbol(d['a_share_code']))]:
    cp=cache/f'{kind}_{code}.json';saved=json.loads(cp.read_text());lo=saved[-1][0] if saved else d['ipo_date'];url=f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,{lo},{cutoff},1500,'
    response=get(url,timeout=25);response.raise_for_status();rows=response.json().get('data',{}).get(symbol,{}).get('day',[])
    if not rows:raise ValueError('No provider history for '+symbol)
    merged={r[0]:r for r in saved}
    for r in rows:
     if lo<=r[0]<=cutoff and len(r)>5 and float(r[5])>0 and float(r[2])>0:merged[r[0]]=[r[0],float(r[2]),float(r[1])]
    saved=[merged[k] for k in sorted(merged)];cp.write_text(json.dumps(saved));legs.append([r[:2] for r in saved])
    time.sleep(.1)
   rebuilt.append(make_pair(d,*legs,fx,cutoff,load_actions(root)))
  except Exception as exc:errors.append({'code':code,'error':str(exc)});rebuilt.append(old)
 data.update(asof=cutoff,errors=errors,pairs=rebuilt);path.write_text(json.dumps(data,ensure_ascii=False,indent=1));return errors

def main():
 cutoff=histories(ROOT)['asof'];errors=refresh_legacy(ROOT,cutoff)+refresh_peers(ROOT,cutoff)
 runpy.run_module('prepare_monitor_data',run_name='__main__')
 from prepare_ah_reference import main as reference
 reference()
 print('Monitor datasets rebuilt; peer fetch failures',len(errors))
 if errors:raise RuntimeError('Some peer histories could not be refreshed; retained and individually dated')
if __name__=='__main__':main()
