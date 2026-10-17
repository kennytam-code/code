"""Run desk release checks sequentially with small per-check logs."""
import os,subprocess,sys,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
out=ROOT/'out/final_review_20261015';out.mkdir(exist_ok=True)
checks=['tools/test_final_polish.py','tools/test_desk_theme.py','tools/test_remove_notes.py','tools/test_native_desk.py','tools/test_presentation_package.py','tools/test_presentation_formulas.py','tools/test_desk_scoring.py','tools/test_sector_monitor_release.py','ipo_lib/audit_formulas.py','ipo_lib/lint_bbg.py','ipo_lib/audit_numbers.py','ipo_lib/audit_prices.py','ipo_lib/checks.py']
checks.append('tools/test_historical_lockups.py')
result=[]
for test in checks:
 start=time.time();log=out/(Path(test).stem+'.final.log')
 with log.open('w') as f:p=subprocess.run([sys.executable,test],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
 result.append(dict(test=test,exit=p.returncode,seconds=round(time.time()-start,1),log=str(log.relative_to(ROOT))))
 print(('PASS' if p.returncode==0 else 'FAIL'),test,flush=True)
 if p.returncode:print(log.read_text()[-3000:],flush=True)
(out/'final_tests.json').write_text(json.dumps(result,indent=2))
raise SystemExit(any(x['exit'] for x in result))
