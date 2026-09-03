#!/usr/bin/env python3
"""EVERY deal, every price and return, checked three ways.

The three failure modes this exists to catch:

  1. WRONG THING EXTRACTED — the offer price is not a price (BAIGE shipped
     the listing-expenses line, HK$54,382,183) or is the wrong number from
     the right table (HESAI 154.99 vs the true 212.80).
  2. WRONG CALCULATION — a stored return that does not follow from the
     price series and the offer price it claims to use.
  3. CORPORATE ACTION IGNORED — a subdivision/consolidation/bonus issue that
     one source silently adjusted for and the other did not. This is the
     dangerous one, because BOTH series look internally consistent.

Nothing here imports fetch_prices' logic: returns are recomputed from the
RAW Tencent prints in h_paths.json against the stored offer price, and the
two independent sources are diffed against each other. Network-free — it
runs on the batches already on disk, so it can run in the gate battery.

Run:  python ipo_lib/audit_prices.py [--verbose]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HORIZONS = [("1w", 5), ("1m", 21), ("3m", 63)]      # trading-bar offsets
TOL_RET = 1.0        # pp — recomputed vs stored return
TOL_SRC = 0.5        # % — Yahoo debut close vs raw Tencent debut close
PRICE_LO, PRICE_HI = 0.05, 3000.0


def load(name):
    p = ROOT / "data" / "batches" / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else {"deals": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    deals = json.loads((ROOT / "data" / "deals.json").read_text())["deals"]
    prices = {r["code"]: r for r in load("prices")["deals"]}
    path_recs = load("h_paths")["deals"]
    paths = {r["code"]: r for r in path_recs}
    # the same non-trading-day filter merge measures on, so this gate checks
    # the real session list rather than the feed's placeholder bars
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from sessions import closed_days, real_sessions
    CLOSED = closed_days(path_recs)
    from corp_actions import load_actions
    splits = load_actions(ROOT)

    fail = {k: [] for k in ("listing_day", "price_band", "price_range", "proceeds",
                            "identity_day1", "identity_expop", "recompute",
                            "source_gap", "action_unhandled", "extreme")}
    checked = {k: 0 for k in fail}

    for x in deals:
        c, nm = x["code"], x["name"][:16]
        fp = x.get("final_price")
        pr = prices.get(c, {})
        pa = paths.get(c, {})
        sess = real_sessions(pa, CLOSED) if pa else []
        # keep the (offset, close) shape the checks below expect, but indexed
        # on REAL sessions only
        raw = [(i, v) for i, (_d, v) in enumerate(sess)]
        first_session = sess[0][0] if sess else None

        # ---- 0. the listing date must be a TRADING day --------------------
        # a Saturday listing date is the allotment-announcement date, and it
        # makes the two price sources disagree about which session is day 1
        ds = (x.get("ipo_date") or "")[:10]
        if ds:
            checked["listing_day"] += 1
            from datetime import date as _d
            if _d.fromisoformat(ds).weekday() >= 5:
                fail["listing_day"].append(f"{c} {nm}: listed on a "
                                           f"{'Saturday' if _d.fromisoformat(ds).weekday() == 5 else 'Sunday'}"
                                           f" ({ds})")

        # ---- 1. is the offer price a PRICE at all -------------------------
        if fp is not None:
            checked["price_band"] += 1
            if not (PRICE_LO <= fp <= PRICE_HI):
                fail["price_band"].append(f"{c} {nm}: offer {fp:,.2f}")
            lo, hi = x.get("price_range_lo"), x.get("price_range_hi")
            if lo and hi and hi >= lo:
                checked["price_range"] += 1
                # HK allows pricing BELOW the low end (downward adjustment),
                # never above the stated maximum
                if fp > hi * 1.001:
                    fail["price_range"].append(
                        f"{c} {nm}: offer {fp:g} above the max {hi:g}")
            gross, sh = x.get("gross_proceeds_hkdm"), x.get("offer_shares")
            if gross and sh:
                checked["proceeds"] += 1
                implied = sh * fp / 1e6
                # the share count may include an exercised over-allotment while
                # the stated gross is the BASE offering — a HK greenshoe is
                # capped at 15%, so that much excess is expected, not an error
                if implied and not (0.98 <= implied / gross <= 1.16):
                    fail["proceeds"].append(
                        f"{c} {nm}: {sh:,.0f} sh x HK${fp:g} = {implied:,.0f}m "
                        f"vs stated gross {gross:,.0f}m")

        # ---- 2. do the stored numbers follow from each other --------------
        d1 = x.get("first_day_return_pct")
        pop, oc = x.get("day1_open_pop_pct"), x.get("day1_open_close_pct")
        if None not in (d1, pop, oc):
            checked["identity_day1"] += 1
            if abs((1 + d1 / 100) - (1 + pop / 100) * (1 + oc / 100)) > 0.005:
                fail["identity_day1"].append(f"{c} {nm}: day-1 != pop x O->C")
        for h, _ in HORIZONS:
            r, a = x.get(f"ret_{h}_pct"), x.get(f"aftermkt_{h}_pct")
            if None not in (r, a, d1) and d1 != -100:
                checked["identity_expop"] += 1
                if abs((1 + r / 100) / (1 + d1 / 100) - (1 + a / 100)) > 0.005:
                    fail["identity_expop"].append(f"{c} {nm}: {h} ex-pop identity")

        # ---- 3. RECOMPUTE from the raw prints, independently --------------
        if fp and raw and first_session == (x.get("ipo_date") or "")[:10]:
            checked["recompute"] += 1
            # day-1 close is the first raw bar
            rd1 = 100 * (raw[0][1] / fp - 1)
            if d1 is not None and abs(rd1 - d1) > TOL_RET:
                fail["recompute"].append(
                    f"{c} {nm}: day-1 stored {d1:+.2f}% vs raw prints "
                    f"{rd1:+.2f}% (offer {fp:g}, close {raw[0][1]:g})")
            for h, nb in HORIZONS:
                stored = x.get(f"ret_{h}_pct")
                if stored is None or len(raw) <= nb:
                    continue
                rec = 100 * (raw[nb][1] / fp - 1)
                if abs(rec - stored) > max(TOL_RET, abs(stored) * 0.02):
                    fail["recompute"].append(
                        f"{c} {nm}: {h} stored {stored:+.2f}% vs raw prints "
                        f"{rec:+.2f}%")

        # ---- 4. TWO SOURCES on the same debut session ---------------------
        # prices.json is Yahoo for most deals; h_paths is always raw Tencent.
        # A gap means one of them adjusted for something the other did not.
        # compare the two sources only on the SAME session. Where Yahoo has no
        # bar on the listing date its first bar is a LATER day, so a price
        # difference is expected and is not evidence of an adjustment — the
        # local feed is used for those deals precisely because it has the day.
        yc, fd = pr.get("first_close"), pr.get("first_date")
        same_session = fd and fd == (x.get("ipo_date") or "")[:10]
        if yc and raw and same_session and "tencent" not in str(pr.get("price_src") or ""):
            checked["source_gap"] += 1
            gap = abs(yc / raw[0][1] - 1) * 100
            if gap > TOL_SRC:
                ratio = raw[0][1] / yc
                fail["source_gap"].append(
                    f"{c} {nm}: same session {fd}, Yahoo close {yc:g} vs raw "
                    f"{raw[0][1]:g} ({gap:.1f}% apart, ratio {ratio:.3f}) — "
                    f"one source is adjusting for something")

        # ---- 5. an action inside the window that nothing corrected --------
        # A round-factor jump is only EVIDENCE of an action; a hot small cap
        # doubling in a session looks identical. What distinguishes them is
        # whether the two sources still agree over a window containing the
        # jump — an action adjusted by one source and not the other makes them
        # diverge. Yahoo's own horizon returns live in the prices batch, so
        # they are the control.
        if raw and c not in splits:
            checked["action_unhandled"] += 1
            for i in range(1, len(raw)):
                a, b = raw[i - 1][1], raw[i][1]
                if not a:
                    continue
                r = b / a
                hit = next((cand for cand in (2, 3, 4, 5, 8, 10, 20)
                            if abs(r - cand) / cand < 0.04
                            or abs(r - 1 / cand) * cand < 0.04), None)
                if not hit:
                    continue
                # which stored horizon spans this jump?
                span = next((h for h, nb in HORIZONS if nb >= i), None)
                ylocal = pr.get(f"ret_{span}_pct") if span else None
                mine = x.get(f"ret_{span}_pct") if span else None
                if ylocal is not None and mine is not None \
                        and abs(ylocal - mine) < 1.0:
                    break        # both sources see the same move: it is real
                fail["action_unhandled"].append(
                    f"{c} {nm}: raw prints jump x{r:.3f} at day {raw[i][0]} "
                    f"and the sources disagree over {span} — likely a 1:{hit} "
                    f"action nothing corrected")
                break

        # ---- 6. extreme prints worth a human look -------------------------
        if d1 is not None and abs(d1) > 400:
            checked["extreme"] += 1
            fail["extreme"].append(f"{c} {nm}: day-1 {d1:+.1f}%")

    print(f"audit_prices: {len(deals)} deals")
    LABEL = {
        "listing_day": "listing date is a trading day",
        "price_band": "offer price is a plausible price",
        "price_range": "offer price not above the stated maximum",
        "proceeds": "shares x price == stated gross proceeds",
        "identity_day1": "day-1 == open-pop x open->close",
        "identity_expop": "ex-pop identities",
        "recompute": "returns recomputed from RAW prints",
        "source_gap": "Yahoo and raw Tencent agree on the debut",
        "action_unhandled": "no uncorrected corporate action in the window",
        "extreme": "no day-1 beyond +/-400%",
    }
    bad = 0
    for k, lab in LABEL.items():
        n = len(fail[k])
        bad += n
        mark = "OK  " if not n else "FAIL"
        print(f"  {mark} {lab:48s} {checked[k]:4d} checked, {n} problems")
        for line in fail[k][:(999 if args.verbose else 6)]:
            print(f"         {line}")
        if n > 6 and not args.verbose:
            print(f"         ... {n - 6} more (--verbose)")
    print("  RESULT:", "CLEAN" if not bad else f"{bad} PROBLEMS")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
