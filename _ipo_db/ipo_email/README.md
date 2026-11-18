# Separate shortable lock-up email

The ready-to-run notebook is `HK_IPO_Two_Emails.ipynb`. Open it in Jupyter
using the same kernel as your working notebook and run cell 1, then cell 2.
It contains exactly two code cells, with no saved outputs or test fixtures.
Cell 1 matches the code extracted from your original Word document exactly.

To keep using your existing notebook instead:
Copy all of `second_cell.py` into a new second code cell in your existing
Jupyter notebook. Run your original first cell, then run the new cell. Keep
the original cell exactly as it is. The add-on reads its `LAST_DRAFT` result.

The new cell creates a second editable Outlook draft with its own subject.
It uses the first cell's To/CC settings; the settings at the top of the
new cell let you change these or disable automatic draft opening. It never
sends an email. Nothing was sent or opened in Outlook during development.

The second email includes both YES and NEW shortable stocks, with one row per
lock-up tranche, ordered by expiry. It shows the expiry date, days remaining,
stock, holder category/count, unlock percentage of issued shares, unlock value,
unlock/free-float-cap percentage, unlock/20-day-turnover multiple, Bloomberg
IPO price, last price and quote date, price change versus IPO, and 7-day and
1-month price changes, **average 20-day turnover (USD millions)** and an
**A-share YES/NO** column. No borrow availability or
cost columns are included.

The 18 November revision uses Times New Roman throughout. Unlock cells are
pale amber only when the reported percentage is strictly greater than 30%;
exactly 30% is not highlighted. A-share YES cells are pale green. Stock labels
retain the exact hyperlink destination used in cell 1 (`row['url']`).
The shortable column is removed: both YES and NEW still qualify for inclusion,
and their original status remains in the audit. The table now has 11 columns.

The email starts directly with the table: no title or summary block above it.
Column labels remain. It has no footnotes, method paragraphs or source-review paragraphs.
Methods and source metadata remain here and in the JSON audit. Unavailable
values stay N/A; affected rows keep a compact REVIEW label under the stock.
The actual price/value dates remain beside their numbers.

The date window comes from the first report's actual `months` list, with past
expiries excluded. In the supplied code, `month_keys()` returns the current
month **plus the following two months**, despite the older comment saying
current and next month. For a run on 18 November 2026, the actual window is
18 November 2026 through 31 January 2027. The add-on reproduces that window
without changing the original function.

## First-cell NEW review

In the lock-up table, NEW means added to the HKEX short-selling list within
the last five Hong Kong trading days and still eligible on the latest list.
The original code compares every published revision in that window with
the immediately preceding list. It does not mark all stocks NEW on the
first notebook run, and rerunning on the same day does not clear the label.
A stock becomes YES when its addition falls outside the window, NO if it
is removed, and NEW again if it is re-added within the window. Renaming a
stock without changing its code does not count as an addition.

PHIP uses a different NEW rule: added since the previous successfully saved
draft. The first saved draft establishes a baseline; an unchanged same-day
rerun clears PHIP NEW, while lock-up NEW retains its five-day meaning.

Both behaviours passed tests of the original functions. No first-cell
logic was changed. The first cell still stops if its source validation or
required comparison baseline fails; a handled source failure leaves
LAST_DRAFT as None, so cell 2 asks you to rerun cell 1. After any first-cell
error, rerun it successfully before proceeding to cell 2.

## Bloomberg prices

Your first cell already uses Bloomberg Desktop API. The add-on reuses that
connection class, so it does not need to start Excel or install another
Bloomberg wrapper. Formula correspondence:

| Value | Bloomberg request / Excel equivalent |
| --- | --- |
| Latest available price | `LAST_PRICE`, equivalent field to `=BDP(ticker,"LAST_PRICE")` |
| IPO offer price | `EQY_INIT_PO_SH_PX`, equivalent to `=BDP(ticker,"EQY_INIT_PO_SH_PX")` |
| vs IPO (%) | `(latest price / IPO offer price - 1) * 100` |
| Currency | `CRNCY`, equivalent to `=BDP(ticker,"CRNCY")` |
| Quote date | `LAST_UPDATE_DT`, equivalent to `=BDP(ticker,"LAST_UPDATE_DT")` |
| Original 20-day turnover input (HKD) | `=BDP(ticker,"INTERVAL_AVG","MARKET_DATA_OVERRIDE","TURNOVER","CALC_INTERVAL","20D","CRNCY","HKD")` |
| Shared FX rate (HKD per USD) | `=BDP("USDHKD Curncy","LAST_PRICE")`, with `LAST_UPDATE_DT` checked |
| Average 20-day turnover (USDm) | `original HKD turnover / USDHKD rate / 1000000` |
| Previous observed daily closes | `HistoricalDataRequest` for `PX_LAST`, the data requested by `BDH` |
| 7D / 1M change | `(latest price / selected historical close - 1) * 100` |

The API takes a snapshot when the cell runs; the email does not stream prices.
IPO price is added to the existing reference-data request, so it does not
require another request per stock. Its missing/non-positive/error responses
produce N/A for IPO price and vs IPO, without suppressing valid 7D/1M changes.
The IPO comparison can still be calculated when 7D/1M history is unavailable,
provided both prices and a sufficiently recent quote date are available.

The offer-price field is documented in the financial-data methods of
[Cleary et al. (2021)](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0243813).
Its live response has not been verified here. For A/H or secondary listings,
confirm that the returned price belongs to the relevant Hong Kong offering.
The calculation compares the reported IPO price with the current price; it
does not separately adjust the IPO price for subsequent capital changes or
claim to measure a particular holder's cost or profit. No offer price is
inferred from the first trading close or another listing.

Seven days means seven calendar days before the report date. One month means
the same day in the previous calendar month, clamped at month end. Each
baseline is the latest available daily close on or before that target date.
It does not use a later observation or substitute an offer price.

Historical requests explicitly enable Bloomberg capital-change adjustments
and disable cash-dividend adjustments, including the account's DPDF defaults.
These are price changes, not dividend-inclusive total returns. The exact
historical options are in `_lu_bbg_request`. Bloomberg documents the
[Excel/API mappings and historical options in its Core Developer Guide,
sections 15.1–15.4](https://data.bloomberglp.com/professional/sites/4/BLPAPI-Core-Developer-Guide.pdf).

Unavailable/non-positive prices, missing quote dates, history that starts too
late, or quote/baseline dates more than 10 calendar days old produce N/A
returns. The latest price and its reported quote date remain visible when
available. Raw errors, actual baseline dates/prices, source timestamps and
the unchanged first-report lock-up fields are retained in a separate JSON
file. No terminal response is invented or replaced with public-web prices.

Existing lock-up values and liquidity ratios are reused, not recalculated
using the new current price. The source valuation timestamp is shown beside
the unlock value. Existing review flags remain visible as compact status labels. The add-on does not
independently verify etnet's expiry dates or convert them into confirmed
primary-source dates.

## Added columns

Average 20-day turnover reuses `avg_turnover_20d_hkd` already fetched by the
first cell. Cell 2 adds **one shared FX reference request per non-empty run**,
on the existing connection, for `USDHKD Curncy` / `LAST_PRICE` and
`LAST_UPDATE_DT`. The USD/HKD quote is HKD per USD; the column divides the
HKD amount by that rate and then by 1,000,000. This is daily traded **value**,
not share volume. It converts the existing 20-day average at the current FX
snapshot; it does not recompute an average using each day's historical FX.
No hardcoded peg or public-web FX fallback is used. Bloomberg identifies the
[USD/HKD pair in its currency data](https://www.bloomberg.com/markets/currencies/asiapac_currencies.html).

Original HKD amounts and the unlock/turnover multiple are preserved. If the
first cell sets `BLOOMBERG_TURNOVER_END_DATE`, the column shows that end date;
conversion still uses the current FX snapshot. The actual FX rate, quote date,
raw response and errors are retained in the audit. Missing, nonpositive,
invalid, future or more-than-10-day-old FX quotes produce N/A for USD turnover;
valid stock prices, returns and draft creation remain available. No new
package is needed. Bloomberg/Outlook have not been tested live here.

I could not verify a Bloomberg mnemonic for the existence of a mainland
A-share line. This does not establish that no such field exists; terminal
field discovery and a real response would be needed to verify one. Prices
and turnover still use Bloomberg. The A-share lookup uses etnet's explicit
[A/H ticker table](https://www.etnet.com.hk/www/tc/stocks/ah.php) and the complete
ordinary-share structure behind [Eastmoney's company profiles](https://emweb.securities.eastmoney.com/PC_HKF10/pages/home/index.html?code=00700&type=web&color=w#/CompanyProfile).
Its public endpoint is `datacenter.eastmoney.com/securities/api/data/v1/get`,
report `RPT_HKF10_INFO_EQUITYSTR`. EtNet issuer capital classes provide a
fallback when the two batch sources do not resolve an issuer. This is a
provider-based classification, not a Bloomberg field or exchange certification.

- YES: an explicit A/H ticker pair or positive mainland A-share capital class.
- NO: complete recognised classes reconcile to issued capital and establish
  that there is no mainland A-share line. Tencent is now resolved from its
  complete Hong Kong/issued-share structure, rather than its total-only profile.
- A generic mainland-listed class is not automatically A: it can include NEEQ
  domestic shares. For this case, the specific etnet domestic/H classes must
  match Eastmoney's total, Hong Kong and domestic counts exactly.
- Missing evidence is never converted to NO. A genuine contradiction, source
  outage or malformed reply remains N/A, with details in the JSON audit.
  Offshore Class A voting shares and unlisted domestic shares are not A shares.

The lookup fetches the A/H table once, then share structures in batches of 40
issuers, sequentially. Individual profiles are requested only if still needed.
It validates issuer codes, ticker links, class labels, dates, nonnegative whole
share counts and capital reconciliation. Absence from the roster never means
NO. An explicit A/H pair conflicting with a complete non-A structure is still
rejected. URLs, timestamps, response hashes, classes, methods and errors remain
in the audit. A newly fetched page can still contain dated provider data.

Requests reuse the original HTTP opener, proxy and TLS settings, with no added
package. Each network operation has an 8-second timeout, responses are limited
to 2 MB, and a 45-second budget stops further requests/reads. An in-progress
socket operation can last until its timeout; 45 seconds is not a strict total
wall-clock guarantee. There are no retry loops. Handled or unexpected A-share
lookup failures do not prevent saving the second draft. The notebook console
reports unresolved lookup counts; the email has no added notes or footnotes.
The settings are `LOCKUP_EMAIL_WEB_TIMEOUT`, `LOCKUP_EMAIL_WEB_BUDGET` and
`LOCKUP_EMAIL_CHECK_A_SHARES` (False disables lookup and displays N/A).

On 17 November, the actual lookup resolved **all 69 unique stocks** across
73 future tranches in the original November–January window: **13 YES, 56 NO,
zero N/A**, in 2.36 seconds on this Mac. This coverage check precedes the
shortability filter and does not independently verify expiry dates. It is
recorded in `review_sources/live_window_coverage.json`. An eight-stock check
also resolves CATL/SMIC as YES and Tencent/APT/Alibaba/Xiaomi/Meituan/JD as NO.
The direct public-web tests do not test the corporate proxy, Bloomberg or
Windows Outlook. Timing is an observation, not a runtime guarantee.

Jinxun 03636 was the one apparent conflict: its NEEQ shares were labelled
generically as mainland-listed by one provider. Both providers' complete
domestic/H share counts agree. Its [2 November issuer filing](https://www.hkexnews.hk/listedco/listconews/sehk/2026/1102/2026110203435_c.pdf)
identifies NEEQ 870844 and the post-capitalisation total; its
[name-change filing](https://www.hkexnews.hk/listedco/listconews/sehk/2026/0227/2026022700889_c.pdf)
identifies the NEEQ venue explicitly. The code uses the general class/count
checks above, with no hardcoded ticker override. Retained source fixtures and
the regression test cover both this resolution and mismatching counts.

Primary-source spot checks support the positive pairs in
[CATL's 2025 annual report, page 4](https://www.hkexnews.hk/listedco/listconews/sehk/2026/0311/2026031100770.pdf)
and [SMIC's 2026 interim summary, page 3](https://star.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-08-28/688981_20260828_XAT4.pdf).
[APT's March 2026 monthly return, pages 1–2](https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0409/2026040900796.pdf)
documents the H and domestic classes; the unlisted domestic class is also
identified in its [May 2026 proxy form](https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0506/2026050601642.pdf).
These dated examples validate interpretation of the classes; they are not an
independent current verification of every stock in the provider table.

## Files and verification

Outputs go into a new `Shortable_Lockups` subfolder beneath the original
email output folder, with unique names: editable `.eml`, HTML preview, plain
text and JSON audit. No original files or first-email data are overwritten.
No matching rows produces an explicit empty-result draft without a Bloomberg
request. A stale or unsuccessful first-cell run requires rerunning that cell.

The review also executes both complete cell sources in one shared namespace
with external source retrieval and desktop applications replaced by fixtures.
The original report construction, NEW logic, SQLite state, rendering, MIME,
and file-writing paths execute. The add-on is checked with the original
Bloomberg connection class against a simulated API. The first report,
first-email files, and existing globals remain unchanged after cell 2 runs.

The original parsers accepted downloaded HKEX lists effective 6 and 10
November 2026 (1,267 securities each) and the government holiday calendar.
This is a source-format check, not an end-to-end live feed run or a test of
your corporate proxy. The 13 November URL returned 404; the original code
already skips confirmed missing pages while rejecting malformed/blocked ones.
The downloaded evidence and parser results are under `review_sources/`.

Cell 2 now validates its timeout before sending any Bloomberg request. It
also falls back to PowerShell when pywin32 is missing/broken or Outlook
connection fails before a draft exists. If an existing draft fails later,
it avoids opening a duplicate. Outlook's signature and unsent status are
covered by mocked automation tests. Neither cell calls Send.

Offline checks cover scope boundaries, year/month ends, YES/NEW eligibility,
multiple tranches, positive/negative/zero returns, missing/stale observations,
IPO-price field wiring, missing/invalid IPO prices, independent return horizons,
multipart Bloomberg responses, security/field errors, escaped HTML, MIME
output, unique filenames, and preservation of the first report. These checks
use synthetic fixtures. Bloomberg and Windows Outlook have **not** been
tested live here; run both cells on your Bloomberg desktop to verify them.

Final review: **49 tests passed, zero failures or errors**. Both source cells
compile, the packaged notebook's cells match the source files, and cell 1
matches the Word attachment exactly. Python's measured peak RSS stayed below 80 MiB
under the unchanged 512 MiB guard. The updated eleven-column email is checked
at 1440 px and 1100 px, including Times New Roman, the strict 30% threshold,
A-share highlights and stock links. FX tests cover conversion direction,
units, invalid/missing/stale quotes and isolation of an FX timeout from the
rest of the draft. The sample contains fictional companies, numbers and FX.
`validation.json` records the delivery hashes.
Run `python run_checks.py` from this folder to repeat the offline checks.
The tests use the retained source snapshots; no Bloomberg/Outlook connection
or original Word file is needed. To also recheck your Word attachment, run
`python run_checks.py --source-docx /path/to/code.docx`.
