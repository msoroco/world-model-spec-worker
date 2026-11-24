"""Build six exact diagnostic blind-person encounter constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SOURCE_FILES = (
    "blind_encounter.py", "native_capture.py", "carla_adapter.py",
    "saved_encounter.py", "delivery_audit.py", "reviewed_sources.py",
)

RUNNER = '''"""Exact blind-person encounter diagnostic bundle preflight."""
import argparse
import hashlib
import json
from pathlib import Path
from blind_encounter import CASE_BY_ID
from native_capture import CAMERAS
from reviewed_sources import prepare


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact case plan changed")
    plan = json.loads(source)
    case_id = config["selected_case_id"]
    rows = [item for item in plan["cases"] if item["case_id"] == case_id]
    if len(rows) != 1 or not case_id.startswith(config["assignment_id"] + "__"):
        raise ValueError("Exact encounter case missing")
    suffix = case_id.removeprefix(config["assignment_id"] + "__")
    if suffix not in CASE_BY_ID:
        raise ValueError("Unsupported encounter case")
    case = CASE_BY_ID[suffix]
    if config["case"] != {"cue": case.cue, "encounter": case.encounter,
                          "response": case.response, "precaution": case.precaution}:
        raise ValueError("Encounter construction knobs changed")
    if config["case"] != {key: rows[0][key] for key in config["case"]}:
        raise ValueError("Encounter differs from exact plan")
    if config["hz"] != 20 or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("Original capture timebase changed")
    if config["cameras"] != list(CAMERAS):
        raise ValueError("Original camera list changed")
    if config["required_sources"] != ["reviewed_map_route", "blindness_attestation",
                                      "actually_carried_cue", "original_body_history",
                                      "original_camera_pixels"]:
        raise ValueError("Encounter source contract changed")
    return case_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--source-packet")
    args = parser.parse_args()
    case_id = check()
    if args.check:
        print("diagnostic blind-person bundle passed: " + case_id)
        return
    if args.source_packet:
        plan = prepare(Path(args.source_packet))
        if plan["case_id"] != case_id.removeprefix(json.loads((Path(__file__).resolve().parent / "config.json").read_text())["assignment_id"] + "__"):
            raise ValueError("reviewed packet exact case mismatch")
        raise ValueError("reviewed plan bound; Native actor spawn and world ownership require local integration")
    raise ValueError("Reviewed Native map, blindness and actually carried cue sources required")


if __name__ == "__main__":
    main()
'''

TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner
import reviewed_sources
import saved_encounter


class BundleTests(unittest.TestCase):
    def test_exact_case_preflight(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_refuses_unsourced_native_run(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Reviewed Native map"):
                runner.main()

    def test_materialized_source_processors_keep_assignment_identity(self):
        config = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())
        self.assertEqual(reviewed_sources.ASSIGNMENT_ID, config["assignment_id"])
        self.assertEqual(saved_encounter.ASSIGNMENT_ID, config["assignment_id"])


if __name__ == "__main__":
    unittest.main()
'''


def build():
    source = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(source)
    rows = []
    for item in plan["cases"]:
        case_id = item["case_id"]
        if not case_id.startswith(AID + "__"):
            raise ValueError("Foreign exact case")
        suffix = case_id.removeprefix(AID + "__")
        config = {
            "assignment_id": AID, "law_id": "LVMC-11-30-140-B", "cell_id": "C111248",
            "actor": "motor_vehicle_driver", "selected_case_id": case_id,
            "plan_sha256": hashlib.sha256(source).hexdigest(),
            "case": {key: item[key] for key in ("cue", "encounter", "response", "precaution")},
            "hz": 20, "frame_count": 900, "duration_s": 45,
            "cameras": ["front", "left", "right", "rear"],
            "required_sources": ["reviewed_map_route", "blindness_attestation",
                                 "actually_carried_cue", "original_body_history",
                                 "original_camera_pixels"],
            "required_atoms": [], "diagnostic_only": True,
        }
        files = {name: (HERE / name).read_text() for name in SOURCE_FILES}
        files.update({"runner.py": RUNNER, "case-plan.json": source.decode(),
                      "config.json": json.dumps(config, indent=2) + "\n",
                      "tests/test_bundle.py": TEST})
        construction = {
            "law_id": config["law_id"], "cell_id": config["cell_id"],
            "actor": config["actor"], "case_id": case_id,
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": {
                "status": "diagnostic_only_original_sources_pending",
                "channels": config["cameras"]},
            "files": [{"path": path, "content": content} for path, content in files.items()],
        }
        output = HERE / ("construction-" + suffix + ".json")
        output.write_text(json.dumps(construction, indent=2) + "\n")
        rows.append({"case_id": case_id, "construction": output.name,
                     "construction_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                     "candidate_risk": item["candidate_risk"]})
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({
        "assignment_id": AID, "status": "diagnostic_offline_only_original_sources_pending",
        "cases": rows}, indent=2) + "\n")
    print("built", len(rows), "exact blind-person diagnostic constructions")


if __name__ == "__main__":
    build()
