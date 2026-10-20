"""Execute the delivered identifier formulas and prove narrow native preservation."""
import json,re,sys,hashlib,zipfile,xml.etree.ElementTree as E
from pathlib import Path
import formulas,numpy as np
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value
out=ROOT/'out/screener_ah_20261020'
with zipfile.ZipFile(out/'baseline.xlsx') as z:before={p:z.read(p) for p in z.namelist()}
with zipfile.ZipFile(ROOT/'out/HK_IPO_Database_v1.xlsx') as z:
    assert z.testzip() is None;after={p:z.read(p) for p in z.namelist()}
assert set(before)==set(after)
wb,_,sheets=maps(after);sc=nodes(E.fromstring(after[sheets['Screener']]));en=nodes(E.fromstring(after[sheets['Calc (scoring engine)']]))
changed={p for p in after if after[p]!=before[p]}
assert changed=={sheets['Screener'],sheets['Calc (scoring engine)'],'xl/styles.xml','xl/workbook.xml'},changed
for sheet in ['Screener','Calc (scoring engine)']:
    old=nodes(E.fromstring(before[sheets[sheet]]));new=nodes(E.fromstring(after[sheets[sheet]]))
    for a,c in old.items():
        if sheet=='Screener' and a in ['A5','B5','E5']:continue
        assert E.tostring(c)==E.tostring(new[a]),(sheet,a)
    assert {a for a in new if a not in old}<={'AW'+str(i) for i in range(2,1000)}
assert value(sc['B5'])==value(nodes(E.fromstring(before[sheets['Screener']]))['B5'])
assert len([n for n in wb.find(q('definedNames')) if n.get('name').startswith('W_')])==11
assert next(n for n in E.fromstring(after[sheets['Screener']]).iter(q('dataValidation')) if n.get('sqref')=='B5').find(q('formula1')).text=='AllTargetCodes'
cache={n:nodes(E.fromstring(after[p])) for n,p in sheets.items() if n in ['Pipeline','Database','Calc (scoring engine)']}
def val(sheet,addr):
    c=cache[sheet][addr.replace('$','')];f=c.find(q('f'))
    if f is None:return value(c)
    ref=f.text.replace('$','')
    if '!' in ref:
        name,ref=ref.rsplit('!',1);return val(name.strip("'"),ref)
    return val(sheet,ref)
def arr(col,start,end):return np.array([[val('Calc (scoring engine)',col+str(i))] for i in range(start,end+1)],dtype=object)
normalize=formulas.Parser().ast('='+en['AQ1'].find(q('f')).text)[1].compile()
resolve=formulas.Parser().ast('='+en['AR1'].find(q('f')).text)[1].compile()
fixed={}
for k in resolve.inputs:
    if ':' not in k:continue
    col,start,end=re.fullmatch(r'([A-Z]+)(\d+):[A-Z]+(\d+)',k).groups()
    fixed[k]=arr(col,int(start),int(end))
def lookup(key):
    fixture={**fixed,'SCREENER!B5':key,'AQ1':normalize(key).item()}
    return resolve(*[fixture[k] for k in resolve.inputs]).item()
aliases={val('Calc (scoring engine)',a):val('Calc (scoring engine)','AR'+a[2:]) for a in en if re.fullmatch(r'AQ\d+',a) and int(a[2:])>=3}
codes=sorted({str(int(k)) for k in aliases if k.isdigit()},key=int);count=0
for code in codes:
    for key in [code,int(code),code.zfill(5)]:assert lookup(key)==aliases[code],(key,lookup(key),aliases[code]);count+=1
for key in ['9607 HK Equity','03223.HK',' 9976 ','Red Avenue',value(sc['B5'])]:assert lookup(key)==aliases[key.strip().lower()];count+=1
for key in ['', '999999','Unknown issuer']:assert lookup(key)=='';count+=1
dropdown=[value(c) for a,c in en.items() if re.fullmatch(r'AW\d+',a) and int(a[2:])>=3]
assert len(dropdown)==len(set(dropdown));assert all(c in dropdown for c in codes)
assert all(lookup(k) for k in dropdown)
report={'passed':True,'lookup_cases':count,'codes':len(codes),'dropdown_entries':len(dropdown),'changed_parts':sorted(changed),'all_existing_business_cells_formulas_and_charts_preserved':True,'live_bloomberg_execution':False,'sha256':hashlib.sha256((ROOT/'out/HK_IPO_Database_v1.xlsx').read_bytes()).hexdigest()}
(out/'workbook_checks.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS',count,'actual Excel formula lookups;',len(codes),'H codes; code dropdown, names, ticker aliases, unknown inputs and native preservation')
