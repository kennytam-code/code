"""Bounded, sequential checks for the A/H-only presentation release."""
import sys,subprocess,json,time,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'out/ah_readability_20261019'
node='/Users/lemon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
checks=['tools/test_ah_readability.py','tools/test_native_desk.py','tools/test_presentation_package.py','tools/test_ah_market_render.mjs','tools/test_comparison_scope.mjs','tools/test_selected_averages.mjs']
shutil.copyfile(OUT/'HK_IPO_Database_v1.xlsx',ROOT/'out/HK_IPO_Database_v1.xlsx')
results=[]
for test in checks:
    cmd=[node,'--max-old-space-size=384',test] if test.endswith('.mjs') else [sys.executable,test]
    log=OUT/(Path(test).stem+'.log');start=time.monotonic()
    with log.open('w') as f:p=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    result={'test':test,'passed':p.returncode==0,'seconds':round(time.monotonic()-start,1),'log':str(log.relative_to(ROOT))};results.append(result)
    print(('PASS' if result['passed'] else 'FAIL'),test,flush=True)
    if p.returncode:
        print(log.read_text()[-2200:]);break
(OUT/'checks.json').write_text(json.dumps(results,indent=2)+'\n')
raise SystemExit(any(not r['passed'] for r in results))
