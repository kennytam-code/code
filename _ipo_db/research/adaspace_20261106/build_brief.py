"""Build the listed IPO trader brief from the retained user template and dated audit.
Only document.xml and document.xml.rels change. No workbook/database mutation.
Run with bundled Python. Optional --template and --output paths.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from copy import deepcopy
from lxml import etree
import argparse,hashlib,json,re,resource
HERE=Path(__file__).resolve().parent
WORK=HERE.parents[1]
T=Path('/private/tmp/adaspace-20261106');T.mkdir(exist_ok=True)
parser=argparse.ArgumentParser()
parser.add_argument('--template',type=Path,default=Path('/Users/lemon/Downloads/ipo analysis.docx'))
parser.add_argument('--output',type=Path,default=WORK/'Adaspace_IPO_Trader_Brief_2026-11-06.docx')
args=parser.parse_args()
A=json.loads((HERE/'source_and_valuation_audit.json').read_text());I=A['issuer'];P=A['peers']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(args.template)==A['template']['sha256']
with ZipFile(args.template) as z:original={n:z.read(n) for n in z.namelist()}
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships';PK='http://schemas.openxmlformats.org/package/2006/relationships'
NS={'w':W,'r':R};q=lambda n:'{'+W+'}'+n
root=etree.fromstring(original['word/document.xml']);body=root.find('w:body',NS);donors=[deepcopy(e) for e in body]
rels=etree.fromstring(original['word/_rels/document.xml.rels'])
base_rpr=deepcopy(donors[28].find('w:r/w:rPr',NS));title_rpr=deepcopy(donors[26].find('w:r/w:rPr',NS));heading_rpr=deepcopy(donors[30].find('w:r/w:rPr',NS))
def prop(p,name,**attrs):
 e=p.find(q(name))
 if e is None:e=etree.SubElement(p,q(name))
 for k,v in attrs.items():e.set(q(k),str(v))
 return e

def run(p,text,bold=False,underline=False,role='body'):
 r=etree.SubElement(p,q('r'))
 rp=deepcopy(title_rpr if role=='title' else heading_rpr if role=='heading' else base_rpr)
 if bold:prop(rp,'b')
 if underline:prop(rp,'u',val='single')
 if re.search('[\u3400-\u9fff]',text):
  fonts=prop(rp,'rFonts',eastAsia='Hiragino Sans GB')
  fonts.attrib.pop(q('eastAsiaTheme'),None)
 r.append(rp)
 for j,s in enumerate(text.split('\n')):
  if j:etree.SubElement(r,q('br'))
  t=etree.SubElement(r,q('t'));t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=s
 return r

def para(text='',kind='body',before=0,after=65,keep=False,pagebreak=False):
 p=deepcopy(donors[32 if kind=='bullet' else 30 if kind=='heading' else 26 if kind=='title' else 28])
 for x in list(p):
  if x.tag!=q('pPr'):p.remove(x)
 pp=p.find(q('pPr'))
 for name in ['pageBreakBefore','keepNext','keepLines','spacing','tabs','contextualSpacing']:
  for x in pp.findall(q(name)):pp.remove(x)
 prop(pp,'spacing',before=before,after=after,line=240,lineRule='auto');prop(pp,'keepLines')
 if kind in ['heading','title'] or keep:prop(pp,'keepNext')
 if pagebreak:prop(pp,'pageBreakBefore')
 if kind in ['heading','title']:run(p,text,role=kind)
 else:
  for j,s in enumerate(re.split(r'\*\*(.*?)\*\*',text)):
   if s:run(p,s,bold=bool(j%2))
 return p

def hyperlink(p,label,url):
 used={x.get('Id') for x in rels};n=1
 while 'rId'+str(n) in used:n+=1
 rid='rId'+str(n)
 etree.SubElement(rels,'{'+PK+'}Relationship',Id=rid,Type=R+'/hyperlink',Target=url,TargetMode='External')
 h=etree.SubElement(p,q('hyperlink'));h.set('{'+R+'}id',rid);run(h,label,underline=True)

def source(label,links):
 p=para('',after=55);run(p,label,bold=True)
 for j,(name,url) in enumerate(links):
  if j:run(p,'; ')
  hyperlink(p,name,url)
 return p

def table(headers,rows,widths,overview=False,left_cols=(0,),keep=True):
 assert sum(widths)==9972
 donor=donors[27 if overview else 37]
 t=deepcopy(donor)
 for x in list(t):
  if x.tag==q('tr'):t.remove(x)
 tp=t.find(q('tblPr'));prop(tp,'tblW',w=9972,type='dxa');prop(tp,'tblLayout',type='fixed');prop(tp,'tblInd',w=0,type='dxa')
 for x in tp.findall(q('tblpPr')):tp.remove(x)
 borders=prop(tp,'tblBorders')
 for n in ['top','left','bottom','right','insideH','insideV']:prop(borders,n,val='single',sz=4,space=0,color='D9D9D9')
 margins=prop(tp,'tblCellMar')
 for n,v in [('top',65),('bottom',65),('left',65),('right',65)]:prop(margins,n,w=v,type='dxa')
 grid=t.find(q('tblGrid'))
 for x in list(grid):grid.remove(x)
 for width in widths:etree.SubElement(grid,q('gridCol')).set(q('w'),str(width))
 orig_rows=donor.findall('w:tr',NS)
 head=orig_rows[0].findall('w:tc',NS);cells=orig_rows[1].findall('w:tc',NS)
 for ri,values in enumerate([headers]+rows):
  assert len(values)==len(widths)
  tr=etree.SubElement(t,q('tr'));trp=etree.SubElement(tr,q('trPr'));prop(trp,'cantSplit')
  if ri==0:prop(trp,'tblHeader')
  for ci,value in enumerate(values):
   ds=head if ri==0 else cells;c=deepcopy(ds[min(ci,len(ds)-1)])
   cp=c.find(q('tcPr'))
   if cp is None:cp=etree.Element(q('tcPr'));c.insert(0,cp)
   for n in ['gridSpan','vMerge','tcMar','tcBorders','shd']:
    for x in cp.findall(q(n)):cp.remove(x)
   prop(cp,'tcW',w=widths[ci],type='dxa');prop(cp,'vAlign',val='center')
   if ri==0:prop(cp,'shd',val='clear',color='auto',fill='F2F2F2')
   for x in list(c):
    if x.tag!=q('tcPr'):c.remove(x)
   p=para('',after=0);pp=p.find(q('pPr'));prop(pp,'jc',val='left' if overview or ci in left_cols else 'center')
   for x in pp.findall(q('ind')):pp.remove(x)
   run(p,str(value),bold=ri==0 or ci==0)
   if keep and ri<len(rows):prop(pp,'keepNext')
   c.append(p);tr.append(c)
 return t

for x in list(body):body.remove(x)
out=body.append
S=A['sources'];RFS={}
def fmt(v):return 'n/v' if v is None else v if isinstance(v,str) else f'{v:,.1f}x'
def rangefmt(x,k):
 a,b=x[k+'_low'],x[k+'_high'];return fmt(a) if a==b else f'{a:.1f}–{b:.1f}x'
def textp(t,**kw):out(para(t,**kw))
def bullet(t):out(para(t,kind='bullet',after=70))
def head(t):out(para(t,kind='heading',before=95,after=75))
def sources(label,ls):out(source(label,ls))
def doc(k):return RFS[k]['url']
def page_title(text,new=True):
 p=para(text,kind='title',after=120,pagebreak=new)
 for rp in p.findall('w:r/w:rPr',NS):prop(rp,'sz',val=28);prop(rp,'szCs',val=28)
 out(p)

def n(v):return f'{v:,.1f}'
def xr(a,b):return f'{a:.1f}–{b:.1f}x'
x=I
page_title('國星宇航  06935 HK  |  IPO trader briefing',False)
textp('Adaspace  •  6 November 2026, before Hong Kong open',after=105)
textp('**Desk view: credible orders and a strong balance sheet support the space-AI trade. The IPO still prices in a major commercial ramp. Prefer the lower end; the upper end needs evidence that high margins survive delivery and customers pay. Thin supply can drive a squeeze, but does not establish fair value.**',after=110)
out(table(['Offer snapshot','Base offer; options excluded'],[
 ['Price / full equity value','HK$24.90–33.20 / HK$15.0–20.0bn'],
 ['Valuation',xr(x['ps_annual_low'],x['ps_annual_high'])+' FY25 sales; '+xr(x['ps_ltm_low'],x['ps_ltm_high'])+' LTM sales'],
 ['Timetable','Closes 10 Nov; pricing 11 Nov; allocations/grey market 12 Nov; expected listing 13 Nov'],
 ['Deal / board lot','30.121m new shares (~5%); HK$750m–1.0bn gross; 100 shares, HK$3,353.48 maximum entry'],
 ['Sole sponsor','Guotai Junan Capital Limited']
],[2900,7072],overview=True))
head('Good points — why the stock can attract capital')
bullet('**A tangible AI infrastructure theme.** Processing data in orbit can reduce downlink congestion and response time. Satellite-related revenue reached 57.7% of H1 sales, versus 0.6% in 2023. HK-listed exposure is unusual; the recurring compute-service business is still to be proven.')
bullet('**A sizeable pipeline with funding to execute.** 114 pending AI satellites carried RMB3.475bn of contract value on 20 October, about 4.9x FY25 sales. September cash and financial investments totalled RMB3.93bn before IPO proceeds. Financing risk is less immediate than delivery and collection risk.')
bullet('**Low initial supply can amplify the theme.** The base deal excluding cornerstones is only 4.6–4.7% of total equity. Sector policy, successful launches and paid AI deployments can create catalysts. This is a supply argument, not evidence of committed long-only demand.')
head('Risks — what can break the trade')
bullet('**The margin rebound is not yet a repeatable delivery margin.** H1 AI-computing gross margin reached 55.4%, but no satellites completed orbital delivery in that half. Milestone revenue, contract mix and launch costs can fall in different periods. FY26 loss is guided to widen.')
bullet('**Cash collection is the fundamental weak point.** June gross receivables were RMB747m; RMB228m were over two years old. Only 21% of the June balance was collected by 20 October. The prospectus expects FY26 operating cash flow to turn negative despite a positive first half.')
bullet('**Demand concentration and supply risks remain.** Five customers supplied 91.1% of H1 sales. Launch capacity, approvals and failures can delay conversion. Cornerstones cover only 6–8% of the offer; most international placement shares are not cornerstone-locked.')
textp('**What changes the view:** repeated deliveries at healthy margins plus cash receipts strengthen the case. A strong debut, a headline partnership or a high subscription multiple alone does not.',before=80,after=0)

page_title('Earnings quality, cash and the AI opportunity')
out(table(['RMBm, except margin','FY24','FY25','H1 25','H1 26'],[
 ['Revenue']+[n(x['revenue'][i]) for i in [1,2,3,4]],
 ['Gross margin']+[f'{100*x["gross_profit"][i]/x["revenue"][i]:.1f}%' for i in [1,2,3,4]],
 ['Reported group profit / (loss)']+[n(x['group_net_profit'][i]) for i in [1,2,3,4]],
 ['Adjusted group profit / (loss)']+[n(x['adjusted_group_profit'][i]) for i in [1,2,3,4]],
 ['Operating cash flow']+[n(x['CFO'][i]) for i in [1,2,3,4]],
 ['R&D expense']+[n(x['R_and_D'][i]) for i in [1,2,3,4]]
],[3572,1600,1600,1600,1600]))
textp('H1 adjusted loss removes RMB71.2m of share-based pay and RMB14.2m of listing costs. R&D of RMB108.6m still exceeded gross profit of RMB88.9m: improving gross margin has yet to cover the operating cost base.',before=70,after=65)
head('Good points — genuine commercial progress')
bullet('**The orders have industrial substance.** FY25 completed 12 satellite deliveries. For ten satellites funded through customer finance leases, 77.8% of the contracted amount had reached the company by 20 October. The RMB3.475bn pipeline spans periods; contract value is not one year of future sales or necessarily all still unrecognised.')
bullet('**A credible niche, with a carefully defined market share.** The prospectus ranks Adaspace #7 with 2.1% of revenue among ~400 Chinese private commercial-aerospace firms with satellite businesses. Its 22.6% / #2 ranking covers only ~20 private full-value-chain firms, not the whole space industry.')
bullet('**AI upside requires monetisation.** Eight more constellation satellites launched in October, following twelve in May 2025. Tencent cooperation and the SenseTime framework broaden access; only two firm SenseTime satellite orders are confirmed. Repeat service revenue needs paid utilisation and competitive cost per task after power, cooling, launch and replacement costs—not just a model demonstration.')
head('Risks — accounting profit, collected cash and treasury are different')
bullet('**H1 is a transition period.** Sales fell 6.3% while satellite-related sales rose 6.9%; legacy solutions fell 20.2%. H1 AI-computing revenue of RMB124.7m arose without completed orbital deliveries. FY25’s 7.6% AI-computing margin and H1’s 55.4% are poor endpoints for a straight-line earnings forecast.')
bullet('**The legacy business faces a regulatory reset.** In February 2026 the company ceased 3D mapping compilation, surrendered the relevant licence and stopped direct imagery sales, using qualified third-party data instead. Hardware growth must replace activity that previously supported solutions margins.')
bullet('**Receivables still need collecting.** June net receivables were RMB597.8m after RMB149.4m allowances; the gross balance was RMB747.2m. The 610.8-day ratio uses average gross balances and 180 days of H1 sales. Seasonality inflates it, but old unpaid balances are real. SOE/SOE-led customers account for 73.1% of gross receivables; that is not a sovereign guarantee.')
bullet('**Positive H1 cash flow does not prove self-funding.** Customer advances rose RMB147.6m; supplier payment terms also help. Inventory days rose from 21.9 to 94.3 as production built up. Inventory supports booked orders if launches proceed; delays trap capital and expose costs to ageing or redesign.')
textp('**Funding is stronger than the supplied cash figure suggests:** September cash was RMB224m plus RMB3.702bn of financial investments, against RMB412m of borrowing and leases. April’s RMB3.55bn equity round largely explains the balance. Investments include structured deposits and non-guaranteed wealth products; they are not all immediately available cash. H1’s RMB3.61bn investing outflow was largely treasury investment, not satellite capex.',before=75,after=0)

page_title('Valuation — H peers first, closest A peers retained')
textp('HK/A: 5 November close. US: 5 November 12:04 ET intraday, not close. Equity uses price × total basic shares. Currency is local to each row. P/S uses the full company, including Adaspace’s domestic shares.',after=95)
rows=[['Adaspace\n06935 HK','HK$24.90–\n33.20','HK$15.00–\n20.00bn',xr(x['ps_annual_low'],x['ps_annual_high']),xr(x['ps_ltm_low'],x['ps_ltm_high'])+'\nJun 26','N/M']]
for p in P:
 label=p['name']+'\n'+p['code'];price={'HKD':'HK$','RMB':'RMB','USD':'US$'}[p['currency']]+f'{p["price"]:g}'
 annual=f'{p["annual_ps"]:.1f}x'+('†' if p['code']=='0031 HK' else '*' if p['code']=='PL US' else '')
 ltm='n/v' if p['ltm_ps'] is None else f'{p["ltm_ps"]:.1f}x\n'+p['ltm_end'].replace('2026','26')
 rows.append([label,price,f'{p["equity_m"]/1000:.2f}bn',annual,ltm,f'{p["annual_pe"]:,.0f}x' if p['annual_pe'] else 'N/M'])
out(table(['Company','Price','Equity\nlocal ccy','Last FY\nP/S','LTM\nP/S','Last FY\nP/E'],rows,[2772,1400,1500,1350,1550,1400]))
textp('Last FY = December 2025, except *Planet: January 2026 (its FY2026). †China Aerospace figures are rounded secondary-source results. LTM ends are stated; missing H-peer LTM inputs stay n/v. N/M = loss-making; n/v = not verified. Earnings use attributable profit for peers.',before=70,after=60)
head('Which comparisons matter?')
bullet('**H shares are valuation boundaries, not direct substitutes.** APT leases mature GEO satellite capacity. China Aerospace combines industrial components and property. Their low sales multiples show that “space” alone earns no premium; neither is an AI constellation manufacturer. 01725 is excluded: FY25 continuing revenue came from EMS manufacturing.')
bullet('**A shares provide the closest operating overlap.** China Spacesat is the manufacturing comparison; Geovis is the geospatial-software comparison. Geovis’s 9M sales fell 65%, making its LTM P/S jump to 20.6x. That weak denominator does not make a similar Adaspace multiple cheap. China Spacesat’s tiny FY25 profit also makes its P/E economically unhelpful.')
bullet('**US names price commercial data services.** Planet and BlackSky are adjacent earth-observation/analytics businesses with different customer and recurring-revenue mixes. Both trade below Adaspace on LTM sales. Their growth is not proof that an untested space-compute service deserves the same unit economics.')
head('Forward valuation — use observable inputs, not stale EPS')
out(table(['Company / basis','Revenue input','Forward P/S'],[
 ['Planet; year to Jan 2027 guidance','US$430–441m; midpoint','9.4x'],
 ['BlackSky; FY26 guidance, updated 5 Nov','US$140–150m; midpoint','5.0x'],
 ['Adaspace: revenue sensitivity only','RMB1.0bn / 1.5bn / 2.0bn','12.8–17.1x / 8.6–11.4x / 6.4–8.6x']
],[4372,2800,2800],left_cols=(0,1,2)))
textp('**Forward P/E:** Adaspace FY26E is N/M under its loss warning; FY27E is n/v. No current, original-source FY26E/FY27E profit forecast was verified for these peers. Pre-Q3 A-share estimates are excluded. At 40x P/E, the offer would require RMB321–428m of annual attributable profit; that is a valuation hurdle, not a forecast.',before=70,after=70)
textp('**Cash and private-round check:** midpoint treasury-adjusted EV/FY25 sales is about 15.4x, allowing for September investments, debt and midpoint net IPO proceeds. This is conditional on realising those investments. IPO post-money value is 11–48% above April’s RMB11.554bn private valuation at current FX; removing new gross cash narrows the comparison to 6–41%. Neither is a price floor.',after=0)

page_title('Offer structure, holders and catalysts')
head('Cornerstones — modest support, with specific identities')
out(table(['Legal investor','Commitment','Type / connection'],[
 ['JinkoSolar Investment Limited','HK$5m','Jinko Holdings (NYSE: JKS) subsidiary. Affiliates already held 2.23% and 0.56% before IPO.'],
 ['Kamshin Oriental (HK) Limited','HK$55m','Electronic-component / bulk-chemical trader; Zhejiang Jinshuo subsidiary, ultimately Jiang Yueqing 90% / Lu Tao 10%.']
],[3500,1500,4972],left_cols=(0,1,2)))
textp('Total HK$60m excludes fees: 6.9% of the midpoint deal, only 0.3–0.4% of total equity. Both lock for six months from and including listing. Kamshin provides 91.7% of the commitment. This is not broad institutional sponsorship, nor an undertaking to buy after listing.',before=75,after=75)
head('Good points and risks in the share structure')
bullet('**The retail allocation is small, but not fixed.** Mechanism B has no automatic clawback. Public allocation starts at 10%; discretionary reallocation can lift it to ~15% of the base offer only if priced at HK$24.90. “No clawback” does not mean “no reallocation”.')
bullet('**Use the whole deal to measure potential selling.** Base offer excluding cornerstones is HK$690–940m, including HK$615–840m of international placement. HK$75–100m is only the initial retail slice. Final distribution, concentration and actual book quality remain unknown.')
bullet('**New shares and later release can expand supply.** A 15% size option plus a greenshoe can raise new issuance to 39.835m shares. Pre-IPO H shares have a statutory 12-month transfer restriction. Exact expiry dates and any longer holder-specific limits must follow the confirmed listing/allotment documents; no future date is presented as confirmed here.')
bullet('**Capital allocation matters despite ample treasury.** Midpoint net proceeds are HK$772.4m, after costs of about HK$102.6m. Planned uses: R&D 35.6%, Shenzhen centre 24.4%, acquisitions 20%, debt 10%, working capital 10%. The issue is execution and return on that spending, not an immediate cash shortage.')
head('Catalysts and checkpoints')
out(table(['Window','What to watch','Trading implication'],[
 ['10–13 Nov 2026','Close, final price, allocations, debut','Lower pricing improves entry valuation. Check concentration, actual free offer and options; subscription demand is not long-term sponsorship.'],
 ['Nov–Dec 2026','15 satellites planned for launch','Launch slots and approvals are dependencies. Two satellites failed in January; an internal test asset and a customer asset were lost.'],
 ['FY26 results; by 31 Mar 2027*','Deliveries, margin bridge, collections, cash flow','Test the loss / negative-CFO warning. Compare realised receipts with June receivables and new customer advances.'],
 ['March 2027 regular HSCI window','31 Dec cutoff; illustrative effective date 8 Mar','Potential route to Southbound, conditional on selection, liquidity and exchange notices. No addition is confirmed.']
],[2200,3100,4672],left_cols=(0,1,2)))
textp('**Southbound is an option, not a locked-in catalyst.** HSCI has no minimum listing history, but uses the H-share class and available market-cap history, index ranking and liquidity. The small-cap Southbound screen is HK$5bn, not a universal HK$6bn rule. H-share value of HK$10.7–14.2bn clears only the size screen. A high-concentration warning can impede index entry. *FY26 reporting deadline assumes the normal December year-end rule; exact results date unannounced.',before=70,after=0)

page_title('Sources, valuation basis and evidence limits')
textp('The analysis reconciles the supplied claims with the final prospectus and dated market data. Public investor arguments are incorporated in the good points and risks. There is no claim of private buy-side access or verified institutional demand.',after=100)
head('Adaspace — primary evidence')
sources('Issuer  ',[('5 November final prospectus',S['prospectus'])])
textp('Key locations: Summary (financial trends and FY26 warnings); History pp 102/107 (private round and transfers); Business pp 154–155 (customer finance lease), 166–167 (milestone revenue); Financial Information (receivables, treasury and cash flow); Cornerstone Investors pp 266–269; Structure of the Global Offering pp 286–287 (discretionary reallocation). Page numbers refer to printed pages.',after=80)
head('Peer earnings and market prices')
sources('Hong Kong  ',[('APT FY25 audited results',S['apt_fy25']),('China Aerospace FY25 report — secondary',S['aerospace_fy25_secondary'])])
sources('China Spacesat  ',[('FY25 issuer report mirror',S['spacesat_fy25']),('Q3 2026 filing',S['spacesat_q3'])])
sources('Geovis  ',[('FY25 annual report',S['geovis_fy25']),('Q3 2026 filing',S['geovis_q3'])])
sources('United States  ',[('Planet financial results',S['planet_results']),('Planet Q2 FY27 issuer release',S['planet_q2_release']),('BlackSky FY25',S['blacksky_fy25']),('BlackSky 5 Nov Q3',S['blacksky_q3'])])
sources('FX / checks  ',[('5 Nov CFETS fixing republication',S['cfets_republication']),('Geovis dated prices',S['geovis_price_crosscheck']),('APT quote',S['apt_price_crosscheck'])])
textp('HK/A closing prices matched between Tencent and Sina. US figures are the explicitly timed Tencent intraday snapshot; US markets had not closed at the research cutoff. Basic share counts are dated vendor inputs. No live Bloomberg terminal was used. FX: HK$1 = RMB0.85601, a fixing rather than an executable spot quote.',after=80)
head('Public arguments assessed')
sources('Read and consolidated  ',[('CITIC sector commentary, 30 Oct',S['citic_sector']),('Xueqiu project-versus-platform analysis, 15 May',S['xueqiu_long_read']),('Niuniu IPO roundup, 30 Oct',S['niuniu_roundup'])])
sources('Launch cross-check  ',[('5 Nov Xueqiu launch post — excerpt only',S['xueqiu_launch_snippet']),('accessible launch mirror',S['launch_mirror'])])
textp('CITIC’s public sector thesis supports the latency/downlink opportunity, not a stock-specific price target. The Xueqiu analysis tests whether revenues justify a platform multiple; its old financial inputs are replaced here. Niuniu’s roundup shows theme promotion, not a representative sentiment survey. No “80% probability of a premium” or friendly-fund allocation assumption is retained.',after=80)
head('Index rules and calculation discipline')
sources('Official rules  ',[('HSCI methodology',S['hsi_method']),('SSE Southbound coverage',S['southbound_sse']),('investor eligibility explainer',S['southbound_education'])])
bullet('**Matched denominators.** IPO equity = 602.419740m total post-offer shares × offer price. P/S = equity in revenue currency ÷ revenue. LTM = last full year + latest interim period − prior comparable period. No partial year is annualised as a forecast.')
bullet('**Forward inputs are dated.** Planet guidance is from its September Q2 release; BlackSky from 5 November. Adaspace revenue cases and the 40x profit hurdle are desk sensitivities. Old A-share broker estimates conflict with newer results and are not labelled current consensus.')
bullet('**Evidence limits are explicit.** Rounded China Aerospace data and unverified LTM/forward estimates are marked. Private-market Micro-Nano Space valuations are excluded as unverified, illiquid anchors. No peer average combines these different businesses.')
textp('The repository retains source URLs, raw numerical inputs, formulas, quote comparisons, exclusions and document checks in research/adaspace_20261106/. Arithmetic verification does not constitute independent source verification.',before=60,after=0)

out(deepcopy(donors[-1]))
assert etree.tostring(body[-1],method='c14n',exclusive=True)==etree.tostring(donors[-1],method='c14n',exclusive=True)
xml=etree.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True);rx=etree.tostring(rels,encoding='UTF-8',xml_declaration=True,standalone=True)
with ZipFile(args.output,'w',ZIP_DEFLATED) as z:
 for name,b in original.items():z.writestr(name,xml if name=='word/document.xml' else rx if name=='word/_rels/document.xml.rels' else b)
with ZipFile(args.output) as z:
 changed=[name for name,b in original.items() if z.read(name)!=b]
 assert set(changed)=={'word/document.xml','word/_rels/document.xml.rels'};assert set(z.namelist())==set(original)
assert sha(args.template)==A['template']['sha256']
qa=dict(document_sha256=sha(args.output),parts=len(original),only_changed_parts=changed,tables=len(body.findall('w:tbl',NS)),sections=1,template_unchanged=True,python_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1048576)
(HERE/'document_qa.json').write_text(json.dumps(qa,indent=2)+'\n');print(json.dumps(qa));(T/'draft_text.txt').write_text('\n'.join(''.join(e.xpath('.//w:t/text()',namespaces=NS)) for e in body))
