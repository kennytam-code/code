"""Repair three primary-confirmed mappings; add only their dated histories."""
import json,sys,hashlib,urllib.request
from pathlib import Path
from datetime import date,timedelta
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from analyse_ah_study import make_pair
from corp_actions import load_actions
review=ROOT/'data/update_20261109';review.mkdir(exist_ok=True)
mapping={
 '3228':('603228.SS','https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1104/2026110400744.pdf'),
 '6727':('688031.SS','https://static.cninfo.com.cn/finalpage/2026-10-08/1225595449.PDF'),
 '3757':('300757.SZ','https://static.cninfo.com.cn/finalpage/2026-10-26/1225621924.PDF')}
def load(p):return json.loads((ROOT/p).read_text())
def save(p,d):(ROOT/p).write_text(json.dumps(d,ensure_ascii=False,indent=1)+'\n')
data=load('data/deals.json');ds={d['code']:d for d in data['deals']};am=load('data/batches/ah_map.json');study=load('data/batches/ah_study.json');cache=ROOT/'data/ah_study_cache';ipo_batch=load('data/batches/ah_ipo.json')
sources=[];cutoff='2026-10-02';actions=load_actions(ROOT);fx=load('data/ah_study_cache/cnyhkd.json')
for code,(acode,source) in mapping.items():
 d=ds[code];num,exchange=acode.split('.');ast=(date.fromisoformat(d['ipo_date'])-timedelta(days=45)).isoformat()
 rawpath=review/(code+'_primary.pdf')
 if not rawpath.exists():
  req=urllib.request.Request(source,headers={'User-Agent':'Mozilla/5.0'})
  rawpath.write_bytes(urllib.request.urlopen(req,timeout=30).read())
 assert rawpath.read_bytes().startswith(b'%PDF')
 evidence={'code':code,'a_share_code':acode,'source':source,'source_sha256':hashlib.sha256(rawpath.read_bytes()).hexdigest(),'history_through':cutoff,'prices':[]}
 for leg,symbol,start in [('a',('sh' if exchange=='SS' else 'sz')+num,ast),('h',f'hk{int(code):05d}',d['ipo_date'])]:
  url=f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,{start},{cutoff},320,'
  rawfile=review/(code+'_'+leg+'_raw.json')
  if not rawfile.exists():
   req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/'})
   rawfile.write_bytes(urllib.request.urlopen(req,timeout=30).read())
  raw=json.loads(rawfile.read_text());rows=raw.get('data',{}).get(symbol,{}).get('day',[])
  clean=sorted({r[0]:float(r[2]) for r in rows if start<=r[0]<=cutoff and float(r[2])>0 and float(r[5])>0}.items())
  if not clean:raise RuntimeError(f'No raw history {code} {leg}')
  if leg=='h':
   assert clean[0][0]==d['ipo_date'] and abs(clean[0][1]-d['first_close'])<.001
   assert clean[-1][0]==d['price_asof'] and abs(clean[-1][1]-d['last_close'])<.001
  (cache/f'{leg}_{code}.json').write_text(json.dumps(clean))
  evidence['prices'].append({'leg':leg,'url':url,'sha256':hashlib.sha256(rawfile.read_bytes()).hexdigest(),'rows':len(clean),'first':clean[0][0],'last':clean[-1][0]})
 d.update(a_share_code=acode,is_h_share=True,ah_note='')
 for f in ['a_share_code','is_h_share']:
  d.setdefault('_prov',{})[f]={'src':source,'status':'primary-reviewed','evidence':{'url':source,'sha256':evidence['source_sha256'],'page':1}}
 d['_prov'].pop('ah_note',None)
 entry={'code':code,'name':d['name'],'a_share_code':acode,'a_share_exchange':exchange,'verified_by':[source], 'h_over_a_note':'','reviewed_on':'2026-11-09'}
 am['ah_pairs']=[r for r in am['ah_pairs'] if r['code']!=code]+[entry]
 hs=load(f'data/ah_study_cache/h_{code}.json');ars=load(f'data/ah_study_cache/a_{code}.json')
 rec=make_pair(d,hs,ars,fx,cutoff,actions);rec['current_cap_date']='2026-10-03';assert len(rec['history'])==len(hs)
 study['pairs']=[r for r in study['pairs'] if r['code']!=code]+[rec]
 # These are derived only from the explicit pre-debut closes, never today's quote.
 if rec.get('offer_reference_premium_pct') is not None:
  pre=[r for r in ars if r[0]==rec['offer_reference_a_date']][0];rate=[r for r in fx if r[0]==rec['offer_reference_fx_date']][0]
  d['a_premium_ipo_pct']=round(rec['offer_reference_premium_pct'],2);d['a_close_hkd']=pre[1]*rate[1]
  ir={'code':code,'a_share_code':acode,'ipo_date':d['ipo_date'],'h_offer_price':d['final_price'],'a_close_status':'single','a_close_date':pre[0],'a_close_cny':pre[1],'cnyhkd':rate[1],'fx_date':rate[0],'a_close_hkd':d['a_close_hkd'],'ah_discount_ipo_pct':round(100*(d['final_price']/d['a_close_hkd']-1),2),'source':'Dated Tencent raw A close; retained Yahoo CNYHKD close; data/update_20261109'}
  ipo_batch['deals']=[r for r in ipo_batch['deals'] if r['code']!=code]+[ir]
  for f in ['a_premium_ipo_pct','a_close_hkd']:d['_prov'][f]={'src':'derived:dated pre-debut A and CNYHKD; data/update_20261109','status':'single'}
 sources.append(evidence);print(code,acode,'history',len(rec['history']),'last',rec.get('latest_date'),flush=True)
study['universe_count']=len(study['pairs']);study['coverage_reviewed_on']='2026-11-09'
am['mapping_reviewed_on']='2026-11-09'
save('data/deals.json',data);save('data/batches/ah_map.json',am);save('data/batches/ah_study.json',study)
ipo_batch['count']=len(ipo_batch['deals']);ipo_batch['resolved']=sum(r.get('a_close_hkd') is not None for r in ipo_batch['deals']);save('data/batches/ah_ipo.json',ipo_batch)
save('data/update_20261109/mapping_sources.json',sources)
