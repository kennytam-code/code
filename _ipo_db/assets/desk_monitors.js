// Monitoring comparisons share the same dated observations as the workbook.
const deskColors=['#315b7d','#9b4a47','#55745d','#927d54','#6b617d','#397a80'];
const ahCompareColors=['#1D4E89','#16857A','#B17816','#6F5598','#B2505D','#486873'];
function deskLines(box,series,{offset=false,percent=true,label='Comparison'}={}){
 box.innerHTML='';const vals=series.flatMap(s=>s.points.filter(p=>Number.isFinite(p[1])).map(p=>p[1])),xs=series.flatMap(s=>s.points.map(p=>offset?p[0]:Date.parse(p[0]+'T00:00:00Z')).filter(Number.isFinite));
 if(!vals.length||!xs.length){box.innerHTML='<p class="note">No observed prices for this selection.</p>';return;}
 const W=fitW(box,900),H=340,M={l:66,r:22,t:20,b:44},minX=offset?-30:Math.min(...xs),maxX=offset?30:Math.max(...xs),lo=Math.min(0,...vals),hi=Math.max(0,...vals),pad=Math.max(1,(hi-lo)*.07),X=maxX===minX?()=>M.l+(W-M.r-M.l)/2:lin(minX,maxX,M.l,W-M.r),Y=lin(lo-pad,hi+pad,H-M.b,M.t);
 const svg=el('svg',{viewBox:`0 0 ${W} ${H}`,role:'img','aria-label':label,'data-series':series.length},box);
 niceTicks(lo-pad,hi+pad,5).forEach(v=>{el('line',{x1:M.l,x2:W-M.r,y1:Y(v),y2:Y(v),class:'gridline'},svg);const t=el('text',{x:M.l-8,y:Y(v)+4,'text-anchor':'end',class:'axlabel'},svg);t.textContent=v.toFixed(1)+(percent?'%':' pp');});
 for(let i=0;i<(maxX===minX?1:5);i++){const x=minX+(maxX-minX)*i/4,t=el('text',{x:X(x),y:H-14,'text-anchor':maxX===minX?'middle':i===0?'start':i===4?'end':'middle',class:'axlabel'},svg);t.textContent=offset?(x>0?'+':'')+Math.round(x)+' sessions':new Date(x).toISOString().slice(0,10);}
 el('line',{x1:M.l,x2:W-M.r,y1:Y(0),y2:Y(0),stroke:css('--mid')},svg);
 if(offset)el('line',{x1:X(0),x2:X(0),y1:M.t,y2:H-M.b,stroke:css('--mid'),'stroke-dasharray':'4 4'},svg);
 series.forEach((s,k)=>{let path='',started=false,last=null;const color=s.color||deskColors[k%deskColors.length];
  s.points.forEach(p=>{const x=offset?p[0]:Date.parse(p[0]+'T00:00:00Z');if(!Number.isFinite(p[1])){started=false;last=x;return;}if(!offset&&last!=null&&x-last>10*86400000)started=false;path+=`${started?'L':'M'}${X(x).toFixed(2)},${Y(p[1]).toFixed(2)} `;started=true;last=x;});
  const line=el('path',{d:path,fill:'none',stroke:color,'stroke-width':s.mean?2.7:2.2,'stroke-dasharray':s.dash||'none','stroke-linejoin':'round','stroke-linecap':'round',opacity:1,'data-name':s.name,'data-code':s.code||'','data-sector':s.sector||'','data-average':s.mean?'true':'false'},svg);
  const joined=(a,b)=>a&&b&&Number.isFinite(a[1])&&Number.isFinite(b[1])&&(offset||Date.parse(b[0])-Date.parse(a[0])<=10*86400000);
  s.points.forEach((p,i)=>{if(Number.isFinite(p[1])&&!joined(s.points[i-1],p)&&!joined(p,s.points[i+1]))el('circle',{cx:X(offset?p[0]:Date.parse(p[0]+'T00:00:00Z')),cy:Y(p[1]),r:2.8,fill:color,'data-isolated-point':'true','data-name':s.name},svg);});

 });
 const focus=el('line',{x1:0,x2:0,y1:M.t,y2:H-M.b,stroke:css('--mid'),'stroke-dasharray':'3 3',visibility:'hidden'},svg);
 svg.addEventListener('mousemove',ev=>{const rect=svg.getBoundingClientRect(),px=(ev.clientX-rect.left)*W/rect.width;if(px<M.l||px>W-M.r){focus.setAttribute('visibility','hidden');hideTT();return;}const v=minX+(px-M.l)/(W-M.r-M.l)*(maxX-minX),point=series.flatMap(s=>s.points).filter(p=>Number.isFinite(p[1])).reduce((b,p)=>Math.abs((offset?p[0]:Date.parse(p[0]))-v)<Math.abs((offset?b[0]:Date.parse(b[0]))-v)?p:b),at=offset?point[0]:Date.parse(point[0]);focus.setAttribute('x1',X(at));focus.setAttribute('x2',X(at));focus.setAttribute('visibility','visible');const rows=series.map((s,k)=>{const p=s.points.find(p=>(offset?p[0]:Date.parse(p[0]))===at);return `<span style="color:${s.color||deskColors[k%deskColors.length]}">${safeText(s.name)}</span>: ${p&&Number.isFinite(p[1])?p[1].toFixed(2)+(percent?'%':' pp'):'—'}${p&&p[2]!=null?' ('+p[2]+' '+(s.countUnit||'observations')+')':''}`;}).join('<br>');showTT(`<b>${offset?'Session ':''}${point[0]}</b>${rows}`,ev);});svg.addEventListener('mouseleave',()=>{focus.setAttribute('visibility','hidden');hideTT();});

 const legend=document.createElement('div');legend.className='legend comparison-legend';legend.innerHTML=series.map((s,k)=>`<span><span class="sw" style="height:0;width:24px;border-top:3px ${s.dash?'dashed':'solid'} ${s.color||deskColors[k%deskColors.length]};background:none"></span>${safeText(s.name)}</span>`).join('');box.appendChild(legend);
}
const ahComparisons=new Set(['3986','3308','3759']);
function validAHPoint(s,p){return Number.isFinite(p[4]);}
function adjustedAHPoint(s,p){const evs=s.entitlement_review?(s.entitlement_review.events||[s.entitlement_review]):[],af=evs.filter(e=>p[5]>=e.a_ex_date).reduce((v,e)=>v*e.ratio,1),hf=evs.filter(e=>p[0]>=e.h_ex_date).reduce((v,e)=>v*e.ratio,1);return 100*(p[2]*p[3]/p[1]*af/hf-1);}
function ahCompareWindow(){const h=$('#ah-compare-horizon').value,end=h==='Custom'?$('#ah-compare-to').value:DATA.ah_asof;if(h==='Custom')return[$('#ah-compare-from').value,end];if(h==='Max')return['1900-01-01',end];const months={'1M':1,'3M':3,'6M':6,'1Y':12,'3Y':36}[h],d=new Date(end+'T00:00:00Z'),day=d.getUTCDate();d.setUTCDate(1);d.setUTCMonth(d.getUTCMonth()-months);d.setUTCDate(Math.min(day,new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth()+1,0)).getUTCDate()));return[d.toISOString().slice(0,10),end];}
function averageSeries(series,name,color,offset=false){
 const sums=new Map();
 series.forEach(s=>s.points.forEach(p=>{if(!sums.has(p[0]))sums.set(p[0],[0,0]);if(Number.isFinite(p[1])){const v=sums.get(p[0]);v[0]+=p[1];v[1]++;}}));
 return {name,color,mean:true,points:[...sums].sort((a,b)=>offset?a[0]-b[0]:a[0].localeCompare(b[0])).map(([date,[sum,n]])=>[date,n?sum/n:null,n])};
}
function selectedAverages(series,bySector=false,offset=false){
 const groups=new Map();
 series.forEach(s=>{if(!groups.has(s.code))groups.set(s.code,[]);groups.get(s.code).push(s);});
 // Each selected stock has one weight, even with several selected expiry dates.
 const stocks=[...groups.values()].map(group=>({...averageSeries(group,group[0].name,null,offset),code:group[0].code,sector:group[0].sector,mean:false}));
 const overall={...averageSeries(stocks,'Selected average','#303A45',offset),countUnit:'stocks'};
 const sectors=bySector?[...new Set(stocks.map(s=>s.sector))].sort().map((sector,i)=>({...averageSeries(stocks.filter(s=>s.sector===sector),sector+' · selected average',deskColors[i%deskColors.length],offset),countUnit:'stocks'})):[];
 return {overall,sectors};
}
function ahSeries(d,from,to){
 const r=AHST[d.code]||{},by=new Map((r.history||[]).map(p=>[p[0],p]));
 return {name:d.name+' ('+d.code+')',code:d.code,sector:d.sector,points:(r.h_history||r.history||[]).filter(h=>h[0]>=from&&h[0]<=to).map(h=>{const p=by.get(h[0]);return[h[0],p&&!d.classReview&&validAHPoint(r,p)?adjustedAHPoint(r,p):null];})};
}
function sectorOptions(rows){return '<option value="">All sectors</option>'+[...new Set(rows.map(d=>d.sector).filter(Boolean))].sort().map(s=>`<option>${safeText(s)}</option>`).join('');}
// The active scope is applied to both raw lines and the average inputs.
const comparisonPages={ah:0,lockup:0},comparisonPageSize=6;
function ahScopeRows(){
 const sector=$('#ah-compare-sector').value,sub=$('#ah-sub').value;
 return ahDeals.filter(d=>(!sector||d.sector===sector)&&(!sub||d.subsector===sub));
}
function lockScopeRows(){
 const sector=$('#lockup-compare-sector').value,q=$('#lockup-q').value.trim();
 return LOCKUPS.map((e,i)=>({e,i})).filter(({e})=>(!sector||e.sector===sector)&&(!q||matchesDealSearch(deals.find(d=>d.code===e.code),q)));
}
function comparisonLines(stocks,mode,offset=false){
 if(mode==='stocks')return stocks;
 const means=selectedAverages(stocks,mode==='sector',offset);
 return mode==='sector'?means.sectors:[means.overall];
}
function renderComparisonPage(prefix,series,options){
 const available=series.filter(s=>s.points.some(p=>Number.isFinite(p[1]))),pages=Math.max(1,Math.ceil(available.length/comparisonPageSize));
 comparisonPages[prefix]=Math.max(0,Math.min(comparisonPages[prefix],pages-1));
 const start=comparisonPages[prefix]*comparisonPageSize,shown=available.slice(start,start+comparisonPageSize);
 $('#'+prefix+'-compare-pager').hidden=pages===1;
 $('#'+prefix+'-compare-prev').disabled=comparisonPages[prefix]===0;
 $('#'+prefix+'-compare-next').disabled=comparisonPages[prefix]===pages-1;
 $('#'+prefix+'-compare-page').textContent=available.length?`Lines ${start+1}–${start+shown.length} of ${available.length} · page ${comparisonPages[prefix]+1}/${pages}`:'No lines';
 const box=$('#'+prefix+'-compare-chart');
 const palette=prefix==='ah'?ahCompareColors:deskColors;
 deskLines(box,shown.map((s,i)=>({...s,color:s.mean&&available.length===1?'#303A45':palette[i%palette.length],dash:prefix==='ah'&&i>=3?'7 3':undefined})),options);
 const svg=$('#'+prefix+'-compare-chart svg');if(svg){svg.dataset.totalSeries=available.length;svg.dataset.page=comparisonPages[prefix]+1;}
 return {available,shown,svg};
}
$('#ah-compare-sector').innerHTML=sectorOptions(ahDeals);
function renderAHComparison(){
 const [from,to]=ahCompareWindow(),custom=$('#ah-compare-horizon').value==='Custom',mode=$('#ah-compare-mode').value;
 for(const id of ['from','to'])$('#ah-compare-'+id).disabled=!custom;
 if(!custom){$('#ah-compare-from').value=from==='1900-01-01'?'':from;$('#ah-compare-to').value=to;}
 const sector=$('#ah-compare-sector').value;
 $('#ah-select-sector').disabled=!sector;
 document.querySelectorAll('.ah-compare-pick').forEach(x=>x.checked=ahComparisons.has(x.dataset.code));
 if(!from||!to||from>to){$('#ah-compare-chart').innerHTML='';$('#ah-compare-pager').hidden=true;$('#ah-compare-count').textContent='Choose a valid date range.';return;}
 const rows=ahScopeRows().filter(d=>ahComparisons.has(d.code)).sort((a,b)=>a.code.localeCompare(b.code)),stocks=rows.map(d=>ahSeries(d,from,to));
 const series=comparisonLines(stocks,mode),{svg}=renderComparisonPage('ah',series,{label:mode==='stocks'?'Selected A/H premiums':mode==='average'?'Equal-weight premium of selected stocks':'Sector averages of selected stocks'});
 const observed=stocks.filter(s=>s.points.some(p=>Number.isFinite(p[1]))).length;
 $('#ah-compare-count').textContent=`${sector||'All sectors'} · ${rows.length} pairs selected · ${observed} with prices · ${from==='1900-01-01'?'since listing':from} to ${to}`;
 if(!rows.length)$('#ah-compare-chart').innerHTML='<p class="note">Select pairs in the table or use Select all.</p>';
 if(svg){svg.dataset.from=from;svg.dataset.to=to;svg.dataset.selected=rows.length;svg.dataset.averages=mode==='stocks'?0:series.length;svg.dataset.averageScope='selected';svg.dataset.sector=sector;svg.dataset.mode=mode;}
}
function selectAHScope(){ahComparisons.clear();ahScopeRows().forEach(d=>ahComparisons.add(d.code));comparisonPages.ah=0;renderAHComparison();}
$('#ah-tbl').addEventListener('change',ev=>{if(ev.target.matches('.ah-compare-pick')){const code=ev.target.dataset.code;ev.target.checked?ahComparisons.add(code):ahComparisons.delete(code);comparisonPages.ah=0;renderAHComparison();}});
$('#ah-select-all').addEventListener('click',selectAHScope);
$('#ah-select-sector').addEventListener('click',selectAHScope);
$('#ah-compare-sector').addEventListener('change',()=>{$('#ah-sec').value=$('#ah-compare-sector').value;fillAhSubs();redrawAHTab();selectAHScope();});
for(const id of ['ah-compare-horizon','ah-compare-from','ah-compare-to','ah-compare-mode'])$('#'+id).addEventListener('change',()=>{comparisonPages.ah=0;renderAHComparison();});
$('#ah-clear-compare').addEventListener('click',()=>{ahComparisons.clear();comparisonPages.ah=0;renderAHComparison();});
$('#ah-compare-prev').addEventListener('click',()=>{comparisonPages.ah--;renderAHComparison();});
$('#ah-compare-next').addEventListener('click',()=>{comparisonPages.ah++;renderAHComparison();});renderAHComparison();
const lockComparisons=new Set(LOCKUPS.map((e,i)=>i));
$('#lockup-compare-sector').innerHTML=sectorOptions(LOCKUPS);
function lockSeries(e){return {name:e.name+' ('+e.code+') · '+e.last_day_locked,code:e.code,sector:e.sector,points:e.window.path.map(p=>[p[0],Number.isFinite(p[2])?100*(p[2]/e.window.anchor_close-1):null])};}
function renderLockComparison(){
 const mode=$('#lockup-compare-mode').value,from=$('#lockup-compare-from').value,to=$('#lockup-compare-to').value,sector=$('#lockup-compare-sector').value;
 $('#lockup-select-sector').disabled=!sector;
 document.querySelectorAll('.lockup-compare-pick').forEach(x=>x.checked=lockComparisons.has(Number(x.dataset.event)));
 if(from&&to&&from>to){$('#lockup-compare-chart').innerHTML='';$('#lockup-compare-pager').hidden=true;$('#lockup-compare-count').textContent='Choose a valid expiry-date range.';return;}
 const inScope=lockScopeRows().filter(x=>lockComparisons.has(x.i));
 const selected=inScope.filter(x=>x.e.last_day_locked&&(!from||x.e.last_day_locked>=from)&&(!to||x.e.last_day_locked<=to));
 const events=selected.filter(x=>x.e.window.anchor_close>0&&x.e.window.path.some(p=>Number.isFinite(p[2]))).sort((a,b)=>a.e.code.localeCompare(b.e.code)||a.e.last_day_locked.localeCompare(b.e.last_day_locked));
 const stocks=events.map(({e})=>lockSeries(e)),series=comparisonLines(stocks,mode,true);
 const {svg}=renderComparisonPage('lockup',series,{offset:true,label:mode==='stocks'?'Selected lock-up returns':mode==='average'?'Equal-weight return of selected stocks around expiry':'Sector averages of selected stocks around expiry'});
 const selectedStocks=new Set(selected.map(x=>x.e.code)).size,observedStocks=new Set(events.map(x=>x.e.code)).size,undated=inScope.filter(x=>!x.e.last_day_locked).length;
 $('#lockup-compare-count').textContent=`${sector||'All sectors'} · ${selectedStocks} stocks selected in range · ${selected.length} expiries · ${observedStocks} stocks with prices`+(undated?` · ${undated} undated excluded`:'');
 if(!inScope.length)$('#lockup-compare-chart').innerHTML='<p class="note">Select events in the table or use Select all.</p>';
 if(svg){svg.dataset.selected=selected.length;svg.dataset.observed=events.length;svg.dataset.averages=mode==='stocks'?0:series.length;svg.dataset.averageScope='selected';svg.dataset.sector=sector;svg.dataset.mode=mode;}
}
function selectLockScope(){lockComparisons.clear();lockScopeRows().forEach(({i})=>lockComparisons.add(i));comparisonPages.lockup=0;renderLockComparison();}
$('#lockup-tbl').addEventListener('change',ev=>{if(ev.target.matches('.lockup-compare-pick')){const i=Number(ev.target.dataset.event);ev.target.checked?lockComparisons.add(i):lockComparisons.delete(i);comparisonPages.lockup=0;renderLockComparison();}});
$('#lockup-select-all').addEventListener('click',selectLockScope);
$('#lockup-select-sector').addEventListener('click',selectLockScope);
$('#lockup-compare-sector').addEventListener('change',()=>{$('#lockup-sec').value=$('#lockup-compare-sector').value;redrawLockupTab();selectLockScope();});
$('#lockup-clear-compare').addEventListener('click',()=>{lockComparisons.clear();comparisonPages.lockup=0;renderLockComparison();});
for(const id of ['lockup-compare-mode','lockup-compare-from','lockup-compare-to'])$('#'+id).addEventListener('change',()=>{comparisonPages.lockup=0;renderLockComparison();});
for(const id of ['lockup-sec','lockup-q'])$('#'+id).addEventListener(id==='lockup-q'?'input':'change',()=>{$('#lockup-compare-sector').value=$('#lockup-sec').value;selectLockScope();});
$('#lockup-compare-prev').addEventListener('click',()=>{comparisonPages.lockup--;renderLockComparison();});
$('#lockup-compare-next').addEventListener('click',()=>{comparisonPages.lockup++;renderLockComparison();});
renderLockComparison();
const PEERS=DATA.peer_pairs||{pairs:[],stocks:[]},PST=new Map((PEERS.stocks||[]).map(s=>[s.code,s])),PCATALOG=new Map((DATA.hk_stocks||[]).map(s=>[s.code,s]));
$('#peer-pair').innerHTML=PEERS.pairs.map(p=>`<option value="${p.id}">${safeText(p.label||p.name_a+' / '+p.name_b)} · ${safeText(p.segment)}</option>`).join('');$('#peer-pair').value=PEERS.pairs[0]?.id||'';
const normPeerCode=v=>{const m=String(v).trim().match(/^0*(\d{1,5})(?:\s+HK(?:\s+Equity)?)?$/i);return m?String(Number(m[1])).padStart(4,'0'):'';};
function peerWindow(){const end=$('#peer-horizon').value==='Custom'?$('#peer-to').value:PEERS.asof,h=$('#peer-horizon').value;if(h==='Custom')return [$('#peer-from').value,end];if(h==='Max')return ['1900-01-01',end];const months={'1M':1,'3M':3,'6M':6,'1Y':12,'3Y':36,'5Y':60}[h],d=new Date(end+'T00:00:00Z'),day=d.getUTCDate();d.setUTCDate(1);d.setUTCMonth(d.getUTCMonth()-months);d.setUTCDate(Math.min(day,new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth()+1,0)).getUTCDate()));return [d.toISOString().slice(0,10),end];}
function renderPeer(){const preset=PEERS.pairs.find(p=>p.id===$('#peer-pair').value);if(!preset)return;const a=preset.code_a,b=preset.code_b,pa=PST.get(a),pb=PST.get(b),[from,to]=peerWindow();$('#peer-title').textContent=preset.label;$('#peer-watch').textContent=preset.segment+' · '+preset.peer_reason+' '+preset.watch;
 const custom=$('#peer-horizon').value==='Custom';document.querySelectorAll('.peer-custom').forEach(x=>x.hidden=!custom);$('#peer-from').disabled=!custom;$('#peer-to').disabled=!custom;if(!custom){$('#peer-from').value=from==='1900-01-01'?'':from;$('#peer-to').value=to;}
 const clear=msg=>{$('#peer-coverage').textContent=msg;$('#peer-performance').innerHTML='';$('#peer-spread').innerHTML='';$('#peer-summary').innerHTML='';};if(!from||!to||from>to){clear('Choose a valid date range.');return;}if(!pa||!pb){clear('Saved history is unavailable for this pair.');return;}
 const bm=new Map(pb.history),all=pa.history.filter(h=>h[0]>=from&&h[0]<=to),joint=all.filter(h=>bm.has(h[0]));if(joint.length<2){clear('Fewer than two shared observations in this window. Choose a longer horizon.');return;}const base=joint[0],baseb=bm.get(base[0]),points=all.filter(h=>h[0]>=base[0]),ra=points.map(h=>[h[0],bm.has(h[0])?100*(h[1]/base[1]-1):null]),rb=points.map(h=>[h[0],bm.has(h[0])?100*(bm.get(h[0])/baseb-1):null]),spread=ra.map((h,i)=>[h[0],h[1]===null?null:h[1]-rb[i][1]]);
 $('#peer-coverage').textContent='Stored · '+joint[0][0]+' to '+joint.at(-1)[0]+' · '+joint.length+' shared observations'+(joint[0][0]>from?' · history starts within the selected window':'');
 const last=joint.at(-1)[0],va=ra.find(p=>p[0]===last)[1],vb=rb.find(p=>p[0]===last)[1],vs=va-vb;$('#peer-summary').innerHTML=[[pa.name+' return',va,'%'],[pb.name+' return',vb,'%'],['A − B spread',vs,' pp']].map(([name,v,u])=>`<div class="tile"><div class="l">${safeText(name)}</div><div class="v ${v>0?'up':v<0?'down':''}">${v>0?'+':''}${v.toFixed(1)}${u}</div></div>`).join('');
 deskLines($('#peer-performance'),[{name:pa.name+' ('+a+')',points:ra,color:'#315b7d'},{name:pb.name+' ('+b+')',points:rb,color:'#9b4a47'}],{label:a+'/'+b+' relative performance'});deskLines($('#peer-spread'),[{name:'A − B spread',points:spread,color:'#315b7d'}],{percent:false,label:a+'/'+b+' spread in percentage points'});
 document.querySelectorAll('.peer-pick').forEach(x=>x.closest('tr').classList.toggle('peer-active',x.dataset.pair===preset.id));
}
for(const id of ['peer-pair','peer-horizon','peer-from','peer-to'])$('#'+id).addEventListener('change',renderPeer);renderPeer();
$('#peer-table').innerHTML=`<table class="tbl"><thead><tr><th>Product</th><th>Company A</th><th>Company B</th><th>Key difference</th><th class="num">A daily</th><th class="num">B daily</th></tr></thead><tbody>`+PEERS.pairs.map(p=>`<tr><td><button class="ah-select peer-pick" data-pair="${p.id}">${safeText(p.segment)}</button></td><td>${safeText(p.name_a)} <span class="m">${p.code_a}</span></td><td>${safeText(p.name_b)} <span class="m">${p.code_b}</span></td><td>${safeText(p.watch)}</td><td class="num ${p.daily_a>0?'up':p.daily_a<0?'down':''}">${fmt.pct(100*p.daily_a)}</td><td class="num ${p.daily_b>0?'up':p.daily_b<0?'down':''}">${fmt.pct(100*p.daily_b)}</td></tr>`).join('')+'</tbody></table>';
$('#peer-table').addEventListener('click',ev=>{const pick=ev.target.closest('.peer-pick'),p=PEERS.pairs.find(p=>p.id===pick?.dataset.pair);if(p){$('#peer-pair').value=p.id;renderPeer();}});renderPeer();

for(const id of ['ah-sec','ah-sub'])$('#'+id).addEventListener('change',()=>{$('#ah-compare-sector').value=$('#ah-sec').value;selectAHScope();});
$('#ah-when').addEventListener('change',renderAHComparison);
