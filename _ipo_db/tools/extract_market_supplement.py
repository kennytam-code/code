"""HKEX's 2019/2020 listing roster, kept outside the core IPO database."""
import json,re
from pathlib import Path
from collections import Counter
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent.parent
out=[]
for year,pages in [(2019,range(51,60)),(2020,range(58,66))]:
 reader=PdfReader(ROOT/f'data/desk_review_20261012/FB_{year}.pdf')
 for i in pages:
  text=reader.pages[i].extract_text()
  chunks=re.split(r'(?m)^\s*(0\d{4})\s+',text)
  for j in range(1,len(chunks),2):
   code=chunks[j];block=chunks[j+1];dt=re.search(r'20\d\d/\d\d/\d\d',block)
   if not dt:continue
   ipo=dt[0].replace('/','-')
   if ipo<'2019-10-12' or ipo>='2021-01-01' or block.lstrip().startswith('#') or 'Transfer of Listing' in block:continue
   name=re.split(r'Offer for (?:subscription|placing|sale)|Introduction',block,1)[0].strip()
   name=re.sub(r'\s+',' ',name)
   industry=re.search(r'(?:Information Technology|Healthcare|Health Care|Consumer Goods|Consumer Services|Consumer Discretionary|Consumer Staples|Financials|Industrials|Materials|Energy|Utilities|Telecommunications|Properties & Construction)\s*[–—-]\s*([^\n]+)',block)
   value=re.search(r'Offer for (?:subscription|placing|sale)\s+[\d,]+\s*\([a-z]\)\s+([\d,.]+)',block)
   out.append({'code':str(int(code)).zfill(4),'name':name,'ipo_date':ipo,'board':'Main','industry_hkex':industry[0] if industry else None,'final_price':float(value[1].replace(',','')) if value else None,'listing_method':'Introduction' if 'Introduction' in block else 'IPO','source':f'https://www.hkex.com.hk/-/media/HKEX-Market/Market-Data/Statistics/Consolidated-Reports/HKEX-Fact-Book/HKEX-Fact-Book-{year}/FB_{year}.pdf?la=en','source_page':i+1})
(ROOT/'data/market_supplement.json').write_text(json.dumps({'from':'2019-10-12','through':'2020-12-31','deals':out},ensure_ascii=False,indent=1))
print('Supplement',len(out),Counter(r['ipo_date'][:4] for r in out))
print('Industries',Counter(r['industry_hkex'] for r in out))
print('potential AH',[(d['code'],d['name']) for d in out if 'H Shares' in d['name'] or d['code'] in ['3347','9995']])
print('Canonical boards',Counter(r['board'] for r in json.loads((ROOT/'data/deals.json').read_text())['deals']))
