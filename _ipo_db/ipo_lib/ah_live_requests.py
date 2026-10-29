"""Bounded native Bloomberg arrays and shared A/H horizon lookups.

Current prices remain scalar BDP calls. History returns have explicit native
two-column array ranges; no scalar implicit intersection or MATCH on headers.
Full chart histories have an independent Stored/Bloomberg selector.
"""
import json,re
from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as E
from reflow_monitors import nodes,value,put,sort,ec,ci
from patch_peer_workbook import q

def position(dates,prices,cut,enabled):
    # MATCH over 1/error flags ignores headers/padding and retains zero as
    # an explicit not-found position. Each leg is scanned once per horizon.
    return f'IF({enabled},IFERROR(MATCH(2,1/ISNUMBER({dates})/ISNUMBER({prices})/({dates}>0)/({prices}>0)/({dates}<={cut}),1),0),0)'

def normalized_date(cell):
    numeric=f'IF({cell}>=10000000,DATE(INT({cell}/10000),MOD(INT({cell}/100),100),MOD({cell},100)),INT({cell}))'
    text=f'IF(LEN(TRIM({cell}))=8,DATE(VALUE(LEFT({cell},4)),VALUE(MID({cell},5,2)),VALUE(RIGHT({cell},2))),DATEVALUE(LEFT({cell},10)))'
    return f'IFERROR(IF(ISNUMBER({cell}),{numeric},{text}),"")'

def entitlement(row,a_date,h_date):
    return '*'.join(f'IF(AND(${a}{row}>0,{a_date}>=${a}{row}),${fac}{row},1)/IF(AND(${h}{row}>0,{h_date}>=${h}{row}),${fac}{row},1)' for h,a,fac in [('J','K','R'),('L','M','S'),('O','P','T')])

def reference(row,stored,cut,hpos,hd,hp,apos,ad,ap,fpos,fd,fp):
    good=f'IFERROR(AND({hpos}>0,{apos}>0,{fpos}>0,{hd}>=F{row},{hd}<={cut},{cut}-{hd}<=10,{ad}<={hd},{hd}-{ad}<=10,{fd}<={hd},{hd}-{fd}<=5,{hp}>0,{ap}>0,{fp}>0),FALSE)'
    result=f'{ap}*{fp}/{hp}*({entitlement(row,ad,hd)})-1'
    live=f'IF(OR(NOT(ISNUMBER(W{row})),W{row}<20000,W{row}>TODAY()+1),"No date",IF({cut}<F{row},"Too new",IF({good},{result},"No history")))'
    return f'IF(AH!$E$4="Stored",IF(ISNUMBER({stored}),{stored},"n.a."),IF(AH!$E$4="Bloomberg",{live},"No source"))'

def mark_array(doc,anchor,end_col,end_row):
    cs=nodes(doc);n=cs[anchor];f=n.find(q('f'));assert f is not None and 'BDH(' in f.text
    col=ci(re.match('[A-Z]+',anchor)[0]);row=int(re.search(r'\d+',anchor)[0]);last=ci(end_col)
    for addr,cell in cs.items():
        c=ci(re.match('[A-Z]+',addr)[0]);r=int(re.search(r'\d+',addr)[0])
        if addr!=anchor and col<=c<=last and row<=r<=end_row:
            assert cell.find(q('f')) is None and value(cell) in ['',None],('Occupied Bloomberg response range',addr)
    f.set('t','array');f.set('ref',f'{anchor}:{end_col}{end_row}')
    # Numeric Excel dates, not locale-formatted strings; daily ascending output.
    if '"DtFmt=D"' not in f.text:
        assert '"Dts=S"' in f.text
        f.text=f.text.replace('"Dts=S"','"Dts=S","DtFmt=D"')

def apply(parts,sheets,root):
    root=Path(root);ah=E.fromstring(parts[sheets['AH']]);ac=nodes(ah)
    if value(ac.get('G4'))=='Charts':return
    cfg=json.loads((root/'data/ah_live_controls.json').read_text())
    put(ah,'D4',v=cfg['quoteLabel'],style=ac['D4'].get('s'))
    put(ah,'G4',v=cfg['chartLabel'],style=ac['D4'].get('s'))
    put(ah,'H4',v=cfg['chartDefault'],style=ac['E4'].get('s'))
    dvs=ah.find(q('dataValidations'));dv=deepcopy(next(d for d in dvs if d.get('sqref')=='E4'))
    dv.set('sqref','H4');dv.set('errorTitle','Choose a chart source');dv.find(q('formula1')).text='"'+','.join(cfg['choices'])+'"';dvs.append(dv);dvs.set('count',str(len(dvs)))
    for addr,n in ac.items():
        f=n.find(q('f'))
        if f is not None and re.fullmatch('P[0-9]+',addr) and int(addr[1:])<=35:f.text=f.text.replace('$E$4','$H$4')
    ac['J24'].find(q('f')).text=ac['J24'].find(q('f')).text.replace('$E$4','$H$4')
    # Quotes set to Stored must never be appended to a live chart as today's tick.
    p12=ac['P12'].find(q('f'));p12.text=p12.text.replace('AND($H$4="Bloomberg",','AND($H$4="Bloomberg",$E$4="Bloomberg",')

    # Change only chart-source routing. Existing data, ranges, charts and caches
    # remain intact; full history is dormant when monitoring live quotes alone.
    for name in ['Live History','Chart Data','AH Reference','AH Compare','AH Compare Live']:
        parts[sheets[name]]=parts[sheets[name]].replace(b'AH!$E$4',b'AH!$H$4')
    for name in ['Live History','AH Compare Live','AH Reference']:
        doc=E.fromstring(parts[sheets[name]])
        for addr,n in list(nodes(doc).items()):
            f=n.find(q('f'))
            if f is None or 'BDH(' not in f.text:continue
            col=ci(re.match('[A-Z]+',addr)[0]);mark_array(doc,addr,ec(col+1),2204)
        parts[sheets[name]]=E.tostring(doc)

    md=E.fromstring(parts[sheets['Market Data']]);mc=nodes(md)
    rows=sorted(int(a[1:]) for a in mc if re.fullmatch('P[0-9]+',a) and int(a[1:])>=3 and value(mc[a]))
    delta=E.fromstring(parts[sheets['AH Delta']]);dc=nodes(delta)
    recent=E.fromstring(parts[sheets['AH Recent']])
    for i,r in enumerate(rows):
        outrow=r+5
        # Both live legs have one transparent, scalar last-price subscription.
        for col,ticker,saved in [('AC','R','AF'),('AD','Q','AG')]:
            put(md,f'{col}{r}',v=value(mc[f'{col}{r}']),f=f'IF(AH!$E$4="Bloomberg",BDP({ticker}{r},"LAST_PRICE"),IF(AH!$E$4="Stored",{saved}{r},""))',style=mc[f'{col}{r}'].get('s'))
        put(delta,f'W{r}',f=normalized_date(f'V{r}'))
        start=5+70*i;stop=start+64
        hd=f"'AH Recent'!$A${start}:$A${stop}";hp=f"'AH Recent'!$B${start}:$B${stop}"
        ad=f"'AH Recent'!$D${start}:$D${stop}";ap=f"'AH Recent'!$E${start}:$E${stop}"
        fd="'AH Recent'!$G$5:$G$69";fp="'AH Recent'!$H$5:$H$69"
        enabled=f'AND(AH!$E$4="Bloomberg",ISNUMBER(W{r}))'
        for a,b in [('A','B'),('D','E')]:mark_array(recent,f'{a}{start}',b,stop)
        horizons=[
            ('AD','U',f'W{r}-1','AE','X','Y','AF','Z','AA','AG','AB','AC'),
            ('D','B',f'W{r}-7','AI','AJ','AK','AL','AM','AN','AO','AP','AQ'),
            ('E','C',f'EDATE(W{r},-1)','AS','AT','AU','AV','AW','AX','AY','AZ','BA')]
        for output,saved,cut,hpos,hdate,hprice,apos,adate,aprice,fpos,fdate,fprice in horizons:
            addresses=[x+str(r) for x in [hpos,hdate,hprice,apos,adate,aprice,fpos,fdate,fprice]]
            hpi,hdi,hvi,api,adi,avi,fpi,fdi,fvi=addresses
            for pos,dt,px,dates,prices,target in [(hpi,hdi,hvi,hd,hp,cut),(api,adi,avi,ad,ap,hdi),(fpi,fdi,fvi,fd,fp,hdi)]:
                scan_cell=put(delta,pos,f=position(dates,prices,target,enabled),v=0)
                # The scan is array arithmetic even though its result is scalar.
                # Explicit CSE metadata also supports pre-dynamic-array Excel.
                scan=scan_cell.find(q('f'))
                scan.set('t','array');scan.set('ref',pos)
                put(delta,dt,f=f'IF({pos}>0,INDEX({dates},{pos}),"")')
                put(delta,px,f=f'IF({pos}>0,INDEX({prices},{pos}),"")')
            old=dc[output+str(r)]
            put(delta,output+str(r),v=value(old),f=reference(r,saved+str(r),cut,*addresses),style=old.get('s'))
        for col,ref in [('G','AD'),('H','D'),('I','E')]:
            old=ac[f'{col}{outrow}'];prior=f"'AH Delta'!{ref}{r}"
            f=f'IF(ISNUMBER(F{outrow}),IF(ISNUMBER({prior}),100*(F{outrow}-{prior}),{prior}),"No quote")'
            put(ah,f'{col}{outrow}',v=value(old),f=f,style=old.get('s'))
    mark_array(recent,'G5','H',69)
    # Cache all existing Stored values unchanged. No prices are fetched here.
    dim=delta.find(q('dimension'));dim.set('ref',f'A1:BA{max(rows)}')
    for name,doc in [('AH',ah),('AH Delta',delta),('AH Recent',recent),('Market Data',md)]:
        sort(doc);parts[sheets[name]]=E.tostring(doc)

def patch(source,dest,root):
    """Stream untouched ZIP parts instead of holding the whole book in RAM."""
    import zipfile
    from patch_peer_workbook import maps
    with zipfile.ZipFile(source) as src:
        _,_,sheets=maps({p:src.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
        names=['AH','AH Delta','AH Recent','Market Data','Live History','Chart Data','AH Reference','AH Compare','AH Compare Live']
        parts={sheets[name]:src.read(sheets[name]) for name in names}
        apply(parts,sheets,root)
        with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as out:
            for info in src.infolist():out.writestr(info,parts[info.filename] if info.filename in parts else src.read(info.filename))
