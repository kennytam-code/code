import gc,hashlib,io,json,re,urllib.request
from pathlib import Path
from pypdf import PdfReader
import sys
R=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(R/'ipo_lib'));P=R/'data/demand_review_20261109'
from market_universe import load
D={r['code']:r for r in load(R)};M={r['code']:r for r in json.loads((R/'data/batches/hkex_allotment_files.json').read_text())['manifest']}
checks=json.loads((P/'ah_offer_term_checks.json').read_text());out=[]
for x in checks:
 if x['matched'] or x['code'] in ['2315','9969','9995','6690']:continue
 d=D[x['code']];e=d.get('_prov',{}).get('final_price',{}).get('evidence',{});url=e.get('url');parts=M.get(x['code'],{}).get('parts',[])
 if not url or '.pdf' not in url:
  part=next((p for p in parts if p['label']=='Summary'),None) or next((p for p in parts if p['label']=='Document'),None);url=part['url'] if part else d.get('allotment_link')
 r={'code':d['code'],'url':url,'expected':x['offer_hkd'],'pages':[],'evidence':[]}
 try:
  if not url or '.pdf' not in url:raise ValueError('No direct PDF final allocation source')
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=16) as f:raw=f.read(16*1024*1024)
  pdf=PdfReader(io.BytesIO(raw));r['sha256']=hashlib.sha256(raw).hexdigest()
  for i in range(min(6,len(pdf.pages))):
   t=re.sub(r'\s+',' ',pdf.pages[i].extract_text() or '');r['pages'].append({'page':i+1,'text':t})
   for m in re.finditer(r'(?:Final\s+)?Offer\s+Price\s*:?\s*HK\$\s*([\d,.]+)',t,re.I):r['evidence'].append({'price':float(m[1].replace(',','')),'page':i+1,'snippet':t[max(0,m.start()-70):m.end()+160]})
  del raw,pdf;gc.collect()
 except Exception as exc:r['error']=str(exc)
 out.append(r);(P/'ah_final_offers.json').write_text(json.dumps(out,ensure_ascii=False,indent=1)+'\n');print(r['code'],r.get('error',str([(v['price'],v['page']) for v in r['evidence']])),flush=True)
