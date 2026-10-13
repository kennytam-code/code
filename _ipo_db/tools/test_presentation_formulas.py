"""Evaluate production formulas individually, without a full Excel dependency graph.
Bloomberg responses here are fixtures, never claims of live terminal execution.
"""
import sys,json,zipfile,math,re
from pathlib import Path
import xml.etree.ElementTree as E
import numpy as np,formulas
from openpyxl.utils.cell import range_boundaries,get_column_letter
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q
from patch_presentation_workbook import serial,extracted
with zipfile.ZipFile(ROOT/'out/HK_IPO_Database_v1.xlsx') as z:
 _,_,sheets=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
 source={x.get('r'):x for x in E.fromstring(z.read(sheets['AH Reference'])).iter(q('c'))}
ref=json.loads((ROOT/'data/ah_reference.json').read_text());meta=json.loads((ROOT/'data/desk_chart_data.json').read_text())['pairs']
functions={};base={}
for a,x in source.items():
 f=x.find(q('f'));v=x.find(q('v'))
 if a in ['W4','AA4']:continue
 if f is not None:
  formula='='+f.text.replace('ROW()',re.search(r'\d+',a)[0]);functions[a]=formulas.Parser().ast(formula)[1].compile()
 elif v is not None:base[a]=float(v.text)
functions['L8']=formulas.Parser().ast(extracted('C','D',8))[1].compile()
inputs={};cache={}
def evaluate(addr):
 if addr in inputs:return inputs[addr]
 if addr in cache:return cache[addr]
 if addr in functions:
  fn=functions[addr];args=[]
  for name in fn.inputs:
   name=name.replace('$','')
   if ':' in name:
    c1,r1,c2,r2=range_boundaries(name);args.append(np.array([[evaluate(get_column_letter(c)+str(r)) for c in range(c1,c2+1)] for r in range(r1,r2+1)],dtype=object))
   else:args.append(evaluate(name))
  result=fn(*args);value=result.item() if hasattr(result,'size') and result.size==1 else result
 else:value=base.get(addr,'')
 cache[addr]=value;return value
for index,m in enumerate(meta,1):
 inputs={'AH!P3':index,'AH!P6':serial(m['ipo_date']),'AH!E4':'Stored'};cache={}
 rows=ref['pairs'][m['code']]['rows'];pre=[x for x in rows if x[0]<m['ipo_date']]
 assert evaluate('V7')==len(pre),(m['code'],evaluate('V7'))
 if rows:
  assert evaluate('A80')==serial(rows[0][0]) and evaluate('D80')==100 and evaluate('E80')==100
  end=str(79+len(rows));assert math.isclose(evaluate('D'+end),100*rows[-1][1]/rows[0][1],abs_tol=1e-9)
  assert math.isclose(evaluate('E'+end),100*rows[-1][2]/rows[0][2],abs_tol=1e-9)
 else:assert evaluate('D80')=='' and evaluate('E80')==''
 if index%20==0:print('Stored selectors checked:',index,flush=True)
m=next(x for x in meta if x['code']=='3986');index=meta.index(m)+1;rows=ref['pairs']['3986']['rows']
for header in [0,1,2]:
 inputs={'AH!P3':index,'AH!P6':serial(m['ipo_date']),'AH!E4':'Bloomberg'};cache={}
 for r in range(4,100):
  for col in ['W','X','AA','AB']:inputs[col+str(r)]=''
 for r in range(4,4+header):
  for col in ['W','X','AA','AB']:inputs[col+str(r)]='Header'
 for i,x in enumerate(rows,4+header):
  for col,v in [('W',serial(x[0])),('X',x[1]),('AA',serial(x[0])),('AB',x[2])]:inputs[col+str(i)]=v
 assert evaluate('A80')==serial(rows[0][0]) and evaluate('D80')==100 and evaluate('E80')==100
 assert math.isclose(evaluate('D90'),100*rows[10][1]/rows[0][1],abs_tol=1e-9)
 assert math.isclose(evaluate('E90'),100*rows[10][2]/rows[0][2],abs_tol=1e-9)
 inputs['AA'+str(14+header)]='';inputs['AB'+str(14+header)]='';cache={}
 assert evaluate('D90')=='' and evaluate('E90')==''
for values,expected in [({'C8':22.5},22.5),({'C8':'ID','D8':18.3},18.3),({'C8':'ID','D8':'P/E','D9':14.2},14.2),({'D8':'Header','D9':'Field','D10':-3.1},-3.1),({'D9':0},0),({'C8':'#N/A Invalid field'},'Unavailable'),({},'Unavailable')]:
 inputs={a:values.get(a,'') for a in ['C8','D8','D9','D10','D11']};cache={};assert evaluate('L8')==expected,(values,evaluate('L8'))
print('PASS 68 CSI selectors; common-date rebasing; stored/BDH parity with 0/1/2 headers; missing-session blanks; BQL scalar/header/negative/zero/unavailable extraction')
