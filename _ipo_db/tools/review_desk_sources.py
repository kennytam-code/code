"""Read primary filings for the desk upgrade; retain every evidence page privately."""
import json,re,hashlib,io
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests
import pymupdf
ROOT=Path(__file__).resolve().parent.parent
CACHE=ROOT.parent/'filings';CACHE.mkdir(exist_ok=True)
D=json.loads((ROOT/'data/deals.json').read_text())['deals'];DM={d['code']:d for d in D}
miss={e['code'] for e in json.loads((ROOT/'data/batches/lockup_events.json').read_text())['events'] if e['category']=='Cornerstone' and not e.get('last_day_locked') and e['date_basis']!='No cornerstone tranche'}
a=json.loads((ROOT/'data/batches/hkex_allotment_files.json').read_text())['manifest'];p=json.loads((ROOT/'data/batches/hkex_prospectus_links.json').read_text())['deals']
jobs=[dict(part,type='allot',code=r['code']) for r in a for part in r['parts']]
jobs += [dict(part,type='prosp',code=r['code']) for r in p if r['code'] in miss for part in r['parts']]
jobs += [{'code':d['code'],'type':'stab','file':'stab_'+d['code']+'_'+d['stabilization_link'].split('/')[-1], 'url':d['stabilization_link']} for d in D if d.get('stabilization_link') and d['stabilization_link'].endswith('.pdf')]
def run(job):
 path=CACHE/(job['file']+'.pages.json')
 if path.exists():return job['code']
 response=requests.get(job['url'],timeout=60);response.raise_for_status();raw=response.content
 if raw[:4]!=b'%PDF':raise ValueError('not PDF: '+job['url'])
 with pymupdf.open(stream=raw,filetype='pdf') as pdf:
  n=len(pdf) if job['type']=='prosp' else min(len(pdf),20)
  pages=[{'page':i+1,'text':pdf[i].get_text(sort=True)} for i in range(n)]
 path.write_text(json.dumps(dict(job,sha256=hashlib.sha256(raw).hexdigest(),pages=pages),ensure_ascii=False))
 return job['code']
errors=[]
with ThreadPoolExecutor(max_workers=6) as pool:
 tasks={pool.submit(run,j):j for j in jobs}
 for i,t in enumerate(as_completed(tasks),1):
  try:t.result()
  except Exception as ex:errors.append(dict(tasks[t],error=str(ex)))
  if i%50==0:print('Filing pages',i,'/',len(jobs),'errors',len(errors),flush=True)
(ROOT/'out/desk_source_download_issues.json').write_text(json.dumps(errors,indent=1))
print('Downloaded',len(jobs)-len(errors),'errors',len(errors),flush=True)
