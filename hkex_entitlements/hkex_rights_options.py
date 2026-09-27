"""HKEX rights & options - press Run in Jupyter, get an Outlook draft.

Reads HKEX's daily list "Dividends & Other Entitlements"
    https://www3.hkexnews.hk/reports/doe/eent.htm
keeps every entry whose Description contains RIGHT or OPTION (any case) and
drafts an email with the page's own columns, in the page's own order:

    Stock Short Name (Stock Code) | Description | Ex-Date | Book Closing Date

How to run: paste this whole file into a Jupyter cell and press Run
(or keep the file next to the notebook and run   %run hkex_rights_options.py).

    Windows + Outlook   the draft is saved in Drafts and opened for review
    anywhere else       an .eml draft is written to OUT_DIR and opened
    in Jupyter          the email is also drawn under the cell

Nothing is ever sent.  Python 3.8+, standard library only (plus pywin32 for
the Outlook step).
"""

import datetime as dt
import html
import os
import re
import ssl
import subprocess
import sys
import urllib.request
from email.message import EmailMessage
from html.parser import HTMLParser

# ================================================================ CONFIG ===
URL = 'https://www3.hkexnews.hk/reports/doe/eent.htm'
KEYWORDS = ('RIGHT', 'OPTION')    # kept if the Description contains any of these, any case
TO = ''                           # 'a@nomura.com; b@nomura.com' - or leave blank, fill in Outlook
CC = ''
SUBJECT = 'HKEX Entitlements – Rights & Options – {date}'
GREETING = 'Hi all,'
OPEN_DRAFT = True                 # open the draft for review; False = only save it to Drafts
try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:                 # pasted straight into a notebook cell
    HERE = os.getcwd()
OUT_DIR = os.path.join(HERE, 'hkex_out')   # the .eml lands here when Outlook is not reachable

# ================================================================ ENGINE ===
HKT = dt.timezone(dt.timedelta(hours=8), 'HKT')        # Hong Kong has no daylight saving
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')
FONT = 'font-family:Arial,Helvetica,sans-serif;'
INK, MUTED, RULE, HEAD, BAND, FLAG = '#1f2937', '#6b7280', '#dfe4ea', '#1f3a5f', '#f3f6fa', '#c0392b'


class Stop(Exception):
    """A failure one sentence explains - printed instead of a traceback."""


# ----------------------------------------------------------------- fetch ---
def fetch(url=URL):
    """(page text, note).  Certificates: the system's, then certifi's, then none -
    this is a public read-only page, better fetched unchecked than not at all."""
    contexts = [('', ssl.create_default_context())]
    try:
        import certifi
        contexts.append(('', ssl.create_default_context(cafile=certifi.where())))
    except ImportError:
        pass
    contexts.append(('certificate check skipped - this Python has no CA bundle',
                     ssl._create_unverified_context()))
    request = urllib.request.Request(url, headers={'User-Agent': UA})
    for note, context in contexts:
        try:
            with urllib.request.urlopen(request, timeout=30, context=context) as response:
                raw = response.read()
            break
        except OSError as e:          # URLError, HTTPError, timeouts and SSL errors alike
            reason = getattr(e, 'reason', e)
            if not isinstance(reason, ssl.SSLCertVerificationError):
                raise Stop(f'could not reach HKEX ({reason}) - check the network or proxy, then run again')
    try:
        return raw.decode('utf-8'), note
    except UnicodeDecodeError:
        return raw.decode('cp1252', errors='replace'), note


# ----------------------------------------------------------------- parse ---
class _Cells(HTMLParser):
    """Every <tr> as a list of cell texts, <br> kept as a newline.  HKEX leaves
    cells unclosed, so a new <td> or <tr> closes whatever is still open."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self._row, self._cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self._end_row()
            self._row = []
        elif tag in ('td', 'th'):
            self._end_cell()
            if self._row is None:
                self._row = []
            self._cell = []
        elif tag == 'br' and self._cell is not None:
            self._cell.append('\n')

    def handle_endtag(self, tag):
        if tag in ('td', 'th'):
            self._end_cell()
        elif tag in ('tr', 'table'):
            self._end_row()

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(re.sub(r'\s+', ' ', data))    # only <br> breaks a line

    def _end_cell(self):
        if self._cell is not None:
            self._row.append(''.join(self._cell))
            self._cell = None

    def _end_row(self):
        self._end_cell()
        if self._row:
            self.rows.append(self._row)
        self._row = None


def _lines(cell):
    return [' '.join(line.split()) for line in cell.split('\n') if line.strip()]


def _columns(row):
    """Where each field sits if `row` is the header row, else None."""
    labels = [' '.join(cell).lower() for cell in row]

    def first(test):
        return next((i for i, label in enumerate(labels) if test(label)), None)
    col = {'stock': first(lambda s: 'stock' in s),
           'desc': first(lambda s: s == 'description'),
           'ex': first(lambda s: s.replace(' ', '-').startswith('ex-date')),
           'book': first(lambda s: 'book clos' in s)}
    return None if None in col.values() else col


def parse(page):
    """(meta, entries): one entry per row of HKEX's table, in HKEX's order."""
    cells = _Cells()
    cells.feed(page)
    cells.close()
    rows = [[_lines(c) for c in r] for r in cells.rows]
    for h, header in enumerate(rows):
        col = _columns(header)
        if col:
            break
    else:
        raise Stop('the HKEX page layout has changed - no header row with '
                   'Stock / Description / Ex-Date / Book Closing Date')

    entries, stock = [], ('', '')
    for row in rows[h + 1:]:
        if len(row) != len(header) or row == header:
            continue                                   # spacer rows
        if not any(line.strip('-') for cell in row for line in cell):
            continue                                   # the ------ underline
        if row[col['stock']]:                          # blank = same stock as the row above
            name = ' '.join(row[col['stock']])
            m = re.match(r'(.*?)\s*\((\d+)\)$', name)
            stock = (m.group(1), m.group(2)) if m else (name, '')
        entries.append({'flag': ['*'] in row,          # HKEX's own asterisk column
                        'name': stock[0], 'code': stock[1],
                        'desc': row[col['desc']],
                        'ex': ' '.join(row[col['ex']]),
                        'book': row[col['book']]})
    if not entries:
        raise Stop('the HKEX page has a header but no entries under it')

    date = re.search(r'(?m)^\s*Date\s*:\s*(\d{1,2}/\d{1,2}/\d{4})', page)
    flag_to = re.search(r'up to\s+(\d{1,2}/\d{1,2}/\d{4})', page)
    meta = {'date': dt.datetime.strptime(date.group(1), '%d/%m/%Y').date() if date else None,
            'flag_to': flag_to.group(1) if flag_to else '',
            'labels': {k: header[i] for k, i in col.items()}}
    return meta, entries


def mentions(entry):
    """The KEYWORDS its Description contains, any case.  Checked with the lines
    joined by a space and glued together, so a word HKEX wraps mid-way still counts."""
    spaced = ' '.join(entry['desc']).upper()
    glued = ''.join(entry['desc']).upper()
    return [k for k in KEYWORDS if k.upper() in spaced or k.upper() in glued]


# ----------------------------------------------------------------- email ---
def _br(lines):
    return '<br>'.join(html.escape(line) for line in lines)


def _listed(meta):
    return meta['date'].strftime('%a %d/%m/%Y') if meta['date'] else 'undated'


def _tally(kept):
    return ' · '.join(f"{k.title()} {sum(k in e['hits'] for e in kept)}" for k in KEYWORDS)


def build_email(meta, entries, kept, fetched):
    """(subject, html).  Outlook draws mail with Word, so: tables and inline styles only."""
    listed = _listed(meta)
    subject = SUBJECT.format(date=(meta['date'] or fetched).strftime('%d %b %Y'))
    words = ' or '.join(f'“{k.title()}”' for k in KEYWORDS)
    counts = _tally(kept)
    para = f'margin:0 0 12px 0;{FONT}font-size:10pt;color:{INK};'
    note = f'margin:6px 0 0 0;{FONT}font-size:8pt;color:{MUTED};'

    # one fixed-width frame, so the text wraps with the table in Outlook too
    out = ['<table cellpadding="0" cellspacing="0" border="0" width="752" style="width:752px;">'
           f'<tr><td style="{FONT}">']
    if GREETING:
        out.append(f'<p style="{para}">{html.escape(GREETING)}</p>')
    list_name = f'HKEX\'s <b>Dividends &amp; Other Entitlements</b> list dated <b>{listed}</b>'
    if not kept:
        out.append(f'<p style="{para}">No entry on {list_name} mentions {words}.</p>')
    else:
        many = len(kept) != 1
        out.append(f'<p style="{para}">Below {"are" if many else "is"} the <b>{len(kept)}</b> '
                   f'entr{"ies" if many else "y"} on {list_name} whose description mentions '
                   f'{words} ({counts}).</p>')

        th = (f'{FONT}font-size:9pt;font-weight:bold;color:#ffffff;background:{HEAD};'
              f'padding:7px 10px;text-align:left;vertical-align:bottom;')
        labels = meta['labels']
        cols = [(labels['stock'], 140), (labels['desc'], 300), (labels['ex'], 52), (labels['book'], 160)]
        out.append('<table cellpadding="0" cellspacing="0" border="0" width="752" '
                   'style="border-collapse:collapse;width:752px;">')
        out.append(f'<tr><td width="12" style="{th}padding:7px 0 7px 8px;">&nbsp;</td>'
                   + ''.join(f'<td width="{w}" style="{th}">{_br(label)}</td>' for label, w in cols)
                   + '</tr>')
        band, previous = True, None
        for e in kept:
            if (e['name'], e['code']) != previous:     # one shade per stock, as HKEX groups them
                band, previous = not band, (e['name'], e['code'])
            td = (f'{FONT}font-size:9.5pt;color:{INK};background:{BAND if band else "#ffffff"};'
                  f'padding:7px 10px;vertical-align:top;border-bottom:1px solid {RULE};'
                  f'line-height:14px;mso-line-height-rule:exactly;')
            flag = (f'<td style="{td}padding:7px 0 7px 8px;color:{FLAG};font-weight:bold;">*</td>'
                    if e['flag'] else f'<td style="{td}padding:7px 0 7px 8px;">&nbsp;</td>')
            stock = f'<b>{html.escape(e["name"])}</b>'
            if e['code']:
                stock += f'<br><span style="color:{MUTED};">({e["code"]})</span>'
            ex = html.escape(e['ex']) or f'<span style="color:{MUTED};">&mdash;</span>'
            dated = re.search(r'\d', ' '.join(e['book']))
            book = _br(e['book']) if dated else f'<span style="color:{MUTED};">{_br(e["book"])}</span>'
            out.append(f'<tr>{flag}<td style="{td}">{stock}</td><td style="{td}">{_br(e["desc"])}</td>'
                       f'<td style="{td}white-space:nowrap;">{ex}</td>'
                       f'<td style="{td}white-space:nowrap;">{book}</td></tr>')
        out.append('</table>')
        if meta['flag_to'] and any(e['flag'] for e in kept):
            out.append(f'<p style="{note}margin-top:10px;"><b style="color:{FLAG};">*</b> '
                       f'HKEX flag: effective book closing date commencing up to {meta["flag_to"]}.</p>')

    out.append(f'<p style="{note}">Source: <a href="{URL}" style="color:{MUTED};">HKEX Dividends '
               f'&amp; Other Entitlements</a>, list dated {listed}, fetched '
               f'{fetched:%a %d/%m/%Y %H:%M} HKT. Kept {len(kept)} of {len(entries)} entries: '
               f'description contains {words}, any case. HKEX notes the list may not be '
               f'exhaustive &ndash; check the issuer\'s announcement for terms.</p>'
               f'</td></tr></table>')
    return subject, ''.join(out)


def _page(subject, fragment):
    return (f'<html><head><meta charset="utf-8"><title>{html.escape(subject)}</title></head>'
            f'<body style="margin:0;padding:16px;background:#ffffff;">{fragment}</body></html>')


# ----------------------------------------------------------------- draft ---
def outlook_draft(subject, fragment):
    """Save the draft in Outlook and open it.  Raises if Outlook is not reachable."""
    import win32com.client
    mail = win32com.client.Dispatch('Outlook.Application').CreateItem(0)   # 0 = olMailItem
    mail.To = TO
    mail.CC = CC
    mail.Subject = subject
    try:
        mail.GetInspector                  # touching it makes Outlook add the default signature
        signature = mail.HTMLBody or ''
    except Exception:
        signature = ''
    body = re.search(r'<body[^>]*>', signature, flags=re.I)
    mail.HTMLBody = (signature[:body.end()] + fragment + signature[body.end():]
                     if body else _page(subject, fragment))
    mail.Save()
    if OPEN_DRAFT:
        mail.Display()
    return 'Outlook - saved to Drafts' + (' and opened' if OPEN_DRAFT else '')


def eml_draft(subject, fragment, stamp):
    """Write an .eml that opens as an unsent draft, and open it."""
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f'hkex_rights_options_{stamp}.eml')
    msg = EmailMessage()
    msg['Subject'] = subject
    if TO:
        msg['To'] = TO.replace(';', ',')
    if CC:
        msg['Cc'] = CC.replace(';', ',')
    msg['X-Unsent'] = '1'                  # Outlook opens it as an editable draft
    msg.set_content(_page(subject, fragment), subtype='html')
    with open(path, 'wb') as fh:
        fh.write(bytes(msg))
    if OPEN_DRAFT:
        if sys.platform == 'win32':
            os.startfile(path)
        else:
            subprocess.run(['open' if sys.platform == 'darwin' else 'xdg-open', path], check=False)
    return path


def make_draft(subject, fragment, stamp):
    try:
        return outlook_draft(subject, fragment)
    except ImportError:
        why = 'pywin32 not installed' if sys.platform == 'win32' else 'Outlook automation is Windows-only'
    except Exception as e:
        why = f'Outlook not reachable: {e}'
    return f'.eml {"written and opened" if OPEN_DRAFT else "written"} ({why}): {eml_draft(subject, fragment, stamp)}'


# ------------------------------------------------------------------- run ---
def _show(fragment):
    """Draw the email under the Jupyter cell.  False outside Jupyter."""
    try:
        from IPython import get_ipython
        from IPython.display import HTML, display
    except ImportError:
        return False
    if type(get_ipython()).__name__ != 'ZMQInteractiveShell':
        return False
    display(HTML(f'<div style="background:#ffffff;padding:14px 18px;border:1px solid {RULE};'
                 f'max-width:820px;">{fragment}</div>'))
    return True


def as_text(kept):
    """The kept rows as plain text, for a terminal."""
    rows = [(f"{'*' if e['flag'] else ' '} {e['name']} ({e['code']})", e['ex'] or '-',
             ' '.join(e['book']), ' '.join(e['desc'])) for e in kept]
    if not rows:
        return ''
    w = [max(len(r[i]) for r in rows) for i in range(3)]
    return '\n'.join(f'{a:<{w[0]}}  {b:<{w[1]}}  {c:<{w[2]}}  {d}' for a, b, c, d in rows)


def run():
    """Fetch the page, keep the RIGHT / OPTION entries, draft the email.  Returns the kept entries."""
    fetched = dt.datetime.now(HKT)
    try:
        page, note = fetch()
        meta, entries = parse(page)
    except Stop as e:
        print(f'Stopped: {e}.  Nothing drafted.')
        return []
    kept = []
    for e in entries:
        hits = mentions(e)
        if hits:
            kept.append(dict(e, hits=hits))
    subject, fragment = build_email(meta, entries, kept, fetched)
    draft = make_draft(subject, fragment, (meta['date'] or fetched).strftime('%Y%m%d'))

    counts = _tally(kept)
    facts = [('HKEX list', f'dated {_listed(meta)}  (fetched {fetched:%a %d/%m/%Y %H:%M} HKT)'),
             ('Entries', f'{len(entries)} on the list'),
             ('Kept', f'{len(kept)}  ({counts})'),
             ('Subject', subject),
             ('Draft', draft)]
    if note:
        facts.append(('Note', note))
    for label, value in facts:
        print(f'{label:<10} {value}')
    if not _show(fragment):
        print('\n' + as_text(kept))
    return kept


if __name__ == '__main__':
    run()
