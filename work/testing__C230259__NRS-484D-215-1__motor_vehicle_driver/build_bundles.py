"""Materialize eight exact source-bound Native construction bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PLAN_PATH = ROOT / "case-plan.json"
PLAN = json.loads(PLAN_PATH.read_text())
ASSIGNMENT = PLAN["assignment_id"]
SOURCES = ("beam_measure.py", "beam_construction.py", "beam_camera.py",
           "beam_native.py", "beam_pixels.py", "beam_projection.py",
           "analysis.py", "beam_publication.py", "runner.py", "case-plan.json")
CHANNELS = (
    ("original_actor_state", "Original Native participant bodies, motion, driver-eye geometry and lamp readback"),
    ("original_four_view_frame_map", "Four RGB sensor frames joined to each original Native tick"),
    ("original_beam_pixels", "Original projected person, vehicle and oncoming-eye ROI pixel frames"),
    ("original_oncoming_distance", "Original frame-by-frame body and driver-eye separation"),
)


def _dump(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _recording_description():
    return {"channels": [{"name": name, "unit": "structured record", "method": method,
                          "sampling_rate_hz": 20,
                          "time_window": "all 900 original frames during 45-second road travel",
                          "reference_frame": "original Native world frame and synchronized camera frame",
                          "uncertainty": "20 Hz sampling, source-reviewed map/calibration and image projection precision"}
                         for name, method in CHANNELS],
            "context_inputs": [{"name": "reviewed_highway_time_lamp_and_contour",
                                "unit": "structured record",
                                "method": "source-hashed reviewed site and original Native map/clock packet"}],
            "limitations": ["CARLA lamp bits are requests and readbacks, not calibrated beam distribution.",
                            "Original RGB luma is not a legal safe-distance or glare threshold.",
                            "NRS 484D.210(2) lowermost specification requires independent source review."]}


def _config(case, description):
    cameras = []
    for name, width, height, fov in (("overview", 1920, 1080, 70),
                                     ("approach", 1280, 720, 45),
                                     ("reference_corner", 1280, 720, 65),
                                     ("driver_reference", 1280, 720, 20)):
        cameras.append({"name": name, "width": width, "height": height,
                        "fov_deg": fov, "pose_strategy": "source-reviewed Native site and original sensor transform"})
    return {"assignment_id": ASSIGNMENT, "law_id": PLAN["law_id"],
            "cell_id": PLAN["cell_id"], "actor": PLAN["actor"],
            "selected_case_id": case["case_id"],
            "supported_case_ids": [x["case_id"] for x in PLAN["cases"]],
            "case_plan": case,
            "case": {"case_id": case["case_id"], "recording_description": description},
            "plan_sha256": hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest(),
            "requested_beam": case["requested_beam"],
            "requested_speed_mps": 2.0,
            "rate_hz": 20, "frame_count": 900, "duration_s": 45,
            "camera_dimensions": {x["name"]: [x["width"], x["height"]] for x in cameras},
            "cameras": cameras, "required_atoms": [], "source_packets": [],
            "source_requirements": ["reviewed Native highway/time and map sources",
                                    "original moving actor/eye geometry",
                                    "frame-specific reviewed person/vehicle/eye pixel ROIs"],
            "diagnostic_only": False}


def _construction(case, config, description):
    files = [{"path": name, "source": (ROOT / name).relative_to(REPO).as_posix(),
              "content": (ROOT / name).read_text()} for name in SOURCES]
    files.append({"path": "config.json", "content": _dump(config)})
    files.append({"path": "tests/test_bundle.py",
                  "source": (ROOT / "bundle_test.py").relative_to(REPO).as_posix(),
                  "content": (ROOT / "bundle_test.py").read_text()})
    return {"law_id": PLAN["law_id"], "cell_id": PLAN["cell_id"],
            "actor": PLAN["actor"], "case_id": case["case_id"],
            "entrypoint": "runner.py", "files": files, "diagnostic_only": False,
            "recording_description": description,
            "measurement_plan": {"finalizer": "analysis.py",
                                 "source": "hash-sealed original Native geometry, camera pixels and reviewed site"},
            "mechanisms": ["reviewed highway, lighting-time, lamp and contour site packet",
                           "opposing moving Native vehicles and person/vehicle targets",
                           "exact requested beam and source readback",
                           "four synchronized original RGB sensors",
                           "saved-only geometry, pixel and physical completion review"],
            "static_checks": ["exact source hash and selected case",
                              "opposing routes and 500-foot engineering target",
                              "four original camera profiles and 900-frame source joins"],
            "termination_rules": ["45 seconds at 20 Hz",
                                  "fail on stale source, missing actor, pixel ROI or restoration failure"]}


def main():
    description = _recording_description()
    for index, case in enumerate(PLAN["cases"]):
        suffix = case["case_id"].split("__")[-1]
        config = _config(case, description)
        construction = _construction(case, config, description)
        if index == 0:
            (ROOT / "config.json").write_text(_dump(config))
            (ROOT / "construction.json").write_text(_dump(construction))
        folder = ROOT / "cases" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "config.json").write_text(_dump(config))
        (folder / "construction.json").write_text(_dump(construction))


if __name__ == "__main__":
    main()
