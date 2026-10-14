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

MARKET TABS (14 October 2026)
  IPO Live: 715 seven-year monitoring listings. B4 selects Stored/Bloomberg.
  Stored quotes: 14 October 2026; unavailable or stale daily quotes
  do not enter sector means. Bloomberg uses LAST_PRICE / PX_YEST_CLOSE.
  B5 selects Sector/Subsector; H34 chooses the
  sector for the subsector-average chart.
  AH: E4 selects Stored / Bloomberg. Stored opens through 2 October;
  Bloomberg requests current quotes and history through TODAY.
  70 A/H pairs, including LONGSYS 9976 / 301308. Database/Screener: 525.
  G/H show seven-day / calendar-month premium changes in percentage points.
  The selected Excel chart combines premium (left) with A-share and CSI 300
  price returns (right). Reference history starts before the H listing.
  Compare four pairs in Excel. HTML has multiple selection, Select all,
  preset horizons and custom dates, with the six-panel A/H format.
  Verified share actions are adjusted; genuine missing prices stay absent.
  Lock-up: B4/E4 select the event. IPO date, cornerstone %, since-IPO
  return, deal size and +/-30 HK trading sessions are together in one row.
  Compared codes: B10/E10/H10/K10. Expiry date range: B11/E11.
  Peer Trades: B3 selects a named direct product peer pair. F3 selects
  Stored/Bloomberg; H3 selects 1M/3M/6M/1Y/3Y/5Y/Max/Custom.
  F4/H4 set custom dates. Both company summaries and their charts appear
  beside each other. 35 pairs / 66 saved stocks, including non-IPO peers.
  Actual common coverage is shown; spread is A minus B return in pp.
  Live TTM PE/PS: direct PE_RATIO / PX_TO_SALES_RATIO, with BQL fallback.
  Database fundamentals BM:BO and Screener BH:BJ show live NTM P/E,
  FY2027 P/E and FY2027 P/S using the supplied BQL expressions.
  BQL replies are read by requested field, excluding date/period metadata.
  Unavailable is a missing live reply, never a substituted IPO multiple.
  Live Bloomberg execution requires the terminal add-in; this Mac checks
  formula logic with fixtures; the delivered workbook was also opened
  and visually inspected in native Excel without a repair prompt.
  Refresh updates the Live snapshot, A/H, peer and benchmark data and
  preserves lock-up
  windows. Then build regenerates Excel and the offline HTML snapshot.

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
