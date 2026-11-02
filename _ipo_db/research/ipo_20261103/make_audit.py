"""Dated inputs and transparent arithmetic for the November 2026 Word briefing.
No workbook or database inputs are changed. Sources are factual extracts, not copies of reports.
"""
import json,hashlib,re
from pathlib import Path
D=Path('/private/tmp/ipo-20261103');HERE=Path(__file__).resolve().parent
fx=.85595
A={'as_of':'2026-11-02 Hong Kong close; filings through 2026-11-02 evening','template':{'path':'/Users/lemon/Downloads/ipo analysis.docx','sha256':'ea8859ddd61c5ea574bd69c628c59d2bd737c732afdfa3b68da714587288f899'},'fx':{'cny_per_hkd':fx,'date':'2026-11-02','basis':'CFETS central parity, not closing spot','source':'https://finance.eastmoney.com/a/202611023917883759.html'}}
I={}
def issuer(c,name,shares,lo,hi,rev,gp,np,cfo,period='4M',**kw):
 I[c]=dict(name=name,shares=shares,low=lo,high=hi,rev25=rev[0],rev_prev=rev[1],rev_now=rev[2],gp25=gp[0],gp_prev=gp[1],gp_now=gp[2],np25=np[0],np_prev=np[1],np_now=np[2],cfo25=cfo[0],cfo_prev=cfo[1],cfo_now=cfo[2],period=period,fy26_np=None,fy27_np=None,**kw)
issuer('2206','Neautus 新荷花',65172741,40.20,50.55,[1334.707,382.819,432.185],[253.161,72.234,94.228],[106.441,20.740,33.878],[154.051,-22.868,-26.996],close='2026-11-06',listing='2026-11-11',offer_shares=6517300)
issuer('7672','Xinde 芯德半導體',1065624232,8.60,9.60,[1012.159,306.371,359.672],[-182.464,-62.692,-64.261],[-437.165,-155.648,-138.044],[39.960,110.723,-108.150],close='2026-11-05',listing='2026-11-10',offer_shares=106562500,group_loss25=-483.088,adjusted_group_loss25=-273.907,adjusted_group_loss_prev=-87.140,adjusted_group_loss_now=-101.022)
issuer('9917','Denglin 登臨科技-P',60827518,231,288,[171.292,5.796,200.365],[84.302,3.402,102.016],[-281.005,-108.280,-16.474],[-295.022,-164.224,-146.744],close='2026-11-05',listing='2026-11-10',offer_shares=6125000)
issuer('2681','Hosin 宏芯宇',482531284,72.29,82.90,[11237.576,2804.510,8012.275],[2446.388,386.592,4968.808],[1363.885,123.068,3840.646],[716.701,-430.187,-2691.062],close='2026-11-09',listing='2026-11-12',offer_shares=14717000)
issuer('2687','Able Digital 卓越睿新',66666700,81.05,81.05,[969.406,275.421,327.942],[634.598,129.198,165.363],[130.224,-98.956,-116.414],[-64.021,-258.014,-364.183],period='H1',last_locked='2026-12-07',first_release='2026-12-08',h_shares=61952800,unlock_h=55286100,excluded_domestic=4713900,controller_h=23066820,other_old_h=32219280)
I['2687'].update(fy26_np=200,fy27_np=280,forecast_source='Guosheng 13 August 2026; rounded figures publicly reported 14 August. Predates H1 results and October subsidiary penalty; not current consensus.')
issuer('1333','Breton 博雷頓',426197162,16.39,16.39,[779.483,326.775,330.674],[86.174,20.950,54.484],[-318.629,-174.184,-81.646],[-174.6,-147.909,-165.094],period='H1',last_locked='2026-11-06',first_release='2026-11-07',first_session='2026-11-09',h_shares=393921890,treasury_h=1420800,unlock_h=102515835,qiu_blocked_h=3091551,screened_cohort_h=99424284,extended_funds_h=58909668,funds_last_locked='2027-02-28',funds_first_session='2027-03-01')
for c,x in I.items():
 x['mid']=77.60 if c=='2681' else (x['low']+x['high'])/2
 x['ltm_rev']=x['rev25']+x['rev_now']-x['rev_prev'];x['ltm_np']=x['np25']+x['np_now']-x['np_prev']
 for s in ['low','mid','high']:
  cap=x[s]*x['shares']/1e6;x['equity_hkdm_'+s]=cap;x['equity_cnym_'+s]=cap*fx
  x['ps25_'+s]=cap*fx/x['rev25'];x['pe25_'+s]=cap*fx/x['np25'] if x['np25']>0 else 'NM'
  x['ltm_ps_'+s]=cap*fx/x['ltm_rev'];x['ltm_pe_'+s]=cap*fx/x['ltm_np'] if x['ltm_np']>0 else 'NM'
 x['pe26']=x['equity_cnym_mid']/x['fy26_np'] if x['fy26_np'] else None;x['pe27']=x['equity_cnym_mid']/x['fy27_np'] if x['fy27_np'] else None
 if c in ['2687','1333']:
  d=json.loads((D/('hk'+c.zfill(5)+'_daily.json')).read_text())['data']['hk'+c.zfill(5)];rows=[r for r in d.get('qfqday',d.get('day')) if '2026-10-13'<=r[0]<='2026-11-02'];assert len(rows)==14
  x['adv_sessions']=14;x['adv_shares']=sum(float(r[5]) for r in rows)/14;x['adv_start']='2026-10-13';x['daily_turnover']=[{'date':r[0],'close':float(r[2]),'shares':float(r[5])} for r in rows];x['unlock_adv']=x['unlock_h']/x['adv_shares'];x['unlock_pct_total']=x['unlock_h']/x['shares']*100
I['2687']['h2_profit_required_for_200m']=200-I['2687']['np_now'];I['2687']['h2_2025_profit']=I['2687']['np25']-I['2687']['np_prev']
I['2687']['required_h2_profit_growth']=I['2687']['h2_profit_required_for_200m']/I['2687']['h2_2025_profit']-1
I['2687']['cfo_ltm']=-64.021-364.183+258.014
I['2681']['profit_scenarios']=[{'sustainable_profit_cnym':p,'mid_pe':I['2681']['equity_cnym_mid']/p} for p in [1500,3000,6000]]
I['2206']['profit_scenarios']=[{'growth':g,'profit_cnym':106.441*(1+g),'mid_pe':I['2206']['equity_cnym_mid']/(106.441*(1+g))} for g in [.2,.4]]
# Current price snapshot from Tencent. Values are price-class-implied total-equity values, not free-float or summed A+H values.
Q={}
for l in (D/'quotes_raw.txt').read_text().splitlines():
 p=l.split('"')[1].split('~');key=l.split('=')[0].split('_')[-1];Q[key]={'name':p[1],'price':float(p[3]),'quote_date':p[30],'equity_quote_m':float(p[45])*100}
E=json.loads((D/'etnet_clean.json').read_text());P={}
F={'570':(582,728,'Morgan Stanley','2026-08-31'),'2273':(407,480,'CITIC','2026-09-08'),'522':(2039,2710,'CLSA','2026-10-29'),'9903':(-404,1076,'CLSA','2026-09-14'),'6082':(-1091,944,'Goldman Sachs','2026-10-21'),'9976':(17112,14885,'Citi','2026-11-02'),'777':(301.66,547.94,'First Shanghai','2026-09-22'),'631':(2211,3147,'CLSA','2026-10-30'),'1157':(4807,6184,'Citi','2026-09-28')}
N={'570':('China TCM','Closest H product mix; granules and finished medicines also material'),'2273':('Gushengtang','Adjacent downstream TCM clinics'),'522':('ASMPT','Adjacent packaging-equipment supplier; not an OSAT'),'9903':('Iluvatar CoreX','Direct GPGPU developer'),'6082':('Biren','Direct GPGPU developer'),'9976':('Longsys H','Direct memory modules and controllers'),'777':('NetDragon','Adjacent digital education with material gaming exposure'),'2469':('Fenbi','Adjacent adult training; not university digitisation'),'631':('Sany International','Closest H mining-equipment exposure; diversified'),'1157':('Zoomlion H','Adjacent diversified construction equipment')}
for c,(name,rel) in N.items():
 t=E[c+'_quote_ci_pl'];rev_tokens=t[t.index('營業額 / 收益'):].split();rev=float(rev_tokens[5].replace(',',''))/1000
 # The first five tokens are label tokens and current-period value; use an explicit expression to avoid ambiguous slash-token indexing.
 m=re.search(r'營業額 / 收益\s+[\d,]+\s+[-\d.]+%\s+([\d,]+)',t);rev=float(m.group(1).replace(',',''))/1000
 m=re.search(r'股東應佔溢利 / \(虧損\)\s+(?:\([\d,]+\)|[\d,]+)\s+(?:[-\d.]+%|--)\s+(\([\d,]+\)|[\d,]+)',t);np=float(m.group(1).replace(',','').replace('(','-').replace(')',''))/1000
 q=Q['hk'+c.zfill(5)];profit_ccy='HKD' if c=='522' else 'CNY';cap=q['equity_quote_m']*(1 if profit_ccy=='HKD' else fx)
 f=F.get(c,(None,None,None,None));P[c+' HK']=dict(code=c+' HK',name=name,relation=rel,price_currency='HKD',profit_currency=profit_ccy,price=q['price'],equity_hkdm=q['equity_quote_m'],equity_profit_m=cap,rev25=rev,np25=np,fy26_np=f[0],fy27_np=f[1],broker=f[2],forecast_date=f[3],basis='EtNet-labelled profit forecast; original broker accounting adjustments not independently verified',forecast_url='https://www.etnet.com.hk/www/tc/stocks/realtime/quote_profit.php?code='+c,historical_url='https://www.etnet.com.hk/www/tc/stocks/realtime/quote_ci_pl.php?code='+c)
AP=[('300181','Zoli','Product overlap in decoction pieces; majority branded finished drugs',3041,631.93,787.33,953.81,'China Post','2026-09-12','AP202609121829316730'),('600584','JCET','Direct OSAT; larger and profitable',38871,1565,2283,2936,'Shanxi','2026-10-28','AP202610281831069536'),('688362','Ningbo Silicon','Direct OSAT; small profit base',4398,81.73,120.05,278.84,'Soochow','2026-10-30','AP202610301831207492'),('688795','Moore Threads','Direct GPU developer; broader full-function portfolio',1506,-1001,150,1243,'Shanxi','2026-10-30','AP202610301831227112'),('688525','Biwin','Direct memory module/controller and packaging exposure',11302,853,14657,16182,'Sinolink','2026-08-10','AP202608101827803026'),('000528','LiuGong','Direct overlap in battery-electric loaders; diversified',33144,1609.23,1684.92,2094.88,'China Post','2026-10-30','AP202610301831238126'),('300559','Jiafa Education','Closest A education IT; examination hardware differs',430.529643,31.656620,None,None,None,None,None)]
for c,name,rel,rev,np,n26,n27,b,date,info in AP:
 q=Q[('sh' if c.startswith('6') else 'sz')+c];P[c+' A']=dict(code=c+' A',name=name,relation=rel,price_currency='CNY',profit_currency='CNY',price=q['price'],equity_profit_m=q['equity_quote_m'],rev25=rev,np25=np,fy26_np=n26,fy27_np=n27,broker=b,forecast_date=date,basis='Reported attributable profit; original broker PDF read' if info else 'No current public forecast verified',forecast_url='https://pdf.dfcfw.com/pdf/H3_'+info+'_1.pdf' if info else None,historical_url='https://static.cninfo.com.cn/finalpage/2026-04-21/1225130651.PDF' if c=='300559' else None)
# Same issuer, same profit estimates and share base: A/H valuation is a class-price comparison.
h=P['9976 HK'];q=Q['sz301308'];P['301308 A']={**h,'code':'301308 A','name':'Longsys A','price_currency':'CNY','price':q['price'],'equity_profit_m':q['equity_quote_m'],'relation':'Same company as 9976; same Citi profit estimates used'}
for p in P.values():
 cap=p['equity_profit_m'];p['ps25']=cap/p['rev25'];p['pe25']=cap/p['np25'] if p['np25']>0 else 'NM'
 p['pe26']='NM' if p['fy26_np'] is not None and p['fy26_np']<=0 else cap/p['fy26_np'] if p['fy26_np'] else None
 p['pe27']='NM' if p['fy27_np'] is not None and p['fy27_np']<=0 else cap/p['fy27_np'] if p['fy27_np'] else None
A['issuers']=I;A['peers']=P;A['quotes']=Q
A['limits']=['IPO offer ranges and scheduled dates are provisional until pricing/allotment notices; base deal only, before adjustment and greenshoe.','No verified public FY26/FY27 profit estimate for the four IPOs or Breton. n/v is deliberate; annualised four-month earnings are not forecasts.','EtNet-labelled estimates are individual broker observations, not consensus; adjustments and dilution cannot be fully verified without original notes.','Guosheng Able Digital estimates are rounded public extracts predating the H1 results and penalty.','IPO lockup cohorts are not immediately saleable quantities: director transfer caps, resignation restrictions, blackouts and extensions may apply.','14-session ADV 13 October–2 November avoids Able Digital parallel-counter board-lot change period. Shares, not lots. No live borrow or fee verified.','Broker and social posts are selected views, not representative polls. Inaccessible original Xueqiu links were not described as read.']
A['critical_reconciliations']={'xinde':'Do not confuse 2.5D/3D revenue share with all advanced packaging; BGA/WLP also classified advanced. Redeemable-share liabilities convert on listing; bank debt separately identified.','hosin':'RMB10.8bn private valuation is not IPO market cap. Reciprocal IPO investments with Transsion/Longsys are disclosed as non-interconditional. HK455.32m cornerstone table mixes fee bases; HK451.56m aggregate excludes fees.','able':'FY25 cash-flow statement is -RMB64.021m despite positive-CFO wording in narrative. Wang Xin July DI is loss of deemed partnership interest, not sale. Domestic conversion is proposed, not completed.','breton':'102.515835m contractual H cohort excludes 21.125599m domestic; subtract Qiu3.091551m from near-term screen because resignation transfer restriction; annual director cap remains. Separate 58.909668m funds locked through 28Feb2027; do not add to November cohort.'}
# Primary source registry, includes content hashes and page-text source locators for all downloaded issuer materials.
R={}
for f in sorted(D.glob('*.pdf')):
 k=f.stem
 if k in ['2206','7672e','2681e','9917e']:
  n={'2206':'2026103000020_c','7672e':'2026103000027','2681e':'2026103000025','9917e':'2026103000023'}[k];url='https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1030/'+n+'.pdf'
 elif '_broker' in k:
  p=next((p for p in P.values() if p['code'].startswith(k.split('_')[0])),None);url=p['forecast_url'] if p else None
 elif k.endswith('_allot'):url='https://www1.hkexnews.hk/listedco/listconews/sehk/'+('2025/1205/2025120501787.pdf' if k.startswith('2687') else '2025/0506/2025050602875.pdf')
 elif k in ['1333_articles','1333_resign']:url='https://www1.hkexnews.hk/listedco/listconews/sehk/'+('2026/1021/2026102101047.pdf' if k.endswith('articles') else '2026/1020/2026102001455.pdf')
 elif re.match(r'(2687|1333)_\d{13}$',k):
  n=k.split('_')[1];url='https://www1.hkexnews.hk/listedco/listconews/sehk/'+n[:4]+'/'+n[4:8]+'/'+n+'.pdf'
 else:continue
 R[k]={'url':url,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size}
A['primary_documents']=R
A['other_sources']={'able_di':'https://di.hkex.com.hk/di/NSForm3A.aspx?fn=DA20260723E00090&lang=EN','able_forecast':'https://finance.sina.com.cn/stock/hkstock/hkgg/2026-08-14/doc-ininfvzw2710630.shtml','southbound_able':'https://www.sse.com.cn/services/hkexsc/disclo/announ/c/c_20260306_10811051.shtml','southbound_breton':'https://www.sse.com.cn/services/hkexsc/disclo/announ/c/c_20250905_10790691.shtml','msci':'https://app2.msci.com/eqb/pressreleases/archive/ir_dates.pdf','hsi':'https://finance.sina.com.cn/stock/estate/integration/2026-10-02/doc-initvpqz4618655.shtml','short_list':'https://www.hkex.com.hk/eng/market/sec_tradinfo/ds20261020.htm','niuniu':'https://q.futunn.com/feed/117529347752340','xueqiu_neautus':'https://www.xueqiu.com/9244403865/414958726','xueqiu_neautus_terms':'https://www.xueqiu.com/9244403865/414958819','xueqiu_xinde':'https://www.xueqiu.com/9244403865/414970758','xueqiu_xinde_backers':'https://www.xueqiu.com/9252950692/409987709','xueqiu_denglin':'https://www.xueqiu.com/9244403865/414970218','xinde_critique':'https://finance.sina.com.cn/stock/observe/2026-09-29/doc-initnscx7702383.shtml','hosin_sina':'https://finance.sina.com.cn/stock/stockzmt/2026-10-21/doc-inivyhkr6195510.shtml','neautus_history':'https://www.jiemian.com/article/14508745.html','quote_breton_check':'https://www.marketscreener.com/quote/stock/BRETON-TECHNOLOGY-CO-LTD-187716725/','quote_able_check':'https://daily.hstong.com/quotes/10000-02687-HK'}
assert I['2687']['unlock_h']==I['2687']['controller_h']+I['2687']['other_old_h']
assert I['1333']['unlock_h']-I['1333']['qiu_blocked_h']==I['1333']['screened_cohort_h']
assert I['1333']['shares']==I['1333']['h_shares']+32275272
assert I['7672']['shares']==265152545+693909187+106562500
(HERE/'source_and_valuation_audit.json').write_text(json.dumps(A,ensure_ascii=False,indent=2))
print('Issuers',len(I),'peers',len(P))
for c,x in I.items(): print(c,'cap HKm',round(x['equity_hkdm_mid'],2),'FY25 PE',x['pe25_mid'],'PS',round(x['ps25_mid'],2),'LTM PE',x['ltm_pe_mid'])
for c,p in P.items():print(c,p['name'],'price',p['price'],'PE25',p['pe25'],'PS25',p['ps25'],'PE26/27',p['pe26'],p['pe27'])
