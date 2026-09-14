"""Parse only some deals, and keep the rest of the batch.

Every extractor reads a manifest, walks EVERY deal's PDFs and rewrites its
whole output file. That is right for a first build and wasteful afterwards:
a week's work is three new listings against 527 unchanged ones, and on a
machine where iCloud has evicted the PDF cache each unchanged deal costs a
multi-second download before it parses to the same answer it gave last time.

So every extractor takes `--only 2041,9976` (or `--new`, meaning "codes the
output file does not have yet"): it parses those deals and carries every
other record forward from the existing batch. The output is identical in
shape, so nothing downstream knows the difference.

    python ipo_lib/extract_prospectus.py allotments --only 2041,9976,3231
    python ipo_lib/extract_profiles.py --new
"""
import json
import sys
from pathlib import Path


def _codes(argv=None):
    argv = list(sys.argv if argv is None else argv)
    if "--only" in argv:
        i = argv.index("--only")
        if i + 1 < len(argv):
            return {c.strip().lstrip("0").zfill(4)
                    for c in argv[i + 1].replace(",", " ").split() if c.strip()}
    return None


def wanted(out_path, manifest_codes=None, argv=None):
    """The set of codes to parse, or None for "all of them".

    --only lists them. --new derives them: every code in the manifest that the
    existing output file has no record for.
    """
    argv = list(sys.argv if argv is None else argv)
    only = _codes(argv)
    if only:
        return only
    if "--new" in argv:
        have = {str(r.get("code")) for r in existing(out_path)}
        return {c for c in (manifest_codes or ()) if str(c) not in have}
    return None


def existing(out_path, key="deals"):
    p = Path(out_path)
    if not p.exists():
        return []
    try:
        blob = json.loads(p.read_text())
    except Exception:
        return []
    return blob.get(key) or blob.get("manifest") or []


def merge(out_path, fresh, only, key="deals"):
    """Fresh records for `only`, every other record carried forward.

    A code parsed this run REPLACES its old record even when the parse found
    less than before — a re-parse is a decision to trust the new read.
    """
    if not only:
        return fresh
    done = {str(r.get("code")) for r in fresh}
    kept = [r for r in existing(out_path, key) if str(r.get("code")) not in done]
    out = kept + fresh
    out.sort(key=lambda r: str(r.get("code") or ""))
    return out
