import json,sys,calendar
from pathlib import Path
from datetime import date,timedelta
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from corp_actions import load_actions,price_factor
from market_universe import load,histories
from ah_basis import review_for,comparable
D={d['code']:d for d in load(ROOT)};sectors=list(json.loads((ROOT/'data/taxonomy.json').read_text())['sectors']);listed=sorted(D.values(),key=lambda d:(sectors.index(d['sector']),d['name']));pairs=[d for d in listed if d.get('a_share_code')];records={r['code']:r for r in histories(ROOT)['pairs']};cr=2;meta=[]
for d in pairs:
 r=records[d['code']];hs=[h for h in r.get('h_history',[]) if h[0]>=d['ipo_date']];review=review_for(d['code'],ROOT);valid=[h for h in r.get('history',[]) if comparable(review,h[0],h[5])];last=hs[-1][0] if hs else None
 def reference(month=False):
  if not last:return None
  dt=date.fromisoformat(last)
  if month:
   mon=dt.month-1;y=dt.year-(mon==0);mon=mon or 12;target=date(y,mon,min(dt.day,calendar.monthrange(y,mon)[1])).isoformat()
  else:target=(dt-timedelta(days=7)).isoformat()
  v=[h for h in valid if h[0]<=target]
  return v[-1][4] if v and (date.fromisoformat(target)-date.fromisoformat(v[-1][0])).days<=10 else None
 meta.append(dict(code=d['code'],name=d['name'],a_ticker=d['a_share_code'].split('.')[0]+' CH Equity',h_ticker=str(int(d['code']))+' HK Equity',ipo_date=d['ipo_date'],raw_debut=hs[0][1] if hs else None,cache_start=cr,cache_rows=len(hs),stored_7=reference(),stored_1m=reference(True),latest_date=last,review=review));cr+=len(hs)
pp=json.loads((ROOT/'data/peer_pairs.json').read_text());actions=load_actions(ROOT)
for p in pp['pairs']:
 prices=[]
 for c in [p['code_a'],p['code_b']]:
  x=json.loads((ROOT/'data/peer_price_cache'/f'{c}.json').read_text());rows={r[0]:float(r[2]) for r in x['rows'] if r[0]<=pp['asof'] and float(r[5])>0};adjusted='finance.yahoo.com' in x['src'];total=price_factor(c,actions,pp['asof'])
  prices.append({dt:close if adjusted else close*price_factor(c,actions,dt)/total for dt,close in rows.items()})
 dates=sorted(set(prices[0])&set(prices[1]));base=dates[0] if dates else None
 p['history']=[[dt,prices[0][dt],prices[1][dt],prices[0][dt]/prices[0][base]-1,prices[1][dt]/prices[1][base]-1,prices[0][dt]/prices[0][base]-prices[1][dt]/prices[1][base]] for dt in dates]
 p['start']=base;p['latest_date']=dates[-1] if dates else None
 p['ticker_a']=str(int(p['code_a']))+' HK Equity';p['ticker_b']=str(int(p['code_b']))+' HK Equity'
 p['daily_a']=prices[0][dates[-1]]/prices[0][dates[-2]]-1 if len(dates)>1 else None;p['daily_b']=prices[1][dates[-1]]/prices[1][dates[-2]]-1 if len(dates)>1 else None
pp['method']='Split-neutral closing-price performance; A minus B return in percentage points from the common first observed session. Excludes dividends and rights value.'
(ROOT/'data/peer_pairs.json').write_text(json.dumps(pp,ensure_ascii=False,indent=1));(ROOT/'data/desk_chart_data.json').write_text(json.dumps(dict(listed_count=len(listed),pairs=meta,ah_cache_end=cr-1,peer=pp),ensure_ascii=False,indent=1));print(len(listed),len(meta),len(pp['pairs']))
