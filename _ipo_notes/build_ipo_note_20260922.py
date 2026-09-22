"""Kinwong / RoboTechnik / Red Avenue / Direct Drive - HK IPO note, written 22 Sep 2026.

Run:  /tmp/ipo_venv/bin/python _ipo_notes/build_ipo_note_20260922.py
Out:  Kinwong_RoboTechnik_RedAvenue_DirectDrive_IPO_Note.docx  (repo root)

Where the numbers come from
  deal terms / financials : the four prospectuses dated 21 Sep 2026
                            (_ipo_db/scrape/text_cache/newlist_{3228,3757,9607,6731}_*.txt)
  peer prices / multiples : data_20260922/peers_out.json  (pull_peers.py - Tencent quotes,
                            Eastmoney reported periods) and hkus_out.json (pull_hkus.py)
  FX                      : CNY/HKD 1.1713 (Yahoo, 21 Sep)
  day-one margin          : Zhitong broker tally, 21 Sep
Conventions
  H P/E for an A+H name   = A-share P/E x (H price in CNY / A price)
  "ann. 1H26"             = market cap / (2 x 1H26 parent net profit)
  TTM                     = FY25 + 1H26 - 1H25
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from docx_helpers import new_doc, title, h1, h2, para, bullets, table  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), "Kinwong_RoboTechnik_RedAvenue_DirectDrive_IPO_Note.docx")

d = new_doc()
title(d, "Kinwong, RoboTechnik, Red Avenue, Direct Drive — HK IPO Note",
      "Written 22 Sep 2026  ·  Prices as of the 21 Sep close, CNY/HKD 1.1713  ·  "
      "All four book 21–24 Sep, price Fri 25 Sep, list Tue 29 Sep")

para(d, "Four deals on one timetable, HK$14bn+ of paper pricing on the same Friday, into a tape where "
        "Transwarp just closed its first day −9% after pricing at the bottom of its range. Three are A+H deals sold as '40–50% off "
        "the A'; one is an 18C robot name at a fixed price. Snapshot first, then each name.")

table(d,
      ["", "Kinwong 3228", "RoboTechnik 3757", "Red Avenue 9607", "Direct Drive 6731"],
      [
          ["Price", "≤ HK$69.88 (max only)", "≤ HK$436 (max only)", "HK$39–44", "HK$21.60 fixed"],
          ["Raise", "HK$5.10bn", "HK$5.18bn (+15% upsize option)", "HK$2.66–3.00bn", "HK$1.08bn"],
          ["Cap at the H price", "HK$75.1bn", "HK$78.3bn", "HK$26.7–30.1bn", "HK$8.0bn"],
          ["H line, % of company", "6.8%", "6.6%", "10.0%", "13.5% (rest converts to H)"],
          ["Cornerstones", "US$310m · 47.7%", "US$232m · 35.2%", "US$127m · 33–37%", "HK$472m · 43.5%"],
          ["Greenshoe", "none", "15%", "none, no stabilisation", "15%"],
          ["Day-one margin", "HK$0.99bn · 1.9x", "HK$1.18bn · 2.3x", "HK$0.42bn · 1.4x", "HK$0.35bn · 6.5x"],
          ["H vs A at the top", "−46%", "−40%", "−48% to −54%", "H only"],
          ["What you pay", "53x ann. 1H26 earnings, profit falling",
           "51x TTM sales; 1H26 profit RMB6m", "38–43x headline; 84–96x ex the tyre stakes",
           "20x TTM sales, 90x gross profit"],
          ["Call", "Pass — own VGT H / Delton H", "Pass — Innolight H or ASMPT instead",
           "Avoid, debut included", "Flip only — sell the pop"],
      ],
      col_widths=[3.0, 3.5, 3.6, 3.5, 3.4], font_size=8.5)

# ----------------------------------------------------------------------------------------------
h1(d, "1. Kinwong 景旺电子 (3228 HK) — the world's #1 auto-PCB maker, sold with an AI label")
para(d, "A+H off Shanghai (603228). Maximum price only, HK$69.88 — no range; the final is struck Friday "
        "off the A-share close and can only come lower. Raising up to HK$5.10bn at a HK$75bn cap; the H "
        "line is just 6.8% of the company. CITIC, BofA and Guolian sponsoring, HK$7,058 a lot. There is "
        "no greenshoe, so no stabilising bid on the debut.")
h2(d, "The deal mechanics")
bullets(d, [
    "Cornerstones total US$310m ≈ 47.7% of the deal, fourteen names, six-month lock. Read the list: "
    "Innolight US$50m, Han's CNC US$50m (through HK Mason), CIG US$30m, Kingboard US$5m. That is US$135m "
    "from this year's other A+H issuers — a customer-side optics name, Kinwong's own equipment supplier and "
    "its own laminate supplier. CPE (US$50m) is the biggest pure financial; the long-onlys you'd want to "
    "see — JPMAM, Barings — wrote US$5m tickets.",
    "Retail is cold: day-one margin HK$0.99bn, 1.9x the public tranche. The PCB shelf it is joining "
    "closed at 431x (VGT) and 1,071x (Delton). Net of the lock, real float is about HK$2.7bn.",
])
h2(d, "What it is — and where the AI claim stops")
bullets(d, [
    "A real, big business: #11 PCB maker globally, #1 in automotive PCBs with 10.6% share (CIC). FY25 "
    "revenue RMB15.3bn, +21%. Auto is 45% of revenue, smart devices 24%, telecom and data 10%.",
    "But profit is going backwards. 1H26 revenue +21%, net profit −6.5% to RMB611m; the first four months "
    "were −25%. Gross margin has fallen every period — 23.2% → 21.6% → 20.2% — and it's the core that "
    "hurts: automotive gross margin went from 31.1% to 13.8% in 4M26, with ASPs flat at ~RMB1,030/sqm for "
    "four years while copper and laminate rose. That is what no pricing power looks like.",
    "The line the roadshow won't lead with: the best-margin item in the P&L is scrap. Selling "
    "copper-bearing production waste is 8% of revenue at a 94% gross margin — about 40% of group gross "
    "profit in 4M26. Strip it out and the PCB business earns a 12.3% gross margin, down from 19.6% in 2023.",
    "The AI story is real but small. AI-related PCB was RMB268m, 5.0% of 4M26 revenue (1.3% in FY25), and "
    "the flagship AI-server win is 'expect to supply' — certified, customer unnamed, not yet revenue. HDI, "
    "the AI product, saw its margin roll from 20.8% to 12.2% on low initial yields.",
    "The balance sheet is doing the lifting: borrowings went from RMB0.66bn to RMB6.1bn in nineteen "
    "months, capex now exceeds operating cash flow, and 15% of this raise repays banks — while RMB542m "
    "of dividends were declared in the first four months of the year.",
])
h2(d, "Valuation — foreign and A/H shelves together")
table(d,
      ["", "P/E TTM", "P/E ann. 1H26", "P/S", "1H26 profit", "GM", "Note"],
      [
          ["Kinwong H @ HK$69.88 max", "54x", "53x", "3.8x", "−7%", "20%", "12% ex-scrap"],
          ["Kinwong A 603228", "93x", "92x", "6.6x", "−7%", "20%", "the anchor; H is −46%"],
          ["VGT H 2476", "38x", "33x", "8.6x", "+33%", "33%", "H −22% to A"],
          ["Delton H 1989", "34x", "26x", "6.7x", "+94%", "39%", "H −44% to A"],
          ["Kingboard Laminates 1888", "40x", "31x", "6.8x", "+209%", "31%", "its CCL supplier"],
          ["Kingboard 148", "16x", "14x", "1.4x", "+5%", "27%", ""],
          ["WUS A 002463", "48x", "42x", "10.0x", "+74%", "39%", ""],
          ["Shennan A 002916", "65x", "60x", "9.4x", "+66%", "31%", ""],
          ["Shengyi Electronics A 688183", "51x", "47x", "9.0x", "+109%", "34%", ""],
          ["Avary A 002938", "55x", "82x", "5.2x", "+4%", "24%", ""],
          ["Olympic / Suntak / Aoshikang A (auto PCB)", "87 / 116 / 138x", "—", "5.6 / 3.5 / 4.5x",
           "−78 / −31 / −58%", "14–20%", "the honest comp set"],
          ["TTM Technologies (US)", "55x", "—", "3.9x", "rev +37%", "21%", ""],
      ],
      col_widths=[5.4, 2.0, 2.0, 1.8, 2.0, 1.2, 2.8], font_size=8)
para(d, "On the A-share anchor this looks like a gift — half the price of the A. But the A is the leg that's "
        "wrong: 93x for falling earnings, in a market where auto-PCB names with profits down 30–80% trade "
        "at 90–140x because the whole sector wears the AI label. Hong Kong doesn't price PCBs that way. It "
        "will sell you VGT — the GPU-chain leader, 33% gross margin, profit +33% — at 33x annualised "
        "earnings, and Delton — server boards, 39% margin, profit +94% — at 26x. Kinwong asks 53x for a 20% "
        "margin and shrinking profit. The leader is cheaper than the laggard, again. Put VGT-H's 33x on "
        "Kinwong's annualised RMB1.2bn and you get about HK$43 a share; Delton's 26x gives HK$34; pay a "
        "generous 40x for the AI option and it's HK$52. The cap is HK$69.88.")
bullets(d, [("Verdict: ", "pass anywhere near the cap. If you want HK PCB exposure, own VGT H or Delton H — "
             "cheaper, faster, better margin. No shoe, a 1.9x retail book and 48% locked means the debut "
             "hangs on the A holding up into Friday's pricing, and the max-price structure means it can "
             "only surprise cheaper. I'd get interested below ~HK$50, and properly interested when the auto "
             "margin stops falling — the 3Q print in late October is the tell.")])

# ----------------------------------------------------------------------------------------------
h1(d, "2. RoboTechnik 罗博特科 (3757 HK) — a collapsing solar-equipment maker that bought the CPO shovel")
para(d, "A+H off ChiNext (300757). Maximum price only, HK$436, struck Friday off the A close. Raising "
        "HK$5.18bn at a HK$78bn cap; H line 6.6% of the company. Huatai, Citi and Orient sponsoring; 15% "
        "greenshoe with Huatai stabilising — plus a 15% offer-size adjustment option, so strong demand gets "
        "met with more stock. HK$22,020 a lot, which keeps retail out: day-one margin 2.3x.")
h2(d, "The deal mechanics")
bullets(d, [
    "Cornerstones US$232m ≈ 35.2% of the deal, sixteen names. Temasek leads with US$45m — a real name, "
    "though already a shareholder. After that it thins fast: a commodity trader's vehicle US$40m, IvyRock "
    "US$30m, an individual US$30m, a company incorporated this March US$10m, and one fund that may pay "
    "for its ticket with prime-broker leverage.",
    "CIG is in for US$10m — and the prospectus says CIG is a customer of the silicon-photonics equipment "
    "business. Same CIG that is a cornerstone in Kinwong this week. The optics chain is anchoring its own "
    "equipment vendor.",
])
h2(d, "What you need to know")
bullets(d, [
    "The legacy business is going away. PV cell automation was 95% of revenue in 2023; PV revenue went "
    "from RMB1.49bn in 2023 to RMB433m in 2025 and RMB83m in 1H26, units from 1,932 a year to 110, and management's own "
    "assumption is that PV loses money through 2026. Receivables doubled while that revenue collapsed; "
    "the cash conversion cycle has stretched from 156 to 580 days.",
    "What you're buying is ficonTEC, the German silicon-photonics assembly-and-test house consolidated in "
    "May 2025. It's genuinely good: #1 globally (CIC) with Broadcom running its systems in volume, a "
    "RMB2.0bn backlog at June — 4.5x last year's SiPh revenue — and a joint CPO development with an unnamed "
    "'world-leading AI infrastructure company'. SiPh revenue was RMB488m in 1H26, of which RMB358m landed "
    "in May–June alone.",
    "Now size the claims. #1 means 20.5% of a market that was RMB3.0bn in 2025, with #2 at 19.7%. Group "
    "net profit in 1H26 was RMB6m on RMB608m of revenue; FY25 was a RMB45m loss; ficonTEC itself lost "
    "RMB47m in the first four months before the May–June shipments. Goodwill is RMB1.66bn — 74% of net "
    "assets, and RMB666m higher under IFRS than in the A-share books for the same deal.",
    "Governance: CSRC and SZSE warning letters on file, including one for not disclosing repurchase and "
    "return-guarantee arrangements in the ficonTEC acquisition itself. And for scale: the A trades at "
    "RMB621; the placement that part-funded that acquisition was done at RMB124.99.",
])
h2(d, "Valuation — foreign and A/H shelves together")
table(d,
      ["", "P/S TTM", "P/E", "Growth", "GM", "Note"],
      [
          ["RoboTechnik H @ HK$436 max", "51x · 31x on the May–Jun run-rate", "n/m (1H26 NI RMB6m)",
           "1H26 rev +145%", "42%", "H cap HK$78bn"],
          ["RoboTechnik A 300757", "79x", "n/m (FY25 loss)", "", "", "the anchor; H is −40%"],
          ["ASMPT 522", "4.9x", "62x", "rev +42%", "41%", "HK$70bn in total, 10x the revenue"],
          ["CFMEE H 9630", "24.6x", "81x ann.", "NI +98%", "43%", "HK's richest profitable equipment name"],
          ["Han's CNC H 3200", "5.6x", "24x ann.", "NI +263%", "35%", "H −64% to A"],
          ["Wuxi Lead H 0470", "2.5x", "21x ann.", "NI +29%", "32%", "H −27% to A"],
          ["FormFactor", "10.3x", "81x", "rev +32%", "51%", ""],
          ["Onto Innovation", "12.1x", "102x", "rev +35%", "53%", ""],
          ["Camtek", "13.7x", "185x", "rev +8%", "50%", ""],
          ["Aehr Test", "63x", "n/m", "rev +34%", "43%", "the US equivalent of this trade"],
          ["Innolight H 3308 (the customer side)", "19.3x", "46x ann.", "NI +242%", "46%",
           "H trades 13% ABOVE its A"],
          ["CIG H 6166", "7.2x", "61x ann.", "NI +171%", "31%", "cornerstone and customer"],
          ["Coherent / Lumentum", "8.8x / 28x", "78x / n/m", "rev +34% / +109%", "39% / 47%", ""],
          ["PV equipment A: Jiejia / Autowell", "1.9x / 2.4x", "16x / 32x", "rev −67% / −20%", "30–35%",
           "what the legacy side is worth"],
      ],
      col_widths=[5.2, 3.2, 2.5, 2.4, 1.1, 2.8], font_size=8)
para(d, "Give it full credit first. Annualise the May–June shipments and SiPh is a ~RMB2.1bn business, and "
        "the backlog says that's deliverable. Even on that number the H cap is 31x sales. The shovel-sellers "
        "the market actually respects — FormFactor, Onto, Camtek — get 10–14x. Hong Kong's richest "
        "profitable equipment name, CFMEE H, gets 25x with profit doubling. ASMPT, which also sells "
        "photonics and CPO bonding tools, is worth HK$70bn in total — less than RoboTechnik's H cap — on "
        "ten times the revenue. And the shovel now costs more than the mine: Innolight H, 46% margin, "
        "profit +242%, is 19x sales and 46x earnings. Put the US shelf's 12x on the run-rate and you get "
        "~HK$170 a share; CFMEE-H's 25x gives ~HK$350, and that needs the run-rate to hold, HK's richest "
        "multiple, and zero drag from PV. The cap is HK$436. Said another way: 50x earnings at the cap "
        "needs RMB1.3bn of net profit. It made RMB6m last half, in a market CIC sizes at RMB3bn last year "
        "and RMB27bn in 2030. The cap already pays for 2030 going right.")
bullets(d, [("Verdict: ", "pass as an investment anywhere near HK$436. The debut is a coin-flip on the "
             "A-share and on CPO sentiment — it's the hottest label of the four, Temasek anchors and Huatai "
             "has a shoe to defend with, but the upsize option caps the scarcity and a HK$22k lot keeps "
             "retail out. If you want CPO in HK, Innolight H is the cleaner own; if you want the equipment "
             "angle, ASMPT at 5x sales. Revisit on proof the backlog converts at margin — 3Q results in "
             "late October are the first real test.")])

# ----------------------------------------------------------------------------------------------
h1(d, "3. Red Avenue 彤程新材 (9607 HK) — a tyre-chemicals company with a photoresist label")
para(d, "A+H off Shanghai (603650). Range HK$39–44, raising HK$2.66–3.00bn at a HK$26.7–30.1bn cap; H "
        "line ~10% of the company. Haitong International sole sponsor, HK$4,444 a lot. No greenshoe and no "
        "stabilising manager at all — the prospectus itself flags that as a risk.")
h2(d, "The deal mechanics")
bullets(d, [
    "Cornerstones US$127m ≈ 33–37% of the deal, and it's a friends-and-family book: a family office "
    "(Goldshore, US$45m), Full Truck Alliance — a freight app — US$20m, CITIC Bank's HK arm US$18m, then "
    "three individuals' money — two of them existing shareholders, one the former chairman of its own "
    "resin subsidiary — and Prinx Chengshan, which is at once Red Avenue's "
    "customer and its associate. No semiconductor strategic, no global long-only. For a 'China's #1 "
    "photoresist' pitch, that absence is the signal.",
    "Coldest book of the four: day-one margin HK$420m, 1.4x the public tranche.",
])
h2(d, "What you need to know")
bullets(d, [
    "The label is semiconductor photoresist — #1 among local suppliers in China (F&S), KrF in production, "
    "ArF at customer-development stage, no EUV. True, and strategically valuable. Now size it: "
    "semiconductor materials were RMB428m in FY25, 12.5% of revenue. '#1 local' is a 5.8% share of China "
    "and 1.8% of the world (#9); all five local suppliers together hold 10.5%. The photoresist plant ran "
    "at 42% utilisation in 1H26, the solvents line at 23%.",
    "And the growth inside that line is lower-grade than it looks: semiconductor-materials ASP fell from "
    "RMB595k to RMB225k a tonne in a year. The volume is high-purity solvent, not resist.",
    "What pays the bills is tyres. Rubber additives — global #1 in phenolic tackifier resins, 41% share — "
    "are 62–68% of revenue, with resin prices down every period (RMB15.2k → 13.4k/t) and segment margin "
    "down to 22.6%. And 53–66% of net profit isn't operating at all: it's the equity-accounted share of "
    "two tyre makers, Zhongce Rubber (8.0%) and Prinx Chengshan (5.1%). That income is untaxed, which is "
    "why the group tax rate is ~4% and the net margin flatters.",
    "Cash says the same. Operating cash flow was RMB37m in 1H26 against RMB283m of capex and RMB307m of "
    "dividends declared; free cash flow negative in every period; borrowings ~RMB4.0bn, gearing 88%. "
    "10% of the raise repays banks and 20% is for M&A with no target.",
])
h2(d, "Valuation — foreign and A/H shelves together")
table(d,
      ["", "P/E TTM", "P/S", "1H26 profit", "GM", "Note"],
      [
          ["Red Avenue H @ HK$39–44", "38–43x · 84–96x ex tyre stakes", "5.8–6.6x", "+11%",
           "23%", "electronic materials GM 28%"],
          ["Red Avenue A 603650", "74x", "11.3x", "+11%", "23%", "the anchor; H is −48 to −54%"],
          ["Anji Micro A 688019", "57x", "18.4x", "+42%", "56%", "CMP slurry — the quality bar"],
          ["Dinglong A 300054", "73x", "17.9x", "+70%", "59%", ""],
          ["Shanghai Sinyang A 300236", "74x", "12.6x", "+60%", "42%", ""],
          ["Nata Opto A 300346", "105x", "14.1x", "+23%", "41%", "ArF resist"],
          ["Yoke A 002409", "63x", "7.4x", "+7%", "30%", ""],
          ["Qnity (ex-DuPont; global top-3 resist)", "44x", "4.9x", "rev +22%", "47%", ""],
          ["Entegris", "72x", "6.6x", "rev +11%", "48%", ""],
          ["Shengquan A 605589 (phenolic resin)", "36x", "3.0x", "−11%", "25%", "the tyre-chem multiple"],
          ["Yanggu Huatai A 300121 (rubber additives)", "34x", "1.2x", "−53%", "19%", ""],
          ["Zhongce Rubber / Prinx Chengshan", "9x / 4x", "—", "—", "—", "what the market pays for the stakes"],
          ["HK's price for A+H materials paper", "—", "—", "—", "—",
           "Woer −55% · Befar −56% · Senior −58% · SICC −45% to A"],
      ],
      col_widths=[5.4, 3.8, 1.6, 1.8, 1.1, 3.5], font_size=8)
para(d, "Start with what Hong Kong already pays for this kind of paper: A+H materials names sit 45–58% below "
        "their A-shares. The range, at −48% to −54%, is simply the going rate — there's no discount on "
        "offer. Then look through the label. Back out the two tyre stakes at market, ~RMB3.4bn — and note "
        "the market values those earnings at 9x and 4x, not 40x — and you're paying RMB19–22bn for an "
        "operating business earning ~RMB230m: 84–96x. For that multiple the A-share market gives you Anji or "
        "Dinglong — pure semi-materials, 56–59% gross margins, profits +40–70%. Red Avenue's operating "
        "business is two-thirds tyre resin at a 23% margin, which trades at ~35x on a good day. Blend it "
        "honestly — 35x for rubber, 65x for electronic materials, weighted by gross profit — and the core "
        "is worth ~45x × RMB230m ≈ RMB10.5bn. Add the stakes and it's ~RMB14bn, about HK$24 a share. The "
        "range is HK$39–44.")
bullets(d, [("Verdict: ", "avoid, debut included. Coldest book, no shoe, no stabilisation, a "
             "friends-and-family cornerstone list, and a range set exactly at the going A/H discount. The "
             "A-share at 74x is the inflated leg. If you want China semi-materials it's an A-share trade "
             "(Anji, Dinglong); in HK there's no clean way and this isn't one. Look again near HK$30, or "
             "when semiconductor materials are a third of revenue rather than an eighth.")])

# ----------------------------------------------------------------------------------------------
h1(d, "4. Direct Drive Tech 本末科技 (6731 HK) — a robot-vacuum motor supplier in an 18C wrapper")
para(d, "Dongguan, H-only, Chapter 18C commercial company. Fixed HK$21.60, raising HK$1.08bn at a HK$8.0bn "
        "cap. CITIC Securities sole sponsor, 15% greenshoe. HK$2,182 a lot. The Hong Kong public tranche is "
        "just 5% — HK$54m.")
h2(d, "The deal mechanics")
bullets(d, [
    "Cornerstones HK$472m ≈ 43.5% of the deal, and it's all state money: Dongguan SASAC's tech fund "
    "(HK$299m) and a Beijing SASAC / E-Town vehicle (HK$173m) that is a connected party of existing "
    "shareholders — needed a waiver, doesn't count as float. No customer, no strategic, no long-only.",
    "Hottest book of the four: day-one margin HK$351m, 6.5x that tiny public tranche. Fixed price, small "
    "deal, robot label, a shoe behind it — the recipe this shelf pops on.",
    "The up-round already happened. Series C closed in January at RMB3.2bn post-money (RMB9.97 a share); "
    "the IPO is 2.2x that, nine months later. Series C is locked twelve months; three early funds holding "
    "12% of the company come free at six.",
])
h2(d, "What you need to know")
bullets(d, [
    "What it actually sells: direct-drive motor modules at ~RMB29 apiece, 8.5m units last year, "
    "overwhelmingly into robot vacuums — 82–88% of revenue. Revenue went RMB18m → 80m → 282m; 1H26 was "
    "+40% to RMB200m. Fast, but the triple-digit phase is over.",
    "'#1 with 61% share' is of a niche that is 3.9% of China's consumer-robot actuator market. In the "
    "actual market it's #8 with 2.4% (F&S).",
    "One customer is 54% of 1H26 sales (43% in FY25) — unnamed, described as a private, Suzhou-based "
    "top-ten global consumer-robot brand, which reads like Dreame (my inference, not disclosed). Other top "
    "customers' descriptions fit Ecovacs and Roborock. Top five are 81%. Overseas revenue is 1.7%.",
    "Margins are component-grade: gross margin 20.7%, and the consumer module line earns 17%. The "
    "high-margin lines the roadshow will talk about — wheel-legged robots (56% margin, 230 units in 1H26) "
    "and humanoid joint modules (RMB3.3m, 1.7% of revenue, ASP down from RMB763 to RMB257) — are 7% of "
    "revenue combined. It doesn't make a humanoid; it sells a few joints to companies that do.",
    "Still losing money where it counts: adjusted net loss widened to RMB27.5m in 1H26 from RMB19.6m "
    "despite +40% revenue; operating cash flow negative in every period, burn doubled to RMB13m a month. "
    "Management guides to a 2026 loss, and July shipments ran at about half the 1H monthly rate.",
])
h2(d, "Valuation — the HK robot shelf")
table(d,
      ["", "P/S TTM", "P / gross profit", "Growth", "GM", "vs IPO price"],
      [
          ["Direct Drive @ HK$21.60", "20.1x", "90x", "+40%", "21%", "—"],
          ["LDRobot 1236 (sensors into the same vacuum OEMs)", "8.6x", "31x", "+35%", "29%",
           "+1% (was +128% day one)"],
          ["Zhaowei H 2692 (micro-drives; 41x P/E)", "5.1x", "16x", "+4%", "31%", "−46%"],
          ["Onerobotics 6600", "8.2x", "16x", "+32%", "50%", "−41%"],
          ["Dobot 2432", "12.1x", "26x", "+107%", "47%", "—"],
          ["SEER 6106", "12.5x", "26x", "+67%", "47%", "−28%"],
          ["UBTech 9880", "13.0x", "31x", "+104%", "45%", "—"],
          ["Mech-Mind 9615", "19.8x", "30x", "+73%", "65%", "−21%"],
          ["Rokae 3752", "14.3x", "55x", "+136%", "30%", "+26%"],
          ["Geek+ 2590", "2.6x", "7x", "+25%", "36%", "−51%"],
          ["Leader Drive A 688017 (the A-share 'robot joint' anchor)", "79x", "—", "+39%", "32%", "—"],
          ["The customers: Roborock / Ecovacs", "1.5x / 1.4x", "P/E 18x / 14x", "+28% / +19%", "43% / 49%",
           "—"],
      ],
      col_widths=[6.4, 1.8, 2.3, 1.8, 1.1, 3.8], font_size=8)
para(d, "Margins differ too much across this shelf for P/S to be fair, so use price to gross profit. Hong "
        "Kong pays 16–31x gross profit for its robot names — including the ones growing +100% on 45%+ "
        "margins (UBTech 31x, Dobot 26x). Direct Drive asks 90x, for +40% growth and a 21% margin. The "
        "cleanest comp is LDRobot: same customers, same end-product, similar growth, better margin — 31x "
        "gross profit, 8.6x sales. Put LDRobot's multiples on Direct Drive and you get HK$2.7–3.4bn, HK$7–9 "
        "a share — which is about where Series C priced it in January (HK$11.7 equivalent). And remember who "
        "the customers are: Roborock and Ecovacs trade at 14–18x earnings and 1.4x sales. A RMB29 motor "
        "supplier doesn't durably hold 20x sales when the brands it sells to hold 1.4x.")
bullets(d, [("Verdict: ", "a flip, not a holding. It's the one deal of the four with a real debut set-up — "
             "fixed price, a HK$54m public tranche already 6.5x covered on day one, 44% locked, a shoe "
             "behind it — and this shelf's small deals have opened +76% to +154% this year (RobotPhoenix, "
             "LDRobot, Excelland). Play it for that if you play it, and sell the pop: LDRobot opened +128% "
             "and is now +1%, and the bigger robot deals — Mech-Mind −21%, SEER −28%, Onerobotics −41% — "
             "show where the shelf settles once the float turns over. Fundamental value is HK$7–12.")])

# ----------------------------------------------------------------------------------------------
h1(d, "5. Bottom line — one pattern across all four")
bullets(d, [
    "All three A+H deals sell a discount to an A-share that is itself the inflated leg — 93x falling "
    "earnings, 79x sales, 74x with half the profit coming from tyre stakes. Hong Kong already has its own "
    "shelf for each (VGT and Delton; ASMPT and Innolight; the −55% materials discount) and prices to that, "
    "not to the mainland. Same conclusion as the last two notes.",
    "Watch the cornerstone club. This year's A+H issuers are now each other's anchors — Innolight, Han's "
    "CNC, CIG and Kingboard in Kinwong, CIG again in RoboTechnik, Prinx Chengshan in Red Avenue. That is "
    "issuer cash recycling through the supply chain, not price discovery.",
    "Where I'd get interested: Kinwong below ~HK$50; RoboTechnik HK$170–350; Red Avenue near HK$30 "
    "(fair ~HK$24); Direct Drive is a debut flip only — fundamental value HK$7–12. In the meantime the "
    "better owns are already listed: VGT H, Delton H, Innolight H, ASMPT.",
])
h2(d, "Dates")
bullets(d, [
    "24 Sep (noon) — all four books close · 25 Sep — all four price; Kinwong and RoboTechnik are struck off "
    "that week's A-share closes · 28 Sep — allotment results, grey market · 29 Sep — all four list · late "
    "Oct — 3Q prints for Kinwong, RoboTechnik and Red Avenue (A-share calendar).",
])
para(d, "Sources: the four prospectuses dated 21 Sep 2026 (HKEXnews); A / H / US prices and reported "
        "financials from Tencent and Eastmoney feeds at the 21 Sep close; day-one margin from the Zhitong "
        "broker tally. H multiples for A+H names are the A-share multiple scaled by the H/A price ratio.",
     size=8.5, italic=True)

d.save(OUT)
print("saved", OUT)
