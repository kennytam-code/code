"""Deliver the tested AH-only repair locally, preserving market inputs and studies.

No network or Git mutations. Run after formula/native Excel validation.
"""
import json,hashlib,shutil,sys,re,base64,zlib,zipfile,io,gc,codecs
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
WORK=Path('/Users/lemon/Desktop/REPO/code/_ipo_db')
REVIEW=ROOT/'data/ah_live_fix_20261029';REVIEW.mkdir(exist_ok=True)
FOLDER=ROOT/'out/ah_live_fix_20261029'
BASE=FOLDER/'published_base'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def install(source,target):
    # Replacing a completed temporary file avoids partial/truncated deliverables
    # and does not open an evicted iCloud placeholder for writing.
    target.parent.mkdir(exist_ok=True,parents=True)
    temp=target.with_name('.'+target.name+'.ahfix.tmp')
    shutil.copyfile(source,temp);temp.replace(target)
def unpack(path):
    text=path.read_text()
    compressed=base64.b64decode(re.search(r'^_PAYLOAD = "([A-Za-z0-9+/=]+)"',text,re.M)[1])
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(re.search(r'^_LIBZIP = "([A-Za-z0-9+/=]+)"',text,re.M)[1]))) as z:
        lib={n:z.read(n) for n in z.namelist() if n!='__init__.py'}
    del text
    # Do not decode the entire 72 MB JSON into one four-byte Unicode string.
    # Parse one embedded file at a time, retaining only its digest.
    inflater=zlib.decompressobj();utf8=codecs.getincrementaldecoder('utf-8')()
    def chunks():
        tail=compressed
        while tail:
            raw=inflater.decompress(tail,1048576);tail=inflater.unconsumed_tail
            yield utf8.decode(raw)
        yield utf8.decode(inflater.flush(),final=True)
    source=iter(chunks());buffer='';decoder=json.JSONDecoder()
    def fill():
        nonlocal buffer
        buffer+=next(source)
    def token(wanted):
        nonlocal buffer
        while not buffer.strip():fill()
        buffer=buffer.lstrip();assert buffer.startswith(wanted),(wanted,buffer[:30]);buffer=buffer[len(wanted):]
    def read():
        nonlocal buffer
        while True:
            buffer=buffer.lstrip()
            try:obj,end=decoder.raw_decode(buffer);break
            except json.JSONDecodeError:fill()
        buffer=buffer[end:];return obj
    data={};token('{')
    while True:
        key=read();token(':');contents=read()
        data[key]=hashlib.sha256(contents.encode()).digest();del contents
        while not buffer.strip():fill()
        buffer=buffer.lstrip()
        if buffer.startswith('}'):break
        token(',')
    return data,lib

oldpath=ROOT/'TO_NOMURA/hk_ipo.py'
assert digest(oldpath)=='ca5caf434b336861359b4d27fe597456824733db9e62111c06b4dfd3c6c6f68f'
olddata,oldlib=unpack(oldpath)
oldhash=olddata
oldlibhash={p:hashlib.sha256(v).digest() for p,v in oldlib.items()}
old_staged=oldlib['staged_native_build.py']
del olddata,oldlib;gc.collect()
newdata,newlib=unpack(ROOT/'export/hk_ipo.py')
assert set(newdata)-set(oldhash)=={'data/ah_live_controls.json'}
assert not(set(oldhash)-set(newdata))
for p,d in oldhash.items():assert newdata[p]==d,('Unexpected market/template change',p)
assert set(newlib)-set(oldlibhash)=={'ah_live_requests.py'}
assert not(set(oldlibhash)-set(newlib))
for p,data in newlib.items():
    assert data==(ROOT/'ipo_lib'/p).read_bytes(),('Bundle source mismatch',p)
    if p not in ['ah_live_requests.py','staged_native_build.py']:assert hashlib.sha256(data).digest()==oldlibhash[p],('Unexpected module change',p)
for p,data in newdata.items():assert hashlib.sha256((ROOT/p).read_text().encode()).digest()==data,('Bundle data mismatch',p)
assert b"('ah_live_requests','apply')" in newlib['staged_native_build.py']
# The existing source may include edits authored earlier in this same fix.
for name in ['staged_native_build.py']:
    current=(WORK/'ipo_lib'/name).read_bytes()
    assert current in [old_staged,newlib[name]],('Unrelated workspace edits',name)
del newdata,newlib;gc.collect()

checks=json.loads((FOLDER/'formula_checks.json').read_text())
book=ROOT/'out/HK_IPO_Database_v1.xlsx'
assert digest(book)==checks['workbook_sha256']
native=json.loads((REVIEW/'native_excel.json').read_text())
assert native['sha256']==digest(book) and native['opened_without_repair']
base_state=BASE/'data_release_state.json'
assert base_state.stat().st_size==(WORK/'data/release_state.json').stat().st_size
prior=json.loads(base_state.read_text())
for name in ['HK_IPO_Database_v1.xlsx','hk_ipo.py','hk_ipo_dashboard.html','hk_ipo_dashboard.zip','READ_ME_FIRST.txt']:
    # All five SHA-256 comparisons passed in the earlier invocation before its
    # subsequent START_HERE read hung. iCloud has evicted the same bytes again.
    # Guard that verified baseline's file metadata rather than rehydrating it.
    stat=(WORK/'TO_NOMURA'/name).stat()
    expected_time={'HK_IPO_Database_v1.xlsx':'2026-10-28 23:37','hk_ipo.py':'2026-10-28 23:38','hk_ipo_dashboard.html':'2026-10-28 23:38','hk_ipo_dashboard.zip':'2026-10-28 23:38','READ_ME_FIRST.txt':'2026-10-29 00:00'}[name]
    assert stat.st_size==prior['deliverables'][name]['bytes'] and datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')==expected_time,('Workspace delivery changed',name)
for name in ['hk_ipo_dashboard.html','hk_ipo_dashboard.zip']:
    assert digest(ROOT/'TO_NOMURA'/name)==prior['deliverables'][name]['sha256']

# Exact immutable published base; the same local handover was read at start.
# Its size and modification time remain unchanged, but iCloud re-evicted it.
assert (BASE/'START_HERE.md').stat().st_size==(WORK/'START_HERE.md').stat().st_size
handover=(BASE/'START_HERE.md').read_text()
section='''## 29 October: Bloomberg A/H horizon repair

Local workbook fix; the previous 28 October data release remains on GitHub.
Market observations and all accepted financial inputs are unchanged.

AH E4 is now **Quotes** (Stored/Bloomberg), H4 is **Charts** (Stored/Bloomberg).
Both default Stored. For a live table without long history requests, choose
E4 Bloomberg and leave H4 Stored. Current A/H prices use scalar BDP LAST_PRICE;
one FX quote is shared. The independent IPO-price checker still follows E4.

1D/7D/1M are premium changes in percentage points. All references use the H
quote date: previous H session, seven calendar days earlier, or one calendar
month earlier. A and FX observations are as-of the chosen H close, with the
existing independent entitlement factors. Do not change them into stock returns.
One short H history and one A history per pair plus one shared FX history serve
all three horizons (145 guarded BDH occurrences for 72 pairs, 55 calendar days).
Long chart requests (16 occurrences) only activate with H4 Bloomberg. Counts
are formula occurrences, not measured terminal requests or RAM benchmarks.

The final native stage is ah_live_requests.apply after excel_chart_refresh.
It declares bounded two-column native BDH array ranges; header/error/blank-safe
lookup scans are single-cell native arrays for older Excel compatibility.
Quote-date normalization handles serials, YYYYMMDD numbers/text and date text.
H/A/FX positions are shared per horizon instead of repeated nested searches.
Missing replies show No quote, No date, No history or Too new, not zero or a
silent error. Group averages exclude unavailable text. Do not restore blanket
IFERROR blanks or couple table and long-chart request switches.

The small control template is data/ah_live_controls.json, authored via Artifact.
Tests: tools/test_ah_live_requests.py plus native_desk, presentation_package
and update_20261028. All original data/chart caches and 62 unaffected ZIP parts
are identical. Native Excel opened the final package without repair; the AH
table, controls and charts were reviewed. Bloomberg execution remains untested
without an entitled terminal. Review evidence: data/ah_live_fix_20261029/.

'''
assert '## 29 October: Bloomberg A/H horizon repair' not in handover
handover=handover.replace('## 28 October: new listing',section+'## 28 October: new listing',1)
handover=handover.replace('| AH | B4 chart pair; E4 Stored/Bloomberg.', '| AH | B4 chart pair; E4 Quotes Stored/Bloomberg; H4 independent Charts source.')
(ROOT/'START_HERE.md').write_text(handover)

readme=(WORK/'TO_NOMURA/READ_ME_FIRST.txt').read_text()
readme=readme.replace('HK IPO desk files — 28 October 2026','HK IPO desk files — A/H formula fix 29 October 2026; data 28 October')
readme=readme.replace('AH: E4 chooses Stored or Bloomberg.', 'AH: E4 Quotes chooses Stored or Bloomberg. H4 Charts is independent.\nFor a live table with less history work, use E4 Bloomberg and H4 Stored.\nCurrent prices use BDP LAST_PRICE; a short shared history feeds the changes.')
readme=readme.replace('observations. A first-day IPO has no previous H trading close.', 'observations. Seven-day/month reference dates also follow the H quote date.\nA first-day IPO has no previous H trading close. Missing history or dates\nshow a short status instead of a silent blank. Sector means exclude missing.')
readme=readme.split('\nGitHub downloads:\n')[0]+'\nThis 29 October A/H fix is local. GitHub still has the prior published release.\n'
(REVIEW/'READ_ME_FIRST.txt').write_text(readme)

state=dict(prior)
state['previous_publication']=prior['publication']
state['release_date']='2026-10-29'
state['data_release_date']='2026-10-28'
state['publication']={'status':'local_only','github_updated_this_session':False,'prior_release_commit':prior['publication'].get('release_commit'),'reason':'A/H follow-up repair has not received a new publication instruction.'}
state['validation']['ah_live_fix_20261029']={**checks,'native_excel':native,'bundle_market_inputs_unchanged':True,'html_byte_identical':True,'checks_passed':['test_ah_live_requests','test_native_desk','test_presentation_package','test_update_20261028']}
state['validation']['native_excel_open']='29 October AH formula repair opened without repair. AH controls/table/charts reviewed, then closed without saving. Mac view-only; no live Bloomberg execution.'
state['known_limits']['ah_live_terminal']='Formula and response-fixture checks passed; actual Bloomberg add-in responses/entitlements are not verified. Quotes and Charts use separate switches.'
deliveries={'HK_IPO_Database_v1.xlsx':book,'hk_ipo.py':ROOT/'export/hk_ipo.py','READ_ME_FIRST.txt':REVIEW/'READ_ME_FIRST.txt'}
state['deliverables']={**prior['deliverables'],**{name:{'bytes':p.stat().st_size,'sha256':digest(p)} for name,p in deliveries.items()}}
(ROOT/'data/release_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
report={'data_inputs_unchanged':True,'html_unchanged':True,'native_excel':native,'formula_checks':checks,'deliverables':state['deliverables'],'github_updated':False}
(REVIEW/'delivery_checks.json').write_text(json.dumps(report,indent=2)+'\n')
shutil.copyfile(FOLDER/'formula_checks.json',REVIEW/'formula_checks.json')

if '--install' in sys.argv:
    for rel in ['ipo_lib/ah_live_requests.py','ipo_lib/staged_native_build.py','ipo_lib/make_bundle.py','data/ah_live_controls.json','tools/create_ah_live_controls.mjs','tools/test_ah_live_requests.py','tools/package_ah_fix_20261029.py','START_HERE.md','data/release_state.json']:
        target=WORK/rel;install(ROOT/rel,target)
    for p in REVIEW.iterdir():
        target=WORK/'data/ah_live_fix_20261029'/p.name;install(p,target)
    for folder in ['TO_NOMURA','out','export']:
        for name,source in deliveries.items():
            target=WORK/folder/name;install(source,target)
            assert digest(target)==state['deliverables'][name]['sha256']
    for name in ['controls.png','controls.xlsx']:
        target=WORK/'out/ah_live_fix_20261029'/name;install(FOLDER/name,target)
    print('Installed local fix; all delivery copies have verified SHA-256. No Git operation.')
else:print('Checked package; --install writes it to the workspace.')
print(json.dumps({name:state['deliverables'][name] for name in deliveries},indent=2))
