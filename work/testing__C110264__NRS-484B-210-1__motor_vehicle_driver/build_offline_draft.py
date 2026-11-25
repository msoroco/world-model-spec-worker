"""Build three exact right-pass diagnostic constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SOURCE_FILES = (
    "pass_right_route.py", "pass_right_live.py", "pass_right_capture.py",
    "pass_right_measure.py", "pass_right_audit.py", "pass_right_media.py",
    "pass_right_sensor.py", "pass_right_actor.py", "pass_right_session.py",
    "pass_right_control.py", "native_runner.py", "pass_right_lifecycle.py",
    "analysis.py",
)

RUNNER = '''"""Exact paragraph-(a) right-pass bundle preflight."""
import argparse
import hashlib
import json
from pathlib import Path
from pass_right_capture import CAMERAS


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact plan source changed")
    case = config["selected_case_id"]
    entries = [row for row in json.loads(source)["cases"] if row["case_id"] == case]
    if len(entries) != 1 or not case.startswith(config["assignment_id"] + "__"):
        raise ValueError("Exact case absent")
    variant = case.removeprefix(config["assignment_id"] + "__")
    if variant not in ("left_signal", "left_turn", "neither"):
        raise ValueError("Unknown exact paragraph-(a) variant")
    if entries[0]["draft_variables"]["controller"]["target"] != variant or config["target_behavior_request"] != variant:
        raise ValueError("Target request changed")
    if config["rate_hz"] != 20 or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("Original timebase changed")
    if config["native_cameras"] != list(CAMERAS):
        raise ValueError("Original four-camera profile changed")
    if [(item["name"], item["width"], item["height"]) for item in config["cameras"]] != [
            ("overview", 1920, 1080), ("approach", 1280, 720),
            ("reference_corner", 1280, 720), ("driver_reference", 1280, 720)]:
        raise ValueError("Canonical four-view profile changed")
    if config["required_sources"] != ["reviewed_map", "ego_target_trace", "frame_map", "original_camera_media"]:
        raise ValueError("Original source requirements changed")
    if config["native_setup_role"] not in ("primary", "fallback1"):
        raise ValueError("Unknown reviewed Native setup role")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic right-pass bundle passed: " + case)
        return
    raise ValueError("Reviewed Native paved corridor, actor motion and original camera capture required")


if __name__ == "__main__":
    main()
'''

TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case_preflight(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_refuses_unsourced_native_capture(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Reviewed Native paved corridor"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
'''


def build():
    source = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(source)
    rows = []
    for item in plan["cases"]:
        case = item["case_id"]
        if not case.startswith(AID + "__"):
            raise ValueError("Foreign case")
        suffix = case.removeprefix(AID + "__")
        config = {
            "assignment_id": AID, "law_id": "NRS-484B-210-1", "cell_id": "C110264",
            "actor": "motor_vehicle_driver", "selected_case_id": case,
            "recording_description": item["recording_description"],
            "supported_case_ids": [row["case_id"] for row in plan["cases"]],
            "plan_sha256": hashlib.sha256(source).hexdigest(),
            "target_behavior_request": item["draft_variables"]["controller"]["target"],
            "rate_hz": 20, "frame_count": 900, "duration_s": 45,
            "cameras": [{"name": name, "width": width, "height": height,
                         "fov_deg": 75,
                         "pose_strategy": "source-reviewed intersection, target and right-pass visibility"}
                        for name, width, height in (("overview", 1920, 1080),
                                                    ("approach", 1280, 720),
                                                    ("reference_corner", 1280, 720),
                                                    ("driver_reference", 1280, 720))],
            "native_cameras": ["front", "rear", "left", "right"],
            "required_sources": ["reviewed_map", "ego_target_trace", "frame_map", "original_camera_media"],
            "required_atoms": [], "diagnostic_only": True,
            "native_setup_role": "primary",
            "physical_completion": {"criterion": "overtake_pass",
                                    "motion_source": "pass_history.jsonl",
                                    "body_key": "ego_vertices_m",
                                    "other_body_key": "target_vertices_m",
                                    "lateral_transition_m": 0,
                                    "minimum_progress_m": 10,
                                    "completion_goal_method": "Engineering source-bound longitudinal order reversal and sampled 10 m progress; independent paved/intersection audit required, not a legal cutoff."},
        }
        files = {name: (HERE / name).read_text() for name in SOURCE_FILES}
        files.update({"runner.py": RUNNER, "case-plan.json": source.decode(),
                      "config.json": json.dumps(config, indent=2) + "\n",
                      "tests/test_bundle.py": TEST})
        construction = {
            "law_id": config["law_id"], "cell_id": config["cell_id"],
            "actor": config["actor"], "case_id": case,
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": item["recording_description"],
            "files": [{"path": path, "content": content} for path, content in files.items()],
        }
        output = HERE / ("construction-" + suffix + ".json")
        output.write_text(json.dumps(construction, indent=2) + "\n")
        rows.append({"case_id": case, "construction": output.name,
                     "construction_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                     "candidate_risk": item["physical_risk_assessment"]})
        fallback_config = {**config, "native_setup_role": "fallback1"}
        fallback_files = dict(files)
        fallback_files["config.json"] = json.dumps(fallback_config, indent=2) + "\n"
        fallback = {**construction, "files": [{"path": path, "content": content}
                                              for path, content in fallback_files.items()]}
        fallback_output = HERE / ("fallback1-construction-" + suffix + ".json")
        fallback_output.write_text(json.dumps(fallback, indent=2) + "\n")
        rows[-1]["candidates"] = [{
            "id": "fallback1", "construction": fallback_output.name,
            "construction_sha256": hashlib.sha256(fallback_output.read_bytes()).hexdigest(),
            "trigger": {"source": "original-attempt/native/capture-receipt.json",
                        "metric": "source-confirmed paved right corridor and actor spawn clearance",
                        "failure_condition": "primary reviewed spawn locations fail Native placement or paved-clearance readback"},
            "changed_knobs": ["native_setup_role=fallback1",
                              "independently reviewed alternate actor starts and camera mounts"]}]
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({
        "assignment_id": AID, "status": "diagnostic_offline_only_original_sources_pending", "cases": rows,
    }, indent=2) + "\n")
    print("built", len(rows), "exact right-pass diagnostic constructions")


if __name__ == "__main__":
    build()
