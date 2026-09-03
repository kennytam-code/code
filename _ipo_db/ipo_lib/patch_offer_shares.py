#!/usr/bin/env python3
"""Re-parse ONLY the offer-share count from the allotment announcement header.

Every allotment announcement opens with the same block:

    GLOBAL OFFERING
    Number of Offer Shares under the Global Offering : 8,076,400 H Shares
    Number of Hong Kong Offer Shares                 :   808,000 H Shares
    Number of International Offer Shares             : 7,268,400 H Shares

`RE_SHARES` in extract_prospectus.py never matched that phrasing (it wants
"total number of ... Offer Shares" or a price-anchored form), so deals whose
gross proceeds were also unstated fell all the way through to net proceeds.
Jenscare was published as a HK$32m deal — the greenshoe's figure — when the
offering was 8,076,400 shares at HK$27.80 = HK$224.5m.

It also records whether the offering includes SALE shares. Weibo's 11,000,000
shares were "5,500,000 New Shares and 5,500,000 Sale Shares": the company
received net proceeds on its half only, so the deal size and the company's
net take legitimately differ by ~2x, and the merge's net-proceeds bracket
must not treat that as a bad parse.

PIPELINE STAGE `patch-offer-shares`, in both ipo.py and the desk bundle, run
after every other writer of extracted_allotments.json. Left outside the
pipeline it would be undone by the next plain refresh, taking 262 re-read
share counts with it.

Run:  python ipo_lib/patch_offer_shares.py [--apply]
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT = ROOT / "scrape" / "text_cache"
BATCH = ROOT / "data" / "batches" / "extracted_allotments.json"
HEAD = 20000          # the block is always in the announcement's first pages

RE_HDR = re.compile(
    r"Number\s+of\s+(?:Offer|Global\s+Offer)\s+Shares\s+under\s+the\s+"
    r"Global\s+Offering\s*[::]\s*([\d,]+)", re.I)
RE_HDR2 = re.compile(r"Number\s+of\s+Offer\s+Shares\s*[::]\s*([\d,]+)", re.I)
# Both phrasings appear: "(including 5,500,000 New Shares and 5,500,000 Sale
# Shares)" (Weibo) and "comprising 291,720,000 new Shares and 81,000,000 Sale
# Shares" (Tat Hong). Missing the second form left the audit flagging deals
# whose gross legitimately covers the new shares only.
RE_SALE = re.compile(
    r"(?:including|comprising)\s+[\d,]+\s+new\s+Shares?\s+and\s+([\d,]+)\s+Sale\s+Shares?",
    re.I)


def main(apply_it):
    data = json.loads(BATCH.read_text())
    by_code = defaultdict(list)
    for p in sorted(TEXT.glob("allot_*.txt")):
        m = re.match(r"allot_(\d{4})_", p.name)
        if m:
            by_code[m.group(1)].append(p)

    changed, agreed, sale, none_found = [], 0, [], 0
    for rec in data["deals"]:
        got, sale_sh = None, None
        for p in by_code.get(rec["code"], []):
            txt = re.sub(r"\s+", " ", p.read_text(errors="ignore")[:HEAD])
            m = RE_HDR.search(txt) or RE_HDR2.search(txt)
            if m:
                got = float(m.group(1).replace(",", ""))
                s = RE_SALE.search(txt)
                sale_sh = float(s.group(1).replace(",", "")) if s else None
                break
        if got is None:
            none_found += 1
            continue
        old = rec.get("offer_shares")
        if old is None or abs(got - old) / max(got, old) > 0.005:
            changed.append((rec["code"], old, got))
            if apply_it:
                rec["offer_shares"] = got
                rec["offer_shares_snip"] = (
                    f"allotment header: Number of Offer Shares under the Global "
                    f"Offering = {got:,.0f}")
        else:
            agreed += 1
        if sale_sh:
            sale.append((rec["code"], got, sale_sh))
            if apply_it:
                rec["sale_shares"] = sale_sh

    print(f"header found on {len(data['deals']) - none_found}/{len(data['deals'])} deals"
          f" | no header: {none_found}")
    print(f"agreed with the existing count: {agreed}")
    print(f"corrected / filled: {len(changed)}")
    for c, old, new in changed[:25]:
        print(f"  {c}  {str(old):>14} -> {new:>14,.0f}")
    if len(changed) > 25:
        print(f"  ... {len(changed) - 25} more")
    print(f"offerings that include SALE shares (company's net covers its half "
          f"only): {len(sale)}")
    for c, tot, s in sale[:12]:
        print(f"  {c}  {tot:>12,.0f} offered, of which {s:>12,.0f} sold by holders")

    if apply_it:
        data["offer_shares_patch"] = (
            "offer_shares re-read from the allotment announcement header "
            "('Number of Offer Shares under the Global Offering'); sale_shares "
            "recorded where the offering includes secondary stock")
        BATCH.write_text(json.dumps(data, ensure_ascii=False, indent=1))
        print(f"\nwrote {BATCH}")
    else:
        print("\n(dry run — pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main("--apply" in sys.argv))
