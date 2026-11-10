"""Context-reviewed outcome decisions, separate from source mechanism classification."""
import json,re
from pathlib import Path
R=Path(__file__).resolve().parent.parent;P=R/'data/demand_review_20261109'
rows=json.loads((P/'remaining_outcome_prose.json').read_text())
# These specific filed paragraphs state the subscription threshold and that the
# prospectus procedure was applied to increase the public tranche. No allocation
# percentage rule is used to create this list.
yes=set('9600 1855 2129 1643 2125 2158 1490 9608 2159 6668 2160 1024 2170 1473 6601 1413 1927 9888 9626 6939 6608 2195 9959 9961 6622 2618 6699 2171 2155 2150 2190 2219 2162 2209 2177 6909 9960 2205 6609 6669 9869 2252 2265 2279 2392 2172 2237 2321 2350 2440 1947 9985 2457 2469 2147 2373 2306 2482 9669 2442 1284 9890 2268'.split())
# Explicit public under-subscription; the actual transfer is PUBLIC -> PRIVATE.
reverse=set('2418 9857 2152 9863 2602 3931 6963 2402 1405 9930 2416 9686 1973 2520'.split())
decisions=[]
for d in rows:
 c=d['code'];ev=None;outcome=None;basis=None
 for p in d['pages']:
  t=p['text'];m=re.search(r'(?:no\s+re.?allocat\w*.{0,420}?(?:has\s+(?:been\s+applied|taken\s+place))|(?:re.?allocation|claw.?back).{0,500}?(?:has|have)\s+not\s+(?:been\s+(?:applied|effected)|taken\s+place)|no\s+claw.?back\s+mechanism\s+was\s+effected|has\s+not\s+exercised\s+the\s+reallocation)',t,re.I)
  if m:
   outcome='NO';basis='Explicit completed non-trigger / no reallocation statement';ev={'page':p['page'],'snippet':t[max(0,m.start()-350):m.end()+450]};break
 if c in yes or c in reverse:
  assert outcome is None,(c,'Contradictory negative needs review')
  p=next(p for p in d['pages'] if re.search(r'claw.?back|reallocation|re-allocation',p['text'],re.I));t=p['text'];m=re.search(r'claw.?back|reallocation|re-allocation',t,re.I)
  ev={'page':p['page'],'snippet':t[max(0,m.start()-800):m.end()+1600]}
  outcome='YES' if c in yes else 'NO'
  basis='Filed public-demand trigger and implemented public-tranche increase' if c in yes else 'Public tranche undersubscribed; transfer to international tranche, not a public clawback'
 if c=='2161':
  outcome='NA';basis='Public offer only; no international tranche to claw back';ev={'page':1,'snippet':d['pages'][0]['text']}
 if outcome:
  decisions.append({'code':c,'clawback':outcome,'basis':basis,'evidence':dict(ev,url=d['url'],sha256=d['sha256'])})
(P/'remaining_outcome_decisions.json').write_text(json.dumps({'decisions':decisions,'held':[d['code'] for d in rows if d['code'] not in {r['code'] for r in decisions}]},ensure_ascii=False,indent=2)+'\n')
print('Accepted',len(decisions),'held',[d['code'] for d in rows if d['code'] not in {r['code'] for r in decisions}])
