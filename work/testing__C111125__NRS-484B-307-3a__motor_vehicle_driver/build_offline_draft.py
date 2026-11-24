"""Build exact, source-bound diagnostic bundles for the four dual-green cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT = "testing__C111125__NRS-484B-307-3a__motor_vehicle_driver"
SUFFIXES = ("dual_clear", "dual_vehicle_present", "dual_pedestrian_present",
            "dual_pedestrian_late")
SOURCES = ("dual_green.py", "native_attempt.py", "native_straight_controller.py",
           "native_other_controller.py", "native_cameras.py",
           "saved_attempt.py", "saved_finalizer.py", "camera_audit.py",
           "comparison_audit.py", "source_handoff.py", "native_publication.py",
           "analysis.py")
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")

RUNNER = '''"""Exact dual-green diagnostic preflight; original sources required for capture."""
import argparse
import hashlib
import json
from pathlib import Path

ASSIGNMENT = "testing__C111125__NRS-484B-307-3a__motor_vehicle_driver"
SUFFIXES = ("dual_clear", "dual_vehicle_present", "dual_pedestrian_present", "dual_pedestrian_late")
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    raw = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != config["plan_sha256"]:
        raise ValueError("dual-green case plan changed")
    case_id = config["selected_case_id"]
    if case_id not in {ASSIGNMENT + "__" + s for s in SUFFIXES}:
        raise ValueError("foreign dual-green case")
    plan = json.loads(raw)
    rows = [row for row in plan["cases"] if row["case_id"] == case_id]
    if len(rows) != 1 or rows[0]["scenario_parameters"] != config["scenario_parameters"]:
        raise ValueError("dual-green case parameters changed")
    if config["fps"] != 20 or config["frame_count"] != 900 or tuple(config["cameras"]) != CAMERAS:
        raise ValueError("dual-green capture contract changed")
    if config["required_sources"] != ["surveyed_native_site", "official_dual_aspect_lamp_packets", "original_camera_png", "lawful_use_packets"]:
        raise ValueError("dual-green original source contract changed")
    for name, digest in config["code_sha256"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError("dual-green code source changed: " + name)
    return case_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    case_id = check()
    if args.check:
        print("diagnostic dual-green case passed: " + case_id)
        return
    raise ValueError("Reviewed original dual-aspect site, lamp, lawful-use and camera sources required")


if __name__ == "__main__":
    main()
'''

TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_source_bound_case(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_unsourced_capture_rejected(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Reviewed original dual-aspect"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
'''


def build():
    plan_bytes = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(plan_bytes)
    semantic = json.loads((HERE / "proposals/cases.json").read_text(encoding="utf-8"))
    descriptions = {row["case_id"]: row["recording_description"] for row in semantic["cases"]
                    if row["target_type"] != "baseline"}
    expected = {ASSIGNMENT + "__" + suffix for suffix in SUFFIXES}
    if {case["case_id"] for case in plan["cases"]} != expected or len(plan["cases"]) != 4:
        raise ValueError("exact dual-green case coverage changed")
    if set(descriptions) != expected:
        raise ValueError("semantic cases differ from exact dual-green construction")
    rows = []
    for item in plan["cases"]:
        case_id = item["case_id"]
        suffix = case_id.removeprefix(ASSIGNMENT + "__")
        code = {name: (HERE / name).read_bytes() for name in SOURCES}
        config = {"assignment_id": ASSIGNMENT, "law_id": "NRS-484B-307-3a",
                  "cell_id": "C111125", "actor": "motor_vehicle_driver",
                  "selected_case_id": case_id,
                  "scenario_parameters": item["scenario_parameters"],
                  "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
                  "code_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in code.items()},
                  "fps": 20, "frame_count": 900, "cameras": list(CAMERAS),
                  "diagnostic_only": True, "required_atoms": [],
                  "required_sources": ["surveyed_native_site", "official_dual_aspect_lamp_packets",
                                       "original_camera_png", "lawful_use_packets"]}
        files = {name: data.decode("utf-8") for name, data in code.items()}
        files.update({"runner.py": RUNNER, "case-plan.json": plan_bytes.decode("utf-8"),
                      "config.json": json.dumps(config, indent=2) + "\n",
                      "tests/test_bundle.py": TEST})
        construction = {"law_id": config["law_id"], "cell_id": config["cell_id"],
                        "actor": config["actor"], "case_id": case_id,
                        "entrypoint": "runner.py", "diagnostic_only": True,
                        "recording_description": descriptions[case_id],
                        "files": [{"path": name, "content": content} for name, content in files.items()]}
        path = HERE / ("construction-" + suffix + ".json")
        path.write_text(json.dumps(construction, indent=2) + "\n", encoding="utf-8")
        rows.append({"case_id": case_id, "construction": path.name,
                     "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "measurement_contract": f"measurement-contract-{suffix}.json",
                     "measurement_procedure": {"entrypoint": "analysis.py"},
                     "candidate_risk": item["physical_risk_assessment"]})
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({
        "assignment_id": ASSIGNMENT, "status": "diagnostic_original_sources_pending",
        "cases": rows}, indent=2) + "\n", encoding="utf-8")
    print("built", len(rows), "exact dual-green diagnostic constructions")


if __name__ == "__main__":
    build()
