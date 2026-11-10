"""Retain allocation prose for human review; never infer a trigger from percentages."""
import gc, hashlib, io, json, re, urllib.request
from pathlib import Path
from pypdf import PdfReader
R=Path(__file__).resolve().parent.parent
O=R/'data/demand_review_20261109/remaining_outcome_prose.json'
D=json.loads((R/'data/deals.json').read_text())['deals']
M={r['code']:r for r in json.loads((R/'data/batches/hkex_allotment_files.json').read_text())['manifest']}
out=json.loads(O.read_text()) if O.exists() else []
known={d['code'] for d in out}
for d in D:
 if d['code'] in known or d.get('clawback_status')!='Unconfirmed':continue
 parts=M.get(d['code'],{}).get('parts',[])
 p=next((p for p in parts if p['label']=='Summary'),None) or next((p for p in parts if p['label']=='Document'),None)
 rec={'code':d['code'],'name':d['name'],'pages':[]}
 if not p:rec['error']='No allocation document in manifest'
 else:
  rec['url']=p['url']
  try:
   with urllib.request.urlopen(urllib.request.Request(p['url'],headers={'User-Agent':'Mozilla/5.0'}),timeout=18) as f:raw=f.read(12*1024*1024)
   rec['sha256']=hashlib.sha256(raw).hexdigest();pdf=PdfReader(io.BytesIO(raw))
   for i in range(min(12,len(pdf.pages))):
    t=re.sub(r'\s+',' ',pdf.pages[i].extract_text() or '')
    rec['pages'].append({'page':i+1,'text':t})
   del pdf,raw;gc.collect()
  except Exception as e:rec['error']=str(e)
 out.append(rec);O.write_text(json.dumps(out,ensure_ascii=False,indent=1)+'\n')
 print(len(out),d['code'],rec.get('error','read'),flush=True)
