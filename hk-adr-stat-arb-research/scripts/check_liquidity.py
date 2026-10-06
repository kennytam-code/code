from pathlib import Path
import csv, json, urllib.request, urllib.parse, statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from lxml import html

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / 'liquidity_sources'
CACHE.mkdir(exist_ok=True)
SYMBOLS = {
 'HK core': {'BABA':'nyse','JD':'nasdaq','BIDU':'nasdaq','NTES':'nasdaq','TCOM':'nasdaq','BILI':'nasdaq','TME':'nyse','LI':'nasdaq','XPEV':'nyse','NIO':'nyse'},
 'HK broader': {'GDS':'nasdaq','KC':'nasdaq','BZ':'nasdaq','BEKE':'nyse','EDU':'nyse','ZTO':'nyse','YUMC':'nyse','MNSO':'nyse','WB':'nasdaq','QFIN':'nasdaq','TUYA':'nyse','ZH':'nyse','ATHM':'nyse','HTHT':'nasdaq','ZLAB':'nasdaq','HSAI':'nasdaq','PONY':'nasdaq','WRD':'nasdaq','HSBC':'nyse'},
 'Taiwan': {'TSM':'nyse','UMC':'nyse','ASX':'nyse','CHT':'nyse'},
 'Japan': {'TM':'nyse','HMC':'nyse','SONY':'nyse','MUFG':'nyse','SMFG':'nyse','MFG':'nyse'},
 'Korea': {'SKHY':'nasdaq','KB':'nyse','SHG':'nyse','WF':'nyse','PKX':'nyse','KT':'nyse','SKM':'nyse','LPL':'nyse','KEP':'nyse'},
 'Australia': {'BHP':'nyse','RIO':'nyse','WDS':'nyse'},
 'US hedge ETFs': {'KWEB':'nyse','EWJ':'nyse','EWY':'nyse','EWT':'nyse','EWA':'nyse','SMH':'nasdaq','SOXX':'nasdaq'},
}

def fetch(item):
 group, ticker, exchange = item
 url=f'https://chartexchange.com/symbol/{exchange}-{ticker.lower()}/historical/'
 try:
  req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
  raw=urllib.request.urlopen(req, timeout=20).read()
  (CACHE/f'{ticker}.html').write_bytes(raw)
  tree=html.fromstring(raw)
  records=[]
  for tr in tree.xpath('//table//tr'):
   cells=[' '.join(c.text_content().split()) for c in tr.xpath('./td')]
   if len(cells)<7 or len(cells[0])!=10 or not cells[0].startswith('20'): continue
   if cells[0]>'2026-10-02': continue
   try:
    date,close,volume=cells[0],float(cells[4].replace(',','')),int(cells[6].replace(',',''))
   except ValueError: continue
   records.append({'date':date,'close':close,'volume':volume,'dollar_volume_proxy':close*volume})
  records=sorted(records,key=lambda x:x['date'],reverse=True)[:20]
  if not records: raise ValueError('No dated price-volume rows')
  return {'group':group,'ticker':ticker,'source':url,'n':len(records),'from':records[-1]['date'],'to':records[0]['date'],
   'avg_shares':statistics.mean(x['volume'] for x in records),
   'avg_usd_proxy':statistics.mean(x['dollar_volume_proxy'] for x in records),
   'median_usd_proxy':statistics.median(x['dollar_volume_proxy'] for x in records),
   'min_usd_proxy':min(x['dollar_volume_proxy'] for x in records),'records':records}
 except Exception as e: return {'group':group,'ticker':ticker,'source':url,'error':str(e)}

items=[(group,ticker,exchange) for group,stocks in SYMBOLS.items() for ticker,exchange in stocks.items()]
results=[]
with ThreadPoolExecutor(max_workers=6) as pool:
 jobs={pool.submit(fetch,x):x for x in items}
 for job in as_completed(jobs):
  result=job.result(); results.append(result)
  print(json.dumps({k:v for k,v in result.items() if k!='records'}),flush=True)
results.sort(key=lambda x:(x['group'],x['ticker']))
(ROOT/'liquidity_US_20d.json').write_text(json.dumps(results,indent=2))
with (ROOT/'liquidity_US_20d.csv').open('w',newline='') as f:
 cols=['group','ticker','n','from','to','avg_shares','avg_usd_proxy','median_usd_proxy','min_usd_proxy','source','error']
 w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
 for r in results: w.writerow({k:v for k,v in r.items() if k in cols})
