"""Dated observed IPO legs and recovered listing-day tape, applied after merge."""
import json

def apply_records(rows,root):
 by={r['code']:r for r in rows}
 for name in ['ah_offer_reference_review','day1_source_recovery']:
  p=root/f'data/batches/{name}.json'
  if not p.exists():continue
  for r in json.loads(p.read_text())['deals']:
   d=by.get(r['code'])
   if d is None:continue
   if name=='ah_offer_reference_review':
    a=r['a_close_cny']*r['cnyhkd'];fp=d.get('final_price')
    if not fp:continue
    vals={k:r[k] for k in ['a_close_cny','a_close_date','cnyhkd']}
    vals.update(a_close_hkd=round(a,6),a_premium_ipo_pct=round(100*(a/fp-1),2),ah_discount_ipo_pct=round(100*(fp/a-1),2))
   else:vals=r['values']
   for k,v in vals.items():
    d[k]=v;d.setdefault('_prov',{})[k]={'src':'dated public quote:source review 2026-11-10','status':'single','evidence':r['evidence']}
   if name=='day1_source_recovery':
    v=d.get('day1_volume');sh=d.get('offer_shares');public=d.get('public_shares_final')
    if isinstance(v,(int,float)) and v>=0:
     if sh:d['day1_vol_x_offer']=round(v/sh,2)
     if public:d['day1_vol_x_retail']=round(v/public,2)
 return rows
