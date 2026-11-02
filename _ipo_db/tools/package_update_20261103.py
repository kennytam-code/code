"""Verify the November 3 release, then optionally install completed local files.

No Git/network mutations. Uses the prior immutable updater for input parity.
Run under the project's 512 MiB Python guard in the staged project.
"""
import ast,base64,codecs,gc,gzip,hashlib,io,json,re,shutil,sys,zipfile,zlib
from pathlib import Path
import xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parent.parent
WORK=Path('/Users/lemon/Desktop/REPO/code/_ipo_db')
BASE=ROOT.parent
sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def install(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    tmp=dst.with_name('.'+dst.name+'.nov3.tmp');shutil.copyfile(src,tmp);tmp.replace(dst)
def unpack(path):
    text=path.read_text()
    compressed=base64.b64decode(re.search(r'^_PAYLOAD = "([A-Za-z0-9+/=]+)"',text,re.M)[1])
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(re.search(r'^_LIBZIP = "([A-Za-z0-9+/=]+)"',text,re.M)[1]))) as z:
        lib={n:z.read(n) for n in z.namelist() if n!='__init__.py'}
    inline=ast.literal_eval(re.search(r'^_MODULES = (.+)$',text,re.M)[1])
    inline={n:zlib.decompress(base64.b64decode(v)) for n,v in inline.items()}
    del text
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
        buffer=buffer.lstrip();assert buffer.startswith(wanted);buffer=buffer[len(wanted):]
    def read():
        nonlocal buffer
        while True:
            buffer=buffer.lstrip()
            try:obj,end=decoder.raw_decode(buffer);break
            except json.JSONDecodeError:fill()
        buffer=buffer[end:];return obj
    data={};token('{')
    while True:
        key=read();token(':');contents=read();data[key]=hashlib.sha256(contents.encode()).hexdigest()
        while not buffer.strip():fill()
        buffer=buffer.lstrip()
        if buffer.startswith('}'):break
        token(',')
    return data,lib,inline

prior=json.loads((BASE/'previous_release.json').read_text())
assert digest(BASE/'before.xlsx')==prior['deliverables']['HK_IPO_Database_v1.xlsx']['sha256']
assert digest(BASE/'previous_updater.py')==prior['deliverables']['hk_ipo.py']['sha256']
olddata,oldlib,_=unpack(BASE/'previous_updater.py')
newdata,newlib,inlined=unpack(ROOT/'export/hk_ipo.py')
changed={p for p in olddata if newdata.get(p)!=olddata[p]}
assert changed=={'data/batches/newlistings.json','data/batches/pipeline_review.json'},changed
assert set(newdata)-set(olddata)=={'data/pipeline_peers.json'}
assert not(set(olddata)-set(newdata))
for p,h in newdata.items():assert digest(ROOT/p)==h,('Embedded data differs',p)
for p,b in newlib.items():assert b==(ROOT/'ipo_lib'/p).read_bytes(),('Embedded source differs',p)
for name,b in inlined.items():
    expected=(ROOT/'ipo_lib'/f'{name}.py').read_text().replace('ROOT = Path(__file__).resolve().parent.parent','ROOT = BUNDLE_ROOT').replace('if __name__ == "__main__":','if False:')
    assert b.decode()==expected,('Inlined builder differs',name)
source_changes={p for p in oldlib if newlib.get(p)!=oldlib[p]}
assert source_changes=={'build_xlsx.py','build_dashboard.py','pipeline_dedupe.py','staged_native_build.py'},source_changes
assert set(newlib)-set(oldlib)=={'bloomberg_mode_repair.py','pipeline_peer_inputs.py'}
del oldlib,newlib,inlined;gc.collect()
book=ROOT/'out/HK_IPO_Database_v1.xlsx'
checks=json.loads((ROOT/'out/update_20261103_checks.json').read_text())
assert digest(book)==checks['workbook_sha256']
def sheet(z,name):
    _,_,s=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
    return E.fromstring(z.read(s[name]))
with zipfile.ZipFile(BASE/'before.xlsx') as old,zipfile.ZipFile(book) as new:
    before=nodes(sheet(old,'Database'));after=nodes(sheet(new,'Database'))
    untouched=0
    for addr,c in before.items():
        if int(re.search(r'\d+',addr)[0])<5:continue
        assert E.tostring(c)==E.tostring(after[addr]),('Historical Database cell changed',addr)
        untouched+=1
    for name in ['AH History','AH Delta']:
        # AH Delta calculations/caches retain the Oct29 response handling.
        assert E.tostring(sheet(old,name))==E.tostring(sheet(new,name)),name
    chart_parts=[p for p in old.namelist() if p.startswith('xl/charts/') and p.endswith('.xml')]
    for p in chart_parts:assert old.read(p)==new.read(p),('Chart changed',p)
review=ROOT/'data/update_20261103';review.mkdir(exist_ok=True)
batch=json.loads((ROOT/'data/batches/newlistings.json').read_text())
accepted=[r for r in batch['deals'] if r.get('reviewed_at')=='2026-11-03']
assert len(accepted)==8
(review/'accepted.json').write_text(json.dumps(accepted,ensure_ascii=False,indent=2)+'\n')
report={**checks,'embedded_data_files':len(newdata),'changed_data_inputs':sorted(changed),'new_data_inputs':['data/pipeline_peers.json'],'unchanged_database_cells':untouched,'unchanged_chart_parts':len(chart_parts),'historical_ah_inputs_unchanged':True,'all_embedded_source_and_data_match':True,'checks_passed':['test_update_20261103: 105 formula/response fixtures','test_native_desk: structure, named weights and valuation fixtures','test_presentation_package: 168630 formula structures,19944 numeric source comparisons','test_desk_scoring: 527 rows x three targets','test_pipeline_release: actual renderer and code search','test_html_update_20261028: 432 SVG /40 detail cases','test_scope_update_20261028: 6775 scope/average observations'],'browser_review':{'pipeline_code_search':True,'hosin_compare_button':True,'hosin_pinned_peers':['3986','9976'],'introduction_filter':True,'console_errors':0},'native_excel':{'opened_without_repair':True,'reviewed':['Database default All','AH controls and rendered charts','Pipeline eight current listings','Screener automatic Hemay peers'],'view_only':True,'live_bloomberg_tested':False,'closed_without_saving':True},'artifact_projection':'Pipeline A4:L13,120 cells; rendered and visually checked','terminal_speed_or_memory_measured':False}
(review/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
html=ROOT/'out/hk_ipo_dashboard.html';zipout=ROOT/'out/hk_ipo_dashboard.zip'
with zipfile.ZipFile(zipout,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:z.write(html,html.name)
assert digest(BASE/'previous_READ_ME_FIRST.txt')==prior['deliverables']['READ_ME_FIRST.txt']['sha256']
readme=(BASE/'previous_READ_ME_FIRST.txt').read_text()
readme=readme.replace('HK IPO desk files — A/H formula fix 29 October 2026; data 28 October','HK IPO desk files — 3 November 2026; historical market snapshots unchanged')
readme=readme.replace('21 pipeline rows.','23 pipeline rows.')
readme=readme.replace('Database B2: Selected/All/Off live valuation scope. BBG Verify B2: Off/On.','Database B2 defaults All: PE/PS and forward valuations load for all issuers.\nSelected and Off remain optional. Screener reuses the same issuer results.\nBDH output areas are writable, without preallocated multi-cell array locks.\nBBG Verify B2 remains Off/On, default Off.')
readme=readme.replace('2384 DSBJ is listed.', 'Seven new offerings: 0054, 2065, 2206, 2681, 7672, 9621, 9917.\n1821 is an introduction. Terms were checked against HKEX prospectuses.\nPipeline cards open comparisons in Screener; Excel selects peer codes\nautomatically for the new offerings. These are business comparison sets.\nAP/PHIP membership outside these eight remains the 28 October review.\n2384 DSBJ is listed.')
(review/'READ_ME_FIRST.txt').write_text(readme)
state=json.loads(json.dumps(prior));state['release_date']='2026-11-03'
state['counts']['pipeline_rows']=23;state['dates']['pipeline_status_checked']='2026-11-03'
state['dates']['pipeline_scope']='Eight new launch/introduction documents checked Nov3; other AP/PHIP membership Oct28'
state['validation']['update_20261103']=report
state['validation']['fresh_browser_visual_review']=True
state['validation']['native_excel_open']='3 November: opened without repair; Database,AH,Pipeline,Screener reviewed. View-only Mac; no live Bloomberg test.'
state['known_limits']['browser']='Fresh Pipeline/Screener interaction review; A/H/Lock-up actual SVG and scope fixtures passed.'
state['known_limits']['ah_live_terminal']='Preallocated BDH multi-cell array locks removed. Native opening and formula fixtures checked; live Bloomberg mode switching and responses still require an entitled terminal.'
state['known_limits']['pipeline']='Current seven offerings and one introduction checked Nov3. Other AP/PHIP membership retains Oct28 review. Final subscriptions/allocations are not yet published for the new offerings.'
state['previous_publication']=prior['publication']
state['publication']={'status':'ready_to_publish','github_updated_this_session':False,'authorization':'User: push to github once done','repository':'https://github.com/kennytam-code/code','branch':'main'}
deliveries={'HK_IPO_Database_v1.xlsx':book,'hk_ipo.py':ROOT/'export/hk_ipo.py','hk_ipo_dashboard.html':html,'hk_ipo_dashboard.zip':zipout,'READ_ME_FIRST.txt':review/'READ_ME_FIRST.txt'}
state['deliverables']={n:{'bytes':p.stat().st_size,'sha256':digest(p)} for n,p in deliveries.items()}
(ROOT/'data/release_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
section='''## 3 November: Bloomberg modes and new offerings

This section supersedes the October defaults/array instructions below.
Database B2 defaults **All**, explicitly requested by the user. Selected/Off
remain optional. Scope is normalised once; Selected uses issuer codes and the
displayed peer codes. Five Screener H valuation fields reuse the database
issuer block; standalone H queries are reserved for pipeline-only codes. Off
also gates selected H/A forward requests. No new Bloomberg fields were added.
Out-of-scope values say Outside selection or Off, not ambiguous Not requested.

All 161 BDH anchors have **no preallocated multi-cell legacy CSE arrays**.
Bloomberg must own and resize its reply areas. Keep those zones empty. Retain
the 648 separate single-cell AH Delta array lookup calculations: they do not
occupy a Bloomberg reply zone. AH Quotes E4 and Charts H4 remain independent,
default Stored; 145 short histories serve 1D/7D/1M and 16 long chart calls are
guarded separately. Current prices still use scalar BDP LAST_PRICE. All-mode
valuation loading increases active requests relative to Selected by design;
actual terminal latency/RAM has not been measured.

527 database IPOs,717 Live stocks,72 A/H pairs,23 pipeline rows. New offerings:
0054,2065,2206,2681,7672,9621,9917;1821 is an introduction. Eight HKEX documents
were reviewed for terms, cornerstone legal names and percentages, sponsors,
lot size and timetable. No new final allocations/subscriptions are invented.
Other AP/PHIP membership remains Oct28. Market histories remain dated as in
the release state. CTG Hongkong/Macao tourism must not dedupe into CTG Duty-Free;
the HOSIN name variant and trailing PHIP class suffixes are handled explicitly.

data/pipeline_peers.json supplies reviewed business comparisons. Excel's
Screener P10 resolves these automatically for a pipeline selection; HTML cards
have Compare in Screener. Pinned companies lead the wider subsector ranking.
Comparison limitations are retained in the data; do not call every broad peer
an exact direct competitor. Introduction offer-only terms display N/A.

Final native stages: ah_live_requests, bloomberg_mode_repair,
pipeline_peer_inputs. Both new modules and peer inputs are in the standalone
updater. Use tools/test_update_20261103.py instead of the old AH test's CSE
expectations. data/update_20261103/validation.json records formula, package,
historical preservation, native Excel, browser and bounded Artifact checks.
Bloomberg live execution remains untested; this Mac is view-only. Validation
and source notes stay here, not in workbook tabs. See release_state publication
status/hash manifest for the exact delivery and GitHub commit.

'''
handover=(BASE/'previous_START_HERE.md').read_text()
if '## 3 November:' not in handover:handover=handover.replace('## 29 October:',section+'## 29 October:',1)
(ROOT/'START_HERE.md').write_text(handover)
if '--install' in sys.argv:
    sources=['ipo_lib/'+n+'.py' for n in ['build_xlsx','build_dashboard','pipeline_dedupe','staged_native_build','make_bundle','bloomberg_mode_repair','pipeline_peer_inputs']]
    sources+=['tools/'+n+'.py' for n in ['test_native_desk','test_update_20261103','package_update_20261103']]
    for rel in sources+['data/batches/newlistings.json','data/batches/pipeline_review.json','data/pipeline_peers.json','data/release_state.json','START_HERE.md']:
        install(ROOT/rel,WORK/rel)
    for p in review.iterdir():
        if p.is_file():install(p,WORK/'data/update_20261103'/p.name)
    for n,p in deliveries.items():
        for folder in ['TO_NOMURA','export']:
            install(p,WORK/folder/n)
        if n in ['HK_IPO_Database_v1.xlsx','hk_ipo_dashboard.html','hk_ipo_dashboard.zip']:install(p,WORK/'out'/n)
    for n,meta in state['deliverables'].items():
        assert digest(WORK/'TO_NOMURA'/n)==digest(WORK/'export'/n)==meta['sha256']
print(json.dumps({'passed':True,'embedded_data_files':len(newdata),'unchanged_database_cells':untouched,'unchanged_chart_parts':len(chart_parts),'deliverables':state['deliverables'],'installed':'--install' in sys.argv},indent=2))
