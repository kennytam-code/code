"""Accept the reviewed filings and preserve a separate audit of every change."""
import copy,json,re,sys,collections
from pathlib import Path
R=Path(__file__).resolve().parent.parent;P=R/'data/demand_review_20261109';sys.path.insert(0,str(R/'ipo_lib'))
load=lambda p:json.loads(p.read_text())
write=lambda p,d:p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
prose={d['code']:d for d in load(P/'remaining_outcome_prose.json')}
conditions={d['code']:d for d in load(P/'clawback_conditions.json')}
decisions={d['code']:d for d in load(P/'remaining_outcome_decisions.json')['decisions']}
def add(code,outcome,pattern,basis,page=None,terms=False):
 d=prose[code];p=next(p for p in d['pages'] if (page is None or p['page']==page) and re.search(pattern,p['text'],re.I));t=p['text'];m=re.search(pattern,t,re.I)
 e={'url':d['url'],'sha256':d['sha256'],'page':p['page'],'snippet':t[max(0,m.start()-350):m.end()+1400],'basis':basis}
 if terms:
  s=conditions[code];assert s['evidence'];e['prospectus_conditions']={'url':s['url'],'sha256':s['sha256'],'pages':s['evidence']}
 decisions[code]={'code':code,'clawback':outcome,'basis':basis,'evidence':e}
for c in ['2137','2192','6628']:add(c,'YES','reallocation','Filed demand-triggered public-tranche increase')
add('2145','NO','reallocation','Public under-subscription; reverse transfer to institutional tranche')
for c in ['2410','6166','2493']:add(c,'NO',r'Re-?allocation\s+No','Allocation results explicitly say no reallocation')
add('6727','YES',r'Reallocation\s+Yes','Filed reallocation under the separately verified Chapter 18C terms')
add('2651','NO','not been triggered','Announcement explicitly distinguishes actual reallocation from the untriggered clawback')
add('2121','NO','13.89 times','Filed public demand below the prospectus 15x trigger; no mandatory clawback',terms=True)
# The allocation notices and the applicable filed provisos are read together.
# A discretionary transfer is not the mandatory demand-triggered clawback.
for c in ['1440','2187','6680','2450','2439','2509','2497','2505','2443','2881','1334','2585','2613']:
 pattern=r'under.?subscr|re-?allocation'
 if c in ['2509','2497','2505','2443','2881']:pattern=r'INTERNATIONAL.{0,400}Subscription\s+Level|PLACING.{0,400}Subscription\s+Level'
 if c=='2439':pattern='clawback mechanism'
 add(c,'NO',pattern,'Discretionary/shortfall reallocation; mandatory clawback conditions not met. Source terms and actual subscription coverage reviewed together.',terms=True)
decisions['2439']['clawback_reported']='YES'
# Preserve the issuer wording separately: this filing calls a GL91-18 transfer
# "clawback", although its mandatory PN18 tier condition was not met.
records=load(R/'data/batches/allocation_source_review.json');review={d['code']:d for d in records['deals']}
for c,r in decisions.items():
 target=review.setdefault(c,{'code':c,'evidence':r['evidence']});target['clawback']=r['clawback'];target['outcome_evidence']=r['evidence'];target['outcome_evidence']['basis']=r['basis']
 if 'clawback_reported' in r:target['clawback_reported']=r['clawback_reported']
records['deals']=list(review.values());records['completed_date']='2026-11-10';records['method']='Explicit filed mechanism and actual mandatory-clawback outcome, reviewed separately. Discretionary/reverse transfers are not mandatory clawbacks. No final-allocation percentage or listing-date inference.'
write(R/'data/batches/allocation_source_review.json',records)
write(P/'remaining_outcome_decisions.json',{'decisions':list(decisions.values()),'held':[c for c in prose if c not in decisions]})
from demand_review import apply_records
from capital_review import apply_records as capital
raw=load(P/'before_deals.json');before=copy.deepcopy(raw);apply_records(raw['deals'],R);capital(raw['deals'],R)
again=copy.deepcopy(raw);apply_records(again['deals'],R);capital(again['deals'],R);assert again==raw
changes=[]
for a,b in zip(before['deals'],raw['deals']):
 diff={k:{'before':a.get(k),'after':b.get(k)} for k in set(a)|set(b) if a.get(k)!=b.get(k) and k!='_prov'}
 if diff:changes.append({'code':a['code'],'changes':diff})
write(P/'accepted_changes.json',changes);write(R/'data/deals.json',raw)
print('Resolved',len(decisions),'of',len(prose),'prior missing outcomes; held',[c for c in prose if c not in decisions])
print('Outcomes',collections.Counter(d['clawback_status'] for d in raw['deals']))
