"""Remove cell-note markers and their package parts, preserving chart/control drawings."""
import posixpath,re
import xml.etree.ElementTree as E
from patch_peer_workbook import q,R

def resolve(owner,target):
 return target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(posixpath.dirname(owner),target))

def apply(parts,sheets,root):
 removed=set();count=0
 for path,raw in list(parts.items()):
  if re.search(r'(?:^|/)(?:comments/|comments[^/]*\.xml|threadedComments/|persons/)',path,re.I) and not path.endswith('.rels'):
   count+=len(re.findall(rb'<(?:\w+:)?comment\b',raw));removed.add(path)
  elif path.lower().endswith('.vml'):
   types=set(re.findall(rb'ObjectType=[\"\x27]([^\"\x27]+)',raw))
   if types=={b'Note'}:removed.add(path)
   elif b'Note' in types:
    doc=E.fromstring(raw)
    for parent in doc.iter():
     for node in list(parent):
      if node.tag.rsplit('}',1)[-1]=='shape' and any(n.get('ObjectType')=='Note' for n in node.iter()):parent.remove(node)
    parts[path]=E.tostring(doc)
 # Strip relationships, including worksheet legacyDrawing references only
 # when their own VML target was exclusively cell notes.
 for path in list(parts):
  if not path.endswith('.rels'):continue
  owner=posixpath.normpath(posixpath.join(posixpath.dirname(path),'..',posixpath.basename(path)[:-5]))
  if owner in removed:removed.add(path);continue
  doc=E.fromstring(parts[path]);ids=set()
  for rel in list(doc):
   if rel.get('TargetMode')!='External' and resolve(owner,rel.get('Target','')) in removed:
    ids.add(rel.get('Id'));doc.remove(rel)
  if not ids:continue
  parts[path]=E.tostring(doc)
  if owner in parts and owner in sheets.values():
   sheet=E.fromstring(parts[owner])
   for parent in sheet.iter():
    for node in list(parent):
     if node.get('{'+R+'}id') in ids:parent.remove(node)
   parts[owner]=E.tostring(sheet)
 types=E.fromstring(parts['[Content_Types].xml'])
 for node in list(types):
  if node.get('PartName','').lstrip('/') in removed:types.remove(node)
  elif node.get('Extension')=='vml' and not any(p.endswith('.vml') and p not in removed for p in parts):types.remove(node)
 parts['[Content_Types].xml']=E.tostring(types)
 for path in removed:parts.pop(path,None)
 print('Removed cell notes:',count,'comments,',len(removed),'package parts',flush=True)
