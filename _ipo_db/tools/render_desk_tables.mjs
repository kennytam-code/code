import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const root=new URL('../',import.meta.url);
const phase=process.argv.includes('--before')?'before':'after';
for(const [name,range] of [['Database','A1:Q13'],['Pipeline','A1:L22']]){
 const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(new URL('out/_presentation_'+name+'.xlsx',root).pathname));
 const image=await wb.render({sheetName:name,range,scale:1,format:'png'});
 await fs.writeFile(new URL('out/'+phase+'_'+name+'.png',root),new Uint8Array(await image.arrayBuffer()));
 console.log('Rendered',phase,name);
}
