# PCA v128 changes

Revision 2026-10-26-v128-result-state; retains incremental downloads and all v127 market controls.

- Clear old results, comparisons and report text before a new run and when loading new data. Failed/rejected full runs, failed window comparisons, interrupted runs and failed re-hedges cannot export a previous or partial basket as the latest result.
- Preserve the previous validated configuration as the input to a successful re-hedge, then export only its new result.
- Make Show code reuse the loaded dataset, including manually added tickers, instead of starting a different full download. Quote cache paths with Python repr so Windows paths and apostrophes remain valid.
- Add actual form-action regressions for failure, interruption, successful rerun/re-hedge, export blocking, data replacement and generated-code execution. No changes to hedge selection, fitting or reported statistics.

# PCA v127 changes

Revision 2026-10-26-v127-incremental-download; retains the v126 global default and download recovery.

- Add a compact incremental download button and API. Request only missing explicit ticker histories and associated metadata within the existing cached dates, without repeating discovery or changing existing prices.
- Preserve source coverage and original download age; expose partial global additions and missing-price failures. Classify added instruments without automatically treating them as peers or basket holdings.
- Share metadata retrieval between full and incremental downloads; invalidate old analysis results after switching or updating the loaded data.
- Isolate both public HTTP clients in the offline source-failure test so CI cannot accidentally use live exchange data.
- Add regressions for incremental vendor requests, no-op/duplicates, original-data preservation, partial/all failure, classification, listing constraints, executable analysis with an added required peer, and the Data-tab action.

# PCA v126 changes

Revision 2026-10-26-v126-market-scope-and-download, same script and notebook entry points.

- Remove the invalid unused Bloomberg average-volume field request; keep valid quote-volume requests and observed-session volume fallback.
- Prefer the tested lightweight HKEXnews JSON. Bound official source attempts across standard and curl clients; retain verified TLS and configured proxies. Recover optional yfinance import failures through a fresh anonymous public-screener session. Keep partial listing results and precise source audits, with one compact coverage notice.
- Move the listing checkbox to Data and default it to unchecked (overseas peers allowed). Use one visible stock universe: verified local sector stocks plus verified overseas business peers when allowed. Remove the hidden automatic timezone restriction from that form/default scope; retain explicit script controls. Require a new download before turning a local-only cache into a global run.
- Report candidate counts by market and the actual return basis. Correct the error-attribution label for two-day observations. Disclose FX-incomplete coefficients as research values and withhold executable-weight exports.
- Clarify Auto compare as the recommended objective, its training-only volatility criterion and short-window limits. Preserve fitted R², historical tests, charts, alternatives, and basket priority.
- Add integration tests for global candidate admission, local-cache guarding, manual exclusions, form placement, import-error recovery, direct-client failures, source fallback, compact notices and mixed-currency handling.

Live public-source checks were performed from the development environment. They do not verify the user's terminal/network or establish complete peer coverage. No network blocking is inferred from timeout/import messages. Prices and business classifications still come from Bloomberg.

# PCA v125 changes

Revision 2026-10-26-v125-discovery-and-selection, same script and notebook entry points.

- Default downloads to Broad universe. Replace the EQS form input with Force download; distinguish download requests from required basket holdings.
- Add a bounded Yahoo regional listing-directory fallback, exchange partitioning, two-direction paging for the observed 10,000-slot limit, slot-aware offsets, partial-data retention, type/venue checks and explicit source audits. Prices and peer classification remain Bloomberg-based.
- Batch second-degree Bloomberg requests and retain security errors; preflight invalid fields, drain failed reference responses, and show actionable summaries.
- Keep CV-selected lookbacks in final long-window fits. Preserve complete analysis-horizon charts, label the fitting segment and stop replacement recipes inheriting a trade-eligible verdict.
- Use constrained QP screening, exact constrained pair seeds, no materiality rejection of partial baskets, and a display-independent shortlist. Validate search:0 automatically; keep alternatives as research references.
- Extract legacy PCA directions without target legs and use signal-based loadings. Keep the covariance shrinkage model.
- Add a visible simple-return reconciliation of current positions alongside the retained log-return model. Neither is a forecast of alpha or net execution P&L.
- Add regression coverage for Yahoo pagination/venue/type/error cases, batched vendor failures, force-download semantics, target-free PCA, selected lookbacks, exact pair optimization, and return-basis reconciliation.

Live directory connectivity and Bloomberg field entitlements vary across computers. The release records underlying source and field errors; a successful local directory check does not prove another computer’s network access or terminal entitlement. No all-peer, global-optimum, higher-R² or zero-error guarantee is made.

# PCA v124 changes

Revision 2026-10-23-v124-tracking-charts in the existing v115 entry point.

- Recover local listings of foreign direct peers using Bloomberg company identity, local venue, equity type and industry evidence. Reuse the full local listing scan; query unmatched issuers through documented instrument search even if a received roster may be stale. Keep unresolved checks explicit. Apply the same process across markets.
- Add HKEXnews active-directory fallback; verify instrument types so funds/debt do not become stock peers. Include legitimate HK equity subcategories and REITs. Classify sector-index names even outside broad indices. Retain successful reference batches and vendor errors.
- Narrow strict-peer/exposure rules so a broad hardware/semiconductor parent does not override distinct businesses or imply a semiconductor factor. Keep broader sector scope available and distinguish classification changes from missing prices.
- Scan listings broadly, then default price/cap/volume history to verified peers, sector names and references. Keep broad history as an explicit option; preserve all manual candidates/required names and classify historical additions. Reuse requests within a download and stream compact progress with a saved full log.
- Require a fresh discovery download for new coverage. Export peer coverage and basket identities. Preserve negative test results and historical eligibility exclusions.
- Make equivalent short-window training scores use a deterministic recipe tie-break; stabilize factor-reference ordering.
- Replace raw Download-button logs with an updating stage panel, source status, visible notices and an expandable full log. Keep compact console output and failure diagnostics.
- Reorder result presentation around the main and alternative baskets; add notebook comparison cards and expandable supporting analysis. Keep charts first, fitted/test labels distinct, and all positions and negative metrics unchanged.
- Add target-versus-basket tracking charts for every analysis window, separating current fits from recorded frozen tests. Preserve training intercepts and all test rows; never replace old weights with current weights. Avoid overlapping two-session path accumulation and joins between separate test blocks. Verify plotted metrics against the report.
- Regression coverage includes non-index names in three sectors across six markets, generic local-share resolution, identity/type and own-issuer rejection, source timeouts, response draining, batch failures, recent listings with complete short-window history, history scope, cache freshness and numerical ties. Live Bloomberg execution still requires terminal verification; no claim of exhaustive peers or improved realized hedge performance.

# PCA v123 changes

Revision 2026-10-20-v123-estimator-selection in the existing v115 entry point.

- Let constrained Ridge tracking compete with factor covariance inside training-only chronological estimator selection. Preserve basket priority, constraints, candidate scopes and the existing form workflow; short histories explicitly retain a fallback, not a claimed method winner.
- Use identical gross selection penalties for factor/tracking comparison, correcting the earlier zero-penalty descriptive reference. Keep the final reserved tests outside method selection.
- Report current fitted scores beside matched frozen historical R² and spread-volatility reduction. Keep every matched test row and preserve failure statuses. Export comparison recipes and estimator-selection evidence for independent recomputation.
- Dispatch the selected estimator consistently through search, final fitting, same-date ETF references and sensitivity. Factor projections remain descriptive when Ridge supplies the weights.
- Print actual searched basket sizes and concrete historical market-cap/return-history exclusions. Preserve negative results and source-coverage failures.
- Add synthetic checks for genuine tracking selection, temporal isolation, constraints, required names, no-test fallback, two-day purge, pooled-score reconciliation and diagnostic export. Test results do not establish live performance improvement.

# PCA v122 changes

Revision 2026-10-20-v122-residual-review in the existing v115 entry point.

- Add training-only chronological calibration of residual shrinkage for joint factor search, with fresh factor estimation, date-specific eligibility and basket search in every inner block. Preserve gross/per-leg limits, required names and meaningful basket sizes. Fall back explicitly when history or comparisons are insufficient.
- Keep calibration evidence distinct from outer historical tests. Preserve the existing estimator with `residual_policy='estimated'`; the new optional argument is appended to preserve positional API compatibility.
- Attribute each fitted error to retained-factor mismatch, target returns outside the factors and hedge returns outside the factors. Print the largest error dates, retain all observations and export a daily reconciliation CSV.
- Accept sourced event context as descriptive metadata only; do not identify alpha or claim an event caused a return. Reuse the primary factor model for stock-only runs' ETF references and freeze the selected residual policy in weight-sensitivity diagnostics.
- Add temporal-isolation, matched-block risk, PSD/variance, fallback, cap, attribution-reconciliation and diagnostic-export regressions. No private holdings or market-data files are included in this release.

# PCA v121 changes

Revision 2026-10-19-v121-data-integrity in the existing v115 entry point.

- Fix listing-download resilience with official Taiwan CSV alternatives and verified HTTPS; retain errors and source provenance. Never claim an unavailable official source was checked successfully.
- Defer current-cap discovery pruning when historical caps are requested. Convert historical caps using dated FX, exclude unknown/stale historical size data at active gates, and explain an unverifiable relative target-size band. Preserve old-cache reproducibility with visible limitations.
- Recover only verified, already-downloaded legacy cap exclusions; preserve manual exclusions, per-fit size gates and stock/ETF scope.
- Request alternative volume fields and observed-session historical volume, retaining errors and unknowns. Date current reference snapshots independently of the analysis window.
- Disclose effective primary-model settings and disable unrelated legacy PCA controls for joint search.
- Surface data gaps and weight sensitivity beside headline results; improve Word pagination without changing weights, objective or scores.
- Add synthetic download-error, HTTPS fallback, dated-FX, stale-cap, cache restoration, diagnostic-export and temporal-isolation regressions. Private user data are not included in the repository.

# PCA v120 changes

Revision 2026-10-17-v120-residual-covariance in the existing v115 entry point.

- Retain regularized residual co-movements after market/sector/equity PCA instead of assuming every off-diagonal residual covariance is zero. Estimate Ledoit-Wolf shrinkage on standardized training residuals from the eligible target/hedge universe. Preserve original return units and marginal variances; reference-only prices cannot alter calibration.
- Use orthogonal least-squares factor projection. The old penalized loadings left nonzero factor/residual cross terms which were then omitted from covariance, understating fitted marginal variances. Retain numerical stabilization in the constrained optimizer.
- Use the fitted primary model for the exposure report, including its actual training-eligible PCA and residual-calibration names. Holdout and nested folds continue to estimate independently from training rows.
- Keep current-basket R² prominent; move hypothetical same-name reweighting scores out of the compact main table. Preserve fit diagnostics and a labelled tracking-basket reference.
- Add Export diagnostics and safe JSON/CSV ZIP loading. Freeze downloaded inputs and exact options at run time. Archive round-trip tests reproduce 1m/2m/3m weights and scores without Bloomberg, and reject modified inputs.
- Added checks for variance accounting, factor/residual orthogonality, positive covariance, return-unit invariance, reference-only-column isolation, omitted-relationship recovery on independent simulated rows, and noise-only targets. Synthetic checks are not a live 2889 result or proof of trading improvement.

# PCA v119 changes

Revision 2026-10-17-v119-short-window-factor-coverage in the existing v115 entry point.

- Fixed short-window factor starvation seen in the supplied GMD report: prioritize specific taxonomy exposures before parent-sector fallbacks, share proxy-family slots, and reserve equity PCA capacity. The target remains excluded from PCA, and training folds build their own factors.
- Added a factor-coverage audit and a separately labelled current-fit tracking-basket comparison. The comparison obeys the same scope, exclusions, required instruments, size and caps, and cannot overwrite the primary basket or historical validation.
- Added synthetic gold-miner, cross-market taxonomy, missing-proxy, target-exclusion, covariance, constrained-comparison and holdout-isolation regressions. These reproduce the failure mechanism, not the user's live Bloomberg returns.
- Corrected the PMGOLD description to Perth Mint Gold. Existing v118 sector-policy caches remain usable; restart the kernel to load the repaired model.
- Fixed exposure keyword matching for plural industry labels such as Semiconductors, Banks, Airlines and Precious Metals. Newly recognized mapped factors appear in the coverage audit even when an older cache lacks their prices.

- Fixed the cross-market discovery/search disconnect: verified local sector stocks can now enter the actual search even when their narrow business classification differs. Added separate stock-only and ETF-inclusive sector scopes; strict-peer scopes are preserved.
- Default form/API scope is same-market sector stocks. Current single-ETF and local-market ETF references remain separate from the primary basket.
- Added per-stock eligibility evidence, actual-search names and disjoint rejection-stage counts. Size, price-history, exposure-cap and exclusion rules remain enforced; no fitted score or specific stock is forced.
- Added six-market/multi-sector synthetic integration tests, the 31-sector/9-peer regression, unknown/conflicting classification checks, listing aliases, old-cache refusal and ETF-reference isolation. Live Bloomberg reruns remain unverified.

- Fixed the October 15 actual-result failures: constrained Ridge fits now optimize within gross/per-leg limits across all modes and references; zero/dust positions no longer count toward basket size; negligible improvements cannot receive a positive risk-reduction grade.
- Separated low fitted R² into exposure-cap and objective/regularization gaps against same-date least-squares references; restored descriptive correlation diagnostics for 1m windows.
- Preserved both market and sector factors when short-window sensitivity removes a few days, preventing a hidden change of factor specification.
- Closed remaining placeholder-label/sector-conflict peer leaks, made peer-only ETF exclusion absolute, retained classification evidence and exposed constituent identities. Fresh peer-policy-v4 downloads are required for automatic peers.
- Fixed recipe amounts/line breaks for notebook rendering and Word copying; removed the duplicate plain-text notebook report while retaining terminal output and exports.
- Added Python 3.8 dependency pins and Windows/Linux CI jobs matching the environment shown in the result document.
- Added complementary-pair, growth and replacement basket search with distinct alternatives and an explicit bounded-search audit.
- Added a market/sector/peer factor covariance objective with diagonal specific risk, constrained weights and target-excluded peer PCA. Raw in-sample R² remains visible; no positive score is manufactured.
- Separated complete-window current weights from frozen historical validation weights, including full reports, alternatives, charts and quick refits.
- Tightened every automatic peer taxonomy path, including missing/unknown labels; added official listing rosters for HK/AU/JP/TW/KR/US, independent industry cross-checks where provided, and optional existing Bloomberg EQS/manual discovery universes. Missing coverage and partial downloads are reported.
- Preserved sector ETFs in focused scope, added sector mappings, removed the incorrect Japanese bond proxy, fixed keyword substring collisions and full-identifier membership exemptions.
- Kept the single analysis-window workflow and added optional separate comparisons. Single stock/ETF hedges remain references.
- Unified printed/notebook/Word output, kept charts at the top, added exposure/sensitivity/execution diagnostics and reduced repeated explanatory text.
- Added tests for the actual updated engine and notebook; retained the historical v103 regression suite separately.
- Final logic review: prevented backup market proxies from displacing sector factors, fixed pinned joint-search recipes in long-window/quick validation, and surfaced mixed-currency fits with an explicit FX implementation block. Added independent constrained-objective and negative-R²/volatility identity checks.
- Normalized known listing aliases for instrument identity and factor matching, so JP/JT duplicates cannot masquerade as separate hedge legs or reintroduce the target itself.
- Updated printed, notebook and Word reports with interpreted fit/validation metrics, consolidated alternative positions, and an institutional red/charcoal design. Scores and model selection are unchanged by presentation styling.

Run after restarting the kernel and downloading fresh peer metadata. Live Bloomberg coverage, borrow availability and future hedge performance remain unverified by offline tests. Market-cap screens are not liquidity guarantees; costs and FX conversion remain outside this model.
