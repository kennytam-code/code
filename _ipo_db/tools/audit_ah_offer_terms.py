"""Compare A/H H-offer terms with explicit final-price allocation passages."""
import json,re,sys
from pathlib import Path
R=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(R/'ipo_lib'));P=R/'data/demand_review_20261109'
from market_universe import load,histories
D={d['code']:d for d in load(R)}
S={d['code']:d for f in ['remaining_outcome_prose.json','existing_outcome_prose.json','retail_float_prose.json'] for d in json.loads((P/f).read_text())}
patterns=[r'Final\s+Offer\s+Price\s*[:：]?\s*(?:is\s+|of\s+)?HK\$\s*([\d,]+(?:\.\d+)?)',r'(?:final\s+)?Offer\s+Price\s+(?:has\s+been\s+determined\s+at|has\s+been\s+set\s+at|is)\s+HK\$\s*([\d,]+(?:\.\d+)?)']
out=[]
for r in histories(R)['pairs']:
 c=r['code'];d=D[c];e=[];src=S.get(c,{})
 for p in src.get('pages',[]):
  for pat in patterns:
   for m in re.finditer(pat,p['text'],re.I):e.append({'price':float(m[1].replace(',','')),'page':p['page'],'snippet':p['text'][max(0,m.start()-40):m.end()+150]})
 matches=[h for h in e if d.get('final_price') is not None and abs(h['price']-d['final_price'])<1e-8]
 out.append({'code':c,'offer_hkd':d.get('final_price'),'matched':bool(matches),'evidence':dict(matches[0],url=src.get('url'),sha256=src.get('sha256')) if matches else e[:3]})
(P/'ah_offer_term_checks.json').write_text(json.dumps(out,indent=2)+'\n');print('Source matched',sum(x['matched'] for x in out),'remaining',[(x['code'],x['offer_hkd'],x['evidence']) for x in out if not x['matched']])
