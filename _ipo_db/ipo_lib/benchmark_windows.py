"""Date-aligned benchmark legs from a durable, offline daily-close cache."""
import json
from bisect import bisect_left

BENCH = {
    'Technology': ('3033.HK', 'HSTECH (Hang Seng TECH ETF)'),
    'Healthcare': ('2820.HK', 'China Biotech ETF (HS biotech proxy)'),
    'Financials': ('^HSNF', 'Hang Seng Finance sub-index'),
    'Real Estate': ('^HSNP', 'Hang Seng Properties sub-index'),
    'Materials/Energy': ('^HSNC', 'Hang Seng Commerce & Industry sub-index'),
    'Consumer': ('^HSNC', 'Hang Seng Commerce & Industry sub-index'),
    'Industrials': ('^HSNC', 'Hang Seng Commerce & Industry sub-index'),
    'Media & telecom': ('^HSI', 'Hang Seng Index'),
    'Other': ('^HSI', 'Hang Seng Index'),
}
DEFAULT_BENCH = ('^HSI', 'Hang Seng Index')


def load_benchmarks(root):
    p = root / 'data' / 'batches' / 'benchmark_prices.json'
    return json.loads(p.read_text()).get('benchmarks', {}) if p.exists() else {}


def dated_return(rows, start, end, include_start=False):
    """Require the exact end session; anchor before debut, or at debut for ex-pop."""
    values = dict(rows)
    if end not in values:
        return None
    dates = sorted(values)
    i = bisect_left(dates, start)
    if not (include_start and start in values):
        i -= 1
    if i < 0 or not values[dates[i]] or end < dates[i]:
        return None
    return round(100 * (values[end] / values[dates[i]] - 1), 2)


def align_benchmarks(deal, benchmarks):
    """Recompute after final classification and price/date adjudication."""
    label = BENCH.get(deal.get('sector'), DEFAULT_BENCH)[1]
    rows = benchmarks.get(label, {}).get('closes')
    if not rows:
        return 0
    deal['benchmark'] = label
    ipo = (deal.get('ipo_date') or '')[:10]
    changed = 0
    for h, end, stock in [
        ('day1', ipo, deal.get('first_day_return_pct')),
        ('since', deal.get('price_asof'), deal.get('since_ipo_pct')),
        *[(h, deal.get(f'ret_{h}_date'), deal.get(f'ret_{h}_pct'))
          for h in ('1w', '1m', '3m')],
    ]:
        if not (ipo and end and stock is not None):
            continue
        b = dated_return(rows, ipo, end)
        if b is None:
            deal.pop(f'bench_{h}_pct', None)
            deal.pop(f'alpha_{h}_pct', None)
            deal['alpha_note'] = f'{label}: no exact close on {end}'
            continue
        changed += deal.get(f'bench_{h}_pct') != b
        deal[f'bench_{h}_pct'] = b
        deal[f'alpha_{h}_pct'] = round(stock - b, 2)
    end = deal.get('ret_1m_date')
    if ipo and end and deal.get('aftermkt_1m_pct') is not None:
        b = dated_return(rows, ipo, end, include_start=True)
        if b is not None:
            deal['bench_1m_expop_pct'] = b
            deal['alpha_1m_expop_pct'] = round(deal['aftermkt_1m_pct'] - b, 2)
    return changed
