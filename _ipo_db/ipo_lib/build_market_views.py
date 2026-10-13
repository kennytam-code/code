"""Simple Bloomberg desk monitors using the Artifact Tool-authored layout.

The production desk builder retains openpyxl for native workbook assembly;
all layout and chart designs are maintained in create_market_template.mjs.
"""
import base64,io,json,re
from copy import copy,deepcopy
from datetime import date
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font,Alignment,PatternFill,Border,Side
from openpyxl.chart.data_source import AxDataSource,NumRef,NumDataSource,StrRef,NumData,NumVal
from openpyxl.chart.axis import DateAxis
from openpyxl.chart import Reference
from openpyxl.worksheet.table import Table,TableStyleInfo
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.comments import Comment
from ah_basis import chart_review
from market_universe import load as market_universe, histories as market_histories
ROOT=Path(__file__).resolve().parent.parent
PCT='0.0%;(0.0%);0.0%'
def xml_text(value):
 return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(value))

def cell(ws,r,c,v,fmt=None):
 x=ws.cell(r,c,v);x.font=Font(name='Arial',size=11,color='111111');x.alignment=Alignment(vertical='center');x.border=Border(bottom=Side(style='hair',color='DDDDDD'))
 if fmt:x.number_format=fmt
 return x

def template(wb):
 doc=json.loads((ROOT/'data/market_views_template.json').read_text());src=load_workbook(io.BytesIO(base64.b64decode(doc['xlsx_base64'])))
 peer_doc=json.loads((ROOT/'data/peer_views_template.json').read_text());peer_src=load_workbook(io.BytesIO(base64.b64decode(peer_doc['xlsx_base64'])))
 sources=[s for s in src if not s.title.startswith('Peer ')]+list(peer_src)
 for s in sources:
  if s.title in ['Market Data','AH History']:continue
  t=wb.create_sheet(s.title)
  for row in [list(s._cells.values())]:
   for c in row:
    if c.__class__.__name__=='MergedCell':continue
    value=c.value.replace('3004','2204') if s.title in ['AH Compare','AH Compare Live'] and isinstance(c.value,str) and c.value.startswith('=') else c.value
    n=t.cell(c.row,c.column,value)
    for attr in ('font','fill','border','alignment','protection'):setattr(n,attr,copy(getattr(c,attr)))
    n.number_format=c.number_format
  for k,d in s.column_dimensions.items():t.column_dimensions[k]=copy(d);t.column_dimensions[k].parent=t
  for k,d in s.row_dimensions.items():t.row_dimensions[k]=copy(d);t.row_dimensions[k].parent=t
  for m in s.merged_cells.ranges:t.merge_cells(str(m))
  t.conditional_formatting=deepcopy(s.conditional_formatting);t.sheet_properties=deepcopy(s.sheet_properties);t._charts=deepcopy(s._charts);t.freeze_panes=s.freeze_panes;t.sheet_view.showGridLines=False
  for validation in s.data_validations.dataValidation:
   dv=deepcopy(validation)
   if dv.formula1 and dv.formula1.startswith(chr(34)) and len(dv.formula1)>257:dv.formula1='AHPairList' if s.title=='AH' else 'INDIRECT("\'Lock-up Data\'!$Y$8:$Y$393")'
   t.add_data_validation(dv)
  if t.title in ['AH','Lock-up','Peer Trades']:t._charts.sort(key=lambda c: len(c.series) if t.title!='Peer Trades' else -len(c.series))
  elif t.title=='IPO Live':
   def chart_title(c):return ''.join(x.text or '' for x in c.title.to_tree().iter() if x.tag.endswith('}t')) if c.title else ''
   t._charts.sort(key=lambda c:'subsector' in chart_title(c).lower())
 src.close();peer_src.close()

def build(wb,deals,root=None):
 global ROOT
 ROOT=Path(root or ROOT);template(wb)
 pd=wb['Peer Data'];cursor=2
 for st in json.loads((ROOT/'data/peer_pairs.json').read_text())['stocks']:
  for dt,price in st['history']:pd.cell(cursor,1,date.fromisoformat(dt));pd.cell(cursor,2,price);cursor+=1
 ipo,ah,chart=wb['IPO Live'],wb['AH'],wb['Chart Data']
 md=wb.create_sheet('Market Data');cache=wb.create_sheet('AH History');live=wb.create_sheet('Live History')
 batch=market_histories(ROOT);recs={r['code']:r for r in batch['pairs']};taxonomy=json.loads((ROOT/'data/taxonomy.json').read_text())['sectors'];sectors=list(taxonomy)
 listed=sorted(market_universe(ROOT),key=lambda d:(sectors.index(d['sector']),d['name']));pairs=[d for d in listed if d.get('a_share_code')];hrows={d['code']:8+i for i,d in enumerate(listed)};end=7+len(listed);pend=2+len(pairs)
 md['D2']='Live CNYHKD';md['E2']='=IF(AH!$E$4="Bloomberg",BDP("CNYHKD Curncy","LAST_PRICE"),"")'
 md['A7'],md['B7'],md['C7'],md['D7']='Bloomberg H ticker','Previous trading-day close','Sector','Subsector'
 for i,d in enumerate(listed,8):
  ticker=f'{int(d["code"])} HK Equity'
  for c,v in enumerate([ticker,d['name'],d['sector']],1):cell(ipo,i,c,v)
  cell(ipo,i,3,f'=IF($B$5="Subsector",\'Market Data\'!D{i},\'Market Data\'!C{i})')
  cell(ipo,i,4,f'=IF($A{i}="","",BDP($A{i},"LAST_PRICE"))','0.00')
  cell(ipo,i,5,f'=IFERROR(IF(AND(ISNUMBER(D{i}),ISNUMBER(\'Market Data\'!B{i}),\'Market Data\'!B{i}>0),D{i}/\'Market Data\'!B{i}-1,""),"")',PCT)
  md.cell(i,1,ticker);md.cell(i,2,f'=IF(\'IPO Live\'!$A{i}="","",BDP(\'IPO Live\'!$A{i},"PX_YEST_CLOSE"))')
  md.cell(i,3,d['sector']);md.cell(i,4,d['subsector'])
  ipo.row_dimensions[i].height=22
 for r,sec in enumerate(sectors,6):
  cell(ipo,r,7,sec);cell(ipo,r,8,f'=IFERROR(AVERAGEIFS($E$8:$E${end},\'Market Data\'!$C$8:$C${end},G{r}),NA())',PCT)
  cell(ipo,r,9,f'=COUNTIFS(\'Market Data\'!$C$8:$C${end},G{r},$E$8:$E${end},">=-1E+99",$E$8:$E${end},"<=1E+99")','0')
 ipo['G15']='Equal-weight average of available daily changes.';ipo.merge_cells('G15:O15');ipo['G15'].font=Font(name='Arial',size=10,color='555555')
 bar=ipo._charts[0];bar.series[0].val=NumDataSource(numRef=NumRef(f=f"'IPO Live'!$H$6:$H${5+len(sectors)}"));bar.series[0].cat=AxDataSource(strRef=StrRef(f=f"'IPO Live'!$G$6:$G${5+len(sectors)}"));bar.x_axis.scaling.min=None
 bar.type='bar';bar.x_axis.axPos='l';bar.y_axis.axPos='b';bar.x_axis.delete=False;bar.y_axis.delete=False;bar.x_axis.tickLblPos='low';bar.y_axis.numFmt='0.0%'
 ipo['C7']='Classification';ipo['G45']='Equal-weight average of available quotes in the selected sector.';ipo.merge_cells('G45:O45');ipo['G45'].font=Font(name='Arial',size=10,color='555555')
 for j,sec in enumerate(sectors,53):
  md.cell(2,j,sec)
  for r,item in enumerate(taxonomy[sec],3):md.cell(r,j,item['label'])
 for r in range(37,45):
  cell(ipo,r,7,f'=IFERROR(IF(INDEX(\'Market Data\'!$BA$3:$BI$10,ROW()-36,MATCH($H$34,\'Market Data\'!$BA$2:$BI$2,0))=0,"",INDEX(\'Market Data\'!$BA$3:$BI$10,ROW()-36,MATCH($H$34,\'Market Data\'!$BA$2:$BI$2,0))),"")')
  cell(ipo,r,8,f'=IFERROR(IF(G{r}="",NA(),AVERAGEIFS($E$8:$E${end},\'Market Data\'!$C$8:$C${end},$H$34,\'Market Data\'!$D$8:$D${end},G{r})),NA())',PCT)
  cell(ipo,r,9,f'=IF(G{r}="","",COUNTIFS(\'Market Data\'!$C$8:$C${end},$H$34,\'Market Data\'!$D$8:$D${end},G{r},$E$8:$E${end},">=-1E+99",$E$8:$E${end},"<=1E+99"))','0')
 for col,name in [('G','LiveSubsectorLabels'),('H','LiveSubsectorChanges')]:wb.defined_names.add(DefinedName(name,attr_text=f"'IPO Live'!${col}$37:INDEX('IPO Live'!${col}$37:${col}$44,MAX(1,COUNTIF('IPO Live'!$G$37:$G$44,\"?*\")))"))
 sub=ipo._charts[1];sub.series[0].val=NumDataSource(numRef=NumRef(f="'IPO Live'!LiveSubsectorChanges"));sub.series[0].cat=AxDataSource(strRef=StrRef(f="'IPO Live'!LiveSubsectorLabels"));sub.type='bar';sub.x_axis.axPos='l';sub.y_axis.axPos='b';sub.x_axis.delete=False;sub.y_axis.delete=False;sub.x_axis.tickLblPos='low';sub.y_axis.numFmt='0.0%'
 tab=Table(displayName='IPOLiveQuotes',ref=f'A7:E{end}');tab.tableStyleInfo=TableStyleInfo(name='TableStyleLight1',showRowStripes=False);ipo.add_table(tab)
 for j,h in enumerate(['Date','H HKD','A CNY','CNYHKD','A date','FX date'],1):cache.cell(1,j,h)
 heads=['H code','H ticker','A ticker','Company','Sector','Subsector','H listing','IPO premium','Cache start','Cache rows','Class review','Raw debut H','Cache through','A last CNY','H last HKD','Latest premium','Stored A CNY','Stored H HKD','Stored CNYHKD','Stored A date','Stored FX date','Selected CNYHKD']
 for j,h in enumerate(heads,16):md.cell(2,j,h)
 cr=2
 for i,d in enumerate(pairs,3):
  rec=recs[d['code']];basis=chart_review(d['code'],rec,ROOT);aligned={x[0]:x for x in rec.get('history',[])};hs=[x for x in rec.get('h_history',[]) if x[0]>=d['ipo_date']];start=cr
  for dt,h in hs:
   x=aligned.get(dt)
   vals=[date.fromisoformat(dt),h,x[2] if x else None,x[3] if x else None,date.fromisoformat(x[5]) if x else None,date.fromisoformat(x[6]) if x else None]
   for j,v in enumerate(vals,1):cache.cell(cr,j,v).number_format='dd-mmm-yy' if j in [1,5,6] else '0.0000'
   cr+=1
  review='share-scale' in rec.get('exclusion','') and not basis;hcode=f'{int(d["code"])} HK Equity';acode=f'{d["a_share_code"].split(".")[0]} CH Equity'
  if basis:
   md.cell(i,41,date.fromisoformat(basis['h_ex_date']))
   md.cell(i,42,date.fromisoformat(basis['a_ex_date']))
  vals=[d['code'],hcode,acode,d['name'],d['sector'],d['subsector'],date.fromisoformat(d['ipo_date']),rec.get('offer_reference_premium_pct')/100 if rec.get('offer_reference_premium_pct') is not None else None,start,len(hs),int(review),hs[0][1] if hs else None,date.fromisoformat(hs[-1][0]) if hs else None]
  for j,v in enumerate(vals,16):md.cell(i,j,v)
  last=aligned.get(hs[-1][0]) if hs else None
  for j,v in enumerate([last[2] if last else None,hs[-1][1] if hs else None,last[3] if last else None,date.fromisoformat(last[5]) if last else None,date.fromisoformat(last[6]) if last else None],32):md.cell(i,j,v)
  md.cell(i,37,f'=IF(AH!$E$4="Stored",IF(ISNUMBER(AH{i}),AH{i},""),IF(AH!$E$4="Bloomberg",$E$2,""))')
  md.cell(i,29,f'=IF(AH!$E$4="Bloomberg",BDP($R{i},"LAST_PRICE"),IF(AH!$E$4="Stored",IF(ISNUMBER(AF{i}),AF{i},""),""))')
  md.cell(i,30,f'=IF(AH!$E$4="Bloomberg",\'IPO Live\'!D{hrows[d["code"]]},IF(AH!$E$4="Stored",AG{i},""))')
  md.cell(i,31,f'=IFERROR(IF($Z{i}=1,"Class ratio review",IF(AND(ISNUMBER(AC{i}),AC{i}>0,ISNUMBER(AD{i}),AD{i}>0,ISNUMBER(AK{i}),AK{i}>0,OR(AH!$E$4="Bloomberg",AND(ISNUMBER(AI{i}),ISNUMBER(AJ{i}),AI{i}<=AB{i},AJ{i}<=AB{i},AB{i}-AI{i}<=10,AB{i}-AJ{i}<=5))),AC{i}*AK{i}/AD{i}-1,"")),"")')
  r=i+5
  for j,col in enumerate(['R','Q','T','U','W','AE'],1):
   value=f"='Market Data'!{col}{i}"
   if col=='W':value=f'=IF(\'Market Data\'!Z{i}=1,"Class ratio review",IF(ISNUMBER(\'Market Data\'!W{i}),\'Market Data\'!W{i},""))'
   cell(ah,r,j,value,PCT if j in [5,6] else None)
   if basis and j in [5,6]:
    ah.cell(r,j).comment=Comment('Filed capitalisation issue applies to both classes. H ex-date: '+basis['h_ex_date']+'; A ex-date: '+basis['a_ex_date']+'. IPO and latest quotes are outside the mismatch interval.\n'+'\n'.join(s['url'] for s in basis['sources']),'Source')
  ah.row_dimensions[r].height=22
 ah['B4']='3986';ah['B4'].number_format='@';ah['B4'].font=Font(name='Arial',size=11,color='0000FF')
 wb.defined_names.add(DefinedName('AHPairList',attr_text=f"'Market Data'!$P$3:$P${pend}"))
 dv=DataValidation(type='list',formula1='AHPairList',allow_blank=True);dv.showErrorMessage=False;ah.add_data_validation(dv);dv.add(ah['B4'])
 ah['A5']='=IF($E$4="Stored","Stored snapshot through 02-Oct-2026","Bloomberg mode | prices / histories requested through today")';ah['E4']='Stored';mode=DataValidation(type='list',formula1='"Stored,Bloomberg"',allow_blank=False);mode.showErrorMessage=True;mode.errorTitle='Choose a price source';mode.error='Choose Stored or Bloomberg.';ah.add_data_validation(mode);mode.add(ah['E4'])
 ah['A5']=f'=IF($E$4="Stored","{len(pairs)} IPO A/H pairs | Stored through {batch["asof"]}",IF($E$4="Bloomberg","{len(pairs)} IPO A/H pairs | Bloomberg through TODAY","Choose Stored or Bloomberg in E4"))';ah.merge_cells('A5:H5');ah['A5'].font=Font(name='Arial',size=10,color='555555')
 typed='VALUE(IFERROR(LEFT(TRIM($B$4),FIND(" ",TRIM($B$4))-1),IFERROR(LEFT(TRIM($B$4),FIND(".",TRIM($B$4))-1),TRIM($B$4))))'
 ah['P3']=f'=IFERROR(MATCH(TEXT({typed},"0000"),\'Market Data\'!$P$3:$P${pend},0),IFERROR(MATCH(TEXT({typed},"000000")&" CH Equity",\'Market Data\'!$R$3:$R${pend},0),0))'
 p=lambda col:f'IFERROR(INDEX(\'Market Data\'!${col}$3:${col}${pend},$P$3),"")'
 for coord,col in [('P4','Q'),('P5','R'),('P6','V'),('P7','X'),('P8','Y'),('P9','Z'),('P16','AA'),('P17','AB'),('P18','AC'),('P19','AD'),('P20','AK'),('P22','AO'),('P23','AP')]:ah[coord]='='+p(col)
 ah['J4']=f'=IF($P$3=0,"Choose an A/H code",{p("S")})';ah.merge_cells('J4:O4');ah['J4'].font=Font(name='Arial',size=12,bold=True,color='111111')
 ah['P10']='=IFERROR(IF(AND($P$3>0,COUNT(\'Live History\'!$A$5:$A$2204)>0,MIN(\'Live History\'!$A$5:$A$2204)=$P$6,MAX(\'Live History\'!$A$5:$A$2204)<=TODAY(),MAX(\'Live History\'!$A$5:$A$2204)>=MIN(TODAY()-8,$P$17),ABS(INDEX(\'Live History\'!$B$5:$B$2204,MATCH($P$6,\'Live History\'!$A$5:$A$2204,0))-$P$16)<=MAX(0.005,$P$16*0.0005)),1,0),0)'
 ah['P10']=ah['P10'].value.replace('COUNT(\'Live History\'!$A$5:$A$2204)>0,','COUNT(\'Live History\'!$A$5:$A$2204)>0,COUNT(\'Live History\'!$D$5:$D$2204)>0,COUNT(\'Live History\'!$G$5:$G$2204)>0,')
 ah['P10']=ah['P10'].value.replace('AND($P$3>0,','AND($E$4="Bloomberg",$P$3>0,')
 ah['P12']='=IFERROR(IF(AND($E$4="Bloomberg",$P$3>0,ISNUMBER($P$18),$P$18>0,ISNUMBER($P$19),$P$19>0,ISNUMBER($P$20),$P$20>0),1,0),0)'
 ah['P13']='=IFERROR(MATCH($P$6,\'Live History\'!$A$5:$A$2204,0),1)'
 ah['P24']='=IFERROR(INDEX(\'AH Delta\'!$L$3:$L$'+str(pend)+',$P$3),0)'
 ah['P25']='=IFERROR(INDEX(\'AH Delta\'!$M$3:$M$'+str(pend)+',$P$3),0)'
 ah['P21']='=IFERROR(IF(AND($P$10=1,$P$12=1,MAX(\'Live History\'!$A$5:$A$2204)<TODAY()),1,0),0)'
 ah['P11']='=MAX(1,MIN(2200,IF($E$4="Stored",N($P$8),IF($P$10=1,COUNT(\'Live History\'!$A$5:$A$2204)+$P$21,0))))'
 ah['J24']='=IF($P$3=0,"",IF($P$9=1,"Premium withheld pending share-class ratio review",IF($E$4="Stored","Stored through "&TEXT($P$17,"dd-mmm-yy"),IF($P$10=1,"Bloomberg through "&TEXT(MAX(\'Live History\'!$A$5:$A$2204),"dd-mmm-yy")&IF($P$21=1," plus today\'s live quote",""),"Bloomberg history unavailable or failed validation. Choose Stored to view the saved chart."))))';ah.merge_cells('J24:O25');ah['J24'].alignment=Alignment(wrap_text=True,vertical='top');ah['J24'].font=Font(name='Arial',size=10,color='555555')
 ah['J57']='IPO premium uses the H offer price and the prior A/FX closes.';ah.merge_cells('J57:O58');ah['J57'].alignment=Alignment(wrap_text=True);ah['J57'].font=Font(name='Arial',size=10,color='555555')
 ah['J57']='=IF($P$22>0,"Chart gap "&TEXT($P$22,"dd-mmm-yy")&" to "&TEXT($P$23-1,"dd-mmm-yy")&": A/H ex-entitlement dates differ. IPO and current premiums remain comparable.","IPO premium uses the H offer price and the prior A/FX closes.")'
 ah['J60']='=IF(OR($E$4<>"Bloomberg",$P$3=0),"",IF($P$10<>1,"Same-date check awaits valid Bloomberg history",IF(COUNTIF(\'Chart Data\'!$I$5:$I$2204,"<>0")=0,"No matching snapshot dates to compare",IF(COUNTIF(\'Chart Data\'!$I$5:$I$2204,-1)=0,"Same-date check: "&COUNTIF(\'Chart Data\'!$I$5:$I$2204,1)&" closes agree","Same-date check: "&COUNTIF(\'Chart Data\'!$I$5:$I$2204,-1)&" of "&COUNTIF(\'Chart Data\'!$I$5:$I$2204,"<>0")&" dates differ; review H / A / FX closes"))))';ah.merge_cells('J60:O62');ah['J60'].alignment=Alignment(wrap_text=True,vertical='top');ah['J60'].font=Font(name='Arial',size=10,color='555555')
 ah.column_dimensions['P'].hidden=True
 tab=Table(displayName='AHLivePairs',ref=f'A7:H{7+len(pairs)}');tab.tableStyleInfo=TableStyleInfo(name='TableStyleLight1',showRowStripes=False);ah.add_table(tab)
 # BDH owns separate clear output areas. It is never nested inside INDEX/MATCH.
 options=',"Dts=S","Dir=V","Sort=A","Days=T","Per=cd","UseDPDF=N","CshAdjNormal=N","CshAdjAbnormal=N","CapChg=N"'
 for col,ticker,start in [(1,'AH!$P$4','AH!$P$6'),(4,'AH!$P$5','AH!$P$6-31'),(7,'"CNYHKD Curncy"','AH!$P$6-31')]:
  opt=options if col!=7 else ',"Dts=S","Dir=V","Sort=A","Days=T","Per=cd"'
  live.cell(2,col,'H history' if col==1 else 'A history' if col==4 else 'FX history');live.cell(5,col,f'=IF(OR(AH!$P$3=0,AH!$E$4<>"Bloomberg"),"",BDH({ticker},"PX_LAST",{start},TODAY(){opt}))')
 for j,h in enumerate(['Date','A premium','H HKD','A CNY','CNYHKD','A date','FX date','Snapshot matching row','Same-date check (1 agree / -1 differ)'],1):chart.cell(4,j,h)
 for r in range(5,2205):
  off=r-5;idx=f'AH!$P$13+{off}';cached=f'AH!$P$7+{off}'
  chart.cell(r,1,f'=IF(OR(AH!$P$3=0,{off}+1>AH!$P$11,AND(AH!$E$4<>"Stored",AH!$P$10<>1)),"",IFERROR(IF(AND(AH!$P$21=1,{off}+1=AH!$P$11),TODAY(),IF(AH!$P$10=1,INDEX(\'Live History\'!$A$5:$A$2204,{idx}),INDEX(\'AH History\'!$A$1:$A${cr-1},{cached}))),""))').number_format='dd-mmm-yy'
  current=f'AND(AH!$P$10=1,AH!$P$12=1,$A{r}=TODAY())'
  h=f'IF({current},AH!$P$19,IF(AH!$P$10=1,INDEX(\'Live History\'!$B$5:$B$2204,{idx}),INDEX(\'AH History\'!$B$1:$B${cr-1},{cached})))'
  chart.cell(r,3,f'=IFERROR(IF(ISNUMBER($A{r}),{h},NA()),NA())')
  for dest,rawdate,rawvalue,cachedcol,livevalue in [(4,'D','E','C','AH!$P$18'),(5,'G','H','D','AH!$P$20'),(6,'D','D','E',f'IF({current},TODAY(),NA())'),(7,'G','G','F',f'IF({current},TODAY(),NA())')]:
   hv=f'INDEX(\'Live History\'!${rawvalue}$5:${rawvalue}$2204,MATCH($A{r},\'Live History\'!${rawdate}$5:${rawdate}$2204,1))';cv=f'INDEX(\'AH History\'!${cachedcol}$1:${cachedcol}${cr-1},{cached})'
   chart.cell(r,dest,f'=IFERROR(IF(ISNUMBER($A{r}),IF({current},{livevalue},IF(AH!$P$10=1,{hv},{cv})),NA()),NA())')
  samebasis=f'AND(OR(AH!$P$22<=0,($A{r}>=AH!$P$22)=($F{r}>=AH!$P$23)),OR(AH!$P$24<=0,($A{r}>=AH!$P$24)=($F{r}>=AH!$P$25)))'
  chart.cell(r,2,f'=IFERROR(IF(AND(AH!$P$9<>1,{samebasis},$C{r}>0,$D{r}>0,$E{r}>0,$F{r}>0,$G{r}>0,$F{r}<=$A{r},$G{r}<=$A{r},$A{r}-$F{r}<=10,$A{r}-$G{r}<=5),$D{r}*$E{r}/$C{r}-1,NA()),NA())').number_format=PCT
  dates=f"'AH History'!$A$1:$A${cr-1}";ref=f'INDEX({dates},AH!$P$7):INDEX({dates},AH!$P$7+AH!$P$8-1)'
  chart.cell(r,8,f'=IFERROR(IF(AND(AH!$E$4="Bloomberg",AH!$P$10=1,ISNUMBER($A{r}),$A{r}<=AH!$P$17),AH!$P$7-1+MATCH($A{r},{ref},0),0),0)')
  snap=lambda col:f'INDEX(\'AH History\'!${col}$1:${col}${cr-1},$H{r})'
  check=f'AND(ABS($C{r}-{snap("B")})<=MAX(0.005,ABS({snap("B")})*0.00005),ABS($D{r}-{snap("C")})<=MAX(0.005,ABS({snap("C")})*0.00005),ABS($E{r}-{snap("D")})<=0.00005,$F{r}={snap("E")},$G{r}={snap("F")})'
  chart.cell(r,9,f'=IF($H{r}=0,0,IFERROR(IF({check},1,-1),-1))')
 for col,name in [('A','AHChartDates'),('B','AHChartPremium')]:wb.defined_names.add(DefinedName(name,attr_text=f"'Chart Data'!${col}$5:INDEX('Chart Data'!${col}$5:${col}$2204,AH!$P$11)"))
 c=ah._charts[0];c.series[0].val=NumDataSource(numRef=NumRef(f="'Chart Data'!AHChartPremium"));c.series[0].cat=AxDataSource(numRef=NumRef(f="'Chart Data'!AHChartDates"));old=c.x_axis;c.x_axis=DateAxis(axId=old.axId,crossAx=old.crossAx,axPos='b',numFmt='mmm-yy',tickLblPos='low',delete=False,auto=True,baseTimeUnit='days');c.y_axis.crosses='min';c.x_axis.majorTickMark='out';c.display_blanks='gap'
 for s in [md,cache,live,chart]:s.sheet_state='hidden';s.sheet_view.showGridLines=False
 from openpyxl.formula.translate import Translator
 # Extend the Artifact-authored exemplar formulas without changing their logic.
 for helper,groups,last in [('AH Compare',[(1,7),(10,16),(19,25),(28,34)],2204),('Peer Chart',[(1,7)],3004)]:
  sh=wb[helper]
  for lo,hi in groups:
   for col in range(lo,hi+1):
    source=sh.cell(5,col)
    for rr in range(7,last+1):sh.cell(rr,col,Translator(source.value,origin=source.coordinate).translate_formula(sh.cell(rr,col).coordinate))
 build_lockups(wb,deals)
 bind_desk_charts(wb)
 return ah

def build_lockups(wb,deals):
 data=json.loads((ROOT/'data/batches/lockup_events.json').read_text());ws=wb['Lock-up'];raw=wb['Lock-up Data'];known={d['code'] for d in deals}
 events=[e for e in data['events'] if e['code'] in known and e['category']=='Cornerstone' and e['date_basis']!='No cornerstone tranche'];codes=sorted({e['code'] for e in events});event_end=7+len(events);sentinel=event_end+1;path_end=7+61*(len(events)+1)
 layout=json.loads((ROOT/'data/market_views_template.json').read_text())['lockup_layout'];header=layout['table_header'];choices=[];defaults=[]
 def label(e):return e['category']+' · '+(e.get('last_day_locked') or 'date unavailable')
 def auto(code):
  candidates=[(i,e) for i,e in enumerate(events) if e['code']==code];past=[x for x in candidates if x[1].get('last_day_locked') and x[1]['last_day_locked']<=data['price_asof']];cs=[x for x in past if x[1]['category']=='Cornerstone'];pool=cs or past or candidates
  return 8+sorted(pool,key=lambda x:x[1].get('last_day_locked') or '',reverse=True)[0][0]
 for code in codes:
  defaults.append([code,auto(code)]);choices.append([code,'Auto']);choices.extend([code,label(e)] for e in events if e['code']==code)
 choices.append(['','Auto']);choice_end=7+len(choices)
 # The Artifact-authored formulas and layout survive. Rebind their bounded
 # input ranges when a refresh adds stocks or filed restriction schedules.
 ends={**{c:event_end for c in ['J','S','U']},**{c:sentinel for c in ['A','B','C','G','K','L','N','O','P','Q','R','T','AA']},'M':sentinel,'V':choice_end,'Y':7+len(codes),'Z':7+len(codes),'AC':path_end,'AD':path_end}
 def resize(value):
  return re.sub(r"('Lock-up Data'!\$([A-Z]+)\$8:\$\2\$)(\d+)",lambda m:m[1]+str(event_end if m[2]=='M' and int(m[3])==7+layout['event_count'] else ends[m[2]]),value)
 for sheet in [ws,wb['Chart Data']]:
  for x in list(sheet._cells.values()):
   if x.data_type=='f' and (sheet==ws or 11<=x.column<=15):x.value=resize(x.value)
 ws['P4']=re.sub(r',\d+\)$',f',{sentinel})',ws['P4'].value);ws['P5']=re.sub(r',\d+\)$',f',{len(choices)})',ws['P5'].value)
 for validation in ws.data_validations.dataValidation:
  if str(validation.sqref)=='B4':validation.formula1=f'INDIRECT("\'Lock-up Data\'!$Y$8:$Y${7+len(codes)}")'
 if str(ws['B4'].value) not in codes:ws['B4']=codes[0]
 ws['A5']=f'Prices through {data["price_asof"]}. Day 0 = last HK trading session on/before the last locked day.';ws['A5'].font=Font(name='Arial',size=10,color='555555')
 for c in list(raw._cells.values()):
  if c.row>=8:c.value=None
 listing_dates={d['code']:d['ipo_date'] for d in deals};investors={d['code']:d.get('cornerstone_investors') or [] for d in deals}
 for index,e in enumerate(events):
  i=header+1+index;r=8+index
  dt=e.get('last_day_locked');windows=e.get('windows',{});t=windows.get('30 trading sessions',{});c=windows.get('Calendar days',{})
  names=investors[e['code']];display=names[0]+(f' +{len(names)-1}' if len(names)>1 else '') if names else 'Roster unconfirmed'
  vals=[e['code'],e['name'],e['sector'],display,date.fromisoformat(listing_dates[e['code']]),date.fromisoformat(dt) if dt else 'Expiry unconfirmed']
  for j,v in enumerate(vals,1):cell(ws,i,j,v,'dd-mmm-yyyy' if j==5 or j==6 and dt else '@' if j==1 else None)
  if names:ws.cell(i,4).comment=Comment(xml_text('Full company cornerstone roster; individual expiry dates can apply to subsets. See the event filing.\n'+'; '.join(names)),'Filed cornerstone roster')
  ws.cell(i,6).comment=Comment(xml_text('\n'.join([e.get('date_basis',''),f'First day after lock-up: {e.get("first_day_after","unestablished")}',f'Filing page {e.get("page","—")}: {e.get("url","")}',e.get('snippet',''),* [f'{m}: {w.get("pre_start")} → {w.get("anchor")} → {w.get("post_end")} | closes {w.get("pre_start_close")}, {w.get("anchor_close")}, {w.get("post_end_close")}' for m,w in windows.items()]])),'HK IPO source review')
  rawvals=[t.get('pre_start_close'),t.get('anchor_close'),t.get('post_end_close'),c.get('pre_start_close'),c.get('anchor_close'),c.get('post_end_close'),'Expiry unconfirmed' if not dt else t.get('status',e['date_basis']),c.get('status',e['date_basis'])]
  metadata=[e['code'],e['name'],e['sector'],label(e),date.fromisoformat(dt) if dt else None,8+index*61,*[date.fromisoformat(t[k]) if t.get(k) else None for k in ['pre_start','anchor','post_end']],e['code']+'|'+label(e),e.get('url')]
  for j,v in enumerate(rawvals,1):raw.cell(r,j,v)
  for j,v in enumerate(metadata,10):raw.cell(r,j,v)
  raw.cell(r,21,r)
  raw.cell(r,27,date.fromisoformat(listing_dates[e['code']]))
  by_offset={p[0]:p for p in t.get('path',[])}
  for offset in range(-30,31):
   p=by_offset.get(offset);pr=8+index*61+offset+30
   for j,v in enumerate([offset,date.fromisoformat(p[1]) if p and p[1] else None,p[2] if p else None],28):raw.cell(pr,j,v)
  for col,old,new in [(7,'A','B'),(8,'B','C')]:
   start=f"'Lock-up Data'!${old}${r}";finish=f"'Lock-up Data'!${new}${r}"
   cell(ws,i,col,f'=IFERROR(IF(AND(ISNUMBER({start}),{start}>0,ISNUMBER({finish}),{finish}>0),{finish}/{start}-1,""),"")',PCT)
  deal=next(d for d in deals if d['code']==e['code'])
  for col,key in [(9,'cornerstone_pct'),(10,'since_ipo_pct'),(11,'deal_size_hkdm')]:
   val=deal.get(key);cell(ws,i,col,val/100 if val is not None and col in [9,10] else val,PCT if col in [9,10] else '#,##0.0')
  cell(ws,i,12,f"='Lock-up Data'!$G${r}")
  link=cell(ws,i,13,'HKEX' if e.get('url') else '—')
  if e.get('url'):link.hyperlink=e['url'];link.font=Font(name='Arial',size=11,color='0563C1',underline='single')
  import math
  ws.row_dimensions[i].height=max(24,16*math.ceil(len(display)/32),36 if not dt else 24)
  for j in [4,6,12]:ws.cell(i,j).alignment=Alignment(wrap_text=True,vertical='center')
  ws.cell(i,12).alignment=Alignment(wrap_text=True,vertical='center',indent=1)
 for col,value in {'G':'Unknown H code','J':'','K':'Unknown H code','L':'','M':'Select an event','O':8+len(events)*61,'S':''}.items():raw[f'{col}{sentinel}']=value
 for offset in range(-30,31):raw.cell(8+len(events)*61+offset+30,28,offset)
 for r,values in enumerate(choices,8):
  for j,v in enumerate(values,22):raw.cell(r,j,v)
 for r,values in enumerate(defaults,8):
  for j,v in enumerate(values,25):raw.cell(r,j,v)
 for col in ['N','P','Q','R','AA','AC']:
  for c in list(raw._cells.values()):
   if c.column_letter==col and c.value is not None:c.number_format='dd-mmm-yyyy'
 for col in range(16,27):ws.column_dimensions[__import__('openpyxl').utils.get_column_letter(col)].hidden=True
 line=ws._charts[0];line.display_blanks='gap';line.visible_cells_only=False;line.x_axis.tickLblPos='low';line.x_axis.delete=False;line.y_axis.delete=False;line.y_axis.numFmt='0.0%';line.y_axis.crosses='min'
 table=Table(displayName='LockupEvents',ref=f'A{header}:M{header+len(events)}');table.tableStyleInfo=TableStyleInfo(name='TableStyleLight1',showRowStripes=True);ws.add_table(table);raw.sheet_state='hidden';raw.sheet_view.showGridLines=False


def bind_desk_charts(wb):
 from openpyxl.chart.series import SeriesLabel
 # Dynamic names keep axes bounded by the selected history length.
 for k in range(4):
  col=__import__('openpyxl').utils.get_column_letter(k*9+1);prem=__import__('openpyxl').utils.get_column_letter(k*9+7);count=__import__('openpyxl').utils.get_column_letter(k*9+9)
  for suffix,c in [('Dates',col),('Premium',prem)]:
   name=f'AHCompare{k+1}{suffix}';wb.defined_names.add(DefinedName(name,attr_text=f"'AH Compare'!${c}$5:INDEX('AH Compare'!${c}$5:${c}$2204,'AH Compare'!${count}$3)"))
  series=wb['AH']._charts[1].series[k];series.yVal=NumDataSource(numRef=NumRef(f=f"'AH Compare'!AHCompare{k+1}Premium"));series.xVal=AxDataSource(numRef=NumRef(f=f"'AH Compare'!AHCompare{k+1}Dates"));series.tx=SeriesLabel(strRef=StrRef(f="AH!$B$4" if k==0 else f"AH!$K${27+k}"))
 ch=wb['AH']._charts[1];ch.scatterStyle='line';ch.x_axis.numFmt='mmm-yy';ch.x_axis.delete=False;ch.x_axis.tickLblPos='low';
 for sr in ch.series:sr.marker.symbol='none'
 ch.y_axis.crosses='min';ch.display_blanks='gap';ch.visible_cells_only=False
 bind_peer_charts(wb)
 for k,sr in enumerate(wb['Lock-up']._charts[1].series):
  if k:sr.tx=SeriesLabel(strRef=StrRef(f"'Lock-up'!$B${31+k}"))
 for name in ['AH Delta','AH Recent','AH Compare','AH Compare Live','Lock Compare','Lock Matrix','Peer Data','Peer Live','Peer Chart','HK Stocks']:wb[name].sheet_state='hidden';wb[name].sheet_view.showGridLines=False


def bind_peer_charts(wb):
 from openpyxl.chart.series import SeriesLabel
 for col,suffix in [('A','Dates'),('B','A'),('C','B'),('D','Spread')]:wb.defined_names.add(DefinedName('PeerChart'+suffix,attr_text=f"INDEX('Peer Chart'!${col}$5:${col}$3004,MAX(1,'Peer Chart'!$J$3-4)):INDEX('Peer Chart'!${col}$5:${col}$3004,MAX(MAX(1,'Peer Chart'!$J$3-4),'Peer Chart'!$J$2))"))
 for ci,ch in enumerate(wb['Peer Trades']._charts):
  for si,sr in enumerate(ch.series):
   sr.cat=AxDataSource(numRef=NumRef(f="'Peer Chart'!PeerChartDates"));sr.val=NumDataSource(numRef=NumRef(f="'Peer Chart'!PeerChart"+('Spread' if ci else 'A' if si==0 else 'B')))
  old=ch.x_axis;ch.x_axis=DateAxis(axId=old.axId,crossAx=old.crossAx,axPos='b',numFmt='mmm-yy',baseTimeUnit='days',delete=False,tickLblPos='low');
  if ci==0:
   for si,sr in enumerate(ch.series):sr.tx=SeriesLabel(strRef=StrRef(f"'Peer Chart'!$H${3+si}"))
  ch.display_blanks='gap';ch.visible_cells_only=False
  ch.x_axis.majorGridlines=None;ch.x_axis.minorGridlines=None
  for sr in ch.series:sr.marker.symbol='none';sr.smooth=False
