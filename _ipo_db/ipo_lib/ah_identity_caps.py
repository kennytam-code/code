"""Add A/H identities, class market caps and an independent live code checker.

Native package edit: preserve chart series, Bloomberg-owned reply areas and
all unrelated worksheets. M60 remains the user's H-code input.
"""
import re
from copy import deepcopy
import xml.etree.ElementTree as E
from openpyxl.formula.tokenizer import Tokenizer
from patch_peer_workbook import q
from reflow_monitors import nodes, value, put, place, sort, ci, ec, drawing_path, xd
from sector_monitor_release import relpath, target

CAP_FIELD = 'CURRENT_MARKET_CAP_SHARE_CLASS'
ROSTER = {1:2, 2:3, 3:4, 4:5, 5:8, 6:9, 7:10, 8:11, 9:12}
CHECKER = {'M60':'M60','M61':'O60','M62':'Q60','M64':'P64',
           'M65':'P65','M66':'M62','M68':'P67','M69':'P68',
           'M70':'P69','M72':'P73','M73':'P75'}

def address(addr, end):
    m=re.fullmatch(r'(\$?)([A-Z]+)(\$?)(\d+)',addr)
    if not m:return addr
    ca,c,ra,r=m.groups();r=int(r);n=ci(c);plain=c+str(r)
    if plain in CHECKER:out=CHECKER[plain]
    elif 7<=r<=end and n<=9:out=ec(ROSTER[n])+str(r)
    elif n>=10 and r<=56:out=ec(n+3)+str(r)
    elif n>=16:out=ec(n+3)+str(r)
    elif r>end and 5<=n<=9:out=ec(ROSTER[n])+str(r)
    else:out=plain
    a=re.fullmatch(r'([A-Z]+)(\d+)',out)
    return ca+a[1]+ra+a[2]

def formula(text,end,local=False):
    """Translate only range tokens, never function names or quoted strings."""
    tokens=Tokenizer('='+text).items
    for t in tokens:
        if t.type!='OPERAND' or t.subtype!='RANGE':continue
        prefix='';ref=t.value
        if '!' in ref:
            prefix,ref=ref.rsplit('!',1)
            if prefix.strip("'")!='AH':continue
            prefix+='!'
        elif not local:continue
        t.value=prefix+':'.join(address(a,end) for a in ref.split(':'))
    return ''.join(t.value for t in tokens)

def apply(parts,sheets,root):
    ah=E.fromstring(parts[sheets['AH']]);old=nodes(ah)
    if value(old.get('A7'))=='Company':return
    assert value(old.get('G7'))=='1D Δ (pp)'
    end=max(int(a[1:]) for a in old if re.fullmatch(r'B\d+',a) and 8<=int(a[1:])<1000 and old[a].find(q('f')) is not None and "'Market Data'!P" in old[a].find(q('f')).text)
    mend=end-5
    # Relocate the requested roster, chart controls, existing helpers and summaries.
    for row in ah.find(q('sheetData')):
        for c in list(row):
            a=c.get('r');r=int(re.search(r'\d+',a)[0]);col=ci(re.match('[A-Z]+',a)[0])
            if r>=57 and 10<=col<=15:row.remove(c);continue
            c.set('r',address(a,end))
            f=c.find(q('f'))
            if f is not None:f.text=formula(f.text,end,True)
    # Keep every dependent AH reference aligned, including hidden chart builds.
    for p,raw in list(parts.items()):
        if p==sheets['AH'] or not p.endswith('.xml') or not (b'AH!' in raw or b"'AH'!" in raw):continue
        d=E.fromstring(raw);changed=False
        for n in d.iter():
            if n.tag.split('}')[-1] not in ['f','definedName'] or not n.text:continue
            if 'AH!' not in n.text and "'AH'!" not in n.text:continue
            new=formula(n.text,end)
            if new!=n.text:n.text=new;changed=True
        if changed:parts[p]=E.tostring(d)
    merges=ah.find(q('mergeCells'))
    for n in list(merges):
        first=n.get('ref').split(':')[0];r=int(re.search(r'\d+',first)[0]);co=ci(re.match('[A-Z]+',first)[0])
        if 57<=r<=76 and co>=10:merges.remove(n);continue
        n.set('ref',':'.join(address(a,end) for a in n.get('ref').split(':')))
    for cf in list(ah.findall(q('conditionalFormatting'))):
        if cf.get('sqref')=='M72':ah.remove(cf);continue
        cf.set('sqref',' '.join(':'.join(address(a,end) for a in area.split(':')) for area in cf.get('sqref').split()))
        for f in cf.iter(q('formula')):f.text=formula(f.text,end,True)
    for dv in ah.iter(q('dataValidation')):
        dv.set('sqref',' '.join(':'.join(address(a,end) for a in area.split(':')) for area in dv.get('sqref').split()))
        for f in list(dv):
            if f.text and not f.text.startswith('"'):f.text=formula(f.text,end,True)
    for h in ah.iter(q('hyperlink')):
        h.set('ref',address(h.get('ref'),end))
    # Chart geometry moves by three columns; data, axes and series are untouched.
    dp=drawing_path(parts,sheets['AH']);dr=E.fromstring(parts[dp])
    for a in dr:
        for tag in ['from','to']:
            x=a.find(xd(tag))
            if x is not None:
                col=x.find(xd('col'))
                col.text=str(int(col.text)+3)
    parts[dp]=E.tostring(dr)
    # Legacy notes must stay attached to their original premium metrics.
    rels=E.fromstring(parts[relpath(sheets['AH'])])
    for rel in rels:
        path=target(sheets['AH'],rel.get('Target'))
        if rel.get('Type').endswith('/comments'):
            d=E.fromstring(parts[path])
            for note in d.iter(q('comment')):note.set('ref',address(note.get('ref'),end))
            parts[path]=E.tostring(d)
        elif rel.get('Type').endswith('/vmlDrawing'):
            d=E.fromstring(parts[path]);x=lambda n:'{urn:schemas-microsoft-com:office:excel}'+n
            for client in d.iter(x('ClientData')):
                col=client.find(x('Column'));row=client.find(x('Row'))
                if col is None or row is None:continue
                oldcol=int(col.text);newaddr=address(ec(oldcol+1)+str(int(row.text)+1),end)
                newcol=ci(re.match('[A-Z]+',newaddr)[0])-1
                col.text=str(newcol);row.text=str(int(re.search(r'\d+',newaddr)[0])-1)
                anchor=client.find(x('Anchor'))
                if anchor is not None:
                    nums=[int(v.strip()) for v in anchor.text.split(',')]
                    nums[0]+=newcol-oldcol;nums[4]+=newcol-oldcol;anchor.text=', '.join(map(str,nums))
            parts[path]=E.tostring(d)
    # Use existing desk styles, adding only a neutral market-cap number format.
    styles=E.fromstring(parts['xl/styles.xml']);xfs=styles.find(q('cellXfs'));fmts=styles.find(q('numFmts'))
    nid=max([163]+[int(n.get('numFmtId')) for n in fmts])+1
    E.SubElement(fmts,q('numFmt'),{'numFmtId':str(nid),'formatCode':'#,##0.0;(#,##0.0);0.0'})
    fmts.set('count',str(len(fmts)))
    capstyle=deepcopy(xfs[int(old['F8'].get('s'))]);capstyle.set('numFmtId',str(nid));cs=len(xfs);xfs.append(capstyle)
    name_style=deepcopy(xfs[int(old['D8'].get('s'))]);align=name_style.find(q('alignment'))
    if align is not None:align.set('wrapText','0');align.set('shrinkToFit','0')
    ns=len(xfs);xfs.append(name_style)
    head=deepcopy(xfs[int(old['G7'].get('s'))]);ha=head.find(q('alignment'))
    if ha is None:ha=E.SubElement(head,q('alignment'))
    ha.set('wrapText','1');ha.set('vertical','center');hs=len(xfs);xfs.append(head)
    xfs.set('count',str(len(xfs)));parts['xl/styles.xml']=E.tostring(styles)
    headers=['Company','A code','H code','Sector','Subsector','A cap\nCNY m','H cap\nHKD m','IPO\nprem.','Now\nprem.','1D Δ\n(pp)','7D Δ\n(pp)','1M Δ\n(pp)']
    market=nodes(E.fromstring(parts[sheets['Market Data']]))
    for i,title in enumerate(headers,1):put(ah,ec(i)+'7',v=title,style=hs)
    for r in range(8,end+1):
        j=r-5
        put(ah,'A'+str(r),v=value(market['S'+str(j)]),f=f"'Market Data'!S{j}",style=ns)
        for col,ticker in [('F','R'),('G','Q')]:
            put(ah,col+str(r),v='—',f=f'IF($E$4<>"Bloomberg","—",IFERROR(BDP(\'Market Data\'!${ticker}{j},"{CAP_FIELD}"),"Unavailable"))',style=cs)
    for p,raw in list(parts.items()):
        if not p.startswith('xl/tables/') or not p.endswith('.xml'):continue
        t=E.fromstring(raw)
        if t.get('name')!='AHLivePairs':continue
        t.set('ref',f'A7:L{end}');t.find(q('autoFilter')).set('ref',f'A7:L{end}')
        cols=t.find(q('tableColumns'));cols[:]=[]
        for i,title in enumerate(headers,1):E.SubElement(cols,q('tableColumn'),{'id':str(i),'name':title})
        cols.set('count',str(len(cols)));parts[p]=E.tostring(t)
    # The independent calculator is always live. It does not start BDH histories.
    def merge(a):E.SubElement(merges,q('mergeCell'),{'ref':a})
    def add(a,v=None,f=None,source='M68'):
        return put(ah,a,v=v,f=f,style=old[source].get('s'))
    add('M58','A/H live price check',source='J58');merge('M58:R58')
    for a,label in [('M59','H code'),('O59','A code override'),('Q59','IPO price override · HKD')]:
        add(a,label,source='J60');merge(a+':'+ec(ci(a[:-2])+1)+'59')
    for olda,newa in [('M60','M60'),('M61','O60'),('M62','Q60')]:
        c=deepcopy(old[olda]);c.set('r',newa);place(ah,c);merge(newa+':'+ec(ci(re.match('[A-Z]+',newa)[0])+1)+'60')
    labels={64:'A code',65:'H IPO price · HKD',67:'A live price · CNY',68:'CNY / HKD',69:'A live price · HKD',70:'H live price · HKD',72:'A/H premium now',73:'A premium vs H IPO',75:'A quote date',76:'H quote date'}
    for r,label in labels.items():
        add('M'+str(r),label,source='J72' if r in [72,73] else 'J68');merge(f'M{r}:O{r}');merge(f'P{r}:R{r}')
    for olda,newa in [('M64','P64'),('M65','P65'),('M66','M62')]:
        c=deepcopy(old[olda]);c.set('r',newa);f=c.find(q('f'))
        if f is not None:f.text=formula(f.text,end,True)
        place(ah,c)
    merge('M62:R62')
    original_a=nodes(ah)['S79'].find(q('f')).text
    add('S79',value(old['P79']),f=f'IF($S$82>0,INDEX(\'Market Data\'!$R$3:$R${mend},$S$82),{original_a})')
    company=nodes(ah)['M62']
    add('S85',value(company),f=company.find(q('f')).text,source='M66')
    add('M62',value(company),f=f'IF($S$78="","",IF($S$82>0,INDEX(\'Market Data\'!$S$3:$S${mend},$S$82),IF($S$85<>"",$S$85,BDP($S$84,"NAME"))))',source='M66')
    add('S84',f='IF($S$78="","",TEXT(VALUE($M$60),"0")&" HK Equity")')
    add('P67','Awaiting Bloomberg',f=f'IF($S$81="","Enter A code",IF(AND($E$4="Bloomberg",$S$83),INDEX(\'Market Data\'!$AC$3:$AC${mend},$S$82),BDP($S$81,"LAST_PRICE")))')
    add('P68','Awaiting Bloomberg',f='IF($S$78="","",IF($E$4="Bloomberg",\'Market Data\'!$E$2,BDP("CNYHKD Curncy","LAST_PRICE")))',source='M69')
    add('P69','Awaiting prices',f='IF(AND(ISNUMBER(P67),P67>0,ISNUMBER(P68),P68>0),P67*P68,"Awaiting prices")',source='M70')
    add('P70','Awaiting Bloomberg',f=f'IF($S$84="","Enter H code",IF(AND($E$4="Bloomberg",$S$82>0),INDEX(\'Market Data\'!$AD$3:$AD${mend},$S$82),BDP($S$84,"LAST_PRICE")))')
    add('P72','Awaiting prices',f='IF(AND(ISNUMBER(P69),P69>0,ISNUMBER(P70),P70>0),P69/P70-1,"Awaiting prices")',source='M72')
    add('P73','Awaiting prices',f='IF(AND(ISNUMBER(P69),P69>0,ISNUMBER(P65),P65>0),P69/P65-1,"Awaiting prices")',source='M72')
    add('P75','Awaiting Bloomberg',f='IF($S$81="","",BDP($S$81,"LAST_UPDATE_DT"))',source='M73')
    add('P76','Awaiting Bloomberg',f=f'IF($S$84="","",IF(AND($E$4="Bloomberg",$S$82>0),INDEX(\'AH Delta\'!$V$3:$V${mend},$S$82),BDP($S$84,"LAST_UPDATE_DT")))',source='M73')
    # Update links and extend summary labels across the wider identity columns.
    add('O5','Live price check',f='HYPERLINK("#\'AH\'!M58","Live price check")',source='L5')
    for n in merges:
        a=n.get('ref')
        if re.fullmatch(r'A\d+:D\d+',a):n.set('ref',a.replace(':D',':G'))
    cols=ah.find(q('cols'));cols[:]=[]
    widths=[28,10,9,16,28,14,14,11,11,11,11,11]+[16]*6
    for i,w in enumerate(widths,1):E.SubElement(cols,q('col'),{'min':str(i),'max':str(i),'width':str(w),'customWidth':'1'})
    E.SubElement(cols,q('col'),{'min':'19','max':'24','width':'12','customWidth':'1','hidden':'1'})
    for pane in ah.iter(q('pane')):
        if pane.get('xSplit')=='2':pane.set('xSplit','3');pane.set('topLeftCell','D8')
    for row in ah.find(q('sheetData')):
        r=int(row.get('r'))
        if r==7:row.set('ht','38')
        if 58<=r<=76:row.set('ht','23')
        if r==59:row.set('ht','29')
    for cf in list(ah.findall(q('conditionalFormatting'))):
        if cf.get('sqref')==f'I8:L{end}':
            for r in [72,73]:
                n=deepcopy(cf);n.set('sqref',f'P{r}')
                for rule in n:
                    rule.set('priority',str(100+r*2+int(rule.get('priority'))));rule.find(q('formula')).text=rule.find(q('formula')).text.replace('I8',f'P{r}')
                ah.append(n)
            break
    # Handle an unavailable add-in at the external call boundary, not by
    # replacing failed calculations or missing prices with numeric zero.
    for a,c in nodes(ah).items():
        r=int(re.search(r'\d+',a)[0]);col=ci(re.match('[A-Z]+',a)[0]);f=c.find(q('f'))
        if r>=58 and col>=13 and f is not None and 'BDP(' in f.text:
            f.text='IFERROR('+f.text+',"BBG unavailable")'
    merges.set('count',str(len(merges)));sort(ah);parts[sheets['AH']]=E.tostring(ah)
