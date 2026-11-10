import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const root=new URL('../',import.meta.url),w=Workbook.create(),s=w.worksheets.add('Database style');
const groups=[['Identity','#F4E9EA','#CB2125'],['Deal terms','#E9EDF2','#455A70'],['Demand','#EFEDE7','#756044'],['Performance','#E8EFED','#3C6B60'],['Fundamentals','#EDEBF2','#655578'],['A / H','#E9EFF3','#466779'],['Banks & docs','#ECEEEF','#535F6B'],['Review','#F0F0F0','#60656B']];
for(let i=0;i<groups.length;i++){
 const [label,fill,color]=groups[i],r=i+1;
 s.getRange(`A${r}`).values=[[label]];s.getRange(`A${r}`).format={fill,font:{name:'Arial',size:10,bold:true,color},verticalAlignment:'center',borders:{bottom:{style:'thin',color}}};
}
s.getRange('C1').values=[['Column label']];s.getRange('C1').format={fill:'#F3F4F6',font:{name:'Arial',size:10,bold:true,color:'#353D49'},verticalAlignment:'center',horizontalAlignment:'center',wrapText:true,borders:{bottom:{style:'thin',color:'#CBD1D9'}}};
s.getRange('D1').values=[['Body']];s.getRange('D1').format={font:{name:'Arial',size:10,bold:false,color:'#27313D'},verticalAlignment:'center',borders:{bottom:{style:'hair',color:'#E5E8EC'}}};
s.getRange('E1').values=[['Company']];s.getRange('E1').format={font:{name:'Arial',size:10,bold:true,color:'#27313D'},verticalAlignment:'center',borders:{bottom:{style:'hair',color:'#E5E8EC'}}};
s.getRange('A1:E8').format.columnWidth=22;s.getRange('A1:E8').format.rowHeight=24;s.showGridLines=false;
w.recalculate();console.log((await w.inspect({kind:'table',range:"'Database style'!A1:E2",tableMaxRows:2,tableMaxCols:5,maxChars:900})).ndjson);
const file=await SpreadsheetFile.exportXlsx(w),path=new URL('out/database_desk_style.xlsx',root).pathname;await file.save(path);
await fs.writeFile(new URL('data/database_desk_style.json',root),JSON.stringify({version:1,xlsx_base64:(await fs.readFile(path)).toString('base64')})+'\n');
