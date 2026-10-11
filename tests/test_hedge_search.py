"""Offline regression checks: no Bloomberg connection or market-data download."""
import ast
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest

os.environ.setdefault('MPLBACKEND', 'Agg')
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'PCA_fixed.py'
if not SCRIPT.exists():
    SCRIPT = ROOT / 'pca_hedge_v103_full.py'
engine = runpy.run_path(str(SCRIPT), init_globals={'HEDGE_UI_AUTOSTART': False})

def data(n=420, seed=11):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range('2023-01-02', periods=n)
    market, sector = rng.normal(0, .01, (2, n))
    target = .75 * market + .25 * sector + rng.normal(0, .001, n)
    returns = np.column_stack([
        target, target + rng.normal(0, .002, n),
        .8 * market + rng.normal(0, .003, n),
        .6 * market + .3 * sector + rng.normal(0, .004, n),
        sector + rng.normal(0, .004, n), rng.normal(0, .01, n)])
    columns = ['2889 TT Equity', '2910 TT Equity', '0050 TT Equity',
               '006208 TT Equity', '2911 TT Equity', '2912 TT Equity']
    return {'target': columns[0],
            'prices': pd.DataFrame(100 * np.exp(np.cumsum(returns, axis=0)),
                                   index=dates, columns=columns),
            'mktcap_usd_mm': {}, 'price_observations': 'ACTIVE_DAYS_ONLY'}

OPTIONS = dict(lookback_options=(126,), pc_options=(2,),
               basket_size_options=(1, 2, 3), cv_test_window=21, cv_n_folds=3,
               outer_window=21, outer_folds=2, min_mktcap_usd_mm=0,
               restrict_to_target_tz=True, async_adjust=False,
               rolling_oos=False, boot_n=0, show_plots=False)

def run(dataset=None, **options):
    with contextlib.redirect_stdout(io.StringIO()):
        return engine['find_best_hedge']('2889 TT Equity', data=dataset or data(),
                                        **dict(OPTIONS, **options))

class HedgeSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = data()
        cls.result = run(cls.dataset)
        cls.report = engine['transcript_text']()

    def tearDown(self):
        plt.close('all')

    def test_every_eligible_single_competes_with_basket_methods(self):
        specs = set(self.result['cv_detail']['pc_spec'])
        expected = {'single:' + c for c in self.dataset['prices'].columns[1:]}
        self.assertTrue(expected <= specs)
        self.assertTrue({'correlation', 'forward', '2'} <= specs)
        self.assertEqual(self.result['search']['single_instruments_scored'], 5)

    def test_stock_etf_and_basket_have_same_unseen_periods(self):
        for family in ('basket', 'single', 'single_stock', 'single_etf'):
            item = self.result['hedge_alternatives'][family]
            self.assertEqual(item['n_unseen_windows'], 2)
            self.assertEqual(item['trade_risk']['n_observations'], 42)
            self.assertTrue(np.isfinite(item['unseen_r2']))
        stock = self.result['best_single_stock_hedge']['weights']
        etf = self.result['best_single_etf_hedge']['weights']
        self.assertEqual(len(stock), 1)
        self.assertFalse(engine['_is_etf'](stock.index[0]))
        self.assertEqual(len(etf), 1)
        self.assertTrue(engine['_is_etf'](etf.index[0]))
        self.assertGreaterEqual(len(self.result['best_basket_hedge']['weights']), 2)

    def test_comparison_is_in_existing_report(self):
        text = self.report
        self.assertIn('BEST BASKET AND SINGLE-INSTRUMENT HEDGES', text)
        self.assertIn('Best single', text)
        self.assertIn('stock', text)
        self.assertIn('ETF', text)

    def test_forward_selection_can_find_complementary_exposures(self):
        rng = np.random.default_rng(31)
        common, factor = rng.normal(0, 1, (2, 3000))
        frame = pd.DataFrame({'y': factor, 'a': 5*common + factor,
                              'b': 5*common - factor, 'noise': rng.normal(0, 1, 3000)})
        chosen = engine['_forward_order'](frame, 'y', ['a', 'b', 'noise'], max_size=2)
        self.assertEqual(set(chosen), {'a', 'b'})
        _, raw, _ = engine['_fit_basket'](frame, 'y', chosen)
        self.assertGreater(raw, .99)

    def test_failed_tracking_test_cannot_return_trade_weights(self):
        sample = data()
        prices = sample['prices']
        returns = np.log(prices / prices.shift()).fillna(0)
        returns.iloc[-42:, 0] *= -1
        sample['prices'] = 100 * np.exp(returns.cumsum())
        result = run(sample)
        self.assertLess(result['nested_pooled_r2'], 0)
        self.assertFalse(result['trade_eligible'])
        self.assertTrue(result['trade_weights'].empty)
        self.assertFalse(result['best_single_hedge']['qualified'])

    def test_gross_cap_is_never_silently_ignored(self):
        with self.assertRaisesRegex(RuntimeError, 'All CV folds failed'):
            run(max_gross=1e-12)

    def test_nested_score_and_risk_equal_the_actual_unseen_errors(self):
        unseen = self.result['nested_unseen_returns']
        self.assertTrue(unseen.index.is_monotonic_increasing)
        self.assertTrue(unseen.index.is_unique)
        y, residual, spread = (unseen[c].to_numpy() for c in unseen.columns)
        expected = 1 - np.sum(residual**2) / np.sum((y-y.mean())**2)
        self.assertAlmostEqual(self.result['nested_pooled_r2'], expected)
        risk = self.result['trade_risk']
        self.assertAlmostEqual(risk['vol_reduction'], 1 - spread.std()/y.std())
        self.assertAlmostEqual(risk['variance_reduction'], 1 - spread.var()/y.var())

    def test_bootstrap_interval_resamples_its_own_point_statistic(self):
        result = run(boot_n=150)
        interval = result['bootstrap_ci']
        self.assertEqual(interval['source'], 'nested unseen selection procedure')
        self.assertTrue(interval['conditional_on_observed_fits'])
        self.assertAlmostEqual(interval['r2_point'], result['nested_pooled_r2'])
        selected = result['selected_config_bootstrap_ci']
        self.assertAlmostEqual(selected['r2_point'], result['selected_unseen_pooled_r2'])
        self.assertTrue(np.isfinite([interval['r2_lo'], interval['r2_hi']]).all())

    def test_future_test_returns_do_not_change_prior_selection_or_predictions(self):
        changed = data()
        returns = np.log(changed['prices'] / changed['prices'].shift()).fillna(0)
        returns.iloc[-21:, 0] = -.5 * returns.iloc[-21:, 0] + .015
        changed['prices'] = 100 * np.exp(returns.cumsum())
        altered = run(changed)
        columns = ['window', 'lookback', 'pc_spec', 'basket_size']
        pd.testing.assert_frame_equal(self.result['nested_validation'][columns],
                                      altered['nested_validation'][columns])
        first = self.result['nested_unseen_returns']
        second = altered['nested_unseen_returns']
        np.testing.assert_allclose(first['target'] - first['regression_residual'],
                                   second['target'] - second['regression_residual'], atol=1e-12)
        self.assertNotAlmostEqual(self.result['nested_pooled_r2'], altered['nested_pooled_r2'])

    def test_later_missing_quotes_do_not_remove_an_earlier_eligible_stock(self):
        baseline = data()
        baseline['prices'].iloc[:60, 1] = np.nan
        changed = {**baseline, 'prices': baseline['prices'].copy()}
        changed['prices'].iloc[-21:, 1] = np.nan
        first, second = run(baseline), run(changed)
        oldest = first['nested_validation'].iloc[-1]
        changed_oldest = second['nested_validation'].iloc[-1]
        for key in ('lookback', 'pc_spec', 'basket_size'):
            self.assertEqual(oldest[key], changed_oldest[key])
        self.assertAlmostEqual(oldest['r2_oos'], changed_oldest['r2_oos'])
        self.assertIn('2910 TT Equity', second['prices'].columns)

    def test_predictive_r2_is_not_given_a_fisher_correlation_interval(self):
        detail = self.result['outer_window_detail'].copy()
        detail['r2'] = [-.1, .7]
        stats = engine['_window_dispersion_stats'](detail, .5, 42)
        self.assertIsNone(stats['band'])
        self.assertEqual(stats['flags'], ['negative', ''])

    def test_singles_are_searched_even_with_basket_only_size_settings(self):
        result = run(basket_size_options=(2, 3))
        self.assertEqual(result['search']['single_instruments_scored'], 5)
        self.assertIsNotNone(result['best_single_hedge'])

    def test_quick_rehedge_preserves_a_single_configuration(self):
        result = run(basket_size_options=(1,))
        self.assertTrue(result['params']['pc_spec'].startswith('single:'))
        with contextlib.redirect_stdout(io.StringIO()):
            quick = engine['quick_rehedge']('2889 TT Equity', self.dataset, result,
                                           show_plots=False, rolling_oos=False)
        self.assertEqual(result['params']['pc_spec'], quick['params']['pc_spec'])
        self.assertEqual(result['weights'].index.tolist(), quick['weights'].index.tolist())
        self.assertFalse(quick['params']['broad_search'])

    def test_monthly_candidates_are_indicative_and_include_both_forms(self):
        result = run(sample_window='1m')
        self.assertEqual(result['validation_mode'], 'IN-SAMPLE')
        for family in ('basket', 'single_stock', 'single_etf'):
            item = result['hedge_alternatives'][family]
            self.assertIn('INDICATIVE', item['status'])
            self.assertTrue(np.isnan(item['unseen_r2']))
            self.assertFalse(item['qualified'])

    def test_short_history_with_many_names_caps_requested_pca_dimensions(self):
        sample = data()
        rng = np.random.default_rng(123)
        for i in range(30):
            sample['prices'][f'{3100+i} TT Equity'] = 100 * np.exp(np.cumsum(rng.normal(0, .01, 420)))
        result = run(sample, sample_window='1m', pc_options=(30,))
        self.assertEqual(result['validation_mode'], 'IN-SAMPLE')
        self.assertTrue(np.isfinite(result['in_sample_r2']))
        self.assertIsNotNone(result['best_basket_hedge'])

    def test_reported_flat_prices_are_retained(self):
        frame = pd.DataFrame({'a': [100.] * 20})
        pd.testing.assert_frame_equal(engine['_mask_stale'](frame, 7, frame), frame)

    def test_unsupported_matplotlib_setting_is_removed_and_charts_draw(self):
        rc = engine['_supported_plot_style']({'font.size': 9, 'axes.titlecolor': 'navy'}, {'font.size': 10})
        self.assertNotIn('axes.titlecolor', rc)
        with plt.rc_context(rc):
            figure, axis = plt.subplots()
            axis.set_title('Hedge comparison', color='navy')
            figure.canvas.draw()

    def test_cache_roundtrip_and_local_export_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            with contextlib.redirect_stdout(io.StringIO()):
                path = engine['save_hedge_data'](data(), cache_dir=folder)
                restored = engine['load_hedge_data'](path)
            pd.testing.assert_frame_equal(restored['prices'], data()['prices'])
            export_folder, warning = engine['_export_folder'](str(Path(folder) / 'reports'))
            self.assertTrue(Path(export_folder).is_dir())
            self.assertIsNone(warning)
        self.assertNotIn('G:', engine['HEDGE_EXPORT_DIR'])

    def test_missing_bloomberg_api_gives_actionable_download_error(self):
        namespace = engine['bbg_connect'].__globals__
        previous = namespace['blpapi']
        try:
            namespace['blpapi'] = None
            with self.assertRaisesRegex(RuntimeError, 'Install the Bloomberg Python API'):
                engine['bbg_connect']()
        finally:
            namespace['blpapi'] = previous

    def test_existing_form_and_word_export_work_without_bloomberg(self):
        from docx import Document
        from IPython.utils.capture import capture_output
        with capture_output():
            state = engine['hedge_ui'](data=self.dataset)
        self.assertIs(state['data'], self.dataset)
        with tempfile.TemporaryDirectory() as folder:
            with contextlib.redirect_stdout(io.StringIO()):
                path = engine['export_result'](self.result, report_text='Offline synthetic validation.', out_dir=folder)
            self.assertEqual(Path(path).suffix, '.docx')
            document = Document(path)
            text = '\n'.join(cell.text for table in document.tables for row in table.rows for cell in row.cells)
            self.assertIn('Basket', text)
            self.assertIn('Single stock', text)
            self.assertIn('Single ETF', text)
            alternatives = pd.read_csv(Path(path).with_suffix('').as_posix() + '_alternatives.csv')
            self.assertEqual(set(alternatives['candidate_type']), {'basket', 'single_stock', 'single_etf'})

    def test_history_comparison_contains_both_forms_for_each_window(self):
        with contextlib.redirect_stdout(io.StringIO()):
            comparison = engine['compare_history_windows']('2889 TT Equity', self.dataset,
                windows=('1y', '6m', '3m', '1m'), **OPTIONS)
        table = comparison['alternatives_summary']
        self.assertEqual(set(table['period']), {'1y', '6m', '3m', '1m'})
        for period, rows in table.groupby('period'):
            self.assertEqual(set(rows['candidate_type']), {'basket', 'single_stock', 'single_etf'})
        rejected = table[~table['qualified'] & ~table['status'].str.contains('INDICATIVE')]
        self.assertTrue(rejected['weights_per_100'].eq('').all())

    def test_notebook_engine_matches_script_and_every_cell_parses(self):
        notebook_path = ROOT / 'PCA_fixed.ipynb'
        if not notebook_path.exists():
            notebook_path = ROOT / 'pca_hedge_v103_full.ipynb'
        notebook = json.loads(notebook_path.read_text(encoding='utf-8'))
        self.assertEqual(''.join(notebook['cells'][1]['source']), SCRIPT.read_text(encoding='utf-8'))
        for cell in notebook['cells']:
            if cell['cell_type'] == 'code':
                ast.parse(''.join(cell['source']))
                self.assertFalse(cell.get('outputs'))

if __name__ == '__main__':
    unittest.main(verbosity=2)
