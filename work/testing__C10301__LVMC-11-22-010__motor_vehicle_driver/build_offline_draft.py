"""Build the two exact diagnostic alley bundles for pinned offline validation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
AID = HERE.name
KINDS = ("steady_travel", "steering_variation")

RUNNER = '''"""Exact alley operation diagnostic entrypoint."""
import argparse
import json
from pathlib import Path
from alley_geometry import validate
from native_operation import CASE_PROFILES


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    scene = json.loads((root / "alley-scene.json").read_text())
    if config["selected_case_id"] not in CASE_PROFILES:
        raise ValueError("unknown exact alley case")
    if config["profile"] != CASE_PROFILES[config["selected_case_id"]]:
        raise ValueError("case controller profile differs")
    if config["fps"] != 20 or config["duration_s"] != 45:
        raise ValueError("original acquisition duration differs")
    validate(scene)
    return config["selected_case_id"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic alley bundle passed: " + case)
        return
    raise ValueError("Reviewed Native site and original camera source required; diagnostic capture refused")


if __name__ == "__main__":
    main()
'''

TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_scene_and_controller_profile(self):
        self.assertEqual(runner.check(), json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())["selected_case_id"])

    def test_diagnostic_bundle_refuses_capture(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "diagnostic capture refused"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
'''


def build() -> None:
    plan = json.loads((HERE / "case-plan.json").read_text())
    expected = {row["case_id"] for row in plan["cases"]}
    scene = (HERE / "alley-scene.json").read_text()
    cases = []
    for kind in KINDS:
        case = AID + "__" + kind
        if case not in expected:
            raise ValueError("exact selected case missing")
        config = {"law_id": "LVMC-11-22-010", "cell_id": "C10301",
                  "actor": "motor_vehicle_driver", "selected_case_id": case,
                  "profile": "steady" if kind == "steady_travel" else "variation",
                  "fps": 20, "duration_s": 45, "diagnostic_only": True,
                  "cameras": ["overview", "alley_approach", "access_aisle", "driver_reference"],
                  "required_atoms": []}
        files = {"runner.py": RUNNER,
                 "alley_geometry.py": (HERE / "alley_geometry.py").read_text(),
                 "native_operation.py": (HERE / "native_operation.py").read_text(),
                 "native_context.py": (HERE / "native_context.py").read_text(),
                 "native_capture.py": (HERE / "native_capture.py").read_text(),
                 "saved_delivery.py": (HERE / "saved_delivery.py").read_text(),
                 "saved_finalizer.py": (HERE / "saved_finalizer.py").read_text(),
                 "attention_measurement.py": (HERE / "attention_measurement.py").read_text(),
                 "alley-scene.json": scene,
                 "config.json": json.dumps(config, indent=2) + "\n",
                 "tests/test_bundle.py": TEST}
        construction = {"law_id": config["law_id"], "cell_id": config["cell_id"],
                        "actor": config["actor"], "case_id": case,
                        "entrypoint": "runner.py", "diagnostic_only": True,
                        "recording_description": {"status": "diagnostic_only_original_source_pending",
                                                  "channels": config["cameras"]},
                        "files": [{"path": name, "content": content} for name, content in files.items()]}
        path = HERE / ("construction-" + kind + ".json")
        path.write_text(json.dumps(construction, indent=2) + "\n")
        cases.append({"case_id": case, "construction": path.name,
                      "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "candidate_risk": {"status": "none", "reason": "Diagnostic geometry has no measured case-specific Native failure trigger"}})
    manifest = {"assignment_id": AID, "cases": cases,
                "status": "diagnostic_offline_only_reviewed_native_site_pending"}
    (HERE / "execution-manifest.draft.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("built two exact diagnostic alley bundles")


if __name__ == "__main__":
    build()
