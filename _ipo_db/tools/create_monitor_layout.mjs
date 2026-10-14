import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const root=new URL('../',import.meta.url),wb=Workbook.create();
const put=(s,a,v)=>s.getRange(a).values=[[v]];
const base=(s,cols,end)=>{s.showGridLines=false;s.getRange(`A1:${end}80`).format={font:{name:'Arial',size:11,color:'#243746'},rowHeight:23};for(const [c,w]of cols)s.getRange(c+':'+c).format.columnWidth=w;};
const head=(s,r)=>s.getRange(r).format={fill:'#E7E7E7',font:{name:'Arial',size:10,bold:true,color:'#202020'},rowHeight:32,wrapText:true,borders:{top:{style:'thin',color:'#D71920'},bottom:{style:'thin',color:'#BBBBBB'}}};
const input=(s,r)=>s.getRange(r).format={fill:'#F5F5F5',font:{name:'Arial',size:11,color:'#0000FF'},borders:{bottom:{style:'thin',color:'#888888'}}};
const peers=JSON.parse(await fs.readFile(new URL('data/peer_pairs.json',root),'utf8'));
const p=wb.worksheets.add('Peer Trades');
base(p,[['A',19],['B',27],['C',27],['D',9],['E',19],['F',15],['G',12],['H',15]],'H');
put(p,'A2','Peer trades');p.getRange('A2:H2').format={font:{name:'Arial',size:15,bold:true,color:'#243746'},rowHeight:30,borders:{bottom:{style:'thin',color:'#A4B3BF'}}};
for(const [a,v]of [['A3','Pair'],['B3',peers.pairs[0].label],['E3','Source'],['F3','Stored'],['G3','Horizon'],['H3','1Y'],['A4','Product'],['B4',peers.pairs[0].segment],['E4','Custom start'],['F4',new Date('2025-10-02')],['G4','Custom end'],['H4',new Date(peers.asof)]])put(p,a,v);
input(p,'B3');input(p,'F3');input(p,'H3');input(p,'F4');input(p,'H4');p.getRange('B3').format.wrapText=true;p.getRange('A3:H3').format.rowHeight=34;p.getRange('F4').setNumberFormat('dd-mmm-yy');p.getRange('H4').setNumberFormat('dd-mmm-yy');
put(p,'B7',peers.pairs[0].name_a);put(p,'C7',peers.pairs[0].name_b);head(p,'A7:C7');
for(const [r,label]of [[8,'H code'],[9,'Price'],[10,'Currency'],[11,'Daily change'],[12,'Window return'],[13,'Quote date']]){put(p,'A'+r,label);p.getRange(`A${r}:C${r}`).format={rowHeight:25,borders:{bottom:{style:'hair',color:'#D5DDE3'}}};}
for(const [a,v]of [['E7','Return spread (pp)'],['F8',7.8],['E10','Chart from'],['E11','Chart to']])put(p,a,v);
p.getRange('E7:H7').format={font:{name:'Arial',size:10,bold:true,color:'#243746'},rowHeight:32,borders:{bottom:{style:'thin',color:'#A4B3BF'}}};p.getRange('F8').format.font={name:'Arial',size:16,bold:true,color:'#243746'};p.getRange('F8').setNumberFormat('0.0" pp"');p.getRange('B11:C12').setNumberFormat('0.0%;(0.0%);0.0%');p.getRange('B9:C9').setNumberFormat('0.00');p.getRange('B13:C13').setNumberFormat('dd-mmm-yy');p.getRange('F10:F11').setNumberFormat('dd-mmm-yy');
put(p,'A35','Peer list');p.getRange('A35:H35').format={font:{name:'Arial',size:12,bold:true,color:'#243746'},rowHeight:30};
p.getRange('A37:E37').values=[['Product','Company A','Company B','H code A','H code B']];head(p,'A37:E37');
for(let i=0;i<peers.pairs.length;i++){const x=peers.pairs[i],r=38+i;p.getRange(`A${r}:E${r}`).values=[[x.segment,x.name_a,x.name_b,x.code_a,x.code_b]];p.getRange(`A${r}:E${r}`).format={rowHeight:32,wrapText:true,fill:i%2?'#F3F6F8':'#FFFFFF',borders:{bottom:{style:'hair',color:'#D5DDE3'}}};}
const l=wb.worksheets.add('Lock-up');base(l,[['A',9],['B',22],['C',13],['D',15],['E',12],['F',12],['G',11],['H',11],['I',12],['J',12],['K',13],['L',11],['M',2]],'M');
put(l,'A2','Cornerstone lock-up');l.getRange('A2:M2').format={font:{name:'Arial',size:15,bold:true,color:'#243746'},rowHeight:30,borders:{bottom:{style:'thin',color:'#A4B3BF'}}};
put(l,'A4','H code');put(l,'B4','2706');put(l,'D4','Expiry event');put(l,'E4','Auto');input(l,'B4');input(l,'E4');l.getRange('E4').format.wrapText=true;l.getRange('A4:M4').format.rowHeight=38;
l.getRange('A7:L7').values=[['H code','Company','IPO date','Last locked day','Pre 30 sessions','Post 30 sessions','CS % of offer','Since IPO %','Deal HK$m','Coverage','Prices through','Filing']];head(l,'A7:L7');l.getRange('A8:L8').format={rowHeight:38,wrapText:true,borders:{bottom:{style:'thin',color:'#D5DDE3'}}};l.getRange('C8:D8').setNumberFormat('dd-mmm-yy');l.getRange('E8:H8').setNumberFormat('0.0%;(0.0%);0.0%');l.getRange('I8').setNumberFormat('#,##0.0');l.getRange('K8').setNumberFormat('dd-mmm-yy');
put(l,'A28','Compare expiry returns');l.getRange('A28:M28').format={font:{name:'Arial',size:12,bold:true,color:'#243746'},rowHeight:30};
for(const [a,v]of [['A30','Stock 1'],['B30','0600'],['D30','Stock 2'],['E30','0470'],['G30','Stock 3'],['H30','2706'],['J30','Stock 4'],['K30','9981'],['A33','From'],['B33',new Date('2021-01-01')],['D33','To'],['E33',new Date(peers.asof)]])put(l,a,v);
for(const a of ['B30','E30','H30','K30','B33','E33'])input(l,a);l.getRange('B33').setNumberFormat('dd-mmm-yy');l.getRange('E33').setNumberFormat('dd-mmm-yy');
l.getRange('A54:M54').values=[['H code','Company','Sector','Cornerstones','IPO date','Last locked day','Pre 30 sessions','Post 30 sessions','CS % of offer','Since IPO %','Deal HK$m','Coverage','Filing']];head(l,'A54:M54');
const live=wb.worksheets.add('IPO Live');base(live,[['A',18],['B',30],['C',24],['D',14],['E',15],['F',2],['G',26],['H',15],['I',8],['J',16],['K',16],['L',16],['M',16],['N',16],['O',16]],'O');
live.getRange('A2:O2').format={font:{name:'Arial',size:15,bold:true,color:'#243746'},rowHeight:28,borders:{bottom:{style:'thin',color:'#A4B3BF'}}};
head(live,'A7:E7');head(live,'G5:I5');head(live,'G36:I36');input(live,'B5');input(live,'H34');live.getRange('D8:D80').setNumberFormat('0.00');live.getRange('E8:E80').setNumberFormat('0.0%;(0.0%);0.0%');live.getRange('H6:H14').setNumberFormat('0.0%;(0.0%);0.0%');live.getRange('H37:H44').setNumberFormat('0.0%;(0.0%);0.0%');
const ah=wb.worksheets.add('AH');base(ah,[['A',11],['B',9],['C',14],['D',33],['E',12],['F',12],['G',13],['H',13],['I',2],['J',16],['K',16],['L',16],['M',16],['N',16],['O',16]],'O');
ah.getRange('A2:O2').format={font:{name:'Arial',size:15,bold:true,color:'#243746'},rowHeight:28,borders:{bottom:{style:'thin',color:'#A4B3BF'}}};head(ah,'A7:H7');input(ah,'B4');input(ah,'E4');ah.getRange('A7:H7').format.rowHeight=38;ah.getRange('E8:F80').setNumberFormat('0.0%;(0.0%);0.0%');ah.getRange('G8:H80').setNumberFormat('0.0" pp";(0.0" pp");0.0" pp"');
for(const [sh,end] of [[p,'H'],[l,'M'],[live,'O'],[ah,'O']]){
 sh.getRange(`A1:${end}1`).format.rowHeight=8;
 sh.getRange(`A2:${end}2`).format.font={name:'Arial',size:15,bold:true,color:'#202020'};
 sh.getRange(`A2:${end}2`).format.borders={bottom:{style:'thin',color:'#D71920'}};
}
wb.recalculate();console.log((await wb.inspect({kind:'table',range:'Peer Trades!A3:H13',tableMaxRows:11,tableMaxCols:8,maxChars:1000})).ndjson);
const out=await SpreadsheetFile.exportXlsx(wb),path=new URL('data/monitor_layout.xlsx',root).pathname;await out.save(path);await fs.writeFile(new URL('data/monitor_layout.json',root),JSON.stringify({version:1,xlsx_base64:(await fs.readFile(path)).toString('base64')}));await fs.unlink(path);console.log('Authored compact monitor layouts without merged cells');
