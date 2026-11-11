"""Freeze the first fire apparatus exact case as an inline CPU construction.

The source files stay editable until the package is finalized. Re-run this
builder after source changes, then rerun the offline and saved-source proofs.
"""
from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.name + "__traveling_follow_500ft"


def main() -> None:
    plan = json.loads((HERE / "case-plan.json").read_text())
    cameras = [
        {"name": name, "width": width, "height": height,
         "pose_strategy": "subject-mounted provisional visibility view",
         "fov_deg": 90}
        for name, width, height in (
            ("overview", 1920, 1080), ("approach", 1280, 720),
            ("reference_corner", 1280, 720),
            ("driver_reference", 1280, 720))
    ]
    recording = {
        "channels": [{"name": "fire_gap_ft", "unit": "ft",
                      "method": "ground-footprint nearest separation from retained Native corners",
                      "sampling_rate_hz": 20,
                      "time_window": "all original frames",
                      "reference_frame": "world ground plane",
                      "uncertainty": "Native vertex precision and 20 Hz temporal sampling"}],
        "context_inputs": [],
        "limitations": ["Authored dispatch purpose and authorization require source review; CPU tests do not establish physical visibility."],
    }
    config = {
        "cell_id": "C109514", "law_id": "NRS-484B-710",
        "actor": "motor_vehicle_driver", "selected_case_id": CASE,
        "supported_case_ids": [case["case_id"] for case in plan["cases"]],
        "fire_branch": "traveling_follow", "target_distance_ft": 500,
        "fire_context": {
            "alarm_response_source": "authored fire dispatch premise; verify against local Native scene record",
            "apparatus_answered_alarm": True,
            "subject_authorized_emergency": False,
            "subject_official_business": False,
        },
        "required_atoms": [], "source_packets": [],
        "rate_hz": 20, "duration_s": 8, "frames": 160,
        "cameras": cameras,
        "case": {"case_id": CASE, "recording_description": recording},
    }
    (HERE / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    names = [
        "runner.py", "intersection_route.py", "fire_camera_capture.py",
        "fire_capture_session.py", "fire_source_capture.py",
        "follow_controller.py", "fire_finalizer.py", "fire_branch.py",
        "fire_distance.py", "delivery_audit.py",
    ]
    tests = [
        "tests/test_runner.py", "tests/test_intersection_route.py",
        "tests/test_fire_capture_session.py", "tests/test_fire_finalizer.py",
    ]
    construction = {
        "format": "worker-inline-construction", "case_id": CASE,
        "cell_id": "C109514", "law_id": "NRS-484B-710",
        "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
        "files": [
            {"path": name, "content": (HERE / name).read_text()}
            for name in [*names, *tests, "config.json"]
        ],
        "measurement_plan": {
            "finalizer": "fire_finalizer.py",
            "retained_sources": ["video_frames.jsonl", "trace.jsonl",
                                 "participant_footprints.jsonl",
                                 "participant_state.jsonl", "fire_context.json"],
            "reported_boundary": "minimum active-frame full-footprint separation in feet",
        },
        "recording_description": recording,
        "static_checks": ["runner --check", "materialized CPU unit tests"],
        "termination_rules": ["160 original 20 Hz frames", "reject any missing synchronized camera/source frame"],
        "mechanisms": ["Native through-intersection route selection", "measured following feedback",
                       "four original RGB sources", "saved-only fire distance finalization"],
    }
    (HERE / "construction.json").write_text(json.dumps(construction, indent=2) + "\n")


if __name__ == "__main__":
    main()
