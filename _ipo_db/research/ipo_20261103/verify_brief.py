"""Check the dated inputs, rendered financial tables and preserved template package.

Run with bundled Python after build_brief.py and render_docx.py. This validates
arithmetic and delivery consistency, not independent primary-source accuracy.
"""
from pathlib import Path
from zipfile import ZipFile
from datetime import date, timedelta
import hashlib, json, math, sys
from lxml import etree
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
DOC = WORK / 'IPO_and_Lockup_Trader_Brief_2026-11-03.docx'
TEMP = Path('/private/tmp/ipo-20261103')
PDF = TEMP / 'final-render' / (DOC.stem + '.pdf')
A = json.loads((HERE/'source_and_valuation_audit.json').read_text())
C = json.loads((HERE/'price_crosscheck.json').read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
checks = 0
def check(value, label):
    global checks
    assert value, label
    checks += 1
def close(a,b,label): check(math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-9),label)
def multiple(v): return 'n/v' if v is None else v if isinstance(v,str) else f'{v:,.1f}x'
def span(x,k):
    a,b=x[k+'_low'],x[k+'_high']
    return multiple(a) if a==b else f'{a:.1f}–{b:.1f}x'

check(C['count']==24 and len(C['crosschecks'])==24,'quote count')
for q in C['crosschecks']:
    check(q['date']=='2026-11-02' and q['match'],'independent quote date')
    close(q['sina'],A['quotes'][q['code']]['price'],'Sina/Tencent price parity')
fx=A['fx']['cny_per_hkd']
for code,x in A['issuers'].items():
    for s in ('low','mid','high'):
        cap=x[s]*x['shares']*fx/1e6
        close(cap,x['equity_cnym_'+s],code+' equity')
        close(cap/x['rev25'],x['ps25_'+s],code+' PS')
        if x['np25']>0: close(cap/x['np25'],x['pe25_'+s],code+' PE')
        else: check(x['pe25_'+s]=='NM',code+' loss PE')
    for yr in ('26','27'):
        profit=x['fy'+yr+'_np']
        if profit: close(x['equity_cnym_mid']/profit,x['pe'+yr],code+' forward PE')
        else: check(x['pe'+yr] is None,code+' unavailable forecast')
    close(x['ltm_rev'],x['rev25']+x['rev_now']-x['rev_prev'],code+' LTM sales')
    close(x['ltm_np'],x['np25']+x['np_now']-x['np_prev'],code+' LTM earnings')
for code,p in A['peers'].items():
    close(p['ps25'],p['equity_profit_m']/p['rev25'],code+' PS')
    for yr in ('25','26','27'):
        profit=p['np25'] if yr=='25' else p['fy'+yr+'_np']
        if profit is None: check(p['pe'+yr] is None,code+' unavailable')
        elif profit<=0: check(p['pe'+yr]=='NM',code+' negative earnings')
        else: close(p['pe'+yr],p['equity_profit_m']/profit,code+' PE')
for code in ('2687','1333'):
    x=A['issuers'][code]
    check((date.fromisoformat(x['first_release'])-date.fromisoformat(x['last_locked'])).days==1,code+' release boundary')
    check(len(x['daily_turnover'])==14,code+' ADV sessions')
    close(sum(v['shares'] for v in x['daily_turnover'])/14,x['adv_shares'],code+' ADV')
    close(x['unlock_h']/x['adv_shares'],x['unlock_adv'],code+' supply ratio')
check(sum([63376798,31101004,2370189,3091551,2576293])==A['issuers']['1333']['unlock_h'],'Breton cohort')
check(A['issuers']['1333']['unlock_h']-3091551==99424284,'Qiu exclusion')
check(23066820+32219280==A['issuers']['2687']['unlock_h'],'Able cohort')
for k,r in A['primary_documents'].items():
    check(sha(TEMP/(k+'.pdf'))==r['sha256'],k+' retained source hash')

NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W='{'+NS['w']+'}'
template=Path(A['template']['path'])
check(sha(template)==A['template']['sha256'],'template unchanged')
with ZipFile(template) as t, ZipFile(DOC) as z:
    check(set(t.namelist())==set(z.namelist()),'package members')
    changed=[n for n in t.namelist() if t.read(n)!=z.read(n)]
    check(set(changed)=={'word/document.xml','word/_rels/document.xml.rels'},'only approved OOXML changes')
    root=etree.fromstring(z.read('word/document.xml'))
tables=root.findall('.//w:tbl',NS)
check(len(tables)==21,'table count')
for t in tables:
    check(sum(int(x.get(W+'w')) for x in t.findall('w:tblGrid/w:gridCol',NS))==9972,'table width')
    check(not t.findall('.//w:trHeight',NS),'no fixed row heights')
text=' '.join(root.xpath('//w:t/text()',namespaces=NS))
check('Jinzhuo Hengbang Technology (Beijing) Co., Ltd.' in text,'Sina legal name')
check('Suzhou Industrial Park Jinzhuo' not in text,'incorrect legal name absent')
check('7.7–8.7' not in text and text.count('7.8–8.7')==3,'Xinde rounding consistent')
check('pre-results, pre-penalty forecast' in text,'Able forecast caveat')
check('2 November 2026 closes' in text,'common date visible')
vals=[t for t in tables if ''.join(t.find('w:tr',NS).xpath('.//w:t/text()',namespaces=NS)).startswith('CompanyPrice')]
keys=[('2206',['570 HK','2273 HK','300181 A']),('7672',['522 HK','600584 A','688362 A']),('9917',['9903 HK','6082 HK','688795 A']),('2681',['9976 HK','301308 A','688525 A']),('2687',['777 HK','2469 HK','300559 A']),('1333',['631 HK','1157 HK','000528 A'])]
check(len(vals)==6,'six valuation tables')
for t,(code,peers) in zip(vals,keys):
    rows=[[ ''.join(c.xpath('.//w:t/text()',namespaces=NS)) for c in r.findall('w:tc',NS)] for r in t.findall('w:tr',NS)[1:]]
    x=A['issuers'][code]
    check(rows[0][2:4]==[span(x,'ps25'),span(x,'pe25')],code+' displayed historical ratios')
    check([s.rstrip('†') for s in rows[0][4:]]==[multiple(x['pe26']),multiple(x['pe27'])],code+' displayed forward ratios')
    for row,k in zip(rows[1:],peers):
        p=A['peers'][k]
        check([s.rstrip('†') for s in row[2:]]==[multiple(p[n]) for n in ('ps25','pe25','pe26','pe27')],k+' displayed ratios')
pdf=PdfReader(str(PDF))
check(len(pdf.pages)==11,'11 rendered pages')
page_text=[p.extract_text() for p in pdf.pages]
for i,key in enumerate(['November IPO','2206','7672','9917','2681','2687','1333','Cornerstones','Lockup supply','Forecast inputs','Sources and evidence']):
    check(key in page_text[i][:150],f'page {i+1} begins correctly')
check(len(list(PDF.parent.glob('page-*.png')))==11,'11 page PNGs')
qa=json.loads((HERE/'document_qa.json').read_text())
check(qa['document_sha256']==sha(DOC),'final document hash')
qa.update(checks_passed=checks,rendered_pages=11,quote_crosschecks=24,primary_source_files=len(A['primary_documents']),arithmetic_is_not_independent_source_verification=True,live_bloomberg_tested=False,live_borrow_verified=False)
(HERE/'document_qa.json').write_text(json.dumps(qa,indent=2))
print(json.dumps({'passed':checks,'pages':11,'sha256':sha(DOC)}))
