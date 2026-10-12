"""Carry forward reviewed IPO facts and review cached filings for new stocks.
Ambiguous readings stay unresolved; they never overwrite reviewed facts.
"""
import hashlib,json,re
from pathlib import Path
from pypdf import PdfReader
from filing_review import subscriptions
from review_offer_numbers import read
from review_financial_numbers import rows as annual_rows
from review_lockups import events_from_pages
ROOT=Path(__file__).resolve().parent.parent
def main():
 D=json.loads((ROOT/'data/deals.json').read_text())['deals'];batches=ROOT/'data/batches';cache=ROOT/'scrape/pdf_cache'
 a={r['code']:r for r in json.loads((batches/'hkex_allotment_files.json').read_text())['manifest']};p={r['code']:r for r in json.loads((batches/'hkex_prospectus_links.json').read_text())['deals']}
 names=['subscription_review','offer_number_review','financial_number_review'];docs={};records={}
 for name in names:
  path=batches/(name+'.json');docs[name]=json.loads(path.read_text()) if path.exists() else {'batch':name,'deals':[]};records[name]={r['code']:r for r in docs[name]['deals']}
 locks=json.loads((batches/'lockup_events.json').read_text());known={e['code'] for e in locks['events']};updated=0
 for d in D:
  code=d['code']
  if all(code in records[n] for n in names) and code in known:continue
  sources=[]
  for typ,manifest in [('allot',a),('prosp',p)]:
   for part in manifest.get(code,{}).get('parts',[]):
    path=cache/part['file']
    if not path.exists() or not part.get('url'):continue
    try:
     raw=path.read_bytes();reader=PdfReader(path);pages=[pg.extract_text() or '' for pg in reader.pages[:75]]
     sources.append({'type':typ,'url':part['url'],'sha256':hashlib.sha256(raw).hexdigest(),'pages':pages})
    except Exception as ex:print('Source unavailable',code,part['file'],str(ex)[:100])
  for name in names:
   if code in records[name]:continue
   candidates={};result={'code':code}
   for s in sources:
    if name=='subscription_review' and s['type']=='allot':
     for key,ev in subscriptions(s['pages']).items():
      if isinstance(ev,dict):candidates.setdefault('oversub_public_mult' if key=='public' else 'oversub_intl_mult',[]).append(dict(ev,url=s['url'],sha256=s['sha256']))
    if name=='offer_number_review' and s['type']=='allot':
     for key,ev in read(s['pages']).items():
      if isinstance(ev,dict):candidates.setdefault(key,[]).append(dict(ev,url=s['url'],sha256=s['sha256']))
    if name=='financial_number_review' and s['type']=='prosp':
     rec=dict(s,pages=[{'page':i,'text':t} for i,t in enumerate(s['pages'],1)])
     for ev in annual_rows(rec,d['ipo_date']):candidates.setdefault(ev['field'],[]).append(ev)
   for field,hits in candidates.items():
    owners=[h for h in hits if h.get('basis')=='Net income attributable to owners'];hits=owners or hits
    vals=[h['value'] for h in hits]
    if max(vals)-min(vals)<=max(.00001,max(abs(v) for v in vals)*.000001):result[field]=hits[0]['value'];result[field+'_evidence']=hits[0]
    else:result[field+'_candidates']=hits
   # Preserve alternate proceeds bases; the canonical base offer is shares × price.
   base=d.get('final_price',0)*d.get('offer_shares',0)/1e6
   if result.get('gross_proceeds_hkdm') and base and abs(result['gross_proceeds_hkdm']-base)>max(.1,base*.001):
    result['filed_gross_proceeds_hkdm']=result.pop('gross_proceeds_hkdm');result['filed_gross_proceeds_evidence']=result.pop('gross_proceeds_hkdm_evidence')
   records[name][code]=result
  if code not in known:
   events=[]
   for s in sources:
    if s['type']=='allot':events.extend(dict(e,url=s['url'],sha256=s['sha256']) for e in events_from_pages(s['pages'],d['ipo_date']))
   if not any(e['category']=='Cornerstone' for e in events):events.insert(0,{'category':'Cornerstone','last_day_locked':None,'date_basis':'No cornerstone tranche' if d.get('cornerstone_none') else 'Expiry not established from available allotment filing','url':d.get('allotment_link')})
   seen=set()
   for e in events:
    key=(e['category'],e['last_day_locked'])
    if key in seen:continue
    seen.add(key);e.update(code=code,name=d['name'],sector=d['sector'],windows={},price_asof=locks['price_asof']);locks['events'].append(e)
  updated+=1
 for name in names:docs[name]['deals']=list(records[name].values());(batches/(name+'.json')).write_text(json.dumps(docs[name],ensure_ascii=True,indent=1))
 locks['stock_count']=len(D);(batches/'lockup_events.json').write_text(json.dumps(locks,ensure_ascii=True,indent=1));print('New stocks source-reviewed:',updated)
if __name__=='__main__':main()
