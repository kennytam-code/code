import zipfile,xml.etree.ElementTree as E,collections,json,sys,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value
p=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'TO_NOMURA/HK_IPO_Database_v1.xlsx'
report={}
with zipfile.ZipFile(p) as z:
 wb,_,s=maps({x:z.read(x) for x in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']});states={n.get('name'):n.get('state','visible') for n in wb.find(q('sheets'))}
 for name,path in s.items():
  n=collections.Counter();samples=collections.defaultdict(list);active=0;rows=0;fields=collections.Counter();fcount=0
  for event,c in E.iterparse(z.open(path),events=('end',)):
   if c.tag==q('c'):
    rows+=1;f=c.find(q('f'))
    if f is not None:
     fcount+=1;t=f.text or '';types=re.findall(r'\b(BDP|BDH|BQL)\(',t)
     for typ in types:
      n[typ]+=1
      if len(samples[typ])<5:samples[typ].append([c.get('r'),t])
     if types and not re.search(r'Bloomberg|Stored',t):active+=1
     for fld in re.findall(r'(?:BDP|BDH)\([^,]+,"([A-Z_]+)"',t):fields[fld]+=1
    c.clear()
   elif c.tag==q('row'):c.clear()
  report[name]={'state':states[name],'cells':rows,'formulas':fcount,'requests':dict(n),'no_source_switch':active,'fields':dict(fields),'samples':dict(samples)}
  print(name,states[name],rows,'cells',fcount,'formulas',dict(n),'no source switch',active)
(Path(sys.argv[2]) if len(sys.argv)>2 else ROOT/'out/efficiency_20261022/request_audit_before.json').write_text(json.dumps(report,indent=2)+'\n')
for name in ['IPO Live','Market Data','Peer Data','Valuation Data','BBG Verify','AH Delta','Screener']:
 print('\n'+name)
 for typ,xs in report.get(name,{}).get('samples',{}).items():
  for a,f in xs[:3]:print(a,f[:600])
