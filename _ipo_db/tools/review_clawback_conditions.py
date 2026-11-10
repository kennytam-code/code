"""Read filed conditions for actual discretionary/shortfall reallocations."""
import gc,hashlib,io,json,re,urllib.request
from pathlib import Path
from pypdf import PdfReader
R=Path(__file__).resolve().parent.parent;P=R/'data/demand_review_20261109'
D={d['code']:d for d in json.loads((R/'data/deals.json').read_text())['deals']}
M={d['code']:d for d in json.loads((R/'data/batches/hkex_prospectus_links.json').read_text())['deals']}
O=P/'clawback_conditions.json';out=json.loads(O.read_text()) if O.exists() else [];known={d['code'] for d in out if d.get('evidence')};out=[d for d in out if d['code'] in known]
for c in '1440 2187 6680 2450 2439 2509 2497 2505 2443 2550 2881 1334 2585 2613 2121'.split():
 if c in known:continue
 part=next((p for p in M.get(c,{}).get('parts',[]) if p['label'].lower().startswith('structure')),None)
 url=part['url'] if part else D[c]['prospectus_link'];d={'code':c,'url':url,'evidence':[]}
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as f:raw=f.read(20*1024*1024)
  d['sha256']=hashlib.sha256(raw).hexdigest();pdf=PdfReader(io.BytesIO(raw));total=len(pdf.pages)
  indexes=range(total) if part else range(int(total*.45),int(total*.87))
  for i in indexes:
   t=re.sub(r'\s+',' ',pdf.pages[i].extract_text() or '')
   if ('STRUCTURE' in t.upper() or part) and re.search(r'(?:not.{0,15}fully subscribed|undersubscri|under-subscri|15\s+times)',t,re.I):
    d['evidence'].append({'page':i+1,'text':t})
  del pdf,raw;gc.collect();print(c,len(d['evidence']),flush=True)
 except Exception as e:d['error']=str(e);print(c,str(e),flush=True)
 out.append(d);O.write_text(json.dumps(out,ensure_ascii=False,indent=1)+'\n')
