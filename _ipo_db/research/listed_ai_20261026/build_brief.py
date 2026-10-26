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

# Reader order: desk summary, four identical company pages, source key.
def page_title(text,new=True):
 p=para(text,kind='title',after=130,pagebreak=new)
 for rp in p.findall('w:r/w:rPr',NS):prop(rp,'sz',val=28);prop(rp,'szCs',val=28)
 out(p)

def valuation(c,keys):
 rows=[]
 for k in [c]+keys:
  target=k in I;x=I[k] if target else P[k]
  mark='†' if (target and k in ['3317','6651']) or (not target and x['broker'] and 'EtNet' in x['broker']) else ''
  name=x['name'].split(' ')[0] if target else x['name']
  ccy='HK$' if target or x['price_currency']=='HKD' else 'RMB'
  code=k+' HK' if target else k
  rows.append([name+' '+code,ccy+f'{x["price"]:.3f}',f'{x["ps25"]:.1f}x',fmt(x['pe26'])+mark,fmt(x['pe27'])+mark])
 tb=table(['Company','26 Oct price','FY2025 P/S','FY2026E P/E','FY2027E P/E'],rows,[3492,1620,1620,1620,1620])
 # Distinguish the subject from its peers without another colour system.
 for c1 in tb.findall('w:tr',NS)[1].findall('w:tc',NS):prop(c1.find('w:tcPr',NS),'shd',val='clear',color='auto',fill='F2F2F2')
 out(tb)

def company(c,theme,view):
 x=I[c];page_title(c+'  '+x['name'])
 textp(theme+'  |  Equity value HK$'+f'{x["equity_hkdm"]/1000:.2f}'+'bn',after=90)
 textp('**Desk view  '+view+'**',after=110)
 facts(c)

page_title('IPO lockup trading brief',False)
textp('2635  /  3317  /  6600  /  6651     •     26 October 2026 close',after=130)
textp('**Research priority: Xunce and 51WORLD.** OneRobotics has a valuation concern but difficult short liquidity. Nuobikan needs evidence of collection problems to strengthen the bearish case.',after=130)
head('The four calls')
out(table(['Stock and theme','Core concern','Main risk to the short'],[
 ['2635 Nuobikan\nInfrastructure AI','Weak cash conversion; receivables exceed annual sales.','Profitable at 15.4x LTM P/E; compute orders could improve growth.'],
 ['3317 Xunce\nEnterprise data','RMB661m H1 cash outflow; investment gains support profit.','December HSTECH inclusion is a published analyst possibility.'],
 ['6600 OneRobotics\nHome robotics','Costs outrun growth; 352.5x FY2027E P/E.','New products and thin turnover can drive a squeeze.'],
 ['6651 51WORLD\nPhysical AI','60.5x FY2025 sales; recurring cash earnings unproven.','NVIDIA ecosystem news and Aper deliveries support the theme.']
],[2280,3846,3846],left_cols=(0,1,2)))
head('December supply at a glance')
rows=[]
for c in ['2635','3317','6600','6651']:
 x=I[c];rows.append([c,x['first_released'][8:]+' Dec',f'{x["unlock_h"]/1e6:.2f}m',f'{x["unlock_pct_total"]:.1f}%',f'{x["unlock_adv"]:.1f}x'])
out(table(['Code','First release','H shares','% total shares','Shares / 20d ADV'],rows,[1000,1900,2200,2200,2672]))
textp('Identified original pre-IPO H holdings only. Last locked day is the preceding date. OneRobotics excludes the founder’s extended lock. Supply is potential, not a forecast of selling.',before=80,after=100)
head('Dates that matter before taking the short')
out(table(['Date','Event','Trading relevance'],[
 ['29 Oct','Anker Q3 board meeting','Early consumer-hardware read-through for 6600.'],
 ['11 Nov / 1 Dec','MSCI review / effective','Scheduled; no new addition verified for these four.'],
 ['20 Nov / 7 Dec','Hang Seng review / HSTECH effective','Xunce is an analyst add candidate; inclusion unconfirmed.'],
 ['By 31 Mar 2027','FY2026 results deadline','Exact dates for all four remain unannounced.']
],[2100,3400,4472],left_cols=(0,1,2)))
head('Execution matters')
textp('**Southbound:** all four already admitted. **Borrow:** all are designated short-sale securities, but availability, fee and recall terms are unverified. **Selling:** recent DI percentage reductions mainly reflect new-share dilution; expiry alone is not evidence of an exit.',after=110)
textp('Company pages: 2635 p2  •  3317 p3  •  6600 p4  •  6651 p5  |  Sources and definitions p6',after=0)

company('2635','Rail inspection, power monitoring and urban systems','Cash collection is the test; valuation alone is a weaker short case.')
head('Good points')
bullet('**A profitable specialist.** 2024 niche shares were 5.9% in AI rail-power inspection and 1.8% in broader AI rail inspection. Reported LTM owner profit is RMB131.5m; H1 gross margin recovered to 55.0%.')
bullet('**Compute spending creates upside.** August’s RMB50.8m software contract with a domestic AI chip company is about 10% of FY2025 sales, including VAT. Repeat orders and payment would strengthen the growth case.')
head('Risks')
bullet('**Earnings are ahead of cash.** June receivables were RMB637.9m versus RMB498.2m FY2025 sales. H1 operating cash covered 50% of profit; city projects were 54% of sales, exposing collections to budgets and acceptance.')
bullet('**Growth is expensive.** H1 R&D rose 165% and selling costs 183%, versus sales growth of 32%. A supplier’s accounting penalty adds diligence risk; it does not establish misconduct by Nuobikan, which disputes any issue with its transactions.')
head('Valuation versus peers')
valuation('2635',['2121 HK','20 HK','600728 A'])
textp('**Closest:** AInnovation for H-share project economics; PCI for A-share rail/city exposure. PCI’s hardware mix makes its lower P/S an imperfect target. SenseTime is a broader AI comparison.',before=75,after=85)
head('Catalysts and shareholder actions')
bullet('**9 October placing:** 16.49m new H shares at HK$8.19; net HK$131.5m. The close is 27% below the placing price. Reviewed DI changes were dilution, not disclosed disposals.')
bullet('**23 December release:** 266.48m H shares, including 136.90m outside the controller group. FY2026 results are due by March 2027; no verified new index-add call.')
textp('**Confirms the short:** ageing receivables or higher provisions.\n**Invalidates it:** strong collections and repeat chip/compute orders.',after=90)
textp('Forecast unavailable for 2635. NM = loss; n/v = unavailable. Forecast dates and sources: p6.',after=0)

company('3317','Real-time enterprise data and usage-based AI services','Strongest earnings-quality concern; index buying could arrive before selling.')
head('Good points')
bullet('**A useful enterprise-AI function.** Prospectus research ranks it first in China’s asset-management real-time data market (11.6% in 2024), but fourth across industries (3.4%). H1 revenue rose 389%.')
bullet('**Usage billing could improve scalability.** Token revenue exceeded 10%; industries outside asset management contributed 87.6%. Shenton’s October screen also names Xunce as a December HSTECH candidate.')
head('Risks')
bullet('**Reported profit depends on investment gains.** H1 pretax profit was RMB67.0m, including RMB101.4m fair-value gains. Removing that gain alone gives a RMB34.4m pretax loss. Gross margin fell 6.6 percentage points.')
bullet('**Cash demand is accelerating.** H1 operating outflow was RMB661.2m; transaction-based products remained 90.5% of sales. The proposed RMB12bn project increases execution and funding risk; its budget is not cash already spent.')
head('Valuation versus peers')
valuation('3317',['1384 HK','6682 HK','600570 A'])
textp('**Closest:** Deepexi in H enterprise data/AI; Hundsun for A financial software. Phancy is adjacent. Xunce’s premium needs repeat usage and collections. † Indicative vendor forecasts; original broker accounting basis unverified.',before=75,after=85)
head('Catalysts and shareholder actions')
bullet('**20 November / 7 December:** HSTECH decision / effective date. **30 December:** 244.48m H shares release, including 174.41m outside the largest shareholder group. Tencent/GBA DI percentage declines were dilution.')
bullet('**Financing:** July placed 7.283m shares at HK$107.70 and issued RMB1.36bn zero-coupon bonds. RMB1.268bn remained in September, due July 2027; conversion HK$123.86, redemption 101.75%.')
textp('**Confirms the short:** continued cash burn or fresh funding without cash returns.\n**Invalidates it:** sustained token cash generation; index inclusion is a near-term squeeze risk.',after=90)
textp('FY2026 earnings: date unannounced, due by March 2027. Forecast dates and sources: p6.',after=0)

company('6600','SwitchBot smart-home devices and emerging embodied robots','The growth premium is large; thin turnover makes the short difficult to execute.')
head('Good points')
bullet('**A distribution base for new products.** Prospectus research cites 11.9% of the narrowly defined global home-robotic-system market in 2024. Onero H1, Acemate and Kata produced 13.1% of H1 sales.')
bullet('**Growth has funding.** Europe and North America grew 97.5% and 85.7%; June cash/bank balances plus structured deposits were RMB1.595bn. Much investing outflow was a move into term deposits.')
head('Risks')
bullet('**Costs outrun sales.** H1 gross margin fell to 50.4%; selling and R&D costs rose 63% and 73%. Forward gains of RMB33.8m offset much of the RMB42.7m FX loss, so FX alone does not explain the earnings reversal.')
bullet('**Inventory needs to sell through.** It absorbed RMB100.1m of cash; provisions rose to RMB9.8m from RMB5.7m. Great Wall forecasts only RMB28m FY2027 owner profit despite RMB2.045bn sales.')
head('Valuation versus peers')
valuation('6600',['668 HK','2391 HK','9880 HK','300866 A','688169 A','603486 A'])
textp('**Closest:** Anker H for global smart-home hardware; Roborock/Ecovacs for home robots. Tuya and UBTech are secondary platform/theme references. † Vendor forecast basis unverified.',before=75,after=85)
head('Catalysts and shareholder actions')
bullet('**29 October:** Anker Q3 read-through. **30 December:** 156.35m H shares release; founder Li Zhichen’s 43.65m stay locked through 29 June 2027. Average daily turnover is just 0.227m shares.')
bullet('**Trust buying:** 653,200 shares for HK$39.9m by 14 September; employee-scheme stock, not cancellation. No new July–26 October DI notices found. FY2026 results due by March 2027, date unannounced.')
textp('**Confirms the short:** weak sell-through and continued margin pressure.\n**Invalidates it:** successful Q4 launches, cash conversion and margin recovery.',after=0)

company('6651','51Sim simulation, digital twins and physical-AI training infrastructure','Largest valuation stretch; theme momentum can persist before earnings catch up.')
head('Good points')
bullet('**A strong simulation niche.** The FY2025 report cites 53.5% of China’s end-to-end high-level driving simulation/data-platform market. H1 51Sim sales rose 545% to RMB51.2m, or 41.4% of revenue.')
bullet('**Visible physical-AI catalysts.** 51Sim joined NVIDIA’s Halos SAFE ecosystem on 22 October. Aper orders exceeded RMB200m by 16 September, with over 90% targeted for delivery this year.')
head('Risks')
bullet('**Orders still need to become cash.** Hardware/software delivery, acceptance and collection remain essential. NVIDIA ecosystem participation does not itself establish contracted revenue; initial equipment orders do not prove recurring usage.')
bullet('**The earnings hurdle is high.** H1 losses and cash outflow continued. Guosheng’s newer forecasts imply 28.1x / 13.8x FY2026/27 sales, but only -RMB110m / +RMB10m adjusted profit; this is not reported breakeven.')
head('Valuation versus peers')
valuation('6651',['2571 HK','68 HK','300036 A'])
textp('**Closest:** Saimo for H simulation/testing; SuperMap for A digital twins. Manycore is adjacent spatial software. Saimo had zero volume on 26 October. † Vendor forecast basis unverified; Huatai expects reported losses in both years.',before=75,after=85)
head('Catalysts and shareholder actions')
bullet('**Year-end Aper deliveries** are the next operating test. **30 December:** 363.30m original H shares release, including 79.26m held by LS51World Holding Limited and Sky9 51World Limited.')
bullet('**10 July placing:** 5.466m shares at HK$73.20; net HK$394.5m. The close is 20% lower. Li Yi/LS51World DI changes were dilution; September RSUs are incentives. FY2026 results due by March 2027; no verified new index-add call.')
textp('**Confirms the short:** missed acceptance, margin dilution or weak repeat orders.\n**Invalidates it:** paid deployments and recurring usage at improving margins.',after=90)
textp('Market-share claims use narrow commissioned definitions. Forecast dates and sources: p6.',after=0)

page_title('Sources and valuation basis')
textp('Prices are dated 26 October 2026. Forecast dates and accounting conventions are listed below.',after=100)
head('How to read the numbers')
textp('**P/S:** FY2025 actual sales. **P/E:** dated full-year owner-profit forecasts; no interim annualisation. **NM:** forecast loss. **n/v:** no verified exact forecast. **†:** EtNet owner-profit field; the original broker adjustment basis is unverified. These are selected estimates, not consensus.',after=85)
textp('H-share values apply H price to total ordinary shares. FX: RMB0.85634/HKD and RMB6.7162/USD, SAFE central parity. Anker A/H use identical shares and earnings; their line-implied values are separate, with a 22.9% H discount. Target capital counts use filings; most peer market caps use the dated quote feeds.',after=85)
head('Forecast source key')
forecast_rows=[
 ('3317','GTJ / EtNet · 28 Sep†','https://www.etnet.com.hk/www/tc/stocks/realtime/quote_profit.php?code=3317'),
 ('6600','Great Wall · 20 Oct',S['greatwall_onerobotics']),
 ('6651','Huatai / EtNet · 15 Sep†',S['huatai_51world']),
 ('SenseTime 20','GTHT · 10 Sep',P['20 HK']['forecast_url']),
 ('Deepexi 1384','GTJ / EtNet · 20 Sep†',P['1384 HK']['forecast_url']),
 ('Phancy 6682','JPM / EtNet · 23 Sep†',P['6682 HK']['forecast_url']),
 ('Manycore 68','JPM / EtNet · 23 Sep†',P['68 HK']['forecast_url']),
 ('Hundsun 600570','Soochow · 25 Aug',P['600570 A']['forecast_url']),
 ('Anker H 668 / A 300866','Kaiyuan · 1 Sep',P['668 HK']['forecast_url']),
 ('Roborock 688169','Guosen · 12 Oct',P['688169 A']['forecast_url']),
 ('Ecovacs 603486','Guosen · 13 Oct',P['603486 A']['forecast_url']),
 ('Tuya 2391','CICC / EtNet · 29 Aug†',P['2391 HK']['forecast_url']),
 ('UBTech 9880','CICC · 29 Aug',P['9880 HK']['forecast_url'])]
tb=table(['Stock','Broker and 2026 forecast date'],[[x,y] for x,y,z in forecast_rows],[4000,5972],left_cols=(0,1))
for row,(_,label,url) in zip(tb.findall('w:tr',NS)[1:],forecast_rows):
 p=row.findall('w:tc',NS)[1].find('w:p',NS)
 for x in list(p):
  if x.tag!=q('pPr'):p.remove(x)
 hyperlink(p,label,url)
out(tb)
textp('**51WORLD reconciliation:** Huatai sales RMB623m / RMB1,172m imply 33.8x / 18.0x FY2026/27 P/S, with reported losses. Guosheng sales RMB750m / RMB1,530m imply 28.1x / 13.8x; its profit estimates are adjusted. They are not mixed in the P/E table.',before=75,after=85)
head('Primary filings and supporting research')
sources('2635  ',[('H1 results',filing('2026/0916','2026091600183')),('FY2025',filing('2026/0428','2026042805085')),('lockup',filing('2025/1222','2025122201578')),('placing',filing('2026/1009','2026100901015')),('supplier clarification',filing('2026/0511','2026051101486'))])
sources('3317  ',[('H1 results',filing('2026/0921','2026092100985')),('lockup',filing('2025/1229','2025122902057')),('project',filing('2026/0909','2026090900997')),('financing',filing('2026/0703','2026070300105')),('index forecast',S['hstech_candidate'])])
sources('6600  ',[('H1 results',filing('2026/0918','2026091800725')),('lockup',filing('2025/1229','2025122902399')),('founder extension',filing('2026/0630','2026063002277')),('trust purchases',filing('2026/0914','2026091401199'))])
sources('6651  ',[('H1 results',filing('2026/0921','2026092100462')),('lockup',filing('2025/1229','2025122902393')),('Aper orders',filing('2026/0916','2026091601231')),('NVIDIA',filing('2026/1022','2026102200055')),('Guosheng',S['guosheng_51world']),('Xueqiu',S['xueqiu_51world'])])
sources('Events  ',[('HSTECH rules',S['hstech_rules']),('Hang Seng dates',S['hstech_calendar']),('MSCI dates',S['msci_calendar']),('Anker meeting',filing('2026/1016','2026101600304')),('Connect April',S['southbound_2635']),('Connect March',S['southbound_march'])])
textp('**Lockup scope:** identified IPO restrictions only; excludes unlisted shares, post-IPO options and the 6600 founder extension. Other insider rules may apply. ADV covers 25 September–26 October. Full disclosure links, source hashes, shareholder reconciliation and limitations are in the repository audit.',before=75,after=0)

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
