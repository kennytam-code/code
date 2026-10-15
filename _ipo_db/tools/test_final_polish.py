"""Verify style-only Database edits and new listing/pipeline dependencies."""
import json,sys,re,zipfile,xml.etree.ElementTree as E
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value
def without_style(c):
 c=E.fromstring(E.tostring(c));c.attrib.pop('s',None);return E.tostring(c)
post=ROOT/'out/_theme_baseline_20261015.xlsx'
with zipfile.ZipFile(ROOT/'out/_polish_baseline_20261015.xlsx') as a,zipfile.ZipFile(post if post.exists() else ROOT/'out/HK_IPO_Database_v1.xlsx') as z:
 _,_,sa=maps({p:a.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']});_,_,sz=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
 before=nodes(E.fromstring(a.read(sa['Database'])));after=nodes(E.fromstring(z.read(sz['Database'])))
 for addr,c in before.items():
  if addr in ['A1','A2']:continue
  assert without_style(c)==without_style(after[addr]),('Database content changed',addr)
 for name in ['IPO Live','AH','Peer Trades','Screener','Market Data','Valuation Data','AH Reference']:
  assert a.read(sa[name])==z.read(sz[name]),('Unrelated sheet changed',name)
 for p in z.namelist():
  if p.startswith('xl/charts/') and p.endswith('.xml'):assert a.read(p)==z.read(p),p
 db=after;code=next(int(re.search(r'\d+',a)[0]) for a,c in db.items() if re.fullmatch(r'A\d+',a) and value(c)=='2636')
 assert float(value(db['M'+str(code)]))==35.3
 live=nodes(E.fromstring(z.read(sz['IPO Live'])));r=next(int(a[1:]) for a,c in live.items() if re.fullmatch(r'A\d+',a) and value(c)=='2636 HK Equity')
 quote=json.loads((ROOT/'data/live_snapshot.json').read_text())['quotes'].get('2636',{})
 if quote.get('quote_time','')[:10]=='2026-10-15':assert value(live['E'+str(r)]) in [None,''],'IPO reference must not be called a previous trading close'
 for name in ['Database','CS League','SM League','Taxonomy','Scoring Stats','SizeBench','Verification']:
  assert value(nodes(E.fromstring(z.read(sz[name]))).get('A2')) in [None,''],name
 print('PASS Database values/formulas/number content unchanged by formatting; unrelated monitors and all native charts byte-identical; removed prose empty')
from build_dashboard import load
from pipeline_dedupe import status_asof
deals,tax,cfg,pipe=load();assert len([d for d in deals if d['code']=='2636'])==1
assert not any('transsion' in (p.get('name') or '').lower() for p in pipe)
if not any(d['code']=='6157' for d in deals):assert any(str(p.get('expected_code'))=='6157' for p in pipe)
assert status_asof(ROOT)>='2026-10-15'
data=json.loads((ROOT/'data/deals.json').read_text());new=next(d for d in data['deals'] if d['code']=='2636')
assert new['oversub_public_mult']==4.46 and new['oversub_intl_mult']==2.55
assert new['shares_outstanding']==1237832845 and new['offer_shares']==86648300
assert new['greenshoe_exercised_final']=='pending'
if new.get('price_asof')=='2026-10-15':
 for k in ['ret_1w_pct','ret_1m_pct','ret_3m_pct']:assert new.get(k) is None
prior=ROOT/'out/final_review_20261015/deals_before.json'
if prior.exists():
 old={d['code']:d for d in json.loads(prior.read_text())['deals']};current={d['code']:d for d in data['deals']}
 for code,d in old.items():
  for k,v in d.items():
   if isinstance(v,(int,float)) and not isinstance(v,bool):assert current[code].get(k)==v,(code,k)
 print('PASS all existing listed numeric values unchanged; 2636 has immature horizons blank; 6157 active and 2636 excluded from pipeline')
