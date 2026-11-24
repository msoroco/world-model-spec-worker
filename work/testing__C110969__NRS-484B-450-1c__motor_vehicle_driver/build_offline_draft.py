"""Build exact diagnostic constructions for the intersection-stop branch."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SOURCES = (
    "intersection_observables.py", "finalize_observables.py",
    "native_acquisition.py", "native_scene.py", "native_media.py",
    "native_camera_adapter.py", "native_scene_factory.py",
    "native_capture_entrypoint.py", "native_export.py",
    "finalize_delivery.py", "analysis.py", "audit_finalized.py", "comparison_audit.py",
    "delivery_audit.py",
)

RUNNER = '''"""Exact case identity and source-profile preflight."""
import argparse
import hashlib
import json
from pathlib import Path


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("exact intersection plan source changed")
    plan = json.loads(source)
    case = config["selected_case_id"]
    if not case.startswith(config["assignment_id"] + "__"):
        raise ValueError("foreign intersection case")
    matches = [row for row in plan["cases"] if row["case_id"] == case]
    if len(matches) != 1:
        raise ValueError("exact intersection case absent")
    row = matches[0]
    for key in ("activity_intent", "body_destination", "exception_context"):
        if row[key] != config[key]:
            raise ValueError("exact intersection case intent changed: " + key)
    if config["rate_hz"] != 20 or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("original intersection interval changed")
    if config["camera_dimensions"] != {"overview": [1920, 1080], "approach": [1280, 720],
                                       "reference_corner": [1280, 720], "driver_reference": [1280, 720]}:
        raise ValueError("original four-camera profile changed")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic intersection construction passed: " + case)
        return
    if not args.output_dir:
        raise ValueError("Native attempt output directory required")
    from native_capture_entrypoint import run_from_environment
    result = run_from_environment(case, args.output_dir, args.host, args.port)
    print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
'''

TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_identity(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_unsourced_native_refused(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "reviewed Native route"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
'''


def build():
    source = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(source)
    semantic = json.loads((HERE / "proposals/cases.json").read_text())
    descriptions = {item["case_id"]: item["recording_description"]
                    for item in semantic["cases"] if item["target_type"] != "baseline"}
    rows = []
    if len(plan["cases"]) != 9:
        raise ValueError("nine exact intersection cases required")
    for item in plan["cases"]:
        case = item["case_id"]
        if not case.startswith(AID + "__"):
            raise ValueError("foreign intersection case")
        suffix = case.removeprefix(AID + "__")
        config = {
            "assignment_id": AID, "law_id": "NRS-484B-450-1c", "cell_id": "C110969",
            "actor": "motor_vehicle_driver", "selected_case_id": case,
            "activity_intent": item["activity_intent"],
            "body_destination": item["body_destination"],
            "exception_context": item["exception_context"],
            "plan_sha256": hashlib.sha256(source).hexdigest(),
            "rate_hz": 20, "frame_count": 900, "duration_s": 45,
            "camera_dimensions": {"overview": [1920, 1080], "approach": [1280, 720],
                                  "reference_corner": [1280, 720], "driver_reference": [1280, 720]},
            "source_requirements": ["reviewed_intersection_boundary", "original_trace",
                                    "original_activity", "original_camera_media"],
            "required_atoms": [], "diagnostic_only": True,
            "controller_profile": {"brake_distance_m": 2.0,
                                   "throttle_gain": 0.2,
                                   "through_speed_floor_mps": 2.0},
        }
        files = {name: (HERE / name).read_text() for name in SOURCES}
        files.update({"runner.py": RUNNER, "case-plan.json": source.decode(),
                      "config.json": json.dumps(config, indent=2) + "\n",
                      "measurement-contract.json": (HERE / "cases" / suffix / "measurement-contract.json").read_text(),
                      "tests/test_bundle.py": TEST})
        construction = {
            "law_id": config["law_id"], "cell_id": config["cell_id"],
            "actor": config["actor"], "case_id": case,
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": descriptions[case],
            "files": [{"path": path, "content": content} for path, content in files.items()],
        }
        output = HERE / ("construction-" + suffix + ".json")
        output.write_text(json.dumps(construction, indent=2) + "\n")
        rows.append({"case_id": case, "construction": output.name,
                     "construction_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                     "candidate_risk": item["risk"]})
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({
        "assignment_id": AID, "status": "diagnostic_offline_only_original_boundary_pending",
        "cases": rows,
    }, indent=2) + "\n")
    print("built", len(rows), "exact intersection diagnostic constructions")


if __name__ == "__main__":
    build()
