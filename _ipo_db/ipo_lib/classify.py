#!/usr/bin/env python3
"""Sector / subsector assignment for every Main Board IPO in the roster.

Each code was assigned by reading the business-overview prose extracted from its
own prospectus (data/classify_input.txt, built by make_classify_sheet.py) plus
the issuer's known business. This is an analyst JUDGMENT layer — it merges with
status "judgment" (amber in the workbook) so it is never mistaken for a filed
figure. Edit the groups below and re-run to reclassify; taxonomy.json defines
the allowed values.

Deliberate conventions, so comps stay meaningful:
  * a Chapter 18A "-B" ticker is NOT automatically a biotech — device makers
    (MedBot, Acotec, CardioFlow ...) classify as Medical devices; the 18A fact
    lives in listing_regime instead.
  * automotive AI-silicon designers (Horizon Robotics, Black Sesame) sit with
    AI chips & semis; LiDAR / robotaxi / robot builders sit in Robotics & AD.
  * hydrogen fuel-cell names sit with Batteries / energy storage so the new-
    energy power-system peers comp against each other.
"""
import json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "batches" / "deep_classify.json"

GROUPS = {
"llm": "0100 2513",
"ai_app": "0020 2121 6682 2438 2228 9678 1384 2718 3696 2706 6636 1392 1956 2723 7656 1879",
"ai_chips": "6939 2149 2533 2577 2631 1304 2658 2676 6082 9903 0501 3986 6809 0600 2701 2726 3625 3277 3310 6675 3661 9630 9971 2249 2551 9660",
"dc_cloud": "2512 2567",
"robotics_ad": "1274 9880 2498 2432 2431 2590 2525 2670 2026 3881 6600 2715 2729 1021 1236 6871 1511 6106 3752 6880 7687 6656.SKIP",
"smart_hw": "2385 0300 0638 6166 9611 2768 3268 1989 3355 2476 3296 6810 0901 3388 1688 1191 0668 1770 2475 6951 1377 3308 6613 9881 2580 2619 2581 2543",
"saas": "1473 2167 2391 2392 2436 1204 2440 9669 2416 2479 6657 2576 2586 6959 2635 3317 6651 0068 2272 2597 2655 2687 2556",
"internet": "1024 2518 9888 9626 9961 2209 2177 9899 9898 9878 2390 2420 3650 9690 2550 2559 9680 2643 2605 2076 2685 7618 2603",
"fintech": "6608 9959 3660 2598 2458 3887 2483",
"biotech_prerev": "6622 2171 2162 2137 1228 2256 2197 2257 2157 2179 1244 6955 2480 2105 6990 1541 2496 2511 2509 2487 2898 2563 2410 2561 9606 2629 2565 2617 2592 9887 2627 2591 2595 2630 2575 3378 2396 6938 7630 6872 1779 6132 2335 9637 2659 2493 7666 2315 6628",
"biopharma_comm": "2161 0013 6660 2566 2652 2637 6915 2477 1276",
"medtech": "2160 2170 6699 2190 2276 2185 6609 6669 2216 2235 2252 2172 6929 2427 2291 2407 9877 6922 2297 2675 6681 2526 1609 1187 2697 2455.SKIP",
"cxo": "6127 6821 9960 2325 6667 2415 9860 2268 3880",
"digital_health": "9600 2158 2159 2192 2251 9886 0314 2361 9885 9686 6086 2587 2506 2656 2609 2677 9955",
"providers": "2219 2279 1406 6639 1947 2453 2522 2508 2651",
"tcm": "1643 2273 2593 2667",
"fnb_chain": "2150 9869 1405 2555 0999 1364 2097 2589 6831 2408",
"food_bev": "1927 9858 9985 2147 2425 6979 9676 2419 1497 6911 2460 2530 3288 6603 2648 6980 9980 2714 6658 6715 2797 0664 2497 2573",
"apparel_lux": "9638 6181 2585 6168 2583",
"beauty": "6601 2367 2145 2373 1318 6883 2657",
"consumer_svc": "6913 2175 2469 2536",
"nev_oem": "9868 2015 9863 9973 9927 2451",
"auto_parts": "2457 2531 2050 2889 2650 0699 2632 2261 1334",
"retail": "2347 9896 1880 2411 2517 2429 2473 2443 2549 2519 2625 0325 2720 2290 6909",
"banks": "9889 2596",
"insurance": "2378 6963 1471 2621 2661 2672 1828",
"brokers_am": "6686 9636 1973 2691",
"capgoods": "2153 2155 2285 2260 6680 2499 9930 2507 2571 2613 6031 3200 2692 3952 0537 7688 0470 1333",
"battery_ess": "3931 0666 2465 2582 2570 9663 2402 3677 3750 2579 6960 6067 6656",
"solar_wind": "2865 1081",
"logistics": "2129 2618 9699 2246 2418 2482 2409 2490 1519 2516 2510 6936 2505 1641 2649",
"construction": "1855 1440 1413 2195 2187 1489 2350 2433 2442 2515 2520 9639 2503 2535 1111 2671",
"mining": "9696 2237 2245 2489 6693 2610 3858 2546 2693 3636 6228 2259",
"chemicals": "6616 2372 2459 2439 9879 2502 2881 2560 2569 9609 9981 2553 6745",
"oil_gas_util": "6661 1407 2265 2321 2481",
"developers": "6611",
"prop_mgmt": "2146 9608 6668 3658 9982 6626 1965 2165 2215 2205 2210 2370 2352 2376 2152 2602 2271 1354 2529 2539 2521 0606 2270 2455",
"reit_light": "2191",
"telecom": "2545 2495",
"media_ad": "2125 1490 1948 9857 2250 2422 6610 6696 2540 2405 2486 6683 1284 9890 2306 6698 2695 6633",
"other": "2450 2501 0917 6090 6687 2698 2788 1768 1855.SKIP",
}

SECTOR_OF = {}


def main():
    tax = json.loads((ROOT / "data" / "taxonomy.json").read_text())
    label, sector = {}, {}
    for sec, subs in tax["sectors"].items():
        for s in subs:
            label[s["id"]] = s["label"]
            sector[s["id"]] = sec
    roster = json.loads((ROOT / "data" / "batches" / "hkex_allotments.json").read_text())
    valid = {d["code"] for d in roster["deals"]}

    assigned, dupes, unknown = {}, [], []
    for sub, codes in GROUPS.items():
        if sub not in label:
            sys.exit(f"unknown subsector id in GROUPS: {sub}")
        for c in codes.split():
            if c.endswith(".SKIP"):
                continue
            c = c.zfill(4)
            if c not in valid:
                unknown.append(c)
                continue
            if c in assigned:
                dupes.append((c, assigned[c], sub))
                continue
            assigned[c] = sub

    main_codes = {d["code"] for d in roster["deals"] if d["board"] == "Main"}
    missing = sorted(main_codes - set(assigned))
    out = [{"code": c, "sector": sector[s], "subsector": label[s],
            "_prov": {"sector": {"src": "analyst classification from prospectus overview",
                                 "status": "judgment"},
                      "subsector": {"src": "analyst classification from prospectus overview",
                                    "status": "judgment"}}}
           for c, s in sorted(assigned.items())]
    OUT.write_text(json.dumps({"batch": "deep_classify", "deals": out,
                               "generated": datetime.now(timezone.utc).isoformat(timespec="seconds")},
                              ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {len(out)} classified")
    if dupes:
        print(f"  DUPLICATES ({len(dupes)}):", dupes[:10])
    if unknown:
        print(f"  not in roster ({len(unknown)}):", unknown[:10])
    if missing:
        print(f"  UNCLASSIFIED Main Board ({len(missing)}): {' '.join(missing)}")
    from collections import Counter
    print("  by sector:", dict(Counter(o["sector"] for o in out)))


if __name__ == "__main__":
    main()
