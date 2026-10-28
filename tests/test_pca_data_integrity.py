"""Offline regression coverage for download failures and historical eligibility.

All market series are synthetic; these tests never require Bloomberg/network.
"""
import contextlib,io,json,ssl,unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from test_pca_research import E,fixture,OPTIONS
import test_pca_sector_scope as sector_tests


class DataIntegrityTests(unittest.TestCase):
    def test_vendor_errors_survive_and_volume_requests_do_not_fill_holidays(self):
        class Element:
            def __init__(self,value): self.value=value
            def hasElement(self,key): return key in self.value
            def getElement(self,key): return Element(self.value[key])
            def getElementAsString(self,key): return str(self.value[key])
            def numValues(self): return len(self.value)
            def getValueAsElement(self,key): return Element(self.value[key])
            def __str__(self): return str(self.value)
            def appendValue(self,value): self.value.append(value)
        class Request:
            def __init__(self): self.values={'fields':[],'securities':[]}
            def getElement(self,key): return Element(self.values[key])
            def set(self,key,value): self.values[key]=value
        class Session:
            def getService(self,name): return self
            def createRequest(self,name): self.request=Request();return self.request
            def sendRequest(self,request): pass
        sd={'security':'A','fieldExceptions':[{'fieldId':'PX_VOLUME','errorInfo':{'message':'not entitled'}}],
            'fieldData':[]}
        def drain(session,callback): callback(Element({'securityData':sd}))
        session=Session();errors=[];fn=E['bbg_hist_field']
        with patch.dict(fn.__globals__,{'_drain_events':drain}):
            values=fn(session,['A'],'PX_VOLUME','20260101','20260131',active_days=True,errors=errors)
        self.assertTrue(values.empty)
        self.assertEqual(session.request.values['nonTradingDayFillOption'],'ACTIVE_DAYS_ONLY')
        self.assertNotIn('nonTradingDayFillMethod',session.request.values)
        self.assertIn('not entitled',errors[0]['reason'])
        sd.pop('fieldData')
        with patch.dict(fn.__globals__,{'_drain_events':drain}):
            self.assertTrue(fn(session,['A'],'PX_VOLUME','20260101','20260131',errors=[]).empty)
        refsd=dict(sd,fieldData={'CRNCY':'USD'})
        fn=E['bbg_ref_multi'];errors=[]
        with patch.dict(fn.__globals__,{'_drain_events':lambda s,cb:cb(Element({'securityData':[refsd]}))}):
            values=fn(session,['A'],['CRNCY','PX_VOLUME'],errors=errors)
        self.assertEqual(values['A']['CRNCY'],'USD')
        self.assertEqual(errors[0]['field'],'PX_VOLUME')

    def test_access_challenge_is_not_treated_as_listing_data(self):
        with self.assertRaisesRegex(ValueError,'access/challenge'):
            E['_parse_public_roster']('Nasdaq listed',b'<html><script>challenge</script></html>')

    def test_csv_rosters_preserve_industry_and_identifier(self):
        text='出表日期,公司代號,公司簡稱,產業別\n1151019,2889,國票金,17\n'
        for source in ('TWSE','TPEx'):
            for encoding in ('utf-8-sig','cp950'):
                names,audit=E['_parse_public_roster'](source,text.encode(encoding))
                self.assertEqual(names,['2889 TT Equity'])
                self.assertEqual(audit['industries']['2889 TT Equity'],'17')

    def test_official_alternate_after_tls_error_retains_verification(self):
        def receive(req,**kw):
            self.assertEqual(kw['context'].verify_mode,ssl.CERT_REQUIRED)
            self.assertTrue(kw['context'].check_hostname)
            if 'mopsfin.twse.com.tw' not in req.full_url:
                raise ssl.SSLCertVerificationError('test certificate failure')
            code='2889' if '_L.' in req.full_url else '5864'
            return io.BytesIO(('公司代號,公司簡稱,產業別\n'+code+',test,17\n').encode())
        with patch.dict(E['_public_equity_universe'].__globals__,{'_bundled_listing_sources':lambda market:{}}),patch('urllib.request.urlopen',side_effect=receive):
            names,audit=E['_public_equity_universe']('TW',refresh=True)
        self.assertEqual(names,['2889 TT Equity','5864 TT Equity'])
        self.assertTrue(all(a['status']=='received' and len(a['attempts'])==1 for a in audit))

    def test_volume_alias_and_active_day_fallback_are_recorded(self):
        dates=pd.bdate_range('2026-08-01','2026-10-19')
        volumes=pd.DataFrame({'B':np.arange(len(dates),dtype=float),'C':np.nan},index=dates)
        volumes.loc[dates[:10],'C']=20  # old observations cannot establish current liquidity
        def history(session,names,field,start,end,**kw):
            self.assertEqual(names,['B','C']); self.assertEqual(field,'PX_VOLUME')
            self.assertTrue(kw['active_days'])
            return volumes
        def reference(*args,**kw):
            kw['errors'].append({'security':'B','field':'VOLUME_AVG_30D','reason':'not entitled'})
            return {'A':{'VOLUME_AVG_30D':'10000'},'B':{},'C':{}}
        fn=E['_download_execution_snapshot']
        with patch.dict(fn.__globals__,{'bbg_ref_multi':reference,'bbg_hist_field':history}):
            quotes,audit=fn(object(),['A','B','C'],'20261019')
        self.assertEqual(quotes['A']['PCA_AVG_DAILY_VOLUME'],10000)
        self.assertAlmostEqual(quotes['B']['PCA_AVG_DAILY_VOLUME'],volumes['B'].tail(30).mean())
        self.assertNotIn('PCA_AVG_DAILY_VOLUME',quotes['C'])
        self.assertEqual(audit['volume']['B']['sessions'],30)
        self.assertEqual(audit['volume']['C']['source'],'unavailable')
        self.assertIn('not entitled',audit['errors'][0]['reason'])

    def test_volume_failure_does_not_invent_zero_liquidity(self):
        fn=E['_download_execution_snapshot']
        with patch.dict(fn.__globals__,{'bbg_ref_multi':lambda *a,**k:{'A':{'PX_BID':'20','CRNCY':'USD'}},
                 'bbg_hist_field':lambda *a,**k: (_ for _ in ()).throw(RuntimeError('field denied'))}):
            quotes,audit=fn(object(),['A'],'20261019')
        self.assertNotIn('PCA_AVG_DAILY_VOLUME',quotes['A'])
        self.assertEqual(quotes['A']['CRNCY'],'USD')
        self.assertIn('field denied',audit['errors'][0]['reason'])

    def test_dated_fx_cannot_look_ahead_or_rescale_past(self):
        dates=pd.to_datetime(['2026-01-01','2026-01-02','2026-01-12'])
        caps=pd.DataFrame({'A':1000.,'U':200.},index=dates)
        fx=pd.DataFrame({'TWDUSD Curncy':[.03,.04]},index=dates[:2])
        ccy={'A':{'CRNCY':'TWD'},'U':{'CRNCY':'USD'}}
        units={'TWDUSD Curncy':1}
        out,missing=E['_historical_caps_usd'](caps,ccy,fx,fx_quote_units=units)
        self.assertEqual(list(out['A'].iloc[:2]),[30.,40.])
        self.assertTrue(np.isnan(out['A'].iloc[2]))
        self.assertEqual(list(out['U']),[200.,200.,200.])
        changed=fx.copy();changed.iloc[1]=999
        again,_=E['_historical_caps_usd'](caps,ccy,changed,fx_quote_units=units)
        self.assertEqual(again['A'].iloc[0],out['A'].iloc[0])
        late,_=E['_historical_caps_usd'](caps,ccy,fx.iloc[1:],fx_quote_units=units)
        self.assertTrue(np.isnan(late['A'].iloc[0]))

    def test_cached_cap_restoration_needs_verified_prices_and_honours_exclusions(self):
        d,stocks,_=sector_tests.SectorScopeTests().sector_data()
        d['sector_stock_tickers_by_target'][d['target']]=stocks[3:]
        disc=d['peer_discovery_by_target'][d['target']]
        disc['market_cap_filtered']=stocks[:3]+['UNKNOWN TT Equity']
        disc['manual_excluded']=[stocks[1]]
        d['prices']=d['prices'].drop(columns=stocks[2])
        new=E['_restore_cached_sector_candidates'](d)
        self.assertIn(stocks[0],new['sector_stock_tickers_by_target'][d['target']])
        self.assertNotIn(stocks[1],new['sector_stock_tickers_by_target'][d['target']])
        self.assertNotIn(stocks[2],new['sector_stock_tickers_by_target'][d['target']])
        self.assertNotIn(stocks[0],d['sector_stock_tickers_by_target'][d['target']])

    def test_new_dated_cap_path_does_not_fall_back_to_future_cap(self):
        d,stocks,_=sector_tests.SectorScopeTests().sector_data(n=150)
        idx=d['prices'].index
        d['mktcap_hist_method']=E['CAP_HISTORY_METHOD']
        d['mktcap_hist']=pd.DataFrame(2000.,index=idx,columns=[d['target']]+stocks)
        d['mktcap_hist'].loc[idx[:-5],stocks[0]]=np.nan
        d['mktcap_usd_mm']={t:2000. for t in [d['target']]+stocks}
        options=dict(OPTIONS,candidate_scope='sector',min_mktcap_usd_mm=300.,sample_window='3m')
        with contextlib.redirect_stdout(io.StringIO()):
            r=E['find_best_hedge'](d['target'],data=d,**options)
        audits=r['joint_search_audit']
        early=min(audits,key=lambda a:a['end']);current=max(audits,key=lambda a:a['end'])
        self.assertNotIn(stocks[0],early['eligible_tickers'])
        self.assertIn(stocks[0],current['eligible_tickers'])

    def test_stale_cap_and_missing_target_size_band_are_not_passed(self):
        d,stocks,_=sector_tests.SectorScopeTests().sector_data(n=100)
        idx=d['prices'].index
        d['mktcap_hist_method']='historical local cap x dated FX'
        d['mktcap_hist']=pd.DataFrame(2000.,index=idx,columns=[d['target']]+stocks)
        d['mktcap_hist'].loc[idx[-15:],stocks[0]]=np.nan
        d['mktcap_usd_mm']={t:2000. for t in [d['target']]+stocks}
        options=dict(OPTIONS,candidate_scope='sector',min_mktcap_usd_mm=300.,sample_window='1m')
        with contextlib.redirect_stdout(io.StringIO()):
            r=E['find_best_hedge'](d['target'],data=d,**options)
        self.assertNotIn(stocks[0],max(r['joint_search_audit'],key=lambda a:a['end'])['eligible_tickers'])
        d['mktcap_hist'][d['target']]=np.nan
        with contextlib.redirect_stdout(io.StringIO()),self.assertRaisesRegex(ValueError,'relative size band cannot be verified'):
            E['find_best_hedge'](d['target'],data=d,**dict(options,size_band=(.5,2)))

    def test_data_quality_and_model_setting_scope_are_printed_and_exportable(self):
        d,stocks,_=sector_tests.SectorScopeTests().sector_data(n=100)
        disc=d['peer_discovery_by_target'][d['target']]
        disc['listing_registry_audit']=[{'source':'TWSE','status':'unavailable','reason':'timeout','count':0}]
        with contextlib.redirect_stdout(io.StringIO()):
            r=E['find_best_hedge'](d['target'],data=d,**dict(OPTIONS,candidate_scope='sector',sample_window='1m'))
        self.assertIn('Listing coverage incomplete',r['report_text'])
        self.assertIn('Average volume unavailable',r['report_text'])
        self.assertLess(r['report_text'].index('Listing coverage incomplete'),r['report_text'].index('CURRENT BASKET'))
        self.assertEqual(r['effective_model_settings']['main_model_returns'],'unclipped')
        self.assertEqual(r['effective_model_settings']['pca_controls_scope'],'descriptive PCA only')
        self.assertTrue(r['data_quality']['historical_universe_limits'])

    def test_future_returns_do_not_change_frozen_holdout_selection(self):
        d,stocks,_=sector_tests.SectorScopeTests().sector_data(n=100)
        options=dict(OPTIONS,candidate_scope='sector',sample_window='3m')
        with contextlib.redirect_stdout(io.StringIO()):
            before=E['find_best_hedge'](d['target'],data=d,**options)
            changed=dict(d,prices=d['prices'].copy())
            changed['prices'].iloc[-5:]*=1.5
            after=E['find_best_hedge'](d['target'],data=changed,**options)
        pd.testing.assert_series_equal(before['validation_weights'],after['validation_weights'])


if __name__=='__main__': unittest.main()
