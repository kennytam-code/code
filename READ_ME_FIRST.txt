HK IPO DATABASE — what to do
============================

You only need ONE of these to work. Try them in this order.

OPTION A — easiest
  Download HK_IPO_Database_v1.xlsx and just open it.
  Go to the NEW DEAL tab. That is the whole tool.

OPTION B — if you cannot download .xlsx files
  Download hk_ipo.py (it has the whole database inside it), then run:
      pip install openpyxl
      python hk_ipo.py
  It creates the .xlsx and the .html next to itself. Open the .xlsx.

  If pip is blocked by the bank network, use ONE of these instead:
      pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org openpyxl
      pip install --proxy http://USER:PASSWORD@PROXY:PORT openpyxl

OPTIONAL — hk_ipo_dashboard.html is just charts. Double-click to open
  it in a browser. Skip it if HTML downloads are blocked; nothing else
  depends on it.

DAILY USE
  Open the workbook, NEW DEAL tab, type the deal's numbers into the
  BLUE cells. Everything else fills in automatically.
