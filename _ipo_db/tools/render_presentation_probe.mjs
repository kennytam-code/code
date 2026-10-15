import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
for(const [name,range] of (process.argv.includes('--sector')?[['AH','J55:O70']]:[['AH','J1:O70'],['Peer Trades','A1:H43']])){
 const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(fileURLToPath(new URL('../out/_presentation_'+name.replace('-','')+'.xlsx',import.meta.url))));
 wb.worksheets.getItem(name).charts.items.forEach((ch,ci)=>{
  ch.series.items.forEach((s,j)=>{const end=s.valuesSource?.match(/\$(\d+)$/)?.[1],col=String.fromCharCode(65+j*2);if(end)s.categoriesSource=`'Chart ${ci}'!$${col}$2:$${col}$${end}`;});
  if(name==='AH'&&ch.type==='combo'){const end=Number(ch.series.items[0].valuesSource.match(/\$(\d+)$/)[1]),data=wb.worksheets.getItem('Chart '+ci).getRange('A2:F'+end).values;ch.groups=[{type:'line',axis:'primary',series:[{name:'A/H premium · left',values:data.map(r=>r[1]),line:{fill:'#315B7D',width:2}}]},{type:'line',axis:'secondary',series:[{name:'CSI 300 return · right',values:data.map(r=>r[3]),line:{fill:'#757F88',width:1.6}},{name:'A-share return · right',values:data.map(r=>r[5]),line:{fill:'#9B4A47',width:1.6}}]}];ch.categories=data.map(r=>r[0]);for(const t of ch.getAxisTargets())if(t.axis==='y')ch.applyAxis(t.axisId,{numberFormatCode:'0%'});ch.displayBlanksAs='gap';}
  ch.xAxis=ch.type==='scatter'?{numberFormatCode:'mmm-yy',numberFormatSourceLinked:false,textStyle:{typeface:'Arial',fontSize:10}}:{axisType:'textAxis',textStyle:{typeface:'Arial',fontSize:10}};
 });
 const blob=await wb.render({sheetName:name,range,scale:1,format:'png'});await fs.writeFile(new URL('../out/verified_'+name.replace('-','')+'.png',import.meta.url),new Uint8Array(await blob.arrayBuffer()));console.log('Rendered actual',name);
}
