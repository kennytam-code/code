# ADR statistical arbitrage research

Three-page trader's sheet, researched as of **6 October 2026**. Statistical arbitrage only: enter and close each leg independently, with no ADR conversion.

- [Word sheet](../HK_ADR_Strategies_and_Backtest_Research.docx)
- [Readable copy](research/HK_ADR_Strategies_and_Backtest_Research.md)
- [Source links and methodology](research/sources.json)
- [US daily liquidity summary](data/us_liquidity_summary.csv)
- [Taiwan futures activity during US trading hours](data/taiwan_us_window_liquidity.json)
- [Additional exchange measurements](data/exchange_liquidity_summary.json)

The sheet compares HK ADR baskets against HSTECH and KWEB, exact-company Taiwan futures, TOPIX and Japan night cash, Korean futures and Nextrade overlap, and Australian SPI and commodity hedges. It includes named stocks, measured activity, trading windows, hedge sizing and execution conditions.

## What was measured

US share activity: mean daily closing price multiplied by reported share volume for 20 completed US sessions, 4 September–2 October 2026. ChartExchange is the secondary data provider. This is a turnover proxy, not VWAP turnover or evidence of premarket, postmarket, overnight ATS depth or stock borrow.

Taiwan: five available exchange trade files representing US sessions 24, 29 and 30 September and 1–2 October. These are not five consecutive US trading days. October 2026 contracts are measured during 21:30–04:00 HK, with zero-trade five-minute intervals retained. Outright volume is the exchange's `Volume(Buy+Sell)` divided by two. Calendar spreads are excluded from the US-window measures; selected spread-leg volume is divided by four for separate nightly reconciliation. Block activity may be absent. Different contract sizes make raw lot counts unsuitable for direct capacity comparisons.

HK and Australia: exchange daily/night reports. Japan: September exchange and PTS statistics. Taiwan bid/ask figures are one terminal night-report snapshot, not an average spread or a quote that can currently be filled. Dates and primary links accompany the measurements.

## Reproduce the liquidity audits

Python 3 with `lxml` is required for US HTML parsing. The Taiwan audit uses only the standard library.

```sh
python3 -m pip install -r scripts/requirements.txt
python3 scripts/check_liquidity.py
python3 scripts/audit_taiwan_window.py
```

The scripts cache public source files and write their audit results beside the scripts. Those generated files are ignored by Git. Public HTML can change, and Taiwan trade-file downloads may have limited retention; the committed derived measurements preserve the researched sample. Raw source reports and trade files are not distributed here.

## What remains to establish tradability

No strategy P&L backtest has been run. Daily volume and historical prints do not establish execution capacity. Pre-US and after-hours eligibility, two-sided quotes, depth, borrow, partial fills, fees and venue access remain necessary inputs. Japan's aggregate futures statistics can include both sessions and negotiated trades; September expiry rolls can inflate them. Korean night depth and individual ADR overnight ATS depth remain unmeasured.

The hedge-beta example is illustrative. Estimate weights using simultaneous returns, separate session regimes, FX and futures carry; validate residual behavior and net returns out of sample. An index constituent's weight is not its hedge beta. HSTECH weights shown are an ETF holdings proxy dated 2 October, rather than exact official index weights.

SGX US single-stock-futures removal is sourced to Trading Technologies' operational notice, effective 1 October 2026; an exchange circular was not obtained. References to company matching describe economic exposure, not a fixed zero-premium or executable arbitrage.
