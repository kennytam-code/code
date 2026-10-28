"""Asymmetric local-sector/global-peer coverage, with synthetic vendor evidence."""
import contextlib
import copy
import io
import unittest
from unittest.mock import patch
import pandas as pd
from test_pca_research import E


def tech(industry='Semiconductors', sector='Information Technology', **extra):
    return dict({'GICS_SECTOR_NAME':sector, 'BICS_LEVEL_1_SECTOR_NAME':'Technology',
                 'GICS_INDUSTRY_GROUP_NAME':industry, 'GICS_INDUSTRY_NAME':industry,
                 'GICS_SUB_INDUSTRY_NAME':industry, 'BICS_LEVEL_2_INDUSTRY_GROUP_NAME':industry,
                 'BICS_LEVEL_3_INDUSTRY_NAME':industry, 'BICS_LEVEL_4_SUB_INDUSTRY_NAME':industry,
                 'SECURITY_TYP2':'Common Stock'}, **extra)


class LocalGlobalPolicyTests(unittest.TestCase):
    def discovery(self, suffix='HK'):
        target='3986 '+suffix+' Equity'
        direct='DIRECT US Equity'
        local='9976 '+suffix+' Equity'
        unrelated='UNRELATED '+suffix+' Equity'
        foreign='HARDWARE JP Equity'
        precise='000660 KS Equity'
        # Even where KR/JP is the local test market, these foreign identifiers
        # stay overseas so the same economic rule is tested in every market.
        if suffix=='JP': foreign='HARDWARE US Equity'
        if suffix=='KS': precise='MEMORY US Equity'
        if suffix=='US': direct='DIRECT JP Equity'
        refs={target:tech(),direct:tech('Hardware'),local:tech('Hardware'),
              foreign:tech('Hardware'),precise:tech(),
              unrelated:tech('Shipping','Industrials',BICS_LEVEL_1_SECTOR_NAME='Industrials')}
        calls=[]
        links={target:[direct,direct], direct:[local,foreign,precise,unrelated,local,target]}
        def bulk(session,names,field):
            if isinstance(names,list):
                calls.extend(names)
                return {t:[{'Peer Ticker':v} for v in links.get(t,[])] for t in names}
            calls.append(names)
            return [{'Peer Ticker':v} for v in links.get(names,[])]
        def reference(session,names,*a,**k):
            return {t:refs.get(t,{}) for t in names}
        stubs={'bbg_ref_multi':reference,'bbg_bulk':bulk,
               '_public_equity_universe':lambda *a:([],[]),
               '_index_members':lambda *a:('TEST Index',[target]),
               '_sector_index_members':lambda *a:([],[])}
        meta={};progress=[]
        with patch.dict(E['auto_discover_universe'].__globals__,stubs),contextlib.redirect_stdout(io.StringIO()):
            found=E['auto_discover_universe'](None,target,min_mktcap_usd_mm=0,meta=meta,
                                             progress=lambda *a:progress.append(a))
        return target,direct,local,foreign,precise,unrelated,meta,found,calls,progress,stubs

    def test_local_graph_only_hardware_survives_and_global_sector_only_does_not(self):
        for suffix in ('HK','TT','JP','KS','AU','US','CH'):
            with self.subTest(suffix=suffix):
                target,direct,local,foreign,precise,bad,m,found,calls,progress,_=self.discovery(suffix)
                self.assertIn(local,found)
                self.assertIn(local,m['sector_stock_tickers'])
                self.assertNotIn(local,m['peer_tickers'])
                self.assertIn(local,m['local_second_degree_sector'])
                self.assertIn(local,m['non_index_shorts'])
                self.assertNotIn(foreign,found)
                self.assertNotIn(foreign,m['peer_tickers'])
                self.assertNotIn(bad,m['sector_stock_tickers'])
                self.assertIn(direct,m['peer_tickers'])
                self.assertIn(precise,m['peer_tickers'])
                self.assertEqual(calls,[target,direct])  # no duplicate or third-hop query
                self.assertEqual(m['second_degree_parents'][local],[direct])
                self.assertEqual(len(found),len(set(found)))
                self.assertTrue(any('additional local sector' in row[1] for row in progress))

    def test_direct_exception_needs_relation_type_sector_and_different_issuer(self):
        target=tech(ID_BB_COMPANY=123)
        ref=tech('Hardware',ID_BB_COMPANY=456)
        classify=E['_strict_peer_set']
        self.assertEqual(classify(target,{'A':ref},['A'])[0],[])
        self.assertEqual(classify(target,{'A':ref},['A'],direct_candidates=['A'])[0],['A'])
        for changed in (dict(ref,SECURITY_TYP2='ETF'),dict(ref,SECURITY_TYP2=None),
                        dict(ref,ID_BB_COMPANY=123),dict(ref,GICS_SECTOR_NAME='Utilities'),{}):
            self.assertEqual(classify(target,{'A':changed},['A'],direct_candidates=['A'])[0],[])

    def test_either_local_taxonomy_sector_can_support_broad_scope_with_conflict_recorded(self):
        target,local,foreign='T HK Equity','L HK Equity','F US Equity'
        ref=tech('Hardware',sector='Industrials')
        accepted,rows=E['_discover_sector_stocks'](target,{target:tech(),local:ref,foreign:ref},[local,foreign])
        self.assertEqual(accepted,[local])  # BICS agrees; GICS disagreement is explicit
        row=next(r for r in rows if r['ticker']==local)
        self.assertIn('BICS_LEVEL_1_SECTOR_NAME: Technology',row['evidence'])
        self.assertEqual(len(row['classification_conflicts']),1)
        self.assertFalse(E['_direct_peer_supported'](tech(),ref))

    def test_cache_recheck_preserves_direct_link_but_does_not_invent_one(self):
        target,direct,local,foreign,precise,bad,m,_,_,_,_=self.discovery()
        d={'peer_policy_version':4,'peer_tickers_by_target':{target:m['peer_tickers']+[foreign]},
           'peer_discovery_by_target':{target:m}}
        original=copy.deepcopy(d)
        out=E['_refresh_cached_peer_classification'](d)
        self.assertIn(direct,out['peer_tickers_by_target'][target])
        self.assertNotIn(foreign,out['peer_tickers_by_target'][target])
        self.assertEqual(d,original)

    def test_full_download_preserves_provenance_and_price_requests_once(self):
        target,direct,local,foreign,precise,bad,_,_,_,_,stubs=self.discovery()
        batches=[]
        def history(session,names,start,end):
            batches.extend(names)
            return pd.DataFrame(100.,index=pd.bdate_range('2026-09-01',periods=25),columns=names)
        packet=dict(mktcap_usd_mm={},mktcap_hist=pd.DataFrame(),mktcap_hist_audit={},
                    execution_snapshot={},execution_data_audit={},execution_snapshot_date='20261028')
        stubs.update(bbg_hist=history,_download_quote_metadata=lambda *a:packet)
        with patch.dict(E['_download_hedge_data_impl'].__globals__,stubs),contextlib.redirect_stdout(io.StringIO()):
            d=E['_download_hedge_data_impl'](target,session=object(),cache=False,
                min_mktcap_usd_mm=0,fetch_pit_members=False,fetch_mktcap_hist=False,
                download_scope='related',force_download=[local],download_window='3m')
        self.assertEqual(batches.count(local),1)
        self.assertNotIn(foreign,batches)
        self.assertIn(direct,batches)
        refreshed=E['_refresh_cached_peer_classification'](d)
        self.assertIn(direct,E['_related_stock_names'](refreshed,[target]))
        self.assertIn(local,E['_related_stock_names'](refreshed,[target]))
        kept,_=E['_exchange_filter']([direct,local],[target],True,'test',quiet=True)
        self.assertEqual(kept,[local])
        coverage=E['peer_coverage_report'](refreshed,target)
        self.assertEqual(coverage['local_second_degree_sector'],[local])
        self.assertEqual(coverage['direct_sector_supported'],[direct])
        self.assertIn(local,coverage['second_degree_parents'])
        rows=E['_peer_identity_rows']({'portfolio_legs':[target],
            'weights':pd.Series([.5,.5],index=[direct,local])},refreshed)
        self.assertEqual(rows[0][-1],'Bloomberg direct peer')
        self.assertEqual(rows[1][-1],'Same-market sector stock')

    def test_cap_conversion_audit_keeps_raw_values_and_actual_rate_date(self):
        dates=pd.to_datetime(['2026-10-02','2026-10-05'])
        caps=pd.DataFrame({'000660 KS Equity':[150000000.,151000000.],
                           'USD US Equity':[200.,210.],'NOFX HK Equity':[50.,60.]},index=dates)
        ccys={'000660 KS Equity':{'CRNCY':'KRW'},'USD US Equity':{'CRNCY':'USD'},
              'NOFX HK Equity':{'CRNCY':'HKD'}}
        fx=pd.DataFrame({'KRWUSD Curncy':[.07]},index=dates[:1]);audit={}
        out,missing=E['_historical_caps_usd'](caps,ccys,fx,audit=audit,
                                           fx_quote_units={'KRWUSD Curncy':100})
        row=audit['000660 KS Equity']
        self.assertEqual(row['local_cap'],151000000.)
        self.assertEqual(row['fx_rate'],.07)
        self.assertEqual(row['fx_quote_units'],100)
        self.assertEqual(row['fx_date'],'2026-10-02')
        self.assertEqual(row['date'],'2026-10-05')
        self.assertAlmostEqual(row['usd_mm'],105700.)
        self.assertAlmostEqual(out.iloc[-1,0],row['usd_mm'])
        self.assertEqual(audit['USD US Equity']['fx_rate'],1.)
        self.assertEqual(audit['NOFX HK Equity']['status'],'unavailable')
        self.assertEqual(missing,['NOFX HK Equity'])


if __name__=='__main__': unittest.main()
