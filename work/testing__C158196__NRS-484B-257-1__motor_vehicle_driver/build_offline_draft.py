"""Build four exact diagnostic bundles for pinned offline construction proof.

Diagnostic site values exercise interfaces only. The runner refuses live capture
until a genuinely reviewed Native site packet is supplied and verified.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name

RUNNER = '''"""Exact C158196 diagnostic Native entrypoint."""
import argparse
import hashlib
import json
from pathlib import Path
from construction import validate_site, controller


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    scene = json.loads((root / "scene.json").read_text())
    source = (root / "frozen-assignment.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != scene["assignment_sha256"]:
        raise ValueError("frozen assignment source changed")
    assignment = json.loads(source)
    if assignment["assignment_id"] != scene["assignment_id"]:
        raise ValueError("wrong assignment source")
    if config["selected_case_id"] != scene["case_id"]:
        raise ValueError("wrong exact case selection")
    suffix = scene["case_id"].split("__")[-1]
    if suffix != scene["variant"]:
        raise ValueError("variant and exact case disagree")
    site = scene["diagnostic_site"]
    validate_site(site, suffix)
    controller(suffix, site, {"ego_speed_mps": 3.0,
                              "ego_front_station_m": 2.1,
                              "through_occupied": suffix not in
                              ("nearest_view_clear", "active_signal_exception")})
    return scene


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    scene = check()
    if args.check:
        print("diagnostic construction passed: " + scene["case_id"])
        return
    raise ValueError("Diagnostic site is not a reviewed Native site packet; capture is refused")


if __name__ == "__main__":
    main()
'''

TEST = '''import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_frozen_source_and_site(self):
        self.assertTrue(runner.check()["case_id"].startswith(
            "testing__C158196__NRS-484B-257-1__motor_vehicle_driver__"))

    def test_refuses_capture_from_diagnostic_site(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "capture is refused"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
'''


def build() -> dict:
    raw = (ROOT / "inputs" / ASSIGNMENT / "assignment.json").read_bytes()
    frozen_hash = hashlib.sha256(raw).hexdigest()
    plan = json.loads((HERE / "case-plan.json").read_text())
    constructions = []
    for case in plan["cases"]:
        case_id = case["case_id"]
        variant = case_id.rsplit("__", 1)[1]
        site = {"native_cell_id": "C158196", "layout": "one_way_to_two_way_intersection",
                "route_connected": True, "through_highway_confirmed": True,
                "marked_stop_line": False, "near_side_crosswalk": False,
                "sidewalk_derived_crosswalk": False, "officer_controlling": False,
                "proper_yield_sign": True, "yield_sign_governs": True,
                "signal_controlling": variant == "active_signal_exception",
                "nearest_view_station_m": 2.0, "intersection_entry_station_m": 4.0,
                "map_hash": "a" * 64, "device_hash": "b" * 64,
                "raycast_hash": "c" * 64, "camera_plan_hash": "d" * 64}
        config = {"law_id": "NRS-484B-257-1", "cell_id": "C158196",
                  "actor": "motor_vehicle_driver", "selected_case_id": case_id,
                  "rate_hz": 20, "duration_s": 45,
                  "cameras": ["front", "rear", "left", "right"],
                  "required_atoms": [], "source_packets": [], "case": {"kind": variant}}
        scene = {"assignment_id": ASSIGNMENT, "assignment_sha256": frozen_hash,
                 "case_id": case_id, "variant": variant,
                 "source_kind": "diagnostic_only_synthetic_site",
                 "diagnostic_site": site}
        files = {"runner.py": RUNNER,
                 "construction.py": (HERE / "construction.py").read_text(),
                 "nearest_view.py": (HERE / "nearest_view.py").read_text(),
                 "config.json": json.dumps(config, indent=2) + "\n",
                 "scene.json": json.dumps(scene, indent=2) + "\n",
                 "frozen-assignment.json": raw.decode("utf-8"),
                 "tests/test_bundle.py": TEST}
        construction = {"law_id": config["law_id"], "cell_id": config["cell_id"],
                        "actor": config["actor"], "case_id": case_id,
                        "entrypoint": "runner.py", "diagnostic_only": True,
                        "recording_description": {"observations": case["source_requirements"],
                                                  "status": "draft_not_original_capture"},
                        "files": [{"path": name, "content": value} for name, value in files.items()]}
        path = HERE / ("construction-" + variant + ".json")
        path.write_text(json.dumps(construction, indent=2) + "\n", encoding="utf-8")
        constructions.append({"case_id": case_id, "kind": "delivery",
                              "construction": path.name,
                              "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                              "candidate_risk": case["physical_risk"], "candidates": []})
    manifest = {"assignment_id": ASSIGNMENT, "cases": constructions,
                "status": "diagnostic_offline_only_genuine_site_source_pending"}
    (HERE / "execution-manifest.draft.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    built = build()
    print(f"built {len(built['cases'])} exact diagnostic bundles")
