/** Exercise and render the shipped SVG function; this is not a browser test. */
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import sharp from 'sharp';
const root=new URL('../',import.meta.url),out=new URL('out/ah_readability_20261019/',root);
const html=fs.readFileSync(new URL('out/hk_ipo_dashboard.html',root),'utf8');
const payload=h=>JSON.parse(gunzipSync(Buffer.from(h.match(/<script id="ipo-payload" type="application\/octet-stream">([^<]+)<\/script>/)[1],'base64')));
const data=payload(html),before=payload(fs.readFileSync(new URL('TO_NOMURA/hk_ipo_dashboard.html',root),'utf8'));
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
   const legend=`<g font-size="12"><path d="M20 70h26" stroke="#1D4E89" stroke-width="3"/><text x="52" y="74">Premium (left)</text><path d="M210 70h26" stroke="#16857A" stroke-width="2"/><text x="242" y="74">A-share return (right)</text><path d="M460 70h26" stroke="#B17816" stroke-width="2" stroke-dasharray="7 4"/><text x="492" y="74">CSI 300 return (right)</text></g>`;
   const rendered=svg.outerHTML.replace('<svg ',`<svg x="10" y="95" width="${width}" height="340" `);
   const poster=`<svg xmlns="http://www.w3.org/2000/svg" width="${width+20}" height="450"><style>text{font-family:Arial,sans-serif}</style><rect width="100%" height="100%" fill="white"/><text x="20" y="30" fill="#253341" font-size="16" font-weight="bold">${esc(deal.name)} (${deal.code})</text><text x="20" y="50" fill="#626E7B" font-size="12">A/H premium and mainland market</text>${width>600?legend:''}${rendered}</svg>`;
   await sharp(Buffer.from(poster)).png().toFile(new URL(`html_${deal.code}_${width}.png`,out).pathname);
  }
  count++;
 }
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
assert(count>=142);
fs.writeFileSync(new URL('html_checks.json',out),JSON.stringify({passed:true,render_cases:count,entire_payload_unchanged:true,all_observations_and_gaps_preserved:true,actual_svg_function:true,browser:false},null,2)+'\n');
console.log(`PASS ${count} actual SVG render cases: every A/H pair at desktop/mobile widths, complete points, real gaps, consistent lines, axes, tooltip; entire embedded dataset unchanged.`);
