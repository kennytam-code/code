import json,requests
from pathlib import Path
from datetime import date,timedelta
from concurrent.futures import ThreadPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parent.parent
D={d['code']:d for d in json.loads((ROOT/'data/deals.json').read_text())['deals']};cutoff='2026-10-02'
choices=[('9856','3308','Optical transceivers','Datacom product mix and customer concentration'),('2525','2498','LiDAR','ADAS versus robotics mix and unit pricing'),('9660','2533','ADAS chips','Design wins, chip shipments and software attach'),('2097','1364','Tea franchises','Store growth, unit economics and price positioning'),('9863','2015','New energy vehicles','Deliveries, product cycle and gross margin'),('3750','3931','EV batteries','Battery mix, capacity use and margin')]
rec=[]
for a,b,segment,catalyst in choices:
 rec.append({'id':a+'/'+b,'code_a':a,'code_b':b,'name_a':D[a]['name'],'name_b':D[b]['name'],'segment':segment,'watch':catalyst,'sources':[D[a]['prospectus_link'],D[b]['prospectus_link']]})
cache=ROOT/'data/peer_price_cache';cache.mkdir(exist_ok=True)
codes={c for a,b,*_ in choices for c in [a,b]}
def run(c):
 p=cache/(c+'.json');lo=max(D[c]['ipo_date'],(date.fromisoformat(cutoff)-timedelta(days=730)).isoformat());u=f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=hk{int(c):05d},day,{lo},{cutoff},1500,'
 if not p.exists():

  import time
  for attempt in range(3):
   r=requests.get(u,timeout=30)
   if r.ok:break
   time.sleep(1)

  if r.ok:raw=r.json().get('data',{}).get(f'hk{int(c):05d}',{}).get('day',[])
  else:
   from datetime import datetime,timezone
   start=int(datetime.fromisoformat(lo).replace(tzinfo=timezone.utc).timestamp());stop=int(datetime.fromisoformat(cutoff).replace(tzinfo=timezone.utc).timestamp())+86400
   u=f'https://query1.finance.yahoo.com/v8/finance/chart/{int(c):04d}.HK?period1={start}&period2={stop}&interval=1d'
   q=requests.get(u,headers={'User-Agent':'Mozilla/5.0'},timeout=30);q.raise_for_status();z=q.json()['chart']['result'][0];o=z['indicators']['quote'][0];raw=[]
   for i,ts in enumerate(z['timestamp']):
    if o['close'][i] is not None and o['volume'][i]:raw.append([datetime.fromtimestamp(ts,timezone.utc).date().isoformat(),o['open'][i],o['close'][i],o['high'][i],o['low'][i],o['volume'][i]])
  p.write_text(json.dumps({'src':u,'rows':raw},separators=(',',':')))
 return c
with ThreadPoolExecutor(max_workers=4) as pool:
 for f in as_completed([pool.submit(run,c) for c in codes]):print('Peer history',f.result(),flush=True)
(ROOT/'data/peer_pairs.json').write_text(json.dumps({'asof':cutoff,'pairs':rec},ensure_ascii=False,indent=1))
