#!/usr/bin/env python3
"""ONE loader for corporate actions — auto-detected plus hand-curated.

Why this module exists: four call sites each did

    acts = load(auto); acts.update(load(manual))

and dict.update REPLACES the whole per-code list. WellCell (2477) has a
2-into-1 consolidation on 2025-03-31 (auto-detected) AND a 1-into-4
subdivision on 2026-04-21 (hand-added after the terminal verify). The
update() dropped the first, so only x4 was applied where the truth is x8 —
and Bloomberg's own print said so (2.640/8 = 0.330, which read as a CHECK).

The merge is BY DATE:
  * different dates  -> both events apply and COMPOUND (2477: x2 then x4 = x8)
  * same date        -> one event described twice; the hand entry wins and it
                        is counted ONCE (3881 CIDI is in both files at
                        2026-03-02 and must stay x10, never x100)

Entitlement issues (rights / open offers) live in their own file: they never
re-scale the traded print, so they must NEVER reach fetch_prices. They are
returned separately, for the Bloomberg-basis comparison only.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(p):
    if not p.exists():
        return {}
    return {k: v for k, v in json.loads(p.read_text()).items()
            if not k.startswith("_")}


def load_actions(root=None):
    """{code: [event, ...]} — auto + manual merged by date, sorted."""
    root = Path(root or ROOT)
    auto = _read(root / "data" / "auto_splits.json")
    manual = _read(root / "data" / "manual_splits.json")
    out = {}
    for code in set(auto) | set(manual):
        by_date = {}
        for ev in auto.get(code, []):          # auto first...
            by_date[ev["date"]] = ev
        for ev in manual.get(code, []):        # ...hand-curated wins the date
            by_date[ev["date"]] = ev
        out[code] = [by_date[d] for d in sorted(by_date)]
    return out


def load_entitlements(root=None):
    """{code: [event, ...]} — rights/open offers (BBG-basis comparison only)."""
    root = Path(root or ROOT)
    return _read(root / "data" / "entitlement_adjustments.json")


def price_factor(code, actions=None):
    """Cumulative factor applied to RAW PRINTS (splits/consolidations only)."""
    acts = actions if actions is not None else load_actions()
    f = 1.0
    for ev in acts.get(str(code), []):
        f *= float(ev.get("ratio") or 1)
    return f


def bbg_factor(code, actions=None, entitlements=None):
    """Cumulative factor between OUR raw print and BLOOMBERG's adjusted one:
    price-scale actions AND entitlement (TERP) adjustments."""
    f = price_factor(code, actions)
    ent = entitlements if entitlements is not None else load_entitlements()
    for ev in ent.get(str(code), []):
        f *= float(ev.get("factor") or 1)
    return f
