"""Guard against Excel recovery, stale column references and valuation drift."""
import sys,json,zipfile,re,math
from pathlib import Path
import xml.etree.ElementTree as E
import numpy as np,formulas
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value,ci,ec
from desk_release import SHEET_ORDER,moved_formula,moved_range
from patch_presentation_workbook import QUERIES
path=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'out/HK_IPO_Database_v1.xlsx'
with zipfile.ZipFile(path) as z:
 assert z.testzip() is None
 _,_,s=maps({k:z.read(k) for k in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
 for name,p in s.items():
  previous=-1;rows=set();refs=set()
  for _,n in E.iterparse(z.open(p),events=('end',)):
   if n.tag==q('c'):
    assert n.get('r') not in refs,(name,n.get('r'));refs.add(n.get('r'));n.clear()
   elif n.tag==q('row'):
    assert n.get('r') not in rows,(name,n.get('r'));rows.add(n.get('r'));n.clear()
  d=E.fromstring(z.read(p)) if name in ['AH','Lock-up','Peer Trades','Screener','Database','IPO Live','Valuation Data'] else None
  # Inspect just the start events for root-child order, without retaining history grids.
  depth=0;order=[]
  for event,n in E.iterparse(z.open(p),events=('start','end')):
   if event=='start':
    depth+=1
    if depth==2:order.append(SHEET_ORDER.index(n.tag.split('}')[-1]))
   else:depth-=1;n.clear()
  assert order==sorted(order),(name,order)
 print('PASS all native worksheet child sequences, unique rows and unique cells')
 db=nodes(E.fromstring(z.read(s['Database'])));sc=nodes(E.fromstring(z.read(s['Screener'])));val=nodes(E.fromstring(z.read(s['Valuation Data'])));peer=nodes(E.fromstring(z.read(s['Peer Data'])));pt=nodes(E.fromstring(z.read(s['Peer Trades'])));lock=nodes(E.fromstring(z.read(s['Lock-up'])));live=nodes(E.fromstring(z.read(s['IPO Live'])))
 deals=json.loads((ROOT/'data/deals.json').read_text())['deals'];n=len(deals)
 notes=nodes(E.fromstring(z.read(s['Notes'])))
 workbook=E.fromstring(z.read('xl/workbook.xml'))
 for named in workbook.find(q('definedNames')):
  if named.get('name').startswith('W_'):
   assert named.text.startswith('Notes!');addr=named.text.split('!')[1].replace('$','');actual=value(notes[addr]);assert actual not in [None,''] and float(actual)>0,(named.get('name'),addr,actual)
 print('PASS every scoring weight remains numeric and positive at its named address')
 for col,title in [('BM','NTM P/E live'),('BN','FY2027 P/E live'),('BO','FY2027 P/S live')]:assert value(db[col+'4'])==title
 assert f'Database!$BQ$5:$BQ${n+4}' in sc['F53'].find(q('f')).text
 for i,d in enumerate(deals):
  rr=8+8*i
  assert value(db['BQ'+str(i+5)])==(d.get('a_share_code') or '')
  for source,output,col,query in zip(['P','Z','AJ'],['X','AH','AR'],['BM','BN','BO'],QUERIES[2:]):
   assert '"'+query+'"' in val[source+str(rr)].find(q('f')).text
   assert db[col+str(i+5)].find(q('f')).text==f"'Valuation Data'!{output}{rr}"
 for col,source in [('BH','BM'),('BI','BN'),('BJ','BO')]:
  assert f'Database!${source}$5:${source}${n+4}' in sc[col+'21'].find(q('f')).text
  assert f'MEDIAN({col}21:{col}35)' in sc[col+'37'].find(q('f')).text
  fn=formulas.Parser().ast('='+sc[col+'21'].find(q('f')).text)[1].compile()
  scores=np.arange(1,n+1).reshape((n,1)).astype(object);multiples=(np.arange(1,n+1)+5).reshape((n,1)).astype(object)
  args=[15 if key=='D18' else scores if 'CALC' in key.upper() else multiples for key in fn.inputs]
  assert fn(*args).item()==n+5
 def evaluate(formula,fixture):
  fn=formulas.Parser().ast('='+formula)[1].compile();args=[]
  for key in fn.inputs:
   if ':' in key:
    a,b=key.split(':');ac=ci(re.match('[A-Z]+',a)[0]);bc=ci(re.match('[A-Z]+',b)[0]);ar=int(re.search('[0-9]+',a)[0]);br=int(re.search('[0-9]+',b)[0]);args.append(np.array([[fixture.get(ec(c)+str(r),'') for c in range(ac,bc+1)] for r in range(ar,br+1)],dtype=object))
   else:args.append(fixture.get(key,''))
  return fn(*args).item()
 for out,source,helper,field in [('X','P','Y','PE_RATIO'),('AH','Z','AI','PE_RATIO'),('AR','AJ','AS','PX_TO_SALES_RATIO')]:
  start=ci(source)
  for datum in [12.8,0,-4.2]:
   # Real table shape: numeric date metadata precedes the requested ratio.
   fixture={source+'8':'ID',ec(start+1)+'8':'AS_OF_DATE',ec(start+2)+'8':'PERIOD',ec(start+3)+'8':field,source+'9':'2170 HK Equity',ec(start+1)+'9':46000,ec(start+2)+'9':2027,ec(start+3)+'9':datum}
   fixture[helper+'8']=evaluate(val[helper+'8'].find(q('f')).text,fixture)
   assert fixture[helper+'8']==4
   assert evaluate(val[out+'8'].find(q('f')).text,fixture)==datum
   assert evaluate(val[out+'8'].find(q('f')).text,{source+'8':datum,helper+'8':0})==datum
  assert evaluate(val[out+'8'].find(q('f')).text,{source+'8':'#N/A',helper+'8':0})=='Unavailable'
  # A numeric date in the first cell is table metadata, never a scalar ratio.
  assert evaluate(val[out+'8'].find(q('f')).text,{source+'8':46000,ec(start+1)+'8':25.6,helper+'8':0})==25.6
  assert evaluate(val[out+'8'].find(q('f')).text,{source+'8':46000,ec(start+1)+'8':2027,ec(start+2)+'8':25.6,helper+'8':0})=='Unavailable'
 # Two-column responses and unavailable direct fields have the same safe fallback.
 fixture={'C8':'#N/A','AU8':'ID','AV8':'PE_RATIO','AU9':'2170 HK Equity','AV9':21.3}
 fixture['BC8']=evaluate(val['BC8'].find(q('f')).text,fixture)
 assert evaluate(val['L8'].find(q('f')).text,fixture)==21.3
 # Sparse ticker lookup must resolve the last issuer just as correctly as the first.
 hrow=8+8*n;fn=formulas.Parser().ast('='+val['L'+str(hrow+16)].find(q('f')).text)[1].compile()
 tickers=np.full((8*(n-1)+1,1),'',dtype=object);multiples=tickers.copy()
 for i in range(n):tickers[8*i,0]=f'{i+1} HK Equity';multiples[8*i,0]=i+1.5
 for i in [0,n//2,n-1]:
  args=[f'{i+1} HK Equity' if key=='A'+str(hrow) else tickers if key.startswith('A8:') else multiples for key in fn.inputs];assert fn(*args).item()==i+1.5
 assert moved_formula('IF(A1="Database!BN5",Database!$BN$5,0)','Database',64,3)=='IF(A1="Database!BN5",Database!$BQ$5,0)'
 assert moved_range('$A$5:$CC$528',64,3)=='$A$5:$CF$528'
 for i,p in enumerate(json.loads((ROOT/'data/peer_pairs.json').read_text())['pairs'],3):assert value(peer['S'+str(i)])==p['code_a']+' / '+p['code_b']
 assert value(pt['B3'])=='9856 / 3308'
 table=next(E.fromstring(z.read(p)) for p in z.namelist() if p.startswith('xl/tables/') and p.endswith('.xml') and E.fromstring(z.read(p)).get('name')=='LockupEvents');assert table.get('ref')==f'A37:M{37+len([e for e in json.loads((ROOT/"data/batches/lockup_events.json").read_text())["events"] if e["category"]=="Cornerstone" and e["date_basis"]!="No cornerstone tranche"])}';assert [x.get('name') for x in table.find(q('tableColumns'))]==[value(lock[ec(i)+'37']) for i in range(1,14)]
 events=[e for e in json.loads((ROOT/'data/batches/lockup_events.json').read_text())['events'] if e['category']=='Cornerstone' and e['date_basis']!='No cornerstone tranche']
 for row,e in enumerate(events,38):
  assert value(lock['A'+str(row)])==e['code']
  w=e.get('windows',{}).get('30 trading sessions',{})
  for col,key in [('G','before_pct'),('H','after_pct')]:
   expected=w.get(key);actual=value(lock[col+str(row)])
   if expected is not None:assert math.isclose(float(actual),expected/100,abs_tol=1e-12)
   else:assert actual in [None,'']
 snapshot=json.loads((ROOT/'data/live_snapshot.json').read_text())
 md=nodes(E.fromstring(z.read(s['Market Data'])))
 for addr,cell in live.items():
  if not re.fullmatch('A[0-9]+',addr) or int(addr[1:])<8 or not value(cell) or 'HK Equity' not in str(value(cell)):continue
  row=int(addr[1:]);code=str(int(value(cell).split()[0])).zfill(4);quote=snapshot['quotes'].get(code,{})
  if quote:
   assert math.isclose(float(value(live['D'+str(row)])),quote['last'],abs_tol=1e-12)
   assert value(md['BU'+str(row)])==quote['quote_time']
   change=value(live['E'+str(row)])
   if quote['quote_time'][:10]==snapshot['asof']:assert math.isclose(float(change),quote['last']/quote['previous_close']-1,abs_tol=1e-12)
   else:assert change in [None,'']
 assert value(live['B4'])=='Stored'
 assert 'BDP(Q3,"LAST_PRICE")' in md['AD3'].find(q('f')).text
 for p in z.namelist():
  if p.startswith('xl/worksheets/') and p.endswith('.xml'):
   for _,cell in E.iterparse(z.open(p),events=('end',)):
    if cell.tag==q('f'):assert len(cell.text or '')<=8192;(cell.clear())
 # The visible legend must follow the same stock selectors as its data.
 for path in z.namelist():
  if path.startswith('xl/charts/') and path.endswith('.xml'):
   doc=E.fromstring(z.read(path));cn=lambda x:'{http://schemas.openxmlformats.org/drawingml/2006/chart}'+x
   if b"Lock-up" in z.read(path):
    for ref in doc.iter(cn('f')):assert not re.search(r"'Lock-up'!\$[BEHK]\$30",ref.text or '')
   if b'AHMarketPremium' in z.read(path):
    assert len(list(doc.iter(cn('scatterChart'))))==2
    groups=list(doc.iter(cn('scatterChart')));assert groups[0].find(cn('axId')).get('val')==groups[1].find(cn('axId')).get('val')
 # Verify cached sector means exclude stale quotes and agree with the roster.
 groups={}
 for addr,cell in live.items():
  if re.fullmatch('E[0-9]+',addr) and int(addr[1:])>=8 and value(cell) not in [None,'']:
   sector=value(md['C'+addr[1:]]);groups.setdefault(sector,[]).append(float(value(cell)))
 for r in range(6,15):
  key=value(live['G'+str(r)]);items=groups.get(key,[])
  assert int(value(live['I'+str(r)]))==len(items)
  if items:assert math.isclose(float(value(live['H'+str(r)])),sum(items)/len(items),abs_tol=1e-12)
 print('PASS all forward bindings, selected/comparison fundamentals, sparse ticker lookup, negative/zero/missing replies, peer selectors, all expiry rows and safe off-terminal live display')
 prior=ROOT/'out/desk_prior_release.xlsx'
 if prior.exists():
  with zipfile.ZipFile(prior) as before:
   _,_,oldmap=maps({p:before.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
   old=nodes(E.fromstring(before.read(oldmap['Database'])))
   for addr,cell in old.items():
    col=ci(re.match('[A-Z]+',addr)[0]);r=int(re.search('[0-9]+',addr)[0])
    if r<5:continue
    dest=ec(col+3 if col>=64 else col)+str(r);current=db[dest]
    if value(current)!=value(cell):
     assert (col==ci('CC') and value(db['A'+str(r)])=='2315') or (value(db['A'+str(r)])=='9976' and ec(col) in ['BM','BP','BS','BT','CC']) or (value(db['A'+str(r)])=='9607' and col>=ci('BM')),(addr,dest,value(current),value(cell))
   print('PASS original Database fields preserved; documented A/H mapping/note changes match Longsys, Red Avenue and 2315 sources')
