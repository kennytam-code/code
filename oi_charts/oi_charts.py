#!/usr/bin/env python3
"""Daily open interest of index futures from Bloomberg -> one Excel tab + chart per product.

Everything you may want to change is in the CONFIG block right below.  The engine
underneath needs no edits.  Run the whole file at once:

    Jupyter       %run oi_charts.py      (or paste the file into a cell and run it)
                  -> pulls the data, writes the workbook, draws every chart in the notebook
    Command line  python oi_charts.py [--tickers-only] [--out FILE] [--years-back N]

Self-check, no terminal needed (a fake Bloomberg inside this file drives the real code):

    python oi_charts.py --test     self-checks: ticker forms, windows, cell-by-cell alignment, errors
    python oi_charts.py --demo     writes demo_OI_charts.xlsx from fake data (and draws it in Jupyter)

Needs: blpapi and openpyxl; matplotlib only for the notebook charts.
"""

# ================================================================ CONFIG ===
# 1. Products: (Bloomberg root, tab name).  One line per future - add a line to add a
#    product.  Tickers are built as <root><month code><year> Index (HIU6, HIU25 ...).
#    For a non-Index yellow key add it as a third item, e.g. ('CL', 'WTI', 'Comdty').
PRODUCTS = [
    ('HI',  'HSI'),
    ('HC',  'HSCEI'),
    ('HCT', 'HSTECH'),
    ('KM',  'KOSPI2'),
    ('XP',  'AS51'),
    ('FT',  'TWSE'),
    ('TWT', 'FTSE TW'),
    ('FPO', 'FPO'),
    ('HJA', 'TAMSCI'),          # the request note's "MSCI - HJAU6" row is this same root
    ('QZ',  'SIMSCI'),
]

# 2. Contract months: every month from Jan START_YEAR to Dec END_YEAR (36 for 2024-2026).
START_YEAR, END_YEAR = 2024, 2026

# 3. History per contract: from its last trade date back this many years (or as far as
#    Bloomberg has prints - a contract listed later simply has fewer rows, never NA).
YEARS_BACK = 2

# 4. Output.  The workbook is OI_charts_<yyyymmdd>.xlsx (or OUTPUT_FILE) and goes to
#    OUTPUT_FOLDER; when that folder does not exist it goes to the current folder instead.
#    The full path is printed at the end of every run.
OUTPUT_FILE = None
OUTPUT_FOLDER = '~/Downloads'
SHOW_CHARTS = True              # in Jupyter also draw every chart inline (needs matplotlib)
TICKERS_ONLY = False            # True -> only resolve and print the contract table (quick check)

# 5. Chart text.  {name} is the tab name.
CHART_TITLE = '{name} Futures Open Interest'
Y_AXIS_TITLE = 'OI'

# 6. Bloomberg.
HIST_FIELD = 'OPEN_INT'         # daily open interest of one contract
YELLOW_KEY = 'Index'            # default yellow key for the roots above
BBG_HOST, BBG_PORT = 'localhost', 8194
# ===========================================================================


# ================================================================ ENGINE ===
import argparse                                   # noqa: E402
import dataclasses                                # noqa: E402
import datetime as dt                             # noqa: E402
import os                                         # noqa: E402
import sys                                        # noqa: E402
import traceback                                  # noqa: E402
from typing import List, Optional, Tuple          # noqa: E402

try:
    from openpyxl import Workbook, load_workbook          # noqa: E402
    from openpyxl.chart import LineChart, Reference       # noqa: E402
    from openpyxl.chart.axis import DateAxis              # noqa: E402
    from openpyxl.utils import get_column_letter          # noqa: E402
except ImportError:
    print('openpyxl is not installed in this Python - run:  pip install openpyxl')
    raise

REF_FIELDS = ['LAST_TRADEABLE_DT', 'FUT_MONTH_YR', 'NAME']
EVENT_SPINS = 240                        # 500 ms each: ~2 min per request, then it is an error
REF_CHUNK = 100                          # securities per ReferenceDataRequest

MONTH_CODES = 'FGHJKMNQUVXZ'             # index 0 = January
MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

OK, NOT_FOUND, NO_DATA, NOT_PULLED = 'OK', 'NOT FOUND', 'NO DATA', 'NOT PULLED'
AUDIT_SHEET = 'Contracts'
AUDIT_COLUMNS = ['Product', 'Contract', 'Ticker 1-digit', 'Ticker 2-digit', 'Ticker used',
                 'Status', 'LAST_TRADEABLE_DT', 'FUT_MONTH_YR', 'Name', 'Request start',
                 'Request end', 'First OI date', 'Last OI date', 'Rows', 'Last OI', 'Max OI',
                 'Note']

# Line colours: one hue per contract year, light (Jan) to dark (Dec) within the year, so
# 36 lines read as three families instead of a repeating six-colour cycle.
HUES = [('c6dbef', '08306b'),            # blues
        ('fdd0a2', '7f2704'),            # oranges
        ('c7e9c0', '00441b'),            # greens
        ('dadaeb', '3f007d'),            # purples
        ('d9d9d9', '252525')]            # greys


# --------------------------------------------------------------- helpers ---
def product_rows(products):
    """[(root, tab name, yellow key)] - the optional third item defaults to YELLOW_KEY."""
    rows = []
    for p in products:
        root, name = p[0], p[1]
        key = p[2] if len(p) > 2 and p[2] else YELLOW_KEY
        rows.append((root, name, key))
    return rows


def contract_months(start_year, end_year):
    """[(year, month)] for every month from Jan start_year to Dec end_year."""
    return [(y, m) for y in range(start_year, end_year + 1) for m in range(1, 13)]


def month_label(year, month):
    """(2024, 1) -> 'Jan 24'."""
    return '%s %02d' % (MONTH_ABBR[month - 1], year % 100)


def candidate_tickers(root, year, month, key=YELLOW_KEY):
    """('HI', 2026, 1) -> ('HIF6 Index', 'HIF26 Index'): the one- and two-digit forms."""
    code = MONTH_CODES[month - 1]
    return ('%s%s%d %s' % (root, code, year % 10, key),
            '%s%s%02d %s' % (root, code, year % 100, key))


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


def row_date(pt):
    """The date of one history row: 'YYYY-MM-DD' text first, the datetime form as fallback."""
    d = as_date(pt.getElementAsString('date'))
    if d is None:
        try:
            d = as_date(pt.getElementAsDatetime('date'))
        except Exception:
            d = None
    return d


def series_color(year, month, base_year):
    """Hex colour (no '#') for one contract line: hue by year, shade by month."""
    light, dark = HUES[(year - base_year) % len(HUES)]
    t = 0.2 + 0.8 * (month - 1) / 11.0
    rgb = [round(int(light[i:i + 2], 16) * (1 - t) + int(dark[i:i + 2], 16) * t) for i in (0, 2, 4)]
    return '%02x%02x%02x' % tuple(rgb)


def in_ipython():
    """True inside Jupyter / IPython (where the file should just run)."""
    try:
        import builtins
        return builtins.get_ipython() is not None
    except Exception:
        return False


def output_path(out=None, today=None):
    """Where the workbook goes: a bare file name lands in OUTPUT_FOLDER (or the current folder)."""
    name = out or OUTPUT_FILE or 'OI_charts_%s.xlsx' % (today or dt.date.today()).strftime('%Y%m%d')
    name = os.path.expanduser(name)
    if os.path.dirname(name):
        return os.path.abspath(name)
    folder = os.path.expanduser(OUTPUT_FOLDER or '.')
    if not os.path.isdir(folder):
        folder = os.getcwd()
    return os.path.join(os.path.abspath(folder), name)


class StepError(RuntimeError):
    """A failure tagged with the step it happened in; an unexpected cause keeps its traceback."""

    def __init__(self, stage, cause, extra=''):
        self.stage, self.cause, self.extra = stage, cause, extra
        RuntimeError.__init__(self, 'while %s: %s%s' % (stage, cause, extra))


def report_error(e):
    """One clear message per problem; the full traceback only when the cause is not one of ours."""
    if isinstance(e, StepError):
        print('ERROR while %s:\n    %s%s' % (e.stage, e.cause, e.extra))
        cause = e.cause
    else:
        print('ERROR: %s' % e)
        cause = e
    if isinstance(cause, PermissionError):
        print('    (the workbook is probably open in Excel - close it and rerun)')
    elif not isinstance(cause, RuntimeError):
        print('Full detail for debugging:')
        traceback.print_exception(type(cause), cause, cause.__traceback__, file=sys.stdout)


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


# ------------------------------------------------------------- bloomberg ---
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
        self.field_error_secs = {}           # mnemonic -> set of securities it was refused for
        self.bad_securities = {}             # security -> message
        self.n_ref_securities = 0            # securities sent through ref(), for the summary

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

    def _note_field_exceptions(self, sd, sec=''):
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
            self.field_error_secs.setdefault(fid, set()).add(sec)

    def ref(self, securities, fields):
        """ReferenceDataRequest -> {security: {field: value}}; unknown securities are skipped."""
        out = {}
        svc = self.service('//blp/refdata')
        securities = list(securities)
        self.n_ref_securities += len(securities)

        def take(msg):
            self._check_response_error(msg)
            if not msg.hasElement('securityData'):
                return
            for sd in self._items(msg.getElement('securityData')):
                sec = sd.getElementAsString('security')
                if sd.hasElement('securityError'):
                    self.bad_securities[sec] = self._error_text(sd.getElement('securityError'))
                    continue
                self._note_field_exceptions(sd, sec)
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
                self._note_field_exceptions(sd, sec)
                if not sd.hasElement('fieldData'):
                    continue
                fd = sd.getElement('fieldData')
                for j in range(fd.numValues()):
                    pt = fd.getValueAsElement(j)
                    if not pt.hasElement('date') or not pt.hasElement(field):
                        continue
                    if pt.getElement(field).isNull():
                        continue
                    d = row_date(pt)
                    if d is not None:
                        rows.append((d, float(pt.getElementAsFloat(field))))

        self._drain(rq, take)
        rows.sort()
        return rows


# -------------------------------------------------------------- pipeline ---
def build_contracts(products, months):
    """[(tab name, [Contract, ...])] in PRODUCTS order, contracts in expiry order."""
    out = []
    for root, name, key in product_rows(products):
        cs = []
        for y, m in months:
            t1, t2 = candidate_tickers(root, y, m, key)
            cs.append(Contract(product=name, root=root, year=y, month=m,
                               label=month_label(y, m), ticker_1=t1, ticker_2=t2))
        out.append((name, cs))
    return out


def pick_ticker(c, ref, bad_securities, today):
    """Choose the form whose LAST_TRADEABLE_DT is in the contract month; mark NOT FOUND otherwise.

    The note says, per ticker form, what Bloomberg answered - that is the 'why' of a NOT FOUND.
    """
    valid, why = [], []
    for t in (c.ticker_1, c.ticker_2):
        if t in bad_securities:
            why.append('%s -> %s' % (t, bad_securities[t]))
            continue
        row = ref.get(t)
        if row is None:
            why.append('%s -> no answer from Bloomberg' % t)
            continue
        ltd = as_date(row.get('LAST_TRADEABLE_DT'))
        if ltd is None:
            why.append('%s -> not a futures contract (no LAST_TRADEABLE_DT%s)'
                       % (t, '; name: %s' % row['NAME'] if row.get('NAME') else ''))
            continue
        if (ltd.year, ltd.month) == (c.year, c.month):
            valid.append((t, ltd, row))
        else:
            why.append('%s -> last trade %s, outside the month' % (t, ltd.isoformat()))
    if not valid:
        c.status, c.note = NOT_FOUND, '; '.join(why)
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
        c.note = bbg.bad_securities.get(c.ticker) or (
            'contract exists, but no %s prints between %s and %s'
            % (HIST_FIELD, c.req_start.isoformat(), c.req_end.isoformat()))


def align_product(contracts):
    """(sorted union of dates, contracts that have data) - the shape of one product tab."""
    found = [c for c in contracts if c.status == OK and c.rows]
    dates = sorted({d for c in found for d, _ in c.rows})
    return dates, found


# -------------------------------------------------------------- workbook ---
def safe_sheet_name(name):
    for ch in '[]:*?/\\':
        name = name.replace(ch, ' ')
    return name.strip()[:31]


def add_oi_chart(ws, name, found, n_rows, base_year):
    """One line per contract; blanks are gaps, so each line spans only its own data."""
    n_series = len(found)
    ch = LineChart()
    ch.title = CHART_TITLE.format(name=name)
    ch.y_axis.title = Y_AXIS_TITLE
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
    for s, c in zip(ch.series, found):
        s.marker.symbol = 'none'
        s.smooth = False
        s.graphicalProperties.line.width = 12700   # EMU: 1 pt
        s.graphicalProperties.line.solidFill = series_color(c.year, c.month, base_year)
    ws.add_chart(ch, '%s2' % get_column_letter(n_series + 3))


def write_product_sheet(wb, name, contracts, base_year):
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
    add_oi_chart(ws, name, found, len(dates), base_year)
    return ws


def audit_row(c):
    return [c.product, c.label, c.ticker_1, c.ticker_2, c.ticker or None, c.status,
            c.last_trade, c.fut_month_yr or None, c.name or None, c.req_start, c.req_end,
            c.first_dt, c.last_dt, (len(c.rows) if c.status in (OK, NO_DATA) else None),
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


def write_workbook(path, results, base_year=None):
    if base_year is None:
        base_year = min([c.year for _, cs in results for c in cs] or [START_YEAR])
    wb = Workbook()
    wb.remove(wb.active)
    for name, cs in results:
        write_product_sheet(wb, name, cs, base_year)
    write_contracts_sheet(wb, results)
    wb.save(path)
    return path


# ------------------------------------------------------- notebook charts ---
def show_charts(results, base_year=None):
    """Draw every product chart with matplotlib (inline in Jupyter). Returns the figure count."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.ticker import FuncFormatter
    except ImportError:
        print('matplotlib is not installed, so no charts here - they are in the workbook '
              '(pip install matplotlib)')
        return 0
    if base_year is None:
        base_year = min([c.year for _, cs in results for c in cs] or [START_YEAR])
    n_fig = 0
    for name, cs in results:
        dates, found = align_product(cs)
        if not found:
            continue
        fig, ax = plt.subplots(figsize=(13, 6.5))
        for c in found:
            ax.plot([d for d, _ in c.rows], [v for _, v in c.rows], linewidth=1.2,
                    color='#' + series_color(c.year, c.month, base_year), label=c.label)
        ax.set_title(CHART_TITLE.format(name=name), fontweight='bold')
        ax.set_ylabel(Y_AXIS_TITLE)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b-%y'))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos: format(int(v), ',')))
        ax.grid(True, axis='y', alpha=0.3)
        for side in ('top', 'right'):
            ax.spines[side].set_visible(False)
        fig.autofmt_xdate()
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=12, fontsize=7,
                  frameon=False, handlelength=1.6)
        fig.tight_layout()
        plt.show()
        n_fig += 1
    return n_fig


# --------------------------------------------------------------- console ---
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
        for status in (NOT_FOUND, NO_DATA, NOT_PULLED):
            labels = [c.label for c in cs if c.status == status]
            if labels:
                print('         %-11s %s' % (status + ':', ', '.join(labels)))
    for fid, text in sorted(bbg.field_errors.items()):
        secs = sorted(bbg.field_error_secs.get(fid, ()))
        if 'NOT_APPLICABLE' in text and secs and len(secs) < bbg.n_ref_securities:
            print('%s not applicable to %d of %d candidate tickers - those are not futures contracts '
                  'and count as NOT FOUND (e.g. %s; the %s tab names each one)'
                  % (fid, len(secs), bbg.n_ref_securities, secs[0], AUDIT_SHEET))
        else:
            print('Bloomberg refused the field %s for %d securities: %s' % (fid, len(secs), text))
    seen_status = {c.status for _, cs in results for c in cs}
    if NOT_FOUND in seen_status:
        print('NOT FOUND = neither ticker form is a futures contract with its last trade in that month '
              '(the Note column of the %s tab says what each form was)' % AUDIT_SHEET)
    if NO_DATA in seen_status:
        print('NO DATA   = the contract exists on Bloomberg but has no %s prints in its window '
              '(not traded yet, or never)' % HIST_FIELD)
    if out:
        print('Written: %s' % out)


# ------------------------------------------------------------------- run ---
def run(products=None, start_year=None, end_year=None, years_back_n=None, out=None,
        today=None, blpapi_module=None, tickers_only=None, show_charts_=None,
        host=BBG_HOST, port=BBG_PORT):
    """Resolve every contract, pull its open interest, write the workbook; returns the path.

    Every argument defaults to the CONFIG value at the top of the file.
    """
    products = list(PRODUCTS if products is None else products)
    start_year = START_YEAR if start_year is None else start_year
    end_year = END_YEAR if end_year is None else end_year
    years_back_n = YEARS_BACK if years_back_n is None else years_back_n
    tickers_only = TICKERS_ONLY if tickers_only is None else tickers_only
    if show_charts_ is None:
        show_charts_ = SHOW_CHARTS and in_ipython()
    today = today or dt.date.today()
    months = contract_months(start_year, end_year)
    out = output_path(out, today)
    print('OI charts | %d products | contracts %s .. %s | %d years back per contract | today %s'
          % (len(products), month_label(*months[0]), month_label(*months[-1]), years_back_n,
             today.isoformat()))
    try:
        bbg = Bloomberg(host, port, blpapi_module=blpapi_module).connect()
    except Exception as e:
        raise StepError('connecting to Bloomberg', e)
    pull_error = None
    try:
        print('Resolving %d contracts for %d products (%d candidate tickers) ...'
              % (len(months) * len(products), len(products), 2 * len(months) * len(products)))
        try:
            results = resolve_contracts(bbg, products, months, today)
        except Exception as e:
            raise StepError('resolving the tickers', e)
        if tickers_only:
            print_contract_table(results)
            print_summary(results, bbg, None)
            return ''
        for name, cs in results:
            n_ok = sum(1 for c in cs if c.status == OK)
            if pull_error is not None:
                print('%-8s skipped - the pull stopped earlier' % name)
            else:
                print('%-8s pulling %s for %d/%d contracts ' % (name, HIST_FIELD, n_ok, len(cs)),
                      end='', flush=True)
            for c in cs:
                if c.status != OK:
                    continue
                if pull_error is not None:
                    c.status, c.note = NOT_PULLED, 'not requested - the pull stopped at %s' % pull_error[0].ticker
                    continue
                try:
                    fetch_open_interest(bbg, c, years_back_n, today)
                    print('.', end='', flush=True)
                except Exception as e:                 # keep what we have, say where it stopped
                    pull_error = (c, e)
                    c.status, c.note = NOT_PULLED, 'the pull failed here: %s' % e
                    print(' x', flush=True)
            if pull_error is None:
                print()
    finally:
        bbg.close()
    try:
        write_workbook(out, results, base_year=start_year)
    except Exception as e:
        raise StepError('writing the workbook %s' % out, e)
    print_summary(results, bbg, out)
    if show_charts_:
        try:
            show_charts(results, base_year=start_year)
        except Exception as e:
            raise StepError('drawing the charts (the workbook is already written: %s)' % out, e)
    if pull_error is not None:
        c, e = pull_error
        n_done = sum(1 for _, cs in results for x in cs if x.status in (OK, NO_DATA))
        n_all = n_done + sum(1 for _, cs in results for x in cs if x.status == NOT_PULLED)
        raise StepError('pulling %s for %s (%s %s)' % (HIST_FIELD, c.ticker, c.product, c.label), e,
                        '\n    The workbook was still written with the %d of %d resolved contracts '
                        'pulled before that; the rest are marked %s in the %s tab:\n    %s'
                        % (n_done, n_all, NOT_PULLED, AUDIT_SHEET, out))
    return out


def notebook_main(**kw):
    """What %run / a pasted cell does: run everything; a problem is a clear message, not a traceback."""
    try:
        return run(**kw)
    except Exception as e:
        report_error(e)
        return None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', default=OUTPUT_FILE,
                   help='output workbook; a bare name goes to OUTPUT_FOLDER (default OI_charts_<yyyymmdd>.xlsx)')
    p.add_argument('--start-year', type=int, default=START_YEAR, help='first contract year (default %(default)s)')
    p.add_argument('--end-year', type=int, default=END_YEAR, help='last contract year (default %(default)s)')
    p.add_argument('--years-back', type=int, default=YEARS_BACK,
                   help='history per contract, back from its last trade date (default %(default)s)')
    p.add_argument('--tickers-only', action='store_true', default=TICKERS_ONLY,
                   help='resolve and print the contract table, no history')
    p.add_argument('--asof', help='treat this date (YYYY-MM-DD) as today')
    p.add_argument('--test', action='store_true', help='run the self-checks against the built-in fake terminal')
    p.add_argument('--demo', nargs='?', const='demo_OI_charts.xlsx', metavar='FILE',
                   help='write a workbook from fake data (default demo_OI_charts.xlsx)')
    a = p.parse_args(argv)
    if a.test:
        return run_tests()
    if a.demo:
        demo(a.demo)
        return 0
    today = dt.date.fromisoformat(a.asof) if a.asof else None
    try:
        run(start_year=a.start_year, end_year=a.end_year, years_back_n=a.years_back,
            out=a.out, today=today, tickers_only=a.tickers_only, show_charts_=False)
        return 0
    except Exception as e:
        report_error(e)
        return 1


# =============================================================== FIXTURE ===
# A fake Bloomberg terminal, so --test and --demo run on any machine.  It speaks enough
# of the API to exercise the real code path above: batched ReferenceDataRequests split
# across PARTIAL_RESPONSE / RESPONSE events, HistoricalDataRequests with the
# single-element securityData shape, securityError for unknown tickers, rejected
# mnemonics, a silent terminal, a rejected request - and a universe with one-digit
# tickers for live contracts, two-digit for expired ones, a wrong-decade one-digit
# ticker, a quarterly-only product and a contract that resolves but has no prints yet.
import importlib.util                             # noqa: E402
import io                                         # noqa: E402
import tempfile                                   # noqa: E402
import zipfile                                    # noqa: E402
from contextlib import redirect_stdout            # noqa: E402

TEST_TODAY = dt.date(2026, 9, 17)
FAKE_PRODUCTS = [('HI', 'HSI'), ('XP', 'AS51'), ('QZ', 'SIMSCI')]
QUARTERLY = (3, 6, 9, 12)
HOLIDAYS = {(1, 1), (4, 4), (12, 25)}
DAY = dt.timedelta(days=1)


# ========================================================== FAKE BLPAPI ===
class FakeEvent:
    TIMEOUT, RESPONSE, PARTIAL_RESPONSE, REQUEST_STATUS = 0, 1, 2, 3

    def __init__(self, messages, event_type=1):
        self._messages, self._type = messages, event_type

    def __iter__(self):
        return iter(self._messages)

    def eventType(self):
        return self._type


class FakeName(str):
    pass


class FakeElement:
    """Scalar, array-of-scalars, or complex (named children), like the real thing."""

    def __init__(self, name, value=None, children=None, array=None):
        self._name, self._value = name, value
        self._children = children                 # list[(name, FakeElement)] when complex
        self._array = array                       # list[FakeElement] when an array

    def name(self):
        return FakeName(self._name)

    def isArray(self):
        return self._array is not None

    def isComplexType(self):
        if self._array is not None:
            return bool(self._array) and self._array[0]._children is not None
        return self._children is not None

    def isNull(self):
        return self._value is None and self._children is None and self._array is None

    def numValues(self):
        return len(self._array or [])

    def numElements(self):
        return len(self._children or [])

    def getValueAsElement(self, i):
        return self._array[i]

    def getElement(self, key):
        if isinstance(key, int):
            return self._children[key][1]
        for n, el in (self._children or []):
            if n == key:
                return el
        raise KeyError(key)

    def hasElement(self, key):
        return any(n == key for n, _ in (self._children or []))

    def getValue(self, i=None):
        return self._array[i]._value if i is not None else self._value

    def getValueAsString(self):
        return '' if self._value is None else str(self._value)

    def getElementAsString(self, key):
        v = self.getElement(key)._value
        return '' if v is None else str(v)

    def getElementAsFloat(self, key):
        return float(self.getElement(key)._value)

    def getElementAsDatetime(self, key):
        return self.getElement(key)._value

    def appendValue(self, v):
        self._array.append(FakeElement('item', v))

    def set(self, key, value):
        self._children = [(n, e) for n, e in (self._children or []) if n != key]
        self._children.append((key, FakeElement(key, value)))


def fake_complex(name, pairs):
    return FakeElement(name, children=[(n, e if isinstance(e, FakeElement) else FakeElement(n, e))
                                       for n, e in pairs])


def fake_array(name, items):
    return FakeElement(name, array=list(items))


class FakeMessage:
    def __init__(self, root):
        self._root = root

    def hasElement(self, key):
        return self._root.hasElement(key)

    def getElement(self, key):
        return self._root.getElement(key)

    def toString(self):
        def dump(el):
            if el._children is not None:
                return '%s = { %s }' % (el._name, ' '.join(dump(e) for _, e in el._children))
            if el._array is not None:
                return '%s[] = { %s }' % (el._name, ' '.join(dump(e) for e in el._array))
            return '%s = %s' % (el._name, el._value)
        return dump(self._root)


class FakeRequest:
    def __init__(self, operation):
        self.operation = operation
        self.settings = {}
        self._root = FakeElement('request', children=[
            ('securities', fake_array('securities', [])),
            ('fields', fake_array('fields', [])),
        ])

    def getElement(self, key):
        return self._root.getElement(key)

    def set(self, key, value):
        self.settings[key] = value
        self._root.set(key, value)

    @property
    def securities(self):
        return [e._value for e in self._root.getElement('securities')._array]

    @property
    def fields(self):
        return [e._value for e in self._root.getElement('fields')._array]


class FakeService:
    def __init__(self, name):
        self._name = name

    def createRequest(self, operation):
        return FakeRequest(operation)


class FakeSessionOptions:
    def setServerHost(self, *a):
        pass

    def setServerPort(self, *a):
        pass


# ------------------------------------------------------------ fake market ---
def weekday_on_or_before(d):
    while d.weekday() >= 5:
        d -= DAY
    return d


def last_trade(y, m):
    """Second-last weekday on or before the 28th: always inside the month."""
    return weekday_on_or_before(weekday_on_or_before(dt.date(y, m, 28)) - DAY)


def listing(y, m):
    days = 1100 if m == 12 else (400 if m in QUARTERLY else 90)   # Dec listed 3y out, serials 3m
    return last_trade(y, m) - dt.timedelta(days=days)


def spec(y, m, **over):
    s = dict(year=y, month=m, last_trade=last_trade(y, m), listing=listing(y, m))
    s.update(over)
    return s


def build_universe():
    """ticker -> contract spec.  Which forms exist follows the real Bloomberg behaviour."""
    u = {}
    for root, _ in FAKE_PRODUCTS:
        for y, m in contract_months(2024, 2026):
            if root == 'XP' and m not in QUARTERLY:
                continue                                            # (v)  quarterly-only product
            t1, t2 = candidate_tickers(root, y, m)
            s = spec(y, m)
            expired = s['last_trade'] < TEST_TODAY
            if root == 'HI' and (y, m) == (2026, 1):                # (iv) one-digit form is the 2036 contract
                u[t1], u[t2] = spec(2036, 1), s
            elif root == 'QZ' and (y, m) == (2026, 2):              # (iv) only a wrong-decade form exists
                u[t1] = spec(2036, 2)
            elif root == 'QZ' and (y, m) == (2026, 10):             # (vi) resolves, not listed yet
                u[t1] = spec(y, m, listing=dt.date(2026, 10, 1))
            elif root == 'HI' and (y, m) in ((2026, 8), (2026, 12)):   # (iii) both forms valid
                u[t1], u[t2] = s, s
            else:                                                   # (i) expired 2-digit / (ii) live 1-digit
                u[t2 if expired else t1] = s
    return u


UNIVERSE = build_universe()
# a fourth root, used only by test_not_a_future(): NFH4 exists but is not a future (NFH24 is);
# NFJ4 is not a future and NFJ24 is unknown -> Apr 24 has no futures contract at all
UNIVERSE['NFH4 Index'] = spec(2024, 3, not_future=True)
UNIVERSE['NFH24 Index'] = spec(2024, 3)
UNIVERSE['NFJ4 Index'] = spec(2024, 4, not_future=True)
TICKER_ID = {t: i for i, t in enumerate(sorted(UNIVERSE))}


def fake_oi(ticker, d):
    """Deterministic, distinct per ticker, rising with time - a misaligned cell cannot match."""
    s = UNIVERSE[ticker]
    return float(TICKER_ID[ticker] * 100000 + (d - s['listing']).days * 3 + 100)


def is_session(d):
    return d.weekday() < 5 and (d.month, d.day) not in HOLIDAYS


def first_session_on_or_after(d):
    while not is_session(d):
        d += DAY
    return d


def last_session_on_or_before(d):
    while not is_session(d):
        d -= DAY
    return d


def fake_rows(ticker, start, end):
    s = UNIVERSE.get(ticker)
    if s is None:
        return []
    d, hi, out = max(s['listing'], start), min(s['last_trade'], end), []
    while d <= hi:
        if is_session(d):
            out.append((d, fake_oi(ticker, d)))
        d += DAY
    return out


def security_error(sec):
    return fake_complex('securityData', [
        ('security', sec),
        ('securityError', fake_complex('securityError', [
            ('category', 'BAD_SEC'), ('message', 'Unknown/Invalid Security [nid:1234]')])),
    ])


class FakeSession:
    instances = []

    def __init__(self, options=None):
        self._queue, self.log, self.stopped = [], [], False
        FakeSession.instances.append(self)

    def start(self):
        return True

    def stop(self):
        self.stopped = True

    def openService(self, name):
        return name == '//blp/refdata'

    def getService(self, name):
        return FakeService(name)

    def sendRequest(self, request):
        self.log.append(dict(op=request.operation, securities=list(request.securities),
                             fields=list(request.fields), settings=dict(request.settings)))
        if request.operation == 'ReferenceDataRequest':
            self._queue = self._ref_events(request)
        elif request.operation == 'HistoricalDataRequest':
            self._queue = self._hist_events(request)
        else:
            raise ValueError(request.operation)

    def nextEvent(self, timeout=0):
        return self._queue.pop(0) if self._queue else FakeEvent([], FakeEvent.TIMEOUT)

    @staticmethod
    def _ref_item(sec, wanted):
        s = UNIVERSE.get(sec)
        if s is None:
            return security_error(sec)
        mon = MONTH_ABBR[s['month'] - 1]
        if s.get('not_future'):                     # a ticker that exists but is not a future
            known = {'NAME': 'FAKE %s SOMETHING ELSE' % sec.split()[0]}
            refusal = ('NOT_APPLICABLE_TO_REF_DATA', 'Field not applicable to security')
        else:
            known = {'LAST_TRADEABLE_DT': s['last_trade'],
                     'FUT_MONTH_YR': '%s %02d' % (mon.upper(), s['year'] % 100),
                     'NAME': 'FAKE %s FUT %s%02d' % (sec.split()[0], mon, s['year'] % 100)}
            refusal = ('BAD_FLD', 'Invalid Field')
        kids = [('security', sec),
                ('fieldData', fake_complex('fieldData', [(k, known[k]) for k in wanted if k in known]))]
        bad = [f for f in wanted if f not in known]
        if bad:
            kids.append(('fieldExceptions', fake_array('fieldExceptions', [
                fake_complex('fieldExceptions', [
                    ('fieldId', f),
                    ('errorInfo', fake_complex('errorInfo', [
                        ('subcategory', refusal[0]), ('message', refusal[1])])),
                ]) for f in bad])))
        return fake_complex('securityData', kids)

    def _ref_events(self, request):
        items = [self._ref_item(s, request.fields) for s in request.securities]
        half = len(items) // 2
        events = [FakeEvent([], FakeEvent.TIMEOUT)]
        for part, kind in ((items[:half], FakeEvent.PARTIAL_RESPONSE), (items[half:], FakeEvent.RESPONSE)):
            root = FakeElement('ReferenceDataResponse',
                               children=[('securityData', fake_array('securityData', part))])
            events.append(FakeEvent([FakeMessage(root)], kind))
        return events

    @staticmethod
    def _hist_event(sd, kind):
        root = FakeElement('HistoricalDataResponse', children=[('securityData', sd)])   # scalar
        return FakeEvent([FakeMessage(root)], kind)

    def _hist_events(self, request):
        start = dt.datetime.strptime(request.settings['startDate'], '%Y%m%d').date()
        end = dt.datetime.strptime(request.settings['endDate'], '%Y%m%d').date()
        field = request.fields[0]
        events = [FakeEvent([], FakeEvent.TIMEOUT)]
        secs = request.securities
        for k, sec in enumerate(secs):
            last_sec = (k == len(secs) - 1)
            if sec not in UNIVERSE:
                events.append(self._hist_event(
                    security_error(sec), FakeEvent.RESPONSE if last_sec else FakeEvent.PARTIAL_RESPONSE))
                continue
            rows = fake_rows(sec, start, end)
            half = len(rows) // 2
            for pi, part in enumerate((rows[:half], rows[half:])):     # one history, two messages
                fd = fake_array('fieldData', [fake_complex('fieldData', [('date', d), (field, v)])
                                              for d, v in part])
                sd = fake_complex('securityData', [('security', sec), ('fieldData', fd)])
                kind = FakeEvent.RESPONSE if (last_sec and pi == 1) else FakeEvent.PARTIAL_RESPONSE
                events.append(self._hist_event(sd, kind))
        return events


class FakeAPI:
    """Stands in for the blpapi module itself."""
    SessionOptions = FakeSessionOptions
    Session = FakeSession
    Event = FakeEvent


class SilentSession(FakeSession):
    def sendRequest(self, request):
        self._queue = []


class RejectingSession(FakeSession):
    def sendRequest(self, request):
        root = FakeElement('RequestFailure', children=[
            ('reason', fake_complex('reason', [('description', 'Daily capacity reached')]))])
        self._queue = [FakeEvent([FakeMessage(root)], FakeEvent.REQUEST_STATUS)]


class ResponseErrorSession(FakeSession):
    def sendRequest(self, request):
        root = FakeElement('ReferenceDataResponse', children=[
            ('responseError', fake_complex('responseError', [('message', 'Not logged in')]))])
        self._queue = [FakeEvent([FakeMessage(root)], FakeEvent.RESPONSE)]


def api_with(session_cls):
    return type('API', (), dict(SessionOptions=FakeSessionOptions, Session=session_cls, Event=FakeEvent))


# ================================================================= TESTS ===
# python oi_charts.py --test   (no terminal, no network)
FAILS, COUNT = [], [0]


def check(name, cond, detail=''):
    COUNT[0] += 1
    if cond:
        print('PASS  ' + name)
    else:
        print('FAIL  ' + name + ('  -- %s' % (detail,) if detail != '' else ''))
        FAILS.append(name)


def quiet(fn, *a, **k):
    buf = io.StringIO()
    with redirect_stdout(buf):
        out = fn(*a, **k)
    return out, buf.getvalue()


def test_helpers():
    months = contract_months(2024, 2026)
    check('36 contract months, Jan 24 first, Dec 26 last',
          len(months) == 36 and months[0] == (2024, 1) and months[-1] == (2026, 12))
    check('candidate forms HI Sep 24', candidate_tickers('HI', 2024, 9) == ('HIU4 Index', 'HIU24 Index'))
    check('candidate forms HCT Jan 26', candidate_tickers('HCT', 2026, 1) == ('HCTF6 Index', 'HCTF26 Index'))
    check('candidate forms TWT Dec 25', candidate_tickers('TWT', 2025, 12) == ('TWTZ5 Index', 'TWTZ25 Index'))
    check('labels', month_label(2024, 1) == 'Jan 24' and month_label(2026, 12) == 'Dec 26')
    check('years_back clips 29 Feb', years_back(dt.date(2024, 2, 29), 2) == dt.date(2022, 2, 28))
    check('years_back plain', years_back(dt.date(2026, 9, 28), 2) == dt.date(2024, 9, 28))
    check('as_date datetime', as_date(dt.datetime(2026, 1, 28, 0, 0)) == dt.date(2026, 1, 28))
    check('as_date date', as_date(dt.date(2026, 1, 28)) == dt.date(2026, 1, 28))
    check('as_date text', as_date('2026-01-28T00:00:00') == dt.date(2026, 1, 28))
    check('as_date None / garbage', as_date(None) is None and as_date('n.a.') is None)
    text_row = fake_complex('fieldData', [('date', '2026-01-28'), ('OPEN_INT', 1.0)])
    dt_row = FakeElement('fieldData', children=[('date', FakeElement('date', dt.date(2026, 1, 28)))])
    dt_row.getElementAsString = lambda key: 'garbage'          # text form unusable -> datetime fallback
    check('row_date: text form first, datetime form as fallback',
          row_date(text_row) == dt.date(2026, 1, 28) and row_date(dt_row) == dt.date(2026, 1, 28))
    check('10 real products, distinct legal tab names',
          len({n for _, n in PRODUCTS}) == len(PRODUCTS) == 10
          and all(safe_sheet_name(n) == n for _, n in PRODUCTS))
    check('real roots match the request note',
          [p[0] for p in PRODUCTS] == ['HI', 'HC', 'HCT', 'KM', 'XP', 'FT', 'TWT', 'FPO', 'HJA', 'QZ'])
    check('optional yellow key: third item in PRODUCTS',
          candidate_tickers('CL', 2026, 1, 'Comdty') == ('CLF6 Comdty', 'CLF26 Comdty')
          and product_rows([('HI', 'HSI'), ('CL', 'WTI', 'Comdty')]) == [('HI', 'HSI', 'Index'), ('CL', 'WTI', 'Comdty')]
          and build_contracts([('CL', 'WTI', 'Comdty')], [(2026, 1)])[0][1][0].ticker_2 == 'CLF26 Comdty')
    jan, jun, dec = (series_color(2024, m, 2024) for m in (1, 6, 12))
    lum = lambda h: sum(int(h[i:i + 2], 16) for i in (0, 2, 4))
    check('series colours: 6-hex, Jan lighter than Jun lighter than Dec, year changes the hue, 5-year cycle',
          all(len(h) == 6 and int(h, 16) >= 0 for h in (jan, jun, dec)) and lum(jan) > lum(jun) > lum(dec)
          and series_color(2025, 12, 2024) != dec and series_color(2029, 1, 2024) == jan)
    import builtins
    plain = in_ipython()
    builtins.get_ipython = lambda: object()
    try:
        faked = in_ipython()
    finally:
        del builtins.get_ipython
    check('in_ipython: False under plain python, True when IPython injects get_ipython', plain is False and faked is True)


def test_resolution():
    bbg = Bloomberg(blpapi_module=FakeAPI).connect()
    months = contract_months(2024, 2026)
    results = resolve_contracts(bbg, FAKE_PRODUCTS, months, TEST_TODAY)
    by = {(n, c.label): c for n, cs in results for c in cs}
    refs = [e for e in bbg.session.log if e['op'] == 'ReferenceDataRequest']
    cands = [t for _, cs in results for c in cs for t in (c.ticker_1, c.ticker_2)]
    requested = [s for e in refs for s in e['securities']]
    check('one reference pass, chunked at REF_CHUNK',
          len(refs) == -(-len(cands) // REF_CHUNK) and all(len(e['securities']) <= REF_CHUNK for e in refs),
          len(refs))
    check('every candidate requested exactly once', sorted(requested) == sorted(cands))
    check('reference fields as configured', all(e['fields'] == REF_FIELDS for e in refs))
    c = by[('HSI', 'Sep 25')]
    check('(i)   expired -> two-digit form', c.ticker == 'HIU25 Index' and c.status == OK, c)
    check('(ii)  live -> one-digit form',
          by[('HSI', 'Oct 26')].ticker == 'HIV6 Index' and by[('HSI', 'Sep 26')].ticker == 'HIU6 Index')
    c = by[('HSI', 'Aug 26')]
    check('(iii) both forms valid, expired -> two-digit', c.ticker == 'HIQ26 Index' and c.note == 'both forms valid', c)
    check('(iii) both forms valid, live -> one-digit', by[('HSI', 'Dec 26')].ticker == 'HIZ6 Index')
    c = by[('HSI', 'Jan 26')]
    check('(iv)  wrong-decade one-digit rejected, two-digit used',
          c.ticker == 'HIF26 Index' and c.status == OK and c.last_trade.year == 2026, c)
    c = by[('SIMSCI', 'Feb 26')]
    check('(iv)  only a wrong-decade form -> NOT FOUND, note shows the date seen',
          c.status == NOT_FOUND and c.ticker == '' and c.last_trade is None and '2036' in c.note, c.note)
    as51 = results[1][1]
    nf = [c for c in as51 if c.status == NOT_FOUND]
    check('(v)   quarterly-only product: 24 NOT FOUND, 12 OK',
          len(nf) == 24 and sum(c.status == OK for c in as51) == 12, [c.label for c in nf])
    check('(v)   the NOT FOUND months are exactly the serial months', all(c.month not in QUARTERLY for c in nf))
    note = by[('AS51', 'Jan 24')].note
    check('(v)   NOT FOUND note says what each form was',
          note.startswith('XPF4 Index -> Unknown/Invalid') and '; XPF24 Index -> Unknown/Invalid' in note, note)
    note = by[('SIMSCI', 'Feb 26')].note
    check('(iv)  wrong-decade note names the date seen and the unknown form',
          'QZG6 Index -> last trade 2036-02' in note and 'outside the month' in note
          and 'QZG26 Index -> Unknown/Invalid' in note, note)
    check('(vii) unknown tickers collected, not raised',
          'HIU5 Index' in bbg.bad_securities and 'HIU25 Index' not in bbg.bad_securities)
    check('no field errors on the reference pass', not bbg.field_errors, bbg.field_errors)
    ok = [c for _, cs in results for c in cs if c.status == OK]
    check('LAST_TRADEABLE_DT kept as a date, inside the contract month',
          all(isinstance(c.last_trade, dt.date) and (c.last_trade.year, c.last_trade.month) == (c.year, c.month)
              for c in ok))
    c = by[('HSI', 'Sep 25')]
    check('FUT_MONTH_YR / NAME captured', c.fut_month_yr == 'SEP 25' and c.name.startswith('FAKE HIU25'), (c.fut_month_yr, c.name))
    counts = [(n, sum(c.status == OK for c in cs)) for n, cs in results]
    check('resolution counts HSI 36 / AS51 12 / SIMSCI 35', counts == [('HSI', 36), ('AS51', 12), ('SIMSCI', 35)], counts)
    return bbg, results


def test_history(bbg, results):
    for _, cs in results:
        for c in cs:
            fetch_open_interest(bbg, c, 2, TEST_TODAY)
    by = {(n, c.label): c for n, cs in results for c in cs}
    hist = [e for e in bbg.session.log if e['op'] == 'HistoricalDataRequest']
    resolved = [c for _, cs in results for c in cs if c.status in (OK, NO_DATA)]
    check('one historical request per resolved contract (83)', len(hist) == len(resolved) == 83, (len(hist), len(resolved)))
    check('each request: one security, OPEN_INT only',
          all(len(e['securities']) == 1 and e['fields'] == ['OPEN_INT'] for e in hist))
    check('settings: DAILY / ACTUAL / ACTIVE_DAYS_ONLY',
          all(e['settings'].get('periodicitySelection') == 'DAILY'
              and e['settings'].get('periodicityAdjustment') == 'ACTUAL'
              and e['settings'].get('nonTradingDayFillOption') == 'ACTIVE_DAYS_ONLY' for e in hist))
    by_ticker = {c.ticker: c for c in resolved}
    bad = []
    for e in hist:
        c = by_ticker[e['securities'][0]]
        exp = (years_back(c.last_trade, 2).strftime('%Y%m%d'), min(c.last_trade, TEST_TODAY).strftime('%Y%m%d'))
        got = (e['settings']['startDate'], e['settings']['endDate'])
        if got != exp:
            bad.append((c.ticker, got, exp))
    check('request window = [last trade - 2y, min(last trade, today)] as YYYYMMDD', not bad, bad[:3])
    c = by[('SIMSCI', 'Oct 26')]
    check('(vi)  resolves but no prints -> NO DATA, no rows, window kept for the audit',
          c.status == NO_DATA and c.rows == [] and c.req_start is not None
          and c.note == 'contract exists, but no OPEN_INT prints between %s and %s'
          % (c.req_start.isoformat(), c.req_end.isoformat()), c)
    ok = [c for c in resolved if c.status == OK]
    check('every OK contract has rows', all(c.rows for c in ok))
    check('rows sorted, strictly increasing dates',
          all(all(a[0] < b[0] for a, b in zip(c.rows, c.rows[1:])) for c in ok))
    check('rows inside the request window', all(c.req_start <= c.rows[0][0] and c.rows[-1][0] <= c.req_end for c in ok))
    check('rows are sessions only (no filled holidays / weekends)', all(is_session(d) for c in ok for d, _ in c.rows))
    check('values are floats equal to the print of that day',
          all(isinstance(v, float) and v == fake_oi(c.ticker, d) for c in ok for d, v in c.rows))
    check('two messages of one history are accumulated, not overwritten',
          all(len(c.rows) == len(fake_rows(c.ticker, c.req_start, c.req_end)) for c in ok))
    c = by[('HSI', 'Feb 25')]
    check('serial contract: starts on its listing day, ~3 months long',
          c.rows[0][0] == first_session_on_or_after(UNIVERSE[c.ticker]['listing'])
          and (c.rows[-1][0] - c.rows[0][0]).days < 100, (c.rows[0], c.rows[-1]))
    c = by[('HSI', 'Dec 25')]
    check('Dec contract listed 3y out: clipped to the 2-year window',
          c.rows[0][0] == first_session_on_or_after(c.req_start) and c.req_start == years_back(c.last_trade, 2),
          (c.rows[0], c.req_start))
    c = by[('HSI', 'Jun 25')]
    check('expired contract: ends on its last trade date', c.rows[-1][0] == last_session_on_or_before(c.last_trade))
    c = by[('HSI', 'Dec 26')]
    check('live contract: ends today', c.rows[-1][0] == last_session_on_or_before(TEST_TODAY))
    c3 = Contract(**{k: getattr(by[('HSI', 'Dec 25')], k) for k in
                        ('product', 'root', 'year', 'month', 'label', 'ticker_1', 'ticker_2', 'ticker', 'status', 'last_trade')})
    fetch_open_interest(bbg, c3, 3, TEST_TODAY)
    check('--years-back 3 widens the window', c3.req_start == years_back(c3.last_trade, 3)
          and bbg.session.log[-1]['settings']['startDate'] == c3.req_start.strftime('%Y%m%d'))
    return results


def test_workbook(results):
    by = {(n, c.label): c for n, cs in results for c in cs}
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, 'test_OI.xlsx')
    write_workbook(path, results)
    wb = load_workbook(path)
    check('tabs: products in order, then Contracts', wb.sheetnames == ['HSI', 'AS51', 'SIMSCI', AUDIT_SHEET], wb.sheetnames)
    with zipfile.ZipFile(path) as z:
        chart_xml = {n: z.read(n) for n in z.namelist() if n.startswith('xl/charts/chart')}
        sheet_xml = {n: z.read(n) for n in z.namelist() if n.startswith('xl/worksheets/sheet')}
    check('no empty <v></v> cells anywhere (the Excel "repair" trigger)',
          all(b'<v></v>' not in x and b'<v/>' not in x for x in sheet_xml.values()))
    check('one chart part per product tab', len(chart_xml) == 3, len(chart_xml))
    check('chart XML: gaps, date axis, no markers, straight lines',
          all(b'dispBlanksAs val="gap"' in x and b'<dateAx>' in x and b'symbol val="none"' in x
              and b'smooth val="0"' in x for x in chart_xml.values()))
    for name, cs in results:
        ws = wb[name]
        dates, found = align_product(cs)
        n, N = len(found), len(dates)
        check('%s: row 1 tickers, row 2 labels, expiry order' % name,
              [ws.cell(1, j).value for j in range(2, n + 2)] == [c.ticker for c in found]
              and [ws.cell(2, j).value for j in range(2, n + 2)] == [c.label for c in found]
              and ws['A1'].value == 'Ticker' and ws['A2'].value == 'Date')
        check('%s: no column beyond the %d found contracts' % (name, n), ws.max_column == n + 1, ws.max_column)
        col_a = [ws.cell(i, 1).value for i in range(3, N + 3)]
        col_a = [v.date() if isinstance(v, dt.datetime) else v for v in col_a]
        check('%s: column A = sorted union of dates, nothing below' % name,
              col_a == dates and all(a < b for a, b in zip(dates, dates[1:])) and ws.max_row == N + 2)
        good, why = True, ''
        for j, c in enumerate(found, start=2):
            lk = dict(c.rows)
            for i, d in enumerate(dates, start=3):
                v, exp = ws.cell(i, j).value, lk.get(d)
                if (exp is None and v is not None) or (exp is not None and v != exp):
                    good, why = False, (c.ticker, d, v, exp)
                    break
            if not good:
                break
        check('%s: every cell is the print of that (contract, date), blank elsewhere' % name, good, why)
        check('%s: no NaN cells' % name,
              all(not (isinstance(v, float) and v != v) for row in ws.iter_rows(values_only=True) for v in row))
        check('%s: freeze panes B3' % name, ws.freeze_panes == 'B3')
        check('%s: exactly one chart' % name, len(ws._charts) == 1)
        ch = ws._charts[0]
        check('%s: LineChart with %d series' % (name, n), isinstance(ch, LineChart) and len(ch.series) == n, len(ch.series))
        check('%s: gaps, date axis mmm-yy by month, both axes shown, crossAx wired' % name,
              ch.display_blanks == 'gap' and isinstance(ch.x_axis, DateAxis)
              and ch.x_axis.number_format.formatCode == 'mmm-yy' and ch.x_axis.majorTimeUnit == 'months'
              and ch.x_axis.delete is False and ch.y_axis.delete is False
              and ch.x_axis.axId == 500 and ch.x_axis.crossAx == 100
              and ch.y_axis.axId == 100 and ch.y_axis.crossAx == 500)
        title = ch.title.tx.rich.p[0].r[0].t
        ytitle = ch.y_axis.title.tx.rich.p[0].r[0].t
        check('%s: chart title and OI axis title' % name,
              title == '%s Futures Open Interest' % name and ytitle == 'OI', (title, ytitle))
        check('%s: legend at the bottom' % name, ch.legend is not None and ch.legend.position == 'b')
        ok_series, why = True, ''
        for k, s in enumerate(ch.series):
            col = get_column_letter(k + 2)
            want = ("'%s'!%s2" % (name, col), "'%s'!$%s$3:$%s$%d" % (name, col, col, N + 2), "'%s'!$A$3:$A$%d" % (name, N + 2))
            got = (s.tx.strRef.f, s.val.numRef.f, s.cat.numRef.f)
            colour = s.graphicalProperties.line.solidFill.srgbClr
            if got != want or s.smooth is not False or s.marker.symbol is not None \
                    or s.graphicalProperties.line.width != 12700 \
                    or colour != series_color(found[k].year, found[k].month, 2024):
                ok_series, why = False, (got, want, colour)
                break
        check('%s: series titles from row 2, values rows 3..%d, dates as categories, year/month colours' % (name, N + 2),
              ok_series, why)
        check('%s: chart anchored one column right of the data' % name,
              ch.anchor._from.col == n + 2 and ch.anchor._from.row == 1, (ch.anchor._from.col, ch.anchor._from.row))
        check('%s: chart 32 x 16 cm' % name, ch.anchor.ext.cx == 11520000 and ch.anchor.ext.cy == 5760000)
    ws = wb[AUDIT_SHEET]
    total = sum(len(cs) for _, cs in results)
    check('Contracts: header + one row per contract', ws.max_row == total + 1 and [c.value for c in ws[1]] == AUDIT_COLUMNS,
          (ws.max_row, total))
    rows = {(r[0], r[1]): r for r in ws.iter_rows(min_row=2, values_only=True)}
    r = rows[('SIMSCI', 'Feb 26')]
    check('Contracts: NOT FOUND row - no ticker, no window, no rows, a note',
          r[5] == NOT_FOUND and r[4] is None and r[9] is None and r[13] is None and r[16], r)
    r = rows[('SIMSCI', 'Oct 26')]
    check('Contracts: NO DATA row - ticker, window, Rows == 0',
          r[5] == NO_DATA and r[4] == 'QZV6 Index' and r[9] is not None and r[13] == 0, r)
    c, r = by[('HSI', 'Sep 25')], rows[('HSI', 'Sep 25')]
    check('Contracts: OK row - both forms, ticker used, dates, rows, last and max OI',
          r[2] == 'HIU5 Index' and r[3] == 'HIU25 Index' and r[4] == c.ticker and r[5] == OK
          and r[6].date() == c.last_trade and r[7] == 'SEP 25' and r[9].date() == c.req_start
          and r[10].date() == c.req_end and r[11].date() == c.first_dt and r[12].date() == c.last_dt
          and r[13] == len(c.rows) and r[14] == c.last_oi and r[15] == c.max_oi, r)
    check('Contracts: frozen header', ws.freeze_panes == 'A2')
    empty = [Contract(product='EMPTY', root='ZZ', year=2024, month=m, label=month_label(2024, m),
                        ticker_1='a', ticker_2='b') for m in range(1, 13)]
    p2 = os.path.join(tmp, 'empty.xlsx')
    write_workbook(p2, [('EMPTY', empty)])
    wb2 = load_workbook(p2)
    check('product with nothing found: note in the tab, no chart, no crash',
          wb2.sheetnames == ['EMPTY', AUDIT_SHEET] and len(wb2['EMPTY']._charts) == 0
          and 'No contract' in str(wb2['EMPTY']['B1'].value))
    for p in (path, p2):
        os.remove(p)
    os.rmdir(tmp)


def test_guards():
    bbg = Bloomberg(blpapi_module=api_with(SilentSession)).connect()
    try:
        bbg.ref(['HIU6 Index'], REF_FIELDS)
        raised = ''
    except RuntimeError as e:
        raised = str(e)
    check('silent terminal -> one sentence after the spin budget, no hang', 'did not answer' in raised, raised)
    bbg = Bloomberg(blpapi_module=api_with(RejectingSession)).connect()
    try:
        bbg.history('HIU6 Index', 'OPEN_INT', dt.date(2024, 1, 1), dt.date(2024, 2, 1))
        raised = ''
    except RuntimeError as e:
        raised = str(e)
    check('REQUEST_STATUS (RequestFailure) -> one sentence', 'rejected the request' in raised, raised)
    bbg = Bloomberg(blpapi_module=api_with(ResponseErrorSession)).connect()
    try:
        bbg.ref(['HIU6 Index'], REF_FIELDS)
        raised = ''
    except RuntimeError as e:
        raised = str(e)
    check('responseError -> one sentence with Bloomberg\'s message', 'Not logged in' in raised, raised)
    bbg = Bloomberg(blpapi_module=FakeAPI).connect()
    out = bbg.ref(['HIU25 Index', 'XXXX FAKE Index'], ['LAST_TRADEABLE_DT', 'NOT_A_FIELD'])
    check('rejected mnemonic + dead ticker collected, good row still returned',
          bbg.field_errors.get('NOT_A_FIELD') == 'BAD_FLD / Invalid Field'
          and 'XXXX FAKE Index' in bbg.bad_securities and 'HIU25 Index' in out
          and isinstance(out['HIU25 Index']['LAST_TRADEABLE_DT'], dt.date))
    hist = bbg.history('XXXX FAKE Index', 'OPEN_INT', dt.date(2024, 1, 1), dt.date(2024, 2, 1))
    check('history of a dead ticker: empty, error collected', hist == [] and 'XXXX FAKE Index' in bbg.bad_securities)
    if importlib.util.find_spec('blpapi') is None:
        rc, text = quiet(main, ['--tickers-only'])
        check('no blpapi on this machine -> ERROR sentence, exit code 1', rc == 1 and 'blpapi is not installed' in text, text)


def test_run():
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, 'run.xlsx')
    FakeSession.instances.clear()
    out, text = quiet(run, products=FAKE_PRODUCTS, today=TEST_TODAY, blpapi_module=FakeAPI, out=path)
    check('run(): returns the path and writes the file', out == path and os.path.exists(path))
    check('run(): per-product counts, NOT FOUND months, NO DATA months, output path printed',
          ('%-8s %2d/%d' % ('AS51', 12, 36)) in text and ('%-11s Jan 24' % 'NOT FOUND:') in text
          and ('%-11s Oct 26' % 'NO DATA:') in text and ('Written: %s' % path) in text, text[-800:])
    check('run(): session closed', FakeSession.instances and FakeSession.instances[-1].stopped)
    FakeSession.instances.clear()
    out, text = quiet(run, products=FAKE_PRODUCTS, today=TEST_TODAY, blpapi_module=FakeAPI, tickers_only=True)
    sess = FakeSession.instances[-1]
    check('run(tickers_only): no historical request, table printed, returns ""',
          out == '' and not any(e['op'] == 'HistoricalDataRequest' for e in sess.log)
          and 'HIU25 Index' in text and 'NOT FOUND' in text)
    try:
        quiet(main, ['--help'])
        code = None
    except SystemExit as e:
        code = e.code
    check('--help exits 0', code == 0, code)
    path2 = os.path.join(tmp, 'nb.xlsx')
    out, text = quiet(notebook_main, products=FAKE_PRODUCTS, today=TEST_TODAY, blpapi_module=FakeAPI,
                      out=path2, show_charts_=False)
    check('notebook_main(): runs everything, returns the path', out == path2 and os.path.exists(path2) and 'Written:' in text)
    out, text = quiet(notebook_main, products=FAKE_PRODUCTS, today=TEST_TODAY,
                      blpapi_module=api_with(SilentSession), out=path2)
    check('notebook_main(): a Bloomberg problem is one clear message with the step, no traceback',
          out is None and 'ERROR while resolving the tickers:' in text and 'Bloomberg did not answer' in text
          and 'Traceback' not in text, text)
    results = resolve_contracts(Bloomberg(blpapi_module=FakeAPI).connect(), FAKE_PRODUCTS,
                                  contract_months(2024, 2026), TEST_TODAY)
    bbg = Bloomberg(blpapi_module=FakeAPI).connect()
    for _, cs in results:
        for c in cs:
            fetch_open_interest(bbg, c, 2, TEST_TODAY)
    if importlib.util.find_spec('matplotlib') is None:
        n, text = quiet(show_charts, results)
        check('show_charts without matplotlib: says so in one line, draws nothing', n == 0 and 'matplotlib is not installed' in text)
    else:
        import warnings
        import matplotlib.pyplot as plt
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            n, text = quiet(show_charts, results)
        figs = plt.get_fignums()
        titles = [plt.figure(i).axes[0].get_title() for i in figs]
        n_lines = [len(plt.figure(i).axes[0].get_lines()) for i in figs]
        plt.close('all')
        check('show_charts with matplotlib: one figure per product with data, one line per found contract',
              n == 3 and len(figs) == 3 and titles == ['HSI Futures Open Interest', 'AS51 Futures Open Interest',
                                                       'SIMSCI Futures Open Interest']
              and n_lines == [36, 12, 34], (n, titles, n_lines))
    os.remove(path)
    os.remove(path2)
    os.rmdir(tmp)


class DeadTerminalSession(FakeSession):
    def start(self):
        return False


class StopsMidPullSession(FakeSession):
    """The 5th HistoricalDataRequest is rejected (the shape of a data-limit hit)."""
    def sendRequest(self, request):
        n_hist = sum(1 for e in self.log if e['op'] == 'HistoricalDataRequest')
        if request.operation == 'HistoricalDataRequest' and n_hist == 4:
            self.log.append(dict(op=request.operation, securities=list(request.securities),
                                 fields=list(request.fields), settings=dict(request.settings)))
            root = FakeElement('RequestFailure', children=[
                ('reason', fake_complex('reason', [('description', 'Daily capacity reached')]))])
            self._queue = [FakeEvent([FakeMessage(root)], FakeEvent.REQUEST_STATUS)]
            return
        FakeSession.sendRequest(self, request)


class BuggyHistorySession(FakeSession):
    """A history response that makes the parser blow up with a non-Bloomberg error."""
    def _hist_events(self, request):
        raise TypeError('unexpected element shape')


def test_not_a_future():
    bbg = Bloomberg(blpapi_module=FakeAPI).connect()
    results = resolve_contracts(bbg, [('NF', 'NOTFUT')], [(2024, 3), (2024, 4)], TEST_TODAY)
    mar, apr = results[0][1]
    check('a ticker that exists but is not a future is skipped, the real form is used',
          mar.status == OK and mar.ticker == 'NFH24 Index', mar)
    check('no futures contract at all -> NOT FOUND, note explains both forms',
          apr.status == NOT_FOUND and apr.note == 'NFJ4 Index -> not a futures contract (no LAST_TRADEABLE_DT; '
          'name: FAKE NFJ4 SOMETHING ELSE); NFJ24 Index -> Unknown/Invalid Security [nid:1234]', apr.note)
    check('field refusals remembered per security',
          bbg.field_error_secs.get('LAST_TRADEABLE_DT') == {'NFH4 Index', 'NFJ4 Index'} and bbg.n_ref_securities == 4)
    _, text = quiet(print_summary, results, bbg, None)
    check('summary explains the refusal instead of calling the field invalid',
          'LAST_TRADEABLE_DT not applicable to 2 of 4 candidate tickers' in text and 'e.g. NFH4 Index' in text
          and 'NOT FOUND = neither ticker form' in text and 'refused' not in text, text)
    bbg = Bloomberg(blpapi_module=FakeAPI).connect()
    bbg.ref(['HIU25 Index'], ['NOT_A_FIELD'])
    _, text = quiet(print_summary, [('HSI', [])], bbg, None)
    check('a mnemonic refused for every security is reported as refused',
          'Bloomberg refused the field NOT_A_FIELD for 1 securities: BAD_FLD / Invalid Field' in text, text)


def test_failures():
    tmp = tempfile.mkdtemp()
    # output_path: bare names go to OUTPUT_FOLDER, missing folder -> current folder, paths untouched
    global OUTPUT_FOLDER
    saved = OUTPUT_FOLDER
    try:
        OUTPUT_FOLDER = tmp
        p1 = output_path(None, dt.date(2026, 9, 17))
        OUTPUT_FOLDER = os.path.join(tmp, 'does-not-exist')
        p2 = output_path('x.xlsx')
        p3 = output_path(os.path.join(tmp, 'sub', 'y.xlsx'))
    finally:
        OUTPUT_FOLDER = saved
    check('output_path: default name in OUTPUT_FOLDER, missing folder -> cwd, explicit path kept',
          p1 == os.path.join(tmp, 'OI_charts_20260917.xlsx') and p2 == os.path.join(os.getcwd(), 'x.xlsx')
          and p3 == os.path.join(tmp, 'sub', 'y.xlsx'), (p1, p2, p3))
    # terminal not running
    out, text = quiet(notebook_main, products=FAKE_PRODUCTS, today=TEST_TODAY,
                      blpapi_module=api_with(DeadTerminalSession), out=os.path.join(tmp, 'a.xlsx'))
    check('terminal not running -> "ERROR while connecting to Bloomberg" + what to check',
          out is None and 'ERROR while connecting to Bloomberg' in text and 'logged in' in text
          and 'Traceback' not in text, text)
    # a data-limit style failure in the middle of the pull: keep what was pulled, say where it stopped
    path = os.path.join(tmp, 'partial.xlsx')
    out, text = quiet(notebook_main, products=FAKE_PRODUCTS, today=TEST_TODAY,
                      blpapi_module=api_with(StopsMidPullSession), out=path, show_charts_=False)
    wb = load_workbook(path) if os.path.exists(path) else None
    statuses = [r[5] for r in wb[AUDIT_SHEET].iter_rows(min_row=2, values_only=True)] if wb else []
    check('pull stops at contract 5: workbook still written with the 4 pulled, rest NOT PULLED, message says so',
          out is None and wb is not None and 'ERROR while pulling OPEN_INT for HIK24 Index (HSI May 24)' in text
          and 'Daily capacity reached' in text and 'still written with the 4 of 83' in text and path in text
          and wb['HSI'].max_column == 5 and statuses.count(NOT_PULLED) == 79 and statuses.count(OK) == 4
          and 'HSI      pulling' in text and 'AS51     skipped' in text and 'NOT PULLED:' in text
          and 'Traceback' not in text, text[-900:])
    # an unexpected (non-Bloomberg) error: the message names the step AND the traceback follows
    out, text = quiet(notebook_main, products=FAKE_PRODUCTS, today=TEST_TODAY,
                      blpapi_module=api_with(BuggyHistorySession), out=os.path.join(tmp, 'b.xlsx'), show_charts_=False)
    check('unexpected error -> step named, "Full detail for debugging" and the traceback shown',
          out is None and 'ERROR while pulling OPEN_INT for HIF24 Index (HSI Jan 24)' in text
          and 'Full detail for debugging' in text and 'TypeError: unexpected element shape' in text
          and 'Traceback' in text, text[-600:])
    # the command line reports the same way and exits 1
    rc, text = quiet(main, ['--out', os.path.join(tmp, 'c.xlsx')]) if importlib.util.find_spec('blpapi') is None else (1, 'ERROR while connecting')
    check('command line: same message, exit code 1', rc == 1 and 'ERROR while connecting to Bloomberg' in text, text)
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)


def demo(out=None):
    """The whole pipeline on fake data: a workbook to open in Excel, charts inline in Jupyter."""
    out = out or os.path.join(os.getcwd(), 'demo_OI_charts.xlsx')
    run(products=FAKE_PRODUCTS, today=TEST_TODAY, blpapi_module=FakeAPI, out=out)
    print('open it in Excel: 3 product tabs with a chart each, plus Contracts')


def run_tests():
    """python oi_charts.py --test  ->  PASS/FAIL per check; returns 1 if anything failed."""
    if not in_ipython():
        os.environ.setdefault('MPLBACKEND', 'Agg')      # matplotlib, if present, must not open windows
    del FAILS[:]
    COUNT[0] = 0
    test_helpers()
    bbg, results = test_resolution()
    test_history(bbg, results)
    test_workbook(results)
    test_guards()
    test_run()
    test_not_a_future()
    test_failures()
    print('\n%d checks, %d failed' % (COUNT[0], len(FAILS)))
    for f in FAILS:
        print('  FAIL  ' + f)
    return 1 if FAILS else 0


# ================================================================= ENTRY ===
if __name__ == '__main__':
    if '--test' in sys.argv[1:]:                    # python oi_charts.py --test / %run oi_charts.py --test
        _rc = run_tests()
        if not in_ipython():
            sys.exit(_rc)
    elif '--demo' in sys.argv[1:]:
        _i = sys.argv.index('--demo')
        demo(sys.argv[_i + 1] if len(sys.argv) > _i + 1 else None)
    elif in_ipython():                              # %run oi_charts.py, or the file pasted into a cell
        _ = notebook_main()
    else:
        sys.exit(main())
