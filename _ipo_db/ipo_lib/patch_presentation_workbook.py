"""Bounded native graft for presentation, BQL valuations and CSI reference.

Artifact Tool owns the small layout. ZIP edits preserve the production
workbook's existing formulas, native charts, comments and validations.
"""
import base64,io,json,re,zipfile,sys,gc
from copy import deepcopy
from pathlib import Path
from datetime import date
import xml.etree.ElementTree as E
from patch_peer_workbook import maps,q,N,R,P,T
C='http://schemas.openxmlformats.org/drawingml/2006/chart'
D='http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing'
c=lambda n:'{'+C+'}'+n
xd=lambda n:'{'+D+'}'+n

QUERIES=['pe_ratio(fpt=ltm, fpo=0, ae=a)','px_to_sales_ratio(fpt=ltm)',
 'pe_ratio(fpt=ltm, fpo=1, ae=e)','pe_ratio(fpt=a, fpr=2027, ae=e)',
 'px_to_sales_ratio(fpt=a, fpr=2027, ae=e)']
def serial(s):return (date.fromisoformat(s)-date(1899,12,30)).days if s else None
def cells(doc):return {x.get('r'):x for x in doc.iter(q('c'))}
def put(doc,addr,value=None,formula=None,style=None):
 data=doc.find(q('sheetData'));row=int(re.search(r'\d+',addr)[0]);rows={int(r.get('r')):r for r in data};r=rows.get(row)
 if r is None:r=E.SubElement(data,q('row'),{'r':str(row)})
 node=next((x for x in r if x.get('r')==addr),None)
 if node is None:node=E.SubElement(r,q('c'),{'r':addr})
 for child in list(node):node.remove(child)
 node.attrib.pop('t',None)
 if style is not None:node.set('s',str(style))
 if formula is not None:E.SubElement(node,q('f')).text=formula.lstrip('=')
 if isinstance(value,str):
  node.set('t','str' if formula else 'inlineStr')
  if formula:E.SubElement(node,q('v')).text=value
  else:E.SubElement(E.SubElement(node,q('is')),q('t')).text=value
 elif value is not None:E.SubElement(node,q('v')).text=str(value)
 elif formula is not None:node.set('t','str');E.SubElement(node,q('v')).text=''
 return node
def sort(doc):
 data=doc.find(q('sheetData'));data[:]=sorted(data,key=lambda r:int(r.get('r')))
 def col(a):
  n=0
  for x in re.match('[A-Z]+',a)[0]:n=n*26+ord(x)-64
  return n
 for row in data:row[:]=sorted(row,key=lambda x:col(x.get('r')))
def text(node,shared):
 if node is None:return ''
 if node.get('t')=='s':return shared[int(node.find(q('v')).text)]
 return ''.join(node.find(q('is')).itertext()) if node.find(q('is')) is not None else node.find(q('v')).text if node.find(q('v')) is not None else ''
def extracted(a,b,row):
 # Exact two-argument BQL requests retain Bloomberg's native headers/IDs.
 # A scalar, a one-row table, and up to two header rows are supported.
 choices=[f'{b}{row+i}' for i in range(4)]+[f'{a}{row}']
 f='"Unavailable"'
 for cell in reversed(choices):f=f'IF(IFERROR(ISNUMBER({cell}),FALSE),{cell},{f})'
 return '='+f
def patch(source,dest,root):
 root=Path(root)
 template=json.loads((root/'data/presentation_template.json').read_text())
 with zipfile.ZipFile(io.BytesIO(base64.b64decode(template['xlsx_base64']))) as z:new={p:z.read(p) for p in z.namelist()}
 with zipfile.ZipFile(source) as z:parts={p:z.read(p) for p in z.namelist()}
 wb,wr,sheets=maps(parts);_,_,nsheets=maps(new)
 shared=[''.join(x.itertext()) for x in E.fromstring(new['xl/sharedStrings.xml'])] if 'xl/sharedStrings.xml' in new else []
 styles=E.fromstring(parts['xl/styles.xml']);incoming=E.fromstring(new['xl/styles.xml']);offset={}
 for name in ['fonts','fills','borders','cellStyleXfs','cellXfs','dxfs','numFmts']:
  a=styles.find(q(name));b=incoming.find(q(name))
  if a is None:a=E.SubElement(styles,q(name),{'count':'0'})
  offset[name]=len(a)
  if name in ['cellXfs','numFmts','dxfs'] or b is None:continue
  for x in b:a.append(deepcopy(x))
  a.set('count',str(len(a)))
 fmts=styles.find(q('numFmts'));fm={};nextid=max([163]+[int(x.get('numFmtId')) for x in fmts])+1
 for x in incoming.find(q('numFmts')) or []:
  n=deepcopy(x);fm[int(x.get('numFmtId'))]=nextid;n.set('numFmtId',str(nextid));fmts.append(n);nextid+=1
 fmts.set('count',str(len(fmts)))
 for x in incoming.find(q('cellXfs')):
  n=deepcopy(x)
  for attr,group in [('fontId','fonts'),('fillId','fills'),('borderId','borders'),('xfId','cellStyleXfs')]:n.set(attr,str(int(n.get(attr,'0'))+offset[group]))
  n.set('numFmtId',str(fm.get(int(n.get('numFmtId','0')),int(n.get('numFmtId','0')))));styles.find(q('cellXfs')).append(n)
 styles.find(q('cellXfs')).set('count',str(len(styles.find(q('cellXfs')))))
 parts['xl/styles.xml']=E.tostring(styles)
 content=E.fromstring(parts['[Content_Types].xml'])
 def override(path,kind):
  if not any(x.get('PartName')=='/'+path for x in content):E.SubElement(content,'{'+T+'}Override',{'PartName':'/'+path,'ContentType':kind})
 def add_sheet(name):
  if name in sheets:return E.fromstring(parts[sheets[name]])
  path='xl/worksheets/sheet'+name.replace(' ','')+'.xml';sheets[name]=path
  E.SubElement(wb.find(q('sheets')),q('sheet'),{'name':name,'sheetId':str(max(int(x.get('sheetId')) for x in wb.find(q('sheets')))+1),'state':'hidden','{'+R+'}id':name.replace(' ','')})
  E.SubElement(wr,'{'+P+'}Relationship',{'Id':name.replace(' ',''),'Type':R+'/worksheet','Target':'/'+path})
  override(path,'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml')
  doc=E.Element(q('worksheet'));E.SubElement(doc,q('sheetData'));return doc
 # Graft layout cells/styles but retain working formula addresses and inputs.
 for name in ['Lock-up','AH','Screener']:
  doc=E.fromstring(parts[sheets[name]]);layout=E.fromstring(new[nsheets[name]]);old=cells(doc)
  for n in layout.iter(q('c')):
   addr=n.get('r');row=int(re.search(r'\d+',addr)[0]);style=int(n.get('s','0'))+offset['cellXfs']
   if name=='Lock-up' and row<=54:
    if addr in old and old[addr].find(q('f')) is not None:old[addr].set('s',str(style));continue
    if addr in ['B4','E4','B32','B33','B34','B35','B37','B38']:old[addr].set('s',str(style));continue
   put(doc,addr,text(n,shared) if n.get('t') in ['s','inlineStr','str'] else None,style=style)
  mergers=doc.find(q('mergeCells'))
  if mergers is None:mergers=E.SubElement(doc,q('mergeCells'))
  if name=='Lock-up':
   for m in list(mergers):
    if int(re.search(r'\d+',m.get('ref'))[0])<=54:mergers.remove(m)
  for m in layout.iter(q('mergeCell')):mergers.append(deepcopy(m))
  mergers.set('count',str(len(mergers)))
  if name=='Lock-up':
   cols=doc.find(q('cols'));idx=list(doc).index(cols);doc.remove(cols);doc.insert(idx,deepcopy(layout.find(q('cols'))))
   # Do not expand / restyle hidden helper columns P onward.
   for col in E.fromstring(parts[sheets[name]]).find(q('cols')):
    if int(col.get('min'))>=16:doc.find(q('cols')).append(deepcopy(col))
   put(doc,'A6',formula='IF($P$8="","",$P$8)',value='')
   put(doc,'A10','Cornerstone expiry')
   for addr in ['A26','A27','A41','A42']:put(doc,addr,'')
   # Keep source hyperlink concise; the actual filed URL remains unchanged.
   cell=cells(doc)['A25'];cell.find(q('f')).text=cell.find(q('f')).text.replace('Selected event: HKEX filing','HKEX filing');cell.find(q('v')).text='HKEX filing'
   for row in doc.find(q('sheetData')):
    r=int(row.get('r'))
    if r<=54:
     lr=next((x for x in layout.find(q('sheetData')) if int(x.get('r'))==r),None)
     if lr is not None:
      for attr in ['ht','customHeight']:
       if attr in lr.attrib:row.set(attr,lr.get(attr))
   for addr in ['A14','A18']:
    oldcell=cells(doc)[addr];xf=deepcopy(styles.find(q('cellXfs'))[int(oldcell.get('s'))]);oldcell.set('s',str(len(styles.find(q('cellXfs')))));styles.find(q('cellXfs')).append(xf)
   # Align the event roster and avoid very long coverage descriptions.
   data=json.loads((root/'data/batches/lockup_events.json').read_text());events=[e for e in data['events'] if e['category']=='Cornerstone' and e['date_basis']!='No cornerstone tranche']
   for i,e in enumerate(events,55):
    status=e.get('windows',{}).get('30 trading sessions',{}).get('status','')
    short='Complete' if status=='Complete' else 'Expiry unconfirmed' if not e.get('last_day_locked') else 'Future expiry' if e['last_day_locked']>data['price_asof'] else 'Post window pending' if 'pending' in status.lower() or 'future' in status.lower() else 'Missing prices'
    put(doc,'L'+str(i),short)
   # Preserve existing conditional colors, add reactive color to the KPIs.
   dxf=styles.find(q('dxfs'));start=len(dxf)
   for color in ['1E6B45','A33434']:
    dx=E.SubElement(dxf,q('dxf'));E.SubElement(E.SubElement(dx,q('font')),q('color'),{'rgb':'FF'+color})
   dxf.set('count',str(len(dxf)))
   cf=E.Element(q('conditionalFormatting'),{'sqref':'A14 A18'})
   for k,op in enumerate(['greaterThan','lessThan']):
    rule=E.SubElement(cf,q('cfRule'),{'type':'cellIs','dxfId':str(start+k),'priority':str(100+k),'operator':op});E.SubElement(rule,q('formula')).text='0'
   pos=next((i for i,x in enumerate(doc) if x.tag in [q('dataValidations'),q('hyperlinks'),q('pageMargins'),q('drawing')]),len(doc));doc.insert(pos,cf)
  sort(doc);parts[sheets[name]]=E.tostring(doc)
  if name=='Lock-up':
   sheetrel=E.fromstring(parts[sheets[name].replace('/worksheets/','/worksheets/_rels/')+'.rels'])
   for relationship in sheetrel:
    if relationship.get('Type')!=R+'/table':continue
    path=relationship.get('Target').lstrip('/');path=path if path.startswith('xl/') else 'xl/tables/'+Path(path).name
    table=E.fromstring(parts[path]);header=int(re.search(r'\d+',table.get('ref'))[0])
    for i,col in enumerate(table.find(q('tableColumns')),1):col.set('name',text(cells(doc)[chr(64+i)+str(header)],[]))
    parts[path]=E.tostring(table)
 # Rescale the first lock-up chart to the same width as the comparison.
 lockrels=E.fromstring(parts[sheets['Lock-up'].replace('/worksheets/','/worksheets/_rels/')+'.rels'])
 drawing=next(x.get('Target').lstrip('/') for x in lockrels if x.get('Type')==R+'/drawing');drawing=drawing if drawing.startswith('xl/') else 'xl/drawings/'+Path(drawing).name
 ld=E.fromstring(parts[drawing]);first=list(ld)[0]
 end=first.find(xd('to'))
 if end is not None:end.find(xd('col')).text='12';end.find(xd('row')).text='24'
 else:
  extent=first.find(xd('ext'))
  if extent is not None:extent.set('cx',str(1090*9525));extent.set('cy',str(400*9525))
 parts[drawing]=E.tostring(ld)
 # Exact live TTM queries for all H counters; estimates only for the selected
 # A/H company, to avoid multiplying every stock by five expensive requests.
 val=add_sheet('Valuation Data');put(val,'A1','Bloomberg BQL requests. Raw responses preserve IDs and headers.');put(val,'A2','User-supplied query expressions; no historical valuation fallback.')
 deals=json.loads((root/'data/deals.json').read_text())['deals'];db=E.fromstring(parts[sheets['Database']]);verify=E.fromstring(parts[sheets['BBG Verify']]);screen=E.fromstring(parts[sheets['Screener']])
 for i,d in enumerate(deals):
  rr=8+i*8;dr=5+i;put(val,f'A{rr}',formula=f'TEXT(VALUE(Database!$A{dr}),"0")&" HK Equity"',value=str(int(d['code']))+' HK Equity')
  for ac,bc,oc,query in [('C','D','L',QUERIES[0]),('F','G','M',QUERIES[1])]:
   put(val,f'{ac}{rr}',formula=f'BQL($A{rr},"{query}")');put(val,f'{oc}{rr}',formula=extracted(ac,bc,rr),value='Unavailable')
  for col,out in [('BJ','L'),('BL','M')]:put(db,f'{col}{dr}',formula=f"'Valuation Data'!{out}{rr}",value='Unavailable')
  for col,out in [('J','L'),('S','M')]:put(verify,f'{col}{dr}',formula=f"'Valuation Data'!{out}{rr}",value='Unavailable')
 put(db,'BJ4','P/E TTM live (BQL)',style=cells(db)['BJ4'].get('s'));put(db,'BL4','P/S TTM live (BQL)',style=cells(db)['BL4'].get('s'))
 # The target H ticker expression is already used in the existing live panel.
 sf=cells(screen)['B59'].find(q('f')).text;htick=sf[3:sf.index('=""')]
 htick=f'IF({htick}="0 HK Equity","",{htick})'
 hrow=8+len(deals)*8;arow=hrow+48
 for rr,ticker in [(hrow,htick),(arow,"'Screener'!$F$54")]:
  put(val,f'A{rr}',formula=ticker,value='');
  for k,query in enumerate(QUERIES):
   r=rr+k*8;put(val,f'C{r}',formula=f'IF($A${rr}="","",BQL($A${rr},"{query}"))');put(val,f'L{r}',formula=extracted('C','D',r),value='Unavailable')
 put(screen,'B56',formula=f'IF($F$54="","n/a",\'Valuation Data\'!L{arow})',value='n/a')
 for addr,rr in [('B59',hrow),('B60',hrow+8)]:put(screen,addr,formula=f'IF(\'Valuation Data\'!$A${hrow}="","n/a",\'Valuation Data\'!L{rr})',value='n/a')
 for row,k in [(65,2),(66,3),(67,1),(68,4)]:
  for col,rr in [('C',arow),('D',hrow)]:put(screen,f'{col}{row}',formula=f'IF(\'Valuation Data\'!$A${rr}="","n/a",\'Valuation Data\'!L{rr+k*8})',value='n/a')
 put(screen,'A52','A/H live prices and terms',style=cells(screen)['A52'].get('s'));put(screen,'A60','H P/S now (TTM)',style=cells(screen)['A60'].get('s'))
 put(screen,'F52','A-share price · last month',style=cells(screen)['F52'].get('s'))
 put(screen,'G53','A-share code',style=cells(screen)['G53'].get('s'))
 headers={text(x,[]) if x.get('t')=='inlineStr' else '':x.get('r') for x in screen.iter(q('c')) if x.get('r').endswith('20')}
 for label,dbcol in [('P/E now (x)','BJ'),('P/S now (x)','BL')]:
  col=re.match('[A-Z]+',headers[label])[0]
  for r in range(21,36):
   node=cells(screen)[f'{col}{r}'];f=node.find(q('f')).text;ix=f.index('IFERROR(BDP(');end=f.index(',IF(INDEX(',ix);matched=f[ix+len('IFERROR(BDP('):end]
   match=re.search(r'MATCH\(LARGE\([^,]+,\d+\),[^,]+,0\)',f)[0]
   shown=f[:ix];rank=cells(screen).get('A'+str(r));cache=rank.find(q('v')) if rank is not None else None
   put(screen,f'{col}{r}',formula=shown+f'IFERROR(INDEX(Database!${dbcol}$5:${dbcol}${len(deals)+4},{match}),"Unavailable"),""))',value='Unavailable' if cache is not None and cache.text else '')
 for name,doc in [('Valuation Data',val),('Database',db),('BBG Verify',verify),('Screener',screen)]:sort(doc);parts[sheets[name]]=E.tostring(doc)
 # Selected CSI / A history uses the same E4 mode as the premium chart.
 refdata=json.loads((root/'data/ah_reference.json').read_text());meta=json.loads((root/'data/desk_chart_data.json').read_text())['pairs'];ref=add_sheet('AH Reference');cursor=3
 from ah_basis import review_for
 delta=E.fromstring(parts[sheets['AH Delta']]);market=E.fromstring(parts[sheets['Market Data']])
 for i,m in enumerate(meta,3):
  review=review_for(m['code'],root);events=review.get('events',[review]) if review else []
  for k,(hc,ac) in enumerate([('J','K'),('L','M'),('O','P')]):
   e=events[k] if k<len(events) else None
   put(delta,hc+str(i),serial(e['h_ex_date']) if e else 0);put(delta,ac+str(i),serial(e['a_ex_date']) if e else 0)
  if review:
   put(market,'Z'+str(i),0);put(market,'AO'+str(i),serial(events[0]['h_ex_date']));put(market,'AP'+str(i),serial(events[0]['a_ex_date']))
 for name,doc in [('AH Delta',delta),('Market Data',market)]:sort(doc);parts[sheets[name]]=E.tostring(doc)
 ahguards=E.fromstring(parts[sheets['AH']])
 for addr,col in [('P26','O'),('P27','P')]:put(ahguards,addr,formula=f'IFERROR(INDEX(\'AH Delta\'!${col}$3:${col}$70,$P$3),0)',value=0,style=1)
 sort(ahguards);parts[sheets['AH']]=E.tostring(ahguards)
 chart=E.fromstring(parts[sheets['Chart Data']])
 for node in chart.iter(q('c')):
  if re.fullmatch('B(?:[5-9]|[1-9][0-9]+)',node.get('r','')) and node.find(q('f')) is not None:
   row=re.search(r'\d+',node.get('r'))[0];f=node.find(q('f'));f.text=f.text.replace('AND(AH!$P$9<>1,',f'AND(AH!$P$9<>1,OR(AH!$P$26<=0,(A{row}>=AH!$P$26)=(F{row}>=AH!$P$27)),')
 parts[sheets['Chart Data']]=E.tostring(chart)
 comp=E.fromstring(parts[sheets['AH Compare']])
 for h,a,out,idx in [('A','E','G','H'),('J','N','P','Q'),('S','W','Y','Z'),('AB','AF','AH','AI')]:
  for node in comp.iter(q('c')):
   if re.fullmatch(out+r'[0-9]+',node.get('r','')) and node.find(q('f')) is not None:
    row=re.search(r'\d+',node.get('r'))[0];f=node.find(q('f'));hh=f'IFERROR(INDEX(\'AH Delta\'!$O$3:$O$70,${idx}$2),0)';aa=f'IFERROR(INDEX(\'AH Delta\'!$P$3:$P$70,${idx}$2),0)'
    f.text=f.text.replace('AND(ISNUMBER(',f'AND(OR({hh}=0,(${h}{row}>={hh})=(${a}{row}>={aa})),ISNUMBER(',1)
 parts[sheets['AH Compare']]=E.tostring(comp)
 for i,m in enumerate(meta,3):
  r=refdata['pairs'][m['code']];vals=[m['code'],serial(m['ipo_date']),cursor,len(r['rows'])]
  for j,x in enumerate(vals):put(ref,chr(65+j)+str(i),x)
  for dt,a,b in r['rows']:
   for col,value in [('M',serial(dt)),('N',a),('O',b)]:put(ref,col+str(cursor),value)
   cursor+=1
 put(ref,'V1',formula="IFERROR(INDEX($C$3:$C$70,AH!$P$3),3)");put(ref,'V2',formula="IFERROR(INDEX($D$3:$D$70,AH!$P$3),0)")
 put(ref,'W4',formula='IF(AH!$E$4="Bloomberg",BDH(AH!$P$5,"PX_LAST",AH!$P$6-31,MIN(TODAY(),AH!$P$6+31),"Dts=S","Dir=V","Sort=A","Days=T","Per=cd","UseDPDF=N","CshAdjNormal=N","CshAdjAbnormal=N","CapChg=N"),"")')
 put(ref,'AA4',formula='IF(AH!$E$4="Bloomberg",BDH("SHSZ300 Index","PX_LAST",AH!$P$6-31,MIN(TODAY(),AH!$P$6+31),"Dts=S","Dir=V","Sort=A","Days=T","Per=cd"),"")')
 put(ref,'V3',formula='IF(ISNUMBER(W4),4,IF(ISNUMBER(W5),5,6))')
 put(ref,'V4',formula='IFERROR(IF(AND(COUNT($W$4:$W$99)>1,COUNT($AA$4:$AA$99)>1,MIN($W$4:$W$99)>=AH!$P$6-31,MAX($W$4:$W$99)<=MIN(TODAY(),AH!$P$6+31)),1,0),0)')
 put(ref,'V5',formula='IFERROR(MATCH(1,$G$80:$G$149,0),0)');put(ref,'V6',formula='MAX($H$80:$H$149)');put(ref,'V7',formula='COUNTIFS($H$80:$H$149,">0")')
 active=refdata['pairs']['3986']['rows']
 for row in range(80,150):
  i=row-80;known=active[i] if i<len(active) else None
  put(ref,f'A{row}',formula=f'IF(AH!$P$3=0,"",IF(AH!$E$4="Stored",IF(ROW()-79<=$V$2,INDEX($M$3:$M${cursor-1},$V$1+ROW()-82),""),IF(AND($V$4=1,ROW()-79<=COUNT($W$4:$W$99)),INDEX($W$4:$W$99,$V$3+ROW()-83),"")))',value=serial(known[0]) if known else '')
  for col,rawcol,livecol in [('B','N','X'),('C','O','AB')]:
   live=f'INDEX($X$4:$X$99,MATCH(A{row},$W$4:$W$99,0))' if col=='B' else f'INDEX($AB$4:$AB$99,MATCH(A{row},$AA$4:$AA$99,0))'
   put(ref,f'{col}{row}',formula=f'IF(ISNUMBER(A{row}),IF(AH!$E$4="Stored",INDEX(${rawcol}$3:${rawcol}${cursor-1},$V$1+ROW()-82),IFERROR({live},"")),"")',value=known[1 if col=='B' else 2] if known else '')
  put(ref,f'G{row}',formula=f'IF(AND(ISNUMBER(B{row}),B{row}>0,ISNUMBER(C{row}),C{row}>0),1,0)',value=1 if known else 0)
  for col,raw in [('D','B'),('E','C')]:put(ref,f'{col}{row}',formula=f'IF(AND(G{row}=1,$V$5>0),{raw}{row}/INDEX(${raw}$80:${raw}$149,$V$5)*100,"")',value=100*known[1 if raw=='B' else 2]/active[0][1 if raw=='B' else 2] if known else '')
  put(ref,f'F{row}',formula=f'IF(G{row}=1,D{row}-E{row},"")',value=100*known[1]/active[0][1]-100*known[2]/active[0][2] if known else '')
  put(ref,f'H{row}',formula=f'IF(AND(ISNUMBER(A{row}),A{row}<AH!$P$6,G{row}=1),ROW()-79,0)',value=i+1 if known and known[0]<refdata['pairs']['3986']['ipo_date'] else 0)
 idx=next(i for i,m in enumerate(meta,3) if m['code']=='3986');pre=[x for x in active if x[0]<refdata['pairs']['3986']['ipo_date']]
 for addr,value in [('V1',3+sum(len(refdata['pairs'][m['code']]['rows']) for m in meta[:idx-3])),('V2',len(active)),('V3',6),('V4',0),('V5',1),('V6',len(pre)),('V7',len(pre))]:
  node=cells(ref)[addr];node.attrib.pop('t',None);v=node.find(q('v'));v.text=str(value)
 sort(ref);parts[sheets['AH Reference']]=E.tostring(ref)
 ah=E.fromstring(parts[sheets['AH']]);values=refdata['pairs']['3986']
 for addr,formula,val in [('J89',"IF('AH Reference'!$V$7>1,INDEX('AH Reference'!$D$80:$D$149,'AH Reference'!$V$6)/100-1,\"\")",values['pre_a_return_pct']/100),('L89',"IF('AH Reference'!$V$7>1,INDEX('AH Reference'!$E$80:$E$149,'AH Reference'!$V$6)/100-1,\"\")",values['pre_csi_return_pct']/100),('N89',"IF(AND(ISNUMBER(J89),ISNUMBER(L89)),100*(J89-L89),\"\")",values['pre_excess_pp'])]:put(ah,addr,formula=formula,value=val)
 put(ah,'J91',formula='IF(\'AH Reference\'!$V$7>1,TEXT(INDEX(\'AH Reference\'!$A$80:$A$149,\'AH Reference\'!$V$5),"dd-mmm-yy")&" to "&TEXT(INDEX(\'AH Reference\'!$A$80:$A$149,\'AH Reference\'!$V$6),"dd-mmm-yy"),"Pre-IPO A-line history unavailable")',value=values['pre_from']+' to '+values['pre_to']);sort(ah);parts[sheets['AH']]=E.tostring(ah)
 # Append the authored CSI chart to the existing A/H drawing.
 ar=E.fromstring(parts[sheets['AH'].replace('/worksheets/','/worksheets/_rels/')+'.rels']);draw=next(x.get('Target').lstrip('/') for x in ar if x.get('Type')==R+'/drawing');draw=draw if draw.startswith('xl/') else 'xl/drawings/'+Path(draw).name
 ndrel=E.fromstring(new[nsheets['AH'].replace('/worksheets/','/worksheets/_rels/')+'.rels']);nd=next(x.get('Target').lstrip('/') for x in ndrel if x.get('Type')==R+'/drawing');nd=nd if nd.startswith('xl/') else 'xl/drawings/'+Path(nd).name
 ndoc=E.fromstring(new[nd]);anchor=deepcopy(list(ndoc)[0]);chartnode=anchor.find('.//'+c('chart'));chartnode.set('{'+R+'}id','rIdCSI300')
 drawdoc=E.fromstring(parts[draw]);ids=[int(x.get('id')) for x in drawdoc.iter(xd('cNvPr'))];props=anchor.find('.//'+xd('cNvPr'))
 if props is not None:props.set('id',str(max(ids,default=0)+1));props.set('name','CSI 300 reference')
 drawdoc.append(anchor);parts[draw]=E.tostring(drawdoc)
 drpath=draw.replace('/drawings/','/drawings/_rels/')+'.rels';dr=E.fromstring(parts[drpath]);E.SubElement(dr,'{'+P+'}Relationship',{'Id':'rIdCSI300','Type':R+'/chart','Target':'/xl/charts/chartCSI300.xml'});parts[drpath]=E.tostring(dr)
 nr=E.fromstring(new[nd.replace('/drawings/','/drawings/_rels/')+'.rels']);chartpath=list(nr)[0].get('Target').lstrip('/');chartpath=chartpath if chartpath.startswith('xl/') else 'xl/charts/'+Path(chartpath).name;chartdoc=E.fromstring(new[chartpath])
 for k,ser in enumerate(chartdoc.iter(c('ser'))):
  for name,col in [('cat','A'),('val','D' if k==0 else 'E')]:
   node=ser.find(c(name));node.clear();refnode=E.SubElement(node,c('numRef'));E.SubElement(refnode,c('f')).text=f"'AH Reference'!${col}$80:${col}$149";ca=E.SubElement(refnode,c('numCache'));E.SubElement(ca,c('formatCode')).text='dd-mmm-yy' if name=='cat' else '0.0';E.SubElement(ca,c('ptCount'),{'val':'70'})
   for i,x in enumerate(active):
    value=serial(x[0]) if name=='cat' else 100*x[1+k]/active[0][1+k];E.SubElement(E.SubElement(ca,c('pt'),{'idx':str(i)}),c('v')).text=str(value)
 for axis in chartdoc.iter(c('catAx')):
  axis.tag=c('dateAx')
  for child in list(axis):
   if child.tag in [c('lblAlgn'),c('tickLblSkip'),c('tickMarkSkip'),c('noMultiLvlLbl')]:axis.remove(child)
  num=axis.find(c('numFmt'))
  if num is None:num=E.SubElement(axis,c('numFmt'))
  num.set('formatCode','dd-mmm-yy');num.set('sourceLinked','0');E.SubElement(axis,c('baseTimeUnit'),{'val':'days'})
  order=['axId','scaling','delete','axPos','majorGridlines','minorGridlines','title','numFmt','majorTickMark','minorTickMark','tickLblPos','spPr','txPr','crossAx','crosses','crossesAt','auto','lblOffset','baseTimeUnit','majorUnit','majorTimeUnit','minorUnit','minorTimeUnit','extLst']
  axis[:]=sorted(axis,key=lambda x:order.index(x.tag.split('}')[-1]))
 parts['xl/charts/chartCSI300.xml']=E.tostring(chartdoc);override('xl/charts/chartCSI300.xml','application/vnd.openxmlformats-officedocument.drawingml.chart+xml')
 # No dense daily vertical gridlines on either lock-up chart.
 drel=E.fromstring(parts[drawing.replace('/drawings/','/drawings/_rels/')+'.rels'])
 for relationship in drel:
  path=relationship.get('Target','').lstrip('/');path=path if path.startswith('xl/') else 'xl/charts/'+Path(path).name
  if path not in parts:continue
  doc=E.fromstring(parts[path])
  # Empty category caches made the saved comparison chart collapse into a
  # vertical line in previewers. Cache the real session labels from its source.
  for series in doc.iter(c('ser')):
   category=series.find(c('cat'))
   if category is None:continue
   reference=category.find(c('strRef'))
   if reference is None:continue
   cache=reference.find(c('strCache'))
   if cache is not None and cache.find(c('ptCount')).get('val')!='0':continue
   f=reference.find(c('f')).text;match=re.fullmatch(r"'([^']+)'!\$([A-Z]+)\$(\d+):\$[A-Z]+\$(\d+)",f)
   if not match:continue
   sheet,col,start,end=match.groups();sourcecells=cells(E.fromstring(parts[sheets[sheet]]))
   if cache is not None:reference.remove(cache)
   cache=E.SubElement(reference,c('strCache'));E.SubElement(cache,c('ptCount'),{'val':str(int(end)-int(start)+1)})
   for i,row in enumerate(range(int(start),int(end)+1)):
    label=text(sourcecells.get(col+str(row)),[])
    if label is not None:E.SubElement(E.SubElement(cache,c('pt'),{'idx':str(i)}),c('v')).text=str(label)
  for axis in doc.iter(c('catAx')):
   for n in ['majorGridlines','minorGridlines']:
    x=axis.find(c(n))
    if x is not None:axis.remove(x)
   for name in ['tickLblSkip','tickMarkSkip']:
    x=axis.find(c(name))
    if x is None:x=E.SubElement(axis,c(name))
    x.set('val','15')
  parts[path]=E.tostring(doc)
 # Native desk charts use restrained strokes, sparse date labels and no
 # point markers. Screener's BDH date column must use a real date axis.
 A='http://schemas.openxmlformats.org/drawingml/2006/main';a=lambda n:'{'+A+'}'+n
 for path in ['xl/charts/chart9.xml','xl/charts/chartDeskPeer1.xml','xl/charts/chartDeskPeer2.xml']:
  if path not in parts:continue
  chart=E.fromstring(parts[path])
  for axis in list(chart.iter(c('catAx')))+list(chart.iter(c('dateAx'))):
   axis.tag=c('dateAx')
   for child in list(axis):
    if child.tag in [c('lblAlgn'),c('tickLblSkip'),c('tickMarkSkip'),c('noMultiLvlLbl'),c('majorGridlines'),c('minorGridlines')]:axis.remove(child)
   n=axis.find(c('numFmt'))
   if n is None:n=E.SubElement(axis,c('numFmt'))
   n.set('formatCode','dd-mmm' if path.endswith('chart9.xml') else 'mmm-yy');n.set('sourceLinked','0')
   if axis.find(c('baseTimeUnit')) is None:E.SubElement(axis,c('baseTimeUnit'),{'val':'days'})
   order=['axId','scaling','delete','axPos','majorGridlines','minorGridlines','title','numFmt','majorTickMark','minorTickMark','tickLblPos','spPr','txPr','crossAx','crosses','crossesAt','auto','lblOffset','baseTimeUnit','majorUnit','majorTimeUnit','minorUnit','minorTimeUnit','extLst'];axis[:]=sorted(axis,key=lambda x:order.index(x.tag.split('}')[-1]) if x.tag.split('}')[-1] in order else 99)
  for k,series in enumerate(chart.iter(c('ser'))):
   marker=series.find(c('marker'))
   if marker is None:marker=E.SubElement(series,c('marker'))
   sym=marker.find(c('symbol'))
   if sym is None:sym=E.SubElement(marker,c('symbol'))
   sym.set('val','none')
   smooth=series.find(c('smooth'))
   if smooth is not None:smooth.set('val','0')
   props=series.find(c('spPr'))
   if props is None:props=E.SubElement(series,c('spPr'))
   line=props.find(a('ln'))
   if line is None:line=E.SubElement(props,a('ln'))
   line.set('w','25400')
   for n in list(line):
    if n.tag in [a('solidFill'),a('noFill'),a('gradFill')]:line.remove(n)
   E.SubElement(E.SubElement(line,a('solidFill')),a('srgbClr'),{'val':'315B7D' if k==0 else '9B4A47'})
   series_order=['idx','order','tx','spPr','marker','dPt','dLbls','trendline','errBars','cat','val','smooth','extLst'];series[:]=sorted(series,key=lambda x:series_order.index(x.tag.split('}')[-1]) if x.tag.split('}')[-1] in series_order else 99)
  if path.endswith('chart9.xml'):
   legend=chart.find('.//'+c('legend'));parent=next((x for x in chart.iter() if legend in list(x)),None) if legend is not None else None
   if parent is not None:parent.remove(legend)
  parts[path]=E.tostring(chart)
 styles.find(q('cellXfs')).set('count',str(len(styles.find(q('cellXfs')))));parts['xl/styles.xml']=E.tostring(styles)
 parts['xl/workbook.xml']=E.tostring(wb);parts['xl/_rels/workbook.xml.rels']=E.tostring(wr);parts['[Content_Types].xml']=E.tostring(content)
 with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
  for path,raw in parts.items():z.writestr(path,raw)
 return Path(dest)
if __name__=='__main__':
 root=Path(__file__).resolve().parent.parent;patch(sys.argv[1],sys.argv[2],root);print('Patched presentation, live BQL valuations and CSI reference')
