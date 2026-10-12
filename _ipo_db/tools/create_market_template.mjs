import {enhance} from './enhance_market_template.mjs';
import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const wb=Workbook.create();wb.worksheets.add('Market Data');wb.worksheets.add('AH History');
const ipo=wb.worksheets.add('IPO Live'),ah=wb.worksheets.add('AH'),lock=wb.worksheets.add('Lock-up'),chart=wb.worksheets.add('Chart Data'),lockData=wb.worksheets.add('Lock-up Data');
for(const s of [ipo,ah,lock,chart]){s.showGridLines=false;s.getRange('A1:Q80').format.font={name:'Arial',size:11,color:'#111111'};s.getRange('A1:Q80').format.rowHeight=22;}
function text(s,addr,val,bold=false,size=11){s.getRange(addr).values=[[val]];s.getRange(addr).format.font={name:'Arial',size,bold,color:'#111111'};}
text(ipo,'A2','IPO prices',true,14);text(ipo,'A4','Daily change versus previous trading-day close');
text(ipo,'A5','Classification',true);text(ipo,'B5','Sector');ipo.getRange('B5').dataValidation={rule:{type:'list',values:['Sector','Subsector']}};ipo.getRange('B5').format.font.color='#0000FF';
ipo.getRange('A7:E7').values=[['Bloomberg ticker','Company','Sector','Live price (HK$)','Daily change']];
ipo.getRange('G5:I5').values=[['Sector','Average change','Quotes']];
text(ipo,'G2','Sector averages',true,12);
for(const r of ['A7:E7','G5:I5'])ipo.getRange(r).format={fill:'#E6E6E6',font:{name:'Arial',size:11,bold:true,color:'#111111'},rowHeight:28,wrapText:true,borders:{bottom:{style:'thin',color:'#777777'}}};
for(const [c,w]of [['A',20],['B',27],['C',21],['D',18],['E',15],['F',3],['G',22],['H',17],['I',10],['J',3],['K',12],['L',12],['M',12],['N',12],['O',12]])ipo.getRange(`${c}:${c}`).format.columnWidth=w;
ipo.getRange('G6:H8').values=[['Technology',null],['Healthcare',null],['Consumer',null]];
const bar=ipo.charts.add('bar',ipo.getRange('G5:H8'));bar.title='Average daily change by sector';bar.hasLegend=false;bar.titleTextStyle.fontSize=12;bar.titleTextStyle.typeface='Arial';bar.setPosition('G17','O31');bar.series.items[0].fill='#505050';bar.xAxis={textStyle:{typeface:'Arial',fontSize:10}};bar.yAxis={numberFormatCode:'0.0%',numberFormatSourceLinked:false,textStyle:{typeface:'Arial',fontSize:10}};
text(ipo,'G33','Subsector averages',true,12);text(ipo,'G34','Choose sector',true);text(ipo,'H34','Technology');ipo.getRange('H34').format.font.color='#0000FF';
ipo.getRange('H34').dataValidation={rule:{type:'list',values:['Technology','Healthcare','Consumer','Financials','Industrials','Materials/Energy','Real Estate','Media & telecom','Other']}};
ipo.getRange('G36:I36').values=[['Subsector','Average change','Quotes']];ipo.getRange('G36:I36').format={fill:'#E6E6E6',font:{name:'Arial',size:11,bold:true,color:'#111111'},rowHeight:28,wrapText:true,borders:{bottom:{style:'thin',color:'#777777'}}};
ipo.getRange('G37:H39').values=[['Semiconductors',null],['Software & AI',null],['Hardware & electronics',null]];
const sub=ipo.charts.add('bar',ipo.getRange('G36:H39'));sub.title='Average daily change by subsector';sub.hasLegend=false;sub.titleTextStyle.fontSize=12;sub.titleTextStyle.typeface='Arial';sub.setPosition('G47','O62');sub.series.items[0].fill='#505050';sub.xAxis={textStyle:{typeface:'Arial',fontSize:10}};sub.yAxis={numberFormatCode:'0.0%',numberFormatSourceLinked:false,textStyle:{typeface:'Arial',fontSize:10}};
ipo.freezePanes.freezeRows(7);ipo.freezePanes.freezeColumns(2);
const lockBatch=JSON.parse(await fs.readFile(new URL('../data/batches/lockup_events.json',import.meta.url),'utf8')),events=lockBatch.events.filter(e=>e.category==='Cornerstone'&&e.date_basis!=='No cornerstone tranche');
const listingDates=new Map(JSON.parse(await fs.readFile(new URL('../data/deals.json',import.meta.url),'utf8')).deals.map(d=>[d.code,d.ipo_date]));
const stockCodes=[...new Set(events.map(e=>e.code))].sort(),eventEnd=7+events.length,sentinel=eventEnd+1,pathEnd=7+61*(events.length+1);
const eventLabel=e=>`${e.category} · ${e.last_day_locked||'date unavailable'}`;
const dt=s=>s?new Date(s+'T00:00:00Z'):null;
function autoEvent(code){
 const candidates=events.map((e,i)=>({e,i})).filter(x=>x.e.code===code),past=candidates.filter(x=>x.e.last_day_locked&&x.e.last_day_locked<=lockBatch.price_asof),cs=past.filter(x=>x.e.category==='Cornerstone');
 const pool=cs.length?cs:past.length?past:candidates;
 return pool.sort((a,b)=>(b.e.last_day_locked||'').localeCompare(a.e.last_day_locked||''))[0].i;
}
const firstEvent=events.filter(e=>e.category==='Cornerstone'&&e.windows?.['30 trading sessions']?.status==='Complete').sort((a,b)=>b.last_day_locked.localeCompare(a.last_day_locked))[0];
const initialCode=firstEvent?.code||stockCodes[0];
const sourceRows=events.map((e,i)=>{const t=e.windows?.['30 trading sessions']||{},c=e.windows?.['Calendar days']||{};return [t.pre_start_close??null,t.anchor_close??null,t.post_end_close??null,c.pre_start_close??null,c.anchor_close??null,c.post_end_close??null,t.status||e.date_basis,c.status||e.date_basis,null,e.code,e.name,e.sector,eventLabel(e),dt(e.last_day_locked),8+i*61,dt(t.pre_start),dt(t.anchor),dt(t.post_end),e.code+'|'+eventLabel(e),e.url||null];});
sourceRows.push([null,null,null,null,null,null,'Unknown H code',null,null,'','Unknown H code','', 'Select an event',null,8+events.length*61,null,null,null,'',null]);
lockData.getRange(`A8:T${sentinel}`).values=sourceRows;lockData.getRange(`U8:U${eventEnd}`).values=events.map((e,i)=>[i+8]);
lockData.getRange(`AA8:AA${eventEnd}`).values=events.map(e=>[dt(listingDates.get(e.code))]);lockData.getRange(`AA8:AA${eventEnd}`).setNumberFormat('dd-mmm-yyyy');
lockData.getRange(`N8:N${sentinel}`).setNumberFormat('dd-mmm-yyyy');lockData.getRange(`P8:R${sentinel}`).setNumberFormat('dd-mmm-yyyy');
const choices=[];for(const code of stockCodes){choices.push([code,'Auto']);for(const e of events.filter(e=>e.code===code))choices.push([code,eventLabel(e)]);}choices.push(['','Auto']);
const choiceEnd=7+choices.length;lockData.getRange(`V8:W${choiceEnd}`).values=choices;
lockData.getRange(`Y8:Z${7+stockCodes.length}`).values=stockCodes.map(code=>[code,8+autoEvent(code)]);
const pathRows=[];for(const e of [...events,null]){const byOffset=new Map((e?.windows?.['30 trading sessions']?.path||[]).map(p=>[p[0],p]));for(let offset=-30;offset<=30;offset++){const p=byOffset.get(offset);pathRows.push([offset,dt(p?.[1]),p?.[2]??null]);}}
lockData.getRange(`AB8:AD${pathEnd}`).values=pathRows;lockData.getRange(`AC8:AC${pathEnd}`).setNumberFormat('dd-mmm-yyyy');
lock.getRange('A2:I2').merge();text(lock,'A2','Cornerstone lock-up expiries',true,14);text(lock,'A4','H code',true);text(lock,'B4',initialCode);text(lock,'D4','Expiry event',true);lock.getRange('E4:I4').merge();text(lock,'E4','Auto');
for(const r of ['B4','E4:I4'])lock.getRange(r).format={fill:'#F2F2F2',font:{name:'Arial',size:11,color:'#0000FF'},borders:{bottom:{style:'thin',color:'#7F8C99'}}};
lock.getRange('B4').dataValidation={rule:{type:'list',formula1:`INDIRECT("'Lock-up Data'!$Y$8:$Y$${7+stockCodes.length}")`}};
lock.getRange('E4').dataValidation={rule:{type:'list',formula1:`INDIRECT("'Lock-up Data'!$W$"&($P$5+7)&":$W$"&($P$6+7))`}};
const helpers=[
 '=IFERROR(TEXT(VALUE($B$4),"0000"),"")',
 `=IFERROR(MATCH($P$2,'Lock-up Data'!$J$8:$J$${eventEnd},0),0)`,
 `=IFERROR(INDEX('Lock-up Data'!$Z$8:$Z$${7+stockCodes.length},MATCH($P$2,'Lock-up Data'!$Y$8:$Y$${7+stockCodes.length},0)),${sentinel})`,
 `=IFERROR(MATCH($P$2,'Lock-up Data'!$V$8:$V$${choiceEnd},0),${choices.length})`,
 `=$P$5+MAX(1,COUNTIFS('Lock-up Data'!$V$8:$V$${choiceEnd},$P$2))-1`,
 `=IF($E$4="Auto",$P$4,IF(COUNTIFS('Lock-up Data'!$J$8:$J$${eventEnd},$P$2,'Lock-up Data'!$M$8:$M$${eventEnd},$E$4)=1,SUMIFS('Lock-up Data'!$U$8:$U$${eventEnd},'Lock-up Data'!$J$8:$J$${eventEnd},$P$2,'Lock-up Data'!$M$8:$M$${eventEnd},$E$4),$P$4))`,
 `=IF($P$3=0,"Unknown H code. Select a code from B4.",IF(OR($E$4="Auto",COUNTIFS('Lock-up Data'!$J$8:$J$${eventEnd},$P$2,'Lock-up Data'!$M$8:$M$${eventEnd},$E$4)=1),"","Event choice unavailable for this stock. Auto event shown; choose an event in E4."))`,
 `=IFERROR(INDEX('Lock-up Data'!$B$8:$B$${sentinel},$P$7-7),0)`,
 `=IFERROR(INDEX('Lock-up Data'!$G$8:$G$${sentinel},$P$7-7),"Unknown H code")`,
 `=INDEX('Lock-up Data'!$O$8:$O$${sentinel},$P$7-7)`];
lock.getRange('P2:P11').formulas=helpers.map(f=>[f]);
for(const r of ['A5:I5','A6:I6','A25:I25','A26:I26'])lock.getRange(r).merge();
text(lock,'A5',`Prices through ${lockBatch.price_asof}. Day 0 = last HK trading session on/before the last locked day.`,false,10);
lock.getRange('A6').formulas=[['=IF($P$8="","Select an H code and expiry event. Auto follows the HTML event selection.",$P$8)']];
lock.getRange('A6:I6').format={font:{name:'Arial',size:10,color:'#555555'},wrapText:true,rowHeight:28};
const lookup=col=>`INDEX('Lock-up Data'!$${col}$8:$${col}$${sentinel},$P$7-7)`;
for(const r of ['A8:C9','A10:C11','A13:C13','A14:C14','A15:C15','A17:C17','A18:C18','A19:C19','A21:C21','A22:C22','A23:C24'])lock.getRange(r).merge();
lock.getRange('A8').formulas=[[`=${lookup('K')}`]];lock.getRange('A8:C9').format={font:{name:'Arial',size:14,bold:true,color:'#111111'},wrapText:true};
lock.getRange('A10').formulas=[[`=${lookup('M')}`]];lock.getRange('A10:C11').format={font:{name:'Arial',size:11,color:'#555555'},wrapText:true};
text(lock,'A13','30 trading sessions before',true,10);text(lock,'A17','30 trading sessions after',true,10);text(lock,'A21','Last day locked',true,10);
for(const [addr,start,finish]of [['A14','A','B'],['A18','B','C']]){const a=lookup(start),b=lookup(finish);lock.getRange(addr).formulas=[[`=IFERROR(IF(AND(ISNUMBER(${a}),${a}>0,ISNUMBER(${b}),${b}>0),${b}/${a}-1,""),"")`]];lock.getRange(addr+':C'+addr.slice(1)).format.font={name:'Arial',size:19,bold:true,color:'#111111'};lock.getRange(addr).setNumberFormat('0.0%;(0.0%);0.0%');}
for(const [addr,start,end]of [['A15','P','Q'],['A19','Q','R']])lock.getRange(addr).formulas=[[`=IF(AND(${lookup(start)}>0,${lookup(end)}>0),TEXT(${lookup(start)},"dd-mmm-yy")&" to "&TEXT(${lookup(end)},"dd-mmm-yy"),"Window unavailable / pending")`]];
lock.getRange('A22').formulas=[[`=IF(${lookup('N')}>0,${lookup('N')},"Expiry unconfirmed")`]];lock.getRange('A22').setNumberFormat('dd-mmm-yyyy');lock.getRange('A23').formulas=[['=$P$10']];lock.getRange('A23:C24').format.wrapText=true;
lock.getRange('A25').formulas=[[`=IF(${lookup('T')}=0,"",HYPERLINK(${lookup('T')},"Selected event: HKEX filing"))`]];
text(lock,'A26','Expiry unconfirmed: the available filing does not establish the date. Returns and charts stay blank.',false,10);
lock.getRange('A27:I27').merge();text(lock,'A27','Before = day 0 close / day −30 close − 1. After = day +30 close / day 0 close − 1.',false,10);
lock.getRange('A8:C24').format.horizontalAlignment='left';
lock.getRange('A12:C12').merge();lock.getRange('A12').formulas=[[`=IF(${lookup('AA')}>0,"IPO date: "&TEXT(${lookup('AA')},"dd-mmm-yyyy"),"")`]];lock.getRange('A12:C12').format.font={name:'Arial',size:10,color:'#555555'};
lock.getRange('A54:M54').values=[['H code','Company','Sector','Company cornerstones','IPO date','Last day locked','30 sessions before','30 sessions after','Cornerstone % of offer','Since IPO %','Deal size HK$m','Window status','Filing']];
lock.getRange('A54:M54').format={fill:'#E6E6E6',font:{name:'Arial',size:11,bold:true,color:'#111111'},rowHeight:32,wrapText:true,borders:{bottom:{style:'thin',color:'#777777'}}};
for(const [c,w]of [['A',12],['B',28],['C',19],['D',42],['E',18],['F',19],['G',15],['H',15],['I',18],['J',15],['K',17],['L',33],['M',12]])lock.getRange(`${c}:${c}`).format.columnWidth=w;
lock.freezePanes.freezeRows(7);lock.freezePanes.freezeColumns(2);
chart.getRange('K4:O4').values=[['Trading day','Price vs expiry reference','Day 0 reference','Date','Split-neutral H close']];
chart.getRange('K5:K65').values=Array.from({length:61},(_,i)=>[i-30]);
for(let r=5;r<=65;r++){
 const index=`'Lock-up'!$P$11+ROW()-5-7`;
 for(const [dest,src]of [['N','AC'],['O','AD']]){const v=`INDEX('Lock-up Data'!$${src}$8:$${src}$${pathEnd},${index})`;chart.getRange(`${dest}${r}`).formulas=[[`=IFERROR(IF(${v}>0,${v},NA()),NA())`]];}
 chart.getRange(`L${r}`).formulas=[[`=IFERROR(IF(AND(ISNUMBER(O${r}),O${r}>0,'Lock-up'!$P$9>0),O${r}/'Lock-up'!$P$9-1,NA()),NA())`]];
 chart.getRange(`M${r}`).formulas=[[`=IFERROR(IF(AND(ISNUMBER(N${r}),N${r}>0,'Lock-up'!$P$9>0),0,NA()),NA())`]];
}
chart.getRange('L5:M65').setNumberFormat('0.0%');chart.getRange('N5:N65').setNumberFormat('dd-mmm-yyyy');chart.getRange('O5:O65').setNumberFormat('0.0000');
const lockLine=lock.charts.add('line',chart.getRange('K4:M65'));lockLine.title='H price around lock-up expiry';lockLine.hasLegend=false;lockLine.titleTextStyle.fontSize=12;lockLine.titleTextStyle.typeface='Arial';lockLine.setPosition('D8','I24');lockLine.series.items[0].line={fill:'#303030',style:'solid',width:2};lockLine.series.items[1].line={fill:'#9A9A9A',style:'dashed',width:1};lockLine.xAxis={axisType:'textAxis',textStyle:{typeface:'Arial',fontSize:10}};lockLine.yAxis={numberFormatCode:'0.0%',numberFormatSourceLinked:false,textStyle:{typeface:'Arial',fontSize:10}};
text(ah,'A2','A/H premiums',true,14);text(ah,'A4','Chart stock',true);text(ah,'B4','3986');ah.getRange('B4').format.font.color='#0000FF';
text(ah,'D4','Price source',true);text(ah,'E4','Stored');ah.getRange('E4').format={fill:'#EAF2F8',font:{name:'Arial',size:11,color:'#0000FF'},borders:{bottom:{style:'thin',color:'#7F8C99'}}};
ah.getRange('A7:F7').values=[['A code','H code','Sector','Subsector','Premium at IPO','Premium latest']];
ah.getRange('A7:F7').format={fill:'#E6E6E6',font:{name:'Arial',size:11,bold:true,color:'#111111'},rowHeight:30,wrapText:true,borders:{bottom:{style:'thin',color:'#777777'}}};
for(const [c,w]of [['A',19],['B',19],['C',20],['D',28],['E',21],['F',21],['G',3],['H',12],['I',12],['J',12],['K',12],['L',12],['M',12],['N',12]])ah.getRange(`${c}:${c}`).format.columnWidth=w;
chart.getRange('A4:B7').values=[['Date','A premium'],[new Date('2026-01-13T00:00:00Z'),null],[new Date('2026-01-14T00:00:00Z'),null],[new Date('2026-01-15T00:00:00Z'),null]];
const line=ah.charts.add('line',chart.getRange('A4:B7'));line.title='A premium from H listing';line.hasLegend=false;line.titleTextStyle.fontSize=12;line.titleTextStyle.typeface='Arial';line.series.items[0].line={fill:'#303030',style:'solid',width:2};line.setPosition('H7','N23');line.xAxis={axisType:'textAxis',textStyle:{typeface:'Arial',fontSize:10}};line.yAxis={numberFormatCode:'0.0%',numberFormatSourceLinked:false,textStyle:{typeface:'Arial',fontSize:10}};
ah.freezePanes.freezeRows(7);ah.freezePanes.freezeColumns(2);
await enhance(wb,ipo,ah,lock,chart,events,54);

wb.recalculate();
console.log((await wb.inspect({kind:'region',sheetId:'Lock-up',range:'A4:I24',maxChars:2500,tableMaxRows:20,tableMaxCols:9})).ndjson);
console.log((await wb.inspect({kind:'match',sheetId:'Lock-up',range:'A1:I28',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!',options:{useRegex:true,maxResults:10},summary:'Lock-up output formula scan'})).ndjson);
const output=await SpreadsheetFile.exportXlsx(wb);const path=new URL('../data/market_views_template.xlsx',import.meta.url).pathname;await output.save(path);const bytes=await fs.readFile(path);await fs.writeFile(new URL('../data/market_views_template.json',import.meta.url),JSON.stringify({version:8,lockup_layout:{event_count:events.length,stock_count:stockCodes.length,choice_count:choices.length,table_header:54},xlsx_base64:bytes.toString('base64')}));await fs.unlink(path);console.log('Saved daily monitor controls and selectable native lock-up chart');
// The preview engine lacks HYPERLINK. Keep the native formula in the saved
// template, then show its friendly label in this disposable rendering only.
lock.getRange('A25').values=[['Selected event: HKEX filing']];
await fs.mkdir(new URL('../out/',import.meta.url),{recursive:true});const preview=await wb.render({sheetName:'Lock-up',range:'A1:M55',scale:1.2,format:'png'});await fs.writeFile(new URL('../out/lockup_excel_preview.png',import.meta.url),new Uint8Array(await preview.arrayBuffer()));
