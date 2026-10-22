"""Check query scopes, response separation, exact aggregate factoring and cell moves."""
import sys,re,zipfile,json,hashlib,collections
from pathlib import Path
import xml.etree.ElementTree as E
import numpy as np,formulas
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value
from screener_desk import MOVES,rewrite,CALC
OUT=ROOT/'out/efficiency_20261022'
def load(path):
 z=zipfile.ZipFile(path);_,_,s=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']});return z,s
old,os=load(OUT/'baseline.xlsx');mid,ms=load(OUT/'requests_only.xlsx');new,ns=load(ROOT/'out/HK_IPO_Database_v1.xlsx')
def sheet(z,s,n):return nodes(E.fromstring(z.read(s[n])))
def formula(c):return c.find(q('f')).text if c is not None and c.find(q('f')) is not None else None
v=sheet(new,ns,'Valuation Data');db=sheet(new,ns,'Database');sc=sheet(new,ns,'Screener');verify=sheet(new,ns,'BBG Verify')
assert value(db['B2'])=='Selected' and value(verify['B2'])=='Off'
guards=0
for a,c in verify.items():
 f=formula(c)
 if f and re.search(r'\b(BDP|BDH|BQL)\(',f):assert f.startswith('IF($B$2="On",');guards+=1
assert guards==5385
gate_cases=0
for i in range(526):
 r=8+8*i;f=formulas.Parser().ast('='+formula(v['BM'+str(r)]))[1].compile()
 for mode,selected,comp,expected in [('Off',True,True,False),('All',False,False,True),('Selected',False,False,False),('Selected',True,False,True),('Selected',False,True,True)]:
  args=[]
  for key in f.inputs:
   if key=='DATABASE!B2':args.append(mode)
   elif key=='SELECTEDDEAL':args.append('Issuer' if selected else 'Other')
   elif ':' in key:args.append(np.array([['Issuer' if comp else 'Other']]*15,dtype=object))
   else:args.append('Issuer')
  assert bool(f(*args).item())==expected,(r,mode,f.inputs);gate_cases+=1
 for col in ['C','F','P','Z','AJ','AU','BD']:assert formula(v[col+str(r)]).startswith(f'IF($BM{r},')
 for col,direct in [('AU','C'),('BD','F')]:assert f'IF(ISNUMBER({direct}{r}),"",' in formula(v[col+str(r)])
 for col in ['L','M','X','AH','AR']:assert formula(v[col+str(r)]).endswith(',"Not requested")')
# A/H requests use the exact live roster, preserving independent A/H adjustment options.
recent=sheet(new,ns,'AH Recent');md=sheet(new,ns,'Market Data');delta=sheet(new,ns,'AH Delta')
req=[(a,formula(c)) for a,c in recent.items() if formula(c) and 'BDH(' in formula(c)]
assert len(req)==143 and sum('CNYHKD Curncy' in f for a,f in req)==1
for i in range(71):
 rr=5+70*i;r=i+3
 for col,ticker in [('A','Q'),('D','R')]:
  f=formula(recent[col+str(rr)]);assert f"'Market Data'!${ticker}${r}" in f and 'TODAY()-55,TODAY()' in f and '"CapChg=N"' in f
  assert value(md[ticker+str(r)]).endswith(' Equity')
 for col in ['D','E']:
  f=formula(delta[col+str(r)]);assert f"'AH Recent'!$A${rr}:$A${rr+64}" in f
  refs=re.findall(r"'AH Recent'!\$([GH])\$(\d+):\$[GH]\$(\d+)",f);assert refs and all(start=='5' and end=='69' for _,start,end in refs)
# Prove aggregate factoring is algebraically identical by expanding helper references.
before=sheet(old,os,'AH Compare');after=sheet(new,ns,'AH Compare');expanded=0
for a,c in before.items():
 f=formula(c);g=formula(after[a])
 if not f:continue
 for helper in ['AK','AL','AM','AN']:
  rg=f"'AH Compare Live'!${dict(AK='A',AL='J',AM='S',AN='AB')[helper]}$5:${dict(AK='A',AL='J',AM='S',AN='AB')[helper]}$2204"
  g=re.sub(r'(?<!!)' + re.escape(f'${helper}$5') + r'(?![0-9])',lambda m:f'MATCH(MIN({rg}),{rg},0)',g)
  for r,op in [(2,'COUNT'),(3,'MIN'),(4,'MAX')]:g=re.sub(r'(?<!!)' + re.escape(f'${helper}${r}') + r'(?![0-9])',lambda m:f'{op}({rg})',g)
 assert g==f,a;expanded+=1
counts=lambda cells:collections.Counter(re.findall(r'\b(COUNT|MIN|MAX)\([^()]+\)', '\n'.join(formula(c) or '' for c in cells.values())))
assert counts(after)['COUNT']==4 and counts(before)['COUNT']==52808
del before,after
# Every layout-moved value, user input and formula has an explicit one-to-one target.
mscreen=sheet(mid,ms,'Screener');ncalc=sheet(new,ns,CALC)
for a,(sn,dest) in MOVES.items():
 original=mscreen[a];actual=(sc if sn=='Screener' else ncalc)[dest]
 assert value(original)==value(actual),(a,dest,'cached value')
 assert (rewrite(formula(original),'Screener',sn) if formula(original) else None)==formula(actual),(a,dest)
# All other formulas in all sheets must equal the deterministic reference mapping.
preserved=0
for name in ms:
 prev=sheet(mid,ms,name);now=sheet(new,ns,name)
 for a,c in prev.items():
  f=formula(c)
  if f is None:continue
  sn,dest=MOVES.get(a,(name,a)) if name=='Screener' else (name,a)
  got=(ncalc if sn==CALC and name=='Screener' else now)[dest]
  assert formula(got)==rewrite(f,name,sn),(name,a,dest);preserved+=1
# Database historic constants, all native charts, saved histories and eleven inputs survive.
numeric=0
odb=sheet(old,os,'Database')
for a,c in odb.items():
 if int(re.search(r'\d+',a)[0])<5:continue
 assert value(c)==value(db[a]),a
 if c.get('t') in [None,'n'] and value(c):numeric+=1
for p in old.namelist():
 if p.startswith(('xl/charts/','xl/drawings/')):assert old.read(p)==new.read(p),p
for name in ['AH History','Peer Data','HK Stocks']:
 assert old.read(os[name])==new.read(ns[name]),name
assert new.read('xl/workbook.xml')==old.read('xl/workbook.xml')
# Native structure, formula lengths, and control merge boundaries.
for name,path in ns.items():
 for _,c in E.iterparse(new.open(path),events=('end',)):
  if c.tag==q('f'):assert '#REF!' not in (c.text or '') and len(c.text or '')<=8192;c.clear()
  elif c.tag==q('row'):c.clear()
doc=E.fromstring(new.read(ns['Screener']));ranges=[m.get('ref') for m in doc.iter(q('mergeCell'))]
assert 'B5:C5' in ranges and doc.find(q('sheetViews')).find(q('sheetView')).find(q('pane')).get('xSplit')=='2'
assert {dv.get('sqref') for dv in doc.iter(q('dataValidation'))}>={'B5','P7','P9'}
result={'passed':True,'valuation_gate_cases':gate_cases,'guarded_verify_cells':guards,'ah_pairs':71,'recent_bdh_requests_before':204,'recent_bdh_requests_after':143,'ah_compare_count_before':52808,'ah_compare_count_after':4,'aggregate_formulas_expanded':expanded,'layout_formulas_checked':preserved,'historical_database_numeric_cells_unchanged':numeric,'native_charts_unchanged':True,'live_bloomberg_tested':False,'sha256':hashlib.sha256((ROOT/'out/HK_IPO_Database_v1.xlsx').read_bytes()).hexdigest()}
(OUT/'workbook_checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
