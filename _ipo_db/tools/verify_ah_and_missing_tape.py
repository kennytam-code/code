import json,sys,re,hashlib
from datetime import date,timedelta,datetime,timezone
from pathlib import Path
import requests
R=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(R/'ipo_lib'));P=R/'data/demand_review_20261109'
from fetch_ah_paths import tx_kline,a_symbol,yahoo_fx
D={d['code']:d for d in json.loads((R/'data/deals.json').read_text())['deals']};audit=json.loads((P/'ah_ipo_cap_audit.json').read_text());out=[]
start=int(datetime(2026,7,28,tzinfo=timezone.utc).timestamp());end=int(datetime(2026,10,16,tzinfo=timezone.utc).timestamp())
url=f'https://query1.finance.yahoo.com/v8/finance/chart/CNYHKD=X?period1={start}&period2={end}&interval=1d'
response=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=30);response.raise_for_status();raw=response.json()['chart']['result'][0]
fx={datetime.fromtimestamp(t,timezone.utc).strftime('%Y-%m-%d'):v for t,v in zip(raw['timestamp'],raw['indicators']['quote'][0]['close']) if v}
(P/'ah_offer_fx_response.json').write_text(json.dumps({'url':url,'response':response.json()},indent=1)+'\n');print('FX fetched',len(fx),flush=True)
for r in audit['held']:
 c=r['code']
 if 'recomputed_premium_pct' not in r:continue
 d=D[c];dt=r['a_date'];a=tx_kline(a_symbol(d['a_share_code']),dt,dt);found=[p for p in a if p[0]==dt];f=fx.get(r['fx_date']);rec=dict(code=c,a_date=dt,a_rows=found,fx_date=r['fx_date'],cnyhkd=f,a_source='https://web.ifzq.gtimg.cn/appstock/app/fqkline/get',fx_source='https://query1.finance.yahoo.com/v8/finance/chart/CNYHKD=X')
 if found and f:rec['premium_pct']=(found[0][1]*f/d['final_price']-1)*100
 out.append(rec);print(c,rec.get('premium_pct'),flush=True)
(P/'ah_offer_fresh_quotes.json').write_text(json.dumps(out,indent=2)+'\n')
missing=[d for d in D.values() if any(d.get(k) is None for k in ['day1_volume','day1_range_pct'])];out=[]
for d in missing:
 c=d['code'];dt=d['ipo_date'];symbol='hk'+c.zfill(5);url=f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,{dt},{dt},5,'
 try:
  response=requests.get(url,timeout=20);response.raise_for_status();bars=response.json()['data'][symbol].get('day',[]);bar=next(b for b in bars if b[0]==dt);r={'code':c,'date':dt,'raw_bar':bar,'url':url,'sha256':hashlib.sha256(response.content).hexdigest()};out.append(r);print('Tape',c,bar[:6],flush=True)
 except Exception as e:out.append({'code':c,'error':str(e)});print('Tape',c,str(e),flush=True)
(P/'day1_tape_recovery.json').write_text(json.dumps(out,indent=2)+'\n')
