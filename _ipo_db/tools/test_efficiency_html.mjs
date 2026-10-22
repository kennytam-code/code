/** Exercise and render the shipped SVG function; this is not a browser test. */
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import sharp from 'sharp';
const root=new URL('../',import.meta.url),out=new URL('out/efficiency_20261022/',root);
const html=fs.readFileSync(new URL('out/hk_ipo_dashboard.html',root),'utf8');
const payload=h=>JSON.parse(gunzipSync(Buffer.from(h.match(/<script id="ipo-payload" type="application\/octet-stream">([^<]+)<\/script>/)[1],'base64')));
for(const script of html.matchAll(/<script(?: [^>]*)?>([\s\S]*?)<\/script>/g)){if(script[1].trim()&&!script[0].includes('ipo-payload'))new vm.Script(script[1]);}
const data=payload(html),before=payload(fs.readFileSync(new URL('baseline.html',out),'utf8'));
const digest=x=>createHash('sha256').update(JSON.stringify(x)).digest('hex');
assert.equal(digest(data),digest(before),'The entire HTML dataset must be unchanged');
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
for(const name of ['niceTicks','scaleFor','pathline','addXhair','fullAHPath','drawAHMarket'])vm.runInContext(source(name),ctx);
let count=0;
for(const deal of data.market_deals.filter(x=>x.a_share_code&&data.ahpaths[x.code])){
 const P=ctx.fullAHPath(deal),trend=data.ah_reference.pairs[deal.code]?.trend_rows||[],span=Math.max(1,P.days.at(-1)||1),lead=P.offer_date?Math.min(0,Math.round((Date.parse(P.offer_date)-Date.parse(P.ipo))/86400000)):0;
 for(const width of [1080,480]){
  const svg=new Node('svg',{xmlns:'http://www.w3.org/2000/svg',viewBox:`0 0 ${width} 340`});svg.W=width;
  ctx.drawAHMarket(svg,width,340,{l:58,r:58,t:38,b:40},P,P,trend,span,lead);
  assert(!/NaN|Infinity|undefined/.test(svg.outerHTML),deal.code);
  const paths=svg.children.filter(n=>n.tag==='path');assert.equal(paths.length,3);
  assert.equal(paths[0].attrs.stroke,'#B17816');assert.equal(paths[0].attrs['stroke-dasharray'],'7 4');assert.equal(paths[2].attrs.stroke,'#1D4E89');
  const marketDays=trend.map(x=>Math.round((Date.parse(x[0])-Date.parse(P.ipo))/86400000));
  const series=[{days:marketDays,ys:trend.map(x=>100*(x[2]/trend[0][2]-1))},{days:marketDays,ys:trend.map(x=>100*(x[1]/trend[0][1]-1))},{days:P.days,ys:P.prem}];
  for(let k=0;k<series.length;k++){
   let segments=0,started=false;const s=series[k];
   s.days.forEach((d,i)=>{if(!Number.isFinite(s.ys[i])){started=false;return;}if(i&&d-s.days[i-1]>10)started=false;if(!started)segments++;started=true;});
   assert.equal((paths[k].attrs.d.match(/M/g)||[]).length,segments,deal.code+' gap preservation');
   assert.equal((paths[k].attrs.d.match(/[ML]/g)||[]).length,s.ys.filter(Number.isFinite).length,deal.code+' full observation coverage');
  }
  svg.handlers.mousemove({clientX:width*.65});assert(tooltip.includes('<b>'));
  if(['3986','3223','9976','2636'].includes(deal.code)&&width===1080||deal.code==='3986'&&width===480){
   const legend=`<g font-size="12"><path d="M20 70h26" stroke="#1D4E89" stroke-width="3"/><text x="52" y="74">Premium (left)</text><path d="M210 70h26" stroke="#16857A" stroke-width="2"/><text x="242" y="74">A-share return (right)</text><path d="M460 70h26" stroke="#B17816" stroke-width="2" stroke-dasharray="7 4"/><text x="492" y="74">CSI 300 return</text></g>`;
   const rendered=svg.outerHTML.replace('<svg ',`<svg x="10" y="95" width="${width}" height="340" `);
   const poster=`<svg xmlns="http://www.w3.org/2000/svg" width="${width+20}" height="450"><style>text{font-family:Arial,sans-serif}</style><rect width="100%" height="100%" fill="white"/><text x="20" y="30" fill="#253341" font-size="16" font-weight="bold">${esc(deal.name)} (${deal.code})</text><text x="20" y="50" fill="#626E7B" font-size="12">A/H premium and mainland market</text>${width>600?legend:''}${rendered}</svg>`;
   await sharp(Buffer.from(poster)).png().toFile(new URL(`html_${deal.code}_${width}.png`,out).pathname);
  }
  count++;
 }
}
// Test each user-selectable main chart with real observations.
let modes=0;
for(const deal of data.market_deals.filter(x=>x.a_share_code&&data.ahpaths[x.code])){
 const P=ctx.fullAHPath(deal),trend=data.ah_reference.pairs[deal.code]?.trend_rows||[],span=Math.max(1,P.days.at(-1)||1);
 for(const mode of ['premium','market'])for(const width of [1080,480]){
  const svg=new Node('svg',{xmlns:'http://www.w3.org/2000/svg',viewBox:`0 0 ${width} 340`});svg.W=width;
  ctx.drawAHMarket(svg,width,340,{l:58,r:58,t:38,b:40},P,P,trend,span,0,mode);
  const paths=svg.children.filter(n=>n.tag==='path');assert.equal(paths.length,mode==='premium'?1:2);
  assert(!/NaN|Infinity|undefined/.test(svg.outerHTML),deal.code+' '+mode);
  assert.equal((paths.at(-1).attrs.d.match(/[ML]/g)||[]).length,P.prem.filter(Number.isFinite).length);
  if(mode==='market')assert.equal((paths[0].attrs.d.match(/[ML]/g)||[]).length,trend.length);
  svg.handlers.mousemove({clientX:width*.7});assert(!tooltip.includes('A-share return'));
  if(['3986','3223','9976'].includes(deal.code)&&width===1080||deal.code==='3986'&&width===480){
   const chart=svg.outerHTML.replace('<svg ',`<svg x="10" y="130" width="${width}" height="340" `);
   const legend=`<path d="M20 108h24" stroke="#1D4E89" stroke-width="3"/><text x="52" y="112" font-size="12">Premium</text>`+(mode==='market'?`<path d="M180 108h24" stroke="#B17816" stroke-width="2" stroke-dasharray="7 4"/><text x="212" y="112" font-size="12">CSI 300 return</text>`:'');
   const poster=`<svg xmlns="http://www.w3.org/2000/svg" width="${width+20}" height="500"><style>text{font-family:Arial,sans-serif;fill:#263442}</style><rect width="100%" height="100%" fill="white"/><text x="20" y="28" font-size="17" font-weight="bold">${esc(deal.name)} · ${deal.code} HK</text><text x="20" y="55" font-size="12" fill="#626E7B">${mode==='premium'?'Premium':'Premium + CSI 300'} · listing to snapshot</text>${legend}${chart}</svg>`;
   await sharp(Buffer.from(poster)).png().toFile(new URL(`desk_${deal.code}_${mode}_${width}.png`,out).pathname);
  }
  modes++;
 }
}
// Execute renderAH itself: precisely one chart for every selectable analysis.
Node.prototype.querySelector=function(sel){if(!this.queries)this.queries={};return this.queries[sel]??=new Node('div');};
Node.prototype.insertBefore=function(n,b){this.children=this.children.filter(x=>x!==n);this.children.unshift(n);};
const controls=new Map(),$=sel=>{if(!controls.has(sel))controls.set(sel,new Node('div'));return controls.get(sel);};
Object.assign(ctx,{$,document:{createElement:tag=>new Node(tag)},fitW:()=>1080,fmt:{pct:v=>v.toFixed(1)+'%'},safeText:esc,LEAD:-8});
for(const name of ['ahPanel','pathYAxis','aOpen0HKD','hOpen0','openStart'])vm.runInContext(source(name),ctx);
vm.runInContext(html.slice(html.indexOf('let labAHFocus=null,'),html.indexOf('\nredrawAHTab();',html.indexOf('let labAHFocus=null,'))),ctx);
for(const code of ['3986','3223','9976','2636'])for(const mode of ['premium','market','around','hkd','open'])for(const full of [true,false]){
 controls.clear();const d=data.market_deals.find(d=>d.code===code);
 ctx.renderAH([d],{host:'#probe',note:'#note',deskMode:mode,full});
 const g=$('#probe').children[0].querySelector('.ahgrid');
 assert.equal(g.children.length,1,code+' '+mode+' must show exactly one analysis');
 const card=g.children[0];assert(card.innerHTML.includes('<h4>'));
 if(mode==='market')assert(!card.innerHTML.includes('A-share return (right)'));
 if(mode==='premium')assert(card.innerHTML.includes('A/H premium'));
}
// Review the real comparison renderer with six distinctly identified lines.
const desk=fs.readFileSync(new URL('assets/desk_monitors.js',root),'utf8');
const cut=desk.indexOf('const ahComparisons=');
const cctx=vm.createContext({Number,Date,Math,Map,Set,AHST:data.ahstudy,
 document:{createElement:tag=>new Node(tag)},el:(tag,attrs,parent)=>parent.appendChild(new Node(tag,attrs)),
 fitW:box=>box.W,niceTicks:ctx.niceTicks,lin:(a,b,c,d)=>v=>c+(v-a)/(b-a||1)*(d-c),
 css:()=> '#9AA6B4',showTT:()=>{},hideTT:()=>{},safeText:esc});
vm.runInContext(desk.slice(0,cut),cctx);
for(const name of ['validAHPoint','adjustedAHPoint','ahSeries']){
 const start=desk.indexOf('function '+name+'(');let end=desk.indexOf('{',start),depth=1;for(end++;depth;end++){if(desk[end]==='{')depth++;if(desk[end]==='}')depth--;}
 vm.runInContext(desk.slice(start,end),cctx);
}
const palette=['#1D4E89','#16857A','#B17816','#6F5598','#B2505D','#486873'];
const series=data.market_deals.filter(d=>d.a_share_code&&d.sector==='Technology').sort((a,b)=>a.code.localeCompare(b.code)).map(d=>cctx.ahSeries(d,'2026-07-01',data.ah_asof)).filter(s=>s.points.some(p=>Number.isFinite(p[1]))).slice(0,6).map((s,i)=>({...s,color:palette[i],dash:i>=3?'7 3':undefined}));
const box=new Node('div');box.W=1080;cctx.deskLines(box,series,{label:'A/H premium comparison'});
const comparison=box.children.find(n=>n.tag==='svg');
assert.equal(comparison.children.filter(n=>n.tag==='path').length,6);
const legend=series.map((s,i)=>{const x=20+(i%2)*540,y=430+Math.floor(i/2)*25;return `<path d="M${x} ${y-4}h26" stroke="${s.color}" stroke-width="2.5"${s.dash?' stroke-dasharray="7 3"':''}/><text x="${x+35}" y="${y}" font-size="12">${esc(s.name)}</text>`;}).join('');
const chart=comparison.outerHTML.replace('<svg ','<svg x="10" y="65" width="1080" height="340" ');
const poster=`<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="510"><style>text{font-family:Arial,sans-serif;fill:#344252}.axlabel{font-size:11px;fill:#626E7B}.gridline{stroke:#E5E9EE}</style><rect width="100%" height="100%" fill="white"/><text x="20" y="30" font-size="17" font-weight="bold">A/H premium · Technology</text><text x="20" y="50" font-size="12">3 months · six selected pairs</text>${chart}${legend}</svg>`;
await sharp(Buffer.from(poster)).png().toFile(new URL('html_comparison.png',out).pathname);
// Legend focus and endpoint labels use the actual renderer, including narrow views.
for(const width of [1080,480]){
 const box=new Node('div');box.W=width;cctx.deskLines(box,series,{label:'Selected premiums'});
 const svg=box.children.find(n=>n.tag==='svg'),legend=box.children.find(n=>n.tag==='div');
 const lines=svg.children.filter(n=>n.tag==='path'),keys=legend.children;
 assert.equal(keys.length,6);assert.equal(svg.children.filter(n=>n.attrs['data-end-label']).length,6);
 keys[2].handlers.mouseenter();assert.equal(lines[2].attrs.opacity,1);assert.equal(lines[0].attrs.opacity,.12);
 keys[2].handlers.click();keys[2].handlers.mouseleave();assert.equal(keys[2].attrs['aria-pressed'],'true');assert.equal(lines[0].attrs.opacity,.12);
 keys[2].handlers.click();assert(lines.every(n=>n.attrs.opacity===1));
 const dateLabels=svg.children.filter(n=>n.tag==='text'&&/^2026-/.test(n.textContent));assert.equal(dateLabels.length,width<600?3:5);
 const ys=svg.children.filter(n=>n.attrs['data-end-label']).map(n=>Number(n.attrs.y)).sort((a,b)=>a-b);assert(ys.every((y,i)=>!i||y-ys[i-1]>=24));
}
// Default Screener uses a single full-width analysis with a metric selector.
controls.clear();ctx.renderAH([data.market_deals.find(d=>d.code==='3986')]);
const host=$('#lab-ah');assert(host.children.some(n=>n.innerHTML?.includes('lab-ah-analysis')));
const wrap=host.children.find(n=>n.className?.includes('ah-desk-detail'));assert.equal(wrap.querySelector('.ahgrid').children.length,1);
assert(count>=142);
fs.writeFileSync(new URL('html_checks.json',out),JSON.stringify({passed:true,render_cases:count+ modes,detail_control_cases:40,html_code_search_cases:searchCases,entire_payload_unchanged:true,all_observations_and_gaps_preserved:true,actual_svg_function:true,browser:false},null,2)+'\n');
console.log(`PASS ${count+modes} actual SVG render cases and 40 detail control cases: every A/H pair at desktop/mobile widths, complete points, real gaps, consistent lines, axes, tooltip; entire embedded dataset unchanged.`);
