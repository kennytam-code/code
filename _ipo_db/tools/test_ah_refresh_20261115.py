"""Independent dates/arithmetic and preservation checks for the A/H refresh."""
import json,sys,math,hashlib
from pathlib import Path
from datetime import date
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'ipo_lib'))
from refresh_ah_history import merge_rows,aligned_append,kline
from market_universe import histories
from ah_basis import adjusted_premium,review_for
report=json.loads((ROOT/'data/ah_refresh_review/latest.json').read_text())
assert not report['errors'] and report['pair_count']==75
assert report['fx_asof']==report['csi_asof']=='2026-11-13'
assert all(r['after']=='2026-11-13' for r in report['pairs'])
# Overlap duplicates do not restate verified closes; incompatible prices fail.
assert merge_rows([['2026-10-01',10]],[['2026-10-01',10],['2026-10-02',11]],'2026-10-02')[0]==[['2026-10-01',10],['2026-10-02',11]]
try:merge_rows([['2026-10-01',10]],[['2026-10-01',9]],'2026-10-02')
except ValueError:pass
else:raise AssertionError('Accepted conflicting overlap')
try:kline('sh000300','2024-01-01','2026-11-13',lambda _:None)
except ValueError:pass
else:raise AssertionError('Accepted a range that could silently truncate')
assert not aligned_append([],[['2026-11-13',10]],[['2026-11-14',12]],[['2026-11-13',1]])
assert not aligned_append([],[['2026-11-13',10]],[['2026-11-01',12]],[['2026-11-13',1]])
assert not aligned_append([],[['2026-11-13',10]],[['2026-11-13',12]],[['2026-11-01',1]])
assert aligned_append([],[['2026-11-13',10]],[['2026-11-12',12]],[['2026-11-13',1]])[0][5]=='2026-11-12'
rows=histories(ROOT)['pairs'];observations=0
for r in rows:
 assert r['latest_date']==r['latest_h_date']==r['latest_a_date']==r['latest_fx_date']=='2026-11-13',r['code']
 assert [x[0] for x in r['history']]==sorted(set(x[0] for x in r['history']))
 for x in r['history']:
  assert all(math.isfinite(v) and v>0 for v in x[1:4])
  assert math.isclose(x[4],x[2]*x[3]/x[1]-1,rel_tol=1e-9,abs_tol=1e-9)
  assert 0<=(date.fromisoformat(x[0])-date.fromisoformat(x[5])).days<=10
  assert 0<=(date.fromisoformat(x[0])-date.fromisoformat(x[6])).days<=5
  observations+=1
 x=r['history'][-1];assert math.isclose(r['latest_premium_pct'],100*x[4],abs_tol=1e-9)
baseline=json.loads((ROOT/'data/ah_review_20261115/baseline_hashes.json').read_text())
for p in ['data/deals.json','data/peer_pairs.json','data/live_snapshot.json','data/batches/lockup_events.json','data/lockup_date_review.json','data/batches/ah_ipo.json']:
 assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==baseline[p],p+' changed'
print('PASS 75 dated pairs,',observations,'premium observations, no look-ahead, conflict fixtures and unrelated financial inputs unchanged')
