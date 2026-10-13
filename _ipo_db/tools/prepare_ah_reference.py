"""Sequential CSI 300 cache and factual A/H coverage audit. No workbook load."""
import sys,json,math,time
from pathlib import Path
from datetime import date,timedelta,datetime,timezone
from bisect import bisect_right
import requests
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'ipo_lib'))
from market_universe import histories
from ah_basis import review_for,comparable

def main():
 records=histories(ROOT)['pairs'];asof=histories(ROOT)['asof']
 cache=ROOT/'data/csi300_prices.json'
 if cache.exists(): benchmark=json.loads(cache.read_text())
 else:
  closes={};urls=[]
  for year in range(2019,2027):
   url=f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000300,day,{year}-01-01,{year}-12-31,320,'
   response=requests.get(url,timeout=25);response.raise_for_status()
   rows=response.json()['data']['sh000300']['day']
   for row in rows:
    if row[0]<=asof and float(row[2])>0:closes[row[0]]=float(row[2])
   urls.append(url);print(year,len(rows),flush=True);time.sleep(.15)
  benchmark=dict(name='CSI 300',code='000300',bloomberg_ticker='SHSZ300 Index',asof=asof,
   closes=sorted(closes.items()),source_urls=urls,methodology='https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/en/000300_Index_Methodology_en.pdf',
   retrieved_at=datetime.now(timezone.utc).isoformat())
  cache.write_text(json.dumps(benchmark,ensure_ascii=False,indent=1))
 b=dict(benchmark['closes']);pairs={};audit=[]
 for r in records:
  code=r['code'];ipo=r['ipo_date'];raw=json.loads((ROOT/f'data/ah_study_cache/a_{code}.json').read_text())
  # The A cache stores [date, raw close, raw open]. Retain native CNY prices.
  start=(date.fromisoformat(ipo)-timedelta(days=31)).isoformat();end=(date.fromisoformat(ipo)+timedelta(days=31)).isoformat()
  common=[[x[0],x[1],b[x[0]]] for x in raw if start<=x[0]<=end and x[0] in b and x[1]>0]
  pre=[x for x in common if x[0]<ipo];post=[x for x in common if x[0]>=ipo]
  ar=100*(pre[-1][1]/pre[0][1]-1) if len(pre)>1 else None
  br=100*(pre[-1][2]/pre[0][2]-1) if len(pre)>1 else None
  pairs[code]=dict(ipo_date=ipo,rows=common,pre_a_return_pct=ar,pre_csi_return_pct=br,
   pre_excess_pp=ar-br if ar is not None and br is not None else None,
   pre_from=pre[0][0] if pre else None,pre_to=pre[-1][0] if pre else None,
   a_first_observation=raw[0][0] if raw else None)
  hs=r.get('h_history',[]);aligned=r.get('history',[]);by={x[0]:x for x in aligned};review=review_for(code,ROOT)
  absent=[x[0] for x in hs if x[0] not in by];mismatch=[x[0] for x in aligned if not comparable(review,x[0],x[5])]
  assert all(math.isclose(x[4],x[2]*x[3]/x[1]-1,rel_tol=1e-10,abs_tol=1e-10) for x in aligned)
  assert all(0<=(date.fromisoformat(x[0])-date.fromisoformat(x[5])).days<=10 and 0<=(date.fromisoformat(x[0])-date.fromisoformat(x[6])).days<=5 for x in aligned)
  assert [x[0] for x in hs]==sorted(set(x[0] for x in hs))
  audit.append(dict(code=code,h_sessions=len(hs),aligned_sessions=len(aligned),first_h=hs[0][0] if hs else None,
   first_a=raw[0][0] if raw else None,latest_h=hs[-1][0] if hs else None,missing_aligned_dates=absent,
   incompatible_entitlement_dates=mismatch,pre_common_sessions=len(pre),pre_reference_available=len(pre)>1))
 ref=dict(asof=asof,benchmark=benchmark['name'],pairs=pairs)
 (ROOT/'data/ah_reference.json').write_text(json.dumps(ref,ensure_ascii=False,indent=1))
 (ROOT/'data/batches/ah_chart_review_20261013.json').write_text(json.dumps(dict(asof=asof,pair_count=len(records),premium_math='passed',no_lookahead='passed',pairs=audit),indent=1))
 print('PASS',len(records),'pairs;',sum(len(x['rows'])>1 for x in pairs.values()),'benchmark windows;',sum(x['pre_reference_available'] for x in audit),'pre-IPO windows',flush=True)
 for x in audit:
  if x['missing_aligned_dates']:print(x['code'],'H sessions',x['h_sessions'],'aligned',x['aligned_sessions'],'first A',x['first_a'])
if __name__=='__main__':main()
