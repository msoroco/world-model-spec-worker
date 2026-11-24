"""Build exact median-opening precedence diagnostic bundles without source claims."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
CAMERAS = ("front", "rear", "left", "right")
SUFFIXES = ("precedence", "advance")

RUNNER = '''"""Check one exact median-opening diagnostic bundle."""
import argparse
import hashlib
import json
from pathlib import Path


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    raw = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact median-opening case plan changed")
    plan = json.loads(raw)
    case = config["selected_case_id"]
    if case not in {config["assignment_id"] + "__precedence",
                    config["assignment_id"] + "__advance"}:
        raise ValueError("Foreign median-opening case")
    matches = [row for row in plan["cases"] if row["case_id"] == case]
    if len(matches) != 1 or plan["cell_id"] != "C125697":
        raise ValueError("Exact median-opening case absent")
    if (config["law_id"] != "NRS-484B-250-1" or
            config["actor"] != "motor_vehicle_driver" or
            config["crossing_kind"] != "median_opening_roadway_crossing" or
            config["governing_signal_state"] != "inoperative"):
        raise ValueError("Statutory crossing or governing signal contract changed")
    if (config["rate_hz"] != 20 or config["frame_count"] != 900 or
            config["duration_s"] != 45 or
            config["cameras"] != ["front", "rear", "left", "right"]):
        raise ValueError("Original source capture contract changed")
    if config["required_sources"] != ["native_trace", "opendrive", "device_inventory",
                                       "camera_front", "camera_rear", "camera_left",
                                       "camera_right"]:
        raise ValueError("Original median-opening source contract changed")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic median-opening bundle passed: " + case)
        return
    raise ValueError("Reviewed original roadway crossing, governing signal and Native sources required")


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
    if len(cases) != 2 or {row["case_id"] for row in cases} != {
            AID + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("two exact median-opening cases required")
    rows = []
    for item in cases:
        case = item["case_id"]
        suffix = case.removeprefix(AID + "__")
        config = {
            "assignment_id": AID, "law_id": "NRS-484B-250-1",
            "cell_id": "C125697", "actor": "motor_vehicle_driver",
            "selected_case_id": case, "plan_sha256": hashlib.sha256(raw).hexdigest(),
            "crossing_kind": "median_opening_roadway_crossing",
            "governing_signal_state": "inoperative",
            "requested_ego_response": "yield_before_entry" if suffix == "precedence" else "advance_before_other_exit",
            "rate_hz": 20, "frame_count": 900, "duration_s": 45,
            "cameras": list(CAMERAS), "required_atoms": [],
            "required_sources": ["native_trace", "opendrive", "device_inventory",
                                 "camera_front", "camera_rear", "camera_left", "camera_right"],
            "diagnostic_only": True,
        }
        files = {"runner.py": RUNNER, "median_opening.py": (HERE / "median_opening.py").read_text(),
                 "case-plan.json": raw.decode(), "config.json": json.dumps(config, indent=2) + "\n",
                 "tests/test_bundle.py": TEST}
        construction = {
            "law_id": config["law_id"], "cell_id": config["cell_id"],
            "actor": config["actor"], "case_id": case,
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": {"status": "diagnostic_only_original_sources_pending",
                                      "channels": list(CAMERAS)},
            "files": [{"path": name, "content": body} for name, body in files.items()],
        }
        path = HERE / ("construction-" + suffix + ".json")
        path.write_text(json.dumps(construction, indent=2) + "\n")
        rows.append({"case_id": case, "construction": path.name,
                     "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "candidate_risk": {"status": "physical",
                         "reason": item["physical_risk"]["risk"]}})
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({
        "assignment_id": AID, "status": "diagnostic_offline_only_original_sources_pending",
        "cases": rows}, indent=2) + "\n")
    print("built two exact median-opening diagnostic constructions")


if __name__ == "__main__":
    build()
