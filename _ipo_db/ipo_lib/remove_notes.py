"""Remove the requested Notes sheet while retaining its named model inputs."""
import base64, io, json, re, zipfile
from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as E
from patch_peer_workbook import maps, q, R
from reflow_monitors import nodes, value, put, place, sort

ENGINE = 'Calc (scoring engine)'

def apply(parts, sheets, root):
    if 'Notes' not in sheets:
        return
    wb, rels, _ = maps(parts)
    notes_path = sheets['Notes']
    assert notes_path.rsplit('/', 1)[0]+'/_rels/'+notes_path.rsplit('/', 1)[1]+'.rels' not in parts
    notes = nodes(E.fromstring(parts[notes_path]))
    calc = E.fromstring(parts[sheets[ENGINE]])
    existing = nodes(calc)
    cfg = json.loads((Path(root)/'data/note_weight_layout.json').read_text())
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(cfg['xlsx_base64']))) as z:
        _, _, template_sheets = maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
        template = nodes(E.fromstring(z.read(template_sheets['Weights'])))
        strings = [''.join(x.itertext()) for x in E.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
    for src, dst in [('A1','AT1'),('B1','AU1'),('C1','AV1')]:
        c = template[src]
        text = strings[int(c.findtext(q('v')))] if c.get('t')=='s' else value(c)
        assert dst not in existing
        put(calc, dst, v=text, style=notes['A25'].get('s'))
    names = wb.find(q('definedNames'))
    affected = {n.get('name'):n for n in names if (n.text or '').startswith('Notes!')}
    assert set(affected)==set(cfg['parameters'])
    for row, name in enumerate(cfg['parameters'], 2):
        named = affected[name]
        source = named.text.split('!')[1].replace('$','')
        assert re.fullmatch(r'B\d+', source)
        assert notes[source].find(q('f')) is None
        float(value(notes[source]))
        for a,b in [('A','AT'),('B','AU'),('C','AV')]:
            src=a+source[1:]; dst=b+str(row)
            assert dst not in existing
            cell=deepcopy(notes[src]);cell.set('r',dst);place(calc,cell)
        named.text=f"'{ENGINE}'!$AU${row}"
    # Only the already hidden calculation page receives these existing inputs.
    cols=calc.find(q('cols'))
    for col,width in [(46,18),(47,12),(48,54)]:
        assert not any(int(c.get('min'))<=col<=int(c.get('max')) for c in cols)
        E.SubElement(cols,q('col'),{'min':str(col),'max':str(col),'width':str(width),'customWidth':'1'})
    dimension=calc.find(q('dimension'))
    dimension.set('ref','A1:AV'+re.search(r'\d+$',dimension.get('ref'))[0])
    a2=existing.get('A2')
    if a2 is not None and 'Weights are named cells on the Notes tab.' in (value(a2) or ''):
        put(calc,'A2',v=value(a2).replace('Weights are named cells on the Notes tab.','Named weights are stored in AT:AV.'),style=a2.get('s'))
    sort(calc);parts[sheets[ENGINE]]=E.tostring(calc)
    all_sheets=wb.find(q('sheets'));old=list(all_sheets)
    removed=next(s for s in old if s.get('name')=='Notes')
    all_sheets.remove(removed)
    for rel in list(rels):
        if rel.get('Id')==removed.get('{'+R+'}id'):rels.remove(rel)
    for n in list(names):
        local=n.get('localSheetId')
        if local is not None:
            owner=old[int(local)]
            if owner is removed:names.remove(n)
            else:n.set('localSheetId',str(list(all_sheets).index(owner)))
        assert 'Notes!' not in (n.text or '') and "'Notes'!" not in (n.text or '')
    for v in wb.iter(q('workbookView')):
        for attr in ['activeTab','firstSheet']:
            idx=int(v.get(attr,'0'));owner=old[idx]
            v.set(attr,str(list(all_sheets).index(owner)) if owner is not removed else '0')
    parts['xl/workbook.xml']=E.tostring(wb)
    parts['xl/_rels/workbook.xml.rels']=E.tostring(rels)
    types=E.fromstring(parts['[Content_Types].xml'])
    for n in list(types):
        if (n.get('PartName') or '').lstrip('/')==notes_path:types.remove(n)
    parts['[Content_Types].xml']=E.tostring(types)
    parts.pop(notes_path);sheets.pop('Notes')
    if 'docProps/app.xml' in parts:
        d=E.fromstring(parts['docProps/app.xml']);vt='{http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes}'
        for child in d:
            vector=child.find(vt+'vector')
            if vector is None:continue
            if child.tag.endswith('TitlesOfParts'):
                for item in list(vector):
                    if item.text=='Notes':vector.remove(item)
                vector.set('size',str(len(vector)))
            elif child.tag.endswith('HeadingPairs'):
                for i,item in enumerate(vector):
                    if item.findtext(vt+'lpstr')=='Worksheets':list(vector)[i+1].find(vt+'i4').text=str(len(all_sheets))
        parts['docProps/app.xml']=E.tostring(d)
    for path,raw in parts.items():
        if path.endswith('.xml'):
            assert b'Notes!' not in raw and b"'Notes'!" not in raw and b'Notes&apos;!' not in raw,path
    print('Removed Notes; preserved all 11 named scoring inputs in the existing hidden calculation sheet.',flush=True)
