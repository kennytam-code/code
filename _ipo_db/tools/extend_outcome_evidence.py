"""Read the rest of the few allocation announcements requiring contextual review."""
import gc,hashlib,io,json,re,urllib.request,urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from pypdf import PdfReader
R=Path(__file__).resolve().parent.parent;P=R/'data/demand_review_20261109'
D=json.loads((P/'remaining_outcome_prose.json').read_text());deals={d['code']:d for d in json.loads((R/'data/deals.json').read_text())['deals']}
held=set(json.loads((P/'remaining_outcome_decisions.json').read_text())['held'])
class Links(HTMLParser):
 def __init__(self):super().__init__();self.a=None;self.links=[]
 def handle_starttag(self,tag,attrs):
  if tag=='a':self.a=[dict(attrs).get('href',''),'']
 def handle_data(self,data):
  if self.a:self.a[1]+=data
 def handle_endtag(self,tag):
  if tag=='a' and self.a:self.links.append(self.a);self.a=None
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as f:return f.read(12*1024*1024)
for d in D:
 if d['code'] not in held:continue
 try:
  url=d.get('url')
  if not url:
   parent=deals[d['code']]['allotment_link'];links=Links();links.feed(get(parent).decode('utf8',errors='replace'))
   url=urllib.parse.urljoin(parent,next(href for href,label in links.links if 'summary' in label.lower()));d['url']=url;d['index_url']=parent
  raw=get(url);d['sha256']=hashlib.sha256(raw).hexdigest();pdf=PdfReader(io.BytesIO(raw));d['pages']=[]
  for i in range(min(32,len(pdf.pages))):d['pages'].append({'page':i+1,'text':re.sub(r'\s+',' ',pdf.pages[i].extract_text() or '')})
  d.pop('error',None);del pdf,raw;gc.collect();print(d['code'],len(d['pages']),'read',flush=True)
 except Exception as e:d['error']=str(e);print(d['code'],str(e),flush=True)
 (P/'remaining_outcome_prose.json').write_text(json.dumps(D,ensure_ascii=False,indent=1)+'\n')
