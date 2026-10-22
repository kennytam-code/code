import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const root=new URL('../',import.meta.url),out=new URL('out/efficiency_20261022/',root);
const wb=Workbook.create(),s=wb.worksheets.add('Request controls');
s.showGridLines=false;s.getRange('A1:F4').format.font={name:'Arial',size:10,color:'#263442'};
s.getRange('A1:F4').format.columnWidth=19;s.getRange('A1:F4').format.rowHeight=25;
s.getRange('A2').values=[['Valuations']];s.getRange('B2').values=[['Selected']];
s.getRange('C2:F2').merge();s.getRange('C2').values=[['Screener company + comparisons']];
s.getRange('A4').values=[['Verification']];s.getRange('B4').values=[['Off']];
for(const a of ['B2','B4']){s.getRange(a).format.fill='#EEF3F7';s.getRange(a).format.font={name:'Arial',size:11,color:'#1D4E89',bold:true};}
s.getRange('C2:F2').format.font={name:'Arial',size:10,color:'#626E7B'};
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(new URL('request_controls.xlsx',out).pathname);
const preview=await wb.render({sheetName:s.name,range:'A1:F4',scale:1.5,format:'png'});
await fs.writeFile(new URL('request_controls.png',out),new Uint8Array(await preview.arrayBuffer()));
await fs.writeFile(new URL('data/request_controls.json',root),JSON.stringify({xlsx_base64:(await fs.readFile(new URL('request_controls.xlsx',out))).toString('base64')})+'\n');
console.log('Created bounded request-control template');
