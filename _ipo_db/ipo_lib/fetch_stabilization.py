#!/usr/bin/env python3
"""The FINAL over-allotment outcome, from the end-of-stabilization announcement.

The allotment announcement is filed the day before listing, so it can only ever
say the option "has not been exercised" — that is a not-yet, not a no. The real
answer lands ~30 days later in a notice titled like:

    END OF STABILIZATION PERIOD, NO STABILIZATION ACTIONS AND
    LAPSE OF OVER-ALLOTMENT OPTION

Wording varies a lot, so several styles are matched:
  "the Over-allotment Option had not been exercised"                -> lapsed
  "no over-allocation ... did not exercise the Over-allotment Option" -> lapsed
  "the Over-allotment Option has been fully exercised"              -> full
  "partially exercised ... 12,345,600 Shares"                       -> partial

Writes data/batches/stabilization.json (outcome + the notice's own URL).
"""
import json, re, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_hkex_filings import BASE, CACHE, doc_parts, get, load_stock_ids, search

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "batches" / "stabilization.json"
TEXT = ROOT / "scrape" / "text_cache"

# Titles vary far more than the wording inside. Ingenic filed its notice as
# plain "GLOBAL OFFERING OF INGENIC ..." with no stabilisation word anywhere in
# the title, so a title-only filter dropped it and the deal came back with no
# hyperlink at all. Inside the 15-75 day post-allotment window a "global
# offering" announcement is the stabilisation/over-allotment notice in practice,
# and the body regexes below still have to agree before an outcome is recorded.
TITLE_HINT = re.compile(r"stabilis|stabiliz|over-?allot|overallot|lapse|"
                        r"over-?alloc|global\s+offering|share\s+offer", re.I)
# does the DOCUMENT talk about stabilisation at all? Used to justify keeping the
# notice's hyperlink even when the outcome wording is one we cannot classify.
BODY_HINT = re.compile(r"stabilis|stabiliz|over-?allot|over-?alloc", re.I)
NUM = r"[\d,]+(?:\.\d+)?"

FULL = re.compile(r"Over-?allotment\s+Option\s+(?:has\s+been|was)\s+(?:fully\s+)?exercised\s+in\s+full|"
                  r"full\s+exercise\s+of\s+the\s+Over-?allotment\s+Option", re.I)
PARTIAL = re.compile(r"Over-?allotment\s+Option[^.]{0,120}?partially\s+exercised|"
                     r"partial(?:ly)?\s+exercise[^.]{0,80}?Over-?allotment\s+Option", re.I)
NOT_EX = re.compile(r"Over-?allotment\s+Option[^.]{0,160}?"
                    r"(?:had\s+not\s+been|has\s+not\s+been|was\s+not|not\s+been)\s+exercised|"
                    r"did\s+not\s+exercise\s+the\s+Over-?allotment\s+Option|"
                    r"Over-?allotment\s+Option[^.]{0,120}?(?:has\s+)?lapsed", re.I)
NO_OVERALLOC = re.compile(r"no\s+over-?alloc\w*", re.I)
# require real digits: NUM alone can match empty and blow up float()
EX_SHARES = re.compile(r"exercis\w+[^.]{0,140}?(\d[\d,]{4,})\s+(?:H\s+)?Shares", re.I)


def cache_key(url):
    return "stab_" + url.rsplit("/", 1)[-1]


def main():
    roster = json.loads((ROOT / "data" / "batches" / "hkex_allotments.json").read_text())
    deals = [d for d in roster["deals"] if d["board"] == "Main"]
    prev = {}
    if OUT.exists():
        prev = {r["code"]: r for r in json.loads(OUT.read_text())["deals"]}
    ids = load_stock_ids()
    TEXT.mkdir(exist_ok=True)

    out = []
    for i, d in enumerate(deals):
        code = d["code"]
        if code in prev and prev[code].get("greenshoe_exercised_final"):
            out.append(prev[code])
            continue
        rec = {"code": code}
        sid = ids.get(code)
        if sid:
            ann = datetime.fromisoformat(d["allot_announce_dt"]).date()
            # the stabilisation window closes 30 days after listing; allow slack
            rows = search(ann + timedelta(days=15), ann + timedelta(days=75),
                          10000, -2, -2, stock_id=sid, row_range=100)
            # rank: an explicit stabilisation/over-allotment title first, then
            # the looser "global offering" style, so the cheap certain match is
            # still tried before the broad one.
            strong = re.compile(r"stabilis|stabiliz|over-?allot|overallot|lapse", re.I)
            cands = [r for r in rows if strong.search(r.get("TITLE", ""))]
            cands += [r for r in rows if r not in cands
                      and TITLE_HINT.search(r.get("TITLE", ""))]
            for r in cands[:4]:
                parts = doc_parts(r["FILE_LINK"])
                txt = ""
                for _lbl, url in parts[:3]:
                    key = cache_key(url)
                    cached = TEXT / (key + ".txt")
                    if cached.exists():
                        txt += cached.read_text(errors="ignore")
                        continue
                    blob = get(url, binary=True)
                    if blob and blob[:4] == b"%PDF":
                        pdf = CACHE / key
                        pdf.write_bytes(blob)
                        try:
                            from pypdf import PdfReader
                            t = "\n".join((p.extract_text() or "")
                                          for p in PdfReader(str(pdf)).pages[:12])
                        except Exception:
                            t = ""
                        cached.write_text(t, errors="ignore")
                        txt += t
                if not txt:
                    continue
                flat = re.sub(r"\s+", " ", txt)
                if FULL.search(flat):
                    rec["greenshoe_exercised_final"] = "full"
                elif PARTIAL.search(flat):
                    rec["greenshoe_exercised_final"] = "partial"
                    m = EX_SHARES.search(flat)
                    if m:
                        rec["greenshoe_shares_exercised"] = float(m.group(1).replace(",", ""))
                elif NOT_EX.search(flat):
                    rec["greenshoe_exercised_final"] = (
                        "lapsed (no over-allocation)" if NO_OVERALLOC.search(flat) else "lapsed")
                # Keep the notice's HYPERLINK whenever the document is genuinely
                # about stabilisation, even if the outcome wording is one the
                # regexes above cannot classify. The link is the thing the desk
                # clicks to read it themselves, and withholding it because the
                # parse was inconclusive left 74 deals that HAVE a greenshoe
                # with nothing to click.
                resolved = bool(rec.get("greenshoe_exercised_final"))
                if resolved or BODY_HINT.search(flat):
                    rec["stabilization_title"] = r.get("TITLE", "")[:120]
                    rec["stabilization_link"] = BASE + r["FILE_LINK"]
                    rec["stabilization_dt"] = r.get("DATE_TIME")
                    if not resolved:
                        rec["stabilization_note"] = (
                            "notice located and linked; its outcome wording is "
                            "not one of the recognised forms, so the over-allotment "
                            "result is left blank rather than guessed")
                    break
        if len(rec) > 1:
            out.append(rec)
        if (i + 1) % 40 == 0:
            print(f"  {i+1}/{len(deals)}, {sum(1 for r in out if r.get('greenshoe_exercised_final'))} resolved",
                  flush=True)
            OUT.write_text(json.dumps({"batch": "stabilization", "deals": out},
                                      ensure_ascii=False, indent=1))
    n = sum(1 for r in out if r.get("greenshoe_exercised_final"))
    OUT.write_text(json.dumps(
        {"batch": "stabilization",
         "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(out), "resolved": n, "deals": out}, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {n}/{len(deals)} deals with a final over-allotment outcome")


if __name__ == "__main__":
    main()
