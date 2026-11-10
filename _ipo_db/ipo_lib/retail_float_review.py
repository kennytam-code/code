"""Restore source-reviewed final retail counts and dependent turnover ratios."""
import json

def apply_records(rows,root):
 p=root/'data/batches/retail_float_review.json'
 if not p.exists():return rows
 by={r['code']:r for r in json.loads(p.read_text())['deals']}
 for d in rows:
  if d['code'] not in by:continue
  r=by[d['code']];count=r['public_shares_final'];assert count>0
  d['public_shares_final']=count
  d.setdefault('_prov',{})['public_shares_final']={'src':'hkexnews:reviewed final public allocation','status':'single','evidence':r['evidence']}
  v=d.get('day1_volume')
  if isinstance(v,(int,float)) and v>=0:
   d['day1_vol_x_retail']=round(v/count,2)
   d['_prov']['day1_vol_x_retail']={'src':'derived:Day-1 traded units / filed final public units','status':'single'}
 return rows
