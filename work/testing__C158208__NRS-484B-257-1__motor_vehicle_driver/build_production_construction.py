"""Build an exact C158208 Native construction from a reviewed site packet.

This builder never invents a map or site. The caller supplies a reviewed packet
and all eight adjacent original source files. The output remains unselected
until its own offline and delivery proofs pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from build_semantic_proposals import KINDS, recording_description
from carla_scene_adapter import validate_native_scene_spec
from native_attempt import REVIEW_SOURCES, verify_review_sources
from source_tick_capture import validate_geometry
from through_traffic_control import validate_plan as validate_through_plan
from branch_site_preflight import validate_site_branch


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name


def build(kind: str, site_path: Path, output: Path) -> dict:
    if kind not in KINDS:
        raise ValueError("unknown exact statutory case")
    site_path = Path(site_path)
    output = Path(output)
    if output.exists():
        raise ValueError("production construction output already exists")
    site_bytes = site_path.read_bytes()
    site = json.loads(site_bytes)
    if site.get("review_status") != "reviewed" or site.get("cell_id") != "C158208":
        raise ValueError("reviewed C158208 Native site required")
    verify_review_sources(site, site_path, diagnostic_fixture=False)
    validate_geometry(site["capture_geometry"])
    case_id = ASSIGNMENT + "__" + kind
    validate_site_branch(site, case_id)
    station = site.get("ego_view_station_m") if kind.startswith("nearest_view") else site.get("stopping_reference_station_m")
    if isinstance(station, bool) or not isinstance(station, (int, float)) or not math.isfinite(station):
        raise ValueError("reviewed finite nearest-view station required")
    scene_source = site.get("native_scene")
    validate_native_scene_spec(scene_source, site["capture_geometry"])
    validate_through_plan(scene_source["through_vehicle"].get("motion_plan"))
    source_names = [site_path.name]
    if not site_path.name or site_path.name in ("scene.json", "config.json", "runner.py"):
        raise ValueError("reviewed site filename conflicts with construction")
    for name in REVIEW_SOURCES:
        source_names.append(site["source_bindings"][name]["path"])
    if len(source_names) != len(set(source_names)):
        raise ValueError("reviewed original source filenames must be unique")
    donor = kind if (HERE / f"construction-{kind}.json").is_file() else "nearest_view_response"
    draft = json.loads((HERE / f"construction-{donor}.json").read_text())
    if draft.get("case_id") != ASSIGNMENT + "__" + donor or draft.get("diagnostic_only") is not True:
        raise ValueError("diagnostic construction donor changed")
    files = {item["path"]: item["content"] for item in draft["files"]}
    files["analysis.py"] = (HERE / "analysis.py").read_text(encoding="utf-8")
    files["statutory_branch_measurement.py"] = (HERE / "statutory_branch_measurement.py").read_text(encoding="utf-8")
    files["prepare_derived_media.py"] = (HERE / "prepare_derived_media.py").read_text(encoding="utf-8")
    files["native_capture_finalize.py"] = (HERE / "native_capture_finalize.py").read_text(encoding="utf-8")
    files["carla_scene_adapter.py"] = (HERE / "carla_scene_adapter.py").read_text(encoding="utf-8")
    files["through_traffic_control.py"] = (HERE / "through_traffic_control.py").read_text(encoding="utf-8")
    files["native_attempt.py"] = (HERE / "native_attempt.py").read_text(encoding="utf-8")
    files["branch_site_preflight.py"] = (HERE / "branch_site_preflight.py").read_text(encoding="utf-8")
    files["build_semantic_proposals.py"] = (HERE / "build_semantic_proposals.py").read_text(encoding="utf-8")
    files["yield_control.py"] = (HERE / "yield_control.py").read_text(encoding="utf-8")
    files["source_tick_capture.py"] = (HERE / "source_tick_capture.py").read_text(encoding="utf-8")
    files["camera_sources.py"] = (HERE / "camera_sources.py").read_text(encoding="utf-8")
    files["delivery_audit.py"] = (HERE / "delivery_audit.py").read_text(encoding="utf-8")
    files["runner.py"] = (HERE / "production_runner.py").read_text(encoding="utf-8")
    files["tests/test_bundle.py"] = (HERE / "production_bundle_test.py").read_text(encoding="utf-8")
    config = json.loads(files["config.json"])
    config["selected_case_id"] = case_id
    config["case"]["kind"] = kind
    files["config.json"] = json.dumps(config, indent=2, sort_keys=True) + "\n"
    scene = json.loads(files["scene.json"])
    scene.update({"source_kind": "original_reviewed_site", "site_source": site_path.name,
                  "site_sha256": hashlib.sha256(site_bytes).hexdigest(),
                  "site_source_status": "reviewed_original_source_embedded",
                  "capture_geometry": site["capture_geometry"],
                  "case_id": case_id, "kind": kind})
    files["scene.json"] = json.dumps(scene, indent=2, sort_keys=True) + "\n"
    for name in source_names:
        if name in files:
            raise ValueError("reviewed source filename conflicts with construction file")
        files[name] = (site_path.parent / name).read_text(encoding="utf-8")
    draft["diagnostic_only"] = False
    draft["case_id"] = case_id
    draft["recording_description"] = recording_description()
    draft["files"] = [{"path": path, "content": content} for path, content in files.items()]
    encoded = (json.dumps(draft, indent=2, ensure_ascii=False) + "\n").encode()
    if len(encoded) > 2 * 1024 * 1024:
        raise ValueError("production construction exceeds returned-file limit")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encoded)
    return {"case_id": case_id, "construction_sha256": hashlib.sha256(encoded).hexdigest(),
            "reviewed_site_sha256": hashlib.sha256(site_bytes).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=KINDS, required=True)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.kind, args.site, args.output), indent=2))
