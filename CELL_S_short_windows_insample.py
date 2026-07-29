# =============================================================================
# CELL S: SHORT-WINDOW MODE — v77 add-on to pca_hedge_v75_full.py
# =============================================================================
# Paste this AFTER CELL 2 (the engine). CELL 1 and CELL 2 are untouched and
# find_best_hedge() behaves exactly as it did in v75.
#
# v77 vs v76: IN-SAMPLE ONLY, and windows end on an explicit date (28-Jul)
# rather than "today". The leave-one-out machinery is gone.
#
# WHY A SEPARATE ESTIMATOR AT ALL
# -------------------------------
# find_best_hedge() needs, at its default settings, 378+ return rows before its
# sufficiency check will let it start. July MTD has ~20. So these windows are
# not a harder version of the same job; they are a different job:
#
#   find_best_hedge()      "what is a durable hedge for this name?"    predictive
#   short_window_hedge()   "what has been moving with this name since
#                           the 13th, and how much of its variance does
#                           that explain?"                             descriptive
#
# WHAT IN-SAMPLE ONLY MEANS HERE
# ------------------------------
# Every number below is fitted and scored on the same rows. That is the correct
# tool for ATTRIBUTION — decomposing a window that has already happened — and
# the wrong tool for forecasting. The R-squared is not an estimate of how the
# basket will perform tomorrow; it is a statement about how much of GMD's
# realized July variance these names co-moved with. Both readings are useful.
# Only one of them is a hedge recommendation, and it isn't this one.
#
# Two guards remain, because dropping out-of-sample testing makes them load-
# bearing rather than optional:
#   * ADJUSTED R-squared is reported next to raw R-squared. Raw in-sample R2
#     rises mechanically with every leg added; on 13 rows a 5-leg basket can
#     hit 0.9 while explaining nothing. Adjusted R2 charges for parameters and
#     is the only column that can be compared ACROSS windows with different
#     leg counts.
#   * BASKET SIZE IS CAPPED BY OBSERVATION COUNT (4 rows per leg by default).
#     Without a hold-out to expose it, an oversized basket has nothing to stop
#     it. Raise obs_per_leg to be stricter; you cannot disable the cap.
#   * Tracking error uses ddof = k+1, so the residual spread is not flattered
#     by the parameters that were fitted to shrink it.
#
# READ SECTION [3]. Three nested windows exist so that agreement between them
# can be evidence and disagreement can be evidence. A name that survives all
# three start dates is telling you something an in-sample R-squared cannot.
# =============================================================================

from datetime import datetime   # numpy / pandas already imported in CELL 1


# ─────────────────────────────────────────────────────────────────────────────
# Window specification
# ─────────────────────────────────────────────────────────────────────────────
def _last_bday_before(ts):
    ts = pd.Timestamp(ts).normalize()
    return (ts - pd.tseries.offsets.BDay(1)).normalize()


def default_windows(end=None):
    """The three requested windows, all ending on `end` (default: the last
    business day before today).

      1. month-to-date  : 1st of `end`'s month → end
      2. from the 6th   : 6th  of `end`'s month → end
      3. from the 13th  : 13th of `end`'s month → end

    Returns [(label, start, end), ...]. Edit here to change the dates."""
    end = pd.Timestamp(end).normalize() if end is not None \
        else _last_bday_before(datetime.now())
    y, m = end.year, end.month
    return [
        (f"MTD (01-{end:%b} →)", pd.Timestamp(y, m, 1),  end),
        (f"from 06-{end:%b}",    pd.Timestamp(y, m, 6),  end),
        (f"from 13-{end:%b}",    pd.Timestamp(y, m, 13), end),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Data slicing — zero Bloomberg calls, reuses the CELL A download
# ─────────────────────────────────────────────────────────────────────────────
def slice_data(data, start, end, lead=1):
    """Return a COPY of the CELL A data dict restricted to [start, end].

    `lead` extra price rows are kept BEFORE `start` so the first return inside
    the window is a real return. Without it the 01-Jul close would have no
    30-Jun close to difference against and July MTD would silently begin on the
    2nd. Market-cap paths and membership snapshots are trimmed to `end`."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    px = data['prices']
    idx = px.index
    before = idx[idx < start]
    lead_from = before[-lead] if len(before) >= lead else (
        before[0] if len(before) else start)
    out = dict(data)
    out['prices'] = px.loc[(idx >= lead_from) & (idx <= end)].copy()
    mh = data.get('mktcap_hist')
    if isinstance(mh, pd.DataFrame) and not mh.empty:
        out['mktcap_hist'] = mh.loc[mh.index <= end].copy()
    pm = data.get('pit_members') or {}
    if pm:
        out['pit_members'] = {k: v for k, v in pm.items()
                              if pd.Timestamp(k) <= end}
    out['_window'] = (start, end)
    return out


def _adj_r2(r2, n, k):
    """Adjusted R-squared. Returns NaN when there are not enough residual
    degrees of freedom for the number to mean anything."""
    if n - k - 1 <= 0:
        return np.nan
    return 1.0 - (1.0 - r2) * (n - 1) / (n - k - 1)


# ─────────────────────────────────────────────────────────────────────────────
# The short-window estimator — IN SAMPLE
# ─────────────────────────────────────────────────────────────────────────────
def short_window_hedge(
    target, data, start, end,
    label=None,
    basket_size=None,          # None → auto from the observation count
    max_basket_size=5,
    obs_per_leg=4,             # DOF rule: n_obs >= obs_per_leg * k. Load-bearing
                               # now that nothing out-of-sample checks the fit.
    min_mktcap_usd_mm=1000,
    exclude=None,
    force_include=None,
    restrict_to_target_tz='auto',
    tz_tolerance_hours=3.0,
    winsorize_pct=0.0,         # OFF: with ~15 rows, clipping the 1%/99% tails
                               # clips most of the information there is
    robust_cov='ledoit',       # ON: p >> n here, shrinkage is not optional
    n_pc=None,                 # None → auto, capped at n_obs // 4
    max_zero_frac=0.34,        # drop candidates this often unchanged in-window
                               # (short-window analogue of the stale guard)
    allow_two_day=False,       # 2-day overlapping returns halve an already
                               # tiny sample; opt in explicitly
    notional_mm=None,
    verbose=True,
):
    """Fit a hedge basket for `target` on the rows in [start, end], in sample.

    Returns a dict with: label, start, end, n_obs, basket, weights, gross,
    r2_in, r2_adj, te_bp_day, te_ann, best_single, best_single_r2, returns.

    `weights` is a pd.Series indexed by full ticker, using the SAME sign
    convention as find_best_hedge's recipe: a POSITIVE weight means SHORT that
    many dollars per $100 long the target."""
    legs, pf_w, is_pf, pf_label = _coerce_targets(target)
    start = pd.Timestamp(start).normalize()
    end = pd.Timestamp(end).normalize()
    label = label or f"{start:%d-%b} → {end:%d-%b}"
    say = (lambda *a: print(*a)) if verbose else (lambda *a: None)

    d = slice_data(data, start, end)
    prices = d['prices'].copy()
    missing = [l for l in legs if l not in prices.columns]
    if missing:
        raise ValueError(f"legs {missing} are not in the downloaded data — "
                         f"re-run CELL A (optionally with force_include=)")

    target_keepset = set(legs)
    forced, fi_unres = _resolve_force_include(force_include, prices.columns,
                                              legs[0])
    if fi_unres:
        say(f"    ⚠ force_include {fi_unres} not in the download — ignored")

    kept, dropped_ex = _apply_exclusions(
        [c for c in prices.columns if c not in target_keepset], exclude)
    kept += [c for c in dropped_ex if c in forced]
    prices = prices[list(dict.fromkeys(list(target_keepset) + kept))]

    # ── size floor, applied AS-OF the window start (no current-cap look-ahead)
    caps = data.get('mktcap_usd_mm') or {}
    ch = data.get('mktcap_hist')
    ch = ch if isinstance(ch, pd.DataFrame) else pd.DataFrame()

    def cap_asof(c):
        if not ch.empty and c in ch.columns:
            s = ch[c]
            s = s[s.index <= start].dropna()
            if len(s):
                return float(s.iloc[-1])
        return caps.get(c)

    if min_mktcap_usd_mm:
        keep, n_drop = list(target_keepset), 0
        for c in prices.columns:
            if c in target_keepset or c in forced or c.split(' ')[0] in ETF_SHORT_SET:
                if c not in keep:
                    keep.append(c)
                continue
            mc = cap_asof(c)
            if mc is None or mc >= min_mktcap_usd_mm:
                keep.append(c)          # unknown cap → keep (fail-open)
            else:
                n_drop += 1
        if n_drop:
            say(f"    size floor {_fmt_mktcap(min_mktcap_usd_mm)} as-of "
                f"{start:%d-%b}: dropped {n_drop} names")
            prices = prices[list(dict.fromkeys(keep))]

    # ── timezone: same rule as the main engine ───────────────────────────────
    tgt_close = _close_utc_of(legs[0]) if not is_pf else (
        float(np.mean([_close_utc_of(c) or np.nan for c in legs])))
    others = [c for c in prices.columns if c not in target_keepset]
    if tgt_close is None or np.isnan(tgt_close):
        same_tz, do_restrict = [], False
    else:
        same_tz = [c for c in others
                   if _close_utc_of(c) is not None
                   and _close_gap_hours(_close_utc_of(c), tgt_close)
                   <= tz_tolerance_hours]
        do_restrict = (restrict_to_target_tz is True or
                       (restrict_to_target_tz == 'auto' and len(same_tz) >= 30))
    if do_restrict and len(same_tz) < len(others):
        keep_tz = same_tz + [c for c in list(forced) + legs if c not in same_tz]
        say(f"    timezone restriction: {len(others)} → {len(keep_tz)} "
            f"candidates within {tz_tolerance_hours:.0f}h of the target's close")
        prices = prices[list(dict.fromkeys(list(target_keepset) + keep_tz))]

    closes = [_close_utc_of(c) for c in prices.columns]
    known = sorted({c for c in closes if c is not None})
    max_gap = max((_close_gap_hours(a, b)
                   for i, a in enumerate(known) for b in known[i + 1:]),
                  default=0.0)
    two_day = (any(c is None for c in closes) or max_gap > tz_tolerance_hours)
    if two_day and not allow_two_day:
        say(f"    ⚠ universe is cross-timezone (max close gap {max_gap:.1f}h) "
            f"but the window is too short to spend half of it on 2-day "
            f"overlapping returns — staying on DAILY returns. Async bias is "
            f"NOT corrected; treat any cross-tz name in the basket with "
            f"suspicion, or pass restrict_to_target_tz=True.")
        two_day = False
    ann = np.sqrt(252 / (2 if two_day else 1))

    # ── returns, trimmed to the window ───────────────────────────────────────
    rets = np.log(prices / prices.shift(1))
    if is_pf:
        present = [c for c in legs if c in rets.columns]
        w = pd.Series([pf_w[c] for c in present], index=present)
        w = w / (w.abs().sum() or 1.0)
        rets[PORTFOLIO_COL] = rets[present].mul(w, axis=1).sum(axis=1,
                                                              skipna=False)
        tgt, target_short = PORTFOLIO_COL, pf_label
    else:
        tgt = legs[0]
        target_short = tgt.split(' ')[0]
    if two_day:
        rets = rets.rolling(2).sum()
    rets = rets.loc[rets.index >= start]

    # ── candidate screen ─────────────────────────────────────────────────────
    skipped, ok = {}, []
    for c in rets.columns:
        if c in target_keepset or c == tgt:
            continue
        s = rets[c]
        if s.isna().any():
            skipped['incomplete'] = skipped.get('incomplete', 0) + 1
        elif s.std() < 1e-8:
            skipped['flat'] = skipped.get('flat', 0) + 1
        elif (s.abs() < 1e-9).mean() > max_zero_frac:
            skipped['illiquid'] = skipped.get('illiquid', 0) + 1
        else:
            ok.append(c)
    if tgt not in rets.columns or rets[tgt].isna().any():
        raise ValueError(f"{target_short} has missing prices inside {label} "
                         f"— cannot fit this window")
    rets = rets[[tgt] + ok].dropna()
    n_obs = len(rets)

    # ── degrees of freedom ───────────────────────────────────────────────────
    k_cap = max(1, min(max_basket_size, n_obs // obs_per_leg))
    k = int(basket_size or k_cap)
    if k > k_cap:
        say(f"    ⚠ basket_size={k} requested but {n_obs} observations only "
            f"support {k_cap} legs at {obs_per_leg} obs/leg — using {k_cap}")
        k = k_cap
    f_ok = [c for c in forced if c in ok]
    if len(f_ok) > k:
        say(f"    ⚠ {len(f_ok)} force_include names exceed the {k}-leg budget "
            f"— basket grows to hold them")
        k = len(f_ok)
    if n_obs < 8:
        say(f"    ⚠ {n_obs} observations — below any threshold at which a "
            f"fitted hedge means anything. Reported for completeness only.")

    say(f"    {n_obs} return rows × {len(ok)} candidates → {k}-leg basket"
        + (f"   (skipped: " + ", ".join(f"{v} {kk}" for kk, v in skipped.items())
           + ")" if skipped else ""))

    # ── selection + fit ──────────────────────────────────────────────────────
    npc_cap = max(1, min(n_obs // 4, 5))

    def select(tr):
        cols = [c for c in tr.columns if c != PORTFOLIO_COL]
        trw = _winsorize_returns(tr[cols], winsorize_pct)
        sd = trw.std().replace(0, 1.0)
        tr_sc = (trw - trw.mean()) / sd
        cap = max(1, min(len(cols) - 1, npc_cap))
        npc = int(min(n_pc or npc_cap, cap))
        pca = _pca_fit(tr_sc, npc, robust_cov)
        lds = pd.DataFrame(
            pca.components_.T * np.sqrt(np.clip(pca.explained_variance_, 0, None)),
            index=cols, columns=[f'PC{i+1}' for i in range(npc)])
        if is_pf:
            lin = [c for c in legs if c in lds.index]
            wv = np.array([pf_w[c] for c in lin], dtype=float)
            wv = wv / (np.abs(wv).sum() or 1.0)
            lds.loc[PORTFOLIO_COL] = (lds.loc[lin].values * wv[:, None]).sum(0)
        pool = [c for c in tr.columns if c != tgt and c not in target_keepset]
        rank = _rank_scores(lds, tr, tgt, pool)
        rest = [t for t in rank.index if t not in f_ok]
        return f_ok + rest[:max(0, k - len(f_ok))]

    basket = select(rets)
    if not basket:
        raise ValueError(f"no usable candidates inside {label}")
    reg, r2_in, resid = _fit_basket(rets, tgt, basket)
    kk = len(basket)
    weights = pd.Series(reg.coef_, index=basket)      # +ve = SHORT
    gross = float(weights.abs().sum())
    r2_adj = _adj_r2(float(r2_in), n_obs, kk)

    # residual spread charged for the parameters fitted to shrink it
    dof = max(1, n_obs - kk - 1)
    te_day = float(np.sqrt(np.sum(resid ** 2) / dof))

    # ── best single instrument over the same window, same footing ────────────
    pool_single = [c for c in ok if c.split(' ')[0] in ETF_SHORT_SET] or ok
    corrs = {c: abs(rets[tgt].corr(rets[c])) for c in pool_single}
    corrs = {c: v for c, v in corrs.items() if not np.isnan(v)}
    best_single, bs_r2, bs_adj, bs_beta = None, np.nan, np.nan, np.nan
    if corrs:
        best_single = max(corrs, key=corrs.get)
        reg_s, bs_r2, _ = _fit_basket(rets, tgt, [best_single])
        bs_r2 = float(bs_r2)
        bs_adj = _adj_r2(bs_r2, n_obs, 1)
        bs_beta = float(reg_s.coef_[0])

    return {
        'label': label, 'start': start, 'end': end,
        'target': target_short, 'target_col': tgt,
        'n_obs': n_obs, 'n_candidates': len(ok),
        'basket': basket, 'weights': weights, 'gross': gross,
        'r2_in': float(r2_in), 'r2_adj': r2_adj,
        'te_bp_day': te_day * 1e4, 'te_ann': te_day * ann,
        'tgt_vol_ann': float(np.std(rets[tgt].values, ddof=1) * ann),
        'best_single': best_single, 'best_single_r2': bs_r2,
        'best_single_r2_adj': bs_adj, 'best_single_beta': bs_beta,
        'corr_best_single': corrs.get(best_single, np.nan) if corrs else np.nan,
        'notional_mm': notional_mm, 'two_day': two_day,
        'returns': rets, 'reg': reg, 'skipped': skipped,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Runner: three windows + the stability comparison
# ─────────────────────────────────────────────────────────────────────────────
def run_short_windows(target, data, windows=None, end=None, verbose=True, **kw):
    """Run short_window_hedge over several nested windows and print the
    per-window recipes plus the cross-window stability report.

    windows : list of (label, start, end). Defaults to month-to-date /
              from-the-6th / from-the-13th, all ending on `end`.
    end     : common end date for the default windows (e.g. '2026-07-28').
    **kw    : passed to short_window_hedge (min_mktcap_usd_mm, force_include,
              exclude, basket_size, notional_mm, restrict_to_target_tz, ...).

    Returns {'runs', 'stability', 'summary', 'core', 'errors'}."""
    windows = windows or default_windows(end)
    L = 82
    runs, errs = [], []
    print("=" * L)
    print(f"SHORT-WINDOW HEDGE (IN SAMPLE) — {_coerce_targets(target)[3]}"
          f"   ·   {len(windows)} nested windows")
    print("=" * L)
    for lab, s, e in windows:
        print(f"\n  ▸ {lab}   [{pd.Timestamp(s):%Y-%m-%d} → "
              f"{pd.Timestamp(e):%Y-%m-%d}]")
        try:
            runs.append(short_window_hedge(target, data, s, e, label=lab,
                                           verbose=verbose, **kw))
        except Exception as ex:
            print(f"    ✗ skipped: {ex}")
            errs.append((lab, str(ex)))
    if not runs:
        print("\nNo window produced a fit — nothing to compare.")
        return {'runs': [], 'stability': pd.DataFrame(),
                'summary': pd.DataFrame(), 'core': [], 'errors': errs}

    notional = next((r['notional_mm'] for r in runs if r['notional_mm']), None)

    # ── [1] per-window recipes ───────────────────────────────────────────────
    print("\n" + "=" * L)
    print("[1] RECIPE BY WINDOW   (SHORT $x per $100 long the target)")
    print("=" * L)
    for r in runs:
        print(f"\n  {r['label']}  —  {r['n_obs']} obs, {len(r['basket'])} legs, "
              f"gross ${r['gross'] * 100:.0f} per $100")
        rows = []
        for tk, w in r['weights'].sort_values(key=abs, ascending=False).items():
            cell = [tk.split(' ')[0], 'SHORT' if w > 0 else 'LONG ',
                    f"${abs(w) * 100:6.1f}"]
            if notional:
                cell.append(f"${abs(w) * notional:6.2f}mm")
            rows.append(cell)
        hdr = ['Ticker', 'Side', 'per $100'] + (
            [f'per ${notional:.0f}mm'] if notional else [])
        _print_table(hdr, rows, indent='    ')

    # ── [2] in-sample fit ────────────────────────────────────────────────────
    print("\n" + "=" * L)
    print("[2] IN-SAMPLE FIT   (compare windows on ADJ R2, never on raw R2)")
    print("=" * L)
    srows = []
    for r in runs:
        srows.append([
            r['label'], f"{r['n_obs']}", f"{len(r['basket'])}",
            f"{r['r2_in']:.2f}",
            "n/a" if np.isnan(r['r2_adj']) else f"{r['r2_adj']:+.2f}",
            f"{r['te_bp_day']:.0f}",
            f"{r['tgt_vol_ann'] * 100:.0f}%",
            r['best_single'].split(' ')[0] if r['best_single'] else '—',
            "n/a" if np.isnan(r['best_single_r2']) else f"{r['best_single_r2']:.2f}",
        ])
    _print_table(['Window', 'Obs', 'Legs', 'R2', 'Adj R2', 'TE bp/d',
                  'Tgt vol', 'Best single', 'its R2'], srows, indent='  ')
    print("\n  R2      fitted and scored on the SAME rows. Rises mechanically")
    print("          with every leg added and with every row removed, so it is")
    print("          NOT comparable across these windows.")
    print("  Adj R2  charges for the parameters. This is the comparable column,")
    print("          and it can go negative — meaning the basket explains less")
    print("          than the window mean once its legs are paid for.")
    print("  TE      residual sd at ddof = k+1, so the fitted legs do not")
    print("          flatter it. Still an in-sample floor on live tracking error.")
    print("  Best single = most correlated single instrument, fitted the same")
    print("          way. If the basket's Adj R2 does not clear it, the basket")
    print("          is not earning its extra legs.")

    # ── [3] STABILITY — the reason for running three windows ─────────────────
    print("\n" + "=" * L)
    print("[3] STABILITY ACROSS WINDOWS   ← the load-bearing section")
    print("=" * L)
    allw = pd.DataFrame({r['label']: r['weights'] for r in runs}).fillna(0.0)
    allw = allw.reindex(allw.abs().max(axis=1).sort_values(ascending=False).index)
    n_win = len(runs)
    strows = []
    for tk, row in allw.iterrows():
        nz = row[row != 0]
        signs = {np.sign(v) for v in nz}
        strows.append([tk.split(' ')[0], f"{len(nz)}/{n_win}"]
                      + [("—" if v == 0 else f"{v * 100:+.0f}") for v in row]
                      + [f"{nz.mean() * 100:+.0f}",
                         "yes" if len(signs) == 1 else "FLIPS"])
    _print_table(['Ticker', 'In'] + [r['label'] for r in runs]
                 + ['Mean', 'Same side'], strows, indent='  ')

    core = [tk for tk, row in allw.iterrows()
            if (row != 0).sum() == n_win
            and len({np.sign(v) for v in row if v != 0}) == 1]
    churn = [tk for tk, row in allw.iterrows() if (row != 0).sum() == 1]
    print(f"\n  Persistent core (in all {n_win} windows, same side): "
          + (", ".join(t.split(' ')[0] for t in core) if core else "NONE"))
    if churn:
        print(f"  Appears in one window only: "
              f"{', '.join(t.split(' ')[0] for t in churn)}")
    if not core:
        print("  → No name survives all three start dates. The basket is being")
        print("    driven by which days happen to be in the sample. With no")
        print("    out-of-sample test in this build, section [3] is the ONLY")
        print("    check standing between you and a curve-fit — heed it.")
    else:
        worst = float((allw.loc[core].std(axis=1) * 100).max())
        print(f"  → Core weight dispersion across windows: max {worst:.0f} "
              f"per $100"
              + ("  (tight — the ratio is holding)" if worst < 15 else
                 "  (wide — the NAMES persist but the RATIO does not)"))

    # ── [3b] pin the persistent core in every window ─────────────────────────
    if core:
        print("\n  [3b] PERSISTENT CORE PINNED IN EVERY WINDOW")
        crows = []
        for r in runs:
            rr, tcol = r['returns'], r['target_col']
            usable = [c for c in core if c in rr.columns]
            if not usable:
                continue
            try:
                reg_c, r2c, _ = _fit_basket(rr, tcol, usable)
            except Exception:
                continue
            wc = pd.Series(reg_c.coef_, index=usable)
            crows.append([
                r['label'],
                " / ".join(f"{t.split(' ')[0]} {w * 100:+.0f}"
                           for t, w in wc.items()),
                f"{float(r2c):.2f}",
                (lambda a: "n/a" if np.isnan(a) else f"{a:+.2f}")(
                    _adj_r2(float(r2c), r['n_obs'], len(usable))),
                "n/a" if np.isnan(r['r2_adj']) else f"{r['r2_adj']:+.2f}"])
        if crows:
            _print_table(['Window', 'Core recipe per $100', 'R2',
                          'core Adj R2', 'free-pick Adj R2'], crows, indent='  ')
            print("  The core carries fewer legs, so if its Adj R2 is close to")
            print("  the free pick's, the extra legs were bought with degrees of")
            print("  freedom rather than explanatory power.")

    summary = pd.DataFrame([{
        'window': r['label'], 'obs': r['n_obs'], 'legs': len(r['basket']),
        'r2_in': r['r2_in'], 'r2_adj': r['r2_adj'],
        'te_bp_day': r['te_bp_day'], 'gross': r['gross'],
        'best_single': r['best_single'], 'best_single_r2': r['best_single_r2'],
    } for r in runs]).set_index('window')

    # ── [4] scope ────────────────────────────────────────────────────────────
    print("\n" + "=" * L)
    print("[4] SCOPE OF THESE NUMBERS")
    print("=" * L)
    nmax = max(r['n_obs'] for r in runs)
    print(f"  Largest window here is {nmax} observations, fitted and scored on")
    print(f"  itself. find_best_hedge() wants 378+ rows and reports a NESTED")
    print(f"  out-of-sample R2 over three unseen 42-day windows. Nothing on")
    print(f"  this page is that number, and no number here forecasts anything.")
    print()
    print("  This answers: how much of the target's realized variance over")
    print("  these dates moved with these names — an attribution question.")
    print()
    print("  It does not answer: what will hedge the position tomorrow. For")
    print("  that, run find_best_hedge() on the 3-year download and use these")
    print("  windows to ask whether its basket still appears in section [3].")
    print("  A long-run basket that survives all three July start dates is a")
    print("  much stronger result than any single in-sample R2 above.")
    if errs:
        print(f"\n  Windows that failed: {', '.join(l for l, _ in errs)}")
    return {'runs': runs, 'stability': allw, 'summary': summary,
            'core': core, 'errors': errs}
