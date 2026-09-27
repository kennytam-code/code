"""HKEX dividend currency elections - which companies let holders pick the dividend currency.

Searches HKEX's title search   https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=en
(Circulars + Announcements and Notices) over the last five years for dividend currency
election forms and lists each company ONCE: how many forms it filed each year, and the
currencies its latest form lets holders choose - so the HKD/RMB ones stand out.

What counts as a currency election form:
  * a title that says so - "Dividend Currency Election Form", "How to elect ... the currency",
    or an RMB "Dividend Election Form" (SINOTRUK titles its forms that way);
  * a plain "(Dividend) Election Form" (OOIL, BAY AREA DEV, CHINA MERCHANTS) ONLY if the form
    itself offers two or more currencies - scrip, reinvestment and corporate-communication
    forms fall out there.

Five one-year searches, not one per company: HKEX lets a search across ALL stocks span at
most 12 months (a longer one comes back EMPTY, without an error), so the five years go as
five 12-month windows per title and category, merged.  About 20 requests, not 2,600.

A currency election is not always HKD/RMB: HSBC and StanChart offer HKD/USD/GBP, PRU HKD/USD,
HX BLDG MAT declares in RMB but offers HKD/USD.  So the forms are read, with pypdf - which
is installed automatically the first time if it is missing.

How to run: paste this whole file into a Jupyter cell and press Run
(or keep the file next to the notebook and run   %run hkex_currency_election.py).
The table is drawn under the cell and saved (CSV + Markdown) in the hkex_out folder.
Python 3.8+, standard library only (plus pypdf).
"""

import collections
import concurrent.futures
import csv
import datetime as dt
import gzip
import html
import http.client
import importlib
import io
import json
import logging
import os
import re
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import warnings

# ================================================================ CONFIG ===
CATEGORIES = ('Circulars',                # HKEX headline categories, by HKEX's own names.  Most
              'Announcements and Notices')   # forms are circulars; CHINA VANKE, S HARBOURHOLD and
SEARCH_TITLES = ('Currency',                 # CHINA MOBILE filed some as announcements
                 'Election Form')         # searched in titles; every hit is then classified
YEARS = 5
READ_FORMS = True                         # read the forms for the currencies they offer
AUTO_INSTALL = True                       # pip-install pypdf the first time if it is missing
try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:                         # pasted straight into a notebook cell
    HERE = os.getcwd()
OUT_DIR = os.path.join(HERE, 'hkex_out')  # a CSV and a Markdown copy of the table, per run date

# ================================================================ ENGINE ===
SITE = 'https://www1.hkexnews.hk'
MAX_ROWS = 1000                           # HKEX returns at most 1,000 hits per search
HKT = dt.timezone(dt.timedelta(hours=8), 'HKT')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')
NO_CACHE = {'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}
CURRENCIES = (('HKD', r'\bHKD\b|HK\$|HONG KONG DOLLAR|\bHK DOLLAR'),
              ('RMB', r'\bRMB\b|RENMINBI|\bCNY\b'),
              ('USD', r'\bUSD\b|US\$|UNITED STATES DOLLAR|\bU\.?S\.? DOLLAR'),
              ('GBP', r'\bGBP\b|STERLING|£'),
              ('EUR', r'\bEUR\b|\bEUROS?\b'),
              ('JPY', r'\bJPY\b|JAPANESE YEN'),
              ('SGD', r'\bSGD\b|SINGAPORE DOLLAR'),
              ('AUD', r'\bAUD\b|AUSTRALIAN DOLLAR'),
              ('CAD', r'\bCAD\b|CANADIAN DOLLAR'))
SKIP = re.compile(r'SCRIP|REINVEST|(?:SHARE|CASH) ALTERNATIVE|BONUS|NOTIFICATION LETTER|'
                  r'CORPORATE COMMUNICATION|MEANS OF RECEIPT|POLL RESULT|PROXY FORM')
ELECT = re.compile(r'(?<!RE-)\bELECT(?:ION)?S?\b')    # not "re-election" of directors
FONT = 'font-family:Arial,Helvetica,sans-serif;'
INK, MUTED, RULE, HEAD, BAND, YES, NO = '#1f2937', '#6b7280', '#dfe4ea', '#1f3a5f', '#f3f6fa', '#1e7b4f', '#b45309'


class Stop(Exception):
    """A failure one sentence explains - printed instead of a traceback."""


# ----------------------------------------------------------------- fetch ---
_route = {}                               # what worked first time is used from then on


def get(url):
    """The bytes at `url`: Python first; on Windows, if Python cannot get out (an office
    proxy that wants a sign-in, say), Windows' own web stack - the one the browser uses."""
    if _route.get('windows'):
        return _windows_get(url)
    try:
        return _python_get(url)
    except (OSError, http.client.HTTPException) as e:
        reason = getattr(e, 'reason', e)
        if sys.platform != 'win32':
            raise Stop(f'could not reach HKEX ({reason}) - check the network or proxy, then run again')
        try:
            data = _windows_get(url)
        except Exception as e2:
            raise Stop(f'could not reach HKEX (Python: {reason}; Windows: {e2}) - '
                       f'check the network, then run again')
        _route['windows'] = True
        return data


def _python_get(url):
    """Certificates: the system's, then certifi's, then none - these are public read-only
    pages, better fetched unchecked than not at all."""
    contexts = [_route['context']] if 'context' in _route else _contexts()
    request = urllib.request.Request(url, headers=dict(NO_CACHE, **{'User-Agent': UA}))
    for context in contexts:
        try:
            with urllib.request.urlopen(request, timeout=30, context=context) as response:
                data = response.read()
            break
        except OSError as e:
            if not isinstance(getattr(e, 'reason', e), ssl.SSLCertVerificationError):
                raise
            refused = e
    else:
        raise refused                     # every certificate route refused
    _route['context'] = context
    return gzip.decompress(data) if data[:2] == b'\x1f\x8b' else data


def _contexts():
    out = [ssl.create_default_context()]
    try:
        import certifi
        out.append(ssl.create_default_context(cafile=certifi.where()))
    except ImportError:
        pass
    return out + [ssl._create_unverified_context()]


def _windows_get(url):
    """Through MSXML/WinINet: the browser's proxy settings and sign-in."""
    import win32com.client
    xhr = win32com.client.Dispatch('MSXML2.XMLHTTP.6.0')
    xhr.open('GET', url, False)
    for name, value in NO_CACHE.items():
        xhr.setRequestHeader(name, value)
    xhr.send()
    if xhr.status != 200:
        raise OSError(f'HTTP {xhr.status}')
    return bytes(xhr.responseBody)


def _json(url):
    return json.loads(get(url).decode('utf-8-sig'))


# ---------------------------------------------------------------- search ---
def category_codes(names=CATEGORIES):
    """HKEX's code for each headline category name, from HKEX's own list."""
    known = {c['name'].lower(): c['code'] for c in _json(SITE + '/ncms/script/eds/tierone_e.json')}
    missing = [n for n in names if n.lower() not in known]
    if missing:
        raise Stop(f'HKEX has no headline category called {missing} - check CATEGORIES')
    return [(n, known[n.lower()]) for n in names]


def windows(today, years=YEARS):
    """`years` back-to-back windows of 12 months, newest first, the first ending today."""
    out, end = [], today
    for _ in range(years):
        try:
            start = end.replace(year=end.year - 1) + dt.timedelta(days=1)
        except ValueError:                # 29 February
            start = end.replace(year=end.year - 1, day=28) + dt.timedelta(days=1)
        out.append((start, end))
        end = start - dt.timedelta(days=1)
    return out


def _query(t1code, start, end, title, rows):
    q = dict(sortDir=0, sortByOptions='DateTime', category=0, market='SEHK', stockId=-1,
             documentType=-1, fromDate=f'{start:%Y%m%d}', toDate=f'{end:%Y%m%d}', title=title,
             searchType=1, t1code=t1code, t2Gcode=-2, t2code=-2, rowRange=rows, lang='E')
    reply = _json(SITE + '/search/titleSearchServlet.do?' + urllib.parse.urlencode(q))
    result = reply.get('result')
    hits = json.loads(result) if isinstance(result, str) and result not in ('', 'null') else []
    return hits, int(reply.get('recordCnt') or 0)


def search(t1code, start, end, title):
    """Every hit for `title` in one category between two dates, inclusive.  HKEX answers a
    window it will not serve with nothing at all, and caps a hit list at 1,000 - either
    way the window is split in half and searched again."""
    hits, count = _query(t1code, start, end, title, MAX_ROWS)
    refused = count == 0 and _query(t1code, start, end, '', 1)[1] == 0   # nothing at all = refused
    if (refused or count > len(hits)) and (end - start).days > 31:
        middle = start + (end - start) // 2
        return search(t1code, start, middle, title) + search(t1code, middle + dt.timedelta(days=1), end, title)
    if count > len(hits):
        raise Stop(f'more than {MAX_ROWS} hits for "{title}" in {start:%d/%m/%Y}-{end:%d/%m/%Y}')
    return hits


def kind(title):
    """'says' - the title says it is a currency election;  'check' - an election form whose
    text must show a choice of currencies;  None - anything else."""
    t = title.upper()
    if SKIP.search(t) or not ELECT.search(t):
        return None
    if 'CURRENCY' in t or (re.search(r'\bRMB\b|RENMINBI', t) and 'ELECTION FORM' in t):
        return 'says'
    return 'check' if 'ELECTION FORM' in t else None


def _split(field):
    return [html.unescape(' '.join(p.split())) for p in re.split(r'(?i)<br\s*/?>', field or '')]


def document(hit, category):
    codes, names = _split(hit.get('STOCK_CODE')), _split(hit.get('STOCK_NAME'))
    names += [''] * (len(codes) - len(names))
    link = hit.get('FILE_LINK') or ''
    title = html.unescape(' '.join((hit.get('TITLE') or '').split()))
    return {'id': hit.get('NEWS_ID') or link,
            'codes': codes, 'names': names,
            'when': dt.datetime.strptime(hit['DATE_TIME'], '%d/%m/%Y %H:%M'),
            'title': title, 'kind': kind(title),
            'link': link if link.startswith('http') else SITE + link,
            'category': category}


def collect(cats, spans):
    """Every filing of the window whose title marks it 'says' or 'check' - one search per
    title x category x 12-month window, four at a time."""
    tasks = [(title, name, code, start, end) for title in SEARCH_TITLES for name, code in cats
             for start, end in spans]
    docs = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for batch in pool.map(lambda t: [document(h, t[1]) for h in search(t[2], t[3], t[4], t[0])], tasks):
            for d in batch:
                if d['kind'] and d['id'] not in docs:
                    docs[d['id']] = d
    return docs


# ----------------------------------------------------------------- forms ---
def pdf_reader_installed():
    for name in ('pypdf', 'PyPDF2'):
        try:
            __import__(name)
            return True
        except ImportError:
            pass
    return False


def ensure_reader():
    """(True, note) once a PDF reader imports - installing pypdf first when AUTO_INSTALL."""
    if pdf_reader_installed():
        return True, ''
    fix = 'run  pip install pypdf  once, then Run again'
    if not AUTO_INSTALL:
        return False, f'pypdf is not installed - {fix}'
    print('Installing pypdf (reads the forms) - first run only ...')
    try:
        done = subprocess.run([sys.executable, '-m', 'pip', 'install', '--quiet', 'pypdf'],
                              capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as e:
        return False, f'could not install pypdf ({e}) - {fix}'
    importlib.invalidate_caches()
    if done.returncode == 0 and pdf_reader_installed():
        return True, 'pypdf installed'
    last = (done.stderr or done.stdout or 'pip failed').strip().splitlines()[-1]
    last = last.replace(sys.executable, 'python')          # "python: No module named pip"
    return False, f'could not install pypdf ({last[:160]}) - {fix}'


def _pdf_text(data, pages=8):
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader      # the same library under its older name
    for name in ('pypdf', 'PyPDF2'):
        logging.getLogger(name).setLevel(logging.ERROR)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return ' '.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(data)).pages[:pages])


def read_currencies(doc):
    """(currencies the form lets holders choose, e.g. ['HKD', 'RMB'], or None;  why not read)."""
    try:
        data = get(doc['link'])
        if doc['link'].lower().endswith('.pdf'):
            text = _pdf_text(data)
        else:
            text = re.sub(r'<[^>]+>', ' ', data.decode('utf-8', 'replace'))
    except Exception as e:                # one unreadable form must not stop the list
        return None, f'could not read the form ({e})'
    text = ' '.join(html.unescape(text).split()).upper()
    if not text:
        return None, 'no text in the form (a scan?)'
    return offered(text), ''


def offered(text):
    """The currencies a form lets you choose.  The currency a dividend is DECLARED in is
    named too - but as an amount (RMB0.21), an exchange rate (HK$1.0 : RMB0.87) or
    "declared in ..." - so those mentions are dropped first.  E.g. HX BLDG MAT declares
    in RMB and offers HKD or USD: RMB must not count."""
    any_currency = '(?:' + '|'.join(pattern for _, pattern in CURRENCIES) + ')S?'
    text = re.sub(f'EXCHANGE RATE (?:OF |BETWEEN |FROM )?{any_currency}\\s*[\\d.,]*\\s*'
                  f'(?:TO|:|=|AND|AGAINST|INTO)\\s*{any_currency}', ' ', text)      # "HK$1.0 : RMB0.87"
    text = re.sub(f'(?:DECLARED|DENOMINATED) IN {any_currency}', ' ', text)
    return [k for k, pattern in CURRENCIES if re.search(f'(?:{pattern})(?!\\s*[\\d.,]*\\d)', text)]


def _read_all(docs):
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for d, (cur, why) in zip(docs, pool.map(read_currencies, docs)):
            d['currencies'], d['why'] = cur, why


# --------------------------------------------------------------- company ---
def companies(docs):
    """One entry per company.  Codes filed together on one document are one company (its
    shares, an RMB counter, its notes), and a code keeps its row through a change of name.
    Only the FORMS are counted when a company files them: NIRAKU files "How to elect ... the
    currency" next to every "Currency Election Form", SY HOLDINGS announcements next to its
    forms - counting both would count every dividend twice."""
    parent = {}

    def root(c):
        parent.setdefault(c, c)
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c
    for d in docs:
        for c in d['codes'][1:]:
            parent[root(c)] = root(d['codes'][0])
    groups = collections.defaultdict(list)
    for d in docs:
        groups[root(d['codes'][0])].append(d)

    out = []
    for group in groups.values():
        group.sort(key=lambda d: d['when'], reverse=True)                  # newest first
        group = [d for d in group if 'FORM' in d['title'].upper()] or group
        code = collections.Counter(d['codes'][0] for d in group).most_common(1)[0][0]
        names = [d['names'][d['codes'].index(code)] for d in group if code in d['codes']]
        out.append({'code': code, 'name': names[0],
                    'formerly': [n for i, n in enumerate(names) if n and n != names[0] and n not in names[:i]],
                    'docs': group, 'latest': group[0],
                    'years': collections.Counter(d['when'].year for d in group),
                    'currencies': None, 'why': 'not read'})
    return out


# ----------------------------------------------------------------- table ---
def _both(c):
    return None if c['currencies'] is None else ('HKD' in c['currencies'] and 'RMB' in c['currencies'])


def _order(rows):
    rank = {True: 0, False: 1, None: 2}
    return sorted(rows, key=lambda c: (rank[_both(c)], c['code']))


LABELS = {True: 'HKD and RMB on the latest form', False: 'Other currencies (no RMB on the latest form)',
          None: 'Latest form not read'}


def as_html(rows, span, years, counts):
    th = (f'{FONT}font-size:8.5pt;font-weight:bold;color:#ffffff;background:{HEAD};'
          f'padding:6px 8px;text-align:left;vertical-align:bottom;white-space:nowrap;')
    heads = (['Stock Code', 'Stock Name', 'HKD &amp; RMB', 'Currencies<br>(latest form)']
             + [f'{y}' for y in years] + ['Total', 'Latest form'])
    out = [f'<div style="{FONT}color:{INK};">',
           '<div style="font-size:12pt;font-weight:bold;margin:0 0 4px 0;">'
           'HKEX dividend currency elections &ndash; one row per company</div>',
           f'<div style="font-size:9pt;color:{MUTED};margin:0 0 10px 0;">{html.escape(counts)}</div>',
           '<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">',
           '<tr>' + ''.join(f'<td style="{th}{"text-align:center;" if h[:2].isdigit() or h == "Total" else ""}">'
                            f'{h}</td>' for h in heads) + '</tr>']
    section, band = object(), False
    for c in _order(rows):
        if _both(c) != section:
            section = _both(c)
            n = sum(1 for r in rows if _both(r) == section)
            out.append(f'<tr><td colspan="{len(heads)}" style="{FONT}font-size:9pt;font-weight:bold;'
                       f'color:{INK};padding:12px 8px 4px 8px;border-bottom:2px solid {HEAD};">'
                       f'{LABELS[section]} ({n})</td></tr>')
        band = not band
        td = (f'{FONT}font-size:9pt;color:{INK};background:{BAND if band else "#ffffff"};padding:5px 8px;'
              f'border-bottom:1px solid {RULE};vertical-align:top;')
        name = f'<b>{html.escape(c["name"])}</b>'
        if c['formerly']:
            name += f'<br><span style="color:{MUTED};">formerly {html.escape(", ".join(c["formerly"]))}</span>'
        mark = {True: f'<b style="color:{YES};">Yes</b>', False: f'<b style="color:{NO};">No</b>',
                None: f'<span style="color:{MUTED};" title="{html.escape(c["why"])}">?</span>'}[_both(c)]
        cur = ' · '.join(c['currencies']) if c['currencies'] else f'<span style="color:{MUTED};">&ndash;</span>'
        cells = [f'<td style="{td}">{c["code"]}</td>', f'<td style="{td}">{name}</td>',
                 f'<td style="{td}text-align:center;">{mark}</td>', f'<td style="{td}white-space:nowrap;">{cur}</td>']
        for y in years:
            k = c['years'].get(y, 0)
            cells.append(f'<td style="{td}text-align:center;{"font-weight:bold;" if k else ""}">{k or ""}</td>')
        latest = c['latest']
        cells.append(f'<td style="{td}text-align:center;">{len(c["docs"])}</td>')
        cells.append(f'<td style="{td}white-space:nowrap;"><a href="{html.escape(latest["link"])}" '
                     f'title="{html.escape(latest["title"])}">{latest["when"]:%d/%m/%Y}</a></td>')
        out.append('<tr>' + ''.join(cells) + '</tr>')
    out.append('</table>')
    out.append(f'<div style="font-size:8.5pt;color:{MUTED};margin-top:8px;">Years count the forms filed in '
               f'that calendar year within {html.escape(span)}. Currencies are the ones the latest form lets '
               f'holders choose; the date opens it.</div></div>')
    return ''.join(out)


def _write_csv(rows, years, path):
    header = (['stock_code', 'bbg_ticker', 'stock_name', 'formerly', 'hkd_and_rmb', 'currencies']
              + [str(y) for y in years] + ['total', 'latest_date', 'latest_title', 'latest_link'])
    with open(path, 'w', newline='', encoding='utf-8-sig') as fh:        # -sig: Excel reads it as UTF-8
        w = csv.writer(fh)
        w.writerow(header)
        for c in _order(rows):
            w.writerow([c['code'], f'{int(c["code"])} HK' if c['code'].isdigit() else '', c['name'],
                        '; '.join(c['formerly']), {True: 'Yes', False: 'No', None: '?'}[_both(c)],
                        ' '.join(c['currencies'] or [])]
                       + [c['years'].get(y, 0) for y in years]
                       + [len(c['docs']), f'{c["latest"]["when"]:%d/%m/%Y}', c['latest']['title'],
                          c['latest']['link']])


def _write_md(rows, years, span, counts, path):
    head = ['Code', 'Company', 'HKD & RMB', 'Currencies'] + [str(y) for y in years] + ['Total', 'Latest form']
    lines = [f'# HKEX dividend currency elections, {span}', '', counts, '',
             'Years count the forms filed in that calendar year. Currencies are the ones the latest '
             'form lets holders choose; the date links to it.']
    section = object()
    for c in _order(rows):
        if _both(c) != section:
            section = _both(c)
            n = sum(1 for r in rows if _both(r) == section)
            lines += ['', f'## {LABELS[section]} ({n})', '', '| ' + ' | '.join(head) + ' |',
                      '|' + '---|' * len(head)]
        name = c['name'] + (f' (formerly {", ".join(c["formerly"])})' if c['formerly'] else '')
        cells = ([c['code'], name, {True: 'Yes', False: 'No', None: '?'}[_both(c)],
                  ' · '.join(c['currencies'] or []) or '–']
                 + [str(c['years'].get(y) or '') for y in years]
                 + [str(len(c['docs'])), f"[{c['latest']['when']:%d/%m/%Y}]({c['latest']['link']})"])
        lines.append('| ' + ' | '.join(x.replace('|', '/') for x in cells) + ' |')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')


def save(rows, years, span, counts, stamp):
    """CSV + Markdown copies of the table in OUT_DIR - or in TEMP if that cannot be written."""
    for folder in (OUT_DIR, tempfile.gettempdir()):
        try:
            os.makedirs(folder, exist_ok=True)
            base = os.path.join(folder, f'hkex_currency_election_{stamp}')
            _write_csv(rows, years, base + '.csv')
            _write_md(rows, years, span, counts, base + '.md')
            return base + '.csv  (+ .md)'
        except OSError as e:
            error = e
    return f'not saved ({error})'


# ------------------------------------------------------------------- run ---
def _show(fragment):
    try:
        from IPython import get_ipython
        from IPython.display import HTML, display
    except ImportError:
        return False
    if type(get_ipython()).__name__ != 'ZMQInteractiveShell':
        return False
    display(HTML(f'<div style="background:#ffffff;padding:14px 18px;">{fragment}</div>'))
    return True


def run():
    """Search, classify, read the forms, draw the table, save it.  Returns one dict per company."""
    started, now = time.time(), dt.datetime.now(HKT)
    spans = windows(now.date())
    first, last = spans[-1][0], spans[0][1]
    span = f'{first:%d/%m/%Y} - {last:%d/%m/%Y}'
    try:
        cats = category_codes()
        print(f'Searching HKEX: {len(SEARCH_TITLES) * len(cats) * len(spans)} one-year searches ...')
        docs = collect(cats, spans)
    except Stop as e:
        print(f'Stopped: {e}.  Nothing listed.')
        return []

    readable, note = ensure_reader() if READ_FORMS else (False, 'forms not read (READ_FORMS = False)')
    checks = [d for d in docs.values() if d['kind'] == 'check']
    if readable:
        print(f'Reading {len(checks)} plain election forms for a choice of currencies ...')
        _read_all(checks)
    kept = [d for d in docs.values() if d['kind'] == 'says' or len(d.get('currencies') or []) >= 2]
    rows = companies(kept)
    if readable:
        todo = [c['latest'] for c in rows if 'currencies' not in c['latest']]
        print(f'Reading the latest form of {len(todo)} companies ...')
        _read_all(todo)
        for c in rows:
            cur, why = c['latest']['currencies'], c['latest']['why']
            if cur is not None and len(cur) < 2:            # a currency election names two or more
                cur, why = None, 'the form text names no choice of currencies'
            c['currencies'], c['why'] = cur, why
    else:
        for c in rows:
            c['why'] = note

    years = [y for y in range(first.year, last.year + 1) if any(c['years'].get(y) for c in rows)]
    tally = collections.Counter(_both(c) for c in rows)
    says = sum(1 for d in kept if d['kind'] == 'says')
    counts = f'{len(rows)} companies · {len(kept)} forms · {span} · run {now:%d/%m/%Y %H:%M} HKT'
    facts = [('Search', 'titles with "' + '" or "'.join(SEARCH_TITLES) + '" in ' + ' + '.join(n for n, _ in cats)),
             ('Window', f'{span}  ({len(spans)} x 12-month all-stock searches per title and category)'),
             ('Forms', f'{len(kept)} currency elections  ({says} titled as such, {len(kept) - says} plain '
                       f'election forms offering 2+ currencies, {len(checks) - (len(kept) - says)} other election forms dropped)'
                       if readable else f'{says} titled as currency elections  ({len(checks)} plain election forms NOT checked)'),
             ('Companies', f'{len(rows)}  (one row each: stock codes and renames merged)'),
             ('HKD & RMB', f'{tally[True]} yes · {tally[False]} other currencies · {tally[None]} not read')]
    if note:
        facts.append(('Note', note))
    facts.append(('Saved', save(rows, years, span, counts, f'{now:%Y-%m-%d}')))
    facts.append(('Took', f'{time.time() - started:.0f} s'))
    for label, value in facts:
        print(f'{label:<11}{value}')
    if not _show(as_html(rows, span, years, counts)):
        for c in _order(rows):
            both = {True: 'Yes', False: 'No ', None: ' ? '}[_both(c)]
            print(f"{c['code']}  {c['name']:<18} {both}  {' '.join(c['currencies'] or []):<14}"
                  + ' '.join(f"{c['years'].get(y, 0) or '.':>2}" for y in years)
                  + f"  latest {c['latest']['when']:%d/%m/%Y}")
    return rows


if __name__ == '__main__':
    run()
