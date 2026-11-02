"""Keep Bloomberg reply zones writable and make valuation scope explicit.

Native patch: no full-workbook round trip and no extra Bloomberg requests.
The add-in owns its multi-cell BDH output. A preallocated legacy CSE range
prevents it resizing that output when a source selector changes.
"""
import re,zipfile
from pathlib import Path
import xml.etree.ElementTree as E
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value,put,sort

HISTORY=['AH Recent','Live History','AH Compare Live','AH Reference']

def apply(parts,sheets,root):
    for name in HISTORY:
        doc=E.fromstring(parts[sheets[name]]);changed=False
        for f in doc.iter(q('f')):
            if 'BDH(' in (f.text or '') and f.get('t')=='array':
                # The range remains reserved/empty, but is not a locked CSE
                # block. Never add @/implicit intersection to a history call.
                for key in ['t','ref','aca','ca']:f.attrib.pop(key,None)
                changed=True
        if changed:parts[sheets[name]]=E.tostring(doc)
    db=E.fromstring(parts[sheets['Database']]);dc=nodes(db)
    val=E.fromstring(parts[sheets['Valuation Data']]);vc=nodes(val)
    if value(vc.get('BM2'))=='Scope v2':return
    n=sum(1 for a,c in dc.items() if re.fullmatch(r'A\d+',a) and int(a[1:])>=5 and value(c))
    last=8+8*(n-1);hrow=8+8*n;arow=hrow+48
    put(db,'B2',v='All',style=dc['B2'].get('s'))
    put(val,'BM1',f='IF(UPPER(TRIM(Database!$B$2))="ALL","All",IF(UPPER(TRIM(Database!$B$2))="OFF","Off",IF(UPPER(TRIM(Database!$B$2))="SELECTED","Selected","Invalid mode")))',v='All')
    put(val,'BM2',v='Scope v2')
    scope='$BM$1';ticker=f'$A${hrow}'
    # Numeric/padded codes are already canonicalised by the existing selector.
    # Codes, not legal-name spelling, identify the requested database issuer.
    for i in range(n):
        rr=8+8*i;dr=5+i
        gate=f'OR({scope}="All",AND({scope}="Selected",OR($A{rr}={ticker},COUNTIF(Screener!$C$21:$C$35,Database!$A${dr})>0)))'
        put(val,'BM'+str(rr),f=gate)
        for col in ['L','M','X','AH','AR']:
            f=vc[col+str(rr)].find(q('f'))
            assert f.text.endswith(',"Not requested")'),(col,rr)
            f.text=f.text[:-len('"Not requested")')]+f'IF({scope}="Off","Off",IF({scope}="Selected","Outside selection","Check mode")))'
    # All selected H metrics share the database result where available. The
    # existing standalone queries are retained only for pipeline-only codes.
    match=f'MATCH({ticker},$A$8:$A${last},0)'
    found=f'IFERROR({match},0)>0'
    enabled=f'AND(OR({scope}="All",{scope}="Selected"),{ticker}<>"",NOT({found}))'
    for k,out in enumerate(['L','M','X','AH','AR']):
        rr=hrow+k*8
        # Request guards also cover NTM/FY estimates, previously not disabled
        # by Off for the selected H block.
        for col in ['C','AU','BD']:
            c=vc.get(col+str(rr));f=c.find(q('f')) if c is not None else None
            if f is not None and re.search(r'\b(BDP|BQL)\(',f.text):f.text=f'IF({enabled},{f.text},"")'
        f=vc['L'+str(rr)].find(q('f'));old=f.text
        lookup=f'INDEX(${out}$8:${out}${last},{match})'
        f.text=f'IF({scope}="Off","Off",IF({scope}="Invalid mode","Check mode",IF({ticker}="","No H code",IFERROR({lookup},{old}))))'
    for rr in range(arow,arow+33,8):
        for col in ['C','AU','BD']:
            c=vc.get(col+str(rr));f=c.find(q('f')) if c is not None else None
            if f is not None and re.search(r'\b(BDP|BQL)\(',f.text):f.text=f'IF(OR({scope}="All",{scope}="Selected"),{f.text},"")'
        f=vc['L'+str(rr)].find(q('f'))
        f.text=f'IF({scope}="Off","Off",IF({scope}="Invalid mode","Check mode",{f.text}))'
    # Off is an intentional state, not a failed Bloomberg response.
    for f in val.iter(q('f')):
        if f.text:f.text=f.text.replace('"Not requested"','"Off"')
    put(db,'C2',f='IF(\'Valuation Data\'!$BM$1="Selected","Selected company + peers",IF(\'Valuation Data\'!$BM$1="All","All database companies",IF(\'Valuation Data\'!$BM$1="Off","Live valuations off","Choose Selected, All or Off")))',v='All database companies',style=dc['C2'].get('s'))
    for name,doc in [('Database',db),('Valuation Data',val)]:
        sort(doc);parts[sheets[name]]=E.tostring(doc)

def patch(source,dest,root):
    with zipfile.ZipFile(source) as z:
        head={p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']}
        _,_,sheets=maps(head);names=HISTORY+['Database','Valuation Data']
        parts={sheets[n]:z.read(sheets[n]) for n in names}
        apply(parts,sheets,Path(root))
        with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as out:
            for item in z.infolist():out.writestr(item,parts.get(item.filename,z.read(item.filename)))
