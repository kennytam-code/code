HK IPO desk files — 15 November 2026; A/H refresh and chart update

Open HK_IPO_Database_v1.xlsx for Excel and hk_ipo_dashboard.html for the
offline dashboard. The ZIP contains exactly the same HTML.

527 IPOs; 717 IPO Live stocks; 75 A/H pairs; 35 peer comparisons; 23 pipeline
rows. This release refreshes the existing A/H universe through 13 November.
It does not update every dataset: IPO Live remains 9 November, peer and
historical lock-up prices 2 October, and pipeline status review 3 November
with other AP/PHIP membership from 28 October. Individual dates are retained.

HTML A/H: choose the company and history. A/H prices appear in the upper
panel; premium appears separately below, on the same date interval. Choose
the indexed price view to add CSI 300. The around-listing view includes
pre-listing mainland performance. Genuine missing-data gaps remain.
Comparisons respect sector/subsector filters. Stocks, Selected average and
Sector averages are separate views, with up to six lines per page.

Excel AH E4 controls Quotes; H4 controls Charts. Both default Stored.
Use E4 Bloomberg and leave H4 Stored for live table values without requesting
long chart histories. Company names and A/H codes are shown in the roster.
A-class cap is in CNY millions; H-class cap is in HKD millions. These are
share-class market caps, not issuer-wide caps. Both use scalar Bloomberg
CURRENT_MARKET_CAP_SHARE_CLASS. Stored mode shows a dash for caps.
Actual Bloomberg field responses, units, coverage and latency still need
checking on an entitled terminal. No additional Bloomberg requests were added.

H:I show IPO/current premium; J:L show 1D/7D/1M premium changes in percentage
points. Definitions remain previous H session, seven calendar days and one
calendar month, using the last eligible observed close. Database A premium
now links to AH by H code, so it follows E4 without an extra Bloomberg call.
AH reuses IPO Live H quotes when both quote modes are Bloomberg.

Live price check: M60 accepts the H code alone. The A code resolves from the
AH list, Database or Pipeline; O60 is an optional A-code override and Q60
an H IPO price override. It uses scalar live quotes, independently of E4,
and requests no chart history.

Database B2 defaults All for PE/PS and forward valuations. Screener reuses
those results. Selected and Off remain optional. BBG Verify defaults Off.
BDH output areas remain writable without preallocated multi-cell array locks.
The final workbook opened in native Excel without a repair prompt. This Mac
is view-only and does not have a Bloomberg terminal; live execution is untested.

Standalone updater: python hk_ipo.py build rebuilds saved data; update
refreshes providers before building. Retain its persistent data directory.
The new A/H refresh uses the last completed Hong Kong close independently of
the older IPO-return snapshot. Check reported failures and actual observation
dates before distributing an update. Corporate-action conflicts need review.

Methods, source evidence, checks and handover are in START_HERE.md,
data/release_state.json and data/ah_review_20261115/REVIEW.md in the project.
15 November release downloads on GitHub main:
Excel: https://github.com/kennytam-code/code/raw/refs/heads/main/HK_IPO_Database_v1.xlsx
HTML: https://github.com/kennytam-code/code/raw/refs/heads/main/hk_ipo_dashboard.html
Publication verification is recorded in data/release_state.json.
