"""Execute the shipped scoring formulas with actual rows and named weights."""
import sys,json,re,zipfile,math
from pathlib import Path
import xml.etree.ElementTree as E
import formulas
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,serial
from build_xlsx import load

def cellvalue(c):
 if c is None:return ''
 if c.get('t')=='inlineStr':
  inline=c.find(q('is'));return ''.join(inline.itertext()) if inline is not None else ''
 v=c.find(q('v'))
 if v is None or v.text is None:return ''
 return v.text if c.get('t') in ['str','e'] else float(v.text)
with zipfile.ZipFile(ROOT/'out/HK_IPO_Database_v1.xlsx') as z:
 w,_,s=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']});db=nodes(E.fromstring(z.read(s['Database'])));engine=nodes(E.fromstring(z.read(s['Calc (scoring engine)'])))
 byrow={}
 for addr,cell in db.items():byrow.setdefault(int(re.search('[0-9]+',addr)[0]),{})['DATABASE!'+re.match('[A-Z]+',addr)[0]+'5']=cellvalue(cell)
 weights={}
 for n in w.find(q('definedNames')):
  if n.get('name').startswith('W_'):
   sheet,addr=n.text.rsplit('!',1);sheet=sheet.strip("'");assert sheet=='Calc (scoring engine)'
   weights[n.get('name')]=cellvalue(engine[addr.replace('$','')])
 compiled={col:formulas.Parser().ast('='+engine[col+'5'].find(q('f')).text.replace('ROW()','CURRENTROW'))[1].compile() for col in 'BCDEFGHIJK'}
 deals,tax,cfg,pipe,counts=load();targets=[deals[-1],next(d for d in deals if d['code']=='9607'),pipe[0]]
 for target in targets:
  title=target['name'];ispipe='code' not in target or target not in deals
  attrs={'D7':target.get('sector') or '', 'D8':target.get('subsector') or '', 'D9':target.get('deal_size_hkdm',target.get('expected_size_hkdm')) or '', 'D10':target.get('profitable_at_ipo') or '', 'D11':target.get('is_h_share') or '', 'D12':serial(target['ipo_date']) if target.get('ipo_date') else serial('2026-10-15'),'D13':target.get('pe_ipo') or '', 'D14':target.get('oversub_public_mult') or '', 'B18':'All','B16':'standard','D17':'','B17':''}
  base={**weights,**{'SCREENER!'+k:v for k,v in attrs.items()},'SELECTEDDEAL':title};keys=(target.get('cornerstone_keys') or '').split(';')
  base.update({col+'1':keys[i] if i<len(keys) else '' for i,col in enumerate('UVWXY')})
  scores=[]
  for row,deal in enumerate(deals,5):
   fixture=dict(base);fixture['CURRENTROW']=row
   fixture.update(byrow[row])
   for col,fn in compiled.items():
    missing=set(fn.inputs)-set(fixture);assert not missing,(col,missing)
    result=fn(*[fixture[k] for k in fn.inputs]).item();assert isinstance(result,(float,int)) and math.isfinite(result),(title,row,col,result);fixture[col+'5']=result
   scores.append((fixture['K5'],deal['name'],deal['subsector']))
  top=sorted(scores,reverse=True)[:10];assert len(top)==10 and top[0][0]>0 and top[0][2]==target['subsector']
  print('PASS actual native scores for',title,'—',len(scores),'finite rows; leading comp:',top[0][1])
