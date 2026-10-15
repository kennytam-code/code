import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const code=fs.readFileSync(new URL('../assets/desk_monitors.js',import.meta.url),'utf8');
function source(name){const start=code.indexOf('function '+name+'(');assert(start>=0);let i=code.indexOf('{',start),depth=1;for(i++;depth;i++){if(code[i]==='{')depth++;if(code[i]==='}')depth--;}return code.slice(start,i);}
const controls=new Map(),element=id=>{if(!controls.has(id))controls.set(id,{value:'',checked:false,dataset:{},innerHTML:'',textContent:''});return controls.get(id);};
let plotted=[];
const ctx=vm.createContext({Map,Set,Number,Date,deskColors:['#123','#456'],$:element,document:{querySelectorAll:()=>[]},deskLines:(_box,series)=>{plotted=series;},ahCompareWindow:()=>['2026-01-01','2026-01-10']});
for(const name of ['averageSeries','selectedAverages','validAHPoint','adjustedAHPoint','ahSeries','renderAHComparison','lockSeries','renderLockComparison'])vm.runInContext(source(name),ctx);
const point=(code,sector,ret)=>({code,name:code,sector,points:[[0,0],[1,ret]]});
let result=ctx.selectedAverages([point('A','Tech',10),point('A','Tech',30),point('B','Tech',-10)],true,true);
assert.equal(result.overall.points[1][1],5);assert.equal(result.overall.points[1][2],2);assert.equal(result.sectors[0].points[1][1],5);
result=ctx.selectedAverages([{...point('A','Tech',0),points:[[0,0],[1,null]]},point('B','Consumer',-10)],true,true);
assert.equal(result.overall.points[0][1],0);assert.equal(result.overall.points[0][2],2);assert.equal(result.overall.points[1][1],-10);assert.equal(result.overall.points[1][2],1);
assert.equal(ctx.selectedAverages([],true).overall.points.length,0);
ctx.AHST={};ctx.ahDeals=[];
for(const [code,premium] of [['A',20],['B',40],['UNSELECTED',900]]){
 ctx.ahDeals.push({code,name:code,sector:'Tech'});ctx.AHST[code]={history:[['2026-01-05',100,100+premium,1,premium,'2026-01-05']],h_history:[['2026-01-05',100]]};
}
ctx.ahComparisons=new Set(['A','B']);element('#ah-compare-horizon').value='Custom';element('#ah-selected-average').checked=true;element('#ah-sector-average').checked=true;
ctx.renderAHComparison();
assert.equal(plotted.length,4);assert(Math.abs(plotted[0].points[0][1]-30)<1e-10);assert(Math.abs(plotted[1].points[0][1]-30)<1e-10);assert(!plotted.some(s=>s.name.includes('UNSELECTED')));
ctx.ahComparisons.delete('B');ctx.renderAHComparison();assert(Math.abs(plotted[0].points[0][1]-20)<1e-10);assert.equal(plotted[0].points[0][2],1);
ctx.ahComparisons.clear();ctx.renderAHComparison();assert(plotted.every(s=>s.points.length===0));
const event=(code,date,ret,anchor=100)=>({code,name:code,sector:'Tech',last_day_locked:date,window:{anchor_close:anchor,path:[[-1,date,90],[0,date,100],[1,date,100+ret]]}});
ctx.LOCKUPS=[event('A','2026-01-03',10),event('A','2026-01-08',30),event('B','2026-01-04',-10),event('UNSELECTED','2026-01-05',900),event('NO_PRICE','2026-01-05',0,null)];
ctx.lockComparisons=new Set([0,1,2,4]);element('#lockup-compare-mode').value='selected';element('#lockup-sector-average').checked=true;
ctx.renderLockComparison();
assert(Math.abs(plotted[0].points.find(p=>p[0]===1)[1]-5)<1e-10);assert.equal(plotted[0].points.find(p=>p[0]===1)[2],2);assert(Math.abs(plotted[1].points.find(p=>p[0]===1)[1]-5)<1e-10);assert(!plotted.some(s=>s.name.includes('UNSELECTED')||s.name.includes('NO_PRICE')));
element('#lockup-compare-to').value='2026-01-05';ctx.renderLockComparison();assert(Math.abs(plotted[0].points.find(p=>p[0]===1)[1])<1e-10);
ctx.lockComparisons.delete(2);ctx.renderLockComparison();assert(Math.abs(plotted[0].points.find(p=>p[0]===1)[1]-10)<1e-10);
element('#lockup-compare-mode').value='average';ctx.renderLockComparison();assert.equal(plotted.length,2);
ctx.lockComparisons.clear();ctx.renderLockComparison();assert(plotted.every(s=>s.points.length===0));
assert(!code.includes('Selected-event average'));assert(!code.includes('sector averages: all'));
const html=fs.readFileSync(new URL('../out/hk_ipo_dashboard.html',import.meta.url),'utf8');
assert(!html.includes('Selected-event average'));assert(html.includes('id="ah-selected-average" type="checkbox" checked'));assert(html.includes('Selected stocks + average'));assert(html.includes(code));
let scripts=0;for(const match of html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)){if(/application\/octet-stream/.test(match[1]))continue;new vm.Script(match[2]);scripts++;}
assert(scripts>0);
console.log('PASS actual AH/lock renderers exclude unselected outliers; selection/date/toggle changes recalculate; selected stocks have one weight; missing/zero/negative cases pass');
