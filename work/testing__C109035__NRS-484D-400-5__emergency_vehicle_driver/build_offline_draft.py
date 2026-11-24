"""Build the seven exact emergency-device diagnostic constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
AID = HERE.name
SOURCE_FILES = (
    "emergency_scene.py", "native_scene.py", "native_capture.py",
    "camera_recorder.py", "device_readback.py", "saved_finalizer.py",
    "warning_audit.py", "pixel_audit.py", "comparison_audit.py",
)

RUNNER = '''"""Exact emergency-device bundle preflight."""
import argparse
import hashlib
import json
from pathlib import Path
from emergency_scene import CASE_KNOBS, control_plan, scene_geometry
from native_capture import FRAMES, HZ


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    plan_data = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(plan_data).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact plan changed")
    plan = json.loads(plan_data)
    case = config["selected_case_id"]
    if case not in {row["case_id"] for row in plan["cases"]}:
        raise ValueError("Exact case absent")
    suffix = case.removeprefix(config["assignment_id"] + "__")
    if suffix not in CASE_KNOBS or config["case"] != CASE_KNOBS[suffix]:
        raise ValueError("Event or device commands changed")
    if config["rate_hz"] != HZ or config["frame_count"] != FRAMES:
        raise ValueError("Original timebase changed")
    if config["duration_s"] != 45 or config["cameras"] != ["front", "rear", "left", "right"]:
        raise ValueError("Camera or duration contract changed")
    if config["required_sources"] != ["site_packet", "dispatch_context", "equipment_record", "device_samples", "camera_media"]:
        raise ValueError("Original source requirements changed")
    geometry = scene_geometry(config["approach"])
    if geometry["pedestrian_distance_at_spawn_m"] <= 20:
        raise ValueError("Recipient approach geometry invalid")
    controls = control_plan(suffix)
    if controls["event_context"] != config["case"]["event"]:
        raise ValueError("Control event changed")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic emergency-device bundle passed: " + case)
        return
    raise ValueError("Reviewed original dispatch, equipment, Native site, device instrument and camera sensors required")


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

    def test_refuses_unsourced_native_run(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Reviewed original dispatch"):
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
        suffix = case.removeprefix(AID + "__")
        if not case.startswith(AID + "__"):
            raise ValueError("Foreign case")
        config = {
            "assignment_id": AID, "law_id": "NRS-484D-400-5", "cell_id": "C109035",
            "actor": "emergency_vehicle_driver", "selected_case_id": case,
            "plan_sha256": hashlib.sha256(source).hexdigest(),
            "case": {"event": item["authored_event_context"], "siren": item["requested_siren"], "lamps": item["requested_warning_lamps"]},
            "approach": "eastbound", "rate_hz": 20, "frame_count": 900,
            "duration_s": 45, "cameras": ["front", "rear", "left", "right"],
            "required_sources": ["site_packet", "dispatch_context", "equipment_record", "device_samples", "camera_media"],
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
            "recording_description": {"status": "diagnostic_only_original_sources_pending", "channels": config["cameras"]},
            "files": [{"path": path, "content": content} for path, content in files.items()],
        }
        output = HERE / ("construction-" + suffix + ".json")
        output.write_text(json.dumps(construction, indent=2) + "\n")
        rows.append({"case_id": case, "construction": output.name,
                     "construction_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                     "candidate_risk": item["candidate_risk"]})
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({
        "assignment_id": AID, "status": "diagnostic_offline_only_original_sources_pending",
        "cases": rows,
    }, indent=2) + "\n")
    print("built", len(rows), "exact emergency-device diagnostic constructions")


if __name__ == "__main__":
    build()
