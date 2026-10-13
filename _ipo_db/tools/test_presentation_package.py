"""Stream the native package: data parity, styles, charts, bindings and Excel limits."""
import sys,json,zipfile,re,math,posixpath,base64,gzip
from pathlib import Path
import xml.etree.ElementTree as E
from openpyxl.utils.cell import range_boundaries
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q,N,R,P
from patch_presentation_workbook import QUERIES
from build_xlsx import DB_COLS
from build_dashboard import KEEP
from ah_basis import review_for,comparable
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
def col(i):
 result=''
 while i:i,k=divmod(i-1,26);result=chr(65+k)+result
 return result
with zipfile.ZipFile(ROOT/'out/HK_IPO_Database_v1.xlsx') as z:
 assert z.testzip() is None
 wb,rels,sheets=maps({k:z.read(k) for k in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
 assert [s.get('name') for s in wb.find(q('sheets'))][:6]==['IPO Live','AH','Lock-up','Peer Trades','Screener','Database']
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
  doc=E.fromstring(z.read(path))
  for n in doc.iter(q('c')):
   assert int(n.get('s','0'))<nf,(name,n.get('r'))
   f=n.find(q('f'))
   if f is not None:
    formula_count+=1;assert '#REF!' not in f.text,(name,n.get('r'));assert f.text.count('"')%2==0,(name,n.get('r'))
   if name in ['IPO Live','AH','Lock-up','Peer Trades','Screener','Database']:assert n.get('t')!='e',(name,n.get('r'),value(n))
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
     expected=d.get(field);addr=col(j)+str(i)
     if isinstance(expected,(int,float)) and not isinstance(expected,bool) and col(j) not in ['BJ','BL']:
      assert value(db.get(addr))==expected,(d['code'],field,addr,value(db.get(addr)),expected);numeric+=1
    assert value(db['BJ'+str(i)])=='Unavailable' and value(db['BL'+str(i)])=='Unavailable'
    assert db['BJ'+str(i)].find(q('f')).text==f"'Valuation Data'!L{8+(i-5)*8}"
  if name=='Lock-up':lock=cells(doc)
  if name=='AH':assert value(cells(doc)['E4'])=='Stored'
  if name=='Valuation Data':
   requests=[n.find(q('f')).text for n in doc.iter(q('c')) if n.find(q('f')) is not None and 'BQL(' in n.find(q('f')).text]
   assert len(requests)==2*len(deals)+10
   assert all(any('"'+s+'"' in f for s in QUERIES) for f in requests)
  if name=='Peer Trades':
   peer=cells(doc);assert 'MATCH($B$3' in peer['B4'].find(q('f')).text and 'MATCH($B$3' in peer['E4'].find(q('f')).text
   assert value(peer['B4'])=='9856' and value(peer['E4'])=='3308'
   assert not any(x.get('sqref') in ['B4','E4'] for x in doc.iter(q('dataValidation')))
  if name=='Chart Data':assert 'AH!$P$26' in cells(doc)['B5'].find(q('f')).text
 for path in z.namelist():
  if path.startswith('xl/tables/') and path.endswith('.xml'):
   table=E.fromstring(z.read(path))
   if table.get('name')=='LockupEvents':
    assert [x.get('name') for x in table.find(q('tableColumns'))]==[value(lock[col(i)+'54']) for i in range(1,14)]
 for addr,label in [('A2','Cornerstone lock-up expiries'),('A5','Prices through 02-Oct-2026. 30 HK trading sessions around expiry.'),('A30','Compare expiry performance')]:assert value(lock[addr])==label,(addr,value(lock[addr]))
 c=E.fromstring(z.read('xl/charts/chartCSI300.xml'));cn=lambda x:'{http://schemas.openxmlformats.org/drawingml/2006/chart}'+x
 for path in ['xl/charts/chart5.xml','xl/charts/chart6.xml']:
  chart=E.fromstring(z.read(path))
  for ser in chart.iter(cn('ser')):
   cache=ser.find(cn('cat')).find(cn('strRef')).find(cn('strCache'));assert int(cache.find(cn('ptCount')).get('val'))==61 and [p.find(cn('v')).text for p in cache.findall(cn('pt'))]==[str(i) for i in range(-30,31)]
 assert c.find('.//'+cn('dateAx')) is not None and len(list(c.iter(cn('ser'))))==2
 for s in c.iter(cn('ser')):
  assert s.find(cn('cat')).find(cn('numRef')).find(cn('f')).text=="'AH Reference'!$A$80:$A$149"
  for n in s.iter(cn('numCache')):assert int(n.find(cn('ptCount')).get('val'))==70
 with zipfile.ZipFile(ROOT/'out/_presentation_baseline.xlsx') as b:
  for name in ['IPO Live','AH History','Lock-up Data','Pipeline','Taxonomy','Calc (scoring engine)']:
   if name in sheets:assert z.read(sheets[name])==b.read(sheets[name]),('Unintended change',name)
 peer_meta=json.loads((ROOT/'data/peer_pairs.json').read_text());pd=cells(E.fromstring(z.read(sheets['Peer Data'])));cursor=2
 for i,s in enumerate(peer_meta['stocks'],3):
  assert value(pd['H'+str(i)])==s['code'] and value(pd['K'+str(i)])==cursor and value(pd['L'+str(i)])==len(s['history'])
  for offset in [0,len(s['history'])-1]:assert math.isclose(value(pd['B'+str(cursor+offset)]),s['history'][offset][1],abs_tol=1e-12)
  cursor+=len(s['history'])
 pc=cells(E.fromstring(z.read(sheets['Peer Chart'])));assert str(cursor-1) in pc['E5'].find(q('f')).text
 events=[x for x in json.loads((ROOT/'data/batches/lockup_events.json').read_text())['events'] if x['category']=='Cornerstone' and x['date_basis']!='No cornerstone tranche']
 assert len(web['lockups']['events'])==len(events)==396
 for i,e in enumerate(events,55):
  w=e.get('windows',{}).get('30 trading sessions',{});assert value(lock['A'+str(i)])==e['code']
  for c,k in [('G','before_pct'),('H','after_pct')]:
   expected=w.get(k);actual=value(lock[c+str(i)])
   assert (expected is None and actual in [None,'']) or expected is not None and math.isclose(actual,expected/100,abs_tol=1e-12),(e['code'],k)
  if w.get('pre_start_close') and w.get('anchor_close'):assert math.isclose(w['before_pct'],100*(w['anchor_close']/w['pre_start_close']-1),abs_tol=1e-9)
  if w.get('post_end_close') and w.get('anchor_close'):assert math.isclose(w['after_pct'],100*(w['post_end_close']/w['anchor_close']-1),abs_tol=1e-9)
print('PASS package CRC/relationships/unique drawing IDs/styles/no-overlap/dropdown limits; '+str(formula_count)+' formulas; '+str(numeric)+' historical numeric cells; 524 HTML records; 396 expiry rows/returns; exact BQL wiring and native CSI chart; unrelated core sheets unchanged')
