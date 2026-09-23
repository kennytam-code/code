#!/usr/bin/env python3
"""The 套路回撥 study: is the day-one pop allocation, or fundamentals?

Every number here is computed from data/deals.json at run time; nothing is
typed in. The desk's list of 27 deals is the starting point, the whole book
is the control. Output: data/batches/clawback_study.json (tables for the
Word note) and a printed readout.
"""
import json
import statistics as st
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK_27 = ("0300 9982 2881 1333 2625 2573 2450 2613 2553 1440 2497 9881 2651 2477 1334 "
           "2535 2505 2443 2550 1354 1471 2585 2587 2609 2582 2627 2691").split()


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(st.median(xs), 1) if xs else None


def share(xs, pred):
    xs = [x for x in xs if x is not None]
    return round(100 * sum(1 for x in xs if pred(x)) / len(xs)) if xs else None


def spearman(pairs):
    pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
    n = len(pairs)
    if n < 6:
        return None, n
    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    ra, rb = ranks([p[0] for p in pairs]), ranks([p[1] for p in pairs])
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return (round(cov / (va * vb), 2) if va and vb else None), n


def index_move(idx, day):
    """Same-day % move of an index series [(date, close)...] on `day`."""
    closes = idx.get("^HSI") if isinstance(idx, dict) else None
    out = {}
    for name, key in (("hsi", "^HSI"), ("hscei", "^HSCE")):
        ser = idx.get(key) or []
        for i, (d, c) in enumerate(ser):
            if d == day and i > 0:
                out[name] = round(100 * (c / ser[i - 1][1] - 1), 2)
                break
    return out


def cohort(x):
    """Where a deal sits on the international book."""
    i = x.get("oversub_intl_mult")
    if i is None:
        return "unknown"
    if i < 0.85:
        return "under (<0.85x)"
    if i < 1.0:
        return "just under (0.85-0.99x)"
    if i < 3:
        return "covered (1-3x)"
    if i < 10:
        return "3-10x"
    return "hot (>=10x)"


def regime(x):
    d = (x.get("ipo_date") or "")[:10]
    return "new rules (Aug-2025+)" if d >= "2025-08-04" else "old rules (PN18 50%)"


def main():
    deals = json.loads((ROOT / "data" / "deals.json").read_text())["deals"]
    by = {d["code"]: d for d in deals}
    idx = json.loads((ROOT / "data" / "batches" / "index_daily.json").read_text())
    for x in deals:
        x["_cohort"] = cohort(x)
        x["_regime"] = regime(x)
        mv = index_move(idx, (x.get("ipo_date") or "")[:10])
        x["_hsi_d1"], x["_hscei_d1"] = mv.get("hsi"), mv.get("hscei")

    out = {"as_of": date.today().isoformat(), "n_book": len(deals)}

    # ---- 1. the desk's 27, verified against the filings -----------------------
    rows = []
    for c in DESK_27:
        x = by.get(c)
        if not x:
            continue
        rows.append({k: x.get(k) for k in (
            "code", "name", "ipo_date", "sector", "deal_size_hkdm", "oversub_public_mult",
            "oversub_intl_mult", "intl_placees", "public_alloc_pct", "clawback",
            "day1_open_pop_pct", "first_day_return_pct", "day1_open_close_pct", "grey_pct",
            "day1_vol_x_retail", "day1_range_pct", "aftermkt_1w_pct", "aftermkt_1m_pct",
            "pe_ipo", "ps_ipo", "profitable_at_ipo", "rev_latest", "ni_latest", "is_h_share",
            "mktcap_ipo_hkdm", "cornerstone_pct")} | {
            "hsi_d1": x["_hsi_d1"], "hscei_d1": x["_hscei_d1"], "regime": x["_regime"],
            "cohort": x["_cohort"]})
    out["desk27"] = rows
    n_cluster = sum(1 for r in rows if r["cohort"] == "just under (0.85-0.99x)")
    out["desk27_summary"] = {
        "n": len(rows), "in_cluster": n_cluster,
        "not_in_cluster": [(r["code"], r["name"], r["oversub_intl_mult"]) for r in rows
                           if r["cohort"] != "just under (0.85-0.99x)"],
        "median_placees": med([r["intl_placees"] for r in rows if r["cohort"] == "just under (0.85-0.99x)"]),
        "median_public_alloc": med([r["public_alloc_pct"] for r in rows if r["cohort"] == "just under (0.85-0.99x)"]),
        "clawback_fired": Counter(r["clawback"] for r in rows if r["cohort"] == "just under (0.85-0.99x)"),
    }

    # ---- 2. cohorts across the book ------------------------------------------
    def stats(xs):
        return {
            "n": len(xs),
            "median_size_hkdm": med([x.get("deal_size_hkdm") for x in xs]),
            "median_public_x": med([x.get("oversub_public_mult") for x in xs]),
            "median_placees": med([x.get("intl_placees") for x in xs]),
            "median_public_alloc": med([x.get("public_alloc_pct") for x in xs]),
            "share_clawback_fired": share([x.get("clawback") for x in xs if x.get("clawback")],
                                          lambda v: v == "YES"),
            "median_grey": med([x.get("grey_pct") for x in xs]),
            "median_open": med([x.get("day1_open_pop_pct") for x in xs]),
            "median_close": med([x.get("first_day_return_pct") for x in xs]),
            "median_open_to_close": med([x.get("day1_open_close_pct") for x in xs]),
            "share_open_up": share([x.get("day1_open_pop_pct") for x in xs], lambda v: v > 0),
            "share_close_up": share([x.get("first_day_return_pct") for x in xs], lambda v: v > 0),
            "share_gave_back": share([x.get("day1_open_close_pct") for x in xs], lambda v: v < 0),
            "median_vol_x_retail": med([x.get("day1_vol_x_retail") for x in xs]),
            "median_range": med([x.get("day1_range_pct") for x in xs]),
            "median_1w_expop": med([x.get("aftermkt_1w_pct") for x in xs]),
            "median_1m_expop": med([x.get("aftermkt_1m_pct") for x in xs]),
            "median_3m_expop": med([x.get("aftermkt_3m_pct") for x in xs]),
            "median_pe": med([x.get("pe_ipo") for x in xs if x.get("pe_ipo") and x.get("pe_ipo") > 0]),
            "share_profitable": share([x.get("profitable_at_ipo") for x in xs], lambda v: v == "Y"),
            # is_h_share is set only where an A line exists: None means NO
            "share_ah": (round(100 * sum(1 for x in xs if x.get("is_h_share") in ("Y", True)) / len(xs))
                         if xs else None),
            "median_hsi_d1": med([x.get("_hsi_d1") for x in xs]),
        }
    order = ["under (<0.85x)", "just under (0.85-0.99x)", "covered (1-3x)", "3-10x", "hot (>=10x)", "unknown"]
    out["cohorts"] = {k: stats([x for x in deals if x["_cohort"] == k]) for k in order}

    # ---- 3. the clawback test: public >= 100x, intl just under vs covered ------
    hot_pub = [x for x in deals if (x.get("oversub_public_mult") or 0) >= 100]
    out["hot_public"] = {
        "just under": stats([x for x in hot_pub if x["_cohort"] == "just under (0.85-0.99x)"]),
        "covered (>=1x)": stats([x for x in hot_pub if x.get("oversub_intl_mult") is not None
                                 and x["oversub_intl_mult"] >= 1.0]),
    }
    # by regime, within the just-under cohort
    ju = [x for x in deals if x["_cohort"] == "just under (0.85-0.99x)"]
    out["just_under_by_regime"] = {r: stats([x for x in ju if x["_regime"] == r])
                                   for r in ("old rules (PN18 50%)", "new rules (Aug-2025+)")}
    out["just_under_by_year"] = {y: stats([x for x in ju if (x.get("ipo_date") or "")[:4] == y])
                                 for y in ("2021", "2022", "2023", "2024", "2025", "2026")}
    out["cluster_share_by_year"] = {
        y: {"n": len([x for x in deals if (x.get("ipo_date") or "")[:4] == y and x.get("oversub_intl_mult") is not None]),
            "just_under": len([x for x in ju if (x.get("ipo_date") or "")[:4] == y])}
        for y in ("2021", "2022", "2023", "2024", "2025", "2026")}

    # ---- 4. what explains open -> close inside the cluster --------------------
    held = [x for x in ju if (x.get("day1_open_close_pct") or 0) >= 0 and x.get("day1_open_close_pct") is not None]
    gave = [x for x in ju if (x.get("day1_open_close_pct") or 0) < 0]
    out["open_to_close"] = {"held_or_rose": stats(held), "gave_back": stats(gave)}
    out["open_to_close_corr"] = {}
    for lab, key in (("public alloc %", "public_alloc_pct"), ("placees", "intl_placees"),
                     ("deal size", "deal_size_hkdm"), ("public x", "oversub_public_mult"),
                     ("open pop", "day1_open_pop_pct"), ("grey", "grey_pct"),
                     ("vol x retail", "day1_vol_x_retail"), ("range", "day1_range_pct"),
                     ("cornerstone %", "cornerstone_pct"), ("P/E", "pe_ipo"),
                     ("HSI same day", "_hsi_d1")):
        rho, n = spearman([(x.get(key), x.get("day1_open_close_pct")) for x in ju])
        out["open_to_close_corr"][lab] = {"rho": rho, "n": n}
    # the volume signature, cluster only
    out["volume_signature"] = {
        "held_or_rose": {"median_vol_x_retail": med([x.get("day1_vol_x_retail") for x in held]),
                         "median_range": med([x.get("day1_range_pct") for x in held]), "n": len(held)},
        "gave_back": {"median_vol_x_retail": med([x.get("day1_vol_x_retail") for x in gave]),
                      "median_range": med([x.get("day1_range_pct") for x in gave]), "n": len(gave)},
    }

    # ---- 5. macro: does the index move on listing day explain anything? -------
    rho_all, n_all = spearman([(x.get("_hsi_d1"), x.get("first_day_return_pct")) for x in deals])
    rho_ju, n_ju = spearman([(x.get("_hsi_d1"), x.get("first_day_return_pct")) for x in ju])
    rho_open, n_open = spearman([(x.get("_hsi_d1"), x.get("day1_open_pop_pct")) for x in ju])
    out["macro"] = {"rho_hsi_vs_day1_all": (rho_all, n_all), "rho_hsi_vs_day1_cluster": (rho_ju, n_ju),
                    "rho_hsi_vs_open_cluster": (rho_open, n_open),
                    "cluster_median_hsi_d1": med([x.get("_hsi_d1") for x in ju]),
                    "cluster_share_hsi_up": share([x.get("_hsi_d1") for x in ju], lambda v: v > 0),
                    "cluster_big_pops_on_flat_index": [
                        (x["code"], x["name"], x.get("day1_open_pop_pct"), x.get("_hsi_d1"))
                        for x in ju if (x.get("day1_open_pop_pct") or 0) >= 50 and abs(x.get("_hsi_d1") or 0) < 1.0]}

    # ---- 6. grey vs pop, cluster -------------------------------------------
    g = [x for x in ju if x.get("grey_pct") is not None and x.get("day1_open_pop_pct") is not None]
    out["grey"] = {
        "n": len(g),
        "rho_grey_vs_open": spearman([(x["grey_pct"], x["day1_open_pop_pct"]) for x in g]),
        "median_open_minus_grey": med([x["day1_open_pop_pct"] - x["grey_pct"] for x in g]),
        "share_open_above_grey": share([x["day1_open_pop_pct"] - x["grey_pct"] for x in g], lambda v: v > 0),
        "share_close_above_grey": share([(x.get("first_day_return_pct") or 0) - x["grey_pct"] for x in g], lambda v: v > 0),
    }

    # ---- 7. fundamentals: cluster vs the rest -----------------------------------
    rest = [x for x in deals if x["_cohort"] not in ("just under (0.85-0.99x)", "unknown")]
    out["fundamentals"] = {"cluster": stats(ju), "rest": stats(rest)}
    # does P/E or profitability predict the pop inside the cluster?
    out["fund_corr"] = {}
    for lab, key in (("P/E", "pe_ipo"), ("P/S", "ps_ipo"), ("size", "deal_size_hkdm"),
                     ("public alloc %", "public_alloc_pct"), ("public x", "oversub_public_mult")):
        out["fund_corr"][lab] = spearman([(x.get(key), x.get("day1_open_pop_pct")) for x in ju])

    (ROOT / "data" / "batches" / "clawback_study.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1, default=str))

    # ---- readout ----------------------------------------------------------------
    print(f"book {len(deals)} | just-under cluster {len(ju)} | desk 27 in cluster {n_cluster}")
    print("\nCOHORTS (median):")
    print(f"{'cohort':26s} {'n':>4s} {'size':>6s} {'pub x':>7s} {'plcee':>5s} {'pub%':>5s} {'claw':>5s} {'grey':>6s} {'open':>6s} {'close':>6s} {'o->c':>6s} {'gave':>5s} {'volxR':>6s} {'rng':>5s} {'1m xp':>6s} {'P/E':>5s}")
    for k in order:
        s = out["cohorts"][k]
        print(f"{k:26s} {s['n']:>4d} {str(s['median_size_hkdm']):>6s} {str(s['median_public_x']):>7s} {str(s['median_placees']):>5s} "
              f"{str(s['median_public_alloc']):>5s} {str(s['share_clawback_fired']):>5s} {str(s['median_grey']):>6s} {str(s['median_open']):>6s} "
              f"{str(s['median_close']):>6s} {str(s['median_open_to_close']):>6s} {str(s['share_gave_back']):>5s} {str(s['median_vol_x_retail']):>6s} "
              f"{str(s['median_range']):>5s} {str(s['median_1m_expop']):>6s} {str(s['median_pe']):>5s}")
    print("\nPUBLIC >= 100x, by international book:")
    for k, s in out["hot_public"].items():
        print(f"  {k:16s} n={s['n']:3d} pub alloc {s['median_public_alloc']}% | clawback fired {s['share_clawback_fired']}% | open {s['median_open']} close {s['median_close']} o->c {s['median_open_to_close']} | vol x retail {s['median_vol_x_retail']}")
    print("\nOPEN -> CLOSE inside the cluster:")
    for k, s in out["open_to_close"].items():
        print(f"  {k:12s} n={s['n']:3d} open {s['median_open']} close {s['median_close']} | pub% {s['median_public_alloc']} placees {s['median_placees']} size {s['median_size_hkdm']} | vol x retail {s['median_vol_x_retail']} range {s['median_range']} | 1w xp {s['median_1w_expop']} 1m xp {s['median_1m_expop']}")
    print("  rank correlations with open->close:", {k: v['rho'] for k, v in out['open_to_close_corr'].items()})
    print("\nMACRO:", out["macro"]["rho_hsi_vs_day1_all"], out["macro"]["rho_hsi_vs_day1_cluster"], "cluster median HSI d1", out["macro"]["cluster_median_hsi_d1"])
    print("GREY (cluster):", out["grey"])
    print("CLUSTER BY YEAR:", out["cluster_share_by_year"])


if __name__ == "__main__":
    main()
