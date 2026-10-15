#!/usr/bin/env python3
"""HK Equities Daily — one run creates a formatted, unsent Outlook draft.

Designed for a SINGLE Jupyter code cell or `python HK_Equities_Jupyter.py`.
Works with Python 3.8+ standard libraries to gather public data. On Windows it
opens an editable draft in Classic Outlook via pywin32 or PowerShell COM.
No message is sent. If Outlook automation is unsupported, an HTML preview,
.eml file, and other audit files are created in the output folder.
"""

from __future__ import annotations

# ===================== EDIT ONLY THESE SETTINGS =====================
EMAIL_SUBJECT = "IPO, PHIP & Lock-up Update | {date}"
EMAIL_TO = ""      # Optional: recipient addresses separated by semicolons
EMAIL_CC = ""      # Optional: CC addresses separated by semicolons
OUTPUT_FOLDER = "HK_Equities_Drafts"   # Created beneath the Jupyter working directory
OPEN_OUTLOOK = True                    # Show a real editable Outlook draft when possible
SHOW_NOTEBOOK_PREVIEW_IF_NO_OUTLOOK = True
INCLUDE_GEM_PHIPS = True
INCLUDE_EXPIRED_THIS_MONTH = False
SHORT_HISTORY_LOOKBACK_DAYS = 45
# Auto: Python urllib first; on Windows connection failure, retry with the
# Windows system proxy/PAC and your existing Windows login via PowerShell.
NETWORK_MODE = "auto"          # "auto", "windows_proxy", or "urllib"
NETWORK_TIMEOUT_SECONDS = 25   # Per-request limit through the company proxy
WINDOWS_PROXY_TIMEOUT_SECONDS = 35
# Proxy you verified as reachable from the Nomura desktop.
# Use http:// here: the HTTP proxy CONNECT-tunnels HTTPS destinations.
# Never store company passwords or tokens in this notebook.
# If your approved proxy changes, update this single line.
HTTPS_PROXY_URL = "http://instinetpxy.nomura.com:8080"
# ====================================================================

from contextlib import contextmanager
import base64
import subprocess
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import format_datetime, make_msgid
from html.parser import HTMLParser
import hashlib
import html
import json
import logging
import os
import tempfile
from pathlib import Path
import re
import sqlite3
import ssl
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlparse, parse_qs
import webbrowser

HK = timezone(timedelta(hours=8), "HKT")
ROOT = Path.cwd()  # Works inside a Jupyter notebook or as a standalone .py file
DEFAULT_DAILY_TIME = "18:30"
MAIN_BOARD_URL = "https://www2.hkexnews.hk/New-Listings/New-Listing-Information/Main-Board?sc_lang=zh-HK"
PHIP_PAGE_URL = "https://www1.hkexnews.hk/app/appindex.html?lang=zh"
PHIP_FEED_BASE = "https://www1.hkexnews.hk/ncms/json/eds/"
PHIP_DOCUMENT_BASE = "https://www1.hkexnews.hk/app/"
SHORT_URL = "https://www.hkex.com.hk/eng/market/sec_tradinfo/ds{day:%Y%m%d}.htm"
LOCKUP_URL = "https://www.etnet.com.hk/www/tc/stocks/ipo-free-float.php?month={month}"
HOLIDAYS_URL = "https://www.1823.gov.hk/common/ical/en.json"
LOG = logging.getLogger("hk_equities_daily")


class Element:
    """Small HTML tree for the specific public source tables and cards."""
    def __init__(self, tag="document", attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []

    def __getitem__(self, key):
        return self.attrs[key]

    def get(self, key, default=None):
        return self.attrs.get(key, default)

    def descendants(self):
        for child in self.children:
            if isinstance(child, Element):
                yield child
                yield from child.descendants()

    def find_all(self, tags, recursive=True):
        tags = {tags} if isinstance(tags, str) else set(tags)
        nodes = self.descendants() if recursive else self.children
        return [node for node in nodes if isinstance(node, Element) and node.tag in tags]

    def find(self, tag):
        return next((node for node in self.descendants() if node.tag == tag), None)

    def get_text(self, separator="", strip=False):
        def walk(node):
            for child in node.children:
                if isinstance(child, str):
                    if not strip or child.strip(): yield child.strip() if strip else child
                elif child.tag not in {"script", "style"}:
                    yield from walk(child)
        return separator.join(walk(self))

    @staticmethod
    def matches(node, selector):
        attribute = re.search(r'\[([\w-]+)(?:([*]?=)["\x27]?([^"\x27\]]+)["\x27]?)?\]', selector)
        if attribute:
            key, operator, value = attribute.groups()
            if key not in node.attrs: return False
            actual = node.attrs[key] or ""
            if operator == "=" and actual != value: return False
            if operator == "*=" and value not in actual: return False
            selector = selector[:attribute.start()] + selector[attribute.end():]
        pieces = selector.split(".")
        if pieces[0] and node.tag != pieces[0]: return False
        return all(piece in (node.attrs.get("class") or "").split() for piece in pieces[1:])

    def select(self, selector):
        matches = [self]
        for token in selector.split():
            found, seen = [], set()
            for parent in matches:
                for node in parent.descendants():
                    if id(node) not in seen and self.matches(node, token):
                        seen.add(id(node)); found.append(node)
            matches = found
        return matches

    def select_one(self, selector):
        return next(iter(self.select(selector)), None)


class DocumentParser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Element(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in self.VOID: self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID: self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack)-1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse_html(document, *_):
    parser = DocumentParser()
    parser.feed(document)
    parser.close()
    return parser.root


def tls_context():
    context = ssl.create_default_context()
    # Python.org macOS installs sometimes lack an OpenSSL default CA file.
    # Add the OS certificate bundle without disabling certificate validation.
    if sys.platform == "darwin" and Path("/etc/ssl/cert.pem").is_file():
        context.load_verify_locations(cafile="/etc/ssl/cert.pem")
    return context


def _decode_source(url, raw, encoding=None):
    """Keep identical source decoding for urllib and Windows proxy downloads."""
    if raw.startswith(b"\xef\xbb\xbf") or urlparse(url).path.endswith('.json'):
        return raw.decode('utf-8-sig')
    declared = re.search(rb'charset\s*=\s*["\x27]?([\w-]+)', raw[:8192], re.I)
    encoding = declared[1].decode('ascii') if declared else (encoding or 'utf-8')
    return raw.decode(encoding, errors='strict')


def _download_via_windows_proxy(url, timeout):
    """Use Windows proxy/PAC settings and current login; never disable TLS checks.

    This helps managed desktops where Edge/Outlook can access the web but
    Python urllib cannot evaluate the company's automatic PAC configuration.
    Windows PowerShell 5.1 ships with Windows and needs no Python packages.
    """
    if os.name != 'nt':
        raise SourceNetworkError('Windows proxy fallback is available only on Windows.')
    with tempfile.TemporaryDirectory(prefix='hk_eq_net_') as temp:
        download = Path(temp) / 'response.bin'
        command = '\n'.join([
            "$ErrorActionPreference = 'Stop'",
            '[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12',
            '$url = ' + _ps_quote(url),
            '$target = ' + _ps_quote(str(download)),
            ('$proxy = [System.Net.WebProxy]::new(' + _ps_quote(HTTPS_PROXY_URL.strip()) + ', $true)'
             if HTTPS_PROXY_URL.strip() else
             '$proxy = [System.Net.WebRequest]::GetSystemWebProxy()'),
            'if ($null -ne $proxy) { $proxy.Credentials = [System.Net.CredentialCache]::DefaultNetworkCredentials }',
            '$req = [System.Net.HttpWebRequest]::Create($url)',
            '$req.Method = "GET"',
            '$req.UserAgent = "Mozilla/5.0 (compatible; HK-Equities-Daily/3.0)"',
            '$req.Accept = "text/html,application/json,*/*"',
            '$req.Headers.Add("Accept-Language", "zh-HK,zh;q=0.9,en;q=0.8")',
            '$req.Timeout = ' + str(int(timeout * 1000)),
            '$req.ReadWriteTimeout = ' + str(int(timeout * 1000)),
            '$req.Proxy = $proxy',
            'try {',
            '  $resp = $req.GetResponse()',
            '  try {',
            '    $inputStream = $resp.GetResponseStream()',
            '    $outputStream = [System.IO.File]::Create($target)',
            '    try { $inputStream.CopyTo($outputStream) }',
            '    finally { $outputStream.Dispose(); $inputStream.Dispose() }',
            '  } finally { $resp.Dispose() }',
            '} catch {',
            '  [Console]::Error.WriteLine($_.Exception.Message)',
            '  exit 1',
            '}',
        ])
        encoded = base64.b64encode(command.encode('utf-16le')).decode('ascii')
        try:
            result = subprocess.run(
                ['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                capture_output=True, text=True, timeout=timeout+10, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SourceNetworkError('Windows PowerShell web download unavailable: ' + str(exc)) from exc
        if result.returncode != 0:
            reason = (result.stderr or result.stdout or 'unknown download error').strip()[:600]
            if re.search(r'\(404\)|HTTP\s*404', reason, re.I):
                raise PageMissing(f'Not published (HTTP 404): {url}')
            if re.search(r'\(410\)|HTTP\s*410', reason, re.I):
                raise PageMissing(f'Not published (HTTP 410): {url}')
            raise SourceNetworkError('Windows proxy fetch failed for ' + url + ': ' + reason)
        if not download.is_file():
            raise SourceNetworkError('Windows proxy fetch returned no file for ' + url)
        return download.read_bytes()


class Client:
    def __init__(self):
        self.context = tls_context()
        self.cache = {}
        self.windows_proxy_worked = NETWORK_MODE == 'windows_proxy'
        if NETWORK_MODE not in ('auto', 'urllib', 'windows_proxy'):
            raise ValueError('NETWORK_MODE must be auto, urllib, or windows_proxy.')
        # The user's successful proxy test used urllib.install_opener().
        # This Client builds its own opener; configure that opener explicitly,
        # otherwise it silently ignores the working global proxy!
        if HTTPS_PROXY_URL.strip():
            parsed_proxy = urlparse(HTTPS_PROXY_URL.strip())
            if (parsed_proxy.scheme not in ('http', 'https') or not parsed_proxy.hostname
                    or parsed_proxy.username or parsed_proxy.password):
                raise ValueError('HTTPS_PROXY_URL must be an http(s) proxy URL without credentials.')
            self.opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({
                    'http': HTTPS_PROXY_URL.strip(),
                    'https': HTTPS_PROXY_URL.strip(),
                }),
                urllib.request.HTTPSHandler(context=self.context),
            )
        else:
            self.opener = urllib.request.build_opener(
                urllib.request.ProxyHandler(),
                urllib.request.HTTPSHandler(context=self.context),
            )

    def text(self, url):
        if url in self.cache:
            return self.cache[url]
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; HK-Equities-Daily/3.0)',
            'Accept-Language': 'zh-HK,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache',
        })
        direct_failure = None
        use_windows = (self.windows_proxy_worked and NETWORK_MODE != 'urllib')
        if not use_windows:
            try:
                with self.opener.open(req, timeout=NETWORK_TIMEOUT_SECONDS) as response:
                    raw = response.read()
                    encoding = response.headers.get_content_charset()
                data = _decode_source(url, raw, encoding)
                self.cache[url] = data
                return data
            except urllib.error.HTTPError as exc:
                if exc.code in (404, 410):
                    raise PageMissing(f'Not published: {url}') from exc
                # 407 Proxy Authentication Required often means urllib cannot
                # negotiate the Windows integrated login used by company proxies.
                if exc.code not in (407, 429, 500, 502, 503, 504):
                    raise SourceError(f'HTTP {exc.code}: {url}') from exc
                direct_failure = f'HTTP {exc.code} from urllib'
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                direct_failure = str(exc)
            except (UnicodeError, LookupError) as exc:
                raise SourceError(f'Unexpected source encoding: {url}') from exc

        if NETWORK_MODE == 'urllib' or os.name != 'nt':
            raise SourceNetworkError(f'Could not connect to {url}. urllib: {direct_failure}')
        try:
            if not self.windows_proxy_worked:
                print('Python cannot reach this source. Trying Windows/company proxy settings...')
            raw = _download_via_windows_proxy(url, WINDOWS_PROXY_TIMEOUT_SECONDS)
            data = _decode_source(url, raw)
            self.cache[url] = data
            if not self.windows_proxy_worked:
                print('Windows proxy download worked; using it for remaining sources.')
            self.windows_proxy_worked = True
            return data
        except PageMissing:
            raise
        except SourceError as exc:
            first = f'Python urllib: {direct_failure}\n' if direct_failure else ''
            raise SourceNetworkError(
                f'Unable to download {url}\n{first}'
                f'Windows network/proxy: {exc}\n'
                'If the same website cannot open in Edge, ask IT whether access to the '
                'public source is permitted. Do not disable corporate proxy/TLS controls.'
            ) from exc
        except (UnicodeError, LookupError) as exc:
            raise SourceError(f'Unexpected source encoding: {url}') from exc


class SourceError(RuntimeError):
    """An unavailable source or unexpected source format; never means no changes."""


class PageMissing(SourceError):
    pass


class SourceNetworkError(SourceError):
    """A failed corporate network / proxy fetch, not a valid empty data set."""


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


def stock_code(value: object) -> str:
    value = unicodedata.normalize("NFKC", clean(value))
    if not re.fullmatch(r"\d{1,5}(?:\.HK)?", value, re.I):
        raise SourceError(f"Invalid stock code: {value!r}")
    return value.split(".")[0].zfill(5)


def parse_date(value: object) -> date:
    value = clean(value)
    for fmt in ("%d/%m/%Y", "%Y/%m/%d", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise SourceError(f"Unrecognized source date: {value!r}")


def month_keys(day: date) -> list[str]:
    first = day.replace(day=1)
    following = (first + timedelta(days=32)).replace(day=1)
    return [first.strftime("%Y%m"), following.strftime("%Y%m")]


def source_link(value: object, base: str) -> str:
    value = clean(value)
    if not value or value == "#":
        return ""
    url = urljoin(base, value)
    if urlparse(url).scheme not in ("http", "https"):
        raise SourceError(f"Unexpected source link: {value!r}")
    return url


@dataclass
class IPO:
    code: str
    name: str
    announcements: list[str]
    prospectuses: list[str]
    allotment_results: list[str]


@dataclass
class PHIP:
    key: str
    company: str
    board: str
    status: str
    posted: str
    title: str
    links: list[str]
    new: bool = False


@dataclass
class ShortList:
    effective: str
    url: str
    securities: dict[str, str]


@dataclass
class Lockup:
    code: str
    name: str
    expiry: str
    holder_type: str
    holders: str
    amount: str
    percent: str
    url: str
    price: str
    tab: str
    issue: str
    cumulative_change: str
    quote_url: str



def parse_ipos(document: str) -> list[IPO]:
    soup = parse_html(document, "html.parser")
    table = None
    for candidate in soup.select("table"):
        headers = clean(candidate.find("thead").get_text(" ")) if candidate.find("thead") else ""
        if "股份代號" in headers and "招股章程" in headers:
            table = candidate
            break
    if table is None:
        raise SourceError("Main Board IPO table was not found; the page may have changed.")
    rows: dict[str, IPO] = {}
    for tr in table.select("tbody tr"):
        cells = tr.find_all("td", recursive=False)
        if not cells:
            continue
        if (len(cells) == 1 and cells[0].get("colspan") == "5"
                and re.search(r"沒有|暫無|無資料|No\s+(?:records?|data)", clean(tr.get_text(" ")), re.I)):
            continue
        if len(cells) != 5:
            raise SourceError("Unexpected number of Main Board IPO columns.")
        if not clean(cells[0].get_text()) and ("沒有" in tr.get_text() or "No record" in tr.get_text()):
            continue
        code = stock_code(cells[0].get_text())
        links = [[source_link(a["href"], MAIN_BOARD_URL) for a in cell.select("a[href]")]
                 for cell in cells[2:5]]
        rows[code] = IPO(code, clean(cells[1].get_text(" ")), *links)
    # A recognizable empty table is valid; missing tables and malformed rows are errors.
    return list(rows.values())


def parse_phip(payload: dict, board: str, report_day: date) -> list[PHIP]:
    if not isinstance(payload, dict) or not isinstance(payload.get("app"), list):
        raise SourceError("Unexpected HKEX PHIP JSON schema (expected app array).")
    start = report_day - timedelta(days=6)
    rows: dict[str, PHIP] = {}
    statuses = {"A": "Active", "LP": "Lapsed", "RJ": "Rejected", "W": "Withdrawn", "LT": "Listed"}
    for applicant in payload["app"]:
        if not isinstance(applicant, dict) or "a" not in applicant or "id" not in applicant:
            raise SourceError("Unexpected PHIP applicant schema.")
        # Use each document's date, never the applicant's overall latest posting date.
        for bucket in ("ls", "ps"):
            proofs = applicant.get(bucket, [])
            if not isinstance(proofs, list):
                raise SourceError("Unexpected PHIP submission schema.")
            for proof in proofs:
                if not isinstance(proof, dict):
                    raise SourceError("Unexpected PHIP proof record (not an object).")
                title = clean(proof.get("nF", ""))
                if not ("聆訊後資料集" in title or re.search(r"\bPHIP\b|Post[- ]Hearing", title, re.I)):
                    continue
                posted = parse_date(proof.get("d", ""))
                if not start <= posted <= report_day:
                    continue
                links = sorted({url for field in ("u1", "u2")
                                if (url := source_link(proof.get(field, ""), PHIP_DOCUMENT_BASE))})
                identity = [board, str(applicant["id"]), posted.isoformat(), title, links]
                key = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
                rows[key] = PHIP(key, clean(applicant["a"]), board,
                                 statuses.get(applicant.get("s"), clean(applicant.get("s"))),
                                 posted.isoformat(), title, links)
    return list(rows.values())


def fetch_phip(client: Client, report_day: date, include_gem: bool) -> list[PHIP]:
    rows: dict[str, PHIP] = {}
    boards = [("sehk", "Main Board")] + ([("gem", "GEM")] if include_gem else [])
    for slug, board in boards:
        # Active feeds retain PHIP history; inactive feeds capture recent status changes.
        # Listed feeds currently have no document history, but are checked as well.
        for stem in ("appactive_appphip", "appinactive", "applisted"):
            url = PHIP_FEED_BASE + f"{stem}_{slug}_c.json"
            try:
                payload = json.loads(client.text(url))
            except json.JSONDecodeError as exc:
                raise SourceError(f"Invalid PHIP JSON: {url}") from exc
            for row in parse_phip(payload, board, report_day):
                rows[row.key] = row
    return sorted(rows.values(), key=lambda row: (row.posted, row.company), reverse=True)


def parse_short_list(document: str, url: str, as_of: date) -> ShortList:
    if not re.search(r"</table\s*>", document, re.I) or not re.search(r"</html\s*>", document, re.I):
        raise SourceError(f"Incomplete short-selling HTML document: {url}")
    soup = parse_html(document, "html.parser")
    content = clean(soup.get_text(" "))
    match = re.search(r"Effective\s+Date\s*:\s*(\d{1,2}/\d{1,2}/\d{4})", content, re.I)
    if not match:
        raise SourceError(f"Short-selling effective date not found: {url}")
    effective = parse_date(match[1])
    if effective > as_of:
        raise SourceError(f"Future-effective short-selling list: {effective}")
    url_date = re.search(r"ds(\d{8})\.htm", url)
    if url_date and effective != parse_date(url_date[1]):
        raise SourceError(f"Short-list date does not match the requested URL: {url}")
    table = None
    for candidate in soup.select("table"):
        first = candidate.find("tr")
        if first and "Stock Code" in first.get_text(" ") and "Stock Short Name" in first.get_text(" "):
            table = candidate
            break
    if table is None:
        raise SourceError("HKEX short-selling securities table not found.")
    securities: dict[str, str] = {}
    numbers: list[int] = []
    for tr in table.select("tr")[1:]:
        cells = tr.find_all(["td", "th"], recursive=False)
        if not cells:
            continue
        if len(cells) < 3:
            raise SourceError("Malformed short-selling row.")
        number, raw_code, name = [clean(c.get_text(" ")) for c in cells[:3]]
        if number == "No." and raw_code == "Stock Code":
            continue
        if not number.isdigit() or not name:
            raise SourceError("Malformed short-selling row values.")
        code = stock_code(raw_code)
        if code in securities:
            raise SourceError(f"Duplicate short-selling code: {code}")
        numbers.append(int(number))
        securities[code] = name
    if not securities or numbers != list(range(1, len(numbers) + 1)):
        raise SourceError("Short-selling list is empty or incomplete (row sequence check failed).")
    return ShortList(effective.isoformat(), url, securities)


def find_short_list(client: Client, as_of: date, lookback: int) -> ShortList:
    for offset in range(lookback):
        candidate = as_of - timedelta(days=offset)
        url = SHORT_URL.format(day=candidate)
        try:
            return parse_short_list(client.text(url), url, as_of)
        except PageMissing:
            continue
        # A blocked/invalid page must fail, not silently skip to an older list.
    raise SourceError(f"No published short-selling list found in {lookback} days ending {as_of}.")


def short_changes(current: ShortList, previous: ShortList | None) -> tuple[dict, dict]:
    if previous is None:
        return {}, {}
    added = {code: current.securities[code] for code in sorted(current.securities.keys() - previous.securities.keys())}
    removed = {code: previous.securities[code] for code in sorted(previous.securities.keys() - current.securities.keys())}
    return added, removed


def short_history_changes(snapshots: list[ShortList]) -> list[dict]:
    """Keep every daily transition, including removals followed by re-additions."""
    ordered = sorted(snapshots, key=lambda item: item.effective)
    if len({item.effective for item in ordered}) != len(ordered):
        raise SourceError("Duplicate effective dates in short-selling history.")
    events = []
    for previous, current in zip(ordered, ordered[1:]):
        added, removed = short_changes(current, previous)
        for action, records in [("ADDED", added), ("REMOVED", removed)]:
            for code, name in records.items():
                events.append({"effective": current.effective, "change": action,
                               "code": code, "name": name, "url": current.url,
                               "previous_effective": previous.effective})
    return sorted(events, key=lambda event: (event["effective"], event["change"], event["code"]), reverse=True)


def recent_trading_dates(document: str, day: date, days: int = 5) -> list[date]:
    """Use the live government general-holiday calendar, including year boundaries."""
    try:
        payload = json.loads(document)
        calendars = payload["vcalendar"]
        holidays = {parse_date(event["dtstart"][0]) for calendar in calendars
                    for event in calendar["vevent"]}
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        raise SourceError("Hong Kong holiday calendar changed format.") from exc
    by_year = {}
    for holiday in holidays:
        by_year.setdefault(holiday.year, set()).add(holiday)
    # Observed holidays may replace 1 January or 25 December when they fall
    # on Sunday. Check full-year coverage rather than requiring those dates.
    covered_years = {year for year, dates in by_year.items()
                     if len(dates) >= 16 and min(dates).month <= 3 and max(dates).month == 12}
    dates = []
    candidate = day
    while len(dates) < days:
        if candidate.year not in covered_years:
            raise SourceError(f"Holiday calendar does not cover {candidate.year}.")
        if candidate.weekday() < 5 and candidate not in holidays:
            dates.append(candidate)
        candidate -= timedelta(days=1)
    return list(reversed(dates))


def fetch_short_history(client: Client, day: date, start: date, lookback: int = 45) -> list[ShortList]:
    """Fetch every dated revision in the window and the preceding effective list.

    Only a confirmed missing page is skipped. A network or parsing failure never
    substitutes an older list or silently hides a daily eligibility change.
    """
    if start > day:
        raise ValueError("Comparison start must not be after the report date.")
    snapshots = []
    for offset in range(lookback):
        candidate = day - timedelta(days=offset)
        url = SHORT_URL.format(day=candidate)
        try:
            item = parse_short_list(client.text(url), url, day)
        except PageMissing:
            continue
        snapshots.append(item)
        if candidate < start:
            return list(reversed(snapshots))
    raise SourceError(f"No short-selling comparison baseline before {start} within {lookback} days; draft withheld.")


def embedded_lockups(document):
    match = re.search(r"\b(?:var|let|const)\s+freefloat_search_card_array\s*=\s*", document)
    if not match: return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(document[match.end():])
        if not isinstance(payload, dict): raise ValueError("Expected object")
        return [row for dates in payload.values() for records in dates.values() for row in records]
    except (ValueError, TypeError, AttributeError) as exc:
        raise SourceError("etnet verification data changed format.") from exc


def decimal_value(text, percent=False):
    match = re.fullmatch(r"\s*([+-]?[\d,]+(?:\.\d+)?)\s*%?\s*", str(text))
    if not match: return None
    try: return Decimal(match[1].replace(",", ""))
    except InvalidOperation: return None


def hkd_millions(raw):
    if raw in ("", "--", "—"): return "—"
    match = re.fullmatch(r"(?:HKD|HK\$)\s*([\d,]+(?:\.\d+)?)\s*(億|萬)?", raw)
    if not match: return raw
    amount = Decimal(match[1].replace(",", ""))
    multiplier = {"億": Decimal(100), "萬": Decimal("0.01"), None: Decimal("0.000001")}[match[2]]
    return f"{amount * multiplier:,.1f}"


def parse_lockups(document, month):
    """Read visible monthly cards; reconcile counts and values to embedded JSON."""
    soup = parse_html(document)
    expected = None
    for anchor in soup.select("a[data-yearmonth]"):
        if anchor.get("data-yearmonth") == month:
            quantity = anchor.select_one(".quantity")
            if quantity and clean(quantity.get_text()).isdigit():
                expected = int(clean(quantity.get_text()))
                break
    rows = {}
    for card in soup.select(".section-card"):
        fields = {}
        for header in card.select(".card-header"):
            value = header.parent.select_one(".card-field")
            if value: fields[clean(header.get_text(" "))] = clean(value.get_text(" "))
        if "解禁日" not in fields: continue
        expiry = parse_date(fields["解禁日"])
        if expiry.strftime("%Y%m") != month: continue
        heading = card.select_one(".card-title h3")
        anchor = card.select_one('.card-title a[href*="ipo-info.php"]')
        match = re.fullmatch(r"(\d{1,5})\s+(.+)", clean(heading.get_text(" ")) if heading else "")
        if not match or not anchor: raise SourceError("A lock-up card is missing its company or code.")
        code = stock_code(match[1])
        url = source_link(anchor["href"], "https://www.etnet.com.hk/")
        query = parse_qs(urlparse(url).query)
        if stock_code(query.get("code", [""])[0]) != code:
            raise SourceError(f"Lock-up stock code/link mismatch: {code}")
        tab = query.get("tab", [""])[0]
        labels = {"cornerstone": ("Cornerstone", "基石投資者總數"),
                  "majorsharesholder": ("Major shareholder", "大股東總數")}
        if tab not in labels: raise SourceError(f"Unknown lock-up investor tab: {code}")
        holder_type, holder_label = labels[tab]
        if holder_label not in fields: raise SourceError(f"Lock-up investor type mismatch: {code}")
        for required in ["解禁總金額", "佔已發行股數", "按盤價", "累積升跌"]:
            if required not in fields: raise SourceError(f"Missing {required} for {code}")
        nominal = card.select_one(".nominal")
        price = clean(nominal.get_text()) if nominal else clean(fields["按盤價"].split()[0])
        quote = next((anchor for anchor in card.select('a[href*="realtime/quote.php"]')
                      if clean(anchor.get_text()) == "即時報價"), None)
        if not quote: raise SourceError(f"Missing quote link for {code}")
        quote_url = source_link(quote["href"], "https://www.etnet.com.hk/")
        if stock_code(parse_qs(urlparse(quote_url).query).get("code", [""])[0]) != code:
            raise SourceError(f"Lock-up quote link/code mismatch: {code}")
        percent = fields["佔已發行股數"]
        amount = fields["解禁總金額"]
        problems = []
        pct = decimal_value(percent)
        if pct is None:
            problems.append("Issued-share percentage unavailable")
        elif not Decimal(0) <= pct <= Decimal(100):
            problems.append(f"Source reports {percent} of issued shares")
        if amount in ("", "--", "—"): problems.append("Unlock value unavailable")
        row = Lockup(code, match[2], expiry.isoformat(), holder_type, fields[holder_label],
                     amount, percent, url, price, tab, "; ".join(problems),
                     fields["累積升跌"], quote_url)
        key = (code, row.expiry, tab)
        if key in rows: raise SourceError(f"Duplicate visible lock-up row: {key}")
        rows[key] = row
    if expected is None:
        raise SourceError(f"etnet monthly row-count control missing for {month}.")
    if len(rows) != expected:
        raise SourceError(f"etnet {month}: page says {expected} records; extracted {len(rows)}. Draft withheld.")
    embedded = embedded_lockups(document)
    if embedded is None:
        raise SourceError("etnet verification data is missing; draft withheld.")
    checks = {}
    for item in embedded:
        def value(key): return clean(item.get(key, {}).get("data", ""))
        expiry = parse_date(value("freefloatdate"))
        if expiry.strftime("%Y%m") != month: continue
        tab = value("freefloat_type")
        code = stock_code(value("stockcode"))
        key = (code, expiry.isoformat(), tab)
        comparison = (value("name"), value("totalcornerstonescnt" if tab == "cornerstone" else "totalmajorsharesholderscnt"),
                      value("currency_totalfreefloatamount"), value("totalpercentofissuedshares"), value("nominal"),
                      value("totalchg_percent"), source_link(item.get("stockcode", {}).get("quotelink", ""), "https://www.etnet.com.hk/"))
        if key in checks and checks[key] != comparison:
            raise SourceError(f"Conflicting etnet verification records: {key}")
        checks[key] = comparison
    if set(rows) != set(checks):
        raise SourceError(f"etnet {month}: visible and embedded lock-up records disagree. Draft withheld.")
    for key, row in rows.items():
        comparison = (row.name, row.holders, row.amount, row.percent, row.price, row.cumulative_change, row.quote_url)
        if comparison != checks[key]:
            raise SourceError(f"etnet values disagree for {row.code} / {row.holder_type}. Draft withheld.")
    return list(rows.values())


class State:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS runs (
            day TEXT NOT NULL, mode TEXT NOT NULL, short_json TEXT NOT NULL,
            phip_json TEXT NOT NULL, created_at TEXT NOT NULL, receipt_json TEXT,
            PRIMARY KEY(day, mode))""")
        self.db.commit()

    def previous(self, day: date, mode: str) -> dict | None:
        row = self.db.execute("SELECT day, short_json, phip_json FROM runs WHERE day < ? AND mode = ? ORDER BY day DESC LIMIT 1",
                              (day.isoformat(), mode)).fetchone()
        if row is None:
            return None
        return {"day": row[0], "short": ShortList(**json.loads(row[1])), "phip": set(json.loads(row[2]))}

    def already_sent(self, day: date) -> bool:
        return self.db.execute("SELECT 1 FROM runs WHERE day=? AND mode='send'",
                               (day.isoformat(),)).fetchone() is not None

    def save(self, day: date, mode: str, short: ShortList, phip: list[PHIP], receipt: dict | None) -> None:
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?, ?)",
                            (day.isoformat(), mode, json.dumps(asdict(short), ensure_ascii=False),
                             json.dumps([p.key for p in phip]), datetime.now(HK).isoformat(),
                             json.dumps(receipt) if receipt else None))

    def close(self) -> None:
        self.db.close()


@contextmanager
def run_lock(state_dir: Path):
    """Cross-platform process lock released automatically if the process exits."""
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / "run.lock").open("a+b") as handle:
        try:
            if os.name == "nt":
                import msvcrt
                if os.fstat(handle.fileno()).st_size == 0:
                    handle.write(b"0"); handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("Another digest process is already running.") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)




def e(value):
    return html.escape(str(value), quote=True)


def link(url, label):
    return f'<a href="{e(url)}" style="color:#263d57;text-decoration:none;border-bottom:1px solid #c7cdd4">{e(label)}</a>' if url else e(label)


def nice_date(value, year=False):
    return parse_date(value).strftime("%d %b %Y" if year else "%d %b")


def badge(label, color="neutral"):
    colors = {"neutral": ("#f1f3f5", "#4b5563"), "green": ("#087f38", "#ffffff"),
              "red": ("#dc2626", "#ffffff"), "blue": ("#175cff", "#ffffff"),
              "amber": ("#ffcc33", "#332700")}
    background, foreground = colors[color]
    return f'<span style="display:inline-block;padding:3px 7px;font-size:10px;font-weight:700;letter-spacing:.5px;background:{background};color:{foreground};white-space:nowrap">{e(label)}</span>'


def table(headers, rows, highlighted=None):
    if not rows: return '<p style="font-size:13px;color:#6b7280">No updates in this period.</p>'
    head = ''.join(f'<th style="text-align:{"right" if h.startswith("#") else "left"};padding:9px 10px;border-bottom:2px solid #c8cdd3;font-size:10px;font-weight:700;color:#69717b;letter-spacing:.45px;white-space:nowrap">{e(h.lstrip("#"))}</th>' for h in headers)
    body = []
    for index, row in enumerate(rows):
        background = '#fff8e8' if highlighted and index in highlighted else '#ffffff'
        cells = []
        for number, value in enumerate(row):
            align = 'right' if headers[number].startswith('#') else 'left'
            cells.append(f'<td style="text-align:{align};padding:11px 10px;vertical-align:top;border-bottom:1px solid #e7e9ec;background:{background};font-size:12px;line-height:1.5">{value}</td>')
        body.append('<tr>' + ''.join(cells) + '</tr>')
    return '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse">' + '<thead><tr>' + head + '</tr></thead><tbody>' + ''.join(body) + '</tbody></table>'


def section(number, title, detail):
    return (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top:30px;margin-bottom:10px;border-top:1px solid #cbd0d5"><tr><td style="padding-top:17px">'
            f'<span style="font-size:11px;color:#b41529;font-weight:700;margin-right:10px">{number:02d}</span>'
            f'<span style="font-size:16px;font-weight:700;letter-spacing:-.2px">{e(title)}</span>'
            f'<div style="font-size:11px;color:#69717b;margin-top:5px">{detail}</div></td></tr></table>')


def eligibility(row, report):
    code = row['code']
    if code not in report['short']['securities']: return 'NO', 'red'
    if code in report['added']: return 'NEW', 'blue'
    return 'YES', 'green'


def email_subject(report):
    return EMAIL_SUBJECT.replace('{date}', parse_date(report['day']).strftime('%d %b %Y'))


def render_report(report):
    day = parse_date(report['day'])
    visible_lockups = report['lockups']  # Preserve flagged rows; mark for review instead of silently hiding
    subject = email_subject(report)
    short = report['short']
    window = report['short_window']
    events = report['short_changes']
    addition_count = sum(event['change'] == 'ADDED' for event in events)
    removal_count = sum(event['change'] == 'REMOVED' for event in events)
    text = [subject, '', f'Updated {datetime.fromisoformat(report["generated_at"]):%d %b %Y, %H:%M} HKT', '']
    fragments = []
    fragments.append('<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#202a36;color:white;border-top:5px solid #b41529"><tr><td style="padding:25px 28px 26px">'
                     '<div style="font-size:27px;line-height:1.2;font-weight:700;letter-spacing:-.6px">IPO, PHIP &amp; Lock-up Update</div>'
                     f'<div style="font-size:12px;color:#d3d9df;margin-top:12px">{day:%A, %d %B %Y} &nbsp; · &nbsp; Updated {datetime.fromisoformat(report["generated_at"]):%H:%M} HKT</div></td></tr></table>')
    stats = [(str(len(report['ipos'])), 'MAIN BOARD IPOs'), (str(len(report['phip'])), 'PHIPs · 7 DAYS'),
             (f'+{addition_count} / −{removal_count}', 'SHORT-LIST CHANGES · 5 DAYS'),
             (str(len(visible_lockups)), 'LOCK-UP TRANCHES / %d REVIEW' % sum(bool(r['issue']) for r in visible_lockups))]
    fragments.append('<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-bottom:1px solid #d9dde2"><tr>' +
                     ''.join(f'<td width="25%" style="padding:18px 18px 17px;border-right:1px solid #eceef1"><div style="font-size:25px;color:#202a36;font-weight:700;line-height:1.2">{e(value)}</div><div style="font-size:9px;color:#707985;letter-spacing:.8px;margin-top:7px">{label}</div></td>' for value, label in stats) + '</tr></table>')
    fragments.append('<div style="padding:0 28px 25px">')
    fragments.append(section(1, 'IPO pipeline', link(MAIN_BOARD_URL, 'Main Board')))
    ipo_rows = []
    text.append('1. IPO PIPELINE — MAIN BOARD')
    for row in report['ipos']:
        documents = []
        for key, label in [('announcements', 'Announcement'), ('prospectuses', 'Prospectus'), ('allotment_results', 'Allotment')]:
            documents.extend(link(url, label + (f' {i}' if len(row[key]) > 1 else '')) for i, url in enumerate(row[key], 1))
        ipo_rows.append([f'<strong>{e(row["code"])}</strong>', e(row['name']), '<br>'.join(documents) or '—'])
        text.append(f'{row["code"]} | {row["name"]}')
        for key in ['announcements', 'prospectuses', 'allotment_results']:
            text.extend(f'  {key}: {url}' for url in row[key])
    fragments.append(table(['CODE', 'ISSUER', 'DOCUMENTS'], ipo_rows))
    phip_range = f'{nice_date(report["phip_start"])}–{nice_date(report["day"])} · past 7 calendar days'
    fragments.append(section(2, 'PHIP updates', e(phip_range)))
    text.extend(['', '2. PHIP UPDATES', phip_range])
    phip_rows, highlights = [], set()
    for row in report['phip']:
        new = badge('NEW', 'blue') + ' ' if row['new'] else ''
        if row['new']: highlights.add(len(phip_rows))
        phip_rows.append([e(nice_date(row['posted'])), new + e(row['company']), e(row['board']),
                          e(row['title']) + '<br>' + ' · '.join(link(url, 'PDF' if url.lower().endswith('.pdf') else 'Documents') for url in row['links'])])
        text.append(f'{row["posted"]} | {row["company"]} | {row["board"]} | {row["title"]}' + (' | NEW' if row['new'] else ''))
        text.extend(row['links'])
    fragments.append(table(['POSTED', 'ISSUER', 'BOARD', 'FILING'], phip_rows, highlights))
    if not phip_rows: text.append('No filings in the seven-day window.')
    comparison = f'{nice_date(window["start"], True)}–{nice_date(window["end"], True)} · {window["label"]}'
    detail = 'Latest effective list: ' + link(short['url'], nice_date(short['effective'], True))
    fragments.append(section(3, 'Short-selling eligibility', detail))
    fragments.append(f'<p style="font-size:11px;color:#69717b;margin:0 0 10px">{e(comparison)} &nbsp; · &nbsp; {len(short["securities"]):,} eligible securities.</p>')
    text.extend(['', '3. SHORT-SELLING ELIGIBILITY', comparison, 'Latest effective list: ' + short['effective']])
    changes = []
    for event in events:
        color = 'blue' if event['change'] == 'ADDED' else 'red'
        changes.append([e(nice_date(event['effective'], True)), badge(event['change'], color),
                        '<strong>' + e(event['code']) + '</strong>', e(event['name'])])
        text.append(f'{event["effective"]} | {event["change"]} | {event["code"]} | {event["name"]}')
    if changes:
        fragments.append(table(['EFFECTIVE DATE', 'CHANGE', 'CODE', 'HKEX SHORT NAME'], changes))
        if not removal_count: fragments.append('<p style="font-size:11px;color:#69717b;margin:8px 0 0">Removals: none.</p>')
    else:
        fragments.append('<p style="font-size:13px">No additions or removals in this period.</p>')
        text.append('No additions or removals in this period.')
    fragments.append(section(4, 'Lock-up calendar', f'{nice_date(report["day"])} through {datetime.strptime(report["months"][-1], "%Y%m"):%B %Y} &nbsp; · &nbsp; Upcoming expiries only'))
    fragments.append('<p style="font-size:11px;color:#69717b;margin:0 0 12px">' + badge('YES', 'green') + ' shortable &nbsp; ' + badge('NEW', 'blue') + ' added within the comparison period &nbsp; ' + badge('NO', 'red') + ' not shortable</p>')
    text.extend(['', '4. LOCK-UP CALENDAR', 'YES = shortable; NEW = added within the comparison period; NO = not shortable.'])
    last_added = {}
    for event in events:
        if event['change'] == 'ADDED':
            last_added[event['code']] = max(event['effective'], last_added.get(event['code'], ''))
    for month in report['months']:
        monthly = [r for r in visible_lockups if r['expiry'].replace('-', '').startswith(month)]
        label = datetime.strptime(month, '%Y%m').strftime('%B %Y').upper()
        fragments.append(f'<div style="margin:18px 0 4px;font-size:11px;font-weight:700;letter-spacing:1px;color:#49515c">{label} <span style="font-weight:400;letter-spacing:0;color:#7b838e"> / {len(monthly)} tranches</span></div>')
        rows, highlights = [], set()
        for row in monthly:
            days = (parse_date(row['expiry']) - day).days
            tag, color = eligibility(row, report)
            if tag == 'NEW' or row['issue']: highlights.add(len(rows))
            relative_date = 'Today' if days == 0 else f'In {days} days'
            date_cell = '<strong style="white-space:nowrap">' + e(row['expiry'].replace('-', '/')) + '</strong>' + f'<br><span style="font-size:10px;color:#7b838e">{relative_date}</span>'
            security = '<strong>' + link(row['url'], row['code'] + ' ' + row['name']) + '</strong>'
            holder_label = '基石投資者總數' if row['tab'] == 'cornerstone' else '大股東總數'
            holder = f'<span style="color:#7b838e;font-size:10px;white-space:nowrap">{holder_label}</span><br><strong>{e(row["holders"])}</strong>'
            price = '<strong>' + e(row['price']) + '</strong><br><span style="font-size:10px;white-space:nowrap">' + link(row['quote_url'], '即時報價') + '</span>'
            change_parts = row['cumulative_change'].split(' ', 1)
            change_color = '#c7202b' if row['cumulative_change'].startswith('-') else '#087f38'
            change_value = '<span style="color:' + change_color + ';white-space:nowrap">' + '<br>'.join(e(part) for part in change_parts) + '</span>'
            short_cell = badge(tag, color)
            if tag == 'NEW':
                short_cell += '<br><span style="font-size:10px;white-space:nowrap;color:#175cff">' + e(nice_date(last_added[row['code']])) + '</span>'
            if row['issue']:
                short_cell += '<br>' + badge('REVIEW', 'amber') + '<br><span style="font-size:10px;color:#795b00">' + e(row['issue']) + '</span>' 
            rows.append([date_cell, security, holder, '<span style="white-space:nowrap">' + e(row['amount']) + '</span>',
                         e(row['percent']), price, change_value, short_cell])
            text.append(f'{row["expiry"]} | {row["code"]} {row["name"]} | {holder_label} {row["holders"]} | 解禁總金額 {row["amount"]} | 佔已發行股數 {row["percent"]} | 按盤價 {row["price"]} | 累積升跌 {row["cumulative_change"]} | Shortable: {tag}')
            if row['issue']: text.append('  MANUAL REVIEW: ' + row['issue'])
            text.extend([row['url'], '即時報價: ' + row['quote_url']])
        fragments.append(table(['解禁日', '股票', '投資者／股東', '#解禁總金額', '#佔已發行股數', '#按盤價', '#累積升跌', 'SHORTABLE'], rows, highlights))
    quote_asof = ', '.join(f"{month}: {when} HKT" for month, when in report.get('source_asof', {}).items() if when)
    note = 'Public-source compilation for manual review before distribution. HKEX: listing/PHIP/short-selling; etnet: lock-ups. Prices from etnet are delayed at least 15 minutes.'
    if quote_asof:
        note += ' etnet indicated update times: ' + quote_asof + '.'
    fragments.append('<p style="font-size:10px;line-height:1.5;color:#68717d;margin:18px 0 8px;border-top:1px solid #e0e4e8;padding-top:14px">' + e(note) + '</p>')
    text.extend(['', note])
    fragments.append('</div>')
    content = ''.join(fragments)
    document = '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + e(subject) + '</title></head><body style="margin:0;background:#edf0f3;color:#222b36;font-family:Arial,Helvetica,\'Microsoft JhengHei\',sans-serif"><div id="email-content" style="max-width:1080px;margin:22px auto;background:white;color:#222b36;font-family:Arial,Helvetica,\'Microsoft JhengHei\',sans-serif">' + content + '</div></body></html>'
    return document, '\n'.join(text) + '\n'


def make_email(report, html_body, text_body):
    message = EmailMessage(policy=SMTP)
    message['Subject'] = email_subject(report)
    if EMAIL_TO.strip():
        message['To'] = ', '.join(x.strip() for x in re.split(r'[,;]+', EMAIL_TO) if x.strip())
    if EMAIL_CC.strip():
        message['Cc'] = ', '.join(x.strip() for x in re.split(r'[,;]+', EMAIL_CC) if x.strip())
    message['Date'] = format_datetime(datetime.now(HK))
    message['Message-ID'] = make_msgid(domain='ipo-daily.local')
    message['X-Unsent'] = '1'
    message.set_content(text_body)
    message.add_alternative(html_body, subtype='html')
    return message


def preview_document(document, draft_name):
    toolbar = '<div style="max-width:1080px;margin:20px auto 0;display:flex;gap:10px;align-items:center;font-family:Arial,sans-serif"><button onclick="copyEmail()" style="background:#263443;color:white;border:0;padding:11px 17px;cursor:pointer;font-weight:600">Copy formatted email</button><a href="' + e(draft_name) + '" download style="color:#263443;font-size:12px;text-decoration:none;border:1px solid #bac1c9;padding:10px 15px">Download email draft</a><span id="copy-status" style="font-size:12px;color:#5a6470">Paste into an Outlook email.</span></div>'
    script = '''<script>
async function copyEmail(){
 const box=document.getElementById('email-content');
 const status=document.getElementById('copy-status');
 try {
   if(navigator.clipboard && window.ClipboardItem){
     await navigator.clipboard.write([new ClipboardItem({'text/html':new Blob([box.outerHTML],{type:'text/html'}),'text/plain':new Blob([box.innerText],{type:'text/plain'})})]);
   } else {
     const selection=window.getSelection(); const range=document.createRange(); range.selectNodeContents(box);
     selection.removeAllRanges(); selection.addRange(range);
     if(!document.execCommand('copy')) throw new Error('Clipboard unavailable');
     selection.removeAllRanges();
   }
   status.textContent='Copied. Paste into your email compose window.';
 } catch(error) {
   const selection=window.getSelection(); const range=document.createRange(); range.selectNodeContents(box);
   selection.removeAllRanges(); selection.addRange(range);
   status.textContent='Email selected. Press Ctrl+C (Windows) or Command+C (Mac), then paste.';
 }
}
</script>'''
    return document.replace('<div id="email-content"', toolbar + '<div id="email-content"', 1).replace('</body>', script + '</body>')


def build_report(client: Client, state: State, day: date, mode: str,
                 include_gem: bool, include_expired: bool, lookback: int) -> dict:
    ipos = parse_ipos(client.text(MAIN_BOARD_URL))
    phip = fetch_phip(client, day, include_gem)
    trading_dates = recent_trading_dates(client.text(HOLIDAYS_URL), day)
    snapshots = fetch_short_history(client, day, trading_dates[0], lookback=lookback)
    short = snapshots[-1]
    changes = short_history_changes(snapshots)
    baseline = {"effective": snapshots[0].effective, "url": snapshots[0].url}
    # These membership maps are for current lock-up badges. The dated event log
    # remains authoritative for daily counts and includes round-trip changes.
    added = {event["code"]: short.securities[event["code"]] for event in changes
             if event["change"] == "ADDED" and event["code"] in short.securities}
    removed = {event["code"]: event["name"] for event in changes
               if event["change"] == "REMOVED" and event["code"] not in short.securities}
    previous = state.previous(day, mode)
    notes: list[str] = []
    if previous:
        for filing in phip: filing.new = filing.key not in previous["phip"]
    months = month_keys(day)
    lockups: dict[tuple, Lockup] = {}
    for month in months:
        for row in parse_lockups(client.text(LOCKUP_URL.format(month=month)), month):
            if include_expired or parse_date(row.expiry) >= day:
                lockups[(row.code, row.expiry, row.holder_type)] = row
    if parse_date(short.effective) < day:
        notes.append(f'Latest available HKEX shortable list is effective {short.effective}; no later dated page was found through {day}.')
    notes.append("Lock-up window includes the current and next calendar month" +
                 (", including earlier expiries this month." if include_expired else ", with expiries on or after the report date."))
    notes.append("The IPO source lists current announcements and prospectuses; it does not provide scheduled listing dates.")
    return {"day": day.isoformat(), "generated_at": datetime.now(HK).isoformat(), "mode": mode,
            "months": months, "phip_start": (day - timedelta(days=6)).isoformat(),
            "ipos": [asdict(r) for r in ipos], "phip": [asdict(r) for r in phip],
            "short": asdict(short), "baseline": baseline, "added": added, "removed": removed,
            "short_changes": changes,
            "short_window": {"days": 5, "start": trading_dates[0].isoformat(), "end": day.isoformat(),
                             "label": "past 5 trading days", "dates": [d.isoformat() for d in trading_dates],
                             "lists": [{"effective": item.effective, "url": item.url,
                                        "count": len(item.securities)} for item in snapshots]},
            "lockups": [asdict(r) for r in sorted(lockups.values(), key=lambda r: (r.expiry, r.code, r.holder_type))],
            "notes": notes}


def atomic_write(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)




def generate_draft(directory: Path, day: date | None = None):
    """Collect and validate sources, then write the Outlook email and audit files."""
    day = day or datetime.now(HK).date()
    directory = Path(directory).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    with run_lock(directory / '.history'):
        state = State(directory / '.history' / 'daily.sqlite3')
        try:
            client = Client()
            report = build_report(client, state, day, 'draft', INCLUDE_GEM_PHIPS,
                                  INCLUDE_EXPIRED_THIS_MONTH, SHORT_HISTORY_LOOKBACK_DAYS)
            report['source_asof'] = {}
            for month in report['months']:
                source = client.cache[LOCKUP_URL.format(month=month)]
                match = re.search(r'解禁總金額\s*=.*?更新[：:]\s*(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2})', source, re.S)
                if not match:
                    if any(row['expiry'].replace('-', '').startswith(month) for row in report['lockups']):
                        raise SourceError(f'etnet quote timestamp missing for {month}; draft withheld.')
                    report['source_asof'][month] = None
                    continue
                quote_time = datetime.strptime(match[1], '%d/%m/%Y %H:%M').replace(tzinfo=HK)
                if quote_time.date() > datetime.now(HK).date():
                    raise SourceError(f'Future etnet quote timestamp: {match[1]}')
                report['source_asof'][month] = match[1]

            email_html, plain_text = render_report(report)
            message = make_email(report, email_html, plain_text)
            base = directory / f'HK_Equities_{day.isoformat()}'
            raw_email_path = directory / (base.name + '_email.html')
            preview_path = directory / (base.name + '_preview.html')
            eml_path = base.with_suffix('.eml')
            files = {
                raw_email_path: email_html.encode('utf-8'),
                preview_path: preview_document(email_html, eml_path.name).encode('utf-8'),
                eml_path: message.as_bytes(),
                base.with_suffix('.txt'): plain_text.encode('utf-8'),
                base.with_suffix('.json'): json.dumps(report, ensure_ascii=False, indent=2).encode('utf-8'),
            }
            for target, contents in files.items():
                atomic_write(target, contents)
            state.save(day, 'draft', ShortList(**report['short']),
                       [PHIP(**item) for item in report['phip']], None)
            return preview_path, raw_email_path, eml_path, report
        finally:
            state.close()



def report_summary(report):
    review = sum(bool(r['issue']) for r in report['lockups'])
    added = sum(event['change'] == 'ADDED' for event in report['short_changes'])
    removed = sum(event['change'] == 'REMOVED' for event in report['short_changes'])
    return (f'{len(report["ipos"])} IPOs · {len(report["phip"])} PHIPs · '
            f'+{added}/−{removed} short-list changes over 5 days\n'
            f'{len(report["lockups"])} lock-up tranches ({review} requiring review)')




def _ps_quote(value: str) -> str:
    """Safely embed a path or subject as a literal in PowerShell source."""
    return "'" + str(value).replace("'", "''") + "'"


def _prepend_to_outlook_signature(report_html: str, existing_signature_html: str) -> str:
    """Insert the digest above Outlook's configured personal/corporate signature."""
    signature = existing_signature_html or ''
    if not signature.strip():
        return report_html
    match = re.search(r'<body[^>]*>(.*?)</body>', report_html, re.I | re.S)
    content = match.group(1) if match else report_html
    body_start = re.search(r'<body[^>]*>', signature, re.I | re.S)
    if body_start:
        return signature[:body_start.end()] + content + '<div style="height:18px"></div>' + signature[body_start.end():]
    return report_html + '<div style="height:18px"></div>' + signature


def open_classic_outlook_draft(raw_email_path: Path, report: dict) -> tuple[bool, str]:
    """Create a saved, editable Outlook draft, opening it without sending.

    Classic Outlook for Windows supports COM. Try pywin32 first; if it is not
    installed or COM fails, use Windows PowerShell COM without installing a package.
    New Outlook / web Outlook generally do not support local COM automation.
    """
    if os.name != 'nt':
        return False, 'This is not Windows; local Classic Outlook automation was skipped.'

    subject = email_subject(report)
    html_body = raw_email_path.read_text(encoding='utf-8')
    errors = []
    try:
        import win32com.client  # optional; no pip install necessary when PowerShell works
        outlook = win32com.client.Dispatch('Outlook.Application')
        draft = outlook.CreateItem(0)
        draft.Subject = subject
        draft.To = EMAIL_TO.replace(',', ';').strip()
        draft.CC = EMAIL_CC.replace(',', ';').strip()
        draft.Display()   # Let Outlook insert the user's configured signature.
        signature_html = draft.HTMLBody
        draft.HTMLBody = _prepend_to_outlook_signature(html_body, signature_html)
        draft.Save()      # Save to the default Outlook account's Drafts folder; NO Send call.
        return True, 'Outlook editable draft is open and has been saved to Drafts.'
    except Exception as exc:
        errors.append('pywin32: ' + str(exc))

    # PowerShell is a useful fallback on managed desktops without pywin32.
    # All user text and paths are represented as quoted literals, never shell args.
    commands = '\n'.join([
        "$ErrorActionPreference = 'Stop'",
        "$outlook = New-Object -ComObject Outlook.Application",
        "$mail = $outlook.CreateItem(0)",
        '$mail.Subject = ' + _ps_quote(subject),
        '$mail.To = ' + _ps_quote(EMAIL_TO.replace(',', ';')),
        '$mail.CC = ' + _ps_quote(EMAIL_CC.replace(',', ';')),
        '$mail.Display()',
        '$signature = $mail.HTMLBody',
        '$html = [System.IO.File]::ReadAllText(' + _ps_quote(str(raw_email_path)) + ', [System.Text.Encoding]::UTF8)',
        "$matchedBody = [regex]::Match($html, '(?is)<body[^>]*>(.*?)</body>')",
        '$content = if ($matchedBody.Success) { $matchedBody.Groups[1].Value } else { $html }',
        "$start = [regex]::Match($signature, '(?is)<body[^>]*>')",
        'if ($start.Success) { $mail.HTMLBody = $signature.Insert($start.Index + $start.Length, $content + \'<div style="height:18px"></div>\') }',
        'else { $mail.HTMLBody = $html + $signature }',
        '$mail.Save()',
    ])
    encoded = base64.b64encode(commands.encode('utf-16le')).decode('ascii')
    try:
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
            capture_output=True, text=True, timeout=35, check=False,
        )
        if result.returncode == 0:
            return True, 'Outlook editable draft opened using built-in Windows PowerShell.'
        errors.append('PowerShell: ' + (result.stderr or result.stdout or 'unknown error').strip()[:400])
    except (OSError, subprocess.TimeoutExpired) as exc:
        errors.append('PowerShell: ' + str(exc))
    return False, 'Classic Outlook automation unavailable (New Outlook or IT restrictions possible). ' + ' | '.join(errors)


def run_now():
    """Call exactly once when the cell is run; no scheduler or automatic sending."""
    output = (ROOT / OUTPUT_FOLDER).expanduser().resolve()
    print('Checking live public sources: HKEX, Hong Kong holiday calendar, etnet ...')
    if HTTPS_PROXY_URL.strip():
        print('Using configured corporate proxy: ' + urlparse(HTTPS_PROXY_URL).netloc)
    print('Email will NOT be sent automatically.\n')
    try:
        preview_path, raw_email_path, eml_path, report = generate_draft(output)
    except SourceNetworkError as exc:
        print('\nNETWORK BLOCKED — DRAFT NOT CREATED')
        print(str(exc))
        print('\nTry opening the URL in Microsoft Edge on the SAME computer.')
        print('If Edge works but this still fails, ask IT for the approved proxy/PAC settings.')
        print('No incomplete report was generated; no email was sent.')
        return None
    except SourceError as exc:
        print('\nSOURCE COULD NOT BE VERIFIED — DRAFT NOT CREATED')
        print(type(exc).__name__ + ': ' + str(exc))
        print('No incomplete report was generated; no email was sent.')
        return None

    print('\nDRAFT READY: ' + email_subject(report))
    print(report_summary(report))
    print('Files saved in:', output)
    print('Editable email file:', eml_path.name)
    print('Preview:', preview_path.name)
    print('JSON audit trail:', report['day'] + ' / ' + str(len(report['short_changes'])) + ' short-list events')
    if any(row['issue'] for row in report['lockups']):
        print('DATA REVIEW: some lock-up records were flagged in amber (retained, not silently dropped).')

    launched, detail = (False, 'Outlook opening disabled in settings.')
    if OPEN_OUTLOOK:
        launched, detail = open_classic_outlook_draft(raw_email_path, report)
    print('\n' + detail)

    if not launched and SHOW_NOTEBOOK_PREVIEW_IF_NO_OUTLOOK:
        print('Showing the formatted preview within Jupyter instead. Use the .eml file or copy it into Outlook.')
        try:
            from IPython.display import HTML, FileLink, display
            display(FileLink(str(eml_path.relative_to(ROOT))))
            display(HTML(raw_email_path.read_text(encoding='utf-8')))
        except ImportError:
            print('View the HTML preview in your browser:', preview_path)
            webbrowser.open(preview_path.as_uri())
    return {'preview': preview_path, 'email_html': raw_email_path, 'eml': eml_path, 'report': report}


# This guard is True in a pasted Jupyter code cell or when run as a .py script.
# Importing as a library will not accidentally generate drafts.
if __name__ == '__main__':
    LAST_DRAFT = run_now()
