"""Parsing, filtering, sorting, Excel ingest and rendering.  No terminal, no Outlook.

    python3 tests/test_daily_email.py          (or: pytest tests/test_daily_email.py)

The Excel tests are skipped when openpyxl is not installed.
"""

import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import daily_email as de              # noqa: E402
import fake_blpapi                    # noqa: E402

TODAY = dt.date(2026, 9, 4)
FAILURES = []


def check(name, cond, detail=''):
    if cond:
        print(f'  ok    {name}')
    else:
        print(f'  FAIL  {name}  {detail}')
        FAILURES.append(name)


# ------------------------------------------------------------ conversions ---
def test_dates_and_times():
    print('dates and times')
    check('ISO date', de.as_date('2026-09-04') == dt.date(2026, 9, 4))
    check('datetime keeps the date', de.as_date(dt.datetime(2026, 9, 4, 8, 30)) == dt.date(2026, 9, 4))
    check('Excel serial 46269 -> 2026-09-04', de.as_date(46269) == dt.date(2026, 9, 4),
          str(de.as_date(46269)))
    check('day/month/year', de.as_date('04/09/2026') == dt.date(2026, 9, 4))
    check('blank is None', de.as_date('') is None and de.as_date(None) is None)
    check('junk is None', de.as_date('n.a.') is None)
    check('clock text', de.as_time('8:30') == '08:30')
    check('Excel fraction 0.354166 -> 08:30', de.as_time(0.3541666667) == '08:30', de.as_time(0.3541666667))
    check('text time survives', de.as_time('Bef-mkt') == 'Bef-mkt')
    check('midnight datetime is not a time', de.as_time(dt.datetime(2026, 9, 4, 0, 0)) is None)
    check('time object', de.as_time(dt.time(14, 0)) == '14:00')


def test_sort_and_format():
    print('sorting and formatting')
    keys = [de.time_key('Bef-mkt'), de.time_key('08:30'), de.time_key('16:00'),
            de.time_key('Aft-mkt'), de.time_key(None)]
    check('before < clock < after < unknown', keys == sorted(keys), str(keys))
    check('thousands', de.fmt_num(1234567.0) == '1,234,567', de.fmt_num(1234567.0))
    check('trailing zeros trimmed', de.fmt_num(0.700) == '0.7', de.fmt_num(0.7))
    check('rate to 2dp', de.fmt_num(5.5, 2) == '5.50')
    check('None is a dash', de.fmt_num(None) == '–')
    check('zero prints as 0', de.fmt_num(0.0) == '0', de.fmt_num(0.0))
    check('negative survives', de.fmt_num(-0.25) == '-0.25', de.fmt_num(-0.25))
    check('today tag', de.day_tag(TODAY, TODAY) == 'TODAY')
    check('tomorrow tag', de.day_tag(TODAY + dt.timedelta(days=1), TODAY) == 'tomorrow')
    check('n-day tag', de.day_tag(TODAY + dt.timedelta(days=9), TODAY) == 'in 9 days')


def test_exclusions():
    print('exclusion list')
    check('exact name excluded', de.is_excluded('Building Permits'))
    check('case and spacing ignored', de.is_excluded('  building   permits '))
    check('kept name not excluded', not de.is_excluded('Change in Nonfarm Payrolls'))
    check('near-miss kept', not de.is_excluded('Retail Sales Advance MoM'))
    check('every VBA entry loaded', len(de._EXCLUDE) == len(set(de.EXCLUDE_EVENTS)),
          f'{len(de._EXCLUDE)} vs {len(de.EXCLUDE_EVENTS)}')
    labels = {lbl for _, lbl in de.US_ECO_TICKERS}
    unmatched = [e for e in de.EXCLUDE_EVENTS if e not in labels]
    check('every exclusion matches a configured label', not unmatched, str(unmatched))


def test_pick_date_skips_stale():
    print('date selection')
    rec = {'ECO_FUTURE_RELEASE_DATE': '2026-08-01', 'ECO_RELEASE_DT': '2026-09-20'}
    when, _ = de.pick_date(rec, ['ECO_FUTURE_RELEASE_DATE', 'ECO_RELEASE_DT'], [], TODAY)
    check('a past date falls through to the next candidate', when == dt.date(2026, 9, 20), str(when))
    rec = {'ECO_FUTURE_RELEASE_DATE': dt.datetime(2026, 9, 20, 8, 30)}
    when, t = de.pick_date(rec, ['ECO_FUTURE_RELEASE_DATE'], ['ECO_FUTURE_RELEASE_TIME'], TODAY)
    check('a datetime supplies the time', (when, t) == (dt.date(2026, 9, 20), '08:30'), f'{when} {t}')
    rec = {'ECO_FUTURE_RELEASE_DATE': '2026-09-20', 'ECO_FUTURE_RELEASE_TIME': '14:00'}
    _, t = de.pick_date(rec, ['ECO_FUTURE_RELEASE_DATE'], ['ECO_FUTURE_RELEASE_TIME'], TODAY)
    check('an explicit time field wins', t == '14:00')
    check('no usable date -> None', de.pick_date({}, ['A'], ['B'], TODAY) == (None, None))


def test_timezone_shift():
    print('time-zone conversion')
    d, t = de.shift_tz(dt.date(2026, 9, 4), '08:30', 'America/New_York', 'Asia/Hong_Kong')
    check('NY 08:30 -> HK 20:30 same day', (d, t) == (dt.date(2026, 9, 4), '20:30'), f'{d} {t}')
    d, t = de.shift_tz(dt.date(2026, 9, 4), '16:00', 'America/New_York', 'Asia/Hong_Kong')
    check('NY 16:00 rolls the date forward', (d, t) == (dt.date(2026, 9, 5), '04:00'), f'{d} {t}')
    d, t = de.shift_tz(dt.date(2026, 9, 4), 'Bef-mkt', 'America/New_York', 'Asia/Hong_Kong')
    check('text time passes through untouched', (d, t) == (dt.date(2026, 9, 4), 'Bef-mkt'))


# ------------------------------------------------------------- API path ----
def build(today=TODAY):
    fake_blpapi.configure(today)
    sections, bbg = de.build_sections_blpapi(today, blpapi_module=fake_blpapi)
    return sections, bbg


def test_api_path():
    print('Bloomberg path (fake blpapi)')
    sections, bbg = build()
    check('three sections', set(sections) == {'central_banks', 'us_eco', 'hsi_earnings'})

    eco = sections['us_eco']
    check('us_eco has rows', len(eco.rows) > 10, str(len(eco.rows)))
    check('nothing excluded survived', not [r for r in eco.rows if de.is_excluded(r['event'])])
    check('excluded rows were counted', eco.n_excluded > 0, str(eco.n_excluded))
    dates = [r['date'] for r in eco.rows]
    check('sorted by date', dates == sorted(dates))
    check('nothing in the past', all(d >= TODAY for d in dates))
    check('nothing past the horizon',
          all(d <= TODAY + dt.timedelta(days=de.LOOKAHEAD_DAYS) for d in dates))
    same_day = [r for r in eco.rows if r['date'] == dates[0]]
    check('same-day rows ordered by time',
          [de.time_key(r['time']) for r in same_day] == sorted(de.time_key(r['time']) for r in same_day))

    cb = sections['central_banks']
    check('central banks have rows', len(cb.rows) >= 5, str(len(cb.rows)))
    check('each names a bank', all(r['bank'] for r in cb.rows))
    check('countries look right', {r['country'] for r in cb.rows} <= {c for c, *_ in de.CENTRAL_BANKS})

    earn = sections['hsi_earnings']
    check('earnings have rows', len(earn.rows) >= 5, str(len(earn.rows)))
    check('tickers carry no Equity suffix', not [r for r in earn.rows if 'Equity' in r['ticker']])
    check('every row has a company name', all(r['name'] for r in earn.rows))
    check('sorted by date', [r['date'] for r in earn.rows] == sorted(r['date'] for r in earn.rows))
    check('some rows carry a conference call', any(r['call_date'] for r in earn.rows))
    check('the bulk-field fallback filled some dates', any(r['estimated'] for r in earn.rows))
    check('bulk-sourced dates are still in the window',
          all(TODAY <= r['date'] <= TODAY + dt.timedelta(days=de.LOOKAHEAD_DAYS)
              for r in earn.rows if r['estimated']))
    check('the fallback is disclosed in the notes',
          any('ERN_ANN_DT_AND_PER' in n for n in earn.notes), str(earn.notes))


def test_bulk_fields():
    print('bulk fields')
    rec = {'INDX_MEMBERS': [{'Member Ticker and Exchange Code': '700 HK'}, {'Ticker': '939 HK'}]}
    check('substring match handles both element names',
          de.bulk_field(rec, 'INDX_MEMBERS', 'ticker') == ['700 HK', '939 HK'],
          str(de.bulk_field(rec, 'INDX_MEMBERS', 'ticker')))
    odd = {'INDX_MEMBERS': [{'Something Unexpected': '1299 HK'}]}
    check('an unknown element name falls back to the first value',
          de.bulk_field(odd, 'INDX_MEMBERS', 'ticker') == ['1299 HK'])
    check('a missing bulk field is empty, not an error', de.bulk_field({}, 'X', 'y') == [])
    check('a scalar in place of a bulk field is ignored',
          de.bulk_field({'X': ['not a dict']}, 'X', 'y') == [])
    hist = {de.EARN_BULK_DATE: [{'Announcement Date': '2025-03-20'},
                                {'Announcement Date': '2026-11-12'},
                                {'Announcement Date': '2026-09-30'}]}
    check('the earliest FUTURE announcement wins',
          de.next_announced(hist, TODAY) == dt.date(2026, 9, 30),
          str(de.next_announced(hist, TODAY)))
    past = {de.EARN_BULK_DATE: [{'Announcement Date': '2025-03-20'}]}
    check('history alone yields nothing', de.next_announced(past, TODAY) is None)


def test_bad_security_and_field():
    print('error handling')
    fake_blpapi.configure(TODAY)
    bbg = de.Bloomberg(blpapi_module=fake_blpapi).connect()
    got = bbg.ref(['XXXX FAKE Index', 'FDTR Index'], ['PX_LAST', 'CONF_CALL_DT'])
    check('a dead ticker is recorded, not raised', 'XXXX FAKE Index' in bbg.bad_securities)
    check('the dead ticker returns no row', 'XXXX FAKE Index' not in got)
    check('the good ticker still comes back', 'FDTR Index' in got)
    check('a rejected mnemonic is recorded', 'CONF_CALL_DT' in bbg.field_errors)
    quiet = de.field_notes(bbg, {'call_date': ['EARNINGS_CONF_CALL_DT', 'CONF_CALL_DT']},
                           [{'EARNINGS_CONF_CALL_DT': '2026-09-20'}])
    check('a covered fallback produces no note', quiet == [], str(quiet))
    loud = de.field_notes(bbg, {'call_date': ['CONF_CALL_DT']}, [{}])
    check('a role with no data at all is flagged', len(loud) == 1 and 'call_date' in loud[0], str(loud))
    bbg.close()


def test_chunking():
    print('request chunking')
    fake_blpapi.configure(TODAY)
    bbg = de.Bloomberg(blpapi_module=fake_blpapi).connect()
    tickers = [t for t, _ in de.US_ECO_TICKERS]
    check('universe is larger than one chunk', len(tickers) > de.CHUNK, str(len(tickers)))
    got = bbg.ref(tickers, ['PX_LAST'])
    check('every ticker comes back across chunks', len(got) == len(tickers), f'{len(got)}/{len(tickers)}')
    bbg.close()


# ------------------------------------------------------------- rendering ---
def test_rendering():
    print('rendering')
    sections, _ = build()
    now = dt.datetime(2026, 9, 4, 7, 30)
    for cfg in de.EMAILS:
        subject, frag = de.render_email(cfg, sections, TODAY, now, 'test')
        check(f'[{cfg["key"]}] subject filled in', '{' not in subject, subject)
        check(f'[{cfg["key"]}] tags balance',
              frag.count('<table') == frag.count('</table>') and frag.count('<tr') == frag.count('</tr>'))
        check(f'[{cfg["key"]}] inline styles only (Outlook strips <style>)', '<style' not in frag)
        check(f'[{cfg["key"]}] recipients not in the body', 'nomura.com' not in frag)
        check(f'[{cfg["key"]}] greeting present', de.GREETING in frag)
    subject, frag = de.render_email(de.EMAILS[1], sections, TODAY, now, 'test')
    check('earnings count reaches the subject', str(len(sections['hsi_earnings'].rows)) in subject, subject)

    row = dict(date=TODAY, time='08:30', country='US', bank='', event='Fish & Chips <PMI>',
               bbg_name=None, survey=1.0, prior=2.0, relevance=99, ticker='X Index')
    frag = de.render_calendar(de.Section('us_eco', [row]), TODAY)
    check('markup in an event name is escaped', '&lt;PMI&gt;' in frag and '&amp;' in frag)

    empty = de.render_email(de.EMAILS[0], {}, TODAY, now, 'test')[1]
    check('no data still renders an email', 'Nothing returned' in empty)

    doc = de.full_document('s', frag)
    check('full document wraps the fragment', doc.startswith('<html>') and doc.rstrip().endswith('</html>'))
    spliced = de.splice_into_signature('<html><body><p>-- <br>Sig</p></body></html>', '<b>BODY</b>')
    check('body goes above the signature', spliced.index('BODY') < spliced.index('Sig'))
    check('no <body> means the fragment is still kept',
          'BODY' in de.splice_into_signature('', '<b>BODY</b>'))


def test_eml_written():
    print('files written')
    sections, _ = build()
    now = dt.datetime(2026, 9, 4, 7, 30)
    subject, frag = de.render_email(de.EMAILS[0], sections, TODAY, now, 'test')
    html_path, eml_path = de.write_files('unittest', subject, frag, TODAY, now)
    raw = open(eml_path, encoding='utf-8').read()
    check('.eml opens in compose mode', 'X-Unsent: 1' in raw)
    check('.eml is addressed', 'nomura.com' in raw)
    check('.eml carries the HTML part', 'text/html' in raw)
    check('.html written', os.path.getsize(html_path) > 500)
    for p in (html_path, eml_path):
        os.remove(p)


# ----------------------------------------------------------- excel path ----
def test_excel_path():
    print('Excel path')
    try:
        import openpyxl
    except ImportError:
        print('  skip  openpyxl not installed')
        return
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = 'BQL'
    # A BQL calendar block, exactly the shape the add-in spills: header then rows.
    ws.append(['ID', 'RELEASE_DATE', 'RELEASE_TIME', 'EVENT_NAME', 'SURVEY_MEDIAN', 'PRIOR'])
    rows = [
        ('US Country', dt.datetime(2026, 9, 8), 0.3541666667, 'Change in Nonfarm Payrolls', 75, 22),
        ('US Country', dt.datetime(2026, 9, 8), 0.3541666667, 'Building Permits', 1.4, 1.5),   # excluded
        ('US Country', dt.datetime(2026, 9, 10), 0.3541666667, 'CPI MoM', 0.2, 0.3),
        ('US Country', dt.datetime(2026, 8, 1), 0.3541666667, 'CPI YoY', 2.9, 3.0),            # past
        ('US Country', dt.datetime(2027, 6, 1), 0.3541666667, 'GDP Annualized QoQ', 2.0, 1.8), # beyond
    ]
    for r in rows:
        ws.append(list(r))
    ws2 = wb.create_sheet('EARN')
    ws2.append(['ID', 'NAME', 'EXPECTED_REPORT_DT', 'EXPECTED_REPORT_TIME',
                'EARNINGS_CONF_CALL_DT', 'EARNINGS_CONF_CALL_TIME'])
    ws2.append(['700 HK Equity', 'TENCENT', dt.datetime(2026, 11, 12), 'Aft-mkt',
                dt.datetime(2026, 11, 12), 0.6875])
    ws2.append(['939 HK Equity', 'CCB', dt.datetime(2026, 10, 29), 'Bef-mkt', None, None])
    ws2.append(['1 HK Equity', 'CKH', dt.datetime(2025, 3, 20), 'Bef-mkt', None, None])   # past
    path = os.path.join(HERE, '_tmp_excel_test.xlsx')
    wb.save(path)
    try:
        sections = de.read_excel_sections(path, TODAY)
        eco = sections.get('us_eco')
        check('calendar block found', eco is not None)
        events = [r['event'] for r in eco.rows]
        check('two rows kept', len(eco.rows) == 2, str(events))
        check('excluded name dropped', 'Building Permits' not in events)
        check('past row dropped', 'CPI YoY' not in events)
        check('beyond-horizon row dropped', 'GDP Annualized QoQ' not in events)
        check('Excel time fraction decoded', eco.rows[0]['time'] == '08:30', str(eco.rows[0]['time']))
        check('survey read', eco.rows[0]['survey'] == 75, str(eco.rows[0]['survey']))
        earn = sections.get('hsi_earnings')
        check('earnings block found', earn is not None)
        check('two names kept', len(earn.rows) == 2, str([r['ticker'] for r in earn.rows]))
        check('earliest first', earn.rows[0]['ticker'] == '939 HK', str(earn.rows[0]))
        check('Equity suffix stripped', all(' Equity' not in r['ticker'] for r in earn.rows))
        check('call time decoded', earn.rows[1]['call_time'] == '16:30', str(earn.rows[1]['call_time']))
        subject, frag = de.render_email(de.EMAILS[1], sections, TODAY, dt.datetime(2026, 9, 4), 'xl')
        check('an Excel-sourced email renders', 'TENCENT' in frag)
    finally:
        os.remove(path)


def test_column_mapping():
    print('column mapping')
    m = de.map_columns(['ID', 'RELEASE_DATE', 'RELEASE_TIME', 'EVENT_NAME', 'SURVEY_MEDIAN', 'PRIOR'],
                       de.CAL_SPEC)
    check('date column', m['date'] == 1, str(m))
    check('time not confused with date', m['time'] == 2, str(m))
    check('event column', m['event'] == 3, str(m))
    check('survey column', m['survey'] == 4, str(m))
    check('prior column', m['prior'] == 5, str(m))
    m = de.map_columns(['#DATES', '#TIMES', '#EVENTS', '#SURVEY', '#PRIOR'], de.CAL_SPEC)
    check('BQL # headers still map', m.get('event') == 2 and m.get('survey') == 3, str(m))
    check('calendar header classified', de.classify_header(['RELEASE_DATE', 'EVENT_NAME']) == 'calendar')
    check('earnings header classified',
          de.classify_header(['EXPECTED_REPORT_DT', 'NAME']) == 'hsi_earnings')
    check('an unrelated header is ignored', de.classify_header(['Price', 'Qty']) is None)


def test_config_sanity():
    print('config')
    tickers = [t for t, _ in de.US_ECO_TICKERS]
    check('no duplicate US tickers', len(tickers) == len(set(tickers)))
    cb = [t for _, _, t, _, _ in de.CENTRAL_BANKS]
    check('no duplicate CB tickers', len(cb) == len(set(cb)))
    check('every ticker carries a yellow key',
          all(t.split()[-1] in ('Index', 'Equity', 'Curncy', 'Comdty') for t in tickers + cb))
    keys = [k for cfg in de.EMAILS for k in cfg['sections']]
    check('every email section is produced', set(keys) <= set(de.SECTION_TITLES))
    check('every section has a title', set(de.SECTION_TITLES) >= set(keys))
    check('recipients are the two names asked for',
          de.RECIPIENTS.count('@') == 2 and 'oscar.chan1@nomura.com' in de.RECIPIENTS)


if __name__ == '__main__':
    for fn in [test_dates_and_times, test_sort_and_format, test_exclusions, test_pick_date_skips_stale,
               test_timezone_shift, test_api_path, test_bulk_fields, test_bad_security_and_field,
               test_chunking,
               test_rendering, test_eml_written, test_excel_path, test_column_mapping,
               test_config_sanity]:
        fn()
    print()
    if FAILURES:
        print(f'{len(FAILURES)} FAILED: ' + ', '.join(FAILURES))
        sys.exit(1)
    print('all tests passed')
