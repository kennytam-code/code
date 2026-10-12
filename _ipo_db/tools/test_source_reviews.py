"""Regressions for real audit failure modes, including wrong tranche/year,
non-IPO dates, and corporate actions inside the event window."""
import json,sys
from pathlib import Path
from datetime import date,timedelta
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from filing_review import subscriptions
from review_financial_numbers import rows
from review_lockups import events_from_pages,window
from extract_deep import parse_greenshoe_pct
assert parse_greenshoe_pct('The Offer Shares represent approximately 19.11% of the issued share capital, assuming that the Over-allotment Option is not exercised.')[0] is None
assert parse_greenshoe_pct('The Over-allotment Option granted to the representatives gives the right to require us to issue up to 1,500,000 additional Shares, representing approximately 15% of the Offer Shares initially available under the Global Offering.')[0]==15
assert parse_greenshoe_pct('The Over-allotment Option granted to the representatives gives the right to require us to issue up to 1,500,000 additional Shares, representing approximately 5% of the issued share capital.')[0] is None
assert parse_greenshoe_pct('The Over-allotment Option granted to the representatives gives the right to require us to issue up to 1,500,000 (representing 15.0% of the Offer Shares being offered under the Global Offering) Shares.')[0]==15
assert parse_greenshoe_pct('The Over-allotment Option means the option to be granted to the underwriters to require the seller to sell up to 26,000,000 Units, representing 5% of the total number of Units under the Global Offering.')[0]==5
assert parse_greenshoe_pct('We will not grant any over-allotment option to the underwriters.')[0]==0
deals={d['code']:d for d in json.loads((ROOT/'data/deals.json').read_text())['deals']}
assert deals['9607']['greenshoe_pct']==0 and deals['9607']['shoe_note']=='no over-allotment option'
pub='PUBLIC OFFER\nNo. of valid applications 20\nSubscription Level 3,546.91 times\n'
intl='INTERNATIONAL OFFER\nNo. of placees 10\nSubscription Level 2.72 times\n'
r=subscriptions([pub+intl]);assert r['public']['value']==3546.91 and r['intl']['value']==2.72
r=subscriptions([pub+'EMPLOYEE PREFERENTIAL OFFERING\nSubscription Level 208.56 times\n'+intl]);assert r['intl']['value']==2.72
r=subscriptions(['The Placing was under-subscribed, representing approximately 95.6% of the total number of Placing Shares initially available under the Placing.']);assert r['intl']['value']==.956
def financial(text):return rows({'pages':[{'page':1,'text':text}],'url':'https://www1.hkexnews.hk/example.pdf','sha256':'test'},'2026-09-01')
base='Year ended December 31, Three months ended March 31,\n2023 2024 2025 2025 2026\n(RMB in thousands)\n'
r=financial(base+'Revenue 100,000 200,000 300,000 40,000 50,000\nProfit for the year/period (10,000) (20,000) 30,000 4,000 5,000\nAttributable to:\nOwners of the Company (9,000) (18,000) 27,000 3,000 4,000');assert next(x for x in r if x['field']=='rev_latest')['value']==330;assert next(x for x in r if x.get('basis')=='Net income attributable to owners')['value']==29.7
r=financial('Year ended December 31, Six months ended June 30,\n2024 2025 2025 2026\n(RMB in thousands)\nRevenue – 259,612 306 413');assert r[0]['value']==285.5732 and r[0]['financial_year']==2025
assert not financial('Seven months ended October 31,\n2024 2025\n(RMB in thousands)\nTotal Revenue 68,219 338,391')
assert not financial(base+'Revenue 0.2% 0.3% 0.4% 0.1% 0.2%')
r=financial('Year ended December 31,\n2023 2024 2025\n(RMB in millions)\nRevenue 4,816.43,215.27,597.9');assert r[0]['value']==8357.69
r=financial('Year ended December 31,\n2023 2024 2025\n(RMB in thousands)\nRevenue 4 1 1,751 444,387 449,350');assert r[0]['value']==494.285
assert not financial(base+'Loss (123) (456) (789) (111) (222)')
t='Cornerstone Investors\nName\nLast day subject to lock-up undertakings\nInvestor A 1,000 5% 24 June 2027\nThe expiry date shown above follows the Prospectus.\nOVER-ALLOTMENT OPTION\nUntil 10 July 2026.'
ev=events_from_pages([t],'2026-06-25');assert [e['last_day_locked'] for e in ev]==['2027-06-24']
assert not events_from_pages(['Cornerstone Investors\n'+('ordinary text\n'*200)+'Last day subject to lock-up undertakings\n24 June 2027'],'2026-06-25')
sessions=[(date(2026,1,1)+timedelta(days=i)).isoformat() for i in range(50) if (date(2026,1,1)+timedelta(days=i)).weekday()<5];prices={d:100.0 for d in sessions};anchor=sessions[14]
pre=sessions[7];post=sessions[21];prices[post]=55.0
w=window(anchor,sessions,prices,[{'date':sessions[18],'ratio':2}],sessions[-1]);assert w['before_pct']==0 and abs(w['after_pct']-10)<1e-10
assert [p[0] for p in w['path']]==list(range(-7,8)) and w['path'][7]==[0,anchor,100.0] and w['path'][-1][2]==110.0
gap=prices.copy();del gap[sessions[16]];w=window(anchor,sessions,gap,[],sessions[-1]);assert w['path'][9][2] is None and w['after_pct'] is not None
no=prices.copy();del no[post];assert window(anchor,sessions,no,[],sessions[-1])['after_pct'] is None
assert window('2027-01-01',sessions,prices,[],sessions[-1])['before_pct'] is None
assert window(sessions[-2],sessions,prices,[],sessions[-1])['after_pct'] is None
w=window('2026-01-24',sessions,prices,[],sessions[-1],mode='Calendar days');assert w['anchor']=='2026-01-23' and w['pre_start']=='2026-01-16' and w['post_end']=='2026-01-30'
print('PASS own tranche, under-subscription, annual/stub columns, currency units, decimal kerning, owner earnings, lock-up section boundaries, split-neutral and missing/future windows')
