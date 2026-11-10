import json,copy
from pathlib import Path
R=Path(__file__).resolve().parent.parent;P=R/'data/demand_review_20261109';load=lambda p:json.loads(p.read_text());write=lambda p,d:p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
D={d['code']:d for d in load(R/'data/deals.json')['deals']};rows=[]
for r in load(P/'ah_offer_fresh_quotes.json'):
 d=D[r['code']];a=r['a_rows'][0][1];fx=r['cnyhkd'];assert a>0 and fx>0
 rows.append({'code':r['code'],'a_close_cny':a,'a_close_date':r['a_date'],'cnyhkd':fx,'fx_date':r['fx_date'],'evidence':r})
write(R/'data/batches/ah_offer_reference_review.json',{'date':'2026-11-10','deals':rows})
for f in ['data/batches/ah_ipo.json','data/batches/ah_study.json']:
 obj=load(R/f);key='deals' if f.endswith('ah_ipo.json') else 'pairs';by={r['code']:r for r in rows}
 for d in obj[key]:
  if d['code'] not in by:continue
  r=by[d['code']];offer=D[d['code']]['final_price'];a=r['a_close_cny']*r['cnyhkd'];premium=(a/offer-1)*100
  if key=='deals':d.update(a_close_cny=r['a_close_cny'],a_close_hkd=a,a_close_date=r['a_close_date'],cnyhkd=r['cnyhkd'],ah_discount_ipo_pct=100*(offer/a-1))
  else:
   d.update(offer_reference_premium_pct=premium,offer_reference_a_date=r['a_close_date'],offer_reference_fx_date=r['fx_date'])
   if d.get('premium_day1_pct') is not None:d['offer_to_day1_change_pp']=d['premium_day1_pct']-premium
   cap=D[d['code']].get('mktcap_ipo_hkdm')
   if cap:
    d['company_cap_at_a_reference_hkdm']=cap/offer*a
    if d.get('deal_size_hkdm'):d['offer_size_to_a_reference_cap_pct']=100*d['deal_size_hkdm']/d['company_cap_at_a_reference_hkdm']
 write(R/f,obj)
rows=[]
for r in load(P/'day1_tape_recovery.json'):
 if 'raw_bar' not in r:continue
 c=r['code'];b=r['raw_bar'];o,cl,h,l,v=map(float,b[1:6]);assert 0<l<=min(o,cl)<=max(o,cl)<=h and v>0
 assert abs((cl/D[c]['final_price']-1)*100-D[c]['first_day_return_pct'])<.02,(c,'price basis mismatch')
 vals={'day1_open':o,'day1_close':cl,'day1_high':h,'day1_low':l,'day1_volume':v,'day1_range_pct':round((h-l)/o*100,2),'day1_turnover_hkdm':round(v*(o+cl+h+l)/4/1e6,2)}
 missing={k:v for k,v in vals.items() if D[c].get(k) is None}
 rows.append({'code':c,'values':missing,'evidence':r})
write(R/'data/batches/day1_source_recovery.json',{'date':'2026-11-10','deals':rows});print('IPO refs',len(by),'listing tapes',len(rows))
