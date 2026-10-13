"""Restore full native range bindings after bounded Artifact layout authoring."""
import base64,io,json,re,zipfile
from datetime import date
from pathlib import Path
import xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parent.parent
N='http://schemas.openxmlformats.org/spreadsheetml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships';q=lambda n:'{'+N+'}'+n
def maps(parts):
 wb=E.fromstring(parts['xl/workbook.xml']);rels=E.fromstring(parts['xl/_rels/workbook.xml.rels']);targets={x.get('Id'):x.get('Target') for x in rels}
 return wb,rels,{s.get('name'):('xl/'+targets[s.get('{'+R+'}id')].lstrip('/')).replace('xl/xl/','xl/') for s in wb.find(q('sheets'))}
def serial(s):return (date.fromisoformat(s)-date(1899,12,30)).days
def put(doc,addr,value):
 data=doc.find(q('sheetData'));r=int(re.search(r'\d+',addr)[0]);row=next((x for x in data if int(x.get('r'))==r),None)
 if row is None:row=E.SubElement(data,q('row'),{'r':str(r)})
 cell=next((x for x in row if x.get('r')==addr),None)
 if cell is None:cell=E.SubElement(row,q('c'),{'r':addr})
 for x in list(cell):cell.remove(x)
 cell.attrib.pop('t',None)
 if isinstance(value,str):cell.set('t','inlineStr');E.SubElement(E.SubElement(cell,q('is')),q('t')).text=value
 else:E.SubElement(cell,q('v')).text=str(value)
def sort(doc):
 data=doc.find(q('sheetData'));data[:]=sorted(data,key=lambda r:int(r.get('r')))
p=ROOT/'data/peer_views_template.json';authored=json.loads(p.read_text())
with zipfile.ZipFile(io.BytesIO(base64.b64decode(authored['xlsx_base64']))) as z:parts={n:z.read(n) for n in z.namelist()}
_,_,sheets=maps(parts);meta=json.loads((ROOT/'data/peer_pairs.json').read_text());stocks=meta['stocks'];old_end=1+sum(min(2,len(s['history'])) for s in stocks);new_end=1+sum(len(s['history']) for s in stocks)
pd=E.fromstring(parts[sheets['Peer Data']]);cursor=2
for i,s in enumerate(stocks,3):
 for col,v in zip('HIJKLMN',[s['code'],s['name'],s['ticker'],cursor,len(s['history']),serial(s['history'][-1][0]),s['currency']]):put(pd,col+str(i),v)
 cursor+=len(s['history'])
sort(pd);parts[sheets['Peer Data']]=E.tostring(pd)
for name in ['Peer Trades','Peer Chart','Peer Live']:
 d=E.fromstring(parts[sheets[name]])
 for f in d.iter(q('f')):
  if f.text:
   for col in 'AB':f.text=f.text.replace(f"'Peer Data'!${col}$1:${col}${old_end}",f"'Peer Data'!${col}$1:${col}${new_end}")
 parts[sheets[name]]=E.tostring(d)
buffer=io.BytesIO()
with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
 for name,raw in parts.items():z.writestr(name,raw)
authored['xlsx_base64']=base64.b64encode(buffer.getvalue()).decode();authored['history_ranges']='Full native ranges restored from dated stock histories.';p.write_text(json.dumps(authored));print('Restored',len(stocks),'stocks and',new_end-1,'history-row range capacity')
