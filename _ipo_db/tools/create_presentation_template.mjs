import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const root=new URL('../',import.meta.url),wb=Workbook.create();
const s=wb.worksheets.add('Lock-up'),ah=wb.worksheets.add('AH'),v=wb.worksheets.add('Screener'),input=wb.worksheets.add('Preview Inputs'),reference=wb.worksheets.add('AH Reference');
const batch=JSON.parse(await fs.readFile(new URL('data/batches/lockup_events.json',root),'utf8'));
const e=batch.events.find(e=>e.code==='2706'&&e.category==='Cornerstone'),w=e.windows['30 trading sessions'];
for(const sh of [s,ah,v]){sh.showGridLines=false;}
s.getRange('A1:M54').format={font:{name:'Arial',size:11,color:'#202D39'},rowHeight:22};
for(const [c,width] of [['A',11],['B',25],['C',18],['D',27],['E',14],['F',14],['G',14],['H',14],['I',13],['J',13],['K',16],['L',19],['M',9]])s.getRange(c+':'+c).format.columnWidth=width;
const put=(sh,a,x)=>sh.getRange(a).values=[[x]],merge=(sh,r)=>sh.getRange(r).merge();
merge(s,'A2:M2');put(s,'A2','Cornerstone lock-up expiries');s.getRange('A2:M2').format={font:{name:'Arial',size:15,bold:true,color:'#202D39'},rowHeight:28,borders:{bottom:{style:'thin',color:'#8C99A5'}}};
put(s,'A4','H code');put(s,'B4','2706');put(s,'D4','Expiry');merge(s,'E4:I4');put(s,'E4','Auto');
for(const r of ['B4','E4:I4'])s.getRange(r).format={fill:'#F2F5F8',font:{name:'Arial',size:11,color:'#0000FF'},borders:{bottom:{style:'thin',color:'#8C99A5'}}};
merge(s,'A5:I5');put(s,'A5','Prices through 02-Oct-2026. 30 HK trading sessions around expiry.');s.getRange('A5:I5').format.font={name:'Arial',size:10,color:'#657480'};
merge(s,'A6:I6');put(s,'A6','');s.getRange('A6:I6').format.font={name:'Arial',size:10,color:'#9D3333'};
for(const r of ['A8:C9','A10:C11','A12:C12','A13:C13','A14:C14','A15:C15','A17:C17','A18:C18','A19:C19','A21:C21','A22:C22','A23:C24','A25:C25'])merge(s,r);
put(s,'A8',e.name);s.getRange('A8:C9').format={font:{name:'Arial',size:14,bold:true,color:'#202D39'},wrapText:true};
put(s,'A10','Cornerstone expiry');s.getRange('A10:C12').format.font={name:'Arial',size:10,color:'#657480'};put(s,'A12','IPO 13-Feb-2026');
for(const [r,label] of [[13,'30 sessions before'],[17,'30 sessions after'],[21,'Last day locked']]){put(s,'A'+r,label);s.getRange(`A${r}:C${r}`).format={font:{name:'Arial',size:10,bold:true,color:'#526475'},borders:{top:{style:'thin',color:'#CED6DD'}}};}
input.getRange('A1:A3').values=[[w.pre_start_close],[w.anchor_close],[w.post_end_close]];
s.getRange('A14').formulas=[["='Preview Inputs'!A2/'Preview Inputs'!A1-1"]];s.getRange('A18').formulas=[["='Preview Inputs'!A3/'Preview Inputs'!A2-1"]];
for(const r of ['A14:C14','A18:C18'])s.getRange(r).format.font={name:'Arial',size:16,bold:true,color:'#202D39'};
s.getRange('A14').setNumberFormat('0.0%;(0.0%);0.0%');s.getRange('A18').setNumberFormat('0.0%;(0.0%);0.0%');
put(s,'A15',w.pre_start+' to '+w.anchor);put(s,'A19',w.anchor+' to '+w.post_end);s.getRange('A15:C15').format.font={name:'Arial',size:10,color:'#657480'};s.getRange('A19:C19').format.font={name:'Arial',size:10,color:'#657480'};
put(s,'A22',new Date(e.last_day_locked+'T00:00:00Z'));s.getRange('A22').setNumberFormat('dd-mmm-yyyy');s.getRange('A22:C22').format.font={name:'Arial',size:14,bold:true,color:'#202D39'};
put(s,'A23',w.status);put(s,'A25','HKEX filing');
put(s,'A30','Compare expiry performance');s.getRange('A30:C30').format.font={name:'Arial',size:12,bold:true,color:'#202D39'};
for(const [r,c] of [[32,'0600'],[33,'0470'],[34,'2706'],[35,'9981']]){put(s,'A'+r,'Stock '+(r-31));put(s,'B'+r,c);s.getRange('B'+r).format.font.color='#0000FF';}
put(s,'A37','Expiry from');put(s,'A38','Expiry to');put(s,'B37',new Date('2021-01-01'));put(s,'B38',new Date(batch.price_asof));s.getRange('B37:B38').setNumberFormat('dd-mmm-yyyy');
merge(s,'A40:C41');put(s,'A40','Day 0 = 0%. Cohort is equal-weight.');s.getRange('A40:C41').format={font:{name:'Arial',size:10,color:'#657480'},wrapText:true};
s.getRange('A54:M54').values=[['H code','Company','Sector','Cornerstones','IPO date','Last locked day','Pre 30 sessions','Post 30 sessions','CS % of offer','Since IPO %','Deal HK$m','Coverage','Filing']];
s.getRange('A54:M54').format={fill:'#E9EEF2',font:{name:'Arial',size:10,bold:true,color:'#202D39'},wrapText:true,rowHeight:32,borders:{bottom:{style:'thin',color:'#8C99A5'}}};
input.getRange('D1:E62').values=[['Session','Price return'],...w.path.map(x=>[x[0],x[2]?x[2]/w.anchor_close-1:null])];
const chart=s.charts.add('line',input.getRange('D1:E62'));chart.title='Price return around expiry';chart.hasLegend=false;chart.series.items[0].fill='#315B7D';chart.setPosition('D8','M25');chart.titleTextStyle.typeface='Arial';chart.titleTextStyle.fontSize=12;chart.yAxis={numberFormatCode:'0%',numberFormatSourceLinked:false};
ah.getRange('J63:O92').format={font:{name:'Arial',size:11,color:'#202D39'},rowHeight:22};merge(ah,'J63:O63');put(ah,'J63','A shares vs CSI 300 around H listing');ah.getRange('J63:O63').format.font.bold=true;
merge(ah,'J64:O64');put(ah,'J64','Both = 100 on the first common date.');ah.getRange('J64:O64').format.font={name:'Arial',size:10,color:'#657480'};
const ref=JSON.parse(await fs.readFile(new URL('data/ah_reference.json',root),'utf8')).pairs['3986'];
reference.getRange('A79:C79').values=[['Date','A shares','CSI 300']];reference.getRange(`A80:C${79+ref.rows.length}`).values=ref.rows.map(x=>[new Date(x[0]+'T00:00:00Z'),100*x[1]/ref.rows[0][1],100*x[2]/ref.rows[0][2]]);reference.getRange('A80:A149').setNumberFormat('dd-mmm-yy');
const c=ah.charts.add('line',reference.getRange(`A79:C${79+ref.rows.length}`));c.title='A shares and CSI 300';c.hasLegend=true;c.setPosition('J66','O86');c.titleTextStyle.typeface='Arial';c.titleTextStyle.fontSize=12;c.series.items[0].fill='#9B4A47';c.series.items[1].fill='#757F88';c.yAxis={numberFormatCode:'0',numberFormatSourceLinked:false};
for(const [a,label] of [['J88','Pre-IPO A'],['L88','CSI 300'],['N88','A − CSI (pp)']])put(ah,a,label);
put(ah,'J89',ref.pre_a_return_pct/100);put(ah,'L89',ref.pre_csi_return_pct/100);put(ah,'N89',ref.pre_excess_pp);ah.getRange('J89:M89').setNumberFormat('0.0%;(0.0%)');ah.getRange('N89').setNumberFormat('0.0');
merge(ah,'J91:O91');put(ah,'J91',ref.pre_from+' to '+ref.pre_to);ah.getRange('J91:O91').format.font={name:'Arial',size:10,color:'#657480'};
v.getRange('A63:D69').format={font:{name:'Arial',size:11,color:'#202D39'},rowHeight:23};
merge(v,'A63:D63');put(v,'A63','Live Bloomberg valuations');v.getRange('A63:D63').format.font.bold=true;merge(v,'A64:B64');put(v,'A64','Metric');put(v,'C64','A shares');put(v,'D64','H shares');v.getRange('A64:D64').format={fill:'#E9EEF2',font:{name:'Arial',size:10,bold:true,color:'#202D39'}};
for(const [row,label] of [[65,'NTM P/E'],[66,'FY2027 P/E'],[67,'TTM P/S'],[68,'FY2027 P/S']]){merge(v,`A${row}:B${row}`);put(v,'A'+row,label);v.getRange(`C${row}:D${row}`).setNumberFormat('0.0"x"');}
wb.recalculate();console.log((await wb.inspect({kind:'table',range:'Lock-up!A13:C22',tableMaxRows:10,tableMaxCols:3,maxChars:1400})).ndjson);
const out=await SpreadsheetFile.exportXlsx(wb),path=new URL('data/presentation_template.xlsx',root).pathname;await out.save(path);
await fs.writeFile(new URL('data/presentation_template.json',root),JSON.stringify({version:1,xlsx_base64:(await fs.readFile(path)).toString('base64')}));await fs.unlink(path);
const preview=await wb.render({sheetName:'Lock-up',range:'A1:M27',scale:1,format:'png'});await fs.writeFile(new URL('out/new_lockup_layout.png',root),new Uint8Array(await preview.arrayBuffer()));console.log('Saved bounded presentation template');
