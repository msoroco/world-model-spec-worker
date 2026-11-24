"""Build five exact diagnostic sidewalk-bypass constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SOURCE_FILES = (
    "geometry.py", "native_construction.py", "native_walking.py", "native_source_packet.py",
    "native_readback.py", "native_camera_capture.py", "native_attempt.py",
    "saved_measurement.py", "delivery_audit.py", "comparison_audit.py",
)

RUNNER = '''"""Exact sidewalk-bypass diagnostic bundle entrypoint."""
import argparse
import hashlib
import json
from pathlib import Path
from geometry import construct, audit_design
from native_walking import FPS


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    plan_data = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(plan_data).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact case plan changed")
    case = config["selected_case_id"]
    entries = [x for x in json.loads(plan_data)["cases"] if x["case_id"] == case]
    if len(entries) != 1 or not case.startswith(config["assignment_id"] + "__"):
        raise ValueError("Exact case missing")
    if config["construction_parameters"] != entries[0]["construction_parameters"]:
        raise ValueError("Case parameters changed")
    if config["rate_hz"] != FPS or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("Original frame contract changed")
    if config["cameras"] != ["overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("Four-camera contract changed")
    p = config["construction_parameters"]
    scene = construct(case, direction=p["direction"], area_blocked=p["area_blocked"],
                      sidewalk_end=float(p["sidewalk_end_m"]), obstruction_kind=p["obstruction_kind"])
    result = audit_design(scene)
    if result["designated_lane_used"] != p["area_blocked"]:
        raise ValueError("Bicycle-lane condition changed")
    if p["obstruction_kind"] == "missing_section" and not scene.missing_sections:
        raise ValueError("Missing sidewalk surface not constructed")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic sidewalk-bypass bundle passed: " + case)
        return
    raise ValueError("Surveyed Native sidewalk, bicycle lane, local transform and original walker capture required")


if __name__ == "__main__":
    main()
'''

TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_constructed_geometry(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_refuses_unsurveyed_native_capture(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Surveyed Native sidewalk"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
'''


def build():
    plan_data = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(plan_data)
    rows = []
    for item in plan["cases"]:
        case = item["case_id"]
        if not case.startswith(AID + "__"):
            raise ValueError("Foreign case")
        suffix = case.removeprefix(AID + "__")
        config = {
            "assignment_id": AID, "law_id": "NRS-484B-297-6", "cell_id": "C104081",
            "actor": "pedestrian", "selected_case_id": case,
            "plan_sha256": hashlib.sha256(plan_data).hexdigest(),
            "construction_parameters": item["construction_parameters"],
            "rate_hz": 20, "frame_count": 900, "duration_s": 45,
            "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
            "required_atoms": [], "diagnostic_only": True,
        }
        files = {name: (HERE / name).read_text() for name in SOURCE_FILES}
        files.update({"runner.py": RUNNER, "case-plan.json": plan_data.decode(),
                      "config.json": json.dumps(config, indent=2) + "\n",
                      "tests/test_bundle.py": TEST})
        construction = {
            "law_id": config["law_id"], "cell_id": config["cell_id"],
            "actor": config["actor"], "case_id": case,
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": {"status": "diagnostic_only_survey_pending", "channels": config["cameras"]},
            "files": [{"path": path, "content": content} for path, content in files.items()],
        }
        output = HERE / ("construction-" + suffix + ".json")
        output.write_text(json.dumps(construction, indent=2) + "\n")
        rows.append({"case_id": case, "construction": output.name,
                     "construction_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                     "candidate_risk": {"status": "physical", "reason": item["physical_risk_assessment"]["risk"]}})
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({
        "assignment_id": AID, "status": "diagnostic_offline_only_original_survey_pending", "cases": rows,
    }, indent=2) + "\n")
    print("built", len(rows), "exact sidewalk-bypass diagnostic constructions")


if __name__ == "__main__":
    build()
