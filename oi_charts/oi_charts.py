#!/usr/bin/env python3
"""Daily open interest for index futures, straight from Bloomberg, one Excel tab per product.

For every monthly contract expiring Jan 2024 - Dec 2026 (36 per product) the script
pulls OPEN_INT from the contract's last trade date back two years (or as far as
Bloomberg has data) and writes ONE workbook:

    <product tab>   raw data: column A = date, one column per contract (row 1 the
                    ticker, row 2 the label, e.g. 'Jan 24'), blank where the
                    contract has no print - plus a line chart, one line per contract
    Contracts       the audit trail: which ticker form resolved, status
                    (OK / NOT FOUND / NO DATA), last trade date, request window,
                    first and last date with data, rows, last and max OI

Ticker forms.  Bloomberg quotes a live contract with a one-digit year (HIU6) and an
expired one with two digits (HIU25).  Nothing here assumes which is which: both
forms are requested and the one whose LAST_TRADEABLE_DT falls in the intended month
is used.  A contract month the exchange never listed (serial months on a quarterly-
only product) comes back NOT FOUND - it is counted and listed, never invented.

Run on a machine with the Bloomberg terminal logged in:

    python oi_charts.py                    -> OI_charts_<yyyymmdd>.xlsx in this folder
    python oi_charts.py --tickers-only     resolve and print the contract table only
    python oi_charts.py --out C:/x.xlsx    choose the output file
    python oi_charts.py --years-back 3     longer history per contract

From a notebook:  %run oi_charts.py   then   run()   in the next cell.

Needs:  blpapi    pip install blpapi --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/
        openpyxl  pip install openpyxl
"""
import argparse
import dataclasses
import datetime as dt
import sys
from typing import Dict, List, Optional, Tuple

from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.chart.axis import DateAxis
from openpyxl.utils import get_column_letter

# ================================================================ CONFIG ===
# (Bloomberg root, tab name).  Edit this list to add or drop a product.  The
# request note listed "MSCI - HJAU6" and "TAMSCI - HJAU6": one root, so one tab.
PRODUCTS = [
    ('HI',  'HSI'),
    ('HC',  'HSCEI'),
    ('HCT', 'HSTECH'),
    ('KM',  'KOSPI2'),
    ('XP',  'AS51'),
    ('FT',  'TWSE'),
    ('TWT', 'FTSE TW'),
    ('FPO', 'FPO'),
    ('HJA', 'TAMSCI'),
    ('QZ',  'SIMSCI'),
]
START_YEAR, END_YEAR = 2024, 2026        # first and last contract month (Jan .. Dec)
YEARS_BACK = 2                           # history per contract, back from its last trade date

HIST_FIELD = 'OPEN_INT'                  # daily open interest of one contract
REF_FIELDS = ['LAST_TRADEABLE_DT', 'FUT_MONTH_YR', 'NAME']

BBG_HOST, BBG_PORT = 'localhost', 8194
EVENT_SPINS = 240                        # 500 ms each: ~2 min per request, then it is an error
REF_CHUNK = 100                          # securities per ReferenceDataRequest

MONTH_CODES = 'FGHJKMNQUVXZ'             # index 0 = January
MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

OK, NOT_FOUND, NO_DATA = 'OK', 'NOT FOUND', 'NO DATA'
AUDIT_SHEET = 'Contracts'
AUDIT_COLUMNS = ['Product', 'Contract', 'Ticker 1-digit', 'Ticker 2-digit', 'Ticker used',
                 'Status', 'LAST_TRADEABLE_DT', 'FUT_MONTH_YR', 'Name', 'Request start',
                 'Request end', 'First OI date', 'Last OI date', 'Rows', 'Last OI', 'Max OI',
                 'Note']


# =============================================================== HELPERS ===
def contract_months(start_year, end_year):
    """[(year, month)] for every month from Jan start_year to Dec end_year."""
    return [(y, m) for y in range(start_year, end_year + 1) for m in range(1, 13)]


def month_label(year, month):
    """(2024, 1) -> 'Jan 24'."""
    return '%s %02d' % (MONTH_ABBR[month - 1], year % 100)


def candidate_tickers(root, year, month):
    """('HI', 2026, 1) -> ('HIF6 Index', 'HIF26 Index'): the one- and two-digit forms."""
    code = MONTH_CODES[month - 1]
    return ('%s%s%d Index' % (root, code, year % 10),
            '%s%s%02d Index' % (root, code, year % 100))


def years_back(d, n):
    """Same calendar day n years earlier; 29 Feb falls back to 28 Feb."""
    try:
        return d.replace(year=d.year - n)
    except ValueError:
        return d.replace(year=d.year - n, day=28)


def as_date(v):
    """A date from whatever blpapi hands back: datetime, date, or 'YYYY-MM-DD...' text."""
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    try:
        return dt.date.fromisoformat(str(v).strip()[:10])
    except ValueError:
        return None


def element_value(el):
    """Python value of a response element: scalars as-is, bulk fields as list of dicts."""
    if el.isArray():
        if el.isComplexType():
            return [element_dict(el.getValueAsElement(i)) for i in range(el.numValues())]
        return [el.getValue(i) for i in range(el.numValues())]
    if el.isComplexType():
        return element_dict(el)
    if el.isNull():
        return None
    try:
        return el.getValue()
    except Exception:
        return el.getValueAsString()


def element_dict(el):
    return {str(el.getElement(i).name()): element_value(el.getElement(i))
            for i in range(el.numElements())}


@dataclasses.dataclass
class Contract:
    product: str                     # tab name, e.g. 'HSI'
    root: str                        # 'HI'
    year: int
    month: int
    label: str                       # 'Jan 24'
    ticker_1: str                    # 'HIF4 Index'  (one-digit year)
    ticker_2: str                    # 'HIF24 Index' (two-digit year)
    ticker: str = ''                 # the form that resolved ('' when NOT FOUND)
    status: str = NOT_FOUND
    last_trade: Optional[dt.date] = None
    fut_month_yr: str = ''
    name: str = ''
    req_start: Optional[dt.date] = None
    req_end: Optional[dt.date] = None
    rows: List[Tuple[dt.date, float]] = dataclasses.field(default_factory=list)  # sorted
    note: str = ''

    @property
    def first_dt(self):
        return self.rows[0][0] if self.rows else None

    @property
    def last_dt(self):
        return self.rows[-1][0] if self.rows else None

    @property
    def last_oi(self):
        return self.rows[-1][1] if self.rows else None

    @property
    def max_oi(self):
        return max(v for _, v in self.rows) if self.rows else None


# ============================================================= BLOOMBERG ===
class Bloomberg:
    """One session for the whole run (the daily_email / price_alarm pattern).

    Dead tickers and rejected mnemonics are collected, not raised: the caller
    decides what a gap means and the summary says what is missing.
    """

    def __init__(self, host=BBG_HOST, port=BBG_PORT, blpapi_module=None):
        self.host, self.port = host, port
        self.blpapi = blpapi_module          # None -> import the real one in connect()
        self.session = None
        self.services = {}
        self.field_errors = {}               # mnemonic -> Bloomberg's message (first seen)
        self.bad_securities = {}             # security -> message

    def connect(self):
        if self.blpapi is None:
            try:
                import blpapi
            except ImportError:
                raise RuntimeError(
                    'blpapi is not installed in this Python - run from the prompt the desk '
                    'notebooks use, or: pip install blpapi --index-url='
                    'https://blpapi.bloomberg.com/repository/releases/python/simple/')
            self.blpapi = blpapi
        opts = self.blpapi.SessionOptions()
        opts.setServerHost(self.host)
        opts.setServerPort(self.port)
        self.session = self.blpapi.Session(opts)
        if not self.session.start():
            raise RuntimeError('cannot start a Bloomberg session - is the terminal running '
                               'and logged in on this machine?')
        return self

    def close(self):
        try:
            if self.session is not None:
                self.session.stop()
        except Exception:
            pass
        self.session, self.services = None, {}

    def service(self, name):
        if name not in self.services:
            if not self.session.openService(name):
                raise RuntimeError('cannot open %s' % name)
            self.services[name] = self.session.getService(name)
        return self.services[name]

    def _drain(self, request, take):
        """Send one request, hand every message to take(msg), stop at the final RESPONSE."""
        self.session.sendRequest(request)
        events = self.blpapi.Event
        failed = getattr(events, 'REQUEST_STATUS', None)
        for _ in range(EVENT_SPINS):                 # bounded: never hang the desk
            ev = self.session.nextEvent(500)
            if failed is not None and ev.eventType() == failed:
                texts = [m.toString() for m in ev]
                raise RuntimeError('Bloomberg rejected the request: ' + (texts[0] if texts else '?'))
            for msg in ev:
                take(msg)
            if ev.eventType() == events.RESPONSE:
                return
        raise RuntimeError('Bloomberg did not answer within ~2 min - check the terminal session')

    # -- response plumbing shared by ref() and history() --
    @staticmethod
    def _check_response_error(msg):
        if msg.hasElement('responseError'):
            err = msg.getElement('responseError')
            raise RuntimeError('Bloomberg responseError: ' + (
                err.getElementAsString('message') if err.hasElement('message') else '?'))

    @staticmethod
    def _items(el):
        """securityData is an array in reference responses and a single element in historical ones."""
        if el.isArray():
            return [el.getValueAsElement(i) for i in range(el.numValues())]
        return [el]

    @staticmethod
    def _error_text(err):
        return err.getElementAsString('message') if err.hasElement('message') else 'security error'

    def _note_field_exceptions(self, sd):
        if not sd.hasElement('fieldExceptions'):
            return
        fe = sd.getElement('fieldExceptions')
        for j in range(fe.numValues()):
            x = fe.getValueAsElement(j)
            fid = x.getElementAsString('fieldId')
            text = 'field exception'
            if x.hasElement('errorInfo'):
                info = x.getElement('errorInfo')
                parts = [info.getElementAsString(k) for k in ('subcategory', 'message')
                         if info.hasElement(k)]
                text = ' / '.join(p for p in parts if p) or text
            self.field_errors.setdefault(fid, text)

    def ref(self, securities, fields):
        """ReferenceDataRequest -> {security: {field: value}}; unknown securities are skipped."""
        out = {}
        svc = self.service('//blp/refdata')
        securities = list(securities)

        def take(msg):
            self._check_response_error(msg)
            if not msg.hasElement('securityData'):
                return
            for sd in self._items(msg.getElement('securityData')):
                sec = sd.getElementAsString('security')
                if sd.hasElement('securityError'):
                    self.bad_securities[sec] = self._error_text(sd.getElement('securityError'))
                    continue
                self._note_field_exceptions(sd)
                row = {}
                if sd.hasElement('fieldData'):
                    fd = sd.getElement('fieldData')
                    for j in range(fd.numElements()):
                        el = fd.getElement(j)
                        row[str(el.name())] = element_value(el)
                out[sec] = row

        for i in range(0, len(securities), REF_CHUNK):
            rq = svc.createRequest('ReferenceDataRequest')
            for s in securities[i:i + REF_CHUNK]:
                rq.getElement('securities').appendValue(s)
            for f in fields:
                rq.getElement('fields').appendValue(f)
            self._drain(rq, take)
        return out

    def history(self, security, field, start, end):
        """HistoricalDataRequest, daily, active days only -> [(date, value)] sorted by date."""
        svc = self.service('//blp/refdata')
        rq = svc.createRequest('HistoricalDataRequest')
        rq.getElement('securities').appendValue(security)
        rq.getElement('fields').appendValue(field)
        rq.set('startDate', start.strftime('%Y%m%d'))
        rq.set('endDate', end.strftime('%Y%m%d'))
        rq.set('periodicitySelection', 'DAILY')
        rq.set('periodicityAdjustment', 'ACTUAL')
        rq.set('nonTradingDayFillOption', 'ACTIVE_DAYS_ONLY')   # no filled holidays, no NA
        rows = []

        def take(msg):
            self._check_response_error(msg)
            if not msg.hasElement('securityData'):
                return
            for sd in self._items(msg.getElement('securityData')):
                sec = sd.getElementAsString('security')
                if sd.hasElement('securityError'):
                    self.bad_securities[sec] = self._error_text(sd.getElement('securityError'))
                    continue
                self._note_field_exceptions(sd)
                if not sd.hasElement('fieldData'):
                    continue
                fd = sd.getElement('fieldData')
                for j in range(fd.numValues()):
                    pt = fd.getValueAsElement(j)
                    if not pt.hasElement('date') or not pt.hasElement(field):
                        continue
                    if pt.getElement(field).isNull():
                        continue
                    d = as_date(pt.getElementAsDatetime('date'))
                    if d is not None:
                        rows.append((d, float(pt.getElementAsFloat(field))))

        self._drain(rq, take)
        rows.sort()
        return rows


# ============================================================== PIPELINE ===
def build_contracts(products, months):
    """[(tab name, [Contract, ...])] in PRODUCTS order, contracts in expiry order."""
    out = []
    for root, name in products:
        cs = []
        for y, m in months:
            t1, t2 = candidate_tickers(root, y, m)
            cs.append(Contract(product=name, root=root, year=y, month=m,
                               label=month_label(y, m), ticker_1=t1, ticker_2=t2))
        out.append((name, cs))
    return out


def pick_ticker(c, ref, bad_securities, today):
    """Choose the form whose LAST_TRADEABLE_DT is in the contract month; mark NOT FOUND otherwise."""
    seen, valid = [], []
    for t in (c.ticker_1, c.ticker_2):
        row = ref.get(t)
        if not row:
            continue
        ltd = as_date(row.get('LAST_TRADEABLE_DT'))
        if ltd is None:
            continue
        seen.append((t, ltd))
        if (ltd.year, ltd.month) == (c.year, c.month):
            valid.append((t, ltd, row))
    if not valid:
        c.status = NOT_FOUND
        if seen:
            c.note = 'LAST_TRADEABLE_DT outside the contract month: ' + ', '.join(
                '%s -> %s' % (t, d.isoformat()) for t, d in seen)
        else:
            errs = [bad_securities[t] for t in (c.ticker_1, c.ticker_2) if t in bad_securities]
            c.note = errs[0] if errs else 'no LAST_TRADEABLE_DT returned for either form'
        return
    if len(valid) == 2:
        # both forms resolve: use the one the desk would type (expired -> two digits)
        choice = valid[1] if valid[0][1] < today else valid[0]
        c.note = 'both forms valid'
    else:
        choice = valid[0]
    t, ltd, row = choice
    c.ticker, c.last_trade, c.status = t, ltd, OK
    c.fut_month_yr = str(row.get('FUT_MONTH_YR') or '')
    c.name = str(row.get('NAME') or '')


def resolve_contracts(bbg, products, months, today):
    """One batched reference pass over both ticker forms of every contract."""
    results = build_contracts(products, months)
    candidates = [t for _, cs in results for c in cs for t in (c.ticker_1, c.ticker_2)]
    ref = bbg.ref(candidates, REF_FIELDS)
    for _, cs in results:
        for c in cs:
            pick_ticker(c, ref, bbg.bad_securities, today)
    return results


def fetch_open_interest(bbg, c, years_back_n, today):
    """Fill c.rows with daily OPEN_INT from last trade - years_back_n to min(last trade, today)."""
    if c.status != OK:
        return
    c.req_start = years_back(c.last_trade, years_back_n)
    c.req_end = min(c.last_trade, today)
    if c.req_start > c.req_end:
        c.status, c.note = NO_DATA, 'window starts after today'
        return
    c.rows = bbg.history(c.ticker, HIST_FIELD, c.req_start, c.req_end)
    if not c.rows:
        c.status = NO_DATA
        c.note = bbg.bad_securities.get(c.ticker) or ('no %s rows returned' % HIST_FIELD)


def align_product(contracts):
    """(sorted union of dates, contracts that have data) - the shape of one product tab."""
    found = [c for c in contracts if c.status == OK and c.rows]
    dates = sorted({d for c in found for d, _ in c.rows})
    return dates, found


# ============================================================== WORKBOOK ===
def safe_sheet_name(name):
    for ch in '[]:*?/\\':
        name = name.replace(ch, ' ')
    return name.strip()[:31]


def add_oi_chart(ws, name, n_series, n_rows):
    """One line per contract; blanks are gaps, so each line spans only its own data."""
    ch = LineChart()
    ch.title = '%s Futures Open Interest' % name
    ch.y_axis.title = 'OI'
    ch.display_blanks = 'gap'
    ch.x_axis = DateAxis(crossAx=100)          # axId 500; the value axis must cross it
    ch.x_axis.number_format = 'mmm-yy'
    ch.x_axis.majorTimeUnit = 'months'
    ch.y_axis.crossAx = 500
    ch.y_axis.number_format = '#,##0'
    ch.x_axis.delete = False                   # newer Excel hides axes when this is absent
    ch.y_axis.delete = False
    ch.legend.position = 'b'
    ch.width, ch.height = 32, 16               # cm
    last_row = 2 + n_rows
    ch.add_data(Reference(ws, min_col=2, max_col=1 + n_series, min_row=2, max_row=last_row),
                titles_from_data=True)          # row 2 = the 'Jan 24' labels
    ch.set_categories(Reference(ws, min_col=1, min_row=3, max_row=last_row))
    for s in ch.series:
        s.marker.symbol = 'none'
        s.smooth = False
        s.graphicalProperties.line.width = 12700   # EMU: 1 pt
    ws.add_chart(ch, '%s2' % get_column_letter(n_series + 3))


def write_product_sheet(wb, name, contracts):
    ws = wb.create_sheet(title=safe_sheet_name(name))
    dates, found = align_product(contracts)
    ws['A1'] = 'Ticker'
    ws['A2'] = 'Date'
    ws.column_dimensions['A'].width = 12
    if not found:
        ws['B1'] = 'No contract returned open-interest data - see the %s tab' % AUDIT_SHEET
        return ws
    for j, c in enumerate(found, start=2):
        ws.cell(row=1, column=j, value=c.ticker)
        ws.cell(row=2, column=j, value=c.label)
    lookups = [dict(c.rows) for c in found]
    for i, d in enumerate(dates, start=3):
        ws.cell(row=i, column=1, value=d).number_format = 'yyyy-mm-dd'
        for j, lk in enumerate(lookups, start=2):
            v = lk.get(d)
            if v is not None:                       # a missing print stays an empty cell
                ws.cell(row=i, column=j, value=v).number_format = '#,##0'
    ws.freeze_panes = 'B3'
    add_oi_chart(ws, name, len(found), len(dates))
    return ws


def audit_row(c):
    return [c.product, c.label, c.ticker_1, c.ticker_2, c.ticker or None, c.status,
            c.last_trade, c.fut_month_yr or None, c.name or None, c.req_start, c.req_end,
            c.first_dt, c.last_dt, (len(c.rows) if c.status != NOT_FOUND else None),
            c.last_oi, c.max_oi, c.note or None]


def write_contracts_sheet(wb, results):
    ws = wb.create_sheet(title=AUDIT_SHEET)
    for j, h in enumerate(AUDIT_COLUMNS, start=1):
        ws.cell(row=1, column=j, value=h)
    r = 1
    for _, cs in results:
        for c in cs:
            r += 1
            for j, v in enumerate(audit_row(c), start=1):
                if v is None:
                    continue
                cell = ws.cell(row=r, column=j, value=v)
                if isinstance(v, dt.date):
                    cell.number_format = 'yyyy-mm-dd'
                elif isinstance(v, float):
                    cell.number_format = '#,##0'
    ws.freeze_panes = 'A2'
    for j, w in enumerate([10, 9, 15, 15, 15, 11, 18, 13, 26, 13, 13, 13, 13, 7, 10, 10, 60], start=1):
        ws.column_dimensions[get_column_letter(j)].width = w
    return ws


def write_workbook(path, results):
    wb = Workbook()
    wb.remove(wb.active)
    for name, cs in results:
        write_product_sheet(wb, name, cs)
    write_contracts_sheet(wb, results)
    wb.save(path)
    return path


# =============================================================== CONSOLE ===
def print_contract_table(results):
    print('%-8s %-7s %-14s %-9s %-11s %s' % ('Product', 'Month', 'Ticker', 'Status', 'Last trade', 'Note'))
    for name, cs in results:
        for c in cs:
            print('%-8s %-7s %-14s %-9s %-11s %s' % (
                name, c.label, c.ticker or '-', c.status,
                c.last_trade.isoformat() if c.last_trade else '-', c.note))
    print()


def print_summary(results, bbg, out):
    print()
    for name, cs in results:
        n_ok = sum(1 for c in cs if c.status == OK)
        print('%-8s %2d/%d contracts with data' % (name, n_ok, len(cs)))
        for status in (NOT_FOUND, NO_DATA):
            labels = [c.label for c in cs if c.status == status]
            if labels:
                print('         %-9s %s' % (status + ':', ', '.join(labels)))
    if bbg.field_errors:
        print('Bloomberg rejected these fields: ' + ', '.join(
            '%s (%s)' % kv for kv in sorted(bbg.field_errors.items())))
    if out:
        print('Written: %s' % out)


# =================================================================== RUN ===
def run(products=None, start_year=START_YEAR, end_year=END_YEAR, years_back_n=YEARS_BACK,
        out=None, today=None, blpapi_module=None, tickers_only=False,
        host=BBG_HOST, port=BBG_PORT):
    """Resolve every contract, pull its open interest, write the workbook; returns the path."""
    products = list(PRODUCTS if products is None else products)
    today = today or dt.date.today()
    months = contract_months(start_year, end_year)
    bbg = Bloomberg(host, port, blpapi_module=blpapi_module).connect()
    try:
        print('Resolving %d contracts for %d products (%d candidate tickers) ...'
              % (len(months) * len(products), len(products), 2 * len(months) * len(products)))
        results = resolve_contracts(bbg, products, months, today)
        if tickers_only:
            print_contract_table(results)
            print_summary(results, bbg, None)
            return ''
        for name, cs in results:
            n_ok = sum(1 for c in cs if c.status == OK)
            print('%-8s pulling %s for %d/%d contracts ' % (name, HIST_FIELD, n_ok, len(cs)),
                  end='', flush=True)
            for c in cs:
                if c.status == OK:
                    fetch_open_interest(bbg, c, years_back_n, today)
                    print('.', end='', flush=True)
            print()
    finally:
        bbg.close()
    out = out or 'OI_charts_%s.xlsx' % today.strftime('%Y%m%d')
    write_workbook(out, results)
    print_summary(results, bbg, out)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', help='output workbook (default OI_charts_<yyyymmdd>.xlsx)')
    p.add_argument('--start-year', type=int, default=START_YEAR, help='first contract year (default %(default)s)')
    p.add_argument('--end-year', type=int, default=END_YEAR, help='last contract year (default %(default)s)')
    p.add_argument('--years-back', type=int, default=YEARS_BACK,
                   help='history per contract, back from its last trade date (default %(default)s)')
    p.add_argument('--tickers-only', action='store_true', help='resolve and print the contract table, no history')
    p.add_argument('--asof', help='treat this date (YYYY-MM-DD) as today')
    a = p.parse_args(argv)
    today = dt.date.fromisoformat(a.asof) if a.asof else None
    try:
        run(start_year=a.start_year, end_year=a.end_year, years_back_n=a.years_back,
            out=a.out, today=today, tickers_only=a.tickers_only)
        return 0
    except PermissionError as e:
        print('ERROR: cannot write the workbook - close it in Excel and rerun (%s)' % e)
        return 1
    except RuntimeError as e:
        print('ERROR: %s' % e)
        return 1


if __name__ == '__main__':
    if 'IPython' in sys.modules and len(sys.argv) <= 1:      # %run oi_charts.py
        print('oi_charts loaded.  In the next cell:\n'
              '    run()                        pull everything -> OI_charts_<date>.xlsx\n'
              '    run(tickers_only=True)       resolve the tickers and print the table only\n'
              "    run(out='C:/path/x.xlsx')    choose the output file")
    else:
        rc = main()
        if 'IPython' not in sys.modules:
            sys.exit(rc)
