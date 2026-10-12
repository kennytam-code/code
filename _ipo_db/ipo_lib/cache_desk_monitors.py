"""Dated opening caches for formula-backed monitors, never live quote stand-ins."""
import json,math,re,xml.etree.ElementTree as ET
from pathlib import Path
from datetime import date
from market_universe import histories
from ah_basis import comparable,review_for
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main';CN='http://schemas.openxmlformats.org/drawingml/2006/chart';q=lambda s:'{'+NS+'}'+s;c=lambda s:'{'+CN+'}'+s
serial=lambda dt:(date.fromisoformat(dt)-date(1899,12,30)).days

def add_caches(parts,sheets,root):
 docs={name:ET.fromstring(parts[p]) for name,p in sheets.items() if name in ['AH','AH Delta','AH Compare','Lock-up','Lock Compare','Peer Trades','Peer Chart','Chart Data']};cells={name:{n.get('r'):n for n in doc.iter(q('c'))} for name,doc in docs.items()};refs={}
 def text(x):
  if x is None:return ''
  v=x.find(q('v'));return v.text if v is not None and v.text else ''.join(n.text or '' for n in x.iter(q('t')))
 def put(sheet,addr,v,error=False):
  x=cells[sheet].get(addr)
  if x is None:return
  for node in list(x):
   if node.tag in [q('v'),q('is')]:x.remove(node)
  x.attrib.pop('t',None);n=ET.SubElement(x,q('v'))
  if error:x.set('t','e');n.text='#N/A'
  elif v is None:x.set('t','str');n.text=''
  elif isinstance(v,str):x.set('t','str');n.text=v
  else:n.text=str(v)
 dc=json.loads((root/'data/desk_chart_data.json').read_text());record={r['code']:r for r in histories(root)['pairs']}
 for i,m in enumerate(dc['pairs'],3):
  put('AH Delta',f'D{i}',m['stored_7']);put('AH Delta',f'E{i}',m['stored_1m']);r=record[m['code']];latest=r.get('latest_premium_pct')
  for col,key in [('G','stored_7'),('H','stored_1m')]:put('AH',f'{col}{i+5}',latest-100*m[key] if latest is not None and m[key] is not None else None)
 def ec(n):
  s=''
  while n:n,r=divmod(n-1,26);s=chr(65+r)+s
  return s
 selected=[text(cells['AH'].get(a)) for a in ['B4','K28','K29','K30']]
 for k,code in enumerate(selected):
  rec=record.get(code);meta=next((m for m in dc['pairs'] if m['code']==code),None);hs=rec['h_history'] if rec else [];aligned={r[0]:r for r in rec.get('history',[])} if rec else {};base=k*9;review=review_for(code,root)
  for addr,val in [(ec(base+8)+'2',dc['pairs'].index(meta)+1 if meta else 0),(ec(base+8)+'3',len(hs)),(ec(base+8)+'4',meta['cache_start'] if meta else 0),(ec(base+9)+'2',0),(ec(base+9)+'3',max(1,len(hs)))]:put('AH Compare',addr,val)
  premiums=[]
  for i,(dt,h) in enumerate(hs,5):
   v=aligned.get(dt);p=v[4] if v and comparable(review,dt,v[5]) else None;premiums.append(p)
   for j,value in enumerate([serial(dt),h,v[2] if v else None,v[3] if v else None,serial(v[5]) if v else None,serial(v[6]) if v else None,p],1):put('AH Compare',ec(base+j)+str(i),value,error=value is None and j>1)
  refs[f'AHCompare{k+1}Dates']=[serial(x[0]) for x in hs] or [None];refs[f'AHCompare{k+1}Premium']=premiums or [None]
 events=[e for e in json.loads((root/'data/batches/lockup_events.json').read_text())['events'] if e['category']=='Cornerstone' and e['date_basis']!='No cornerstone tranche'];cutoff=dc['peer']['asof'];start=text(cells['Lock-up'].get('B37'));finish=text(cells['Lock-up'].get('B38'));from_serial=float(start) if start else serial('2021-01-01');to_serial=float(finish) if finish else serial(cutoff)
 def auto(code):
  es=[e for e in events if e['code']==code];past=[e for e in es if e.get('last_day_locked') and e['last_day_locked']<=cutoff];return sorted(past or es,key=lambda e:e.get('last_day_locked') or '',reverse=True)[0] if es else None
 choices=[auto(text(cells['Lock-up'].get(f'B{r}'))) for r in range(32,36)];cohort=[e for e in events if e.get('last_day_locked') and from_serial<=serial(e['last_day_locked'])<=to_serial]
 def point(e,offset):
  w=e.get('windows',{}).get('30 trading sessions',{}) if e else {};p=next((p for p in w.get('path',[]) if p[0]==offset),None);return p[2]/w['anchor_close']-1 if p and p[2] and w.get('anchor_close') else None
 for col in ['B','C','D','E','F']:refs[f"'Lock Compare'!${col}$5:${col}$65"]=[]
 refs["'Lock Compare'!$A$5:$A$65"]=list(range(-30,31))
 for off in range(-30,31):
  v=[point(e,off) for e in cohort];v=[x for x in v if x is not None];vals=[sum(v)/len(v) if v else None]+[point(e,off) for e in choices]
  for j,val in enumerate(vals,2):col=ec(j);put('Lock Compare',f'{col}{off+35}',val,error=val is None);refs[f"'Lock Compare'!${col}$5:${col}$65"].append(val)
 pp=dc['peer'];selected=text(cells['Peer Trades'].get('B4'));peer=next(p for p in pp['pairs'] if p['id']==selected);h=peer['history'];put('Peer Chart','H2',pp['pairs'].index(peer)+1);put('Peer Chart','H3',peer['name_a']+' ('+peer['code_a']+')');put('Peer Chart','H4',peer['name_b']+' ('+peer['code_b']+')');put('Peer Chart','I2',0);put('Peer Chart','K2',0);put('Peer Chart','J2',max(1,len(h)))
 for i,row in enumerate(h,5):
  dt,a,b,ra,rb,spread=row
  for j,val in enumerate([serial(dt),ra,rb,100*spread,a,b],1):put('Peer Chart',ec(j)+str(i),val)
 for name,idx in [('Dates',0),('A',3),('B',4),('Spread',5)]:refs['PeerChart'+name]=[serial(x[0]) if idx==0 else x[idx]*100 if idx==5 else x[idx] for x in h]
 # Native charts consume exactly the same cached source cells and lengths.
 for name,raw in list(parts.items()):
  if not name.startswith('xl/charts/chart') or not name.endswith('.xml'):continue
  doc=ET.fromstring(raw);changed=False
  for ref in doc.iter(c('numRef')):
   f=ref.find(c('f'));formula=f.text or '' if f is not None else '';key=next((k for k in refs if k==formula or formula.endswith('!'+k)),None)
   if key is None:continue
   vals=refs[key];old=ref.find(c('numCache'))
   if old is not None:ref.remove(old)
   cache=ET.SubElement(ref,c('numCache'));ET.SubElement(cache,c('formatCode')).text='dd-mmm-yy' if 'Dates' in key else '0.0';ET.SubElement(cache,c('ptCount'),{'val':str(len(vals))})
   for i,v in enumerate(vals):
    if v is not None and math.isfinite(v):ET.SubElement(ET.SubElement(cache,c('pt'),{'idx':str(i)}),c('v')).text=str(v)
   changed=True
  for label in doc.iter(c('tx')):
   ref=label.find(c('strRef'))
   if ref is None:continue
   f=ref.find(c('f'));formula=f.text if f is not None else ''
   label_value=None
   for sheet in ['AH','Lock-up','Peer Chart']:
    match=re.fullmatch(r"'?"+re.escape(sheet)+r"'?!\$(\w+)\$(\d+)",formula)
    if match:label_value=text(cells[sheet].get(match[1]+match[2]));break
   if label_value:
    old=ref.find(c('strCache'))
    if old is not None:ref.remove(old)
    cache=ET.SubElement(ref,c('strCache'));ET.SubElement(cache,c('ptCount'),{'val':'1'});ET.SubElement(ET.SubElement(cache,c('pt'),{'idx':'0'}),c('v')).text=label_value;changed=True
  if changed:parts[name]=ET.tostring(doc,encoding='utf-8')
 for name,doc in docs.items():parts[sheets[name]]=ET.tostring(doc,encoding='utf-8')
