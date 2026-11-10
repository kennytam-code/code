# Database and A/H review — completed 10 November 2026

## Accepted changes

- Read 34 HKEX capital chapters and checked final offer prices. Corrected/filled 32 IPO capitalisations. Basis is outstanding issuer shares × final H offer price, HKD millions, ex shoe; this is separate from live A/H share-class caps. 2390/3660 exclude reserved awards from outstanding shares; 9690 uses the actual partial offer-size adjustment. Dependent IPO P/E and P/S were recomputed. Independently quoted 6979 Bloomberg TTM P/E remains 17.5.
- All 524 populated institutional multiples reconcile with retained filing evidence. 2161 is public-only (N/A); 2378/2439 do not disclose numerical institutional coverage. This reconciliation is not a fresh download of every institutional source.
- Mechanisms: 145 explicit Mechanism B, two explicit A, 20 Chapter 18C. Outcome review includes 269 earlier reads, full prose for 164 unresolved entries, and fresh reads of 151 previously populated outcomes. Some coverage overlaps. 163 of the 164 missing outcomes were resolved; 2636 changed from No to the issuer's N/A.
- Final outcomes: 155 Yes, 221 No, 150 N/A (145 Mechanism B and five filed/public-only N/A), one unresolved. Mechanism B has no mandatory clawback; No is an applicable mechanism that did not trigger. Discretionary and reverse transfers are not automatically mandatory clawbacks. 2439's literal issuer wording is retained separately from the reviewed mandatory-clawback interpretation.
- 2550 remains unresolved: 114.59x public, 0.98x institutional demand, 13.17% final public allocation, and prospectus mandatory/discretionary clauses do not establish the actual labelled outcome. Its displayed cell is blank. No 'Unconfirmed' filler is published. Unknown allocation mechanisms are not guessed from the IPO date or final public percentage.
- Recovered 168 missing final public-allocation counts from official allocation results. For 2476/1377, the denominator excludes separately reserved overseas employee shares; 6228 uses HDRs consistently with trading volume. Recovered four missing listing-day tapes/fields at the exact IPO dates; existing close returns cross-check within 0.02pp. All 527 volume/public-allocation ratios now have real inputs.
- Audited all 75 A/H offer references. 71 have pre-H-listing A prices; 2315/9969/9995 listed A after H, and 6690 has no H offer price. Five stale FX anchors (3308/3223/9976/9607/2636) were corrected against newly fetched dated A prices and FX closes. All 71 applicable H offer prices were checked in issuer allocation notices or issuer publications. Other 66 numeric A/FX references reconcile to retained dated histories, not an independent fresh market-data source. The convention is A close before H listing × CNYHKD / H offer − 1. Database, AH and HTML use the corrected values.
- Checked all 150 scalar cap formulas: CURRENT_MARKET_CAP_SHARE_CLASS on each pair's A/H Bloomberg identifier. Existing convention is millions in the security currency (CNY/HKD), with no extra scaling. Do not substitute issuer-wide CUR_MKT_CAP. Entitled responses, live field metadata/units and actual terminal latency remain untested.
- IPO Live refreshed: 702 validated public quotes from the 717-stock universe, source as of 9 November. Individual quote timestamps are preserved. Historical Database return observations and A/H/peer chart histories are not a full November refresh. Database date header now says 'Returns as of'; do not relabel an old observation as current.

## Presentation and missing values

Database uses compact Arial, muted section colours, subtle rules, a small signature-red accent and red/green performance changes. No data is altered by styling. Secondary columns remain expandable. The effective-free-float share-count column is hidden independently (backing cells preserve existing formulas); the HTML detail field is removed. All Excel cell comments and their red corner markers are removed, while native charts and controls remain. No Notes sheet or Excel Lock-up sheet is added.

Not every blank valuation is a data error: losses, non-revenue businesses, missing filed denominators and unavailable consensus estimates are distinct. This review restores the demonstrated allocation/tape gaps; remaining financial-source gaps are recorded in `fundamental_completeness.json`. Bloomberg responses cannot be manufactured or certified from an offline formula check.

## Maintenance

Accepted inputs: allocation_source_review, capital_source_review, retail_float_review, day1_source_recovery and ah_offer_reference_review batches. Merge applies demand_review, capital_review, metric_source_review, then retail_float_review at the end. All are idempotent. Corrected IPO reference values also reside in ah_ipo/ah_study. Keep quote dates distinct from build dates.

Final native stages: database_desk, then remove_cell_notes after ah_database_links. Spreadsheet style control was authored through the bounded Artifact workflow. Run tests in this directory plus native/package/mode and shipped-HTML SVG checks. Preserve eleven W_* inputs. One heavy process at a time, Python 512 MiB, Node 384 MiB; no raised limits. The standalone updater must embed all accepted inputs/modules. Verify installation hashes before delivery. This session is local only; no GitHub publication was requested.

## Limits

The 34 fresh capital reviews do not independently certify all other historical caps. Prudential's exact listing-date outstanding capital remains unresolved. Source issues outside the scoped inputs remain recorded in the existing repository reviews. Do not call an arithmetic pass independent verification. No Bloomberg terminal is available here, and there is no terminal performance measurement.
