"""Graft the Artifact-authored peer layout without loading the whole workbook.

The existing daily workbook remains the source for unaffected sheets. Only
monitor parts, dropdown definitions, chart names and appended styles change.
"""
import base64,hashlib,io,json,re,zipfile,gc
from copy import deepcopy
from datetime import date
from pathlib import Path
import xml.etree.ElementTree as E
from openpyxl import load_workbook
from openpyxl.formula.translate import Translator
from build_market_views import bind_peer_charts
from cache_desk_monitors import add_caches
N='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P='http://schemas.openxmlformats.org/package/2006/relationships'
T='http://schemas.openxmlformats.org/package/2006/content-types'
q=lambda n:'{'+N+'}'+n

def maps(parts):
 w=E.fromstring(parts['xl/workbook.xml']);rel=E.fromstring(parts['xl/_rels/workbook.xml.rels']);targets={x.get('Id'):x.get('Target') for x in rel}
 return w,rel,{s.get('name'):('xl/'+targets[s.get('{'+R+'}id')].lstrip('/')).replace('xl/xl/','xl/') for s in w.find(q('sheets'))}

def patch(source,dest,root):
 root=Path(root);meta=json.loads((root/'data/peer_pairs.json').read_text())
 authored=json.loads((root/'data/peer_views_template.json').read_text())
 peer=load_workbook(io.BytesIO(base64.b64decode(authored['xlsx_base64'])))
 pd=peer['Peer Data'];cursor=2
 for stock in meta['stocks']:
  for dt,price in stock['history']:
   pd.cell(cursor,1,date.fromisoformat(dt));pd.cell(cursor,2,price);cursor+=1
 pc=peer['Peer Chart']
 for col in range(1,8):
  cell=pc.cell(5,col)
  for row in range(7,3005):pc.cell(row,col,Translator(cell.value,origin=cell.coordinate).translate_formula(pc.cell(row,col).coordinate))
 bind_peer_charts(peer)
 for sh in peer:
  sh.sheet_state='visible' if sh.title=='Peer Trades' else 'hidden';sh.sheet_view.showGridLines=False
  if sh.title=='Peer Trades':sh.sheet_properties.tabColor='706080'
 for v in peer['Peer Trades'].data_validations.dataValidation:v.showErrorMessage=False
 buffer=io.BytesIO();peer.save(buffer);peer.close();del peer,pd,pc;gc.collect()
 with zipfile.ZipFile(buffer) as z:new={x:z.read(x) for x in z.namelist()}
 buffer.close()
 with zipfile.ZipFile(source) as z:parts={x:z.read(x) for x in z.namelist()}
 wb,rel,sheets=maps(parts);pwb,prel,psheets=maps(new)
 # Append style components and translate only the incoming cell style IDs.
 styles=E.fromstring(parts['xl/styles.xml']);incoming=E.fromstring(new['xl/styles.xml']);offset={}
 for name in ['fonts','fills','borders','cellStyleXfs','cellXfs','dxfs','numFmts']:
  a=styles.find(q(name));b=incoming.find(q(name))
  if a is None:a=E.SubElement(styles,q(name),{'count':'0'})
  offset[name]=len(a)
  if b is None:continue
  if name in ['cellXfs','numFmts','dxfs']:continue
  for item in b:a.append(deepcopy(item))
  a.set('count',str(len(a)))
 nfs=styles.find(q('numFmts'));nfmap={};nextid=max([163]+[int(x.get('numFmtId')) for x in nfs])+1
 for item in incoming.find(q('numFmts')) or []:
  old=int(item.get('numFmtId'));nfmap[old]=nextid;n=deepcopy(item);n.set('numFmtId',str(nextid));nfs.append(n);nextid+=1
 nfs.set('count',str(len(nfs)))
 for item in incoming.find(q('cellXfs')):
  n=deepcopy(item)
  for attr,group in [('fontId','fonts'),('fillId','fills'),('borderId','borders'),('xfId','cellStyleXfs')]:n.set(attr,str(int(n.get(attr,'0'))+offset[group]))
  old=int(n.get('numFmtId','0'));n.set('numFmtId',str(nfmap.get(old,old)));styles.find(q('cellXfs')).append(n)
 styles.find(q('cellXfs')).set('count',str(len(styles.find(q('cellXfs')))))
 for item in incoming.find(q('dxfs')) or []:styles.find(q('dxfs')).append(deepcopy(item))
 styles.find(q('dxfs')).set('count',str(len(styles.find(q('dxfs')))))
 parts['xl/styles.xml']=E.tostring(styles,encoding='utf-8')
 content=E.fromstring(parts['[Content_Types].xml']);known={x.get('PartName') for x in content}
 def override(path,kind):
  if '/'+path not in known:E.SubElement(content,'{'+T+'}Override',{'PartName':'/'+path,'ContentType':kind});known.add('/'+path)
 # Incoming drawing/chart paths are isolated from all existing charts.
 remap={p:p.replace('drawing1','drawingDeskPeer').replace('chart1','chartDeskPeer1').replace('chart2','chartDeskPeer2') for p in new if p.startswith(('xl/drawings/','xl/charts/'))}
 for name,path in psheets.items():
  if name not in sheets:
   pathout='xl/worksheets/sheetDeskStocks.xml';sheets[name]=pathout;sid=max(int(s.get('sheetId')) for s in wb.find(q('sheets')))+1
   E.SubElement(wb.find(q('sheets')),q('sheet'),{'name':name,'sheetId':str(sid),'state':'hidden','{'+R+'}id':'deskStocks'})
   E.SubElement(rel,'{'+P+'}Relationship',{'Id':'deskStocks','Type':R+'/worksheet','Target':'/'+pathout});override(pathout,'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml')
  pathout=sheets[name];doc=E.fromstring(new[path])
  for cell in doc.iter(q('c')):
   if 's' in cell.attrib:cell.set('s',str(int(cell.get('s'))+offset['cellXfs']))
  for rule in doc.iter(q('cfRule')):
   if 'dxfId' in rule.attrib:rule.set('dxfId',str(int(rule.get('dxfId'))+offset['dxfs']))
  parts[pathout]=E.tostring(doc,encoding='utf-8')
  rp=path.replace('/worksheets/','/worksheets/_rels/')+'.rels'
  if rp in new:
   rd=E.fromstring(new[rp])
   for x in rd:
    target=x.get('Target');x.set('Target',target.replace('drawing1','drawingDeskPeer'))
   parts[pathout.replace('/worksheets/','/worksheets/_rels/')+'.rels']=E.tostring(rd,encoding='utf-8')
 for path,out in remap.items():
  raw=new[path]
  if path.endswith('.rels'):
   rd=E.fromstring(raw)
   for x in rd:x.set('Target',x.get('Target').replace('chart1','chartDeskPeer1').replace('chart2','chartDeskPeer2'))
   raw=E.tostring(rd,encoding='utf-8')
  parts[out]=raw
  if '/charts/' in out and out.endswith('.xml'):override(out,'application/vnd.openxmlformats-officedocument.drawingml.chart+xml')
  elif out.endswith('.xml') and '/drawings/' in out:override(out,'application/vnd.openxmlformats-officedocument.drawing+xml')
 # Excel rejects inline validation lists longer than 255 characters.
 for name in ['AH','Lock-up','AH Compare','AH Compare Live','Chart Data','Live History']:
  doc=E.fromstring(parts[sheets[name]])
  for dv in doc.iter(q('dataValidation')):
   f=dv.find(q('formula1'))
   if f is not None and f.text and f.text.startswith('"') and len(f.text)>257:f.text='AHPairList' if name=='AH' else 'INDIRECT("\'Lock-up Data\'!$Y$8:$Y$393")'
  if name in ['AH Compare','Chart Data']:
   rows=doc.find(q('sheetData'))
   for row in list(rows):
    if int(row.get('r'))>2204:rows.remove(row)
  for f in doc.iter(q('f')):
   if f.text:
    f.text=f.text.replace('3004','2204')
    if name=='AH':f.text=f.text.replace('MIN(3000,','MIN(2200,')
  if name=='AH':
   cell=next(x for x in doc.iter(q('c')) if x.get('r')=='A5')
   for n in list(cell):cell.remove(n)
   cell.attrib.pop('t',None);cutoff=json.loads((root/'data/desk_chart_data.json').read_text())['peer']['asof'];E.SubElement(cell,q('f')).text=f'IF($E$4="Stored","Stored snapshot through {cutoff}","Bloomberg mode | prices / histories requested through today")'
  parts[sheets[name]]=E.tostring(doc,encoding='utf-8')
 names=wb.find(q('definedNames'));incoming_names=pwb.find(q('definedNames'))
 for n in list(names):
  if n.get('name','').startswith('PeerChart'):names.remove(n)
  elif n.text:n.text=n.text.replace('3004','2204')
 for n in incoming_names or []:names.append(deepcopy(n))
 parts['xl/workbook.xml']=E.tostring(wb,encoding='utf-8');parts['xl/_rels/workbook.xml.rels']=E.tostring(rel,encoding='utf-8');parts['[Content_Types].xml']=E.tostring(content,encoding='utf-8')
 add_caches(parts,sheets,root)
 dest=Path(dest);dest.parent.mkdir(exist_ok=True,parents=True)
 with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
  for path,raw in parts.items():z.writestr(path,raw)
 return dest
