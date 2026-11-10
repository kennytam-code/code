"""Re-read final price evidence for the issued-capital review; no auto edits."""
import json,re,io,hashlib,gc,urllib.request
from pathlib import Path
from pypdf import PdfReader
R=Path(__file__).resolve().parent.parent
deals={r['code']:r for r in json.loads((R/'data/deals.json').read_text())['deals']}
targets=json.loads((R/'data/demand_review_20261109/capital_chapters.json').read_text())
out=[]
for x in targets:
 d=deals[x['code']];e=d.get('_prov',{}).get('final_price',{}).get('evidence',{});url=e.get('url')
 if not url:continue
 r={'code':d['code'],'url':url,'expected':d['final_price']}
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=15) as f:raw=f.read(12*1024*1024)
  p=PdfReader(io.BytesIO(raw));r['sha256']=hashlib.sha256(raw).hexdigest();r['evidence']=[];r['pages']=[]
  for i in range(min(5,len(p.pages))):
   t=re.sub(r'\s+',' ',p.pages[i].extract_text() or '');r['pages'].append({'page':i+1,'text':t})
   for m in re.finditer(r'(?:Final\s+)?Offer\s+Price\s*:?\s*HK\$\s*([\d,.]+)',t,re.I):
    r['evidence'].append({'price':float(m.group(1).replace(',','')),'page':i+1,'snippet':t[max(0,m.start()-70):m.end()+120]})
  del p,raw;gc.collect()
 except Exception as exc:r['error']=str(exc)
 out.append(r);print(r['code'],[(v['price'],v['page']) for v in r.get('evidence',[])],flush=True)
 (R/'data/demand_review_20261109/final_prices.json').write_text(json.dumps(out,ensure_ascii=False,indent=1)+'\n')
