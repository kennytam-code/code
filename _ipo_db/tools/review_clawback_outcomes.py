"""Recover unresolved historical clawback outcomes from completed allocations."""
import json,re,io,hashlib,gc,urllib.request
from pathlib import Path
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'data/demand_review_20261109/clawback_outcomes.json'
D=json.loads((ROOT/'data/deals.json').read_text())['deals'];M={r['code']:r for r in json.loads((ROOT/'data/batches/hkex_allotment_files.json').read_text())['manifest']}
records=json.loads(OUT.read_text()) if OUT.exists() else [];known={r['code'] for r in records}
for d in D:
 if d['code'] in known:continue
 src=d.get('_prov',{}).get('clawback',{}).get('src','')
 if d.get('clawback') is not None and not src.startswith('derived:'):continue
 parts=M.get(d['code'],{}).get('parts',[])
 part=next((p for p in parts if p['label']=='Summary'),None) or next((p for p in parts if p['label']=='Document'),None)
 if not part:continue
 rec={'code':d['code'],'url':part['url'],'existing':d.get('clawback')}
 try:
  with urllib.request.urlopen(urllib.request.Request(part['url'],headers={'User-Agent':'Mozilla/5.0'}),timeout=15) as reply:raw=reply.read(12*1024*1024)
  pdf=PdfReader(io.BytesIO(raw));rec['sha256']=hashlib.sha256(raw).hexdigest();rec['evidence']=[]
  for i in range(min(8,len(pdf.pages))):
   t=re.sub(r'\s+',' ',pdf.pages[i].extract_text() or '')
   for pat in [r'claw.?back.{0,100}?(?:has|have)\s+(?:not\s+)?been\s+(?:triggered|applied|effected)',r'no\s+reallocation.{0,220}?has\s+been\s+(?:effected|made|applied)',r'no\s+reallocation.{0,220}?have\s+been\s+(?:effected|made|applied)']:
    for m in re.finditer(pat,t,re.I):
     phrase=m.group();context=t[max(0,m.start()-240):m.end()+200]
     # Quoted chapter headings are not an actual trigger statement. Check
     # preceding negation; positive reallocation may run in either direction.
     outcome='NO' if re.search(r'\bnot\b',phrase,re.I) or re.search(r'\bno\s+(?:claw.?back|reallocation).{0,240}?(?:has|have)\s+been\s+(?:triggered|applied|effected)',context,re.I) else 'REVIEW'
     rec['evidence'].append({'clawback':outcome,'page':i+1,'snippet':context})
  print(d['code'],sorted({e['clawback'] for e in rec['evidence']}),flush=True);del pdf,raw;gc.collect()
 except Exception as e:rec['error']=str(e);print(d['code'],'unavailable',flush=True)
 records.append(rec);OUT.write_text(json.dumps(records,ensure_ascii=False,indent=1)+'\n')
