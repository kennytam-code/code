import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
for(const [name,range] of [['Screener','A52:O80'],['Peer Trades','A1:L43']]){
 const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(fileURLToPath(new URL('../out/_presentation_'+name.replace('-','')+'.xlsx',import.meta.url))));
 wb.worksheets.getItem(name).charts.items.forEach((ch,ci)=>{
  ch.series.items.forEach((s,j)=>{const end=s.valuesSource?.match(/\$(\d+)$/)?.[1],col=String.fromCharCode(65+j*2);if(end)s.categoriesSource=`'Chart ${ci}'!$${col}$2:$${col}$${end}`;});
  ch.xAxis={axisType:'textAxis',textStyle:{typeface:'Arial',fontSize:10}};
 });
 const blob=await wb.render({sheetName:name,range,scale:1,format:'png'});await fs.writeFile(new URL('../out/verified_'+name.replace('-','')+'.png',import.meta.url),new Uint8Array(await blob.arrayBuffer()));console.log('Rendered actual',name);
}
