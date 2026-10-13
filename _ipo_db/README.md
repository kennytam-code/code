# HK IPO database and market monitors

The workbook and offline HTML dashboard cover 524 IPO records. IPO Live and A/H monitoring extend to seven years: 714 listings and 68 A/H pairs. The latest deal-data review is dated 12 October 2026; stored market prices are through 2 October 2026.

Use the files in `TO_NOMURA/`:

| File | Purpose |
|---|---|
| `HK_IPO_Database_v1.xlsx` | IPO Live, A/H, Lock-up, Peer Trades, Screener and Database, in that order. |
| `hk_ipo_dashboard.html` | Self-contained charts and filters; about 2.5 MB and no external requests. |
| `hk_ipo_dashboard.zip` | Compressed transfer copy; extract before opening. |
| `hk_ipo.py` | Standalone build/update script with embedded data and source modules. |
| `READ_ME_FIRST.txt` | Desk controls and update instructions. |

IPO Live shows Bloomberg prices and change versus the previous close, with broad-sector and selected-sector/subsector averages. Screener freezes the first two columns. Current P/E and P/S in Excel use the supplied BQL TTM expressions; selected A/H companies also have NTM and FY2027 estimates. Historical IPO valuations remain historical. Live requests require a Bloomberg terminal. Missing replies show `Unavailable`.

A/H opens in Stored mode; E4 selects Bloomberg. HTML uses the Screener's chart format, with listing-to-snapshot and three-month views. The CSI 300 panel compares A-share and market performance on the same observed dates around H listing. Sixty-five pairs have pre-IPO A-share history; three listed their A shares later. Missing quotes and mismatched bonus entitlements remain gaps.

Lock-up contains 396 cornerstone schedules for 386 companies, IPO dates, filed source links, and price returns over 30 HK trading sessions before and after expiry. Charts support individual stocks, selected comparisons and date-filtered cohorts. Unconfirmed dates and incomplete windows remain unavailable.

Peer Trades selects one named product peer pair; both securities populate automatically. Source and horizon controls remain, including custom dates. The roster covers 35 pairs / 66 stocks, including established Hong Kong companies outside the IPO database, and shows material business-mix differences. Spread is the difference between the two price returns, in percentage points, from the first common observed session.

## Conventions

Money is HK$ millions unless labelled otherwise. Positive A/H premium means A shares trade above H: A price × CNY/HKD ÷ H price − 1. Premium changes are percentage points. Return windows labelled 1w/1m/3m use 5/21/63 traded sessions after debut. Price performance excludes cash dividends.

## Maintenance

Read `MAINTENANCE.md` first. It records source conventions, corrections, validation limits and the memory-bounded build workflow. Audit evidence is retained under `data/batches/`.

```sh
python ipo.py status
python ipo.py build
python ipo.py check
```

Validation covers saved formula logic, data parity, native workbook structure and offline browser interactions. Bloomberg response tests use fixtures; actual add-in execution must be checked on a terminal. Stored mode avoids unnecessary history requests. Do one heavy operation at a time and avoid opening the full workbook repeatedly for previews.
