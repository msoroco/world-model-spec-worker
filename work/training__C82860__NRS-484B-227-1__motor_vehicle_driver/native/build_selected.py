"""Build exact C82860 U-turn delivery constructions and spawn-risk fallbacks."""

import hashlib
import json
from pathlib import Path

from road_request import CAMERAS, request

PKG = Path(__file__).resolve().parents[1]
NATIVE = Path(__file__).resolve().parent
ASSIGNMENT = PKG.name
CASES = ("authorized_opening", "barrier_crossing")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(suffix, candidate="primary"):
    if suffix not in CASES or candidate not in ("primary", "fallback1"):
        raise ValueError("Unknown divided-road U-turn candidate")
    case_id = ASSIGNMENT + "__" + suffix
    bundle = NATIVE / "bundles" / suffix
    bundle.mkdir(parents=True, exist_ok=True)
    assignment = Path("inputs") / ASSIGNMENT / "assignment.json"
    req = request(suffix)
    request_text = json.dumps(req, indent=2) + "\n"
    camera_strategy = {
        "overview": "fixed_divided_road_overview",
        "approach": "ego_attached_forward_turn",
        "median_reference": "fixed_median_reference",
        "driver_reference": "fixed_opposing_roadway",
    }
    config = {
        "case_id": case_id, "selected_case_id": case_id,
        "case": {"case_id": case_id}, "candidate_id": candidate,
        "cell_id": "C82860", "law_id": "NRS-484B-227-1",
        "actor": "motor_vehicle_driver",
        "assignment_sha256": sha(assignment.read_bytes()),
        "law_text": json.loads(assignment.read_text())["law"]["text"],
        "rate_hz": 20, "duration_s": 30, "frames": 600,
        "spawn_z_m": 1.5 if candidate == "primary" else 1.8,
        "source_kind": "synthetic_scene_request", "native_observed": False,
        "physical_completion": {
            "criterion": "turn", "motion_source": "body_history.jsonl",
            "body_key": "body_vertices_m", "heading_key": "heading_deg",
            "turn_degrees": 180, "turn_tolerance_deg": 30,
            "minimum_progress_m": 8.0,
            "completion_goal_method": "Original 180-degree U-turn body and heading history; engineering milestone, not a statutory outcome",
        },
        "required_atoms": [], "source_packets": [],
        "cameras": [{"name": name, "width": width, "height": height,
                     "fov_deg": 85, "pose_strategy": camera_strategy[name]}
                    for name, width, height in CAMERAS],
        "supported_case_ids": [case_id],
        "case_target": {"physical_target": suffix,
                        "crossing_x_m": req["requested_crossing_x_m"],
                        "authority_establishment": "pending_original_source"},
        "request_sha256": sha(request_text.encode()),
    }
    files = [
        {"path": "assignment-source.json", "source": str(assignment),
         "content": assignment.read_text()},
        {"path": "request.json", "content": request_text},
        {"path": "road.xodr", "content": req["source_map"]},
        {"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
    ]
    for name, source in (
        ("road_request.py", NATIVE / "road_request.py"),
        ("runner.py", NATIVE / "runner.py"),
        ("finalize.py", NATIVE / "finalize.py"),
        ("measure_uturn.py", NATIVE / "measure_uturn.py"),
        ("analysis/divided_road.py", PKG / "analysis/divided_road.py"),
        ("tests/test_bundle.py", NATIVE / "test_bundle.py"),
    ):
        files.append({"path": name, "source": str(source.relative_to(Path.cwd())),
                      "content": source.read_text()})
    description = {
        "channels": [{"name": name, "unit": "structured", "method": method,
                      "sampling_rate_hz": 20, "time_window": "600 frames",
                      "reference_frame": "Native divided roadways 828601 and 828602",
                      "uncertainty": "Original body, median, roadway and authority review pending"}
                     for name, method in (
                         ("ego_pose", "original Native transform and body vertices"),
                         ("median_crossing_location", "saved body polygon against original median and roadway readback"),
                     )],
        "context_inputs": [],
        "limitations": ["An authored median gap does not prove public authority.",
                        "Original motion and four-camera pixels require source review."],
    }
    construction = {
        "case_id": case_id, "cell_id": "C82860",
        "law_id": "NRS-484B-227-1", "actor": "motor_vehicle_driver",
        "entrypoint": "runner.py", "files": files,
        "recording_description": description,
        "status": "selected_native_draft",
        "measurement_plan": {"metric": "600-frame full-body median, opening and roadway overlap",
                             "window": "all driven frames and crossing event",
                             "source_review_required": True},
        "static_checks": ["opposing right-hand roadways", "two physical median sections",
                          "600-frame U-turn request", "four synchronized camera sources"],
        "termination_rules": ["600 frames", "original capture seal and world restoration"],
        "mechanisms": ["CARLA Native OpenDRIVE map", "median object readback",
                       "source-bound steering and full-body capture"],
    }
    path = bundle / ("construction.json" if candidate == "primary" else "fallback1.json")
    path.write_text(json.dumps(construction, indent=2) + "\n")
    return {"case_id": case_id, "candidate_id": candidate,
            "construction": str(path.relative_to(PKG)),
            "construction_sha256": sha(path.read_bytes()), "kind": "delivery"}


if __name__ == "__main__":
    print(json.dumps([build(suffix, candidate) for suffix in CASES
                      for candidate in ("primary", "fallback1")], indent=2))
