/** Exercise and render the shipped SVG function; this is not a browser test. */
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import sharp from 'sharp';
const root=new URL('../',import.meta.url),out=new URL('out/ah_review_20261115/',root);
const html=fs.readFileSync(new URL('out/hk_ipo_dashboard.html',root),'utf8');
const payload=h=>JSON.parse(gunzipSync(Buffer.from(h.match(/<script id="ipo-payload" type="application\/octet-stream">([^<]+)<\/script>/)[1],'base64')));
for(const script of html.matchAll(/<script(?: [^>]*)?>([\s\S]*?)<\/script>/g)){if(script[1].trim()&&!script[0].includes('ipo-payload'))new vm.Script(script[1]);}
const data=payload(html);
assert.equal(data.deals.length,527);assert.equal(Object.keys(data.ahstudy).length,75);
assert(data.deals.some(d=>d.code==='2384'));
fs.mkdirSync(out,{recursive:true});
const digest=x=>createHash('sha256').update(JSON.stringify(x)).digest('hex');
// Canonical numeric parity is checked by test_presentation_package.py; this run tests refreshed observations.
function source(name){const start=html.indexOf('function '+name+'(');assert(start>=0);let i=html.indexOf('{',start),depth=1;for(i++;depth;i++){if(html[i]==='{')depth++;if(html[i]==='}')depth--;}return html.slice(start,i);}
const esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
class Node{
 constructor(tag,attrs={}){this.tag=tag;this.attrs=attrs;this.children=[];this.dataset={};this.handlers={};this.textContent='';}
 appendChild(n){this.children.push(n);return n;}
 setAttribute(k,v){this.attrs[k]=v;}
 addEventListener(k,f){this.handlers[k]=f;}
 getBoundingClientRect(){return{left:0,width:this.W};}
 get outerHTML(){return `<${this.tag}${Object.entries(this.attrs).map(([k,v])=>` ${k}="${esc(v)}"`).join('')}>${esc(this.textContent)}${this.children.map(n=>n.outerHTML).join('')}</${this.tag}>`;}
}
let tooltip='';
const ctx=vm.createContext({Number,Date,Math,Map,Set,DATA:data,AHST:data.ahstudy,el:(tag,attrs,parent)=>parent.appendChild(new Node(tag,attrs)),showTT:x=>tooltip=x,hideTT:()=>{}});
const search=vm.createContext({deals:data.deals,Number,String});
for(const name of ['normalCode','matchesDealSearch','findDeal'])vm.runInContext(source(name),search);
let searchCases=0;
for(const d of data.deals)for(const key of [d.code,String(Number(d.code)),String(Number(d.code)).padStart(5,'0'),`${Number(d.code)} HK Equity`]){assert.equal(search.findDeal(key).code,d.code);searchCases++;}
assert.equal(search.findDeal('999999'),undefined);assert.equal(search.findDeal(''),null);
vm.runInContext("const AHCHART={premium:'#1D4E89',a:'#16857A',csi:'#B17816'}",ctx);
for(const name of ['niceTicks','scaleFor','pathline','pathYAxis','addXhair','fullAHPath','drawAHMarket','ahDetailData','drawAHDetailPanel'])vm.runInContext(source(name),ctx);
let rendered=0,pricePoints=0;
for(const d of data.market_deals.filter(d=>d.a_share_code)){
 const full=ctx.fullAHPath(d),short=data.ahpaths[d.code];
 assert.equal(full.dates.at(-1),'2026-11-13');assert.equal(data.ahstudy[d.code].latest_date,'2026-11-13');
 // Independently built Python path and full JS path must agree through the
 // entire overlap, including all corporate-action factors and raw ratios.
 for(const field of ['h','a_cny','a_hkd','prem','h_perf','a_perf_hkd'])for(let i=0;i<short[field].length;i++){
  const a=short[field][i],b=full[field][i];
  if(a==null)assert.equal(b,null);else assert(Math.abs(a-b)<1e-5*Math.max(1,Math.abs(a)),d.code+' '+field+' '+i);
 }
 for(const mode of ['hkd','performance','around'])for(const horizon of ['Max','1M','3M','6M','1Y','3Y','First3M']){
  const view=ctx.ahDetailData(d,horizon,mode);
  assert(view.from<=view.to);assert(view.to<='2026-11-13');
  for(const width of [1080,480])for(const [series,unit] of [[view.prices,view.unit],[view.prem,'%']]){
   const svg=new Node('svg',{xmlns:'http://www.w3.org/2000/svg',viewBox:`0 0 ${width} 270`});svg.W=width;
   ctx.drawAHDetailPanel(svg,width,270,{l:58,r:22,t:22,b:35},series,view,unit);
   assert(!/NaN|Infinity|undefined/.test(svg.outerHTML),d.code+' '+mode+' '+horizon);
   const paths=svg.children.filter(x=>x.tag==='path');assert.equal(paths.length,series.length);
   for(let i=0;i<series.length;i++){
    const s=series[i];assert.equal((paths[i].attrs.d.match(/[ML]/g)||[]).length,s.ys.filter(Number.isFinite).length);
    let segments=0,started=false;s.ys.forEach((v,j)=>{if(!Number.isFinite(v)){started=false;return;}if(j&&s.days[j]-s.days[j-1]>10)started=false;if(!started)segments++;started=true;});
    assert.equal((paths[i].attrs.d.match(/M/g)||[]).length,segments,'Missing-data gaps preserved');
    pricePoints+=s.ys.filter(Number.isFinite).length;
   }
   if(series.some(s=>s.ys.some(Number.isFinite))){svg.handlers.mousemove({clientX:width*.7});assert(tooltip.includes('<b>'));}
   rendered++;
  }
 }
}
const controls=new Map(),$=sel=>{if(!controls.has(sel))controls.set(sel,new Node('div'));return controls.get(sel);};
Object.assign(ctx,{$,document:{createElement:tag=>new Node(tag)},fitW:()=>1080});
vm.runInContext(source('renderAHDetail'),ctx);
for(const d of data.market_deals.filter(d=>d.a_share_code))for(const mode of ['hkd','performance','around']){
 controls.clear();ctx.renderAHDetail(d,'Max',mode);
 const cards=$('#ah-history').children;assert.equal(cards.length,2);
 assert(cards[0].innerHTML.includes(mode==='hkd'?'A / H prices':mode==='around'?'Price action around H listing':'A / H price action'));
 assert(cards[1].innerHTML.includes('A/H premium'));
 const svgs=cards.map(x=>x.children.find(n=>n.tag==='svg'));
 assert(svgs.every(Boolean));assert.equal(svgs[0].dataset.first,svgs[1].dataset.first);assert.equal(svgs[0].dataset.last,svgs[1].dataset.last);
}
assert(html.includes('Prices through 2026-10-02 · live Bloomberg mode in Excel'),'Unrelated peer date incorrectly relabelled');
const result={pairs:75,rendered,observations:pricePoints,two_panel_controls:225,corporate_action_js_python_parity:true,live_bloomberg_tested:false};
fs.writeFileSync(new URL('detail_checks.json',out),JSON.stringify(result,null,2));
console.log('PASS',JSON.stringify(result));
