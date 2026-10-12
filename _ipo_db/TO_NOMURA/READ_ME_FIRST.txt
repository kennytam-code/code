HK IPO DATABASE
===============

PUT THESE FILES IN:  G:\FIN_COMM\DeltaOne\Kenny\ECM\

THE FILES
  HK_IPO_Database_v1.xlsx   the workbook — IPO Live, AH trend and Screener
  hk_ipo_dashboard.html     the charts — double-click, works offline
  hk_ipo_dashboard.zip      smaller transfer copy; extract before opening
  hk_ipo.py                 updates everything (Jupyter, one command)
  ah_peers.ipynb            A/H price charts live off Bloomberg
  AH_Premium_Study.docx     updated 62-pair A/H study (6 October)
  Grey_Market_vs_Day1.docx  the grey market against day 1, every deal
  Clawback_Study.docx       the 套路回撥 allocation study
  READ_ME_FIRST.txt         this file

MARKET TABS (12 October 2026)
  IPO Live: 714 seven-year monitoring listings; live LAST_PRICE and change vs PX_YEST_CLOSE.
  B5 selects Sector/Subsector classification; H34 chooses the sector
  for the second, subsector-average chart. The first chart stays broad.
  AH: 68 pairs in the seven-year monitoring roster. B4 accepts H/A code; E4 selects Stored/Bloomberg.
  Stored is the default, through 2 October. Bloomberg requests history
  from listing through TODAY and appends an available live endpoint.
  AH includes the 62 database pairs and six 2019/2020 H listings.
  Huaqin (3296): IPO/current premiums are available; the trend omits
  22 May to 16 June while A/H ex-entitlement bases differ.
  AH G/H: 7-day / one-calendar-month premium changes, percentage points.
  Compare up to four pairs in Excel; select multiple pairs in HTML.
  Peer Trades: six direct-product pairs, live quotes and performance spread.
  Lock-up: 396 cornerstone events for 386 stocks; no-cornerstone
  entries and unrelated shareholder restrictions are excluded.
  returns use 30 HK trading sessions before and after expiry.
  Excel: B4 selects H code; E4 selects expiry event, with Auto default.
  Both files show the IPO date and a selectable day -30 to +30 graph.
  HTML Lock-up searches H code/company and selects an expiry event to chart
  every session from day -30 to +30, rebased to the expiry reference.
  Prices through 2 October 2026. Future and
  missing returns stay blank; hover dates for sources and endpoints.
  Expiry unconfirmed means the retained filing does not establish a date;
  that event has no inferred expiry, return or chart.
  Company cornerstones shows the full company roster; individual
  expiry events may apply to a subset, as shown in the linked filing.
  Screener freezes columns A:B, with no frozen rows.
  Screener B5 accepts the H code, e.g. 9607 = RA MATERIALS / Red Avenue.
  Cornerstones search 9607 shows all eight investors even if the
  minimum-deals filter was set above one. MLP resolves to Millennium.
  Pipeline: key terms first; expand M:AD in Excel or a company in HTML.
  Financial/source audit: see database_numeric_audit.md and CSV.
  Orange annual financial cells need fresh primary-row confirmation.
  Bloomberg formula logic is tested; live add-in execution is a desk check.

RETURN METHODS / REVIEW (4 October 2026)
  1w/1m/3m = 5/21/63 traded sessions after debut, not calendar dates.
  Benchmark index Day-1 = sector index return from previous close to
  listing close; the index named on each deal is used. Prices as of
  shows the actual last traded date, including suspended stocks.
  Other Word studies and weekly email are 3 October carryovers; they were
  not regenerated with the expanded grey-market sample.

TO JUST USE IT
  Open the .xlsx -> SCREENER tab. Pick a deal from the dropdown, or
  type your own terms in the TYPE TO OVERRIDE column — comps re-rank
  as you type. The comp table carries EVERY Database column (terms,
  demand, all returns incl. ex-pop, A-premium at IPO and today,
  HSAHP at IPO, banks, cornerstone) plus the score and why.
  Rank modes: standard (subsector first) / cornerstone overlap first /
  demand-similar first. A-share filter screens A+H or non-A only.

  Sign conventions: A-premium = A over H - 1 (+ = A trades ABOVE H).
  Ex-pop columns (teal) start at the day-1 CLOSE; the charts' ex-pop
  panels rebase at the day-1 OPEN — the first tradeable print.

TO UPDATE IT (Jupyter, ONE command)
  To reproduce this delivery exactly, run hk_ipo.py in a clean folder.
  An existing persistent data folder is retained for your own updates.
  %run hk_ipo.py update      <- fetch + parse + prices + gates +
                                rebuild, ends with a VERDICT block
  %run hk_ipo.py update --skip aastocks   <- if a site is blocked
  %run hk_ipo.py status      <- what is in the database now
  A stage that fails keeps its previous data — the files stay usable;
  they just do not gain that stage's update.

BLOOMBERG (terminal only)
  The BBG Verify tab fills itself on the terminal (CP036/CP037 subs,
  shoe, P/E at listing, A-share P/E at H-IPO, HSAHP Index at IPO —
  verify one HSAHP cell before trusting that column, it is new).
  To feed the numbers back: let the tab compute, paste-VALUES into
  bbg.xlsx (one sheet, headers on row 4), put it next to the repo,
  then on the build machine: python ipo_lib/ingest_bbg.py + update.
  Combined BBG Verify: subscriptions, shoe, valuation and price checks.
  Bloomberg supersedes scrapes; reviewed HKEX figures take priority.

THE DASHBOARD
  Copy the delivered HTML file directly. It embeds compressed data and
  opens offline with no companion folder. All stored histories remain.
  If the shared drive reports no space, try the ZIP transfer copy
  or open a local copy. Compression cannot clear a full server quota;
  the shared drive owner may need to free space. Browser-saved HTML
  was also checked to reopen offline. Quotes remain dated snapshots.

  Screener tab: pick or type a target, Deal Brief (base rate + worst
  peer = your downside), paint comps red/blue, factor strips, plot
  anything vs anything, daily price action for every comp (offer-
  rebased AND open-rebased), and the six A/H panes per pair incl.
  A-share month-before -> month-after. Hover any chart for the scan
  line with every series' value. It is a snapshot — it cannot reach
  Bloomberg; the live layer is the Excel BDP/BDH cells + the notebook.

  ah_peers.ipynb: run all cells, a form appears — type codes, draw.
  H rebased on the OFFER (100 = what subscribers paid).

IF PACKAGES ARE EVER MISSING
  pip install requests beautifulsoup4 lxml openpyxl pypdf yfinance
  (blocked network: add --trusted-host pypi.org --trusted-host files.pythonhosted.org)
