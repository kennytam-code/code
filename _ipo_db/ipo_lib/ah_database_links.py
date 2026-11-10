"""Reuse one A/H premium and live H quote; preserve quote/history controls."""
import json,re
import xml.etree.ElementTree as E
from patch_peer_workbook import q
from reflow_monitors import nodes,value,put,sort

def typed(c):
    v=value(c)
    return float(v) if c is not None and c.get('t') not in ['str','inlineStr','s','e'] and v not in ['',None] else v

def apply(parts,sheets,root):
    cfg=json.loads((root/'data/ah_link_formulas.json').read_text())
    ah=E.fromstring(parts[sheets['AH']]);ac=nodes(ah)
    md=E.fromstring(parts[sheets['Market Data']]);mc=nodes(md)
    db=E.fromstring(parts[sheets['Database']]);dc=nodes(db)
    ipo=nodes(E.fromstring(parts[sheets['IPO Live']]))
    rows=sorted(int(a[1:]) for a in mc if re.fullmatch(r'P\d+',a) and int(a[1:])>=3 and value(mc[a]))
    end=max(rows)+5
    lend=max(int(a[1:]) for a in ipo if re.fullmatch(r'A\d+',a) and str(value(ipo[a])).endswith(' HK Equity'))
    codes={str(int(value(mc['P'+str(r)]))).zfill(4):r for r in rows}
    for r in rows:
        h=mc['AD'+str(r)];f=cfg['h_quote'].replace('{row}',str(r)).replace('{lend}',str(lend))
        put(md,'AD'+str(r),v=typed(h),f=f,style=h.get('s'))
        current=ac['I'+str(r+5)];cached=typed(current)
        if cached in [None,'']:cached='No quote'
        put(ah,'I'+str(r+5),v=cached,f=cfg['ah_current'].replace('{row}',str(r)),style=current.get('s'))
    ac=nodes(ah)
    for a,c in dc.items():
        if not re.fullmatch(r'A\d+',a) or int(a[1:])<5 or not value(c):continue
        r=int(a[1:]);code=str(int(value(c))).zfill(4);col='BT'+str(r)
        f=cfg['database'].replace('{row}',str(r)).replace('{end}',str(end))
        cached=typed(ac['I'+str(codes[code]+5)]) if code in codes else 'N/A'
        if value(dc.get('BQ'+str(r))) and code not in codes:raise ValueError('Missing AH roster member '+code)
        put(db,col,v=cached,f=f,style=dc[col].get('s'))
    put(db,'BP2',v='Quotes',style=dc['A2'].get('s'))
    put(db,'BQ2',v=value(ac['E4']),f='HYPERLINK("#\'AH\'!E4",AH!$E$4)',style=dc['B2'].get('s'))
    put(db,'BT4',v='A premium now',style=dc['BT4'].get('s'))
    for name,doc in [('AH',ah),('Market Data',md),('Database',db)]:
        sort(doc);parts[sheets[name]]=E.tostring(doc)
