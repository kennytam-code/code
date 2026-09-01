"""Price alarm — speaks out loud when a watched name crosses a % threshold.

Reads a watchlist CSV (ticker, thresholds, repeat cap), polls Bloomberg for
LAST_PRICE and CHG_PCT_1D, and announces "Tencent is trading at 612.50, up
3.1 percent" through the machine's voice whenever the day move crosses one of
your thresholds. Works both ways: a -3 threshold speaks on the way down.

A threshold re-arms once the price retreats past it (by REARM_BUFFER_PCT), so a
name that crosses, falls back and crosses again is announced again — capped at
MaxRepeats announcements per threshold per day, set per ticker in the CSV.

Run it:
    START_PRICE_ALARM.bat              (Windows, double-click, on the terminal)
    python price_alarm.py              (same thing from a prompt)
    python price_alarm.py --demo       (fake prices, no Bloomberg — hear it work)
"""

import argparse
import csv
import os
import platform
import queue
import random
import subprocess
import sys
import threading
from datetime import datetime

# ----------------------------------------------------------------- CONFIG ---
WATCHLIST_CSV      = 'watchlist.csv'   # sits next to this script
POLL_SECONDS       = 4                 # seconds between Bloomberg snapshots
DEFAULT_MAX_REPEATS = 2                # announcements per threshold per day
REARM_BUFFER_PCT   = 0.25              # retreat this far past a threshold to re-arm
EVENT_SPINS        = 120               # bounded drain: ~60s worst case at 500ms
RECONNECT_BACKOFF_S = [5, 10, 20, 30, 60]   # then stays at 60
GUI_DRAIN_MS       = 250               # how often the window reads the poll queue
BBG_HOST           = 'localhost'
BBG_PORT           = 8194
MAX_ROWS_LOG       = 500               # announcement log lines kept on screen

HERE = os.path.dirname(os.path.abspath(__file__))

SAMPLE_WATCHLIST = """Ticker,NickName,Thresholds,MaxRepeats
700 HK Equity,Tencent,3;5;-3;-5,
2330 TT Equity,TSMC,3;-3,2
NVDA US Equity,Nvidia,5;-5,1
"""


# -------------------------------------------------------------- WATCHLIST ---
class WatchItem:
    """One row of the watchlist."""

    def __init__(self, ticker, nickname, thresholds, max_repeats):
        self.ticker = ticker
        self.nickname = nickname
        self.thresholds = thresholds        # list of signed floats, e.g. [3, 5, -3]
        self.max_repeats = max_repeats      # int >= 1

    def __repr__(self):
        return f'WatchItem({self.ticker!r}, {self.nickname!r}, {self.thresholds})'


def default_nickname(ticker):
    """'700 HK Equity' -> '700 HK'.  Spoken names read better without the suffix."""
    t = ticker.strip()
    for suffix in (' Equity', ' Index', ' Curncy', ' Comdty'):
        if t.upper().endswith(suffix.upper()):
            return t[: -len(suffix)].strip()
    return t


def parse_thresholds(raw, where=''):
    """'3;5;-3' -> [3.0, 5.0, -3.0].  Blanks skipped, 0 and junk rejected."""
    out = []
    for piece in str(raw).split(';'):
        piece = piece.strip().replace('%', '')
        if not piece:
            continue
        try:
            val = float(piece)
        except ValueError:
            raise ValueError(f'{where}: "{piece}" is not a number — '
                             f'thresholds look like 3;5;-3')
        if val == 0:
            raise ValueError(f'{where}: a threshold of 0 would fire constantly')
        if val in out:
            raise ValueError(f'{where}: threshold {piece} listed twice')
        out.append(val)
    if not out:
        raise ValueError(f'{where}: no thresholds given')
    return out


def load_watchlist(path):
    """Read the CSV into WatchItems.  Raises ValueError naming the bad row."""
    items, seen = [], set()
    with open(path, newline='', encoding='utf-8-sig') as fh:
        reader = csv.DictReader(fh)
        cols = {(c or '').strip().lower() for c in (reader.fieldnames or [])}
        for need in ('ticker', 'thresholds'):
            if need not in cols:
                raise ValueError(f'{os.path.basename(path)}: missing a "{need}" '
                                 f'column — header should be '
                                 f'Ticker,NickName,Thresholds,MaxRepeats')
        for n, row in enumerate(reader, start=2):     # row 1 is the header
            row = {(k or '').strip().lower(): (v or '').strip()
                   for k, v in row.items()}
            ticker = row.get('ticker', '')
            if not ticker or ticker.startswith('#'):
                continue
            where = f'row {n} ({ticker})'
            if ticker.upper() in seen:
                raise ValueError(f'{where}: this ticker is listed twice')
            seen.add(ticker.upper())

            thresholds = parse_thresholds(row.get('thresholds', ''), where)

            raw_max = row.get('maxrepeats', '')
            if raw_max:
                try:
                    max_repeats = int(float(raw_max))
                except ValueError:
                    raise ValueError(f'{where}: MaxRepeats "{raw_max}" '
                                     f'is not a whole number')
                if max_repeats < 1:
                    raise ValueError(f'{where}: MaxRepeats must be 1 or more')
            else:
                max_repeats = DEFAULT_MAX_REPEATS

            nickname = row.get('nickname', '') or default_nickname(ticker)
            items.append(WatchItem(ticker, nickname, thresholds, max_repeats))
    if not items:
        raise ValueError(f'{os.path.basename(path)}: no tickers found')
    return items


# ------------------------------------------------------------------ ENGINE ---
def announcement(name, price, pct):
    """The sentence the computer says."""
    way = 'up' if pct >= 0 else 'down'
    return f'{name} is trading at {price:,.2f}, {way} {abs(pct):.1f} percent'


class AlarmEngine:
    """Threshold state machine.  No Bloomberg, no audio, no threads — so the
    crossing rules can be tested on any machine.

    One state per (ticker, threshold): armed or spent, plus how many times it
    has spoken today.  Armed + through the level = announce and disarm.  It
    only re-arms once the price pulls back past the level by the buffer, which
    is what stops a name sitting on +3.00 from talking every four seconds.
    """

    def __init__(self, items, rearm_buffer=REARM_BUFFER_PCT):
        self.items = {it.ticker: it for it in items}
        self.rearm_buffer = float(rearm_buffer)
        self._st = {}
        self._day = None
        self.reset()

    def reset(self):
        """Re-arm everything and zero the counts (new day, or the button)."""
        self._st = {}
        for tkr, it in self.items.items():
            for thr in it.thresholds:
                self._st[(tkr, thr)] = {'armed': True, 'count': 0}

    def status(self, ticker):
        """[(threshold, armed, count, max)] for the on-screen table."""
        it = self.items.get(ticker)
        if not it:
            return []
        return [(thr, self._st[(ticker, thr)]['armed'],
                 self._st[(ticker, thr)]['count'], it.max_repeats)
                for thr in it.thresholds]

    def update(self, ticker, price, pct, now=None):
        """Feed one price.  Returns the sentences to speak (0 or 1 of them)."""
        now = now or datetime.now()
        today = now.date()
        if self._day is None:
            self._day = today
        elif today != self._day:
            self.reset()
            self._day = today

        it = self.items.get(ticker)
        if it is None or price is None or pct is None:
            return []

        fired = []
        for thr in it.thresholds:
            st = self._st[(ticker, thr)]
            through = (pct >= thr) if thr > 0 else (pct <= thr)
            back = ((pct <= thr - self.rearm_buffer) if thr > 0
                    else (pct >= thr + self.rearm_buffer))
            if through:
                if st['armed'] and st['count'] < it.max_repeats:
                    st['armed'] = False
                    st['count'] += 1
                    fired.append(thr)
            elif back and not st['armed']:
                st['armed'] = True

        if not fired:
            return []
        # A jump from flat to +5.5 crosses +3 and +5 at once: both are spent,
        # but the desk hears one sentence — it quotes the real move anyway.
        return [announcement(it.nickname, price, pct)]


# ------------------------------------------------------------------ SPEECH ---
class Speaker:
    """Speaks queued sentences one at a time on a background thread.

    Named speak(), never say() — say() is the console status printer in the
    desk scripts and these files sometimes end up in the same namespace.
    """

    def __init__(self, on_log=None):
        self.mute = False
        self._q = queue.Queue()
        self._on_log = on_log
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def speak(self, text):
        self._q.put(text)

    def stop(self):
        self._q.put(None)

    def _run(self):
        while True:
            text = self._q.get()
            if text is None:
                return
            if self.mute:
                continue          # a stale announcement spoken later is wrong
            try:
                self._utter(text)
            except Exception as exc:
                if self._on_log:
                    self._on_log(f'speech failed: {exc}')

    def _utter(self, text):
        """Blocking on purpose — the queue is what makes it async, and running
        these one after another is what stops two voices overlapping."""
        if sys.platform == 'darwin':
            subprocess.run(['/usr/bin/say', text], check=False)
        elif sys.platform.startswith('win'):
            safe = text.replace("'", "''")
            subprocess.run(
                ['powershell', '-NoProfile', '-Command',
                 "Add-Type -AssemblyName System.Speech; "
                 "(New-Object System.Speech.Synthesis.SpeechSynthesizer)"
                 f".Speak('{safe}')"],
                check=False,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        else:
            subprocess.run(['espeak', text], check=False)


# -------------------------------------------------------------------- FEED ---
class BloombergFeed:
    """One long-lived //blp/refdata session, re-used for every poll.

    LAST_PRICE and CHG_PCT_1D are the same two fields you would type as
    =BDP(A2,"LAST_PRICE") — this is the request/response snapshot, which is
    how every other script on this desk talks to Bloomberg.
    """

    name = 'Bloomberg'

    def __init__(self, host=BBG_HOST, port=BBG_PORT):
        self.host, self.port = host, port
        self.connected = False
        self._blpapi = None
        self._ss = None
        self._svc = None

    def connect(self):
        try:
            import blpapi
        except ImportError:
            raise RuntimeError(
                'blpapi is not installed in this Python — start the alarm from '
                'the same environment the desk notebooks run in')
        self._blpapi = blpapi
        opts = blpapi.SessionOptions()
        opts.setServerHost(self.host)
        opts.setServerPort(self.port)
        self._ss = blpapi.Session(opts)
        if not self._ss.start():
            raise RuntimeError('cannot start a Bloomberg session — is the '
                               'terminal running and logged in on this machine?')
        if not self._ss.openService('//blp/refdata'):
            raise RuntimeError('cannot open //blp/refdata')
        self._svc = self._ss.getService('//blp/refdata')
        self.connected = True

    def poll(self, tickers):
        """One batched request for every name.  Returns
        {ticker: {'price': float|None, 'pct': float|None, 'error': str|None}}."""
        blpapi = self._blpapi
        out = {t: {'price': None, 'pct': None, 'error': None} for t in tickers}

        rq = self._svc.createRequest('ReferenceDataRequest')
        for t in tickers:
            rq.getElement('securities').appendValue(t)
        for f in ('LAST_PRICE', 'CHG_PCT_1D'):
            rq.getElement('fields').appendValue(f)
        self._ss.sendRequest(rq)

        for _spin in range(EVENT_SPINS):        # bounded: never hang the desk
            ev = self._ss.nextEvent(500)
            for msg in ev:
                if not msg.hasElement('securityData'):
                    continue
                arr = msg.getElement('securityData')
                for i in range(arr.numValues()):
                    sd = arr.getValueAsElement(i)
                    tkr = sd.getElementAsString('security')
                    if tkr not in out:
                        continue
                    if sd.hasElement('securityError'):
                        err = sd.getElement('securityError')
                        out[tkr]['error'] = (
                            err.getElementAsString('message')
                            if err.hasElement('message') else 'security error')
                        continue
                    if not sd.hasElement('fieldData'):
                        continue
                    fd = sd.getElement('fieldData')
                    # hasElement first, always: getElementAsFloat on a missing
                    # field throws and would take the whole poll down with it.
                    if fd.hasElement('LAST_PRICE'):
                        out[tkr]['price'] = fd.getElementAsFloat('LAST_PRICE')
                    if fd.hasElement('CHG_PCT_1D'):
                        out[tkr]['pct'] = fd.getElementAsFloat('CHG_PCT_1D')
            if ev.eventType() == blpapi.Event.RESPONSE:
                break
        else:
            raise RuntimeError('Bloomberg did not answer within ~60s — '
                               'check the terminal session')
        return out

    def close(self):
        try:
            if self._ss is not None:
                self._ss.stop()
        except Exception:
            pass
        self._ss = self._svc = None
        self.connected = False


class FakeFeed:
    """Random walk for --demo: no terminal, no market, but it does speak."""

    name = 'demo (fake prices)'
    poll_seconds = 2                       # livelier than the real thing

    def __init__(self, tickers, seed=None):
        rnd = random.Random(seed)
        self._rnd = rnd
        self._state = {t: {'pct': rnd.uniform(-2, 2),
                           'close': rnd.uniform(20, 600)}
                       for t in tickers}
        self.connected = False

    def connect(self):
        self.connected = True

    def poll(self, tickers):
        out = {}
        for t in tickers:
            s = self._state.setdefault(
                t, {'pct': 0.0, 'close': self._rnd.uniform(20, 600)})
            # drift wide enough to trip a 3% threshold within ~15 seconds
            s['pct'] = max(-12.0, min(12.0, s['pct'] + self._rnd.gauss(0, 1.6)))
            if self._rnd.random() < 0.03:      # occasional pre-open style blank
                out[t] = {'price': None, 'pct': None, 'error': None}
                continue
            price = s['close'] * (1 + s['pct'] / 100.0)
            out[t] = {'price': price, 'pct': s['pct'], 'error': None}
        return out

    def close(self):
        self.connected = False


# --------------------------------------------------------------- POLL LOOP ---
class PollWorker:
    """Runs the feed on a background thread and posts results to a queue.

    Nothing here touches a widget — Tk is not thread-safe, so the window drains
    the queue on its own timer instead.
    """

    def __init__(self, feed, engine, speaker, out_q, tickers, poll_seconds=None):
        self.feed, self.engine, self.speaker = feed, engine, speaker
        self.out_q, self.tickers = out_q, tickers
        self.poll_seconds = poll_seconds or getattr(feed, 'poll_seconds',
                                                    POLL_SECONDS)
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def _run(self):
        attempt = 0
        while not self._stop.is_set():
            try:
                if not self.feed.connected:
                    self.feed.connect()
                    attempt = 0
                    self.out_q.put(('log', f'connected to {self.feed.name}'))
                results = self.feed.poll(self.tickers)
            except Exception as exc:
                self.feed.close()
                wait = RECONNECT_BACKOFF_S[min(attempt,
                                               len(RECONNECT_BACKOFF_S) - 1)]
                attempt += 1
                self.out_q.put(('error', str(exc)))
                self.out_q.put(('log', f'retrying in {wait}s (attempt {attempt})'))
                self._stop.wait(wait)
                continue

            spoken = []
            for tkr, r in results.items():
                for text in self.engine.update(tkr, r['price'], r['pct']):
                    spoken.append(text)
                    self.speaker.speak(text)
            self.out_q.put(('tick', results, spoken))
            self._stop.wait(self.poll_seconds)
        self.out_q.put(('log', 'stopped'))


# --------------------------------------------------------------------- GUI ---
def build_gui(items, engine, speaker, feed):
    import tkinter as tk
    from tkinter import ttk

    tickers = [it.ticker for it in items]
    out_q = queue.Queue()
    worker = PollWorker(feed, engine, speaker, out_q, tickers)

    root = tk.Tk()
    root.title('Price Alarm')
    root.geometry('980x620')

    bar = ttk.Frame(root, padding=(8, 8))
    bar.pack(fill='x')
    btn_run = ttk.Button(bar, text='Start')
    btn_mute = ttk.Button(bar, text='Mute')
    btn_reset = ttk.Button(bar, text='Reset counts')
    for b in (btn_run, btn_mute, btn_reset):
        b.pack(side='left', padx=(0, 6))
    lbl_status = ttk.Label(bar, text='idle')
    lbl_status.pack(side='right')

    cols = ('ticker', 'name', 'price', 'chg', 'alarms', 'state')
    tree = ttk.Treeview(root, columns=cols, show='headings', height=14)
    for c, head, w, anchor in (
            ('ticker', 'Ticker', 160, 'w'), ('name', 'Name', 130, 'w'),
            ('price', 'Price', 100, 'e'), ('chg', 'Chg %', 80, 'e'),
            ('alarms', 'Alarms  (fired/max)', 300, 'w'),
            ('state', 'Status', 190, 'w')):
        tree.heading(c, text=head)
        tree.column(c, width=w, anchor=anchor)
    tree.tag_configure('up', foreground='#0a7a25')
    tree.tag_configure('down', foreground='#b3120f')
    tree.tag_configure('bad', foreground='#8a6d00')
    tree.pack(fill='both', expand=True, padx=8)
    for it in items:
        tree.insert('', 'end', iid=it.ticker,
                    values=(it.ticker, it.nickname, '—', '—', '', 'waiting'))

    ttk.Label(root, text='Announcements', padding=(8, 6, 8, 0)).pack(anchor='w')
    log_frame = ttk.Frame(root)
    log_frame.pack(fill='both', expand=True, padx=8, pady=(0, 8))
    log = tk.Text(log_frame, height=9, state='disabled', wrap='none')
    scroll = ttk.Scrollbar(log_frame, command=log.yview)
    log.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right', fill='y')
    log.pack(side='left', fill='both', expand=True)

    def write_log(line):
        log.configure(state='normal')
        log.insert('end', f'{datetime.now():%H:%M:%S}  {line}\n')
        if int(log.index('end-1c').split('.')[0]) > MAX_ROWS_LOG:
            log.delete('1.0', '2.0')
        log.see('end')
        log.configure(state='disabled')

    def alarm_cell(ticker):
        bits = []
        for thr, armed, count, mx in engine.status(ticker):
            bits.append(f'{thr:+g}%{"" if armed else "*"} {count}/{mx}')
        return '   '.join(bits)

    def on_tick(results, spoken):
        for tkr, r in results.items():
            it = engine.items[tkr]
            if r['error']:
                tree.item(tkr, values=(tkr, it.nickname, '—', '—',
                                       alarm_cell(tkr), r['error'][:40]),
                          tags=('bad',))
                continue
            price = '—' if r['price'] is None else f'{r["price"]:,.2f}'
            pct = '—' if r['pct'] is None else f'{r["pct"]:+.2f}'
            state = 'live' if r['pct'] is not None else 'waiting for first print'
            tag = ('up',) if (r['pct'] or 0) > 0 else (
                ('down',) if (r['pct'] or 0) < 0 else ())
            tree.item(tkr, values=(tkr, it.nickname, price, pct,
                                   alarm_cell(tkr), state), tags=tag)
        for text in spoken:
            write_log(('[muted] ' if speaker.mute else '') + text)
        lbl_status.config(text=f'last poll {datetime.now():%H:%M:%S}')

    def drain():
        try:
            while True:
                msg = out_q.get_nowait()
                if msg[0] == 'tick':
                    on_tick(msg[1], msg[2])
                elif msg[0] == 'error':
                    write_log(f'!! {msg[1]}')
                    lbl_status.config(text='disconnected')
                else:
                    write_log(msg[1])
        except queue.Empty:
            pass
        root.after(GUI_DRAIN_MS, drain)

    def toggle_run():
        if worker.running:
            worker.stop()
            btn_run.config(text='Start')
            lbl_status.config(text='stopping…')
        else:
            worker.start()
            btn_run.config(text='Stop')
            lbl_status.config(text='starting…')

    def toggle_mute():
        speaker.mute = not speaker.mute
        btn_mute.config(text='Unmute' if speaker.mute else 'Mute')
        write_log('muted — alarms still logged' if speaker.mute else 'unmuted')

    def do_reset():
        engine.reset()
        for it in items:
            vals = list(tree.item(it.ticker, 'values'))
            vals[4] = alarm_cell(it.ticker)
            tree.item(it.ticker, values=vals)
        write_log('counts reset — every threshold re-armed')

    btn_run.config(command=toggle_run)
    btn_mute.config(command=toggle_mute)
    btn_reset.config(command=do_reset)

    def on_close():
        worker.stop()
        speaker.stop()
        feed.close()
        root.destroy()

    root.protocol('WM_DELETE_WINDOW', on_close)
    write_log(f'watching {len(items)} names via {feed.name} — press Start')
    root.after(GUI_DRAIN_MS, drain)
    toggle_run()                      # start polling as soon as it opens
    return root


def run_console(items, engine, speaker, feed):
    """No-window fallback: same loop, printed one fact per line."""
    out_q = queue.Queue()
    worker = PollWorker(feed, engine, speaker, out_q,
                        [it.ticker for it in items])
    worker.start()
    print('running — ctrl-C to stop')
    try:
        while True:
            msg = out_q.get()
            if msg[0] == 'tick':
                for text in msg[2]:
                    print(f'{datetime.now():%H:%M:%S}  {text}')
            elif msg[0] == 'error':
                print(f'{datetime.now():%H:%M:%S}  !! {msg[1]}')
            else:
                print(f'{datetime.now():%H:%M:%S}  {msg[1]}')
    except KeyboardInterrupt:
        worker.stop()
        speaker.stop()
        feed.close()
        print('stopped')


# -------------------------------------------------------------------- MAIN ---
def main(argv=None):
    ap = argparse.ArgumentParser(description='Speak an alarm when a stock '
                                             'crosses a % threshold.')
    ap.add_argument('--watchlist', default=os.path.join(HERE, WATCHLIST_CSV),
                    help='watchlist CSV (default: watchlist.csv next to this file)')
    ap.add_argument('--demo', action='store_true',
                    help='fake prices instead of Bloomberg — to hear it work')
    ap.add_argument('--no-gui', action='store_true',
                    help='print to the console instead of opening a window')
    args = ap.parse_args(argv)

    print(f'price alarm — {platform.system()}, python {sys.version.split()[0]}')

    # First run on a new machine: write the sample list rather than refusing to
    # start over a missing file the user has never seen.
    if not os.path.exists(args.watchlist):
        try:
            with open(args.watchlist, 'w', encoding='utf-8') as fh:
                fh.write(SAMPLE_WATCHLIST)
            print(f'created a starter watchlist: {args.watchlist}')
            print('edit it in Excel or Notepad to put your own names in')
        except OSError as exc:
            print(f'cannot create {args.watchlist}: {exc}')
            return 2

    try:
        items = load_watchlist(args.watchlist)
    except (OSError, ValueError) as exc:
        print(f'watchlist problem: {exc}')
        return 2

    print(f'watchlist: {args.watchlist}')
    for it in items:
        thr = ', '.join(f'{t:+g}%' for t in it.thresholds)
        print(f'  {it.ticker:<20} {it.nickname:<14} {thr}   '
              f'max {it.max_repeats}/threshold/day')
    engine = AlarmEngine(items)
    speaker = Speaker(on_log=lambda m: print(m))
    feed = (FakeFeed([it.ticker for it in items]) if args.demo
            else BloombergFeed())
    print(f'poll every {getattr(feed, "poll_seconds", POLL_SECONDS)}s, '
          f're-arm buffer {REARM_BUFFER_PCT}%, source {feed.name}')

    if args.no_gui:
        run_console(items, engine, speaker, feed)
        return 0
    try:
        root = build_gui(items, engine, speaker, feed)
    except Exception as exc:
        print(f'no window available ({exc}) — falling back to the console')
        run_console(items, engine, speaker, feed)
        return 0
    root.mainloop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
