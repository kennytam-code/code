from pathlib import Path
import urllib.request, zipfile, csv, io, json, statistics
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT=Path(__file__).resolve().parent
(ROOT/'liquidity_sources').mkdir(exist_ok=True)
DAYS=['2026_09_29','2026_09_30','2026_10_01','2026_10_02','2026_10_05']
PRODUCTS=['CDF','QFF','CCF','SOF','TE','TX','MTX']

def audit(day):
 url=f'https://www.taifex.com.tw/file/taifex/Dailydownload/DailydownloadCSV_eng/Daily_{day}.zip'
 p=ROOT/'liquidity_sources'/f'tw_ticks_{day.replace("_","")}.zip'
 try:
  if not p.exists():
   p.write_bytes(urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=25).read())
  rows=[]
  with zipfile.ZipFile(p) as z:
   with z.open(z.namelist()[0]) as f:
    for r in csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig')):
     prod=r['Product Code'].strip()
     if prod not in PRODUCTS:continue
     rows.append((prod,r['Contract Month(Week)'].strip(),r['Date'].strip(),r['Time of Trades'].strip().zfill(6),float(r['Volume(Buy+Sell)'])))
  dates=sorted({x[2] for x in rows})
  session_date=dates[0]
  d0=datetime.strptime(session_date,'%Y%m%d')
  start=d0+timedelta(hours=21,minutes=30);end=d0+timedelta(days=1,hours=4)
  night_start=d0+timedelta(hours=17,minutes=25);night_end=d0+timedelta(days=1,hours=5)
  results={prod:{'night_outright':0,'night_calendar_legs':0,'us_outright':0,'late_0300_0500':0,'bins':[0]*78} for prod in PRODUCTS}
  for prod,month,date,time,qty in rows:
   if '202610' not in month:continue
   ts=datetime.strptime(date+time,'%Y%m%d%H%M%S')
   r=results[prod]
   if month=='202610':
    v=qty/2
    if night_start<=ts<night_end:r['night_outright']+=v
    if start<=ts<end:
     r['us_outright']+=v;r['bins'][int((ts-start).total_seconds()//300)]+=v
    if d0+timedelta(days=1,hours=3)<=ts<night_end:r['late_0300_0500']+=v
   elif '/' in month and night_start<=ts<night_end:
    # The CSV counts both sides of both spread legs; one selected leg is qty/4.
    r['night_calendar_legs']+=qty/4
  for r in results.values():
   r['median_5m']=statistics.median(r['bins']);r['zero_5m_pct']=100*r['bins'].count(0)/78
  return {'report_date':day.replace('_','-'),'us_session_date':d0.strftime('%Y-%m-%d'),'source':url,'results':results}
 except Exception as e:return {'report_date':day,'error':str(e),'source':url}

daily=[]
with ThreadPoolExecutor(max_workers=4) as pool:
 for job in as_completed([pool.submit(audit,d) for d in DAYS]):
  r=job.result();daily.append(r)
  print(json.dumps({k:v for k,v in r.items() if k!='results'}),flush=True)
daily.sort(key=lambda r:r['report_date'])
summary={}
for prod in PRODUCTS:
 rs=[d['results'][prod] for d in daily if 'results' in d]
 if not rs:continue
 bins=[v for r in rs for v in r['bins']]
 summary[prod]={'sessions':len(rs),'avg_us_outright':statistics.mean(r['us_outright'] for r in rs),
  'median_daily_us_outright':statistics.median(r['us_outright'] for r in rs),
  'median_5m':statistics.median(bins),'zero_5m_pct':100*bins.count(0)/len(bins),
  'avg_night_with_calendar_legs':statistics.mean(r['night_outright']+r['night_calendar_legs'] for r in rs)}
 print(prod,summary[prod],flush=True)
output={'method':'Five US sessions. 21:30 to 04:00 HK. October 2026 contracts only. Outright US window volume = Buy+Sell/2. Spread prints are excluded from US-window measures; each calendar-spread leg = Buy+Sell/4 for reconciliation. Block activity may be absent. Five-minute buckets include zero-trade intervals. No quote depth inferred.','daily':daily,'summary':summary}
(ROOT/'liquidity_tw_5sessions.json').write_text(json.dumps(output,indent=2))
