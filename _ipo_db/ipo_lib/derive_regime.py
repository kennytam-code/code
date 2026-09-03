#!/usr/bin/env python3
"""Listing regime from the HKEX stock-short-name suffix convention.

  -B   Chapter 18A pre-revenue biotech
  -P   Chapter 18C specialist technology (pre-commercial)
  -W   weighted voting rights
  -S   secondary listing        -SW  secondary + WVR      -WP  WVR + 18C

This is mechanical (the suffix IS the regime under the Listing Rules), so it is
recorded as a deterministic derivation, not a judgment. Business classification
is separate — a -B company can be a device maker rather than a biotech.
"""
import json, re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "batches" / "deep_regime.json"

SUFFIX = [
    ("-SW", "Secondary + WVR"), ("-WP", "WVR + 18C"), ("-BW", "18A + WVR"),
    ("-B", "18A"), ("-P", "18C"), ("-W", "WVR"), ("-S", "Secondary"),
]


def main():
    roster = json.loads((ROOT / "data" / "batches" / "hkex_allotments.json").read_text())
    out = []
    for d in roster["deals"]:
        nm = d["stock_name_short"].strip().upper().replace("–", "-")
        regime = next((lbl for suf, lbl in SUFFIX if nm.endswith(suf)), "Standard")
        out.append({"code": d["code"], "listing_regime": regime,
                    "_prov": {"listing_regime": {
                        "src": f"HKEX short-name suffix ({nm})",
                        "status": "xchecked" if regime != "Standard" else "single"}}})
    OUT.write_text(json.dumps({"batch": "deep_regime", "deals": out,
                               "generated": datetime.now(timezone.utc).isoformat(timespec="seconds")},
                              ensure_ascii=False, indent=1))
    from collections import Counter
    print(f"wrote {OUT}:", dict(Counter(o["listing_regime"] for o in out)))


if __name__ == "__main__":
    main()
