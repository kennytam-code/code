"""Apply Artifact-authored desk colours and a dated A/H opening chart cache.

Patch only the native OOXML parts affected by this edit. Keep Bloomberg calls,
dynamic names, date axes and all unrelated workbook parts intact.
"""
import base64, io, json, re, zipfile
from copy import deepcopy
from datetime import date
from pathlib import Path
import xml.etree.ElementTree as ET
from ah_basis import review_for, comparable
from market_universe import histories as market_histories, load as market_universe

ROOT=Path(__file__).resolve().parent.parent
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
CNS='http://schemas.openxmlformats.org/drawingml/2006/chart'
RNS='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
def q(n): return '{'+NS+'}'+n
def c(n): return '{'+CNS+'}'+n
def serial(dt): return (date.fromisoformat(dt)-date(1899,12,30)).days

def apply(path, root=None):
    root=Path(root or ROOT)
    palette=json.loads((root/'data/desk_colours.json').read_text())
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(palette['xlsx_base64']))) as z:
        ts=ET.fromstring(z.read('xl/styles.xml'))
        tx=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
    template_cells={x.get('r'):x for x in tx.iter(q('c'))}
    authored_fills={k:deepcopy(ts.find(q('fills'))[int(ts.find(q('cellXfs'))[int(template_cells[v].get('s','0'))].get('fillId','0'))]) for k,v in palette['cells'].items()}
    with zipfile.ZipFile(path) as z: parts={i.filename:z.read(i.filename) for i in z.infolist()}
    style=ET.fromstring(parts['xl/styles.xml']); fills=style.find(q('fills')); xfs=style.find(q('cellXfs'))
    dxfs=style.find(q('dxfs'))
    if dxfs is None: dxfs=ET.SubElement(style,q('dxfs'),{'count':'0'})
    fillids={}
    for role,fill in authored_fills.items():
        key=ET.tostring(fill)
        found=next((i for i,x in enumerate(fills) if ET.tostring(x)==key),None)
        if found is None: found=len(fills);fills.append(fill)
        fillids[role]=found
    variants={}
    def recolour(cell,role):
        old=int(cell.get('s','0')); key=(old,role)
        if key not in variants:
            xf=deepcopy(xfs[old]);xf.set('fillId',str(fillids[role]));xf.set('applyFill','1')
            variants[key]=len(xfs);xfs.append(xf)
        cell.set('s',str(variants[key]))
    wb=ET.fromstring(parts['xl/workbook.xml'])
    rel=ET.fromstring(parts['xl/_rels/workbook.xml.rels'])
    targets={x.get('Id'):x.get('Target') for x in rel}
    sheets={s.get('name'):targets[s.get('{'+RNS+'}id')].lstrip('/') for s in wb.find(q('sheets'))}
    sheets={k:v if v.startswith('xl/') else 'xl/'+v for k,v in sheets.items()}
    strings=[]
    if 'xl/sharedStrings.xml' in parts:
        strings=[''.join(x.itertext()) for x in ET.fromstring(parts['xl/sharedStrings.xml'])]
    def text(cell):
        if cell.find(q('f')) is not None:return ''
        if cell.get('t')=='inlineStr':
            inline=cell.find(q('is'))
            return ''.join(inline.itertext()) if inline is not None else ''
        v=cell.find(q('v'))
        return strings[int(v.text)] if cell.get('t')=='s' and v is not None else (v.text or '') if v is not None else ''
    def colnum(addr):
        n=0
        for x in re.match('[A-Z]+',addr)[0]:n=n*26+ord(x)-64
        return n
    for name in ['Screener','Database']:
        sheet=ET.fromstring(parts[sheets[name]]); cells={x.get('r'):x for x in sheet.iter(q('c'))}
        # Keep band meaning and input cues from the first workbook.
        bands=19 if name=='Screener' else 3; header=bands+1
        for addr,cell in cells.items():
            row=int(re.search('[0-9]+',addr)[0]); label=text(cell)
            if row==bands and label in fillids:recolour(cell,label)
            elif row==header:recolour(cell,'exPop' if 'ex-pop' in label.lower() else 'header')
        if name=='Screener':
            # A pipeline's exact listing date can arrive as ISO text.
            # Preserve the selected date rather than silently using today.
            cells['D12'].find(q('f')).text='IF($C12<>"",$C12,IF(ISNUMBER($B12),$B12,IFERROR(DATEVALUE($B12),TODAY())))'
            for addr,cell in cells.items():
                row=int(re.search('[0-9]+',addr)[0]);col=colnum(addr)
                if (row==4 and col<=5) or (row==6 and col<=5):recolour(cell,'header')
                elif row==15 and col<=5:recolour(cell,'rank')
                elif addr in ['G7','G11']:recolour(cell,'panel')
                elif row in [40,41] and col<=4:recolour(cell,'summary')
                elif row==52 and col<=7 or row==55 and col in [6,7]:recolour(cell,'ashare')
                elif addr in ['B5','B16','B17','D17','B18','D18'] or col==3 and 7<=row<=14:recolour(cell,'input')
            # The deal selector is merged; extend its input shade to the full cell.
            for addr in ['C5','D5','E5','F5']:
                if addr in cells:recolour(cells[addr],'input')
        # Conditional formats must remain live and must not recolour other tabs.
        for rule in sheet.iter(q('cfRule')):
            scale=rule.find(q('colorScale'));bar=rule.find(q('dataBar'))
            if scale is not None:
                for node,role in zip(scale.findall(q('color')),['negative','zero','positive']):node.attrib.clear();node.set('rgb','FF'+palette['colours'][role][1:])
            elif bar is not None:
                node=bar.find(q('color'));node.attrib.clear();node.set('rgb','FF'+palette['colours']['bar'][1:])
            elif rule.get('dxfId') is not None:
                formula=' '.join(x.text or '' for x in rule.findall(q('formula')))
                role='sameSubsector' if 'same subsector' in formula else 'sectorOnly' if 'sector only' in formula else 'zebra' if 'MOD(ROW()' in formula else None
                if role:
                    dxf=deepcopy(dxfs[int(rule.get('dxfId'))]);old=dxf.find(q('fill'))
                    if old is not None:dxf.remove(old)
                    dxf.append(deepcopy(authored_fills[role]));rule.set('dxfId',str(len(dxfs)));dxfs.append(dxf)
        props=sheet.find(q('sheetPr'))
        if props is None:props=ET.Element(q('sheetPr'));sheet.insert(0,props)
        tab=props.find(q('tabColor'))
        if tab is None:tab=ET.Element(q('tabColor'));props.insert(0,tab)
        tab.attrib.clear();tab.set('rgb','FF'+palette['colours']['header' if name=='Database' else 'IDENTITY'][1:])
        parts[sheets[name]]=ET.tostring(sheet,encoding='utf-8')
    fills.set('count',str(len(fills)));xfs.set('count',str(len(xfs)));dxfs.set('count',str(len(dxfs)))
    parts['xl/styles.xml']=ET.tostring(style,encoding='utf-8')
    notes=ET.fromstring(parts[sheets['Notes']])
    for node in notes.iter(q('c')):
        if node.get('r')=='A2':
            for t in node.iter(q('t')):
                t.text=re.sub(r'Built \d{4}-\d{2}-\d{2}', 'Built '+date.today().isoformat(),t.text or '')
    parts[sheets['Notes']]=ET.tostring(notes,encoding='utf-8')
    # Default Stored view: cache only dated snapshot values. Formula cells
    # remain formulas; current Bloomberg quotes are never fabricated.
    ah=ET.fromstring(parts[sheets['AH']]); acells={x.get('r'):x for x in ah.iter(q('c'))}
    for node in ah.find(q('cols')):
        if node.get('min') in ['5','6']:node.set('width','21')
    selector=text(acells['B4']);batch=market_histories(root)
    rec=next((r for r in batch['pairs'] if r['code']==selector),None)
    md=ET.fromstring(parts[sheets['Market Data']]);mcells={x.get('r'):x for x in md.iter(q('c'))}
    def cache_value(cell,value):
        for child in list(cell):
            if child.tag in [q('v'),q('is')]:cell.remove(child)
        cell.attrib.pop('t',None)
        v=ET.SubElement(cell,q('v'))
        if isinstance(value,str):cell.set('t','str');v.text=value
        else:v.text=str(value)
    if rec:
        idx=next(int(re.search('[0-9]+',a)[0])-2 for a,x in mcells.items() if a.startswith('P') and text(x)==selector)
        mr=idx+2; hs=rec['h_history']; aligned={x[0]:x for x in rec.get('history',[])}
        start=int(text(mcells[f'X{mr}']));hs=hs[:3000]
        latest=aligned.get(hs[-1][0])
        for addr,val in {'P3':idx,'P4':text(mcells[f'Q{mr}']),'P5':text(mcells[f'R{mr}']),'P6':serial(hs[0][0]),'P7':start,'P8':len(hs),'P9':int(text(mcells[f'Z{mr}'])),'P10':0,'P11':max(1,len(hs)),'P12':0,'P13':1,'P16':hs[0][1],'P17':serial(hs[-1][0]),'P18':latest[2] if latest else '', 'P19':hs[-1][1], 'P20':latest[3] if latest else '', 'P21':0,'P22':text(mcells.get(f'AO{mr}')) if f'AO{mr}' in mcells else 0,'P23':text(mcells.get(f'AP{mr}')) if f'AP{mr}' in mcells else 0,'J4':rec['name'],'J24':'Stored through '+date.fromisoformat(hs[-1][0]).strftime('%d-%b-%y'),'A5':str(len(batch['pairs']))+' IPO A/H pairs | Stored through '+batch['asof'],'J60':''}.items():cache_value(acells[addr],val)
        for row in range(8,8+len(batch['pairs'])):
            srcrow=row-5
            for dest,source in [('A','R'),('B','Q'),('C','T'),('D','U')]:cache_value(acells[f'{dest}{row}'],text(mcells[f'{source}{srcrow}']))
            if text(mcells[f'Z{srcrow}'])=='1':cache_value(acells[f'E{row}'],'Class ratio review')
            elif f'W{srcrow}' in mcells and text(mcells[f'W{srcrow}']):cache_value(acells[f'E{row}'],float(text(mcells[f'W{srcrow}'])))
            else:cache_value(acells[f'E{row}'],'')
            a=float(text(mcells[f'AF{srcrow}'])) if f'AF{srcrow}' in mcells and text(mcells[f'AF{srcrow}']) else None
            h=float(text(mcells[f'AG{srcrow}'])) if f'AG{srcrow}' in mcells and text(mcells[f'AG{srcrow}']) else None
            fx=float(text(mcells[f'AH{srcrow}'])) if f'AH{srcrow}' in mcells and text(mcells[f'AH{srcrow}']) else None
            prem='Class ratio review' if text(mcells[f'Z{srcrow}'])=='1' else a*fx/h-1 if a and h and fx else ''
            for col,val in [('AC',a if a else ''),('AD',h if h else ''),('AK',fx if fx else ''),('AE',prem)]:cache_value(mcells[f'{col}{srcrow}'],val)
            cache_value(acells[f'F{row}'],prem)
        parts[sheets['AH']]=ET.tostring(ah,encoding='utf-8')
        cache_value(mcells['E2'],'');parts[sheets['Market Data']]=ET.tostring(md,encoding='utf-8')
        chartdata=ET.fromstring(parts[sheets['Chart Data']]);dcells={x.get('r'):x for x in chartdata.iter(q('c'))}
        valid=[];basis=review_for(selector,root)
        for i,(dt,h) in enumerate(hs,5):
            x=aligned.get(dt);cache_value(dcells[f'A{i}'],serial(dt));cache_value(dcells[f'C{i}'],h)
            allowed=x and not int(text(mcells[f'Z{mr}'])) and comparable(basis,dt,x[5])
            for col,val in [('D',x[2] if x else None),('E',x[3] if x else None),('F',serial(x[5]) if x else None),('G',serial(x[6]) if x else None),('B',x[4] if allowed else None)]:
                if val is None:
                    cache_value(dcells[f'{col}{i}'],'#N/A');dcells[f'{col}{i}'].set('t','e')
                else:cache_value(dcells[f'{col}{i}'],val)
            valid.append(x[4] if allowed else None)
        parts[sheets['Chart Data']]=ET.tostring(chartdata,encoding='utf-8')
        # Locate the A/H native chart by its dynamic premium binding.
        for name,raw in list(parts.items()):
            if not name.startswith('xl/charts/chart') or not name.endswith('.xml') or b'AHChartPremium' not in raw:continue
            native=ET.fromstring(raw)
            for ref in native.iter(c('numRef')):
                f=ref.find(c('f'))
                if f is None or 'AHChart' not in (f.text or ''):continue
                prior=ref.find(c('numCache'))
                if prior is not None:ref.remove(prior)
                values=[serial(x[0]) for x in hs] if 'AHChartDates' in f.text else valid
                cache=ET.SubElement(ref,c('numCache'));ET.SubElement(cache,c('formatCode')).text='dd-mmm-yy' if 'AHChartDates' in f.text else '0.0%'
                ET.SubElement(cache,c('ptCount'),{'val':str(len(values))})
                for i,val in enumerate(values):
                    if val is not None:ET.SubElement(ET.SubElement(cache,c('pt'),{'idx':str(i)}),c('v')).text=str(val)
            parts[name]=ET.tostring(native,encoding='utf-8')
    if 'IPO Live' in sheets:
        live_sheet=ET.fromstring(parts[sheets['IPO Live']]);live_cells={x.get('r'):x for x in live_sheet.iter(q('c'))}
        for row in range(8,8+len(market_universe(root))):cache_value(live_cells[f'C{row}'],text(mcells[f'C{row}']))
        taxonomy=json.loads((root/'data/taxonomy.json').read_text())['sectors']
        labels=[x['label'] for x in taxonomy['Technology']]
        for row in range(37,45):
            cache_value(live_cells[f'G{row}'],labels[row-37] if row-37<len(labels) else '')
            cache_value(live_cells[f'I{row}'],0 if row-37<len(labels) else '')
        parts[sheets['IPO Live']]=ET.tostring(live_sheet,encoding='utf-8')
        for name,raw in list(parts.items()):
            if not name.startswith('xl/charts/chart') or b'LiveSubsectorLabels' not in raw:continue
            native=ET.fromstring(raw)
            for ref in native.iter(c('strRef')):
                if 'LiveSubsectorLabels' not in (ref.find(c('f')).text or ''):continue
                prior=ref.find(c('strCache'))
                if prior is not None:ref.remove(prior)
                cache=ET.SubElement(ref,c('strCache'));ET.SubElement(cache,c('ptCount'),{'val':str(len(labels))})
                for i,label in enumerate(labels):ET.SubElement(ET.SubElement(cache,c('pt'),{'idx':str(i)}),c('v')).text=label
            parts[name]=ET.tostring(native,encoding='utf-8')
    if 'Lock-up' in sheets:
        locked=ET.fromstring(parts[sheets['Lock-up']]);lcells={x.get('r'):x for x in locked.iter(q('c'))}
        events=[e for e in json.loads((root/'data/batches/lockup_events.json').read_text())['events'] if e['category']=='Cornerstone' and e['date_basis']!='No cornerstone tranche']
        header=json.loads((root/'data/market_views_template.json').read_text())['lockup_layout']['table_header']
        for i,event in enumerate(events,header+1):
            w=event.get('windows',{}).get('30 trading sessions',{})
            for col,key in [('G','before_pct'),('H','after_pct')]:
                cache_value(lcells[f'{col}{i}'],w[key]/100 if w.get(key) is not None else '')
            cache_value(lcells[f'L{i}'],w.get('status',event['date_basis']) if event.get('last_day_locked') else 'Expiry unconfirmed')
        code=text(lcells['B4']);candidates=[(i,e) for i,e in enumerate(events) if e['code']==code]
        past=[x for x in candidates if x[1].get('last_day_locked') and x[1]['last_day_locked']<=json.loads((root/'data/batches/lockup_events.json').read_text())['price_asof']]
        cs=[x for x in past if x[1]['category']=='Cornerstone'];index,event=sorted(cs or past or candidates,key=lambda x:x[1].get('last_day_locked') or '',reverse=True)[0];w=event.get('windows',{}).get('30 trading sessions',{})
        selected_row=8+index;code_first=next(i for i,e in enumerate(events) if e['code']==code)+1
        codes=sorted({e['code'] for e in events});choice_first=1+sum(1+sum(e['code']==s for e in events) for s in codes if s<code);choice_last=choice_first+sum(e['code']==code for e in events)
        values={'P2':code,'P3':code_first,'P4':selected_row,'P5':choice_first,'P6':choice_last,'P7':selected_row,'P8':'','P9':w.get('anchor_close') or 0,'P10':w.get('status',event['date_basis']),'P11':8+index*61,
                'A6':'Select an H code and expiry event. Auto follows the HTML event selection.','A8':event['name'],'A10':event['category']+' · '+(event.get('last_day_locked') or 'date unavailable'),
                'A14':w['before_pct']/100 if w.get('before_pct') is not None else '', 'A18':w['after_pct']/100 if w.get('after_pct') is not None else '',
                'A22':serial(event['last_day_locked']) if event.get('last_day_locked') else 'Expiry unconfirmed','A23':w.get('status',event['date_basis']) if event.get('last_day_locked') else 'Expiry unconfirmed','A25':'Selected event: HKEX filing' if event.get('url') else ''}
        values['A12']='IPO date: '+date.fromisoformat(next(d['ipo_date'] for d in json.loads((root/'data/deals.json').read_text())['deals'] if d['code']==code)).strftime('%d-%b-%Y')
        for addr,first,last in [('A15','pre_start','anchor'),('A19','anchor','post_end')]:values[addr]=(date.fromisoformat(w[first]).strftime('%d-%b-%y')+' to '+date.fromisoformat(w[last]).strftime('%d-%b-%y')) if w.get(first) and w.get(last) else 'Window unavailable / pending'
        for addr,value in values.items():cache_value(lcells[addr],value)
        parts[sheets['Lock-up']]=ET.tostring(locked,encoding='utf-8')
        chartdata=ET.fromstring(parts[sheets['Chart Data']]);dcells={x.get('r'):x for x in chartdata.iter(q('c'))};points={p[0]:p for p in w.get('path',[])};plotted=[];reference=[]
        for offset in range(-30,31):
            p=points.get(offset);anchor=w.get('anchor_close');close=p[2] if p else None;dt=p[1] if p else None;v=close/anchor-1 if close and anchor else None;zero=0 if dt and anchor else None;plotted.append(v);reference.append(zero)
            for col,value in [('L',v),('M',zero),('N',serial(dt) if dt else None),('O',close)]:
                target=dcells[f'{col}{offset+35}'];cache_value(target,value if value is not None else '#N/A')
                if value is None:target.set('t','e')
        parts[sheets['Chart Data']]=ET.tostring(chartdata,encoding='utf-8')
        for name,raw in list(parts.items()):
            if not name.startswith('xl/charts/chart') or not name.endswith('.xml') or b'$L$5:$L$65' not in raw:continue
            native=ET.fromstring(raw)
            for kind in ['numRef','strRef']:
                for ref in native.iter(c(kind)):
                    formula=ref.find(c('f')).text or '';values=list(range(-30,31)) if '$K$5:$K$65' in formula else plotted if '$L$5:$L$65' in formula else reference if '$M$5:$M$65' in formula else None
                    if values is None:continue
                    tag='numCache' if kind=='numRef' else 'strCache';prior=ref.find(c(tag))
                    if prior is not None:ref.remove(prior)
                    cache=ET.SubElement(ref,c(tag))
                    if kind=='numRef':ET.SubElement(cache,c('formatCode')).text='0' if '$K$' in formula else '0.0%'
                    ET.SubElement(cache,c('ptCount'),{'val':str(len(values))})
                    for i,value in enumerate(values):
                        if value is not None:ET.SubElement(ET.SubElement(cache,c('pt'),{'idx':str(i)}),c('v')).text=str(value)
            parts[name]=ET.tostring(native,encoding='utf-8')
    from cache_desk_monitors import add_caches
    add_caches(parts,sheets,root)
    temp=Path(str(path)+'.styled.tmp')
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
        for name,raw in parts.items():z.writestr(name,raw)
    temp.replace(path)

if __name__=='__main__':
    import sys
    apply(Path(sys.argv[1]))
