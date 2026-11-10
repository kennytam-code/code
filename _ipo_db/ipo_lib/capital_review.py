"""Apply reviewed issued-capital facts and recalculate only their dependants."""
import json
def apply_records(rows,root):
 path=root/'data/batches/capital_source_review.json'
 reviewed={r['code']:r for r in json.loads(path.read_text())['deals']} if path.exists() else {}
 for d in rows:
  r=reviewed.get(d['code'])
  if not r:continue
  pv=d.setdefault('_prov',{});shares=r['shares_outstanding'];ratio=d.get('depositary_ratio') or 1
  if not d.get('final_price') or shares<=0 or ratio<=0:raise ValueError('Invalid reviewed capital inputs: '+d['code'])
  cap=round(d['final_price']*shares/ratio/1e6,1)
  d['shares_outstanding']=shares;d['shares_issued_on_listing']=r.get('shares_issued_on_listing',shares)
  d.update(mktcap_ipo_hkdm=cap,mktcap_basis=r.get('basis','Filed issued capital, ex shoe × final offer price'),mktcap_source=r['evidence']['url'],mktcap_source_page=r['evidence']['page'])
  d.pop('mktcap_note',None)
  for f in ['shares_outstanding','shares_issued_on_listing','mktcap_ipo_hkdm']:
   pv[f]={'src':'hkexnews:issued-capital review','status':'single','evidence':r['evidence']}
  for field,denominator in [('pe_ipo','ni_latest'),('ps_ipo','rev_latest')]:
   den=d.get(denominator)
   note='pe_note' if field=='pe_ipo' else 'ps_note'
   if den is not None and den>0 and (cap/den<=300 or d.get(field) is not None or pv.get(denominator,{}).get('evidence',{}).get('financial_year')):
    d[field]=round(cap/den,1);pv[field]={'src':'derived:reviewed market cap / '+denominator,'status':'single'}
    d.pop(note,None)
    if cap/den>300:d[note]='Extreme trailing multiple on retained financial denominator; not comparable with normal positive earnings/revenue.'
    if field=='pe_ipo' and d.get('ni_latest_basis')=='Consolidated net income':d[note]=(d.get(note,'')+' ' if note in d else '')+'Uses consolidated net income; owner-attributable earnings not independently confirmed.'
   elif den is not None:
    d.pop(field,None);pv.pop(field,None)
  size=d.get('deal_size_hkdm');cs=d.get('cornerstone_pct')
  if cs is None and not d.get('cornerstone_investors'):cs=0
  if size is not None and cs is not None:
   d['eff_free_float_pct']=round(100*size*(1-cs/100)/cap,2)
   pv['eff_free_float_pct']={'src':'derived:offer less cornerstone / reviewed market cap','status':'single'}
   d.pop('eff_ff_note',None)
 return rows
