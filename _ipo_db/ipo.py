#!/usr/bin/env python3
"""HK IPO database — the only script you need to run.

    python ipo.py refresh     # update everything (resumable; skips what is cached)
    python ipo.py prices      # just re-pull listing-day / current prices
    python ipo.py newdeal 1234 [--name "Acme"]   # fetch + parse ONE deal
    python ipo.py build       # rebuild the workbook and the dashboard
    python ipo.py check       # validation gate
    python ipo.py status      # what is in the database right now

`refresh` runs, in order: roster -> filings -> deep parse -> subscription ->
cornerstone/greenshoe -> profiles -> financials -> prices -> classify -> merge.
Every stage caches, so a re-run weeks later only fetches what is new.

Network: HKEXnews (filings) and AAStocks (roster, A/H) and Yahoo (prices). If one
source is blocked, use --skip to carry on with the rest, e.g.
    python ipo.py refresh --skip hkex        # aggregator + prices only
    python ipo.py refresh --skip prices
"""
import argparse, runpy, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# use the local .venv when there is one (mac/linux or windows layout), else
# whatever python is running us — which is what Jupyter on the desk will give
_venv = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / \
    ("python.exe" if sys.platform == "win32" else "python")
PY = str(_venv) if _venv.exists() else sys.executable

# stage -> (module script in ipo_lib/, argv, source-group)
STAGES = [
    ("roster-aastocks", "ipo_lib/fetch_roster.py", [], "aastocks"),
    ("roster-hkex", "ipo_lib/fetch_hkex_filings.py", ["roster"], "hkex"),
    ("filings-allot", "ipo_lib/fetch_hkex_filings.py", ["allotments"], "hkex"),
    ("filings-prosp", "ipo_lib/fetch_hkex_filings.py", ["prospectus"], "hkex"),
    ("filings-bodies", "ipo_lib/fetch_bodies.py", [], "hkex"),
    ("parse-allot", "ipo_lib/extract_prospectus.py", ["allotments"], "parse"),
    ("parse-prosp", "ipo_lib/extract_prospectus.py", ["prospectus"], "parse"),
    ("parse-deep", "ipo_lib/extract_deep.py", [], "parse"),
    ("parse-subscription", "ipo_lib/fix_oversub.py", [], "parse"),
    # Both re-read the FULL cached announcement text, where the 12-page PDF
    # read used by parse-allot stops short — so they run last of everything
    # that writes extracted_allotments.json, and they never blank a value
    # they cannot better. Skipping them costs 165 proceeds figures and 262
    # offer-share counts, so they are stages, not one-off scripts.
    ("patch-proceeds", "ipo_lib/patch_proceeds.py", ["--apply"], "parse"),
    ("patch-offer-shares", "ipo_lib/patch_offer_shares.py", ["--apply"], "parse"),
    ("parse-shoe", "ipo_lib/extract_shoe_cornerstone.py", [], "parse"),
    ("parse-profiles", "ipo_lib/extract_profiles.py", [], "parse"),
    ("parse-financials", "ipo_lib/extract_financials.py", [], "parse"),
    ("regimes", "ipo_lib/derive_regime.py", [], "parse"),
    # who held the shoe and the after-market bid — read from the cached
    # allotment text, so it costs no network
    ("parse-stabmgr", "ipo_lib/extract_stabmgr.py", [], "parse"),
    ("classify", "ipo_lib/classify.py", [], "parse"),
    ("classify-auto", "ipo_lib/auto_classify.py", [], "parse"),
    ("pipeline-phip", "ipo_lib/fetch_phip.py", [], "hkex"),
    # deals in their OFFERING WINDOW (prospectus out, allotment pending) get the
    # full prospectus parse — plain requests, runs on the desk too
    ("offering-window", "ipo_lib/fetch_newlistings.py", [], "hkex"),
    ("names-cn", "ipo_lib/fetch_names_cn.py", [], "hkex"),
    ("stabilisation", "ipo_lib/fetch_stabilization.py", [], "hkex"),
    ("ah-snapshot", "ipo_lib/fetch_ah_snapshot.py", [], "aastocks"),
    # AAStocks per-deal pages: sponsors, the full underwriting syndicate, market
    # cap at listing and the institutional book. Needs a browser engine, so it is
    # skipped automatically wherever playwright is not installed.
    ("aastocks-deal", "ipo_lib/fetch_aastocks.py", ["--all"], "aastocks"),
    # fetch_prices / fetch_h_paths / fetch_ah_paths all read deals.json for
    # their code list, so a listing parsed in THIS run is invisible to them
    # until it has been merged once. Without this stage a brand-new deal
    # (SHEIN and Mech-Mind, 2026-09-01) lands in the book with no day-1 return
    # and needs a SECOND refresh to price — the merge below then folds the
    # prices back in.
    ("merge-pre-prices", "ipo_lib/merge_batches.py", [], "local"),
    ("prices", "ipo_lib/fetch_prices.py", [], "prices"),
    ("ah-at-ipo", "ipo_lib/fetch_ah_ipo.py", [], "prices"),
    # the chart batches: daily H closes for EVERY deal, and the paired A/H
    # daily paths. These were run by hand until v13, which meant a plain
    # `refresh` produced a database whose price panels were stale.
    ("split-detect", "ipo_lib/detect_splits.py", [], "prices"),
    ("h-paths", "ipo_lib/fetch_h_paths.py", [], "prices"),
    ("ah-paths", "ipo_lib/fetch_ah_paths.py", [], "prices"),
    ("merge", "ipo_lib/merge_batches.py", [], "local"),
]


def run(script, argv=(), quiet=False):
    cmd = [PY, str(ROOT / script), *argv]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    out = "\n".join(l for l in (r.stdout or "").splitlines()
                    if l.strip() and not l.startswith("Cannot set"))
    if not quiet:
        for line in out.splitlines()[-3:]:
            print("   " + line)
    if r.returncode != 0:
        err = "\n".join((r.stderr or "").splitlines()[-4:])
        print(f"   !! failed: {err}")
    return r.returncode == 0


def cmd_refresh(args):
    skip = set(args.skip or [])
    t0 = time.time()
    ok, failed = [], []
    for name, script, argv, group in STAGES:
        if group in skip or name in skip:
            print(f"-- {name}: skipped")
            continue
        print(f"-- {name} ...", flush=True)
        (ok if run(script, argv) else failed).append(name)
    print(f"\ndone in {int(time.time() - t0)}s | {len(ok)} ok, {len(failed)} failed")
    if failed:
        print("failed stages:", ", ".join(failed))
        print("the database still merged with whatever succeeded — re-run to retry")
    cmd_status(args)


def cmd_build(_args):
    run("ipo_lib/build_xlsx.py")
    run("ipo_lib/make_ah_notebook.py")
    run("ipo_lib/build_dashboard.py")


GATES = [
    # name, script, red = export-blocking
    ("coverage floors", "ipo_lib/checks.py", True),
    ("data identities + explained blanks", "ipo_lib/audit_identities.py", True),
    ("prices + returns (every deal, 3 ways)", "ipo_lib/audit_prices.py", True),
    ("Bloomberg terminal reconciliation", "ipo_lib/audit_bbg_verify.py", True),
    ("fresh listings fully parsed", "ipo_lib/audit_fresh.py", True),
    ("formula bindings + field parity", "ipo_lib/audit_formulas.py", True),
    ("Bloomberg formula lint", "ipo_lib/lint_bbg.py", True),
    ("Excel computes + scoring parity", "ipo_lib/test_screener_formulas.py", True),
    ("visual (overlaps/hidden/NaN, light+dark)", "ipo_lib/audit_visual.py", True),
]


def cmd_check(_args):
    """THE review battery — run after every update, before every export.

    This is the scripted version of the full manual review: every gate below
    started life as a by-hand check that caught a real error. Export refuses
    to ship while any of them is red.
    """
    import subprocess
    results = []
    for name, script, _blocking in GATES:
        r = subprocess.run([PY, str(ROOT / script)], cwd=ROOT,
                           capture_output=True, text=True)
        tail = [l for l in (r.stdout or "").splitlines() if l.strip()][-1:]
        results.append((name, r.returncode == 0, tail[0] if tail else ""))
    print("=" * 64)
    print("GATE BATTERY")
    print("=" * 64)
    ok = True
    for name, passed, tail in results:
        print(f"  {'PASS' if passed else 'FAIL'}  {name:42} {tail[:60]}")
        ok = ok and passed
    print("=" * 64)
    print("  ALL GATES GREEN — safe to export." if ok
          else "  RED GATES — fix before exporting (export will refuse).")
    return ok


def cmd_prices(_args):
    run("ipo_lib/fetch_prices.py")
    run("ipo_lib/merge_batches.py")


def cmd_setup(_args):
    """Create .venv and install the (deliberately common) dependencies."""
    import venv
    vdir = ROOT / ".venv"
    if not vdir.exists():
        print("creating .venv ...")
        venv.EnvBuilder(with_pip=True).create(vdir)
    pip = vdir / ("Scripts" if sys.platform == "win32" else "bin") / "pip"
    print("installing requirements (requests, beautifulsoup4, lxml, openpyxl, pypdf, yfinance) ...")
    r = subprocess.run([str(pip), "install", "-r", str(ROOT / "requirements.txt")])
    if r.returncode != 0:
        print("\npip failed — on a proxied corporate network try:")
        print("  .venv\\Scripts\\pip install --proxy http://<user>:<pass>@<proxy>:<port> -r requirements.txt")
    else:
        print("done. run:  python ipo.py refresh")


def cmd_status(_args):
    import json
    p = ROOT / "data" / "deals.json"
    if not p.exists():
        print("no database yet — run: python ipo.py refresh")
        return
    d = json.loads(p.read_text())
    deals = d["deals"]
    n = len(deals)
    print(f"\ndatabase: {n} deals, as of {d.get('as_of')}")
    fields = ["ipo_date", "final_price", "deal_size_hkdm", "subsector",
              "oversub_public_mult", "first_day_return_pct", "cornerstone_pct",
              "sponsors", "pe_ipo", "ps_ipo", "since_ipo_pct"]
    for f in fields:
        k = sum(1 for x in deals if x.get(f) is not None)
        bar = "#" * int(20 * k / max(1, n))
        print(f"  {f:22s} {k:4d}/{n} {bar}")


def cmd_export(args):
    """Build TO_NOMURA/ — the files to carry over, nothing else.

    Runs the FULL gate battery first and refuses on red; --force skips the
    battery (for emergencies only, and it says so on the console).
    """
    import shutil
    run("ipo_lib/build_xlsx.py", quiet=True)
    run("ipo_lib/build_dashboard.py", quiet=True)
    force = getattr(args, "force", False) if args is not None else False
    if force:
        print("   !! --force: exporting WITHOUT the gate battery")
    elif not cmd_check(None):
        print("\nEXPORT REFUSED — a gate is red. Fix it, or use --force "
              "and own the consequences.")
        return
    run("ipo_lib/make_ah_notebook.py", quiet=True)
    run("ipo_lib/make_bundle.py", quiet=True)
    dest = ROOT / "TO_NOMURA"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir()
    shutil.copy2(ROOT / "export" / "hk_ipo.py", dest / "hk_ipo.py")
    shutil.copy2(ROOT / "out" / "HK_IPO_Database_v1.xlsx", dest / "HK_IPO_Database_v1.xlsx")
    shutil.copy2(ROOT / "out" / "hk_ipo_dashboard.html", dest / "hk_ipo_dashboard.html")
    shutil.copy2(ROOT / "out" / "ah_peers.ipynb", dest / "ah_peers.ipynb")
    # the A/H premium study travels with the deliverables when it has been
    # built (export rmtree's this folder, so a hand-copied file would vanish)
    study = ROOT / "out" / "AH_Premium_Study.docx"
    if study.exists():
        shutil.copy2(study, dest / "AH_Premium_Study.docx")
    (dest / "READ_ME_FIRST.txt").write_text(
        "HK IPO DATABASE\n"
        "===============\n\n"
        "PUT THESE FILES IN:  G:\\FIN_COMM\\DeltaOne\\Kenny\\ECM\\\n\n"
        "THE FILES\n"
        "  HK_IPO_Database_v1.xlsx   the workbook — Screener tab is the tool\n"
        "  hk_ipo_dashboard.html     the charts — double-click, works offline\n"
        "  hk_ipo.py                 updates everything (Jupyter, one command)\n"
        "  ah_peers.ipynb            A/H price charts live off Bloomberg\n"
        "  AH_Premium_Study.docx     the A/H premium write-up for senior traders\n"
        "  READ_ME_FIRST.txt         this file\n\n"
        "TO JUST USE IT\n"
        "  Open the .xlsx -> SCREENER tab. Pick a deal from the dropdown, or\n"
        "  type your own terms in the TYPE TO OVERRIDE column — comps re-rank\n"
        "  as you type. The comp table carries EVERY Database column (terms,\n"
        "  demand, all returns incl. ex-pop, A-premium at IPO and today,\n"
        "  HSAHP at IPO, banks, cornerstone) plus the score and why.\n"
        "  Rank modes: standard (subsector first) / cornerstone overlap first /\n"
        "  demand-similar first. A-share filter screens A+H or non-A only.\n\n"
        "  Sign conventions: A-premium = A over H - 1 (+ = A trades ABOVE H).\n"
        "  Ex-pop columns (teal) start at the day-1 CLOSE; the charts' ex-pop\n"
        "  panels rebase at the day-1 OPEN — the first tradeable print.\n\n"
        "TO UPDATE IT (Jupyter, ONE command)\n"
        "  %run hk_ipo.py update      <- fetch + parse + prices + gates +\n"
        "                                rebuild, ends with a VERDICT block\n"
        "  %run hk_ipo.py update --skip aastocks   <- if a site is blocked\n"
        "  %run hk_ipo.py status      <- what is in the database now\n"
        "  A stage that fails keeps its previous data — the files stay usable;\n"
        "  they just do not gain that stage's update.\n\n"
        "BLOOMBERG (terminal only)\n"
        "  The BBG Verify tab fills itself on the terminal (CP036/CP037 subs,\n"
        "  shoe, P/E at listing, A-share P/E at H-IPO, HSAHP Index at IPO —\n"
        "  verify one HSAHP cell before trusting that column, it is new).\n"
        "  To feed the numbers back: let the tab compute, paste-VALUES into\n"
        "  bbg.xlsx (one sheet, headers on row 4), put it next to the repo,\n"
        "  then on the build machine: python ipo_lib/ingest_bbg.py + update.\n"
        "  Retail/instl subscription from Bloomberg OVERRIDE the scrape.\n\n"
        "THE DASHBOARD\n"
        "  Screener tab: pick or type a target, Deal Brief (base rate + worst\n"
        "  peer = your downside), paint comps red/blue, factor strips, plot\n"
        "  anything vs anything, daily price action for every comp (offer-\n"
        "  rebased AND open-rebased), and the six A/H panes per pair incl.\n"
        "  A-share month-before -> month-after. Hover any chart for the scan\n"
        "  line with every series' value. It is a snapshot — it cannot reach\n"
        "  Bloomberg; the live layer is the Excel BDP/BDH cells + the notebook.\n\n"
        "  ah_peers.ipynb: run all cells, a form appears — type codes, draw.\n"
        "  H rebased on the OFFER (100 = what subscribers paid).\n\n"
        "IF PACKAGES ARE EVER MISSING\n"
        "  pip install requests beautifulsoup4 lxml openpyxl pypdf yfinance\n"
        "  (blocked network: add --trusted-host pypi.org "
        "--trusted-host files.pythonhosted.org)\n")
    print(f"\nUPLOAD THIS FOLDER: {dest}\n")
    for f in sorted(dest.iterdir()):
        print(f"   {f.name:28s} {f.stat().st_size/1e6:6.2f} MB")
    print("\n   (READ_ME_FIRST.txt explains the files in plain English)")


def cmd_newdeal(args):
    """Fetch and parse a single code, then print the NEW DEAL inputs to type in."""
    import json
    code = args.code.lstrip("0").zfill(4)
    print(f"fetching {code} from HKEXnews ...")
    run("ipo_lib/fetch_hkex_filings.py", ["roster"], quiet=True)
    run("ipo_lib/fetch_hkex_filings.py", ["prospectus"], quiet=True)
    run("ipo_lib/extract_deep.py", quiet=True)
    run("ipo_lib/extract_financials.py", quiet=True)
    run("ipo_lib/merge_batches.py", quiet=True)
    d = json.loads((ROOT / "data" / "deals.json").read_text())["deals"]
    hit = next((x for x in d if x["code"] == code), None)
    if not hit:
        print(f"{code} not found — it may not have filed allotment results yet.")
        print("Type what you have from the prospectus into the NEW DEAL tab instead.")
        return
    print(f"\n--- NEW DEAL inputs for {hit.get('name')} ({code}) ---")
    for label, key in (("Subsector", "subsector"), ("Offer size (HK$m)", "deal_size_hkdm"),
                       ("Offer price", "final_price"), ("Cap price", "price_range_hi"),
                       ("Shares in issue (m)", "shares_outstanding"),
                       ("Revenue (HK$m)", "rev_latest"), ("Net profit (HK$m)", "ni_latest"),
                       ("Cornerstone %", "cornerstone_pct"),
                       ("Subscription (x)", "oversub_public_mult")):
        v = hit.get(key)
        if key == "shares_outstanding" and v:
            v = round(v / 1e6, 1)
        print(f"  {label:22s} {v if v is not None else '— type it in'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("refresh", help="update everything")
    r.add_argument("--skip", nargs="*", help="stages or source groups: hkex aastocks prices parse")
    r.set_defaults(fn=cmd_refresh)
    sub.add_parser("setup", help="create .venv + install requirements").set_defaults(fn=cmd_setup)
    sub.add_parser("build", help="rebuild workbook + dashboard").set_defaults(fn=cmd_build)
    sub.add_parser("check", help="run the validation gate").set_defaults(fn=cmd_check)
    sub.add_parser("prices", help="re-pull prices only").set_defaults(fn=cmd_prices)
    sub.add_parser("status", help="coverage summary").set_defaults(fn=cmd_status)
    ex = sub.add_parser("export", help="bundle what another machine needs")
    ex.add_argument("--force", action="store_true",
                    help="skip the gate battery (emergencies only)")
    ex.set_defaults(fn=cmd_export)
    nd = sub.add_parser("newdeal", help="fetch + parse one deal")
    nd.add_argument("code")
    nd.set_defaults(fn=cmd_newdeal)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
