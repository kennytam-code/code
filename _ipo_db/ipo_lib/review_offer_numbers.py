"""Independent named-field readings from the final allotment announcements."""
import argparse,json,re
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
NUM=r'\d[\d,]*(?:\.\d+)?'
PATTERNS={
 'final_price':[rf'(?<!Maximum )(?<!maximum )Offer\s+Price\s*(?::|\(Note\s*\d+\))?\s*HK\$\s*({NUM})(?=\s*(?:per\s+(?:H\s+|Offer\s+|Class\s+[AB]\s+)?Share|[\n\r]|$))'],
 'offer_shares':[rf'(?:Number|No\.)\s+of\s+Offer\s+Shares\s+under\s+the\s+(?:Global\s+Offering|Share\s+Offer)\s*:?\s*({NUM})',rf'(?<!Final )(?<!Final Number of )Number\s+of\s+Offer\s+Shares\s*:?\s*({NUM})\s+(?:H\s+|Class\s+[AB]\s+)?Shares'],
 'gross_proceeds_hkdm':[rf'Gross\s+proceeds\s*(?:\([^)]*\))?\s*HK\$\s*({NUM})\s*(million|billion)'],
 'mktcap_filing_hkdm':[rf'(?:expected\s+)?Market\s+capitali[sz]ation\s+(?:of\s+the\s+Company(?:[’\x27]s\s+H\s+Shares)?\s+)?(?:immediately\s+)?upon\s+(?:the\s+)?Listing\s+(?:is|would\s+be|will\s+be)(?:\s+expected\s+to\s+be)?\s*(?:approximately\s+)?HK\$\s*({NUM})\s*(million|billion)'],
 'intl_placees':[rf'(?<!total )(?:No\.|Number)\s+of\s+placees\s*(?:\([^)]*\))?\s*({NUM})\b(?=\s+Subscription\s+Level)'],
 'public_shares_final':[rf'Final\s+(?:no\.|number)\s+of\s+(?:Hong\s+Kong\s+)?(?:Offer\s+|H\s+)?Shares\s+under\s+the\s+(?:Hong\s+Kong\s+)?Public\s+Offering\s*(?:\([^)]*\))?\s*({NUM})'],
}
def read(pages):
 out={}
 for field,patterns in PATTERNS.items():
  hits=[]
  for pg,text in enumerate(pages,1):
   t=re.sub(r'\s+',' ',text)
   for pat in patterns:
    for m in re.finditer(pat,t,re.I):
     v=float(m.group(1).replace(',',''))
     if len(m.groups())>1 and m.group(2)=='billion':v*=1000
     if v<=0:continue
     hits.append({'value':v,'page':pg,'snippet':t[max(0,m.start()-60):m.end()+140]})
  vals=[h['value'] for h in hits]
  if vals and max(vals)-min(vals)<=max(.005,max(vals)*.00005):out[field]=hits[0]
  elif vals:out[field+'_ambiguous']=hits
 return out
def main():
 p=argparse.ArgumentParser();p.add_argument('--cache-dir',type=Path,required=True);a=p.parse_args();D=json.loads((ROOT/'data/deals.json').read_text())['deals'];out=[];issues=[]
 for d in D:
  row={'code':d['code']};candidates={}
  for f in a.cache_dir.glob(f'allot_{d["code"]}_*.pages.json'):
   r=json.loads(f.read_text())
   for k,h in read(r['pages']).items():
    if not k.endswith('_ambiguous'):candidates.setdefault(k,[]).append(dict(h,url=r['url'],sha256=r['sha256']))
  for k,hits in candidates.items():
   vals=[h['value'] for h in hits]
   if max(vals)-min(vals)<=max(.005,max(vals)*.00005):row[k]=hits[0]['value'];row[k+'_evidence']=hits[0]
   else:issues.append({'code':d['code'],'field':k,'readings':hits})
  # The summary's proceeds can include over-allocated shares while its Offer
  # Shares line excludes them. Preserve the printed amount and reconcile the
  # base offering separately, rather than mixing these two denominators.
  base=row.get('final_price',d.get('final_price',0))*row.get('offer_shares',d.get('offer_shares',0))/1e6
  gross=row.get('gross_proceeds_hkdm')
  if gross and base and abs(gross-base)>max(.1,base*.001):
   over=[]
   for f in a.cache_dir.glob(f'allot_{d["code"]}_*.pages.json'):
    rec=json.loads(f.read_text())
    for pg,t in enumerate(rec['pages'],1):
     for m in re.finditer(r'No\.\s+of\s+Offer\s+Shares\s+over-allocated\s+([\d,]+)',t,re.I):
      over.append(int(m.group(1).replace(',','')))
   if any(abs(base+n*row.get('final_price',d.get('final_price',0))/1e6-gross)<.02 for n in over):
    row['filed_gross_proceeds_hkdm']=gross
    row['filed_gross_proceeds_evidence']=row['gross_proceeds_hkdm_evidence']
    row['gross_proceeds_hkdm']=round(base,6)
    row['gross_proceeds_hkdm_evidence']=dict(row['gross_proceeds_hkdm_evidence'],value=round(base,6),basis_note=f'Base offer price × base Offer Shares; printed HK${gross:g}m includes over-allocation.')
   else:
    issues.append({'code':d['code'],'field':'gross_proceeds_hkdm','note':'Printed gross proceeds have a different, unestablished share basis; retained as filing evidence only.','value':gross,'base':base})
    row['filed_gross_proceeds_hkdm']=row.pop('gross_proceeds_hkdm');row['filed_gross_proceeds_evidence']=row.pop('gross_proceeds_hkdm_evidence')
  out.append(row)
 (ROOT/'data/batches/offer_number_review.json').write_text(json.dumps({'batch':'offer_number_review','reviewed_at':date.today().isoformat(),'deals':out},ensure_ascii=False,indent=1))
 (ROOT/'out/offer_number_issues.json').write_text(json.dumps(issues,ensure_ascii=False,indent=1))
 print({k:sum(k in r for r in out) for k in PATTERNS})
 for r in out:
  d=next(d for d in D if d['code']==r['code'])
  for k in PATTERNS:
   if k in r and d.get(k) is not None and abs(r[k]-d[k])>max(.02,abs(r[k])*.001):print('DIFFERENCE',r['code'],k,d[k],r[k])
if __name__=='__main__':main()
