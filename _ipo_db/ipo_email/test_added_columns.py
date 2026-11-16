"""A-share source fixtures and turnover/layout regression checks; no live calls."""
import copy
import json
import types
import unittest
from pathlib import Path
from unittest.mock import Mock

from test_cells_integration import first
from test_second_cell import m, fixture, HK

SOURCES = Path(__file__).with_name('review_sources')


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
        self.assertEqual(client.text.call_count, 2)
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
        self.assertEqual(len(result['document_sha256']), 64)
        self.assertIn('?code=1', result['url'])
        self.assertIn('retrieved_at', result)

    def test_turnover_units_a_share_and_table_only_layout(self):
        report = fixture()
        report['bloomberg'] = {'turnover_end_date': '20261113'}
        rows, start, end = m._lu_select(report)
        for row in rows:
            row['avg_turnover_20d_hkd'] = '40500000'
            row['a_share'] = {'status': 'YES', 'error': None}
            row['price_performance'] = m._lu_performance({}, {}, start)
        before = copy.deepcopy(rows)
        subject, html, plain = m._lu_render(report, rows, start, end, 'Fixture')
        root = first.parse_html(html)
        self.assertEqual(len(root.find_all('th')), 12)
        self.assertIn('Avg 20D <br>turnover (HKDm)', html)
        self.assertIn('40.50<br>', html)
        self.assertIn('To 20261113', html)
        self.assertIn('A-share YES', plain)
        self.assertIn('Avg 20D turnover HKDm 40.50', plain)
        self.assertFalse(root.find_all(['h1', 'h2', 'h3', 'p']))
        self.assertTrue(subject.startswith('Shortable IPO Lock-up'))
        self.assertEqual(rows, before)
        for row in rows:
            row.pop('avg_turnover_20d_hkd')
            row['a_share'] = {'status': 'N/A', 'error': 'Missing capital breakdown'}
        _, html, plain = m._lu_render(report, rows, start, end, 'Fixture')
        self.assertIn('Avg 20D turnover HKDm N/A', plain)
        self.assertIn('A-share N/A', plain)
        self.assertNotIn('Missing capital breakdown', html)


if __name__ == '__main__':
    unittest.main()
