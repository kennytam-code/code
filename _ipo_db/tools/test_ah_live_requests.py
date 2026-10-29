"""Native package preservation and actual AH formula response fixtures.

This does not execute Bloomberg; it tests workbook wiring and returned-data math.
"""
import sys,json,re,zipfile,math,hashlib
from pathlib import Path
import xml.etree.ElementTree as E
import numpy as np,formulas
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value,ci,ec
from ah_live_requests import apply

folder=ROOT/'out/ah_live_fix_20261029'
before=Path(sys.argv[1]) if len(sys.argv)>1 else folder/'before.xlsx'
after=Path(sys.argv[2]) if len(sys.argv)>2 else folder/'fixed.xlsx'
changed=['AH','AH Delta','AH Recent','Market Data','Live History','Chart Data','AH Reference','AH Compare','AH Compare Live']
report={'terminal_tested':False,'fixtures':0}

def eq(got,want):
    if isinstance(want,(int,float)):
        assert isinstance(got,(int,float,np.number)) and math.isclose(float(got),want,abs_tol=1e-10),(got,want)
    else:assert got==want,(got,want)
    report['fixtures']+=1

def compile_f(text):return formulas.Parser().ast('='+text)[1].compile()
def evaluate(text,fixture):
    fn=compile_f(text)
    return fn(*[fixture[k] for k in fn.inputs]).item()

with zipfile.ZipFile(before) as old,zipfile.ZipFile(after) as new:
    assert new.testzip() is None
    assert set(old.namelist())==set(new.namelist())
    _,_,sheets=maps({p:new.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
    permitted={sheets[s] for s in changed}
    untouched=0
    for p in old.namelist():
        if p not in permitted:
            assert old.read(p)==new.read(p),p
            untouched+=1
    report['unchanged_package_parts']=untouched
    def cells(z,name):return nodes(E.fromstring(z.read(sheets[name])))
    ah=cells(new,'AH');delta=cells(new,'AH Delta');md=cells(new,'Market Data')
    for name in ['AH','Market Data']:
        a=cells(old,name);b=cells(new,name)
        for addr,cell in a.items():
            if name=='AH' and addr in ['D4','G4','H4']:continue
            assert value(cell)==value(b[addr]),(name,addr,'cached value changed')
    report['stored_ah_and_market_caches']='unchanged'
    assert value(ah['E4'])==value(ah['H4'])=='Stored'
    assert value(ah['D4'])=='Quotes' and value(ah['G4'])=='Charts'
    ahdoc=E.fromstring(new.read(sheets['AH']))
    assert any(x.get('sqref')=='H4' and x.find(q('formula1')).text=='"Stored,Bloomberg"' for x in ahdoc.iter(q('dataValidation')))
    for p in ['P12','J24']:
        assert '$H$4' in ah[p].find(q('f')).text
    assert '$E$4' in ah['P12'].find(q('f')).text
    # Preserve independent manual IPO-price checker and the entire sector table.
    oa=cells(old,'AH')
    for addr,cell in oa.items():
        if int(re.search(r'\d+',addr)[0])>=58:
            if re.match(r'[A-I]\d+$',addr) and int(re.search(r'\d+',addr)[0])<=79:continue
            assert E.tostring(cell)==E.tostring(ah[addr]),addr
    all_bdh=[]
    for name in ['AH Recent','Live History','AH Compare Live','AH Reference']:
        cs=cells(new,name);rectangles=[]
        for addr,cell in cs.items():
            f=cell.find(q('f'))
            if f is None or 'BDH(' not in f.text:continue
            assert f.get('t')=='array' and '"DtFmt=D"' in f.text
            match=re.fullmatch(r'([A-Z]+)(\d+):([A-Z]+)(\d+)',f.get('ref'))
            a,b,c,d=match.groups();x,y,xx,yy=ci(a),int(b),ci(c),int(d)
            assert xx==x+1 and f.get('ref').startswith(addr+':')
            assert yy-y+1==(65 if name=='AH Recent' else 2200)
            assert 'AH!$E$4' in f.text if name=='AH Recent' else 'AH!$H$4' in f.text
            assert f.text.count('BDH(')==1 and '@' not in f.text
            for u,v,uu,vv in rectangles:assert xx<u or uu<x or yy<v or vv<y
            rectangles.append((x,y,xx,yy));all_bdh.append((name,addr))
        report[name+'_bdh']=len(rectangles)
    assert len(all_bdh)==161 and report['AH Recent_bdh']==145
    for r in range(3,75):
        for col in ['AE','AF','AG','AI','AL','AO','AS','AV','AY']:
            f=delta[f'{col}{r}'].find(q('f'))
            assert f.get('t')=='array' and f.get('ref')==f'{col}{r}'
        for col in ['AC','AD']:
            f=md[f'{col}{r}'].find(q('f')).text
            assert f.count('BDP(')==1 and '"LAST_PRICE"' in f and 'IFERROR' not in f
        for col in ['D','E','AD']:
            f=delta[f'{col}{r}'].find(q('f')).text
            assert 'MATCH(' not in f and 'BDH(' not in f
        assert f'W{r}-7' in delta[f'D{r}'].find(q('f')).text
        assert f'EDATE(W{r},-1)' in delta[f'E{r}'].find(q('f')).text
    # Applying the final stage again must have no effect.
    parts={sheets[n]:new.read(sheets[n]) for n in changed}
    original=dict(parts);apply(parts,sheets,ROOT);assert original==parts
    report['idempotent']=True
    def formulas_size(z):
        cs=cells(z,'AH Delta');fs=[c.find(q('f')).text for c in cs.values() if c.find(q('f')) is not None]
        return {'formula_characters':sum(map(len,fs)),'history_range_references':sum(len(re.findall("'AH Recent'!",f)) for f in fs)}
    report['before_delta']=formulas_size(old);report['after_delta']=formulas_size(new)
    assert report['after_delta']['formula_characters']<report['before_delta']['formula_characters']

    # Actual emitted Excel expressions; mixed Bloomberg headers, blanks, error
    # text and date forms, plus independently dated A/H entitlement adjustments.
    for datum in [46323,20261028,'20261028','2026-10-28','10/28/2026']:
        eq(evaluate(delta['W3'].find(q('f')).text,{'V3':datum}),46323)
    for datum in ['', 'Requesting Data...', '#N/A']:
        eq(evaluate(delta['W3'].find(q('f')).text,{'V3':datum}),'')
    def history(dates,prices):return np.array(dates,dtype=object).reshape(-1,1),np.array(prices,dtype=object).reshape(-1,1)
    dates,prices=history(['Date',46310,46316,46320,'',46322],['Price',90,100,120,'','#N/A'])
    fn=compile_f(delta['AI3'].find(q('f')).text)
    fix={k:dates if 'A5:A69' in k else prices if 'B5:B69' in k else 46323 if k=='W3' else 'Bloomberg' for k in fn.inputs}
    eq(fn(*[fix[k] for k in fn.inputs]).item(),3)
    for key in fix:
        if key=='W3':fix[key]=46200
    eq(fn(*[fix[k] for k in fn.inputs]).item(),0)
    fix['AH!E4']='Stored';eq(fn(*[fix[k] for k in fn.inputs]).item(),0)

    # Formula graph evaluator for all three horizons using actual expressions.
    # Deliberately different calendars: H reference is 23 Oct, A 22 Oct, FX 23 Oct.
    hs,ps=history(['Date',46280,46291,46316,46318,46322,''],['PX_LAST',9,10,12,12,14,''])
    aa,pa=history(['Date',46280,46291,46315,46318,46322,''],['PX_LAST',18,20,24,24,28,''])
    fx,px=history(['Date',46280,46291,46316,46318,46322,''],['PX_LAST',1.1,1.1,1.1,1.1,1.1,''])
    base={'AH!E4':'Bloomberg','W3':46323,'F3':46200,'B3':0.25,'C3':0.35,'U3':0.15}
    for col in ['J','K','L','M','O','P']:base[col+'3']=0
    for col in ['R','S','T']:base[col+'3']=1
    raw={"'AH RECENT'!A5:A69":hs,"'AH RECENT'!B5:B69":ps,"'AH RECENT'!D5:D69":aa,"'AH RECENT'!E5:E69":pa,"'AH RECENT'!G5:G69":fx,"'AH RECENT'!H5:H69":px}
    def graph(out,overrides=None,raw_override=None):
        values=dict(base);values.update(overrides or {});values.update(raw);values.update(raw_override or {})
        def resolve(key):
            if key in values:return values[key]
            assert key in delta,key
            fn=compile_f(delta[key].find(q('f')).text)
            values[key]=fn(*[resolve(k) for k in fn.inputs]).item()
            return values[key]
        return resolve(out)
    for out,saved in [('D3',.25),('E3',.35),('AD3',.15)]:
        eq(graph(out),1.2)
        for saved_value in [saved,0,-.2]:
            key={'D3':'B3','E3':'C3','AD3':'U3'}[out]
            eq(graph(out,{'AH!E4':'Stored',key:saved_value}),saved_value)
        eq(graph(out,{'AH!E4':'Stored',{'D3':'B3','E3':'C3','AD3':'U3'}[out]:''}),'n.a.')
        eq(graph(out,{'W3':''}),'No date')
        eq(graph(out,{'F3':46323}),'Too new')
        eq(graph(out,raw_override={"'AH RECENT'!B5:B69":np.array([['#N/A']]*7,dtype=object)}),'No history')
    # Independent capital-action ex dates; H action applied before A action.
    eq(graph('D3',{'J3':46310,'K3':46320,'R3':.5}),3.4)
    eq(graph('D3',{'J3':46310,'K3':46310,'R3':.5}),1.2)
    eq(graph('D3',raw_override={"'AH RECENT'!D5:D69":np.array([['Date'],[46200],[46201],[46202],[46203],[46204],['']],dtype=object)}),'No history')
    eq(graph('D3',raw_override={"'AH RECENT'!G5:G69":np.array([['Date'],[46200],[46201],[46202],[46203],[46204],['']],dtype=object)}),'No history')
    for prior,want in [(.2,10),(.5,-20),(0,30),('No history','No history'),('Too new','Too new')]:
        eq(evaluate(ah['H8'].find(q('f')).text,{'F8':.3,"'AH DELTA'!D3":prior}),want)
    eq(evaluate(ah['H8'].find(q('f')).text,{'F8':'',"'AH DELTA'!D3":.2}),'No quote')

report['workbook_sha256']=hashlib.sha256(after.read_bytes()).hexdigest()
folder.mkdir(exist_ok=True,parents=True)
(folder/'formula_checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
