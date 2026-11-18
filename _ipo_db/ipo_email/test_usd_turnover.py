"""USD conversion direction, quote validation and FX failure isolation; no live calls."""
import copy
import json
import tempfile
import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from test_second_cell import m, fixture, HK


class USDTurnoverTests(unittest.TestCase):
    def test_conversion_units_and_valid_weekend_quote(self):
        fx = m._lu_fx_rate({'fields': {'LAST_PRICE': '7.8', 'LAST_UPDATE_DT': '2026-11-13'}},
                           date(2026, 11, 15))
        self.assertEqual(fx['errors'], {})
        self.assertEqual(Decimal(m._lu_turnover_usd('39000000', fx)), Decimal('5000000'))
        self.assertEqual(m._lu_turnover_usd('0', fx), '0E+1')
        for missing in (None, '', 'NaN', 'Infinity', '-1', True):
            self.assertIsNone(m._lu_turnover_usd(missing, fx))

    def test_bad_fx_never_becomes_a_peg_or_zero(self):
        for rate, observed, errors in [
            (None, '2026-11-13', {}), ('0', '2026-11-13', {}), ('-7.8', '2026-11-13', {}),
            ('NaN', '2026-11-13', {}), ('Infinity', '2026-11-13', {}),
            ('7.8', None, {}), ('7.8', 'bad-date', {}), ('7.8', '2026-10-01', {}),
            ('7.8', '2026-11-16', {}), ('7.8', '2026-11-13', {'LAST_PRICE': 'denied'}),
            ('7.8', '2026-11-13', {'request': 'incomplete response'}),
        ]:
            with self.subTest(rate=rate, date=observed, errors=errors):
                fx = m._lu_fx_rate({'fields': {'LAST_PRICE': rate, 'LAST_UPDATE_DT': observed}, 'errors': errors},
                                   date(2026, 11, 15))
                self.assertIsNone(fx['hkd_per_usd'])
                self.assertIsNone(m._lu_turnover_usd('39000000', fx))

    def test_fx_failure_preserves_draft_and_stock_prices(self):
        day = datetime.now(HK).date()
        report = fixture(day)
        report['months'] = [day.strftime('%Y%m')]
        report['lockups'] = report['lockups'][1:2]
        report['lockups'][0].update(expiry=day.isoformat(), avg_turnover_20d_hkd='39000000')
        original = copy.deepcopy(report)
        class Client:
            def __enter__(self): return self
            def __exit__(self, *args): pass
        def request(client, securities, start, historical=False, reference_fields=None):
            if securities == ['USDHKD Curncy']:
                raise TimeoutError('FX request timed out')
            if historical:
                return {s: {'history': {d.isoformat(): '10' for d in m._lu_horizons(start).values()}} for s in securities}
            return {s: {'fields': {'LAST_PRICE': '12', 'CRNCY': 'HKD', 'LAST_UPDATE_DT': day.isoformat(),
                                   'EQY_INIT_PO_SH_PX': '8'}} for s in securities}
        with tempfile.TemporaryDirectory() as directory:
            env = {'HK': HK, 'BloombergClient': Client, 'bloomberg_security': lambda c: c+' HK Equity',
                   'atomic_write': lambda p, data: p.write_bytes(data), 'LOCKUP_EMAIL_CHECK_A_SHARES': False,
                   'SHOW_NOTEBOOK_PREVIEW_IF_NO_OUTLOOK': False}
            with patch.object(m, '_lu_bbg_request', request):
                delivered = m._lu_run({'report': report, 'email_html': Path(directory)/'first.html'}, env, False)
            self.assertTrue(delivered['eml'].exists())
            audit = json.loads(delivered['audit'].read_text())
            self.assertIn('timed out', audit['turnover_fx']['errors']['request'])
            row = audit['rows'][0]
            self.assertIsNone(row['avg_turnover_20d_usd'])
            self.assertEqual(row['price_performance']['last_price'], '12')
            self.assertEqual(row['price_performance']['7D']['change_pct'], '20.0')
            self.assertEqual(row['avg_turnover_20d_hkd'], '39000000')
            self.assertEqual(row['unlock_to_20d_avg_turnover_x'], original['lockups'][0]['unlock_to_20d_avg_turnover_x'])
        self.assertEqual(report, original)


if __name__ == '__main__':
    unittest.main()
