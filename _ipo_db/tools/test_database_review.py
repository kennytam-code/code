"""Dated source/preservation and delivered Database regression checks."""
import copy,hashlib,json,math,re,sys,tempfile,zipfile,gc
from pathlib import Path
import xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from demand_review import apply_records
from capital_review import apply_records as capital
from metric_source_review import apply_records as metric
from retail_float_review import apply_records as retail
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value
review=ROOT/'data/demand_review_20261109'
before=json.loads((review/'before_deals.json').read_text())['deals'];after=json.loads((ROOT/'data/deals.json').read_text())['deals']
capital_rows=json.loads((ROOT/'data/batches/capital_source_review.json').read_text())['deals'];caps={r['code']:r for r in capital_rows}
allocation={'alloc_mechanism','allocation_mechanism','clawback','clawback_status','clawback_display','clawback_reported','_prov'}
capfields={'shares_outstanding','shares_issued_on_listing','mktcap_ipo_hkdm','mktcap_basis','mktcap_source','mktcap_source_page','mktcap_note','pe_ipo','ps_ipo','pe_note','ps_note','eff_free_float_pct','eff_ff_note'}
assert len(before)==len(after)==527
for a,b in zip(before,after):
 assert a['code']==b['code']
 allowed=allocation|(capfields if b['code'] in caps else set())
 allowed|={'public_shares_final','day1_vol_x_retail'}
 if b['code'] in ['3308','3223','9976','9607','2636']:allowed|={'a_close_cny','a_close_date','a_close_hkd','cnyhkd','a_premium_ipo_pct','ah_discount_ipo_pct'}
 if b['code'] in ['2256','1256','2636','2384']:allowed|={'day1_open','day1_close','day1_high','day1_low','day1_volume','day1_range_pct','day1_turnover_hkdm','day1_vol_x_offer'}
 assert all(a.get(k)==b.get(k) for k in set(a)|set(b) if k not in allowed),(b['code'],'unrelated data changed')
 if b['code'] in caps:
  r=caps[b['code']];assert b['shares_outstanding']==r['shares_outstanding']
  assert b['mktcap_ipo_hkdm']==round(b['final_price']*b['shares_outstanding']/(b.get('depositary_ratio') or 1)/1e6,1)
  assert r['final_offer_evidence']['price']==b['final_price']
  for f,d in [('pe_ipo','ni_latest'),('ps_ipo','rev_latest')]:
   if b.get(f) is not None and b.get(d):assert b[f]==round(b['mktcap_ipo_hkdm']/b[d],1)
 if b['allocation_mechanism']=='Mechanism B':assert b['clawback']=='NA' and b['clawback_display']=='Mechanism B / N/A'
 assert not str(b.get('_prov',{}).get('clawback',{}).get('src','')).startswith('derived:final public split')
assert next(d for d in after if d['code']=='6727')['allocation_mechanism']=='18C'
assert next(d for d in after if d['code']=='2631')['allocation_mechanism']=='Mechanism A'
assert next(d for d in after if d['code']=='2580')['allocation_mechanism']=='Mechanism A'
zjld=next(d for d in after if d['code']=='6979');assert zjld['pe_ipo']==17.5 and zjld['_prov']['pe_ipo']['src'].startswith('bloomberg:'),'Independent TTM P/E must not be erased by missing FY income'
for c in ['2015','9868','9898','2390','9896']:assert next(d for d in after if d['code']==c)['clawback']=='NO'
again=copy.deepcopy(after);apply_records(again,ROOT);capital(again,ROOT);metric(again,ROOT);retail(again,ROOT);assert again==after;del again
with tempfile.TemporaryDirectory() as t:
 root=Path(t);(root/'data/batches').mkdir(parents=True)
 (root/'data/batches/allocation_source_review.json').write_text(json.dumps({'deals':[{'code':'B','allocation_mechanism':'Mechanism B','evidence':{}},{'code':'C','allocation_mechanism':'18C','evidence':{}}]}))
 rows=[{'code':'B','clawback':'NO'},{'code':'C','clawback':'NO'},{'code':'N','clawback':'NA'},{'code':'U','clawback':'YES','_prov':{'clawback':{'src':'derived:final public split'}}}]
 apply_records(rows,root)
 assert [d['clawback_display'] for d in rows]==['Mechanism B / N/A','18C / No','N/A','']
 # Quoted headings and reverse reallocation candidates never auto-promote YES.
 assert rows[-1].get('clawback') is None
path=ROOT/'out/HK_IPO_Database_v1.xlsx';baseline=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT.parent/'before.xlsx'
def formula_map(z,p):
 result={};bdp=bdh=bql=0
 for _,n in E.iterparse(z.open(p),events=('end',)):
  if n.tag==q('c'):
   f=n.find(q('f'))
   if f is not None:
    result[n.get('r')]=(f.text,dict(f.attrib));bdp+=(f.text or '').count('BDP(');bdh+=(f.text or '').count('BDH(');bql+=(f.text or '').count('BQL(')
   n.clear()
  elif n.tag==q('row'):n.clear()
 return result,(bdp,bdh,bql)
with zipfile.ZipFile(path) as z,zipfile.ZipFile(baseline) as old:
 assert z.testzip() is None
 _,_,s=maps({k:z.read(k) for k in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']});_,_,os=maps({k:old.read(k) for k in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
 assert set(s)==set(os) and 'Notes' not in s and 'Lock-up' not in s
 count=0;calls=[0,0,0]
 for name,p in s.items():
  a,c=formula_map(z,p);b,oc=formula_map(old,os[name])
  if name=='IPO Live':
   assert a['C4'][0]==b['C4'][0].replace('2026-10-28','2026-11-09');b['C4']=a['C4']
  assert a==b,(name,'formula drift');assert c==oc,(name,'request count drift');count+=len(a);calls=[x+y for x,y in zip(calls,c)];del a,b;gc.collect()
 charts=[p for p in z.namelist() if p.startswith('xl/charts/') and p.endswith('.xml')]
 changed_charts=[p for p in charts if z.read(p)!=old.read(p)]
 assert not changed_charts,changed_charts
 dbdoc=E.fromstring(z.read(s['Database']));db=nodes(dbdoc)
 for i,d in enumerate(after,5):
  assert (value(db['X'+str(i)]) or '')==d['clawback_display']
  assert 'Unconfirmed' not in d['clawback_display']
 assert value(db['T4'])=='Institutional sub (x)' and ' '.join(value(db['X4']).split())=='Mechanism / clawback'
 assert not any(x.get('type')=='dataBar' for x in dbdoc.iter(q('cfRule')))
 ah=nodes(E.fromstring(z.read(s['AH'])));assert value(ah['E4'])==value(ah['H4'])=='Stored'
 assert value(db['B2'])=='All'
 assert not any('/comments/' in p.lower() or re.search(r'/comments[0-9]+\.xml',p,re.I) or p.lower().endswith('.vml') for p in z.namelist())
 assert next(c for c in dbdoc.find(q('cols')) if int(c.get('min'))<=26<=int(c.get('max'))).get('hidden')=='1'
 for d in after:assert d['day1_vol_x_retail']==round(d['day1_volume']/d['public_shares_final'],2)
 wb=E.fromstring(z.read('xl/workbook.xml'));weights=[n for n in wb.iter(q('definedName')) if n.get('name','').startswith('W_')];assert len(weights)==11
report={'passed':True,'database_rows':len(after),'reviewed_capital_records':len(caps),'changed_market_caps':sum(a.get('mktcap_ipo_hkdm')!=b.get('mktcap_ipo_hkdm') for a,b in zip(before,after)), 'formula_count':count,'business_formulas_unchanged':True,'snapshot_label_formula_updated':1,'added_bloomberg_requests':0,'bloomberg_formula_counts':dict(zip(['BDP','BDH','BQL'],calls)),'charts_byte_identical':len(charts),'unrelated_data_preserved':True,'terminal_tested':False,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
(review/'workbook_validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
