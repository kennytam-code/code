"""Small public closing-quote snapshot for the seven-year monitor only.

No quote from this source overwrites IPO terms, historical returns or
Bloomberg valuation fields. Bloomberg mode remains a direct terminal pull.
"""
import json,re,math
from datetime import datetime
from pathlib import Path
import requests
from market_universe import load

ROOT=Path(__file__).resolve().parent.parent

def refresh(root=ROOT):
 root=Path(root);codes=sorted({str(d['code']).zfill(4) for d in load(root)})
 quotes={};errors=[];session=requests.Session()
 for start in range(0,len(codes),60):
  batch=codes[start:start+60];url='https://qt.gtimg.cn/q='+','.join('hk'+c.zfill(5) for c in batch)
  try:
   response=session.get(url,timeout=25);response.raise_for_status();response.encoding='gb18030'
   for ticker,raw in re.findall(r'v_hk(\d+)="([^"]*)"',response.text):
    fields=raw.split('~');code=str(int(ticker)).zfill(4)
    if code not in batch or len(fields)<33 or fields[2]!=ticker:continue
    price,previous=float(fields[3]),float(fields[4]);stamp=datetime.strptime(fields[30],'%Y/%m/%d %H:%M:%S')
    if not all(math.isfinite(x) and x>0 for x in [price,previous]):continue
    # Stale/suspended names keep their dated price but do not enter today's mean.
    quotes[code]={'last':price,'previous_close':previous,'quote_time':stamp.isoformat(sep=' '),'source':'Tencent HK quote'}
  except (requests.RequestException,ValueError) as exc:errors.append({'codes':batch,'error':str(exc)})
 asof=max((v['quote_time'][:10] for v in quotes.values()),default=None)
 if not quotes:raise RuntimeError('No validated public closing quotes; retained prior snapshot')
 result={'asof':asof,'timezone':'Asia/Hong_Kong','source':'https://qt.gtimg.cn/','quotes':quotes,'requested':len(codes),'missing':sorted(set(codes)-set(quotes)),'request_errors':errors}
 (root/'data/live_snapshot.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')))
 print(f'Live monitor snapshot: {len(quotes)}/{len(codes)} validated quotes, {asof}; {len(errors)} failed batches')
 return result

if __name__=='__main__':refresh()
