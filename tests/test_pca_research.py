"""Offline checks of the v116 production engine, including chronological isolation."""
import contextlib,io,os,runpy,unittest,json,tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
os.environ.setdefault('MPLBACKEND','Agg')
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent if HERE.name=='tests' else HERE
SCRIPT=ROOT/'pca_hedge_v115_peer_pca_diagnostics.py'
if not SCRIPT.exists(): SCRIPT=ROOT/'PCA_fixed.py'
with contextlib.redirect_stdout(io.StringIO()):
    E=runpy.run_path(str(SCRIPT),init_globals={'HEDGE_UI_AUTOSTART':False})

def fixture(n=420,seed=12):
    rng=np.random.default_rng(seed)
    market,sector=rng.normal(0,.01,(2,n)); common=.7*market+.5*sector
    names=['2889 TT Equity','0050 TT Equity','0055 TT Equity']+[f'{2900+i} TT Equity' for i in range(7)]
    r=np.column_stack([common+rng.normal(0,.004,n),market,market+sector]+[common+rng.normal(0,.006,n) for _ in range(7)])
    return {'target':names[0],'prices':pd.DataFrame(100*np.exp(r.cumsum(0)),index=pd.bdate_range('2024-01-01',periods=n),columns=names),
        'price_observations':'ACTIVE_DAYS_ONLY','peer_policy_version':3,'peer_tickers_by_target':{names[0]:names[3:]},
        'factor_tickers_by_target':{names[0]:['0055 TT Equity']},'sector_tickers_by_target':{names[0]:['0055 TT Equity']}}
OPTIONS=dict(show_plots=False,rolling_oos=False,boot_n=0,min_mktcap_usd_mm=0,
             basket_size_options=(3,),alternative_baskets=3,max_gross=2,max_leg=1)
def run(data=None,**kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return E['find_best_hedge']('2889 TT Equity',data=data or fixture(),**dict(OPTIONS,**kw))

class ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=fixture();cls.one=run(cls.data,sample_window='1m');cls.three=run(cls.data,sample_window='3m')

    def test_actual_revision_loaded(self):
        self.assertIn('v116',E['PCA_REVISION'])

    def test_short_window_search_has_multiple_distinct_baskets(self):
        rows=self.one['basket_comparison']
        self.assertGreaterEqual(len(rows),4)
        self.assertEqual(len(rows),len({tuple(sorted(r['weights'].index)) for r in rows}))
        self.assertGreater(self.one['joint_search_audit'][-1]['surrogate_subsets'],1)

    def test_all_five_windows_run_and_use_selected_end(self):
        for period in ('1m','2m','3m','6m','1y'):
            r=run(self.data,sample_window=period)
            self.assertEqual(r['returns'].index[-1],self.data['prices'].index[-1])
            self.assertTrue(np.isfinite(r['in_sample_r2']))
            self.assertEqual(r['params']['sample_window'],period)
            self.assertGreaterEqual(len(r['weights']),2)

    def test_holdout_refit_retains_untouched_validation_result(self):
        r=self.three
        self.assertEqual(r['validation_mode'],'HOLDOUT')
        self.assertGreater(len(r['returns']),len(r['validation_fit_returns']))
        changed=fixture()
        prices=changed['prices']; ret=np.log(prices/prices.shift())
        # Modify only held-out prices, preserving every training bit exactly.
        prices.iloc[-12:,0]*=np.exp((.003-1.8*ret.iloc[-12:,0]).cumsum())
        q=run(changed,sample_window='3m')
        pd.testing.assert_series_equal(r['validation_weights'],q['validation_weights'])
        self.assertNotAlmostEqual(r['holdout_r2'],q['holdout_r2'])
        self.assertGreater(float((r['weights'].reindex(q['weights'].index,fill_value=0)-q['weights']).abs().sum()),1e-5)

    def test_current_r2_equals_actual_current_predictions(self):
        r=self.three; f=r['returns']; y=f['2889 TT Equity']; spread=y-f[r['weights'].index]@r['weights']
        expected=1-float(((spread-spread.mean())**2).sum()/((y-y.mean())**2).sum())
        self.assertAlmostEqual(r['in_sample_r2'],expected)
        self.assertAlmostEqual(r['current_fit_risk']['vol_reduction'],1-spread.std()/y.std())

    def test_factor_model_excludes_target_from_pca(self):
        frame=np.log(self.data['prices']/self.data['prices'].shift()).dropna().iloc[-60:]
        peers=self.data['peer_tickers_by_target']['2889 TT Equity']
        a=E['_common_risk_model'](frame,'2889 TT Equity',peers,['0050 TT Equity','0055 TT Equity'])
        frame['2889 TT Equity']*=20
        b=E['_common_risk_model'](frame,'2889 TT Equity',peers+['2889 TT Equity'],['0050 TT Equity','0055 TT Equity'])
        np.testing.assert_allclose(a['factors'],b['factors'])
        self.assertTrue(np.linalg.eigvalsh(a['covariance']).min()>0)

    def test_common_risk_reduction_uses_covariance_not_loading_norm(self):
        r=self.one; a=r['common_exposures']
        before=np.array([v[1] for v in a['rows']]);after=np.array([v[2] for v in a['rows']])
        self.assertAlmostEqual(a['common_variance_reduction'],1-after@after/(before@before))

    def test_constraints_apply_to_current_and_alternative_weights(self):
        r=run(sample_window='1m',max_gross=.4,max_leg=.2)
        for w in [r['weights']]+[x['weights'] for x in r['basket_comparison']]:
            self.assertLessEqual(w.abs().sum(),.4000001)
            self.assertLessEqual(w.abs().max(),.2000001)

    def test_exact_size_and_required_names(self):
        r=run(sample_window='2m',basket_size_range=(4,4),force_include=['2901 TT'])
        self.assertEqual(len(r['weights']),4)
        self.assertIn('2901 TT Equity',r['weights'])
        for row in r['basket_comparison']:
            self.assertEqual(len(row['weights']),4)
            self.assertIn('2901 TT Equity',row['weights'])

    def test_exclusion_and_same_exchange_apply_to_every_recipe(self):
        d=fixture();d['prices']['FOREIGN US Equity']=d['prices']['2901 TT Equity']
        d['peer_tickers_by_target'][d['target']].append('FOREIGN US Equity')
        r=run(d,sample_window='1m',exclude=['2901'],same_exchange_only=True)
        for w in [r['weights']]+[x['weights'] for x in r['basket_comparison']]:
            self.assertNotIn('2901 TT Equity',w)
            self.assertTrue(all(' TT ' in n for n in w.index))

    def test_keyword_does_not_match_inside_environmental(self):
        self.assertEqual(E['_exposure_tags']('Environmental & Facilities Services'),set())
        self.assertIn('BASE_METALS',E['_exposure_tags']('Iron & Steel'))
        self.assertIn('RATES',E['_exposure_tags']('Utilities'))

    def test_strict_peers_reject_network_only_and_unknown_industry(self):
        f='GICS_INDUSTRY_NAME'
        accepted,rejected,unknown=E['_strict_peer_set']({f:'Banks'},
            {'A':{f:'Banks'},'B':{f:'Shipping'},'C':{}},['A','B','C'])
        self.assertEqual(accepted,['A']);self.assertEqual(rejected,['B']);self.assertEqual(unknown,['C'])

    def test_legacy_cache_cannot_claim_verified_peers(self):
        d=fixture();d['peer_policy_version']=2
        with self.assertRaisesRegex(ValueError,'fresh v116 download'):
            run(d,sample_window='1m')
        r=run(d,sample_window='1m',peer_tickers=d['peer_tickers_by_target'][d['target']])
        self.assertTrue(len(r['weights'])>=2)

    def test_sector_etf_survives_focused_filter(self):
        self.assertIn('XLF US Equity',E['SECTOR_INSTRUMENTS'][('US','Financials')])
        d={'peer_policy_version':3,'peer_tickers_by_target':{'JPM US Equity':['BAC US Equity']},
           'factor_tickers_by_target':{'JPM US Equity':E['SECTOR_INSTRUMENTS'][('US','Financials')]}}
        names=['JPM US Equity','BAC US Equity','XLF US Equity','SPY US Equity']
        kept=E['_filter_candidate_scope'](d,['JPM US Equity'],names,'focused',True)
        self.assertIn('XLF US Equity',kept['columns'])

    def test_mislabeled_japanese_bond_is_not_jgb_proxy(self):
        self.assertNotIn('1482 JT Equity',E['MARKET_INSTRUMENTS'].get(('JP','RATES'),[]))

    def test_market_audit_allowed_without_market_hedge_candidate(self):
        r=run(sample_window='2m',candidate_scope='peers',include_broad_market=False)
        self.assertNotIn('0050 TT Equity',r['weights'])
        self.assertTrue(any('0050' in row[0] for row in r['common_exposures']['rows']))

    def test_negative_tracking_is_not_automatic_variance_failure(self):
        grade,_=E['_ticket_verdict'](-.2,-.2,.1,None,False,np.nan,np.nan,False,
                                    vol_red=.3,worst_vol_red=.2,objective='factor')
        self.assertFalse(grade.startswith('✗'))

    def test_no_test_observations_do_not_get_trade_weights(self):
        self.assertFalse(self.one['trade_eligible'])
        self.assertTrue(self.one['trade_weights'].empty)

    def test_missing_borrow_is_unknown_not_passed(self):
        rows=self.one['execution_audit']['rows']
        self.assertTrue(any(row['borrow']=='unknown' for row in rows))
        self.assertFalse(self.one['execution_audit']['order_ready'])

    def test_in_sample_label_and_latest_fit_dates_in_report(self):
        blocks=E['_report_blocks'](self.three)
        text=str(blocks)
        self.assertIn('Raw in-sample R²',text)
        self.assertIn('Current fit',text)
        self.assertIn('Alternative baskets',text)
        self.assertIn('Single instrument references',text)
        self.assertNotIn('independent statistical directions',text)

    def test_report_is_printed(self):
        buf=io.StringIO()
        with contextlib.redirect_stdout(buf):
            E['_render_compact_report'](self.one)
        self.assertIn('CURRENT BASKET',buf.getvalue())
        self.assertIn('IN-SAMPLE',buf.getvalue())

    def test_printed_metrics_match_fit_and_unseen_risk_and_preserve_positions(self):
        r=self.three
        buf=io.StringIO()
        with contextlib.redirect_stdout(buf):
            E['_render_compact_report'](r)
        printed=buf.getvalue()
        fitted=printed.split('CURRENT FIT MEASURE',1)[1].split('MARKET SECTOR',1)[0]
        unseen=printed.split('HISTORICAL TEST MEASURE',1)[1].split('WEIGHT SENSITIVITY',1)[0]
        for output,risk in [(fitted,r['current_fit_risk']),(unseen,r['trade_risk'])]:
            for key in ('unhedged_vol_ann','hedged_vol_ann','vol_reduction'):
                self.assertIn(f"{risk[key]*100:.1f}%",output)
        self.assertIn(f"{r['in_sample_r2']:.3f}",fitted)
        self.assertIn(f"{r['ticket']['quality_r2']:.3f}",unseen)
        alternatives=printed.split('ALTERNATIVE BASKETS',1)[1].split('SINGLE INSTRUMENT REFERENCES',1)[0]
        for row in r['basket_comparison']:
            if row['selected']: continue
            for ticker,weight in row['weights'].items():
                position=f"{'SHORT' if weight>0 else 'LONG'} ${abs(weight)*100:.1f} {ticker}"
                self.assertTrue(any(position in ' '.join(line.split()) for line in alternatives.splitlines()),position)
        self.assertIn('not total stock risk',printed)

    def test_complementary_pair_beats_top_individuals(self):
        rng=np.random.default_rng(40);n=80
        common,factor=rng.normal(0,.01,(2,n))
        f=pd.DataFrame({'y':factor+rng.normal(0,.0001,n),'a':4*common+factor,'b':4*common-factor,
            'c':factor+rng.normal(0,.008,n),'d':factor+rng.normal(0,.009,n),'e':factor+rng.normal(0,.010,n)})
        recipes,audit=E['_joint_basket_search'](f,'y',list(f.columns[1:]),(3,),keep=4)
        self.assertTrue({'a','b'}<=set(recipes[3][0]['basket']))
        self.assertGreater(recipes[3][0]['fit'][1],.99)
        self.assertEqual(audit['surrogate_subsets'],10)

    def test_covariance_objective_handles_collinearity(self):
        f=np.log(self.data['prices']/self.data['prices'].shift()).dropna().iloc[-40:]
        f['copy']=f['0050 TT Equity']
        m=E['_common_risk_model'](f,'2889 TT Equity',[],['0050 TT Equity','copy','0055 TT Equity'])
        self.assertEqual(len(m['labels']),2)
        fit,_,_=E['_fit_common_risk'](f,'2889 TT Equity',['0050 TT Equity','copy'],m,2,1)
        self.assertTrue(np.isfinite(fit.coef_).all())

    def test_short_full_protocol_lookback_is_not_silently_all_skipped(self):
        tier=E['_validation_tier'](130,(40,),10,2,10,2,0,(3,),21)
        self.assertLessEqual(tier['min_train_rows'],40)

    def test_nan_taxonomy_is_not_industry_agreement(self):
        for value in (None,np.nan,'','N/A','unknown'):
            self.assertFalse(E['_peer_industry_supported']({'GICS_INDUSTRY_NAME':value},{'GICS_INDUSTRY_NAME':value}))

    def test_registry_sources_union_and_failures_are_reported(self):
        responses=[io.BytesIO(json.dumps([{'公司代號':'2889'}]).encode()),
                   io.BytesIO(json.dumps([{'SecuritiesCompanyCode':'5864'}]).encode())]
        with patch('urllib.request.urlopen',side_effect=responses):
            names,audit=E['_public_equity_universe']('TW')
        self.assertEqual(names,['2889 TT Equity','5864 TT Equity'])
        self.assertTrue(all(r['status']=='received' for r in audit))
        with patch('urllib.request.urlopen',side_effect=OSError('offline')):
            names,audit=E['_public_equity_universe']('TW')
        self.assertFalse(names);self.assertEqual(len(audit),2)
        self.assertTrue(all(r['status']=='unavailable' for r in audit))

    def test_registry_malformed_schema_is_not_silently_partial(self):
        with patch('urllib.request.urlopen',side_effect=[io.BytesIO(b'[{"changed":"2889"}]'),OSError('offline')]):
            names,audit=E['_public_equity_universe']('TW')
        self.assertEqual(names,[]);self.assertEqual(audit[0]['status'],'unavailable')

    def test_partial_roster_download_retries_once_then_reports_failure(self):
        from http.client import IncompleteRead
        good=io.BytesIO(b'[{"SecuritiesCompanyCode":"5864"}]')
        with patch('urllib.request.urlopen',side_effect=[IncompleteRead(b'a'),IncompleteRead(b'b'),good]) as fetch:
            names,audit=E['_public_equity_universe']('TW')
        self.assertEqual(fetch.call_count,3)
        self.assertEqual(names,['5864 TT Equity'])
        self.assertEqual(audit[0]['status'],'unavailable')

    def test_hk_roster_excludes_derivatives_and_duplicate_rmb_counter(self):
        f=pd.DataFrame([['Updated as at 2026-10-14','','','',''],
            ['Stock Code','Name of Securities','Category','Sub-Category','Trading Currency'],
            ['00700','Tencent','Equity','Equity Securities (Main Board)','HKD'],
            ['80700','Tencent RMB','Equity','Equity Securities (Main Board)','CNY'],
            ['12345','Warrant','Derivative Warrants','Warrants','HKD']])
        buffer=io.BytesIO();f.to_excel(buffer,index=False,header=False)
        names,audit=E['_parse_public_roster']('HKEX',buffer.getvalue())
        self.assertEqual(names,['700 HK Equity']);self.assertEqual(audit['excluded_non_equity'],2)
        self.assertEqual(audit['industry_count'],0)

    def test_japan_roster_includes_alphanumeric_codes_excludes_etf(self):
        f=pd.DataFrame([['130A','Company','グロース（内国株式）','医薬品','20260930'],
                        ['1306','Fund','ETF・ETN','-','20260930']],
                       columns=['コード','銘柄名','市場・商品区分','33業種区分','日付'])
        buffer=io.BytesIO();f.to_excel(buffer,index=False)
        names,audit=E['_parse_public_roster']('JPX',buffer.getvalue())
        self.assertEqual(names,['130A JP Equity'])
        self.assertEqual(audit['industries']['130A JP Equity'],'医薬品')

    def test_asx_roster_preserves_digit_codes_and_missing_classification(self):
        payload=b'ASX listed companies as at today\n\nCompany name,ASX code,GICS industry group\n14D,14D,Capital Goods\nUnknown,ZZZ,Not Applic\n'
        names,audit=E['_parse_public_roster']('ASX',payload)
        self.assertEqual(names,['14D AU Equity','ZZZ AU Equity'])
        self.assertEqual(audit['industry_count'],1)

    def test_korea_roster_preserves_zeroes_excludes_konex(self):
        f=pd.DataFrame([['Samsung','유가','005930','반도체 제조업'],['Other','코스닥','086520','화학'],
                        ['New','코스닥','0035S0','화학'],['Small','코넥스','000001','화학']],columns=['회사명','시장구분','종목코드','업종'])
        names,audit=E['_parse_public_roster']('KRX KIND',f.to_html(index=False).encode('euc-kr'))
        self.assertEqual(names,['0035S0 KS Equity','005930 KS Equity','086520 KS Equity'])
        self.assertEqual(audit['industry_count'],3)

    def test_us_roster_excludes_funds_test_issues_and_warrants(self):
        payload=('ACT Symbol|Security Name|ETF|Test Issue\n'
                 'BRK.B|Berkshire Class B Common Stock|N|N\n'
                 'SPY|SPDR ETF|Y|N\nTEST|Test Common Stock|N|Y\n'
                 'ABC.W|ABC Warrants|N|N\nZZ|ZZ Preferred Stock|N|N\n'
                 'BAD.$|Unmapped Common Stock|N|N\nFile Creation Time: today|||\n').encode()
        names,audit=E['_parse_public_roster']('Other US exchanges',payload)
        self.assertEqual(names,['BRK/B US Equity'])
        self.assertEqual(audit['unmapped_identifiers'],['BAD.$'])
        self.assertEqual(audit['source_date'],'File Creation Time: today')

    def test_independent_industry_crosscheck_is_review_only_and_unions_taiwan(self):
        sources=[{'status':'received','industry_scheme':'TW exchange industry',
                  'industries':{'2889 TT Equity':'17','2890 TT Equity':'17'}},
                 {'status':'received','industry_scheme':'TW exchange industry',
                  'industries':{'5864 TT Equity':'17','1234 TT Equity':'1'}}]
        rows=E['_independent_peer_crosscheck']('2889 TT Equity',sources,['2890 TT Equity','1234 TT Equity'])
        self.assertEqual(rows[0]['needs_review'],['5864 TT Equity'])
        self.assertEqual(rows[0]['verified_different_category'],['1234 TT Equity'])
        self.assertEqual(sources[0]['industries']['2889 TT Equity'],'17')

    def test_unknown_labels_cannot_enter_through_alternative_taxonomy_path(self):
        target='2889 TT Equity';candidate='9999 TT Equity'
        ref={'COUNTRY_ISO':'TW','GICS_SECTOR_NAME':'Financials','GICS_INDUSTRY_NAME':'unknown',
             'BICS_LEVEL_2_INDUSTRY_GROUP_NAME':'N/A'}
        overrides={'bbg_ref_single':lambda *a:ref,
            'bbg_ref_multi':lambda session,names,*a,**k:{t:ref for t in names},'bbg_bulk':lambda *a:[],
            '_public_equity_universe':lambda market:([candidate],[]),
            '_index_members':lambda *a:('TEST Index',[target]),'_sector_index_members':lambda *a:([],[])}
        meta={}
        with patch.dict(E['auto_discover_universe'].__globals__,overrides),contextlib.redirect_stdout(io.StringIO()):
            E['auto_discover_universe'](None,target,min_mktcap_usd_mm=0,meta=meta)
        self.assertNotIn(candidate,meta['peer_tickers'])
        self.assertIn(candidate,meta['classification_missing'])

    def test_discovery_reaches_non_index_peers_and_rejects_bad_links(self):
        target='2889 TT Equity';good='5864 TT Equity';bad='2637 TT Equity'
        bank={'COUNTRY_ISO':'TW','GICS_SECTOR_NAME':'Financials','GICS_INDUSTRY_NAME':'Banks'}
        refs={target:bank,good:bank,bad:{'GICS_INDUSTRY_NAME':'Marine Transportation'}}
        def multi(session,names,fields,**kw): return {t:refs.get(t,{}) for t in names}
        def bulk(session,ticker,field): return [{'Peer Ticker':bad}] if ticker==target else []
        overrides={'bbg_ref_single':lambda *a:bank,'bbg_ref_multi':multi,'bbg_bulk':bulk,
            '_public_equity_universe':lambda market:([good],[{'source':'mock official roster','status':'received','count':1}]),
            '_index_members':lambda *a:('TEST Index',[target]),'_sector_index_members':lambda *a:([],[])}
        meta={}
        with patch.dict(E['auto_discover_universe'].__globals__,overrides),contextlib.redirect_stdout(io.StringIO()):
            universe=E['auto_discover_universe'](None,target,min_mktcap_usd_mm=0,meta=meta)
        self.assertIn(good,universe);self.assertIn(good,meta['peer_tickers'])
        self.assertNotIn(bad,meta['peer_tickers']);self.assertIn(bad,meta['taxonomy_rejected'])
        self.assertIn(good,meta['non_index_shorts']);self.assertNotIn('5864',meta['non_index_shorts'])

    def test_eqs_request_and_nested_response(self):
        from unittest.mock import MagicMock
        class Element:
            def __init__(self,name,value): self.key,self.value=name,value
            def name(self): return self.key
            def isArray(self): return isinstance(self.value,list)
            def isComplexType(self): return isinstance(self.value,dict)
            def numValues(self): return len(self.value)
            def numElements(self): return len(self.value)
            def getValueAsElement(self,i): return self.value[i]
            def getElement(self,i): return list(self.value.values())[i]
            def getValueAsString(self): return self.value
        root=Element('response',{'data':Element('securityData',[Element('row',{'sec':Element('security','2889 TT Equity')})])})
        session=MagicMock();message=MagicMock();message.hasElement.return_value=False;message.asElement.return_value=root
        with patch.dict(E['bbg_screen_universe'].__globals__,{'_drain_events':lambda session,fn:fn(message)}):
            names=E['bbg_screen_universe'](session,'My local equities')
        self.assertEqual(names,['2889 TT Equity'])
        session.getService.return_value.createRequest.assert_called_with('BeqsRequest')
        session.getService.return_value.createRequest.return_value.set.assert_any_call('screenName','My local equities')
        message.hasElement.return_value=True
        with patch.dict(E['bbg_screen_universe'].__globals__,{'_drain_events':lambda session,fn:fn(message)}):
            with self.assertRaisesRegex(RuntimeError,'EQS screen failed'): E['bbg_screen_universe'](session,'Missing')

    def test_full_report_uses_current_weights_and_dates(self):
        r=run(sample_window='3m',report='full')
        self.assertIn('CURRENT BASKET',r['report_text'])
        self.assertIn('DETAILED VALIDATION CONFIGURATION',r['report_text'])
        self.assertIn(r['current_fit']['fit_end'].strftime('%d %b %Y'),r['report_text'])
        pd.testing.assert_series_equal(r['weights'],self.three['weights'])

    def test_direct_download_path_keeps_metadata_for_report(self):
        with patch.dict(E['find_best_hedge'].__globals__,{'download_hedge_data':lambda *a,**kw:fixture()}),contextlib.redirect_stdout(io.StringIO()):
            r=E['find_best_hedge']('2889 TT Equity',session=object(),sample_window='1m',**OPTIONS)
        self.assertIn('2889 TT Equity',r['peer_coverage'])
        self.assertEqual(r['peer_pca_diagnostics']['status'],'ok')

    def test_confirmed_borrow_failure_is_not_eligible(self):
        d=fixture();d['borrow_available']={t:False for t in d['prices']}
        r=run(d,sample_window='3m')
        self.assertEqual(r['recommended_action'],'BORROW_UNAVAILABLE')
        self.assertFalse(r['trade_eligible']);self.assertTrue(r['trade_weights'].empty)

    def test_complete_window_has_one_selected_alternative(self):
        for r in (self.one,self.three):
            chosen=[b for b in r['basket_comparison'] if b['selected']]
            self.assertEqual(len(chosen),1)
            pd.testing.assert_series_equal(chosen[0]['weights'],r['weights'])

    def test_optional_comparison_preserves_selected_window(self):
        with contextlib.redirect_stdout(io.StringIO()):
            comp=E['compare_history_windows'](self.data['target'],self.data,windows=('1m','2m','3m'),**OPTIONS)
        self.assertEqual(list(comp['summary']['period']),['1m','2m','3m'])
        self.assertFalse(comp['errors'])
        self.assertEqual(self.three['params']['sample_window'],'3m')

    def test_zero_variance_target_fails_explaining_data(self):
        d=fixture();d['prices'].iloc[:,0]=100
        with self.assertRaisesRegex((ValueError,RuntimeError),'(?i)(variance|constant|flat|stale|valid|eligible|usable|target)'):
            run(d,sample_window='1m')

    def test_duplicate_dates_are_rejected(self):
        d=fixture();d['prices'].index=list(d['prices'].index[:-1])+[d['prices'].index[-2]]
        with self.assertRaisesRegex(ValueError,'duplicated'): run(d,sample_window='1m')

    def test_incomplete_candidate_does_not_erase_target_history(self):
        d=fixture();d['prices'].iloc[-19:,-1]=np.nan
        r=run(d,sample_window='1m')
        self.assertNotIn(d['prices'].columns[-1],r['weights'])
        self.assertEqual(r['current_fit_rows'],self.one['current_fit_rows'])

    def test_off_venue_factor_not_added_to_same_day_model(self):
        d=fixture();d['prices']['SPY US Equity']=d['prices']['0050 TT Equity']
        f=np.log(d['prices']/d['prices'].shift()).dropna().iloc[-30:].drop(columns=['SPY US Equity'])
        q=E['_with_reference_returns'](f,d,['SPY US Equity'],False,d['target'])
        self.assertNotIn('SPY US Equity',q)

    def test_market_factor_still_works_in_strict_peers_scope(self):
        d=fixture();d['factor_tickers_by_target']={};d['sector_tickers_by_target']={}
        r=run(d,sample_window='1m',candidate_scope='peers',include_broad_market=False)
        self.assertTrue(np.isfinite(r['in_sample_r2']))
        self.assertNotIn('0050 TT Equity',r['weights'])

    def test_full_nested_evaluation_is_chronological(self):
        opts=dict(sample_window='6m',lookback_options=(40,),cv_test_window=10,cv_n_folds=2,outer_window=10,outer_folds=2)
        a=run(**opts)
        d=fixture();d['prices'].iloc[-9:,0]*=np.linspace(1,1.2,9)
        b=run(d,**opts)
        self.assertEqual(a['validation_mode'],'FULL')
        pd.testing.assert_frame_equal(a['nested_validation'].sort_values('start').iloc[:1],b['nested_validation'].sort_values('start').iloc[:1])
        early=a['nested_unseen_returns'].index[:-10]
        pd.testing.assert_frame_equal(a['nested_unseen_returns'].loc[early],b['nested_unseen_returns'].loc[early])

    def test_ui_defaults_and_all_common_windows(self):
        with contextlib.redirect_stdout(io.StringIO()): state=E['hedge_ui'](self.data)
        w=state['widgets']
        self.assertEqual(w['objective'].value,'factor')
        self.assertEqual(w['basket_methods'].value,'search')
        self.assertEqual(w['compare_windows'].value,())
        self.assertEqual(w['max_leg'].value,1.)
        self.assertTrue({'1m','2m','3m','6m','1y'}<=set(v for label,v in w['analysis_window'].options))

    def test_quick_refit_keeps_position_caps(self):
        a=run(sample_window='1m',max_gross=.4,max_leg=.2)
        with contextlib.redirect_stdout(io.StringIO()):
            b=E['quick_rehedge'](self.data['target'],self.data,a,show_plots=False,rolling_oos=False)
        self.assertLessEqual(b['weights'].abs().sum(),.4000001)
        self.assertLessEqual(b['weights'].abs().max(),.2000001)

    def test_market_backup_proxies_do_not_displace_sector_factor(self):
        d=fixture(n=30); f=np.log(d['prices']/d['prices'].shift()).dropna().iloc[-20:]
        f['006204 TT Equity']=f['0050 TT Equity']+.01*f['2900 TT Equity']
        f['006208 TT Equity']=f['0050 TT Equity']+.01*f['2901 TT Equity']
        refs=['006204 TT Equity','0050 TT Equity','006208 TT Equity','0055 TT Equity']
        model=E['_common_risk_model'](f,d['target'],d['peer_tickers_by_target'][d['target']],refs)
        self.assertEqual(model['labels'],['006204 TT Equity','0055 TT Equity'])
        f['006204 TT Equity']=0.
        model=E['_common_risk_model'](f,d['target'],[],refs)
        self.assertEqual(model['labels'],['0050 TT Equity','0055 TT Equity'])

    def test_pinned_search_rule_runs_long_validation_and_quick_refit(self):
        r=run(self.data,sample_window='1y',pc_options=['search:1'],broad_search=False)
        self.assertEqual(r['params']['pc_spec'],'search:1')
        self.assertEqual(set(r['nested_validation']['pc_spec']),{'search:1'})
        with contextlib.redirect_stdout(io.StringIO()):
            q=E['quick_rehedge'](self.data['target'],self.data,r,show_plots=False,rolling_oos=False)
        self.assertEqual(q['params']['pc_spec'],'search:1')
        self.assertEqual(q['params']['basket_size'],r['params']['basket_size'])

    def test_pinned_short_recipe_is_not_replaced_by_search_winner(self):
        for spec in ('correlation','search:1'):
            r=run(sample_window='1m',pc_options=[spec],broad_search=False)
            self.assertEqual(r['params']['pc_spec'],spec)
            self.assertEqual(r['search']['configurations_scored'],1)

    def test_mixed_currency_result_cannot_supply_trade_weights(self):
        d=fixture(); names=list(d['prices'].columns)
        d['execution_snapshot']={n:dict(CRNCY='TWD' if n==d['target'] else 'USD',
            PX_BID=99,PX_ASK=100,AVERAGE_VOLUME_30D=1000000) for n in names}
        d['borrow_available']={n:True for n in names}
        r=run(d,sample_window='3m')
        self.assertEqual(r['execution_audit']['currency_status'],'mixed')
        self.assertFalse(r['trade_eligible']);self.assertTrue(r['trade_weights'].empty)
        self.assertEqual(r['recommended_action'],'FX_NORMALIZATION_REQUIRED')
        self.assertIn('not a common-currency portfolio return',str(E['_report_blocks'](r)))

    def test_currency_audit_does_not_assume_unknown_currency_matches(self):
        d={'execution_snapshot':{'target':{'CRNCY':'TWD'},'a':{'CRNCY':np.nan}}}
        r={'portfolio_legs':['target'],'weights':pd.Series({'a':.5})}
        self.assertEqual(E['_execution_audit'](r,d)['currency_status'],'unknown')
        d['execution_snapshot']['a']['CRNCY']='TWD'
        self.assertEqual(E['_execution_audit'](r,d)['currency_status'],'same')

    def test_constrained_risk_fit_matches_independent_grid_minimum(self):
        f=pd.DataFrame({'y':np.arange(20)*.001,'a':np.sin(np.arange(20))*.01,
                        'b':np.cos(np.arange(20))*.01})
        C=np.array([[1,.8,-.5],[.8,1,-.2],[-.5,-.2,1.]])
        model={'columns':list(f),'covariance':C,'labels':['market']}
        fit,_,_=E['_fit_common_risk'](f,'y',['a','b'],model,.6,.4)
        w=fit.coef_; self.assertGreater(w[0],0);self.assertLess(w[1],0)
        objective=lambda z: 1-2*z@C[1:,0]+z@C[1:,1:]@z
        grid=[objective(np.array([a,b])) for a in np.linspace(-.4,.4,101)
              for b in np.linspace(-.4,.4,101) if abs(a)+abs(b)<=.60000001]
        self.assertLessEqual(objective(w),min(grid)+1e-7)
        self.assertAlmostEqual(fit.risk_model_['expected_variance'],objective(w))

    def test_negative_unseen_r2_can_coexist_with_lower_spread_variance(self):
        x=np.linspace(-.01,.01,30);y=2*x+.1
        fit=E['_HedgeFit']([2],0)
        self.assertLess(fit.score(x[:,None],y),0)
        risk=E['_trade_risk'](y,y-2*x,np.sqrt(252))
        self.assertAlmostEqual(risk['vol_reduction'],1.)

    def test_listing_aliases_are_one_instrument_but_other_markets_remain_distinct(self):
        self.assertEqual(E['_ticker_key']('1306 JT Equity'),E['_ticker_key']('1306 JP Equity'))
        self.assertNotEqual(E['_ticker_key']('1306 JP Equity'),E['_ticker_key']('1306 TT Equity'))
        names=['7203 JP Equity','7203 JT Equity','1306 JP Equity','1306 JT Equity','1615 JT Equity']
        scope=E['_filter_candidate_scope']({},['7203 JP Equity'],names,'all',True)
        self.assertEqual(scope['columns'],['7203 JP Equity','1306 JP Equity','1615 JT Equity'])
        self.assertEqual(scope['alias_duplicates_removed'],['7203 JT Equity','1306 JT Equity'])

    def test_japanese_factor_aliases_resolve_to_observed_columns(self):
        rng=np.random.default_rng(9)
        f=pd.DataFrame(rng.normal(0,.01,(20,3)),columns=['7203 JP Equity','1306 JT Equity','1615 JP Equity'])
        refs=['1306 JP Equity','1615 JT Equity']
        m=E['_common_risk_model'](f,'7203 JP Equity',[],refs)
        self.assertEqual(m['labels'],['1306 JT Equity','1615 JP Equity'])
        d={'prices':100*np.exp(f.cumsum())}
        augmented=E['_with_reference_returns'](f.iloc[1:,[0]],d,refs,False,'7203 JP Equity')
        self.assertEqual(list(augmented),list(f))
        existing=E['_with_reference_returns'](f.iloc[1:],d,refs,False,'7203 JP Equity')
        self.assertEqual(list(existing),list(f))

    def test_chart_assets_are_created_from_latest_fit(self):
        figures=E['_report_figures'](self.three)
        self.assertGreaterEqual(len(figures),2)
        labels=[ax.get_title() for _,fig in figures for ax in fig.axes]
        self.assertIn('Current basket hedge weights',labels)
        for _,fig in figures: E['plt'].close(fig)

    def test_style_compatibility_filters_unsupported_rc_parameters(self):
        self.assertEqual(E['_supported_plot_style']({'axes.titlecolor':'red','font.size':10},{'font.size':12}),{'font.size':10})

    def test_large_universe_bounded_search_finishes_complete_baskets(self):
        rng=np.random.default_rng(42);f=rng.normal(size=(50,81))*.01
        f[:,1:]+=.6*f[:,[0]]
        frame=pd.DataFrame(f,columns=['y']+[f'p{i}' for i in range(80)])
        result,audit=E['_joint_basket_search'](frame,'y',list(frame.columns[1:]),(3,5),keep=2,budget=100)
        self.assertTrue(result[3]);self.assertTrue(result[5])
        self.assertEqual(audit['pairs_screened'],3160)
        self.assertFalse(audit['global_optimum_claimed'])

    def test_published_notebook_matches_script(self):
        nb=SCRIPT.with_suffix('.ipynb')
        if not nb.exists(): self.skipTest('Notebook is generated at publication')
        cells=json.loads(nb.read_text(encoding='utf-8'))['cells']
        code=''.join(''.join(c['source']) for c in cells if c['cell_type']=='code')
        self.assertEqual(code,SCRIPT.read_text(encoding='utf-8'))

if __name__=='__main__': unittest.main()
