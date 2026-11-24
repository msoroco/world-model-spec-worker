"""Build three exact parked-headlamp diagnostic constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SOURCE_FILES = (
    "lamp_probe.py", "parking_geometry.py", "native_capture.py",
    "camera_recorder.py", "saved_lamps.py", "delivery_audit.py",
    "comparison_audit.py",
)

RUNNER = '''"""Exact parked-headlamp bundle preflight."""
import argparse
import hashlib
import json
from pathlib import Path
from lamp_probe import CASE_MODES
from native_capture import VIEWS


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact plan source changed")
    plan = json.loads(source)
    case = config["selected_case_id"]
    entries = [row for row in plan["cases"] if row["case_id"] == case]
    if len(entries) != 1 or not case.startswith(config["assignment_id"] + "__"):
        raise ValueError("Exact case absent")
    mode = case.removeprefix(config["assignment_id"] + "__")
    if mode not in CASE_MODES or entries[0]["requested_headlamp_mode"] != mode or config["requested_headlamp_mode"] != mode:
        raise ValueError("Requested lamp mode changed")
    if config["rate_hz"] != 20 or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("Original 20 Hz interval changed")
    if config["cameras"] != list(VIEWS):
        raise ValueError("Four original camera views changed")
    if config["source_requirements"] != ["reviewed_site", "actor_state", "camera_frame_map", "original_camera_media"]:
        raise ValueError("Original source requirements changed")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic parked-headlamp bundle passed: " + case)
        return
    raise ValueError("Reviewed Native intersection site, parked actor and original emission/aim capture required")


if __name__ == "__main__":
    main()
'''

TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_refuses_unsourced_native(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Reviewed Native intersection"):
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
            "assignment_id": AID, "law_id": "NRS-484D-165-4", "cell_id": "C110454",
            "actor": "motor_vehicle_driver", "selected_case_id": case,
            "requested_headlamp_mode": item["requested_headlamp_mode"],
            "plan_sha256": hashlib.sha256(source).hexdigest(),
            "rate_hz": 20, "frame_count": 900, "duration_s": 45,
            "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
            "source_requirements": ["reviewed_site", "actor_state", "camera_frame_map", "original_camera_media"],
            "required_atoms": [], "diagnostic_only": True,
        }
        files = {name: (HERE / name).read_text() for name in SOURCE_FILES}
        files.update({"runner.py": RUNNER, "case-plan.json": source.decode(),
                      "config.json": json.dumps(config, indent=2) + "\n",
                      "tests/test_bundle.py": TEST})
        construction = {
            "law_id": config["law_id"], "cell_id": config["cell_id"],
            "actor": config["actor"], "case_id": case,
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": {"status": "diagnostic_only_site_and_emission_review_pending", "channels": config["cameras"]},
            "files": [{"path": path, "content": content} for path, content in files.items()],
        }
        output = HERE / ("construction-" + suffix + ".json")
        output.write_text(json.dumps(construction, indent=2) + "\n")
        rows.append({"case_id": case, "construction": output.name,
                     "construction_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                     "candidate_risk": {"status": "physical", "reason": "Parking footprint and actual headlamp emission/aim visibility need reviewed Native measurement; no source-verified fallback selected"}})
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({
        "assignment_id": AID, "status": "diagnostic_offline_only_original_site_pending", "cases": rows,
    }, indent=2) + "\n")
    print("built", len(rows), "exact parked-headlamp diagnostic constructions")


if __name__ == "__main__":
    build()
