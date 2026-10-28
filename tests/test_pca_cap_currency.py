"""Historical USD caps: vendor request units, error draining and stale-cache guards."""
import contextlib
import io
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from test_pca_research import E, fixture, OPTIONS


class Element:
    def __init__(self, value): self.value=value
    def hasElement(self, key): return key in self.value
    def getElement(self, key): return Element(self.value[key])
    def getElementAsString(self, key): return str(self.value[key])
    def getElementAsDatetime(self, key): return self.value[key]
    def getElementAsFloat(self, key): return float(self.value[key])
    def numValues(self): return len(self.value)
    def getValueAsElement(self, key): return Element(self.value[key])
    def appendValue(self, value): self.value.append(value)
    def __str__(self): return str(self.value)


class Session:
    def __init__(self): self.requests=[]
    def getService(self, name): return self
    def createRequest(self, name):
        class Request:
            def __init__(self): self.values={'fields':[],'securities':[]}
            def getElement(self, key): return Element(self.values[key])
            def set(self, key, value): self.values[key]=value
        return Request()
    def sendRequest(self, req): self.requests.append(req.values)


class CapCurrencyTests(unittest.TestCase):
    def test_currency_is_set_on_each_cap_request_not_on_price_or_volume(self):
        session=Session();names=[str(i)+' TT Equity' for i in range(101)]
        def drain(session, callback):
            for name in session.requests[-1]['securities']:
                callback(Element({'securityData':{'security':name,'fieldData':[
                    {'date':pd.Timestamp('2026-10-01'),'CUR_MKT_CAP':123.}]}}))
        fn=E['bbg_hist_field']
        with patch.dict(fn.__globals__,{'_drain_events':drain}):
            values=fn(session,names,'CUR_MKT_CAP','20261001','20261002',currency='USD')
            self.assertEqual(values.shape,(1,101))
            self.assertEqual([r['currency'] for r in session.requests],['USD','USD'])
            fn(session,['V'],'PX_VOLUME','20261001','20261002',active_days=True)
            self.assertNotIn('currency',session.requests[-1])
            fn(session,['P'],'PX_LAST','20261001','20261002')
            self.assertNotIn('currency',session.requests[-1])

    def test_request_error_is_raised_only_after_response_has_drained(self):
        finished=[];errors=[]
        def drain(session, callback):
            callback(Element({'responseError':'USD conversion denied'}))
            callback(Element({}))
            finished.append(True)
        fn=E['bbg_hist_field']
        with patch.dict(fn.__globals__,{'_drain_events':drain}):
            with self.assertRaisesRegex(RuntimeError,'USD conversion denied'):
                fn(Session(),['000660 KS Equity'],'CUR_MKT_CAP','20261001','20261002',
                   currency='USD',errors=errors)
        self.assertEqual(finished,[True])
        self.assertEqual(errors[0]['currency'],'USD')

    def test_all_regions_use_vendor_usd_caps_with_no_local_fx_path(self):
        names=['2889 TT Equity','BHP AU Equity','7203 JP Equity','600000 CH Equity',
               '000001 CH Equity','000660 KS Equity','3986 HK Equity','MSFT US Equity']
        dates=pd.bdate_range('2026-10-01',periods=3)
        caps=pd.DataFrame({t:np.arange(3)+1000.*(i+1) for i,t in enumerate(names)},index=dates)
        caps.iloc[0,0]=np.inf;caps.iloc[1,0]=-10
        calls=[]
        def historical(session,tickers,field,start,end,**kw):
            calls.append((tickers,field,kw));return caps
        fn=E['_download_quote_metadata']
        with patch.dict(fn.__globals__,{'bbg_hist_field':historical,
                'bbg_ref_multi':lambda *a,**k:{t:{'CRNCY_ADJ_MKT_CAP':caps[t].iloc[-1]} for t in names},
                '_download_execution_snapshot':lambda *a:({},{}),
                '_historical_caps_usd':lambda *a,**k:self.fail('must not self-convert raw FX')}),contextlib.redirect_stdout(io.StringIO()):
            result=fn(None,pd.DataFrame(100.,index=dates,columns=names),'20261001','20261005')
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][1],'CUR_MKT_CAP')
        self.assertEqual(calls[0][2]['currency'],'USD')
        self.assertEqual(calls[0][0],names)
        pd.testing.assert_frame_equal(result['mktcap_hist'],caps.where(np.isfinite(caps)&(caps>0)))
        audit=result['mktcap_hist_audit']
        self.assertEqual(audit['missing_histories'],[])
        for name in names:
            self.assertEqual(audit['conversion_samples'][name]['usd_mm'],caps[name].iloc[-1])
            self.assertEqual(audit['conversion_samples'][name]['method'],E['CAP_HISTORY_METHOD'])

    def test_unavailable_usd_caps_remain_unknown_not_local_currency_numbers(self):
        fn=E['_download_quote_metadata']
        def fail(*a,**k): raise RuntimeError('USD cap request failed')
        with patch.dict(fn.__globals__,{'bbg_hist_field':fail,'bbg_ref_multi':lambda *a,**k:{},
                 '_download_execution_snapshot':lambda *a:({},{})}),contextlib.redirect_stdout(io.StringIO()):
            result=fn(None,pd.DataFrame({'000660 KS Equity':[100.]},index=pd.to_datetime(['2026-10-01'])),
                      '20261001','20261002')
        self.assertTrue(result['mktcap_hist'].empty)
        self.assertIn('USD cap request failed',result['mktcap_hist_audit']['errors'][0]['reason'])

    def test_legacy_converter_refuses_unknown_quote_units(self):
        dates=pd.to_datetime(['2026-10-01'])
        caps=pd.DataFrame({'000660 KS Equity':[150000000.]},index=dates)
        out,missing=E['_historical_caps_usd'](caps,{'000660 KS Equity':{'CRNCY':'KRW'}},
            pd.DataFrame({'KRWUSD Curncy':[.07]},index=dates))
        self.assertTrue(out.empty)
        self.assertEqual(missing,['000660 KS Equity'])

    def test_legacy_korean_cap_cache_is_blocked_before_active_size_screen(self):
        d=fixture(n=90);old='2900 TT Equity';name='000660 KS Equity'
        d['prices']=d['prices'].rename(columns={old:name})
        d['peer_tickers_by_target'][d['target']]=[name if t==old else t for t in d['peer_tickers_by_target'][d['target']]]
        d['mktcap_hist_method']='historical local cap x dated FX'
        d['mktcap_hist']=pd.DataFrame(1e8,index=d['prices'].index,columns=d['prices'].columns)
        self.assertEqual(E['_legacy_cap_unit_issues'](d,d['prices'].columns),[name])
        with contextlib.redirect_stdout(io.StringIO()),self.assertRaisesRegex(ValueError,'full Download'):
            E['find_best_hedge'](d['target'],data=d,**dict(OPTIONS,sample_window='1m',
                                   same_exchange_only=False,pit_size=True,min_mktcap_usd_mm=300))
        d['mktcap_hist_method']=E['CAP_HISTORY_METHOD']
        self.assertEqual(E['_legacy_cap_unit_issues'](d,d['prices'].columns),[])


if __name__=='__main__': unittest.main()
