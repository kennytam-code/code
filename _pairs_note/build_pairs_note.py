"""Build HK_Semi_Pair_Trades_Sep2026.docx from data/ (prices 7-Sep-2026 close)."""
import csv, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from docx_helpers import *

D = os.path.join(os.path.dirname(__file__), 'data')
snap = {r['name']: r for r in csv.DictReader(open(os.path.join(D, 'snapshot.csv')))}
ahp = json.load(open(os.path.join(D, 'ahp.json')))
ps = json.load(open(os.path.join(D, 'pairstats.json')))
q = json.load(open(os.path.join(D, 'quotes.json')))
CODE = {'SMIC': '981', 'HuaHong': '1347', 'ASMPT': '522', 'Nexchip': '2249', 'GigaDevice': '3986', 'Montage': '6809',
        'OmniVision': '501', 'SGMicro': '3661', 'Novosense': '2676', 'NSing': '2701', 'Fortior': '1304', 'SICC': '2631',
        'CFMEE': '9630', 'Ingenic': '3223', 'Biren': '6082', 'Iluvatar': '9903', 'Axera': '600', 'BlackSesame': '2533',
        'Horizon': '9660', 'Innoscience': '2577', 'Gpixel': '3277', 'Innolight': '3308', 'Epiworld': '2726',
        'FourSemi': '3625', 'Viewtrix': '3310', 'Senasic': '6675', 'BasicSemi': '9971', 'TianyuSemi': '2658'}
LABEL = {'SMIC': 'SMIC', 'HuaHong': 'Hua Hong', 'ASMPT': 'ASMPT', 'Nexchip': 'Nexchip 晶合', 'GigaDevice': 'GigaDevice 兆易',
         'Montage': 'Montage 澜起', 'OmniVision': 'OmniVision 豪威', 'SGMicro': 'SG Micro 圣邦', 'Novosense': 'Novosense 纳芯微',
         'NSing': 'NSing 国民技术', 'Fortior': 'Fortior 峰岹', 'SICC': 'SICC 天岳', 'CFMEE': 'CFMEE 芯碁', 'Ingenic': 'Ingenic 君正',
         'Biren': 'Biren 壁仞', 'Iluvatar': 'Iluvatar 天数', 'Axera': 'Axera 爱芯', 'BlackSesame': 'Black Sesame 黑芝麻',
         'Horizon': 'Horizon 地平线', 'Innoscience': 'Innoscience 英诺赛科', 'Gpixel': 'Gpixel 长光辰芯', 'Innolight': 'Innolight 中际旭创',
         'Epiworld': 'Epiworld', 'FourSemi': 'FourSemi', 'Viewtrix': 'Viewtrix', 'Senasic': 'Senasic', 'BasicSemi': 'BasicSemi', 'TianyuSemi': 'Tianyu Semi'}


def qf(name, i):
    f = q.get('hk' + CODE[name].zfill(5))
    return f[i] if f else None


def hfloat_bn(name):
    v = qf(name, 44)
    return float(v) / 10 if v else None


def pe(name):
    v = qf(name, 39)
    if not v: return 'n/a'
    v = float(v)
    return 'loss' if v < 0 else f"{v:.0f}x"


def s(name, k, nd=1, pct=True, sign=True):
    v = snap[name][k]
    return fmt(v, nd, pct=pct, sign=sign)


d = new_doc()
title(d, 'HK Semis — Pair Trade Ideas',
      'Written 8 Sep 2026 · prices = 7 Sep 2026 HKEX close (Tencent/HKEX prints), A-shares SSE/SZSE close, CNYHKD 1.1674 · '
      'ratios are H-share price ratios unless marked A · trader audience, internal')

para(d, 'Short version. The HK semi complex topped 25–30 June and is 20–60% off the highs while HSTECH is +3% over the same window, '
        'so this was a sector unwind (A-share crowd rotating out, IPO supply, July–August lock-up expiries), not a market fall. '
        'That leaves a lot of dispersion inside the group, which is where the pairs are. Four I would actually put on, three to watch:', bold_lead='')
numbered(d, [
    ('Long Nexchip 2249 / short GigaDevice 3986. ', 'The tradeable direction of the pair you asked about — Nexchip is not shortable yet. '
     'H at a 53% discount to its A with Southbound inclusion ahead, against a memory name whose H trades ABOVE its A on 190x trailing.'),
    ('Long Montage 6809 / short GigaDevice 3986. ', 'The cleanest memory pair: content growth (DDR5/MRDIMM/retimers) vs commodity price (DDR4/NOR). '
     'Ratio at a 2-year low on the A-shares, 0.82 correlation, both liquid and shortable.'),
    ('Long SMIC 981 / short Hua Hong 1347. ', 'Hua Hong/SMIC ratio still at the 88th–91st percentile of two years after a 30% give-back; 468x trailing vs 110x. '
     'Enter on a bounce, not here.'),
    ('Long Innoscience 2577 / short SICC 2631. ', 'GaN adoption curve vs SiC substrate price war; ratio 0.67 vs a one-year mean of 1.03.'),
    ('Watch: ', 'Horizon/Black Sesame (quality, but 0.35 correlation and thin borrow), Iluvatar/Biren (ratio at a 40-day extreme after Iluvatar’s −11% Monday — find the cause first), '
     'OmniVision/Gpixel (20x vs 115x, but the long leg trades HK$30m a day).'),
])
para(d, 'Two housekeeping points before the detail. (a) Pairs 1 and 2 share the same short; run one, or halve both and swap SMIC in as the short leg of pair 1. '
        '(b) Spread vols in this group are 45–90% annualised — a 20% ratio move inside three months is roughly a half-sigma event, so the edge in every one of these is the '
        'catalyst sequence and the structural set-up, not the z-score. Size accordingly (half normal) and stop on the spread, never on a leg.', size=10)

# ---------------- Section 1: the tape ----------------
h1(d, '1. Where the group is')
bullets(d, [
    ('The top was 25–30 June. ', 'GigaDevice 1,241 (29 Jun) → 492 now, Hua Hong 215 → 115, Iluvatar 793 → 340, Montage 501 (13 May) → 279, ASMPT 239 → 168. '
     'SMIC only −20% from its October-2025 high — the big liquid name held, the 2026 IPO cohort did not.'),
    ('Supply explains the timing. ', 'The January–February H-listings all came out of their six-month cornerstone lock-ups between 2 Jul (Biren) and 10 Aug (Axera): '
     'Iluvatar 8 Jul, OmniVision 12 Jul, GigaDevice 13 Jul, Montage 9 Aug. On top of that: Nexchip listed 10 Jul, Innolight 30 Jul, Ingenic 25 Aug. '
     'Free float in the sector roughly doubled in eight weeks.'),
    ('A/H tells you who owns what. ', 'Memory names trade with the H ABOVE the A — GigaDevice H at an 8.5% premium to its A, Montage 17%, Innolight 13% — '
     'which only happens when Southbound plus offshore money is crowding into an H float that is a fraction of the A float (GigaDevice H float HK$16bn vs A HK$300bn). '
     'Foundries are the opposite: SMIC H at a 112% A-premium, Hua Hong 127%, Nexchip 53% (was 96% on debut, 35% at the 14-Aug low).'),
    ('Monday 7 Sep was index day. ', 'The Hang Seng quarterly review took effect (Monday after the first Friday of September) and the tape looked like it: '
     'Innolight +19.6%, CFMEE +12.9%, Montage +6.7%, GigaDevice +5.8% against Iluvatar −11.4%, Axera −12.5%, FourSemi −18%, Gpixel −8%. '
     'Treat Monday’s closes as flow-distorted when you set entry levels — check the constituent changes on hsi.com.hk before trusting any single-day ratio.'),
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
table(d, ['Code / name', 'Last', '1m', '3m', 'From high (date)', 'vs IPO', 'Vol 60d %', 'ADV20 HK$m', 'P/E trail', 'A-prem', 'H float HK$bn'], rows,
      col_widths=[3.6, 1.3, 1.1, 1.1, 2.3, 1.2, 1.3, 1.6, 1.3, 1.3, 1.5], font_size=8)
para(d, 'P/E is the trailing multiple on the quote feed (“loss” = negative earnings). A-prem = A-share price in HKD over H price, minus one; negative means the H is the more expensive line. '
        'H float = H-share market cap (what is actually tradeable/lendable in HK). vs IPO shown for 2025–26 listings only.', size=8.5, italic=True, color=GREY)

h2(d, 'Plumbing — what you can and cannot short')
para(d, 'HKEX only allows covered shorts in “designated securities”. Regular criteria: market cap ≥ HK$3bn and 12-month turnover velocity ≥ 60%, reviewed quarterly; '
        'a fast-track exists for new listings with public float ≥ HK$20bn over 20 sessions and ≥ HK$500m turnover. Applying the rules to the float/turnover numbers above '
        '(this is the rule-based read — confirm on the HKEX list the morning you trade):', size=10)
table(d, ['Name', 'Shortable now?', 'Why', 'Southbound', 'Lock-up (cornerstone, 6m)'], [
    ['SMIC 981 / Hua Hong 1347', 'Yes', 'index heavyweights, GC borrow', 'Yes', '—'],
    ['GigaDevice 3986', 'Yes (expected)', 'fast-track: float HK$16bn at IPO, ran >HK$20bn by Feb; ADV HK$1.5bn', 'Yes (2026)', 'expired 13 Jul 2026'],
    ['Montage 6809', 'Yes (expected)', 'float HK$21bn, ADV HK$1.0bn', 'Yes (2026)', 'expired 9 Aug 2026'],
    ['Nexchip 2249', 'NO', 'float HK$6.2bn (<HK$20bn fast-track); listed 10 Jul → earliest = Nov quarterly review', 'Not yet — Dec review (eff. ~7 Dec)', '10 Jan 2027'],
    ['Ingenic 3223 / Innolight 3308', 'No / probably (fast-track)', 'Ingenic float HK$3.2bn; Innolight float HK$75bn, ADV HK$1.8bn', 'No / check fast-entry', '25 Feb 2027 / 30 Jan 2027'],
    ['OmniVision 501', 'Probably (May/Aug review)', 'float HK$3.7bn, velocity ~200% — but ADV only HK$30m', 'Yes (2026)', 'expired 12 Jul 2026'],
    ['SICC 2631 / Innoscience 2577', 'Yes', 'listed Aug-25 / Dec-24; ADV HK$180m / 210m', 'Yes / Yes', 'expired'],
    ['Horizon 9660 / Black Sesame 2533', 'Yes / Yes (thin)', 'Black Sesame float HK$7.6bn, ADV HK$54m — borrow will be small and special', 'Yes / Yes', 'expired'],
    ['Biren 6082 / Iluvatar 9903', 'Yes (expected)', 'float HK$56bn / 88bn, ADV HK$0.5bn / 0.8bn', 'Yes (2026)', 'expired 2 Jul / 8 Jul 2026'],
    ['Gpixel 3277', 'Probably (fast-track)', 'float HK$25bn, ADV HK$61m', 'check', 'expired'],
    ['SG Micro 3661 / Novosense 2676', 'No (Nov review) / probably', 'SG Micro float HK$5.5bn, listed 26 Jun; Novosense float HK$3.2bn', 'check / Yes', '26 Dec 2026 / expired'],
], col_widths=[3.6, 2.4, 6.0, 2.6, 2.6], font_size=8, align_right_from=99)

# ---------------- Section 2: pairs ----------------
def statrow(key, label):
    p = ps[key]
    return [label, f"{p['ratio']:.3f}" if p['ratio'] < 5 else f"{p['ratio']:.2f}", f"{p['ratio_mean']:.3f}" if p['ratio_mean'] < 5 else f"{p['ratio_mean']:.2f}",
            (f"{p['ratio_min']:.3f} – {p['ratio_max']:.3f}" if p['ratio_max'] < 5 else f"{p['ratio_min']:.2f} – {p['ratio_max']:.2f}"),
            f"{p['pct']:.0f}", f"{p['z']:+.1f}", f"{p['corr']:.2f}", f"{p['beta']:.2f}", f"{p['volL']:.0f} / {p['volS']:.0f}", f"{p['sv']:.0f}", str(p['n'])]


STAT_HDR = ['Window', 'Ratio now', 'Mean', 'Min – max', 'Pctile', 'z', 'Corr', 'Beta (num on den)', 'Vol num / den %', 'Spread vol 1:1 %', 'n']
STAT_W = [3.4, 1.5, 1.4, 2.6, 1.1, 0.9, 1.0, 1.7, 1.9, 1.7, 0.8]

h1(d, '2. Pair 1 — Long Nexchip 2249 / Short GigaDevice 3986')
para(d, 'Ratio quoted as GigaDevice ÷ Nexchip (H prices): 17.9 now. You want it lower.', bold_lead='The trade. ')
para(d, '', bold_lead='Why.')
numbered(d, [
    ('You cannot short Nexchip, so the question is only whether to be long it. ', 'H float is HK$6.2bn (10% of the company), listed 10 Jul: no fast-track, and the regular '
     'designation needs the November review. Anyone who wants to be short the DDIC foundry story is stuck until then — the first two months of a new H-line with no '
     'shorts and no Southbound is exactly when the discount is widest.'),
    ('The discount is the trade. ', 'Nexchip H is 53% below its A (A HK$42.0 equivalent vs H HK$27.5). It was 96% on debut and 35% at the 14-Aug low, so it has already closed '
     'once on nothing but offshore buying; it re-widened as the H fell 25% from 17 Aug on sector supply while the A fell less. Southbound is the marginal buyer that closes '
     'these — Nexchip missed the September HSCI review (30-Jun cut-off) so the December review (announced ~20 Nov, effective ~7 Dec) is the date. Every 2026 A+H chip '
     'listing has seen its discount compress into and through inclusion; GigaDevice and Montage went all the way through zero.'),
    ('GigaDevice is the expensive line of an expensive story. ', 'Its H trades 8.5% ABOVE the A on 190x trailing earnings (feed). That premium is Southbound and offshore money '
     'crowding an H float of HK$16bn — it is a positioning artefact, not a valuation, and it reverses when the memory tape turns. The 2026 re-rating is a DDR4/LPDDR4 and '
     'NOR price story (the majors walked away from legacy DRAM); GigaDevice is fabless and buys its DRAM wafers, so it rents the price cycle — margin goes up with contract '
     'prices and comes down with them, and Q4 contract pricing (TrendForce, end-Sep) is the first place the second derivative shows.'),
    ('The A-share ratio says the same thing. ', 'GigaDevice_A ÷ Nexchip_A is 10.7 — the 95th percentile since January 2024 (mean 6.3; 250-day mean 8.5; peaked 13.8 on 29 Jun). '
     'The H ratio of 17.9 is that 10.7 times the two A/H distortions (1.53 ÷ 0.915). Both components — the A-ratio and the A/H gap — point the same way.'),
    ('What Nexchip actually is. ', '12-inch mature-node foundry: display drivers are over half of revenue, then CIS, PMIC, MCU; 28nm OLED DDIC ramping; heavy depreciation, '
     'low-20s gross margin, 79x trailing on the H (feed). Not a great business, and DDIC pricing into a flat panel market is the weak spot — but you are not paying for the '
     'business, you are paying 47% of the price the A-share market pays for the same claim, with a date on which that gap gets a buyer.'),
])
table(d, STAT_HDR, [statrow('H:GigaDevice/Nexchip', 'H since 10 Jul (41d)'), statrow('H40:GigaDevice/Nexchip', 'H last 40d'),
                    statrow('A:GigaDevice_A/Nexchip_A', 'A-shares since Jan-24'), statrow('A250:GigaDevice_A/Nexchip_A', 'A-shares last 250d'),
                    statrow('H:SMIC/Nexchip', 'Alt short: SMIC/Nexchip (H)')], col_widths=STAT_W, font_size=8)
kv_table(d, [
    ('Legs', 'Long Nexchip 2249 HK$5m / short GigaDevice 3986 HK$3.5m (vol-neutral 0.7:1; 1:1 dollar gives spread vol 78%, 0.7:1 gives ~58%). Beta-neutral would be 0.47:1 but leaves you net long sector.'),
    ('Size', 'Cap the long leg at ~10% of ADV per day: Nexchip trades HK$54m/day, so HK$5m is a two-session build. GigaDevice (HK$1.5bn/day) is a click.'),
    ('Entry', 'Ratio ≥ 17.5 (now 17.9). Do not chase below 16.5.'),
    ('Target', '15.0 (−16%): the mid-August level where Southbound anticipation last took the discount to 35%. Stretch 13.5 if the A-ratio also mean-reverts to its 250-day mean.'),
    ('Stop', '20.5 (+15%) on the ratio, or GigaDevice’s A/H premium widening past 15% (means Southbound is re-crowding the H — the thesis is wrong for now).'),
    ('Horizon / time stop', 'Into the 7 Dec inclusion; be flat before 10 Jan 2027 (cornerstone unlock on the long leg).'),
    ('Borrow', 'GigaDevice should be designated (verify). Lendable float excludes Southbound holdings, so the pool is smaller than HK$16bn — budget 1–3% and check the rate before sizing.'),
    ('Catalysts', 'End-Sep TrendForce Q4 DRAM/NOR contract outlook · late-Oct A-share Q3 reports (both) · ~20 Nov HSCI review announcement · Nov HKEX short-sell review (Nexchip designated → the reverse trade opens) · ~7 Dec inclusion.'),
    ('Kill switches', 'Nexchip Q3 gross margin below Q2 (DDIC ASP/depreciation) with no volume offset; a Nexchip A-share raise or convertible; DRAM contract prices accelerating again in Q4 (GigaDevice EPS upgrades keep coming).'),
])
para(d, 'Put it on, small, and treat it as a dated trade. If you only want one memory short, use SMIC as the short leg here instead (corr 0.65, spread vol 45% beta-adjusted) and keep the GigaDevice short for pair 2.', bold_lead='Verdict. ')

h1(d, '3. Pair 2 — Long Montage 6809 / Short GigaDevice 3986')
para(d, 'Ratio Montage ÷ GigaDevice (H): 0.568 now. You want it higher.', bold_lead='The trade. ')
para(d, '', bold_lead='Why.')
numbered(d, [
    ('Same theme, different engine. ', 'Both are “China memory”, and the market trades them together (correlation 0.82 over 40 days, 0.73 since February). But GigaDevice’s '
     'earnings move with the DDR4/NOR contract price; Montage’s move with units and content — DDR5 penetration in servers, RCD generation upgrades (each gen carries a higher ASP), '
     'MRCD/MDB for MRDIMM in AI servers, PCIe 5/6 retimers, CKD on the client side. One is a price cycle, the other is an AI-server bill-of-materials line.'),
    ('The market has paid for the cycle and left the content story behind. ', 'Montage_A ÷ GigaDevice_A averaged ~0.70 through 2025, hit 0.38 at GigaDevice’s 29-Jun blow-off, '
     'and is 0.51 now — the 12th percentile since January 2024. On the H it is 0.568 vs a 40-day range of 0.46–0.62. Trailing P/E 138x vs 190x (feed): the faster, more visible '
     'earnings stream is the cheaper one.'),
    ('Price cycles roll; content ramps do not. ', 'Legacy-DRAM tightness came from supplier exit, which is a one-off step; once contract increases decelerate (the Q4 print is the '
     'first candidate) the earnings-revision momentum that carried GigaDevice reverses, and it reverses first in the H line that is priced above the A. Montage’s Q3/Q4 are '
     'driven by hyperscaler DDR5/MRDIMM builds already in backlog.'),
    ('The A/H component cancels. ', 'Both H-lines trade above their A (Montage −17%, GigaDevice −8.5%), both are Southbound names with HK$1bn+ daily turnover, both are designated '
     'for shorting. That is why this pair is cleaner than pair 1: it is one bet (cycle vs content), not two.'),
])
table(d, STAT_HDR, [statrow('H:Montage/GigaDevice', 'H since 9 Feb (140d)'), statrow('H40:Montage/GigaDevice', 'H last 40d'),
                    statrow('A:Montage_A/GigaDevice_A', 'A-shares since Jan-24'), statrow('A250:Montage_A/GigaDevice_A', 'A-shares last 250d')], col_widths=STAT_W, font_size=8)
kv_table(d, [
    ('Legs', 'Long Montage HK$20m / short GigaDevice HK$20m, dollar-neutral (40-day beta 0.98, vols 119% / 100%). Both legs are a click at this size.'),
    ('Entry', 'Ratio ≤ 0.57 (now 0.568). Add at 0.52 if it gets there without news.'),
    ('Target', '0.70 (+23%) — the 2025 average of the A-share ratio, i.e. the pre-cycle relationship. Take half at 0.64.'),
    ('Stop', '0.47 (−17%): the 40-day low (0.464) and below the post-June rebound base.'),
    ('Horizon', '3–6 months, through two quarterly prints and one TrendForce quarter-end.'),
    ('Borrow', 'GigaDevice as above; Montage no borrow needed. Both H floats are Southbound-held — check the lendable pool, not the float.'),
    ('Catalysts', 'End-Sep TrendForce Q4 contract-price outlook (the trigger) · late-Oct Q3 reports · DDR4 EOL/allocation headlines from Samsung/Hynix/Micron · hyperscaler capex updates (Oct/Nov earnings) · MRDIMM adoption news.'),
    ('Kill switches', 'Q4 DRAM contract prices re-accelerating (+20% or more); GigaDevice sourcing its own DDR4/LPDDR4 capacity at fixed cost (turns it from renter to owner); Montage guiding a customer inventory digestion; a Montage placement.'),
])
para(d, 'Best risk/reward in the note: high correlation, similar vols, no A/H noise, a dated catalyst. If you run only one memory pair, run this one.', bold_lead='Verdict. ')

h1(d, '4. Pair 3 — Long SMIC 981 / Short Hua Hong 1347')
para(d, 'Ratio Hua Hong ÷ SMIC (H): 1.685 now. You want it lower — but not from here; wait for a bounce.', bold_lead='The trade. ')
para(d, '', bold_lead='Why.')
numbered(d, [
    ('Hua Hong re-rated 4x against SMIC in eighteen months. ', 'Hua Hong_A ÷ SMIC_A went 0.49 (Dec-24) → 2.12 (Jun-26); on the H the ratio peaked at 2.45 on 7 Jul. It was a '
     'capacity-scarcity story — mature-node price hikes, 12-inch utilisation, the parent asset-consolidation narrative — and the whole A/H semis crowd was in it.'),
    ('Earnings cannot hold that. ', 'Hua Hong is 468x trailing on the H (feed): ~HK$200bn of market cap on roughly HK$0.4bn of earnings, because the new 12-inch fab’s '
     'depreciation sits on the P&L for years and single-digit price hikes do not move a low-teens gross margin enough. SMIC is 110x trailing on the same feed, and its demand '
     'is the structural one in China semis — every domestic AI accelerator is made at SMIC’s advanced nodes, and that capacity is the bottleneck of the whole domestic AI build.'),
    ('The ratio has already turned, which is the problem and the opportunity. ', 'From the 7-Jul peak: Hua Hong −44%, SMIC −20%; the ratio is 1.69 vs a 40-day mean of 1.91 '
     '(z −1.1). It is still the 88th percentile since 2024 (mean 1.06) and 91st on the A-shares — so the long-run says more to come, the short-run says you are late. '
     'Resolution: scale in on a bounce toward 1.85–2.00, which the sector gives you roughly every three weeks.'),
    ('Vol asymmetry makes the pair net-short sector vol. ', 'Hua Hong runs 99% 60-day vol vs SMIC 60%. Vol-neutral sizing (0.6 of Hua Hong per 1.0 of SMIC) means the pair '
     'pays in a further de-rating and roughly holds in a bounce — you are short the melt-up scenario, which is the one you already believe is over.'),
    ('The counter-argument, stated. ', 'On A/H terms Hua Hong’s H is at the cheap end of its own range (127% A-premium vs a 36–190% range, mean 98%) while SMIC’s H is at the rich '
     'end (112% vs 85–335%, mean 163%). If A/H premia mean-revert through the A falling, that is neutral for this pair; if through the H rising, it hurts. It is why the entry is on a bounce and the size is normal, not large.'),
])
table(d, STAT_HDR, [statrow('H:HuaHong/SMIC', 'H since Jan-24 (658d)'), statrow('H40:HuaHong/SMIC', 'H last 40d'),
                    statrow('A:HuaHong_A/SMIC_A', 'A-shares since Jan-24'), statrow('A250:HuaHong_A/SMIC_A', 'A-shares last 250d')], col_widths=STAT_W, font_size=8)
kv_table(d, [
    ('Legs', 'Long SMIC HK$30m / short Hua Hong HK$18m (vol-neutral 0.6:1). Both trade HK$4–5bn a day; borrow is GC.'),
    ('Entry', 'One-third now at 1.69; the rest at ≥ 1.85. Full position only if the bounce comes without a Hua Hong-specific catalyst (deal terms, guidance).'),
    ('Target', '1.30 (−23% from here): the May level, and roughly the point where Hua Hong’s premium to SMIC matches its 2025 average relationship.'),
    ('Stop', '2.10 on the ratio (a new leg of the Hua Hong story), or a Hua Hong Q3 gross-margin guide above 15% with rising utilisation — that would mean the price hikes are real earnings.'),
    ('Horizon', '3–6 months, through the November Q3 prints (Hua Hong ~6 Nov, SMIC ~12 Nov — both guide the next quarter).'),
    ('Catalysts', 'Q3 results and Q4 guides (Nov) · terms of the parent asset injection (dilution vs accretion) · mature-node pricing commentary from TSMC/UMC/Vanguard (Oct) · export-control headlines (hit SMIC harder — the one asymmetric risk to the long leg).'),
    ('Kill switches', 'Asset injection announced at an accretive price with an aggressive timetable; 8-inch/12-inch price hikes accelerating (>10%); an SMIC-specific US action; SMIC equity raise.'),
])
para(d, 'Right direction, wrong moment — the 40-day move already did a third of the work. Stage the entry and let the sector’s next bounce set the size.', bold_lead='Verdict. ')

h1(d, '5. Pair 4 — Long Innoscience 2577 / Short SICC 2631')
para(d, 'Ratio Innoscience ÷ SICC (H): 0.670 now. You want it higher.', bold_lead='The trade. ')
para(d, '', bold_lead='Why.')
numbered(d, [
    ('SiC substrates are a commodity with a Chinese supply curve. ', 'Capacity from SICC, TankeBlue, SanAn and a dozen others tripled in three years; 6-inch prices have more '
     'than halved since 2023 and 8-inch is the next front. Wolfspeed’s 2025 restructuring is what it looks like when even the leader cannot earn its cost of capital. SICC’s '
     'growth is volume at falling ASP — revenue up, margin down, and its overseas customers (near half of sales) are the ones squeezing hardest as they dual-source.'),
    ('GaN is on the other side of its curve. ', 'Penetration is rising, not saturating: fast chargers → data-centre 48V/800V power stages → auto → motor drives/humanoids. '
     'Innoscience is the volume leader on 8-inch GaN-on-Si, gross margin has crossed into positive territory and losses are narrowing — the operating leverage runs its way, '
     'and the AI-server power-architecture roadmaps (800V DC) put GaN in the bill of materials at exactly the point the market has stopped paying for it.'),
    ('The ratio says the market has it backwards. ', '0.67 vs a one-year mean of 1.03; 14th percentile since SICC listed. Both are loss-makers on the feed, both roughly '
     'HK$30–40bn of enterprise value on ~RMB 2bn of revenue — one with expanding margins, one with contracting.'),
    ('Tradeable. ', 'Both are designated and Southbound-eligible, both do ~HK$200m a day, SICC’s lock-ups are long expired. 40-day correlation 0.67, vols 67% / 83%.'),
])
table(d, STAT_HDR, [statrow('H:Innoscience/SICC', 'H since 20 Aug-25 (257d)'), statrow('H40:Innoscience/SICC', 'H last 40d')], col_widths=STAT_W, font_size=8)
kv_table(d, [
    ('Legs', 'Long Innoscience HK$10m / short SICC HK$8m (vol-neutral 0.8:1). Two sessions to build at 10% of ADV.'),
    ('Entry', 'Ratio ≤ 0.70 (now 0.670).'),
    ('Target', '0.90 (+34%); take half at 0.80.'),
    ('Stop', '0.55 (−18%): the 11-Aug low was 0.542.'),
    ('Horizon', '3–6 months.'),
    ('Catalysts', 'SICC Q3 (late Oct) — ASP and gross margin, not revenue · Innoscience 2H trading updates and data-centre design-win announcements · Infineon/onsemi/ST SiC pricing commentary (Oct/Nov) · any SiC capacity closure headlines.'),
    ('Kill switches', 'The US patent cases against Innoscience (EPC/Infineon) producing an import restriction — sentiment hit even if commercially small; an Innoscience placement; '
     'an 800V-EV or AI-DC SiC demand surprise that lifts 8-inch pricing; SICC’s A-premium (76% now) compressing via the H rallying.'),
])
para(d, 'Good pair, lower liquidity than 2 and 3, so half the size. The patent docket is the risk you cannot model — keep an alert on it.', bold_lead='Verdict. ')

# ---------------- Section 3: watch list ----------------
h1(d, '6. Watch list — not yet')
h2(d, 'Long Horizon 9660 / short Black Sesame 2533')
bullets(d, [
    'Quality vs cash burn inside the same de-rated sub-sector: Horizon has volume (J6 ramp, HSD programmes), 70%-plus gross margin and a large cash pile; Black Sesame is sub-scale with a handful of customers. Both are ~58% off their autumn-2025 highs and neither joined the June melt-up.',
    'The problem is it is not a pair: 40-day correlation 0.35 (0.46 since 2024), beta 0.25–0.37, so the short hedges very little of the long. Black Sesame’s H float is HK$7.6bn and it trades HK$54m a day — borrow will be small and special.',
    'Ratio 0.414, 70th percentile since Oct-24 (0.34 mean); this is a trend trade, not a reversion. Do it as a long Horizon with a HSTECH hedge unless borrow is genuinely there.',
])
h2(d, 'Iluvatar 9903 vs Biren 6082')
bullets(d, [
    'Biren ÷ Iluvatar is 0.121 — the 98th percentile of the last 40 sessions (0.061 on 28 Jul). Iluvatar is −51% from the June top and fell 11.4% on Monday alone; Biren is +6% since mid-August.',
    'Mean reversion says long Iluvatar / short Biren. You do not buy an −11% day in a loss-making GPU name without knowing why — both cornerstone lock-ups expired in early July, so a pre-IPO block or placement is the first thing to rule out; if it was index flow (Monday was rebalance day), the ratio reverses on its own.',
    'Set the alert at 0.13 with the cause identified. Correlation 0.64, vols 107% / 130% — size at a third of pair 2.',
])
h2(d, 'Long OmniVision 501 / short Gpixel 3277')
bullets(d, [
    '20x vs 115x trailing (feed) for two CIS names: the smartphone/auto leader at a 30% discount to its A, against an industrial machine-vision niche that ran to 111 on 30 Jun and is −24% since.',
    'Not a pair either: correlation 0.31, and the long leg trades HK$30m a day on a HK$3.7bn H float. Gpixel should be designated via the fast-track (float HK$25bn) — verify.',
    'Best used as “sell Gpixel on strength above 95” with OmniVision as the sector long you already want to own for the A/H convergence.',
])
h2(d, 'Long SG Micro 3661 / short Novosense 2676')
bullets(d, [
    'Analog pair, profitable vs loss-making, ratio 0.563 at the 8th percentile since June (A-share ratio mid-range). But both trade HK$40–60m a day, Novosense’s H sits at an 80% A-discount (the H is the cheap line — bad to be short if premia compress), and SG Micro’s own six-month unlock is 26 Dec. Park it.',
])

# ---------------- Section 4: calendar & how-to ----------------
h1(d, '7. Calendar')
table(d, ['Date', 'Event', 'Matters for'], [
    ['late Sep', 'TrendForce Q4-26 DRAM/NAND/NOR contract price outlook', 'Pairs 1, 2 (the trigger)'],
    ['~8 Oct', 'Nexchip passes 60 trading days listed — enters the pool for the November short-sell review', 'Pair 1 (reverse trade timing)'],
    ['late Oct', 'A-share Q3 reports: Nexchip, GigaDevice, Montage, SICC, SG Micro, Novosense (by 31 Oct)', 'All'],
    ['~6 Nov / ~12 Nov', 'Hua Hong / SMIC Q3 results with Q4 guides', 'Pair 3'],
    ['mid–late Nov', 'HKEX quarterly short-sell designation review (Nexchip, SG Micro, CFMEE candidates)', 'Pair 1, watch list'],
    ['~20 Nov', 'Hang Seng Composite December review announced (Nexchip Southbound inclusion)', 'Pair 1'],
    ['7 Dec', 'HSI review effective (Monday after first Friday) — Southbound changes go live', 'Pair 1'],
    ['26 Dec', 'SG Micro / CFMEE cornerstone unlock', 'Watch list'],
    ['10 Jan 2027', 'Nexchip cornerstone unlock (six months from 10 Jul)', 'Pair 1 — be flat before'],
    ['30 Jan / 25 Feb 2027', 'Innolight / Ingenic cornerstone unlocks', 'Sector supply'],
], col_widths=[2.8, 10.6, 3.8], font_size=8.5, align_right_from=99)

h1(d, '8. How to run them')
bullets(d, [
    ('Stop on the spread, not the leg. ', 'Every stop above is a ratio level. A leg-level stop in a 100%-vol name gets you out of the hedge and leaves you naked in the other one.'),
    ('Size to the illiquid leg. ', 'Nexchip, Innoscience/SICC, anything on the watch list: 10% of 20-day ADV per session, VWAP, and assume the exit takes as long as the entry.'),
    ('Rebalance on ±15% leg drift, ', 'not daily. Vol-neutral ratios assume the vols hold; if GigaDevice’s vol halves after the memory tape calms, the 0.7:1 in pair 1 becomes too small a hedge — recheck monthly.'),
    ('Do not stack the same short. ', 'Pairs 1 and 2 are both short GigaDevice; the book’s net short in one 100%-vol name should not exceed one pair’s worth.'),
    ('Check three things the morning you trade: ', 'the HKEX designated-securities list (shortable or not), the borrow rate and quantity (Southbound-held floats lend badly), and whether Monday’s index-day close distorted the ratio you are entering on.'),
])

h1(d, '9. What in this note is measured vs what is a read')
bullets(d, [
    ('Measured: ', 'every price, return, ratio, percentile, correlation, beta, vol, ADV, A/H premium and H float above — HKEX daily prints to 7 Sep 2026, A-shares SSE/SZSE, FX 1.1674.'),
    ('Rule-based: ', 'short-sell eligibility and Southbound/lock-up dates are derived from the HKEX and Hang Seng rules applied to listing dates and floats. Verify each on the exchange lists before dealing — designation is binary and the list is the only source.'),
    ('Read, not verified this week: ', 'the business descriptions and the cycle arguments (DDR4/NOR pricing, DDIC, SiC ASP, GaN adoption, the Hua Hong asset consolidation). '
     'They are the framework; the August interim results and the September TrendForce release are the two documents that can break them, and both should be checked against sections 2–5 before sizing up.'),
])

out = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'HK_Semi_Pair_Trades_Sep2026.docx')
d.save(out)
print('saved', out)
