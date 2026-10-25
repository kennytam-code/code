#!/usr/bin/env python3
"""HK Equities Daily — one run creates a formatted, unsent Outlook draft.

Designed for a SINGLE Jupyter code cell or `python HK_Equities_Bloomberg.py`.
Works with Python 3.8+ standard libraries to gather public data. On Windows it
opens an editable draft in Classic Outlook via pywin32 or PowerShell COM.
No message is sent. If Outlook automation is unsupported, an HTML preview,
.eml file, and other audit files are created in the output folder.

Bloomberg setup: run on your logged-in Bloomberg desktop with Desktop API access.
Install blpapi into the same Python environment as Jupyter, following:
https://professional.bloomberg.com/support/api-library/
python -m pip install --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi

The final section includes unlock / free-float market cap (%) and unlock / 20-day
average turnover (x). Monetary inputs are normalized to absolute HKD. Bloomberg
errors appear as N/A with review reasons; set BLOOMBERG_REQUIRED to True to
withhold the draft if any ratio is unavailable. Nothing is sent automatically.
"""

from __future__ import annotations

import os

# ===================== EDIT ONLY THESE SETTINGS =====================
EMAIL_SUBJECT = "IPO, PHIP & Lock-up Update | {date}"
EMAIL_TO = os.environ.get("HK_EQUITIES_EMAIL_TO", "")      # Optional: recipient addresses separated by semicolons
EMAIL_CC = os.environ.get("HK_EQUITIES_EMAIL_CC", "")      # Optional: CC addresses separated by semicolons
OUTPUT_FOLDER = "HK_Equities_Drafts"   # Created beneath the Jupyter working directory
OPEN_OUTLOOK = True                    # Show a real editable Outlook draft when possible
SHOW_NOTEBOOK_PREVIEW_IF_NO_OUTLOOK = True
INCLUDE_GEM_PHIPS = True
INCLUDE_EXPIRED_THIS_MONTH = False
SHORT_HISTORY_LOOKBACK_DAYS = 45
# In a corporate PowerShell Constrained Language environment, the old
# PowerShell web-download fallback fails. Stay on the confirmed Python proxy.
NETWORK_MODE = "urllib"       # Recommended. "auto" / "windows_proxy" are legacy options.
NETWORK_TIMEOUT_SECONDS = 18 # Per-socket inactivity limit; prevents a stalled source holding everything up
ETNET_TIMEOUT_SECONDS = 22    # Slightly more leeway for the larger etnet pages
NETWORK_RETRIES = 2           # Other public sources: retry recoverable download errors.
ETNET_RETRIES = 2             # Avoid multi-minute loops on repeated proxy 503s.
NETWORK_RETRY_PAUSE_SECONDS = 1
SHOW_DOWNLOAD_TIMINGS = True   # Identify a slow/blocked source directly in Jupyter
ETNET_CACHE_ENABLED = True     # Save fully verified etnet data immediately when each month succeeds
ETNET_CACHE_MAX_MINUTES = 120  # ONLY reuse within this many minutes, and ONLY on the same HKT day
USE_GZIP_COMPRESSION = True    # Request smaller HTTP transfers; verify decompression and full response
WINDOWS_PROXY_TIMEOUT_SECONDS = 35  # Legacy fallback, not used in "urllib" mode
# Optional: if Edge opens the etnet page but Python still times out, save the
# CURRENT page as HTML in this directory using a filename like etnet_202610.html.
# Only a recent file from a matching month is accepted and fully validated.
ALLOW_MANUAL_ETNET_HTML = True
MANUAL_ETNET_FOLDER = "HK_Equities_Drafts/manual_etnet"
MANUAL_ETNET_MAX_AGE_HOURS = 24
# Keep the original working corporate proxy unless explicitly overridden.
# A missing or blank HK_EQUITIES_HTTPS_PROXY keeps the original default.
# Use http:// here: the HTTP proxy CONNECT-tunnels HTTPS destinations.
# Never store company passwords or tokens in this notebook.
# If your approved proxy changes, update this single line.
HTTPS_PROXY_URL = os.environ.get("HK_EQUITIES_HTTPS_PROXY", "").strip() or "http://instinetpxy.nomura.com:8080"

# Bloomberg connects to the local Desktop API, not the public-web HTTP proxy.
BLOOMBERG_ENABLED = True
BLOOMBERG_REQUIRED = False          # True: withhold draft if any ratio is unavailable
BLOOMBERG_HOST = "localhost"
BLOOMBERG_PORT = 8194
BLOOMBERG_CONNECT_TIMEOUT_MS = 5000
BLOOMBERG_REQUEST_TIMEOUT_SECONDS = 30
BLOOMBERG_BATCH_SIZE = 100           # Unique securities per request
# Blank = Bloomberg's latest 20D interval; optional historical end date YYYYMMDD.
# This affects turnover ONLY. Market cap/free-float remain current snapshots;
# etnet unlock values retain the source quote timestamp shown in the report.
BLOOMBERG_TURNOVER_END_DATE = ""
# ====================================================================

from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import base64
import subprocess
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import format_datetime, make_msgid
from html.parser import HTMLParser
import http.client
import zlib
import hashlib
import html
import json
import logging
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


def _read_complete_response(response, url, max_bytes=20_000_000):
    """Read the full HTTP response, never trusting or returning truncated data.

    A company proxy sometimes closes HTTP/1.1 chunked responses before the
    terminating chunk is received. `http.client.IncompleteRead` must cause a
    fresh request, not be mistaken for a valid partial webpage. Bounded small
    reads also avoid allocating a 20 MB read buffer on every request.
    """
    chunks = []
    total = 0
    while True:
        part = response.read(64 * 1024)
        if not part:
            break
        total += len(part)
        if total > max_bytes:
            raise SourceError('Source exceeds the allowed download size: ' + url)
        chunks.append(part)
    # For non-chunked responses a premature EOF may not always raise.
    # Only check numeric Content-Length when HTTP transfers are not chunked.
    transfer_encoding = (response.headers.get('Transfer-Encoding') or '').lower()
    length = response.headers.get('Content-Length')
    if 'chunked' not in transfer_encoding and length and length.isdecimal():
        if total != int(length):
            raise http.client.IncompleteRead(b'', int(length) - total)
    return b''.join(chunks)


def _decode_http_encoding(raw, encoding, url, limit=20_000_000):
    """Handle HTTP gzip/deflate with a strict decompressed-size and stream-integrity check."""
    encoding = (encoding or '').strip().lower()
    if not encoding or encoding == 'identity':
        return raw
    if encoding not in ('gzip', 'deflate'):
        raise SourceError('Unsupported Content-Encoding ' + repr(encoding) + ': ' + url)
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS if encoding == 'gzip' else zlib.MAX_WBITS)
    try:
        data = decoder.decompress(raw, limit + 1)
        if len(data) > limit or decoder.unconsumed_tail:
            raise SourceError('Uncompressed webpage exceeds safety limit: ' + url)
        data += decoder.flush(limit + 1 - len(data))
        if not decoder.eof:
            raise http.client.IncompleteRead(data)
        if len(data) > limit or decoder.unused_data:
            raise SourceError('Unexpected extra bytes in compressed response: ' + url)
        return data
    except zlib.error as exc:
        raise http.client.IncompleteRead(b'') from exc


def _etnet_month(url):
    parsed = urlparse(url)
    if parsed.hostname != 'www.etnet.com.hk' or parsed.path != '/www/tc/stocks/ipo-free-float.php':
        return None
    month = parse_qs(parsed.query).get('month', [''])[0]
    return month if re.fullmatch(r'\d{6}', month) else None


def _verified_etnet_cache_paths(month):
    directory = ROOT / OUTPUT_FOLDER / '.history' / 'verified_etnet_cache'
    base = 'etnet_' + month + '_'
    return directory / (base + 'verified.html'), directory / (base + 'verified.json')


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
        self.manual_sources = {}
        self.cached_sources = {}
        self.windows_proxy_worked = NETWORK_MODE == 'windows_proxy'
        if NETWORK_MODE not in ('auto', 'urllib', 'windows_proxy'):
            raise ValueError('NETWORK_MODE must be auto, urllib, or windows_proxy.')
        if not isinstance(NETWORK_RETRIES, int) or NETWORK_RETRIES < 1:
            raise ValueError('NETWORK_RETRIES must be a positive integer.')
        if not isinstance(ETNET_RETRIES, int) or ETNET_RETRIES < 1:
            raise ValueError('ETNET_RETRIES must be a positive integer.')
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

    def _recent_manual_etnet(self, url):
        """Use only a fresh, locally browser-saved etnet page for this exact month.

        It still passes through the normal strict visible/embedded-source parsing.
        The file must be obtained by the user through an approved browser session.
        """
        if not ALLOW_MANUAL_ETNET_HTML:
            return None
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname != 'www.etnet.com.hk' or \
                parsed.path != '/www/tc/stocks/ipo-free-float.php':
            return None
        month = parse_qs(parsed.query).get('month', [''])[0]
        if not re.fullmatch(r'\d{6}', month):
            return None
        source = (ROOT / MANUAL_ETNET_FOLDER / ('etnet_' + month + '.html')).resolve()
        if not source.is_file():
            return None
        age_seconds = time.time() - source.stat().st_mtime
        max_age = MANUAL_ETNET_MAX_AGE_HOURS * 3600
        if not 0 <= age_seconds <= max_age:
            raise SourceNetworkError(
                'The manual etnet HTML file is older than ' + str(MANUAL_ETNET_MAX_AGE_HOURS)
                + ' hours or has an invalid modification time: ' + str(source)
                + '. Save a fresh page from Edge; do not use stale lock-up data.'
            )
        raw = source.read_bytes()
        if not raw or len(raw) > 20_000_000:
            raise SourceError('The manual etnet HTML file is empty or unexpectedly large: ' + str(source))
        try:
            page = _decode_source(url, raw)
        except (UnicodeError, LookupError) as exc:
            raise SourceError('Cannot decode manual etnet HTML file: ' + str(source)) from exc
        self.cache[url] = page
        self.manual_sources[month] = datetime.fromtimestamp(source.stat().st_mtime, HK).strftime('%d %b %Y %H:%M HKT')
        print('Using freshly browser-saved etnet HTML for ' + month
              + ' (age %.1f hours). Normal source validation still applies.' % (age_seconds/3600))
        return page

    def _recent_verified_etnet_cache(self, url):
        """Same-day, time-limited verified HTTP snapshot; reject mismatches and tampering."""
        month = _etnet_month(url)
        if not month or not ETNET_CACHE_ENABLED:
            return None
        html_path, metadata_path = _verified_etnet_cache_paths(month)
        if not html_path.is_file() or not metadata_path.is_file():
            return None
        try:
            metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
            if metadata.get('url') != url or metadata.get('report_day') != datetime.now(HK).date().isoformat():
                return None
            fetched = datetime.fromisoformat(metadata['fetched_at'])
            now = datetime.now(HK)
            age = (now - fetched).total_seconds()
            if fetched.tzinfo is None or not 0 <= age <= ETNET_CACHE_MAX_MINUTES * 60:
                return None
            raw = html_path.read_bytes()
            if len(raw) != metadata.get('bytes') or hashlib.sha256(raw).hexdigest() != metadata.get('sha256'):
                return None
            page = raw.decode('utf-8', errors='strict')
            # An HTTP cache hit is never proof by itself. Recheck the source table.
            parse_lockups(page, month)
            self.cache[url] = page
            stamp = fetched.astimezone(HK).strftime('%d %b %Y %H:%M HKT')
            self.cached_sources[month] = stamp
            print('  VERIFIED CACHE etnet ' + month + ' (' + stamp + ', age %.0f min)' % (age / 60), flush=True)
            return page
        except (OSError, ValueError, KeyError, TypeError, UnicodeError, SourceError) as exc:
            print('  NOTE etnet ' + month + ' cache unusable (' + str(exc)[:100] + '); fetching live...', flush=True)
            return None

    def _save_verified_etnet_cache(self, url, page):
        month = _etnet_month(url)
        if not month or not ETNET_CACHE_ENABLED:
            return
        # Save only sources that pass the same visible-vs-embedded check used for the draft.
        parse_lockups(page, month)
        html_path, metadata_path = _verified_etnet_cache_paths(month)
        try:
            html_path.parent.mkdir(parents=True, exist_ok=True)
            raw = page.encode('utf-8')
            stamp = datetime.now(HK)
            metadata = {'url': url, 'report_day': stamp.date().isoformat(),
                        'fetched_at': stamp.isoformat(), 'sha256': hashlib.sha256(raw).hexdigest(),
                        'bytes': len(raw), 'source': 'complete validated etnet HTML'}
            atomic_write(html_path, raw)
            atomic_write(metadata_path, json.dumps(metadata, indent=2).encode('utf-8'))
        except OSError as exc:
            # Failure to cache must never destroy already downloaded, validated data.
            print('  NOTE Could not save etnet cache: ' + str(exc)[:120], flush=True)

    def text(self, url):
        if url in self.cache:
            return self.cache[url]
        # Prefer a recent, validated browser-saved page immediately rather than
        # first waiting through two timeouts for a known troublesome etnet route.
        try:
            manual = self._recent_manual_etnet(url)
        except SourceNetworkError:
            # Stale browser HTML must never prevent a fresh network attempt.
            # It is not used as a substitute for current data.
            manual = None
        if manual is not None:
            return manual
        verified_cache = self._recent_verified_etnet_cache(url)
        if verified_cache is not None:
            return verified_cache

        short_source = urlparse(url)
        source_label = short_source.hostname + short_source.path.rsplit('/', 1)[-1]
        if short_source.hostname == 'www.etnet.com.hk':
            source_label = 'etnet ' + parse_qs(short_source.query).get('month', [''])[0]
        timeout = (ETNET_TIMEOUT_SECONDS if short_source.hostname == 'www.etnet.com.hk'
                   else NETWORK_TIMEOUT_SECONDS)
        retry_limit = (ETNET_RETRIES if short_source.hostname == 'www.etnet.com.hk'
                       else NETWORK_RETRIES)
        started_at = time.monotonic()
        if SHOW_DOWNLOAD_TIMINGS:
            print('  GET ' + source_label + ' ...', flush=True)
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; HK-Equities-Daily/3.1)',
            'Accept-Language': 'zh-HK,zh;q=0.9,en;q=0.8',
            'Accept': 'text/html,application/json,*/*',
            'Accept-Encoding': 'gzip, deflate' if USE_GZIP_COMPRESSION else 'identity',
            'Connection': 'close',
            'Cache-Control': 'no-cache',
        })
        direct_failure = None
        use_windows = self.windows_proxy_worked and NETWORK_MODE != 'urllib'
        if not use_windows:
            for attempt in range(1, retry_limit + 1):
                try:
                    with self.opener.open(req, timeout=timeout) as response:
                        raw = _read_complete_response(response, url)
                        body = _decode_http_encoding(raw, response.headers.get('Content-Encoding'), url)
                        encoding = response.headers.get_content_charset()
                    data = _decode_source(url, body, encoding)
                    self._save_verified_etnet_cache(url, data)
                    self.cache[url] = data
                    if SHOW_DOWNLOAD_TIMINGS:
                        print('  OK  ' + source_label + ' (%.1fs, %.0f KB)' %
                              (time.monotonic()-started_at, len(raw)/1024), flush=True)
                    return data
                except urllib.error.HTTPError as exc:
                    if exc.code in (404, 410):
                        raise PageMissing('Not published: ' + url) from exc
                    if exc.code not in (407, 429, 500, 502, 503, 504):
                        raise SourceError('HTTP ' + str(exc.code) + ': ' + url) from exc
                    direct_failure = 'HTTP ' + str(exc.code)
                except http.client.IncompleteRead as exc:
                    # Discard the partial bytes. Retrying must start a new GET.
                    direct_failure = ('Incomplete HTTP transfer ('
                                      + str(len(exc.partial)) + ' bytes in final interrupted read)')
                except http.client.HTTPException as exc:
                    direct_failure = 'Broken HTTP response: ' + str(exc)
                except (urllib.error.URLError, TimeoutError, OSError) as exc:
                    direct_failure = str(exc)
                    if 'Tunnel connection failed: 503' in direct_failure:
                        direct_failure = 'Corporate HTTPS proxy returned 503 while opening the tunnel'
                except (UnicodeError, LookupError) as exc:
                    raise SourceError('Unexpected source encoding: ' + url) from exc
                if attempt < retry_limit:
                    print('  RETRY ' + source_label + ' after ' + str(direct_failure)[:100]
                          + ' (' + str(attempt + 1) + '/' + str(retry_limit) + ')', flush=True)
                    time.sleep(NETWORK_RETRY_PAUSE_SECONDS * attempt)

        if SHOW_DOWNLOAD_TIMINGS:
            print('  FAILED ' + source_label + ' after %.1fs' %
                  (time.monotonic() - started_at), flush=True)

        if NETWORK_MODE == 'urllib' or os.name != 'nt':
            raise SourceNetworkError(
                'Unable to download ' + url + '\n'
                + 'Python/company proxy: ' + str(direct_failure) + '\n'
                + 'No data were substituted or assumed missing.'
            )

        # Optional legacy fallback; not recommended in corporate PowerShell
        # Constrained Language mode. No bypass of corporate policy is attempted.
        try:
            if not self.windows_proxy_worked:
                print('Python could not reach this source. Trying Windows proxy fallback...')
            raw = _download_via_windows_proxy(url, WINDOWS_PROXY_TIMEOUT_SECONDS)
            data = _decode_source(url, raw)
            self.cache[url] = data
            self.windows_proxy_worked = True
            return data
        except PageMissing:
            raise
        except SourceError as exc:
            raise SourceNetworkError(
                'Unable to download ' + url + '\n'
                + 'Python/company proxy: ' + str(direct_failure) + '\n'
                + 'Windows fallback: ' + str(exc)
            ) from exc
        except (UnicodeError, LookupError) as exc:
            raise SourceError('Unexpected source encoding: ' + url) from exc


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


class BloombergError(SourceError):
    """Bloomberg data could not be retrieved or validated."""


def bloomberg_security(code):
    return str(int(stock_code(code))) + ' HK Equity'


def unlock_amount_hkd(raw):
    """Parse the source amount without rounding or assuming a missing currency.

    etnet commonly uses HKD/HK$ plus 萬 or 億. A foreign-currency or unknown
    format is flagged, never silently treated as HKD or zero.
    """
    value = re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(raw)))
    match = re.fullmatch(
        r'(?:HKD|HK\$|港元)(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)'
        r'(百萬|百万|億|亿|萬|万|千)?', value, re.I)
    if not match:
        raise ValueError('Unlock amount is missing, non-HKD, or has an unsupported format: ' + str(raw))
    scale = {'': 1, '千': 1000, '萬': 10000, '万': 10000,
             '百萬': 1000000, '百万': 1000000, '億': 100000000, '亿': 100000000}
    return Decimal(match[1].replace(',', '')) * scale[match[2] or '']


def finite_decimal(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def bloomberg_request_specs():
    end_date = str(BLOOMBERG_TURNOVER_END_DATE).strip()
    turnover_overrides = {'MARKET_DATA_OVERRIDE': 'TURNOVER', 'CALC_INTERVAL': '20D', 'CRNCY': 'HKD'}
    if end_date:
        if not re.fullmatch(r'\d{8}', end_date):
            raise BloombergError('BLOOMBERG_TURNOVER_END_DATE must be blank or YYYYMMDD.')
        try:
            parsed = datetime.strptime(end_date, '%Y%m%d').date()
        except ValueError as exc:
            raise BloombergError('Invalid Bloomberg turnover end date: ' + end_date) from exc
        if parsed > datetime.now(HK).date():
            raise BloombergError('Bloomberg turnover end date cannot be in the future.')
        turnover_overrides['END_DATE_OVERRIDE'] = end_date
    # Separate requests preserve the overrides of each supplied Excel formula.
    # Keep the supplied base BDP formula: market cap is in HKD millions.
    # Convert it explicitly in Python; do not assume an Excel scaling option
    # is supported as a ReferenceDataRequest field override.
    return [
        ('CRNCY_ADJ_MKT_CAP', {'EQY_FUND_CRNCY': 'HKD'}),
        ('EQY_FREE_FLOAT_PCT', {}),
        ('INTERVAL_AVG', turnover_overrides),
    ]


class BloombergClient:
    """Synchronous Desktop API requests with bounded waits and error auditing.

    API reference: https://bloomberg.github.io/blpapi-docs/python/3.26.9/
    Field names and override choices follow the supplied Excel formulas.
    """
    def __enter__(self):
        self.session = None
        try:
            import blpapi
        except (ImportError, OSError) as exc:
            raise BloombergError('blpapi is unavailable in this Python environment. '
                                 'Install Bloomberg\'s supported package and sign in to the desktop Terminal.') from exc
        self.api = blpapi
        try:
            options = blpapi.SessionOptions()
            options.setServerHost(BLOOMBERG_HOST)
            options.setServerPort(BLOOMBERG_PORT)
            options.setClientMode(blpapi.SessionOptions.DAPI)
            options.setConnectTimeout(BLOOMBERG_CONNECT_TIMEOUT_MS)
            options.setNumStartAttempts(1)
            options.setServiceCheckTimeout(BLOOMBERG_CONNECT_TIMEOUT_MS)
            options.setServiceDownloadTimeout(BLOOMBERG_CONNECT_TIMEOUT_MS)
            self.session = blpapi.Session(options)
            if not self.session.start():
                raise BloombergError('Cannot connect to Bloomberg Desktop API. Check that the Terminal is logged in.')
            if not self.session.openService('//blp/refdata'):
                raise BloombergError('Bloomberg //blp/refdata service is unavailable.')
            self.service = self.session.getService('//blp/refdata')
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self.session is not None:
            try:
                self.session.stop()
            except Exception as exc:
                LOG.warning('Bloomberg session cleanup failed: %s', exc)

    def reference(self, securities, field, overrides):
        request = self.service.createRequest('ReferenceDataRequest')
        for security in securities:
            request.getElement('securities').appendValue(security)
        request.getElement('fields').appendValue(field)
        for key, value in overrides.items():
            override = request.getElement('overrides').appendElement()
            override.setElement('fieldId', key)
            override.setElement('value', str(value))
        queue = self.api.EventQueue()
        correlation = self.session.sendRequest(request, eventQueue=queue)
        deadline = time.monotonic() + BLOOMBERG_REQUEST_TIMEOUT_SECONDS
        result, completed = {}, False
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise BloombergError(field + ': request timed out; partial results discarded.')
                event = queue.nextEvent(max(1, min(500, int(remaining * 1000))))
                event_type = event.eventType()
                for message in event:
                    if event_type == self.api.Event.REQUEST_STATUS:
                        raise BloombergError(field + ': ' + str(message)[:600])
                    if event_type not in (self.api.Event.PARTIAL_RESPONSE, self.api.Event.RESPONSE):
                        continue
                    if message.hasElement('responseError'):
                        raise BloombergError(field + ': ' + str(message.getElement('responseError'))[:600])
                    if not message.hasElement('securityData'):
                        raise BloombergError(field + ': response has no securityData.')
                    data = message.getElement('securityData')
                    for index in range(data.numValues()):
                        item = data.getValueAsElement(index)
                        security = item.getElementAsString('security')
                        # sequenceNumber identifies the requested security even if Bloomberg
                        # returns a canonical name different from the input ticker.
                        if item.hasElement('sequenceNumber'):
                            sequence = item.getElementAsInteger('sequenceNumber')
                            if not 0 <= sequence < len(securities):
                                raise BloombergError('Unexpected Bloomberg security sequence number.')
                            security = securities[sequence]
                        if security not in securities:
                            raise BloombergError('Unexpected Bloomberg security: ' + security)
                        if item.hasElement('securityError'):
                            result[security] = (None, str(item.getElement('securityError'))[:600])
                            continue
                        error = None
                        if item.hasElement('fieldExceptions'):
                            exceptions = item.getElement('fieldExceptions')
                            for j in range(exceptions.numValues()):
                                exception = exceptions.getValueAsElement(j)
                                if exception.getElementAsString('fieldId') == field:
                                    error = str(exception.getElement('errorInfo'))[:600]
                        number = None
                        if not error and item.hasElement('fieldData'):
                            fields = item.getElement('fieldData')
                            if fields.hasElement(field):
                                element = fields.getElement(field)
                                if not element.isNull() and element.numValues():
                                    number = finite_decimal(element.getValueAsString())
                        result[security] = (number, error or (None if number is not None else 'Missing or non-finite value'))
                if event_type == self.api.Event.RESPONSE:
                    completed = True
                    break
            return {security: result.get(security, (None, 'Security omitted from response'))
                    for security in securities}
        finally:
            if not completed:
                try:
                    self.session.cancel(correlation)
                except Exception as exc:
                    LOG.warning('Bloomberg request cleanup failed: %s', exc)


def fetch_bloomberg_metrics(codes):
    securities = sorted({bloomberg_security(code) for code in codes})
    metrics = {security: {'fields': {}, 'errors': {}} for security in securities}
    specs = bloomberg_request_specs()
    audit = {'enabled': BLOOMBERG_ENABLED, 'requested_securities': len(securities),
             'started_at': datetime.now(HK).isoformat(), 'currency': 'HKD',
             'monetary_units': 'normalized amounts in absolute HKD',
             'raw_field_units': {'CRNCY_ADJ_MKT_CAP': 'HKD millions',
                                 'EQY_FREE_FLOAT_PCT': 'percent', 'INTERVAL_AVG': 'absolute HKD'},
             'unit_basis': 'Units follow the supplied Excel field definitions; validate with Terminal FLDS.',
             'turnover_end_date': str(BLOOMBERG_TURNOVER_END_DATE).strip() or None,
             'requests': [{'field': field, 'overrides': overrides} for field, overrides in specs]}
    if securities:
        if BLOOMBERG_BATCH_SIZE < 1 or BLOOMBERG_REQUEST_TIMEOUT_SECONDS <= 0:
            raise BloombergError('Bloomberg batch size and request timeout must be positive.')
        try:
            if not BLOOMBERG_ENABLED:
                raise BloombergError('Bloomberg enrichment disabled in settings.')
            print('Fetching Bloomberg lock-up metrics for ' + str(len(securities)) + ' unique securities ...', flush=True)
            with BloombergClient() as client:
                for start in range(0, len(securities), BLOOMBERG_BATCH_SIZE):
                    batch = securities[start:start + BLOOMBERG_BATCH_SIZE]
                    for field, overrides in specs:
                        try:
                            values = client.reference(batch, field, overrides)
                        except Exception as exc:
                            values = {security: (None, str(exc)[:600]) for security in batch}
                        for security, (value, error) in values.items():
                            if error:
                                metrics[security]['errors'][field] = error
                            else:
                                # Strings retain decimal precision and serialize safely to JSON.
                                metrics[security]['fields'][field] = str(value)
        except Exception as exc:
            audit['error'] = str(exc)[:600]
            for entry in metrics.values():
                for field, _ in specs:
                    if field not in entry['fields']:
                        entry['errors'].setdefault(field, audit['error'])
    audit['completed_at'] = datetime.now(HK).isoformat()
    audit['securities'] = metrics
    return metrics, audit


def lockup_ratios(raw_amount, fields, errors=None):
    """Calculate each tranche independently, using unrounded absolute HKD."""
    errors = errors or {}
    issues = []
    try:
        amount = unlock_amount_hkd(raw_amount)
    except ValueError as exc:
        amount = None
        issues.append(str(exc))

    def value(field, valid, description):
        number = finite_decimal(fields.get(field))
        if field in errors or number is None or not valid(number):
            issues.append(description + ': ' + errors.get(field, 'missing or outside the allowed range'))
            return None
        return number

    cap_millions = value('CRNCY_ADJ_MKT_CAP', lambda n: n > 0, 'Market cap unavailable')
    cap = cap_millions * Decimal(1000000) if cap_millions is not None else None
    free_float = value('EQY_FREE_FLOAT_PCT', lambda n: 0 < n <= 100, 'Free-float percentage unavailable')
    turnover = value('INTERVAL_AVG', lambda n: n > 0, '20D average turnover unavailable')
    float_cap = cap * free_float / Decimal(100) if cap is not None and free_float is not None else None
    percentage = amount / float_cap * Decimal(100) if amount is not None and float_cap is not None else None
    multiple = amount / turnover if amount is not None and turnover is not None else None
    values = {'unlock_amount_hkd': amount, 'market_cap_hkd': cap, 'free_float_pct': free_float,
              'float_market_cap_hkd': float_cap, 'avg_turnover_20d_hkd': turnover,
              'unlock_to_float_market_cap_pct': percentage, 'unlock_to_20d_avg_turnover_x': multiple}
    return {key: str(number) if number is not None else None for key, number in values.items()}, issues


def enrich_lockup_rows(rows):
    metrics, audit = fetch_bloomberg_metrics(row['code'] for row in rows)
    missing = 0
    for row in rows:
        security = bloomberg_security(row['code'])
        entry = metrics[security]
        values, issues = lockup_ratios(row['amount'], entry['fields'], entry['errors'])
        row.update(values)
        row['bloomberg_security'] = security
        row['bloomberg_issues'] = issues
        row['source_issue'] = row['issue']
        if issues:
            missing += 1
            row['issue'] = '; '.join(filter(None, [row['issue'], 'Bloomberg ratios: ' + '; '.join(issues)]))
    audit['tranches_with_unavailable_ratios'] = missing
    audit['status'] = 'no_lockups' if not rows else ('incomplete' if missing else 'ok')
    if missing and BLOOMBERG_REQUIRED:
        raise BloombergError(f'Bloomberg ratios unavailable for {missing} lock-up tranches; draft withheld. '
                             + next(row['issue'] for row in rows if row['bloomberg_issues']))
    return audit


def format_bloomberg_metric(row, field, suffix='', divisor=1):
    number = finite_decimal(row.get(field))
    return 'N/A' if number is None else f'{number / Decimal(divisor):,.2f}{suffix}'


def lockup_review_summary(row):
    """Keep the email actionable; raw API error messages stay in the JSON audit."""
    reasons = [row.get('source_issue', row.get('issue', ''))]
    if row.get('bloomberg_issues'):
        if row.get('unlock_amount_hkd') is None:
            reasons.append('Unlock amount cannot be read as HKD')
        if row.get('float_market_cap_hkd') is None:
            reasons.append('Free-float market cap unavailable')
        if row.get('avg_turnover_20d_hkd') is None:
            reasons.append('20D average turnover unavailable')
    return '; '.join(dict.fromkeys(reason for reason in reasons if reason))


SECTION_NAMES = {'ipo': 'IPO pipeline', 'phip': 'PHIP updates',
                 'short': 'Short-selling eligibility', 'lockup': 'Lock-up calendar'}


def section_snapshot(report):
    """Compare content, independent of ordering, refresh times and date labels.

    Rolling-window entries and exits count as changes. Market ratios compare at
    the precision displayed in the email. API diagnostics remain in the audit.
    """
    def records(rows, keys, fields):
        result = {}
        for row in rows:
            key = json.dumps([row[k] for k in keys], ensure_ascii=False)
            if key in result:
                raise SourceError('Duplicate record identity in section comparison: ' + key)
            result[key] = {field: sorted(row[field]) if isinstance(row[field], list) else row[field]
                           for field in fields}
        return result

    lockups = []
    for row in report['lockups']:
        item = {field: row[field] for field in ('code', 'expiry', 'holder_type', 'name', 'holders',
                'amount', 'percent', 'price', 'cumulative_change', 'url', 'quote_url', 'tab')}
        for field in ('float_market_cap_hkd', 'avg_turnover_20d_hkd'):
            item[field] = format_bloomberg_metric(row, field, divisor=1000000)
        for field in ('unlock_to_float_market_cap_pct', 'unlock_to_20d_avg_turnover_x'):
            item[field] = format_bloomberg_metric(row, field)
        item['eligibility'] = eligibility(row, report)[0]
        item['review'] = lockup_review_summary(row)
        lockups.append(item)
    return {'version': 1, 'sections': {
        'ipo': {'records': records(report['ipos'], ('code',),
                ('code', 'name', 'announcements', 'prospectuses', 'allotment_results')), 'context': {}},
        'phip': {'records': records(report['phip'], ('key',),
                ('company', 'board', 'status', 'posted', 'title', 'links')), 'context': {}},
        'short': {'records': {code: {'name': name} for code, name in report['short']['securities'].items()},
                  'context': {'events': records(report['short_changes'], ('effective', 'code', 'change'),
                                              ('effective', 'code', 'change', 'name', 'url'))}},
        'lockup': {'records': records(lockups, ('code', 'expiry', 'holder_type'),
                                     tuple(lockups[0]) if lockups else ()),
                   'context': {'turnover_end_date': report.get('bloomberg', {}).get('turnover_end_date')}}}}


def annotate_section_changes(report, previous):
    current = section_snapshot(report)
    compatible = previous is not None and previous['snapshot'].get('version') == current['version']
    report['comparison'] = {'basis': 'previous successfully saved draft',
                            'previous_generated_at': previous['generated_at'] if compatible else None,
                            'previous_day': previous['day'] if compatible else None}
    changes = {}
    for key, now in current['sections'].items():
        if not compatible or key not in previous['snapshot']['sections']:
            changes[key] = {'status': 'baseline', 'added': 0, 'removed': 0, 'updated': 0,
                            'context_changed': False, 'summary': 'Comparison starts with the next saved draft.'}
            continue
        before = previous['snapshot']['sections'][key]
        old_keys, new_keys = set(before['records']), set(now['records'])
        added, removed = new_keys - old_keys, old_keys - new_keys
        updated = {item for item in old_keys & new_keys if before['records'][item] != now['records'][item]}
        context_changed = before['context'] != now['context']
        parts = [str(len(items)) + ' ' + label for items, label in
                 ((added, 'added'), (removed, 'removed'), (updated, 'updated')) if items]
        if context_changed:
            parts.append('5-day event list updated' if key == 'short' else 'Turnover end date changed')
        changes[key] = {'status': 'changed' if parts else 'unchanged', 'added': len(added),
                        'removed': len(removed), 'updated': len(updated), 'context_changed': context_changed,
                        'summary': ' · '.join(parts) if parts else 'No content changes.'}
    report['section_changes'] = changes
    # PHIP NEW now means added since the same comparison draft as the headers.
    old_phips = previous['snapshot']['sections'].get('phip', {}).get('records', {}) if compatible else None
    for row in report['phip']:
        row['new'] = old_phips is not None and json.dumps([row['key']], ensure_ascii=False) not in old_phips
    return current


class State:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS runs (
            day TEXT NOT NULL, mode TEXT NOT NULL, short_json TEXT NOT NULL,
            phip_json TEXT NOT NULL, created_at TEXT NOT NULL, receipt_json TEXT,
            PRIMARY KEY(day, mode))""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS section_snapshots (
            day TEXT NOT NULL, mode TEXT NOT NULL, generated_at TEXT NOT NULL,
            snapshot_json TEXT NOT NULL, PRIMARY KEY(day, mode))""")
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

    def previous_sections(self, day: date, mode: str):
        row = self.db.execute('SELECT day, generated_at, snapshot_json FROM section_snapshots '
                              'WHERE day <= ? AND mode = ? ORDER BY day DESC LIMIT 1',
                              (day.isoformat(), mode)).fetchone()
        return {'day': row[0], 'generated_at': row[1], 'snapshot': json.loads(row[2])} if row else None

    def save(self, day: date, mode: str, short: ShortList, phip: list[PHIP], receipt: dict | None,
             sections=None, generated_at=None) -> None:
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?, ?)",
                            (day.isoformat(), mode, json.dumps(asdict(short), ensure_ascii=False),
                             json.dumps([p.key for p in phip]), datetime.now(HK).isoformat(),
                             json.dumps(receipt) if receipt else None))
            if sections is not None:
                self.db.execute('INSERT OR REPLACE INTO section_snapshots VALUES (?, ?, ?, ?)',
                                (day.isoformat(), mode, generated_at or datetime.now(HK).isoformat(),
                                 json.dumps(sections, ensure_ascii=False, sort_keys=True)))

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
    """Readable clickable hyperlinks with explicit Outlook-friendly font size."""
    label_html = e(label)
    if not url:
        return label_html
    return (f'<a href="{e(url)}" style="color:#0759A4;'
            'font-family:Arial,Microsoft JhengHei,sans-serif;'
            'font-size:16px;font-weight:700;text-decoration:underline;">'
            f'<u style="color:#0759A4;">{label_html}</u></a>')

def nice_date(value, year=False):
    return parse_date(value).strftime("%d %b %Y" if year else "%d %b")


def badge(label, color="neutral"):
    """High-contrast, large YES / NO / NEW / REVIEW indicator for Outlook."""
    colors = {
        "neutral": ("#e8edf2", "#213245", "#b6c1cc"),
        "green": ("#087544", "#ffffff", "#075c36"),
        "red": ("#a82032", "#ffffff", "#871929"),
        "blue": ("#1257b5", "#ffffff", "#0c468f"),
        "amber": ("#f4ce65", "#332700", "#a67b17"),
    }
    background, foreground, border = colors[color]
    return (f'<span style="display:inline-block;padding:6px 10px;'
            f'font-family:Arial,sans-serif;font-size:16px;line-height:22px;'
            f'font-weight:700;text-align:center;'
            f'background-color:{background};color:{foreground};border:1px solid {border};'
            f'white-space:nowrap;"><strong>{e(label)}</strong></span>')

def table(headers, rows, highlighted=None, widths=None):
    """Compact Word/Outlook-safe tables; optional explicit widths for lock-ups."""
    if not rows:
        return ('<p style="font-family:Arial,Microsoft JhengHei,sans-serif;'
                'font-size:16px;color:#495462;line-height:1.5;">No updates in this period.</p>')
    if widths is not None and (len(widths) != len(headers) or sum(widths) != 100):
        raise ValueError('Column widths must match headers and sum to 100%.')
    head = []
    for i, h in enumerate(headers):
        right = h.startswith('#')
        width_attr = f' width="{widths[i]}%"' if widths else ''
        width_style = f'width:{widths[i]}%;' if widths else ''
        head.append(
            f'<th scope="col"{width_attr} style="{width_style}text-align:{"right" if right else "left"};'
            'padding:12px 9px;background-color:#eaf0f6;border-bottom:2px solid #9eafc0;'
            'font-family:Arial,Microsoft JhengHei,sans-serif;'
            'font-size:14px;font-weight:700;color:#26394c;line-height:1.4;'
            f'white-space:normal;vertical-align:bottom;">{e(h.lstrip("#"))}</th>'
        )
    body = []
    for index, row in enumerate(rows):
        if len(row) != len(headers):
            raise ValueError('Report table column mismatch.')
        background = '#fff6e5' if highlighted and index in highlighted else ('#f7f9fc' if index % 2 else '#ffffff')
        cells = []
        for number, value in enumerate(row):
            align = 'right' if headers[number].startswith('#') else 'left'
            width_attr = f' width="{widths[number]}%"' if widths else ''
            width_style = f'width:{widths[number]}%;' if widths else ''
            cells.append(
                f'<td{width_attr} style="{width_style}text-align:{align};padding:13px 9px;'
                f'vertical-align:top;border-bottom:1px solid #d8e0e8;background-color:{background};'
                'font-family:Arial,Microsoft JhengHei,sans-serif;font-size:16px;'
                f'color:#263341;line-height:1.45;overflow-wrap:break-word;">{value}</td>'
            )
        body.append('<tr>' + ''.join(cells) + '</tr>')
    fixed = 'table-layout:fixed;' if widths else ''
    return ('<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
            f'style="width:100%;border-collapse:collapse;{fixed}"><thead><tr>'
            + ''.join(head) + '</tr></thead><tbody>' + ''.join(body) + '</tbody></table>')

def section_status(change):
    return {'changed': 'CHANGED', 'unchanged': 'NO CHANGE', 'baseline': 'BASELINE'}.get(
        (change or {}).get('status'), 'BASELINE')


def section(number, title, detail, change=None, review_count=0):
    """Large numbered headings, implemented as a table for Classic Outlook."""
    change = change or {'status': 'baseline', 'summary': 'Comparison starts with the next saved draft.'}
    changed = change['status'] == 'changed'
    status = ('<span style="display:inline-block;margin-left:12px;padding:4px 8px;'
              'font-family:Arial,sans-serif;font-size:12px;line-height:18px;font-weight:700;'
              f'background:{"#e2efff" if changed else "#eef1f4"};'
              f'color:{"#0759A4" if changed else "#526474"};">{section_status(change)}</span>')
    if review_count:
        status += ('<span style="display:inline-block;margin-left:7px;padding:4px 8px;font-size:12px;'
                   f'line-height:18px;font-weight:700;background:#fff1ca;color:#795b00;">REVIEW {review_count}</span>')
    summary = ('<div style="font-size:14px;color:#0759A4;margin-top:5px;">'
               + e(change['summary']) + '</div>') if changed else ''
    return (
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
        'style="width:100%;border-collapse:collapse;margin-top:30px;margin-bottom:13px;'
        'border-top:2px solid #b41529;">'
        '<tr><td width="67" valign="top" style="width:67px;padding:16px 10px 8px 0;vertical-align:top;">'
        '<table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr>'
        '<td bgcolor="#b41529" style="background-color:#b41529;color:white;'
        'font-family:Arial,sans-serif;text-align:center;padding:6px 11px;'
        f'font-size:22px;font-weight:700;line-height:29px;">{number:02d}</td>'
        '</tr></table></td>'
        '<td valign="top" style="padding:14px 0 10px;vertical-align:top;'
        'font-family:Calibri,Arial,Microsoft JhengHei,sans-serif;">'
        f'<div style="font-size:22px;font-weight:700;color:#172b3f;line-height:1.25;">{e(title)}{status}</div>'
        + summary +
        f'<div style="font-size:14px;color:#48596a;line-height:1.55;margin-top:5px;">{detail}</div>'
        '</td></tr></table>'
    )


def section_text_heading(report, key, title):
    change = report.get('section_changes', {}).get(key, {})
    return title + ' [' + section_status(change) + ']' + (
        ' — ' + change['summary'] if change.get('status') == 'changed' else '')


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
                     '<div style="font-size:30px;line-height:1.25;font-weight:700;letter-spacing:-.2px">IPO, PHIP &amp; Lock-up Update</div>'
                     f'<div style="font-size:15px;color:#e2e7ed;margin-top:12px">{day:%A, %d %B %Y} &nbsp; · &nbsp; Updated {datetime.fromisoformat(report["generated_at"]):%H:%M} HKT</div></td></tr></table>')
    stats = [(str(len(report['ipos'])), 'MAIN BOARD IPOs'), (str(len(report['phip'])), 'PHIPs · 7 DAYS'),
             (f'+{addition_count} / −{removal_count}', 'SHORT-LIST CHANGES · 5 DAYS'),
             (str(len(visible_lockups)), 'LOCK-UP TRANCHES / %d REVIEW' % sum(bool(r['issue']) for r in visible_lockups))]
    fragments.append('<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-bottom:1px solid #d9dde2"><tr>' +
                     ''.join(f'<td width="25%" style="padding:18px 18px 17px;border-right:1px solid #eceef1"><div style="font-size:28px;color:#202a36;font-weight:700;line-height:1.2">{e(value)}</div><div style="font-size:13px;color:#46596c;font-weight:700;letter-spacing:.1px;margin-top:7px">{label}</div></td>' for value, label in stats) + '</tr></table>')
    fragments.append('<div style="padding:0 28px 25px">')
    section_changes = report.get('section_changes', {})
    previous_time = report.get('comparison', {}).get('previous_generated_at')
    changed_names = [SECTION_NAMES[key] for key, change in section_changes.items() if change['status'] == 'changed']
    if previous_time:
        comparison_line = ('Compared with the saved draft from '
                           + datetime.fromisoformat(previous_time).strftime('%d %b %Y, %H:%M HKT') + '.')
        change_line = 'Changed sections: ' + ', '.join(changed_names) + '.' if changed_names else 'No section content changes.'
    else:
        comparison_line = 'Baseline saved on this run. Change flags begin with the next successfully saved draft.'
        change_line = 'Section comparison baseline'
    fragments.append('<p style="font-size:16px;line-height:1.5;color:#172b3f;margin:22px 0 5px;">'
                     + '<strong>' + e(change_line) + '</strong></p>'
                     + '<p style="font-size:13px;line-height:1.5;color:#526474;margin:0 0 10px;">'
                     + e(comparison_line) + ' Refresh times alone do not count. Added and removed refer to entries in the displayed lists.</p>')
    text.extend([change_line, comparison_line, ''])
    fragments.append(section(1, 'IPO pipeline', link(MAIN_BOARD_URL, 'Main Board'), section_changes.get('ipo')))
    ipo_rows = []
    text.append(section_text_heading(report, 'ipo', '1. IPO PIPELINE — MAIN BOARD'))
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
    fragments.append(section(2, 'PHIP updates', e(phip_range) + ' &nbsp; · &nbsp; ' + link(PHIP_PAGE_URL, 'HKEX filing index'), section_changes.get('phip')))
    text.extend(['', section_text_heading(report, 'phip', '2. PHIP UPDATES'), phip_range])
    phip_rows, highlights = [], set()
    for row in report['phip']:
        new = badge('NEW', 'blue') + ' ' if row['new'] else ''
        if row['new']: highlights.add(len(phip_rows))
        # Each link comes from the verified HKEX filing feed; never fabricate missing URLs.
        filing_urls = row['links']
        filing_title = link(filing_urls[0], row['title']) if filing_urls else e(row['title'])
        issuer = link(filing_urls[0], row['company']) if filing_urls else e(row['company'])
        filing_actions = (' &nbsp; | &nbsp; '.join(
            link(url, 'Open filing' + (f' {i}' if len(filing_urls) > 1 else ''))
            for i, url in enumerate(filing_urls, 1)
        ) if filing_urls else '<span style="color:#815100;">No document URL in HKEX feed</span>')
        phip_rows.append([e(nice_date(row['posted'])), new + issuer, e(row['board']),
                          filing_title + '<div style="margin-top:8px;font-size:14px;">' + filing_actions + '</div>'])
        text.append(f'{row["posted"]} | {row["company"]} | {row["board"]} | {row["title"]}' + (' | NEW' if row['new'] else ''))
        text.extend(row['links'])
    fragments.append(table(['POSTED', 'ISSUER', 'BOARD', 'FILING'], phip_rows, highlights))
    if not phip_rows: text.append('No filings in the seven-day window.')
    comparison = f'{nice_date(window["start"], True)}–{nice_date(window["end"], True)} · {window["label"]}'
    detail = 'Latest effective list: ' + link(short['url'], nice_date(short['effective'], True))
    fragments.append(section(3, 'Short-selling eligibility', detail, section_changes.get('short')))
    fragments.append(f'<p style="font-size:14px;color:#48596a;margin:0 0 12px">{e(comparison)} &nbsp; · &nbsp; {len(short["securities"]):,} eligible securities.</p>')
    text.extend(['', section_text_heading(report, 'short', '3. SHORT-SELLING ELIGIBILITY'), comparison, 'Latest effective list: ' + short['effective']])
    changes = []
    for event in events:
        color = 'blue' if event['change'] == 'ADDED' else 'red'
        changes.append([link(event['url'], nice_date(event['effective'], True)), badge(event['change'], color),
                        '<strong>' + e(event['code']) + '</strong>', e(event['name'])])
        text.append(f'{event["effective"]} | {event["change"]} | {event["code"]} | {event["name"]}')
    if changes:
        fragments.append(table(['EFFECTIVE DATE', 'CHANGE', 'CODE', 'HKEX SHORT NAME'], changes))
        if not removal_count: fragments.append('<p style="font-size:14px;color:#48596a;margin:8px 0 0">Removals: none.</p>')
    else:
        fragments.append('<p style="font-size:15px">No additions or removals in this period.</p>')
        text.append('No additions or removals in this period.')
    expiry_scope = 'Includes earlier expiries this month' if report.get('include_expired') else 'Upcoming expiries only'
    fragments.append(section(4, 'Lock-up calendar', f'{nice_date(report["day"])} through {datetime.strptime(report["months"][-1], "%Y%m"):%B %Y} &nbsp; · &nbsp; {expiry_scope}',
                             section_changes.get('lockup'), sum(bool(r['issue']) for r in visible_lockups)))
    if report.get('manual_sources'):
        manual_note = '; '.join(month + ': ' + when for month, when in sorted(report['manual_sources'].items()))
        fragments.append('<p style="font-size:14px;color:#805c00;background:#fff8e8;padding:10px 12px">'
                         '<strong>SOURCE REVIEW:</strong> etnet lock-up data include a browser-saved '
                         'page (' + e(manual_note) + '). Verify the source timestamps before distribution.</p>')
        text.extend(['SOURCE REVIEW: etnet browser-saved HTML (' + manual_note
                     + '). Verify source timestamps before distribution.'])
    if report.get('cached_sources'):
        cache_note = '; '.join(month + ': ' + when for month, when in sorted(report['cached_sources'].items()))
        fragments.append('<p style="font-size:14px;color:#805c00;background:#fff8e8;padding:10px 12px">'
                         '<strong>SOURCE REVIEW:</strong> Reused verified etnet HTML fetched earlier today ('
                         + e(cache_note) + '). Check its quote timestamps before distribution.</p>')
        text.append('SOURCE REVIEW: reused verified same-day etnet HTML (' + cache_note + '). Check quote timestamps.')
    fragments.append('<p style="font-family:Arial,Microsoft JhengHei,sans-serif;font-size:15px;line-height:2.5;color:#364b60;margin:0 0 16px">'
                     + badge('YES', 'green') + ' Can short &nbsp; &nbsp; '
                     + badge('NEW', 'blue') + ' Newly added to short-selling list &nbsp; &nbsp; '
                     + badge('NO', 'red') + ' Not shortable</p>')
    text.extend(['', section_text_heading(report, 'lockup', '4. LOCK-UP CALENDAR'), 'YES = shortable; NEW = added within the 5-day short-list window; NO = not shortable.'])
    bloomberg = report.get('bloomberg', {})
    ratio_note = ('Unlock / float cap (%) = unlock value ÷ free-float market cap × 100. '
                  'Unlock / 20D turnover (x) = unlock value ÷ Bloomberg 20D average turnover. '
                  'HKDm means HKD millions. ')
    timing_note = ('Bloomberg market cap and free float are current snapshots; '
                   'etnet unlock values use the quote times below. ')
    if bloomberg.get('turnover_end_date'):
        timing_note += ('The turnover interval ends on ' + bloomberg['turnover_end_date']
                       + '; this does not make the other inputs historical. ')
    else:
        timing_note += 'Turnover uses Bloomberg\'s latest 20D interval. '
    if bloomberg.get('completed_at'):
        timing_note += ('Bloomberg checked '
                       + datetime.fromisoformat(bloomberg['completed_at']).strftime('%d %b %Y %H:%M HKT') + '. ')
    if bloomberg.get('tranches_with_unavailable_ratios'):
        count = bloomberg['tranches_with_unavailable_ratios']
        ratio_note += str(count) + (' tranche needs' if count == 1 else ' tranches need') + ' review; unavailable ratios show N/A.'
    fragments.append('<p style="font-size:14px;line-height:1.6;color:#48596a;margin:0 0 16px">'
                     + e(ratio_note) + '</p>')
    text.append(ratio_note)
    last_added = {}
    for event in events:
        if event['change'] == 'ADDED':
            last_added[event['code']] = max(event['effective'], last_added.get(event['code'], ''))
    for month in report['months']:
        monthly = [r for r in visible_lockups if r['expiry'].replace('-', '').startswith(month)]
        label = datetime.strptime(month, '%Y%m').strftime('%B %Y').upper()
        month_url = LOCKUP_URL.format(month=month)
        fragments.append('<div style="margin:24px 0 10px;font-family:Arial,Microsoft JhengHei,sans-serif;'
                         'font-size:18px;font-weight:700;color:#25394b;">'
                         + e(label) + ' <span style="font-size:15px;font-weight:400;color:#526474;">'
                         + f' / {len(monthly)} tranches &nbsp; · &nbsp; ' + link(month_url, 'View etnet source')
                         + '</span></div>')
        rows, highlights = [], set()
        for row in monthly:
            days = (parse_date(row['expiry']) - day).days
            tag, color = eligibility(row, report)
            if tag == 'NEW' or row['issue']:
                highlights.add(len(rows))
            relative_date = 'Today' if days == 0 else (f'In {days} days' if days > 0 else f'{-days} days ago')
            date_cell = ('<strong style="font-size:16px;color:#172b3f;white-space:nowrap">'
                         + e(row['expiry'].replace('-', '/')) + '</strong>'
                         + '<div style="font-size:14px;color:#536578;margin-top:6px;">'
                         + e(relative_date) + '</div>')
            holder_label = '基石投資者總數' if row['tab'] == 'cornerstone' else '大股東總數'
            security = ('<strong style="font-size:16px;">'
                        + link(row['url'], row['code'] + ' ' + row['name']) + '</strong>'
                        + '<div style="font-size:14px;color:#4c5c6f;margin-top:7px;">'
                        + e(holder_label) + ': <strong>' + e(row['holders']) + '</strong></div>')
            unlock_display = ('HKDm ' + format_bloomberg_metric(row, 'unlock_amount_hkd', divisor=1000000)
                              if row.get('unlock_amount_hkd') is not None else row['amount'])
            unlock = ('<strong style="font-size:16px;color:#1f2e3f;">' + e(unlock_display) + '</strong>'
                      + '<div style="font-size:14px;color:#4c5c6f;margin-top:6px;">'
                      + '佔已發行股數: <strong>' + e(row['percent']) + '</strong></div>')
            float_ratio = format_bloomberg_metric(row, 'unlock_to_float_market_cap_pct', '%')
            turnover_ratio = format_bloomberg_metric(row, 'unlock_to_20d_avg_turnover_x', 'x')
            ratios = ('<div style="font-size:13px;color:#4c5c6f;">Unlock / float cap</div>'
                      + '<strong style="font-size:16px;color:#1f2e3f;">' + e(float_ratio) + '</strong>'
                      + '<div style="font-size:12px;color:#526474;">Float cap HKDm: '
                      + e(format_bloomberg_metric(row, 'float_market_cap_hkd', divisor=1000000)) + '</div>'
                      + '<div style="font-size:13px;color:#4c5c6f;margin-top:9px;">Unlock / 20D turnover</div>'
                      + '<strong style="font-size:16px;color:#1f2e3f;">' + e(turnover_ratio) + '</strong>'
                      + '<div style="font-size:12px;color:#526474;">20D avg HKDm: '
                      + e(format_bloomberg_metric(row, 'avg_turnover_20d_hkd', divisor=1000000)) + '</div>')
            change_parts = row['cumulative_change'].split(' ', 1)
            change_color = '#b11d2b' if row['cumulative_change'].startswith('-') else '#087544'
            change_value = ('<strong style="font-size:16px;color:' + change_color + ';">'
                            + '<br>'.join(e(part) for part in change_parts) + '</strong>')
            short_cell = badge(tag, color)
            if tag == 'NEW':
                short_cell += ('<div style="font-size:14px;line-height:1.5;color:#0759A4;margin-top:8px;">'
                               + 'Since ' + e(nice_date(last_added[row['code']])) + '</div>')
            if row['issue']:
                short_cell += '<div style="margin-top:8px;">' + badge('REVIEW', 'amber') + '</div>'
            rows.append([date_cell, security, unlock, ratios, change_value, short_cell])
            text.append(f'{row["expiry"]} | {row["code"]} {row["name"]} | {holder_label} {row["holders"]} | 解禁總金額 {row["amount"]} | 佔已發行股數 {row["percent"]} | 累積升跌 {row["cumulative_change"]} | Shortable: {tag}')
            text.append('  解禁金額 / Float market cap: ' + float_ratio
                        + ' | 解禁金額 / 20D average turnover: ' + turnover_ratio)
            text.append('  Bloomberg ' + row.get('bloomberg_security', bloomberg_security(row['code']))
                        + ' | Float market cap HKDm: ' + format_bloomberg_metric(row, 'float_market_cap_hkd', divisor=1000000)
                        + ' | 20D average turnover HKDm: ' + format_bloomberg_metric(row, 'avg_turnover_20d_hkd', divisor=1000000))
            if row['issue']:
                text.append('  MANUAL REVIEW: ' + lockup_review_summary(row))
            text.append('Source: ' + row['url'])
        fragments.append(table(['解禁日', '股票 / 投資者', '解禁金額 / 持股比例', '解禁金額比率', '累積升跌', 'SHORTABLE'],
                               rows, highlights, widths=[14, 22, 21, 20, 10, 13]))
        for row in monthly:
            if row['issue']:
                label = row['code'] + ' / ' + row['expiry'] + ' / ' + row['holder_type']
                fragments.append('<p style="font-size:13px;line-height:1.5;color:#795b00;margin:10px 0;">'
                                 + '<strong>REVIEW ' + e(label) + ':</strong> ' + e(lockup_review_summary(row)) + '</p>')
    quote_asof = ', '.join(f"{month}: {when} HKT" for month, when in report.get('source_asof', {}).items() if when)
    note = 'Compilation for manual review before distribution. HKEX: listing, PHIP and short-selling; etnet: lock-up expiry, value and issued-share percentages; Bloomberg: market cap, free-float percentage and 20-day average turnover.'
    note += ' ' + timing_note
    if quote_asof:
        note += ' etnet indicated update times: ' + quote_asof + '.'
    fragments.append('<p style="font-size:13px;line-height:1.6;color:#536578;margin:18px 0 8px;border-top:1px solid #e0e4e8;padding-top:14px">' + e(note) + '</p>')
    text.extend(['', note])
    fragments.append('</div>')
    content = ''.join(fragments)
    document = '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + e(subject) + '</title></head><body style="margin:0;background:#edf0f3;color:#222b36;font-family:Arial,\'Microsoft JhengHei\',sans-serif;font-size:16px;line-height:1.5"><div id="email-content" style="max-width:900px;margin:18px auto;background:white;color:#222b36;font-family:Arial,\'Microsoft JhengHei\',sans-serif;font-size:16px;line-height:1.5">' + content + '</div></body></html>'
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
    toolbar = '<div style="max-width:900px;margin:20px auto 0;display:flex;gap:10px;align-items:center;font-family:Arial,sans-serif"><button onclick="copyEmail()" style="background:#263443;color:white;border:0;padding:11px 17px;cursor:pointer;font-weight:600">Copy formatted email</button><a href="' + e(draft_name) + '" download style="color:#263443;font-size:12px;text-decoration:none;border:1px solid #bac1c9;padding:10px 15px">Download email draft</a><span id="copy-status" style="font-size:12px;color:#5a6470">Paste into an Outlook email.</span></div>'
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
    # Independent host groups may run in parallel, but do not fetch multiple
    # etnet pages at the same time through the same corporate proxy.
    months = month_keys(day)

    def get_etnet_months():
        return {month: client.text(LOCKUP_URL.format(month=month)) for month in months}

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='hk_equities') as pool:
        phip_future = pool.submit(fetch_phip, client, day, include_gem)
        etnet_future = pool.submit(get_etnet_months)
        ipos = parse_ipos(client.text(MAIN_BOARD_URL))
        trading_dates = recent_trading_dates(client.text(HOLIDAYS_URL), day)
        snapshots = fetch_short_history(client, day, trading_dates[0], lookback=lookback)
        short = snapshots[-1]
        changes = short_history_changes(snapshots)
        phip = phip_future.result()  # Raises if any PHIP source fails verification.
        etnet_pages = etnet_future.result()  # Rejects partial HTTP responses.
        lockups: dict[tuple, Lockup] = {}
        for month in months:
            for row in parse_lockups(etnet_pages[month], month):
                if include_expired or parse_date(row.expiry) >= day:
                    lockups[(row.code, row.expiry, row.holder_type)] = row

    lockup_rows = [asdict(r) for r in sorted(lockups.values(), key=lambda r: (r.expiry, r.code, r.holder_type))]
    bloomberg_audit = enrich_lockup_rows(lockup_rows)
    baseline = {"effective": snapshots[0].effective, "url": snapshots[0].url}
    added = {event["code"]: short.securities[event["code"]] for event in changes
             if event["change"] == "ADDED" and event["code"] in short.securities}
    removed = {event["code"]: event["name"] for event in changes
               if event["change"] == "REMOVED" and event["code"] not in short.securities}
    previous = state.previous(day, mode)
    notes: list[str] = []
    if previous:
        for filing in phip:
            filing.new = filing.key not in previous["phip"]
    if parse_date(short.effective) < day:
        notes.append(f'Latest available HKEX shortable list is effective {short.effective}; no later dated page was found through {day}.')
    notes.append("Lock-up window includes the current and next calendar month" +
                 (", including earlier expiries this month." if include_expired else ", with expiries on or after the report date."))
    notes.append("The IPO source lists current announcements and prospectuses; it does not provide scheduled listing dates.")
    return {"day": day.isoformat(), "generated_at": datetime.now(HK).isoformat(), "mode": mode,
            "include_expired": include_expired,
            "months": months, "phip_start": (day - timedelta(days=6)).isoformat(),
            "ipos": [asdict(r) for r in ipos], "phip": [asdict(r) for r in phip],
            "short": asdict(short), "baseline": baseline, "added": added, "removed": removed,
            "short_changes": changes,
            "short_window": {"days": 5, "start": trading_dates[0].isoformat(), "end": day.isoformat(),
                             "label": "past 5 trading days", "dates": [d.isoformat() for d in trading_dates],
                             "lists": [{"effective": item.effective, "url": item.url,
                                        "count": len(item.securities)} for item in snapshots]},
            "lockups": lockup_rows, "bloomberg": bloomberg_audit,
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
            report['manual_sources'] = dict(client.manual_sources)
            report['cached_sources'] = dict(client.cached_sources)
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

            sections = annotate_section_changes(report, state.previous_sections(day, 'draft'))
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
                       [PHIP(**item) for item in report['phip']], None,
                       sections=sections, generated_at=report['generated_at'])
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
    print('HK EQUITIES — OUTLOOK CLEAR VERSION (same proven RESILIENT network)', flush=True)
    print('Checking live public sources: HKEX, Hong Kong holiday calendar, etnet ...', flush=True)
    print('PHIP and etnet fetch in parallel; etnet months run one at a time.', flush=True)
    print('Verified same-day etnet cache: ON (max ' + str(ETNET_CACHE_MAX_MINUTES) + ' minutes).')
    if HTTPS_PROXY_URL.strip():
        print('Using configured corporate proxy: ' + urlparse(HTTPS_PROXY_URL).netloc)
    print('Email will NOT be sent automatically.\n')
    try:
        preview_path, raw_email_path, eml_path, report = generate_draft(output)
    except SourceNetworkError as exc:
        print('\nSOURCE DOWNLOAD FAILED — DRAFT NOT CREATED')
        print(str(exc))
        print('\nThis can be a stalled website response or a corporate proxy restriction;')
        print('a working proxy alone does not guarantee every destination works.')
        month_match = re.search(r'ipo-free-float\.php\?month=(\d{6})', str(exc))
        if month_match and ALLOW_MANUAL_ETNET_HTML:
            month = month_match.group(1)
            folder = (ROOT / MANUAL_ETNET_FOLDER).resolve()
            print('If the page opens in Edge, save it as HTML (full page) here:')
            print(str(folder / ('etnet_' + month + '.html')))
            print('Then rerun this notebook. The saved page must be complete; source validation is mandatory.')
            print('Already successful monthly etnet downloads are retained in same-day verified cache.')
        print('If the same page fails in Edge, check with IT for permitted access.')
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
    if report.get('manual_sources'):
        print('SOURCE REVIEW: manually saved etnet HTML used. Confirm timestamps before distribution.')
    if report.get('cached_sources'):
        print('SOURCE REVIEW: etnet source reused from verified same-day cache:', report['cached_sources'])
    if any(row['issue'] for row in report['lockups']):
        print('DATA REVIEW: some lock-up records were flagged in amber (retained, not silently dropped).')
    if report.get('bloomberg', {}).get('tranches_with_unavailable_ratios'):
        print('BLOOMBERG REVIEW: unavailable ratios are N/A; reasons are shown in the draft and JSON audit.')
        if report['bloomberg'].get('error'):
            print(report['bloomberg']['error'])

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
