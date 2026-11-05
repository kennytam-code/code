"""Dated research inputs; no market-data or forecast values are imputed.
Run with bundled Python. Currency amounts are millions unless specified.
"""
from pathlib import Path
import json, hashlib
H=Path(__file__).resolve().parent
S={
 'prospectus':'https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1105/2026110500055.pdf',
 'apt_fy25':'https://www.apstar.com/uploads/file/20260326/9a3925d84cb24d52e26057bfc00144a3.pdf',
 'aerospace_fy25_secondary':'https://stock.stockstar.com/AN2026032700002771.shtml',
 'spacesat_fy25':'https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12038644&stockid=600118',
 'spacesat_q3':'https://static.cninfo.com.cn/finalpage/2026-10-29/1225637125.PDF',
 'geovis_fy25':'https://pdf.dfcfw.com/pdf/H2_AN202604141821199765_1.pdf',
 'geovis_q3':'https://static.cninfo.com.cn/finalpage/2026-10-28/1225632671.PDF',
 'planet_results':'https://investors.planet.com/financials/quarterly-results/default.aspx',
 'planet_q2_release':'https://www.nasdaq.com/press-release/planet-reports-financial-results-second-quarter-fiscal-year-2027-2026-09-03',
 'blacksky_fy25':'https://ir.blacksky.com/news-events/press-releases/news-details/2026/BlackSky-Reports-Fourth-Quarter-and-Full-Year-2025-Results/default.aspx',
 'blacksky_q3':'https://ir.blacksky.com/news-events/press-releases/news-details/2026/BlackSky-Reports-Third-Quarter-2026-Results/default.aspx',
 'cfets_republication':'https://news.smm.cn/news/104205419',
 'hsi_method':'https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/methodologies/IM_hscie.pdf',
 'southbound_sse':'https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20221219_5714157.shtml',
 'southbound_education':'https://www.investor.org.cn/xxzx/tjzl/tjnrgmjytx/bk/kj/jyxl_3796/202311/P020231123515882074241.pdf',
 'msci_dates':'https://www.msci.com/eqb/pressreleases/archive/ir_dates.pdf',
 'citic_sector':'https://finance.sina.com.cn/wm/2026-10-30/doc-iniwyfwa2343625.shtml',
 'xueqiu_long_read':'https://xueqiu.com/6902145880/389098980',
 'xueqiu_launch_snippet':'https://www.xueqiu.com/1697254901/415630732',
 'niuniu_roundup':'https://q.futunn.com/hk/feed/117529347752340',
 'niuniu_may_report':'https://news.futunn.com/post/73131259/ipo-news-guoxing-aerospace-a-hard-tech-company-in-the',
 'launch_mirror':'https://www.itiger.com/hans/news/2681678092',
 'treasury_snippet':'https://www.hafoo.com.hk/news/hans/notice/202610313917514348',
 'geovis_price_crosscheck':'https://cn.investing.com/equities/geovis-technology-co-ltd-historical-data',
 'spacesat_price_crosscheck':'https://cn.investing.com/equities/china-spacesat-candlestick',
 'apt_price_crosscheck':'https://www.hstong.com/quotes/10000-01045-HK',
 'stale_geovis_forecast':'https://pdf.dfcfw.com/pdf/H3_AP202512011791937421_1.pdf',
 'stale_spacesat_forecast_index':'https://basic.10jqka.com.cn/48/600118/worth.html'
}
A={'as_of':'2026-11-06 HKT, before HK market open',
 'scope':'New requested Adaspace Word study only; no workbook, database or dashboard changes.',
 'template':{'path':'/Users/lemon/Downloads/ipo analysis.docx','sha256':'ea8859ddd61c5ea574bd69c628c59d2bd737c732afdfa3b68da714587288f899'},
 'sources':S,'fx':{'date':'2026-11-05','RMB_per_HKD':0.85601,'RMB_per_USD':6.7156,'basis':'CFETS central parity, not executable spot; SMM republication','source':S['cfets_republication']},
 'price_basis':{'HK_A':'2026-11-05 closing prices, Tencent independently matched to Sina','US':'2026-11-05 12:04 ET intraday snapshot, Tencent; not the closing price','equity':'Price times vendor total shares for listed peers; full post-offer shares, including domestic shares, for issuer. Basic equity values, not fully diluted.'},
 'issuer':{
  'name':'Adaspace / 國星宇航','ticker':'06935.HK','low':24.90,'mid':29.05,'high':33.20,'post_shares':602419740,'post_H_shares':428025170,'post_domestic_shares':174394570,
  'base_new_shares':30121000,'public_initial_shares':3012100,'public_max_base_shares':4518100,'size_option_shares':4518100,'max_greenshoe_if_size_option':5195800,
  'net_proceeds_mid_HKDm':772.4,'gross_funding_private_RMBm':3550,'private_postmoney_RMBm':11553.6,
  'financial_periods':['FY2023','FY2024','FY2025','H1 2025','H1 2026'],
  'revenue':[507.541,553.473,702.703,241.322,226.110],
  'gross_profit':[71.065,210.174,143.173,24.281,88.873],
  'group_net_profit':[-139.300,-177.173,-255.945,-192.028,-150.756],
  'adjusted_group_profit':[-90.690,-69.047,-156.597,-144.154,-65.297],
  'R_and_D':[53.478,142.030,151.656,97.726,108.630],
  'CFO':[-313.474,-212.526,8.206,-78.050,61.155],
  'satellite_related_revenue':[3.221,90.971,256.674,122.144,130.622],
  'AI_computing_revenue':[0,77.656,224.801,120.045,124.690],
  'solutions_revenue':[460.328,440.947,443.778,118.086,94.183],
  'AI_computing_GM_FY25_pct':7.6,'AI_computing_GM_H126_pct':55.4,'satellite_related_GM_H126_pct':53.3,
  'delivered_satellites_2023_2024_2025_H126':[0,6,12,0],
  'pending_order_date':'2026-10-20','pending_satellites':114,'pending_contract_value_RMBm':3475,'order_value_warning':'Multi-period aggregate contract value; not one-year revenue or remaining performance obligations net of milestones already recognised.',
  'largest_customer_H126_pct':35.9,'top5_H126_pct':91.1,
  'market_rank_broad':{'rank':7,'share_pct':2.1,'universe':'About 400 Chinese private commercial-aerospace firms with satellite businesses; FY2025 revenue'},
  'market_rank_narrow':{'rank':2,'share_pct':22.6,'universe':'About 20 private full-satellite-value-chain companies; FY2025 revenue'},
  'receivables':{'FY25_gross':787.327,'FY25_allowance':156.860,'FY25_net':630.467,'June26_gross':747.240,'June26_allowance':149.441,'June26_net':597.799,'FY25_older_than_2y':284.340,'June26_older_than_2y':228.096,'June26_older_than_1y':305.285,'June26_SOE_and_SOE_led_gross':546.376,'June26_turnover_days':610.8,'turnover_formula':'Average FY25-end and June26-end GROSS trade receivables and bills / H126 revenue * 180','post_June_collections_to_Oct20':156.6},
  'treasury':{'June_cash':685.919,'June_FVPL':3406.674,'September_cash':224.0,'September_FVPL':3701.746,'September_borrowing':349.354,'September_leases':62.905,'September_undrawn_facilities':641.7,'note':'Financial investments are not all cash equivalents. Structured deposits/CDs principal-protected; wealth-management products not guaranteed. Debt includes leases for the indicative EV.'},
  'contract_liabilities_FY25':75.0,'contract_liabilities_June26':222.6,'inventory_June26':114.8,'inventory_days_FY25':21.9,'inventory_days_H126':94.3,
  'H126_share_pay':71.227,'H126_listing_costs':14.232,'H126_investment_cashflow':-3614.924,
  'guidance':'Prospectus warns FY2026 net loss will widen and operating cash flow will turn negative.',
  'forward_PE_2026':'N/M: issuer loss guidance; no numeric estimate','forward_PE_2027':'n/v: no verified current public attributable-profit forecast',
  'cornerstones':[
   {'legal_name':'JinkoSolar Investment Limited','HKDm':5,'type':'Wholly owned by NYSE-listed Jinko Holdings Limited; affiliates are existing investors','affiliates_preIPO_pct':[2.23,0.56],'lock':'Six months from and including Listing Date'},
   {'legal_name':'Kamshin Oriental (HK) Limited','HKDm':55,'type':'Electronic-components wholesale / bulk-chemical trading vehicle; wholly owned by Zhejiang Jinshuo Trading Co., Ltd.','ultimate_owners':{'Jiang Yueqing':90,'Lu Tao':10},'lock':'Six months from and including Listing Date'}
  ],
  'offer_rules':'Mechanism B: no automatic clawback, but discretionary public reallocation to about 15% of base offer requires HK$24.90 pricing. Final allocations not yet published.',
  'expected_dates':{'subscription_open':'2026-11-05','subscription_close':'2026-11-10','pricing':'2026-11-11','allotment':'2026-11-12','grey_market':'2026-11-12','listing':'2026-11-13'},
  'lock_dates':'Contractual duration only, not an exact unlock calendar: cornerstones six months; pre-IPO H shares statutory 12 months; later allotment/restriction notices needed.',
  'use_of_net_proceeds_pct':{'R_and_D':35.6,'Shenzhen_center':24.4,'acquisitions':20,'debt_repayment':10,'working_capital':10},
  'primary_locations':{'financials':'Summary / Financial Information / Accountants Report','market_rank':'Industry Overview and Business','milestone_revenue':'Business, printed pp 166–167 footnote 3','finance_lease_customer':'Business, printed pp 154–155','preIPO_valuation':'History, printed p 102','preIPO_transfer':'History, printed p 107','cornerstones':'Cornerstone Investors, printed pp 266–269','reallocation':'Structure of the Global Offering, printed pp 286–287','FY26_warnings':'Summary, printed p 17'}
 },
 'peers':[
  {'code':'1045 HK','name':'APT Satellite','currency':'HKD','price':1.825,'shares':928572500,'annual_period':'Dec 2025','annual_revenue':739.092,'annual_owner_profit':141.392,'ltm_revenue':None,'ltm_end':None,'peer_type':'Adjacent: mature GEO transponder leasing, not AI satellite manufacturing','sources':['apt_fy25']},
  {'code':'0031 HK','name':'China Aerospace Intl','currency':'HKD','price':.395,'shares':3085021882,'annual_period':'Dec 2025','annual_revenue':4031.0,'annual_owner_profit':-166.0,'ltm_revenue':None,'ltm_end':None,'peer_type':'Theme proxy: industrial components and property; not direct satellite operations','sources':['aerospace_fy25_secondary'],'financial_source_quality':'Rounded secondary earnings report; original statement not retrieved'},
  {'code':'600118 A','name':'China Spacesat','currency':'RMB','price':56.89,'shares':1182489135,'annual_period':'Dec 2025','annual_revenue':6102.944926,'annual_owner_profit':35.55668785,'latest_period_revenue':3956.18499215,'prior_period_revenue':3102.45819560,'ltm_end':'Sep 2026','peer_type':'Closest listed manufacturing overlap: satellites and applications; state-sector mix differs','sources':['spacesat_fy25','spacesat_q3']},
  {'code':'688568 A','name':'Geovis','currency':'RMB','price':31.79,'shares':808078912,'annual_period':'Dec 2025','annual_revenue':2676.73999566,'annual_owner_profit':29.40012924,'latest_period_revenue':780.5271826,'prior_period_revenue':2208.34121456,'ltm_end':'Sep 2026','peer_type':'Closest listed software overlap: digital earth / geospatial applications; current revenue contraction','sources':['geovis_fy25','geovis_q3']},
  {'code':'PL US','name':'Planet Labs','currency':'USD','price':11.23,'shares':363847989,'annual_period':'Jan 2026 (company FY2026)','annual_revenue':307.7,'annual_owner_profit':None,'annual_loss_confirmed':True,'latest_period_revenue':210.202,'prior_period_revenue':139.651,'ltm_end':'Jul 2026','peer_type':'Adjacent: earth-observation subscriptions plus satellite services and space-AI development','sources':['planet_results','planet_q2_release'],'annual_rounding':'Annual revenue rounded to USD0.1m, so LTM and P/S are approximate','forward_sales_period':'Jan 2027 (company FY2027)','forward_sales_range':[430,441],'forward_source_date':'2026-09-03'},
  {'code':'BKSY US','name':'BlackSky','currency':'USD','price':17.73,'shares':40924846,'annual_period':'Dec 2025','annual_revenue':106.575,'annual_owner_profit':-70.3,'latest_period_revenue':96.934,'prior_period_revenue':71.361,'ltm_end':'Sep 2026','peer_type':'Adjacent: real-time geospatial intelligence and satellites, with defence-customer exposure','sources':['blacksky_fy25','blacksky_q3'],'forward_sales_period':'Dec 2026','forward_sales_range':[140,150],'forward_source_date':'2026-11-05','latest_results_note':'Nov5 Q3 release included. Quarterly GAAP profit benefits from derivative valuation; not evidence of stable annual earnings.'}
 ],
 'forward_estimate_policy':{'no_current_verified_profit_forecasts':['06935','1045','0031','600118','688568','PL','BKSY'],'rejections':[{'company':'600118','input':'May 2026 AVIC/other pre-Q3 public forecasts','reason':'Forecasts predate Q3; some FY26 profit forecasts already below reported nine-month profit. Original AVIC PDF fetch returned HTML. Not current verified estimates.'},{'company':'688568','input':'Kaiyuan 1 December 2025 EPS/profit forecasts','reason':'Predates 2026 revenue collapse and nine-month loss. A mechanically low forward P/E would be misleading.'}],'no_annualisation':True,'adjusted_EBITDA_is_not_net_income':True},
 'index':{'HSCI_version':'v2.5 September 2025','minimum_listing_history':'None; must be listed by review cutoff','cap_basis':'Relevant listed H-share class; shorter-than-12-month history uses available history','new_member_rank':'94% cumulative market-cap inclusion buffer','liquidity':'Monthly median turnover >=0.05% of free-float shares; all available months for fewer than six months of trading, subject to methodology supplemental tests','regular_cutoff':'2026-12-31','illustrative_effective_date':'2027-03-08','date_status':'Derived regular-calendar window, not issuer-specific confirmed inclusion','ad_hoc':'Top-10%-by-count market-cap rank versus existing HSCI constituents; not established for this IPO','southbound_smallcap_threshold_HKDbn':5,'not_guaranteed':'HSCI selection, liquidity, exchange rules/exclusions and final inclusion notice all required. SFC high-concentration warning can exclude an HSCI candidate.'},
 'public_reading':[
  {'source':'citic_sector','date':'2026-10-30','access':'Bylined CITIC sector commentary republished by Sina; read','use':'On-orbit AI latency/downlink thesis and launch execution risks; not a stock-specific recommendation'},
  {'source':'xueqiu_long_read','date':'2026-05-15','access':'Full article read','use':'Project manufacturer versus recurring compute-platform valuation; old financial inputs replaced with final prospectus'},
  {'source':'niuniu_roundup','date':'2026-10-30','access':'Niuniu IPO account roundup read','use':'Evidence of thematic promotional framing; not institutional demand or retail consensus'},
  {'source':'xueqiu_launch_snippet','date':'2026-11-05','access':'Search excerpt; original open blocked, launch mirror reviewed','use':'Launch-story cross-check only; no unverified financials imported'},
  {'source':'treasury_snippet','date':'2026-10-31','access':'Search excerpt only; full page inaccessible','use':'Prompted primary treasury reconciliation; not cited as full article read'}
 ],
 'limitations':['No private buy-side conversations, verified institutional book or live Bloomberg terminal.','No final allocation, subscription tally or confirmed lock-expiry date yet.','US share counts are vendor basic shares; future dilution is not forecast.','APT and China Aerospace LTM revenue not independently verified, so left blank.','Audit calculations are not independent primary-source verification.','China Aerospace FY25 numbers are rounded secondary-source inputs, expressly labelled.'],
 'rejected_reference_claims':['Mechanism B fixes public tranche at 10% with no possible reallocation.','HK$75–100m retail tranche is the entire freely tradable deal.','All revenue waits for orbital delivery.','H1 AI satellite margin is an established full-cycle delivery margin.','June cash of RMB686m represents all available treasury assets.','RMB3.475bn contract value equals one year of future revenue.','HK$6bn market cap guarantees early-2027 Southbound access.','22.6% is the whole Chinese aerospace market share.','Private-round valuation and USPACE/01725 establish a liquid fair-value anchor.','80% probability of IPO premium is evidence-based.']
}
x=A['issuer'];fx=A['fx']['RMB_per_HKD']
x['ltm_revenue']=x['revenue'][2]+x['revenue'][4]-x['revenue'][3]
x['September_net_treasury']=x['treasury']['September_cash']+x['treasury']['September_FVPL']-x['treasury']['September_borrowing']-x['treasury']['September_leases']
for point in ['low','mid','high']:
 cap=x[point]*x['post_shares']/1e6;gross=x[point]*x['base_new_shares']/1e6
 x['cap_HKDm_'+point]=cap;x['cap_RMBm_'+point]=cap*fx;x['gross_HKDm_'+point]=gross
 x['ps_annual_'+point]=cap*fx/x['revenue'][2];x['ps_ltm_'+point]=cap*fx/x['ltm_revenue']
 x['price_to_order_'+point]=cap*fx/x['pending_contract_value_RMBm']
 x['tradable_base_HKDm_'+point]=gross-60
 x['tradable_base_total_pct_'+point]=(gross-60)/cap*100
 x['cornerstone_deal_pct_'+point]=60/gross*100
 x['private_postmoney_premium_pct_'+point]=(cap*fx/x['private_postmoney_RMBm']-1)*100
 x['private_premoney_premium_pct_'+point]=((cap-gross)*fx/x['private_postmoney_RMBm']-1)*100
x['EV_treasury_adjusted_mid']=x['cap_RMBm_mid']-x['September_net_treasury']-x['net_proceeds_mid_HKDm']*fx
x['EV_sales_mid']=x['EV_treasury_adjusted_mid']/x['revenue'][2]
x['revenue_scenarios']=[{'revenue_RMBm':v,'ps_low':x['cap_RMBm_low']/v,'ps_high':x['cap_RMBm_high']/v,'type':'Desk sensitivity, not forecast'} for v in [1000,1500,2000]]
x['profit_hurdle_40x']=[x['cap_RMBm_low']/40,x['cap_RMBm_high']/40]
for p in A['peers']:
 p['equity_m']=p['price']*p['shares']/1e6
 if 'latest_period_revenue' in p:p['ltm_revenue']=p['annual_revenue']+p['latest_period_revenue']-p['prior_period_revenue']
 p['annual_ps']=p['equity_m']/p['annual_revenue'];p['ltm_ps']=p['equity_m']/p['ltm_revenue'] if p['ltm_revenue'] else None
 p['annual_pe']=p['equity_m']/p['annual_owner_profit'] if p['annual_owner_profit'] and p['annual_owner_profit']>0 else None
 p['FY26E_PE']=None;p['FY27E_PE']=None
 if 'forward_sales_range' in p:p['forward_ps_mid']=p['equity_m']/(sum(p['forward_sales_range'])/2)
(H/'source_and_valuation_audit.json').write_text(json.dumps(A,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'issuer_ps':[x['ps_annual_low'],x['ps_annual_high']],'peers':[(p['code'],p['annual_ps'],p['ltm_ps']) for p in A['peers']]},indent=2))
