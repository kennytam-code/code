# HK IPO desk files

## 國星宇航 / Adaspace IPO — 6 November 2026

**[Download the Word trader briefing — 06935 HK](https://github.com/kennytam-code/code/raw/refs/heads/main/Adaspace_IPO_Trader_Brief_2026-11-06.docx)**

Five pages following the Word template: **good points, risks, AI business potential, earnings and cash quality, H-first peer valuations, cornerstones, offer supply and conditional Southbound catalysts**. The final prospectus corrects the supplied reallocation, cash and margin claims. Forward sales guidance and explicit revenue scenarios are included; unverified forward P/E is left unavailable. **HK/A prices: 5 November close; US: 5 November 12:04 ET intraday.**

[Sources and valuation audit](_ipo_db/research/adaspace_20261106/source_and_valuation_audit.json) · [Price cross-checks](_ipo_db/research/adaspace_20261106/price_crosscheck.json)

## November IPO and lockup brief — 3 November 2026

**[Download the Word briefing — 新荷花 / 芯德 / 登臨 / 宏芯宇 / 2687 / 1333](https://github.com/kennytam-code/code/raw/refs/heads/main/IPO_and_Lockup_Trader_Brief_2026-11-03.docx)**

One page per company with the trading view, good points, risks and H-first peer valuations, including dated FY26E/FY27E P/E where available. Covers cornerstone identities, lockup cohorts, recent shareholder actions, earnings and index calendars, and existing Southbound eligibility. Prices: **2 November 2026 close**; older or unavailable forecasts are explicitly identified.

[Sources and calculation audit](_ipo_db/research/ipo_20261103/source_and_valuation_audit.json) · [Price cross-checks](_ipo_db/research/ipo_20261103/price_crosscheck.json)

## Reviewed hedge finder — 29 October 2026

**[Open the reviewed v130 notebook](PCA_Hedge_Finder_v130.ipynb)** · **[Download notebook](https://github.com/kennytam-code/code/raw/refs/heads/main/PCA_Hedge_Finder_v130.ipynb)** · [Python source](PCA_Hedge_Finder_v130.py)

This reviewed snapshot adds broader BICS/GICS and peer-network search, optional peers of peers and listing-directory checks, 1m/3m/6m downloads, exchange restrictions, shared-history handling, and before/after factor exposures. It also fixes candidate/cache issues and improves the form and report styling. Run the notebook and use a fresh Bloomberg download for the expanded universe.

The existing maintained PCA engine and its release history remain documented separately in [PCA_README.md](PCA_README.md).

## Listed IPO lockup brief

**[Download the Word briefing — 2635 / 3317 / 6600 / 6651](https://github.com/kennytam-code/code/raw/refs/heads/main/Listed_AI_Lockup_Trader_Brief_2026-10-26.docx)**

Six-page trader brief: comparison and key dates first, then one page per stock with fundamentals, risks, shareholder actions and peer valuations including forward P/E. Market snapshot: 26 October 2026.

**[Download the Excel workbook](https://github.com/kennytam-code/code/raw/refs/heads/main/HK_IPO_Database_v1.xlsx)**

| File | Download |
|---|---|
| Excel | [IPO Live, A/H, Peer Trades, Screener and Database](https://github.com/kennytam-code/code/raw/refs/heads/main/HK_IPO_Database_v1.xlsx) |
| HTML dashboard | [Download and open locally](https://github.com/kennytam-code/code/raw/refs/heads/main/hk_ipo_dashboard.html) |
| Compressed HTML | [ZIP for shared-drive transfer](https://github.com/kennytam-code/code/raw/refs/heads/main/_ipo_db/TO_NOMURA/hk_ipo_dashboard.zip) |
| Updater | [Standalone Python updater](https://github.com/kennytam-code/code/raw/refs/heads/main/hk_ipo.py) |

29 October 2026: A/H Bloomberg 1D/7D/1M formula repair, separate Quotes/Charts switches, and shared short-history lookups to reduce repeated calculation. Data remains the 28 October release: 527 listed IPOs, 717 live-monitor stocks and 72 A/H pairs. Native Excel and formula checks passed; Bloomberg terminal execution is not certified.
Market histories retain their displayed snapshot dates. Live Bloomberg responses still require terminal verification.

[Desk instructions](READ_ME_FIRST.txt) · [Maintenance handover](_ipo_db/START_HERE.md) · [Release details](_ipo_db/data/release_state.json)
