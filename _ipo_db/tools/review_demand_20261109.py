"""Bounded review of existing evidence and explicit prospectus mechanisms."""
import json,re,signal,hashlib,collections,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
CACHE=Path('/Users/lemon/Desktop/REPO/code/_ipo_db/scrape/text_cache')
OUT=ROOT/'data/demand_review_20261109';OUT.mkdir(exist_ok=True)
load=lambda p:json.loads((ROOT/p).read_text())
deals=load('data/deals.json')['deals'];by={d['code']:d for d in deals}
def alarm(*_):raise TimeoutError()
signal.signal(signal.SIGALRM,alarm)
def read(p):
 try:
  signal.alarm(2);return p.read_text()
 except (TimeoutError,OSError):return None
 finally:signal.alarm(0)
def flat(t):return re.sub(r'\s+',' ',t)
sources={}
for name in ['subscription_review','desk_source_review','latest_listed_review_20261015','latest_listed_review_20261028']:
 for r in load('data/batches/'+name+'.json').get('deals',[]):sources.setdefault(r['code'],{}).update(r)
report={'subscription':[],'capital':[],'mechanisms':[],'unread_files':[]}
for d in deals:
 c=d['code'];s=sources.get(c,{})
 ev=s.get('oversub_intl_mult_evidence') or d.get('oversub_intl_mult_evidence')
 report['subscription'].append({'code':c,'current':d.get('oversub_intl_mult'),'source_value':s.get('oversub_intl_mult'),'evidence':ev,'matches':d.get('oversub_intl_mult')==s.get('oversub_intl_mult'),'note':s.get('oversub_intl_mult_note') or d.get('oversub_intl_mult_note')})
 fp=d.get('final_price');sh=d.get('shares_outstanding');cap=d.get('mktcap_ipo_hkdm');dr=d.get('depositary_ratio') or 1
 implied=round(fp*sh/dr/1e6,1) if fp and sh else None
 report['capital'].append({'code':c,'current':cap,'implied':implied,'difference':round(cap-implied,2) if cap is not None and implied is not None else None,'basis':d.get('mktcap_basis'),'source':s.get('mktcap_source') or d.get('mktcap_source'),'source_page':s.get('mktcap_source_page') or d.get('mktcap_source_page'),'shares':sh,'price':fp,'depositary_ratio':dr})
files=[p for p in CACHE.glob('prosp_*') if p.name.split('_')[1] in by and by[p.name.split('_')[1]].get('ipo_date','')>='2025-08-04']
if '--evidence-only' in sys.argv:files=[]
for i,p in enumerate(files):
 txt=read(p)
 if txt is None:report['unread_files'].append(p.name);continue
 t=flat(txt);c=p.name.split('_')[1]
 hits=[]
 for m in re.finditer(r'Mechanism\s+([AB])\b',t,re.I):
  hits.append({'mechanism':m.group(1).upper(),'file':p.name,'text_sha256':hashlib.sha256(txt.encode()).hexdigest(),'snippet':t[max(0,m.start()-220):m.end()+360]})
 if by[c].get('listing_regime_18c'):
  m=re.search(r'(?:claw.?back.{0,200}18C\.09|18C\.09.{0,200}claw.?back)',t,re.I)
  if m:hits.append({'mechanism':'18C','file':p.name,'text_sha256':hashlib.sha256(txt.encode()).hexdigest(),'snippet':t[max(0,m.start()-100):m.end()+300]})
 if hits:report['mechanisms'].append({'code':c,'hits':hits})
 if i%25==0:
  print('Prospectus files inspected',i+1,'/',len(files),flush=True)
  (OUT/'candidates.json').write_text(json.dumps(report,ensure_ascii=False,indent=1)+'\n')
(OUT/'candidates.json').write_text(json.dumps(report,ensure_ascii=False,indent=1)+'\n')
print('Subscription mismatches',[(r['code'],r['current'],r['source_value']) for r in report['subscription'] if not r['matches']])
print('Capital arithmetic mismatches',[(r['code'],r['difference']) for r in report['capital'] if r['difference'] not in [None,0]])
print('Explicit mechanisms',len({r['code'] for r in report['mechanisms']}),'unread',len(report['unread_files']),flush=True)
