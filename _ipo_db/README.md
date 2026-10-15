# HK IPO database

**16 October 2026 delivery; market/pipeline review dated 15 October.** Start with [START_HERE.md](START_HERE.md) when maintaining this project. It is the current handover for an analyst or a new AI session; [data/release_state.json](data/release_state.json) records coverage, dates and validation limits. Older MAINTENANCE entries are historical.

Use the files in `TO_NOMURA/`:

| File | Purpose |
|---|---|
| `HK_IPO_Database_v1.xlsx` | IPO Live, AH, Peer Trades, Screener, Database and Pipeline. |
| `hk_ipo_dashboard.html` | Self-contained offline charts and filters, including Lock-up. |
| `hk_ipo_dashboard.zip` | Compressed transfer copy; extract before opening. |
| `hk_ipo.py` | Standalone updater with embedded data and source modules. |
| `READ_ME_FIRST.txt` | Desk controls and update instructions. |

The Database/Screener contain 526 IPOs, including Transsion 2636. The design pass preserves every existing numeric value and formula. Styling uses Nomura signature-graphic red accents, white space, grey, compact Arial text and useful section colours; generic workbook and HTML footnotes have been removed. Large per-tab titles are removed. Screener uses a compact source/override form and a separate selected-deal panel. Source comments and necessary field/date labels remain. Public Nomura reporting is a visual reference, not an internal corporate template.

IPO Live covers 716 seven-year listings. The 15 October closing snapshot has 701 current quotes (707 saved quotes, including six stale observations). B4 selects Stored/Bloomberg, B5 selects Sector/Subsector, and H34 selects the broad sector for subsector averages. Bloomberg uses LAST_PRICE and PX_YEST_CLOSE. Stale or absent previous closes are excluded from daily averages; an IPO's offer price is not treated as yesterday's close.

AH covers 71 pairs. B4 selects the H or A code and E4 selects Stored/Bloomberg. The selected chart combines premium on the left axis with A-share and CSI 300 returns on the right. J5 links to sector averages at J57. HTML supports Select all, Select sector, selected-stock averages, sector splits and date horizons. Each selected stock has one weight. Genuine missing observations are not invented or smoothed; verified share actions use their own ex dates.

Lock-up is HTML-only: 398 cornerstone schedules for 388 issuers, with IPO date, cornerstone percentage, deal size, since-IPO return and 30 HK trading sessions before/after expiry. Selected average uses only checked stocks. If a stock has several selected expiries, average those observations within the stock first. Future or unconfirmed endpoints remain blank.

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
