# Weekly "week ahead" desk email

One email, sent Friday evening or Monday morning, covering the coming week:
what prints, what reports, what gets launched, and what any of it means.

```
_weekly/
    weekly_email.py               the builder - stdlib only, runs anywhere
    data/week_YYYY-MM-DD.json     one file per week, this is what you edit
    out/week_ahead_YYYY-MM-DD.html    paste into Outlook
    out/week_ahead_YYYY-MM-DD.md      paste into Teams
```

Build it:

```
python3 weekly_email.py data/week_2026-09-07.json
```

Open the HTML, select all, paste into a new Outlook mail. The HTML is written
with tables and inline styles only, because Outlook renders mail through Word
and throws away `<style>` blocks, flexbox, grid, CSS variables and web fonts.
Nothing in that file is clever, on purpose.

---

## Can this be automated?

Mostly yes, and the part that can be automated is the part that takes the time.

Split the email into a **skeleton** and a **read**. The skeleton is every date,
time, ticker, consensus and prior. The read is the four sentences that say why
a reader should care. The skeleton is perhaps 70% of the hours and 0% of the
value. It is also entirely mechanical.

### The skeleton - a machine can build this

| Row in the email | Where it comes from | Status |
|---|---|---|
| Earnings dates, forward | `ERN_ANN_DT_AND_PER` bulk field | **Proven.** `v33_hk_basket_full.py` already pulls this and already handles the fact that it returns future estimated dates alongside history. |
| Consensus EPS / revenue | `BEST_EPS`, `BEST_SALES` with `BEST_FPERIOD_OVERRIDE` | Standard. Verify the override string on the terminal. |
| Economic release dates | ECO tickers, e.g. `CPI YOY Index`, `NFP TCH Index` | Verify the forward-date field name on the terminal before trusting it. |
| Consensus and prior for a release | survey median field on the ECO ticker, `PX_LAST` for prior | Same caveat. |
| Index events, HK IPO listing dates | `_ipo_db/` - we already own this data | **Proven.** |
| Monthly revenue dates (TSMC, Hon Hai) | fixed monthly cadence, roughly the 10th | Derivable, but the exact day is not published in advance. |

The Bloomberg field names above follow the pattern this repo already uses, but
only `ERN_ANN_DT_AND_PER` has actually been run in anger. Treat the rest the way
we treated the dividend-workbook mnemonics: **assume nothing until it has
returned a value on the terminal.** A bad mnemonic does not throw, it returns
`#N/A Invalid Field` as a value, and it will sit in an email looking like data.

So: one script on the terminal PC, same shape as `price_alarm.py`, pulling a
watchlist of tickers and ECO codes into `data/week_YYYY-MM-DD.json` with the
`calendar` array pre-filled. That is a realistic afternoon of work, and it is
the same blpapi session pattern already written twice in this repo.

### The read - a machine cannot build this, and should not

These fields stay hand-typed:

- `thesis` - the four lines at the top. This is the whole email.
- `why` on each calendar row. "US CPI, 08:30 ET" is a calendar. "Last inflation
  print before the Committee votes" is the email.
- `tier` - what moves the book this week. Tiering is a view, and it changes
  week to week for the same release.
- `focus` blocks and every `verdict`.
- Conferences, keynotes, product launches, political catalysts. Bloomberg has
  no field for "Jensen speaks at Goldman on Thursday". That comes off the press
  release, and it was one of the three biggest items of the week it appeared in.

### The honest verdict

Automate the skeleton, keep the read manual. Expect the weekly job to fall from
about three hours to about forty minutes, and expect the forty minutes to be
the part worth paying for. Do not automate end to end and send unread: the week
this note covers had two public sources disagreeing about whether the Fed's
next move was a cut or a hike, and an automated email would have printed one of
them as fact.

---

## Writing a new week

Copy the previous week's JSON, change the dates, then work through it:

1. `week_label`, `written`, `subject`.
2. `regime` - the standing state. Usually only one or two rows change.
3. `calendar` - one object per event. Fields:
   - `day` groups the rows, so keep the wording identical within a day.
   - `hkt` is what the reader scans. Local time goes in `local`.
   - `tier` 1 moves the book and prints in red, 2 is worth watching, 3 is noted.
   - `status` is `CONFIRMED` or `ESTIMATED`, and `src` says who said so.
     Anything estimated prints its status in red, so a guess cannot be mistaken
     for a fact at a glance.
   - Leave `cons` and `prior` as `"check ECO"` rather than filling them from a
     news article. A placeholder is honest. A stale consensus is not.
4. `focus` - two to four blocks. Each takes `steps` (a numbered deduction
   chain) or `bullets`, optionally a `table`, and always a `verdict`.
5. `beyond` - what is already being priced from further out.
6. `verify_before_send` - the terminal checklist. It prints at the foot of the
   email as a reminder, and it should be empty of surprises by the time you
   send.

Rules that keep the thing readable: one fact per line, HKT first because the
desk sits in Asia, and never a table without a verdict under it.
