"""Field-level numeric review ledger. Unconfirmed sources never become verified
merely because a value is plausible or a workbook formula calculates.
"""
import argparse,csv,json,math,re
from collections import Counter
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
RETURN_FIELDS={'first_day_return_pct','since_ipo_pct','first_close','last_close','day1_open_pop_pct','day1_open_close_pct','traded_sessions_available'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path);a=p.parse_args()
 doc=json.loads((ROOT/'data/deals.json').read_text());deals=doc['deals'];ledger=[];fail=[];warnings=[]
 def check(d,f,expected,tol=.051):
  actual=d.get(f)
  if isinstance(actual,(int,float)) and expected is not None and abs(actual-expected)>tol:
   fail.append({'code':d['code'],'field':f,'actual':actual,'expected':expected})
 for d in deals:
  pv=d.get('_prov',{});fp=d.get('final_price');mc=d.get('mktcap_ipo_hkdm');ni=d.get('ni_latest');rev=d.get('rev_latest');size=d.get('deal_size_hkdm');cs=d.get('cornerstone_pct');sh=d.get('offer_shares')
  if mc and ni and ni>0:check(d,'pe_ipo',mc/ni)
  elif d.get('pe_ipo') is not None and not pv.get('pe_ipo',{}).get('src','').startswith('bloomberg:'):fail.append({'code':d['code'],'field':'pe_ipo','issue':'Positive earnings denominator absent'})
  if mc and rev and rev>0:check(d,'ps_ipo',mc/rev)
  elif rev==0 and d.get('ps_ipo') is not None:fail.append({'code':d['code'],'field':'ps_ipo','issue':'Zero revenue denominator'})
  if d.get('price_range_hi'):check(d,'pct_of_cap',100*fp/d['price_range_hi'])
  if size is not None and cs is not None:
   check(d,'eff_free_float_hkdm',size*(1-cs/100),.011)
   if mc:check(d,'eff_free_float_pct',100*size*(1-cs/100)/mc,.011)
   if sh:check(d,'eff_free_float_shares',sh*(1-cs/100),1)
  if sh and d.get('day1_volume'):check(d,'day1_vol_x_offer',d['day1_volume']/sh,.011)
  if d.get('grey_close'):
   check(d,'grey_pct',100*(d['grey_close']/fp-1))
   check(d,'grey_to_day1_pct',100*(d['first_close']/d['grey_close']-1))
  for horizon in ['day1','since','1w','1m','3m']:
   f='first_day_return_pct' if horizon=='day1' else 'since_ipo_pct' if horizon=='since' else f'ret_{horizon}_pct'
   b=d.get(f'bench_{horizon}_pct')
   if b is not None and d.get(f) is not None:check(d,f'alpha_{horizon}_pct',d[f]-b,.021)
  for f,v in d.items():
   if not isinstance(v,(int,float)) or isinstance(v,bool):continue
   source=pv.get(f,{});ev=source.get('evidence') or {};status='Retained source; not independently re-confirmed';basis=''
   if not math.isfinite(v):fail.append({'code':d['code'],'field':f,'issue':'Non-finite number'})
   if f in ['cornerstone_pct','one_lot_hit_pct','public_alloc_pct','public_pct_initial','eff_free_float_pct'] and not 0<=v<=100:fail.append({'code':d['code'],'field':f,'issue':'Percentage outside 0–100'})
   if f.endswith('_shares') or f in ['offer_shares','shares_outstanding','intl_placees','lot_size','day1_volume']:
    if v<0 or v!=int(v):fail.append({'code':d['code'],'field':f,'issue':'Invalid share / count value'})
   if f in ['oversub_public_mult','oversub_intl_mult','rev_latest'] and v<0:fail.append({'code':d['code'],'field':f,'issue':'Negative subscription / revenue'})
   if ev:
    status='Reviewed primary filing';basis=ev.get('basis_note',ev.get('basis',ev.get('method','')))
    if ev.get('value') is not None:check(d,f,ev['value'],.00001)
   elif source.get('src')=='hkexnews:desk primary filing review':
    status='Reviewed primary filing';basis=d.get('mktcap_basis','') if f in ['shares_outstanding','shares_issued_on_listing','treasury_shares_at_listing','depositary_ratio'] else 'Final over-allotment option exercise, separate from stabilising market purchases'
    source={'src':d.get('mktcap_source') if f in ['shares_outstanding','shares_issued_on_listing','treasury_shares_at_listing'] else d.get('depositary_ratio_source') if f=='depositary_ratio' else d.get('stabilization_link')}
   elif source.get('src','').startswith('derived:'):
    status='Recalculated; input source confidence retained';basis=source['src']
   if f in RETURN_FIELDS or re.match(r'(?:ret_|aftermkt_|bench_|alpha_).*_pct$',f):
    status='Price / benchmark audit reconciled';basis='See audit_prices: exact dates, raw closes, corporate actions and benchmark windows'
   if f.endswith('_financial_year'):
    parent=f.removesuffix('_financial_year');ev=pv.get(parent,{}).get('evidence',{});status='Reviewed primary filing metadata' if ev else status
   ledger.append({'code':d['code'],'company':d['name'],'field':f,'value':v,'review_status':status,'source':ev.get('url',source.get('src','')),'page':ev.get('page',''),'basis':basis,'financial_year':ev.get('financial_year',''),'currency':ev.get('currency',''),'native_unit':ev.get('unit','')})
   if f in ['rev_latest','ni_latest'] and not ev:
    warnings.append({'code':d['code'],'field':f,'value':v,'issue':'Retained researched figure; fresh annual filing row is missing or ambiguous','source':source.get('src','')})
 changes=[]
 if a.baseline:
  old={d['code']:d for d in json.loads(a.baseline.read_text())['deals']}
  for row in ledger:
   prev=old.get(row['code'],{}).get(row['field'])
   if prev is not None and isinstance(prev,(int,float)) and abs(prev-row['value'])>max(.15,abs(row['value'])*.001):changes.append(dict(row,previous=prev))
 output=ROOT/'out';output.mkdir(exist_ok=True)
 with (output/'database_numeric_audit.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(ledger[0]));w.writeheader();w.writerows(ledger)
 changes_path=output/'database_numeric_changes.csv'
 if a.baseline or not changes_path.exists():
  with changes_path.open('w',newline='',encoding='utf-8-sig') as f:
   w=csv.DictWriter(f,fieldnames=[*list(ledger[0]),'previous']);w.writeheader();w.writerows(changes)
 else:
  with changes_path.open(encoding='utf-8-sig') as f:changes=list(csv.DictReader(f))
 subs=json.loads((ROOT/'data/batches/subscription_review.json').read_text())['deals'];corners=json.loads((ROOT/'data/batches/cornerstone_review.json').read_text())['deals'];locks=json.loads((ROOT/'data/batches/lockup_events.json').read_text())
 with (output/'cornerstone_name_review.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=['code','investor_group','review_status','page','source']);w.writeheader()
  for r in corners:
   for n in r['name_checks']:w.writerow({'code':r['code'],'investor_group':n['name'],'review_status':n['status'],'page':n.get('page',''),'source':n.get('url','')})
 accepted=json.loads((ROOT/'data/batches/latest_listed_review_20261015.json').read_text())
 for row in accepted['deals']:
  if row['code'] not in {r['code'] for r in subs}:subs.append(row)
 counts=Counter(x['review_status'] for x in ledger)
 snapshot=max(d.get('price_asof','') for d in deals)
 summary={'reviewed_at':date.today().isoformat(),'snapshot_asof':snapshot,'stocks':len(deals),'numeric_values':len(ledger),'numeric_fields':len({x['field'] for x in ledger}),'status_counts':dict(counts),'errors':fail,'unconfirmed_financials':warnings,'material_changes':len(changes),'subscriptions':{f:sum(f in r for r in subs) for f in ['oversub_public_mult','oversub_intl_mult']},'cornerstone':{'percentage_checks':sum('cornerstone_pct' in r for r in corners),'unresolved_name_aliases':sum('needs manual' in c['status'] for r in corners for c in r['name_checks'])},'lockups':{'rows':len(locks['events']),'dated':sum(bool(e['last_day_locked']) for e in locks['events'])}}
 visible=[e for e in locks['events'] if e['category']=='Cornerstone' and e['date_basis']!='No cornerstone tranche']
 summary['lockups'].update(visible_rows=len(visible),visible_stocks=len({e['code'] for e in visible}),unconfirmed_visible_expiries=sum(not e['last_day_locked'] for e in visible))
 (output/'database_numeric_audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 md=f'''# Database numeric review — {summary['reviewed_at']}

Reviewed all {len(deals)} listed stocks and {len(ledger):,} scalar numeric entries across {summary['numeric_fields']} fields. Latest individual quote date: {snapshot}; older histories retain their own dates. This is a source-confidence ledger, not a blanket certification.

Public subscription: {summary['subscriptions']['oversub_public_mult']}/{len(deals)} reviewed readings. Institutional subscription: {summary['subscriptions']['oversub_intl_mult']}/{len(deals)}; JBM Healthcare was public-offer-only, UJU's placing was under-subscribed without a numeric multiple, and Prudential's filing did not establish a numeric book multiple. These display N/A or Not disclosed rather than invented values.

Annual financials use the latest full fiscal year disclosed in the IPO filing. Owner-attributable earnings take priority for P/E; a consolidated-profit proxy is labelled. Native annual units and years survive in cell comments and the CSV. Legacy HKD conversions use fixed approximations (RMB×1.10; USD×7.80); newly reviewed rows retain their explicit prospectus conversion and source. They are not current spot conversions. Tian Tu retains its documented total-income proxy.

{len(warnings)} existing revenue/profit cells still need manual primary-row confirmation: these are listed in the JSON and retain their researched source. Investor group aliases also remain labelled as unresolved where exact legal names do not match filing text. A printed cornerstone total cannot establish every investor alias. The Excel and HTML use the same canonical names and percentages.

Base offer size excludes over-allocation; where the filing's gross proceeds include it, the printed amount and basis are retained separately. P/E and P/S are recalculated after financial corrections; losses and zero revenue do not produce numeric multiples.

The internal lock-up evidence retains {len(locks['events'])} group/date rows, with {summary['lockups']['dated']} filed or explicitly derived dates. HTML shows {len(visible)} cornerstone events for {summary['lockups']['visible_stocks']} companies, including IPO dates; Excel has no Lock-up sheets. Unrelated holder restrictions and no-cornerstone placeholders are excluded. Company cornerstones is the full company roster; a particular expiry can apply to a subset, established by the linked event filing. There are {summary['lockups']['unconfirmed_visible_expiries']} events with no established expiry: they keep blank dates, returns and charts. Returns use exactly 30 HK trading sessions before and after the last session on or before the last locked day. Selected averages use only selected stocks, giving each stock one weight; multiple selected expiries for a stock are averaged first. Missing observations and future endpoints stay blank.

Bloomberg formulas are linted and their surrounding arithmetic is evaluated with simulated quotes. Execution by a Bloomberg terminal/add-in remains a desk check. Sources retain individual observation dates; the newest database quote is {snapshot}. An incremental new listing does not refresh every historical series.

## Numeric review status

'''+ '\n'.join(f'- {k}: {v:,}' for k,v in counts.items())+f'\n\nInternal numeric failures: {len(fail)}. Material numeric changes versus the prior delivery: {len(changes)}. The separate CSV lists each value, previous value, source and basis. Existing price, formula, identity, scoring and visual gates must also pass before delivery.\n'
 (output/'database_numeric_audit.md').write_text(md)
 print(json.dumps({k:summary[k] for k in ['stocks','numeric_values','numeric_fields','status_counts','material_changes']},indent=2));print('Internal failures',len(fail),'unconfirmed annual figures',len(warnings))
 for e in fail[:20]:print('FAIL',e)
 return bool(fail)
if __name__=='__main__':raise SystemExit(main())
