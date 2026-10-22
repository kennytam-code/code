HK IPO DATABASE — 22 OCTOBER 2026

GITHUB DOWNLOADS — 22 OCTOBER RELEASE
  Excel: https://github.com/kennytam-code/code/raw/refs/heads/main/HK_IPO_Database_v1.xlsx
  HTML: https://github.com/kennytam-code/code/raw/refs/heads/main/hk_ipo_dashboard.html

Desk folder: G:\FIN_COMM\DeltaOne\Kenny\ECM\

OPEN
  HK_IPO_Database_v1.xlsx   Excel desk views
  hk_ipo_dashboard.html    Offline dashboard; no companion folder needed
  hk_ipo_dashboard.zip     Smaller transfer copy; extract before opening
  hk_ipo.py                Standalone updater
  Existing Word studies are separate dated research.

CONTROLS
  IPO Live — B4 Stored/Bloomberg; B5 Sector/Subsector; H34 broad sector
  for the subsector chart. 716 listings, 701 current 15-Oct quotes; 707 saved quotes in total.
  Green/red is change against the previous trading close. Missing/stale
  quotes and IPO-day offer-price references do not enter daily averages.

  AH — B4 H/A code; E4 Stored/Bloomberg. 71 pairs. J5 links to the
  sector table at J57. Premium is A price x CNYHKD / H price - 1;
  seven-day / one-month changes are percentage points. The chart combines
  premium with A-share and CSI 300 returns on separate axes. Bloomberg
  requests through TODAY; stored histories show their actual dates.
  Navy = premium (left axis); teal = A-share return (right axis);
  amber dashed = CSI 300 return (right axis). The 19 October update
  changes chart presentation only; all prices and formulas are preserved.
  Excel compares four pairs; HTML supports multiple selection, Select all,
  Select sector and preset/custom dates. Sector/subsector filters restrict
  the plotted selection. Stocks, Selected average and Sector averages are
  separate views; individual lines are paginated in groups of six.

  HTML AH — one full-width chart at a time. Use Chart to select Premium,
  Premium + CSI 300, around-IPO market context, HKD prices or performance.
  Premium and CSI share dates in separate upper/lower plots. Comparison
  lines have endpoint labels; click a legend to focus a line. HTML Screener
  also shows one selected analysis at a time.
  Premium changes use seven calendar days / one calendar month, in pp.

  Peer Trades — B3 named product-peer pair; F3 source; H3 horizon;
  F4/H4 custom dates. Both stocks populate automatically. 35 pairs / 66
  stocks. Spread is A minus B price return from their first common session.

  Screener — B5 H code / pipeline; E5 shows the resolved company.
  Type 9607, 09607, or a company name. First two columns are frozen.
  HTML Screener also offers code-first search.
  D7:D14 shows database inputs; F7:F14 accepts overrides. P7:P11 groups
  ranking, cornerstone, A-share, included-code and comparison-count filters.
  Selected-deal outputs sit on the right. Large tab title rows have been removed.
  Database B2: Selected / All / Off. Selected is the default and requests
  valuations only for the Screener company and displayed comparisons.
  All loads every database company; Off stops valuation requests.
  BBG Verify B2 defaults Off; use On only when running the verification.
  IPO Live, AH and Peer Trades retain separate Stored/Bloomberg switches.
  Database fundamentals contain live TTM PE/PS, NTM PE and FY2027 PE/PS;
  Screener mirrors them. Historical IPO multiples remain separate.

  Pipeline — status checked 15 October. New offering 6157 is included;
  listed 2636 is now in the 526-stock Database/Screener. Active deals come
  first; watchlist and withdrawn/postponed rows are separated/collapsed.

  Lock-up — HTML only. 161 completed historical events / 158 stocks.
  Confirmed cornerstone dates and exactly 30 HK trading sessions either
  side, prices through 2 October. Unconfirmed/future dates and unfinished
  or unverifiable return windows are excluded. Interior missing prices
  remain gaps. Selected average includes only checked stocks, one weight
  per stock. Stocks and average lines are shown in separate views.

DATA DATES AND CHECKS
  This 22 October delivery changes controls, formulas and presentation;
  it does not refresh market observations.
  Live quotes and the new IPO are dated 15 October. Older histories retain
  their own dates, mostly 2 October; this is not a blanket market refresh.
  Corporate-action adjustments use reviewed factors, not curve smoothing.
  Price returns exclude cash dividends. IPO 1w/1m/3m use 5/21/63 sessions.

  Native workbook structure, formula bindings, price/return arithmetic,
  stored data parity and comparison functions are checked locally.
  Bloomberg PE/PS and history queries still require a terminal/add-in to
  verify live responses. Off-terminal Unavailable is not an invented ratio.
  Audit CSV/JSON records remaining primary-source follow-up outside Excel.

UPDATE (JUPYTER)
  %run hk_ipo.py status
  %run hk_ipo.py update      fetch, parse, validate and rebuild
  %run hk_ipo.py build       reproduce stored data without a market refresh

  Run in a clean folder to reproduce the embedded release. An existing
  persistent data folder is retained for your updates. A failed provider
  keeps its previously dated cache; it does not make that cache current.
  Shared drive full: use ZIP for transfer or open a local copy. A full
  server quota still needs space freed by its owner.

HANDOVER
  In the repository, read START_HERE.md then data/release_state.json.
  AGENTS.md directs a new AI to these files. MAINTENANCE.md is history.
  Keep source review notes there, not as explanatory workbook footnotes.
