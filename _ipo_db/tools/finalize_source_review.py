"""Record final allocation checks; never fill missing values from assumptions."""
import json,re
from pathlib import Path
R=Path(__file__).resolve().parent.parent;P=R/'data/demand_review_20261109'
load=lambda p:json.loads(p.read_text())
write=lambda p,d:p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
review=load(R/'data/batches/allocation_source_review.json');by={d['code']:d for d in review['deals']};accepted=[]
for d in load(P/'existing_outcome_prose.json'):
 hits=[]
 for p in d['pages']:
  m=re.search(r'Claw\s*[-–]?\s*back\s+triggered\s+(Yes|No|N\s*/\s*A)\b',p['text'],re.I)
  if m:hits.append((p,m,m[1].upper().replace(' ','').replace('N/A','NA')))
 if d['code']=='6127':
  p=next(p for p in d['pages'] if '11,697,700' in p['text'] and 'clawback' in p['text'].lower());m=re.search('clawback',p['text'],re.I);hits=[(p,m,'YES')]
 assert hits and len({h[2] for h in hits})==1,(d['code'],len(hits))
 p,m,outcome=hits[0];e={'url':d['url'],'sha256':d['sha256'],'page':p['page'],'snippet':p['text'][max(0,m.start()-200):m.end()+1100],'basis':'Explicit filed clawback outcome' if d['code']!='6127' else 'Filed alternative clawback implemented; 11,697,700 public shares after 88x demand'}
 row=by.setdefault(d['code'],{'code':d['code'],'evidence':e});row.update(clawback=outcome,outcome_evidence=e);accepted.append({'code':d['code'],'clawback':outcome,'evidence':e})
review['deals']=list(by.values());write(R/'data/batches/allocation_source_review.json',review);write(P/'existing_outcome_decisions.json',{'accepted':accepted,'held':[]});print('Fresh existing outcomes accepted',len(accepted))
