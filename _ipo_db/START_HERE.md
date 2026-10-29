# HK IPO — current handover

Read this file, then `data/release_state.json`. The latest instruction wins over
older dated entries in `MAINTENANCE.md`. This file is intended for the next AI or
analyst, including a session with no conversation history.

## 29 October: Bloomberg A/H horizon repair

Published to GitHub main on 29 October with the user's explicit request.
All five downloaded deliverables passed SHA-256 verification; root Excel and
updater match TO_NOMURA. See `data/release_state.json` for the release commit.
Market observations and all accepted financial inputs are unchanged.

AH E4 is now **Quotes** (Stored/Bloomberg), H4 is **Charts** (Stored/Bloomberg).
Both default Stored. For a live table without long history requests, choose
E4 Bloomberg and leave H4 Stored. Current A/H prices use scalar BDP LAST_PRICE;
one FX quote is shared. The independent IPO-price checker still follows E4.

1D/7D/1M are premium changes in percentage points. All references use the H
quote date: previous H session, seven calendar days earlier, or one calendar
month earlier. A and FX observations are as-of the chosen H close, with the
existing independent entitlement factors. Do not change them into stock returns.
One short H history and one A history per pair plus one shared FX history serve
all three horizons (145 guarded BDH occurrences for 72 pairs, 55 calendar days).
Long chart requests (16 occurrences) only activate with H4 Bloomberg. Counts
are formula occurrences, not measured terminal requests or RAM benchmarks.

The final native stage is ah_live_requests.apply after excel_chart_refresh.
It declares bounded two-column native BDH array ranges; header/error/blank-safe
lookup scans are single-cell native arrays for older Excel compatibility.
Quote-date normalization handles serials, YYYYMMDD numbers/text and date text.
H/A/FX positions are shared per horizon instead of repeated nested searches.
Missing replies show No quote, No date, No history or Too new, not zero or a
silent error. Group averages exclude unavailable text. Do not restore blanket
IFERROR blanks or couple table and long-chart request switches.

The small control template is data/ah_live_controls.json, authored via Artifact.
Tests: tools/test_ah_live_requests.py plus native_desk, presentation_package
and update_20261028. All original data/chart caches and 62 unaffected ZIP parts
are identical. Native Excel opened the final package without repair; the AH
table, controls and charts were reviewed. Bloomberg execution remains untested
without an entitled terminal. Review evidence: data/ah_live_fix_20261029/.

## 28 October: new listing, daily A/H changes and all Excel charts

Published to GitHub main on 29 October with the user's explicit request.
The data release is dated 28 October. Root downloads and TO_NOMURA match; all
five downloaded files passed SHA-256 verification. Publication used an isolated
checkout, preserving the parent Git branch/index and unrelated work. See
`data/release_state.json` for the release commit. Future changes require their
own publication authorization.

527 database IPOs, 717 IPO Live stocks, 72 A/H pairs, 21 pipeline rows. DSBJ
(2384 / 002384.SZ) listed 28 October: offer HK$86.80, public/institutional
subscription 0.52x/3.17x, 50.00% cornerstone allocation, 20 allocation groups
comprising 24 separately named legal investors. Primary evidence and rejected
vendor observations are under `data/update_20261028/`; accepted inputs are
`data/batches/latest_listed_review_20261028.json`. 6157 and 3275 are postponed
under issuer filings. Official AP/PHIP membership was refreshed; unparsed new
financial terms remain missing. The existing 526 issuers' numeric fields are
unchanged. Historical lock-ups remain 161 events / 158 stocks.

IPO Live's dated snapshot has 702 valid quotes from a 717-stock request, with
latest date 28 October. Missing/stale/debut references do not enter the daily
average. This is not a complete historical refresh: 70 A/H pairs remain at
2 October, Transsion at 15 October, DSBJ at 28 October. DSBJ uses the completed
27 October FX daily close (28 October's UTC FX bar was unfinished). Peer
histories remain 2 October. No later point is fabricated.

AH table is A:I: A/H codes, sector, subsector, IPO/current premium, then 1D,
7D and 1M premium changes in percentage points. 1D uses the previous H trading
session before the H quote date, with A and FX as-of closes and existing
independent entitlement adjustments. First-day IPOs have no prior-H-session
change. Seven days and one month keep the existing calendar definitions.
Sector and subsector summaries below the roster average each available pair
change, excluding missing. J5 jumps to these groups.

The independent A-current-price / H-IPO-price checker is on AH J58:O73; L5
jumps there. M60 is numeric H code; M61 optional numeric A-code override;
M62 optional positive H IPO-price override. M64/M65 show effective A code / IPO
price. M68/M69/M70/M72/M73 show A price, CNYHKD, converted A price, A premium
vs H IPO, and A quote date. E4 selects Stored/Bloomberg for it and the AH view.
Known H codes resolve Database or Pipeline terms. Unknown/new A codes need
Bloomberg mode for a live price; Stored never borrows another pair's cache.
The checker has no BDH request or A-price history graph. Its named outputs
A_PX/A_FX/A_HKD/H_TRM now refer to AH. The main AH charts remain.

Screener's selected-company A-code helpers moved from F53/F54 to hidden
Calc AY53/AY54. Valuation Data references AY54, independently of the manual
AH checker. Its live PE/PS matrix moved A63:D69 to A52:D58. The old Screener
checker/history spill and drawing were removed. Preserve all eleven W_* names.

Final build stages after screener_desk: ah_desk_update, excel_chart_refresh.
`data/ah_update_layout.json` is a bounded Artifact-authored template. The chart
stage styles all native chart parts and uses two aligned AH panels: premium
above, A-share/CSI 300 returns below, sharing dates. Navy/teal/grey distinguish
semantics; comparison lines have separate colours. Tiny AH points keep a
new one-observation IPO visible. Do not smooth or fill gaps. Live bars use
Excel's dynamic negative-fill red and positive green. Peer charts share plot
alignment with compact dates. Chart series/formulas/caches are preserved.
Manual layout uses edge positions, not offsets from automatic layout (Microsoft
Office Open XML ST_LayoutMode implementation notes). The prior single dual-axis
AH chart instructions later in this document are superseded.

Memory fix: combine_bbg_sheets loads the canonical roster once rather than
parsing a 15 MB JSON file once for every issuer. Keep the staged native build
and Python 512 MiB / Node 384 MiB limits. Never rescue a failure by raising them.

Validation: test_update_20261028.py (72 pairs, 100 summary formulas, input edge
cases, all chart series preserved); test_native_desk.py (Bloomberg valuation
response fixtures and native structure); test_presentation_package.py (167,037
formula structures, source/data parity and package relationships); actual desk
scoring; test_html_update_20261028.mjs (432 SVG cases, 40 controls);
test_scope_update_20261028.mjs (6,775 scope/average observations); selected means.
The final native workbook opened without repair and Live/AH/Peer/Screener areas
were inspected. This Mac is view-only; actual Bloomberg execution and mode
switching are not certified. Small final Artifact projections are under
out/update_20261028. Source review and formula notes stay outside the workbook.

`tools/package_update_20261028.py` is the date-specific local package utility.
It validates embedded source/data parity, prior-number preservation and hashes,
then installs only requested files with --install. It never publishes or
removes unrelated studies. Keep the previous Word studies untouched.

## 22 October: request load and compact Screener

Published to GitHub main on 22 October with the user's explicit authorization.
Root download files and TO_NOMURA contain the same verified release. Future
changes need their own publication authorization. Market observations were not
refreshed.

Database B2 controls live valuations: **Selected** (default: Screener company
and its displayed comparisons), **All**, or **Off**. BBG Verify B2 defaults
**Off**; On explicitly enables its 5,911 BDP/BDH function occurrences. Those
verification calls and 3,693 valuation occurrences previously lacked an on/off
guard. Counts are formula occurrences, not measured terminal/network requests.
TTM BQL is now only a fallback for a nonnumeric BDP response. Selected H values
reuse the database issuer block; pipeline-only H codes retain their own fallback.
All eight-row BQL response areas, field-header extraction and zero/negative
valuation handling remain intact. No actual Bloomberg terminal test is available.

AH Recent now covers all 71 roster pairs, including 9976, 9607 and 2636, and uses
one shared FX history: 143 guarded BDH calls versus 204 covering only 68 pairs.
The AH Compare sheet factors 52,808 repeated COUNT calls into four helper cells,
plus shared minimum/maximum/first-date positions. This changes computation,
not the observations or entitlement adjustments. Do not remove the hidden saved
history sheets: their constant cells do not issue Bloomberg requests.

Screener B5 remains the code/pipeline selector. D7:D14 now contains database
attributes, F7:F14 contains overrides; effective values are on hidden
Calc (scoring engine)!AX7:AX14. Selected-deal context is I7:L14. Filters are
P7 ranking, P8 cornerstone text, P9 A-share filter, P10 included codes and P11
comparison count. The old G5 helper moved to Calc!AX5. Preserve the explicit
reference map in `ipo_lib/screener_desk.py`; never restore old D18/B16 references
in tests or future patches. W_* inputs remain AU2:AU12.

HTML comparisons have endpoint codes/values, full dated legends and click/hover
focus. Real missing observations remain gaps. Premium + CSI uses aligned upper
and lower plots sharing dates, avoiding two return scales overlaid together.
HTML Screener also shows one selected analysis at a time. Sector scope, exclusive
average modes and six-line pagination remain mandatory.

Final stages: `request_efficiency`, then `screener_desk`. Small Artifact templates
are `data/request_controls.json` and `data/screener_desk_layout.json`; graft them
with native XML. Checks: `tools/test_request_efficiency.py`,
`tools/test_native_desk.py`, `tools/test_desk_scoring.py`,
`tools/test_presentation_package.py`, `tools/test_efficiency_html.mjs`,
`tools/test_comparison_scope.mjs`, `tools/test_selected_averages.mjs`.
The new tests supersede earlier date-specific layout assertions.

Bloomberg's primary documentation confirms BDP for a streaming last price:
`=IF(A8="","",BDP(A8,"LAST_PRICE"))`. BDH requests historical data. Source:
[Bloomberg Open API Core Developer Guide, §15.1 and §15.4](https://data.bloomberglp.com/professional/sites/4/BLPAPI-Core-Developer-Guide.pdf).
The guide is dated 2016; do not infer current default update intervals from it.
Changing workbook query scopes is not a measured speed benchmark.

## What the user wants

The user works in Nomura sales/trading. The deliverables are a professional Excel
workbook and a self-contained offline HTML dashboard. Clear and tidy comes first.
Use Nomura-inspired red, white space, grey and charcoal, with distinct section
colours and green/red performance changes. Latest feedback rejects brick red and
large red blocks in Screener. The working accent CB2125 is sampled from the red
signature graphic in Nomura's official Americas recruiting brochure, page 15;
it is not asserted as an official sRGB brand specification. Do not use the
Nomura Plus editorial palette. No large title at the top of each Excel tab.
Screener uses a pale-grey form and table header, with two clear input/context
areas. Retain useful Database section colours and comparison chart colours.
Avoid decorative cards, oversized merged areas, repeated explanations and generic
footnotes. Put methods and unresolved review notes in repository documents.
Preserve all data/formulas during design-only changes, and prove preservation.

Excel order: IPO Live, AH, Peer Trades, Screener, Database, Pipeline, leagues and
support. No Excel Lock-up, Analogs or Notes tabs. Keep Lock-up analysis in HTML and the
A/H research in Word. Screener freezes its first two columns. Support and helper
tabs stay at the back/hidden. Do not delete other research in TO_NOMURA.

## Current controls and definitions

| View | Controls / meaning |
|---|---|
| IPO Live | B4 Stored/Bloomberg; B5 Sector/Subsector; H34 subsector chart's broad sector. LAST_PRICE and PX_YEST_CLOSE. Daily return needs a real previous trading close: no offer-price substitution on IPO day. Stale/missing quotes do not enter daily averages. |
| AH | B4 chart pair; E4 Quotes Stored/Bloomberg; H4 independent Charts source. A:I roster includes 1D/7D/1M premium changes in pp. J5 jumps to group averages; L5 to independent IPO-price checker. |
| AH charts | Aligned premium and A-share/CSI return panels, common observed dates. Bloomberg requests through TODAY; Stored retains per-pair dates. No invented points or cosmetic interpolation. Reviewed split/bonus factors align each leg on its own ex date. |
| Peer Trades | B3 named direct product-peer pair; F3 source; H3 horizon; F4/H4 custom dates. Return spread = A minus B price return in percentage points, both rebased at their first common observed session. Keep the product overlap/mix distinction. |
| Screener | B5 is code-first: numeric-sorted H-code dropdown plus uncoded pipeline names; E5:L5 shows the resolved company. Free typing still accepts company names, leading zeros and Bloomberg tickers; retain exact numeric aliases such as 9607. Calc AY53 reads Database BQ (selected A code); AY54 is its ticker. The eleven W_* named model inputs now live in hidden Calc (scoring engine)!AU2:AU12, with names/descriptions in AT/AV. The final workbook has no Notes sheet. Never overwrite these inputs with prose. |
| Screener form | D7:D14 shows database inputs; F7:F14 contains overrides. Effective calculations are Calc!AX7:AX14. B5:C5 is the code/pipeline selector; E5:L5 shows the resolved company. Selected-deal context is I7:L14; filters are P7:P11. Top titles are hidden; the real snapshot date stays visible. |
| Database fundamentals | BJ/BL: live TTM P/E/P/S. BM:BO: NTM P/E, FY2027 P/E, FY2027 P/S. Screener BE/BG/BH:BJ mirrors these. Historical IPO multiples remain separate. |
| HTML comparisons | Active sector/subsector/search filters restrict both individual lines and mean inputs. Select all selects only that scope. Stocks, Selected average and Sector averages are mutually exclusive views. Six lines per page with full legend/tooltip. Means use **only checked stocks**, each stock one weight; multiple selected expiries of one stock are averaged within that stock first. Missing is excluded, not zero. |
| Lock-up (HTML only) | Historical, source-confirmed cornerstone expiries with complete ±30 HK-session endpoints. 161 events / 158 stocks in the 17 October release, prices through 2 October. Future/undated/ambiguous dates and incomplete or unverified price windows are excluded, not blank rows. Interior price gaps remain visible. Date shown is the last day locked; day 0 is the last HK session on/before it. |
| IPO returns | 1w/1m/3m are 5/21/63 traded sessions after debut. Ex-pop table returns start at day-1 close. Offer returns start at the offer price. Price performance excludes cash dividends. |

## Data authority and refresh dependencies

`data/deals.json` is the canonical listed database. `data/batches/` contains inputs
and accepted reviews; `_prov` records source and confidence. Do not only edit the
canonical JSON: a merge would undo it. A newly listed company needs the allotment
roster seed, accepted primary fields, classification, code mapping, dates and
price/horizon inputs. A new A/H pair additionally needs A and H caches, an
`ah_study` record and regenerated monitor/reference metadata. Validate every new
pair, not just the default chart. Keep the core IPO sample separate from legacy
monitor-only listings in `market_supplement.json`.

For a launched deal, retain the prospectus code, offer period, price range, share
count and expected listing date. Pipeline uses both official AP/PHIP feeds and
`newlistings.json`. `pipeline_dedupe` excludes listed companies and applies filed
withdrawal/postponement records. Unconfirmed press-only ideas are Watchlist,
separate from active offerings. Its status-check date is independent of market
data dates. Refreshing a new listing does not refresh all older price histories.

Important accepted batch: `latest_listed_review_20261015.json`. It includes ESWIN,
Longsys/Red Avenue mapping corrections and Transsion. Merge it before derived
arithmetic; `review_quote_guard` prevents its old prices overriding newer quotes.
2636: offer 35.30, public/institutional subscription 4.46x/2.55x, 86,648,300 base
shares. The 12,997,200 over-allocation is **not** exercised greenshoe. Lock-up last
day 14-Apr-2027. Cornerstone legal funds are distinct; manager aliases are explicit.
FY2025 attributable profit and revenue use the prospectus RMB0.8605/HKD conversion.
Sources, SHA256 hashes and the new market observations are under
`data/final_review_20261015/`. Do not use the erroneous vendor market-cap figure.

Corporate actions are not permission to invent smooth histories. Keep raw prices
and apply verified entitlement factors; record missing or incompatible dates.
The HTML sample is selected by `historical_lockups.historical_events` using
`data/lockup_date_review.json`. New code/date/source-hash combinations need primary
review before appearing. An elapsed date alone is not confirmation. A generic
six-month phrase without an exact end date/inclusive start remains excluded.
Subsequent amendments take precedence over the original schedule.
`data/lockup_amendments.json` blocks six issuer-level dates (2565, 2567, 2592,
2629, 2655, 2889) pending holder-specific reconciliation of filed extensions.
Do not restore them from an old prospectus. The targeted English/Chinese
amendment search is not an exhaustive legal-title search for every issuer.
Preserve `data/lockup_review_20261017` (source pages, listing-date proofs, prior
windows and independent price checks). 6911's 21-Dec-2024 row is a controller
restriction; its cornerstone date is 21-Jun-2024. The parser now stops at the
controller-group header. Do not revert the category or replace a reviewed
complete 30-session history while refreshing an incomplete legacy seven-day
window. Keep the full evidence internally, including excluded records.

## Bloomberg valuation contract

TTM PE/PS use scalar `BDP(…, "PE_RATIO")` / `PX_TO_SALES_RATIO`, with separate BQL
fallback areas. The user's expressions are:

```
pe_ratio(fpt=ltm, fpo=0, ae=a)
px_to_sales_ratio(fpt=ltm)
pe_ratio(fpt=ltm, fpo=1, ae=e)
pe_ratio(fpt=a, fpr=2027, ae=e)
px_to_sales_ratio(fpt=a, fpr=2027, ae=e)
```

Preserve eight-row response zones and field-header extraction: numeric date/year
metadata must not be mistaken for a multiple. Preserve zero/negative replies.
Unavailable remains Unavailable; do not substitute an IPO multiple. Do not add @,
INDEX/MATCH wrappers to historical BDH calls without proving response behaviour.
Actual Bloomberg add-in execution is not available on this Mac. Formula fixtures
and a clean native Excel open do not certify live replies. FY2027 is an explicit
estimate year; review its rollover deliberately rather than silently relabelling it.

## Rebuild, refresh and release

Read `ipo.py` stage order before a full refresh. Normal commands:

```
python ipo.py status
python ipo.py refresh
python ipo.py build
python ipo.py check
```

If a provider fails, retain its dated good cache and report the failure; do not
label the entire dataset current. After A/H updates, run `prepare_monitor_data`
and `prepare_ah_reference`. The standalone `hk_ipo.py update` performs the full
refresh/build workflow; `build` only reproduces stored data. It preserves an
existing persistent data folder, so use a clean folder to reproduce a release.

Large workbooks must use `staged_native_build`: core and monitors in separate
processes; native joining; peer history; colours; presentation; reflow; request
guards; chart axes; CSI combination; desk release; sector release; final polish; desk theme; remove Notes.
Apply each structural patch once to a fresh baseline. Never re-import/export the
full workbook for cosmetic work: unsupported native chart/Excel features matter.
The `ah_chart_style` stage must run after `desk_theme` and `remove_notes`:
navy premium, teal A-share return, amber dashed CSI 300, explicit axis titles and
top legends. Its first chart starts below the frozen header so the chart scrolls
as one object. Otherwise the generic theme overrides the semantic line colors.
Use `data/ah_chart_style.json`, authored by `tools/create_ah_chart_style.mjs`.
HTML uses the same three styles in a full-width combined panel and distinct
comparison colors/line styles. Preserve the underlying observations and gaps.

New layout pieces are authored with Artifact Tool and grafted without changing
business data. Use small cached projections for rendering.

For release QA, set `IPO_QA_BASELINES=1` before the staged build, then run
`tools/run_release_checks.py` sequentially. It checks native XML/relationships,
valuation fixtures, Screener scoring, prices/returns, sector math and style-only
preservation. Also run `tools/test_selected_averages.mjs` and
`tools/test_sector_comparisons.mjs`, `tools/test_comparison_scope.mjs` and
`tools/test_historical_lockups.py`. `tools/render_comparison_scope.mjs` checks and
renders the actual SVG functions without launching a browser. Render changed
views, and open the exact
final workbook in native Excel to check for repair. Do not claim browser/native
checks that were not actually performed. Test dates/horizons with actual and
missing observations, zero/negative responses and newly appended records.

Bundle with `ipo_lib/make_bundle.py`. Confirm it includes every new module,
template, cache and accepted source batch, including desk_theme.json / desk_theme.py and note_weight_layout.json / remove_notes.py. Deliver Excel, HTML, ZIP and updater
in TO_NOMURA and the existing GitHub root aliases. Do not overwrite unrelated
PCA/research files. Preserve Word studies. Compare hashes after copying and verify
the pushed commit. Keep audit CSV/JSON outside Excel. Update `release_state.json`
and this handover when controls, conventions, coverage or known limits change.
`tools/package_chart_scope.py` reproduces the archived 17 October HTML-only
release and pins that older Excel hash. Do not use it to package the current
workbook. Keep its historical validation record.

The 19 October presentation-only release uses `tools/package_ah_readability.py`.
Its baseline is the 17 October workbook. Only two A/H chart parts and the first
chart's top drawing anchor change; every worksheet and native formula is
byte-identical. `tools/test_ah_market_render.mjs` checks all 71 pairs at desktop
and narrow widths and compares the entire embedded dataset to the prior HTML.
These are actual SVG-function checks, not a browser rendering certification.

## Known limits to retain, not conceal

The 16 October taxonomy review retains the nine broad sectors and six Technology
groups as a practical daily-monitoring framework; it is not an endorsement of
every stock assignment or a claim that all members are direct peers. See
`data/taxonomy_review_20261016.json` for source-backed recommendations and boundary
issues. The review did not reclassify securities. In particular 2477 (WellCell)
is currently incorrectly in commercial biopharma and 2321 (Swang Chai Chuan)
incorrectly in oil/gas/utilities. Correct the persistent classification inputs,
canonical data and all derived monitor/HTML/Excel outputs together when applying
the recommendations; do not fix only a displayed workbook cell.

The last full numeric audit had 273 annual revenue/profit entries needing fresh
primary-row confirmation, 119 unresolved cornerstone name aliases in the earlier
filing-name audit. The 67 undated lock-up events are now internal evidence only,
along with 70 dates whose precise boundary needs confirmation. Twenty-six other
past, date-confirmed events lack a finished or independently checked 30-session
price window. These exclusions make the visible sample selective; do not describe
it as every IPO or an unbiased estimate of an expiry effect. The audit JSON/CSV is the
authority for current counts. Internal arithmetic consistency is not proof of
all underlying inputs. Older A/H and peer histories can be older than the newest
Live/new-listing quote. Keep their actual dates visible. Word studies are separate
dated research and are not automatically rewritten by a data refresh.

## 20 October: code selector and single-analysis A/H view

Apply `screener_code_selector` after the existing final native stages. It uses
`data/screener_code_layout.json` (Artifact-authored), creates AllTargetCodes in
hidden Calc AW3 onward, and retains SelectedDeal and all downstream scoring
formulas. B5 accepts 9607, 09607, 9607 HK Equity, exact names and pipeline names.
E5:F5 displays the matched company or Code not found. HTML Screener also puts the
code finder first, with code-valued suggestions and a visible invalid-query state.

HTML A/H shows one full-width analysis at a time: Premium (default), Premium +
CSI 300, A-share vs CSI around IPO, prices in HKD, or performance from first open.
Premium alone starts at listing and scales to its observed range; CSI uses its
explicit separate return axis. No smoothing or observation changes. Summary
changes are seven **calendar days** and one calendar month (existing definition),
in percentage points. The table is bounded; comparisons retain scoped selections,
exclusive stock/average modes and six-line pages. Company-history dates remain
pair-specific. The around-IPO analysis has its own fixed window.

Check `tools/test_screener_code.py`, `tools/test_screener_ah_html.mjs`, native desk,
package and comparison checks. 1,595 identifier formula cases; 426 actual SVG
cases; 40 detail-control cases. These HTML checks use a small DOM adapter, not a
fresh browser visual run. Native Excel opens without repair; the Mac is View Only,
so interactive code edits and Bloomberg responses are not certified live.
