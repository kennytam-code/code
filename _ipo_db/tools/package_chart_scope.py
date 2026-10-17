"""Package the HTML-only historical/comparison release; keep Excel byte-identical."""
from pathlib import Path
import base64,hashlib,io,json,re,shutil,sys,zipfile,zlib
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from make_bundle import DATA_FILES,LIB_MODULES
dest=ROOT/'TO_NOMURA';state=json.loads((ROOT/'data/release_state.json').read_text())
excel_hash='cb2e93c2c229640b7aab886d94f2216fd9c6d41393f9faac1fb27a10eabf96e2'
assert hashlib.sha256((dest/'HK_IPO_Database_v1.xlsx').read_bytes()).hexdigest()==excel_hash
qa=json.loads((ROOT/'out/chart_scope_20261017/qa_results.json').read_text());assert all(c['passed'] for c in qa)
functions=json.loads((ROOT/'out/chart_scope_20261017/functional_checks.json').read_text());assert functions['passed'] and functions['unrelated_payload_unchanged']
summary=json.loads((ROOT/'data/lockup_review_20261017/summary.json').read_text())
script=(ROOT/'export/hk_ipo.py').read_text();compile(script,'hk_ipo.py','exec')
blob=json.loads(zlib.decompress(base64.b64decode(re.search(r'^_PAYLOAD = "([A-Za-z0-9+/=]+)"',script,re.M)[1])))
for p in set(DATA_FILES):
 source=ROOT/p
 if source.exists():assert blob[p]==source.read_text(),('Bundle data mismatch',p)
with zipfile.ZipFile(io.BytesIO(base64.b64decode(re.search(r'^_LIBZIP = "([A-Za-z0-9+/=]+)"',script,re.M)[1]))) as z:
 for name in LIB_MODULES:
  actual=z.read(name+'.py').decode();assert actual==(ROOT/'ipo_lib'/f'{name}.py').read_text(),name;compile(actual,name+'.py','exec')
del blob,script
for name in ['hk_ipo_dashboard.html','database_numeric_audit.md','database_numeric_audit.json']:
 shutil.copyfile(ROOT/'out'/name,dest/name)
shutil.copyfile(ROOT/'export/hk_ipo.py',dest/'hk_ipo.py')
with zipfile.ZipFile(dest/'hk_ipo_dashboard.zip','w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:z.write(dest/'hk_ipo_dashboard.html','hk_ipo_dashboard.html')
with zipfile.ZipFile(dest/'hk_ipo_dashboard.zip') as z:assert z.read('hk_ipo_dashboard.html')==(dest/'hk_ipo_dashboard.html').read_bytes()
state['release_date']='2026-10-17';state['counts'].update(html_lockup_events=summary['displayed_events'],html_lockup_stocks=summary['displayed_stocks'])
state['dates']['historical_lockup_prices']=summary['price_asof']
state['validation']['historical_lockup_review']=summary
state['validation']['comparison_scope']={**functions,'checks':qa,'svg_visual_review':['A/H Technology','Lock-up individual stocks','Lock-up selected average','Single observation','Genuine gaps'],'full_browser_review':False,'excel_unchanged':True}
state['known_limits']['undated_visible_lockup_events']=0
state['known_limits']['historical_lockups']='161 completed, date-confirmed events; selective sample. 21 retain interior price gaps. 70 ambiguous dates, 67 undated, 67 future, 26 incomplete/unverified price windows and six original schedules with later extensions excluded; 6911 controller row corrected. Amendment search was targeted, not exhaustive. Sources and exclusions retained outside Excel.'
for name in ['HK_IPO_Database_v1.xlsx','hk_ipo_dashboard.html','hk_ipo_dashboard.zip','hk_ipo.py','READ_ME_FIRST.txt']:
 p=dest/name;state['deliverables'][name]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(ROOT/'data/release_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
for name in ['qa_results.json','functional_checks.json']:shutil.copyfile(ROOT/'out/chart_scope_20261017'/name,ROOT/'data/lockup_review_20261017'/name)
print('PASS source/data bundle parity, compilation, compressed HTML parity; Excel unchanged')
print(json.dumps({k:v for k,v in state['deliverables'].items() if k!='HK_IPO_Database_v1.xlsx'},indent=2))
