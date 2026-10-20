"""Code-first selector; native input aliases and downstream scoring stay intact."""
import base64,io,json,zipfile,re
from copy import deepcopy
import xml.etree.ElementTree as E
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value,put,sort

def apply(parts,sheets,root):
    doc=E.fromstring(parts[sheets['Screener']]);cs=nodes(doc)
    engine=E.fromstring(parts[sheets['Calc (scoring engine)']]);en=nodes(engine)
    if any(n.find(q('formula1')) is not None and n.find(q('formula1')).text=='AllTargetCodes' for n in doc.iter(q('dataValidation'))):return
    # A two-cell Artifact template supplies the visible selector presentation.
    cfg=json.loads((root/'data/screener_code_layout.json').read_text())
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(cfg['xlsx_base64']))) as z:
        src=E.fromstring(z.read('xl/styles.xml'));_,_,ss=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
        sample=nodes(E.fromstring(z.read(ss['Code selector'])))
    styles=E.fromstring(parts['xl/styles.xml']);xfs=styles.find(q('cellXfs'));offset={}
    for group in ['fonts','fills','borders']:
        target=styles.find(q(group));offset[group]=len(target)
        target.extend(deepcopy(list(src.find(q(group)))));target.set('count',str(len(target)))
    def style(addr):
        n=deepcopy(src.find(q('cellXfs'))[int(sample[addr].get('s','0'))])
        for attr,group in [('fontId','fonts'),('fillId','fills'),('borderId','borders')]:n.set(attr,str(int(n.get(attr,'0'))+offset[group]))
        n.set('numFmtId','0');n.set('xfId','0')
        a=n.find(q('alignment'))
        if a is None:a=E.SubElement(n,q('alignment'))
        a.set('vertical','center');a.set('wrapText','1')
        xfs.append(n);return len(xfs)-1
    put(doc,'A5',v='H code / pipeline',style=style('A2'))
    cs['B5'].set('s',str(style('B2')))
    sheet_cells={'Calc (scoring engine)':en}
    def resolved(sheet,addr):
        if sheet not in sheet_cells:sheet_cells[sheet]=nodes(E.fromstring(parts[sheets[sheet]]))
        cell=sheet_cells[sheet].get(addr.replace('$',''))
        if cell is None:return ''
        f=cell.find(q('f'))
        if f is None:return value(cell)
        ref=f.text.replace('$','')
        if '!' in ref:
            name,ref=ref.rsplit('!',1);return resolved(name.strip("'"),ref)
        if re.fullmatch('[A-Z]+[0-9]+',ref):return resolved(sheet,ref)
        return value(cell)
    aliases={value(c):resolved('Calc (scoring engine)','AR'+a[2:]) for a,c in en.items() if re.fullmatch(r'AQ\d+',a) and int(a[2:])>=3}
    selected=aliases.get(str(value(cs['B5'])).strip().lower(),'')
    put(doc,'E5',f='IF($B$5="","",IF(SelectedDeal="","Code not found",SelectedDeal))',v=selected or ('Code not found' if value(cs['B5']) else ''),style=style('E2'))
    merges=doc.find(q('mergeCells'))
    if not any(m.get('ref')=='E5:F5' for m in merges):E.SubElement(merges,q('mergeCell'),{'ref':'E5:F5'})
    merges.set('count',str(len(merges)))
    # Select exact, unambiguous H codes. Uncoded pipeline deals keep their names.
    codes=sorted({str(int(k)) for k,v in aliases.items() if k.isdigit() and v},key=int)
    covered={aliases[k] for k in aliases if k.isdigit()}
    all_names=[resolved('Calc (scoring engine)',a) for a in en if re.fullmatch(r'AA\d+',a) and int(a[2:])>=3]
    names=[n for n in all_names if n and n not in covered]
    targets=codes+list(dict.fromkeys(names))
    put(engine,'AW2',v='H code / pipeline')
    for r,item in enumerate(targets,3):put(engine,'AW'+str(r),v=item)
    wb=E.fromstring(parts['xl/workbook.xml']);dn=wb.find(q('definedNames'))
    E.SubElement(dn,q('definedName'),{'name':'AllTargetCodes'}).text="'Calc (scoring engine)'!$AW$3:$AW$"+str(len(targets)+2)
    for dv in doc.iter(q('dataValidation')):
        if dv.get('sqref')=='B5':
            dv.find(q('formula1')).text='AllTargetCodes';dv.set('showErrorMessage','0');dv.set('showInputMessage','1');dv.set('promptTitle','H code / pipeline');dv.set('prompt','Type an H code such as 9607, or select a pipeline company.');dv.set('showDropDown','0')
    xfs.set('count',str(len(xfs)));sort(doc);sort(engine)
    parts[sheets['Screener']]=E.tostring(doc);parts[sheets['Calc (scoring engine)']]=E.tostring(engine)
    parts['xl/styles.xml']=E.tostring(styles);parts['xl/workbook.xml']=E.tostring(wb)
