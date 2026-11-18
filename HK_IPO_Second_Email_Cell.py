# Paste this entire file into a NEW second Jupyter cell, below your existing code.
# Run the original cell first. It must finish successfully and create LAST_DRAFT.
# The original code, LAST_DRAFT, and its first email are not modified.
# Bloomberg uses your existing Desktop API connection. LAST_PRICE corresponds
# to =BDP(ticker,"LAST_PRICE"); historical closes use BDH's PX_LAST field.
# IPO price uses =BDP(ticker,"EQY_INIT_PO_SH_PX").

LOCKUP_EMAIL_TO = globals().get("EMAIL_TO", "")
LOCKUP_EMAIL_CC = globals().get("EMAIL_CC", "")
LOCKUP_EMAIL_OPEN_OUTLOOK = globals().get("OPEN_OUTLOOK", True)
LOCKUP_EMAIL_CHECK_A_SHARES = True  # etnet A/H pairs + Eastmoney share classes
LOCKUP_EMAIL_WEB_TIMEOUT = 8        # Per network operation, seconds
LOCKUP_EMAIL_WEB_BUDGET = 45        # Stop starting/reading requests after this budget


def _lu_select(report):
    """Reuse the first email's actual month window; include YES and NEW."""
    import calendar
    import copy
    from datetime import date

    start = date.fromisoformat(report["day"])
    months = set(report["months"])
    last_month = max(months)
    year, month = int(last_month[:4]), int(last_month[4:])
    end = date(year, month, calendar.monthrange(year, month)[1])
    eligible = report["short"]["securities"]
    rows = []
    for original in report["lockups"]:
        expiry = date.fromisoformat(original["expiry"])
        if (start <= expiry <= end and expiry.strftime("%Y%m") in months
                and original["code"] in eligible):
            row = copy.deepcopy(original)
            row["shortable"] = "NEW" if row["code"] in report.get("added", {}) else "YES"
            rows.append(row)
    return sorted(rows, key=lambda r: (r["expiry"], r["code"], r["holder_type"])), start, end


def _lu_a_share_profile(document, code, parse_html):
    """Infer mainland A-share presence from a validated issuer capital breakdown."""
    import re

    root = parse_html(document)
    title = root.find('title')
    if (not title or not re.match(r'^0*' + str(int(code)) + r'\.HK\b', title.get_text(strip=True))
            or not re.search(r'</html\s*>', document, re.I)):
        raise ValueError('Incomplete profile or stock identity mismatch.')
    sections = []
    for tr in root.find_all('tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) == 2 and cells[0].get_text(strip=True) == '股本':
            sections.append(cells[1])
    if len(sections) != 1:
        raise ValueError('Missing or ambiguous share-capital section.')
    amounts = {}
    for tr in sections[0].find_all('tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) < 2:
            raise ValueError('Incomplete share-capital row.')
        label, value = cells[0].get_text(strip=True), cells[1].get_text(strip=True)
        if label in amounts or not re.fullmatch(r'(?:\d+|\d{1,3}(?:,\d{3})+)', value):
            raise ValueError('Invalid or duplicate share-capital value.')
        amounts[label] = int(value.replace(',', ''))
    total = amounts.get('發行股數', 0)
    classes = {k: v for k, v in amounts.items() if k != '發行股數'}
    mainland_a = {'有限制流通A股', '無限制流通A股', 'A股'}
    non_a = {'H股', '內資股及其他', '內資股', '非上市外資股', '普通股'}
    # An issued total alone is not evidence of No. Unlisted domestic shares
    # and offshore Class A voting shares are not mainland-listed A shares.
    if (total <= 0 or not classes or not set(classes) <= mainland_a | non_a
            or sum(classes.values()) != total):
        raise ValueError('Share classes do not provide a complete recognised capital breakdown.')
    return {'status': 'YES' if any(classes.get(k, 0) > 0 for k in mainland_a) else 'NO',
            'capital': amounts, 'error': None,
            'method': 'etnet issuer capital classes; not a Bloomberg field or exchange confirmation'}


def _lu_a_share_roster(document, parse_html):
    """Read exact H/A ticker pairs; absence from this roster never proves No."""
    import re
    from urllib.parse import urlparse, parse_qs

    if not re.search(r'</html\s*>', document, re.I):
        raise ValueError('Incomplete A/H table page.')
    root = parse_html(document)
    tables = []
    for table in root.find_all('table'):
        rows = table.find_all('tr')
        if rows:
            heading = rows[0].get_text(' ', strip=True)
            if 'H股代號' in heading and 'A股代號' in heading:
                tables.append(rows)
    if len(tables) != 1:
        raise ValueError('Missing or ambiguous A/H table.')
    pairs = {}
    for row in tables[0][1:]:
        cells = row.find_all('td', recursive=False)
        if len(cells) != 9:
            raise ValueError('Unexpected A/H row shape.')
        h_code = cells[1].get_text(strip=True)
        a_match = re.fullmatch(r'(滬|深|京)(\d{6})', cells[5].get_text(strip=True))
        if not re.fullmatch(r'\d{5}', h_code) or not a_match:
            raise ValueError('Invalid A/H ticker pair.')
        a_venue, a_code = a_match.groups()
        for cell, path, code in ((cells[1], 'realtime/quote.php', h_code),
                                 (cells[5], 'ashares/quote.php', a_code)):
            anchor = cell.find('a')
            link = urlparse(anchor.get('href', '') if anchor else '')
            if not link.path.endswith(path) or parse_qs(link.query).get('code') != [code]:
                raise ValueError('A/H ticker does not match its source link.')
        if h_code in pairs:
            raise ValueError('Duplicate H-share ticker in A/H table.')
        pairs[h_code] = {'a_code': a_code,
                         'a_exchange': {'滬': 'Shanghai', '深': 'Shenzhen', '京': 'Beijing'}[a_venue]}
    if len(pairs) < 100:
        raise ValueError('A/H table unexpectedly small; page may be incomplete.')
    return pairs


def _lu_source_text(client, url, env, deadline):
    """Reuse the original proxy/TLS opener, with bounded reads and no retry loop."""
    import time
    import urllib.request

    remaining = deadline - time.monotonic()
    timeout = float(env.get('LOCKUP_EMAIL_WEB_TIMEOUT', 8))
    if not 0 < timeout <= 30 or remaining <= 0:
        raise TimeoutError('A-share network budget exhausted or timeout setting invalid.')
    # In-memory source adapters used by the offline checks have only text().
    if not hasattr(client, 'opener'):
        return client.text(url)
    if url in client.cache:
        return client.cache[url]
    request = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json,text/html',
        'Accept-Encoding': 'identity', 'Connection': 'close', 'Cache-Control': 'no-cache'})
    with client.opener.open(request, timeout=min(timeout, remaining)) as response:
        chunks, size = [], 0
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('A-share network budget exhausted.')
            chunk = response.read1(64 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > 2_000_000:
                raise ValueError('A-share response exceeds size limit.')
            chunks.append(chunk)
        raw = b''.join(chunks)
        length = response.headers.get('Content-Length')
        if length and length.isdecimal() and int(length) != size:
            raise ValueError('Incomplete A-share response.')
        raw = env['_decode_http_encoding'](raw, response.headers.get('Content-Encoding'), url, limit=2_000_000)
        return env['_decode_source'](url, raw, response.headers.get_content_charset())


def _lu_share_structure(document, codes, day):
    """Use complete, dated ordinary-share classes; mainland-listed is not automatically A."""
    import json
    from datetime import date
    from decimal import Decimal

    data = json.loads(document)
    result = data.get('result') or {}
    rows = result.get('data')
    if (data.get('success') is not True or not isinstance(rows, list)
            or result.get('pages') != 1 or result.get('count') != len(rows) or len(rows) > 500):
        raise ValueError('Incomplete or unsuccessful share-structure response.')
    groups = {code: [] for code in codes}
    for row in rows:
        code = row.get('SECURITY_CODE')
        if code not in groups or row.get('SECUCODE') != code + '.HK':
            raise ValueError('Unexpected issuer in share-structure response.')
        groups[code].append(row)
    labels = {'001': '已发行普通股', '001001': '香港普通股', '001002': '非港股',
              '001002001': '内地上市股', '001002002': '海外上市股', '001002003': '非上市流通股'}
    output = {}
    for code, entries in groups.items():
        item = {'status': 'N/A', 'error': None}
        try:
            amounts, dates = {}, set()
            for row in entries:
                key = row.get('SHARES_TYPE_CODE')
                if key not in labels or key in amounts or row.get('SHARES_TYPE') != labels[key]:
                    raise ValueError('Unknown or duplicate share class.')
                value = Decimal(str(row['SHARES_NUM']))
                if not value.is_finite() or value < 0 or value != value.to_integral_value():
                    raise ValueError('Invalid share count.')
                amounts[key] = int(value)
                dates.add(date.fromisoformat(row['CHANGE_DATE'][:10]))
            if len(dates) != 1 or next(iter(dates)) > day:
                raise ValueError('Missing, mixed or future share-structure date.')
            total, hk = amounts.get('001'), amounts.get('001001')
            non_hk = amounts.get('001002', 0)
            leaves = sum(amounts.get(k, 0) for k in ('001002001', '001002002', '001002003'))
            if (total is None or hk is None or total <= 0 or hk <= 0
                    or total != hk + non_hk or non_hk != leaves):
                raise ValueError('Share classes do not reconcile to the complete issued total.')
            item.update(status='MAINLAND_LISTED' if amounts.get('001002001', 0) > 0 else 'NO',
                        capital={labels[k]: v for k, v in amounts.items()},
                        asof=next(iter(dates)).isoformat(),
                        method='Eastmoney complete ordinary-share structure, RPT_HKF10_INFO_EQUITYSTR')
        except Exception as exc:
            item['error'] = str(exc)[:600]
        output[code] = item
    return output


def _lu_a_shares(codes, env):
    """Batch listings and share classes; profile fallback only for unresolved issuers."""
    from datetime import datetime
    from urllib.parse import urlencode
    import hashlib
    import re
    import time

    results, pairs, structures = {}, {}, {}
    keys = sorted(set(codes))
    if not keys:
        return results
    day = datetime.now(env['HK']).date()
    for code in keys:
        results[code] = {'status': 'N/A', 'error': None, 'retrieved_at': datetime.now(env['HK']).isoformat()}
    try:
        if not env.get('LOCKUP_EMAIL_CHECK_A_SHARES', True):
            raise ValueError('A-share lookup disabled.')
        budget = float(env.get('LOCKUP_EMAIL_WEB_BUDGET', 45))
        if not 0 < budget <= 120:
            raise ValueError('A-share network budget must be between 0 and 120 seconds.')
        deadline = time.monotonic() + budget
        client = env['Client']()
    except Exception as exc:
        for result in results.values():
            result['error'] = str(exc)[:600]
        return results
    valid = [c for c in keys if isinstance(c, str) and re.fullmatch(r'\d{5}', c)]
    def fetch(url):
        record = {'url': url, 'retrieved_at': datetime.now(env['HK']).isoformat()}
        document = _lu_source_text(client, url, env, deadline)
        record['document_sha256'] = hashlib.sha256(document.encode('utf-8')).hexdigest()
        return document, record
    roster = {'url': 'https://www.etnet.com.hk/www/tc/stocks/ah.php'}
    try:
        document, roster = fetch(roster['url'])
        pairs = _lu_a_share_roster(document, env['parse_html'])
        roster['count'] = len(pairs)
    except Exception as exc:
        roster['error'] = str(exc)[:600]
    for offset in range(0, len(valid), 40):
        batch = valid[offset:offset + 40]
        url = 'https://datacenter.eastmoney.com/securities/api/data/v1/get?' + urlencode({
            'reportName': 'RPT_HKF10_INFO_EQUITYSTR',
            'columns': 'SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,CHANGE_DATE,SHARES_TYPE_CODE,SHARES_TYPE,SHARES_NUM',
            'filter': '(SECUCODE in ("' + '","'.join(c + '.HK' for c in batch) + '"))',
            'pageNumber': '1', 'pageSize': '500', 'sortTypes': '1,1',
            'sortColumns': 'SECURITY_CODE,SHARES_TYPE_CODE', 'source': 'F10', 'client': 'PC'})
        record = {'url': url}
        try:
            document, record = fetch(url)
            parsed = _lu_share_structure(document, batch, day)
            for code, item in parsed.items():
                structures[code] = dict(item, source=record)
        except Exception as exc:
            for code in batch:
                structures[code] = {'status': 'N/A', 'error': str(exc)[:600], 'source': record}
    for code, result in results.items():
        if code not in valid:
            result['error'] = 'Invalid Hong Kong stock code.'
            continue
        structure = structures[code]
        pair = pairs.get(code)
        result.update(roster=dict(roster), share_structure=structure)
        if pair and structure['status'] == 'NO':
            result.update(pair)
            result['error'] = 'Explicit A/H listing conflicts with the complete share structure.'
        elif pair:
            result.update(pair, status='YES', method='Explicit etnet A/H ticker pair')
        elif structure['status'] == 'NO':
            result.update(status='NO', method=structure['method'])
        else:
            url = 'https://www.etnet.com.hk/www/tc/stocks/realtime/quote_ci_brief.php?code=' + str(int(code))
            try:
                document, record = fetch(url)
                profile = _lu_a_share_profile(document, code, env['parse_html'])
                result['profile'] = dict(profile, source=record)
                if profile['status'] == 'NO' and structure['status'] == 'MAINLAND_LISTED':
                    # "Mainland listed" also includes NEEQ domestic shares.
                    # Use the more specific capital classes only if both sources
                    # account for exactly the same total, H and domestic shares.
                    p, s = profile['capital'], structure['capital']
                    domestic = sum(p.get(k, 0) for k in ('內資股及其他', '內資股'))
                    if (p['發行股數'] != s['已发行普通股']
                            or p.get('H股') != s['香港普通股']
                            or domestic != s.get('内地上市股')
                            or domestic + p['H股'] != p['發行股數']):
                        raise ValueError('Domestic share classes disagree between sources.')
                    profile['method'] += '; domestic/H counts reconciled to Eastmoney (mainland-listed is not necessarily A)'
                result.update(status=profile['status'], method=profile['method'])
            except Exception as exc:
                result['error'] = str(exc)[:600]
    return results


def _lu_horizons(day):
    import calendar
    from datetime import date, timedelta

    year, month = (day.year - 1, 12) if day.month == 1 else (day.year, day.month - 1)
    previous_month = date(year, month, min(day.day, calendar.monthrange(year, month)[1]))
    return {"7D": day - timedelta(days=7), "1M": previous_month}


def _lu_bbg_request(client, securities, day, historical=False, reference_fields=None):
    """Bounded, sequential Bloomberg request; discard incomplete request results."""
    import time
    from datetime import date, datetime, timedelta

    # Validate before submitting so a bad setting cannot strand a live request.
    timeout = float(globals().get("BLOOMBERG_REQUEST_TIMEOUT_SECONDS", 30))
    if not 0 < timeout <= 120:
        raise ValueError("Bloomberg request timeout must be between 0 and 120 seconds.")
    fields = ["PX_LAST"] if historical else (reference_fields or ["LAST_PRICE", "CRNCY", "LAST_UPDATE_DT", "EQY_INIT_PO_SH_PX"])
    request = client.service.createRequest("HistoricalDataRequest" if historical else "ReferenceDataRequest")
    for security in securities:
        request.getElement("securities").appendValue(security)
    for field in fields:
        request.getElement("fields").appendValue(field)
    if historical:
        # Observed daily closes only. Do not synthesize holiday observations.
        # Cash dividends excluded; Bloomberg capital-change adjustments enabled.
        start = _lu_horizons(day)["1M"] - timedelta(days=14)
        for key, value in {
            "startDate": start.strftime("%Y%m%d"), "endDate": day.strftime("%Y%m%d"),
            "periodicitySelection": "DAILY", "periodicityAdjustment": "ACTUAL",
            "nonTradingDayFillOption": "ACTIVE_DAYS_ONLY", "nonTradingDayFillMethod": "NIL_VALUE",
            "adjustmentFollowDPDF": False, "adjustmentNormal": False,
            "adjustmentAbnormal": False, "adjustmentSplit": True,
            "pricingOption": "PRICING_OPTION_PRICE", "overrideOption": "OVERRIDE_OPTION_CLOSE",
        }.items():
            request.set(key, value)
    result = {s: {"fields": {}, "history": {}, "errors": {}} for s in securities}
    queue = client.api.EventQueue()
    correlation = client.session.sendRequest(request, eventQueue=queue)
    deadline, complete = time.monotonic() + timeout, False
    seen = set()
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("Bloomberg request timed out; incomplete response discarded.")
            event = queue.nextEvent(max(1, min(500, int(remaining * 1000))))
            kind = event.eventType()
            for message in event:
                if kind == client.api.Event.REQUEST_STATUS:
                    raise RuntimeError(str(message)[:600])
                if kind not in (client.api.Event.PARTIAL_RESPONSE, client.api.Event.RESPONSE):
                    continue
                if message.hasElement("responseError"):
                    raise RuntimeError(str(message.getElement("responseError"))[:600])
                if not message.hasElement("securityData"):
                    raise RuntimeError("Bloomberg response has no securityData.")
                data = message.getElement("securityData")
                items = [data] if historical else [data.getValueAsElement(i) for i in range(data.numValues())]
                for item in items:
                    security = item.getElementAsString("security")
                    if item.hasElement("sequenceNumber"):
                        sequence = item.getElementAsInteger("sequenceNumber")
                        if not 0 <= sequence < len(securities):
                            raise RuntimeError("Invalid Bloomberg security sequence number.")
                        security = securities[sequence]
                    if security not in result:
                        raise RuntimeError("Unexpected Bloomberg security: " + security)
                    seen.add(security)
                    entry = result[security]
                    if item.hasElement("securityError"):
                        entry["errors"]["security"] = str(item.getElement("securityError"))[:600]
                        entry["fields"].clear()
                        entry["history"].clear()
                        continue
                    if item.hasElement("fieldExceptions"):
                        errors = item.getElement("fieldExceptions")
                        for i in range(errors.numValues()):
                            error = errors.getValueAsElement(i)
                            entry["errors"][error.getElementAsString("fieldId")] = str(error.getElement("errorInfo"))[:600]
                    if not item.hasElement("fieldData"):
                        continue
                    values = item.getElement("fieldData")
                    if historical:
                        if "PX_LAST" in entry["errors"]:
                            entry["history"].clear()
                            continue
                        for i in range(values.numValues()):
                            point = values.getValueAsElement(i)
                            if not point.hasElement("date") or not point.hasElement("PX_LAST"):
                                continue
                            price = point.getElement("PX_LAST")
                            if price.isNull():
                                continue
                            observed = point.getElementAsDatetime("date")
                            if isinstance(observed, datetime):
                                observed = observed.date()
                            if not isinstance(observed, date) or not start <= observed <= day:
                                raise RuntimeError("Invalid Bloomberg historical observation date.")
                            key, value = observed.isoformat(), price.getValueAsString()
                            if key in entry["history"] and entry["history"][key] != value:
                                raise RuntimeError("Conflicting Bloomberg historical observations.")
                            entry["history"][key] = value
                    else:
                        for field in fields:
                            if field in entry["errors"] or not values.hasElement(field):
                                continue
                            element = values.getElement(field)
                            if element.isNull() or not element.numValues():
                                continue
                            if field == "LAST_UPDATE_DT":
                                try:
                                    observed = element.getValueAsDatetime()
                                    if isinstance(observed, datetime):
                                        observed = observed.date()
                                    if not isinstance(observed, date):
                                        raise ValueError("Quote date is not a date.")
                                    entry["fields"][field] = observed.isoformat()
                                except Exception:
                                    entry["errors"][field] = "Quote date unavailable or invalid."
                            else:
                                entry["fields"][field] = element.getValueAsString()
            if kind == client.api.Event.RESPONSE:
                complete = True
                break
        for security in set(securities) - seen:
            result[security]["errors"]["security"] = "Security omitted from Bloomberg response."
        return result
    finally:
        if not complete:
            try:
                client.session.cancel(correlation)
            except Exception:
                pass


def _lu_number(value):
    from decimal import Decimal, InvalidOperation

    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _lu_performance(snapshot, history, day):
    """Price returns from last available close on/before each calendar target."""
    from datetime import date

    fields = snapshot.get("fields", {})
    errors = dict(snapshot.get("errors", {}))
    errors.update({"history/" + k: v for k, v in history.get("errors", {}).items()})
    price = _lu_number(fields.get("LAST_PRICE"))
    if any(k in snapshot.get("errors", {}) for k in ("security", "request", "LAST_PRICE")):
        price = None
    if price is None or price <= 0:
        price = None
        errors.setdefault("LAST_PRICE", "Last price unavailable.")
    quote_date = fields.get("LAST_UPDATE_DT")
    if quote_date:
        try:
            if date.fromisoformat(quote_date) > day:
                price = None
                errors["LAST_PRICE"] = "Future-dated quote withheld."
        except ValueError:
            quote_date = None
    if not quote_date:
        errors.setdefault("LAST_UPDATE_DT", "Quote date unavailable.")
    if not fields.get("CRNCY"):
        errors.setdefault("CRNCY", "Price currency unavailable.")
    current = bool(quote_date and 0 <= (day - date.fromisoformat(quote_date)).days <= 10)
    ipo_price = _lu_number(fields.get("EQY_INIT_PO_SH_PX"))
    if any(k in snapshot.get("errors", {}) for k in ("security", "request", "EQY_INIT_PO_SH_PX")):
        ipo_price = None
    if ipo_price is None or ipo_price <= 0:
        ipo_price = None
        errors.setdefault("EQY_INIT_PO_SH_PX", "IPO offer price unavailable.")
    ipo_change = (price / ipo_price - 1) * 100 if price is not None and ipo_price is not None and current else None
    if ipo_change is None:
        errors["vs_IPO"] = "IPO comparison unavailable: missing IPO/current price or missing/stale quote date."
    observations = []
    if not history.get("errors"):
        for observed, raw in history.get("history", {}).items():
            value = _lu_number(raw)
            if value is not None and value > 0:
                observations.append((date.fromisoformat(observed), value))
    out = {"last_price": str(price) if price is not None else None,
           "ipo_price": str(ipo_price) if ipo_price is not None else None,
           "ipo_change_pct": str(ipo_change) if ipo_change is not None else None,
           "currency": fields.get("CRNCY"), "quote_date": quote_date, "errors": errors}
    for label, target in _lu_horizons(day).items():
        choices = [(d, p) for d, p in observations if d <= target]
        baseline = max(choices, default=None)
        # Long suspension / very old baseline: do not label it a 7D/1M move.
        valid = baseline is not None and (target - baseline[0]).days <= 10
        chronological = baseline is not None and quote_date and baseline[0] < date.fromisoformat(quote_date)
        change = (price / baseline[1] - 1) * 100 if price is not None and valid and current and chronological else None
        out[label] = {"target_date": target.isoformat(),
                      "baseline_date": baseline[0].isoformat() if baseline else None,
                      "baseline_price": str(baseline[1]) if baseline else None,
                      "change_pct": str(change) if change is not None else None}
        if change is None:
            errors[label] = "Price change unavailable: missing, stale or insufficient price history/quote date."
    return out


def _lu_fx_rate(snapshot, day):
    """USDHKD is HKD per USD; only a positive, dated Bloomberg quote is usable."""
    from datetime import date

    fields = snapshot.get('fields', {})
    errors = dict(snapshot.get('errors', {}))
    rate = _lu_number(fields.get('LAST_PRICE'))
    observed = fields.get('LAST_UPDATE_DT')
    if rate is None or rate <= 0:
        errors.setdefault('LAST_PRICE', 'USD/HKD rate unavailable or invalid.')
    try:
        quote_date = date.fromisoformat(observed)
        if not 0 <= (day - quote_date).days <= 10:
            raise ValueError('Stale or future FX quote.')
    except (TypeError, ValueError):
        errors.setdefault('LAST_UPDATE_DT', 'USD/HKD quote date missing, stale or invalid.')
    return {'security': 'USDHKD Curncy', 'hkd_per_usd': str(rate) if not errors else None,
            'quote_date': observed, 'errors': errors}


def _lu_turnover_usd(value, fx):
    amount, rate = _lu_number(value), _lu_number(fx.get('hkd_per_usd'))
    if amount is None or amount < 0 or rate is None or rate <= 0 or fx.get('errors'):
        return None
    return str(amount / rate)


def _lu_render(report, rows, start, end, retrieved_at):
    from html import escape
    from urllib.parse import urlsplit

    def text(value):
        return escape(str(value if value is not None else "N/A"))

    def number(value, suffix="", divisor=1, signed=False, decimals=2):
        n = _lu_number(value)
        if n is None:
            return "N/A"
        n /= divisor
        return (f"{n:+,.{decimals}f}" if signed else f"{n:,.{decimals}f}") + suffix

    def change(value):
        n = _lu_number(value)
        colour = "#087544" if n is not None and n > 0 else "#b11d2b" if n is not None and n < 0 else "#555555"
        return '<b style="color:' + colour + '">' + number(value, "%", signed=True) + '</b>'

    font = "font-family:'Times New Roman',Times,serif;"

    def stock_link(row):
        # Cell 1 links the stock label to row['url']; keep that exact destination.
        label, url = text(row['code'] + ' ' + row['name']), row.get('url')
        try:
            parsed = urlsplit(url or '')
            valid = parsed.scheme.lower() in ('http', 'https') and bool(parsed.netloc)
        except ValueError:
            valid = False
        if not valid:
            return '<b>' + label + '</b>'
        return '<a href="' + text(url) + '" style="' + font + 'color:#0759A4;font-weight:bold;text-decoration:underline">' + label + '</a>'

    subject = "Shortable IPO Lock-up Expiries | " + start.strftime("%d %b %Y")
    # The email body starts with the table. Its subject stays on the email itself.
    parts, plain = [], []
    if rows:
        headers = ["Expiry", "Stock / holders", "A-share", "Unlock", "Avg 20D turnover (USDm)", "Liquidity ratios", "IPO price", "Last price", "vs IPO %", "7D %", "1M %"]
        parts.append('<table width="100%" cellspacing="0" cellpadding="6" style="' + font + 'border-collapse:collapse;font-size:14px;border-top:2px solid #CB2125"><tr>'
                     + ''.join('<th align="left" style="background:#eeeeee;border-bottom:1px solid #cccccc">'
                               + (h.replace('turnover (USDm)', '<br>turnover (USDm)') if h.startswith('Avg 20D') else h)
                               + '</th>' for h in headers) + '</tr>')
        for i, row in enumerate(rows):
            p = row["price_performance"]
            expiry = row["expiry"]
            from datetime import date
            days = (date.fromisoformat(expiry) - start).days
            holder_count = str(row["holders"])
            holders = row["holder_type"] + " · " + holder_count + (" holder" if holder_count == "1" else " holders")
            amount = ("HKDm " + number(row.get("unlock_amount_hkd"), divisor=1000000)
                      if row.get("unlock_amount_hkd") is not None else row.get("amount", "N/A"))
            quote_time = report.get("source_asof", {}).get(expiry.replace("-", "")[:6])
            unlock = '<b>' + text(row["percent"]) + '</b> of issued shares<br>' + text(amount)
            if quote_time:
                unlock += '<br><span style="font-size:11px;color:#666666">Value as of ' + text(quote_time) + ' HKT</span>'
            ratios = (number(row.get("unlock_to_float_market_cap_pct"), "%") + ' / float cap<br>'
                      + number(row.get("unlock_to_20d_avg_turnover_x"), "x") + ' / 20D turnover')
            # Convert cell 1's HKD denominator with one shared current USD/HKD quote.
            turnover = number(row.get("avg_turnover_20d_usd"), divisor=1000000)
            turnover_end = report.get("bloomberg", {}).get("turnover_end_date")
            if turnover_end:
                turnover += '<br><span style="font-size:11px;color:#666666">To ' + text(turnover_end) + '</span>'
            a_share = text(row.get("a_share", {}).get("status", "N/A"))
            last = number(p["last_price"], decimals=3) + ' ' + text(p["currency"])
            last += '<br><span style="font-size:11px;color:#666666">Quote: ' + text(p["quote_date"]) + '</span>'
            ipo = number(p["ipo_price"], decimals=3) + ' ' + text(p["currency"])
            needs_review = bool(row.get("issue") or row.get("source_issue") or row.get("bloomberg_issues") or p["errors"]
                                or row.get("a_share", {}).get("error") or row.get("avg_turnover_20d_usd") is None)
            stock = stock_link(row) + '<br>' + text(holders)
            if needs_review:
                stock += '<br><span style="font-size:11px;color:#795b00">REVIEW</span>'
            cells = ['<span style="white-space:nowrap">' + text(expiry) + '</span><br><span style="color:#666666">' + str(days) + ' days</span>',
                     stock,
                     a_share, unlock, turnover, ratios, ipo, last, change(p["ipo_change_pct"]),
                     change(p["7D"]["change_pct"]), change(p["1M"]["change_pct"])]
            percent = str(row.get('percent', '')).strip()
            unlock_pct = _lu_number(percent[:-1].strip()) if percent.endswith('%') else None
            highlights = {}
            if unlock_pct is not None and unlock_pct > 30:
                highlights[3] = ('#FFF2CC', 'color:#6B4F00;')
            if row.get('a_share', {}).get('status') == 'YES':
                highlights[2] = ('#E2F0D9', 'color:#245B28;font-weight:bold;')
            background = '#ffffff' if i % 2 == 0 else '#f7f7f7'
            formatted = []
            for index, cell in enumerate(cells):
                colour, extra = highlights.get(index, (background, ''))
                formatted.append('<td valign="top" bgcolor="' + colour + '" style="' + font + 'background-color:' + colour
                                 + ';border-bottom:1px solid #dddddd;' + extra + '">' + cell + '</td>')
            parts.append('<tr>' + ''.join(formatted) + '</tr>')
            # Detailed review reasons remain in the JSON audit, not email footnotes.
            plain.append(f"{expiry} | {row['code']} {row['name']} | {holders} | A-share {row.get('a_share', {}).get('status', 'N/A')} | Unlock {row['percent']} of issued shares / {amount} | "
                         f"Avg 20D turnover USDm {number(row.get('avg_turnover_20d_usd'), divisor=1000000)}"
                         + (f" (to {turnover_end})" if turnover_end else "") + " | "
                         f"Unlock/float cap {number(row.get('unlock_to_float_market_cap_pct'), '%')} | "
                         f"Unlock/20D turnover {number(row.get('unlock_to_20d_avg_turnover_x'), 'x')} | "
                         f"IPO price {number(p['ipo_price'], decimals=3)} {p['currency'] or 'N/A'} | "
                         f"Last {number(p['last_price'], decimals=3)} {p['currency'] or 'N/A'} (quote {p['quote_date'] or 'N/A'}) | "
                         f"vs IPO {number(p['ipo_change_pct'], '%', signed=True)} | "
                         f"7D {number(p['7D']['change_pct'], '%', signed=True)} | 1M {number(p['1M']['change_pct'], '%', signed=True)}"
                         + (f" | {row['url']}" if row.get('url') else '')
                         + (" | REVIEW" if needs_review else ""))
        parts.append('</table>')
    else:
        parts.append('<p>No shortable lock-up expiries in this window.</p>')
        plain.append('No shortable lock-up expiries in this window.')
    # Methods, source metadata and detailed review notes stay outside the email.
    body = '<!doctype html><html><head><meta charset="utf-8"></head><body style="' + font + 'color:#222222"><div id="email-content" style="' + font + 'max-width:1320px;margin:18px auto">' + ''.join(parts) + '</div></body></html>'
    return subject, body, '\n'.join(plain)


def _lu_outlook(path, subject, to, cc, env):
    import os
    import subprocess

    if os.name != "nt":
        return False, "Open the saved .eml file in Outlook; automatic draft opening requires Classic Outlook for Windows."
    body = path.read_text(encoding="utf-8")
    draft = None
    try:
        import win32com.client
        draft = win32com.client.Dispatch("Outlook.Application").CreateItem(0)
    except Exception:
        # Missing/broken pywin32 or failure before a draft exists: use PowerShell.
        pass
    if draft is not None:
        try:
            draft.Subject, draft.To, draft.CC = subject, to.replace(',', ';'), cc.replace(',', ';')
            draft.Display()
            draft.HTMLBody = env["_prepend_to_outlook_signature"](body, draft.HTMLBody)
            draft.Save()
            return True, "Second Outlook draft opened and saved. Nothing sent."
        except Exception as exc:
            # Do not create a duplicate via fallback after a potentially successful Display.
            return False, "Outlook automation did not finish; check open drafts before opening the .eml. " + str(exc)[:200]
    q = lambda s: "'" + str(s).replace("'", "''") + "'"
    script = '\n'.join([
        "$ErrorActionPreference = 'Stop'",
        "$outlook = New-Object -ComObject Outlook.Application", "$mail = $outlook.CreateItem(0)",
        "$mail.Subject = " + q(subject), "$mail.To = " + q(to.replace(',', ';')), "$mail.CC = " + q(cc.replace(',', ';')),
        "$mail.Display()", "$signature = $mail.HTMLBody",
        "$html = [System.IO.File]::ReadAllText(" + q(path) + ", [System.Text.Encoding]::UTF8)",
        "$body = [regex]::Match($html, '(?is)<body[^>]*>(.*)</body>').Groups[1].Value",
        "$start = [regex]::Match($signature, '(?is)<body[^>]*>')",
        "if ($start.Success) { $mail.HTMLBody = $signature.Insert($start.Index + $start.Length, $body + '<br>') }",
        "else { $mail.HTMLBody = $html + $signature }", "$mail.Save()",
    ])
    import base64
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    try:
        completed = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                                   capture_output=True, text=True, timeout=45)
        if completed.returncode == 0:
            return True, "Second Outlook draft opened and saved. Nothing sent."
        return False, "Outlook automation unavailable. Open the saved .eml; check for an existing draft first."
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, "Outlook automation did not finish; check open drafts before opening the .eml. " + str(exc)[:200]


def _lu_run(first, env, open_outlook=True):
    import copy
    import json
    from datetime import datetime
    from email.message import EmailMessage
    from email.policy import SMTP
    from email.utils import format_datetime, make_msgid
    from pathlib import Path

    required = ("HK", "BloombergClient", "bloomberg_security", "atomic_write")
    if not first or "report" not in first or "email_html" not in first or any(k not in env for k in required):
        raise RuntimeError("Run your original first cell successfully before this second cell.")
    report = copy.deepcopy(first["report"])
    rows, start, end = _lu_select(report)
    now = datetime.now(env["HK"])
    if start != now.date():
        raise RuntimeError("The first report is not dated today in Hong Kong. Rerun the original cell first.")
    securities = sorted({env["bloomberg_security"](r["code"]) for r in rows})
    snapshots, histories = {}, {}
    fx_snapshot = {'errors': {'request': 'Bloomberg FX not requested.'}}
    if securities:
        print(f"Second email: fetching Bloomberg prices for {len(securities)} unique stocks ...", flush=True)
        try:
            if not env.get("BLOOMBERG_ENABLED", True):
                raise RuntimeError("Bloomberg disabled in the first cell's settings.")
            size = min(100, max(1, int(env.get("BLOOMBERG_BATCH_SIZE", 100))))
            with env["BloombergClient"]() as client:
                for offset in range(0, len(securities), size):
                    batch = securities[offset:offset + size]
                    for historical, destination in ((False, snapshots), (True, histories)):
                        try:
                            destination.update(_lu_bbg_request(client, batch, start, historical))
                        except Exception as exc:
                            destination.update({s: {"errors": {"request": str(exc)[:600]}} for s in batch})
                try:
                    fx_snapshot = _lu_bbg_request(client, ['USDHKD Curncy'], start,
                                                 reference_fields=['LAST_PRICE', 'LAST_UPDATE_DT'])['USDHKD Curncy']
                except Exception as exc:
                    fx_snapshot = {'errors': {'request': str(exc)[:600]}}
        except Exception as exc:
            fx_snapshot = {'errors': {'request': str(exc)[:600]}}
            for security in securities:
                snapshots.setdefault(security, {"errors": {"request": str(exc)[:600]}})
                histories.setdefault(security, {"errors": {"request": str(exc)[:600]}})
    retrieved = datetime.now(env["HK"]).strftime("%d %b %Y %H:%M:%S HKT")
    fx = _lu_fx_rate(fx_snapshot, start)
    metrics = {s: _lu_performance(snapshots[s], histories[s], start) for s in securities}
    if rows:
        print("Second email: checking A-share capital classes ...", flush=True)
    try:
        a_shares = _lu_a_shares([r['code'] for r in rows], env)
    except Exception as exc:
        # Reference-data failures must not prevent saving the separate email.
        a_shares = {r['code']: {'status': 'N/A', 'error': str(exc)[:600]} for r in rows}
    for row in rows:
        row["price_performance"] = metrics[env["bloomberg_security"](row["code"])]
        row['a_share'] = a_shares[row['code']]
        row['avg_turnover_20d_usd'] = _lu_turnover_usd(row.get('avg_turnover_20d_hkd'), fx)
    subject, body, plain = _lu_render(report, rows, start, end, retrieved)
    to, cc = str(env.get("LOCKUP_EMAIL_TO", "")), str(env.get("LOCKUP_EMAIL_CC", ""))
    message = EmailMessage(policy=SMTP)
    message['Subject'], message['Date'], message['Message-ID'] = subject, format_datetime(now), make_msgid()
    if to.strip():
        message['To'] = to.replace(';', ',')
    if cc.strip():
        message['Cc'] = cc.replace(';', ',')
    message['X-Unsent'] = '1'
    message.set_content(plain)
    message.add_alternative(body, subtype='html')
    folder = Path(first['email_html']).resolve().parent / 'Shortable_Lockups'
    folder.mkdir(parents=True, exist_ok=True)
    # Separate names and folder: never overwrite first-email outputs.
    stem = 'Shortable_Lockups_' + now.strftime('%Y-%m-%d_%H%M%S_%f')
    paths = {suffix: folder / (stem + suffix) for suffix in ('.html', '.eml', '.txt', '.json')}
    audit = {"source_report_date": report['day'], "source_generated_at": report.get('generated_at'),
             "window_start": start.isoformat(), "window_end": end.isoformat(), "months": report['months'],
             "shortability_effective": report['short']['effective'], "bloomberg_retrieved_at": retrieved,
             "source_asof": report.get('source_asof'), "manual_sources": report.get('manual_sources'),
             "cached_sources": report.get('cached_sources'), "original_bloomberg": report.get('bloomberg'),
             "snapshots": snapshots, "histories": histories, "rows": rows,
             "a_share_profiles": a_shares,
             "turnover_fx": fx, "turnover_fx_snapshot": fx_snapshot,
             "turnover_method": "Reuse cell 1 avg_turnover_20d_hkd / current Bloomberg USDHKD LAST_PRICE / 1,000,000. USD millions at the shared snapshot FX rate, not daily historical FX conversion. Original HKD liquidity ratios unchanged.",
             "price_method": "Calendar 7D/1M; last price / observed prior close - 1. Capital changes adjusted; cash dividends excluded.",
             "ipo_price_field": "EQY_INIT_PO_SH_PX",
             "ipo_comparison_method": "(LAST_PRICE / EQY_INIT_PO_SH_PX - 1) * 100; reported offer price, no separate corporate-action adjustment or holder-cost assumption.",
             "max_baseline_age_days": 10, "max_quote_age_days": 10}
    for suffix, content in {'.html': body.encode('utf-8'), '.eml': message.as_bytes(),
                            '.txt': plain.encode('utf-8'), '.json': json.dumps(audit, ensure_ascii=False, indent=2).encode('utf-8')}.items():
        env['atomic_write'](paths[suffix], content)
    opened, detail = (False, "Outlook opening disabled; open the saved .eml to review.")
    if open_outlook:
        opened, detail = _lu_outlook(paths['.html'], subject, to, cc, env)
    print(f"\nSECOND EMAIL READY: {len(rows)} tranches / {len(securities)} stocks")
    print(f"Expiry window: {start} to {end}; YES and NEW included.")
    print(detail)
    print("Email file:", paths['.eml'])
    print("HTML preview:", paths['.html'])
    if any(r['price_performance']['errors'] for r in rows):
        print("Some Bloomberg values are unavailable or need review; see N/A in the draft and details in its JSON file.")
    if any(r['a_share'].get('error') for r in rows):
        print("Some A-share lookups could not be verified. The draft is saved; details are in its JSON file.")
    if rows and fx['errors']:
        print("USD/HKD is unavailable or stale. USD turnover shows N/A; the draft and other values are saved.")
    if not opened and env.get('SHOW_NOTEBOOK_PREVIEW_IF_NO_OUTLOOK', True):
        try:
            from IPython.display import HTML, display
            display(HTML(body))
        except ImportError:
            pass
    return {"email_html": paths['.html'], "eml": paths['.eml'], "audit": paths['.json'], "rows": rows}


# Running this second cell creates ONLY the separate lock-up draft.
if __name__ == '__main__':
    LAST_LOCKUP_DRAFT = _lu_run(globals().get('LAST_DRAFT'), globals(), LOCKUP_EMAIL_OPEN_OUTLOOK)
