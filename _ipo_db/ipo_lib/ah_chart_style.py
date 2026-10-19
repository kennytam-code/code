"""A/H-only chart presentation. Preserve every cell, source binding and cache."""
from copy import deepcopy
import json
import xml.etree.ElementTree as E

C='http://schemas.openxmlformats.org/drawingml/2006/chart'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
c=lambda x:'{'+C+'}'+x
a=lambda x:'{'+A+'}'+x

def replace(parent,tag,node):
    old=parent.find(tag)
    if old is not None:
        i=list(parent).index(old);parent.remove(old);parent.insert(i,node)
    else:parent.append(node)

def text_style(color='54616E',size=1000):
    n=E.Element(c('txPr'));E.SubElement(n,a('bodyPr'));E.SubElement(n,a('lstStyle'));p=E.SubElement(n,a('p'));pp=E.SubElement(p,a('pPr'));r=E.SubElement(pp,a('defRPr'),{'sz':str(size)})
    E.SubElement(E.SubElement(r,a('solidFill')),a('srgbClr'),{'val':color});E.SubElement(r,a('latin'),{'typeface':'Arial'});E.SubElement(p,a('endParaRPr'),{'lang':'en-US'})
    return n

def line_shape(color=None,width=8000):
    n=E.Element(c('spPr'));ln=E.SubElement(n,a('ln'),{'w':str(width)})
    if color:E.SubElement(E.SubElement(ln,a('solidFill')),a('srgbClr'),{'val':color})
    else:E.SubElement(ln,a('noFill'))
    return n

def axis_title(xml,text,color):
    n=E.fromstring(xml)
    ts=list(n.iter(a('t')))
    ts[0].text=text
    for t in ts[1:]:t.text=''
    for run in n.iter(a('r')):
        if run.find(a('rPr')) is None:run.insert(0,E.Element(a('rPr')))
    for r in list(n.iter(a('rPr')))+list(n.iter(a('defRPr'))):
        r.set('sz','1000');r.set('b','0')
        for child in list(r):
            if child.tag in [a('solidFill'),a('schemeClr')]:r.remove(child)
        E.SubElement(E.SubElement(r,a('solidFill')),a('srgbClr'),{'val':color})
        E.SubElement(r,a('latin'),{'typeface':'Arial'})
    return n

def apply(parts,sheets,root):
    template=json.loads((root/'data/ah_chart_style.json').read_text())
    for path,raw in list(parts.items()):
        if not(path.startswith('xl/charts/') and path.endswith('.xml')):continue
        combined=b'!AHMarketPremium' in raw;compare=b'!AHCompare1Premium' in raw
        if not(combined or compare):continue
        doc=E.fromstring(raw);chart=doc.find(c('chart'));plot=chart.find(c('plotArea'))
        for i,s in enumerate(plot.findall('.//'+c('ser'))):
            if combined:
                ref=' '.join(n.text or '' for n in s.iter(c('f')))
                key='premium' if 'AHMarketPremium' in ref else 'csi' if 'AHMarketCSI' in ref else 'a'
                style_index={'premium':0,'csi':1,'a':2}[key]
                tx=s.find(c('tx'));v=tx.find(c('v'))
                if v is not None:v.text={'premium':'Premium (L)','csi':'CSI 300 return (R)','a':'A-share return (R)'}[key]
            else:style_index=[0,2,1,3][i]
            replace(s,c('spPr'),E.fromstring(template['series'][style_index]))
            if compare:
                ln=s.find(c('spPr')).find(a('ln'));dash=ln.find(a('prstDash'))
                if dash is None:dash=E.SubElement(ln,a('prstDash'))
                dash.set('val','dash' if i>=3 else 'solid')
            smooth=s.find(c('smooth'))
            if smooth is not None:smooth.set('val','0')
        for axis in [x for x in plot if x.tag in [c('valAx'),c('dateAx'),c('catAx')]]:
            pos=axis.find(c('axPos')).get('val');color='1D4E89' if combined and pos=='l' else '54616E'
            replace(axis,c('txPr'),text_style(color));replace(axis,c('spPr'),line_shape('D5DBE3',6500))
            for grid in list(axis.findall(c('majorGridlines')))+list(axis.findall(c('minorGridlines'))):axis.remove(grid)
            if pos=='l':
                grid=E.Element(c('majorGridlines'));grid.append(line_shape('E5E9EE',6500));axis.insert(list(axis).index(axis.find(c('axPos')))+1,grid)
            if pos in ['l','r']:
                title=axis_title(template['axis_title'],'Premium (%)' if pos=='l' else 'Price return (%)',color)
                old=axis.find(c('title'))
                if old is not None:axis.remove(old)
                axis.insert(list(axis).index(axis.find(c('numFmt'))),title)
            for tag in ['majorTickMark','minorTickMark']:
                node=axis.find(c(tag))
                if node is not None:node.set('val','none')
            # Excel axis elements must stay in schema order.
            order=['axId','scaling','delete','axPos','majorGridlines','minorGridlines','title','numFmt','majorTickMark','minorTickMark','tickLblPos','spPr','txPr','crossAx','crosses','crossesAt','crossBetween','auto','lblAlgn','lblOffset','tickLblSkip','tickMarkSkip','noMultiLvlLbl','baseTimeUnit','majorUnit','majorTimeUnit','minorUnit','minorTimeUnit','dispUnits','extLst']
            axis[:]=sorted(axis,key=lambda n:order.index(n.tag.split('}')[-1]) if n.tag.split('}')[-1] in order else 99)
        legend=chart.find(c('legend'))
        if legend is not None:
            legend.find(c('legendPos')).set('val','t')
            replace(legend,c('txPr'),text_style('344252',1000))
        title=chart.find(c('title'))
        for r in list(title.iter(a('rPr')))+list(title.iter(a('defRPr'))):r.set('sz','1150')
        replace(doc,c('spPr'),line_shape());replace(plot,c('spPr'),line_shape())
        parts[path]=E.tostring(doc)
    # Keep the complete selected chart below the frozen table header. A chart
    # crossing the pane boundary leaves its legend behind when users scroll.
    if 'AH' in sheets:
        from reflow_monitors import drawing_path,xd
        path=drawing_path(parts,sheets['AH']);doc=E.fromstring(parts[path])
        for anchor in doc:
            name=anchor.find('.//'+xd('cNvPr'))
            if name is not None and name.get('name')=='Chart 1':
                row=anchor.find(xd('from')+'/'+xd('row'))
                if int(row.text)<7:row.text='7'
        parts[path]=E.tostring(doc)
