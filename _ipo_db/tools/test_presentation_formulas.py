"""Current A/H/valuation fixtures, including headered CSI replies.

Actual Bloomberg execution remains a terminal check.
"""
import runpy,sys,zipfile
from pathlib import Path
import xml.etree.ElementTree as E
import numpy as np,formulas
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
runpy.run_path(str(ROOT/'tools/test_latest_monitor_fixes.py'),run_name='__main__')
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,serial
with zipfile.ZipFile(ROOT/'out/HK_IPO_Database_v1.xlsx') as z:
 _,_,s=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']});n=nodes(E.fromstring(z.read(s['AH Reference'])));fn=formulas.Parser().ast('='+n['BJ5'].find(q('f')).text)[1].compile()
 for header in [0,1,2]:
  dates=np.full((2200,1),'',dtype=object);prices=dates.copy()
  for i in range(header):dates[i,0]=prices[i,0]='Header'
  for i,(dt,px) in enumerate([('2026-10-09',3000),('2026-10-12',3100)],header):dates[i,0]=serial(dt);prices[i,0]=px
  def calc(day):
   args=[]
   for key in fn.inputs:
    if key=='AH!E4':args.append('Bloomberg')
    elif key=='BD5':args.append(serial(day))
    elif key.startswith('BB'):args.append(dates)
    elif key.startswith('BC'):args.append(prices)
    else:args.append(np.full((1880,1),0,dtype=object))
   return fn(*args).item()
  assert calc('2026-10-13')==3100
  assert str(calc('2026-10-01'))=='#N/A' # Never take a future observation.
  assert str(calc('2026-10-23'))=='#N/A' # Explicit freshness ceiling.
print('PASS CSI live fixtures with 0/1/2 header rows; dated holiday carry, no future quotes and stale-data rejection')
