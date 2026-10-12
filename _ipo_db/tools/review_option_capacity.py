"""Maximum option capacity is separate from actual allocation/exercise."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;cache=Path('/private/tmp/hkipo_desk_upgrade_20261012/filings')
cs=json.loads((ROOT/'out/desk_filing_candidates.json').read_text());full={r['code'] for r in cs['shoes'] if r['status'].lower()=='full'};found={}
for p in sorted(cache.glob('*.pages.json')):
 doc=json.loads(p.read_text());code=doc['code'];kind=doc['type']
 for pg in doc['pages']:
  t=re.sub(r'\s+',' ',pg['text'])
  # Explicit maximum grant: require/allot/issue up to additional Shares.
  for m in re.finditer(r'up to\s+(?:an aggregate of\s+)?[\d,]+\b.{0,300}?\b(?:Shares|Units)',t,re.I):
   before=t[max(0,m.start()-1500):m.start()];after=t[m.end():m.end()+450]
   if not re.search('over.allotment option',before,re.I) or not re.search(r'granted|right|require|exercisable|entitled',before[-1000:],re.I):continue
   z=re.search(r'(?:representing|equivalent to)\s*(?:in aggregate\s*)?(?:(?:approximately|not more than|no more than|up to|a maximum of)\s*)?(\d+(?:\.\d+)?)%\s*of\s*(.{0,170})',t[m.start():m.end()]+after,re.I)
   if z and re.search('Offer Shares|Global Offering|initial.*Offer',z[2],re.I) and not re.search('issued share capital',z[2],re.I) and 0<float(z[1])<=15.1:
    found.setdefault(code,[]).append(dict(value=float(z[1]),url=doc['url'],page=pg['page'],sha256=doc['sha256'],basis='Express maximum option grant as % of base offer',snippet=t[max(0,m.start()-100):m.end()+450]))
  # Exercised in full; its expressly stated % of the original offer is capacity.
  if kind=='stab' and code in full:
   for m in re.finditer(r'(?:has been|was|have been|were)\s+fully\s+exercised',t,re.I):
    tail=t[m.end():m.end()+800]
    z=re.search(r'representing\s+(?:in aggregate\s*)?(?:(?:approximately|not more than|up to|a maximum of)\s*)?(\d+(?:\.\d+)?)%\s*of\s*(.{0,180})',tail,re.I)
    if z and re.search('Offer Shares|initial.*Offer|Global Offering',z[2],re.I) and not re.search('issued share capital',z[2],re.I) and 0<float(z[1])<=15.1:
     found.setdefault(code,[]).append(dict(value=float(z[1]),url=doc['url'],page=pg['page'],sha256=doc['sha256'],basis='Option fully exercised; stated % of original offer',snippet=tail[:600]))
accepted={c:rs[0] for c,rs in found.items() if max(r['value'] for r in rs)-min(r['value'] for r in rs)<.051}
# Targeted reading of grammatical variants and the explicit no-option clause.
# Page numbers are PDF pages, not printed page labels.
manual=[('2191','2021050500053',49,5,'26,000,000 Units'),('2440','2022113000131',432,15,'5,400,000 Shares'),('1334','2024062800081',35,15,'18,750,000'),('3288','2025061100017',37,15,'41,854,700'),('2651','2025063000019',403,15,'1,629,200 H Shares'),('9607','2026092100029',53,0,'we will not grant any over-allotment option')]
for code,filing,page,value,needle in manual:
 matches=list(cache.glob(f'prosp_{code}_'+(filing+'*' if filing else '*')+'.pages.json'))
 if not matches:raise ValueError(f'Missing retained prospectus for {code}')
 d=json.loads(matches[0].read_text());pg=next(p for p in d['pages'] if p['page']==page);t=re.sub(r'\s+',' ',pg['text']);pos=t.lower().find(needle.lower())
 if pos<0:raise ValueError(f'Primary reading not found for {code} on PDF page {page}')
 accepted[code]=dict(value=value,url=d['url'],page=page,sha256=d['sha256'],basis='Explicit no-option clause' if value==0 else 'Manually reviewed maximum option grant as % of base offer',snippet=t[max(0,pos-700):pos+650])
(ROOT/'out/option_capacity_review.json').write_text(json.dumps(accepted,indent=1));print('Explicit option capacity readings',len(accepted),'ambiguous',len(found)-len(accepted));print('Non-15',[ (c,r['value']) for c,r in accepted.items() if r['value']!=15]);print('New deals',[(c,accepted.get(c)) for c in ['6731','6802','9856','9615']])
