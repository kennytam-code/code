"""Keep accepted historical snapshots from overriding a later quote refresh."""
from datetime import date,timedelta
MUTABLE={'last_close','last_date','price_asof','since_ipo_pct','bench_since_pct','alpha_since_pct','a_close_cny','a_close_date','a_close_hkd','a_premium_now','a_mktcap_now_hkdm','cnyhkd'}
def quote_dates(batches):
 dates={}
 def add(code,dt):
  if code and dt:
   code=str(code).zfill(4);dt=str(dt)[:10]
   try:date.fromisoformat(dt)
   except ValueError:return
   dates[code]=max(dates.get(code,''),dt)
 for r in (batches.get('prices') or {}).get('deals',[]):add(r.get('code'),r.get('last_date'))
 for r in (batches.get('ah_study') or {}).get('pairs',[]):add(r.get('code'),r.get('latest_date') or r.get('latest_h_date'))
 snapshot=batches.get('ah_snapshot') or {};stamp=str(snapshot.get('as_of') or '')[:10]
 if stamp:
  dt=date.fromisoformat(stamp)
  while dt.weekday()>4:dt-=timedelta(days=1)
  for r in snapshot.get('pairs',[]):add(r.get('code'),r.get('quote_date') or dt.isoformat())
 for r in (batches.get('h_paths') or {}).get('deals',[]):
  closes=r.get('closes') or []
  if closes and r.get('ipo'):
   add(r.get('code'),(date.fromisoformat(r['ipo'][:10])+timedelta(days=max(p[0] for p in closes))).isoformat())
 return dates

def allowed(field,snapshot,latest_date):
 return field not in MUTABLE or not snapshot or not latest_date or latest_date<=snapshot
