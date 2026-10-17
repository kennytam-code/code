"""Plan an explicit IPO-only publication; preserve unrelated files and research."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parent.parent
PUB=Path('/private/tmp/hkipo_publish_20261016')
files=[]
def add(p,relative=None):
 if not p.is_file():return
 rel=relative or '_ipo_db/'+str(p.relative_to(ROOT))
 dest=PUB/rel
 h=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
 old=subprocess.run(['git','show','HEAD:'+rel],cwd=PUB,capture_output=True)
 if old.returncode==0 and hashlib.sha256(old.stdout).hexdigest()==h(p):return
 if any(f['target']==rel for f in files):return
 files.append({'source':str(p),'target':rel,'sha256':h(p),'bytes':p.stat().st_size})
for name in ['AGENTS.md','START_HERE.md','MAINTENANCE.md','README.md','ipo.py']:add(ROOT/name)
for directory in ['ipo_lib','assets']:
 for p in sorted((ROOT/directory).glob('*')):
  if p.suffix in ['.py','.js','.LICENSE']:add(p)
for p in sorted((ROOT/'data').glob('*.json')):
 if p.name not in ['deals.json','conflicts.json','auto_splits.json']:add(p)
for name in ['market_views_template.json','entitlement_adjustments.json','ah_entitlement_reviews.json','market_supplement.json','peer_pairs.json','desk_chart_data.json']:add(ROOT/'data'/name)
for p in sorted((ROOT/'data/desk_review_20261012').glob('*.json')):add(p)
for name in ['HK_IPO_Database_v1.xlsx','hk_ipo_dashboard.html','hk_ipo_dashboard.zip','hk_ipo.py','READ_ME_FIRST.txt','database_numeric_audit.md','database_numeric_audit.csv','database_numeric_audit.json','database_numeric_changes.csv','cornerstone_name_review.csv']:add(ROOT/'TO_NOMURA'/name)
for name in ['HK_IPO_Database_v1.xlsx','hk_ipo_dashboard.html','hk_ipo.py','READ_ME_FIRST.txt']:add(ROOT/'TO_NOMURA'/name,name)
for name in ['create_market_template.mjs','enhance_market_template.mjs','review_option_capacity.py','fetch_option_prospectuses.py','review_desk_sources.py','audit_desk_filings.py','accept_desk_source_review.py','extract_market_supplement.py','prepare_market_supplement.py','fetch_market_supplement.py','fetch_peer_history.py','prepare_desk_chart_data.py','refresh_desk_windows.py','test_source_reviews.py','test_desk_comparisons.py','test_desk_dashboard.py','test_monitors.py','test_ah_dashboard.py','test_lockup_html.py','test_deliverable_review.py','test_lockup_excel.mjs','prepare_final_visual_probe.py','render_final_visual_probe.mjs']:add(ROOT/'tools'/name)
for name in ['create_presentation_template.mjs','prepare_ah_reference.py','test_presentation_formulas.py','test_presentation_package.py','prepare_presentation_probe.py','render_presentation_probe.mjs','prepare_publication.py']:add(ROOT/'tools'/name)
for name in ['curate_peer_pairs.py','restore_peer_history_ranges.py','test_peer_horizons.py','prepare_peer_visual_probe.py']:add(ROOT/'tools'/name)
for code in ['0006','0168','0688','0836','1211','1478','3692']:add(ROOT/'data/peer_price_cache'/f'{code}.json')
add(ROOT/'data/batches/ah_chart_review_20261013.json')
for name in ['test_comparison_scope.mjs','render_comparison_scope.mjs','fetch_lockup_review.py','review_lockup_tables.py','audit_lockup_dates.py','check_lockup_prices.py','check_lockup_listing_dates.py','accept_lockup_history.py','test_historical_lockups.py','package_chart_scope.py']:add(ROOT/'tools'/name)
for p in sorted((ROOT/'data/lockup_review_20261017').glob('*')):add(p)
for name in ['ah_map.json','ah_study.json','longsys_ah_review_20261014.json']:add(ROOT/'data/batches'/name)
for kind in ['a','h']:add(ROOT/'data/ah_study_cache'/f'{kind}_9976.json')
for name in ['create_monitor_layout.mjs','test_monitor_revision.py','test_latest_monitor_fixes.py','test_native_desk.py']:add(ROOT/'tools'/name)
add(ROOT/'data/batches/native_repair_review_20261014.json')
add(ROOT/'tools/test_release_sources.py')
add(ROOT/'tools/test_desk_scoring.py')
add(ROOT/'out/monitor_review_20261015.json','_ipo_db/data/monitor_review_20261015.json')
for name in ['latest_listed_review_20261015.json','hkex_allotments.json','h_paths.json','benchmark_prices.json','lockup_events.json']:add(ROOT/'data/batches'/name)
for p in sorted((ROOT/'data/eswin_review_20261015').glob('*.json')):add(p)
for p in sorted((ROOT/'data/red_avenue_review_20261015').glob('*.json')):add(p)
for kind in ['a','h']:add(ROOT/'data/ah_study_cache'/f'{kind}_9607.json')
for kind in ['a','h']:add(ROOT/'data/ah_study_cache'/f'{kind}_2636.json')
add(ROOT/'data/ah_study_cache/cnyhkd.json')
for name in ['pipeline.json','pipeline_review.json','phip_pipeline.json','newlistings.json']:add(ROOT/'data/batches'/name)
for p in sorted((ROOT/'data/final_review_20261015').glob('*')):add(p)
for name in ['create_database_layout.mjs','create_pipeline_layout.mjs','prepare_pipeline_layout.py','render_desk_tables.mjs','test_final_polish.py','test_sector_monitor_release.py','test_selected_averages.mjs','test_sector_comparisons.mjs','test_pipeline_release.mjs','run_release_checks.py']:add(ROOT/'tools'/name)
for name in ['create_desk_theme.mjs','test_desk_theme.py','render_desk_theme.mjs','package_final_review.py']:add(ROOT/'tools'/name)
for name in ['create_weight_layout.mjs','test_remove_notes.py']:add(ROOT/'tools'/name)
(ROOT/'out/publication_plan.json').write_text(json.dumps(files,indent=2));print('Prepared',len(files),'explicit changed files,',sum(f['bytes'] for f in files)//1024,'KB')
for f in files:print(f['target'])
