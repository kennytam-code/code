#!/usr/bin/env python3
"""Daily open interest of index futures from Bloomberg, as USD notional -> one Excel tab + chart per product.

Everything you may want to change is in the CONFIG block right below.  The engine
underneath needs no edits.  Run the whole file at once:

    Jupyter       %run oi_charts.py      (or paste the file into a cell and run it)
                  -> pulls the data, writes the workbook, draws every chart in the notebook
    Command line  python oi_charts.py [--tickers-only] [--out FILE] [--years-back N] [--skip-months N]
                                     [--measure oi|notional] [--chart stacked|lines]

Self-check, no terminal needed (a fake Bloomberg inside this file drives the real code):

    python oi_charts.py --test     self-checks: ticker forms, windows, cell-by-cell alignment, charts, errors
    python oi_charts.py --demo     writes demo_OI_charts.xlsx from fake data (and draws it in Jupyter)

Each contract's line is its USD notional: open interest x FUT_VAL_PT (value of one index point in
the contract's currency) x the underlying index's daily last price, converted to USD at the
contract currency's rate.  The index (not the futures price) is used so every expiry is scaled
the same way.  Set MEASURE = 'oi' for plain contract counts.

Needs: blpapi and openpyxl; matplotlib only for the notebook charts.
"""

# ================================================================ CONFIG ===
# 1. Products: (Bloomberg root, tab name).  One line per future - add a line to add a
#    product.  The tab name is the underlying index ticker (HSI -> 'HSI Index'): that is the
#    index the USD notional is built on; INDEX_TICKERS below overrides it where the two differ.
#    Tickers are built as <root><month code><year> Index (HIU6, HIU25 ...).  For a non-Index
#    yellow key add it as a third item, e.g. ('CL', 'WTI', 'Comdty').
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
    ('VG',  'SX5E'),            # Eurex Euro Stoxx 50 futures (EUR)
    ('VHO', 'SX5T'),            # Eurex Euro Stoxx 50 total return futures (EUR)
    ('ES',  'SPX'),             # CME E-mini S&P 500 futures (USD)
]

# 2. Time frame: every trading day from DATA_START to today is on the charts.
DATA_START = '2021-01-01'

# 2b. Which expiries to look for.  Every month from DATA_START (+ SKIP_MONTHS: earlier
#     contracts end before the window) up to ALL_MONTHS_AHEAD months after today, then
#     Mar/Jun/Sep/Dec up to QUARTERLY_AHEAD months after today, then December only up to
#     LAST_EXPIRY_YEAR.  A month an exchange never listed comes back NOT FOUND, nothing else.
ALL_MONTHS_AHEAD, QUARTERLY_AHEAD, LAST_EXPIRY_YEAR = 15, 36, 2036

# 3. Contracts expiring within the next SKIP_MONTHS calendar months are left out on every date.
#    4 -> on any day of March the Mar, Apr, May and Jun contracts are hidden and July is the
#    first one shown; July disappears on 1 April.  (Each contract's history is cut at the end of
#    the calendar month SKIP_MONTHS before its expiry month, so the expiry day - mid-month or
#    end-month - makes no difference.)  0 -> keep everything up to the last trade date.
SKIP_MONTHS = 4
#    A contract that is inside the window for fewer than MIN_DAYS_TO_CHART trading days (an
#    exchange often lists a serial month the very day it stops being "within SKIP_MONTHS") is
#    pulled and kept in the Contracts tab but left off the chart: a one-day sliver says nothing.
MIN_DAYS_TO_CHART = 5

# 4. Output.  The workbook is OI_charts_<yyyymmdd>.xlsx (or OUTPUT_FILE) and goes to
#    OUTPUT_FOLDER; when that folder does not exist it goes to the current folder instead.
#    The full path is printed at the end of every run.
OUTPUT_FILE = None
OUTPUT_FOLDER = '~/Downloads'
SHOW_CHARTS = True              # in Jupyter also draw every chart inline (needs matplotlib)
TICKERS_ONLY = False            # True -> only resolve and print the contract table (quick check)

# 5. What each band is.  'notional': open interest x FUT_VAL_PT x index level, in USD (a product
#    whose index or multiplier cannot be found falls back to plain OI, and the chart title and the
#    summary say so).  'oi': open interest in contracts.  {name} in the text is the tab name.
MEASURE = 'notional'
CHART_TITLE = {'notional': '{name} futures open interest, USD notional',
               'oi': '{name} futures open interest, contracts'}
FALLBACK_TITLE = '{name} futures open interest, contracts (USD notional unavailable)'
SUBTITLE = 'Contracts expiring within {skip} months excluded   |   Source: Bloomberg, Nomura'
Y_AXIS_TITLE = {'notional': 'USD bn', 'oi': 'Contracts'}   # a small product is shown in USD m instead

# 5b. Chart type.  'stacked': the contracts stacked as daily columns (earliest expiry at the
#     bottom, no gap between days), so the top edge of the stack is the product total, traced by
#     the Total line; the contracts alive on the last day are named at the right edge, the other
#     big bands at their peak.  'lines': one line per contract.
CHART_KIND = 'stacked'

# 5c. Band colours: every contract gets its own, in expiry order down this list (it wraps after
#     20, so two bands of one colour are 20 expiries apart and never next to each other).  The
#     Nomura deck family, four tone families at five depths each - the reds around Nomura red
#     (Pantone 186 C), cool greys, navy-to-steel blues, and warm greys from espresso to linen -
#     dealt out so that neighbours differ in both family and depth.  Hex, no '#'.
NOMURA_RED = 'C8102E'
BAND_COLORS = [
    NOMURA_RED, # Nomura red
    '1B2A47',   # navy
    'AEB4BA',   # silver
    '857766',   # greige
    '4A6684',   # slate blue
    'D9A0A6',   # rose
    '2F3136',   # graphite
    'C6BBA5',   # champagne
    '6A82A0',   # steel
    '7A1E2B',   # burgundy
    '8A8D91',   # mid grey
    '5C4F46',   # espresso
    '98ACC0',   # light steel
    'B0453E',   # claret
    'D3D6DA',   # light grey
    'A99E8B',   # stone
    '34506E',   # deep blue
    'B87A81',   # dusty red
    '55606B',   # slate grey
    'E2DACD',   # linen
]
CHART_FONT = 'Arial'

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
# 8. Sanity check only - what the exchanges publish as (contract currency, value of one index
#    point).  Bloomberg's FUT_VAL_PT is what the notional uses; a disagreement with this table is
#    printed as a WARNING so it gets looked at, never silently overridden.  Roots not listed here
#    (MTW, HJA, VHO) are simply not checked.
EXPECTED_CONTRACT = {
    'HI': ('HKD', 50), 'HC': ('HKD', 50), 'HCT': ('HKD', 50),      # HKEX: HK$50 x index
    'KM': ('KRW', 250000),                                         # KRX KOSPI 200: KRW 250,000 x index
    'XP': ('AUD', 25),                                             # ASX SPI 200: A$25 x index
    'FT': ('TWD', 200),                                            # TAIFEX TX: NT$200 x index
    'TWT': ('USD', 40), 'FPO': ('USD', 1), 'QZ': ('SGD', 100),     # SGX FTSE Taiwan / FTSE China A50 / MSCI Singapore
    'VG': ('EUR', 10), 'ES': ('USD', 50),                          # Eurex Euro Stoxx 50 / CME E-mini S&P 500
}
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
    from openpyxl.chart.axis import ChartLines, DateAxis  # noqa: E402
    from openpyxl.chart.layout import Layout, ManualLayout   # noqa: E402
    from openpyxl.chart.shapes import GraphicalProperties  # noqa: E402
    from openpyxl.chart.text import RichText, Text        # noqa: E402
    from openpyxl.chart.title import Title                # noqa: E402
    from openpyxl.drawing.line import LineProperties      # noqa: E402
    from openpyxl.drawing.text import (CharacterProperties, Font, Paragraph, ParagraphProperties,   # noqa: E402
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
# chart look: dark grey text, light grey axis line and gridlines, grey subtitle, no borders
CHART_TEXT, CHART_LINE, GRID_COLOR, SUBTITLE_COLOR = '404040', 'BFBFBF', 'E6E6E6', '6E6E6E'
TOTAL_LABEL = 'Total'
LABEL_MIN_HEIGHT = 0.06      # a band is named at its peak when it is at least this share of the axis there
LABEL_BOX = (0.05, 0.035)    # width, height of one in-band label as a share of the plot: two labels closer than this collide
MAX_END_LABELS = 10          # at most this many contracts named at the right edge (the largest ones)
AUDIT_COLUMNS = ['Product', 'Contract', 'Ticker 1-digit', 'Ticker 2-digit', 'Ticker used',
                 'Status', 'LAST_TRADEABLE_DT', 'FUT_MONTH_YR', 'Name', 'Request start',
                 'Request end', 'First OI date', 'Last OI date', 'Rows', 'Last OI', 'Max OI',
                 'Multiplier', 'Ccy', 'Last notional (USD)', 'Max notional (USD)', 'Note']


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


def add_months(year, month, n):
    """(year, month) shifted by n months."""
    idx = year * 12 + (month - 1) + n
    return idx // 12, idx % 12 + 1


def expiry_months(data_start, today, skip_months, all_ahead, quarterly_ahead, last_year):
    """The expiry months worth asking Bloomberg for, in order: every month from data_start
    (+ skip_months - earlier contracts end before the window) up to all_ahead months after
    today, Mar/Jun/Sep/Dec up to quarterly_ahead months after today, then December only up to
    last_year."""
    all_to = add_months(today.year, today.month, all_ahead)
    q_to = add_months(today.year, today.month, quarterly_ahead)
    tail = max(all_to, q_to)
    out = []
    y, m = add_months(data_start.year, data_start.month, skip_months)
    while (y, m) <= all_to:
        out.append((y, m))
        y, m = add_months(y, m, 1)
    while (y, m) <= q_to:
        if m in (3, 6, 9, 12):
            out.append((y, m))
        y, m = add_months(y, m, 1)
    for yy in range(y, last_year + 1):
        if (yy, 12) > tail:
            out.append((yy, 12))
    return out


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


def band_family(month):
    """'dec' | 'quarter' | 'serial' - the tenor family a contract month belongs to."""
    return 'dec' if month == 12 else ('quarter' if month in (3, 6, 9) else 'serial')


def band_colors(contracts):
    """One hex colour per contract (same order): BAND_COLORS in expiry order, wrapping."""
    return [BAND_COLORS[i % len(BAND_COLORS)] for i in range(len(contracts))]


def axis_unit(max_value, measure):
    """(axis title, Excel number format, divisor) for the y axis: USD bn, or USD m for a small
    product; contracts as they are."""
    if measure != 'notional':
        return Y_AXIS_TITLE['oi'], '#,##0', 1.0
    if max_value >= 1e9:
        return Y_AXIS_TITLE['notional'], '#,##0.0,,,', 1e9
    return 'USD m', '#,##0,,', 1e6


def month_tick(d):
    """'Sep-23' - the x-axis label of a month (MONTH_ABBR, not the locale's)."""
    return '%s-%02d' % (MONTH_ABBR[d.month - 1], d.year % 100)


def month_starts(dates):
    """Indexes of the first date of each month in a sorted date list."""
    return [i for i, d in enumerate(dates) if i == 0 or (d.year, d.month) != (dates[i - 1].year, dates[i - 1].month)]


def subtitle_text(skip_months=None):
    skip = SKIP_MONTHS if skip_months is None else skip_months
    if not skip:
        return 'All listed contracts shown, to their last trade date   |   Source: Bloomberg, Nomura'
    return SUBTITLE.format(skip=skip)


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


def expected_form(c, today):
    """The form the desk would type: two digits once the contract month has passed, else one."""
    return c.ticker_2 if (c.year, c.month) < (today.year, today.month) else c.ticker_1


def other_form(c, today):
    return c.ticker_1 if expected_form(c, today) == c.ticker_2 else c.ticker_2


def resolve_contracts(bbg, products, months, today):
    """Two reference passes: the expected ticker form of every contract, then the other form
    for the contracts that did not resolve.  pick_ticker validates each form on LAST_TRADEABLE_DT,
    so a one-digit code that Bloomberg maps to another decade is caught and the other form tried."""
    results = build_contracts(products, months)
    allc = [c for _, cs in results for c in cs]
    ref = dict(bbg.ref([expected_form(c, today) for c in allc], REF_FIELDS))
    for c in allc:
        pick_ticker(c, ref, bbg.bad_securities, today)
    missing = [c for c in allc if c.status != OK]
    if missing:
        ref.update(bbg.ref([other_form(c, today) for c in missing], REF_FIELDS))
        for c in missing:
            pick_ticker(c, ref, bbg.bad_securities, today)
    return results


def fetch_open_interest(bbg, c, data_start, today, skip_months=None):
    """Fill c.rows with daily OPEN_INT from data_start up to the earliest of the last trade date,
    today, and the end of the calendar month skip_months before the contract month."""
    if c.status != OK:
        return
    skip_months = SKIP_MONTHS if skip_months is None else skip_months
    c.req_start = data_start
    c.req_end = min(c.last_trade, today)
    cutoff = history_cutoff(c.year, c.month, skip_months)
    if cutoff is not None:
        c.req_end = min(c.req_end, cutoff)
    if c.req_start > c.req_end:
        c.status, c.note = NO_DATA, 'its window ends %s, before DATA_START' % c.req_end.isoformat()
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


def product_series(contracts, measure, ix=None):
    """What one tab shows: (measure used, [(contract, rows)], dates, note).

    dates run from the first to the last day any contract has a value; inside that span every
    trading day of the index (ix.rows, when given) is a row too, so a day without a single print
    stays visible as a hole instead of being squeezed out of a category axis.  A contract with
    fewer than MIN_DAYS_TO_CHART days in the window is left out (it stays in the Contracts tab).
    'notional' falls back to 'oi' for a product where no contract has a notional.
    """
    ok = [c for c in contracts if c.status == OK and len(c.rows) >= MIN_DAYS_TO_CHART]
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
    value_dates = {d for _, rows in series for d, _ in rows}
    if value_dates and ix is not None and ix.rows:
        lo, hi = min(value_dates), max(value_dates)
        value_dates.update(d for d, _ in ix.rows if lo <= d <= hi)
    return used, series, sorted(value_dates), note


# -------------------------------------------------------------- workbook ---
def safe_sheet_name(name):
    for ch in '[]:*?/\\':
        name = name.replace(ch, ' ')
    return name.strip()[:31]


def font_props(size, bold=False, color=None):
    """Character properties: size in 1/100 pt, CHART_FONT, colour (hex, no '#')."""
    return CharacterProperties(sz=size, b=bold, solidFill=color or CHART_TEXT, latin=Font(typeface=CHART_FONT))


def chart_text(size, bold=False, color=None, rot=None):
    """Text properties for an axis or a label; rot in 1/60000 degree (-2700000 = 45 degrees up)."""
    cp = font_props(size, bold, color)
    body = RichTextProperties(rot=rot, vert='horz') if rot is not None else None
    return RichText(bodyPr=body, p=[Paragraph(pPr=ParagraphProperties(defRPr=cp), endParaRPr=cp)])


def chart_title(text, subtitle=None):
    """The title (12 pt bold) with the grey subtitle under it, both at the top left."""
    t = font_props(1200, True)
    paras = [Paragraph(pPr=ParagraphProperties(defRPr=t, algn='l'), r=[RegularTextRun(rPr=t, t=text)])]
    if subtitle:
        u = font_props(850, False, SUBTITLE_COLOR)
        paras.append(Paragraph(pPr=ParagraphProperties(defRPr=u, algn='l'), r=[RegularTextRun(rPr=u, t=subtitle)]))
    title = Title(tx=Text(rich=RichText(bodyPr=RichTextProperties(), p=paras)), overlay=False)
    title.layout = Layout(manualLayout=ManualLayout(x=0.01, y=0.01, xMode='edge', yMode='edge'))
    return title


def axis_title(text):
    cp = font_props(850, False, SUBTITLE_COLOR)
    return Title(tx=Text(rich=RichText(bodyPr=RichTextProperties(), p=[Paragraph(
        pPr=ParagraphProperties(defRPr=cp), r=[RegularTextRun(rPr=cp, t=text)])])), overlay=False)


def style_axes(ch, unit_title, number_format):
    """The shared deck look: light horizontal gridlines, no y axis line, a hairline x axis, grey
    8 pt tick labels, the legend of every contract along the bottom, no borders."""
    ch.y_axis.delete = False
    ch.x_axis.delete = False
    ch.y_axis.title = axis_title(unit_title)
    ch.y_axis.number_format = number_format
    ch.y_axis.majorGridlines = ChartLines(spPr=GraphicalProperties(ln=LineProperties(solidFill=GRID_COLOR, w=6350)))
    ch.x_axis.majorGridlines = None
    ch.y_axis.txPr = chart_text(800)
    ch.x_axis.txPr = chart_text(750, rot=-2700000)      # one label per month, 45 degrees
    for ax in (ch.x_axis, ch.y_axis):
        ax.minorTickMark = 'none'
    ch.y_axis.graphicalProperties = GraphicalProperties(ln=LineProperties(noFill=True))
    ch.y_axis.majorTickMark = 'none'
    ch.x_axis.graphicalProperties = GraphicalProperties(ln=LineProperties(solidFill=CHART_LINE, w=6350))
    ch.x_axis.majorTickMark = 'none'
    ch.x_axis.tickLblPos = 'low'
    ch.legend.position = 'b'
    ch.legend.txPr = chart_text(750)
    ch.graphical_properties = GraphicalProperties(ln=LineProperties(noFill=True))   # no chart border
    ch.plot_area.graphicalProperties = GraphicalProperties(noFill=True, ln=LineProperties(noFill=True))


def point_label(idx, show_name=False, show_value=False, num_fmt=None, pos='ctr', size=750, color=None, bold=True,
                box=None):
    """A data label on one point of a series (all other points stay unlabelled).  box = a hex
    colour -> white box with a hairline of that colour, so the name reads on any band."""
    lbl = DataLabel(idx=idx, showSerName=show_name, showVal=show_value, showCatName=False, showLegendKey=False,
                    showPercent=False, showBubbleSize=False, dLblPos=pos,
                    txPr=chart_text(size, bold=bold, color=color))
    if num_fmt:
        lbl.numFmt = num_fmt
    if box:
        lbl.spPr = GraphicalProperties(solidFill='FFFFFF', ln=LineProperties(solidFill=box, w=9525))
    return lbl


def series_labels(labels):
    """dLbls for a series: only the listed points carry a label."""
    return DataLabelList(dLbl=labels, showSerName=False, showVal=False, showCatName=False, showLegendKey=False,
                         showPercent=False, showBubbleSize=False)


def add_oi_chart(ws, name, series, dates, measure='oi', title=None, skip_months=None, anchor_col=None):
    """'lines': one line per contract on a date axis; blanks are gaps, so each line spans only
    its own data.  A contract alive on the last day is named there, another big one at its peak."""
    n_series, n_rows = len(series), len(dates)
    labels, totals = band_labels(series, dates)
    unit_title, fmt, _div = axis_unit(max((v for _, rows in series for _, v in rows), default=0), measure)
    colors = band_colors([c for c, _ in series])
    ch = LineChart()
    ch.title = chart_title(title or CHART_TITLE[measure].format(name=name), subtitle_text(skip_months))
    ch.display_blanks = 'gap'
    ch.x_axis = DateAxis(crossAx=100)          # axId 500; the value axis must cross it
    ch.x_axis.number_format = 'mmm-yy'
    ch.x_axis.majorTimeUnit = 'months'
    ch.x_axis.majorUnit = 1                    # every month labelled
    ch.y_axis.crossAx = 500
    style_axes(ch, unit_title, fmt)
    ch.width, ch.height = 30, 17               # cm
    last_row = 2 + n_rows
    ch.add_data(Reference(ws, min_col=2, max_col=1 + n_series, min_row=2, max_row=last_row),
                titles_from_data=True)          # row 2 = the 'Jan 24' labels
    ch.set_categories(Reference(ws, min_col=1, min_row=3, max_row=last_row))
    for s, colour, (mode, k, _h, _b) in zip(ch.series, colors, labels):
        s.marker.symbol = 'none'
        s.smooth = False
        s.graphicalProperties.line.width = 12700   # EMU: 1 pt
        s.graphicalProperties.line.solidFill = colour
        if mode is not None:
            s.dLbls = series_labels([point_label(k, show_name=True, pos='r' if mode == 'last' else 't', box=colour)])
    ws.add_chart(ch, '%s2' % get_column_letter(anchor_col or (n_series + 5)))   # after the Total and Month columns


def add_stacked_chart(ws, name, series, dates, measure='oi', title=None, skip_months=None, month_col=None):
    """Stacked daily columns, one band per contract in expiry order (earliest at the bottom), no
    gap between days, so the top of the stack is the product total.  A contract alive on the last
    day is named at the end of its band, another band tall enough at its peak; the legend below
    lists every contract.  The x axis reads the Month column: one label on the first day of
    each month, nothing in between."""
    n_series, n_rows = len(series), len(dates)
    last_row = 2 + n_rows
    month_col = month_col or (n_series + 3)
    labels, totals = band_labels(series, dates)
    unit_title, fmt, _div = axis_unit(max(totals) if totals else 0, measure)
    colors = band_colors([c for c, _ in series])
    ch = BarChart()
    ch.type = 'col'
    ch.grouping = 'stacked'
    ch.overlap = 100
    ch.gapWidth = 0
    ch.title = chart_title(title or CHART_TITLE[measure].format(name=name), subtitle_text(skip_months))
    ch.display_blanks = 'gap'
    style_axes(ch, unit_title, fmt)
    ch.x_axis.tickLblSkip = 1                  # every category label - and only month starts carry one
    ch.x_axis.tickMarkSkip = 1
    ch.x_axis.noMultiLvlLbl = True
    ch.width, ch.height = 30, 17               # cm: room for the legend rows under the plot
    ch.add_data(Reference(ws, min_col=2, max_col=1 + n_series, min_row=2, max_row=last_row),
                titles_from_data=True)          # row 2 = the 'Jan 24' labels
    ch.set_categories(Reference(ws, min_col=month_col, min_row=3, max_row=last_row))
    top = max(totals) if totals else 1.0
    for s, colour, (mode, k, h, _b) in zip(ch.series, colors, labels):
        s.graphicalProperties.solidFill = colour
        s.graphicalProperties.line.noFill = True
        if mode == 'peak' or (mode == 'last' and h >= LABEL_MIN_HEIGHT * top):
            s.dLbls = series_labels([point_label(k, show_name=True, size=800, box=colour)])
    ws.add_chart(ch, '%s2' % get_column_letter(month_col + 2))


def write_product_sheet(wb, name, contracts, measure='oi', kind=None, ix=None, skip_months=None):
    """Row 1 tickers, row 2 labels, then one row per date; the cells are the USD notional (or the
    OI when measure == 'oi' or the notional is unavailable), then a Total column (blank on a day
    without a single print).  Returns (sheet, measure used, note)."""
    kind = CHART_KIND if kind is None else kind
    ws = wb.create_sheet(title=safe_sheet_name(name))
    used, series, dates, note = product_series(contracts, measure, ix)
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
        ws.column_dimensions[get_column_letter(j)].width = 14 if used == 'notional' else 9
    total_col = len(found) + 2
    lookups = [dict(rows) for _, rows in series]
    for i, d in enumerate(dates, start=3):
        ws.cell(row=i, column=1, value=d).number_format = 'yyyy-mm-dd'
        total, any_value = 0.0, False
        for j, lk in enumerate(lookups, start=2):
            v = lk.get(d)
            if v is not None:                       # a missing print stays an empty cell
                ws.cell(row=i, column=j, value=v).number_format = '#,##0'
                total, any_value = total + v, True
        if any_value:                               # a day without one print stays a hole
            ws.cell(row=i, column=total_col, value=total).number_format = '#,##0'
    ws.cell(row=1, column=total_col, value=TOTAL_LABEL)
    ws.cell(row=2, column=total_col, value=TOTAL_LABEL)
    ws.column_dimensions[get_column_letter(total_col)].width = 16 if used == 'notional' else 12
    month_col = total_col + 1                      # the chart's x axis: a label on the first day of each month
    ws.cell(row=1, column=month_col, value='Axis')
    ws.cell(row=2, column=month_col, value='Month')
    for i in month_starts(dates):
        ws.cell(row=i + 3, column=month_col, value=month_tick(dates[i]))
    ws.column_dimensions[get_column_letter(month_col)].width = 8
    ws.freeze_panes = 'B3'
    title = FALLBACK_TITLE.format(name=name) if (measure == 'notional' and used == 'oi') else None
    if kind == 'stacked':
        add_stacked_chart(ws, name, series, dates, used, title, skip_months, month_col)
    else:
        add_oi_chart(ws, name, series, dates, used, title, skip_months, month_col + 2)
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


def write_workbook(path, results, indices=None, measure=None, kind=None, skip_months=None):
    """measure: 'notional' (default MEASURE) or 'oi'; kind: 'stacked' (default CHART_KIND) or
    'lines'.  indices: {tab name: IndexSeries} - the trading calendar behind each tab and the
    Indices audit tab (None -> neither).  Returns {tab name: (measure used, note)}."""
    measure = MEASURE if measure is None else measure
    kind = CHART_KIND if kind is None else kind
    wb = Workbook()
    wb.remove(wb.active)
    used = {}
    for name, cs in results:
        _, m, note = write_product_sheet(wb, name, cs, measure, kind, (indices or {}).get(name), skip_months)
        used[name] = (m, note)
    write_contracts_sheet(wb, results)
    if indices is not None:
        write_indices_sheet(wb, indices)
    wb.save(path)
    return used


# ------------------------------------------------------- notebook charts ---
def _bands(series, dates):
    """[(values per date, bottoms per date)] per band, in series order."""
    pos = {d: i for i, d in enumerate(dates)}
    n = len(dates)
    bottom = [0.0] * n
    out = []
    for _, rows in series:
        y = [0.0] * n
        for d, v in rows:
            y[pos[d]] = v
        out.append((y, list(bottom)))
        bottom = [b + v for b, v in zip(bottom, y)]
    return out


def band_labels(series, dates):
    """Which point of each band carries its name: ('last', idx) for a band alive on the last day
    (the MAX_END_LABELS largest ones); ('peak', idx) for another band - the middle of the days
    where it stands at 60% of its peak or more, else its tallest day - where a label fits: tall
    enough (LABEL_MIN_HEIGHT of the plot) and not on top of a label already placed (LABEL_BOX);
    None when no day qualifies.
    Returns ([(mode, idx, band height at idx, bottom of the band at idx)] in series order, totals)."""
    n = len(dates)
    bands = _bands(series, dates)              # (values, bottoms) per band
    bottom = [b + v for v, b in zip(bands[-1][0], bands[-1][1])] if bands else [0.0] * n
    top = max(bottom) if bottom else 1.0
    live = [(i, y[n - 1]) for i, ((_, rows), (y, _)) in enumerate(zip(series, bands))
            if rows and rows[-1][0] == dates[-1]]
    named_last = {i for i, _ in sorted(live, key=lambda t: -t[1])[:MAX_END_LABELS]}
    placed = []                                # (x, y) of the peak labels kept, as shares of the plot
    out = []
    for i, ((_, rows), (y, base)) in enumerate(zip(series, bands)):
        if i in named_last:
            k = n - 1
            out.append(('last', k, y[k], base[k]))
            continue
        chosen = None
        peak = max(y) if y else 0.0
        plateau = [j for j in range(n) if y[j] >= 0.6 * peak > 0]
        candidates = ([plateau[len(plateau) // 2]] if plateau else []) + \
            sorted((j for j in range(n) if y[j] > 0), key=lambda j: -y[j])
        for k in candidates:                   # the middle of the plateau first, then the tallest days
            if y[k] < LABEL_MIN_HEIGHT * top:
                break                          # everything after is shorter still
            x, yc = k / max(1, n - 1), (base[k] + y[k] / 2.0) / top
            if not any(abs(x - px) < LABEL_BOX[0] and abs(yc - py) < LABEL_BOX[1] for px, py in placed):
                chosen = k
                placed.append((x, yc))
                break
        if chosen is None:
            k = max(range(n), key=lambda j: y[j])
            out.append((None, k, y[k], base[k]))
        else:
            out.append(('peak', chosen, y[chosen], base[chosen]))
    return out, bottom


def money(value, div, unit_title):
    """'12.3bn' / '1,234bn' / '850m' / '1,234' for an axis divisor."""
    if div >= 1e9:
        v = value / 1e9
        return ('{:,.0f}bn' if v >= 100 else '{:,.1f}bn').format(v)
    if div >= 1e6:
        return '{:,.0f}m'.format(value / 1e6)
    return format(int(round(value)), ',')


def axis_formatter(div, top):
    """matplotlib tick formatter for the y axis: billions with one decimal while the axis is
    small, whole numbers with separators once it is not; contracts as they are."""
    if div >= 1e9:
        decimals = 1 if top / 1e9 < 100 else 0
        return lambda v, _pos: ('{:,.%df}' % decimals).format(v / 1e9)
    if div >= 1e6:
        return lambda v, _pos: '{:,.0f}'.format(v / 1e6)
    return lambda v, _pos: format(int(round(v)), ',')


def stacked_axes(ax, series, dates, used, skip_months=None):
    """Draw the stack on a matplotlib axes: one column per day (the x axis is the trading-day
    index, so a day without a print is a visible hole), the Total line, in-band names for the
    tall bands, a label rail in the right margin for the contracts alive on the last day, and
    the legend of every contract below.  Returns (labels placed, axis title, divisor)."""
    import numpy as np
    n = len(dates)
    x = np.arange(n)
    pos = {d: i for i, d in enumerate(dates)}
    labels, totals = band_labels(series, dates)
    colors = band_colors([c for c, _ in series])
    unit_title, _fmt, div = axis_unit(max(totals) if totals else 0, used)
    bottom = np.zeros(n)
    top = max(totals) if totals else 1.0
    ax.set_ylim(0, top * 1.10)
    rail_x = n - 1 + n * 0.03                  # the rail sits just right of the last column
    ax.set_xlim(-0.5, n - 0.5 + n * 0.14)
    placed = 0
    rail = []                                  # (y anchor, label, colour) for the right-margin labels
    for (c, rows), (mode, k, h, b), colour in zip(series, labels, colors):
        y = np.zeros(n)
        for d, v in rows:
            y[pos[d]] = v
        ax.bar(x, y, bottom=bottom, width=1.0, color='#' + colour, linewidth=0, align='center', label=c.label)
        bottom = bottom + y
        if mode == 'last':
            rail.append((b + h / 2.0, c.label, colour))
        elif mode == 'peak':
            ha = 'left' if k < 0.03 * n else ('right' if k > 0.97 * n else 'center')
            ax.text(k, b + h / 2.0, c.label, fontsize=8, fontweight='bold', color='#' + CHART_TEXT, ha=ha,
                    va='center', bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='#' + colour, lw=1.0))
            placed += 1
    # the rail: labels bottom-up, each at least one step above the previous, a light connector to the band
    gap = top * 1.10 * 0.045
    y_prev = -gap
    for y_anchor, label, colour in sorted(rail):
        y_text = max(y_anchor, y_prev + gap)
        y_prev = y_text
        ax.plot([n - 0.5, rail_x - n * 0.012], [y_anchor, y_text], color='#' + CHART_LINE, linewidth=0.7,
                solid_capstyle='round', clip_on=False)
        ax.plot([rail_x - n * 0.008], [y_text], marker='s', ms=6, color='#' + colour, linestyle='none', clip_on=False)
        ax.text(rail_x, y_text, label, fontsize=8.5, color='#' + CHART_TEXT, ha='left', va='center')
        placed += 1
    ticks = month_starts(dates)                # one tick per month
    step = max(1, len(ticks) // 48)            # thin out only beyond four years
    ticks = ticks[::step]
    ax.set_xticks(ticks)
    ax.set_xticklabels([month_tick(dates[i]) for i in ticks], rotation=45, ha='right', rotation_mode='anchor',
                       fontsize=7.5)
    return placed, unit_title, div


def lines_axes(ax, series, dates, used):
    """'lines' on matplotlib: one line per contract on a real date axis, named at its end when
    alive on the last day, else at its peak when tall enough.  Returns (labels, axis title, divisor)."""
    import matplotlib.dates as mdates
    labels, _ = band_labels(series, dates)
    colors = band_colors([c for c, _ in series])
    unit_title, _fmt, div = axis_unit(max((v for _, rows in series for _, v in rows), default=0), used)
    placed = 0
    for (c, rows), (mode, k, _h, _b), colour in zip(series, labels, colors):
        ax.plot([d for d, _ in rows], [v for _, v in rows], linewidth=1.2, color='#' + colour, label=c.label)
        if mode == 'last':
            ax.annotate(' ' + c.label, xy=rows[-1], fontsize=8, color='#' + CHART_TEXT, ha='left', va='center')
            placed += 1
        elif mode == 'peak':
            d, v = dates[k], dict(rows).get(dates[k], 0.0)
            ax.annotate(c.label, xy=(d, v), xytext=(0, 5), textcoords='offset points', fontsize=8,
                        color='#' + CHART_TEXT, ha='center', va='bottom',
                        bbox=dict(boxstyle='round,pad=0.25', fc='white', ec='#' + colour, lw=0.9))
            placed += 1
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b-%y'))
    ax.tick_params(axis='x', labelrotation=45, labelsize=7.5)
    return placed, unit_title, div


def use_chart_font(plt):
    """CHART_FONT when the machine has it (Windows and Mac do), the default sans otherwise."""
    try:
        from matplotlib import font_manager
        font_manager.findfont(font_manager.FontProperties(family=CHART_FONT), fallback_to_default=False)
    except Exception:
        return
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = [CHART_FONT] + [f for f in plt.rcParams['font.sans-serif'] if f != CHART_FONT]


def show_charts(results, measure=None, kind=None, indices=None, skip_months=None):
    """Draw every product chart with matplotlib (inline in Jupyter). Returns the figure count."""
    try:
        import matplotlib.pyplot as plt
        from matplotlib.ticker import FuncFormatter
    except ImportError:
        print('matplotlib is not installed, so no charts here - they are in the workbook '
              '(pip install matplotlib)')
        return 0
    use_chart_font(plt)
    measure = MEASURE if measure is None else measure
    kind = CHART_KIND if kind is None else kind
    n_fig = 0
    for name, cs in results:
        used, series, dates, note = product_series(cs, measure, (indices or {}).get(name))
        if not series:
            continue
        n_cols = 10
        n_rows_legend = -(-len(series) // n_cols)
        fig, ax = plt.subplots(figsize=(13, 6.5 + 0.22 * n_rows_legend), dpi=110)
        if kind == 'stacked':
            _n, unit_title, div = stacked_axes(ax, series, dates, used, skip_months)
        else:
            _n, unit_title, div = lines_axes(ax, series, dates, used)
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.09), ncol=n_cols, fontsize=8, frameon=False,
                  handlelength=1.2, handleheight=1.0, columnspacing=1.4, handletextpad=0.5)
        title = FALLBACK_TITLE if (measure == 'notional' and used == 'oi') else CHART_TITLE[used]
        ax.set_title(title.format(name=name), loc='left', fontsize=12, fontweight='bold', color='#' + CHART_TEXT,
                     pad=24)
        ax.text(0, 1.035, subtitle_text(skip_months), transform=ax.transAxes, fontsize=8.5,
                color='#' + SUBTITLE_COLOR, ha='left', va='bottom')
        ax.set_ylabel(unit_title, color='#' + SUBTITLE_COLOR, fontsize=8.5)
        ax.yaxis.set_major_formatter(FuncFormatter(axis_formatter(div, ax.get_ylim()[1])))
        ax.yaxis.grid(True, color='#' + GRID_COLOR, linewidth=0.8)
        ax.xaxis.grid(False)
        ax.set_axisbelow(True)
        ax.tick_params(colors='#' + CHART_TEXT, labelsize=8, length=3, width=0.6)
        ax.tick_params(axis='y', length=0)
        for side in ('top', 'right', 'left'):
            ax.spines[side].set_visible(False)
        ax.spines['bottom'].set_color('#' + CHART_LINE)
        ax.spines['bottom'].set_linewidth(0.6)
        fig.tight_layout()
        plt.show()
        n_fig += 1
    return n_fig


# --------------------------------------------------------------- console ---
def print_contract_table(results):
    print('%-8s %-7s %-14s %-9s %-11s %-9s %-4s %s' % ('Product', 'Month', 'Ticker', 'Status', 'Last trade',
                                                        MULTIPLIER_FIELD, 'Ccy', 'Note'))
    for name, cs in results:
        for c in cs:
            print('%-8s %-7s %-14s %-9s %-11s %-9s %-4s %s' % (
                name, c.label, c.ticker or '-', c.status,
                c.last_trade.isoformat() if c.last_trade else '-',
                ('%g' % c.multiplier) if c.multiplier is not None else '-', c.currency or '-', c.note))
    print()


def contract_warnings(cs, ix):
    """Sentences for a product whose Bloomberg multiplier or working currency disagrees with
    EXPECTED_CONTRACT (empty when it agrees or the root is not in the table)."""
    out = []
    for root in sorted({c.root for c in cs}):
        if root not in EXPECTED_CONTRACT:
            continue
        ccy, mult = EXPECTED_CONTRACT[root]
        seen = sorted({c.multiplier for c in cs if c.status == OK and c.multiplier is not None})
        if seen and any(abs(m - mult) > 1e-9 for m in seen):
            out.append('%s for %s is %s on Bloomberg; the exchange multiplier is %s %g - check before using the notional'
                       % (MULTIPLIER_FIELD, root, ' / '.join('%g' % m for m in seen), ccy, mult))
        if ix is not None and ix.status == OK and ix.fut_currency and ix.fut_currency != ccy:
            out.append('the notional converts %s from %s (%s) but the %s contract is denominated in %s - '
                       'set CONTRACT_CURRENCY or INDEX_TICKERS for it'
                       % (root, ix.fut_currency, ix.ccy_source, root, ccy))
    return out


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
        thin = ['%s (%d)' % (c.label, len(c.rows)) for c in cs if c.status == OK and 0 < len(c.rows) < MIN_DAYS_TO_CHART]
        if thin:
            print('         not charted, under %d days in the window: %s' % (MIN_DAYS_TO_CHART, ', '.join(thin)))
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
                for w in contract_warnings(cs, ix):
                    print('         WARNING:    %s' % w)
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
def run(products=None, data_start=None, out=None, today=None, blpapi_module=None, tickers_only=None,
        show_charts_=None, host=BBG_HOST, port=BBG_PORT, skip_months=None, measure=None, kind=None,
        all_ahead=None, quarterly_ahead=None, last_expiry_year=None):
    """Resolve every contract, pull its open interest, write the workbook; returns the path.

    Every argument defaults to the CONFIG value at the top of the file.
    """
    products = list(PRODUCTS if products is None else products)
    data_start = as_date(DATA_START if data_start is None else data_start)
    if data_start is None:
        raise ValueError('DATA_START must be a date, YYYY-MM-DD')
    skip_months = SKIP_MONTHS if skip_months is None else skip_months
    all_ahead = ALL_MONTHS_AHEAD if all_ahead is None else all_ahead
    quarterly_ahead = QUARTERLY_AHEAD if quarterly_ahead is None else quarterly_ahead
    last_expiry_year = LAST_EXPIRY_YEAR if last_expiry_year is None else last_expiry_year
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
    months = expiry_months(data_start, today, skip_months, all_ahead, quarterly_ahead, last_expiry_year)
    if not months:
        raise ValueError('no expiry month to look for - check DATA_START / LAST_EXPIRY_YEAR')
    out = output_path(out, today)
    print('OI charts | %d products | window %s .. %s | expiries %s .. %s (%d) | '
          'contracts expiring within %d months excluded | %s'
          % (len(products), data_start.isoformat(), today.isoformat(), month_label(*months[0]),
             month_label(*months[-1]), len(months), skip_months,
             'USD notional' if measure == 'notional' else 'OI in contracts'))
    try:
        bbg = Bloomberg(host, port, blpapi_module=blpapi_module).connect()
    except Exception as e:
        raise StepError('connecting to Bloomberg', e)
    pull_error = None
    try:
        print('Resolving %d contracts for %d products ...' % (len(months) * len(products), len(products)))
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
                    fetch_open_interest(bbg, c, data_start, today, skip_months)
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
        used = write_workbook(out, results, indices=indices, measure=measure, kind=kind, skip_months=skip_months)
    except Exception as e:
        raise StepError('writing the workbook %s' % out, e)
    print_summary(results, bbg, out, indices, used)
    if show_charts_:
        try:
            show_charts(results, measure=measure, kind=kind, indices=indices, skip_months=skip_months)
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
    p.add_argument('--start', default=DATA_START, metavar='YYYY-MM-DD',
                   help='first day of the time frame (default %(default)s)')
    p.add_argument('--last-expiry-year', type=int, default=LAST_EXPIRY_YEAR,
                   help='look for December contracts up to this year (default %(default)s)')
    p.add_argument('--skip-months', type=int, default=SKIP_MONTHS,
                   help='hide the contracts expiring within this many months on every date (default %(default)s)')
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
        run(data_start=a.start, last_expiry_year=a.last_expiry_year, out=a.out, today=today,
            tickers_only=a.tickers_only, show_charts_=False, skip_months=a.skip_months,
            measure=a.measure, kind=a.chart)
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
import math                                       # noqa: E402
import tempfile                                   # noqa: E402
import zipfile                                    # noqa: E402
from contextlib import redirect_stdout            # noqa: E402

TEST_TODAY = dt.date(2026, 9, 17)
FAKE_PRODUCTS = [('HI', 'HSI'), ('XP', 'AS51'), ('QZ', 'SIMSCI')]
FAKE_KRW_PRODUCTS = [('KM', 'KOSPI2')]        # a KRW product with a big multiplier, for the USD check
FAKE_MID_PRODUCTS = [('MM', 'MIDMONTH')]     # a product whose contracts expire on the 12th, for the front-month rule
QUARTERLY = (3, 6, 9, 12)
HOLIDAYS = {(1, 1), (4, 4), (12, 25)}          # the futures' holidays ...
INDEX_HOLIDAYS = {(1, 1), (12, 25)}            # ... the index prints on 4 Apr too: a day without a single contract print
DAY = dt.timedelta(days=1)
TEST_START = dt.date(2023, 9, 1)               # + 4 skipped months -> the universe's first expiry, Jan 24
TEST_KW = dict(data_start=TEST_START, skip_months=4, all_ahead=3, quarterly_ahead=3, last_expiry_year=2026)
TEST_MONTHS = expiry_months(TEST_START, TEST_TODAY, 4, 3, 3, 2026)      # Jan 24 .. Dec 26, like the universe


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


SERIAL_LISTING_DAYS = [200]     # the tests keep serial months visible under a 4-month rule; demo() uses 100 (HKEX-like)


def listing(y, m):
    days = 1100 if m == 12 else (400 if m in QUARTERLY else SERIAL_LISTING_DAYS[0])   # Dec listed 3y out
    return last_trade(y, m) - dt.timedelta(days=days)


def spec(y, m, **over):
    s = dict(year=y, month=m, last_trade=last_trade(y, m), listing=listing(y, m))
    s.update(over)
    return s


def mid_spec(y, m):
    """A contract expiring on the 12th (KOSPI / TAIFEX style), listed 400 days before."""
    lt = weekday_on_or_before(dt.date(y, m, 12))
    return dict(year=y, month=m, last_trade=lt, listing=lt - dt.timedelta(days=400))


def build_universe():
    """ticker -> contract spec.  Which forms exist follows the real Bloomberg behaviour."""
    u = {}
    for root, _ in FAKE_PRODUCTS + FAKE_KRW_PRODUCTS + FAKE_MID_PRODUCTS:
        for y, m in contract_months(2024, 2026):
            if root == 'XP' and m not in QUARTERLY:
                continue                                            # (v)  quarterly-only product
            t1, t2 = candidate_tickers(root, y, m)
            s = mid_spec(y, m) if root == 'MM' else spec(y, m)
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


def extend_universe(u):
    """The odd corners: a root whose one-digit ticker is not a future, and HSI's long-dated
    Decembers (Dec 27-31 live as one-digit codes; Dec 36 only as HIZ36, because HIZ6 *is* Dec 26,
    so the one-digit form has to be rejected on its last trade date and HIZ36 tried)."""
    u['NFH4 Index'] = spec(2024, 3, not_future=True)       # test_not_a_future(): exists, not a future
    u['NFH24 Index'] = spec(2024, 3)
    u['NFJ4 Index'] = spec(2024, 4, not_future=True)       # ... and NFJ24 unknown -> no future at all
    u['HIZ7 Index'] = spec(2027, 12, listing=dt.date(2022, 12, 1))
    u['HIZ8 Index'] = spec(2028, 12, listing=dt.date(2023, 12, 1))
    u['HIZ9 Index'] = spec(2029, 12, listing=dt.date(2024, 12, 2))
    u['HIZ0 Index'] = spec(2030, 12, listing=dt.date(2025, 12, 1))
    u['HIZ1 Index'] = spec(2031, 12, listing=dt.date(2026, 6, 1))
    u['HIZ36 Index'] = spec(2036, 12, listing=dt.date(2026, 6, 1))
    return u


UNIVERSE = extend_universe(build_universe())
# the underlying indices (kind 'index', with a currency) and their USD rates (kind 'fx')
FAKE_INDICES = {'HSI Index': 'HKD', 'AS51 Index': 'AUD', 'SIMSCI Index': 'SGD', 'KOSPI2 Index': 'KRW'}
FAKE_FUT = {'HI': ('HKD', 50.0), 'XP': ('AUD', 25.0), 'QZ': ('USD', 100.0), 'NF': ('USD', 1.0),
            'KM': ('USD', 250000.0), 'MM': ('USD', 1.0)}   # root -> (CRNCY as Bloomberg reports it, FUT_VAL_PT); KM says USD like the real terminal
FAKE_FX = ['USDHKD Curncy', 'USDAUD Curncy', 'USDSGD Curncy', 'USDKRW Curncy']
FAKE_LEVELS = {'HSI Index': 20000.0, 'AS51 Index': 8000.0, 'SIMSCI Index': 350.0, 'KOSPI2 Index': 400.0,
               'USDHKD Curncy': 7.8, 'USDAUD Curncy': 1.5, 'USDSGD Curncy': 1.35, 'USDKRW Curncy': 1350.0}
def add_markets(u):
    for _t, _ccy in FAKE_INDICES.items():
        u[_t] = dict(kind='index', currency=_ccy, year=2099, month=12,
                     listing=dt.date(2015, 1, 1), last_trade=dt.date(2099, 12, 31))
    for _t in FAKE_FX:
        u[_t] = dict(kind='fx', year=2099, month=12, listing=dt.date(2015, 1, 1), last_trade=dt.date(2099, 12, 31))
    return u


add_markets(UNIVERSE)
TICKER_ID = {t: i for i, t in enumerate(sorted(UNIVERSE))}


def rebuild_universe(serial_listing_days):
    """demo() only: relist the serial months like HKEX does (about three months ahead)."""
    SERIAL_LISTING_DAYS[0] = serial_listing_days
    UNIVERSE.clear()
    UNIVERSE.update(add_markets(extend_universe(build_universe())))
    TICKER_ID.clear()
    TICKER_ID.update({t: i for i, t in enumerate(sorted(UNIVERSE))})


FAKE_SCALE = {'HI': 1.0, 'XP': 0.7, 'QZ': 1.3, 'KM': 1.0, 'NF': 1.0, 'MM': 1.0}   # per root, in contracts


def fake_oi(ticker, d):
    """Deterministic prints that behave like real open interest, distinct per ticker and day (the
    ticker's id sits in the third decimal, so a misaligned cell cannot match).  Index levels drift
    up; FX rates move a little every day.  A December contract carries a sizeable, slowly growing
    structural position; another quarterly is small far out, grows as it becomes the second
    contract and only jumps in the roll, inside the last five weeks; a serial month stays small."""
    s = UNIVERSE[ticker]
    days = (d - s['listing']).days
    if s.get('kind') == 'fx':                         # realistic rate, moves every day
        return FAKE_LEVELS[ticker] * (1 + (days % 10) * 0.001)
    if s.get('kind') == 'index':                      # realistic level, drifts up, wobbles
        return FAKE_LEVELS[ticker] * (1 + days / 5000.0 + (days % 7) * 0.002)
    k = TICKER_ID[ticker]
    dte = (s['last_trade'] - d).days                  # days to expiry
    fam = band_family(s['month'])
    if fam == 'dec':                                  # a term structure: thin far out, building as it nears
        base = 30000.0 / (1.0 + 1.2 * max(0.0, dte / 365.0 - 0.5))
    elif fam == 'quarter':
        base = 2000.0 + 12000.0 / (1.0 + math.exp((dte - 150) / 25.0)) + 45000.0 / (1.0 + math.exp((dte - 35) / 6.0))
    else:
        base = 2500.0 + 1500.0 / (1.0 + math.exp((dte - 60) / 10.0))
    scale = FAKE_SCALE.get(ticker[:2], 1.0) * (0.9 + 0.2 * ((k * 7) % 11) / 10.0)
    drift = 1.0 + 0.0015 * math.sin(days / 9.0 + k)  # gentle day-to-day movement
    return round(base * scale * drift) + k * 0.001


def is_session(d, kind=None):
    return d.weekday() < 5 and (d.month, d.day) not in (INDEX_HOLIDAYS if kind in ('index', 'fx') else HOLIDAYS)


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
        if is_session(d, s.get('kind')):
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
    check('add_months', add_months(2024, 11, 3) == (2025, 2) and add_months(2024, 1, -1) == (2023, 12)
          and add_months(2023, 9, 4) == (2024, 1))
    check('month_end', month_end(2024, 2) == dt.date(2024, 2, 29) and month_end(2025, 12) == dt.date(2025, 12, 31))
    check('history_cutoff: Jun 24 / 2 -> 30 Apr 24, Jan 26 / 2 -> 30 Nov 25, 0 -> no cutoff',
          history_cutoff(2024, 6, 2) == dt.date(2024, 4, 30) and history_cutoff(2026, 1, 2) == dt.date(2025, 11, 30)
          and history_cutoff(2024, 6, 0) is None)
    ends = {m: history_cutoff(2025, m, 4) for m in range(3, 9)}
    check('the March rule with 4: Mar-Jun 25 end before March, Jul 25 ends 31 Mar (all of March), Aug 25 ends 30 Apr',
          all(ends[m] < dt.date(2025, 3, 1) for m in (3, 4, 5, 6)) and ends[7] == dt.date(2025, 3, 31)
          and ends[8] == dt.date(2025, 4, 30), ends)
    check('CONFIG: 2021-01-01 .. today, expiries to 2036 (15 / 36 months ahead), 4 front months hidden, USD notional; '
          'KOSPI2 / HSI / AS51 / TWSE not listed as USD contracts',
          as_date(DATA_START) == dt.date(2021, 1, 1) and (ALL_MONTHS_AHEAD, QUARTERLY_AHEAD, LAST_EXPIRY_YEAR) == (15, 36, 2036)
          and SKIP_MONTHS == 4 and MEASURE == 'notional'
          and not {'KOSPI2', 'HSI', 'HSCEI', 'HSTECH', 'AS51', 'TWSE'} & set(CONTRACT_CURRENCY))
    months = expiry_months(dt.date(2021, 1, 1), TEST_TODAY, 4, 15, 36, 2036)
    serial_after = [ym for ym in months if ym > (2027, 12) and ym[1] not in QUARTERLY]
    nondec_after = [ym for ym in months if ym > (2029, 9) and ym[1] != 12]
    check('expiry_months: May 21 first (Jan 21 + 4), every month to Dec 27, quarterly to Sep 29, then Decembers to 2036, ordered',
          months[0] == (2021, 5) and months[-1] == (2036, 12) and (2027, 12) in months and (2028, 1) not in months
          and (2028, 3) in months and (2029, 9) in months and (2029, 12) in months and (2030, 3) not in months
          and (2030, 12) in months and not serial_after and not nondec_after
          and all(a < b for a, b in zip(months, months[1:]))
          and len(months) == 80 + 7 + 8 == len([ym for ym in months if ym <= (2027, 12)]) + 7 + 8, (months[:2], months[-3:], len(months)))
    check('expiry_months for the fixture: Jan 24 .. Dec 26, 36 months',
          TEST_MONTHS == contract_months(2024, 2026) and expiry_months(TEST_START, TEST_TODAY, 4, 3, 3, 2036)
          == contract_months(2024, 2026) + [(y, 12) for y in range(2027, 2037)])
    check('as_float', as_float(50) == 50.0 and as_float('12.5') == 12.5 and as_float(None) is None
          and as_float(float('nan')) is None and as_float(0) is None and as_float('n.a.') is None)
    check('index ticker: <tab> Index by default (SX5E, SX5T, SPX included), INDEX_TICKERS for the exceptions',
          index_ticker('KOSPI2') == 'KOSPI2 Index' and index_ticker('FPO') == 'XIN9I Index'
          and index_ticker('SX5T') == 'SX5T Index' and index_ticker('SPX') == 'SPX Index'
          and fx_for('EUR') == ('USDEUR Curncy', 'divide'))
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
    global MIN_DAYS_TO_CHART
    saved_min = MIN_DAYS_TO_CHART
    MIN_DAYS_TO_CHART = 1                      # these unit checks use 2-4 day contracts
    try:
        used, series, dates, note = product_series([c], 'notional')
        check('product_series: notional unavailable -> falls back to OI with a note',
              used == 'oi' and series == [(c, c.rows)] and dates == [d0, d1, d2, d3] and note.startswith('USD notional unavailable'), note)
        used, series, dates, note = product_series([c], 'oi')
        check('product_series: oi', used == 'oi' and note == '')
        d5, d6 = dt.date(2024, 1, 5), dt.date(2024, 1, 8)
        ix2 = IndexSeries(product='K', ticker='K Index', status=OK, rows=[(dt.date(2023, 12, 29), 1.0), (d0, 1.0), (d2, 1.0),
                                                                            (d5, 1.0), (d6, 1.0), (dt.date(2024, 1, 9), 1.0)])
        c2 = Contract(product='K', root='K', year=2024, month=1, label='Jan 24', ticker_1='a', ticker_2='b', ticker='a',
                      status=OK, rows=[(d1, 4.0), (d6, 6.0)])
        _, _, dates, _ = product_series([c2], 'oi', ix2)
        check('product_series with the index calendar: first to last value date, index days inside are rows too',
              dates == [d1, d2, d5, d6], dates)
    finally:
        MIN_DAYS_TO_CHART = saved_min
    days6 = [dt.date(2024, 1, k) for k in (2, 3, 4, 5, 8, 9)]
    c6 = Contract(product='K', root='K', year=2024, month=1, label='Jan 24', ticker_1='a', ticker_2='b', ticker='a',
                  status=OK, rows=[(d, 10.0) for d in days6])
    thin = Contract(product='K', root='K', year=2024, month=2, label='Feb 24', ticker_1='a', ticker_2='b', ticker='a',
                    status=OK, rows=[(d0, 1.0), (d1, 2.0)])
    used, series, dates, note = product_series([c6, thin], 'oi')
    check('product_series: a contract with fewer than MIN_DAYS_TO_CHART (5) days is left off the chart',
          MIN_DAYS_TO_CHART == 5 and [x for x, _ in series] == [c6] and dates == days6)
    _, text = quiet(print_summary, [('K', [c6, thin])], Bloomberg(blpapi_module=FakeAPI), None)
    check('summary names the contracts left off for being too short', 'not charted, under 5 days in the window: Feb 24 (2)' in text, text)
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
    check('14 real products, distinct legal tab names',
          len({n for _, n in PRODUCTS}) == len(PRODUCTS) == 14
          and all(safe_sheet_name(n) == n for _, n in PRODUCTS))
    check('real roots: the request note + MTW + VG / VHO / ES, tabs named after the underlying index',
          [p[0] for p in PRODUCTS] == ['HI', 'HC', 'HCT', 'KM', 'XP', 'FT', 'TWT', 'MTW', 'FPO', 'HJA', 'QZ', 'VG', 'VHO', 'ES']
          and [p[1] for p in PRODUCTS][-3:] == ['SX5E', 'SX5T', 'SPX'])
    check('optional yellow key: third item in PRODUCTS',
          candidate_tickers('CL', 2026, 1, 'Comdty') == ('CLF6 Comdty', 'CLF26 Comdty')
          and product_rows([('HI', 'HSI'), ('CL', 'WTI', 'Comdty')]) == [('HI', 'HSI', 'Index'), ('CL', 'WTI', 'Comdty')]
          and build_contracts([('CL', 'WTI', 'Comdty')], [(2026, 1)])[0][1][0].ticker_2 == 'CLF26 Comdty')
    cs = [Contract(product='x', root='x', year=2025, month=1, label='', ticker_1='', ticker_2='') for _ in range(23)]
    cols = band_colors(cs)
    check('band colours: every contract its own colour in expiry order, 20 distinct 6-hex values, wrapping after 20',
          [band_family(m) for m in (1, 3, 12, 7)] == ['serial', 'quarter', 'dec', 'serial']
          and cols[:20] == BAND_COLORS and cols[20:] == BAND_COLORS[:3] and len(set(BAND_COLORS)) == 20
          and all(len(h) == 6 and int(h, 16) >= 0 for h in BAND_COLORS), cols[:3])
    d_m = [dt.date(2024, 1, 2), dt.date(2024, 1, 3), dt.date(2024, 2, 1), dt.date(2024, 2, 2), dt.date(2024, 4, 1)]
    check('month ticks: one per month start, MONTH_ABBR text',
          month_starts(d_m) == [0, 2, 4] and month_tick(dt.date(2023, 9, 4)) == 'Sep-23' and month_tick(dt.date(2026, 12, 1)) == 'Dec-26')
    check('axis_unit / money: bn for a big product, m for a small one, contracts as they are',
          axis_unit(5e10, 'notional') == ('USD bn', '#,##0.0,,,', 1e9) and axis_unit(4e8, 'notional') == ('USD m', '#,##0,,', 1e6)
          and axis_unit(12345, 'oi') == ('Contracts', '#,##0', 1.0)
          and money(12.34e9, 1e9, '') == '12.3bn' and money(2788.2e9, 1e9, '') == '2,788bn' and money(850e6, 1e6, '') == '850m'
          and money(1234.6, 1.0, '') == '1,235' and axis_formatter(1e9, 60e9)(12.34e9, 0) == '12.3'
          and axis_formatter(1e9, 6000e9)(2500e9, 0) == '2,500' and axis_formatter(1.0, 5)(1234.0, 0) == '1,234')
    check('subtitle names the rule and the source; with 0 it says everything is shown',
          subtitle_text(4).startswith('Contracts expiring within 4 months excluded') and 'Source: Bloomberg, Nomura' in subtitle_text()
          and subtitle_text(0).startswith('All listed contracts shown'))
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
    months = TEST_MONTHS
    results = resolve_contracts(bbg, FAKE_PRODUCTS, months, TEST_TODAY)
    by = {(n, c.label): c for n, cs in results for c in cs}
    refs = [e for e in bbg.session.log if e['op'] == 'ReferenceDataRequest']
    allc = [c for _, cs in results for c in cs]
    expected = [expected_form(c, TEST_TODAY) for c in allc]
    n1 = -(-len(expected) // REF_CHUNK)
    pass1 = [s for e in refs[:n1] for s in e['securities']]
    pass2 = [s for e in refs[n1:] for s in e['securities']]
    misses = [c for c in allc if expected_form(c, TEST_TODAY) in bbg.bad_securities
              or (c.status == NOT_FOUND)]
    check('pass 1: the expected form of every contract, once, chunked at REF_CHUNK',
          pass1 == expected and all(len(e['securities']) <= REF_CHUNK for e in refs), (len(pass1), len(expected)))
    check('pass 2: only the other form of the contracts pass 1 could not resolve',
          sorted(pass2) == sorted(other_form(c, TEST_TODAY) for c in misses) and 0 < len(pass2) < len(pass1),
          (len(pass2), len(misses)))
    check('reference fields as configured', all(e['fields'] == REF_FIELDS for e in refs))
    check('expected_form: two digits once the month has passed, one digit while live',
          expected_form(by[('HSI', 'Sep 25')], TEST_TODAY) == 'HIU25 Index'
          and expected_form(by[('HSI', 'Sep 26')], TEST_TODAY) == 'HIU6 Index'
          and expected_form(by[('HSI', 'Aug 26')], TEST_TODAY) == 'HIQ26 Index')
    c = by[('HSI', 'Sep 25')]
    check('(i)   expired -> two-digit form', c.ticker == 'HIU25 Index' and c.status == OK, c)
    check('(ii)  live -> one-digit form',
          by[('HSI', 'Oct 26')].ticker == 'HIV6 Index' and by[('HSI', 'Sep 26')].ticker == 'HIU6 Index')
    c = by[('HSI', 'Aug 26')]
    check('(iii) both forms valid, expired: the two-digit form resolves in pass 1, the other is never asked for',
          c.ticker == 'HIQ26 Index' and c.note == '' and 'HIQ6 Index' not in pass1 + pass2, c)
    check('(iii) both forms valid, live -> one-digit', by[('HSI', 'Dec 26')].ticker == 'HIZ6 Index')
    c = by[('HSI', 'Jan 26')]
    check('(iv)  expired 2026 contract: two-digit form first, so the wrong-decade one-digit code is never asked for',
          c.ticker == 'HIF26 Index' and c.status == OK and c.last_trade.year == 2026 and 'HIF6 Index' not in pass1 + pass2, c)
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
    check('(vii) unknown tickers collected, not raised; a form that resolved in pass 1 is never a bad security',
          'XPF24 Index' in bbg.bad_securities and 'HIU25 Index' not in bbg.bad_securities
          and 'HIU5 Index' not in bbg.bad_securities)
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
            fetch_open_interest(bbg, c, TEST_START, TEST_TODAY, 4)
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
        exp = (TEST_START.strftime('%Y%m%d'),
               min(c.last_trade, TEST_TODAY, history_cutoff(c.year, c.month, 4)).strftime('%Y%m%d'))
        got = (e['settings']['startDate'], e['settings']['endDate'])
        if got != exp:
            bad.append((c.ticker, got, exp))
    check('request window = [DATA_START, min(last trade, today, end of month-4)] as YYYYMMDD', not bad, bad[:3])
    c = by[('HSI', 'Jun 24')]
    check('Jun 24: no Mar-Jun 24 rows, last row in Feb 24',
          c.req_end == dt.date(2024, 2, 29) and c.rows[-1][0] == last_session_on_or_before(dt.date(2024, 2, 29))
          and all((d.year, d.month) not in ((2024, 3), (2024, 4), (2024, 5), (2024, 6)) for d, _ in c.rows),
          (c.req_end, c.rows[-1]))
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
    check('serial contract: starts on its listing day, ends 4 months before expiry (~2-3 months of rows)',
          c.rows[0][0] == first_session_on_or_after(UNIVERSE[c.ticker]['listing'])
          and c.rows[-1][0] == last_session_on_or_before(dt.date(2024, 10, 31))
          and 40 < len(c.rows) < 80, (c.rows[0], c.rows[-1], len(c.rows)))
    c = by[('HSI', 'Dec 25')]
    check('Dec contract listed 3y out: starts at DATA_START (2023-09-01)',
          c.rows[0][0] == first_session_on_or_after(TEST_START) and c.req_start == TEST_START, (c.rows[0], c.req_start))
    c = by[('HSI', 'Jun 25')]
    check('expired contract: ends at the end of the month four before expiry (28 Feb 25)',
          c.req_end == dt.date(2025, 2, 28) and c.rows[-1][0] == last_session_on_or_before(dt.date(2025, 2, 28)))
    c = by[('HSI', 'Dec 26')]
    check('live contract: ends 31 Aug 26 (four months before December), not today',
          c.req_end == dt.date(2026, 8, 31) and c.rows[-1][0] == last_session_on_or_before(dt.date(2026, 8, 31)))
    c0 = Contract(**{k: getattr(by[('HSI', 'Jun 25')], k) for k in
                        ('product', 'root', 'year', 'month', 'label', 'ticker_1', 'ticker_2', 'ticker', 'status', 'last_trade')})
    fetch_open_interest(bbg, c0, TEST_START, TEST_TODAY, 0)
    check('--skip-months 0: history runs to the last trade date',
          c0.req_end == c0.last_trade and c0.rows[-1][0] == last_session_on_or_before(c0.last_trade))
    c3 = Contract(**{k: getattr(by[('HSI', 'Dec 25')], k) for k in
                        ('product', 'root', 'year', 'month', 'label', 'ticker_1', 'ticker_2', 'ticker', 'status', 'last_trade')})
    fetch_open_interest(bbg, c3, dt.date(2024, 6, 3), TEST_TODAY, 4)
    check('a later DATA_START narrows the window', c3.req_start == dt.date(2024, 6, 3)
          and bbg.session.log[-1]['settings']['startDate'] == '20240603' and c3.rows[0][0] == dt.date(2024, 6, 3))
    c4 = Contract(product='HSI', root='HI', year=2024, month=1, label='Jan 24', ticker_1='HIF4 Index',
                  ticker_2='HIF24 Index', ticker='HIF24 Index', status=OK, last_trade=dt.date(2024, 1, 30))
    fetch_open_interest(bbg, c4, dt.date(2023, 10, 2), TEST_TODAY, 4)
    check('a contract whose window ends before DATA_START is NO DATA with a reason, not a request',
          c4.status == NO_DATA and 'before DATA_START' in c4.note and bbg.session.log[-1]['securities'] != ['HIF24 Index'], c4.note)
    return results


def test_visibility():
    """The front-month rule, on a product that expires mid-month: every day of March shows the
    same set - nothing expiring Mar-Jun, July onwards."""
    bbg = Bloomberg(blpapi_module=FakeAPI).connect()
    results = resolve_contracts(bbg, FAKE_MID_PRODUCTS, TEST_MONTHS, TEST_TODAY)
    cs = results[0][1]
    for c in cs:
        fetch_open_interest(bbg, c, TEST_START, TEST_TODAY, 4)
    check('mid-month product: 36 contracts resolved, expiring on the 12th or the weekday before',
          all(c.status == OK and 8 <= c.last_trade.day <= 12 for c in cs), [(c.label, c.last_trade) for c in cs[:3]])

    def visible(day):
        return {c.label for c in cs if day in dict(c.rows)}
    d_first, d_mid, d_last, d_april = dt.date(2025, 3, 3), dt.date(2025, 3, 14), dt.date(2025, 3, 31), dt.date(2025, 4, 1)
    hidden = {'Mar 25', 'Apr 25', 'May 25', 'Jun 25'}
    check('on 3, 14 and 31 March 2025: no Mar/Apr/May/Jun 25 contract, Jul 25 present on all three days',
          all(not (visible(d) & hidden) and 'Jul 25' in visible(d) for d in (d_first, d_mid, d_last)),
          {d.isoformat(): sorted(visible(d))[:6] for d in (d_first, d_mid, d_last)})
    check('14 March is after the Mar 25 contract expired (12 Mar) and the set is still the same rule',
          d_mid > [c for c in cs if c.label == 'Mar 25'][0].last_trade and 'Jul 25' in visible(d_mid))
    check('on 1 April 2025 Jul 25 is gone and Aug 25 is the first contract shown',
          'Jul 25' not in visible(d_april) and 'Aug 25' in visible(d_april) and min(
              (c.year, c.month) for c in cs if c.label in visible(d_april)) == (2025, 8), sorted(visible(d_april))[:4])
    check('the nearest contract shown is always 4 months out: Feb 25 shows in Oct 24, not in Nov 24',
          'Feb 25' in visible(dt.date(2024, 10, 31)) and 'Feb 25' not in visible(dt.date(2024, 11, 1)))


def test_long_dated():
    """Expiries to 2036: the Decembers that exist resolve (Dec 36 only via its two-digit code), the
    rest are NOT FOUND, and a contract listed in June 2026 simply has three months of rows."""
    bbg = Bloomberg(blpapi_module=FakeAPI).connect()
    months = expiry_months(TEST_START, TEST_TODAY, 4, 3, 3, 2036)
    results = resolve_contracts(bbg, [('HI', 'HSI')], months, TEST_TODAY)
    cs = results[0][1]
    by = {c.label: c for c in cs}
    check('46 expiries: 36 months + Dec 27 .. Dec 36', len(cs) == 46 and cs[-1].label == 'Dec 36')
    check('Dec 27 .. Dec 31 resolve on their one-digit codes',
          [by['Dec %d' % y].ticker for y in (27, 28, 29, 30, 31)] == ['HIZ7 Index', 'HIZ8 Index', 'HIZ9 Index', 'HIZ0 Index', 'HIZ1 Index'])
    c = by['Dec 36']
    check('Dec 36: HIZ6 is Dec 26 (last trade outside the month) -> rejected, HIZ36 used in pass 2',
          c.status == OK and c.ticker == 'HIZ36 Index' and c.last_trade.year == 2036, c)
    nf = [c.label for c in cs if c.status == NOT_FOUND]
    check('unlisted Decembers are NOT FOUND with both forms explained',
          nf == ['Dec 32', 'Dec 33', 'Dec 34', 'Dec 35']
          and by['Dec 32'].note == 'HIZ2 Index -> Unknown/Invalid Security [nid:1234]; HIZ32 Index -> Unknown/Invalid Security [nid:1234]',
          (nf, by['Dec 32'].note))
    for c in cs:
        fetch_open_interest(bbg, c, TEST_START, TEST_TODAY, 4)
    check('Dec 36 listed June 2026: rows from its listing day to today, nothing invented before',
          c.rows[0][0] == first_session_on_or_after(dt.date(2026, 6, 1)) and c.rows[-1][0] == last_session_on_or_before(TEST_TODAY)
          and by['Dec 27'].rows[0][0] == first_session_on_or_after(TEST_START), (c.rows[0], c.rows[-1]))
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, 'long.xlsx')
    write_workbook(path, results, measure='oi')
    wb = load_workbook(path)
    ws = wb['HSI']
    _, series, dates, _ = product_series(cs, 'oi')
    check('workbook: the live Decembers are the last columns and the dates run to today',
          [ws.cell(2, j).value for j in range(2, len(series) + 2)][-6:] == ['Dec 27', 'Dec 28', 'Dec 29', 'Dec 30', 'Dec 31', 'Dec 36']
          and dates[-1] == last_session_on_or_before(TEST_TODAY) and ws.max_row == len(dates) + 2)
    os.remove(path)
    os.rmdir(tmp)


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
    check('chart XML: gaps, date axis, no markers, straight lines, light gridlines, grey x axis, no legend, no border',
          all(b'dispBlanksAs val="gap"' in x and b'<dateAx>' in x and b'symbol val="none"' in x
              and b'smooth val="0"' in x and b'majorGridlines' in x and x.count(b'noFill') >= 3
              and x.count(b'srgbClr val="BFBFBF"') == 1 and b'srgbClr val="E6E6E6"' in x and b'<legend>' in x
              and b'legendPos val="b"' in x and b'latin typeface="Arial"' in x for x in chart_xml.values()))
    for name, cs in results:
        ws = wb[name]
        _, series, dates, _ = product_series(cs, 'oi')
        found = [c for c, _ in series]
        n, N = len(found), len(dates)
        check('%s: row 1 tickers, row 2 labels, expiry order' % name,
              [ws.cell(1, j).value for j in range(2, n + 2)] == [c.ticker for c in found]
              and [ws.cell(2, j).value for j in range(2, n + 2)] == [c.label for c in found]
              and ws['A1'].value == 'Ticker' and ws['A2'].value == 'Date')
        starts = month_starts(dates)
        check('%s: Total column right after the %d found contracts, then the Month axis column' % (name, n),
              ws.max_column == n + 3 and ws.cell(1, n + 2).value == TOTAL_LABEL and ws.cell(2, n + 2).value == TOTAL_LABEL
              and ws.column_dimensions[get_column_letter(n + 2)].width == 12
              and ws.cell(2, n + 3).value == 'Month'
              and [ws.cell(i + 3, n + 3).value for i in starts] == [month_tick(dates[i]) for i in starts]
              and sum(1 for i in range(3, N + 3) if ws.cell(i, n + 3).value is not None) == len(starts),
              (ws.max_column, ws.cell(2, n + 2).value))
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
        subtitle = ch.title.tx.rich.p[1].r[0].t
        ytitle = ch.y_axis.title.tx.rich.p[0].r[0].t
        check('%s: title + subtitle, Contracts axis title and number format, gridlines, legend along the bottom' % name,
              title == CHART_TITLE['oi'].format(name=name) and subtitle == subtitle_text()
              and ytitle == Y_AXIS_TITLE['oi'] and ch.y_axis.number_format.formatCode == '#,##0'
              and ch.y_axis.majorGridlines is not None and ch.x_axis.txPr is not None
              and ch.legend is not None and ch.legend.position == 'b', (title, subtitle, ytitle))
        colors = band_colors(found)
        labels, _ = band_labels(series, dates)
        ok_series, why = True, ''
        for k, s in enumerate(ch.series):
            col = get_column_letter(k + 2)
            want = ("'%s'!%s2" % (name, col), "'%s'!$%s$3:$%s$%d" % (name, col, col, N + 2), "'%s'!$A$3:$A$%d" % (name, N + 2))
            got = (s.tx.strRef.f, s.val.numRef.f, s.cat.numRef.f)
            colour = s.graphicalProperties.line.solidFill.srgbClr
            mode, kk = labels[k][0], labels[k][1]
            named = (s.dLbls is not None and len(s.dLbls.dLbl) == 1 and s.dLbls.dLbl[0].idx == kk
                     and s.dLbls.dLbl[0].showSerName is True and s.dLbls.dLbl[0].spPr is not None
                     and s.dLbls.dLbl[0].spPr.ln.solidFill.srgbClr == colors[k])
            if got != want or s.smooth is not False or s.marker.symbol is not None \
                    or s.graphicalProperties.line.width != 12700 or colour != colors[k] \
                    or (mode is None) == named:
                ok_series, why = False, (got, want, colour, mode, named)
                break
        check('%s: series titles from row 2, values rows 3..%d, dates as categories, family colours, named lines' % (name, N + 2),
              ok_series, why)
        check('%s: chart anchored one column right of the data, date axis labelled every month' % name,
              ch.anchor._from.col == n + 4 and ch.anchor._from.row == 1 and ch.x_axis.majorUnit == 1
              and ch.x_axis.majorTimeUnit == 'months', (ch.anchor._from.col, ch.anchor._from.row))
        check('%s: chart 30 x 17 cm' % name, ch.anchor.ext.cx == 10800000 and ch.anchor.ext.cy == 6120000,
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
    results = resolve_contracts(bbg, FAKE_PRODUCTS, TEST_MONTHS, TEST_TODAY)
    for _, cs in results:
        for c in cs:
            fetch_open_interest(bbg, c, TEST_START, TEST_TODAY, 4)
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
    kr = resolve_indices(bbg, resolve_contracts(bbg, FAKE_KRW_PRODUCTS, [(2025, m) for m in range(1, 13)], TEST_TODAY))['KOSPI2']
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
    check('index window = DATA_START .. latest contract end (31 Aug 26: four months before Dec 26)',
          ix.req_start == TEST_START == min(c.req_start for c in cs if c.rows)
          and ix.req_end == max(c.req_end for c in cs if c.rows) == dt.date(2026, 8, 31), (ix.req_start, ix.req_end))
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
        _, series, dates, _ = product_series(cs, 'notional', indices[name])
        n, N = len(series), len(dates)
        check('%s: one column per contract + Total + Month, rows = first..last notional date on the index calendar' % name,
              ws.max_column == n + 3 and ws.max_row == N + 2
              and [ws.cell(1, j).value for j in range(2, n + 2)] == [c.ticker for c, _ in series], (ws.max_column, n))
        gaps = [i for i, d in enumerate(dates, start=3) if (d.month, d.day) == (4, 4)]
        check('%s: 4 April is a row (index day, no contract print) with every cell and the Total blank - a visible hole' % name,
              len(gaps) == 2 and all(ws.cell(i, j).value is None for i in gaps for j in range(2, n + 3))
              and dates[0] == min(d for _, rows in series for d, _ in rows)
              and dates[-1] == max(d for _, rows in series for d, _ in rows), (gaps, len(dates)))
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
        check('%s: stacked chart, no total line, notional title, USD bn axis, light gridlines, legend' % name,
              isinstance(ch, BarChart) and len(ch._charts) == 1 and len(ch.series) == n
              and title == CHART_TITLE['notional'].format(name=name)
              and ch.y_axis.title.tx.rich.p[0].r[0].t == Y_AXIS_TITLE['notional']
              and ch.y_axis.number_format.formatCode == '#,##0.0,,,' and ch.y_axis.majorGridlines is not None
              and ch.legend is not None and ch.anchor._from.col == n + 4, (title, ch.anchor._from.col))
    check('chart XML: one bar chart (no line chart) on one category + one value axis, gridlines, USD bn format, legend',
          all(x.count(b'<barChart>') == 1 and x.count(b'<lineChart>') == 0 and x.count(b'<catAx>') == 1
              and x.count(b'<valAx>') == 1 and b'majorGridlines' in x and b'#,##0.0,,,' in x and b'<legend>' in x
              for x in chart_xml.values()) and len(chart_xml) == 3)
    ws = wb[AUDIT_SHEET]
    rows = {(r[0], r[1]): r for r in ws.iter_rows(min_row=2, values_only=True)}
    c, r = [x for x in results[0][1] if x.label == 'Sep 25'][0], rows[('HSI', 'Sep 25')]
    check('Contracts tab: multiplier, ccy, last and max notional',
          r[16] == 50.0 and r[17] == 'HKD' and abs(r[18] - c.last_notional) < 1e-9 * c.last_notional
          and abs(r[19] - c.max_notional) < 1e-9 * c.max_notional, r[16:20])
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
          and t == FALLBACK_TITLE.format(name='HSI') and wb3['HSI'].max_column == 39
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
    out, text = quiet(run, products=FAKE_PRODUCTS, today=TEST_TODAY, blpapi_module=FakeAPI, out=path4, **TEST_KW)
    sess = FakeSession.instances[-1]
    wb4 = load_workbook(path4)
    check('run(): USD notional by default - index pulled per product, summary explains the formula, Indices tab',
          out == path4 and 'USD notional' in text and 'notional:   OI x 50 x HSI Index' in text and '/ USDHKD Curncy' in text
          and 'OI x 100 x SIMSCI Index' in text and '(USD-denominated, no FX)' in text and 'showing USD notional' in text
          and '[contract ccy HKD from index CRNCY]' in text and '[contract ccy USD from CONTRACT_CURRENCY]' in text
          and INDEX_SHEET in wb4.sheetnames
          and wb4['HSI']._charts[0].title.tx.rich.p[0].r[0].t == CHART_TITLE['notional'].format(name='HSI')
          and sum(1 for e in sess.log if e['op'] == 'HistoricalDataRequest') == 83 + 5, text[-900:])
    out, text = quiet(run, products=FAKE_PRODUCTS, today=TEST_TODAY, blpapi_module=FakeAPI, out=path4, measure='oi', **TEST_KW)
    wb5 = load_workbook(path4)
    check('run(measure="oi") / --measure oi: contracts, no index requests, no Indices tab',
          INDEX_SHEET not in wb5.sheetnames and 'showing OI in contracts' in text and 'notional:' not in text
          and wb5['HSI']._charts[0].title.tx.rich.p[0].r[0].t == CHART_TITLE['oi'].format(name='HSI'))
    try:
        run(products=FAKE_PRODUCTS, today=TEST_TODAY, blpapi_module=FakeAPI, out=path4, measure='usd', **TEST_KW)
        raised = ''
    except ValueError as e:
        raised = str(e)
    check('run(measure=?) is refused', "'notional' or 'oi'" in raised, raised)
    # ---- the USD check, on a KRW product with a realistic multiplier: KOSPI2 ----
    FakeSession.instances.clear()
    path5 = os.path.join(tmp, 'krw.xlsx')
    out, text = quiet(run, products=FAKE_KRW_PRODUCTS, today=TEST_TODAY, blpapi_module=FakeAPI, out=path5, **TEST_KW)
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
    check('KOSPI2: FUT_VAL_PT 250,000 KRW agrees with the exchange table -> no multiplier / currency warning',
          'the exchange multiplier' not in text and 'is denominated in' not in text)
    cs_hi = results[0][1]
    warn = contract_warnings(cs_hi, indices['HSI'])
    check('EXPECTED_CONTRACT: HSI at HKD 50 agrees -> nothing to say', warn == [], warn)
    c0 = [c for c in cs_hi if c.status == OK][0]
    saved_m = c0.multiplier
    c0.multiplier = 10.0
    warn = contract_warnings(cs_hi, indices['HSI'])
    c0.multiplier = saved_m
    check('a multiplier that disagrees with the exchange is a WARNING naming the root and both numbers',
          len(warn) == 1 and warn[0].startswith('FUT_VAL_PT for HI is 10 / 50 on Bloomberg; the exchange multiplier is HKD 50'), warn)
    ix_wrong = IndexSeries(product='HSI', ticker='HSI Index', status=OK, fut_currency='USD', ccy_source='CONTRACT_CURRENCY')
    warn = contract_warnings(cs_hi, ix_wrong)
    check('a working currency that disagrees with the exchange is a WARNING pointing at the CONFIG knobs',
          len(warn) == 1 and 'converts HI from USD (CONTRACT_CURRENCY) but the HI contract is denominated in HKD' in warn[0], warn)
    check('roots outside the table are not judged',
          contract_warnings([Contract(product='x', root='MTW', year=2025, month=1, label='', ticker_1='', ticker_2='',
                                      status=OK, multiplier=7.0)], None) == [])
    if importlib.util.find_spec('matplotlib') is not None:
        import warnings
        import matplotlib.pyplot as plt
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            n_fig, _ = quiet(show_charts, results, kind='lines')
        fig = plt.figure(plt.get_fignums()[0])
        ax = fig.axes[0]
        ylab, title, n_lines = ax.get_ylabel(), ax.get_title(loc='left'), len(ax.get_lines())
        grid = any(l.get_visible() for l in ax.get_ygridlines())
        subtitle = [t.get_text() for t in ax.texts if t.get_text().startswith('Contracts expiring')]
        plt.close('all')
        check('show_charts (lines): title left + subtitle, USD bn axis, light gridlines, one line per contract',
              n_fig == 3 and len(fig.axes) == 1 and ylab == Y_AXIS_TITLE['notional']
              and title == CHART_TITLE['notional'].format(name='HSI') and n_lines == 36 and grid
              and subtitle == [subtitle_text()], (n_fig, ylab, title, n_lines, grid, subtitle))
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)


def test_stacked():
    check('CONFIG: stacked columns by default', CHART_KIND == 'stacked')
    def hsv(hexcol):
        r, g, b = (int(hexcol[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        mx, mn = max(r, g, b), min(r, g, b)
        return (0 if mx == 0 else (mx - mn) / mx), mx
    strong = [h for h in BAND_COLORS if hsv(h)[0] > 0.6 and hsv(h)[1] > 0.6]
    check('BAND_COLORS: the Nomura family - Nomura red first, greys, navy / steel, gold; at most three strong tones',
          BAND_COLORS[0] == NOMURA_RED == 'C8102E' and {'2F3136', '1B2A47', '7A1E2B'} <= set(BAND_COLORS)
          and len(strong) <= 3 and len(set(BAND_COLORS)) == 20, strong)
    bbg = Bloomberg(blpapi_module=FakeAPI).connect()
    results = resolve_contracts(bbg, FAKE_PRODUCTS, TEST_MONTHS, TEST_TODAY)
    for _, cs in results:
        for c in cs:
            fetch_open_interest(bbg, c, TEST_START, TEST_TODAY, 4)
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
        check('%s: stacked column chart, no gap, overlap 100, %d bands in expiry order, nothing else on it' % (name, n),
              isinstance(ch, BarChart) and ch.grouping == 'stacked' and ch.overlap == 100 and ch.gapWidth == 0
              and ch.type == 'col' and len(ch.series) == n and len(ch._charts) == 1
              and [s.tx.strRef.f for s in ch.series] == ["'%s'!%s2" % (name, get_column_letter(j)) for j in range(2, n + 2)],
              (ch.grouping, ch.overlap, ch.gapWidth, len(ch.series)))
        labels, totals = band_labels(series, dates)
        colors = band_colors([c for c, _ in series])
        top = max(totals)
        good = all(s.graphicalProperties.solidFill.srgbClr == colour
                   and s.graphicalProperties.line.noFill is True
                   and (((mode is None or (mode == 'last' and h < LABEL_MIN_HEIGHT * top)) and s.dLbls is None) or
                        (len(s.dLbls.dLbl) == 1 and s.dLbls.dLbl[0].idx == k
                         and s.dLbls.dLbl[0].spPr.solidFill.srgbClr == 'FFFFFF'
                         and s.dLbls.dLbl[0].spPr.ln.solidFill.srgbClr == colour
                         and s.dLbls.dLbl[0].showSerName is True and s.dLbls.dLbl[0].showVal is False
                         and s.dLbls.showVal is False and s.dLbls.showSerName is False
                         and s.dLbls.dLbl[0].txPr.p[0].pPr.defRPr.solidFill.srgbClr == CHART_TEXT))
                   for s, colour, (mode, k, h, _b) in zip(ch.series, colors, labels))
        live = [c.label for (c, rows) in series if rows[-1][0] == dates[-1]]
        modes = [m for m, _, _, _ in labels]
        check('%s: one colour per contract; live bands named at the last day (max %d), tall ones at their peak, boxed names'
              % (name, MAX_END_LABELS), good and modes.count('last') == min(len(live), MAX_END_LABELS) and 0 < modes.count('peak')
              and all(k == N - 1 for m, k, _, _ in labels if m == 'last')
              and all(h >= LABEL_MIN_HEIGHT * max(totals) for m, k, h, _ in labels if m == 'peak'),
              (modes.count('last'), len(live), modes.count('peak'), modes.count(None)))
        ml = get_column_letter(n + 3)
        check('%s: x axis = the Month column (a label per month start, 45 degrees), legend along the bottom, chart after it, 30 x 17 cm' % name,
              all(s.cat.numRef.f == "'%s'!$%s$3:$%s$%d" % (name, ml, ml, N + 2) for s in ch.series)
              and ch.x_axis.tickLblSkip == 1 and ch.x_axis.txPr.bodyPr.rot == -2700000
              and ch.legend is not None and ch.legend.position == 'b' and ch.anchor._from.col == n + 4
              and ch.y_axis.majorGridlines is not None and ch.anchor.ext.cx == 10800000 and ch.anchor.ext.cy == 6120000,
              (ch.x_axis.tickLblSkip, ch.anchor._from.col))
    check('chart XML: one stacked barChart on one catAx and one valAx, data labels, gridlines, legend, Arial',
          all(x.count(b'<barChart>') == 1 and x.count(b'<lineChart>') == 0 and x.count(b'<catAx>') == 1
              and x.count(b'<valAx>') == 1 and b'grouping val="stacked"' in x and b'overlap val="100"' in x
              and b'gapWidth val="0"' in x and b'<dLbl>' in x and b'showSerName val="1"' in x
              and b'majorGridlines' in x and b'<legend>' in x and b'latin typeface="Arial"' in x
              for x in chart_xml.values()) and len(chart_xml) == 3,
          {k: (x.count(b'<barChart>'), x.count(b'<catAx>'), x.count(b'<valAx>')) for k, x in chart_xml.items()})
    xml = chart_xml['xl/charts/chart1.xml']
    _, series, dates, _ = product_series(results[0][1], 'oi')
    n_lbl = sum(1 for m, _, _, _ in band_labels(series, dates)[0] if m)
    check('chart XML: HSI has one label per named band', xml.count(b'<dLbl>') == n_lbl, (xml.count(b'<dLbl>'), n_lbl))
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
        run(products=FAKE_PRODUCTS, today=TEST_TODAY, blpapi_module=FakeAPI, out=path, kind='pie', **TEST_KW)
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
        texts = [t for t in ax.texts if not t.get_text().startswith('Contracts expiring')]
        labels = sorted(t.get_text() for t in texts)
        ylim = ax.get_ylim()
        xt = [t.get_text() for t in ax.get_xticklabels()]
        plt.close('all')
        lbls, totals = band_labels(series, dates)
        n_last = sum(1 for m, _, _, _ in lbls if m == 'last')
        exp_labels = sorted(c.label for (c, _), (m, _, _, _) in zip(series, lbls) if m)
        n_peak = sum(1 for m, _, _, _ in lbls if m == 'peak')
        boxed = sum(1 for t in texts if t.get_bbox_patch() is not None)
        check('show_charts (stacked): one bar per contract-day, no total line, connector + swatch per rail label, '
              'boxed in-band names, legend of every contract, one x label per month',
              n_fig == 3 and n_bars == 36 * len(dates) and n_lines == 2 * n_last and labels == exp_labels
              and boxed == n_peak and ax.get_legend() is not None and len(ax.get_legend().get_texts()) == 36 and ylim[0] == 0
              and xt == [month_tick(dates[i]) for i in month_starts(dates)],
              (n_fig, n_bars, n_lines, n_last, boxed, n_peak, labels[:3], exp_labels[:3], xt[:3]))
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
    out, text = quiet(run, products=FAKE_PRODUCTS, today=TEST_TODAY, blpapi_module=FakeAPI, out=path, **TEST_KW)
    check('run(): returns the path and writes the file', out == path and os.path.exists(path))
    check('run(): banner states the window, the expiries and the rule',
          'window 2023-09-01 .. 2026-09-17 | expiries Jan 24 .. Dec 26 (36) | contracts expiring within 4 months excluded'
          in text, text[:300])
    check('run(): per-product counts, NOT FOUND months, NO DATA months, output path printed',
          ('%-8s %2d/%d' % ('AS51', 12, 36)) in text and ('%-11s Jan 24' % 'NOT FOUND:') in text
          and ('%-11s Oct 26' % 'NO DATA:') in text and ('Written: %s' % path) in text, text[-800:])
    check('run(): session closed', FakeSession.instances and FakeSession.instances[-1].stopped)
    FakeSession.instances.clear()
    out, text = quiet(run, products=FAKE_PRODUCTS, today=TEST_TODAY, blpapi_module=FakeAPI, tickers_only=True, **TEST_KW)
    sess = FakeSession.instances[-1]
    check('run(tickers_only): no historical request, table with multiplier and currency printed, returns ""',
          out == '' and not any(e['op'] == 'HistoricalDataRequest' for e in sess.log)
          and 'HIU25 Index' in text and 'NOT FOUND' in text and 'FUT_VAL_PT Ccy' in text
          and any(line.split()[:2] == ['HSI', 'Sep'] and ' 50 ' in line and 'HKD' in line for line in text.splitlines()),
          text[:400])
    try:
        quiet(main, ['--help'])
        code = None
    except SystemExit as e:
        code = e.code
    check('--help exits 0', code == 0, code)
    path2 = os.path.join(tmp, 'nb.xlsx')
    out, text = quiet(notebook_main, products=FAKE_PRODUCTS, today=TEST_TODAY, blpapi_module=FakeAPI,
                      out=path2, show_charts_=False, **TEST_KW)
    check('notebook_main(): runs everything, returns the path', out == path2 and os.path.exists(path2) and 'Written:' in text)
    out, text = quiet(notebook_main, products=FAKE_PRODUCTS, today=TEST_TODAY,
                      blpapi_module=api_with(SilentSession), out=path2, **TEST_KW)
    check('notebook_main(): a Bloomberg problem is one clear message with the step, no traceback',
          out is None and 'ERROR while resolving the tickers:' in text and 'Bloomberg did not answer' in text
          and 'Traceback' not in text, text)
    results = resolve_contracts(Bloomberg(blpapi_module=FakeAPI).connect(), FAKE_PRODUCTS, TEST_MONTHS, TEST_TODAY)
    bbg = Bloomberg(blpapi_module=FakeAPI).connect()
    for _, cs in results:
        for c in cs:
            fetch_open_interest(bbg, c, TEST_START, TEST_TODAY, 4)
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
        titles = [plt.figure(i).axes[0].get_title(loc='left') for i in figs]
        n_lines = [len(plt.figure(i).axes[0].get_lines()) for i in figs]
        plt.close('all')
        check('show_charts with matplotlib: one figure per product with data, one line per found contract',
              n == 3 and len(figs) == 3 and titles == [CHART_TITLE['oi'].format(name=x) for x in ('HSI', 'AS51', 'SIMSCI')]
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
    check('field refusals remembered per security (NFH4 was never asked for: NFH24 resolved in pass 1)',
          bbg.field_error_secs.get('LAST_TRADEABLE_DT') == {'NFJ4 Index'} and bbg.n_ref_securities == 3)
    _, text = quiet(print_summary, results, bbg, None)
    check('summary explains the refusal instead of calling the field invalid',
          'LAST_TRADEABLE_DT not applicable to 1 of 3 candidate tickers' in text and 'e.g. NFJ4 Index' in text
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
                      blpapi_module=api_with(DeadTerminalSession), out=os.path.join(tmp, 'a.xlsx'), **TEST_KW)
    check('terminal not running -> "ERROR while connecting to Bloomberg" + what to check',
          out is None and 'ERROR while connecting to Bloomberg' in text and 'logged in' in text
          and 'Traceback' not in text, text)
    # a data-limit style failure in the middle of the pull: keep what was pulled, say where it stopped
    path = os.path.join(tmp, 'partial.xlsx')
    out, text = quiet(notebook_main, products=FAKE_PRODUCTS, today=TEST_TODAY,
                      blpapi_module=api_with(StopsMidPullSession), out=path, show_charts_=False, **TEST_KW)
    wb = load_workbook(path) if os.path.exists(path) else None
    statuses = [r[5] for r in wb[AUDIT_SHEET].iter_rows(min_row=2, values_only=True)] if wb else []
    check('pull stops at contract 5: workbook still written with the 4 pulled, rest NOT PULLED, message says so',
          out is None and wb is not None and 'ERROR while pulling OPEN_INT for HIK24 Index (HSI May 24)' in text
          and 'Daily capacity reached' in text and 'still written with the 4 of 83' in text and path in text
          and wb['HSI'].max_column == 7 and statuses.count(NOT_PULLED) == 79 and statuses.count(OK) == 4
          and 'HSI      pulling' in text and 'AS51     skipped' in text and 'NOT PULLED:' in text
          and 'Traceback' not in text, text[-900:])
    # an unexpected (non-Bloomberg) error: the message names the step AND the traceback follows
    out, text = quiet(notebook_main, products=FAKE_PRODUCTS, today=TEST_TODAY,
                      blpapi_module=api_with(BuggyHistorySession), out=os.path.join(tmp, 'b.xlsx'), show_charts_=False,
                      **TEST_KW)
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
    rebuild_universe(118)                     # serial months listed the day the third month out opens, as on HKEX
    run(products=FAKE_PRODUCTS, today=TEST_TODAY, blpapi_module=FakeAPI, out=out, **dict(TEST_KW, last_expiry_year=2036))
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
    test_visibility()
    test_long_dated()
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
