"""Release contracts for the AH relocation, daily deltas and complete chart refresh."""
import json,sys,zipfile,math,collections,re,hashlib
from pathlib import Path
import xml.etree.ElementTree as E
import numpy as np,formulas
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value
from market_universe import histories
from ah_basis import adjusted_premium,review_for
from ah_chart_style import c
path=ROOT/'out/HK_IPO_Database_v1.xlsx'
with zipfile.ZipFile(path) as z:
 _,_,sheets=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
 def cells(name):return nodes(E.fromstring(z.read(sheets[name])))
 ah=cells('AH');delta=cells('AH Delta');sc=cells('Screener');calc=cells('Calc (scoring engine)')
 meta=json.loads((ROOT/'data/desk_chart_data.json').read_text())['pairs'];records={r['code']:r for r in histories(ROOT)['pairs']}
 assert value(ah['G7'])=='1D Δ (pp)' and value(ah['I7'])=='1M Δ (pp)'
 for i,m in enumerate(meta):
  r=i+8;d=i+3;rec=records[m['code']];points={x[0]:x for x in rec.get('history',[])};hs=rec.get('h_history',[])
  p=points.get(hs[-2][0]) if len(hs)>1 and hs[-1][0]==rec.get('latest_date') else None
  expected=adjusted_premium(review_for(m['code'],ROOT),p) if p else None
  got=value(delta[f'U{d}'])
  assert (expected is None and got in ['',None]) or math.isclose(float(got),expected,abs_tol=1e-12),(m['code'],'prior')
  f=ah[f'G{r}'].find(q('f')).text;assert f"'AH Delta'!AD{d}" in f
  if expected is not None:assert math.isclose(float(value(ah[f'G{r}'])),100*(float(value(ah[f'F{r}']))-expected),abs_tol=1e-10)
  else:assert value(ah[f'G{r}']) in ['',None]
 assert value(ah['M60'])=='2384' and float(value(ah['M64']))==2384
 assert math.isclose(float(value(ah['M72'])),104.6*1.176082968711853/86.8-1,abs_tol=1e-12)
 for addr in ['F53','F54','F56']:
  assert addr not in sc or sc[addr].find(q('f')) is None
 assert not any('BDH(' in f.text for f in E.fromstring(z.read(sheets['Screener'])).iter(q('f')))
 assert 'Database!$BQ$5' in calc['AY53'].find(q('f')).text
 valuation=z.read(sheets['Valuation Data']);assert b"'Calc (scoring engine)'!$AY$54" in valuation and b'Screener!$F$54' not in valuation
 # Execute the exact numeric-only input formulas, including invalid values.
 def evaluate(addr,data):
  fn=formulas.Parser().ast('='+ah[addr].find(q('f')).text)[1].compile()
  return fn(*[data[k] for k in fn.inputs]).item()
 for inp,want in [('9607','9607'),(9607,'9607'),('09607','9607'),('2384','2384'),('a',''),(0,''),(2.3,''),(100000,'')]:assert evaluate('P78',{'M60':inp})==want
 for manual,auto,want in [('', '002384.SZ',2384),('688036','002384.SZ',688036),('000001','',1),('bad','002384.SZ',''),('','','')]:assert evaluate('M64',{'M61':manual,'P79':auto})==want
 for manual,auto,want in [('',86.8,86.8),(80,86.8,80),(0,86.8,''),(-1,86.8,''),('bad',86.8,'')]:assert evaluate('M65',{'M62':manual,'P80':auto})==want
 # Only one shared FX history; no history requests in the manual checker.
 recent=E.fromstring(z.read(sheets['AH Recent']));bdh=[f.text for f in recent.iter(q('f')) if 'BDH(' in f.text]
 assert len(bdh)==2*len(meta)+1 and sum('CNYHKD Curncy' in f for f in bdh)==1
 assert not any('BDH(' in ah[f'M{r}'].find(q('f')).text for r in [64,65,66,68,69,70,72,73])
 # Every summary is the arithmetic average of the matching pair changes.
 end=7+len(meta);summary=0
 for addr,n in ah.items():
  f=n.find(q('f'))
  if f is None or 'AVERAGEIF(' not in f.text:continue
  match=re.search(r'AVERAGEIF\(\$([CD])\$8:.*?,\$A(\d+),\$([FGHI])\$8',f.text);assert match
  criterion,row,col=match.groups();group=value(ah['A'+row]);vs=[]
  for r in range(8,end+1):
   v=value(ah[col+str(r)])
   if value(ah[criterion+str(r)])==group and v not in ['',None]:vs.append(float(v))
  assert (not vs and value(n) in ['',None]) or math.isclose(float(value(n)),sum(vs)/len(vs),abs_tol=1e-10),addr
  summary+=1
 # A cosmetic update cannot change any chart's underlying ranges or values.
 def signatures(archive):
  result=collections.Counter()
  for p in archive.namelist():
   if not(p.startswith('xl/charts/') and p.endswith('.xml')):continue
   doc=E.fromstring(archive.read(p))
   if b'Screener' in archive.read(p):continue
   for ser in doc.iter(c('ser')):
    sig=tuple(E.tostring(n).decode() for n in ser if n.tag in [c('xVal'),c('yVal'),c('cat'),c('val')]);result[sig]+=1
  return result
 with zipfile.ZipFile(ROOT/'out/update_20261028/pre_chart_refresh.xlsx') as base:assert signatures(z)==signatures(base)
 chart_count=0
 for p in z.namelist():
  if not(p.startswith('xl/charts/') and p.endswith('.xml')):continue
  chart_count+=1;doc=E.fromstring(z.read(p))
  assert all(n.get('val')=='0' for n in doc.iter(c('smooth')))
  for group in doc.iter(c('barChart')):
   for ser in group.findall(c('ser')):
    assert ser.find(c('invertIfNegative')).get('val')=='1'
    assert b'B5484D' in E.tostring(ser) and b'28795A' in E.tostring(ser)
 result=dict(passed=True,ah_pairs=len(meta),summary_formulas=summary,chart_parts=chart_count,chart_ranges_and_observations_preserved=True,actual_formula_edge_cases=18,bloomberg_live_tested=False,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
 (ROOT/'data/update_20261028/workbook_checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
