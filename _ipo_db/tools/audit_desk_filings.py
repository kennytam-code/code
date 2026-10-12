"""Primary-source desk audit. Candidate extraction is separate from accepted changes."""
import json,re,sys,calendar
from pathlib import Path
from datetime import date,timedelta
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from fetch_stabilization import FULL,PARTIAL,NOT_EX,NO_OVERALLOC
D={d['code']:d for d in json.loads((ROOT/'data/deals.json').read_text())['deals']};cache=ROOT.parent/'filings';caps=[];shoes=[];dates=[]
for f in sorted(cache.glob('*.pages.json')):
 x=json.loads(f.read_text());code=x.get('code');d=D.get(code)
 if not d:continue
 txt='\n'.join(pg['text'] for pg in x['pages']);clean=re.sub(r'\s+',' ',txt)
 if x['type']=='allot':
  for pg in x['pages'][:6]:
   t=pg['text'];m=re.search(r'(?:Number|No\.)\s+of\s+issued\s+Shares\s+upon\s+Listing[^0-9]{0,170}([0-9][\d,]{6,})',t,re.I)
   if not m:continue
   n=int(m[1].replace(',',''));tail=t[m.start():m.end()+600];treasury=re.search(r'includ(?:es|ing)\s+([\d,]+)\s+(?:repurchased\s+)?A\s+Shares[^.]{0,250}treasury',tail,re.I);tr=int(treasury[1].replace(',','')) if treasury else 0
   if n<1000000 or not d.get('final_price'):continue
   cap=round((n-tr)*d['final_price']/1e6,1);old=d.get('mktcap_ipo_hkdm')
   caps.append(dict(code=code,name=d['name'],issued=n,treasury=tr,shares_outstanding=n-tr,old=old,new=cap,changed=bool(old is None or abs(cap-old)>max(.1,cap*.0001)),url=x['url'],page=pg['page'],snippet=re.sub(r'\s+',' ',tail)))
 if x['type']=='stab':
  # Only affirmative past exercise language determines exercise; references
  # to hypothetical full exercise in a lapsed notice do not count.
  mfull=re.search(r'Over[- ]?allotment\s+Option[^.]{0,100}?(?:has\s+been|had\s+been|was)\s+(?:fully\s+exercised|exercised\s+in\s+full)',clean,re.I)
  mp=re.search(r'Over[- ]?allotment\s+Option[^.]{0,100}?(?:has\s+been|had\s+been|was)\s+partially\s+exercised|partial\s+exercise\s+of\s+the\s+Over[- ]?allotment\s+Option',clean,re.I);mn=NOT_EX.search(clean)
  status='full' if mfull else 'partial' if mp else ('lapsed (no over-allocation)' if NO_OVERALLOC.search(clean) else 'lapsed') if mn else None
  if not status:continue
  ev=mfull or mp or mn
  block=clean[max(0,ev.start()-60):ev.end()+450]
  q=re.search(r'(?:respect\s+of|for|involving|comprising|an?\s+aggregate\s+of|a\s+total\s+of)\s+([\d,]+)\s+(?:additional\s+|new\s+)?(?:H\s+)?Shares',block,re.I)
  shares=float(q[1].replace(',','')) if q and status in ['full','partial'] else 0 if status.startswith('lapsed') else None
  if shares and d.get('offer_shares') and shares>d['offer_shares']*.3:shares=None
  shoes.append(dict(code=code,name=d['name'],old=d.get('greenshoe_exercised_final'),status=status,old_shares=d.get('greenshoe_shares_exercised'),shares=shares,url=x['url'],snippet=block))
 if x['type']=='prosp':
  for pg in x['pages']:
   t=re.sub(r'\s+',' ',pg['text']);pat=r'cornerstone[^.]{0,1800}?(?:agreed|undertaken|undertakes)[^.]{0,1500}?(?:six|6)\s*(?:\(6\)\s*)?months\s+(?:(?:starting\s+|commencing\s+)?from(?:\s+and\s+(?:including|inclusive\s+of))?|commencing\s+on\s+and\s+including)[^.]{0,45}Listing\s+Date'
   m=re.search(pat,t,re.I)
   if not m:continue
   dt=date.fromisoformat(d['ipo_date']);mon=dt.month+6;y=dt.year+(mon-1)//12;mon=(mon-1)%12+1;release=date(y,mon,min(dt.day,calendar.monthrange(y,mon)[1]));last=release-timedelta(days=1)
   dates.append(dict(code=code,last_day_locked=last.isoformat(),first_day_after=release.isoformat(),date_basis='Derived from filed six-month term; release at six-month anniversary',url=x['url'],page=pg['page'],sha256=x['sha256'],snippet=m[0]))
   break
out=dict(market_caps=caps,shoes=shoes,lockup_dates=dates);(ROOT/'out/desk_filing_candidates.json').write_text(json.dumps(out,ensure_ascii=False,indent=1))
print('Caps extracted',len(caps),'changed',sum(r['changed'] for r in caps),'Shoes',len(shoes),'status differences',sum(r['old']!=r['status'] for r in shoes),'CS terms',len(dates))
for r in shoes:
 if r['old']!=r['status'] or r['shares'] is not None and r['old_shares'] is not None and r['shares']!=r['old_shares']:print('SHOE',r)
