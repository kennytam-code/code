import json,re,sys
from pathlib import Path
R=Path(__file__).resolve().parent.parent;P=R/'data/demand_review_20261109'
load=lambda p:json.loads(p.read_text());write=lambda p,d:p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
x=load(P/'retail_float_candidates.json');rows={d['code']:d for d in x['candidates']};S={d['code']:d for f in ['remaining_outcome_prose.json','existing_outcome_prose.json','retail_float_prose.json'] for d in load(P/f)}
manual={'2129':156250000,'1643':45000000,'2161':44686000,'1473':100000000,'1927':99000000,'6608':61912000,'2191':52000000,'2209':19770000,'2216':8935500,'2251':2226800,'9899':1600000,'2285':7191600,'2260':11420000,'2121':4474600,'2157':12688000,'6639':4653000,'2418':22900500,'9863':2146400,'6660':971600,'2422':25000000,'2367':2261200,'2291':2246000,'2145':1764900,'6955':1069600,'2458':3726000,'2459':17240000,'1405':575500,'2415':6679000,'2487':2128400,'9885':1581200,'9860':3320000,'2271':12668000,'2501':12500000,'1519':32655200,'2473':10312500,'2476':7852800,'6067':14952500,'6228':8966900,'1377':1202900}
for c,v in manual.items():
 r=S[c];needle=f'{v:,}';found=[]
 for p in r['pages']:
  # Preserve exact original text; compact only for matching broken PDF tokens.
  t=p['text'];compact=re.sub(r'\s+','',t).lower();pattern=re.compile('\\s*'.join(re.escape(ch) for ch in needle))
  for m in pattern.finditer(t):
   near=t[max(0,m.start()-240):m.end()+750]
   if (('final' in near.lower() and c not in ['2216','2285','2161']) or (p['page']==1 and c in ['2216','2285','2161'])):
    found.append({'page':p['page'],'snippet':near})
 assert found,c
 e=dict(found[0],url=r['url'],sha256=r['sha256'],basis='Explicit final public allocation in filed results')
 if c in ['2216','2285']:e['basis']='Initial public count unchanged: the same filed paragraph explicitly says reallocation not effected'
 if c=='2161':e['basis']='Entire offer is public only; subscribed offer count in final results'
 if c in ['2476','1377']:e['basis']='Final public-tranche shares excluding separately reserved overseas employee allocation'
 if c=='6228':e['basis']='Final public HDR count; same listed receipt unit as trading volume'
 rows[c]={'code':c,'public_shares_final':v,'evidence':e}
assert len(rows)==168
for r in rows.values():assert r['public_shares_final']>0 and r['evidence']['sha256']
write(R/'data/batches/retail_float_review.json',{'date':'2026-11-10','deals':list(rows.values()),'method':'Final public allocation denominator; separately reserved employee allocations excluded where explicitly split. Receipt/unit counts match listed trading unit. No initial-allocation percentage substitute.'});print('Accepted final public allocation counts',len(rows))
