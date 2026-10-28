"""Regression tests for listing fallbacks, constrained selection and fit scope."""
import contextlib,io,inspect,unittest
from unittest.mock import patch,MagicMock
import numpy as np
import pandas as pd
from test_pca_research import E,fixture,run,OPTIONS
from test_pca_peer_discovery import electronics

class OctoberReviewTests(unittest.TestCase):
    def test_roundoff_at_gross_limit_does_not_discard_valid_baskets(self):
        from test_pca_estimator_selection import sparse_relationship
        solve=E['_solve_hedge_qp']; boundary_calls=[]
        def rounded(H,c,max_gross=None,max_leg=None):
            w=solve(H,c,max_gross,max_leg).copy()
            if max_gross and abs(abs(w).sum()-max_gross)<1e-10:
                # Simulate cross-platform BLAS/SLSQP rounding at a binding cap.
                j=int(np.argmax(abs(w)))
                while abs(w).sum()<=max_gross:
                    w[j]=np.nextafter(w[j],np.copysign(np.inf,w[j]))
                boundary_calls.append(abs(w).sum())
            return w
        with patch.dict(solve.__globals__,{'_solve_hedge_qp':rounded}):
            r=run(sparse_relationship(),sample_window='3m',max_gross=1.2,
                  max_leg=.7,force_include=['P0 TT Equity'])
        self.assertTrue(boundary_calls)
        self.assertGreaterEqual(len(r['weights']),2)
        self.assertIn('P0 TT Equity',r['weights'].index)
        self.assertLessEqual(r['weights'].abs().sum(),1.2+1e-7)
        self.assertLessEqual(r['weights'].abs().max(),.7+1e-7)

    def test_yahoo_client_public_api_is_installed(self):
        import yfinance as yf
        self.assertTrue(callable(yf.screen))
        self.assertEqual(yf.EquityQuery('eq',['region','hk']).to_dict()['operator'],'EQ')

    def test_yahoo_maps_all_priority_venues_without_accepting_etfs_or_foreign_quotes(self):
        cases=[('HK','1989.HK','HKG','1989 HK Equity'),('TW','2889.TW','TAI','2889 TT Equity'),
          ('TW','5864.TWO','TWO','5864 TT Equity'),('JP','285A.T','JPX','285A JP Equity'),
          ('KR','005930.KS','KSC','005930 KS Equity'),('KR','035900.KQ','KOE','035900 KS Equity'),
          ('AU','GMD.AX','ASX','GMD AU Equity'),('US','BRK-B','NYQ','BRK/B US Equity')]
        for market,symbol,exchange,want in cases:
            q=dict(symbol=symbol,exchange=exchange,quoteType='EQUITY')
            self.assertEqual(E['_yahoo_listing_ticker'](q,market),want)
            self.assertIsNone(E['_yahoo_listing_ticker'](dict(q,quoteType='ETF'),market))
            self.assertIsNone(E['_yahoo_listing_ticker'](dict(q,exchange='UNKNOWN'),market))
        self.assertIsNone(E['_yahoo_listing_ticker'](dict(symbol='80700.HK',exchange='HKG',quoteType='EQUITY'),'HK'))

    def test_yahoo_pages_by_slots_even_when_one_quote_is_omitted(self):
        offsets=[]
        def fetch(offset):
            offsets.append(offset)
            ids=range(1,250) if offset==0 else [1989]
            return dict(start=offset,total=251,quotes=[dict(symbol=f'{i:04d}.HK',exchange='HKG',quoteType='EQUITY') for i in ids])
        names,audit=E['_yahoo_equity_universe']('HK',fetch_page=fetch)
        self.assertEqual(offsets,[0,250]);self.assertIn('1989 HK Equity',names)
        self.assertEqual(audit['status'],'partial');self.assertEqual(audit['omitted_quote_slots'],1)
        self.assertTrue(audit['requires_security_type']);self.assertFalse(audit['coverage_complete'])

    def test_yahoo_paging_failure_keeps_received_names_but_never_claims_completion(self):
        def fetch(offset):
            if offset: raise TimeoutError('network down')
            return dict(total=501,start=0,quotes=[dict(symbol=f'{i:04d}.HK',exchange='HKG',quoteType='EQUITY') for i in range(1,251)])
        names,a=E['_yahoo_equity_universe']('HK',fetch_page=fetch)
        self.assertEqual(len(names),250);self.assertEqual(a['status'],'partial');self.assertIn('network down',a['reason'])
        names,a=E['_yahoo_equity_universe']('HK',fetch_page=lambda offset:dict(total=5,start=999,quotes=[]))
        self.assertFalse(names);self.assertFalse(a['coverage_complete']);self.assertIn('offset',a['reason'])

    def test_yahoo_directory_is_not_a_peer_label(self):
        names=['1989 HK Equity','999 HK Equity']
        audit=[dict(requires_security_type=True,issuer_names=dict.fromkeys(names,'company'),status='partial')]
        accepted,blocked=E['_verify_roster_candidates'](names,audit,{names[0]:electronics(),names[1]:{'SECURITY_TYP':'Warrant'}})
        self.assertEqual(accepted,[names[0]]);self.assertIn(names[1],blocked)
        self.assertEqual(E['_strict_peer_set'](electronics(),{names[0]:dict(SECURITY_TYP='Common Stock',GICS_INDUSTRY_NAME='Banks')},accepted)[0],[])

    def test_official_failure_uses_independent_directory_and_retains_both_statuses(self):
        fallback=MagicMock(return_value=(['1989 HK Equity'],dict(source='Yahoo',status='received',count=1)))
        with patch.dict(E['_public_equity_universe'].__globals__,{'_bundled_listing_sources':lambda market:{},'_public_roster_bytes':MagicMock(side_effect=OSError('TLS/proxy denied')),'_yahoo_equity_universe':fallback}):
            names,a=E['_public_equity_universe']('HK')
        self.assertEqual(names,['1989 HK Equity']);fallback.assert_called_once_with('HK')
        self.assertEqual(a[0]['status'],'unavailable');self.assertIn('TLS/proxy denied',a[0]['reason'])
        self.assertEqual(a[-1]['status'],'received')

    def test_constrained_pair_screen_agrees_with_independent_qp(self):
        rng=np.random.default_rng(42)
        for gross,leg in ((.7,.4),(.7,None),(None,.4),(None,None)):
            for _ in range(10):
                z=rng.normal(size=(4,2));H=z.T@z+np.eye(2)*.001;c=rng.normal(size=2)*3
                a,b=E['_constrained_pair_weights'](*[np.array([v]) for v in (H[0,0],H[1,1],H[0,1],c[0],c[1])],gross,leg)
                w=np.array([a[0],b[0]]);q=E['_solve_hedge_qp'](H,c,gross,leg)
                self.assertAlmostEqual(float(w@H@w-2*c@w),float(q@H@q-2*c@q),places=7)

    def test_partial_basket_materiality_is_not_used_to_prune_growth(self):
        f=np.log(fixture(60)['prices']).diff().dropna();names=list(f.columns[1:])
        checked=[]
        def materiality(w): checked.append(len(w));return True
        with patch.dict(E['_joint_basket_search'].__globals__,{'_meaningful_basket':materiality}):
            E['_joint_basket_search'](f,f.columns[0],names,[3],budget=30,keep=3,max_gross=2,max_leg=1)
        self.assertTrue(checked);self.assertEqual(set(checked),{3})

    def test_alternative_display_count_does_not_change_winning_search(self):
        f=np.log(fixture(70)['prices']).diff().dropna();names=list(f.columns[1:])
        a,_=E['_joint_basket_search'](f,f.columns[0],names,[3],keep=2)
        b,_=E['_joint_basket_search'](f,f.columns[0],names,[3],keep=15)
        self.assertEqual(a[3][0]['basket'],b[3][0]['basket'])
        np.testing.assert_allclose(a[3][0]['fit'][0].coef_,b[3][0]['fit'][0].coef_)

    def test_final_fit_obeys_selected_lookback_and_keeps_full_horizon_chart(self):
        r=run(sample_window='6m',lookback_options=(40,),cv_test_window=10,cv_n_folds=2,outer_folds=2,outer_window=10)
        self.assertIsNotNone(r['current_fit']['selected_lookback'])
        self.assertEqual(len(r['returns']),r['current_fit']['selected_lookback'])
        self.assertEqual(len(r['returns']),r['params']['lookback'])
        self.assertGreater(len(r['analysis_returns']),len(r['returns']))
        chart=E['_tracking_chart_data'](r)['current']
        self.assertTrue(chart['history'].index.equals(r['analysis_returns'].index))
        self.assertAlmostEqual(chart['r2'],r['in_sample_r2'])
        specs=set(r['cv_detail']['pc_spec']) if 'cv_detail' in r else set(r['cv_results']['pc_spec'])
        self.assertFalse(any(str(x).startswith('search:') and x!='search:0' for x in specs))
        self.assertGreater(len(r['basket_comparison']),1)

    def test_legacy_pca_directions_exclude_target_and_project_its_loading(self):
        opts=dict(sample_window='1m',basket_methods='pca',hedge_objective='tracking',broad_search=False,pc_options=[2])
        r=run(**opts);d=fixture();d['prices'].iloc[-15:,0]*=np.exp(np.linspace(0,.1,15))
        q=run(d,**opts)
        np.testing.assert_allclose(abs(r['chart_pca'].components_),abs(q['chart_pca'].components_))
        self.assertIn('2889 TT Equity',r['chart_loadings'].index)
        self.assertEqual(r['chart_pca'].components_.shape[1],len(r['chart_loadings'])-1)

    def test_simple_return_check_aggregates_each_portfolio_leg_before_netting(self):
        f=pd.DataFrame({'A':[.1,-.2,.04],'B':[-.05,.3,.1],'H':[.02,-.01,.03]})
        f[E['PORTFOLIO_COL']]=.6*f.A+.4*f.B
        r=dict(returns=f,weights=pd.Series({'H':.5}),portfolio_legs=['A','B'],portfolio_weights={'A':.6,'B':.4},is_portfolio=True)
        a=E['_simple_return_reconciliation'](r)
        self.assertEqual(a['status'],'ok')
        want=.6*np.expm1(f.A)+.4*np.expm1(f.B)-.5*np.expm1(f.H)
        np.testing.assert_allclose(a['returns']['spread'],want)
        self.assertGreater(a['max_daily_basis_gap'],.01)

    def test_download_default_and_forced_names_do_not_become_mandatory_weights(self):
        self.assertEqual(inspect.signature(E['download_hedge_data']).parameters['download_scope'].default,'all')
        d=fixture(40);forced='1989 HK Equity';d['prices'][forced]=d['prices'].iloc[:,1]
        mock_hist=MagicMock(side_effect=lambda session,names,*a:d['prices'][names])
        stubs={'bbg_hist':mock_hist,'bbg_ref_multi':lambda *a,**k:{},'_download_execution_snapshot':lambda *a:({},{})}
        with patch.dict(E['download_hedge_data'].__globals__,stubs),contextlib.redirect_stdout(io.StringIO()):
            out=E['download_hedge_data'](d['target'],candidates=[d['prices'].columns[1]],force_download=['1989 HK'],session=object(),cache=False,fetch_mktcap_hist=False,fetch_pit_members=False,download_scope='related')
        self.assertIn(forced,mock_hist.call_args[0][1]);self.assertIn(forced,out['prices'])
        self.assertEqual(out['fingerprint']['force_include'],[]);self.assertEqual(out['force_download_missing'],[])
        with self.assertRaisesRegex(ValueError,'conflicting'):
            E['download_hedge_data'](d['target'],force_download=['1989 HK'],exclude=['1989 HK'])

    def test_invalid_field_preflight_does_not_disable_entitlement_failed_fields(self):
        target,peer='T US Equity','P US Equity';calls=[]
        def reference(session,names,fields,**kw):
            calls.append((names,list(fields)))
            if names==[target]:
                kw['errors'].extend([dict(field='BICS_LEVEL_4_SUB_INDUSTRY_NAME',reason='BAD_FLD INVALID_FIELD'),dict(field='GICS_INDUSTRY_NAME',reason='NOT_ENTITLED')])
            return {t:electronics(COUNTRY_ISO='US') for t in names}
        stubs={'bbg_ref_multi':reference,'bbg_bulk':lambda *a:[], '_public_equity_universe':lambda *a:([target,peer],[]),
               '_index_members':lambda *a:('TEST Index',[target,peer]),'_sector_index_members':lambda *a:([],[])}
        with patch.dict(E['auto_discover_universe'].__globals__,stubs),contextlib.redirect_stdout(io.StringIO()):
            E['auto_discover_universe'](None,target,min_mktcap_usd_mm=0)
        self.assertGreater(len(calls),1)
        for names,fields in calls[1:]:
            if 'GICS_INDUSTRY_NAME' in fields:
                self.assertNotIn('BICS_LEVEL_4_SUB_INDUSTRY_NAME',fields)
                self.assertIn('GICS_INDUSTRY_NAME',fields)

    def test_yahoo_changing_total_retains_later_valid_pages_with_warning(self):
        def fetch(offset):
            ids=range(1,251) if offset==0 else [1989,1990]
            return dict(total=251 if offset==0 else 252,start=offset,quotes=[dict(symbol=f'{i:04d}.HK',exchange='HKG',quoteType='EQUITY') for i in ids])
        names,a=E['_yahoo_equity_universe']('HK',fetch_page=fetch)
        self.assertIn('1989 HK Equity',names);self.assertIn('1990 HK Equity',names)
        self.assertEqual(a['status'],'partial');self.assertTrue(a['pagination_changed'])

    def test_yahoo_uses_two_directions_for_large_exchange_and_no_cap_filter(self):
        import yfinance as yf
        from curl_cffi import requests
        calls=[]
        def pages(market,fetch,*args):
            fetch(0);i=len(calls);calls.append(i)
            symbols=[str(j) for j in range(10000)] if i==0 else ['10000']
            return ['1989 HK Equity'],dict(issuer_names={'1989 HK Equity':'Delton'},raw_symbols=symbols,
                reported_total=10001,pages=40,status='partial',coverage_complete=False)
        with patch.dict(E['_yahoo_equity_universe'].__globals__,{'_yahoo_directory_pages':pages}),patch.object(requests,'Session'),patch.object(yf,'screen') as screen:
            names,a=E['_yahoo_equity_universe']('HK')
        self.assertEqual(names,['1989 HK Equity']);self.assertTrue(a['coverage_complete'])
        self.assertEqual([c.kwargs['sortAsc'] for c in screen.call_args_list],[False,True])
        self.assertEqual(screen.call_args_list[0].args[0].to_dict(),{'operator':'EQ','operands':['exchange','HKG']})

    def test_reference_request_error_is_drained_and_successful_batches_survive(self):
        class Element:
            def __init__(self,value): self.value=value
            def hasElement(self,key): return key in self.value
            def getElement(self,key): return Element(self.value[key])
            def getElementAsString(self,key): return str(self.value[key])
            def numValues(self): return len(self.value)
            def getValueAsElement(self,key): return Element(self.value[key])
            def __str__(self): return str(self.value)
        done=[]
        def drain(session,cb):
            cb(Element({'responseError':'bad batch'}))
            cb(Element({'securityData':[{'security':'OK','fieldData':{'NAME':'Good'}}]}))
            done.append(True)
        errors=[]
        with patch.dict(E['bbg_ref_multi'].__globals__,{'_drain_events':drain}):
            data=E['bbg_ref_multi'](MagicMock(),['OK','BAD'],['NAME'],errors=errors)
        self.assertEqual(done,[True]);self.assertEqual(data['OK']['NAME'],'Good')
        self.assertIn('bad batch',errors[0]['reason'])

    def test_batched_peer_requests_preserve_per_security_errors(self):
        class Element:
            def __init__(self,value,name=''): self.value=value;self.key=name
            def hasElement(self,key): return key in self.value
            def getElement(self,key):
                if isinstance(key,int): key=list(self.value)[key]
                return Element(self.value[key],key)
            def getElementAsString(self,key): return str(self.value[key])
            def numValues(self): return len(self.value)
            def numElements(self): return len(self.value)
            def getValueAsElement(self,key): return Element(self.value[key])
            def name(self): return self.key
            def getValue(self): return self.value
            def __str__(self): return str(self.value)
        records=[{'security':'OK','fieldData':{'BLOOMBERG_PEERS':[{'Peer Ticker':'1989 HK'}]}},
                 {'security':'BAD','securityError':'Not entitled'}]
        with patch.dict(E['bbg_bulk'].__globals__,{'_drain_events':lambda session,cb:cb(Element({'securityData':records}))}):
            out=E['bbg_bulk'](MagicMock(),['OK','BAD'],'BLOOMBERG_PEERS')
        self.assertEqual(out['OK'],[{'Peer Ticker':'1989 HK'}]);self.assertIsInstance(out['BAD'],RuntimeError)

    def test_local_listing_search_with_missing_identity_remains_unresolved(self):
        target,foreign,local='2476 HK Equity','001389 CH Equity','1989 HK Equity'
        refs={target:electronics(ID_BB_COMPANY='1'),foreign:electronics(ID_BB_COMPANY='2',NAME='Delton')}
        session=MagicMock();session.openService.return_value=True
        with patch.dict(E['_local_peer_listings'].__globals__,{'_bbg_equity_lookup':lambda *a:([local],False),
                  '_discovery_references':lambda *a:{local:{}}}):
            names,audit=E['_local_peer_listings'](session,target,[foreign],refs,[],[])
        self.assertFalse(names);self.assertEqual(audit[0]['status'],'unresolved')
        self.assertIn('identity',audit[0]['reason'])

if __name__=='__main__': unittest.main()
