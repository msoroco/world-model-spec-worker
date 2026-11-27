"""Build exact primary and same-case fallback Native bundles."""

import json
from pathlib import Path

from case_specs import CASES

FOLDER = Path(__file__).resolve().parents[1]
NATIVE = FOLDER / "native"
ASSIGNMENT = "training__C150660__NRS-484B-450-1h__motor_vehicle_driver"
LAW = "NRS-484B-450-1h"
CAMERAS = [
    {"name": "overview", "width": 1920, "height": 1080, "fov_deg": 85,
     "pose_strategy": "surveyed_world"},
    {"name": "approach", "width": 1280, "height": 720, "fov_deg": 85,
     "pose_strategy": "surveyed_world"},
    {"name": "reference_corner", "width": 1280, "height": 720, "fov_deg": 85,
     "pose_strategy": "surveyed_world"},
    {"name": "driver_reference", "width": 1280, "height": 720, "fov_deg": 85,
     "pose_strategy": "ego_attached"},
]
CHANNELS = [
    ("drv.standing_or_parked", "boolean proxy", "Native 20 Hz velocity and stop control"),
    ("st.safety_zone", "source geometry", "authored and Native map plus independent zone designation review"),
    ("st.road_edge", "m", "Native shoulder edge and independent curb review"),
    ("rel.occupies", "boolean geometry", "four-corner body footprint between zone and curb"),
    ("rel.centre_distance", "m", "footprint distance to both opposite curb-end points"),
    ("kin.position", "m", "original Native four-corner body footprint"),
    ("drv.forced_halt", "review source", "original traffic-conflict and halt-purpose review"),
    ("dev.human_direction", "review source", "original officer-direction review"),
    ("exception_context", "review source", "original law, traffic, officer and device review"),
]
DESCRIPTION = {
    "channels": [{"name": name, "unit": unit, "method": method,
                  "reference_frame": "authored one-way road with original Native map readback",
                  "sampling_rate_hz": 20, "time_window": "600 frames / 30 s",
                  "uncertainty": "50 ms sampling; geometry tolerance is engineering only"}
                 for name, unit, method in CHANNELS],
    "context_inputs": [],
    "limitations": [
        "Requested position is not realized distance; measure original footprint",
        "Authored markers do not establish an official safety zone or adjacent curb",
        "Every statutory exception and actual camera pixels require independent original-source review",
        "CPU fixtures do not establish physical or legal acceptance",
    ],
}
TEST = '''import json
import unittest
from pathlib import Path
import road
import runner
from case_specs import CASES, target_x

class BundleTest(unittest.TestCase):
    def test_exact_zone_and_capture(self):
        cfg = json.loads(Path("config.json").read_text())
        self.assertTrue(road.check()["passed"])
        self.assertTrue(runner.check()["passed"])
        self.assertEqual(cfg["selected_case_id"], cfg["case_id"])
        self.assertEqual(len(cfg["cameras"]), 4)
        self.assertEqual(cfg["frames"], 600)
        self.assertEqual(cfg["rate_hz"], 20)
        self.assertIn(cfg["case_id"][len(cfg["assignment_id"]) + 2:], CASES)

    def test_boundary_and_candidate_invariants(self):
        self.assertLess(target_x("start_35"), target_x("start_30"))
        self.assertLess(target_x("end_30"), target_x("end_35"))
        cfg = json.loads(Path("config.json").read_text())
        self.assertIn(cfg["brake_lead_seconds"], (1.4, 2.0))
'''


def build(suffix, candidate):
    case_id = ASSIGNMENT + "__" + suffix
    position, activity, exception, gap_ft = CASES[suffix]
    config = {
        "assignment_id": ASSIGNMENT, "cell_id": "C150660", "law_id": LAW,
        "actor": "motor_vehicle_driver", "case_id": case_id,
        "selected_case_id": case_id,
        "supported_case_ids": [ASSIGNMENT + "__" + key for key in CASES],
        "frozen_cell": {"layout": "one_way_road", "maneuver": "stop_stand",
                        "control": "safety_zone"},
        "candidate_id": candidate, "rate_hz": 20, "frames": 600,
        "duration_s": 30, "cameras": CAMERAS, "required_atoms": [],
        "source_packets": [], "position_request": position,
        "activity_request": activity, "exception_request": exception,
        "requested_curb_end_gap_ft": gap_ft,
        "brake_lead_seconds": 1.4 if candidate == "primary" else 2.0,
        "recording_description": DESCRIPTION,
        "legal_verdict": None, "physical_acceptance_claimed": False,
    }
    files = [{"path": name, "content": (NATIVE / name).read_text()}
             for name in ("runner.py", "road.py", "case_specs.py",
                          "safety_zone_geometry.py", "finalize.py")]
    files.extend([{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                  {"path": "tests/test_bundle.py", "content": TEST}])
    construction = {
        "format": "worker-construction", "assignment_id": ASSIGNMENT,
        "case_id": case_id, "law_id": LAW, "cell_id": "C150660",
        "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
        "files": files, "recording_description": DESCRIPTION,
        "measurement_plan": {"method": "original Native stopped footprint to sourced safety-zone/curb geometry",
                             "requested_position": position,
                             "requested_curb_end_gap_ft": gap_ft,
                             "statutory_boundary_ft": 30,
                             "statutory_boundary_m": 9.144,
                             "legal_tolerance_claimed": False},
        "static_checks": ["authored one-way road, refuge markers and shoulder",
                          "Native map and original curb/zone source readback",
                          "600 synchronized 20 Hz four-camera frames"],
        "termination_rules": ["600 original frames", "abort on wrong exact case",
                              "abort on missing camera/source frame",
                              "restore original Native world before sealing"],
        "mechanisms": ["authored OpenDRIVE roadside refuge and curb-edge request",
                       "Native four-corner footprint and 20 Hz stop trace",
                       "position-targeted braking with same-case fallback brake lead",
                       "independent original-source designation and exception review"],
    }
    directory = FOLDER / "cases" / suffix / ("fallback1" if candidate != "primary" else "primary")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "construction.json"
    path.write_text(json.dumps(construction, indent=2) + "\n")
    return path, construction


if __name__ == "__main__":
    for suffix in CASES:
        for candidate in ("primary", "fallback1"):
            path, construction = build(suffix, candidate)
            print(path.relative_to(FOLDER))
            if suffix == "selected_6214a61f__condition_a" and candidate == "primary":
                (FOLDER / "construction.json").write_text(path.read_text())
                for name in ("runner.py", "config.json"):
                    entry = next(item for item in construction["files"] if item["path"] == name)
                    (FOLDER / name).write_text(entry["content"])
