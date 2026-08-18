HK IPO DATABASE
===============

PUT THESE FILES IN:  G:\FIN_COMM\DeltaOne\Kenny\ECM\

TO JUST USE IT
  Open HK_IPO_Database_v1.xlsx -> SCREENER tab. That is the whole tool.
  Either pick a deal from the dropdown, or type your own deal into the
  'TYPE TO OVERRIDE' column. Anything you type wins; comps re-rank as
  you type. Extra controls:
    Rank by        - 'cornerstone overlap first' ranks comps by how many
                     cornerstone investors they share with the target
    A-share filter - screen only issuers with (or without) an A line
  The comp table carries every metric (1w/1m/3m, ex-pop, alpha, both
  subscriptions, shoe outcome, H-vs-A discount at IPO, premium today).

COMPS LAB (in the dashboard html)
  Pick the candidate, tick the comps you believe, and the Lab shows a
  side-by-side matrix of every metric plus a 'why do they split?' panel:
  choose an outcome (H above/below A, day-1 up/down, pop held...) and it
  ranks which factor - size, subscription, cornerstone, discount -
  actually separates the two camps.

TO UPDATE IT (Jupyter, three cells)
  %run hk_ipo.py status     <- what is in the database now
  %run hk_ipo.py refresh    <- go get the newest deals
  %run hk_ipo.py build      <- rewrite the .xlsx and .html

  If a website is blocked at the office, this still updates the rest:
      %run hk_ipo.py refresh --skip hkex

HOW OFTEN
  Weekly: refresh + build. New deals arrive by themselves; a pipeline
  name that has LISTED moves into the Database automatically; young
  deals' 1m/3m returns fill in as their windows pass.
  Monthly: do the update on the build machine instead (ask Claude
  there to 'update the HK IPO database' - its runbook is
  _ipo_db/MAINTENANCE.md) so the AAStocks/Tencent extras refresh too,
  then carry the new TO_NOMURA folder over.

  You already have all six packages installed, so nothing to install.
  If you ever do need them:
      pip install requests beautifulsoup4 lxml openpyxl pypdf yfinance
  and if the bank network blocks pip:
      pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org <packages>
      pip install --proxy http://USER:PASSWORD@PROXY:PORT <packages>

hk_ipo_dashboard.html is the charts. Double-click it. Skip it if HTML
downloads are blocked - nothing else depends on it.

ah_peers.ipynb  -  A/H price charts for any peer group, off Bloomberg.
  Open it in Jupyter and run all cells: a FORM appears (section 6) -
  type the codes from the Screener, set the start date and window,
  press 'Draw charts'. Names, listing dates, offer prices and A-share
  tickers are looked up for you; the H line is rebased on the OFFER
  price, so 100 = back to what subscribers paid. (No ipywidgets? The
  CODES cell at the top does the same job - edit it and run all.)

BLOOMBERG: the BBG Verify tab fills in only on your terminal. It resolves
each deal's IPO order ID from EQUITY_OFFERINGS and cross-checks the
scraped numbers against CP036 / CP037 / GREENSHOE_FACILITY, plus
A/H_SHARE_CONVERSION, market cap and P/E at the listing date.
Database cells that no public filing answered are already wired to it -
they say 'not filed - run on terminal' here and fill themselves there.
