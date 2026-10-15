## 16 October 2026 — latest user correction: colour and Screener form

This supersedes the red-header draft immediately below. The user rejected its
brick-red tone and large red fields, and requested no per-tab title rows.
Reference now inspected: Nomura Americas Recruiting Brochure, page 15, at
https://www.nomura.com/amhr-recruiting-brochure/files/assets/common/downloads/Nomura_Americas_Recruiting_Brochure.pdf
The principal signature-graphic red renders as CB2125 in the PDF preview; this is
a sampled working colour, not a claimed official sRGB specification. The public
corporate description calls the colour Heartful Red. Nomura Plus is no longer
the style reference. Screener now has grey headers and a source/override form on
the left, with seven context outputs on the right. Effective cells D7:D14 retain
their formulas under display format `;;;`; inputs and scoring references do not
move. The context-output mapping is tested. Large tab titles are cleared, their
rows hidden without shifting chart anchors or formulas. Database data is intact.

## 15 October 2026 — red-led visual direction

Latest user direction supersedes the earlier navy/grey emphasis: use elegant
Nomura-inspired red prominently. Official visual reference inspected:
https://plus.nomuraholdings.com/en/latest/20260424-FY202603-4Q-Highlights.html
The public page uses red rules and accents, white space and pale warm table fills.
Our adapted desk palette uses A9322C red, 8F2D2D deep red, white and warm grey;
it is not an official internal Nomura template. Database retains useful section
colours; returns remain green/red and comparison curves stay distinguishable.
Artifact-authored profiles now apply red titles/headers and warm input/row shading
throughout the desk. HTML navigation, table headers and charts follow the palette
without gradients or rounded pill navigation. No business data or formulas change.

## 15 October 2026 — all other desk tabs restyled

The final desk_theme stage applies an Artifact-authored style profile to 13 other visible/support sheets. It standardises Arial typography, red headers, warm input shading, alternating rows, long-name wrapping and native chart line/grid colours. Screener subsector/industry widths are expanded. Native chart data, axes, anchors, formulas, cached cell values and worksheet order are unchanged; test_desk_theme checks those separately from the earlier Database polish. All visible sheets were inspected as bounded actual-cell projections or in native Excel. Native Excel opened the final book without content repair; Live, AH, Peer Trades and Screener were rechecked.

Screener's unknown pipeline profitability now stays blank rather than rendering a numeric zero in a Y/N field. AH's summary says stored dates vary by stock: 70 pairs end 2 October and the new 2636 pair ends 15 October. Keep actual chart dates. Formula and UI fixtures pass locally, but actual Bloomberg add-in execution remains untested on this Mac.

## 15 October 2026 — final desk review and Database presentation

Read START_HERE.md and data/release_state.json first. They are the current handover and supersede obsolete counts/control locations below.

Database typography, widths, alignment, header heights and muted section bands were restyled using an Artifact-authored small template and a native XML graft. The final-polish test compares every cell value/formula against the immediate pre-polish workbook. Existing 525-stock numeric values also match the saved pre-review database. Removed generic footnotes are explicit cells, never a length-based deletion of data, legal names or source notes.

Separately, the source review appends Transsion 2636 (15-Oct debut) and adds Slender West Lake 6157's offering terms. Official AP/PHIP feeds are checked on 15 October. The final roster is 526 core / 716 Live / 71 A/H. HTML has 398 cornerstone events for 388 companies; Excel has no Lock-up sheets. Existing historical prices were not advanced by this incremental review. Live has 701 current 15-Oct closing quotes, six stale observations and nine missing securities. The 700 valid daily returns exclude the new IPO. On IPO day Tencent's reference is the offer price; stored and Bloomberg daily-change formulas now exclude that reference from previous-close and sector daily-return calculations.

The new accepted batch, dated evidence manifest and per-provider JSON retain source provenance. An over-allocation is not exercised greenshoe. New Transsion financials use the explicit prospectus currency conversion. Pipeline press ideas are Watchlist, postponed/withdrawn names stay separate, and the official application queue is limited to 30 recent entries. Rebuild final_polish once after sector_monitor_release; package its module and database_layout template.

The final checks cover the native package, retained charts, live formula fixtures, source parity and selected-only comparison means. Bloomberg live execution still requires a terminal. Primary-source gaps remain in the separate numeric/name audit; a clean arithmetic result does not certify every input.

## 15 October 2026 — averages follow the checked stocks

This supersedes the earlier full-sector overlays and event-weighted HTML mean. A/H and Lock-up now share selectedAverages: the overall Selected average and optional By sector curves use only the checked rows surviving the chart date window. Unchecked same-sector stocks must never enter either curve. A/H shows the selected mean by default; Lock-up defaults to Selected average, with Selected stocks + average available. Select sector replaces the selection; unticking any row immediately removes it from the averages.

Each distinct selected stock has one weight per observed date/session. If more than one selected lock-up expiry belongs to the same stock, average its available selected-expiry returns first, then average across selected stocks. Never include unselected expiries. Missing/non-finite values are omitted, not zero-filled; real zeros/negative values remain. The tooltip count is contributing stocks. The workbook sector summary is unchanged. tools/test_selected_averages.mjs executes the actual renderers with an unchecked 900% same-sector outlier, duplicate selected expiries, date bounds and changing selections.

## 15 October 2026 — sector comparisons and HTML-only lock-ups

This entry supersedes the earlier Excel lock-up controls. The final build applies sector_monitor_release after desk_release. Excel removes Lock-up, Lock-up Data, Lock Compare and Lock Matrix, their exclusively owned native parts, and Chart Data K:O. A:H data and native charts elsewhere remain unchanged. Worksheet-local names are reindexed; remaining formulas must not reference any removed sheet. The source lock-up dataset and all 397 HTML expiry schedules remain.

AH J57:O67 contains equal-weight sector averages: IPO premium, latest premium, 7-calendar-day and one-calendar-month premium changes in percentage points. The formulas read the existing AH table, so they follow E4 Stored/Bloomberg without additional requests. Missing/non-numeric values are excluded, valid zeros and negatives retained. Pairs is the sector roster count, not necessarily the available observation count for each metric. A shortcut in J5 opens the summary. The same-date diagnostic formerly at J60 is preserved at hidden P60. The small Artifact-authored sector_summary_template.json is required by the standalone updater; sector rows and range bounds are regenerated from the current roster.

HTML A/H and Lock-up retain Select all and add Select sector, Clear and an optional Sector averages overlay. Select sector replaces the comparison selection with that sector. A/H averages include all eligible pairs of each represented sector on each actual date; missing values are never zero-filled or interpolated. Lock-up averages include all observed events of the represented sector within the selected expiry dates, aligned to expiry close = 0% over -30..+30 HK trading sessions. Selected-event average means an equal-weight mean of the selected observed expiry events, including separate dates for issuers with multiple events. Tooltip observation counts expose changing coverage. Unconfirmed/future events remain selectable in the roster but cannot contribute an invented reference close.

Stabiliser explanatory paragraphs and trading-outcome commentary are removed. Keep concise headers and controls. Run test_sector_monitor_release.py, test_sector_comparisons.mjs, test_native_desk.py and test_presentation_package.py for this release. Browser checks cover all six A/H sectors, all eight lock-up sectors, full/clear selection and date filters. This change does not refresh historical market data or certify live Bloomberg execution.

The exact final workbook opened in Microsoft Excel without a content-repair prompt on 15 October. The sector table, existing A/H charts and sheet removal were reviewed in native Excel, then closed without saving review-only view changes. Excel was view-only; live Bloomberg execution remains a terminal check. For the sector regression test, preserve the pre-stage workbook as out/_sector_baseline_20261015.xlsx; it proves every unaffected worksheet and retained chart is byte-identical.

## 15 October 2026 — final desk review and newly listed ESWIN

Screener blank-table regression: Notes B26/B27 are W_SUB/W_SEC. Never write descriptive controls into numeric/name-bound model cells. Control descriptions now use Notes rows 70–72 and all W_ names must resolve to positive numbers. Direct native recalculation is part of release QA.

9607 Red Avenue was falsely marked without an A line. HKEX prospectus PDF pages 21/23 confirms SSE 603650 listed 27 June 2018. The mapping now survives a merge and both A/H monitors contain it. Three H observations through 2 October and 26 pre-/post-listing A observations are retained with URLs. CSI uses common actual observations. The provider H debut is 39.98 versus the retained Database 40.00; this 0.02 HKD difference is an internal diagnostic, not permission to overwrite an already reviewed historical IPO return.

Full rebuilds now use staged_native_build: save the core and monitors in separate processes, graft native parts with isolated paths/styles, then apply peer history, caches, presentation, reflow, request guards, axes, benchmark and final desk format in fresh stages. Python remains capped at 512 MiB. Never retry a failed build with a larger cap or publish a partially styled intermediate workbook.

This entry supersedes earlier release counts and control addresses. Database/Screener contain 525 IPOs; Live contains 715 seven-year listings. Stored Live has 706 validated closing quotes dated 14 October; legacy A/H and peer histories retain their individual dates (mostly 2 October). AH has 70 pairs. Lock-up has 397 cornerstone schedules for 387 issuers. Lock controls are B4/E4 (event), B10/E10/H10/K10 (comparison codes), B11/E11 (expiry cohort). Peer controls are B3 (named pair), F3 (source), H3 (horizon), F4/H4 (custom dates). Live B4 is source, B5 grouping and H34 broad-sector selection.

1256 ESWIN listed on 9 October and had been omitted because the core roster seed was stale. latest_listed_review_20261015.json plus hkex_allotments.json now preserve its official sources, allocation quantities, legal subscribers, offer terms and financial basis. The 47,106,000-share upsizing is not a greenshoe. Public/institutional subscription levels are 9.09x/1.95x. Ten legal cornerstone subscribers total 749,354,000 shares (46.33% of the enlarged offer); the GBAHIL parent aggregate must not be counted again. ORIX's investing SPC is distinct from its manager. Locked through 8 April 2027, first unlocked day 9 April. Future windows and immature 1w/1m/3m IPO returns stay blank. The price path contains actual HKD closes, never offer-normalised values. Benchmark closes use the existing HSTECH 3033 proxy and explicit matching sessions.

Merge the accepted latest-listed batch before derived size/return calculations. review_quote_guard skips mutable A/H/H-price snapshot fields when a later dated prices/study/history refresh is present; mapping, IPO reference premiums and filed terms remain durable. An old Saturday retrieval marker is treated as the prior business date for this ordering check. The separate Live snapshot does not replace historical A/H observations. Its filing-prefixed priority prevents a manager-name scrape replacing the legal cornerstone subscriber list. Longsys's reviewed mapping and observations are preserved by the same durable acceptance path. Do not publish a corrected canonical JSON without its roster seed and accepted-source batch: the next rebuild would omit or regress it.

Pipeline excludes listed codes/names in both builders. Support tabs have compact rows and wrapped league headers. BBG Verify retains simple direct BDH requests inside an outer availability guard; off-terminal execution shows Unavailable. Historical IPO ratios and live TTM/NTM/FY2027 multiples remain distinct. Native worksheet sequence, unique cells, table-header agreement and named chart axes are checked before opening the exact delivery in Excel. Never treat synthetic formula fixtures as terminal execution.

## 13 October 2026 — named product peers and chart presentation

## 14 October 2026 — compact monitors, comparison dates and A/H coverage

The latest release supersedes the older control addresses below. Lock-up and Peer Trades have no merged cells, flat tables, horizontal controls and no generic explanatory footnotes. Peer Trades uses B3 for a named product peer pair, F3 for Stored/Bloomberg, H3 for the horizon, and F4/H4 for custom dates. The two companies and returns are beside one another. The transferred scalar model lives in hidden Peer Chart N:Y. Move absolute as well as relative internal references; Excel copy translation alone leaves the original $B$3 and similar references behind. The visible source/horizon inputs feed the same builds as the native curves. Lock-up uses B4/E4 for the event, B30/E30/H30/K30 for compared H codes, and B33/E33 for the expiry-date range. All 396 filed / unconfirmed schedules, IPO dates, source links and +/-30 HK-session windows remain.

HTML A/H preserves the six-panel layout. Compare selected pairs now has Select all, Since listing / 1M / 3M / 6M / 1Y / 3Y and custom dates. Each premium retains its absolute level; different IPO dates are not rebased to a common listing date. The selected-stock premium panel also shows A-share and CSI 300 price returns on a separate right axis. Excel combines these three series in one native chart with a common actual date timeline, replacing the separate CSI chart. Premium is on the left; stock/index return is on the right. A/CSI context starts up to 31 calendar days before the H IPO. No pre-A-listing price is invented.

9976 LONGSYS was incorrectly missing its A-share code. The issuer's 8 September announcement (https://static.cninfo.com.cn/finalpage/2026-09-08/1225554053.PDF) confirms H 09976 / A 301308. Its mapping is retained in ah_map.json so a merge preserves it. All 18 H sessions from 8 September through 2 October are restored. The seven-year A/H roster is now 69, while Database/Screener remain 524 IPOs and IPO Live remains 714. Appended monitor rows must extend AH History ranges and worksheet dimensions as well as the code list. Ingenic 3223 already has 28 saved H observations. Headered Bloomberg histories may start later than debut, and a first-close difference is diagnostic rather than a reason to suppress every point. Actual quote dates and freshness guards still determine each usable A/H/FX point. The same-date comparison remains available.

Verified bonus/split schedules now normalize historical A/H premiums by the cumulative share factor on each leg's own ex date. Native and HTML formulas use A_quote * FX / H_quote * A_factor(A_quote_date) / H_factor(H_date) - 1. This eliminates mechanical entitlement jumps; it does not fit a smoother curve or invent missing observations. Raw quotes remain raw for price checks. The stored and live historical premium formulas share the same schedule and date guards. H event dates in seven earlier reviews are sourced from the retained split series; do not describe them as independently HKEX-file verified. New actions still require source review.

Live TTM PE and PS use scalar BDP PE_RATIO / PX_TO_SALES_RATIO first, with the user's BQL TTM expressions in separate clear fallback areas if the direct result is unavailable. Estimates retain the exact supplied NTM / FY2027 BQL expressions. No historical IPO multiple is substituted for an absent live value. Negative/zero numeric replies are preserved. Selected A-code F53 consistently reads the verified mapping; F54 normalizes to six digits and CH Equity; F56 owns a clear two-column BDH output area. Off-terminal cached valuations remain Unavailable; this machine cannot execute Bloomberg's add-in.

Refresh now rederives desk metadata and benchmark references after the A/H study, fetches the six legacy A/H histories and the curated 66 peer securities sequentially, retains early FX observations, and preserves 30-session lock-up windows. A partial provider failure retains individually dated saved data and is retried on the same cutoff. CSI cache refreshes only when the A/H cutoff advances. The updater must pack monitor_layout.json plus reflow_monitors, adjust_ah_charts, fix_monitor_requests, combine_ah_benchmark, refresh_monitor_data and both prepare modules. The full native build applies these patches once, after normal assembly. Never patch an already patched workbook as a baseline.

Checks use streaming native XML, scalar formula fixtures, all 69 browser A/H selectors, Select all/date controls, 35 named peer horizons, 396 expiry events and offline reopen. Bloomberg fixtures validate logic, not live terminal availability. Small cached projections verify presentation; the Artifact renderer does not resolve imported combo-series references, so its combo projection rebinds the same native caches as explicit groups. Native curves retain dynamic named ranges and their own axes. Python stays capped at 512 MiB, Node 384 MiB and renderer JS 128 MiB; Excel stays closed. Saved market prices remain dated 2 October 2026.


Peer Trades now selects one named company pair in B3; B4 / E4 populate automatically. H4 still selects Stored / Bloomberg and K4 the horizon; H5 / K5 are custom dates. Both price returns start at the first common observed session in the chosen window; spread is their difference in percentage points. The roster identifies both companies, codes, product overlap and key mix differences. Seven weak cross-industry / value-chain comparisons were replaced with camera-module, passenger-car, China residential-property, beer, electricity-utility / generation and innovative-medicine comparisons. There are still 35 pairs / 66 saved stocks, now with 72,134 stored price observations. Selection is an analytical judgement about product overlap, not issuer endorsement or a hedge-ratio claim. Primary product sources for additions and exclusions remain in data/peer_pairs.json; keep mix differences visible. Seven new histories were downloaded sequentially only through 2 October, retaining provider URLs in data/peer_price_cache.

HTML uses the same named roster; manual A / B code boxes are removed. Custom dates appear only for Custom horizon. The selected pair has two side-by-side charts and three return/spread figures. Excel also uses side-by-side native charts with actual date axes, no point markers and muted blue / burgundy strokes. Stored remains the opening source. The prior entry's independent-code controls are superseded by the user's pair-first request.

Screener / Comps Lab charts use a larger two-column grid, sparse numeric axes and restrained strokes / fills. A/H company selection focuses on one chosen comp at a time, preserving all six panels and the separate A/H comparison view. Missing sparkline values now break the path rather than joining across absent horizons. Screener's native Bloomberg price chart uses a true date axis.

The full Artifact peer-model rebuild reached the existing 384 MiB cap and stopped; do not raise the cap. create_market_template.mjs --peers now authors/recalculates two real sessions per stock, exports, then runs the standard-library restore_peer_history_ranges.py to restore full metadata / native formula ranges before production assembly. patch_peer_workbook.py appends the actual histories and chart caches within the Python cap. Do not ship the intermediate two-session bindings. test_peer_horizons.py evaluates all 35 pair selections, missing sessions, common rebasing and every horizon using stored / simulated Bloomberg inputs. Live execution remains a Bloomberg-terminal check.

## 13 October 2026 — presentation, live BQL and CSI reference

Lock-up now has a restrained Arial / navy-grey layout, aligned event and comparison charts, concise labels and reactive red/green return figures. IPO dates, filed source links, +/-30 HK trading sessions, all 396 events and source comments remain. Only the selected warning is shown; routine explanations were removed. Table XML names must match the revised visible headers. The saved comparison chart had empty category caches; cache the actual -30..+30 labels from Lock Compare so previewers do not collapse the curves into a vertical line.

HTML A/H uses the same six-panel renderer as Screener. Listing-to-snapshot is the default; 3M remains available. An A-share / CSI 300 price-index panel covers 31 calendar days either side of H listing, rebased on the first common actual session. Pre-IPO A / CSI returns and their percentage-point difference use the same dates. CSI is context, not a beta-adjusted attribution. Of 68 pairs, 65 have pre-H-IPO A prices; 2315, 9969 and 9995 listed their A shares later. data/csi300_prices.json retains provider URLs, methodology and retrieval time; data/ah_reference.json retains exact common dates. Stored prices end 2 October 2026. Native Excel follows AH!E4 for the CSI panel; Bloomberg requests SHSZ300 Index and the selected A counter, with explicit dates, ascending trading-day output and the same raw-price adjustment flags as the main A/H history.

The full-history review added A-share entitlement dates for 6127, 6821, 6680, 2402, 2691, 9980 and 2768. Nine pairs now have reviewed event schedules, including three events for 6127. Retain raw A/H quotes for the premium. Omit periods in which the two quote dates carry different bonus entitlements. The performance panes compound eligible-holder share ratios on each leg’s own ex date, excluding cash dividends. Native AH / AH Compare guards support three events. A sources are retained in data/ah_entitlement_reviews.json; the Nanhua SSE endpoint returned an anti-bot page, so its full issuer announcement mirror is identified explicitly. H ex dates for the new reviews match the retained split series, and must not be described as independently primary-file verified. data/batches/ah_chart_review_20261013.json retains exact missing/mismatched dates and premium/no-lookahead checks. Missing data stays missing. Reference premium markers use the actual A reference date, not an invented lead-in date.

Database BJ (current P/E), BL (current P/S), BBG Verify J/S and current Screener values now use the user’s exact two-argument BQL TTM expressions. Historical IPO multiples remain historical. The selected Screener A/H panel adds NTM P/E and FY2027 P/E / P/S. Hidden Valuation Data separates raw requests from scalar extraction, preserving headers and IDs. Eight-row response zones avoid collisions; numeric scalar / one-row replies and up to two header rows are supported. Negative and zero values remain numeric. Missing / rejected responses show Unavailable with no stale IPO fallback. Estimates are selected-company requests only, limiting Bloomberg load. This Mac has no Bloomberg terminal; tests validate expressions, bindings and simulated responses, not live execution.

Use tools/create_presentation_template.mjs for the small Artifact-authored layout. patch_presentation_workbook.py applies it to a freshly built workbook or the immutable baseline, never to an already patched file. It preserves unsupported native objects and all unrelated core sheet bytes. data/presentation_template.json, ah_reference.json and csi300_prices.json and both native patch modules are packed in the standalone bundle. Artifact string cells may be type=str; the graft must preserve those values. Keep drawing IDs unique and date-axis child order valid.

Validation: 68 native benchmark selectors; headered / unheadered BDH fixtures and missing dates; scalar BQL fixtures; all 68 HTML A/H selectors, 65 CSI windows, 396 HTML expiry schedules; multi-stock / peer integration; streaming numeric / source parity, native relationships / styles / merges / table headers / dropdown limits. Small native projections render actual shipped caches without loading the entire workbook twice. Python remains capped at 512 MiB, Node 384 MiB; only one headless browser at a time, renderer JS capped at 128 MiB. Do not open Excel to execute Bloomberg formulas on this Mac.

## 13 October 2026 — Excel repair and selectable peer horizons

Native Excel confirmed a content-repair warning. Seven inline dropdown lists exceeded Excel’s 255-character limit (A/H comparison codes and lock-up comparison codes). They now reference hidden ranges; the corrected test copy opened without recovery. Validate inline list length on every release, including charts’ comparison selectors.

A/H opens in Stored mode through 2 October. E4 = Bloomberg requests live A/H/FX quotes and listing-to-TODAY histories. The banner states the active mode. The seven-year roster remains 68 pairs; the underlying database and screener remain 524 IPOs.

Peer Trades: B4 / E4 are independent HK codes, H4 is Stored / Bloomberg, K4 is 1M / 3M / 6M / 1Y / 3Y / 5Y / Max / Custom. H5 / K5 specify custom dates. Max and custom requests have a ten-year chart capacity. Bloomberg accepts codes outside the IPO database and saved watchlist. The HKEX catalog contains 2,832 equity / REIT counters; 66 stocks have saved histories supporting 35 preset comparisons. HTML accepts any saved-stock combination and shows a clear message where no snapshot exists; it cannot call Bloomberg.

Both returns rebase at the first common observed session within the chosen calendar horizon; spread = 100 × (A return − B return), in percentage points. No interpolation over missing stock prices. Quotes show each counter’s currency and individual stored quote date. Stored daily changes use each stock’s own last two observed closes. The display states actual common coverage, including recent listings / stale snapshots.

Use tools/create_market_template.mjs --peers to author the small peer layout. data/peer_views_template.json is required in standalone bundles. Keep long code lists range-backed. tools/test_peer_horizons.py tests the shipped scalar formula logic with deliberately missing sessions and headered Bloomberg fixtures; those responses are simulated. Real Bloomberg add-in execution remains a terminal check.

Resource constraint: do one heavy operation at a time. Full regeneration hit the 512 MB cap; patch_peer_workbook.py grafts the Artifact-authored layout into the existing file with less than 512 MB peak memory and preserves unrelated sheet parts. A/H helper capacity is 2,200 rows (largest stored history: 1,683); peer capacity is 3,000 rows. Audit readers stream the workbook; the screener test uses a 20-deal fixture covering A/H, shared cornerstones and multiple subsectors, evaluates the visible Screener / required scoring outputs, and releases dispatch graphs between input cases. Full-record numeric and formula-binding audits remain in place. Avoid loading the full workbook twice merely to create screenshots. Verified public filing page caches may be regenerated from the retained source-URL / SHA manifest; audit evidence remains in data/batches.

# HK IPO Database — MAINTENANCE RUNBOOK

Written for two readers: the analyst (Kenny, on the Nomura desk) and a future
AI session on this Mac that is asked to "update the database". Everything a
refresh needs to know lives here. **Patch, never rebuild** — the data caches in
`data/batches/` and `scrape/` are weeks of accumulated work.

## 11 October 2026: code discovery, cornerstone grouping, compact delivery

This revision preserves all 524 canonical IPOs, price histories and numeric
fields. Nayuki 2150's CUAM name was concatenated twice in a vendor parse; its
filed legal name is restored once, with PDF p.339 / printed p.329 evidence in
cornerstone_name_corrections.json. All other investor rosters are retained.
Price observations still end 2 October; the database
snapshot is 7 October. Do not describe this offline HTML as live or current.

Red Avenue is already recorded as the official short name **RA MATERIALS,
9607**. HTML searches the H code and full issuer name. Excel Screener B5
accepts a name or H code and resolves it once through the SelectedDeal named
range, backed by Calc AQ:AR. Match code exactly and retain leading-zero aliases.
When migrating B5 references use a bounded expression: naive string replacement
also corrupts Database B5:B528 into an invalid range. All 524 name/code choices
were compared using the delivered resolver and target formulas.

The HTML now gzip-compresses its complete JSON payload and embeds the pinned
fflate 0.8.3 decoder plus MIT license. assets/fflate.min.js and its license must
travel in hk_ipo.py. Keep the ipo-payload DOM script after initialization: browser
Save As/content export needs it to reopen offline. A browser-save round trip and
zero-network-request check passed. This reduces the HTML from 5.48 MB to about
1.77 MB without dropping charts/history. A ZIP copy is an optional transfer
format; a full shared-drive quota still needs free space or a local destination.

Pipeline retains all 30 fields, with the 12 main fields first. M:AD expands the
investor, bank, A-line and note details. Data still starts at row 6, and Screener
mirror columns must be derived from PIPE_COLS. data/pipeline_layout.json comes
from tools/create_pipeline_layout.mjs using Artifact Tool; apply_pipeline_layout
grafts its styles while preserving native data, formulas and validation. New
rows use the same stripe styles; the application queue shifts with row count.

The visible Lock-up views now contain only the 396 actual cornerstone events
for 386 companies. Keep all 1,064 filed/reviewed restriction records in the
internal batch; founder/controlling-holder restrictions and no-cornerstone
placeholders are excluded only from these desk views. The company-cornerstone
column shows its complete roster; multiple expiry events can apply to subsets,
so the linked event filing is the authority for the actual restriction. There
are 156 events whose expiry is not established by the retained evidence. Label
them Expiry unconfirmed and leave dates, returns and charts blank. Never infer
six months. Both returns continue to use seven HK trading sessions, with day 0
the last traded session on/before the last locked day. All 396 event selectors,
386 Auto choices and 2,618 graph observations were exercised in Artifact Tool.

Cornerstone keys changed for 143 stocks after correcting unrelated groups that
shared generic/city prefixes. Use explicit documented aliases for MLP/Millennium,
Hillhouse/HHLR, JPMAM, ADIA and E Fund. Preserve separately named legal
subscribers in the company roster. Do not fuzzy-fold CS League keys by a prefix,
city, surname, PT, ICBC or CITIC. Each investor group counts a company once.
Every one of 1,146 league groups was reconciled across Excel/HTML, including hit
rate denominators and all seven return averages. A code query in HTML
Cornerstones overrides the minimum-deal count, exposing the complete roster.
The full filing-name audit was rerun. Short full names now require a complete
word-bounded spelling on a cornerstone page, rather than being discarded by
the old >8-character rule; 119 investor aliases remain unconfirmed and are
retained in the internal review CSV. Numeric source confidence is unchanged.

AH still covers all 62 identified A/H pairs in this IPO sample, not the entire
market universe. All database codes present in ah_universe have their A code.
Ingenic 3223 / 300223.SZ is an additional documented mapping outside that cache.
Huaqin 3296's previous blanket Class ratio review came from its first-month
H capitalisation. Primary filings now establish the same 4-for-10 capitalization
on both classes, with H ex-date 22 May and A ex-date 17 June. Store evidence in
data/ah_entitlement_reviews.json. ah_basis.py enables IPO/latest premiums once
the quote bases match, while the chart omits mismatched H/A observation bases
(22 May through 16 June, or a carried pre-ex A quote after 17 June). Raw histories
are preserved. Stored and Bloomberg share the date rule; unknown/new actions
invalidate the exception. Keep the first-month research correlation exclusion:
the study's affected month-end remains outside comparable raw share units.

Checks: ipo.py check; tools/test_cornerstone_names.py;
tools/test_deliverable_review.py; tools/test_shared_drive_review.py;
tools/test_search_excel.mjs; tools/test_lockup_excel.mjs;
tools/test_lockup_refresh.py; tools/test_monitors.py;
tools/test_ah_dashboard.py. Native Microsoft Excel opened without repair and
rendered the Pipeline and Lock-up chart. This Mac is View Only and has no
Bloomberg add-in: external BDP/BDH execution remains a desk validation.
Do not deliver temporary fixture workbooks or render probes. Do not delete the
TO_NOMURA directory during export; preserve separately prepared Word research.

## 6 October 2026 revision: simplified monitors and consolidated Technology

7 October follow-up: Screener and Database restore the original navy headers,
dark section bands and pale blue inputs. Signed returns use subdued red/green
shading and magnitude bars use muted blue. The Artifact-authored colour
template is data/desk_colours.json; apply_desk_styles.py applies it after the
native builder saves, preserving all formulas and unrelated sheets. This step
also saves a truthful default A/H snapshot chart cache, so the curve and its
dated cutoff are visible on first open without Bloomberg. Its dynamic names
and formulas remain live. Premium now is never filled with a saved quote.
The A/H premium headers are wider to accommodate the filter buttons. The
standalone desk bundle includes the colour template and postprocessor.

Visual QA also caught Screener D12 replacing an exact pipeline listing date
stored as ISO text with TODAY(). The effective-date formula now parses that
text date, retaining the existing typed override and real-date behavior.

The current layout supersedes the source-mode controls described in older
notes. IPO Live has five visible columns: Bloomberg H ticker, company, sector,
live price and daily change. LAST_PRICE supplies the current price and
PX_YEST_CLOSE supplies the previous trading-day close. Change is current /
previous close minus one. The sector table and bar chart use equal-weight
averages of available numeric changes; missing quotes are excluded and the
quote count is shown. There is no saved-price substitution in this table.

AH has six visible columns: A code, H code, sector, subsector, premium at IPO
and premium now. B4 accepts an H or A code. Its single native chart uses each
pair's own H-traded dates from H listing through TODAY, with A and FX aligned
on or before each H date. The latest complete quote is appended to today when
the daily series ends earlier. Prior A/FX carry is capped at 10/5 calendar days.
Raw dated BDH output occupies three separate empty blocks on hidden Live
History. If the native H output is unavailable, stale or fails the raw debut
price/date check, the chart uses the dated cached history and explicitly labels
its actual cutoff. It must never label a saved October 2 series as live today.
Huaqin's premium remains withheld pending share-class ratio validation.

Both BBG verification tabs use direct single-date BDH, matching the user's
terminal-confirmed four-argument formula. There is no INDEX/MATCH around BDH.
The Database's optional Bloomberg fallback marks unavailable responses as
Awaiting Bloomberg; otherwise an add-in error can poison the offline screener
score range. The verification sheet itself retains the raw external result.
Date cells are typed Excel dates; HK security codes use their integer value.
Do not restore N(text-code), which yields zero. Bloomberg API transport and
desk entitlements cannot be tested on this Mac. Fixture calculation verifies
the dependent maths, not the external Bloomberg response.

Technology is consolidated into six business groups: Semiconductors;
Software & AI; Internet & fintech; Hardware & electronics; Robotics &
autonomous driving; Data centres & cloud. Both historical and pipeline labels,
classification rules, the Taxonomy sheet and both screeners use these same
labels. Existing return benchmark assignments are preserved. Screener freezes
columns A:B only (C1); no row is frozen. Other tabs retain the neutral palette.

The HTML A/H table retains all 62 pairs, including missing/review cases. Click
a company or select it in the Company dropdown for its complete cached history.
The comparison chart includes every available premium in the chosen slice.
Cached observation dates are shown; HTML is an offline snapshot.

Run tools/test_monitors.py after changing either monitor. It executes the
delivered formulas with simulated quotes, exercises code selection, daily
returns, sector averages, headered histories, holiday alignment, no look-ahead,
wrong/stale output rejection and the live TODAY endpoint. Do not deliver the
temporary visual probes or fixture values.

## Earlier 6 October build: superseded monitor layout

**IPO Live** is the first tab. It shows all 524 IPO H lines, grouped by sector,
with live H price, one-day change versus the previous trading-day close,
quote date/time and source. `B5` filters sector or A/H only. Available A prices
and A premiums appear independently; missing A/FX does not suppress H prices.
**AH** is second and contains only the 62 actual A/H pairs in this database.
`B5` accepts an H code (3986, 0501 or numeric 501) or A code (603986.SS).
Unknown codes clear the trend. `I5` filters sectors. Screener has no frozen rows.

Each monitor's `M5` independently controls Bloomberg / Auto / Snapshot.
Default Bloomberg never substitutes saved closes. Auto may use a complete,
labelled dated snapshot; Snapshot is explicit historical mode. The cache ends
2 October, with Mainland closes often 30 September. `PX_LAST` pulls prices;
`CHG_PCT_1D / 100` pulls daily changes. Source dates and quote times are shown.

AH's two editable charts request raw BDH history from H listing through TODAY.
Three reserved two-column output blocks feed scalar date-aligned calculations.
Headers are tolerated. A/FX begin 31 calendar days earlier for holiday carry;
maximum prior-close carry is 10/5 days, with no future observations. A complete
current quote is appended when daily history ends before today. Invalid,
stale, wrong-debut or incomplete Bloomberg output does not become a chart.
Default Bloomberg has no cached snapshot chart. The dynamic chart range uses
a calendar date axis with monthly labels; gaps reflect unavailable or unverified observations.

Bloomberg equity history explicitly requests no cash/capital adjustments.
Date/time fields, daily change and adjustment flags still require a terminal
test. This Mac has no Bloomberg add-in: fixture computation is not native
Bloomberg proof. Native Excel can be used to inspect file compatibility only.

Both Bloomberg verification sheets now construct H tickers with `VALUE`, not
`N`: Excel `N(text)` returns zero. Single-date BDH checks extract the requested
row and the price column with `INDEX/MATCH`, instead of `@` implicit
intersection. Relevant date cells are real Excel dates. A-company Bloomberg
`CUR_MKT_CAP` is already millions; the screener's erroneous extra division by
1,000,000 and hard-coded FX fallback have been removed. Native Bloomberg
execution remains a desk check.

**AH_Premium_Study.docx** (Word, outside Excel) includes every pair and a 60-case first-month sample. First month
means 21 H-traded sessions AFTER Day 1. Offer reference, Day 1 and first month
are distinct. Offer reference uses A/FX closes before H debut, not book pricing
time. BIOCYTOGEN has no A listing at H debut; HUAQIN has a first-month share
scale event requiring class-ratio validation. Both are explicitly excluded.
35/60 absolute gaps narrowed. GigaDevice: 32.2% Day 1 to 8.7% after one month,
mainly H gains. Montage: 11.6% to -4.9%, mainly A declines. Deal-size Spearman
rho is -0.182, with 95% interval spanning zero. Six exploratory correlations
include bootstrap intervals and adjusted permutation p-values. Current cap
has look-ahead bias. The listing cap revalued at the pre-debut A reference
inherits the database's company-share basis; neither proxy is A-only float
cap. Do not turn these weak associations into causal conclusions.

New study sources and all dated observations live in `data/batches/ah_study.json`
and `data/ah_study_cache/`. `analyse_ah_study.py` refresh merges new history into
old cache rows, preserving debut data beyond the provider's rolling window.
`ipo.py refresh` and the desk bundle include the study after merge. `make_ah_study.py` regenerates the Word study during export; `ipo.py ah-study-note`
is its standalone command. Markdown is an internal research intermediate, not
a delivered workbook tab. Export copies the regenerated Word into TO_NOMURA.

Taxonomy v2 splits 27 semiconductor IPOs into compute/AI, memory/interface,
analog/power, image/display, equipment/materials, foundry, and diversified
businesses. Broad sectors remain unchanged. Manual and fallback classifiers,
pipeline normalisation, HTML and workbook use the same labels. Legal regimes
and profitability remain separate. Peer-boundary notes explain mixed names.

`build_market_views.py` loads the small Artifact Tool-authored layout from
`data/market_views_template.json`; normal desk builds still need only openpyxl.
Node/Artifact Tool are design-time tools. `make_bundle.py` embeds the template,
study, histories and support modules; it updates extracted module versions
when a newer bundle is installed. Do not omit them from the single-file build.
Backend/SizeBench/Verification sheets are hidden and support checks are at the
back. Right-click a sheet tab and Unhide to inspect them. Existing return,
grey-market, sponsor and cornerstone records have been preserved.

Validation: all nine existing gates passed; semiconductor screener probes
compute every revised peer group and an override; monitor probes compute
H/A-code switches, invalid codes, quote-source modes and sector counts with
simulated Bloomberg responses; chart probes check headers, holiday carry,
FX alignment, rebasing and dynamic native chart references. Workbook sheet
layouts were rendered in a disposable preview, separate from native formula
execution. A clean single-file build is required before delivery.

## The two machines

| | This Mac (build machine) | Nomura desk |
|---|---|---|
| Full refresh incl. AAStocks/Tencent/playwright | ✅ | ❌ (no playwright; some sites blocked) |
| Scripted refresh (HKEX, Yahoo, Tencent) | ✅ | ✅ `%run hk_ipo.py refresh` |
| Rebuild .xlsx / .html / .ipynb | ✅ `python ipo.py build` | ✅ `%run hk_ipo.py build` |
| Bloomberg columns compute | ❌ | ✅ (BBG Verify tab, BDH/BDP) |
| AI relabelling (subsectors, press sizes) | ✅ (an AI session) | ❌ |

## Update cadence

**Weekly (desk or Mac):** `refresh` → `build`. That is all. Every stage is
resumable and staleness-aware:
- new allotment filings arrive → new deals appear end-to-end (roster → filings
  → parse → merge);
- a PHIP that has LISTED graduates out of the Pipeline automatically (it enters
  the listed roster; the pipeline dedupes by company identity, including full-name aliases);
- young deals' 1w/1m/3m fill in as their windows elapse, and `since IPO`
  refreshes, because `fetch_prices.py` re-fetches any cached code whose
  last quote/check is behind the latest completed HSI session, whose benchmark changed, or whose elapsed horizon is still blank
  (the `stale()` rule — do not remove it);
- stabilisation outcomes resolve as END-OF-STABILISATION notices get filed
  (only unresolved deals are re-searched).

**Monthly (Mac, ~30-60 min):** the enrichment stages that need playwright /
unblocked networks, then re-export to the desk:
```
python ipo.py refresh              # includes aastocks-deal + planned + prices
python ipo_lib/fetch_aastocks.py financials   # P&L for any NEW no-NI deals
python ipo_lib/fetch_ah_paths.py   # extends young A/H pairs toward day 92
python ipo_lib/audit_returns.py    # independent recompute; investigate any mismatch
python ipo.py export               # regenerates TO_NOMURA/ (5 files)
```
Carry `TO_NOMURA/` to `G:\FIN_COMM\DeltaOne\Kenny\ECM\`.

**When a new PHIP appears (needs an AI session):**
1. `refresh` already parsed it (financials, A-share venue, OC-announcement
   banks) and gave it a PROVISIONAL keyword subsector (amber, ~49% exact).
2. Ask Claude to: confirm/fix the subsector in `PIPELINE_LABELS`
   (`ipo_lib/fetch_phip.py`) — the analyst-label override map;
3. and refresh `data/batches/press_sizes.json` (expected size + source +
   confidence) — sizes there are ESTIMATES and are always displayed with their
   basis; empty is better than invented.

**When a pipeline deal LISTS:** nothing manual. Next refresh pulls its
allotment filing; it enters the Database with the full column set; the
first-word dedupe drops it from the Pipeline tab. Hand it a proper subsector in
`ipo_lib/classify.py` (`GROUPS`) at the next AI session — until then it wears
the amber keyword label.

## THE ROUTINE — run this whenever asked to "update everything" (v12)

The one sequence that graduates listed pipeline deals into the Database, pulls
any new pipeline, refreshes every return, and checks itself. Order matters.

```
# 1. everything HKEX + AAStocks + PHIP + offering-window prospectuses
python ipo.py refresh
#   If the machine is evicting the PDF cache (ls -lO scrape/pdf_cache | grep -c
#   dataless), skip the parse group and run the extractors incrementally on the
#   new codes instead — see v29:  python ipo.py refresh --skip parse

# 2. prices (returns incl. ex-pop family), daily H paths, A/H daily paths
#    fetch_prices reads deals.json, so a BRAND-NEW listing needs merge -> prices
#    -> merge again, or its day-1 comes off the AAStocks table (see v29)
python ipo_lib/fetch_prices.py
python ipo_lib/fetch_h_paths.py
python ipo_lib/fetch_ah_paths.py

# 3. canonical merge (consumes bbg_desk + press_figures too)
python ipo_lib/merge_batches.py

# 4. THE GATE BATTERY — one command, and export refuses while any gate is red
python ipo.py check
#   = coverage floors + data identities/explained blanks + PRICES & RETURNS
#     (every deal, three ways) + formula bindings + Bloomberg lint +
#     Excel-computes parity + the visual gate (label overlaps, hidden scroll,
#     NaN, tooltip-less truncation — light AND dark).
# If prices were refetched, run the corporate-action sweep first — it is a
# refresh stage but worth knowing by name:
python ipo_lib/detect_splits.py     # writes data/auto_splits.json
# Monthly extras (network-heavy, not in the battery):
python ipo_lib/audit_returns.py              # independent recompute of returns
python ipo_lib/audit_opens.py 8 --horizons   # two-source day-1+1w/1m/3m (1/8 sample; full monthly)

# 5. rebuild + ship
python ipo.py export                         # TO_NOMURA/ → G:\FIN_COMM\DeltaOne\Kenny\ECM\

# 6. publish the two viewable files to GitHub (github.com/kennytam-code/code)
#    — TO_NOMURA/ is gitignored EXCEPT these two (whitelisted in _ipo_db/.gitignore)
git add _ipo_db/.gitignore _ipo_db/TO_NOMURA/HK_IPO_Database_v1.xlsx _ipo_db/TO_NOMURA/hk_ipo_dashboard.html
git commit -m "HK IPO database: refresh"
git push origin main
```

What to eyeball after: the Pipeline tab holds only unlisted names; the newest
listings show day-1 but blank 1m/3m (windows not elapsed — correct); checks.py
prints `0 failures`; the parity test prints `subsec gate … [OK]`.

**Bloomberg desk paste (bbg.xlsx):** on the terminal, open the workbook's BBG
Verify tab, let the BDP/BDH formulas resolve, paste-values into `bbg.xlsx`
(one sheet, headers on row 4 — the ingest reads columns by position), drop it
at `REPO/code/bbg.xlsx`, then `python ipo_lib/ingest_bbg.py` and re-merge.
Retail/instl subscription OVERRIDE the scrape (CP036/CP037 are the record);
`Mkt cap at listing (BBG)` is deliberately ignored — that desk formula is
wrong. P/E-at-listing lands in its own column beside the scraped multiple.

**`press_figures.json` is research, not scrape** — hand-verified numbers with
sources for rows no machine can read. Append to it; never regenerate it.

## v13 — what changed, and what the desk can now do alone

**One command on the Nomura machine.** `%run hk_ipo.py update` runs the whole
chain — fetch → parse → prices → chart batches → merge → gates → rebuild both
files — and ends with a VERDICT block that says plainly whether the output can
be trusted. Skip any blocked group and it still finishes on what it can reach:
`%run hk_ipo.py update --skip aastocks`. Verified end-to-end from a clean
folder: the desk's `data/deals.json` came out **cell-for-cell identical** to the
Mac's, and both output files rebuilt.

Bugs this exposed and fixed (all of them would have bitten on the desk):
- **`build` could delete everything.** `_unpack()` returns the SCRIPT'S OWN
  folder once `data/` exists beside it, and both build paths then called
  `shutil.rmtree(datadir)`. Running `build` a second time would have wiped
  hk_ipo.py, the data and both outputs. Every rmtree is now guarded with
  `if Path(datadir).resolve() != BUNDLE_ROOT`.
- **The bundle ran fewer stages than the Mac** — no offering-window prospectus
  parse, no A-premium-at-IPO leg, no chart batches. `audit_formulas.py` now
  fails if the two STAGES lists diverge (playwright-only `aastocks-deal`
  excepted), so this cannot drift again.
- **`ipo.py refresh` itself never ran the chart batches** — h-paths/ah-paths were
  hand-run. They are stages now.
- **merge crashed with a TypeError** when a base batch was missing; it now says
  which file, and what to run.
- **merge could not import its own helpers** on the desk (`clean_names`): the
  unpacked lib dir was not on `sys.path`.
- The bundle embeds **40 data files** (was 10) — every batch merge consumes — so
  a desk with NO network can still re-merge after a Bloomberg paste and rebuild.

**What still needs this Mac (be honest about it):**
- `aastocks-deal` (sponsors, full syndicate, market cap at listing, the
  institutional book) needs playwright. Without it those columns simply keep
  their last values; nothing breaks.
- Hand-labelled subsectors (`classify.py`) and `press_sizes.json` /
  `press_figures.json` are research, not scraping. New deals get a provisional
  keyword subsector (amber) until someone labels them.
- If HKEX/AAStocks/Yahoo/Tencent are blocked at the bank, those stages fail
  LOUDLY and the previous data stays. The files remain usable and correctly
  dated; they just do not gain that stage's update.

## v14 — real opens everywhere, open-to-open charts, amber means judgment

- **Tencent kline row[1] IS the open** — v13 threw it away and then had to
  withhold "Day-1 open→close" for every Tencent-sourced deal. `tencent_kline`
  now returns (date, close, open); the split-fix and no-Yahoo branches build
  real Open columns; `fetch_ah_paths` stores each pair's `h_open0`/`a_open0`;
  `fetch_h_paths` stores `open0`. Coverage: day-1 open pop and open→close are
  511/511. OmniVision cross-check: open 108.0 vs offer 104.8 = +3.05% pop.
- **Open-to-open convention (charts)**: every EX-POP panel rebases BOTH legs on
  their own day-0 opening print (A's open converted at the day-0 FX recovered
  from the series itself), and the premium-at-the-opens overlay uses
  (A open × FX) ÷ H open on day 0. The at-IPO premium panel starts at the level
  struck at pricing via the @offer lead-in dot.
- **A-share pane spans the listing**: month before → month after, split by the
  "H LISTS" rule, headline carries both legs (+17.0% → +29.6% style).
- **Scoring engine is text-proof**: Bloomberg-fallback TEXT in pe/size cells
  scores 0 via N() instead of poisoning LOG10 with #VALUE! (this broke the comp
  table for ANY target that carried a P/E — the parity fixture never had one,
  so the new "P/E target" probe in test_screener_formulas re-solves with
  C13=30 and asserts zero error cells). The A-share filter tests
  `is_h_share="Y"`, not `a_share_code<>""` — the fallback text made every deal
  count as an A/H pair.
- **Comp table adds**: "HSAHP @IPO" (Hang Seng AH Premium index on the listing
  day, BBG Verify col R → Database mirror `_hsahp_bbg`, desk-live BDH) sits
  next to IPO date; "Day-1 O→C" joins the return block. Probe letters in the
  parity test are now COMPUTED from COMP_COLS — never hardcode them again.
- **BBG Verify mktcap**: CUR_MKT_CAP arrives already in millions — the /1e6 is
  gone (desk-verified formula).
- **Amber now means judgment/soft-parse only** (3,122 → ~1,600 cells):
  deterministic derivations (NI sign, mktcap÷NI, stated caps, fixed-price caps)
  are plain "single"; 191 heuristic listing dates were auto-VERIFIED against
  the first traded bar (the exchange's own record) and turned green; the ~35
  that disagree stay amber on purpose — the bar date is probably righter than
  the heuristic. What stays amber: single-source PDF financials, prose-parsed
  subscriptions, amount-derived cornerstone %, keyword subsectors.
- **Explorer colour modes are all real** (sector / year / A-H / size bucket /
  up-down) with a live legend; the cornerstone cell's expander is one "+N all ▾"
  chip (the old grey +N doubled it into "+23+23").

## v15 — sources named, the screener mirrors the Database, new PHIP flow proven

- **What "Tencent" is**: web.ifzq.gtimg.cn/appstock/app/fqkline/get — the public
  market-data API behind gu.qq.com (Tencent Finance, one of mainland China's
  largest retail quote services). Its bare `day` series is RAW exchange prints,
  no split adjustment — the right series to compare against an offer price.
  `audit_opens.py` now cross-checks day-1 OPEN and CLOSE for every deal against
  Yahoo (fresh pulls, no cache) and classifies every row: agree ±0.5% /
  split-adjusted-Yahoo (disagreement EXPECTED, raw is the record) / Yahoo-blind
  recycled codes / UNEXPLAINED (gate fails if any). Graph-level proof: SICC's
  eight pane numbers (h0/a0 opens+closes, day-1, open-pop, prem[0], open-prem)
  reproduce from fresh raw pulls with independent code, to the tick.
- **The comp table is now GENERATED from DB_COLS** ("the screener should have
  whatever we got in database"): same headers, formats, bands and widths as the
  Database, minus links/prose/identity-dupes (COMP_SKIP), plus the scoring
  block. A new Database column lands in the screener automatically, and
  audit_formulas checks both against the same source.
- **P/E blanks are now a closed list**: 193 loss-makers (n/m on BOTH sources —
  Bloomberg prints #N/A for them too, that is the field working, not failing),
  29 no-NI + BBG blank, 10 withheld by the plausibility gate (2 of which BBG
  "confirms" only at 1,597–2,073x — past the 1,000x ceiling, stays out), 7 no
  mktcap + BBG blank. Sane BBG values now PROMOTE into the main column with a
  basis note (270/511 filled).
- **lint_bbg.py** walks all ~5,700 Bloomberg formulas: parens/quotes balance,
  mnemonics against the desk-proven set (values that actually came back in
  bbg.xlsx), BDH dates anchored on the Database, IFERROR guards. It caught 123
  unguarded AH-tab BDP cells that printed #NAME? off-terminal — fixed.
  "HSAHP Index" is flagged AWAIT-VERIFY until one cell is confirmed on the desk.
- **New-PHIP flow, exercised for real**: Medcaptain Medical (PHIP 2026-08)
  arrived via `fetch_phip`, financials parsed (rev RMB1.78bn), hand-labelled
  "Medical devices" in PIPELINE_LABELS, now the 11th pipeline card everywhere.
  The fetch also caught a v14 REGRESSION: series_from's new 3-tuple broke the
  2-tuple unpacking in fetch_phip/fetch_newlistings — every PHIP financial
  parse was dying silently ("too many values to unpack"). Fixed both callers;
  when you change a shared helper's signature, grep EVERY caller.

- **The opens audit's first full run paid for itself**: 474 deals agree to
  ±0.5% on both open AND close; 10 are Yahoo-blind recycled codes (Tencent
  only); 26 disagree by exactly their split factor (the book already uses raw —
  expected); and ONE real error surfaced: REGO (2422) — Yahoo carries a hidden
  x1.194 capital-action adjustment WITH NO SPLIT ROW, so the split-guard never
  fired and the book's day-1 read +76.7% instead of the true +110.9%. Fixed,
  and generalised: `data/force_raw_codes.json` — the audit auto-appends any
  uniform-factor code, `fetch_prices` force-drops Yahoo for codes on the list,
  and the list ships in the desk bundle.

## v16 — visibility as a gate, horizons in the audit

- **"Visible" now has a machine definition and a scanner**: no element may hide
  content behind a horizontal scroller, and no text may ellipsize without BOTH
  a hover tooltip and (where it matters) a click-through. The clip-scanner
  found the A/H pane row hiding two panes behind 380px of scroll on every
  screen — the six panes are now a 3×2 grid, all visible, taller. The deal
  table was 242px wider than the viewport: P/S dropped (it lives in the
  screener), subsector display names shortened with the full name on hover
  ("Smart hw / cons. elec."), dates compacted to yy-mm-dd with full date on
  hover, cornerstone cell shows the TOP HOLDER + "+N all ▾". The table now
  fits 1440 with zero hidden pixels. Excel: all headers wrap inside their
  30px header row — zero truncations.
- **audit_opens --horizons** extends the two-source check to the 1w/1m/3m
  closes (offsets 5/21/63) — the REGO class of hidden adjustment is now
  screened across the whole first three months, and uniform-factor codes
  auto-join force_raw_codes.json.

## v17 — the review IS the battery now

"Check everything again" is a command, not a conversation:
`python ipo.py check` runs the six gates and `python ipo.py export` REFUSES
while any is red (`--force` exists and announces itself). Every gate began as
a manual check that caught a real error: coverage floors, arithmetic
identities + the explained-absence contract, formula-binding audit (the c_sub
class), Bloomberg lint (the 123 unguarded AH cells), Excel-computes parity
(the P/E-target probe), and the visual gate (the hidden A/H panes, the CATL
label collision — light and dark). audit_visual skips gracefully where
playwright is absent, so the desk bundle can run the battery too.

Tidiness rules locked in this pass: the Analogs machine keys live in a HIDDEN
helper column (a visible wall of "Biotech 18A|10-100x" is clutter, and the
lookups follow the defined names); stale change-notes do not belong in UI copy
("P/E proximity now outranks profitability" said nothing to a first-time
reader); the peer-median day-1 tile is the PRIMARY tile, and Day-1/1-month are
key-columns in the comp table — the numbers a position is sized off carry the
visual weight.

## v18 — every orange adjudicated; the brief reads like a trade

- **Zero conflict-orange cells.** Every source disagreement is now RESOLVED by
  evidence, three ways: (1) quality adjudication — a clean researched list
  beats a damaged-table parse ("Subtotal", "upon Listing Top", address bleed
  all score as garbage; the research batch also stored its lists as STRINGS,
  which lost every comparison until coerced); (2) cross-check repair — a
  cornerstone % that fails the AAStocks-institutional-total check by 20pp+ is
  a placing-table bleed, REPLACED by the filed aggregate amount (CALB 93%→58.7%,
  MTT 100%→24.8%); a cap below the struck price is popped, not shown;
  (3) hand rulings in data/batches/conflict_rulings.json (append-only, carries
  the reason; supports value overrides — GigaDevice's SPV names swapped for the
  press-corroborated managers). cornerstone_n is now derived from the final
  list, never merged. A Bloomberg/press winner marks the cell RESOLVED, and a
  later low-rank disagreement can no longer repaint an authoritative winner.
- **Deal Brief = the four medians a position is sized off**: DAY-1 POP
  (primary tile) then 1-week / 1-month / 3-month EX-POP, coloured by sign,
  plus the base rate and the worst-peer downside. Shared CS appears in the
  top-5 table only when a comp actually shares an investor.
- Lesson recorded: an inserted helper landed at column 0 INSIDE main() and
  silently ended the function — the merge "ran" green while skipping half its
  body. After structural edits, assert the function's statement count/span
  (ast), not just that the file parses.

## Conventions the desk relies on (do not flip back)

- **A-premium, not H-discount** (v12): every premium in the book is
  `A over H − 1`, + = A trades above H. Columns: `A prem vs H at IPO`
  (A close the day before listing ÷ H offer − 1) and `A premium (today)`.
  The AH tab's live formula, the dashboard, the notebook and the screener all
  use this one direction. If a number looks flipped, check it is not being
  read as the old H/A convention.
- **The FX chain, end to end** (asked and verified 2026-08-21). Every A-leg is
  converted with the CNYHKD rate of ITS OWN session, never a flat 1.10:
  `a_close_cny x cnyhkd = a_close_hkd` (CATL: 260.00 x 1.0838 = HK$281.80), and
  the daily path multiplies each day's A close by that day's FX before forming
  the premium. The at-IPO anchor and the daily series therefore join exactly —
  verified by identity on all 59 pairs:
  `(1+prem[0]) == (1+prem@IPO) x (A0/A_prev) / (1+day1)`. The visible step at
  day 0 is the day-1 pop offset by the A line's own overnight move, nothing else.
  `a_premium_now` comes from a DIFFERENT source (the AAStocks snapshot, today)
  and legitimately differs from the daily series' last point (~day 92) — median
  14pp apart, because they are different dates, not different maths.
- **One field runs the other way, on purpose and labelled**: the pipeline's
  `h_cap_vs_a_pct` is H-cap over A (that is how an offering is quoted). Its
  A-over-H twin `a_prem_vs_hcap_pct` is derived beside it so the pipeline row is
  comparable with the Database's A-premium columns; the dashboard tile shows the
  A-over-H number and states the H-over-A read in its own label.
- **Ex-pop family** (v12): `1w/1m/3m ex-pop` start at the day-1 CLOSE;
  `Alpha 1m ex-pop` nets the index over the identical day-1-close window;
  `Day-1 open→close` is the intraday move after the opening print (withheld
  for Tencent-sourced series — a raw close line has no true open). Ex-pop
  columns wear TEAL headers; with-pop columns navy. The dashboard uses the
  same tint on chart backgrounds.
- **Tencent kline `n` must be ≤1500** — the endpoint answers 200-with-empty
  above that (it blanked an entire fetch on 2026-08-20). It also throttles
  bursts by answering empty; the helper retries with backoff, keep ≥0.6s
  sleeps in loops.
- **Extreme multiples**: >300x is withheld UNLESS Bloomberg independently
  prints the same level (±25%, and ≤1000x) — CALB's 549x is real and stays;
  DRCB's 9,514x "bank P/E" is a shared artifact and stays out.
- **`audit_formulas.py` is the guard against the class of bug that hid longest.**
  It resolves every `Database!$X$n` in the Screener and Calc sheets back to a
  FIELD NAME and compares it against what the cell's own header says it pulls,
  checks each per-deal formula references its own row, and asserts the card's
  labels still sit beside the cells the engine reads. Run it after any layout
  change; a moved row now fails loudly instead of silently ranking on the wrong
  column. Its inputs (`COMP_COLS` / `COMP_PULL`) are module-level in
  build_xlsx.py on purpose — one definition, shared by builder and auditor.
- **A silent fallback is a bug, not a safety net.** The split-correction (raw
  Tencent instead of Yahoo's split-adjusted line) failed quietly when the
  endpoint rejected `n=3000`, and 26 deals silently reverted to a 1,360% day-1.
  The engine now sets `split_uncorrected` + a loud `price_note` when the
  correction cannot be applied. If you ever see that flag, refetch — do not ship.
- **Charts vs columns, the two anchors**: chart panels labelled EX-POP rebase on
  the day-1 OPEN (what you could actually buy). The ex-pop COLUMNS keep the
  day-1-CLOSE basis (the standard aftermarket definition the index alpha is
  matched to). Both are stated on the panels and on the Notes tab.
- **The A-premium series starts at the level struck at pricing.** It is drawn as
  a dot at `@offer` LEFT of day 0 with a dashed lead-in, because stacking it at
  x=0 turned every line's drop into one vertical bar and crushed the scale.
- **Excel and HTML carry the same field set**, enforced by audit_formulas step 6.
  Adding a Database column without adding it to `build_dashboard.KEEP` (or vice
  versa) now fails the gate.
- **Two singleton subsectors are deliberate**: SF REIT and SANXUN (sole REIT,
  sole developer) can never fire the subsector gate — they fall back to
  sector scoring honestly rather than being force-paired.

## What each stage writes (ipo.py STAGES, in order)

| Stage | Output batch | Notes |
|---|---|---|
| roster-aastocks / roster-hkex | hkex_allotments.json | the deal universe (Allotment Results = every IPO) |
| filings-* / parse-* | prospectus/allotment parses | full-text caches in `scrape/text_cache/` |
| classify / classify-auto | subsectors | hand labels in classify.py ALWAYS win |
| pipeline-phip | phip_pipeline.json | PHIP parse + OC-announcement banks (PHIP covers redact them) |
| names-cn | names_cn.json | HKEX bilingual feeds |
| stabilisation | stabilization.json | end-of-stabilisation outcomes, resumable |
| aastocks-deal | aastocks_deal.json | 保薦人/包銷商/上市市值/機構性投資者 — playwright, Mac only |
| ah-snapshot | (premium today) | uncached by design |
| prices | prices.json | Yahoo + Tencent fallback; staleness-aware |
| ah-at-ipo | ah_ipo.json | A close before listing × CNYHKD, twice-sourced |
| merge | **data/deals.json** | THE canonical file; all adjudication rules live in merge_batches.py |

| offering-window | newlistings.json | www2 New Listings table; FULL prospectus parse of deals still open for subscription (expected P/E at range, cornerstone, timetable) — desk-safe |

Not in STAGES (run monthly on the Mac): `fetch_aastocks.py english` (EN names for
sponsors/underwriters/cornerstones — the DISPLAYED set), `fetch_aastocks.py financials`,
`fetch_aastocks.py planned`, `fetch_ah_paths.py` (incl. each pair's A-share month
BEFORE the H listing), `audit_returns.py`, and the A+H-universe diff
(ah_universe.json — proves no missed A-share codes).

## Gates — run before every export

```
python ipo_lib/checks.py                 # 0 failures required (floors inside)
python ipo_lib/test_screener_formulas.py # PARITY MATCH + 0 error cells required
```
The build itself refuses to save a workbook with unbalanced formulas.

## Known caveats (learned the hard way — keep them true)

- **Dashboard CSS: sticky belongs only to tables inside their own scroll
  container.** The generic `table.tbl th` was once viewport-sticky — the
  side-by-side matrix header detached from its columns and slid under the page
  nav. Only `.tbl.deals` (own scroll box) keeps a sticky header. And when two
  rules tie on specificity (`.labtbl thead th` vs `table.tbl th`), the LATER
  one in the sheet wins — the matrix header alignment rules are written as
  `table.labtbl thead th` so they out-rank the generic left-align regardless
  of order.
- **Helper ranges never share a sheet OR A COLUMN with anything else.** The
  cornerstone-split scratch once sat in Calc J1:J5 — the same column as the
  score — and silently killed every comp formula. Scratch lives in Calc T:Y.
- **Helper ranges never share a sheet with a growing table.** The screener
  pick-list lives on the Calc sheet (cols K:Q) because twice a widened table
  overwrote hidden helpers and silently corrupted everything to its right.
- Yahoo lies twice: it back-adjusts for splits (undo with the per-bar factor)
  and returns current quotes for codes it has no history for (the DEBUT_LAG
  guard + Tencent fallback exist for this — 0300/0501/0917 class).
- The PHIP cover REDACTS bank names; the same-day OC Announcement carries them.
- AAStocks 機構性投資者 is a SUPERSET of cornerstones (anchors included) — its
  total being larger than the prospectus % is expected, not a conflict.
- `oversub_intl_mult` values <1 on a deal priced at cap with a hot retail book
  are percentage-misreads: flagged orange, resolved on the desk via CP037.
- P/E is only for profitable issuers (n/m otherwise); market cap carries its
  derivation basis in `mktcap_basis`.
- EastMoney is IP-blocked from this network; Tencent (`web.ifzq.gtimg.cn`) is
  the working CN source for HK/A-share/FX history.
- The `formulas` test library cannot resolve BDP/BDH — Bloomberg cells are
  excluded from parity by design and only compute on the desk.
- Cornerstone SIMILARITY matches on `cornerstone_keys` (normalized first-token
  names, derived in merge via clean_names.investor_key) — never on raw names.
- The dashboard build ASSERTS embed key-coverage for ah_paths (fetched fields
  must reach the page); extend the same guard when embedding a new batch.

## v19 (2026-08-24) — cornerstone league, effective free float, filter leak

- **CS League** (Excel sheet + HTML "Cornerstones" tab): one row per investor,
  grouped on the Screener's normalized key (`clean_names.investor_key`), with
  n deals, day-1 hit rate, and average day-1 pop / 1w / 1m / 3m ex-pop.
  Aggregation lives in ONE place — `clean_names.cs_league` — imported by both
  builders, so the two deliverables cannot disagree.
- **Eff. free float (% of cap)** = deal size × (1 − cornerstone%) ÷ market
  cap — the slice that can actually trade on day 1 (cornerstones locked 6
  months). Derived in merge, identity-checked in audit_identities, blank only
  with `eff_ff_note`. No-cornerstone deals use cs=0 (the whole offer floats);
  a deal with a list but no % stays blank rather than pretending.
- **A-share filter leak (user-caught)**: comp rows come from
  `LARGE(score_rng, k+1)`; with a hard filter on, most scores are −999999 and
  the tail slots rendered those gated rows as phantom comps. Every comp-row
  formula now blanks when the k-th LARGE ≤ −900000. Probe in
  test_screener_formulas sets the filter and asserts no non-A name renders.
- **Index column names**: "Index 1m ex-pop" was nonsense (an index has no pop
  to strip). Renamed to state the window: "Index, IPO→1m" (bench_1m_pct) and
  "Index, d1→1m" (bench_1m_expop_pct — same window as the 1m ex-pop leg).
- **Cornerstone press round 2** (all in press_figures.json, append-only):
  2531 Carlink = ONE cornerstone (Huizhou Guohuilian; the "ZH-tendency Inc"
  garbage was the LOCK-UP shareholders table, not cornerstones); 2714 Muyuan =
  14 houses at exactly 50.0%; 9981 Woer = 16 entities incl. three OTC-swap
  rows (parse had deduped to 11 and included a placee); 3881 CIDI = the five
  parsed names were the prospectus's own short forms (only an RMB amount had
  glued on); 2566 Jiuyuan = 7 real names (Fosun/Alibaba Health/Jointown...)
  at 49.66% post-clawback. Lesson: a cornerstone table that parses "clean"
  can still be the WRONG TABLE — lock-up undertakings and placee lists sit
  pages away and look identical.
- **Cleaner v2**: trailing subscription amounts ("… RMB70,000,000"), leading
  "Shareholder(s)"/"Offering Relationship" bleed, embedded "Subtotal", "…
  Top" tails, "Hong Kong Limited"-class orphans; within-ONE-deal truncation
  fold (RIME ⊂ RIME Capital) — across deals that fold stays off (unsafe).
- **cornerstone_pct upper-bound fill**: deals with a list but no % take
  AAStocks institutional-total ÷ deal size, capped at 100, note says "upper
  bound — table can include non-cornerstone orders". Remaining gaps carry a
  "% not stated" note.
- **ipo.py refresh hang (2026-08-24)**: the stage runner sat 35 min at 0.08s
  CPU with zero output (cause not found — first network call inside the
  runner never returned). Workaround that works every time: run the stages
  directly (`run_stages.py`-style driver, per-stage timeout, merge last).
  If refresh hangs again, don't wait — drive the stages.
- **data/manual_splits.json** (CIDI 3881, 1→10): Yahoo split rows are
  discarded by design (the Zhida double-record lesson) and raw Tencent
  prints carry subdivisions UNADJUSTED — CIDI's "3m −91% / since −93%" was
  the subdivision, not a crash (true: −11.8% / −28.0%). The file multiplies
  raw-print bars on/after each date by the ratio, in fetch_prices (both
  branches) AND fetch_h_paths. Two rules: (1) every entry needs a filing
  (HKSCC circular) as evidence; (2) use the DEALING date, not the circular's
  "effective" date — prints divide when dealing in subdivided shares starts
  (CIDI: effective 02-20, dealing 03-02; the kline series proves which).
  Note: prices.json caches for 7 days — after editing this file, pop the
  code from prices.json + h_paths.json and re-run both fetchers.
- **A-share filter root cause (v19)**: the Database `a_share_code` cell is a
  BBG-fallback FORMULA whose off-terminal text ("not filed — run on
  terminal") is non-empty for EVERY deal — `<>""` passed the whole book.
  The gate now tests `is_h_share="Y"` (values, not formulas). This is the
  v14 lesson re-learned: NEVER gate on text non-emptiness of a cell that
  can hold fallback text; gate on the dedicated flag.
- **League verification lessons (v19)**: (1) two spellings of one investor
  inside ONE deal double-counted the deal (TAL China Focus "2 deals" was
  one) — cs_league dedupes keys per deal, and an assertion in review is
  "no investor counts one deal twice"; (2) bare Chinese surnames folded
  different PEOPLE into one row ("Yang Xiaojie" held 6 Yangs) — surnames
  are in the keep-two-tokens set now; (3) same house split across rows
  (HHLRA/HHLR, Schroders/Schroder, Southern-AM, MSIP/Morgan Stanley) —
  folded by a narrow rule (≥4-char key prefix + ≤1 extra char or one
  generic token) plus a curated `_ALIASES` map that requires book-internal
  evidence; near-misses (Al-Rayyan vs All View, Da Cheng vs Dajia) proved
  the rule must stay narrow.

## v20 (2026-08-25) — split sweep, price arbiter, zero orange

- **Corporate actions were unadjusted across the WHOLE raw-print class, not
  just CIDI.** Any deal whose Yahoo series reports a split is rebuilt from
  RAW Tencent prints — and raw prints carry subdivisions/consolidations
  unadjusted. `ipo_lib/detect_splits.py` now sweeps every raw-print deal:
  Yahoo split rows are CANDIDATES, and each is confirmed against a real
  scale change in the raw series before it is applied (unverified candidates
  are listed and left alone — WELLCELL's second row failed and was skipped).
  26 deals corrected; the effect is large (NOAH −95% → −50% since IPO, HESAI
  −91% → −7%, ZHIDA −85% → −23%, NUOBIKAN −86% → +29%). Re-run it whenever
  prices are refetched; output is `data/auto_splits.json`, hand-curated
  `data/manual_splits.json` still wins per code. Both directions work:
  ratio 10 = subdivision (multiply later prints by 10), 0.1 = consolidation.
- **The day-1 close is the ARBITER for a disputed offer price.** Research
  found the filing-PDF parse wrong 6 times out of 6 against AAStocks
  (BAIGE's "price" was the LISTING EXPENSES line, HK$54,382,183; HESAI
  154.99 vs the true 212.80; PONY 252.25 vs 139.00 …), so priority alone was
  picking the loser. merge now computes `close ÷ (1 + reported day-1 %)` and
  keeps whichever candidate that implies, before any priority rule. Plus two
  band guards: an offer price must sit in [0.05, 3000] and a market cap
  under HK$3tn — both are gate-checked, and a cap that fails is recomputed
  from shares × price or emptied with a reason.
- **Zero orange cells.** Sponsor conflicts were mostly press short forms vs
  filing legal entities ("CICC" vs "China International Capital Corporation
  Hong Kong Securities Limited") — they now compare on the normalized house
  key and CONFIRM each other. Two were genuine: ANKER's list was the
  PARTIES-INVOLVED table (compliance adviser, receiving bank), JOYSON was
  missing CICC; both press-ruled. Midea's subscription disagreement is a
  documented basis difference (both figures named in the note), and an
  institutional-sub reading we can prove wrong is now EMPTIED with the
  rejected value in the note rather than published as orange.
- **investor_key: never key a house to one generic word.** CICC's legal
  name reduced to a bare "china" (every token is a dropped generic), which
  both missed its own short form and risked colliding with any other
  China-named house. The all-generic path now keeps two tokens, and a small
  evidence-backed `_ALIASES` map covers initialisms (msip→morgan,
  cicc→china-international, gtja→guotai).
- **SHEIN appeared TWICE in the pipeline** — a curated watch-list row and
  the live offering-window row — so the tabs disagreed on its sector.
  `ipo_lib/pipeline_dedupe.py` (used by BOTH builders) keeps one row per
  company: the coded live record wins on facts, the curated HAND
  classification wins over a scraped industry string, and the filing's own
  industry stays visible with a `classification_note`.
- **Prose is clipped on a boundary, never mid-word** (`ipo_lib/textclip.py`):
  descriptions end on a SENTENCE, proceeds buckets on a word, PDF glyph
  artefacts ("/H1118") and tables-read-as-prose ("2023 2024 2025 118 250")
  are cut away. The pipeline card's 4-line clamp is a DISPLAY choice, so it
  now ships with a more/less toggle — a clamp with no way to expand reads
  as truncated data.
- **League verification round 2**: the "their deals" chip was clipped away
  by the inherited `td.csx` ellipsis (names truncate, the chip must not);
  min-deals is a typed number; WITH-POP (day-1/1w/1m/3m vs offer) sits
  beside EX-POP under grouped headers; a long list scrolls inside its cell.

## v21 (2026-08-25) — every price and return, checked three ways

`ipo_lib/audit_prices.py` is now a RED gate. It runs network-free on the
batches already on disk and answers the three questions that matter: was the
right thing extracted, is the arithmetic right, and was a corporate action
missed. It found four real defects, all now fixed.

- **33 deals carried a SATURDAY listing date** (plus one on a HK public
  holiday). HK allotment results are often published on a Saturday with
  dealings starting the next business day, and the HKEX-derived field is
  literally named `ipo_date_est`. A wrong listing date makes the two price
  sources pick DIFFERENT debut sessions — Morimatsu's day-1 read +213.7% off
  session two instead of +258.9% off session one. AAStocks' "Listing Date"
  (dealings commenced) now wins outright, and a weekend listing date is a
  gate failure.
- **Yahoo's HK history has HOLES.** Both STARPLUS and KEEP are missing the
  2023-07-17 session; a missing session shifts every trading-bar horizon by
  one day (up to 15pp on a volatile debut), and Yahoo can miss the DEBUT
  itself. Returns are therefore measured on the LOCAL kline session list —
  the same series the dashboard's charts draw — so the return columns and
  the chart can no longer disagree. 5 day-1 and 48 horizon values changed;
  all 511 now recompute exactly from the raw prints.
- **16 deals published a "gross" smaller than their own net proceeds**
  (YesAsia: gross HK$4.5m vs net HK$91.0m) and deal_size took that figure —
  a HK$117m deal shown as HK$4.5m. Gross < net is arithmetically impossible,
  so the stated gross is now rejected and the size falls through to
  shares x price, then to net, with the rejection stated in the note.
- **Two more "maximum offer price" extractions** (XUANWU 6.91 vs the true
  6.24, JENSCARE 28.80 vs 27.80 — both exactly the stated maximum, the same
  bad anchor that was wrong 6/6 in v20). Ruled in conflict_rulings.json on
  local evidence: the independently ingested day-1 is consistent only with
  the aggregator's price, and Jenscare's record also parsed gross < net.
- **Derived legs are re-derived LAST.** alpha = ret − bench and the ex-pop
  legs are now recomputed after every source has landed; computing alpha
  beside the return that produced it left one deal stale when a later batch
  refreshed its benchmark.
- Two audit checks were deliberately narrowed after producing explained
  signals: the two sources are compared only on the SAME session (where
  Yahoo lacks the debut, a price difference is expected, not evidence), and
  a round-factor jump is reported only when the sources also DISAGREE over
  the window containing it — a hot small cap doubling in a session looks
  identical to a 1:2 action, and MANYCORE/QIYUNSHAN/HUASHI were real moves.
- Greenshoe tolerance: shares x price may exceed the stated gross by up to
  15% (an exercised over-allotment against a base-offering gross) before it
  counts as a mismatch.

## v22 (2026-08-25) — cross-checked against news, and the typhoon lesson

Every value v20/v21 changed was put to independent sources. Two findings
came back, one confirming and one refuting.

- **All 8 corporate actions CONFIRMED** against HKEX primary filings —
  ratio and date both, for HESAI (1→8, 2026-07-10), NOAH (1→10,
  2023-10-30), ZHIDA (1→5, 2026-03-03), NUOBIKAN (1→10, 2026-03-11),
  GOGOX (10→1, 2025-04-25), FLOWING CLOUD (20→1, 2025-12-05), JOINN
  (three 4-for-10 bonus issues, ex-dates 2021-06-23 / 2022-07-28 /
  2023-06-20) and CIDI (1→10). Two things worth keeping: for splits and
  consolidations the effective date and the dealings-start date are the
  SAME day — the ~2-week gaps in those timetables are parallel-trading and
  certificate mechanics, not price-scale events; for BONUS issues the price
  re-scales on the EX-DATE while the bonus shares only become dealable
  4–6 weeks later. CIDI's effective date was POSTPONED from 2026-02-20 to
  2026-03-02 (Mainland holiday delayed certificate exchange), which is why
  the kline series changes scale on 03-02.
- **The Saturday fix over-corrected ONE deal, and finding out why exposed a
  real defect.** New Media Lab (1284) was moved to 2023-07-17 — but HKEX was
  shut all day for Typhoon Talim, so dealings began 07-18 and the original
  reading (+1.09%) was right. The general cause: **the kline feed inserts a
  PLACEHOLDER bar on days the exchange never opened**, repeating every
  stock's prior close. Counting one as a session shifted horizons by a day
  (which is what the v21 note misread as "Yahoo has holes" — Yahoo was
  right to omit those days), and a listing scheduled into a closed day gets
  a placeholder bar at the offer price that reads as a flat debut.
  `ipo_lib/sessions.py` derives the real trading calendar from the book
  itself: on a closed day EVERY stock's bar repeats its prior close, so a
  date with several bars and none of them moving was not a session. It found
  all three 2023 closures unaided (Talim 07-17, Saola 09-01, the 09-08 black
  rainstorm). merge measures on the filtered list and moves a listing off a
  closed day with a stated reason. Morimatsu (+258.9%) and YZYBIO (0.00%)
  survive this — both independently confirmed by listing-day press.
- **`Verify (BBG)` workbook tab** — the whole change-list on one screen for
  the terminal: our value, a BDP/BDH call for Bloomberg's, and a VERDICT
  cell that reads MATCH or CHECK by itself. Four sections: listing date +
  day-1 close, offer prices ruled against the filing parse, corporate
  actions (our day-1 close ÷ the cumulative factor must equal Bloomberg's
  adjusted print for that day), and the rebuilt deal sizes. Two mnemonics
  are new and flagged AWAITING VERIFY: `EQY_INIT_PO_SH_PRC`, `EQY_SH_OUT`.
- lint_bbg's BDH rule was widened from "must reference the Database" to
  "must reference a CELL, never a literal date" — the intent was always to
  forbid frozen dates, and the Verify tab anchors on its own date column
  because corporate-action dates are not in the Database.

## v23 (2026-08-25) — multiples everywhere, force-include, live P/S

- **P/E & P/S basis is ONE thing, stated everywhere: TRAILING.** Market cap
  at the final offer price ÷ the last FULL pre-IPO fiscal year's net income
  (P/E) or revenue (P/S), as filed. Pipeline expected multiples use the same
  definition at the range, so SHEIN (12.4–13.0x P/E, 0.61–0.64x P/S at
  US$25.7–26.8bn) compares with the listed book. Never forward.
- **No deal is blank on both multiples any more.** 36 deals lacked revenue —
  press/filing research filled every one (Baidu, XPeng, Li Auto, Trip.com,
  Autohome, 360 DigiTech, FWD, Hesai, Wuxi Lead, MiniMax, Merdeka…). The 11
  that remain number-less are the true zero-revenue biotechs, and their
  cells now READ "n/m" (loss-maker) and "pre-rev" (the filed P&L has no
  revenue line) — an answer, not a blank. Three research caveats recorded:
  FWD's "revenue" is IFRS-17 insurance revenue (no total-revenue line
  exists); MiniMax's loss is FY2025-basis so FY2025 revenue matches it
  (never mix the prospectus FY2024 revenue with that loss); Merdeka is
  pre-production (its US$0.13m "revenue" is rental income).
- **Pre-revenue is a fact about the revenue line, not a biotech label** —
  the prerev exception now also catches rev < HK$10m (Merdeka-class).
- **Financials are exempt from the NI>revenue wipe**: a PE firm's
  equity-method gains legitimately put NI above total income (Tian Tu
  FY2022: income RMB423m, NI RMB749m → P/E 7.6x, with the why in the note).
- **EKH's offering was WITHDRAWN 2026-07-08** and still showed OFFERING NOW —
  the roster keeps a pulled prospectus forever. `data/batches/withdrawn.json`
  (append-only, needs the HKEX announcement) re-labels such rows via the
  shared pipeline dedupe. Its FY2025 NI was also wrong (HK$81m, not 15).
- **P/S now (live)** joined P/E now in the comp table: BDP PX_TO_SALES_RATIO
  (the desk's own formula, quote-fixed), IFERROR-wrapped, falls back to the
  at-IPO P/S off-terminal. Mnemonic AWAITS first terminal verify.
- **Force-include**: Screener **C17 label / D17 input** (comma-separated
  codes) and the dashboard's "force-include a comp" box pin deals to the top
  of the comps PAST every filter; the gate probe pushes a non-A deal through
  an active A-share filter. Two lessons, both found by double-checking the
  SHIPPED file rather than the source: (1) it was first written to B19 —
  which is the comp table's BAND row — and was silently overwritten, while
  the gate still passed because the test SETS that cell; a control must be
  read back from a rebuilt workbook, and `audit_formulas.CARD_EXPECT` now
  asserts the "Force-include" label so the collision cannot come back.
  (2) JS: a `const` used by a hoisted function must be declared before the
  first render call — the TDZ error killed the whole page once.
- **Strip labels were distorted, not just small**: text inside a
  `preserveAspectRatio:none` SVG stretches with the container. Labels moved
  to HTML (`.saxrow`); the two sticky league header rows now stack at 0 and
  24px with OPAQUE backgrounds (transparent tints let data bleed through).

## v24 (2026-08-26) — the terminal verdict, entitlement issues, A/H drivers

- **The desk ran the Verify (BBG) tab: 79/90 dates and 24/26 actions MATCH.**
  Every non-match decoded: (1) HK tickers must be built WITHOUT leading
  zeros — "0606 HK Equity" is Invalid Security, "606 HK Equity" resolves;
  the Verify tab now strips them. (2) EQY_INIT_PO_SH_PRC and
  EQUITY_OFFERINGS-as-BDP are Invalid Fields — removed; the offer price is
  tied down by the verified day-1 close + day-1 % consistency instead.
  (3) Section A now compares on BLOOMBERG'S basis (raw ÷ cumulative action
  factor) for deals with later corporate actions — BBG's history is
  back-adjusted, ours is the true print; both are right on their own basis.
- **Entitlement issues are a THIRD adjustment class**
  (`data/entitlement_adjustments.json`): rights/open offers never re-scale
  the raw print, but Bloomberg back-adjusts by the TERP factor. Four cases
  reproduced BBG to 4dp from HKEX prospectuses (MTT 2-for-5 rights ×1.2460;
  Howkingtech/MemeStrategy 1-for-2 ×1.22414; Sanergy 1-for-2 pre-
  consolidation ×1.195431; Many Idea open offer ×1.13235 THEN 6-for-1
  rights ×1.09705). CONVENTION: our return columns are simple price returns
  vs offer and EXCLUDE entitlement value — stated per deal in ret_note; the
  factors feed only the Verify tab's BBG-basis comparison. REGO's ×1.1936
  is the same class but the announcement is not yet located (basis-only).
- **WellCell 2477 was a real miss the terminal caught**: its 2026-04-21
  event is a genuine 1→4 SUBDIVISION (raw prints re-scale 27.82 → 6.97)
  that detect_splits rejected because the stock CRASHED the same session
  (close-to-close ≈ ÷5.5, outside tolerance). Lesson: verify a split
  candidate against the ex-date OPEN, not close-to-close, when the day's
  move is violent. Since-IPO corrected −75% → −6%.
- **A/H premium drivers panel** (A/H tab) + the study's conclusions:
  size is the story (corr −0.71 with log mktcap; megas +25% median vs
  mid-caps +109%; CATL/Montage/GigaDevice trade A BELOW H); venue gaps
  collapse when size is held; P/E shows no relationship (+0.08); high
  premiums cluster in domestic-theme subsectors (solar/chemicals/18A ~
  +101–117%) and low in globally-priced ones (consumer electronics +35%,
  F&B +34%). Mechanism (researched, sourced): Southbound fast-entry
  (~10 trading days for top-10% IPOs; ~1 month for A+H names) vs the
  HK$5bn floor that keeps small H-lines out; A-share borrow is dead for
  EVERYONE since the relending shutdown (zeroed 2024-09-30, ~0.7% of the
  margin book in 2026) so borrow does NOT explain the cross-section; A/H
  are non-fungible, so the premium is a segmentation price.
- Explorer gained the greenshoe/no-greenshoe colour mode; the Excel comp
  table now carries a Code column beside Name.

## v25 (2026-09-01) — the A-line fixes market cap, Ingenic lands, three new deals

- **The market-cap complaint was real, and the fix is the A line.** Five deals
  carried NO cap at all (Luxshare, SG Micro, CCTC, Ingenic, PRU) because the
  prospectus parse found neither a share count nor a stated cap, and seven more
  carried a cap derived from a misread offer-% — Anker was published at
  HK$386bn against a true ~HK$58bn. Both classes are now caught by one
  independent yardstick: **the A line's TOTAL share capital × the H offer
  price**. `fetch_ah_snapshot` reads Tencent quote field 45 (总市值) and field 44
  (float cap) for every A/H pair and divides by the A price to recover the
  share count. Field-45 semantics are VERIFIED, not assumed: on ICBC it implies
  356.4bn shares = the full A+H capital, not the 269.6bn A-only float. The
  count already includes the newly issued H shares — on Ingenic it gives
  514,948,196 against the allotment announcement's filed 514,951,667, 0.0007%
  apart.
  - New ladder rung (prio 45, below stated/AAStocks figures, above the
    midpoint estimate), restricted to **2025+ listings** so today's share count
    is never backdated across years of buybacks and placements.
  - New adjudication in pass 2: an existing cap more than **30%** from the
    A-line figure is REPLACED by it, with `mktcap_note` naming the old basis
    and the gap. Result on this run: 45 within 30%, 7 adjudicated (Anker
    386k→58k, Wuxi Lead 275k→77k, Novosense 116k→19k, Eastroc 122k→182k,
    Huaqin 73k→118k, Longcheer 26k→16k, Gon 11k→16k HK$m). P/E and P/S rederive
    off the corrected cap because the adjudication runs BEFORE them.
  - `a_mktcap_now_hkdm` (A-line company cap today, CNY→HKD at the snapshot FX)
    is now a Database column, a comp-table column, a Comps-Lab metric and an
    explorer axis. **This is the "Luxshare isn't that small" answer**: the H
    tranche is HK$24bn, the company is ~HK$490bn at the offer and ~HK$520bn
    today. Effective free float joined the explorer axes at the same time.
  - The AAStocks A/H table lags brand-new H listings by weeks, so the snapshot
    now unions in `ah_map.json` — those codes still get the A-side enrichment
    even before the pair appears in the published table.
  - PRU (2378) was the one non-A/H gap: 2,746,394,249 shares in issue at
    2021-10-04 from Prudential's own Total Voting Rights RNS/SEC 6-K, × HK$143.80
    = HK$394.9bn. **Market cap is now 512/512.**
  - **THE A-LINE COUNT IS A PROXY, NOT A SOURCE — and it is TODAY's count.**
    Verifying the seven adjudications against the filings found three issuers
    that ran a capitalisation issue AFTER listing: Huaqin 10-for-4, Eastroc
    10-for-3, Gon 10-for-4.8. Applying today's share count to the IPO price
    overstates those caps by 30–45%, and for Gon the pre-existing figure had
    been right all along. So the rule is now explicit in code: where a filing
    states the count upon listing, that count wins and the A-line only
    cross-checks; the A-line overrides ONLY an offer-%-derived or
    aggregator-midpoint estimate, which is the class that was actually broken.
    Filed "number of issued Shares upon Listing (before any exercise of the
    Over-allotment Option)" is now in `press_figures.json` for all ten A+H
    names — Luxshare 7,701,730,624 · CCTC 1,987,861,671 · Wuxi Lead
    1,673,821,434 · Huaqin 1,074,280,544 · SG Micro 675,015,824 · Anker
    582,909,162 · Eastroc 560,902,900 · Longcheer 522,590,644 · Ingenic
    514,951,667 · Gon 301,250,000 — each with its announcement URL. Where the
    proxy is still the only figure, `mktcap_note` says so and names the risk.
  - Convention confirmed, not changed: the book's cap is **all share classes ×
    the H offer price**, which is the multiple an H buyer actually pays. The
    prospectus "Global Offering Statistics" figure is a MIXED basis (A shares
    at a 5-day average A price, H at the offer), so the two legitimately differ
    — Luxshare HK$487bn ours vs HK$590,584m stated. Both are recorded.
- **Ingenic (3223) moved from placeholder to filed fact**, all from the HKEX
  allotment announcement (2026082401907.pdf) and prospectus (2026081700003.pdf):
  final price **HK$100.00** (the HK$102.80 in the roster was the CAP — priced
  below it), 31,287,300 H shares, gross HK$3,128.7m / net HK$3,054.6m, public
  **927.37×** on 141,851 applications, international **8.43×**, no clawback
  (10/90 held), cornerstones US$191.65m = 15,034,000 shares = **48.05%** of the
  offer locked to 2027-02-24, greenshoe 4,693,000 (15%) fully over-allocated
  with **no exercise announced** as of 2026-08-31 (stabilisation to 09-19,
  Guotai Junan), one-lot ballot 0.27%. Classified Tech/AI · AI chips & semis
  (fabless memory ~61% of FY25 revenue, computing 27%, analog 11%; automotive
  33.5%). Cap HK$51,495m; P/E 124.4× and P/S 9.9× trailing.
  `press_figures` now also carries `shares_outstanding`, `offer_shares`,
  `overallot_shares` and both subscription multiples — filing-verified
  structure, still below the Bloomberg desk paste (prio 95) for subs.
- **`audit_fresh` was wrong about flat debuts.** It failed any day-1 of exactly
  0.00%, but Ingenic really did open AND close at HK$100.00 on 2026-08-25 — on
  5.8m shares with a 100.40/97.10 range. A moving bar is a real session; the
  placeholder shape is a row with no listing-day bar behind it at all. The gate
  now tests for the bar, not the zero, and reads CLEAN.
- **The deal-size parser was reading the GREENSHOE's sentence.** Chasing the
  cap complaint turned up a second defect underneath it. An allotment
  announcement states "net proceeds ... HK$X million" three different ways —
  the deal itself ("are estimated to be approximately HK$24,113 million"), the
  over-allotment option ("**additional** net proceeds of approximately
  HK$3,632 million") and each use-of-proceeds bucket ("approximately 55% of
  the net proceeds, or approximately HK$13,262 million"). The old regex took
  whichever came first in the file **and** capped its search at 300 characters,
  which is shorter than the base sentence actually runs. JD Logistics was
  therefore published as a **HK$3,632m** deal against a real **HK$24,113m**.
  `parse_proceeds()` now ranks candidates instead of taking the first: the
  greenshoe and bucket sentences are rejected outright, an explicit "estimated
  to be" statement outranks a bare mention, and a document with only buckets
  can have its total recovered when two or more agree within 2%. Verified
  against four hand-read filings (JD Logistics 24,113 · Leapmotor 6,057.4 ·
  Tuhu 1,081.5 · Weibo 1,383.4). Deal size feeds effective free float AND the
  offer-% market-cap rung, so this was a cap error too.
  - Applied by `_model_scripts/patch_proceeds.py`, which re-parses ONLY the
    proceeds fields from `scrape/text_cache` (full document text, better than
    the 12-page window the original parse read). A full
    `extract_prospectus.py allotments` re-run re-reads 522 PDFs and times out
    past 900s; every other field in that batch was already correct.
  - Anchor-then-window, not one big regex: running a value pattern over a whole
    60KB announcement backtracks for ~2 seconds per deal because the documents
    are dense with digit-and-comma runs. Match the cheap literal first, then
    scan a 600-character window.
- **Stabilising manager extracted, and its own league tab** (`SM League` in
  Excel, `Stabilisers` in the HTML). Every allotment announcement carries the
  same cover sentence — "In connection with the Global Offering, *Guotai Junan
  Securities (Hong Kong) Limited* as stabilizing manager (the 'Stabilizing
  Manager')" — so `ipo_lib/extract_stabmgr.py` reads the name from the local
  text cache; nothing is inferred from the sponsor, and a deal with no
  over-allotment option correctly has none (its `shoe_note` already says so).
  Names are grouped by BANK FAMILY, so "Goldman Sachs (Asia) L.L.C." and
  "Goldman Sachs International" are one row.
  - The league is the exact mirror of CS League — same columns, same
    with-pop/ex-pop split, same shared aggregation (`clean_names.stab_league`
    beside `cs_league`) so Excel and HTML cannot disagree — **plus two columns
    only stabilisation has: shoe full % and shoe lapsed %**. That is the
    reading: a shoe exercised in full means the price never needed support;
    a lapsed shoe means the manager was buying stock back to hold the line.
  - Read it AGAINST the cornerstone league. One says who anchored the deal,
    the other who defended it — the same bank often does neither well at both.
- **Three deals added to the pipeline, each from its own prospectus:**
  - **Longsys 9976** (深圳市江波龍, A-line 301308.SZ) — maximum-price structure,
    no floor: "no more than HK$240.60". 26,077,800 H shares, gross max
    HK$6,274m, cap **HK$204,633.5m** as the prospectus itself states it (A shares
    at the 5-day RMB399.18 average). 15 cornerstones ~US$151.1m = 18.89% of the
    offer; greenshoe 15% PLUS a separate 15% offer-size adjustment option;
    stabilisation to 2026-10-03. FY2025 revenue RMB22.77bn, profit RMB1.50bn —
    but H1-2026 revenue RMB24.09bn and profit RMB10.72bn against RMB41.0m,
    i.e. the memory upcycle has already made the trailing multiple meaningless.
    Max price sits ~45% below the A line. Closes 09-03, lists 09-08.
  - **Excelland Robotics 3231** (優地機器人, brand Uditech) — **Chapter 18C**
    commercial company, HK$14.45–19.55, 45m shares, HK$650–880m gross, cap
    HK$6,016–8,140m on 416,368,421 shares. Cornerstones only **US$3m** total
    (SensePower/SenseTime US$2m + CYGG US$1m ≈ 3.1% of the offer, both close
    associates of existing holders); **no greenshoe and no stabilising manager**
    — the same structure the desk flagged on Medcaptain. FY2025 revenue
    RMB317.7m (+18.9%), loss RMB110.8m; 3M-2026 loss widened ~20% y/y. Sole
    sponsor is a boutique (Silver Nile). No P/E — loss-maker; P/S 17.2–23.3×.
    Closes 09-04, lists 09-09.
  - **Medcaptain 2041** was already loaded in v24's pass; unchanged.
  - EKH 2523 finally carries a sector (Industrials · Logistics) and its status
    reads WITHDRAWN rather than the roster's stale "OFFERING NOW".

## Data-quality rules that now run automatically

- **Cover-page bleed is scrubbed from every party list** (`clean_names.
  clean_party_element/_list`, applied in merge to `sponsors`, `sponsors_en`,
  `underwriters_en`, `bookrunners`, both display strings, and — via
  `clean_investor` — cornerstone cells). The five classes, all observed in the
  book (109 deals): the section heading "DIRECTORS AND PARTIES INVOLVED IN THE
  GLOBAL OFFERING/SHARE OFFER" with page-number fragments ("– 176 –", "–1 1 0–",
  en/em/minus dashes); role labels glued to the next name ("Managers CLSA
  Limited", "Sole Representative : …", "Sponsor-Overall Coor dinators …",
  "Joint Bookrunner, Capital Market Intermediary …"); the issuer's US address
  ("New York, NY 10179 United States of America UBS AG …"); footnote pointers
  ("Please refer to Note (1). No" — CAOCAO's whole cornerstone list was two of
  these); orphaned suffix halves ("Securities Limited" alone). Lesson that cost
  a debugging loop: **strip junk punctuation BEFORE each ^-anchored role pass**
  — "-Overall Coordinator X" hid the label behind a leading hyphen, so the
  strip ran but removed only the hyphen. Test any new pattern against the
  legit-name regression list in the unit block (The Hongkong and Shanghai
  Banking…, CMB International Capital…).
- **press_figures.json now also carries `cornerstone_investors` +
  `cornerstone_pct`** (prio 70, xchecked); the AAStocks cornerstone fill SKIPS
  deals whose provenance is press — hand research is never overwritten.
  CAOCAO 2643 is the precedent: the PDF allotment parse read footnote refs as
  names and 23%, press says six cornerstones (Mercedes-Benz Mobility, Mirae,
  Infini, Gotion, EVE, RoboSense), HK$951.6m = 22.6424m of 44.1786m offer
  shares = 51.3%.
- **Cornerstone spellings are canonicalised book-wide.** The same investor arrives
  from three sources with different spellings ("GIC Private Li" vs "GIC Private
  Limited", ALL-CAPS forms, "A及B" in one cell, footnote markers). merge collapses
  them to the most-filed full spelling; different vehicles of one house (CPE
  Investment XVI vs CPE Redwood) stay separate on purpose. Raw lists survive as
  `cornerstone_investors_raw` for audit.
- **Price vs range**: a struck price ABOVE the recorded cap means the CAP parse is
  wrong — the cap is flagged and % -of-cap withdrawn (SAIMO). A price BELOW the
  indicative low is legal in HK (Downward Offer Price Adjustment) and is annotated,
  not flagged (Global New Material).
- **Every column is a value or a stated reason.** merge writes *_note fields for
  each remaining blank; the Database's "Notes on blanks" column shows them.
- `price_asof` dates the since-IPO column (prices refresh weekly, so the number is
  never more than a few sessions old — this was the only "mismatch" left in the
  independent audit).
- **Financial plausibility gate (v11).** merge refuses to publish a multiple it
  cannot believe. Two internal checks, no thresholds pulled from the air:
  net income above revenue means the extracted PAIR is inconsistent, so both
  figures and both multiples are withheld; a derived P/E or P/S above 300x means
  the denominator is wrong, so the multiple goes and the suspect figure with it.
  A pre-revenue 18A issuer is the exception — its tiny revenue is real, so the
  revenue stands and only the meaningless P/S is withheld as `n/m`. Every case
  writes its own reason into `fin_check` / `pe_note` / `ps_note`, which surface in
  the Database's "Notes on blanks" column. This removed 92 impossible
  multiples (Li Auto read 307,800x P/S, Zijin Gold 39,145x P/E).
- **Three extraction bugs the gate exposed, now fixed at source:**
  a *year header row* under a "Revenue" label was being read as money
  (`[2017, 2018, 2019]`); a *narrative sentence* mentioning revenue was matched
  before the summary table, yielding page numbers and dates; and a table printed
  "(RMB in millions)" was divided by 1,000 again on the thousands assumption.
  `series_from` now scans every label occurrence instead of only the first,
  rejects year-shaped series, and reads the unit from the row's own header.
- **Cornerstone % must come from a cornerstone sentence.** "representing
  approximately X% of the Offer Shares" is also how the prospectus states the HK
  public-offer CLAWBACK, and that sentence can fall inside the cornerstone
  window — Sanhua's cornerstone tranche read 10.0% when 10.0% was the retail
  reallocation. A match is now accepted only when its own sentence mentions the
  Cornerstone Investors and is not a reallocation clause, and block selection
  weights the "aggregate amount of approximately US$Xm" sentence 100x (it is the
  one unambiguous marker of the real section). Sanhua now reads US$562.0m →
  47% of the deal, matching the filing and the press.
- **A NaN is never a number.** yfinance's newest row can be a stub with a NaN
  close before the session settles; that wrote NaN straight through to since-IPO
  and its alpha for 14 deals and rendered as "NaN%" in the dashboard. Prices now
  mark to the last bar that actually printed, and `bench_return` returns None
  rather than a non-finite reading.
- **Risk and tax boilerplate is not a business description.** "We are a PRC
  enterprise and we are subject to PRC tax…" and "We are a company incorporated
  under the laws of…" match the business-description patterns but describe no
  business; `RISKY` now rejects them, and offering-window deals are classified
  into the taxonomy instead of showing "sector not yet classified".

## Benchmarks and weights — measured, not assumed

- Materials/Energy was benchmarked against the Hang Seng UTILITIES sub-index, which
  holds power/gas distributors only. Miners, chemicals and energy producers sit in
  Commerce & Industry under the index's own methodology — corrected to ^HSNC.
- A pair test over 24,090 deal pairs asked which factors identify deals with SIMILAR
  day-1 outcomes: both-A+H +49%, subscription-within-2x +32%, same sector +4%, while
  subsector / size / P/E / cornerstone were no better than random. Subsector-first
  therefore stays as the VALUATION comparability gate (the user's design), and a
  "demand-similar first" rank mode was added for the outcome question. The numbers
  are printed on the Notes tab so the weights can be re-argued from evidence.

## v26 (2026-09-02) — SHEIN and Mech-Mind land, and four pipeline holes they exposed

Two listings on 2026-09-01 took the book from 512 to 514. Both were already in
the Pipeline tab, so graduating them exercised the whole path from roster to
deliverable — and it found four defects that would have bitten the desk on
every future listing, not just these two.

- **SHEIN (0625, SHEIN-W)** — final price **HK$48.56** against a HK$47.60–49.50
  range, so priced 1.9% below the cap and a shade above the mid. 279,992,500
  Class B shares, 100% primary, gross **HK$13,596.4m** / net HK$13,214.1m
  (279,992,500 × 48.56 = 13,596,437,800 — the identity holds to the dollar).
  Public tranche **5.63x** on 35,751 valid applications, international 2.59x on
  106 placees; below the 15x trigger, so **no clawback** and the split held at
  10/90. Seven cornerstones for US$383.0m = 22.1% of the offer but only 1.5% of
  issued capital. Greenshoe 41,998,500 (15.0%) **fully over-allocated**,
  stabilising manager Goldman Sachs (Asia) L.L.C. to 2026-09-26. Shares upon
  Listing 4,246,202,609 (Class A + B) × HK$48.56 = **HK$206.2bn** on the book's
  convention. Day 1: opened exactly at the offer, traded to HK$43.72 (**−10.0%**)
  and closed HK$48.50 — one tick under issue, inside a live stabilisation
  mandate. WVR regime from the short-name suffix, hand sector kept (Tech/AI ·
  internet platform) over the filing's Consumer/Apparel industry string.
- **Mech-Mind Robotics (9615)** — final price **HK$101.70**, which is the CAP of
  the HK$95.30–101.70 range. 23,140,590 H shares, gross **HK$2,353.4m** / net
  HK$2,200.2m. Public **3,835.36x** on 252,461 applications against international
  13.39x — **clawback triggered**, 3,471,090 shares reallocated, final split
  20/80 (from 5/95). Note the two nearly identical figures in that filing are
  genuinely different mechanics and neither is a typo: over-allocation is
  **3,471,060** shares, the clawback reallocation is **3,471,090**. Cornerstones
  US$186.0m = 62.02% of the offer. Greenshoe fully over-allocated, stabilising
  manager CLSA Limited. 125,011,050 shares upon Listing × HK$101.70 =
  **HK$12,713.6m**, which matches the prospectus's own stated expected cap
  exactly. Day 1 opened at the offer, low HK$97.00 (−4.6%), closed HK$99.80
  (**−1.87%**). One-lot ballot 3.00%.

**The four defects, all now fixed in the pipeline rather than by hand:**

1. **`patch_proceeds` and `patch_offer_shares` were one-off scripts, so the next
   plain `refresh` would have silently undone them.** They live in `ipo_lib/`
   now and run as the `patch-proceeds` / `patch-offer-shares` stages in BOTH
   `ipo.py` and the desk bundle, after every other writer of
   `extracted_allotments.json`. They re-read the FULL cached announcement text
   where `parse-allot` sees only the first 12 pages, and they never blank a
   value they cannot better. Leaving them outside the pipeline was worth 165
   corrected proceeds figures and 262 re-read share counts — i.e. the whole of
   the v25 deal-size repair, one refresh away from vanishing.
2. **Prices ran BEFORE the merge, so a brand-new listing was unpriced until the
   NEXT refresh.** `fetch_prices`, `fetch_h_paths` and `fetch_ah_paths` all take
   their code list from `deals.json`, which a listing parsed in the same run has
   not yet reached. A new `merge-pre-prices` stage sits ahead of them and the
   existing merge folds the prices back in. Without it SHEIN and Mech-Mind would
   have entered the book with no day-1 return at all, and the fix is general:
   every future listing now prices on its first refresh.
3. **The stabilising-manager regex could not span a name containing periods —
   and that quietly deleted the two biggest stabilisers from the v25 league.**
   The cover-sentence pattern used a `[^.;]` name class, which stops dead at the
   first dot, so a name like "Goldman Sachs (Asia) L.L.C." never reached the
   ", as the stabilizing manager" anchor. SHEIN was how it surfaced — unnamed
   against a filing that names one plainly — but SHEIN was 1 of **43**. Measured
   against the cached text of all 524 announcements, the widened pattern newly
   names:
   - **Goldman Sachs — 27 deals**, previously absent from the league ENTIRELY
   - **J.P. Morgan — 10 deals**, likewise entirely absent
   - Shenwan Hongyuan 5, China Galaxy 1
   Coverage goes 265 → **308 of 524 (58.8%)**. The v25 SM League therefore
   ranked HK stabilisers with Goldman and J.P. Morgan missing from the sample,
   which is enough to move any league conclusion drawn off it — treat the v25
   stabiliser read as superseded, not merely extended.
   The rule: a dot is kept when it is an abbreviation dot and dropped when it
   ends a sentence, on two signals — not followed by whitespace-then-capital, or
   straight after a lone initial. That second signal is exactly what "J.P.
   Morgan" needs, since its `P.` IS followed by " Morgan"; the naive fix would
   have fixed SHEIN while still losing all ten J.P. Morgan deals.
   Sentence-boundary safety is preserved, so the match can still never run
   backwards into a previous sentence.

4. **A brand-new code loses a race with itself, and its whole prospectus goes
   unparsed.** `fetch_newlistings` downloads the prospectus the day it posts
   (as `newlist_<code>_*.pdf`), while the roster-driven per-stock search in
   `fetch_hkex_filings prospectus` still cannot resolve a code that new and
   returns nothing — so the manifest carries no parts for a document already
   sitting in `scrape/pdf_cache/`. SHEIN was parsed from its allotment
   announcement but NOT from its prospectus for exactly this reason.
   **The tell was a false explanation, not a blank.** With no prospectus text,
   the merge labels missing sponsors *"sponsor not stated in the extractable
   filing text"* — which for SHEIN was untrue: Goldman Sachs (Asia) L.L.C.,
   Morgan Stanley Asia Limited and J.P. Morgan Securities (Far East) Limited
   are all in the document, in a file we had already downloaded. An explained
   blank is only worth anything if the explanation is true.
   Fixed in `fetch_hkex_filings.attach_cached_newlist()` — the MANIFEST
   builder — rather than in any one parser, because `extract_prospectus`,
   `extract_deep` (sponsors, bookrunners) and `extract_profiles` all read that
   single manifest and all skip a deal with no parts; fixing it once upstream
   fixes all three. It indexes the cache in one pass (globbing per deal over a
   3,300-file directory is ~200k stat calls for nothing) and prints what it
   recovered. Today: 468 → **469** deals with prospectus parts, the one
   recovery being SHEIN. The other 55 partless entries have no cached
   prospectus at all — the long-standing, genuinely explained "body never filed
   as one document" absence — but this is the race EVERY new listing hits, so
   it now self-heals.
   Note the AAStocks per-deal page lags a listing by weeks (both new codes came
   back null for sponsors, underwriters and cap), so for a fresh deal the
   prospectus is not a nice-to-have second source — it is the ONLY source.

**Two traps in these debut numbers, both worth knowing before anyone updates a
figure by hand.**

1. *Field order.* The Tencent kline row is `[date, OPEN, CLOSE, high, low,
   volume]` — open before close, the opposite of most feeds; the Sina HK quote
   is different again (`open, prevclose, high, low, last`). `fetch_prices.py`
   reads Tencent correctly (`row[2]` is the close). Both these deals opened at
   exactly their offer price, so a transposed read turns two deals that BROKE
   ISSUE into two that closed flat. A debut reporting a day-1 return of exactly
   0.00% is the signature of this mistake — check the field order before
   believing it.
2. *Press headlines are intraday, not closes.* SHEIN's debut was reported as a
   "10% plunge" (CNBC, The National) and simultaneously as "ends flat" (Forbes,
   The Information). Both are true of different moments: it traded to HK$43.72
   (−10.0%) early and closed HK$48.50 (−0.12%). Never lift a day-1 return from a
   headline written during the session.

Both closes were verified against six independent feeds — Tencent, Sina and
Eastmoney on the Chinese side, CNBC (exchange-sourced), Investing.com and
stockanalysis.com on the Western side — agreeing to the cent on OHLC and to the
share on volume, with Reuters stating the HK$48.50 close in prose. HKEX's own
Daily Quotations Sheet could not be retrieved (URL relocated), so the primary
exchange document is NOT among those six; if the desk wants one, that is the
gap to close on the terminal.

## v26.1 (2026-09-02) — the desk's read-through: stabilisers, floats, multiples

**A greenshoe implies a stabilising manager.** That is the desk's rule and it is
right: someone holds the option. Reading only the allotment announcement left
**110 deals with a greenshoe and no manager**, and Innolight (3308) is the proof
the announcement is not always enough — its allotment filing does not contain the
string "stabilis"/"stabiliz" ANYWHERE, while its prospectus glossary says plainly:

    "Stabilizing Manager"   Goldman Sachs (Asia) L.L.C.

So `extract_stabmgr` is now two passes. Pass 1 is the allotment announcement
(post-pricing, authoritative). Pass 2, only for deals pass 1 could not name,
reads the PROSPECTUS — the definitions glossary first, then the cover sentence
and parties table. The glossary is a flattened two-column term/definition list,
so the name runs from the closing quote of the term to the next opening quote;
curly quotes are what the PDF text actually carries. `src` records which
document and which pattern produced every name, so nothing is ever inferred
from the sponsor. Pass 2 reads whole parts rather than a head window (the
glossary sits deep in the definitions section) but skips any part whose text
does not contain "tabili" at all, which keeps that from costing anything.

One artefact worth knowing: PDF extraction splits a word after its first letter
often enough to matter — Yuen Meta came out `Y uen Meta` and keyed as `Y uen`.
A lone capital followed by a LOWERCASE continuation is always that artefact, so
`tidy()` rejoins it; a real initial is followed by a capital ("J P Morgan"), so
this cannot glue two genuine tokens together.

**Stabilisation notices were being dropped on their title.** The fetcher required
"stabilis|stabiliz|over-allot|lapse" in the TITLE, but Ingenic filed its notice as
plain `GLOBAL OFFERING OF INGENIC ...` — no stabilisation word at all — so it was
never opened and the deal carried no hyperlink. Three changes: the title match now
also accepts "global offering"/"share offer"/"over-alloc" (safe, because the search
window is already 15–75 days after the allotment announcement, where such a filing
is the stabilisation notice in practice); candidates are ranked so an explicit
stabilisation title is still tried first, and four are examined rather than two;
and, most importantly, **the notice's hyperlink is now recorded whenever the
document is genuinely about stabilisation, even when the outcome wording is one
the regexes cannot classify**. Withholding the link because the parse was
inconclusive left 74 deals that HAVE a greenshoe with nothing to click; the
outcome itself is still left blank rather than guessed, with a note saying so.

**The stabiliser league gained the day-1 session, which is the thing it should
have measured all along.** New columns, in Excel and HTML off the same shared
aggregation: `open vs issue` (the pop — where the stock opened against the price
the bank sold it at), `close vs issue` (the day-1 return), and `open→close`
(whether that open was HELD or given back). A negative open→close beside a
positive close is a bank that spent the session supporting a fading stock, which
a single "day-1 pop" number hides completely. On the current book CLSA opens
+46.5% and closes +40.9%, while China Securities opens +22.1% and *adds* to
+35.1%.

**Effective free float, three ways off one identity.** The formula was already
`deal size × (1 − cornerstone %)` — cornerstone % is a share OF THE OFFER, which
is what makes the subtraction valid — but it was only ever published as a
percentage of market cap, so the absolute number the desk actually wanted was
nowhere. Now `eff_free_float_hkdm` (money) and `eff_free_float_shares` (offer
shares × the same factor) sit beside `eff_free_float_pct`. The absolute pair
needs no market cap, so they survive the two rows whose cap is not derivable.
Not modelled: an over-allocated greenshoe puts MORE stock in the market on day 1
than the offer alone — the stabiliser is short it — so on a fully over-allocated
deal the true day-1 tradeable float is larger than this figure.

**Two P/E columns, and which one to trust.** They are both right on different
bases. `P/E at IPO` is ours — final market cap ÷ the last PRE-IPO fiscal-year net
income from the prospectus — computed identically for every row, with both inputs
visible as columns beside it. `P/E at IPO (BBG)` is Bloomberg's — price ÷
trailing-12m EPS at listing. They diverge most on 2021-23 vintages (median
BBG/ours ≈0.5) because earnings grew between the covered FY and listing and
Bloomberg uses weighted pre-deal shares. **Use ours to rank deals against each
other** (only one basis, and auditable); **use Bloomberg's when quoting a number
someone will check on a terminal.** The book already treats Bloomberg as referee:
where our multiple breaks the plausibility cap, a BBG print within 25% restores
it as real (CALB at ~549x), and agreement at an absurd level is read as a shared
artifact rather than a confirmation. This is now stated in the workbook's own
notes, not just here.

**Also added:** `P/S today (BBG)` in the Database FUNDAMENTALS band — no public
source exists for a live multiple, so every row resolves off BBG Verify col S on
the terminal and says "run on terminal" off it; `A-share mkt cap now (BBG)` as
BBG Verify col T (CUR_MKT_CAP on the A ticker), which the scraped A-line cap
column now falls back to wherever the Tencent snapshot had no figure; and the
Screener's `P/E now` / `P/S now` moved INTO the FUNDAMENTALS band next to
`P/E at IPO`, instead of being stranded beside Match/Score where they read as
scoring inputs.

**A self-inflicted lesson.** The prospectus-rescue in v26 appended a docs entry
with `file_link: None`, and the merge builds the Database hyperlink by
concatenating that onto the hkexnews host — so the whole 514-deal merge died with
`TypeError: can only concatenate str (not "NoneType") to str`, twice, silently,
while every expensive parse stage around it succeeded. Two fixes: the rescue now
takes the real path from the offering-window record (so the manifest is truthful
and SHEIN gets a working prospectus link), and the merge picks the first doc that
actually HAS a link rather than assuming `docs[0]` carries one. **Never append a
document record without its link.**

Market cap is **512/514**, not the 512/512 v25 claimed: Sipai Health (0314) and
Jinxun Resource (3636) have no share count, no offer-% of capital and no
published listing cap in any source, AAStocks included. Both say so in
`mktcap_note` rather than carrying a number.

## v26.2 (2026-09-02) — the full-book audit: every number re-derived, every reason visible

The instruction was "check everything — returns with corporate actions, market
cap, P/E, P/S, every field, every visual — spend as much time as possible".
This section records what was checked, what was found, and what changed.

**Returns, verified against the exchange's own prints.** The method: pull the
raw Tencent day-kline (unadjusted, as-traded) for a deal, index its sessions
locally, apply the DOCUMENTED corporate-action factors from
`data/auto_splits.json` / `entitlement_adjustments.json`, and rebuild
day-1/1w/1m/3m against the offer price — then diff the book. Results:

- 12 random non-split deals: **exact to the digit on every elapsed horizon**.
- 6 split-affected deals (Hesai, Nuobikan, Zhida, Nanhua, Gon, Huaqin):
  **day-1 and 1m exact**; the "since" differences were the live session.
- 4 deals where tonight's prices batch disagreed with the book (Morimatsu,
  YZYBIO, UJU, New Media Lab): the raw prints sided with the BOOK on three and
  with the batch on one — see the open0 fix below. Root cause of the batch
  side: **Yahoo permanently lacks the debut bar** for 2155 (starts 06-29,
  listed 06-28) and 2496 (starts 09-26, listed 09-25), so any Yahoo-based read
  calls day 2 the debut. The book is immune BY DESIGN: the merge re-measures
  every return on the local session list at priority 55, which beats the batch.
- 8 audit flags with no prior explanation (1497, 2129, 2185, 2252, 2431, 6090,
  6628, 9676): raw prints say **8/8 the book is right** — the auditor's Yahoo
  side mis-aligned sessions.

`audit_returns.py` itself ran under heavy Yahoo throttling and produced a
polluted table (2635's 3m "mismatch" is exactly the ×10 split factor its
throttled split-row fetch missed). No deliverable consumes that JSON — its
docstring's Verification-tab claim is outdated — but do not trust a run of it
made while Yahoo is limiting; the tell is hundreds of "since" flags at once.

**One real returns bug found and fixed: the day-1 OPEN of a postponed listing.**
h_paths cached "complete" records keyed on fetch-time listing dates, so New
Media Lab (1284) — typhoon-postponed from 2023-07-17 to 07-18 — kept the
exchange placeholder's open (0.92, the offer echoed back) frozen forever and
printed a day-1 open pop of exactly 0.0% against a real open of 0.88 (−4.35%).
Fixes: the h-paths cache invalidates when its stored listing date no longer
matches the book's; and the merge only trusts `open0` when the record's anchor
matches, otherwise it drops the open legs with the reason in `day1_oc_note`.
1284 now prints −4.35%. A debut open pop of exactly 0.00% remains the
signature of this class — Ingenic's genuine 0.0% day-1 CLOSE (open 100.00,
close 100.00, low 97.10, offer HK$100.00 — pinned at issue by the stabiliser)
was verified against the raw bar before being believed.

**Market cap / P/E / P/S: identities re-derived for the whole book, all clean.**
gross≥net (221 rows), shares×price=size where the basis says so (268),
price×shares-upon-listing=cap where the basis says so (175), P/E=cap/NI on
every derived row (284), P/S=cap/rev (480), the free-float trio (502),
since-IPO vs last close (514), A-premium convention (61), ranges and
structure (514). Zero failures. Comparability: P/S is single-basis 480/480;
P/E is single-basis on 284 rows plus 8 documented Bloomberg gap-fills — rows
where no FY NI or no cap exists — each carrying its basis in `pe_note` and its
provenance, with the same value visible in the `P/E at IPO (BBG)` column. That
v12 design stands: an explained basis-borrow on 8 rows beats 8 blanks.

**The syndicate lists were shipping office addresses glued to bank names.**
The Parties-Involved parse carried the previous entry's address tail onto the
next name — 192 rows like "Central, Hong Kong CLSA Limited" (originally
counted 171; the tighter counting found more). Fixed in
`clean_names.clean_party_element` (one choke point, so leagues, display
strings and raw lists all heal), anchored on the literal ", Hong Kong "
marker with head-must-look-like-an-address and tail-must-look-like-a-company
tests, because two REAL names had to survive: "Central China International
Capital Limited" (a genuine house) and "Deutsche Bank AG, Hong Kong Branch"
(a genuine suffix). The last holdout was "uSmart Securities" — a lowercase
brand — so the tail test accepts camel-case starts. Residual count: **0**.

**Stabilising managers, round three.** Two more filing shapes surfaced:
"NAME has been appointed as the Stabilising Manager" (Conant Optical names
Guotai Junan ONLY that way) and the filed absence "No stabilizing manager
will be appointed" (USAS Building, WITH a greenshoe — the desk's
greenshoe⇒manager rule has real, filed exceptions). Both parse now; a filed
absence is recorded as `stabilizing_manager_none` and its note states the
fact rather than an extraction shrug.

**Suspensions say so.** Many Idea Cloud (6696) last traded 2026-03-30; its
since-IPO print sat five months old with nothing explaining why. A price
frozen >30 days now writes `price_note` ("suspended or delisted; measured to
the final traded session").

**Every reason is now visible.** A sweep of `*_note` fields the merge writes
vs the workbook's NOTE_FIELDS found five that never rendered — `price_note`
itself, `eff_ff_note`, `eff_ff_shares_note`, `ipo_date_note` (the typhoon
note!), `stabilization_note` — "a blank with an unread reason is
indistinguishable from an unexplained blank". All render now.

**Freshness is a policy, not an accident.** 438 rows carry the Friday 08-28
close (inside the designed 7-day cache tolerance), 73 the Monday 08-31 close,
young listings are refetched on a 2-day leash, and `price_asof` states the
date on every row.

**Operational: this volume intermittently fails reads with TimeoutError
[Errno 60].** It killed one extraction run and one visual-gate run tonight —
the signature of Desktop-folder cloud eviction faulting files back in. A file
read once stays local, so every long stage now runs with up-to-3 retries
(`run_v26_final_chain.sh` pattern). If a stage dies mid-write with a timeout,
re-run it; the batches are regenerated whole, so a retry is always safe.

## GREY MARKET (v27) — 暗盤, and why it must be captured WEEKLY

The evening before a HK listing, brokers run an off-exchange session
(16:15–18:30) in the new stock. Its close is the last price before the
exchange opens, struck after allocations are out and anyone who wants out can
leave — so a deal that closes the grey market below its offer has already
broken issue in every sense that matters. It is the closest thing to a
forecast of day 1 that exists, which is why it now sits in the Database, the
screener comp table, the All-deals table, the explorer axes and the weekly
email.

**`fetch_greymarket.py` reads AAStocks' own standardised headline:**

    《新股》希音－Ｗ暗盤收報42.2元 低上市價13.1%

Machine-readable, and the same line the desk reads, so it can be eyeballed.
`grey_pct` is signed off the headline's own 高/低/平 wording — never inferred
by comparing prices. The quoted venue is Phillip's (輝立) platform, which is
what AAStocks reports; Futu's print differs by a tick (SHEIN closed 42.2 on
Phillip vs 42.12 on Futu), so `grey_venue` records which, and the two are
never mixed.

**THIS IS A CAPTURE-OR-LOSE FIELD — the single most important thing to know.**
**Superseded by the 4 October 2026 review:** historical published closing reports are accessible through stock-specific AAStocks news URLs, broker reports and newspaper archives. Capture promptly, but do not treat old blanks as unrecoverable. The original feed limitations were:
  * AAStocks' `greymarket.aspx` **ignores its own `?symbol=` parameter** and
    always renders TODAY's session; live quotes arrive over a websocket and no
    REST endpoint serves a past one.
  * The per-stock news list is server-rendered only for RECENT items; older
    pages are JS-paginated and eight pages deep still does not reach a listing
    six weeks old.
  * etnet's calendar is today-only and its news search 404s. No aggregator
    publishes a historical table.
So the batch is an **accumulating cache**: a captured value is never
re-fetched and never overwritten, because a re-fetch after the headline has
scrolled away can only ever LOSE data. `grey-market` is a stage in both
`ipo.py refresh` and the desk bundle. Run the weekly routine and the archive
builds itself; skip it for a month and that month is gone for good.

Two derived columns, because the raw close is not the interesting part:
`grey_to_day1_pct` measures the day-1 close FROM the grey close (how much of
the evening move survived the night), and `grey_called_it` is Y/N on whether
the grey market got the direction right. A deal with no headline on file
carries `grey_note` saying so — an explained absence, not a silent blank.


**v27.5 — three desk questions, answered from the data, not assumed:**
- *"A lot of 3-month returns are missing."* 43 of 514 at 8 Sep: 40 are listings
  from the last three months whose 63-session window has not elapsed (the book
  carries 103 deals from 2026, many from June onward), each with `ret_3m_note`
  saying so; the other 3 (Lung Fung, Dajin, Longbio, all listed 5 June) crossed
  their 63rd bar AFTER the last price fetch and fill on the next `h-paths` run.
  A blank 3m on a young listing is correct; a blank on an old one means the
  price path is stale — refresh, do not patch.
- *"Why is one stock's price-in-range negative?"* Global New Materials (6616):
  offer HK$3.25 against a HK$3.52–4.22 range, struck via HK's Downward Offer
  Price Adjustment (up to 10% below the floor). (3.25−3.52)/(4.22−3.52) =
  −38.6% of the range-width below the floor. The negative is the honest
  figure and the row's `range_note` says why; clamping to 0 would hide a real
  pricing event. It is the only such row.
- *"I only need grey market % vs offer."* The Database and screener now carry
  ONE grey column, in PERFORMANCE beside Day-1. `grey_close`, `grey_date`,
  `grey_to_day1_pct` and `grey_called_it` stay in `deals.json` (the analysis
  note and the email read them) but no longer ship as columns. Field parity
  between Excel and HTML re-verified with only `grey_pct` on both sides.
- The scoring-parity gate needs the `formulas` package in whichever venv runs
  it; a missing package reads as a red gate, which is what happened once.

**v27.6 — the scoring gate went red on a TIE, and the fix found a second gap.**
The `test_screener_formulas` gate compares Excel's comp #1 against a Python
reference scorer. It went red the day Xiaohongshu became the screener's
default pick: a PHIP applicant with no size, no P/E and no profitability
flag ties every same-subsector comp at the gate (1,000 + the A/H point). The
sheet adds `ROW()/1e6` to every score so `MATCH(LARGE(...,k))` never returns
the same comp twice — and that epsilon is also the tie policy: the later
Database row (more recent listing) wins, so Excel said TRIP.COM (Apr 2021)
while the reference's stable sort said Kuaishou (Feb 2021). The HTML scorer
already carried the same epsilon; the reference now does too. Nothing in the
shipped workbook was wrong; the test's oracle was incomplete.

Dumping the Calc rows to find that exposed a REAL divergence: `is_h_share` is
only ever set where an A line was found, so the workbook writes an unset flag
as "N" on both the Database and Pipeline tabs and scores it ("N"="N" → +W_AH).
The dashboard's JS treated null as UNKNOWN and scored 0 — so for a non-A/H
target the page never gave its non-A/H comps the 50-point match Excel gave
them, and the two products could rank a near-tied A/H vs non-A/H pair
differently. The JS now reads unset as "no pair", same as the sheet. The gate
gained a third leg: it drives the built dashboard with playwright, ranks the
same 40-deal slice with the page's own `similarityScore`, requires the same
comp #1, and scores a synthetic unset-vs-A/H pair requiring a gap of exactly
W_AH. Run against the pre-fix page it fails (gap 0); against the rebuilt page
it passes (gap 50). Three implementations, one answer, checked every ship.

## v28 (2026-09-09) — the workbook reads like a desk file, not a generator

The desk's read: the Screener's sections could not be told apart (every bar
was the same navy), the tabs carried too many footnotes, and the whole file
read as machine-written. What changed, and where to keep it that way:

**Screener section colours.** Each block has its own bar: TARGET navy, RANK
AND FILTER green, the comp table's band row in the same per-band tints as the
Database (deal terms green, demand gold, performance teal, fundamentals grey,
A/H burgundy, scoring grey), TARGET VS CLOSEST COMP slate, the two A-share
panels burgundy (the A/H colour), the side panels grey. Palette constants are
`F_SEC_*` and `BAND_TINT` at the top of `build_xlsx.py`; the `section()`
helper writes a bar. A new block gets its own `F_SEC_*`, never a reuse.

**Footnotes.** Rule: a label says what a cell takes; a note is for something
the label cannot carry. The Screener lost every hint beside its controls (the
gate, "drives demand-similar first", the rank-mode glossary, the live-panel
side notes, the cornerstone how-to block), the median-row footnote and the
"what it does" column. Tab intro lines are one sentence. The SM League intro
was a 20-line paragraph; it is three sentences. The Notes tab is the one place
for explanation and it was rewritten plainly.

**Wording.** No em-dashes, arrows or middle dots in cell text; no ALL-CAPS
emphasis inside sentences; titles are nouns ("STABILISING MANAGER LEAGUE",
not "STABILISING-MANAGER LEAGUE — how deals each bank defended traded").
Research inputs typed with dashes (`pipeline.json` statuses, A/H commentary)
are normalised at render time by `plain()` in `build_xlsx.py`, prose fields
only, never names. Column headers: "Notes on blanks" (was "Why anything is
blank"), "Day-1 open to close", "Index, IPO to 1m".

**Per-row notes (merge_batches.py).** Every explained-absence note was
rewritten as the reason alone, without the defence of the reason: "no
over-allotment option" (was "... in the offer structure, so no stabilising
manager is appointed"), "maximum offer price only, no floor published" (was a
sentence about what the filing publishes), "no archived print; add to
data/grey_market_manual.json" (was a five-line paragraph on 384 rows). The
"no A-share listing" note no longer renders in the notes column because the
A/H cells already read N/A; it stays in `deals.json`. One real bug surfaced:
the proxy A/H note printed a Python dict (`{'code': ..., 'name': ...}`) into
the cell; it now prints the proxy's name and code. Mean notes-cell length
351 to 292 characters. `Verify (BBG)` section D filters on "below the net
proceeds" (the note text changed with the rest).

**Stale legend fixed.** The Database intro and the Notes tab promised green
(cross-checked) and amber (judgment) fills that the Database has not painted
since the single-fill rule; the legend now says what is there: orange =
sources disagree, grey = calculated, blue = input. The Calc tab intro said
the Screener ranks on column H; it is K (`H_SCORE`), now read from the constant.

**Gates unchanged** and all nine green: label contracts are prefix-matched
(`audit_formulas.CARD_EXPECT`, the test's `row_of`), so "Subsector (ranks
first)" and "Force-include codes (9888, 2015)" still satisfy them. Off the
desk, look at a tab before shipping it: `python ipo_lib/render_xlsx.py --tab
"SM League"` renders the tab to out/render/ as HTML and, with playwright, a
PNG (fills, fonts, merges, widths; no conditional formats, no cached formula
values).

## v28.1 (2026-09-09) — the Pipeline tab, rebuilt as a stage table

The desk's read: "very ugly and unclear". What it was: 27 columns, most
blank for most rows; four populations (press rumours, PHIP applicants, live
offerings, a withdrawn deal) in one unordered list; 15-high rows with
prospectus prose spilling across neighbours; two applicants with no sector.

What it is now (`sheet_pipeline` in `build_xlsx.py`):
- **One stage per row, rows sorted by stage** in `load()`: Offering, PHIP
  posted, A1 filed, Reported, Withdrawn (`_stage()` reads the status text
  and the terms). Each stage has a row tint (`STAGE_FILL`) and a rule line
  where the stage changes. The order is fixed in `load()` because the
  Screener mirrors Pipeline rows BY POSITION (rows 6+); sort nowhere else.
- **Columns banded** like the Database (`PIPE_BANDS`, `PIPE_BAND_TINT`):
  DEAL, TERMS, PROFILE, A-SHARE (A+H only), BANKS & DOCS, NOTES. The US$
  lo/hi pair collapsed into one "Press size (US$m)" text column; "Status
  detail" dropped (Stage, the range and the offer period already say it).
- **Prose**: Business shows its first two sentences (`_lead`, 280 chars)
  with the full text in a cell comment; Valuation notes wrap in a 58-wide
  column; Size basis shows a label ("prospectus, net at max price", "press
  estimate") with the sentence in a comment. No fixed row heights, so Excel
  sizes rows to the wrapped text. Offer period shows dates only.
- **Contract kept**: the Screener resolves Pipeline column letters from
  `PIPE_COLS` by field, so columns can move; the fields it reads (name,
  sector, subsector, expected_size_hkdm, profitable_at_ipo, is_h_share,
  expected_timing, pe_expected_mid, a_share_code, a_price_now, a_pe_ttm,
  range_hi, expected_code) must stay in the list. `assert sum(PIPE_BANDS)
  == len(PIPE_COLS)` catches a band/column drift at build time.

**Wrong-paragraph business text.** Transwarp's "business" was the PRC
service-of-process boilerplate ("We are a company established under the laws
of the PRC and substantially all of our assets are located in the PRC...").
`extract_profiles.RISKY` now rejects "established under the laws", "assets
are located in" and "reside in the PRC"; both the PHIP parser and the
offering-window parser use `find_overview`, so one fix covers both. The PHIP
rows' generated instruction ("type it in the blue cell to rank comps on
size") is gone from the notes column.

**Listed deals leave the pipeline only via the routine.** Medcaptain (2041),
Longsys (9976) and Excelland (3231) sat as "Offering" after they had
listed because the book had not been refreshed; `pipeline_dedupe` drops a
row the moment its code is in the Database, and the Database only gains a
row from `ipo.py refresh` (allotment results) + `merge`. When a deal has
listed and still shows in the pipeline, run THE ROUTINE; do not hand-edit.

## v29 (2026-09-14) — incremental parsing, and the eviction that made it necessary

**What broke.** `ipo.py refresh` ran for two hours and never reached the merge.
Cause: iCloud had evicted the whole PDF cache (3,328 of 3,328 dataless, disk
at 91%), and every extractor re-reads EVERY deal's PDFs on every run. Each
evicted file costs seconds to materialise, so a 527-deal parse that used to
take minutes takes hours — and warming the cache first does not help, because
the volume evicts again while the pass is still running.

**The fix is incremental parsing, not a bigger cache.** `ipo_lib/incremental.py`
gives every extractor `--only 2041,9976` and `--new`: it parses those deals and
carries every other record forward from the existing batch, so the output is
identical in shape and nothing downstream knows the difference. Wired into
extract_prospectus (both kinds), extract_deep, extract_profiles,
extract_financials, extract_stabmgr, extract_shoe_cornerstone and fix_oversub.

```
# a normal week: the roster names three new codes
python ipo_lib/extract_prospectus.py allotments --only 2041,9976,3231
python ipo_lib/extract_prospectus.py prospectus --only 2041,9976,3231
python ipo_lib/extract_deep.py --only 2041,9976,3231     # etc.
python ipo_lib/extract_profiles.py --new                 # or: whatever the batch lacks
```
Three deals parsed in seconds against 527 carried forward, all counts intact.
THE ROUTINE still runs everything when the cache is warm; use `--only` when
the machine is evicting or when you know exactly what changed.

**FETCH ORDER MATTERS: prices read deals.json.** The three new listings first
merged with a day-1 from the AAStocks listed-IPO table, because `fetch_prices`
had run before the merge put them in the book and so never fetched them. Run
prices AFTER the first merge of a new listing, then merge again; the second
pass replaced all three with kline/Yahoo series and independently confirmed
the AAStocks figures (Medcaptain -42.93%, Longsys -1.02%, Excelland +153.84%).

**Business text: four more boilerplate paragraphs rejected.** The overview
extractor was quoting, as the business description, whatever paragraph opened
with "We are/We operate". Now rejected (`extract_profiles.RISKY`): PRC
service-of-process boilerplate; accounting-presentation prose ("our financial
statements are presented in RMB" — that was Forms Syntron); production
footprint with no product in it ("We produce and assemble our products at our
manufacturing facilities" — Medcaptain); and risk-factor openers ("market
acceptance remains uncertain", "we compete against a large number of
established competitors"). Net: 2041, 6700, 6727 gained real descriptions;
3231 lost its only candidate and now reads blank, which is honest — its
scanned pages carry no business sentence.

**Classifier vocabulary, from the filings' own words.** Optical interconnect
(transceiver / communication / network terminal) -> Smart hardware, the label
Innolight already carries; AI-and-big-data INFRASTRUCTURE software, data
warehouse, database, banking IT -> SaaS / enterprise software; hospital
equipment (infusion and syringe pumps, enteral feeding, anaesthesia,
endoscope, patient monitor, ventilator) -> Medical devices. That filled
9856 Ligent, 6727 Transwarp, 6700 Forms Syntron and 2041 Medcaptain without a
single per-deal hardcode. Where nothing matches (Zhejiang Taotao: e-bikes,
golf carts, ATVs — the taxonomy has no powersports home and the book has no
precedent), the row now SAYS "subsector not auto-classified; type one in the
blue cell" rather than showing a bare blank. Do not invent a label to fill it.

## v30 (2026-09-21) — a wrong offer price, and the identity that caught it

**THE BUG, and it was in the book.** Transwarp (6727) merged at HK$57.08. Its
allotment cover says `Final Offer Price : HK$49.00 per H Share`. The table
pattern was `Final\s+Offer\s+Price\s+HK\$(NUM)` — no colon allowed — so it
skipped the cover and matched the listing-expenses line, "based on Final
Offer Price HK$57.08 million". A price read off a MILLIONS figure.

Two rules now, everywhere a price is read (`extract_prospectus`): the label
may carry a colon, and a magnitude word after the number disqualifies it.
The magnitude guard has a trap of its own — a bare lookahead lets the engine
shorten the number until it passes ("154.99 million" matched as "154.9" +
"9 million"), so the digits are closed first with `(?![\d.,])`.

**The check that proves a price: shares x price = gross proceeds.** 14,010,800
x HK$49.00 = HK$686.53m, exactly the gross the same filing states. Run it
across the book whenever a price parse changes:

```python
# every deal with all three fields; >2% is worth reading
implied = gross_proceeds_hkdm * 1e6 / offer_shares    # vs final_price
```
25 of 241 fail it today; 22 are share-count problems the merge already
adjudicates (it rejects implausible offer-share counts for 19 deals). The
price-specific test is narrower: a price whose snippet is NOT anchored on a
"per Share" phrase AND which fails the identity. That is 3 deals, all three
verified correct (0999, 2521, 6831 — standardised table, gap is in shares).
Six records carried the magnitude trap; five had been silently overridden by
another source, so only Transwarp reached the book wrong.

**A CAP IS NOT A RANGE.** `extract_deep` emitted range 61.0-61.0 for a
cap-only filing, and the merge then read a HK$49.00 strike as a downward
offer-price adjustment — a filed event that did not happen. Both sides now
refuse lo >= hi: deep drops the invented floor, the merge clears it and says
"maximum offer price only, no floor published". Only 6616 is genuinely
downward-adjusted.

**ORDER WITHIN THE PARSE CHAIN.** `fix_oversub` patches extracted_allotments
IN PLACE, so re-running `extract_prospectus allotments` after it wipes the
table-anchored public/international split (Transwarp briefly showed a 73.86x
institutional book — the retail number). Always: parse-allot, then
patch-proceeds / patch-offer-shares / parse-subscription. STAGES has this
order; a manual `--only` run must keep it.

**OFFERING TERMS ARE PUBLISHED ONLY WHILE A DEAL IS OPEN.** The indicative
range lives on the HKEX New Listings page; the prospectus states a maximum
and the allotment announcement the strike. `fetch_newlistings` now appends
every row it sees to `data/batches/offering_terms.json`, never pruned, and
the merge reads it for range / lot size / offer period at priority 38 — below
the filing parse, so it fills gaps and never overrides. Transwarp listed
before this existed, which is why its HK$49-61 range is not in the book.

**Incremental fetching, not just parsing (v29 extended).** `fetch_hkex_filings
allotments|prospectus` and `fetch_bodies` take `--only` / `--new` too: one
network call per deal to read a document index is ~9 minutes across the book,
and 527 of 528 answers are last week's. This week's run: 2 seconds each.

**A+H detection on offering-window deals.** `fetch_newlistings` never ran the
A-share detector — it took `a_share_code` only from the hand-kept press file,
so Kinwong (603228, printed in its own prospectus) showed no A line. It now
runs the same `_a_share` the PHIP parser uses, and the code regex accepts
"under the stock code of 603650" (it required a colon or bare space). Four of
this week's seven offerings resolved: Kinwong 603228.SS, Red Avenue
603650.SS, RoboTechnik 300757.SZ, Forms Syntron 300468.SZ — each with a live
A price, A P/E and the H-cap-vs-A discount. No existing A code changed.

**A listed deal keeps its classification.** `extract_profiles` falls back to
the offering-window copy of the prospectus (`newlist_<code>_*.pdf`) when the
filed parts yield no overview — a brand-new code often has only that copy on
disk, which is why Transwarp listed with no subsector until this was added.

## v30.1 (2026-09-21) — reading the live offerings back, field by field

A live offering is the part of the book with no second source to correct it:
nothing has traded, no aggregator has published a return. Every number comes
from one prospectus parse, so each one was read back against the filing.

**A DEAL WITH NO SIZE.** All six offerings showed a blank expected size —
the first thing the desk looks for. The size was derivable all along: every
row carries `offer_shares`, and the cap is on the page. `size_at_cap_hkdm =
offer shares x maximum price`, the same ladder the Database uses for a struck
deal, labelled "offer shares x maximum price". Kinwong HK$5,097m, RoboTechnik
HK$5,178m, Ligent HK$5,670m, Red Avenue HK$2,997m, Direct Drive HK$1,080m,
Forms Syntron HK$943m.

**A FIXED-PRICE OFFERING STATES ONE PRICE.** Ligent and Direct Drive showed
no price the day before listing because the range patterns only knew "HK$A to
HK$B" and "Maximum Offer Price of HK$X". Their filings say `Offer Price :
HK$32.96` and `HK$21.60`. Added, with the same magnitude guard as the
allotment parser, and labelled "fixed-price offering (no indicative range)".

**THE A+H PROSPECTUS QUOTES THE H TRANCHE, NOT THE COMPANY.** Red Avenue:
"Market capitalization of the H Shares following the completion of the Global
Offering". Forms Syntron: "Market capitalization of our H Shares". An
expected P/E built on that is wrong by construction, and it was: Forms
Syntron read 8.7x where its own A line prices the same earnings at 15.7x at
the H cap. Both workbook and dashboard now prefer `pe_at_h_cap` (A P/E TTM x
the H-cap-vs-A discount) whenever an A line exists.

**TWO SANITY TESTS ON ANY STATED MARKET CAP**, because the phrase also sits
beside listing-rule thresholds and proceeds figures: a range spanning more
than 3x is not a price range (Ligent's "HK$4bn-32.4bn", an 8x spread), and a
company cannot be worth less than the offering it is selling (Forms Syntron's
"HK$824m" against its own HK$943m deal). A rejected cap takes its derived
P/E and P/S with it, and the row says why.

**A REJECTION HAS TO SURVIVE THE NEXT RUN.** `fetch_newlistings` backfills
each record from the previous batch, which quietly resurrected both the
impossible market cap and Red Avenue's "revenue 0" — note and all. The parse
now records `_rejected` and the backfill skips those fields. A zero revenue
beside a positive net income is itself a failed parse, not a pre-revenue
issuer, and is dropped with a note.

**WITHDRAWN IS NOT OFFERING.** The dashboard badged EKH — pulled 2026-07-08 —
as OFFERING NOW and ranked it first, because `/OFFERING/i` matches the word
inside "WITHDRAWN — offering pulled 2026-07-08". One `isPulled()` helper is
now checked first in all four places the page tests status.

**pypdf SPLITS WORDS: "semicondu ctor", "pho toresist", "h igh-performance".**
`extract_profiles._mend_split_words` rejoins a pair ONLY when the joined token
appears elsewhere in the same document, so nothing is invented and "end
market" stays two words. Two lessons in the implementation: a regex sub
consumes both words of a match, so "sale reve nue" tested "sale"+"reve",
failed, and never tried "reve"+"nue" (it walks token pairs now); and a guard
that skipped joins when the split form also appears in the document blocked
exactly the case it exists for, since the artifact repeats within the filing.

**The off-terminal viewer was lying about prices.** `render_xlsx` read any
format containing "0.0" as one decimal, so a HK$32.96 offer price (format
"0.000") displayed as "33.0" and looked like a P/E. Decimals now come from
the format string itself.

## v31 (2026-09-23) — the allocation outcome, the listing-day tape, and the 套路回撥 study

The desk asked whether 27 small deals popped on day one because the placing
was held under 1x so retail got almost nothing. The answer is in
`TO_NOMURA/Clawback_Study.docx` (regenerate: `python ipo.py clawback-note`);
this entry records what the book gained and what it taught.

**THE INTERNATIONAL MULTIPLE NEEDED PROVING.** For 20 of the 27 the evidence
snippet beside `oversub_intl_mult` quoted the PUBLIC offer's table, so the
number could not be trusted on its face. `ipo_lib/extract_allocation.py`
reads every allotment notice's own INTERNATIONAL OFFERING section, anchored
on the placee count, plus the final public/international split and the
notice's "Claw-back triggered" line. Values held for 24 of 27; Midea's 0.11x
was a threshold read off the clawback rule table (real: 8.06x, 236 placees).
New book fields: `intl_placees`, `public_alloc_pct` (the public tranche's
share of the offering AFTER reallocation), `clawback` (YES/NO/NA from the
notice; derived from the split only when unambiguous, >=28% or <=12%),
`reallocated_from_intl`. Three DEMAND columns in the workbook.

**THE LISTING-DAY TAPE.** `ipo_lib/fetch_day1_tape.py` pulls the listing-day
bar (open/high/low/close/VOLUME) from Tencent's kline for every deal, with a
Yahoo fallback and a checkpoint every 50 (Tencent answers HTTP 501 after
~300 rapid calls; the first pass lost nothing because the second pass filled
the rest once the block lifted). Derived: `day1_vol_x_retail` = day-1 volume
/ shares the public tranche received, and `day1_range_pct`. Two PERFORMANCE
columns. This is the distribution gauge: ~1.5x means the placees held, 2.5x+
means they sold into the open.

**THE MECHANISM, AND WHERE IT IS WRITTEN.** The PN18 clawback (retail to
30/40/50% at 15x/50x/100x public cover under the old rules) applies only "if
the International Offering is fully subscribed or oversubscribed" (AB&B
prospectus, Reallocation and clawback). At 0.99x it does not, and the
coordinators reallocate the placing SHORTFALL only. Measured on 100x-plus
public books: old rules, placing covered — retail 50.0%, median open +2.7%;
old rules, placing 0.85-0.99x — retail 17.8%, open +53.3%; new rules
(Mechanism B), placing covered — retail 10.0%, open +36.4%. The trick was a
2024-25 phenomenon (14 and 9 deals) and Mechanism B made it unnecessary (2 in
2026); the starved open it produced is now the default for every hot deal.
`analyse_clawback.py` computes all of it; the numbers in the note are not
typed.

**GREY MARKET: 20 hand-verified prints now, 150 in total.** 12 were added
for the desk's list from press reports of the evening session (HKET, Sina,
163, 華盛通, StockFisher, Futu), each reconciled to its offer price. The
manual file accepts a RANGE (`grey_close_lo`/`grey_close_hi`) where the press
gives the three venues' spread; the merge shows the midpoint and the note
says so. A grey OPEN is not a close and is not recorded (WK Group +144%).
Still missing: Ruichang, Healthyway, Huaibei, Deyun — no retrievable print.

**PRE-ALLOTMENT DATA EXISTS FOR THE PUBLIC TRANCHE ONLY.** Brokers publish
running margin totals during the offer and the press aggregates them daily
(Shougang Lanza: 36x on day two, 1,133.5x margin-only at close, 1,421.5x
final; AB&B: 225x day one, 629x close, 4,007.6x final) — a floor at roughly
half to four-fifths of the final. Nothing is published for the placing until
the allotment notice, the evening before listing. The book does not capture
the margin prints yet; `offering_terms.json` is where they would go.

**Lessons for the parser (all fixed).** RISKY missed "highly competitive AND
FRAGMENTED industry" (Ligent listed unclassified for an hour). Full-width
colons ("Global Offering ： 97,625,000") broke the total-shares pattern;
notices that print "% of Offer Shares under the Hong Kong Public Offer to
the Global Offering 15.20%" are read directly now. A --only run on a batch
another process is still writing loses the race (extract_allocation for 9856
had to be redone after the full pass); wait for the full pass first.

## GREY MARKET COVERAGE — what is reachable, measured (v31.2)

456 of 519 deals carry a grey-market close (261 in v31.1). By listing year:
2021 42/92, 2022 68/72, 2023 60/68, 2024 67/67, 2025 111/112, 2026 108/108.

| source | what it holds | floor | prio |
|---|---|---|---|
| hand-verified press (`data/grey_market_manual.json`) | one print, source named | — | 70 |
| etnet `ipo-info.php?code=NNNNN` | 暗盤數據 table: all three brokers' close + volume | **2 October 2024** | 50 |
| **etnet news wire, by article ID** (`fetch_etnet_grey_news.py`) | the evening story, 輝立暗盤收報X元 | **January 2021** (older untested) | 48 |
| AAStocks headline (`fetch_greymarket.py`) | 《新股》…暗盤收報… | ~21 articles per stock | 45 |
| AAStocks greymarket.aspx, broker pages | live quotes | today only | — |

**The etnet news wire is the archive nobody lists.** Every etnet article
resolves by ID at `ipo-news-article/{YYYYMMDD}{NNN}/x`, NNN = 001-999, all
sections, back to at least January 2021. The sequence is NOT time-ordered,
so the fetcher reads a whole day's headlines (the `<title>` sits in the first
2 KB of a 450 KB page; it streams and stops), then reads in full only the
暗盤 stories. Two days per deal: the grey-session evening (whole day) and the
listing morning (001-259). ~30 s per day at 64 threads; 310 days = one hour
with four workers. Title cache: `scrape/etnet_news/{date}.json`; the result
is TRACKED in `data/grey_market_etnet_news.json` (the capture is the archive).

    python ipo_lib/fetch_etnet_grey_news.py            # every deal without a print
    python ipo_lib/fetch_etnet_grey_news.py 2410 9885  # named deals
    python ipo_lib/fetch_etnet_grey_news.py --parse --refetch-empty

Parsing rules, each learned from a real story:
- The print is **Phillip's CLOSE** (收報/收市/收於). Other venues' quotes in the
  same story are live (現報/暫報) and only context. A Futu or Bright Smart close
  is used only when the story has no Phillip close (和譽 2256: Futu 11.56).
- **An open is not a close.** Through mid-2021 etnet often reported only the
  grey OPEN (開報/開市價). 33 deals: no number, the note gives the open.
- **Every quote must reproduce the story's own percentage** (貝康 2170: the
  body says 開報230元 for a HK$27.36 deal, the headline 40元; rejected).
- **The deal is the code that lists next.** A spin-off story names its parent
  first (微創醫療(00853)分拆旗下心通醫療(02160)); a wrap-up names several; each
  quote goes to the nearest listing deal before it. "Next" = up to the next
  HSI bar, because 13-Oct-2021 (typhoon) has none but deals listed.
- 2021 wording splits venue and verb by a comma (據輝立交易場顯示,…收報58.25元);
  stories carried from 《香港經濟日報》 have no wire dateline (body = after
  the headline's last appearance).
- The PERCENTAGE is computed at the end of the merge, after the offer price
  is adjudicated: 玄武雲 2392 and 健世 9877 were parsed at the range top
  (6.91, 28.80); the stories quote 6.24 and 27.80, the adjudicated prices.
- One venue across the book: a hand entry from another venue yields to a
  Phillip close from the wire, and the venue cell names the other print
  (茶百道: "Phillip…; Bright Smart closed 16").

Validated: every overlap matches to the cent — etnet's table (FWD 36.75,
Anjoy 59.6, Phillip row) and the AAStocks headline (天聚地合 110.5, 泓盈 3.57).

**Historical v31.2 snapshot — 63 were blank; superseded by the 4 October 2026 review below:**
- 33 open-only (31 in H1-2021): etnet printed the open, never the close.
- 7 of the first FINI deals (Dec-2023: 國鴻氫能, KCASH, 升輝, 瑞浦蘭鈞, 泛遠, 集海,
  瀾滄): etnet ran no price stories for them. The one HKET piece it carried
  (20231205512) says only that the first batch traded in the grey market
  before their allotment results were out, with no prices.
- 22 with no story at all (mostly 2021 property services, biotech -B, 保誠).
- 1 follow-on offering with no grey session (BOSS 2076, `grey_market_na.json`).

Historical access failures, not a permanent prohibition on retrying: AAStocks `NOW.{id}` before
~2024 (0 of 160 probes resolve); HKET inews (403 / human check); Zhitong (JS
challenge); jisilu (history is member-only); Eastmoney search API (canned
response); Futu post IDs (~30k a day, no way to target a date); web search
(headline only, no price to reconcile).

RULES when adding by hand: the close divided by the offer price must
reproduce the stated percentage (the merge rejects it otherwise); a grey OPEN
is not a close; where the press gives only the three-venue range, use
`grey_close_lo`/`grey_close_hi` and the merge shows the midpoint and says so.

`ipo_lib/fetch_etnet_ipo.py` also brings back the one-lot hit rate
(一手中籤率) and etnet's own final HK/international split, which cross-checks
the allotment parser: 229 deals have both and 1 disagrees (9615, worth a look).

## v31.3 (2026-09-29) — a live deal arrives with every field, and the bank columns are whole

**The desk's complaint, verbatim: "everytime you're like blank."** Three
separate defects produced the blanks; all three are fixed in code, not by hand.

1. **The offering-window parser never filled a bank.** `fetch_newlistings.
   deep_parse` read `parse_syndicate()`'s result by the keys "sponsors" and
   "bookrunners", but that function keys by the FILING's role wording ("Joint
   Sponsors", "Sponsor-Overall Coordinators", "Joint Bookrunners"). Nothing
   ever matched, so every live deal reached the Pipeline with no banks. Now
   read by role, with the Database's rule (a Sponsor-Overall Coordinator is the
   sponsor's affiliate acting as coordinator — a bookrunner, not a sponsor),
   then scrubbed by `clean_party_list`. AAStocks' deal page fills whatever the
   prospectus leaves (sponsors, the whole syndicate, cornerstone names/amounts)
   and `*_src` says so.
2. **The greenshoe was never read for a live deal**, and a deal with NO shoe
   showed blank. Now `parse_greenshoe_pct`, and where the prospectus has no
   over-allotment option at all it is recorded as 0 with the reason (ESWIN
   1256: an Offer Size Adjustment Option — an upsize — and no stabilisation).
3. **Pipeline and dashboard had no column for them.** Pipeline gained
   Cornerstone investors, Greenshoe %, Lot size (TERMS) and Bookrunners (BANKS &
   DOCS); the dashboard card shows Sponsors, Bookrunners and Lot size.

Also for live deals: Chinese name from AAStocks' upcoming table (HKEX's
bilingual feed carries a code only once it trades); cornerstone % from the
committed amount at the maximum price when the filing states only the amount;
**the whole-company market cap**, not the H-share line — ESWIN's statistics
table states both (H HK$15.0-16.1bn, all shares HK$32.5-35.0bn) and the first
match made its P/S 5.6x instead of 12.2x; risk-factor openers ("We operate in a
competitive market subject to an evolving landscape") rejected as a business
description, and a rejected overview no longer backfills from last run.

**Database bank columns.**
- *Bookrunners* fell back to AAStocks' underwriters CUT TO SIX names when no
  bookrunner list had been parsed — 75 deals showed a partial list that read as
  the full one. The fallback is now the whole syndicate, and the 140 deals with
  no parsed list were re-parsed (`extract_deep.py --only`): the parser reads
  them fine from the cached text; the stored batch simply predated it.
- *Sponsors* showed the prospectus parse only — blank on 134 deals whose
  English name did not parse, while AAStocks had it. The column now shows the
  best available (`sponsors_display`); the note column says which source.
- Prudential 2378 prints its banks as logos (no text): filled from its RNS of
  19 Sep 2021 via `press_figures.json`, which now accepts `bookrunners` and
  `sponsor_note` (no sponsor: an already-listed issuer's offer).
- The role scrub missed "Capital MarketS Intermediaries" (plural) and left
  "and Capital Markets Intermediaries CLSA Limited" as a bank name.

**Three systemic bugs found on the way (all fixed in code):**

1. **Reused stock codes hid 55 prospectuses.** `load_stock_ids()` read HKEX's
   active list, then the INACTIVE list over it, so a reused code (華曦達 0901,
   Midea 0300, JD Logistics 2618, HUTCHMED 0013, Innolight 3308, FWD 1828 …)
   searched under the DELISTED company's id and found no prospectus.
   `load_stock_id_candidates()` keeps every id a code has held (live first) and
   the prospectus search tries each until one filed in the deal's own window.
   534/534 deals now have their prospectus; sponsor lists 375→423, bookrunner
   lists 390→437, business descriptions 380→427, revenue 421→472.
2. **`incremental.merge()` wiped a batch when `--new` found nothing new.** It
   tested `if not only`, so an EMPTY set read as "all deals" and the batch was
   rewritten with zero records — `etnet_ipo.json` (244 grey tables and every
   one-lot hit rate) went this way on 29 Sep and was re-fetched. Now `only is
   None` = all; an empty set carries everything forward.
3. **Cornerstone % was sometimes the largest PLACEE, not the cornerstones.**
   The allotment parser read the "Top 1 / Top 5 / Top 25 placees" concentration
   table (names like "are issued) Top", "Subtotal"). `fill_cornerstones.py`
   reads the notice's real cornerstone table: the printed Total in the "% of
   Offer Shares" column (prio 75), else the rows summed (68), else cornerstone
   shares over offer shares when the table only has "% of H shares" (66); a
   lock-up table count 60; a complete prospectus with no cornerstone section =
   0% "no cornerstone tranche" (65). A computed % from a table that found fewer
   investors than AAStocks lists is discarded (a missed row reads low). Fixed,
   e.g.: KCASH 2483 24.7%→0 (no cornerstones), 方舟健客 6086 28.6%→0, 博泰 2889
   22.8%→43.56%, IFBH 6603 78.3%→26.76%, 軒竹 2575 78%→9.81%, 綠茶 6831
   5.71%→50.0%, 紫金黃金 2259 1.6%→49.9%. Muyuan 2714 reads 45.25% of the
   FINAL (upsized) offer where the press quoted 50% of the base.

**Refresh speed on an evicted cache.** `fetch_hkex_filings allotments|
prospectus` without `--new` makes one throttled network call per deal (534);
the routine runner now passes `--new` (5 new deals: 25 s instead of ~15 min).
6700 Forms Syntron had listed on 22 Sep without reaching the Database — the
roster had been fetched before its debut; this refresh graduated it.

## THE WEEKLY EMAIL (v26.3) — one command, Monday morning

```
python ipo_lib/make_weekly_email.py            # 2-week lookback (default)
python ipo_lib/make_weekly_email.py --weeks 1  # last week only
```

Writes `out/weekly_ipo_email.html` and `.txt`. Open the HTML in a browser,
select-all, copy, paste into Outlook — the styling is inline, so it survives
the paste. The text version is there for anyone who prefers plain mail.

**Two sections, in the order the desk reads them.** *Coming up* is every deal
in its offering window or listing within ten days: terms, cornerstone %,
book-close and listing dates, then the line saying your notes are attached.
*Listed in the last N weeks* is one block per debut: the book (public/instl),
the day-1 open AND close, where it stands now against the offer, and the shoe.

**The shoe line is the point of the whole thing.** For a live deal it prints
who runs it and the filing's own stated expiry with a countdown — "Goldman
Sachs runs the shoe — support can run until Sat 26 Sep (22d left)". Once the
notice lands it prints the outcome instead (exercised in full = the price
never needed support; lapsed = stock was bought back to hold the line). That
date now comes from `stabilization_end_date`, parsed out of the allotment
announcement in three real-world shapes: "26 September 2026, being the 30th
day after…", the US order ("September 26, 2026" — Mech-Mind), and the
trailing parenthetical ("(which is Saturday, September 19, 2026)" — Ingenic;
SHEIN writes "which is expected to be"). Never inferred as listing+30.

**Colour is hand-written, never generated.** `data/weekly_email_notes.json`
holds one or two sentences per stock code; the generator prints them under
that deal and invents nothing. A code with no entry simply shows its numbers.
Append to it as you form views — that file IS the analyst layer of the email,
and it is what stops the note reading like a machine wrote it.

Sector falls back to the filing's own industry string for applicants the
taxonomy has not classified yet (Longsys listed as "Semiconductors &
Semiconductor Equipment"), because an empty sector cell in a client-facing
note reads as a mistake rather than as an absence.

**`stabilization_end_date` is a first-class column now** — "Shoe ends (filed)"
in the Database and the dashboard's deal brief, not just a line in the email.
Coverage went 32 → **276 of 514** once the parser learned all three shapes;
the jump is the point, because the date is not derivable any other way. Do NOT
be tempted to compute it as listing + 30: the anchor is the last day for
LODGING APPLICATIONS, not the listing, so the true gap runs 17–45 days. Six
deals sit outside the usual 20–50 day band and every one was checked against
its filing — e.g. 1440 says "expire on Saturday, 30 January 2021" for a
13 January listing, exactly 17 days. Parsed, not guessed.

Blank expiry maps to `shoe_note`, which now also covers the case the gate
caught: a deal whose over-allotment outcome is ALREADY published but whose
announcement never spelled the expiry out — the date is moot once resolved,
and the note says so rather than leaving an unexplained hole.

## File map (what to never delete)

- `data/deals.json` — canonical output (regenerated by merge; safe to rebuild)
- `data/batches/*.json` — SOURCE-OF-TRUTH caches; deleting one forces a slow
  refetch, deleting `stabilization.json`/`aastocks_deal.json` costs ~an hour
- `scrape/text_cache/`, `scrape/pdf_cache/` — parsed filings; large but cheap
  insurance, keep
- `ipo_lib/classify.py` GROUPS + `fetch_phip.py` PIPELINE_LABELS — the analyst
  judgment layers; only ever extend
- `TO_NOMURA/` — regenerated by `ipo.py export`, never edited by hand


## 3 October 2026 refresh — v31.4, sponsor/cornerstone completeness

Current deliverables contain **524 listed deals and 13 pipeline entries**. The latest
listed deal is Camsense 6802 (30 September); HKEX's roster was checked through 3 October.
Prices extend through the 2 October trading session. Original research caches remain
append-only. A before-refresh backup is retained in `backups/2026-10-03-before-refresh.zip`.

**Sponsor and cornerstone display coverage is complete on the Database tab.** There
are 386 deals with cornerstone investor names and 138 verified cases with no cornerstone
tranche, shown explicitly rather than left blank. Every listed deal has a cornerstone
percentage. Nine apparent missing-name cases were caused by the name cleaner rejecting
legal names longer than 70 characters. The cleaner now preserves long entity names and
all investors, while rejecting concentration-table headings and numeric debris.
Camsense's final allotment gives 1,869,200 cornerstone shares, 16.13% of the final offer,
allocated to GoldenLink and Taiwan ZMAX; its manual record retains the filing URL.
Manual/filing cornerstone lists must not be replaced by lower-priority AAStocks lists.

**Prudential 2378 requires an explicit N/A sponsor.** Its September 2021 offer was by
an existing listed issuer, and the prospectus's parties section does not appoint a
sponsor. Do not turn its financial adviser or underwriting banks into a sponsor.
Pipeline overall coordinators likewise are not automatically sponsors: only an explicit
"sponsor-overall coordinator" role supplies both. Pipeline banks are labelled
"Bookrunners / OCs" and undisclosed sponsor names remain "at launch".

**Pipeline identity:** use `company_key` with geographic prefixes removed and both
listed short/full names considered. A first-word match incorrectly removed Transsion
because Forms Syntron also starts with Shenzhen; matching provincial prefixes could
similarly suppress Sinomags or Taotao. Six active PHIP rows now remain, alongside one
live offering, four curated applicants, one postponed offer and one withdrawn offer.
Forms Syntron 6700 is postponed and EKH 2523 withdrawn: the older v26 statement saying
Forms had listed is superseded. Neither belongs among completed listed deals.

**Latest financial tables:** RA Materials 9607 requires repairing a whitespace-split
thousands separator. Robotechnik 3757 uses the consolidated Group table, not the acquired
ficonTEC subsidiary. Direct Drive 6731 uses the reported IFRS loss, not adjusted loss.
Camsense 6802's FY2025 profit is RMB2.201m (HK$2.4m using the project's 1.10 conversion),
so its extreme trailing P/E is real. `ni_filing_verified` in the source record allows
that checked denominator to survive the automatic 300x extraction sanity cap; it is
not permission to waive the cap for unverified rows. Each manual record links its
specific prospectus and page.

**Export reproducibility:** `make_bundle.py` now includes the manual sponsor/cornerstone
fills and other merge inputs used by the Mac. A clean unpack and re-merge reproduced
all 524 codes and the 11 checked fields. The regression suite in
`tests/test_refresh_regressions.py` covers long names, table debris, split numeric
columns, company identity, and explicitly stated bank roles. All five cases passed.
The final export also passed all nine existing validation gates, including Excel's
computed formulas, HTML/Excel field parity and light/dark visual checks. The premium
chart's current-value annotation was moved to avoid overlapping the IPO label.

Refreshes preserve manually verified research in `data/cornerstone_fill.json`,
`data/banks_fill.json` and `data/batches/press_figures.json`. Make fixes in those source
records or extraction modules, then merge and export; never patch the generated
workbook or `data/deals.json` directly. Word research studies were carried forward
unchanged; they remain separately maintained research documents.


## 4 October 2026 review — v31.5, returns and Day-1 benchmark

- Independently downloaded raw Tencent histories for all 524 listed deals through the last completed HK session, 2 October. The primary endpoint was supplemented with Tencent's official proxy for 12 blocked responses; no audit failures remain.
- Confirmed price-only Day-1, 1-week, 1-month and 3-month returns, including split/consolidation scaling. Horizons remain **5/21/63 traded sessions after debut (debut = 0)**, not calendar anniversaries; dividends and entitlement value are excluded. Each Database horizon cell now comments its exact date or pending reason.
- Corrected seven stored horizon dates across Morimatsu (2155), YZYBIO (2496) and Medcaptain (2041). Align benchmark legs to these exact dates, use the previous trading close as the offer-period anchor, and choose the benchmark after final sector classification. Four source-cache debut records now resolve the exact debut instead of a later/missing quote.
- Refresh all 524 last closes from the fresh raw feed; 56 Since IPO values changed materially. Keep actual last-trade dates for halted or thin-history stocks instead of assigning a current carried-forward quote. MIRXES and Sanxun suspension evidence is retained in prices.json.
- Add **Benchmark index Day-1** directly beside Day-1 in Database/Screener and the HTML table/comparison/explorer. It is the existing sector benchmark's percentage return from the previous trading close to the listing-day close, not an index level. Durable benchmark_prices.json is included in the desk bundle so offline re-merges reproduce the same values.
- Recover 57 additional verified grey closing quotes (now 518 numeric closes); preserve source/date/venue and show them in cell comments. Missing closes remain unverified/no-session, never zero. Newspaper/broker archives can resolve historical blanks despite earlier runbook claims.
- Two opening prices (2629, 1276) differ between the existing validated source and the new Tencent feed. Retain the existing opens and explicitly flag the variance; closing-price returns agree.
- New price pulls exclude in-progress sessions and zero-volume stock carry-forward bars. Cache checks track the latest completed session, including stocks with an old actual last trade.
- The three Word studies and weekly email are carryovers from 3 October; they were not regenerated with the expanded grey sample. Treat the workbook/HTML and dated review report as current.

Read out/data_review_2026-10-04.md for counts, corrections, remaining grey gaps and validation. Historical v31.2 counts/dead-end notes above describe the old capture, not current coverage.

**Suspension-window correction:** ALSCO Pooling (2649) has only 15 traded sessions after debut before suspension on 30 March 2026. Clear its spurious flat 1m/3m returns and derived index/alpha/ex-pop legs; keep its last-trade Since IPO return. Checked traded-session counts now overrule carried-forward cached horizon quotes.

**Abbisko trading debut (2256):** formal listing was 13 October 2021, but the company confirms first share trading on 15 October due to the typhoon closure. conflict_rulings.json adjudicates the database IPO/debut date to 15 October, with the formal date retained in ipo_date_note. Price paths are rebased to the actual trading date; Day-1 benchmark now resolves for all 524 deals.

## 7 October 2026 — A/H Stored / Bloomberg selector

The A/H sheet now has one macro-free source dropdown at **E4**, alongside the H/A chart-code selector at B4. Default is **Stored**. This switch controls A/H requests only; IPO Live, Screener and the verification tabs retain their Bloomberg formulas.

- Stored uses `ah_study.json` and each pair's own H trading dates. The latest premium uses A and FX closes aligned to the final H close, never a mixture of saved and current quotes. The snapshot currently ends on 2 October 2026; A/FX dates can precede it over holidays.
- Bloomberg activates the A/H BDP and three separate BDH anchors. Histories are raw price closes (`UseDPDF=N`, cash and capital adjustments off), ordered ascending. Match the last A/FX date on or before each H date; existing carry limits are ten calendar days for A and five for FX. A complete live quote can append today's point.
- Both sources calculate **A close (CNY) × CNYHKD ÷ H close (HKD) − 1**. IPO premium remains the H offer-price comparison. Share-class ratio exceptions remain explicitly withheld.
- Bloomberg history that is unavailable, stale or fails the raw debut-price check leaves the chart unavailable and identifies the reason. It does not silently use a saved chart under a Bloomberg label. Switching to Stored ignores any lingering Bloomberg output.
- A same-date comparison below the chart reconciles all overlapping H/A/FX closes and actual A/FX dates against the selected pair's snapshot. Price tolerances are max(0.005, 0.005%) for each equity close and 0.00005 for FX. Differences are reported for review, not forced equal or overwritten.
- `tools/create_market_template.mjs` authors the selector's layout with Artifact Tool; the existing native workbook assembler preserves Bloomberg functions, dynamic chart names and the Excel date axis. `apply_desk_styles.py` saves a truthful dated opening cache, including the Stored latest-premium column.
- `tools/test_monitors.py` checks all 62 selectors, all 18,045 saved H observations, premium mathematics, source switching, unavailable-history handling and same-date equality/mismatch detection with explicitly simulated Bloomberg inputs. Live Bloomberg responses still require a Bloomberg-enabled Excel session.

Canonical deal data, classification, return calculations and HTML snapshot data are unchanged by this edit. The standalone desk bundle includes the source-selector implementation and layout template.


## 7 October 2026 — complete numeric review, subscriptions and lock-ups

The latest working data contains 524 listed stocks. `data/batches/subscription_review.json` reviews every public tranche and 521 institutional tranches against current HKEX allotment files, with document hashes, pages and snippets. JBM Healthcare 2161 was public-offer-only; UJU 2439 was under-subscribed without a numeric placing multiple; Prudential 2378's filing did not establish a numeric book multiple. Do not restore the former invented/repeated institutional figures. Camsense 6802 public demand is **3,546.91x**, not 5.53x. Direct Drive 6731 institutional demand is **2.72x**, not the retail 208.56x. Public-only, employee/preferential and Pool A/B figures must remain distinct. The quoted legacy “over-subscribed by” wording retains its basis note; do not add one blindly.

The numeric audit covers all scalar database values. `out/database_numeric_audit.csv` is the full field/source ledger, `database_numeric_changes.csv` lists material differences from the prior delivery, and the JSON/Markdown describe unresolved primary confirmations. A passing arithmetic check is not a certification of a retained source. **273 annual revenue/profit figures still lack an unambiguous fresh primary-row confirmation**; they keep their researched source and orange Excel cue with a source comment. Cornerstone investor-group aliases also require confirmation where the filed legal name differs. No claim that every value has been primary-source verified should be made.

Financial annual-row reviews are in `financial_number_review.json`. Fiscal-year headers determine the annual column; never take the third number indiscriminately from a two-FY-plus-interim table. Explicit currency and units are mandatory. Owner-attributable earnings take priority for P/E; a consolidated-profit fallback is labelled as a proxy. The project uses fixed HKD conversion approximations, RMB×1.10 and USD×7.80. Tian Tu 1973 retains its documented total-income proxy. P/E and P/S are recomputed after correction and are withheld for losses/zero revenue. Reviewed low earnings can create a real high multiple and must not be deleted solely by a 300x heuristic. Controls in PDFs must be removed from XML comment strings.

Offer-number review distinguishes the **base offering** from proceeds including over-allocation. KCash 2483, Lancang Tea 6911 and Dida 2559 print proceeds that include extra shares; base gross figures are 225.0m, 224.7m and 234.546m HKD. Printed amounts and their bases survive separately. SDMC 0901's evening filing was truncated; the complete 27 May 2026 morning filing `2026052700001.pdf` is now also in its manifest. The roster retains supplemental same-deal allotment links without moving the listing-date estimate to the next day.

Cornerstone review covers all 524 stocks, with 138 no-tranche cases reviewed against prospectus/allotment context. Partial table parses cannot replace a complete group list or percentage. Connected clients and waiver allottees are not automatically cornerstone investors: Tongshifu 0664's single cornerstone is **6.75%**, and the following consent table must not be included. Kinwong 3228's filed total is **34,788,400 shares / 47.69%**; E Fund's group total must be counted once, while both E Fund subscribers and Zhongji Innolight's VERTEXVEST vehicle are disclosed in the names. HTML and Excel use identical canonical lists and percentages, including explicit no-tranche text. Subscription displays retain two decimals and up to three when filed; cornerstone percentage displays use one decimal.

Tab order is IPO Live, AH, Lock-up, Screener, Database, then reference sheets. IPO Live keeps five visible columns. **B5 selects Sector/Subsector**, and **H34 selects the broad sector for the second subsector-average chart**. The first chart remains the nine broad-sector averages. Changes exclude unavailable quotes and zero previous close. AH retains **B4 code selection / E4 Stored or Bloomberg**, with Stored default; 62 pairs, date-aligned A/H/FX snapshots, history to listing-to-TODAY in Bloomberg mode. Screener freezes only columns A:B (`C1`), with no row freeze. Existing professional band colours remain.

`lockup_events.json` holds **1,064 group/date rows**, **770 dated events**, covering every stock. There are **240 dated cornerstone schedules**, **156 unestablished cornerstone expiries**, and **138 no-tranche cases**. This is the original filed schedule, not a record of actual sales or later waivers. Display the LAST day locked; the first day after is in the date's comment. A six-month date is derived only where the filing explicitly says “from and including” (or “inclusive of”) listing. Controller second-period restrictions can concern loss of control, rather than all sales; keep their label distinct. The delivered Excel and HTML windows use exactly seven HK trading sessions; there is no calendar-day selector. Internal calendar-window comparisons remain in the evidence batch for review. Anchor the last completed session on/before expiry; require exact, positive-volume endpoint closes; no carry over suspension gaps. Compound all splits from the common action loader. Price-only returns exclude dividends/rights value. Upcoming events have no before/after numbers. Snapshot is through **2 October 2026**.

`refresh_filing_reviews.py` reviews cached sources for new stocks; `refresh_lockup_windows.py` updates incomplete event windows. Both run in Mac and bundled refresh workflows. Completed exact windows remain stable. Source-review modules and evidence batches are embedded in the standalone bundle. `fix_oversub.py` now uses the own-tranche parser, and allocation table matching is case-insensitive. `ipo.py build` stops on workbook build failure.

Run the full gate battery plus `tools/test_source_reviews.py`, `tools/test_monitors.py`, and `tools/test_deliverable_review.py`. The latter checks all 524 HTML records, every displayed numeric Database cell, full cornerstone/subscription parity, all lock-up caches and trading-session formulas. Bloomberg calls are linted and surrounding logic is computed with simulated quotes; a Bloomberg terminal is still required to verify actual add-in execution. Native Excel inspection was unavailable because the Mac was locked; Artifact layout renders and automated checks were used.

HTML has a dedicated **Lock-up** tab, with sector, company and holder-group/date selectors, before/after return tiles, and an A/H-style line chart covering day −7 to +7. The chart is rebased to the expiry reference close = 0%; returns themselves retain P0/P−7−1 and P+7/P0−1. `Trading sessions.path` stores all 15 offset/date/split-neutral-close observations; unknown or suspended observations stay null, breaking the plotted line. Hover gives the exact date and close. All 7,440 stored observations reconcile to cached raw histories and the common split adjustments. `tools/test_lockup_html.py` exercises every one of the 1,064 events, selectors, gaps, table row clicks, and both themes. Source dates stay linked to their HKEX PDF pages.


### Selectable Excel lock-up chart and investor-name review — 8 October 2026

Lock-up has a native line chart and the complete 1,064-event table. B4 chooses the H code; E4 chooses the holder-group/date event (Auto default). Auto uses the same stock/event priority as HTML. A stale event label triggers an explicit Auto fallback notice; invalid stock codes blank the metrics and graph. The chart uses the same 15 split-neutral observations as HTML, from -7 to +7 HK trading sessions around day 0. Intentional #N/A values in hidden Chart Data are graph gaps, not missing returns replaced with zero. IPO date is a typed sortable date in column E; last locked date is F, before/after returns G:H. Table header is row 28; data begin row 29. The top chart and summary show the actual selected event and IPO date.

Name-comparison rules live in data/investor_aliases.json, with primary references. MLP, Millennium and Integrated Core Strategies compare under Millennium; HHLR/HHLRA/Hillhouse, JPM asset-management legal entities, and ADIA have explicit comparable keys. CPP segregated accounts managed by HHLRA retain a separate key. Individual stock rosters retain distinct legal subscribers (e.g. Value Partners Limited and Value Partners Hong Kong Limited; mainland and HK E Fund); the league counts a deal once per investor family. Never merge separate legal vehicles just because one name is a prefix of another.

Internal audit lessons (do not add an Excel audit tab): source table rows continue across PDF pages. Dates, page numbers, Yes/No status and footnotes must never become investor names. CATL previously had 18 contaminated names: its complete final-allotment roster has 23 groups. Zijin Gold FIL and Gaoyi/CSICM, NSING Kaifeng/Wider Huge, AICT Greenwoods/GF Fund, and Yangtze Optical Foresight/ADIA demonstrate adjacent-row contamination. Review the complete roster; an exact substring in a cornerstone chapter does not prove row membership or completeness. A manually corrected name does not certify every other name in that stock list. Each corrected name retains page, URL and downloaded-file SHA evidence in cornerstone_name_corrections.json. Raw spellings remain available. Numeric/source uncertainty remains in the external review files; do not call retained figures independently verified. A passing arithmetic gate cannot establish a source value.

Native Mac Excel opened the workbook without a repair prompt and rendered the default chart and summary at normal zoom. Its Microsoft 365 installation is view-only, so editable selector changes are tested by the spreadsheet evaluator, not claimed as native recalculation. Bloomberg add-in calls still require the desk terminal. Existing quotes remain the 2 October snapshot. New charts do not fetch Bloomberg data.

Final source-confidence counts: 524 stocks, 37,771 scalar numeric entries across 99 fields, no arithmetic failures. Primary subscription readings cover all 524 public tranches and 521 institutional tranches, with the three documented N/A cases retained. There are 273 annual revenue/profit cells needing fresh unambiguous row confirmation, 226 cornerstone legal-name/group confirmations outstanding, and 156 unestablished cornerstone expiry dates. These are unresolved evidence items, not verified values. Sixteen stock rosters have targeted, page-and-hash-backed name corrections. Do not treat those targeted corrections as certification of untouched roster members. The delivered lock-up paths remain exactly the 2 October snapshot.

QA includes offline bundle reproduction, all 1,064 HTML event graphs, every numeric Database cell and HTML record, source-review regressions, all 62 A/H selectors, stored histories and simulated Bloomberg switching, future-stock/event extension, and scope preservation of other sheets' values, formulae, styles, validations, native charts and conditional formats. Mac Excel visually confirms the final chart, IPO date, Screener and Database colours; editing is unavailable in its view-only installation. Keep these audit notes in maintenance/evidence files, not an Excel audit tab.


## 12 October 2026 — market monitors, 30-session lock-ups and primary capital review

This delivery keeps the canonical Database/Screener at 524 deals. Only IPO Live and A/H monitoring extend to the seven-year listing roster: 190 additional Main Board listings from the 2019/2020 HKEX Factbooks produce 714 live tickers and 68 A/H pairs. Supplementary records are in market_supplement.json, not deals.json; company codes identify securities. The additional A/H lines are Pharmaron, Tigermed, Hepalink, InnoCare, RemeGen and Haier Smart Home. An introduction or an A line listed after the H debut does not have an invented IPO premium. Stored prices remain dated, through 2 October; individual series retain actual last observation dates.

IPO Live has five columns, LAST_PRICE, change against PX_YEST_CLOSE, sector/subsector classification and two average-change charts. Positive moves are green and negative red. Missing prices and nonpositive prior closes do not enter averages. B5 changes classification; H34 selects the broad sector for the subsector chart. Screener freezes A:B only; Database/Screener keep the professional group bands. Important tabs have muted identifying colours.

AH uses B4 for H/A code and E4 for Stored/Bloomberg. G/H show current premium minus the premium on the last observed H date on/before seven calendar days or one calendar month earlier, in percentage points. The one-month reference uses EDATE, not 21 trading sessions. Both modes use raw A/H/FX price bases, dated alignment and ten-day A/five-day FX carry limits. Independent Bloomberg BDH output areas prevent spill collisions. Four selectable histories compare on their actual numeric date coordinates in an XY chart with lines, so a 2019 listing and a 2026 listing cannot be aligned by row number. The primary chart remains separately selectable. Headered BDH replies must be matched to the first data date; never index row one as a price/date. Filled formulas use ROW offsets rather than literal exemplar offsets. A valid current quote can append TODAY; missing, stale or wrong-security histories do not silently show stored prices under the live label. Native charts have bounded series and truthful opening caches, including legend labels.

Huaqin's H/A ex-entitlement mismatch remains excluded. Pharmaron has two 5-for-10 events: H/A ex dates are 6/14 June 2022 and 18/27 July 2023. Each mismatch interval is excluded, including stale pre-ex A quotes carried after its own ex date. Keep all reviewed events in ah_entitlement_reviews.json; checking only the latest event would create a false historical premium. IPO and current premiums outside the intervals remain available.

Peer Trades tracks six product pairs, including 9856/3308. Live quotes use LAST_PRICE and PX_YEST_CLOSE; independent stored/live chart selection is E4. Relative prices are rebased to the first common observed session; spread is A return minus B return in percentage points, not the raw-price difference. A/B price ratio is shown separately. BDH uses capital adjustments, with dividend adjustments disabled. Stored Tencent raw histories are normalized once; Yahoo Close is already split-adjusted and must not be scaled again. Product peers have different product mixes, customer exposures and valuation risks, recorded concisely next to each pair. Offline HTML uses dated snapshots and cannot execute the Bloomberg add-in.

Lock-up displays 396 actual cornerstone schedules for 386 companies; no-tranche rows and unrelated holder restrictions stay excluded. Returns and 61-observation graphs now use exactly 30 HK trading sessions before/after day 0. Day 0 is the final HK session on/before the last locked day. IPO date, cornerstone percentage of base offer, since-IPO return and base deal size are included. Four stock selectors and an expiry-date cohort range are provided in Excel; HTML has cohort/all/selected-stock comparisons. Curves are normalized at their own observed reference close; cohort averages use only available observations at each offset. This composition can change across the window. Missing observations are gaps; future endpoints remain unavailable. Yahoo raw Close was used where Tencent blocked requests; do not apply split factors a second time. 0917's unavailable history remains unresolved rather than fabricated.

Of previously undated cornerstone events, 89 now have explicit prospectus wording establishing six months from and inclusive of the listing date. The six-month anniversary is the first unlocked date; the preceding date is the last locked day. These dates are derived from the issuer's express clause, never inferred from a generic market convention. Sixty-seven visible events still lack sufficient evidence; their dates, returns and curves remain blank. The original filed schedule does not prove actual selling or rule out later waivers.

The primary-source review downloaded/extracted 1,976 filing parts without download failures. The durable desk_source_review batch carries accepted listing share capital/treasury counts and final over-allotment outcomes/quantities. Primary evidence, pages and document hashes are in data/desk_review_20261012/source_evidence.json. Final exercise quantity is distinct from stabilising secondary-market purchases and from the facility's maximum percentage. Do not replace the maximum greenshoe facility with actual over-allocation: use over_allocation_pct for that separate quantity. Partial exercise followed by lapse of the remaining option remains Partial. A separate capacity review confirms 382 maximum-grant readings, with source page/hash evidence in option_capacity_evidence.json. This includes SF REIT 2191 at 5% (Units), 2440/1334/3288/2651 at 15%, and Red Avenue 9607 at zero under its explicit no-option clause. The early parser confused company float or employee awards with option capacity; require an express grant and a base-offer denominator. Parenthesized percentages, Units, and “no more than” clauses are valid grammatical variants. The six initially withheld legacy figures are now resolved by targeted primary readings. Maximum capacity, actual over-allocation and final exercise quantity stay separate. Additional complete-prospectus review covered 173 suspect documents, with 50 expanded narrative extractions, without download failures. Specific corrections include 1021/2219 Partial, 9927 Lapsed (not upsizing), and 2657 Full. The combined BBG Verify sheet compares numeric exercised shares with numeric exercised shares; final outcome is a separate column. The former second verification sheet is appended after the main block. Listing-close market cap and offer-price company market cap are separately labelled and not colour compared as if identical.

Market cap uses filed total issued shares excluding identified treasury shares, multiplied by H offer price. A-line estimated cap no longer overwrites a higher-priority filed share count. Major source corrections include 3308, 2525 and 9609; resulting P/E/P/S and effective float are recalculated. Merdeka 6228 is an HDR: ten underlying shares per HDR (prospectus PDF p24); issued underlying shares must be multiplied by HDR offer price / 10. Its ratio evidence is durable and the source acceptance script handles it explicitly.

2147 Zhengwei's raw historical debut remains HK$0.56. Its six-for-one rights at HK$0.40, ex 9 September 2026, add a Bloomberg entitlement factor based on the last cum-rights HK$0.585 close. Combined with the earlier consolidation, current comparable debut is 8.16410256. Bloomberg reconciliation factors must be evaluated as of the terminal observation date: the 26 August fixture is still 11.2 because the rights event had not occurred. Never change raw price returns just to force equality with an adjusted terminal print.

The visible Analogs tab is removed; hidden Scoring Stats retains the screener's base-rate inputs. Numeric audit still covers every scalar value; 273 annual financial cells need fresh unambiguous primary-row confirmation. Retained figures are not promoted to verified status by arithmetic checks. The current review has 568 material numeric changes against the previous delivery; the earlier 358-correction history is retained separately in numeric_changes_history.json. Keep source-confidence notes in maintenance/evidence files, not an Excel audit tab. Word research remains separate and is preserved; it has not been extended to the six new monitoring pairs.

HTML is approximately 2 MB, with self-contained gzip/fflate payloads and chart-only values rounded to eight decimal places; canonical deal fields retain precision. Browser Save As/reopen remains offline. A ZIP is also supplied for transfer. Shared-drive quota failures still require space on the server; compression cannot clear a full quota. Tables, graphs, selectors and tooltips are checked in both themes; unnecessary instructional footnotes have been shortened.

Development workflow: after changing the monitoring roster, history or event universe, run prepare_desk_chart_data.py and re-author the market layout via create_market_template.mjs before build/export. The pre-authored template and new data/modules are included in the standalone hk_ipo.py bundle. Check all gates, the controlled headered-Bloomberg probes in test_desk_comparisons.py/test_monitors.py, all A/H and event charts, comparison selectors and offline saved-file reopening. Native visual QA uses actual cached values in a disposable bounded workbook; simulated live quotes must never enter a deliverable. Actual add-in execution requires a Bloomberg terminal and is not claimed by the controlled tests.


## 14 October 2026 — native recovery fix and compact desk layout

Native Excel recovery was reproduced, not inferred from XML validity. Repair Result to HK_IPO_Database_v10.xml and repair_probe_full0.xml identified the Lock-up and Peer Trades worksheet parts. Their child sequence was invalid (conditionalFormatting/dataValidations after pageMargins), and the Lock-up layout graft also created duplicate rows 55–80. reflow_monitors.sort now enforces the CT_Worksheet sequence and asserts unique rows/cells. The blank template roster is removed before copying real events. A later diagnostic recovered Table1 because its stored field names disagreed with the visible Live headers; all monitor table names are now synchronized. Never claim native compatibility based only on ZIP CRC or well-formed XML.

The final delivery was opened in native Mac Excel without a repair prompt. IPO Live, AH, Lock-up, Peer Trades, Screener and Database were reviewed. This installation is view-only and has no Bloomberg add-in: editing and live server replies remain fixture/terminal checks. Diagnostic copies were closed without saving; unrelated recovered-workbook state was preserved.

Database inserts three fundamental columns before the old BM: BM NTM P/E live, BN FY2027 P/E live, BO FY2027 P/S live. Old A/H pair moves to BP, A-share code to BQ, and the original last field to CF. Every original Database data cell is preserved at its translated address. Screener reuses duplicate live TTM columns BH/BI for estimates and inserts BJ for FY2027 P/S. The comparison band is AZ:BJ; selected valuation rows are 65–69. F53 references Database BQ. All qualified formulas, names, chart references, comment positions and VML anchors are translated; hard-coded legacy numeric field maps must not be reused. audit_formulas derives the field map from actual headers.

Valuation Data reserves eight raw columns and eight rows per BQL request. Helpers identify pe_ratio or px_to_sales_ratio headers, then take a numeric value only from that field's column. Numeric date/fiscal metadata must not be interpreted as ratios. Scalar and headerless two-column replies are supported, as are negative/zero values; unrecognized replies remain Unavailable. NTM raw P:W/output X; FY2027 PE raw Z:AG/output AH; FY2027 PS raw AJ:AQ/output AR. TTM fallback raw AU:BB/output L and BD:BK/output M; direct C/F take priority. Selected H estimates reuse sparse all-issuer requests, without multiplying MATCH's offset by eight. Selected A requests retain the user-supplied query semantics. Do not substitute an unverified Bloomberg field or FY1 for NTM to remove an unavailable result.

Live B4 defaults to Stored. fetch_live_snapshot retrieves bounded public batches and validates code, positive finite prices and quote timestamps. The 14 October snapshot has 705/714 prices; 699 same-day return observations enter the sector means. Stale/suspended names can retain their individually dated price but contribute no daily return. Market Data BS:BU stores previous close, last and actual timestamp. Public quotes never overwrite historical IPO terms, returns or Bloomberg valuation fields. Refresh replaces this separate snapshot; failed refresh retains dated data. A/H Bloomberg H quotes are independent direct BDP requests, so they cannot inherit Stored prices from the Live tab's switch. Source/date context is visible and no public quote is described as Bloomberg live.

Monitor layout uses compact controls, functional tab colours and numeric-only red/green formatting. Missing text stays neutral. Lock-up comparison controls are B10/E10/H10/K10 and cohort dates B11/E11, above two complete charts; roster header is row 37. The roster uses cornerstone-investor count; legal names remain in Database and canonical evidence. Chart legend formulas must move with controls, not just history helper formulas. AH premium and CSI/A returns share one real calendar X axis with separate Y axes. Peer charts use numeric calendar axes with automatic spacing for short and long horizons. No curves are fitted across unavailable prices or unreviewed corporate actions.

Internal checks: test_native_desk covers schema order/unique rows/field metadata/forward and selected bindings/sector averages/legend references/all 396 event rows and every original Database cell. test_latest_monitor_fixes covers all 69 selectors, 3223/9976, live-history gates, and benchmark source/cache parity. test_monitor_revision covers 35 peer selectors, comparison controls, corporate-action fixtures and refresh failure retention. test_presentation_package streams package relationships, styles, formulas, data/HTML parity and return calculations. Run bounded Python and one heavy operation at a time. Preserve earlier unresolved primary-source confidence items; this presentation repair is not a new filing certification.
