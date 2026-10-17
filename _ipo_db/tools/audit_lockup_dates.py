"""Reconcile stored expiry dates with retrieved primary-source pages."""
import calendar,hashlib,json,re,sys
from datetime import date,timedelta
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from review_lockups import events_from_pages,DATE,iso
B=json.loads((ROOT/'data/batches/lockup_events.json').read_text());D={d['code']:d for d in json.loads((ROOT/'data/deals.json').read_text())['deals']}
source=ROOT/'out/lockup_review_20261017/sources'
norm=lambda s:re.sub('[^a-z0-9]','',s.lower())
def dates(text):
 out=[]
 for m in DATE.finditer(text):
  try:out.append(iso(m))
  except ValueError:pass
 return sorted(set(out))
rows=[]
for i,e in enumerate(B['events']):
 if e['category']!='Cornerstone' or not e.get('last_day_locked') or e['last_day_locked']>='2026-10-17':continue
 key=hashlib.sha256(e['url'].encode()).hexdigest()[:20];path=source/(key+'.json')
 row={'index':i,'code':e['code'],'name':e['name'],'last_day_locked':e['last_day_locked'],'ipo_date':D[e['code']]['ipo_date'],'basis':e['date_basis'],'url':e['url'],'page':e.get('page'),'source_file':str(path.relative_to(ROOT))}
 if not path.exists():row['status']='source pending';rows.append(row);continue
 s=json.loads(path.read_text())
 if not s.get('ok'):row['status']='source unavailable';rows.append(row);continue
 page_map=s.get('ordered_pages',s['pages'])
 pages=[text for k,text in sorted(page_map.items(),key=lambda x:int(x[0])) if abs(int(k)-(e.get('page') or 1))<=2];text='\n'.join(pages);plain=norm(text)
 row.update(source_sha256=s['sha256'],hash_matches=s['sha256']==e.get('sha256'),snippet_matches=norm(e.get('snippet','')) in plain and bool(e.get('snippet')),dates_on_pages=dates(text))
 expiry=date.fromisoformat(e['last_day_locked']);row['first_unlocked_day']=(expiry+timedelta(days=1)).isoformat()
 row['first_day_matches']=not e.get('first_day_after') or e['first_day_after']==row['first_unlocked_day']
 if e['date_basis'].startswith('Printed'):
  try:parsed=[x for x in events_from_pages(pages,row['ipo_date']) if x['category']=='Cornerstone']
  except ValueError:parsed=[]
  row['parsed_cornerstone_dates']=sorted({x['last_day_locked'] for x in parsed})
  row['status']='verified printed date' if expiry.isoformat() in row['parsed_cornerstone_dates'] and row['first_day_matches'] else 'needs visual table review'
 else:
  # Accept only explicitly inclusive wording, rather than a generic assumed
  # six-month market convention. Retain the exact clause for human review.
  clause=re.search(r'(?:period\s+of\s+)?six\s*(?:\(6\)\s*)?months\s+(?:starting\s+|commencing\s+)?from\s+and\s+(?:inclusive\s+of|including)\s+(?:the\s+)?Listing\s+Date',text,re.I)
  d=date.fromisoformat(row['ipo_date']);m=d.month+6;y=d.year+(m-1)//12;m=(m-1)%12+1;expected=date(y,m,min(d.day,calendar.monthrange(y,m)[1]))-timedelta(days=1)
  row.update(derived_last_day=expected.isoformat(),inclusive_clause=clause.group() if clause else None)
  row['status']='verified explicit inclusive term' if clause and row['snippet_matches'] and expiry==expected and row['first_day_matches'] else 'needs term review'
 rows.append(row)
report={'review_date':'2026-10-17','rows':rows,'counts':dict(Counter(r['status'] for r in rows))}
(ROOT/'out/lockup_review_20261017/date_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(report['counts'])
for r in rows:
 if r['status'].startswith('needs'):print(r['code'],r['last_day_locked'],r['status'],'hash',r.get('hash_matches'),'snippet',r.get('snippet_matches'),r.get('parsed_cornerstone_dates'),r.get('inclusive_clause'))
