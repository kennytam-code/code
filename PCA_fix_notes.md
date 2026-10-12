# PCA revision notes

The existing notebook/form workflow is preserved. The report now compares the best basket, single stock and single ETF. The four-period helper returns both forms for the past one-year, six-month, three-month and one-month windows.

## Search and screening

All eligible singles compete with PCA, correlation and forward-selected baskets. Forward selection considers complementary exposures that marginal correlation can miss. Every configuration must complete the requested inner-CV folds. Family winners are selected using earlier data before being evaluated on the same outer periods. Outer test results do not select today's winning configuration. Candidate completeness is determined on training rows, so later missing prices cannot remove a name from an earlier fit.

Default selection prioritizes volatility reduction with dispersion/gross penalties. This is a finite heuristic search within the downloaded universe, not an exhaustive optimum over every possible basket. Gross caps apply per CV fit/outer refit; final weights exceeding the cap do not qualify.

Negative headline unseen tracking R² prevents qualification even if volatility falls. Failed scores and candidate weights remain diagnostic references, with blank recommendation weights in the history comparison. In-sample-only candidates are indicative and have no unseen scores. Incomplete validation cannot qualify as full support.

## Statistical corrections

- Raw fitted R² is checked for material negative or non-finite values.
- The nominal-count adjusted field is labelled a complexity heuristic, not Ridge effective degrees of freedom.
- Risk uses the coefficient-only spread, without treating a regression intercept as a traded instrument. Volatility and variance reduction are distinct.
- Nested bootstrap intervals use the actual nested errors; selected-configuration intervals are separately identified. Errors are chronological for block resampling.
- Intervals condition on observed fits and omit additional search/refitting uncertainty.
- The Fisher-z noise band was removed because predictive R² is not generally squared correlation.
- Numerical variance thresholds are consistent between eligibility and scoring. Unsupported synthetic claims about optimal history were removed from the report.

R² of -0.20 means 20% more squared prediction error than deviation from the evaluated period's mean. It can coexist with lower volatility because R² also reflects a residual mean mismatch. See [scikit-learn's definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.r2_score.html). Reusing the same test to hunt for a positive score would undermine validation.

## Reported 2889 failure

The old stale-price guard deleted long runs of identical reported prices. That could create missing target returns and skip every fold. The revision retains unchanged observations and distinguishes missing returns, genuinely constant returns and insufficient history. Price display fills use earlier observations only. Missing quotes and a missing interval’s accumulated resumption move are excluded from daily-return fitting and evaluation.

Fresh downloads request `ACTIVE_DAYS_ONLY`, documented in the [Bloomberg guide](https://data.bloomberglp.com/professional/sites/4/blpapi-developers-guide-2.54.pdf). A shared absent day is inferred as an exchange closure only when the target and at least two same-exchange peers lack observations. Isolated target gaps now use common observed-row masks with a 90% coverage guard. Missing dates are reported; substantial gaps remain unscoreable. Old caches may contain vendor-generated fills; redownload for clearer provenance.

The original failure was reproduced on synthetic flat-price data and the revised engine completed that dataset. The actual cause in the user's 2889 history remains unverified without the cache or a live connection.

## Portability

Matplotlib settings are filtered against installed rcParams and title colors are set directly, addressing `axes.titlecolor`. The ADF wrapper supports old/new statsmodels APIs. Cached analysis imports without Bloomberg's package; live-download errors explain installation. Local export/cache folders replace the mapped-drive default.

The repository includes a notebook, current and pinned older dependencies, setup instructions and Windows/Linux CI. Offline checks also run on macOS with both dependency sets. They cover analysis, charts, the form and Word/CSV export, not another computer's Bloomberg session or real 2889 weights.

See `PCA_README.md` for setup, result fields and the history comparison.

## October 12 regression repair

The production-sized report exposed a missed performance case: `_select_and_fit` ran large PCA calculations before fitting each fixed single instrument. The new path skips PCA for singles, batches the original ridge leave-one-out criterion, shares PCA across basket sizes, and computes Ledoit-Wolf leading components without a large covariance inverse/eigendecomposition. Numerical tests compare eigenvalues, component subspaces, alpha choices, coefficients and residuals with the original library calculations.

Two missing training returns no longer invalidate an otherwise usable 46-row window. Cleaning removes the same target rows across all columns, preserves chronology, requires coverage/retained rows, and reports dates. Validation masks are common across candidates; candidate-specific test gaps still fail their fold. An empty nested result has a stable schema and returns an unvalidated reference report rather than a `KeyError`.

The report previously mixed negative nested R² with positive selected-configuration risk reduction and worst-window scores. Primary ticket figures now use the same nested source. Monitoring prose no longer recommends full size after rejection. Selected-configuration weight stability does not claim that the whole search picked the same instrument, and a small fitted/unseen gap does not assert that a model generalizes. Gaussian coverage promises were removed. Word exports identify selected-configuration evidence and monitoring separately.

Current and pinned older dependencies pass 32 offline tests on macOS. Windows/Linux CI runs the same suite against both dependency sets. The production-sized fixtures are synthetic, including 1,132 eligible singles; their speed and successful execution do not establish the actual 2889/AAPL hedge quality. The uploaded error report contains output and dates, not the underlying prices/configuration needed to reproduce the AAPL winner or determine the real cause of each missing quote. No score is forced positive.

## Basket as the primary hedge

The default search now selects only baskets with at least two instruments for the main recipe, every nested outer selection, recency diagnostics and next-best basket recipes. Every eligible single stock and ETF is still evaluated using earlier data on the same planned validation periods, but appears as a reference and cannot replace the basket or change its grade. `broad_search=False` remains available for an explicitly pinned configuration, including fast rehedging. No eligible basket produces an explicit constraint/data diagnostic rather than an implicit single fallback.

Further review found required instruments could be dropped when unavailable, and the legacy ETF benchmark could fall back to a stock. Required instruments now fail the constrained fit explicitly, and absent ETFs remain unavailable. Correlation-picked references use eligible instruments and gross limits; diagnostic comparisons only declare relative performance when their window sets match. The main basket's evidence status now agrees with the ticket screen, including the holdout tier. Single references are marked in Word, CSV and history comparisons.

When singles complete CV but no basket does, usable training data can still produce a fitted basket reference. It is explicitly unvalidated and returns no recommendation weights. The failed CV rows and prior nested diagnostics are retained; they do not become a successful test of this fitted basket. Default form sizes are 2, 3, 5 and 7.

The updated suite has 39 offline regression checks, including stronger-single comparisons, basket-only nested selection, holdout chronology, required-instrument failures, absent ETFs, single-only settings, and pinned basket/single refits. Actual market-data quality and the live Bloomberg session still require the original price cache or a fresh download on the licensed computer.
