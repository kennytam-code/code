/** Run the shipped comparison event handlers against the real embedded observations.
 * The small control adapter is not a browser; screenshots are tested separately.
 */
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
const root=new URL('../',import.meta.url),html=fs.readFileSync(new URL('out/hk_ipo_dashboard.html',root),'utf8');
const payload=html.match(/<script id="ipo-payload" type="application\/octet-stream">([A-Za-z0-9+/=]+)<\/script>/)[1];
const data=JSON.parse(gunzipSync(Buffer.from(payload,'base64'))),code=fs.readFileSync(new URL('assets/desk_monitors.js',root),'utf8');
const withoutLockups=({lockups,...other})=>other;
assert.equal(data.deals.length,527);assert.equal(Object.keys(data.ahstudy).length,72);
fs.mkdirSync(new URL('out/update_20261028/',root),{recursive:true});
const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
// Limit duplicate-ID check to static markup (the JS source contains templates).
const markup=html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'');
const realIds=[...markup.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);assert.equal(realIds.length,new Set(realIds).size);
const controls=new Map(realIds.map(id=>[id,{id,value:'',checked:false,hidden:false,disabled:false,dataset:{},innerHTML:'',textContent:'',handlers:{},addEventListener(type,fn){(this.handlers[type]??=[]).push(fn);},fire(type='change',target=this){for(const fn of this.handlers[type]||[])fn({target});}}]));
const plots=new Map(),svgs=new Map();
function $(selector){if(selector.endsWith(' svg'))return svgs.get(selector.slice(1,-4));const key=selector.slice(1);assert(controls.has(key),'missing control '+selector);return controls.get(key);}
$('#ah-compare-mode').value='stocks';$('#lockup-compare-mode').value='average';$('#ah-compare-horizon').value='Max';
const ahDeals=data.market_deals.filter(d=>d.a_share_code).map(d=>({...d,classReview:/share-scale/.test(data.ahstudy[d.code]?.exclusion||'')&&!data.ahstudy[d.code]?.entitlement_review}));
const context=vm.createContext({Map,Set,Number,Date,Math,console,DATA:data,AHST:data.ahstudy,ahDeals,LOCKUPS:data.lockups.events,deals:data.deals,$,
 document:{querySelectorAll:()=>[]},safeText:v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;'),
 fillAhSubs:()=>{$('#ah-sub').value='';},redrawAHTab:()=>{},redrawLockupTab:()=>{},
 deskLines:(box,series,options)=>{plots.set(box.id,series);svgs.set(box.id,series.some(s=>s.points.some(p=>Number.isFinite(p[1])))?{dataset:{}}:null);}
});
function source(text,name){const start=text.indexOf('function '+name+'(');assert(start>=0,name);let i=text.indexOf('{',start),depth=1;for(i++;depth;i++){if(text[i]==='{')depth++;if(text[i]==='}')depth--;}return text.slice(start,i);}
for(const name of ['normalCode','matchesDealSearch'])vm.runInContext(source(html,name),context);
vm.runInContext(code.slice(0,code.indexOf('function deskLines(')),context);
vm.runInContext(code.slice(code.indexOf('const ahComparisons='),code.indexOf('const PEERS=')),context);
vm.runInContext(code.slice(code.lastIndexOf("for(const id of ['ah-sec','ah-sub'])")),context);
const run=s=>vm.runInContext(s,context),change=(id,value)=>{$('#'+id).value=value;$('#'+id).fire(id==='lockup-q'?'input':'change');};
const current=prefix=>plots.get(prefix+'-compare-chart'),json=x=>JSON.parse(JSON.stringify(x));
let checks=0;
function verifyPages(prefix,expected){
 let seen=[];for(let page=0;page<100;page++){
  const plotted=current(prefix);assert(plotted.length<=6);assert(plotted.every(s=>!s.mean));seen.push(...plotted.map(s=>s.name));
  if($('#'+prefix+'-compare-next').disabled)break;
  $('#'+prefix+'-compare-next').fire('click');
 }
 assert.deepEqual(seen,expected.map(s=>s.name));assert.equal(new Set(seen).size,seen.length);checks+=seen.length;
}
function expectedAverage(series,offset){
 const byCode=new Map();for(const s of series){if(!byCode.has(s.code))byCode.set(s.code,[]);byCode.get(s.code).push(s);}
 const dates=[...new Set(series.flatMap(s=>s.points.map(p=>p[0])))].sort(offset?(a,b)=>a-b:undefined);
 return dates.map(date=>{const perStock=[...byCode.values()].map(events=>events.map(s=>s.points.find(p=>p[0]===date)?.[1]).filter(Number.isFinite)).filter(values=>values.length).map(values=>values.reduce((a,b)=>a+b,0)/values.length);return[date,perStock.length?perStock.reduce((a,b)=>a+b,0)/perStock.length:null,perStock.length];});
}
function assertMean(actual,expected){assert.equal(actual.length,expected.length);for(let i=0;i<actual.length;i++){assert.equal(actual[i][0],expected[i][0]);assert.equal(actual[i][2],expected[i][2]);if(expected[i][1]===null)assert.equal(actual[i][1],null);else assert(Math.abs(actual[i][1]-expected[i][1])<1e-9);checks++;}}
for(const sector of new Set(ahDeals.map(d=>d.sector))){
 change('ah-compare-sector',sector);assert.equal($('#ah-sec').value,sector);change('ah-compare-mode','stocks');
 const scoped=run("ahScopeRows().map(d=>ahSeries(d,...ahCompareWindow())).sort((a,b)=>a.code.localeCompare(b.code))");
 assert(scoped.every(s=>s.sector===sector));verifyPages('ah',scoped.filter(s=>s.points.some(p=>Number.isFinite(p[1]))));
 change('ah-compare-mode','average');const plotted=current('ah');assert.equal(plotted.length,1);assert(plotted[0].mean);assertMean(plotted[0].points,expectedAverage(scoped));
 change('ah-compare-mode','sector');assert.equal(current('ah').length,1);assert(current('ah')[0].name.startsWith(sector));
 $('#ah-select-all').fire('click');assert(run('[...ahComparisons].every(c=>ahDeals.find(d=>d.code===c).sector===\''+sector+'\')'));
}
// A top-level sector/subsector change must also restrict comparison lines.
change('ah-sec','Technology');assert.equal($('#ah-compare-sector').value,'Technology');change('ah-sub','Semiconductors');change('ah-compare-mode','stocks');assert(run("[...ahComparisons].every(c=>ahDeals.find(d=>d.code===c).subsector==='Semiconductors')"));
const first=current('ah')[0].code;$('#ah-tbl').fire('change',{matches:()=>true,dataset:{code:first},checked:false});assert(!run('ahComparisons.has('+JSON.stringify(first)+')'));assert(!current('ah').some(s=>s.code===first));
// A stale off-sector checkbox must not leak through, even without resetting the set.
run("ahComparisons.add(ahDeals.find(d=>d.sector!=='Technology').code);renderAHComparison();");assert(current('ah').every(s=>s.sector==='Technology'));
change('ah-compare-horizon','Custom');change('ah-compare-from','2026-01-01');change('ah-compare-to','2026-03-31');assert(current('ah').every(s=>s.points.every(p=>p[0]>='2026-01-01'&&p[0]<='2026-03-31')));
change('ah-compare-from','2027-01-01');assert.equal($('#ah-compare-count').textContent,'Choose a valid date range.');assert($('#ah-compare-pager').hidden);
change('ah-compare-horizon','Max');$('#ah-clear-compare').fire('click');assert.equal(current('ah').length,0);assert($('#ah-compare-chart').innerHTML.includes('Select pairs'));
for(const sector of new Set(data.lockups.events.map(e=>e.sector))){
 change('lockup-compare-sector',sector);assert.equal($('#lockup-sec').value,sector);change('lockup-compare-mode','stocks');
 const scoped=run("lockScopeRows().filter(x=>x.e.last_day_locked&&x.e.window.anchor_close>0&&x.e.window.path.some(p=>Number.isFinite(p[2]))).sort((a,b)=>a.e.code.localeCompare(b.e.code)||a.e.last_day_locked.localeCompare(b.e.last_day_locked)).map(x=>lockSeries(x.e))");
 assert(scoped.every(s=>s.sector===sector));verifyPages('lockup',scoped);
 change('lockup-compare-mode','average');if(scoped.length){assert.equal(current('lockup').length,1);assertMean(current('lockup')[0].points,expectedAverage(scoped,true));}
 change('lockup-compare-mode','sector');assert(current('lockup').every(s=>s.mean&&s.name.startsWith(sector)));
}
change('lockup-sec','');change('lockup-q','9607');change('lockup-compare-mode','stocks');assert(current('lockup').every(s=>s.code==='9607'));$('#lockup-select-all').fire('click');assert(run('[...lockComparisons].every(i=>LOCKUPS[i].code===\'9607\')'));
change('lockup-q','');change('lockup-compare-from','2025-01-01');change('lockup-compare-to','2025-06-30');change('lockup-compare-mode','average');
const inRange=run("lockScopeRows().filter(x=>x.e.last_day_locked>='2025-01-01'&&x.e.last_day_locked<='2025-06-30'&&x.e.window.anchor_close>0&&x.e.window.path.some(p=>Number.isFinite(p[2]))).map(x=>lockSeries(x.e))");assertMean(current('lockup')[0].points,expectedAverage(inRange,true));
change('lockup-compare-from','2027-01-01');assert.equal($('#lockup-compare-count').textContent,'Choose a valid expiry-date range.');assert($('#lockup-compare-pager').hidden);
change('lockup-compare-from','');change('lockup-compare-to','');$('#lockup-clear-compare').fire('click');assert.equal(current('lockup').length,0);
fs.writeFileSync(new URL('out/update_20261028/scope_checks.json',root),JSON.stringify({checks,ah_pairs:ahDeals.length,lockup_events:data.lockups.events.length,refreshed_dataset:true,real_browser:false,passed:true},null,2)+'\n');
console.log(`PASS ${checks} assertions/observations across ${ahDeals.length} A/H pairs and ${data.lockups.events.length} lock-up events: scopes, both selector directions, averages, all pages, custom dates, search, clear and off-sector stale selections; refreshed dataset checked.`);
