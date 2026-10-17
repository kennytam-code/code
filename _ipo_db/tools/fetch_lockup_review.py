"""Sequential bounded re-read of primary HKEX lock-up source pages."""
import argparse,hashlib,json,re,time,gc
from pathlib import Path
from collections import defaultdict
import requests,fitz
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'out/lockup_review_20261017/sources';OUT.mkdir(parents=True,exist_ok=True)
p=argparse.ArgumentParser();p.add_argument('--limit',type=int);a=p.parse_args()
b=json.loads((ROOT/'data/batches/lockup_events.json').read_text());groups=defaultdict(list)
for i,e in enumerate(b['events']):
 if e['category']=='Cornerstone' and e.get('last_day_locked') and e['last_day_locked']<'2026-10-17':groups[e['url']].append((i,e))
urls=list(groups);urls=urls[:a.limit] if a.limit else urls
session=requests.Session();session.headers['User-Agent']='Mozilla/5.0'
results=[]
for n,url in enumerate(urls,1):
 key=hashlib.sha256(url.encode()).hexdigest()[:20];target=OUT/(key+'.json');pdf=OUT/'current.pdf'
 if target.exists():
  record=json.loads(target.read_text())
  if record.get('ok'):results.append({'url':url,'ok':True,'cached':True});continue
 try:
  with session.get(url,timeout=(15,45),stream=True) as r:
   r.raise_for_status()
   with pdf.open('wb') as f:
    for chunk in r.iter_content(262144):f.write(chunk)
  digest=hashlib.sha256(pdf.read_bytes()).hexdigest();size=pdf.stat().st_size
  with fitz.open(pdf) as doc:
   requested={0,1,2}
   for _,e in groups[url]:
    page=int(e.get('page') or 1)-1;requested.update(range(max(0,page-2),min(len(doc),page+3)))
   pages={str(i+1):doc[i].get_text(sort=True) for i in sorted(requested) if i<len(doc)}
   record={'ok':True,'url':url,'sha256':digest,'bytes':size,'page_count':len(doc),'pages':pages,'events':[{'index':i,'code':e['code'],'expiry':e['last_day_locked'],'source_page':e.get('page'),'previous_sha256':e.get('sha256')} for i,e in groups[url]],'checked_date':'2026-10-17'}
   # Keep one source image per basis as a first visual check; ambiguous pages
   # can be fetched again for a targeted table-layout inspection.
   if n in [1,2,3]:
    i=max(0,min(len(doc)-1,int(groups[url][0][1].get('page') or 1)-1));doc[i].get_pixmap(matrix=fitz.Matrix(1.4,1.4)).save(OUT/(key+'.png'))
  target.write_text(json.dumps(record,ensure_ascii=False,indent=1));results.append({'url':url,'ok':True,'bytes':size})
 except Exception as ex:
  record={'ok':False,'url':url,'error':str(ex),'checked_date':'2026-10-17'};target.write_text(json.dumps(record));results.append(record)
 finally:
  pdf.unlink(missing_ok=True);gc.collect()
 if n%10==0 or not record.get('ok'):print('HKEX files',n,'/',len(urls),'failed',sum(not x['ok'] for x in results),flush=True)
(OUT.parent/'fetch_summary.json').write_text(json.dumps(results,indent=2));print('Finished',len(results),'sources; failures',sum(not x['ok'] for x in results),flush=True)
