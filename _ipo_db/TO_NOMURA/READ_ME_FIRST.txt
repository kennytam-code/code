HK IPO DATABASE
===============

PUT THESE FILES IN:  G:\FIN_COMM\DeltaOne\Kenny\ECM\

THE FILES
  HK_IPO_Database_v1.xlsx   the workbook — IPO Live, AH trend and Screener
  hk_ipo_dashboard.html     the charts — double-click, works offline
  hk_ipo.py                 updates everything (Jupyter, one command)
  ah_peers.ipynb            A/H price charts live off Bloomberg
  AH_Premium_Study.docx     updated 62-pair A/H study (6 October)
  Grey_Market_vs_Day1.docx  the grey market against day 1, every deal
  Clawback_Study.docx       the 套路回撥 allocation study
  READ_ME_FIRST.txt         this file

MARKET TABS (7 October 2026)
  IPO Live: all 524 IPOs; live LAST_PRICE and change vs PX_YEST_CLOSE.
  B5 selects Sector/Subsector classification; H34 chooses the sector
  for the second, subsector-average chart. The first chart stays broad.
  AH: 62 pairs only. B4 accepts H/A code; E4 selects Stored/Bloomberg.
  Stored is the default, through 2 October. Bloomberg requests history
  from listing through TODAY and appends an available live endpoint.
  Lock-up: original filed expiry schedules for all 524 stocks;
  returns use seven HK trading sessions before and after expiry.
  HTML Lock-up selects a company and holder-group event to chart
  every session from day -7 to +7, rebased to the expiry reference.
  Prices through 2 October 2026. Future and
  missing returns stay blank; hover dates for sources and endpoints.
  Screener freezes columns A:B, with no frozen rows.
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
  Bloomberg supersedes scrapes; reviewed HKEX figures take priority.

THE DASHBOARD
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
