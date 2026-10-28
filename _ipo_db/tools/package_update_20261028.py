"""Package the checked local release. This script never publishes to GitHub."""
import json,re,zlib,base64,zipfile,io,hashlib,shutil,sys,collections,gc
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;WORK=Path('/Users/lemon/Desktop/REPO/code/_ipo_db')
sys.path.insert(0,str(ROOT/'ipo_lib'))
from make_bundle import DATA_FILES,LIB_MODULES
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def semantic(text):
 # Compare one decoded JSON at a time, never three full databases together.
 obj=json.loads(text);h=hashlib.sha256()
 for chunk in json.JSONEncoder(sort_keys=True,ensure_ascii=False).iterencode(obj):h.update(chunk.encode())
 del obj;gc.collect();return h.digest()
oldscript=(ROOT/'out/update_20261028/baseline_hk_ipo.py').read_text()
old=json.loads(zlib.decompress(base64.b64decode(re.search(r'^_PAYLOAD = "([A-Za-z0-9+/=]+)"',oldscript,re.M)[1])).decode('utf-8'))
with zipfile.ZipFile(io.BytesIO(base64.b64decode(re.search(r'^_LIBZIP = "([A-Za-z0-9+/=]+)"',oldscript,re.M)[1]))) as z:oldlib={n:z.read(n) for n in z.namelist()}
changes=[];divergences=[]
for rel in sorted(set(DATA_FILES)):
 p=ROOT/rel
 if not p.exists():continue
 before=old.get(rel);after=p.read_text()
 if before==after:continue
 if rel.endswith('.json') and before is not None and semantic(before)==semantic(after):continue
 changes.append(rel)
 target=WORK/rel
 if before is not None and target.exists():
  current=target.read_text()
  if current not in [before,after] and not (rel.endswith('.json') and semantic(current) in [semantic(before),semantic(after)]):divergences.append(rel)
for mod in LIB_MODULES+['make_bundle']:
 rel='ipo_lib/'+mod+'.py';p=ROOT/rel
 if not p.exists():continue
 before=oldlib.get(mod+'.py');after=p.read_bytes()
 if before==after:continue
 changes.append(rel);target=WORK/rel
 if before is not None and target.exists() and target.read_bytes() not in [before,after]:divergences.append(rel)
if divergences==['data/conflicts.json']:
 # This is the generated disagreement report, not an accepted input batch.
 # Retain the workspace copy verbatim before installing the rebuilt report.
 shutil.copyfile(WORK/'data/conflicts.json',ROOT/'data/update_20261028/workspace_conflicts_before.json')
 divergences=[]
assert not divergences,('Preserve and reconcile existing user work',divergences)
prior_text=old['data/deals.json'];del old,oldscript,oldlib;gc.collect()
before={d['code']:d for d in json.loads(prior_text)['deals']};del prior_text;gc.collect()
now=json.loads((ROOT/'data/deals.json').read_text())['deals'];by={d['code']:d for d in now};numeric_changes=[]
for code,d in before.items():
 for k,v in d.items():
  if isinstance(v,(int,float)) and not isinstance(v,bool) and by[code].get(k)!=v:numeric_changes.append((code,k))
assert not numeric_changes,numeric_changes
del before,now,by;gc.collect()
print('Prior numeric preservation passed; released comparison payloads.',flush=True)
# Check embedded sources and data match the exact tested build inputs.
script=(ROOT/'export/hk_ipo.py').read_text();payload=json.loads(zlib.decompress(base64.b64decode(re.search(r'^_PAYLOAD = "([A-Za-z0-9+/=]+)"',script,re.M)[1])).decode('utf-8'))
for rel,contents in payload.items():assert (ROOT/rel).read_text()==contents,rel
with zipfile.ZipFile(io.BytesIO(base64.b64decode(re.search(r'^_LIBZIP = "([A-Za-z0-9+/=]+)"',script,re.M)[1]))) as z:
 for name in z.namelist():
  if name=='__init__.py':continue
  assert z.read(name)==(ROOT/'ipo_lib'/name).read_bytes(),name
del payload,script;gc.collect()
out=ROOT/'out';delivery=ROOT/'TO_NOMURA';delivery.mkdir(exist_ok=True)
for name in ['HK_IPO_Database_v1.xlsx','hk_ipo_dashboard.html']:shutil.copyfile(out/name,delivery/name)
shutil.copyfile(ROOT/'export/hk_ipo.py',delivery/'hk_ipo.py')
with zipfile.ZipFile(delivery/'hk_ipo_dashboard.zip','w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:z.write(out/'hk_ipo_dashboard.html','hk_ipo_dashboard.html')
readme='''HK IPO desk files — 28 October 2026

Open HK_IPO_Database_v1.xlsx for the desk workbook; open hk_ipo_dashboard.html
for the offline dashboard. The ZIP contains that same HTML.

527 listed IPOs; 717 stocks in IPO Live; 72 A/H pairs; 21 pipeline rows.
2384 DSBJ is listed. 6157 and 3275 have postponed their offerings.
IPO Live has 702 valid saved quotes, with individual dates. The latest is
28 October. Missing/stale quotes and debut-day reference prices are excluded
from daily averages. This update does not refresh every historical series.

AH: E4 chooses Stored or Bloomberg. G:I show premium changes in percentage
points over 1D, seven calendar days and one calendar month. 1D compares the
current premium with the previous H trading close, using dated A/FX as-of
observations. A first-day IPO has no previous H trading close.

AH top links: Group averages, IPO price check. The independent price checker
uses M60 for H code; optional M61 for A code and M62 for H IPO price. Numeric
codes only; suffixes are added internally. Known pairs auto-fill. New A codes
need Bloomberg mode for a live quote. It does not issue a history request.
The Screener keeps its own selected-company valuation fields and code lookup.

Premium and mainland returns now occupy aligned upper/lower charts. All
visible charts have consistent fonts, colours and axes; Live bars turn green
or red dynamically. Observed points and genuine gaps are preserved.

Database B2: Selected/All/Off live valuation scope. BBG Verify B2: Off/On.
Stored is the default for daily monitors. Bloomberg mode requires the add-in
and a logged-in entitled terminal. This Mac cannot certify live Bloomberg
replies. Native Excel opened the final file without a repair prompt.

Standalone updater: python hk_ipo.py build reproduces stored data; update
refreshes providers then builds. Keep its persistent data directory. Source
review and handover are in START_HERE.md and data/release_state.json in the
project. A new price does not certify old histories or old filing fields.

This release is saved locally; GitHub has not been updated in this session.
'''
(delivery/'READ_ME_FIRST.txt').write_text(readme)
state=json.loads((WORK/'data/release_state.json').read_text());state['previous_publication']=state['publication'];state['release_date']='2026-10-28'
state['counts'].update(database_screener=527,live_universe=717,ah_pairs=72,pipeline_rows=21)
snapshot=json.loads((ROOT/'data/live_snapshot.json').read_text());quotes=snapshot['quotes'];current=[v for v in quotes.values() if v['quote_time'][:10]==snapshot['asof']]
state['dates'].update(pipeline_status_checked='2026-10-28',live_fetch='2026-10-28',live_saved_quotes=len(quotes),live_current_quotes=len(current),live_daily_returns=sum(bool(v.get('previous_close')) for v in current),ah_pair_latest_dates={'2026-10-02':70,'2026-10-15':1,'2026-10-28':1})
state['validation']['update_20261028']=dict(workbook=json.loads((ROOT/'data/update_20261028/workbook_checks.json').read_text()),html=json.loads((out/'update_20261028/html_checks.json').read_text()),comparison_scope=json.loads((out/'update_20261028/scope_checks.json').read_text()),old_database_numeric_changes=0,bundle_inputs_match=True,native_excel_open_without_repair=True,native_tabs_reviewed=['IPO Live','AH selected and comparison charts','AH independent calculator','Peer Trades','Screener valuations'],live_bloomberg_tested=False)
state['validation']['native_excel_open']='28 October final workbook opened without repair; Live, AH, Peer Trades and moved Screener valuation area reviewed. View-only Mac; terminal responses and interactive inputs not tested live.'
state['known_limits']['market_dates']='IPO Live quote snapshot 28 October; 2384 A/H closes 28 October with completed FX close 27 October. Other A/H histories remain 2/15 October and peer histories 2 October. Missing remains unavailable; no full-history refresh.'
state['publication']={'status':'local_only','github_updated_this_session':False,'prior_release_date':'2026-10-22','reason':'Current update has no new publication instruction.'}
state['deliverables']={p.name:{'bytes':p.stat().st_size,'sha256':digest(p)} for p in delivery.iterdir()}
assert state['deliverables']['HK_IPO_Database_v1.xlsx']['sha256']==state['validation']['update_20261028']['workbook']['sha256']
(ROOT/'data/release_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
report=dict(changed_inputs=changes,prior_526_numeric_changes=0,all_bundle_inputs_match=True,deliverables=state['deliverables'],github_updated=False)
(ROOT/'data/update_20261028/delivery_checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
if '--install' in sys.argv:
 for rel in changes+['data/release_state.json','START_HERE.md']:
  dest=WORK/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dest)
 for p in (ROOT/'data/update_20261028').iterdir():
  dest=WORK/'data/update_20261028'/p.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
 for p in (ROOT/'tools').iterdir():
  if p.name in ['ah_projection.py','render_ah_projection.mjs','create_ah_update.mjs','accept_update_20261028.py','test_update_20261028.py','test_html_update_20261028.mjs','test_scope_update_20261028.mjs','package_update_20261028.py','test_native_desk.py','test_presentation_package.py']:shutil.copyfile(p,WORK/'tools'/p.name)
 for folder in ['TO_NOMURA','out','export']:
  (WORK/folder).mkdir(exist_ok=True)
  for p in delivery.iterdir():
   shutil.copyfile(p,WORK/folder/p.name);assert digest(p)==digest(WORK/folder/p.name)
 for p in (out/'update_20261028').iterdir():
  dest=WORK/'out/update_20261028'/p.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
 print('Installed locally; all delivery hashes match. No Git operation performed.')
