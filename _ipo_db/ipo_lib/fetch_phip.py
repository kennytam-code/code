#!/usr/bin/env python3
"""The REAL pipeline: every live listing application on HKEX.

HKEX publishes all active Application Proofs / PHIPs as plain JSON — the same
data the "New Listing Information - AP & PHIP" page renders:

    /ncms/json/eds/appactive_app_sehk_e.json   (~330 live applications)

Row shape: {"id", "d" first-filing date, "a" applicant name, "s" status,
            "sD"/"sA" counters, "ls" latest submissions [{d, nF, nS1, u1, u2}],
            "ps" previous submissions, "hasPhip", "postingDate"}

A PHIP posted means the deal has cleared the listing hearing — it is weeks, not
months, from pricing. Those are the ones worth watching, so they sort first.

Writes data/batches/phip_pipeline.json.
"""
import json, re, sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "batches" / "phip_pipeline.json"
# Two feeds, per the page's own toggle (app_common.js builds the filename):
#   appactive_app_sehk_e     applicants with an Application Proof ONLY
#   appactive_appphip_sehk_e applicants who have POSTED A PHIP = hearing cleared,
#                            i.e. days-to-weeks from launch. Those matter most.
FEEDS = {
    "PHIP posted (hearing cleared)": "https://www1.hkexnews.hk/ncms/json/eds/appactive_appphip_sehk_e.json",
    "Application Proof only": "https://www1.hkexnews.hk/ncms/json/eds/appactive_app_sehk_e.json",
}
DOCBASE = "https://www1.hkexnews.hk/app/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def dparse(s):
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except Exception:
        return None


def main():
    today = date.today()
    out, gen, rows, seen = [], None, [], set()
    for stage, url in FEEDS.items():
        r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
        r.raise_for_status()
        feed = r.json()
        gen = gen or feed.get("genDate") or feed.get("uDate")
        for a in feed.get("app", []):
            a["_stage"] = stage
            rows.append(a)
    for a in rows:
        if a.get("id") in seen:
            continue
        seen.add(a.get("id"))
        first = dparse(a.get("d", ""))
        subs = (a.get("ls") or []) + (a.get("ps") or [])
        latest, latest_kind, link = None, None, None
        for s in subs:
            d = dparse(s.get("d", ""))
            kind = (s.get("nF") or s.get("nS1") or "").strip()
            if d and (latest is None or d > latest):
                latest, latest_kind = d, kind
                u = s.get("u1") or s.get("u2")
                link = DOCBASE + u if u else None
        # An applicant files several documents on the same day and the prospectus
        # is rarely the first of them — Shein, Mech-Mind and Direct Drive were all
        # parsed from an 8KB "OC Announcement - Appointment" instead of their
        # 300KB+ PHIP. Always prefer the actual listing document.
        doc = None
        for s in subs:
            label = ((s.get("nF") or "") + " " + (s.get("nS1") or "")).lower()
            if re.search(r"phip|post hearing|application proof|full version", label):
                d = dparse(s.get("d", ""))
                u = s.get("u1") or s.get("u2")
                if u and (doc is None or (d and d > doc[0])):
                    doc = (d, DOCBASE + u, (s.get("nF") or s.get("nS1") or "").strip())
        if doc:
            link, latest_kind = doc[1], doc[2] or latest_kind
        has_phip = a["_stage"].startswith("PHIP") or any(
            re.search(r"PHIP|Post Hearing", (s.get("nF") or "") + (s.get("nS1") or ""), re.I)
            for s in subs)
        terminated = any(re.search(r"Termination", (s.get("nS1") or "") + (s.get("nF") or ""), re.I)
                         for s in subs)
        out.append({
            "applicant": a.get("a"),
            "app_id": a.get("id"),
            "first_filing": first.isoformat() if first else None,
            "latest_submission": latest.isoformat() if latest else None,
            "latest_kind": latest_kind,
            "has_phip": has_phip,
            "stage": ("PHIP posted (hearing cleared)" if has_phip
                      else "Application Proof only"),
            "sponsor_terminated": terminated,
            "days_in_process": (today - first).days if first else None,
            "doc_link": link,
            "_subs": subs,          # raw submissions — the OC announcement lives here
        })
    # PHIP-stage deals are ACTIVE pipeline: download and parse their PHIP so
    # they arrive in the screener with financials and a provisional subsector
    try:
        _parse_phip_docs([a for a in out if a["has_phip"] and not a["sponsor_terminated"]])
    except Exception as e:
        print(f"  PHIP parse skipped: {e}")

    # PHIP first, then most recently active
    out.sort(key=lambda x: (not x["has_phip"], x["latest_submission"] or ""), reverse=False)
    out.sort(key=lambda x: (x["has_phip"], x["latest_submission"] or ""), reverse=True)
    for x in out:                    # working field only, not part of the batch
        x.pop("_subs", None)
    OUT.write_text(json.dumps(
        {"batch": "phip_pipeline", "source": "hkexnews appactive_app_sehk_e.json",
         "feed_generated": gen,
         "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "count": len(out),
         "with_phip": sum(1 for x in out if x["has_phip"]),
         "applications": out}, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {len(out)} live applications, "
          f"{sum(1 for x in out if x['has_phip'])} with a PHIP posted")


# Analyst labels for live applicants, matched on a name fragment. The keyword
# classifier agrees with the hand labels only ~49% of the time and it put Shein
# in "Fintech platform"; a pipeline name is the one place a wrong sector is
# expensive, so these override it exactly like classify.py's codes do for
# listed deals. Anything not listed here keeps the provisional keyword label.
PIPELINE_LABELS = {
    "shein": "Internet platform / e-commerce",
    "tanboer": "Apparel / luxury",
    "direct drive": "Robotics & autonomous driving",
    "mech-mind": "Robotics & autonomous driving",
    "ingenic": "AI chips & semis",
    "ekh": "Logistics",
    # infusion systems / surgical devices / IVD (Shenzhen; PHIP 2026-08)
    "medcaptain": "Medical devices",
}


def _a_share(txt):
    """Spot an existing mainland listing and return its yfinance-style code.

    An A-to-H applicant is a different animal from a first-time issuer: the deal
    prices off a live quote, so the pipeline row must say so. The PHIP always
    names the exchange and the stock code of the A line.
    """
    flat = re.sub(r"\s+", " ", txt[:400000])
    # Is the APPLICANT itself already listed on the mainland? The statement is
    # made about "the Company"/"our Company" — a PHIP also describes dozens of
    # third parties as "a company listed on the ... Stock Exchange with stock
    # code NNNNNN", and reading those gave Ingenic the code of Huaqin, one of
    # its own investors. Establish the fact first, take a code only if the
    # document ties one to the issuer.
    self_listed = re.search(
        r"(?:A\s+Shares\s+of\s+(?:the|our)\s+Company|our\s+A\s+Shares)[^.]{0,120}?"
        r"(?:have\s+been|are|were)\s+listed\s+on\s+(?:the\s+)?"
        r"(ChiNext(?:\s+of\s+the\s+Shenzhen)?|STAR\s+Market|Shanghai|Shenzhen|Beijing)"
        r"|LISTING\s+ON\s+THE\s+(CHINEXT|STAR\s+MARKET|SHANGHAI|SHENZHEN|BEIJING)", flat, re.I)
    if not self_listed:
        return {}
    where = next((g for g in self_listed.groups() if g), "").lower()
    venue = ("Shenzhen ChiNext" if "chinext" in where else
             "Shanghai STAR Market" if "star" in where else
             "Shanghai Stock Exchange" if "shanghai" in where else
             "Shenzhen Stock Exchange" if "shenzhen" in where else
             "Beijing Stock Exchange" if "beijing" in where else "mainland exchange")
    out = {"is_ah_applicant": True, "a_share_venue": venue}
    # a code counts only when the sentence is about the issuer, never about
    # "a company listed on ... with stock code NNNNNN" (that is someone else)
    for m in re.finditer(r"(?:stock\s+code|股份代碼)[:\s]*(\d{6})\b", flat, re.I):
        ctx = flat[max(0, m.start() - 260): m.start()]
        if re.search(r"a\s+company\s+listed|Huaqin|shareholding|Investment", ctx, re.I):
            continue
        if re.search(r"(?:the|our)\s+Company|the\s+Issuer|our\s+A\s+Shares", ctx, re.I):
            digits = m.group(1)
            suffix = (".SS" if digits[0] == "6" else
                      ".BJ" if digits[0] in "48" else ".SZ")
            out["a_share_code"] = digits + suffix
            break
    if "a_share_code" not in out:
        out["a_share_note"] = (f"A-share listed on the {venue}; the PHIP does not "
                               f"print the code — confirm on the terminal")
    return out


# longest-suffix first: "…Corporation Hong Kong Securities Limited" must not
# stop at "Corporation" (CICC split in half), "…Company Limited" not at "Company"
_BANK = re.compile(
    r"[A-Z][A-Za-z&\-\.,'() ]{4,80}?"
    r"(?:Corporation\s+Hong\s+Kong\s+Securities\s+Limited|"
    r"Company\s+Limited|Securities\s+Company\s+Limited|"
    r"Limited|Ltd\.?|L\.L\.C\.?|LLC|Company|Corporation|Inc\.?|Branch)")


def _clean_banks(names):
    """Strip the previous name's tail riding on the next one
    ('...Company Limited CLSA Limited' -> 'CLSA Limited')."""
    out = []
    for n in names:
        n = re.sub(r"^(?:Limited|Ltd\.?|Company|Corporation)\s+", "", n.strip(" ,."))
        if len(n) > 4 and n not in out:
            out.append(n)
    return out


def _oc_banks(a):
    """Sponsors + overall coordinators from the applicant's OC Announcement.

    Shape (Mech-Mind, verbatim): "the Company has appointed the following
    overall coordinators: Sponsor-Overall Coordinators <banks> Overall
    Coordinators <banks> Further announcement(s)..." — the Sponsor-OCs are the
    deal's sponsors.
    """
    from fetch_hkex_filings import get
    from pypdf import PdfReader
    sub = next((s for s in (a.get("_subs") or [])
                if re.search(r"OC Announcement", (s.get("nS1") or "") + (s.get("nF") or ""))),
               None)
    if not sub or not sub.get("u1"):
        return {}
    key = f"oc_{a['app_id']}"
    tfile = ROOT / "scrape" / "text_cache" / (key + ".txt")
    if not tfile.exists():
        url = sub["u1"] if sub["u1"].startswith("http") else DOCBASE + sub["u1"]
        blob = get(url, binary=True)
        if not blob or blob[:4] != b"%PDF":
            return {}
        pdf = ROOT / "scrape" / "pdf_cache" / (key + ".pdf")
        pdf.write_bytes(blob)
        tfile.write_text("\n".join((p.extract_text() or "")
                                   for p in PdfReader(str(pdf)).pages[:8]), errors="ignore")
    flat = re.sub(r"\s+", " ", tfile.read_text(errors="ignore"))
    m = re.search(r"appointed\s+the\s+following\s+overall\s+coordinators?\s*:?(.{10,1200}?)"
                  r"(?:Further\s+announcement|By\s+order\s+of\s+the\s+Board)", flat, re.I)
    if not m:
        # single-bank prose: "has appointed CLSA Limited as its (sole) overall
        # coordinator" (Direct Drive, Tanboer)
        m1 = re.search(r"has\s+appointed\s+(.{4,120}?)\s+as\s+its\s+"
                       r"(?:sole\s+)?overall\s+coordinator", flat, re.I)
        if m1:
            names = _clean_banks(_BANK.findall(m1.group(1)))
            if names:
                return {"coordinators": names}
        return {}
    body = m.group(1)
    # walk the role headings in order: whatever names follow "Sponsor-Overall
    # Coordinators" are the sponsors, whatever follows a bare "Overall
    # Coordinators" (or "Joint Sponsors") joins the coordinator list
    parts = re.split(r"(Sponsor[\s\-–]*Overall\s+Coordinators?|Joint\s+Sponsors?|"
                     r"Sole\s+Sponsor|Overall\s+Coordinators?)", body, flags=re.I)
    out, role = {}, None
    for seg in parts:
        low = seg.strip().lower()
        if re.fullmatch(r"sponsor[\s\-–]*overall\s+coordinators?|joint\s+sponsors?|"
                        r"sole\s+sponsor", low):
            role = "sponsors"
            continue
        if re.fullmatch(r"overall\s+coordinators?", low):
            role = "coordinators"
            continue
        names = _clean_banks(_BANK.findall(seg))
        if role and names:
            out.setdefault(role, []).extend(names[:8])
    if not out.get("sponsors") and out.get("coordinators"):
        # some issuers list everyone under one heading — the first banks named
        # are the sponsor side by convention; keep them as coordinators only
        pass
    return out


def _parse_phip_docs(apps):
    from fetch_hkex_filings import get, doc_parts
    from pypdf import PdfReader
    import extract_financials as EF
    import extract_profiles as EP
    import auto_classify as AC
    cache = ROOT / "scrape" / "pdf_cache"
    text = ROOT / "scrape" / "text_cache"
    cache.mkdir(parents=True, exist_ok=True)
    text.mkdir(parents=True, exist_ok=True)
    tax = json.loads((ROOT / "data" / "taxonomy.json").read_text())
    sector_of = {sb["label"]: sec for sec, subs in tax["sectors"].items() for sb in subs}
    for a in apps:
        link = a.get("doc_link")
        if not link:
            continue
        key = f"phip_{a['app_id']}"
        tfile = text / (key + ".txt")
        if not tfile.exists():
            urls = []
            if link.lower().endswith(".pdf"):
                urls = [link]
            else:
                rel = link.replace("https://www1.hkexnews.hk", "")
                urls = [u for _lbl, u in doc_parts(rel)][:6]
            chunks = []
            for j, u in enumerate(urls):
                blob = get(u, binary=True)
                if blob and blob[:4] == b"%PDF":
                    pf = cache / f"{key}_{j}.pdf"
                    pf.write_bytes(blob)
                    try:
                        r = PdfReader(str(pf))
                        chunks.append("\n".join((pg.extract_text() or "")
                                                for pg in r.pages[:120]))
                    except Exception:
                        pass
            tfile.write_text("\n".join(chunks), errors="ignore")
        txt = tfile.read_text(errors="ignore")
        if len(txt) < 5000:
            continue
        flat = EF.clean_text(txt)
        rev, _, _ = EF.series_from(flat, EF.REV_LINE)
        ni, _, _ = EF.series_from(flat, EF.NI_LINE)
        if not rev or not ni:
            f2 = re.sub(r"\s+", " ", flat)
            if not ni:
                ni, _, _ = EF.series_from_flat(f2, EF.FLAT_LABELS_NI)
            if not rev:
                rev, _, _ = EF.series_from_flat(f2, EF.FLAT_LABELS_REV)
        cur = EF.currency_of(flat)
        fxm = {"RMB": 1.10, "HK$": 1.0, "US$": 7.80}.get(cur or "", None)
        ov = EP.find_overview(txt)
        sub = AC.classify_text(" ".join(filter(None, [ov, a.get("applicant")])))
        name_l = (a.get("applicant") or "").lower()
        hand = next((v for k, v in PIPELINE_LABELS.items() if k in name_l), None)
        sub = hand or sub
        from textclip import clip_sentence
        parsed = {"business_overview": clip_sentence(ov, 620, hard=760),
                  "subsector": sub, "sector": sector_of.get(sub),
                  "subsector_src": "analyst label" if hand else
                                   ("keyword classifier (provisional)" if sub else None),
                  "fin_currency": cur}
        parsed.update(_a_share(txt))
        # Banks CANNOT come from the PHIP — its cover prints "[REDACTED] Sole
        # Sponsor..." until launch. The same-day "OC Announcement – Appointment"
        # names them, so that document is fetched and parsed instead.
        try:
            parsed.update(_oc_banks(a))
        except Exception as e:
            print(f"  OC parse failed for {a.get('applicant', '?')[:30]}: {e}")
        # an A-to-H applicant states its existing issued A-share count, which
        # with the A price gives the market the deal will be sized against
        m = re.search(r"(?:offer|issue)\s+(?:of\s+)?(?:up\s+to\s+)?([\d,]{7,})\s+"
                      r"(?:H\s+)?[Ss]hares", flat or "")
        if m:
            try:
                parsed["expected_shares"] = float(m.group(1).replace(",", ""))
            except ValueError:
                pass
        for keyn, series in (("rev_latest", rev), ("ni_latest", ni)):
            if series and fxm and len(series) <= 6:
                idx = 2 if len(series) >= 3 else len(series) - 1
                parsed[keyn] = round(series[idx] * fxm / 1000, 1)
        if parsed.get("ni_latest") is not None:
            parsed["profitable_at_ipo"] = parsed["ni_latest"] > 0
        a["parsed"] = {k: v for k, v in parsed.items() if v is not None}
        print(f"  parsed PHIP: {a['applicant'][:40]} -> {sub or 'unclassified'}"
              f"{' rev ' + str(parsed.get('rev_latest')) if parsed.get('rev_latest') else ''}")


if __name__ == "__main__":
    main()
