import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const root=new URL('../',import.meta.url),wb=Workbook.create(),s=wb.worksheets.add('Desk theme');
const deals=JSON.parse(await fs.readFile(new URL('data/deals.json',root),'utf8')).deals;
const roles={title:1,section:3,header:4,body:5,alternate:6,input:8,minor:10,key:12,soft:14,hidden:16};
s.showGridLines=false;s.getRange('A1:D12').format={font:{name:'Arial',size:10,color:'#263A4A'},verticalAlignment:'center'};
s.getRange('A:A').format.columnWidth=28;s.getRange('B:D').format.columnWidth=19;
s.getRange('A1').values=[['IPO prices']];s.getRange('A1:D1').format={font:{name:'Arial',size:17,bold:true,color:'#CB2125'},rowHeight:32,borders:{bottom:{style:'thin',color:'#CB2125'}}};
s.getRange('A3').values=[['DAILY MONITOR']];s.getRange('A3:D3').format={fill:'#CB2125',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:24};
s.getRange('A4:D4').values=[['Company','Sector','IPO date','Offer price (HK$)']];s.getRange('A4:D4').format={fill:'#333333',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:36,wrapText:true,borders:{bottom:{style:'thin',color:'#CB2125'}}};
for(let i=0;i<2;i++){let d=deals[deals.length-1-i];s.getRange(`A${5+i}:D${5+i}`).values=[[d.name,d.sector,d.ipo_date,d.final_price]];s.getRange(`A${5+i}:D${5+i}`).format={fill:i?'#F7F5F3':'#FFFFFF',rowHeight:25,borders:{bottom:{style:'hair',color:'#E6E1DD'}}};}
s.getRange('A8').values=[['Stored']];s.getRange('A8:D8').format={fill:'#F0F3F6',font:{name:'Arial',size:10,color:'#245A87'},rowHeight:27,borders:{bottom:{style:'thin',color:'#A6B4C0'}}};
s.getRange('A10').values=[['Sector averages']];s.getRange('A10:D10').format={font:{name:'Arial',size:12,bold:true,color:'#333333'},rowHeight:27,borders:{bottom:{style:'thin',color:'#CB2125'}}};
s.getRange('A12').values=[[deals.at(-1).name]];s.getRange('A12:D12').format={font:{name:'Arial',size:10,bold:true,color:'#263A4A'},rowHeight:25};
s.getRange('A14:D14').values=[['Field','Database','Override','Selected deal']];s.getRange('A14:D14').format={fill:'#EDEFF1',font:{name:'Arial',size:10,bold:true,color:'#333333'},rowHeight:24,borders:{bottom:{style:'thin',color:'#BEC4CA'}}};
s.getRange('A16').values=[[0]];s.getRange('A16:D16').format={fill:'#FFFFFF',font:{name:'Arial',size:10,color:'#333333'},numberFormat:';;;'};
wb.recalculate();const file=await SpreadsheetFile.exportXlsx(wb),path=new URL('out/desk_theme.xlsx',root).pathname;await file.save(path);
await fs.writeFile(new URL('data/desk_theme.json',root),JSON.stringify({version:3,roles,xlsx_base64:(await fs.readFile(path)).toString('base64'),chart_colors:['CB2125','315B7D','85817D','4E7468'],chart_grid:'E6E1DD'}));
console.log('Authored compact desk theme from current IPO data');
