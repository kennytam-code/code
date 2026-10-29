HK IPO desk files — A/H formula fix 29 October 2026; data 28 October

Open HK_IPO_Database_v1.xlsx for the desk workbook; open hk_ipo_dashboard.html
for the offline dashboard. The ZIP contains that same HTML.

527 listed IPOs; 717 stocks in IPO Live; 72 A/H pairs; 21 pipeline rows.
2384 DSBJ is listed. 6157 and 3275 have postponed their offerings.
IPO Live has 702 valid saved quotes, with individual dates. The latest is
28 October. Missing/stale quotes and debut-day reference prices are excluded
from daily averages. This update does not refresh every historical series.

AH: E4 Quotes chooses Stored or Bloomberg. H4 Charts is independent.
For a live table with less history work, use E4 Bloomberg and H4 Stored.
Current prices use BDP LAST_PRICE; a short shared history feeds the changes. G:I show premium changes in percentage
points over 1D, seven calendar days and one calendar month. 1D compares the
current premium with the previous H trading close, using dated A/FX as-of
observations. Seven-day/month reference dates also follow the H quote date.
A first-day IPO has no previous H trading close. Missing history or dates
show a short status instead of a silent blank. Sector means exclude missing.

AH top links: Group averages, IPO price check. The independent price checker
uses M60 for H code; optional M61 for A code and M62 for H IPO price. Numeric
codes only; suffixes are added internally. Known pairs auto-fill. New A codes
need Bloomberg mode for a live quote. It does not issue a history request.
The Screener keeps its own selected-company valuation fields and code lookup.

Premium and mainland returns now occupy aligned upper/lower charts. All
visible charts have consistent fonts, colours and axes; Live bars turn green
or red dynamically. Observed points and genuine gaps are preserved.

Database B2: Selected/All/Off live valuation scope. BBG Verify B2: Off/On.
Stored is the default for daily monitors. Bloomberg mode requires the add-in
and a logged-in entitled terminal. This Mac cannot certify live Bloomberg
replies. Native Excel opened the final file without a repair prompt.

Standalone updater: python hk_ipo.py build reproduces stored data; update
refreshes providers then builds. Keep its persistent data directory. Source
review and handover are in START_HERE.md and data/release_state.json in the
project. A new price does not certify old histories or old filing fields.

GitHub downloads:
Excel: https://github.com/kennytam-code/code/raw/refs/heads/main/HK_IPO_Database_v1.xlsx
HTML: https://github.com/kennytam-code/code/raw/refs/heads/main/hk_ipo_dashboard.html
Publication status: _ipo_db/data/release_state.json in the repository.
