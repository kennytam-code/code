"""Source checks retained outside the workbook; no live Bloomberg claim."""
import json,math,sys,urllib.request,ssl,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'ipo_lib'))
from refresh_ah_history import fetch,asof,write
review=ROOT/'data/ah_review_20261115';review.mkdir(exist_ok=True)
samples=[
 dict(code='3223',name='Ingenic',a_code='300223.SZ',asof='2026-10-31',a_ex_treasury=482646067,a_treasury=1018300,h_ex_treasury=31287300,h_treasury=0,
 url='https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1102/2026110201372.pdf',page=2),
 dict(code='6809',name='Montage',a_code='688008.SS',asof='2026-10-31',a_ex_treasury=1132043159,a_treasury=12721362,h_ex_treasury=75773500,h_treasury=0,
 url='https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1102/2026110203403.pdf',page=2)
]
for row in samples:
 for kind,ccy in [('a','CNY'),('h','HKD')]:
  prices=json.loads((ROOT/f'data/ah_study_cache/{kind}_{row["code"]}.json').read_text());p=asof(prices,row['asof'])
  row[kind+'_close']=p[1];row[kind+'_price_date']=p[0]
  row[kind+'_class_cap_ex_treasury_m']=p[1]*row[kind+'_ex_treasury']/1e6
  row[kind+'_currency']=ccy
write(review/'market_cap_sources.json',dict(review_date='2026-11-15',samples=samples,
 interpretation='Filed share-class issued shares excluding treasury multiplied by the dated class close, divided by 1,000,000. These are month-end reference calculations, not observed Bloomberg responses or current cap replacements.',
 formula_decision='Retain CURRENT_MARKET_CAP_SHARE_CLASS; clarify headers to A-class/H-class cap. No unverified field or scaling override added.',
 terminal_tested=False,
 documentation=[
  dict(url='https://data.bloomberglp.com/professional/sites/10/Bloomberg-US-Equity-Index-Methodology1.pdf',basis='Bloomberg distinguishes company market capitalization; do not substitute company-wide CUR_MKT_CAP for class caps.'),
  dict(url='https://help.macrobond.com/apis-feeds-connectors/the-macrobond-bloomberg-connector/',basis='Official connector documentation shows MLN scaling and warns units require field-description verification. Does not independently establish RR233 override support.')]))
# Independent provider check of current raw closes: Yahoo vs retained Tencent.
from market_universe import load
roster={r['code']:r for r in load(ROOT)}
checks=[]
for code in sorted(r['code'] for r in roster.values() if r.get('a_share_code')):
 for kind in ['a','h']:
  symbol=roster[code]['a_share_code'] if kind=='a' else f'{int(code):04d}.HK'
  epoch=lambda d:int(datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp())
  url=f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={epoch("2026-10-01")}&period2={epoch("2026-11-14")}&interval=1d&events=splits'
  result=dict(code=code,leg=kind,url=url)
  try:
   cached=review/f'yahoo_{kind}_{code}.json'
   obj=json.loads(cached.read_text()) if cached.exists() else fetch(url);write(cached,obj)
   r=obj['chart']['result'][0];q=r['indicators']['quote'][0];rows=[[datetime.fromtimestamp(t,timezone.utc).date().isoformat(),q['close'][i]] for i,t in enumerate(r['timestamp']) if q['close'][i] is not None and q['volume'][i]]
   p=rows[-1];saved=asof(json.loads((ROOT/f'data/ah_study_cache/{kind}_{code}.json').read_text()),p[0])
   result.update(date=p[0],yahoo_close=p[1],tencent_close=saved[1],match=p[0]==saved[0] and math.isclose(p[1],saved[1],rel_tol=.0001,abs_tol=.001),split_events=r.get('events',{}).get('splits',{}))
  except Exception as exc:result['error']=str(exc)
  checks.append(result);print(code,kind,result.get('match',result.get('error')),flush=True);time.sleep(.1)
write(review/'price_crosscheck.json',dict(checks=checks,terminal_tested=False))
