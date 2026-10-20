"""Regression tests for residual-risk estimation and reproducible review inputs."""
import contextlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
from sklearn.covariance import ledoit_wolf_shrinkage
from test_pca_research import E, fixture, run


def omitted_direction(n=19, seed=0, future=1000):
    rng = np.random.default_rng(seed)
    m, s, h, g = rng.normal(0, .01, (4, n + future))
    peers = ['P%d TT Equity' % i for i in range(26)]
    target = 'T TT Equity'
    values = {target: .4*m + .3*s + .8*h + rng.normal(0, .004, n+future),
              '0050 TT Equity': m, '0055 TT Equity': .5*m+s}
    for i, name in enumerate(peers):
        values[name] = .5*m + .2*s + (h if i < 3 else .9*g) + rng.normal(0, .006, n+future)
    frame = pd.DataFrame(values)
    return frame.iloc[:n], frame.iloc[n:], target, peers


class ResidualCovarianceTests(unittest.TestCase):
    def model(self, frame, target, peers, **kwargs):
        return E['_common_risk_model'](frame, target, peers,
            ['0050 TT Equity', '0055 TT Equity'], **kwargs)

    def test_projection_is_orthogonal_and_preserves_observed_variances(self):
        for n in (19, 42, 63):
            frame, _, target, peers = omitted_direction(n)
            model = self.model(frame, target, peers)
            x = frame.to_numpy() - frame.to_numpy().mean(0)
            residual = x - model['factors'] @ model['loadings']
            np.testing.assert_allclose(model['factors'].T @ residual, 0, atol=1e-12)
            np.testing.assert_allclose(np.diag(model['covariance']), x.var(0), rtol=1e-9, atol=1e-16)
            self.assertGreater(np.linalg.eigvalsh(model['covariance']).min(), 0)
            self.assertGreater(np.linalg.norm(model['residual_covariance'] - np.diag(model['specific_variance'])), 0)

    def test_shrinkage_matches_independent_standardized_estimator(self):
        frame, _, target, peers = omitted_direction()
        model = self.model(frame, target, peers, covariance_names=[target]+peers)
        x = frame.to_numpy()-frame.to_numpy().mean(0)
        residual = x-model['factors']@model['loadings']
        indices = [model['columns'].index(c) for c in model['residual_calibration_names']]
        z = residual[:, indices] / np.sqrt(np.mean(residual[:, indices]**2, axis=0))
        expected = ledoit_wolf_shrinkage(z, assume_centered=True)
        self.assertAlmostEqual(model['residual_shrinkage'], expected)
        self.assertGreaterEqual(expected, 0); self.assertLessEqual(expected, 1)

    def test_additional_reference_columns_cannot_change_calibrated_hedge(self):
        frame, _, target, peers = omitted_direction()
        a = self.model(frame, target, peers, covariance_names=[target]+peers)
        frame['REFERENCE ONLY'] = frame[peers[0]]*9
        b = self.model(frame, target, peers, covariance_names=[target]+peers)
        np.testing.assert_allclose(a['covariance'], b['covariance'][:-1, :-1], rtol=1e-10, atol=1e-15)
        self.assertEqual(a['residual_shrinkage'], b['residual_shrinkage'])

    def test_change_of_units_and_column_order_preserves_covariance(self):
        frame, _, target, peers = omitted_direction(42)
        a = self.model(frame, target, peers)
        changed = frame.copy(); changed[peers[0]] *= 50
        order = list(reversed(frame.columns)); changed = changed[order]
        b = self.model(changed, target, list(reversed(peers)))
        scale = np.ones(len(frame.columns)); scale[frame.columns.get_loc(peers[0])] = 50
        indices = [order.index(c) for c in frame.columns]
        np.testing.assert_allclose(b['covariance'][np.ix_(indices, indices)],
            a['covariance']*scale[:, None]*scale[None, :], rtol=1e-8, atol=1e-13)

    def test_omitted_relationship_improves_on_separate_simulated_rows(self):
        # Fixed basket isolates covariance estimation from subset-search bias.
        # The test is a mechanism regression, not evidence about live 2889.
        for n in (19, 42, 63):
            differences = []
            for seed in range(12):
                tr, te, target, peers = omitted_direction(n, seed)
                model = self.model(tr, target, peers)
                f = model['factors']; x = tr.to_numpy()-tr.to_numpy().mean(0)
                old_b = np.linalg.solve(f.T@f+2*np.eye(f.shape[1]), f.T@x)
                old_res = x-f@old_b
                legacy = dict(model, covariance=old_b.T@(f.T@f/n)@old_b +
                    np.diag(np.maximum(np.mean(old_res**2, axis=0), .01*x.var(0))))
                old_fit, _, _ = E['_fit_common_risk'](tr, target, peers[:3], legacy, 2, 1)
                new_fit, _, _ = E['_fit_common_risk'](tr, target, peers[:3], model, 2, 1)
                old_spread = te[target]-te[peers[:3]]@old_fit.coef_
                new_spread = te[target]-te[peers[:3]]@new_fit.coef_
                differences.append((old_spread.var()-new_spread.var())/te[target].var())
            self.assertGreater(np.mean(differences), .03)

    def test_independent_target_does_not_get_artificial_high_fit(self):
        scores = []
        for seed in range(24):
            tr, _, target, peers = omitted_direction(19, seed)
            rng = np.random.default_rng(seed+2000)
            tr = tr.copy(); tr[target] = rng.normal(0, .01, len(tr))
            model = self.model(tr, target, peers)
            _, score, _ = E['_fit_common_risk'](tr, target, peers[:3], model, 2, 1)
            scores.append(score)
        self.assertLess(np.mean(scores), .25)

    def test_report_uses_the_covariance_model_that_fitted_weights(self):
        result = run(sample_window='1m')
        model = result['current_fit']['common_model']
        audit = result['common_exposures']
        self.assertEqual(audit['residual_shrinkage'], model['residual_shrinkage'])
        self.assertEqual([row[0] for row in audit['rows']], model['labels'])
        self.assertNotIn('Same-name capped fit R²', result['report_text'])
        self.assertNotIn('Same-name uncapped OLS R²', result['report_text'])
        self.assertIn('BASKET METHOD', result['report_text'])
        self.assertTrue(np.isfinite(result['fit_diagnostics']['same_basket_capped_ols_r2']))


class DiagnosticExportTests(unittest.TestCase):
    def test_export_reload_reproduces_all_three_windows_without_bloomberg(self):
        data = fixture(n=150)
        data['mktcap_hist'] = pd.DataFrame(5000., index=data['prices'].index, columns=data['prices'].columns)
        data['mktcap_usd_mm'] = {c:5000. for c in data['prices']}
        data['pit_members'] = {data['prices'].index[0]:set(data['prices'].columns)}
        data['execution_snapshot'] = {data['target']:{'CRNCY':'TWD','PX_BID':np.float64(12.),'missing':np.nan}}
        result = run(data, sample_window='3m')
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            path = E['export_hedge_diagnostics'](result, folder)
            bundle = E['load_hedge_diagnostics'](path)
            pd.testing.assert_frame_equal(bundle['data']['prices'], data['prices'], check_freq=False)
            pd.testing.assert_frame_equal(bundle['data']['mktcap_hist'], data['mktcap_hist'], check_freq=False)
            self.assertEqual(bundle['data']['pit_members'], data['pit_members'])
            self.assertNotIn('session', bundle['run_options'])
            for window in ('1m','2m','3m'):
                opts = dict(bundle['run_options'], sample_window=window)
                with patch.dict(E['find_best_hedge'].__globals__, get_session=lambda: self.fail('Unexpected Bloomberg call')):
                    replay = E['find_best_hedge'](data=bundle['data'], **opts)
                original = run(data, sample_window=window)
                pd.testing.assert_series_equal(replay['weights'], original['weights'])
                self.assertAlmostEqual(replay['in_sample_r2'], original['in_sample_r2'])
            with zipfile.ZipFile(path) as archive:
                self.assertIn('fitted_returns.csv', archive.namelist())
                self.assertIn('report.txt', archive.namelist())
                self.assertFalse(any(name.endswith(('.pkl','.py')) for name in archive.namelist()))

    def test_input_snapshot_survives_later_data_mutations(self):
        data = fixture(n=100)
        before = data['prices'].copy()
        result = run(data, sample_window='1m')
        data['prices'].iloc[:, 0] *= 3
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            bundle = E['load_hedge_diagnostics'](E['export_hedge_diagnostics'](result, folder))
        pd.testing.assert_frame_equal(bundle['data']['prices'], before, check_freq=False)

    def test_corrupt_inputs_and_unknown_data_types_are_rejected(self):
        with self.assertRaises(ValueError):
            E['_diagnostic_unpack']({'type':'execute', 'value':'anything'})
        result = run(sample_window='1m')
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            path = E['export_hedge_diagnostics'](result, folder)
            corrupt = Path(folder)/'corrupt.zip'
            with zipfile.ZipFile(path) as original, zipfile.ZipFile(corrupt, 'w') as changed:
                for name in original.namelist():
                    raw = original.read(name)
                    changed.writestr(name, raw+b' ' if name=='inputs.json' else raw)
            with self.assertRaisesRegex(ValueError, 'integrity'):
                E['load_hedge_diagnostics'](corrupt)

    def test_ui_has_diagnostic_export_button(self):
        with contextlib.redirect_stdout(io.StringIO()):
            ui = E['hedge_ui'](fixture(n=100))
        found = []
        def visit(widget):
            if getattr(widget, 'description', None) == 'Export diagnostics': found.append(widget)
            for child in getattr(widget, 'children', ()): visit(child)
        visit(ui['widgets']['form'])
        self.assertEqual(len(found), 1)


if __name__ == '__main__':
    unittest.main()
