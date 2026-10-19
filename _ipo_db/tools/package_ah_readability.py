"""Package a verified presentation-only release without refreshing market data."""
from pathlib import Path
import base64,hashlib,io,json,re,shutil,sys,zipfile,zlib
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from make_bundle import DATA_FILES,LIB_MODULES
OUT=ROOT/'out/ah_readability_20261019';dest=ROOT/'TO_NOMURA'
checks=json.loads((OUT/'checks.json').read_text());assert len(checks)==6 and all(x['passed'] for x in checks)
excel=json.loads((OUT/'workbook_checks.json').read_text());web=json.loads((OUT/'html_checks.json').read_text());native=json.loads((OUT/'native_visual_check.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
candidate=OUT/'HK_IPO_Database_v1.xlsx';assert sha(candidate)==excel['sha256']==native['sha256']
assert native['opened_without_repair'] and native['combined_and_comparison_charts_reviewed'] and web['entire_payload_unchanged']
oldscript=(dest/'hk_ipo.py').read_text();script=(ROOT/'export/hk_ipo.py').read_text();compile(script,'hk_ipo.py','exec')
def payload(s):return json.loads(zlib.decompress(base64.b64decode(re.search(r'^_PAYLOAD = "([A-Za-z0-9+/=]+)"',s,re.M)[1])))
old=payload(oldscript);new=payload(script)
assert set(old)<=set(new),'The updater must not lose any previously embedded input'
assert {k for k in old if old[k]!=new[k]}<={'assets/desk_monitors.js'},'A chart-style release must preserve all existing embedded data'
for p in set(DATA_FILES):
    source=ROOT/p
    if source.exists():assert new[p]==source.read_text(),p
with zipfile.ZipFile(io.BytesIO(base64.b64decode(re.search(r'^_LIBZIP = "([A-Za-z0-9+/=]+)"',script,re.M)[1]))) as z:
    for name in LIB_MODULES:
        actual=z.read(name+'.py').decode();assert actual==(ROOT/'ipo_lib'/f'{name}.py').read_text(),name;compile(actual,name+'.py','exec')
del old,new,script,oldscript
for source,target in [(candidate,dest/'HK_IPO_Database_v1.xlsx'),(candidate,ROOT/'out/HK_IPO_Database_v1.xlsx'),(ROOT/'out/hk_ipo_dashboard.html',dest/'hk_ipo_dashboard.html'),(ROOT/'export/hk_ipo.py',dest/'hk_ipo.py')]:shutil.copyfile(source,target)
with zipfile.ZipFile(dest/'hk_ipo_dashboard.zip','w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:z.write(dest/'hk_ipo_dashboard.html','hk_ipo_dashboard.html')
with zipfile.ZipFile(dest/'hk_ipo_dashboard.zip') as z:assert z.read('hk_ipo_dashboard.html')==(dest/'hk_ipo_dashboard.html').read_bytes()
state=json.loads((ROOT/'data/release_state.json').read_text());state['release_date']='2026-10-19'
state['validation']['ah_chart_readability']={'date':'2026-10-19','checks':checks,'workbook':excel,'html':web,'native_excel':native,'market_data_refreshed':False,'live_bloomberg_execution':False,'bundle_existing_data_preserved':True}
state['validation']['native_excel_open']='19 October final workbook opened in native Microsoft Excel without a content-repair prompt; combined A/H and comparison charts visually reviewed at 90% zoom and after scrolling. View-only installation; no live Bloomberg execution.'
for name in ['HK_IPO_Database_v1.xlsx','hk_ipo_dashboard.html','hk_ipo_dashboard.zip','hk_ipo.py','READ_ME_FIRST.txt']:
    p=dest/name;state['deliverables'][name]={'bytes':p.stat().st_size,'sha256':sha(p)}
(ROOT/'data/release_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
audit=ROOT/'data/ah_readability_20261019';audit.mkdir(exist_ok=True)
for name in ['checks.json','workbook_checks.json','html_checks.json','native_visual_check.json']:shutil.copyfile(OUT/name,audit/name)
print('PASS updater data/source parity, native verification hash and final delivery hashes')
print(json.dumps(state['deliverables'],indent=2))
