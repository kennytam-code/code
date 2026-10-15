# PCA hedge research

The current engine is `pca_hedge_v115_peer_pca_diagnostics.py` and its matching notebook. The filename is retained for existing users; its internal revision is **2026-10-15-v118-cross-market-sector-search**. The v103 files are historical and use a different model. Use the current notebook for these changes.

The default candidate scope now compares **same-market sector stocks**, rather than restricting every run to narrow industry peers. This applies across markets and sectors. It fixes a discovery/search mismatch: already-downloaded sector stocks could previously be excluded from focused search. Sector candidates need matching GICS/BICS sector evidence, a matching official exchange industry category, or mapped local sector-index membership; a known Bloomberg sector conflict blocks automatic inclusion. The broader sector scope is labelled separately from strict business peers. No stock is forced into the selected basket just to raise fitted R².

Restart the kernel and **download fresh data** for sector policy v1; old caches cannot establish the new candidate set. Choose `Same-market sector stocks` for a stock-only basket (default), or `Same-market sector stocks + ETFs` to let relevant ETFs compete. Strict-peer scopes retain their previous definitions. ETF references and market/sector risk diagnostics remain available in stock-only mode when their prices are present. The report lists actual current-search stocks and counts of exclusions; per-stock evidence/statuses are in `result['sector_search_audit']`. Current classifications and official rosters are not point-in-time sector histories, and coverage still depends on available sources and price data.

## Run on another computer

Python 3.12 is the primary validation target. Python 3.8 uses the pinned legacy dependency set in `pca_requirements-py38.txt`; `pca_requirements.txt` selects those versions automatically with environment markers. Both versions run in Windows/Linux CI. Bloomberg API compatibility remains dependent on your licensed installation. Install packages into the notebook's own kernel, then restart it:

```python
%pip install -r pca_requirements.txt
```

Open `pca_hedge_v115_peer_pca_diagnostics.ipynb` and run its engine cell, or run:

```python
%run pca_hedge_v115_peer_pca_diagnostics.py
```

The existing form opens. Enter the target, download/load data, choose one **past analysis window**, and Run. The usual 1m, 2m, 3m, 6m and 1y choices remain. The optional “Also compare” control runs other windows separately; it does not replace the selected primary window. Book size and holding duration remain optional display/risk references.

**Download again after upgrading.** Older caches do not establish the new taxonomy verification. An explicit manual peer list can be used with existing downloaded prices, but manual inclusion is a user assumption. Never load a pickle cache from an untrusted source.

Live Bloomberg downloads require an active licensed connection, the Python API and relevant field entitlements. Package installation does not provide these. Follow the [Bloomberg API instructions](https://professional.bloomberg.com/support/api-library/) for your terminal. Cached analysis does not require `blpapi`. Independent exchange-roster retrieval uses public HTTPS endpoints and records unavailable sources when internet access is blocked. `openpyxl` reads HKEX/JPX workbooks and `lxml` reads KIND's HTML download; both are included in the requirements.

`pca_requirements-min.txt` pins an older supported dependency set. Plot styling filters unsupported Matplotlib parameters, including `axes.titlecolor`. Word exports use `python-docx`; charts use Matplotlib. A missing Word dependency produces an explicit text-export fallback. Export paths default to `./hedge_exports`, cache paths to `./hedge_data_cache`; no machine-specific mapped drive is needed.

## What the model does

The default objective estimates common market/sector risk using named ETF directions followed by equity PCA on the residual common variation of the declared stock scope (sector stocks or strict peers). Only the first usable broad-market proxy per market supplies a named factor; its backups remain eligible hedge instruments without consuming extra factor slots ahead of the sector. The target stock is excluded from peer PCA. Factor loadings are regularized; the covariance includes instrument-specific variance, so minimizing shared exposure cannot treat the hedge stocks' own risk as free. This is a statistical risk model, not an expected-alpha model. Unexplained returns also contain company risk, omitted factors and noise. Minimizing variance does not impose exact market/sector neutrality; inspect the remaining exposures.

The basket is the primary result. Current single-stock, single-ETF and local-market ETF hedges remain references. Joint search screens complementary pairs across eligible names, grows combinations and replaces members; PCA, correlation and forward-selection recipes also remain competing procedures. Small universes screen all subsets; final constrained fits are applied to a shortlist. Larger searches are bounded, and actual screen/fit counts are reported. It does not claim a global optimum. More searching can increase fitting bias, so the historical tests remain separate.

The selected procedure is refitted using the **full chosen analysis window**, including its latest available day. `weights`, `returns`, `current_fit` and headline in-sample R² describe that current fit. Earlier frozen validation fits and weights are retained separately in `validation_weights`, `validation_fit_returns` and `validation_hedge_alternatives`. Unseen scores test those historical procedures; they do not validate today's precise refitted weights.

The factor objective minimizes modelled spread variance, subject to gross/per-leg caps. This can choose a lower tracking R² than ordinary least squares. The report therefore shows actual raw in-sample R², same-basket unconstrained OLS R², fitted volatility reduction, common-factor exposures before/after hedging, and weight sensitivity. OLS is a descriptive reference, not an independently tested alternative. Adjusted R² remains available as a nominal complexity heuristic; it is not an unbiased statistic after model selection or regularization.

The report separates the same-name fit gap into exposure-cap effects (uncapped OLS minus capped OLS) and objective/regularization effects (capped OLS minus actual fitted R²), on identical dates. The capped reference permits zero legs, so it is a descriptive upper reference, not a selected basket or an unseen test. Short 1m runs also retain their descriptive candidate correlations.

Low fitted R² is still a limitation. Under the report's same-date fitted-intercept convention, fitted volatility reduction equals `1 - sqrt(1 - R²)`; these are not independent pieces of evidence. A low-tracking-R² hedge can reduce a particular common exposure when company-specific variation dominates, but fitted exposure reduction alone does not validate future effectiveness. Negative fitted R² means increased fitted spread variance under this convention and remains visible. Residual risk is not automatically alpha.

**Numerically negligible risk reductions do not earn a positive verdict.** Reductions below 0.05% (the one-decimal display boundary) are labelled no material validated reduction. This tolerance is not a cost hurdle or statistical significance test. Common-factor reduction is displayed alongside the fraction of target variance represented by those factors; near-100% factor reduction can still leave most stock risk.

**Negative scores remain visible.** Negative unseen tracking R² means a poor return-tracking test against its mean-return benchmark. It is not automatically equivalent to increased spread volatility, because tracking also penalizes mean-return errors. Variance/common-risk modes evaluate volatility evidence and report tracking separately; strict tracking mode retains a negative-R² rejection. No unseen observations means an unvalidated research candidate and empty `trade_weights`. `trade_eligible` is a legacy statistical-evidence flag, not order approval; execution checks always remain necessary.

Short windows usually provide descriptive fitted evidence; where enough data exist, a final segment is reserved before the current refit. Longer windows use chronological inner/outer validation when feasible. Missing target dates are diagnosed separately from constant returns. Data errors are not repaired by inventing returns, hiding losses, or forcing R² positive. Alternative baskets are distinct full-window research fits, not independent unseen winners.

## Peers and instruments

Discovery combines Bloomberg direct/second-degree relationships, GICS/BICS industry matching, local broad/sector index members and optional broader listing universes. **Every automatic peer relationship must have industry-group or narrower taxonomy support**; two network links alone do not verify a peer. Broad GICS sector membership alone does not qualify. Company identifiers retain their exchange suffix.

For the six priority markets, independent official rosters extend discovery beyond index constituents. The downloaded current lists still require Bloomberg identifier, industry and price validation:

| Market | Independent source | Coverage / cross-check |
| --- | --- | --- |
| Hong Kong | [HKEX securities list](https://www.hkex.com.hk/Services/Trading/Securities/Securities-Lists?sc_lang=en) | Main Board/GEM equity entries; derivatives, funds and duplicate RMB counters excluded. Listing cross-check only: no industry taxonomy in this file. |
| Australia | [ASX company directory](https://www.asx.com.au/markets/trade-our-cash-market/directory.html) | Published company directory and GICS industry groups; preserves codes beginning with digits. |
| Japan | [JPX listed securities](https://www.jpx.co.jp/markets/statistics-equities/misc/01.html) | TSE domestic-equity entries and 33-industry classification; supports alphanumeric codes and the current XLSX format. Regional-only listings, foreign stocks and REIT categories are outside this supplemental source. |
| Taiwan | [TWSE](https://openapi.twse.com.tw/) and [TPEx](https://www.tpex.org.tw/openapi/) | Listed/OTC issuer codes and exchange industry categories. Emerging-stock companies are outside these two sources. |
| Korea | [KRX KIND](https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13) | KOSPI/KOSDAQ issuer entries and industry labels; excludes KONEX from this supplemental source. Six-character identifiers retain leading zeros and allow newer alphanumeric codes. |
| United States | [Nasdaq Trader directory](https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs) | Nasdaq and other covered US exchanges; excludes flagged ETFs, test issues and identifiable funds/derivatives/preferred/debt instruments. No industry taxonomy or OTC universe in these files. |

Official industry categories are independent review aids, not interchangeable with Bloomberg taxonomies. The audit records same-category names missing from the verified peer set and verified peers with different official categories; neither is automatically promoted/rejected based only on this cross-check. Listing sources without industry labels cannot independently establish business similarity. Full lists, source timestamps, unmapped identifiers and source errors remain in `peer_coverage[target]`. Truncated HTTP downloads retry once; failures remain explicit and do not crash the whole analysis.

All supported markets can additionally use an existing Bloomberg EQS all-equity screen or a supplied ticker list:

```python
data = download_hedge_data(
    '2889 TT Equity',
    peer_screen='Your existing EQS screen name',  # optional; omit if not configured
    peer_universe=['5864 TT Equity'],             # optional additional discovery names
)
```

The EQS screen must already exist and be accessible. A requested screen failure stops with an explicit error. Additional-universe names are classified before becoming automatic peers. The form accepts a PRIVATE screen; the API additionally accepts `peer_screen_type` and `peer_screen_group`.

There is no universal “all peers” guarantee: business similarity is not a unique classification, and listings, classifications, Bloomberg entitlements and prices can be missing. The report shows source availability, discovered/eligible counts, rejected/unverified relationships, missing classifications/prices and failed expansion requests. Full ticker lists remain in `peer_coverage` and downloaded provenance. Cached peer policy v4 rejects Bloomberg error/placeholder strings in every taxonomy path and known sector conflicts; older automatic peer sets require a new download or an explicit manual list. Company names, industry labels and eligibility are shown for basket constituents. Current classifications and present-day rosters still create historical universe bias; index membership checks do not eliminate it.

Scopes are `sector` (default: same-market sector stocks), `sector_focused` (same sector plus relevant ETFs), `peers` (strict business peers), `focused` (strict peers plus relevant ETFs), and `all` (broad exploratory universe). Stock-only scopes exclude ETFs even when forced/manual inputs request them; incompatible required instruments produce an explicit error. The market-ETF checkbox is disabled in those modes. Sector scopes always keep stock candidates in each target's listing market; strict/global exploratory scopes retain their exchange control. Diagnostic market exposure and ETF references can still be measured without permitting that ETF in the basket. In same-day mode, an excluded distant-time-zone ETF is not silently reintroduced as a factor. Known listing aliases such as JP/JT share instrument identity for exclusions, deduplication and factor matching; the same symbol in unrelated markets remains distinct. Alias duplicates cannot supply extra basket legs or masquerade as the target's hedge. Market-cap filters are size screens, not proof of liquidity; all stock scopes obey them.

Local market references follow the listing market: HSI/2800 HK, TAIEX/006204 TT with explicitly labelled Taiwan 50 alternatives, S&P 500/SPY US, TOPIX/1306 JT, CSI 300/510300 CH, KOSPI 200/069500 KS and mapped local proxies for other supported markets. Indices themselves are not executable legs. US sector ETFs are retained in focused mode; selected local sector proxies also exist. A banking sub-sector proxy is not complete financial-sector coverage. Missing/filtered instruments are reported, not replaced by an unrelated ETF. The incorrectly labelled Japanese 1482 bond mapping was removed: it holds US Treasuries with JPY hedging, not Japanese government bonds.

## Controls and output

The form defaults to common-risk mode, joint basket search, 2× maximum gross hedge exposure and 1× per instrument. The API preserves optional caps, so set them explicitly when scripting. A required range is inclusive; equal bounds request an exact count. All current and alternative baskets respect required/excluded names, scope and exposure caps. Every counted basket leg must have absolute notional of at least **1 per 100 units of target**. Dust recipes are rejected, not padded by forcing extra risk. This is a disclosed materiality convention, not statistical significance. Requested meaningful legs must be feasible; the model cannot fabricate a basket to meet an impossible request.

```python
result = find_best_hedge(
    '2889 TT Equity', data=data,
    sample_window='2m', candidate_scope='sector', include_broad_market=False,
    basket_size_range=(3, 5), alternative_baskets=5,
    hedge_objective='factor', basket_methods='search', max_gross=2, max_leg=1,
)
```

Charts lead the institutional report, using a white background, red accents, charcoal tables and Arial typography. It includes the current basket, raw fitted R² for every window, exposure reduction, multiple alternative recipes, single references, historical evidence, sensitivity and coverage/execution checks. Key fit and historical-test measures include a brief interpretation. Alternative positions and metrics appear together for comparison. Run displays one styled report in a notebook, without a second duplicate transcript. Terminal runs print the same report. `result["report_text"]` and exports retain the complete printable text. Position recipes use currency-neutral amounts per 100 target and explicit line breaks to avoid notebook math rendering swallowing dollar-delimited text. Compact and full reports use the same current weights; full adds configuration detail. Word and notebook reports share the same structured content. `diagnostic_log`/`full_report` preserve the legacy calculation log with its earlier-fit context. The design is inspired by institutional research reports; it does not represent an official Nomura document.

```python
comparison = compare_history_windows(
    '2889 TT Equity', data, windows=('1m', '2m', '3m'), max_gross=2, max_leg=1,
)
comparison['summary']
comparison['diagnostic_results']['2m']['weights']
export_result(result)
```

Optional window comparisons are overlapping historical fits, not independent repeated tests. Borrow availability is unknown unless supplied explicitly in `data['borrow_available']`; a confirmed unavailable short leg prevents eligibility. Bid/ask and average volume are snapshot diagnostics. Costs, financing, taxes, slippage, borrow fees and FX conversion are not modelled. Known mixed quote currencies across target/hedge legs produce a prominent FX-normalization warning and empty `trade_weights`; unknown currency is explicitly incomplete, never assumed equal. Those local-currency fits cannot establish common-currency portfolio risk. Paths use a log-return spread approximation, not an exact self-financing portfolio backtest. Cross-time-zone two-day returns reduce timing mismatch but do not remove it.

`quick_rehedge` pins the selected recipe rule and basket size, including joint-search ranks in longer validation windows. Reapplying that rule can select different names on new data; it does not hold the previous constituents fixed or transfer the old validation to today's weights.

## Validation

`tests/test_pca_research.py` loads the actual current engine and checks all five windows, complementary combinations, caps/required names, chronological isolation, latest refits, industry verification, official-roster/EQS parsing with mocks, missing/constant prices, UI defaults, plots, printed reports and exact notebook/script parity. `tests/test_hedge_search.py` separately checks the historical v103 engine. GitHub Actions runs both suites on Windows/Linux with Python 3.12 minimum/current dependencies; Python 3.8 legacy jobs validate the current engine only.

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

Offline/simulated tests establish software behavior; they cannot establish live Bloomberg field coverage or future profitability. The samples are clearly marked simulated. Statistical references: [factor covariance models](https://docs.mosek.com/portfolio-cookbook/factormodels.html), [R² definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.r2_score.html), [Bloomberg EQS API](https://data.bloomberglp.com/professional/sites/10/2017/03/BLPAPI-Core-Developer-Guide.pdf).
