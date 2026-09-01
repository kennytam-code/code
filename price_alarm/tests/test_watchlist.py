"""Watchlist CSV loading and validation.

    python3 test_watchlist.py     (or: pytest test_watchlist.py)
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from price_alarm import (DEFAULT_MAX_REPEATS, default_nickname,   # noqa: E402
                         load_watchlist, parse_thresholds)

HEAD = 'Ticker,NickName,Thresholds,MaxRepeats\n'


def write(body, head=HEAD):
    fh = tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False,
                                     newline='', encoding='utf-8')
    fh.write(head + body)
    fh.close()
    return fh.name


def fails(body, needle, head=HEAD):
    try:
        load_watchlist(write(body, head))
    except ValueError as exc:
        assert needle in str(exc), f'expected {needle!r} in: {exc}'
        return
    raise AssertionError(f'should have been rejected: {body!r}')


def test_good_file_loads():
    items = load_watchlist(write(
        '700 HK Equity,Tencent,3;5;-3;-5,\n'
        '2330 TT Equity,TSMC,3;-3,2\n'
        'NVDA US Equity,Nvidia,5;-5,1\n'))
    assert [it.ticker for it in items] == [
        '700 HK Equity', '2330 TT Equity', 'NVDA US Equity']
    assert items[0].thresholds == [3.0, 5.0, -3.0, -5.0]
    assert items[0].max_repeats == DEFAULT_MAX_REPEATS   # blank column
    assert items[1].max_repeats == 2
    assert items[2].nickname == 'Nvidia'


def test_blank_nickname_falls_back_to_the_ticker_stem():
    items = load_watchlist(write('700 HK Equity,,3,\n'))
    assert items[0].nickname == '700 HK'
    assert default_nickname('NVDA US Equity') == 'NVDA US'
    assert default_nickname('HSI Index') == 'HSI'
    assert default_nickname('PLAIN') == 'PLAIN'


def test_blank_rows_and_comments_are_skipped():
    items = load_watchlist(write('# a note,,,\n'
                                 ',,,\n'
                                 '700 HK Equity,Tencent,3,\n'))
    assert len(items) == 1


def test_percent_signs_and_spaces_survive():
    assert parse_thresholds(' 3% ; -3 %;5') == [3.0, -3.0, 5.0]
    assert parse_thresholds('3;;;-3') == [3.0, -3.0]     # empty pieces skipped


def test_duplicate_ticker_rejected():
    fails('700 HK Equity,Tencent,3,\n700 HK Equity,Again,5,\n', 'listed twice')


def test_duplicate_threshold_rejected():
    fails('700 HK Equity,Tencent,3;3,\n', 'listed twice')


def test_zero_threshold_rejected():
    fails('700 HK Equity,Tencent,0,\n', 'fire constantly')


def test_garbage_threshold_rejected():
    fails('700 HK Equity,Tencent,3;abc,\n', 'not a number')


def test_empty_threshold_column_rejected():
    fails('700 HK Equity,Tencent,,\n', 'no thresholds')


def test_bad_max_repeats_rejected():
    fails('700 HK Equity,Tencent,3,zero\n', 'not a whole number')
    fails('700 HK Equity,Tencent,3,0\n', '1 or more')


def test_missing_column_named_in_the_error():
    fails('700 HK Equity,3\n', 'thresholds', head='Ticker,Levels\n')


def test_empty_watchlist_rejected():
    fails('', 'no tickers found')


def test_error_names_the_row():
    fails('700 HK Equity,Tencent,3,\n2330 TT Equity,TSMC,oops,\n', 'row 3')


if __name__ == '__main__':
    bad = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith('test_') or not callable(fn):
            continue
        try:
            fn()
            print(f'  PASS  {name}')
        except AssertionError as exc:
            bad += 1
            print(f'  FAIL  {name}: {exc}')
    print(f'{"all watchlist tests pass" if not bad else str(bad) + " FAILED"}')
    sys.exit(1 if bad else 0)
