"""Build two exact nearest-view diagnostic bundles for pinned CPU offline proof."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
INPUT = ROOT / "inputs" / ASSIGNMENT / "review-context" / "review.json"
KINDS = ("nearest_view_response", "nearest_view_uninterrupted")
DIAGNOSTIC_GEOMETRY = {"ego_route_origin_xy_m": [-10, 5], "ego_route_axis_xy": [1, 0],
                       "through_route_origin_xy_m": [5, -10], "through_route_axis_xy": [0, 1],
                       "ego_entry_station_m": 10,
                       "intersection_polygon_xy_m": [[0, 0], [10, 0], [10, 10], [0, 10]]}

RUNNER = '''"""Exact nearest-view diagnostic Native entrypoint."""
import argparse
import hashlib
import json
from pathlib import Path
from yield_control import control
from source_tick_capture import validate_geometry


def check():
    root = Path(__file__).resolve().parent
    scene = json.loads((root / "scene.json").read_text())
    config = json.loads((root / "config.json").read_text())
    source = (root / scene["review_source"]).read_bytes()
    if hashlib.sha256(source).hexdigest() != scene["review_sha256"]:
        raise ValueError("frozen review context changed")
    review = json.loads(source)
    expected = next(c for c in review["comparisons"] if c["id"] == "yield_nearest_view")
    if scene["case_id"] not in {c["case_id"] for c in expected["cases"]}:
        raise ValueError("case is absent from frozen nearest-view comparison")
    if config["selected_case_id"] != scene["case_id"] or config["case"]["kind"] != scene["kind"]:
        raise ValueError("selected case and scene differ")
    if scene["source_kind"] != "diagnostic_review_context":
        raise ValueError("unexpected source kind in diagnostic bundle")
    validate_geometry(scene["capture_geometry"])
    control(scene["kind"], {"ego_speed_mps": 3.0, "distance_to_view_point_m": 5.0,
                           "through_vehicle_in_conflict_interval": True,
                           "yield_sign_governs_approach": True,
                           "viewpoint_source_verified": True})
    return scene


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    scene = check()
    if args.check:
        print("diagnostic offline check passed: " + scene["case_id"])
        return
    raise ValueError("Diagnostic review context is not a genuine Native site packet; capture is refused")


if __name__ == "__main__":
    main()
'''

TEST = '''import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import unittest
import runner
from runner import check
from yield_control import control


class BundleTests(unittest.TestCase):
    def test_exact_review_source_and_case(self):
        scene = check()
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(hashlib.sha256((root / scene["review_source"]).read_bytes()).hexdigest(),
                         scene["review_sha256"])

    def test_controller_isolates_conflict_response(self):
        scene = check()
        observation = {"ego_speed_mps": 3, "distance_to_view_point_m": 5,
                       "through_vehicle_in_conflict_interval": True,
                       "yield_sign_governs_approach": True, "viewpoint_source_verified": True}
        command = control(scene["kind"], observation)
        self.assertEqual(command["engineering_state"],
                         "yield_hold" if scene["kind"] == "nearest_view_response" else "approach_or_cross")

    def test_diagnostic_bundle_refuses_native_capture(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "capture is refused"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
'''


def build():
    frozen = INPUT.read_text(encoding="utf-8")
    source_hash = hashlib.sha256(frozen.encode()).hexdigest()
    plan = json.loads((HERE / "branch-plan.json").read_text(encoding="utf-8"))
    exact = set(plan["exact_case_ids"])
    cases = []
    for kind in KINDS:
        case_id = ASSIGNMENT + "__" + kind
        if case_id not in exact:
            raise ValueError("exact case missing from frozen branch plan")
        scene = {"case_id": case_id, "kind": kind,
                 "source_kind": "diagnostic_review_context", "review_source": "review-context.json",
                 "review_sha256": source_hash, "site_source_status": "missing_genuine_native_site_packet",
                 "capture_geometry": DIAGNOSTIC_GEOMETRY}
        config = {"law_id": "NRS-484B-257-1", "cell_id": "C158208",
                  "actor": "motor_vehicle_driver", "selected_case_id": case_id,
                  "rate_hz": 20, "duration_s": 20,
                  "case": {"kind": kind, "comparison_variable": "observed_conflict_response"},
                  "required_atoms": [], "source_packets": [], "cameras": ["front", "rear", "left", "right"]}
        files = {"runner.py": RUNNER, "yield_control.py": (HERE / "yield_control.py").read_text(),
                 "source_tick_capture.py": (HERE / "source_tick_capture.py").read_text(),
                 "native_attempt.py": (HERE / "native_attempt.py").read_text(),
                 "camera_sources.py": (HERE / "camera_sources.py").read_text(),
                 "physical_completion.py": (HERE / "physical_completion.py").read_text(),
                 "scene.json": json.dumps(scene, indent=2) + "\n",
                 "config.json": json.dumps(config, indent=2) + "\n",
                 "review-context.json": frozen,
                 "tests/test_bundle.py": TEST}
        construction = {"law_id": config["law_id"], "cell_id": config["cell_id"],
                        "actor": config["actor"], "case_id": case_id,
                        "entrypoint": "runner.py", "diagnostic_only": True,
                        "recording_description": {"observations": ["original ego and through-vehicle bodies",
                            "original view and sign source", "four synchronized camera streams"],
                            "status": "draft_not_original_capture"},
                        "files": [{"path": path, "content": content} for path, content in files.items()]}
        location = HERE / ("construction-" + kind + ".json")
        location.write_text(json.dumps(construction, indent=2) + "\n", encoding="utf-8")
        cases.append({"case_id": case_id, "construction": location.name,
                      "construction_sha256": hashlib.sha256(location.read_bytes()).hexdigest(),
                      "candidate_risk": {"status": "none", "reason": "No specific physical fallback trigger has yet been measured for this diagnostic draft"}})
    manifest = {"assignment_id": ASSIGNMENT, "cases": cases,
                "status": "diagnostic_offline_only_genuine_site_source_pending"}
    (HERE / "execution-manifest.draft.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("built two exact diagnostic offline constructions")


if __name__ == "__main__":
    build()
