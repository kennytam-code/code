"""Filed lock-up events and auditable, split-neutral seven-session windows.

The date is the LAST day locked, not a prediction of actual selling. Controller
second-period undertakings can restrict loss of control rather than all sales.
Unstated dates stay unstated. Price-only returns exclude dividends/rights value.
"""
import argparse,json,re,calendar
from bisect import bisect_right
from datetime import date,timedelta
from pathlib import Path
from corp_actions import load_actions
ROOT=Path(__file__).resolve().parent.parent
MONTHS='January February March April May June July August September October November December'.split()
MONTH=r'(?:'+'|'.join(MONTHS)+r')'
DATE=re.compile(r'('+MONTH+r')\s+(\d{1,2})\s*,?\s*(20\d{2})|(\d{1,2})\s+('+MONTH+r')\s*,?\s*(20\d{2})',re.I)
GROUP=re.compile(r'(?im)^[ \t]*(Cornerstone Investors?|Controlling Shareholders?|Single Largest[^\n]*Shareholders?|Pre-IPO Investors?[^\n]*|Other (?:Existing )?Shareholders?[^\n]*|Directors|Senior Management|Pathfinder[^\n]*|Key Persons?[^\n]*)[ \t]*$')

def iso(m):
    month,day,year=(m.group(1),m.group(2),m.group(3)) if m.group(1) else (m.group(5),m.group(4),m.group(6))
    return date(int(year),[x.lower() for x in MONTHS].index(month.lower())+1,int(day)).isoformat()

def events_from_pages(pages,ipo_date):
    text='\n'.join(pages);starts=[];n=0
    for p in pages:starts.append(n);n+=len(p)+1
    events=[];groups=list(GROUP.finditer(text))
    for k,g in enumerate(groups):
        end=groups[k+1].start() if k+1<len(groups) else min(len(text),g.end()+18000)
        block=text[g.end():end]
        caption=re.search(r'Last\s+day\s+subject|Expiry\s+date|lock.up\s+(?:expiry|expiration)',block,re.I)
        if not caption or caption.start()>1500:continue
        # End at the table's footnotes/explanation or next announcement
        # section. Underwriting termination and greenshoe dates are not
        # investor lock-up expiries.
        table=re.split(r'(?im)^\s*(?:Notes?\s*:|The\s+expiry\s+date|The\s+lock.up\s+period|PUBLIC\s+FLOAT|COMMENCEMENT|OTHER\s+INFORMATION|OVER.ALLOTMENT\s+OPTION|SHARE\s+CERTIFICATES|The\s+Directors\s+confirm|The\s+Hong\s+Kong\s+(?:Underwriting|Public))',block,1)[0]
        found={}
        for m in DATE.finditer(table):
            dt=iso(m)
            if dt<=ipo_date:continue
            # Dates occur in the table's right-most column. Keep each distinct
            # holder-group date; page/caption survive the grouped display.
            found.setdefault(dt,[]).append(m)
        for dt,ms in sorted(found.items()):
            m=ms[0];phase=''
            tail=re.sub(r'\s+',' ',table[m.end():m.end()+100])
            if re.search('First Six.Month',tail,re.I):phase=' — initial restriction'
            if re.search('Second Six.Month',tail,re.I):phase=' — control-retention period'
            offset=g.end()+m.start();group=re.sub(r'\s+',' ',g.group(1)).strip()
            category='Cornerstone' if group.lower().startswith('cornerstone') else ('Controller' if re.search('Controlling|Largest',group,re.I) else ('Pre-IPO / existing holders' if re.search('Pre-IPO|Other Existing',group,re.I) else group))
            events.append({'category':category+phase,'last_day_locked':dt,'first_day_after':(date.fromisoformat(dt)+timedelta(days=1)).isoformat(),'date_basis':'Printed last day locked','page':bisect_right(starts,offset),'snippet':re.sub(r'\s+',' ',text[max(g.start(),offset-300):offset+200]),'filing_group':group})
    # Older filings often state the inclusive cornerstone period in prose.
    # Derive only when its start and duration are explicit. Do not infer a
    # generic six-month period just because a deal has cornerstone investors.
    if not any(e['category']=='Cornerstone' for e in events):
        pat=re.compile(r'cornerstone[^.]{0,250}(?:agreed|undertaken)[^.]{0,250}(?:six|6)\s*(?:\(6\)\s*)?months\s+from\s+and\s+(?:including|inclusive\s+of)[^.]{0,40}Listing\s+Date',re.I)
        m=pat.search(text)
        if m:
            d=date.fromisoformat(ipo_date);mon=d.month+6;y=d.year+(mon-1)//12;mon=(mon-1)%12+1
            last=date(y,mon,min(d.day,calendar.monthrange(y,mon)[1]))-timedelta(days=1)
            events.append({'category':'Cornerstone','last_day_locked':last.isoformat(),'first_day_after':(last+timedelta(days=1)).isoformat(),'date_basis':'Derived from filed inclusive six-month term','page':bisect_right(starts,m.start()),'snippet':re.sub(r'\s+',' ',m.group())})
    return events

def window(expiry,sessions,prices,actions,cutoff,mode='Trading sessions',days=7):
    if expiry>cutoff:return {'status':'Upcoming expiry','pre_start':None,'anchor':None,'post_end':None,'pre_start_close':None,'anchor_close':None,'post_end_close':None,'before_pct':None,'after_pct':None,'path':[]}
    d=date.fromisoformat(expiry);idx=bisect_right(sessions,expiry)-1
    if idx<0:return {'status':'No anchor session'}
    anchor=sessions[idx]
    if mode=='Trading sessions':
        pre=sessions[idx-days] if idx>=days else None
        post=sessions[idx+days] if idx+days<len(sessions) else None
    else:
        def align(dt):
            i=bisect_right(sessions,dt.isoformat())-1
            return sessions[i] if i>=0 else None
        pre=align(d-timedelta(days=days));post=align(d+timedelta(days=days)) if (d+timedelta(days=days)).isoformat()<=cutoff else None
    def close(dt):
        if dt is None or dt>cutoff:return None
        raw=prices.get(dt)
        if raw is None:return None
        factor=1
        for ev in actions:
            if dt>=ev['date']:factor*=float(ev['ratio'])
        return raw*factor
    vals=[close(dt) for dt in [pre,anchor,post]]
    status=('Upcoming expiry' if expiry>cutoff else 'After window pending' if post is None or post>cutoff else 'Complete')
    if expiry<=cutoff and (vals[0] is None or vals[1] is None or post is not None and post<=cutoff and vals[2] is None):status='Missing close / suspended'
    # Keep every intervening HK session, including missing/suspended prices.
    # A chart must not join across an absent observation or invent future dates.
    path=[]
    if mode=='Trading sessions':
        for offset in range(-days,days+1):
            pos=idx+offset;dt=sessions[pos] if 0<=pos<len(sessions) else None
            path.append([offset,dt,close(dt)])
    return {'pre_start':pre,'anchor':anchor,'post_end':post,'pre_start_close':vals[0],'anchor_close':vals[1],'post_end_close':vals[2],'before_pct':100*(vals[1]/vals[0]-1) if vals[0] and vals[1] else None,'after_pct':100*(vals[2]/vals[1]-1) if vals[1] and vals[2] else None,'status':status,'path':path}

def main():
    p=argparse.ArgumentParser();p.add_argument('--cache-dir',type=Path,required=True);p.add_argument('--prospectuses',type=Path);p.add_argument('--prices-dir',type=Path,required=True);p.add_argument('--sessions',type=Path,required=True);p.add_argument('--cutoff',default='2026-10-02');a=p.parse_args()
    deals=json.loads((ROOT/'data/deals.json').read_text())['deals'];sessions=json.loads(a.sessions.read_text());actions=load_actions(ROOT);out=[]
    for d in deals:
        evs=[]
        for file in sorted(a.cache_dir.glob(f'allot_{d["code"]}_*.pages.json')):
            r=json.loads(file.read_text())
            for e in events_from_pages(r['pages'],d['ipo_date']):e.update(url=r['url'],sha256=r['sha256']);evs.append(e)
        seen=set();evs=[e for e in evs if not ((e['category'],e['last_day_locked']) in seen or seen.add((e['category'],e['last_day_locked'])))]
        if a.prospectuses and not any(e['category']=='Cornerstone' for e in evs) and not (d.get('cornerstone_none') or d.get('cornerstone_pct')==0):
            for file in a.prospectuses.glob(f'prosp_{d["code"]}_*.pages.json'):
                r=json.loads(file.read_text())
                for pg in r['pages']:
                    derived=[e for e in events_from_pages([pg['text']],d['ipo_date']) if e['category']=='Cornerstone' and e['date_basis'].startswith('Derived')]
                    if derived:
                        e=derived[0];e.update(page=pg['page'],url=r['url'],sha256=r['sha256']);evs.append(e);break
                if any(e['category']=='Cornerstone' for e in evs):break
        if not any(e['category']=='Cornerstone' for e in evs):
            evs.insert(0,{'category':'Cornerstone','last_day_locked':None,'date_basis':'No cornerstone tranche' if d.get('cornerstone_none') or d.get('cornerstone_pct')==0 else 'Expiry not established from available allotment filing','url':d.get('allotment_link')})
        file=a.prices_dir/(d['code']+'.json')
        if not file.exists():file=next(a.prices_dir.glob(f'*{d["code"]}*.json'),None)
        hist=json.loads(file.read_text()) if file else {};prices={r[0]:float(r[2]) for r in hist.get('rows',[]) if len(r)>5 and float(r[5])>0}
        for e in evs:
            e.update(code=d['code'],name=d['name'],sector=d['sector'],price_url=hist.get('src'),price_asof=a.cutoff)
            e['windows']={mode:window(e['last_day_locked'],sessions,prices,actions.get(d['code'],[]),a.cutoff,mode) for mode in ['Trading sessions','Calendar days']} if e['last_day_locked'] else {}
            out.append(e)
    result={'batch':'lockup_events','reviewed_at':date.today().isoformat(),'price_asof':a.cutoff,'window':7,'stock_count':len(deals),'events':out,'method':'Last day locked; anchor last HK session on/before expiry; ±7 HK sessions (or calendar-day option). Exact endpoint closes required; split-neutral price returns; no dividend/rights value; not evidence of actual selling.'}
    (ROOT/'data/batches/lockup_events.json').write_text(json.dumps(result,ensure_ascii=False,indent=1))
    print({'stocks':len(deals),'rows':len(out),'dated':sum(bool(e['last_day_locked']) for e in out),'cornerstone_dated':sum(e['category']=='Cornerstone' and bool(e['last_day_locked']) for e in out)})

if __name__=='__main__':main()
