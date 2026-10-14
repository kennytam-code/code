"""Premium / A-price / CSI 300 chart on one dated, capital-adjusted timeline."""
import json,math,re
from copy import deepcopy
from datetime import date,timedelta
from bisect import bisect_right
import xml.etree.ElementTree as E
from reflow_monitors import nodes,sort,value,serial,q,c,xd,drawing_path
from patch_peer_workbook import R,P

_writers={}
def put(doc,addr,v=None,f=None,style=None):
 key=id(doc)
 if key not in _writers:
  data=doc.find(q('sheetData'));_writers[key]=(data,{int(r.get('r')):r for r in data},nodes(doc))
 data,rows,cells=_writers[key];r=int(re.search(r'\d+',addr)[0]);row=rows.get(r)
 if row is None:row=E.SubElement(data,q('row'),{'r':str(r)});rows[r]=row
 old=cells.get(addr)
 if old is not None:row.remove(old)
 n=E.SubElement(row,q('c'),{'r':addr});cells[addr]=n
 if style is not None:n.set('s',str(style))
 if f is not None:E.SubElement(n,q('f')).text=f
 if isinstance(v,str):
  n.set('t','str' if f else 'inlineStr')
  if f:E.SubElement(n,q('v')).text=v
  else:E.SubElement(E.SubElement(n,q('is')),q('t')).text=v
 elif v is not None:E.SubElement(n,q('v')).text=str(v)
 elif f is not None:n.set('t','str');E.SubElement(n,q('v')).text=''
 return n

def apply(parts,sheets,root):
 _writers.clear();meta=json.loads((root/'data/desk_chart_data.json').read_text())['pairs'];refdata=json.loads((root/'data/ah_reference.json').read_text());benchmark=json.loads((root/'data/csi300_prices.json').read_text());end=len(meta)+2;ref=E.fromstring(parts[sheets['AH Reference']]);ah=E.fromstring(parts[sheets['AH']]);cursor=3
 # Store factual common A / CSI observations once, plus the complete benchmark calendar.
 for i,m in enumerate(meta,3):
  rows=refdata['pairs'][m['code']]['trend_rows'];put(ref,'AG'+str(i),v=cursor);put(ref,'AH'+str(i),v=len(rows))
  for dt,a,b in rows:
   for col,v in [('AK',serial(dt)),('AL',a),('AM',b)]:put(ref,col+str(cursor),v=v)
   cursor+=1
 bs=benchmark['closes'];bend=len(bs)+2
 for row,(dt,px) in enumerate(bs,3):put(ref,'AE'+str(row),v=serial(dt));put(ref,'AF'+str(row),v=px)
 put(ref,'BB5',f='IF(AND(AH!$E$4="Bloomberg",AH!$P$3>0),BDH("SHSZ300 Index","PX_LAST",AH!$P$6-31,TODAY(),"Dts=S","Dir=V","Sort=A","Days=T","Per=cd"),"")')
 # One selected-stock request. The earlier around-IPO requests are superseded.
 for addr in ['W4','AA4']:put(ref,addr,v='')
 put(ref,'AZ1',f=f'IFERROR(INDEX($AG$3:$AG${end},AH!$P$3),0)')
 put(ref,'AZ2',f=f'IFERROR(INDEX($AH$3:$AH${end},AH!$P$3),0)')
 put(ref,'AZ3',f='IF(ISNUMBER(BB5),1,IF(ISNUMBER(BB6),2,3))')
 pre=f'COUNTIFS($AE$3:$AE${bend},">="&AH!$P$6-31,$AE$3:$AE${bend},"<"&AH!$P$6)'
 put(ref,'AZ4',f=f'IF(AH!$E$4="Stored",{pre},COUNTIFS($BB$5:$BB$2204,">="&AH!$P$6-31,$BB$5:$BB$2204,"<"&AH!$P$6))')
 put(ref,'AZ5',f='MIN(2200,$AZ$4+AH!$P$11)')
 put(ref,'AZ6',f='IFERROR(MATCH(1,$BH$5:$BH$2204,0),0)')
 put(ref,'AZ7',f=f'IFERROR(MATCH(AH!$P$6-31,$AE$3:$AE${bend},1)+IF(INDEX($AE$3:$AE${bend},MATCH(AH!$P$6-31,$AE$3:$AE${bend},1))<AH!$P$6-31,1,0),1)')
 rawend=cursor-1
 def lookup(day,dates,prices):return f'IFERROR(IF(AND(ISNUMBER(INDEX({dates},MATCH({day},{dates},1))),INDEX({dates},MATCH({day},{dates},1))<={day},{day}-INDEX({dates},MATCH({day},{dates},1))<=10),INDEX({prices},MATCH({day},{dates},1)),NA()),NA())'
 from ah_basis import review_for,share_multiplier,adjusted_premium
 from market_universe import histories
 selected=value(nodes(ah)['B4']);rec=next(r for r in histories(root)['pairs'] if r['code']==selected);trend=refdata['pairs'][selected]['trend_rows'];start=(date.fromisoformat(rec['ipo_date'])-timedelta(days=31)).isoformat();pre_dates=[dt for dt,_ in bs if start<=dt<rec['ipo_date']];timeline=pre_dates+[dt for dt,_ in rec['h_history']];td=[x[0] for x in trend];bd=[x[0] for x in bs];bm=dict(bs);rawby={x[0]:x for x in rec['history']};rv=review_for(selected,root)
 def prior(day,dates,prices):
  i=bisect_right(dates,day)-1
  return prices[i] if i>=0 and (date.fromisoformat(day)-date.fromisoformat(dates[i])).days<=10 else None
 astored=[prior(dt,td,[x[1] for x in trend]) for dt in timeline];cstored=[prior(dt,bd,[x[1] for x in bs]) for dt in timeline];joint=next((i for i,(a,b) in enumerate(zip(astored,cstored)) if a is not None and b is not None),None);base=next((i for i,b in enumerate(cstored) if b is not None),None)
 caches=[[],[],[],[]]
 for row in range(5,2205):
  k=row-5;dt=timeline[k] if k<len(timeline) else None;n=k+1
  # Before the H IPO, use actual CSI sessions; afterwards use actual H sessions.
  datef=f'IF(OR(AH!$P$3=0,ROW()-4>$AZ$5),"",IF(ROW()-4<=$AZ$4,IF(AH!$E$4="Stored",INDEX($AE$3:$AE${bend},$AZ$7+ROW()-5),IFERROR(INDEX($BB$5:$BB$2204,$AZ$3+ROW()-6),"")),IFERROR(INDEX(\'Chart Data\'!$A$5:$A$2204,ROW()-4-$AZ$4),"")))'
  put(ref,'BD'+str(row),v=serial(dt) if dt else '',f=datef)
  put(ref,'BE'+str(row),v=adjusted_premium(rv,rawby[dt]) if dt in rawby and dt>=rec['ipo_date'] else None,f=f'IFERROR(IF(AND(ISNUMBER(BD{row}),BD{row}>=AH!$P$6),INDEX(\'Chart Data\'!$B$5:$B$2204,MATCH(BD{row},\'Chart Data\'!$A$5:$A$2204,0)),NA()),NA())')
  bformula=lookup(f'BD{row}',f'$AE$3:$AE${bend}',f'$AF$3:$AF${bend}');blive=lookup(f'BD{row}','$BB$5:$BB$2204','$BC$5:$BC$2204')
  put(ref,'BJ'+str(row),v=cstored[k] if dt else None,f=f'IFERROR(IF(ISNUMBER(BD{row}),IF(AH!$E$4="Stored",{bformula},{blive}),NA()),NA())')
  stored=lookup(f'BD{row}',f'INDEX($AK$3:$AK${rawend},$AZ$1-2):INDEX($AK$3:$AK${rawend},$AZ$1+$AZ$2-3)',f'INDEX($AL$3:$AL${rawend},$AZ$1-2):INDEX($AL$3:$AL${rawend},$AZ$1+$AZ$2-3)')
  live=lookup(f'BD{row}',"'Live History'!$D$5:$D$2204","'Live History'!$E$5:$E$2204")
  ad=f'IFERROR(INDEX(\'Live History\'!$D$5:$D$2204,MATCH(BD{row},\'Live History\'!$D$5:$D$2204,1)),0)'
  def m(col):return f'INDEX(\'AH Delta\'!${col}$3:${col}${end},AH!$P$3)'
  factor='*'.join(f'IF({m(ac)}>0,IF({ad}>={m(ac)},{m(ratio)},1)/IF(TODAY()>={m(ac)},{m(ratio)},1),1)' for ac,ratio in [('K','R'),('M','S'),('P','T')])
  put(ref,'BK'+str(row),v=astored[k] if dt else None,f=f'IFERROR(IF(ISNUMBER(BD{row}),IF(AH!$E$4="Stored",{stored},{live}*{factor}),NA()),NA())')
  put(ref,'BH'+str(row),v=int(dt is not None and cstored[k] is not None) if dt else 0,f=f'IF(AND(ISNUMBER(BJ{row}),BJ{row}>0),1,0)')
  put(ref,'BI'+str(row),v=int(dt is not None and astored[k] is not None and cstored[k] is not None) if dt else 0,f=f'IF(AND(ISNUMBER(BJ{row}),BJ{row}>0,ISNUMBER(BK{row}),BK{row}>0),1,0)')
  for out,raw in [('BF','BJ'),('BG','BK')]:
   v=None
   if dt and base is not None:
    series=cstored if raw=='BJ' else astored
    if series[k] is not None and series[base] is not None:v=series[k]/series[base]-1
   put(ref,out+str(row),v=v,f=f'IFERROR(IF(AND($AZ$6>0,ISNUMBER({raw}{row}),{raw}{row}>0),{raw}{row}/INDEX(${raw}$5:${raw}$2204,$AZ$6)-1,NA()),NA())')
  if dt:
   caches[0].append(serial(dt));caches[1].append(adjusted_premium(rv,rawby[dt]) if dt in rawby and dt>=rec['ipo_date'] else None);caches[2].append(cstored[k]/cstored[base]-1 if base is not None and cstored[k] is not None else None);caches[3].append(astored[k]/astored[base]-1 if base is not None and astored[k] is not None and astored[base] is not None else None)
 # Populate the saved selected history without Bloomberg or external recalculation.
 for addr,v in [('AZ1',3+sum(len(refdata['pairs'][m['code']]['trend_rows']) for m in meta[:next(i for i,m in enumerate(meta) if m['code']==selected)])),('AZ2',len(trend)),('AZ3',3),('AZ4',len(pre_dates)),('AZ5',len(timeline)),('AZ6',base+1 if base is not None else 0),('AZ7',next(i+1 for i,(dt,_) in enumerate(bs) if dt>=start))]:
  n=nodes(ref)[addr];n.attrib.pop('t',None);vnode=n.find(q('v'))
  if vnode is None:vnode=E.SubElement(n,q('v'))
  vnode.text=str(v)
 sort(ref);parts[sheets['AH Reference']]=E.tostring(ref)
 # Reuse the authored premium chart and add a separate right-hand market-return axis.
 dp=drawing_path(parts,sheets['AH']);drp=dp.replace('/drawings/','/drawings/_rels/')+'.rels';draw=E.fromstring(parts[dp]);rels=E.fromstring(parts[drp]);removed=[]
 for anchor in list(draw):
  props=anchor.find('.//'+xd('cNvPr'))
  if props is not None and props.get('name')=='CSI 300 reference':removed.append(anchor.find('.//'+c('chart')).get('{'+R+'}id'));draw.remove(anchor)
 for x in list(rels):
  if x.get('Id') in removed:rels.remove(x)
 # Identify the individual premium chart through its original named series.
 path=next(p for p,raw in parts.items() if p.startswith('xl/charts/') and p.endswith('.xml') and b'!AHChartPremium' in raw);doc=E.fromstring(parts[path]);plot=doc.find('.//'+c('plotArea'));line=plot.find(c('lineChart'));primary=line.find(c('ser'))
 def bind(ser,col,cache,label,idx):
  ser.find(c('idx')).set('val',str(idx));ser.find(c('order')).set('val',str(idx));tx=ser.find(c('tx'))
  if tx is not None:ser.remove(tx)
  tx=E.Element(c('tx'));E.SubElement(tx,c('v')).text=label;ser.insert(2,tx)
  for tag,source,values,fmt in [('cat','BD',caches[0],'dd-mmm-yy'),('val',col,cache,'0.0%')]:
   n=ser.find(c(tag));n.clear();nr=E.SubElement(n,c('numRef'));E.SubElement(nr,c('f')).text="'AH Reference'!"+{'BD':'AHMarketDates','BE':'AHMarketPremium','BF':'AHMarketCSI','BG':'AHMarketA'}[source];ca=E.SubElement(nr,c('numCache'));E.SubElement(ca,c('formatCode')).text=fmt;E.SubElement(ca,c('ptCount'),{'val':str(len(values))})
   for i,v in enumerate(values):
    if v is not None and math.isfinite(v):E.SubElement(E.SubElement(ca,c('pt'),{'idx':str(i)}),c('v')).text=str(v)
  smooth=ser.find(c('smooth'))
  if smooth is not None:smooth.set('val','0')
 wb=E.fromstring(parts['xl/workbook.xml']);names=wb.find(q('definedNames'))
 if names is None:names=E.SubElement(wb,q('definedNames'))
 for col,label in [('BD','AHMarketDates'),('BE','AHMarketPremium'),('BF','AHMarketCSI'),('BG','AHMarketA')]:
  n=next((n for n in names if n.get('name')==label),None)
  if n is None:n=E.SubElement(names,q('definedName'),{'name':label})
  n.text=f"'AH Reference'!${col}$5:INDEX('AH Reference'!${col}$5:${col}$2204,MAX(1,'AH Reference'!$AZ$5))"
 parts['xl/workbook.xml']=E.tostring(wb)
 bind(primary,'BE',caches[1],'A/H premium · left',0)
 secondary=deepcopy(line)
 for n in list(secondary):
  if n.tag==c('ser'):secondary.remove(n)
 for k,(col,vals,label,color) in enumerate([('BF',caches[2],'CSI 300 return · right','757F88'),('BG',caches[3],'A-share return · right','9B4A47')],1):
  ser=deepcopy(primary);bind(ser,col,vals,label,k);sp=ser.find(c('spPr'));ln=sp.find('{http://schemas.openxmlformats.org/drawingml/2006/main}ln') if sp is not None else None
  if ln is not None:
   for child in list(ln):ln.remove(child)
   E.SubElement(E.SubElement(ln,'{http://schemas.openxmlformats.org/drawingml/2006/main}solidFill'),'{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr',{'val':color})
  secondary.insert(2+k,ser)
 axes=list(secondary.findall(c('axId')))
 for node,aid in zip(axes,[777001,777002]):node.set('val',str(aid))
 insert=list(plot).index(line)+1;order=['grouping','varyColors','ser','dLbls','dropLines','hiLowLines','upDownBars','marker','smooth','axId','extLst'];secondary[:]=sorted(secondary,key=lambda n:order.index(n.tag.split('}')[-1]) if n.tag.split('}')[-1] in order else 99);plot.insert(insert,secondary)
 xaxis=plot.find(c('dateAx'));yaxis=plot.find(c('valAx'));sx=deepcopy(xaxis);sy=deepcopy(yaxis)
 sx.find(c('axId')).set('val','777001');sx.find(c('crossAx')).set('val','777002');sx.find(c('delete')).set('val','1')
 sy.find(c('axId')).set('val','777002');sy.find(c('crossAx')).set('val','777001');sy.find(c('axPos')).set('val','r');sy.find(c('crosses')).set('val','max')
 for grid in list(sy.findall(c('majorGridlines'))):sy.remove(grid)
 for axis in [yaxis,sy]:
  scaling=axis.find(c('scaling'))
  for child in list(scaling):
   if child.tag in [c('min'),c('max')]:scaling.remove(child)
  num=axis.find(c('numFmt'))
  if num is not None:num.set('formatCode','0%');num.set('sourceLinked','0')
 plot.append(sx);plot.append(sy)
 chart=doc.find(c('chart'));legend=chart.find(c('legend'))
 if legend is None:
  legend=E.Element(c('legend'));E.SubElement(legend,c('legendPos'),{'val':'b'});E.SubElement(legend,c('overlay'),{'val':'0'});chart.insert(list(chart).index(plot)+1,legend)
 texts=list(doc.find('.//'+c('title')).iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'))
 if texts:texts[0].text='A/H premium and mainland market';[setattr(t,'text','') for t in texts[1:]]
 for l in doc.iter(c('lineChart')):
  for s in l.findall(c('ser')):
   order=['idx','order','tx','spPr','marker','dPt','dLbls','trendline','errBars','cat','val','smooth','extLst'];s[:]=sorted(s,key=lambda n:order.index(n.tag.split('}')[-1]) if n.tag.split('}')[-1] in order else 99)
 parts[path]=E.tostring(doc);parts[dp]=E.tostring(draw);parts[drp]=E.tostring(rels)
 # Remove the obsolete separate CSI panel and bulky captions.
 merges=ah.find(q('mergeCells'))
 if merges is not None:
  for m in list(merges):
   if int(re.search(r'\d+',m.get('ref'))[0])>=65:merges.remove(m)
  merges.set('count',str(len(merges)))
 for addr,n in list(nodes(ah).items()):
  if int(re.search(r'\d+',addr)[0])>=65 and 10<=__import__('reflow_monitors').ci(re.match('[A-Z]+',addr)[0])<=15:put(ah,addr,v='',style=n.get('s'))
 sort(ah);parts[sheets['AH']]=E.tostring(ah)
