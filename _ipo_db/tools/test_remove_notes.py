"""Verify Notes removal changes no business cells, charts or scoring inputs."""
import copy,sys,zipfile
from pathlib import Path
import xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value
ENGINE='Calc (scoring engine)'
def read(path):
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None
  return {p:z.read(p) for p in z.namelist()}
a=read(ROOT/'out/_notes_baseline_20261016.xlsx');b=read(ROOT/'out/HK_IPO_Database_v1.xlsx')
wa,_,sa=maps(a);wb,_,sb=maps(b)
assert list(sb)==[s for s in sa if s!='Notes']
assert next(s for s in wb.find(q('sheets')) if s.get('name')==ENGINE).get('state')=='hidden'
assert set(a)-set(b)=={sa['Notes']} and not set(b)-set(a)
allowed={'xl/workbook.xml','xl/_rels/workbook.xml.rels','[Content_Types].xml','docProps/app.xml',sa[ENGINE],sa['Notes']}
assert [p for p in set(a)&set(b) if a[p]!=b[p] and p not in allowed]==[]
na={n.get('name'):n for n in wa.find(q('definedNames'))};nb={n.get('name'):n for n in wb.find(q('definedNames'))}
assert set(na)==set(nb)
oldnotes=nodes(E.fromstring(a[sa['Notes']]));oldcalc=nodes(E.fromstring(a[sa[ENGINE]]));newcalc=nodes(E.fromstring(b[sb[ENGINE]]))
changed=[]
for name,n in na.items():
 if (n.text or '').startswith('Notes!'):
  changed.append(name);old=oldnotes[n.text.split('!')[1].replace('$','')]
  sheet,addr=nb[name].text.rsplit('!',1);assert sheet=="'"+ENGINE+"'"
  new=newcalc[addr.replace('$','')]
  old=copy.deepcopy(old);old.set('r',new.get('r'))
  assert E.tostring(old)==E.tostring(new),(name,'input changed')
 else:
  assert n.text==nb[name].text,(name,'unexpected defined-name change')
assert len(changed)==11
for addr,c in oldcalc.items():
 if addr=='A2':
  assert value(newcalc[addr])==value(c).replace('Weights are named cells on the Notes tab.','Named weights are stored in AT:AV.')
 else:assert E.tostring(c)==E.tostring(newcalc[addr]),('Calc cell changed',addr)
assert set(newcalc)-set(oldcalc)=={col+str(row) for col in ['AT','AU','AV'] for row in range(1,13)}
for path,raw in b.items():
 if path.endswith('.xml'):
  assert b'Notes!' not in raw and b"'Notes'!" not in raw and b'Notes&apos;!' not in raw,path
print('PASS Notes removed; all 11 input values and names preserved; every business cell, formula, cached value, chart, drawing and style unchanged.')
