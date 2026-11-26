"""Capture one exact source-reviewed Native pavement protection case."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from package_spec import AID, CAMERA_NAMES, CELL
from pavement_protection import CASES, validate_scene


def reviewed_site(path, case_id):
    path = Path(path).resolve()
    site = json.loads(path.read_text(encoding="utf-8"))
    if (site.get("source_kind") != "reviewed_original_native_site" or
            site.get("assignment_id") != AID or site.get("case_id") != case_id or
            site.get("cell_id") != CELL):
        raise ValueError("reviewed exact pavement site identity missing")
    if (not site.get("map_name") or not site.get("map_sha256") or
            site.get("duration_frames") != 900 or site.get("rate_hz") != 20 or
            tuple(site.get("cameras", ())) != CAMERA_NAMES):
        raise ValueError("reviewed Native map or 900-frame profile missing")
    refs = site.get("source_refs")
    required = {"map", "jurisdiction", "driver", "vehicle", "pavement_condition",
                "pavement_extent", "protection_geometry", "protection_placement_time",
                "vehicle_route", "employment", "work_activity"}
    if not isinstance(refs, list) or not required <= {ref.get("role") for ref in refs}:
        raise ValueError("reviewed Native pavement source classes missing")
    hashes = {}
    for ref in refs:
        target = (path.parent / ref["path"]).resolve()
        if not target.is_relative_to(path.parent) or not target.is_file():
            raise ValueError("reviewed Native pavement source missing")
        value = hashlib.sha256(target.read_bytes()).hexdigest()
        if value != ref.get("sha256"):
            raise ValueError("reviewed Native pavement source hash changed")
        hashes[ref["role"]] = value
    if hashes["map"] != site["map_sha256"]:
        raise ValueError("reviewed Native map source hash differs")
    scene = site.get("scene")
    if not isinstance(scene, dict):
        raise ValueError("reviewed pavement scene missing")
    for role in required - {"map"}:
        if scene.get(role + "_source_sha256") != hashes[role]:
            raise ValueError("reviewed pavement scene source differs: " + role)
    name = case_id.removeprefix(AID + "__")
    matches = [case for case in CASES if case.name == name]
    if len(matches) != 1:
        raise ValueError("unknown exact protected pavement case")
    validate_scene(scene, matches[0])
    site["reviewed_site_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return site, scene, matches[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--case")
    parser.add_argument("--site", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    config_path = Path(__file__).resolve().parent / "config.json"
    if not config_path.is_file():
        raise ValueError("exact bundled config missing")
    config = json.loads(config_path.read_text())
    case_id = config["selected_case_id"]
    if args.case is not None and args.case != case_id:
        raise ValueError("selected exact case changed")
    if args.check:
        print("exact protected pavement runner static check passed: " + case_id)
        return
    site_path = args.site or os.environ.get("C230211_PAVEMENT_SITE")
    if not site_path or not args.host or not args.port or args.output_dir is None:
        raise ValueError("reviewed Native site, host, port and output required")
    site, scene, exact = reviewed_site(site_path, case_id)
    from pavement_native import CarlaPavementAdapter
    from pavement_capture import capture
    adapter = CarlaPavementAdapter(args.host, args.port, site,
                                   config.get("control_profile", {}))
    attempt = capture(adapter, site, scene, exact, case_id, args.output_dir)
    private = next((parent for parent in attempt.parents
                    if parent.name == ".runtime-work"), None)
    if private is None:
        raise ValueError("Native attempt must remain under .runtime-work")
    os.environ.setdefault("SCENARIO_PIPELINE_OUTPUT_ROOT",
                          str(private / "pipeline-output"))
    output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    if output_root != private and private not in output_root.parents:
        raise ValueError("Native analysis requires private runtime output root")
    from analysis import analyze
    report = attempt / "analysis-report.json"
    if report.exists():
        raise ValueError("retain prior Native analysis report")
    report.write_text(json.dumps(analyze(attempt), indent=2) + "\n")


if __name__ == "__main__":
    main()
