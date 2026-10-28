"""Market controls, isolated public-data recovery and clear failure reporting."""
import builtins,contextlib,io,json,unittest
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
import numpy as np
import pandas as pd
from test_pca_research import E,fixture,run,OPTIONS
from test_pca_peer_discovery import electronics


def global_fixture(n=180):
    d=fixture(n=n)
    mapping={d['target']:'2476 HK Equity','0050 TT Equity':'2800 HK Equity',
             '0055 TT Equity':'3033 HK Equity'}
    mapping.update({c:str(1989+i)+' HK Equity' for i,c in enumerate(d['prices'].columns[3:])})
    d['prices']=d['prices'].rename(columns=mapping);d['target']='2476 HK Equity'
    local=list(d['prices'].columns[3:]);foreign='PEER US Equity'
    y=np.log(d['prices'][d['target']]).diff().fillna(0)
    rng=np.random.default_rng(18)
    d['prices'][foreign]=100*np.exp((y+rng.normal(0,.002,n)).cumsum())
    d.update(peer_tickers_by_target={d['target']:local+[foreign]},
             sector_scope_policy_version=1,sector_stock_tickers_by_target={d['target']:local},
             factor_tickers_by_target={d['target']:['3033 HK Equity']},
             sector_tickers_by_target={d['target']:['3033 HK Equity']},
             same_exchange_only_download=False,
             execution_snapshot={t:{'CRNCY':'USD' if t==foreign else 'HKD'} for t in d['prices']})
    return d,local,foreign


class MarketControlsTests(unittest.TestCase):
    def test_one_scope_keeps_foreign_verified_peers_only_when_listing_control_allows(self):
        d,local,foreign=global_fixture();target=d['target'];d['prices']['UNRELATED US Equity']=d['prices'][foreign]
        f=E['_filter_candidate_scope']
        with contextlib.redirect_stdout(io.StringIO()):
            domestic=f(d,[target],d['prices'].columns,'related',True,same_exchange_only=True)
            global_=f(d,[target],d['prices'].columns,'related',True,same_exchange_only=False)
        self.assertNotIn(foreign,domestic['columns']);self.assertIn(foreign,global_['columns'])
        self.assertTrue(set(local)<=set(global_['columns']))
        self.assertNotIn('UNRELATED US Equity',global_['columns'])
        self.assertNotIn('2800 HK Equity',global_['columns'])
        self.assertFalse(global_['include_broad_market'])

    def test_new_scope_has_no_automatic_timezone_removal_and_preserves_currency_warning(self):
        d,local,foreign=global_fixture()
        with contextlib.redirect_stdout(io.StringIO()):
            r=E['find_best_hedge'](d['target'],data=d,**dict(OPTIONS,candidate_scope='related',sample_window='3m',force_include=[foreign]))
        self.assertIn(foreign,r['prices']);self.assertIn(foreign,r['weights'].index)
        self.assertTrue(r['two_day_returns'])
        self.assertEqual(r['candidate_market_audit']['analysis_by_market']['US'],1)
        self.assertEqual(r['recommended_action'],'FX_NORMALIZATION_REQUIRED')
        self.assertFalse(r['trade_eligible']);self.assertTrue(r['trade_weights'].empty)
        normalized=' '.join(r['report_text'].split())
        self.assertIn('2-day overlapping returns',normalized)
        self.assertIn('Two-day overlapping log returns.',normalized)
        self.assertIn('Research coefficients only',normalized)
        self.assertIn('Verified sector stocks and peers before screens',normalized)
        self.assertIn('global peers allowed',r['report_text'])

    def test_manual_peers_obey_exclusions_and_listing_control_without_spurious_missing_errors(self):
        d,local,foreign=global_fixture();target=d['target']
        with contextlib.redirect_stdout(io.StringIO()):
            r=E['_filter_candidate_scope'](d,[target],d['prices'].columns,'related',False,
                  peers=[foreign,local[0]],exclude=[local[0]],same_exchange_only=True)
        self.assertNotIn(foreign,r['columns']);self.assertNotIn(local[0],r['columns'])

    def test_local_only_cache_cannot_masquerade_as_global_run(self):
        d,_,_=global_fixture();d['same_exchange_only_download']=True
        with self.assertRaisesRegex(ValueError,'Download again'),contextlib.redirect_stdout(io.StringIO()):
            E['find_best_hedge'](d['target'],data=d,**dict(OPTIONS,candidate_scope='related',sample_window='1m'))
        with contextlib.redirect_stdout(io.StringIO()):
            r=E['find_best_hedge'](d['target'],data=d,**dict(OPTIONS,candidate_scope='related',same_exchange_only=True,sample_window='1m'))
        self.assertEqual(set(r['candidate_market_audit']['analysis_by_market']),{'HK'})

    def test_listing_control_is_on_data_tab_and_candidate_dropdown_is_not_shown(self):
        d,_,_=global_fixture()
        with contextlib.redirect_stdout(io.StringIO()): widgets=E['hedge_ui'](d)['widgets']
        def descendants(w):
            return [w]+[item for c in getattr(w,'children',()) for item in descendants(c)]
        self.assertIn(widgets['same_exchange_only'],descendants(widgets['data_tab']))
        self.assertNotIn(widgets['same_exchange_only'],descendants(widgets['candidate_tab']))
        self.assertNotIn(widgets['candidate_scope'],descendants(widgets['candidate_tab']))
        self.assertEqual(widgets['candidate_scope'].value,'related')
        self.assertEqual(widgets['objective'].value,'factor')
        self.assertFalse(widgets['same_exchange_only'].value)
        self.assertEqual(widgets['download_scope'].value,'all')

    def test_discovery_does_not_request_invalid_volume_alias(self):
        target='2476 HK Equity';seen=[]
        def refs(session,names,fields,**kwargs):
            seen.extend(fields);return {t:electronics(ID_BB_COMPANY='1') for t in names}
        stubs={'bbg_ref_multi':refs,'bbg_bulk':lambda *a:[],
               '_public_equity_universe':lambda *a:([],[]),
               '_index_members':lambda *a:('TEST Index',[target]),
               '_sector_index_members':lambda *a:([],[])}
        with patch.dict(E['auto_discover_universe'].__globals__,stubs),contextlib.redirect_stdout(io.StringIO()):
            E['auto_discover_universe'](MagicMock(),target,min_mktcap_usd_mm=0)
        self.assertNotIn('AVERAGE_VOLUME_30D',seen)
        seen.clear()
        with patch.dict(E['_download_execution_snapshot'].__globals__,{'bbg_ref_multi':refs,'bbg_hist_field':lambda *a,**kw:pd.DataFrame()}):
            E['_download_execution_snapshot'](MagicMock(),[target],'20261026')
        self.assertNotIn('AVERAGE_VOLUME_30D',seen)

    def test_broken_yfinance_import_uses_isolated_public_client(self):
        from curl_cffi import requests
        calls=[]
        class Session:
            def __init__(self,**kwargs): pass
            def request(self,method,url,**kwargs):
                calls.append((method,url,kwargs))
                if url.endswith('getcrumb'): return SimpleNamespace(status_code=200,text='test-token')
                if url.endswith('fc.yahoo.com'): return SimpleNamespace(status_code=404)
                return SimpleNamespace(status_code=200,json=lambda:{'finance':{'result':[{'start':0,'total':1,'quotes':[{'symbol':'1989.HK','exchange':'HKG','quoteType':'EQUITY'}]}],'error':None}})
            def get(self,url,**kwargs): return self.request('GET',url,**kwargs)
            def post(self,url,**kwargs): return self.request('POST',url,**kwargs)
            def close(self): calls.append(('CLOSE',None,{}))
        original=builtins.__import__
        def import_(name,*args,**kwargs):
            if name=='yfinance': raise TypeError("'type' object is not subscriptable")
            return original(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=import_),patch.object(requests,'Session',Session):
            names,audit=E['_yahoo_equity_universe']('HK')
        self.assertEqual(names,['1989 HK Equity']);self.assertEqual(audit['status'],'received')
        self.assertIn('compatibility',audit['client']);self.assertIn('TypeError',audit['client_notice'])
        post=next(x[2] for x in calls if x[0]=='POST')
        self.assertEqual(post['json']['query'],{'operator':'EQ','operands':['exchange','HKG']})
        self.assertEqual(post['json']['size'],250)
        self.assertTrue(0<post['timeout']<=15)
        self.assertEqual(calls[-1][0],'CLOSE')

    def test_direct_client_rejects_rate_limit_and_changed_schema(self):
        for status,payload in [(429,{}),(200,{'finance':{'error':{'code':'Bad Request'},'result':[]}})]:
            session=MagicMock();session.post.return_value=SimpleNamespace(status_code=status,json=lambda:payload)
            client=E['_YahooDirectoryHTTP'](session);client.crumb='test'
            with self.assertRaises((ValueError,RuntimeError)): client.screen(['HKG'],0)
            session.post.assert_called_once()

    def test_official_roster_recovers_on_other_transport_without_repeated_same_requests(self):
        calls=[]
        def fetch(endpoint,transport):
            calls.append((endpoint,transport))
            if transport=='urllib': raise TimeoutError('slow route')
            return json.dumps([{'i':1,'c':'01989','n':'TEST'}]).encode()
        with patch.dict(E['_public_equity_universe'].__globals__,{'_bundled_listing_sources':lambda market:{},'_public_roster_bytes':fetch,'_yahoo_equity_universe':MagicMock(side_effect=AssertionError('unneeded'))}):
            names,audit=E['_public_equity_universe']('HK',refresh=True)
        self.assertEqual(names,['1989 HK Equity']);self.assertEqual(audit[0]['transport'],'curl')
        self.assertEqual(len(calls),3);self.assertEqual(len(set(calls)),3)
        self.assertIn('hkexnews',calls[0][0])

    def test_unavailable_external_sources_are_one_notice_and_bloomberg_result_survives(self):
        d,local,foreign=global_fixture()
        d['peer_discovery_by_target']={d['target']:{'listing_registry_audit':[
            {'source':'HKEX','status':'unavailable','reason':'timed out'},
            {'source':'Yahoo Finance directory','status':'unavailable','reason':'network unavailable'}]}}
        p=E['_DownloadProgress'](d['target'],lambda x:None,io.StringIO());p.finish('full details',d)
        self.assertEqual(len(p.state['notices']),1)
        self.assertIn('Bloomberg discovery were retained',p.state['notices'][0])
        self.assertEqual(p.state['status'],'warning')
        self.assertIn('1/1 overseas peers downloaded',p.state['summary'])
        self.assertEqual(len(d['peer_discovery_by_target'][d['target']]['listing_registry_audit']),2)


if __name__=='__main__': unittest.main()
