# HK ADR statistical arbitrage

Start with BABA, JD, BIDU, TCOM and NTES versus HSTECH during the US session; close both sides before 03:00 HK. A direct local share versus ADR trade is better matched when both books are live. Every position is independently closed; no ADR conversion.

### Ten US ADRs inside HSTECH

| ADR | HK code | US daily $m | HSTECH % | Test priority |
| --- | --- | --- | --- | --- |
| BABA | 9988 | 901 | 8.27 | First basket |
| JD | 9618 | 160 | 5.03 | First basket |
| BIDU | 9888 | 236 | 4.11 | First basket |
| TCOM | 9961 | 174 | 3.32 | First basket |
| NTES | 9999 | 78 | 8.62 | First basket |
| BILI | 9626 | 55 | 1.15 | Add if spreads and borrow pass |
| TME | 1698 | 57 | 0.06 | Test KWEB as well |
| LI | 2015 | 37 | 1.83 | EV sleeve with XPEV and NIO |
| XPEV | 9868 | 72 | 1.87 | EV sleeve with LI and NIO |
| NIO | 9866 | 121 | 0.53 | EV sleeve with LI and XPEV |

The ten names sum to 34.79% of the HSTECH ETF holdings proxy on 2 October; the rest is largely other names. Membership alone does not establish a good hedge. Fit the basket beta and residual risk; compare HTI with KWEB. TME is only 0.06% in this HSTECH proxy versus 2.10% in KWEB.

US daily $m = mean of daily closing price × reported share volume over 20 completed sessions, 4 September–2 October 2026. This estimates turnover; it does not measure premarket, overnight depth or borrow.

Sources: [HSTECH holdings](https://www.globalxetfs.com.hk/funds/hang-seng-tech-etf/) | [KWEB holdings](https://kraneshares.com/etf/kweb/) | [BABA volume](https://chartexchange.com/symbol/nyse-baba/historical/) | [JD volume](https://chartexchange.com/symbol/nasdaq-jd/historical/) | [BIDU volume](https://chartexchange.com/symbol/nasdaq-bidu/historical/) | [TCOM volume](https://chartexchange.com/symbol/nasdaq-tcom/historical/) | [NTES volume](https://chartexchange.com/symbol/nasdaq-ntes/historical/) | [BILI volume](https://chartexchange.com/symbol/nasdaq-bili/historical/) | [TME volume](https://chartexchange.com/symbol/nyse-tme/historical/) | [LI volume](https://chartexchange.com/symbol/nasdaq-li/historical/) | [XPEV volume](https://chartexchange.com/symbol/nyse-xpev/historical/) | [NIO volume](https://chartexchange.com/symbol/nyse-nio/historical/)

### The wider HK linked universe

| Additional lines and average daily US turnover | Hedge to test |
| --- | --- |
| BZ 2076 $133m; BEKE 2423 $94m; ZTO 2057 $64m; HTHT 1179 $60m; YUMC 9987 $55m | KWEB for internet exposure; sector peers for property, logistics, hotels and restaurants. YUMC is a US common share. |
| GDS 9698 $42m; EDU 9901 $37m; KC 3896 $12m | GDS/KC cloud pair; EDU/TAL education pair. Add HTI or KWEB only for residual country beta. |
| PONY 2026 $27m; HSAI 2525 $18m; WRD 0800 $15m | Separate autonomy sleeve. Peer hedge plus residual HTI; recent listings and company news can dominate. |
| QFIN 3660 $16m; ATHM 2518 $11m; MNSO 9896 $8m; WB 9898 $7m; ZH 2390 $2m; TUYA 2391 $1m | Smaller lines need stricter execution tests. TUYA median daily turnover is only $0.49m; its mean is event-inflated. |
| HSBC 0005 $157m; ZLAB 9688 $21m | Bank and biotech hedges respectively. HSTECH is a weak default; same-company local/ADR overlap is preferable. |

OTC watchlist: TCEHY, MPNGY, LNVGY, XIACY and BYDDY. Do not count them as executable basket legs without venue eligibility, two-way quotes and stock borrow. US-only China names such as PDD and FUTU can enter a factor basket without a HK listing.

Sources: [BZ listing](https://ir.zhipin.com/static-files/6d76a2e2-c473-4191-a745-3b64cfcbbb0d) | [BEKE listing](https://www.hkexnews.hk/listedco/listconews/sehk/2026/0519/2026051900692.pdf) | [HTHT listing](https://ir.hworld.com/static-files/ec1a016d-4329-41e0-b3de-7af9e460bfcf) | [HSBC listing](https://www.hsbc.com/investors/shareholder-and-dividend-information/investor-faqs) | [ZLAB listing](https://ir.zailaboratory.com/static-files/a2818321-29a4-4374-b949-31581dd79a04) | [HSAI listing](https://www.hesaitech.com/cn/news/1454) | [PONY listing](https://ir.pony.ai/) | [WRD listing](https://ir.weride.ai/)

# Regional hedges and measured liquidity

### Taiwan company futures are usable only above their costs

US daily turnover: TSM $4.47bn, UMC $262m, ASE ADR ASX $295m, CHT $12m. TSMC CD/QF and UMC CC trade 17:25–05:00 HK; ASE OZ and Chunghwa DL are day-only. CD/CC represent 2,000 shares, QF 100. For 1,000 TSM ADS, hedge 5,000 local shares with 2 CD + 10 QF; hedge TWD separately.

| October contract | Mean US window lots | Median lots per 5 min | No trades in 5 min |
| --- | --- | --- | --- |
| TSMC CD | 955 | 2 | 33% |
| TSMC mini QF | 3,468 | 10 | 14% |
| UMC CC | 3,068 | 9 | 20% |
| TAIEX TX | 15,999 | 131.5 | 0% |
| Mini TAIEX MTX | 51,252 | 442.5 | 0% |
| Semiconductor SOF | 3 | 0 | 96% |
| Electronics TE | 34 | 0 | 81% |

Five sampled US sessions: 24, 29, 30 September and 1–2 October; 21:30–04:00 HK. Counts are outright prints, excluding calendar spreads and possible block activity. Lot sizes differ. Night quote snapshot: TSMC about 20bp wide, UMC 31bp; SOF about 421bp and TE 94bp. Prefer CD/QF/CC for company matching, TX/MTX for capacity. Drop SOF/TE from the initial book.

Sources: [Taiwan contracts](https://www.taifex.com.tw/enl/eng2/stockLists) | [Taiwan trade files](https://www.taifex.com.tw/enl/eng3/futPrevious30DaysSalesData) | [Taiwan night quotes](https://www.taifex.com.tw/enl/eng3/futDailyMarketReport?queryType=2&marketCode=1&queryDate=2026%2F10%2F02&commodity_id=specialid2&commodity_id2=CDF) | [TSM share ratio](https://investor.tsmc.com/sites/ir/sec-filings/2025_20F%20Report.pdf)

### Japan use TOPIX first and examine night cash

Mixed ADR basket: test TOPIX before price-weighted Nikkei. JPX lists stock options, but no domestic SSFs. September ADV: TOPIX 134,255 lots, mini 25,961, TOPIX Banks 4,455; combined sessions, possibly negotiated trades. Banks fits MUFG/SMFG/MFG; rolls can inflate volume. US daily turnover: SONY $81m, MUFG $70m, TM $59m, SMFG/MFG about $39m each, HMC $28m.

Japannext local cash trades 16:00–05:00 HK. MUFG 8306 traded JPY5.97bn there in September, about JPY314m per night. Investigate MUFG ADR versus 8306 cash before an index proxy. Require broker PTS access and borrow; ordinary margin trading is day-only. EWJ ($390m daily) is a US-close hedge alternative; company and currency exposure still differ.

Sources: [JPX September volume](https://www.jpx.co.jp/english/corporate/news/news-releases/0063/vk0khi000002j3l8-att/reference(oseandtocom).pdf) | [JPX product list](https://www.jpx.co.jp/english/derivatives/products/list/) | [TOPIX Banks terms](https://www.jpx.co.jp/english/derivatives/products/domestic/topix-banks-index-futures/01.html) | [Japan night cash rules](https://www.japannext.co.jp/pub_data/pub_onboarding/JNX_Trading_Rules_Equities_2.02_EN.pdf) | [Japan night cash volume](https://www.japannext.co.jp/pub_data/reports/2026/monthly/Japannext_Monthly_Statistics_2026-09.pdf)

### Korea separate the semiconductor and bank sleeves

SKHY averaged $3.74bn daily US turnover, but its ADR only began in July 2026. SKM $41m, KT $26m, KB $19m, SHG $15m and WF $7m are smaller. Nextrade after-market ends 19:00 HK: test eligible local shares against US premarket from 16:00 summer / 17:00 winter. That overlap needs its own quotes; daily turnover does not validate it.

KRX KOSPI 200/mini trade 17:00–05:00 HK; SSFs and sector futures are absent from its night list. For SKHY test MU/semiconductor peers plus country beta. For KB/SHG/WF use bank peers first. EWY ($2.47bn daily) works at US close, with sector and KRW basis. KRX and Nextrade depth at the proposed clock remains unmeasured.

Sources: [KRX night products](https://global.krx.co.kr/contents/GLB/02/0201/0201041004/GLB0201041004.jsp) | [Nextrade hours](https://www.nextrade.co.kr/menu/transactionSys.do) | [SKHY ADR](https://news.skhynix.com/en/skhynix-lists-adrs-on-nasdaq/) | [EWY volume](https://chartexchange.com/symbol/nyse-ewy/historical/)

### Australia standard SPI beats the untraded mini sample

US daily turnover: BHP $234m, RIO $173m, WDS $15m. The 2 October ASX night report shows December SPI AP 22,813 lots and OI 265,928; mini AM showed no trades. Resources AR is day-only; old ASX SSFs were delisted. Test SPI + iron ore + AUD for miners, Brent + AUD for WDS. Same-company London/ADR overlap is preferable where available. RIO ADR represents London plc; ASX Rio Limited is a DLC statistical pair with a persistent premium.

Sources: [SPI night volume](https://www.asx.com.au/data/futures/reports/EODWebMarketSummary261002SFN.htm) | [ASX futures hours](https://www.asx.com.au/markets/market-resources/trading-hours-calendar/index-derivatives.) | [ASX old SSFs](https://www.asx.com.au/markets/market-resources/asx-codes-and-descriptors/asx-24-commodity-codes) | [Rio London futures](https://www.eurex.com/ex-en/markets/equ/fut/Rio-Tinto-3090504)

# Trade windows sizing and execution rules

All times are HK, on normal trading days. Summer/winter below means US daylight-saving status. Use venue calendars for holidays, expiry and the weeks when Australian and US clock changes differ.

| Entry idea | Orders and actual exit |
| --- | --- |
| US open ADR basket versus HTI | After the first 5–15 minutes: buy cheap ADR basket / sell beta-sized HTI, or reverse. Use HK closing values updated by futures and FX as a signal anchor. Close both before 02:50; HTI stops at 03:00. |
| HK before close versus US overnight ATS | Summer: scan 15:30–15:45. Winter: 15:30–15:55. Buy cheaper local line / short equivalent ADR shares, or reverse. Close both independently during a later common trading window. Eligibility, borrow and ATS depth must pass. |
| HK close local basket versus HTI | Buy local / short HTI, or reverse, then exit both during the next HK cash session. This forecasts convergence and retains company risk. Selling ADRs at US open while covering HTI leaves a local/ADR pair outstanding. |
| US close or after-hours | HTI is already shut. Trade ADR versus KWEB, EWJ, EWY, EWT or sector peers if both quotes and borrow are available. Close both later while both markets trade. OSE/KRX/TAIFEX end at 05:00, coinciding with winter US close; do not wait for that closing print to initiate a futures hedge. |

### Premarket after-hours and overnight are different books

US regular: 21:30–04:00 summer / 22:30–05:00 winter. Premarket starts 16:00 / 17:00. Ordinary after-hours ends 08:00 / 09:00, before HK cash opens at 09:30. IBKR overnight ATS: 08:00–15:50 / 09:00–16:50. Confirm each symbol and short route; broad overnight availability does not prove depth.

Japan/Korea cash opens around 08:00 HK, giving a winter postmarket overlap; Nextrade premarket starts 07:00. Taiwan cash at 09:00 has no meaningful ordinary postmarket overlap. Australia cash opens around 07:00 with Sydney DST / 08:00 otherwise: US postmarket overlap varies from zero to two hours. Japan PTS gives US regular-session overlap directly.

Sources: [US overnight ATS](https://www.interactivebrokers.com/en/trading/us-overnight-trading.php) | [HTI hours](https://www.hkex.com.hk/Products/Listed-Derivatives/Equity-Index/Hang-Seng-TECH-Index-Futures-and-Options/Hang-Seng-TECH-Index-Futures?sc_lang=en) | [Japan night cash rules](https://www.japannext.co.jp/pub_data/pub_onboarding/JNX_Trading_Rules_Equities_2.02_EN.pdf) | [Nextrade hours](https://www.nextrade.co.kr/menu/transactionSys.do) | [ASX futures hours](https://www.asx.com.au/markets/market-resources/trading-hours-calendar/index-derivatives.)

### HK SSFs fail the first capacity screen

5 October all-expiry volume: ALB 96; JDC 25; BIU 319; NTE 13; TRP 20; BLI 0; PEN 25 lots. They are day-only. ALB front month traded only 82 lots, roughly HKD4.3m notional using settlement price. Investigate firm market-maker quotes for a small ADR/SSF pair; do not assume a basket can use these as its default hedge.

HTI October traded 8,054 contracts in the previous after-hours session reported on 5 October, with OI 198,303 after that business day. This supports prioritizing HTI; executable depth in your exact minute is still required. SGX US SSFs were removed effective 1 October per TT’s operational notice. CME’s current SSF card has US semiconductor proxies, not BABA or TSM. CME TOPIX exists; validate quotes before relying on its longer clock.

Sources: [HK SSF volume](https://www.hkex.com.hk/eng/stat/dmstat/dayrpt/stock261005.htm) | [HK SSF terms](https://www.hkex.com.hk/Products/Listed-Derivatives/Single-Stock/Stock-Futures?sc_lang=en) | [HTI volume](https://www.hkex.com.hk/eng/stat/dmstat/dayrpt/htif261005.htm) | [SGX SSF removal notice](https://tradingtechnologies.com/support-updates/sgx-delisting-of-single-stock-futures-hkex-introduction-of-new-contracts-on-partition-3-and-more/) | [CME SSF list](https://www.cmegroup.com/markets/equities/files/single-stock-futures-fact-card.pdf) | [CME TOPIX](https://www.cmegroup.com/articles/faqs/frequently-asked-questions-usd-denominated-topix-futures.html)

### Fit the hedge and reject trades that cannot pay for execution

Index lots = beta × basket value in hedge currency / (futures price × multiplier). Example only: USD1m × 7.80 × assumed beta 1.10 / (HTI 5,000 × HKD50) = 34.3 lots. Fit rolling 60-session simultaneous 15-minute returns separately for HK day, US premarket and US regular; control FX. Compare HTI, HTI plus NQ and KWEB on out-of-sample residual risk after costs.

Use a learned residual mean, not forced zero parity. Require stationary residuals, stable hedge weights, located borrow and two-sided quotes. Backtest actual bid/ask, depth, partial fills, rolls and session gaps. HK cash round trip is about 21.7bp in stamp duty and exchange levies alone. Apply a time stop before either venue closes and a maximum unhedged fill exposure. No strategy P&L backtest has been run.

Sources: [HK cash costs](https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Fees/Securities-%28Hong-Kong%29/Trading/Transaction?sc_lang=en)
