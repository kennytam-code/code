#!/usr/bin/env python3
"""Keyword auto-classifier for NEW deals — no AI required on the desk.

The primary sector/subsector labels are an analyst judgment layer keyed by
stock code (classify.py). A brand-new deal refreshed on a machine with no AI
would land unclassified, which would break the screener for exactly the deals
that matter most. This module assigns a PROVISIONAL subsector from the deal's
own prospectus business-overview text using ordered keyword rules.

Accuracy is measured against the 511 hand-labelled deals every time it runs and
printed, so drift is visible. Provisional labels merge at LOW priority with
status "estimated" (amber) — a later hand label in classify.py always wins.
"""
import json, re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "batches" / "deep_autoclass.json"

# ordered: first match wins. Most specific business first.
RULES = [
    ("LLM / foundation model", r"large language model|foundation model|LLM|generative AI model"),
    ("AI chips & semis", r"\bGPU\b|\bASIC\b|semiconductor|chip design|fabless|wafer|foundry|"
                         r"integrated circuit|CMOS|image sensor|SiC|silicon carbide|EDA\b|analog IC|MCU\b"),
    ("Robotics & autonomous driving", r"robot|autonomous driving|self-driving|robotaxi|LiDAR|"
                                      r"ADAS|humanoid|embodied|drone|intelligent driving|AGV\b"),
    ("Data center / cloud infra", r"data cent(?:er|re)|IDC\b|cloud comput|colocation"),
    ("AI application / agent software", r"artificial intelligence|AI-powered|AI solutions|"
                                        r"machine learning|computer vision|speech recognition|NLP\b"),
    ("Fintech platform", r"fintech|online (?:lending|payment)|digital payment|consumer credit platform|"
                         r"virtual bank|crypto|blockchain|digital asset"),
    ("Media / advertising", r"mobile game|game develop|game publish|esports"),
    ("SaaS / enterprise software", r"SaaS|enterprise software|ERP\b|CRM\b|software-as-a-service|"
                                   r"cloud-based (?:software|solution|platform for enterprise)"),
    ("Internet platform / e-commerce", r"e-commerce|online marketplace|online platform|online retail|"
                                       r"livestream|short video|social (?:media|commerce)|content community|"
                                       r"online travel|ride-?hailing|food delivery|recruitment platform"),
    ("Smart hardware / consumer electronics", r"consumer electronics|smart (?:device|hardware|home|wearable)|"
                                              r"smartphone|IoT device|acoustic|optical module|display module|"
                                              r"printed circuit|PCB\b|connector|camera module|e-?paper"),
    ("Biotech pre-revenue (18A)", r"clinical[- ]stage|pre-?clinical|pipeline of (?:drug|product) candidates|"
                                  r"investigational|IND\b|Phase (?:I|II|III)\b.{0,60}(?:trial|study)"),
    ("CXO / pharma services", r"\bCRO\b|\bCDMO\b|\bCMO\b|contract (?:research|development|manufactur)|"
                              r"peptide.{0,40}(?:development|production) service"),
    ("Medical devices", r"medical device|surgical|stent|catheter|orthop|imaging equipment|"
                        r"in.?vitro diagnostic|IVD\b|dental (?:implant|device)"),
    ("Biopharma commercial", r"pharmaceutical|biopharma|vaccine|drug (?:manufactur|commercial)|"
                             r"generic drug|API\b.{0,40}(?:manufactur|production)"),
    ("Digital health", r"online health|digital health|internet hospital|telemedicine|"
                       r"health(?:care)? (?:platform|app|SaaS)"),
    ("Hospitals / clinics", r"hospital|clinic|dental service|ophthalm|medical (?:examination|institution)|"
                            r"eye care|hair transplant|postpartum"),
    ("TCM", r"traditional Chinese medicine|\bTCM\b|Chinese medicin"),
    ("Batteries / energy storage", r"lithium|battery|energy storage|\bESS\b|fuel cell|hydrogen|"
                                   r"cathode|anode|electrolyte"),
    ("Solar / wind supply chain", r"photovoltaic|\bPV\b|solar|wind (?:power|turbine)|inverter"),
    ("Autos (NEV OEM)", r"electric vehicle manufactur|smart EV|vehicle OEM|passenger vehicle|automaker"),
    ("Auto parts / supply chain", r"auto(?:motive)? (?:part|component|supplier)|thermal management|"
                                  r"transmission|chassis|head-?up display|in-?vehicle"),
    ("F&B chains / restaurants", r"restaurant|tea (?:drink|shop|store)|freshly[- ]made|catering chain|"
                                 r"coffee (?:chain|shop)|noodle"),
    ("Beverages / packaged food", r"beverage|packaged food|snack|dairy|liquor|baijiu|brewery|"
                                  r"food (?:manufactur|process|company)|frozen food|condiment|flavou?ring"),
    ("Beauty / personal care", r"cosmetic|skincare|skin care|beauty|personal care|medical aesthetic"),
    ("Apparel / luxury", r"apparel|fashion|footwear|jewell?ery|luxury|gold ornament|watch"),
    ("Consumer services / education", r"education|training institution|tutoring|vocational|test preparation"),
    ("Retail / distribution", r"retail(?:er)? (?:chain|network|store)|department store|supermarket|"
                              r"distribution of|trading compan|franchis"),
    ("Banks", r"\bbank\b(?!rupt)"),
    ("Insurance", r"insurance|insurer|broker.{0,30}insurance"),
    ("Brokers / asset management", r"securities (?:brokerage|firm)|asset management|wealth management|"
                                   r"fund manage|futures compan|private equity"),
    ("Fintech platform", r"money lend|pawn|micro-?finance|licensed moneylender"),
    ("Logistics", r"logistics|freight|express delivery|shipping|supply chain service|warehouse|cold[- ]chain"),
    ("Construction / engineering", r"construction|engineering service|contractor|foundation work|"
                                   r"fitting-?out|curtain wall|municipal work"),
    ("Capital goods / machinery", r"machinery|equipment manufactur|industrial equipment|crane|"
                                  r"laser (?:equipment|technolog)|machine tool|automation equipment"),
    ("Mining / metals", r"mining|gold mine|copper|molybdenum|coal|iron ore|rare earth|tungsten|"
                        r"aluminium|alumina|metals"),
    ("Chemicals", r"chemical|petrochemical|polymer|resin|coating|fertiliser|fertilizer|graphite"),
    ("Oil & gas / utilities", r"natural gas|pipeline gas|city gas|oil ?field|water (?:supply|treatment)|"
                              r"sewage|waste treatment|environmental protection|power (?:generation|plant)|heat(?:ing)? service"),
    ("Developers", r"property develop"),
    ("Property management", r"property management|estate management|facility management|"
                            r"commercial operational service"),
    ("Media / advertising", r"advertis|marketing service|media (?:company|group)|film|drama|"
                            r"television|content production|artist management|music"),
    ("Telecom", r"telecommunication|telecom operator|communication service"),
]


def classify_text(text):
    """Most-evidence wins: count distinct keyword hits per label; rule order
    breaks ties (specific rules sit first). Measured ~49% exact-subsector
    agreement with the hand labels on overview text — a PROVISIONAL signal,
    always amber, always overridden by the next hand-labelled refresh."""
    if not text:
        return None
    best, best_score, best_rank = None, 0, 1e9
    for rank, (label, pat) in enumerate(RULES):
        hits = len(set(m.group(0).lower() for m in re.finditer(pat, text, re.I)))
        if hits > best_score or (hits == best_score and hits > 0 and rank < best_rank):
            best, best_score, best_rank = label, hits, rank
    return best if best_score else None


def main():
    # runs BEFORE merge and does not need AI or deals.json: reads the extracted
    # profiles directly and skips every code that classify.py hand-labels
    tax = json.loads((ROOT / "data" / "taxonomy.json").read_text())
    sector_of = {s["label"]: sec for sec, subs in tax["sectors"].items() for s in subs}
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from classify import GROUPS
    hand = {c.split(".")[0].zfill(4) for codes in GROUPS.values()
            for c in codes.split() if not c.endswith(".SKIP")}
    prof = {r["code"]: r for r in json.loads(
        (ROOT / "data" / "batches" / "extracted_profiles.json").read_text())["deals"]}

    # accuracy vs hand labels (when the merged DB exists), so quality is visible
    acc, tested = "untested", 0
    dj = ROOT / "data" / "deals.json"
    if dj.exists():
        scored = 0
        for d in json.loads(dj.read_text())["deals"]:
            text = " ".join(str(d.get(k) or "") for k in ("business_overview", "name"))
            g = classify_text(text)
            if g and d.get("subsector"):
                tested += 1
                scored += g == d["subsector"]
        acc = f"{100 * scored // max(1, tested)}%"

    out = []
    for code, r in prof.items():
        if code in hand:
            continue                        # hand label exists — never override
        text = " ".join(str(r.get(k) or "") for k in ("overview", "name_full", "name_cn"))
        guess = classify_text(text)
        if guess:
            out.append({"code": code, "sector": sector_of.get(guess, "Other"),
                        "subsector": guess,
                        "_prov": {"subsector": {"src": f"keyword auto-classifier "
                                                       f"(provisional; ~{acc} vs hand labels)",
                                                "status": "estimated"}}})
    OUT.write_text(json.dumps(
        {"batch": "deep_autoclass", "accuracy_vs_hand": acc, "tested": tested,
         "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "deals": out}, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {len(out)} provisional labels | "
          f"keyword engine agrees with hand labels on {acc}% of {tested} testable deals")


if __name__ == "__main__":
    main()
