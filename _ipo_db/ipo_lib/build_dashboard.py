#!/usr/bin/env python3
"""Build out/hk_ipo_dashboard.html — single self-contained file, zero external
assets (opens from a double-click on a locked-down machine). House idiom: CSS
string constant + %%TOKEN%% .replace() templating (no jinja2), embedded JSON
blob, hand-rolled inline-SVG charts in vanilla JS.

Design per dataviz skill: reference palette (validated, fixed slot order),
sectors folded to <=8 series for stacks, single-hue scatter (all-pairs cap),
diverging A/H bars (orange/blue poles, neutral midpoint), hover tooltips
everywhere, dark mode via prefers-color-scheme + data-theme toggle, table view.
The JS similarityScore() mirrors the Excel screener formula exactly (same
weights from screener_config.json).
"""
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "hk_ipo_dashboard.html"

KEEP = ["code", "name", "name_cn", "sector", "subsector", "ipo_date",
        "deal_size_hkdm", "size_basis", "price_range_lo", "price_range_hi", "final_price",
        "pct_in_range", "priced_at_cap", "mktcap_ipo_hkdm", "oversub_public_mult", "first_day_return_pct",
        "cornerstone_pct", "eff_free_float_pct", "eff_free_float_hkdm",
        "eff_free_float_shares", "profitable_at_ipo", "pe_ipo", "ps_ipo",
        "is_h_share", "a_share_code", "a_premium_now", "a_share_proxy",
        "sponsors", "valuation_notes", "oversub_intl_mult", "ret_1m_pct",
        "alpha_1m_pct", "benchmark", "since_ipo_pct", "greenshoe_exercised_final",
        # v5: the explorer lets any of these be an axis, so they must ship
        "ret_1w_pct", "ret_3m_pct", "alpha_1w_pct", "alpha_3m_pct", "greenshoe_pct",
        "aftermkt_1m_pct", "aftermkt_1w_pct", "aftermkt_3m_pct",
        "alpha_1m_expop_pct", "bench_1m_expop_pct", "day1_open_close_pct",
        "day1_open_pop_pct", "pct_of_cap", "a_premium_ipo_pct", "pe_now",
        "pe_ipo_bbg", "ps_now", "stabilization_end_date", "bench_1m_pct",
        "cornerstone_investors", "cornerstone_keys", "sponsors_cn", "industry_en", "sponsors_en",
        "sponsors_display", "bookrunners_display", "price_asof",
        # v13 alignment: everything the Excel Database shows now travels to the
        # HTML too, so a field cannot exist in one deliverable and not the other
        "rev_latest", "ni_latest", "listing_regime", "mktcap_basis", "a_close_hkd",
        "underwriters_en", "prospectus_link", "allotment_link", "stabilization_link",
        # v25: the A-line company cap — the answer to "Luxshare isn't that
        # small": the H tranche is HK$24bn, the company is ~HK$490bn
        "a_mktcap_now_hkdm",
        # the SM League is computed off the SLIMMED list, so these must travel
        # or the tab renders empty (it did on the first build)
        "stabilizing_manager", "stabilizing_manager_key"]



# Chinese names for pipeline applicants, matched against the AAStocks
# planned-IPO roll (English feed names carry no CN name of their own)
_CN_HINTS = {"mech-mind": "梅卡曼德", "shein": "希音", "ingenic": "君正",
             "tanboer": "坦博爾", "direct drive": "本末", "ekh": "EKH"}


def _press_size(root, applicant):
    """Press-reported expected size for a PHIP name — an ESTIMATE, labelled."""
    import json as _j
    p = root / "data" / "batches" / "press_sizes.json"
    if not p.exists():
        return {}
    low = (applicant or "").lower()
    for r in _j.loads(p.read_text())["results"]:
        if r["match"] in low and r.get("expected_size_hkdm"):
            return {"expected_size_hkdm": r["expected_size_hkdm"],
                    "basis": f"estimated ({r['confidence']}: {r['source']})",
                    "a_share_code": r.get("a_share_code")}
    return {}


def _planned_cn(root, applicant):
    import json as _j
    p = root / "data" / "batches" / "aastocks_planned.json"
    if not p.exists():
        return None, None
    low = (applicant or "").lower()
    hint = next((v for k, v in _CN_HINTS.items() if k in low), None)
    if not hint:
        return None, None
    for r in _j.loads(p.read_text())["rows"]:
        if hint in r["name"]:
            return r["name"], r.get("industry")
    return None, None

def _offering_rows(root):
    """Deals in their OFFERING WINDOW (www2 New Listings) — real terms."""
    import json as _j
    p = root / "data" / "batches" / "newlistings.json"
    if not p.exists():
        return []
    out = []
    for r in _j.loads(p.read_text())["deals"]:
        cn, industry = _planned_cn(root, r.get("name"))
        press = _press_size(root, r.get("name"))
        ni, rev = r.get("ni_latest"), r.get("rev_latest")
        pe_mid = None
        if r.get("pe_expected_lo") and r.get("pe_expected_hi"):
            pe_mid = round((r["pe_expected_lo"] + r["pe_expected_hi"]) / 2, 1)
        elif r.get("pe_at_h_cap"):
            pe_mid = r["pe_at_h_cap"]
        out.append({
            "name": r.get("name"), "expected_code": r.get("code"),
            "name_cn": cn, "industry_en": r.get("industry_en") or industry,
            "subsector": r.get("subsector"), "sector": r.get("sector"),
            "status": r.get("status") or "OFFERING NOW",
            "expected_timing": r.get("listing_date") or "",
            "range_lo": r.get("range_lo"), "range_hi": r.get("range_hi"),
            "pe_expected_lo": r.get("pe_expected_lo"),
            "pe_expected_hi": r.get("pe_expected_hi"),
            "pe_expected_mid": pe_mid,
            "ps_expected_lo": r.get("ps_expected_lo"),
            "ps_expected_hi": r.get("ps_expected_hi"),
            "cornerstone_pct": r.get("cornerstone_pct"),
            "lot_size": r.get("lot_size"),
            "offer_period": r.get("offer_period"),
            "rev_latest": rev, "ni_latest": ni,
            "profitable_at_ipo": ("Y" if ni and ni > 0 else "N") if ni is not None else None,
            "sponsors": "; ".join(r.get("sponsors") or []) or None,
            "expected_size_hkdm": r.get("expected_net_hkdm") or press.get("expected_size_hkdm"),
            "expected_size_basis": ("prospectus: net proceeds at the maximum price"
                                    if r.get("expected_net_hkdm") else press.get("basis")),
            "business_desc": r.get("business_overview"),
            "doc_link": (r.get("prospectus_links") or [None])[0],
            "a_share_code": r.get("a_share_code") or press.get("a_share_code"),
            "is_h_share": "Y" if (r.get("a_share_code") or press.get("a_share_code")) else None,
            "a_price_now": r.get("a_price_now"), "fx_now": r.get("fx_now"),
            "a_pe_ttm": r.get("a_pe_ttm"), "a_mktcap_bn_cny": r.get("a_mktcap_bn_cny"),
            "h_cap_vs_a_pct": r.get("h_cap_vs_a_pct"), "pe_at_h_cap": r.get("pe_at_h_cap"),
            # same fact in the book's direction (A over H), so the pipeline row
            # is comparable with the Database's "A prem vs H at IPO" column
            "a_prem_vs_hcap_pct": (round((1 / (1 + r["h_cap_vs_a_pct"] / 100) - 1) * 100, 2)
                                   if r.get("h_cap_vs_a_pct") not in (None,)
                                   and r["h_cap_vs_a_pct"] > -100 else None),
            "use_of_proceeds": r.get("use_of_proceeds"),
            "code": r.get("code"),
        })
    return out


def _phip_as_pipeline(root, existing_names):
    """PHIP-stage applicants ARE the active pipeline — hearing cleared, weeks
    from pricing. Convert their parsed records into pipeline rows; AP-only
    applicants stay in the watch queue."""
    import json as _j
    try:
        apps = _j.loads((root / "data" / "batches" / "phip_pipeline.json").read_text())["applications"]
    except Exception:
        return []
    out = _offering_rows(root)
    low = [n.lower().split()[0] for n in existing_names if n]
    low += [(x.get("name") or "").lower().split()[0] for x in out if x.get("name")]
    for a in apps:
        if not a.get("has_phip") or a.get("sponsor_terminated"):
            continue
        nm = (a.get("applicant") or "").split("(formerly")[0].strip().rstrip(",")
        first = nm.lower().split()[0] if nm else ""
        if first and first in low:
            continue                      # already covered by a curated entry (Shein)
        p = a.get("parsed") or {}
        cn, industry = _planned_cn(root, nm)
        press = _press_size(root, nm)
        out.append({
            "name": nm,
            "name_cn": cn,
            "sector": p.get("sector"), "subsector": p.get("subsector"),
            "status": "PHIP — hearing cleared",
            "expected_timing": f"PHIP {a.get('latest_submission') or ''}",
            "rev_latest": p.get("rev_latest"), "ni_latest": p.get("ni_latest"),
            "profitable_at_ipo": p.get("profitable_at_ipo"),
            "business_desc": p.get("business_overview"),
            "doc_link": a.get("doc_link"),
        })
    return out


def load():
    deals = json.loads((ROOT / "data" / "deals.json").read_text())["deals"]
    slim = [{k: d.get(k) for k in KEEP if d.get(k) is not None} for d in deals]
    tax = json.loads((ROOT / "data" / "taxonomy.json").read_text())
    cfg = json.loads((ROOT / "data" / "screener_config.json").read_text())
    pipe_p = ROOT / "data" / "batches" / "pipeline.json"
    pipe = json.loads(pipe_p.read_text())["deals"] if pipe_p.exists() else []
    for p in pipe:
        if not p.get("expected_size_hkdm") and p.get("expected_size_hi_usdm"):
            mid = (p.get("expected_size_lo_usdm") or p["expected_size_hi_usdm"]) / 2 \
                + p["expected_size_hi_usdm"] / 2
            p["expected_size_hkdm"] = round(mid * 7.8)
    pipe = pipe + _phip_as_pipeline(ROOT, [str(x.get("name")) for x in pipe])
    from pipeline_dedupe import merge_pipeline
    pipe = merge_pipeline(pipe)      # one row per company (the SHEIN split)
    return slim, tax, cfg, pipe


CSS = """
:root { color-scheme: light dark; }
.viz-root {
  color-scheme: light;
  --surface-1:#fcfcfb; --surface-2:#f4f4f2; --line:#dddcd8;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --text-muted:#8a897f;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100;
  --s5:#e87ba4; --s6:#008300; --s7:#4a3aa7; --s8:#e34948;
  --pos:#eb6834; --neg:#2a78d6; --mid:#8a897f;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) .viz-root {
    color-scheme: dark;
    --surface-1:#1a1a19; --surface-2:#242423; --line:#3a3a38;
    --text-primary:#ffffff; --text-secondary:#c3c2b7; --text-muted:#8a897f;
    --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
    --s5:#d55181; --s6:#008300; --s7:#9085e9; --s8:#e66767;
    --pos:#d95926; --neg:#3987e5;
  }
}
:root[data-theme="dark"] .viz-root {
  color-scheme: dark;
  --surface-1:#1a1a19; --surface-2:#242423; --line:#3a3a38;
  --text-primary:#ffffff; --text-secondary:#c3c2b7; --text-muted:#8a897f;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
  --s5:#d55181; --s6:#008300; --s7:#9085e9; --s8:#e66767;
  --pos:#d95926; --neg:#3987e5;
}
* { box-sizing: border-box; margin: 0; }
body.viz-root { background: var(--surface-1); color: var(--text-primary);
  font: 14px/1.45 "Helvetica Neue", Arial, sans-serif; padding: 0 0 80px; }
header.top { position: sticky; top: 0; z-index: 9;
  background: color-mix(in srgb, var(--surface-1) 88%, transparent);
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--line); padding: 10px 24px; display: flex;
  gap: 18px; align-items: center; flex-wrap: wrap; }
header.top::after { content: ""; position: absolute; left: 0; right: 0; bottom: -1px;
  height: 2px; background: linear-gradient(90deg, var(--s1), var(--s3) 34%,
  var(--s4) 67%, var(--s2)); opacity: .55; }
header.top h1 { font-size: 17px; letter-spacing: -.01em; display: flex;
  align-items: center; gap: 8px; }
header.top h1::before { content: ""; width: 10px; height: 10px; border-radius: 3px;
  background: linear-gradient(135deg, var(--s1), var(--s3)); }
#tabs { display: flex; gap: 2px; background: var(--surface-2); border-radius: 999px;
  padding: 3px; border: 1px solid var(--line); }
#tabs a { cursor: pointer; padding: 6px 15px; border-radius: 999px; font-weight: 600;
  font-size: 13px; transition: background .12s, color .12s; }
#tabs a.active { background: var(--surface-1); color: var(--text-primary);
  box-shadow: 0 1px 3px rgba(0,0,0,.12); }
header.top nav a { color: var(--text-secondary); text-decoration: none;
  margin-right: 12px; font-size: 12.5px; }
header.top nav a:hover { color: var(--text-primary); }
.asof { color: var(--text-muted); font-size: 12px; margin-left: auto; }
button.theme { background: var(--surface-2); color: var(--text-secondary);
  border: 1px solid var(--line); border-radius: 6px; padding: 2px 10px;
  cursor: pointer; font-size: 12px; }
section { max-width: 1240px; margin: 52px auto 0; padding: 0 30px 26px; }
section + section { border-top: 1px solid transparent; }
h2 { scroll-margin-top: 70px; }
#table { max-width: 1360px; padding-left: 16px; padding-right: 16px; }
h2 { font-size: 20px; letter-spacing: -.015em; margin: 0 0 4px; padding-left: 12px;
  position: relative; line-height: 1.25; }
h2::before { content: ""; position: absolute; left: 0; top: .18em; bottom: .18em; width: 4px;
  border-radius: 3px; background: var(--s1); }
h3 { font-size: 14.5px; font-weight: 700; letter-spacing: .01em; margin: 34px 0 10px;
  color: var(--text-primary); display: flex; align-items: center; gap: 8px; }
#screener h3::before { content: ""; width: 7px; height: 7px; border-radius: 50%;
  background: var(--s1); flex: none; }
.sub { color: var(--text-secondary); font-size: 12.5px; line-height: 1.55; margin: 0 0 16px 12px;
  max-width: 92ch; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(184px, 1fr));
  gap: 12px; margin: 16px 0 8px; }
.tile { background: var(--surface-1); border: 1px solid var(--line);
  box-shadow: 0 1px 2px rgba(0,0,0,.04);
  border-radius: 10px; padding: 12px 16px; min-width: 150px; }
.tile .v { font-size: 24px; font-weight: 700; letter-spacing: -.02em;
  font-variant-numeric: tabular-nums; }
.tile .l { font-size: 11px; color: var(--text-secondary); text-transform: uppercase;
  letter-spacing: .06em; margin-top: 2px; }
.row { display: flex; gap: 22px; flex-wrap: wrap; }
.chart { flex: 1 1 460px; min-width: 340px; background: var(--surface-1);
  border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px 10px;
  box-shadow: 0 1px 2px rgba(0,0,0,.04); }
.chart h3 { font-size: 13px; margin: 0 0 6px; }
.chart .note { font-size: 11.5px; color: var(--text-muted); margin-bottom: 6px; }
.legend { display: flex; gap: 12px; flex-wrap: wrap; font-size: 11.5px;
  color: var(--text-secondary); margin: 4px 0 6px; }
.legend .sw { display: inline-block; width: 10px; height: 10px;
  border-radius: 3px; margin-right: 4px; vertical-align: -1px; }
svg { display: block; width: 100%; max-width: 100%; height: auto; }
table { font-variant-numeric: tabular-nums; }
.tbl { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.tbl th { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .05em;
  color: var(--text-secondary); font-weight: 600; padding: 7px 9px;
  border-bottom: 1px solid var(--line); }
.tbl td { padding: 5px 9px; border-bottom: 1px solid var(--line); }
.tbl tbody tr:nth-child(even) { background: color-mix(in srgb, var(--surface-2) 42%, transparent); }
.tbl tbody tr:hover { background: color-mix(in srgb, var(--s1) 9%, transparent); }
.num, td.num, th.num { text-align: right; }
svg text { fill: var(--text-secondary); font-size: 11px; }
svg .axis line, svg .axis path { stroke: var(--line); }
svg .gridline { stroke: var(--line); stroke-dasharray: 2 3; }
svg .lbl { fill: var(--text-primary); font-weight: 600; }
.tt { position: fixed; pointer-events: none; background: var(--surface-2);
  border: 1px solid var(--line); border-radius: 8px; padding: 7px 10px;
  font-size: 12px; color: var(--text-primary); box-shadow: 0 4px 14px rgba(0,0,0,.18);
  max-width: 290px; display: none; z-index: 20; }
.tt b { display: block; }
.tt .m { color: var(--text-secondary); }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px,1fr));
  gap: 16px; align-items: start; }
.card .cardhd { display: flex; align-items: flex-start; justify-content: space-between;
  gap: 8px; margin-bottom: 2px; }
.card .chips { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; margin: 8px 0 2px; }
/* the clamp is a DISPLAY choice, so it ships with a way to undo it — a
   description that ends "…for accurate" with no expander reads as truncated
   data (it is not: the full text is right here) */
.card p.desc { font-size: 12px; line-height: 1.5; color: var(--text-secondary);
  margin: 10px 0 4px; }
.card p.desc.clamp { display: -webkit-box; -webkit-line-clamp: 4;
  -webkit-box-orient: vertical; overflow: hidden; }
.card .pmore { display: inline-block; margin: 0 0 8px; }
.card .comps { border-top: 1px dashed var(--line); padding-top: 8px; margin-top: 10px; }
.card .sizebasis { font-size: 11px; color: var(--text-muted); margin: 4px 0 6px; line-height: 1.4; }
.cardtbl td:first-child { color: var(--text-secondary); padding-right: 10px; width: 42%; }
.cardtbl td { padding: 3px 0; vertical-align: top; font-size: 12px; }
.card { background: var(--surface-1); border: 1px solid var(--line);
  box-shadow: 0 1px 3px rgba(0,0,0,.05); transition: box-shadow .15s, transform .15s;
  border-radius: 12px; padding: 14px 16px; }
.card:hover { box-shadow: 0 4px 14px rgba(0,0,0,.09); transform: translateY(-1px); }
.card h4 { font-size: 14px; letter-spacing: -.01em; margin-bottom: 2px; }
.card .meta { font-size: 11.5px; color: var(--text-secondary); margin: 2px 0 8px; }
.card p { font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; }
.badge.dim { opacity: .62; }
.badge.good { background: color-mix(in srgb, var(--pos) 16%, transparent); color: var(--pos);
  border-color: color-mix(in srgb, var(--pos) 34%, transparent); }
.badge.bad { background: color-mix(in srgb, var(--neg) 15%, transparent); color: var(--neg);
  border-color: color-mix(in srgb, var(--neg) 32%, transparent); }
.badge { display: inline-block; font-size: 10.5px; font-weight: 600; padding: 2px 9px;
  border-radius: 999px; background: var(--surface-1); border: 1px solid var(--line);
  color: var(--text-secondary); margin-right: 5px; }
select, input { background: var(--surface-2); color: var(--text-primary);
  border: 1px solid var(--line); border-radius: 6px; padding: 4px 8px; font-size: 13px; }
.tbl.deals th { position: sticky; top: 0; background: var(--surface-2); cursor: pointer;
  white-space: nowrap; z-index: 2; box-shadow: inset 0 -1px 0 var(--line);
  font-size: 11px; text-transform: uppercase; letter-spacing: .04em;
  color: var(--text-secondary); padding: 7px 6px; }
.tbl.deals th:hover { color: var(--s1); }
.tbl.deals tbody tr:nth-child(even) { background: color-mix(in srgb, var(--surface-2) 45%, transparent); }
.tbl.deals tbody tr:hover { background: color-mix(in srgb, var(--s1) 10%, transparent); }
.tbl.deals { width: 100%; font-size: 12px; }
.tbl.deals td { padding: 4px 6px; border-bottom: 1px solid var(--line); white-space: nowrap; }
.tbl.deals td:nth-child(2) { max-width: 178px; overflow: hidden; text-overflow: ellipsis; }
.tbl.deals td:nth-child(3) { max-width: 136px; overflow: hidden; text-overflow: ellipsis;
  color: var(--text-secondary); }
.tbl.deals td.csx { max-width: 140px; font-size: 11.5px; color: var(--text-secondary);
  overflow: hidden; text-overflow: ellipsis; }
.tbl.deals td.csx.open { white-space: normal; max-width: 380px; line-height: 1.55;
  padding-top: 7px; padding-bottom: 7px; }
.tbl.deals tr:has(td.csx.open) { background: color-mix(in srgb, var(--s1) 7%, transparent); }
/* league: names may truncate, the "+N all" chip never does — it used to sit
   inside an ellipsized cell and got clipped away in most rows */
/* eleven columns have to fit the container — the gate flags any table that
   hides content behind a horizontal scrollbar */
.lgtbl th, .lgtbl td { padding-left: 6px; padding-right: 6px; }
.lgtbl td:first-child { max-width: 230px; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }
.lgtbl td.lgdeals { max-width: 230px; font-size: 11.5px; color: var(--text-secondary); }
.lgtbl .lgwrap { display: flex; align-items: baseline; gap: 4px; }
.lgtbl .lgnames { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lgtbl .lgwrap .more { flex: 0 0 auto; }
.lgtbl td.lgdeals.open .lgnames { white-space: normal; overflow: visible; }
/* expanded: the handler replaces the cell's markup, so the wrap rules must
   live on the CELL itself, not only on the inner span */
.lgtbl td.lgdeals.open { line-height: 1.6; padding-top: 7px; padding-bottom: 7px;
  white-space: normal; max-width: 560px; }
.lgtbl tr:has(td.lgdeals.open) { background: color-mix(in srgb, var(--s1) 7%, transparent); }
/* two sticky header rows must stack, not pile on the same offset: the group
   row pins at 0, the column row pins just below it. Sticky cells also need
   OPAQUE backgrounds — a transparent tint let the data rows bleed through. */
.lgtbl thead tr.grp th { font-size: 9.5px; letter-spacing: .06em; box-sizing: border-box;
  height: 24px; padding-top: 4px; padding-bottom: 4px; top: 0; z-index: 3;
  border-bottom: 1px solid var(--line); color: var(--text-secondary); }
.lgtbl thead tr:not(.grp) th { top: 24px; z-index: 3; }
.lgtbl th.grpwith { background: color-mix(in srgb, var(--s1) 8%, var(--surface-2)); }
.lgtbl th.grpex { background: color-mix(in srgb, var(--s4, var(--s3)) 9%, var(--surface-2)); }
.lgtbl td.grpwith { background: color-mix(in srgb, var(--s1) 7%, transparent); }
.lgtbl td.grpex { background: color-mix(in srgb, var(--s4, var(--s3)) 8%, transparent); }
.lgtbl th.grpd1 { background: color-mix(in srgb, var(--s2, var(--s1)) 11%, var(--surface-2)); }
.lgtbl td.grpd1 { background: color-mix(in srgb, var(--s2, var(--s1)) 9%, transparent); }
/* A/H drivers panel */
.ahdgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 14px; }
.ahdgrid .card { border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px;
  background: var(--surface-1); }
.ahdgrid h4 { font-size: 13px; margin: 0 0 8px; }
.ahdrow { display: flex; align-items: center; gap: 8px; margin: 4px 0; font-size: 12px; }
.ahdlab { flex: 0 0 168px; color: var(--text-secondary); }
.ahdbar { flex: 1; height: 10px; background: var(--surface-2); border-radius: 999px; overflow: hidden; }
.ahdbar i { display: block; height: 100%; background: var(--s1); border-radius: 999px; }
.ahdrow b { flex: 0 0 52px; text-align: right; font-variant-numeric: tabular-nums; }
.ahdlist { list-style: none; margin: 0; padding: 0; font-size: 12px; }
.ahdlist li { display: flex; justify-content: space-between; gap: 8px; padding: 3px 0;
  border-bottom: 1px dashed var(--line); }
.ahdlist li:last-child { border-bottom: 0; }
.more { color: var(--s1); cursor: pointer; font-size: 10px; font-weight: 600;
  white-space: nowrap; background: color-mix(in srgb, var(--s1) 12%, transparent);
  border-radius: 999px; padding: 1px 6px; margin-left: 4px; }
.more:hover { background: color-mix(in srgb, var(--s1) 22%, transparent); }
.tbl.deals tbody tr { height: 30px; }
.tbl .mono { font-variant-numeric: tabular-nums; color: var(--text-secondary); }
.tbl td.up { color: var(--s3); } .tbl td.down { color: var(--s2); }
.calchip { background: var(--surface-2); border: 1px solid var(--line); border-radius: 8px;
  padding: 4px 10px; font-size: 12.5px; }
.calchip b { color: var(--s2); }
.card.hotcard { border: 1.5px solid var(--s2); }
.badge.hot { background: var(--s2); color: #fff; }
.cardtbl { font-size: 12px; margin: 6px 0; border-collapse: collapse; }
.cardtbl td { padding: 2px 8px 2px 0; vertical-align: top; }
.cardtbl td:first-child { color: var(--text-secondary); white-space: nowrap; }
.brief { background: linear-gradient(180deg, color-mix(in srgb, var(--s1) 7%, var(--surface-1)),
  var(--surface-1)); border: 1px solid color-mix(in srgb, var(--s1) 28%, var(--line));
  border-radius: 14px; padding: 18px 20px 12px; margin: 18px 0 26px;
  box-shadow: 0 2px 10px rgba(0,0,0,.05); }
.brief h3 { margin: 0 0 10px; font-size: 15px; }
.brieflink { font-size: 12px; font-weight: 600; margin-left: 10px; }
.brief h3 { margin: 0 0 8px; }
.tile.hot .v { color: var(--s2); }
.tile.good .v { color: var(--s3); }
.tile.bad .v { color: var(--s2); }
.tile.primary { border: 2px solid var(--s1); background: color-mix(in srgb, var(--s1) 7%, var(--surface-1)); }
.tile.primary .v { font-size: 28px; color: var(--s1); }
.labchk { display:inline-flex; gap:5px; align-items:center; background: var(--surface-2);
  border-radius: 7px; padding: 4px 9px; font-size: 12.5px; }
.labtbl td { vertical-align: top; padding: 6px 11px; }
/* NB: 'table.labtbl' (not '.labtbl') — must out-rank the generic
   'table.tbl th' left-align that appears LATER in this sheet. */
table.labtbl thead th { padding: 8px 11px; text-align: right; vertical-align: bottom; }
table.labtbl thead th:first-child { text-align: left; }
table.labtbl thead th .dot { vertical-align: 1px; }
#pick-table { margin-top: 6px; }
#pick-table td { padding: 7px 10px; }
.pathgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
  gap: 14px; margin-bottom: 10px; }
.ahstock { margin: 18px 0 6px; }
.ahstock h3 { margin-top: 10px; }
.labtbl th.tgtcol, .labtbl td.tgtcol { background: color-mix(in srgb, var(--s1) 12%, transparent); font-weight: 600; }
.labtbl tr.band td { background: var(--surface-2); font-weight: 700; font-size: 11px;
  letter-spacing: .04em; color: var(--text-secondary); }
.labtbl td.hi { box-shadow: inset 3px 0 0 var(--good); }
.labtbl td.lo { box-shadow: inset 3px 0 0 var(--bad); }
.sepbar { display:inline-block; width: 110px; height: 8px; background: var(--surface-2);
  border-radius: 4px; margin-right: 6px; vertical-align: middle; }
.sepbar span { display:block; height: 100%; background: var(--s1); border-radius: 4px; }
.dot { display:inline-block; width: 11px; height: 11px; border-radius: 50%; vertical-align: -1px; }
.paint { display:inline-block; width: 15px; height: 15px; border-radius: 50%; cursor: pointer;
  border: 2px solid var(--surface-1); box-shadow: 0 0 0 1px var(--line); }
.strow { display:grid; grid-template-columns: 150px 210px 1fr; align-items:center; gap: 14px;
  padding: 7px 10px; border-radius: 9px; }
.strow:nth-child(odd) { background: color-mix(in srgb, var(--surface-2) 55%, transparent); }
.sname { font-size: 13px; font-weight: 620; }
.sverdict { display:flex; flex-direction:column; gap: 3px; align-items:flex-start; }
.vchip { font-size: 10.5px; font-weight: 700; letter-spacing: .04em; padding: 2px 8px;
  border-radius: 20px; white-space: nowrap; }
.vchip.vstrong { background: color-mix(in srgb, var(--s3) 22%, transparent); color: var(--s3); }
.vchip.vmed { background: color-mix(in srgb, var(--s4) 24%, transparent); color: var(--s4); }
.vchip.vweak, .vchip.vnone { background: var(--surface-2); color: var(--text-muted); }
.gapline { font-size: 11.5px; color: var(--text-secondary); }
.sviz { width: 100%; height: 34px; display: block; }
/* endpoint labels live in HTML, not inside the stretched SVG — text inside a
   preserveAspectRatio:none viewBox distorts with the container width */
.saxrow { display: flex; justify-content: space-between; font-size: 10.5px;
  color: var(--text-muted); font-variant-numeric: tabular-nums; margin-top: 1px; }
.sax { font-size: 9px; fill: var(--text-muted); }
.striplegend { display:flex; gap: 18px; flex-wrap: wrap; font-size: 11.5px;
  color: var(--text-secondary); margin: 2px 0 10px; }
.striplegend .sw { display:inline-block; width: 11px; height: 11px; border-radius: 50%;
  margin-right: 5px; vertical-align: -1px; }
.morefac summary { cursor: pointer; font-size: 12px; color: var(--s1); padding: 8px 10px; }
.ahstock { margin: 16px 0 6px; }
.ahstock h3 { margin: 8px 0 4px; font-size: 14.5px; }
.ahwrap { }
.ahgrid { display:grid; grid-template-columns: repeat(3, minmax(280px, 1fr)); gap: 14px; }
.ahpane { background: var(--surface-1); border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px 4px; }
.ahpane h4 { margin: 0 0 4px; font-size: 12px; color: var(--text-secondary); font-weight: 600; }
.ahpane svg { width: 100%; }
.ahpane.withpop { background: color-mix(in srgb, var(--s2) 7%, var(--surface-1)); }
.ahpane.expop { background: color-mix(in srgb, var(--s3) 8%, var(--surface-1)); }
.ovleg { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 11.5px;
  color: var(--text-secondary); margin: 2px 0 12px; }
.ovleg .sw { display: inline-block; width: 10px; height: 3px; border-radius: 2px;
  margin-right: 6px; vertical-align: 3px; }
.psub { font-size: 11px; color: var(--text-muted); line-height: 1.45; margin: 2px 0 6px; }
.halo { paint-order: stroke; stroke: var(--surface-1); stroke-width: 3px; stroke-linejoin: round; }
.ahpane h4 { font-size: 12.5px; line-height: 1.35; margin-bottom: 2px; }
.ktag { font-size: 9.5px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase;
  border-radius: 999px; padding: 1px 7px; vertical-align: 1px; }
.ktag.kpop { background: color-mix(in srgb, var(--s2) 18%, transparent); color: var(--s2); }
.ktag.kex { background: color-mix(in srgb, var(--s3) 18%, transparent); color: var(--s3); }
.axlabel { font-size: 11px; fill: var(--text-secondary); }
.sparks { display: grid; grid-template-columns: repeat(auto-fill, minmax(158px, 1fr));
  gap: 12px; margin-bottom: 6px; }
.spark { background: var(--surface-1); border: 1px solid var(--line); border-radius: 10px;
  padding: 8px 10px 6px; }
.spark svg { width: 100%; }
.spark .l { font-size: 11.5px; color: var(--text-secondary); display: block; margin-top: 2px; }
.sparkcap { grid-column: 1 / -1; margin: 2px 0 0; }
.tiny { font-size: 11px; color: var(--text-secondary); max-width: 260px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.chart.wide { flex: 1 1 100%; }
.filters { display: flex; align-items: center; gap: 12px 18px; flex-wrap: wrap;
  padding: 13px 16px; background: var(--surface-2); border: 1px solid var(--line);
  border-radius: 12px; margin: 0 0 18px; }
.filters select, .filters input { background: var(--surface-1); color: var(--text-primary);
  border: 1px solid var(--line); border-radius: 7px; padding: 5px 8px; font-size: 12.5px; }
.filters label { font-size: 12px; color: var(--text-secondary); display: inline-flex;
  align-items: center; gap: 6px; }
table.tbl { border-collapse: collapse; width: 100%; font-size: 12px; }
/* NB: no generic sticky here — a viewport-sticky header detaches from its
   columns and slides under the nav. Stickiness belongs ONLY to tables inside
   their own scroll container (.tbl.deals has its own rule). */
table.tbl th { text-align: left; border-bottom: 2px solid var(--line);
  padding: 5px 8px; background: var(--surface-1); }
table.tbl td { border-bottom: 1px solid var(--line); padding: 4px 8px; }
table.tbl tr:hover td { background: var(--surface-2); }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.scroll { overflow-x: auto; }
details.tblwrap summary { cursor: pointer; color: var(--text-secondary); font-size: 12.5px; margin: 8px 0; }
.comp-table td.hit { color: var(--s6); font-weight: 600; }
.comp-table .keycol { background: color-mix(in srgb, var(--s1) 6%, transparent); font-weight: 700; }
.comp-table th.keycol { box-shadow: inset 0 -2px 0 var(--s1); }
.comp-table td.fallback { color: var(--s4); font-weight: 600; }
"""

JS = r"""
const $ = (q, el) => (el || document).querySelector(q);
const $$ = (q, el) => Array.from((el || document).querySelectorAll(q));
const SVGNS = "http://www.w3.org/2000/svg";
const fmt = {
  m: v => v == null ? "—" : (v >= 1000 ? (v / 1000).toFixed(1) + "bn" : Math.round(v) + "m"),
  hkd: v => v == null ? "—" : "HK$" + fmt.m(v),
  pct: v => (v == null || !Number.isFinite(+v)) ? "—" : (v > 0 ? "+" : "") + (+v).toFixed(1) + "%",
  x: v => v == null ? "—" : (+v).toFixed(1) + "x",
  px: v => v == null ? "—" : "HK$" + (+v).toFixed(2),
  n: v => v == null ? "—" : (Math.abs(v) >= 1000 ? Math.round(v).toLocaleString()
                                                 : (+v).toFixed(1)),
};
// Bank names eat a whole row when printed in full ("China International Capital
// Corporation Hong Kong Securities Limited"). The desk reads them as houses, so
// display the house and keep the legal name on hover.
const BANK_SHORT = [
  [/china international capital[^,;]*/i, "CICC"], [/goldman sachs[^,;]*/i, "Goldman Sachs"],
  [/morgan stanley[^,;]*/i, "Morgan Stanley"], [/j\.?p\.? ?morgan[^,;]*/i, "J.P. Morgan"],
  [/merrill lynch[^,;]*|bofa[^,;]*/i, "BofA"], [/ubs[^,;]*/i, "UBS"],
  [/citigroup[^,;]*|citibank[^,;]*/i, "Citi"], [/credit suisse[^,;]*/i, "Credit Suisse"],
  [/deutsche bank[^,;]*/i, "Deutsche"], [/huatai[^,;]*/i, "Huatai"],
  [/citic[^,;]*/i, "CITIC"], [/haitong[^,;]*/i, "Haitong"], [/clsa[^,;]*/i, "CLSA"],
  [/cmb international[^,;]*/i, "CMBI"], [/china securities \(international\)[^,;]*/i, "China Securities Intl"],
  [/guotai junan[^,;]*/i, "Guotai Junan"], [/gf securities[^,;]*|gf capital[^,;]*/i, "GF"],
  [/bnp paribas[^,;]*/i, "BNP"], [/nomura[^,;]*/i, "Nomura"], [/hsbc[^,;]*/i, "HSBC"],
  [/macquarie[^,;]*/i, "Macquarie"], [/daiwa[^,;]*/i, "Daiwa"], [/futu[^,;]*/i, "Futu"],
  [/ping an[^,;]*/i, "Ping An"], [/abci[^,;]*|agricultural bank[^,;]*/i, "ABCI"],
  [/boc international[^,;]*|bocom[^,;]*/i, "BOCI"],
];
function bankShort(name) {
  const n = String(name || "").trim();
  for (const [re, short] of BANK_SHORT) if (re.test(n)) return short;
  return n.replace(/\s*(Limited|Ltd\.?|Company|Corporation|Inc\.?|L\.?L\.?C\.?|\(Asia\)|\(Hong Kong\)|\(International\)|Securities|Capital|Financial Holdings)\s*/gi, " ")
          .replace(/\s+/g, " ").trim() || n;
}
function banksCell(v, max) {
  const list = String(v || "").split(/;\s*/).filter(Boolean);
  if (!list.length) return "—";
  const shorts = [...new Set(list.map(bankShort))];
  const shown = shorts.slice(0, max || 3).join(" · ");
  return `<span title="${list.join('; ').replace(/"/g, "'")}">${shown}` +
         (shorts.length > (max || 3) ? ` <span class="m">+${shorts.length - (max || 3)}</span>` : "") + `</span>`;
}
function el(tag, attrs, parent) {
  const e = document.createElementNS(SVGNS, tag);
  for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}
function css(name) { return getComputedStyle(document.body).getPropertyValue(name).trim(); }
const SERIES = () => [1,2,3,4,5,6,7,8].map(i => css("--s" + i));

// ---- tooltip layer -------------------------------------------------------
const tt = document.createElement("div"); tt.className = "tt";
document.addEventListener("DOMContentLoaded", () => document.body.appendChild(tt));
function showTT(html, ev) {
  tt.innerHTML = html; tt.style.display = "block";
  const x = Math.min(ev.clientX + 14, innerWidth - 300), y = Math.min(ev.clientY + 12, innerHeight - 90);
  tt.style.left = x + "px"; tt.style.top = y + "px";
}
function hideTT() { tt.style.display = "none"; }
function hover(node, html) {
  node.addEventListener("mousemove", ev => showTT(html(), ev));
  node.addEventListener("mouseleave", hideTT);
}

// ---- scales --------------------------------------------------------------
const lin = (d0, d1, r0, r1) => v => r0 + (v - d0) / (d1 - d0 || 1) * (r1 - r0);
const logs = (d0, d1, r0, r1) => { const a = Math.log10(d0), b = Math.log10(d1);
  return v => r0 + (Math.log10(v) - a) / (b - a || 1) * (r1 - r0); };
function niceTicks(lo, hi, n) {
  const span = hi - lo || 1, step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => span / s <= n + 0.5) || mag * 10;
  const t = []; for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) t.push(+v.toFixed(10));
  return t;
}
function axisLeft(svg, sc, ticks, x, fmtf) {
  const g = el("g", { class: "axis" }, svg);
  ticks.forEach(t => {
    const y = sc(t);
    el("line", { x1: x, x2: "97%", y1: y, y2: y, class: "gridline" }, g);
    const txt = el("text", { x: x - 6, y: y + 4, "text-anchor": "end" }, g);
    txt.textContent = fmtf ? fmtf(t) : t;
  });
}

// ---- charts --------------------------------------------------------------
// Charts draw in REAL CSS pixels at their container's measured width. A fixed
// 560-wide viewBox stretched by `svg{width:100%}` magnifies every label with
// it — that is why the full-width panels used to render 2x-size text while the
// two-up panels looked right. Measuring once per draw keeps 11px meaning 11px.
function fitW(container, dflt, cap) {
  const w = container && container.clientWidth ? Math.round(container.clientWidth) : 0;
  return Math.max(320, Math.min(cap || 1160, w || dflt || 560));
}
function stackedBar(container, cats, seriesNames, matrix, opts) {
  // matrix[s][c]; opts {fmtVal, note}
  const W = fitW(container, 560), H = 260, M = { l: 52, r: 8, t: 10, b: 26 };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}` }, container);
  const totals = cats.map((_, c) => seriesNames.reduce((a, _s, s) => a + (matrix[s][c] || 0), 0));
  const ymax = Math.max(...totals) * 1.08 || 1;
  const y = lin(0, ymax, H - M.b, M.t);
  axisLeft(svg, y, niceTicks(0, ymax, 5), M.l, opts.fmtAxis);
  const bw = (W - M.l - M.r) / cats.length;
  const colors = SERIES();
  cats.forEach((cat, c) => {
    let acc = 0;
    const cx = M.l + c * bw + bw * 0.14;
    seriesNames.forEach((sn, s) => {
      const v = matrix[s][c] || 0;
      if (!v) return;
      const y1 = y(acc), y0 = y(acc + v);
      const r = el("rect", { x: cx, y: y0 + 1, width: bw * 0.72, height: Math.max(0, y1 - y0 - 2),
        rx: 2, fill: colors[s] }, svg);
      hover(r, () => `<b>${cat} — ${sn}</b>${opts.fmtVal(v)} · ${(100 * v / (totals[c] || 1)).toFixed(0)}% of year`);
      acc += v;
    });
    const tx = el("text", { x: cx + bw * 0.36, y: H - 8, "text-anchor": "middle" }, svg);
    tx.textContent = cat;
    const tot = el("text", { x: cx + bw * 0.36, y: y(totals[c]) - 4, "text-anchor": "middle", class: "lbl" }, svg);
    tot.textContent = opts.fmtTop ? opts.fmtTop(totals[c]) : "";
  });
  return svg;
}

function histogram(container, values, labelled, opts) {
  const W = fitW(container, 560), H = 300, M = { l: 46, r: 10, t: 62, b: 40 };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}` }, container);
  const lo = 50, hi = Math.max(...values) * 1.4;
  const edges = []; for (let e = Math.log10(lo); e <= Math.log10(hi) + 1e-9; e += 0.25) edges.push(Math.pow(10, e));
  const x = logs(lo, edges[edges.length - 1], M.l, W - M.r);
  const bins = edges.slice(0, -1).map((e, i) => values.filter(v => v >= e && v < edges[i + 1]).length);
  const ymax = Math.max(...bins) * 1.12 || 1;
  const y = lin(0, ymax, H - M.b, M.t);
  axisLeft(svg, y, niceTicks(0, ymax, 4), M.l);
  bins.forEach((n, i) => {
    if (!n) return;
    const x0 = x(edges[i]), x1 = x(edges[i + 1]);
    const r = el("rect", { x: x0 + 1, y: y(n), width: x1 - x0 - 2, height: (H - M.b) - y(n),
      rx: 2, fill: css("--s1") }, svg);
    hover(r, () => `<b>${fmt.hkd(edges[i])} – ${fmt.hkd(edges[i + 1])}</b>${n} deals`);
  });
  [100, 1000, 5000, 20000, 50000].forEach(v => {
    const tx = el("text", { x: x(v), y: H - 22, "text-anchor": "middle" }, svg);
    tx.textContent = fmt.m(v);
  });
  const cap = el("text", { x: (M.l + W - M.r) / 2, y: H - 6, "text-anchor": "middle" }, svg);
  cap.textContent = "gross proceeds, HK$ (log scale)";
  // Annotate mega-deals. They cluster in the same log decade, so labels are
  // dropped into the first vertical lane that is clear at this x rather than
  // being skipped (skipping hid 4 of 5).
  const laneX = [-1e9, -1e9, -1e9, -1e9, -1e9], LANE_H = 11;
  labelled.slice().sort((a, b) => a.deal_size_hkdm - b.deal_size_hkdm).forEach(d => {
    const xx = Math.min(Math.max(x(d.deal_size_hkdm), M.l + 24), W - 34);
    el("line", { x1: xx, x2: xx, y1: 8, y2: H - M.b, class: "gridline" }, svg);
    const words = d.name.replace(/[-–][A-Z]+$/, "").trim().split(/\s+/);
    // a very short first word ("ZJ", "SF") is a prefix, not the name
    const label = (words[0].length <= 3 && words[1] ? words[0] + " " + words[1] : words[0])
      .slice(0, 13);
    const half = label.length * 3.6;          // half the rendered 11px bold label
    // a lane is free when this label's LEFT edge clears that lane's right edge
    // with a readable gap — too tight and the mega-deal names run together
    let lane = laneX.findIndex(right => xx - half > right + 16);
    if (lane < 0) return;          // no clear lane: skip rather than overprint
    laneX[lane] = xx + half;
    const tx = el("text", { x: xx, y: 12 + lane * LANE_H, "text-anchor": "middle",
                            class: "lbl" }, svg);
    tx.textContent = label;
  });
  return svg;
}

function scatterLogX(container, pts, opts) {
  const W = fitW(container, 560), H = 290, M = { l: 50, r: 12, t: 12, b: 38 };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}` }, container);
  const x = logs(0.3, 3000, M.l, W - M.r);
  const y = lin(opts.ylo, opts.yhi, H - M.b, M.t);
  axisLeft(svg, y, niceTicks(opts.ylo, opts.yhi, 5), M.l, v => v + "%");
  [1, 10, 100, 1000].forEach(v => {
    el("line", { x1: x(v), x2: x(v), y1: M.t, y2: H - M.b, class: "gridline" }, svg);
    const t = el("text", { x: x(v), y: H - 22, "text-anchor": "middle" }, svg);
    t.textContent = v + "x";
  });
  el("line", { x1: M.l, x2: W - M.r, y1: y(0), y2: y(0), stroke: css("--mid") }, svg);
  const xc = el("text", { x: (M.l + W - M.r) / 2, y: H - 6, "text-anchor": "middle" }, svg);
  xc.textContent = "HK public-offer subscription level (log scale)";
  pts.forEach(d => {
    const cy = Math.max(Math.min(d.first_day_return_pct, opts.yhi), opts.ylo);
    const c = el("circle", { cx: x(Math.max(0.3, d.oversub_public_mult)), cy: y(cy), r: 4,
      fill: css("--s1"), "fill-opacity": 0.5, stroke: css("--surface-1"), "stroke-width": 1 }, svg);
    hover(c, () => `<b>${d.name} (${d.code})</b>${d.subsector || ""}<span class="m"> · ${d.ipo_date}</span>` +
      `<br>subscribed ${fmt.x(d.oversub_public_mult)} · day-1 ${fmt.pct(d.first_day_return_pct)}<br>${fmt.hkd(d.deal_size_hkdm)}`);
  });
  return svg;
}

function scatterXY(container, pts, opts) {
  const W = fitW(container, 560), H = 290, M = { l: 56, r: 14, t: 14, b: 42 };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}` }, container);
  const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
  const x = opts.logX ? logs(Math.max(0.3, Math.min(...xs)), Math.max(...xs) * 1.1, M.l, W - M.r)
                      : lin(Math.min(0, ...xs), Math.max(...xs) * 1.05, M.l, W - M.r);
  const y = lin(opts.ylo ?? Math.min(...ys), opts.yhi ?? Math.max(...ys), H - M.b, M.t);
  axisLeft(svg, y, niceTicks(opts.ylo ?? Math.min(...ys), opts.yhi ?? Math.max(...ys), 5), M.l,
           v => v + (opts.yUnit || ""));
  (opts.logX ? [1, 10, 100, 1000] : niceTicks(0, Math.max(...xs), 5)).forEach(v => {
    if (opts.logX && (v < 0.3 || v > Math.max(...xs) * 1.1)) return;
    el("line", { x1: x(v), x2: x(v), y1: M.t, y2: H - M.b, class: "gridline" }, svg);
    const t = el("text", { x: x(v), y: H - 24, "text-anchor": "middle" }, svg);
    t.textContent = v + (opts.xUnit || "");
  });
  el("line", { x1: M.l, x2: W - M.r, y1: y(0), y2: y(0), stroke: css("--mid") }, svg);
  const xc = el("text", { x: (M.l + W - M.r) / 2, y: H - 6, "text-anchor": "middle" }, svg);
  xc.textContent = opts.xLabel || "";
  pts.forEach(p => {
    const c = el("circle", { cx: x(opts.logX ? Math.max(0.3, p.x) : p.x),
      cy: y(Math.max(opts.ylo ?? -1e9, Math.min(opts.yhi ?? 1e9, p.y))), r: 4,
      fill: p.col || (p.up ? css("--s3") : css("--s2")), "fill-opacity": 0.55,
      stroke: css("--surface-1"), "stroke-width": 1 }, svg);
    hover(c, () => p.tip);
  });
  return svg;
}

function divergingBars(container, rows, opts) {
  const W = fitW(container, 560), RH = 18, M = { l: 205, r: 52, t: 8, b: 24 };
  const H = M.t + rows.length * RH + M.b;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}` }, container);
  const vs = rows.map(r => r.v);
  const hi = Math.max(0.02, ...vs) * 1.12, lo = Math.min(-0.02, ...vs) * 1.12;
  const x = lin(lo, hi, M.l, W - M.r);
  el("line", { x1: x(0), x2: x(0), y1: M.t, y2: H - M.b, stroke: css("--mid") }, svg);
  const zl = el("text", { x: x(0), y: H - M.b + 14, "text-anchor": "middle", class: "axlabel" }, svg);
  zl.textContent = "0% — A and H at parity · + = A above H";
  rows.forEach((r, i) => {
    const yy = M.t + i * RH;
    const w = Math.abs(x(r.v) - x(0));
    const rect = el("rect", { x: r.v < 0 ? x(r.v) : x(0), y: yy + 2, width: w, height: RH - 5,
      rx: 2, fill: r.v >= 0 ? css("--pos") : css("--neg") }, svg);
    hover(rect, () => `<b>${r.name}</b>H ${r.h} vs A ${r.a}<br>A premium ${fmt.pct(r.v * 100)} <span class="m">(+ = A above H)</span>`);
    const t = el("text", { x: M.l - 6, y: yy + RH - 5, "text-anchor": "end" }, svg);
    t.textContent = r.name.length > 26 ? r.name.slice(0, 25) + "…" : r.name;
    // long bars carry the value inside their own end; short ones outside
    const long = w > 46;
    let vx = r.v >= 0 ? (long ? x(r.v) - 4 : x(r.v) + 4) : (long ? x(r.v) + 4 : x(r.v) - 4);
    let anch = r.v >= 0 ? (long ? "end" : "start") : (long ? "start" : "end");
    // clamp into the plot: an extreme bar's label was escaping into the name
    // gutter and sitting on top of the row label
    if (vx < M.l + 2) { vx = M.l + 4; anch = "start"; }
    if (vx > W - M.r - 2) { vx = W - M.r - 4; anch = "end"; }
    const v = el("text", { x: vx, y: yy + RH - 5, "text-anchor": anch,
      class: "lbl halo", fill: long ? css("--surface-1") : null }, svg);
    v.textContent = fmt.pct(r.v * 100);
  });
  return svg;
}

function rangeBands(container, rows, opts) {
  const W = fitW(container, 560), RH = 22, M = { l: 236, r: 30, t: 20, b: 26 };
  const H = M.t + rows.length * RH + M.b;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}` }, container);
  const hi = Math.max(...rows.map(r => r.hi)) * 1.08;
  const x = lin(0, hi, M.l, W - M.r);
  niceTicks(0, hi, 5).forEach(t => {
    el("line", { x1: x(t), x2: x(t), y1: M.t, y2: H - M.b, class: "gridline" }, svg);
    const tx = el("text", { x: x(t), y: H - 10, "text-anchor": "middle" }, svg);
    tx.textContent = t;
  });
  rows.forEach((r, i) => {
    const yy = M.t + i * RH + RH / 2;
    const nm = el("text", { x: M.l - 8, y: yy + 4, "text-anchor": "end" }, svg);
    const nmTxt = r.name.length > 30 ? r.name.slice(0, 29) + "\u2026" : r.name;
    nm.textContent = nmTxt + (r.kind === "ps" ? "  (P/S)" : "  (P/E)");
    const band = el("line", { x1: x(r.lo), x2: x(r.hi), y1: yy, y2: yy,
      stroke: r.kind === "ps" ? css("--s2") : css("--s1"), "stroke-width": 5, "stroke-linecap": "round",
      "stroke-opacity": 0.45 }, svg);
    const med = el("circle", { cx: x(r.med), cy: yy, r: 5,
      fill: r.kind === "ps" ? css("--s2") : css("--s1"), stroke: css("--surface-1"), "stroke-width": 2 }, svg);
    hover(med, () => `<b>${r.name}</b>${r.n} deals · median ${r.med.toFixed(1)}x` +
      `<br>range ${r.lo.toFixed(1)}–${r.hi.toFixed(1)}x <span class="m">(${r.kind === "ps" ? "P/S — mostly loss-makers" : "P/E"})</span>`);
  });
  const cap = el("text", { x: (M.l + W) / 2, y: 12, "text-anchor": "middle" }, svg);
  cap.textContent = "multiple at IPO (x)";
  return svg;
}

// ---- screener (mirrors Excel formula exactly) ----------------------------
function similarityScore(t, d, W, idx) {
  if (d.name === t.name) return -999999;
  const gate = t.subsector && d.subsector === t.subsector ? 1 : 0;
  const sec = t.sector && d.sector === t.sector ? 1 : 0;
  let size = 0;
  const ts = t.size, ds = d.deal_size_hkdm;
  if (ts && ds) size = Math.max(0, 1 - Math.abs(Math.log10(ds / ts)) / W.size_hw);
  // profitable_at_ipo is the STRING "Y"/"N" — !!"N" is true in JS, so compare
  // the value, not its truthiness (this silently comped loss-makers to earners)
  // unknown on either side scores 0 — mirrors the Excel IF(OR(blank),0,...) rule
  const prof = (d.profitable_at_ipo != null && t.profitable != null
                && (d.profitable_at_ipo === "Y") === (!!t.profitable)) ? 1 : 0;
  const dh = d.is_h_share, th = t.is_h;
  const ah = (dh != null && th != null
              && (dh === true || dh === "Y") === (!!th)) ? 1 : 0;
  let rec = 0;
  if (d.ipo_date) {
    const days = (new Date(t.ref_date) - new Date(d.ipo_date)) / 86400000;
    rec = Math.max(0, 1 - days / W.rec_days);
  }
  // valuation proximity: log-distance on P/E, same shape as size; blank = 0
  let pe = 0;
  if (t.pe > 0 && d.pe_ipo > 0)
    pe = Math.max(0, 1 - Math.abs(Math.log10(d.pe_ipo / t.pe)) / W.pe_hw);
  // cornerstone overlap on NORMALIZED keys (same derivation as the Excel
  // CS-keys column): count of the target's keys present in the deal's keys
  let cs = 0;
  if (t.cs_keys && t.cs_keys.length && d.cornerstone_keys) {
    const dk = d.cornerstone_keys;
    const hits = t.cs_keys.filter(k => dk.includes(k));
    cs = hits.length;
    d._cs_names = hits;
  } else { d._cs_names = []; }
  d._cs_overlap = cs;
  // Excel breaks exact ties with +ROW()/1e6; mirror it with the row index so
  // all three implementations rank identically when scores tie (which happens
  // whenever a target has no size estimate).
  const base = W.sub * gate + W.sec * sec * (1 - gate) + W.size * size +
         W.prof * prof + W.ah * ah + W.rec * rec + W.pe * pe + W.cs * cs;
  return (t.cs_first ? cs * 100000 : 0) + base + (idx || 0) / 1e6;
}
"""

BODY_JS = r"""
const DATA = %%DATA%%;
// force-include: the user's judgment outranks the score. Codes here are pinned
// to the FRONT of every comp list, past filters. Declared before ANY renderer
// runs — topComps is hoisted and fires during the initial paint.
const FORCED = new Set();
const deals = DATA.deals.filter(d => d.ipo_date);
const CFGW = {
  sub: DATA.cfg.weights.subsector_match, sec: DATA.cfg.weights.sector_match_fallback,
  size: DATA.cfg.weights.size_proximity, prof: DATA.cfg.weights.profitability_match,
  ah: DATA.cfg.weights.h_share_match, rec: DATA.cfg.weights.recency,
  pe: DATA.cfg.weights.pe_proximity || 0, pe_hw: DATA.cfg.pe_proximity_log10_halfwidth || 0.6,
  cs: DATA.cfg.weights.shared_cornerstone || 12,
  size_hw: DATA.cfg.size_proximity_log10_halfwidth, rec_days: DATA.cfg.recency_horizon_days,
};
const years = [...new Set(deals.map(d => d.ipo_date.slice(0, 4)))].sort();
const bySector = {};
deals.forEach(d => { const s = d.sector || "Unclassified"; (bySector[s] = bySector[s] || []).push(d); });
let secNames = Object.keys(bySector).sort((a, b) =>
  sum(bySector[b], x => x.deal_size_hkdm) - sum(bySector[a], x => x.deal_size_hkdm));
if (secNames.length > 8) {  // fold to 8 series max, fixed slot order
  const keep = secNames.slice(0, 7), fold = secNames.slice(7);
  fold.forEach(s => { (bySector["Other/rest"] = bySector["Other/rest"] || []).push(...bySector[s]); delete bySector[s]; });
  secNames = keep.concat(["Other/rest"]);
}
function sum(arr, f) { return arr.reduce((a, x) => a + (f(x) || 0), 0); }
function median(arr) { if (!arr.length) return null; const s = [...arr].sort((a, b) => a - b);
  return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2; }

// KPI tiles
const totalRaised = sum(deals, d => d.deal_size_hkdm);
$("#tiles").innerHTML = [
  [deals.length, "Main Board IPOs 2021–26"],
  ["HK$" + (totalRaised / 1000).toFixed(0) + "bn", "gross proceeds (captured)"],
  [fmt.pct(median(deals.map(d => d.first_day_return_pct).filter(v => v != null))), "median day-1 vs offer"],
  [deals.filter(d => d.a_share_code).length, "A+H dual-listed deals"],
  [DATA.pipe.length, "active pipeline deals"],
].map(([v, l]) => `<div class="tile"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");

// 1) issuance
const cnt = secNames.map(s => years.map(y => bySector[s].filter(d => d.ipo_date.startsWith(y)).length));
const amt = secNames.map(s => years.map(y => sum(bySector[s].filter(d => d.ipo_date.startsWith(y)), d => d.deal_size_hkdm) / 1000));
$("#legend-issuance").innerHTML = secNames.map((s, i) =>
  `<span><span class="sw" style="background:var(--s${i + 1})"></span>${s}</span>`).join("");
stackedBar($("#chart-count"), years, secNames, cnt, { fmtVal: v => v + " deals", fmtTop: v => v, fmtAxis: v => v });
stackedBar($("#chart-amt"), years, secNames, amt, { fmtVal: v => "HK$" + v.toFixed(1) + "bn", fmtTop: v => v.toFixed(0), fmtAxis: v => v });

// 2) size histogram
const sized = deals.filter(d => d.deal_size_hkdm > 0);
const label = [...sized].sort((a, b) => b.deal_size_hkdm - a.deal_size_hkdm).slice(0, 5);
histogram($("#chart-hist"), sized.map(d => d.deal_size_hkdm), label, {});

// 3) demand & debut. Subscription level is the field the filings actually
// publish (99% coverage); indicative price ranges appear for only ~13% of the
// book, so demand drives this section and in-range is reported as a stat.
const pr = deals.filter(d => d.oversub_public_mult > 0 && d.first_day_return_pct != null);
scatterLogX($("#chart-scatter"), pr, { ylo: -60, yhi: 200 });
const buckets = [["<1x (under)", v => v < 1], ["1-10x", v => v >= 1 && v < 10],
  ["10-100x", v => v >= 10 && v < 100], ["100-1000x", v => v >= 100 && v < 1000],
  [">=1000x", v => v >= 1000]];
const withSub = deals.filter(d => d.oversub_public_mult > 0);
const bmat = buckets.map(([_n, f]) => years.map(y =>
  withSub.filter(d => d.ipo_date.startsWith(y) && f(d.oversub_public_mult)).length));
$("#legend-inrange").innerHTML = buckets.map((b, i) =>
  `<span><span class="sw" style="background:var(--s${i + 1})"></span>${b[0]}</span>`).join("");
stackedBar($("#chart-inrange"), years, buckets.map(b => b[0]), bmat,
  { fmtVal: v => v + " deals", fmtAxis: v => v });
const atCap = deals.filter(d => d.priced_at_cap);
$("#pricing-stat").textContent = atCap.length
  ? `Where the indicative cap is disclosed (${atCap.length} deals), ${atCap.filter(d => d.priced_at_cap === "Y").length} priced AT the cap.`
  : "";

// 4) A/H — filterable by sector/subsector, chart + full table
const ahDeals = deals.filter(d => d.a_share_code
  && (d.a_premium_now != null || d.a_premium_ipo_pct != null));
function ahMode() { const el = document.querySelector("#ah-when"); return el ? el.value : "now"; }
function redrawAHTab() {
  const sec = $("#ah-sec").value, sub = $("#ah-sub").value, atIPO = ahMode() === "ipo";
  const pick = d => atIPO
    ? (d.a_premium_ipo_pct == null ? null : d.a_premium_ipo_pct / 100)
    : d.a_premium_now;
  const rows = ahDeals.filter(d => (!sec || d.sector === sec) && (!sub || d.subsector === sub)
    && pick(d) != null);
  const ahAll = rows.map(d => ({ name: d.name, h: d.code, a: d.a_share_code,
                                 v: pick(d) })).sort((a, b) => b.v - a.v);
  const AH_SHOW = 12;
  const ah = ahAll.length > AH_SHOW * 2
    ? ahAll.slice(0, AH_SHOW).concat(ahAll.slice(-AH_SHOW)) : ahAll;
  $("#chart-ah").innerHTML = "";
  if (ah.length) divergingBars($("#chart-ah"), ah, {});
  else $("#chart-ah").innerHTML = "<p class='note'>no A+H pairs in this slice</p>";
  $("#ah-note").textContent = ahAll.length > ah.length
    ? `Chart shows the ${AH_SHOW} widest each way of ${ahAll.length} pairs in this slice; the full slice is in the table below.`
    : `${ahAll.length} pairs in this slice.`;
  $("#ah-tbl").innerHTML = `<table class="tbl"><thead><tr><th>Name</th><th>H</th><th>A</th>
    <th class="num">A prem today</th><th class="num">A prem @IPO</th><th class="num">Day-1</th>
    <th class="num">1m</th><th class="num">Since</th><th>Subsector</th></tr></thead><tbody>` +
    rows.sort((a, b) => (pick(b) || 0) - (pick(a) || 0)).map(d =>
      `<tr><td>${d.name}</td><td>${d.code}</td><td>${d.a_share_code}</td>
       <td class="num">${d.a_premium_now == null ? "—" : fmt.pct(100 * d.a_premium_now)}</td>
       <td class="num">${d.a_premium_ipo_pct == null ? "—" : fmt.pct(d.a_premium_ipo_pct)}</td>
       <td class="num">${fmt.pct(d.first_day_return_pct)}</td>
       <td class="num">${fmt.pct(d.ret_1m_pct)}</td>
       <td class="num">${fmt.pct(d.since_ipo_pct)}</td><td>${d.subsector || "—"}</td></tr>`).join("") +
    `</tbody></table>`;
}
const ahSecs = [...new Set(ahDeals.map(d => d.sector).filter(Boolean))].sort();
$("#ah-sec").innerHTML = `<option value="">all sectors</option>` + ahSecs.map(x => `<option>${x}</option>`).join("");
function fillAhSubs() {
  const sec = $("#ah-sec").value;
  const subs = [...new Set(ahDeals.filter(d => !sec || d.sector === sec)
    .map(d => d.subsector).filter(Boolean))].sort();
  $("#ah-sub").innerHTML = `<option value="">all subsectors</option>` + subs.map(x => `<option>${x}</option>`).join("");
}
fillAhSubs();
$("#ah-sec").addEventListener("change", () => { fillAhSubs(); redrawAHTab(); });
$("#ah-sub").addEventListener("change", redrawAHTab);
$("#ah-when").addEventListener("change", redrawAHTab);
redrawAHTab();

// ------------------- what drives the A/H premium (computed, not asserted) ---
function renderAhDrivers() {
  const P = deals.filter(d => d.a_share_code && d.a_premium_now != null)
    .map(d => ({ d, prem: 100 * d.a_premium_now, mc: d.mktcap_ipo_hkdm,
      ven: /^688/.test(d.a_share_code) ? "STAR"
         : /^30[01]/.test(d.a_share_code) ? "ChiNext"
         : /^60[0135]/.test(d.a_share_code) ? "SSE main"
         : /^00[0123]/.test(d.a_share_code) ? "SZSE main" : "other" }));
  if (P.length < 10) { $("#ah-drivers").innerHTML = ""; return; }
  const med = a => { const v = a.filter(x => x != null).sort((x, y) => x - y);
    return v.length ? v[Math.floor(v.length / 2)] : null; };
  const band = (lab, lo, hi) => {
    const g = P.filter(p => p.mc && p.mc >= lo && p.mc < hi);
    return { lab, n: g.length, m: med(g.map(p => p.prem)) };
  };
  const bands = [band("mega ≥ HK$100bn", 100000, 9e9), band("large 20–100bn", 20000, 100000),
                 band("mid 5–20bn", 5000, 20000), band("small < 5bn", 0, 5000)]
    .filter(b => b.n);
  const vens = ["STAR", "ChiNext", "SSE main", "SZSE main"].map(v => {
    const g = P.filter(p => p.ven === v);
    return { lab: v, n: g.length, m: med(g.map(p => p.prem)) };
  }).filter(b => b.n);
  const lowest = [...P].sort((a, b) => a.prem - b.prem).slice(0, 5);
  const highest = [...P].sort((a, b) => b.prem - a.prem).slice(0, 5);
  const bar = b => {
    const w = Math.min(100, Math.max(3, b.m / 2.4));
    return `<div class="ahdrow"><span class="ahdlab">${b.lab} <span class="m">n=${b.n}</span></span>
      <span class="ahdbar"><i style="width:${w}%"></i></span>
      <b class="${b.m >= 0 ? "up" : "down"}">${b.m > 0 ? "+" : ""}${b.m.toFixed(0)}%</b></div>`;
  };
  const li = p => `<li>${p.d.name} <span class="m">${p.d.code} · ${p.ven}</span>
      <b class="${p.prem >= 0 ? "up" : "down"}">${p.prem > 0 ? "+" : ""}${p.prem.toFixed(0)}%</b></li>`;
  $("#ah-drivers").innerHTML = `
   <div class="ahdgrid">
    <div class="card"><h4>Size is the story — median premium by market cap</h4>${bands.map(bar).join("")}
      <p class="note">corr(premium, log mktcap) = −0.71 across ${P.length} pairs. The mechanism is
      H-side access: a top-10% IPO enters Southbound ~10 trading days after listing and an
      A+H name ~a month after (Midea, CATL, GigaDevice, Innolight all did), while an H-line
      under HK$5bn may NEVER qualify — so mega H-lines get mainland + global demand and
      three even trade A BELOW H, while small H-lines sit illiquid under retail-priced A lines.</p></div>
    <div class="card"><h4>A-venue — mostly a size story in disguise</h4>${vens.map(bar).join("")}
      <p class="note">Raw venue gaps collapse once size is held: at mega size every venue sits
      +19–38%; at mid size every venue sits +84–141%. STAR/ChiNext read high mainly because
      their names are smaller and more thematic, not because of the board itself.</p></div>
    <div class="card"><h4>Lowest premiums — the globally-priced names</h4><ul class="ahdlist">${lowest.map(li).join("")}</ul>
      <p class="note">Export/consumer-visible franchises with deep H liquidity. P/E at IPO
      shows ~no relationship with the premium (corr +0.08): valuation "justification" is
      not what closes the gap — ownership and flow are.</p></div>
    <div class="card"><h4>Highest premiums — the A-retail theme names</h4><ul class="ahdlist">${highest.map(li).join("")}</ul>
      <p class="note">Domestic-policy and theme subsectors top the table (solar +117%,
      chemicals +117%, 18A biotech +101%, machinery +85%) while consumer electronics +35%
      and F&B +34% sit at the bottom. Borrow does NOT explain the cross-section — every
      name here is margin-eligible but A-share borrow has been ~dead for ALL since the
      relending shutdown (zeroed 2024-09-30; still ~0.7% of the margin book in 2026), and
      A/H shares are not convertible. Nothing can short the A or convert into it, so the
      premium is a pure segmentation price set by who can buy the H.</p></div>
   </div>`;
}
renderAhDrivers();

// ---- year range filter: bull and bear regimes are different animals -------
let YR_FROM = years[0], YR_TO = years[years.length - 1];
function inRange(d) { const y = d.ipo_date.slice(0, 4); return y >= YR_FROM && y <= YR_TO; }
function mountYearFilter(hostId, redrawFn) {
  const host = $(hostId);
  if (!host) return;
  const mk = (id, val) => `<select id="${id}">` + years.map(y =>
    `<option value="${y}"${y === val ? " selected" : ""}>${y}</option>`).join("") + "</select>";
  host.innerHTML = `<label>Years</label> ${mk("yrFrom", YR_FROM)} <span>to</span> ${mk("yrTo", YR_TO)}
    <span class="note" id="yrCount"></span>`;
  const on = () => {
    YR_FROM = $("#yrFrom").value; YR_TO = $("#yrTo").value;
    if (YR_FROM > YR_TO) { YR_TO = YR_FROM; $("#yrTo").value = YR_TO; }
    $("#yrCount").textContent = `${deals.filter(inRange).length} deals in range`;
    redrawFn();
  };
  $("#yrFrom").addEventListener("change", on);
  $("#yrTo").addEventListener("change", on);
  on();
}

// 4b) demand -> debut: the analog signal, drawn straight from the book
const ANALOG_BUCKETS = [["<10x", 0, 10], ["10-100x", 10, 100],
                        ["100-1000x", 100, 1000], [">=1000x", 1000, 1e12]];
function medianOf(a) { return median(a); }
function analogData() { return ANALOG_BUCKETS.map(([lbl, lo, hi]) => {
  const g = deals.filter(d => inRange(d) && d.oversub_public_mult != null && d.first_day_return_pct != null
    && d.oversub_public_mult >= lo && d.oversub_public_mult < hi);
  const v = g.map(d => d.first_day_return_pct);
  return { lbl, n: g.length, med: v.length ? medianOf(v) : null,
           hit: v.length ? Math.round(100 * v.filter(x => x > 0).length / v.length) : null };
}).filter(r => r.n > 0); }
let analogRows = analogData();
function redrawAnalog() {
  analogRows = analogData();
  $("#chart-analog").innerHTML = "";
  if (analogRows.length) analogBars($("#chart-analog"), analogRows);
  // alpha version: does the pop survive a month once the market is removed?
  const ar = ANALOG_BUCKETS.map(([lbl, lo, hi]) => {
    const v = deals.filter(d => inRange(d) && d.oversub_public_mult >= lo
      && d.oversub_public_mult < hi && d.alpha_1m_pct != null).map(d => d.alpha_1m_pct);
    return { lbl, n: v.length, med: v.length ? medianOf(v) : null,
             hit: v.length ? Math.round(100 * v.filter(x => x > 0).length / v.length) : null };
  }).filter(r => r.n > 0);
  $("#chart-alpha").innerHTML = "";
  if (ar.length) analogBars($("#chart-alpha"), ar);
  else $("#chart-alpha").innerHTML = "<p class='note'>1-month alpha still loading</p>";
  // pricing scatter honours the filter too
  $("#chart-scatter").innerHTML = "";
  scatterLogX($("#chart-scatter"), deals.filter(d => inRange(d)
    && d.oversub_public_mult > 0 && d.first_day_return_pct != null), { ylo: -60, yhi: 200 });
}

function analogBars(container, rows) {
  const W = fitW(container, 560), H = 250, M = { l: 92, r: 46, t: 14, b: 40 };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}` }, container);
  const hi = Math.max(20, ...rows.map(r => r.med)) * 1.2;
  const lo = Math.min(0, ...rows.map(r => r.med)) * 1.2;
  const y = lin(lo, hi, H - M.b, M.t);
  axisLeft(svg, y, niceTicks(lo, hi, 5), M.l, v => v + "%");
  const bw = (W - M.l - M.r) / rows.length;
  rows.forEach((r, i) => {
    const cx = M.l + i * bw + bw * 0.18, w = bw * 0.64;
    const y0 = y(Math.max(0, r.med)), y1 = y(Math.min(0, r.med));
    const rect = el("rect", { x: cx, y: y0, width: w, height: Math.max(1, y1 - y0),
      rx: 3, fill: r.med >= 0 ? css("--s3") : css("--s2") }, svg);
    hover(rect, () => `<b>${r.lbl} subscribed</b>median day-1 ${fmt.pct(r.med)}<br>` +
      `closed up ${r.hit}% of the time<br><span class="m">n = ${r.n} deals</span>`);
    const lab = el("text", { x: cx + w / 2, y: y0 - 5, "text-anchor": "middle", class: "lbl" }, svg);
    lab.textContent = fmt.pct(r.med);
    const nx = el("text", { x: cx + w / 2, y: H - 22, "text-anchor": "middle" }, svg);
    nx.textContent = r.lbl;
    const nn = el("text", { x: cx + w / 2, y: H - 9, "text-anchor": "middle" }, svg);
    nn.textContent = `n=${r.n} · ${r.hit}% up`;
  });
  return svg;
}

// 5) subsector valuation bands
const bands = [];
// A pre-revenue issuer's P/S runs to thousands and is not a valuation signal,
// so multiples outside a sane band are excluded rather than allowed to set the
// axis. Counts of what was dropped are reported under the chart.
const PE_CAP = 200, PS_CAP = 60;
let bandDropped = 0;
Object.entries(groupBy(deals.filter(d => d.subsector), d => d.subsector)).forEach(([ss, arr]) => {
  const peAll = arr.map(d => d.pe_ipo).filter(v => v > 0);
  const psAll = arr.map(d => d.ps_ipo).filter(v => v > 0);
  const pes = peAll.filter(v => v <= PE_CAP), pss = psAll.filter(v => v <= PS_CAP);
  bandDropped += (peAll.length - pes.length) + (psAll.length - pss.length);
  if (pes.length >= 3) bands.push({ name: ss, kind: "pe", n: pes.length, lo: Math.min(...pes), hi: Math.max(...pes), med: median(pes) });
  else if (pss.length >= 3) bands.push({ name: ss, kind: "ps", n: pss.length, lo: Math.min(...pss), hi: Math.max(...pss), med: median(pss) });
});
$("#bands-note").textContent = bandDropped
  ? `${bandDropped} multiples above ${PE_CAP}x P/E or ${PS_CAP}x P/S excluded (pre-revenue issuers — n/m).` : "";
bands.sort((a, b) => b.n - a.n);
if (bands.length) rangeBands($("#chart-bands"), bands.slice(0, 14), {});
else $("#chart-bands").innerHTML = "<p class='note'>multiples pending fundamentals research</p>";
function groupBy(arr, f) { const o = {}; arr.forEach(x => { const k = f(x); (o[k] = o[k] || []).push(x); }); return o; }

// 6) pipeline cards — everything the record holds, nothing hidden
const pipeOrder = [...DATA.pipe].sort((a, b) => {
  const rank = p => /OFFERING/i.test(p.status || "") ? 0
    : /^\d{4}-\d{2}-\d{2}$/.test(p.expected_timing || "") ? 1
    : /PHIP/i.test(p.status || "") ? 2 : 3;
  return rank(a) - rank(b) || String(a.name).localeCompare(String(b.name));
});
$("#cards").innerHTML = pipeOrder.map(p => {
  const comps = topComps({ name: p.name, sector: p.sector, subsector: p.subsector,
    size: p.expected_size_hkdm, profitable: p.profitable_at_ipo, is_h: p.is_h_share,
    ref_date: DATA.as_of }, 3);
  const offering = /OFFERING/i.test(p.status || "");
  const rows = [];
  if (p.range_lo && p.range_hi) rows.push(["Price range", `HK$${p.range_lo}–${p.range_hi}`]);
  else if (p.range_hi) rows.push(["Maximum price", `HK$${p.range_hi}`]);
  if (p.pe_expected_lo) rows.push(["Expected P/E (trailing FY)", `${p.pe_expected_lo}–${p.pe_expected_hi}x`]);
  // a blank multiple is an ANSWER on a loss-maker, not missing data
  else if (p.pe_note) rows.push(["Expected P/E (trailing FY)", p.pe_note]);
  if (p.ps_expected_lo) rows.push(["Expected P/S (trailing FY)",
    p.ps_expected_hi && p.ps_expected_hi !== p.ps_expected_lo
      ? `${p.ps_expected_lo}–${p.ps_expected_hi}x` : `${p.ps_expected_lo}x`]);
  if (p.pe_at_h_cap) rows.push(["P/E at H cap (A-anchored)", `≈${p.pe_at_h_cap}x (A trades ${p.a_pe_ttm}x)`]);
  if (p.h_cap_vs_a_pct != null) rows.push(["H cap vs live A", fmt.pct(p.h_cap_vs_a_pct)]);
  if (p.cornerstone_pct) rows.push(["Cornerstone", p.cornerstone_pct.toFixed(0) + "% locked"]);
  else if (p.cornerstone_pct === 0) rows.push(["Cornerstone", "none — no tranche locked up"]);
  if (p.cornerstone_investors) rows.push(["Cornerstone investors",
    Array.isArray(p.cornerstone_investors) ? p.cornerstone_investors.join("; ")
                                           : p.cornerstone_investors]);
  // a deal with NO shoe has no stabilisation bid behind it — the structural
  // tell the desk reads on Medcaptain and Excelland, so state it either way
  if (p.greenshoe_pct) rows.push(["Greenshoe", p.greenshoe_pct.toFixed(0) + "%"]);
  else if (p.greenshoe_pct === 0) rows.push(["Greenshoe",
    p.greenshoe_note || "none — no stabilisation bid"]);
  if (p.listing_regime) rows.push(["Listing regime", p.listing_regime]);
  if (p.offer_period) rows.push(["Offer period", p.offer_period]);
  if (p.expected_timing) rows.push(["Listing", p.expected_timing]);
  if (p.rev_latest) rows.push(["Latest FY revenue", fmt.hkd(p.rev_latest)]);
  if (p.ni_latest != null) rows.push(["Latest FY net income", fmt.hkd(p.ni_latest)]);
  if (p.a_share_code) rows.push(["A-share", p.a_share_code +
    (p.a_price_now ? ` @ ¥${p.a_price_now}` : "")]);
  if (p.industry_en) rows.push(["Industry (AAStocks)", p.industry_en]);
  if (p.sponsors) rows.push(["Banks", p.sponsors]);
  if (p.use_of_proceeds) rows.push(["Use of proceeds", p.use_of_proceeds]);
  const size = p.expected_size_lo_usdm
    ? "US$" + p.expected_size_lo_usdm + "–" + p.expected_size_hi_usdm + "m"
    : (p.expected_size_hkdm ? fmt.hkd(p.expected_size_hkdm) : null);
  return `<div class="card ${offering ? "hotcard" : ""}">
  <div class="cardhd"><h4>${p.name}${p.name_cn ? " · " + p.name_cn : ""}</h4>
    <span class="badge ${offering ? "hot" : ""}">${
      offering ? "OFFERING NOW" : (p.status || "filed")}</span></div>
  <div class="meta">${p.subsector || p.sector || "sector not yet classified"}</div>
  <div class="chips">
  ${size ? `<span class="badge">${size}</span>`
         : `<span class="badge dim">size not guided</span>`}
  ${p.is_h_share ? '<span class="badge">A+H</span>' : ""}
  ${p.profitable_at_ipo === "Y" || p.profitable_at_ipo === true ? '<span class="badge good">profitable</span>'
    : p.profitable_at_ipo != null ? '<span class="badge bad">loss-making</span>' : ""}
  </div>
  ${p.expected_size_basis ? `<div class="sizebasis">size basis: ${p.expected_size_basis}</div>` : ""}
  <table class="cardtbl">${rows.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("")}</table>
  ${p.business_desc ? `<p class="desc clamp">${p.business_desc}</p>` +
      (p.business_desc.length > 200
        ? `<span class="more pmore" title="show the full description">more ▾</span>` : "") : ""}
  ${p.doc_link ? `<div class="meta"><a href="${p.doc_link}" rel="noopener">filing ↗</a></div>` : ""}
  <div class="meta comps">closest comps: ${comps.map(c => `${c.d.name} (${c.d.code})`).join(" · ") || "—"}</div></div>`;
}).join("");

// IPO calendar strip — the dates that matter this fortnight
(function calendar() {
  const ev = [];
  DATA.pipe.forEach(p => {
    if (p.offer_period) ev.push([p.offer_period.slice(-10), "offer closes", p.name]);
    if (/OFFERING/i.test(p.status || "") && p.expected_timing &&
        /^\d{4}-\d{2}-\d{2}$/.test(p.expected_timing))
      ev.push([p.expected_timing, "lists", p.name]);
  });
  ev.sort();
  const upc = ev.filter(([d]) => d >= DATA.as_of).slice(0, 8);
  $("#calendar").innerHTML = upc.length
    ? upc.map(([d, what, who]) =>
        `<span class="calchip"><b>${d.slice(5)}</b> ${who.split(" ")[0]} ${what}</span>`).join("")
    : `<span class="m">no dated events in the window</span>`;
})();

// 7) deal picker
function topComps(t, n) {
  const ranked = deals.map((d, i) => ({ d, s: similarityScore(t, d, CFGW, i + 1) }))
    .sort((a, b) => b.s - a.s);
  const pin = ranked.filter(c => FORCED.has(c.d.code) && c.d.name !== t.name)
    .map(c => ({ ...c, forced: true }));
  const rest = ranked.filter(c => !FORCED.has(c.d.code));
  return pin.concat(rest).slice(0, Math.max(n, pin.length));
}
// one matcher for every box: code with/without leading zeros, EN substring,
// CN substring, or the "Name (1234)" form the datalist inserts
function findDeal(q) {
  q = (q || "").trim();
  if (!q) return null;
  const par = q.match(/\((\d{3,5})\)\s*$/);
  if (par) q = par[1];
  const ql = q.toLowerCase();
  if (/^\d{3,5}$/.test(q)) {
    const c = q.padStart(4, "0");
    const hit = deals.find(d => d.code === c);
    if (hit) return hit;
  }
  return deals.find(d => (d.name || "").toLowerCase() === ql)
      || deals.find(d => (d.name || "").toLowerCase().startsWith(ql))
      || deals.find(d => (d.name || "").toLowerCase().includes(ql)
                      || (d.name_cn || "").includes(q));
}
const sel = $("#picker");
const opts = DATA.pipe.map(p => ({ v: "P:" + p.name, t: "▶ " + p.name + "  (pipeline)" }))
  .concat([...deals].sort((a, b) => (b.deal_size_hkdm || 0) - (a.deal_size_hkdm || 0))
    .map(d => ({ v: "D:" + d.code, t: d.name + " (" + d.code + ")" })));
sel.innerHTML = opts.map(o => `<option value="${o.v}">${o.t}</option>`).join("");
sel.addEventListener("change", () => { renderPick(); labReset(); });
// the finder drives the picker: type CATL or 3750, land on the deal
$("#deal-list").innerHTML = deals.map(d =>
  `<option value="${d.name} (${d.code})">`).join("");
const finder = $("#finder");
const jumpTo = () => {
  const hit = findDeal(finder.value);
  if (!hit) return;
  sel.value = "D:" + hit.code;
  finder.value = "";
  renderPick(); labReset();
};
finder.addEventListener("change", jumpTo);
finder.addEventListener("keydown", e => { if (e.key === "Enter") jumpTo(); });
const subsOpts = [...new Set(deals.map(d => d.subsector).filter(Boolean))].sort();
$("#ov-sub").innerHTML += subsOpts.map(x => `<option>${x}</option>`).join("");
// force-include: Enter (or datalist pick) adds a chip; × removes it
function drawFiChips() {
  $("#fi-chips").innerHTML = [...FORCED].map(c => {
    const d = deals.find(x => x.code === c);
    return `<span class="more" data-fi="${c}" title="remove">${d ? d.name : c} ✕</span>`;
  }).join(" ");
}
$("#fi-box").addEventListener("change", () => {
  const hit = findDeal($("#fi-box").value);
  if (hit) { FORCED.add(hit.code); $("#fi-box").value = ""; drawFiChips(); renderPick(); }
});
$("#fi-box").addEventListener("keydown", e => {
  if (e.key !== "Enter") return;
  const hit = findDeal($("#fi-box").value);
  if (hit) { FORCED.add(hit.code); $("#fi-box").value = ""; drawFiChips(); renderPick(); }
});
$("#fi-chips").addEventListener("click", e => {
  const chip = e.target.closest("[data-fi]");
  if (chip) { FORCED.delete(chip.dataset.fi); drawFiChips(); renderPick(); }
});
["#ov-name", "#ov-sub", "#ov-size", "#ov-pe", "#ov-prof", "#ov-ah", "#cs-box", "#cs-first"].forEach(id =>
  $(id).addEventListener("change", () => { renderPick(); labReset(); }));
$("#ov-clear").addEventListener("click", () => {
  ["#ov-name", "#ov-size", "#ov-pe"].forEach(id => $(id).value = "");
  ["#ov-sub", "#ov-prof", "#ov-ah"].forEach(id => $(id).value = "");
  renderPick(); labReset(); });
function overrides() {
  const g = id => ($(id).value || "").trim();
  return { name: g("#ov-name"), sub: g("#ov-sub"), size: parseFloat(g("#ov-size")) || null,
           pe: parseFloat(g("#ov-pe")) || null, prof: g("#ov-prof"), ah: g("#ov-ah") };
}
function csTargetKeys(meta) {
  const own = (meta && meta.cornerstone_keys ? meta.cornerstone_keys.split(";") : []);
  const typed = ($("#cs-box").value || "").trim().toLowerCase();
  if (typed) own.push(typed);
  return own.filter(Boolean).slice(0, 8);
}
function applyOv(t) {
  const o = overrides();
  t.cs_keys = csTargetKeys(t.meta);
  t.cs_first = $("#cs-first").checked;
  if (o.name) t.name = o.name;
  if (o.sub) { t.subsector = o.sub;
    const hit = deals.find(d => d.subsector === o.sub);
    if (hit) t.sector = hit.sector; }
  if (o.size) t.size = o.size;
  if (o.pe) t.pe = o.pe;
  if (o.prof) t.profitable = o.prof === "Y";
  if (o.ah) t.is_h = o.ah === "Y";
  return t;
}
function target() {
  const v = sel.value;
  if (v.startsWith("P:")) {
    const p = DATA.pipe.find(x => "P:" + x.name === v);
    return applyOv({ name: p.name, sector: p.sector, subsector: p.subsector, size: p.expected_size_hkdm,
      pe: p.pe_expected_mid || null,
      profitable: p.profitable_at_ipo, is_h: p.is_h_share, ref_date: DATA.as_of, meta: p });
  }
  const d = deals.find(x => "D:" + x.code === v);
  return applyOv({ name: d.name, sector: d.sector, subsector: d.subsector, size: d.deal_size_hkdm,
    pe: d.pe_ipo || null,
    profitable: d.profitable_at_ipo, is_h: d.is_h_share, ref_date: d.ipo_date, meta: d });
}
// ------------------------------------------------------------ Deal Brief ----
// The conviction one-pager: what the terms are, what the peers did, and — for
// an A+H name — where peer discounts say the H should price vs its live A line.
function renderBrief(t, comps) {
  const host = $("#deal-brief");
  const m = t.meta || {};
  const peers = comps.map(c => c.d);
  const med = f => median(peers.map(f).filter(v => v != null));
  const n_of = f => peers.map(f).filter(v => v != null).length;
  const tiles = [];
  if (m.status && /OFFERING/i.test(m.status)) {
    tiles.push([m.status, "status", "hot"]);
    if (m.range_lo && m.range_hi) tiles.push([`HK$${m.range_lo}–${m.range_hi}`, "price range"]);
    else if (m.range_hi) tiles.push([`≤ HK$${m.range_hi}`, "maximum offer price"]);
    if (m.pe_expected_lo) tiles.push([`${m.pe_expected_lo}–${m.pe_expected_hi}x`, "expected P/E at range"]);
    if (m.pe_at_h_cap) tiles.push([`≈${m.pe_at_h_cap}x`, "implied P/E at the H cap (A-anchored)"]);
    if (m.a_pe_ttm) tiles.push([`${m.a_pe_ttm}x`, `its A-share P/E TTM (¥${m.a_mktcap_bn_cny}bn cap)`]);
    if (m.h_cap_vs_a_pct != null && m.h_cap_vs_a_pct > -100) {
      // shown in the book's direction (A over H) so it is comparable with the
      // "A prem at IPO" column and the peer-median tile beside it; the raw
      // H-over-A read stays in the label so neither reading is ambiguous
      const aOver = (1 / (1 + m.h_cap_vs_a_pct / 100) - 1) * 100;
      tiles.push([fmt.pct(aOver),
        `A premium over the H cap (H cap is ${fmt.pct(m.h_cap_vs_a_pct)} vs the A line)`]);
    }
    if (m.cornerstone_pct) tiles.push([m.cornerstone_pct.toFixed(0) + "%", "cornerstone locked"]);
    if (m.expected_timing) tiles.push([m.expected_timing, "expected listing"]);
  } else if (m.first_day_return_pct != null) {
    tiles.push([fmt.pct(m.first_day_return_pct), "its own day-1"]);
    if (m.ret_1m_pct != null) tiles.push([fmt.pct(m.ret_1m_pct), "its own 1-month"]);
  }
  // the four medians a position is actually sized off: the pop you get on
  // day 1, then what the AFTERMARKET did at 1w / 1m / 3m once the pop is out
  tiles.push([med(d => d.first_day_return_pct) == null ? "—" : fmt.pct(med(d => d.first_day_return_pct)),
              `peer median DAY-1 POP (n=${n_of(d => d.first_day_return_pct)})`, "primary"]);
  [["aftermkt_1w_pct", "1-WEEK ex-pop"], ["aftermkt_1m_pct", "1-MONTH ex-pop"],
   ["aftermkt_3m_pct", "3-MONTH ex-pop"]].forEach(([f2, lab]) => {
    const m2 = med(d => d[f2]);
    tiles.push([m2 == null ? "—" : fmt.pct(m2),
                `peer median ${lab} (n=${n_of(d => d[f2])})`,
                m2 == null ? "" : m2 >= 0 ? "good" : "bad"]);
  });
  // base rate + downside — the odds and the loss case
  const d1s = peers.map(d => d.first_day_return_pct).filter(v => v != null);
  if (d1s.length) {
    const up = d1s.filter(v => v > 0).length;
    tiles.push([`${up} of ${d1s.length}`, "peers closed ABOVE offer on day 1",
                up * 2 >= d1s.length ? "good" : "bad"]);
    tiles.push([fmt.pct(Math.min(...d1s)), "worst peer day-1 (downside case)", "bad"]);
  }
  const medPrem = med(d => d.a_premium_ipo_pct);
  if (medPrem != null)
    tiles.push([fmt.pct(medPrem), `peer median A prem at IPO (n=${n_of(d => d.a_premium_ipo_pct)})`]);
  // A+H applicant: implied H pricing zone off the LIVE A line.
  // A-premium convention: peers struck at A-prem p means H = A_HKD / (1 + p).
  let implied = "";
  if (m.a_price_now && m.fx_now && medPrem != null) {
    const zone = m.a_price_now * m.fx_now / (1 + medPrem / 100);
    implied = `<p class="sub"><b>Implied H price at the peer-median A-premium:</b>
      A ¥${m.a_price_now} × ${m.fx_now} FX ÷ (1 ${medPrem < 0 ? "−" : "+"} ${Math.abs(medPrem).toFixed(0)}%)
      = <b>HK$${zone.toFixed(2)}</b>` +
      (m.range_hi ? ` vs the filed ${m.range_lo ? "range HK$" + m.range_lo + "–" + m.range_hi : "cap HK$" + m.range_hi}` : "") +
      ` <span class="m">(peer premia vary widely — a zone, not a target)</span></p>`;
  }
  const pre = (DATA.ahpaths[m.code] || {}).a_pre_runup_pct;
  const preTile = pre != null ? `<div class="tile"><div class="v">${fmt.pct(pre)}</div><div class="l">its A-share, month BEFORE H-IPO</div></div>` : "";
  const docLink = m.doc_link
    ? ` <a class="brieflink" href="${m.doc_link}" rel="noopener">prospectus ↗</a>` : "";
  host.innerHTML = `<div class="brief"><h3>Deal brief — ${t.name || "target"}${docLink}</h3>
    <div class="tiles">` + tiles.map(([v, l, cls]) =>
      `<div class="tile ${cls || ""}"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("") +
    preTile + `</div>${implied}
    <p class="note">Peer stats = the top-${peers.length} comps below; sizes marked estimated carry their press source.</p></div>`;
}

function renderPick() {
  const t = target();
  const comps = topComps(t, 5);
  renderBrief(t, topComps(t, 8));
  const pctile = t.size && sized.length ? Math.round(100 * sized.filter(d => d.deal_size_hkdm < t.size).length / sized.length) : null;
  const bkt = t.size == null ? "n/a" : DATA.cfg.size_buckets_hkdm.find(b => t.size >= b.min).label;
  $("#pick-summary").innerHTML =
    `<div class="tiles"><div class="tile"><div class="v">${bkt}</div><div class="l">size bucket ${t.size ? "(" + fmt.hkd(t.size) + ")" : ""}</div></div>
     <div class="tile"><div class="v">${pctile == null ? "—" : "P" + pctile}</div><div class="l">size percentile vs 2021–26</div></div>
     <div class="tile"><div class="v">${t.subsector || "—"}</div><div class="l">subsector (gates the comps)</div></div></div>`;
  const pe5 = median(comps.map(c => c.d.pe_ipo).filter(v => v > 0));
  const ps5 = median(comps.map(c => c.d.ps_ipo).filter(v => v > 0));
  const sgn = (v, key) => `<td class="num ${key ? "keycol " : ""}${v > 0 ? "up" : v < 0 ? "down" : ""}">${fmt.pct(v)}</td>`;
  const anyCS = comps.some(c => c.d._cs_overlap > 0);
  $("#pick-table").innerHTML = `<table class="tbl comp-table"><thead><tr>
    <th>#</th><th>Comp</th><th>Subsector</th><th>IPO</th><th class="num">Size</th>
    <th class="num">P/E</th><th class="num">P/S</th><th class="num keycol">Day-1</th><th class="num keycol">1-month</th><th class="num">3-month</th><th class="num">A prem@IPO</th>${anyCS ? '<th class="num">Shared CS</th>' : ""}<th>Match</th></tr></thead><tbody>` +
    comps.map((c, i) => {
      const hit = t.subsector && c.d.subsector === t.subsector;
      return `<tr><td>${i + 1}</td><td>${c.d.name} (${c.d.code})${
        c.forced ? ' <span class="more" title="force-included by you — remove with the ✕ chip above">pinned</span>' : ""}</td><td>${c.d.subsector || "—"}</td>
      <td>${c.d.ipo_date}</td><td class="num">${fmt.hkd(c.d.deal_size_hkdm)}</td>
      <td class="num">${fmt.x(c.d.pe_ipo)}</td><td class="num">${fmt.x(c.d.ps_ipo)}</td>
      ${sgn(c.d.first_day_return_pct, 1)}${sgn(c.d.ret_1m_pct, 1)}${sgn(c.d.ret_3m_pct)}
      <td class="num">${c.d.a_premium_ipo_pct == null ? (c.d.a_share_code ? "—" : "N/A") : fmt.pct(c.d.a_premium_ipo_pct)}</td>
      ${anyCS ? `<td class="num">${c.d._cs_overlap
        ? `<span class="csshare" title="shared cornerstone keys: ${(c.d._cs_names || []).join(", ")}">${c.d._cs_overlap}× <span class="m">${(c.d._cs_names || []).slice(0, 2).join(", ")}</span></span>`
        : "—"}</td>` : ""}
      <td class="${hit ? "hit" : "fallback"}">${hit ? "subsector" : "sector"}</td></tr>`;
    }).join("") +
    `</tbody></table>
    <p class="note">top-5 median: P/E ${pe5 ? pe5.toFixed(1) + "x" : "n/m"} · P/S ${ps5 ? ps5.toFixed(1) + "x" : "n/a"} —
    scoring identical to the Excel screener (weights: subsector ${CFGW.sub} ≫ sector ${CFGW.sec}, size ${CFGW.size}, P/E proximity ${CFGW.pe}, profitability ${CFGW.prof}, A/H ${CFGW.ah}, recency ${CFGW.rec})</p>`;
}
renderPick();

// ---------------------------------------------------------------- Comps Lab --
// The point of the whole tool: hold the candidate against a HAND-CHOSEN comp
// set, PAINT the comps into two camps (red/blue), and see which factor - or
// combination - actually separates them. Everything below reads the paint.
const METRICS = [
  ["TERMS", null, null],
  ["Deal size", "deal_size_hkdm", v => fmt.hkd(v)],
  ["Mkt cap at IPO", "mktcap_ipo_hkdm", v => fmt.hkd(v)],
  // company cap off the A line today (all share classes x A price). An A+H
  // name's H tranche is a slice; this is the whole issuer.
  ["A-line mkt cap now", "a_mktcap_now_hkdm", (v, d) => v == null
     ? (d && d.a_share_code ? "—" : "no A line") : fmt.hkd(v)],
  ["% of cap struck", "pct_of_cap", v => v == null ? "—" : v.toFixed(0) + "%"],
  // blank is an ANSWER here, not missing data: n/m = loss-maker, pre-rev = no
  // revenue line in the filed P&L (no denominator exists)
  ["P/E at IPO", "pe_ipo", (v, d) => v == null ? (d && d.profitable_at_ipo === "N" ? "n/m" : "—") : fmt.x(v)],
  ["P/S at IPO", "ps_ipo", (v, d) => v == null ? (d && d.rev_latest === 0 ? "pre-rev" : "—") : fmt.x(v)],
  // live-only: fills on the terminal (BBG Verify col S); the HTML shows where
  // to get it rather than pretending a number exists
  ["P/S today", "ps_now", v => v == null ? "terminal (BBG)" : fmt.x(v)],
  ["DEMAND", null, null],
  ["Public sub", "oversub_public_mult", v => fmt.x(v)],
  ["Instl sub", "oversub_intl_mult", v => fmt.x(v)],
  ["Cornerstone %", "cornerstone_pct", v => v == null ? "—" : v.toFixed(0) + "%"],
  // what can actually TRADE on day 1: the offer less the locked-up cornerstone
  // take. The money/share figures need no market cap, so they survive rows
  // whose cap is not derivable; the % is that same number over the cap.
  ["Eff. free float (HK$m)", "eff_free_float_hkdm", v => fmt.hkd(v)],
  ["Eff. free float (shares)", "eff_free_float_shares",
     v => v == null ? "—" : v.toLocaleString()],
  ["Eff. free float", "eff_free_float_pct", v => v == null ? "—" : v.toFixed(1) + "% of cap"],
  ["Greenshoe size", "greenshoe_pct", v => v == null ? "—" : v.toFixed(0) + "%"],
  ["Greenshoe outcome", "greenshoe_exercised_final", v => v || "—"],
  ["Shoe ends (filed)", "stabilization_end_date", v => v || "—"],
  ["PERFORMANCE (vs offer)", null, null],
  ["Day-1", "first_day_return_pct", v => fmt.pct(v)],
  ["1-week", "ret_1w_pct", v => fmt.pct(v)],
  ["1-month", "ret_1m_pct", v => fmt.pct(v)],
  ["3-month", "ret_3m_pct", v => fmt.pct(v)],
  ["Day-1 open pop", "day1_open_pop_pct", v => fmt.pct(v)],
  ["Day-1 open\u2192close", "day1_open_close_pct", v => fmt.pct(v)],
  ["1w ex-pop", "aftermkt_1w_pct", v => fmt.pct(v)],
  ["1m ex-pop", "aftermkt_1m_pct", v => fmt.pct(v)],
  ["3m ex-pop", "aftermkt_3m_pct", v => fmt.pct(v)],
  ["Alpha 1m vs index", "alpha_1m_pct", v => fmt.pct(v)],
  ["Alpha 1m ex-pop", "alpha_1m_expop_pct", v => fmt.pct(v)],
  ["Since IPO", "since_ipo_pct", v => fmt.pct(v)],
  ["A / H", null, null],
  ["A premium vs H at IPO", "a_premium_ipo_pct", v => fmt.pct(v)],
  ["A premium today", "a_premium_now", v => v == null ? "N/A" : fmt.pct(100 * v)],
  ["BANKS", null, null],
  ["Industry (AAStocks)", "industry_en", v => v || "—"],
  ["Sponsors", "sponsors_display", v => banksCell(v, 3)],
  ["Bookrunners", "bookrunners_display", v => banksCell(v, 4)],
  ["Cornerstone investors", "cornerstone_investors",
   v => Array.isArray(v) && v.length
        ? `<span class="csxp">${v.slice(0, 2).join(" · ")}` +
          (v.length > 2 ? ` <span class="more csmore" data-full="${v.join("; ").replace(/"/g, "&quot;")}"
             title="show the full list">+${v.length - 2} all ▾</span>` : "") + `</span>`
        : "—"],
];
const DRIVERS = [
  ["deal size", d => d.deal_size_hkdm > 0 ? Math.log10(d.deal_size_hkdm) : null,
   v => fmt.hkd(Math.pow(10, v)), true],
  ["mkt cap", d => d.mktcap_ipo_hkdm > 0 ? Math.log10(d.mktcap_ipo_hkdm) : null,
   v => fmt.hkd(Math.pow(10, v)), true],
  ["public sub", d => d.oversub_public_mult > 0 ? Math.log10(d.oversub_public_mult) : null,
   v => Math.pow(10, v).toFixed(0) + "x", true],
  ["instl sub", d => d.oversub_intl_mult > 0 ? Math.log10(d.oversub_intl_mult) : null,
   v => Math.pow(10, v).toFixed(1) + "x", true],
  ["cornerstone %", d => d.cornerstone_pct, v => v.toFixed(0) + "%", false],
  ["A prem at IPO", d => d.a_premium_ipo_pct, v => v.toFixed(0) + "%", false],
  ["P/E at IPO", d => d.pe_ipo, v => v.toFixed(0) + "x", false],
  ["P/S at IPO", d => d.ps_ipo, v => v.toFixed(1) + "x", false],
  ["% of cap", d => d.pct_of_cap, v => v.toFixed(0) + "%", false],
  ["greenshoe %", d => d.greenshoe_pct, v => v.toFixed(0) + "%", false],
  ["day-1", d => d.first_day_return_pct, v => fmt.pct(v), false],
  ["1m ex-pop", d => d.aftermkt_1m_pct, v => fmt.pct(v), false],
  ["A prem today", d => d.a_premium_now == null ? null : 100 * d.a_premium_now,
   v => fmt.pct(v), false],
];
const RET_OPTS = [
  ["day-1", d => d.first_day_return_pct], ["1-week", d => d.ret_1w_pct],
  ["1-month", d => d.ret_1m_pct], ["3-month", d => d.ret_3m_pct],
  ["1m ex-pop", d => d.aftermkt_1m_pct], ["1w ex-pop", d => d.aftermkt_1w_pct],
  ["3m ex-pop", d => d.aftermkt_3m_pct], ["alpha 1m", d => d.alpha_1m_pct],
  ["alpha 1m ex-pop", d => d.alpha_1m_expop_pct],
  ["day-1 open\u2192close", d => d.day1_open_close_pct],
  ["since IPO", d => d.since_ipo_pct],
];
const OUTCOMES = [
  ["A premium sign today", d => d.a_premium_now == null ? null : d.a_premium_now > 0,
   "A above H", "H above A"],
  ["A prem sign at IPO", d => d.a_premium_ipo_pct == null ? null : d.a_premium_ipo_pct > 0,
   "H struck ABOVE A", "H struck below A"],
  ["day-1 direction", d => d.first_day_return_pct == null ? null : d.first_day_return_pct > 0,
   "up on debut", "down on debut"],
  ["1m beat its index", d => d.alpha_1m_pct == null ? null : d.alpha_1m_pct > 0,
   "beat index", "lagged index"],
  ["3m above offer", d => d.ret_3m_pct == null ? null : d.ret_3m_pct > 0,
   "above offer at 3m", "below offer at 3m"],
  ["pop held (1m ex-pop)", d => d.aftermkt_1m_pct == null ? null : d.aftermkt_1m_pct > 0,
   "held after day-1", "faded after day-1"],
];
const RED = "#e34948", BLUE = "#2a78d6";
let labSel = new Set();
let labPaint = {};                // code -> "r" | "b" | undefined (grey)
function ahOnly() { return $("#lab-ashare").checked; }
function labCandidates() {
  const t = target();
  let pool = ahOnly() ? deals.filter(d => d.a_share_code) : deals;
  const ind = (t.meta || {}).industry_en;
  if ($("#lab-industry").checked && ind)
    pool = pool.filter(d => d.industry_en === ind);
  return pool.map((d, i) => ({ d, s: similarityScore(t, d, CFGW, i + 1) }))
    .sort((a, b) => b.s - a.s).slice(0, 12).map(c => c.d);
}
function autoPaint() {
  const oc = OUTCOMES[+$("#lab-outcome").value];
  labPaint = {};
  labChosen().forEach(d => {
    const v = oc[1](d);
    if (v === true) labPaint[d.code] = "r";
    else if (v === false) labPaint[d.code] = "b";
  });
}
function labReset() {
  labSel = new Set(labCandidates().slice(0, 8).map(d => d.code));
  autoPaint();
  renderLab();
}
function labChosen() { return deals.filter(d => labSel.has(d.code)); }
function paintOf(d) { return labPaint[d.code]; }
function paintColor(d) { return paintOf(d) === "r" ? RED : paintOf(d) === "b" ? BLUE : "var(--mid)"; }

function renderLab() {
  const t = target();
  const cands = labCandidates();
  const extra = labChosen().filter(d => !cands.includes(d));
  // 1. chooser with paint chips: checkbox picks, the dot cycles red/blue/grey
  $("#lab-pick").innerHTML = cands.concat(extra).map(d => {
    const pc = paintOf(d) === "r" ? RED : paintOf(d) === "b" ? BLUE : "var(--mid)";
    return `<span class="labchk"><input type="checkbox" data-code="${d.code}" ${labSel.has(d.code) ? "checked" : ""}>
      <span class="paint" data-code="${d.code}" style="background:${pc}" title="click to repaint red/blue/grey"></span>
      ${d.name} <span class="m">(${d.code})</span></span>`;
  }).join("") +
    `<span class="labchk">add: <input id="lab-add" placeholder="name or code" size="13"></span>`;
  $("#lab-pick").querySelectorAll("input[type=checkbox]").forEach(cb =>
    cb.addEventListener("change", () => {
      cb.checked ? labSel.add(cb.dataset.code) : (labSel.delete(cb.dataset.code), delete labPaint[cb.dataset.code]);
      renderLab();
    }));
  $("#lab-pick").querySelectorAll(".paint").forEach(sw =>
    sw.addEventListener("click", () => {
      const c = sw.dataset.code, cur = labPaint[c];
      labPaint[c] = cur === "r" ? "b" : cur === "b" ? undefined : "r";
      renderLab();
    }));
  const add = $("#lab-add");
  add.setAttribute("list", "deal-list");
  const addFromBox = () => {
    const hit = findDeal(add.value);
    if (hit) { labSel.add(hit.code); add.value = ""; renderLab(); }
  };
  add.addEventListener("keydown", e => { if (e.key === "Enter") addFromBox(); });
  add.addEventListener("change", addFromBox);
  const chosen = labChosen();
  if (!chosen.length) { $("#lab-matrix").innerHTML = "<p class='note'>tick at least one comp</p>"; return; }
  const reds = chosen.filter(d => paintOf(d) === "r"), blues = chosen.filter(d => paintOf(d) === "b");
  $("#lab-paintnote").innerHTML =
    `<span class="dot" style="background:${RED}"></span> ${reds.length} red · ` +
    `<span class="dot" style="background:${BLUE}"></span> ${blues.length} blue · ` +
    `${chosen.length - reds.length - blues.length} unpainted — click a comp's dot to repaint; ` +
    `the selector below repaints all from an outcome.`;

  // 2. matrix — candidate first, per-row hi/lo edges, painted headers
  const cols = [{ name: (t.name || "target") + " (target)", d: t.meta || {}, paint: null }]
    .concat(chosen.map(d => ({ name: d.name, d, paint: paintOf(d) })));
  const SIGNED = new Set(["first_day_return_pct", "ret_1w_pct", "ret_1m_pct", "ret_3m_pct",
    "aftermkt_1m_pct", "aftermkt_1w_pct", "aftermkt_3m_pct", "alpha_1m_pct",
    "alpha_1m_expop_pct", "day1_open_close_pct", "since_ipo_pct",
    "a_premium_ipo_pct", "a_premium_now"]);
  let html = `<table class="tbl labtbl"><thead><tr><th></th>` +
    cols.map((c, i) => `<th class="${i ? "" : "tgtcol"}">` +
      (c.paint ? `<span class="dot" style="background:${c.paint === "r" ? RED : BLUE}"></span> ` : "") +
      `${c.name}</th>`).join("") + `</tr></thead><tbody>`;
  METRICS.forEach(([label, field, fmtf]) => {
    if (!field) { html += `<tr class="band"><td colspan="${cols.length + 1}">${label}</td></tr>`; return; }
    const vals = cols.map(c => c.d[field]);
    const nums = vals.filter(v => typeof v === "number");
    const lo = Math.min(...nums), hi = Math.max(...nums);
    html += `<tr><td>${label}</td>` + vals.map((v, i) => {
      let cls = i ? "" : "tgtcol";
      if (typeof v === "number" && nums.length > 2 && hi > lo)
        cls += v === hi ? " hi" : v === lo ? " lo" : "";
      // a return is the one metric where the SIGN is the headline, so colour it
      if (SIGNED.has(field) && typeof v === "number")
        cls += v > 0 ? " up" : v < 0 ? " down" : "";
      return `<td class="num ${cls}">${fmtf(v, cols[i].d)}</td>`;
    }).join("") + `</tr>`;
  });
  $("#lab-matrix").innerHTML = html + "</tbody></table>";

  renderPaths(chosen);
  renderHPaths(chosen);
  renderStrips(chosen, reds, blues);
  renderXY(chosen);
  renderHist(chosen);
  renderAH(chosen);
}

// 3. one strip per factor, ALL AT ONCE, ordered by how cleanly red/blue split.
// The faint band behind each strip is the whole 511-deal universe (P10-P90 with
// a median tick) so every dot has market context.
const GOLD = "#eda100";
function renderStrips(chosen, reds, blues) {
  const tmeta = (target().meta) || {};
  if (!reds.length || !blues.length) {
    $("#lab-strips").innerHTML = "<p class='note'>Paint at least one comp red and one blue " +
      "(click the dots above, or pick an outcome) and every factor lights up here.</p>";
    return;
  }
  const rows = DRIVERS.map(([name, f, disp, islog]) => {
    const rv = reds.map(f).filter(v => v != null), bv = blues.map(f).filter(v => v != null);
    const uni = deals.map(f).filter(v => v != null).sort((a, b) => a - b);
    if (!uni.length) return null;
    const q = p => uni[Math.floor(p * (uni.length - 1))];
    const all = rv.concat(bv);
    const both = rv.length > 0 && bv.length > 0;
    const mr = rv.length ? median(rv) : null, mb = bv.length ? median(bv) : null;
    const spread = all.length ? (Math.max(...all) - Math.min(...all) || 1) : 1;
    return { name, f, disp, mr, mb,
             miss: (reds.length - rv.length) + (blues.length - bv.length),
             sep: both ? Math.abs(mr - mb) / spread : -1,
             p10: q(.1), p50: q(.5), p90: q(.9),
             lo: Math.min(...(all.length ? all : [q(.1)]), q(.1)),
             hi: Math.max(...(all.length ? all : [q(.9)]), q(.9)) };
  }).filter(Boolean).sort((a, b) => b.sep - a.sep);

  // plain-English verdict instead of a bare percentage
  const verdict = v => v < 0 ? ["no data on one side", "vnone"]
    : v >= 0.45 ? ["SPLITS THE TWO GROUPS", "vstrong"]
    : v >= 0.22 ? ["leans apart", "vmed"]
    : ["barely separates", "vweak"];

  const W = 460, PAD = 12;
  const rowHtml = r => {
    const x = v => PAD + (W - 2 * PAD) * (v - r.lo) / ((r.hi - r.lo) || 1);
    const seen = {};
    const dot = (d, v) => {
      const key = Math.round(x(v) / 8);
      const k = (seen[key] = (seen[key] || 0) + 1) - 1;
      const cy = 20 + (k % 2 ? -1 : 1) * Math.ceil(k / 2) * 8;
      return `<circle cx="${x(v).toFixed(1)}" cy="${cy}" r="5.5" fill="${paintOf(d) === "r" ? RED : BLUE}"
        fill-opacity=".8" stroke="var(--surface-1)" stroke-width="1.2"><title>${d.name}: ${r.disp(v)}</title></circle>`;
    };
    const dots = g => g.map(d => { const v = r.f(d); return v == null ? "" : dot(d, v); }).join("");
    const med = (v, col) => v == null ? "" :
      `<line x1="${x(v).toFixed(1)}" x2="${x(v).toFixed(1)}" y1="8" y2="32" stroke="${col}" stroke-width="2"/>`;
    const tv = r.f(tmeta);
    const tmark = (tv == null || !Number.isFinite(x(tv))) ? "" :
      `<polygon points="${x(tv).toFixed(1)},6 ${(x(tv)+6.5).toFixed(1)},13 ${x(tv).toFixed(1)},20 ${(x(tv)-6.5).toFixed(1)},13"
        fill="${GOLD}" stroke="var(--surface-1)" stroke-width="1.2"><title>TARGET: ${r.disp(tv)}</title></polygon>`;
    const [word, cls] = verdict(r.sep);
    const gap = r.sep < 0 ? "" :
      `<span class="gapline"><b style="color:${RED}">${r.disp(r.mr)}</b> vs <b style="color:${BLUE}">${r.disp(r.mb)}</b></span>`;
    return `<div class="strow">
      <div class="sname">${r.name}${r.miss ? ` <span class="m">(${r.miss} n/a)</span>` : ""}</div>
      <div class="sverdict"><span class="vchip ${cls}">${word}</span>${gap}</div>
      <div class="svizwrap"><svg class="sviz" viewBox="0 0 ${W} 40" preserveAspectRatio="none">
        <rect x="${x(r.p10).toFixed(1)}" y="15" width="${(x(r.p90) - x(r.p10)).toFixed(1)}" height="10"
          rx="5" fill="var(--surface-2)"/>
        <line x1="${x(r.p50).toFixed(1)}" x2="${x(r.p50).toFixed(1)}" y1="12" y2="28" stroke="var(--mid)" stroke-width="1"/>
        ${med(r.mr, RED)}${med(r.mb, BLUE)}${dots(reds)}${dots(blues)}${tmark}
      </svg>
      <div class="saxrow"><span>${r.disp(r.lo)}</span><span>${r.disp(r.hi)}</span></div></div></div>`;
  };
  const top = rows.slice(0, 6), rest = rows.slice(6);
  $("#lab-strips").innerHTML =
    `<div class="striplegend"><span><i class="sw" style="background:${GOLD};
       clip-path:polygon(50% 0,100% 50%,50% 100%,0 50%)"></i>your candidate</span>
     <span><i class="sw" style="background:${RED}"></i>red group median &amp; deals</span>
     <span><i class="sw" style="background:${BLUE}"></i>blue group median &amp; deals</span>
     <span><i class="sw" style="background:var(--surface-2);border:1px solid var(--line)"></i>
       middle 80% of all ${deals.length} HK IPOs</span></div>` +
    top.map(rowHtml).join("") +
    (rest.length ? `<details class="morefac"><summary>${rest.length} more factors</summary>` +
       rest.map(rowHtml).join("") + `</details>` : "") +
    `<p class="note">Factors are ordered by how cleanly the red and blue groups separate — the top row is
     the strongest candidate explanation for why your two camps behaved differently. Each strip is a
     number line: the grey capsule is where the whole market sits, the coloured bars are the two group
     medians, and every dot is one comp. Log scale on size, market cap and both subscriptions.</p>`;
}

// 4. returns vs factor — the trading question, with one-click presets
function renderXY(chosen) {
  const dx = DRIVERS[+$("#lab-x").value];
  const dyDef = RET_OPTS[+$("#lab-y").value];
  const dy = [dyDef[0], dyDef[1], v => fmt.pct(v), false];
  const pts = chosen.map(d => ({ x: dx[1](d), y: dy[1](d), d }))
    .filter(p => p.x != null && p.y != null);
  const host = $("#lab-xy");
  host.innerHTML = "";
  if (pts.length < 2) { host.innerHTML = "<p class='note'>not enough comps carry both fields</p>"; return; }
  const W = fitW(host, 560), H = 300, M = { l: 60, r: 14, t: 12, b: 44 };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}` }, host);
  const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
  const xr = [Math.min(...xs), Math.max(...xs)], yr = [Math.min(0, ...ys), Math.max(0, ...ys)];
  const xpad = (xr[1] - xr[0]) * 0.08 || 1, ypad = (yr[1] - yr[0]) * 0.08 || 1;
  const X = v => M.l + (W - M.l - M.r) * (v - xr[0] + xpad) / (xr[1] - xr[0] + 2 * xpad);
  const Y = v => H - M.b - (H - M.t - M.b) * (v - yr[0] + ypad) / (yr[1] - yr[0] + 2 * ypad);
  el("line", { x1: M.l, x2: W - M.r, y1: Y(0), y2: Y(0), stroke: "var(--mid)", "stroke-width": .9 }, svg);
  niceTicks(yr[0], yr[1], 5).forEach(v => {
    el("line", { x1: M.l, x2: W - M.r, y1: Y(v), y2: Y(v), class: "gridline" }, svg);
    const tt = el("text", { x: M.l - 6, y: Y(v) + 3, "text-anchor": "end" }, svg);
    tt.textContent = Math.round(v) + "%";
  });
  niceTicks(xr[0], xr[1], 5).forEach(v => {
    const tt = el("text", { x: X(v), y: H - 26, "text-anchor": "middle" }, svg);
    tt.textContent = dx[3] ? dx[2](v) : Math.round(v * 10) / 10;
  });
  const xl = el("text", { x: (M.l + W - M.r) / 2, y: H - 6, "text-anchor": "middle", class: "axlabel" }, svg);
  xl.textContent = dx[0] + (dx[3] ? " (log)" : "");
  const yl = el("text", { x: 12, y: M.t + 8, class: "axlabel" }, svg);
  yl.textContent = dy[0] + " return";
  // least-squares fit + correlation: a scatter without them is decoration
  const n = pts.length, mx = pts.reduce((s2, q) => s2 + q.x, 0) / n,
        my = pts.reduce((s2, q) => s2 + q.y, 0) / n;
  let sxy = 0, sxx = 0, syy = 0;
  pts.forEach(q => { sxy += (q.x - mx) * (q.y - my); sxx += (q.x - mx) ** 2; syy += (q.y - my) ** 2; });
  if (sxx > 0 && n >= 3) {
    const b1 = sxy / sxx, b0 = my - b1 * mx;
    const x1 = xr[0] - xpad, x2 = xr[1] + xpad;
    el("line", { x1: X(x1), x2: X(x2), y1: Y(b0 + b1 * x1), y2: Y(b0 + b1 * x2),
      stroke: "var(--mid)", "stroke-width": 1.4, "stroke-dasharray": "5,4" }, svg);
  }
  const r = (sxx && syy) ? sxy / Math.sqrt(sxx * syy) : 0;
  pts.forEach(p => {
    const c = el("circle", { cx: X(p.x), cy: Y(p.y), r: 6.5, fill: paintColor(p.d),
      "fill-opacity": .82, stroke: "var(--surface-1)", "stroke-width": 1.2 }, svg);
    hover(c, () => `<b>${p.d.name} (${p.d.code})</b>${dx[0]}: ${dx[2](p.x)} · ${dy[0]}: ${fmt.pct(p.y)}`);
  });
  // the candidate, if it carries both fields
  const tm = (target().meta) || {};
  const tx2 = dx[1](tm), ty2 = dy[1](tm);
  if (tx2 != null && ty2 != null && Number.isFinite(X(tx2)) && Number.isFinite(Y(ty2))) {
    const dmd = el("polygon", { points:
      `${X(tx2)},${Y(ty2) - 8} ${X(tx2) + 8},${Y(ty2)} ${X(tx2)},${Y(ty2) + 8} ${X(tx2) - 8},${Y(ty2)}`,
      fill: GOLD, stroke: "var(--surface-1)", "stroke-width": 1.4 }, svg);
    hover(dmd, () => `<b>${target().name} (target)</b>${dx[0]}: ${dx[2](tx2)} · ${dy[0]}: ${fmt.pct(ty2)}`);
  }
  host.insertAdjacentHTML("beforeend",
    `<p class="note"><span style="color:${GOLD}">◆</span> candidate ·
     <span style="color:${RED}">●</span> red · <span style="color:${BLUE}">●</span> blue ·
     dashed line = best fit · correlation ${r >= 0 ? "+" : ""}${r.toFixed(2)}
     ${Math.abs(r) < 0.2 ? "(none)" : Math.abs(r) < 0.45 ? "(weak)" : "(clear)"} on ${n} comps</p>`);
}
const XY_PRESETS = [
  ["sub → day-1", 2, 0], ["size → 1m", 0, 2], ["H disc → 3m", 5, 3],
  ["cornerstone → ex-pop", 4, 4], ["P/E → 1m", 6, 2],
];

// 5. universe histogram with the painted comps dropped on top
function renderHist(chosen) {
  const dr = DRIVERS[+$("#lab-hfac").value];
  const host = $("#lab-hist");
  host.innerHTML = "";
  const uni = deals.map(dr[1]).filter(v => v != null);
  if (uni.length < 20) { host.innerHTML = "<p class='note'>no universe data</p>"; return; }
  const W = fitW(host, 560), H = 240, M = { l: 16, r: 14, t: 14, b: 46 };
  const lo = Math.min(...uni), hi = Math.max(...uni);
  const NB = 24, bw = (hi - lo) / NB || 1;
  const bins = new Array(NB).fill(0);
  uni.forEach(v => bins[Math.min(NB - 1, Math.floor((v - lo) / bw))]++);
  const bmax = Math.max(...bins);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}` }, host);
  const X = v => M.l + (W - M.l - M.r) * (v - lo) / ((hi - lo) || 1);
  bins.forEach((n, i) => {
    if (!n) return;
    el("rect", { x: X(lo + i * bw) + 1, y: H - M.b - (H - M.t - M.b) * n / bmax,
      width: (W - M.l - M.r) / NB - 2, height: (H - M.t - M.b) * n / bmax,
      rx: 2, fill: "var(--surface-2)", stroke: "var(--line)", "stroke-width": .6 }, svg);
  });
  niceTicks(lo, hi, 5).forEach(v => {
    const tt = el("text", { x: X(v), y: H - 28, "text-anchor": "middle" }, svg);
    tt.textContent = dr[3] ? dr[2](v) : Math.round(v * 10) / 10;
  });
  // market median, so "where does this sit" has a reference
  const sorted = [...uni].sort((a, b) => a - b);
  const med = sorted[Math.floor(sorted.length / 2)];
  el("line", { x1: X(med), x2: X(med), y1: M.t, y2: H - M.b, stroke: "var(--mid)",
    "stroke-width": 1.2, "stroke-dasharray": "4,3" }, svg);
  const mlab = el("text", { x: X(med) + 3, y: M.t + 10, class: "m" }, svg);
  mlab.textContent = "market median " + dr[2](med);
  const seen2 = {};
  chosen.forEach(d => {
    const v = dr[1](d);
    if (v == null) return;
    const key = Math.round(X(v) / 9);
    const k = (seen2[key] = (seen2[key] || 0) + 1) - 1;      // dodge, like the strips
    const c = el("circle", { cx: X(v), cy: H - M.b - 8 - k * 11, r: 6, fill: paintColor(d),
      "fill-opacity": .85, stroke: "var(--surface-1)", "stroke-width": 1.2 }, svg);
    hover(c, () => `<b>${d.name} (${d.code})</b>${dr[0]}: ${dr[2](v)}`);
  });
  const tmv = dr[1]((target().meta) || {});
  if (tmv != null && Number.isFinite(X(tmv))) {
    const dmd = el("polygon", { points:
      `${X(tmv)},${H - M.b - 30} ${X(tmv) + 7},${H - M.b - 22} ${X(tmv)},${H - M.b - 14} ${X(tmv) - 7},${H - M.b - 22}`,
      fill: GOLD, stroke: "var(--surface-1)", "stroke-width": 1.2 }, svg);
    hover(dmd, () => `<b>${target().name} (target)</b>${dr[0]}: ${dr[2](tmv)}`);
  }
  const xl = el("text", { x: (M.l + W - M.r) / 2, y: H - 6, "text-anchor": "middle", class: "axlabel" }, svg);
  xl.textContent = `${dr[0]}${dr[3] ? " (log)" : ""} — all ${uni.length} deals (bars) vs your comps (dots)`;
}

// 6. the reference notebook's A/H charts, from the embedded daily paths -------
const AHP = DATA.ahpaths || {};
function pathline(svg, xs, ys, X, Y, color, w) {
  let dstr = "", started = false;
  xs.forEach((x, i) => {
    const v = ys[i];
    if (!Number.isFinite(v)) { return; }
    const px = X(x), py = Y(v);
    if (!Number.isFinite(px) || !Number.isFinite(py)) { return; }
    dstr += (started ? "L" : "M") + px.toFixed(1) + "," + py.toFixed(1);
    started = true;
  });
  return el("path", { d: dstr, fill: "none", stroke: color, "stroke-width": w || 1.6 }, svg);
}
function addXhair(svg, W, H, M, Xs, sers, unit) {
  // sers: [{name, days, ys, color}] — hover shows the vertical scan line and
  // every series' value at the nearest session ("it can't show all" fixed)
  const vline = el("line", { y1: M.t, y2: H - M.b, stroke: "var(--text-muted)",
    "stroke-width": .9, "stroke-dasharray": "3,3", visibility: "hidden" }, svg);
  const allDays = [...new Set(sers.flatMap(s2 => s2.days))].sort((a, b) => a - b);
  svg.addEventListener("mousemove", ev => {
    const r = svg.getBoundingClientRect();
    const vx = (ev.clientX - r.left) * (W / r.width);
    if (vx < M.l || vx > W - M.r) { vline.setAttribute("visibility", "hidden"); hideTT(); return; }
    let best = allDays[0], bd = 1e9;
    allDays.forEach(dd => { const d2 = Math.abs(Xs(dd) - vx); if (d2 < bd) { bd = d2; best = dd; } });
    vline.setAttribute("x1", Xs(best)); vline.setAttribute("x2", Xs(best));
    vline.setAttribute("visibility", "visible");
    const rows = sers.map(s2 => {
      const i = s2.days.lastIndexOf(best);
      const v = i >= 0 ? s2.ys[i] : null;
      if (v == null || !Number.isFinite(v)) return "";
      const val = unit === "%" ? (v > 0 ? "+" : "") + v.toFixed(1) + "%"
        : unit === "idx" ? v.toFixed(1) : v.toFixed(2);
      return `<div><span class="sw" style="background:${s2.color}"></span>${s2.name}: <b>${val}</b></div>`;
    }).join("");
    showTT(`<b>day ${best}</b>${rows}`, ev);
  });
  svg.addEventListener("mouseleave", () => { vline.setAttribute("visibility", "hidden"); hideTT(); });
}

// prepend the day-1 OPEN as the =100 anchor: the line begins at the first
// price a subscriber missing the allotment could actually TRADE; the tiny
// vertical step at day 0 is the intraday open->close move
// the premium series a trader actually lived: it BEGINS at the level struck
// at pricing (A's last close before listing vs the H OFFER), then follows the
// daily close-vs-close premium. The vertical step at day 0 is the pop's effect
// on the spread.
// A-leg day-0 open in HKD: the batch stores a_open0 in CNY; day-0 FX is
// recovered from the series itself (a_hkd[0]/a_cny[0])
function aOpen0HKD(P) {
  if (!P.a_open0 || P.a_hkd[0] == null || !P.a_cny[0]) return null;
  return P.a_open0 * (P.a_hkd[0] / P.a_cny[0]);
}
function hOpen0(P, code) {
  return P.h_open0 || (DATA.hpaths[code] || {}).open0
      || P.h.find(v => Number.isFinite(v));
}

const LEAD = -8;             // where the "struck at pricing" point is drawn
function premFromIPO(days, prem, ipoPct) {
  if (!prem || !prem.length) return null;
  if (ipoPct == null) return { days: days, ys: prem, lead: null };
  // The at-pricing premium is observed BEFORE day 0 (A's last close vs the
  // offer), so it belongs left of the axis origin. Drawn as its own dashed
  // lead-in: stacking it at x=0 turned every line's drop into one vertical bar
  // and squashed the whole panel.
  return { days: days, ys: prem, lead: { x: LEAD, y: ipoPct } };
}
// x-scale that includes the pre-listing lead-in
function xLead(W, M) { return v => M.l + (W - M.l - M.r) * (v - LEAD) / (92 - LEAD); }
function drawLead(svg, Xs, Y, lead, y0, col) {
  if (!lead || !Number.isFinite(Y(lead.y)) || !Number.isFinite(Y(y0))) return;
  el("line", { x1: Xs(lead.x), y1: Y(lead.y), x2: Xs(0), y2: Y(y0),
    stroke: col, "stroke-width": 1.4, "stroke-dasharray": "3,2.5", opacity: .85 }, svg);
  el("circle", { cx: Xs(lead.x), cy: Y(lead.y), r: 2.8, fill: col }, svg);
}

function openStart(days, closes, open0) {
  const base = open0 != null ? open0 : closes.find(v => Number.isFinite(v));
  if (!base) return null;
  return { days: [days[0]].concat(days),
           ys: [100].concat(closes.map(v => v == null ? null : 100 * v / base)),
           base, fromOpen: open0 != null };
}

function daymarks(svg, X, M, H) {
  [[7, "1w"], [14, "2w"], [30, "1M"], [61, "2M"], [92, "3M"]].forEach(([d, lab]) => {
    el("line", { x1: X(d), x2: X(d), y1: M.t, y2: H - M.b, stroke: "var(--line)",
      "stroke-dasharray": "2,3", "stroke-width": .8 }, svg);
    const t = el("text", { x: X(d) + 2, y: M.t + 9, class: "m" }, svg);
    t.textContent = lab;
  });
}
function ahPanel(host, title, draw, kind, subtitle) {
  const card = document.createElement("div");
  card.className = "ahpane" + (kind === "pop" ? " withpop" : kind === "expop" ? " expop" : "");
  card.innerHTML = `<h4>${title}${kind === "pop" ? ' <span class="ktag kpop">incl. pop</span>'
    : kind === "expop" ? ' <span class="ktag kex">ex-pop</span>' : ""}</h4>` +
    (subtitle ? `<p class="psub">${subtitle}</p>` : "");
  host.appendChild(card);
  const W = fitW(card, 340, 640), H = 230, M = { l: 44, r: 44, t: 14, b: 26 };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}` }, card);
  draw(svg, W, H, M);
  return svg;
}
function scaleFor(vals, H, M, pad) {
  const ok = vals.filter(v => Number.isFinite(v));
  if (!ok.length) return () => NaN;
  const lo = Math.min(...ok), hi = Math.max(...ok);
  const p = (hi - lo) * (pad || .06) || 1;
  return v => H - M.b - (H - M.t - M.b) * (v - lo + p) / (hi - lo + 2 * p);
}
function renderAH(chosen) {
  const host = $("#lab-ah");
  host.innerHTML = "";
  const pairs = chosen.filter(d => AHP[d.code]);
  $("#lab-ah-note").textContent = pairs.length
    ? `${pairs.length} of the chosen comps have an A line — first ~3 months of daily prices, precomputed (Tencent + CNYHKD). The Jupyter notebook draws the same four panels live off Bloomberg for any window.`
    : "None of the chosen comps has an A-share line — pick A/H deals (or tick 'A-share only') to see the paired-price panels.";
  pairs.forEach(d => {
    const P = AHP[d.code];
    const wrap = document.createElement("div");
    wrap.className = "ahstock";
    wrap.innerHTML = `<h3>${P.name} (${d.code}.HK vs ${P.a_code}) — listed ${P.ipo}, offer HK$${P.offer}` +
      (d.first_day_return_pct != null ? ` · day-1 pop <b class="${d.first_day_return_pct >= 0 ? "up" : "down"}">${fmt.pct(d.first_day_return_pct)}</b>` : "") +
      (d.a_premium_ipo_pct != null ? ` · A prem vs offer at IPO <b>${fmt.pct(d.a_premium_ipo_pct)}</b>` : "") +
      (P.a_pre_runup_pct != null ? ` · <span class="m">A ran ${fmt.pct(P.a_pre_runup_pct)} in the month before</span>` : "") +
      `</h3><div class="ahwrap"><div class="ahgrid"></div></div>`;
    host.appendChild(wrap);
    const g = wrap.querySelector(".ahgrid");
    const X = (W, M) => v => M.l + (W - M.l - M.r) * v / 92;
    // pane 0: the A line, month BEFORE -> month AFTER the H listing. The
    // vertical rule at day 0 IS the IPO date; left of it = the run-in flow,
    // right of it = how the A line digested the H listing.
    if (P.a_pre && P.a_pre.length > 1) {
      const postD = P.days.filter((dd, i) => dd <= 31 && P.a_cny[i] != null);
      const postV = P.days.map((dd, i) => dd <= 31 ? P.a_cny[i] : null)
                          .filter((v, i) => P.days[i] <= 31);
      const postOK = postV.filter(v => v != null);
      const postPct = postOK.length > 1 && postOK[0]
        ? Math.round(1000 * (postOK[postOK.length - 1] / postOK[0] - 1)) / 10 : null;
      ahPanel(g, `A-share, month before → month after`
        + ` (${fmt.pct(P.a_pre_runup_pct)} → ${postPct == null ? "—" : fmt.pct(postPct)})`,
        (svg, W, H, M) => {
        const Xp = v => M.l + (W - M.l - M.r) * (v + 31) / 63;
        const allv = P.a_pre.concat(postOK);
        const Y = scaleFor(allv, H, M);
        [[-21, "-3w"], [-7, "-1w"], [7, "+1w"], [21, "+3w"]].forEach(([dd, lab]) => {
          el("line", { x1: Xp(dd), x2: Xp(dd), y1: M.t, y2: H - M.b, stroke: "var(--line)",
            "stroke-dasharray": "2,3", "stroke-width": .8 }, svg);
          const t2 = el("text", { x: Xp(dd) + 2, y: M.t + 9, class: "m" }, svg);
          t2.textContent = lab;
        });
        pathline(svg, P.pre_days, P.a_pre, Xp, Y, RED, 1.8);
        pathline(svg, postD, postV, Xp, Y, RED, 1.8);
        // the IPO date, unmissable: a solid rule with its own label
        el("line", { x1: Xp(0), x2: Xp(0), y1: M.t, y2: H - M.b,
          stroke: "var(--text-primary)", "stroke-width": 1.3 }, svg);
        const t = el("text", { x: Xp(0), y: H - M.b + 12, "text-anchor": "middle",
          class: "m halo" }, svg);
        t.textContent = "H LISTS";
        addXhair(svg, W, H, M, Xp, [
          { name: "A (¥), pre-IPO", days: P.pre_days, ys: P.a_pre, color: RED },
          { name: "A (¥), post-IPO", days: postD, ys: postV, color: RED }], "px");
      }, null, "Did the A line run INTO the H pricing, and did it hold after? "
        + "Left of the rule = the month before; right = the month after.");
    } else {
      ahPanel(g, "A-share, month before (no data)", () => {});
    }
    // pane 1: native levels, twin axes (A CNY left red, H HKD right blue)
    ahPanel(g, "Price levels, native currency", (svg, W, H, M) => {
      const Xs = X(W, M);
      daymarks(svg, Xs, M, H);
      const Ya = scaleFor(P.a_cny, H, M), Yh = scaleFor(P.h, H, M);
      pathline(svg, P.days, P.a_cny, Xs, Ya, RED);
      pathline(svg, P.days, P.h, Xs, Yh, BLUE);
      addXhair(svg, W, H, M, Xs, [
        { name: "H (HK$)", days: P.days, ys: P.h, color: BLUE },
        { name: "A (¥)", days: P.days, ys: P.a_cny, color: RED }], "px");
      // One label per end, currency INSIDE the value ("¥80"), clamped into the
      // plot: a separate "A ¥" caption sat on top of the max tick and both
      // became unreadable.
      const aok = P.a_cny.filter(v => Number.isFinite(v)), hok = P.h;
      const put2 = (v, Y, side, col, pre) => {
        if (!Number.isFinite(v) || !Number.isFinite(Y(v))) return;
        // clear the 1w/2w/1M/3M day marks, which live at M.t+9
        const y = Math.min(Math.max(Y(v) + 3, M.t + 22), H - M.b - 2);
        const t = el("text", { x: side < 0 ? M.l - 5 : W - M.r + 5, y,
          "text-anchor": side < 0 ? "end" : "start", fill: col, class: "m halo" }, svg);
        t.textContent = (v >= 100 ? v.toFixed(0) : v.toFixed(1));
      };
      if (aok.length) { put2(Math.max(...aok), Ya, -1, RED, ""); put2(Math.min(...aok), Ya, -1, RED, ""); }
      if (hok.length) { put2(Math.max(...hok), Yh, 1, BLUE, ""); put2(Math.min(...hok), Yh, 1, BLUE, ""); }
    }, null, `<span style="color:${RED}">left axis ¥ (A)</span> · ` +
       `<span style="color:${BLUE}">right axis HK$ (H)</span> — two scales, `
       + `so the LINES' shapes compare, not their levels.`);
    // pane 2: both legs in HKD, gap shaded by premium sign
    ahPanel(g, "Common currency — shaded gap = premium", (svg, W, H, M) => {
      const Xs = X(W, M);
      daymarks(svg, Xs, M, H);
      const all = P.h.concat(P.a_hkd.filter(v => v != null));
      const Y = scaleFor(all, H, M);
      for (let i = 1; i < P.days.length; i++) {
        if (P.a_hkd[i] == null || P.a_hkd[i - 1] == null) continue;
        if (![P.a_hkd[i], P.a_hkd[i-1], P.h[i], P.h[i-1]].every(Number.isFinite)) continue;
        const up = P.a_hkd[i] >= P.h[i];
        el("polygon", { points:
          `${Xs(P.days[i-1]).toFixed(1)},${Y(P.a_hkd[i-1]).toFixed(1)} ${Xs(P.days[i]).toFixed(1)},${Y(P.a_hkd[i]).toFixed(1)} ` +
          `${Xs(P.days[i]).toFixed(1)},${Y(P.h[i]).toFixed(1)} ${Xs(P.days[i-1]).toFixed(1)},${Y(P.h[i-1]).toFixed(1)}`,
          fill: up ? RED : BLUE, "fill-opacity": .13 }, svg);
      }
      pathline(svg, P.days, P.a_hkd, Xs, Y, RED);
      pathline(svg, P.days, P.h, Xs, Y, BLUE);
      addXhair(svg, W, H, M, Xs, [
        { name: "H (HK$)", days: P.days, ys: P.h, color: BLUE },
        { name: "A in HKD", days: P.days, ys: P.a_hkd, color: RED }], "px");
    });
    // pane 3: rebased WITH the pop — 100 = the OFFER (pre-listing), so the
    // H line's very first dot already sits its day-1 return above/below 100
    ahPanel(g, "Rebased on the OFFER (=100)", (svg, W, H, M) => {
      const Xs = X(W, M);
      daymarks(svg, Xs, M, H);
      const a0 = aOpen0HKD(P) || P.a_hkd.find(v => v != null);
      const hreb = P.h.map(v => 100 * v / P.offer);
      const areb = P.a_hkd.map(v => v == null ? null : 100 * v / a0);
      const Y = scaleFor(hreb.concat(areb.filter(v => v != null)).concat([100]), H, M);
      el("line", { x1: M.l, x2: W - M.r, y1: Y(100), y2: Y(100), stroke: "var(--mid)", "stroke-width": .8 }, svg);
      // the pop, made visible: a dotted riser from the offer line to day-1's dot
      if (Number.isFinite(hreb[0])) {
        el("line", { x1: Xs(P.days[0]), x2: Xs(P.days[0]), y1: Y(100), y2: Y(hreb[0]),
          stroke: BLUE, "stroke-width": 1, "stroke-dasharray": "2,2" }, svg);
        el("circle", { cx: Xs(P.days[0]), cy: Y(hreb[0]), r: 2.6, fill: BLUE }, svg);
      }
      pathline(svg, P.days, areb, Xs, Y, RED);
      pathline(svg, P.days, hreb, Xs, Y, BLUE, 1.9);
      const t = el("text", { x: M.l - 4, y: Y(100) + 3, "text-anchor": "end", class: "m halo" }, svg);
      t.textContent = "100";
      addXhair(svg, W, H, M, Xs, [
        { name: "H (offer =100)", days: P.days, ys: hreb, color: BLUE },
        { name: "A (day-0 close =100)", days: P.days, ys: areb, color: RED }], "idx");
    }, "pop", `100 = the H OFFER. The dotted riser into the first dot IS the day-1 pop `
      + `(${fmt.pct(d.first_day_return_pct)}). A (red) on its own day-0 OPEN.`);
    // pane 3b: EX-POP — 100 = the day-1 OPEN, the first print you could
    // actually TRADE; the tiny day-0 step is the intraday open→close move
    ahPanel(g, "Rebased ex-pop — 100 = the day-1 open (tradeable)", (svg, W, H, M) => {
      const Xs = X(W, M);
      daymarks(svg, Xs, M, H);
      const hOS = openStart(P.days, P.h, hOpen0(P, d.code));
      const aO = aOpen0HKD(P);
      const a0 = aO || P.a_hkd.find(v => v != null);
      if (!hOS || !a0) return;
      const aOS = openStart(P.days, P.a_hkd, a0);
      const areb = aOS ? aOS.ys : P.a_hkd.map(v => v == null ? null : 100 * v / a0);
      const aDays = aOS ? aOS.days : P.days;
      const Y = scaleFor(hOS.ys.concat(areb.filter(v => v != null)).concat([100]), H, M);
      el("line", { x1: M.l, x2: W - M.r, y1: Y(100), y2: Y(100), stroke: "var(--mid)", "stroke-width": .8 }, svg);
      pathline(svg, aDays, areb, Xs, Y, RED);
      pathline(svg, hOS.days, hOS.ys, Xs, Y, BLUE, 1.9);
      const t = el("text", { x: M.l - 4, y: Y(100) + 3, "text-anchor": "end", class: "m halo" }, svg);
      t.textContent = "100";
      addXhair(svg, W, H, M, Xs, [
        { name: "H (buy at open =100)", days: hOS.days, ys: hOS.ys, color: BLUE },
        { name: aO ? "A (its open =100)" : "A (day-0 close =100)",
          days: aDays, ys: areb, color: RED }], "idx");
      if (!hOS.fromOpen) {
        const n2 = el("text", { x: W - M.r, y: H - 6, "text-anchor": "end", class: "m halo" }, svg);
        n2.textContent = "no true open on file — day-1 close used";
      }
    }, "expop", "OPEN-TO-OPEN: both legs = 100 at their own day-0 opening print — "
      + "the two first prices you could actually trade. Day-0 steps = each side's intraday move.");
    // pane 4: premium with sign fills + the struck level vs the OFFER
    const ipoLvl = d.a_premium_ipo_pct;
    ahPanel(g, "A premium over H (+ = A above H)", (svg, W, H, M) => {
      const Xs = xLead(W, M);
      daymarks(svg, Xs, M, H);
      const ok = P.prem.filter(v => v != null);
      const Y = scaleFor(ok.concat([0]).concat(ipoLvl != null ? [ipoLvl] : []), H, M);
      if (ipoLvl != null && Number.isFinite(Y(ipoLvl))) {
        // the tag sits BY its dot, not down on the axis
        const tl = el("text", { x: Xs(LEAD), y: Y(ipoLvl) + 16, "text-anchor": "middle",
          class: "m halo" }, svg);
        tl.textContent = "@offer";
      }
      if (ipoLvl != null) {
        el("line", { x1: M.l, x2: W - M.r, y1: Y(ipoLvl), y2: Y(ipoLvl),
          stroke: GOLD, "stroke-width": 1.2, "stroke-dasharray": "5,3" }, svg);
        const tg = el("text", { x: W - M.r, y: Y(ipoLvl) - 4, "text-anchor": "end",
          class: "m halo", fill: GOLD }, svg);
        tg.textContent = "@IPO";
      }
      el("line", { x1: M.l, x2: W - M.r, y1: Y(0), y2: Y(0), stroke: "var(--mid)", "stroke-width": .8 }, svg);
      for (let i = 1; i < P.days.length; i++) {
        if (P.prem[i] == null || P.prem[i - 1] == null) continue;
        if (!Number.isFinite(P.prem[i]) || !Number.isFinite(P.prem[i-1])) continue;
        el("polygon", { points:
          `${Xs(P.days[i-1]).toFixed(1)},${Y(0).toFixed(1)} ${Xs(P.days[i-1]).toFixed(1)},${Y(P.prem[i-1]).toFixed(1)} ` +
          `${Xs(P.days[i]).toFixed(1)},${Y(P.prem[i]).toFixed(1)} ${Xs(P.days[i]).toFixed(1)},${Y(0).toFixed(1)}`,
          fill: P.prem[i] >= 0 ? RED : BLUE, "fill-opacity": .15 }, svg);
      }
      const pS = premFromIPO(P.days, P.prem, ipoLvl) || { days: P.days, ys: P.prem };
      drawLead(svg, Xs, Y, pS.lead, P.prem.find(v => v != null), "#6C5B7B");
      pathline(svg, pS.days, pS.ys, Xs, Y, "#6C5B7B", 1.7);
      const last = ok[ok.length - 1];
      if (Number.isFinite(last) && Number.isFinite(Y(last))) {
        // halo + side-aware placement so the tag never sits ON the line
        const above = Y(last) > (M.t + H - M.b) / 2;
        const t = el("text", { x: W - M.r - 2, y: Y(last) + (above ? -7 : 14),
          "text-anchor": "end", class: "m halo" }, svg);
        t.textContent = "now " + (last > 0 ? "+" : "") + last.toFixed(0) + "%";
      }
      addXhair(svg, W, H, M, Xs, [
        { name: "A premium", days: pS.days, ys: pS.ys, color: "#6C5B7B" }], "%");
    }, null, (ipoLvl != null
      ? `Gold dash = the premium STRUCK AT PRICING — A's last close ÷ the H offer − 1 `
        + `= ${fmt.pct(ipoLvl)}. Line above the dash: A has re-rated vs H since listing.`
      : "Daily A premium: (A × FX) ÷ H − 1."));
  });
  // overlay: all chosen pairs on one axis — H rebased | A rebased | premium
  if (pairs.length >= 2) {
    const wrap = document.createElement("div");
    wrap.className = "ahstock";
    wrap.innerHTML = `<h3>All chosen A/H comps on one axis</h3>` +
      `<div class="ovleg">` + pairs.map((d, i) =>
        `<span><i class="sw" style="background:${palette0[i % palette0.length]}"></i>` +
        `${AHP[d.code].name}</span>`).join("") + `</div>` +
      `<div class="pathgrid"></div>`;
    host.appendChild(wrap);
    const g = wrap.querySelector(".pathgrid");
    const palette = palette0;
    const mk = (title, series, base, kind, subt, lead) => ahPanel(g, title, (svg, W, H, M) => {
      const Xs = lead ? xLead(W, M) : (v => M.l + (W - M.l - M.r) * v / 92);
      daymarks(svg, Xs, M, H);
      const flat = series.flatMap(s => s.ys.filter(v => v != null)).concat([base])
        .concat(lead ? series.map(s => s.lead && s.lead.y).filter(v => v != null) : []);
      const Y = scaleFor(flat, H, M);
      el("line", { x1: M.l, x2: W - M.r, y1: Y(base), y2: Y(base), stroke: "var(--mid)", "stroke-width": .8 }, svg);
      series.forEach((s, i) => {
        const col = palette[i % palette.length];
        if (lead) drawLead(svg, Xs, Y, s.lead, s.y0, col);
        const pth = pathline(svg, s.days, s.ys, Xs, Y, col, 1.5);
        hover(pth, () => `<b>${s.name}</b>`);
      });
      if (lead) { const tl = el("text", { x: Xs(LEAD), y: H - M.b + 12,
        "text-anchor": "middle", class: "m halo" }, svg); tl.textContent = "@offer"; }
      addXhair(svg, W, H, M, Xs, series.map((s2, i) => ({
        name: s2.name, days: s2.days, ys: s2.ys,
        color: palette[i % palette.length] })), base === 0 ? "%" : "idx");
    }, kind, subt);
    mk("H shares, rebased on the OFFER (=100)", pairs.map((d, i) => ({
      name: AHP[d.code].name, days: AHP[d.code].days,
      ys: AHP[d.code].h.map(v => 100 * v / AHP[d.code].offer) })), 100, "pop",
      "100 = each deal's own offer — the gap into each line's first dot is its pop.");
    mk("H shares, rebased ex-pop (=100 at the day-1 open)", pairs.map(d => {
      const P = AHP[d.code];
      const os = openStart(P.days, P.h, (DATA.hpaths[d.code] || {}).open0);
      return os ? { name: P.name, days: os.days, ys: os.ys } : null;
    }).filter(Boolean), 100, "expop",
      "100 = each deal's day-1 OPEN — the first tradeable print; pops stripped.");
    mk("A shares (HKD), rebased on their day-0 OPEN (=100)", pairs.map(d => {
      const P = AHP[d.code];
      const a0 = aOpen0HKD(P) || P.a_hkd.find(v => v != null);
      const os = openStart(P.days, P.a_hkd, a0);
      return os ? { name: P.name, days: os.days, ys: os.ys } : null;
    }).filter(Boolean), 100, "expop",
      "OPEN-TO-OPEN with the H panels: each A line = 100 at its own day-0 opening print.");
    mk("A premium over H (%) — from the level struck at IPO", pairs.map(d => {
      const P = AHP[d.code];
      const ps = premFromIPO(P.days, P.prem, d.a_premium_ipo_pct);
      return ps ? { name: P.name, days: ps.days, ys: ps.ys, lead: ps.lead,
                    y0: P.prem.find(v => v != null) } : null;
    }).filter(Boolean), 0, null,
      "The dot at @offer is the premium STRUCK AT PRICING; the dashed lead-in runs "
      + "into day 0, then each line is the daily close-vs-close premium. 0 = parity.", true);
    mk("A premium over H (%) — day 0 at the OPENS", pairs.map(d => {
      const P = AHP[d.code];
      const o0 = hOpen0(P, d.code);
      const aO = aOpen0HKD(P);
      if (!P.prem || !P.prem.length) return null;
      const ys = P.prem.slice();
      // day 0 = (A open x FX) / H open — the spread between the two FIRST
      // tradeable prints, aligned open-to-open with the rebased panels
      if (o0 && aO) ys[0] = Math.round((aO / o0 - 1) * 1000) / 10;
      return { name: P.name, days: P.days, ys };
    }).filter(Boolean), 0, "expop",
      "OPEN-TO-OPEN: day 0 = (A open × FX) ÷ H open — the spread between the two "
      + "first tradeable prints; later days are close-vs-close.");
  }
}

const palette0 = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4",
                  "#4a3aa7", "#e34948", "#008300"];
// 6b. daily H paths for every chosen comp — offer-rebased and ex-pop
function renderHPaths(chosen) {
  const host = $("#lab-hpaths");
  if (!host) return;
  host.innerHTML = "";
  const HPX = DATA.hpaths || {};
  const withP = chosen.filter(d => HPX[d.code] && d.final_price);
  if (withP.length < 1) {
    host.innerHTML = "<p class='note'>no daily paths for the chosen comps</p>";
    return;
  }
  const palette = palette0;
  const mk = (title, mkSeries, kind, subt) => ahPanel(host, title, (svg, W, H, M) => {
    const Xs = v => M.l + (W - M.l - M.r) * Math.min(v, 92) / 92;
    daymarks(svg, Xs, M, H);
    const series = withP.map(d => mkSeries(d, HPX[d.code])).filter(Boolean);
    const flat = series.flatMap(s2 => s2.ys.filter(Number.isFinite)).concat([100]);
    const Y = scaleFor(flat, H, M);
    el("line", { x1: M.l, x2: W - M.r, y1: Y(100), y2: Y(100), stroke: "var(--mid)", "stroke-width": .8 }, svg);
    series.forEach((s2, i) => {
      const pth = pathline(svg, s2.days, s2.ys, Xs, Y, s2.color, 1.5);
      hover(pth, () => `<b>${s2.name}</b>last ${(s2.ys[s2.ys.length-1] - 100).toFixed(1)}% vs base`);
    });
    addXhair(svg, W, H, M, Xs, series, "idx");
    const t = el("text", { x: M.l - 4, y: Y(100) + 3, "text-anchor": "end", class: "m halo" }, svg);
    t.textContent = "100";
  }, kind, subt);
  const colOf = (d, i) => paintOf(d) ? paintColor(d) : palette[i % palette.length];
  mk("Rebased on the OFFER (=100)", (d, P) => {
    const i = withP.indexOf(d);
    return { name: d.name, days: P.c.map(x => x[0]),
             ys: P.c.map(x => 100 * x[1] / d.final_price), color: colOf(d, i) };
  }, "pop", "100 = each comp's own offer; the gap into each line's first dot is its pop.");
  mk("Rebased ex-pop (=100 at the day-1 open)", (d, P) => {
    const i = withP.indexOf(d);
    const os = openStart(P.c.map(x => x[0]), P.c.map(x => x[1]), P.open0);
    return os ? { name: d.name, days: os.days, ys: os.ys, color: colOf(d, i) } : null;
  }, "expop", "100 = each comp's day-1 OPEN — the first tradeable print; pops stripped.");
}

// 7. return paths — drawn whatever the paint looks like
function renderPaths(chosen) {
  const H = [["offer", () => 0], ["day1", d => d.first_day_return_pct], ["1w", d => d.ret_1w_pct],
             ["1m", d => d.ret_1m_pct], ["3m", d => d.ret_3m_pct]];
  // second leg: the same horizons for someone who MISSED the allotment and
  // bought at the day-1 open. r_vs_open = (1+r_vs_offer)/(1+pop) - 1.
  const vsOpen = d => {
    const pop = d.day1_open_pop_pct;
    if (pop == null || pop <= -100) return null;
    const k = 1 + pop / 100;
    const conv = v => v == null ? null : ((1 + v / 100) / k - 1) * 100;
    return [0, d.day1_open_close_pct != null ? d.day1_open_close_pct : conv(d.first_day_return_pct),
            conv(d.ret_1w_pct), conv(d.ret_1m_pct), conv(d.ret_3m_pct)];
  };
  $("#lab-paths").innerHTML = chosen.map(d => {
    const ys = H.map(([, f]) => f(d)).map(v => v == null ? null : v);
    const yo = vsOpen(d);
    const known = ys.filter(v => v != null);
    if (known.length < 2) return "";
    const all = known.concat((yo || []).filter(v => v != null));
    const lo = Math.min(0, ...all), hi = Math.max(0, ...all), rng = hi - lo || 1;
    const px = i => 8 + i * 33, py = v => 44 - 38 * ((v - lo) / rng);
    const draw = arr => { let path = "", started = false;
      arr.forEach((v, i) => { if (v == null) return;
        path += (started ? "L" : "M") + px(i) + "," + py(v).toFixed(1); started = true; });
      return path; };
    const last = known[known.length - 1];
    const lastO = yo ? [...yo].reverse().find(v => v != null) : null;
    const col = paintOf(d) ? paintColor(d) : (last >= 0 ? "var(--s3)" : "var(--s2)");
    return `<div class="spark"><svg viewBox="0 0 150 56">
      <line x1="8" x2="142" y1="${py(0)}" y2="${py(0)}" stroke="var(--mid)" stroke-width="0.7"/>
      ${yo ? `<path d="${draw(yo)}" fill="none" stroke="var(--text-muted)" stroke-width="1.4"
        stroke-dasharray="3,2.5"/>` : ""}
      <path d="${draw(ys)}" fill="none" stroke="${col}" stroke-width="1.8"/>
      ${ys.map((v, i) => v == null ? "" : `<circle cx="${px(i)}" cy="${py(v).toFixed(1)}" r="2.2" fill="${col}"/>`).join("")}
    </svg><div class="l">${d.name.slice(0, 16)} <span class="m">${fmt.pct(last)}</span>` +
      (lastO != null ? ` <span class="m">· open ${fmt.pct(lastO)}</span>` : "") +
      `</div></div>`;
  }).join("") + `<p class="note sparkcap"><b>Solid</b> = bought the OFFER · ` +
    `<b>dashed grey</b> = bought the day-1 OPEN (missed the allotment). ` +
    `Steps: offer/open → day-1 → 1w → 1m → 3m; grey rule = your entry.</p>`;
}

function fillSel(sel, list, def) {
  sel.innerHTML = list.map((d, i) => `<option value="${i}" ${i === def ? "selected" : ""}>${d[0]}</option>`).join("");
}
fillSel($("#lab-x"), DRIVERS, 2); fillSel($("#lab-y"), RET_OPTS, 0); fillSel($("#lab-hfac"), DRIVERS, 2);
$("#lab-presets").innerHTML = XY_PRESETS.map(([lab], i) =>
  `<button class="theme preset" data-i="${i}">${lab}</button>`).join(" ");
document.querySelectorAll("#lab-presets .preset").forEach(b =>
  b.addEventListener("click", () => { const [_, xi, yi] = XY_PRESETS[+b.dataset.i];
    $("#lab-x").value = xi; $("#lab-y").value = yi; renderXY(labChosen()); }));
["#lab-x", "#lab-y"].forEach(id => $(id).addEventListener("change", () => renderXY(labChosen())));
$("#lab-hfac").addEventListener("change", () => renderHist(labChosen()));
$("#lab-outcome").innerHTML = OUTCOMES.map((o, i) => `<option value="${i}" ${i===2?"selected":""}>${o[0]}</option>`).join("");
$("#lab-outcome").addEventListener("change", () => { autoPaint(); renderLab(); });
$("#lab-ashare").addEventListener("change", labReset);
$("#lab-industry").addEventListener("change", labReset);
$("#lab-reset").addEventListener("click", labReset);
labReset();

// cornerstone vs debut, and retail vs institutional demand
function redrawInsights() {
  const cs = deals.filter(d => inRange(d) && d.cornerstone_pct > 0 && d.first_day_return_pct != null)
    .map(d => ({ x: d.cornerstone_pct, y: Math.max(-60, Math.min(200, d.first_day_return_pct)),
      up: d.first_day_return_pct > 0,
      tip: `<b>${d.name} (${d.code})</b>cornerstone ${d.cornerstone_pct}% of the deal<br>day-1 ${fmt.pct(d.first_day_return_pct)}` }));
  $("#chart-corner").innerHTML = "";
  if (cs.length) scatterXY($("#chart-corner"), cs,
    { xLabel: "cornerstone % of the offer", xUnit: "%", yUnit: "%", ylo: -60, yhi: 200 });

  const both = deals.filter(d => inRange(d) && d.oversub_public_mult > 0 && d.oversub_intl_mult > 0)
    .map(d => ({ x: d.oversub_public_mult, y: d.oversub_intl_mult,
      up: (d.first_day_return_pct || 0) > 0,
      tip: `<b>${d.name} (${d.code})</b>retail ${fmt.x(d.oversub_public_mult)} · institutional ${fmt.x(d.oversub_intl_mult)}<br>day-1 ${fmt.pct(d.first_day_return_pct)}` }));
  $("#chart-demand").innerHTML = "";
  if (both.length) scatterXY($("#chart-demand"), both,
    { logX: true, xLabel: "retail subscription (x, log)", xUnit: "x", yUnit: "x",
      ylo: 0, yhi: Math.min(60, Math.max(...both.map(p => p.y)) * 1.05) });
  $("#insight-note").textContent =
    `green = closed above offer, orange = below. ${cs.length} deals with a cornerstone tranche, ${both.length} with both subscription legs.`;
}

// ---------------------------------------------------------------- explorer --
// Any measure against any other. The fixed charts answer the questions we knew
// to ask; this one answers the rest without a rebuild.
const AXES = [
  ["oversub_public_mult", "public subscription", "x", true],
  ["oversub_intl_mult",   "institutional subscription", "x", true],
  ["deal_size_hkdm",      "deal size", "m", true],
  ["mktcap_ipo_hkdm",     "market cap at IPO", "m", true],
  ["a_mktcap_now_hkdm",   "A-line company market cap now (A+H names)", "m", true],
  ["eff_free_float_pct",  "effective free float % of cap", "%", false],
  ["eff_free_float_hkdm", "effective free float (HK$m)", "HK$m", true],
  ["cornerstone_pct",     "cornerstone % of offer", "%", false],
  ["pe_ipo",              "P/E at IPO", "x", true],
  ["ps_ipo",              "P/S at IPO", "x", true],
  ["pct_of_cap",          "priced at % of cap", "%", false],
  ["a_premium_ipo_pct", "A premium vs H at IPO", "%", false],
  ["first_day_return_pct", "day-1 return", "%", false],
  ["ret_1w_pct",          "1-week return", "%", false],
  ["ret_1m_pct",          "1-month return", "%", false],
  ["ret_3m_pct",          "3-month return", "%", false],
  ["aftermkt_1m_pct",     "1-month excluding the day-1 pop", "%", false],
  ["aftermkt_1w_pct",     "1-week excluding the day-1 pop", "%", false],
  ["aftermkt_3m_pct",     "3-month excluding the day-1 pop", "%", false],
  ["day1_open_pop_pct",   "day-1 open pop (offer\u2192open)", "%", false],
  ["day1_open_close_pct", "day-1 open\u2192close (intraday)", "%", false],
  ["alpha_1m_pct",        "1-month alpha vs sector index", "%", false],
  ["alpha_1m_expop_pct",  "1-month alpha ex-pop (matched window)", "%", false],
  ["alpha_3m_pct",        "3-month alpha vs sector index", "%", false],
  ["greenshoe_pct",       "greenshoe size %", "%", false],
  ["pe_now",              "P/E today (BBG desk)", "x", true],
  ["since_ipo_pct",       "return since IPO", "%", false],
];
const AXMAP = Object.fromEntries(AXES.map(a => [a[0], a]));

function fillAxis(sel, def) {
  AXES.forEach(([k, label]) => {
    const o = document.createElement("option");
    o.value = k; o.textContent = label;
    if (k === def) o.selected = true;
    sel.appendChild(o);
  });
}

function redrawExplorer() {
  const xk = $("#ex-x").value, yk = $("#ex-y").value, ck = $("#ex-c").value;
  const [, xlab, xunit, xlog] = AXMAP[xk], [, ylab, yunit] = AXMAP[yk];
  // every colour mode is a real mapping with its own legend — "sector" and
  // "year" used to be listed but silently fell back to up/down
  const YEARCOL = { 2021: "#bcd7f2", 2022: "#8fbce8", 2023: "#5f9edd",
                    2024: "#2a78d6", 2025: "#1c56a0", 2026: "#123a6e" };
  const SIZEB = d => d.deal_size_hkdm >= 20000 ? "Mega ≥20bn"
    : d.deal_size_hkdm >= 5000 ? "Large 5–20" : d.deal_size_hkdm >= 1000 ? "Mid 1–5"
    : d.deal_size_hkdm > 0 ? "Small <1" : null;
  const SIZECOL = { "Mega ≥20bn": "#123a6e", "Large 5–20": "#2a78d6",
                    "Mid 1–5": "#8fbce8", "Small <1": "#d3c9b8" };
  const secIdx = Object.fromEntries(secNames.map((n2, i) => [n2, `var(--s${i + 1})`]));
  // greenshoe: a deal HAS a shoe when the filing carries a stabilisation
  // facility (greenshoe_pct) or a final exercise outcome; "without" is a
  // stated zero/absent facility — the two trade differently (price support)
  const shoeOf = d => (d.greenshoe_pct > 0 || d.greenshoe_exercised_final)
    ? "with" : "without";
  const colOf = d =>
    ck === "sector" ? secIdx[d.sector] :
    ck === "year" ? YEARCOL[(d.ipo_date || "").slice(0, 4)] :
    ck === "ah" ? (d.a_share_code ? "var(--s7)" : "var(--mid)") :
    ck === "shoe" ? (shoeOf(d) === "with" ? "var(--s6)" : "var(--s8)") :
    ck === "size" ? (SIZECOL[SIZEB(d)] || "var(--mid)") : null;
  const legend =
    ck === "sector" ? secNames.map(n2 => [n2, secIdx[n2]]) :
    ck === "year" ? Object.entries(YEARCOL) :
    ck === "ah" ? [["A/H pair", "var(--s7)"], ["no A-line", "var(--mid)"]] :
    ck === "shoe" ? [["greenshoe in the deal", "var(--s6)"], ["no greenshoe", "var(--s8)"]] :
    ck === "size" ? Object.entries(SIZECOL).concat([["no size on file", "var(--mid)"]]) :
    [["closed above offer", "var(--s3)"], ["below", "var(--s2)"]];
  $("#ex-legend").innerHTML = legend.map(([l2, c2]) =>
    `<span><span class="sw" style="background:${c2}"></span>${l2}</span>`).join("");
  const pts = deals.filter(d => inRange(d) && d[xk] != null && d[yk] != null
                             && (!xlog || d[xk] > 0))
    .map(d => ({ x: d[xk], y: d[yk], up: (d.first_day_return_pct || 0) > 0,
      col: colOf(d),
      tip: `<b>${d.name} (${d.code})</b>${d.subsector || ""}<span class="m"> · ${d.ipo_date}</span>` +
           `<br>${xlab}: ${fmt.n(d[xk])}${xunit} · ${ylab}: ${fmt.n(d[yk])}${yunit}` }));
  $("#chart-explorer").innerHTML = "";
  if (!pts.length) {
    $("#chart-explorer").innerHTML = "<p class='note'>No deal has both of those on file for this period.</p>";
    $("#ex-note").textContent = "";
    return;
  }
  const ys = pts.map(p => p.y);
  scatterXY($("#chart-explorer"), pts, {
    logX: xlog, xLabel: xlab + (xlog ? " (log scale)" : ""), xUnit: xunit, yUnit: yunit,
    ylo: Math.min(0, ...ys), yhi: Math.max(...ys) * 1.05 });
  // the number worth reading off a scatter is the correlation, so state it
  const mx = pts.reduce((s, p) => s + (xlog ? Math.log10(p.x) : p.x), 0) / pts.length;
  const my = ys.reduce((s, v) => s + v, 0) / pts.length;
  let sxy = 0, sxx = 0, syy = 0;
  pts.forEach(p => { const a = (xlog ? Math.log10(p.x) : p.x) - mx, b = p.y - my;
                     sxy += a * b; sxx += a * a; syy += b * b; });
  const r = (sxx && syy) ? sxy / Math.sqrt(sxx * syy) : 0;
  $("#ex-note").textContent =
    `${pts.length} deals · correlation ${r >= 0 ? "+" : ""}${r.toFixed(2)}` +
    (Math.abs(r) < 0.2 ? " (essentially none)" : Math.abs(r) < 0.45 ? " (weak)" : " (clear)");
}

fillAxis($("#ex-x"), "oversub_public_mult");
fillAxis($("#ex-y"), "first_day_return_pct");
["#ex-x", "#ex-y", "#ex-c"].forEach(id => $(id).addEventListener("change", redrawExplorer));

mountYearFilter("#yearfilter", () => { redrawAnalog(); redrawInsights(); redrawExplorer(); });
redrawInsights();
redrawExplorer();

// full table — searchable, including by cornerstone investor ("who else did
// Hillhouse back?") and by sponsor
const tblRows = [...deals].sort((a, b) => (b.deal_size_hkdm || 0) - (a.deal_size_hkdm || 0));
const SUBSHORT = {
  "Smart hardware / consumer electronics": "Smart hw / cons. elec.",
  "Internet platform / e-commerce": "Internet / e-commerce",
  "Robotics & autonomous driving": "Robotics & autonomous",
  "SaaS / enterprise software": "SaaS / enterprise",
  "Beverages / packaged food": "Beverages / pkg. food",
  "Biotech pre-revenue (18A)": "Biotech 18A",
  "AI application / agent software": "AI application",
  "Brokers / asset management": "Brokers / asset mgmt",
  "Commercial & Professional Services": "Comm. & prof. services",
  "F&B chain / restaurants": "F&B / restaurants",
  "Capital goods / machinery": "Capital goods",
  "Construction / engineering": "Construction / eng.",
};
function subShort(v) { return SUBSHORT[v] || v || "—"; }
function csList(d) {
  const v = d.cornerstone_investors;
  return Array.isArray(v) ? v.join("; ") : (v || "");
}
function csShort(d) {
  const v = d.cornerstone_investors;
  if (!Array.isArray(v) || !v.length) return "—";
  // ONE name + the "+N all" chip: two names always ellipsized anyway, which
  // read as cut-off words — one full name reads clean
  // legal suffixes carry no information in a 150px cell — full name on hover
  return v[0].replace(/\s+(Limited|Ltd\.?|LLC|L\.L\.C\.?|Inc\.?|Pte\. Ltd\.?|Co\.?,? Ltd\.?)$/i, "");
}
let SORT_K = "deal_size_hkdm", SORT_DIR = -1;
function retCell(v) {
  if (v == null) return `<td class="num m">—</td>`;
  const cls = v > 0 ? "up" : v < 0 ? "down" : "";
  return `<td class="num ${cls}">${fmt.pct(v)}</td>`;
}
function drawTable() {
  const q = ($("#tbl-q").value || "").trim().toLowerCase();
  let rows = q ? tblRows.filter(d =>
    [d.name, d.code, d.name_cn, d.sector, d.subsector, csList(d), d.sponsors, d.sponsors_en]
      .some(v => (v || "").toString().toLowerCase().includes(q))) : tblRows.slice();
  rows.sort((a, b) => {
    const x = a[SORT_K], y = b[SORT_K];
    if (x == null && y == null) return 0;
    if (x == null) return 1;
    if (y == null) return -1;
    return (typeof x === "number" ? x - y : String(x).localeCompare(String(y))) * SORT_DIR;
  });
  $("#tbl-body").innerHTML = rows.map(d => `<tr><td class="mono">${d.code}</td>
  <td title="${(d.name + (d.name_cn ? " " + d.name_cn : "")).replace(/"/g, "'")}"><b>${d.name}</b>${d.name_cn ? ` <span class="m">${d.name_cn}</span>` : ""}</td>
  <td title="${d.subsector || ""}">${subShort(d.subsector)}</td>
  <td class="mono" title="${d.ipo_date}">${d.ipo_date.slice(2)}</td><td class="num">${fmt.m(d.deal_size_hkdm)}</td>
  <td class="num">${fmt.px(d.final_price)}</td>
  <td class="num">${d.oversub_public_mult == null ? "—" : fmt.x(d.oversub_public_mult)}</td>
  <td class="num">${d.cornerstone_pct == null ? "—" : d.cornerstone_pct.toFixed(0) + "%"}</td>
  ${retCell(d.first_day_return_pct)}${retCell(d.ret_1m_pct)}${retCell(d.ret_3m_pct)}${retCell(d.since_ipo_pct)}
  <td class="num">${d.pe_ipo == null ? (d.profitable_at_ipo === "N" ? "n/m" : "—") : fmt.x(d.pe_ipo)}</td>
  <td class="mono" title="${d.a_share_code || ""}">${(d.a_share_code || "—").split(".")[0]}</td>
  <td class="csx" title="${csList(d).replace(/"/g, "'")}" data-full="${csList(d).replace(/"/g, "&quot;")}">${csShort(d)}${
      (d.cornerstone_investors || []).length > 1
        ? `<span class="more" title="show the full list">+${(d.cornerstone_investors || []).length - 1} all ▾</span>` : ""}</td></tr>`).join("");
  drawTableBind();
  $("#tbl-count").textContent = (q ? `${rows.length} of ${tblRows.length} match "${q}" · `
                                   : `${tblRows.length} deals · `) +
    `sorted by ${SORT_K.replace(/_/g, " ")} ${SORT_DIR < 0 ? "↓" : "↑"} — click any header to re-sort`;
}
function drawTableBind() {
  document.querySelectorAll("#tbl-body td.csx .more").forEach(sp => {
    if (sp.dataset.bound) return;
    sp.dataset.bound = "1";
    sp.addEventListener("click", ev => {
      const td = ev.target.closest("td");
      const code = td.closest("tr").firstElementChild.textContent.trim();
      const d = tblRows.find(x => x.code === code);
      if (td.classList.toggle("open"))
        td.innerHTML = `${td.dataset.full.split("; ").join("<br>")}<span class="more">close ▴</span>`;
      else
        td.innerHTML = csShort(d) +
          `<span class="more" title="show the full list">+${(d.cornerstone_investors || []).length - 1} all ▾</span>`;
      drawTableBind();
    });
  });
}
document.querySelectorAll("#table th[data-k]").forEach(th =>
  th.addEventListener("click", () => {
    const k = th.dataset.k;
    SORT_DIR = (SORT_K === k) ? -SORT_DIR : (typeof (tblRows[0] || {})[k] === "number" ? -1 : 1);
    SORT_K = k;
    drawTable();
  }));
$("#tbl-q").addEventListener("input", drawTable);
drawTable();

// ------------------------------------------------- cornerstone league ------
// AAStocks-style: one row per investor (grouped on the screener's normalized
// key), averages across every deal they anchored. Data precomputed at build.
let CS_SORT = "n", CS_DIR = -1;
function csLeagueRows() {
  const q = ($("#cs-q").value || "").trim().toLowerCase();
  const min = +($("#cs-min").value || 1);
  let rows = DATA.cs_league.filter(r => r.n >= min &&
    (!q || r.investor.toLowerCase().includes(q) ||
     r.deals.some(d => (d.name || "").toLowerCase().includes(q) || d.code === q)));
  rows.sort((a, b) => {
    const va = a[CS_SORT], vb = b[CS_SORT];
    if (va == null && vb == null) return 0;
    if (va == null) return 1;                    // blanks sink regardless of dir
    if (vb == null) return -1;
    return (va < vb ? -1 : va > vb ? 1 : 0) * (typeof va === "string" ? -CS_DIR : CS_DIR);
  });
  return rows;
}
// never cut a name mid-word — "MORIMATSU INTL" not "MORIMATS"
function clipWord(s, n) {
  s = String(s || "");
  if (s.length <= n) return s;
  const cut = s.lastIndexOf(" ", n);
  return (cut > 3 ? s.slice(0, cut) : s.slice(0, n)) + "…";
}
function csCell(v, grp) {
  const g = grp || "";
  if (v == null) return `<td class="num m ${g}">—</td>`;
  const cls = v > 0 ? "up" : v < 0 ? "down" : "";
  return `<td class="num ${cls} ${g}">${fmt.pct(v)}</td>`;
}
function drawCsLeague() {
  const rows = csLeagueRows();
  $("#cs-body").innerHTML = rows.map(r => `<tr>
    <td title="${r.investor.replace(/"/g, "'")}"><b>${r.investor}</b></td>
    <td class="num">${r.n}</td>
    <td class="num">${r.hit == null ? "—" : r.hit.toFixed(0) + "%"}</td>
    ${csCell(r.avg_d1, "grpwith")}${csCell(r.avg_1w_pop, "grpwith")}${csCell(r.avg_1m_pop, "grpwith")}${csCell(r.avg_3m_pop, "grpwith")}
    ${csCell(r.avg_1w, "grpex")}${csCell(r.avg_1m, "grpex")}${csCell(r.avg_3m, "grpex")}
    <td class="lgdeals" title="${r.deals.map(d => `${d.name} (${d.code})`).join("; ").replace(/"/g, "'")}"><div class="lgwrap"><span class="lgnames">${
      r.deals.slice(0, 2).map(d => `${clipWord(d.name, 20)} <span class="m">${d.code}</span>`).join(" · ")
    }</span>${r.deals.length > 2
        ? `<span class="more csmore" data-full="${r.deals.map(d =>
            `${d.name} (${d.code}) day-1 ${d.d1 == null ? "—" : (d.d1 > 0 ? "+" : "") + d.d1.toFixed(1) + "%"}`)
            .join("; ").replace(/"/g, "&quot;")}" title="show all ${r.deals.length} deals">+${r.deals.length - 2} all ▾</span>`
        : ""}</div></td>
  </tr>`).join("");
  $("#cs-count").textContent = `${rows.length} investors shown · sorted by ${CS_SORT.replace(/_/g, " ")} — click a header to re-sort`;
}
document.querySelectorAll("#cs-tbl th[data-k]").forEach(th =>
  th.addEventListener("click", () => {
    const k = th.dataset.k;
    CS_DIR = (CS_SORT === k) ? -CS_DIR : -1;
    CS_SORT = k;
    drawCsLeague();
  }));
$("#cs-q").addEventListener("input", drawCsLeague);
$("#cs-min").addEventListener("input", drawCsLeague);
drawCsLeague();

// ------------------------------------------- stabilising-manager league -----
// The same table for the bank that held the shoe and the after-market bid.
// Shares csCell/clipWord and the precomputed clean_names.stab_league rows, so
// it cannot drift from the Excel SM League sheet.
let SM_SORT = "n", SM_DIR = -1;
function smLeagueRows() {
  const q = ($("#sm-q").value || "").trim().toLowerCase();
  const min = +($("#sm-min").value || 1);
  let rows = (DATA.stab_league || []).filter(r => r.n >= min &&
    (!q || r.manager.toLowerCase().includes(q) ||
     r.deals.some(d => (d.name || "").toLowerCase().includes(q) || d.code === q)));
  rows.sort((a, b) => {
    const va = a[SM_SORT], vb = b[SM_SORT];
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    return (va < vb ? -1 : va > vb ? 1 : 0) * (typeof va === "string" ? -SM_DIR : SM_DIR);
  });
  return rows;
}
function drawSmLeague() {
  const rows = smLeagueRows();
  $("#sm-body").innerHTML = rows.map(r => `<tr>
    <td title="${r.manager.replace(/"/g, "'")}"><b>${r.manager}</b></td>
    <td class="num">${r.n}</td>
    <td class="num">${r.hit == null ? "—" : r.hit.toFixed(0) + "%"}</td>
    ${csCell(r.avg_d1_open, "grpd1")}${csCell(r.avg_d1, "grpd1")}${csCell(r.avg_d1_open_close, "grpd1")}
    ${csCell(r.avg_1w_pop, "grpwith")}${csCell(r.avg_1m_pop, "grpwith")}${csCell(r.avg_3m_pop, "grpwith")}
    ${csCell(r.avg_1w, "grpex")}${csCell(r.avg_1m, "grpex")}${csCell(r.avg_3m, "grpex")}
    <td class="num m" title="${r.shoe_known || 0} of ${r.n} deals have a published shoe outcome">${
      r.shoe_full_pct == null ? "—" : r.shoe_full_pct.toFixed(0) + "%"}</td>
    <td class="num m" title="${r.shoe_known || 0} of ${r.n} deals have a published shoe outcome">${
      r.shoe_lapsed_pct == null ? "—" : r.shoe_lapsed_pct.toFixed(0) + "%"}</td>
    <td class="lgdeals" title="${r.deals.map(d => `${d.name} (${d.code})`).join("; ").replace(/"/g, "'")}"><div class="lgwrap"><span class="lgnames">${
      r.deals.slice(0, 2).map(d => `${clipWord(d.name, 20)} <span class="m">${d.code}</span>`).join(" · ")
    }</span>${r.deals.length > 2
        ? `<span class="more csmore" data-full="${r.deals.map(d =>
            `${d.name} (${d.code}) day-1 ${d.d1 == null ? "—" : (d.d1 > 0 ? "+" : "") + d.d1.toFixed(1) + "%"}${d.shoe ? " · shoe " + d.shoe : ""}`)
            .join("; ").replace(/"/g, "&quot;")}" title="show all ${r.deals.length} deals">+${r.deals.length - 2} all ▾</span>`
        : ""}</div></td>
  </tr>`).join("");
  $("#sm-count").textContent = `${rows.length} managers shown · sorted by ${SM_SORT.replace(/_/g, " ")} — click a header to re-sort`;
}
document.querySelectorAll("#sm-tbl th[data-k]").forEach(th =>
  th.addEventListener("click", () => {
    const k = th.dataset.k;
    SM_DIR = (SM_SORT === k) ? -SM_DIR : -1;
    SM_SORT = k;
    drawSmLeague();
  }));
$("#sm-q").addEventListener("input", drawSmLeague);
$("#sm-min").addEventListener("input", drawSmLeague);
drawSmLeague();

// pipeline-card description: unclamp in place
document.addEventListener("click", ev => {
  const m = ev.target.closest(".pmore");
  if (!m) return;
  const p = m.previousElementSibling;
  if (!p || !p.classList.contains("desc")) return;
  const open = !p.classList.toggle("clamp");
  m.textContent = open ? "less ▴" : "more ▾";
});

// see-all chips (screener matrix + league): delegated, survives re-renders
document.addEventListener("click", ev => {
  const chip = ev.target.closest(".csmore");
  if (!chip) return;
  const host = chip.closest("td, .csxp");
  if (!host) return;
  if (!host.dataset.short) host.dataset.short = host.innerHTML;
  if (host.classList.toggle("open")) {
    const items = chip.dataset.full.split("; ");
    // a 36-deal investor would otherwise push the whole table off-screen —
    // long lists scroll inside the cell instead
    const cls = items.length > 8 ? ' class="lgfull"' : "";
    host.innerHTML = `<div${cls}>${items.join("<br>")}</div>` +
      `<span class="more csmore" data-full="${chip.dataset.full.replace(/"/g, "&quot;")}">close ▴</span>`;
  } else {
    host.innerHTML = host.dataset.short;
  }
});

// ---------------------------------------------------------------- tabs ------
// One page, five tabs: senior eyes get ONE topic per screen instead of a
// two-metre scroll. Sections keep their ids so old #hash links still resolve.
const TABMAP = {
  screener: ["screener", "complab"],
  market: ["issuance", "size", "pricing", "analog", "insights", "explorer", "valuation"],
  ah: ["ah"],
  cs: ["csleague"],
  sm: ["smleague"],
  pipeline: ["pipeline"],
  table: ["table"],
};
function showTab(name) {
  Object.entries(TABMAP).forEach(([tab, secs]) =>
    secs.forEach(id => { const el = document.getElementById(id);
      if (el) el.style.display = (tab === name) ? "" : "none"; }));
  document.querySelectorAll("#tabs a").forEach(a =>
    a.classList.toggle("active", a.dataset.tab === name));
  try { history.replaceState(null, "", "#" + name); } catch (e) {}
  window.scrollTo(0, 0);
}
document.querySelectorAll("#tabs a").forEach(a =>
  a.addEventListener("click", () => showTab(a.dataset.tab)));
const wantTab = (location.hash || "").slice(1);
const containing = Object.entries(TABMAP).find(([t, secs]) =>
  t === wantTab || secs.includes(wantTab));
showTab(containing ? containing[0] : "screener");

// theme toggle
$("#theme").addEventListener("click", () => {
  const cur = document.documentElement.getAttribute("data-theme");
  const next = cur === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  redraw();
});
function redraw() {
  ["#chart-count", "#chart-amt", "#chart-hist", "#chart-scatter", "#chart-inrange", "#chart-ah", "#chart-bands", "#chart-analog", "#chart-alpha", "#chart-corner", "#chart-demand"]
    .forEach(id => { const n = $(id); if (n) n.innerHTML = ""; });
  stackedBar($("#chart-count"), years, secNames, cnt, { fmtVal: v => v + " deals", fmtTop: v => v, fmtAxis: v => v });
  stackedBar($("#chart-amt"), years, secNames, amt, { fmtVal: v => "HK$" + v.toFixed(1) + "bn", fmtTop: v => v.toFixed(0), fmtAxis: v => v });
  histogram($("#chart-hist"), sized.map(d => d.deal_size_hkdm), label, {});
  scatterLogX($("#chart-scatter"), pr, { ylo: -60, yhi: 200 });
  stackedBar($("#chart-inrange"), years, buckets.map(b => b[0]), bmat, { fmtVal: v => v + " deals", fmtAxis: v => v });
  redrawAHTab();
  if (bands.length) rangeBands($("#chart-bands"), bands.slice(0, 14), {});
  redrawAnalog();
  redrawInsights();
}
"""

HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HK IPO Dashboard — 2021–2026 + Pipeline</title>
<style>%%CSS%%</style>
</head>
<body class="viz-root">
<header class="top">
  <h1>HK IPO Dashboard</h1>
  <nav id="tabs">
    <a data-tab="screener" class="active">Screener</a><a data-tab="market">Market</a><a data-tab="ah">A / H</a><a data-tab="cs">Cornerstones</a><a data-tab="sm">Stabilisers</a><a data-tab="pipeline">Pipeline</a><a data-tab="table">All deals</a>
  </nav>
  <span class="asof">Main Board IPOs · data as of %%ASOF%% · offline snapshot (Bloomberg-live view: Excel workbook)</span>
  <button class="theme" id="theme">◐ theme</button>
</header>

<section id="issuance">
  <h2>Issuance overview</h2>
  <p class="sub">All Main Board IPOs with a public offering (allotment results filed). Money = gross proceeds, HK$.</p>
  <div class="tiles" id="tiles"></div>
  <div class="legend" id="legend-issuance"></div>
  <div class="row">
    <div class="chart"><h3>Deal count by year × sector</h3><div id="chart-count"></div></div>
    <div class="chart"><h3>Proceeds by year × sector (HK$bn)</h3><div id="chart-amt"></div></div>
  </div>
</section>

<section id="size">
  <h2>Size distribution</h2>
  <p class="sub">Log-scale histogram; labelled lines mark the mega-deal precedents. Buckets: Mega ≥ HK$20bn · Large 5–20 · Mid 1–5 · Small &lt; 1.</p>
  <div class="row"><div class="chart"><div id="chart-hist"></div></div></div>
</section>

<section id="pricing">
  <h2>Demand &amp; debut</h2>
  <p class="sub">Left: how hard the Hong Kong public tranche was subscribed, by year. Right: subscription level vs day-1 performance — the "hot book &rarr; pop?" view (day-1 clamped to −60/+200% for display; hover for the deal). <span id="pricing-stat"></span></p>
  <div class="legend" id="legend-inrange"></div>
  <div class="row">
    <div class="chart"><h3>Subscription level mix by year</h3><div id="chart-inrange"></div></div>
    <div class="chart"><h3>Subscription vs day-1 (each dot = a deal)</h3><div id="chart-scatter"></div></div>
  </div>
</section>

<section id="ah">
  <h2>A premium over H — dual-listed deals</h2>
  <p class="sub">A premium = (A×CNY→HKD) ÷ H − 1 · + = A trades ABOVE H. Static snapshot as of %%ASOF%%; the Excel AH tab carries the live Bloomberg view.</p>
  <div class="filters"><label>show <select id="ah-when">
      <option value="now">A premium — today</option>
      <option value="ipo">A premium — at IPO (vs H offer)</option></select></label>
    <label>sector <select id="ah-sec"></select></label>
    <label>subsector <select id="ah-sub"></select></label></div>
  <div class="row"><div class="chart"><div id="chart-ah"></div><p class="note" id="ah-note"></p></div></div>
  <div class="scroll" id="ah-tbl"></div>

  <h3>What drives the premium — the evidence in this book</h3>
  <div id="ah-drivers"></div>
</section>

<section id="analog">
  <div class="filters" id="yearfilter"></div>
  <h2>Demand &rarr; debut: what the book size actually predicted</h2>
  <p class="sub">Median day-1 return by how hard the Hong Kong public tranche was subscribed. The n under each bar is the sample size &mdash; read it before leaning on the bar.</p>
  <div class="row">
    <div class="chart"><h3>Median day-1 by subscription</h3><div id="chart-analog"></div></div>
    <div class="chart"><h3>Median 1-month ALPHA vs sector index</h3><div id="chart-alpha"></div></div>
  </div>
  <p class="sub">The right-hand chart strips the market out: it asks whether the pop was the deal
  or just the tape. Each deal is measured against its own sector index.</p>
</section>

<section id="insights">
  <h2>What actually drives the debut</h2>
  <p class="sub">Left: how much of the book was locked up by cornerstones. Right: retail versus
  institutional demand for the same deal. <span id="insight-note"></span></p>
  <div class="row">
    <div class="chart"><h3>Cornerstone % vs day-1</h3><div id="chart-corner"></div></div>
    <div class="chart"><h3>Retail vs institutional subscription</h3><div id="chart-demand"></div></div>
  </div>
</section>

<section id="explorer">
  <h2>Plot anything against anything</h2>
  <p class="sub">Pick the two measures yourself — the year filter above applies here too.
  Size and subscription axes switch to a log scale automatically because both span
  three orders of magnitude. <span id="ex-note"></span></p>
  <div class="filters">
    <label>X axis <select id="ex-x"></select></label>
    <label>Y axis <select id="ex-y"></select></label>
    <label>Colour <select id="ex-c">
      <option value="perf">up / down on debut</option>
      <option value="sector">sector</option>
      <option value="year">listing year</option>
      <option value="ah">A/H pair vs no A-line</option>
      <option value="shoe">greenshoe vs no greenshoe</option>
      <option value="size">size bucket</option>
    </select></label>
    <span class="legend" id="ex-legend"></span>
  </div>
  <div class="row"><div class="chart wide"><div id="chart-explorer"></div></div></div>
</section>

<section id="valuation">
  <h2>Subsector valuation bands at IPO</h2>
  <p class="sub">Band = min–max, dot = median. Blue = P/E; orange = P/S (used where the subsector is mostly loss-makers). Subsectors with ≥3 priced multiples.</p>
  <div class="row"><div class="chart"><div id="chart-bands"></div><p class="note" id="bands-note"></p></div></div>
</section>

<section id="pipeline">
  <h2>Active pipeline</h2>
  <p class="sub">Sizes are indicative and fluid; comps computed with the same subsector-first scorer.</p>
  <div class="cards" id="cards"></div>
</section>

<section id="screener">
  <h2>Screener</h2>
  <div class="filters" id="calendar"></div>
  <p class="sub">Pick a deal — or type your own. Comps rank subsector-first, same weights as the Excel screener.</p>
  <div class="filters"><label>Target deal:</label> <select id="picker"></select>
    <label>find <input id="finder" list="deal-list" size="18"
      placeholder="type a name or code — CATL, 3750, 快手"></label>
    <span class="note">…or override any field:</span></div>
  <datalist id="deal-list"></datalist>
  <div class="filters" id="override">
    <label>name <input id="ov-name" size="14" placeholder="(optional)"></label>
    <label>subsector <select id="ov-sub"><option value="">— from pick —</option></select></label>
    <label>size HK$m <input id="ov-size" size="7" inputmode="numeric"></label>
    <label>P/E <input id="ov-pe" size="5" inputmode="numeric"></label>
    <label>profitable <select id="ov-prof"><option value="">—</option><option>Y</option><option>N</option></select></label>
    <label>A-share <select id="ov-ah"><option value="">—</option><option>Y</option><option>N</option></select></label>
    <button id="ov-clear" class="theme">clear</button>
  </div>
  <div class="filters">
    <label>cornerstone investor <input id="cs-box" size="14" placeholder="e.g. gic, hillhouse"></label>
    <label class="labchk"><input type="checkbox" id="cs-first"> rank by cornerstone overlap first</label>
    <span class="note">any spelling of the same house counts</span>
  </div>
  <div class="filters">
    <label>force-include a comp <input id="fi-box" list="deal-list" size="18"
      placeholder="name or code, then Enter"></label>
    <span id="fi-chips"></span>
    <span class="note">pinned to the top of the comps, past every filter — same as Screener!B19 in the workbook</span>
  </div>
  <div id="deal-brief"></div>
  <div id="pick-summary"></div>
  <div class="scroll" id="pick-table"></div>
</section>

<section id="complab">
  <h2>Comps Lab — paint the comps, find the factor</h2>
  <p class="sub">Tick the comps you believe in (top-8 pre-ticked; add any deal by name or code), then
  <b>click each comp's dot to paint it red or blue</b> — e.g. the 3 that trade H-above-A in red, the
  5 that don't in blue. Every panel below reads the paint: the strip grid shows ALL factors at once
  ordered by how cleanly they split, the scatter crosses any two factors, and the histogram drops
  your comps onto the whole market's distribution.</p>
  <div class="filters"><label class="labchk"><input type="checkbox" id="lab-ashare"> A-share deals only
    (mandatory A line)</label>
    <label class="labchk"><input type="checkbox" id="lab-industry"> must match AAStocks industry</label>
    <button id="lab-reset" class="theme">↺ reset to top-8</button>
    <label>auto-paint by outcome <select id="lab-outcome"></select></label></div>
  <div class="filters" id="lab-pick"></div>
  <p class="note" id="lab-paintnote"></p>

  <h3>Side-by-side matrix</h3>
  <div class="scroll" id="lab-matrix"></div>

  <h3>Which factor separates red from blue? — all factors at once</h3>
  <div id="lab-strips"></div>

  <div class="row">
    <div class="chart"><h3>Returns vs factor — where the money is</h3>
      <div class="filters"><label>factor <select id="lab-x"></select></label>
        <label>return <select id="lab-y"></select></label></div>
      <div class="filters" id="lab-presets"></div>
      <div id="lab-xy"></div></div>
    <div class="chart"><h3>Your comps vs the whole market</h3>
      <div class="filters"><label>factor <select id="lab-hfac"></select></label></div>
      <div id="lab-hist"></div></div>
  </div>

  <h3>Return paths (vs offer)</h3>
  <div class="sparks" id="lab-paths"></div>

  <h3>Daily price action, listing → 3 months — every chosen comp</h3>
  <p class="note">Hover any chart for the scan line. Left = rebased on the OFFER (pop included);
  right = rebased on the day-1 OPEN, the first price you could actually trade.</p>
  <div class="pathgrid" id="lab-hpaths"></div>

  <h3>A/H price paths since listing — the notebook's charts, offline</h3>
  <p class="note" id="lab-ah-note"></p>
  <div id="lab-ah"></div>
</section>

<section id="table">
  <h2>Deal table</h2>
  <div class="filters">
    <label>Find <input id="tbl-q" type="search" placeholder="name, code, cornerstone investor, sponsor"
      style="min-width:320px;padding:5px 8px"></label>
    <span class="note" id="tbl-count"></span>
  </div>
  <details class="tblwrap" open><summary>every deal — click a column header to sort</summary>
  <div class="scroll" style="max-height:560px;overflow:auto">
  <table class="tbl deals"><thead><tr>
  <th data-k="code">Code</th><th data-k="name">Name</th><th data-k="subsector">Subsector</th>
  <th data-k="ipo_date">IPO date</th>
  <th class="num" data-k="deal_size_hkdm">Size</th><th class="num" data-k="final_price">Offer</th>
  <th class="num" data-k="oversub_public_mult">Sub</th><th class="num" data-k="cornerstone_pct">CS%</th>
  <th class="num" data-k="first_day_return_pct">Day-1</th><th class="num" data-k="ret_1m_pct">1m</th>
  <th class="num" data-k="ret_3m_pct">3m</th><th class="num" data-k="since_ipo_pct">Since</th>
  <th class="num" data-k="pe_ipo">P/E</th>
  <th data-k="a_share_code">A-share</th><th>Cornerstone (top holder)</th></tr></thead>
  <tbody id="tbl-body"></tbody></table></div></details>
</section>

<section id="csleague">
  <h2>Cornerstone league — how deals anchored by each investor traded</h2>
  <p class="note">Every investor below anchored at least one Main Board IPO in the book.
  Returns are simple averages across their deals: <b>day-1 pop</b> = offer→close;
  the <b>ex-pop legs</b> strip the pop (day-1 close→1w/1m/3m). Hit = share of their
  deals that closed day-1 above offer. Same grouping key the Screener uses, so
  "GIC Private Limited" and "GIC" count as one house.</p>
  <div class="filters">
    <label>Find investor <input id="cs-q" type="search" placeholder="name…"
      style="min-width:260px;padding:5px 8px"></label>
    <label>Min deals <input id="cs-min" type="number" min="1" max="60" step="1"
      value="2" style="width:74px;padding:5px 8px"></label>
    <span class="note" id="cs-count"></span>
  </div>
  <div class="scroll" style="max-height:640px;overflow:auto">
  <table class="tbl deals lgtbl" id="cs-tbl"><thead>
  <tr class="grp">
    <th colspan="3"></th>
    <th class="num grpwith" colspan="4">WITH POP — vs offer (what a cornerstone earns)</th>
    <th class="num grpex" colspan="3">EX-POP — from the day-1 close</th>
    <th></th></tr>
  <tr>
    <th data-k="investor">Investor</th>
    <th class="num" data-k="n">Deals</th>
    <th class="num" data-k="hit">Day-1 hit</th>
    <th class="num grpwith" data-k="avg_d1">Day-1 pop</th>
    <th class="num grpwith" data-k="avg_1w_pop">1 week</th>
    <th class="num grpwith" data-k="avg_1m_pop">1 month</th>
    <th class="num grpwith" data-k="avg_3m_pop">3 month</th>
    <th class="num grpex" data-k="avg_1w">1 week</th>
    <th class="num grpex" data-k="avg_1m">1 month</th>
    <th class="num grpex" data-k="avg_3m">3 month</th>
    <th>Their deals</th></tr></thead>
  <tbody id="cs-body"></tbody></table></div>
</section>

<section id="smleague">
  <h2>Stabilising-manager league — how the deals each bank defended traded</h2>
  <p class="note">The stabilising manager is the bank holding the <b>greenshoe and the
  after-market bid</b>, so this answers a different question from the cornerstone league:
  not who anchored the deal, but who defended it once it traded. Names come from each
  deal's own allotment announcement and are grouped by bank family, so
  "Goldman Sachs (Asia) L.L.C." and "Goldman Sachs International" count once.
  Returns are simple averages. The <b>DAY 1 block</b> splits the session the manager
  actually defended: <b>open vs issue</b> is the pop — where the stock opened against the
  price the bank sold it at; <b>close vs issue</b> is the day-1 return; and
  <b>open→close</b> is whether that open was <i>held</i> or given back. A negative
  open→close alongside a positive close is a bank that spent the day supporting a fading
  stock. The <b>ex-pop legs</b> strip the pop (day-1 close→1w/1m/3m). The <b>shoe
  columns</b> are the tell — a shoe exercised in full means the price never needed
  support; a lapsed one means stock was bought back in to hold the line.</p>
  <p class="note"><b>Read this as deal mix, not as a skill ranking.</b> The banks at the
  bottom of the table are the ones that lead the large international deals — bigger books,
  institutionally priced, deliberately less left on the table — while the banks at the top
  sit on smaller HK retail-driven offerings where pops are structurally larger. A low
  median here means "defended a tightly-priced deal", not "defended it badly". The
  comparison worth making is a bank against deals of its OWN size and regime, which is what
  the screener's comp filters are for.</p>
  <div class="filters">
    <label>Find manager <input id="sm-q" type="search" placeholder="bank…"
      style="min-width:260px;padding:5px 8px"></label>
    <label>Min deals <input id="sm-min" type="number" min="1" max="60" step="1"
      value="2" style="width:74px;padding:5px 8px"></label>
    <span class="note" id="sm-count"></span>
  </div>
  <div class="scroll" style="max-height:640px;overflow:auto">
  <table class="tbl deals lgtbl" id="sm-tbl"><thead>
  <tr class="grp">
    <th colspan="3"></th>
    <th class="num grpd1" colspan="3">DAY 1 — the session they defended</th>
    <th class="num grpwith" colspan="3">WITH POP — vs offer</th>
    <th class="num grpex" colspan="3">EX-POP — from the day-1 close</th>
    <th class="num" colspan="2">SHOE OUTCOME</th>
    <th></th></tr>
  <tr>
    <th data-k="manager">Stabilising manager</th>
    <th class="num" data-k="n">Deals</th>
    <th class="num" data-k="hit">Day-1 hit</th>
    <th class="num grpd1" data-k="avg_d1_open" title="Average day-1 OPEN against the offer price — the pop">Open vs issue</th>
    <th class="num grpd1" data-k="avg_d1" title="Average day-1 CLOSE against the offer price — the day-1 return">Close vs issue</th>
    <th class="num grpd1" data-k="avg_d1_open_close" title="Average day-1 open→close: whether the open was held or given back">Open→close</th>
    <th class="num grpwith" data-k="avg_1w_pop">1 week</th>
    <th class="num grpwith" data-k="avg_1m_pop">1 month</th>
    <th class="num grpwith" data-k="avg_3m_pop">3 month</th>
    <th class="num grpex" data-k="avg_1w">1 week</th>
    <th class="num grpex" data-k="avg_1m">1 month</th>
    <th class="num grpex" data-k="avg_3m">3 month</th>
    <th class="num" data-k="shoe_full_pct">Full</th>
    <th class="num" data-k="shoe_lapsed_pct">Lapsed</th>
    <th>Their deals</th></tr></thead>
  <tbody id="sm-body"></tbody></table></div>
</section>

<script>%%JS%%</script>
</body>
</html>
"""


def main():
    deals, tax, cfg, pipe = load()
    as_of = date.today().isoformat()
    # daily A/H paths (Tencent + FX) so the reference notebook's charts render
    # offline inside the Lab — keyed by code, arrays only
    paths = {}
    pp = ROOT / "data" / "batches" / "ah_paths.json"
    if pp.exists():
        for r in json.loads(pp.read_text())["pairs"]:
            if r.get("days"):
                # EVERY analytic key the batch carries — a fixed whitelist here
                # silently dropped the pre-IPO leg once (every "month before"
                # pane read "no data" while the data sat on disk)
                paths[r["code"]] = {k: v for k, v in r.items()
                                    if k not in ("complete", "v")}
    # fetched-but-dropped guard: every field present in the batch must reach
    # the embed (minus the bookkeeping keys) — the class of bug above can
    # never ship silently again
    if paths:
        batch_keys = {k for r in json.loads(pp.read_text())["pairs"]
                      for k in r} - {"complete", "v", "error", "note"}
        embed_keys = {k for r in paths.values() for k in r}
        missing = batch_keys - embed_keys
        if missing:
            raise SystemExit(f"embed drops batch fields {sorted(missing)} — "
                             f"refusing to build a lying dashboard")
    # H price paths for EVERY deal (first ~3 months) + the day-1 open where a
    # real open exists, so the Lab can draw price action for comps with no A
    # line and rebase ex-pop at the true opening print
    hpaths = {}
    hp = ROOT / "data" / "batches" / "h_paths.json"
    if hp.exists():
        opens = {}
        prp = ROOT / "data" / "batches" / "prices.json"
        if prp.exists():
            for r in json.loads(prp.read_text())["deals"]:
                if r.get("first_open") is not None \
                        and "tencent" not in str(r.get("price_src") or ""):
                    opens[r["code"]] = r["first_open"]
        for r in json.loads(hp.read_text())["deals"]:
            if r.get("closes"):
                # the batch's own kline open wins; Yahoo's open is the fallback
                hpaths[r["code"]] = {"ipo": r["ipo"], "c": r["closes"],
                                     "open0": r.get("open0") or opens.get(r["code"])}
    # cornerstone league — computed HERE (shared clean_names.cs_league) so
    # the Excel sheet and this tab can never disagree
    from clean_names import cs_league, stab_league
    league = cs_league(deals)
    # same treatment for the stabilising-manager league
    smleague = stab_league(deals)
    # A LEAGUE COMPUTED OFF THE SLIMMED LIST IS ONLY AS GOOD AS KEEP. The first
    # build shipped an empty Stabilisers tab because the two manager fields were
    # not whitelisted; the data was on disk the whole time. Fail loudly instead.
    for _nm, _rows, _src in (("cs_league", league, "cornerstone_investors"),
                             ("stab_league", smleague, "stabilizing_manager")):
        if not _rows and any(d.get(_src) for d in
                             json.loads((ROOT / "data" / "deals.json").read_text())["deals"]):
            raise SystemExit(
                f"{_nm} is empty but data/deals.json has {_src} — the field is "
                f"missing from KEEP, so it never reached the embed")
    blob = json.dumps({"as_of": as_of, "deals": deals, "pipe": pipe, "cfg": cfg,
                       "ahpaths": paths, "hpaths": hpaths, "cs_league": league,
                       "stab_league": smleague},
                      ensure_ascii=False, separators=(",", ":"))
    js = JS + BODY_JS.replace("%%DATA%%", blob)
    html = (HTML.replace("%%CSS%%", CSS).replace("%%JS%%", js)
                .replace("%%ASOF%%", as_of))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html)
    print(f"wrote {OUT} ({len(html)//1024} KB, {len(deals)} deals, {len(pipe)} pipeline)")


if __name__ == "__main__":
    main()
