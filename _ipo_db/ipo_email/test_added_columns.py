"""A-share source fixtures and turnover/layout regression checks; no live calls."""
import copy
import json
import types
import unittest
from pathlib import Path
from unittest.mock import Mock
from datetime import date, datetime

from test_cells_integration import first
from test_second_cell import m, fixture, HK

SOURCES = Path(__file__).with_name('review_sources')
DAY = date(2026, 11, 17)


def structure_response(codes):
    data = json.loads((SOURCES / 'eastmoney_share_structure.json').read_text())
    data['result']['data'] = [r for r in data['result']['data'] if r['SECURITY_CODE'] in codes]
    data['result']['count'] = len(data['result']['data'])
    return json.dumps(data, ensure_ascii=False)


def fixture_client():
    from urllib.parse import urlparse, parse_qs
    import re
    def text(url):
        if url.endswith('/ah.php'):
            return (SOURCES / 'etnet_ah.html').read_text()
        if 'datacenter.eastmoney.com' in url:
            codes = re.findall(r'"(\d{5})\.HK"', parse_qs(urlparse(url).query)['filter'][0])
            return structure_response(codes)
        code = parse_qs(urlparse(url).query)['code'][0]
        return (SOURCES / ('etnet_profile_' + code + '.html')).read_text()
    return types.SimpleNamespace(text=Mock(side_effect=text))


def profile(rows, code='00001'):
    capital = ''.join('<tr><td>' + k + '</td><td>' + str(v) + '</td><td></td></tr>' for k, v in rows)
    return ('<html><head><title>' + code + '.HK Fixture</title></head><body>'
            '<nav>A股</nav><table><tr><td>股本</td><td><table>' + capital + '</table></td></tr></table></body></html>')


class AddedColumns(unittest.TestCase):
    def test_downloaded_profiles_and_hashes(self):
        import hashlib
        for record in json.loads((SOURCES / 'a_share_fetch.json').read_text()):
            raw = (SOURCES / ('etnet_profile_' + record['code'] + '.html')).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), record['sha256'])
            if record['code'] == '700':
                # Only total issued shares: deliberately avoid inferring No.
                with self.assertRaisesRegex(ValueError, 'complete recognised'):
                    m._lu_a_share_profile(raw.decode('utf-8'), '00700', first.parse_html)
            else:
                result = m._lu_a_share_profile(raw.decode('utf-8'), record['code'], first.parse_html)
                self.assertEqual(result['status'], 'YES' if record['code'] == '3750' else 'NO')

    def test_capital_categories_and_zero_a_shares(self):
        for rows, expected in [
            ([('有限制流通A股', 10), ('無限制流通A股', 80), ('H股', 10), ('發行股數', 100)], 'YES'),
            ([('內資股及其他', 80), ('H股', 20), ('發行股數', 100)], 'NO'),
            ([('A股', 0), ('H股', 100), ('發行股數', 100)], 'NO'),
        ]:
            self.assertEqual(m._lu_a_share_profile(profile(rows), '00001', first.parse_html)['status'], expected)

    def test_incomplete_unknown_and_wrong_issuer_never_no(self):
        cases = [
            profile([('發行股數', 100)]),
            profile([('H股', 10), ('發行股數', 100)]),
            profile([('H股', '-'), ('發行股數', 100)]),
            profile([('H股', 100), ('發行股數', 100)], '00002'),
            profile([('H股', 100), ('發行股數', 100)])[:-7],
            profile([('A類普通股', 80), ('B類普通股', 20), ('發行股數', 100)]),
            profile([('H股', 100), ('H股', 100), ('發行股數', 200)]),
            '<html><title>00001.HK</title><body>Blocked A股</body></html>',
        ]
        for html in cases:
            with self.subTest(html=html), self.assertRaises(ValueError):
                m._lu_a_share_profile(html, '00001', first.parse_html)

    def test_network_failure_disabled_lookup_and_deduplication(self):
        client = types.SimpleNamespace(text=Mock(side_effect=TimeoutError('Fixture timeout')))
        env = {'Client': Mock(return_value=client), 'HK': HK, 'parse_html': first.parse_html}
        results = m._lu_a_shares(['00001', '00001', '00002'], env)
        self.assertEqual(client.text.call_count, 4)  # roster, batch and two profile fallbacks
        self.assertEqual(env['Client'].call_count, 1)
        self.assertTrue(all(r['status'] == 'N/A' and r['error'] for r in results.values()))
        client.text.reset_mock()
        env['LOCKUP_EMAIL_CHECK_A_SHARES'] = False
        self.assertEqual(m._lu_a_shares(['00001'], env)['00001']['status'], 'N/A')
        client.text.assert_not_called()
        self.assertEqual(m._lu_a_shares([], {}), {})

    def test_successful_lookup_records_evidence(self):
        html = profile([('A股', 80), ('H股', 20), ('發行股數', 100)])
        env = {'Client': lambda: types.SimpleNamespace(text=lambda url: html), 'HK': HK, 'parse_html': first.parse_html}
        result = m._lu_a_shares(['00001'], env)['00001']
        self.assertEqual(result['status'], 'YES')
        self.assertEqual(len(result['profile']['source']['document_sha256']), 64)
        self.assertIn('?code=1', result['profile']['source']['url'])
        self.assertIn('retrieved_at', result)

    def test_downloaded_roster_exact_ticker_pairs(self):
        import hashlib
        raw = (SOURCES / 'etnet_ah.html').read_bytes()
        record = json.loads((SOURCES / 'ah_roster_fetch.json').read_text())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), record['sha256'])
        pairs = m._lu_a_share_roster(raw.decode('utf-8'), first.parse_html)
        self.assertEqual(len(pairs), 211)
        self.assertEqual(pairs['03750'], {'a_code': '300750', 'a_exchange': 'Shenzhen'})
        self.assertEqual(pairs['00981'], {'a_code': '688981', 'a_exchange': 'Shanghai'})
        self.assertNotIn('02551', pairs)
        self.assertNotIn('00700', pairs)

    def test_invalid_roster_rejected_without_inventing_no(self):
        raw = (SOURCES / 'etnet_ah.html').read_text()
        for document in (raw.replace('</html>', ''), raw.replace('code=03750', 'code=03751'),
                         raw.replace('H股代號', 'unexpected heading'), '<html>Blocked</html>'):
            with self.subTest(document=document[:20]), self.assertRaises(ValueError):
                m._lu_a_share_roster(document, first.parse_html)

    def test_roster_positive_can_resolve_missing_profile(self):
        roster = (SOURCES / 'etnet_ah.html').read_text()
        def text(url):
            if url.endswith('/ah.php'):
                return roster
            raise TimeoutError('Fixture profile unavailable')
        env = {'Client': lambda: types.SimpleNamespace(text=text), 'HK': HK, 'parse_html': first.parse_html}
        results = m._lu_a_shares(['03750', '00700'], env)
        self.assertEqual(results['03750']['status'], 'YES')
        self.assertEqual(results['03750']['a_code'], '300750')
        self.assertIsNone(results['03750']['error'])
        self.assertIn('unavailable', results['03750']['share_structure']['error'])
        self.assertEqual(results['00700']['status'], 'N/A')  # absence is not No

    def test_roster_profile_conflict_stays_unknown(self):
        roster = (SOURCES / 'etnet_ah.html').read_text()
        def text(url):
            if url.endswith('/ah.php'):
                return roster
            data = json.loads(structure_response(['00700']))
            for row in data['result']['data']:
                row.update(SECURITY_CODE='03750', SECUCODE='03750.HK')
            return json.dumps(data)
        env = {'Client': lambda: types.SimpleNamespace(text=text), 'HK': HK, 'parse_html': first.parse_html}
        result = m._lu_a_shares(['03750'], env)['03750']
        self.assertEqual(result['status'], 'N/A')
        self.assertIn('conflicts', result['error'])

    def test_roster_and_profile_real_fixtures_end_to_end(self):
        client = fixture_client()
        env = {'Client': lambda: client, 'HK': HK, 'parse_html': first.parse_html}
        results = m._lu_a_shares(['03750', '02551', '00700'], env)
        self.assertEqual({k: v['status'] for k, v in results.items()},
                         {'03750': 'YES', '02551': 'NO', '00700': 'NO'})
        self.assertEqual(results['03750']['a_code'], '300750')
        self.assertEqual(client.text.call_count, 2)

    def test_eight_examples_no_unknowns_and_no_profile_requests(self):
        client = fixture_client()
        env = {'Client': lambda: client, 'HK': HK, 'parse_html': first.parse_html}
        codes = ['00700', '03750', '00981', '02551', '09988', '01810', '03690', '09618']
        results = m._lu_a_shares(codes + ['00700'], env)
        self.assertEqual({c: r['status'] for c, r in results.items()},
                         {c: 'YES' if c in {'03750', '00981'} else 'NO' for c in codes})
        self.assertTrue(all(r['error'] is None for r in results.values()))
        self.assertEqual(client.text.call_count, 2)

    def test_neeq_domestic_shares_are_not_a_shares(self):
        roster = (SOURCES / 'etnet_ah.html').read_text()
        structure = (SOURCES / 'eastmoney_jinxun_structure.json').read_text()
        issuer = (SOURCES / 'etnet_profile_3636.html').read_text()
        def text(url):
            if url.endswith('/ah.php'): return roster
            if 'datacenter.eastmoney.com' in url: return structure
            return issuer
        env = {'Client': lambda: types.SimpleNamespace(text=text), 'HK': HK, 'parse_html': first.parse_html}
        result = m._lu_a_shares(['03636'], env)['03636']
        self.assertEqual(result['status'], 'NO')
        self.assertIsNone(result['error'])
        self.assertIn('counts reconciled', result['method'])
        # Keep internally complete profiles that disagree with the other source unresolved.
        issuer = issuer.replace('275,741,607', '275,741,608').replace('380,786,607', '380,786,608')
        result = m._lu_a_shares(['03636'], env)['03636']
        self.assertEqual(result['status'], 'N/A')
        self.assertIn('disagree', result['error'])

    def test_structure_integrity_and_mainland_not_assumed_a(self):
        parsed = m._lu_share_structure(structure_response(['03750', '00700']), ['03750', '00700'], DAY)
        self.assertEqual(parsed['03750']['status'], 'MAINLAND_LISTED')
        self.assertEqual(parsed['00700']['status'], 'NO')
        raw = json.loads(structure_response(['00700']))
        for mutate in [
            lambda d: d['result']['data'][1].update(SHARES_NUM=1),
            lambda d: d['result']['data'][1].update(SHARES_NUM=None),
            lambda d: d['result']['data'][1].update(SHARES_NUM=float('nan')),
            lambda d: d['result']['data'][1].update(SHARES_TYPE_CODE='001009'),
            lambda d: d['result']['data'][1].update(CHANGE_DATE='2027-01-01 00:00:00'),
        ]:
            data = copy.deepcopy(raw); mutate(data)
            self.assertEqual(m._lu_share_structure(json.dumps(data), ['00700'], DAY)['00700']['status'], 'N/A')
        for mutate in [lambda d: d.update(success=False),
                       lambda d: d['result'].update(pages=2),
                       lambda d: d['result'].update(count=3),
                       lambda d: d['result']['data'][0].update(SECUCODE='03750.HK')]:
            data = copy.deepcopy(raw); mutate(data)
            with self.assertRaises(ValueError):
                m._lu_share_structure(json.dumps(data), ['00700'], DAY)

    def test_source_budget_stops_network_before_request(self):
        from unittest.mock import patch
        client = types.SimpleNamespace(text=Mock())
        with patch('time.monotonic', return_value=100):
            with self.assertRaises(TimeoutError):
                m._lu_source_text(client, 'https://example.com', {}, 99)
        client.text.assert_not_called()
        env = {'Client': Mock(), 'HK': HK, 'LOCKUP_EMAIL_WEB_BUDGET': float('nan')}
        result = m._lu_a_shares(['00700'], env)
        self.assertEqual(result['00700']['status'], 'N/A')
        env['Client'].assert_not_called()

    def test_transport_partial_and_oversize_responses_rejected(self):
        import email.message
        import time
        class Response:
            def __init__(self, parts, length):
                self.parts = iter(parts)
                self.headers = email.message.Message()
                self.headers['Content-Length'] = str(length)
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read1(self, size): return next(self.parts, b'')
        env = dict(first.__dict__)
        for parts, length in [([b'partial'], 20), ([b'x' * 2_000_001], 2_000_001)]:
            client = types.SimpleNamespace(opener=types.SimpleNamespace(open=Mock(return_value=Response(parts, length))), cache={})
            with self.assertRaises(ValueError):
                m._lu_source_text(client, 'https://example.com', env, time.monotonic()+30)
            self.assertLessEqual(client.opener.open.call_args.kwargs['timeout'], 8)

    def test_unexpected_lookup_failure_still_saves_email(self):
        import tempfile
        from unittest.mock import patch
        report = fixture(datetime.now(HK).date())
        report['months'] = [report['day'].replace('-', '')[:6]]
        report['lockups'] = [report['lockups'][0]]
        report['lockups'][0]['expiry'] = report['day']
        with tempfile.TemporaryDirectory() as directory:
            env = {'HK': HK, 'BloombergClient': Mock(side_effect=RuntimeError('offline')),
                   'bloomberg_security': lambda code: code+' HK Equity',
                   'atomic_write': lambda p, b: p.write_bytes(b), 'SHOW_NOTEBOOK_PREVIEW_IF_NO_OUTLOOK': False}
            original = {'report': report, 'email_html': Path(directory)/'original.html'}
            with patch.object(m, '_lu_a_shares', side_effect=RuntimeError('unexpected source failure')):
                delivered = m._lu_run(original, env, False)
            self.assertTrue(delivered['eml'].exists())
            self.assertEqual(delivered['rows'][0]['a_share']['status'], 'N/A')

    def test_turnover_units_a_share_and_table_only_layout(self):
        report = fixture()
        report['bloomberg'] = {'turnover_end_date': '20261113'}
        rows, start, end = m._lu_select(report)
        for row in rows:
            row['avg_turnover_20d_hkd'] = '40500000'
            row['avg_turnover_20d_usd'] = m._lu_turnover_usd(row['avg_turnover_20d_hkd'], {'hkd_per_usd': '7.8'})
            row['a_share'] = {'status': 'YES', 'error': None}
            row['price_performance'] = m._lu_performance({}, {}, start)
        before = copy.deepcopy(rows)
        subject, html, plain = m._lu_render(report, rows, start, end, 'Fixture')
        root = first.parse_html(html)
        self.assertEqual(len(root.find_all('th')), 11)
        self.assertIn('Avg 20D <br>turnover (USDm)', html)
        self.assertIn('5.19<br>', html)
        self.assertIn('To 20261113', html)
        self.assertIn('A-share YES', plain)
        self.assertIn('Avg 20D turnover USDm 5.19', plain)
        self.assertFalse(root.find_all(['h1', 'h2', 'h3', 'p']))
        self.assertTrue(subject.startswith('Shortable IPO Lock-up'))
        self.assertEqual(rows, before)
        for row in rows:
            row.pop('avg_turnover_20d_hkd')
            row.pop('avg_turnover_20d_usd')
            row['a_share'] = {'status': 'N/A', 'error': 'Missing capital breakdown'}
        _, html, plain = m._lu_render(report, rows, start, end, 'Fixture')
        self.assertIn('Avg 20D turnover USDm N/A', plain)
        self.assertIn('A-share N/A', plain)
        self.assertNotIn('Missing capital breakdown', html)


if __name__ == '__main__':
    unittest.main()
