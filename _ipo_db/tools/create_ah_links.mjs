import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const root=new URL('../',import.meta.url);
const config={
 database:'IF($BQ{row}="","N/A",IFERROR(INDEX(AH!$I$8:$I${end},MATCH(TEXT(VALUE($A{row}),"0000"),AH!$C$8:$C${end},0)),"Pair missing"))',
 h_quote:'IF(AH!$E$4="Bloomberg",IF(\'IPO Live\'!$B$4="Bloomberg",INDEX(\'IPO Live\'!$D$8:$D${lend},MATCH(Q{row},\'IPO Live\'!$A$8:$A${lend},0)),BDP(Q{row},"LAST_PRICE")),IF(AH!$E$4="Stored",AG{row},"No source"))',
 ah_current:'IF(ISNUMBER(\'Market Data\'!AE{row}),\'Market Data\'!AE{row},IF(\'Market Data\'!AE{row}="","No quote",\'Market Data\'!AE{row}))'
};
const wb=Workbook.create();const db=wb.worksheets.add('Database');const ah=wb.worksheets.add('AH');
db.getRange('A5').values=[['03228']];db.getRange('BQ5').values=[['603228.SS']];
ah.getRange('C8:C10').values=[['0668'],['3228'],['3757']];ah.getRange('I8:I10').values=[[.2],[.35],[-.1]];
db.getRange('BT5').formulas=[['='+config.database.replaceAll('{row}','5').replaceAll('{end}','10')]];
const verify=(want)=>{wb.recalculate();let v=db.getRange('BT5').values[0][0];if(v!==want)throw Error(JSON.stringify({v,want}));};
verify(.35);db.getRange('A5').values=[[3228]];verify(.35);
ah.getRange('I9').values=[[0]];verify(0);
ah.getRange('I9').values=[['No quote']];verify('No quote');
ah.getRange('C8:C10').values=[['3228'],['3757'],['0668']];ah.getRange('I8:I10').values=[[.35],[-.1],[.2]];verify(.35);
db.getRange('A5').values=[['9999']];verify('Pair missing');
db.getRange('BQ5').values=[['']];verify('N/A');
db.getRange('A5').values=[['3228']];db.getRange('BQ5').values=[['603228.SS']];verify(.35);
wb.recalculate();console.log((await wb.inspect({kind:'table',range:'Database!BQ5:BT5',include:'values,formulas',tableMaxRows:2,tableMaxCols:4})).ndjson);
await fs.writeFile(new URL('data/ah_link_formulas.json',root),JSON.stringify(config,null,2)+'\n');
await (await SpreadsheetFile.exportXlsx(wb)).save(new URL('out/ah_link_fixture.xlsx',root).pathname);
console.log('Artifact lookup fixtures passed: code padding, zero, missing, sort, non-pair.');
