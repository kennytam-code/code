"""A desk-wide cosmetic change must preserve every value, formula and chart input."""
import zipfile,xml.etree.ElementTree as E,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q
from desk_theme import SCREEN_MOVES,SCREEN_LABELS,SCREEN_CLEARS
def payload(raw):
 n=E.fromstring(raw);n.attrib.pop('r',None);return E.tostring(n)
def blank(raw):
 n=E.fromstring(raw);return n.find(q('f')) is None and not ''.join(n.itertext())
def content(z,p):
 result={}
 for _,node in E.iterparse(z.open(p),events=('end',)):
  if node.tag==q('c'):
   node.attrib.pop('s',None);result[node.get('r')]=E.tostring(node);node.clear()
  elif node.tag==q('row'):node.clear()
 return result
def chart_data(raw):
 doc=E.fromstring(raw)
 for parent in doc.iter():
  for child in list(parent):
   if child.tag.endswith('}spPr'):parent.remove(child)
 return E.tostring(doc)
with zipfile.ZipFile(ROOT/'out/_theme_baseline_20261015.xlsx') as old,zipfile.ZipFile(ROOT/'out/HK_IPO_Database_v1.xlsx') as new:
 assert set(old.namelist())==set(new.namelist())
 _,_,s=maps({p:new.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
 count=0
 for name,p in s.items():
  if old.read(p)==new.read(p):continue
  a,b=content(old,p),content(new,p)
  title='A2' if name in ['IPO Live','AH','Peer Trades'] else 'A1'
  assert blank(b[title]),('Title not removed',name);a.pop(title);b.pop(title)
  if name=='IPO Live':
   assert payload(a['G2'])==payload(b['G4']) and blank(b['G2'])
   for addr in ['G2','G4']:a.pop(addr,None);b.pop(addr,None)
  if name=='Screener':
   for source,target in SCREEN_MOVES.items():
    assert payload(a[source])==payload(b[target]),('Moved output changed',source,target)
    assert blank(b[source]),source
    for addr in [source,target]:a.pop(addr,None);b.pop(addr,None)
   for addr in [*SCREEN_LABELS,*SCREEN_CLEARS]:
    if addr in a:
     assert E.fromstring(a[addr]).find(q('f')) is None,addr
     assert E.fromstring(b[addr]).find(q('f')) is None,addr
     a.pop(addr);b.pop(addr)
    elif addr in b:
     assert E.fromstring(b[addr]).find(q('f')) is None,addr
     b.pop(addr)
   for addr in ['F6','E15','F15']:
    if addr not in a and addr in b:assert blank(b.pop(addr)),addr
  assert a==b,('Cell content changed',name,next(k for k in set(a)|set(b) if a.get(k)!=b.get(k)))
  count+=1
 for p in new.namelist():
  if p.startswith('xl/charts/') and p.endswith('.xml'):assert chart_data(old.read(p))==chart_data(new.read(p)),p
  if p.startswith('xl/drawings/') or p.endswith('.rels') or p=='xl/workbook.xml':assert old.read(p)==new.read(p),p
 styles=E.fromstring(new.read('xl/styles.xml'));assert len(styles.find(q('cellXfs')))<64000
 # Keep every live/override control accessible after removing title rows.
 for name,rows in {'IPO Live':[4,5],'AH':[4],'Peer Trades':[3,4],'Screener':[5,7,8,9,10,11,12,13,14,16,17,18]}.items():
  d=E.fromstring(new.read(s[name]));rr={int(r.get('r')):r for r in d.find(q('sheetData'))}
  assert all(rr[r].get('hidden')!='1' for r in rows),('Hidden input',name)
 d=E.fromstring(new.read(s['Screener']));cells={c.get('r'):c for c in d.iter(q('c'))}
 nf={x.get('numFmtId'):x.get('formatCode') for x in styles.find(q('numFmts'))};xf=styles.find(q('cellXfs'))
 assert all(nf.get(xf[int(cells['D'+str(r)].get('s'))].get('numFmtId'))==';;;' for r in range(7,15))
 print('PASS',count,'tabs: business values/formulas/caches identical including seven mapped Screener outputs; only explicit titles/labels removed; native chart data, axes, anchors, relationships and sheet order retained')
