"""Offline fixtures only. No Bloomberg connection, network, or Outlook calls."""
import copy
import importlib.util
import json
import tempfile
import types
import unittest
from datetime import date, datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('lockup_addon', Path(__file__).with_name('second_cell.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
HK = timezone(timedelta(hours=8))


def fixture(day=date(2026, 11, 15)):
    def row(code, expiry, holder='Cornerstone'):
        return {'code': code, 'name': 'Fixture <A&B>', 'expiry': expiry,
                'holder_type': holder, 'holders': '3', 'percent': '12.5%',
                'amount': 'HKD 100 million', 'unlock_amount_hkd': '100000000',
                'unlock_to_float_market_cap_pct': '15', 'unlock_to_20d_avg_turnover_x': '2.5',
                'issue': '', 'source_issue': '', 'bloomberg_issues': [], 'url': 'https://example.com'}
    return {'day': day.isoformat(), 'months': ['202611', '202612', '202701'],
            'short': {'securities': {'00001': 'A', '00002': 'B'}, 'effective': day.isoformat()},
            'added': {'00002': 'B'}, 'source_asof': {'202611': '15/11/2026 16:00'},
            'lockups': [row('00001', '2026-11-14'), row('00001', '2026-11-15'),
                        row('00002', '2026-12-01'), row('00002', '2026-12-01', 'Controller'),
                        row('00001', '2027-01-31'), row('00001', '2027-02-01'),
                        row('00003', '2026-11-20')]}


class Element:
    """Minimal Bloomberg-shaped fixture, including array vs object shapes."""
    def __init__(self, value): self.value = value
    def hasElement(self, key): return isinstance(self.value, dict) and key in self.value
    def getElement(self, key): return Element(self.value[key])
    def getElementAsString(self, key): return str(self.value[key])
    def getElementAsInteger(self, key): return self.value[key]
    def getElementAsDatetime(self, key): return self.value[key]
    def getValueAsElement(self, index): return Element(self.value[index])
    def getValueAsString(self): return str(self.value)
    def getValueAsDatetime(self): return self.value
    def isNull(self): return self.value is None
    def numValues(self): return len(self.value) if isinstance(self.value, list) else int(self.value is not None)
    def appendValue(self, value): self.value.append(value)
    def __str__(self): return str(self.value)


class Request(Element):
    def __init__(self): super().__init__({'securities': [], 'fields': []})
    def set(self, key, value): self.value[key] = value


class Event(list):
    def __init__(self, kind, values):
        super().__init__(Element(value) for value in values)
        self.kind = kind
    def eventType(self): return self.kind


def client_fixture(events):
    request, cancelled = Request(), []
    queue = types.SimpleNamespace(nextEvent=lambda timeout: events.pop(0))
    client = types.SimpleNamespace(
        service=types.SimpleNamespace(createRequest=lambda kind: request),
        session=types.SimpleNamespace(sendRequest=lambda req, eventQueue: 123, cancel=cancelled.append),
        api=types.SimpleNamespace(EventQueue=lambda: queue,
                                  Event=types.SimpleNamespace(REQUEST_STATUS=3, PARTIAL_RESPONSE=1, RESPONSE=2)))
    return client, request, cancelled


class AddonTests(unittest.TestCase):
    def test_window_and_preservation(self):
        report = fixture()
        before = copy.deepcopy(report)
        rows, start, end = m._lu_select(report)
        self.assertEqual((start, end), (date(2026, 11, 15), date(2027, 1, 31)))
        self.assertEqual([r['shortable'] for r in rows], ['YES', 'NEW', 'NEW', 'YES'])
        self.assertEqual(len(rows), 4)
        rows[0]['name'] = 'changed copy'
        self.assertEqual(report, before)

    def test_calendar_targets(self):
        self.assertEqual(m._lu_horizons(date(2024, 3, 31))['1M'], date(2024, 2, 29))
        self.assertEqual(m._lu_horizons(date(2026, 3, 31))['1M'], date(2026, 2, 28))
        self.assertEqual(m._lu_horizons(date(2026, 1, 31))['1M'], date(2025, 12, 31))
        self.assertEqual(m._lu_horizons(date(2026, 11, 15))['7D'], date(2026, 11, 8))

    def test_returns_and_holiday_baseline(self):
        snap = {'fields': {'LAST_PRICE': '12', 'LAST_UPDATE_DT': '2026-11-13', 'CRNCY': 'HKD'}}
        hist = {'history': {'2026-11-06': '10', '2026-11-09': '100', '2026-10-15': '15'}}
        result = m._lu_performance(snap, hist, date(2026, 11, 15))
        self.assertEqual(result['7D']['change_pct'], '20.0')
        self.assertEqual(result['1M']['change_pct'], '-20.0')
        self.assertEqual(result['7D']['baseline_date'], '2026-11-06')
        snap['fields']['LAST_PRICE'] = '10'
        self.assertEqual(m._lu_performance(snap, hist, date(2026, 11, 15))['7D']['change_pct'], '0')

    def test_unavailable_stale_and_insufficient(self):
        day = date(2026, 11, 15)
        for price in [None, 'NaN', 'Infinity', '0', '-2']:
            result = m._lu_performance({'fields': {'LAST_PRICE': price}}, {}, day)
            self.assertIsNone(result['last_price'])
            self.assertIsNone(result['7D']['change_pct'])
        for quote in ['2026-11-16', '2026-09-01', None, 'invalid']:
            result = m._lu_performance({'fields': {'LAST_PRICE': '12', 'LAST_UPDATE_DT': quote}},
                                      {'history': {'2026-11-06': '10'}}, day)
            self.assertIsNone(result['7D']['change_pct'])
        snap = {'fields': {'LAST_PRICE': '12', 'LAST_UPDATE_DT': '2026-11-13'}}
        for history in [{'2026-11-10': '10'}, {'2026-10-01': '10'}, {'2026-11-06': '0'}]:
            self.assertIsNone(m._lu_performance(snap, {'history': history}, day)['7D']['change_pct'])
        result = m._lu_performance(snap, {'history': {'2026-11-06': '10'}, 'errors': {'PX_LAST': 'denied'}}, day)
        self.assertIsNone(result['7D']['change_pct'])

    def test_reference_multi_response_and_canonical_mapping(self):
        events = [Event(1, [{'securityData': [{'security': 'CANONICAL', 'sequenceNumber': 0,
                   'fieldData': {'LAST_PRICE': 12, 'CRNCY': 'HKD', 'LAST_UPDATE_DT': date(2026, 11, 13),
                                 'EQY_INIT_PO_SH_PX': 8}}]}]),
                  Event(2, [{'securityData': [{'security': '2 HK Equity', 'sequenceNumber': 1,
                   'securityError': 'denied'}]}])]
        client, req, cancelled = client_fixture(events)
        result = m._lu_bbg_request(client, ['1 HK Equity', '2 HK Equity', '3 HK Equity'], date(2026, 11, 15))
        self.assertEqual(result['1 HK Equity']['fields']['LAST_PRICE'], '12')
        self.assertEqual(result['1 HK Equity']['fields']['LAST_UPDATE_DT'], '2026-11-13')
        self.assertEqual(result['1 HK Equity']['fields']['EQY_INIT_PO_SH_PX'], '8')
        self.assertEqual(req.value['fields'].count('EQY_INIT_PO_SH_PX'), 1)
        self.assertIn('security', result['2 HK Equity']['errors'])
        self.assertIn('security', result['3 HK Equity']['errors'])
        self.assertEqual(cancelled, [])

    def test_ipo_price_comparison_independent_of_history(self):
        fields = {'LAST_PRICE': '12', 'LAST_UPDATE_DT': '2026-11-13', 'CRNCY': 'HKD'}
        for offer, expected in [('10', '20.0'), ('15', '-20.0'), ('12', '0')]:
            fields['EQY_INIT_PO_SH_PX'] = offer
            result = m._lu_performance({'fields': fields}, {'errors': {'PX_LAST': 'unavailable'}}, date(2026, 11, 15))
            self.assertEqual(result['ipo_price'], offer)
            self.assertEqual(result['ipo_change_pct'], expected)
            self.assertIsNone(result['7D']['change_pct'])
        for quote in [None, '2026-09-01', '2026-11-16']:
            fields['LAST_UPDATE_DT'] = quote
            self.assertIsNone(m._lu_performance({'fields': fields}, {}, date(2026, 11, 15))['ipo_change_pct'])

    def test_invalid_ipo_keeps_valid_horizon_returns(self):
        fields = {'LAST_PRICE': '12', 'LAST_UPDATE_DT': '2026-11-13', 'CRNCY': 'HKD'}
        history = {'history': {'2026-11-06': '10', '2026-10-15': '15'}}
        for offer in [None, '0', '-1', 'NaN', 'Infinity', 'unavailable']:
            fields['EQY_INIT_PO_SH_PX'] = offer
            result = m._lu_performance({'fields': fields}, history, date(2026, 11, 15))
            self.assertIsNone(result['ipo_price'])
            self.assertIsNone(result['ipo_change_pct'])
            self.assertEqual(result['7D']['change_pct'], '20.0')
            self.assertEqual(result['1M']['change_pct'], '-20.0')

    def test_ipo_field_exception_is_isolated(self):
        events = [Event(2, [{'securityData': [{'security': '1 HK Equity', 'sequenceNumber': 0,
                  'fieldData': {'LAST_PRICE': 12, 'CRNCY': 'HKD', 'LAST_UPDATE_DT': date(2026, 11, 13),
                                'EQY_INIT_PO_SH_PX': 8},
                  'fieldExceptions': [{'fieldId': 'EQY_INIT_PO_SH_PX', 'errorInfo': 'denied'}]}]}])]
        client, req, cancelled = client_fixture(events)
        snapshot = m._lu_bbg_request(client, ['1 HK Equity'], date(2026, 11, 15))['1 HK Equity']
        self.assertNotIn('EQY_INIT_PO_SH_PX', snapshot['fields'])
        self.assertEqual(snapshot['fields']['LAST_PRICE'], '12')
        result = m._lu_performance(snapshot, {'history': {'2026-11-06': '10'}}, date(2026, 11, 15))
        self.assertIsNone(result['ipo_price'])
        self.assertEqual(result['7D']['change_pct'], '20.0')

    def test_history_shape_and_field_error(self):
        events = [Event(1, [{'securityData': {'security': 'CANONICAL', 'sequenceNumber': 0,
                  'fieldData': [{'date': date(2026, 11, 6), 'PX_LAST': 10}]}}]),
                  Event(2, [{'securityData': {'security': '2 HK Equity', 'sequenceNumber': 1,
                  'fieldData': [], 'fieldExceptions': [{'fieldId': 'PX_LAST', 'errorInfo': 'denied'}]}}])]
        client, req, cancelled = client_fixture(events)
        result = m._lu_bbg_request(client, ['1 HK Equity', '2 HK Equity'], date(2026, 11, 15), True)
        self.assertEqual(result['1 HK Equity']['history'], {'2026-11-06': '10'})
        self.assertIn('PX_LAST', result['2 HK Equity']['errors'])
        self.assertFalse(req.value['adjustmentFollowDPDF'])
        self.assertFalse(req.value['adjustmentNormal'])
        self.assertTrue(req.value['adjustmentSplit'])

    def test_request_failure_discards_partial(self):
        events = [Event(1, [{'securityData': [{'security': '1 HK Equity', 'fieldData': {'LAST_PRICE': 12}}]}]),
                  Event(3, [{'error': 'failed'}])]
        client, req, cancelled = client_fixture(events)
        with self.assertRaises(RuntimeError):
            m._lu_bbg_request(client, ['1 HK Equity'], date(2026, 11, 15))
        self.assertEqual(cancelled, [123])

    def test_render_escapes_and_empty(self):
        report = fixture()
        rows, start, end = m._lu_select(report)
        for row in rows:
            row['price_performance'] = m._lu_performance({}, {}, start)
        rows[0]['source_issue'] = 'Check <date>'
        subject, body, plain = m._lu_render(report, rows, start, end, 'fixture time')
        self.assertIn('Fixture &lt;A&amp;B&gt;', body)
        self.assertIn('REVIEW', body)
        self.assertNotIn('Check &lt;date&gt;', body)
        self.assertNotIn('7 calendar days', body)
        self.assertNotIn('Bloomberg price check:', body)
        self.assertNotIn('7 calendar days', plain)
        self.assertIn('IPO price', body)
        self.assertIn('vs IPO %', body)
        self.assertNotIn('borrow', body.lower())
        self.assertIn('N/A', body)
        self.assertNotIn('Fixture <A&B>', body)
        self.assertIn('No shortable', m._lu_render(report, [], start, end, 'fixture time')[1])

    def test_draft_outputs_and_first_report_preserved(self):
        today = datetime.now(HK).date()
        report = fixture(today)
        report['months'] = [today.strftime('%Y%m')]
        report['lockups'] = report['lockups'][1:4]
        for row in report['lockups']:
            row['expiry'] = today.isoformat()
        before = copy.deepcopy(report)
        called = []

        class FakeClient:
            def __enter__(self): return self
            def __exit__(self, *args): pass

        def request(client, securities, day, historical=False):
            called.append((tuple(securities), historical))
            if historical:
                return {s: {'history': {v.isoformat(): '10' for v in m._lu_horizons(day).values()}} for s in securities}
            return {s: {'fields': {'LAST_PRICE': '12', 'LAST_UPDATE_DT': day.isoformat(), 'CRNCY': 'HKD',
                                   'EQY_INIT_PO_SH_PX': '8'}} for s in securities}

        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / 'original.html'
            original.write_text('unchanged original')
            first = {'report': report, 'email_html': original}
            env = {'HK': HK, 'BloombergClient': FakeClient,
                   'bloomberg_security': lambda code: str(int(code)) + ' HK Equity',
                   'atomic_write': lambda path, contents: path.write_bytes(contents),
                   'LOCKUP_EMAIL_TO': 'review@example.com', 'SHOW_NOTEBOOK_PREVIEW_IF_NO_OUTLOOK': False}
            with patch.object(m, '_lu_bbg_request', request), patch.object(m, '_lu_outlook') as outlook:
                one = m._lu_run(first, env, open_outlook=False)
                two = m._lu_run(first, env, open_outlook=False)
                outlook.assert_not_called()
            self.assertNotEqual(one['eml'], two['eml'])
            self.assertEqual(original.read_text(), 'unchanged original')
            self.assertEqual(report, before)
            self.assertEqual(called[0], (('1 HK Equity', '2 HK Equity'), False))
            self.assertEqual(len(called), 4)  # One reference and one history batch per run.
            mail = BytesParser(policy=policy.default).parsebytes(one['eml'].read_bytes())
            self.assertEqual(mail['X-Unsent'], '1')
            self.assertEqual(mail['To'], 'review@example.com')
            self.assertIn('Shortable IPO', mail['Subject'])
            self.assertEqual(len(list(mail.iter_parts())), 2)
            audit = json.loads(one['audit'].read_text())
            self.assertEqual(len(audit['rows']), 3)
            self.assertTrue(all(r['price_performance']['7D']['change_pct'] == '20.0' for r in audit['rows']))
            self.assertTrue(all(r['price_performance']['ipo_change_pct'] == '50.0' for r in audit['rows']))
            self.assertEqual(audit['ipo_price_field'], 'EQY_INIT_PO_SH_PX')
            self.assertIn('IPO price 8.000 HKD', mail.get_body(preferencelist=('plain',)).get_content())
            self.assertIn('vs IPO +50.00%', mail.get_body(preferencelist=('plain',)).get_content())

    def test_empty_skips_bloomberg_and_stale_rejected(self):
        today = datetime.now(HK).date()
        report = fixture(today)
        report['lockups'] = []
        with tempfile.TemporaryDirectory() as directory:
            first = {'report': report, 'email_html': Path(directory) / 'first.html'}
            env = {'HK': HK, 'BloombergClient': lambda: self.fail('Unexpected API request'),
                   'bloomberg_security': lambda code: code, 'atomic_write': lambda p, b: p.write_bytes(b),
                   'SHOW_NOTEBOOK_PREVIEW_IF_NO_OUTLOOK': False}
            self.assertEqual(m._lu_run(first, env, False)['rows'], [])
            report['day'] = (today - timedelta(days=1)).isoformat()
            with self.assertRaisesRegex(RuntimeError, 'not dated today'):
                m._lu_run(first, env, False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
