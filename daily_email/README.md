# Daily calendar email

Two Outlook drafts every morning, straight from Bloomberg, no Excel in the loop.
Run from Jupyter.

| Draft | What is in it |
| --- | --- |
| **Macro calendar** | Central-bank decisions across the US, Taiwan, Korea, Malaysia, Thailand, Indonesia, India, China, Japan and Australia, then the high-relevance US data calendar. Next three months, your 30-name exclusion list applied. |
| **HSI earnings** | Hang Seng constituents reporting inside 91 days, with the conference-call date and time. |

Addressed to Oscar Chan and Gordon Ho, grouped by day, today highlighted.
Nothing is ever sent. Both land in Drafts and you press Send.

Two files, and that is the whole thing:

- **`daily_email.py`** — the script, with its own tests and a fake Bloomberg
  terminal inside it
- **`README.md`** — this guide

---

## The only cell you need to remember

Put the notebook in the same folder as the script, then in the first cell:

```python
%run daily_email.py
```

It prints a short menu and does nothing else. In the next cell, call one of six
functions:

```python
demo()                          # both emails from sample data, no Bloomberg
test()                          # run the self-tests
probe()                         # check fields and tickers on the terminal
run()                           # the real thing: two Outlook drafts
run(excel='C:/path/cal.xlsx')   # from the workbook instead
compare('C:/path/cal.xlsx')     # Bloomberg against the workbook
```

The emails are drawn **inside the notebook**, under the subject line and the
recipients, so you can read them before anything reaches Outlook. Copies are also
saved to the `out` folder.

If your notebook lives somewhere else, point at the folder first:

```python
import sys; sys.path.insert(0, r'C:\path\to\daily_email')
from daily_email import *
```

**None of the six will ever throw a red traceback.** If Bloomberg is not
reachable, or a path is wrong, or a library is missing, you get a sentence
telling you what to do next and the kernel keeps running.

---

## Start here: `demo()`

You do not need Bloomberg or Outlook to see what the emails look like.

```python
demo()
```

Sample data, both emails drawn in the notebook, nothing touched. Run it now.

Then check the logic holds:

```python
test()
```

About ninety checks over date parsing, the exclusion list, sort order, dead
tickers, rejected fields, the Excel reader and the HTML. It ends with
`all tests passed`.

Both of these work on any machine, including one with no Bloomberg at all.

---

## On the Bloomberg PC: `probe()` first

Start the notebook from the kernel that has `blpapi` — the same one the desk
notebooks use. Then:

```python
probe()
```

**Do this before you trust a single number.** Here is why.

Your Excel formulas use BQL, and **BQL cannot be called from Python.**
`calendar()`, `members()` and `btoday()` run only in the Excel add-in and in
BQuant. The Bloomberg API that Python talks to has no BQL service. So the script
does not port your query. It rebuilds the same output from ordinary Bloomberg
fields, the kind behind `=BDP()`.

That rebuild depends on field names and ticker symbols being right, and **a wrong
field name does not raise an error.** It quietly returns "invalid field" as if it
were data, and it would sit in the email looking like a number. The probe is what
catches that. It:

- checks every field and every ticker against your live terminal;
- prints Bloomberg's own name beside each ticker, so a mislabelled row is obvious;
- searches for the correct field name whenever one is rejected;
- searches for a replacement symbol whenever a ticker is rejected;
- tells you whether release times arrive in New York or Hong Kong time.

It writes `out/probe_YYYY-MM-DD.txt`. **Send me that file** and I will fix
whatever it flags. Three central-bank tickers are already flagged `VERIFY` in the
script, because I could not confirm them without a terminal.

---

## Then, every morning

```python
run()
```

Two drafts appear in Outlook's Drafts folder with your signature underneath, and
they are drawn in the notebook so you can read them first. Copies land in `out`
as `.html` and `.eml`.

Useful variations:

```python
run(display=True)     # pop the drafts open on screen instead of saving them
run(outlook=False)    # build and show them, do not touch Outlook at all
```

---

## If you would rather not trust the API yet

Keep the workbook as the data source and let Python do the filtering, formatting
and drafting. Same two emails, exactly the numbers Excel already shows you, no
field-name risk at all:

```python
run(excel='C:/path/to/your/calendar.xlsx')
```

Open and refresh the workbook first, so the BQL values are saved inside it.
Forward slashes work fine in the path.

When you want to see whether the API agrees before switching to it:

```python
compare('C:/path/to/your/calendar.xlsx')
```

That prints a row-by-row diff: what Bloomberg found, what the workbook found, and
anything only one of them has.

---

## Changing things

Everything you would want to change sits in one block at the top of
`daily_email.py`, between the lines marked `CONFIG` and `END CONFIG`. Nothing
below that needs touching. After an edit, re-run the `%run daily_email.py` cell.

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
reading the code settles it. That is what `probe()` is for. One run, one file
sent back, one correction pass.

Dates that came from the backup earnings field are marked `est.` in the email,
and the footer says how many. Anything the script could not fetch is named in
that footer rather than left silently blank.

---

## If you ever want it outside Jupyter

The same script runs from a command prompt, and
`python daily_email.py --make-launcher` writes a `.bat` you can double-click.
`--demo`, `--test`, `--probe`, `--excel` and `--parity` mirror the six functions
above. You do not need any of this if you work in the notebook.
