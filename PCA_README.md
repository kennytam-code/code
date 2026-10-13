# PCA hedge finder

Find a primary basket hedge and compare it with single-stock and single-ETF references for the same target and past history window using the existing form. Basket candidates are selected using earlier training/CV data; later validation is reported separately. Negative headline unseen tracking R² cannot qualify a supported hedge. A stronger single reference never replaces the basket.

## Setup on another computer

Python 3.12 is tested. Open a notebook in the folder containing these files and install dependencies into that notebook's kernel:

```python
%pip install -r pca_requirements.txt
```

Restart the kernel afterwards. Use `pca_requirements-min.txt` for the reproducible older dependency set. Automated checks cover current and older sets on Windows/Linux; cached-data checks also run locally on macOS.

On a licensed Bloomberg computer, install its Python API separately using the [official instructions](https://professional.bloomberg.com/support/api-library/):

```python
%pip install --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi
```

Cached analyses work without `blpapi`. Live discovery/downloads require Bloomberg connectivity and data entitlements; installing packages alone does not provide market data.

## Same workflow

Open `pca_hedge_v103_full.ipynb` and run the engine cell, or run the existing script in a notebook:

```python
%run pca_hedge_v103_full.py
```

After updating, restart the notebook kernel and run the engine cell again. The result field `engine_revision` reads `2026-10-13-printed-report`; this confirms the new engine is loaded. The form opens automatically. Enter `2889 TT Equity`, load or download data, choose the past history window, then press **Run**. A fresh download is preferable for the reported issue because old caches can contain Bloomberg-generated inactive-day fills.

Every analysis run prints its result automatically. In a notebook, the styled report and charts appear first, followed by the plain-text result with its summary, scores, basket weights, alternative recipes and diagnostics. The printed notebook copy uses one brief methodology note; detailed notes remain in the styled report and `result['report_text']`. The same behaviour applies to direct `find_best_hedge(...)` calls and the form's **Run** button. If rich display is unavailable, the text result still prints. Ordinary Python/terminal runs print their structured report as before.

The main recipe, nested validation, recency comparison and next-best recipes select among baskets with at least two instruments. Single-stock and single-ETF candidates are evaluated separately as references, even if their scores are higher. Their relative performance cannot replace the basket or change its grade. A rejected basket stays rejected; a single reference cannot approve it. Default selection prioritizes volatility reduction; negative headline unseen tracking R² prevents qualification. The optional tracking objective retains additional conservative heuristic gates.

Keep at least one basket size of 2 or more in the existing form. A one-instrument universe cannot produce a basket and gets an explicit diagnostic. `broad_search=False` preserves an explicitly pinned configuration for code users and `quick_rehedge`; it is not an automatic fallback to a single. A missing required `force_include` instrument now stops the constrained fit instead of silently disappearing. An unavailable ETF is reported as unavailable, rather than relabelling a stock as an ETF.

If single references complete CV but no basket does, the engine can return an **unvalidated fitted basket reference** when the training data support one. It keeps `trade_eligible=False`, empty recommendation weights, the failed CV rows and earlier nested diagnostics. A fitted reference is not a successful validation result.

Exports default to `hedge_exports` in the working folder; caches default to `hedge_data_cache`. Override `HEDGE_EXPORT_DIR`/`HEDGE_CACHE_DIR`, or select another folder in the form. A mapped network drive is unnecessary.

## Candidate filters and basket sizes

The Candidates tab offers **All eligible candidates** or **Peers only**. Peers means direct Bloomberg peers plus matching BICS/GICS industry peers discovered for the target. Index constituents and second-degree-only peers do not automatically qualify. This is an instrument filter applied before PCA, CV, nested selection, alternatives and final fitting; it does not merely hide names in the report. Current peer classifications still carry historical survivorship/classification bias.

Peers-only turns the local market ETF off by default. Check **Include local broad market ETF** for an explicit exception. Other-sector ETFs remain excluded. Required instruments outside the selected universe produce an actionable constraint error. Existing caches without peer metadata need a new download, or an explicit manual peer list of already-downloaded tickers. Unknown manual names do not silently disappear.

Choose **Require a range or exact size**, then minimum and maximum names. Equal bounds request an exact number. The range is inclusive and includes every integer between the bounds. Unfillable sizes are skipped; the run cannot substitute an instrument count outside the range. Default automatic sizes omit overly large fits according to the existing sample-size heuristic. An explicit range preserves the requested sizes even on short histories, provided fitting is possible; this does not improve validation strength. One-month fits generally remain indicative.

```python
result = find_best_hedge(
    '2889 TT Equity', data=data,
    candidate_scope='peers',
    include_broad_market=False,
    basket_size_range=(2, 4),  # (3, 3) requests exactly three names
    sample_window='2m',
    min_mktcap_usd_mm=1000,
)
# For an older cache, add peer_tickers=['2910 TT Equity', '2911 TT Equity']
```

The form offers 1m, 2m, 3m, 6m, 1y and 2y windows. Book size and hedge duration are optional, initially unset and collapsed under sizing/holding-period risk. They change report sizing or risk units, not the normal search or validation-window defaults. The form preview now uses the same validation-window defaults as the engine.

## Local market references

Broad-market ETF proxies enter the permitted basket universe and receive a separate single-market reference comparison. This family is selected using earlier training/CV data before each outer test, just like the other references. Listing venue controls this mapping: Hong Kong-listed China companies use Hong Kong proxies; a US-listed ADR uses the US market reference while its industry discovery can reflect its country of risk. Raw Bloomberg Index levels are discovery benchmarks, not executable hedge legs.

| Listing market | Reference | ETF candidates |
| --- | --- | --- |
| Hong Kong | Hang Seng Index | 2800 HK |
| Taiwan | Taiwan 50 large-cap proxy | 0050 TT, 006208 TT |
| United States | S&P 500 | SPY US |
| Japan | TOPIX | 1306 JP |
| Mainland China | CSI 300 | 510300 CH |
| Korea | KOSPI 200 | 069500 KS |
| India | Nifty 50 | NIFTYBEES IN |
| Germany | DAX | EXS1 GR |
| United Kingdom | FTSE 100 | ISF LN, VUKE LN |
| France | CAC 40 | CAC FP |
| Australia | S&P/ASX 200 | STW AU, IOZ AU |

These are broad local benchmarks or explicitly labelled large-cap proxies, not claims of complete all-stock coverage. In particular, Taiwan 50 is **not TAIEX**. Unknown markets, missing proxy prices, manual exclusions, required-name conflicts or eligibility constraints produce an unavailable reference rather than a foreign-market substitution. Cached runs do not fetch an absent ETF silently. Aliased exchange codes such as JT/JP are resolved consistently. The existing time-zone filters and conservative asynchronous-return treatment still apply. A local listing reduces timing/currency mismatch but does not implement portfolio FX conversion or prove hedge effectiveness.

The approximate cash-close map now uses Japan's 15:30 JST close, following the [JPX schedule](https://www.jpx.co.jp/english/equities/trading/domestic/01.html). Fixed standard-time closes remain a timing heuristic, not a full historical exchange calendar or a complete correction for asynchronous pricing.

Primary source checks: [Tracker Fund and HSI](https://www.trahk.com.hk/en-hk/trahk-fund/), [Taiwan 50 fund](https://www.yuantaetfs.com/product/detail/0050/PD), [TAIEX coverage](https://www.twse.com.tw/en/indices/indices/series.html), [SPY](https://www.ssga.com/us/en/individual/etfs/state-street-spdr-sp-500-etf-trust-spy), [TOPIX ETF](https://nextfunds.jp/lineup/1306/), [CSI 300 ETF](https://english.sse.com.cn/news/newsrelease/c/4970464.shtml), [KODEX 200](https://www.samsungfund.com/fund/search.do?searchText=069500), [Nifty BeES](https://www.nseindia.com/get-quote/equity/NIFTYBEES/Nippon-India-ETF-Nifty-50-BeES), [DAX fund](https://www.ishares.com/uk/individual/en/literature/fact-sheet/daxex-ishares-core-dax-ucits-etf-de-fund-fact-sheet-en-gb.pdf), [FTSE 100 fund](https://www.ishares.com/uk/individual/en/products/251795/ishares-core-ftse-100-ucits-etf), [CAC 40 fund](https://www.amundietf.com/pdfDocuments/kid-priips/FR0007052782/FRA/FRA/20250611), [ASX 200 fund](https://www.ssga.com/au/en_gb/individual/etfs/state-street-spdr-spasx-200-etf-stw).

## Structured desk analysis

The default report presents the verdict and comparable unseen metrics, primary recipe, distinct alternative basket recipes and single-instrument references. Alternative basket R² is explicitly a selected-configuration diagnostic with selection bias; it is not relabelled as independent nested evidence. It never selects a new recommendation by looking at its later scores. Repeated equivalent recipes are collapsed. When the best single ETF is also the local-market reference, the display combines their labels while retaining both result/CSV roles.

The report also retains rolling stability, recent condition flags, matched-date weight staleness, factor exposures, downside behaviour and search/data-quality settings when available. Their sources and limitations are shown beside the numbers.

Notebook tables use a consistent sans-serif font, numerical alignment and spacing. Word uses structured tables and readable headings; its long text appendix is omitted by default. Use `report='full'` for the diagnostic appendix. The exact structured report text is in `result['report_text']`; detailed calculations are retained in `full_report` and `diagnostic_log`. Downloads print a short summary; `download_hedge_data(..., verbose=True)` restores discovery output. No scores are concealed or forced positive.

## Five usual history windows

The one-month, two-month, three-month, six-month and one-year periods mean past analysis windows, not forecasts of future holding periods. After downloading once:

```python
comparison = compare_history_windows(
    '2889 TT Equity', UI_STATE['data'],
    windows=('1m', '2m', '3m', '6m', '1y'),
    min_mktcap_usd_mm=0,
    restrict_to_target_tz=True,
)
comparison['alternatives_summary']
comparison['alternative_weights_table'].to_csv('2889_history_weights.csv', index=False)
```

Use the appropriate market-cap floor consistently in download and analysis. The notebook's optional comparison cell uses the download's recorded floor. Each period's main row is the basket; stock and ETF references appear separately when available. Their records include `reference_only`. Failed alternatives have blank recommendation weights; full results remain in `diagnostic_results`. One month generally supports only an **indicative** fitted basket, with no unseen score. Longer windows may support holdout, CV or nested validation depending on settings and available observations.

## Missing returns and large universes

Training windows can omit isolated non-finite target-return rows, jointly across every candidate, while retaining their original calendar boundaries. A window needs at least 90% observed target returns and the retained-row floor. Reduced-validation tiers reserve up to 10% of the shortest training lookback for this allowance. Constant targets and substantial missing histories still fail with a distinct diagnostic.

Validation uses the same observed-target dates for every candidate, with at least 90% coverage. It never removes a candidate's own missing test returns to rescue that candidate. All configurations must complete the requested inner folds; incomplete nested evidence cannot qualify the overall hedge. These coverage thresholds are operational heuristics, not statistical confidence guarantees. Scores are conditional on the observed dates, and the run reports missing dates, counts and rejected windows. Missing quotes and their multi-session resumptions are not manufactured daily zero returns.

The short-history search batches single-feature ridge fits using the exact leave-one-out criterion of the original `RidgeCV`, and shares training/PCA work across basket sizes. Single-stock selection does not require PCA; a selected single gets descriptive PCA charts only if charts are enabled. Thin SVD removes the large covariance eigendecomposition and inverse. Isotropic [Ledoit-Wolf shrinkage](https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html) preserves sample eigenvectors and changes their eigenvalues; it is covariance regularization, not an outlier-robust estimator. Winsorization remains a separate candidate-selection setting.

The ticket's headline, volatility reduction and worst-window score use nested evidence. Selected-configuration monitoring is labelled separately and cannot approve a failed hedge. A low fitted-to-test gap is a descriptive difference, not proof of generalization. If nested validation is unavailable, the primary verdict is unvalidated; selected-configuration scores remain visible as diagnostics. The result includes its engine revision and detailed diagnostics. The form keeps a running status while the default report suppresses routine progress prints.

## What best means

Every eligible single instrument is evaluated for reference. Requested baskets compete with one another using PCA exposure ranking, absolute correlation ranking and greedy forward selection that considers complementary exposures. Defaults try basket sizes 2, 3, 5 and 7. Forced names, exclusions, time-zone and size settings still apply. Every requested size is exact. A configuration with too few eligible names is skipped rather than shrunk; forced names occupy those slots and cannot enlarge the basket.

The default inner-CV score is:

```text
mean volatility reduction - 0.5 × fold dispersion - gross_penalty × mean gross
```

PCA identifies directions of shared return variation ([PCA documentation](https://scikit-learn.org/stable/modules/decomposition.html#pca)); similarity of factor loadings does not itself minimize the target’s residual variance. Ridge fits the hedge ratios after candidate selection. Automatic PC counts use an ideal-noise spectral heuristic, not a formal significance test for dependent, heavy-tailed market returns. These penalties are heuristics, not estimated trading costs. Configurations must complete every requested inner-CV fold. A gross cap applies per CV fit, outer refit and rolling diagnostic refit. Final candidates above the cap do not qualify. Each family is selected again using earlier data before the same outer test period. Outer scores describe the historical **selection procedure**, with instruments and weights refitted between periods; they are not an untouched test of today's exact fixed basket. Today's configuration comes from inner CV and is refitted on its training history.

The search covers a finite downloaded universe and several basket heuristics. It does not exhaust every possible subset or guarantee a global executable optimum. Repeatedly changing settings after viewing outer results also introduces selection bias. See the [nested validation example](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html).

## Reading the statistics

Predictive R² is `1 - squared prediction error / target deviation from the evaluated period's mean`. Negative unseen R² means that tracking test failed. It can coexist with lower volatility when the residual mean is mismatched. The mean-return reference is a scoring benchmark calculated after observing that period, not a forecast available beforehand. See the [R² definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.r2_score.html).

Raw fitted R² should be nonnegative for this Ridge fit with an intercept, apart from numerical error; material negative fitted scores raise a diagnostic. The legacy adjusted in-sample field is explicitly labelled a nominal-count **complexity heuristic**, because it does not use Ridge's effective degrees of freedom.

Risk uses the coefficient-only spread `target - X @ weights`; the intercept is not a traded instrument. Volatility reduction and variance reduction are reported separately. Bootstrap intervals resample the errors belonging to the adjacent score. They condition on observed fits and do not rerun the full search, so additional selection and fitting uncertainty is omitted. Predictive R² is not given a Fisher-z correlation interval.

## Result fields

- `best_basket_hedge`, `best_single_hedge`, `best_single_stock_hedge`, `best_single_etf_hedge`: candidate weights, fitted/unseen scores, evidence and `qualified`. Unavailable families return `None`.
- `broad_market_hedge`, `broad_markets`, `market_reference_status`: local market reference, mapping and availability.
- `basket_comparison`: distinct alternative recipes and their conditional diagnostic scores.
- `primary_hedge_family`: `basket` for the default search. Single entries in `hedge_alternatives` have `reference_only=True`; their evidence status is not the main recommendation.
- `trade_eligible`, `trade_weights`: overall screen and weights; rejected/unvalidated runs have empty trade weights.
- `candidate_weights`, legacy `weights`: fitted reference weights, including failed candidates.
- `nested_unseen_returns`, `bootstrap_ci`, `selected_config_bootstrap_ci`: auditable errors and separately identified intervals.
- `search`, `cv_summary`, `cv_detail`: search scope and selection diagnostics.
- `training_data_diagnostics`, `evaluation_data_diagnostics`: affected calendar windows, retained rows, missing dates and acceptance.
- `engine_revision`: the loaded engine version.
- `fallback_reason`, `prior_nested_validation`: explain the unvalidated fitted-basket fallback and retain earlier nested diagnostics separately from its unavailable headline evidence.

Legacy `best_single`/`best_etf` remain correlation-picked benchmarks; use the new `*_hedge` fields for the broader search. Stock/ETF categories use the instrument mappings. A manually supplied ETF absent from those mappings may be categorized as a stock.

## Verification and limits

```bash
python -m unittest discover -s tests -p test_hedge_search.py -v
```

The 58 offline tests include stronger-single reference cases that must keep a basket primary, holdout chronology, constrained required instruments, an absent ETF, single-only settings, and pinned rehedges. They also include 1,132-candidate short-history coverage, sparse target gaps, rejection of missing hedge test returns, empty nested evidence, consistent rejected-report wording, and numerical equivalence of the faster PCA/single-feature ridge calculations. Existing checks cover matched validation windows, no use of future test returns in prior selection, R² arithmetic, actual-spread risk, interval association, negative-result rejection, price handling, caps, caches, the form, notebook consistency, charts and Word/CSV export. Printed-output checks cover notebook and terminal runs, display failure, and unchanged weights and validation scores. Synthetic ticker labels are not actual 2889 market data.

Live 2889 history and the other computer's Bloomberg session were unavailable. Verify that particular history with a fresh download there. The engine uses adjusted prices and weighted log returns as a P&L approximation. Explicit FX conversion, borrow, fees, financing and turnover costs are outside the optimization. Historical support is evidence for reference, not a guarantee of future performance.

Drawdown now uses the coefficient-only spread, including the starting zero level, rather than subtracting an untradeable fitted intercept. Two-day returns are sampled without overlap before cumulating. The path remains a log-spread approximation, not financed portfolio P&L. Rolling regression tracking error and coefficient-only spread volatility are separate diagnostics.

Short windows retain fitted factor, tail and spread-path diagnostics where computable. These do not upgrade their validation tier. Holdout and recent-condition verdicts describe limited evidence or deterioration without prescribing a trade size.

The fitted cumulative chart also uses non-overlapping two-day returns on a common phase for target and spread. Chart CV sensitivity and monitoring lines are labelled as diagnostics and heuristics.

The report uses a softer slate and teal palette, metric cards, clearer section headings and lighter table bands. In-sample R² is explicitly labelled for every history window, including 1y; it measures the current training fit, whose row count is shown. Repeated explanations are gathered into one expandable notebook methodology section; Word uses one brief methodology paragraph. Detailed notes remain in the result transcript and optional full report.

The report shows up to five distinct additional basket recipes by default; set `alternative_baskets=8` (1–20) or use the form’s Alternative baskets control for more. It scans past duplicate configurations, retains the selected recipe, and respects the requested scope and basket sizes. Fewer alternatives are shown when the tested configurations produce fewer distinct recipes. This is a reporting change and does not rerank the primary basket using alternative test results.

Charts are enabled by default and included in the structured notebook, standalone HTML and Word exports. The previous PCA scree/map, correlations, fitted spread path, rolling volatility and basket-size sensitivity views are retained, with basket-weight and alternative-score comparisons. Rolling tracking-error/R² charts appear when available; 1m/2m also get clearly labelled fitted charts. Set `show_plots=False` to omit figures. Charts do not upgrade the validation tier.

Charts lead the report immediately after the title and analysis dates, before the summary and basket tables. The regression checks also verify positive coefficients map to SHORT, negative coefficients to LONG, the spread subtracts the hedge coefficients without a traded intercept, and unvalidated/failed verdicts expose no trade weights.
