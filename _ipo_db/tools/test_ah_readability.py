"""The A/H visual edit must not alter any business data or formulas."""
from pathlib import Path
import sys,zipfile,hashlib,json
import xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'ipo_lib'))
from ah_chart_style import apply,c,a
before=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'out/ah_readability_20261019/baseline.xlsx'
after=ROOT/'out/ah_readability_20261019/HK_IPO_Database_v1.xlsx'
with zipfile.ZipFile(before) as old,zipfile.ZipFile(after) as new:
    assert old.namelist()==new.namelist()
    assert new.testzip() is None
    changed=[p for p in old.namelist() if old.read(p)!=new.read(p)]
    assert set(changed)=={'xl/charts/monitor_chart3.xml','xl/charts/monitor_chart4.xml','xl/drawings/monitor_drawing2.xml'},changed
    dp='xl/drawings/monitor_drawing2.xml';d=E.fromstring(old.read(dp));xd=lambda x:'{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}'+x
    d[0].find(xd('from')+'/'+xd('row')).text='7'
    assert E.tostring(d)==new.read(dp),'Only the first A/H chart top anchor may move below the frozen header'
    charts={}
    for p in changed:
        if p==dp:continue
        x,y=E.fromstring(old.read(p)),E.fromstring(new.read(p))
        for tag in ['xVal','yVal','cat','val']:
            assert [E.tostring(n) for n in x.iter(c(tag))]==[E.tostring(n) for n in y.iter(c(tag))],(p,tag)
        for tag in ['axId','crossAx','scaling','numFmt','dispBlanksAs']:
            assert [E.tostring(n) for n in x.iter(c(tag))]==[E.tostring(n) for n in y.iter(c(tag))],(p,tag)
        series=list(y.iter(c('ser')))
        colors=[s.find(c('spPr')).find(a('ln')).find(a('solidFill')).find(a('srgbClr')).get('val') for s in series]
        assert len(set(colors))==len(colors)
        assert all(int(s.find(c('spPr')).find(a('ln')).get('w'))>=20000 for s in series)
        assert y.find('.//'+c('legendPos')).get('val')=='t'
        assert all(n.get('val')=='0' for n in y.iter(c('smooth')))
        if 'chart3' in p:
            assert colors==['1D4E89','B17816','16857A'],colors
            assert series[1].find('.//'+a('prstDash')).get('val')!='solid'
            labels=[''.join(n.itertext()) for n in y.findall('.//'+c('valAx')+'/'+c('title'))]
            assert any('Premium (%)' in t for t in labels) and any('Price return (%)' in t for t in labels)
        charts[p]=new.read(p)
    apply(charts,{},ROOT)
    assert all(charts[p]==new.read(p) for p in charts),'Style patch must be idempotent'
    report={'passed':True,'changed_parts':changed,'all_cells_formulas_and_caches_unchanged':True,'chart_bindings_points_scales_unchanged':True,'style_patch_idempotent':True,'sha256':hashlib.sha256(after.read_bytes()).hexdigest()}
    (ROOT/'out/ah_readability_20261019/workbook_checks.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS two A/H chart styles and one top anchor changed; all worksheet values, formulas, caches, names, relationships, chart observations and axis scales preserved; styles idempotent')
