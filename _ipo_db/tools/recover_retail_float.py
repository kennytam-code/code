"""Extract explicit final public-share counts from official allocation notices."""
import gc,hashlib,io,json,re,urllib.request
from pathlib import Path
from pypdf import PdfReader
R=Path(__file__).resolve().parent.parent;P=R/'data/demand_review_20261109';O=P/'retail_float_prose.json'
load=lambda p:json.loads(p.read_text())
D=load(R/'data/deals.json')['deals'];M={d['code']:d for d in load(R/'data/batches/hkex_allotment_files.json')['manifest']}
existing={d['code']:d for f in ['remaining_outcome_prose.json','existing_outcome_prose.json'] for d in load(P/f) if d.get('pages')}
out=load(O) if O.exists() else [];existing.update({d['code']:d for d in out})
for d in D:
 c=d['code']
 if d.get('public_shares_final') is not None or c in existing:continue
 parts=M.get(c,{}).get('parts',[]);p=next((p for p in parts if p['label']=='Summary'),None) or next((p for p in parts if p['label']=='Document'),None)
 r={'code':c,'pages':[]}
 try:
  if not p:raise ValueError('No PDF allocation source in manifest')
  r['url']=p['url']
  with urllib.request.urlopen(urllib.request.Request(p['url'],headers={'User-Agent':'Mozilla/5.0'}),timeout=18) as f:raw=f.read(16*1024*1024)
  r['sha256']=hashlib.sha256(raw).hexdigest();pdf=PdfReader(io.BytesIO(raw))
  for i in range(min(20,len(pdf.pages))):r['pages'].append({'page':i+1,'text':re.sub(r'\s+',' ',pdf.pages[i].extract_text() or '')})
  del pdf,raw;gc.collect()
 except Exception as e:r['error']=str(e)
 out.append(r);existing[c]=r;O.write_text(json.dumps(out,ensure_ascii=False,indent=1)+'\n');print(len(out),c,r.get('error','read'),flush=True)
# Require a complete grouped number followed by share label or the next table label.
# PDF spacing inside comma-separated thousands is normalized, never truncated.
pat=re.compile(r'(?:final\s+(?:number|no\.)\s+of\s+(?:Hong Kong |HK |Public )?(?:Offer |H |Sale )?Shares\s+(?:under|available\s+under|(?:offered\s+)?(?:in|for))\s+the\s+(?:Hong Kong |HK )?Public\s+(?:Offering|Offer|Subscription)(?:\s+(?:has been|will be|is|are|was|has increased to|has been increased to|is therefore|is now|amounts to|is adjusted to))?\s*[:=]?\s*)([\d, ]+)(?=\s*(?:Offer |H )?Shares\b|\s+No\.|\s+%\s+of|\s+Allocation\b|\s+Percentage\b|\s+The\b|\s+Final\b|\s+Number\b)',re.I)
candidates=[];held=[]
for d in D:
 if d.get('public_shares_final') is not None:continue
 c=d['code'];r=existing.get(c,{});hits=[]
 for p in r.get('pages',[]):
  t=p['text']
  for m in pat.finditer(t):
   num=m[1].replace(' ','').strip(',')
   if not re.fullmatch(r'\d{1,3}(?:,\d{3})+|\d+',num):continue
   v=int(num.replace(',',''))
   if not v or (d.get('offer_shares') and v>d['offer_shares']*1.3):continue
   hits.append({'public_shares_final':v,'page':p['page'],'snippet':t[max(0,m.start()-80):m.end()+200]})
 if hits and len({h['public_shares_final'] for h in hits})==1:
  h=hits[0];candidates.append({'code':c,'public_shares_final':h['public_shares_final'],'evidence':dict(h,url=r['url'],sha256=r['sha256'])})
 else:held.append({'code':c,'hits':hits,'error':r.get('error')})
(P/'retail_float_candidates.json').write_text(json.dumps({'candidates':candidates,'held':held},ensure_ascii=False,indent=2)+'\n');print('Candidates',len(candidates),'held',len(held))
