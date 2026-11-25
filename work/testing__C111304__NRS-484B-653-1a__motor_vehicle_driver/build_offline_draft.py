"""Build exact, source-gated diagnostic bundles for the eight encounter cases."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from encounter import CASES
from native_acquisition import CAMERAS


HERE = Path(__file__).resolve().parent
AID = HERE.name
SOURCE_FILES = (
    "encounter.py", "native_acquisition.py", "site_binding.py",
    "saved_audit.py", "media_audit.py", "carla_adapter.py",
    "native_runner.py",
)

RUNNER = '''"""Exact C111304 encounter bundle preflight; no unsourced simulation."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from encounter import CASES
from native_acquisition import CAMERAS


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact case plan source changed")
    case_id = config["selected_case_id"]
    if not case_id.startswith(config["assignment_id"] + "__"):
        raise ValueError("Foreign exact case")
    if sum(row["case_id"] == case_id for row in json.loads(source)["cases"]) != 1:
        raise ValueError("Exact case absent from plan")
    suffix = case_id.removeprefix(config["assignment_id"] + "__")
    matches = [case for case in CASES if case.case_id == suffix]
    if len(matches) != 1 or config["case_spec"] != asdict(matches[0]):
        raise ValueError("Exact encounter construction changed")
    if config["rate_hz"] != 20 or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("Original timebase changed")
    if config["cameras"] != list(CAMERAS):
        raise ValueError("Original four-camera plan changed")
    if config["required_sources"] != ["loaded_map", "public_access_review", "site_packet", "actor_trace", "control_trace", "original_camera_media"]:
        raise ValueError("Required original sources changed")
    return case_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    case_id = check()
    if args.check:
        print("diagnostic C111304 encounter bundle passed: " + case_id)
        return
    raise ValueError("Reviewed original C111304 site, actors and camera sensor sources required")


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

    def test_refuses_unsourced_capture(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Reviewed original C111304 site"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
'''


def build():
    source = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(source)
    specs = {case.case_id: asdict(case) for case in CASES}
    found = {row["case_id"].removeprefix(AID + "__") for row in plan["cases"]}
    if len(plan["cases"]) != len(specs) or found != set(specs):
        raise ValueError("Exact case plan and encounter construction differ")
    rows = []
    for item in plan["cases"]:
        case_id = item["case_id"]
        if not case_id.startswith(AID + "__"):
            raise ValueError("Foreign exact case")
        suffix = case_id.removeprefix(AID + "__")
        config = {
            "assignment_id": AID, "law_id": "NRS-484B-653-1a", "cell_id": "C111304",
            "actor": "motor_vehicle_driver", "selected_case_id": case_id,
            "case_spec": specs[suffix], "plan_sha256": hashlib.sha256(source).hexdigest(),
            "rate_hz": 20, "frame_count": 900, "duration_s": 45,
            "cameras": list(CAMERAS),
            "required_sources": ["loaded_map", "public_access_review", "site_packet", "actor_trace", "control_trace", "original_camera_media"],
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
            "recording_description": {"status": "diagnostic_only_original_sources_pending", "channels": config["cameras"]},
            "files": [{"path": path, "content": content} for path, content in files.items()],
        }
        output = HERE / ("construction-" + suffix + ".json")
        output.write_text(json.dumps(construction, indent=2) + "\n")
        rows.append({"case_id": case_id, "construction": output.name,
                     "construction_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                     "candidate_risk": item["physical_risk"]})
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({
        "assignment_id": AID, "status": "diagnostic_offline_only_original_sources_pending", "cases": rows,
    }, indent=2) + "\n")
    print("built", len(rows), "exact C111304 diagnostic constructions")


if __name__ == "__main__":
    build()
