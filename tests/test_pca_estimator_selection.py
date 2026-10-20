"""Matched estimator selection, frozen tests and genuine Ridge dispatch.

Synthetic relationships verify mechanism, not performance for any traded stock.
"""
import contextlib
import copy
import io
import tempfile
import unittest
import numpy as np
import pandas as pd
from test_pca_research import E, fixture, run


def sparse_relationship(seed=0):
    rng=np.random.default_rng(seed);n=180
    market=rng.normal(0,.01,n);sector=rng.normal(0,.01,n)
    peers=['P%d TT Equity'%i for i in range(14)]
    x=.4*market[:,None]+.2*sector[:,None]+rng.normal(0,.01,(n,len(peers)))
    y=x[:,:3]@np.array([.8,-.5,.7])+rng.normal(0,.002,n)
    names=['2889 TT Equity','0050 TT Equity','0055 TT Equity']+peers
    values=np.column_stack([y,market,market+sector,x])
    data=fixture()
    data['prices']=pd.DataFrame(100*np.exp(values.cumsum(0)),
        index=pd.bdate_range('2025-01-01',periods=n),columns=names)
    data['peer_tickers_by_target']={data['target']:peers}
    return data


class EstimatorSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=sparse_relationship()
        cls.result=run(cls.data,sample_window='3m',report='full')

    def test_tracking_can_become_primary_with_real_fitted_weights(self):
        r=self.result
        self.assertEqual(r['model_selection']['selected_policy'],'tracking')
        self.assertEqual(r['selected_estimator'],'tracking')
        self.assertEqual(r['residual_calibration']['status'],'not_used_by_tracking_estimator')
        frame=r['returns'];basket=list(r['weights'].index)
        fit,r2,_=E['_fit_basket'](frame,'2889 TT Equity',basket,2,1)
        np.testing.assert_allclose(r['weights'],fit.coef_,atol=1e-10)
        self.assertAlmostEqual(r['in_sample_r2'],r2)
        self.assertEqual(r['effective_model_settings']['covariance'],'regularized return fit')
        self.assertIn('Model: constrained Ridge',r['report_text'])
        audit=next(x['estimator_calibration'] for x in r['joint_search_audit']
                   if x['end']==r['validation_fit_returns'].index[-1])
        expected=('nominal_adjusted_fit_r2_minus_gross_penalty' if audit['selected_policy']=='tracking'
                  else 'factor_covariance_risk_reduction_minus_penalties')
        self.assertEqual(r['short_window_selection_rule'],expected)
        score=E['_estimator_fit_score'](fit,r2,len(frame),len(basket),abs(fit.coef_).sum(),.02)
        expected_score=E['_short_window_fit_score'](r2,len(frame),len(basket),abs(fit.coef_).sum(),.02)[0]
        self.assertAlmostEqual(score,expected_score)

    def test_new_estimator_does_not_change_past_fits_using_future_test_prices(self):
        a=self.result;changed=sparse_relationship()
        changed['prices'].iloc[-12:,0]*=np.exp(np.linspace(.02,.3,12))
        b=run(changed,sample_window='3m')
        pd.testing.assert_series_equal(a['validation_weights'],b['validation_weights'])
        end=a['validation_fit_returns'].index[-1]
        def audits(r):
            return [x['estimator_calibration'] for x in r['joint_search_audit'] if x['end']<=end]
        self.assertEqual(audits(a),audits(b))
        for method in ('selected','factor','tracking'):
            af=a['method_validation']['folds'][0]['methods'][method]
            bf=b['method_validation']['folds'][0]['methods'][method]
            pd.testing.assert_series_equal(af['weights'],bf['weights'])
            self.assertEqual(af['intercept'],bf['intercept'])
            self.assertNotAlmostEqual(af['r2'],bf['r2'])

    def test_reference_search_and_frozen_predictions_reproduce_independently(self):
        r=self.result;fold=r['method_validation']['folds'][0]
        frame=r['validation_fit_returns'];w=fold['methods']['selected']['weights']
        audit=next(x for x in r['joint_search_audit'] if x['end']==frame.index[-1])
        rows,_=E['_joint_basket_search'](frame,'2889 TT Equity',audit['eligible_tickers'],
            [len(w)],keep=1,budget=r['params']['search_budget'],
            gross_penalty=r['params']['gross_penalty'],max_gross=2,max_leg=1)
        fit=rows[len(w)][0]['fit'][0];basket=rows[len(w)][0]['basket']
        item=fold['methods']['tracking']
        pd.testing.assert_series_equal(item['weights'],pd.Series(fit.coef_,index=basket))
        test=r['returns'].loc[fold['test_dates']]
        error=test['2889 TT Equity'].values-fit.predict(test[basket].values)
        spread=test['2889 TT Equity'].values-test[basket].values@fit.coef_
        np.testing.assert_allclose(item['prediction_errors'],error)
        np.testing.assert_allclose(item['spread_returns'],spread)
        self.assertEqual(fold['train_end'],frame.index[-1])
        self.assertLess(fold['train_end'],fold['test_start'])
        for reference in r['method_comparison'].values():
            self.assertEqual(reference['gross_penalty'],r['params']['gross_penalty'])
            self.assertEqual(reference['rows'],len(r['returns']))

    def test_comparison_caps_and_required_names_apply_to_all_policies(self):
        r=run(self.data,sample_window='3m',max_gross=1.2,max_leg=.7,force_include=['P0 TT Equity'])
        for fold in r['model_selection']['folds']:
            self.assertEqual(set(fold['recipes']),{'estimated','half','none','tracking'})
            for recipe in fold['recipes'].values():
                self.assertIn('P0 TT Equity',recipe['basket'])
                self.assertTrue(set(recipe['basket'])<=set(fold['eligible_tickers']))
                self.assertLessEqual(sum(abs(x) for x in recipe['weights']),1.2000001)
                self.assertLessEqual(max(abs(x) for x in recipe['weights']),.7000001)
        for item in r['method_comparison'].values():
            self.assertIn('P0 TT Equity',item['weights'].index)
            self.assertLessEqual(item['weights'].abs().sum(),1.2000001)
        for fold in r['method_validation']['folds']:
            for item in fold['methods'].values():
                self.assertLessEqual(item['weights'].abs().sum(),1.2000001)
                self.assertLessEqual(item['weights'].abs().max(),.7000001)

    def test_tracking_one_lucky_block_and_failed_comparison_cannot_win(self):
        policies=('estimated','tracking')
        for losses in ([0.,1.05,1.05],[.2,.2,np.nan]):
            folds=[{'loss':{'estimated':1.,'tracking':value}} for value in losses]
            a=E['_choose_residual_policy'](folds,policies)
            self.assertEqual(a['selected_policy'],'estimated')
        folds=[{'loss':{'estimated':1.,'tracking':.5}} for _ in range(3)]
        self.assertEqual(E['_choose_residual_policy'](folds,policies)['selected_policy'],'tracking')

    def test_short_window_cannot_promote_tracking_from_fitted_r2(self):
        r=run(self.data,sample_window='1m')
        self.assertEqual(r['model_selection']['status'],'insufficient_history')
        self.assertEqual(r['selected_estimator'],'factor')
        self.assertEqual(r['method_validation']['status'],'no_reserved_test')
        self.assertGreater(r['tracking_basket_reference']['r2'],r['in_sample_r2'])
        self.assertFalse(r['trade_eligible'])
        self.assertIn('no reliable method winner',' '.join(r['report_text'].split()))

    def test_fixed_family_option_excludes_tracking_only_from_selection(self):
        r=run(self.data,sample_window='3m',estimator_policy='factor')
        self.assertEqual(r['model_selection']['candidate_policies'],['estimated','half','none'])
        self.assertEqual(r['selected_estimator'],'factor')
        self.assertIn('tracking',r['method_validation']['methods'])
        with self.assertRaisesRegex(ValueError,'estimator_policy'):
            run(estimator_policy='highest_fitted_score')

    def test_two_day_comparison_purges_boundary_and_does_not_overlap_inner_rows(self):
        r=run(self.data,sample_window='3m',async_adjust=True)
        index=r['returns'].index
        for fold in r['model_selection']['folds']:
            start=index.get_loc(fold['test_start']);end=index.get_loc(fold['test_end'])
            self.assertGreaterEqual(start-index.get_loc(fold['train_end']),2)
            self.assertEqual(fold['test_rows'],len(index[start:end+1:2]))
            self.assertIn('tracking',fold['loss'])

    def test_selected_tracking_factor_decomposition_still_reconciles(self):
        r=self.result;a=r['hedge_error_attribution'];d=a['daily']
        np.testing.assert_allclose(d[['common_factor_gap','target_outside_factors',
            'hedge_outside_factors']].sum(axis=1),d['centered_spread'],atol=1e-12)
        self.assertAlmostEqual(sum(a['variance_contributions'].values()),1.)
        self.assertFalse(a['alpha_identified'])

    def test_export_keeps_exact_estimator_and_both_validation_recipes(self):
        with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stdout(io.StringIO()):
            bundle=E['load_hedge_diagnostics'](E['export_hedge_diagnostics'](self.result,folder))
        self.assertEqual(bundle['run_options']['estimator_policy'],'validated')
        self.assertEqual(bundle['result']['selected_estimator'],'tracking')
        self.assertEqual(set(bundle['result']['method_validation']['methods']),{'selected','factor','tracking'})
        self.assertEqual(bundle['result']['model_selection']['selected_policy'],'tracking')

    def test_sensitivity_and_sector_etf_references_use_selected_ridge_weights(self):
        r=self.result;frame=r['returns'];weights=r['weights'];names=list(weights.index)
        for check,sub in zip(r['current_sensitivity'],(frame.iloc[5:],frame.iloc[:-5])):
            fit,_,_=E['_fit_basket'](sub,'2889 TT Equity',names,2,1)
            self.assertAlmostEqual(check['max_weight_change'],np.max(abs(fit.coef_-weights.values)))
        result=dict(r,current_single_references={})
        options=dict(candidate_scope='sector',hedge_objective='factor',exclude=None,
                     max_gross=2,max_leg=1,gross_penalty=.02)
        E['_sector_etf_references'](result,frame,[],['0050 TT Equity','0055 TT Equity'],options)
        self.assertTrue(result['current_single_references'])
        for item in result['current_single_references'].values():
            fit,r2,_=E['_fit_basket'](frame,'2889 TT Equity',[item['ticker']],2,1)
            self.assertAlmostEqual(item['weight'],fit.coef_[0])
            self.assertAlmostEqual(item['r2'],r2)

    def test_market_cap_rejection_identifies_the_dated_screen(self):
        data=sparse_relationship();prices=data['prices']
        data['mktcap_hist']=pd.DataFrame(5000.,index=prices.index,columns=prices.columns)
        data['mktcap_hist']['P13 TT Equity']=500.
        data['mktcap_usd_mm']=data['mktcap_hist'].iloc[-1].to_dict()
        r=run(data,sample_window='3m',min_mktcap_usd_mm=1000)
        audit=next(x for x in r['joint_search_audit'] if x['end']==r['returns'].index[-1])
        item=next(x for x in audit['eligibility_exclusions'] if x['ticker']=='P13 TT Equity')
        self.assertEqual(item['reason'],'below historical market-cap floor')
        self.assertEqual(item['market_cap_usd_mm'],500.)
        self.assertEqual(item['minimum_market_cap_usd_mm'],1000.)
        self.assertEqual(item['asof'],r['returns'].index[-1])
        self.assertNotIn('P13 TT Equity',audit['eligible_tickers'])


class MatchedScoreTests(unittest.TestCase):
    def test_pooled_metrics_reconcile_for_long_windows(self):
        for window in ('6m','1y'):
            r=run(sample_window=window,lookback_options=(42,63),cv_test_window=10,cv_n_folds=2,outer_window=10,outer_folds=2)
            comparison=r['method_validation']
            self.assertEqual(comparison['status'],'ok')
            self.assertGreater(len(comparison['folds']),1)
            dates=[d for f in comparison['folds'] for d in f['test_dates']]
            self.assertEqual(len(dates),len(set(dates)))
            y=np.concatenate([f['target_returns'] for f in comparison['folds']])
            for method,item in comparison['methods'].items():
                errors=np.concatenate([f['methods'][method]['prediction_errors'] for f in comparison['folds']])
                spread=np.concatenate([f['methods'][method]['spread_returns'] for f in comparison['folds']])
                self.assertAlmostEqual(item['r2'],1-errors@errors/np.sum((y-y.mean())**2))
                self.assertAlmostEqual(item['vol_reduction'],1-spread.std()/y.std())
            self.assertAlmostEqual(comparison['methods']['selected']['r2'],r['ticket']['quality_r2'])
            self.assertAlmostEqual(comparison['methods']['selected']['vol_reduction'],r['trade_risk']['vol_reduction'])

    def test_failed_or_overlapping_tests_do_not_create_partial_favourable_scores(self):
        r=run(sample_window='3m');fold=r['method_validation']['folds'][0]
        bad=copy.deepcopy(fold);bad['status']='incomplete'
        a=E['_matched_method_summary']([fold,bad])
        self.assertEqual(a['status'],'incomplete_matched_comparison');self.assertFalse(a['methods'])
        a=E['_matched_method_summary']([fold,fold])
        self.assertEqual(a['status'],'overlapping_test_dates');self.assertFalse(a['methods'])


if __name__=='__main__':unittest.main()
