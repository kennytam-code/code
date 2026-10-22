"""Compact Screener form; explicit cell moves preserve scoring and user inputs."""
import base64,io,json,re,zipfile
from copy import deepcopy
import xml.etree.ElementTree as E
from openpyxl.formula.tokenizer import Tokenizer
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value,put,sort,place,ci,ec
CALC='Calc (scoring engine)'
MOVES={'G5':(CALC,'AX5')}
for r in range(7,15):
    MOVES.update({f'A{r}':('Screener',f'B{r}'),f'B{r}':('Screener',f'D{r}'),f'C{r}':('Screener',f'F{r}'),f'D{r}':(CALC,f'AX{r}')})
for r in [7,8,10,11,12,13,14]:MOVES.update({f'E{r}':('Screener',f'I{r}'),f'F{r}':('Screener',f'K{r}')})
for old,new in [('A16','N7'),('B16','P7'),('A17','N8'),('B17','P8'),('A18','N9'),('B18','P9'),('C17','N10'),('D17','P10'),('C18','N11'),('D18','P11')]:MOVES[old]=('Screener',new)

def rewrite(formula,context,target=None):
    target=target or context
    if context!='Screener' and 'Screener!' not in formula and "'Screener'!" not in formula:return formula
    tokens=Tokenizer('='+formula).items
    for t in tokens:
        if t.type!='OPERAND' or t.subtype!='RANGE':continue
        ref=t.value;sheet=context
        if '!' in ref:
            sh,ref=ref.rsplit('!',1);sheet=sh.strip("'").replace("''", "'")
        m=re.fullmatch(r'(\$?[A-Z]{1,3}\$?\d+)(?::(\$?[A-Z]{1,3}\$?\d+))?',ref)
        if not m:continue
        def point(a):
            dest,addr=MOVES.get(a.replace('$',''),('Screener',a.replace('$',''))) if sheet=='Screener' else (sheet,a.replace('$',''))
            old=re.fullmatch(r'(\$?)[A-Z]+(\$?)\d+',a);col=re.match('[A-Z]+',addr)[0];row=re.search(r'\d+',addr)[0]
            return dest,old[1]+col+old[2]+row
        sh,a=point(m[1]);b=None
        if m[2]:
            sh2,b=point(m[2]);assert sh==sh2,(t.value,sh,sh2)
        prefix='' if sh==target and '!' not in t.value else "'"+sh.replace("'","''")+"'!"
        # Avoid changing spelling of unrelated explicit references.
        if sheet!='Screener' and context==target:continue
        t.value=prefix+a+(':'+b if b else '')
    return ''.join(t.value for t in tokens)

def apply(parts,sheets,root):
    screen=E.fromstring(parts[sheets['Screener']]);sc=nodes(screen)
    if value(sc.get('B4'))=='H code / pipeline':return
    cfg=json.loads((root/'data/screener_desk_layout.json').read_text())
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(cfg['xlsx_base64']))) as z:
        src=E.fromstring(z.read('xl/styles.xml'));_,_,ss=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']});sample=nodes(E.fromstring(z.read(ss['Screener desk'])))
    styles=E.fromstring(parts['xl/styles.xml']);xfs=styles.find(q('cellXfs'));offset={}
    for group in ['fonts','fills','borders']:
        dest=styles.find(q(group));offset[group]=len(dest);dest.extend(deepcopy(list(src.find(q(group)))));dest.set('count',str(len(dest)))
    variants={}
    def style(addr,old=None):
        si=int(sample.get(addr,sample['A7']).get('s','0'));nf=xfs[int(old.get('s','0'))].get('numFmtId','0') if old is not None else '0';key=(si,nf)
        if key not in variants:
            n=deepcopy(src.find(q('cellXfs'))[si])
            for attr,group in [('fontId','fonts'),('fillId','fills'),('borderId','borders')]:n.set(attr,str(int(n.get(attr,'0'))+offset[group]))
            n.set('numFmtId',nf);n.set('xfId','0');n.set('applyNumberFormat','1');variants[key]=len(xfs);xfs.append(n)
        return variants[key]
    moved={};calc=None
    # Rewrite original coordinates once, then relocate; never apply an offset twice.
    for name,path in sheets.items():
        if name not in ['Screener',CALC] and b'Screener!' not in parts[path] and b"Screener'!" not in parts[path]:continue
        doc=screen if name=='Screener' else E.fromstring(parts[path]);changed=False
        for c in doc.iter(q('c')):
            f=c.find(q('f'))
            if f is not None:
                target=MOVES.get(c.get('r'),(name,''))[0] if name=='Screener' else name
                new=rewrite(f.text,name,target)
                if new!=f.text:f.text=new;changed=True
        if name==CALC:calc=doc
        elif name!='Screener' and changed:parts[path]=E.tostring(doc)
    assert calc is not None
    for old,(sheet,addr) in MOVES.items():
        n=deepcopy(sc[old]);n.set('r',addr);moved[(sheet,addr)]=n
    # Rebuild the small form only; comparison table and bottom valuation areas stay.
    data=screen.find(q('sheetData'))
    for row in list(data):
        if 4<=int(row.get('r'))<=18:data.remove(row)
    for r in range(4,19):
        for col in range(1,18):put(screen,ec(col)+str(r),v='',style=style(ec(col)+str(r)))
    for a in ['B5','E5']:
        n=deepcopy(sc[a]);n.set('s',str(style(a,n)));place(screen,n)
    for (sheet,addr),n in moved.items():
        if sheet=='Screener':n.set('s',str(style(addr,n)))
        place(screen if sheet=='Screener' else calc,n)
    for a,t in [('B4','H code / pipeline'),('B6','Company'),('D6','Database'),('F6','Override'),('I6','Selected deal'),('N6','Filters')]:put(screen,a,v=t,style=style(a))
    merges=screen.find(q('mergeCells'))
    for m in list(merges):
        first=int(re.search(r'\d+',m.get('ref'))[0])
        if 3<=first<=18:merges.remove(m)
    for ref in cfg['merges']:E.SubElement(merges,q('mergeCell'),{'ref':ref})
    for ref in ['C42:D42','C43:D43']:
        assert not value(sc.get(ref.split(':')[1])) and (sc.get(ref.split(':')[1]) is None or sc[ref.split(':')[1]].find(q('f')) is None)
        E.SubElement(merges,q('mergeCell'),{'ref':ref})
    merges.set('count',str(len(merges)))
    for dv in screen.iter(q('dataValidation')):
        old=dv.get('sqref');dv.set('sqref',MOVES.get(old,('Screener',old))[1])
        for f in dv:
            if f.text and not f.text.startswith('"'):f.text=rewrite(f.text,'Screener')
    cols=screen.find(q('cols'))
    for i,w in enumerate(cfg['widths'],1):
        n=next((x for x in cols if int(x.get('min'))==int(x.get('max'))==i),None)
        assert n is not None,i;n.set('width',str(w));n.set('customWidth','1')
    for row in screen.find(q('sheetData')):
        r=int(row.get('r'))
        if str(r) in cfg['heights']:
            h=cfg['heights'][str(r)];row.set('ht',str(h));row.set('customHeight','1')
            if h:row.attrib.pop('hidden',None)
            else:row.set('hidden','1')
        if 21<=r<=35:row.set('ht','30');row.set('customHeight','1')
        if r in [42,43] or 53<=r<=61:row.set('ht','36');row.set('customHeight','1')
    # The lower comparison/valuation blocks share these columns; keep labels readable.
    for addr,c in nodes(screen).items():
        r=int(re.search(r'\d+',addr)[0])
        if 42<=r<=61 and ci(re.match('[A-Z]+',addr)[0])<=4:
            xf=deepcopy(xfs[int(c.get('s','0'))]);a=xf.find(q('alignment'))
            if a is None:a=E.SubElement(xf,q('alignment'))
            a.set('wrapText','1');a.set('vertical','center');xfs.append(xf);c.set('s',str(len(xfs)-1))
    xfs.set('count',str(len(xfs)));parts['xl/styles.xml']=E.tostring(styles)
    sort(screen);sort(calc);parts[sheets['Screener']]=E.tostring(screen);parts[sheets[CALC]]=E.tostring(calc)
