"""Final desk outputs: fundamental estimates, compact charts and native safety.

All field expressions come from the user's Bloomberg examples. Native column
insertion updates source references before adding the new output cells.
"""
import re,json,zipfile,sys
from copy import deepcopy
import xml.etree.ElementTree as E
from openpyxl.formula.tokenizer import Tokenizer
from reflow_monitors import q,c,xd,ci,ec,nodes,value,put,place,sort,anchor,drawing_path
from patch_peer_workbook import maps,R,P

SHEET_ORDER='sheetPr dimension sheetViews sheetFormatPr cols sheetData sheetCalcPr sheetProtection protectedRanges scenarios autoFilter sortState dataConsolidate customSheetViews mergeCells phoneticPr conditionalFormatting dataValidations hyperlinks printOptions pageMargins pageSetup headerFooter rowBreaks colBreaks customProperties cellWatches ignoredErrors smartTags drawing legacyDrawing legacyDrawingHF picture oleObjects controls webPublishItems tableParts extLst'.split()

def moved_range(text,start,count):
 def move(m):
  col=ci(m[2]);return m[1]+ec(col+count if col>=start else col)+m[3]
 return re.sub(r'(?<![A-Za-z0-9_])(\$?)([A-Z]{1,3})(\$?[0-9]*)(?![A-Za-z0-9_])',move,text)

def moved_formula(text,sheet,start,count,local=False):
 if not text:return text
 if not local and sheet+'!' not in text and "'"+sheet+"'!" not in text:return text
 tokens=Tokenizer('='+text).items
 for t in tokens:
  if t.type!='OPERAND' or t.subtype!='RANGE':continue
  if '!' in t.value:
   prefix,ref=t.value.rsplit('!',1)
   if prefix.strip("'")==sheet:t.value=prefix+'!'+moved_range(ref,start,count)
  elif local and re.fullmatch(r'\$?[A-Z]{1,3}\$?[0-9]+(?::\$?[A-Z]{1,3}\$?[0-9]+)?',t.value):t.value=moved_range(t.value,start,count)
 return ''.join(t.value for t in tokens)

def insert_columns(parts,sheets,sheet,start,count):
 target=sheets[sheet]
 relpath=target.replace('/worksheets/','/worksheets/_rels/')+'.rels'
 related=[]
 if relpath in parts:
  import posixpath
  for rel in E.fromstring(parts[relpath]):
   if rel.get('Type','').endswith('/comments') or rel.get('Type','').endswith('/vmlDrawing'):
    dest=rel.get('Target');related.append(dest.lstrip('/') if dest.startswith('/') else posixpath.normpath(posixpath.join('xl/worksheets',dest)))
 for path in related:
  doc=E.fromstring(parts[path])
  for node in doc.iter():
   tag=node.tag.split('}')[-1]
   if tag=='comment':node.set('ref',moved_range(node.get('ref'),start,count))
   elif tag=='Column' and node.text is not None:
    n=int(node.text);node.text=str(n+count if n>=start-1 else n)
   elif tag=='Anchor' and node.text:
    coordinates=[int(x.strip()) for x in node.text.split(',')]
    for i in [0,4]:
     if coordinates[i]>=start-1:coordinates[i]+=count
    node.text=', '.join(map(str,coordinates))
  parts[path]=E.tostring(doc)
 for path,raw in list(parts.items()):
  if not path.endswith('.xml'):continue
  local=path==target
  if not local and sheet.encode() not in raw:continue
  if not (path.startswith('xl/worksheets/') or path.startswith('xl/charts/') or path=='xl/workbook.xml'):continue
  doc=E.fromstring(raw)
  for n in doc.iter():
   tag=n.tag.split('}')[-1]
   if tag in ['f','formula','formula1','formula2','definedName'] and n.text:n.text=moved_formula(n.text,sheet,start,count,local)
   if local:
    for attr in ['r','ref','sqref','activeCell','topLeftCell']:
     if attr in n.attrib and re.search('[A-Z]',n.get(attr)):n.set(attr,moved_range(n.get(attr),start,count))
    if tag=='col':
     a,b=int(n.get('min')),int(n.get('max'));n.set('min',str(a+count if a>=start else a));n.set('max',str(b+count if b>=start else b))
  if local:sort(doc)
  parts[path]=E.tostring(doc)

def set_child(parent,name,attrs):
 n=parent.find(c(name))
 if n is None:n=E.SubElement(parent,c(name))
 n.attrib.update(attrs);return n

def valuation_request(doc,row,ticker,query,raw,out,helper,field,direct=None):
 """Read the requested field, never a date/period from BQL metadata."""
 first=ci(raw);last=ec(first+7)
 header='0'
 for r in reversed(range(row,row+4)):
  for col in reversed(range(first,first+8)):
   header=f'IF(IFERROR(ISNUMBER(SEARCH("{field}",{ec(col)}{r})),FALSE),{col-first+1},{header})'
 put(doc,helper+str(row),v=0,f=header)
 result='"Unavailable"'
 for r in reversed(range(row,row+8)):
  ref=f'INDEX({raw}{r}:{last}{r},1,{helper}{row})'
  result=f'IF(IFERROR(ISNUMBER({ref}),FALSE),{ref},{result})'
 fallback='"Unavailable"'
 for r in reversed(range(row,row+8)):
  ref=ec(first+1)+str(r);fallback=f'IF(IFERROR(ISNUMBER({ref}),FALSE),{ref},{fallback})'
 fallback=f'IF(COUNTA({ec(first+2)}{row}:{last}{row+7})=0,{fallback},"Unavailable")'
 formula=f'IF(IFERROR(ISNUMBER({raw}{row}),FALSE),{raw}{row},IF({helper}{row}>0,{result},{fallback}))'
 if direct:formula=f'IF(IFERROR(ISNUMBER({direct}{row}),FALSE),{direct}{row},{formula})'
 put(doc,raw+str(row),f=f'IF({ticker}="","",BQL({ticker},"{query}"))')
 put(doc,out+str(row),v='Unavailable',f=formula)

def live_snapshot(parts,sheets,root):
 """A dated offline first view and independent Bloomberg mode for A/H."""
 path=root/'data/live_snapshot.json';data=json.loads(path.read_text()) if path.exists() else {'quotes':{},'asof':None}
 live=E.fromstring(parts[sheets['IPO Live']]);market=E.fromstring(parts[sheets['Market Data']]);ln=nodes(live);mn=nodes(market)
 put(live,'A4',v='Source',style=ln['A4'].get('s'));put(live,'B4',v='Stored',style=ln['B5'].get('s'))
 label=f'Snapshot {data["asof"]} · HKD' if data['asof'] else 'Stored quotes unavailable'
 put(live,'C4',v=label,f=f'IF($B$4="Bloomberg","Bloomberg live · HKD","{label}")',style=ln['A4'].get('s'))
 dv=live.find(q('dataValidations'));E.SubElement(E.SubElement(dv,q('dataValidation'),{'type':'list','allowBlank':'0','showErrorMessage':'1','sqref':'B4'}),q('formula1')).text='"Stored,Bloomberg"';dv.set('count',str(len(dv)))
 changes={};sectors={};subsectors={}
 from datetime import date
 for addr,old in ln.items():
  if not re.fullmatch('A[0-9]+',addr) or int(addr[1:])<8:continue
  r=int(addr[1:]);ticker=value(old)
  if not ticker or 'HK Equity' not in ticker:continue
  code=str(int(ticker.split()[0])).zfill(4);quote=data['quotes'].get(code,{})
  last=quote.get('last');previous=quote.get('previous_close');fresh=quote.get('quote_time','')[:10]==data['asof']
  change=last/previous-1 if fresh and last and previous else None
  put(market,'BS'+str(r),v=previous if fresh else None);put(market,'BT'+str(r),v=last);put(market,'BU'+str(r),v=quote.get('quote_time',''))
  put(market,'B'+str(r),v=previous if fresh else None,f=f'IF(\'IPO Live\'!$B$4="Bloomberg",IFERROR(BDP(\'IPO Live\'!$A{r},"PX_YEST_CLOSE"),""),BS{r})',style=mn['B'+str(r)].get('s'))
  put(live,'D'+str(r),v=last if last is not None else 'Unavailable',f=f'IF($A{r}="","",IF($B$4="Bloomberg",IFERROR(BDP($A{r},"LAST_PRICE"),"Unavailable"),IF(ISNUMBER(\'Market Data\'!BT{r}),\'Market Data\'!BT{r},"Unavailable")))',style=ln['D'+str(r)].get('s'))
  put(live,'E'+str(r),v=change,f=ln['E'+str(r)].find(q('f')).text,style=ln['E'+str(r)].get('s'))
  changes[r]=change
  if change is not None:
   sectors.setdefault(value(mn['C'+str(r)]),[]).append(change);subsectors.setdefault((value(mn['C'+str(r)]),value(mn['D'+str(r)])),[]).append(change)
 for r in list(range(6,15))+list(range(37,45)):
  group=value(ln.get('G'+str(r)));items=sectors.get(group,[]) if r<15 else subsectors.get((value(ln['H34']),group),[])
  for col,val in [('H',sum(items)/len(items) if items else '—'),('I',len(items))]:
   old=ln.get(col+str(r))
   if old is not None:put(live,col+str(r),v=val,f=old.find(q('f')).text,style=old.get('s'))
 # A/H's Bloomberg switch must never inherit the Live tab's stored mode.
 for addr,old in mn.items():
  if re.fullmatch('AD[0-9]+',addr) and old.find(q('f')) is not None:
   r=int(addr[2:]);put(market,addr,v=value(old),f=f'IF(AH!$E$4="Bloomberg",IFERROR(BDP(Q{r},"LAST_PRICE"),""),IF(AH!$E$4="Stored",AG{r},""))',style=old.get('s'))
 for name,doc in [('IPO Live',live),('Market Data',market)]:sort(doc);parts[sheets[name]]=E.tostring(doc)
 # Native chart caches are necessary when the file is viewed before recalculation.
 import posixpath
 dp=drawing_path(parts,sheets['IPO Live']);rels=E.fromstring(parts[dp.replace('/drawings/','/drawings/_rels/')+'.rels'])
 for rel in rels:
  target=rel.get('Target');p=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join('xl/drawings',target))
  if not p.startswith('xl/charts/'):continue
  doc=E.fromstring(parts[p])
  for ref in doc.iter(c('numRef')):
   f=ref.find(c('f'));cache=ref.find(c('numCache'))
   if f is None or cache is None:continue
   bounds=re.search(r'\$H\$(\d+):\$H\$(\d+)',f.text or '')
   if not bounds and 'LiveSubsectorChanges' in (f.text or ''):bounds=re.search(r'(\d+):(\d+)','37:44')
   if not bounds:continue
   for pt in list(cache.findall(c('pt'))):cache.remove(pt)
   a,b=map(int,bounds.groups());cache.find(c('ptCount')).set('val',str(b-a+1))
   for i,r in enumerate(range(a,b+1)):
    v=value(nodes(live).get('H'+str(r)))
    if isinstance(v,(int,float)) or isinstance(v,str) and re.fullmatch(r'-?\d+(?:\.\d+)?(?:e[+-]?\d+)?',v,re.I):E.SubElement(E.SubElement(cache,c('pt'),{'idx':str(i)}),c('v')).text=str(v)
  parts[p]=E.tostring(doc)

def premium_calendar_axis(doc):
 """One actual-date X axis shared by both premium and benchmark Y axes.

 Native Excel interpreted the named category timeline as text and drew one
 label per observation. XY series retain the same dates and observations;
 sharing the X axis also prevents different primary/secondary date bounds.
 """
 plot=doc.find('.//'+c('plotArea'));groups=plot.findall(c('lineChart'))
 if len(groups)!=2:return
 common=groups[0].findall(c('axId'))[0].get('val')
 for group in groups:
  group.tag=c('scatterChart')
  for node in list(group):
   if node.tag in [c('grouping'),c('marker'),c('smooth'),c('dropLines'),c('hiLowLines'),c('upDownBars')]:group.remove(node)
  E.SubElement(group,c('scatterStyle'),{'val':'line'})
  group.findall(c('axId'))[0].set('val',common)
  for ser in group.findall(c('ser')):
   ser.find(c('cat')).tag=c('xVal');ser.find(c('val')).tag=c('yVal')
  order='scatterStyle varyColors ser dLbls axId extLst'.split();group[:]=sorted(group,key=lambda n:order.index(n.tag.split('}')[-1]))
 for axis in list(plot.findall(c('dateAx'))):
  if axis.find(c('axId')).get('val')!=common:plot.remove(axis);continue
  axis.tag=c('valAx')
  for child in list(axis):
   if child.tag in [c(n) for n in ['auto','lblOffset','baseTimeUnit','majorUnit','majorTimeUnit','minorUnit','minorTimeUnit']]:axis.remove(child)
  set_child(axis,'numFmt',{'formatCode':'dd-mmm-yy','sourceLinked':'0'})
  set_child(axis,'numFmt',{'formatCode':'mmm-yy','sourceLinked':'0'})
  set_child(axis,'majorUnit',{'val':'90'})
  set_child(axis,'crosses',{'val':'min'})
 for axis in plot.findall(c('valAx')):
  if axis.find(c('axPos')).get('val') in ['l','r']:axis.find(c('crossAx')).set('val',common)
  for child in list(axis.findall(c('crossBetween'))):axis.remove(child)

def peer_calendar_axis(doc):
 """Let Excel choose date spacing for both short and multi-year windows."""
 plot=doc.find('.//'+c('plotArea'))
 for group in plot.findall(c('lineChart')):
  group.tag=c('scatterChart')
  for n in list(group):
   if n.tag in [c(x) for x in ['grouping','marker','smooth','dropLines','hiLowLines','upDownBars']]:group.remove(n)
  E.SubElement(group,c('scatterStyle'),{'val':'line'})
  for ser in group.findall(c('ser')):ser.find(c('cat')).tag=c('xVal');ser.find(c('val')).tag=c('yVal')
  order='scatterStyle varyColors ser dLbls axId extLst'.split();group[:]=sorted(group,key=lambda n:order.index(n.tag.split('}')[-1]))
 for axis in plot.findall(c('dateAx')):
  axis.tag=c('valAx')
  for child in list(axis):
   if child.tag in [c(n) for n in ['auto','lblOffset','baseTimeUnit','majorUnit','majorTimeUnit','minorUnit','minorTimeUnit']]:axis.remove(child)
  set_child(axis,'numFmt',{'formatCode':'d/m/yy','sourceLinked':'0'});set_child(axis,'crosses',{'val':'min'})
 for axis in plot.findall(c('valAx')):
  if axis.find(c('axPos')).get('val')=='b':set_child(axis,'numFmt',{'formatCode':'d/m/yy','sourceLinked':'0'})
  for child in list(axis.findall(c('crossBetween'))):axis.remove(child)

def compact_lock_roster(parts,sheets,deals):
 def shift(ref):
  def cell(m):
   row=int(m[4]);return m[1]+m[2]+m[3]+str(row-17 if ci(m[2])<=13 and row>=54 else row)
  return re.sub(r'(\$?)([A-Z]{1,3})(\$?)([0-9]+)',cell,ref)
 lock=E.fromstring(parts[sheets['Lock-up']]);moving=[]
 for row in lock.find(q('sheetData')):
  for n in list(row):
   if int(row.get('r'))>=54 and ci(re.match('[A-Z]+',n.get('r'))[0])<=13:
    row.remove(n);n.set('r',shift(n.get('r')));moving.append(n)
 for n in moving:place(lock,n)
 lookup={d['code']:d for d in deals};ln=nodes(lock)
 put(lock,'D37',v='CS investors',style=ln['D37'].get('s'))
 for row in lock.find(q('sheetData')):
  r=int(row.get('r'))
  if r>=38 and 'A'+str(r) in ln:
   code=value(ln['A'+str(r)]).zfill(4);deal=lookup.get(code,{})
   if deal:put(lock,'D'+str(r),v=deal.get('cornerstone_n',len(deal.get('cornerstone_investors',[]))),style=ln.get('A'+str(r)).get('s'))
   row.set('ht','28');row.set('customHeight','1')
 parts[sheets['Lock-up']]=E.tostring(lock)
 for path,raw in list(parts.items()):
  if not path.endswith('.xml') or not (path.startswith('xl/worksheets/') or path=='xl/workbook.xml' or path.startswith('xl/charts/') or path.startswith('xl/tables/')):continue
  local=path==sheets['Lock-up'];table=path.startswith('xl/tables/') and b'LockupEvents' in raw
  if not local and not table and b'Lock-up' not in raw:continue
  doc=E.fromstring(raw)
  for node in doc.iter():
   tag=node.tag.split('}')[-1]
   if tag in ['f','formula','formula1','formula2','definedName'] and node.text:
    tokens=Tokenizer('='+node.text).items
    for t in tokens:
     if t.type=='OPERAND' and t.subtype=='RANGE':
      if '!' in t.value:
       prefix,ref=t.value.rsplit('!',1)
       if prefix.strip("'")=='Lock-up':t.value=prefix+'!'+shift(ref)
      elif local:t.value=shift(t.value)
    node.text=''.join(t.value for t in tokens)
   if tag in ['autoFilter','table'] and (local or table) and 'ref' in node.attrib:node.set('ref',shift(node.get('ref')))
  if table:
   columns=doc.find(q('tableColumns'))
   if columns is not None:list(columns)[3].set('name','CS investors')
  if local:sort(doc)
  parts[path]=E.tostring(doc)

def chart_style(parts,sheets):
 a='http://schemas.openxmlformats.org/drawingml/2006/main';aq=lambda s:'{'+a+'}'+s
 palette=['D71920','333333','888888','315B7D','A58A64']
 for name in ['IPO Live','AH','Lock-up','Peer Trades','Screener']:
  dp=drawing_path(parts,sheets[name]);draw=E.fromstring(parts[dp]);drp=dp.replace('/drawings/','/drawings/_rels/')+'.rels';rels=E.fromstring(parts[drp]);paths={n.get('Id'):n.get('Target') for n in rels}
  for n in draw:
   chart=n.find('.//'+c('chart'))
   if chart is None:continue
   target=paths[chart.get('{'+R+'}id')];path=target.lstrip('/') if target.startswith('/') else 'xl/charts/'+target.rsplit('/',1)[-1]
   doc=E.fromstring(parts[path]);set_child(doc,'roundedCorners',{'val':'0'})
   title=doc.find('.//'+c('title'))
   if title is not None:
    for run in title.iter(aq('r')):
     if run.find(aq('rPr')) is None:run.insert(0,E.Element(aq('rPr'),{'sz':'1100','b':'0'}))
    for prop in list(title.iter(aq('rPr')))+list(title.iter(aq('defRPr')))+list(title.iter(aq('endParaRPr'))):prop.set('sz','1100');prop.set('b','0')
    if name=='Lock-up':
     texts=list(title.iter(aq('t')))
     if texts:
      texts[0].text='Expiry return · day 0 = 0%' if len(list(doc.iter(c('ser'))))==2 else 'Expiry comparison · day 0 = 0%'
      for t in texts[1:]:t.text=''
    # Native Excel's default auto-title size differs across chart types.
    tx=title.find(c('txPr'))
    if tx is None:
     tx=E.SubElement(title,c('txPr'));E.SubElement(tx,aq('bodyPr'));E.SubElement(tx,aq('lstStyle'));para=E.SubElement(tx,aq('p'));E.SubElement(E.SubElement(para,aq('pPr')),aq('defRPr'),{'sz':'1100'})
   if name=='AH' and b'AHMarketPremium' in parts[path]:premium_calendar_axis(doc)
   if name=='Peer Trades':peer_calendar_axis(doc)
   if name=='IPO Live':
    for bar in doc.iter(c('barDir')):bar.set('val','bar')
    for axis in doc.iter(c('catAx')):axis.find(c('axPos')).set('val','l')
    for axis in doc.iter(c('valAx')):axis.find(c('axPos')).set('val','b')
   sp=doc.find(c('spPr'))
   if sp is None:sp=E.SubElement(doc,c('spPr'))
   for old in list(sp):sp.remove(old)
   E.SubElement(sp,aq('noFill'));E.SubElement(E.SubElement(sp,aq('ln')),aq('noFill'))
   for i,ser in enumerate(doc.iter(c('ser'))):
    ss=ser.find(c('spPr'))
    if ss is None:ss=E.Element(c('spPr'));ser.insert(3,ss)
    ln=ss.find(aq('ln'))
    if ln is None:ln=E.SubElement(ss,aq('ln'))
    ln.set('w','15875')
    for old in list(ln):ln.remove(old)
    color='526779' if name=='IPO Live' else palette[i%len(palette)]
    if name=='AH' and b'AHMarketPremium' in parts[path]:color=['D71920','888888','333333'][i%3]
    E.SubElement(E.SubElement(ln,aq('solidFill')),aq('srgbClr'),{'val':color})
    if name=='IPO Live':
     fill=ss.find(aq('solidFill'))
     if fill is not None:ss.remove(fill)
     E.SubElement(E.SubElement(ss,aq('solidFill')),aq('srgbClr'),{'val':'526779'})
    smooth=ser.find(c('smooth'))
    if smooth is not None:smooth.set('val','0')
   for axis in list(doc.iter(c('dateAx')))+list(doc.iter(c('catAx')))+list(doc.iter(c('valAx'))):
    set_child(axis,'majorTickMark',{'val':'none'});set_child(axis,'minorTickMark',{'val':'none'})
    if axis.tag==c('dateAx'):
     set_child(axis,'numFmt',{'formatCode':'mmm-yy','sourceLinked':'0'});set_child(axis,'majorUnit',{'val':'2'});set_child(axis,'majorTimeUnit',{'val':'months'});set_child(axis,'tickLblPos',{'val':'low'})
    if axis.tag==c('valAx') and axis.find(c('axPos')).get('val')=='l':set_child(axis,'crosses',{'val':'min'})
    if name=='Lock-up' and axis.tag==c('catAx'):set_child(axis,'tickLblSkip',{'val':'10'});set_child(axis,'tickLblPos',{'val':'low'})
    grid=axis.find(c('majorGridlines'))
    if grid is not None:
     for old in list(grid):grid.remove(old)
     gsp=E.SubElement(grid,c('spPr'));gl=E.SubElement(gsp,aq('ln'),{'w':'6350'});E.SubElement(E.SubElement(gl,aq('solidFill')),aq('srgbClr'),{'val':'D9E0E5'})
    tx=axis.find(c('txPr'))
    if tx is not None:
     for b in tx.iter(aq('bodyPr')):b.attrib.pop('rot',None)
     for d in tx.iter(aq('defRPr')):d.set('sz','900')
   # Native chart child sequences also matter to Excel.
   ranks={
    'dateAx':'axId scaling delete axPos majorGridlines minorGridlines title numFmt majorTickMark minorTickMark tickLblPos spPr txPr crossAx crosses crossesAt auto lblOffset baseTimeUnit majorUnit majorTimeUnit minorUnit minorTimeUnit extLst',
    'catAx':'axId scaling delete axPos majorGridlines minorGridlines title numFmt majorTickMark minorTickMark tickLblPos spPr txPr crossAx crosses crossesAt auto lblAlgn lblOffset tickLblSkip tickMarkSkip noMultiLvlLbl extLst',
    'valAx':'axId scaling delete axPos majorGridlines minorGridlines title numFmt majorTickMark minorTickMark tickLblPos spPr txPr crossAx crosses crossesAt crossBetween majorUnit minorUnit dispUnits extLst',
    'chartSpace':'date1904 lang roundedCorners AlternateContent style clrMapOvr pivotSource protection chart spPr txPr externalData printSettings userShapes extLst',
    'ser':'idx order tx spPr invertIfNegative pictureOptions marker dPt dLbls trendline errBars cat xVal val yVal smooth shape extLst'}
   for node in doc.iter():
    rank=ranks.get(node.tag.split('}')[-1])
    if rank:
     order=rank.split();node[:]=sorted(node,key=lambda x:order.index(x.tag.split('}')[-1]) if x.tag.split('}')[-1] in order else 99)
   parts[path]=E.tostring(doc)

def compact_controls(parts,sheets):
 """Keep comparison inputs above their plots, inside the first screen."""
 moves={ec(col)+str(row):ec(col)+str({28:9,30:10,33:11}[row]) for col in range(1,14) for row in [28,30,33]}
 lock=E.fromstring(parts[sheets['Lock-up']]);ln=nodes(lock)
 for a,b in moves.items():
  if a not in ln:continue
  n=deepcopy(ln[a]);n.set('r',b);place(lock,n);put(lock,a,v='')
 for path,raw in list(parts.items()):
  if not path.endswith('.xml') or not (path.startswith('xl/worksheets/') or path.startswith('xl/charts/') or path=='xl/workbook.xml'):continue
  local=path==sheets['Lock-up'];doc=lock if local else E.fromstring(raw)
  if not local and b'Lock-up' not in raw:continue
  for n in doc.iter():
   if n.tag.split('}')[-1] in ['f','formula','formula1','formula2','definedName'] and n.text:
    tokens=Tokenizer('='+n.text).items
    for t in tokens:
     if t.type!='OPERAND' or t.subtype!='RANGE':continue
     if '!' in t.value:
      prefix,ref=t.value.rsplit('!',1)
      if prefix.strip("'")!='Lock-up':continue
     elif local:prefix=None;ref=t.value
     else:continue
     simple=ref.replace('$','')
     if simple in moves:
      dest=moves[simple];t.value=(prefix+'!' if prefix else '')+'$'+re.match('[A-Z]+',dest)[0]+'$'+re.search('[0-9]+',dest)[0]
    n.text=''.join(t.value for t in tokens)
   if local and n.tag==q('dataValidation'):n.set('sqref',moves.get(n.get('sqref'),n.get('sqref')))
  if local:sort(doc)
  parts[path]=E.tostring(doc)
 for name in ['IPO Live','AH','Lock-up','Peer Trades']:
  doc=E.fromstring(parts[sheets[name]])
  for row in doc.find(q('sheetData')):
   r=int(row.get('r'))
   if (r in [3,5,6] and name=='Lock-up') or (r in [5,6] and name=='Peer Trades') or (r==3 and name in ['IPO Live','AH']) or (r==6 and name=='AH'):row.set('ht','8');row.set('customHeight','1')
   if name=='Lock-up' and r in [4,9,10,11]:row.set('ht','22');row.set('customHeight','1')
   if name=='Lock-up' and 12<=r<=36:row.set('ht','18');row.set('customHeight','1')
   if name=='Peer Trades' and 15<=r<=34:row.set('ht','18');row.set('customHeight','1')
   if name=='Peer Trades' and r in [3,4,7]:row.set('ht','26');row.set('customHeight','1')
   if name=='Peer Trades' and 8<=r<=13:row.set('ht','19');row.set('customHeight','1')
  sort(doc);parts[sheets[name]]=E.tostring(doc)
  dp=drawing_path(parts,sheets[name]);draw=E.fromstring(parts[dp])
  if name=='Lock-up':anchor(list(draw)[0],'A13','G27');anchor(list(draw)[1],'G13','M27')
  if name=='Peer Trades':anchor(list(draw)[0],'A15','D29');anchor(list(draw)[1],'D15','H29')
  if name=='IPO Live':anchor(list(draw)[0],'J5','P24');anchor(list(draw)[1],'J36','P55')
  parts[dp]=E.tostring(draw)

def quote_precision(parts,sheets,root=None):
 """Show penny quotes and small daily moves without rounding them to zero."""
 styles=E.fromstring(parts['xl/styles.xml']);xfs=styles.find(q('cellXfs'));formats=styles.find(q('numFmts'));ids={n.get('formatCode'):int(n.get('numFmtId')) for n in formats};copies={}
 def format_cell(cell,code):
  if cell is None:return
  if code not in ids:
   ids[code]=max([163]+list(ids.values()))+1;E.SubElement(formats,q('numFmt'),{'numFmtId':str(ids[code]),'formatCode':code})
  key=(int(cell.get('s','0')),code)
  if key not in copies:
   style=deepcopy(list(xfs)[key[0]]);style.set('numFmtId',str(ids[code]));style.set('applyNumberFormat','1');copies[key]=len(xfs);xfs.append(style)
  cell.set('s',str(copies[key]))
 for name in ['IPO Live','Peer Trades']:
  doc=E.fromstring(parts[sheets[name]]);ns=nodes(doc)
  if name=='IPO Live':
   for addr,cell in ns.items():
    if re.fullmatch('D[0-9]+',addr) and int(addr[1:])>=8:format_cell(cell,'0.000')
    if re.fullmatch('E[0-9]+',addr) and int(addr[1:])>=8 or re.fullmatch('H(?:[6-9]|1[0-4]|3[7-9]|4[0-4])',addr):format_cell(cell,'0.00%;(0.00%);0.00%')
  else:
   for addr in ['B9','C9']:format_cell(ns.get(addr),'0.000')
   for addr in ['B11','C11']:format_cell(ns.get(addr),'0.00%;(0.00%);0.00%')
  parts[sheets[name]]=E.tostring(doc)
 formats.set('count',str(len(formats)));xfs.set('count',str(len(xfs)));parts['xl/styles.xml']=E.tostring(styles)

def support_tab_clarity(parts,sheets,root,n):
 """Compact reference pages and keep off-terminal checks readable."""
 styles=E.fromstring(parts['xl/styles.xml']);xfs=styles.find(q('cellXfs'));wrapped={}
 def wrap(cell):
  if cell is None:return
  old=int(cell.get('s','0'))
  if old not in wrapped:
   style=deepcopy(list(xfs)[old]);alignment=style.find(q('alignment'))
   if alignment is None:alignment=E.SubElement(style,q('alignment'))
   alignment.set('wrapText','1');alignment.set('vertical','center');wrapped[old]=len(xfs);xfs.append(style)
  cell.set('s',str(wrapped[old]))
 from datetime import date
 for name in ['Pipeline','CS League','SM League','Taxonomy','Notes','BBG Verify']:
  doc=E.fromstring(parts[sheets[name]]);ns=nodes(doc)
  if name=='Pipeline':
   put(doc,'A2',v='Pipeline · filed / reported terms',style=ns['A2'].get('s'))
  if name in ['CS League','SM League']:
   put(doc,'A2',v='Equal-weight returns · day-1 hit = close above offer',style=ns['A2'].get('s'))
   cols=doc.find(q('cols'))
   for i in [2,3]:
    for col in cols:
     if int(col.get('min'))<=i<=int(col.get('max')):col.set('width',str(max(14,float(col.get('width','14')))))
   for a,cell in ns.items():
    if re.fullmatch('[A-Z]+4',a):wrap(cell)
  if name=='Notes':
   updates={
    'A2':f'{n} IPOs · built {date.today().isoformat()} · quote dates shown in each monitor',
    'B6':'E4 selects Stored / Bloomberg. Stored uses dated saved quotes; Bloomberg requests live A, H and FX prices and history through today.',
    'B7':'A/H analysis is in AH_Premium_Study.docx. The workbook contains the monitoring charts.',
    'B8':'BBG Verify is at the back. Calculation and history sheets are hidden.',
    'B11':'Cornerstone and stabilising-manager deal statistics. Filed allocations and actual appointed managers are retained separately.',
    'B19':'Live TTM P/E and P/S: scalar BDP with BQL fallback. NTM / FY2027 estimates: BQL. Missing live values show Unavailable.',
    'A70':'IPO Live','B70':'B4 selects Stored / Bloomberg; daily change is versus previous close. Sector averages exclude missing or stale quotes.',
    'A71':'Lock-up','B71':'B4 / E4 select the event; B10 / E10 / H10 / K10 compare codes. B11 / E11 set the expiry cohort. Windows are 30 trading sessions.',
    'A72':'Peer Trades','B72':'B3 selects a named peer pair; F3 sets source; H3 sets horizon; F4 / H4 set custom dates. Spread is the return difference in percentage points.'}
   model_names=E.fromstring(parts['xl/workbook.xml']).find(q('definedNames'))
   protected={n.text.split('!')[1].replace('$','') for n in model_names if n.get('name','').startswith('W_') and n.text.startswith('Notes!')}
   assert not set(updates)&protected,'Control notes would overwrite a named scoring input'
   for addr,text in updates.items():put(doc,addr,v=text,style=ns.get(addr,ns['B9' if addr.startswith('B') else 'A9']).get('s'))
  if name=='BBG Verify':
   put(doc,'A2',v='Bloomberg and filed terms side by side',style=ns['A2'].get('s'))
   for addr,cell in ns.items():
    f=cell.find(q('f'))
    if f is not None and re.search(r'\b(?:BDP|BDH|BDS|BQL)\(',f.text or '') and not f.text.startswith('IFERROR('):
     put(doc,addr,v='Unavailable',f=f'IFERROR({f.text},"Unavailable")',style=cell.get('s'))
  for row in doc.find(q('sheetData')):
   r=int(row.get('r'));height=42 if name=='Notes' and 70<=r<=72 else 32 if name=='Pipeline' and r>=6 or name=='Taxonomy' and r>=5 else 40 if name in ['CS League','SM League'] and r==4 else 16 if r==2 else None
   if height:row.set('ht',str(height));row.set('customHeight','1')
  sort(doc);parts[sheets[name]]=E.tostring(doc)
 xfs.set('count',str(len(xfs)));parts['xl/styles.xml']=E.tostring(styles)

def apply(parts,sheets,root):
 db=E.fromstring(parts[sheets['Database']]);assert value(nodes(db)['BM4'])=='A/H pair','Apply desk release only once'
 insert_columns(parts,sheets,'Database',ci('BM'),3)
 insert_columns(parts,sheets,'Screener',ci('BJ'),1)
 db=E.fromstring(parts[sheets['Database']]);screen=E.fromstring(parts[sheets['Screener']]);val=E.fromstring(parts[sheets['Valuation Data']]);deals=json.loads((root/'data/deals.json').read_text())['deals'];n=len(deals)
 from patch_presentation_workbook import QUERIES
 for i,d in enumerate(deals):
  rr=8+i*8;dr=i+5
  for old in ['D','G']:put(val,old+str(rr),v='')
  valuation_request(val,rr,f'$A{rr}',QUERIES[0],'AU','L','BC','pe_ratio','C')
  valuation_request(val,rr,f'$A{rr}',QUERIES[1],'BD','M','BL','px_to_sales_ratio','F')
  for ac,out,helper,dbcol,query in zip(['P','Z','AJ'],['X','AH','AR'],['Y','AI','AS'],['BM','BN','BO'],QUERIES[2:]):
   valuation_request(val,rr,f'$A{rr}',query,ac,out,helper,'px_to_sales_ratio' if dbcol=='BO' else 'pe_ratio')
   put(db,dbcol+str(dr),v='Unavailable',f=f"'Valuation Data'!{out}{rr}",style=nodes(db)['BJ'+str(dr)].get('s'))
 for col,label in [('BM','NTM P/E live'),('BN','FY2027 P/E live'),('BO','FY2027 P/S live')]:put(db,col+'4',v=label,style=nodes(db)['BJ4'].get('s'))
 for m in db.iter(q('mergeCell')):
  if m.get('ref')=='BE3:BL3':m.set('ref','BE3:BO3')
 cols=db.find(q('cols'))
 for i in range(ci('BM'),ci('BO')+1):E.SubElement(cols,q('col'),{'min':str(i),'max':str(i),'width':'16','customWidth':'1'})
 cols[:]=sorted(cols,key=lambda x:int(x.get('min')))
 # The comparison fundamentals already had duplicate TTM columns. Reuse them
 # for the estimates, then insert only one additional estimate column.
 sn=nodes(screen)
 for col,label in [('BE','TTM P/E live'),('BG','TTM P/S live'),('BH','NTM P/E live'),('BI','FY2027 P/E live'),('BJ','FY2027 P/S live')]:put(screen,col+'20',v=label,style=sn['BE20'].get('s'))
 for row in list(range(21,36))+[37]:
  source=sn['BE'+str(row)];f=source.find(q('f')).text
  for col,dbcol in [('BH','BM'),('BI','BN'),('BJ','BO')]:
   output=f.replace('$BJ$',f'${dbcol}$').replace('BE21:BE35',col+'21:'+col+'35')
   put(screen,col+str(row),v='Unavailable' if row!=37 else '',f=output,style=source.get('s'))
 for m in screen.iter(q('mergeCell')):
  if m.get('ref')=='AZ19:BI19':m.set('ref','AZ19:BJ19')
 # The desk controls should not push the comparison table off the opening view.
 cutoff=json.loads((root/'data/desk_chart_data.json').read_text())['peer']['asof']
 put(screen,'A2',v='Price snapshot · '+cutoff,style=sn['A2'].get('s'))
 for old in screen.iter(q('c')):
  f=old.find(q('f'));v=old.find(q('v'))
  if f is not None:f.text=f.text.replace('not listed yet','Not in Database')
  if v is not None and v.text=='not listed yet':v.text='Not in Database'
 for addr,label in [('A8','Subsector'),('A11','A/H pair (Y/N)'),('A12','IPO date'),('A13','Offer P/E (x)'),('A17','Cornerstone filter'),('C17','Include codes'),('C18','Comps to show')]:put(screen,addr,v=label,style=sn[addr].get('s'))
 for addr in ['B11','D11','B13','D13']:
  old=sn[addr];f=old.find(q('f')).text;put(screen,addr,v='' if value(old) in ['0','0.0',None,''] else value(old),f=f'IFERROR(IF(({f})=0,"",{f}),"")',style=old.get('s'))
 for row in screen.find(q('sheetData')):
  r=int(row.get('r'));ht=14 if r==2 else 28 if r==5 else 22 if r in [3,4,6,15,19] else 19 if 7<=r<=18 else 32 if r==20 else 20 if 21<=r<=35 else None
  if ht is not None:row.set('ht',str(ht));row.set('customHeight','1')
 E.SubElement(screen.find(q('cols')),q('col'),{'min':str(ci('BJ')),'max':str(ci('BJ')),'width':'16','customWidth':'1'});screen.find(q('cols'))[:]=sorted(screen.find(q('cols')),key=lambda x:int(x.get('min')))
 hrow=8+n*8;arow=hrow+48
 for row,label,k in [(65,'TTM P/E',0),(66,'NTM P/E',2),(67,'FY2027 P/E',3),(68,'TTM P/S',1),(69,'FY2027 P/S',4)]:
  put(screen,'A'+str(row),v=label,style=sn['A65'].get('s'))
  for col,base in [('C',arow),('D',hrow)]:put(screen,col+str(row),v='Unavailable',f=f'IF(\'Valuation Data\'!$A${base}="","",\'Valuation Data\'!L{base+8*k})',style=sn['C65'].get('s'))
 merges=screen.find(q('mergeCells'));E.SubElement(merges,q('mergeCell'),{'ref':'A69:B69'});merges.set('count',str(len(merges)))
 # Selected H estimates reuse the database requests rather than launch them twice.
 # The ticker column is sparse at eight-row intervals: MATCH already returns
 # the native row offset. Do not multiply the offset a second time.
 for base in [hrow,arow]:
  for k in [0,1]:
   rr=base+8*k
   for old in ['D','G']:put(val,old+str(rr),v='')
   valuation_request(val,rr,f'$A${base}',QUERIES[k],'AU' if k==0 else 'BD','L','BC' if k==0 else 'BL','pe_ratio' if k==0 else 'px_to_sales_ratio','C')
 for k,col in [(2,'X'),(3,'AH'),(4,'AR')]:
  put(val,'C'+str(hrow+8*k),v='')
  put(val,'L'+str(hrow+8*k),v='Unavailable',f=f'IFERROR(INDEX(${col}$8:${col}${8*(n-1)+8},MATCH($A${hrow},$A$8:$A${8*(n-1)+8},0)),"Unavailable")')
 for k,raw,helper in [(2,'P','Y'),(3,'Z','AI'),(4,'AJ','AS')]:
  rr=arow+8*k;put(val,'C'+str(rr),v='');valuation_request(val,rr,f'$A${arow}',QUERIES[k],raw,'L',helper,'px_to_sales_ratio' if k==4 else 'pe_ratio')
 for name,doc in [('Database',db),('Screener',screen),('Valuation Data',val)]:sort(doc);parts[sheets[name]]=E.tostring(doc)
 # Code-pair labels fit one editable cell; both company names remain directly below.
 roster=json.loads((root/'data/peer_pairs.json').read_text())['pairs'];peer=E.fromstring(parts[sheets['Peer Trades']]);data=E.fromstring(parts[sheets['Peer Data']])
 for i,p in enumerate(roster,3):put(data,'S'+str(i),v=p['code_a']+' / '+p['code_b'])
 put(peer,'B3',v=roster[0]['code_a']+' / '+roster[0]['code_b'],style=nodes(peer)['B3'].get('s'))
 # Both native monitors are real Excel sheets; validate sequence and row identity.
 for name in ['IPO Live','AH','Lock-up','Peer Trades','Screener']:
  doc=peer if name=='Peer Trades' else E.fromstring(parts[sheets[name]])
  view=doc.find(q('sheetViews')).find(q('sheetView'));view.set('zoomScale','90')
  if name=='IPO Live':
   for addr,old in list(nodes(doc).items()):
    if re.fullmatch('D[0-9]+',addr) and int(addr[1:])>=8 and old.find(q('f')) is not None:
     r=int(addr[1:]);put(doc,addr,v='Unavailable',f=f'IF($A{r}="","",IFERROR(BDP($A{r},"LAST_PRICE"),"Unavailable"))',style=old.get('s'))
   for r in list(range(6,15))+list(range(37,45)):
    old=nodes(doc).get('H'+str(r))
    if old is not None and old.find(q('f')) is not None:old.find(q('f')).text=old.find(q('f')).text.replace('NA())','"—")')
   for a in ['G15','G45']:put(doc,a,v='')
   put(doc,'A4',v='Bloomberg live · HKD · change vs previous close',style=nodes(doc)['A4'].get('s'))
   put(doc,'D7',v='Price (HK$)',style=nodes(doc)['D7'].get('s'));put(doc,'E7',v='1D change',style=nodes(doc)['E7'].get('s'))
  if name=='AH':
   meta=json.loads((root/'data/desk_chart_data.json').read_text())['pairs']
   for i,m in enumerate(meta,8):
    rr=i-5
    put(doc,'A'+str(i),v=m['a_ticker'][:6],f=f"LEFT('Market Data'!R{rr},6)",style=nodes(doc)['A'+str(i)].get('s'))
    put(doc,'B'+str(i),v=m['code'].zfill(4),f=f'TEXT(VALUE(\'Market Data\'!P{rr}),"0000")',style=nodes(doc)['B'+str(i)].get('s'))
   ignored=doc.find(q('ignoredErrors'))
   if ignored is None:ignored=E.SubElement(doc,q('ignoredErrors'))
   E.SubElement(ignored,q('ignoredError'),{'sqref':f'A8:B{len(meta)+7}','numberStoredAsText':'1'})
  prop=doc.find(q('sheetPr'))
  if prop is None:prop=E.Element(q('sheetPr'));doc.insert(0,prop)
  color=prop.find(q('tabColor'))
  if color is None:color=E.Element(q('tabColor'));prop.insert(0,color)
  color.set('rgb',{'IPO Live':'FF217346','AH':'FFD71920','Lock-up':'FF99784E','Peer Trades':'FF526779','Screener':'FF1F4E79'}[name])
  for row in doc.find(q('sheetData')):
   r=int(row.get('r'))
   if r>=8 and name in ['IPO Live','AH']:row.set('ht','20');row.set('customHeight','1')
  sort(doc);parts[sheets[name]]=E.tostring(doc)
 sort(data);parts[sheets['Peer Data']]=E.tostring(data)
 # Restrained colour on figures, without full-cell red/green blocks.
 styles=E.fromstring(parts['xl/styles.xml']);dxfs=styles.find(q('dxfs'));quiet={}
 for name in ['IPO Live','AH','Lock-up','Peer Trades']:
  doc=E.fromstring(parts[sheets[name]])
  for rule in doc.iter(q('cfRule')):
   if rule.get('dxfId') is None:continue
   old=int(rule.get('dxfId'))
   if old not in quiet:
    copy=deepcopy(list(dxfs)[old]);fill=copy.find(q('fill'))
    if fill is not None:copy.remove(fill)
    quiet[old]=len(dxfs);dxfs.append(copy)
   rule.set('dxfId',str(quiet[old]))
  # Excel treats text as greater than a number in cellIs rules. A missing
  # quote must stay neutral, rather than acquiring the positive-return colour.
  for cf in list(doc.findall(q('conditionalFormatting'))):
   numeric=[r for r in cf if r.get('type')=='cellIs' and r.get('operator') in ['greaterThan','lessThan'] and r.find(q('formula')) is not None and r.find(q('formula')).text=='0']
   if not numeric:continue
   ranges=cf.get('sqref').split();position=list(doc).index(cf);doc.remove(cf)
   for rng in ranges:
    copy=deepcopy(cf);copy.set('sqref',rng);origin=rng.split(':')[0]
    for r in copy:
     if r.get('type')=='cellIs' and r.get('operator') in ['greaterThan','lessThan']:
      op='>' if r.get('operator')=='greaterThan' else '<';r.set('type','expression');r.attrib.pop('operator',None);r.find(q('formula')).text=f'AND(ISNUMBER({origin}),{origin}{op}0)'
    doc.insert(position,copy);position+=1
  parts[sheets[name]]=E.tostring(doc)
 dxfs.set('count',str(len(dxfs)))
 parts['xl/styles.xml']=E.tostring(styles)
 # Two expiry charts on one horizontal row, with comparison controls below.
 dp=drawing_path(parts,sheets['Lock-up']);draw=E.fromstring(parts[dp]);anchor(list(draw)[0],'A11','G27');anchor(list(draw)[1],'G11','M27');parts[dp]=E.tostring(draw)
 compact_lock_roster(parts,sheets,deals)
 compact_controls(parts,sheets)
 live_snapshot(parts,sheets,root)
 quote_precision(parts,sheets)
 # Excel repairs a table when its saved field names disagree with the sheet.
 for name in ['IPO Live','AH','Lock-up','Peer Trades']:
  doc=E.fromstring(parts[sheets[name]]);ns=nodes(doc)
  relpath=sheets[name].replace('/worksheets/','/worksheets/_rels/')+'.rels'
  if relpath not in parts:continue
  import posixpath
  for rel in E.fromstring(parts[relpath]):
   if not rel.get('Type','').endswith('/table'):continue
   t=rel.get('Target');p=t.lstrip('/') if t.startswith('/') else posixpath.normpath(posixpath.join('xl/worksheets',t));table=E.fromstring(parts[p]);start=table.get('ref').split(':')[0];row=re.search('[0-9]+',start)[0];col=ci(re.match('[A-Z]+',start)[0])
   for i,field in enumerate(table.find(q('tableColumns'))):field.set('name',str(value(ns[ec(col+i)+row])))
   parts[p]=E.tostring(table)
 chart_style(parts,sheets)
 support_tab_clarity(parts,sheets,root,n)

if __name__=='__main__':
 from pathlib import Path
 root=Path(__file__).resolve().parent.parent
 with zipfile.ZipFile(sys.argv[1]) as z:parts={p:z.read(p) for p in z.namelist()}
 _,_,sheets=maps(parts);apply(parts,sheets,root)
 with zipfile.ZipFile(sys.argv[2],'w',zipfile.ZIP_DEFLATED) as z:
  for p,raw in parts.items():z.writestr(p,raw)
