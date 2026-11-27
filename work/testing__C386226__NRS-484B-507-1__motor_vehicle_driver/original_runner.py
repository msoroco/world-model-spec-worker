"""Load a reviewed C386226 site before any original Native construction."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from freight_zone import CASES, build_case, validate_site

AID = "testing__C386226__NRS-484B-507-1__motor_vehicle_driver"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_reviewed_site(manifest_path, site_path, exact_case_id):
    manifest_path, site_path = Path(manifest_path), Path(site_path)
    if any(not path.is_file() or path.is_symlink() for path in (manifest_path, site_path)):
        raise ValueError("reviewed original freight-zone site source missing")
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get("source_kind") != "reviewed_original_site" or
            manifest.get("diagnostic_fixture") is not False or not manifest.get("reviewer") or
            manifest.get("case_id") != exact_case_id):
        raise ValueError("reviewed original freight source identity missing")
    provenance = manifest.get("source_provenance", {})
    if (provenance.get("kind") != "original_reviewed_site" or
            provenance.get("diagnostic_fixture") is not False or
            not provenance.get("reviewer") or not provenance.get("citation")):
        raise ValueError("original reviewed freight site provenance missing")
    if manifest.get("files", {}).get("site-context.json", {}).get("sha256") != sha(site_path):
        raise ValueError("original freight site source hash mismatch")
    site = json.loads(site_path.read_text())
    if site.get("source_kind") != "reviewed_original_site" or not site.get("reviewer"):
        raise ValueError("original freight site reviewer missing")
    return site


def construct(adapter, manifest_path, site_path, exact_case_id):
    prefix = AID + "__"
    if not exact_case_id.startswith(prefix):
        raise ValueError("wrong exact freight case")
    name = exact_case_id.removeprefix(prefix)
    case = next((item for item in CASES if item.name == name), None)
    if case is None:
        raise ValueError("unknown exact freight case")
    site = load_reviewed_site(manifest_path, site_path, exact_case_id)
    validate_site(site, case)
    made = build_case(adapter, site, case)
    return {"case_id": exact_case_id, "owned": made["owned"],
            "site_sha256": sha(site_path), "source_manifest_sha256": sha(manifest_path),
            "physical_status": "unverified", "legal_status": "unresolved"}
