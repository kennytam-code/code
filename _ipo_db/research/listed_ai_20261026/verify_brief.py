"""Arithmetic, source-integrity and DOCX checks; not independent financial verification.
Optional --sources-dir checks the retained research downloads against recorded hashes.
"""
from pathlib import Path
from zipfile import ZipFile
from datetime import date,timedelta
from decimal import Decimal
from lxml import etree
import argparse,hashlib,json,math,re
H=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--document',type=Path,default=H.parents[1]/'Listed_AI_Lockup_Trader_Brief_2026-10-26.docx');ap.add_argument('--sources-dir',type=Path);args=ap.parse_args()
a=json.loads((H/'source_and_valuation_audit.json').read_text());checks=0

def eq(x,y):
 global checks
 assert math.isclose(x,y,rel_tol=1e-10,abs_tol=1e-9),(x,y)
 checks+=1

def pe(cap,np):return None if np is None else 'NM' if np<=0 else cap/np
fx=a['fx']['cny_per_hkd'];usd=a['fx']['cny_per_usd']
for code,x in a['issuers'].items():
 eq(x['equity_hkdm'],x['price']*x['shares']/1e6);eq(x['equity_cnym'],x['equity_hkdm']*fx)
 eq(x['shares'],x['h_shares']+x['excluded_unlisted'])
 eq(x['ps25'],x['equity_cnym']/x['rev25'])
 eq(x['ltm_rev'],x['rev25']+x['rev_h126']-x['rev_h125'])
 eq(x['ltm_np'],x['np25']+x['np_h126']-x['np_h125'])
 eq(x['unlock_pct_total'],x['unlock_h']/x['shares']*100)
 eq(x['unlock_adv'],x['unlock_h']/x['adv20_shares'])
 eq(x['short_pct_total'],x['short_shares_20261016']/x['shares']*100)
 assert date.fromisoformat(x['first_released'])==date.fromisoformat(x['last_locked'])+timedelta(days=1)
 for yr in ['26','27']:
  want=pe(x['equity_cnym'],x['fy'+yr+'_np']);actual=x['pe'+yr]
  if isinstance(want,(int,float)):eq(actual,want)
  else:assert actual==want
 if 'control_h' in x:eq(x['unlock_h'],x['control_h']+x['other_preipo_h'])
 if code=='6600':eq(x['unlock_h']+x['extended_founder_h'],200000000)
for x in a['peers']:
 mult=fx if x['price_currency']=='HKD' else 1;denfx=usd if x['financial_currency']=='USD' else 1
 eq(x['cap_cnym'],x['cap_local_m']*mult);eq(x['ps25'],x['cap_cnym']/(x['rev25']*denfx))
 if x['shares']:eq(x['cap_local_m'],x['price']*x['shares']/1e6)
 for yr in ['26','27']:
  n=x['np'+yr];want=pe(x['cap_cnym'],None if n is None else n*denfx);actual=x['pe'+yr]
  if isinstance(want,(int,float)):eq(actual,want)
  else:assert actual==want
# Dated quote checks against independently retrieved Sina snapshot.
source_matches=0
if args.sources_dir:
 for fn,rec in a['sources'].items():
  p=args.sources_dir/fn
  if p.is_file() and rec.get('sha256'):
   assert hashlib.sha256(p.read_bytes()).hexdigest()==rec['sha256'],fn
   source_matches+=1
 s=(args.sources_dir/'sina-cross.txt').read_bytes().decode('gb18030');prices={}
 for sym,v in re.findall(r'hq_str_(\w+)="([^"]+)"',s):
  cells=v.split(',');prices[sym]=float(cells[6] if sym.startswith('rt_hk') else cells[3])
 for sym,q in a['quote_snapshots'].items():
  k='rt_'+sym if sym.startswith('hk') else sym
  if k in prices:eq(q['price'],prices[k])
 for code,x in a['issuers'].items():
  d=json.loads((args.sources_dir/('0'+code+'-daily.json')).read_text())['data']['hk0'+code];rows=d.get('qfqday',d.get('day'))[-20:]
  assert len(rows)==20 and rows[-1][0]=='2026-10-26' and rows[0][0]=='2026-09-25'
  eq(x['adv20_shares'],sum(float(r[5]) for r in rows)/20)
# The retained template stays immutable and package/style/section identities survive.
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
reference=Path(a['template']['path'])
assert hashlib.sha256(reference.read_bytes()).hexdigest()==a['template']['sha256']
with ZipFile(reference) as r,ZipFile(args.document) as z:
 assert set(r.namelist())==set(z.namelist())
 changed=[n for n in r.namelist() if r.read(n)!=z.read(n)]
 assert set(changed)=={'word/document.xml','word/_rels/document.xml.rels'}
 root=etree.fromstring(z.read('word/document.xml'));old=etree.fromstring(r.read('word/document.xml'))
 assert etree.tostring(root.find('.//w:sectPr',ns),method='c14n',exclusive=True)==etree.tostring(old.find('.//w:sectPr',ns),method='c14n',exclusive=True)
 tables=root.findall('.//w:body/w:tbl',ns);assert len(tables)==12
 for t in tables:
  assert sum(int(c.get('{'+ns['w']+'}w')) for c in t.findall('w:tblGrid/w:gridCol',ns))==9972
  for row in t.findall('w:tr',ns):assert row.find('w:trPr/w:cantSplit',ns) is not None
 for table,code in zip([tables[i] for i in [3,5,7,9]],['2635','3317','6600','6651']):
  vals=[''.join(c.xpath('.//w:t/text()',namespaces=ns)) for c in table.findall('.//w:tc',ns)]
  x=a['issuers'][code]
  for metric in ['rev','np','cfo']:
   for suffix in ['25','_h125','_h126']:assert f'{x[metric+suffix]:.1f}' in vals
  for suffix in ['25','_h125','_h126']:assert f'{100*x["gp"+suffix]/x["rev"+suffix]:.1f}%' in vals
 peer_map={p['code']:p for p in a['peers']}
 groups=[['2635','2121 HK','20 HK','600728 A'],['3317','1384 HK','6682 HK','600570 A'],['6600','668 HK','2391 HK','9880 HK','300866 A','688169 A','603486 A'],['6651','2571 HK','68 HK','300036 A']]
 for idx,keys in zip([4,6,8,10],groups):
  rows=tables[idx].findall('w:tr',ns)[1:];assert len(rows)==len(keys)
  for row,key in zip(rows,keys):
   target=key in a['issuers'];x=a['issuers'][key] if target else peer_map[key]
   mark='†' if (target and key in ['3317','6651']) or (not target and x['broker'] and 'EtNet' in x['broker']) else ''
   ccy='HK$' if target or x['price_currency']=='HKD' else 'RMB'
   f=lambda n:'n/v' if n is None else n if isinstance(n,str) else f'{n:.1f}x'
   cells=[''.join(c.xpath('.//w:t/text()',namespaces=ns)) for c in row.findall('w:tc',ns)]
   assert cells[1:]==[ccy+f'{x["price"]:.3f}',f'{x["ps25"]:.1f}x',f(x['pe26'])+mark,f(x['pe27'])+mark],(key,cells)
 assert hashlib.sha256((H/'source_and_valuation_audit.json').read_bytes()).hexdigest()=='6f4c2f43c3159f5fc2a88666aff79bf5e29111212e124551e84a024037d1d445','Design-only revision changed research inputs'
 # No stranded link IDs, changes/comments, or source-tool citation tokens.
 rel=etree.fromstring(z.read('word/_rels/document.xml.rels'));ids={n.get('Id') for n in rel}
 for h in root.findall('.//w:hyperlink',ns):assert h.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id') in ids
 assert not root.findall('.//w:ins',ns) and not root.findall('.//w:del',ns)
 plain=''.join(root.xpath('.//w:t/text()',namespaces=ns));assert 'turn226' not in plain and '' not in plain
qa=json.loads((H/'document_qa.json').read_text());assert hashlib.sha256(args.document.read_bytes()).hexdigest()==qa['document_sha256']
qa['arithmetic_check']={'status':'pass','comparisons':checks,'independent_primary_verification':False,'note':'Recalculation of recorded source inputs, plus separately identified Sina cross-vendor price matches.'}
qa['source_integrity_hash_matches']=source_matches
(H/'document_qa.json').write_text(json.dumps(qa,indent=2))
print(json.dumps(qa,indent=2))
