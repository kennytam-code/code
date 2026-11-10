"""Fresh HKEX checks of previously populated outcomes; no automatic acceptance."""
import gc,hashlib,io,json,re,urllib.request,urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from pypdf import PdfReader
R=Path(__file__).resolve().parent.parent;P=R/'data/demand_review_20261109';O=P/'existing_outcome_prose.json'
D={d['code']:d for d in json.loads((R/'data/deals.json').read_text())['deals']}
M={r['code']:r for r in json.loads((R/'data/batches/hkex_allotment_files.json').read_text())['manifest']}
targets=json.loads((P/'existing_outcome_targets.json').read_text());out=json.loads(O.read_text()) if O.exists() else [];known={d['code'] for d in out}
class Links(HTMLParser):
 def __init__(self):super().__init__();self.a=None;self.links=[]
 def handle_starttag(self,tag,attrs):
  if tag=='a':self.a=[dict(attrs).get('href',''),'']
 def handle_data(self,data):
  if self.a:self.a[1]+=data
 def handle_endtag(self,tag):
  if tag=='a' and self.a:self.links.append(self.a);self.a=None
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as f:return f.read(16*1024*1024)
for c in targets:
 if c in known or c=='2550':continue
 d={'code':c,'previous':D[c].get('clawback'),'pages':[]}
 try:
  parts=M.get(c,{}).get('parts',[]);part=next((p for p in parts if p['label']=='Summary'),None) or next((p for p in parts if p['label']=='Document'),None)
  url=part['url'] if part else D[c]['allotment_link']
  if '.htm' in url:
   links=Links();links.feed(get(url).decode('utf8',errors='replace'));url=urllib.parse.urljoin(url,next(h for h,l in links.links if 'summary' in l.lower()))
  d['url']=url;raw=get(url);d['sha256']=hashlib.sha256(raw).hexdigest();pdf=PdfReader(io.BytesIO(raw))
  for i in range(min(32,len(pdf.pages))):d['pages'].append({'page':i+1,'text':re.sub(r'\s+',' ',pdf.pages[i].extract_text() or '')})
  del pdf,raw;gc.collect()
 except Exception as e:d['error']=str(e)
 out.append(d);O.write_text(json.dumps(out,ensure_ascii=False,indent=1)+'\n');print(len(out),c,d.get('error','read'),flush=True)
