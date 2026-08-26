#!/usr/bin/env python3
"""
Yuanta 0050 PCF scraper -> Excel matrix of REAL fund holdings by date.

Source
------
https://etfapi.yuantaetfs.com/ectranslation/api/bridge
    ?APIType=ETFAPI&FuncId=PCF/Daily&ticker=0050&date=YYYYMMDD

The `date` in the URL is the ANNOUNCEMENT date (anndate) = the trade date the
in-kind basket is good for.  The holdings block inside is stamped `trandate`,
which is the prior business day's close.  Both are written to the sheet header.

The two halves of the payload
-----------------------------
  InKind/FundComposition   "basket" quantity  -- shares per ONE creation unit
                           (baseunit = 500,000 ETF units).  Integer, rounded.
  FundWeights/StockWeights "real"  quantity   -- shares the fund actually holds
  FundWeights/FutureWeights                   -- futures contracts held (TX, NYF, ...)

We take the REAL quantity, i.e. the lower half.  See basket_vs_real() for the
conversion identity between the two.

Output
------
0050_holdings_<from>_<to>.xlsx with one tab per constituent regime:
rows = RIC, columns = date, cells = real quantity (shares / contracts).
"""

import argparse
import datetime as dt
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.request

import pandas as pd

API = ("https://etfapi.yuantaetfs.com/ectranslation/api/bridge"
       "?APIType=ETFAPI&FuncId=PCF%2FDaily&ticker={ticker}&date={date}")

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_pcf_cache")

# CME/Refinitiv delivery-month letters, Jan..Dec
MONTH_CODE = "FGHJKMNQUVXZ"


# ----------------------------------------------------------------- fetching --

def _ssl_context():
    """A bare python3 on macOS ships no CA bundle; use certifi's when present."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


_CTX = None


def _get(url, timeout=30):
    """GET a URL as text.  Falls back to curl if the SSL handshake cannot be
    verified from python (happens behind TLS-inspecting corporate proxies)."""
    global _CTX
    if _CTX is None:
        _CTX = _ssl_context()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
            return resp.read().decode("utf-8-sig")
    except ssl.SSLError:
        out = subprocess.run(["curl", "-sS", "--max-time", str(timeout), url],
                             capture_output=True, check=True)
        return out.stdout.decode("utf-8-sig")


def fetch(ticker, date, retries=3, pause=0.4):
    """Return the parsed PCF payload for one date, or None if the fund did not
    publish one (weekend / holiday / date out of range)."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{ticker}_{date}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        return json.loads(raw) if raw.strip() else None

    url = API.format(ticker=ticker, date=date)
    for attempt in range(retries):
        try:
            raw = _get(url)
            break
        except Exception as exc:                       # noqa: BLE001
            if attempt == retries - 1:
                # A transport failure is NOT a no-publish day: do not cache it.
                print(f"  {date}: fetch failed ({exc})", file=sys.stderr)
                return None
            time.sleep(1.5 * (attempt + 1))
    time.sleep(pause)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = None

    # A no-publish day comes back empty / without the PCF block.  Cache the miss
    # as an empty file so a re-run does not re-hit the API for it.
    if not data or not data.get("PCF"):
        open(path, "w", encoding="utf-8").write("")
        return None

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(raw)
    return data


# ------------------------------------------------------------------- naming --

def stock_ric(code):
    """Bare listing code, as the desk keys off."""
    return code


def future_ric(code, ym):
    """TAIFEX contract RIC: root + month letter + last digit of year, e.g. TXU6."""
    if not ym or len(ym) != 6:
        return code
    year, month = int(ym[:4]), int(ym[4:6])
    return f"{code}{MONTH_CODE[month - 1]}{year % 10}"


# ------------------------------------------------------------------ parsing --

def rows_for_date(data):
    """One date -> list of (ric, code, ym, name_zh, name_en, kind, real_qty)."""
    fw = data.get("FundWeights") or {}
    out = []

    for s in fw.get("StockWeights") or []:
        out.append((stock_ric(s["code"]), s["code"], "", s.get("name") or "",
                    s.get("ename") or "", "Stock", s.get("qty")))

    for f in fw.get("FutureWeights") or []:
        ym = f.get("ym") or ""
        out.append((future_ric(f["code"], ym), f["code"], ym, f.get("name") or "",
                    f.get("ename") or "", "Future", f.get("qty")))

    # ETF / bond sleeves are empty for 0050 today but carry them if they appear.
    for e in fw.get("ETFWeights") or []:
        out.append((stock_ric(e["code"]), e["code"], "", e.get("name") or "",
                    e.get("ename") or "", "ETF", e.get("qty")))
    for b in fw.get("BondWeights") or []:
        out.append((b["code"], b["code"], "", b.get("name") or "",
                    b.get("ename") or "", "Bond", b.get("qty")))
    return out


def basket_vs_real(data):
    """Diagnostic: real qty / basket qty per name, against osunit / baseunit.

    The basket is shares per ONE creation unit.  The fund holds `osunit /
    baseunit` creation units, so

        real_qty  ~=  basket_qty * (osunit / baseunit)

    It is only approximate: basket_qty is rounded to whole shares, and osunit is
    stamped on anndate while the holdings are stamped on trandate.
    """
    pcf = data["PCF"]
    units = pcf["osunit"] / pcf["baseunit"]
    basket = {x["stkcd"]: x["qty"] for x in (data.get("InKind") or {}).get("FundComposition") or []}
    recs = []
    for s in (data.get("FundWeights") or {}).get("StockWeights") or []:
        b = basket.get(s["code"])
        if b:
            recs.append({"code": s["code"], "basket_qty": b, "real_qty": s["qty"],
                         "implied_units": s["qty"] / b})
    df = pd.DataFrame(recs)
    return units, df


# -------------------------------------------------------------------- build --

def daterange(start, end):
    d = start
    while d <= end:
        if d.weekday() < 5:                    # TAIFEX/TWSE never trade weekends
            yield d
        d += dt.timedelta(days=1)


def build(ticker, start, end):
    frames, meta, members = {}, {}, {}
    for d in daterange(start, end):
        key = d.strftime("%Y%m%d")
        data = fetch(ticker, key)
        if data is None:
            print(f"  {key}: no PCF published (holiday / not available)")
            continue
        rows = rows_for_date(data)
        if not rows:
            print(f"  {key}: PCF present but no holdings block")
            continue
        frames[d] = rows
        meta[d] = {"trandate": data["PCF"].get("trandate"),
                   "nav": data["PCF"].get("nav"),
                   "osunit": data["PCF"].get("osunit"),
                   "baseunit": data["PCF"].get("baseunit")}
        # regime key = the STOCK constituent set (futures roll, that is not a rebalance)
        members[d] = frozenset(r[1] for r in rows if r[5] == "Stock")
        print(f"  {key}: {sum(1 for r in rows if r[5]=='Stock')} stocks, "
              f"{sum(1 for r in rows if r[5]=='Future')} futures "
              f"(holdings as of {meta[d]['trandate']})")
    return frames, meta, members


def report_changes(dates, members):
    """Print every stock constituent change so nothing is merged silently."""
    hits = []
    for prev, cur in zip(dates, dates[1:]):
        add = sorted(members[cur] - members[prev])
        rem = sorted(members[prev] - members[cur])
        if add or rem:
            hits.append((cur, add, rem))
            print(f"  constituent change on {cur:%Y-%m-%d}: "
                  f"+{add if add else '-'}  -{rem if rem else '-'}")
    if not hits:
        print("  no constituent changes detected")
    return hits


def split_regimes(dates, members, cut=None, mode="cut"):
    """Group dates into tabs.

    mode='cut'  -- a single break immediately before `cut` (the index review
                   effective date).  The transition day, where the fund still
                   carries residual tails of the deleted names alongside the
                   full new positions, stays with the post-rebalance tab.
    mode='auto' -- a break at every detected constituent-set change.
    """
    if mode == "cut":
        if cut is None:
            return [list(dates)]
        pre = [d for d in dates if d < cut]
        post = [d for d in dates if d >= cut]
        return [g for g in (pre, post) if g]

    groups, cur = [], []
    for i, d in enumerate(dates):
        if cur and members[d] != members[dates[i - 1]]:
            groups.append(cur)
            cur = [d]
        else:
            cur.append(d)
    if cur:
        groups.append(cur)
    return groups


def residual_rows(df, kinds):
    """Deleted names the fund had not finished selling at the rebalance close.

    The tab's opening column carries the prior close, i.e. the transition book,
    so an outgoing name still shows an unsold tail there and never again.  Any
    STOCK present only in that first column is exactly that residual.  Futures
    are exempt -- a contract legitimately expires out of the front of a tab.
    """
    if df.shape[1] < 3:                      # need at least two date columns
        return []
    first, rest = df.columns[1], list(df.columns[2:])
    only_first = df[first].notna() & df[rest].isna().all(axis=1)
    is_stock = df["RIC"].map(kinds).eq("Stock")
    return df.loc[only_first & is_stock, "RIC"].tolist()


def matrix(group, frames, drop_residuals=True):
    """dates -> DataFrame: col A = RIC, then one column per date. Nothing else."""
    sort_key, kinds, cols = {}, {}, {}
    for d in group:
        col = {}
        for ric, code, ym, zh, en, kind, qty in frames[d]:
            rank = {"Stock": "0", "ETF": "1", "Bond": "2", "Future": "3"}[kind]
            sort_key.setdefault(ric, f"{rank}|{code}|{ym}")
            kinds.setdefault(ric, kind)
            col[ric] = qty
        cols[d.strftime("%Y-%m-%d")] = col

    df = pd.DataFrame(cols)
    # stocks first by code, then futures by code then contract month
    df = df.loc[pd.Series(sort_key).sort_values().index]
    df.index.name = "RIC"
    df = df.reset_index()

    dropped = residual_rows(df, kinds) if drop_residuals else []
    if dropped:
        df = df[~df.RIC.isin(dropped)].reset_index(drop=True)
    return df, dropped


def sheet_name(group, members, index):
    a, b = group[0], group[-1]
    tag = "pre-rebal" if index == 0 else "post-rebal"
    return f"{tag} {a:%m%d}-{b:%m%d}"


# --------------------------------------------------------------------- main --

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ticker", default="0050")
    ap.add_argument("--start", default="20260617")
    ap.add_argument("--end", default="20260825")
    ap.add_argument("--cut", default="20260622",
                    help="index review effective date: the single tab break")
    ap.add_argument("--split", default="cut", choices=["cut", "auto"],
                    help="'cut' = one break at --cut; 'auto' = break at every "
                         "detected constituent change")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    start = dt.datetime.strptime(args.start, "%Y%m%d").date()
    end = dt.datetime.strptime(args.end, "%Y%m%d").date()
    cut = None if args.cut.lower() == "none" else \
        dt.datetime.strptime(args.cut, "%Y%m%d").date()

    print(f"Fetching {args.ticker} PCF {args.start} -> {args.end}")
    frames, meta, members = build(args.ticker, start, end)
    if not frames:
        sys.exit("no data")

    dates = sorted(frames)
    print("\nconstituent audit")
    report_changes(dates, members)
    groups = split_regimes(dates, members, cut, args.split)
    print(f"\n{len(dates)} publish dates -> {len(groups)} tab(s)")

    out = args.out or f"{args.ticker}_holdings_{args.start}_{args.end}.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as xl:
        for i, g in enumerate(groups):
            df, dropped = matrix(g, frames)
            if dropped:
                print(f"  dropped {len(dropped)} rebalance residual(s) from tab {i + 1}: "
                      f"{dropped} (held only into {g[0]:%Y-%m-%d}, then sold out)")
            name = sheet_name(g, members, i)[:31]
            df.to_excel(xl, sheet_name=name, index=False)

            ws = xl.sheets[name]
            ws.freeze_panes = "B2"
            ws.column_dimensions["A"].width = 12
            for row in ws.iter_rows(min_row=2, min_col=2, max_col=1 + len(g)):
                for cell in row:
                    cell.number_format = "#,##0"
            for j in range(len(g)):
                ws.column_dimensions[
                    ws.cell(row=1, column=2 + j).column_letter].width = 13
            print(f"  tab '{name}': {len(df)} rows x {len(g)} dates")

    print(f"\nwrote {out}")

    # basket -> real sanity check on the last date
    last = frames and sorted(frames)[-1]
    data = fetch(args.ticker, last.strftime("%Y%m%d"))
    units, chk = basket_vs_real(data)
    print(f"\nbasket -> real check on {last}: osunit/baseunit = {units:,.0f} creation units")
    print(f"  implied units from qty ratios: min {chk.implied_units.min():,.0f} "
          f"median {chk.implied_units.median():,.0f} max {chk.implied_units.max():,.0f}")


if __name__ == "__main__":
    main()
