"""Incremental additions must preserve existing histories and coverage boundaries."""
import contextlib,io,copy,unittest
from unittest.mock import patch,MagicMock
import numpy as np
import pandas as pd
from test_pca_research import E,OPTIONS
from test_pca_market_controls import global_fixture
from test_pca_peer_discovery import electronics


class IncrementalDownloadTests(unittest.TestCase):
    def setUp(self):
        self.data,_,_=global_fixture()
        d=self.data;target=d['target'];self.target=target
        d['peer_discovery_by_target']={target:{'classification_evidence':{
            t:electronics(ID_BB_COMPANY=str(i)) for i,t in enumerate(d['prices'])},'discovery_version':E['DISCOVERY_VERSION']}}
        d['fingerprint']={'exclude':[],'same_exchange_only':False}
        d['mktcap_hist']=pd.DataFrame(4000.,index=d['prices'].index,columns=d['prices'].columns)
        d['mktcap_hist_method']='historical local cap x dated FX'
        self.calls=[]
        def hist(session,names,start,end):
            self.calls.append(('prices',list(names),start,end))
            return pd.DataFrame({t:d['prices'][target]*(1+0.0001*np.arange(len(d['prices']))) for t in names if not t.startswith('MISSING')})
        def refs(session,names,fields,**kwargs):
            self.calls.append(('refs',list(names),list(fields)))
            return {t:dict(electronics(ID_BB_COMPANY='NEW-'+t),CRNCY='USD' if ' US ' in t else 'HKD',
                          CRNCY_ADJ_MKT_CAP=4000.,VOLUME_AVG_30D=500000.,PX_BID=99.,PX_ASK=100.) for t in names}
        def field(session,names,field,start,end,**kwargs):
            self.calls.append(('field',list(names),field))
            return pd.DataFrame(10000. if field=='CUR_MKT_CAP' else .128,index=d['prices'].index,columns=names)
        self.stubs={'bbg_hist':hist,'bbg_ref_multi':refs,'bbg_hist_field':field,
                    'auto_discover_universe':MagicMock(side_effect=AssertionError('must not rescan universe')),
                    '_public_equity_universe':MagicMock(side_effect=AssertionError('must not download directory')),
                    '_pit_index_membership':MagicMock(side_effect=AssertionError('must retain existing memberships'))}

    def add(self,names,**kwargs):
        with patch.dict(E['_download_added_tickers_impl'].__globals__,self.stubs),contextlib.redirect_stdout(io.StringIO()):
            return E['download_added_tickers'](self.data,names,session=MagicMock(),cache=False,**kwargs)

    def test_only_new_prices_and_metadata_are_requested_and_original_is_unchanged(self):
        before=copy.deepcopy(self.data);new='1989NEW HK Equity'
        out=self.add([self.target,new,new])
        pd.testing.assert_frame_equal(self.data['prices'],before['prices'])
        pd.testing.assert_frame_equal(out['prices'][before['prices'].columns],before['prices'])
        pd.testing.assert_frame_equal(out['mktcap_hist'][before['mktcap_hist'].columns],before['mktcap_hist'])
        self.assertEqual([c[1] for c in self.calls if c[0]=='prices'],[[new]])
        for call in self.calls:
            self.assertFalse(set(call[1])&set(before['prices'].columns))
        self.assertEqual(out['last_incremental_download']['already_available'],[self.target])
        self.assertIn(new,out['peer_tickers_by_target'][self.target])
        self.assertIn(new,out['sector_stock_tickers_by_target'][self.target])
        self.assertIn(new,out['execution_snapshot']);self.assertIn(new,out['mktcap_usd_mm'])
        self.assertEqual(out.get('downloaded_at'),before.get('downloaded_at'))
        self.assertIn('Added tickers: 1 downloaded',out['download_progress']['summary'])
        # A valid added peer can actually be used as a required basket leg.
        with contextlib.redirect_stdout(io.StringIO()):
            result=E['find_best_hedge'](self.target,data=out,**dict(OPTIONS,candidate_scope='related',force_include=[new],sample_window='1m'))
        self.assertIn(new,result['weights'].index)

    def test_noop_has_no_vendor_calls_and_duplicate_alias_does_not_add_columns(self):
        before=self.data['prices'].copy()
        out=self.add([self.target,self.target.replace(' Equity','')])
        self.assertEqual(self.calls,[])
        pd.testing.assert_frame_equal(out['prices'],before)
        self.assertEqual(out['last_incremental_download']['status'],'nothing to download')

    def test_unavailable_alias_is_replaced_and_outside_dates_are_not_appended(self):
        self.data['prices']['1989NEW HK']=np.nan
        first,last=self.data['prices'].index[[0,-1]]
        original=self.stubs['bbg_hist']
        def hist(*args):
            frame=original(*args)
            frame.loc[first-pd.Timedelta(days=1)]=100.
            frame.loc[last+pd.Timedelta(days=1)]=200.
            return frame
        self.stubs['bbg_hist']=hist
        out=self.add(['1989NEW HK Equity'])
        self.assertNotIn('1989NEW HK',out['prices'])
        self.assertIn('1989NEW HK Equity',out['prices'])
        self.assertEqual(out['prices'].index.min(),first)
        self.assertEqual(out['prices'].index.max(),last)

    def test_partial_prices_keep_success_and_missing_names_visible(self):
        out=self.add(['1989NEW HK Equity','MISSING HK Equity'])
        self.assertIn('1989NEW HK Equity',out['prices'])
        self.assertNotIn('MISSING HK Equity',out['prices'])
        self.assertEqual(out['last_incremental_download']['missing'],['MISSING HK Equity'])
        self.assertIn('MISSING HK Equity',out['force_download_missing'])
        self.assertEqual(out['download_progress']['status'],'warning')

    def test_no_prices_or_bad_request_retains_original_dataset(self):
        before=copy.deepcopy(self.data)
        for names,kwargs in [(['MISSING HK Equity'],{}),(['1989'],{}),
                             (['NEW US Equity'],{'same_exchange_only':True}),
                             (['1989NEW HK Equity'],{'exclude':['1989NEW']})]:
            with self.assertRaises(ValueError): self.add(names,**kwargs)
        pd.testing.assert_frame_equal(self.data['prices'],before['prices'])
        self.assertEqual(self.data['peer_tickers_by_target'],before['peer_tickers_by_target'])

    def test_adding_foreign_stock_to_local_cache_marks_partial_expansion(self):
        self.data['same_exchange_only_download']=True
        self.data['prices']=self.data['prices'].drop(columns=['PEER US Equity'])
        for ticker in ['NEW US Equity','1989NEW HK Equity']:
            out=self.add([ticker],same_exchange_only=False)
            self.assertFalse(out['same_exchange_only_download'])
            self.assertTrue(out['global_peer_download_incomplete'])
            self.assertIn('remaining global peers were not downloaded',out['download_progress']['notices'][0])
            with contextlib.redirect_stdout(io.StringIO()):
                result=E['find_best_hedge'](self.target,data=out,**dict(OPTIONS,candidate_scope='related',force_include=[ticker],sample_window='1m'))
            self.assertIn(ticker,result['weights'].index)

    def test_nonpeer_is_downloaded_but_not_automatically_promoted(self):
        original=self.stubs['bbg_ref_multi']
        def refs(*args,**kwargs):
            values=original(*args,**kwargs)
            for r in values.values(): r.update(GICS_SECTOR_NAME='Energy',BICS_LEVEL_1_SECTOR_NAME='Energy')
            return values
        self.stubs['bbg_ref_multi']=refs
        out=self.add(['UNRELATED HK Equity'])
        self.assertIn('UNRELATED HK Equity',out['prices'])
        self.assertNotIn('UNRELATED HK Equity',out['peer_tickers_by_target'][self.target])
        self.assertNotIn('UNRELATED HK Equity',out['sector_stock_tickers_by_target'][self.target])

    def test_button_is_in_data_and_uses_both_force_fields(self):
        with contextlib.redirect_stdout(io.StringIO()): state=E['hedge_ui'](self.data)
        w=state['widgets']
        def flatten(x): return [x]+[a for child in getattr(x,'children',()) for a in flatten(child)]
        self.assertIn(w['add_tickers_button'],flatten(w['data_tab']))
        self.assertIn('force_include',w);self.assertIn('force_download',w)
        call=MagicMock(return_value=dict(self.data,last_incremental_download={}))
        with contextlib.redirect_stdout(io.StringIO()),patch.dict(E['hedge_ui'].__globals__,{'download_added_tickers':call}):
            w['target'].value=self.target
            w['force_include'].value='1989NEW HK Equity'
            w['force_download'].value='NEW US Equity'
            state['result']={'old':'result'}
            w['add_tickers_button'].click()
        call.assert_called_once()
        self.assertEqual(set(call.call_args[0][1]),{'1989NEW HK Equity','NEW US Equity'})
        self.assertIsNone(state['result'])
        for force,download in [('1989NEW HK Equity',''),('','NEW US Equity')]:
            call.reset_mock()
            with contextlib.redirect_stdout(io.StringIO()),patch.dict(E['hedge_ui'].__globals__,{'download_added_tickers':call}):
                w['force_include'].value=force
                w['force_download'].value=download
                w['add_tickers_button'].click()
            call.assert_called_once()
            self.assertEqual(call.call_args[0][1],[force or download])


if __name__=='__main__': unittest.main()
