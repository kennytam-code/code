"""Compact Database presentation; preserve values, formulas and native objects."""
import base64,io,json,re,zipfile
from copy import deepcopy
import xml.etree.ElementTree as E
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,ci

def apply(parts,sheets,root):
 layout=json.loads((root/'data/database_desk_style.json').read_text())
 with zipfile.ZipFile(io.BytesIO(base64.b64decode(layout['xlsx_base64']))) as z:
  _,_,sm=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
  template=nodes(E.fromstring(z.read(sm['Database style'])));source=E.fromstring(z.read('xl/styles.xml'))
 style=E.fromstring(parts['xl/styles.xml']);xfs=style.find(q('cellXfs'));tx=source.find(q('cellXfs'));offset={}
 for group in ['fonts','fills','borders']:
  dest=style.find(q(group));offset[group]=len(dest)
  dest.extend(deepcopy(list(source.find(q(group)))));dest.set('count',str(len(dest)))
 doc=E.fromstring(parts[sheets['Database']]);variants={};fontvariants={}
 cells=nodes(doc)
 for address,label in {'A2':'PE / PS','I4':'Deal size\n(HK$m)','M4':'Final px\n(HK$)','Q4':'Mkt cap at IPO\n(HK$m)','S4':'Public sub\n(x)','V4':'Intl\nplacees','X4':'Mechanism /\nclawback'}.items():
  cell=cells[address]
  for child in list(cell):cell.remove(child)
  cell.set('t','inlineStr');E.SubElement(E.SubElement(cell,q('is')),q('t')).text=label
 for cell in doc.iter(q('c')):
  a=cell.get('r');r=int(re.search(r'\d+',a)[0]);col=re.match('[A-Z]+',a)[0];c=ci(col)
  if r<3:continue
  group=next(i for i,end in enumerate([8,18,34,56,67,75,82,1000],1) if c<=end)
  ref='A'+str(group) if r==3 else 'C1' if r==4 else 'E1' if col=='B' else 'D1'
  sample=tx[int(template[ref].get('s','0'))];old=int(cell.get('s','0'))
  align='center' if r==4 or (r>4 and col in ['G','X']) else 'left' if r==3 or cell.get('t') in ['inlineStr','str','s','e'] else 'right'
  key=(old,ref,align)
  if key not in variants:
   n=deepcopy(xfs[old])
   if r in [3,4]:
    for attr,groupname in [('fontId','fonts'),('fillId','fills'),('borderId','borders')]:n.set(attr,str(int(sample.get(attr,'0'))+offset[groupname]))
   else:
    fid=int(n.get('fontId','0'));fk=(fid,col=='B')
    if fk not in fontvariants:
     font=deepcopy(style.find(q('fonts'))[fid]);tmpl=source.find(q('fonts'))[int(sample.get('fontId','0'))]
     for tag in ['name','sz','b']:
      current=font.find(q(tag))
      if current is not None:font.remove(current)
      replacement=tmpl.find(q(tag))
      if replacement is not None:font.append(deepcopy(replacement))
     fontvariants[fk]=len(style.find(q('fonts')));style.find(q('fonts')).append(font)
    n.set('fontId',str(fontvariants[fk]));n.set('borderId',str(int(sample.get('borderId','0'))+offset['borders']))
   al=n.find(q('alignment'))
   if al is not None:n.remove(al)
   n.append(E.Element(q('alignment'),{'horizontal':align,'vertical':'center','wrapText':'1' if r==4 else '0'}))
   for attr in ['applyFont','applyFill','applyBorder','applyAlignment']:n.set(attr,'1')
   variants[key]=len(xfs);xfs.append(n)
  cell.set('s',str(variants[key]))
 for row in doc.find(q('sheetData')):
  r=int(row.get('r'))
  if r>=2:row.set('ht',str({2:22,3:21,4:38}.get(r,23)));row.set('customHeight','1')
 # Secondary fields remain accessible through native outline controls.
 hidden={3,6,10,11,12,14,15,16,18,29,34}
 widths={'A':10,'B':25,'C':16,'D':17,'E':28,'F':30,'G':13,'H':13,'I':15,'J':25,'K':12,'L':12,'M':12,'N':12,'O':12,'P':14,'Q':17,'R':40,'S':14,'T':14,'U':15,'V':14,'W':15,'X':24}
 cols=doc.find(q('cols'));new=[]
 for entry in cols:
  for c in range(int(entry.get('min')),int(entry.get('max'))+1):
   n=deepcopy(entry);n.set('min',str(c));n.set('max',str(c));col='';k=c
   while k:k,t=divmod(k-1,26);col=chr(65+t)+col
   if col in widths:n.set('width',str(widths[col]));n.set('customWidth','1')
   if c in hidden:n.set('hidden','1');n.set('outlineLevel','1')
   # User removed the shares version from the desk view. Keep its backing
   # cells in place so existing formula references do not shift.
   if c==26:n.set('hidden','1');n.attrib.pop('outlineLevel',None)
   new.append(n)
 cols[:]=new
 for cf in list(doc.findall(q('conditionalFormatting'))):
  for rule in list(cf):
   if rule.get('type')=='dataBar':cf.remove(rule)
  if not len(cf):doc.remove(cf)
 for v in doc.iter(q('sheetView')):v.set('zoomScale','90');v.set('showGridLines','0')
 for group in ['fonts','cellXfs']:style.find(q(group)).set('count',str(len(style.find(q(group)))))
 parts[sheets['Database']]=E.tostring(doc);parts['xl/styles.xml']=E.tostring(style)
