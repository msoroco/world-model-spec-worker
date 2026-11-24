"""Build three exact, source-gated C10301 offline construction drafts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
MODULES = (
    "capture_finalizer.py", "delivery_audit.py", "native_capture.py",
    "native_media.py", "native_motion.py", "native_site.py", "owned_capture.py",
    "saved_speed.py", "speed_boundary.py", "speed_capture.py",
)
EXPECTED = {"below": 75, "equal": 80, "above": 85}

RUNNER = '''"""Exact speed-case preflight and source-gated Native runner."""
import argparse
import hashlib
import json
from pathlib import Path


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact source plan changed")
    plan = json.loads(source)
    if plan["assignment_id"] != config["assignment_id"] or plan["law_id"] != config["law_id"]:
        raise ValueError("Assignment identity changed")
    matches = [row for row in plan["cases"] if row["case_id"] == config["selected_case_id"]]
    if len(matches) != 1 or matches[0]["intended_speed_mph"] != config["requested_speed_mph"]:
        raise ValueError("Exact speed case changed")
    if (config["rate_hz"], config["frame_count"], config["duration_s"]) != (20, 900, 45):
        raise ValueError("Original observation clock changed")
    if config["cameras"] != ["overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("Original camera profile changed")
    if config["required_sources"] != ["reviewed_site_packet", "original_motion", "route_readback", "four_camera_media"]:
        raise ValueError("Original source requirements changed")
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    config = check()
    if args.check:
        print("exact diagnostic speed bundle passed: " + config["selected_case_id"])
        return
    raise ValueError("Reviewed C10301 route, access-aisle authority and Native site packet required")


if __name__ == "__main__":
    main()
'''

TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_source_and_clock(self):
        config = runner.check()
        self.assertEqual(config["frame_count"], 900)
        self.assertEqual(config["selected_case_id"], json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())["selected_case_id"])

    def test_unreviewed_native_run_rejected(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Reviewed C10301 route"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
'''


def build() -> None:
    source = (ROOT / "case-plan.json").read_bytes()
    plan = json.loads(source)
    if plan["assignment_id"] != AID or plan["law_id"] != "NRS-484B-600-1e":
        raise ValueError("Plan identity changed")
    by_suffix = {row["case_id"].removeprefix(AID + "__"): row for row in plan["cases"]}
    if set(by_suffix) != set(EXPECTED):
        raise ValueError("Three exact speed cases required")
    entries = []
    for suffix, requested_speed in EXPECTED.items():
        item = by_suffix[suffix]
        if (item["case_id"], item["intended_speed_mph"], item["physical_status"]) != (AID + "__" + suffix, requested_speed, "unverified"):
            raise ValueError(f"Speed or physical claim changed: {suffix}")
        config = {
            "assignment_id": AID, "law_id": plan["law_id"], "cell_id": plan["cell_id"],
            "actor": plan["actor"], "selected_case_id": item["case_id"],
            "plan_sha256": hashlib.sha256(source).hexdigest(),
            "requested_speed_mph": requested_speed, "statutory_boundary_mph": 80,
            "rate_hz": 20, "frame_count": 900, "duration_s": 45,
            "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
            "required_sources": ["reviewed_site_packet", "original_motion", "route_readback", "four_camera_media"],
            "diagnostic_only": True,
        }
        files = {name: (ROOT / name).read_text() for name in MODULES}
        files.update({"runner.py": RUNNER, "case-plan.json": source.decode(),
                      "config.json": json.dumps(config, indent=2) + "\n",
                      "tests/test_bundle.py": TEST})
        construction = {
            "law_id": plan["law_id"], "cell_id": plan["cell_id"],
            "actor": plan["actor"], "case_id": item["case_id"],
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": {"status": "diagnostic_only_reviewed_site_pending",
                                      "channels": config["cameras"]},
            "files": [{"path": path, "content": content} for path, content in files.items()],
        }
        path = ROOT / f"construction-{suffix}.json"
        path.write_text(json.dumps(construction, indent=2) + "\n")
        entries.append({"case_id": item["case_id"], "construction": path.name,
                        "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (ROOT / "execution-manifest.draft.json").write_text(json.dumps({
        "assignment_id": AID, "status": "diagnostic_offline_only_reviewed_site_pending",
        "cases": entries,
    }, indent=2) + "\n")
    print("built three exact source-gated speed constructions")


if __name__ == "__main__":
    build()
