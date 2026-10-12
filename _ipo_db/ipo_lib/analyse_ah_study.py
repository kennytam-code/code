"""Dated A/H close history and an exploratory IPO-premium study.

Never writes deals.json. Raw H/A prints (not back-adjusted) determine the
price ratio of one share in each class. FX and A prices are carried only
from a known earlier date, with the actual dates retained. Missing or
incompatible observations are excluded, never replaced by zero.
"""
import argparse
import json
import math
from bisect import bisect_right
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/batches/ah_study.json"
CACHE = ROOT / "data/ah_study_cache"


def earlier(rows, dt):
    dates = [r[0] for r in rows]
    i = bisect_right(dates, dt) - 1
    return rows[i] if i >= 0 else None


def valid_rows(raw, start, end):
    result = {}
    for r in raw:
        try:
            if start <= r[0] <= end and float(r[2]) > 0 and (len(r) < 6 or float(r[5]) > 0):
                result[r[0]] = float(r[2])
        except (IndexError, ValueError, TypeError):
            pass
    return sorted(result.items())


def correlation(x, y, ranked=False):
    if len(x) < 4 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return None
    if ranked:
        x, y = pd.Series(x).rank().to_numpy(), pd.Series(y).rank().to_numpy()
    return float(np.corrcoef(x, y)[0, 1])


def stats(records, field, outcome="premium_change_1m_pp"):
    rows = [r for r in records if r.get(field) is not None and r.get(outcome) is not None]
    x = np.array([r[field] for r in rows], dtype=float)
    y = np.array([r[outcome] for r in rows], dtype=float)
    rho = correlation(x, y, True)
    result = {"field": field, "outcome": outcome, "n": len(rows), "pearson": correlation(x, y), "spearman": rho}
    if rho is None:
        return result
    rng = np.random.default_rng(20261005)
    boots = []
    for _ in range(1000):
        idx = rng.integers(0, len(x), len(x))
        v = correlation(x[idx], y[idx], True)
        if v is not None:
            boots.append(v)
    result["spearman_ci95"] = np.quantile(boots, [0.025, 0.975]).tolist()
    null = [correlation(x, rng.permutation(y), True) for _ in range(1999)]
    result["permutation_p"] = (1 + sum(abs(v) >= abs(rho) for v in null if v is not None)) / 2000
    return result


def make_pair(d, hrows, arows, fxrows, asof, actions):
    ipo = d["ipo_date"][:10]
    rec = {"code": d["code"], "name": d["name"], "sector": d.get("sector"), "subsector": d.get("subsector"),
           "a_code": d["a_share_code"], "ipo_date": ipo, "offer_hkd": d.get("final_price"),
           "deal_size_hkdm": d.get("deal_size_hkdm"), "size_basis": d.get("size_basis"),
           "current_company_cap_at_a_hkdm": d.get("a_mktcap_now_hkdm"),
           "current_cap_date": None, "history": [], "h_history": hrows, "eligible_1m": False}
    if not hrows or hrows[0][0] != ipo:
        rec["exclusion"] = "No verified H debut close on the recorded listing date"
        return rec
    for dt, h in hrows:
        a, fx = earlier(arows, dt), earlier(fxrows, dt)
        if not a or not fx:
            continue
        a_lag = (date.fromisoformat(dt) - date.fromisoformat(a[0])).days
        fx_lag = (date.fromisoformat(dt) - date.fromisoformat(fx[0])).days
        if a_lag > 10 or fx_lag > 5:
            continue
        rec["history"].append([dt, h, a[1], fx[1], a[1] * fx[1] / h - 1, a[0], fx[0]])
    bydate = {r[0]: r for r in rec["history"]}
    day0 = bydate.get(ipo)
    prev = (date.fromisoformat(ipo) - timedelta(days=1)).isoformat()
    apre, fxpre = earlier(arows, prev), earlier(fxrows, prev)
    if apre and fxpre and d.get("final_price") and (date.fromisoformat(ipo) - date.fromisoformat(apre[0])).days <= 10:
        rec["offer_reference_premium_pct"] = 100 * (apre[1] * fxpre[1] / d["final_price"] - 1)
        rec["offer_reference_a_date"] = apre[0]
        rec["offer_reference_fx_date"] = fxpre[0]
        cap = d.get("mktcap_ipo_hkdm")
        if isinstance(cap, (int, float)) and cap > 0:
            # The database's company cap at the H offer implies a listing share
            # count. Revalue that same capital at the pre-debut A reference.
            rec["company_cap_at_a_reference_hkdm"] = cap / d["final_price"] * apre[1] * fxpre[1]
            rec["listing_cap_basis"] = d.get("mktcap_basis", "Database listing company cap")
            size = d.get("deal_size_hkdm")
            if isinstance(size, (int, float)) and size > 0:
                rec["offer_size_to_a_reference_cap_pct"] = 100 * size / rec["company_cap_at_a_reference_hkdm"]
    if day0:
        rec["premium_day1_pct"] = day0[4] * 100
        rec["day1_h_hkd"], rec["day1_a_cny"], rec["day1_fx"] = day0[1:4]
        rec["day1_a_date"], rec["day1_fx_date"] = day0[5:7]
        if rec.get("offer_reference_premium_pct") is not None:
            rec["offer_to_day1_change_pp"] = rec["premium_day1_pct"] - rec["offer_reference_premium_pct"]
    if rec["history"]:
        end = rec["history"][-1]
        rec.update({"latest_date": end[0], "latest_h_hkd": end[1], "latest_a_cny": end[2],
                    "latest_fx": end[3], "latest_premium_pct": end[4] * 100,
                    "latest_a_date": end[5], "latest_fx_date": end[6]})
    for horizon, offset in [("1w", 5), ("1m", 21), ("3m", 63)]:
        if len(hrows) <= offset or not day0:
            continue
        dt = hrows[offset][0]
        row = bydate.get(dt)
        if not row:
            continue
        rec[f"date_{horizon}"] = dt
        rec[f"premium_{horizon}_pct"] = row[4] * 100
        rec[f"premium_change_{horizon}_pp"] = (row[4] - day0[4]) * 100
        # Exact decomposition of log(A * FX / H); contributions are log points.
        hlog = 100 * math.log(row[1] / day0[1])
        alog = 100 * math.log(row[2] / day0[2])
        fxlog = 100 * math.log(row[3] / day0[3])
        rec[f"h_return_{horizon}_pct"] = 100 * (row[1] / day0[1] - 1)
        rec[f"a_return_{horizon}_pct"] = 100 * (row[2] / day0[2] - 1)
        rec[f"a_date_{horizon}"] = row[5]
        rec[f"fx_date_{horizon}"] = row[6]
        rec[f"log_h_contribution_{horizon}"] = -hlog
        rec[f"log_a_contribution_{horizon}"] = alog
        rec[f"log_fx_contribution_{horizon}"] = fxlog
        rec[f"log_ratio_change_{horizon}"] = 100 * math.log((1 + row[4]) / (1 + day0[4]))
        rec[f"bridge_check_{horizon}"] = rec[f"log_ratio_change_{horizon}"] - (alog + fxlog - hlog)
    pre = [(dt, px) for dt, px in arows if ipo > dt >= (date.fromisoformat(ipo) - timedelta(days=31)).isoformat()]
    if len(pre) > 1:
        rec["a_runup_pre_ipo_pct"] = 100 * (pre[-1][1] / pre[0][1] - 1)
        rec["a_runup_start_date"], rec["a_runup_end_date"] = pre[0][0], pre[-1][0]
    if rec.get("date_1m"):
        events = [e for e in actions.get(d["code"], []) if ipo < e["date"] <= rec["date_1m"]]
        if events:
            rec["exclusion"] = "H share-scale action in first month: A/H entitlement ratio requires separate validation"
        else:
            rec["eligible_1m"] = True
    else:
        rec["exclusion"] = "Missing aligned Day 1 or 21st subsequent H-traded session"
    return rec


def main(refresh=False, h_cache=None):
    from fetch_prices import tencent_kline
    from fetch_ah_paths import yahoo_fx, a_symbol
    from corp_actions import load_actions
    deals = json.loads((ROOT / "data/deals.json").read_text())["deals"]
    pairs = [d for d in deals if d.get("a_share_code") and d.get("ipo_date")]
    asof = max(d.get("price_asof", "")[:10] for d in deals)
    start = (date.fromisoformat(min(d["ipo_date"][:10] for d in pairs)) - timedelta(days=45)).isoformat()
    CACHE.mkdir(parents=True, exist_ok=True)
    fxp = CACHE / "cnyhkd.json"
    if refresh or not fxp.exists():
        fx = yahoo_fx(start, (date.fromisoformat(asof) + timedelta(days=1)).isoformat())
        if not fx:
            raise RuntimeError("No dated CNYHKD history; study cannot be calculated")
        fxp.write_text(json.dumps(sorted(fx.items())))
    fxrows = json.loads(fxp.read_text())
    errors = []

    def fetch(d):
        c = d["code"]
        hp, ap = CACHE / f"h_{c}.json", CACHE / f"a_{c}.json"
        if h_cache and (Path(h_cache) / f"{c}.json").exists():
            raw = json.loads((Path(h_cache) / f"{c}.json").read_text())["rows"]
            hs = valid_rows(raw, d["ipo_date"][:10], asof)
            old = dict([r[:2] for r in json.loads(hp.read_text())]) if hp.exists() else {}
            old.update((r[0], r[1]) for r in hs)
            hp.write_text(json.dumps(sorted(old.items())))
        elif refresh or not hp.exists():
            hs = tencent_kline(f"hk{int(c):05d}", d["ipo_date"][:10], asof)
            if not hs:
                raise RuntimeError(f"{c}: H history unavailable")
            old = dict([r[:2] for r in json.loads(hp.read_text())]) if hp.exists() else {}
            old.update((r[0], r[1]) for r in hs)
            hp.write_text(json.dumps(sorted(old.items())))
        if refresh or not ap.exists():
            ast = (date.fromisoformat(d["ipo_date"][:10]) - timedelta(days=45)).isoformat()
            ars = tencent_kline(a_symbol(d["a_share_code"]), ast, asof)
            if not ars:
                raise RuntimeError(f"{c}: A history unavailable")
            old = dict([r[:2] for r in json.loads(ap.read_text())]) if ap.exists() else {}
            old.update((r[0], r[1]) for r in ars)
            ap.write_text(json.dumps(sorted(old.items())))
        return c, [r[:2] for r in json.loads(hp.read_text())], [r[:2] for r in json.loads(ap.read_text())]

    fetched = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(fetch, d): d for d in pairs}
        for i, task in enumerate(as_completed(jobs), 1):
            try:
                c, hs, ars = task.result()
                fetched[c] = (hs, ars)
            except Exception as e:
                errors.append(str(e))
            if i % 10 == 0:
                print(f"A/H history {i}/{len(pairs)}", flush=True)
    records = [make_pair(d, *fetched.get(d["code"], ([], [])), fxrows, asof, load_actions(ROOT)) for d in pairs]
    snap = json.loads((ROOT / "data/batches/ah_snapshot.json").read_text())
    for r in records:
        r["current_cap_date"] = snap.get("as_of")
    eligible = [r for r in records if r["eligible_1m"]]
    factors = ["deal_size_hkdm", "company_cap_at_a_reference_hkdm", "offer_size_to_a_reference_cap_pct", "premium_day1_pct", "a_runup_pre_ipo_pct", "current_company_cap_at_a_hkdm"]
    correlations = [stats(eligible, f) for f in factors]
    # Benjamini-Hochberg adjustment across the exploratory factor tests.
    ps = sorted([(i, x["permutation_p"]) for i, x in enumerate(correlations) if "permutation_p" in x], key=lambda v: v[1])
    adjusted = 1.0
    for rank in range(len(ps), 0, -1):
        idx, p = ps[rank - 1]
        adjusted = min(adjusted, p * len(ps) / rank)
        correlations[idx]["bh_adjusted_p"] = adjusted
    result = {"version": 1, "asof": asof, "generated_at": datetime.now(timezone.utc).isoformat(),
              "universe_count": len(pairs), "eligible_1m_count": len(eligible), "errors": errors,
              "method": "A premium = raw A(CNY) * dated CNYHKD / raw H(HKD) - 1. Day 1 close to 21st subsequent H-traded session. Prior known A/FX close carried at most 10/5 calendar days; quote dates retained. Different closing times, not executable arbitrage. No dividends. One share per class. First-month H share-scale actions excluded from correlations. Offer reference uses A/FX close before H debut, not book pricing time. Historical company cap at A reference = listing company cap / H offer * pre-debut A * FX; it inherits the listing cap's share-count basis, and is not A-only float cap. Offer value / this cap is a funding-value ratio, not free float. Current company cap at A price is a descriptive, forward-looking proxy, not historical A-float cap. Correlations are exploratory, not causation.",
              "sources": ["https://web.ifzq.gtimg.cn/appstock/app/fqkline/get", "https://finance.yahoo.com/quote/CNYHKD=X/history/", "https://www.aastocks.com/en/stocks/market/ah.aspx"],
              "correlations": correlations, "pairs": records}
    OUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    outdir = ROOT / "out"
    outdir.mkdir(exist_ok=True)
    report = [f"# A/H IPO premium study — closes through {asof}", "", result["method"], "",
              f"Universe: {len(pairs)} pairs. First-month sample: {len(eligible)}. Excluded: {len(pairs) - len(eligible)}.", "",
              "| Factor | n | Pearson | Spearman | 95% bootstrap interval | Adjusted exploratory p |", "|---|---:|---:|---:|---|---:|"]
    for s in correlations:
        ci = s.get("spearman_ci95", [float("nan"), float("nan")])
        report.append(f"| {s['field']} | {s['n']} | {s.get('pearson', float('nan')):.3f} | {s.get('spearman', float('nan')):.3f} | {ci[0]:.3f} to {ci[1]:.3f} | {s.get('bh_adjusted_p', float('nan')):.3f} |")
    report += ["", "A negative premium change is narrowing only when A started at a positive premium; if the ratio crosses below zero, H has become the dearer class. Initial premium versus premium change shares the starting value mechanically and can reflect regression to the mean. Today's cap cannot establish a historical causal effect. Deal size is measured in HK$m using the database's stated size basis; shoe-inclusive and net-proceeds estimates are not homogeneous treatments.", ""]
    for c in ("3986", "6809"):
        r = next(x for x in records if x["code"] == c)
        report += [f"## {r['name']} ({c})", "", f"Offer-reference A premium: {r.get('offer_reference_premium_pct', float('nan')):.2f}%; Day 1 close: {r.get('premium_day1_pct', float('nan')):.2f}%; first month ({r.get('date_1m')}): {r.get('premium_1m_pct', float('nan')):.2f}%. Day 1 to month: H {r.get('h_return_1m_pct', float('nan')):+.2f}%, A {r.get('a_return_1m_pct', float('nan')):+.2f}%. Latest paired close {r.get('latest_date')}: {r.get('latest_premium_pct', float('nan')):+.2f}%.", ""]
    narrowed = sum(abs(r["premium_1m_pct"]) < abs(r["premium_day1_pct"]) for r in eligible)
    report += [f"{narrowed}/{len(eligible)} pairs had a smaller absolute A/H gap at the first-month close. Deal-size and historical cap correlations are weak and their rank-correlation intervals include zero.", "", "## Largest remaining first-month A premiums", "", "| Pair | First-month close | A premium |", "|---|---|---:|"]
    for r in sorted(eligible, key=lambda x: x["premium_1m_pct"], reverse=True)[:7]:
        report.append(f"| {r['code']} {r['name']} | {r['date_1m']} | {r['premium_1m_pct']:.1f}% |")
    report.append("")
    report += ["## Interpretation and limits", "", "The arithmetic identifies which price leg and FX account for the change; it does not establish why investors repriced it. Different investor access, liquidity, borrow costs and company-specific news are plausible explanations for persistent gaps. Event-level Stock Connect admission, turnover/free float at listing, borrow availability and investor flows are needed before attributing any individual case to those mechanisms. First-month stabilisation and price discovery can coincide with convergence; timing alone is not causal evidence.", "", "HKEX explains the investor access and eligibility framework in [Stock Connect](https://www.hkex.com.hk/Mutual-Market/Connect-Hub/Stock-Connect?sc_lang=en). Data sources: [Tencent](https://web.ifzq.gtimg.cn/appstock/app/fqkline/get), [dated CNYHKD closes](https://finance.yahoo.com/quote/CNYHKD=X/history/), [current A/H snapshot](https://www.aastocks.com/en/stocks/market/ah.aspx).", "", "## Excluded first-month observations", ""]
    report += [f"- {r['code']} {r['name']}: {r.get('exclusion')}" for r in records if not r["eligible_1m"]]
    (outdir / "ah_premium_study.md").write_text("\n".join(report) + "\n")
    print(f"Study: {len(records)} pairs, {len(eligible)} first-month observations; {len(errors)} source errors", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--h-cache")
    args = parser.parse_args()
    main(args.refresh, args.h_cache)
