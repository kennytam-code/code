"""Conservative prospectus annual-row review; ambiguous values are candidates."""
import argparse,json,re
from pathlib import Path
from extract_financials import clean_text,tonum,FX
ROOT=Path(__file__).resolve().parent.parent
NUMBER=re.compile(r'\(?-?\d[\d,]*(?:\.\d+)?\)?')
LABELS={'rev_latest':re.compile(r'^\s*(?:Total\s+)?Revenue[s]?(?:\s+from\s+contracts\s+with\s+customers)?\s*[.·…\s]*',re.I),
 'ni_latest':re.compile(r'^\s*(?:Net\s+(?:profit|loss)(?:\s+for\s+the\s+(?:year/period|year|period))?|(?:Profit|Loss|Profit/\(loss\)|\(Loss\)/profit)\s+for\s+the\s+(?:year/period|year|period))\s*[.·…\s]*',re.I)}
OWNER=re.compile(r'^\s*(?:Owners|Equity\s+(?:holders|shareholders)|Shareholders)\s+of\s+(?:the\s+)?(?:Company|parent)\s*[.·…\s]*',re.I)
def values(tail,count,header):
 tail=re.sub(r'[–—]', ' 0 ',tail)
 if re.search(r'[A-Za-z]',tail):return None
 tokens=NUMBER.findall(tail)
 while tokens and re.fullmatch(r'\([1-9]\)',tokens[0]):tokens.pop(0)
 vals=[tonum(t) for t in tokens]
 if len(vals) in [4,6,8,10,12] and '%' in header and all(abs(v)<=100 for v in vals[1::2]):vals=vals[::2]
 return vals if len(vals) in [count,count+2] else None
def rows(record,ipo_date):
 out=[]
 for page in record['pages']:
  fixed=re.sub(r'(?<!\d)(\d(?:\s+\d){1,2}),(\d{3})(?!\d)',lambda m:re.sub(r'\s+','',m.group(1))+','+m.group(2),page['text'])
  fixed=re.sub(r'(?i)R\s+e\s+v\s+e\s+n\s+u\s+e', 'Revenue',fixed)
  # Pypdf joins adjacent comma-grouped figures after a one-decimal value.
  fixed=re.sub(r'(\d\.\d)(?=\d{1,3},\d{3})',r'\1 ',fixed)
  lines=clean_text(fixed).splitlines()
  for i,line in enumerate(lines):
   for field,pat in LABELS.items():
    m=pat.match(line)
    if not m:continue
    tail=line[m.end():]
    tail=re.sub(r'[–—]', ' 0 ',tail)
    if '%' in tail and all('%' in token for token in tail.split() if re.search(r'\d',token)):continue
    if re.search(r'[A-Za-z]',tail):continue
    tokens=NUMBER.findall(tail)
    while tokens and re.fullmatch(r'\([1-9]\)',tokens[0]):tokens.pop(0)
    if not tokens:continue
    before=lines[max(0,i-70):i];header='\n'.join(before)[-6000:]
    ylines=[s for s in before if len(re.findall(r'(?<!\d)20\d{2}(?!\d)|FY\d{2}',s))>=2]
    if not ylines:continue
    yidx=before.index(ylines[-1]);caption=' '.join(before[max(0,yidx-8):yidx+1])
    if not re.search(r'Y\s*ears?\s+ended|financial\s+years?|FY\d{2}',caption,re.I):continue
    if re.search(r'financial statement balances.*VIE|VIEs and their subsidiaries',header,re.I):continue
    years=re.findall(r'(?<!\d)20\d{2}(?!\d)|FY\d{2}',ylines[-1]);years=[int('20'+y[2:]) if y.startswith('FY') else int(y) for y in years]
    count=next((j for j in range(1,len(years)) if years[j]<=years[j-1]),len(years))
    if count not in [2,3] or max(years[:count])>=int(ipo_date[:4]):continue
    vals=values(tail,count,header)
    if vals is None:continue
    currency=re.findall(r'(RMB|HK\$|US\$)\s*[’\x27]?\s*000|(?:\(|\b)(RMB|HK\$|US\$)\s+(?:in\s+)?(?:thousands|millions)',header,re.I)
    cur=(currency[-1][0] or currency[-1][1]).upper() if currency else None
    if not cur and re.search(r'in\s+thousands|in\s+millions',header,re.I):
     currencies=set(re.findall(r'RMB|HK\$|US\$',header,re.I))
     if len(currencies)==1:cur=next(iter(currencies)).upper()
    if not cur:continue
    unit='millions' if re.search(r'(?:RMB|HK\$|US\$)\s+(?:in\s+)?millions|\(in\s+millions',header,re.I) and not re.search(r'(?:RMB|HK\$|US\$)\s*[’\x27]?\s*000',header,re.I) else 'thousands'
    value=vals[count-1]*FX[cur]/(1000 if unit=='thousands' else 1)
    if field=='ni_latest' and re.match(r'^\s*(?:Net\s+)?Loss',line,re.I) and vals[count-1]>0:value=-value
    if field=='rev_latest' and value<0:continue
    ev={'field':field,'value':round(value,6),'native_value':vals[count-1],'currency':cur,'unit':unit,'financial_year':years[count-1],'page':page['page'],'row':line.strip(),'header':header,'url':record['url'],'sha256':record['sha256'],'basis':'Revenue' if field=='rev_latest' else 'Consolidated net income','method':'Explicit annual table row; database FX convention '+str(FX[cur])}
    out.append(ev)
    if field=='ni_latest':
     for following in lines[i+1:i+12]:
      if re.search(r'comprehensive\s+(?:income|loss)',following,re.I):break
      om=OWNER.match(following)
      if not om:continue
      own=values(following[om.end():],count,header)
      if own is not None:
       native=own[count-1];amount=native*FX[cur]/(1000 if unit=='thousands' else 1)
       out.append(dict(ev,value=round(amount,6),native_value=native,row=following.strip(),basis='Net income attributable to owners'))
       break
 return out
def main():
 p=argparse.ArgumentParser();p.add_argument('--cache-dir',type=Path,required=True);a=p.parse_args();D=json.loads((ROOT/'data/deals.json').read_text())['deals'];out=[]
 for d in D:
  candidates=[]
  for f in a.cache_dir.glob(f'prosp_{d["code"]}_*.pages.json'):
   try:candidates+=rows(json.loads(f.read_text()),d['ipo_date'])
   except Exception as ex:print('SOURCE ERROR',f.name,str(ex))
  row={'code':d['code']}
  for field in LABELS:
   hits=[x for x in candidates if x['field']==field]
   if hits:
    latest=max(x['financial_year'] for x in hits);hits=[x for x in hits if x['financial_year']==latest]
   owner=[x for x in hits if x.get('basis')=='Net income attributable to owners']
   if owner:hits=owner
   distinct={x['value'] for x in hits}
   if len(distinct)==1:row[field]=hits[0]['value'];row[field+'_evidence']=hits[0]
   else:row[field+'_candidates']=hits
  out.append(row)
 (ROOT/'data/batches/financial_number_review.json').write_text(json.dumps({'batch':'financial_number_review','deals':out},ensure_ascii=False,indent=1))
 print({f:sum(f in r for r in out) for f in LABELS})
 for r in out:
  d=next(x for x in D if x['code']==r['code'])
  for f in LABELS:
   if f in r and d.get(f) is not None and abs(r[f]-d[f])>max(.15,abs(r[f])*.001):print('DIFFERENCE',r['code'],f,d[f],r[f])
if __name__=='__main__':main()
