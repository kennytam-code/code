import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const [source,sheet,range,output]=process.argv.slice(2);
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const png=await wb.render({sheetName:sheet,range,scale:1.2,format:'png'});
await fs.writeFile(output,new Uint8Array(await png.arrayBuffer()));
console.log('Rendered',output);
