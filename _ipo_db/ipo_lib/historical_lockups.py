"""The historical-only HTML sample, separate from the full restriction evidence.

New source/date combinations require an explicit source review. Passing a date
or obtaining a price does not by itself confirm a cornerstone expiry. Incomplete
30-session observations stay in the evidence but not in the comparison sample.
"""
import json,math
from datetime import date
from pathlib import Path

def event_key(event):
    return '|'.join(str(event.get(k) or '') for k in ('code','last_day_locked','sha256'))

def historical_events(batch,root,today=None):
    today=today or date.today().isoformat()
    path=Path(root)/'data/lockup_date_review.json'
    review=json.loads(path.read_text()) if path.exists() else {'events':{}}
    amendments_path=Path(root)/'data/lockup_amendments.json'
    amendments=json.loads(amendments_path.read_text()) if amendments_path.exists() else {}
    blocked=amendments.get('blocked_codes',{})
    accepted=review['events'];result=[]
    for event in batch['events']:
        end=event.get('last_day_locked')
        if event['category']!='Cornerstone' or not end or end>=today:continue
        if event['code'] in blocked:continue
        source=accepted.get(event_key(event),{})
        if not source.get('confirmed') or source.get('url')!=event.get('url'):continue
        w=event.get('windows',{}).get('30 trading sessions',{})
        if w.get('status')!='Complete' or not w.get('post_end') or w['post_end']>batch['price_asof']:continue
        if not all(isinstance(w.get(k),(int,float)) and math.isfinite(w[k]) for k in ('before_pct','after_pct')):continue
        if len(w.get('path',[]))!=61:continue
        result.append(event)
    return result
