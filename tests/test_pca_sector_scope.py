"""Cross-market regression tests. All prices and classifications are synthetic."""
import contextlib
import io
import unittest
import numpy as np
import pandas as pd
from unittest.mock import patch
from test_pca_research import E, OPTIONS, fixture


class SectorScopeTests(unittest.TestCase):
    def sector_data(self, suffix='TT', sector='Financials', n=150):
        d=fixture(n=n,seed=61)
        target=f'TARGET {suffix} Equity'
        stocks=[f'S{i} {suffix} Equity' for i in range(7)]
        mapping={d['target']:target,**dict(zip(list(d['prices'].columns)[3:],stocks))}
        d['prices']=d['prices'].rename(columns=mapping)
        if suffix!='TT':
            d['prices']=d['prices'][[target]+stocks]
        unrelated=f'OTHER {suffix} Equity'
        d['prices'][unrelated]=d['prices'][target]  # perfect fit must still be excluded
        d.update(target=target,sector_scope_policy_version=1,
                 sector_stock_tickers_by_target={target:stocks},
                 peer_tickers_by_target={target:stocks[:2]},
                 peer_discovery_by_target={target:{'sector_stock_audit':[
                     {'ticker':t,'eligible':True,'reason':'same-market sector stock',
                      'evidence':['GICS_SECTOR_NAME: '+sector],'sector':sector,'industry':'Subindustry '+str(i%3)}
                     for i,t in enumerate(stocks)]}},
                 factor_tickers_by_target={target:['0055 TT Equity'] if suffix=='TT' else []},
                 sector_tickers_by_target={target:['0055 TT Equity'] if suffix=='TT' else []})
        return d,stocks,unrelated

    def test_discovery_and_search_in_six_markets_and_multiple_sectors(self):
        cases=[('TT','Financials'),('HK','Information Technology'),('AU','Materials'),
               ('JP','Consumer Discretionary'),('KS','Industrials'),('US','Health Care')]
        for suffix,sector in cases:
            with self.subTest(market=suffix,sector=sector):
                d,stocks,unrelated=self.sector_data(suffix,sector)
                target=d['target']
                refs={target:{'GICS_SECTOR_NAME':sector,'GICS_INDUSTRY_NAME':'Target industry'}}
                refs.update({t:{'GICS_SECTOR_NAME':sector,'GICS_INDUSTRY_NAME':'Different industry'} for t in stocks})
                refs[unrelated]={'GICS_SECTOR_NAME':'Utilities'}
                found,audit=E['_discover_sector_stocks'](target,refs,stocks+[unrelated])
                self.assertEqual(set(found),set(stocks))
                self.assertFalse(E['_peer_industry_supported'](refs[target],refs[stocks[0]]))
                d['peer_discovery_by_target'][target]['sector_stock_audit']=audit
                with contextlib.redirect_stdout(io.StringIO()):
                    r=E['find_best_hedge'](target,data=d,**dict(OPTIONS,candidate_scope='sector',sample_window='3m'))
                self.assertTrue(set(r['weights'].index)<=set(stocks))
                for row in r['basket_comparison']:
                    self.assertTrue(set(row['weights'].index)<=set(stocks))
                searched=r['sector_search_audit'][target]['searched_stocks']
                self.assertEqual(set(searched),set(stocks))
                self.assertNotIn(unrelated,searched)
                self.assertTrue(set(stocks[2:])<=set(searched))
                self.assertIn('Stocks actually searched:',r['report_text'])
                self.assertIn(stocks[-1],r['report_text'])

    def test_31_local_sector_stocks_do_not_collapse_to_9_narrow_peers(self):
        target='2889 TT Equity';stocks=[f'{3000+i} TT Equity' for i in range(31)]
        base={'COUNTRY_ISO':'TW','GICS_SECTOR_NAME':'Financials','GICS_INDUSTRY_NAME':'Target industry'}
        refs={target:base}
        refs.update({t:dict(base,GICS_INDUSTRY_NAME='Target industry' if i<9 else 'Other financial industry',
                           CRNCY_ADJ_MKT_CAP=500 if i>=23 else 2000) for i,t in enumerate(stocks)})
        meta={};fn=E['auto_discover_universe']
        stubs={'bbg_ref_single':lambda *a,**k:base,
               'bbg_ref_multi':lambda session,names,*a,**k:{t:refs.get(t,{}) for t in names},
               '_public_equity_universe':lambda *a:(stocks,[]),
               '_index_members':lambda *a:('TEST Index',[target]+stocks),
               '_sector_index_members':lambda *a:(['SECTOR Index'],[target]+stocks),
               'bbg_bulk':lambda *a,**k:[]}
        with patch.dict(fn.__globals__,stubs),contextlib.redirect_stdout(io.StringIO()):
            fn(None,target,min_mktcap_usd_mm=1000,meta=meta)
        self.assertEqual(len(meta['peer_tickers']),9)
        self.assertEqual(len(meta['sector_stock_tickers']),23)
        self.assertEqual(len([r for r in meta['sector_stock_audit'] if r['eligible']]),31)
        d={'peer_policy_version':4,'sector_scope_policy_version':1,
           'peer_tickers_by_target':{target:meta['peer_tickers']},
           'sector_stock_tickers_by_target':{target:meta['sector_stock_tickers']}}
        narrow=E['_filter_candidate_scope'](d,[target],[target]+stocks,'peers',True)
        broad=E['_filter_candidate_scope'](d,[target],[target]+stocks,'sector',True)
        self.assertEqual(len(narrow['columns'])-1,9)
        self.assertEqual(len(broad['columns'])-1,23)

    def test_download_retains_sector_metadata_through_analysis(self):
        d,stocks,unrelated=self.sector_data()
        target=d['target']
        def discovery(session,ticker,meta=None,**kwargs):
            meta.update(target=target,broad_market=E['_broad_market_spec'](target),peer_tickers=stocks[:2],peer_raw=stocks[:2],
                        sector_stock_tickers=stocks,
                        sector_stock_audit=d['peer_discovery_by_target'][target]['sector_stock_audit'],
                        source_candidates={'Same-market sector stocks':stocks})
            return stocks+[unrelated]
        fn=E['_download_hedge_data_impl']
        stubs={'auto_discover_universe':discovery,
               'bbg_hist':lambda session,names,*a:d['prices'][names].copy(),
               'bbg_ref_multi':lambda session,names,*a,**kw:{t:{'CRNCY_ADJ_MKT_CAP':2000,'CRNCY':'TWD'} for t in names}}
        with patch.dict(fn.__globals__,stubs),contextlib.redirect_stdout(io.StringIO()):
            downloaded=fn(target,session=object(),fetch_mktcap_hist=False,fetch_pit_members=False,cache=False)
            result=E['find_best_hedge'](target,data=downloaded,**dict(OPTIONS,candidate_scope='sector',sample_window='1m'))
        self.assertEqual(downloaded['sector_scope_policy_version'],1)
        self.assertEqual(downloaded['sector_stock_tickers_by_target'][target],stocks)
        self.assertEqual(set(result['sector_search_audit'][target]['searched_stocks']),set(stocks))
        self.assertNotIn(unrelated,result['weights'])

    def test_known_conflicts_unknown_labels_and_foreign_listings_cannot_leak(self):
        target='A US Equity';bad='B US Equity';unknown='C US Equity';foreign='D HK Equity'
        refs={target:{'GICS_SECTOR_NAME':'Financials'},bad:{'GICS_SECTOR_NAME':'Industrials'},
              unknown:{'GICS_SECTOR_NAME':'#N/A Field Not Applicable'},foreign:{'GICS_SECTOR_NAME':'Financials'}}
        names,rows=E['_discover_sector_stocks'](target,refs,[bad,unknown,foreign],
                  sector_members=[bad,foreign],sector_key='Financials')
        self.assertEqual(names,[])
        self.assertEqual(len(rows),3)

    def test_official_category_and_sector_index_fallback_keep_separate_evidence(self):
        target,a,b='A AU Equity','B AU Equity','C AU Equity'
        source=[{'status':'received','industry_scheme':'ASX industry group','industries':{target:'Materials',a:'Materials'}}]
        names,rows=E['_discover_sector_stocks'](target,{},[a,b],source,[b],'Materials')
        self.assertEqual(set(names),{a,b})
        self.assertIn('ASX industry group',rows[0]['evidence'][0])
        self.assertIn('mapped local sector index',rows[1]['evidence'][0])
        self.assertFalse(E['_peer_industry_supported']({},{}))

    def test_japan_listing_alias_is_one_market_and_target_is_never_a_candidate(self):
        refs={'7203 JP Equity':{'GICS_SECTOR_NAME':'Consumer Discretionary'},
              '7201 JT Equity':{'GICS_SECTOR_NAME':'Consumer Discretionary'}}
        names,_=E['_discover_sector_stocks']('7203 JP Equity',refs,['7201 JT Equity','7203 JT Equity'])
        self.assertEqual(names,['7201 JT Equity'])

    def test_default_scope_requires_new_metadata_and_keeps_etfs_as_references(self):
        d,stocks,other=self.sector_data()
        options={k:v for k,v in OPTIONS.items() if k!='candidate_scope'}
        with contextlib.redirect_stdout(io.StringIO()):
            r=E['find_best_hedge'](d['target'],data=d,sample_window='1m',**options)
        self.assertEqual(r['params']['candidate_scope'],'sector')
        self.assertFalse(r['params']['include_broad_market'])
        self.assertIn('single_etf',r['current_single_references'])
        self.assertTrue(r['current_single_references']['single_etf']['reference_only'])
        self.assertFalse(any(E['_is_etf'](t) for t in r['weights'].index))
        del d['sector_scope_policy_version']
        with self.assertRaisesRegex(ValueError,'fresh v118 download'),contextlib.redirect_stdout(io.StringIO()):
            E['find_best_hedge'](d['target'],data=d,sample_window='1m',**options)

    def test_etf_opt_in_exclusions_required_names_and_stale_cache(self):
        d,stocks,other=self.sector_data();target=d['target'];cols=list(d['prices'])
        f=E['_filter_candidate_scope']
        clean=f(d,[target],cols,'sector',True,exclude=[stocks[0]])
        self.assertNotIn(stocks[0],clean['columns']);self.assertNotIn('0055 TT Equity',clean['columns'])
        expanded=f(d,[target],cols,'sector_focused',True)
        self.assertIn('0055 TT Equity',expanded['columns']);self.assertIn('0050 TT Equity',expanded['columns'])
        with self.assertRaisesRegex(ValueError,'conflict'):
            f(d,[target],cols,'sector',True,forced=[other])
        with self.assertRaisesRegex(ValueError,'conflict'):
            f(d,[target],cols,'sector',True,forced=['0055 TT Equity'])

    def test_default_ui_is_stock_sector_scope(self):
        d,_,_=self.sector_data()
        with contextlib.redirect_stdout(io.StringIO()): state=E['hedge_ui'](d)
        w=state['widgets'];self.assertEqual(w['candidate_scope'].value,'sector')
        self.assertTrue({'sector','sector_focused','peers','focused','all'}<=set(v for _,v in w['candidate_scope'].options))

    def test_all_user_windows_and_new_scope_preserve_caps_and_holdout_isolation(self):
        d,stocks,_=self.sector_data(n=420)
        for period in ('1m','2m','3m','6m','1y'):
            with self.subTest(window=period),contextlib.redirect_stdout(io.StringIO()):
                r=E['find_best_hedge'](d['target'],data=d,**dict(OPTIONS,candidate_scope='sector',sample_window=period))
            self.assertTrue(set(r['weights'].index)<=set(stocks))
            self.assertEqual(r['returns'].index[-1],d['prices'].index[-1])
            self.assertLessEqual(r['weights'].abs().sum(),2+1e-7)
            self.assertGreaterEqual(float(r['weights'].abs().min()),.01-1e-9)
        opts=dict(OPTIONS,candidate_scope='sector_focused',sample_window='3m')
        with contextlib.redirect_stdout(io.StringIO()):
            before=E['find_best_hedge'](d['target'],data=d,**opts)
            d['prices'].iloc[-12:,0]*=np.exp(np.linspace(0,.1,12))
            after=E['find_best_hedge'](d['target'],data=d,**opts)
        pd.testing.assert_series_equal(before['validation_weights'],after['validation_weights'])
        self.assertFalse(before['params']['candidate_scope']=='sector')

    def test_search_audit_resolves_aliases_and_keeps_disjoint_counts(self):
        a='7201 JP Equity';alias='7201 JT Equity';target='7203 JP Equity'
        frame=pd.DataFrame({target:[100.,101.],alias:[100.,102.]})
        data={'prices':frame,'peer_discovery_by_target':{target:{'sector_stock_audit':[
            {'ticker':a,'eligible':True,'reason':'same sector','evidence':[]}]}}}
        result={'params':{'candidate_scope':'sector'},'prices':frame,
                'portfolio_legs':[target],'weights':pd.Series({alias:.3}),
                'joint_search_audit':[{'end':2,'rows':2,'eligible_tickers':[alias]}]}
        audit=E['_sector_search_audit'](result,data)[target]
        self.assertEqual(audit['rows'][0]['status'],'selected basket')
        self.assertEqual(sum(audit['counts'].values()),audit['discovered_sector_stocks'])

    def test_window_rejections_have_a_reason_and_do_not_count_as_searched(self):
        d,stocks,_=self.sector_data()
        d['prices'][stocks[-1]]=100.0
        with contextlib.redirect_stdout(io.StringIO()):
            r=E['find_best_hedge'](d['target'],data=d,**dict(OPTIONS,candidate_scope='sector',sample_window='2m',exclude=[stocks[-2]]))
        audit=r['sector_search_audit'][d['target']]
        statuses={row['ticker']:row['status'] for row in audit['rows']}
        self.assertEqual(statuses[stocks[-2]],'manual exclusion')
        self.assertNotIn(stocks[-1],audit['searched_stocks'])
        self.assertNotIn(stocks[-1],r['weights'])
        self.assertNotIn(statuses[stocks[-1]],('selected basket','alternative basket','searched; not selected'))


if __name__=='__main__':
    unittest.main()
