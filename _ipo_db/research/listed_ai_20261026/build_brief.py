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
T=Path('/private/tmp/listed-ai-20261026');T.mkdir(exist_ok=True)
parser=argparse.ArgumentParser()
parser.add_argument('--template',type=Path,default=Path('/Users/lemon/Downloads/ipo analysis.docx'))
parser.add_argument('--output',type=Path,default=WORK/'Listed_AI_Lockup_Trader_Brief_2026-10-26.docx')
args=parser.parse_args()
A=json.loads((HERE/'source_and_valuation_audit.json').read_text());I=A['issuers'];P={p['code']:p for p in A['peers']}
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
S=A['additional_sources']; H='https://www1.hkexnews.hk/listedco/listconews/sehk/'
def filing(date,num):return H+date+'/'+num+'.pdf'
def fmt(v):return 'n/v' if v is None else v if isinstance(v,str) else f'{v:.1f}x'
def textp(t,**kw):out(para(t,**kw))
def bullet(t):out(para(t,kind='bullet',after=75))
def head(t,new=False):out(para(t,kind='heading',before=90,after=80,pagebreak=new))
def sources(label,ls):out(source(label,ls))
def facts(c):
 x=I[c]
 rows=[['Revenue',f'{x["rev25"]:.1f}',f'{x["rev_h125"]:.1f}',f'{x["rev_h126"]:.1f}'],['Gross margin',f'{100*x["gp25"]/x["rev25"]:.1f}%',f'{100*x["gp_h125"]/x["rev_h125"]:.1f}%',f'{100*x["gp_h126"]/x["rev_h126"]:.1f}%'],['Owner profit / (loss)',f'{x["np25"]:.1f}',f'{x["np_h125"]:.1f}',f'{x["np_h126"]:.1f}'],['Operating cash flow',f'{x["cfo25"]:.1f}',f'{x["cfo_h125"]:.1f}',f'{x["cfo_h126"]:.1f}']]
 out(table(['RMBm, except margin','FY2025','H1 2025','H1 2026'],rows,[3972,2000,2000,2000]))

def issuerline(c):
 x=I[c]
 mark='†' if c in ['3317','6651'] else ''
 textp(f'HK${x["price"]:,.3f} | Equity value HK${x["equity_hkdm"]/1000:.2f}bn | FY2025 P/S {x["ps25"]:.1f}x | FY2026E / FY2027E P/E {fmt(x["pe26"])} / {fmt(x["pe27"])}{mark}',after=100)

textp('Listed IPO / Lock-up Watch',kind='title',after=100)
textp('2635 / 3317 / 6600 / 6651 | Trader briefing | 26 October 2026 close',after=100)
textp('**Desk view.** The earnings-quality concern is strongest at Xunce; the valuation stretch is greatest at 51WORLD. OneRobotics has the most difficult liquidity for a short. Nuobikan has already de-rated to 15.4x reported LTM earnings. December unlocks create potential supply, but timing needs evidence of holders selling and a workable borrow.',after=110)
out(table(['Stock / theme','Short thesis worth testing','What can defeat the short'],[
['2635 Nuobikan\nInfrastructure AI','Receivables exceed annual sales; cash conversion weakening.','Profitable, 4.1x FY2025 sales; new compute-infrastructure orders.'],
['3317 Xunce\nEnterprise data / Token','RMB661m H1 operating outflow; fair-value gains underpin reported profit.','Very fast growth; credible December HSTECH inclusion candidate.'],
['6600 OneRobotics\nHome / embodied robots','Costs outrun sales; expensive against established consumer hardware.','New products, founder lock extension; thin trading amplifies squeezes.'],
['6651 51WORLD\nSimulation / physical AI','60.5x FY2025 sales; recurring economics still unproven.','NVIDIA ecosystem news, 51Sim growth and Aper order deliveries.']
],[2130,3921,3921],left_cols=(0,1,2)))
head('December supply: identified original pre-IPO H shares')
rows=[]
for c in ['2635','3317','6600','6651']:
 x=I[c];rows.append([c,x['last_locked'][8:]+' Dec / '+x['first_released'][8:]+' Dec',f'{x["unlock_h"]/1e6:.2f}m',f'{x["unlock_pct_total"]:.1f}%',f'{x["unlock_adv"]:.1f}x'])
out(table(['Code','Last locked / first release','H shares','% current total','Shares / 20d ADV'],rows,[900,3072,2000,1800,2200]))
textp('Dates are 2026. Release means expiry of the identified IPO restriction; other insider rules can still apply. Amounts exclude unlisted shares, post-IPO option shares and OneRobotics’ founder extension. ADV is 25 September–26 October. The multiples measure potential overhang, not expected selling or days needed to liquidate.',before=80,after=100)
head('Trading implications')
bullet('**The flow catalyst is index buying before the unlock.** Watch the 20 November Hang Seng review and 7 December HSTECH implementation, particularly Xunce. All four have already been admitted to Southbound; first-time admission is not a new catalyst.')
bullet('**No confirmed near-term earnings date for the four.** FY2026 results are expected by March 2027; exact dates are unannounced. A short initiated now may have to carry through both index and year-end theme risk before audited full-year evidence arrives.')
bullet('**Eligible to short does not mean available to borrow.** All four appear on HKEX’s designated list effective 23 October. Borrow size, fee and recall terms remain unverified. Recent DI forms reviewed show placement dilution, not a wave of disclosed insider selling.')
sources('Primary lock-up evidence: ',[('Nuobikan',filing('2025/1222','2025122201578')),('Xunce',filing('2025/1229','2025122902057')),('OneRobotics extension',filing('2026/0630','2026063002277')),('51WORLD',filing('2025/1229','2025122902393'))])

head('2635 Nuobikan 諾比侃 — cash collection is the test',True)
issuerline('2635');facts('2635')
head('Good / potential')
bullet('**A paying infrastructure niche, with a less demanding valuation.** Rail inspection, power monitoring and urban systems are real project businesses. Cited 2024 shares were 5.9% in AI rail-power inspection and 1.8% in broader AI rail inspection: useful specialist positions, not dominance across AI. Reported LTM owner profit is RMB131.5m, giving 15.4x P/E.')
bullet('**A new route into compute spending.** The 6 August software contract with an unnamed domestic AI chip company is RMB50.8m including VAT, roughly 10% of FY2025 sales. It creates upside if delivered and paid; it does not yet establish recurring cloud revenue. H1 gross margin recovered to 55.0% from a weak comparison base.')
head('Bad / risk')
bullet('**Profit has accumulated in receivables.** June trade receivables were RMB637.9m versus RMB498.2m FY2025 revenue. H1 operating cash covered only 50% of owner profit and fell 68% YoY. City projects generated 54% of H1 sales, increasing exposure to customer budgets, acceptance and collection timing.')
bullet('**Margin recovery has not removed the spending burden.** H1 R&D rose 165% and selling expense 183%, far ahead of 32% sales growth. More bespoke projects can produce revenue without software-like operating leverage. The key downside trigger is further ageing or provisions, not the AI label itself.')
bullet('**Supplier controversy remains a diligence issue.** Its May clarification followed a supplier’s accounting penalty. Nuobikan stated its own transactions and accounting were valid. The supplier’s offence is not proof of misconduct by Nuobikan; no independent clearance of Nuobikan’s accounting was established in this review.')
head('Shareholders / lock-up / what changes the view')
textp('**Recent action:** 16.49m new H shares placed at HK$8.19, completed 9 October; net proceeds HK$131.5m. This is 4.2% of current total shares. The close is 27% below the placing price. The 9 October DI events explicitly reflect dilution; Liao Yu’s concert group still reports 129.58m H shares and Luo Tian’s deemed interest 54.65m H shares. These overlapping interests must not be added twice.',after=85)
textp('**23 December release:** 266.48m original H shares, including 136.90m outside the controller group; 74.32m unlisted shares excluded. A large overhang is real, but the valuation case is weaker than for the other three. **Bear confirmation:** collections disappoint or provisions rise. **Short breaker:** strong cash collection plus repeat chip/compute orders.',after=85)
textp('**Next earnings:** FY2026, date unannounced; expected by 31 March 2027. No verified exact FY2026/27 profit forecast. HSTECH/MSCI addition is not an established catalyst for this name.',after=85)
sources('Evidence: ',[('H1 report',filing('2026/0916','2026091600183')),('FY2025',filing('2026/0428','2026042805085')),('chip contract',filing('2026/0806','2026080601150')),('placing',filing('2026/1009','2026100901015')),('clarification',filing('2026/0511','2026051101486')),('DI',A['di_source_urls']['02635-di-notices-0']),('market-share context',S['nuobikan_marketshare'])])

head('3317 Xunce 迅策 — high growth, low cash quality',True)
issuerline('3317');facts('3317')
head('Good / potential')
bullet('**The enterprise-AI bottleneck is credible.** Models need usable, real-time data. Prospectus research puts Xunce first in China’s asset-management real-time data market (11.6% share in 2024), but fourth across industries (3.4%). H1 sales rose 389%; non-asset-management clients contributed 87.6%. Token-based revenue exceeded 10%. Usage billing could scale better than one-off deployments.')
bullet('**Index demand can arrive before the bearish catalyst.** Shenton Research’s 16 October screen names Xunce as a December HSTECH add candidate. The expanded 50-stock methodology favours both scale and revenue growth. This is an analyst forecast, not a confirmed inclusion; 20 November and 7 December are the critical dates.')
head('Bad / risk')
bullet('**The profit inflection is not yet an operating one.** H1 pretax profit of RMB67.0m included RMB101.4m of investment fair-value gains. Subtracting that gain alone gives a RMB34.4m pretax loss; this is a sensitivity, not adjusted net profit. Group gross margin fell 6.6 percentage points to 60.1%.')
bullet('**Cash burn overwhelms reported earnings.** H1 operating outflow was RMB661.2m, driven by receivables, inventories and prepayments. Transaction-based products still represented 90.5% of revenue; subscriptions were only 9.5%. Token language does not turn the whole company into recurring SaaS. The next test is repeat usage and collections, not another headline growth rate.')
bullet('**The capital intensity is increasing.** The September circular proposes a RMB12bn project and financing/guarantees up to RMB10bn. These are proposed capacity and limits, not proof the cash is already spent or financing fully drawn. July equity and convertible issuance rebuilt liquidity, but also linked the thesis to execution and refinancing.')
head('Shareholders / lock-up / what changes the view')
textp('**Recent action:** July placement of 7.283m H shares at HK$107.70 plus RMB1.36bn zero-coupon bonds due July 2027. September outstanding principal was RMB1.268bn; initial conversion price HK$123.86, well above HK$65.20. Redemption at 101.75% creates a cash obligation if not converted/refinanced. Tencent and GBA Fund DI percentage reductions were placement dilution, with share counts unchanged.',after=85)
textp('**30 December release:** 244.48m original pre-IPO H shares; 174.41m outside the largest shareholder group. The June cornerstone expiry is already past. **Bear confirmation:** sustained cash burn, slower collections or new funding without cash returns. **Short breaker:** token cash generation or confirmed HSTECH inclusion; avoid treating the lock date as the first catalyst.',after=85)
textp('**Next earnings:** FY2026, unannounced; expected by March 2027. Selected GTJ estimates via EtNet (28 September): owner profit RMB57m / RMB294m in FY2026/27, implying 324.1x / 62.8x. Original note/accounting adjustments were not independently verified; these are indicative, not consensus.',after=85)
sources('Evidence: ',[('H1 report',filing('2026/0921','2026092100985')),('prospectus',filing('2025/1218','2025121800027')),('project circular',filing('2026/0909','2026090900997')),('July financing',filing('2026/0703','2026070300105')),('September capital',filing('2026/1002','2026100202637')),('DI',A['di_source_urls']['03317-di-notices-0']),('GTHT business case',S['gtj_xunce']),('index screen',S['hstech_candidate'])])

head('6600 OneRobotics 臥安機器人 — growth must earn its premium',True)
issuerline('6600');facts('6600')
head('Good / potential')
bullet('**A route from existing homes into embodied AI.** Prospectus research ranks it first with 11.9% of the narrowly defined global home-robotic-system market (2024 retail sales). SwitchBot provides channels for Onero H1, Acemate and Kata, which together contributed RMB68.4m in H1, or 13.1% of sales. Cross-selling and reusable control models are the upside; current revenue is predominantly hardware.')
bullet('**Expansion has measurable traction and funding.** Europe and North America grew 97.5% and 85.7%, reaching a combined 42.1% of sales. June cash/bank balances plus structured deposits were about RMB1.595bn. Much of the investing outflow was a transfer into term deposits, not a disappearance of liquidity. New-product execution matters more than an imminent funding-crisis narrative.')
head('Bad / risk')
bullet('**Costs are rising faster than the revenue base.** Gross margin fell from 54.2% to 50.4%; selling costs rose 63% and R&D 73%. The RMB42.7m FX loss was substantially offset at profit level by RMB33.8m of forward-contract gains. Treating the full FX loss as the sole explanation for the earnings reversal overstates the underlying recovery potential.')
bullet('**Inventory is a delivery bet, not automatically good or bad.** H1 operating outflow reached RMB164.7m; inventory absorbed RMB100.1m and receivables RMB47.5m. This can reverse with Q4 sell-through, but inventories also bring markdown and obsolescence risk. Inventory provisions rose to RMB9.8m from RMB5.7m. Watch cash collected after delivery and product gross margin together.')
bullet('**The premium needs much more profit.** Great Wall’s 20 October forecast gives FY2026/27 sales of RMB1.412bn / RMB2.045bn, but owner profit of -RMB46m / +RMB28m. That is 7.0x FY2026 sales and 352.5x FY2027 earnings, versus roughly 12–17x FY2027 earnings for Anker, Roborock and Ecovacs. Their categories differ, but they anchor consumer-hardware economics.')
head('Shareholders / lock-up / what changes the view')
textp('**Support is specific:** Li Zhichen extended 43.65m directly held shares through 29 June 2027. Other pre-IPO holders’ 156.35m shares release from the identified restriction on 30 December 2026. Cornerstones’ June 2026 expiry has passed; their later confidence statements are not binding extensions.',after=85)
textp('**Recent action:** the incentive trustee bought 653,200 shares cumulatively for about HK$39.9m by 14 September. This is employee-scheme stock, not cancellation or a founder purchase, and only 0.29% of shares. No new DI notices were found in the July–26 October window. **Short breaker:** strong Q4 deliveries and margin recovery; **execution problem:** just 0.227m shares/day on the 20-session average.',after=85)
textp('**Next earnings:** FY2026 date unannounced; expected by March 2027. Anker’s confirmed 29 October Q3 meeting is an earlier channel/margin read-through, not OneRobotics guidance. No verified new index-add forecast for OneRobotics.',after=85)
sources('Evidence: ',[('H1 report',filing('2026/0918','2026091800725')),('prospectus',filing('2025/1218','2025121800167')),('founder extension',filing('2026/0630','2026063002277')),('trust purchases',filing('2026/0914','2026091401199')),('Great Wall forecast',S['greatwall_onerobotics']),('Anker meeting',filing('2026/1016','2026101600304'))])

head('6651 51WORLD 五一視界 — strong theme, demanding conversion',True)
issuerline('6651');facts('6651')
head('Good / potential')
bullet('**Simulation has a concrete use case.** 51Sim helps automakers test difficult driving scenarios and validate safety. The FY2025 report cites 53.5% share of China’s end-to-end high-level intelligent-driving simulation/data platform market. That is a narrow commissioned-market definition, not 53.5% of global simulation. H1 51Sim sales rose 545% to RMB51.2m, reaching 41.4% of revenue.')
bullet('**The catalyst is tools for physical AI.** The 22 October announcement confirms 51Sim’s inclusion in NVIDIA’s Halos SAFE ecosystem. Aper’s orders exceeded RMB200m on 16 September, with over 90% targeted for delivery this year. These improve market access and near-term revenue visibility. Usage-based training and repeat purchases are the longer-term upside, if demonstrated.')
head('Bad / risk')
bullet('**Orders and ecosystem membership are not cash earnings.** Aper combines hardware and software; delivery, acceptance and collection still matter. Initial equipment sales do not prove recurring platform revenue, and more hardware can dilute margins. NVIDIA participation does not itself disclose contracted revenue, exclusivity or a minimum purchase commitment.')
bullet('**Growth starts from a small, seasonal base.** H1 sales were RMB123.7m, with a RMB67.6m owner loss and RMB43.1m operating cash outflow. Receivables improved, but cash generation remains negative. The margin recovery to 44.8% is encouraging; FY2025’s 30.0% margin shows how much project mix can change the outcome.')
bullet('**Even bullish forecasts leave a large valuation hurdle.** Latest Guosheng coverage (20 October) forecasts FY2026/27 sales of RMB750m / RMB1.53bn, giving 28.1x / 13.8x P/S, and only -RMB110m / +RMB10m adjusted profit. That positive FY2027 figure is non-GAAP, not evidence of reported breakeven. Huatai’s 15 September reported-profit forecasts remain negative in both years.')
head('Shareholders / lock-up / what changes the view')
textp('**Recent action:** 5.466m new H shares placed at HK$73.20 on 10 July; net proceeds HK$394.5m. The close is 20% below that price. July DI forms for Li Yi and LS51World Holding Limited explicitly state no share-count reduction: the percentage changes were dilution. September RSU grants are incentives, not insider buying.',after=85)
textp('**30 December release:** 363.30m original pre-IPO H shares; excludes 19.08m unlisted shares and 7.65m H shares issued on April option exercises whose restriction treatment is not included. Pathfinder investors LS51World Holding Limited and Sky9 51World Limited account for 79.26m; other pre-IPO investors another 172.11m. Holder willingness to sell is still unproven.',after=85)
textp('**Bear confirmation:** missed Aper delivery/acceptance, weak repeat orders or margin dilution. **Short breaker:** paid deployments plus recurring usage; further ecosystem news can sustain the theme before earnings catch up. FY2026 results are unannounced, expected by March 2027; no verified new index-add forecast.',after=85)
sources('Evidence: ',[('H1 report',filing('2026/0921','2026092100462')),('FY2025 market share',filing('2026/0424','2026042403908')),('Aper orders',filing('2026/0916','2026091601231')),('NVIDIA',filing('2026/1022','2026102200055')),('DI',A['di_source_urls']['06651-di-notices-0']),('Guosheng',S['guosheng_51world']),('Huatai',S['huatai_51world']),('Xueqiu argument',S['xueqiu_51world'])])

# H-first comparison groups. Original earnings conventions stay visible.
def peerrow(code):
 x=P[code];price=('HK$' if x['price_currency']=='HKD' else 'RMB')+f'{x["price"]:.3f}'
 date=x['forecast_date'];b='No verified forecast' if not date else x['broker']+' '+date[8:]+' '+{'08':'Aug','09':'Sep','10':'Oct'}[date[5:7]]
 mark='†' if x['broker'] and 'EtNet' in x['broker'] else ''
 return [x['name']+'\n'+code,price,f'{x["ps25"]:.1f}x',fmt(x['pe26'])+mark,fmt(x['pe27'])+mark,b]
def targetrow(c):
 x=I[c];b={'2635':'No verified forecast','3317':'GTJ / EtNet 28 Sep†','6600':'Great Wall 20 Oct','6651':'Huatai / EtNet 15 Sep†'}[c];m='†' if c in ['3317','6651'] else ''
 return [x['name'].split(' ')[0]+'\n'+c+' HK',f'HK${x["price"]:.3f}',f'{x["ps25"]:.1f}x',fmt(x['pe26'])+m,fmt(x['pe27'])+m,b]
headers=['Company / code','26 Oct price','FY2025\nP/S','FY2026E\nP/E','FY2027E\nP/E','Selected forecast / date']
widths=[2572,1300,1000,1100,1100,2900]

def valuationtable(rows,meta):
 tb=table(headers,rows,widths,left_cols=(0,5))
 for tr,x in zip(tb.findall('w:tr',NS)[1:],meta):
  if x:
   p=tr.findall('w:tc',NS)[-1].find('w:p',NS);label=''.join(p.xpath('.//w:t/text()',namespaces=NS))
   for r in list(p):
    if r.tag!=q('pPr'):p.remove(r)
   hyperlink(p,label,x)
 out(tb)
head('Valuation — infrastructure AI, data and simulation',True)
textp('Common 26 October prices and FX; actual FY2025 sales for every P/S. Forward P/E is a dated selected forecast, not consensus. † Vendor-listed owner-profit estimates: original broker adjustment conventions not independently verified.',after=100)
keys=['2635','2121 HK','20 HK','600728 A','3317','1384 HK','6682 HK','600570 A','6651','2571 HK','68 HK','300036 A']
valuationtable([targetrow(k) if k in I else peerrow(k) for k in keys],[('https://www.etnet.com.hk/www/tc/stocks/realtime/quote_profit.php?code='+k if k in ['3317','6651'] else None) if k in I else P[k]['forecast_url'] for k in keys])
textp('NM = forecast loss; n/v = no verified exact estimate. Do not treat n/v as zero or cheap. Saimo’s HK$16.20 quote matches two vendors but 26 October volume was zero; it is a valuation reference, not an executable hedge.',before=75,after=80)
head('Which comparisons matter')
bullet('**2635:** AInnovation is the closest H reference for industrial AI project delivery; PCI is the closest A reference for rail/city systems. SenseTime is a broader AI platform. PCI’s hardware/integration mix depresses P/S, so its 1.0x is not a like-for-like target for Nuobikan’s higher margins.')
bullet('**3317:** Deepexi is the closest H enterprise-data/AI reference; Phancy is adjacent in enterprise decision AI. Hundsun overlaps financial clients and software, with slower growth and more established earnings. The premium must be earned through cash and recurring usage, not simply assigned because revenue grew faster.')
bullet('**6651:** Saimo is the most direct H simulation/testing peer. Manycore overlaps spatial software/data, and SuperMap overlaps GIS/digital twins; neither is an identical autonomous-driving platform. 51WORLD’s 60.5x historical P/S is far above all three. Even Guosheng’s newer growth case leaves 13.8x FY2027 sales.')
textp('**Forecast reconciliation:** Huatai’s 51WORLD FY2026/27 sales forecasts are RMB623m / RMB1,172m, or 33.8x / 18.0x P/S, with reported losses. Guosheng’s newer estimates are RMB750m / RMB1,530m, but its profit forecast is adjusted. Both are shown explicitly; adjusted earnings are not substituted into the reported-profit row.',after=85)
sources('Source trail: ',[('H issuer financials / HKEX', 'https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=en'),('PCI FY2025',S['pci_annual']),('SuperMap FY2025',S['supermap_annual']),('SenseTime forecast',P['20 HK']['forecast_url']),('51WORLD latest',S['guosheng_51world'])])

head('Valuation — OneRobotics versus consumer / robotics peers',True)
textp('Anker H is the principal H operating comparison. The A listings retain the closest home-robotics product overlaps. Tuya and UBTech show platform/theme valuations, not equivalent product economics.',after=100)
keys=['6600','668 HK','2391 HK','9880 HK','300866 A','688169 A','603486 A']
valuationtable([targetrow(k) if k in I else peerrow(k) for k in keys],[S['greatwall_onerobotics'] if k in I else P[k]['forecast_url'] for k in keys])
head('Trading the valuation gap')
bullet('**Anker is relevant, but it is broader.** Eufy overlaps smart-home devices and household robots; charging, storage and audio diversify the group. At 13.0x FY2027 P/E on the H line, it offers an earnings anchor that OneRobotics’ 352.5x lacks. Product mix and growth prevent a mechanical pair-trade ratio.')
bullet('**Roborock and Ecovacs are the closest category checks.** Both sell home robots with established earnings, at approximately 12x FY2027 P/E. OneRobotics needs new categories to scale without permanently higher selling and development costs. Its recent growth is meaningful, but does not by itself justify a platform multiple.')
bullet('**Tuya / UBTech are secondary references.** Tuya monetises IoT software and devices across brands; UBTech’s industrial humanoid deployments have different customers, capex and delivery cycles. UBTech is also in the HSTECH candidate screen, so a theme hedge can have its own index catalyst.')
head('Valuation discipline')
textp('Prices are the 26 October closing snapshots; Tencent and Sina agree for the target stocks and the quoted comparison lines checked. Anker H also matches an independent historical-price table. Target share counts are taken from the latest capital returns and completed placement notices, not rounded vendor market caps.',after=85)
textp('All H values use H price × total ordinary shares, converted at 1 HKD = RMB0.85634; USD financials use RMB6.7162/USD. These are whole-company values implied by that share line. Anker A and H use the same 589,432,146 issued shares, FY2025 revenue and profit forecasts; they are not combined A+H market caps. Anker’s H discount to A is 22.9% on this basis.',after=85)
textp('No interim annualisation. P/E divides equity value by full-year owner profit; negative forecasts are NM. Broker dates are explicit and estimates can be revised after this snapshot. † Tuya and other marked rows use EtNet’s owner-profit field; the full original broker basis was unavailable. Use unmarked reported-profit rows for strict accounting comparisons. Primary filings, raw inputs, formulas and limitations accompany the brief in the repository.',after=85)
textp('At a purely illustrative 30x reported P/E, OneRobotics would need RMB329m annual owner profit, versus Great Wall’s RMB28m FY2027 forecast. 51WORLD would need RMB702m, versus current losses. These are profit hurdles, not forecasts or target prices.',after=85)
sources('Evidence: ',[('Anker shares',filing('2026/1007','2026100700758')),('Anker forecast',P['668 HK']['forecast_url']),('Roborock forecast',P['688169 A']['forecast_url']),('Ecovacs forecast',P['603486 A']['forecast_url']),('FX parity','https://www.safe.gov.cn/AppStructured/hlw/RMBQuery.do'),('Tuya FY2025',filing('2026/0303','2026030300005'))])

head('Event calendar — distinguish fixed dates from forecasts',True)
out(table(['Date / window','Event / status','Stock relevance'],[
['29 Oct 2026','Anker Q3 board meeting — confirmed','Sector read-through for 6600; not a target-company earnings date.'],
['11 Nov / 1 Dec','MSCI review announcement / effective date — scheduled','No stock-specific new addition verified for these four. Watch actual results; no automatic inclusion from time listed.'],
['20 Nov / 7 Dec','Hang Seng review / HSTECH implementation — scheduled','3317 is in a published analyst candidate screen; still unconfirmed. Rebalance trading commonly concentrates at the prior close.'],
['22–23 Dec','2635: last locked 22 Dec; release from 23 Dec','266.48m original H shares; no disclosed sale commitment identified.'],
['29–30 Dec','3317 / 6600 / 6651: last locked 29 Dec; release from 30 Dec','244.48m / 156.35m / 363.30m original H shares respectively.'],
['By 31 Mar 2027','FY2026 results — deadline; exact dates unannounced','For all four. Profit warnings and business updates can arrive earlier.'],
['29–30 Jun 2027','6600 founder extension ends 29 Jun; release from 30 Jun','43.65m directly held shares remain excluded from December supply.'],
['Jul 2027','3317 convertible maturity','RMB1.268bn outstanding in September; watch conversion, redemption or refinancing.']
],[2020,4020,3932],left_cols=(0,1,2)))
head('Index / Southbound conclusions')
bullet('**Southbound is already open.** Xunce, OneRobotics and 51WORLD entered in March 2026; Nuobikan’s 2635 line was added from the next Connect session after 17 April, i.e. 20 April. Current vendor eligibility flags also show admission. There is no first-admission date to trade now; ongoing mainland demand is a flow variable.')
bullet('**HSTECH has changed materially.** October rules expand it to 50 stocks: 40 selected by market value and 10 by revenue growth. Non-members need three-month daily turnover of at least HK$100m; the growth stream needs at least HK$500m sales in each of the last two fiscal years. Eligibility also requires HSCI large/mid-cap membership. Xunce has a named candidate call; no equivalent call was verified for the other three.')
bullet('**Expiry is not automatic passive buying.** Index free float excludes strategic holdings under provider rules, so a contractual unlock does not guarantee a matching weight increase. The next MSCI review after December is announced 9 February 2027, effective 1 March; it is a monitoring window, not an inclusion prediction.')
head('Before treating the overhang as a short catalyst')
textp('The SFC’s 16 October reported short positions were 0 / 908,700 / 308,278 / 619,200 shares for 2635 / 3317 / 6600 / 6651 (0.00% / 0.27% / 0.14% / 0.15% of current total shares). These lagged, threshold-based observations do not measure total borrowing or prove an uncrowded trade. Zero means no reportable aggregate in that file, not no shorts.',after=85)
textp('Look for an actual secondary block, disposal filing or sustained sell flow; distinguish custody transfers from sales. Obtain executable borrow with size, fee and recall terms before sizing. An illustrative 30% annual borrow fee costs about 5% over two months before price movement. Thin turnover and an index/news squeeze can dominate an otherwise sound fundamental thesis.',after=85)
sources('Calendar / rules: ',[('HSTECH methodology',S['hstech_rules']),('Xunce candidate screen',S['hstech_candidate']),('Hang Seng dates',S['hstech_calendar']),('MSCI dates',S['msci_calendar']),('April Connect notice',S['southbound_2635']),('March Connect report',S['southbound_march']),('HKEX short list','https://www.hkex.com.hk/-/media/HKEX-Market/Services/Trading/Securities/Securities-Lists/Designated-Securities-Eligible-for-Short-Selling/ds_list20261023.csv')])

out(deepcopy(donors[-1]))
assert etree.tostring(body[-1],method='c14n',exclusive=True)==etree.tostring(donors[-1],method='c14n',exclusive=True)
xml=etree.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True);rx=etree.tostring(rels,encoding='UTF-8',xml_declaration=True,standalone=True)
with ZipFile(args.output,'w',ZIP_DEFLATED) as z:
 for n,b in original.items():z.writestr(n,xml if n=='word/document.xml' else rx if n=='word/_rels/document.xml.rels' else b)
with ZipFile(args.output) as z:
 changed=[n for n,b in original.items() if z.read(n)!=b]
 assert set(changed)=={'word/document.xml','word/_rels/document.xml.rels'}
 assert set(z.namelist())==set(original)
assert sha(args.template)==A['template']['sha256']
qa=dict(document_sha256=sha(args.output),parts=len(original),only_changed_parts=changed,tables=len(body.findall('w:tbl',NS)),sections=1,template_unchanged=True,python_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1048576)
(HERE/'document_qa.json').write_text(json.dumps(qa,indent=2));print(json.dumps(qa))
(T/'draft_text.txt').write_text('\n'.join(''.join(e.xpath('.//w:t/text()',namespaces=NS)) for e in body))
