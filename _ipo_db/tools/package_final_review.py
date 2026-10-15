"""Package the validated desk release with exact source/data bundle parity."""
from pathlib import Path
import base64,hashlib,io,json,re,shutil,sys,zipfile,zlib
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from make_bundle import DATA_FILES,LIB_MODULES
from build_dashboard import load
qa=json.loads((ROOT/'out/final_review_20261015/final_tests.json').read_text());assert all(x['exit']==0 for x in qa)
script=(ROOT/'export/hk_ipo.py').read_text();compile(script,'hk_ipo.py','exec')
blob=json.loads(zlib.decompress(base64.b64decode(re.search(r'^_PAYLOAD = "([A-Za-z0-9+/=]+)"',script,re.M)[1])))
for p in set(DATA_FILES):
 source=ROOT/p
 if source.exists():assert blob[p]==source.read_text(),('Bundle data mismatch',p)
with zipfile.ZipFile(io.BytesIO(base64.b64decode(re.search(r'^_LIBZIP = "([A-Za-z0-9+/=]+)"',script,re.M)[1]))) as z:
 for name in LIB_MODULES:
  actual=z.read(name+'.py').decode();assert actual==(ROOT/'ipo_lib'/f'{name}.py').read_text(),name;compile(actual,name+'.py','exec')
del blob,script
dest=ROOT/'TO_NOMURA';dest.mkdir(exist_ok=True)
for name in ['HK_IPO_Database_v1.xlsx','hk_ipo_dashboard.html','database_numeric_audit.md','database_numeric_audit.csv','database_numeric_audit.json','database_numeric_changes.csv','cornerstone_name_review.csv']:shutil.copyfile(ROOT/'out'/name,dest/name)
shutil.copyfile(ROOT/'export/hk_ipo.py',dest/'hk_ipo.py')
with zipfile.ZipFile(dest/'hk_ipo_dashboard.zip','w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:z.write(dest/'hk_ipo_dashboard.html','hk_ipo_dashboard.html')
with zipfile.ZipFile(dest/'hk_ipo_dashboard.zip') as z:assert z.read('hk_ipo_dashboard.html')==(dest/'hk_ipo_dashboard.html').read_bytes()
audit=json.loads((dest/'database_numeric_audit.json').read_text());live=json.loads((ROOT/'data/live_snapshot.json').read_text());meta=json.loads((ROOT/'data/desk_chart_data.json').read_text());deals,_,_,pipe=load()
state={'release_date':'2026-10-16','handover':'START_HERE.md','counts':{'database_screener':len(deals),'live_universe':meta['listed_count'],'ah_pairs':len(meta['pairs']),'peer_pairs':35,'peer_stocks':66,'pipeline_rows':len(pipe),'html_lockup_events':audit['lockups']['visible_rows'],'html_lockup_stocks':audit['lockups']['visible_stocks']},'dates':{'pipeline_status_checked':'2026-10-15','live_fetch':live['asof'],'live_saved_quotes':len(live['quotes']),'live_current_quotes':sum(q['quote_time'][:10]==live['asof'] for q in live['quotes'].values()),'live_daily_returns':sum(q['quote_time'][:10]==live['asof'] and bool(q.get('previous_close')) for q in live['quotes'].values()),'ah_pair_latest_dates':{dt:sum(p['latest_date']==dt for p in meta['pairs']) for dt in sorted({p['latest_date'] for p in meta['pairs']})}},'validation':{'python_checks_passed':len(qa),'javascript_checks':['selected averages','sector comparisons','pipeline actual renderer'],'numeric_entries':audit['numeric_values'],'internal_numeric_failures':len(audit['errors']),'existing_525_stock_numeric_changes':audit['material_changes'],'native_excel_open':'Final file opened without content-repair prompt; Live, AH, Peer Trades and Screener visually inspected. Database and Pipeline also visually inspected; final Screener form rechecked.','other_tabs_style_preservation':'13 sheets: business values, formulas and caches preserved, including seven relocated Screener outputs; requested titles removed; chart data, axes, drawing anchors and relationships unchanged','small_projection_review':['Database','Pipeline','IPO Live','AH','Peer Trades','Screener','CS League','SM League','Taxonomy','Notes','BBG Verify','Scoring Stats','SizeBench','Verification'],'fresh_browser_visual_review':False,'live_bloomberg_execution':False,'bundle_parity':'All embedded source modules and existing data/template files match their inputs'},'known_limits':{'financial_cells_needing_primary_followup':len(audit['unconfirmed_financials']),'earlier_cornerstone_aliases_unresolved':audit['cornerstone']['unresolved_name_aliases'],'undated_visible_lockup_events':audit['lockups']['unconfirmed_visible_expiries'],'market_dates':'Most historical series remain 2 October; a new quote/listing does not refresh them all.','browser':'Current HTML data and actual renderer functions checked locally; no fresh browser visual pass.','bloomberg':'Formula fixtures passed; terminal/add-in responses remain unverified.'},'deliverables':{}}
notes_review=ROOT/'data/notes_review_20261016.json'
if notes_review.exists():
 notes=json.loads(notes_review.read_text());assert all(x['exit']==0 for x in notes['checks'])
 state['validation']['notes_removal']=notes
 state['validation']['native_excel_open']='Final Notes-free workbook opened in native Excel without a content-repair prompt; all ten visible sheet tabs present, Screener form and rankings rendered. Earlier unchanged views retain their prior visual review.'
 state['validation']['small_projection_review']=[s for s in state['validation']['small_projection_review'] if s!='Notes']
 state['known_limits']['taxonomy']='Framework reviewed and retained; confirmed assignment errors in 2477 and 2321 remain recommendations, not applied changes. See data/taxonomy_review_20261016.json.'
for name in ['HK_IPO_Database_v1.xlsx','hk_ipo_dashboard.html','hk_ipo_dashboard.zip','hk_ipo.py','READ_ME_FIRST.txt']:
 p=dest/name;state['deliverables'][name]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(ROOT/'data/release_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
shutil.copyfile(ROOT/'out/final_review_20261015/final_tests.json',ROOT/'data/final_review_20261015/final_tests.json')
print('PASS bundle source/template/data parity and Python compilation; packaged Excel, HTML, compressed HTML and updater')
print(json.dumps({'counts':state['counts'],'dates':state['dates'],'sizes_MB':{k:round(v['bytes']/1e6,2) for k,v in state['deliverables'].items()}},indent=2))
