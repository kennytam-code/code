"""Presentation must preserve data, failure status and complete diagnostics."""
import contextlib,io,unittest
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


if __name__=='__main__': unittest.main()
