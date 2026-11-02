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
T=Path('/private/tmp/ipo-20261103');T.mkdir(exist_ok=True)
parser=argparse.ArgumentParser()
parser.add_argument('--template',type=Path,default=Path('/Users/lemon/Downloads/ipo analysis.docx'))
parser.add_argument('--output',type=Path,default=WORK/'IPO_and_Lockup_Trader_Brief_2026-11-03.docx')
args=parser.parse_args()
A=json.loads((HERE/'source_and_valuation_audit.json').read_text());I=A['issuers'];P=A['peers']
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
S=A['other_sources'];RFS=A['primary_documents']
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
def facts(c):
 x=I[c];rows=[]
 for label,k in [('Revenue','rev'),('Gross margin','gp'),('Owner profit / loss','np'),('Operating cash flow','cfo')]:
  vals=[f'{100*x[k+s]/x["rev"+s]:.1f}%' if k=='gp' else f'{x[k+s]:,.1f}' for s in ['25','_prev','_now']];rows.append([label]+vals)
 out(table(['RMBm except margin','FY2025',x['period']+' 2025',x['period']+' 2026'],rows,[3972,2000,2000,2000]))
def val(c,keys):
 x=I[c];price=f'{x["low"]:.2f}' if x['low']==x['high'] else f'{x["low"]:.2f}–\n{x["high"]:.2f}'
 rows=[[x['name'].split(' ')[0]+' '+c,price,rangefmt(x,'ps25'),rangefmt(x,'pe25'),fmt(x['pe26'])+('†' if c=='2687' else ''),fmt(x['pe27'])+('†' if c=='2687' else '')]]
 for k in keys:
  p=P[k];mark='†' if p['broker'] and 'EtNet' in p['basis'] else ''
  rows.append([p['name']+' '+k,f'{p["price"]:.3f}'.rstrip('0').rstrip('.'),fmt(p['ps25']),fmt(p['pe25']),fmt(p['pe26'])+mark,fmt(p['pe27'])+mark])
 tb=table(['Company','Price','FY25\nP/S','FY25\nP/E','FY26E\nP/E','FY27E\nP/E'],rows,[3100,1472,1350,1350,1350,1350])
 for c1 in tb.findall('w:tr',NS)[1].findall('w:tc',NS):prop(c1.find('w:tcPr',NS),'shd',val='clear',color='auto',fill='F2F2F2')
 out(tb)
def company(c,theme,view):
 x=I[c];page_title(c+'  '+x['name']);caps=f'{x["equity_hkdm_low"]/1000:.2f}–{x["equity_hkdm_high"]/1000:.2f}' if x['low']!=x['high'] else f'{x["equity_hkdm_mid"]/1000:.2f}'
 textp(theme+'  |  Equity value HK$'+caps+'bn',after=85)
 if 'close' in x:textp('Subscription closes '+str(int(x['close'][8:]))+' November  •  Expected listing '+str(int(x['listing'][8:]))+' November',after=65)
 textp('**Desk view  '+view+'**',after=110);facts(c)

page_title('November IPO and lockup trading brief',False)
textp('2206  /  7672  /  9917  /  2681  /  2687  /  1333     •     3 November 2026',after=110)
textp('**Denglin has the clearest AI growth case; Hosin offers memory-cycle earnings, not a clean cheap-P/E trade. Xinde requires the largest operational turnaround. Neautus needs a better price to compensate for its modest growth and thin float.**',after=110)
head('IPO decisions at the offer range')
out(table(['Name and theme','What matters for the trade'],[
 ['2206 Neautus\nTCM decoction pieces','21.1–26.5x FY25 P/E for 6.8% FY25 sales growth. Lower input costs help, but rank #2 means only 0.4% market share.'],
 ['7672 Xinde\nAdvanced packaging','7.8–8.7x FY25 sales while gross margin is negative. Industrial backers and restricted float can sustain the theme before earnings improve.'],
 ['9917 Denglin\nDomestic GPGPU','Real shipment ramp and paid customer orders. 70.2–87.5x FY25 sales exceeds the direct H-share peers; recurring chip margins and collections must follow.'],
 ['2681 Hosin\nMemory modules','5.9–6.7x LTM P/E looks cheap only if peak earnings persist. 62% four-month gross margin and rising procurement debt are the key cycle exposures.']
],[2800,7172],left_cols=(0,1)))
head('Lockup trades')
out(table(['Stock','First session after contractual release','Identified H cohort','Trading judgement'],[
 ['1333 Breton','9 Nov 2026','102.52m gross;\n99.42m excluding Qiu','More liquid short candidate, but improving margins and fresh fund lock-ups create squeeze risk.'],
 ['2687 Able Digital','8 Dec 2026','55.29m gross','Much larger supply relative to turnover. Price already fell 71% since 12 Oct; borrow and exit liquidity are the constraint.']
],[1500,2300,2600,3572],left_cols=(0,1,2,3)))
textp('Cohorts are contractual holdings, not unrestricted selling capacity. Director limits still apply. Breton’s 58.91m fund shares are separately locked through 28 February 2027.',before=75,after=85)
head('How to read the numbers')
textp('All listed prices are **2 November 2026 closes**. IPO values use the full post-offer share capital and the published range, before optional issuance. HK$1 = RMB0.85595. H-share peers appear first; closest A-share comparisons follow.',after=80)
textp('**Forward P/E is a named broker estimate, not a promise.** † identifies public secondary-source estimates whose original accounting adjustments are unverified. n/v means no verified forecast; NM means losses. Scenarios are explicitly separate. Exact inputs and dates are on page 10.',after=80)
textp('Company pages 2–7  •  Cornerstones 8  •  Lockups and calendar 9  •  Forecast inputs 10  •  Sources 11',after=0)

company('2206','Traditional Chinese medicine processing','Margins are recovering, but the offer valuation leaves little room for tender-price pressure or weaker cash collection.')
head('Good points')
bullet('**Earnings are recovering.** Four-month sales rose 12.9% and profit 63.3%; gross margin gained 2.9ppt as herb costs eased. September year-to-date volume rose 34.6%, although selling prices fell about 8%.')
bullet('**Consolidation and hospital access offer upside.** China’s #2 decoction-piece supplier has only 0.4% share; the top five hold 2.7%. Quality control and tender access can take share from smaller processors, but the overall market is mature.')
head('Risks')
bullet('**The valuation needs more than lower input costs.** FY25 sales grew 6.8%. Hospital tenders may add volume while compressing price; the first procurement round’s RMB32.9m contracts equal only 2.5% of FY25 sales. New consumer channels require spending before profits.')
bullet('**Cash conversion is uneven.** FY25 operating cash of RMB154m included a RMB51m pledged-deposit release. Four-month cash flow is negative in both years; receivables and supplier payments explain the latest outflow. One strong year is not a stable cash yield.')
bullet('**Small float, no cornerstone anchor or stabiliser.** Only 10% is newly offered. Mechanism B has no mandatory clawback; discretionary reallocation to 15% requires the HK$40.20 low-end price. This can amplify volatility in either direction.')
head('Valuation versus peers')
val('2206',['570 HK','2273 HK','300181 A'])
textp('**Closest product comparison:** China TCM, with a different granule/finished-drug mix. Gushengtang is a clinic operator; Zoli has decoction exposure but earns mainly from branded drugs. No pure listed match.',before=75,after=70)
textp('**Forward sensitivity:** 20% / 40% profit growth implies 19.8x / 17.0x P/E at the offer midpoint; these are scenarios, not forecasts. LTM P/E is 18.8–23.6x. Watch tender volumes, selling prices and receivable collection.',after=0)

company('7672','Outsourced semiconductor packaging and testing','Advanced-packaging exposure is real; the present economics do not yet justify a premium to profitable OSATs.')
head('Good points')
bullet('**Domestic supply-chain opportunity.** Xiaomi, OPPO and MediaTek-related pre-IPO backing helps customer access. Xinde ranked #7 among China’s general-purpose OSATs in advanced packaging, with 0.6% share in 2025. Higher utilisation could spread a heavy depreciation base.')
bullet('**The immediate float is tight.** GF Fund, Guohui HK and Maxwell commit HK$313m in total, about 32% of the midpoint deal, locked for nine months. Founder-group H shares have a two-year lock followed by phased release; other old shares generally have one year.')
head('Risks')
bullet('**Losses start at gross profit.** Four-month gross margin remains −17.9%; adjusted group loss widened to RMB101m from RMB87m despite revenue growth. 69.5% of proceeds goes to capacity, adding ramp-up risk before existing assets earn an adequate return.')
bullet('**Do not pay for 2.5D/3D revenue that has not arrived.** It contributed only RMB0.244m in FY25 and none in the latest four months. BGA and wafer-level packaging also count as advanced, so calling the rest “traditional” would be wrong.')
bullet('**Funding matters more than headline negative equity.** Redeemable-share liabilities convert to equity on listing, but August bank/other borrowing was RMB1.58bn against RMB260m cash. The chair’s RMB15.27m FY25 pay included RMB13.37m share awards; it was not an eightfold cash salary increase.')
head('Valuation versus peers')
val('7672',['522 HK','600584 A','688362 A'])
textp('**Direct peers:** JCET and Ningbo Silicon. ASMPT supplies packaging equipment and is an adjacent H-share comparison. Xinde asks 7.8–8.7x FY25 sales versus 2.3x / 3.8x for the two A-share OSATs, despite negative gross profit.',before=75,after=75)
textp('**What changes the view:** positive gross margin, better cash conversion and material advanced-product orders. The 6.6–6.9% free float can drive a technical rally before those tests are met.',after=0)

company('9917','Domestic GPU infrastructure and enterprise AI','The most credible growth story here, but the offer already prices in a substantial commercial ramp.')
head('Good points')
bullet('**The ramp is in shipped products.** Four-month sales of RMB200m exceeded all of FY25. KS chip volumes reached 10,246 versus 6,400 in FY25, with higher ASPs. Its #3 rank is specifically China’s enterprise-AI GPGPU market, where it had 1% share in 2025.')
bullet('**Some demand is funded.** A RMB300m procurement framework had RMB91m paid by Q1; a separate RMB58m contract was delivered in April. These strengthen the AI-substitution case. The RMB681m of procurement intentions still requires conversion into definitive orders.')
head('Risks')
bullet('**Adjusted break-even is not recurring chip profitability.** Four-month adjusted profit was RMB20.6m, but IP licensing contributed RMB31.3m gross profit. Chip gross margin fell to 41.9% from 47.7% in FY25. Licensing can help, but it is less repeatable than shipments.')
bullet('**Customer and funding concentration remain high.** The top five supplied 90.4% of sales. Operating cash outflow was RMB147m despite the earnings recovery; August borrowing reached RMB987m. Rising receivables must turn into cash as volumes scale.')
bullet('**Cornerstones support distribution, not a price floor.** Hua Yuan and the Suzhou consortium are linked to existing investors/local government; Tongfu’s Sky Giant is an industrial investor. Five cornerstones take about 41% of the midpoint offer, with six-month locks.')
head('Valuation versus peers')
val('9917',['9903 HK','6082 HK','688795 A'])
textp('**Direct peers:** Iluvatar and Biren in H shares; Moore Threads in A shares. Denglin’s 70.2–87.5x FY25 sales is above the H peers’ 41.2x / 45.4x. Its own LTM sales multiple falls to 32.9–41.0x after the latest ramp; LTM ends April.',before=75,after=75)
textp('**What changes the view:** repeat chip orders, collection and gross-margin stability without licensing dependence. No verified public profit forecast; multiplying four-month adjusted profit by three would not produce a credible forward P/E.',after=0)

company('2681','Memory modules and controllers','Treat the low trailing multiple as a cycle bet; sustainable profit and working-capital funding decide the value.')
head('Good points')
bullet('**Real exposure to rising memory demand.** Smartphone storage, controllers and firmware can benefit from higher AI-device content. Hosin ranked #12 in global memory products, with 0.6% share in 2025. Enterprise storage offers upside; this is not an HBM wafer manufacturer.')
bullet('**Customer collection supports reported sales.** By August, 93.7% of April trade receivables had been collected, and 45.3% of April inventory sold. Transsion brings a customer link; Longsys brings sector expertise and a resolved patent-licensing relationship.')
head('Risks')
bullet('**62% gross margin is a poor normal-year assumption.** Low-cost memory inventory sold into higher prices created exceptional earnings. Replacement costs catch up; a price reversal can cut both margins and inventory values. FY23 was loss-making.')
bullet('**The cash outflow is not just inventory.** Four-month operating cash was −RMB2.69bn: inventory absorbed RMB3.76bn, prepayments/other assets RMB3.13bn and receivables RMB1.28bn, partly offset by profit and payables. Bank/other debt rose to RMB9.13bn by August.')
bullet('**Strategic backing has qualifications.** Hosin already invested in Transsion’s and Longsys’s IPOs; the reciprocal subscriptions are disclosed as non-interconditional. A subsidiary’s US Entity List exposure remains a supply-chain risk. Tiny tradable float can overwhelm fundamentals initially.')
head('Valuation versus peers')
val('2681',['9976 HK','301308 A','688525 A'])
textp('**Direct peers:** Longsys and Biwin. Longsys A/H uses the same Citi earnings estimates; its H price is about 43% below A after FX. Hosin is 21.9–25.1x FY25 profit, but 5.9–6.7x LTM profit after the inventory windfall.',before=75,after=75)
textp('**Normalisation test:** RMB1.5bn / 3bn / 6bn sustainable profit implies 21.4x / 10.7x / 5.3x at midpoint. These are scenarios. Citi’s latest Longsys forecast declines in FY27: low memory P/E alone is not a rerating catalyst.',after=0)

company('2687','University digital content and education AI','December supply and weak cash conversion support the short case; the 71% price fall and very low turnover complicate entry and exit.')
head('Good points')
bullet('**An installed base for AI cross-selling.** FY25 served 1,797 customers; H1 orders on hand rose 34.7% to RMB505m. Knowledge graphs, agents and Alibaba/Volcano Engine partnerships can raise spend per client. H1 gross margin improved 3.5ppt.')
bullet('**Seasonality gives the bull case time.** H1 was loss-making last year too. FY25 H2 earned RMB229m. University acceptance and collections skew toward year-end, so an interim loss alone does not establish structural failure.')
head('Risks')
bullet('**Cash and the earnings hurdle matter.** FY25 operating cash was −RMB64m despite profit; H1 outflow worsened to RMB364m and June borrowing tripled to RMB288m. Guosheng’s old RMB200m FY26 forecast needs RMB316m H2 profit, 38% above last year’s H2.')
bullet('**AI labels are ahead of proof of recurring revenue.** The interim explicitly describes segment renaming as name-only. A subsidiary received a one-year government-procurement ban over false staff credentials; its government revenue was under 10% of group H1 sales. The ban is not group-wide.')
bullet('**Large old-share cohort, difficult execution.** 55.29m H shares reach contractual release on 8 December, including 16.77m held by Sina- and Baidu-linked investors. A proposed 4.71m domestic-share conversion is additional potential supply, not completed free float.')
head('Valuation versus peers')
val('2687',['777 HK','2469 HK','300559 A'])
textp('**Closest A business:** Jiafa education IT. NetDragon and Fenbi are adjacent H comparisons, not identical software peers. Able is 41.0x LTM P/E; its 23.1x FY26E relies on a pre-results, pre-penalty forecast. Price is down 71% since 12 October.',before=75,after=70)
textp('**Short trigger:** confirmed holder selling plus weak H2 collection/orders. **Invalidation:** strong acceptance and cash receipts or renewed locks. Only 32,439 shares/day traded over the last 14 sessions. July director DI was a deemed-interest change, not a sale.',after=0)

company('1333','Battery-electric mining trucks and overseas power','The nearer and more liquid lockup trade; valuation is demanding, but the earnings direction is improving.')
head('Good points')
bullet('**A real mining-electrification business.** H1 gross margin recovered to 16.5% and owner loss halved. Overseas solar/storage projects may add power income and cross-sell equipment. The direct H comparison is Sany International’s mining business, rather than software AI names.')
bullet('**Recent holder behaviour argues against a simple exit story.** Chen Fangming bought 1.333m H shares from December 2025 to June 2026. On 2 November, seven fund holders locked 58.91m H shares through February 2027, withdrawing a separate block of potential supply.')
head('Risks')
bullet('**Core hardware is not yet recovering.** H1 equipment revenue fell 19.6%; RMB61.5m from PV/storage components and electricity kept total sales roughly flat. That mixed line should not all be valued as recurring power income. H1 operating cash remained −RMB165m.')
bullet('**Expansion consumes capital.** June borrowing was RMB889m against RMB249m cash. July, September and October placings fund the business and dilute holders; they are not insider sales. October raised HK$199m net at HK$12.06, with 60% earmarked for overseas power projects.')
bullet('**November supply survives the new fund locks.** The April controller extension ends 6 November. Its original cohort contains 102.52m H shares, but Qiu Debo’s 3.09m remain subject to the post-resignation restriction. Remaining directors also face annual transfer limits.')
head('Valuation versus peers')
val('1333',['631 HK','1157 HK','000528 A'])
textp('**Direct overlap:** Sany mining equipment and LiuGong electric loaders. Zoomlion is broader machinery. Breton’s 7.7x FY25 sales is far above 0.5–0.7x for these profitable peers. The premium requires a substantial future earnings ramp; no verified forward P/E is available.',before=75,after=75)
textp('**Short trigger:** actual controller distribution after 9 November, weak hardware orders or further financing. **Invalidation:** another controller extension, better cash generation or executable overseas orders. The recent DRC cooperation announcement is an intention, not booked sales.',after=0)

page_title('Cornerstones and offer structure')
textp('Legal investors and contractual amounts from the 30 October prospectuses. Final allocation notices were not yet available. Locked allocations can tighten float; they do not guarantee aftermarket buying.',after=100)
head('7672 Xinde')
out(table(['Legal investor','Amount','What the backing means'],[
 ['GF Fund Management Co., Ltd.','US$15m','Fund manager'],['Guohui (HK) Holdings Co., Limited','US$10m','Shandong state-owned investment vehicle'],['Maxwell Technology Pte. Ltd.','RMB100m','Suzhou Maxwell subsidiary; supplier affiliate']
],[4400,1700,3872],left_cols=(0,1,2)))
textp('HK$312.99m excluding fees; 30.6–34.2% of offer, nine-month lock. Base tradable offer excluding cornerstones: about HK$603–710m, 6.6–6.9% of total shares. No over-allotment or stabiliser. Founder H shares: two years, then up to 60% released in year three; balance after year three.',before=65,after=60)
head('9917 Denglin')
out(table(['Legal investor','Amount','What the backing means'],[
 ['Hua Yuan International Limited','RMB300m','Oriza/Zhongxin existing-investor affiliate'],['Sky Giant Investment Limited','RMB200m*','Tongfu Microelectronics subsidiary'],['Suzhou Chinese Consortium Holding Co., Ltd.','RMB30m','Jiangsu government-linked investor'],['ZGD Capital Investments Pte. Ltd.','US$2m','Zhu Guodong investment vehicle'],['Everbright Wealth Management Co., Ltd.','US$1.8m','Bank wealth manager']
],[4400,1700,3872],left_cols=(0,1,2)))
textp('About HK$646m subscriptions excluding fees; 36.6–45.7% of base offer, six-month lock. *Sky Giant’s stated RMB200m includes fees. Public tranche starts at 5%; 15% over-allotment option. Qualcomm is a pre-IPO investor, not one of these five cornerstones.',before=65,after=60)
head('2681 Hosin')
out(table(['Legal investor','Published amount','Investor connection'],[
 ['Flourish Holding Limited','HK$126.74m*','Chen Li-Shun; MagiCapital director'],['Pine Vigor Capital Limited','HK$78.50m','Existing-investor affiliate'],['Transsion International Limited','HK$78.48m*','Customer group; reciprocal IPO investment'],['Longsys Investment Co., Limited','HK$62.78m*','Peer and patent licensor; reciprocal investment'],['Gottfried (HK) Limited','HK$50.00m*','IC/component trading and processing'],['STRONG LION LIMITED','HK$35.32m*','Private investment vehicle'],['Mr. Chen Chun-Cheng','HK$23.50m*','Individual investor']
],[4400,1700,3872],left_cols=(0,1,2)))
textp('HK$451.56m aggregate excluding fees; the table’s HK$455.32m total mixes fee bases (*includes fees). Six-month locks; 37.0–42.4% of base offer, only 1.1–1.3% of total equity. At midpoint, the offer excluding cornerstones is 1.84% of total shares. Size adjustment and greenshoe can enlarge the deal.',before=65,after=0)

page_title('Lockup supply and trading calendar')
head('2687 Able Digital')
out(table(['Original holder cohort','H shares','% total equity'],[
 ['Wang Hui and Ge Xin','23,066,820','34.60%'],['All other pre-IPO H holders','32,219,280','48.33%'],['Total contractual cohort','55,286,100','82.93%']
],[5472,2400,2100]))
textp('The allotment notice states **7 December 2026 as the last locked day**. First release is 8 December. The other-holder block includes Jinzhuo Hengbang Technology (Beijing) Co., Ltd., the Sina-linked investor, with 10.736m H shares, and Dazi County Bairuixiang Venture Capital Management Co., Ltd., Baidu-linked, with 6.039m.',before=65,after=75)
textp('The proposed conversion of Wang Yunning’s 4.714m domestic shares is excluded pending completion. Wang Xin’s July DI reduction of 282,420 deemed shares followed her departure as a partnership’s general partner; her 709,920 direct shares and spouse’s 709,920 were unchanged. No selling is established by that filing.',after=75)
head('1333 Breton')
out(table(['Original extended holder','H shares','November screen'],[
 ["Shanghai Fang’ao Business Consulting Partnership (Limited Partnership)",'63,376,798','Contractual release; director-control limits need checking'],
 ['Mr. Chen Fangming','31,101,004','Annual director transfer cap applies'],
 ['Shanghai Yunbuluo Yijin Venture Capital Center (Limited Partnership)','2,370,189','Contractual release'],
 ['Mr. Qiu Debo','3,091,551','Exclude: post-departure restriction'],
 ['Ms. Yang Hui','2,576,293','Annual director transfer cap applies']
],[4972,1900,3100],left_cols=(0,2)))
textp('Last contractual lock day is **6 November inclusive**; first trading session is 9 November. The gross H cohort is 102.516m (24.05% of current equity); excluding Qiu leaves 99.424m before other caps. Excludes 21.126m domestic shares and Chen’s later 1.333m market purchases. The October filing calls Yunbuluo “Shanghai Cloud Tribe Yijin”: the same disclosed entity, not an extra holder.',before=65,after=70)
textp('**Liquidity:** 13 Oct–2 Nov average daily volume was 32,439 shares for Able and 2.894m for Breton. Gross cohorts equal 1,704x / 35.4x those averages; this measures scale, not days needed to sell. Both are designated short-sale securities; live borrow, fee and recall terms are unverified.',after=80)
head('Dates and flow catalysts')
out(table(['Date','Event','Assessment'],[
 ['9 Nov / 8 Dec','Breton / Able contractual release','Check for new extensions and actual disposal notices.'],['11 Nov / 1 Dec','MSCI review / effective date','Calendar confirmed; no addition verified for either.'],['20 Nov / 7 Dec','Hang Seng review / Group 1 effective','Review opportunity, not an inclusion prediction.'],['By 31 Mar 2027','FY26 results deadline for both','Exact dates unannounced. Able H2 profit and cash; Breton margins and funding.']
],[2150,3500,4322],left_cols=(0,1,2)))
textp('**Southbound is already available:** Breton since 8 September 2025; Able since 9 March 2026. These are not pending first-inclusion catalysts. Both entered through HSCI-related adjustments.',before=65,after=0)

page_title('Forecast inputs and valuation discipline')
textp('All P/Es are recalculated from the 2 November share-price-implied total equity value and the profit below. Profit is RMBm except ASMPT, which is HK$m. These are selected named forecasts, not a consensus average.',after=100)
rows=[]
for code in ['2687','570 HK','2273 HK','522 HK','600584 A','688362 A','9903 HK','6082 HK','688795 A','9976 HK','688525 A','777 HK','631 HK','1157 HK','000528 A','300181 A']:
 if code=='2687':rows.append(['Able Digital 2687','Guosheng 13 Aug†','200','280']);continue
 p=P[code];rows.append([p['name']+' '+code,p['broker']+' '+p['forecast_date'][8:]+' '+{'08':'Aug','09':'Sep','10':'Oct','11':'Nov'}[p['forecast_date'][5:7]]+('†' if 'EtNet' in p['basis'] else ''),f'{p["fy26_np"]:,.2f}',f'{p["fy27_np"]:,.2f}'])
out(table(['Company','Broker and 2026 date','FY26E profit','FY27E profit'],rows,[3272,2900,1900,1900]))
head('Basis and limitations')
bullet('**† Secondary-source estimate.** EtNet supplies the H-peer forecasts; original broker adjustment and dilution definitions were unavailable. The Able forecast is a rounded public Guosheng extract predating H1 results and the penalty. These values are not independently verified consensus.')
bullet('**Matched arithmetic.** Prices are HK$ for HK rows and RMB for A rows. Full post-offer equity is used for IPOs, including unlisted shares. Breton excludes treasury shares. Longsys A/H uses identical profits, so the difference reflects the price of each class, not a different forecast.')
bullet('**Historical earnings.** FY25 P/E uses reported attributable profit; FY25 P/S uses revenue. LTM adds the latest period and removes the corresponding prior period. IPO LTM ends April 2026; listed-company LTM ends June. No four-month figure is annualised in the forecast table.')
bullet('**Missing forecasts stay missing.** No verified public FY26/FY27 profit estimate was located for the four IPOs, Breton, Fenbi or Jiafa. Hosin and Neautus scenarios are sensitivities only. Biwin’s August estimate has not been refreshed for subsequent results.')
textp('Source URLs, raw numerical inputs, share reconciliation and formulas are retained in research/ipo_20261103/source_and_valuation_audit.json. Recalculation checks verify arithmetic; they do not replace primary-source review.',after=0)

page_title('Sources and evidence')
textp('Prospectuses and issuer filings drive the numbers. Xueqiu, Niuniu and broker views inform the good points and risks; selected posts are not a representative investor survey.',after=95)
head('Issuer filings')
sources('2206  ',[('30 Oct prospectus',doc('2206'))]);textp('Financial statements and cash flow: printed pp 232–252; offer reallocation pp 275–276. Market rank is the prospectus’s commissioned industry estimate.',after=55)
sources('7672  ',[('30 Oct prospectus',doc('7672e'))]);textp('Financials pp 270 onward; cornerstones pp 259–263; founder restrictions pp 331–332. Includes redeemable-equity conversion, compensation components and packaging mix.',after=55)
sources('9917  ',[('30 Oct prospectus',doc('9917e'))]);textp('Commercial contracts pp 171–172; cornerstones pp 223–228; financials and segment margins in Financial Information. Procurement intentions are separated from firm delivered business.',after=55)
sources('2681  ',[('30 Oct prospectus',doc('2681e'))]);textp('Working capital and borrowing pp 244–252; cornerstones pp 253–264, including reciprocal investments, patent licensing and fee definitions.',after=55)
sources('2687  ',[('FY25 annual report',doc('2687_2026042903659')),('H1 report',doc('2687_2026092100863')),('allotment locks',doc('2687_allot')),('subsidiary penalty',doc('2687_2026101500683')),('director DI',S['able_di'])])
sources('1333  ',[('FY25 results',doc('1333_2026033003446')),('H1 report',doc('1333_2026092500373')),('April extension',doc('1333_2026042805191')),('2 Nov fund locks',doc('1333_2026110203513'))])
sources('1333 holders  ',[('June purchases',doc('1333_2026061100969')),('October placing',doc('1333_2026102101027')),('20 Oct resignation',doc('1333_resign')),('articles 33–34',doc('1333_articles'))])
head('Broker and investor reading')
sources('IPO views  ',[('Neautus Xueqiu',S['xueqiu_neautus']),('offer mechanism',S['xueqiu_neautus_terms']),('Xinde Xueqiu',S['xueqiu_xinde']),('Denglin Xueqiu',S['xueqiu_denglin']),('Niuniu IPO overview',S['niuniu'])])
sources('Critical reads  ',[('Neautus IPO history',S['neautus_history']),('Xinde salary and technology critique',S['xinde_critique']),('Hosin listing report',S['hosin_sina']),('Able Guosheng extract',S['able_forecast'])])
textp('Some supplied Xueqiu links were inaccessible; available originals/mirrors and filings were used. Old Xinde six-month figures and Hosin’s private-round valuation were not carried forward as current listing metrics.',after=65)
sources('H-peer forecasts  ',[(c.split()[0],P[c]['forecast_url']) for c in ['570 HK','2273 HK','522 HK','9903 HK','6082 HK','9976 HK','777 HK','631 HK','1157 HK']])
sources('Original A reports  ',[(P[c]['name'],P[c]['forecast_url']) for c in ['300181 A','600584 A','688362 A','688795 A','688525 A','000528 A']])
head('Market and event sources')
sources('Calendar and eligibility  ',[('MSCI dates',S['msci']),('Hang Seng dates',S['hsi']),('Able Southbound',S['southbound_able']),('Breton Southbound',S['southbound_breton']),('short-sale list',S['short_list'])])
sources('Price checks and FX  ',[('Able quote',S['quote_able_check']),('Breton quote',S['quote_breton_check']),('2 Nov CFETS fixing',A['fx']['source'])])
textp('Tencent supplied the common closing-price and daily-volume snapshot; all 24 closing prices matched Sina. H-peer earnings history was checked against EtNet; original A broker PDFs and issuer statements were read separately. No live Bloomberg or stock-borrow terminal was used.',before=55,after=0)

out(deepcopy(donors[-1]))
assert etree.tostring(body[-1],method='c14n',exclusive=True)==etree.tostring(donors[-1],method='c14n',exclusive=True)
xml=etree.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True);rx=etree.tostring(rels,encoding='UTF-8',xml_declaration=True,standalone=True)
with ZipFile(args.output,'w',ZIP_DEFLATED) as z:
 for n,b in original.items():z.writestr(n,xml if n=='word/document.xml' else rx if n=='word/_rels/document.xml.rels' else b)
with ZipFile(args.output) as z:
 changed=[n for n,b in original.items() if z.read(n)!=b]
 assert set(changed)=={'word/document.xml','word/_rels/document.xml.rels'};assert set(z.namelist())==set(original)
assert sha(args.template)==A['template']['sha256']
qa=dict(document_sha256=sha(args.output),parts=len(original),only_changed_parts=changed,tables=len(body.findall('w:tbl',NS)),sections=1,template_unchanged=True,python_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1048576)
(HERE/'document_qa.json').write_text(json.dumps(qa,indent=2));print(json.dumps(qa));(T/'draft_text.txt').write_text('\n'.join(''.join(e.xpath('.//w:t/text()',namespaces=NS)) for e in body))
