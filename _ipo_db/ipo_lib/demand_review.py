"""Keep filed clawback outcomes separate from the allocation mechanism."""
import json

def apply_records(rows,root):
 path=root/'data/batches/allocation_source_review.json'
 reviewed={r['code']:r for r in json.loads(path.read_text()).get('deals',[])} if path.exists() else {}
 for d in rows:
  pv=d.setdefault('_prov',{});c=d['code'];review=reviewed.get(c,{})
  # A final allocation percentage cannot establish the mechanism or trigger.
  if str(pv.get('clawback',{}).get('src','')).startswith('derived:final public split'):
   d.pop('clawback',None);pv.pop('clawback',None)
  if str(pv.get('alloc_mechanism',{}).get('src','')).startswith('derived:'):
   d.pop('alloc_mechanism',None);pv.pop('alloc_mechanism',None)
  mechanism=review.get('allocation_mechanism')
  if mechanism:
   d['allocation_mechanism']=mechanism;d['alloc_mechanism']=mechanism
   pv['alloc_mechanism']={'src':'hkexnews:explicit allocation terms','status':'single','evidence':review['evidence']}
  else:
   d['allocation_mechanism']='Unconfirmed';d['alloc_mechanism']='Unconfirmed'
  raw=str(d.get('clawback') or '').upper().replace('N/A','NA')
  if 'clawback' in review:
   raw=review['clawback'];d['clawback']=raw
   pv['clawback']={'src':'hkexnews:allocation review','status':'single','evidence':review.get('outcome_evidence',review['evidence'])}
  if 'clawback_reported' in review:d['clawback_reported']=review['clawback_reported']
  if mechanism=='Mechanism B':
   # The absence of a mechanism is not an untriggered mechanism.
   if 'clawback_reported' not in d:d['clawback_reported']=raw or None
   d['clawback']='NA';raw='NA'
   pv['clawback']={'src':'hkexnews:Mechanism B has no mandatory clawback','status':'single','evidence':review['evidence']}
  outcome={'YES':'Yes','NO':'No','NA':'N/A'}.get(raw,'')
  d['clawback_status']={'YES':'Triggered','NO':'Not triggered','NA':'Not applicable'}.get(raw,'Unconfirmed')
  if raw=='NA' and mechanism is None:d['clawback_status']='Filed N/A'
  if mechanism=='Mechanism B':display='Mechanism B / N/A'
  elif mechanism in ['Mechanism A','18C']:
   display=('A' if mechanism=='Mechanism A' else '18C')+(' / '+outcome if outcome else '')
  elif outcome=='N/A':display='N/A'
  else:display=outcome
  d['clawback_display']=display
 return rows
