"""Cross-market universe regressions. Synthetic classifications; no network/Bloomberg."""
import contextlib,io,json,unittest
from unittest.mock import patch,MagicMock
import numpy as np
import pandas as pd
from test_pca_research import E,fixture,OPTIONS


def electronics(**extra):
    return dict({'COUNTRY_ISO':'CN','GICS_SECTOR_NAME':'Information Technology',
        'GICS_INDUSTRY_NAME':'Electronic Equipment, Instrume','GICS_SUB_INDUSTRY_NAME':'Electronic Components',
        'BICS_LEVEL_1_SECTOR_NAME':'Technology','BICS_LEVEL_2_INDUSTRY_GROUP_NAME':'Tech Hardware & Semiconductors',
        'BICS_LEVEL_3_INDUSTRY_NAME':'Technology Hardware','BICS_LEVEL_4_SUB_INDUSTRY_NAME':'Electronics Components',
        'SECURITY_TYP2':'Common Stock'},**extra)


class PeerDiscoveryTests(unittest.TestCase):
    def test_hk_official_alternate_recovers_non_index_names_after_timeout(self):
        payload=json.dumps([{'i':1,'c':'01989','n':'DELTON'}, {'i':2,'c':'02800','n':'TRACKER'},
                            {'i':3,'c':'89888','n':'RMB COUNTER'}]).encode()
        requests=[]
        def read(req,**kwargs):
            requests.append(req.full_url)
            if 'hkexnews' not in req.full_url: raise TimeoutError('timeout')
            return io.BytesIO(payload)
        with patch('urllib.request.urlopen',side_effect=read):
            names,audit=E['_public_equity_universe']('HK')
        self.assertEqual(names,['1989 HK Equity','2800 HK Equity'])
        self.assertEqual(len(requests),3)
        self.assertEqual(audit[0]['parser'],'HKEXnews')
        self.assertEqual(len(audit[0]['attempts']),2)
        verified,blocked=E['_verify_roster_candidates'](names,audit,{
            names[0]:electronics(),names[1]:{'SECURITY_TYP2':'Mutual Fund'}})
        self.assertEqual(verified,['1989 HK Equity']);self.assertIn('2800 HK Equity',blocked)
        self.assertEqual(audit[0]['verified_equities'],1)

    def test_hk_fallback_cannot_treat_missing_type_as_common_stock(self):
        names=['1989 HK Equity'];audit=[dict(requires_security_type=True,issuer_names={names[0]:'DELTON'})]
        accepted,blocked=E['_verify_roster_candidates'](names,audit,{})
        self.assertEqual(accepted,[]);self.assertEqual(blocked,set(names))
        with self.assertRaisesRegex(ValueError,'schema'):
            E['_parse_public_roster']('HKEXnews',b'[{"symbol":"1989"}]')

    def test_exact_missing_h_share_enters_discovery_without_hardcoded_mapping(self):
        target,foreign,local='2476 HK Equity','001389 CH Equity','1989 HK Equity'
        refs={target:electronics(ID_BB_COMPANY='1'),
              foreign:electronics(ID_BB_COMPANY='2',NAME='Delton Technology'),
              local:electronics(ID_BB_COMPANY='2',NAME='Delton Technology')}
        session=MagicMock();meta={}
        stub={'bbg_ref_single':lambda *a:refs[target],
              'bbg_ref_multi':lambda session,names,*a,**kw:{t:refs.get(t,{}) for t in names},
              'bbg_bulk':lambda session,ticker,field:[{'Peer Ticker':foreign}] if ticker==target else [],
              '_public_equity_universe':lambda *a:([target,local],[dict(source='HKEX',status='received',count=2)]),
              '_index_members':lambda *a:('TEST Index',[target]),'_sector_index_members':lambda *a:([],[])}
        with patch.dict(E['auto_discover_universe'].__globals__,stub),contextlib.redirect_stdout(io.StringIO()):
            names=E['auto_discover_universe'](session,target,min_mktcap_usd_mm=0,meta=meta)
        self.assertIn(local,names);self.assertIn(local,meta['peer_tickers'])
        self.assertIn(local,meta['sector_stock_tickers'])
        self.assertEqual(meta['local_listing_audit'][0]['local_listings'],[local])
        session.openService.assert_not_called()  # reuse the full listing scan
        kept,dropped=E['_exchange_filter'](names,[target],True,'test',quiet=True)
        self.assertIn(local,kept);self.assertIn(foreign,dropped)

    def test_local_listing_recovery_is_generic_and_requires_issuer_identity(self):
        for suffix in ('HK','TT','JP','KS','AU','US'):
            with self.subTest(market=suffix):
                target='TARGET '+suffix+' Equity';local='LOCAL '+suffix+' Equity';wrong='WRONG '+suffix+' Equity'
                foreign='FOREIGN '+('US' if suffix!='US' else 'HK')+' Equity'
                refs={target:electronics(ID_BB_COMPANY='1'),
                      foreign:electronics(ID_BB_COMPANY='2',NAME='Peer company')}
                leads={local:electronics(ID_BB_COMPANY='2'),wrong:electronics(ID_BB_COMPANY='3')}
                stub={'_bbg_equity_lookup':lambda *a:([local,wrong],False),
                      '_discovery_references':lambda session,names,*a:{t:leads[t] for t in names}}
                session=MagicMock();session.openService.return_value=True
                with patch.dict(E['_local_peer_listings'].__globals__,stub):
                    names,audit=E['_local_peer_listings'](session,target,[foreign],refs,[],[])
                self.assertEqual(names,[local]);self.assertEqual(audit[0]['status'],'verified local listing')
                session.openService.assert_called_once_with('//blp/instruments')

    def test_lookup_no_identity_or_service_is_visible_and_never_guessed(self):
        target='T HK Equity';foreign='F CH Equity';refs={target:electronics(),foreign:electronics(NAME='test')}
        session=MagicMock()
        names,audit=E['_local_peer_listings'](session,target,[foreign],refs,[],[])
        self.assertEqual(names,[]);self.assertIn('identity unavailable',audit[0]['reason'])
        session.openService.assert_not_called()
        refs[foreign]['ID_BB_COMPANY']='2';refs['G CH Equity']=dict(refs[foreign])
        session.openService.return_value=False
        names,audit=E['_local_peer_listings'](session,target,[foreign,'G CH Equity'],refs,[],[])
        self.assertEqual(names,[]);self.assertEqual(len(audit),2);session.openService.assert_called_once()

    def test_no_extra_name_queries_after_listing_scan_and_never_own_issuer(self):
        target='T HK Equity';refs={target:electronics(ID_BB_COMPANY='1'),
            'F CH Equity':electronics(ID_BB_COMPANY='2',NAME='peer'),
            'T CH Equity':electronics(ID_BB_COMPANY='1',NAME='target')}
        session=MagicMock()
        names,audit=E['_local_peer_listings'](session,target,['F CH Equity','T CH Equity'],refs,[],[],allow_lookup=False)
        self.assertEqual(names,[]);self.assertIn('deferred',audit[0]['reason'])
        self.assertEqual(audit[1]['status'],'target issuer excluded');session.openService.assert_not_called()

    def test_sector_only_index_names_are_in_classification_pool_for_all_markets(self):
        for suffix,country in [('HK','HK'),('TT','TW'),('JP','JP'),('AU','AU'),('KS','KR'),('US','US')]:
            for sector,industry in [('Technology','Hardware'),('Financials','Banks'),('Industrials','Machinery')]:
                with self.subTest(market=suffix,sector=sector):
                    t='TARGET '+suffix+' Equity';p='NONINDEX '+suffix+' Equity'
                    ref={'COUNTRY_ISO':country,'GICS_SECTOR_NAME':sector,'GICS_INDUSTRY_NAME':industry}
                    seen=[]
                    def multi(session,names,*args,**kwargs):
                        seen.extend(names);return {n:ref for n in names}
                    stub={'bbg_ref_single':lambda *a:ref,'bbg_ref_multi':multi,
                          'bbg_bulk':lambda *a:[], '_public_equity_universe':lambda *a:([],[]),
                          '_index_members':lambda *a:('Broad Index',[t]),
                          '_sector_index_members':lambda *a:(['Sector Index'],[p])}
                    meta={}
                    with patch.dict(E['auto_discover_universe'].__globals__,stub),contextlib.redirect_stdout(io.StringIO()):
                        E['auto_discover_universe'](None,t,min_mktcap_usd_mm=0,meta=meta)
                    self.assertIn(p,seen);self.assertIn(p,meta['peer_tickers']);self.assertIn(p,meta['sector_stock_tickers'])

    def test_parent_group_cannot_override_narrow_business_conflict(self):
        target=electronics();semi=electronics(BICS_LEVEL_3_INDUSTRY_NAME='Semiconductors',
            BICS_LEVEL_4_SUB_INDUSTRY_NAME='Semiconductor Devices',GICS_INDUSTRY_NAME='Semiconductors & Semiconductor',
            GICS_SUB_INDUSTRY_NAME='Semiconductors')
        self.assertFalse(E['_peer_industry_supported'](target,semi))
        self.assertTrue(E['_peer_industry_supported'](target,electronics()))
        self.assertTrue(E['_peer_industry_supported']({'GICS_INDUSTRY_NAME':'Banks'},{'GICS_INDUSTRY_NAME':'Banks'}))
        self.assertFalse(E['_peer_industry_supported'](target,electronics(SECURITY_TYP2='ETF')))
        self.assertEqual(E['_specific_exposure_tags'](target),set())
        self.assertEqual(E['_specific_exposure_tags'](semi),{'SEMIS'})
        self.assertEqual(E['_specific_exposure_tags']({'GICS_INDUSTRY_NAME':'Banks'}),{'RATES'})
        names,resolved,unresolved=E['_resolve_exposures']({'SEMIS'},'HK','CN')
        self.assertEqual(names,[]);self.assertEqual(resolved,{});self.assertIn('SEMIS',unresolved)

    def test_target_issuer_other_share_classes_are_never_automatic_peers(self):
        target,other,peer='A HK Equity','B HK Equity','C HK Equity'
        refs={target:electronics(ID_BB_COMPANY=10),other:electronics(ID_BB_COMPANY=10),
              peer:electronics(ID_BB_COMPANY=11)}
        self.assertFalse(E['_peer_industry_supported'](refs[target],refs[other]))
        self.assertTrue(E['_peer_industry_supported'](refs[target],refs[peer]))
        names,audit=E['_discover_sector_stocks'](target,refs,[other,peer])
        self.assertEqual(names,[peer]);self.assertIn('target issuer',audit[0]['reason'])

    def test_recent_listing_with_complete_selected_window_remains_searchable(self):
        d=fixture();target=d['target'];peers=d['peer_tickers_by_target'][target]
        recent=peers[0]
        # The cache spans much longer than this synthetic IPO's six-month life.
        d['prices'].loc[d['prices'].index[:-130],recent]=np.nan
        d.update(sector_scope_policy_version=1,sector_stock_tickers_by_target={target:peers},
                 peer_discovery_by_target={target:{'sector_stock_audit':[
                     {'ticker':t,'eligible':True,'reason':'same-market sector stock','evidence':['test taxonomy']}
                     for t in peers]}})
        for window in ('1m','2m','3m'):
            with self.subTest(window=window):
                with contextlib.redirect_stdout(io.StringIO()):
                    result=E['find_best_hedge'](target,data=d,**dict(OPTIONS,candidate_scope='sector',sample_window=window))
                self.assertIn(recent,result['sector_search_audit'][target]['searched_stocks'])

    def test_reference_failure_retains_good_batches_and_retries_once(self):
        names=[str(i)+' US Equity' for i in range(605)];calls=[]
        def multi(session,chunk,*args,**kwargs):
            calls.append(chunk)
            if chunk[0]=='300 US Equity': raise TimeoutError('test batch timeout')
            return {t:{'GICS_INDUSTRY_NAME':'Banks'} for t in chunk}
        errors=[]
        with patch.dict(E['_discovery_references'].__globals__,{'bbg_ref_multi':multi}):
            refs=E['_discovery_references'](None,names,['GICS_INDUSTRY_NAME'],errors)
        self.assertEqual(len(refs),305);self.assertEqual(len(calls),4)
        self.assertIn(names[-1],refs);self.assertEqual(len(errors[-1]['tickers']),300)

    def test_cached_narrow_classification_rechecked_without_changing_sector_or_prices(self):
        d=fixture();t=d['target'];p=d['peer_tickers_by_target'][t][0]
        d['peer_discovery_by_target']={t:{'classification_evidence':{t:electronics(),p:electronics(
            GICS_SUB_INDUSTRY_NAME='Software',BICS_LEVEL_4_SUB_INDUSTRY_NAME='Software')}}}
        updated=E['_refresh_cached_peer_classification'](d)
        self.assertNotIn(p,updated['peer_tickers_by_target'][t]);self.assertIn(p,d['peer_tickers_by_target'][t])
        self.assertIs(updated['prices'],d['prices'])

    def test_related_history_scope_keeps_all_peers_and_sector_stocks(self):
        m=[dict(peer_tickers=['P US Equity'],sector_stock_tickers=['S US Equity'],
                source_candidates={'Local index':['UNRELATED US Equity'],
                                   'Control ETFs':['SPY US Equity']})]
        self.assertEqual(E['_related_history_names'](m),{'P US Equity','S US Equity','SPY US Equity'})

    def test_broad_analysis_cannot_silently_use_related_only_download(self):
        d=fixture();d['download_scope']='related'
        with contextlib.redirect_stdout(io.StringIO()),self.assertRaisesRegex(ValueError,'download_scope'):
            E['find_best_hedge'](d['target'],data=d,**dict(OPTIONS,candidate_scope='all',sample_window='1m'))

    def test_historical_peer_is_classified_and_not_lost_by_related_history_filter(self):
        t,p,u='T US Equity','P US Equity','U US Equity'
        m=[dict(target=t,classification_evidence={t:electronics()},peer_tickers=[],sector_stock_tickers=[])]
        refs={p:electronics(),u:{'GICS_SECTOR_NAME':'Financials','GICS_INDUSTRY_NAME':'Banks'}}
        with patch.dict(E['_extend_historical_discovery'].__globals__,{
                '_discovery_references':lambda *a:refs}):
            E['_extend_historical_discovery'](None,[p,u],m)
        self.assertIn(p,m[0]['peer_tickers']);self.assertIn(p,m[0]['sector_stock_tickers'])
        self.assertIn(p,E['_related_history_names'](m));self.assertNotIn(u,E['_related_history_names'](m))

    def test_old_discovery_cache_is_not_offered_as_up_to_date(self):
        d=fixture();d['fingerprint']={'instrument_map':E['_INSTRUMENT_MAP_HASH']}
        audit=E['check_cache_fit'](d['target'],d)
        self.assertEqual(audit['status'],'mismatch');self.assertIn('peer discovery changed',audit['message'])

    def test_recipe_ties_ignore_machine_roundoff_without_hiding_real_score_gains(self):
        key=E['_recipe_selection_key']
        self.assertGreater(key(.4774856071057815,5,'search:0'),key(.4774856071057817,5,'correlation'))
        self.assertGreater(key(.47749,5,'correlation'),key(.4774856071057815,5,'search:0'))
        self.assertGreater(key(.4,3,'forward'),key(.4,5,'search:0'))

    def test_issuer_id_rejects_zero_and_vendor_error_placeholders(self):
        for value in (None,0,'0','#N/A','nan',-1,1.5):
            self.assertIsNone(E['_issuer_id']({'ID_BB_COMPANY':value}))
        self.assertEqual(E['_issuer_id']({'ID_BB_COMPANY':'123.000'}),'123')
        self.assertTrue(E['_common_share_type']({'SECURITY_TYP2':'REIT'}))
        self.assertTrue(E['_common_share_type']({'SECURITY_TYP2':'#N/A','SECURITY_TYP':'Common Stock'}))

    def test_security_lookup_uses_documented_request_and_counts_raw_response_limit(self):
        class Element:
            def __init__(self,value): self.value=value
            def hasElement(self,key): return key in self.value
            def getElement(self,key): return Element(self.value[key])
            def getElementAsString(self,key): return self.value[key]
            def numValues(self): return len(self.value)
            def getValueAsElement(self,key): return Element(self.value[key])
        rows=[{'security':'/ticker/1989 HK Equity'},{'security':'001389 CH Equity'},
              {'security':'not a valid equity identifier'}]
        session=MagicMock()
        with patch.dict(E['_bbg_equity_lookup'].__globals__,{'_drain_events':lambda s,f:f(Element({'results':rows}))}):
            names,truncated=E['_bbg_equity_lookup'](session,'Delton',limit=3)
        self.assertEqual(names,['001389 CH Equity','1989 HK Equity']);self.assertTrue(truncated)
        session.getService.assert_called_with('//blp/instruments')
        session.getService.return_value.createRequest.assert_called_with('instrumentListRequest')
        session.getService.return_value.createRequest.return_value.set.assert_any_call('yellowKeyFilter','YK_FILTER_EQTY')

    def test_discovery_request_errors_are_reported_after_draining_responses(self):
        class Element:
            def __init__(self,value): self.value=value
            def hasElement(self,key): return key in self.value
            def getElement(self,key): return Element(self.value[key])
            def getElementAsString(self,key): return str(self.value[key])
            def numValues(self): return len(self.value)
            def getValueAsElement(self,key): return Element(self.value[key])
            def __str__(self): return str(self.value)
        cases=[('bbg_bulk',('T HK Equity','BLOOMBERG_PEERS'),
                {'securityData':[{'fieldExceptions':[{'fieldId':'BLOOMBERG_PEERS',
                                                      'errorInfo':'not entitled'}]}]}),
               ('bbg_bulk',('T HK Equity','BLOOMBERG_PEERS'),{'responseError':'not entitled'}),
               ('_bbg_equity_lookup',('peer',),{'responseError':'not entitled'})]
        for name,args,message in cases:
            with self.subTest(name=name,message=message):
                drained=[]
                def drain(session,callback):
                    callback(Element(message));callback(Element({}));drained.append(True)
                fn=E[name]
                with patch.dict(fn.__globals__,{'_drain_events':drain}),self.assertRaisesRegex(RuntimeError,'not entitled'):
                    fn(MagicMock(),*args)
                self.assertEqual(drained,[True])

    def test_discovery_cache_reuses_references_and_indices_only_within_download(self):
        target,peer='T US Equity','P US Equity';ref=electronics(COUNTRY_ISO='US')
        calls={'refs':0,'index':0,'roster':0,'peers':0}
        def refs(session,names,*a,**kw):
            calls['refs']+=1;return {t:ref for t in names}
        def index(*a): calls['index']+=1;return ('TEST Index',[target,peer])
        def roster(*a): calls['roster']+=1;return ([target,peer],[])
        def peers(*a): calls['peers']+=1;return []
        stubs={'bbg_ref_single':lambda *a:ref,'bbg_ref_multi':refs,'_index_members':index,
               '_sector_index_members':lambda *a:([],[]),'_public_equity_universe':roster,'bbg_bulk':peers}
        cache={}
        with patch.dict(E['auto_discover_universe'].__globals__,stubs),contextlib.redirect_stdout(io.StringIO()):
            E['auto_discover_universe'](None,target,min_mktcap_usd_mm=0,discovery_cache=cache)
            first=dict(calls)
            E['auto_discover_universe'](None,target,min_mktcap_usd_mm=0,discovery_cache=cache)
        self.assertEqual(calls,first)


if __name__=='__main__': unittest.main()
