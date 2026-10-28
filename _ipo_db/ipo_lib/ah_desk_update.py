"""AH daily/subsector monitor and independent code-only IPO-price checker.

Native graft of a bounded Artifact layout. No historical query belongs to the
manual IPO checker. Screener valuations retain their own selected-company key.
"""
import base64,io,json,posixpath,re,zipfile
from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as E
from patch_peer_workbook import maps,q,R
from reflow_monitors import nodes,value,put,place,sort,ci,ec,serial
from sector_monitor_release import relpath,target
from ah_basis import review_for,adjusted_premium
CALC='Calc (scoring engine)'

def num(c):
    v=value(c)
    if c is None or c.get('t') in ['str','inlineStr','s','e'] or v in ['',None]:return None
    return float(v)

def apply(parts,sheets,root):
    root=Path(root);ah=E.fromstring(parts[sheets['AH']]);ac=nodes(ah)
    if value(ac.get('G7')) in ['1D change (pp)','1D Δ (pp)']:return
    cfg=json.loads((root/'data/ah_update_layout.json').read_text())
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(cfg['xlsx_base64']))) as z:
        src=E.fromstring(z.read('xl/styles.xml'));_,_,sm=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']});sample=nodes(E.fromstring(z.read(sm['AH desk'])))
    st=E.fromstring(parts['xl/styles.xml']);xfs=st.find(q('cellXfs'));off={}
    for group in ['fonts','fills','borders']:
        dest=st.find(q(group));off[group]=len(dest);dest.extend(deepcopy(list(src.find(q(group)))));dest.set('count',str(len(dest)))
    fmts=st.find(q('numFmts'));nextid=max([163]+[int(n.get('numFmtId')) for n in fmts])+1;fmtmap={}
    for n in src.find(q('numFmts')):
        copy=deepcopy(n);fmtmap[int(n.get('numFmtId'))]=nextid;copy.set('numFmtId',str(nextid));fmts.append(copy);nextid+=1
    fmts.set('count',str(len(fmts)));variants={}
    def style(source,old=None,format_code=None):
        si=int(sample[source].get('s','0'));base=src.find(q('cellXfs'))[si];nf=xfs[int(old.get('s','0'))].get('numFmtId','0') if old is not None else str(fmtmap.get(int(base.get('numFmtId','0')),int(base.get('numFmtId','0'))))
        if format_code:
            found=next((n.get('numFmtId') for n in fmts if n.get('formatCode')==format_code),None)
            if found is None:
                found=str(max([163]+[int(n.get('numFmtId')) for n in fmts])+1);E.SubElement(fmts,q('numFmt'),{'numFmtId':found,'formatCode':format_code});fmts.set('count',str(len(fmts)))
            nf=found
        key=(si,nf)
        if key not in variants:
            n=deepcopy(base)
            for attr,g in [('fontId','fonts'),('fillId','fills'),('borderId','borders')]:n.set(attr,str(int(n.get(attr,'0'))+off[g]))
            n.set('numFmtId',nf);n.set('xfId','0');variants[key]=len(xfs);xfs.append(n)
        return variants[key]
    meta=json.loads((root/'data/desk_chart_data.json').read_text())['pairs'];end=7+len(meta);mend=2+len(meta)
    from market_universe import histories
    records={r['code']:r for r in histories(root)['pairs']}
    delta=E.fromstring(parts[sheets['AH Delta']]);dc=nodes(delta)
    for j,m in enumerate(meta):
        r=j+8;idx=j+3;rec=records[m['code']];points={x[0]:x for x in rec.get('history',[])};hs=rec.get('h_history',[])
        prev=points.get(hs[-2][0]) if len(hs)>1 and hs[-1][0]==rec.get('latest_date') else None
        ref=adjusted_premium(review_for(m['code'],root),prev) if prev else None
        put(delta,f'U{idx}',v=ref)
        put(delta,f'V{idx}',f=f'IF(AH!$E$4="Bloomberg",BDP(\'Market Data\'!$Q{idx},"LAST_UPDATE_DT"),"")')
        put(delta,f'W{idx}',f=f'IFERROR(IF(AH!$E$4<>"Bloomberg","",IF(ISNUMBER(V{idx}),INT(V{idx}),DATEVALUE(V{idx}))),"")')
        start=5+j*70;stop=start+64
        hr=f"'AH Recent'!$A${start}:$A${stop}";hp=f"'AH Recent'!$B${start}:$B${stop}";ar=f"'AH Recent'!$D${start}:$D${stop}";ap=f"'AH Recent'!$E${start}:$E${stop}";fr="'AH Recent'!$G$5:$G$69";fp="'AH Recent'!$H$5:$H$69"
        for out,dates,prices,cut in [('X',hr,hp,f'W{idx}-1'),('Z',ar,ap,f'X{idx}'),('AB',fr,fp,f'X{idx}')]:
            put(delta,f'{out}{idx}',f=f'IFERROR(IF(OR(AH!$E$4<>"Bloomberg",NOT(ISNUMBER(W{idx}))),"",LOOKUP(2,1/ISNUMBER({dates})/ISNUMBER({prices})/({prices}>0)/({dates}<=({cut})),{dates})),"")')
        for out,dates,prices,dt in [('Y',hr,hp,'X'),('AA',ar,ap,'Z'),('AC',fr,fp,'AB')]:
            put(delta,f'{out}{idx}',f=f'IFERROR(IF(AH!$E$4<>"Bloomberg","",INDEX({prices},MATCH({dt}{idx},{dates},0))),"")')
        fa='*'.join(f'IF(AND(ISNUMBER({ex}{idx}),Z{idx}>={ex}{idx}),{factor}{idx},1)' for ex,factor in [('K','R'),('M','S'),('P','T')]);fh='*'.join(f'IF(AND(ISNUMBER({ex}{idx}),X{idx}>={ex}{idx}),{factor}{idx},1)' for ex,factor in [('J','R'),('L','S'),('O','T')])
        put(delta,f'AD{idx}',v=ref,f=f'IFERROR(IF(AH!$E$4="Stored",IF(ISNUMBER(U{idx}),U{idx},""),IF(AND(ISNUMBER(W{idx}),ISNUMBER(X{idx}),ISNUMBER(Z{idx}),ISNUMBER(AB{idx}),X{idx}>=F{idx},X{idx}<W{idx},X{idx}-Z{idx}<=10,X{idx}-AB{idx}<=5,Y{idx}>0,AA{idx}>0,AC{idx}>0),AA{idx}*AC{idx}/Y{idx}*({fa})/({fh})-1,"")),"")')
        # Only the old delta columns move. Chart and helper coordinates stay put.
        for old,new in [('H','I'),('G','H')]:
            n=deepcopy(ac[old+str(r)]);n.set('r',new+str(r));place(ah,n)
        current=num(ac['F'+str(r)])
        put(ah,'G'+str(r),v=100*(current-ref) if current is not None and ref is not None else '',f=f'IFERROR(IF(AND(ISNUMBER(F{r}),ISNUMBER(\'AH Delta\'!AD{idx})),100*(F{r}-\'AH Delta\'!AD{idx}),""),"")',style=ac['G'+str(r)].get('s'))
        # Six digits are meaningful, including the leading zero of Shenzhen codes.
        ac['A'+str(r)].set('s',str(style('A3',format_code='000000')))
    for i,title in enumerate(['A code','H code','Sector','Subsector','IPO prem.','Now prem.','1D Δ (pp)','7D Δ (pp)','1M Δ (pp)'],1):put(ah,ec(i)+'7',v=title,style=style(ec(i)+'2'))
    for col in ah.find(q('cols')):
        if col.get('min')=='9' and col.get('max')=='9':col.set('width','12');col.attrib.pop('hidden',None)
    for p in list(parts):
        if p.startswith('xl/tables/') and p.endswith('.xml'):
            tab=E.fromstring(parts[p])
            if tab.get('name')!='AHLivePairs':continue
            tab.set('ref',f'A7:I{end}');af=tab.find(q('autoFilter'))
            if af is not None:af.set('ref',f'A7:I{end}')
            tc=tab.find(q('tableColumns'));tc[:]=[]
            for i in range(1,10):E.SubElement(tc,q('tableColumn'),{'id':str(i),'name':value(nodes(ah)[ec(i)+'7'])})
            tc.set('count','9');parts[p]=E.tostring(tab)
    # Remove the old right-side sector block, which becomes the compact checker.
    for row in ah.find(q('sheetData')):
        for c in list(row):
            a=c.get('r');r=int(re.search(r'\d+',a)[0]);col=ci(re.match('[A-Z]+',a)[0])
            if 57<=r<=78 and 10<=col<=15:row.remove(c)
    merges=ah.find(q('mergeCells'))
    for n in list(merges):
        a=n.get('ref').split(':')[0]
        if 57<=int(re.search(r'\d+',a)[0])<=78 and ci(re.match('[A-Z]+',a)[0])>=10:merges.remove(n)
    for cf in list(ah.findall(q('conditionalFormatting'))):
        if re.search(r'[J-O](?:5[7-9]|[6-7]\d)',cf.get('sqref','')):ah.remove(cf)
        elif cf.get('sqref')==f'G8:H{end}':cf.set('sqref',f'G8:I{end}')
    def merge(a):E.SubElement(merges,q('mergeCell'),{'ref':a})
    def add(addr,source,v=None,f=None,fmt=None):return put(ah,addr,v=v,f=f,style=style(source,format_code=fmt))
    # Summary changes average each available pair change, not two changing sets.
    sectors=sorted({m['sector'] if 'sector' in m else value(ac['C'+str(j+8)]) for j,m in enumerate(meta)})
    rowsnow=nodes(ah);sector_start=end+4;sub_start=sector_start+len(sectors)+5
    for title,start,groups,criterion in [('Sector averages',sector_start,sectors,'C'),('Subsector averages',sub_start,sorted({value(ac['D'+str(r)]) for r in range(8,end+1)}),'D')]:
        add('A'+str(start),'A6',title);merge(f'A{start}:I{start}')
        for c,t in [('A','Sector' if criterion=='C' else 'Subsector'),('E','Pairs'),('F','Premium now'),('G','1D Δ (pp)'),('H','7D Δ (pp)'),('I','1M Δ (pp)')]:add(c+str(start+1),'A7',t)
        merge(f'A{start+1}:D{start+1}')
        for r,group in enumerate(groups,start+2):
            members=[i for i in range(8,end+1) if value(ac[criterion+str(i)])==group]
            add('A'+str(r),'A8',group);merge(f'A{r}:D{r}');add('E'+str(r),'E8',len(members),f'COUNTIF(${criterion}$8:${criterion}${end},A{r})')
            for c in 'FGHI':
                vs=[num(rowsnow.get(c+str(i))) for i in members];vs=[v for v in vs if v is not None]
                add(c+str(r),'F8' if c=='F' else 'G8',sum(vs)/len(vs) if vs else '',f'IFERROR(AVERAGEIF(${criterion}$8:${criterion}${end},$A{r},${c}$8:${c}${end}),"")')
    add('J5','M4','Group averages ↓',f'HYPERLINK("#\'AH\'!A{sector_start}","Group averages ↓")');merge('J5:K5')
    add('L5','M4','IPO price check ↓','HYPERLINK("#\'AH\'!J58","IPO price check ↓")');merge('L5:O5')
    add('J58','J2','A price vs H IPO price');merge('J58:O58')
    deals=json.loads((root/'data/deals.json').read_text())['deals'];default=max((d for d in deals if d.get('a_share_code')),key=lambda d:d['ipo_date'],default=None)
    # Blank overrides preserve automatic pairing when the H code changes.
    labels={60:'H code',61:'A code override',62:'IPO price override · HKD',64:'A code',65:'H IPO price · HKD',66:'Company',68:'A price · CNY',69:'CNY / HKD',70:'A price · HKD',72:'A premium vs H IPO',73:'A quote date'}
    for r,label in labels.items():
        merge(f'J{r}:L{r}');merge(f'M{r}:O{r}');add('J'+str(r),'J11' if r==72 else 'J4',label);add('M'+str(r),'M4' if r<=62 else 'M11' if r==72 else 'M8','')
    code=default['code'] if default else meta[0]['code'];add('M60','M4',int(code),fmt='0000');add('M61','M5','',fmt='000000');add('M62','M6','',fmt='0.00')
    dbend=len(deals)+4
    pipe=E.fromstring(parts[sheets['Pipeline']]);pc=nodes(pipe);pipe_end=max([6]+[int(a[1:]) for a in pc if re.fullmatch(r'A\d+',a) and int(a[1:])>=6 and value(pc[a])]);pe=max(6,pipe_end)
    def lookup(col,pcoll):return f'IFERROR(INDEX(Database!${col}$5:${col}${dbend},MATCH($P$78,Database!$A$5:$A${dbend},0)),IFERROR(INDEX(Pipeline!${pcoll}$6:${pcoll}${pe},MATCH($P$78,Pipeline!$A$6:$A${pe},0)),""))'
    put(ah,'P78',f='IFERROR(IF(AND(ISNUMBER(VALUE(M60)),VALUE(M60)>0,VALUE(M60)<100000,INT(VALUE(M60))=VALUE(M60)),TEXT(VALUE(M60),"0000"),""),"")',v=code)
    put(ah,'P79',f=lookup('BQ','V'),v=default.get('a_share_code','') if default else '')
    add('M64','M8',int(default['a_share_code'].split('.')[0]) if default else '',f'IFERROR(IF($M$61<>"",IF(AND(VALUE($M$61)>0,VALUE($M$61)<1000000,INT(VALUE($M$61))=VALUE($M$61)),VALUE($M$61),""),IF($P$79="","",VALUE(LEFT($P$79,6)))),"")',fmt='000000')
    put(ah,'P80',f=lookup('M','I'),v=default.get('final_price','') if default else '')
    add('M65','M8',default.get('final_price','') if default else '',f'IFERROR(IF($M$62<>"",IF(AND(ISNUMBER($M$62),$M$62>0),$M$62,""),IF(AND(ISNUMBER($P$80),$P$80>0),$P$80,"")),"")',fmt='0.00')
    add('M66','M7',default.get('name','') if default else '',lookup('B','B'))
    put(ah,'P81',f='IF(M64="","",TEXT(M64,"000000")&" CH Equity")',v=default['a_share_code'].split('.')[0]+' CH Equity' if default else '')
    put(ah,'P82',f=f'IFERROR(MATCH($P$78,\'Market Data\'!$P$3:$P${mend},0),0)',v=next((i+1 for i,m in enumerate(meta) if m['code']==code),0))
    put(ah,'P83',f=f'IFERROR(AND($P$82>0,$P$81=INDEX(\'Market Data\'!$R$3:$R${mend},$P$82)),FALSE)',v=1)
    rec=records.get(code,{});a=rec.get('latest_a_cny');fx=rec.get('latest_fx');offer=default.get('final_price') if default else None
    add('M68','M8',a or '',f'IFERROR(IF($P$81="","",IF($E$4="Bloomberg",BDP($P$81,"LAST_PRICE"),IF($P$83,INDEX(\'Market Data\'!$AF$3:$AF${mend},$P$82),""))),"")',fmt='0.00')
    add('M69','M9',fx or '',f'IFERROR(IF($E$4="Bloomberg",\'Market Data\'!$E$2,IF($P$83,INDEX(\'Market Data\'!$AH$3:$AH${mend},$P$82),"")),"")',fmt='0.0000')
    add('M70','M10',a*fx if a and fx else '',f'IFERROR(IF(AND(ISNUMBER(M68),M68>0,ISNUMBER(M69),M69>0),M68*M69,""),"")',fmt='0.00')
    add('M72','M11',a*fx/offer-1 if a and fx and offer else '',f'IFERROR(IF(AND(ISNUMBER(M70),M70>0,ISNUMBER(M65),M65>0),M70/M65-1,""),"")',fmt='0.0%;(0.0%);0.0%')
    add('M73','M12',serial(rec.get('latest_a_date')) or '',f'IFERROR(IF($P$81="","",IF($E$4="Bloomberg",BDP($P$81,"LAST_UPDATE_DT"),IF($P$83,INDEX(\'Market Data\'!$AI$3:$AI${mend},$P$82),""))),"")',fmt='dd mmm yyyy')
    # Numeric input checks still accept typed leading zeros. No suffix required.
    dvs=ah.find(q('dataValidations'))
    if dvs is None:dvs=E.SubElement(ah,q('dataValidations'))
    for addr,maximum in [('M60',99999),('M61',999999),('M62',1000000)]:
        dv=E.SubElement(dvs,q('dataValidation'),{'type':'whole' if addr!='M62' else 'decimal','operator':'between','allowBlank':'1','showErrorMessage':'1','errorTitle':'Enter a valid code or price','error':'Use the numeric stock code only, or a positive IPO price.','sqref':addr});E.SubElement(dv,q('formula1')).text='1' if addr!='M62' else '0.000001';E.SubElement(dv,q('formula2')).text=str(maximum)
    dvs.set('count',str(len(dvs)))
    # Remove the former Screener checker and its single A-price history chart.
    screen=E.fromstring(parts[sheets['Screener']]);sc=nodes(screen);calc=E.fromstring(parts[sheets[CALC]])
    for old,new in [('F53','AY53'),('F54','AY54')]:
        n=deepcopy(sc[old]);n.set('r',new);f=n.find(q('f'));f.text=f.text.replace('$F$53','$AY$53').replace('F53','AY53');place(calc,n)
    for p,raw in list(parts.items()):
        if p.startswith('xl/worksheets/') and p.endswith('.xml') and (b"'Screener'!$F$54" in raw or b'Screener!$F$54' in raw):
            d=E.fromstring(raw)
            for f in d.iter(q('f')):
                if f.text:f.text=f.text.replace("'Screener'!$F$54",f"'{CALC}'!$AY$54").replace('Screener!$F$54',f"'{CALC}'!$AY$54")
            parts[p]=E.tostring(d)
    for row in screen.find(q('sheetData')):
        for n in list(row):
            a=n.get('r');r=int(re.search(r'\d+',a)[0]);c=ci(re.match('[A-Z]+',a)[0])
            if (52<=r<=61 and c<=4) or (52<=r<=89 and c in [6,7]):row.remove(n)
    # Keep selected-company fundamentals, moved up into the vacated space.
    for a,n in sc.items():
        r=int(re.search(r'\d+',a)[0]);c=ci(re.match('[A-Z]+',a)[0])
        if 63<=r<=69 and c<=4:
            copy=deepcopy(n);copy.set('r',ec(c)+str(r-11));place(screen,copy)
            parent=next((row for row in screen.find(q('sheetData')) if n in list(row)),None)
            if parent is not None:parent.remove(n)
    smg=screen.find(q('mergeCells'))
    for n in list(smg):
        a=n.get('ref').split(':')[0];r=int(re.search(r'\d+',a)[0])
        if 52<=r<=69:
            if r>=63:n.set('ref',re.sub(r'\d+',lambda m:str(int(m[0])-11),n.get('ref')))
            else:smg.remove(n)
    smg.set('count',str(len(smg)))
    sp=sheets['Screener'];rp=relpath(sp);rels=E.fromstring(parts[rp]);removed=set()
    for rel in list(rels):
        if rel.get('Type').endswith('/drawing'):
            dr=target(sp,rel.get('Target'));drr=relpath(dr);drrels=E.fromstring(parts[drr]);assert len(drrels)==1
            chart=target(dr,list(drrels)[0].get('Target'));assert b'F56' in parts[chart] or b'F$56' in parts[chart] or b'53' in parts[chart]
            removed.update([dr,drr,chart]);rels.remove(rel)
    for n in list(screen):
        if n.tag==q('drawing'):screen.remove(n)
    parts[rp]=E.tostring(rels)
    for p in removed:parts.pop(p,None)
    ct=E.fromstring(parts['[Content_Types].xml'])
    for n in list(ct):
        if (n.get('PartName') or '').lstrip('/') in removed:ct.remove(n)
    parts['[Content_Types].xml']=E.tostring(ct)
    wb=E.fromstring(parts['xl/workbook.xml']);name_map={'A_PX':'M68','A_FX':'M69','A_HKD':'M70','H_TRM':'M65'}
    for dn in wb.find(q('definedNames')):
        if dn.get('name') in name_map:dn.text="'AH'!$"+re.sub(r'(\d+)',r'$\1',name_map[dn.get('name')])
    parts['xl/workbook.xml']=E.tostring(wb)
    # Meaningful sign colours are shared with the existing changes.
    basecf=next((n for n in ah.findall(q('conditionalFormatting')) if 'F8' in n.get('sqref','')),None)
    if basecf is not None:
        basecf.set('sqref',f'F8:I{end}')
        for addr,area in [(f'F{sector_start+2}',f'F{sector_start+2}:I{sector_start+1+len(sectors)}'),(f'F{sub_start+2}',f'F{sub_start+2}:I{sub_start+1+len({value(ac["D"+str(r)]) for r in range(8,end+1)})}'),('M72','M72')]:
            copy=deepcopy(basecf);copy.set('sqref',area)
            for rule in copy:
                rule.set('priority',str(int(rule.get('priority'))+10*len(ah.findall(q('conditionalFormatting')))))
                rule.find(q('formula')).text=rule.find(q('formula')).text.replace('F8',addr)
            ah.append(copy)
    merges.set('count',str(len(merges)))
    for row in ah.find(q('sheetData')):
        r=int(row.get('r'))
        if r>=57:row.set('ht','23');row.set('customHeight','1')
        if r in [7,sector_start+1,sub_start+1]:row.set('ht','34');row.set('customHeight','1')
    for row in screen.find(q('sheetData')):
        if 52<=int(row.get('r'))<=58:row.set('ht','25');row.set('customHeight','1')
    xfs.set('count',str(len(xfs)));parts['xl/styles.xml']=E.tostring(st)
    for name,doc in [('AH',ah),('AH Delta',delta),('Screener',screen),(CALC,calc)]:sort(doc);parts[sheets[name]]=E.tostring(doc)
