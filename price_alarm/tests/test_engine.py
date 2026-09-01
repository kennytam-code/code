"""Crossing rules for AlarmEngine.  No Bloomberg, no audio, no window.

    python3 test_engine.py        (or: pytest test_engine.py)
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from price_alarm import AlarmEngine, WatchItem, announcement   # noqa: E402

T0 = datetime(2026, 9, 2, 10, 0, 0)


def engine(thresholds=(3, -3), max_repeats=2, buffer=0.25, nick='Tencent'):
    item = WatchItem('700 HK Equity', nick, list(thresholds), max_repeats)
    return AlarmEngine([item], rearm_buffer=buffer)


def feed(eng, *pcts, price=100.0, now=T0, ticker='700 HK Equity'):
    """Push a price path, collect everything spoken."""
    spoken = []
    for pct in pcts:
        spoken += eng.update(ticker, price, pct, now=now)
    return spoken


def test_cross_up_speaks_once():
    eng = engine()
    spoken = feed(eng, 0.5, 1.8, 3.1, 3.4, 3.9)
    assert len(spoken) == 1, spoken
    assert spoken[0] == 'Tencent is trading at 100.00, up 3.1 percent'


def test_chatter_at_the_threshold_speaks_once():
    # 3.05 -> 2.95 -> 3.05 never retreats past the 0.25 buffer, so it stays spent
    eng = engine()
    spoken = feed(eng, 3.05, 2.95, 3.05, 2.90, 3.10)
    assert len(spoken) == 1, spoken


def test_retreat_past_buffer_then_recross_speaks_twice():
    eng = engine()
    spoken = feed(eng, 3.1, 2.5, 3.2)          # 2.5 < 3 - 0.25 -> re-armed
    assert len(spoken) == 2, spoken


def test_cap_is_per_threshold_per_day():
    eng = engine(max_repeats=2)
    spoken = feed(eng, 3.1, 2.0, 3.2, 2.0, 3.3, 2.0, 3.4)
    assert len(spoken) == 2, spoken
    thr, armed, count, mx = eng.status('700 HK Equity')[0]
    assert (thr, count, mx) == (3, 2, 2)


def test_down_threshold_mirrors_up():
    eng = engine()
    spoken = feed(eng, -1.0, -3.4)
    assert len(spoken) == 1, spoken
    assert spoken[0] == 'Tencent is trading at 100.00, down 3.4 percent'
    # chatter on the downside is equally quiet
    assert feed(eng, -2.95, -3.05) == []
    # a real bounce past the buffer re-arms it
    assert len(feed(eng, -2.5, -3.6)) == 1


def test_one_jump_through_two_levels_speaks_once_and_spends_both():
    eng = engine(thresholds=(3, 5))
    spoken = feed(eng, 0.0, 5.5)
    assert len(spoken) == 1, spoken
    assert 'up 5.5 percent' in spoken[0]
    counts = {thr: count for thr, _, count, _ in eng.status('700 HK Equity')}
    assert counts == {3: 1, 5: 1}, counts


def test_first_update_already_beyond_threshold_fires():
    # launching the alarm when the name is already +4 is information, not noise
    eng = engine()
    assert len(feed(eng, 4.0)) == 1


def test_missing_price_is_a_no_op():
    eng = engine()
    assert eng.update('700 HK Equity', None, None, now=T0) == []
    assert eng.update('700 HK Equity', 100.0, None, now=T0) == []
    thr, armed, count, mx = eng.status('700 HK Equity')[0]
    assert armed is True and count == 0


def test_unknown_ticker_is_a_no_op():
    eng = engine()
    assert eng.update('9988 HK Equity', 100.0, 9.0, now=T0) == []


def test_new_day_rearms_and_resets_counts():
    eng = engine(max_repeats=1)
    assert len(feed(eng, 3.5)) == 1
    assert feed(eng, 2.0, 3.6) == []                       # cap spent today
    tomorrow = T0 + timedelta(days=1)
    assert len(feed(eng, 3.7, now=tomorrow)) == 1           # fresh day, fresh cap
    thr, armed, count, mx = eng.status('700 HK Equity')[0]
    assert count == 1


def test_reset_button_rearms_everything():
    eng = engine(max_repeats=1)
    feed(eng, 3.5)
    assert feed(eng, 2.0, 3.6) == []
    eng.reset()
    assert len(feed(eng, 3.7)) == 1


def test_per_ticker_cap_beats_the_default():
    tight = WatchItem('AAA US Equity', 'Alpha', [3], 1)
    loose = WatchItem('BBB US Equity', 'Beta', [3], 3)
    eng = AlarmEngine([tight, loose])
    for pct in (3.5, 2.0, 3.6, 2.0, 3.7):
        eng.update('AAA US Equity', 10.0, pct, now=T0)
        eng.update('BBB US Equity', 10.0, pct, now=T0)
    assert eng.status('AAA US Equity')[0][2] == 1
    assert eng.status('BBB US Equity')[0][2] == 3


def test_zero_buffer_lets_it_chatter():
    # documented behaviour: buffer 0 re-arms the moment it ticks back below
    eng = engine(buffer=0.0, max_repeats=99)
    assert len(feed(eng, 3.1, 2.99, 3.1, 2.99, 3.1)) == 3


def test_announcement_wording():
    assert (announcement('Nvidia', 1234.5, 3.14)
            == 'Nvidia is trading at 1,234.50, up 3.1 percent')
    assert (announcement('TSMC', 98.765, -5.0)
            == 'TSMC is trading at 98.77, down 5.0 percent')


if __name__ == '__main__':
    fails = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith('test_') or not callable(fn):
            continue
        try:
            fn()
            print(f'  PASS  {name}')
        except AssertionError as exc:
            fails += 1
            print(f'  FAIL  {name}: {exc}')
    print(f'{"all engine tests pass" if not fails else str(fails) + " FAILED"}')
    sys.exit(1 if fails else 0)
