"""Explicit, bounded Bloomberg subscriptions; preserve native reply zones/history.

Formula guards are not a terminal performance measurement. See the request audit.
"""
import base64,io,json,re,zipfile
from copy import deepcopy
import xml.etree.ElementTree as E
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value,put,sort

def apply(parts,sheets,root):
    db=E.fromstring(parts[sheets['Database']]);dc=nodes(db)
    if value(dc.get('A2'))=='Valuations':return
    cfg=json.loads((root/'data/request_controls.json').read_text())
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(cfg['xlsx_base64']))) as z:
        src=E.fromstring(z.read('xl/styles.xml'));_,_,ss=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
        sample=nodes(E.fromstring(z.read(ss['Request controls'])))
    styles=E.fromstring(parts['xl/styles.xml']);xfs=styles.find(q('cellXfs'));offset={}
    for group in ['fonts','fills','borders']:
        target=styles.find(q(group));offset[group]=len(target)
        target.extend(deepcopy(list(src.find(q(group)))));target.set('count',str(len(target)))
    def style(addr):
        n=deepcopy(src.find(q('cellXfs'))[int(sample[addr].get('s','0'))])
        for attr,group in [('fontId','fonts'),('fillId','fills'),('borderId','borders')]:n.set(attr,str(int(n.get(attr,'0'))+offset[group]))
        n.set('numFmtId','0');n.set('xfId','0');xfs.append(n);return len(xfs)-1
    label_style,input_style,status_style=style('A2'),style('B2'),style('C2')
    def control(doc,label,default,choices,status):
        merges=doc.find(q('mergeCells'))
        if merges is None:merges=E.SubElement(doc,q('mergeCells'))
        for m in list(merges):
            if set(re.findall(r'\d+',m.get('ref','')))=={'2'}:merges.remove(m)
        E.SubElement(merges,q('mergeCell'),{'ref':'C2:F2'});merges.set('count',str(len(merges)))
        put(doc,'A2',v=label,style=label_style);put(doc,'B2',v=default,style=input_style)
        put(doc,'C2',f=status,v='Screener company + comparisons' if default=='Selected' else 'Off',style=status_style)
        dvs=doc.find(q('dataValidations'))
        if dvs is None:dvs=E.SubElement(doc,q('dataValidations'))
        dv=E.SubElement(dvs,q('dataValidation'),{'type':'list','sqref':'B2','showErrorMessage':'1','errorStyle':'stop','showDropDown':'0'})
        E.SubElement(dv,q('formula1')).text='"'+choices+'"';dvs.set('count',str(len(dvs)))
        row=next(r for r in doc.find(q('sheetData')) if r.get('r')=='2');row.set('ht','25');row.set('customHeight','1');row.attrib.pop('hidden',None)
    control(db,'Valuations','Selected','Selected,All,Off','IF(B2="Selected","Screener company + comparisons",IF(B2="All","All database companies","Off"))')
    verify=E.fromstring(parts[sheets['BBG Verify']])
    control(verify,'Verification','Off','Off,On','IF(B2="On","Bloomberg verification active","Off")')
    for c in verify.iter(q('c')):
        f=c.find(q('f'))
        if f is not None and re.search(r'\b(BDP|BDH|BQL)\(',f.text or ''):f.text='IF($B$2="On",'+f.text+',"")'
    n=sum(1 for a in dc if re.fullmatch(r'A\d+',a) and int(a[1:])>=5 and value(dc[a]))
    val=E.fromstring(parts[sheets['Valuation Data']]);vc=nodes(val);last=8+8*(n-1);hrow=8+8*n;arow=hrow+48
    for i in range(n):
        rr=8+8*i;dr=5+i
        gate=f'AND(Database!$B$2<>"Off",OR(Database!$B$2="All",Database!$B${dr}=SelectedDeal,COUNTIF(Screener!$B$21:$B$35,Database!$B${dr})>0))'
        put(val,'BM'+str(rr),f=gate)
        for col in ['C','F','P','Z','AJ','AU','BD']:
            f=vc[col+str(rr)].find(q('f'));old=f.text
            if col in ['AU','BD']:
                direct=('C' if col=='AU' else 'F')+str(rr)
                old=f'IF(ISNUMBER({direct}),"",{old})'
            f.text=f'IF($BM{rr},{old},"")'
        # No large header scans for an issuer that was not requested.
        for col in ['L','M','X','AH','AR']:
            f=vc[col+str(rr)].find(q('f'));f.text=f'IF($BM{rr},{f.text},"Not requested")'
    # Selected H multiples reuse the issuer block; pipeline-only H codes retain a fallback.
    for r,col,out in [(hrow,'C','L'),(hrow+8,'C','M')]:
        f=vc[col+str(r)].find(q('f'))
        lookup=f'INDEX(${out}$8:${out}${last},MATCH($A${hrow},$A$8:$A${last},0))'
        f.text=f'IF(Database!$B$2="Off","",IFERROR({lookup},{f.text}))'
    for addr in ['AU'+str(hrow),'BD'+str(hrow+8)]:
        r=int(re.search(r'\d+',addr)[0]);f=vc[addr].find(q('f'))
        f.text=f'IF(Database!$B$2="Off","",IF(OR(ISNUMBER(C{r}),COUNTIF($A$8:$A${last},$A${hrow})>0),"",{f.text}))'
    for addr,c in vc.items():
        r=int(re.search(r'\d+',addr)[0]);f=c.find(q('f'))
        if f is None or r<arow:continue
        if re.search(r'\b(BDP|BQL)\(',f.text):
            if addr.startswith(('AU','BD')):f.text=f'IF(ISNUMBER(C{r}),"",{f.text})'
            f.text=f'IF(Database!$B$2="Off","",{f.text})'
    for r in range(hrow,arow+33,8):
        c=vc.get('L'+str(r))
        if c is not None and c.find(q('f')) is not None:c.find(q('f')).text='IF(Database!$B$2="Off","Not requested",'+c.find(q('f')).text+')'
    # The selected-company price/capitalisation requests also honour Off.
    sc=E.fromstring(parts[sheets['Screener']])
    for c in sc.iter(q('c')):
        f=c.find(q('f'))
        if f is not None and re.search(r'\b(BDP|BDH)\(',f.text):f.text='IF(Database!$B$2="Off","",'+f.text+')'
    # A/H recent changes: every roster pair, and one common FX response.
    md=nodes(E.fromstring(parts[sheets['Market Data']]))
    recent=E.fromstring(parts[sheets['AH Recent']]);recent.find(q('sheetData')).clear()
    common='"Dts=S","Dir=V","Sort=A","Days=T","Per=cd"'
    raw=common+',"UseDPDF=N","CshAdjNormal=N","CshAdjAbnormal=N","CapChg=N"'
    rows=sorted(int(a[1:]) for a in md if re.fullmatch(r'P\d+',a) and int(a[1:])>=3 and value(md[a]))
    for i,r in enumerate(rows):
        start=5+70*i
        for outcol,incol in [('A','Q'),('D','R')]:
            put(recent,outcol+str(start),f=f'IF(AH!$E$4<>"Bloomberg","",BDH(\'Market Data\'!${incol}${r},"PX_LAST",TODAY()-55,TODAY(),{raw}))')
    put(recent,'G5',f=f'IF(AH!$E$4<>"Bloomberg","",BDH("CNYHKD Curncy","PX_LAST",TODAY()-55,TODAY(),{common}))')
    delta=E.fromstring(parts[sheets['AH Delta']])
    for f in delta.iter(q('f')):
        for col in ['G','H']:f.text=re.sub(r"'AH Recent'!\$"+col+r'\$\d+:\$'+col+r'\$\d+',f"'AH Recent'!${col}$5:${col}$69",f.text)
    # Two scalar previous-close subscriptions, not four nested BDP occurrences.
    peer=E.fromstring(parts[sheets['Peer Chart']]);pc=nodes(peer)
    for r,inputcol in [(9,'O'),(10,'R')]:
        call=f'BDP(IFERROR(TEXT(VALUE(${inputcol}$4),"0")&" HK Equity",""),"PX_YEST_CLOSE")'
        f=pc['T'+str(r)].find(q('f'));assert f.text.count(call)==2
        f.text=f.text.replace(call,'$Z$'+str(r))
        put(peer,'Z'+str(r),f=f'IF($U$4="Bloomberg",IFERROR({call},""),"")')
    # One aggregate per live response, instead of 61,612 repeated range scans.
    compare=E.fromstring(parts[sheets['AH Compare']])
    for col,helper in [('A','AK'),('J','AL'),('S','AM'),('AB','AN')]:
        rg=f"'AH Compare Live'!${col}$5:${col}$2204"
        replacements={f'COUNT({rg})':f'${helper}$2',f'MIN({rg})':f'${helper}$3',f'MAX({rg})':f'${helper}$4'}
        for f in compare.iter(q('f')):
            for old,new in replacements.items():f.text=f.text.replace(old,new)
        for r,op in [(2,'COUNT'),(3,'MIN'),(4,'MAX')]:put(compare,helper+str(r),f=f'{op}({rg})')
        # A sorted response's first numeric date position also stays invariant.
        first=f'MATCH(${helper}$3,{rg},0)'
        for f in compare.iter(q('f')):f.text=f.text.replace(first,f'${helper}$5')
        put(compare,helper+'5',f=f'IFERROR({first},0)')
    for name,doc in [('Database',db),('BBG Verify',verify),('Valuation Data',val),('Screener',sc),('AH Recent',recent),('AH Delta',delta),('Peer Chart',peer),('AH Compare',compare)]:
        sort(doc);parts[sheets[name]]=E.tostring(doc)
    xfs.set('count',str(len(xfs)));parts['xl/styles.xml']=E.tostring(styles)
