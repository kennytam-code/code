"""Reviewed pipeline comparison sets, shared by Excel and HTML."""
import json,re
import xml.etree.ElementTree as E
from patch_peer_workbook import q
from reflow_monitors import nodes,value,put,sort

def enrich(rows,root):
    source=root/'data/pipeline_peers.json'
    reviewed=json.loads(source.read_text()) if source.exists() else {}
    for p in rows:
        code=str(p.get('expected_code') or p.get('code') or '').zfill(4)
        if code in reviewed:
            p['peer_codes']=reviewed[code]['codes'];p['peer_basis']=reviewed[code]['basis']
    return rows

def apply(parts,sheets,root):
    pipeline=E.fromstring(parts[sheets['Pipeline']]);pc=nodes(pipeline)
    changed=False
    for addr,c in pc.items():
        if re.fullmatch(r'C\d+',addr) and value(c)=='Introduction':
            for col in ['K','P','Q','S']:
                cell=pc.get(col+addr[1:])
                if value(cell)=='at launch':
                    put(pipeline,col+addr[1:],v='N/A',style=cell.get('s'));changed=True
    if changed:
        sort(pipeline);parts[sheets['Pipeline']]=E.tostring(pipeline)
    reviewed=json.loads((root/'data/pipeline_peers.json').read_text())
    calc=E.fromstring(parts[sheets['Calc (scoring engine)']]);cs=nodes(calc)
    if value(cs.get('CA1'))=='Pipeline comparison sets':return
    assert not any(re.fullmatch(r'C[AB]\d+',a) for a in cs),'Comparison helper region occupied'
    put(calc,'CA1',v='Pipeline comparison sets')
    for r,p in enumerate(reviewed.values(),3):
        put(calc,'CA'+str(r),v=p['name']);put(calc,'CB'+str(r),v=','.join(p['codes']))
    screen=E.fromstring(parts[sheets['Screener']]);sc=nodes(screen)
    if not value(sc['P10']) and sc['P10'].find(q('f')) is None:
        put(screen,'P10',f=f'IFERROR(INDEX(\'Calc (scoring engine)\'!$CB$3:$CB${len(reviewed)+2},MATCH(SelectedDeal,\'Calc (scoring engine)\'!$CA$3:$CA${len(reviewed)+2},0)),"")',v='',style=sc['P10'].get('s'))
        put(screen,'N10',v='Peer codes',style=sc['N10'].get('s'))
    for name,doc in [('Screener',screen),('Calc (scoring engine)',calc)]:
        sort(doc);parts[sheets[name]]=E.tostring(doc)
