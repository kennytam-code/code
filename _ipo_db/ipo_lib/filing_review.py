"""Read subscriptions from their own tranche and retain auditable filing evidence."""
import argparse, json, re, sys
from bisect import bisect_right
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
NUM=r'\d[\d,]*(?:\.\d+)?'
LEVEL=re.compile(r'Subscription\s+level\s*(?:\([^)]{0,180}\))?\s*('+NUM+r')\s*(x?\s*times|%|x)?',re.I)
HEADING=re.compile(r'(?im)^[ \t]*(?:(?:HONG\s+KONG\s+)?PUBLIC\s+OFFER(?:R?ING)?|INTERNATIONAL\s+(?:OFFER(?:ING)?|PLACING)|PLACING|(?:[^\n]{0,30}\s+)?(?:EMPLOYEE\s+)?PREFERENTIAL\s+OFFERING)[ \t]*(?:\([^\n]*\))?[ \t]*$')

def flat(text):
    text=re.sub(r'\s+',' ',text).strip()
    text=re.sub(r'(?<=\d)\.\s+(?=\d)', '.',text)
    text=re.sub(r'(\d+\.\d+)\s+(\d+)(?=\s+times)',r'\1\2',text,flags=re.I)
    # Some embedded PDF fonts insert spaces inside words. Join only vocabulary
    # used in the subscription clauses, never arbitrary investor/company names.
    for word in ['International','Offering','Placing','representing','represents','approximately','initially','originally','available','subscription','subscribed','Shares','times','under','less','than','Pool','Public','Offer','number']:
        text=re.sub(r'(?<!\w)'+r'\s*'.join(word)+r'(?!\w)',word,text,flags=re.I)
    return text
def number(text):return float(text.replace(',',''))
def evidence(page,index,text,method,value,unit='times'):
    return {'value':value,'unit':unit,'method':method,'page':page,'_offset':index,'snippet':text[max(0,index-150):index+300]}

def subscriptions(pages):
    hits={'public':[],'intl':[]}
    for page,text in enumerate(pages,1):
        norm=flat(text)
        prefix=flat(pages[page-2])[-900:] if page>1 else ''
        for match in LEVEL.finditer(norm):
            pre=(prefix+' '+norm[:match.start()])[-900:]
            markers=[(m.start(),'intl') for m in re.finditer(r'(?:No\.|Number)\s+of\s+placees',pre,re.I)]
            markers += [(m.start(),'public') for m in re.finditer(r'(?:No\.|Number)\s+of\s+valid\s+applications',pre,re.I)]
            if not markers:continue
            marker,kind=max(markers)
            # Employee preferential tranches carry their own application count.
            # They must never stand in for the HK public or institutional book.
            # Prefer the actual standalone tranche heading. Parenthetical
            # exclusions of employee reserved shares are not employee headings.
            if kind=='public' and re.search(r'(?:employee|preferential)\s+Offering\s*$',pre[max(0,marker-120):marker],re.I):continue
            raw=(pages[page-2][-2000:]+'\n' if page>1 else '')+text
            labels=list(HEADING.finditer(raw))
            cutoff=len(flat(raw))-len(norm)+match.start()
            prior=[(len(flat(raw[:m.start()])),flat(m.group())) for m in labels if len(flat(raw[:m.start()]))<cutoff]
            if prior and re.search('employee|preferential',max(prior)[1].split('(')[0],re.I):continue
            v=number(match.group(1))/(100 if match.group(2)=='%' else 1)
            hits[kind].append(evidence(page,match.start(),norm,'tranche table',v))
        # Prose with an explicit named-tranche denominator. Do not read Pool A/B.
        for kind,tranche in [('public',r'(?:Hong\s+Kong\s+(?:Public\s+)?|Public\s+)Offer'),('intl',r'(?:International\s+(?:Offer|Placing)|Placing)')]:
            pat=re.compile(r'('+NUM+r')\s*times\s+(?:of\s+)?the\s+(?:total\s+)?(?:number\s+of\s+)?(?:'+NUM+r'\s+)?'+tranche+r'\s+Shares',re.I)
            for match in pat.finditer(norm):
                pre=norm[max(0,match.start()-220):match.start()];tail=norm[match.end():match.end()+220]
                # The pool label follows its denominator, not its demand.
                # Looking only backwards mistakes Pool A/B for the whole book.
                clause=re.split(r'[;•]|\.(?=\s+[A-Z])',tail,1)[0]
                if re.search(r'P\s*o\s*o\s*l\s*[AB]',clause,re.I):continue
                if re.search(r'(?:less than|more than|exceeds?|not exceeding|not more than|reached)\s*$',pre,re.I):continue
                if not re.search(r'represent|equivalent|approximately|about|amounted',pre[-65:],re.I):continue
                if not re.search(r'initially|originally|available',tail,re.I):continue
                hits[kind].append(evidence(page,match.start(),norm,'named-tranche denominator',number(match.group(1))))
        # A full demand sentence: both subject and basis belong to the tranche.
        # Decimal points are preserved; sentence splitting only follows punctuation
        # plus whitespace and a capital letter, bullet or end of page.
        sentences=re.split(r'(?<=[.!?])\s+(?=[A-Z•])',norm)
        offset=0
        for sentence in sentences:
            start=norm.find(sentence,offset);offset=max(offset,start+len(sentence))
            if len(sentence)>1400:continue
            kinds=[]
            if re.search(r'(?:Hong\s+Kong|Public)\s+(?:Public\s+)?Offer(?:ing)?',sentence,re.I):kinds.append('public')
            if re.search(r'International\s+(?:Offer(?:ing)?|Placing)|\bthe\s+Placing\b',sentence,re.I):kinds.append('intl')
            if len(kinds)!=1 or not re.search(r'subscrib|appli(?:cation|ed)',sentence,re.I):continue
            if re.search(r'Pool\s+[AB]|employee|retail claw|claw.?back.*(?:15|50|100)\s*times',sentence,re.I):continue
            pattern=re.compile(r'(?:represent(?:ing|s)\s+|approximately\s+(?:over\s+)?|about\s+)('+NUM+r')\s*(times|%)',re.I)
            for m in pattern.finditer(sentence):
                tail=sentence[m.end():]
                if m.group(2)=='%' and not re.search(r'under.?subscribed|not fully subscribed',sentence,re.I):continue
                if not re.search(r'subscrib|applications|applied',sentence[:m.start()],re.I):continue
                if not re.search(r'total|initially|originally|available|subscrib',tail,re.I) and m.group(2)!='%' and not re.search(r'initially offered.*over.?\s*subscribed\s*,?\s*by',sentence,re.I):continue
                if m.group(2)=='%' and not re.search(r'under.?subscribed|not fully subscribed',sentence,re.I):continue
                v=number(m.group(1))/(100 if m.group(2)=='%' else 1)
                if re.search(r'after (?:the )?reallocation',tail[:180],re.I):continue
                ev=evidence(page,start+m.start(),norm,'tranche demand sentence',v)
                if re.search(r'over.?\s*subscribed\s*,?\s*by\s+approximately',sentence,re.I):
                    ev['basis_note']='Filing says over-subscribed by; quoted multiple retained. Coverage versus excess not independently stated.'
                hits[kinds[0]].append(ev)
    answer={}
    for kind,records in hits.items():
        for r in records:r.pop('_offset',None)
        direct=[r for r in records if r['method']=='tranche table']
        selected=direct or records
        values=sorted({r['value'] for r in selected})
        # Repeated summaries and narrative descriptions may differ only by
        # published precision. Ambiguous large differences require review.
        if values and values[-1]-values[0]<=max(.011,values[-1]*.0005):
            choice=max(selected,key=lambda r:len(str(r['value']).split('.')[-1]))
            answer[kind]=choice
        elif values:answer[kind+'_ambiguous']=selected
    return answer

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cache-dir',type=Path,required=True);args=parser.parse_args()
    canonical=json.loads((ROOT/'data/deals.json').read_text())['deals']
    manifest={r['code']:r for r in json.loads((ROOT/'data/batches/hkex_allotment_files.json').read_text())['manifest']}
    out=[];issues=[]
    for deal in canonical:
        c=deal['code'];parts=manifest.get(c,{}).get('parts',[]);candidates=[]
        for part in parts:
            path=args.cache_dir/(part['file']+'.pages.json')
            if not path.exists():continue
            record=json.loads(path.read_text());readings=subscriptions(record['pages'])
            candidates.append(dict(record=record,readings=readings))
        row={'code':c,'files_reviewed':len(candidates),'subscription_basis':'Published own-tranche multiple; coverage / excess wording retained in evidence'}
        for kind,field in [('public','oversub_public_mult'),('intl','oversub_intl_mult')]:
            readings=[dict(x['readings'][kind],url=x['record']['url'],sha256=x['record']['sha256']) for x in candidates if kind in x['readings']]
            direct=[x for x in readings if x['method']=='tranche table'];readings=direct or readings
            if readings:
                vals=[x['value'] for x in readings]
                if max(vals)-min(vals)<=max(.011,max(vals)*.0005):
                    best=max(readings,key=lambda r:len(str(r['value']).split('.')[-1]));row[field]=best['value'];row[field+'_evidence']=best
                else:issues.append({'code':c,'field':field,'issue':'conflicting parts','readings':readings})
            else:
                issues.append({'code':c,'field':field,'issue':'no unambiguous reading','existing':deal.get(field),'candidates':[x['readings'].get(kind+'_ambiguous') for x in candidates if kind+'_ambiguous' in x['readings']]})
        out.append(row)
    manual_path=ROOT/'data/batches/subscription_manual_review.json'
    if manual_path.exists():
        by={r['code']:r for r in out}
        for decision in json.loads(manual_path.read_text()).get('decisions',[]):
            row=by[decision['code']];field=decision['field']
            if decision.get('value') is not None:row[field]=decision['value'];row[field+'_evidence']=decision
            else:row.setdefault('withdraw_fields',[]).append(field);row[field+'_note']=decision['reason']
            issues=[x for x in issues if not (x['code']==decision['code'] and x['field']==field)]
    (ROOT/'data/batches/subscription_review.json').write_text(json.dumps({'batch':'subscription_review','reviewed_at':date.today().isoformat(),'count':len(out),'deals':out},ensure_ascii=False,indent=1))
    report={'count':len(out),'public_verified':sum('oversub_public_mult' in r for r in out),'intl_verified':sum('oversub_intl_mult' in r for r in out),'issues':issues}
    (ROOT/'out/subscription_review_candidates.json').write_text(json.dumps(report,ensure_ascii=False,indent=1))
    print({k:v for k,v in report.items() if k!='issues'},'issues',len(issues))

if __name__=='__main__':main()
