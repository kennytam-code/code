"""Build a fictional preview using the actual email renderer; no live calls."""
from datetime import date
import importlib.util
from pathlib import Path

folder = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('lockup_email_sample', folder / 'second_cell.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
start, end = date(2026, 11, 15), date(2027, 1, 31)
report = {'short': {'effective': '2026-11-13'},
          'source_asof': {k: '13/11/2026 16:10' for k in ['202611', '202612', '202701']}}
examples = [
    ('DEMO A', 'Technology Co.', '2026-11-20', 'Cornerstone', '5', '12.50%', '240000000', '18.4', '4.2', 'YES', '12.8', '12', '10', '8'),
    ('DEMO B', 'Healthcare Co.', '2026-12-04', 'Cornerstone', '3', '8.00%', '180000000', '11.2', '2.8', 'NEW', '8.6', '9.2', '8', '10'),
    ('DEMO C', 'Industrials Co.', '2027-01-15', 'Controller', '2', '25.00%', '520000000', '36.7', '9.1', 'YES', '26', '25', '28', '20'),
]
rows = []
for code, name, expiry, holder, n, percent, amount, float_pct, turnover, short, last, base7, base1, ipo in examples:
    performance = m._lu_performance(
        {'fields': {'LAST_PRICE': last, 'CRNCY': 'HKD', 'LAST_UPDATE_DT': '2026-11-13', 'EQY_INIT_PO_SH_PX': ipo}},
        {'history': {'2026-11-06': base7, '2026-10-15': base1}}, start)
    rows.append(dict(code=code, name=name, expiry=expiry, holder_type=holder, holders=n, percent=percent,
                     unlock_amount_hkd=amount, unlock_to_float_market_cap_pct=float_pct,
                     unlock_to_20d_avg_turnover_x=turnover, shortable=short, issue='', source_issue='',
                     bloomberg_issues=[], price_performance=performance))
subject, body, plain = m._lu_render(report, rows, start, end, 'Fictional sample')
body = body.replace('>Shortable IPO lock-up expiries</h2>', '>Shortable IPO lock-up expiries · Fictional sample</h2>')
(folder / 'sample_email.html').write_text(body, encoding='utf-8')
print('Fictional sample created:', folder / 'sample_email.html')
