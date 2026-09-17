#!/usr/bin/env python3
"""Daily open interest of index futures from Bloomberg -> one Excel tab + chart per product.

Everything you may want to change is in the CONFIG block right below.  The engine
underneath needs no edits.  Run the whole file at once:

    Jupyter       %run oi_charts.py      (or paste the file into a cell and run it)
                  -> pulls the data, draws every chart in the notebook, writes the workbook
    Command line  python oi_charts.py [--tickers-only] [--out FILE] [--years-back N]
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

# 4. Output.  None -> OI_charts_<yyyymmdd>.xlsx in the working folder.
OUTPUT_FILE = None
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
import sys                                        # noqa: E402
from typing import List, Optional, Tuple          # noqa: E402

from openpyxl import Workbook                     # noqa: E402
from openpyxl.chart import LineChart, Reference   # noqa: E402
from openpyxl.chart.axis import DateAxis          # noqa: E402
from openpyxl.utils import get_column_letter      # noqa: E402

REF_FIELDS = ['LAST_TRADEABLE_DT', 'FUT_MONTH_YR', 'NAME']
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
        for status in (NOT_FOUND, NO_DATA):
            labels = [c.label for c in cs if c.status == status]
            if labels:
                print('         %-9s %s' % (status + ':', ', '.join(labels)))
    if bbg.field_errors:
        print('Bloomberg rejected these fields: ' + ', '.join(
            '%s (%s)' % kv for kv in sorted(bbg.field_errors.items())))
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
    out = out or OUTPUT_FILE or 'OI_charts_%s.xlsx' % today.strftime('%Y%m%d')
    write_workbook(out, results, base_year=start_year)
    print_summary(results, bbg, out)
    if show_charts_:
        show_charts(results, base_year=start_year)
    return out


def notebook_main(**kw):
    """What %run / a pasted cell does: run everything; a problem is one printed sentence."""
    try:
        return run(**kw)
    except PermissionError as e:
        print('ERROR: cannot write the workbook - close it in Excel and rerun (%s)' % e)
    except RuntimeError as e:
        print('ERROR: %s' % e)
    return None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', default=OUTPUT_FILE, help='output workbook (default OI_charts_<yyyymmdd>.xlsx)')
    p.add_argument('--start-year', type=int, default=START_YEAR, help='first contract year (default %(default)s)')
    p.add_argument('--end-year', type=int, default=END_YEAR, help='last contract year (default %(default)s)')
    p.add_argument('--years-back', type=int, default=YEARS_BACK,
                   help='history per contract, back from its last trade date (default %(default)s)')
    p.add_argument('--tickers-only', action='store_true', default=TICKERS_ONLY,
                   help='resolve and print the contract table, no history')
    p.add_argument('--asof', help='treat this date (YYYY-MM-DD) as today')
    a = p.parse_args(argv)
    today = dt.date.fromisoformat(a.asof) if a.asof else None
    try:
        run(start_year=a.start_year, end_year=a.end_year, years_back_n=a.years_back,
            out=a.out, today=today, tickers_only=a.tickers_only, show_charts_=False)
        return 0
    except PermissionError as e:
        print('ERROR: cannot write the workbook - close it in Excel and rerun (%s)' % e)
        return 1
    except RuntimeError as e:
        print('ERROR: %s' % e)
        return 1


if __name__ == '__main__':
    if in_ipython():                 # %run oi_charts.py, or the file pasted into a cell
        _ = notebook_main()
    else:
        sys.exit(main())
