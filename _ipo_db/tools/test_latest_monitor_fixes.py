"""Scalar production formula / coverage checks; Bloomberg inputs are fixtures."""
import sys,json,zipfile,re,math
from pathlib import Path
import xml.etree.ElementTree as E
import numpy as np,formulas
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value,serial
from market_universe import histories
from ah_basis import review_for,adjusted_premium
meta=json.loads((ROOT/'data/desk_chart_data.json').read_text())['pairs'];records={r['code']:r for r in histories(ROOT)['pairs']}
with zipfile.ZipFile(ROOT/'out/HK_IPO_Database_v1.xlsx') as z:
 _,_,s=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']});ah=nodes(E.fromstring(z.read(s['AH'])));md=nodes(E.fromstring(z.read(s['Market Data'])));h=nodes(E.fromstring(z.read(s['AH History'])));chart=nodes(E.fromstring(z.read(s['Chart Data'])));screen=nodes(E.fromstring(z.read(s['Screener'])));ref=nodes(E.fromstring(z.read(s['AH Reference'])));val=nodes(E.fromstring(z.read(s['Valuation Data'])))
 fn=formulas.Parser().ast('='+ah['P3'].find(q('f')).text)[1].compile()
 for i,m in enumerate(meta,1):
  for code in [m['code'],m['a_ticker']]:
   args=[np.array([[p['code']] for p in meta],dtype=object) if '!P3:' in key else np.array([[p['a_ticker']] for p in meta],dtype=object) if '!R3:' in key else code for key in fn.inputs];assert fn(*args).item()==i,(code,fn(*args))
 for code in ['3223','9976','9607']:
  m=next(x for x in meta if x['code']==code);count=m['cache_rows'];start=m['cache_start'];end=start+count-1;r=records[code]
  assert int(float(value(h['A'+str(start)])))==serial(r['ipo_date'])
  assert int(float(value(h['A'+str(end)])))==serial(r['h_history'][-1][0])
  assert float(value(h['B'+str(start)]))==r['h_history'][0][1]
  assert int(re.search(r"'AH History'!\$A\$1:\$A\$(\d+)",chart['A5'].find(q('f')).text)[1])>=end
 fn=formulas.Parser().ast('='+screen['F54'].find(q('f')).text)[1].compile()
 for v,expected in [('300223.SZ','300223 CH Equity'),('301308.SZ','301308 CH Equity'),('301308 CH Equity','301308 CH Equity'),(301308,'301308 CH Equity'),('000001.SZ','000001 CH Equity'),('',''),(0,''),('Awaiting Bloomberg','')]:assert fn(v).item()==expected,(v,fn(v))
 assert screen['F56'].find(q('f')) is not None and 'BDH($F$54,"PX_LAST"' in screen['F56'].find(q('f')).text
 for col in ['F','G']:
  for row in range(57,90):
   n=screen.get(col+str(row));assert n is None or not list(n),(col,row)
 # Numeric scalar fields preserve zero/negative values. Metadata fixtures are
 # covered by test_native_desk, which also executes field-header extraction.
 fn=formulas.Parser().ast('='+val['L8'].find(q('f')).text)[1].compile()
 for v in [18.2,0,-3.1]:
  args=[v if k=='C8' else 0 if k=='BC8' else np.full((1,8),'',dtype=object) if ':' in k else '' for k in fn.inputs];assert fn(*args).item()==v
 # A different debut close must not suppress all valid live points; headers are allowed.
 f=ah['P10'].find(q('f')).text.replace('TODAY()',str(serial('2026-10-14')));fn=formulas.Parser().ast('='+f)[1].compile()
 for code in ['3223','9976','9607']:
  r=records[code];a=np.array([['Date'],[serial(r['ipo_date'])],[serial('2026-10-13')]],dtype=object)
  args=[]
  for key in fn.inputs:
   if key=='E4':args.append('Bloomberg')
   elif key=='P3':args.append(1)
   elif key=='P6':args.append(serial(r['ipo_date']))
   elif key=='P17':args.append(serial('2026-10-02'))
   elif 'LIVE HISTORY' in key:args.append(a)
   else:raise AssertionError(key)
  assert fn(*args).item()==1,code
 # The shipped combined-chart caches agree with the saved helper values and use separate axes.
 cn=lambda k:'{http://schemas.openxmlformats.org/drawingml/2006/chart}'+k
 path=next(p for p in z.namelist() if p.startswith('xl/charts/') and p.endswith('.xml') and b'!AHMarketPremium' in z.read(p));doc=E.fromstring(z.read(path));assert len(list(doc.iter(cn('ser'))))==3 and len(list(doc.iter(cn('valAx'))))==3
 n=int(float(value(ref['AZ5'])));rv=review_for(value(ah['B4']),ROOT);raw=records[value(ah['B4'])];by={x[0]:x for x in raw['history']}
 for row in range(5,5+n):
  dt=__import__('datetime').date(1899,12,30)+__import__('datetime').timedelta(days=int(float(value(ref['BD'+str(row)]))));dt=dt.isoformat();actual=value(ref['BE'+str(row)])
  if dt in by:assert math.isclose(float(actual),adjusted_premium(rv,by[dt]),abs_tol=1e-12)
  else:assert actual in [None,'']
 for ser,col in zip(doc.iter(cn('ser')),['BE','BF','BG']):
  ca=ser.find('.//'+cn('yVal')).find('.//'+cn('numCache'))
  for pt in ca.findall(cn('pt')):assert math.isclose(float(pt.find(cn('v')).text),float(value(ref[col+str(int(pt.get('idx'))+5)])),abs_tol=1e-12)
 print('PASS 70 H/A selectors; 3223/9976 history bounds; selected-code / clear BDH output; numeric direct/BQL valuations; live gate fixtures; combined premium/CSI/A chart and independent axes')
 # Execute the combined benchmark's stored A lookup for every selector, including dynamic INDEX ranges.
 formula=ref['BK5'].find(q('f')).text.replace('TODAY()',str(serial('2026-10-14')))
 refs=json.loads((ROOT/'data/ah_reference.json').read_text())['pairs']
 for i,m in enumerate(meta,3):
  rows=refs[m['code']]['trend_rows'];row=rows[-1];first=int(float(value(ref['AG'+str(i)])));last=first+len(rows)-1
  # formulas cannot resolve INDEX reference-form operands around a colon.
  # Resolve those actual native bounds, then execute the remaining production lookup.
  f=re.sub(r'INDEX\(\$AK\$3:\$AK\$[0-9]+,\$AZ\$1-2\):INDEX\(\$AK\$3:\$AK\$[0-9]+,\$AZ\$1\+\$AZ\$2-3\)',f'$AK${first}:$AK${last}',formula)
  f=re.sub(r'INDEX\(\$AL\$3:\$AL\$[0-9]+,\$AZ\$1-2\):INDEX\(\$AL\$3:\$AL\$[0-9]+,\$AZ\$1\+\$AZ\$2-3\)',f'$AL${first}:$AL${last}',f)
  fn=formulas.Parser().ast('='+f)[1].compile();args=[]
  for key in fn.inputs:
   if key=='AH!E4':args.append('Stored')
   elif key=='AH!P3':args.append(i-2)
   elif key=='BD5':args.append(serial(row[0]))
   elif key.startswith('AK'):args.append(np.array([[serial(x[0])] for x in rows],dtype=object))
   elif key.startswith('AL'):args.append(np.array([[x[1]] for x in rows],dtype=object))
   else:args.append(np.full((len(meta) if 'AH DELTA' in key else 2200,1),0,dtype=object))
  actual=fn(*args).item();assert math.isclose(actual,row[1],abs_tol=1e-9),(m['code'],actual,row[1])
 print('PASS combined-benchmark A-price lookup and resolved native range bounds for all 70 stored selectors')
