"""Exercise actual form actions so stale/partial baskets cannot be exported."""
import contextlib
import io
import unittest
from unittest.mock import MagicMock, patch
from test_pca_research import E, fixture


def flatten(widget):
    return [widget] + [item for child in getattr(widget, 'children', ()) for item in flatten(child)]


class UIResultStateTests(unittest.TestCase):
    def setUp(self):
        data = fixture()
        data['fingerprint'] = {'instrument_map': E['_INSTRUMENT_MAP_HASH'],
                               'discovery_version': E['DISCOVERY_VERSION']}
        with contextlib.redirect_stdout(io.StringIO()):
            self.state = E['hedge_ui'](data)
        self.widgets = self.state['widgets']
        self.widgets['compare_windows'].value = ()
        self.previous = {'old': 'previous basket'}
        self.state.update(result=self.previous, report_text='previous report',
                          code='previous code', comparison={'old': 'comparison'})
        self.export = MagicMock(return_value='report.docx')
        self.diagnostics = MagicMock(return_value='diagnostics.zip')

    def button(self, description):
        return next(w for w in flatten(self.widgets['form']) if getattr(w, 'description', None) == description)

    def click(self, description, **replacements):
        with contextlib.redirect_stdout(io.StringIO()), patch.dict(E['hedge_ui'].__globals__, replacements):
            self.button(description).click()

    def assert_no_result_can_be_exported(self):
        self.assertIsNone(self.state['result'])
        self.assertIsNone(self.state['comparison'])
        self.assertEqual(self.state['report_text'], '')
        self.assertEqual(self.state['code'], '')
        self.click('Export Word', export_result=self.export)
        self.click('Export diagnostics', export_hedge_diagnostics=self.diagnostics)
        self.export.assert_not_called()
        self.diagnostics.assert_not_called()
        self.assertFalse(self.state.get('busy'))

    def test_failed_full_run_blocks_previous_report_and_diagnostics(self):
        run = MagicMock(side_effect=ValueError('required stock has no history'))
        self.click('RUN HEDGE', find_best_hedge=run)
        run.assert_called_once()
        self.assert_no_result_can_be_exported()

    def test_listing_update_is_separate_and_does_not_download_or_replace_prices(self):
        refresh=MagicMock(return_value={'TW':{'count':1994,'refreshed_sources':['TWSE'],'audit':[]}})
        download=MagicMock(side_effect=AssertionError('directory refresh must not download prices'))
        original=self.state['data']
        self.click('Update listing lists',refresh_listing_directories=refresh,download_hedge_data=download)
        self.assertEqual(refresh.call_args[0][0],['TW'])
        self.assertIs(self.state['data'],original)
        self.assertIs(self.state['result'],self.previous)
        download.assert_not_called()
        self.assertFalse(self.state.get('busy'))

    def test_preflight_rejection_clears_previous_analysis(self):
        run = MagicMock()
        self.widgets['target'].value = 'OTHER US Equity'
        self.click('RUN HEDGE', find_best_hedge=run)
        run.assert_not_called()
        self.assert_no_result_can_be_exported()

    def test_failed_window_comparison_clears_partial_primary_result(self):
        self.widgets['compare_windows'].value = ('1m', '2m')
        compare = MagicMock(side_effect=ValueError('comparison failed'))
        self.click('RUN HEDGE', find_best_hedge=MagicMock(return_value={'new': 'primary'}),
                   compare_history_windows=compare, transcript_text=lambda: 'new primary report')
        compare.assert_called_once()
        self.assert_no_result_can_be_exported()

    def test_interrupted_comparison_cannot_leave_primary_result_exportable(self):
        self.widgets['compare_windows'].value = ('1m', '2m')
        with self.assertRaises(KeyboardInterrupt):
            self.click('RUN HEDGE', find_best_hedge=MagicMock(return_value={'new': 'primary'}),
                       compare_history_windows=MagicMock(side_effect=KeyboardInterrupt),
                       transcript_text=lambda: 'partial report')
        self.assert_no_result_can_be_exported()

    def test_successful_rerun_exports_new_result_and_clears_previous_comparisons(self):
        result = {'new': 'basket'}
        self.click('RUN HEDGE', find_best_hedge=MagicMock(return_value=result),
                   transcript_text=lambda: 'new report')
        self.assertIs(self.state['result'], result)
        self.assertIsNone(self.state['comparison'])
        self.click('Export Word', export_result=self.export)
        self.export.assert_called_once()
        self.assertIs(self.export.call_args[0][0], result)
        self.assertEqual(self.export.call_args[0][1], 'new report')

    def test_rehedge_uses_pinned_previous_config_but_clears_it_on_failure(self):
        quick = MagicMock(side_effect=ValueError('new return window invalid'))
        self.click('RE-HEDGE (fast)', quick_rehedge=quick)
        quick.assert_called_once()
        self.assertIs(quick.call_args[0][2], self.previous)
        self.assert_no_result_can_be_exported()

    def test_successful_rehedge_uses_pinned_config_and_exports_new_result(self):
        result = {'new': 'rehedged basket'}
        quick = MagicMock(return_value=result)
        self.click('RE-HEDGE (fast)', quick_rehedge=quick, transcript_text=lambda: 'rehedged report')
        self.assertIs(quick.call_args[0][2], self.previous)
        self.click('Export Word', export_result=self.export)
        self.assertIs(self.export.call_args[0][0], result)
        self.assertEqual(self.export.call_args[0][1], 'rehedged report')
        self.assertIsNone(self.state['comparison'])

    def test_form_seeded_with_new_data_cannot_export_previous_result(self):
        self.state['loaded_from'] = 'old-cache.pkl'
        with contextlib.redirect_stdout(io.StringIO()):
            self.state = E['hedge_ui'](fixture(seed=24))
        self.widgets = self.state['widgets']
        self.assertIsNone(self.state['loaded_from'])
        self.assert_no_result_can_be_exported()

    def test_show_code_reuses_incrementally_extended_data_without_downloading(self):
        data = {'prices': 'existing prices including explicitly added ticker'}
        analyze = MagicMock(return_value={'new': 'basket'})
        download = MagicMock(side_effect=AssertionError('must not redownload'))
        code = E['_ui_code']('2476 HK Equity', '3m', {'force_include': ['1989 HK Equity']}, None)
        namespace = dict(UI_STATE={'data': data}, find_best_hedge=analyze, download_hedge_data=download)
        exec(compile(code, '<show code>', 'exec'), namespace)
        self.assertIs(analyze.call_args[1]['data'], data)
        self.assertEqual(analyze.call_args[1]['force_include'], ['1989 HK Equity'])
        download.assert_not_called()

    def test_show_code_preserves_windows_cache_path_with_quotes(self):
        path = "C:\\Users\\O'Brien\\hedge.pkl"
        load = MagicMock(return_value=self.state['data'])
        code = E['_ui_code']('2476 HK Equity', '1m', {}, path)
        exec(compile(code, '<show code>', 'exec'), dict(load_hedge_data=load, find_best_hedge=MagicMock()))
        load.assert_called_once_with(path)


if __name__ == '__main__':
    unittest.main()
