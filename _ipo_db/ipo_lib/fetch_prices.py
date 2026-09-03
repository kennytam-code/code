#!/usr/bin/env python3
"""Day-1 and since-IPO performance for every deal, from Yahoo (via yfinance).

v1 only had day-1 returns for 2024-2026 (the aggregator's window), so every
"deals like this popped X%" statistic was measured in a single hot tape. This
backfills 2021-2023 — including the 2022 bear market — so the analog engine can
be trusted across regimes.

Captures, per deal:
  first_close / first_open   listing-day prices
  day1_return_pct            first close vs the struck offer price
  day1_open_pop_pct          first open vs the struck offer price (the print you
                             could actually have hit at the bell)
  last_close, since_ipo_pct  current standing

Results are cached to data/batches/prices.json; a re-run only fetches codes that
are missing, so it is cheap to repeat.
"""
import json, math, sys, time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
_FR = Path(__file__).resolve().parent.parent / "data" / "force_raw_codes.json"
FORCE_RAW = set(json.loads(_FR.read_text())) if _FR.exists() else set()
# corporate actions no source shows cleanly (subdivisions in raw Tencent
# prints — CIDI 1->10) — evidence-backed, applied to raw-print series only
# corporate actions come from ONE loader that merges auto + hand-curated BY
# DATE (dict.update replaced whole lists and silently dropped WellCell's
# first of two events — see corp_actions.py). Entitlement issues are NOT
# included here: rights/open offers never re-scale the traded print.
from corp_actions import load_actions

MANUAL_SPLITS = load_actions(ROOT)
OUT = ROOT / "data" / "batches" / "prices.json"
THROTTLE = 0.35


def apply_manual_splits(code, h):
    """Restore OFFER-scale continuity on a RAW-print DataFrame (Open/Close):
    bars on/after each subdivision date are multiplied by the ratio. Yahoo
    series never come here — Yahoo already adjusts (its problem is the
    opposite one)."""
    for ev in MANUAL_SPLITS.get(str(code), []):
        m = h.index.strftime("%Y-%m-%d") >= ev["date"]
        for col in ("Open", "Close"):
            if col in h.columns:
                h.loc[m, col] = h.loc[m, col] * ev["ratio"]
    return h

# Per-SECTOR benchmark, so a biotech is not measured against a tech index.
# Every ticker below was verified to return yfinance history before adoption.
# Healthcare: the Hang Seng biotech indices (^HSHKBIO, ^HSHCI) return NOTHING on
# Yahoo, so the tradeable proxy 2820.HK is used instead (verified 1,380 bars).
BENCH = {
    "Tech/AI":          ("3033.HK", "HSTECH (Hang Seng TECH ETF)"),
    "Healthcare":       ("2820.HK", "China Biotech ETF (HS biotech proxy)"),
    "Financials":       ("^HSNF",   "Hang Seng Finance sub-index"),
    "Real Estate":      ("^HSNP",   "Hang Seng Properties sub-index"),
    # HSI's Utilities sub-index is power/gas distributors ONLY (CLP, HK & China
    # Gas, Power Assets). Miners, chemicals and energy producers are classified
    # into Commerce & Industry by the index's own methodology, so that is the
    # honest benchmark for this bucket — Utilities was a mis-mapping.
    "Materials/Energy": ("^HSNC",   "Hang Seng Commerce & Industry sub-index"),
    "Consumer":         ("^HSNC",   "Hang Seng Commerce & Industry sub-index"),
    "Industrials":      ("^HSNC",   "Hang Seng Commerce & Industry sub-index"),
    "TMT-other":        ("^HSI",    "Hang Seng Index"),
    "Other":            ("^HSI",    "Hang Seng Index"),
}
DEFAULT_BENCH = ("^HSI", "Hang Seng Index")
HORIZONS = [("1w", 5), ("1m", 21), ("3m", 63)]     # trading-day offsets
# how far after the listing date the first available bar may sit and still BE
# the debut session (covers a listing straight into a long weekend)
DEBUT_LAG_MAX = 5
TX_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
         "Referer": "https://gu.qq.com/"}


def tencent_kline(symbol, d1, d2, n=1500):
    """RAW daily closes from Tencent — [(date, close), ...], oldest first.

    Yahoo simply has no history for a handful of recycled HK codes (0300, 0501,
    0917, ...) and answered with current quotes, which fabricated their debut
    returns. Tencent carries all of them from the true listing day. The bare
    `day` series is unadjusted, which is exactly what an offer-price comparison
    needs — no split correction to undo.
    symbol: 'hk00300' / 'sz300750' / 'sh600000'.
    """
    import requests
    # Tencent returns the LAST n bars, so n must span the whole window or an
    # older listing's debut silently falls off the front (a 2021 IPO needs
    # ~1,400 sessions; the old cap of 800 lost 14 debuts). BUT the API now
    # rejects n>~1500 by answering EMPTY — n=3000 silently blanked every call
    # on 2026-08-20 — so 1500 is both the floor the history needs and the
    # ceiling the endpoint accepts.
    u = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
         f"param={symbol},day,{d1},{d2},{n},")
    rows = []
    # Tencent throttles bursts by answering 200-with-empty-data; a burst of 511
    # requests once blanked an entire batch. Empty is retryable, not an answer.
    for attempt in range(3):
        r = requests.get(u, headers=TX_UA, timeout=30)
        d = (r.json().get("data") or {}).get(symbol) or {}
        rows = d.get("day") or d.get("qfqday") or []
        if rows:
            break
        time.sleep(2.5 * (attempt + 1))
    out = []
    for row in rows:
        try:
            # [date, OPEN, CLOSE, high, low, volume] — the open is real data,
            # not a fabrication: v13 discarded it and then had to withhold the
            # day-1 open→close column for every Tencent-sourced deal
            out.append((row[0], float(row[2]), float(row[1])))
        except (IndexError, ValueError, TypeError):
            continue
    return out


def bench_series(tickers, start):
    """One history pull per benchmark, reused for every deal.

    Returned as (dates, closes) lists rather than a DataFrame because alpha is
    aligned by CALENDAR DATE (see bench_return) — the benchmark's bar count is
    not the stock's bar count once a holiday or a halt intervenes.
    """
    out = {}
    for t in sorted(set(tickers)):
        try:
            h = yf.Ticker(t).history(start=start, auto_adjust=False)
            if len(h):
                out[t] = ([d.strftime("%Y-%m-%d") for d in h.index],
                          [float(c) for c in h["Close"]])
                print(f"  benchmark {t}: {len(h)} bars", flush=True)
        except Exception as e:
            print(f"  benchmark {t} FAILED: {e}", flush=True)
    return out


def bench_return(series, ipo, end_date):
    """Benchmark return over the window the IPO money was actually at risk.

    The stock's leg runs from the OFFER PRICE — cash committed before the shares
    ever trade — to the close on `end_date`. Anchoring the index at the debut
    day's CLOSE instead would compare a return that contains the day-one pop
    against one that does not, and dump the entire pop into "alpha": Kuaishou
    showed alpha_1m = +157.7% on a +141.9% one-month return purely from that
    mismatch. So the index is anchored at its last close STRICTLY BEFORE the
    listing date — the same moment the subscriber's money was locked — and ended
    on the stock's own trading date, matched by calendar date.
    """
    if not series:
        return None
    dates, closes = series
    i0 = None
    for i, d in enumerate(dates):
        if d < ipo:
            i0 = i
        else:
            break
    i1 = None
    for i, d in enumerate(dates):
        if d <= end_date:
            i1 = i
        else:
            break
    if i0 is None or i1 is None or i1 <= i0 or not closes[i0]:
        return None
    r = 100 * (closes[i1] / closes[i0] - 1)
    # a stub bar on either end prints NaN; that is an absent reading, not a zero
    return round(r, 2) if math.isfinite(r) else None


def main():
    deals = json.loads((ROOT / "data" / "deals.json").read_text())["deals"]
    sector_of = {d["code"]: d.get("sector") for d in deals}
    earliest = min((d["ipo_date"][:10] for d in deals if d.get("ipo_date")), default="2021-01-01")
    # start the index history BEFORE the first listing: the alpha anchor is the
    # last index close preceding a listing, so the earliest deal needs run-up
    benches = bench_series([t for t, _ in BENCH.values()] + [DEFAULT_BENCH[0]],
                           (date.fromisoformat(earliest) - timedelta(days=20)).isoformat())
    cache = {}
    if OUT.exists():
        cache = {r["code"]: r for r in json.loads(OUT.read_text())["deals"]}

    def stale(rec, d):
        """Does this cached record need refreshing on today's run?

        A cache keyed on "have I ever fetched this code" rots in two ways the
        desk's weekly/monthly update would hit head-on: since-IPO returns keep
        yesterday's last_close forever, and a young listing whose 1m/3m windows
        had not elapsed at first fetch NEVER gains them. Debut facts are
        immutable; everything anchored to "now" must expire.
        """
        if rec.get("error"):
            return True                              # give failures another go
        last = rec.get("last_date")
        if not last or (date.today() - date.fromisoformat(last)).days > 7:
            return True                              # since-IPO leg is stale
        ipo = (d.get("ipo_date") or "")[:10]
        # A DEAL IN ITS FIRST QUARTER is the one the desk actually reads, and
        # its since-IPO print is the headline; the 7-day tolerance above left
        # Ingenic showing a Friday close on the following Tuesday. Refetching
        # only the young names keeps the other ~500 series on the cache.
        if ipo and (date.today() - date.fromisoformat(ipo)).days <= 90 \
                and (date.today() - date.fromisoformat(last)).days > 2:
            return True
        if ipo and not rec.get("debut_missing"):
            aged = (date.today() - date.fromisoformat(ipo)).days
            for lbl, need in (("1w", 12), ("1m", 35), ("3m", 100)):
                if rec.get(f"ret_{lbl}_pct") is None and aged > need:
                    return True                      # window elapsed since caching
        return False

    todo = [d for d in deals if d.get("ipo_date")
            and (d["code"] not in cache or stale(cache[d["code"]], d))]
    print(f"{len(cache)} cached, fetching {len(todo)} "
          f"(new or stale)", flush=True)

    for i, d in enumerate(todo):
        code, ipo = d["code"], d["ipo_date"][:10]
        tkr = f"{int(code):04d}.HK"
        rec = {"code": code, "ticker": tkr, "ipo_date": ipo}
        try:
            start = (date.fromisoformat(ipo) - timedelta(days=3)).isoformat()
            yt = yf.Ticker(tkr)
            h = yt.history(start=start, auto_adjust=False)
            # A dated request can come back TRUNCATED — 0300.HK asked from
            # 2024-09-01 returns bars from 2024-10-02, but period="max" returns
            # them from 2024-07-05. Retry unbounded whenever the response has no
            # bar near the listing date, or the debut would be read off the
            # wrong session.
            if not len(h) or h.index[0].strftime("%Y-%m-%d") > ipo:
                try:
                    hmax = yt.history(period="max", auto_adjust=False)
                    if len(hmax) and (not len(h) or hmax.index[0] < h.index[0]):
                        h = hmax
                except Exception:
                    pass
            # Yahoo back-adjusts history for SPLITS/consolidations even with
            # auto_adjust=False. The offer price is a raw historical price, so
            # comparing the two would be wrong (a 1:3 consolidation showed as a
            # -66% debut). Undo the adjustment with the cumulative split factor.
            # raw(t) = adjusted(t) x product(split ratios dated AFTER t), so the
            # latest bar is untouched and only pre-split history is restored.
            if "Stock Splits" in h.columns and (h["Stock Splits"] != 0).any():
                # Yahoo sometimes records ONE corporate action TWICE a few days
                # apart (Zhida: 5.0 on 2026-02-20 AND 5.0 on 2026-03-03), which
                # squares the correction and turned a +192% debut into +1361%.
                # Raw prices need no reconstruction at all, so whenever this
                # line has any split history the unadjusted Tencent series is
                # used instead and Yahoo's is discarded.
                tx = []
                try:
                    tx = tencent_kline(f"hk{int(code):05d}", ipo,
                                       date.today().isoformat())
                except Exception:
                    tx = []
                # The Tencent leg is what MAKES this record correct; if it
                # comes back empty (the endpoint rejects n>1500, and throttles
                # bursts) the Yahoo split-adjusted series would silently ship a
                # 1,360% day-1. Refuse to publish that quietly.
                if len(tx) <= 5:
                    rec["price_note"] = (
                        "SPLIT-ADJUSTED SOURCE, UNCORRECTED — Yahoo reports a "
                        "split for this code and the raw Tencent series could "
                        "not be fetched; returns below may be overstated")
                    rec["split_uncorrected"] = True
                if len(tx) > 5:
                    import pandas as pd
                    idx = pd.to_datetime([r0[0] for r0 in tx])
                    px = [r0[1] for r0 in tx]
                    op = [r0[2] if len(r0) > 2 else r0[1] for r0 in tx]
                    h = pd.DataFrame({"Open": op, "Close": px}, index=idx)
                    h = apply_manual_splits(code, h)
                    rec["price_src"] = "tencent:kline (raw — Yahoo split data unreliable)"
                    if str(code) in MANUAL_SPLITS:
                        rec["price_src"] += " + manual split correction"
                    rec["split_factor_first"] = None
                else:
                    ratios = h["Stock Splits"].replace(0, 1.0)
                    # product of everything strictly after each row
                    after = ratios[::-1].cumprod()[::-1] / ratios
                    rec["split_factor_first"] = round(float(after.iloc[0]), 6)
                    for col in ("Open", "Close"):
                        h[col] = h[col] * after
            if len(h):
                # The first bar on/after the listing date is the debut session
                # ONLY if it actually falls on it. Yahoo has no history at all
                # for a handful of recycled codes and answers with recent quotes
                # instead; taking those at face value recorded Midea's "day one"
                # from a session 15 days later (+70% instead of +8%) and
                # Qunabox's from 378 days later (+246%). A debut that cannot be
                # located is left EMPTY and explained — never approximated.
                # force-raw: audit_opens found a hidden Yahoo adjustment (a
                # capital action with no split row) for these codes — drop the
                # Yahoo series entirely so the split-branch below rebuilds from
                # raw Tencent prints
                if code in FORCE_RAW:
                    import pandas as _pd
                    h = h.iloc[0:0]
                    rec["price_note"] = ("Yahoo carries a hidden (non-split) "
                                         "adjustment for this code — raw Tencent "
                                         "series used instead (audit_opens)")
                bars = h[h.index.strftime("%Y-%m-%d") >= ipo]
                if len(bars):
                    fd = bars.index[0].strftime("%Y-%m-%d")
                    lag = (date.fromisoformat(fd) - date.fromisoformat(ipo)).days
                    if lag <= DEBUT_LAG_MAX:
                        rec["first_open"] = round(float(bars["Open"].iloc[0]), 4)
                        rec["first_close"] = round(float(bars["Close"].iloc[0]), 4)
                        rec["first_date"] = fd
                    else:
                        rec["debut_missing"] = True
                        rec["price_note"] = (
                            f"Yahoo has no session near the {ipo} listing "
                            f"(earliest bar {fd}); debut and horizon returns "
                            f"left blank rather than measured off the wrong day")
                # Yahoo's newest row can be a stub with a NaN close (session
                # not settled yet), which would otherwise write NaN straight
                # through to since-IPO and its alpha. Mark to the last bar that
                # actually printed a price.
                cl = h["Close"].dropna()
                if len(cl):
                    rec["last_close"] = round(float(cl.iloc[-1]), 4)
                    rec["last_date"] = cl.index[-1].strftime("%Y-%m-%d")
            fp = d.get("final_price")
            if fp and rec.get("first_close"):
                rec["day1_return_pct"] = round(100 * (rec["first_close"] / fp - 1), 2)
            if fp and rec.get("first_open"):
                rec["day1_open_pop_pct"] = round(100 * (rec["first_open"] / fp - 1), 2)
            if fp and rec.get("last_close"):
                rec["since_ipo_pct"] = round(100 * (rec["last_close"] / fp - 1), 2)
            # multi-horizon returns vs the OFFER price, plus alpha over the
            # deal's own sector benchmark across the identical window.
            # Skipped entirely when the debut could not be located: horizon
            # returns counted off a wrong starting bar are worse than no number.
            if fp and len(h) and not rec.get("debut_missing"):
                closes = h["Close"].reset_index(drop=True)
                hdates = [ts.strftime("%Y-%m-%d") for ts in h.index]
                idx = [k for k, s in enumerate(hdates) if s >= ipo]
                i0 = idx[0] if idx else None
                bt, blabel = BENCH.get(sector_of.get(code) or "", DEFAULT_BENCH)
                rec["benchmark"] = blabel
                bh = benches.get(bt)
                for label, n in HORIZONS:
                    if i0 is not None and i0 + n < len(closes):
                        px = float(closes.iloc[i0 + n])
                        rec[f"ret_{label}_pct"] = round(100 * (px / fp - 1), 2)
                        rec[f"ret_{label}_date"] = hdates[i0 + n]
                        # index measured over the SAME window: from the close
                        # before listing to this deal's own horizon date
                        br = bench_return(bh, ipo, hdates[i0 + n])
                        if br is not None:
                            rec[f"alpha_{label}_pct"] = round(rec[f"ret_{label}_pct"] - br, 2)
                            rec[f"bench_{label}_pct"] = br
                # day-1 and since-IPO get the same treatment, so every alpha in
                # the book is measured the one way
                if i0 is not None:
                    b1 = bench_return(bh, ipo, hdates[i0])
                    if b1 is not None and rec.get("day1_return_pct") is not None:
                        rec["bench_day1_pct"] = b1
                        rec["alpha_day1_pct"] = round(rec["day1_return_pct"] - b1, 2)
                bs = bench_return(bh, ipo, rec.get("last_date") or hdates[-1])
                if bs is not None and rec.get("since_ipo_pct") is not None:
                    rec["bench_since_pct"] = bs
                    rec["alpha_since_pct"] = round(rec["since_ipo_pct"] - bs, 2)
            # ---- Tencent fallback: Yahoo has NO usable history for this code
            if fp and (rec.get("debut_missing") or not len(h)):
                try:
                    tx = tencent_kline(f"hk{int(code):05d}",
                                       (date.fromisoformat(ipo) - timedelta(days=4)).isoformat(),
                                       date.today().isoformat())
                except Exception:
                    tx = []
                ti = next((k for k, row_ in enumerate(tx) if row_[0] >= ipo), None)
                if (ti is not None and (date.fromisoformat(tx[ti][0])
                                        - date.fromisoformat(ipo)).days <= DEBUT_LAG_MAX):
                    tdates = [x[0] for x in tx]
                    tcloses = [x[1] for x in tx]
                    topens = [x[2] if len(x) > 2 else x[1] for x in tx]
                    for ev in MANUAL_SPLITS.get(str(code), []):
                        tcloses = [c * ev["ratio"] if d0 >= ev["date"] else c
                                   for d0, c in zip(tdates, tcloses)]
                        topens = [o * ev["ratio"] if d0 >= ev["date"] else o
                                  for d0, o in zip(tdates, topens)]
                    rec.pop("debut_missing", None)
                    rec["price_note"] = ("Yahoo has no history for this code; "
                                         "prices from Tencent kline (raw)")
                    rec["price_src"] = "tencent:kline"
                    if str(code) in MANUAL_SPLITS:
                        rec["price_src"] += " + manual split correction"
                    rec["first_close"] = round(tcloses[ti], 4)
                    rec["first_open"] = round(topens[ti], 4)
                    rec["first_date"] = tdates[ti]
                    if topens[ti] > 0:
                        rec["day1_open_pop_pct"] = round(100 * (topens[ti] / fp - 1), 2)
                    rec["last_close"] = round(tcloses[-1], 4)
                    rec["last_date"] = tdates[-1]
                    rec["day1_return_pct"] = round(100 * (tcloses[ti] / fp - 1), 2)
                    rec["since_ipo_pct"] = round(100 * (tcloses[-1] / fp - 1), 2)
                    bt, blabel = BENCH.get(sector_of.get(code) or "", DEFAULT_BENCH)
                    rec["benchmark"] = blabel
                    bh = benches.get(bt)
                    for label, nb in HORIZONS:
                        if ti + nb < len(tcloses):
                            rec[f"ret_{label}_pct"] = round(100 * (tcloses[ti + nb] / fp - 1), 2)
                            rec[f"ret_{label}_date"] = tdates[ti + nb]
                            br = bench_return(bh, ipo, tdates[ti + nb])
                            if br is not None:
                                rec[f"alpha_{label}_pct"] = round(
                                    rec[f"ret_{label}_pct"] - br, 2)
                                rec[f"bench_{label}_pct"] = br
                    b1 = bench_return(bh, ipo, tdates[ti])
                    if b1 is not None:
                        rec["bench_day1_pct"] = b1
                        rec["alpha_day1_pct"] = round(rec["day1_return_pct"] - b1, 2)
                    bs = bench_return(bh, ipo, tdates[-1])
                    if bs is not None:
                        rec["bench_since_pct"] = bs
                        rec["alpha_since_pct"] = round(rec["since_ipo_pct"] - bs, 2)
        except Exception as e:
            rec["error"] = str(e)[:120]
        cache[code] = rec
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(todo)}", flush=True)
            OUT.write_text(json.dumps({"batch": "prices", "deals": list(cache.values())},
                                      ensure_ascii=False, indent=1))
        time.sleep(THROTTLE)

    recs = list(cache.values())
    OUT.write_text(json.dumps(
        {"batch": "prices",
         "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(recs),
         "with_day1": sum(1 for r in recs if r.get("day1_return_pct") is not None),
         "with_since": sum(1 for r in recs if r.get("since_ipo_pct") is not None),
         "with_1m": sum(1 for r in recs if r.get("ret_1m_pct") is not None),
         "with_alpha_1m": sum(1 for r in recs if r.get("alpha_1m_pct") is not None),
         "deals": recs}, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {len(recs)} codes, "
          f"{sum(1 for r in recs if r.get('day1_return_pct') is not None)} with day-1, "
          f"{sum(1 for r in recs if r.get('since_ipo_pct') is not None)} with since-IPO")


if __name__ == "__main__":
    main()
