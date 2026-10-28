"""Stream the native package: data parity, styles, charts, bindings and Excel limits."""
import sys,json,zipfile,re,math,posixpath,base64,gzip,gc
from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as E
from openpyxl.utils.cell import range_boundaries
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q,N,R,P
from patch_presentation_workbook import QUERIES
from build_xlsx import DB_COLS
from build_dashboard import KEEP
from ah_basis import review_for,comparable
from desk_release import moved_range
html=(ROOT/'out/hk_ipo_dashboard.html').read_text();payload=re.search(r'<script id="ipo-payload" type="application/octet-stream">([A-Za-z0-9+/=]+)</script>',html)[1];web=json.loads(gzip.decompress(base64.b64decode(payload)))
deals=json.loads((ROOT/'data/deals.json').read_text())['deals'];wd={d['code']:d for d in web['deals']}
assert set(wd)=={d['code'] for d in deals}
for d in deals:
 for f in KEEP:
  if f in d:assert wd[d['code']].get(f)==d[f],(d['code'],f)
def value(n):
 if n is None:return None
 v=n.find(q('v'))
 if n.get('t')=='inlineStr':return ''.join(n.find(q('is')).itertext())
 if v is None or v.text is None:return None
 if n.get('t') in ['str','e']:return v.text
 return float(v.text)
def cells(doc):return {n.get('r'):n for n in doc.iter(q('c'))}
def close_payload(a,b):
 if isinstance(a,dict):return isinstance(b,dict) and set(a)==set(b) and all(close_payload(v,b[k]) for k,v in a.items())
 if isinstance(a,list):return isinstance(b,list) and len(a)==len(b) and all(close_payload(x,y) for x,y in zip(a,b))
 if isinstance(a,(int,float)) and not isinstance(a,bool):return isinstance(b,(int,float)) and math.isclose(a,b,rel_tol=0,abs_tol=5.1e-9)
 return a==b
def col(i):
 result=''
 while i:i,k=divmod(i-1,26);result=chr(65+k)+result
 return result
with zipfile.ZipFile(ROOT/'out/HK_IPO_Database_v1.xlsx') as z:
 assert z.testzip() is None
 wb,rels,sheets=maps({k:z.read(k) for k in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
 assert [s.get('name') for s in wb.find(q('sheets'))][:5]==['IPO Live','AH','Peer Trades','Screener','Database']
 assert next(s for s in wb.find(q('sheets')) if s.get('name')=='AH Reference').get('state')=='hidden'
 styles=E.fromstring(z.read('xl/styles.xml'));nf=len(styles.find(q('cellXfs')));nd=len(styles.find(q('dxfs')))
 names=set(z.namelist());formula_count=0;changed_sheets=[]
 for path in z.namelist():
  if path.endswith('.rels'):
   rel=E.fromstring(z.read(path));ids=[x.get('Id') for x in rel];assert len(ids)==len(set(ids)),path
   owner=posixpath.normpath(posixpath.join(posixpath.dirname(path),'..',posixpath.basename(path)[:-5])) if path!='_rels/.rels' else ''
   for x in rel:
    if x.get('TargetMode')=='External':continue
    t=x.get('Target');target=t.lstrip('/') if t.startswith('/') else posixpath.normpath(posixpath.join(posixpath.dirname(owner),t));assert target in names,(path,target)
  if path.startswith('xl/drawings/') and path.endswith('.xml'):
   ids=[x.get('id') for x in E.fromstring(z.read(path)).iter() if x.tag.endswith('cNvPr')];assert len(ids)==len(set(ids)),path
 for name,path in sheets.items():
  doc=E.Element(q('worksheet'));retain=name in ['IPO Live','AH','Lock-up','Peer Trades','Screener','Database','Valuation Data','Chart Data']
  for _,n in E.iterparse(z.open(path),events=('end',)):
   if n.tag in [q('cfRule'),q('dataValidation'),q('mergeCell'),q('pane')]:doc.append(deepcopy(n))
   if n.tag==q('row'):n.clear();continue
   if n.tag!=q('c'):continue
   if retain:doc.append(deepcopy(n))
   assert int(n.get('s','0'))<nf,(name,n.get('r'))
   f=n.find(q('f'))
   if f is not None:
    formula_count+=1;assert '#REF!' not in f.text,(name,n.get('r'));assert f.text.count('"')%2==0,(name,n.get('r'))
   if name in ['IPO Live','AH','Lock-up','Peer Trades','Screener','Database']:assert n.get('t')!='e',(name,n.get('r'),value(n))
   n.clear()
  for rule in doc.iter(q('cfRule')):
   if rule.get('dxfId') is not None:assert int(rule.get('dxfId'))<nd
  for dv in doc.iter(q('dataValidation')):
   f=dv.find(q('formula1'))
   if dv.get('type')=='list' and f is not None and f.text and f.text.startswith('"'):assert len(f.text)-2<=255,(name,dv.get('sqref'))
  ranges=[(m.get('ref'),range_boundaries(m.get('ref'))) for m in doc.iter(q('mergeCell'))]
  for i,(a,(x,y,xx,yy)) in enumerate(ranges):
   for b,(u,v,uu,vv) in ranges[:i]:assert xx<u or uu<x or yy<v or vv<y,(name,a,b)
  if name=='Screener':assert doc.find('.//'+q('pane')).get('topLeftCell')=='C1'
  if name=='Database':
   db=cells(doc);numeric=0
   for i,d in enumerate(deals,5):
    assert value(db['A'+str(i)])==d['code']
    for j,(_,_,field,_,_) in enumerate(DB_COLS,1):
     expected=d.get(field);addr=col(j+3 if j>=64 else j)+str(i)
     if isinstance(expected,(int,float)) and not isinstance(expected,bool) and col(j) not in ['BJ','BL']:
      assert math.isclose(value(db.get(addr)),expected,rel_tol=1e-12,abs_tol=1e-10),(d['code'],field,addr,value(db.get(addr)),expected);numeric+=1
    assert value(db['BJ'+str(i)])=='Unavailable' and value(db['BL'+str(i)])=='Unavailable'
    assert db['BJ'+str(i)].find(q('f')).text==f"'Valuation Data'!L{8+(i-5)*8}"
  if name=='Lock-up':lock=cells(doc)
  if name=='AH':assert value(cells(doc)['E4'])=='Stored'
  if name=='Valuation Data':
   requests=[n.find(q('f')).text for n in doc.iter(q('c')) if n.find(q('f')) is not None and 'BQL(' in n.find(q('f')).text]
   assert len(requests)==5*len(deals)+7
   assert all(any('"'+s+'"' in f for s in QUERIES) for f in requests)
  if name=='Peer Trades':
   peer=cells(doc);assert 'MATCH($B$3' in peer['B4'].find(q('f')).text
   assert value(peer['B8'])=='9856' and value(peer['C8'])=='3308'
   assert not any(x.get('sqref') in ['B4','E4'] for x in doc.iter(q('dataValidation')))
  if name=='Chart Data':assert 'AH Delta' in cells(doc)['B5'].find(q('f')).text
 for path in z.namelist():
  if path.startswith('xl/tables/') and path.endswith('.xml'):
   table=E.fromstring(z.read(path))
   if table.get('name')=='LockupEvents':
    assert [x.get('name') for x in table.find(q('tableColumns'))]==[value(lock[col(i)+'37']) for i in range(1,14)]
 assert not {'Lock-up','Lock-up Data','Lock Compare','Lock Matrix'} & set(sheets)
 c=next(E.fromstring(z.read(p)) for p in z.namelist() if p.startswith('xl/charts/') and p.endswith('.xml') and b'!AHMarketPremium' in z.read(p));cn=lambda x:'{http://schemas.openxmlformats.org/drawingml/2006/chart}'+x
 assert len(list(c.iter(cn('ser'))))==1 and len(list(c.iter(cn('valAx'))))==2
 assert len(list(c.iter(cn('scatterChart'))))==1
 returns=E.fromstring(z.read('xl/charts/chartAHMarketReturns.xml'))
 assert len(list(returns.iter(cn('ser'))))==2 and len(list(returns.iter(cn('valAx'))))==2
 peer_meta=json.loads((ROOT/'data/peer_pairs.json').read_text());wanted=set();cursor=2
 for i,st in enumerate(peer_meta['stocks'],3):
  wanted.update(c+str(i) for c in ['H','K','L']);wanted.update(['B'+str(cursor),'B'+str(cursor+len(st['history'])-1)]);cursor+=len(st['history'])
 def sparse(path,wanted):
  result={}
  for _,n in E.iterparse(z.open(path),events=('end',)):
   if n.tag==q('c'):
    if n.get('r') in wanted:result[n.get('r')]=deepcopy(n)
    n.clear()
   elif n.tag==q('row'):n.clear()
  return result
 pd=sparse(sheets['Peer Data'],wanted);cursor=2
 for i,s in enumerate(peer_meta['stocks'],3):
  assert value(pd['H'+str(i)])==s['code'] and value(pd['K'+str(i)])==cursor and value(pd['L'+str(i)])==len(s['history'])
  for offset in [0,len(s['history'])-1]:assert math.isclose(value(pd['B'+str(cursor+offset)]),s['history'][offset][1],abs_tol=1e-12)
  cursor+=len(s['history'])
 pc=sparse(sheets['Peer Chart'],{'E5'});assert str(cursor-1) in pc['E5'].find(q('f')).text
 from historical_lockups import historical_events
 events=historical_events(json.loads((ROOT/'data/batches/lockup_events.json').read_text()),ROOT)
 assert len(web['lockups']['events'])==len(events)==json.loads((ROOT/'data/release_state.json').read_text())['counts']['html_lockup_events']
 for i,e in enumerate(events,38):
  w=e.get('windows',{}).get('30 trading sessions',{});assert web['lockups']['events'][i-38]['code']==e['code']
  assert close_payload(w,web['lockups']['events'][i-38]['window'])
  if w.get('pre_start_close') and w.get('anchor_close'):assert math.isclose(w['before_pct'],100*(w['anchor_close']/w['pre_start_close']-1),abs_tol=1e-9)
  if w.get('post_end_close') and w.get('anchor_close'):assert math.isclose(w['after_pct'],100*(w['post_end_close']/w['anchor_close']-1),abs_tol=1e-9)
print('PASS package CRC/relationships/unique drawing IDs/styles/no-overlap/dropdown limits; '+str(formula_count)+' formulas; '+str(numeric)+' historical numeric cells; all HTML records and expiry rows/returns; exact BQL wiring and native CSI chart; historical numeric source parity')
