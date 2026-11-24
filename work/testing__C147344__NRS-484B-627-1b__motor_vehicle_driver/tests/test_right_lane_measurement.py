import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from right_lane_measurement import ASSIGNMENT, measure


class RightLaneTests(unittest.TestCase):
    def packet(self):
        return {"assignment_id": ASSIGNMENT, "original_trace_id": "synthetic-test-only",
                "follower_relation_source_sha256": "a" * 64,
                "frames": [{"time_s": i * 0.05, "ego_speed_mps": 4.0,
                            "follower_gap_m": 20.0 - i, "follower_speed_mps": 7.0,
                            "ego_lane_id": "middle", "rightmost_same_direction_lane_id": "right",
                            "follower_actor_id": "car-b", "follower_lane_id": "middle",
                            "follower_immediately_behind_readback": True,
                            "passing_slower_vehicle_observed": False,
                            "same_direction_marked_lane_count": 3} for i in range(3)]}

    def run_measure(self, packet):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "source.json"
            p.write_text(json.dumps(packet), encoding="utf-8")
            return measure(p)

    def test_original_observations(self):
        r = self.run_measure(self.packet())
        self.assertEqual(len(r["observations"]), 3)
        self.assertFalse(r["observations"][0]["ego_in_extreme_right_lane"])
        self.assertTrue(r["observations"][0]["follower_immediately_behind_in_ego_lane"])
        self.assertEqual(r["observations"][0]["follower_closing_speed_mps"], 3.0)

    def test_right_lane_separate_from_immediate_follower(self):
        p = self.packet()
        p["frames"][0]["ego_lane_id"] = "right"
        p["frames"][0]["follower_immediately_behind_readback"] = False
        r = self.run_measure(p)
        self.assertTrue(r["observations"][0]["ego_in_extreme_right_lane"])
        self.assertFalse(r["observations"][0]["follower_immediately_behind_in_ego_lane"])

    def test_same_lane_does_not_establish_immediate_follower(self):
        p = self.packet()
        p["frames"][0]["follower_immediately_behind_readback"] = False
        r = self.run_measure(p)
        self.assertTrue(r["observations"][0]["follower_in_ego_lane"])
        self.assertFalse(r["observations"][0]["follower_immediately_behind_in_ego_lane"])

    def test_missing_or_inconsistent_relation_rejected(self):
        p = self.packet()
        del p["follower_relation_source_sha256"]
        with self.assertRaisesRegex(ValueError, "independent original follower-relation"):
            self.run_measure(p)
        p = self.packet()
        p["frames"][0]["follower_lane_id"] = "right"
        with self.assertRaisesRegex(ValueError, "conflicts with original lane"):
            self.run_measure(p)
        p = self.packet()
        del p["frames"][0]["follower_immediately_behind_readback"]
        with self.assertRaisesRegex(ValueError, "relation readback"):
            self.run_measure(p)

    def test_missing_lane_identity_rejected(self):
        p = self.packet()
        del p["frames"][1]["rightmost_same_direction_lane_id"]
        with self.assertRaisesRegex(ValueError, "lane identities"):
            self.run_measure(p)

    def test_skipped_sample_rejected(self):
        p = self.packet()
        p["frames"][2]["time_s"] = 0.2
        with self.assertRaisesRegex(ValueError, "skipped"):
            self.run_measure(p)

    def test_wrong_assignment_rejected(self):
        p = self.packet()
        p["assignment_id"] = "wrong"
        with self.assertRaisesRegex(ValueError, "wrong assignment"):
            self.run_measure(p)


if __name__ == "__main__":
    unittest.main()
