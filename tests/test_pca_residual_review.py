"""Chronological residual calibration and exact descriptive error attribution."""
import contextlib
import io
import tempfile
import unittest
import zipfile
import numpy as np
import pandas as pd
from test_pca_research import E, fixture, run
from test_pca_residual_covariance import omitted_direction


class ResidualPolicyTests(unittest.TestCase):
    def test_stable_improvement_can_reduce_shrinkage(self):
        folds=[{'loss':{'estimated':a,'half':b,'none':c}} for a,b,c in
               [(1.,.6,.9),(.9,.5,1.2),(1.1,.65,1.3)]]
        a=E['_choose_residual_policy'](folds)
        self.assertEqual(a['selected_policy'],'half')
        self.assertFalse(a['independent_performance_claim'])

    def test_one_good_block_cannot_force_switch(self):
        folds=[{'loss':{'estimated':1.,'half':b,'none':2.}} for b in [0.,1.05,1.05]]
        self.assertEqual(E['_choose_residual_policy'](folds)['selected_policy'],'estimated')

    def test_incomplete_comparison_cannot_hide_a_failure(self):
        folds=[{'loss':{'estimated':1.,'half':.2,'none':.4}},
               {'loss':{'estimated':1.,'half':.2,'none':.4}},
               {'loss':{'estimated':1.,'half':.2,'none':np.nan}}]
        a=E['_choose_residual_policy'](folds)
        self.assertEqual(a['selected_policy'],'estimated')
        self.assertEqual(a['comparable_folds'],2)

    def test_small_gain_below_stability_margin_keeps_baseline(self):
        folds=[{'loss':{'estimated':1.,'half':.99,'none':1.}} for _ in range(3)]
        self.assertEqual(E['_choose_residual_policy'](folds)['selected_policy'],'estimated')

    def test_risk_ratio_pools_sums_of_squares_instead_of_flat_block_ratios(self):
        folds=[{'loss':{'estimated':v,'half':v/2,'none':v},
                'target_variance':y,'test_rows':n} for v,y,n in
               [(.1,.01,5),(.5,1.,6),(.4,.5,7)]]
        a=E['_choose_residual_policy'](folds)
        expected=(4*.1+5*.5+6*.4)/(4*.01+5*1.+6*.5)
        self.assertAlmostEqual(a['candidates'][0]['mean_loss'],expected)

    def test_variants_preserve_units_variances_and_psd(self):
        frame,_,target,peers=omitted_direction(60)
        m=E['_common_risk_model'](frame,target,peers,['0050 TT Equity','0055 TT Equity'])
        baseline=m['covariance'].copy()
        for policy in ('estimated','half','none'):
            v=E['_residual_model_variant'](m,frame,policy)
            np.testing.assert_allclose(np.diag(v['covariance']),np.diag(baseline),atol=1e-15)
            self.assertGreater(np.linalg.eigvalsh(v['covariance']).min(),-1e-12)
        empirical=frame.cov(ddof=0).values
        np.testing.assert_allclose(E['_residual_model_variant'](m,frame,'none')['covariance'],
                                   empirical,rtol=1e-7,atol=1e-12)
        np.testing.assert_array_equal(m['covariance'],baseline)

    def test_short_window_falls_back_without_changing_weights(self):
        a=run(sample_window='1m',residual_policy='estimated')
        b=run(sample_window='1m',residual_policy='validated')
        pd.testing.assert_series_equal(a['weights'],b['weights'])
        self.assertEqual(b['residual_calibration']['status'],'insufficient_history')

    def test_inner_blocks_are_chronological_and_respect_caps(self):
        r=run(sample_window='3m',residual_policy='validated',max_gross=1.,max_leg=.6)
        audit=r['residual_calibration']
        self.assertEqual(len(audit['folds']),3)
        prior_end=None
        for fold in audit['folds']:
            self.assertLess(fold['train_end'],fold['test_start'])
            if prior_end is not None:self.assertLess(prior_end,fold['test_start'])
            prior_end=fold['test_end']
            for recipe in fold['recipes'].values():
                self.assertLessEqual(sum(abs(x) for x in recipe['weights']),1.0000001)
                self.assertLessEqual(max(abs(x) for x in recipe['weights']),.6000001)
                self.assertTrue(set(recipe['basket']) <= set(fold['eligible_tickers']))
        self.assertEqual(r['params']['residual_policy'],'validated')

    def test_held_out_changes_do_not_change_earlier_calibration(self):
        data=fixture();a=run(data,sample_window='3m')
        changed=fixture();changed['prices'].iloc[-12:,0]*=np.linspace(1.1,1.8,12)
        b=run(changed,sample_window='3m')
        end=a['validation_fit_returns'].index[-1]
        def before(result):
            return [(x['end'],x.get('residual_calibration')) for x in result['joint_search_audit']
                    if x['end']<=end]
        self.assertEqual(before(a),before(b))
        pd.testing.assert_series_equal(a['validation_weights'],b['validation_weights'])

    def test_invalid_policy_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'residual_policy'):
            run(residual_policy='highest_in_sample')

    def test_two_day_returns_have_a_gap_and_nonoverlapping_validation_rows(self):
        r=run(sample_window='3m',async_adjust=True)
        index=r['returns'].index
        for fold in r['residual_calibration']['folds']:
            train=index.get_loc(fold['train_end']);start=index.get_loc(fold['test_start'])
            self.assertGreaterEqual(start-train,2)
            stop=index.get_loc(fold['test_end'])+1
            self.assertEqual(fold['test_rows'],len(index[start:stop:2]))


class HedgeErrorAttributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=run(sample_window='3m')

    def test_daily_components_and_variance_shares_reconcile(self):
        a=self.result['hedge_error_attribution'];d=a['daily']
        self.assertEqual(a['status'],'ok')
        components=['common_factor_gap','target_outside_factors','hedge_outside_factors']
        np.testing.assert_allclose(d[components].sum(axis=1),d['centered_spread'],atol=1e-12)
        self.assertAlmostEqual(sum(a['variance_contributions'].values()),1.)
        self.assertAlmostEqual(d['error_share'].sum(),1.)
        self.assertFalse(a['alpha_identified']);self.assertFalse(a['causal_claim'])
        self.assertAlmostEqual(a['top_ten_error_share'],d['error_share'].nlargest(10).sum())
        np.testing.assert_allclose(d['target_return']-d['hedge_return']-
            (d['target_return']-d['hedge_return']).mean(),d['centered_spread'],atol=1e-12)

    def test_common_mismatch_share_matches_direct_variance(self):
        a=self.result['hedge_error_attribution'];d=a['daily']
        ratio=d['common_factor_gap'].var()/d['centered_spread'].var()
        self.assertAlmostEqual(ratio,a['variance_contributions']['common_factor_gap'])

    def test_misaligned_factor_dates_fail_explicitly(self):
        r=self.result;frame=r['returns'].copy();frame.index=frame.index+pd.Timedelta(days=1)
        a=E['_hedge_error_attribution'](frame,'2889 TT Equity',r['weights'],r['current_fit']['common_model'])
        self.assertEqual(a['status'],'unavailable')
        self.assertIn('dates',a['reason'])

    def test_event_context_does_not_change_the_fit(self):
        data=fixture();date=self.result['hedge_error_attribution']['rows'][0]['date']
        data['event_evidence']=[{'ticker':'2889 TT Equity','date':str(date.date()),
            'summary':'Illustrative announcement, not causal evidence',
            'source_url':'https://example.com/issuer-announcement'}]
        r=run(data,sample_window='3m')
        pd.testing.assert_series_equal(r['weights'],self.result['weights'])
        pd.testing.assert_series_equal(r['validation_weights'],self.result['validation_weights'])
        row=r['hedge_error_attribution']['rows'][0]
        self.assertEqual(len(row['event_evidence']),1)
        self.assertIn('causality unverified',row['event_status'])

    def test_report_and_export_contain_attribution_without_lookahead_claims(self):
        r=self.result
        self.assertIn('residual risk review',r['report_text'].lower())
        self.assertIn('tuning results, not another unseen test',' '.join(r['report_text'].split()))
        self.assertIn('not identified alpha',r['report_text'])
        with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stdout(io.StringIO()):
            path=E['export_hedge_diagnostics'](r,folder)
            with zipfile.ZipFile(path) as z:
                self.assertIn('hedge_error_attribution.csv',z.namelist())
            bundle=E['load_hedge_diagnostics'](path)
            self.assertEqual(bundle['run_options']['residual_policy'],'validated')
            self.assertEqual(bundle['result']['hedge_error_attribution']['status'],'ok')


if __name__=='__main__':
    unittest.main()
