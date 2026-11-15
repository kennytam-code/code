"""Check the actual standalone artifact against its staged source/data inputs."""
import ast,base64,io,json,sys,zipfile,zlib,tempfile,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'ipo_lib'))
import make_bundle
print('Read embedded constants',flush=True)
vals={}
syntax=[]
for line in (ROOT/'export/hk_ipo.py').open():
 found=False
 for key in ['_PAYLOAD','_MODULES','_LIBZIP']:
  if line.startswith(key+' = '):
   literal=line.split(' = ',1)[1].strip();found=True
   if key=='_MODULES':vals[key]=ast.literal_eval(literal)
   else:
    assert literal[0]==literal[-1]=='"' and re.fullmatch('[A-Za-z0-9+/=]*',literal[1:-1])
    vals[key]=literal[1:-1]
   syntax.append(key+' = None\n')
 if not found:syntax.append(line)
# The three validated literals contain only base64 or a parsed dict. Elide
# their large constant allocations while compiling all executable code.
compile(''.join(syntax),'hk_ipo.py','exec');del syntax,literal,line
expected=list(dict.fromkeys(p for p in make_bundle.DATA_FILES if (ROOT/p).exists()))
# Compare streaming hashes of the exact serialized payload. Construct the
# expected object one file at a time; avoid retaining a Unicode copy of all
# 68 MB of embedded source data or repeatedly decoding the largest string.
from hashlib import sha256
actual=sha256();compressed=base64.b64decode(vals.pop('_PAYLOAD'));dec=zlib.decompressobj()
for start in range(0,len(compressed),8192):actual.update(dec.decompress(compressed[start:start+8192]))
actual.update(dec.flush());del compressed,dec
wanted=sha256();wanted.update(b'{')
for i,p in enumerate(expected):
 if i:wanted.update(b', ')
 wanted.update(json.dumps(p,ensure_ascii=False).encode());wanted.update(b': ')
 wanted.update(json.dumps((ROOT/p).read_text(),ensure_ascii=False).encode())
wanted.update(b'}');assert wanted.digest()==actual.digest(),'Embedded data differs from sources'
print('Check modules',flush=True)
with zipfile.ZipFile(io.BytesIO(base64.b64decode(vals['_LIBZIP']))) as z:
 for name in make_bundle.LIB_MODULES:
  value=z.read(name+'.py').decode();assert value==(ROOT/'ipo_lib'/f'{name}.py').read_text(),name
  compile(value,name+'.py','exec')
for name,value in vals['_MODULES'].items():assert value==make_bundle.module_blob(name),name
assert '("ah-history", "refresh_ah_history", [], "prices")' in (ROOT/'export/hk_ipo.py').read_text()
assert '("ah-history", "ipo_lib/refresh_ah_history.py", [], "prices")' in (ROOT/'ipo.py').read_text()
result=dict(data_files=len(expected),modules=len(make_bundle.LIB_MODULES),standalone_builders=2,compiles=True,parity=True)
(ROOT/'out/ah_review_20261115/bundle_checks.json').write_text(json.dumps(result,indent=2))
print('PASS',json.dumps(result))
