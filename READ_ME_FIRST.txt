HK IPO desk files — 10 November 2026; source review and Database presentation

Open HK_IPO_Database_v1.xlsx for the desk workbook; open hk_ipo_dashboard.html
for the offline dashboard. The ZIP contains that same HTML.

527 listed IPOs; 717 stocks in IPO Live; 75 A/H pairs; 23 pipeline rows.
Seven new offerings: 0054, 2065, 2206, 2681, 7672, 9621, 9917.
1821 is an introduction. Terms were checked against HKEX prospectuses.
Pipeline cards open comparisons in Screener; Excel selects peer codes
automatically for the new offerings. These are business comparison sets.
AP/PHIP membership outside these eight remains the 28 October review.
2384 DSBJ is listed. 6157 and 3275 have postponed their offerings.
IPO Live has 702 valid saved quotes, with individual dates. The latest is
9 November. Missing/stale quotes and debut-day reference prices are excluded
from daily averages. This update does not refresh every historical series.

Current review: 32 IPO caps corrected/filled from 34 filed capital records;
clawback outcomes verified for 526 IPOs, with 2550 held blank. Mechanism B
means no mandatory clawback and is shown as B / N/A. No is not the same as N/A.
168 final retail-allocation counts and four listing-day tape gaps recovered;
all 527 Day-1 volume / retail-allocation ratios now have inputs. Missing
financial denominators or unavailable estimates are not replaced with zero.

A/H IPO premium uses A close before the H listing x dated CNYHKD / H offer - 1.
Five FX anchors corrected: 3308, 3223, 9976, 9607 and 2636. All 71 applicable
H offer prices checked against issuer documents/publications. Three A-after-H
listings and 6690 without an H offer price have no IPO premium. Market-cap
formulas use the appropriate A/H share-class field; terminal replies/units
remain unverified. No additional Bloomberg requests were added.

Database is compact with muted section bands. Cell comments/red markers have
been removed. The free-float share-count column is hidden from the desk view;
backing cells preserve existing formulas. Historical return dates remain
explicit under Returns as of. Current IPO Live snapshot is 9 November; this
release does not refresh the full historical return or A/H chart series.

Database A premium now (BT) links to AH current premium by H code. It follows
AH E4: Bloomberg for live quotes, Stored for saved values. The Quotes control
above the Database A/H block links back to AH E4. No extra Bloomberg request
is made by Database. AH reuses IPO Live's H price when both quote modes are
Bloomberg. Leave AH H4 Stored to avoid long chart-history requests.

3228 KINWONG / 603228, 6727 TRANSWARP / 688031 and 3757 ROBOTECHNIK /
300757 are restored to AH in Excel and HTML. Their A-share mappings were
missing from the canonical database. These three stored histories end on
2 October, consistent with their retained IPO snapshot; this is not a full
November market refresh. Existing 72 pair histories are unchanged.

AH: Company names are shown beside A/H codes. F:G contain A-share class
market cap in CNY millions and H-share class market cap in HKD millions,
using BDP CURRENT_MARKET_CAP_SHARE_CLASS when E4 is Bloomberg. Stored
mode shows a dash for these new fields; no cap snapshots are invented.
H:I show IPO/current premium; J:L show 1D/7D/1M premium changes in pp.

Live price check: M60 accepts the H code only. A code resolves from the AH
list, Database or Pipeline; O60 is an optional A-code override, Q60 an IPO
price override. P70 gets the current H quote, P72 the current A/H premium,
and P73 A price versus H IPO price. This small checker always requests live
BDP quotes, independently of E4. It never requests history. Live responses
and RR233 field coverage remain unverified without a Bloomberg terminal.

E4 controls the AH roster, H4 the charts; both default Stored. The new
small live checker is independent. J:L changes retain their existing
previous-H-session / seven-calendar-day / one-calendar-month definitions.

Premium and mainland returns now occupy aligned upper/lower charts. All
visible charts have consistent fonts, colours and axes; Live bars turn green
or red dynamically. Observed points and genuine gaps are preserved.

Database B2 defaults All: PE/PS and forward valuations load for all issuers.
Selected and Off remain optional. Screener reuses the same issuer results.
BDH output areas are writable, without preallocated multi-cell array locks.
BBG Verify B2 remains Off/On, default Off.
Stored is the default for daily monitors. Bloomberg mode requires the add-in
and a logged-in entitled terminal. This Mac cannot certify live Bloomberg
replies. Native Excel opened the final file without a repair prompt.

Standalone updater: python hk_ipo.py build reproduces stored data; update
refreshes providers then builds. Keep its persistent data directory. Source
review and handover are in START_HERE.md and data/release_state.json in the
project. A new price does not certify old histories or old filing fields.

GitHub downloads — 10 November 2026 release:
Excel: https://github.com/kennytam-code/code/raw/refs/heads/main/HK_IPO_Database_v1.xlsx
HTML: https://github.com/kennytam-code/code/raw/refs/heads/main/hk_ipo_dashboard.html
Publication status: _ipo_db/data/release_state.json in the repository.
