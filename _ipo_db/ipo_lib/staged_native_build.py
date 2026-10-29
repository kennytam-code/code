"""Assemble desk workbook in separate bounded processes, preserving native parts."""
import os,sys,json,zipfile,re,posixpath,subprocess,gc
from pathlib import Path
from copy import deepcopy
import xml.etree.ElementTree as E
from patch_peer_workbook import maps,q,N,R,P,T
ORDER=['IPO Live','AH','Lock-up','Peer Trades','Screener','Database','Pipeline','CS League','SM League','Scoring Stats','Taxonomy','Notes','SizeBench','BBG Verify','Verification']

def join(core,monitors,dest):
 with zipfile.ZipFile(core) as z:parts={p:z.read(p) for p in z.namelist()}
 with zipfile.ZipFile(monitors) as z:new={p:z.read(p) for p in z.namelist()}
 wb,rels,sheets=maps(parts);mw,mrels,msheets=maps(new)
 styles=E.fromstring(parts['xl/styles.xml']);incoming=E.fromstring(new['xl/styles.xml']);offset={}
 for name in ['fonts','fills','borders','cellStyleXfs','cellXfs','dxfs','numFmts']:
  a=styles.find(q(name));b=incoming.find(q(name))
  if a is None:a=E.SubElement(styles,q(name),{'count':'0'})
  offset[name]=len(a)
  if b is not None and name not in ['cellXfs','numFmts','dxfs']:
   for item in b:a.append(deepcopy(item))
   a.set('count',str(len(a)))
 nfs=styles.find(q('numFmts'));nfmap={};nextid=max([163]+[int(x.get('numFmtId')) for x in nfs])+1
 for item in list(incoming.find(q('numFmts'))) if incoming.find(q('numFmts')) is not None else []:
  old=int(item.get('numFmtId'));nfmap[old]=nextid;n=deepcopy(item);n.set('numFmtId',str(nextid));nfs.append(n);nextid+=1
 nfs.set('count',str(len(nfs)))
 for item in incoming.find(q('cellXfs')):
  n=deepcopy(item)
  for attr,group in [('fontId','fonts'),('fillId','fills'),('borderId','borders'),('xfId','cellStyleXfs')]:n.set(attr,str(int(n.get(attr,'0'))+offset[group]))
  old=int(n.get('numFmtId','0'));n.set('numFmtId',str(nfmap.get(old,old)));styles.find(q('cellXfs')).append(n)
 styles.find(q('cellXfs')).set('count',str(len(styles.find(q('cellXfs')))))
 for item in list(incoming.find(q('dxfs'))) if incoming.find(q('dxfs')) is not None else []:styles.find(q('dxfs')).append(deepcopy(item))
 styles.find(q('dxfs')).set('count',str(len(styles.find(q('dxfs')))))
 parts['xl/styles.xml']=E.tostring(styles)
 # Every incoming native part gets an isolated path. Relationship targets follow it.
 remap={}
 for path in new:
  if path.startswith(('xl/worksheets/','xl/drawings/','xl/charts/','xl/tables/','xl/comments/')):
   directory,base=posixpath.split(path);remap[path]=directory+'/monitor_'+base
 for path in new:
  if path.endswith('.rels') and '/_rels/' in path:
   owner=posixpath.normpath(posixpath.join(posixpath.dirname(path),'..',posixpath.basename(path)[:-5]))
   if owner in remap:
    mapped=remap[owner];remap[path]=posixpath.dirname(mapped)+'/_rels/'+posixpath.basename(mapped)+'.rels'
 max_table=max([0]+[int(E.fromstring(raw).get('id')) for p,raw in parts.items() if p.startswith('xl/tables/') and p.endswith('.xml')])
 for path,target in remap.items():
  raw=new[path]
  if path.endswith('.rels'):
   doc=E.fromstring(raw);owner=posixpath.normpath(posixpath.join(posixpath.dirname(path),'..',posixpath.basename(path)[:-5]))
   for rel in doc:
    if rel.get('TargetMode')=='External':continue
    t=rel.get('Target');resolved=t.lstrip('/') if t.startswith('/') else posixpath.normpath(posixpath.join(posixpath.dirname(owner),t))
    assert resolved in remap,(path,resolved);rel.set('Target','/'+remap[resolved])
   raw=E.tostring(doc)
  elif path in msheets.values():
   doc=E.fromstring(raw)
   for cell in doc.iter(q('c')):
    if 's' in cell.attrib:cell.set('s',str(int(cell.get('s'))+offset['cellXfs']))
   for rule in doc.iter(q('cfRule')):
    if 'dxfId' in rule.attrib:rule.set('dxfId',str(int(rule.get('dxfId'))+offset['dxfs']))
   raw=E.tostring(doc)
  elif path.startswith('xl/tables/') and path.endswith('.xml'):
   doc=E.fromstring(raw);max_table+=1;doc.set('id',str(max_table));raw=E.tostring(doc)
  parts[target]=raw
 sid=max(int(s.get('sheetId')) for s in wb.find(q('sheets')))
 for i,s in enumerate(mw.find(q('sheets')),1):
  name=s.get('name');assert name not in sheets,name;sid+=1;copy=deepcopy(s);rid=f'monitorSheet{i}';copy.set('sheetId',str(sid));copy.set('{'+R+'}id',rid);wb.find(q('sheets')).append(copy)
  E.SubElement(rels,'{'+P+'}Relationship',{'Id':rid,'Type':R+'/worksheet','Target':'/'+remap[msheets[name]]})
 names=wb.find(q('definedNames'))
 if names is None:names=E.SubElement(wb,q('definedNames'))
 for n in list(mw.find(q('definedNames'))) if mw.find(q('definedNames')) is not None else []:
  assert n.get('localSheetId') is None,'Local names need explicit rebinding'
  for old in list(names):
   if old.get('name')==n.get('name'):names.remove(old)
  names.append(deepcopy(n))
 sheetsnode=wb.find(q('sheets'));sheetsnode[:]=sorted(sheetsnode,key=lambda n:ORDER.index(n.get('name')) if n.get('name') in ORDER else len(ORDER))
 for v in wb.iter(q('workbookView')):v.set('activeTab','0');v.set('firstSheet','0')
 for node in wb.iter(q('calcPr')):node.set('fullCalcOnLoad','1')
 types=E.fromstring(parts['[Content_Types].xml']);keys={(n.tag,n.get('PartName') or n.get('Extension')) for n in types}
 for n in E.fromstring(new['[Content_Types].xml']):
  copy=deepcopy(n)
  if n.get('PartName'):
   old=n.get('PartName').lstrip('/')
   if old not in remap:continue
   copy.set('PartName','/'+remap[old])
  key=(copy.tag,copy.get('PartName') or copy.get('Extension'))
  if key not in keys:types.append(copy);keys.add(key)
 parts['xl/workbook.xml']=E.tostring(wb);parts['xl/_rels/workbook.xml.rels']=E.tostring(rels);parts['[Content_Types].xml']=E.tostring(types)
 with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
  for p,raw in parts.items():z.writestr(p,raw)
 print('Joined core and monitors without importing the complete workbook',flush=True)

def transform(source,dest,root,module,function):
 import importlib
 with zipfile.ZipFile(source) as z:parts={p:z.read(p) for p in z.namelist()}
 _,_,sheets=maps(parts);getattr(importlib.import_module(module),function)(parts,sheets,Path(root))
 with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
  for p,raw in parts.items():z.writestr(p,raw)
 print('Applied',module,flush=True)

def build(root,dest):
 root=Path(root);dest=Path(dest);dest.parent.mkdir(parents=True,exist_ok=True);core=dest.with_suffix('.core.tmp.xlsx');mon=dest.with_suffix('.monitor.tmp.xlsx');peer=dest.with_suffix('.peer.tmp.xlsx');staged=dest.with_suffix('.presentation.tmp.xlsx')
 env=dict(os.environ);env['PYTHONPATH']=str(root/'ipo_lib')+os.pathsep+env.get('PYTHONPATH','')
 def run(code):subprocess.run([sys.executable,'-c',code],cwd=root,env=env,check=True)
 run(f'import build_xlsx;build_xlsx.main(out={str(core)!r},base_only=True,core_only=True)')
 run(f'from pathlib import Path;from openpyxl import Workbook;from build_xlsx import load;from build_market_views import build;w=Workbook();w.remove(w.active);build(w,load()[0],Path({str(root)!r}),defer_peer_history=True);w.save({str(mon)!r});print("Saved monitor stage")')
 join(core,mon,dest)
 run(f'from patch_peer_workbook import patch;patch({str(dest)!r},{str(peer)!r},{str(root)!r})');peer.replace(dest)
 run(f'from apply_desk_styles import apply;apply({str(dest)!r},{str(root)!r})')
 run(f'from pathlib import Path;from patch_presentation_workbook import patch;patch(Path({str(dest)!r}),Path({str(staged)!r}),Path({str(root)!r}),finish=False)');staged.replace(dest)
 for mod,fn in [('reflow_monitors','reflow'),('fix_monitor_requests','apply'),('adjust_ah_charts','apply'),('combine_ah_benchmark','apply'),('desk_release','apply'),('sector_monitor_release','apply'),('final_polish','apply'),('desk_theme','apply'),('remove_notes','apply'),('ah_chart_style','apply'),('screener_code_selector','apply'),('request_efficiency','apply'),('screener_desk','apply'),('ah_desk_update','apply'),('excel_chart_refresh','apply'),('ah_live_requests','apply')]:
  if os.environ.get('IPO_QA_BASELINES')=='1' and mod in ['sector_monitor_release','final_polish','desk_theme','remove_notes']:
   (root/'out').mkdir(exist_ok=True)
   baseline={'sector_monitor_release':'_sector_baseline_20261015.xlsx','final_polish':'_polish_baseline_20261015.xlsx','desk_theme':'_theme_baseline_20261015.xlsx','remove_notes':'_notes_baseline_20261016.xlsx'}[mod]
   __import__('shutil').copyfile(dest,root/'out'/baseline)
  run(f'from staged_native_build import transform;transform({str(dest)!r},{str(staged)!r},{str(root)!r},{mod!r},{fn!r})');staged.replace(dest)
 for p in [core,mon]:p.unlink(missing_ok=True)
 print('Wrote staged native desk workbook',dest,flush=True);return dest
if __name__=='__main__':build(Path(__file__).resolve().parent.parent,Path(sys.argv[1]))
