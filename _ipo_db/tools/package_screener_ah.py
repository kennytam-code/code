"""Package the checked code-selector / A/H presentation update, without data refresh."""
from pathlib import Path
import base64,gc,hashlib,io,json,re,shutil,sys,zipfile,zlib
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from make_bundle import DATA_FILES,LIB_MODULES
OUT=ROOT/'out/screener_ah_20261020';dest=ROOT/'TO_NOMURA'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
checks=json.loads((OUT/'checks.json').read_text());assert len(checks)==6 and all(c['passed'] for c in checks)
excel=json.loads((OUT/'workbook_checks.json').read_text());web=json.loads((OUT/'html_checks.json').read_text());native=json.loads((OUT/'native_visual_check.json').read_text())
assert excel['passed'] and web['passed'] and web['entire_payload_unchanged']
candidate=ROOT/'out/HK_IPO_Database_v1.xlsx'
assert sha(candidate)==excel['sha256']==native['sha256'] and native['opened_without_repair']
def payload(s):return json.loads(zlib.decompress(base64.b64decode(re.search(r'^_PAYLOAD = "([A-Za-z0-9+/=]+)"',s,re.M)[1])))
# Validate one decoded payload at a time, retaining only hashes of the baseline.
# Pass the prior released updater explicitly; a retry may follow partial local packaging.
baseline=Path(sys.argv[1]) if len(sys.argv)>1 else OUT/'baseline_hk_ipo.py'
old=payload(baseline.read_text());old_hash={k:hashlib.sha256(v.encode()).hexdigest() for k,v in old.items()};del old;gc.collect()
script=(ROOT/'export/hk_ipo.py').read_text()
small=re.sub(r'^_(PAYLOAD|LIBZIP) = "[A-Za-z0-9+/=]+"',r'_\1 = ""',script,flags=re.M)
compile(small,'hk_ipo.py','exec');del small
new=payload(script)
assert set(old_hash)<=set(new) and all(old_hash[k]==hashlib.sha256(new[k].encode()).hexdigest() for k in old_hash),'Existing stored inputs must remain identical'
for p in set(DATA_FILES):
    if (ROOT/p).exists():assert new[p]==(ROOT/p).read_text(),p
with zipfile.ZipFile(io.BytesIO(base64.b64decode(re.search(r'^_LIBZIP = "([A-Za-z0-9+/=]+)"',script,re.M)[1]))) as z:
    for name in LIB_MODULES:
        actual=z.read(name+'.py').decode();assert actual==(ROOT/'ipo_lib'/f'{name}.py').read_text(),name;compile(actual,name+'.py','exec')
del new,script;gc.collect()
for source,name in [(candidate,'HK_IPO_Database_v1.xlsx'),(ROOT/'out/hk_ipo_dashboard.html','hk_ipo_dashboard.html'),(ROOT/'export/hk_ipo.py','hk_ipo.py')]:shutil.copyfile(source,dest/name)
with zipfile.ZipFile(dest/'hk_ipo_dashboard.zip','w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:z.write(dest/'hk_ipo_dashboard.html','hk_ipo_dashboard.html')
with zipfile.ZipFile(dest/'hk_ipo_dashboard.zip') as z:assert z.read('hk_ipo_dashboard.html')==(dest/'hk_ipo_dashboard.html').read_bytes()
state=json.loads((ROOT/'data/release_state.json').read_text());state['release_date']='2026-10-20'
state['validation']['screener_ah_controls']={'date':'2026-10-20','checks':checks,'workbook':excel,'html':web,'native_excel':native,'market_data_refreshed':False,'all_existing_updater_inputs_preserved':True}
state['validation']['native_excel_open']='20 October final workbook opened in native Microsoft Excel without a content-repair prompt; Screener selector, resolved name and rankings visually reviewed. View-only installation; interactive edits and live Bloomberg responses not tested.'
for name in ['HK_IPO_Database_v1.xlsx','hk_ipo_dashboard.html','hk_ipo_dashboard.zip','hk_ipo.py','READ_ME_FIRST.txt']:
    p=dest/name;state['deliverables'][name]={'bytes':p.stat().st_size,'sha256':sha(p)}
(ROOT/'data/release_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
audit=ROOT/'data/screener_ah_20261020';audit.mkdir(exist_ok=True)
for name in ['checks.json','workbook_checks.json','html_checks.json','native_visual_check.json']:shutil.copyfile(OUT/name,audit/name)
print('PASS updater source/data parity, native verification hash and final delivery hashes')
print(json.dumps(state['deliverables'],indent=2))
