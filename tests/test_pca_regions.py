"""Regional identifiers, mainland directory integrity and listing-scope controls."""
import io
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from test_pca_research import E


class RegionTests(unittest.TestCase):
    def test_mainland_sources_include_both_shanghai_boards_shenzhen_and_beijing(self):
        sources=dict(E['_cn_listing_sources']())
        self.assertEqual(set(sources),{'SSE Main Board','SSE STAR','SZSE','BSE'})
        self.assertIn('STOCK_TYPE=1',sources['SSE Main Board'])
        self.assertIn('STOCK_TYPE=8',sources['SSE STAR'])
        self.assertIn('type=inParams',sources['SSE Main Board'])
        self.assertIn('TABKEY=tab1',sources['SZSE'])

    def test_sse_parser_rejects_partial_or_duplicate_pages(self):
        rows=[dict(A_STOCK_CODE='600000',SEC_NAME_CN='test',CSRC_CODE_DESC='金融业')]
        data={'result':rows,'pageHelp':{'total':1}}
        names,audit=E['_parse_public_roster']('SSE Main Board',json.dumps(data).encode())
        self.assertEqual(names,['600000 CH Equity'])
        self.assertTrue(audit['requires_security_type'])
        self.assertIsNone(audit['industry_scheme'])  # broad CSRC category is not GICS
        for changed in ({'result':rows,'pageHelp':{'total':2}},
                        {'result':rows*2,'pageHelp':{'total':2}},
                        {'result':[dict(rows[0],A_STOCK_CODE='900001')],'pageHelp':{'total':1}}):
            with self.assertRaises(ValueError):
                E['_parse_public_roster']('SSE Main Board',json.dumps(changed).encode())
        rows[0]['A_STOCK_CODE']='688001'
        self.assertEqual(E['_parse_public_roster']('SSE STAR',json.dumps(data).encode())[0],['688001 CH Equity'])

    def test_szse_preserves_leading_zeroes_and_skips_blank_b_only_rows(self):
        buffer=io.BytesIO()
        pd.DataFrame({'A股代码':['000001','301001',''], 'A股简称':['bank','tech','b-only'],
                      '所属行业':['J 金融业','C 制造业','C 制造业']}).to_excel(buffer,index=False)
        names,audit=E['_parse_public_roster']('SZSE',buffer.getvalue())
        self.assertEqual(names,['000001 CH Equity','301001 CH Equity'])
        self.assertEqual(audit['excluded_non_equity'],1)

    def test_beijing_paging_consumes_each_page_once_and_refuses_truncation(self):
        calls=[]
        def page(n):
            calls.append(n)
            return 'null('+json.dumps([dict(number=n,totalElements=3,totalPages=2,
                content=[dict(xxzqdm=t,xxzqjc=t) for t in (['920001','920002'] if n==0 else ['920003'])])])+')'
        payload=E['_collect_bse_directory'](page)
        names,audit=E['_parse_public_roster']('BSE',payload)
        self.assertEqual(calls,[0,1]);self.assertEqual(len(names),3)
        self.assertTrue(audit['requires_security_type'])
        with self.assertRaisesRegex(ValueError,'page limit'):
            E['_collect_bse_directory'](page,max_pages=1)
        with self.assertRaisesRegex(ValueError,'repeated'):
            E['_collect_bse_directory'](lambda n:page(n).replace('920003','920002'))
        with self.assertRaisesRegex(ValueError,'invalid JSON'):
            E['_collect_bse_directory'](lambda n:'<html>challenge</html>')

    def test_yahoo_mainland_mapping_requires_matching_venue_and_a_share_type(self):
        fn=E['_yahoo_listing_ticker']
        for symbol,venue,expected in [('000001.SZ','SHZ','000001 CH Equity'),
                                      ('600000.SS','SHH','600000 CH Equity'),
                                      ('688001.SS','SHH','688001 CH Equity'),
                                      ('301001.SZ','SHZ','301001 CH Equity')]:
            q=dict(symbol=symbol,exchange=venue,quoteType='EQUITY')
            self.assertEqual(fn(q,'CN'),expected)
            self.assertIsNone(fn(dict(q,quoteType='ETF'),'CN'))
            self.assertIsNone(fn(dict(q,exchange='HKG'),'CN'))
        for symbol,venue in [('000001.SS','SHH'),('900001.SS','SHH'),('200001.SZ','SHZ'),('510300.SS','SHH')]:
            self.assertIsNone(fn(dict(symbol=symbol,exchange=venue,quoteType='EQUITY'),'CN'))

    def test_listing_only_control_uses_market_not_company_domicile(self):
        local=['2889 TT Equity','BHP AU Equity','7203 JP Equity','600000 CH Equity']
        foreign=['3986 HK Equity','MSFT US Equity','000660 KS Equity']
        for target in local:
            names=local+foreign
            kept,_=E['_exchange_filter'](names,[target],True,'test',quiet=True)
            self.assertEqual(kept,[target])
            all_names,_=E['_exchange_filter'](names,[target],False,'test',quiet=True)
            self.assertEqual(set(all_names),set(names))
        kept,_=E['_exchange_filter'](['000001 CH Equity','688001 CH Equity','920001 CH Equity','0001 HK Equity'],
                                   ['600000 CH Equity'],True,'test',quiet=True)
        self.assertEqual(len(kept),3)  # CH denotes the mainland listing market

    def test_regional_backups_are_dated_and_usable_without_public_network(self):
        fetch=MagicMock(side_effect=TimeoutError('network unavailable'))
        fn=E['_public_equity_universe']
        for market,known in [('TW','2889 TT Equity'),('AU','BHP AU Equity'),
                             ('JP','7203 JP Equity'),('CN','000001 CH Equity')]:
            with patch.dict(fn.__globals__,{'_public_roster_bytes':fetch,
                '_yahoo_equity_universe':lambda *a,**k:self.fail('usable backup should avoid Yahoo retries')}):
                names,audit=fn(market)
            self.assertIn(known,names);self.assertEqual(len(names),len(set(names)))
            self.assertTrue(all(row['snapshot_asof'] and row['transport']=='bundled snapshot' for row in audit))
            if market=='CN':
                self.assertTrue({'600000 CH Equity','688001 CH Equity','920000 CH Equity'}<=set(names))
                self.assertGreater(len(names),5000)
        fetch.assert_not_called()

    def test_explicit_refresh_is_persisted_and_default_download_never_calls_public_sources(self):
        original=E['_public_equity_universe'];calls=[]
        source=dict(source='ASX',status='received',count=1,issuer_names={'NEW AU Equity':'New listing'},
                    retrieved_at='2026-10-29T01:00:00+00:00',transport='urllib')
        def live(market,refresh=False):
            calls.append((market,refresh));return ['NEW AU Equity'],[source]
        with tempfile.TemporaryDirectory() as directory,patch.dict(original.__globals__,{'HEDGE_CACHE_DIR':directory}):
            with patch.dict(original.__globals__,{'_public_equity_universe':live}):
                result=E['refresh_listing_directories'](['AU','AU'])
            self.assertEqual(calls,[('AU',True)])
            self.assertEqual(result['AU']['refreshed_sources'],['ASX'])
            with patch.dict(original.__globals__,{
                '_public_roster_bytes':lambda *a,**k:self.fail('normal download must be offline for directories'),
                '_yahoo_equity_universe':lambda *a,**k:self.fail('normal download must not query Yahoo')}):
                names,audit=original('AU')
            self.assertEqual(names,['NEW AU Equity'])
            self.assertEqual(audit[0]['snapshot_asof'],source['retrieved_at'])
            self.assertEqual(audit[0]['transport'],'saved directory')
            # A failed refresh must not overwrite or erase the last good source.
            with patch.dict(original.__globals__,{'_public_equity_universe':lambda *a,**k:([],[
                dict(source='ASX',status='unavailable',count=0,reason='timeout')])}):
                result=E['refresh_listing_directories']('AU')
            self.assertEqual(result['AU']['refreshed_sources'],[])
            self.assertEqual(original('AU')[0],['NEW AU Equity'])

    def test_unconfigured_market_reports_gap_instead_of_empty_success(self):
        names,audit=E['_public_equity_universe']('UNSUPPORTED')
        self.assertEqual(names,[])
        self.assertEqual(audit[0]['status'],'unavailable')
        self.assertIn('No independent directory',audit[0]['reason'])

    def test_trickling_directory_does_not_extend_deadline_or_return_partial_data(self):
        stream=MagicMock();stream.read1.side_effect=[b'partial',b'later',b'']
        with patch('time.monotonic',side_effect=[1.,2.,3.,9.]):
            with self.assertRaisesRegex(TimeoutError,'time budget'):
                E['_read_roster_body'](stream,8,0.)
        self.assertEqual(stream.read1.call_count,2)
        self.assertEqual(E['_read_roster_body'](io.BytesIO(b'complete'),100,float('inf')),b'complete')


if __name__=='__main__': unittest.main()
