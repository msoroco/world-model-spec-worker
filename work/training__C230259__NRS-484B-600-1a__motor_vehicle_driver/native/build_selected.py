"""Build four exact Native speed-condition constructions from one source policy."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name
SPEEDS = (8, 12, 16, 20)
CAMERAS = (
    ("overview", 1920, 1080, "surveyed_world"),
    ("approach", 1280, 720, "surveyed_world"),
    ("reference_corner", 1280, 720, "surveyed_world"),
    ("driver_reference", 1280, 720, "ego_attached"),
)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def recording():
    specs = (
        ("ego_pose", "m", "Native post-tick vehicle pose and original trace"),
        ("measured_speed", "m/s", "Norm of original three-axis Native vehicle velocity"),
        ("speed_conditions", "structured", "Frame-joined original traffic, lane, surface and weather sources"),
    )
    return {"channels": [{"name": name, "unit": unit, "method": method,
                          "sampling_rate_hz": 20, "time_window": "600 frames / 30 s",
                          "reference_frame": "C230259 surveyed Native road and source frame",
                          "uncertainty": "50 ms samples; actual material, visibility and legal judgment pending"}
                         for name, unit, method in specs],
            "context_inputs": [{"name": "four_source_cameras", "unit": "video",
                                "method": "Native camera frame IDs and full source decode"}],
            "limitations": ["Controller request is not measured speed or a legal threshold",
                            "Surface material and legal reasonableness require independent review"]}


def build():
    selected = [AID + "__" + str(speed) for speed in SPEEDS]
    description = recording()
    text = {"runner.py": (ROOT / "native/runner.py").read_text(),
            "road.py": (ROOT / "native/road.py").read_text(),
            "conditions_source_v2.py": (ROOT / "analysis/conditions_source_v2.py").read_text(),
            "finalize.py": (ROOT / "native/finalize.py").read_text(),
            "tests/test_bundle.py": (ROOT / "native/test_bundle.py").read_text()}
    for speed, case_id in zip(SPEEDS, selected):
        config = {"assignment_id": AID, "case_id": case_id,
                  "selected_case_id": case_id, "supported_case_ids": selected,
                  "law_id": "NRS-484B-600-1a", "cell_id": "C230259",
                  "actor": "motor_vehicle_driver", "candidate_id": "primary",
                  "requested_speed_mps": speed, "rate_hz": 20, "frames": 600,
                  "duration_s": 30, "required_atoms": [], "source_packets": [],
                  "legal_verdict": None, "physical_acceptance_claimed": False,
                  "cameras": [{"name": name, "width": width, "height": height,
                               "pose_strategy": pose, "fov_deg": 85}
                              for name, width, height, pose in CAMERAS],
                  "recording_description": description}
        contents = dict(text)
        contents["config.json"] = json.dumps(config, indent=2, sort_keys=True) + "\n"
        construction = {"format": "worker-construction", "assignment_id": AID,
                        "case_id": case_id, "law_id": "NRS-484B-600-1a",
                        "cell_id": "C230259", "actor": "motor_vehicle_driver",
                        "entrypoint": "runner.py", "files": [{"path": path, "content": value}
                                                          for path, value in contents.items()],
                        "recording_description": description,
                        "measurement_plan": {"method": "source-joined original Native speed and named conditions",
                                             "requested_speed_mps": speed,
                                             "legal_threshold_claimed": False},
                        "mechanisms": ["generated two-lane OpenDRIVE corridor",
                                       "separate other-vehicle actor and fixed traffic setup",
                                       "Native velocity feedback controller and four synchronized cameras"],
                        "static_checks": ["two distinct Native vehicles", "1,800 m connected corridor",
                                          "20 Hz four-view source capture"],
                        "termination_rules": ["600 original frames", "abort on lane departure",
                                              "abort on source camera frame mismatch"]}
        write(ROOT / "native" / f"{speed}-construction.json", construction)
    offline = {"assignment_id": AID, "cases": []}
    for speed, case_id in zip(SPEEDS, selected):
        path = ROOT / "native" / f"{speed}-construction.json"
        offline["cases"].append({"case_id": case_id, "construction": path.name,
                                 "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                 "candidate_risk": {"status": "none",
                                    "reason": "The 1,800 m corridor exceeds maximum requested 600 m travel; no specific additional physical failure is identified before Native capture."},
                                 "candidates": []})
    write(ROOT / "native/selected-offline-manifest.json", offline)
    return selected


if __name__ == "__main__":
    print(json.dumps({"selected_cases": build()}))
