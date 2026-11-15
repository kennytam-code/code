"""Sequential A/H close refresh, independent of the IPO return snapshot.

Retain accepted observations and IPO pricing inputs. Append provider-observed
raw closes only; keep A/FX observation dates and fail visibly on conflicts.
No workbook, peer refresh, parallel workers or inferred corporate actions.
"""
import argparse
import calendar
import json
import math
import ssl
import time
import urllib.request
from bisect import bisect_right
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':')))
    temp.replace(path)


def fetch(url):
    try:
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context = ssl.create_default_context()
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=25, context=context) as r:
                return json.load(r)
        except Exception:
            if attempt: raise
            time.sleep(1)


def merge_rows(saved, observed, cutoff):
    """No silent restatement: an overlap conflict requires source review."""
    by = {x[0]: x for x in saved}
    added = []
    for row in observed:
        if row[0] > cutoff or not math.isfinite(row[1]) or row[1] <= 0:
            continue
        if row[0] in by:
            if not math.isclose(by[row[0]][1], row[1], rel_tol=0.0001, abs_tol=0.0001):
                raise ValueError(f'Close conflict {row[0]}: saved {by[row[0]][1]}, fetched {row[1]}')
        else:
            by[row[0]] = row
            added.append(row)
    return [by[k] for k in sorted(by)], added


def kline(symbol, start, end, get):
    if (date.fromisoformat(end)-date.fromisoformat(start)).days > 365:
        raise ValueError('Refresh gap exceeds the bounded 320-bar request; backfill in dated annual windows first')
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,{start},{end},320,'
    obj = get(url)
    rows = obj.get('data', {}).get(symbol, {}).get('day', [])
    return [[r[0], float(r[2]), float(r[1])] for r in rows
            if start <= r[0] <= end and len(r) > 5 and float(r[5]) > 0 and float(r[2]) > 0], url, obj


def asof(rows, day):
    i = bisect_right([r[0] for r in rows], day) - 1
    return rows[i] if i >= 0 else None


def aligned_append(old, hs, aa, fx):
    out = list(old)
    last = out[-1][0] if out else ''
    for dt, h, *_ in hs:
        if dt <= last: continue
        a, f = asof(aa, dt), asof(fx, dt)
        if not a or not f: continue
        if (date.fromisoformat(dt)-date.fromisoformat(a[0])).days > 10: continue
        if (date.fromisoformat(dt)-date.fromisoformat(f[0])).days > 5: continue
        out.append([dt, h, a[1], f[1], a[1]*f[1]/h-1, a[0], f[0]])
    return out


def refresh(root=ROOT, cutoff=None, get=fetch):
    from market_universe import load
    from ah_basis import review_for, adjusted_premium
    root = Path(root)
    now = datetime.now(ZoneInfo('Asia/Hong_Kong'))
    cutoff = cutoff or (now.date() - timedelta(days=int(now.hour < 18))).isoformat()
    if cutoff > now.date().isoformat(): raise ValueError('Future cutoff')
    cache = root/'data/ah_study_cache'
    audit_dir = root/'data/ah_refresh_review'
    audit_dir.mkdir(exist_ok=True)
    audit = dict(requested_through=cutoff, retrieved_at=now.isoformat(), errors=[], pairs=[], sources=[])
    roster = {r['code']: r for r in load(root)}
    batches = [(p, json.loads(p.read_text())) for p in
               [root/'data/batches/ah_study.json', root/'data/batches/ah_market_supplement.json']]
    # One shared FX request. Preserve prior accepted rates on overlapping dates.
    fxpath = cache/'cnyhkd.json'; fx = json.loads(fxpath.read_text())
    start = (date.fromisoformat(fx[-1][0])+timedelta(days=1)).isoformat()
    if start <= cutoff:
        epoch = lambda d: int(datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp())
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/CNYHKD=X?period1={epoch(start)}&period2={epoch(cutoff)+86400}&interval=1d'
        obj = get(url); write(audit_dir/'fx_response.json', obj)
        result = obj['chart']['result'][0]; closes = result['indicators']['quote'][0]['close']
        observed = [[datetime.fromtimestamp(t,timezone.utc).date().isoformat(), closes[i]]
                    for i,t in enumerate(result.get('timestamp',[])) if closes[i] is not None]
        fx, added = merge_rows(fx, observed, cutoff)
        # Weekends/holidays can legitimately add nothing. Keep the actual last
        # FX date; aligned_append rejects prices with an excessively old rate.
        if not added: audit['fx_status'] = 'No later provider observations; retained actual last date'
        write(fxpath, fx); audit['sources'].append(url)
    # CSI uses the same requested cutoff; asof is its last actual observation.
    cp = root/'data/csi300_prices.json'; csi = json.loads(cp.read_text())
    start = csi['closes'][-1][0]
    if start < cutoff:
        observed, url, obj = kline('sh000300', start, cutoff, get)
        write(audit_dir/'csi_response.json', obj)
        rows, _ = merge_rows(csi['closes'], [r[:2] for r in observed], cutoff)
        csi.update(closes=rows, asof=rows[-1][0], retrieved_at=now.isoformat())
        csi['source_urls'] = list(dict.fromkeys(csi.get('source_urls',[])+[url])); write(cp,csi)
        audit['sources'].append(url)
    for path, batch in batches:
        for old in batch['pairs']:
            code = old['code']; d = roster[code]; result = dict(code=code, before=old.get('latest_date'))
            try:
                legs = []
                for kind in ['h','a']:
                    p = cache/f'{kind}_{code}.json'; saved = json.loads(p.read_text())
                    acode, venue = d['a_share_code'].split('.')
                    symbol = f'hk{int(code):05d}' if kind=='h' else ('sh' if venue=='SS' else 'sz' if venue=='SZ' else 'bj')+acode
                    start = saved[-min(3,len(saved))][0]
                    observed, url, obj = kline(symbol, start, cutoff, get)
                    if not observed: raise ValueError('No provider observations for '+symbol)
                    write(audit_dir/f'{kind}_{code}_response.json', obj)
                    merged, added = merge_rows(saved, observed, cutoff)
                    write(p, merged); legs.append(merged)
                    result[kind+'_added'] = len(added); result[kind+'_last'] = merged[-1][0]
                    result[kind+'_large_moves'] = [r[0] for i,r in enumerate(merged) if i and r[0] > (old.get('latest_date') or '') and abs(r[1]/merged[i-1][1]-1)>.45]
                    audit['sources'].append(url)
                    time.sleep(.05)
                hs, aa = legs
                old['h_history'] = [r[:2] for r in hs if r[0]>=old['ipo_date']]
                old['history'] = aligned_append(old.get('history',[]),old['h_history'],aa,fx)
                if old['history']:
                    x = old['history'][-1]
                    old.update(latest_date=x[0],latest_h_hkd=x[1],latest_a_cny=x[2],latest_fx=x[3],latest_premium_pct=x[4]*100,latest_a_date=x[5],latest_fx_date=x[6])
                old['latest_h_date'] = old['h_history'][-1][0]
                result['after'] = old.get('latest_date')
            except Exception as exc:
                result['error'] = str(exc); audit['errors'].append(dict(code=code,error=str(exc)))
            audit['pairs'].append(result)
            print(code, result.get('after',result.get('before')), result.get('error',''), flush=True)
            write(audit_dir/'latest.json',audit)
        batch['asof'] = max(r.get('latest_date','') for r in batch['pairs'])
        batch['refreshed_at'] = now.isoformat(); write(path,batch)
    # Only A/H metadata changes. Peer and historical IPO-return data stay intact.
    records = {r['code']:r for _,b in batches for r in b['pairs']}
    mp = root/'data/desk_chart_data.json'; meta = json.loads(mp.read_text()); cr = 2
    for m in meta['pairs']:
        r = records[m['code']]; hs = r.get('h_history',[]); last = hs[-1][0] if hs else None
        review = review_for(m['code'],root)
        def ref(month=False):
            if not last: return None
            dt = date.fromisoformat(last)
            if month:
                mon=dt.month-1; y=dt.year-(mon==0); mon=mon or 12
                target=date(y,mon,min(dt.day,calendar.monthrange(y,mon)[1]))
            else: target=dt-timedelta(days=7)
            x=asof(r.get('history',[]),target.isoformat())
            return adjusted_premium(review,x) if x and (target-date.fromisoformat(x[0])).days<=10 else None
        m.update(cache_start=cr,cache_rows=len(hs),stored_7=ref(),stored_1m=ref(True),latest_date=last,review=review)
        cr += len(hs)
    meta['ah_cache_end']=cr-1; write(mp,meta)
    audit.update(pair_count=len(records),fx_asof=fx[-1][0],csi_asof=csi['asof'])
    write(audit_dir/'latest.json',audit)
    if audit['errors']: raise RuntimeError(f"{len(audit['errors'])} pairs not refreshed; see data/ah_refresh_review/latest.json")
    return audit


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--asof');args=p.parse_args()
    refresh(cutoff=args.asof)
