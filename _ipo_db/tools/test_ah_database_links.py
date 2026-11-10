"""Dated coverage, native links and request reuse. No terminal certification."""
import json,sys,zipfile,re,math,hashlib,gc
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as E
import formulas,numpy as np
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value,serial
from ah_database_links import typed
from market_universe import validate_ah_coverage,load,histories
BASE=ROOT.parent
def prior(p):return json.loads((BASE/'before_data'/p).read_text())
olddata=prior('data/deals.json')['deals'];newdata=json.loads((ROOT/'data/deals.json').read_text())['deals']
added={'3228':'603228.SS','6727':'688031.SS','3757':'300757.SZ'}
assert len(olddata)==len(newdata)==527
for old,new in zip(olddata,newdata):
 assert old['code']==new['code']
 if old['code'] not in added:assert old==new,old['code']
 else:
  allowed={'a_share_code','is_h_share','ah_note','a_premium_ipo_pct','a_close_hkd','_prov'}
  assert all(old.get(k)==new.get(k) for k in set(old)|set(new) if k not in allowed)
  assert new['a_share_code']==added[old['code']] and new['is_h_share'] is True
newdata=[{k:r.get(k) for k in ['code','a_share_code']} for r in newdata];del olddata,old,new;gc.collect()
assert validate_ah_coverage(ROOT)==75
bad=load(ROOT)
next(r for r in bad if r['code']=='3228').pop('a_share_code')
with patch('market_universe.load',return_value=bad):
 try:validate_ah_coverage(ROOT);raise AssertionError('Missing map passed')
 except ValueError as e:assert '3228' in str(e)
del bad;gc.collect()
oldhist=prior('data/batches/ah_study.json')['pairs'];newhist=json.loads((ROOT/'data/batches/ah_study.json').read_text())['pairs']
assert newhist[:len(oldhist)]==oldhist
oldmeta={'pairs':prior('data/desk_chart_data.json')['pairs']};newmeta={'pairs':json.loads((ROOT/'data/desk_chart_data.json').read_text())['pairs']};assert newmeta['pairs'][:72]==oldmeta['pairs']
oldref=prior('data/ah_reference.json');newref=json.loads((ROOT/'data/ah_reference.json').read_text());assert all(newref['pairs'][c]==v for c,v in oldref['pairs'].items())
del oldref,newref;gc.collect()
for r in newhist[len(oldhist):]:
 assert r['code'] in added and r['a_code']==added[r['code']] and r['latest_date']=='2026-10-02'
 assert len(r['h_history'])==len(r['history'])>1
 for dt,h,a,fx,p,ad,fd in r['history']:
  assert math.isclose(p,a*fx/h-1,abs_tol=1e-12) and ad<=dt and fd<=dt
del oldhist,newhist;gc.collect()
report={'terminal_tested':False,'pairs':75,'restored_pairs':added,'formula_fixtures':0,'prior_pair_histories_unchanged':True}
def evaluate(f,inputs):
 fn=formulas.Parser().ast('='+f)[1].compile();return fn(*[inputs[k] for k in fn.inputs]).item()
def eq(got,want):
 assert math.isclose(float(got),want,abs_tol=1e-12) if isinstance(want,(float,int)) else got==want,(got,want)
 report['formula_fixtures']+=1
path=ROOT/'out/HK_IPO_Database_v1.xlsx'
with zipfile.ZipFile(path) as z,zipfile.ZipFile(BASE/'before.xlsx') as old:
 assert z.testzip() is None
 _,_,s=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
 def cells(name,archive=z):return nodes(E.fromstring(archive.read(s[name])))
 ah=cells('AH');md=cells('Market Data');db=cells('Database');before=cells('AH',old);ipo=cells('IPO Live');delta=cells('AH Delta')
 for i,m in enumerate(newmeta['pairs'],8):
  j=i-5
  eq(value(ah['C'+str(i)]),m['code']);eq(value(ah['A'+str(i)]),m['name'])
  eq(value(ah['B'+str(i)]),m['a_ticker'][:6])
  for col,want in [('A',m['code']),('F',serial(m['ipo_date'])),('G',m['raw_debut']),('H',m['cache_start']),('I',m['cache_rows']),('N',serial(m['latest_date']))]:eq(typed(delta[col+str(j)]),want)
  for col,key in [('B','stored_7'),('C','stored_1m')]:
   if m[key] is None:assert typed(delta[col+str(j)]) in [None,'']
   else:eq(typed(delta[col+str(j)]),m[key])
  for col in ['F','G']:assert 'CURRENT_MARKET_CAP_SHARE_CLASS' in ah[col+str(i)].findtext(q('f'))
  if i<80:
   for col in ['H','I','J','K','L']:
    x,y=typed(ah[col+str(i)]),typed(before[col+str(i)])
    if isinstance(y,(int,float)):eq(x,y)
    else:assert x==y or (y in [None,''] and x=='No quote')
 for i,d in enumerate(newdata,5):
  eq(value(db['A'+str(i)]),d['code']);f=db['BT'+str(i)].findtext(q('f'))
  assert 'BDP(' not in f and 'BDH(' not in f and 'BQL(' not in f and 'AH!$I$8:$I$82' in f
  if d.get('a_share_code'):
   r=next(j+8 for j,m in enumerate(newmeta['pairs']) if m['code']==d['code'])
   eq(typed(db['BT'+str(i)]),typed(ah['I'+str(r)]))
  else:eq(typed(db['BT'+str(i)]),'N/A')
 # Lookups retain identity after AH sorting and a genuine zero remains zero.
 f=db['BT525'].findtext(q('f'));codes=np.array([[m['code']] for m in newmeta['pairs']],dtype=object)
 vals=np.array([[.001*j] for j in range(75)],dtype=object)
 for code in ['3228',3228,'03228']:
  for order in [np.arange(75),np.arange(74,-1,-1)]:
   inputs={'A525':code,'BQ525':'603228.SS','AH!C8:C82':codes[order],'AH!I8:I82':vals[order]};eq(evaluate(f,inputs),.072)
 for v in [0,-.4,'No quote','BBG unavailable']:
  test=vals.copy();test[72,0]=v;eq(evaluate(f,{'A525':'3228','BQ525':'603228.SS','AH!C8:C82':codes,'AH!I8:I82':test}),v)
 eq(evaluate(f,{'A525':'9999','BQ525':'603228.SS','AH!C8:C82':codes,'AH!I8:I82':vals}),'Pair missing')
 eq(evaluate(f,{'A525':'9999','BQ525':'','AH!C8:C82':codes,'AH!I8:I82':vals}),'N/A')
 # Mock only the external scalar reply. The actual formula gates are evaluated.
 f=md['AD75'].findtext(q('f')).replace('BDP(Q75,"LAST_PRICE")','ZZ1')
 tickers=np.array([[value(ipo['A'+str(r)])] for r in range(8,725)],dtype=object)
 prices=np.array([[1000+r] for r in range(717)],dtype=object);idx=list(tickers[:,0]).index('3228 HK Equity')
 for ahmode,ipomode,want in [('Stored','Stored',74.4),('Stored','Bloomberg',74.4),('Bloomberg','Stored',52.1),('Bloomberg','Bloomberg',1000+idx)]:
  eq(evaluate(f,{'AH!E4':ahmode,"'IPO LIVE'!B4":ipomode,"'IPO LIVE'!A8:A724":tickers,"'IPO LIVE'!D8:D724":prices,'Q75':'3228 HK Equity','AG75':74.4,'ZZ1':52.1}),want)
 # Names and controls include the appended records, with no array-owned inputs.
 wb=E.fromstring(z.read('xl/workbook.xml'));dn={n.get('name'):n.text for n in wb.iter(q('definedName'))}
 assert dn['AHPairList']=="'Market Data'!$P$3:$P$77"
 assert value(db['B2'])=='All' and value(ah['E4'])==value(ah['H4'])=='Stored'
 assert 'HYPERLINK' in db['BQ2'].findtext(q('f'))
 for a in ['M60','O60','Q60','E4','H4']:assert ah[a].find(q('f')) is None
 assert '$P$3:$P$77' in ah['S82'].findtext(q('f'))
 # One history block for each pair, plus shared FX. Database adds none.
 recent=cells('AH Recent');hist=[f.text for c in recent.values() for f in c.findall(q('f')) if 'BDH(' in (f.text or '')]
 assert len(hist)==151
 for p in z.namelist():
  if not p.startswith('xl/charts/') or not p.endswith('.xml'):continue
  def series(raw):
   root=E.fromstring(raw);return [(n.tag,n.text) for n in root.iter() if n.tag.endswith(('}v','}f'))]
  assert series(z.read(p))==series(old.read(p)),('Existing chart series changed',p)
 report.update(database_links=len(newdata),ah_quote_reuse=75,short_history_calls=151,existing_chart_series_preserved=True,workbook_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
(ROOT/'out/ah_database_link_checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
