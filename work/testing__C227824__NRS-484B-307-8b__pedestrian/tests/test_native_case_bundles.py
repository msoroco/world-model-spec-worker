import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_case_bundles import expand


class CaseBundleTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((ROOT / "case-plan.json").read_text())
        self.common = {
            "map_source_sha256": "a" * 64, "route_id": "reviewed-route",
            "facing_head_id": 7,
            "highway_polygon_xy_m": [[0, 0], [2, 0], [2, 2], [0, 2]],
            "camera_placements": {"overview": "reviewed"},
            "walker_spawn_xyz_m": [-1, 1, 1],
            "walker_blueprint_id": "walker.pedestrian.0001",
            "target_xy_m": [1, 1], "speed_mps": 1,
            "fixed_delta_seconds": .05, "planned_frames": 40,
        }
        self.no_device = {**self.common, "governing_pedestrian_device_ids": [],
                          "device_inventory_review": {"source_sha256": "b" * 64}}
        self.one_device = {**self.common, "governing_pedestrian_device_ids": [8],
                           "device_inventory_review": {"source_sha256": "c" * 64}}

    def test_exact_six_cases_preserve_fixed_sources(self):
        scenes = expand(self.plan, no_device_base=self.no_device,
                        one_device_base=self.one_device)
        self.assertEqual(set(scenes), {case["case_id"] for case in self.plan["cases"]})
        for case in self.plan["cases"]:
            scene = scenes[case["case_id"]]
            self.assertEqual(scene["entry_request"], case["entry_request"])
            self.assertEqual(scene["requested_pedestrian_indication"],
                             case["other_device_indication"])
            self.assertEqual(scene["map_source_sha256"], "a" * 64)
        self.assertEqual(sum(not scene["governing_pedestrian_device_ids"]
                             for scene in scenes.values()), 2)
        self.assertEqual(sum(bool(scene["governing_pedestrian_device_ids"])
                             for scene in scenes.values()), 4)

    def test_changed_fixed_source_or_device_inventory_fails(self):
        self.one_device["map_source_sha256"] = "d" * 64
        with self.assertRaisesRegex(ValueError, "fixed source changed"):
            expand(self.plan, no_device_base=self.no_device, one_device_base=self.one_device)
        self.one_device["map_source_sha256"] = "a" * 64
        self.one_device["device_inventory_review"] = self.no_device["device_inventory_review"]
        with self.assertRaisesRegex(ValueError, "distinct review sources"):
            expand(self.plan, no_device_base=self.no_device, one_device_base=self.one_device)

    def test_missing_or_changed_plan_case_fails(self):
        self.plan["cases"][2]["other_device_indication"] = "none"
        with self.assertRaisesRegex(ValueError, "case request differs"):
            expand(self.plan, no_device_base=self.no_device, one_device_base=self.one_device)


if __name__ == "__main__":
    unittest.main()
