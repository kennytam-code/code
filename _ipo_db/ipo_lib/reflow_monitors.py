"""Apply the small Artifact layout while preserving the existing monitor builds.

Peer display calculations move into the existing hidden Peer Chart build.
All controls remain visible, all observations and native chart bindings survive.
"""
import base64,io,json,re,zipfile
from copy import deepcopy
from datetime import date
import xml.etree.ElementTree as E
from openpyxl.formula.translate import Translator
from openpyxl.formula.tokenizer import Tokenizer
from patch_peer_workbook import maps,q,N,R,P

D='http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing'
C='http://schemas.openxmlformats.org/drawingml/2006/chart'
xd=lambda s:'{'+D+'}'+s
c=lambda s:'{'+C+'}'+s
def ec(n):
 s=''
 while n:n,r=divmod(n-1,26);s=chr(65+r)+s
 return s
def ci(s):
 n=0
 for v in s:n=26*n+ord(v)-64
 return n
def nodes(doc):return {n.get('r'):n for n in doc.iter(q('c'))}
def value(n):
 v=n.find(q('v')) if n is not None else None
 return v.text if v is not None else ''.join(x.text or '' for x in n.iter(q('t'))) if n is not None else ''
def serial(s):return (date.fromisoformat(s)-date(1899,12,30)).days if s else None
def place(doc,node):
 data=doc.find(q('sheetData'));r=int(re.search(r'\d+',node.get('r'))[0]);row=next((x for x in data if int(x.get('r'))==r),None)
 if row is None:row=E.SubElement(data,q('row'),{'r':str(r)})
 old=next((x for x in row if x.get('r')==node.get('r')),None)
 if old is not None:row.remove(old)
 row.append(node)
def put(doc,addr,v=None,f=None,style=None):
 n=E.Element(q('c'),{'r':addr})
 if style is not None:n.set('s',str(style))
 if f is not None:E.SubElement(n,q('f')).text=f.lstrip('=')
 if isinstance(v,str):
  n.set('t','str' if f else 'inlineStr')
  if f:E.SubElement(n,q('v')).text=v
  else:E.SubElement(E.SubElement(n,q('is')),q('t')).text=v
 elif v is not None:E.SubElement(n,q('v')).text=str(v)
 elif f is not None:n.set('t','str');E.SubElement(n,q('v')).text=''
 place(doc,n);return n
def sort(doc):
 # ECMA-376 CT_Worksheet uses a sequence, not an unordered collection.
 # Inserting validations after pageMargins made Excel discard both monitor
 # worksheet parts even though their XML was well-formed.
 order='sheetPr dimension sheetViews sheetFormatPr cols sheetData sheetCalcPr sheetProtection protectedRanges scenarios autoFilter sortState dataConsolidate customSheetViews mergeCells phoneticPr conditionalFormatting dataValidations hyperlinks printOptions pageMargins pageSetup headerFooter rowBreaks colBreaks customProperties cellWatches ignoredErrors smartTags drawing legacyDrawing legacyDrawingHF picture oleObjects controls webPublishItems tableParts extLst'.split()
 unknown=[n.tag for n in doc if n.tag.split('}')[-1] not in order]
 assert not unknown,unknown
 doc[:]=sorted(doc,key=lambda n:order.index(n.tag.split('}')[-1]))
 data=doc.find(q('sheetData'));data[:]=sorted(data,key=lambda r:int(r.get('r')))
 assert len({r.get('r') for r in data})==len(data),'Duplicate worksheet rows'
 for row in data:
  row[:]=sorted(row,key=lambda n:ci(re.match('[A-Z]+',n.get('r'))[0]))
  assert len({n.get('r') for n in row})==len(row),'Duplicate cells in row '+row.get('r')
 cells=nodes(doc);dim=doc.find(q('dimension'))
 if dim is None:dim=E.Element(q('dimension'));doc.insert(1 if doc.find(q('sheetPr')) is not None else 0,dim)
 if cells:dim.set('ref','A1:'+ec(max(ci(re.match('[A-Z]+',a)[0]) for a in cells))+str(max(int(re.search(r'\d+',a)[0]) for a in cells)))
def drawing_path(parts,sp):
 rel=E.fromstring(parts[sp.replace('/worksheets/','/worksheets/_rels/')+'.rels'])
 p=next(n.get('Target') for n in rel if n.get('Type')==R+'/drawing')
 return p.lstrip('/') if p.startswith('/') else 'xl/drawings/'+p.rsplit('/',1)[-1]
def anchor(n,start,end):
 for tag,addr in [('from',start),('to',end)]:
  x=n.find(xd(tag))
  if x is not None:
   x.find(xd('col')).text=str(ci(re.match('[A-Z]+',addr)[0])-1);x.find(xd('row')).text=str(int(re.search(r'\d+',addr)[0])-1)
   x.find(xd('colOff')).text='0';x.find(xd('rowOff')).text='0'
 ext=n.find(xd('ext'))
 if ext is not None:ext.set('cx',str(1250*9525));ext.set('cy',str(350*9525))
def transfer_peer_formula(formula):
 # Every scalar input/output in the original visible build moves together.
 # Excel copy translation deliberately leaves $absolute cells in place, so it
 # is inappropriate for moving an entire build onto a different sheet.
 tokens=Tokenizer('='+formula).items
 for token in tokens:
  if token.type=='OPERAND' and token.subtype=='RANGE' and '!' not in token.value:
   def shift(m):
    if ci(m[2])<=12 and int(m[4])<=13:return m[1]+ec(ci(m[2])+13)+m[3]+m[4]
    return m[0]
   token.value=re.sub(r'(?<![A-Z0-9_])(\$?)([A-Z]+)(\$?)([0-9]+)(?![A-Z0-9_])',shift,token.value)
 return ''.join(t.value for t in tokens)

def reflow(parts,sheets,root):
 root=__import__('pathlib').Path(root)
 with zipfile.ZipFile(io.BytesIO(base64.b64decode(json.loads((root/'data/monitor_layout.json').read_text())['xlsx_base64']))) as z:incoming={p:z.read(p) for p in z.namelist()}
 _,_,layout_paths=maps(incoming)
 styles=E.fromstring(parts['xl/styles.xml']);source=E.fromstring(incoming['xl/styles.xml']);offset={}
 for group in ['fonts','fills','borders','cellStyleXfs','cellXfs','numFmts']:
  a=styles.find(q(group));b=source.find(q(group))
  if a is None:a=E.SubElement(styles,q(group),{'count':'0'})
  offset[group]=len(a)
  if group in ['cellXfs','numFmts']:continue
  for x in b if b is not None else []:a.append(deepcopy(x))
  a.set('count',str(len(a)))
 fm=styles.find(q('numFmts'));ids={};nid=max([163]+[int(x.get('numFmtId')) for x in fm])+1
 for x in source.find(q('numFmts')) or []:
  n=deepcopy(x);ids[int(x.get('numFmtId'))]=nid;n.set('numFmtId',str(nid));fm.append(n);nid+=1
 fm.set('count',str(len(fm)))
 for x in source.find(q('cellXfs')):
  n=deepcopy(x)
  for attr,group in [('fontId','fonts'),('fillId','fills'),('borderId','borders'),('xfId','cellStyleXfs')]:n.set(attr,str(int(n.get(attr,'0'))+offset[group]))
  old=int(n.get('numFmtId','0'));n.set('numFmtId',str(ids.get(old,old)));styles.find(q('cellXfs')).append(n)
 styles.find(q('cellXfs')).set('count',str(len(styles.find(q('cellXfs')))))
 shared=[''.join(n.itertext()) for n in E.fromstring(incoming['xl/sharedStrings.xml'])] if 'xl/sharedStrings.xml' in incoming else []
 def layout(name):
  doc=E.fromstring(incoming[layout_paths[name]])
  for n in doc.iter(q('c')):
   n.set('s',str(int(n.get('s','0'))+offset['cellXfs']))
   if n.get('t')=='s':
    v=shared[int(n.find(q('v')).text)];style=n.get('s');addr=n.get('r');n.clear();n.set('r',addr);n.set('s',style);n.set('t','inlineStr');E.SubElement(E.SubElement(n,q('is')),q('t')).text=v
  return doc
 # Paint the two price monitors from the same small Artifact-authored template.
 # Source values, request formulas, native tables and controls are preserved.
 for name in ['IPO Live','AH']:
  if name not in layout_paths:continue
  original=E.fromstring(parts[sheets[name]]);paint=layout(name);pn=nodes(paint)
  oldcols=original.find(q('cols'));extra=[deepcopy(n) for n in oldcols if int(n.get('min'))>=16]
  oldcols[:]=[deepcopy(n) for n in paint.find(q('cols'))]+extra
  for row in original.find(q('sheetData')):
   r=int(row.get('r'));pr=next((x for x in paint.find(q('sheetData')) if x.get('r')==str(min(r,80))),None)
   if pr is not None:
    for key in ['ht','customHeight']:
     if key in pr.attrib:row.set(key,pr.get(key))
   for n in row:
    col=re.match('[A-Z]+',n.get('r'))[0]
    if ci(col)>15:continue
    source=pn.get(col+str(min(r,80)))
    if source is not None:n.set('s',source.get('s','0'))
  sort(original);parts[sheets[name]]=E.tostring(original)
 peer=E.fromstring(parts[sheets['Peer Trades']]);old=nodes(peer);calc=E.fromstring(parts[sheets['Peer Chart']])
 # Move the original scalar display builds exactly once into N:Y.
 moved={}
 for addr,n in old.items():
  r=int(re.search(r'\d+',addr)[0]);col=re.match('[A-Z]+',addr)[0]
  if r>13 or ci(col)>12:continue
  newaddr=ec(ci(col)+13)+str(r);copy=deepcopy(n);copy.set('r',newaddr)
  f=copy.find(q('f'))
  if f is not None:f.text=transfer_peer_formula(f.text)
  place(calc,copy);moved[addr]=newaddr
 def peerrefs(f):
  return re.sub(r"'Peer Trades'!\$?([A-Z]+)\$?(\d+)",lambda m:"'Peer Chart'!$"+ec(ci(m[1])+13)+'$'+m[2] if int(m[2])<=13 else m[0],f)
 for name in ['Peer Chart','Peer Live']:
  doc=calc if name=='Peer Chart' else E.fromstring(parts[sheets[name]])
  for f in doc.iter(q('f')):f.text=peerrefs(f.text or '')
  if name!='Peer Chart':parts[sheets[name]]=E.tostring(doc)
 for original,target in [('B3','B3'),('H4','F3'),('K4','H3'),('H5','F4'),('K5','H4')]:
  n=nodes(calc)[moved[original]];v=value(n);v=float(v) if n.get('t') not in ['str','inlineStr','s'] and v else v
  put(calc,moved[original],v=v,f="'Peer Trades'!$"+re.match('[A-Z]+',target)[0]+'$'+re.search(r'\d+',target)[0],style=n.get('s'))
 visible=layout('Peer Trades');new=nodes(visible)
 def copy_value(source,addr,f=None):
  n=deepcopy(source);n.set('r',addr);n.set('s',new[addr].get('s','0') if addr in new else new['B8'].get('s','0'))
  if f is not None:
   oldf=n.find(q('f'))
   if oldf is not None:n.remove(oldf)
   n.insert(0,E.Element(q('f')));n.find(q('f')).text=f
  place(visible,n)
 for a,b in [('B3','B3'),('H4','F3'),('K4','H3'),('H5','F4'),('K5','H4')]:copy_value(old[a],b)
 for oldaddr,newaddr in [('A6','B4'),('A9','B7'),('A10','C7'),('B4','B8'),('E4','C8'),('D9','B9'),('D10','C9'),('F9','B10'),('F10','C10'),('G9','B11'),('G10','C11'),('I9','B12'),('I10','C12'),('B11','B13'),('E11','C13'),('K9','F8')]:copy_value(old[oldaddr],newaddr,"'Peer Chart'!$"+re.match('[A-Z]+',moved[oldaddr])[0]+'$'+re.search(r'\d+',moved[oldaddr])[0])
 # Product is its own field; remove repeated generic explanatory text.
 put(visible,'B4',v=value(old['A6']).split(' | ')[0],f='IFERROR(INDEX(\'Peer Data\'!$V$3:$V$37,MATCH($B$3,\'Peer Data\'!$S$3:$S$37,0)),"")',style=new['B4'].get('s'))
 pc=nodes(calc);first=int(float(value(pc['J3']) or 0));last=max((int(re.search(r'\d+',a)[0]) for a,n in pc.items() if re.fullmatch('D[0-9]+',a) and n.get('t')!='e' and value(n)),default=0)
 put(visible,'F10',v=float(value(pc['A'+str(first)])) if first else '',f='IFERROR(INDEX(\'Peer Chart\'!$A$5:$A$3004,\'Peer Chart\'!$J$3-4),"")',style=new['F10'].get('s'))
 put(visible,'F11',v=float(value(pc['A'+str(last)])) if last else '',f='IFERROR(LOOKUP(2,1/(ISNUMBER(\'Peer Chart\'!$D$5:$D$3004)),\'Peer Chart\'!$A$5:$A$3004),"")',style=new['F11'].get('s'))
 put(visible,'B14',v='',f='IF(\'Peer Chart\'!$O$5>\'Peer Chart\'!$R$5,"Start is after end",IF(\'Peer Chart\'!$J$3=0,"History unavailable",""))',style=new['B4'].get('s'))
 dvs=E.SubElement(visible,q('dataValidations'),{'count':'3'})
 for source,target in [('B3','B3'),('H4','F3'),('K4','H3')]:
  dv=deepcopy(next(x for x in peer.iter(q('dataValidation')) if x.get('sqref')==source));dv.set('sqref',target);dvs.append(dv)
 d=peer.find(q('drawing'));visible.append(deepcopy(d))
 sort(visible);sort(calc);parts[sheets['Peer Trades']]=E.tostring(visible);parts[sheets['Peer Chart']]=E.tostring(calc)
 dp=drawing_path(parts,sheets['Peer Trades']);drawing=E.fromstring(parts[dp]);anchor(list(drawing)[0],'A16','D33');anchor(list(drawing)[1],'D16','H33');parts[dp]=E.tostring(drawing)
 # Lock-up calculations already live in hidden helpers P onward.
 lock=E.fromstring(parts[sheets['Lock-up']]);old=nodes(lock);visible=layout('Lock-up');new=nodes(visible)
 # The style template extends to row 80. Replace its empty roster rows before
 # grafting the existing records, rather than writing a second row 55..80.
 data=visible.find(q('sheetData'));data[:]=[r for r in data if int(r.get('r'))<55]
 for row in lock.find(q('sheetData')):
  r=int(row.get('r'))
  if r>=55:visible.find(q('sheetData')).append(deepcopy(row))
  else:
   for n in row:
    if ci(re.match('[A-Z]+',n.get('r'))[0])>=16:place(visible,deepcopy(n))
 lockmoves={'B32':'B30','B33':'E30','B34':'H30','B35':'K30','B37':'B33','B38':'E33'}
 for source,target in [('B4','B4'),('E4','E4'),*lockmoves.items(),('A8','B8'),('A22','D8'),('A14','E8'),('A18','F8'),('A23','J8'),('A25','L8')]:
  n=deepcopy(old[source]);n.set('r',target);n.set('s',new[target].get('s'));place(visible,n)
 def local(f):return re.sub(r'(?<![A-Z0-9_])\$?(B)\$?(32|33|34|35|37|38)(?![0-9])',lambda m:'$'+re.match('[A-Z]+',lockmoves[m[1]+m[2]])[0]+'$'+re.search(r'\d+',lockmoves[m[1]+m[2]])[0],f)
 for f in visible.iter(q('f')):f.text=local(f.text or '')
 for name in ['Lock Compare']:
  doc=E.fromstring(parts[sheets[name]])
  for f in doc.iter(q('f')):
   f.text=re.sub(r"'Lock-up'!\$?([A-Z]+)\$?(\d+)",lambda m:"'Lock-up'!$"+re.match('[A-Z]+',lockmoves[m[1]+m[2]])[0]+'$'+re.search(r'\d+',lockmoves[m[1]+m[2]])[0] if m[1]+m[2] in lockmoves else m[0],f.text or '')
  parts[sheets[name]]=E.tostring(doc)
 events=[e for e in json.loads((root/'data/batches/lockup_events.json').read_text())['events'] if e['category']=='Cornerstone' and e['date_basis']!='No cornerstone tranche'];end=54+len(events)
 code=value(old['B4']).zfill(4);selected=next((e for e in events if e['code']==code and serial(e.get('last_day_locked'))==float(value(old['A22']) or 0)),None)
 deals={d['code']:d for d in json.loads((root/'data/deals.json').read_text())['deals']};deal=deals.get(code,{})
 put(visible,'A8',v=code,f='IFERROR(IF($B$4="","",TEXT(VALUE($B$4),"0000")),"")',style=new['A8'].get('s'))
 put(visible,'C8',v=serial(deal.get('ipo_date')),f=f'IFERROR(IF(INDEX(\'Lock-up Data\'!$AA$8:$AA${8+len(events)},$P$7-7)>0,INDEX(\'Lock-up Data\'!$AA$8:$AA${8+len(events)},$P$7-7),""),"")',style=new['C8'].get('s'))
 for target,source,key in [('G8','I','cornerstone_pct'),('H8','J','since_ipo_pct'),('I8','K','deal_size_hkdm')]:
  v=deal.get(key);v=v/100 if v is not None and target!='I8' else v
  lookup=f'INDEX(${source}$55:${source}${end},$P$7-7)';put(visible,target,v=v,f=f'IFERROR(IF({lookup}="","",{lookup}),"")',style=new[target].get('s'))
 cutoff=json.loads((root/'data/desk_chart_data.json').read_text())['peer']['asof'];put(visible,'K8',v=serial(cutoff),style=new['K8'].get('s'))
 for tag in ['dataValidations','drawing','tableParts','legacyDrawing']:
  n=lock.find(q(tag))
  if n is not None:visible.append(deepcopy(n))
 for dv in visible.iter(q('dataValidation')):
  dv.set('sqref',lockmoves.get(dv.get('sqref'),dv.get('sqref')))
 cols=visible.find(q('cols'))
 for n in lock.find(q('cols')):
  if int(n.get('min'))>=16:cols.append(deepcopy(n))
 # Return colours are restricted to meaningful numeric outputs.
 dxfs=styles.find(q('dxfs'))
 if dxfs is None:dxfs=E.SubElement(styles,q('dxfs'),{'count':'0'})
 base=len(dxfs)
 for color in ['217346','B53939']:
  n=E.SubElement(dxfs,q('dxf'));E.SubElement(E.SubElement(n,q('font')),q('color'),{'rgb':'FF'+color})
 dxfs.set('count',str(len(dxfs)))
 def colours(doc,rng):
  cf=E.Element(q('conditionalFormatting'),{'sqref':rng})
  for i,op in enumerate(['greaterThan','lessThan']):
   rule=E.SubElement(cf,q('cfRule'),{'type':'cellIs','dxfId':str(base+i),'priority':str(i+1),'operator':op});E.SubElement(rule,q('formula')).text='0'
  pos=next((i for i,n in enumerate(doc) if n.tag in [q('dataValidations'),q('drawing')]),len(doc));doc.insert(pos,cf)
 colours(visible,'E8:H8')
 peerout=E.fromstring(parts[sheets['Peer Trades']]);colours(peerout,'B11:C12 F8');parts[sheets['Peer Trades']]=E.tostring(peerout)
 sort(visible);parts[sheets['Lock-up']]=E.tostring(visible)
 dp=drawing_path(parts,sheets['Lock-up']);drawing=E.fromstring(parts[dp]);anchor(list(drawing)[0],'A11','M26');anchor(list(drawing)[1],'A36','M51');parts[dp]=E.tostring(drawing)
 for path,raw in list(parts.items()):
  if not path.startswith('xl/charts/') or not path.endswith('.xml'):continue
  chart=E.fromstring(raw);changed=False
  for f in chart.iter(c('f')):
   if f.text and f.text.startswith("'Lock-up'!"):
    updated=local(f.text);changed|=updated!=f.text;f.text=updated
  if changed:parts[path]=E.tostring(chart)
 parts['xl/styles.xml']=E.tostring(styles)

def patch_file(source,dest,root):
 with zipfile.ZipFile(source) as z:parts={p:z.read(p) for p in z.namelist()}
 _,_,sheets=maps(parts);reflow(parts,sheets,root)
 from fix_monitor_requests import apply as requests
 from adjust_ah_charts import apply
 from combine_ah_benchmark import apply as benchmark
 root=__import__('pathlib').Path(root);requests(parts,sheets,root);apply(parts,sheets,root);benchmark(parts,sheets,root)
 from desk_release import apply as finish
 finish(parts,sheets,root)
 with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
  for p,raw in parts.items():z.writestr(p,raw)
if __name__=='__main__':
 import sys
 patch_file(sys.argv[1],sys.argv[2],__import__('pathlib').Path(__file__).resolve().parent.parent);print('Reflowed Lock-up and Peer Trades without merged cells')
