"""Review the complete canonical cornerstone list against filing evidence.

Investor groups and their legal subscribing vehicles are kept distinct. A
partial row parse cannot replace a complete researched list or its percentage.
"""
import argparse,json,re,unicodedata
from pathlib import Path
from fill_cornerstones import allotment_table
ROOT=Path(__file__).resolve().parent.parent
def norm(s):
 return re.sub(r'[^a-z0-9\u3400-\u9fff]','',unicodedata.normalize('NFKC',s).lower())
def main():
 p=argparse.ArgumentParser();p.add_argument('--allotments',type=Path,required=True);p.add_argument('--prospectuses',type=Path,required=True);a=p.parse_args()
 deals=json.loads((ROOT/'data/deals.json').read_text())['deals'];out=[]
 corrections={r['code']:r for r in json.loads((ROOT/'data/batches/cornerstone_name_corrections.json').read_text())['deals']} if (ROOT/'data/batches/cornerstone_name_corrections.json').exists() else {}
 for d in deals:
  r={'code':d['code']};sources=[];tables=[]
  for directory,prefix in [(a.allotments,'allot'),(a.prospectuses,'prosp')]:
   for f in directory.glob(f'{prefix}_{d["code"]}_*.pages.json'):
    rec=json.loads(f.read_text());pages=rec['pages']
    for i,page in enumerate(pages,1):
     pg=page if isinstance(page,dict) else {'page':i,'text':page}
     if re.search('cornerstone',pg['text'],re.I):sources.append(dict(pg,normalized=norm(pg['text']),url=rec['url'],sha256=rec['sha256'],type=prefix))
    if prefix=='allot':
     table=allotment_table('\n'.join(pages),d.get('offer_shares'))
     if table:tables.append(dict(table,url=rec['url'],sha256=rec['sha256']))
  names=d.get('cornerstone_investors') or [];checks=[]
  for name in names:
   key=norm(name)
   # A short full name such as Zhou Bo is still evidence when its complete,
   # word-bounded spelling occurs on a cornerstone page. Do not accept a
   # short substring inside another investor's name.
   literal=re.compile(r'(?<![A-Za-z0-9])'+r'\s+'.join(re.escape(t) for t in name.split())+r'(?![A-Za-z0-9])',re.I)
   match=next((s for s in sources if (len(key)>8 and key in s['normalized']) or (5<=len(key)<=8 and literal.search(s['text']))),None)
   checks.append({'name':name,'status':'Named in cornerstone filing context' if match else 'Legal name / investor-group alias needs manual confirmation',**({k:match[k] for k in ['page','url','sha256','type']} if match else {})})
  if d['code'] in corrections:
   # Full-roster/manual corrections can span pages or use filed short forms.
   # Their retained page/hash evidence is stronger than literal substring matching.
   ev=corrections[d['code']]['cornerstone_investors_evidence']
   from clean_names import name_signature
   signatures=[name_signature(n) for n in ev.get('confirmed_names',[])]
   for item in checks:
    signature=name_signature(item['name'])
    if len(signature)>8 and any(signature in s for s in signatures):item.update(status='Reviewed filed roster / legal entity context',**{k:ev[k] for k in ['page','url','sha256']})
  r['name_checks']=checks
  if not names and (d.get('cornerstone_none') or d.get('cornerstone_pct')==0):
   section=any(len(re.findall('cornerstone',s['text'],re.I))>7 for s in sources)
   r['none_review']='Needs confirmation' if section else 'No cornerstone tranche found in full prospectus / allotment review'
  # A printed total is reliable without guessing fund aliases. Computed
  # totals require every researched investor group to occur in the rows.
  valid=[]
  for t in tables:
   rowtext=norm(' '.join(t['names']))
   complete=bool(names) and all(norm(n) in rowtext for n in names)
   if t['kind']=='printed' or complete:valid.append(t)
  if valid and max(t['pct'] for t in valid)-min(t['pct'] for t in valid)<=.02:
   t=valid[0];r['cornerstone_pct']=t['pct'];r['cornerstone_pct_evidence']={k:t[k] for k in ['pct','basis','kind','url','sha256','shares']}
  # A duplicated company name was previously concatenated during PDF parsing.
  if d['code']=='2150':
   clean=[re.sub(r'(China Universal Asset Management Co\., Ltd)\s*\1',r'\1',n) for n in names]
   if clean!=names:r['cornerstone_investors']=clean;r['cornerstone_investors_evidence']={'method':'Remove exact duplicated legal name; rest of investor list retained','name_checks':checks}
  r['review_status']='Reviewed; aliases outstanding' if any('needs manual' in c['status'] for c in checks) else 'Reviewed'
  if d['code']=='3228':
   # pp.6–7 print an aggregate of 34,788,400 shares / 47.69%.
   # Note 2 explicitly equates total issued H shares to base Offer Shares.
   t=next(t for t in tables if abs(t['pct']-47.69)<.001)
   r['cornerstone_pct']=47.69;r['cornerstone_pct_evidence']={'value':47.69,'page':7,'url':t['url'],'sha256':t['sha256'],'basis_note':'Printed total 34,788,400 cornerstone shares / 47.69%; Note 2 equates H shares to base Offer Shares. Group totals counted once.'}
   corrected=[('E Fund Management Co., Ltd. and E Fund Management (Hong Kong) Co., Ltd.' if n=='E Fund Management (Hong Kong) Co., Ltd' else 'Zhongji Innolight (via VERTEXVEST HOLDING PTE. LTD.)' if n=='Zhongji Innolight Co., Ltd' else n) for n in names]
   r['cornerstone_investors']=corrected;r['cornerstone_investors_evidence']={'page':6,'url':t['url'],'sha256':t['sha256'],'method':'Retain investor groups; disclose both E Fund subscribers and Zhongji Innolight legal vehicle.'}
  out.append(r)
 (ROOT/'data/batches/cornerstone_review.json').write_text(json.dumps({'batch':'cornerstone_review','deals':out},ensure_ascii=False,indent=1))
 print('Stocks',len(out),'printed/complete percentage checks',sum('cornerstone_pct' in r for r in out),'names',sum(len(r['name_checks']) for r in out),'aliases',sum('needs manual' in c['status'] for r in out for c in r['name_checks']))
if __name__=='__main__':main()
