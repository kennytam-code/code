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
1-month price changes. The 17 November revision adds **average 20-day turnover
(HKD millions)** and an **A-share YES/NO** column. No borrow availability or
cost columns are included.

The email starts directly with the table: no title or summary block above it.
Column labels remain. It has no footnotes, method paragraphs or source-review paragraphs.
Methods and source metadata remain here and in the JSON audit. Unavailable
values stay N/A; affected rows keep a compact REVIEW label in their existing
status cell. The actual price/value dates remain beside their numbers.

The date window comes from the first report's actual `months` list, with past
expiries excluded. In the supplied code, `month_keys()` returns the current
month **plus the following two months**, despite the older comment saying
current and next month. For a run on 15 November 2026, the actual window is
15 November 2026 through 31 January 2027. The add-on reproduces that window
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
| Average 20-day turnover (HKDm) | `=BDP(ticker,"INTERVAL_AVG","MARKET_DATA_OVERRIDE","TURNOVER","CALC_INTERVAL","20D","CRNCY","HKD")/1000000` |
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
first cell. The override settings are exactly those in the original code;
the new column divides the value by 1,000,000. This is daily traded **value**,
not share volume, and it is the denominator of the existing unlock/turnover
multiple. No extra Bloomberg request is needed. If the first cell sets
`BLOOMBERG_TURNOVER_END_DATE`, the column shows that end date. Missing values
remain N/A. The formula above has not been tested on a live terminal here.

I could not verify a Bloomberg mnemonic for the existence of a mainland
A-share line. The A-share column therefore uses etnet's explicit
[A/H ticker table](https://www.etnet.com.hk/www/tc/stocks/ah.php) together with
its issuer share-capital section, through the original cell's HTTP/proxy client. It is a provider-based
classification, not a Bloomberg formula or independent exchange confirmation.
Examples of the source schema are [CATL's profile](https://www.etnet.com.hk/www/tc/stocks/realtime/quote_ci_brief.php?code=3750)
and [APT Electronics' profile](https://www.etnet.com.hk/www/tc/stocks/realtime/quote_ci_brief.php?code=2551).

- YES: an explicit A/H ticker pair or a positive mainland A-share capital
  class is reported, with no conflicting capital evidence.
- NO: a complete, recognised capital-class breakdown reconciles to the issued
  total and contains no positive A-share class. Unlisted domestic shares are
  not treated as A shares.
- N/A: unresolved requests, wrong issuer, incomplete page, unknown class label,
  inconsistent totals, conflicting evidence, or an issued total without a
  class breakdown and no explicit A/H pair. This
  deliberately includes profiles such as Tencent's, which only show an issued
  total. Missing data never becomes NO. Offshore Class A voting shares are
  not assumed to be mainland A shares.

The lookup fetches the A/H table once, then one profile per unique issuer,
sequentially. It validates table structure, ticker/link agreement and duplicate
codes. Absence from the roster never means NO. An explicit pair can resolve a
missing profile as YES; a pair that conflicts with a complete NO capital
breakdown produces N/A. Its URLs, fetch timestamps, mainland ticker/exchange,
capital amounts, page hashes, classification method and any error remain in the
JSON audit. Provider information can lag issuer changes; a successful page
fetch is not proof that the underlying capital table was updated that day.
Set `LOCKUP_EMAIL_CHECK_A_SHARES = False` to disable these requests; the column
then shows N/A. No new package is required. Downloaded profile fixtures and
their hashes are under `review_sources/`.

The actual lookup was run on the public web from this Mac on 17 November:
CATL 03750 -> YES / Shenzhen 300750; SMIC 00981 -> YES / Shanghai 688981;
APT Electronics 02551 -> NO; Tencent 00700 -> N/A (total only, no class breakdown).
The 211-pair etnet table was parsed successfully. This direct-network check
does not test the corporate proxy, Bloomberg or Windows Outlook.

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

Final review: **40 tests passed, zero failures or errors**. Both source cells
compile, the packaged notebook's cells match the source files, and cell 1
matches the Word attachment exactly. Python's measured peak RSS stayed below 80 MiB
under the unchanged 512 MiB guard. The updated twelve-column email is checked
at 1440 px and 1100 px. The sample contains fictional companies and numbers.
`validation.json` records the delivery hashes.
Run `python run_checks.py` from this folder to repeat the offline checks.
The tests use the retained source snapshots; no Bloomberg/Outlook connection
or original Word file is needed. To also recheck your Word attachment, run
`python run_checks.py --source-docx /path/to/code.docx`.
