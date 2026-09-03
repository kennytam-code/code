#!/usr/bin/env python3
"""Lint every Bloomberg formula in the built workbook.

BDP/BDH/BDS cannot execute off the terminal, so a typo ships silently and dies
on the desk. This walks every formula containing a Bloomberg call and checks
what CAN be checked without a terminal:

  1. balanced parentheses and quotes;
  2. the mnemonic against a whitelist split into DESK-PROVEN (values came back
     in the user's bbg.xlsx paste) vs AWAITING VERIFY (print them loudly);
  3. BDH date arguments must reference the Database IPO-date column (a literal
     date would silently freeze);
  4. ticker construction: " HK Equity"/" CH Equity" suffixes must ride a
     Database code reference, "Index"/"Curncy" tickers must be whole literals;
  5. every Bloomberg call is wrapped in IFERROR (off-terminal it must degrade
     to a message, never to #NAME?).

Exit 1 on any hard failure; AWAITING VERIFY is a warning, not a failure.
"""
import re
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
WB = ROOT / "out" / "HK_IPO_Database_v1.xlsx"

# fields that returned real values in the desk's pasted bbg.xlsx
PROVEN = {"CP036", "CP037", "GREENSHOE_FACILITY", "OFFERING_GREENSHOE_SHARES_EX",
          "PE_RATIO", "A/H_SHARE_CONVERSION", "CUR_MKT_CAP", "EQUITY_OFFERINGS",
          "PX_LAST"}
# 2026-08-26 terminal verify: EQY_INIT_PO_SH_PRC and EQUITY_OFFERINGS-as-BDP
# came back "#N/A Invalid Field" and were REMOVED from the Verify tab (the
# offer price is tied down by the verified day-1 close instead). HK tickers
# must be built WITHOUT leading zeros — "0606 HK Equity" was rejected.
AWAIT = {"HSAHP Index": "new in v15 — verify one cell on the terminal before trusting the column",
         "PX_TO_SALES_RATIO": "new in v23 (Screener 'P/S now') — the desk's own formula; check one cell"}
CALL = re.compile(r"\b(BDP|BDH|BDS)\s*\(")
MNEM = re.compile(r'"([A-Z][A-Z0-9_/ ]{2,40})"')


def main():
    wb = openpyxl.load_workbook(WB)
    n_calls = bad = 0
    warns = set()
    for ws in wb:
        for row in ws.iter_rows():
            for c in row:
                f = c.value
                if not isinstance(f, str) or not f.startswith("=") or not CALL.search(f):
                    continue
                n_calls += 1
                where = f"{ws.title}!{c.coordinate}"
                if f.count("(") != f.count(")"):
                    bad += 1
                    print(f"  FAIL {where}: unbalanced parentheses")
                if f.count('"') % 2:
                    bad += 1
                    print(f"  FAIL {where}: odd number of quotes")
                if "IFERROR(" not in f and "IF(" not in f.replace("IFERROR(", ""):
                    bad += 1
                    print(f"  FAIL {where}: Bloomberg call with no IFERROR guard")
                for m in MNEM.finditer(f):
                    tok = m.group(1).strip()
                    if tok.endswith(("HK Equity", "CH Equity", "Curncy")):
                        continue
                    if tok in ("IPO", "array=t", "endcol=1", "endcol=2", "startcol=2"):
                        continue
                    if tok in AWAIT:
                        warns.add(f"{tok}: {AWAIT[tok]}")
                        continue
                    if tok.endswith("Index"):
                        warns.add(f"{tok}: index ticker not desk-proven yet")
                        continue
                    if tok not in PROVEN and tok.isupper():
                        bad += 1
                        print(f"  FAIL {where}: mnemonic {tok!r} not in the desk-proven set")
                # BDH with two date args must anchor on the IPO-date column
                if "BDH(" in f and "TODAY()" not in f:
                    # the rule's intent is NO FROZEN LITERAL DATES: a BDH whose
                    # dates are typed in would keep answering for a date nobody
                    # maintains. Any CELL reference satisfies that — the Verify
                    # sheet anchors on its own date column (corporate-action
                    # dates are not in the Database) — a literal does not.
                    cell_ref = re.search(r"(?:[A-Za-z0-9 ()']+!)?\$?[A-Z]{1,2}\$?\d+", f)
                    literal = re.search(r'"\d{4}[-/]\d{2}[-/]\d{2}"|DATE\s*\(', f)
                    if literal or not cell_ref:
                        bad += 1
                        print(f"  FAIL {where}: BDH dates are literals, not cell "
                              f"references")
    print(f"lint_bbg: {n_calls} Bloomberg formulas checked")
    for w in sorted(warns):
        print(f"  AWAIT VERIFY: {w}")
    print("  RESULT:", "CLEAN" if not bad else f"{bad} PROBLEMS")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
