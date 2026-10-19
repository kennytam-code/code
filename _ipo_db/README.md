# HK IPO database

**19 October 2026 chart update; market/pipeline review dated 15 October.** [Download Excel from main](https://github.com/kennytam-code/code/raw/refs/heads/main/HK_IPO_Database_v1.xlsx). Start with [START_HERE.md](START_HERE.md) when maintaining this project. It is the current handover for an analyst or a new AI session; [data/release_state.json](data/release_state.json) records coverage, dates and validation limits. Older MAINTENANCE entries are historical.

Use the files in `TO_NOMURA/`:

| File | Purpose |
|---|---|
| [Download Excel](https://github.com/kennytam-code/code/raw/refs/heads/main/HK_IPO_Database_v1.xlsx) | IPO Live, AH, Peer Trades, Screener, Database and Pipeline. |
| [Download HTML](https://github.com/kennytam-code/code/raw/refs/heads/main/hk_ipo_dashboard.html) | Self-contained offline charts and filters, including Lock-up. |
| `hk_ipo_dashboard.zip` | Compressed transfer copy; extract before opening. |
| `hk_ipo.py` | Standalone updater with embedded data and source modules. |
| `READ_ME_FIRST.txt` | Desk controls and update instructions. |

The Database/Screener contain 526 IPOs, including Transsion 2636. The design pass preserves every existing numeric value and formula. Styling uses Nomura signature-graphic red accents, white space, grey, compact Arial text and useful section colours; generic workbook and HTML footnotes have been removed. Large per-tab titles are removed. Screener uses a compact source/override form and a separate selected-deal panel. Source comments and necessary field/date labels remain. Public Nomura reporting is a visual reference, not an internal corporate template.

IPO Live covers 716 seven-year listings. The 15 October closing snapshot has 701 current quotes (707 saved quotes, including six stale observations). B4 selects Stored/Bloomberg, B5 selects Sector/Subsector, and H34 selects the broad sector for subsector averages. Bloomberg uses LAST_PRICE and PX_YEST_CLOSE. Stale or absent previous closes are excluded from daily averages; an IPO's offer price is not treated as yesterday's close.

AH covers 71 pairs. B4 selects the H or A code and E4 selects Stored/Bloomberg. The selected chart combines premium on the left axis with A-share and CSI 300 returns on the right. J5 links to sector averages at J57. HTML sector/subsector filters restrict all comparison inputs. Stocks, Selected average and Sector averages are separate views, with at most six lines per page. Select all applies to the current scope. Each selected stock has one weight. Genuine missing observations are not invented or smoothed; verified share actions use their own ex dates.

A/H charts use navy for premium, teal for A-share return and an amber dashed line for CSI 300. Both axes are named. The HTML combined chart occupies a full row; the Excel chart sits below the frozen table header. The 19 October changes affect presentation only, preserving all observations, cells, formulas and Bloomberg requests.

Lock-up is HTML-only and historical: 161 source-confirmed events for 158 issuers with completed 30-HK-session endpoints, prices through 2 October 2026. Unconfirmed/future dates and incomplete or unverified price windows are excluded. The 17 October review re-read 259 primary filings, corrected a controller event misclassified as cornerstone (6911), and recovered 198 missing price observations in the visible sample. Six original schedules affected by later extensions are withheld pending holder-specific reconciliation. Interior gaps remain visible. Selected average uses only checked stocks; multiple selected expiries are first averaged within each stock. The sample is selective, not every IPO. Evidence and exclusions are in `data/lockup_review_20261017`.

Peer Trades has 35 named product-peer pairs / 66 stocks, including established shares outside the IPO sample. B3 selects the pair, F3 the source, H3 the horizon and F4/H4 custom dates. Spread is A minus B price return in percentage points, from the first common observed session.

Database BJ/BL and BM:BO contain live TTM P/E/P/S and NTM P/E / FY2027 P/E / FY2027 P/S; Screener BE/BG/BH:BJ mirrors them. TTM fields use scalar Bloomberg fields with the supplied BQL fallback. Extraction identifies the requested field rather than numeric date/period metadata. Historical IPO multiples stay historical. Live Bloomberg responses require a terminal/add-in; local fixtures do not certify them.

Pipeline status was checked on 15 October against official AP/PHIP and new-listing feeds. Slender West Lake 6157 is included with its filed offering terms; Transsion has moved into the listed database. Press-only ideas are separate Watchlist entries. Withdrawn/postponed items remain identifiable and are excluded from the default active HTML view.

Older A/H, peer and lock-up histories retain their individual dates, mostly 2 October. A fresh Live quote or new IPO does not make every series current. Separate audit files distinguish arithmetic checks from source confirmation: 273 financial cells, 119 earlier cornerstone aliases and 67 undated expiry events still require primary-source follow-up.

## Refresh and reproduce

```sh
python ipo.py status
python ipo.py refresh
python ipo.py build
python ipo.py check
```

The standalone updater uses `python hk_ipo.py update` for refresh/build and `build` for stored-data reproduction. Use a clean folder to reproduce the embedded data; existing persistent data is retained. Run one heavy operation at a time, Python capped at 512 MiB and Node at 384 MiB. Full workbooks use the staged native build; visual previews use small projections.

Methods, known issues, source evidence and release checks belong in the repository and audit CSV/JSON, not in extra workbook footnotes. The Notes sheet has been removed; its eleven named scoring inputs are preserved in the existing hidden calculation sheet. Read START_HERE before changing controls or build stages.
