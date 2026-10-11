# PCA hedge finder

Compare a basket, single stock and single ETF for the same target and past history window using the existing form. Candidates are selected using earlier training/CV data; later validation is reported separately. Negative headline unseen tracking R² cannot qualify a supported hedge.

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

The form opens automatically. Enter `2889 TT Equity`, load or download data, choose the past history window, then press **Run**. A fresh download is preferable for the reported issue because old caches can contain Bloomberg-generated inactive-day fills.

The report and Word export include the best basket, single stock and single ETF, with hedge dollars per $100 target and evidence status. Default selection prioritizes volatility reduction; negative headline unseen tracking R² prevents qualification. The optional tracking objective retains additional conservative heuristic gates.

Exports default to `hedge_exports` in the working folder; caches default to `hedge_data_cache`. Override `HEDGE_EXPORT_DIR`/`HEDGE_CACHE_DIR`, or select another folder in the form. A mapped network drive is unnecessary.

## Four past history windows

The one-year, six-month, three-month and one-month periods mean past analysis windows, not forecasts of future holding periods. After downloading once:

```python
comparison = compare_history_windows(
    '2889 TT Equity', UI_STATE['data'],
    windows=('1y', '6m', '3m', '1m'),
    min_mktcap_usd_mm=0,
    restrict_to_target_tz=True,
)
comparison['alternatives_summary']
comparison['alternative_weights_table'].to_csv('2889_history_weights.csv', index=False)
```

Use the appropriate market-cap floor consistently in download and analysis. The notebook's optional comparison cell uses the download's recorded floor. Each period includes basket, stock and ETF alternatives when available. Failed alternatives have blank recommendation weights; full results remain in `diagnostic_results`. One month generally supports only an **indicative** fitted candidate, with no unseen score. Longer windows may support holdout, CV or nested validation depending on settings and available observations.

## What best means

Every eligible single instrument competes. Requested baskets use PCA exposure ranking, absolute correlation ranking and greedy forward selection that considers complementary exposures. Defaults try basket sizes 2, 3, 5 and 7 alongside singles. Forced names, exclusions, time-zone and size settings still apply.

The default inner-CV score is:

```text
mean volatility reduction - 0.5 × fold dispersion - gross_penalty × mean gross
```

PCA identifies directions of shared return variation ([PCA documentation](https://scikit-learn.org/stable/modules/decomposition.html#pca)); similarity of factor loadings does not itself minimize the target’s residual variance. Ridge fits the hedge ratios after candidate selection. Automatic PC counts use an ideal-noise spectral heuristic, not a formal significance test for dependent, heavy-tailed market returns. These penalties are heuristics, not estimated trading costs. Configurations must complete every requested inner-CV fold. A gross cap applies per CV fit and outer refit, and final candidates above the cap do not qualify. Each family is selected again using earlier data before the same outer test period. Outer scores describe the historical **selection procedure**, with instruments and weights refitted between periods; they are not an untouched test of today's exact fixed basket. Today's configuration comes from inner CV and is refitted on its training history.

The search covers a finite downloaded universe and several basket heuristics. It does not exhaust every possible subset or guarantee a global executable optimum. Repeatedly changing settings after viewing outer results also introduces selection bias. See the [nested validation example](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html).

## Reading the statistics

Predictive R² is `1 - squared prediction error / target deviation from the evaluated period's mean`. Negative unseen R² means that tracking test failed. It can coexist with lower volatility when the residual mean is mismatched. The mean-return reference is a scoring benchmark calculated after observing that period, not a forecast available beforehand. See the [R² definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.r2_score.html).

Raw fitted R² should be nonnegative for this Ridge fit with an intercept, apart from numerical error; material negative fitted scores raise a diagnostic. The legacy adjusted in-sample field is explicitly labelled a nominal-count **complexity heuristic**, because it does not use Ridge's effective degrees of freedom.

Risk uses the coefficient-only spread `target - X @ weights`; the intercept is not a traded instrument. Volatility reduction and variance reduction are reported separately. Bootstrap intervals resample the errors belonging to the adjacent score. They condition on observed fits and do not rerun the full search, so additional selection and fitting uncertainty is omitted. Predictive R² is not given a Fisher-z correlation interval.

## Result fields

- `best_basket_hedge`, `best_single_hedge`, `best_single_stock_hedge`, `best_single_etf_hedge`: candidate weights, fitted/unseen scores, evidence and `qualified`. Unavailable families return `None`.
- `trade_eligible`, `trade_weights`: overall screen and weights; rejected/unvalidated runs have empty trade weights.
- `candidate_weights`, legacy `weights`: fitted reference weights, including failed candidates.
- `nested_unseen_returns`, `bootstrap_ci`, `selected_config_bootstrap_ci`: auditable errors and separately identified intervals.
- `search`, `cv_summary`, `cv_detail`: search scope and selection diagnostics.

Legacy `best_single`/`best_etf` remain correlation-picked benchmarks; use the new `*_hedge` fields for the broader search. Stock/ETF categories use the instrument mappings. A manually supplied ETF absent from those mappings may be categorized as a stock.

## Verification and limits

```bash
python -m unittest discover -s tests -p test_hedge_search.py -v
```

Offline tests cover competition, matched validation windows, no use of future test returns in prior selection, R² arithmetic, actual-spread risk, interval association, negative-result rejection, price handling, caps, caches, the form, notebook consistency, charts and Word/CSV export. Synthetic ticker labels are not actual 2889 market data.

Live 2889 history and the other computer's Bloomberg session were unavailable. Verify that particular history with a fresh download there. The engine uses adjusted prices and weighted log returns as a P&L approximation. Explicit FX conversion, borrow, fees, financing and turnover costs are outside the optimization. Historical support is evidence for reference, not a guarantee of future performance.
