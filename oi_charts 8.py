#!/usr/bin/env python3
"""Daily open interest of index futures from Bloomberg, as USD notional -> one Excel tab + chart per product.

Everything you may want to change is in the CONFIG block right below.  The engine
underneath needs no edits.  Run the whole file at once:

    Jupyter       %run oi_charts.py      (or paste the file into a cell and run it)
                  -> pulls the data, writes the workbook, draws every chart in the notebook
    Command line  python oi_charts.py [--tickers-only] [--out FILE] [--years-back N] [--skip-months N]
                                     [--measure oi|notional] [--chart stacked|lines]

Self-check, no terminal needed (a fake Bloomberg inside this file drives the real code):

    python oi_charts.py --test     self-checks: ticker forms, windows, cell-by-cell alignment, errors
    python oi_charts.py --demo     writes demo_OI_charts.xlsx from fake data (and draws it in Jupyter)

Each contract's line is its USD notional: open interest x FUT_VAL_PT (value of one index point in
the contract's currency) x the underlying index's daily last price, converted to USD at the
contract currency's rate.  The index (not the futures price) is used so every expiry is scaled
the same way.  Set MEASURE = 'oi' for plain contract counts.

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
    ('TWT', 'FTSE TW'),         # SGX FTSE Taiwan (TWTU6 ...)
    ('MTW', 'MTW'),             # Taiwan futures, MTWU6 ... (tab named after the root - rename here if wanted)
    ('FPO', 'FPO'),
    ('HJA', 'TAMSCI'),          # the request note's "MSCI - HJAU6" row is this same root
    ('QZ',  'SIMSCI'),
]

# 2. Contract months: every month from Jan START_YEAR to Dec END_YEAR (36 for 2024-2026).
START_YEAR, END_YEAR = 2024, 2026

# 3. History per contract: from its last trade date back this many years (or as far as
#    Bloomberg has prints - a contract listed later simply has fewer rows, never NA).
YEARS_BACK = 3

# 3b. Months dropped at the end of every contract's history: the contract month itself and
#     the SKIP_MONTHS - 1 months before it.  2 -> Jun 24 gets data up to 30 Apr 24 (no May 24,
#     no Jun 24).  0 -> keep everything up to the last trade date, as before.
SKIP_MONTHS = 2

# 4. Output.  The workbook is OI_charts_<yyyymmdd>.xlsx (or OUTPUT_FILE) and goes to
#    OUTPUT_FOLDER; when that folder does not exist it goes to the current folder instead.
#    The full path is printed at the end of every run.
OUTPUT_FILE = None
OUTPUT_FOLDER = '~/Downloads'
SHOW_CHARTS = True              # in Jupyter also draw every chart inline (needs matplotlib)
TICKERS_ONLY = False            # True -> only resolve and print the contract table (quick check)

# 5. What each line is.  'notional': open interest x FUT_VAL_PT x index level, in USD (a product
#    whose index or multiplier cannot be found falls back to plain OI, and the chart title and the
#    summary say so).  'oi': open interest in contracts.  {name} in the text is the tab name.
MEASURE = 'notional'
CHART_TITLE = {'notional': '{name} Futures Open Interest, USD notional',
               'oi': '{name} Futures Open Interest'}
FALLBACK_TITLE = '{name} Futures Open Interest, contracts (USD notional unavailable)'
Y_AXIS_TITLE = {'notional': 'Notional (USD m)', 'oi': 'Open interest (contracts)'}
Y_NUMBER_FORMAT = {'notional': '#,##0,,"m"', 'oi': '#,##0'}   # cells hold the full USD amount

# 5b. Chart type.  'stacked': the contracts stacked as daily columns (earliest expiry at the
#     bottom, no gap between days), so the top edge of the stack is the product total - traced
#     by a black Total line - and each contract is named in a small box at the end of its own
#     band.  'lines': one line per contract.
CHART_KIND = 'stacked'

# 5c. Band colours: one per contract month, restrained and desaturated.  The quarterlies, which
#     carry most of the open interest, get the four strongest tones (navy, steel blue, burgundy,
#     slate teal); the serial months sit in greys, sand and sage so they read as secondary.  A
#     contract one year older than the newest in the workbook is drawn 22% lighter, two years
#     older 44% lighter.  Edit freely - hex, no '#'.
MONTH_COLORS = {
    1: '9BA7B4',    # Jan  light slate
    2: 'C9B18C',    # Feb  sand
    3: '3E6E9C',    # Mar  steel blue
    4: '8A9A88',    # Apr  sage grey
    5: 'A9A39D',    # May  warm grey
    6: '8C2F3C',    # Jun  burgundy
    7: '6F8AA3',    # Jul  dusty blue
    8: 'B39B72',    # Aug  khaki
    9: '3F7C78',    # Sep  slate teal
    10: '8E7F87',   # Oct  mauve grey
    11: '7C8D99',   # Nov  blue grey
    12: '1F3652',   # Dec  navy
}
YEAR_FADE = 0.22    # share of white mixed in per year of age, capped at two years

# 6. Bloomberg.
HIST_FIELD = 'OPEN_INT'         # daily open interest of one contract
YELLOW_KEY = 'Index'            # default yellow key for the roots above
BBG_HOST, BBG_PORT = 'localhost', 8194

# 7. Underlying index, for the notional.  The index ticker defaults to '<tab name> Index'
#    (HSI Index, KOSPI2 Index, AS51 Index ...); INDEX_TICKERS lists the exceptions.  Notional =
#    OI x FUT_VAL_PT x index level (in index points), an amount in the contract's currency, turned
#    into USD with FX_TICKER (local per USD, so divide).  FX_OVERRIDES swaps in another pair, e.g.
#    {'AUD': ('AUDUSD Curncy', 'multiply')}.
#    The contract currency is CONTRACT_CURRENCY[tab] if listed, else the INDEX's own currency
#    (its CRNCY: KOSPI2 -> KRW, HSI -> HKD, AS51 -> AUD, TWSE -> TWD).  Bloomberg's CRNCY field
#    on the futures is NOT used for this - it comes back as USD for KRW contracts such as KM -
#    it is only reported, and a disagreement is flagged in the summary and the Indices tab.
#    List the genuinely USD-denominated contracts here (SGX's dollar contracts); a USD contract
#    needs no rate: OI x FUT_VAL_PT (in USD) x index points is already USD.
CONTRACT_CURRENCY = {
    'FPO': 'USD',       # SGX FTSE China A50: USD 1 x index   <- CHECK on the terminal
    'FTSE TW': 'USD',   # SGX FTSE Taiwan: USD 40 x index     <- CHECK on the terminal
}
INDEX_TICKERS = {
    'FTSE TW': 'TWSE Index',    # <- CHECK on the terminal: the FTSE Taiwan (RIC capped) index the TWT future settles on
    'MTW': 'TWSE Index',        # <- CHECK on the terminal: whatever the MTW future settles on
    'FPO': 'XIN9I Index',       # FTSE China A50
}
FX_TICKER = 'USD{ccy} Curncy'
FX_OVERRIDES = {}
INDEX_FIELD = 'PX_LAST'         # daily last price of the index and of the FX rate
MULTIPLIER_FIELD = 'FUT_VAL_PT' # value of one index point, in the contract's currency
# ===========================================================================


# ================================================================ ENGINE ===
import argparse                                   # noqa: E402
import bisect                                     # noqa: E402
import dataclasses                                # noqa: E402
import datetime as dt                             # noqa: E402
import os                                         # noqa: E402
import sys                                        # noqa: E402
import traceback                                  # noqa: E402
from typing import List, Optional, Tuple          # noqa: E402

try:
    from openpyxl import Workbook, load_workbook          # noqa: E402
    from openpyxl.chart import BarChart, LineChart, Reference   # noqa: E402
    from openpyxl.chart.label import DataLabel, DataLabelList   # noqa: E402
    from openpyxl.chart.axis import DateAxis              # noqa: E402
    from openpyxl.chart.shapes import GraphicalProperties  # noqa: E402
    from openpyxl.chart.text import RichText, Text        # noqa: E402
    from openpyxl.chart.title import Title                # noqa: E402
    from openpyxl.drawing.line import LineProperties      # noqa: E402
    from openpyxl.drawing.text import (CharacterProperties, Paragraph, ParagraphProperties,   # noqa: E402
                                       RegularTextRun, RichTextProperties)
    from openpyxl.utils import get_column_letter          # noqa: E402
except ImportError:
    print('openpyxl is not installed in this Python - run:  pip install openpyxl')
    raise

REF_FIELDS = ['LAST_TRADEABLE_DT', 'FUT_MONTH_YR', 'NAME', 'CRNCY', MULTIPLIER_FIELD]
EVENT_SPINS = 240                        # 500 ms each: ~2 min per request, then it is an error
REF_CHUNK = 100                          # securities per ReferenceDataRequest

MONTH_CODES = 'FGHJKMNQUVXZ'             # index 0 = January
MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

OK, NOT_FOUND, NO_DATA, NOT_PULLED = 'OK', 'NOT FOUND', 'NO DATA', 'NOT PULLED'
AUDIT_SHEET = 'Contracts'
INDEX_SHEET = 'Indices'
INDEX_REF_FIELDS = ['CRNCY', 'NAME']
INDEX_COLUMNS = ['Product', 'Index ticker', 'Name', 'Index ccy', 'Contract ccy used', 'Ccy source',
                 'Futures CRNCY (Bloomberg)', 'FX ticker', 'Status', 'Request start', 'Request end',
                 'First date', 'Last date', 'Rows', 'Last index', 'Last FX', 'Last index (USD)', 'Note']
# chart look: dark grey text, light grey axis lines, no gridlines, no borders, black total line
CHART_TEXT, CHART_LINE, TOTAL_COLOR = '404040', 'BFBFBF', '1A1A1A'
TOTAL_LABEL = 'Total'
AUDIT_COLUMNS = ['Product', 'Contract', 'Ticker 1-digit', 'Ticker 2-digit', 'Ticker used',
                 'Status', 'LAST_TRADEABLE_DT', 'FUT_MONTH_YR', 'Name', 'Request start',
                 'Request end', 'First OI date', 'Last OI date', 'Rows', 'Last OI', 'Max OI',
                 'Multiplier', 'Ccy', 'Last notional (USD)', 'Max notional (USD)', 'Note']

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


def month_end(year, month):
    """Last calendar day of (year, month)."""
    if month == 12:
        return dt.date(year, 12, 31)
    return dt.date(year, month + 1, 1) - dt.timedelta(days=1)


def history_cutoff(year, month, skip_months):
    """Last day the history of the (year, month) contract may reach: end of the month
    skip_months before the contract month.  (2024, 6, 2) -> 30 Apr 2024.  0 -> None (no cutoff)."""
    if not skip_months:
        return None
    idx = year * 12 + (month - 1) - skip_months
    return month_end(idx // 12, idx % 12 + 1)


def as_float(v):
    """A positive float, or None (NaN, None, text that is not a number)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f > 0 else None


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


def stack_color(year, month, last_year):
    """Hex colour (no '#') for one contract's band in the stack: MONTH_COLORS[month], faded
    towards white by YEAR_FADE per year of age (last_year = the newest contract year in the
    workbook, capped at two years)."""
    base = MONTH_COLORS[month]
    t = YEAR_FADE * max(0, min(2, last_year - year))
    rgb = [round(int(base[i:i + 2], 16) * (1 - t) + 255 * t) for i in (0, 2, 4)]
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
    currency: str = ''               # CRNCY of the future
    multiplier: Optional[float] = None   # FUT_VAL_PT
    req_start: Optional[dt.date] = None
    req_end: Optional[dt.date] = None
    rows: List[Tuple[dt.date, float]] = dataclasses.field(default_factory=list)  # OI, sorted
    notional: List[Tuple[dt.date, float]] = dataclasses.field(default_factory=list)  # USD, sorted
    note: str = ''

    @property
    def last_notional(self):
        return self.notional[-1][1] if self.notional else None

    @property
    def max_notional(self):
        return max(v for _, v in self.notional) if self.notional else None

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


@dataclasses.dataclass
class IndexSeries:
    """One product's underlying index and the USD rate of the product's contract currency.

    rows = index points / rate: multiplied by FUT_VAL_PT and the open interest it is the USD notional.
    """
    product: str                     # tab name
    ticker: str                      # 'KOSPI2 Index'
    currency: str = ''               # CRNCY of the index (for the audit)
    name: str = ''
    fut_currency: str = ''           # currency of FUT_VAL_PT actually used (config, else the index's)
    bbg_fut_currency: str = ''       # what Bloomberg's CRNCY on the futures said (reported only)
    ccy_source: str = ''             # 'CONTRACT_CURRENCY' | 'index CRNCY'
    fx_ticker: str = ''              # 'USDKRW Curncy' ('' for a USD-denominated future)
    fx_mode: str = 'divide'          # amount / rate, or 'multiply'
    status: str = NOT_FOUND
    req_start: Optional[dt.date] = None
    req_end: Optional[dt.date] = None
    index_rows: List[Tuple[dt.date, float]] = dataclasses.field(default_factory=list)  # index points
    fx_rows: List[Tuple[dt.date, float]] = dataclasses.field(default_factory=list)
    rows: List[Tuple[dt.date, float]] = dataclasses.field(default_factory=list)        # points / rate
    note: str = ''

    @property
    def label(self):
        return self.ticker.split()[0]

    @property
    def first_dt(self):
        return self.rows[0][0] if self.rows else None

    @property
    def last_dt(self):
        return self.rows[-1][0] if self.rows else None

    @property
    def last_index(self):
        return self.index_rows[-1][1] if self.index_rows else None

    @property
    def last_fx(self):
        return self.fx_rows[-1][1] if self.fx_rows else None

    @property
    def last_usd(self):
        """The last index level in USD terms (points / rate); the multiplier is not in it."""
        return self.rows[-1][1] if self.rows else None


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
    c.currency = str(row.get('CRNCY') or '').strip().upper()
    c.multiplier = as_float(row.get(MULTIPLIER_FIELD))


def resolve_contracts(bbg, products, months, today):
    """One batched reference pass over both ticker forms of every contract."""
    results = build_contracts(products, months)
    candidates = [t for _, cs in results for c in cs for t in (c.ticker_1, c.ticker_2)]
    ref = bbg.ref(candidates, REF_FIELDS)
    for _, cs in results:
        for c in cs:
            pick_ticker(c, ref, bbg.bad_securities, today)
    return results


def fetch_open_interest(bbg, c, years_back_n, today, skip_months=None):
    """Fill c.rows with daily OPEN_INT from last trade - years_back_n up to the earliest of the
    last trade date, today, and the end of the month skip_months before the contract month."""
    if c.status != OK:
        return
    skip_months = SKIP_MONTHS if skip_months is None else skip_months
    c.req_start = years_back(c.last_trade, years_back_n)
    c.req_end = min(c.last_trade, today)
    cutoff = history_cutoff(c.year, c.month, skip_months)
    if cutoff is not None:
        c.req_end = min(c.req_end, cutoff)
    if c.req_start > c.req_end:
        c.status, c.note = NO_DATA, 'window starts after its end'
        return
    c.rows = bbg.history(c.ticker, HIST_FIELD, c.req_start, c.req_end)
    if not c.rows:
        c.status = NO_DATA
        c.note = bbg.bad_securities.get(c.ticker) or (
            'contract exists, but no %s prints between %s and %s'
            % (HIST_FIELD, c.req_start.isoformat(), c.req_end.isoformat()))


def index_ticker(name):
    """The index behind a product tab: INDEX_TICKERS, else '<tab name> Index'."""
    return INDEX_TICKERS.get(name) or '%s Index' % name


def fx_for(currency):
    """(FX ticker, 'divide' | 'multiply') that turns an amount in `currency` into USD.
    ('', 'divide') for USD itself - the amount is used as is.  An empty currency is refused: it
    must never silently mean 'no conversion'."""
    ccy = (currency or '').strip().upper()
    if not ccy:
        raise ValueError('fx_for: no currency given')
    if ccy == 'USD':
        return '', 'divide'
    if ccy in FX_OVERRIDES:
        t, mode = FX_OVERRIDES[ccy]
        return t, mode
    return FX_TICKER.format(ccy=ccy), 'divide'


def product_currency(contracts):
    """The contract currency of a product: what its resolved contracts say (the most common one)."""
    seen = {}
    for c in contracts:
        if c.status == OK and c.currency:
            seen[c.currency] = seen.get(c.currency, 0) + 1
    return max(seen, key=seen.get) if seen else ''


def resolve_indices(bbg, results):
    """One reference pass (CRNCY, NAME) over every product's index -> {tab name: IndexSeries}.

    The FX pair is chosen by the contract currency: CONTRACT_CURRENCY[tab] if listed, else the
    index's own CRNCY.  Bloomberg's CRNCY on the futures is recorded for the audit only.
    """
    out = {name: IndexSeries(product=name, ticker=index_ticker(name), bbg_fut_currency=product_currency(cs))
           for name, cs in results}
    ref = bbg.ref(sorted({ix.ticker for ix in out.values()}), INDEX_REF_FIELDS)
    for ix in out.values():
        if ix.ticker in bbg.bad_securities:
            ix.note = '%s -> %s' % (ix.ticker, bbg.bad_securities[ix.ticker])
            continue
        row = ref.get(ix.ticker)
        if row is None:
            ix.note = '%s -> no answer from Bloomberg' % ix.ticker
            continue
        ix.currency = str(row.get('CRNCY') or '').strip().upper()
        ix.name = str(row.get('NAME') or '')
        configured = (CONTRACT_CURRENCY.get(ix.product) or '').strip().upper()
        if configured:
            ix.fut_currency, ix.ccy_source = configured, 'CONTRACT_CURRENCY'
        elif ix.currency:
            ix.fut_currency, ix.ccy_source = ix.currency, 'index CRNCY'
        else:
            ix.note = ('%s has no CRNCY and %s is not in CONTRACT_CURRENCY, so the contract currency is unknown'
                       % (ix.ticker, ix.product))
            continue
        if ix.bbg_fut_currency and ix.bbg_fut_currency != ix.fut_currency:
            ix.note = ('Bloomberg CRNCY on the futures says %s - ignored, %s used (%s)'
                       % (ix.bbg_fut_currency, ix.fut_currency, ix.ccy_source))
        ix.fx_ticker, ix.fx_mode = fx_for(ix.fut_currency)
        ix.status = OK
    return out


def to_usd(index_rows, fx_rows, mode='divide'):
    """[(date, USD level)]: each index day uses the last FX print on or before it (rates are carried
    forward over the index market's own holidays).  Index days before the first FX print are dropped."""
    if not fx_rows:
        return list(index_rows)
    fx_dates = [d for d, _ in fx_rows]
    out = []
    for d, level in index_rows:
        i = bisect.bisect_right(fx_dates, d) - 1
        if i < 0:
            continue
        rate = fx_rows[i][1]
        if not rate:
            continue
        out.append((d, level * rate if mode == 'multiply' else level / rate))
    return out


def fetch_index(bbg, ix, contracts, today):
    """Pull the index (and the contract currency's rate) over the span of the product's contract
    windows; ix.rows = index points / rate."""
    if ix.status != OK:
        return
    windows = [(c.req_start, c.req_end) for c in contracts if c.status == OK and c.rows]
    if not windows:
        ix.status, ix.note = NO_DATA, 'no contract of this product has data, so there is no window'
        return
    ix.req_start = min(s for s, _ in windows)
    ix.req_end = min(max(e for _, e in windows), today)
    ix.index_rows = bbg.history(ix.ticker, INDEX_FIELD, ix.req_start, ix.req_end)
    if not ix.index_rows:
        ix.status = NO_DATA
        ix.note = bbg.bad_securities.get(ix.ticker) or (
            'no %s prints between %s and %s' % (INDEX_FIELD, ix.req_start.isoformat(), ix.req_end.isoformat()))
        return
    if ix.fx_ticker:                                # start the rate a little earlier for the first index days
        ix.fx_rows = bbg.history(ix.fx_ticker, INDEX_FIELD, ix.req_start - dt.timedelta(days=10), ix.req_end)
        if not ix.fx_rows:
            ix.status = NO_DATA
            ix.note = bbg.bad_securities.get(ix.fx_ticker) or (
                'no %s prints for %s between %s and %s' % (INDEX_FIELD, ix.fx_ticker, ix.req_start.isoformat(),
                                                           ix.req_end.isoformat()))
            return
    ix.rows = to_usd(ix.index_rows, ix.fx_rows, ix.fx_mode)
    if not ix.rows:
        ix.status, ix.note = NO_DATA, 'no index day has an FX rate'
        return
    dropped = len(ix.index_rows) - len(ix.rows)
    if dropped:
        ix.note = (ix.note + '; ' if ix.note else '') + '%d index day(s) before the first FX print dropped' % dropped


def compute_notional(contracts, ix):
    """c.notional = OI x FUT_VAL_PT x (index points / rate) for every OI day, using the last index
    print on or before that day.  Contracts without a multiplier, or products without an index,
    keep an empty notional and say why in the note."""
    have_index = ix is not None and ix.status == OK and ix.rows
    ix_dates = [d for d, _ in ix.rows] if have_index else []
    for c in contracts:
        c.notional = []
        if c.status != OK or not c.rows:
            continue
        if not have_index:
            c.note = (c.note + '; ' if c.note else '') + 'no USD notional: %s' % (
                ix.note if ix is not None and ix.note else 'index %s' % (ix.status if ix else 'not requested'))
            continue
        if c.multiplier is None:
            c.note = (c.note + '; ' if c.note else '') + 'no USD notional: %s missing' % MULTIPLIER_FIELD
            continue
        out = []
        for d, oi in c.rows:
            i = bisect.bisect_right(ix_dates, d) - 1
            if i >= 0:
                out.append((d, oi * c.multiplier * ix.rows[i][1]))
        c.notional = out
        if len(out) < len(c.rows):
            c.note = (c.note + '; ' if c.note else '') + '%d OI day(s) before the first index print have no notional' % (
                len(c.rows) - len(out))


def product_series(contracts, measure):
    """What one tab shows: (measure used, [(contract, rows)], sorted union of dates, note).

    'notional' falls back to 'oi' for a product where no contract has a notional.
    """
    ok = [c for c in contracts if c.status == OK and c.rows]
    used, note = measure, ''
    if measure == 'notional':
        with_n = [c for c in ok if c.notional]
        if with_n:
            skipped = [c.label for c in ok if not c.notional]
            if skipped:
                note = 'no notional for %s' % ', '.join(skipped)
            ok = with_n
        else:
            used = 'oi'
            reasons = sorted({c.note.split('no USD notional: ', 1)[1] for c in ok if 'no USD notional: ' in c.note})
            note = 'USD notional unavailable' + (' - ' + '; '.join(reasons) if reasons else '')
    series = [(c, c.notional if used == 'notional' else c.rows) for c in ok]
    dates = sorted({d for _, rows in series for d, _ in rows})
    return used, series, dates, note


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


def chart_text(size, bold=False, color=CHART_TEXT):
    """Text properties for an axis, legend or title: Calibri-ish size (in 1/100 pt), colour."""
    cp = CharacterProperties(sz=size, b=bold, solidFill=color)
    return RichText(p=[Paragraph(pPr=ParagraphProperties(defRPr=cp), endParaRPr=cp)])


def chart_title(text, size=1300):
    cp = CharacterProperties(sz=size, b=True, solidFill=CHART_TEXT)
    return Title(tx=Text(rich=RichText(bodyPr=RichTextProperties(), p=[Paragraph(
        pPr=ParagraphProperties(defRPr=cp), r=[RegularTextRun(rPr=cp, t=text)])])), overlay=False)


def axis_title(text):
    return chart_title(text, size=900)


def add_oi_chart(ws, name, found, n_rows, base_year, measure='oi', title=None):
    """One line per contract; blanks are gaps, so each line spans only its own data.  Clean look:
    no gridlines, no borders, grey hairline axes, dark grey text, legend along the bottom."""
    n_series = len(found)
    ch = LineChart()
    ch.title = chart_title(title or CHART_TITLE[measure].format(name=name))
    ch.display_blanks = 'gap'
    ch.x_axis = DateAxis(crossAx=100)          # axId 500; the value axis must cross it
    ch.x_axis.number_format = 'mmm-yy'
    ch.x_axis.majorTimeUnit = 'months'
    ch.y_axis.crossAx = 500
    style_axes(ch, measure)
    ch.legend.position = 'b'
    ch.legend.txPr = chart_text(800)
    ch.width, ch.height = 34, 17               # cm
    last_row = 2 + n_rows
    ch.add_data(Reference(ws, min_col=2, max_col=1 + n_series, min_row=2, max_row=last_row),
                titles_from_data=True)          # row 2 = the 'Jan 24' labels
    ch.set_categories(Reference(ws, min_col=1, min_row=3, max_row=last_row))
    for s, c in zip(ch.series, found):
        s.marker.symbol = 'none'
        s.smooth = False
        s.graphicalProperties.line.width = 12700   # EMU: 1 pt
        s.graphicalProperties.line.solidFill = series_color(c.year, c.month, base_year)
    ws.add_chart(ch, '%s2' % get_column_letter(n_series + 4))   # after the Total column


def style_axes(ch, measure):
    """The shared clean look: no gridlines, grey hairline axes, grey text, no borders."""
    ch.y_axis.delete = False
    ch.x_axis.delete = False
    ch.y_axis.title = axis_title(Y_AXIS_TITLE[measure])
    ch.y_axis.number_format = Y_NUMBER_FORMAT[measure]
    ch.y_axis.majorGridlines = None
    ch.x_axis.majorGridlines = None
    for ax in (ch.x_axis, ch.y_axis):
        ax.txPr = chart_text(900)
        ax.graphicalProperties = GraphicalProperties(ln=LineProperties(solidFill=CHART_LINE, w=6350))
        ax.majorTickMark = 'out'
        ax.minorTickMark = 'none'
    ch.x_axis.tickLblPos = 'low'
    ch.graphical_properties = GraphicalProperties(ln=LineProperties(noFill=True))   # no chart border
    ch.plot_area.graphicalProperties = GraphicalProperties(noFill=True, ln=LineProperties(noFill=True))


def point_label(idx, show_name=False, show_value=False, num_fmt=None, pos='ctr', size=700, boxed=True):
    """A data label on one point of a series (all other points stay unlabelled)."""
    lbl = DataLabel(idx=idx, showSerName=show_name, showVal=show_value, showCatName=False, showLegendKey=False,
                    showPercent=False, showBubbleSize=False, dLblPos=pos,
                    txPr=chart_text(size, bold=True))
    if num_fmt:
        lbl.numFmt = num_fmt
    if boxed:                                  # white box with a grey hairline, so it reads over the bands
        lbl.spPr = GraphicalProperties(solidFill='FFFFFF', ln=LineProperties(solidFill=CHART_LINE, w=6350))
    return lbl


def series_labels(labels):
    """dLbls for a series: only the listed points carry a label."""
    return DataLabelList(dLbl=labels, showSerName=False, showVal=False, showCatName=False, showLegendKey=False,
                         showPercent=False, showBubbleSize=False)


def add_stacked_chart(ws, name, series, dates, last_year, measure='oi', title=None):
    """Stacked daily columns, one band per contract in expiry order (earliest at the bottom), no gap
    between days, so the top of the stack is the product total; a black Total line (column after
    the contracts) traces it and carries the last value.  A contract alive on the last date is
    named in a small box at the end of its band; another band tall enough is named at its peak;
    the legend on the right (in stack order) covers the rest."""
    n_series, n_rows = len(series), len(dates)
    last_row = 2 + n_rows
    total_col = n_series + 2
    ch = BarChart()
    ch.type = 'col'
    ch.grouping = 'stacked'
    ch.overlap = 100
    ch.gapWidth = 0
    ch.title = chart_title(title or CHART_TITLE[measure].format(name=name))
    ch.display_blanks = 'gap'
    style_axes(ch, measure)
    ch.x_axis.number_format = 'mmm-yy'
    skip = max(1, n_rows // 12)                # about 12 date labels along the axis
    ch.x_axis.tickLblSkip = skip
    ch.x_axis.tickMarkSkip = skip
    ch.x_axis.noMultiLvlLbl = True
    ch.legend.position = 'r'
    ch.legend.txPr = chart_text(750)
    ch.width, ch.height = 36, 18               # cm
    ch.add_data(Reference(ws, min_col=2, max_col=1 + n_series, min_row=2, max_row=last_row),
                titles_from_data=True)          # row 2 = the 'Jan 24' labels
    ch.set_categories(Reference(ws, min_col=1, min_row=3, max_row=last_row))
    labels, _ = band_labels(series, dates)
    for s, (c, rows), (mode, k, _h, _b) in zip(ch.series, series, labels):
        s.graphicalProperties.solidFill = stack_color(c.year, c.month, last_year)
        s.graphicalProperties.line.noFill = True
        if mode is not None:                   # alive on the last date -> named there; tall -> named at its peak
            s.dLbls = series_labels([point_label(k, show_name=True)])
    ln = LineChart()                           # the total, on the same axes (same axis ids)
    ln.add_data(Reference(ws, min_col=total_col, max_col=total_col, min_row=2, max_row=last_row), titles_from_data=True)
    ln.set_categories(Reference(ws, min_col=1, min_row=3, max_row=last_row))
    ln.display_blanks = 'gap'
    t = ln.series[0]
    t.marker.symbol = 'none'
    t.smooth = False
    t.graphicalProperties.line.solidFill = TOTAL_COLOR
    t.graphicalProperties.line.width = 12700   # 1 pt
    t.dLbls = series_labels([point_label(n_rows - 1, show_name=True, show_value=True,
                                         num_fmt=Y_NUMBER_FORMAT[measure], pos='t', size=800)])
    ch += ln
    ws.add_chart(ch, '%s2' % get_column_letter(total_col + 2))


def write_product_sheet(wb, name, contracts, base_year, measure='oi', kind=None):
    """Row 1 tickers, row 2 labels, then one row per date; the cells are the USD notional (or the
    OI when measure == 'oi' or the notional is unavailable), then a Total column.
    Returns (sheet, measure used, note)."""
    kind = CHART_KIND if kind is None else kind
    ws = wb.create_sheet(title=safe_sheet_name(name))
    used, series, dates, note = product_series(contracts, measure)
    found = [c for c, _ in series]
    ws['A1'] = 'Ticker'
    ws['A2'] = 'Date'
    ws.column_dimensions['A'].width = 12
    if not found:
        ws['B1'] = 'No contract returned open-interest data - see the %s tab' % AUDIT_SHEET
        return ws, used, note
    for j, c in enumerate(found, start=2):
        ws.cell(row=1, column=j, value=c.ticker)
        ws.cell(row=2, column=j, value=c.label)
    total_col = len(found) + 2
    ws.cell(row=1, column=total_col, value=TOTAL_LABEL)
    ws.cell(row=2, column=total_col, value=TOTAL_LABEL)
    lookups = [dict(rows) for _, rows in series]
    for i, d in enumerate(dates, start=3):
        ws.cell(row=i, column=1, value=d).number_format = 'yyyy-mm-dd'
        total = 0.0
        for j, lk in enumerate(lookups, start=2):
            v = lk.get(d)
            if v is not None:                       # a missing print stays an empty cell
                ws.cell(row=i, column=j, value=v).number_format = '#,##0'
                total += v
        ws.cell(row=i, column=total_col, value=total).number_format = '#,##0'
    ws.freeze_panes = 'B3'
    title = FALLBACK_TITLE.format(name=name) if (measure == 'notional' and used == 'oi') else None
    if kind == 'stacked':
        add_stacked_chart(ws, name, series, dates, max(c.year for c in found), used, title)
    else:
        add_oi_chart(ws, name, found, len(dates), base_year, used, title)
    return ws, used, note


def audit_row(c):
    return [c.product, c.label, c.ticker_1, c.ticker_2, c.ticker or None, c.status,
            c.last_trade, c.fut_month_yr or None, c.name or None, c.req_start, c.req_end,
            c.first_dt, c.last_dt, (len(c.rows) if c.status in (OK, NO_DATA) else None),
            c.last_oi, c.max_oi, c.multiplier, c.currency or None, c.last_notional, c.max_notional,
            c.note or None]


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
    for j, w in enumerate([10, 9, 15, 15, 15, 11, 18, 13, 26, 13, 13, 13, 13, 7, 10, 10, 10, 6, 18, 18, 60], start=1):
        ws.column_dimensions[get_column_letter(j)].width = w
    return ws


def index_row(ix):
    return [ix.product, ix.ticker, ix.name or None, ix.currency or None, ix.fut_currency or None,
            ix.ccy_source or None, ix.bbg_fut_currency or None,
            ix.fx_ticker or None, ix.status, ix.req_start, ix.req_end, ix.first_dt, ix.last_dt,
            (len(ix.rows) if ix.status in (OK, NO_DATA) else None), ix.last_index, ix.last_fx, ix.last_usd,
            ix.note or None]


def write_indices_sheet(wb, indices):
    ws = wb.create_sheet(title=INDEX_SHEET)
    for j, h in enumerate(INDEX_COLUMNS, start=1):
        ws.cell(row=1, column=j, value=h)
    for r, ix in enumerate(indices.values(), start=2):
        for j, v in enumerate(index_row(ix), start=1):
            if v is None:
                continue
            cell = ws.cell(row=r, column=j, value=v)
            if isinstance(v, dt.date):
                cell.number_format = 'yyyy-mm-dd'
            elif isinstance(v, float):
                cell.number_format = '#,##0.00'
    ws.freeze_panes = 'A2'
    for j, w in enumerate([10, 16, 30, 9, 10, 18, 12, 16, 11, 13, 13, 13, 13, 7, 12, 10, 14, 70], start=1):
        ws.column_dimensions[get_column_letter(j)].width = w
    return ws


def write_workbook(path, results, base_year=None, indices=None, measure=None, kind=None):
    """measure: 'notional' (default MEASURE) or 'oi'; kind: 'stacked' (default CHART_KIND) or
    'lines'.  indices: {tab name: IndexSeries} for the Indices audit tab (None -> no tab).
    Returns {tab name: (measure used, note)}."""
    measure = MEASURE if measure is None else measure
    kind = CHART_KIND if kind is None else kind
    if base_year is None:
        base_year = min([c.year for _, cs in results for c in cs] or [START_YEAR])
    wb = Workbook()
    wb.remove(wb.active)
    used = {}
    for name, cs in results:
        _, m, note = write_product_sheet(wb, name, cs, base_year, measure, kind)
        used[name] = (m, note)
    write_contracts_sheet(wb, results)
    if indices is not None:
        write_indices_sheet(wb, indices)
    wb.save(path)
    return used


# ------------------------------------------------------- notebook charts ---
LABEL_MIN_HEIGHT = 0.04      # a band gets a label inside it at its peak when it is at least this share of the axis there
LABEL_BOX = (0.05, 0.035)    # width, height of one in-band label as a share of the plot: two labels closer than this collide


def band_labels(series, dates):
    """Which point of each band carries its name: ('last', idx) for a band alive on the last date;
    ('peak', idx) for another band, at the tallest day of the band where a label fits - tall
    enough (LABEL_MIN_HEIGHT of the plot) and not on top of a label already placed (LABEL_BOX);
    None when no day qualifies (legend only).
    Returns ([(mode, idx, band height at idx, bottom of the band at idx)] in series order, totals)."""
    pos = {d: i for i, d in enumerate(dates)}
    n = len(dates)
    bottom = [0.0] * n
    bands = []                                 # (values, bottoms) per band
    for _, rows in series:
        y = [0.0] * n
        for d, v in rows:
            y[pos[d]] = v
        bands.append((y, list(bottom)))
        bottom = [b + v for b, v in zip(bottom, y)]
    top = max(bottom) if bottom else 1.0
    placed = []                                # (x, y) of the peak labels kept, as shares of the plot
    out = []
    for (_, rows), (y, base) in zip(series, bands):
        if rows[-1][0] == dates[-1]:
            k = n - 1
            out.append(('last', k, y[k], base[k]))
            continue
        chosen = None
        for k in sorted((i for i in range(n) if y[i] > 0), key=lambda i: -y[i]):
            if y[k] < LABEL_MIN_HEIGHT * top:
                break                          # everything after is shorter still
            x, yc = k / max(1, n - 1), (base[k] + y[k] / 2.0) / top
            if not any(abs(x - px) < LABEL_BOX[0] and abs(yc - py) < LABEL_BOX[1] for px, py in placed):
                chosen = k
                placed.append((x, yc))
                break
        if chosen is None:
            k = max(range(n), key=lambda i: y[i])
            out.append((None, k, y[k], base[k]))
        else:
            out.append(('peak', chosen, y[chosen], base[chosen]))
    return out, bottom


def stacked_axes(ax, series, dates, last_year, used):
    """Draw the stack on a matplotlib axes: one column per contract-day (no weekend gaps - the
    x axis is the trading-day index), the black Total line, in-band labels for tall bands, leader-
    line labels in the right margin for the contracts alive on the last date, the total at the
    end, and a small legend for everything.  Returns the number of labels placed."""
    import matplotlib.dates as mdates
    import numpy as np
    n = len(dates)
    x = np.arange(n)
    pos = {d: i for i, d in enumerate(dates)}
    labels, totals = band_labels(series, dates)
    bottom = np.zeros(n)
    top = max(totals) if totals else 1.0
    ax.set_ylim(0, top * 1.12)
    ax.set_xlim(-0.5, n - 0.5 + n * 0.09)
    placed = 0
    right = []                                 # (y anchor, label, colour) for the right-margin labels
    for (c, rows), (mode, k, h, b) in zip(series, labels):
        y = np.zeros(n)
        for d, v in rows:
            y[pos[d]] = v
        colour = '#' + stack_color(c.year, c.month, last_year)
        ax.bar(x, y, bottom=bottom, width=1.0, color=colour, linewidth=0, align='center', label=c.label)
        bottom = bottom + y
        if mode == 'last':
            right.append((b + h / 2.0, c.label, colour))
        elif mode == 'peak':
            ax.text(k, b + h / 2.0, c.label, fontsize=6.5, color='#' + CHART_TEXT, ha='center', va='center',
                    bbox=dict(boxstyle='square,pad=0.25', fc='white', ec=colour, lw=0.6, alpha=0.95))
            placed += 1
    ax.plot(x, totals, color='#' + TOTAL_COLOR, linewidth=0.9, label=TOTAL_LABEL)
    # right-margin labels, bottom-up, each at least a step above the previous one
    gap = top * 1.12 * 0.032
    y_prev = -gap
    x_text = n - 1 + n * 0.02
    for y_anchor, label, colour in sorted(right):
        y_text = max(y_anchor, y_prev + gap)
        y_prev = y_text
        ax.annotate(label, xy=(n - 0.5, y_anchor), xytext=(x_text, y_text), fontsize=6.5, color='#' + CHART_TEXT,
                    ha='left', va='center',
                    bbox=dict(boxstyle='square,pad=0.25', fc='white', ec=colour, lw=0.6),
                    arrowprops=dict(arrowstyle='-', color=colour, lw=0.6, shrinkA=0, shrinkB=0))
        placed += 1
    last_total = float(totals[-1])
    value = (format(int(round(last_total / 1e6)), ',') + 'm') if used == 'notional' else format(int(round(last_total)), ',')
    ax.annotate('%s %s' % (TOTAL_LABEL, value), xy=(n - 1, last_total), xytext=(x_text, max(y_prev + gap, last_total + gap)),
                fontsize=7.5, fontweight='bold', color='#' + TOTAL_COLOR, ha='left', va='center',
                bbox=dict(boxstyle='square,pad=0.25', fc='white', ec='#' + TOTAL_COLOR, lw=0.6),
                arrowprops=dict(arrowstyle='-', color='#' + TOTAL_COLOR, lw=0.6, shrinkA=0, shrinkB=0))
    step = max(1, n // 12)                     # about 12 date ticks
    ticks = list(range(0, n, step))
    ax.set_xticks(ticks)
    ax.set_xticklabels([dates[i].strftime('%b-%y') for i in ticks])
    return placed + 1


def show_charts(results, base_year=None, measure=None, kind=None):
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
    measure = MEASURE if measure is None else measure
    kind = CHART_KIND if kind is None else kind
    n_fig = 0
    for name, cs in results:
        used, series, dates, note = product_series(cs, measure)
        if not series:
            continue
        fig, ax = plt.subplots(figsize=(14, 7.5))
        if kind == 'stacked':
            stacked_axes(ax, series, dates, max(c.year for c, _ in series), used)
        else:
            for c, rows in series:
                ax.plot([d for d, _ in rows], [v for _, v in rows], linewidth=1.1,
                        color='#' + series_color(c.year, c.month, base_year), label=c.label)
        title = FALLBACK_TITLE if (measure == 'notional' and used == 'oi') else CHART_TITLE[used]
        ax.set_title(title.format(name=name), fontweight='bold', color='#' + CHART_TEXT)
        ax.set_ylabel(Y_AXIS_TITLE[used], color='#' + CHART_TEXT)
        if kind != 'stacked':
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b-%y'))
        if used == 'notional':
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos: format(int(round(v / 1e6)), ',') + 'm'))
        else:
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos: format(int(v), ',')))
        ax.grid(False)
        ax.tick_params(colors='#' + CHART_TEXT, labelsize=8)
        for side in ('top', 'right'):
            ax.spines[side].set_visible(False)
        for side in ('left', 'bottom'):
            ax.spines[side].set_color('#' + CHART_LINE)
        fig.autofmt_xdate()
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=13, fontsize=6.5,
                  frameon=False, handlelength=1.4, columnspacing=1.0)
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


def worked_example(contracts, ix):
    """'check: Sep 26 on 2026-09-17: 312,000 x 250000 x 412.50 / 1352.10 = USD 23,801m' - the
    latest notional print of the product, rebuilt from its parts so it can be checked by eye."""
    latest = [c for c in contracts if c.notional]
    if not latest:
        return 'check: no notional computed'
    c = max(latest, key=lambda c: (c.notional[-1][0], c.max_notional))
    d, usd = c.notional[-1]
    oi = dict(c.rows)[d]
    i = bisect.bisect_right([x for x, _ in ix.index_rows], d) - 1
    level = ix.index_rows[i][1]
    if ix.fx_ticker:
        k = bisect.bisect_right([x for x, _ in ix.fx_rows], d) - 1
        rate = ix.fx_rows[k][1]
        fx = ' %s %.4f (%s)' % ('x' if ix.fx_mode == 'multiply' else '/', rate, ix.fx_ticker.split()[0])
    else:
        fx = ' (USD-denominated, no FX)'
    return 'check: %s on %s: %s x %g x %.2f%s = USD %sm' % (
        c.label, d.isoformat(), format(int(oi), ','), c.multiplier, level, fx, format(int(round(usd / 1e6)), ','))


def print_summary(results, bbg, out, indices=None, used=None):
    print()
    for name, cs in results:
        n_ok = sum(1 for c in cs if c.status == OK)
        m, note = (used or {}).get(name, (None, ''))
        shown = {'notional': 'USD notional', 'oi': 'OI in contracts'}.get(m, '')
        print('%-8s %2d/%d contracts with data%s' % (name, n_ok, len(cs), (' - showing ' + shown) if shown else ''))
        if note:
            print('         %s' % note)
        for status in (NOT_FOUND, NO_DATA, NOT_PULLED):
            labels = [c.label for c in cs if c.status == status]
            if labels:
                print('         %-11s %s' % (status + ':', ', '.join(labels)))
        ix = (indices or {}).get(name)
        if ix is not None:
            mult = sorted({c.multiplier for c in cs if c.status == OK and c.multiplier is not None})
            if ix.status == OK:
                print('         notional:   OI x %s x %s (%d rows)%s   [contract ccy %s from %s]' % (
                    ' / '.join('%g' % m for m in mult) if mult else '%s ?' % MULTIPLIER_FIELD, ix.ticker,
                    len(ix.rows), (' / %s' % ix.fx_ticker) if ix.fx_ticker else ' (USD-denominated, no FX)',
                    ix.fut_currency, ix.ccy_source))
                if ix.note:
                    print('         WARNING:    %s' % ix.note)
                print('         %s' % worked_example(cs, ix))
            else:
                print('         index:      %s %s%s' % (ix.ticker, ix.status, (' - ' + ix.note) if ix.note else ''))
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
        host=BBG_HOST, port=BBG_PORT, skip_months=None, measure=None, kind=None):
    """Resolve every contract, pull its open interest, write the workbook; returns the path.

    Every argument defaults to the CONFIG value at the top of the file.
    """
    products = list(PRODUCTS if products is None else products)
    start_year = START_YEAR if start_year is None else start_year
    end_year = END_YEAR if end_year is None else end_year
    years_back_n = YEARS_BACK if years_back_n is None else years_back_n
    skip_months = SKIP_MONTHS if skip_months is None else skip_months
    measure = MEASURE if measure is None else measure
    if measure not in ('notional', 'oi'):
        raise ValueError("measure must be 'notional' or 'oi', not %r" % (measure,))
    kind = CHART_KIND if kind is None else kind
    if kind not in ('stacked', 'lines'):
        raise ValueError("kind must be 'stacked' or 'lines', not %r" % (kind,))
    tickers_only = TICKERS_ONLY if tickers_only is None else tickers_only
    if show_charts_ is None:
        show_charts_ = SHOW_CHARTS and in_ipython()
    today = today or dt.date.today()
    months = contract_months(start_year, end_year)
    out = output_path(out, today)
    print('OI charts | %d products | contracts %s .. %s | %d years back per contract | '
          'last %d month(s) before expiry dropped | %s | today %s'
          % (len(products), month_label(*months[0]), month_label(*months[-1]), years_back_n,
             skip_months, 'USD notional' if measure == 'notional' else 'OI in contracts', today.isoformat()))
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
        indices = None
        if measure == 'notional':
            try:
                indices = resolve_indices(bbg, results)
            except Exception as e:
                raise StepError('resolving the index tickers', e)
        if tickers_only:
            print_contract_table(results)
            print_summary(results, bbg, None, indices)
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
                    fetch_open_interest(bbg, c, years_back_n, today, skip_months)
                    print('.', end='', flush=True)
                except Exception as e:                 # keep what we have, say where it stopped
                    pull_error = (c, e)
                    c.status, c.note = NOT_PULLED, 'the pull failed here: %s' % e
                    print(' x', flush=True)
            ix = (indices or {}).get(name)
            if ix is not None and ix.status == OK:
                if pull_error is not None:
                    ix.status, ix.note = NOT_PULLED, 'not requested - the pull stopped at %s' % pull_error[0].ticker
                else:
                    try:
                        fetch_index(bbg, ix, cs, today)
                        print(' + %s' % ix.ticker, end='', flush=True)
                    except Exception as e:
                        pull_error = (ix, e)
                        ix.status, ix.note = NOT_PULLED, 'the pull failed here: %s' % e
                        print(' x', flush=True)
            if indices is not None:
                compute_notional(cs, ix)
            if pull_error is None:
                print()
    finally:
        bbg.close()
    try:
        used = write_workbook(out, results, base_year=start_year, indices=indices, measure=measure, kind=kind)
    except Exception as e:
        raise StepError('writing the workbook %s' % out, e)
    print_summary(results, bbg, out, indices, used)
    if show_charts_:
        try:
            show_charts(results, base_year=start_year, measure=measure, kind=kind)
        except Exception as e:
            raise StepError('drawing the charts (the workbook is already written: %s)' % out, e)
    if pull_error is not None:
        c, e = pull_error
        n_done = sum(1 for _, cs in results for x in cs if x.status in (OK, NO_DATA))
        n_all = n_done + sum(1 for _, cs in results for x in cs if x.status == NOT_PULLED)
        field = INDEX_FIELD if isinstance(c, IndexSeries) else HIST_FIELD
        raise StepError('pulling %s for %s (%s %s)' % (field, c.ticker, c.product, c.label), e,
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
    p.add_argument('--skip-months', type=int, default=SKIP_MONTHS,
                   help='drop the contract month and the months before it from each history (default %(default)s)')
    p.add_argument('--measure', choices=('notional', 'oi'), default=MEASURE,
                   help='what is plotted: USD notional or contracts (default %(default)s)')
    p.add_argument('--chart', choices=('stacked', 'lines'), default=CHART_KIND,
                   help='stacked columns with a total, or one line per contract (default %(default)s)')
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
            out=a.out, today=today, tickers_only=a.tickers_only, show_charts_=False,
            skip_months=a.skip_months, measure=a.measure, kind=a.chart)
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
FAKE_KRW_PRODUCTS = [('KM', 'KOSPI2')]        # a KRW product with a big multiplier, for the USD check
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
    for root, _ in FAKE_PRODUCTS + FAKE_KRW_PRODUCTS:
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
# the underlying indices (kind 'index', with a currency) and their USD rates (kind 'fx')
FAKE_INDICES = {'HSI Index': 'HKD', 'AS51 Index': 'AUD', 'SIMSCI Index': 'SGD', 'KOSPI2 Index': 'KRW'}
FAKE_FUT = {'HI': ('HKD', 50.0), 'XP': ('AUD', 25.0), 'QZ': ('USD', 100.0), 'NF': ('USD', 1.0),
            'KM': ('USD', 250000.0)}   # root -> (CRNCY as Bloomberg reports it, FUT_VAL_PT); KM says USD like the real terminal
FAKE_FX = ['USDHKD Curncy', 'USDAUD Curncy', 'USDSGD Curncy', 'USDKRW Curncy']
FAKE_LEVELS = {'HSI Index': 20000.0, 'AS51 Index': 8000.0, 'SIMSCI Index': 350.0, 'KOSPI2 Index': 400.0,
               'USDHKD Curncy': 7.8, 'USDAUD Curncy': 1.5, 'USDSGD Curncy': 1.35, 'USDKRW Curncy': 1350.0}
for _t, _ccy in FAKE_INDICES.items():
    UNIVERSE[_t] = dict(kind='index', currency=_ccy, year=2099, month=12,
                        listing=dt.date(2015, 1, 1), last_trade=dt.date(2099, 12, 31))
for _t in FAKE_FX:
    UNIVERSE[_t] = dict(kind='fx', year=2099, month=12, listing=dt.date(2015, 1, 1), last_trade=dt.date(2099, 12, 31))
TICKER_ID = {t: i for i, t in enumerate(sorted(UNIVERSE))}


def fake_oi(ticker, d):
    """Deterministic, distinct per ticker, rising with time - a misaligned cell cannot match.
    FX rates are small numbers (7.7 .. 7.8) that move every day."""
    s = UNIVERSE[ticker]
    days = (d - s['listing']).days
    if s.get('kind') == 'fx':                         # realistic rate, moves every day
        base = FAKE_LEVELS[ticker]
        return base * (1 + (days % 10) * 0.001)
    if s.get('kind') == 'index':                      # realistic level, drifts up, wobbles
        return FAKE_LEVELS[ticker] * (1 + days / 5000.0 + (days % 7) * 0.002)
    return float(TICKER_ID[ticker] * 100000 + days * 3 + 100)


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
        if s.get('kind') in ('index', 'fx'):        # an index / FX rate: NAME, CRNCY, no futures fields
            known = {'NAME': 'FAKE %s' % sec}
            if s['kind'] == 'index':
                known['CRNCY'] = s['currency']
            refusal = ('NOT_APPLICABLE_TO_REF_DATA', 'Field not applicable to security')
        elif s.get('not_future'):                   # a ticker that exists but is not a future
            known = {'NAME': 'FAKE %s SOMETHING ELSE' % sec.split()[0]}
            refusal = ('NOT_APPLICABLE_TO_REF_DATA', 'Field not applicable to security')
        else:
            ccy, mult = FAKE_FUT[sec[:2]]
            known = {'LAST_TRADEABLE_DT': s['last_trade'],
                     'FUT_MONTH_YR': '%s %02d' % (mon.upper(), s['year'] % 100),
                     'NAME': 'FAKE %s FUT %s%02d' % (sec.split()[0], mon, s['year'] % 100),
                     'CRNCY': ccy, 'FUT_VAL_PT': mult}
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
    check('month_end', month_end(2024, 2) == dt.date(2024, 2, 29) and month_end(2025, 12) == dt.date(2025, 12, 31))
    check('history_cutoff: Jun 24 -> 30 Apr 24, Jan 26 -> 30 Nov 25, 0 -> no cutoff',
          history_cutoff(2024, 6, 2) == dt.date(2024, 4, 30) and history_cutoff(2026, 1, 2) == dt.date(2025, 11, 30)
          and history_cutoff(2024, 6, 0) is None)
    check('CONFIG: 3 years back, last 2 months dropped, USD notional; KOSPI2 / HSI / AS51 / TWSE not listed as USD contracts',
          YEARS_BACK == 3 and SKIP_MONTHS == 2 and MEASURE == 'notional'
          and not {'KOSPI2', 'HSI', 'HSCEI', 'HSTECH', 'AS51', 'TWSE'} & set(CONTRACT_CURRENCY))
    check('as_float', as_float(50) == 50.0 and as_float('12.5') == 12.5 and as_float(None) is None
          and as_float(float('nan')) is None and as_float(0) is None and as_float('n.a.') is None)
    check('index ticker: <tab> Index by default, INDEX_TICKERS for the exceptions',
          index_ticker('KOSPI2') == 'KOSPI2 Index' and index_ticker('FPO') == 'XIN9I Index')
    try:
        fx_for('')
        empty = 'no error'
    except ValueError as e:
        empty = str(e)
    check('fx_for: USDxxx / divide, USD -> no conversion, empty currency refused',
          fx_for('KRW') == ('USDKRW Curncy', 'divide') and fx_for('USD') == ('', 'divide') and 'no currency' in empty, empty)
    global FX_OVERRIDES
    saved = FX_OVERRIDES
    FX_OVERRIDES = {'AUD': ('AUDUSD Curncy', 'multiply')}
    try:
        ov = fx_for('aud')
    finally:
        FX_OVERRIDES = saved
    check('fx_for: override', ov == ('AUDUSD Curncy', 'multiply'), ov)
    d0, d1, d2, d3 = (dt.date(2024, 1, k) for k in (1, 2, 3, 4))
    check('to_usd: divide, FX carried forward, days before the first FX print dropped, multiply, USD index as is',
          to_usd([(d1, 100.0), (d2, 200.0)], [(d0, 2.0)]) == [(d1, 50.0), (d2, 100.0)]
          and to_usd([(d0, 100.0), (d2, 200.0)], [(d1, 4.0), (d3, 8.0)]) == [(d2, 50.0)]
          and to_usd([(d1, 100.0)], [(d1, 0.5)], 'multiply') == [(d1, 50.0)]
          and to_usd([(d1, 100.0)], []) == [(d1, 100.0)])
    ix = IndexSeries(product='KOSPI2', ticker='KOSPI2 Index', status=OK, rows=[(d1, 10.0), (d3, 20.0)])
    c = Contract(product='KOSPI2', root='KM', year=2024, month=1, label='Jan 24', ticker_1='a', ticker_2='b',
                 ticker='a', status=OK, multiplier=250000.0, rows=[(d0, 3.0), (d1, 4.0), (d2, 5.0), (d3, 6.0)])
    compute_notional([c], ix)
    check('compute_notional: OI x FUT_VAL_PT x index (carried forward), no notional before the first index print',
          c.notional == [(d1, 4 * 250000 * 10.0), (d2, 5 * 250000 * 10.0), (d3, 6 * 250000 * 20.0)]
          and '1 OI day(s) before the first index print' in c.note, (c.notional, c.note))
    c.multiplier, c.note = None, ''
    compute_notional([c], ix)
    check('compute_notional: no multiplier -> no notional, note says so', c.notional == [] and 'FUT_VAL_PT missing' in c.note)
    c.multiplier, c.note = 1.0, ''
    compute_notional([c], IndexSeries(product='KOSPI2', ticker='KOSPI2 Index', note='KOSPI2 Index -> Unknown'))
    check('compute_notional: index NOT FOUND -> no notional, note carries the reason', c.notional == [] and 'Unknown' in c.note)
    used, series, dates, note = product_series([c], 'notional')
    check('product_series: notional unavailable -> falls back to OI with a note',
          used == 'oi' and series == [(c, c.rows)] and dates == [d0, d1, d2, d3] and note.startswith('USD notional unavailable'), note)
    used, series, dates, note = product_series([c], 'oi')
    check('product_series: oi', used == 'oi' and note == '')
    check('product_currency: the most common CRNCY of the resolved contracts',
          product_currency([Contract(product='x', root='x', year=1, month=1, label='', ticker_1='', ticker_2='',
                                     status=OK, currency=k) for k in ('HKD', 'HKD', 'USD')]) == 'HKD'
          and product_currency([]) == '')
    check('as_date datetime', as_date(dt.datetime(2026, 1, 28, 0, 0)) == dt.date(2026, 1, 28))
    check('as_date date', as_date(dt.date(2026, 1, 28)) == dt.date(2026, 1, 28))
    check('as_date text', as_date('2026-01-28T00:00:00') == dt.date(2026, 1, 28))
    check('as_date None / garbage', as_date(None) is None and as_date('n.a.') is None)
    text_row = fake_complex('fieldData', [('date', '2026-01-28'), ('OPEN_INT', 1.0)])
    dt_row = FakeElement('fieldData', children=[('date', FakeElement('date', dt.date(2026, 1, 28)))])
    dt_row.getElementAsString = lambda key: 'garbage'          # text form unusable -> datetime fallback
    check('row_date: text form first, datetime form as fallback',
          row_date(text_row) == dt.date(2026, 1, 28) and row_date(dt_row) == dt.date(2026, 1, 28))
    check('11 real products, distinct legal tab names',
          len({n for _, n in PRODUCTS}) == len(PRODUCTS) == 11
          and all(safe_sheet_name(n) == n for _, n in PRODUCTS))
    check('real roots match the request note (+ MTW added 18 Sep)',
          [p[0] for p in PRODUCTS] == ['HI', 'HC', 'HCT', 'KM', 'XP', 'FT', 'TWT', 'MTW', 'FPO', 'HJA', 'QZ'])
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
    check('FUT_MONTH_YR / NAME / CRNCY / FUT_VAL_PT captured',
          c.fut_month_yr == 'SEP 25' and c.name.startswith('FAKE HIU25') and c.currency == 'HKD' and c.multiplier == 50.0,
          (c.fut_month_yr, c.name, c.currency, c.multiplier))
    counts = [(n, sum(c.status == OK for c in cs)) for n, cs in results]
    check('resolution counts HSI 36 / AS51 12 / SIMSCI 35', counts == [('HSI', 36), ('AS51', 12), ('SIMSCI', 35)], counts)
    return bbg, results


def test_history(bbg, results):
    for _, cs in results:
        for c in cs:
            fetch_open_interest(bbg, c, 3, TEST_TODAY, 2)
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
        exp = (years_back(c.last_trade, 3).strftime('%Y%m%d'),
               min(c.last_trade, TEST_TODAY, history_cutoff(c.year, c.month, 2)).strftime('%Y%m%d'))
        got = (e['settings']['startDate'], e['settings']['endDate'])
        if got != exp:
            bad.append((c.ticker, got, exp))
    check('request window = [last trade - 3y, min(last trade, today, end of month-2)] as YYYYMMDD', not bad, bad[:3])
    c = by[('HSI', 'Jun 24')]
    check('Jun 24: no May 24 or Jun 24 rows, last row in Apr 24',
          c.req_end == dt.date(2024, 4, 30) and c.rows[-1][0] == last_session_on_or_before(dt.date(2024, 4, 30))
          and all((d.year, d.month) not in ((2024, 5), (2024, 6)) for d, _ in c.rows), (c.req_end, c.rows[-1]))
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
    check('Dec contract listed 3y out: starts at the 3-year window (listing is ~3y out, so on or after)',
          c.rows[0][0] >= first_session_on_or_after(c.req_start) and c.req_start == years_back(c.last_trade, 3),
          (c.rows[0], c.req_start))
    c = by[('HSI', 'Jun 25')]
    check('expired contract: ends at the end of the month two before expiry (30 Apr 25)',
          c.req_end == dt.date(2025, 4, 30) and c.rows[-1][0] == last_session_on_or_before(dt.date(2025, 4, 30)))
    c = by[('HSI', 'Dec 26')]
    check('live contract whose cutoff is after today: ends today', c.rows[-1][0] == last_session_on_or_before(TEST_TODAY))
    c = by[('HSI', 'Oct 26')]
    check('live contract whose cutoff is before today: ends 31 Aug 26',
          c.req_end == dt.date(2026, 8, 31) and c.rows[-1][0] == last_session_on_or_before(dt.date(2026, 8, 31)))
    c0 = Contract(**{k: getattr(by[('HSI', 'Jun 25')], k) for k in
                        ('product', 'root', 'year', 'month', 'label', 'ticker_1', 'ticker_2', 'ticker', 'status', 'last_trade')})
    fetch_open_interest(bbg, c0, 3, TEST_TODAY, 0)
    check('--skip-months 0: history runs to the last trade date, as before',
          c0.req_end == c0.last_trade and c0.rows[-1][0] == last_session_on_or_before(c0.last_trade))
    c3 = Contract(**{k: getattr(by[('HSI', 'Dec 25')], k) for k in
                        ('product', 'root', 'year', 'month', 'label', 'ticker_1', 'ticker_2', 'ticker', 'status', 'last_trade')})
    fetch_open_interest(bbg, c3, 4, TEST_TODAY)
    check('--years-back 4 widens the window', c3.req_start == years_back(c3.last_trade, 4)
          and bbg.session.log[-1]['settings']['startDate'] == c3.req_start.strftime('%Y%m%d'))
    return results


def test_workbook(results):
    by = {(n, c.label): c for n, cs in results for c in cs}
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, 'test_OI.xlsx')
    used = write_workbook(path, results, measure='oi', kind='lines')
    wb = load_workbook(path)
    check('tabs: products in order, then Contracts', wb.sheetnames == ['HSI', 'AS51', 'SIMSCI', AUDIT_SHEET], wb.sheetnames)
    check('write_workbook returns the measure used per tab', used == {n: ('oi', '') for n, _ in results}, used)
    with zipfile.ZipFile(path) as z:
        chart_xml = {n: z.read(n) for n in z.namelist() if n.startswith('xl/charts/chart')}
        sheet_xml = {n: z.read(n) for n in z.namelist() if n.startswith('xl/worksheets/sheet')}
    check('no empty <v></v> cells anywhere (the Excel "repair" trigger)',
          all(b'<v></v>' not in x and b'<v/>' not in x for x in sheet_xml.values()))
    check('one chart part per product tab', len(chart_xml) == 3, len(chart_xml))
    check('chart XML: gaps, date axis, no markers, straight lines, no gridlines, grey axes, no border',
          all(b'dispBlanksAs val="gap"' in x and b'<dateAx>' in x and b'symbol val="none"' in x
              and b'smooth val="0"' in x and b'majorGridlines' not in x and x.count(b'noFill') >= 2
              and x.count(b'srgbClr val="BFBFBF"') == 2 for x in chart_xml.values()))
    for name, cs in results:
        ws = wb[name]
        dates, found = align_product(cs)
        n, N = len(found), len(dates)
        check('%s: row 1 tickers, row 2 labels, expiry order' % name,
              [ws.cell(1, j).value for j in range(2, n + 2)] == [c.ticker for c in found]
              and [ws.cell(2, j).value for j in range(2, n + 2)] == [c.label for c in found]
              and ws['A1'].value == 'Ticker' and ws['A2'].value == 'Date')
        check('%s: Total column right after the %d found contracts, nothing beyond' % (name, n),
              ws.max_column == n + 2 and ws.cell(1, n + 2).value == TOTAL_LABEL and ws.cell(2, n + 2).value == TOTAL_LABEL,
              ws.max_column)
        sums_ok = all(abs((ws.cell(i, n + 2).value or 0) - sum((ws.cell(i, j).value or 0) for j in range(2, n + 2))) < 1e-6
                      for i in range(3, N + 3))
        check('%s: Total = sum of the contracts on each date' % name, sums_ok)
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
        check('%s: chart title and OI axis title, contracts number format' % name,
              title == CHART_TITLE['oi'].format(name=name) and ytitle == Y_AXIS_TITLE['oi']
              and ch.y_axis.number_format.formatCode == Y_NUMBER_FORMAT['oi'] and ch.y_axis.majorGridlines is None
              and ch.x_axis.txPr is not None and ch.legend.txPr is not None, (title, ytitle))
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
              ch.anchor._from.col == n + 3 and ch.anchor._from.row == 1, (ch.anchor._from.col, ch.anchor._from.row))
        check('%s: chart 34 x 17 cm' % name, ch.anchor.ext.cx == 12240000 and ch.anchor.ext.cy == 6120000,
              (ch.anchor.ext.cx, ch.anchor.ext.cy))
    ws = wb[AUDIT_SHEET]
    total = sum(len(cs) for _, cs in results)
    check('Contracts: header + one row per contract', ws.max_row == total + 1 and [c.value for c in ws[1]] == AUDIT_COLUMNS,
          (ws.max_row, total))
    rows = {(r[0], r[1]): r for r in ws.iter_rows(min_row=2, values_only=True)}
    r = rows[('SIMSCI', 'Feb 26')]
    check('Contracts: NOT FOUND row - no ticker, no window, no rows, a note',
          r[5] == NOT_FOUND and r[4] is None and r[9] is None and r[13] is None and r[16] is None and r[20], r)
    r = rows[('SIMSCI', 'Oct 26')]
    check('Contracts: NO DATA row - ticker, window, Rows == 0',
          r[5] == NO_DATA and r[4] == 'QZV6 Index' and r[9] is not None and r[13] == 0, r)
    c, r = by[('HSI', 'Sep 25')], rows[('HSI', 'Sep 25')]
    check('Contracts: OK row - both forms, ticker used, dates, rows, last and max OI',
          r[2] == 'HIU5 Index' and r[3] == 'HIU25 Index' and r[4] == c.ticker and r[5] == OK
          and r[6].date() == c.last_trade and r[7] == 'SEP 25' and r[9].date() == c.req_start
          and r[10].date() == c.req_end and r[11].date() == c.first_dt and r[12].date() == c.last_dt
          and r[13] == len(c.rows) and r[14] == c.last_oi and r[15] == c.max_oi
          and r[16] == 50.0 and r[17] == 'HKD' and r[18] is None and r[19] is None, r)
    check('Contracts: frozen header', ws.freeze_panes == 'A2')
    empty = [Contract(product='EMPTY', root='ZZ', year=2024, month=m, label=month_label(2024, m),
                        ticker_1='a', ticker_2='b') for m in range(1, 13)]
    p2 = os.path.join(tmp, 'empty.xlsx')
    write_workbook(p2, [('EMPTY', empty)], measure='oi', kind='lines')
    wb2 = load_workbook(p2)
    check('product with nothing found: note in the tab, no chart, no crash',
          wb2.sheetnames == ['EMPTY', AUDIT_SHEET] and len(wb2['EMPTY']._charts) == 0
          and 'No contract' in str(wb2['EMPTY']['B1'].value))
    for p in (path, p2):
        os.remove(p)
    os.rmdir(tmp)


def test_notional():
    global CONTRACT_CURRENCY
    saved_ccy = CONTRACT_CURRENCY
    CONTRACT_CURRENCY = {'SIMSCI': 'USD'}          # the fixture's one USD-denominated contract
    try:
        _test_notional()
    finally:
        CONTRACT_CURRENCY = saved_ccy


def _test_notional():
    global CONTRACT_CURRENCY
    bbg = Bloomberg(blpapi_module=FakeAPI).connect()
    results = resolve_contracts(bbg, FAKE_PRODUCTS, contract_months(2024, 2026), TEST_TODAY)
    for _, cs in results:
        for c in cs:
            fetch_open_interest(bbg, c, 3, TEST_TODAY)
    n0 = len(bbg.session.log)
    indices = resolve_indices(bbg, results)
    refs = [e for e in bbg.session.log[n0:] if e['op'] == 'ReferenceDataRequest']
    check('indices: one per product in order, one reference pass for CRNCY / NAME',
          list(indices) == ['HSI', 'AS51', 'SIMSCI'] and len(refs) == 1 and refs[0]['fields'] == INDEX_REF_FIELDS
          and sorted(refs[0]['securities']) == ['AS51 Index', 'HSI Index', 'SIMSCI Index'], refs)
    ix = indices['HSI']
    check('index resolved: contract ccy = the index CRNCY (HKD), FX pair from it, Bloomberg futures CRNCY agrees, OK',
          ix.status == OK and ix.currency == 'HKD' and ix.fut_currency == 'HKD' and ix.ccy_source == 'index CRNCY'
          and ix.bbg_fut_currency == 'HKD' and ix.fx_ticker == 'USDHKD Curncy' and ix.fx_mode == 'divide'
          and ix.name == 'FAKE HSI Index' and ix.note == '', ix)
    qz = indices['SIMSCI']
    check('CONTRACT_CURRENCY = USD: no FX, index used in points, source recorded',
          qz.status == OK and qz.currency == 'SGD' and qz.fut_currency == 'USD' and qz.ccy_source == 'CONTRACT_CURRENCY'
          and qz.fx_ticker == '', qz)
    kr = resolve_indices(bbg, resolve_contracts(bbg, FAKE_KRW_PRODUCTS, contract_months(2025, 2025), TEST_TODAY))['KOSPI2']
    check('KOSPI2: futures CRNCY says USD (as on the real terminal) but the index says KRW -> KRW used, USDKRW, warning',
          kr.status == OK and kr.bbg_fut_currency == 'USD' and kr.fut_currency == 'KRW' and kr.ccy_source == 'index CRNCY'
          and kr.fx_ticker == 'USDKRW Curncy' and 'says USD - ignored, KRW used' in kr.note, kr)
    nc = IndexSeries(product='X', ticker='X Index')
    saved = CONTRACT_CURRENCY
    try:
        CONTRACT_CURRENCY = {}
        ref_none = {'X Index': {'NAME': 'x'}}
        bbg2 = Bloomberg(blpapi_module=FakeAPI).connect()
        bbg2.ref = lambda secs, fields: ref_none
        nc = resolve_indices(bbg2, [('X', [])])['X']
    finally:
        CONTRACT_CURRENCY = saved
    check('index without CRNCY and no CONTRACT_CURRENCY entry -> NOT FOUND, never silently unconverted',
          nc.status == NOT_FOUND and 'contract currency is unknown' in nc.note, nc.note)
    check('no field errors on the index pass', not bbg.field_errors, bbg.field_errors)
    bad = resolve_indices(bbg, [('NOPE', [])])['NOPE']
    check('unknown index -> NOT FOUND with the reason', bad.status == NOT_FOUND and 'Unknown/Invalid' in bad.note, bad.note)
    for name, cs in results:
        fetch_index(bbg, indices[name], cs, TEST_TODAY)
        compute_notional(cs, indices[name])
    hist = [e for e in bbg.session.log[n0:] if e['op'] == 'HistoricalDataRequest']
    check('PX_LAST of the index, then of the FX rate (started 10 days earlier); none for the USD future',
          len(hist) == 5 and [e['securities'][0] for e in hist] == ['HSI Index', 'USDHKD Curncy', 'AS51 Index',
                                                                     'USDAUD Curncy', 'SIMSCI Index']
          and all(e['fields'] == [INDEX_FIELD] for e in hist)
          and hist[0]['settings']['startDate'] == ix.req_start.strftime('%Y%m%d')
          and hist[1]['settings']['startDate'] == (ix.req_start - dt.timedelta(days=10)).strftime('%Y%m%d')
          and hist[0]['settings']['endDate'] == hist[1]['settings']['endDate'] == ix.req_end.strftime('%Y%m%d'),
          [(e['securities'], e['settings']['startDate'], e['settings']['endDate']) for e in hist])
    cs = results[0][1]
    check('index window = earliest contract start .. latest contract end, capped at today',
          ix.req_start == min(c.req_start for c in cs if c.rows)
          and ix.req_end == min(max(c.req_end for c in cs if c.rows), TEST_TODAY) == TEST_TODAY, (ix.req_start, ix.req_end))
    fx = dict(ix.fx_rows)
    check('ix.rows: one per index day, points / same-day FX where the rate printed that day, sorted',
          ix.status == OK and len(ix.rows) == len(ix.index_rows) > 0 and ix.note == ''
          and all(abs(v - lvl / fx[d]) < 1e-9 for (d, v), (_, lvl) in zip(ix.rows, ix.index_rows) if d in fx)
          and all(a[0] < b[0] for a, b in zip(ix.rows, ix.rows[1:])), (len(ix.rows), len(ix.index_rows), ix.note))
    check('USD future: ix.rows == index points', qz.rows == qz.index_rows and qz.fx_rows == [])
    ok = [c for c in cs if c.status == OK and c.rows]
    lk = dict(ix.rows)
    check('HSI notional: every OI day, OI x 50 x (HSI / USDHKD) of that day, sorted',
          all(len(c.notional) == len(c.rows) and c.note in ('', 'both forms valid')
              and all(abs(nv - oi * 50.0 * lk[d]) < 1e-6 for (d, oi), (_, nv) in zip(c.rows, c.notional))
              for c in ok), [(c.label, len(c.rows), len(c.notional), c.note) for c in ok if len(c.notional) != len(c.rows)][:3])
    qz_ok = [c for c in results[2][1] if c.status == OK and c.rows]
    lk = dict(qz.rows)
    check('SIMSCI notional: OI x 100 x index points (no FX)',
          all(all(abs(nv - oi * 100.0 * lk[d]) < 1e-6 for (d, oi), (_, nv) in zip(c.rows, c.notional)) for c in qz_ok))
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, 'notional.xlsx')
    used = write_workbook(path, results, indices=indices)
    wb = load_workbook(path)
    check('tabs: products, Contracts, Indices; every tab shows the notional',
          wb.sheetnames == ['HSI', 'AS51', 'SIMSCI', AUDIT_SHEET, INDEX_SHEET] and used == {n: ('notional', '') for n, _ in results},
          (wb.sheetnames, used))
    with zipfile.ZipFile(path) as z:
        chart_xml = {n: z.read(n) for n in z.namelist() if n.startswith('xl/charts/chart')}
    for name, cs in results:
        ws = wb[name]
        _, series, dates, _ = product_series(cs, 'notional')
        n, N = len(series), len(dates)
        check('%s: one column per contract + Total, dates = union of notional dates' % name,
              ws.max_column == n + 2 and ws.max_row == N + 2
              and [ws.cell(1, j).value for j in range(2, n + 2)] == [c.ticker for c, _ in series], (ws.max_column, n))
        good, why = True, ''
        for j, (c, rows) in enumerate(series, start=2):
            lk = dict(rows)
            for i, d in enumerate(dates, start=3):
                v, exp = ws.cell(i, j).value, lk.get(d)
                if (exp is None) != (v is None) or (exp is not None and abs(v - exp) > 1e-9 * abs(exp)):
                    good, why = False, (c.ticker, d, v, exp)
                    break
            if not good:
                break
        check('%s: every cell is that contract\'s USD notional of that day, blank elsewhere' % name, good, why)
        ch = ws._charts[0]
        title = ch.title.tx.rich.p[0].r[0].t
        check('%s: stacked chart + total line, notional title, USD m axis format, no gridlines' % name,
              isinstance(ch, BarChart) and len(ch._charts) == 2 and len(ch.series) == n
              and title == CHART_TITLE['notional'].format(name=name)
              and ch.y_axis.title.tx.rich.p[0].r[0].t == Y_AXIS_TITLE['notional']
              and ch.y_axis.number_format.formatCode == Y_NUMBER_FORMAT['notional'] and ch.y_axis.majorGridlines is None
              and ch.anchor._from.col == n + 3, (title, ch.anchor._from.col))
    check('chart XML: one bar chart + one line chart on one category + one value axis, no gridlines, USD m format',
          all(x.count(b'<barChart>') == 1 and x.count(b'<lineChart>') == 1 and x.count(b'<catAx>') == 1
              and x.count(b'<valAx>') == 1 and b'majorGridlines' not in x and b'#,##0,,&quot;m&quot;' in x
              for x in chart_xml.values()) and len(chart_xml) == 3)
    ws = wb[AUDIT_SHEET]
    rows = {(r[0], r[1]): r for r in ws.iter_rows(min_row=2, values_only=True)}
    c, r = [x for x in results[0][1] if x.label == 'Sep 25'][0], rows[('HSI', 'Sep 25')]
    check('Contracts tab: multiplier, ccy, last and max notional',
          r[16] == 50.0 and r[17] == 'HKD' and abs(r[18] - c.last_notional) < 1e-6 and abs(r[19] - c.max_notional) < 1e-6, r[16:20])
    ws = wb[INDEX_SHEET]
    rows = {r[0]: r for r in ws.iter_rows(min_row=2, values_only=True)}
    r, ix = rows['HSI'], indices['HSI']
    check('Indices tab: header + one row per product, HSI row complete',
          [c.value for c in ws[1]] == INDEX_COLUMNS and ws.max_row == 4 and ws.freeze_panes == 'A2'
          and r[1] == 'HSI Index' and r[3] == 'HKD' and r[4] == 'HKD' and r[5] == 'index CRNCY' and r[6] == 'HKD'
          and r[7] == 'USDHKD Curncy' and r[8] == OK
          and r[9].date() == ix.req_start and r[10].date() == ix.req_end and r[11].date() == ix.first_dt
          and r[12].date() == ix.last_dt and r[13] == len(ix.rows) and abs(r[14] - ix.last_index) < 1e-6
          and abs(r[15] - ix.last_fx) < 1e-9 and abs(r[16] - ix.last_usd) < 1e-9, r)
    r = rows['SIMSCI']
    check('Indices tab: USD-denominated row - source CONTRACT_CURRENCY, no FX ticker / rate, index used as is',
          r[4] == 'USD' and r[5] == 'CONTRACT_CURRENCY' and r[7] is None and r[15] is None and r[16] == r[14], r)
    # one product without an index: that tab falls back to OI and says so
    indices2 = dict(indices)
    indices2['HSI'] = IndexSeries(product='HSI', ticker='XX Index', note='XX Index -> Unknown/Invalid Security')
    compute_notional(results[0][1], indices2['HSI'])
    path3 = os.path.join(tmp, 'partial.xlsx')
    used = write_workbook(path3, results, indices=indices2)
    wb3 = load_workbook(path3)
    t = wb3['HSI']._charts[0].title.tx.rich.p[0].r[0].t
    check('index NOT FOUND for one product: OI shown there with the fallback title, notional elsewhere',
          used['HSI'][0] == 'oi' and 'Unknown/Invalid' in used['HSI'][1] and used['AS51'] == ('notional', '')
          and t == FALLBACK_TITLE.format(name='HSI') and wb3['HSI'].max_column == 38
          and wb3['HSI']['B3'].value == dict(results[0][1][0].rows).get(wb3['HSI']['A3'].value.date()), (used, t))
    compute_notional(results[0][1], indices['HSI'])          # restore
    # a contract without a multiplier is left out of a notional tab, with a note
    c = results[0][1][5]
    saved = c.multiplier, c.notional, c.note
    c.multiplier, c.note = None, ''
    compute_notional(results[0][1], indices['HSI'])
    used, series, _, note = product_series(results[0][1], 'notional')
    check('contract without FUT_VAL_PT: left out of the notional tab, named in the note',
          used == 'notional' and len(series) == 35 and note == 'no notional for %s' % c.label, note)
    c.multiplier, c.notional, c.note = saved
    compute_notional(results[0][1], indices['HSI'])
    # run() end to end: notional by default, plain OI on request
    FakeSession.instances.clear()
    path4 = os.path.join(tmp, 'run.xlsx')
    out, text = quiet(run, products=FAKE_PRODUCTS, today=TEST_TODAY, blpapi_module=FakeAPI, out=path4)
    sess = FakeSession.instances[-1]
    wb4 = load_workbook(path4)
    check('run(): USD notional by default - index pulled per product, summary explains the formula, Indices tab',
          out == path4 and 'USD notional' in text and 'notional:   OI x 50 x HSI Index' in text and '/ USDHKD Curncy' in text
          and 'OI x 100 x SIMSCI Index' in text and '(USD-denominated, no FX)' in text and 'showing USD notional' in text
          and '[contract ccy HKD from index CRNCY]' in text and '[contract ccy USD from CONTRACT_CURRENCY]' in text
          and INDEX_SHEET in wb4.sheetnames
          and wb4['HSI']._charts[0].title.tx.rich.p[0].r[0].t == CHART_TITLE['notional'].format(name='HSI')
          and sum(1 for e in sess.log if e['op'] == 'HistoricalDataRequest') == 83 + 5, text[-900:])
    out, text = quiet(run, products=FAKE_PRODUCTS, today=TEST_TODAY, blpapi_module=FakeAPI, out=path4, measure='oi')
    wb5 = load_workbook(path4)
    check('run(measure="oi") / --measure oi: contracts, no index requests, no Indices tab',
          INDEX_SHEET not in wb5.sheetnames and 'showing OI in contracts' in text and 'notional:' not in text
          and wb5['HSI']._charts[0].title.tx.rich.p[0].r[0].t == CHART_TITLE['oi'].format(name='HSI'))
    try:
        run(products=FAKE_PRODUCTS, today=TEST_TODAY, blpapi_module=FakeAPI, out=path4, measure='usd')
        raised = ''
    except ValueError as e:
        raised = str(e)
    check('run(measure=?) is refused', "'notional' or 'oi'" in raised, raised)
    # ---- the USD check, on a KRW product with a realistic multiplier: KOSPI2 ----
    FakeSession.instances.clear()
    path5 = os.path.join(tmp, 'krw.xlsx')
    out, text = quiet(run, products=FAKE_KRW_PRODUCTS, today=TEST_TODAY, blpapi_module=FakeAPI, out=path5)
    sess = FakeSession.instances[-1]
    hist = [e for e in sess.log if e['op'] == 'HistoricalDataRequest']
    wb6 = load_workbook(path5)
    ws = wb6['KOSPI2']
    check('KOSPI2: KRW from the index, USDKRW pulled after the contracts, Bloomberg futures CRNCY=USD flagged and ignored',
          [e['securities'][0] for e in hist[-2:]] == ['KOSPI2 Index', 'USDKRW Curncy']
          and 'notional:   OI x 250000 x KOSPI2 Index' in text and '/ USDKRW Curncy' in text
          and '[contract ccy KRW from index CRNCY]' in text and 'WARNING:    Bloomberg CRNCY on the futures says USD' in text
          and 'no FX' not in text, text[-700:])
    # rebuild the expected value of one cell by hand from the fake prints
    i, j = 3, 2                                        # first date row, first contract column
    while ws.cell(i, j).value is None:
        i += 1
    d = ws.cell(i, 1).value.date()
    tk = ws.cell(1, j).value
    oi = fake_oi(tk, d)
    fx_d = d
    while not is_session(fx_d):
        fx_d -= DAY
    by_hand = oi * 250000.0 * fake_oi('KOSPI2 Index', d) / fake_oi('USDKRW Curncy', fx_d)
    krw = oi * 250000.0 * fake_oi('KOSPI2 Index', d)
    cell = ws.cell(i, j).value
    check('KOSPI2 cell = OI x 250,000 x KOSPI2 / USDKRW, by hand, and is ~1,350x smaller than the KRW amount',
          abs(cell - by_hand) < 1e-6 * by_hand and 1300 < krw / cell < 1400, (tk, d, oi, cell, by_hand, krw))
    ws = wb6[INDEX_SHEET]
    r = [x for x in ws.iter_rows(min_row=2, values_only=True)][0]
    check('KOSPI2 Indices row: index KRW, used KRW, Bloomberg futures USD, USDKRW Curncy, last index in USD = index / FX',
          r[3] == 'KRW' and r[4] == 'KRW' and r[5] == 'index CRNCY' and r[6] == 'USD' and r[7] == 'USDKRW Curncy'
          and r[8] == OK and 380 < r[14] < 900 and 1300 < r[15] < 1400 and abs(r[16] - r[14] / r[15]) < 1e-9
          and 'says USD - ignored' in r[17], r)
    check('KOSPI2 summary shows the worked example for the last day',
          'check:' in text and 'USDKRW' in text.split('check:')[1].split('\n')[0], text[-600:])
    if importlib.util.find_spec('matplotlib') is not None:
        import warnings
        import matplotlib.pyplot as plt
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            n_fig, _ = quiet(show_charts, results, kind='lines')
        fig = plt.figure(plt.get_fignums()[0])
        ax = fig.axes[0]
        ylab, title, n_lines, ticks = ax.get_ylabel(), ax.get_title(), len(ax.get_lines()), ax.get_yticklabels()
        grid = any(l.get_visible() for l in ax.get_ygridlines())
        plt.close('all')
        check('show_charts (lines): notional title and axis, USD m tick labels, no gridlines, one line per contract',
              n_fig == 3 and len(fig.axes) == 1 and ylab == Y_AXIS_TITLE['notional']
              and title == CHART_TITLE['notional'].format(name='HSI') and n_lines == 36 and not grid,
              (n_fig, ylab, title, n_lines, grid))
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)


def test_stacked():
    check('CONFIG: stacked columns by default', CHART_KIND == 'stacked')
    cols = [stack_color(2026, m, 2026) for m in range(1, 13)]
    check('stack_color: the 12 configured month colours for the newest year, older years faded to white, capped',
          cols == [MONTH_COLORS[m].lower() for m in range(1, 13)] and len(set(cols)) == 12
          and stack_color(2025, 12, 2026) == '506278' and stack_color(2024, 12, 2026) == '828e9e'
          and stack_color(2020, 12, 2026) == stack_color(2024, 12, 2026), cols)
    def sat(hexcol):
        r, g, b = (int(hexcol[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        mx, mn = max(r, g, b), min(r, g, b)
        return 0 if mx == 0 else (mx - mn) / mx
    check('MONTH_COLORS: no colour is fully saturated or neon (max HSV saturation 0.75), no pure primaries',
          all(sat(c) <= 0.75 for c in MONTH_COLORS.values()), {m: round(sat(c), 2) for m, c in MONTH_COLORS.items()})
    bbg = Bloomberg(blpapi_module=FakeAPI).connect()
    results = resolve_contracts(bbg, FAKE_PRODUCTS, contract_months(2024, 2026), TEST_TODAY)
    for _, cs in results:
        for c in cs:
            fetch_open_interest(bbg, c, 3, TEST_TODAY)
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, 'stacked.xlsx')
    write_workbook(path, results, measure='oi')            # default kind
    wb = load_workbook(path)
    with zipfile.ZipFile(path) as z:
        chart_xml = {n: z.read(n) for n in z.namelist() if n.startswith('xl/charts/chart')}
    for name, cs in results:
        ws = wb[name]
        used, series, dates, _ = product_series(cs, 'oi')
        n, N = len(series), len(dates)
        ch = ws._charts[0]
        check('%s: stacked column chart, no gap, overlap 100, %d bands in expiry order + Total line' % (name, n),
              isinstance(ch, BarChart) and ch.grouping == 'stacked' and ch.overlap == 100 and ch.gapWidth == 0
              and ch.type == 'col' and len(ch.series) == n and len(ch._charts) == 2
              and isinstance(ch._charts[1], LineChart) and len(ch._charts[1].series) == 1
              and [s.tx.strRef.f for s in ch.series] == ["'%s'!%s2" % (name, get_column_letter(j)) for j in range(2, n + 2)],
              (ch.grouping, ch.overlap, ch.gapWidth, len(ch.series)))
        pos = {d: i for i, d in enumerate(dates)}
        last_year = max(c.year for c, _ in series)
        labels, totals = band_labels(series, dates)
        good = all(s.graphicalProperties.solidFill.srgbClr == stack_color(c.year, c.month, last_year)
                   and s.graphicalProperties.line.noFill is True
                   and ((mode is None and s.dLbls is None) or
                        (len(s.dLbls.dLbl) == 1 and s.dLbls.dLbl[0].idx == k
                         and s.dLbls.dLbl[0].showSerName is True and s.dLbls.dLbl[0].showVal is False
                         and s.dLbls.showVal is False and s.dLbls.showSerName is False))
                   for s, (c, rows), (mode, k, _h, _b) in zip(ch.series, series, labels))
        live = [c.label for (c, rows) in series if rows[-1][0] == dates[-1]]
        modes = [m for m, _, _, _ in labels]
        check('%s: bands coloured by month/year; live bands named at the last day, tall ones at their peak, rest legend only'
              % name, good and modes.count('last') == len(live) and 0 < modes.count('peak')
              and all(k == N - 1 for m, k, _, _ in labels if m == 'last')
              and all(h >= LABEL_MIN_HEIGHT * max(totals) for m, k, h, _ in labels if m == 'peak'),
              (modes.count('last'), len(live), modes.count('peak'), modes.count(None)))
        t = ch._charts[1].series[0]
        tl = get_column_letter(n + 2)
        check('%s: Total line from the Total column, black 1 pt, labelled with name + value at the last day' % name,
              t.tx.strRef.f == "'%s'!%s2" % (name, tl) and t.val.numRef.f == "'%s'!$%s$3:$%s$%d" % (name, tl, tl, N + 2)
              and t.graphicalProperties.line.solidFill.srgbClr == TOTAL_COLOR and t.marker.symbol is None
              and len(t.dLbls.dLbl) == 1 and t.dLbls.dLbl[0].idx == N - 1 and t.dLbls.dLbl[0].showVal is True
              and t.dLbls.dLbl[0].showSerName is True and t.dLbls.dLbl[0].numFmt == Y_NUMBER_FORMAT['oi'], t.tx.strRef.f)
        check('%s: category axis with mmm-yy labels ~quarterly, legend on the right, chart after the Total column' % name,
              ch.x_axis.number_format.formatCode == 'mmm-yy' and ch.x_axis.tickLblSkip == max(1, N // 12)
              and ch.legend.position == 'r' and ch.anchor._from.col == n + 3 and ch.y_axis.majorGridlines is None,
              (ch.x_axis.tickLblSkip, ch.anchor._from.col))
    check('chart XML: barChart stacked + lineChart sharing one catAx and one valAx, data labels present, no gridlines',
          all(x.count(b'<barChart>') == 1 and x.count(b'<lineChart>') == 1 and x.count(b'<catAx>') == 1
              and x.count(b'<valAx>') == 1 and b'grouping val="stacked"' in x and b'overlap val="100"' in x
              and b'gapWidth val="0"' in x and b'<dLbl>' in x and b'showSerName val="1"' in x
              and b'majorGridlines' not in x for x in chart_xml.values()) and len(chart_xml) == 3,
          {k: (x.count(b'<barChart>'), x.count(b'<catAx>'), x.count(b'<valAx>')) for k, x in chart_xml.items()})
    xml = chart_xml['xl/charts/chart1.xml']
    _, series, dates, _ = product_series(results[0][1], 'oi')
    n_lbl = sum(1 for m, _, _, _ in band_labels(series, dates)[0] if m)
    check('chart XML: HSI has one label per named band + the total label', xml.count(b'<dLbl>') == n_lbl + 1,
          (xml.count(b'<dLbl>'), n_lbl))
    d = [dt.date(2024, 1, k) for k in (1, 2, 3, 4)]
    ca = Contract(product='x', root='x', year=2024, month=1, label='A', ticker_1='', ticker_2='', status=OK,
                  rows=[(d[0], 10.0), (d[1], 50.0), (d[2], 10.0)])
    cb = Contract(product='x', root='x', year=2024, month=2, label='B', ticker_1='', ticker_2='', status=OK,
                  rows=[(d[1], 1.0), (d[2], 1.0), (d[3], 1.0)])
    cc = Contract(product='x', root='x', year=2024, month=3, label='C', ticker_1='', ticker_2='', status=OK,
                  rows=[(d[0], 1.0), (d[1], 1.0)])
    lbls, tot = band_labels([(ca, ca.rows), (cb, cb.rows), (cc, cc.rows)], d)
    check('band_labels: A expired + tall -> peak at its max day; B alive on the last day -> last; C tiny -> none; totals',
          lbls[0] == ('peak', 1, 50.0, 0.0) and lbls[1] == ('last', 3, 1.0, 0.0) and lbls[2][0] is None
          and tot == [11.0, 52.0, 11.0, 1.0], (lbls, tot))
    days = [dt.date(2024, 1, 1) + dt.timedelta(days=k) for k in range(41)]
    ra = [(x, 100.0 if k == 20 else 1.0) for k, x in enumerate(days[:-1])]          # peak on day 20, expired
    rd = [(x, 100.0 if k == 21 else 1.0) for k, x in enumerate(days[:-1])]          # peak next day, same height
    lbls, _ = band_labels(
        [(Contract(product='x', root='x', year=2024, month=1, label='A', ticker_1='', ticker_2='', status=OK), ra),
         (Contract(product='x', root='x', year=2024, month=4, label='D', ticker_1='', ticker_2='', status=OK), rd)], days)
    check('band_labels: a label that would sit on an earlier one (next day, same height) moves to the band\'s next-best day, or is dropped',
          lbls[0] == ('peak', 20, 100.0, 0.0) and lbls[1][0] is None, lbls)
    rd = [(x, {21: 100.0, 5: 60.0}.get(k, 1.0)) for k, x in enumerate(days[:-1])]
    lbls, _ = band_labels(
        [(Contract(product='x', root='x', year=2024, month=1, label='A', ticker_1='', ticker_2='', status=OK), ra),
         (Contract(product='x', root='x', year=2024, month=4, label='D', ticker_1='', ticker_2='', status=OK), rd)], days)
    check('band_labels: blocked at its tallest day, a band is labelled at its next tallest day that fits',
          lbls[1] == ('peak', 5, 60.0, 1.0), lbls)
    rd = [(x, 100.0 if k == 30 else 1.0) for k, x in enumerate(days[:-1])]
    lbls, _ = band_labels(
        [(Contract(product='x', root='x', year=2024, month=1, label='A', ticker_1='', ticker_2='', status=OK), ra),
         (Contract(product='x', root='x', year=2024, month=4, label='D', ticker_1='', ticker_2='', status=OK), rd)], days)
    check('band_labels: a peak elsewhere in the plot is kept', lbls[0][0] == 'peak' and lbls[1] == ('peak', 30, 100.0, 1.0), lbls)
    try:
        run(products=FAKE_PRODUCTS, today=TEST_TODAY, blpapi_module=FakeAPI, out=path, kind='pie')
        raised = ''
    except ValueError as e:
        raised = str(e)
    check('run(kind=?) is refused', "'stacked' or 'lines'" in raised, raised)
    if importlib.util.find_spec('matplotlib') is not None:
        import warnings
        import matplotlib.pyplot as plt
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            n_fig, _ = quiet(show_charts, results, measure='oi')
        fig = plt.figure(plt.get_fignums()[0])
        ax = fig.axes[0]
        _, series, dates, _ = product_series(results[0][1], 'oi')
        n_bars = len(ax.patches)
        n_lines = len(ax.get_lines())
        texts = [t for t in ax.texts]
        labels = sorted(t.get_text() for t in texts)
        ylim = ax.get_ylim()
        plt.close('all')
        lbls, totals = band_labels(series, dates)
        exp_labels = sorted([c.label for (c, _), (m, _, _, _) in zip(series, lbls) if m]
                            + ['%s %s' % (TOTAL_LABEL, format(int(round(totals[-1])), ','))])
        check('show_charts (stacked): one bar per contract-day, the Total line, boxed labels for the named bands + total, legend',
              n_fig == 3 and n_bars == 36 * len(dates) and n_lines == 1 and labels == exp_labels
              and all(t.get_bbox_patch() is not None for t in texts) and ax.get_legend() is not None
              and len(ax.get_legend().get_texts()) == 37 and ylim[0] == 0,
              (n_fig, n_bars, n_lines, len(texts), labels[:3], exp_labels[:3]))
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
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
            fetch_open_interest(bbg, c, 3, TEST_TODAY)
    if importlib.util.find_spec('matplotlib') is None:
        n, text = quiet(show_charts, results, measure='oi', kind='lines')
        check('show_charts without matplotlib: says so in one line, draws nothing', n == 0 and 'matplotlib is not installed' in text)
    else:
        import warnings
        import matplotlib.pyplot as plt
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            n, text = quiet(show_charts, results, measure='oi', kind='lines')
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
          and wb['HSI'].max_column == 6 and statuses.count(NOT_PULLED) == 79 and statuses.count(OK) == 4
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
    test_notional()
    test_stacked()
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
