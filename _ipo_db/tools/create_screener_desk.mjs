import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const root=new URL('../',import.meta.url),out=new URL('out/efficiency_20261022/',root);
const wb=Workbook.create(),s=wb.worksheets.add('Screener desk');s.showGridLines=false;
const widths=[22,26,10,14,23,22,10,12,12,10,10,10,10,9,9,10,10];
const col=i=>String.fromCharCode(65+i);widths.forEach((w,i)=>s.getRange(`${col(i)}:${col(i)}`).format.columnWidth=w);
s.getRange('A1:Q22').format.font={name:'Arial',size:10,color:'#263442'};s.getRange('A1:Q22').format.rowHeight=22;
s.getRange('A1:Q22').format.fill='#FFFFFF';s.getRange('A1:Q22').format.verticalAlignment='center';
const merges=['B4:C4','B5:C5','E5:L5','B6:C6','D6:E6','F6:G6','I6:L6','N6:Q6'];
for(let r=7;r<=14;r++)merges.push(`B${r}:C${r}`,`D${r}:E${r}`,`F${r}:G${r}`,`I${r}:J${r}`,`K${r}:L${r}`);
for(let r=7;r<=11;r++)merges.push(`N${r}:O${r}`,`P${r}:Q${r}`);
merges.forEach(r=>s.getRange(r).merge());
const set=(a,v)=>s.getRange(a).values=[[v]];
set('B4','H code / pipeline');set('B5','9607');set('E5','RA MATERIALS');
for(const [a,t] of [['B6','Company'],['D6','Database'],['F6','Override'],['I6','Selected deal'],['N6','Filters']])set(a,t);
const labels=['Sector','Subsector','Size (HK$m)','Profitable (Y/N)','A/H pair (Y/N)','IPO date','Offer P/E (x)','Public sub (x), expected'];labels.forEach((t,i)=>set('B'+(7+i),t));
for(const [r,t,v] of [[7,'Size percentile','19%'],[8,'Size bucket','Small'],[10,'Day-1 return','—'],[11,'1-month return','—'],[12,'Public sub (x)','—'],[13,'Cornerstone %','—'],[14,'Sponsors','—']]){set('I'+r,t);set('K'+r,v);}
for(const [r,t,v] of [[7,'Rank by','standard'],[8,'Cornerstone',''],[9,'A-share','All'],[10,'Include codes',''],[11,'Comparisons',10]]){set('N'+r,t);set('P'+r,v);}
for(const r of ['B6:G6','I6:L6','N6:Q6']){s.getRange(r).format.fill='#E9EDF1';s.getRange(r).format.font={name:'Arial',size:10,color:'#263442',bold:true};}
for(const r of ['B5:C5','F7:G14','P7:Q11']){s.getRange(r).format.fill='#EEF3F7';s.getRange(r).format.font={name:'Arial',size:10,color:'#1D4E89'};s.getRange(r).format.borders={bottom:{style:'hair',color:'#BCCBD8'}};}
for(let r=7;r<=14;r++)s.getRange(`F${r}:G${r}`).format.borders={bottom:{style:'thin',color:'#D4DDE6'}};
for(let r=7;r<=11;r++)s.getRange(`P${r}:Q${r}`).format.borders={bottom:{style:'thin',color:'#D4DDE6'}};
s.getRange('B5:C5').format.font={name:'Arial',size:11,color:'#1D4E89',bold:true};s.getRange('E5:L5').format.font={name:'Arial',size:12,color:'#263442',bold:true};
s.getRange('B7:L14').format.wrapText=true;s.getRange('N7:Q11').format.wrapText=true;s.getRange('B5:C5').format.wrapText=true;
s.getRange('B4:C4').format.font={name:'Arial',size:9,color:'#626E7B'};
const heights={4:16,5:34,6:24,7:22,8:30,9:22,10:22,11:22,12:22,13:22,14:38,15:8,16:0,17:0,18:0,19:22,20:38};
for(const [r,h] of Object.entries(heights))if(h)s.getRange(`A${r}:Q${r}`).format.rowHeight=h;
// Illustrative projection only; production formulas and values are grafted unchanged.
set('D7','Materials');set('D8','Specialty chemicals');set('D9',1712);set('D12','2026-10-28');
set('A20','#');set('B20','Company');set('C20','Code');set('D20','Sector');set('E20','Subsector');
s.getRange('A20:Q20').format.fill='#E9EDF1';s.getRange('A20:Q20').format.font={name:'Arial',size:10,color:'#263442',bold:true};
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(new URL('screener_desk.xlsx',out).pathname);
const preview=await wb.render({sheetName:s.name,range:'A4:Q14',scale:1.3,format:'png'});await fs.writeFile(new URL('screener_desk_template.png',out),new Uint8Array(await preview.arrayBuffer()));
await fs.writeFile(new URL('data/screener_desk_layout.json',root),JSON.stringify({widths,heights,merges,xlsx_base64:(await fs.readFile(new URL('screener_desk.xlsx',out))).toString('base64')})+'\n');
console.log('Created bounded Screener control layout');
