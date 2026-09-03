# Daily calendar email

Two Outlook drafts every morning, straight from Bloomberg, no Excel in the loop.

| Draft | What is in it |
| --- | --- |
| **Macro calendar** | Central-bank decisions across the US, Taiwan, Korea, Malaysia, Thailand, Indonesia, India, China, Japan and Australia, then the high-relevance US data calendar. Next three months, your 30-name exclusion list applied. |
| **HSI earnings** | Hang Seng constituents reporting inside 91 days, with the conference-call date and time. |

Addressed to Oscar Chan and Gordon Ho, grouped by day, today highlighted.
Nothing is ever sent. Both land in Drafts and you press Send.

There are two files here and that is the whole thing:

- **`daily_email.py`** — the script. Also contains its own test suite and a fake
  Bloomberg terminal, so it runs on any machine.
- **`README.md`** — this guide.

---

## Try it right now, on any machine

You do not need Bloomberg or Outlook to see what the emails look like.

```
python daily_email.py --demo
```

That writes both emails to `out/` using sample data. Open the `.html` files in a
browser. Nothing touches Bloomberg, nothing touches Outlook.

To check the logic is sound:

```
python daily_email.py --test
```

About ninety checks over date parsing, the exclusion list, sort order, dead
tickers, rejected fields, the Excel reader and the HTML. It should end with
`all tests passed`.

---

## Setting it up on the Bloomberg PC

**1. Use the Python the desk notebooks run on.** That one already has `blpapi`.
Open the prompt you launch Jupyter from. If you ever need to install things:

```
pip install blpapi --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/
pip install pywin32 openpyxl
```

`blpapi` talks to Bloomberg, `pywin32` creates the Outlook drafts, `openpyxl` is
only needed for the workbook option further down.

**2. Run the probe. Do this before you trust a single number.**

```
python daily_email.py --probe
```

This is the important step, and here is why. Your Excel formulas use BQL, and
**BQL cannot be called from Python.** `calendar()`, `members()` and `btoday()`
run only in the Excel add-in and in BQuant; the Bloomberg API that Python talks
to has no BQL service. So the script does not port your query, it rebuilds the
same output from ordinary Bloomberg fields, the kind behind `=BDP()`.

That rebuild depends on field names and ticker symbols being right, and a wrong
field name does not raise an error. It quietly returns "invalid field" as if it
were data. The probe is what catches that. It:

- checks every field and every ticker against your live terminal;
- prints Bloomberg's own name beside each ticker, so a mislabelled row is obvious;
- searches for the correct field name whenever one is rejected;
- searches for a replacement symbol whenever a ticker is rejected;
- tells you whether release times arrive in New York or Hong Kong time.

It writes `out/probe_YYYY-MM-DD.txt`. **Send me that file** and I will fix
whatever it flags. Three central-bank tickers are flagged `VERIFY` in the script
already, because I could not confirm them without a terminal.

**3. Run it for real.**

```
python daily_email.py
```

Two drafts appear in Outlook's Drafts folder with your signature underneath, and
copies land in `out/` as `.html` and `.eml`.

Want a double-click icon instead of typing the command? Run
`python daily_email.py --make-launcher` once. It writes `RUN_DAILY_EMAIL.bat`
next to the script.

---

## If you would rather not trust the API yet

Keep the workbook as the data source and let Python do the filtering, formatting
and drafting. Same two emails, exactly the numbers Excel already shows you, no
field-name risk at all:

```
python daily_email.py --excel --xlsx "C:\path\to\your\calendar.xlsx"
```

Open and refresh the workbook first so the BQL values are saved in it.

And when you want to see whether the API path agrees before switching to it:

```
python daily_email.py --parity --xlsx "C:\path\to\your\calendar.xlsx"
```

That prints a row-by-row diff: what the API found, what the workbook found, and
anything only one of them has.

---

## Every command

| Command | What it does |
| --- | --- |
| `python daily_email.py` | The real thing. Two drafts into Outlook. |
| `python daily_email.py --demo` | Sample data, no Bloomberg, no Outlook. |
| `python daily_email.py --test` | Run the self-tests. |
| `python daily_email.py --probe` | Verify every field and ticker on the terminal. |
| `python daily_email.py --display` | Pop the drafts open instead of saving them. |
| `python daily_email.py --no-outlook` | Write the files only. |
| `python daily_email.py --excel --xlsx PATH` | Read the workbook instead of the API. |
| `python daily_email.py --parity --xlsx PATH` | Diff the API against the workbook. |
| `python daily_email.py --bql` | Run your BQL strings verbatim. BQuant only. |
| `python daily_email.py --make-launcher` | Write the double-click `.bat`. |
| `python daily_email.py --asof 2026-10-01` | Pretend it is another day. |

---

## Changing things

Everything you would want to change sits in one block at the top of
`daily_email.py`, between the lines marked `CONFIG` and `END CONFIG`. Nothing
below that needs touching.

| To change | Edit |
| --- | --- |
| Who gets the emails | `RECIPIENTS` |
| The greeting line | `GREETING` |
| Subject lines and the intro paragraph | `EMAILS` |
| How far ahead to look | `LOOKAHEAD_DAYS` |
| Events you do not care about | `EXCLUDE_EVENTS`, your 30 VBA names, carried over word for word |
| Which US releases to track | `US_ECO_TICKERS` |
| Which central banks | `CENTRAL_BANKS` |
| New York times showing instead of Hong Kong | `TIME_IN_LOCAL_TZ` |

To drop a release you can either delete its row from `US_ECO_TICKERS` or add its
name to `EXCLUDE_EVENTS`. Both work.

---

## How much of this can I trust?

| Piece | How confident |
| --- | --- |
| Formatting, filtering, Outlook drafts | **High.** Tested, and none of it depends on Bloomberg. |
| HSI member list, expected report dates | **High.** Standard fields. The backup field is one your ADR-basket script already uses in production. |
| Conference-call fields | **Medium-high.** Names taken from your own BQL formula. |
| Central-bank tickers | **Medium.** The method is sound. Three symbols are unconfirmed and flagged in the script. |
| US release list | **Medium.** BQL enumerates the calendar for you and the API cannot, so the list of about 78 releases lives in the script. That is the piece most likely to have a gap. |

The uncertainty is entirely in field names and ticker symbols, and no amount of
reading the code settles it. That is what `--probe` is for. One run, one file
sent back, one correction pass.

Dates that came from the backup earnings field are marked `est.` in the email,
and the footer says how many. Anything the script could not fetch is named in
that footer rather than left silently blank.
