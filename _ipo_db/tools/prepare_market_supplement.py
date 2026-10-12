import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
p=ROOT/'data/market_supplement.json';doc=json.loads(p.read_text());snap={r['code']:r for r in json.loads((ROOT/'data/batches/ah_snapshot.json').read_text())['pairs']}
# Classify against the same desk taxonomy. The 2020 ICB software bucket also
# includes internet platforms; reviewed issuer overrides retain their economics.
overrides={
 '3759':('Healthcare','CXO / pharma services'),'3347':('Healthcare','CXO / pharma services'),'9969':('Healthcare','Biopharma commercial'),'9989':('Healthcare','Biopharma commercial'),'9995':('Healthcare','Biopharma commercial'),'6690':('Consumer','Retail / distribution'),
 '9988':('Technology','Internet & fintech'),'9999':('Technology','Internet & fintech'),'9618':('Technology','Internet & fintech'),'9898':('Technology','Internet & fintech'),'9698':('Technology','Software & AI'),'1415':('Technology','Hardware & electronics'),'9922':('Consumer','F&B chains / restaurants'),'9992':('Consumer','Retail / distribution'),'9961':('Healthcare','CXO / pharma services'),
 '9990':('Technology','Data centres & cloud'),'1957':('Technology','Data centres & cloud'),'1769':('Technology','Software & AI'),'2237':('Technology','Hardware & electronics'),'9923':('Technology','Internet & fintech'),
}
for d in doc['deals']:
 ind=d['industry_hkex'] or '';ind=re.split(r'\s{3,}',ind)[0].strip();d['industry_hkex']=ind
 if d['code'] in overrides:sector,sub=overrides[d['code']]
 elif ind.startswith('Healthcare'):sector,sub='Healthcare','Medical devices' if 'Equipment' in ind else 'Biopharma commercial'
 elif ind.startswith('Information Technology'):sector,sub='Technology','Software & AI'
 elif ind.startswith('Properties'):sector,sub='Real Estate','Developers' if 'Properties' in ind.split('–')[-1] else 'Construction / engineering';sector='Industrials' if sub=='Construction / engineering' else sector
 elif ind.startswith('Industrials'):sector,sub='Industrials','Logistics' if 'Transportation' in ind else 'Capital goods / machinery'
 elif ind.startswith('Financials'):sector,sub='Financials','Banks' if 'Banks' in ind else 'Brokers / asset management'
 elif ind.startswith(('Materials','Energy','Utilities')):sector,sub='Materials/Energy','Mining / metals' if 'Metals' in ind else 'Chemicals' if 'Materials' in ind else 'Oil & gas / utilities'
 elif 'Media & Entertainment' in ind:sector,sub='Media & telecom','Media / advertising'
 elif 'Support Services' in ind:sector,sub='Consumer','Consumer services / education'
 elif 'Food & Beverages' in ind:sector,sub='Consumer','Beverages / packaged food'
 elif 'Clothing' in ind:sector,sub='Consumer','Apparel / luxury'
 else:sector,sub='Consumer','Retail / distribution'
 d.update(sector=sector,subsector=sub)
 if d['code'] in snap:
  x=snap[d['code']];d.update(a_share_code=x['a_code'],name=x['name'])
 if d['listing_method']=='Introduction':d['final_price']=None
p.write_text(json.dumps(doc,ensure_ascii=False,indent=1))
print('Classified',len(doc['deals']),'A/H',sum(bool(d.get('a_share_code')) for d in doc['deals']))
