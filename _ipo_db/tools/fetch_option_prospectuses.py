import json,hashlib,time,concurrent.futures
from pathlib import Path
import requests,fitz
ROOT=Path(__file__).resolve().parent.parent;cache=Path('/private/tmp/hkipo_desk_upgrade_20261012/filings');review=json.loads((ROOT/'out/option_capacity_review.json').read_text());deals=json.loads((ROOT/'data/deals.json').read_text())['deals'];jobs=[d for d in deals if d.get('greenshoe_pct') not in [None,0,15] and d['code'] not in review]
def pull(d):
 url=d.get('prospectus_link');name='prosp_'+d['code']+'_'+url.rsplit('/',1)[-1]+'.pages.json';path=cache/name
 if path.exists() and json.loads(path.read_text()).get('extraction_scope')=='all_pages_narrative':return d['code'],'cached'
 for attempt in range(2):
  try:
   raw=requests.get(url,timeout=40).content
   with fitz.open(stream=raw,filetype='pdf') as pdf:
    pages=[{'page':i+1,'text':pdf[i].get_text(sort=False)} for i in range(len(pdf))]
   path.write_text(json.dumps(dict(code=d['code'],type='prosp',url=url,file=url.rsplit('/',1)[-1],sha256=hashlib.sha256(raw).hexdigest(),extraction_scope='all_pages_narrative',pages=pages)))
   return d['code'],'OK'
  except Exception as e:
   if attempt==1:return d['code'],str(e)
def main():
 issues=[]
 with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
  futures=[pool.submit(pull,d) for d in jobs]
  for i,future in enumerate(concurrent.futures.as_completed(futures),1):
   code,status=future.result()
   if status not in ['OK','cached']:issues.append([code,status])
   if i%20==0:print('Reviewed prospectus',i,'/',len(jobs),flush=True)
 (ROOT/'out/option_download_issues.json').write_text(json.dumps(issues));print('Completed',len(jobs),'prospectuses; failures',len(issues),flush=True)
if __name__=='__main__':main()
