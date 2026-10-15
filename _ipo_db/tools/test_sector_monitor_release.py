"""Check sector math, dependency cleanup and unchanged production sheets."""
import sys,zipfile,re,math,json
from pathlib import Path
import xml.etree.ElementTree as E
import numpy as np,formulas,schedula
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value,ci,ec
from sector_monitor_release import REMOVED
sector_output=ROOT/'out/_polish_baseline_20261015.xlsx'
if not sector_output.exists():sector_output=ROOT/'out/HK_IPO_Database_v1.xlsx'
with zipfile.ZipFile(sector_output) as z,zipfile.ZipFile(ROOT/'out/_sector_baseline_20261015.xlsx') as before:
 _,_,s=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
 _,_,old=maps({p:before.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
 assert not REMOVED & set(s)
 assert set(s)==set(old)-REMOVED
 for name,p in s.items():
  if name not in ['AH','Chart Data','Notes']:assert z.read(p)==before.read(old[name]),name
 for p in z.namelist():
  if p.startswith('xl/charts/') and p.endswith('.xml'):assert z.read(p)==before.read(p),p
 ah=nodes(E.fromstring(z.read(s['AH'])));previous=nodes(E.fromstring(before.read(old['AH'])))
 for a,c in previous.items():
  row=int(re.search(r'\d+',a)[0]);col=ci(re.match('[A-Z]+',a)[0])
  if a in ['J5','P60'] or 57<=row<=74 and 10<=col<=15:continue
  assert E.tostring(c)==E.tostring(ah[a]),a
 first,last=8,7+len(json.loads((ROOT/'data/desk_chart_data.json').read_text())['pairs'])
 sectors=sorted({value(ah['C'+str(r)]) for r in range(first,last+1)})
 def raw(c):
  if c is None:return schedula.EMPTY
  v=value(c)
  if v in [None,'']:return schedula.EMPTY
  return v if c.get('t') in ['inlineStr','str','s','e'] else float(v)
 fixture={a:raw(c) for a,c in ah.items()}
 def calc(addr,override=None):
  cells={**fixture,**(override or {})};fn=formulas.Parser().ast('='+ah[addr].find(q('f')).text)[1].compile();args=[]
  for key in fn.inputs:
   if ':' not in key:args.append(cells.get(key,schedula.EMPTY));continue
   a,b=key.split(':');ca=ci(re.match('[A-Z]+',a)[0]);cb=ci(re.match('[A-Z]+',b)[0]);ra=int(re.search(r'\d+',a)[0]);rb=int(re.search(r'\d+',b)[0])
   args.append(np.array([[cells.get(ec(c)+str(r),schedula.EMPTY) for c in range(ca,cb+1)] for r in range(ra,rb+1)],dtype=object))
  result=fn(*args);return result.item() if hasattr(result,'item') else result
 total=61+len(sectors)
 for r,sector in [(60+i,x) for i,x in enumerate(sectors)]+[(total,None)]:
  rows=[i for i in range(first,last+1) if sector is None or fixture['C'+str(i)]==sector]
  assert calc('K'+str(r))==len(rows)==raw(ah['K'+str(r)])
  for out,source in [('L','E'),('M','F'),('N','G'),('O','H')]:
   values=[fixture[source+str(i)] for i in rows];values=[x for x in values if isinstance(x,(int,float))]
   expected=sum(values)/len(values) if values else '—';got=calc(out+str(r))
   assert got==expected or isinstance(got,(int,float)) and math.isclose(got,expected,abs_tol=1e-12)
   assert math.isclose(raw(ah[out+str(r)]),expected,abs_tol=1e-12)
   # A desk refresh changes source values without needing another build.
   changed={source+str(i):schedula.EMPTY for i in rows};changed[source+str(rows[0])]=0
   assert calc(out+str(r),changed)==0
   changed[source+str(rows[0])]=-5
   assert calc(out+str(r),changed)==-5
   changed[source+str(rows[0])]='Unavailable'
   assert calc(out+str(r),changed)=='—'
 assert '#\'AH\'!J57' in ah['J5'].find(q('f')).text
 assert previous['J60'].find(q('f')).text==ah['P60'].find(q('f')).text
 print('PASS sector formulas/caches: six sectors and all pairs; zero/negative/missing updates; formulas follow existing live sources')
 print('PASS all unrelated worksheets and retained native charts are byte-identical; four lock-up sheets removed')
