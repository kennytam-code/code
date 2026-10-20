"""Build the dated Word study from the user's retained template and audit JSON.

Use the bundled Python runtime. Optional arguments: --template PATH --output PATH.
Only document.xml and its hyperlink relationships are changed. Older studies and
the workbook/dashboard database are outside this study's scope.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from copy import deepcopy
from lxml import etree
import argparse, hashlib, json, re, resource

HERE=Path(__file__).resolve().parent
WORK=HERE.parents[1]
T=Path('/private/tmp/micro-ipo-20261020');T.mkdir(exist_ok=True)
parser=argparse.ArgumentParser()
parser.add_argument('--template',type=Path,default=Path('/Users/lemon/Downloads/ipo analysis.docx'))
parser.add_argument('--output',type=Path,default=WORK/'Microintelligence_IPO_Trader_Brief_2026-10-20.docx')
args=parser.parse_args()
A=json.loads((HERE/'source_and_valuation_audit.json').read_text())
I=A['issuer'];V=I['valuations'];F=I['financials_cnym'];P=A['peers']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(args.template)==A['template']['sha256'],'Retained template changed: distill it again before rebuilding.'
with ZipFile(args.template) as z:original={n:z.read(n) for n in z.namelist()}
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PK='http://schemas.openxmlformats.org/package/2006/relationships'
NS={'w':W,'r':R}
q=lambda n:'{'+W+'}'+n
root=etree.fromstring(original['word/document.xml']);body=root.find('w:body',NS)
donors=[deepcopy(e) for e in body]
rels=etree.fromstring(original['word/_rels/document.xml.rels'])
base_rpr=deepcopy(donors[28].find('w:r/w:rPr',NS))
title_rpr=deepcopy(donors[26].find('w:r/w:rPr',NS))
heading_rpr=deepcopy(donors[30].find('w:r/w:rPr',NS))

contract=f'''# Microintelligence Word template contract
Reference: {args.template}; SHA256 {sha(args.template)}. Same retained reference inspected in the prior study; source hash is unchanged.
One Letter portrait section: 12240 x 15840 dxa, top/bottom 1020, left/right 1134, usable width 9972. Header/footer distance 720; no page furniture.
Arial 10pt navy 153D63 body, red FF0000 compact company/section headings, bold-underlined navy Upcoming IPO. Preserve source hyphen ListParagraph (numId 10), single line spacing and source numbering/styles.
Chinese issuer names use available Hiragino Sans GB because the reference DengXian font rendered missing glyphs. Latin text retains Arial 10pt. The greenshoe column is widened by 150 dxa, taken from the sponsor column, to retain the reference two-line header.
Source slots: document.xml/body[26] title, [27] overview table, [28] body/source text, [30] red heading, [32] bullet, [37] valuation table, final sectPr. Replace the source research preamble and sample companies only. This study covers one priced IPO, so retain one overview row; add a price-case table and H-first peer table using cloned native table cells.
Tables: 9972 dxa, fixed layout, grey D9D9D9 borders, F2F2F2 headers, repeating headers, non-splitting rows, no fixed heights. Numeric columns centered, company/product and source columns left aligned.
Flow: Upcoming IPO, dated issuer line, seven-column overview, Some key points, red issuer heading, compact desk view and good/potential/bad bullets, offer valuation table. Second page contains the expanded peer table, relative-value judgment, calculation basis and linked sources. Two-page target; no font shrinking.
All 16 opaque package parts preserve-only except document.xml and document.xml.rels. Source section unchanged. No media, fields, footnotes, headers or content controls added. All final pages must be rendered and inspected. Older Word studies and all Excel/HTML data untouched.
'''
(T/'artifact.md').write_text(contract)
(T/'template-part-inventory.json').write_text(json.dumps({n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'editable':n in ['word/document.xml','word/_rels/document.xml.rels']} for n,b in original.items()},indent=2))

def prop(p,name,**attrs):
 e=p.find(q(name))
 if e is None:e=etree.SubElement(p,q(name))
 for k,v in attrs.items():e.set(q(k),str(v))
 return e

def run(p,text,bold=False,underline=False,role='body'):
 r=etree.SubElement(p,q('r'))
 rp=deepcopy(title_rpr if role=='title' else heading_rpr if role=='heading' else base_rpr)
 if bold:prop(rp,'b')
 if underline:prop(rp,'u',val='single')
 if re.search('[\u3400-\u9fff]',text):
  fonts=prop(rp,'rFonts',eastAsia='Hiragino Sans GB')
  fonts.attrib.pop(q('eastAsiaTheme'),None)
 r.append(rp)
 for j,s in enumerate(text.split('\n')):
  if j:etree.SubElement(r,q('br'))
  t=etree.SubElement(r,q('t'));t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=s
 return r

def para(text='',kind='body',before=0,after=65,keep=False,pagebreak=False):
 p=deepcopy(donors[32 if kind=='bullet' else 30 if kind=='heading' else 26 if kind=='title' else 28])
 for x in list(p):
  if x.tag!=q('pPr'):p.remove(x)
 pp=p.find(q('pPr'))
 for name in ['pageBreakBefore','keepNext','keepLines','spacing','tabs','contextualSpacing']:
  for x in pp.findall(q(name)):pp.remove(x)
 prop(pp,'spacing',before=before,after=after,line=240,lineRule='auto');prop(pp,'keepLines')
 if kind in ['heading','title'] or keep:prop(pp,'keepNext')
 if pagebreak:prop(pp,'pageBreakBefore')
 if kind in ['heading','title']:run(p,text,role=kind)
 else:
  for j,s in enumerate(re.split(r'\*\*(.*?)\*\*',text)):
   if s:run(p,s,bold=bool(j%2))
 return p

def hyperlink(p,label,url):
 used={x.get('Id') for x in rels};n=1
 while 'rId'+str(n) in used:n+=1
 rid='rId'+str(n)
 etree.SubElement(rels,'{'+PK+'}Relationship',Id=rid,Type=R+'/hyperlink',Target=url,TargetMode='External')
 h=etree.SubElement(p,q('hyperlink'));h.set('{'+R+'}id',rid);run(h,label,underline=True)

def source(label,links):
 p=para('',after=55);run(p,label,bold=True)
 for j,(name,url) in enumerate(links):
  if j:run(p,'; ')
  hyperlink(p,name,url)
 return p

def table(headers,rows,widths,overview=False,left_cols=(0,),keep=True):
 assert sum(widths)==9972
 donor=donors[27 if overview else 37]
 t=deepcopy(donor)
 for x in list(t):
  if x.tag==q('tr'):t.remove(x)
 tp=t.find(q('tblPr'));prop(tp,'tblW',w=9972,type='dxa');prop(tp,'tblLayout',type='fixed');prop(tp,'tblInd',w=0,type='dxa')
 for x in tp.findall(q('tblpPr')):tp.remove(x)
 borders=prop(tp,'tblBorders')
 for n in ['top','left','bottom','right','insideH','insideV']:prop(borders,n,val='single',sz=4,space=0,color='D9D9D9')
 margins=prop(tp,'tblCellMar')
 for n,v in [('top',65),('bottom',65),('left',65),('right',65)]:prop(margins,n,w=v,type='dxa')
 grid=t.find(q('tblGrid'))
 for x in list(grid):grid.remove(x)
 for width in widths:etree.SubElement(grid,q('gridCol')).set(q('w'),str(width))
 orig_rows=donor.findall('w:tr',NS)
 head=orig_rows[0].findall('w:tc',NS);cells=orig_rows[1].findall('w:tc',NS)
 for ri,values in enumerate([headers]+rows):
  assert len(values)==len(widths)
  tr=etree.SubElement(t,q('tr'));trp=etree.SubElement(tr,q('trPr'));prop(trp,'cantSplit')
  if ri==0:prop(trp,'tblHeader')
  for ci,value in enumerate(values):
   ds=head if ri==0 else cells;c=deepcopy(ds[min(ci,len(ds)-1)])
   cp=c.find(q('tcPr'))
   if cp is None:cp=etree.Element(q('tcPr'));c.insert(0,cp)
   for n in ['gridSpan','vMerge','tcMar','tcBorders','shd']:
    for x in cp.findall(q(n)):cp.remove(x)
   prop(cp,'tcW',w=widths[ci],type='dxa');prop(cp,'vAlign',val='center')
   if ri==0:prop(cp,'shd',val='clear',color='auto',fill='F2F2F2')
   for x in list(c):
    if x.tag!=q('tcPr'):c.remove(x)
   p=para('',after=0);pp=p.find(q('pPr'));prop(pp,'jc',val='left' if overview or ci in left_cols else 'center')
   for x in pp.findall(q('ind')):pp.remove(x)
   run(p,str(value),bold=ri==0 or ci==0)
   if keep and ri<len(rows):prop(pp,'keepNext')
   c.append(p);tr.append(c)
 return t

for x in list(body):body.remove(x)
out=body.append
out(para('Upcoming IPO',kind='title',after=90))
out(para('Microintelligence IPO | 20 October 2026 close',after=90,keep=True))
out(table(['Name','Sector','Deal size','A-share','Timetable','Green-\nshoe','Sponsor'],[['Microintelligence\n微億智造\n03275 HK','Industrial AI /\nEIIR robots','HK$620-\n800m','None','Close 23 Oct\nList 28 Oct','15%\noption','Orient Capital\n(Hong Kong)']],[1980,1640,1360,680,1920,900,1492],overview=True))
out(para('Offer HK$16.63-21.46; 100 shares/lot. Pricing expected 26 Oct; listing expected 28 Oct. Base issue before greenshoe.',before=85,after=90))
out(para('Some key points:',after=75))
out(para('Microintelligence 微億智造',kind='heading',after=75))
desk='**Desk view - demanding earnings valuation.** Industrial AI has paying customers, but the offer relies on a later profit inflection. Management expects FY2026 profit to fall below the first five months: the strongest constraint on the bullish recovery story.'
out(para(desk,after=75))
bullets=[
 '**Good - real industrial AI demand and a niche lead.** No.1 in China EIIR products by FY2025 revenue, with 20% share. This is a narrowly defined market. Five-month 2026 EIIR sales rose 40%; the opportunity is automating factory tasks with vision, decision-making and motion control.',
 '**Potential - repeat deployments with less engineering work.** Agilebot adds robot bodies and motion control. Reusing the software across tasks could improve operating leverage. New project awards rose 49% to RMB530m, including VAT; conversion still requires delivery and acceptance. 60.3% of IPO net proceeds funds R&D, so returns will take time.',
 '**Bad - full-year profit will fall below January-May.** Management expects FY2026 net profit below RMB22.5m, despite higher sales and gross profit, because of continued R&D. Five-month operating profit rose only 1.8%; the reported profit jump also benefited from RMB16.6m redemption-interest expense disappearing.',
 '**Bad - the mix upgrade has not lifted group margins.** EIIR gross margin reached 54.8%, but group margin slipped to 48.4% from 49.2% YoY as equipment and modules weakened. Orders need to produce both higher gross profit and slower expense growth before the AI theme improves shareholder earnings.',
 '**Bad - working capital still absorbs cash.** Five-month operating cash turned positive at RMB12.7m, yet receivable days remain 188. Inventory rose 51%; turnover slowed to 98 days from 83, and provisions increased. Inventory supports delivery, but slower conversion raises funding and write-down risk.',
 '**Bad - little demand is committed by the cornerstone.** Elbe Rhein Investment Limited, wholly owned by Mr. Liu Jonas, commits HK$15.7m: 2.21% of the offer at the stated midpoint, locked for six months. It is a private investment/asset-management company. The book still needs broad demand; this is limited valuation endorsement.',
]
for b in bullets:out(para(b,kind='bullet',after=65))
out(source('Evidence: ',[('20 Oct prospectus',A['sources']['prospectus']['english_url']),('Niuniu',A['sources']['niuniu_bull']['url']),('Xueqiu excerpts',A['sources']['xueqiu']['url'])]))
out(para('Offer valuation',kind='heading',before=85,after=75))
offer_rows=[
 ['Total equity value (HK$bn)']+[f'{v["equity_value_hkdm"]/1000:.3f}' for v in V],
 ['FY2025 P/S']+[f'{v["FY2025_ps"]:.1f}x' for v in V],
 ['LTM reported / adjusted P/E']+[f'{v["LTM_reported_pe"]:.1f}x / {v["LTM_adjusted_pe"]:.1f}x' for v in V],
 ['FY2026 P/E floor if profitable*']+[f'>{v["FY2026_pe_strict_lower_bound_if_positive"]:.1f}x' for v in V],
]
out(table(['Price case','Low HK$16.63','Mid HK$19.05','High HK$21.46'],offer_rows,[4100,1957,1957,1958]))
out(para('*Conditional bounds from issuer guidance, not exact earnings forecasts. If FY2026 is loss-making, P/E is NM. No verified FY2027 forecast. LTM to May 2026: reported profit RMB20.5m; adjusted profit RMB58.6m. Adjusted earnings add back share payments, redemption interest and listing expenses.',before=65,after=60))

out(para('Valuation and H share peers',kind='heading',pagebreak=True,after=85))
out(para('20 October closes. P/S uses actual FY2025 sales for every row; forward P/E uses dated selected broker attributable-profit estimates.',after=90,keep=True))
peer_rows=[['Microintelligence H (03275)\nEIIR products / factory AI','HK$16.63-\n21.46',f'{V[0]["FY2025_ps"]:.1f}-{V[2]["FY2025_ps"]:.1f}x','n/c*','n/c','Issuer guidance*']]
for p in P:
 price=('HK$'+f'{p["price"]:.3f}') if p['currency']=='HKD' else 'RMB'+f'{p["price"]:.2f}'
 broker='No verified estimate' if p['broker'] is None else {'China Post Securities':'China Post','Soochow':'Soochow','Huaxin':'Huaxin'}.get(p['broker'],p['broker'])+' '+p['forecast_date'][8:]+' '+{'08':'Aug','09':'Sep'}[p['forecast_date'][5:7]]
 peer_rows.append([f'{p["label"]} ({p["ticker"]})\n{p["fit"]}',price,f'{p["FY2025_ps"]:.1f}x',p['FY2026_pe_label'],p['FY2027_pe_label'],broker])
peert=table(['Company / product overlap','20 Oct close','FY2025\nP/S','FY2026E\nP/E','FY2027E\nP/E','Forecast source / date'],peer_rows,[2950,1300,950,1000,1000,2772],left_cols=(0,5))
for tr,p in zip(peert.findall('w:tr',NS)[2:],P):
 if p['forecast_url']:
  cell=tr.findall('w:tc',NS)[-1];para0=cell.find('w:p',NS)
  label=''.join(para0.xpath('.//w:t/text()',namespaces=NS))
  for x in list(para0):
   if x.tag!=q('pPr'):para0.remove(x)
  hyperlink(para0,label,p['forecast_url'])
out(peert)
out(para('n/c = no verified exact full-year estimate. NM = selected forecast loss. *Microintelligence has only qualitative FY2026 guidance; see the conditional P/E floors on page 1. CICC estimates are distributed by EtNet; its original note was not publicly verified.',before=75,after=80))
out(para('How to read the comparison',kind='heading',before=80,after=70))
reads=[
 f'**Revenue valuation offers some room; earnings do not yet support a rerating.** The offer is {V[0]["FY2025_ps"]:.1f}-{V[2]["FY2025_ps"]:.1f}x FY2025 sales, below Mech-Mind\'s {P[0]["FY2025_ps"]:.1f}x and Dobot\'s {P[1]["FY2025_ps"]:.1f}x, around Huayan\'s {P[2]["FY2025_ps"]:.1f}x. Different growth, margins and product standardisation justify different multiples. A lower P/S alone does not establish cheapness.',
 f'**The profit hurdle is substantial.** A future 30x P/E would need RMB{V[0]["owner_profit_cnym_for_illustrative_30x_pe"]:.0f}-{V[2]["owner_profit_cnym_for_illustrative_30x_pe"]:.0f}m annual owner profit, versus RMB20.5m reported LTM. That is a sensitivity, not a forecast or target multiple. Watch repeat orders, gross margin and R&D intensity together.',
 '**Peer fit matters.** Mech-Mind is the closest H vision/AI reference; Dobot and Huayan cover cobots and motion hardware. Estun is a broader industrial robot platform. OPT and TZTEK provide A-share vision/inspection anchors. These are product overlaps, not identical whole-company peers. Estun H and A use the same profit estimates.',
]
for s in reads:out(para(s,kind='bullet',after=75))
out(para('Basis: H price x total ordinary shares, converted at 1HK$ = RMB0.85628 (20 Oct official parity). A rows use quoted total-company equity values. These are line-implied values, not combined A+H market caps. All FYs end December. IPO total shares: 372,757,356 before the greenshoe. LTM = FY2025 minus 5M2025 plus 5M2026; interim results are not annualised. Broker estimates are selected, not consensus.',before=85,after=75))
out(source('Primary sources: ',[('Microintelligence filing',A['sources']['prospectus']['english_url']),('Mech-Mind filing',A['sources']['mech_financials']['url']),('Dobot FY2025',A['sources']['dobot_financials']['url']),('Huayan FY2025',A['sources']['huayan_financials']['url']),('FX parity',A['sources']['fx']['url'])]))
out(source('Market data: ',[('Tencent close snapshot','https://qt.gtimg.cn/q=hk09615,hk02715,hk02432,hk01021,sh688686,sh688003,sz002747'),('Sina cross-check','https://hq.sinajs.cn/list=rt_hk09615,rt_hk02715,rt_hk02432,rt_hk01021,sh688686,sh688003,sz002747')]))
out(deepcopy(donors[-1]))
assert len(body.findall('w:tbl',NS))==3
assert etree.tostring(body[-1],method='c14n',exclusive=True)==etree.tostring(donors[-1],method='c14n',exclusive=True)
xml=etree.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
rels_xml=etree.tostring(rels,encoding='UTF-8',xml_declaration=True,standalone=True)
with ZipFile(args.output,'w',ZIP_DEFLATED) as z:
 for n,b in original.items():z.writestr(n,xml if n=='word/document.xml' else rels_xml if n=='word/_rels/document.xml.rels' else b)
with ZipFile(args.output) as z:
 changed=[n for n,b in original.items() if z.read(n)!=b]
 assert set(changed)=={'word/document.xml','word/_rels/document.xml.rels'}
 assert set(z.namelist())==set(original)
assert sha(args.template)==A['template']['sha256']
assert sha(WORK/'Upcoming_IPO_Trader_Brief_2026-10-13.docx')==A['prior_word_sha256']
A['document_content']={'desk_view':desk,'key_points':bullets,'relative_value':reads,'offer_rows':offer_rows,'peer_rows':peer_rows}
A['document_sha256']=sha(args.output)
A['package_qa']={'parts':len(original),'only_changed_parts':changed,'sections':1,'tables':3,'prior_study_unchanged':True,'reference_unchanged':True,'python_peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1048576}
assert A['package_qa']['python_peak_rss_mib']<512
(HERE/'source_and_valuation_audit.json').write_text(json.dumps(A,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'word':str(args.output),'bytes':args.output.stat().st_size,'sha256':A['document_sha256'],'package_qa':A['package_qa']},indent=2))
