import fs from 'node:fs/promises';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';
const inputs=JSON.parse(await fs.readFile(new URL('../out/pipeline_layout_inputs.json',import.meta.url),'utf8'));
const wb=Workbook.create(),s=wb.worksheets.add('Pipeline');
s.showGridLines=false;
const last=inputs.last_row;
s.getRange(`A1:AD${last}`).format={font:{name:'Arial',size:10,color:'#202B38'},rowHeight:26,verticalAlignment:'center',wrapText:true};
const widths=[8,36,16,19,17,26,15,12,12,14,13,12,17,19,16,35,13,13,24,12,12,15,12,13,13,14,35,35,62,62];
function letter(n){let v='';for(;n>0;n=Math.floor((n-1)/26))v=String.fromCharCode(65+(n-1)%26)+v;return v;}
widths.forEach((width,i)=>s.getRange(`${letter(i+1)}:${letter(i+1)}`).format.columnWidth=width);
s.getRange('A1:L1').merge();s.getRange('A1').values=[['IPO pipeline']];s.getRange('A1:L1').format={font:{name:'Arial',size:17,bold:true,color:'#23384D'},rowHeight:34};
s.getRange('A2:L2').merge();s.getRange('A2').values=[[inputs.subtitle]];s.getRange('A2:L2').format={font:{name:'Arial',size:10,color:'#586575'},rowHeight:30,wrapText:true};
for(const [range,title] of [['A4:F4','DEAL'],['G4:K4','TERMS'],['L4','FILING'],['M4:AD4','INVESTORS, BANKS & OTHER DETAILS']]){s.getRange(range).merge();s.getRange(range).values=[[title]];s.getRange(range).format={fill:'#34495E',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:25};}
s.getRange('A5:AD5').values=[inputs.headers];s.getRange('A5:AD5').format={fill:'#E8EDF2',font:{name:'Arial',size:10,bold:true,color:'#23384D'},rowHeight:40,wrapText:true,borders:{bottom:{style:'thin',color:'#A2ADBA'}}};
s.getRange(`A6:AD${5+inputs.pipeline.length}`).values=inputs.pipeline.map(row=>row.map((value,i)=>i===11&&value?'HKEX filing':value));
for(let i=0;i<inputs.pipeline.length;i++){
 const row=6+i;
 s.getRange(`A${row}:AD${row}`).format={fill:i%2?'#F4F6F8':'#FFFFFF',rowHeight:36,borders:{bottom:{style:'hair',color:'#D7DDE4'}}};
 s.getRange(`B${row}`).format.font={name:'Arial',size:10,bold:true,color:'#23384D'};
 for(const col of ['D','F','G'])s.getRange(`${col}${row}`).format.font.color='#0000FF';
 s.getRange(`L${row}`).format.font={name:'Arial',size:10,color:'#0563C1',underline:'single'};
 s.getRange(`G${row}:K${row}`).format.horizontalAlignment='right';
}
s.getRange(`G6:G${5+inputs.pipeline.length}`).setNumberFormat('#,##0');s.getRange(`H6:I${5+inputs.pipeline.length}`).setNumberFormat('0.00');s.getRange(`J6:J${5+inputs.pipeline.length}`).setNumberFormat('0.0');s.getRange(`K6:K${5+inputs.pipeline.length}`).setNumberFormat('0.0"%"');
const q=inputs.queue_start;
for(const row of [q,q+1,inputs.last_row])s.getRange(`A${row}:L${row}`).merge();
s.getRange(`A${q}`).values=[['Latest applications']];s.getRange(`A${q}:L${q}`).format={font:{name:'Arial',size:13,bold:true,color:'#23384D'},rowHeight:30};
// These widths belong to the deal table as well; merge the applicant name cells.
s.getRange(`A${q+2}:B${q+2}`).merge();
s.getRange(`A${q+2}:G${q+2}`).format={fill:'#E8EDF2',font:{name:'Arial',size:10,bold:true,color:'#23384D'},rowHeight:30};
for(let i=0;i<inputs.queue.length;i++){
 const r=q+3+i;s.getRange(`A${r}:B${r}`).merge();
 s.getRange(`A${r}:G${r}`).format={fill:i%2?'#F4F6F8':'#FFFFFF',rowHeight:42,borders:{bottom:{style:'hair',color:'#D7DDE4'}}};
 s.getRange(`A${r}`).values=[[inputs.queue[i].applicant]];
}
s.freezePanes.freezeRows(5);s.freezePanes.freezeColumns(2);
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'Pipeline!A4:L8',include:'values',tableMaxRows:5,tableMaxCols:12})).ndjson);
const file=await SpreadsheetFile.exportXlsx(wb),path=new URL('../out/_pipeline_layout.xlsx',import.meta.url).pathname;
await file.save(path);
await fs.writeFile(new URL('../data/pipeline_layout.json',import.meta.url),JSON.stringify({version:1,subtitle:inputs.subtitle,pipeline_count:inputs.pipeline.length,xlsx_base64:(await fs.readFile(path)).toString('base64')}));
await fs.unlink(path);
const preview=await wb.render({sheetName:'Pipeline',range:'A1:L18',scale:1,format:'png'});
await fs.writeFile(new URL('../out/pipeline_excel_preview.png',import.meta.url),new Uint8Array(await preview.arrayBuffer()));
console.log('Saved Artifact-authored Pipeline design');
