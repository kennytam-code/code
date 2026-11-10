"""Read issued-capital chapters for caps lacking a filed share count."""
import json,re,io,hashlib,gc,urllib.request
from pathlib import Path
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'data/demand_review_20261109/capital_chapters.json'
D=json.loads((ROOT/'data/deals.json').read_text())['deals'];M={r['code']:r for r in json.loads((ROOT/'data/batches/hkex_prospectus_links.json').read_text())['deals']}
records=json.loads(OUT.read_text()) if OUT.exists() else [];known={r['code'] for r in records}
for d in D:
 if d.get('shares_outstanding') or d['code'] in known:continue
 part=next((p for p in M.get(d['code'],{}).get('parts',[]) if p['label'].lower()=='share capital'),None)
 if part is None:continue
 rec={'code':d['code'],'url':part['url'],'existing_cap':d.get('mktcap_ipo_hkdm'),'offer_price':d.get('final_price')}
 try:
  with urllib.request.urlopen(urllib.request.Request(part['url'],headers={'User-Agent':'Mozilla/5.0'}),timeout=15) as r:raw=r.read(4*1024*1024)
  pdf=PdfReader(io.BytesIO(raw));rec['sha256']=hashlib.sha256(raw).hexdigest();rec['pages']=[]
  for i in range(min(3,len(pdf.pages))):rec['pages'].append({'page':i+1,'text':pdf.pages[i].extract_text() or ''})
  text='\n'.join(p['text'] for p in rec['pages']);flat=re.sub(r'\s+',' ',text)
  patterns=[r'([\d,]{8,})\s+(?:Shares?\s+in\s+total|Shares?\s+in\s+issue\s+immediately)',r'Total\s*:?\s*([\d,]{8,})',r'([\d,]{8,})\s+Total']
  hits=[]
  for pat in patterns:
   for m in re.finditer(pat,flat,re.I):hits.append({'shares':int(m.group(1).replace(',','')),'offset':m.start(),'snippet':flat[max(0,m.start()-400):m.end()+180]})
  rec['candidates']=sorted(hits,key=lambda h:h['offset']);print(d['code'],[h['shares'] for h in rec['candidates']],flush=True)
  del pdf,raw;gc.collect()
 except Exception as e:rec['error']=str(e);print(d['code'],'unavailable',flush=True)
 records.append(rec);OUT.write_text(json.dumps(records,ensure_ascii=False,indent=1)+'\n')
