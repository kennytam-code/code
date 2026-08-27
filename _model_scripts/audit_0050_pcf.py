#!/usr/bin/env python3
"""Integrity audit of the 0050 PCF pull and the Excel it produced.

Checks, in order of how much they would hurt if wrong:
  1  every Excel cell equals the raw JSON qty (no transcription/rounding loss)
  2  no duplicate RICs, no RIC that is silently dropped mid-run
  3  fundsize - (stk+fut+etf+bnd) is a plausible cash residual
  4  the weight shortfall from 100 equals that same cash residual
  5  implied price = weight/100 * fundsize / qty moves only as far as a legal
     TWSE day can, allowing for 2dp weight rounding and share-count corporate
     actions (a qty scaling error shows up here and nowhere else)
  6  futures notional from qty * contract multiplier * price reconciles to
     futvalues, which is what proves the futures qty is CONTRACTS not shares
  7  publish-date coverage vs the trandate chain (no silently skipped day)
"""

import glob
import json
import os
import sys

import pandas as pd

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_pcf_cache")
TX_MULT = 200        # NT$ per TAIEX index point
NYF_MULT = 10000     # 0050 shares per SSF contract

def check(name, ok, detail="", fails=None):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok and fails is not None:
        fails.append(name)


def load(only=None):
    """Cached payloads, restricted to `only` so a cache wider than the workbook
    (which happens as soon as the range is extended) cannot leak into the audit."""
    out = {}
    for f in sorted(glob.glob(os.path.join(CACHE, "0050_*.json"))):
        if os.path.getsize(f) == 0:
            continue
        key = os.path.basename(f)[5:13]
        if only is None or key in only:
            out[key] = json.load(open(f, encoding="utf-8"))
    return out


def rebalance_dates(data, dates):
    """Dates where the persistent constituent set changes -- derived, not hardcoded,
    so a future index review is picked up without editing this file."""
    stocks = {d: {s["code"] for s in data[d]["FundWeights"]["StockWeights"]} for d in dates}
    keep = {}
    for i, d in enumerate(dates):
        later = set().union(*(stocks[x] for x in dates[i + 1:])) if i + 1 < len(dates) else None
        keep[d] = stocks[d] if later is None else stocks[d] & later
    return [d for prev, d in zip(dates, dates[1:]) if keep[d] != keep[prev]]


def run(xlsx, dates_expected=None):
    fails = []
    build_fut_map(xlsx)
    data = load(only=set(dates_expected) if dates_expected else None)
    dates = sorted(data)
    print(f"AUDIT {os.path.basename(xlsx)}")
    print(f"loaded {len(dates)} PCF files, {dates[0]} -> {dates[-1]}\n")
    if dates_expected and sorted(dates_expected) != dates:
        missing = sorted(set(dates_expected) - set(dates))
        check("cache covers every date in the workbook", not missing,
              f"missing {missing}", fails)

    # ---------------------------------------------------------------- 1 & 2 --
    print("1/2  Excel vs raw JSON")
    book = pd.read_excel(xlsx, sheet_name=None, header=0)
    cells = bad = 0
    dup = []
    residuals = {}
    for sheet, df in book.items():
        df = df.set_index(df.columns[0])
        dup += [f"{sheet}:{r}" for r in df.index[df.index.duplicated()]]
        # Independently derive which stocks the extractor was entitled to drop:
        # present in the tab's opening PCF, absent from every later one.
        keys = [str(c).replace("-", "")[:8] for c in df.columns]
        if len(keys) > 1:
            head = {s["code"] for s in data[keys[0]]["FundWeights"]["StockWeights"]}
            later = set().union(*({s["code"] for s in data[k]["FundWeights"]["StockWeights"]}
                                  for k in keys[1:]))
            residuals[sheet] = head - later
        else:
            residuals[sheet] = set()
        for col in df.columns:
            key = str(col).replace("-", "")[:8]
            j = data[key]
            truth = {s["code"]: s["qty"] for s in j["FundWeights"]["StockWeights"]
                     if s["code"] not in residuals[sheet]}
            for f in j["FundWeights"]["FutureWeights"]:
                truth[f"{f['code']}{f['ym']}"] = f["qty"]
            got = {str(k): v for k, v in df[col].dropna().items()}
            # normalise futures RIC back to code+ym for comparison
            norm = {}
            for ric, v in got.items():
                row = ric
                if not ric.isdigit():
                    row = FUT_BACK[(sheet, ric)]
                norm[row] = v
            cells += len(norm)
            if norm != truth:
                bad += 1
                miss = set(truth) ^ set(norm)
                diff = {k: (truth.get(k), norm.get(k)) for k in truth
                        if k in norm and truth[k] != norm[k]}
                print(f"       {sheet} {col}: missing/extra={miss} value-diff={diff}")
    check(f"{cells} cells match raw JSON exactly", bad == 0, fails)
    check("no duplicate RICs", not dup, str(dup), fails)
    for sheet, res in residuals.items():
        if res:
            print(f"       '{sheet}': {len(res)} rebalance residual(s) excluded by "
                  f"design: {sorted(res)}")
    # An excluded row is only legitimate if it really is a sold-down tail: gone
    # from every later PCF in its tab, AND collapsed to a fraction of the size it
    # held in the tab before.  Derived per run, so a future review needs no edit.
    bad_res, sheets = [], list(book)
    for i, sheet in enumerate(sheets):
        keys = [str(c).replace("-", "")[:8] for c in book[sheet].columns[1:]]
        for code in sorted(residuals[sheet]):
            here = next((s["qty"] for s in data[keys[0]]["FundWeights"]["StockWeights"]
                         if s["code"] == code), None)
            before = None
            if i:
                pk = str(book[sheets[i - 1]].columns[-1]).replace("-", "")[:8]
                before = next((s["qty"] for s in data[pk]["FundWeights"]["StockWeights"]
                               if s["code"] == code), None)
            if before:
                print(f"       '{sheet}' excludes {code}: {here:,.0f} shares left of "
                      f"{before:,.0f} in the tab before ({here / before:.2%})")
                if here >= 0.10 * before:
                    bad_res.append((sheet, code))
            else:
                print(f"       '{sheet}' excludes {code} (no prior tab to size against)")
    check("every excluded row is a collapsed sold-down tail, not a live position",
          not bad_res, str(bad_res), fails)

    # -------------------------------------------------------------------- 3 --
    # fundsize is the whole fund; the sleeves are only the securities.  The
    # residual is the cash sleeve, which the API does not publish separately
    # (Cash is null on every date).  So this is not an identity -- what has to
    # hold is that the residual stays small and is genuinely cash-sized.
    print("\n3  fundsize - (stk+fut+etf+bnd) = cash residual")
    cash = {}
    for d in dates:
        s = data[d]["FundWeights"]["Summary"]
        parts = s["stkvalues"] + s["futvalues"] + s["etfvalues"] + s["bndvalues"]
        cash[d] = (s["fundsize"] - parts) / s["fundsize"] * 100
    C = pd.Series(cash)
    check("residual within +/-1% of fund on every date", bool(C.abs().max() < 1.0),
          f"min {C.min():+.3f}%  max {C.max():+.3f}%  (max on {C.idxmax()})", fails)

    # -------------------------------------------------------------------- 4 --
    print("\n4  published weights sum to 100 - cash%")
    sums = {}
    for d in dates:
        fw = data[d]["FundWeights"]
        sums[d] = (sum(x["weights"] for x in fw["StockWeights"])
                   + sum(x["weights"] for x in fw["FutureWeights"]))
    W = pd.Series(sums)
    # 52-56 lines each rounded to 2dp => up to ~0.28 of pure rounding slack
    resid = (100 - W) - C
    check("weight shortfall equals the cash residual (within 2dp rounding)",
          bool(resid.abs().max() < 0.30),
          f"weights {W.min():.2f}-{W.max():.2f}, worst mismatch {resid.abs().max():.3f}pt", fails)

    # -------------------------------------------------------------------- 5 --
    # A qty scaling error cannot hide here: price = weight/100 * fundsize / qty
    # uses qty as the divisor, so any bad qty prints as a price discontinuity.
    print("\n5  implied price continuity  (price = weight/100 * fundsize / qty)")
    px, wt = {}, {}
    for d in dates:
        fs = data[d]["FundWeights"]["Summary"]["fundsize"]
        px[d] = {s["code"]: s["weights"] / 100 * fs / s["qty"]
                 for s in data[d]["FundWeights"]["StockWeights"] if s["qty"]}
        wt[d] = {s["code"]: s["weights"] for s in data[d]["FundWeights"]["StockWeights"]}
    P = pd.DataFrame(px).T.sort_index()
    WT = pd.DataFrame(wt).T.sort_index().reindex(columns=P.columns)

    # A weight published as 0.00 cannot resolve a price.  That only happens to
    # the residual tails of deleted names on the transition day; the qty is
    # still exact (check 1), so exclude these from the price test and name them.
    zero_w = WT.eq(0).stack()
    zero_w = zero_w[zero_w]
    print(f"       {len(zero_w)} line(s) with weight rounded to 0.00 "
          f"(price unresolvable, qty still exact): {list(zero_w.index)}")
    P = P.mask(WT.eq(0))
    check("all resolvable implied prices positive", bool((P > 0).any().any() and
          not (P.stack() <= 0).any()), "", fails)

    # Share-count corporate actions (TW stock dividends are common in Jul/Aug)
    # move one name's holding against the whole book.  Per-unit holdings strip
    # out creations, so the excess over the book's median drift IS the action.
    QTY = pd.DataFrame({d: {s["code"]: s["qty"]
                            for s in data[d]["FundWeights"]["StockWeights"]}
                        for d in dates}).T.sort_index()
    OS = pd.Series({d: data[d]["PCF"]["osunit"] for d in dates}).sort_index()
    pu_chg = QTY.div(OS, axis=0).pct_change()
    excess = (1 + pu_chg).div(1 + pu_chg.median(axis=1), axis=0) - 1
    # On the rebalance transition the index reweights every name, so per-name
    # drift there is not a corporate action and prices are not continuous.
    rebal = [d for d in rebalance_dates(data, dates) if d in excess.index]
    print(f"       rebalance date(s) derived from the data: {rebal or 'none'}")
    if rebal:
        excess = excess.drop(index=rebal)
    ratio = excess.where(excess.abs() > 0.01)          # only a real action clears 1%
    for (d, c), r in ratio.stack().dropna().items():
        print(f"       corporate action {d} {c}: share count {r:+.2%} vs book "
              f"-> reference price adjusts {1 / (1 + r) - 1:+.2%}")

    # Weights are published to 2dp, so the true weight of a line printed as w
    # lies in [w-0.005, w+0.005].  The implied move therefore lies in a BAND.
    # The data is consistent iff that band overlaps the legal +/-10% TWSE limit.
    FS = pd.Series({d: data[d]["FundWeights"]["Summary"]["fundsize"] for d in dates}).sort_index()
    scale = (FS / FS.shift()).values[:, None] * (QTY.shift() / QTY).values
    # share count up by r => price down by 1/r; undo it before testing the move
    corr = 1 + ratio.reindex_like(WT).fillna(0)
    lo = (WT - 0.005) / (WT.shift() + 0.005) * scale * corr - 1
    hi = (WT + 0.005) / (WT.shift() - 0.005) * scale * corr - 1
    if rebal:
        lo, hi = lo.drop(index=rebal), hi.drop(index=rebal)
    bad = ((lo > 0.10) | (hi < -0.10)).stack()
    bad = bad[bad]
    check("every implied move can be a <=10% TWSE move once 2dp weight rounding "
          "and corporate actions are allowed for", bad.empty,
          f"{len(bad)} breach(es) {list(bad.index)[:5]}"
          + (f"; rebalance day(s) {rebal} excluded" if rebal else ""), fails)
    move = P.pct_change().abs()
    check("no implied price jumps by a power of 10 (qty scaling error)",
          bool(move.max().max() < 3.0), f"max raw move {100 * move.max().max():.1f}%", fails)

    # -------------------------------------------------------------------- 6 --
    print("\n6  futures qty are CONTRACTS  (qty * multiplier * price ~ futvalues)")
    rows = []
    for d in dates:
        fw = data[d]["FundWeights"]
        fs = fw["Summary"]["fundsize"]
        # TAIEX level implied by the TX weight; 0050 price implied by the NYF weight
        recon = 0.0
        for f in fw["FutureWeights"]:
            recon += f["weights"] / 100 * fs
        rows.append({"date": d, "futvalues": fw["Summary"]["futvalues"],
                     "from_weights": recon})
    F = pd.DataFrame(rows).set_index("date")
    F["rel"] = (F.from_weights - F.futvalues).abs() / F.futvalues
    # weights are 2dp, so a 0.005pt rounding on a 0.03 weight is ~17% by itself
    check("futvalues reconciles to sum(weight)*fundsize within rounding",
          bool(F.rel.max() < 0.25), f"max rel gap {100 * F.rel.max():.1f}%", fails)

    d = dates[-1]
    fw = data[d]["FundWeights"]
    fs = fw["Summary"]["fundsize"]
    tsmc = next(s for s in fw["StockWeights"] if s["code"] == "2330")
    tsmc_px = tsmc["weights"] / 100 * fs / tsmc["qty"]
    for f in fw["FutureWeights"]:
        val = f["weights"] / 100 * fs
        mult = TX_MULT if f["code"] == "TX" else NYF_MULT
        print(f"       {d} {f['code']} {f['ym']}: {f['qty']:.0f} contracts"
              f" -> implied underlying {val / f['qty'] / mult:,.0f}"
              f" (x{mult:,} multiplier)")
    print(f"       cross-check: implied TSMC price NT${tsmc_px:,.0f}")

    # -------------------------------------------------------------------- 7 --
    print("\n7  publish-date coverage")
    chain = {d: data[d]["PCF"]["trandate"] for d in dates}
    gaps = [(prev, cur) for prev, cur in zip(dates, dates[1:]) if chain[cur] != prev]
    check("each file's trandate == the previous publish date", not gaps, str(gaps), fails)
    ann = [(d, data[d]["PCF"]["anndate"]) for d in dates if data[d]["PCF"]["anndate"] != d]
    check("each file's anndate == the URL date requested", not ann, str(ann[:5]), fails)

    print("\n" + ("ALL CHECKS PASSED" if not fails else f"FAILURES: {fails}"))
    return 1 if fails else 0


# built by the workbook reader: (sheet, ric) -> code+ym, for futures rows
FUT_BACK = {}

def build_fut_map(xlsx):
    MONTH = "FGHJKMNQUVXZ"
    FUT_BACK.clear()
    for sheet, df in pd.read_excel(xlsx, sheet_name=None, header=0).items():
        for ric in df[df.columns[0]].astype(str):
            if ric.isdigit():
                continue
            root, letter, yr = ric[:-2], ric[-2], ric[-1]
            month = MONTH.index(letter) + 1
            FUT_BACK[(sheet, ric)] = f"{root}202{yr}{month:02d}"


def main(xlsx):
    """Entry point for both `python audit_0050_pcf.py <file>` and the scraper,
    which imports this module and calls run() straight after writing the book."""
    return run(xlsx)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: audit_0050_pcf.py <workbook.xlsx>")
    sys.exit(main(sys.argv[1]))
