"""Verified share-ratio adjustments for chart history, excluding cash dividends."""
import json,re,math
from datetime import date
import xml.etree.ElementTree as E
from ah_basis import review_for,adjusted_premium
from market_universe import histories
from reflow_monitors import nodes,put,value,sort,serial,ec,ci,c,q

def apply(parts,sheets,root):
 records=histories(root)['pairs'];meta=json.loads((root/'data/desk_chart_data.json').read_text())['pairs'];count=len(meta)+2
 delta=E.fromstring(parts[sheets['AH Delta']]);ah=E.fromstring(parts[sheets['AH']]);chart=E.fromstring(parts[sheets['Chart Data']]);compare=E.fromstring(parts[sheets['AH Compare']]);raw={r['code']:r for r in records};caches={}
 for i,m in enumerate(meta,3):
  rv=review_for(m['code'],root);events=rv.get('events',[rv]) if rv else []
  assert len(events)<=3,'Extend the explicit corporate-action schedule before charting additional events'
  for k,col in enumerate(['R','S','T']):put(delta,col+str(i),v=events[k]['ratio'] if k<len(events) else 1)
  for col,v in [('B',m['stored_7']),('C',m['stored_1m']),('D',m['stored_7']),('E',m['stored_1m'])]:
   n=nodes(delta).get(col+str(i))
   if n is not None:
    for x in list(n):
     if x.tag in [q('v'),q('is')]:n.remove(x)
    n.attrib.pop('t',None)
    if v is None:n.set('t','str');E.SubElement(n,q('v')).text=''
    else:E.SubElement(n,q('v')).text=str(v)
  # Live trailing reference prices use the same three-event adjustment.
  start=(i-3)*70+5;end=start+64
  for dest,target,stored in [('D','TODAY()-7','B'),('E','EDATE(TODAY(),-1)','C')]:
   hd=f"INDEX('AH Recent'!$A${start}:$A${end},MATCH({target},'AH Recent'!$A${start}:$A${end},1))";hp=f"INDEX('AH Recent'!$B${start}:$B${end},MATCH({target},'AH Recent'!$A${start}:$A${end},1))"
   v=lambda d,p:f"INDEX('AH Recent'!${p}${start}:${p}${end},MATCH({hd},'AH Recent'!${d}${start}:${d}${end},1))"
   ap,fx,ad,fd=v('D','E'),v('G','H'),v('D','D'),v('G','G')
   factors='*'.join(f'IF(AND(${hc}{i}>0,${ac}{i}>0),IF({ad}>=${ac}{i},${ratio}{i},1)/IF({hd}>=${hc}{i},${ratio}{i},1),1)' for hc,ac,ratio in [('J','K','R'),('L','M','S'),('O','P','T')])
   put(delta,dest+str(i),v=m['stored_7' if dest=='D' else 'stored_1m'] if m['stored_7' if dest=='D' else 'stored_1m'] is not None else '',f=f'IF(AH!$E$4="Stored",IF(ISNUMBER({stored}{i}),{stored}{i},""),IFERROR(IF(AND(ISNUMBER({hd}),{target}-{hd}<=10,{hd}<={target},{hp}>0,{ap}>0,{fx}>0,{ad}<={hd},{fd}<={hd},{hd}-{ad}<=10,{hd}-{fd}<=5),{ap}*{fx}/{hp}*{factors}-1,""),""))')
  latest=raw[m['code']].get('latest_premium_pct')
  for col,key in [('G','stored_7'),('H','stored_1m')]:
   n=nodes(ah)[col+str(i+5)];n.attrib.pop('t',None);old=n.find(q('v'))
   if old is not None:n.remove(old)
   if latest is None or m[key] is None:n.set('t','str');E.SubElement(n,q('v')).text=''
   else:E.SubElement(n,q('v')).text=str(latest-100*m[key])
 def factors(index,h,ad):
  m=lambda col:f'IFERROR(INDEX(\'AH Delta\'!${col}$3:${col}${count},{index}),0)'
  return '*'.join(f'IF(AND({m(hc)}>0,{m(ac)}>0),IF({ad}>={m(ac)},{m(ratio)},1)/IF({h}>={m(hc)},{m(ratio)},1),1)' for hc,ac,ratio in [('J','K','R'),('L','M','S'),('O','P','T')])
 chartcells=nodes(chart);compcells=nodes(compare)
 for row in range(5,2205):
  n=chartcells.get('B'+str(row))
  if n is None:continue
  formula=f'IFERROR(IF(AND(AH!$P$9<>1,$C{row}>0,$D{row}>0,$E{row}>0,$F{row}>0,$G{row}>0,$F{row}<=$A{row},$G{row}<=$A{row},$A{row}-$F{row}<=10,$A{row}-$G{row}<=5),$D{row}*$E{row}/$C{row}*{factors("AH!$P$3",f"$A{row}",f"$F{row}")}-1,NA()),NA())'
  n.find(q('f')).text=formula
 selected=[value(nodes(ah).get(a)) for a in ['B4','K28','K29','K30']]
 def observations(code):
  r=raw.get(code,{});by={x[0]:x for x in r.get('history',[])};rv=review_for(code,root);blocked='share-scale' in r.get('exclusion','') and not rv
  return [adjusted_premium(rv,by[dt]) if dt in by and not blocked else None for dt,_ in r.get('h_history',[])]
 caches['AHChartPremium']=observations(selected[0])
 for k,(h,hp,ap,fx,ad,fd,out,idx) in enumerate([('A','B','C','D','E','F','G','H'),('J','K','L','M','N','O','P','Q'),('S','T','U','V','W','X','Y','Z'),('AB','AC','AD','AE','AF','AG','AH','AI')]):
  vals=observations(selected[k]);caches[f'AHCompare{k+1}Premium']=vals
  for row in range(5,2205):
   n=compcells.get(out+str(row))
   if n is None:continue
   n.find(q('f')).text=f'IFERROR(IF(AND(IFERROR(INDEX(\'Market Data\'!$Z$3:$Z${count},${idx}$2),1)<>1,ISNUMBER(${h}{row}),${hp}{row}>0,${ap}{row}>0,${fx}{row}>0,${ad}{row}>0,${fd}{row}>0,${ad}{row}<=${h}{row},${fd}{row}<=${h}{row},${h}{row}-${ad}{row}<=10,${h}{row}-${fd}{row}<=5),${ap}{row}*${fx}{row}/${hp}{row}*{factors(f"${idx}$2",f"${h}{row}",f"${ad}{row}")}-1,NA()),NA())'
   if row-5<len(vals):
    v=vals[row-5];old=n.find(q('v'))
    if old is not None:n.remove(old)
    n.attrib.pop('t',None)
    if v is None:n.set('t','e');E.SubElement(n,q('v')).text='#N/A'
    else:E.SubElement(n,q('v')).text=str(v)
 for row,v in enumerate(caches['AHChartPremium'],5):
  n=chartcells.get('B'+str(row))
  if n is None:continue
  old=n.find(q('v'))
  if old is not None:n.remove(old)
  n.attrib.pop('t',None)
  if v is None:n.set('t','e');E.SubElement(n,q('v')).text='#N/A'
  else:E.SubElement(n,q('v')).text=str(v)
 for addr in ['J55','J57']:put(ah,addr,v='')
 put(ah,'J27',v='Compare capital-adjusted premiums',style=nodes(ah)['J27'].get('s'))
 for name,doc in [('AH Delta',delta),('AH',ah),('Chart Data',chart),('AH Compare',compare)]:sort(doc);parts[sheets[name]]=E.tostring(doc)
 for path,rawxml in list(parts.items()):
  if not path.startswith('xl/charts/') or not path.endswith('.xml'):continue
  doc=E.fromstring(rawxml);changed=False
  for ref in doc.iter(c('numRef')):
   f=ref.find(c('f'));formula=f.text or '' if f is not None else '';key=next((k for k in caches if formula.endswith('!'+k)),None)
   if key is None:continue
   old=ref.find(c('numCache'))
   if old is not None:ref.remove(old)
   cache=E.SubElement(ref,c('numCache'));E.SubElement(cache,c('formatCode')).text='0.0%';E.SubElement(cache,c('ptCount'),{'val':str(len(caches[key]))})
   for i,v in enumerate(caches[key]):
    if v is not None and math.isfinite(v):E.SubElement(E.SubElement(cache,c('pt'),{'idx':str(i)}),c('v')).text=str(v)
   changed=True
  if changed:
   title=doc.find('.//'+c('title'))
   if title is not None:
    texts=list(title.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'))
    if texts:texts[0].text='Capital-adjusted A/H premium';[setattr(n,'text','') for n in texts[1:]]
   parts[path]=E.tostring(doc)
