import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const code=fs.readFileSync(new URL('../assets/desk_monitors.js',import.meta.url),'utf8');
function source(name){const start=code.indexOf('function '+name+'(');assert(start>=0);let i=code.indexOf('{',start),depth=1;for(i++;depth;i++){if(code[i]==='{')depth++;if(code[i]==='}')depth--;}return code.slice(start,i);}
const ctx=vm.createContext({Map,Set,Number,Date,deskColors:['#123','#456']});
for(const name of ['averageSeries','selectedAverages','comparisonLines'])vm.runInContext(source(name),ctx);
const point=(code,sector,ret)=>({code,name:code,sector,points:[[0,0],[1,ret]]});
const fixture=[point('A','Tech',10),point('A','Tech',30),point('B','Tech',-10),point('C','Consumer',0)];
let result=ctx.selectedAverages(fixture.slice(0,3),true,true);
assert.equal(result.overall.points[1][1],5);assert.equal(result.overall.points[1][2],2);assert.equal(result.sectors[0].points[1][1],5);
result=ctx.selectedAverages([{...point('A','Tech',0),points:[[0,0],[1,null]]},point('B','Consumer',-10)],true,true);
assert.equal(result.overall.points[0][1],0);assert.equal(result.overall.points[0][2],2);assert.equal(result.overall.points[1][1],-10);assert.equal(result.overall.points[1][2],1);
assert.equal(ctx.selectedAverages([],true).overall.points.length,0);
assert.deepEqual(ctx.comparisonLines(fixture,'stocks',true),fixture);
const overall=ctx.comparisonLines(fixture,'average',true);assert.equal(overall.length,1);assert(Math.abs(overall[0].points[1][1]-10/3)<1e-12);
const sectors=ctx.comparisonLines(fixture,'sector',true);assert.equal(sectors.length,2);assert(sectors.every(s=>s.mean));assert(!sectors.some(s=>s.name==='Selected average'));
const html=fs.readFileSync(new URL('../out/hk_ipo_dashboard.html',import.meta.url),'utf8');
assert(!html.includes('Selected stocks + average'));assert(!html.includes('id="ah-selected-average"'));assert(html.includes(code));
for(const prefix of ['ah','lockup']){assert(html.includes('id="'+prefix+'-compare-mode"'));assert(html.includes('id="'+prefix+'-compare-pager"'));}
let scripts=0;for(const match of html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)){if(/application\/octet-stream/.test(match[1]))continue;new vm.Script(match[2]);scripts++;}assert(scripts>0);
console.log('PASS averages: one weight per selected stock, duplicate expiries, missing/zero/negative values; mutually exclusive stocks/selected average/sector modes; shipped JS compiles.');
