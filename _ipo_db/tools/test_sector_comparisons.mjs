import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {gunzipSync} from 'node:zlib';
const root=new URL('../',import.meta.url),html=fs.readFileSync(new URL('out/hk_ipo_dashboard.html',root),'utf8');
const payload=html.match(/<script id="ipo-payload" type="application\/octet-stream">([A-Za-z0-9+/=]+)<\/script>/)[1];
const data=JSON.parse(gunzipSync(Buffer.from(payload,'base64'))),code=fs.readFileSync(new URL('assets/desk_monitors.js',root),'utf8');
function source(name){const start=code.indexOf('function '+name+'(');assert(start>=0);let i=code.indexOf('{',start),depth=1;for(i++;depth;i++){if(code[i]==='{')depth++;if(code[i]==='}')depth--;}return code.slice(start,i);}
const context=vm.createContext({AHST:data.ahstudy,Number,Map});
for(const name of ['validAHPoint','adjustedAHPoint','averageSeries','ahSeries'])vm.runInContext(source(name),context);
const avg=(series,offset=false)=>context.averageSeries(series,'Test','#333',offset);
const fixture=avg([{points:[['2026-01-01',0],['2026-01-02',null],['2026-01-03',-10]]},{points:[['2026-01-01',20],['2026-01-02',null],['2026-01-03',0]]}]);
assert.deepEqual(JSON.parse(JSON.stringify(fixture.points)),[['2026-01-01',10,2],['2026-01-02',null,0],['2026-01-03',-5,2]]);
const deals=(data.market_deals||data.deals).filter(d=>d.a_share_code).map(d=>({...d,classReview:/share-scale/.test(data.ahstudy[d.code]?.exclusion||'')&&!data.ahstudy[d.code]?.entitlement_review}));
let checked=0;
for(const sector of new Set(deals.map(d=>d.sector))){
 const series=deals.filter(d=>d.sector===sector).map(d=>context.ahSeries(d,'2025-10-02','2026-10-02'));
 for(const s of series){assert.equal(new Set(s.points.map(p=>p[0])).size,s.points.length);assert(s.points.every(p=>p[0]>='2025-10-02'&&p[0]<='2026-10-02'));}
 const mean=avg(series);
 for(const [date,value,n] of mean.points){const values=series.map(s=>s.points.find(p=>p[0]===date)?.[1]).filter(Number.isFinite);assert.equal(n,values.length);assert.equal(value,n?values.reduce((a,b)=>a+b,0)/n:null);checked++;}
}
for(const sector of new Set(data.lockups.events.map(e=>e.sector))){
 const series=data.lockups.events.filter(e=>e.sector===sector&&e.window.anchor_close>0).map(e=>({points:e.window.path.map(p=>[p[0],Number.isFinite(p[2])?100*(p[2]/e.window.anchor_close-1):null])}));
 const mean=avg(series,true);
 for(const [offset,value,n] of mean.points){assert(offset>=-30&&offset<=30);const values=series.map(s=>s.points.find(p=>p[0]===offset)?.[1]).filter(Number.isFinite);assert.equal(n,values.length);assert.equal(value,n?values.reduce((a,b)=>a+b,0)/n:null);if(offset===0&&n)assert(Math.abs(value)<1e-12);checked++;}
}
assert(!html.includes('Cohort average'));assert(!html.includes('the session they defended'));assert(!html.includes('who defended it once it traded'));
for(const id of ['ah-select-all','ah-select-sector','ah-sector-average','lockup-select-all','lockup-select-sector','lockup-clear-compare','lockup-sector-average'])assert(html.includes('id="'+id+'"'));
console.log(`PASS ${checked} observed sector-average points, missing/zero/negative cases, 1Y bounds and expiry-zero alignment; concise labels and all controls present`);
