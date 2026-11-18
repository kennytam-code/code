"""Integration review of the unchanged attachment and add-on. No live services."""
import ast
import base64
import builtins
import copy
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import types
import unittest
from contextlib import ExitStack, redirect_stdout
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import test_second_cell as addon_tests

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'first_cell_original.py').read_text(encoding='utf-8')
ADDON = (HERE / 'second_cell.py').read_text(encoding='utf-8')
spec = importlib.util.spec_from_file_location('original_ipo_review', HERE / 'first_cell_original.py')
first = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = first
spec.loader.exec_module(first)
second = addon_tests.m
CALENDAR = first._decode_source(first.HOLIDAYS_URL, (HERE / 'review_sources/holiday_calendar.json').read_bytes())
DAY = date(2026, 11, 15)


def short_html(day, codes):
    rows = ''.join(f'<tr><td>{i}</td><td>{code}</td><td>{name}</td></tr>'
                   for i, (code, name) in enumerate(codes.items(), 1))
    return (f'<html><body>Effective Date: {day:%d/%m/%Y}<table>'
            '<tr><th>No.</th><th>Stock Code</th><th>Stock Short Name</th></tr>' + rows + '</table></body></html>')


class SourceClient:
    def __init__(self, versions, module=first):
        self.module = module
        self.pages = {module.SHORT_URL.format(day=d): short_html(d, codes) for d, codes in versions}
        self.manual_sources, self.cached_sources, self.cache = {}, {}, {}
        self.calls = []

    def text(self, url):
        self.calls.append(url)
        if url == self.module.HOLIDAYS_URL:
            text = CALENDAR
        elif 'ds20' in url:
            if url not in self.pages:
                raise self.module.PageMissing('Fixture 404')
            text = self.pages[url]
        else:
            text = '解禁總金額 = fixture 更新：' + datetime.now(first.HK).strftime('%d/%m/%Y %H:%M')
        self.cache[url] = text
        return text


class ImmediateExecutor:
    """Exercise the original build pipeline sequentially with deterministic fixtures."""
    def __init__(self, **kwargs): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def submit(self, fn, *args):
        try:
            value = fn(*args)
            return types.SimpleNamespace(result=lambda: value)
        except Exception as exc:
            def fail(error=exc): raise error
            return types.SimpleNamespace(result=fail)


def fixtures(module, day, versions):
    phip = module.PHIP('fixture-phip', 'Fixture Filing', 'Main Board', 'Active', day.isoformat(),
                       'Fixture filing title', ['https://example.com/fixture'])
    rows = [module.Lockup(code, 'Fixture ' + code, day.isoformat(), 'Cornerstone', '2', 'HKD100000000',
                          '12.5%', 'https://example.com/fixture', '12', 'cornerstone', '', '+5%',
                          'https://example.com/fixture') for code in ('00001', '00002', '00003')]
    # External source parsing/data retrieval is replaced; core build, NEW, state,
    # rendering, MIME, atomic writes and original run_now all execute unchanged.
    return {'Client': lambda: SourceClient(versions, module),
            'ThreadPoolExecutor': ImmediateExecutor,
            'fetch_phip': lambda *args: [copy.deepcopy(phip)],
            'parse_ipos': lambda *args: [module.IPO('00001', 'Fixture IPO', [], [], [])],
            'parse_lockups': lambda document, month: rows if month == day.strftime('%Y%m') else [],
            'BLOOMBERG_ENABLED': False, 'OPEN_OUTLOOK': False,
            'SHOW_NOTEBOOK_PREVIEW_IF_NO_OUTLOOK': False, 'HTTPS_PROXY_URL': ''}


def report_for(day=DAY, versions=None):
    if versions is None:
        versions = [(date(2026, 11, 6), {'00001': 'A', '00003': 'C'}),
                    (date(2026, 11, 10), {'00001': 'A', '00002': 'B'})]
    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        for name, value in fixtures(first, day, versions).items():
            stack.enter_context(patch.object(first, name, value))
        state = first.State(Path(directory) / 'state.sqlite3')
        try:
            report = first.build_report(first.Client(), state, day, 'draft', True, False, 45)
        finally:
            state.close()
    return report


class FirstCellNewTests(unittest.TestCase):
    def test_live_downloaded_hkex_and_holiday_formats(self):
        self.assertEqual(first.recent_trading_dates(CALENDAR, DAY), [date(2026, 11, d) for d in range(9, 14)])
        for stamp in ('20261106', '20261110'):
            day = datetime.strptime(stamp, '%Y%m%d').date()
            url = first.SHORT_URL.format(day=day)
            text = first._decode_source(url, (HERE / 'review_sources' / ('short_' + stamp + '.html')).read_bytes())
            parsed = first.parse_short_list(text, url, DAY)
            self.assertEqual(parsed.effective, day.isoformat())
            self.assertEqual(len(parsed.securities), 1267)

    def test_actual_build_new_yes_no_and_second_cell_agree(self):
        report = report_for()
        self.assertEqual(report['added'], {'00002': 'B'})
        self.assertEqual(report['removed'], {'00003': 'C'})
        self.assertEqual([first.eligibility(row, report)[0] for row in report['lockups']], ['YES', 'NEW', 'NO'])
        rows, _, _ = second._lu_select(report)
        self.assertEqual([(r['code'], r['shortable']) for r in rows], [('00001', 'YES'), ('00002', 'NEW')])

    def test_new_last_day_then_expires(self):
        versions = [(date(2026, 11, 6), {'00001': 'A'}),
                    (date(2026, 11, 9), {'00001': 'A', '00002': 'B'})]
        for day, expected in [(date(2026, 11, 13), 'NEW'), (DAY, 'NEW'), (date(2026, 11, 16), 'YES')]:
            report = report_for(day, versions)
            self.assertEqual(first.eligibility({'code': '00002'}, report)[0], expected)

    def test_removal_readdition_and_rename(self):
        versions = [(date(2026, 11, 6), {'00001': 'A', '00002': 'B'}),
                    (date(2026, 11, 9), {'00001': 'RENAMED', '00003': 'C'}),
                    (date(2026, 11, 10), {'00001': 'RENAMED', '00002': 'B'})]
        report = report_for(versions=versions)
        self.assertEqual(report['added'], {'00002': 'B'})
        self.assertEqual(report['removed'], {'00003': 'C'})
        self.assertEqual(len(report['short_changes']), 4)
        self.assertEqual(first.eligibility({'code': '00001'}, report)[0], 'YES')
        self.assertEqual(first.eligibility({'code': '00002'}, report)[0], 'NEW')
        self.assertEqual(first.eligibility({'code': '00003'}, report)[0], 'NO')

    def test_existing_stocks_not_all_new_on_first_run(self):
        report = report_for(versions=[(date(2026, 11, 6), {'00001': 'A', '00002': 'B'})])
        self.assertEqual(report['added'], {})
        self.assertEqual(report['short_changes'], [])
        self.assertEqual(first.eligibility({'code': '00002'}, report)[0], 'YES')

    def test_holiday_and_year_boundary(self):
        days = first.recent_trading_dates(CALENDAR, date(2026, 10, 1))
        self.assertNotIn(date(2026, 10, 1), days)
        self.assertTrue(all(d.weekday() < 5 for d in days))
        days = first.recent_trading_dates(CALENDAR, date(2026, 1, 2))
        self.assertEqual(days, [date(2025, 12, 24), date(2025, 12, 29), date(2025, 12, 30),
                               date(2025, 12, 31), date(2026, 1, 2)])
        with self.assertRaises(first.SourceError):
            first.recent_trading_dates('{"vcalendar": []}', DAY)

    def test_missing_baseline_and_bad_source_fail_closed(self):
        client = SourceClient([(date(2026, 11, 10), {'00001': 'A'})])
        with self.assertRaisesRegex(first.SourceError, 'baseline'):
            first.fetch_short_history(client, DAY, date(2026, 11, 9), lookback=10)
        for exc in (first.SourceError('invalid HTML'), first.SourceNetworkError('blocked')):
            client = types.SimpleNamespace(text=Mock(side_effect=exc))
            with self.assertRaises(type(exc)):
                first.fetch_short_history(client, DAY, date(2026, 11, 9))
            self.assertEqual(client.text.call_count, 1)
        page = short_html(date(2026, 11, 10), {'00001': 'A'})
        url = first.SHORT_URL.format(day=date(2026, 11, 10))
        for broken in (page.replace('</html>', ''), page.replace('<td>1</td>', '<td>2</td>'),
                       page.replace('10/11/2026', '11/11/2026')):
            with self.assertRaises(first.SourceError):
                first.parse_short_list(broken, url, DAY)
        item = first.parse_short_list(page, url, DAY)
        with self.assertRaises(first.SourceError): first.short_history_changes([item, item])

    def test_phip_new_distinct_from_shortable_new_and_same_day_rerun(self):
        report = report_for()
        with tempfile.TemporaryDirectory() as directory:
            state = first.State(Path(directory) / 'state.sqlite3')
            try:
                snap = first.annotate_section_changes(report, state.previous_sections(DAY, 'draft'))
                self.assertFalse(report['phip'][0]['new'])
                state.save(DAY, 'draft', first.ShortList(**report['short']), [], None, snap, report['generated_at'])
                new_phip = dict(report['phip'][0], key='another-filing', company='Second fixture filing')
                report['phip'].append(new_phip)
                snap = first.annotate_section_changes(report, state.previous_sections(DAY, 'draft'))
                self.assertEqual([r['new'] for r in report['phip']], [False, True])
                self.assertEqual(first.eligibility({'code': '00002'}, report)[0], 'NEW')
                state.save(DAY, 'draft', first.ShortList(**report['short']), [], None, snap, report['generated_at'])
                first.annotate_section_changes(report, state.previous_sections(DAY, 'draft'))
                self.assertEqual([r['new'] for r in report['phip']], [False, False])
                self.assertEqual(first.eligibility({'code': '00002'}, report)[0], 'NEW')
            finally:
                state.close()


class SameKernelTests(unittest.TestCase):
    def test_addon_with_original_bloomberg_client_and_mock_api(self):
        """Real original connection class and add-on request parser, mock service."""
        today = datetime.now(first.HK).date()
        requests, sessions = [], []
        class Options:
            DAPI = 1
            def __getattr__(self, name): return lambda value: None
        class Queue:
            def nextEvent(self, timeout): return self.event
        class Session:
            def __init__(self, options):
                self.stopped = False
                sessions.append(self)
            def start(self): return True
            def openService(self, name): return name == '//blp/refdata'
            def getService(self, name): return self
            def createRequest(self, kind):
                req = addon_tests.Request(); req.kind = kind
                return req
            def sendRequest(self, req, eventQueue):
                requests.append(req)
                securities = req.value['securities']
                if req.kind == 'ReferenceDataRequest':
                    messages = [{'securityData': [{'security': s, 'sequenceNumber': i,
                        'fieldData': {'LAST_PRICE': 7.8 if s == 'USDHKD Curncy' else 12, 'CRNCY': 'HKD', 'LAST_UPDATE_DT': today,
                                      'EQY_INIT_PO_SH_PX': 8}} for i, s in enumerate(securities)]}]
                else:
                    messages = [{'securityData': {'security': s, 'sequenceNumber': i,
                        'fieldData': [{'date': target, 'PX_LAST': 10}
                                      for target in second._lu_horizons(today).values()]}}
                                for i, s in enumerate(securities)]
                eventQueue.event = addon_tests.Event(2, messages)
                return 1
            def stop(self): self.stopped = True
        api = types.ModuleType('blpapi')
        api.SessionOptions, api.Session, api.EventQueue = Options, Session, Queue
        api.Event = types.SimpleNamespace(REQUEST_STATUS=3, PARTIAL_RESPONSE=1, RESPONSE=2)
        report = report_for()
        report['day'] = today.isoformat()
        report['months'] = first.month_keys(today)
        for row in report['lockups']:
            row['expiry'] = today.isoformat()
            row['avg_turnover_20d_hkd'] = '39000000'
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {'blpapi': api}), redirect_stdout(io.StringIO()):
            env = dict(first.__dict__, BLOOMBERG_ENABLED=True, SHOW_NOTEBOOK_PREVIEW_IF_NO_OUTLOOK=False,
                       LOCKUP_EMAIL_CHECK_A_SHARES=False)
            result = second._lu_run({'report': report, 'email_html': Path(directory) / 'first.html'}, env, False)
        self.assertEqual(len(requests), 3)
        self.assertEqual(len(sessions), 1)
        self.assertTrue(sessions[0].stopped)
        self.assertEqual(requests[0].value['securities'], ['1 HK Equity', '2 HK Equity'])
        self.assertEqual(requests[2].value['securities'], ['USDHKD Curncy'])
        self.assertEqual(requests[2].value['fields'], ['LAST_PRICE', 'LAST_UPDATE_DT'])
        for row in result['rows']:
            self.assertEqual(row['avg_turnover_20d_hkd'], '39000000')
            self.assertEqual(row['avg_turnover_20d_usd'], '5.00000E+6')
            self.assertEqual(row['price_performance']['errors'], {})
            self.assertEqual(row['price_performance']['ipo_change_pct'], '50.0')
            self.assertEqual(row['price_performance']['7D']['change_pct'], '20.0')
            self.assertEqual(row['price_performance']['1M']['change_pct'], '20.0')

    def test_exact_both_cells_shared_namespace_full_draft_pipeline(self):
        """Execute the exact two sources, patching ONLY service edges before cell 1 runs."""
        today = datetime.now(first.HK).date()
        days = first.recent_trading_dates(CALENDAR, today)
        versions = [(days[0] - timedelta(days=1), {'00001': 'A', '00003': 'C'}),
                    (days[1], {'00001': 'A', '00002': 'B'})]
        notebook = types.ModuleType('__main__')
        env = notebook.__dict__
        guard_line = ast.parse(SOURCE).body[-1].body[0].lineno
        installed = []
        with tempfile.TemporaryDirectory() as directory:
            def trace(frame, event, arg):
                if event == 'line' and frame.f_code.co_filename == 'exact_first_cell' and frame.f_lineno == guard_line:
                    patches = fixtures(notebook, today, versions)
                    patches.update(ROOT=Path(directory), EMAIL_TO='fixture@example.com', EMAIL_CC='fixturecc@example.com')
                    env.update(patches)
                    installed.append(True)
                    sys.settrace(None)
                return trace
            with patch.dict(sys.modules, {'__main__': notebook}), redirect_stdout(io.StringIO()):
                previous_trace = sys.gettrace()
                try:
                    sys.settrace(trace)
                    exec(compile(SOURCE, 'exact_first_cell', 'exec'), env)
                finally:
                    sys.settrace(previous_trace)
                self.assertEqual(installed, [True])
                original = env['LAST_DRAFT']
                self.assertTrue(original['eml'].is_file())
                before_report = copy.deepcopy(original['report'])
                before_globals = dict(env)
                original_bytes = {p: p.read_bytes() for p in Path(directory).rglob('*') if p.is_file()}
                exec(compile(ADDON, 'exact_second_cell', 'exec'), env)
                delivered = env['LAST_LOCKUP_DRAFT']
                self.assertIs(env['LAST_DRAFT'], original)
                self.assertEqual(original['report'], before_report)
                for name, value in before_globals.items():
                    self.assertIs(env[name], value, name + ' overwritten by cell 2')
                for path, contents in original_bytes.items():
                    self.assertEqual(path.read_bytes(), contents)
                self.assertEqual([r['shortable'] for r in delivered['rows']], ['YES', 'NEW'])
                self.assertEqual(delivered['eml'].parent.name, 'Shortable_Lockups')
                msg = addon_tests.BytesParser(policy=addon_tests.policy.default).parsebytes(delivered['eml'].read_bytes())
                self.assertEqual(msg['To'], 'fixture@example.com')
                self.assertEqual(msg['Cc'], 'fixturecc@example.com')
                self.assertEqual(msg['X-Unsent'], '1')
                # Rerun exactly the second cell: separate new draft, unchanged first draft.
                exec(compile(ADDON, 'exact_second_cell', 'exec'), env)
                self.assertNotEqual(env['LAST_LOCKUP_DRAFT']['eml'], delivered['eml'])
                self.assertEqual(env['LAST_DRAFT']['report'], before_report)

    def test_invalid_first_result_rejected_before_bloomberg(self):
        for result in (None, {}, {'report': addon_tests.fixture()}):
            with self.assertRaisesRegex(RuntimeError, 'original first cell'):
                second._lu_run(result, {}, False)


class SecondCellFailureTests(unittest.TestCase):
    def test_timeout_validation_before_submit(self):
        for invalid in (None, 'oops', float('nan'), float('inf'), -1, 0, 121):
            client, request, cancelled = addon_tests.client_fixture([])
            client.session.sendRequest = Mock()
            with patch.object(second, 'BLOOMBERG_REQUEST_TIMEOUT_SECONDS', invalid, create=True):
                with self.assertRaises((ValueError, TypeError)):
                    second._lu_bbg_request(client, ['1 HK Equity'], DAY)
            client.session.sendRequest.assert_not_called()
            self.assertEqual(cancelled, [])

    def test_timeout_cancels_after_partial_response(self):
        events = [addon_tests.Event(1, [{'securityData': [{'security': '1 HK Equity', 'fieldData': {'LAST_PRICE': 12}}]}])]
        client, request, cancelled = addon_tests.client_fixture(events)
        with patch('time.monotonic', side_effect=[100, 100, 131]):
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                second._lu_bbg_request(client, ['1 HK Equity'], DAY)
        self.assertEqual(cancelled, [123])

    def outlook(self, dispatch=None, import_error=None, save_error=False):
        draft = types.SimpleNamespace(HTMLBody='<html><body>Signature</body></html>', Display=Mock(),
                                      Save=Mock(side_effect=RuntimeError('save failed') if save_error else None))
        client = types.ModuleType('win32com.client')
        client.Dispatch = dispatch or Mock(return_value=types.SimpleNamespace(CreateItem=Mock(return_value=draft)))
        package = types.ModuleType('win32com'); package.client = client
        os_stub = types.ModuleType('os'); os_stub.name = 'nt'
        real_import = builtins.__import__
        def importer(name, *args, **kwargs):
            if name == 'win32com.client' and import_error:
                raise import_error
            return real_import(name, *args, **kwargs)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample ' 中文.html"
            path.write_text('<html><body>Fixture message 中文</body></html>', encoding='utf-8')
            with patch.dict(sys.modules, {'os': os_stub, 'win32com': package, 'win32com.client': client}), \
                 patch('builtins.__import__', side_effect=importer), \
                 patch('subprocess.run', return_value=types.SimpleNamespace(returncode=0)) as ps:
                result = second._lu_outlook(path, "Fixture ' 中文", 'a@example.com,b@example.com', '',
                                            {'_prepend_to_outlook_signature': first._prepend_to_outlook_signature})
        return result, draft, ps

    def test_outlook_com_saves_unsent_with_signature(self):
        result, draft, ps = self.outlook()
        self.assertTrue(result[0]); draft.Display.assert_called_once(); draft.Save.assert_called_once()
        self.assertIn('Fixture message 中文', draft.HTMLBody)
        self.assertIn('Signature', draft.HTMLBody)
        self.assertEqual(draft.To, 'a@example.com;b@example.com')
        ps.assert_not_called()
        self.assertFalse(hasattr(draft, 'Send'))

    def test_outlook_broken_pywin32_and_dispatch_fallback(self):
        for kwargs in ({'import_error': ImportError('missing')}, {'import_error': OSError('DLL failed')},
                       {'dispatch': Mock(side_effect=RuntimeError('COM failed'))}):
            result, draft, ps = self.outlook(**kwargs)
            self.assertTrue(result[0]); ps.assert_called_once(); draft.Display.assert_not_called()
            script = base64.b64decode(ps.call_args.args[0][-1]).decode('utf-16le')
            self.assertIn('$mail.Save()', script)
            self.assertNotIn('.Send', script)
            self.assertIn("Fixture '' 中文", script)
            self.assertIn("sample '' 中文.html", script)

    def test_outlook_save_failure_does_not_duplicate(self):
        result, draft, ps = self.outlook(save_error=True)
        self.assertFalse(result[0]); ps.assert_not_called(); draft.Display.assert_called_once()
        self.assertIn('check open drafts', result[1])


if __name__ == '__main__':
    unittest.main(verbosity=2)
