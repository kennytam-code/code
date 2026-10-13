"""Product peer selection, reusing dated histories without extra price downloads."""
import json,runpy,requests
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
p=ROOT/'data/peer_pairs.json';doc=json.loads(p.read_text())
removed={'0700/9988':'Gaming versus commerce','3690/1024':'Local services versus short video','1810/2018':'Handsets versus components','2319/1117':'Dairy products versus raw milk','2601/1339':'Life versus property/casualty insurance mix','2269/2359':'Biologics versus broader small-molecule CXO','0069/0053':'Hotel operator versus diversified investment group'}
new=[
 ('2382','1478','Camera modules','Both manufacture handset camera modules.','Lens exposure and customer mix differ.',['https://www.sunnyoptical.com/en/pro/009003/index.html','https://www.qtechsmartvision.com/productlist279.html']),
 ('1211','0175','Passenger vehicles','Both develop and sell passenger cars.','EV mix, vertical integration and exports differ.',['https://www.bydglobal.com/en/car.html','https://www.geelyauto.com.hk/company-brief/']),
 ('1109','0688','China developers','Both develop and sell residential property in China.','Rental income, cities and leverage differ.',['https://en.crland.com.hk/zhidiPro/index.html','https://www1.hkexnews.hk/listedco/listconews/sehk/2024/0426/2024042602364.pdf']),
 ('0291','0168','Brewers','Both manufacture and distribute beer in China.','Brand positioning and regional mix differ.',['https://www.crbeer.com.hk/en/index/index.html','https://www.tsingtao.com.cn/EN/about/corpInfo.html']),
 ('0002','0006','Electric utilities','Both own electricity-generation and utility assets.','Operating model, regulated share and geography differ.',['https://www.clpgroup.com/en/about/our-business/assets-and-services.html','https://www.powerassets.com/documents/en/InvestorRelations/Documents/Annual%20Report%202022/e101.pdf']),
 ('0902','0836','China power generators','Both generate and sell electricity in China.','Coal exposure and renewable capacity differ.',['https://www.hpi.com.cn/sites/english/Pages/companyprofile.aspx','https://www.crpower.com.hk/power_en/home/CorporateProfile/index.html']),
 ('3692','1801','Innovative pharmaceuticals','Both develop and commercialise innovative medicines.','Drug modalities, indications and pipeline stages differ.',['https://www.hspharm.com/','https://en.innoventbio.com/InvestorsAndMedia/PressReleaseDetail?key=549'])
]
catalog={s['code']:s for s in json.loads((ROOT/'data/hk_stock_universe.json').read_text())['stocks']}
doc['pairs']=[x for x in doc['pairs'] if x['id'] not in removed]
ids={x['id'] for x in doc['pairs']}
for a,b,segment,reason,difference,sources in new:
 if a+'/'+b not in ids:doc['pairs'].append(dict(id=a+'/'+b,code_a=a,code_b=b,name_a=catalog[a]['name'],name_b=catalog[b]['name'],segment=segment,watch=difference,peer_reason=reason,sources=sources))
for pair in doc['pairs']:
 pair['label']=pair['name_a']+' ('+pair['code_a']+') / '+pair['name_b']+' ('+pair['code_b']+')'
 pair.setdefault('peer_reason','Both compete in '+pair['segment'].lower()+'.')
 pair['selection_basis']='Product overlap; selection is an analytical judgement, not issuer endorsement.'
doc['selection_review']={'date':'2026-10-13','excluded':removed,'basis':'Product overlap, with material mix differences visible for each pair.'}
p.write_text(json.dumps(doc,ensure_ascii=False,indent=1))
for code in sorted({x[k] for x in doc['pairs'] for k in ['code_a','code_b']}):
 cache=ROOT/'data/peer_price_cache'/f'{code}.json'
 try:
  old=json.loads(cache.read_text())
  if old.get('rows'):continue
 except (ValueError,OSError):pass
 start=int(datetime(2021,10,1,tzinfo=timezone.utc).timestamp());end=int(datetime.fromisoformat(doc['asof']).replace(tzinfo=timezone.utc).timestamp())+86400
 url=f'https://query1.finance.yahoo.com/v8/finance/chart/{code}.HK?period1={start}&period2={end}&interval=1d'
 reply=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=30);reply.raise_for_status();stock=reply.json()['chart']['result'][0];quote=stock['indicators']['quote'][0]
 rows=[[datetime.fromtimestamp(ts,timezone.utc).date().isoformat(),quote['open'][i],quote['close'][i],quote['high'][i],quote['low'][i],quote['volume'][i]] for i,ts in enumerate(stock['timestamp']) if quote['close'][i] is not None and quote['volume'][i]]
 assert rows,code+' has no saved observations'
 cache.write_text(json.dumps({'src':url,'rows':rows},separators=(',',':')));print('Saved peer history',code,len(rows),flush=True)
runpy.run_path(str(ROOT/'tools/prepare_desk_chart_data.py'),run_name='__main__')
