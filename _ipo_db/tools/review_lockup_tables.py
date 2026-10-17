"""Recover reading order and date-column text for filed lock-up tables."""
import json,hashlib,gc
from pathlib import Path
import requests,pymupdf as fitz
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'out/lockup_review_20261017/sources'
audit=json.loads((OUT.parent/'date_audit.json').read_text())
rows=[r for r in audit['rows'] if r['status']=='needs visual table review']
session=requests.Session();session.headers['User-Agent']='Mozilla/5.0'
for n,r in enumerate(rows,1):
 p=ROOT/r['source_file'];s=json.loads(p.read_text())
 if s.get('ordered_pages'):continue
 response=session.get(r['url'],timeout=(15,45));response.raise_for_status()
 assert hashlib.sha256(response.content).hexdigest()==s['sha256']
 with fitz.open(stream=response.content,filetype='pdf') as doc:
  s['ordered_pages']={k:doc[int(k)-1].get_text(sort=False) for k in s['pages']}
  s['table_words']={str(r['page']):doc[r['page']-1].get_text('words')}
  # A complete-page proof, with original headings/column alignment intact.
  doc[r['page']-1].get_pixmap(matrix=fitz.Matrix(1.1,1.1)).save(OUT/(p.stem+'.png'))
 p.write_text(json.dumps(s,ensure_ascii=False,indent=1));del response;gc.collect()
 if n%10==0:print('Tables',n,'/',len(rows),flush=True)
print('Table reading-order capture complete',flush=True)
