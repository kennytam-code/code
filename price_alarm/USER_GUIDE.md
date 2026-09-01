# Price Alarm — user guide

Watches the names you choose and **says out loud** when one moves through a
level you set:

> "Tencent is trading at 612.50, up 3.1 percent"

Works both ways — a `-3` threshold speaks on the way down.

There are two versions of the same tool. Use whichever suits you; they follow
identical rules, so they speak at the same moments.

| Version | For | Needs |
|---|---|---|
| `price_alarm.py` + `START_PRICE_ALARM.bat` | you | the Python that runs the desk notebooks (has blpapi) |
| `PriceAlarmVBA.bas` | anyone who lives in Excel | Excel + the Bloomberg add-in, no Python |

Both only work on a PC where the **Bloomberg Terminal is running and logged
in** — that is where live prices come from.

---

# What to copy to the terminal PC

Copy the **`price_alarm` folder**. That is it. Three files matter:

```
price_alarm/
    price_alarm.py           the app
    START_PRICE_ALARM.bat    double-click this
    PriceAlarmVBA.bas        the Excel version (only if your colleague wants it)
    USER_GUIDE.md            this file
```

The `tests` folder is for checking the logic on any machine. You never need it
on the terminal PC — leave it behind if you like.

You do **not** need a watchlist file. The app writes a starter one the first
time it runs.

---

# Version 1 — the app (recommended)

## Starting it

Double-click **START_PRICE_ALARM.bat**.

A window opens listing your names with live price, day move, and how many times
each alarm has spoken. It starts watching straight away.

| Button | |
|---|---|
| **Stop** | pauses the watching |
| **Mute** | keeps the log, silences the voice |
| **Reset counts** | re-arms every level, as if the day just started |

First time on a new machine, it creates **watchlist.csv** next to itself and
tells you so.

## Choosing your names

Open **watchlist.csv** in Excel or Notepad:

```
Ticker,NickName,Thresholds,MaxRepeats
700 HK Equity,Tencent,3;5;-3;-5,
2330 TT Equity,TSMC,3;-3,2
NVDA US Equity,Nvidia,5;-5,1
```

- **Ticker** — exactly as you would type it into BDP.
- **NickName** — what the voice calls it. Leave blank and it says "700 HK".
- **Thresholds** — day move in percent, semicolons between, minus for
  downside. `3;5;-3;-5` watches +3, +5, −3 and −5.
- **MaxRepeats** — how many times *each* level may speak that day. Blank means
  the default of 2. This is the per-name control you asked for: hold a jumpy
  name to 1, give a name you care about 5.

Save the file and restart the app to pick up changes.

If a row is wrong the app stops and names the row, rather than starting up half
configured.

## Checking it works before the open

```
python price_alarm.py --demo
```

Invents prices and really does speak, so you can confirm the voice works with
no market and no terminal. It trips a level within about fifteen seconds.

Other ways to run it, from a prompt in the folder:

```
python price_alarm.py                    normal
python price_alarm.py --no-gui           no window, prints to the console
python price_alarm.py --watchlist X.csv  a different list
```

---

# Version 2 — the Excel one

Set-up is one time, about five minutes. You only need `PriceAlarmVBA.bas`.

1. Open Excel, **new blank workbook**.
2. Press `Alt` + `F11` for the VBA editor.
3. **File → Import File…**, choose `PriceAlarmVBA.bas`, Open.
4. Press `Alt` + `F8`, choose **Setup**, Run.

That builds the Watchlist, Config and Log sheets, writes the BDP formulas, and
puts the four buttons on the sheet.

5. A message tells you to paste this into **ThisWorkbook** (double-click
   `ThisWorkbook` in the VBA editor's left panel):

```vba
Private Sub Workbook_BeforeClose(Cancel As Boolean)
    StopAlarm
End Sub
```

   Do not skip it. The alarm schedules itself with a timer, and a timer left
   running will re-open the workbook by itself hours later.

6. **File → Save As**, type **Excel Macro-Enabled Workbook (\*.xlsm)**. Saving
   as `.xlsx` silently throws the macros away.

Then type your tickers into the blue columns — same four columns as above — and
press **Start**.

No Developer tab or `Alt`+`F8` not working? **File → Options → Customize
Ribbon**, tick **Developer**.

Every time you open it afterwards, click **Enable Content** on the yellow bar,
or nothing runs.

Settings live on the **Config** sheet; everything spoken is written to the
**Log** sheet.

## Checking the Excel one

Press `Alt` + `F8`, run **SelfTest**. It checks the alarm rules in five seconds
and reports "all checks pass". That is the same set of cases the Python tests
run, so a pass means both versions behave the same.

Then a live check: put one liquid name on the sheet with a tiny threshold like
`0.1` and press Start.

---

# How it decides when to speak

A level fires the moment the move reaches it, then goes quiet. It will not
speak again until the price **pulls back past that level by 0.25%** — the
re-arm buffer. That is the difference between a name that genuinely crossed +3
twice and a name sitting at +3.00 with a flickering quote.

On a +3 alarm:

| | |
|---|---|
| `+2.8` → `+3.1` | **speaks** |
| holds at `+3.4` | silent — already counted |
| `+2.9` → `+3.2` | silent — never really left the level |
| `+2.5` → `+3.2` | **speaks again** — a real round trip |

…and it will only do that as many times as **MaxRepeats** allows that day.

Also worth knowing:

- If a name is **already** through a level when you start, it speaks once.
  Starting at +4% with a +3 alarm set is information, not noise.
- One jump through two levels (flat to +5.5, with +3 and +5 set) speaks once
  and uses up both. The sentence quotes the real move anyway.
- Counts reset by themselves when the date changes.
- Everything spoken is logged, muted or not.

To change the buffer, how often it checks, or the default cap: in the app, the
CONFIG block at the top of `price_alarm.py`; in Excel, the **Config** sheet.
Setting the buffer to 0 makes a name resting on the level chatter — that is why
it is not 0.

---

# If something goes wrong

**"blpapi is not installed in this Python"** — start it from the environment
the desk notebooks run in, the one with the Bloomberg API. Open that prompt,
change to this folder, and run `python price_alarm.py`.

**"cannot start a Bloomberg session"** — the Terminal is not running or not
logged in on that machine.

**"No Python found on the PATH"** from the .bat — same thing: use the Anaconda
prompt, or whichever prompt you launch Jupyter from.

**A name shows "no data (check ticker)"** — usually a typo. The other names
keep running.

**Everything sits at "waiting for first print"** — before the open there is no
day move to measure. Nothing fires; nothing is broken.

**It goes quiet after a while** — if the connection drops it reconnects on its
own, backing off 5, 10, 20, 30 then 60 seconds, and says so in the log. Your
counts survive a reconnect.

**No sound** — check Mute, then Windows volume. The voice is whichever
text-to-speech voice Windows is set to.

Watching a US name overnight from Asia crosses local midnight, which resets the
counts mid-session. Press **Reset counts** if you would rather pick the moment
yourself.

---

# For whoever maintains this

```
python3 tests/test_engine.py
python3 tests/test_watchlist.py
```

27 checks on the crossing rules and the watchlist validation. No Bloomberg, no
sound, no window needed — they run on any machine. Run them after touching the
threshold logic, and run the Excel `SelfTest` after touching `CheckOne`, so the
two versions cannot drift apart.
