import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(new URL('../out/_final_visual_probe.xlsx',import.meta.url).pathname));
for(const [sheetName,range] of [['IPO Live','A1:O64'],['AH','A1:O64'],['Lock-up','A1:M60'],['Peer Trades','A1:K63'],['Screener','A1:O38'],['Database','A1:O38']]){
 const blob=await wb.render({sheetName,range,scale:1,format:'png'});await fs.writeFile(new URL('../out/final_'+sheetName.replace(/\W/g,'_')+'.png',import.meta.url),new Uint8Array(await blob.arrayBuffer()));console.log('Rendered',sheetName);
}
