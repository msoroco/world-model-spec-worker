import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from compare_saved import compare


class SavedComparisonCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.plan = Path(self.temp.name) / "plan.json"
        self.first = ROOT.name + "__clear_intervening"
        self.second = ROOT.name + "__blocked_intervening"
        self.plan.write_text(json.dumps({"comparisons": [{
            "comparison_id": "intervening_area_condition",
            "case_ids": [self.first, self.second]}]}) + "\n")

    def packets(self):
        fixed = {"cell_id": "C104081", "actor": "pedestrian", "map_id": "original-map",
                 "pedestrian_blueprint": "walker.pedestrian.0001",
                 "traffic_plan_sha256": "a" * 64, "camera_profile_sha256": "b" * 64,
                 "duration_frames": 900, "pedestrian_direction": 1,
                 "sidewalk_obstruction_end_m": 34,
                 "sidewalk_obstruction_kind": "impassable_section",
                 "source_kind": "original_saved_acquisition", "source_packet_sha256": "c" * 64}
        return {
            self.first: dict(fixed, case_id=self.first,
                             intervening_barrier_present=False, designated_lane_used=False),
            self.second: dict(fixed, case_id=self.second,
                              intervening_barrier_present=True, designated_lane_used=True),
        }

    def test_exact_positive_and_fixed_condition_negative(self):
        packets = self.packets()
        with patch("compare_saved.comparison_projection", side_effect=lambda root, case: packets[case]):
            result = compare(self.plan, "intervening_area_condition", "first", "second")
            self.assertEqual(result["findings"][0]["observed_differences"],
                             ["designated_lane_used", "intervening_barrier_present"])
            self.assertFalse(result["delivery_acceptance_claimed"])
            packets[self.second]["map_id"] = "changed-map"
            with self.assertRaisesRegex(ValueError, "fixed condition changed"):
                compare(self.plan, "intervening_area_condition", "first", "second")

    def test_synthetic_packet_never_enters_production(self):
        packets = self.packets()
        packets[self.first]["source_kind"] = "synthetic_fixture"
        with patch("compare_saved.comparison_projection", side_effect=lambda root, case: packets[case]):
            with self.assertRaisesRegex(ValueError, "original saved acquisition"):
                compare(self.plan, "intervening_area_condition", "first", "second")


if __name__ == "__main__":
    unittest.main()
