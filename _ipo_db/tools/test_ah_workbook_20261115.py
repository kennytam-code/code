import json,sys,zipfile,math,xml.etree.ElementTree as E
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value
from ah_basis import adjusted_premium,review_for
from market_universe import histories
from openpyxl.styles.numbers import BUILTIN_FORMATS
path=ROOT/'out/HK_IPO_Database_v1.xlsx'
def sheets(z):return maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})[2]
def node(n):return (n.tag,tuple(sorted(n.attrib.items())),n.text,tuple(node(c) for c in n))
def styles(z):
 d=E.fromstring(z.read('xl/styles.xml'));fmt=dict(BUILTIN_FORMATS);fmt.update({int(n.get('numFmtId')):n.get('formatCode') for n in d.find(q('numFmts'))});out=[]
 for x in d.find(q('cellXfs')):
  a=dict(x.attrib);a.pop('xfId',None)
  for attr,group in [('fontId','fonts'),('fillId','fills'),('borderId','borders')]:a[attr]=node(d.find(q(group))[int(a[attr])])
  a['numFmtId']=fmt.get(int(a.get('numFmtId',0)));out.append((tuple(sorted(a.items())),tuple(node(c) for c in x)))
 return out
with zipfile.ZipFile(ROOT/'backups/ah_20261115_before/HK_IPO_Database_v1.xlsx') as before,zipfile.ZipFile(path) as after:
 old,new=sheets(before),sheets(after);assert set(old)==set(new)
 assert 'Notes' not in new and 'Lock-up' not in new
 ah=nodes(E.fromstring(after.read(new['AH'])));ah_old=nodes(E.fromstring(before.read(old['AH'])))
 md=nodes(E.fromstring(after.read(new['Market Data'])));db=nodes(E.fromstring(after.read(new['Database'])))
 dc=json.loads((ROOT/'data/desk_chart_data.json').read_text())['pairs'];records={r['code']:r for r in histories(ROOT)['pairs']}
 assert len(dc)==75
 for i,m in enumerate(dc,8):
  k=i-5
  assert value(md[f'P{k}'])==m['code']
  assert value(md[f'Q{k}'])==str(int(m['code']))+' HK Equity'
  assert value(md[f'R{k}'])==m['a_ticker']
  for col,ticker in [('F','R'),('G','Q')]:
   f=ah[f'{col}{i}'].find(q('f')).text
   assert f==ah_old[f'{col}{i}'].find(q('f')).text
   assert f==f'IF($E$4<>"Bloomberg","—",IFERROR(BDP(\'Market Data\'!${ticker}{k},"CURRENT_MARKET_CAP_SHARE_CLASS"),"Unavailable"))'
   assert ah[f'{col}{i}'].find(q('f')).get('t') is None
  r=records[m['code']];expected=adjusted_premium(review_for(m['code'],ROOT),r['history'][-1])
  assert math.isclose(float(value(ah[f'I{i}'])),expected,rel_tol=1e-9,abs_tol=1e-9),m['code']
  for col,ref in [('K','stored_7'),('L','stored_1m')]:
   if m[ref] is not None:assert math.isclose(float(value(ah[f'{col}{i}'])),100*(expected-m[ref]),abs_tol=1e-8),m['code']
 assert value(ah['F7'])=='A-class cap\nCNY m' and value(ah['G7'])=='H-class cap\nHKD m'
 assert value(ah['E4'])==value(ah['H4'])=='Stored'
 # Database must read the very same cached premium, with no new external call.
 code_rows={value(ah[f'C{r}']):r for r in range(8,83)}
 for i in range(5,532):
  code=value(db[f'A{i}']);c=db[f'BT{i}'];f=c.find(q('f')).text
  assert 'BDP(' not in f and 'BDH(' not in f
  if code in code_rows:assert value(c)==value(ah[f'I{code_rows[code]}'])
 # No changes to the unrelated desk views or any Bloomberg formulas.
 preserved=[];counts={};oldstyles,newstyles=styles(before),styles(after)
 for name in ['IPO Live','Peer Trades','Screener','Pipeline','CS League','SM League','Taxonomy','Valuation Data']:
  aa=nodes(E.fromstring(before.read(old[name])));bb=nodes(E.fromstring(after.read(new[name])))
  assert set(aa)==set(bb),name
  for addr in aa:
   a,b=aa[addr],bb[addr]
   assert value(a)==value(b),(name,addr,'value')
   af,bf=a.find(q('f')),b.find(q('f'))
   assert (node(af) if af is not None else None)==(node(bf) if bf is not None else None),(name,addr,'formula')
   assert oldstyles[int(a.get('s',0))]==newstyles[int(b.get('s',0))],(name,addr,'style')
  preserved.append(name)
 for tag,z,mp in [('before',before,old),('after',after,new)]:
  counts[tag]={f:0 for f in ['BDP(','BDH(','BQL(']}
  for p in mp.values():
   for _,n in E.iterparse(z.open(p),events=('end',)):
    if n.tag==q('f'):
     for f in counts[tag]:counts[tag][f]+=(n.text or '').count(f)
    n.clear()
 assert counts['before']==counts['after'],counts
 print('PASS 150 unchanged scalar class-cap formulas, 75 stored premiums/deltas, Database links, unchanged external-request counts and',len(preserved),'unrelated sheets retain values, formulas and effective cell styles')
 (ROOT/'out/ah_workbook_checks.json').write_text(json.dumps(dict(cap_formulas=150,stored_pairs=75,preserved_sheets=preserved,external_formula_occurrences=counts['after'],terminal_tested=False),indent=2))
