import fs from 'node:fs/promises';
export async function enhance(wb,ipo,ah,lock,chart,events,header){
 const doc=JSON.parse(await fs.readFile(new URL('../data/desk_chart_data.json',import.meta.url),'utf8')), pairs=doc.pairs, peer=doc.peer;
 const ec=n=>{let a='';while(n){n--;a=String.fromCharCode(65+n%26)+a;n=Math.floor(n/26)}return a};
 const C=['#315B7D','#9B4A47','#657480','#927D54'];
 const put=(s,a,v)=>{s.getRange(a).values=[[v]];},form=(s,a,f)=>{s.getRange(a).formulas=[[f]];};
 const head=(s,a)=>s.getRange(a).format={fill:'#E6E6E6',font:{name:'Arial',size:11,bold:true,color:'#111111'},rowHeight:30,wrapText:true,borders:{bottom:{style:'thin',color:'#777777'}}};
 const change=(s,a)=>{s.getRange(a).conditionalFormats.add('cellIs',{operator:'greaterThan',formula:0,format:{font:{color:'#217346'},fill:'#E8F2EA'}});s.getRange(a).conditionalFormats.add('cellIs',{operator:'lessThan',formula:0,format:{font:{color:'#B53939'},fill:'#F6E8E8'}});};
 change(ipo,`E8:E${7+doc.listed_count}`);change(ipo,'H6:H14');change(ipo,'H37:H44');
 ah.getRange('G7:H7').values=[['7-day change (pp)','1-month change (pp)']];head(ah,'A7:H7');ah.getRange('G:H').format.columnWidth=19;ah.getRange('I:I').format.columnWidth=3;
 ah.charts.items[0].setPosition('J7','O23');change(ah,`F8:H${7+pairs.length}`);ah.getRange(`G8:H${7+pairs.length}`).setNumberFormat('0.0" pp";(0.0" pp");0.0" pp"');
 const delta=wb.worksheets.add('AH Delta'),recent=wb.worksheets.add('AH Recent');delta.getRange('A2:N2').values=[['H code','Stored 7-day reference','Stored month reference','7-day reference','Month reference','IPO date','Raw debut','Cache start','Cache rows','H ex1','A ex1','H ex2','A ex2','History through']];
 const rawOptions=',"Dts=S","Dir=V","Sort=A","Days=T","Per=cd","UseDPDF=N","CshAdjNormal=N","CshAdjAbnormal=N","CapChg=N"';
 for(let i=0;i<pairs.length;i++){
  const p=pairs[i],r=i+3,start=i*70+5,end=start+64,rv=r+5,evs=p.review?.events|| (p.review?[p.review]:[]);
  delta.getRange(`A${r}:N${r}`).values=[[p.code,p.stored_7,p.stored_1m,null,null,new Date(p.ipo_date+'T00:00:00Z'),p.raw_debut,p.cache_start,p.cache_rows,...[0,1].flatMap(k=>[evs[k]?.h_ex_date?new Date(evs[k].h_ex_date+'T00:00:00Z'):null,evs[k]?.a_ex_date?new Date(evs[k].a_ex_date+'T00:00:00Z'):null]),p.latest_date?new Date(p.latest_date+'T00:00:00Z'):null]];
  for(const [col,ticker]of [['A',p.h_ticker],['D',p.a_ticker],['G','CNYHKD Curncy']])form(recent,`${col}${start}`,`=IF(AH!$E$4<>"Bloomberg","",BDH("${ticker}","PX_LAST",TODAY()-55,TODAY()${col==='G'?rawOptions.split(',"UseDPDF')[0]:rawOptions}))`);
  for(const [dest,target,stored]of [['D','TODAY()-7','B'],['E','EDATE(TODAY(),-1)','C']]){
   const hdt=`INDEX('AH Recent'!$A$${start}:$A$${end},MATCH(${target},'AH Recent'!$A$${start}:$A$${end},1))`, h=`INDEX('AH Recent'!$B$${start}:$B$${end},MATCH(${target},'AH Recent'!$A$${start}:$A$${end},1))`;
   const val=(d,v)=>`INDEX('AH Recent'!$${v}$${start}:$${v}$${end},MATCH(${hdt},'AH Recent'!$${d}$${start}:$${d}$${end},1))`,a=val('D','E'),fx=val('G','H'),ad=val('D','D'),fd=val('G','G');
   const basis=[['J','K'],['L','M']].map(([x,y])=>`OR($${x}${r}=0,(${hdt}>=$${x}${r})=(${ad}>=$${y}${r}))`).join(',');
   form(delta,`${dest}${r}`,`=IF(AH!$E$4="Stored",IF(ISNUMBER(${stored}${r}),${stored}${r},""),IFERROR(IF(AND(ISNUMBER(${hdt}),${target}-${hdt}<=10,${h}>0,${a}>0,${fx}>0,${hdt}-${ad}<=10,${hdt}-${fd}<=5,${basis}),${a}*${fx}/${h}-1,""),""))`);
  }
  for(const [col,ref]of [['G','D'],['H','E']])form(ah,`${col}${rv}`,`=IFERROR(IF(AND(ISNUMBER(F${rv}),ISNUMBER('AH Delta'!${ref}${r})),100*(F${rv}-'AH Delta'!${ref}${r}),""),"")`);
 }
 // Four selectable A/H histories. Each series owns a date range; no long blank axis.
 const cmp=wb.worksheets.add('AH Compare'),live=wb.worksheets.add('AH Compare Live');put(ah,'J27','Compare premium histories');ah.getRange('J27:O27').format.font={name:'Arial',size:12,bold:true};
 for(let k=0;k<4;k++){
  const selector=k?'AH!$K$'+(27+k):'AH!$B$4',p=pairs.find(p=>p.code==['3986','3308','3759','3347'][k])||pairs[k];
  if(k){put(ah,'J'+(27+k),'Compare '+(k+1));put(ah,'K'+(27+k),p.code);ah.getRange('K'+(27+k)).dataValidation={rule:{type:'list',formula1:`INDIRECT("'AH Delta'!$A$3:$A$${pairs.length+2}")`}};ah.getRange('K'+(27+k)).format.font.color='#0000FF';}
  const cs=k*9,cols=Array.from({length:9},(_,j)=>ec(cs+j+1)), [d,h,a,f,ad,fd,prem,helper,valid]=cols;
  // Metadata selection is independently validated, including security and last snapshot date.
  const idx=`IFERROR(MATCH(TEXT(VALUE(${selector}),"0000"),'AH Delta'!$A$3:$A$${pairs.length+2},0),0)`,m=c=>`IFERROR(INDEX('AH Delta'!$${c}$3:$${c}$${pairs.length+2},$${helper}$2),0)`;
  form(cmp,`${helper}2`,k?'='+idx:'=AH!$P$3');form(cmp,`${helper}3`,'='+m('I'));form(cmp,`${helper}4`,'='+m('H'));
  const lcol=['A','J','S','AB'][k],acol=['D','M','V','AE'][k],fcol=['G','P','Y','AH'][k],ncol=s=>s.length===1?String.fromCharCode(s.charCodeAt(0)+1):s[0]+String.fromCharCode(s.charCodeAt(1)+1);
  const ht=`INDEX('Market Data'!$Q$3:$Q$${pairs.length+2},'AH Compare'!$${helper}$2)`,at=`IFERROR(INDEX('Market Data'!$R$3:$R$${pairs.length+2},$${helper}$2),"")`,ipo=m('F');
  const liveIPO=`INDEX('AH Delta'!$F$3:$F$${pairs.length+2},'AH Compare'!$${helper}$2)`,liveAT=`INDEX('Market Data'!$R$3:$R$${pairs.length+2},'AH Compare'!$${helper}$2)`;
  for(const [dest,tk,from]of [[lcol,ht,liveIPO],[acol,liveAT,liveIPO+'-31'],[fcol,'"CNYHKD Curncy"',liveIPO+'-31']])form(live,`${dest}5`,`=IF(OR(AH!$E$4<>"Bloomberg",'AH Compare'!$${helper}$2=0),"",BDH(${tk},"PX_LAST",${from},TODAY()${dest===fcol?rawOptions.split(',"UseDPDF')[0]:rawOptions}))`);
  const L=c=>`'AH Compare Live'!$${c}$5:$${c}$3004`,lH=L(lcol),lHp=L(ncol(lcol));
  form(cmp,`${valid}2`,`=IFERROR(IF(AND(AH!$E$4="Bloomberg",$${helper}$2>0,COUNT(${lH})>0,MIN(${lH})=${ipo},MAX(${lH})>=MIN(TODAY()-8,${m('N')}),ABS(INDEX(${lHp},MATCH(${ipo},${lH},0))-${m('G')})<=MAX(.005,${m('G')}*.0005)),1,0),0)`);
  form(cmp,`${valid}3`,`=MAX(1,IF(AH!$E$4="Stored",$${helper}$3,IF($${valid}$2=1,COUNT(${lH})+IF(AND(MAX(${lH})<TODAY(),ISNUMBER(INDEX('Market Data'!$AE$3:$AE$${pairs.length+2},$${helper}$2))),1,0),0)))`);
  const rows=[];
  for(let rr=5;rr<7;rr++){
   const off='(ROW()-5)',cache=`$${helper}$4+${off}`,cur=`$${d}${rr}`,inc=col=>`INDEX('AH History'!$${col}$1:$${col}$${doc.ah_cache_end},${cache})`,liveval=(dc,vc)=>`INDEX(${L(vc)},MATCH(${cur},${L(dc)},1))`,basis=[['J','K'],['L','M']].map(([x,y])=>`OR(${m(x)}=0,(${cur}>=${m(x)})=($${ad}${rr}>=${m(y)}))`).join(',');
   rows.push([`=IFERROR(IF(OR($${helper}$2=0,${off}+1>$${valid}$3),"",IF(AH!$E$4="Stored",${inc('A')},IF($${valid}$2=1,IF(${off}+1>COUNT(${lH}),TODAY(),INDEX(${lH},MATCH(${m('F')},${lH},0)+${off})),""))),"")`,...[[h,lcol,ncol(lcol),'B'],[a,acol,ncol(acol),'C'],[f,fcol,ncol(fcol),'D'],[ad,acol,acol,'E'],[fd,fcol,fcol,'F']].map(([dest,dc,vc,cc])=>`=IFERROR(IF(ISNUMBER(${cur}),IF(AH!$E$4="Stored",${inc(cc)},IF(${off}+1>COUNT(${lH}),${dest===h?`INDEX('Market Data'!$AD$3:$AD$${pairs.length+2},$${helper}$2)`:dest===a?`INDEX('Market Data'!$AC$3:$AC$${pairs.length+2},$${helper}$2)`:dest===f?`INDEX('Market Data'!$AK$3:$AK$${pairs.length+2},$${helper}$2)`:'TODAY()'},${liveval(dc,vc)})),NA()),NA())`),`=IFERROR(IF(AND(ISNUMBER(${cur}),$${h}${rr}>0,$${a}${rr}>0,$${f}${rr}>0,${cur}-$${ad}${rr}<=10,${cur}-$${fd}${rr}<=5,${basis}),$${a}${rr}*$${f}${rr}/$${h}${rr}-1,NA()),NA())`]);
  }
  cmp.getRange(`${d}5:${prem}6`).formulas=rows;
 }
 const ach=ah.charts.add('scatter',{from:{row:34,col:9},extent:{widthPx:650,heightPx:360}});ach.setPosition('J35','O54');ach.title='Selected A/H premiums';ach.hasLegend=true;ach.titleTextStyle.fontSize=12;ach.xAxis={numberFormatCode:'mmm-yy',numberFormatSourceLinked:false};ach.yAxis={numberFormatCode:'0.0%',numberFormatSourceLinked:false};ach.displayBlanksAs='gap';
 for(let k=0;k<4;k++){let c=k*9;const s=ach.series.add(['Primary','Compare 2','Compare 3','Compare 4'][k]);s.categoriesSource=`'AH Compare'!${ec(c+1)}5:${ec(c+1)}3004`;s.valuesSource=`'AH Compare'!${ec(c+7)}5:${ec(c+7)}3004`;s.line={fill:C[k],width:1.7};}
 put(ah,'J55','7 days / 1 calendar month; changes in premium percentage points.');ah.getRange('J55:O56').merge();ah.getRange('J55:O56').format={wrapText:true,font:{name:'Arial',size:10,color:'#555555'}};
 // Event-range cohort and four stock curves, all normalized at their own expiry.
 const lc=wb.worksheets.add('Lock Compare'),mx=wb.worksheets.add('Lock Matrix');
 const er=events.length+7;mx.getRange(`A8:BK${er}`).values=events.map(e=>{const w=e.windows?.['30 trading sessions']||{},points=new Map((w.path||[]).map(p=>[p[0],p[2]]));return [e.code,e.last_day_locked?new Date(e.last_day_locked+'T00:00:00Z'):null,...Array.from({length:61},(_,i)=>points.get(i-30)>0&&w.anchor_close>0?points.get(i-30)/w.anchor_close-1:null)];});
 put(lock,'A30','Compare stocks / expiry cohort');lock.getRange('A30:C30').format.font={name:'Arial',size:12,bold:true};
 const codes=[...new Set(events.map(e=>e.code))].sort(),defaults=events.filter(e=>e.windows?.['30 trading sessions']?.status==='Complete').slice(-4).map(e=>e.code);
 for(let k=0;k<4;k++){put(lock,`A${32+k}`,'Stock '+(k+1));put(lock,`B${32+k}`,defaults[k]||codes[k]);lock.getRange(`B${32+k}`).dataValidation={rule:{type:'list',formula1:`INDIRECT("'Lock-up Data'!$Y$8:$Y$${7+codes.length}")`}};lock.getRange(`B${32+k}`).format.font.color='#0000FF';}
 put(lock,'A37','Expiry from');put(lock,'B37',new Date('2021-01-01T00:00:00Z'));put(lock,'A38','Expiry to');put(lock,'B38',new Date(peer.asof+'T00:00:00Z'));lock.getRange('B37:B38').setNumberFormat('dd-mmm-yyyy');put(lock,'A40','Cohort = equal-weight mean of');put(lock,'A41','available curves in the date range.');put(lock,'A42','Blank endpoints stay unavailable.');
 lc.getRange('A4:F4').values=[['Trading session','Cohort mean','Stock 1','Stock 2','Stock 3','Stock 4']];
 for(let i=0;i<61;i++){
  const r=i+5,col=(n)=>{let a='';while(n){n--;a=String.fromCharCode(65+n%26)+a;n=Math.floor(n/26)}return a},mc=col(i+3);put(lc,`A${r}`,i-30);
  form(lc,`B${r}`,`=IFERROR(AVERAGEIFS('Lock Matrix'!${mc}8:${mc}${er},'Lock Matrix'!$B$8:$B$${er},">="&'Lock-up'!$B$37,'Lock Matrix'!$B$8:$B$${er},"<="&'Lock-up'!$B$38),NA())`);
  for(let k=0;k<4;k++){
   const code=`TEXT(VALUE('Lock-up'!$B$${32+k}),"0000")`,ix=`INDEX('Lock-up Data'!$Z$8:$Z$${7+codes.length},MATCH(${code},'Lock-up Data'!$Y$8:$Y$${7+codes.length},0))-7`,v=`INDEX('Lock Matrix'!${mc}8:${mc}${er},${ix})`;
   form(lc,`${col(k+3)}${r}`,`=IFERROR(IF(COUNT(INDEX('Lock Matrix'!${mc}8:${mc}${er},${ix}))>0,${v},NA()),NA())`);
  }
 }
 const lchart=lock.charts.add('line',lc.getRange('A4:F65'));lchart.title='Performance around lock-up expiry';lchart.hasLegend=true;lchart.setPosition('D30','M50');lchart.yAxis={numberFormatCode:'0.0%',numberFormatSourceLinked:false};lchart.displayBlanksAs='gap';lchart.series.items.forEach((s,k)=>s.line={fill:k?C[k-1]:'#333333',width:k?1.4:2.5});
 await buildPeers(wb,doc);
 change(lock,`G${header+1}:H${header+events.length}`);change(lock,`J${header+1}:J${header+events.length}`);
}

export async function buildPeers(wb,doc){
 const peer=doc.peer;
 const ec=n=>{let a='';while(n){n--;a=String.fromCharCode(65+n%26)+a;n=Math.floor(n/26)}return a};
 const C=['#315B7D','#9B4A47','#657480','#927D54'];
 const put=(s,a,v)=>{s.getRange(a).values=[[v]];},form=(s,a,f)=>{s.getRange(a).formulas=[[f]];};
 const head=(s,a)=>s.getRange(a).format={fill:'#E6E6E6',font:{name:'Arial',size:11,bold:true,color:'#111111'},rowHeight:30,wrapText:true,borders:{bottom:{style:'thin',color:'#777777'}}};
 const change=(s,a)=>{s.getRange(a).conditionalFormats.add('cellIs',{operator:'greaterThan',formula:0,format:{font:{color:'#217346'},fill:'#E8F2EA'}});s.getRange(a).conditionalFormats.add('cellIs',{operator:'lessThan',formula:0,format:{font:{color:'#B53939'},fill:'#F6E8E8'}});};
 // One named pair selector populates both securities. Only its histories run.
 const ps=wb.worksheets.add('Peer Trades'),pd=wb.worksheets.add('Peer Data'),pl=wb.worksheets.add('Peer Live'),pc=wb.worksheets.add('Peer Chart'),un=wb.worksheets.add('HK Stocks');
 const catalog=JSON.parse(await fs.readFile(new URL('../data/hk_stock_universe.json',import.meta.url),'utf8')).stocks;
 un.getRange(`A2:C${catalog.length+1}`).values=catalog.map(x=>[x.code,x.name,x.currency]);
 ps.showGridLines=false;ps.getRange(`A1:L${54+peer.pairs.length}`).format={font:{name:'Arial',size:11,color:'#111111'},rowHeight:22};
 for(let i=1;i<=12;i++)ps.getRange(`${ec(i)}:${ec(i)}`).format.columnWidth=13;
 put(ps,'A2','Hong Kong product peers');ps.getRange('A2:L2').merge();ps.getRange('A2:L2').format={font:{name:'Arial',size:15,bold:true,color:'#202D39'},rowHeight:30,borders:{bottom:{style:'thin',color:'#8C99A5'}}};
 put(ps,'A3','Peer pair');put(ps,'B3',peer.pairs[0].label);ps.getRange('B3:L3').merge();ps.getRange('B3:L3').format={font:{name:'Arial',size:11,color:'#0000FF'},fill:'#F2F5F8',rowHeight:30,borders:{bottom:{style:'thin',color:'#8C99A5'}}};
 pd.getRange(`S3:W${peer.pairs.length+2}`).values=peer.pairs.map(p=>[p.label,p.code_a,p.code_b,p.segment,p.watch]);
 ps.getRange('B3').dataValidation={rule:{type:'list',formula1:`INDIRECT("'Peer Data'!$S$3:$S$${peer.pairs.length+2}")`}};
 for(const [a,v]of [['A4','Stock A code'],['B4','9856'],['D4','Stock B code'],['E4','3308'],['G4','Price source'],['H4','Stored'],['J4','Horizon'],['K4','1Y'],['A5','From'],['D5','Through'],['G5','Custom from'],['J5','Custom to']])put(ps,a,v);
 for(const [a,col] of [['B4','T'],['E4','U']])form(ps,a,`=IFERROR(INDEX('Peer Data'!$${col}$3:$${col}$${peer.pairs.length+2},MATCH($B$3,'Peer Data'!$S$3:$S$${peer.pairs.length+2},0)),"")`);
 ps.getRange('H4').dataValidation={rule:{type:'list',values:['Stored','Bloomberg']}};ps.getRange('K4').dataValidation={rule:{type:'list',values:['1M','3M','6M','1Y','3Y','5Y','Max','Custom']}};
 put(ps,'H5',new Date('2025-10-02T00:00:00Z'));put(ps,'K5',new Date(peer.asof+'T00:00:00Z'));
 form(ps,'E5',`=IF($K$4="Custom",$K$5,IF($H$4="Bloomberg",TODAY(),DATE(${peer.asof.split('-').map(Number).join(',')})))`);
 form(ps,'B5',`=IF($K$4="Custom",MAX($H$5,EDATE($E$5,-120)),IF($K$4="Max",EDATE($E$5,-120),EDATE($E$5,-INDEX({1,3,6,12,36,60},MATCH($K$4,{"1M","3M","6M","1Y","3Y","5Y"},0)))))`);
 for(const a of ['H4','K4','H5','K5'])ps.getRange(a).format={fill:'#F2F5F8',font:{color:'#0000FF'},borders:{bottom:{style:'thin',color:'#9AA6B0'}}};
 for(const a of ['B5','E5','H5','K5'])ps.getRange(a).setNumberFormat('dd-mmm-yy');
 form(ps,'A6',`=IFERROR(INDEX('Peer Data'!$V$3:$V$${peer.pairs.length+2},MATCH($B$3,'Peer Data'!$S$3:$S$${peer.pairs.length+2},0))&" | "&INDEX('Peer Data'!$W$3:$W$${peer.pairs.length+2},MATCH($B$3,'Peer Data'!$S$3:$S$${peer.pairs.length+2},0)),"")`);ps.getRange('A6:L6').merge();ps.getRange('A6:L6').format={font:{name:'Arial',size:10,color:'#657480'},rowHeight:28,wrapText:true};
 ps.getRange('A8:L8').values=[['Selected stock',null,null,'Price',null,'Currency','Daily change',null,'Window return',null,'Spread (pp)',null]];head(ps,'A8:L8');
 for(const r of [9,10])for(const a of [`A${r}:C${r}`,`D${r}:E${r}`,`G${r}:H${r}`,`I${r}:J${r}`,`K${r}:L${r}`])ps.getRange(a).merge();
 let pr=2;const stocks=peer.stocks,end=stocks.length+2;
 stocks.forEach((p,i)=>{pd.getRange(`A${pr}:B${pr+Math.min(2,p.history.length)-1}`).values=p.history.slice(0,2).map(h=>[new Date(h[0]+'T00:00:00Z'),h[1]]);pd.getRange(`H${i+3}:N${i+3}`).values=[[p.code,p.name,p.ticker,pr,p.history.length,new Date(p.history.at(-1)[0]+'T00:00:00Z'),p.currency]];pr+=p.history.length;});
 const m=(c,row)=>`IFERROR(IF($H$${row}>0,INDEX('Peer Data'!$${c}$3:$${c}$${end},$H$${row}),0),0)`,md=(c,row)=>`INDEX('Peer Data'!$${c}$1:$${c}$${pr-1},MAX(1,${m('K',row)})):INDEX('Peer Data'!$${c}$1:$${c}$${pr-1},MAX(1,${m('K',row)}+${m('L',row)}-1))`;
 for(const [r,inp,mr]of [[9,'B',2],[10,'E',5]]){
  const tk=`IFERROR(TEXT(VALUE($${inp}$4),"0")&" HK Equity","")`,ix=`MATCH(TEXT(VALUE($${inp}$4),"0000"),'HK Stocks'!$A$2:$A$${catalog.length+1},0)`,meta=c=>`IFERROR(IF('Peer Chart'!$H$${mr}>0,INDEX('Peer Data'!$${c}$3:$${c}$${end},'Peer Chart'!$H$${mr}),0),0)`;
  form(ps,`A${r}`,`=IFERROR(INDEX('HK Stocks'!$B$2:$B$${catalog.length+1},${ix})&" ("&TEXT(VALUE($${inp}$4),"0000")&")",IFERROR(TEXT(VALUE($${inp}$4),"0000")&" HK","Enter HK code"))`);
  form(ps,`D${r}`,`=IF($H$4="Bloomberg",IFERROR(BDP(${tk},"LAST_PRICE"),""),IFERROR(IF(${meta('L')}>0,INDEX('Peer Data'!$B$1:$B$${pr-1},${meta('K')}+${meta('L')}-1),""),""))`);
  form(ps,`F${r}`,`=IF($H$4="Bloomberg",IFERROR(BDP(${tk},"CRNCY"),""),IFERROR(INDEX('HK Stocks'!$C$2:$C$${catalog.length+1},${ix}),""))`);
  form(ps,`G${r}`,`=IFERROR(IF($H$4="Bloomberg",IF(AND(ISNUMBER(D${r}),BDP(${tk},"PX_YEST_CLOSE")>0),D${r}/BDP(${tk},"PX_YEST_CLOSE")-1,""),IF(${meta('L')}>1,INDEX('Peer Data'!$B$1:$B$${pr-1},${meta('K')}+${meta('L')}-1)/INDEX('Peer Data'!$B$1:$B$${pr-1},${meta('K')}+${meta('L')}-2)-1,"")),"")`);
  const rc=r===9?'B':'C';form(ps,`I${r}`,`=IFERROR(LOOKUP(2,1/(ISNUMBER('Peer Chart'!$${rc}$5:$${rc}$3004)),'Peer Chart'!$${rc}$5:$${rc}$3004),"")`);
 }
 for(const [label,target,mr]of [['A11','B11',2],['D11','E11',5]]){put(ps,label,mr===2?'A quote date':'B quote date');form(ps,target,`=IF($H$4="Stored",IFERROR(IF('Peer Chart'!$H$${mr}>0,INDEX('Peer Data'!$M$3:$M$${end},'Peer Chart'!$H$${mr}),""),""),"Live")`);ps.getRange(target).setNumberFormat('dd-mmm-yy');}
 form(ps,'D8',`=IF($H$4="Stored","Stored price","Live price")`);
 form(ps,'K9',`=IFERROR(LOOKUP(2,1/(ISNUMBER('Peer Chart'!$D$5:$D$3004)),'Peer Chart'!$D$5:$D$3004),"")`);put(ps,'K10','A return − B');
 form(ps,'A12',`=IF($B$5>$E$5,"Start date is after end date.",IF('Peer Chart'!$J$3=0,IF($H$4="Stored","No shared stored history for these codes / dates. Choose Bloomberg.","Bloomberg history unavailable. Refresh Bloomberg for this pair."),$H$4&" | actual shared dates "&TEXT(INDEX('Peer Chart'!$A$5:$A$3004,'Peer Chart'!$J$3-4),"dd-mmm-yy")&" to "&TEXT(LOOKUP(2,1/(ISNUMBER('Peer Chart'!$D$5:$D$3004)),'Peer Chart'!$A$5:$A$3004),"dd-mmm-yy")))`);ps.getRange('A12:L12').merge();
 put(ps,'A13','Split-adjusted price returns, excluding dividends. Same starting date; missing observations stay gaps.');ps.getRange('A13:L13').merge();ps.getRange('A12:L13').format.font={name:'Arial',size:10,color:'#555555'};
 ps.getRange('D9:E10').setNumberFormat('0.00');ps.getRange('G9:J10').setNumberFormat('0.0%');ps.getRange('K9').setNumberFormat('0.0" pp"');change(ps,'G9:J10');change(ps,'K9');
 form(pc,'H2',`=IFERROR(MATCH(TEXT(VALUE('Peer Trades'!$B$4),"0000"),'Peer Data'!$H$3:$H$${end},0),0)`);form(pc,'H5',`=IFERROR(MATCH(TEXT(VALUE('Peer Trades'!$E$4),"0000"),'Peer Data'!$H$3:$H$${end},0),0)`);
 form(pc,'H3',`='Peer Trades'!$A$9`);form(pc,'H4',`='Peer Trades'!$A$10`);form(pc,'I2',`='Peer Trades'!$B$5`);form(pc,'K2',`='Peer Trades'!$E$5`);
 for(const [col,inp]of [['A','B'],['D','E']])form(pl,`${col}5`,`=IF(OR('Peer Trades'!$H$4<>"Bloomberg",'Peer Trades'!$B$5>'Peer Trades'!$E$5),"",BDH(TEXT(VALUE('Peer Trades'!$${inp}$4),"0")&" HK Equity","PX_LAST",'Peer Trades'!$B$5,'Peer Trades'!$E$5,"Dts=S","Sort=A","Dir=V","Days=T","Per=cd","UseDPDF=N","CshAdjNormal=N","CshAdjAbnormal=N","CapChg=Y"))`);
 const sd=md('A',2),sp=md('B',2),td=md('A',5),tp=md('B',5),ld="'Peer Live'!$A$5:$A$3004",lp="'Peer Live'!$B$5:$B$3004",rd="'Peer Live'!$D$5:$D$3004",rp="'Peer Live'!$E$5:$E$3004";
 const mode="'Peer Trades'!$H$4=\"Stored\"",first=d=>`IFERROR(MATCH($I$2,${d},1)+IF(INDEX(${d},MATCH($I$2,${d},1))<$I$2,1,0),IFERROR(MATCH(MIN(${d}),${d},0),0))`;
 form(pc,'H6',`=IF(${mode},${first(sd)},${first(ld)})`);
 form(pc,'J2',`=MAX(1,IFERROR(IF(${mode},COUNTIFS(${sd},">="&$I$2,${sd},"<="&$K$2),COUNTIFS(${ld},">="&$I$2,${ld},"<="&$K$2)),0))`);form(pc,'J3',`=MIN($G$5:$G$3004)`);
 pc.getRange('A4:G4').values=[['Date','Stock A return','Stock B return','Spread (pp)','A adjusted close','B adjusted close','Shared-row index']];
 for(let r=5;r<=6;r++){
  const n='ROW()-5';form(pc,`A${r}`,`=IFERROR(IF(AND(${n}+1<=$J$2,$H$6>0,$I$2<=$K$2,OR('Peer Trades'!$H$4="Bloomberg",AND($H$2>0,$H$5>0))),IF(${mode},INDEX(${sd},$H$6+${n}),INDEX(${ld},$H$6+${n})),""),"")`);
  form(pc,`E${r}`,`=IFERROR(IF(ISNUMBER(A${r}),IF(${mode},INDEX(${sp},MATCH(A${r},${sd},0)),INDEX(${lp},MATCH(A${r},${ld},0))),NA()),NA())`);
  form(pc,`F${r}`,`=IFERROR(IF(ISNUMBER(A${r}),IF(${mode},INDEX(${tp},MATCH(A${r},${td},0)),INDEX(${rp},MATCH(A${r},${rd},0))),NA()),NA())`);
  form(pc,`G${r}`,`=IFERROR(IF(AND(ISNUMBER(A${r}),ISNUMBER(E${r}),ISNUMBER(F${r}),E${r}>0,F${r}>0),ROW(),""),"")`);
  for(const [col,price]of [['B','E'],['C','F']])form(pc,`${col}${r}`,`=IFERROR(IF(AND($J$3>0,ROW()>=$J$3,ISNUMBER(G${r})),${price}${r}/INDEX($${price}$5:$${price}$3004,$J$3-4)-1,NA()),NA())`);
  form(pc,`D${r}`,`=IFERROR(100*(B${r}-C${r}),NA())`);
 }
 pc.getRange('A5:A3004').setNumberFormat('dd-mmm-yy');pc.getRange('B5:C3004').setNumberFormat('0.0%');pc.getRange('D5:D3004').setNumberFormat('0.0" pp"');
 const perf=ps.charts.add('line',pc.getRange('A4:C3004'));perf.title='Price return';perf.setPosition('A15','F32');perf.hasLegend=true;perf.yAxis={numberFormatCode:'0.0%',numberFormatSourceLinked:false};perf.displayBlanksAs='gap';perf.series.items.forEach((s,k)=>s.line={fill:C[k],width:2});
 const spread=ps.charts.add('line',{from:{row:14,col:6},extent:{widthPx:530,heightPx:360}});spread.setPosition('G15','L32');spread.title='A − B return spread';spread.hasLegend=false;const ser=spread.series.add('Spread (pp)');ser.categoriesSource="'Peer Chart'!A5:A3004";ser.valuesSource="'Peer Chart'!D5:D3004";ser.line={fill:'#315B7D',width:2};spread.yAxis={numberFormatCode:'0.0" pp"',numberFormatSourceLinked:false};spread.displayBlanksAs='gap';
 for(const ch of [perf,spread]){ch.titleTextStyle.typeface='Arial';ch.titleTextStyle.fontSize=12;}
 put(ps,'A35',`${peer.pairs.length} product peer pairs`);ps.getRange('A35:L35').merge();ps.getRange('A35:L35').format={font:{name:'Arial',size:12,bold:true,color:'#202D39'},rowHeight:30};
 for(const [a,v] of [['A37','Product'],['D37','Company A'],['G37','Company B'],['J37','Key difference']])put(ps,a,v);
 for(const a of ['A37:C37','D37:F37','G37:I37','J37:L37'])ps.getRange(a).merge();head(ps,'A37:L37');
 for(let i=0;i<peer.pairs.length;i++){const p=peer.pairs[i],r=38+i;for(const [col,v]of [['A',p.segment],['D',p.name_a+' ('+p.code_a+')'],['G',p.name_b+' ('+p.code_b+')'],['J',p.watch]])put(ps,`${col}${r}`,v);for(const a of [`A${r}:C${r}`,`D${r}:F${r}`,`G${r}:I${r}`,`J${r}:L${r}`])ps.getRange(a).merge();ps.getRange(`A${r}:L${r}`).format={rowHeight:40,wrapText:true,font:{name:'Arial',size:11,color:'#202D39'},borders:{bottom:{style:'hair',color:'#CED6DD'}}};}
 ps.freezePanes.freezeColumns(2);

}
