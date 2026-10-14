"""Bounded checks of reflowed controls, capital adjustments and refresh wiring."""
import json,re,sys,zipfile,tempfile,math,io,gzip,base64
from pathlib import Path
from datetime import date
import xml.etree.ElementTree as E
import numpy as np,formulas
from openpyxl.formula.translate import Translator
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from reflow_monitors import nodes,value,serial,transfer_peer_formula
from patch_peer_workbook import maps,q
from ah_basis import share_multiplier,adjusted_premium,review_for
from market_universe import histories
from refresh_monitor_data import refresh_peers
from desk_release import moved_formula
def read(z,name,sheets):
 _,_,actual=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']});return E.fromstring(z.read(actual[name]))
with zipfile.ZipFile(ROOT/'out/HK_IPO_Database_v1.xlsx') as z,zipfile.ZipFile(ROOT/'out/_compact_baseline.xlsx') as before:
 _,_,sheets=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
 pc=nodes(read(z,'Peer Chart',sheets));pt=nodes(read(z,'Peer Trades',sheets));lc=nodes(read(z,'Lock Compare',sheets));lk=nodes(read(z,'Lock-up',sheets));old=nodes(read(before,'Peer Trades',sheets))
 for name in ['Peer Trades','Lock-up']:assert not list(read(z,name,sheets).iter(q('mergeCell')))
 for name in ['Taxonomy']:
  previous=nodes(read(before,name,sheets));current=nodes(read(z,name,sheets))
  assert set(previous)==set(current),name
  for addr,cell in previous.items():
   assert value(cell)==value(current[addr]),(name,addr)
   oldf=cell.find(q('f'));newf=current[addr].find(q('f'))
   if oldf is not None:
    expected=moved_formula(moved_formula(oldf.text,'Database',64,3),'Screener',62,1)
    expected=expected.replace('$528',f'${len(json.loads((ROOT/"data/deals.json").read_text())["deals"])+4}')
    assert newf.text==expected,(name,addr,newf.text,expected)
 for source,target in [('B4','O4'),('E4','R4'),('B5','O5'),('E5','R5'),('D9','Q9'),('G9','T9'),('I9','V9')]:
  assert pc[target].find(q('f')).text==transfer_peer_formula(old[source].find(q('f')).text),(source,target)
 for cell,source in [('O3','B3'),('U4','F3'),('X4','H3'),('U5','F4'),('X5','H4')]:
  assert pc[cell].find(q('f')).text=="'Peer Trades'!$"+re.match('[A-Z]+',source)[0]+'$'+re.search(r'\d+',source)[0]
  assert pc[cell].get('t')!='inlineStr' and pc[cell].find(q('is')) is None
 assert [d.get('sqref') for d in read(z,'Peer Trades',sheets).iter(q('dataValidation'))]==['B3','F3','H3']
 assert value(pt['B8'])=='9856' and value(pt['C8'])=='3308'
 assert math.isclose(float(value(pt['F8'])),100*(float(value(pt['B12']))-float(value(pt['C12']))),abs_tol=1e-10)
 assert [value(lk[a]) for a in ['B10','E10','H10','K10']]==['0600','0470','2706','9981']
 assert "'Lock-up'!$B$11" in lc['B5'].find(q('f')).text and "'Lock-up'!$E$11" in lc['B5'].find(q('f')).text
 assert "'Lock-up'!$B$10" in lc['C5'].find(q('f')).text and "'Lock-up'!$E$10" in lc['D5'].find(q('f')).text
 code=value(lk['A8']);deal=next(d for d in json.loads((ROOT/'data/deals.json').read_text())['deals'] if d['code']==code)
 for addr,key,scale in [('G8','cornerstone_pct',100),('H8','since_ipo_pct',100),('I8','deal_size_hkdm',1)]:assert math.isclose(float(value(lk[addr])),deal[key]/scale,abs_tol=1e-10)
 chart=nodes(read(z,'Chart Data',sheets));comp=nodes(read(z,'AH Compare',sheets));ah=nodes(read(z,'AH',sheets))
 # Execute actual shipped scalar formulas against raw fixtures, including headers/missing dates elsewhere in the retained tests.
 for f,fields,idx,classflag in [(chart['B5'].find(q('f')).text,{'A5':'hdate','C5':'h','D5':'a','E5':'fx','F5':'adate','G5':'fxdate'},'AH!P3','AH!P9'),(comp['G5'].find(q('f')).text,{'A5':'hdate','B5':'h','C5':'a','D5':'fx','E5':'adate','F5':'fxdate'},'H2',None)]:
  fn=formulas.Parser().ast('='+f)[1].compile()
  def calculate(hdate,adate,a,h=40,blocked=0,fxdate=None):
   data={'hdate':serial(hdate),'adate':serial(adate),'fxdate':serial(fxdate or hdate),'a':a,'h':h,'fx':1};args=[]
   for key in fn.inputs:
    normal=key.replace("'",'').split('!')[-1].replace('$','')
    if normal in fields:args.append(data[fields[normal]])
    elif key.replace("'",'').replace('$','')==idx:args.append(1)
    elif normal=='H2':args.append(1)
    elif normal=='P3':args.append(1)
    elif normal=='P9':args.append(blocked)
    elif 'AH DELTA' in key.upper():
     col=re.match('[A-Z]+',normal)[0];v=serial('2026-01-06') if col=='J' else serial('2026-01-08') if col=='K' else 2 if col=='R' else 1 if col in ['S','T'] else 0;args.append(np.full((len(json.loads((ROOT/"data/desk_chart_data.json").read_text())["pairs"]),1),v,dtype=object))
    elif 'MARKET DATA' in key.upper():args.append(np.full((len(json.loads((ROOT/"data/desk_chart_data.json").read_text())["pairs"]),1),blocked,dtype=object))
    else:raise AssertionError(key)
   return fn(*args).item()
  assert math.isclose(calculate('2026-01-05','2026-01-05',100,80),.25)
  assert math.isclose(calculate('2026-01-07','2026-01-07',100),.25) # H ex, A cum.
  assert math.isclose(calculate('2026-01-09','2026-01-09',50),.25)
  assert math.isclose(calculate('2026-01-09','2026-01-09',55),.375) # A real move remains.
  assert str(calculate('2026-01-07','2026-01-08',50))=='#N/A' # Future quote prohibited.
  assert str(calculate('2026-01-20','2026-01-05',100))=='#N/A'
  assert str(calculate('2026-01-09','2026-01-09',50,blocked=1))=='#N/A'
 records={r['code']:r for r in histories(ROOT)['pairs']}
 for k,selector in enumerate(['B4','K28','K29','K30']):
  code=value(ah[selector]);r=records[code];rv=review_for(code,ROOT);by={p[0]:p for p in r['history']};out=['G','P','Y','AH'][k]
  for i,(dt,h) in enumerate(r['h_history'],5):
   actual=value(comp[out+str(i)]);p=by.get(dt)
   if p:assert math.isclose(float(actual),adjusted_premium(rv,p),abs_tol=1e-12),(code,dt)
   else:assert actual=='#N/A',(code,dt)
 # Every named selector still resolves both codes after being transferred.
 pairs=json.loads((ROOT/'data/peer_pairs.json').read_text())['pairs']
 for addr,field in [('O4','code_a'),('R4','code_b')]:
  fn=formulas.Parser().ast('='+pc[addr].find(q('f')).text)[1].compile()
  for pair in pairs:
   label=lambda p:p['code_a']+' / '+p['code_b']
   args=[label(pair) if key=='O3' else np.array([[label(p)] for p in pairs],dtype=object) if '!S' in key else np.array([[p[field]] for p in pairs],dtype=object) for key in fn.inputs]
   assert fn(*args).item()==pair[field]
 print('PASS no merged cells; transferred live controls, all 35 named selectors, selected-event metrics, preserved core/data sheets; actual native premium formulas and all selected stored observations')

class Response:
 def raise_for_status(self):pass
 def json(self):return {'chart':{'result':[{'timestamp':[int(__import__('datetime').datetime(2026,10,5,tzinfo=__import__('datetime').timezone.utc).timestamp())],'indicators':{'quote':[{'open':[50],'close':[50],'high':[51],'low':[49],'volume':[100]}]}}]}}
with tempfile.TemporaryDirectory(prefix='hkipo-refresh-fixture-') as folder:
 root=Path(folder);(root/'data').mkdir();original={'asof':'2026-10-02','pairs':[{'code_a':'0005','code_b':'2888','label':'HSBC / STANCHART','peer_reason':'International banks','sources':['issuer evidence']}],'stocks':[]};path=root/'data/peer_pairs.json';path.write_text(json.dumps(original));calls=[]
 def get(url,**kw):calls.append(url);return Response()
 assert not refresh_peers(root,'2026-10-05',get)
 revised=json.loads(path.read_text());assert revised['pairs']==original['pairs'] and revised['asof']=='2026-10-05' and len(calls)==2
 assert json.loads((root/'data/peer_price_cache/0005.json').read_text())['rows'][0][2]==50
 assert not refresh_peers(root,'2026-10-05',get) and len(calls)==2
 def fail(url,**kw):raise RuntimeError('blocked provider')
 errors=refresh_peers(root,'2026-10-06',fail);assert len(errors)==2 and json.loads((root/'data/peer_price_cache/0005.json').read_text())['rows'][0][2]==50
 assert json.loads(path.read_text())['pairs']==original['pairs']
print('PASS incremental peer-refresh wiring, curated roster preservation, split-restated full-window fetch and retention on blocked provider')
# The seven-year A/H supplement participates in the standard refresh.
from refresh_monitor_data import refresh_legacy
with tempfile.TemporaryDirectory(prefix='hkipo-legacy-fixture-') as folder:
 root=Path(folder);(root/'data/batches').mkdir(parents=True);(root/'data/ah_study_cache').mkdir();cache=root/'data/ah_study_cache';d=dict(code='0001',name='Legacy pair',a_share_code='600001.SS',ipo_date='2019-05-02',final_price=10,sector='Financials',subsector='Banks');(root/'data/deals.json').write_text(json.dumps({'deals':[]}));(root/'data/market_supplement.json').write_text(json.dumps({'deals':[d]}));old={'code':'0001','h_history':[['2019-05-02',10],['2026-10-02',20]],'history':[]};path=root/'data/batches/ah_market_supplement.json';path.write_text(json.dumps({'asof':'2026-10-02','pairs':[old],'errors':[]}))
 for kind,rows in [('h',old['h_history']),('a',[['2019-05-01',12],['2026-10-02',22]]),('cnyhkd',[['2019-05-01',1.1],['2026-10-05',1.1]])]:(cache/(kind+'_0001.json' if kind!='cnyhkd' else 'cnyhkd.json')).write_text(json.dumps(rows))
 class LegacyResponse:
  def __init__(self,symbol):self.symbol=symbol
  def raise_for_status(self):pass
  def json(self):return {'data':{self.symbol:{'day':[['2026-10-05','21','21','21','21','100']]}}}
 calls=[]
 def get(url,**kw):symbol=re.search(r'param=([^,]+)',url)[1];calls.append(symbol);return LegacyResponse(symbol)
 assert not refresh_legacy(root,'2026-10-05',get)
 updated=json.loads(path.read_text())['pairs'][0];assert updated['latest_date']=='2026-10-05' and updated['h_history'][0]==['2019-05-02',10] and len(calls)==2
 assert not refresh_legacy(root,'2026-10-05',get) and len(calls)==2
print('PASS legacy A/H refresh extends saved history and retains early observations / failures')
