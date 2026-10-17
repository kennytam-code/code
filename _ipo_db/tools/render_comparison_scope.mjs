/** Render the actual deskLines SVG with a lightweight DOM adapter, not a browser. */
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import sharp from 'sharp';
import {gunzipSync} from 'node:zlib';
const root=new URL('../',import.meta.url),html=fs.readFileSync(new URL('out/hk_ipo_dashboard.html',root),'utf8'),code=fs.readFileSync(new URL('assets/desk_monitors.js',root),'utf8');
const data=JSON.parse(gunzipSync(Buffer.from(html.match(/<script id="ipo-payload" type="application\/octet-stream">([^<]+)<\/script>/)[1],'base64')));
function source(text,name){const start=text.indexOf('function '+name+'(');assert(start>=0);let i=text.indexOf('{',start),depth=1;for(i++;depth;i++){if(text[i]==='{')depth++;if(text[i]==='}')depth--;}return text.slice(start,i);}
const esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
class Node{
 constructor(tag,attrs={}){this.tag=tag;this.attrs=attrs;this.children=[];this.handlers={};this.textContent='';this.innerHTML='';this.clientWidth=1060;}
 appendChild(child){this.children.push(child);return child;}
 addEventListener(name,fn){this.handlers[name]=fn;}
 setAttribute(name,v){this.attrs[name]=v;}
 getBoundingClientRect(){return{left:0,width:this.clientWidth};}
 get outerHTML(){return `<${this.tag}${Object.entries(this.attrs).map(([k,v])=>` ${k}="${esc(v)}"`).join('')}>${esc(this.textContent)}${this.children.map(n=>n.outerHTML).join('')}</${this.tag}>`;}
}
let tooltip='';const ctx=vm.createContext({Number,Date,Math,Map,Set,AHST:data.ahstudy,
 document:{createElement:tag=>new Node(tag)},el:(tag,attrs,parent)=>parent.appendChild(new Node(tag,attrs)),
 css:name=>({'--mid':'#8a929d'}[name]||'#777'),showTT:html=>{tooltip=html;},hideTT:()=>{},safeText:esc,
 lin:(d0,d1,r0,r1)=>v=>r0+(v-d0)/(d1-d0||1)*(r1-r0)});
vm.runInContext(code.slice(0,code.indexOf('const ahComparisons=')),ctx);
for(const name of ['fitW','niceTicks'])vm.runInContext(source(html,name),ctx);
for(const name of ['validAHPoint','adjustedAHPoint','ahSeries','lockSeries','averageSeries','selectedAverages'])vm.runInContext(source(code,name),ctx);
const ah=data.market_deals.filter(d=>d.a_share_code&&d.sector==='Technology').sort((a,b)=>a.code.localeCompare(b.code)).map(d=>ctx.ahSeries(d,'2026-07-01',data.ah_asof)).filter(s=>s.points.some(p=>Number.isFinite(p[1])));
const locks=data.lockups.events.filter(e=>e.sector==='Technology'&&e.last_day_locked&&e.window.anchor_close>0&&e.window.path.some(p=>Number.isFinite(p[2]))).sort((a,b)=>b.last_day_locked.localeCompare(a.last_day_locked)).slice(0,6).map(e=>ctx.lockSeries(e));
let cases=0;
async function render(name,title,series,offset,width=1100,subtitle=''){
 const box=new Node('div');box.clientWidth=width-40;ctx.deskLines(box,series,{offset,label:title});
 const svg=box.children.find(c=>c.tag==='svg');assert(svg);const paths=svg.children.filter(c=>c.tag==='path');assert.equal(paths.length,series.length);assert(!/NaN|Infinity|undefined/.test(svg.outerHTML));
 for(let i=0;i<paths.length;i++){
  let expected=0,started=false,last=null;
  for(const p of series[i].points){const x=offset?p[0]:Date.parse(p[0]+'T00:00:00Z');if(!Number.isFinite(p[1])){started=false;last=x;continue;}if(!offset&&last!=null&&x-last>10*86400000)started=false;if(!started)expected++;started=true;last=x;}
  assert.equal((paths[i].attrs.d.match(/M/g)||[]).length,expected,'missing gap or invented continuity');
 }
 const cols=width<600?1:2,legendRows=Math.ceil(series.length/cols),height=470+legendRows*24;
 const chart=svg.outerHTML.replace('<svg ',`<svg x="20" y="100" width="${width-40}" height="${width<600?340*(width-40)/1060:340}" `);
 if(series.every(s=>s.points.length===1))assert.equal(svg.children.filter(c=>c.attrs['data-isolated-point']==='true').length,series.length);
 const colors=['#315b7d','#9b4a47','#55745d','#927d54','#6b617d','#397a80'];
 const legend=series.map((s,i)=>{const x=25+(i%cols)*(width-40)/cols,y=width<600?245+Math.floor(i/cols)*26:460+Math.floor(i/cols)*24;return `<rect x="${x}" y="${y-8}" width="13" height="3" fill="${s.color||colors[i%6]}"/><text x="${x+20}" y="${y}" font-size="11">${esc(s.name)}</text>`;}).join('');
 const poster=`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><style>text{font-family:Arial,sans-serif;fill:#30343b} .gridline{stroke:#e2e5e8;stroke-dasharray:2 3} .axlabel{font-size:11px;fill:#67707b}</style><rect width="100%" height="100%" fill="white"/><rect x="20" y="24" width="3" height="24" fill="#CB2125"/><text x="34" y="43" font-size="19" font-weight="bold">${esc(title)}</text><text x="20" y="76" font-size="12" fill="#67707b">${esc(subtitle)}</text>${chart}${legend}</svg>`;
 const out=new URL('out/chart_scope_20261017/'+name,root);fs.writeFileSync(new URL(name+'.svg',new URL('out/chart_scope_20261017/',root)),poster);await sharp(Buffer.from(poster)).png().toFile(out.pathname+'.png');
 svg.clientWidth=width-40;svg.handlers.mousemove({clientX:(width-40)/2,clientY:180});for(const s of series)assert(tooltip.includes(esc(s.name)));cases++;
}
await render('ah_technology','A/H premium · Technology',ah.slice(0,6),false,1100,`Stocks    |    3 months    |    Lines 1–6 of ${ah.length}`);
await render('lock_stocks','Lock-up returns · Technology',locks,true,1100,'Stocks    |    Expiry close = 0%    |    30 trading sessions before / after');
const avg=ctx.selectedAverages(locks,false,true).overall;await render('lock_average','Lock-up returns · selected average',[avg],true,1100,'Selected average    |    Equal weight across selected stocks');
const fixture=[{name:'Gapped series',points:[['2026-01-01',10],['2026-01-02',null],['2026-01-03',0],['2026-02-01',-5]]},{name:'No interpolation',points:[['2026-01-01',20],['2026-01-02',null],['2026-02-01',0]]}];
await render('gap_probe','Observed points and genuine gaps',fixture,false,1100,'Gap preservation regression');
await render('single_point','A/H · one observed session',[{name:'One observation',points:[['2026-10-15',25]]}],false,1100,'An observed point is shown without inventing a line');
console.log(`PASS ${cases} actual SVG renders: clean numeric geometry, one path per line, full legends/tooltips, expiry reference and genuine gaps preserved; no browser launched.`);
