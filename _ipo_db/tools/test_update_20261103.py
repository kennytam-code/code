"""Regression fixtures for add-in output ownership, valuation modes and IPO peers.

This is returned-data/formula validation, not a Bloomberg terminal execution.
"""
import sys,json,re,zipfile,hashlib,math
from pathlib import Path
import xml.etree.ElementTree as E
import numpy as np,formulas,schedula
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value,ci,ec
from bloomberg_mode_repair import apply,HISTORY
from pipeline_dedupe import company_key
from build_xlsx import load
path=ROOT/'out/HK_IPO_Database_v1.xlsx';report={'terminal_tested':False,'fixtures':0}
def evaluate(text,fix):
    fn=formulas.Parser().ast('='+text)[1].compile()
    return fn(*[fix[k] for k in fn.inputs]).item()
def eq(got,want):
    assert (math.isclose(float(got),want,abs_tol=1e-10) if isinstance(want,(int,float)) else got==want),(got,want)
    report['fixtures']+=1
with zipfile.ZipFile(path) as z:
    assert z.testzip() is None
    _,_,sheets=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
    def cells(name):return nodes(E.fromstring(z.read(sheets[name])))
    ah=cells('AH');delta=cells('AH Delta');db=cells('Database');val=cells('Valuation Data');sc=cells('Screener');calc=cells('Calc (scoring engine)')
    count=0
    for name in HISTORY:
        cs=cells(name)
        for addr,c in cs.items():
            f=c.find(q('f'))
            if f is None or 'BDH(' not in f.text:continue
            assert f.get('t') is None and f.get('ref') is None,(name,addr,f.attrib)
            assert '@' not in f.text and '"DtFmt=D"' in f.text
            assert ('AH!$E$4' if name=='AH Recent' else 'AH!$H$4') in f.text
            col=ci(re.match('[A-Z]+',addr)[0]);r=int(re.search(r'\d+',addr)[0]);last=r+64 if name=='AH Recent' else 2204
            for other,cell in cs.items():
                cc=ci(re.match('[A-Z]+',other)[0]);rr=int(re.search(r'\d+',other)[0])
                if other!=addr and col<=cc<=col+1 and r<=rr<=last:
                    assert cell.find(q('f')) is None and not value(cell),(name,addr,other)
            count+=1
    eq(count,161);eq(value(db['B2']),'All')
    assert value(ah['E4'])==value(ah['H4'])=='Stored'
    # Idempotent migration does not alter controls after a user chooses a mode.
    parts={sheets[n]:z.read(sheets[n]) for n in HISTORY+['Database','Valuation Data']};original=dict(parts)
    apply(parts,sheets,ROOT);assert parts==original
    mode=val['BM1'].find(q('f')).text
    for raw,want in [('All','All'),(' all ','All'),('Selected','Selected'),('Off','Off'),('off','Off'),('bad','Invalid mode')]:eq(evaluate(mode,{'DATABASE!B2':raw}),want)
    # Follow real aliases through SelectedDeal, including numeric/padded codes.
    def resolve(a):
        c=calc[a];f=c.find(q('f'))
        if f is None:return value(c)
        expr=f.text.replace('$','')
        if re.fullmatch(r'[A-Z]+\d+',expr):return resolve(expr)
        if '!' in expr:
            sn,ad=expr.split('!');sn=sn.strip("'")
            if sn not in aliases:aliases[sn]=cells(sn)
            return value(aliases[sn][ad])
        raise AssertionError(expr)
    selected=calc['AR1'].find(q('f')).text
    fn=formulas.Parser().ast('='+selected)[1].compile()
    def vector(key):
        a,b=key.split(':');co=re.match('[A-Z]+',a)[0]
        return np.array([[resolve(co+str(i))] for i in range(int(re.search(r'\d+',a)[0]),int(re.search(r'\d+',b)[0])+1)],dtype=object)
    aliases={'Database':db}
    arrays={k:vector(k) for k in fn.inputs if ':' in k}
    deals,_,_,pipe,_=load();bycode={str(p.get('code')):p for p in pipe}
    codes=['0054','9621','7672','9917','2206','2065','2681','1821']
    assert all(c in bycode for c in codes)
    assert len(pipe)==23 and len({company_key(p['name']) for p in pipe})==23
    for code in codes+['2384','9976']:
        target=bycode[code]['name'] if code in bycode else next(d['name'] for d in deals if d['code']==code)
        for inp in [str(int(code)),int(code),code.zfill(5),code+' HK Equity',target]:
            fix={**arrays,'AQ1':str(inp).strip().lower(),'SCREENER!B5':inp}
            eq(fn(*[fix[k] for k in fn.inputs]).item(),target)
    n=len(deals);hrow=8+8*n;last=8+8*(n-1)
    # Selected and comparison issuer codes must activate; others must not.
    gate=val['BM8'].find(q('f')).text
    base={'BM1':'Selected','A8':'9600 HK Equity','A'+str(hrow):'9600 HK Equity','DATABASE!A5':'9600',"SCREENER!C21:C35":np.array([['9976'],['2384']]+[['']]*13,dtype=object)}
    for mode,ticker,code,want in [('Selected','9600 HK Equity','9600',True),('Selected','1 HK Equity','9976',True),('Selected','1 HK Equity','9999',False),('All','1 HK Equity','9999',True),('Off','9600 HK Equity','9600',False),('Invalid mode','9600 HK Equity','9600',False)]:
        eq(evaluate(gate,{**base,'BM1':mode,'A'+str(hrow):ticker,'DATABASE!A5':code}),want)
    # Each of five selected H outputs resolves issuer results before fallback.
    for k,out in enumerate(['L','M','X','AH','AR']):
        f=val['L'+str(hrow+8*k)].find(q('f')).text;compiled=formulas.Parser().ast('='+f)[1].compile()
        tickers=np.full((last-7,1),'',dtype=object);multiples=tickers.copy()
        for i in range(n):tickers[8*i,0]=str(int(deals[i]['code']))+' HK Equity';multiples[8*i,0]=10+i/10
        for i in [0,n//2,n-1]:
            fix={key:('All' if key in ['BM1','DATABASE!B2'] else tickers if key.startswith('A8:') else multiples if key.startswith(out+'8:') else tickers[8*i,0] if key=='A'+str(hrow) else schedula.EMPTY) for key in compiled.inputs}
            eq(compiled(*[fix[k] for k in compiled.inputs]).item(),10+i/10)
            fix['BM1']='Off';eq(compiled(*[fix[k] for k in compiled.inputs]).item(),'Off')
    for rr in range(hrow,hrow+33,8):
        for col in ['C','AU','BD']:
            c=val.get(col+str(rr));f=c.find(q('f')) if c is not None else None
            if f is not None and ('BDP(' in f.text or 'BQL(' in f.text):assert f.text.startswith('IF(AND(OR($BM$1='),f.text
    # Reference arithmetic continues to use all three independent calendars.
    def history(ds,ps):return np.array(ds,dtype=object).reshape(-1,1),np.array(ps,dtype=object).reshape(-1,1)
    hs,hp=history(['Date',46280,46291,46316,46318,46322,''],['PX_LAST',9,10,12,12,14,''])
    aa,ap=history(['Date',46280,46291,46315,46318,46322,''],['PX_LAST',18,20,24,24,28,''])
    fx,fp=history(['Date',46280,46291,46316,46318,46322,''],['PX_LAST',1.1,1.1,1.1,1.1,1.1,''])
    base={'AH!E4':'Bloomberg','W3':46323,'F3':46200,'B3':.25,'C3':.35,'U3':.15}
    base.update({c+'3':0 for c in ['J','K','L','M','O','P']});base.update({c+'3':1 for c in ['R','S','T']})
    raw={"'AH RECENT'!A5:A69":hs,"'AH RECENT'!B5:B69":hp,"'AH RECENT'!D5:D69":aa,"'AH RECENT'!E5:E69":ap,"'AH RECENT'!G5:G69":fx,"'AH RECENT'!H5:H69":fp}
    compiled={}
    def graph(out,override=None):
        values={**base,**raw,**(override or {})}
        def get(key):
            if key in values:return values[key]
            if key not in compiled:compiled[key]=formulas.Parser().ast('='+delta[key].find(q('f')).text)[1].compile()
            fn=compiled[key];values[key]=fn(*[get(k) for k in fn.inputs]).item();return values[key]
        return get(out)
    for out in ['D3','E3','AD3']:
        eq(graph(out),1.2);eq(graph(out,{'W3':''}),'No date');eq(graph(out,{'F3':46323}),'Too new')
    eq(graph('D3',{'J3':46310,'K3':46320,'R3':.5}),3.4)
    eq(graph('D3',{'J3':46310,'K3':46310,'R3':.5}),1.2)
    # Same historical inputs; new work is future-offering data and formula wiring.
    report.update(ipo_rows=n,pipeline_rows=len(pipe),new_pipeline_codes=codes,unlocked_bdh_anchors=count,default_valuations=value(db['B2']),workbook_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
(ROOT/'out/update_20261103_checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
