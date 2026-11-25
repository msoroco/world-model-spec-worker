"""Build four exact median-opening timing diagnostic bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SUFFIXES = ("timing_below_training", "timing_inside_training",
            "timing_above_training", "right_approach_inside")

RUNNER = '''"""Check one exact median-opening diagnostic bundle."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import median_source
import native_capture


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    raw = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact median-opening case plan changed")
    plan = json.loads(raw)
    case = config["selected_case_id"]
    if case not in {config["assignment_id"] + "__" + suffix for suffix in
                    ("timing_below_training", "timing_inside_training",
                     "timing_above_training", "right_approach_inside")}:
        raise ValueError("Foreign median-opening case")
    matches = [row for row in plan["cases"] if row["case_id"] == case]
    if len(matches) != 1 or plan["cell_id"] != "C125697":
        raise ValueError("Exact median-opening case absent")
    if (config["law_id"] != "NRS-484B-250-2" or
            config["actor"] != "motor_vehicle_driver" or
            config["crossing_kind"] != "median_opening_roadway_crossing" or
            config["governing_signal_state"] != "inoperative"):
        raise ValueError("Statutory crossing or governing signal contract changed")
    if (config["requested_entry_offset_s"] != matches[0]["planned_entry_time_difference_s"] or
            config["ego_approach_side"] != matches[0]["ego_approach_side"]):
        raise ValueError("Exact-case timing or approach request changed")
    if (config["rate_hz"] != 20 or config["frame_count"] != 900 or
            config["duration_s"] != 45 or
            [camera["name"] for camera in config["cameras"]] !=
            ["overview", "approach", "reference_corner", "driver_reference"]):
        raise ValueError("Original source capture contract changed")
    if config["required_sources"] != ["native_trace", "opendrive", "device_inventory",
                                       "highway_identity",
                                       "camera_overview", "camera_approach", "camera_reference_corner",
                                       "camera_driver_reference"]:
        raise ValueError("Original median-opening source contract changed")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--packet", default=os.environ.get("C125697_REVIEWED_PACKET"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic median-opening bundle passed: " + case)
        return
    if not args.output_dir or not args.packet:
        raise ValueError("Reviewed original roadway crossing, governing signal and Native sources required")
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    config = json.loads((Path(__file__).resolve().parent / "config.json").read_text())
    print(json.dumps(native_capture.run(
        client.get_world(), carla, args.packet, args.output_dir, case,
        config["requested_entry_offset_s"], config["ego_approach_side"]), sort_keys=True))


if __name__ == "__main__":
    main()
'''

TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case_and_source_contract(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "config.json").read_text())
        self.assertEqual(runner.check(), config["selected_case_id"])

    def test_refuses_unsourced_native_launch(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Reviewed original roadway crossing"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
'''


def build():
    raw = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(raw)
    cases = plan["cases"]
    if len(cases) != 4 or {row["case_id"] for row in cases} != {
            AID + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("two exact median-opening cases required")
    rows = []
    for item in cases:
        case = item["case_id"]
        suffix = case.removeprefix(AID + "__")
        config = {
            "assignment_id": AID, "law_id": "NRS-484B-250-2",
            "cell_id": "C125697", "actor": "motor_vehicle_driver",
            "selected_case_id": case, "plan_sha256": hashlib.sha256(raw).hexdigest(),
            "crossing_kind": "median_opening_roadway_crossing",
            "governing_signal_state": "inoperative",
            "requested_entry_offset_s": item["planned_entry_time_difference_s"],
            "ego_approach_side": item["ego_approach_side"],
            "physical_completion": {
                "criterion": "intersection_clearance",
                "motion_source": "crossing_history.jsonl",
                "body_key": "ego_vertices_m",
                "context_sources": ["crossing_geometry.json"],
                "exit_axis": 0 if item["ego_approach_side"] == "right" else 1,
                "exit_sign": 1,
                "minimum_progress_m": 1.0,
                "engineering_tolerances_not_legal": True,
            },
            "rate_hz": 20, "frame_count": 900, "duration_s": 45,
            "cameras": [
                {"name": "overview", "width": 1920, "height": 1080,
                 "pose_strategy": "fixed reviewed crossing view", "fov_deg": 90},
                {"name": "approach", "width": 1280, "height": 720,
                 "pose_strategy": "fixed reviewed crossing view", "fov_deg": 90},
                {"name": "reference_corner", "width": 1280, "height": 720,
                 "pose_strategy": "fixed reviewed crossing view", "fov_deg": 90},
                {"name": "driver_reference", "width": 1280, "height": 720,
                 "pose_strategy": "ego mounted", "fov_deg": 90}],
            "required_atoms": [],
            "required_sources": ["native_trace", "opendrive", "device_inventory",
                                 "highway_identity",
                                 "camera_overview", "camera_approach", "camera_reference_corner",
                                 "camera_driver_reference"],
            "diagnostic_only": True,
        }
        files = {"runner.py": RUNNER, "median_source.py": (HERE / "median_source.py").read_text(),
                 "native_capture.py": (HERE / "native_capture.py").read_text(),
                 "entry_timing.py": (HERE / "entry_timing.py").read_text(),
                 "footprint_capture.py": (HERE / "footprint_capture.py").read_text(),
                 "analysis.py": (HERE / "analysis.py").read_text(),
                 "judgment-probe-plan.json": (HERE / "judgment-probe-plan.json").read_text(),
                 "case-plan.json": raw.decode(), "config.json": json.dumps(config, indent=2) + "\n",
                 "tests/test_bundle.py": TEST}
        construction = {
            "law_id": config["law_id"], "cell_id": config["cell_id"],
            "actor": config["actor"], "case_id": case,
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": item["recording_description"],
            "files": [{"path": name, "content": body} for name, body in files.items()],
        }
        path = HERE / ("construction-" + suffix + ".json")
        path.write_text(json.dumps(construction, indent=2) + "\n")
        rows.append({"case_id": case, "construction": path.name,
                     "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "candidate_risk": {"status": "physical",
                         "reason": "Median opening route association and two-vehicle release timing may fail to yield complete independent footprint entry transitions."}})
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({
        "assignment_id": AID, "status": "diagnostic_offline_only_original_sources_pending",
        "cases": rows}, indent=2) + "\n")
    print("built four exact median-opening diagnostic constructions")


if __name__ == "__main__":
    build()
