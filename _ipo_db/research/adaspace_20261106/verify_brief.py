"""Check formulas, displayed values, template fidelity and final delivery hashes.
This is an arithmetic/package check, not independent financial-source verification.
The review PDF is temporary and is not a published deliverable.
"""
from pathlib import Path
from zipfile import ZipFile
import hashlib,json,math,argparse
from lxml import etree
from pypdf import PdfReader
H=Path(__file__).resolve().parent;WORK=H.parents[1]
D=WORK/'Adaspace_IPO_Trader_Brief_2026-11-06.docx'
parser=argparse.ArgumentParser();parser.add_argument('--pdf',type=Path,required=True);args=parser.parse_args()
A=json.loads((H/'source_and_valuation_audit.json').read_text());C=json.loads((H/'price_crosscheck.json').read_text())
x=A['issuer'];checks=[]
def check(ok,label):
 assert ok,label
 checks.append(label)
def close(a,b,label):check(math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-8),label)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
fx=A['fx']['RMB_per_HKD']
check(A['fx']['date']=='2026-11-05','FX date')
check(x['post_H_shares']+x['post_domestic_shares']==x['post_shares'],'H and domestic share reconciliation')
check(x['base_new_shares']+x['size_option_shares']+x['max_greenshoe_if_size_option']==39834900,'maximum optional new shares')
close(x['ltm_revenue'],702.703+226.110-241.322,'issuer LTM')
for pt in ['low','mid','high']:
 cap=x[pt]*x['post_shares']/1e6
 close(cap,x['cap_HKDm_'+pt],pt+' HK equity')
 close(cap*fx,x['cap_RMBm_'+pt],pt+' RMB equity')
 close(cap*fx/702.703,x['ps_annual_'+pt],pt+' annual PS')
 close(cap*fx/687.491,x['ps_ltm_'+pt],pt+' LTM PS')
 close(cap*fx/3475,x['price_to_order_'+pt],pt+' order ratio')
 gross=x[pt]*x['base_new_shares']/1e6
 close(gross-60,x['tradable_base_HKDm_'+pt],pt+' tradable offer')
 close(60/gross*100,x['cornerstone_deal_pct_'+pt],pt+' cornerstone fraction')
 close((gross-60)/cap*100,x['tradable_base_total_pct_'+pt],pt+' tradable equity fraction')
 close((cap*fx/11553.6-1)*100,x['private_postmoney_premium_pct_'+pt],pt+' private postmoney premium')
 close(((cap-gross)*fx/11553.6-1)*100,x['private_premoney_premium_pct_'+pt],pt+' private premoney premium')
r=x['receivables']
for pre in ['FY25','June26']:close(r[pre+'_gross']-r[pre+'_allowance'],r[pre+'_net'],pre+' net receivables')
check(round((r['FY25_gross']+r['June26_gross'])/2/226.110*180,1)==610.8,'gross receivable days')
close(x['adjusted_group_profit'][4],x['group_net_profit'][4]+x['H126_share_pay']+x['H126_listing_costs'],'adjusted loss bridge')
close(sum(x['use_of_net_proceeds_pct'].values()),100,'proceeds allocation')
close(sum(c['HKDm'] for c in x['cornerstones']),60,'cornerstone total')
close(x['EV_sales_mid'],(x['cap_RMBm_mid']-3513.487-772.4*fx)/702.703,'treasury-adjusted EV')
for p,quote in zip(A['peers'],C['crosschecks']):
 code=p['code'];check(code==quote['code'],code+' quote identity')
 close(p['price'],quote['used_price'],code+' quote price')
 close(p['equity_m'],p['price']*p['shares']/1e6,code+' equity')
 close(p['annual_ps'],p['equity_m']/p['annual_revenue'],code+' PS')
 if 'latest_period_revenue' in p:
  close(p['ltm_revenue'],p['annual_revenue']+p['latest_period_revenue']-p['prior_period_revenue'],code+' LTM')
  close(p['ltm_ps'],p['equity_m']/p['ltm_revenue'],code+' LTM PS')
 if p['annual_owner_profit'] and p['annual_owner_profit']>0:close(p['annual_pe'],p['equity_m']/p['annual_owner_profit'],code+' PE')
 check(p['FY26E_PE'] is None and p['FY27E_PE'] is None,code+' no fabricated forward estimates')
 if 'forward_sales_range' in p:close(p['forward_ps_mid'],p['equity_m']/(sum(p['forward_sales_range'])/2),code+' guidance PS')
 if code.endswith(('HK','A')):check(quote['independent_price_match'],code+' independent close match')
check(C['HK_A_independent_matches']==4,'all included HK/A quotes crosschecked')
T=Path(A['template']['path']);check(sha(T)==A['template']['sha256'],'original template untouched')
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'};W='{'+NS['w']+'}'
with ZipFile(T) as zt,ZipFile(D) as zd:
 check(set(zt.namelist())==set(zd.namelist()),'all template parts retained')
 changed=[n for n in zt.namelist() if zt.read(n)!=zd.read(n)]
 check(set(changed)=={'word/document.xml','word/_rels/document.xml.rels'},'only body and hyperlink parts changed')
 root=etree.fromstring(zd.read('word/document.xml'));tr=etree.fromstring(zt.read('word/document.xml'))
 check(etree.tostring(root.find('.//w:sectPr',NS))==etree.tostring(tr.find('.//w:sectPr',NS)),'section geometry unchanged')
 rel=etree.fromstring(zd.read('word/_rels/document.xml.rels'))
 check(len({e.get('Id') for e in rel})==len(rel),'unique relationship IDs')
 alltext=' '.join(root.xpath('//w:t/text()',namespaces=NS))
 check('Guotai Junan Capital Limited' in alltext,'sponsor legal identity')
 check('Kamshin Oriental (HK) Limited' in alltext,'cornerstone legal identity')
 check('18.3–24.4x' in alltext and '19.2–25.6x' not in alltext,'corrected IPO PS displayed')
 check('15%' in alltext and '24.90' in alltext,'discretionary reallocation visible')
 check('FY27E is n/v' in alltext,'forward estimate limitation visible')
 check('5 November 12:04 ET intraday' in alltext,'US intraday disclosed')
 check('RMB747.2m' in alltext and 'RMB597.8m' in alltext,'gross and net not confused')
 tables=root.findall('.//w:tbl',NS);check(len(tables)==6,'six tables')
 for t in tables:
  check(sum(int(c.get(W+'w')) for c in t.findall('w:tblGrid/w:gridCol',NS))==9972,'fixed table width')
  check(not t.findall('.//w:trHeight',NS),'no fixed row heights')
 val=tables[2]
 rows=[[''.join(c.xpath('.//w:t/text()',namespaces=NS)) for c in row.findall('w:tc',NS)] for row in val.findall('w:tr',NS)[1:]]
 check(rows[0][3:5]==['18.3–24.4x','18.7–24.9xJun 26'],'issuer displayed ratios')
 for p,row in zip(A['peers'],rows[1:]):
  check(row[3].rstrip('†*')==f'{p["annual_ps"]:.1f}x',p['code']+' displayed annual PS')
  check(row[5]==(f'{p["annual_pe"]:,.0f}x' if p['annual_pe'] else 'N/M'),p['code']+' displayed PE')
  if p['ltm_ps']:check(row[4].startswith(f'{p["ltm_ps"]:.1f}x'),p['code']+' displayed LTM PS')
 pdf=PdfReader(args.pdf);check(len(pdf.pages)==5,'five rendered pages')
 expected=['IPO trader briefing','Earnings quality','Valuation','Offer structure','Sources, valuation']
 for i,(page,title) in enumerate(zip(pdf.pages,expected),1):
  check(title in page.extract_text()[:180],f'page {i} heading')
  check(len(page.extract_text())>1000,f'page {i} not blank')
 check(len(list(args.pdf.parent.glob('page-*.png')))==5,'five rendered page images')
qa=json.loads((H/'document_qa.json').read_text());check(qa['document_sha256']==sha(D),'final doc hash')
qa.update(checks_passed=len(checks),checks=checks,rendered_pages=5,quote_crosschecks=4,US_price_basis='2 intraday quotes; no independent same-second match',arithmetic_is_not_independent_source_verification=True,live_bloomberg_tested=False)
(H/'document_qa.json').write_text(json.dumps(qa,indent=2)+'\n')
print(json.dumps({'checks_passed':len(checks),'pages':5,'document_sha256':sha(D)}))
