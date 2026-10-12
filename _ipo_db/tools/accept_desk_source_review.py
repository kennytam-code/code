import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
c=json.loads((ROOT/'out/desk_filing_candidates.json').read_text());prior=json.loads((ROOT/'data/batches/desk_source_review.json').read_text()) if (ROOT/'data/batches/desk_source_review.json').exists() else {'deals':[]};by={r['code']:{k:v for k,v in r.items() if k.startswith('greenshoe_pct') or k in ['code','greenshoe_capacity_unconfirmed']} for r in prior['deals']};ledger=[]
for r in c['market_caps']:
 if r['code']=='6228':
  ratio=json.loads((ROOT/'data/desk_review_20261012/hdr_ratio_source.json').read_text())
  by['6228']=dict(code='6228',shares_outstanding=r['shares_outstanding'],shares_issued_on_listing=r['issued'],depositary_ratio=ratio['ratio'],mktcap_basis='HKEX:underlying issued shares x HDR offer price / depositary ratio',mktcap_source=r['url'],depositary_ratio_source=ratio['url'],depositary_ratio_source_page=ratio['page']);ledger.append({**r,'depositary_ratio_evidence':ratio});continue
 if r['shares_outstanding']<1e6:continue
 by.setdefault(r['code'],dict(code=r['code'])).update(shares_outstanding=r['shares_outstanding'],shares_issued_on_listing=r['issued'],treasury_shares_at_listing=r['treasury'],mktcap_basis='HKEX:shares upon listing excluding identified treasury shares x H offer price',mktcap_source=r['url'],mktcap_source_page=r['page']);ledger.append(r)
for r in c['shoes']:
 z=by.setdefault(r['code'],dict(code=r['code']));z.update(greenshoe_exercised_final=r['status'],stabilization_link=r['url'])
 if r['shares'] is not None:z['greenshoe_shares_exercised']=r['shares']
 ledger.append(r)
(ROOT/'data/batches/desk_source_review.json').write_text(json.dumps(dict(batch='desk_source_review',reviewed_at='2026-10-12',deals=list(by.values())),ensure_ascii=False,indent=1))
(ROOT/'out/desk_source_evidence.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=1))
p=ROOT/'data/batches/lockup_events.json';doc=json.loads(p.read_text());accepted=0
for e in doc['events']:
 if e['category']!='Cornerstone' or e.get('last_day_locked') or e['date_basis']=='No cornerstone tranche':continue
 rec=[r for r in c['lockup_dates'] if r['code']==e['code']];unique={r['last_day_locked'] for r in rec}
 if len(unique)==1:
  e.update(rec[0]);accepted+=1
p.write_text(json.dumps(doc,ensure_ascii=True,indent=1));print('Accepted',len(by),'source-reviewed issuers; lock-up dates added',accepted)
p=ROOT/'ipo_lib/merge_batches.py';s=p.read_text();needle='    # pass 2: everything that depends on deal size';block='''    # Primary filed final share capital and final shoe quantities reviewed on 12 Oct.
    reviewed = load("desk_source_review.json")
    if reviewed:
        for row in reviewed["deals"]:
            code = row["code"]
            if code not in deals: continue
            for field, value in row.items():
                if field != "code" and value is not None:
                    put(code, field, value, "hkexnews:desk primary filing review", 100, status="xchecked")

'''
if block not in s:s=s.replace(needle,block+needle)
s=s.replace('x["greenshoe_pct"] = round(100 * x["overallot_shares"] / x["offer_shares"], 1)','x["over_allocation_pct"] = round(100 * x["overallot_shares"] / x["offer_shares"], 1)').replace('prov[c]["greenshoe_pct"] = {"src": "derived:over-allocated / offer shares",','prov[c]["over_allocation_pct"] = {"src": "derived:over-allocated / offer shares",')
p.write_text(s)
