"""Offline-only runner for a synthetic C158208 statutory branch fixture."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from branch_site_preflight import validate_site_branch
from source_tick_capture import validate_geometry


def check() -> dict:
    root = Path(__file__).resolve().parent
    scene = json.loads((root / "scene.json").read_text())
    config = json.loads((root / "config.json").read_text())
    case_id = scene.get("case_id")
    if (config.get("selected_case_id") != case_id or
            config.get("case", {}).get("kind") != scene.get("kind") or
            scene.get("source_kind") != "synthetic_reviewed_fixture"):
        raise ValueError("diagnostic scene or exact case differs")
    site_name = scene.get("site_source")
    if not isinstance(site_name, str) or Path(site_name).name != site_name:
        raise ValueError("diagnostic site must be bundled")
    site_bytes = (root / site_name).read_bytes()
    if hashlib.sha256(site_bytes).hexdigest() != scene.get("site_sha256"):
        raise ValueError("diagnostic site fixture changed")
    site = json.loads(site_bytes)
    if site.get("source_provenance") != "synthetic_fixture":
        raise ValueError("diagnostic site provenance differs")
    validate_geometry(site["capture_geometry"])
    validate_site_branch(site, case_id)
    return {"case_id": case_id, "diagnostic_fixture": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    checked = check()
    if args.check:
        print("diagnostic source-gated check passed: " + checked["case_id"])
        return
    raise ValueError("Synthetic diagnostic fixture cannot run original Native capture")


if __name__ == "__main__":
    main()
