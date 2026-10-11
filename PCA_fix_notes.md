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

The old stale-price guard deleted long runs of identical reported prices. That could create missing target returns and skip every fold. The revision retains unchanged observations and distinguishes missing returns, genuinely constant returns and insufficient history. Bounded fills use earlier observations only; a missing interval's accumulated move is not labelled an ordinary one-row return.

Fresh downloads request `ACTIVE_DAYS_ONLY`, documented in the [Bloomberg guide](https://data.bloomberglp.com/professional/sites/4/blpapi-developers-guide-2.54.pdf). A shared absent day is inferred as an exchange closure only when the target and at least two same-exchange peers lack observations. Isolated target gaps remain problems. Old caches may contain vendor-generated fills; redownload for clearer provenance.

The original failure was reproduced on synthetic flat-price data and the revised engine completed that dataset. The actual cause in the user's 2889 history remains unverified without the cache or a live connection.

## Portability

Matplotlib settings are filtered against installed rcParams and title colors are set directly, addressing `axes.titlecolor`. The ADF wrapper supports old/new statsmodels APIs. Cached analysis imports without Bloomberg's package; live-download errors explain installation. Local export/cache folders replace the mapped-drive default.

The repository includes a notebook, current and pinned older dependencies, setup instructions and Windows/Linux CI. Offline checks also run on macOS with both dependency sets. They cover analysis, charts, the form and Word/CSV export, not another computer's Bloomberg session or real 2889 weights.

See `PCA_README.md` for setup, result fields and the history comparison.
