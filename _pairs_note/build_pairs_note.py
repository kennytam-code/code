"""Build HK_Semi_Pair_Trades_Sep2026.docx from data/ (prices 7-Sep-2026 close; lists verified 9-11 Sep 2026)."""
import csv, json, os, sys, math
sys.path.insert(0, os.path.dirname(__file__))
from docx_helpers import *

D = os.path.join(os.path.dirname(__file__), 'data')
snap = {r['name']: r for r in csv.DictReader(open(os.path.join(D, 'snapshot.csv')))}
ahp = json.load(open(os.path.join(D, 'ahp.json')))
ps = json.load(open(os.path.join(D, 'pairstats.json')))
q = json.load(open(os.path.join(D, 'quotes.json')))
K = json.load(open(os.path.join(D, 'kline.json')))
FX = 1.1674; USDHKD = 7.80

# ---- pure-python pair stats (same as pairs_pure.py) for pairs not pre-computed ----
P = {n: {r[0]: r[2] for r in v['rows']} for n, v in K.items()}
def _mean(x): return sum(x) / len(x)
def _sd(x): m = _mean(x); return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))
def _cov(x, y): mx = _mean(x); my = _mean(y); return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (len(x) - 1)
def pairstat(L, S, win=None):
    ds = sorted(set(P[L]) & set(P[S])); pl = [P[L][d] for d in ds]; psr = [P[S][d] for d in ds]
    if win: ds, pl, psr = ds[-win:], pl[-win:], psr[-win:]
    rl = [math.log(pl[i] / pl[i - 1]) for i in range(1, len(pl))]; rs = [math.log(psr[i] / psr[i - 1]) for i in range(1, len(psr))]
    beta = _cov(rl, rs) / _sd(rs) ** 2; corr = _cov(rl, rs) / (_sd(rl) * _sd(rs))
    lr = [math.log(a / b) for a, b in zip(pl, psr)]; m = _mean(lr); s = _sd(lr)
    sp = [a - b for a, b in zip(rl, rs)]
    return dict(n=len(rl), corr=corr, beta=beta, z=(lr[-1] - m) / s, ratio=pl[-1] / psr[-1], ratio_mean=math.exp(m),
                ratio_min=math.exp(min(lr)), ratio_max=math.exp(max(lr)), volL=_sd(rl) * math.sqrt(252) * 100, volS=_sd(rs) * math.sqrt(252) * 100,
                sv=_sd(sp) * math.sqrt(252) * 100, pct=sum(1 for v in lr if v < lr[-1]) / len(lr) * 100, start=ds[0])
ps['H:GigaDevice/SMIC'] = pairstat('GigaDevice', 'SMIC')
ps['H40:GigaDevice/SMIC'] = pairstat('GigaDevice', 'SMIC', 40)
ps['H40:Montage/GigaDevice'] = pairstat('Montage', 'GigaDevice', 40)

CODE = {'SMIC': '981', 'HuaHong': '1347', 'ASMPT': '522', 'Nexchip': '2249', 'GigaDevice': '3986', 'Montage': '6809',
        'OmniVision': '501', 'SGMicro': '3661', 'Novosense': '2676', 'NSing': '2701', 'Fortior': '1304', 'SICC': '2631',
        'CFMEE': '9630', 'Ingenic': '3223', 'Biren': '6082', 'Iluvatar': '9903', 'Axera': '600', 'BlackSesame': '2533',
        'Horizon': '9660', 'Innoscience': '2577', 'Gpixel': '3277', 'Innolight': '3308'}
LABEL = {'SMIC': 'SMIC', 'HuaHong': 'Hua Hong', 'ASMPT': 'ASMPT', 'Nexchip': 'Nexchip 晶合', 'GigaDevice': 'GigaDevice 兆易',
         'Montage': 'Montage 澜起', 'OmniVision': 'OmniVision 豪威', 'SGMicro': 'SG Micro 圣邦', 'Novosense': 'Novosense 纳芯微',
         'NSing': 'NSing 国民技术', 'Fortior': 'Fortior 峰岹', 'SICC': 'SICC 天岳', 'CFMEE': 'CFMEE 芯碁', 'Ingenic': 'Ingenic 君正',
         'Biren': 'Biren 壁仞', 'Iluvatar': 'Iluvatar 天数', 'Axera': 'Axera 爱芯', 'BlackSesame': 'Black Sesame 黑芝麻',
         'Horizon': 'Horizon 地平线', 'Innoscience': 'Innoscience 英诺赛科', 'Gpixel': 'Gpixel 长光辰芯', 'Innolight': 'Innolight 中际旭创'}

def qf(name, i):
    f = q.get('hk' + CODE[name].zfill(5)); return f[i] if f else None
def hfloat_bn(name):
    v = qf(name, 44); return float(v) / 10 if v else None
def mcap_bn(name):
    v = qf(name, 45); return float(v) / 10 if v else None
def pe(name):
    v = qf(name, 39)
    if not v: return 'n/a'
    v = float(v); return 'loss' if v < 0 else f"{v:.0f}x"
def s(name, k, nd=1, pct=True, sign=True):
    return fmt(snap[name][k], nd, pct=pct, sign=sign)

# annualised-1H26 valuation (verified prints, see section 9)
PRINTS = {  # name: (1H26 NI, currency, YoY text, note)
    'GigaDevice': (6.857, 'RMB', '+10.9x', 'net profit RMB6.857bn'),
    'Montage': (1.997, 'RMB', '+72%', 'net profit RMB1.997bn, interim div RMB0.20/sh'),
    'Nexchip': (0.245, 'RMB', '−26%', 'revenue RMB5.77bn +12%, net profit RMB245m'),
    'SMIC': (0.677, 'USD', '+111%', 'net profit US$677m; 2Q rev >US$3bn, +20% QoQ (TrendForce)'),
    'HuaHong': (0.0596, 'USD', '+409%', 'net profit US$59.6m on record revenue; 2Q beat, positive 3Q guide (Citi)'),
    'Iluvatar': (0.106, 'RMB', 'to profit', 'revenue RMB946m +192%; GM 50.1% → 17.2%'),
}
def ann_pe(name):
    ni, ccy, _, _ = PRINTS[name]; hk = ni * 2 * (FX if ccy == 'RMB' else USDHKD)
    return mcap_bn(name) / hk

d = new_doc()
title(d, 'HK Semis — Pair Trade Ideas',
      'Written 8–9 Sep 2026 · prices = 7 Sep 2026 HKEX close, A-shares SSE/SZSE close, CNYHKD 1.1674 · short-sell and Southbound status verified against the '
      'HKEX designated list (effective 11 Sep) and the SZSE Southbound list (9 Sep) · 1H26 prints from company results headlines · trader audience, internal')

para(d, 'Short version. The HK semi complex topped 25–30 June and is 20–60% off the highs while HSTECH is +3% over the same window — a sector unwind '
        '(bond-yield selloff in global chips, A-share crowd rotating out, IPO supply, July–August lock-up expiries), not a market fall. The interim prints that landed in August '
        'are extreme in both directions, which is what makes the pairs. Four I would put on, three to watch:', bold_lead='')
numbered(d, [
    ('The pair you asked about, Nexchip vs GigaDevice, is right in one direction only — long GigaDevice / short Nexchip. ', '1H26 net profit +10.9x vs −26%; 22x vs 107x on annualised '
     'earnings. The catch: Nexchip is not on the HKEX short-sell list (checked 1, 10 and 11 Sep) and the quarterly review just passed, so the earliest borrow is the December review — '
     'three weeks before its 10 Jan 2027 cornerstone unlock. Do not take the reverse just because the H is 53% below the A: Southbound already has access and the profits are falling. '
     'Interim expression: long GigaDevice hedged with SMIC.'),
    ('Long GigaDevice 3986 / short Montage 6809 into the Q4 contract print. ', 'The ratio z-score screams the opposite and it is a trap — relative EPS moved 6x, the price ratio 0.8x. '
     '22x vs 73x annualised, both H-above-A Southbound names, 0.82 correlation. Flip it if TrendForce’s Q4 outlook (late Sep) is flat.'),
    ('Long SMIC 981 / short Hua Hong 1347. ', '55x vs 215x annualised; Hua Hong/SMIC still at the 88th–91st percentile of two years after a 30% give-back. Hua Hong beat in Q2 and guided '
     'up, so enter on a bounce, not here.'),
    ('Long Innoscience 2577 / short SICC 2631. ', 'The August prints confirm the direction: Innoscience revenue +51% with gross margin +4.8pts; SICC revenue +15% with a swing to loss. Ratio 0.67 vs a one-year mean of 1.03.'),
    ('Watch: ', 'Iluvatar/Biren (ratio at a 40-day extreme after Iluvatar’s −11% Monday, gross margin 50→17% in 1H, four brokers still 2–3x above the price), Horizon/Black Sesame '
     '(both shortable, thin borrow, 0.35 correlation), OmniVision/Gpixel (dead — Gpixel is not designated).'),
])
para(d, 'Housekeeping. (a) Pairs 1 and 2 are both long GigaDevice; the book’s net long in one 100%-vol name should not exceed one pair’s worth — run pair 2 and use pair 1 as the '
        'December set-up. (b) Spread vols here are 45–90% annualised: a 20% ratio move in three months is a half-sigma event, so the edge is the print calendar and the structural set-up, '
        'not the z-score. Size at half normal and stop on the spread, never on a leg.', size=10)

# ---------------- Section 1 ----------------
h1(d, '1. Where the group is')
bullets(d, [
    ('The top was 25–30 June. ', 'GigaDevice 1,241 (29 Jun) → 492, Hua Hong 215 → 115, Iluvatar 793 → 340, Montage 501 (13 May) → 279, ASMPT 239 → 168. '
     'SMIC is only −20% from its October-2025 high — the big liquid name held, the 2026 IPO cohort did not.'),
    ('Supply explains the timing. ', 'The January–February H-listings came out of their six-month cornerstone lock-ups between 2 Jul (Biren) and 10 Aug (Axera): Iluvatar 8 Jul, '
     'OmniVision 12 Jul, GigaDevice 13 Jul, Montage 9 Aug. Then Nexchip listed 10 Jul, Innolight 30 Jul, Ingenic 25 Aug. Free float in the sector roughly doubled in eight weeks, '
     'into a global chip selloff on rising bond yields (Samsung and Hynix −6% days).'),
    ('The prints went the other way. ', '1H26 net profit: GigaDevice +10.9x, Hua Hong +409%, SMIC +111%, Montage +72%, Iluvatar to profit; Nexchip −26%, SICC to loss. '
     'The memory cycle is still running: TrendForce has 2Q26 DRAM industry revenue +59.5% QoQ to US$154.7bn, supplier inventories at historic lows, and 3Q26 conventional DRAM '
     'contract prices +13–18% QoQ — still up, but decelerating from Q2. That deceleration is what the −60% in GigaDevice is pricing.'),
    ('A/H tells you who owns what. ', 'Memory names trade with the H ABOVE the A — GigaDevice 8.5%, Montage 17%, Innolight 13% — which only happens when Southbound plus offshore '
     'money crowd an H float that is a fraction of the A float (GigaDevice H float HK$16bn vs A HK$270bn). Foundries are the opposite: SMIC H at a 112% A-premium, Hua Hong 127%, '
     'Nexchip 53% (96% on debut, 35% at the 14-Aug low). Southbound has been a net seller of SMIC for six straight sessions to 8 Sep and of Hua Hong alongside.'),
    ('Monday 7 Sep was index day. ', 'The Hang Seng quarterly review took effect (Monday after the first Friday of September) and the tape looked like it: Innolight +19.6%, '
     'CFMEE +12.9%, Montage +6.7%, GigaDevice +5.8% against Iluvatar −11.4%, Axera −12.5%, FourSemi −18%, Gpixel −8%. Treat Monday’s closes as flow-distorted when setting entries.'),
])

h2(d, 'Snapshot (7 Sep close)')
rows = []
order = ['SMIC', 'HuaHong', 'Nexchip', 'GigaDevice', 'Montage', 'Ingenic', 'OmniVision', 'Gpixel', 'SGMicro', 'Novosense', 'Innoscience', 'SICC',
         'Horizon', 'BlackSesame', 'Biren', 'Iluvatar', 'Axera', 'ASMPT', 'CFMEE', 'Innolight', 'NSing', 'Fortior']
for n in order:
    r = snap[n]
    since = fmt(r['since_list'], 0, pct=True, sign=True) if r['first'] >= '2025-01-01' else '—'
    prem = fmt(ahp.get(n), 0, pct=True, sign=True) if n in ahp else '—'
    rows.append([f"{CODE[n]} {LABEL[n]}", fmt(r['last'], 2 if float(r['last']) < 20 else 1, sign=False), s(n, 'r1m', 0), s(n, 'r3m', 0) if r['r3m'] else '—',
                 f"{fmt(r['dd'], 0, pct=True, sign=True)} ({r['hi_date'][5:]})", since, fmt(r['vol60'], 0, sign=False), fmt(r['adv20_hkdm'], 0, sign=False),
                 pe(n), prem, fmt(hfloat_bn(n), 1, sign=False)])
table(d, ['Code / name', 'Last', '1m', '3m', 'From high (date)', 'vs IPO', 'Vol 60d %', 'ADV20 HK$m', 'P/E feed', 'A-prem', 'H float HK$bn'], rows,
      col_widths=[3.6, 1.3, 1.1, 1.1, 2.3, 1.2, 1.3, 1.6, 1.3, 1.3, 1.5], font_size=8)
para(d, '“P/E feed” is the trailing multiple on the quote feed — it still uses FY25 earnings and is badly stale for the names whose profits stepped up in 1H26 (next table). '
        'A-prem = A-share price in HKD over H price, minus one; negative = the H is the expensive line. H float = H-share market cap. vs IPO shown for 2025–26 listings only.',
     size=8.5, italic=True, color=GREY)

h2(d, 'Valuation on the August prints (annualised 1H26)')
vrows = []
for n in ['GigaDevice', 'Montage', 'Nexchip', 'SMIC', 'HuaHong', 'Iluvatar']:
    ni, ccy, yoy, note = PRINTS[n]
    vrows.append([f"{CODE[n]} {LABEL[n]}", fmt(mcap_bn(n), 0, sign=False), f"{ccy} {ni*1000:,.0f}m", yoy, f"{ann_pe(n):.0f}x", pe(n), note])
table(d, ['Name', 'Mkt cap HK$bn', '1H26 net profit', 'YoY', 'P/E on 2×1H26', 'P/E feed', 'Print'], vrows,
      col_widths=[3.4, 1.8, 2.2, 1.3, 1.9, 1.4, 5.2], font_size=8, align_right_from=1)
para(d, 'Annualising a first half is crude, and for GigaDevice it annualises a cycle peak — that is exactly the debate. But the feed’s 190x for GigaDevice vs 138x for Montage '
        'inverts the real relationship (22x vs 73x), and anyone trading the pair off screen multiples has it backwards.', size=8.5, italic=True, color=GREY)

h2(d, 'Plumbing — verified against the exchange lists')
para(d, 'HKEX only allows covered shorts in “designated securities” (market cap ≥ HK$3bn and 12-month turnover velocity ≥ 60%, reviewed quarterly, plus a fast-track for large new '
        'listings). The list effective 11 Sep 2026 carries the latest quarterly changes (39 in, 40 out — Epiworld and Viewtrix added, Axera removed on the velocity test). '
        'Southbound eligibility is from the SZSE 港股通标的 list dated 9 Sep 2026.', size=10)
table(d, ['Name', 'Shortable (HKEX list 11 Sep)', 'Southbound (SZSE 9 Sep)', 'Lock-up (cornerstone, 6m)', 'Trading note'], [
    ['SMIC 981 / Hua Hong 1347', 'Yes / Yes', 'Yes / Yes', '—', 'HK$4–5bn a day, GC borrow'],
    ['GigaDevice 3986', 'Yes', 'Yes', 'expired 13 Jul 2026', 'ADV HK$1.5bn; lendable pool < H float (Southbound-held stock does not lend)'],
    ['Montage 6809', 'Yes', 'Yes', 'expired 9 Aug 2026', 'ADV HK$1.0bn'],
    ['Nexchip 2249', 'NO', 'Yes', '10 Jan 2027', 'H float HK$6.2bn, ADV HK$54m; earliest designation = December review'],
    ['Ingenic 3223 / Innolight 3308', 'No / Yes', 'No / Yes', '25 Feb 2027 / 30 Jan 2027', 'Innolight ADV HK$1.8bn'],
    ['OmniVision 501', 'Yes', 'Yes', 'expired 12 Jul 2026', 'ADV only HK$30m on a HK$3.7bn H float'],
    ['SICC 2631 / Innoscience 2577', 'Yes / Yes', 'Yes / Yes', 'expired', 'ADV HK$180m / 210m'],
    ['Horizon 9660 / Black Sesame 2533', 'Yes / Yes', 'Yes / Yes', 'expired', 'Black Sesame ADV HK$54m — borrow small and special'],
    ['Biren 6082 / Iluvatar 9903', 'Yes / Yes', 'Yes / Yes', 'expired 2 Jul / 8 Jul 2026', 'ADV HK$0.5bn / 0.8bn'],
    ['Gpixel 3277', 'NO', 'Yes', 'expired', 'cannot be the short leg of anything'],
    ['SG Micro 3661 / Novosense 2676', 'No / Yes', 'Yes / Yes', '26 Dec 2026 / expired', 'ADV HK$60m / 40m'],
    ['Axera 600', 'No (removed 11 Sep)', 'Yes', 'expired 10 Aug 2026', 'velocity 41% < 60% — the rule working'],
], col_widths=[3.6, 3.0, 2.6, 2.8, 5.2], font_size=8, align_right_from=99)

# ---------------- pairs ----------------
def statrow(key, label):
    p = ps[key]; big = p['ratio_max'] >= 5
    f = (lambda v: f"{v:.2f}") if big else (lambda v: f"{v:.3f}")
    return [label, f(p['ratio']), f(p['ratio_mean']), f"{f(p['ratio_min'])} – {f(p['ratio_max'])}", f"{p['pct']:.0f}", f"{p['z']:+.1f}",
            f"{p['corr']:.2f}", f"{p['beta']:.2f}", f"{p['volL']:.0f} / {p['volS']:.0f}", f"{p['sv']:.0f}", str(p['n'])]
STAT_HDR = ['Window', 'Ratio now', 'Mean', 'Min – max', 'Pctile', 'z', 'Corr', 'Beta (num on den)', 'Vol num / den %', 'Spread vol 1:1 %', 'n']
STAT_W = [3.4, 1.5, 1.4, 2.6, 1.1, 0.9, 1.0, 1.7, 1.9, 1.7, 0.8]

h1(d, '2. Pair 1 — Nexchip 2249 vs GigaDevice 3986: right idea, one direction, not yet')
para(d, 'Long GigaDevice / short Nexchip when Nexchip is designated (December review at the earliest). Until then: long GigaDevice hedged with SMIC, and do not be long Nexchip.', bold_lead='The trade. ')
para(d, '', bold_lead='Why.')
numbered(d, [
    ('The prints settle the direction. ', 'GigaDevice 1H26 net profit RMB6.86bn, up 10.9x, on DDR4/LPDDR4 and NOR pricing — it is fabless and rents the price cycle, and this half '
     'it rented a very good one; BofA took the A-share target to RMB663 on the print. Nexchip 1H26: revenue RMB5.77bn +12%, net profit RMB245m −26% — volume up, margin down, '
     'which is what a DDIC-heavy 12-inch foundry with new depreciation looks like when display-driver pricing is soft. Annualised, that is 22x for GigaDevice and 107x for Nexchip.'),
    ('The H discount is not the bargain it looks. ', 'Nexchip H is 53% below its A. It was 96% on debut and 35% at the 14-Aug low, so the gap closed once on nothing but offshore '
     'buying and re-opened as the H fell 25% from 17 Aug. The buyer that normally closes these — Southbound — already has access (it is on the SZSE list dated 9 Sep). If a 53% '
     'discount does not compress with Southbound open and the cornerstone book still locked, the H is telling you the A is wrong, not the other way round. Note also Huaqin, the '
     'ODM, has been adding to its A-share stake (10.8% by April) — a strategic holder supporting the A leg keeps the gap wide rather than closing it.'),
    ('You cannot short Nexchip today. ', 'It is absent from the HKEX designated lists of 1, 10 and 11 Sep; the 11 Sep list carries the quarterly review changes, so the next chance is '
     'the December review. That lands about three weeks before the 10 Jan 2027 cornerstone unlock on a HK$6.2bn float that trades HK$54m a day — the cleanest set-up in the note, '
     'and the reason to diarise rather than force it.'),
    ('Why long GigaDevice now rather than wait. ', 'Memory equities top on the second derivative, and the −60% from 29 Jun already prices the deceleration TrendForce printed '
     '(+59.5% industry revenue in Q2, +13–18% contract prices in Q3). Supplier inventories are at historic lows, GigaDevice’s own view (Dec-25) was no relief through 2026 with 2H '
     'prices “moderately upward”, and the company has an RMB1–2bn A-share buyback. At 22x annualised the bet is that Q4 stays positive — the late-September TrendForce outlook is the gate. '
     'If you can buy the A, buy the A: the H’s 8.5% premium is the cost of the offshore ticket.'),
    ('The hedge. ', 'SMIC is the liquid sector beta: correlation with GigaDevice 0.69 over 40 days, 60% vol vs 100%, HK$5bn a day, GC borrow. It is a hedge, not alpha — SMIC’s own '
     'print (+111%) is strong. Vol-neutral is 0.6 of SMIC per 1.0 of GigaDevice.'),
])
table(d, STAT_HDR, [statrow('H:GigaDevice/Nexchip', 'GigaDevice/Nexchip H since 10 Jul'), statrow('H40:GigaDevice/Nexchip', 'GigaDevice/Nexchip H 40d'),
                    statrow('A:GigaDevice_A/Nexchip_A', 'GigaDevice/Nexchip A since Jan-24'), statrow('A250:GigaDevice_A/Nexchip_A', 'GigaDevice/Nexchip A 250d'),
                    statrow('H:GigaDevice/SMIC', 'GigaDevice/SMIC H since 13 Jan'), statrow('H40:GigaDevice/SMIC', 'GigaDevice/SMIC H 40d')], col_widths=STAT_W, font_size=8)
kv_table(d, [
    ('Now (interim)', 'Long GigaDevice 3986 HK$10m / short SMIC 981 HK$6m. Ratio GigaDevice/SMIC = 7.2. Target 9.0 (+25%, the mid-August level); stop 6.0 (−17%); '
     'exit regardless if the TrendForce Q4 conventional-DRAM outlook is ≤ +5%.'),
    ('December (the real pair)', 'Long GigaDevice / short Nexchip 1 : 0.7 (vol-neutral) once Nexchip is designated. Reference points on the ratio: 23.3 debut high, 14.6 low (14 Aug), 17.9 now, '
     'mean 16.7. Trade it into the 10 Jan unlock; the A-ratio (10.7, 95th percentile since 2024) is the argument against — it says GigaDevice has already re-rated a lot vs Nexchip on the mainland too.'),
    ('Size', 'Half normal on the interim leg (it is a hedged single-name bet with ~80% spread vol, not a pair). Full size only for the December pair.'),
    ('Borrow', 'SMIC GC. Nexchip: none until designated; ask the desk to flag the December list the day it is published (~2 weeks before effect).'),
    ('Catalysts', 'Late-Sep TrendForce Q4 outlook · late-Oct A-share Q3 reports · mid-Dec HKEX designation review · 10 Jan 2027 Nexchip unlock.'),
    ('Kill switches', 'Q4 contract outlook flat or down; a GigaDevice H placement (the H premium invites one); Nexchip’s A/H gap closing sharply on Southbound flow before December (then the short entry is worse — wait for the unlock instead).'),
])
para(d, 'Long GigaDevice / short Nexchip is the trade; the calendar, not the thesis, is what stops you. Do not be long Nexchip for the A/H gap — the profits are falling and the buyer is already in the room.', bold_lead='Verdict. ')

h1(d, '3. Pair 2 — Long GigaDevice 3986 / Short Montage 6809 (into the Q4 print)')
para(d, 'Ratio quoted Montage ÷ GigaDevice (H): 0.568 now. You want it lower.', bold_lead='The trade. ')
para(d, '', bold_lead='Why.')
numbered(d, [
    ('The z-score is a trap, and it is worth saying why. ', 'Montage_A ÷ GigaDevice_A is 0.51 — the 12th percentile since January 2024 (mean 0.62) — and the naive read is “Montage cheap, '
     'mean-revert it”. But relative earnings moved by a factor of six (GigaDevice 1H26 net profit +10.9x, Montage +72%) while the price ratio moved by 0.8x. On earnings, Montage got '
     'MORE expensive against GigaDevice, not less: 73x vs 22x annualised. A ratio that has not moved as far as the fundamentals is not a reversion candidate.'),
    ('Same theme, different engine — and the market is paying for the wrong one. ', 'Both are “China memory” (0.82 correlation over 40 days) and both H-lines trade above their A '
     '(Montage 17%, GigaDevice 8.5%), so the A/H and Southbound noise cancels. GigaDevice earns off the DDR4/NOR contract price; Montage off DDR5 RCD/MRCD/MDB units and content into '
     'AI servers. Montage is the better business — and at 73x with a 31 Aug −8% reaction to a CLSA target cut it is the one whose multiple is exposed to any AI-capex wobble. '
     'GigaDevice at 22x is priced for the cycle to end.'),
    ('The trigger is dated. ', 'TrendForce’s Q4 conventional-DRAM contract outlook comes at the end of September. Q3 was +13–18% with supplier inventories at historic lows. '
     'If Q4 prints another double-digit increase, GigaDevice’s Q3 report (late Oct) will be a second step up and the 22x collapses toward the teens; Montage cannot match that. '
     'If Q4 is flat, reverse the pair the same day — this is a cycle-continuation trade with a quality hedge, not a valuation-normalisation trade, and it should be run two-sided.'),
    ('Tradeable. ', 'Both designated, both Southbound, HK$1.0–1.5bn a day each, vols 119% / 100% over 40 days so dollar-neutral is close to beta-neutral (0.98).'),
])
table(d, STAT_HDR, [statrow('H:Montage/GigaDevice', 'Montage/GigaDevice H since 9 Feb'), statrow('H40:Montage/GigaDevice', 'Montage/GigaDevice H 40d'),
                    statrow('A:Montage_A/GigaDevice_A', 'Montage/GigaDevice A since Jan-24'), statrow('A250:Montage_A/GigaDevice_A', 'Montage/GigaDevice A 250d')], col_widths=STAT_W, font_size=8)
kv_table(d, [
    ('Legs', 'Long GigaDevice HK$20m / short Montage HK$20m, dollar-neutral.'),
    ('Entry', 'Ratio ≥ 0.55 (now 0.568); it printed 0.62 on 21 Aug — scale the second half there if it comes before the TrendForce release.'),
    ('Target', '0.46 (−19%): the 40-day low; stretch 0.40 (the 29-Jun print was 0.36).'),
    ('Stop', '0.64 (+13%) on the ratio, or an automatic flip to long Montage / short GigaDevice if the Q4 outlook is ≤ +5%.'),
    ('Horizon', 'Into the late-Oct Q3 reports; reassess at the Q1-27 contract outlook (late Dec).'),
    ('Borrow', 'Montage designated; float HK$21bn but Southbound-held, so check the lendable quantity rather than assuming GC.'),
    ('Catalysts', 'Late-Sep TrendForce Q4 outlook (the gate) · DDR4 allocation/EOL headlines from Samsung, Hynix, Micron · late-Oct Q3 prints · hyperscaler capex updates (Oct/Nov).'),
    ('Kill switches', 'Q4 outlook flat; a GigaDevice placement into the H premium; Montage announcing a large buyback or a new MRDIMM customer that re-rates it independently of memory pricing.'),
])
para(d, 'The best-defined trade in the note because it has a date and a two-sided plan. If you only run one memory position, run this one and treat pair 1 as the December follow-on.', bold_lead='Verdict. ')

h1(d, '4. Pair 3 — Long SMIC 981 / Short Hua Hong 1347')
para(d, 'Ratio Hua Hong ÷ SMIC (H): 1.685 now. You want it lower — from a bounce, not from here.', bold_lead='The trade. ')
para(d, '', bold_lead='Why.')
numbered(d, [
    ('Hua Hong re-rated 4x against SMIC in eighteen months. ', 'Hua Hong_A ÷ SMIC_A went 0.49 (Dec-24) → 2.12 (Jun-26); on the H the ratio peaked at 2.45 on 7 Jul. The story was '
     'mature-node scarcity — price hikes, full 12-inch fabs, the parent-consolidation narrative — and the whole A/H semis crowd was in it.'),
    ('The prints are good and still do not carry the multiple. ', 'Hua Hong 1H26 net profit US$59.6m, +409% on record revenue; Q2 beat and the Q3 guide was positive (Citi raised '
     'estimates). Annualise it and the H-share is 215x. SMIC 1H26 net profit US$677m, +111%; Q2 revenue above US$3bn, +20% QoQ, taking foundry share to 5.4% against Samsung’s 5.9% '
     '(TrendForce, 9 Sep) — 55x annualised. Hua Hong Group’s Q2 revenue grew 3.5% QoQ in the same table. The fast-growing, share-gaining one is the cheap one by four times.'),
    ('The ratio has already turned. ', 'From the 7-Jul peak Hua Hong is −44%, SMIC −20%; the ratio is 1.69 vs a 40-day mean of 1.91 (z −1.1) but still the 88th percentile since 2024 '
     '(mean 1.06) and 91st on the A-shares. Long-run says more to come, short-run says you are late — so stage it: a third now, the rest at 1.85–2.00, which the sector gives you about every three weeks.'),
    ('Vol asymmetry makes it net-short sector vol. ', 'Hua Hong runs 99% 60-day vol, SMIC 60%. At 0.6 of Hua Hong per 1.0 of SMIC the pair pays in a further de-rating and roughly holds in a bounce.'),
    ('What argues against, stated. ', 'TrendForce’s Q3 foundry note says mature-process capacity “could remain constrained and wafer prices may rise” — that is Hua Hong’s story '
     'continuing. On A/H terms Hua Hong’s H is at the cheap end of its own range (127% premium vs 36–190%) while SMIC’s is at the rich end (112% vs 85–335%). And Southbound has been '
     'selling both. None of it changes the direction; all of it argues for the staged entry and normal, not large, size.'),
])
table(d, STAT_HDR, [statrow('H:HuaHong/SMIC', 'Hua Hong/SMIC H since Jan-24'), statrow('H40:HuaHong/SMIC', 'Hua Hong/SMIC H 40d'),
                    statrow('A:HuaHong_A/SMIC_A', 'Hua Hong/SMIC A since Jan-24'), statrow('A250:HuaHong_A/SMIC_A', 'Hua Hong/SMIC A 250d')], col_widths=STAT_W, font_size=8)
kv_table(d, [
    ('Legs', 'Long SMIC HK$30m / short Hua Hong HK$18m (vol-neutral 0.6:1). Both HK$4–5bn a day, GC borrow.'),
    ('Entry', 'One-third at 1.69; the rest at ≥ 1.85 if the bounce comes without a Hua Hong-specific catalyst.'),
    ('Target', '1.30 (−23%): the May level.'),
    ('Stop', '2.10 on the ratio, or Hua Hong guiding Q4 gross margin up with rising utilisation at its ~6 Nov print.'),
    ('Horizon', '3–6 months through the November Q3 prints (Hua Hong ~6 Nov, SMIC ~12 Nov).'),
    ('Catalysts', 'Q3 results and Q4 guides (Nov) · terms and timing of the parent asset injection · mature-node pricing commentary from TSMC/UMC/Vanguard (Oct) · export-control headlines (hit SMIC harder — the asymmetric risk to the long leg).'),
    ('Kill switches', 'Asset injection at an accretive price with a fast timetable; another round of 8-inch/12-inch price hikes above 10%; an SMIC-specific US action; SMIC equity raise.'),
])
para(d, 'Right direction, wrong moment — the 40-day move did a third of the work and Hua Hong’s own print was good. Stage it and let the next sector bounce set the size.', bold_lead='Verdict. ')

h1(d, '5. Pair 4 — Long Innoscience 2577 / Short SICC 2631')
para(d, 'Ratio Innoscience ÷ SICC (H): 0.670 now. You want it higher.', bold_lead='The trade. ')
para(d, '', bold_lead='Why.')
numbered(d, [
    ('The August prints point the same way as the thesis. ', 'Innoscience 1H26: revenue RMB834m +51%, gross margin 11.6% (+4.8pts), loss narrowed to RMB309m from RMB429m. '
     'SICC 1H26: revenue RMB914m +15%, swung to a RMB58.6m loss from a small profit — volume up, price down. One has expanding margins, one contracting, on similar revenue.'),
    ('SiC substrates are a commodity with a Chinese supply curve. ', 'SICC has the share (27.6% in 2025, 51% of 8-inch, per CMBI’s initiation) and it still cannot make money, because '
     'capacity across SICC, TankeBlue, SanAn and others tripled in three years and 8-inch is the next price front. Wolfspeed’s 2025 restructuring is what the leader looks like in this market. '
     'SICC’s overseas customers — near half of sales — are the ones dual-sourcing and squeezing.'),
    ('GaN is on the other side of its curve. ', 'Fast chargers → data-centre 48V/800V power stages → auto → motor drives. Innoscience is the volume leader on 8-inch GaN-on-Si, the '
     'operating leverage is now visible in the print, it just won a patent round (CLSA: “proves independent innovation capability”), and Daiwa initiated at Buy on data-centre GaN. '
     'Broker targets sit at HK$74–112 against a HK$44.5 price after the sector unwind.'),
    ('Price says the market has it backwards. ', 'Ratio 0.67 vs a one-year mean of 1.03, 14th percentile since SICC listed. On annualised 1H26 sales the H-shares are ~21x (Innoscience) '
     'vs ~15x (SICC) — you pay a third more for the one growing three times faster with margins going the right way. SICC also carries a 76% A-premium, so its H is the cheap line vs the mainland; that is the one thing to respect on the short.'),
    ('Tradeable. ', 'Both designated and Southbound, ~HK$200m a day each, lock-ups expired. 40-day correlation 0.67, vols 67% / 83%.'),
])
table(d, STAT_HDR, [statrow('H:Innoscience/SICC', 'Innoscience/SICC H since 20 Aug-25'), statrow('H40:Innoscience/SICC', 'Innoscience/SICC H 40d')], col_widths=STAT_W, font_size=8)
kv_table(d, [
    ('Legs', 'Long Innoscience HK$10m / short SICC HK$8m (vol-neutral 0.8:1). Two sessions to build at 10% of ADV.'),
    ('Entry', 'Ratio ≤ 0.70 (now 0.670).'),
    ('Target', '0.90 (+34%); take half at 0.80.'),
    ('Stop', '0.55 (−18%): the 11-Aug low was 0.542.'),
    ('Horizon', '3–6 months.'),
    ('Catalysts', 'SICC Q3 (late Oct) — ASP and gross margin, not revenue · Innoscience data-centre design-win announcements and any 2H trading update · Infineon/onsemi/ST SiC pricing commentary (Oct/Nov) · SiC capacity closures.'),
    ('Kill switches', 'The remaining US patent cases (EPC/Infineon) producing an import restriction — sentiment hit even if commercially small; an Innoscience placement; an 800V-EV or AI-DC SiC demand surprise lifting 8-inch pricing; SICC’s A-premium compressing via the H rallying.'),
])
para(d, 'Good pair, half the liquidity of 2 and 3, so half the size. The patent docket is the risk you cannot model — keep an alert on it.', bold_lead='Verdict. ')

# ---------------- watch list ----------------
h1(d, '6. Watch list — not yet')
h2(d, 'Iluvatar 9903 vs Biren 6082')
bullets(d, [
    'Biren ÷ Iluvatar is 0.121 — the 98th percentile of the last 40 sessions (0.061 on 28 Jul). Iluvatar is −51% from the June top and fell 11.4% on Monday with no headline behind it; Biren is +6% since mid-August.',
    'The 1H26 print explains the de-rating, not Monday: revenue RMB946m (+192% YoY, +33% HoH) but gross margin fell from 50.1% to 17.2% on reselling components below cost and inventory impairment; net profit RMB106m. '
    'Macquarie, CMBI, BofA and Morgan Stanley cut targets to HK$668–1,060 — still two to three times the price — and it was added to Hang Seng TECH at the last review. New flagship GPGPU launched 20 Jul.',
    'Mean reversion says long Iluvatar / short Biren; you do not buy an −11% day in a name with a 17% gross margin until you know whether it was index flow (Monday was rebalance day) or a block. '
    'Both designated, HK$0.5–0.8bn a day. Alert at 0.13 with the cause identified; a third of pair-2 size.',
])
h2(d, 'Long Horizon 9660 / short Black Sesame 2533')
bullets(d, [
    'Quality vs cash burn inside the same de-rated sub-sector. Both ~58% off their autumn-2025 highs, neither joined the June melt-up. Both are designated (verified) — but Black Sesame trades HK$54m a day on a HK$7.6bn float, so borrow will be small and special.',
    'It is not a pair: 40-day correlation 0.35, beta 0.25–0.37. Ratio 0.414, 70th percentile since Oct-24. Do it as long Horizon with a HSTECH hedge unless borrow is genuinely there. Neither name’s 1H26 print was checked for this note.',
])
h2(d, 'OmniVision 501 / Gpixel 3277 — dead')
bullets(d, [
    'The valuation gap is real (20x vs 115x trailing, CIS leader vs machine-vision niche) but Gpixel is not on the designated list, so the pair does not exist. OmniVision on its own — 20x, 30% A-discount, designated, Southbound, but only HK$30m a day — is a long candidate against the SMIC hedge for small size.',
])
h2(d, 'SG Micro 3661 / Novosense 2676')
bullets(d, [
    'Analog pair, profitable vs loss-making, ratio at the 8th percentile since June. Both trade HK$40–60m a day, Novosense’s H sits at an 80% A-discount (the cheap line — bad to be short if premia compress), and SG Micro’s own unlock is 26 Dec. Parked.',
])

# ---------------- calendar & how-to ----------------
h1(d, '7. Calendar')
table(d, ['Date', 'Event', 'Matters for'], [
    ['late Sep', 'TrendForce Q4-26 DRAM/NAND/NOR contract price outlook', 'Pairs 1, 2 — the gate'],
    ['late Oct', 'A-share Q3 reports: Nexchip, GigaDevice, Montage, SICC, SG Micro, Novosense (by 31 Oct)', 'All'],
    ['~6 Nov / ~12 Nov', 'Hua Hong / SMIC Q3 results with Q4 guides', 'Pair 3'],
    ['~20 Nov', 'Hang Seng Composite December review announced (Ingenic Southbound candidate)', 'Sector supply'],
    ['7 Dec', 'HSI review effective (Monday after first Friday) — Southbound changes go live', 'Flows'],
    ['mid-Dec', 'HKEX quarterly short-sell designation review (last one took effect 11 Sep) — Nexchip, SG Micro, CFMEE, Gpixel candidates', 'Pair 1 — the real short opens'],
    ['late Dec', 'TrendForce Q1-27 contract price outlook', 'Pairs 1, 2 — reassess'],
    ['26 Dec', 'SG Micro / CFMEE cornerstone unlock', 'Watch list'],
    ['10 Jan 2027', 'Nexchip cornerstone unlock (six months from 10 Jul)', 'Pair 1 — the short leg’s catalyst'],
    ['30 Jan / 25 Feb 2027', 'Innolight / Ingenic cornerstone unlocks', 'Sector supply'],
], col_widths=[2.8, 10.6, 3.8], font_size=8.5, align_right_from=99)

h1(d, '8. How to run them')
bullets(d, [
    ('Stop on the spread, not the leg. ', 'Every stop above is a ratio level. A leg-level stop in a 100%-vol name takes you out of the hedge and leaves you naked in the other one.'),
    ('Size to the illiquid leg. ', 'Nexchip, Innoscience/SICC, anything on the watch list: 10% of 20-day ADV per session, VWAP, and assume the exit takes as long as the entry.'),
    ('Rebalance on ±15% leg drift, ', 'not daily. Vol-neutral ratios assume the vols hold; if GigaDevice’s vol halves after the memory tape calms, the 0.6:1 in pair 1 becomes too small a hedge — recheck monthly.'),
    ('Do not stack the same long. ', 'Pairs 1 and 2 are both long GigaDevice; the book’s net long in one 100%-vol name should not exceed one pair’s worth.'),
    ('Check three things the morning you trade: ', 'the HKEX designated list (designation is binary), the borrow rate and quantity (Southbound-held floats lend badly), and whether an index-day close distorted the ratio you are entering on.'),
])

h1(d, '9. What in this note is measured, verified, or read')
bullets(d, [
    ('Measured: ', 'every price, return, ratio, percentile, correlation, beta, vol, ADV, A/H premium and H float — HKEX daily prints to 7 Sep 2026, A-shares SSE/SZSE, FX 1.1674.'),
    ('Verified against primary lists (9–11 Sep): ', 'short-sell designation from the HKEX lists effective 1, 10 and 11 Sep 2026 (file in _pairs_note/data); Southbound eligibility from the SZSE 港股通标的 list dated 9 Sep 2026.'),
    ('Verified from results headlines (AAStocks, company announcements): ', '1H26 prints for GigaDevice, Montage, Nexchip, SMIC, Hua Hong, Innoscience, SICC, Iluvatar; TrendForce releases of 7 Sep (DRAM) and 9 Sep (foundry); the broker target changes quoted.'),
    ('Read, not verified this week: ', 'the Hua Hong Q3 guidance numbers and the asset-injection terms; 1H26 prints for Biren, Horizon, Black Sesame; the exact 7 Sep index constituent changes and Nexchip’s Southbound inclusion date; the cause of Iluvatar’s Monday fall; the SiC/GaN industry pricing commentary. '
     'Lock-up dates are computed as six months from listing. Annualised P/Es are 2× the first half on the 7 Sep H-share market cap.'),
])

out = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'HK_Semi_Pair_Trades_Sep2026.docx')
d.save(out)
print('saved', out)
