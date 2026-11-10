"""Nov4 native layout and actual-formula fixtures; no Bloomberg terminal run."""
import json,sys,zipfile,re,math,hashlib
from pathlib import Path
import xml.etree.ElementTree as E
import formulas,numpy as np
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from patch_peer_workbook import maps,q
from reflow_monitors import nodes,value,ci
from ah_identity_caps import apply,CAP_FIELD
path=ROOT/'out/HK_IPO_Database_v1.xlsx';before=ROOT.parent/'before.xlsx'
report={'live_bloomberg_tested':False,'fixtures':0}
def check(got,want):
    assert math.isclose(float(got),want,abs_tol=1e-10) if isinstance(want,(int,float)) else got==want,(got,want)
    report['fixtures']+=1
with zipfile.ZipFile(path) as z,zipfile.ZipFile(before) as old:
    assert z.testzip() is None
    _,_,s=maps({p:z.read(p) for p in ['xl/workbook.xml','xl/_rels/workbook.xml.rels']})
    def doc(name,archive=z):return E.fromstring(archive.read(s[name]))
    ah=nodes(doc('AH'));prior=nodes(doc('AH',old));market=nodes(doc('Market Data'))
    end=79;mend=74
    assert value(ah['A7'])=='Company' and value(ah['F7'])=='A cap\nCNY m'
    assert value(ah['G7'])=='H cap\nHKD m' and value(ah['J7'])=='1D Δ\n(pp)'
    for row in range(8,end+1):
        j=row-5
        check(value(ah[f'A{row}']),value(market[f'S{j}']))
        check(value(ah[f'B{row}']),value(prior[f'A{row}']))
        check(value(ah[f'C{row}']),value(prior[f'B{row}']))
        for a,b in [('E','H'),('F','I'),('G','J'),('H','K'),('I','L')]:check(value(ah[b+str(row)]),value(prior[a+str(row)]))
        for col,ticker in [('F','R'),('G','Q')]:
            f=ah[col+str(row)].find(q('f')).text
            assert f==f'IF($E$4<>"Bloomberg","—",IFERROR(BDP(\'Market Data\'!${ticker}{j},"{CAP_FIELD}"),"Unavailable"))'
            assert 'BDH' not in f and ah[col+str(row)].find(q('f')).get('t') is None
    def evaluate(addr,inputs,substitutions=None):
        f=ah[addr].find(q('f')).text
        for a,b in (substitutions or {}).items():f=f.replace(a,b)
        fun=formulas.Parser().ast('='+f)[1].compile()
        return fun(*[inputs[k] for k in fun.inputs]).item()
    for inp,want in [('9607','9607'),(9607,'9607'),('09607','9607'),('2384','2384'),('a',''),('', ''),(0,''),(-1,''),(2.3,''),(100000,'')]:check(evaluate('S78',{'M60':inp}),want)
    for inp,want in [('09607','9607 HK Equity'),('2384','2384 HK Equity')]:check(evaluate('S84',{'M60':inp,'S78':inp[-4:]}),want)
    check(evaluate('S84',{'M60':'bad','S78':''}),'')
    for manual,auto,want in [('', '002384 CH Equity',2384),('688036','002384.SZ',688036),('000001','',1),('bad','002384.SZ',''),('','','')]:check(evaluate('P64',{'O60':manual,'S79':auto}),want)
    for override,source,want in [('',86.8,86.8),(90,86.8,90),(0,86.8,''),(-1,86.8,''),('',0,''),('','', '')]:check(evaluate('P65',{'Q60':override,'S80':source}),want)
    for a,fx,want in [(100,1.1,110),(0,1.1,'Awaiting prices'),('',1.1,'Awaiting prices'),(100,'#N/A','Awaiting prices')]:check(evaluate('P69',{'P67':a,'P68':fx}),want)
    for a,h,want in [(110,100,.1),(90,100,-.1),(100,100,0),(110,0,'Awaiting prices'),(110,'','Awaiting prices')]:check(evaluate('P72',{'P69':a,'P70':h}),want)
    for a,h,want in [(110,80,.375),(110,'','Awaiting prices')]:check(evaluate('P73',{'P69':a,'P65':h}),want)
    # Real formula branches: quoted price is live even when the roster is Stored.
    hvalues=np.array([[10+i] for i in range(72)],dtype=object)
    for mode,index,want in [('Stored',1,777),('Bloomberg',1,10),('Bloomberg',0,777)]:
        check(evaluate('P70',{'S84':'2384 HK Equity','E4':mode,'S82':index,"'MARKET DATA'!AD3:AD74":hvalues,'ZZ1':777},{'BDP($S$84,"LAST_PRICE")':'ZZ1'}),want)
    for mode,paired,want in [('Stored',True,777),('Bloomberg',True,10),('Bloomberg',False,777)]:
        check(evaluate('P67',{'S81':'002384 CH Equity','E4':mode,'S83':paired,'S82':1,"'MARKET DATA'!AC3:AC74":hvalues,'ZZ1':777},{'BDP($S$81,"LAST_PRICE")':'ZZ1'}),want)
    for mode,want in [('Stored','—'),('Bloomberg',12500)]:check(evaluate('F8',{'E4':mode,'ZZ1':12500},{f'BDP(\'Market Data\'!$R3,"{CAP_FIELD}")':'ZZ1'}),want)
    assert not any('BDH(' in f.text for a,c in ah.items() if 58<=int(re.search(r'\d+',a)[0])<=76 and ci(re.match('[A-Z]+',a)[0])>=13 for f in c.findall(q('f')))
    # Nothing in the enlarged table is merged or covered by a chart.
    for m in doc('AH').iter(q('mergeCell')):
        ends=m.get('ref').split(':');coords=[(ci(re.match('[A-Z]+',a)[0]),int(re.search(r'\d+',a)[0])) for a in ends]
        assert not (coords[0][0]<=12 and coords[-1][0]>=1 and coords[0][1]<=end and coords[-1][1]>=7),m.get('ref')
    # All existing tabs retain data. Only AH references change in dependent builds.
    changed=[p for p in old.namelist() if old.read(p)!=z.read(p)]
    expected={s['AH'],'xl/styles.xml','xl/workbook.xml','xl/drawings/monitor_drawing2.xml','xl/tables/monitor_table2.xml',s['Live History'],s['AH Compare'],s['AH Reference'],s['Chart Data'],'xl/charts/monitor_chart4.xml','xl/comments/monitor_comment1.xml','xl/drawings/monitor_commentsDrawing1.vml'}
    assert set(changed)<=expected,set(changed)-expected
    notes=E.fromstring(old.read('xl/comments/monitor_comment1.xml'));newnotes=E.fromstring(z.read('xl/comments/monitor_comment1.xml'))
    for a,b in zip(notes.iter(q('comment')),newnotes.iter(q('comment'))):
        assert a.get('ref')[0] in ['E','F']
        check(b.get('ref'),{'E':'H','F':'I'}[a.get('ref')[0]]+a.get('ref')[1:])
        a.set('ref',b.get('ref'));assert E.tostring(a)==E.tostring(b)
    for name in ['Database','Screener','IPO Live','Valuation Data','AH Delta','AH Recent','AH History','Market Data','Pipeline']:
        assert z.read(s[name])==old.read(s[name]),name
    for p in old.namelist():
        if p.startswith('xl/charts/') and p.endswith('.xml'):
            a=E.fromstring(old.read(p));b=E.fromstring(z.read(p))
            for x,y in zip(a.iter(),b.iter()):
                if x.text!=y.text:
                    assert x.tag.endswith('}f') and 'AH!' in x.text,(p,x.text,y.text)
                    assert x.text in ['AH!$K$28','AH!$K$29','AH!$K$30'] and x.text.replace('$K$','$N$')==y.text,(p,x.text,y.text)
                    x.text=y.text
            assert E.tostring(a)==E.tostring(b),p
    # Migration is idempotent; it does not replace edited user controls.
    parts={s['AH']:z.read(s['AH'])};apply(parts,s,ROOT);assert parts[s['AH']]==z.read(s['AH'])
    report.update(pairs=72,added_market_cap_requests=144,added_historical_requests=0,changed_package_parts=changed,all_existing_chart_series_unchanged=True,unrelated_data_unchanged=True,workbook_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
(ROOT/'out/ah_identity_caps_checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
