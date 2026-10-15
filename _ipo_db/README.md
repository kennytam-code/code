# HK IPO database

Latest delivery: 15 October 2026. IPO Live has a dated 14 October public closing-quote snapshot. Database, A/H, peer and lock-up histories remain the separately labelled 2 October snapshot.

Use the files in `TO_NOMURA/`:

| File | Purpose |
|---|---|
| `HK_IPO_Database_v1.xlsx` | IPO Live, AH, Peer Trades, Screener and Database. |
| `hk_ipo_dashboard.html` | Self-contained charts and filters; opens offline. |
| `hk_ipo_dashboard.zip` | Compressed transfer copy; extract before opening. |
| `hk_ipo.py` | Standalone updater with embedded data and source modules. |
| `READ_ME_FIRST.txt` | Desk controls and update instructions. |

IPO Live: 715 seven-year listings. B4 selects Stored/Bloomberg; B5 selects Sector/Subsector and H34 selects the broad sector for subsector averages. The stored snapshot contains 706 validated prices. Missing/stale daily quotes are excluded from the averages. Bloomberg uses direct LAST_PRICE and PX_YEST_CLOSE.

AH: 70 pairs. B4 selects an H or A code and E4 selects Stored/Bloomberg. The selected chart combines A/H premium on the left axis with A-share and CSI 300 price returns on the right, using a common actual-date axis. Comparison controls remain below the selected chart. The sector summary at J57 averages IPO/current premium and 7-day/1-month changes, following E4. HTML supports multiple pairs, Select all, Select sector, a Selected average line and optional averages by sector using only the selected stocks, preset horizons and custom dates. Real missing observations stay absent; reviewed capital actions retain their separate ex dates.

Lock-up is HTML-only: 397 cornerstone schedules for 387 issuers, with IPO date, cornerstone percentage, since-IPO return, deal size and 30 HK trading sessions before/after expiry. Select stocks individually or by sector and filter expiry dates. Selected average uses only checked stocks; By sector splits that same selection. Each selected stock has one weight; if several of its expiry dates are checked, their available returns are averaged within that stock first. Day 0 is 0%; unavailable dates/prices remain absent.

Peer Trades: 35 named product-peer pairs / 66 stocks, including established Hong Kong shares outside the IPO database. B3 selects the pair; F3 selects Stored/Bloomberg; H3 selects the horizon; F4/H4 set custom dates. Both securities populate automatically. Spread is A minus B price return in percentage points from their first common observed session. Actual coverage dates are shown.

Database fundamentals BM:BO and Screener BH:BJ contain live NTM P/E, FY2027 P/E and FY2027 P/S. TTM fields use direct Bloomberg fields with the supplied BQL fallback. BQL extraction locates the requested field rather than mistaking numeric date/period metadata for a multiple. Missing replies show `Unavailable`; historical IPO valuations remain historical.

The final workbook opened in Microsoft Excel without a content-repair prompt, and the new sector table was visually checked there. Native package checks cover worksheet order, relationships, retained charts and formula bindings. The new sector formulas are independently recalculated, including missing, zero and negative inputs. Formula fixtures cover negative/zero/missing replies, metadata-bearing BQL responses, all selectors and source bindings. Actual Bloomberg execution still requires the terminal add-in.

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
