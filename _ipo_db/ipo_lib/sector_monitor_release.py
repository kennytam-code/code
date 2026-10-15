"""Sector summaries and HTML-only lock-ups, preserving the native workbook.

The compact summary is Artifact-authored. Native package edits retain the
large workbook's Bloomberg requests, charts, comments and unrelated sheets.
"""
import base64,io,json,posixpath,re,zipfile
from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as E
from patch_peer_workbook import maps,q,R,P
from reflow_monitors import nodes,value,put,sort,ci,ec
from desk_release import SHEET_ORDER

REMOVED={'Lock-up','Lock-up Data','Lock Compare','Lock Matrix'}

def relpath(owner):
 return posixpath.dirname(owner)+'/_rels/'+posixpath.basename(owner)+'.rels'

def target(owner,t):
 return t.lstrip('/') if t.startswith('/') else posixpath.normpath(posixpath.join(posixpath.dirname(owner),t))

def remove_lockup(parts,sheets):
 wb,rels,_=maps(parts);sn=wb.find(q('sheets'));old=list(sn)
 removed={sheets[n] for n in REMOVED if n in sheets}
 ids={x.get('{'+R+'}id') for x in old if x.get('name') in REMOVED}
 for n in list(sn):
  if n.get('name') in REMOVED:sn.remove(n)
 for n in list(rels):
  if n.get('Id') in ids:rels.remove(n)
 new_index={i:list(sn).index(n) for i,n in enumerate(old) if n in list(sn)}
 names=wb.find(q('definedNames'))
 if names is not None:
  for n in list(names):
   local=n.get('localSheetId');expr=n.text or ''
   if (local is not None and int(local) not in new_index) or any("'"+s+"'!" in expr or s+'!' in expr for s in REMOVED):names.remove(n)
   elif local is not None:n.set('localSheetId',str(new_index[int(local)]))
 for view in wb.iter(q('workbookView')):view.set('activeTab','0');view.set('firstSheet','0')
 parts['xl/workbook.xml']=E.tostring(wb);parts['xl/_rels/workbook.xml.rels']=E.tostring(rels)
 # Delete exclusively owned chart, table and comment parts with their sheets.
 graph={}
 for p,raw in parts.items():
  if not p.endswith('.rels') or '/_rels/' not in p:continue
  owner=posixpath.normpath(posixpath.join(posixpath.dirname(p),'..',posixpath.basename(p)[:-5]))
  graph[owner]=[target(owner,n.get('Target')) for n in E.fromstring(raw) if n.get('TargetMode')!='External']
 pending=list(removed)
 while pending:
  for child in graph.get(pending.pop(),[]):
   if child not in removed:removed.add(child);pending.append(child)
 protected={child for owner,children in graph.items() if owner not in removed for child in children if child in removed}
 pending=list(protected)
 while pending:
  for child in graph.get(pending.pop(),[]):
   if child not in protected:protected.add(child);pending.append(child)
 removed-=protected
 removed|={relpath(p) for p in list(removed) if relpath(p) in parts}
 for p in removed:parts.pop(p,None)
 types=E.fromstring(parts['[Content_Types].xml'])
 for n in list(types):
  if (n.get('PartName') or '').lstrip('/') in removed:types.remove(n)
 parts['[Content_Types].xml']=E.tostring(types)
 for name in REMOVED:sheets.pop(name,None)
 # K:O was the removed lock-up chart's dedicated build; A:I owns A/H.
 doc=E.fromstring(parts[sheets['Chart Data']])
 for row in doc.find(q('sheetData')):
  for cell in list(row):
   if 11<=ci(re.match('[A-Z]+',cell.get('r'))[0])<=15:row.remove(cell)
 parts[sheets['Chart Data']]=E.tostring(doc)
 app='docProps/app.xml'
 if app in parts:
  d=E.fromstring(parts[app]);vt='{http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes}'
  for child in d:
   if child.tag.endswith('TitlesOfParts'):
    vector=child.find(vt+'vector')
    if vector is not None:
     for n in list(vector):
      if n.text in REMOVED:vector.remove(n)
     vector.set('size',str(len(vector)))
   if child.tag.endswith('HeadingPairs'):
    vec=child.find(vt+'vector')
    if vec is not None:
     for i,n in enumerate(vec):
      if n.find(vt+'lpstr') is not None and n.find(vt+'lpstr').text=='Worksheets':list(vec)[i+1].find(vt+'i4').text=str(len(sn))
  parts[app]=E.tostring(d)
 for name,p in sheets.items():
  for f in E.fromstring(parts[p]).iter(q('f')):
   assert not any("'"+s+"'!" in (f.text or '') or s+'!' in (f.text or '') for s in REMOVED),(name,f.text)

def apply(parts,sheets,root):
 root=Path(root);doc=E.fromstring(parts[sheets['AH']]);current=nodes(doc)
 assert value(current.get('J57'))!='Sector averages (equal weight)','Apply sector release once'
 table_rows=[int(a[1:]) for a in current if re.fullmatch(r'C\d+',a) and int(a[1:])>=8 and current.get('B'+a[1:]) is not None and current['B'+a[1:]].find(q('f')) is not None]
 first,last=min(table_rows),max(table_rows);sectors=sorted({value(current['C'+str(r)]) for r in table_rows if value(current['C'+str(r)])})
 assert len(sectors)<=12
 template=json.loads((root/'data/sector_summary_template.json').read_text())
 with zipfile.ZipFile(io.BytesIO(base64.b64decode(template['xlsx_base64']))) as z:new={p:z.read(p) for p in z.namelist()}
 _,_,ns=maps(new);layout=E.fromstring(new[ns['AH']]);ln=nodes(layout)
 styles=E.fromstring(parts['xl/styles.xml']);incoming=E.fromstring(new['xl/styles.xml']);offset={}
 for name in ['fonts','fills','borders','cellStyleXfs','cellXfs','dxfs','numFmts']:
  a=styles.find(q(name));b=incoming.find(q(name))
  if a is None:a=E.SubElement(styles,q(name),{'count':'0'})
  offset[name]=len(a)
  if name in ['cellXfs','numFmts'] or b is None:continue
  for n in b:a.append(deepcopy(n))
  a.set('count',str(len(a)))
 fmts=styles.find(q('numFmts'));nf={};nextid=max([163]+[int(x.get('numFmtId')) for x in fmts])+1
 for n in incoming.find(q('numFmts')) if incoming.find(q('numFmts')) is not None else []:
  copy=deepcopy(n);nf[int(n.get('numFmtId'))]=nextid;copy.set('numFmtId',str(nextid));fmts.append(copy);nextid+=1
 fmts.set('count',str(len(fmts)))
 for n in incoming.find(q('cellXfs')):
  copy=deepcopy(n)
  for attr,group in [('fontId','fonts'),('fillId','fills'),('borderId','borders'),('xfId','cellStyleXfs')]:copy.set(attr,str(int(copy.get(attr,'0'))+offset[group]))
  num=int(copy.get('numFmtId','0'));copy.set('numFmtId',str(nf.get(num,num)));styles.find(q('cellXfs')).append(copy)
 styles.find(q('cellXfs')).set('count',str(len(styles.find(q('cellXfs')))))
 parts['xl/styles.xml']=E.tostring(styles)
 # Keep the old same-date diagnostic in the existing hidden helper column.
 old=current.get('J60')
 if old is not None and old.find(q('f')) is not None:put(doc,'P60',v=value(old) or '',f=old.find(q('f')).text,style=old.get('s'))
 for row in doc.find(q('sheetData')):
  for cell in list(row):
   a=cell.get('r');r=int(re.search(r'\d+',a)[0]);col=ci(re.match('[A-Z]+',a)[0])
   if 57<=r<=74 and 10<=col<=15:row.remove(cell)
 merges=doc.find(q('mergeCells'))
 if merges is not None:
  for m in list(merges):
   a=m.get('ref').split(':')[0];r=int(re.search(r'\d+',a)[0]);col=ci(re.match('[A-Z]+',a)[0])
   if 57<=r<=74 and 10<=col<=15:merges.remove(m)
  merges.set('count',str(len(merges)))
 def add(addr,source,v=None,f=None):
  style=str(int(ln[source].get('s','0'))+offset['cellXfs']);put(doc,addr,v=v,f=f,style=style)
 for addr in ['J57']+[c+'59' for c in 'JKLMNO']:add(addr,addr,value(ln[addr]))
 put(doc,'J5',v='Sector averages',f='HYPERLINK("#\'AH\'!J57","Sector averages")',style=current['K28'].get('s'))
 def number(r,c):
  cell=current.get(c+str(r));v=value(cell)
  if cell is None or cell.get('t') in ['str','inlineStr','s','e'] or v in [None,'']:return None
  return float(v)
 total=61+len(sectors)
 for r,sector in [(60+i,s) for i,s in enumerate(sectors)]+[(total,'All sectors')]:
  is_total=r==total;source=67 if is_total else 60
  rows=table_rows if is_total else [i for i in table_rows if value(current['C'+str(i)])==sector]
  add('J'+str(r),'J'+str(source),sector)
  add('K'+str(r),'K'+str(source),len(rows),f'COUNTA($C${first}:$C${last})' if is_total else f'COUNTIF($C${first}:$C${last},J{r})')
  for out,inp in [('L','E'),('M','F'),('N','G'),('O','H')]:
   vals=[number(i,inp) for i in rows];vals=[x for x in vals if x is not None]
   formula=f'AVERAGE(${inp}${first}:${inp}${last})' if is_total else f'AVERAGEIF($C${first}:$C${last},$J{r},${inp}${first}:${inp}${last})'
   add(out+str(r),out+str(source),sum(vals)/len(vals) if vals else '—',f'IFERROR({formula},"—")')
 for cf in layout.findall(q('conditionalFormatting')):
  copy=deepcopy(cf);copy.set('sqref',f'N60:O{total}')
  for rule in copy:
   if rule.get('dxfId') is not None:rule.set('dxfId',str(int(rule.get('dxfId'))+offset['dxfs']))
   rule.set('priority',str(300+int(rule.get('priority','1'))))
  doc.append(copy)
 for row in doc.find(q('sheetData')):
  r=int(row.get('r'))
  if r==59:row.set('ht','30');row.set('customHeight','1')
 # A slightly wider sector label leaves the existing chart column boundaries intact.
 doc[:]=sorted(doc,key=lambda n:SHEET_ORDER.index(n.tag.split('}')[-1]));sort(doc);parts[sheets['AH']]=E.tostring(doc)
 notes=E.fromstring(parts[sheets['Notes']]);nn=nodes(notes)
 put(notes,'A71',v='A/H sector averages',style=nn['A71'].get('s'))
 put(notes,'B71',v='Equal-weight averages of available numeric pairs. Changes average each pair’s premium change in percentage points. Source follows AH E4. Lock-up analysis is in HTML.',style=nn['B71'].get('s'))
 parts[sheets['Notes']]=E.tostring(notes)
 remove_lockup(parts,sheets)

if __name__=='__main__':
 import sys
 root=Path(__file__).resolve().parent.parent
 with zipfile.ZipFile(sys.argv[1]) as z:parts={p:z.read(p) for p in z.namelist()}
 _,_,sheets=maps(parts);apply(parts,sheets,root)
 with zipfile.ZipFile(sys.argv[2],'w',zipfile.ZIP_DEFLATED) as z:
  for p,raw in parts.items():z.writestr(p,raw)
 print('Added reactive A/H sector averages; removed Excel lock-up sheets and owned parts')
