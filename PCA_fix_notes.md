# PCA v116 changes

Revision 2026-10-14-v116-joint-search-common-risk in the existing v115 entry point.

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

Run after restarting the kernel and downloading fresh peer metadata. Live Bloomberg coverage, borrow availability and future hedge performance remain unverified by offline tests. Market-cap screens are not liquidity guarantees; costs and FX conversion remain outside this model.
