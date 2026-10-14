"""Native, bounded fixes for A/H coverage, live valuations and selected codes."""
import json,re
from copy import deepcopy
import xml.etree.ElementTree as E
from openpyxl.formula.translate import Translator
from reflow_monitors import nodes,put,value,sort,serial,ec,ci,q
from patch_peer_workbook import R
from market_universe import histories
from ah_basis import review_for

def apply(parts,sheets,root):
 meta=json.loads((root/'data/desk_chart_data.json').read_text())['pairs'];records={r['code']:r for r in histories(root)['pairs']};deals=json.loads((root/'data/deals.json').read_text())['deals'];md=E.fromstring(parts[sheets['Market Data']]);ah=E.fromstring(parts[sheets['AH']]);delta=E.fromstring(parts[sheets['AH Delta']]);history=E.fromstring(parts[sheets['AH History']]);recent=E.fromstring(parts[sheets['AH Recent']]);mdb=nodes(md);existing={value(n):int(re.search(r'\d+',a)[0]) for a,n in mdb.items() if re.fullmatch(r'P\d+',a) and int(a[1:])>=3};known=len(existing);end=len(meta)+2
 live=nodes(E.fromstring(parts[sheets['IPO Live']]));hr={value(n):int(a[1:]) for a,n in live.items() if re.fullmatch(r'A\d+',a) and int(a[1:])>=8}
 for i,m in enumerate(meta,3):
  if m['code']=='9976':
   put(md,'C'+str(hr[m['h_ticker']]),v='Technology');put(md,'D'+str(hr[m['h_ticker']]),v='Semiconductors')
  if m['code'] in existing:continue
  # Append instead of moving the existing cache offsets / native formula rows.
  assert i==known+3,(i,known)
  for doc,oldrow,newrow in [(md,known+2,i),(delta,known+2,i),(ah,known+7,i+5)]:
   old=nodes(doc)
   for a,n in list(old.items()):
    if int(re.search(r'\d+',a)[0])!=oldrow:continue
    dest=re.match('[A-Z]+',a)[0]+str(newrow);copy=deepcopy(n);copy.set('r',dest);f=copy.find(q('f'))
    if f is not None:f.text=Translator('='+f.text,origin=a).translate_formula(dest).lstrip('=')
    from reflow_monitors import place
    place(doc,copy)
  rec=records[m['code']];d=next(d for d in deals if d['code']==m['code']);hs=rec['h_history'];by={p[0]:p for p in rec['history']};last=rec['history'][-1]
  for col,v in zip(['P','Q','R','S','T','U','V','W','X','Y','Z','AA','AB','AF','AG','AH','AI','AJ'],[m['code'],m['h_ticker'],m['a_ticker'],m['name'],d['sector'],d['subsector'],serial(m['ipo_date']),rec.get('offer_reference_premium_pct',0)/100,m['cache_start'],len(hs),0,m['raw_debut'],serial(m['latest_date']),last[2],last[1],last[3],serial(last[5]),serial(last[6])]):put(md,col+str(i),v=v,style=mdb.get(col+str(known+2),E.Element('x')).get('s'))
  put(md,'AD'+str(i),v=last[1],f=f'IF(AH!$E$4="Bloomberg",\'IPO Live\'!D{hr[m["h_ticker"]]},AG{i})')
  for offset,(dt,h) in enumerate(hs,m['cache_start']):
   p=by.get(dt)
   for col,v in zip(['A','B','C','D','E','F'],[serial(dt),h,p[2] if p else None,p[3] if p else None,serial(p[5]) if p else None,serial(p[6]) if p else None]):put(history,col+str(offset),v=v,style=nodes(history).get(col+'2',E.Element('x')).get('s'))
  for col,v in [('A',m['code']),('F',serial(m['ipo_date'])),('G',m['raw_debut']),('H',m['h_ticker']),('I',m['a_ticker']),('N',serial(m['latest_date']))]:put(delta,col+str(i),v=v)
  for col in ['J','K','L','M','O','P']:put(delta,col+str(i),v=0)
  for col in ['R','S','T']:put(delta,col+str(i),v=1)
  # The selected recent-history build contains one 70-row reserved zone per pair.
  oldnodes=nodes(recent);first=(known-1)*70+5
  for a,n in list(oldnodes.items()):
   r=int(re.search(r'\d+',a)[0])
   if first<=r<first+70:
    dest=re.match('[A-Z]+',a)[0]+str(r+70);copy=deepcopy(n);copy.set('r',dest);f=copy.find(q('f'))
    if f is not None:f.text=Translator('='+f.text,origin=a).translate_formula(dest).lstrip('=').replace('$'+str(known+2),'$'+str(i))
    from reflow_monitors import place
    place(recent,copy)
  known+=1
 # Refresh displayed cached values for the complete roster, including an appended pair.
 for i,m in enumerate(meta,3):
  d=next(d for d in deals if d['code']==m['code']) if any(d['code']==m['code'] for d in deals) else None
  r=records[m['code']];cn=nodes(ah)
  for col,v in [('A',m['a_ticker']),('B',m['h_ticker']),('C',m['name'] and r['sector']),('D',r['subsector']),('E',r.get('offer_reference_premium_pct',0)/100 if r.get('offer_reference_premium_pct') is not None else ''),('F',r.get('latest_premium_pct',0)/100 if r.get('latest_premium_pct') is not None else '')]:
   n=cn[col+str(i+5)];f=n.find(q('f'));put(ah,col+str(i+5),v=v,f=f.text if f is not None else None,style=n.get('s'))
 for doc in [ah,history,delta,recent]:
  dim=doc.find(q('dimension'))
  if dim is not None:
   ns=nodes(doc);dim.set('ref','A1:'+ec(max(ci(re.match('[A-Z]+',a)[0]) for a in ns))+str(max(int(re.search(r'\d+',a)[0]) for a in ns)))
 for name,doc in [('Market Data',md),('AH',ah),('AH Delta',delta),('AH History',history),('AH Recent',recent)]:sort(doc);parts[sheets[name]]=E.tostring(doc)
 # All lookup boundaries follow the current roster, including Artifact-authored comparison helpers.
 history_end=max(int(re.search(r'\d+',a)[0]) for a in nodes(history))
 for name in ['AH','AH Compare','AH Compare Live','AH Reference','Chart Data','AH Recent']:
  doc=E.fromstring(parts[sheets[name]])
  for f in doc.iter(q('f')):
   f.text=re.sub(r"('AH History'!\$([A-Z]+)\$1:\$\2\$)\d+",lambda m:m[1]+str(history_end),f.text or '')
   f.text=re.sub(r"((?:'Market Data'|'AH Delta')!\$([A-Z]+)\$3:\$\2\$)\d+",lambda m:m[1]+str(end),f.text or '')
  if name=='AH':
   put(doc,'P10',v=0,f='IFERROR(IF(AND($E$4="Bloomberg",$P$3>0,COUNT(\'Live History\'!$A$5:$A$2204)>0,COUNT(\'Live History\'!$D$5:$D$2204)>0,COUNT(\'Live History\'!$G$5:$G$2204)>0,MIN(\'Live History\'!$A$5:$A$2204)>=$P$6,MAX(\'Live History\'!$A$5:$A$2204)<=TODAY(),MAX(\'Live History\'!$A$5:$A$2204)>=MIN(TODAY()-8,$P$17)),1,0),0)')
   put(doc,'A5',v=f'{len(meta)} A/H pairs · Stored through {histories(root)["asof"]}',f=f'IF($E$4="Stored","{len(meta)} A/H pairs | Stored through {histories(root)["asof"]}","{len(meta)} A/H pairs | Bloomberg through TODAY")',style=nodes(doc)['A5'].get('s'))
   put(doc,'P13',v=1,f="IFERROR(MATCH(MIN('Live History'!$A$5:$A$2204),'Live History'!$A$5:$A$2204,0),1)")
   # Snapshot agreement remains a diagnostic, never a prerequisite for a live chart.
  if name=='AH Compare':
   for dest,start in [('I2','A'),('R2','J'),('AA2','S'),('AJ2','AB')]:
    idx={'I2':'H','R2':'Q','AA2':'Z','AJ2':'AI'}[dest];raw='\'AH Compare Live\'!$'+start+'$5:$'+start+'$2204'
    put(doc,dest,v=0,f=f'IFERROR(IF(AND(AH!$E$4="Bloomberg",${idx}$2>0,COUNT({raw})>0,MIN({raw})>=INDEX(\'AH Delta\'!$F$3:$F${end},${idx}$2),MAX({raw})<=TODAY(),MAX({raw})>=MIN(TODAY()-8,INDEX(\'AH Delta\'!$N$3:$N${end},${idx}$2))),1,0),0)')
  if name=='AH Compare':
   for col in ['A','J','S','AB']:
    for n in doc.iter(q('c')):
     if re.fullmatch(col+r'[5-9][0-9]*',n.get('r','')) or re.fullmatch(col+r'[1-9][0-9]+',n.get('r','')):
      f=n.find(q('f'))
      if f is not None:f.text=re.sub(r"MATCH\(IFERROR\(INDEX\('AH Delta'!\$F\$3:\$F\$\d+,\$[A-Z]+\$2\),0\),'AH Compare Live'!\$([A-Z]+)\$5:\$\1\$2204,0\)",lambda m:f"MATCH(MIN('AH Compare Live'!${m[1]}$5:${m[1]}$2204),'AH Compare Live'!${m[1]}$5:${m[1]}$2204,0)",f.text)
  sort(doc);parts[sheets[name]]=E.tostring(doc)
 wb=E.fromstring(parts['xl/workbook.xml'])
 for n in wb.iter(q('definedName')):
  if n.get('name')=='AHPairList':n.text=f"'Market Data'!$P$3:$P${end}"
 parts['xl/workbook.xml']=E.tostring(wb)
 for path,raw in list(parts.items()):
  if path.startswith('xl/tables/') and path.endswith('.xml'):
   doc=E.fromstring(raw)
   if doc.get('name')=='AHLivePairs':
    doc.set('ref',f'A7:H{len(meta)+7}');af=doc.find(q('autoFilter'))
    if af is not None:af.set('ref',doc.get('ref'))
    parts[path]=E.tostring(doc)
 # TTM BDP requests are scalar. BQL is a separate clear, header-tolerant fallback area.
 from patch_presentation_workbook import extracted,QUERIES
 val=E.fromstring(parts[sheets['Valuation Data']]);db=E.fromstring(parts[sheets['Database']]);verify=E.fromstring(parts[sheets['BBG Verify']]);screen=E.fromstring(parts[sheets['Screener']])
 def request(row,ac,bc,dc,out,field,query,ticker):
  put(val,ac+str(row),f=f'IF({ticker}="","",IFERROR(BDP({ticker},"{field}"),""))')
  put(val,bc+str(row),f=f'IF(AND({ticker}<>"",NOT(ISNUMBER({ac}{row}))),BQL({ticker},"{query}"),"")')
  fallback=extracted(bc,dc,row).lstrip('=');put(val,out+str(row),v='Unavailable',f=f'IF(ISNUMBER({ac}{row}),{ac}{row},{fallback})')
 for i,d in enumerate(deals):
  rr=8+i*8
  request(rr,'C','D','E','L','PE_RATIO',QUERIES[0],f'$A{rr}')
  request(rr,'F','G','H','M','PX_TO_SALES_RATIO',QUERIES[1],f'$A{rr}')
  if d.get('a_share_code'):
   put(db,'BN'+str(i+5),v=d['a_share_code'],style=nodes(db)['BN'+str(i+5)].get('s'))
  else:put(db,'BN'+str(i+5),v='',style=nodes(db)['BN'+str(i+5)].get('s'))
 hrow=8+len(deals)*8;arow=hrow+48
 for rr in [hrow,arow]:
  for k,field in [(0,'PE_RATIO'),(1,'PX_TO_SALES_RATIO')]:request(rr+k*8,'C','D','E','L',field,QUERIES[k],f'$A${rr}')
 for addr,label in [('BJ4','P/E TTM live'),('BL4','P/S TTM live')]:put(db,addr,v=label,style=nodes(db)[addr].get('s'))
 # Synchronize the corrected Longsys values with their canonical database fields.
 from build_xlsx import DB_COLS
 for i,d in enumerate(deals,5):
  if d['code']=='9976':
   for j,(_,_,field,_,_) in enumerate(DB_COLS,1):
    if field in ['a_share_code','ah_note','subsector','a_premium_ipo_pct','a_premium_now','a_close_cny','a_close_date']:
     n=nodes(db).get(ec(j)+str(i));put(db,ec(j)+str(i),v=d.get(field,''),style=n.get('s') if n is not None else None)
 # Uniform selected-code formula, native CH security ticker and clear BDH spill cells.
 f53=f'IFERROR(INDEX(Database!$BN$5:$BN${len(deals)+4},MATCH(SelectedDeal,Database!$B$5:$B${len(deals)+4},0)),IFERROR(INDEX(Pipeline!$V$6:$V$18,MATCH(SelectedDeal,Pipeline!$B$6:$B$18,0)),""))'
 put(screen,'F53',f=f53,style=nodes(screen)['F53'].get('s'))
 put(screen,'F54',f='IFERROR(IF(OR($F$53="",$F$53=0),"",TEXT(VALUE(LEFT(TRIM($F$53),6)),"000000")&" CH Equity"),"")',style=nodes(screen)['F54'].get('s'))
 put(screen,'F56',f='IF($F$54="","",BDH($F$54,"PX_LAST",TODAY()-31,TODAY(),"Dts=S","Dir=V","Sort=A","Days=T","Per=cd"))',style=nodes(screen)['F56'].get('s'))
 # Empty formatted cells in the two-column history output are safe; no values/formulas may block the spill.
 for addr,n in list(nodes(screen).items()):
  if re.fullmatch('[FG](?:5[7-9]|6[0-9]|7[0-9]|8[0-9])',addr):
   for child in list(n):n.remove(child)
   n.attrib.pop('t',None)
 for name,doc in [('Valuation Data',val),('Database',db),('Screener',screen),('BBG Verify',verify)]:sort(doc);parts[sheets[name]]=E.tostring(doc)
