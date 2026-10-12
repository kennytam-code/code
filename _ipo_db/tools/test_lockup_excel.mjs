import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const base=new URL('../',import.meta.url),j=JSON.parse(await fs.readFile(new URL('data/market_views_template.json',base),'utf8'));
const temp=new URL('out/_lockup_artifact_probe.xlsx',base).pathname;try{await fs.copyFile(new URL('out/_lockup_evaluator_only.xlsx',base),temp)}catch{await fs.writeFile(temp,Buffer.from(j.xlsx_base64,'base64'))};
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(temp)),s=wb.worksheets.getItem('Lock-up'),chart=wb.worksheets.getItem('Chart Data');
const batch=JSON.parse(await fs.readFile(new URL('data/batches/lockup_events.json',base),'utf8')),events=batch.events.filter(e=>e.category==='Cornerstone'&&e.date_basis!=='No cornerstone tranche');
const value=a=>s.getRange(a).values[0][0];
const match=(actual,expected,label)=>{if(expected==null)assert.ok(!Number.isFinite(actual),`${label}: expected unavailable, got ${actual}`);else assert.ok(Number.isFinite(actual)&&Math.abs(actual-expected)<1e-10,`${label}: ${actual} != ${expected}`);};
wb.recalculate();
let observed=0;
const sample=process.argv.includes("--sample"),selected=sample?[0,events.length-1,...["Complete","Upcoming expiry","After window pending","Missing close / suspended"].map(status=>events.findIndex(e=>e.windows?.["30 trading sessions"]?.status===status)),events.findIndex(e=>!e.last_day_locked),events.findIndex(e=>e.code.startsWith("0")),events.findIndex(e=>events.filter(x=>x.code===e.code).length>1)].filter(i=>i>=0):events.map((_,i)=>i);
for(const i of [...new Set(selected)]){
 if(i%40===0)console.log(`Checking lock-up selector ${i+1}/${events.length}`);
 const e=events[i],w=e.windows?.['30 trading sessions']||{};s.getRange('B4').values=[[e.code]];s.getRange('E4').values=[[`${e.category} · ${e.last_day_locked||'date unavailable'}`]];
 const summary=s.getRange('A8:A23').values,helpers=s.getRange('P2:P11').values,points=chart.getRange('L5:L65').values;
 assert.equal(helpers[5][0],i+8,`event identity ${i}`);assert.equal(summary[0][0],e.name);assert.equal(helpers[6][0],'');
 match(summary[6][0],w.before_pct==null?null:w.before_pct/100,`event ${i} before`);match(summary[10][0],w.after_pct==null?null:w.after_pct/100,`event ${i} after`);
 const byOffset=new Map((w.path||[]).map(p=>[p[0],p]));
 for(let offset=-30;offset<=30;offset++){
  const p=byOffset.get(offset),expected=p?.[2]&&w.anchor_close?p[2]/w.anchor_close-1:null;
  match(points[offset+30][0],expected,`event ${i} day ${offset}`);if(expected!=null)observed++;
 }
 if(i%100===0)console.log(`Checked event ${i}/${events.length}`);
}
const codes=[...new Set(events.map(e=>e.code))];
for(const code of (sample?[codes[0],codes.at(-1),...selected.map(i=>events[i].code)]:codes)){
 s.getRange('B4').values=[[code]];s.getRange('E4').values=[['Auto']];
 const candidates=events.map((e,i)=>({e,i})).filter(x=>x.e.code===code),past=candidates.filter(x=>x.e.last_day_locked&&x.e.last_day_locked<=batch.price_asof),cs=past.filter(x=>x.e.category==='Cornerstone'),pool=cs.length?cs:past.length?past:candidates;
 pool.sort((a,b)=>(b.e.last_day_locked||'').localeCompare(a.e.last_day_locked||''));assert.equal(value('P7'),pool[0].i+8,`Auto ${code}`);
}
for(const code of ['', 'not a stock', '9999']){
 s.getRange('B4').values=[[code]];assert.equal(value('A8'),'Unknown H code');assert.ok(value('P8').includes('Unknown H code'));match(value('A14'),null,'unknown before');match(value('A18'),null,'unknown after');
 for(let r=5;r<=65;r++)match(chart.getRange(`L${r}`).values[0][0],null,'unknown chart');
}
s.getRange('B4').values=[[2701]];s.getRange('E4').values=[['old event that does not exist']];assert.equal(value('A8'),'NSING TECH');assert.ok(value('P8').includes('Auto event shown'));assert.equal(value('P7'),value('P4'));
const zeroCode=events.find(e=>e.code.startsWith('0')).code;s.getRange('B4').values=[[Number(zeroCode)]];s.getRange('E4').values=[['Auto']];assert.equal(String(value('P2')).padStart(4,'0'),zeroCode);assert.equal(events[value('P7')-8].code,zeroCode);
console.log(`PASS ${sample?new Set(selected).size:events.length} evaluated event selectors (${sample?"representative boundary/status cases":"exhaustive"}), ${sample?"selected":codes.length} Auto choices, ${observed} graph observations, both returns, unknown/zero-prefixed codes and stale-event fallback`);
await fs.unlink(temp);
