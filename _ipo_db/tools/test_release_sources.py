"""Primary-source acceptance and cross-output roster regression checks."""
import json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from build_xlsx import load as excel_load
from build_dashboard import load as html_load
x=json.loads((ROOT/'data/deals.json').read_text());deals={d['code']:d for d in x['deals']};d=deals['1256']
assert d['ipo_date']=='2026-10-09' and d['final_price']==1.55
assert d['oversub_public_mult']==9.09 and d['oversub_intl_mult']==1.95
assert d['greenshoe_pct']==0 and d['greenshoe_exercised_final']=='no option'
assert d['offer_size_adjustment_shares']==47106000
accepted=json.loads((ROOT/'data/batches/latest_listed_review_20261015.json').read_text());e=accepted['evidence']['1256'];allocations=e.get('cornerstone_allocations',e.get('allocations'))
# The accepted record retains the legal subscriber list; the parent aggregate is not added again.
assert d['cornerstone_n']==10 and len(d['cornerstone_investors'])==10
assert any('Eurus Holdings SPC' in name for name in d['cornerstone_investors'])
assert not any(name=='ORIX Asia Asset Management Limited' for name in d['cornerstone_investors'])
assert sum(a['shares'] for a in allocations)==749354000
assert math.isclose(d['cornerstone_pct'],100*749354000/1617310000,abs_tol=.005)
assert math.isclose(d['first_day_return_pct'],100*(1.535/1.55-1),abs_tol=.005)
assert math.isclose(d['since_ipo_pct'],100*(1.43/1.55-1),abs_tol=.005)
for key in ['ret_1w_pct','ret_1m_pct','ret_3m_pct']:assert d.get(key) is None,key
old={d['code']:d for d in json.loads((ROOT/'out/deals_before_eswin_20261015.json').read_text())['deals']}
checked=0
for code,prior in old.items():
 for key,value in prior.items():
  if isinstance(value,(float,int)) and not isinstance(value,bool) and not key.startswith('_'):
   if deals[code].get(key)!=value:
    assert code=='9607' and key=='a_premium_now' and abs(deals[code][key]-value)<.0002,(code,key,value,deals[code].get(key))
   else:checked+=1
for load in [excel_load,html_load]:
 result=load();assert any(d['code']=='1256' for d in result[0]);assert not any(str(p.get('code'))=='1256' or 'ESWIN' in str(p.get('name','')) for p in result[3])
event=next(e for e in json.loads((ROOT/'data/batches/lockup_events.json').read_text())['events'] if e['code']=='1256')
assert event['last_day_locked']=='2027-04-08' and event['first_day_after']=='2027-04-09'
window=event['windows']['30 trading sessions'];assert not window.get('path')
for key in ['before_pct','after_pct']:assert window.get(key) is None
print(f'PASS primary ESWIN offer/subscription/upsizing/legal cornerstone/immature returns/future lock-up; both roster builders; {checked} pre-existing numeric fields unchanged; Red Avenue premium precision reconciled to dated raw quotes')

from review_quote_guard import quote_dates,allowed
assert allowed('last_close','2026-10-14','2026-10-14')
assert not allowed('last_close','2026-10-14','2026-10-15')
assert not allowed('a_premium_now','2026-10-02','2026-10-14')
assert allowed('a_share_code','2026-10-02','2026-10-14')
assert allowed('a_premium_ipo_pct','2026-10-02','2026-10-14')
assert quote_dates({'ah_snapshot':{'as_of':'2026-10-03T15:00:00','pairs':[{'code':'9607'}]}})['9607']=='2026-10-02'
assert quote_dates({'h_paths':{'deals':[{'code':'1256','ipo':'2026-10-09','closes':[[0,1.535],[7,1.5]]}]}})['1256']=='2026-10-16'
print('PASS future quote refresh supersedes accepted snapshots; verified mapping and historical IPO terms remain durable')
