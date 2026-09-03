"""Fake blpapi: enough of the Desktop API to run daily_email.py off the terminal.

Exercises the real code path - ReferenceDataRequest, chunking, the event drain,
securityError, fieldExceptions, INDX_MEMBERS as a bulk field - against made-up
numbers, so the parsing, filtering, sorting and HTML can be tested anywhere.

    python daily_email.py --source fixture --no-outlook
"""

import datetime as dt

_TODAY = dt.date.today()


def configure(today):
    global _TODAY
    _TODAY = today


class Event:
    TIMEOUT, RESPONSE, PARTIAL_RESPONSE = 0, 1, 2

    def __init__(self, messages, event_type=1):
        self._messages, self._type = messages, event_type

    def __iter__(self):
        return iter(self._messages)

    def eventType(self):
        return self._type


class Name(str):
    pass


class Element:
    """Scalar, array-of-scalars, or complex (named children), like the real thing."""

    def __init__(self, name, value=None, children=None, array=None):
        self._name, self._value = name, value
        self._children = children                 # list[(name, Element)] when complex
        self._array = array                       # list[Element] when an array

    def name(self):
        return Name(self._name)

    def isArray(self):
        return self._array is not None

    def isComplexType(self):
        # A bulk field (INDX_MEMBERS) is an array whose values are complex, and
        # the real API reports isArray() and isComplexType() both True for it.
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

    def appendValue(self, v):
        self._array.append(Element('item', v))

    def set(self, key, value):
        self._children = [(n, e) for n, e in (self._children or []) if n != key]
        self._children.append((key, Element(key, value)))


def complex_el(name, pairs):
    return Element(name, children=[(n, e if isinstance(e, Element) else Element(n, e))
                                   for n, e in pairs])


def array_el(name, items):
    return Element(name, array=list(items))


class Message:
    def __init__(self, root):
        self._root = root

    def hasElement(self, key):
        return self._root.hasElement(key)

    def getElement(self, key):
        return self._root.getElement(key)

    def toString(self):
        return f'<fake message {self._root.name()}>'


class Request:
    def __init__(self, operation):
        self.operation = operation
        self._root = Element('request', children=[
            ('securities', array_el('securities', [])),
            ('fields', array_el('fields', [])),
        ])

    def getElement(self, key):
        return self._root.getElement(key)

    def asElement(self):
        return self._root

    def set(self, key, value):
        self._root.set(key, value)

    @property
    def securities(self):
        return [e._value for e in self._root.getElement('securities')._array]

    @property
    def fields(self):
        return [e._value for e in self._root.getElement('fields')._array]


class Service:
    def __init__(self, name):
        self._name = name

    def createRequest(self, operation):
        return Request(operation)

    def numOperations(self):
        return 0


class SessionOptions:
    def setServerHost(self, *a): pass
    def setServerPort(self, *a): pass


# ------------------------------------------------------------ fake market ---
UNKNOWN_SECURITY = {'XXXX FAKE Index'}          # exercises the securityError path
UNKNOWN_FIELDS = {'ECO_RELEASE_DT', 'CONF_CALL_DT', 'CONF_CALL_TIME', 'ECO_RELEASE_TIME'}

HSI_MEMBERS = [
    ('700 HK', 'TENCENT'), ('939 HK', 'CCB'), ('1299 HK', 'AIA'), ('941 HK', 'CHINA MOBILE'),
    ('9988 HK', 'BABA-W'), ('388 HK', 'HKEX'), ('1398 HK', 'ICBC'), ('3988 HK', 'BANK OF CHINA'),
    ('2318 HK', 'PING AN'), ('883 HK', 'CNOOC'), ('16 HK', 'SHK PPT'), ('1810 HK', 'XIAOMI-W'),
    ('3690 HK', 'MEITUAN-W'), ('2020 HK', 'ANTA SPORTS'), ('27 HK', 'GALAXY ENT'),
    ('1113 HK', 'CK ASSET'), ('2 HK', 'CLP HOLDINGS'), ('386 HK', 'SINOPEC'),
    ('9618 HK', 'JD-SW'), ('1211 HK', 'BYD'), ('6862 HK', 'HAIDILAO'), ('1928 HK', 'SANDS CHINA'),
]


def _bday(base, n):
    d, step = base, (1 if n >= 0 else -1)
    for _ in range(abs(n)):
        d += dt.timedelta(days=step)
        while d.weekday() >= 5:
            d += dt.timedelta(days=step)
    return d


def _eco_row(ticker, label, idx):
    offset = (idx * 5) % 88 + 2
    when = _bday(_TODAY, offset)
    survey = round(0.1 + (idx % 17) * 0.13, 2)
    prior = round(survey - 0.05 * ((idx % 5) - 2), 2)
    return [('ECO_FUTURE_RELEASE_DATE', when.strftime('%Y-%m-%d')),
            ('ECO_FUTURE_RELEASE_TIME', '08:30' if idx % 3 == 0 else ('10:00' if idx % 3 == 1 else '14:00')),
            ('BN_SURVEY_MEDIAN', survey), ('PX_LAST', prior),
            ('RELEVANCE_VALUE', 99 - (idx % 40)), ('NAME', label.upper())]


def _cb_row(ticker, label, idx):
    when = _bday(_TODAY, (idx * 9) % 80 + 3)
    rate = round(0.25 + idx * 0.55, 2)
    return [('ECO_FUTURE_RELEASE_DATE', when.strftime('%Y-%m-%d')),
            ('ECO_FUTURE_RELEASE_TIME', '14:00' if idx % 2 else '09:00'),
            ('BN_SURVEY_MEDIAN', rate), ('PX_LAST', rate),
            ('RELEVANCE_VALUE', 99), ('NAME', label.upper())]


def _earn_row(ticker, name, idx):
    when = _bday(_TODAY, (idx * 4) % 86 + 1)
    call = _bday(when, 0)
    # ERN_ANN_DT_AND_PER returns history AND estimated forward dates together.
    bulk = array_el('ERN_ANN_DT_AND_PER', [
        complex_el('row', [('Announcement Date', d.strftime('%Y-%m-%d')),
                           ('Financial Period', 'FY26')])
        for d in (_bday(_TODAY, -120), _bday(_TODAY, -30), when)])
    # every 7th name has no scalar report date - only the bulk field, so the
    # fallback path is exercised on every fixture run
    scalar_missing = (idx % 7 == 3)
    return [('NAME', name),
            ('EXPECTED_REPORT_DT', None if scalar_missing else when.strftime('%Y-%m-%d')),
            ('EXPECTED_REPORT_TIME', None if scalar_missing else
             ['Bef-mkt', '12:00', 'Aft-mkt', '07:00'][idx % 4]),
            ('EARNINGS_CONF_CALL_DT', call.strftime('%Y-%m-%d') if idx % 5 else None),
            ('EARNINGS_CONF_CALL_TIME', '16:30' if idx % 5 else None),
            ('ERN_ANN_DT_AND_PER', bulk)]


def _fake_fields(security, wanted):
    """Everything the fixture knows, before the requested-field filter."""
    import daily_email as de
    if security == de.HSI_INDEX:
        members = [complex_el('INDX_MEMBERS',
                              [('Member Ticker and Exchange Code', t)]) for t, _ in HSI_MEMBERS]
        return [('INDX_MEMBERS', array_el('INDX_MEMBERS', members))]
    for i, (t, label) in enumerate(de.US_ECO_TICKERS):
        if t == security:
            return _eco_row(t, label, i)
    for i, (_c, _b, t, label, _tz) in enumerate(de.CENTRAL_BANKS):
        if t == security:
            return _cb_row(t, label, i)
    base = security[:-len(' Equity')] if security.upper().endswith(' EQUITY') else security
    for i, (t, name) in enumerate(HSI_MEMBERS):
        if t == base:
            return _earn_row(t, name, i)
    return []


class Session:
    def __init__(self, options=None):
        self._queue = []

    def start(self):
        return True

    def stop(self):
        pass

    def openService(self, name):
        return name in ('//blp/refdata', '//blp/apiflds', '//blp/instruments')

    def getService(self, name):
        return Service(name)

    def sendRequest(self, request):
        wanted = set(request.fields)
        sec_elements = []
        for sec in request.securities:
            if sec in UNKNOWN_SECURITY:
                sec_elements.append(complex_el('securityData', [
                    ('security', sec),
                    ('securityError', complex_el('securityError', [('message', 'Unknown/Invalid Security')])),
                ]))
                continue
            pairs = [(k, v) for k, v in _fake_fields(sec, wanted)
                     if k in wanted and v is not None]
            fd = complex_el('fieldData', pairs)
            kids = [('security', sec), ('fieldData', fd)]
            bad = sorted(wanted & UNKNOWN_FIELDS)
            if bad:
                kids.append(('fieldExceptions', array_el('fieldExceptions', [
                    complex_el('fieldExceptions', [
                        ('fieldId', f),
                        ('errorInfo', complex_el('errorInfo', [
                            ('subcategory', 'BAD_FLD'), ('message', 'Invalid Field')])),
                    ]) for f in bad])))
            sec_elements.append(complex_el('securityData', kids))
        root = Element('ReferenceDataResponse',
                       children=[('securityData', array_el('securityData', sec_elements))])
        self._queue = [Event([Message(root)], Event.RESPONSE)]

    def nextEvent(self, timeout=0):
        return self._queue.pop(0) if self._queue else Event([], Event.TIMEOUT)
