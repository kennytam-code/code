import sys,zipfile,re,posixpath
import xml.etree.ElementTree as E
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'ipo_lib'))
from patch_peer_workbook import maps,q,R,P
from reflow_monitors import ci
src,dest,name,region=sys.argv[1:]
a,b=region.split(':');c0=ci(re.match('[A-Z]+',a)[0]);c1=ci(re.match('[A-Z]+',b)[0]);r0=int(re.search('[0-9]+',a)[0]);r1=int(re.search('[0-9]+',b)[0])
with zipfile.ZipFile(src) as z:
    p={x:z.read(x) for x in ['xl/workbook.xml','xl/_rels/workbook.xml.rels','xl/styles.xml','[Content_Types].xml']}
    wb,rels,sm=maps(p);doc=E.fromstring(z.read(sm[name]));sn=wb.find(q('sheets'))
    keep=next(x for x in sn if x.get('name')==name);rid=keep.get('{'+R+'}id');sn[:]=[keep];keep.attrib.pop('state',None)
    rels[:]=[x for x in rels if x.get('Id')==rid or x.get('Type').endswith(('/styles','/theme','/sharedStrings'))]
    for x in list(wb):
        if x.tag==q('definedNames'):wb.remove(x)
    for x in wb.iter(q('workbookView')):x.set('activeTab','0');x.set('firstSheet','0')
    for row in list(doc.find(q('sheetData'))):
        if not r0<=int(row.get('r'))<=r1:doc.find(q('sheetData')).remove(row);continue
        for cell in list(row):
            c=ci(re.match('[A-Z]+',cell.get('r'))[0])
            if not c0<=c<=c1:row.remove(cell);continue
            f=cell.find(q('f'))
            if f is not None:cell.remove(f)
    allowed=['sheetPr','dimension','sheetViews','sheetFormatPr','cols','sheetData','mergeCells','conditionalFormatting']
    for x in list(doc):
        if x.tag.split('}')[-1] not in allowed:doc.remove(x)
    for x in list(doc.iter(q('pane'))):
        for parent in doc.iter():
            if x in list(parent):parent.remove(x);break
    for merge in list(doc.find(q('mergeCells'))) if doc.find(q('mergeCells')) is not None else []:
        pts=merge.get('ref').split(':');coords=[(ci(re.match('[A-Z]+',s)[0]),int(re.search('[0-9]+',s)[0])) for s in pts]
        if not all(c0<=c<=c1 and r0<=r<=r1 for c,r in coords):doc.find(q('mergeCells')).remove(merge)
    doc.find(q('dimension')).set('ref',region)
    types=E.fromstring(p['[Content_Types].xml'])
    kept={'xl/workbook.xml','xl/styles.xml',sm[name],'xl/sharedStrings.xml','xl/theme/theme1.xml'}
    for x in list(types):
        if x.get('PartName') and x.get('PartName').lstrip('/') not in kept:types.remove(x)
    types_xml=E.tostring(types).replace(b'<ns0:',b'<').replace(b'</ns0:',b'</').replace(b'xmlns:ns0=',b'xmlns=')
    rootrels=E.fromstring(z.read('_rels/.rels'));rootrels[:]=[x for x in rootrels if x.get('Type').endswith('/officeDocument')]
    p={'xl/workbook.xml':E.tostring(wb),'xl/_rels/workbook.xml.rels':E.tostring(rels),'[Content_Types].xml':types_xml,sm[name]:E.tostring(doc),'xl/styles.xml':p['xl/styles.xml'],'_rels/.rels':E.tostring(rootrels)}
    for x in ['xl/sharedStrings.xml','xl/theme/theme1.xml']:
        if x in z.namelist():p[x]=z.read(x)
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as out:
        for path,raw in p.items():out.writestr(path,raw)
print('Projection',name,region)
