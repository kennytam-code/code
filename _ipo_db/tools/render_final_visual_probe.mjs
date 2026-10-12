import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(new URL(process.argv.includes('--peers')?'../out/_peer_visual_probe.xlsx':'../out/_final_visual_probe.xlsx',import.meta.url).pathname));
// The preview importer drops native category references. Restore the
// disposable date-label helpers; the delivered workbook keeps its date axis.
if(process.argv.includes('--peers')){
 wb.worksheets.getItem('Peer Trades').charts.items.forEach((ch,ci)=>{
  ch.series.items.forEach((s,j)=>{const end=s.valuesSource.match(/\$(\d+)$/)[1],col=String.fromCharCode(65+j*2);s.categoriesSource=`'Chart ${ci}'!$${col}$2:$${col}$${end}`;});
  ch.xAxis={axisType:'textAxis',textStyle:{typeface:'Arial',fontSize:10}};
 });
}
for(const [sheetName,range] of (process.argv.includes('--peers')? [['Peer Trades','A1:L89']]: [['IPO Live','A1:O64'],['AH','A1:O64'],['Lock-up','A1:M60'],['Peer Trades','A1:L89'],['Screener','A1:O38'],['Database','A1:O38']])){
 const blob=await wb.render({sheetName,range,scale:1,format:'png'});await fs.writeFile(new URL('../out/final_'+sheetName.replace(/\W/g,'_')+'.png',import.meta.url),new Uint8Array(await blob.arrayBuffer()));console.log('Rendered',sheetName);
}
