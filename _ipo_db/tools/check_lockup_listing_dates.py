"""Confirm the listing-date input for inclusive-term expiry calculations."""
import json,hashlib,sys
from pathlib import Path
import requests,pymupdf as fitz
from bs4 import BeautifulSoup
from urllib.parse import urljoin
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from review_lockups import DATE,iso
OUT=ROOT/'out/lockup_review_20261017';A=json.loads((OUT/'date_audit.json').read_text())
D={d['code']:d for d in json.loads((ROOT/'data/deals.json').read_text())['deals']}
session=requests.Session();session.headers['User-Agent']='Mozilla/5.0';results=[]
def dates(text):
 result=[]
 for m in DATE.finditer(text):
  try:result.append(iso(m))
  except ValueError:pass
 return result
for n,r in enumerate(A['rows']):
 if not r['status'].startswith('verified'):continue
 s=json.loads((ROOT/r['source_file']).read_text());text='\n'.join(s['pages'].get(str(i),'') for i in [1,2,3]);url=r['url'];sha=s['sha256']
 if r['ipo_date'] not in dates(text) or 'inclusive' in r['status']:
  url=D[r['code']].get('allotment_link');target=OUT/('listing_'+r['code']+'.json')
  if target.exists() and json.loads(target.read_text()).get('ok'):results.append(json.loads(target.read_text()));continue
  try:
   response=session.get(url,timeout=(10,30));response.raise_for_status()
   if not response.content.startswith(b'%PDF'):
    links=BeautifulSoup(response.content,'html.parser').find_all('a',href=True)
    summary=next(a for a in links if a['href'].lower().endswith('.pdf') and 'summary' in a.get_text().lower())
    url=urljoin(url,summary['href']);response=session.get(url,timeout=(10,30));response.raise_for_status()
   assert response.content.startswith(b'%PDF'),'Expected official summary PDF'
   sha=hashlib.sha256(response.content).hexdigest()
   with fitz.open(stream=response.content,filetype='pdf') as doc:text='\n'.join(p.get_text(sort=False) for p in doc)
  except Exception as ex:
   result={'code':r['code'],'ok':False,'url':url,'error':str(ex)};results.append(result);target.write_text(json.dumps(result));continue
  matches=[m for m in DATE.finditer(text) if r['ipo_date'] in dates(m.group())]
  result={'code':r['code'],'ipo_date':r['ipo_date'],'ok':bool(matches),'url':url,'sha256':sha,'contexts':[text[max(0,m.start()-250):m.end()+120] for m in matches]}
  target.write_text(json.dumps(result,ensure_ascii=False,indent=1))
 else:result={'code':r['code'],'ipo_date':r['ipo_date'],'ok':True,'url':url,'sha256':sha,'basis':'Date present on first three pages of allotment result'}
 results.append(result)
 if len(results)%20==0:print('Listing date checks',len(results),flush=True)
(OUT/'listing_date_audit.json').write_text(json.dumps(results,ensure_ascii=False,indent=1));print('Listing dates',len(results),'unmatched',[(r['code'],r.get('error')) for r in results if not r['ok']],flush=True)
