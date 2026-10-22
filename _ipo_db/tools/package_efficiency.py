"""Deliver the checked local request/visual update without refreshing observations."""
from pathlib import Path
import base64,gc,hashlib,io,json,re,shutil,sys,zipfile,zlib
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from make_bundle import DATA_FILES,LIB_MODULES
OUT=ROOT/'out/efficiency_20261022';dest=ROOT/'TO_NOMURA'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
excel=json.loads((OUT/'workbook_checks.json').read_text());web=json.loads((OUT/'html_checks.json').read_text());native=json.loads((OUT/'native_visual_check.json').read_text())
assert excel['passed'] and web['passed'] and web['entire_payload_unchanged']
candidate=ROOT/'out/HK_IPO_Database_v1.xlsx'
assert sha(candidate)==excel['sha256']==native['sha256'] and native['opened_without_repair']
def payload(s):return json.loads(zlib.decompress(base64.b64decode(re.search(r'^_PAYLOAD = "([A-Za-z0-9+/=]+)"',s,re.M)[1])))
old=payload((OUT/'baseline_hk_ipo.py').read_text());old_hash={k:hashlib.sha256(v.encode()).hexdigest() for k,v in old.items()};del old;gc.collect()
script=(ROOT/'export/hk_ipo.py').read_text()
compile(re.sub(r'^_(PAYLOAD|LIBZIP) = "[A-Za-z0-9+/=]+"',r'_\1 = ""',script,flags=re.M),'hk_ipo.py','exec')
new=payload(script);changed={k for k in old_hash if k in new and old_hash[k]!=hashlib.sha256(new[k].encode()).hexdigest()}
assert set(old_hash)<=set(new) and changed=={'assets/desk_monitors.js'},changed
assert set(new)-set(old_hash)=={'data/request_controls.json','data/screener_desk_layout.json'}
for p in set(DATA_FILES):
 if (ROOT/p).exists():assert new[p]==(ROOT/p).read_text(),p
with zipfile.ZipFile(io.BytesIO(base64.b64decode(re.search(r'^_LIBZIP = "([A-Za-z0-9+/=]+)"',script,re.M)[1]))) as z:
 for name in LIB_MODULES:
  actual=z.read(name+'.py').decode();assert actual==(ROOT/'ipo_lib'/f'{name}.py').read_text(),name;compile(actual,name+'.py','exec')
del new,script;gc.collect()
for source,name in [(candidate,'HK_IPO_Database_v1.xlsx'),(ROOT/'out/hk_ipo_dashboard.html','hk_ipo_dashboard.html'),(ROOT/'export/hk_ipo.py','hk_ipo.py')]:shutil.copyfile(source,dest/name)
with zipfile.ZipFile(dest/'hk_ipo_dashboard.zip','w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:z.write(dest/'hk_ipo_dashboard.html','hk_ipo_dashboard.html')
with zipfile.ZipFile(dest/'hk_ipo_dashboard.zip') as z:assert z.read('hk_ipo_dashboard.html')==(dest/'hk_ipo_dashboard.html').read_bytes()
checks=['request scopes, factoring and relocation','native formula/valuation fixtures','actual scoring across 526 issuers and three targets','complete native package/source parity','426 SVG cases and control/focus tests','6773 comparison scope/average observations','selected average edge cases']
state=json.loads((ROOT/'data/release_state.json').read_text());state['release_date']='2026-10-22';state['publication']={'status':'local_only','github_updated_this_session':False}
state['validation']['request_efficiency_20261022']={'checks':checks,'workbook':excel,'html':web,'native_excel':native,'all_stored_updater_data_preserved':True,'market_data_refreshed':False,'terminal_speed_measured':False}
state['validation']['native_excel_open']='22 October final workbook opened in native Microsoft Excel without a content-repair prompt; compact Screener form/table reviewed. View-only installation; live Bloomberg responses and mode switching not tested.'
for name in ['HK_IPO_Database_v1.xlsx','hk_ipo_dashboard.html','hk_ipo_dashboard.zip','hk_ipo.py','READ_ME_FIRST.txt']:
 p=dest/name;state['deliverables'][name]={'bytes':p.stat().st_size,'sha256':sha(p)}
(ROOT/'data/release_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
audit=ROOT/'data/efficiency_20261022';audit.mkdir(exist_ok=True)
for name in ['workbook_checks.json','html_checks.json','native_visual_check.json','request_audit_before.json']:shutil.copyfile(OUT/name,audit/name)
shutil.copyfile(ROOT/'out/chart_scope_20261017/functional_checks.json',audit/'comparison_scope.json')
(audit/'checks.json').write_text(json.dumps({'passed':True,'checks':checks,'stored_market_data_unchanged':True,'publication':'local_only'},indent=2)+'\n')
print('PASS stored-input parity, updater module/template parity, native verification and delivery hashes')
print(json.dumps(state['deliverables'],indent=2))
