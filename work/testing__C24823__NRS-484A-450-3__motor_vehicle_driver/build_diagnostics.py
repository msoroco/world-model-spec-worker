"""Author five exact synthetic diagnostics and source-bound measurement contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
EXAMPLE = REPO / "runtime/fixtures/example.json"
REQUIREMENTS = (
    ("Yield sign governance and nearest crosswalk, otherwise marked line, otherwise nearest-view reference",
     "NRS 484A.450(3) exact text", "reference_hierarchy", "measure_reference_hierarchy", "sourced_context"),
    ("Original blind-approach occluder and approaching-traffic sight geometry",
     "NRS 484A.450(3) and frozen C24823 conditional witness", "original_view", "measure_original_view", "measured"),
    ("Independently sourced safety necessity and original 20 Hz motor-vehicle stopping trace",
     "NRS 484A.450(3) conditional if required for safety", "stop_behavior", "measure_stop_behavior", "measured"),
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    ids = [case["case_id"] for case in plan["cases"]]
    plan["requirement_dispositions"] = [{"requirement": req, "source": source,
        "status": "selected_required", "evidence_or_gap": "No accepted original C24823 recording; source review and Native stop trace pending.",
        "case_ids": ids} for req, source, _, _, _ in REQUIREMENTS]
    plan["source_observation_mapping"] = {}
    channels = (
        ("original_body_polygon", "original CARLA eight world-space body vertices and center at 20 Hz", "full body relative to governing stop reference"),
        ("original_speed", "original CARLA ego velocity at 20 Hz", "sampled stop speed"),
        ("yield_control_readback", "original yield sign and live approach lane/map readback", "governing control and approach identity"),
        ("original_view_geometry", "source-sealed original occluder, driver-viewpoint and approaching traffic packets", "geometric candidate sight ray; driver perception unresolved"),
        ("four_camera_frames", "four original synchronized Native RGB cameras", "frame identity, full decode and actual pixel review"),
    )
    plan["observations"] = [{"name": name, "mandatory": True, "source": source,
                              "measurement": measurement} for name, source, measurement in channels]
    plan["observations"].append({"name": "reviewed_yield_context", "mandatory": False,
        "source": "independently reviewed original map, yield sign, crossing inventory, safety context and sight geometry",
        "measurement": "source gate and original evidence hashes; no automatic legal judgment"})
    plan["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary", "coverage": [
            {"view": "overview", "subject": "whole yield approach and intersecting highway", "interval": "before approach through complete passage"},
            {"view": "approach", "subject": "motor vehicle, yield sign and priority reference", "interval": "before stop through release"},
            {"view": "reference_corner", "subject": "crosswalk, marked line or nearest-view reference", "interval": "stop approach through entry"},
            {"view": "driver_reference", "subject": "occluder, sight target and original vehicle pose", "interval": "approach through intersecting-highway entry"}]}
    plan["planning_status"] = "selected_five_cases_three_comparisons_source_gated_cpu_preparation"
    for case in plan["cases"]:
        case["kind"] = "delivery"
        case["new_capture_selected"] = True
        case["planning_status"] = "selected_original_source_and_physical_review_pending"
        case["variant"] = case["case_id"].rsplit("__", 1)[1]
        case["actor"] = "motor_vehicle_driver"
        case["cell_id"] = "C24823"
        case["target_law_id"] = "NRS-484A-450-3"
    for comparison in plan["comparisons"]:
        comparison["status"] = "selected_controlled_comparison_cpu_audit_pending"
    write(ROOT / "case-plan.json", plan)
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    for case in plan["cases"]:
        cid = case["case_id"]
        tag = case["variant"]
        folder = ROOT / "cases" / tag
        diagnostic = json.loads(json.dumps(example))
        files = diagnostic["files"]
        fixture_manifest = json.loads(files["capture/manifest.json"])
        fixture_manifest["case_id"] = cid
        files["capture/manifest.json"] = json.dumps(fixture_manifest, sort_keys=True) + "\n"
        site = {"assignment_id": ROOT.name, "case_id": cid, "map_id": "synthetic-diagnostic-map",
            "control": "yield_sign", "yield_sign_id": "synthetic-yield", "vehicle_type": "motor_vehicle",
            "ego_actor_id": 1, "intersecting_highway_id": "synthetic-highway",
            "approach_roadway_id": "synthetic-approach", "source_review_status": "diagnostic_only",
            "stopping_required_for_safety": "no" if tag == "no_safety_stop_required" else "yes",
            "safety_necessity_source": "synthetic diagnostic context only; original independent safety review required",
            "nearest_crosswalk_position": [-5, 0] if tag == "nearest_crosswalk_stop" else None,
            "marked_stop_line_position": [-3, 0] if tag == "marked_line_stop" else None,
            "intersecting_highway_boundary_x": 0, "approaching_traffic_points": [[2, 6]],
            "occluders": [[-4, 1, -3, 3]], "driver_viewpoint_candidates": [
                {"id": "far", "position": [-6, 0]}, {"id": "near", "position": [-1, 0]}],
            "earlier_obscured_stop_position": [-6, 0], "fixture_only": True}
        site_text = json.dumps(site, sort_keys=True) + "\n"
        frame_map = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
        rows = []
        for mapped in frame_map:
            index = mapped["video_frame"]
            x = (-5 if tag == "nearest_crosswalk_stop" else -3 if tag == "marked_line_stop"
                 else -6 if tag == "fallback_earlier_obscured_stop" else -1)
            x += (index - 4) * .08
            speed = 2 if tag == "no_safety_stop_required" else 0 if 3 <= index <= 5 else 2
            rows.append({"frame": mapped["carla_frame"], "time_s": mapped["time_s"],
                "ego_actor_id": 1, "ego_center_xy_m": [x, 0], "ego_speed_mps": speed,
                "ego_vertices": [[x+dx,dy,z] for z in (-.4,.4) for dx in (-.4,.4) for dy in (-.4,.4)],
                "yield_control_readback": {"yield_sign_id": "synthetic-yield", "control": "yield_sign"},
                "camera_frames": {}})
        trace_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
        receipt = {"assignment_id": ROOT.name, "case_id": cid, "diagnostic_fixture": True,
            "fps": 20, "frame_count": len(rows), "ego_actor_id": 1,
            "site_sha256": sha(site_text.encode()), "trace_sha256": sha(trace_text.encode()),
            "camera_capture_complete": False, "camera_sources": {}}
        files["original-yield-site.json"] = site_text
        files["original-yield-trace.jsonl"] = trace_text
        files["original-yield-receipt.json"] = json.dumps(receipt, sort_keys=True) + "\n"
        files["fixture-provenance.json"] = json.dumps({"scope": "CPU diagnostic only; no original driver sight, physical stopping or safety verdict",
            "case_id": cid, "frames": len(rows)}, sort_keys=True) + "\n"
        diagnostic_path = folder / "diagnostic.json"
        folder.mkdir(parents=True, exist_ok=True)
        diagnostic_path.write_text(json.dumps(diagnostic, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
        rel = diagnostic_path.relative_to(REPO).as_posix()
        write(folder / "fixture-recipe.json", {"format": "worker-fixture-recipe",
            "sources": [{"path": "diagnostic-input.json", "source": rel,
                         "sha256": sha(diagnostic_path.read_bytes())}],
            "generator": {"source": rel, "sha256": sha(diagnostic_path.read_bytes())}})
        write(folder / "measurement-contract.json", {"format": "worker-measurement-contract",
            "case_id": cid, "requirements": [
                {"disposition_index": index, "requirement": req, "source": source,
                 "output_key": key, "method": method, "value_type": "object", "kind": kind,
                 "inputs": ["original-yield-site.json", "original-yield-trace.jsonl", "original-yield-receipt.json"]}
                for index, (req, source, key, method, kind) in enumerate(REQUIREMENTS)],
            "negative": {"remove": ["original-yield-site.json"],
                         "error_contains": "Missing required source: original-yield-site.json"}})
    return len(plan["cases"])


if __name__ == "__main__":
    print(build())
