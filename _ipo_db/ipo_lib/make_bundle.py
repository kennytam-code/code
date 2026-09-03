#!/usr/bin/env python3
"""Build ONE self-contained file: export/hk_ipo.py

The desk can only reliably download .xlsx and .py files, and does not want a
51-file folder. So this packs the entire database (deals + config + pipeline)
plus the two builders into a single .py. On the other machine:

    pip install openpyxl
    python hk_ipo.py

...and it writes the Excel workbook and the HTML dashboard next to itself. No
folder structure, no venv, no internet, one dependency.

Data is zlib-compressed and base64-encoded inline. The builder sources are
inlined too, with their ROOT rewritten to the bundle's own directory.
"""
import base64, json, zlib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "export"

# only what the builders actually read — not the raw scrape batches
DATA_FILES = [
    # what the two builders read
    'data/deals.json', 'data/taxonomy.json', 'data/screener_config.json',
    'data/force_raw_codes.json', 'data/manual_splits.json',
    'data/auto_splits.json', 'data/entitlement_adjustments.json',
    'data/official_counts.json',
    'data/batches/pipeline.json', 'data/batches/phip_pipeline.json',
    'data/batches/newlistings.json', 'data/batches/ah_paths.json',
    'data/batches/h_paths.json',
    'data/batches/press_sizes.json', 'data/batches/aastocks_planned.json',
    # v13: the BASE batches merge_batches consumes. Without these a desk that
    # cannot reach HKEX could not re-merge at all — which is exactly the case
    # after pasting bbg.xlsx (no network needed, but merge must still run).
    'data/batches/hkex_allotments.json', 'data/batches/extracted_allotments.json',
    'data/batches/extracted_prospectus.json', 'data/batches/extracted_deep.json',
    'data/batches/extracted_financials.json', 'data/batches/extracted_profiles.json',
    'data/batches/extracted_shoe_cornerstone.json', 'data/batches/prices.json',
    'data/batches/deep_classify.json', 'data/batches/deep_regime.json',
    'data/batches/aastocks_deal.json', 'data/batches/aastocks_deal_en.json',
    'data/batches/ah_ipo.json', 'data/batches/ah_snapshot.json',
    'data/batches/names_cn.json', 'data/batches/bbg_desk.json',
    'data/batches/press_figures.json', 'data/batches/bbg_verify_results.json',
    'data/batches/withdrawn.json', 'data/batches/hkex_prospectus_links.json',
    'data/batches/bulk_roster.json', 'data/batches/stabilization.json',
    'data/batches/deep_cornerstone_reparse.json', 'data/batches/deep_cornerstone_fill.json',
    'data/batches/deep_sponsors_fill.json', 'data/batches/ah_map.json',
    'data/batches/aastocks_pl.json', 'data/batches/ah_universe.json',
    'data/batches/deep_autoclass.json', 'data/batches/extracted_allotments.json',
    'data/batches/hkex_allotment_files.json', 'data/batches/ah_triplecheck.json',
    'data/batches/relinked_docs.json', 'data/batches/deep_classify.json',
]
# every pipeline module, so the ONE file can also refresh — not just rebuild
LIB_MODULES = [
    "fetch_roster", "fetch_hkex_filings", "fetch_bodies", "fetch_phip",
    "fetch_newlistings", "fetch_names_cn", "fetch_ah_snapshot", "fetch_prices",
    "fetch_ah_ipo", "fetch_ah_paths", "fetch_stabilization", "fetch_aastocks",
    "extract_prospectus", "extract_deep", "extract_profiles", "extract_financials",
    "extract_shoe_cornerstone", "extract_stabmgr",
    "fix_oversub", "patch_proceeds", "patch_offer_shares",
    "derive_regime", "classify", "auto_classify",
    "clean_names", "textclip", "pipeline_dedupe", "detect_splits", "sessions",
    "reparse_cornerstone", "audit_returns",
    "fetch_h_paths", "ingest_bbg", "audit_formulas", "lint_bbg", "audit_opens",
    "audit_identities", "audit_visual", "audit_prices", "audit_bbg_verify", "audit_fresh",
    "corp_actions",
    "merge_batches", "build_xlsx", "build_dashboard", "make_ah_notebook", "checks",
    "make_weekly_email",
]

HEADER = '''#!/usr/bin/env python3
"""HK IPO DATABASE — the whole system in one file.

IN JUPYTER (three cells, in this order):

    %run hk_ipo.py status      # what is in the database right now
    %run hk_ipo.py refresh     # go get the latest deals (needs internet)
    %run hk_ipo.py build       # write the .xlsx and .html next to this file

FROM A TERMINAL: python hk_ipo.py status  (etc.)

If a website is blocked here, refresh still runs on what it can reach:
    %run hk_ipo.py refresh --skip hkex
    %run hk_ipo.py refresh --skip prices

Needs: requests beautifulsoup4 lxml openpyxl pypdf yfinance
    pip install requests beautifulsoup4 lxml openpyxl pypdf yfinance
If the bank network blocks pip:
    pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org <packages>
    pip install --proxy http://USER:PASS@PROXY:PORT <packages>

Everything it creates lands in THIS folder. Built {built}:
{ndeals} Hong Kong Main Board IPOs, {y0}-{y1}.
"""
import base64, datetime as _dt, json, sys, zlib
from pathlib import Path

BUNDLE_ROOT = Path(__file__).resolve().parent
_PAYLOAD = "{payload}"


def _unpack(persist=False):
    """Unpack the embedded database. build() uses a temp folder and cleans up;
    refresh() needs it to persist so the pipeline can update it in place."""
    import tempfile
    if persist or (BUNDLE_ROOT / "data" / "deals.json").exists():
        tmp = BUNDLE_ROOT
        blob = json.loads(zlib.decompress(base64.b64decode(_PAYLOAD)).decode("utf-8"))
        for rel, text in blob.items():
            p = tmp / rel
            if not p.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
        return tmp, len(blob)
    tmp = Path(tempfile.mkdtemp(prefix="hkipo_"))
    blob = json.loads(zlib.decompress(base64.b64decode(_PAYLOAD)).decode("utf-8"))
    for rel, text in blob.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp, len(blob)


_MODULES = {modules}
_LIBZIP = "{libzip}"


def _run(name, datadir):
    """Execute an inlined builder in its own namespace (both modules define
    same-named helpers, so they must not share globals). Reads from the temp
    data folder, writes the finished file next to this script."""
    src = zlib.decompress(base64.b64decode(_MODULES[name])).decode("utf-8")
    ns = {{"__name__": name, "BUNDLE_ROOT": datadir, "__file__": name + ".py"}}
    exec(compile(src, name + ".py", "exec"), ns)
    ns["OUT"] = BUNDLE_ROOT / Path(str(ns["OUT"])).name    # beside the script
    ns["main"]()


def _install_lib():
    """Unpack the pipeline modules beside this file and make them importable,
    so `refresh` works from the single file too (not just `build`)."""
    import zipfile, io, sys as _s
    libdir = BUNDLE_ROOT / "ipo_lib"
    if not (libdir / "merge_batches.py").exists():
        libdir.mkdir(exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(_LIBZIP))) as z:
            z.extractall(libdir)
    # the modules import EACH OTHER by bare name (merge_batches -> clean_names),
    # so the unpacked lib dir itself must be importable, not just its parent
    for _p in (str(libdir), str(BUNDLE_ROOT)):
        if _p not in _s.path:
            _s.path.insert(0, _p)
    return libdir


def _run_stage(mod, argv=()):
    import runpy, sys as _s
    libdir = _install_lib()
    old = _s.argv[:]
    _s.argv = [str(libdir / (mod + ".py")), *argv]
    try:
        runpy.run_path(str(libdir / (mod + ".py")), run_name="__main__")
    finally:
        _s.argv = old


# MUST mirror ipo.py's STAGES (minus playwright-only work). A stage missing
# here means the desk silently ships a thinner database than the Mac does —
# which is exactly what happened to the offering-window parse and both chart
# batches before v13. `python ipo.py check-bundle` now fails if they diverge.
STAGES = [
    ("roster-aastocks", "fetch_roster", [], "aastocks"),
    ("roster-hkex", "fetch_hkex_filings", ["roster"], "hkex"),
    ("filings-allot", "fetch_hkex_filings", ["allotments"], "hkex"),
    ("filings-prosp", "fetch_hkex_filings", ["prospectus"], "hkex"),
    ("filings-bodies", "fetch_bodies", [], "hkex"),
    ("pipeline-phip", "fetch_phip", [], "hkex"),
    ("offering-window", "fetch_newlistings", [], "hkex"),
    ("names-cn", "fetch_names_cn", [], "hkex"),
    ("parse-allot", "extract_prospectus", ["allotments"], "parse"),
    ("parse-prosp", "extract_prospectus", ["prospectus"], "parse"),
    ("parse-deep", "extract_deep", [], "parse"),
    ("parse-subscription", "fix_oversub", [], "parse"),
    ("patch-proceeds", "patch_proceeds", ["--apply"], "parse"),
    ("patch-offer-shares", "patch_offer_shares", ["--apply"], "parse"),
    ("parse-shoe", "extract_shoe_cornerstone", [], "parse"),
    ("stabilisation", "fetch_stabilization", [], "hkex"),
    ("parse-profiles", "extract_profiles", [], "parse"),
    ("parse-financials", "extract_financials", [], "parse"),
    ("regimes", "derive_regime", [], "parse"),
    ("parse-stabmgr", "extract_stabmgr", [], "parse"),
    ("classify", "classify", [], "parse"),
    ("classify-auto", "auto_classify", [], "parse"),
    ("ah-snapshot", "fetch_ah_snapshot", [], "aastocks"),
    ("merge-pre-prices", "merge_batches", [], "local"),
    ("prices", "fetch_prices", [], "prices"),
    ("ah-at-ipo", "fetch_ah_ipo", [], "prices"),
    ("split-detect", "detect_splits", [], "prices"),
    ("h-paths", "fetch_h_paths", [], "prices"),
    ("ah-paths", "fetch_ah_paths", [], "prices"),
    ("merge", "merge_batches", [], "local"),
]


def cmd_refresh(skip):
    _unpack(persist=True)
    ok = fail = 0
    failed = []
    for name, mod, argv, group in STAGES:
        if group in skip or name in skip:
            print(f"-- {{name}}: skipped")
            continue
        print(f"-- {{name}} ...", flush=True)
        try:
            _run_stage(mod, argv)
            ok += 1
        except SystemExit:
            ok += 1
        except Exception as e:
            print(f"   !! {{type(e).__name__}}: {{e}}")
            fail += 1
            failed.append(name)
    print(f"\\n{{ok}} stages ok, {{fail}} failed")
    cmd_status()
    return ok, fail, failed


def cmd_status():
    import json as _j
    p = BUNDLE_ROOT / "data" / "deals.json"
    if not p.exists():
        _unpack(persist=True)
    d = _j.loads(p.read_text(encoding="utf-8"))
    deals = d["deals"]
    n = len(deals)
    print(f"\\ndatabase: {{n}} deals, as of {{d.get('as_of')}}")
    for f in ("ipo_date", "final_price", "deal_size_hkdm", "subsector",
              "oversub_public_mult", "oversub_intl_mult", "first_day_return_pct",
              "ret_1m_pct", "alpha_1m_pct", "cornerstone_pct", "sponsors",
              "pe_ipo", "ps_ipo", "name_cn"):
        k = sum(1 for x in deals if x.get(f) is not None)
        print(f"  {{f:22s}} {{k:4d}}/{{n}} {{'#' * int(20 * k / max(1, n))}}")


def cmd_update(skip):
    """refresh -> gates -> rebuild, in one go, with a verdict at the end.

    This is the command for "a pipeline deal listed, bring everything up to
    date". It never leaves you guessing: each stage prints OK/FAILED, the gates
    run before anything is rebuilt, and the last block says plainly whether the
    two output files can be trusted or need a look.
    """
    import shutil
    t0 = _dt.datetime.now()
    print("=" * 68)
    print("HK IPO DATABASE — FULL UPDATE")
    print("=" * 68)
    ok, fail, failed = cmd_refresh(skip)
    print("\\n-- gates ...", flush=True)
    datadir, _n = _unpack()
    gates = {{}}
    # gates are LIB modules (unpacked beside the script), not inlined builders —
    # _run() only knows the two builders and raised KeyError on them
    for g in ("checks", "audit_returns"):
        try:
            _run_stage(g)
            gates[g] = "PASS"
        except SystemExit as e:
            gates[g] = "PASS" if not e.code else f"ISSUES (exit {{e.code}})"
        except Exception as e:
            gates[g] = f"could not run: {{type(e).__name__}} {{str(e)[:50]}}"
    print("\\n-- rebuilding the two files ...", flush=True)
    built = []
    try:
        for m, label in (("build_xlsx", "HK_IPO_Database_v1.xlsx"),
                         ("build_dashboard", "hk_ipo_dashboard.html")):
            try:
                _run(m, datadir)
                built.append(label)
            except Exception as e:
                print(f"   !! {{label}} FAILED: {{str(e)[:90]}}")
    finally:
        # NEVER delete BUNDLE_ROOT: _unpack() returns the script's OWN folder once
        # data/ exists there, so an unguarded rmtree wiped the script, the data and
        # the two output files. Only a genuine temp dir may be removed.
        if Path(datadir).resolve() != BUNDLE_ROOT:
            shutil.rmtree(datadir, ignore_errors=True)
    mins = (_dt.datetime.now() - t0).total_seconds() / 60
    print("\\n" + "=" * 68)
    print(f"VERDICT  ({{mins:.0f}} min)")
    print("=" * 68)
    print(f"  fetch/parse stages : {{ok}} ok, {{fail}} failed"
          + (f"  -> {{', '.join(failed)}}" if failed else ""))
    for g, v in gates.items():
        print(f"  gate {{g:16}}: {{v}}")
    print(f"  files rebuilt      : {{', '.join(built) if built else 'NONE'}}")
    if fail == 0 and len(built) == 2:
        print("\\n  ALL GOOD — the two files beside this script are current.")
    else:
        print("\\n  NEEDS A LOOK. Nothing here is silently wrong: any stage that")
        print("  failed simply left its previous data in place, so the files are")
        print("  still usable — they just do not include that stage's update.")
        print("  Re-run:  %run hk_ipo.py update --skip <the failing group>")
    return 0 if fail == 0 else 1


def main():
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("Missing openpyxl. Run:  pip install openpyxl")
        print("If the bank network blocks it, try:")
        print("  pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org openpyxl")
        sys.exit(1)
    import shutil
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "status":
        return cmd_status()
    if cmd in ("refresh", "update"):
        skip = set()
        if "--skip" in sys.argv:
            skip = set(sys.argv[sys.argv.index("--skip") + 1:])
        if cmd == "update":
            return cmd_update(skip)
        cmd_refresh(skip)
        return
    datadir, n = _unpack()
    try:
        _run("build_xlsx", datadir)
        _run("build_dashboard", datadir)
    finally:
        # NEVER delete BUNDLE_ROOT: _unpack() returns the script's OWN folder once
        # data/ exists there, so an unguarded rmtree wiped the script, the data and
        # the two output files. Only a genuine temp dir may be removed.
        if Path(datadir).resolve() != BUNDLE_ROOT:
            shutil.rmtree(datadir, ignore_errors=True)
    print("\\nDone. Two files are now next to this script:")
    print("   HK_IPO_Database_v1.xlsx   <- open this, go to the NEW DEAL tab")
    print("   hk_ipo_dashboard.html     <- double-click for the charts")


'''

FOOTER = '''

if __name__ == "__main__":
    main()
'''


def module_blob(name):
    """Compress a builder's source, rewritten to resolve paths at the bundle."""
    src = (ROOT / "ipo_lib" / f"{name}.py").read_text()
    src = src.replace('ROOT = Path(__file__).resolve().parent.parent',
                      'ROOT = BUNDLE_ROOT')
    src = src.replace('if __name__ == "__main__":', 'if False:')
    return base64.b64encode(zlib.compress(src.encode("utf-8"), 9)).decode()


def main():
    blob = {}
    for rel in DATA_FILES:
        p = ROOT / rel
        if p.exists():
            blob[rel] = p.read_text(encoding="utf-8")
    payload = base64.b64encode(
        zlib.compress(json.dumps(blob, ensure_ascii=False).encode("utf-8"), 9)).decode()

    deals = json.loads(blob["data/deals.json"])["deals"]
    years = sorted({d["ipo_date"][:4] for d in deals if d.get("ipo_date")})

    modules = {"build_xlsx": module_blob("build_xlsx"),
               "build_dashboard": module_blob("build_dashboard")}
    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("__init__.py", "")
        for m in LIB_MODULES:
            src = (ROOT / "ipo_lib" / f"{m}.py").read_text()
            z.writestr(f"{m}.py", src)
    libzip = base64.b64encode(buf.getvalue()).decode()

    text = (HEADER.format(payload=payload, built=date.today().isoformat(),
                          ndeals=len(deals), y0=years[0], y1=years[-1],
                          modules=repr(modules), libzip=libzip)
            + FOOTER)

    OUT.mkdir(exist_ok=True)
    dest = OUT / "hk_ipo.py"
    dest.write_text(text, encoding="utf-8")
    print(f"wrote {dest}  ({dest.stat().st_size/1e6:.1f} MB, {len(blob)} data files embedded)")


if __name__ == "__main__":
    main()
