# Daily calendar email

Two Outlook drafts, straight from Bloomberg, no Excel in the loop:

1. **Macro calendar** — central-bank decisions (US, TW, KR, MY, TH, ID, IN, CN, JP, AU) then
   the high-relevance US data calendar, both for the next three months, with your 30-name
   exclusion list applied.
2. **HSI earnings** — index constituents reporting inside 91 days, with the conference-call
   date and time.

Addressed to Oscar Chan and Gordon Ho, grouped by day, today's row highlighted.

```
RUN_DAILY_EMAIL.bat                 double-click on the terminal PC
python daily_email.py               two drafts saved to Outlook's Drafts folder
python daily_email.py --display     drafts pop open for review instead
python daily_email.py --probe       FIRST RUN — verify every field and ticker
```

---

## Can this really be migrated? Honest answer

**The BQL strings cannot be sent through the Bloomberg API.** `calendar()`, `members()`,
`filter()` and `btoday()` are BQL, and BQL runs in two places: the Excel add-in (the
`=@BQL()` formula you use today) and BQuant. The Desktop API that Python talks to
(`blpapi`, port 8194) exposes `//blp/refdata`, `//blp/mktdata` and friends — there is no
BQL service. A one-for-one port of those three formulas does not exist.

What *does* exist is the request/response snapshot behind `=BDP()`, and everything the two
emails need can be rebuilt from it. So the script replicates the **output**, not the query.

| Piece | How it is rebuilt | Confidence |
| --- | --- | --- |
| HSI constituent list | `INDX_MEMBERS` on `HSI Index` | **High.** Standard bulk field, unambiguous. |
| Expected report date/time | `EXPECTED_REPORT_DT`, `EXPECTED_REPORT_TIME` per member | **High.** Same fields your BQL asks for, and BQL's `expected_report_dt` is this field. The 91-day filter moves from BQL into Python. |
| Conference call | `EARNINGS_CONF_CALL_DT` / `_TIME` | **Medium-high.** Field names taken from your own BQL. Verified by `--probe`. |
| Central-bank decisions | Next release date on each policy-rate ticker | **Medium.** The mechanism is sound; three tickers are marked VERIFY in the config because I could not confirm them off-terminal. `--probe` checks each and searches for the right symbol when one is rejected. |
| US data calendar | Next release date, survey and prior on ~78 release tickers | **Medium.** This is the real substitution: BQL enumerates the calendar for you, the API cannot, so the universe is a list in the script. Everything `relevancy=HIGH` normally returns is in it, and `--probe` prints Bloomberg's own name beside each so a wrong ticker is obvious. |
| Exclusion list | Your 30 VBA entries, verbatim, matched case- and space-insensitively | **High.** Tested. |
| Formatting and Outlook drafts | Inline-styled HTML, Outlook COM | **High.** No Bloomberg dependency. |

**The honest summary:** the plumbing and the formatting are solid and tested — the same
session pattern as `price_alarm.py`, which runs on your terminal today. The uncertainty is
entirely in *mnemonics and ticker symbols*, which no amount of code review settles. That is
what `--probe` is for. Run it once, send me the output, and every rejected field or ticker
gets corrected in one pass.

**If you want zero risk on day one**, use `--source excel`: keep the workbook as the data
source, let Python do the filtering, formatting and drafting. Same two emails, guaranteed
identical numbers, no mnemonic risk. `--parity` then diffs the API path against the workbook
row by row, so you can watch the API path agree before you switch to it.

---

## First run, on the terminal PC

```
python daily_email.py --probe
```

Checks every field mnemonic and every ticker against the live terminal and writes a report
to `out/probe_YYYY-MM-DD.txt`. It also:

- prints Bloomberg's own `NAME` beside each ticker, so a mislabelled row stands out;
- runs a field search (FLDS from Python) for each thing we need, so a wrong mnemonic comes
  back with the right one beside it;
- searches for a replacement symbol when a central-bank ticker is rejected;
- tells you whether release times arrive in New York or Hong Kong time — the one setting
  (`TIME_IN_LOCAL_TZ`) you may need to flip;
- opens `//blp/bqlsvc` and prints its schema, on the off chance your install exposes BQL to
  the API after all. It normally does not, and the script does not depend on it.

Send me that file and I will correct the config.

## Every day after that

```
RUN_DAILY_EMAIL.bat
```

Both drafts are saved to Drafts with your Outlook signature underneath, and a copy of each
lands in `out/` as `.html` and `.eml`. Nothing is ever sent — you press Send.

## Options

| Flag | Effect |
| --- | --- |
| `--display` | Open both drafts on screen instead of saving them |
| `--no-outlook` | Write the `.html` / `.eml` files only, no Outlook |
| `--probe` | Verify fields and tickers against the terminal |
| `--source excel --xlsx PATH` | Read the workbook's cached BQL output instead of the API |
| `--parity --xlsx PATH` | Diff the API path against the workbook, row by row |
| `--source bql` | Run the three BQL strings verbatim — inside BQuant only |
| `--source fixture` | Sample data, works on any machine, for checking the layout |
| `--asof YYYY-MM-DD` | Pretend it is another day |

## Configuring

Everything you would change is in the CONFIG block at the top of `daily_email.py`:
recipients, greeting, the two subject lines, the 91-day horizon, the exclusion list, the US
release universe, the central banks, and `TIME_IN_LOCAL_TZ`. To drop an event, delete its
row from `US_ECO_TICKERS` or add its name to `EXCLUDE_EVENTS` — both work.

## Install

```
pip install blpapi --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/
pip install pywin32 openpyxl
```

`blpapi` for the API path, `pywin32` for Outlook drafts, `openpyxl` only for `--source
excel`. Run it from the same Python the desk notebooks use — that one already has `blpapi`.

## Tests

```
python tests/test_daily_email.py
```

80-odd checks over date and time parsing (including Excel serials and fractions), the
exclusion list, sorting, chunked requests, dead tickers, rejected mnemonics, the Excel
reader, HTML escaping and the `.eml` output. A fake `blpapi` stands in for the terminal, so
this runs on any machine.
