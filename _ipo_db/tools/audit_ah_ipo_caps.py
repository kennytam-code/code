"""Audit A/H offer references and scalar share-class-cap wiring; no terminal claims."""
import json,math,re,sys,zipfile,xml.etree.ElementTree as E
from datetime import date
from pathlib import Path
R=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(R/'ipo_lib'))
from market_universe import load,histories
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value
D={d['code']:d for d in load(R)};fx=json.loads((R/'data/ah_study_cache/cnyhkd.json').read_text());rows=[];held=[]
for r in histories(R)['pairs']:
 c=r['code'];d=D[c];ap=R/f'data/ah_study_cache/a_{c}.json';ipo=r['ipo_date'];rec={'code':c,'ipo_date':ipo,'a_code':d['a_share_code'],'offer_hkd':d.get('final_price'),'stored_premium_pct':r.get('offer_reference_premium_pct')}
 if ap.exists() and d.get("final_price"):
  aa=[p for p in json.loads(ap.read_text()) if p[0]<ipo];ff=[p for p in fx if p[0]<ipo]
  if aa and ff:
   a,f=aa[-1],ff[-1];premium=(a[1]*f[1]/d['final_price']-1)*100
   rec.update(a_date=a[0],a_close_cny=a[1],fx_date=f[0],cnyhkd=f[1],recomputed_premium_pct=premium,a_lag_days=(date.fromisoformat(ipo)-date.fromisoformat(a[0])).days,fx_lag_days=(date.fromisoformat(ipo)-date.fromisoformat(f[0])).days)
   rec['history_match']=r.get('offer_reference_premium_pct') is not None and math.isclose(premium,r['offer_reference_premium_pct'],abs_tol=1e-8)
   rec['database_match']=d.get('a_premium_ipo_pct') is None or abs(premium-d['a_premium_ipo_pct'])<.015
   rec['date_match']=a[0]==r.get('offer_reference_a_date') and f[0]==r.get('offer_reference_fx_date')
 if not d.get('final_price'):
  rec['not_applicable']='Listing without H offer price';rows.append(rec);continue
 if ap.exists() and json.loads(ap.read_text())[0][0]>ipo:
  rec['not_applicable']='A-share history starts after H listing';rows.append(rec);continue
 if not rec.get('history_match') or not rec.get('date_match') or rec.get('a_lag_days',99)>10 or rec.get('fx_lag_days',99)>5:held.append(rec)
 rows.append(rec)
with zipfile.ZipFile(R/'out/HK_IPO_Database_v1.xlsx') as z:
 _,_,s=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']});ah=nodes(E.fromstring(z.read(s['AH'])));md=nodes(E.fromstring(z.read(s['Market Data'])));records={r['code']:r for r in histories(R)['pairs']};n=0
 for a,node in ah.items():
  if not re.fullmatch('C[0-9]+',a):continue
  f=node.find(q('f'))
  if f is None or "'Market Data'!P" not in f.text:continue
  row=int(a[1:]);j=row-5;c=str(int(float(value(node)))).zfill(4);d=D[c];r=records[c]
  assert value(md['R'+str(j)])==d['a_share_code'].split('.')[0]+' CH Equity',(c,'A ticker')
  assert value(md['Q'+str(j)])==str(int(c))+' HK Equity',(c,'H ticker')
  for col,t in [('F','R'),('G','Q')]:
   form=ah[col+str(row)].find(q('f'))
   assert form.text==f'IF($E$4<>"Bloomberg","—",IFERROR(BDP(\'Market Data\'!${t}{j},"CURRENT_MARKET_CAP_SHARE_CLASS"),"Unavailable"))'
   assert form.get('t') is None
  cached=value(ah['H'+str(row)]);expected=r.get('offer_reference_premium_pct')
  assert expected is None or math.isclose(float(cached),expected/100,abs_tol=1e-10),(c,cached,expected)
  n+=1
 assert n==75,n
report={'pairs':len(rows),'roster_formula_checks':n,'ipo_reference_checks':rows,'held':held,'source_scope':'Recomputed from retained dated raw A-price and FX histories, not a fresh independent market-price verification. Final H offer price cross-checked against canonical terms.','market_cap_field':'CURRENT_MARKET_CAP_SHARE_CLASS','units':'Existing RR233 output convention: millions in security currency; A CNY, H HKD. No additional scaling. Live field metadata/entitlement and response units unverified without terminal.','market_cap_requests':150,'added_requests':0,'live_terminal_tested':False}
(R/'data/demand_review_20261109/ah_ipo_cap_audit.json').write_text(json.dumps(report,indent=2)+'\n');print('AH',len(rows),'recomputed; held',len(held),'roster',n);print(json.dumps(held,indent=2))
