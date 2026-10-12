import fs from 'node:fs/promises';
export async function enhance(wb,ipo,ah,lock,chart,events,header){
 const doc=JSON.parse(await fs.readFile(new URL('../data/desk_chart_data.json',import.meta.url),'utf8')), pairs=doc.pairs, peer=doc.peer;
 const ec=n=>{let a='';while(n){n--;a=String.fromCharCode(65+n%26)+a;n=Math.floor(n/26)}return a};
 const C=['#1F4E79','#758D50','#8E6949','#706080'];
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
  if(k){put(ah,'J'+(27+k),'Compare '+(k+1));put(ah,'K'+(27+k),p.code);ah.getRange('K'+(27+k)).dataValidation={rule:{type:'list',values:pairs.map(x=>x.code)}};ah.getRange('K'+(27+k)).format.font.color='#0000FF';}
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
 for(let k=0;k<4;k++){put(lock,`A${32+k}`,'Stock '+(k+1));put(lock,`B${32+k}`,defaults[k]||codes[k]);lock.getRange(`B${32+k}`).dataValidation={rule:{type:'list',values:codes}};lock.getRange(`B${32+k}`).format.font.color='#0000FF';}
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
 // Direct peers: live quotes and an independently selected live/stored graph.
 const ps=wb.worksheets.add('Peer Trades'),pd=wb.worksheets.add('Peer Data'),pl=wb.worksheets.add('Peer Live'),pc=wb.worksheets.add('Peer Chart');
 ps.showGridLines=false;ps.getRange('A1:M65').format.font={name:'Arial',size:11,color:'#111111'};ps.getRange('A1:M65').format.rowHeight=22;
 put(ps,'A2','Direct peer monitor');ps.getRange('A2').format.font={name:'Arial',size:14,bold:true};put(ps,'A4','Pair');put(ps,'B4',peer.pairs[0].id);put(ps,'D4','Chart source');put(ps,'E4','Stored');ps.getRange('B4').dataValidation={rule:{type:'list',values:peer.pairs.map(x=>x.id)}};ps.getRange('E4').dataValidation={rule:{type:'list',values:['Stored','Bloomberg']}};ps.getRange('B4:E4').format.font.color='#0000FF';
 ps.getRange('A7:K7').values=[['Pair / product','Stock A','Stock B','Live A HK$','Live B HK$','A daily %','B daily %','A − B daily (pp)','A / B price','Snapshot spread (pp)','Snapshot date']];head(ps,'A7:K7');
 let pr=2;
 peer.pairs.forEach((p,i)=>{
  const r=i+8,start=pr;pd.getRange(`A${pr}:F${pr+p.history.length-1}`).values=p.history.map(h=>[new Date(h[0]+'T00:00:00Z'),...h.slice(1)]);pr+=p.history.length;
  pd.getRange(`H${i+3}:O${i+3}`).values=[[p.id,p.ticker_a,p.ticker_b,start,p.history.length,new Date(p.start+'T00:00:00Z'),p.history[0][1],p.history[0][2]]];
  ps.getRange(`A${r}:C${r}`).values=[[p.id+' · '+p.segment,p.name_a+' ('+p.code_a+')',p.name_b+' ('+p.code_b+')']];form(ps,`D${r}`,`=IF(B${r}="","",BDP("${p.ticker_a}","LAST_PRICE"))`);form(ps,`E${r}`,`=IF(C${r}="","",BDP("${p.ticker_b}","LAST_PRICE"))`);
  for(const [col,price,ticker]of [['F','D',p.ticker_a],['G','E',p.ticker_b]])form(ps,`${col}${r}`,`=IFERROR(IF(AND(ISNUMBER(${price}${r}),${price}${r}>0,BDP("${ticker}","PX_YEST_CLOSE")>0),${price}${r}/BDP("${ticker}","PX_YEST_CLOSE")-1,""),"")`);
  form(ps,`H${r}`,`=IF(AND(ISNUMBER(F${r}),ISNUMBER(G${r})),100*(F${r}-G${r}),"")`);form(ps,`I${r}`,`=IFERROR(IF(AND(ISNUMBER(D${r}),ISNUMBER(E${r}),E${r}>0),D${r}/E${r},""),"")`);put(ps,`J${r}`,100*p.history.at(-1)[5]);put(ps,`K${r}`,new Date(p.latest_date+'T00:00:00Z'));
  put(ps,`A${57+i}`,p.id+' · '+p.watch);ps.getRange(`A${57+i}:K${57+i}`).merge();
 });
 ps.getRange('D8:E13').setNumberFormat('0.00');ps.getRange('F8:G13').setNumberFormat('0.0%');ps.getRange('H8:H13').setNumberFormat('0.0" pp"');ps.getRange('J8:J13').setNumberFormat('0.0" pp"');ps.getRange('K8:K13').setNumberFormat('dd-mmm-yyyy');change(ps,'F8:H13');change(ps,'J8:J13');
 for(const [c,w]of [['A',26],['B',25],['C',25],['D',13],['E',13],['F',13],['G',13],['H',18],['I',12],['J',19],['K',18]])ps.getRange(`${c}:${c}`).format.columnWidth=w;
 put(ps,'A15','Spread = A return minus B return, rebased to the first common observed session.');ps.getRange('A15:K15').merge();put(ps,'A54',`Stored prices through ${peer.asof}; Bloomberg quotes and histories refresh on the terminal.`);ps.getRange('A54:K54').merge();put(ps,'A55','Price performance excludes dividends and rights value. Product peers have different exposures.');ps.getRange('A55:K55').merge();
 form(pc,'H2',`=IFERROR(MATCH('Peer Trades'!$B$4,'Peer Data'!$H$3:$H$8,0),0)`);const pm=c=>`IFERROR(INDEX('Peer Data'!$${c}$3:$${c}$8,$H$2),0)`;
 for(const [col,c]of [['A','I'],['D','J']])form(pl,`${col}5`,`=IF(OR('Peer Trades'!$E$4<>"Bloomberg",'Peer Chart'!$H$2=0),"",BDH(INDEX('Peer Data'!$${c}$3:$${c}$8,'Peer Chart'!$H$2),"PX_LAST",INDEX('Peer Data'!$M$3:$M$8,'Peer Chart'!$H$2),TODAY(),"Dts=S","Sort=A","Dir=V","Days=T","Per=cd","UseDPDF=N","CshAdjNormal=N","CshAdjAbnormal=N","CapChg=Y"))`);
 form(pc,'H3',`=IFERROR(INDEX('Peer Trades'!$B$8:$B$13,$H$2),"")`);form(pc,'H4',`=IFERROR(INDEX('Peer Trades'!$C$8:$C$13,$H$2),"")`);
 form(pc,'I2',`=IFERROR(IF(AND('Peer Trades'!$E$4="Bloomberg",$H$2>0,MIN('Peer Live'!$A$5:$A$1504)=${pm('M')},MIN('Peer Live'!$D$5:$D$1504)=${pm('M')},MAX('Peer Live'!$A$5:$A$1504)>=MIN(TODAY()-8,${new Date(peer.asof+'T00:00:00Z').getTime()/86400000+25569}),MAX('Peer Live'!$D$5:$D$1504)>=MIN(TODAY()-8,${new Date(peer.asof+'T00:00:00Z').getTime()/86400000+25569}),ABS(INDEX('Peer Live'!$B$5:$B$1504,MATCH(${pm('M')},'Peer Live'!$A$5:$A$1504,0))/${pm('N')}-1)<.005,ABS(INDEX('Peer Live'!$E$5:$E$1504,MATCH(${pm('M')},'Peer Live'!$D$5:$D$1504,0))/${pm('O')}-1)<.005),1,0),0)`);
 form(pc,'K2',`=IFERROR(IF(AND($I$2=1,MAX('Peer Live'!$A$5:$A$1504)<TODAY(),ISNUMBER(INDEX('Peer Trades'!$D$8:$D$13,$H$2)),ISNUMBER(INDEX('Peer Trades'!$E$8:$E$13,$H$2)),INDEX('Peer Trades'!$D$8:$D$13,$H$2)>0,INDEX('Peer Trades'!$E$8:$E$13,$H$2)>0),1,0),0)`);
 form(pc,'J2',`=MAX(1,IF('Peer Trades'!$E$4="Stored",${pm('L')},IF($I$2=1,COUNT('Peer Live'!$A$5:$A$1504)+$K$2,0)))`);
 pc.getRange('A4:F4').values=[['Date','Stock A return','Stock B return','Spread (pp)','A adjusted HK$','B adjusted HK$']];const rows=[];
 for(let r=5;r<7;r++){
  const n='(ROW()-4)',idx=`${pm('K')}+${n}-1`,ref=c=>`INDEX('Peer Data'!$${c}$2:$${c}$${pr-1},${idx}-1)`,la=c=>`INDEX('Peer Live'!$${c}$5:$${c}$1504,MATCH(${pm('M')},'Peer Live'!$A$5:$A$1504,0)+${n}-1)`,lb=`INDEX('Peer Live'!$E$5:$E$1504,MATCH(A${r},'Peer Live'!$D$5:$D$1504,0))`;
  rows.push([`=IFERROR(IF(${n}>$J$2,"",IF('Peer Trades'!$E$4="Stored",${ref('A')},IF($I$2=1,IF(${n}>COUNT('Peer Live'!$A$5:$A$1504),TODAY(),${la('A')}),""))),"")`,`=IFERROR(IF(ISNUMBER(A${r}),E${r}/IF('Peer Trades'!$E$4="Stored",${pm('N')},INDEX('Peer Live'!$B$5:$B$1504,MATCH(${pm('M')},'Peer Live'!$A$5:$A$1504,0)))-1,NA()),NA())`,`=IFERROR(IF(ISNUMBER(A${r}),F${r}/IF('Peer Trades'!$E$4="Stored",${pm('O')},INDEX('Peer Live'!$E$5:$E$1504,MATCH(${pm('M')},'Peer Live'!$D$5:$D$1504,0)))-1,NA()),NA())`,`=IFERROR(IF(AND(ISNUMBER(B${r}),ISNUMBER(C${r})),100*(B${r}-C${r}),NA()),NA())`,`=IFERROR(IF(ISNUMBER(A${r}),IF('Peer Trades'!$E$4="Stored",${ref('B')},IF(AND($K$2=1,${n}=$J$2),INDEX('Peer Trades'!$D$8:$D$13,$H$2),${la('B')})),NA()),NA())`,`=IFERROR(IF(ISNUMBER(A${r}),IF('Peer Trades'!$E$4="Stored",${ref('C')},IF(AND($K$2=1,${n}=$J$2),INDEX('Peer Trades'!$E$8:$E$13,$H$2),${lb})),NA()),NA())`]);
 }
 pc.getRange('A5:F6').formulas=rows;pc.getRange('A5:A1504').setNumberFormat('dd-mmm-yy');pc.getRange('B5:C1504').setNumberFormat('0.0%');pc.getRange('D5:D1504').setNumberFormat('0.0" pp"');
 const perf=ps.charts.add('line',pc.getRange('A4:C1504'));perf.title='Relative performance from common start';perf.setPosition('A17','K33');perf.hasLegend=true;perf.yAxis={numberFormatCode:'0.0%',numberFormatSourceLinked:false};perf.displayBlanksAs='gap';perf.series.items.forEach((s,k)=>s.line={fill:C[k],width:2});
 const spread=ps.charts.add('line',{from:{row:34,col:0},extent:{widthPx:1100,heightPx:360}});spread.title='A − B performance spread (pp)';spread.hasLegend=false;const ser=spread.series.add('Spread (pp)');ser.categoriesSource="'Peer Chart'!A5:A1504";ser.valuesSource="'Peer Chart'!D5:D1504";ser.line={fill:'#333333',width:2};spread.yAxis={numberFormatCode:'0.0" pp"',numberFormatSourceLinked:false};spread.displayBlanksAs='gap';ps.freezePanes.freezeRows(7);ps.freezePanes.freezeColumns(3);
 change(lock,`G${header+1}:H${header+events.length}`);change(lock,`J${header+1}:J${header+events.length}`);
}
