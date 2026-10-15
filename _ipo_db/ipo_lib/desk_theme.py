"""Apply Artifact-authored presentation only; retain all cell and chart data."""
import base64,io,json,re,zipfile,xml.etree.ElementTree as E
from copy import deepcopy
from pathlib import Path
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value,ci,put,sort,place

SCREEN_MOVES={'H8':'F7','H9':'F8','H12':'F10','H13':'F11','H14':'F12','H15':'F13','H16':'F14'}
SCREEN_LABELS={'A4':'','A6':'Field','B6':'Database','C6':'Override','D6':'','A15':'Filters','B15':'',
 'E6':'Selected deal','E7':'Size percentile','E8':'Size bucket','E10':'Day-1 return','E11':'1-month return','E12':'Public sub (x)','E13':'Cornerstone %','E14':'Sponsors'}
SCREEN_CLEARS=['G'+str(r) for r in range(7,17)]+['H7','H11']

def apply(parts,sheets,root):
 cfg=json.loads((Path(root)/'data/desk_theme.json').read_text())
 with zipfile.ZipFile(io.BytesIO(base64.b64decode(cfg['xlsx_base64']))) as z:
  _,_,ss=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
  src=E.fromstring(z.read('xl/styles.xml'));sample=nodes(E.fromstring(z.read(ss['Desk theme'])))
 styles=E.fromstring(parts['xl/styles.xml']);xfs=styles.find(q('cellXfs'));offset={}
 for group in ['fonts','fills','borders']:
  dest=styles.find(q(group));offset[group]=len(dest)
  for item in src.find(q(group)):dest.append(deepcopy(item))
  dest.set('count',str(len(dest)))
 variants={};fonts={};nfmap={}
 numfmts=styles.find(q('numFmts'))
 if numfmts is None:numfmts=E.Element(q('numFmts'),{'count':'0'});styles.insert(0,numfmts)
 for nf in src.find(q('numFmts')) if src.find(q('numFmts')) is not None else []:
  match=next((x for x in numfmts if x.get('formatCode')==nf.get('formatCode')),None)
  if match is None:
   match=deepcopy(nf);match.set('numFmtId',str(max([163]+[int(x.get('numFmtId')) for x in numfmts])+1));numfmts.append(match)
  nfmap[int(nf.get('numFmtId'))]=int(match.get('numFmtId'))
 numfmts.set('count',str(len(numfmts)))
 def style(cell,role='body',fill=False,color=False,wrap=None):
  old=int(cell.get('s','0'));key=(old,role,fill,color,wrap)
  if key not in variants:
   n=deepcopy(xfs[old]);t=src.find(q('cellXfs'))[int(sample['A'+str(cfg['roles'][role])].get('s','0'))]
   fid=int(n.get('fontId','0'));fk=(fid,role,color)
   if fk not in fonts:
    f=deepcopy(styles.find(q('fonts'))[fid]);tf=src.find(q('fonts'))[int(t.get('fontId','0'))]
    for tag in ['name','sz']+(['b'] if role in ['title','header','section','minor','key','soft'] else [])+(['color'] if color else []):
     for e in list(f.findall(q(tag))):f.remove(e)
     if tf.find(q(tag)) is not None:f.append(deepcopy(tf.find(q(tag))))
    fonts[fk]=len(styles.find(q('fonts')));styles.find(q('fonts')).append(f)
   n.set('fontId',str(fonts[fk]))
   if fill:n.set('fillId',str(int(t.get('fillId','0'))+offset['fills']))
   if role in ['header','section','input','minor','soft','hidden']:n.set('borderId',str(int(t.get('borderId','0'))+offset['borders']))
   if role=='hidden':n.set('numFmtId',str(nfmap.get(int(t.get('numFmtId','0')),int(t.get('numFmtId','0')))));n.set('applyNumberFormat','1')
   a=n.find(q('alignment'))
   if a is None:a=E.SubElement(n,q('alignment'))
   a.set('vertical','center')
   if wrap is not None:a.set('wrapText','1' if wrap else '0')
   for attr in ['applyFont','applyFill','applyBorder','applyAlignment']:n.set(attr,'1')
   variants[key]=len(xfs);xfs.append(n)
  cell.set('s',str(variants[key]))
 def plain(cell):
  fill=styles.find(q('fills'))[int(xfs[int(cell.get('s','0'))].get('fillId','0'))];p=fill.find(q('patternFill'))
  if p is None or p.get('patternType') in [None,'none']:return True
  fg=p.find(q('fgColor'));return p.get('patternType')=='solid' and fg is not None and fg.get('rgb','')[-6:] in ['FFFFFF','F2F2F2','F3F6F8','F5F7F9']
 def width(doc,col,w):
  cols=doc.find(q('cols'))
  for node in cols if cols is not None else []:
   if int(node.get('min'))==int(node.get('max'))==ci(col):node.set('width',str(w));node.set('customWidth','1')
 targets={'IPO Live','AH','Peer Trades','Screener','Pipeline','CS League','SM League','Taxonomy','Notes','BBG Verify','Scoring Stats','SizeBench','Verification'}
 for name in targets & set(sheets):
  doc=E.fromstring(parts[sheets[name]]);cs=nodes(doc);monitor=name in ['IPO Live','AH','Peer Trades'];title=2 if monitor else 1
  for addr,c in cs.items():
   col=re.match('[A-Z]+',addr)[0];r=int(re.search(r'\d+',addr)[0]);n=ci(col)
   if name=='Peer Trades' and addr=='F8':continue
   if r==title:style(c,'title',color=True)
   elif monitor:
    maxcol=15 if name!='Peer Trades' else 8
    if n>maxcol:continue
    style(c)
    header=(name=='IPO Live' and (r==7 and n<=5 or r in [5,36] and 7<=n<=9) or name=='AH' and (r==7 and n<=8 or r==59 and 10<=n<=15) or name=='Peer Trades' and (r==7 and n<=3 or r==37 and n<=8))
    if header:style(c,'header',fill=True,color=True,wrap=True)
    body=(name=='IPO Live' and r>=8 and n<=5 or name=='AH' and 8<=r<=78 and n<=8 or name=='Peer Trades' and r>=38 and n<=8)
    if body and plain(c):style(c,'alternate' if r%2 else 'body',fill=True,wrap=n in ([2,3] if name=='IPO Live' else [3,4] if name=='AH' else [1,2,3]))
   elif name=='Screener':
    style(c)
    if 21<=r<=35 and n<=76:
     style(c,'alternate' if r%2 else 'body',fill=plain(c),wrap=col in ['B','D','E','F','G'])
    if r==20:style(c,'soft',fill=True,color=True,wrap=True)
    if r==19 and n<=8:style(c,'header',fill=True,color=True)
   elif name=='Pipeline':
    style(c)
    if r==5:style(c,'header',fill=True,color=True,wrap=True)
   else:
    style(c)
    hr=3 if name=='Taxonomy' else 4
    if name not in ['Notes','Scoring Stats'] and r==hr:style(c,'header',fill=True,color=True,wrap=True)
    elif r>hr and name!='Notes' and plain(c):style(c,'alternate' if r%2 else 'body',fill=True,wrap=col=='A' or name=='Taxonomy' and col in ['B','C','D'])
    if name in ['CS League','SM League'] and r>=5 and col=='A':style(c,'key',wrap=True)
  controls={'IPO Live':['B4','B5','H34'],'AH':['B4','E4','K28','K29','K30'],'Peer Trades':['B3','F3','H3','F4','H4'],'Screener':['B5','B16','B17','B18','D17','D18']}.get(name,[])
  if name=='Screener':controls+=['C'+str(r) for r in range(7,15)]
  for a in controls:
   if a in cs:style(cs[a],'input',fill=True,color=True)
  for a in {'IPO Live':['G2'],'AH':['J4','J27','J57'],'Peer Trades':['E7','A35'],'Screener':[]}.get(name,[]):
   if a in cs:style(cs[a],'minor',color=True)
  # Match the tab accent to the red-led desk views while preserving functional
  # colours on data/league/support tabs and all red/green performance formats.
  if name in ['IPO Live','AH','Peer Trades','Screener','Pipeline']:
   pr=doc.find(q('sheetPr'))
   if pr is not None:
    tc=pr.find(q('tabColor'))
    if tc is not None:tc.attrib.clear();tc.set('rgb','FFCB2125')
  for row in doc.find(q('sheetData')):
   r=int(row.get('r'));h=None
   if r==title:h=32
   elif name=='Screener' and 21<=r<=35:h=32
   elif name=='Screener' and r==20:h=41
   elif name in ['CS League','SM League'] and r>=5:
    length=len(value(cs.get('A'+str(r))));h=26 if length<45 else 39 if length<80 else 52
   elif name in ['CS League','SM League','BBG Verify','SizeBench','Verification'] and r==4:h=44
   elif name=='Taxonomy' and r>=4:h=43
   if h:row.set('ht',str(h));row.set('customHeight','1')
  for col,w in {'Screener':[('B',27),('D',17),('E',29),('F',31)],'CS League':[('A',45),('K',48)],'SM League':[('A',48),('R',48)],'Taxonomy':[('A',21),('B',32),('C',80),('D',32)],'Notes':[('A',30),('B',95)],'BBG Verify':[('A',26)]}.get(name,[]):width(doc,col,w)
  # User requested tab names to be the only page titles. Keep underlying row
  # addresses stable so Bloomberg zones, named ranges and chart anchors survive.
  title_cell=cs.get('A'+str(title))
  if title_cell is not None:
   assert title_cell.find(q('f')) is None
   put(doc,'A'+str(title),v='',style=title_cell.get('s'))
  hidden_rows=({1,2} if name=='Peer Trades' else {1,2,3}) if monitor else {1}
  if name in ['CS League','SM League','Taxonomy','Scoring Stats','SizeBench','Verification']:hidden_rows|={2}
  if name=='IPO Live':
   assert value(cs.get('G4')) in [None,''] and ('G4' not in cs or cs['G4'].find(q('f')) is None)
   put(doc,'G4',v=value(cs['G2']),style=cs['G2'].get('s'));put(doc,'G2',v='',style=cs['G2'].get('s'))
  if name=='Screener':
   hidden_rows|={3,4}
   for old,new in SCREEN_MOVES.items():
    assert value(cs.get(new)) in [None,''] and (new not in cs or cs[new].find(q('f')) is None),new
    dest=deepcopy(cs[old]);dest.set('r',new);place(doc,dest);cs[new]=dest
    cs[old]=put(doc,old,v='',style=cs[old].get('s'));style(dest,'body',fill=True,wrap=True)
   for addr in SCREEN_CLEARS:
    if addr in cs:
     assert cs[addr].find(q('f')) is None
     cs[addr]=put(doc,addr,v='',style=cs[addr].get('s'));style(cs[addr],'body',fill=True)
   for addr,label in SCREEN_LABELS.items():
    assert addr not in cs or cs[addr].find(q('f')) is None,addr
    cs[addr]=put(doc,addr,v=label,style=cs.get(addr,cs['A7']).get('s'))
   for addr in ['F6','E15','F15']:
    if addr not in cs:cs[addr]=put(doc,addr,v='',style=cs['A7'].get('s'))
   for r in range(7,15):
    for col in ['A','B']:style(cs[col+str(r)],'body',fill=True,wrap=True)
    style(cs['D'+str(r)],'hidden',fill=True,color=True)
   style(cs['G5'],'hidden',fill=True,color=True)
   # Remove the former merged selector and context-panel fills. These cells
   # are empty; the effective calculation column above remains intact.
   whitespace=['D5','E5','F5','H5','D6','E9','F9','E15','F15']
   whitespace += [col+str(r) for col in ['G','H'] for r in range(6,19)]
   whitespace += [col+str(r) for col in ['E','F'] for r in range(16,19)]
   for addr in whitespace:
    if addr in cs:
     assert value(cs[addr]) in [None,''] and cs[addr].find(q('f')) is None,addr
     style(cs[addr],'hidden',fill=True,color=True)
   for addr in ['A6','B6','C6','E6','F6','A15','B15','C15','D15']:style(cs[addr],'soft',fill=True,color=True,wrap=True)
   for addr in ['D6','E15','F15']:style(cs[addr],'body',fill=True,color=True)
   style(cs['B5'],'input',fill=True,color=True,wrap=True)
   for addr in ['E7','E8','E10','E11','E12','E13','E14']:style(cs[addr],'body',fill=True,color=True)
   merges=doc.find(q('mergeCells'))
   for m in list(merges):
    if m.get('ref') in ['A4:E4','B5:F5','G7:H7','G11:H11']:merges.remove(m)
   for ref in ['B5:C5','E6:F6']:E.SubElement(merges,q('mergeCell'),{'ref':ref})
   merges.set('count',str(len(merges)))
   for row in doc.find(q('sheetData')):
    r=int(row.get('r'))
    if 5<=r<=18:row.set('ht',str(44 if r==5 else 36 if r in [8,14] else 23 if r in [6,15] else 27));row.set('customHeight','1')
  for row in doc.find(q('sheetData')):
   if int(row.get('r')) in hidden_rows:row.set('hidden','1')
  for v in doc.iter(q('sheetView')):v.set('showGridLines','0')
  sort(doc)
  parts[sheets[name]]=E.tostring(doc)
 for group in ['fonts','fills','borders','cellXfs']:styles.find(q(group)).set('count',str(len(styles.find(q(group)))))
 parts['xl/styles.xml']=E.tostring(styles)
 # Native chart styles only: no series formulas, caches, axes, bounds or anchors.
 C='{http://schemas.openxmlformats.org/drawingml/2006/chart}';A='{http://schemas.openxmlformats.org/drawingml/2006/main}'
 for path,raw in list(parts.items()):
  if not(path.startswith('xl/charts/') and path.endswith('.xml')):continue
  d=E.fromstring(raw)
  bars={id(s) for group in d.iter(C+'barChart') for s in group.findall(C+'ser')}
  for i,ser in enumerate(d.iter(C+'ser')):
   sp=ser.find(C+'spPr')
   if sp is not None:
    for rgb in sp.iter(A+'srgbClr'):rgb.set('val',cfg['chart_colors'][i%len(cfg['chart_colors'])])
   if id(ser) in bars:
    # Bars retain their original series semantics; avoid red implying every bar fell.
    if sp is not None:
     for rgb in sp.iter(A+'srgbClr'):rgb.set('val','456984')
  for grid in d.iter(C+'majorGridlines'):
   for rgb in grid.iter(A+'srgbClr'):rgb.set('val',cfg['chart_grid'])
  parts[path]=E.tostring(d)
