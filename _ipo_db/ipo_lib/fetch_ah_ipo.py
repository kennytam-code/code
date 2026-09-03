#!/usr/bin/env python3
"""What the H shares were priced at RELATIVE TO THE A LINE on pricing day.

For an A-to-H listing the single most-asked question is how big a discount the
H shares came at. That is answerable exactly:

    A close on the last session BEFORE the H listing   (CNY)
      x  CNYHKD on that same session                   -> HK$
      vs the struck H offer price                      -> discount / premium

Using the A close from the day before the debut (not the debut day itself)
keeps the comparison clean: on listing day the A line already reacts to the H
print. Hand-checked on CATL: A closed CNY260.00 on 2025-05-19, CNYHKD 1.0838
-> HK$281.79 against an H offer of HK$263.00 = a 6.7% discount.

Writes data/batches/ah_ipo.json.
"""
import json, time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "batches" / "ah_ipo.json"
FX_TICKER = "CNYHKD=X"
THROTTLE = 0.35


def series(tkr, start, end, undo_splits=False):
    """Closes, optionally with Yahoo's split back-adjustment undone.

    Mainland lines pay bonus shares (送股) constantly and Yahoo restates the
    pre-event history for them even with auto_adjust=False. The H offer price is
    a raw historical number, so an adjusted A close makes the comparison
    nonsense — Joinn Labs read as a +144% H PREMIUM before this was applied.
    raw(t) = adjusted(t) x product(ratios dated after t).
    """
    h = yf.Ticker(tkr).history(start=start, end=end, auto_adjust=False)
    if not len(h):
        return [], []
    closes = [float(c) for c in h["Close"]]
    if undo_splits and "Stock Splits" in h.columns:
        sp = [float(s) for s in h["Stock Splits"]]
        factor = 1.0
        for i in range(len(closes) - 1, -1, -1):
            closes[i] *= factor
            if sp[i]:
                factor *= sp[i]
    return [d.strftime("%Y-%m-%d") for d in h.index], closes


def last_before(dates, closes, cutoff):
    """Close on the last session STRICTLY before cutoff."""
    best = None
    for d, c in zip(dates, closes):
        if d < cutoff:
            best = (d, c)
        else:
            break
    return best


def tencent_a_close(a_code, ipo):
    """Second, independent read of the same A close, from Tencent (raw prices).

    Yahoo's A-share history needs a split-unwind that itself deserves checking;
    Tencent's bare `day` series is unadjusted at source. '300750.SZ' -> sz300750.
    """
    import requests
    num, venue = a_code.split(".")
    sym = ("sz" if venue == "SZ" else "sh" if venue == "SS" else "bj") + num
    d1 = (date.fromisoformat(ipo) - timedelta(days=25)).isoformat()
    u = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
         f"param={sym},day,{d1},{ipo},60,")
    r = requests.get(u, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X "
                                 "10_15_7) Chrome/126.0 Safari/537.36"}, timeout=30)
    rows = ((r.json().get("data") or {}).get(sym) or {}).get("day") or []
    best = None
    for row in rows:
        try:
            if row[0] < ipo:
                best = (row[0], float(row[2]))
        except (IndexError, ValueError, TypeError):
            continue
    return best


def main():
    deals = json.loads((ROOT / "data" / "deals.json").read_text())["deals"]
    pairs = [d for d in deals if d.get("a_share_code") and d.get("final_price")
             and d.get("ipo_date")]
    print(f"{len(pairs)} deals with an A line and a struck price", flush=True)

    earliest = min(d["ipo_date"][:10] for d in pairs)
    fxd, fxc = series(FX_TICKER,
                      (date.fromisoformat(earliest) - timedelta(days=30)).isoformat(),
                      (date.today() + timedelta(days=1)).isoformat())
    print(f"  {FX_TICKER}: {len(fxd)} bars", flush=True)

    prev = {}
    if OUT.exists():
        prev = {r["code"]: r for r in json.loads(OUT.read_text())["deals"]}

    out = []
    for i, d in enumerate(pairs):
        code, ipo, fp = d["code"], d["ipo_date"][:10], d["final_price"]
        if code in prev and prev[code].get("ah_discount_ipo_pct") is not None:
            out.append(prev[code])
            continue
        rec = {"code": code, "a_share_code": d["a_share_code"], "ipo_date": ipo,
               "h_offer_price": fp}
        try:
            # pull to TODAY so every post-listing bonus issue is visible and can
            # be unwound; the window is clipped after the correction
            ad, ac = series(d["a_share_code"],
                            (date.fromisoformat(ipo) - timedelta(days=25)).isoformat(),
                            (date.today() + timedelta(days=1)).isoformat(),
                            undo_splits=True)
            hit = last_before(ad, ac, ipo)
            fxhit = last_before(fxd, fxc, ipo)
            # independent second read — and the ONLY read where Yahoo has none
            try:
                tx = tencent_a_close(d["a_share_code"], ipo)
            except Exception:
                tx = None
            if not hit and tx:
                hit = tx
                rec["a_close_src"] = "tencent:kline (Yahoo has no history)"
            if hit and fxhit:
                adate, aclose = hit
                _fxdate, fx = fxhit
                if tx and tx[0] == adate:
                    gap = abs(tx[1] - aclose) / aclose if aclose else 0
                    if gap > 0.01:
                        # raw beats corrected when they disagree: the Tencent
                        # series needs no split-unwind to be wrong about
                        aclose = tx[1]
                        rec["a_close_src"] = "tencent:kline (Yahoo differed "\
                                             f"{100*gap:.1f}%)"
                        rec["a_close_status"] = "conflict"
                    else:
                        rec["a_close_status"] = "xchecked"
                a_hkd = aclose * fx
                rec.update({
                    "a_close_date": adate, "a_close_cny": round(aclose, 4),
                    "cnyhkd": round(fx, 4), "a_close_hkd": round(a_hkd, 4),
                    # negative = H struck BELOW the A line (the usual case)
                    "ah_discount_ipo_pct": round(100 * (fp / a_hkd - 1), 2)})
            else:
                # Biocytogen case: the A line LISTED AFTER the H IPO, so no A
                # close existed at pricing — that is an answer, not a gap
                first_a = ad[0] if ad else None
                if not first_a:
                    try:
                        import requests as _rq
                        num, venue = d["a_share_code"].split(".")
                        sym = ("sz" if venue == "SZ" else "sh") + num
                        u = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
                             f"param={sym},day,{ipo},{date.today().isoformat()},2400,")
                        rows = ((_rq.get(u, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
                                 .json().get("data") or {}).get(sym) or {}).get("day") or []
                        first_a = rows[0][0] if rows else None
                    except Exception:
                        first_a = None
                if first_a and first_a > ipo:
                    rec["note"] = (f"A shares only began trading {first_a}, after "
                                   f"the H IPO — no A line existed at pricing")
                else:
                    rec["note"] = "no A-share close available before the H listing"
        except Exception as e:
            rec["error"] = str(e)[:100]
        out.append(rec)
        if (i + 1) % 15 == 0:
            print(f"  {i+1}/{len(pairs)}", flush=True)
        time.sleep(THROTTLE)

    n = sum(1 for r in out if r.get("ah_discount_ipo_pct") is not None)
    OUT.write_text(json.dumps(
        {"batch": "ah_ipo", "fx": FX_TICKER,
         "method": "H offer price vs A close on the last session before listing, "
                   "converted at that session's CNYHKD",
         "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(out), "resolved": n, "deals": out}, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {n}/{len(pairs)} with an A/H discount at pricing")
    for r in out[:8]:
        if r.get("ah_discount_ipo_pct") is not None:
            print(f"   {r['code']} vs {r['a_share_code']}: A {r['a_close_cny']} CNY "
                  f"x {r['cnyhkd']} = HK${r['a_close_hkd']} vs offer HK${r['h_offer_price']} "
                  f"-> {r['ah_discount_ipo_pct']:+.2f}%")


if __name__ == "__main__":
    main()
