"""Presentation must preserve data, failure status and complete diagnostics."""
import contextlib,io,unittest,copy
import numpy as np
from unittest.mock import patch
import pandas as pd
from test_pca_research import E,fixture,run


class PresentationTests(unittest.TestCase):
    def test_download_panel_streams_stages_without_raw_output_and_keeps_log(self):
        data=fixture(n=40);states=[];visible=io.StringIO()
        def download(*args,progress=None,**kwargs):
            progress('connect','Ready',status='done')
            progress('discovery','Checking 200 records',source=('TEST','TEST: 200 candidates'))
            print('vendor technical detail')
            progress('prices','10 instruments')
            print('  ⚠ incomplete source <test>')
            progress('caps','Caps received')
            progress('trading','Quotes received')
            progress('cache','Not requested',status='skipped')
            return data
        fn=E['download_hedge_data']
        with patch.dict(fn.__globals__,{'_download_hedge_data_impl':download}),contextlib.redirect_stdout(visible):
            result=fn(data['target'],progress=states.append)
        self.assertEqual(visible.getvalue(),'')
        self.assertIn('vendor technical detail',result['download_log'])
        self.assertEqual(states[-1]['status'],'warning')
        rows={r['id']:r for r in states[-1]['stages']}
        self.assertEqual(rows['prices']['status'],'warning');self.assertEqual(rows['cache']['status'],'skipped')
        html=E['_download_progress_html'](states[-1])
        self.assertIn('Detailed download log',html);self.assertIn('&lt;test&gt;',html)
        self.assertNotIn('<test>',html)
        self.assertEqual(states[0]['stages'][0]['status'],'running')
        self.assertIs(result['prices'],data['prices'])

    def test_download_failure_preserves_log_and_never_claims_completion(self):
        states=[]
        def download(*args,progress=None,**kwargs):
            progress('prices','Reading prices');print('request detail')
            raise RuntimeError('vendor unavailable')
        fn=E['download_hedge_data']
        with patch.dict(fn.__globals__,{'_download_hedge_data_impl':download}),self.assertRaisesRegex(RuntimeError,'vendor unavailable'):
            fn('T HK Equity',progress=states.append)
        self.assertEqual(states[-1]['status'],'failed')
        self.assertIn('request detail',states[-1]['log'])
        self.assertEqual(next(r for r in states[-1]['stages'] if r['id']=='prices')['status'],'failed')

    def test_console_download_is_compact_and_reports_warnings(self):
        data=fixture(n=40);visible=io.StringIO()
        def download(*args,progress=None,**kwargs):
            progress('prices','10 names');print('raw request 1');print('raw request 2')
            print('⚠ test source unavailable');return data
        fn=E['download_hedge_data']
        with patch.dict(fn.__globals__,{'_download_hedge_data_impl':download}),contextlib.redirect_stdout(visible):
            fn(data['target'])
        output=visible.getvalue()
        self.assertIn('Price history',output);self.assertIn('test source unavailable',output)
        self.assertNotIn('raw request',output)

    def test_result_layout_preserves_values_positions_and_all_sections(self):
        result=run(sample_window='3m')
        blocks=E['_report_blocks'](result);titles=[b['text'] for b in blocks if b['kind']=='section']
        self.assertLess(titles.index('Alternative baskets'),titles.index('Residual risk review'))
        self.assertIn('Method comparison',titles)
        html=E['_report_html'](result)
        self.assertIn('CURRENT FIT R²',html);self.assertIn('HISTORICAL TEST R²',html)
        self.assertIn('basket-grid',html)
        self.assertIn('<details id="universe-coverage-and-execution">',html)
        self.assertEqual(html.count('<details'),html.count('</details>'))
        for row in result['basket_comparison']:
            if row['selected']: continue
            for ticker,weight in row['weights'].items():
                self.assertIn(ticker,html)
                self.assertIn(('SHORT ' if weight>0 else 'LONG ')+f'{abs(weight)*100:.1f}',html)
        self.assertIn(f'{result["in_sample_r2"]:.3f}',html)
        self.assertIn(f'{result["ticket"]["quality_r2"]:.3f}',html)


    def test_tracking_charts_use_entire_selected_window_and_match_report_metrics(self):
        data=fixture()
        for window in ('1m','2m','3m','6m','1y',('2025-04-01','2025-07-01')):
            with self.subTest(window=window):
                result=run(data,sample_window=window)
                tracking=E['_tracking_chart_data'](result)
                current=tracking['current']
                self.assertEqual(current['status'],'ok',current)
                self.assertTrue(current['parts'][0].index.equals(result['returns'].index))
                self.assertEqual(current['rows'],result['current_fit_rows'])
                self.assertAlmostEqual(current['r2'],result['in_sample_r2'])
                self.assertAlmostEqual(current['vol_reduction'],result['current_fit_risk']['vol_reduction'])
                figures=E['_report_figures'](result)
                self.assertIn('target versus basket',figures[0][0])
                np.testing.assert_allclose(figures[0][1].axes[0].lines[1].get_ydata(),
                    (result.get('analysis_returns',result['returns'])[result['weights'].index]@result['weights']).cumsum()*100)
                for _,fig in figures: E['plt'].close(fig)
                if result['method_validation']['folds']:
                    self.assertEqual(tracking['test']['status'],'ok',tracking['test'])
                    self.assertAlmostEqual(tracking['test']['r2'],result['method_validation']['methods']['selected']['r2'])

    def test_frozen_chart_ignores_current_weights_and_keeps_training_intercept(self):
        result=run(sample_window='3m');original=E['_tracking_chart_data'](result)['test']
        altered=copy.deepcopy(result);altered['weights']*=1.5
        changed=E['_tracking_chart_data'](altered)
        self.assertEqual(changed['current']['status'],'unavailable')
        pd.testing.assert_frame_equal(original['parts'][0],changed['test']['parts'][0])
        fold=result['method_validation']['folds'][0];method=fold['methods']['selected']
        frame=result['returns'].reindex(pd.DatetimeIndex(fold['test_dates']))
        actual=frame[method['weights'].index]@method['weights']
        np.testing.assert_allclose(actual,original['parts'][0]['basket'])
        np.testing.assert_allclose(actual+method['intercept'],original['parts'][0]['prediction'])

    def test_missing_or_overlapping_tests_never_produce_partial_good_chart(self):
        original=run(sample_window='3m')
        for failure in ('nan','short','intercept','overlap','train_overlap','bad_score'):
            result=copy.deepcopy(original);fold=result['method_validation']['folds'][0]
            if failure=='nan': fold['methods']['selected']['spread_returns'][0]=np.nan
            if failure=='short': fold['target_returns'].pop()
            if failure=='intercept': fold['methods']['selected']['intercept']+=.1
            if failure=='overlap': result['method_validation']['folds'].append(copy.deepcopy(fold))
            if failure=='train_overlap': fold['train_end']=fold['test_dates'][0]
            if failure=='bad_score': result['method_validation']['methods']['selected']['r2']+=.1
            with self.subTest(failure=failure):
                tracking=E['_tracking_chart_data'](result)
                self.assertEqual(tracking['current']['status'],'ok')
                self.assertEqual(tracking['test']['status'],'unavailable')
                self.assertNotIn('parts',tracking['test'])

    def test_two_session_paths_do_not_double_count_and_no_test_is_invented(self):
        result=run(sample_window='2m',async_adjust=True)
        figures=E['_report_figures'](result)
        path=E['_tracking_chart_data'](result)['current']['parts'][0].iloc[::2]
        np.testing.assert_allclose(figures[0][1].axes[0].lines[0].get_ydata(),path['target'].cumsum()*100)
        self.assertEqual(len(figures[0][1].axes[1].lines[0].get_ydata()),len(result['returns']))
        for _,fig in figures: E['plt'].close(fig)
        result['method_validation']={'folds':[]}
        figures=E['_report_figures'](result)
        self.assertFalse(any('Earlier frozen baskets' in name for name,_ in figures))
        self.assertTrue(any('Historical test chart unavailable' in t.get_text() for t in figures[0][1].texts))
        for _,fig in figures: E['plt'].close(fig)


if __name__=='__main__': unittest.main()
