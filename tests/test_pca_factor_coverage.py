"""Synthetic regressions for the short-window omission in PCA result3."""
import contextlib
import io
import unittest
import numpy as np
import pandas as pd
from test_pca_research import E, OPTIONS


def gold_data(n=120, suffix='AU', seed=320):
    rng = np.random.default_rng(seed)
    m, b, g = rng.normal(0, .01, (3, n))
    target = 'GMD '+suffix+' Equity'
    golds = ['G'+str(i)+' '+suffix+' Equity' for i in range(5)]
    base = ['B'+str(i)+' '+suffix+' Equity' for i in range(4)]
    stocks = golds+base
    refs = {'STW AU Equity':m, 'IOZ AU Equity':m+.01*b,
            'MVR AU Equity':.5*m+b, 'OZR AU Equity':.5*m+b+rng.normal(0,.0005,n),
            'PMGOLD AU Equity':g}
    returns = {target:.15*m+.1*b+1.4*g+rng.normal(0,.001,n)}
    returns.update(refs)
    returns.update({t:.2*m+1.2*g+rng.normal(0,.002,n) for t in golds})
    returns.update({t:.6*m+b+rng.normal(0,.002,n) for t in base})
    frame = pd.DataFrame(returns,index=pd.bdate_range('2026-05-01',periods=n))
    data = {'target':target,'prices':100*np.exp(frame.cumsum()),
            'price_observations':'ACTIVE_DAYS_ONLY','peer_policy_version':4,
            'peer_tickers_by_target':{target:stocks},'sector_scope_policy_version':1,
            'sector_stock_tickers_by_target':{target:stocks},
            'sector_tickers_by_target':{target:[]},
            'factor_tickers_by_target':{target:['MVR AU Equity','OZR AU Equity','PMGOLD AU Equity']},
            'peer_discovery_by_target':{target:{'classification_evidence':{
                target:{'GICS_SECTOR_NAME':'Materials','GICS_INDUSTRY_NAME':'Metals & Mining',
                        'GICS_SUB_INDUSTRY_NAME':'Gold'}}}}}
    return data,frame,golds,base


def analyze(data, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return E['find_best_hedge'](data['target'],data=data,
            **dict(OPTIONS,candidate_scope='sector',sample_window='1m',**kwargs))


class FactorCoverageTests(unittest.TestCase):
    def test_taxonomy_plurals_are_not_lost_and_substrings_do_not_match(self):
        self.assertEqual(E['_exposure_tags']('Semiconductors'),{'SEMIS'})
        self.assertEqual(E['_exposure_tags']('Banks', 'Banking'),{'RATES'})
        self.assertEqual(E['_exposure_tags']('Airlines'),{'ENERGY'})
        self.assertEqual(E['_exposure_tags']('Precious Metals'),{'GOLD'})
        self.assertEqual(E['_exposure_tags']('Riverbank', 'Soil products'),set())

    def test_short_gold_window_keeps_gold_and_equity_capacity(self):
        data,frame,golds,base = gold_data(n=22)
        refs = E['_ordered_factor_references'](data,[data['target']])
        self.assertLess(refs.index('PMGOLD AU Equity'),refs.index('MVR AU Equity'))
        model = E['_common_risk_model'](frame,data['target'],golds+base,refs)
        self.assertIn('STW AU Equity',model['labels'])
        self.assertIn('PMGOLD AU Equity',model['labels'])
        self.assertEqual(model['equity_pc_count'],1)
        self.assertLessEqual(len(model['labels']),3)
        rows,_ = E['_joint_basket_search'](frame,data['target'],golds+base,[3],factor_model=model,max_gross=2,max_leg=1)
        best = rows[3][0]
        self.assertTrue(set(best['basket'])<=set(golds))
        self.assertGreater(best['fit'][1],.85)

    def test_full_short_run_uses_gold_stocks_without_putting_etfs_in_basket(self):
        data,_,golds,_ = gold_data()
        result = analyze(data)
        self.assertTrue(set(result['weights'].index)<=set(golds))
        self.assertIn('PMGOLD AU Equity',[r[0] for r in result['common_exposures']['rows']])
        self.assertGreater(result['in_sample_r2'],.85)
        self.assertIn('MAPPED REFERENCE NOT RETAINED',result['report_text'])
        self.assertIn('FITTED TRACKING COMPARISON',result['report_text'])

    def test_priority_uses_subindustry_in_different_markets(self):
        for target, sector, narrow, broad, theme in [
            ('G US Equity','Materials','Gold','Metals & Mining','GLD US Equity'),
            ('G HK Equity','Materials','Gold','Metals & Mining','2840 HK Equity'),
            ('G JP Equity','Materials','Gold','Metals & Mining','1540 JT Equity'),
            ('S US Equity','Information Technology','Semiconductors','Technology','SMH US Equity'),
            ('S TT Equity','Information Technology','Semiconductors','Technology','00891 TT Equity')]:
            with self.subTest(target=target):
                fallback='OTHER '+target.split()[1]+' Equity'
                data={'factor_tickers_by_target':{target:[fallback,theme]},
                      'sector_tickers_by_target':{target:[fallback]},
                      'peer_discovery_by_target':{target:{'classification_evidence':{target:{
                          'GICS_SECTOR_NAME':sector,'GICS_SUB_INDUSTRY_NAME':narrow,'GICS_INDUSTRY_NAME':broad}}}}}
                refs=E['_ordered_factor_references'](data,[target])
                self.assertLess(refs.index(theme),refs.index(fallback))

    def test_reference_list_order_does_not_override_taxonomy_priority(self):
        data,frame,golds,base=gold_data(n=22)
        a=E['_ordered_factor_references'](data,[data['target']])
        data['factor_tickers_by_target'][data['target']].reverse()
        b=E['_ordered_factor_references'](data,[data['target']])
        self.assertEqual(a,b)
        data['peer_discovery_by_target'][data['target']]['classification_evidence'][data['target']]['GICS_SUB_INDUSTRY_NAME']='#N/A'
        # Missing taxonomy is not silently treated as a gold classification.
        self.assertIn('PMGOLD AU Equity',E['_ordered_factor_references'](data,[data['target']]))

    def test_missing_gold_prices_use_stock_pca_and_disclose_missing_reference(self):
        data,frame,golds,base=gold_data(n=22)
        frame=frame.drop(columns=['PMGOLD AU Equity'])
        model=E['_common_risk_model'](frame,data['target'],golds+base,
            E['_ordered_factor_references'](data,[data['target']]))
        status={r['instrument']:r['status'] for r in model['reference_audit']}
        self.assertEqual(status['PMGOLD AU Equity'],'unavailable on aligned training dates')
        self.assertGreater(model['equity_pc_count'],0)
        fit,score,_=E['_fit_common_risk'](frame,data['target'],golds[:3],model,2,1)
        self.assertGreater(score,.7)

    def test_proxy_alternatives_do_not_consume_multiple_factor_slots(self):
        data,frame,golds,base=gold_data(n=66)
        refs=E['_ordered_factor_references'](data,[data['target']])
        model=E['_common_risk_model'](frame,data['target'],[],refs)
        self.assertIn('MVR AU Equity',model['labels'])
        self.assertNotIn('OZR AU Equity',model['labels'])
        frame['MVR AU Equity']=0.
        backup=E['_common_risk_model'](frame,data['target'],[],refs)
        self.assertIn('OZR AU Equity',backup['labels'])

    def test_target_is_excluded_from_factor_basis_and_covariance_is_psd(self):
        data,frame,golds,base=gold_data(n=22)
        refs=E['_ordered_factor_references'](data,[data['target']])
        before=E['_common_risk_model'](frame,data['target'],golds+base,refs)
        frame[data['target']]*=-50
        after=E['_common_risk_model'](frame,data['target'],golds+base+[data['target']],refs)
        np.testing.assert_allclose(before['factors'],after['factors'])
        self.assertGreater(np.linalg.eigvalsh(before['covariance']).min(),0)
        self.assertEqual(before['labels'],after['labels'])

    def test_tracking_comparison_obeys_same_dates_size_caps_and_required_names(self):
        data,_,golds,base=gold_data()
        result=analyze(data,max_gross=.8,max_leg=.4,force_include=[golds[0]],exclude=[golds[-1]])
        ref=result['tracking_basket_reference']; w=ref['weights']
        self.assertEqual(ref['status'],'ok')
        self.assertTrue(ref['reference_only'])
        self.assertEqual(len(w),len(result['weights']))
        self.assertIn(golds[0],w.index);self.assertNotIn(golds[-1],w.index)
        self.assertLessEqual(w.abs().sum(),.8000001)
        self.assertLessEqual(w.abs().max(),.4000001)
        self.assertEqual(ref['fit_end'],result['returns'].index[-1])
        self.assertEqual(ref['rows'],len(result['returns']))
        frame=result['returns']; spread=frame[data['target']]-frame[w.index]@w
        expected=1-spread.var()/frame[data['target']].var()
        self.assertAlmostEqual(ref['r2'],expected)
        self.assertEqual(len(result['trade_weights']),0)

    def test_current_reference_cannot_leak_into_frozen_holdout(self):
        data,_,_,_=gold_data(n=180)
        with contextlib.redirect_stdout(io.StringIO()):
            before=E['find_best_hedge'](data['target'],data=data,**dict(OPTIONS,candidate_scope='sector',sample_window='3m'))
            data['prices'].iloc[-12:,0]*=np.exp(np.linspace(0,.3,12))
            after=E['find_best_hedge'](data['target'],data=data,**dict(OPTIONS,candidate_scope='sector',sample_window='3m'))
        pd.testing.assert_series_equal(before['validation_weights'],after['validation_weights'])
        self.assertNotAlmostEqual(before['holdout_r2'],after['holdout_r2'])
        self.assertNotAlmostEqual(before['tracking_basket_reference']['r2'],after['tracking_basket_reference']['r2'])

    def test_all_factor_budgets_are_bounded_and_invalid_values_fail(self):
        data,frame,golds,base=gold_data(n=22)
        refs=E['_ordered_factor_references'](data,[data['target']])
        for limit in (1,2,3,5):
            model=E['_common_risk_model'](frame,data['target'],golds+base,refs,max_factors=limit)
            self.assertLessEqual(len(model['labels']),limit)
        with self.assertRaises(ValueError):
            E['_common_risk_model'](frame,data['target'],golds+base,refs,max_factors=0)


if __name__=='__main__':
    unittest.main()
