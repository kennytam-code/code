# HK IPO — current handover

Read this file, then `data/release_state.json`. The latest instruction wins over
older dated entries in `MAINTENANCE.md`. This file is intended for the next AI or
analyst, including a session with no conversation history.

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
support. No Excel Lock-up or Analogs tabs. Keep Lock-up analysis in HTML and the
A/H research in Word. Screener freezes its first two columns. Support and helper
tabs stay at the back/hidden. Do not delete other research in TO_NOMURA.

## Current controls and definitions

| View | Controls / meaning |
|---|---|
| IPO Live | B4 Stored/Bloomberg; B5 Sector/Subsector; H34 subsector chart's broad sector. LAST_PRICE and PX_YEST_CLOSE. Daily return needs a real previous trading close: no offer-price substitution on IPO day. Stale/missing quotes do not enter daily averages. |
| AH | B4 pair code, E4 Stored/Bloomberg. Premium = A price × CNYHKD / H price − 1. Seven-day and calendar-month changes are percentage points. J5 links to sector averages at J57. |
| AH charts | Premium left axis; A-share and CSI 300 price returns right axis, common observed dates. Bloomberg requests through TODAY; Stored retains per-pair dates. No invented points or cosmetic interpolation. Reviewed split/bonus factors align each leg on its own ex date. |
| Peer Trades | B3 named direct product-peer pair; F3 source; H3 horizon; F4/H4 custom dates. Return spread = A minus B price return in percentage points, both rebased at their first common observed session. Keep the product overlap/mix distinction. |
| Screener | B5 resolves company or code; retain exact numeric aliases such as 9607. F53 reads Database BQ (A code). Notes B26/B27 are numeric named model weights W_SUB/W_SEC: never write prose there. |
| Screener form | B7:B14 shows database inputs; C7:C14 contains overrides. D7:D14 retains the effective calculation with display format `;;;`. The seven context outputs moved from H8/H9/H12:H16 to F7/F8/F10:F14 without changing their formulas or values. B5:C5 is the company selector. Top titles and duplicate selection prose are hidden; the real snapshot date stays visible. |
| Database fundamentals | BJ/BL: live TTM P/E/P/S. BM:BO: NTM P/E, FY2027 P/E, FY2027 P/S. Screener BE/BG/BH:BJ mirrors these. Historical IPO multiples remain separate. |
| HTML comparisons | Select all and Select sector; Selected average and optional By sector use **only checked stocks**. Unchecked same-sector stocks never enter. Each stock has one weight. For multiple selected lock-up expiries of one stock, mean those observations within the stock first. Missing is excluded, not zero. |
| Lock-up (HTML only) | Last locked day, first unlocked day, IPO date, cornerstone %, deal size, since-IPO return. Exactly 30 HK trading sessions either side. Future/unconfirmed endpoints stay blank. |
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
Unconfirmed cornerstone expiries stay undated. No-cornerstone rows are excluded
from the HTML event roster, while full restriction evidence stays in the batch.

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
guards; chart axes; CSI combination; desk release; sector release; final polish; desk theme.
Apply each structural patch once to a fresh baseline. Never re-import/export the
full workbook for cosmetic work: unsupported native chart/Excel features matter.
New layout pieces are authored with Artifact Tool and grafted without changing
business data. Use small cached projections for rendering.

For release QA, set `IPO_QA_BASELINES=1` before the staged build, then run
`tools/run_release_checks.py` sequentially. It checks native XML/relationships,
valuation fixtures, Screener scoring, prices/returns, sector math and style-only
preservation. Also run `tools/test_selected_averages.mjs` and
`tools/test_sector_comparisons.mjs`, render the changed views, and open the exact
final workbook in native Excel to check for repair. Do not claim browser/native
checks that were not actually performed. Test dates/horizons with actual and
missing observations, zero/negative responses and newly appended records.

Bundle with `ipo_lib/make_bundle.py`. Confirm it includes every new module,
template, cache and accepted source batch, including desk_theme.json / desk_theme.py. Deliver Excel, HTML, ZIP and updater
in TO_NOMURA and the existing GitHub root aliases. Do not overwrite unrelated
PCA/research files. Preserve Word studies. Compare hashes after copying and verify
the pushed commit. Keep audit CSV/JSON outside Excel. Update `release_state.json`
and this handover when controls, conventions, coverage or known limits change.

## Known limits to retain, not conceal

The last full numeric audit had 273 annual revenue/profit entries needing fresh
primary-row confirmation, 119 unresolved cornerstone name aliases in the earlier
filing-name audit, and 67 undated visible lock-up events. The audit JSON/CSV is the
authority for current counts. Internal arithmetic consistency is not proof of
all underlying inputs. Older A/H and peer histories can be older than the newest
Live/new-listing quote. Keep their actual dates visible. Word studies are separate
dated research and are not automatically rewritten by a data refresh.
