"""Synthetic CPU checks for comparison isolation and source identity."""
import copy
import unittest

from comparison_audit import PAIRS, audit
from reviewed_scene import ASSIGNMENT


def scene(suffix):
    ego_lane = "R" if suffix == "slow_right_follower" else "M"
    follower_lane = "R" if suffix == "slow_middle_no_immediate_follower" else ego_lane
    actors = [{"role": "ego", "lane_id": ego_lane, "station_m": 20.0,
               "target_speed_mps": 5.0},
              {"role": "following_vehicle", "lane_id": follower_lane,
               "station_m": 0.0, "target_speed_mps": 8.0}]
    if suffix == "slow_middle_passing":
        actors.append({"role": "slower_vehicle", "lane_id": "R",
                       "station_m": 50.0, "target_speed_mps": 3.0})
    return {"format": "c147344-reviewed-scene-plan-v1",
            "case_id": ASSIGNMENT + "__" + suffix,
            "site_sha256": "a" * 64, "map_sha256": "b" * 64,
            "rightmost_lane_id": "R", "actors": actors,
            "cameras": ["overview", "approach", "reference_corner", "conflict"],
            "hz": 20, "frames": 900}


def result(plan):
    suffix = plan["case_id"].removeprefix(ASSIGNMENT + "__")
    fields = {"ego_in_extreme_right_lane": suffix == "slow_right_follower",
              "passing_slower_vehicle_observed": suffix == "slow_middle_passing",
              "follower_immediately_behind_in_ego_lane":
                  suffix != "slow_middle_no_immediate_follower"}
    return {"format": "c147344-original-follower-relation-join-v1",
            "case_id": plan["case_id"], "original_trace_id": suffix + "-trace",
            "original_frame_count": 900, "source": {"trace_sha256": "c" * 64,
                                                    "relation_sha256": "d" * 64},
            "observations": [dict(fields) for _ in range(900)]}


class ComparisonAuditTests(unittest.TestCase):
    def test_three_isolated_original_comparisons(self):
        for comparison_id, names in PAIRS.items():
            left, right = (scene(name) for name in names)
            receipt = audit(comparison_id, left, right, result(left), result(right))
            self.assertTrue(receipt["comparison_isolated"])
            self.assertEqual(receipt["observed_true_frames"], [0, 900] if
                             comparison_id != "immediate_follower_condition" else [900, 0])
            self.assertFalse(receipt["physical_acceptance"])

    def test_rejects_fixed_source_change_or_reused_original(self):
        left, right = (scene(name) for name in PAIRS["extreme_right_position"])
        right["map_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "fixed source"):
            audit("extreme_right_position", left, right, result(left), result(right))
        right["map_sha256"] = left["map_sha256"]
        repeated = result(right)
        repeated["original_trace_id"] = result(left)["original_trace_id"]
        with self.assertRaisesRegex(ValueError, "reuses one original"):
            audit("extreme_right_position", left, right, result(left), repeated)

    def test_rejects_unisolated_actor_speed(self):
        left, right = (scene(name) for name in PAIRS["passing_exception"])
        changed = copy.deepcopy(right)
        changed["actors"][0]["target_speed_mps"] = 7.0
        with self.assertRaisesRegex(ValueError, "fixed actor control"):
            audit("passing_exception", left, changed, result(left), result(changed))


if __name__ == "__main__":
    unittest.main()
