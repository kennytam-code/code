"""Desk chart presentation, preserving formula bindings and observed series.

Split the A/H dual-axis chart into aligned panels. Negative bar colours are
Excel's dynamic invert-fill, not point colours frozen to the saved snapshot.
"""
from copy import deepcopy
import xml.etree.ElementTree as E
from ah_chart_style import c,a,replace,text_style,line_shape
from reflow_monitors import drawing_path,xd
from sector_monitor_release import relpath,target

R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P='http://schemas.openxmlformats.org/package/2006/relationships'
T='http://schemas.openxmlformats.org/package/2006/content-types'
C14='http://schemas.microsoft.com/office/drawing/2007/8/2/chart'
COLORS=['244B70','167C80','9B7136','785F9C']
ORDER=['axId','scaling','delete','axPos','majorGridlines','minorGridlines','title','numFmt','majorTickMark','minorTickMark','tickLblPos','spPr','txPr','crossAx','crosses','crossesAt','crossBetween','auto','lblAlgn','lblOffset','tickLblSkip','tickMarkSkip','noMultiLvlLbl','baseTimeUnit','majorUnit','majorTimeUnit','minorUnit','minorTimeUnit','dispUnits','extLst']

def title(chart,text):
    n=chart.find(c('title'))
    if n is None:return
    ts=list(n.iter(a('t')))
    if ts:ts[0].text=text
    for t in ts[1:]:t.text=''

def shape(color,width=24130,dash='solid',fill=False):
    n=line_shape(color,width)
    if fill:E.SubElement(E.SubElement(n,a('solidFill')),a('srgbClr'),{'val':color})
    E.SubElement(n.find(a('ln')),a('prstDash'),{'val':dash})
    if fill:n[:]=list(n)[1:]+list(n)[:1]
    return n

def frame(plot,y=.20,h=.63):
    layout=E.Element(c('layout'));m=E.SubElement(layout,c('manualLayout'))
    E.SubElement(m,c('layoutTarget'),{'val':'inner'})
    # Office factor-position means offset from its auto-layout, not the canvas.
    # Edge positions keep the two timelines exactly aligned.
    for t in ['xMode','yMode','wMode','hMode']:E.SubElement(m,c(t),{'val':'edge' if t in ['xMode','yMode'] else 'factor'})
    for k,v in [('x',.14),('y',y),('w',.80),('h',h)]:E.SubElement(m,c(k),{'val':str(v)})
    replace(plot,c('layout'),layout);plot.remove(layout);plot.insert(0,layout)

def split_market(parts,sheets):
    path=next(p for p,b in parts.items() if p.startswith('xl/charts/') and b'!AHMarketPremium' in b)
    original=E.fromstring(parts[path]);other=deepcopy(original)
    for doc,premium in [(original,True),(other,False)]:
        chart=doc.find(c('chart'));plot=chart.find(c('plotArea'))
        groups=plot.findall(c('scatterChart'))
        for group in groups:
            keep=any('AHMarketPremium' in (f.text or '') for f in group.iter(c('f')))==premium
            if not keep:plot.remove(group)
        group=plot.find(c('scatterChart'));ids=[n.get('val') for n in group.findall(c('axId'))]
        for axis in list(plot):
            if axis.tag not in [c('valAx'),c('catAx'),c('dateAx')]:continue
            if axis.find(c('axId')).get('val') not in ids:plot.remove(axis);continue
            aid=axis.find(c('axId')).get('val');axis.find(c('crossAx')).set('val',next(i for i in ids if i!=aid))
            if axis.find(c('axPos')).get('val')=='r':axis.find(c('axPos')).set('val','l')
        for i,s in enumerate(group.findall(c('ser'))):
            s.find(c('idx')).set('val',str(i));s.find(c('order')).set('val',str(i))
            tx=s.find(c('tx')+'/'+c('v'))
            if tx is not None:tx.text='A/H premium' if premium else 'CSI 300' if 'CSI' in tx.text else 'A-share'
        if premium:
            n=chart.find(c('legend'))
            if n is not None:chart.remove(n)
        title(chart,'A/H premium (%)' if premium else 'A-share vs CSI 300 · return (%)')
        frame(plot,.24 if premium else .30,.69 if premium else .53)
    new='xl/charts/chartAHMarketReturns.xml'
    parts[path]=E.tostring(original);parts[new]=E.tostring(other)
    dp=drawing_path(parts,sheets['AH']);drawing=E.fromstring(parts[dp]);rp=relpath(dp);rels=E.fromstring(parts[rp])
    rid=next(r.get('Id') for r in rels if target(dp,r.get('Target'))==path)
    anchor=next(an for an in drawing if an.find('.//'+c('chart')).get('{'+R+'}id')==rid)
    extra=deepcopy(anchor)
    anchor.find(xd('from')+'/'+xd('row')).text='7';anchor.find(xd('to')+'/'+xd('row')).text='16'
    extra.find(xd('from')+'/'+xd('row')).text='16';extra.find(xd('to')+'/'+xd('row')).text='26'
    extra.find('.//'+xd('cNvPr')).set('id','91');extra.find('.//'+xd('cNvPr')).set('name','Mainland return reference')
    extra.find('.//'+c('chart')).set('{'+R+'}id','rIdMarketReturns');drawing.append(extra)
    E.SubElement(rels,'{'+P+'}Relationship',{'Id':'rIdMarketReturns','Type':R+'/chart','Target':'/'+new})
    parts[dp]=E.tostring(drawing);parts[rp]=E.tostring(rels)
    types=E.fromstring(parts['[Content_Types].xml']);E.SubElement(types,'{'+T+'}Override',{'PartName':'/'+new,'ContentType':'application/vnd.openxmlformats-officedocument.drawingml.chart+xml'})
    parts['[Content_Types].xml']=E.tostring(types)

def apply(parts,sheets,root):
    if 'xl/charts/chartAHMarketReturns.xml' not in parts:split_market(parts,sheets)
    for path,raw in list(parts.items()):
        if not(path.startswith('xl/charts/') and path.endswith('.xml')):continue
        doc=E.fromstring(raw);chart=doc.find(c('chart'));plot=chart.find(c('plotArea'))
        bars=plot.find(c('barChart')) is not None
        premium=b'!AHMarketPremium' in raw
        market=path.endswith('chartAHMarketReturns.xml')
        peer='chartDeskPeer' in path
        if premium or market:frame(plot,.24 if premium else .30,.69 if premium else .53)
        if peer:frame(plot,.23,.67)
        for i,s in enumerate(plot.findall('.//'+c('ser'))):
            refs=' '.join(f.text or '' for f in s.iter(c('f')))
            color=COLORS[i%4];dash='solid'
            if market:
                color='697685' if 'AHMarketCSI' in refs else COLORS[1];dash='dash' if 'AHMarketCSI' in refs else 'solid'
            if 'chartDeskPeer2' in path:color=COLORS[0]
            replace(s,c('spPr'),shape('28795A' if bars else color,0 if bars else 24130,dash,bars))
            if bars:
                s.find(c('invertIfNegative')).set('val','1')
                ext=s.find(c('extLst'))
                if ext is None:ext=E.SubElement(s,c('extLst'))
                n=E.SubElement(ext,c('ext'),{'uri':'{6F2FDCE9-48DA-4B69-8628-5D25D57E5C99}'})
                fmt=E.SubElement(n,'{'+C14+'}invertSolidFillFmt');sp=E.SubElement(fmt,'{'+C14+'}spPr')
                E.SubElement(E.SubElement(sp,a('solidFill')),a('srgbClr'),{'val':'B5484D'})
            else:
                marker=s.find(c('marker'))
                if marker is not None:
                    points=s.findall('.//'+c('yVal')+'//'+c('numCache')+'/'+c('pt'))
                    one_point_safe=premium or 'AHCompare' in refs or len(points)==1
                    marker.find(c('symbol')).set('val','circle' if one_point_safe else 'none')
                    if one_point_safe:
                        size=marker.find(c('size'))
                        if size is None:size=E.SubElement(marker,c('size'))
                        size.set('val','2')
                        replace(marker,c('spPr'),shape(color,6000,fill=True))
                        marker[:]=sorted(marker,key=lambda n:['symbol','size','spPr','extLst'].index(n.tag.split('}')[-1]))
                smooth=s.find(c('smooth'))
                if smooth is not None:smooth.set('val','0')
        if bars:plot.find(c('barChart')+'/'+c('gapWidth')).set('val','65')
        for axis in [n for n in plot if n.tag in [c('valAx'),c('dateAx'),c('catAx')]]:
            pos=axis.find(c('axPos')).get('val');horizontal=pos in ['b','t']
            replace(axis,c('txPr'),text_style('596674',950));replace(axis,c('spPr'),line_shape('C8CFD6',6000))
            for n in list(axis):
                if n.tag in [c('majorGridlines'),c('minorGridlines'),c('title')]:axis.remove(n)
            numeric_grid=(bars and horizontal) or (not bars and not horizontal)
            if numeric_grid:
                n=E.SubElement(axis,c('majorGridlines'));n.append(line_shape('E6EAEE',5000))
            fmt=axis.find(c('numFmt'))
            if fmt is not None:
                if horizontal and not bars:fmt.set('formatCode','d mmm' if peer else 'd mmm yy')
                elif axis.tag==c('valAx') and ('%' in fmt.get('formatCode','')):fmt.set('formatCode','0.0%;(0.0%);0.0%' if bars else '0%;(0%);0%')
            for name in ['majorTickMark','minorTickMark']:
                n=axis.find(c(name))
                if n is not None:n.set('val','none')
            tick=axis.find(c('tickLblPos'))
            if tick is not None:tick.set('val','none' if premium and horizontal else 'low')
            crosses=axis.find(c('crosses'))
            if crosses is not None:crosses.set('val','min')
            if bars:
                if axis.tag==c('catAx'):axis.find(c('scaling')+'/'+c('orientation')).set('val','maxMin')
                elif crosses is not None:crosses.set('val','max')
            axis[:]=sorted(axis,key=lambda n:ORDER.index(n.tag.split('}')[-1]) if n.tag.split('}')[-1] in ORDER else 99)
        legend=chart.find(c('legend'))
        if legend is not None:
            legend.find(c('legendPos')).set('val','t');replace(legend,c('txPr'),text_style('344252',1000))
            overlay=legend.find(c('overlay'))
            if overlay is not None:overlay.set('val','0')
        t=chart.find(c('title'))
        if t is not None:
            for r in list(t.iter(a('rPr')))+list(t.iter(a('defRPr'))):
                r.set('sz','1100');r.set('b','1')
                for n in list(r):
                    if n.tag==a('solidFill'):r.remove(n)
                E.SubElement(E.SubElement(r,a('solidFill')),a('srgbClr'),{'val':'303D49'})
        if 'chartDeskPeer1' in path:title(chart,'Peer price return (%)')
        if 'chartDeskPeer2' in path:title(chart,'Return spread · first peer − second (pp)')
        blank=chart.find(c('dispBlanksAs'))
        if blank is not None:blank.set('val','gap')
        replace(doc,c('spPr'),line_shape());replace(plot,c('spPr'),line_shape())
        parts[path]=E.tostring(doc)
    dp=drawing_path(parts,sheets['Peer Trades']);drawing=E.fromstring(parts[dp])
    for i,an in enumerate(drawing):
        an.find(xd('from')+'/'+xd('col')).text='0' if i==0 else '4'
        an.find(xd('to')+'/'+xd('col')).text='4' if i==0 else '8'
        an.find(xd('to')+'/'+xd('row')).text='30'
    parts[dp]=E.tostring(drawing)
    dp=drawing_path(parts,sheets['IPO Live']);drawing=E.fromstring(parts[dp])
    drawing[0].find(xd('from')+'/'+xd('row')).text='7'
    drawing[0].find(xd('to')+'/'+xd('row')).text='24'
    parts[dp]=E.tostring(drawing)
