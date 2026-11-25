"""Build four exact source-gated bundles for pinned offline construction proof.

The runner refuses live capture until a genuinely reviewed Native site packet
is supplied and verified. No synthetic site is embedded in a selected bundle.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name

TEST = '''import unittest
from unittest.mock import patch
import runner
from native_observation import derive
import native_capture
import analysis


class BundleTests(unittest.TestCase):
    def test_exact_frozen_source_and_case(self):
        self.assertTrue(runner.check()["selected_case_id"].startswith(
            "testing__C158196__NRS-484B-257-1__motor_vehicle_driver__"))

    def test_refuses_capture_without_original_site(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "reviewed original C158196 site packet missing"):
                runner.main()

    def test_original_body_and_ray_adapter(self):
        geometry = {"ego_route_origin_xy_m": [0, 0], "ego_route_axis_xy": [1, 0],
                    "through_route_origin_xy_m": [0, 0], "through_route_axis_xy": [0, 1],
                    "intersection_polygon_xy_m": [[4, -2], [8, -2], [8, 2], [4, 2]]}
        raw = {"frame": 100, "time_s": 5.0,
               "ego_body_xy_m": [[1, -.5], [2, -.5], [2, .5], [1, .5]],
               "through_body_xy_m": [[5, -.5], [6, -.5], [6, .5], [5, .5]],
               "ego_velocity_xy_mps": [3, 0], "through_center_xy_m": [5.5, 0],
               "native_view_raycast": {"source": "native_raycast", "occluded": False,
                                       "origin_xy_m": [1.5, 0], "target_xy_m": [5.5, 0]},
               "yield_sign_readback": True, "signal_controlling": False,
               "officer_controlling": False}
        result = derive(raw, geometry)
        self.assertTrue(result["through_occupied"])
        self.assertEqual(result["ego_front_station_m"], 2.0)

    def test_saved_finalizer_and_capture_are_bundled(self):
        self.assertEqual(analysis.ASSIGNMENT,
                         "testing__C158196__NRS-484B-257-1__motor_vehicle_driver")
        self.assertEqual(len(native_capture.VIEWS), 4)


if __name__ == "__main__":
    unittest.main()
'''


def build() -> dict:
    raw = (ROOT / "inputs" / ASSIGNMENT / "assignment.json").read_bytes()
    frozen_hash = hashlib.sha256(raw).hexdigest()
    plan = json.loads((HERE / "case-plan.json").read_text())
    semantic = json.loads((HERE / "proposals/cases.json").read_text())
    semantic_cases = {row["case_id"]: row for row in semantic["cases"]}
    constructions = []
    for case in plan["cases"]:
        case_id = case["case_id"]
        variant = case_id.rsplit("__", 1)[1]
        config = {"law_id": "NRS-484B-257-1", "cell_id": "C158196",
                  "actor": "motor_vehicle_driver", "assignment_id": ASSIGNMENT,
                  "input_sha256": frozen_hash,
                  "selected_case_id": case_id,
                  "supported_case_ids": [row["case_id"] for row in plan["cases"]],
                  "rate_hz": 20, "duration_s": 45, "frame_count": 900,
                  "cameras": ["front", "rear", "left", "right"],
                  "required_atoms": [], "source_packets": [],
                  "case": {"kind": variant,
                           "recording_description": semantic_cases[case_id]["recording_description"]}}
        files = {"runner.py": (HERE / "runner.py").read_text(),
                 "construction.py": (HERE / "construction.py").read_text(),
                 "nearest_view.py": (HERE / "nearest_view.py").read_text(),
                 "native_observation.py": (HERE / "native_observation.py").read_text(),
                 "native_capture.py": (HERE / "native_capture.py").read_text(),
                 "signal_exception.py": (HERE / "signal_exception.py").read_text(),
                 "analysis.py": (HERE / "analysis.py").read_text(),
                 "saved_package.py": (HERE / "saved_package.py").read_text(),
                 "config.json": json.dumps(config, indent=2) + "\n",
                 "frozen-assignment.json": raw.decode("utf-8"),
                 "tests/test_bundle.py": TEST}
        construction = {"law_id": config["law_id"], "cell_id": config["cell_id"],
                        "actor": config["actor"], "case_id": case_id,
                        "entrypoint": "runner.py", "original_site_required": True,
                        "recording_description": semantic_cases[case_id]["recording_description"],
                        "files": [{"path": name, "content": value} for name, value in files.items()]}
        path = HERE / ("construction-" + variant + ".json")
        path.write_text(json.dumps(construction, indent=2) + "\n", encoding="utf-8")
        constructions.append({"case_id": case_id, "kind": "delivery",
                              "construction": path.name,
                              "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                              "candidate_risk": case["physical_risk"], "candidates": [],
                              "measurement_procedure": {"entrypoint": "analysis.py"},
                              "measurement_contract": "cases/" + variant + "/measurement-contract.json",
                              "fixture_recipe": "work/" + ASSIGNMENT + "/diagnostic-" + variant + "-recipe.json"})
    manifest = {"assignment_id": ASSIGNMENT, "cases": constructions,
                "runtime_manifest_sha256": hashlib.sha256(
                    (ROOT / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest(),
                "status": "source_gated_runner_draft_genuine_site_pending"}
    (HERE / "execution-manifest.draft.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    built = build()
    print(f"built {len(built['cases'])} exact source-gated bundles")
