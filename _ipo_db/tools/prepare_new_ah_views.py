"""Append repaired pairs without rewriting any existing market observation."""
import json,sys,calendar
from pathlib import Path
from datetime import date,timedelta
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from ah_basis import review_for,adjusted_premium,share_multiplier
def load(p):return json.loads((ROOT/p).read_text())
def save(p,d):(ROOT/p).write_text(json.dumps(d,ensure_ascii=False,indent=1)+'\n')
meta=load('data/desk_chart_data.json');reference=load('data/ah_reference.json');records={r['code']:r for r in load('data/batches/ah_study.json')['pairs']};deals={r['code']:r for r in load('data/deals.json')['deals']};benchmark=dict(load('data/csi300_prices.json')['closes']);cr=meta['ah_cache_end']+1
for code in ['3228','6727','3757']:
 if code in {r['code'] for r in meta['pairs']}:continue
 d=deals[code];rec=records[code];hs=rec['h_history'];last=hs[-1][0];review=review_for(code,ROOT)
 def ref(month=False):
  dt=date.fromisoformat(last)
  if month:
   m=dt.month-1;y=dt.year-(m==0);m=m or 12;target=date(y,m,min(dt.day,calendar.monthrange(y,m)[1])).isoformat()
  else:target=(dt-timedelta(days=7)).isoformat()
  v=[h for h in rec['history'] if h[0]<=target]
  return adjusted_premium(review,v[-1]) if v and (date.fromisoformat(target)-date.fromisoformat(v[-1][0])).days<=10 else None
 meta['pairs'].append(dict(code=code,name=d['name'],a_ticker=d['a_share_code'].split('.')[0]+' CH Equity',h_ticker=str(int(code))+' HK Equity',ipo_date=d['ipo_date'],raw_debut=hs[0][1],cache_start=cr,cache_rows=len(hs),stored_7=ref(),stored_1m=ref(True),latest_date=last,review=review));cr+=len(hs)
 raw=load(f'data/ah_study_cache/a_{code}.json');start=(date.fromisoformat(d['ipo_date'])-timedelta(days=31)).isoformat();end=(date.fromisoformat(d['ipo_date'])+timedelta(days=31)).isoformat()
 common=[[x[0],x[1],benchmark[x[0]]] for x in raw if start<=x[0]<=end and x[0] in benchmark and x[1]>0]
 total=share_multiplier(review,last,'a');trend=[[x[0],x[1]*share_multiplier(review,x[0],'a')/total,benchmark[x[0]]] for x in raw if start<=x[0]<=last and x[0] in benchmark and x[1]>0]
 pre=[x for x in common if x[0]<d['ipo_date']];ar=100*(pre[-1][1]/pre[0][1]-1) if len(pre)>1 else None;br=100*(pre[-1][2]/pre[0][2]-1) if len(pre)>1 else None
 reference['pairs'][code]=dict(ipo_date=d['ipo_date'],rows=common,trend_rows=trend,pre_a_return_pct=ar,pre_csi_return_pct=br,pre_excess_pp=ar-br if ar is not None and br is not None else None,pre_from=pre[0][0] if pre else None,pre_to=pre[-1][0] if pre else None,a_first_observation=raw[0][0] if raw else None)
meta['ah_cache_end']=cr-1
save('data/desk_chart_data.json',meta);save('data/ah_reference.json',reference)
print('AH metadata',len(meta['pairs']),'pairs; appended 15 H sessions; existing histories preserved')
