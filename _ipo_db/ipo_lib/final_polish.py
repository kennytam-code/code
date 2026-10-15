"""Artifact-authored Database formatting and explicit presentation-note removal.

No Database data cell, formula, number format or source note is changed.
Native charts, Bloomberg request areas and calculations stay in their own parts.
"""
import base64,io,json,re,zipfile
from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as E
from patch_peer_workbook import q,maps
from reflow_monitors import nodes,value,put,sort,ci

def apply(parts,sheets,root):
 root=Path(root);layout=json.loads((root/'data/database_layout.json').read_text())
 with zipfile.ZipFile(io.BytesIO(base64.b64decode(layout['xlsx_base64']))) as z:
  _,_,ls=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
  template=E.fromstring(z.read(ls['Database']));source=E.fromstring(z.read('xl/styles.xml'))
 style=E.fromstring(parts['xl/styles.xml']);xfs=style.find(q('cellXfs'));tx=source.find(q('cellXfs'));tc=nodes(template);offset={}
 for name in ['fonts','fills','borders']:
  dest=style.find(q(name));offset[name]=len(dest)
  for item in source.find(q(name)):dest.append(deepcopy(item))
  dest.set('count',str(len(dest)))
 variants={};font_variants={}
 def format_cell(cell,ref,role):
  old=int(cell.get('s','0'));sample=tx[int(tc[ref].get('s','0'))];key=(old,ref,role)
  if key not in variants:
   n=deepcopy(xfs[old])
   if role in ['title','band','header']:
    for attr,group in [('fontId','fonts'),('fillId','fills'),('borderId','borders')]:n.set(attr,str(int(sample.get(attr,'0'))+offset[group]))
   else:
    # Keep source/calculation/conflict font colours and fills on every data cell.
    fid=int(n.get('fontId','0'));bold=ref.startswith('B');fkey=(fid,bold)
    if fkey not in font_variants:
     font=deepcopy(style.find(q('fonts'))[fid]);tmpl=source.find(q('fonts'))[int(sample.get('fontId','0'))]
     for tag in ['name','sz']:
      oldtag=font.find(q(tag))
      if oldtag is not None:font.remove(oldtag)
      font.append(deepcopy(tmpl.find(q(tag))))
     if bold and font.find(q('b')) is None:E.SubElement(font,q('b'))
     font_variants[fkey]=len(style.find(q('fonts')));style.find(q('fonts')).append(font)
    n.set('fontId',str(font_variants[fkey]));n.set('borderId',str(int(sample.get('borderId','0'))+offset['borders']))
   alignment=n.find(q('alignment'))
   if alignment is not None:n.remove(alignment)
   if sample.find(q('alignment')) is not None:n.append(deepcopy(sample.find(q('alignment'))))
   for attr in ['applyFont','applyFill','applyBorder','applyAlignment']:n.set(attr,'1')
   variants[key]=len(xfs);xfs.append(n)
  cell.set('s',str(variants[key]))
 doc=E.fromstring(parts[sheets['Database']]);dn=nodes(doc)
 for a,c in dn.items():
  col=re.match('[A-Z]+',a)[0];row=int(re.search(r'\d+',a)[0])
  if row in [1,3,4] and a in tc:format_cell(c,a,{1:'title',3:'band',4:'header'}[row])
  elif row>=5 and col+'5' in tc:format_cell(c,col+'5','body')
 for row in doc.find(q('sheetData')):
  r=int(row.get('r'));row.set('ht',str({1:32,2:8,3:23,4:39}.get(r,29)));row.set('customHeight','1')
 newcols=template.find(q('cols'));cols=doc.find(q('cols'))
 for col in cols:
  i=int(col.get('min'))
  match=next((c for c in newcols if int(c.get('min'))<=i<=int(c.get('max'))),None)
  if match is not None and i<=18:col.set('width',match.get('width'));col.set('customWidth','1')
 for view in doc.iter(q('sheetView')):view.set('zoomScale','90');view.set('showGridLines','0')
 for addr in ['A1','A2']:put(doc,addr,v='',style=dn[addr].get('s'))
 for row in doc.find(q('sheetData')):
  if row.get('r') in ['1','2']:row.set('hidden','1')
 sort(doc);parts[sheets['Database']]=E.tostring(doc)
 for n in ['fonts','cellXfs']:style.find(q(n)).set('count',str(len(style.find(q(n)))))
 parts['xl/styles.xml']=E.tostring(style)
 # Addresses are presentation prose only. Never clear by text length: names,
 # filing details and business descriptions are data and must be preserved.
 clear={'Taxonomy':['A2'],'CS League':['A2'],'SM League':['A2'],'Scoring Stats':['A2'],'SizeBench':['A2'],'Verification':['A2']}
 for name,addresses in clear.items():
  if name not in sheets:continue
  doc=E.fromstring(parts[sheets[name]]);ns=nodes(doc)
  for a in addresses:
   if a in ns:
    assert ns[a].find(q('f')) is None,(name,a)
    put(doc,a,v='',style=ns[a].get('s'))
  sort(doc);parts[sheets[name]]=E.tostring(doc)
 doc=E.fromstring(parts[sheets['BBG Verify']]);ns=nodes(doc)
 for a,c in ns.items():
  if c.find(q('f')) is not None:continue
  text=value(c)
  if a.startswith('A') and (text.startswith('Orange =') or text.startswith('Values the audits changed')):put(doc,a,v='',style=c.get('s'))
  elif text.startswith('A. LISTING DATE AND DAY-1 CLOSE'):put(doc,a,v='LISTING DATE & DAY-1 CLOSE',style=c.get('s'))
  elif text.startswith('C. CORPORATE ACTIONS'):put(doc,a,v='CORPORATE ACTIONS',style=c.get('s'))
  elif text.startswith('D. DEAL SIZE'):put(doc,a,v='DEAL SIZE',style=c.get('s'))
 sort(doc);parts[sheets['BBG Verify']]=E.tostring(doc)
 # Keep old/press-only deals available to the Screener without occupying
 # the active opening view. Excel's row-outline control exposes them.
 doc=E.fromstring(parts[sheets['Pipeline']]);ns=nodes(doc)
 for row in doc.find(q('sheetData')):
  r=int(row.get('r'));stage=value(ns.get('C'+str(r)))
  if stage in ['Withdrawn','Postponed','Reported']:
   row.set('hidden','1');row.set('outlineLevel','1')
  if r>=6 and value(ns.get('B'+str(r))) and stage:row.set('ht','36');row.set('customHeight','1')
 props=doc.find(q('sheetPr'));outline=props.find(q('outlinePr')) if props is not None else None
 if outline is not None:outline.set('summaryBelow','1')
 sort(doc);parts[sheets['Pipeline']]=E.tostring(doc)
