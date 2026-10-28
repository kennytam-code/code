"""Coverage, short-history and calendar regressions; no Bloomberg/network needed."""
import contextlib,copy,io,unittest
from unittest.mock import patch,MagicMock
import numpy as np
import pandas as pd
from test_pca_research import E,fixture,OPTIONS
from test_pca_peer_discovery import electronics

class October28Tests(unittest.TestCase):
    def test_parent_taxonomy_admits_different_semiconductor_subindustries(self):
        base=electronics(BICS_LEVEL_3_INDUSTRY_NAME='Semiconductors',GICS_INDUSTRY_NAME='Semiconductors & Semiconductor Equipment')
        refs={t:dict(base,BICS_LEVEL_4_SUB_INDUSTRY_NAME=label,GICS_SUB_INDUSTRY_NAME=label)
              for t,label in [('3986 HK Equity','Memory ICs'),('3223 HK Equity','Analog ICs'),
                              ('9976 HK Equity','Storage Devices'),('000660 KS Equity','DRAM')]}
        for name,ref in refs.items():
            if name!='3986 HK Equity':
                self.assertTrue(E['_peer_industry_supported'](refs['3986 HK Equity'],ref))
        self.assertTrue(E['_peer_industry_supported']({'GICS_INDUSTRY_GROUP_NAME':'Banks'},
                                                     {'GICS_INDUSTRY_GROUP_NAME':'Banks'}))
        self.assertFalse(E['_peer_industry_supported'](base,dict(base,SECURITY_TYP2='ETF')))
        self.assertFalse(E['_peer_industry_supported'](base,dict(base,GICS_SECTOR_NAME='Utilities')))

    def test_offline_roster_has_recent_hk_listings_and_dated_provenance(self):
        fn=E['_public_equity_universe'];fetch=MagicMock(side_effect=TimeoutError('restricted network'))
        with patch.dict(fn.__globals__,{'_public_roster_bytes':fetch,
                '_yahoo_equity_universe':MagicMock(side_effect=AssertionError('do not spend another timeout'))}):
            names,audit=fn('HK')
        self.assertTrue({'3223 HK Equity','9976 HK Equity'}<=set(names))
        self.assertEqual(fetch.call_count,1)
        self.assertEqual(audit[0]['transport'],'bundled snapshot')
        self.assertTrue(audit[0]['snapshot_asof'].startswith('2026-10-28'))
        self.assertTrue(audit[0]['requires_security_type'])
        self.assertIn('restricted network',audit[0]['attempts'][0]['reason'])
        accepted,_=E['_verify_roster_candidates'](['3223 HK Equity','9976 HK Equity'],audit,
            {'3223 HK Equity':electronics(),'9976 HK Equity':electronics()})
        self.assertEqual(len(accepted),2)

    def test_backup_rosters_cover_all_six_priority_markets(self):
        for market in ('HK','TW','JP','KR','AU','US'):
            sources=E['_bundled_listing_sources'](market)
            self.assertTrue(sources)
            self.assertGreater(sum(row['count'] for row in sources.values()),1000)
            for row in sources.values():
                self.assertTrue(row['url'].startswith('https://'))
                self.assertTrue(row['snapshot_asof'])

    def test_bloomberg_discovery_checks_broader_fields_for_new_hk_and_global_names(self):
        target='3986 HK Equity';names=['3223 HK Equity','9976 HK Equity','000660 KS Equity']
        base=electronics(BICS_LEVEL_3_INDUSTRY_NAME='Semiconductors')
        refs={target:base}
        refs.update({t:dict(base,BICS_LEVEL_4_SUB_INDUSTRY_NAME='Different subindustry '+str(i),
                           GICS_SUB_INDUSTRY_NAME='Different subindustry '+str(i)) for i,t in enumerate(names)})
        requests=[]
        def reference(session,tickers,fields,**kwargs):
            requests.extend(tickers)
            if 'GICS_SECTOR_NAME' in fields:
                self.assertIn('GICS_INDUSTRY_GROUP_NAME',fields)
                self.assertIn('BICS_LEVEL_2_INDUSTRY_GROUP_NAME',fields)
            return {t:refs.get(t,{}) for t in tickers}
        fn=E['auto_discover_universe'];meta={}
        stubs={'bbg_ref_multi':reference,'bbg_bulk':lambda *a,**k:[],
            '_public_equity_universe':lambda *a:(names[:2],[]),
            '_index_members':lambda *a:('TEST Index',[target,names[2]]),
            '_sector_index_members':lambda *a:([],[])}
        with patch.dict(fn.__globals__,stubs),contextlib.redirect_stdout(io.StringIO()):
            found=fn(None,target,min_mktcap_usd_mm=0,meta=meta)
        self.assertTrue(set(names)<=set(found))
        self.assertTrue(set(names)<=set(meta['peer_tickers']))
        for ticker in names: self.assertEqual(requests.count(ticker),1)

    def test_full_download_merges_price_requests_across_hk_aliases_and_force_fields(self):
        target='3986 HK Equity';requested=[]
        def history(session,names,start,end):
            requested.append(list(names))
            return pd.DataFrame(100.,index=pd.bdate_range('2026-10-01',periods=10),columns=names)
        metadata=dict(mktcap_usd_mm={},mktcap_hist=pd.DataFrame(),mktcap_hist_audit={},
                      execution_snapshot={},execution_data_audit={},execution_snapshot_date='20261028')
        fn=E['_download_hedge_data_impl']
        with patch.dict(fn.__globals__,{'bbg_hist':history,'_download_quote_metadata':lambda *a:metadata}),contextlib.redirect_stdout(io.StringIO()):
            out=fn(target,candidates=['03223 HK Equity','3223 HK Equity','9976 HK Equity'],
                   force_download=['09976 HK Equity'],session=object(),cache=False,
                   fetch_pit_members=False,fetch_mktcap_hist=False,download_window='3m')
        self.assertEqual(requested,[[target,'3223 HK Equity','9976 HK Equity']])
        self.assertEqual(out['fingerprint']['download_window'],'3m')

    def test_hk_alias_dedup_does_not_destroy_korean_or_taiwan_identifiers(self):
        self.assertEqual(E['_fmt_bbg_ticker']('03223 hk equity'),'3223 HK Equity')
        self.assertEqual(E['_fmt_bbg_ticker']('000660 KS Equity'),'000660 KS Equity')
        self.assertEqual(E['_fmt_bbg_ticker']('0050 TT Equity'),'0050 TT Equity')
        self.assertEqual(len(E['_parse_ticker_list'](['03223 HK Equity','3223 HK Equity'])),1)
        calls=[]
        def ref(session,names,fields,**kwargs):
            calls.append(names);return {t:electronics() for t in names}
        fn=E['_discovery_references']
        with patch.dict(fn.__globals__,{'bbg_ref_multi':ref}):
            fn(None,['03223 HK Equity','3223 HK Equity','000660 KS Equity'],['NAME'],[])
        self.assertEqual(calls,[['3223 HK Equity','000660 KS Equity']])

    def test_download_dates_use_calendar_months(self):
        fn=E['_download_date_range']
        self.assertEqual(fn(download_window='3m',today='2026-10-28'),('20261028','20260728'))
        self.assertEqual(fn(download_window='6m',today='2026-10-28'),('20261028','20260428'))
        with self.assertRaises(ValueError): fn(download_window='0m')

    def test_known_korean_holiday_carries_mark_and_preserves_reopening_move(self):
        dates=pd.bdate_range('2026-10-02','2026-10-14')
        s=pd.Series(100.+np.arange(len(dates)),index=dates)
        s.loc['2026-10-05']=np.nan;s.loc['2026-10-09']=np.nan
        p=pd.DataFrame({'000660 KS Equity':s})
        out,audit=E['_carry_scheduled_closures'](p)
        self.assertEqual(out.loc['2026-10-05'].iloc[0],out.loc['2026-10-02'].iloc[0])
        self.assertEqual(out.loc['2026-10-09'].iloc[0],out.loc['2026-10-08'].iloc[0])
        self.assertAlmostEqual(np.log(out/out.shift()).loc['2026-10-06'].iloc[0],np.log(102/100))
        self.assertEqual(audit[0]['count'],2)
        pd.testing.assert_series_equal(p.iloc[:,0],s,check_names=False)

    def test_calendar_ranges_may_start_or_end_on_non_sessions(self):
        for name in ('XHKG','XTAI','XKRX','XTKS','XASX','XNYS'):
            days=E['_calendar_sessions'](name,'2024-01-01','2024-06-30')
            self.assertGreater(len(days),100)
            self.assertGreaterEqual(days.min(),pd.Timestamp('2024-01-01'))
            self.assertLessEqual(days.max(),pd.Timestamp('2024-06-30'))

    def test_price_progress_counts_only_unique_requests_and_keeps_missing_names(self):
        calls=[];states=[]
        def history(session,names,*args):
            calls.extend(names)
            return pd.DataFrame(100.,index=pd.bdate_range('2026-01-01',periods=5),columns=[t for t in names if not t.startswith('MISS')])
        names=[f'{i} HK Equity' for i in range(1,102)]+['00001 HK Equity','MISS HK Equity']
        fn=E['_download_price_batches']
        with patch.dict(fn.__globals__,{'bbg_hist':history}):
            prices=fn(None,names,'20260101','20261028',lambda *a,**k:states.append((a,k)))
        self.assertEqual(len(calls),102);self.assertEqual(len(set(calls)),102)
        self.assertEqual(prices.attrs['price_download_audit']['missing'],['MISS HK Equity'])
        self.assertIn('102/102 unique tickers processed',states[-1][0][1])
        self.assertEqual(states[-1][1]['status'],'done')

    def test_download_inventory_categories_are_disjoint_and_display_concrete_names(self):
        from test_pca_market_controls import global_fixture
        d,local,foreign=global_fixture()
        rows=E['_download_inventory'](d)
        self.assertEqual(sum(r['count'] for r in rows),d['prices'].shape[1])
        self.assertEqual(sum(foreign in r['tickers'] for r in rows),1)
        row=next(r for r in rows if foreign in r['tickers'])
        self.assertEqual(row['category'],'Global industry/group peers')
        tracker=E['_DownloadProgress'](d['target'],lambda state:None,io.StringIO())
        tracker.finish('details',d)
        html=E['_download_progress_html'](tracker.state)
        self.assertIn('WHAT WAS DOWNLOADED',html)
        self.assertIn(foreign,html)

    def test_open_day_gap_pre_ipo_and_suspension_are_never_filled(self):
        dates=pd.bdate_range('2026-10-02','2026-10-14')
        p=pd.DataFrame({'000660 KS Equity':[np.nan,np.nan,102,103,np.nan,np.nan,106,107,108]},index=dates)
        out,_=E['_carry_scheduled_closures'](p)
        self.assertTrue(out.loc['2026-10-05'].isna().all())
        self.assertTrue(out.loc['2026-10-08':'2026-10-09'].isna().to_numpy().all())
        q=p.copy();q.iloc[-1]=np.nan
        a,_=E['_carry_scheduled_closures'](q)
        pd.testing.assert_frame_equal(a.iloc[:-1],out.iloc[:-1])

    def test_korean_peer_is_searched_after_scheduled_closures_but_real_gap_excludes(self):
        d=fixture(n=130);target='3986 HK Equity';korean='000660 KS Equity'
        d['prices']=d['prices'].rename(columns={d['target']:target,list(d['prices'])[3]:korean})
        d['prices'].index=pd.bdate_range(end='2026-10-28',periods=130)
        peers=[korean]+list(d['prices'])[4:]
        d.update(target=target,peer_tickers_by_target={target:peers},sector_stock_tickers_by_target={target:[]},
                 sector_scope_policy_version=1,peer_discovery_by_target={target:{}},
                 factor_tickers_by_target={},sector_tickers_by_target={})
        ks=E['_calendar_sessions']('XKRX',d['prices'].index[0],d['prices'].index[-1])
        d['prices'].loc[~d['prices'].index.isin(ks),korean]=np.nan
        with contextlib.redirect_stdout(io.StringIO()):
            r=E['find_best_hedge'](target,data=d,**dict(OPTIONS,sample_window='1m',candidate_scope='related',restrict_to_target_tz=False))
        audit=max(r['joint_search_audit'],key=lambda a:a['rows'])
        self.assertIn(korean,audit['eligible_tickers'])
        self.assertTrue(any(a.get('ticker')==korean for a in r['market_calendar_audit']))
        d['prices'].loc['2026-10-20',korean]=np.nan
        with contextlib.redirect_stdout(io.StringIO()):
            q=E['find_best_hedge'](target,data=d,**dict(OPTIONS,sample_window='1m',candidate_scope='related',restrict_to_target_tz=False))
        excluded=max(q['joint_search_audit'],key=lambda a:a['rows'])['eligibility_exclusions']
        reason=next(x for x in excluded if x['ticker']==korean)
        self.assertIn('2026-10-20',reason['missing_return_dates'])
        self.assertLess(reason['valid_training_rows'],reason['required_training_rows'])

    def test_new_ipo_one_year_cache_can_be_used_for_one_month(self):
        d=fixture(n=260);old=d['target'];target='3986 HK Equity';new='9976 HK Equity'
        d['prices']=d['prices'].rename(columns={old:target,list(d['prices'])[3]:new})
        d['prices'].index=pd.bdate_range(end='2026-10-28',periods=260)
        peers=[new]+list(d['prices'])[4:]
        d['prices'].loc[:'2026-09-07',new]=np.nan
        d.update(target=target,peer_tickers_by_target={target:peers},factor_tickers_by_target={},sector_tickers_by_target={})
        with contextlib.redirect_stdout(io.StringIO()):
            r=E['find_best_hedge'](target,data=d,**dict(OPTIONS,sample_window='1m',force_include=[new],restrict_to_target_tz=False))
        self.assertIn(new,r['weights'])
        self.assertTrue(d['prices'].loc[:'2026-09-07',new].isna().all())

    def test_factor_before_after_uses_same_fitted_dates_and_covariance(self):
        d=fixture(n=60);target=d['target']
        with contextlib.redirect_stdout(io.StringIO()):
            r=E['find_best_hedge'](target,data=d,**dict(OPTIONS,sample_window='1m',hedge_objective='factor',estimator_policy='factor'))
        a=r['common_exposures'];m=r['current_fit']['common_model'];w=r['weights']
        before=m['loadings'][:,m['columns'].index(target)]
        after=before-m['loadings'][:,[m['columns'].index(t) for t in w.index]]@w.to_numpy()
        v0=np.var(m['factors']@before);v1=np.var(m['factors']@after)
        self.assertAlmostEqual(a['common_variance_before'],v0)
        self.assertAlmostEqual(a['common_variance_after'],v1)
        self.assertAlmostEqual(a['common_vol_reduction'],1-np.sqrt(v1/v0))
        self.assertIn('FACTOR EXPOSURE — BEFORE AND AFTER HEDGING',r['report_text'])
        self.assertIn('CHANGE',r['report_text'])
        self.assertEqual(r['selected_estimator'],'factor')
        html=E['_report_html'](r)
        self.assertIn('href="#factor-exposure-before-and-after-hedging"',html)
        self.assertLess(r['report_text'].index('FACTOR EXPOSURE'),r['report_text'].index('UNIVERSE COVERAGE'))

if __name__=='__main__': unittest.main()
