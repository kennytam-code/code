#!/usr/bin/env python3
"""End-to-end validation. Run after every build. Exit code 1 on hard failures.

1. Per-year deal counts vs official HKEX new-listing counts (delta explained by
   introductions/transfers — flagged only if book > official or delta > 25).
2. Per-year proceeds sums vs official IPO funds raised (tolerance ±10% — book is
   pre-greenshoe for part of the tail; direction should be book <= official).
3. Landmark spot-checks from official_counts.reference_deals (price ±1%, proceeds ±5%).
4. Schema: no duplicate codes, dates in window, subsector coverage, Other <5%,
   per-field completeness report (gaps named, never hidden).
5. Scorer parity: Python reimplementation of the shared scoring config prints
   top-5 for 3 sample targets (the Excel and JS implementations read the same
   weights; this is the reference output to eyeball against both).
"""
import json, math, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAIL = []
WARN = []


def load(p, default=None):
    f = ROOT / p
    return json.loads(f.read_text()) if f.exists() else default


def main():
    data = load("data/deals.json")
    deals = data["deals"]
    counts = load("data/official_counts.json", {})
    cfg = load("data/screener_config.json")

    # 4a duplicates / dates
    codes = [d["code"] for d in deals]
    if len(codes) != len(set(codes)):
        FAIL.append("duplicate codes in deals.json")
    bad_dates = [d["code"] for d in deals
                 if not ("2021-01-01" <= (d.get("ipo_date") or "") <= "2026-12-31")]
    if bad_dates:
        FAIL.append(f"{len(bad_dates)} deals with out-of-window dates: {bad_dates[:5]}")

    # 1/2 counts + proceeds vs official
    years = sorted({d["ipo_date"][:4] for d in deals if d.get("ipo_date")})
    print("== per-year reconciliation ==")
    ydata = counts.get("years", {})
    for y in years:
        sub = [d for d in deals if d["ipo_date"].startswith(y)]
        raised = sum(d.get("deal_size_hkdm") or 0 for d in sub)
        off = ydata.get(y, {})
        oc, om = off.get("new_listings_total"), off.get("equity_funds_raised_ipo_hkdm")
        line = f"  {y}: book {len(sub):3d} deals HK${raised/1000:7.1f}bn"
        if oc:
            line += f" | official {oc} listings"
            if len(sub) > oc:
                FAIL.append(f"{y}: book count {len(sub)} EXCEEDS official {oc}")
            elif oc - len(sub) > 25:
                WARN.append(f"{y}: book {len(sub)} vs official {oc} — delta {oc-len(sub)} (introductions/transfers?)")
        if om:
            line += f" HK${om/1000:.1f}bn"
            if raised > om * 1.10:
                FAIL.append(f"{y}: book proceeds exceed official by >10%")
            elif raised < om * 0.80:
                WARN.append(f"{y}: book proceeds {raised/1000:.1f}bn < 80% of official {om/1000:.1f}bn — extraction gaps")
        print(line)

    # 3 landmarks
    print("== landmark spot-checks ==")
    by_code = {d["code"]: d for d in deals}
    for ref in counts.get("reference_deals", []):
        c = str(ref.get("code", "")).lstrip("0").zfill(4)
        d = by_code.get(c)
        if not d:
            FAIL.append(f"landmark {ref.get('name')} ({c}) missing from book")
            continue
        for field, tol in (("final_price", 0.01), ("deal_size_hkdm", 0.05)):
            official = ref.get("gross_proceeds_hkdm" if field == "deal_size_hkdm" else field)
            got = d.get(field)
            if official and got:
                diff = abs(got - official) / official
                mark = "OK" if diff <= tol else "MISMATCH"
                if mark != "OK":
                    FAIL.append(f"{ref['name']} {field}: book {got} vs official {official}")
                print(f"  {ref.get('name', c):20s} {field:22s} book {got:>12} official {official:>12} {mark}")
            elif official and not got:
                WARN.append(f"{ref.get('name')} {field} missing in book (official {official})")

    # 4b completeness — with hard floors so a regression can never ship silently
    print("== completeness ==")
    n = len(deals)
    floors = {"sector": 97, "subsector": 97, "final_price": 99, "ipo_date": 99,
              "deal_size_hkdm": 95, "oversub_public_mult": 90,
              "first_day_return_pct": 90, "since_ipo_pct": 90,
              "sponsors": 60, "mktcap_ipo_hkdm": 90, "pct_of_cap": 99,
              "sponsors_cn": 95, "aftermkt_1m_pct": 90, "bench_1m_pct": 90,
              # v6: the Tencent fallback and AAStocks P&L pass made these floors
              # safe to raise — a regression below them means a source broke
              "first_day_return_pct": 99, "ret_1m_pct": 95, "ret_3m_pct": 85,
              "ni_latest": 90, "rev_latest": 90, "ps_ipo": 80,
              "cornerstone_investors": 65, "industry_en": 90, "sponsors_en": 90}
    for f in ("ipo_date", "final_price", "price_range_lo", "deal_size_hkdm",
              "oversub_public_mult", "first_day_return_pct", "since_ipo_pct",
              "sector", "subsector", "sponsors", "cornerstone_pct",
              "mktcap_ipo_hkdm", "pe_ipo", "ps_ipo",
              "rev_latest", "ni_latest", "profitable_at_ipo",
              "pct_of_cap", "sponsors_cn", "sponsors_en", "industry_en",
              "cornerstone_investors",
              "aftermkt_1m_pct", "bench_1m_pct", "mktcap_basis"):
        k = sum(1 for d in deals if d.get(f) is not None)
        pct = 100 * k // n
        print(f"  {f:24s} {k:4d}/{n} {pct:3d}%")
        if f in floors and pct < floors[f]:
            FAIL.append(f"{f} coverage {pct}% below the {floors[f]}% floor")
    # RESOLVED = a value OR a verified explanation of why none exists.
    print("  -- resolved = value or explained absence --")
    for f, note, floor in (("cornerstone_pct", "cornerstone_none", 80),
                           ("price_range_hi", "range_note", 98),
                           ("oversub_intl_mult", "intl_note", 98),
                           ("greenshoe_exercised_final", "shoe_note", 98),
                           ("pe_ipo", "pe_note", 98),
                           # every A/H cell is a discount or a stated reason
                           ("ah_discount_ipo_pct", "ah_note", 99),
                           ("ret_1m_pct", "ret_1m_note", 99),
                           ("sponsors", "sponsor_note", 99)):
        res = sum(1 for d in deals if d.get(f) is not None or d.get(note))
        print(f"  {f:26s} {res:4d}/{n} {100*res//n:3d}% resolved")
        if res < floor / 100 * n:
            FAIL.append(f"{f} resolved {100*res//n}% below {floor}%")
    # per-year day-1 coverage: regime bias must stay visible
    print("== per-year day-1 coverage ==")
    for y in sorted({d["ipo_date"][:4] for d in deals if d.get("ipo_date")}):
        sub = [d for d in deals if d["ipo_date"].startswith(y)]
        k = sum(1 for d in sub if d.get("first_day_return_pct") is not None)
        print(f"  {y}: {k}/{len(sub)}")
        if k < 0.85 * len(sub):
            WARN.append(f"{y} day-1 coverage {k}/{len(sub)} — analogs for this year are thin")
    other = sum(1 for d in deals if (d.get("subsector") or "").startswith("Other"))
    if other > 0.05 * n:
        FAIL.append(f"'Other' subsector {other}/{n} exceeds 5%")

    # 5 scorer parity reference
    print("== scorer top-5 reference (same config as Excel + JS) ==")
    W = cfg["weights"]

    row_of = {d["code"]: i + 1 for i, d in enumerate(deals)}

    def score(t, d):
        if d["code"] == t.get("code"):
            return -1e9
        gate = 1 if t.get("subsector") and d.get("subsector") == t["subsector"] else 0
        sec = 1 if t.get("sector") and d.get("sector") == t["sector"] else 0
        size = 0.0
        if t.get("size") and d.get("deal_size_hkdm"):
            size = max(0.0, 1 - abs(math.log10(d["deal_size_hkdm"] / t["size"])) /
                       cfg["size_proximity_log10_halfwidth"])
        dp, tp = d.get("profitable_at_ipo"), t.get("profitable")
        prof = 1 if (dp is not None and tp is not None and (dp == "Y") == bool(tp)) else 0
        dh, th = d.get("is_h_share"), t.get("is_h")
        ah = 1 if (dh is not None and th is not None and bool(dh) == bool(th)) else 0
        rec = 0.0
        if d.get("ipo_date") and t.get("ref_date"):
            days = (date.fromisoformat(t["ref_date"]) - date.fromisoformat(d["ipo_date"][:10])).days
            rec = max(0.0, 1 - days / cfg["recency_horizon_days"])
        return (W["subsector_match"] * gate + W["sector_match_fallback"] * sec * (1 - gate)
                + W["size_proximity"] * size + W["profitability_match"] * prof
                + W["h_share_match"] * ah + W["recency"] * rec
                + row_of[d["code"]] / 1e6)      # mirrors Excel's ROW()/1000000

    pipe = load("data/batches/pipeline.json", {"deals": []})["deals"]
    FX = 7.8

    def pipe_size(p):
        # same derivation the workbook and dashboard use: midpoint of the US$
        # range converted at the stated FX, when no HK$ figure is reported
        if p.get("expected_size_hkdm"):
            return p["expected_size_hkdm"]
        hi = p.get("expected_size_hi_usdm")
        if not hi:
            return None
        lo = p.get("expected_size_lo_usdm") or hi
        return round((lo + hi) / 2 * FX)

    targets = [{"name": p.get("name"), "sector": p.get("sector"), "subsector": p.get("subsector"),
                "size": pipe_size(p), "profitable": p.get("profitable_at_ipo"),
                "is_h": p.get("is_h_share"),
                "ref_date": date.today().isoformat()} for p in pipe[:3]]
    fixture = ROOT / "data" / "scorer_fixture.json"
    computed = {}
    for t in targets:
        top = sorted(deals, key=lambda d: -score(t, d))[:5]
        computed[t["name"]] = [d["code"] for d in top]
        print(f"  {t['name']} [{t.get('subsector')}] -> " +
              ", ".join(f"{d['name']}({d['code']})" for d in top))
    # lock the ranking: a silent change to weights or scoring shows up here
    if fixture.exists():
        prev = json.loads(fixture.read_text())
        for k, v in prev.items():
            if k in computed and computed[k] != v:
                WARN.append(f"scorer ranking changed for {k}: {v} -> {computed[k]}")
    else:
        fixture.write_text(json.dumps(computed, indent=1))
        print(f"  (wrote ranking fixture {fixture.name})")

    print()
    for w in WARN:
        print("WARN:", w)
    for f in FAIL:
        print("FAIL:", f)
    print(f"\n{len(FAIL)} failures, {len(WARN)} warnings")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
