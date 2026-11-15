# 15 November 2026 — A/H refresh and market-cap review

Scope: refresh the existing 75 A/H pairs, repair HTML detail charts, and review
the Excel Bloomberg share-class capitalisation fields. No new universe census,
IPO filing audit, pipeline review, peer-price refresh or valuation-source change.

## Prices and charts

All 75 A/H pairs now have actual H/A/FX observations dated 13 November 2026.
CSI 300 also ends on that date. 4,152 raw A/H close observations were appended;
27,657 aligned premium observations pass arithmetic and no-look-ahead checks.
Existing overlap prices and IPO pricing inputs were retained. The latest close
for every A and H line agrees between Tencent and Yahoo (150/150 checks).
No new split events were reported by the second provider in the refresh window.
This is a provider cross-check, not an independent exchange-tape audit of every
historical observation. Raw responses and URLs are retained beside this review
and in data/ah_refresh_review. No missing prices were interpolated.

HTML has two aligned detail panels: A/H prices above, premium below. HKD price
view converts A prices using the dated FX. The optional indexed view compares
native-currency A, H and CSI 300 prices, each rebased to the first common close;
the around-listing option retains the pre-listing mainland benchmark window.
Both panels show the same date interval. Genuine missing-data gaps remain.
Existing split/entitlement adjustments are preserved. The HTML embed now includes
latest observation dates needed to apply the same H-share factors as Python.
Comparison views retain sector/subsector scope, separate stock/average modes,
and six-line pagination. Peer dates remain 2 October; they are not relabelled.

## Capitalisation

All 150 scalar formulas still use CURRENT_MARKET_CAP_SHARE_CLASS with the
correct A or H ticker. No guessed replacement field, scaling override, cached
cap, or extra Bloomberg request was introduced. Headers now explicitly say
A-class cap / CNY m and H-class cap / HKD m. Stored mode retains a dash.

HKEX monthly returns for Ingenic (3223) and Montage (6809) were inspected for
separate issued A/H shares and treasury shares. market_cap_sources.json records
the exact URLs, counts, currencies and dated arithmetic. Those month-end
calculations are reference examples, not current caps or Bloomberg responses.
Issuer-wide cap is different from share-class cap; A and H columns also have
different currencies. Subsequent treasury-share changes can affect comparisons.

The user's observed erroneous values were unavailable. Public documentation
does not independently establish the returned units/coverage of this specific
Bloomberg field on the user's terminal. Actual field responses, entitlements,
latency and memory consumption remain untested. Do not claim a live cap error
has been conclusively reproduced or fixed.

## Update procedure

refresh_ah_history.py appends observed closes sequentially and independently of
the historical IPO-return snapshot date. Run it with --asof YYYY-MM-DD when an
explicit cutoff is needed, then prepare_ah_reference.py and the normal staged
native/HTML builders. Both ipo.py and standalone hk_ipo.py include ah-history
after ah-study and before monitor-data. build alone uses saved data; update
refreshes providers. Weekends retain actual dates. Conflicting overlap prices
fail visibly. Gaps over one year require a dated backfill before the bounded
320-bar request; do not enlarge memory limits or silently accept truncation.
The ongoing chart audit is now ah_chart_review_latest.json; the dated 13 October
audit is preserved. Review update failures and new corporate actions before
publishing; a successful arithmetic check is not a new source certification.

## Validation and limits

See validation.json, workbook_checks.json, detail_checks.json and bundle_checks.json.
The final workbook opened in Mac Excel without a repair prompt; AH table and
cached charts were inspected. Excel is view-only here, without Bloomberg.
The browser was checked with actual controls, including Ingenic/Longsys,
the benchmark and horizon controls, and Technology comparison pagination.
No browser errors were reported. Bounded Artifact rendering reviewed the
actual workbook's A/H header/table. Eight unrelated sheets preserve business
values, formulas and effective styles. All 11 W_* inputs remain in place.

User authorised GitHub publication on 15 November. Actual commit and download
verification status are recorded in data/release_state.json. Preserve unrelated
files and Word studies.
