import json,requests
from pathlib import Path
from datetime import date,timedelta
from concurrent.futures import ThreadPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parent.parent
D={d['code']:d for d in json.loads((ROOT/'data/deals.json').read_text())['deals']};cutoff='2026-10-02'
choices=[('9856','3308','Optical transceivers','Datacom product mix and customer concentration'),('2525','2498','LiDAR','ADAS versus robotics mix and unit pricing'),('9660','2533','ADAS chips','Design wins, chip shipments and software attach'),('2097','1364','Tea franchises','Store growth, unit economics and price positioning'),('9863','2015','New energy vehicles','Deliveries, product cycle and gross margin'),('3750','3931','EV batteries','Battery mix, capacity use and margin')]
choices += [('0981','1347','Wafer foundries','Process mix and utilization'),('0700','9988','Internet platforms','Gaming versus commerce and cloud'),('9618','9988','Online retail','Retail margins, services and capital return'),('3690','1024','Consumer internet','Local services versus video advertising'),('1810','2018','Smartphone ecosystem','Handsets versus components'),('2382','1478','Optical components','Camera modules and handset demand'),('0285','2018','Electronics manufacturing','Assembly versus components'),('9868','2015','New energy vehicles','Deliveries and vehicle margin'),('1211','0175','Auto manufacturers','Export mix and product cycle'),('0175','2333','Auto manufacturers','Passenger cars versus SUVs'),('2331','2020','Sportswear','Brand mix and inventory'),('1368','2020','Sportswear','Price positioning and retail growth'),('1044','3331','Hygiene products','Product mix and pulp input prices'),('2319','1117','Dairy','Branded dairy versus raw milk; value-chain comparator'),('0291','0168','Brewers','Premiumization and channel demand'),('0005','2888','International banks','Funding mix, credit and capital returns'),('0939','1398','China banks','Net interest margin and asset quality'),('3988','1288','China banks','Loan and funding mix'),('2318','2628','Life insurers','New business, assets and capital'),('2601','1339','Insurers','Life versus property/casualty mix'),('0016','0012','HK developers','Property sales and rental income'),('1109','0688','China developers','Sales, margins and balance sheet'),('0823','0435','REITs','Retail versus office assets'),('0017','0004','Property companies','Residential versus investment property'),('0941','0728','Telecom operators','Cloud, mobile subscribers and capital expenditure'),('0762','0728','Telecom operators','Mobile versus fixed-line mix'),('0883','0857','Oil producers','Upstream versus integrated exposure'),('1088','1171','Coal miners','Coal prices and cost'),('2899','3993','Metals miners','Copper/gold versus molybdenum mix'),('0902','0836','Power generators','Thermal versus renewables mix'),('0002','0006','HK utilities','Regulated utility exposure'),('0914','2233','Cement','Regional demand and pricing'),('3323','1313','Cement','Cement demand and capacity'),('1177','1093','Pharmaceuticals','Drug mix and pipeline'),('2269','2359','CXO services','Biologics versus small-molecule exposure'),('3692','1801','Biopharma','Commercial products and R&D'),('1919','0316','Container shipping','Freight rates and capacity'),('0753','0670','Airlines','Route mix and passenger yield'),('1928','0027','Macau casinos','Gaming mix and market share'),('0069','0053','Hotels','Property mix and travel demand')]
# Cross-industry and value-chain comparisons are labelled explicitly.
U={r['code']:r for r in json.loads((ROOT/'data/hk_stock_universe.json').read_text())['stocks']}
rec=[]
for a,b,segment,catalyst in choices:
 a=f'{int(a):04d}';b=f'{int(b):04d}'
 if a not in U or b not in U:print('Unavailable catalog pair',a,b);continue
 rec.append({'id':a+'/'+b,'code_a':a,'code_b':b,'name_a':U[a]['name'],'name_b':U[b]['name'],'segment':segment,'watch':catalyst,'sources':[json.loads((ROOT/'data/hk_stock_universe.json').read_text())['source']]})
cache=ROOT/'data/peer_price_cache';cache.mkdir(exist_ok=True)
codes={p[c] for p in rec for c in ['code_a','code_b']}
def run(c):
 p=cache/(c+'.json');lo='2021-10-01'
 if p.exists():
  try:old=json.loads(p.read_text())
  except (ValueError,OSError):old={}
  if old.get('rows') and old['rows'][0][0]<=lo or c in D and old.get('rows') and old['rows'][0][0]<=D[c]['ipo_date']:return c
 from datetime import datetime,timezone
 start=int(datetime.fromisoformat(lo).replace(tzinfo=timezone.utc).timestamp());stop=int(datetime.fromisoformat(cutoff).replace(tzinfo=timezone.utc).timestamp())+86400
 u=f'https://query1.finance.yahoo.com/v8/finance/chart/{int(c):04d}.HK?period1={start}&period2={stop}&interval=1d'
 q=requests.get(u,headers={'User-Agent':'Mozilla/5.0'},timeout=30);q.raise_for_status();z=q.json()['chart']['result'][0];o=z['indicators']['quote'][0];raw=[]
 for i,ts in enumerate(z['timestamp']):
  if o['close'][i] is not None and o['volume'][i]:raw.append([datetime.fromtimestamp(ts,timezone.utc).date().isoformat(),o['open'][i],o['close'][i],o['high'][i],o['low'][i],o['volume'][i]])
 if not raw:raise ValueError(c+' empty history')
 p.write_text(json.dumps({'src':u,'rows':raw},separators=(',',':')));return c
with ThreadPoolExecutor(max_workers=1) as pool:
 for f in as_completed([pool.submit(run,c) for c in codes]):print('Peer history',f.result(),flush=True)
(ROOT/'data/peer_pairs.json').write_text(json.dumps({'asof':cutoff,'pairs':rec},ensure_ascii=False,indent=1))
