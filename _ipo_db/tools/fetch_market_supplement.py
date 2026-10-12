import json,sys,requests
from pathlib import Path
from datetime import date,timedelta,datetime,timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from analyse_ah_study import make_pair
from fetch_ah_paths import a_symbol
S=json.loads((ROOT/'data/market_supplement.json').read_text())['deals'];pairs=[d for d in S if d.get('a_share_code')];cache=ROOT/'data/ah_study_cache';cutoff=json.loads((ROOT/'data/batches/ah_study.json').read_text())['asof']
# FX observations use the same Yahoo daily-close vendor as existing pairs.
fp=cache/'cnyhkd.json';fx=json.loads(fp.read_text());start=(date.fromisoformat(min(d['ipo_date'] for d in pairs))-timedelta(days=45)).isoformat()
if fx[0][0]>start:
 p1=int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp());p2=int(datetime.fromisoformat(fx[0][0]).replace(tzinfo=timezone.utc).timestamp())
 u=f'https://query1.finance.yahoo.com/v8/finance/chart/CNYHKD=X?period1={p1}&period2={p2}&interval=1d'
 response=requests.get(u,headers={'User-Agent':'Mozilla/5.0'},timeout=30);response.raise_for_status();obj=response.json()['chart']['result'][0];raw=[[datetime.fromtimestamp(t,timezone.utc).date().isoformat(),c] for t,c in zip(obj['timestamp'],obj['indicators']['quote'][0]['close']) if c and c>0]
 merged=dict(fx);merged.update(raw);fx=sorted(merged.items());fp.write_text(json.dumps(fx))

def history(symbol,start,code,kind):
 path=cache/f'{kind}_{code}.json'
 if path.exists():return json.loads(path.read_text())
 prices={};actions=[]
 for year in range(int(start[:4]),int(cutoff[:4])+1):
  lo=max(start,f'{year}-01-01');hi=min(cutoff,f'{year}-12-31')
  u=f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,{lo},{hi},1500,'
  response=requests.get(u,timeout=30);response.raise_for_status();rows=response.json().get('data',{}).get(symbol,{}).get('day',[])
  for r in rows:
   if start<=r[0]<=cutoff and len(r)>5 and float(r[5])>0 and float(r[2])>0:
    prices[r[0]]=float(r[2])
    if len(r)>6 and isinstance(r[6],dict):actions.append(r)
 path.write_text(json.dumps(sorted(prices.items())));(cache/f'{kind}_{code}_events.json').write_text(json.dumps(actions,ensure_ascii=False))
 return sorted(prices.items())
def run(d):
 c=d['code'];hs=history(f'hk{int(c):05d}',d['ipo_date'],c,'h');ars=history(a_symbol(d['a_share_code']),start,c,'a');return make_pair(d,hs,ars,fx,cutoff,{})
records=[];errors=[]
with ThreadPoolExecutor(max_workers=4) as pool:
 futures={pool.submit(run,d):d for d in pairs}
 for f in as_completed(futures):
  try:r=f.result();records.append(r);print(r['code'],len(r['h_history']),len(r['history']),r.get('latest_premium_pct'),flush=True)
  except Exception as ex:errors.append({'code':futures[f]['code'],'error':str(ex)});print(errors[-1],flush=True)
(ROOT/'data/batches/ah_market_supplement.json').write_text(json.dumps({'asof':cutoff,'errors':errors,'pairs':records},ensure_ascii=False,separators=(',',':')))
if errors:raise SystemExit('Supplemental history missing; review required')
