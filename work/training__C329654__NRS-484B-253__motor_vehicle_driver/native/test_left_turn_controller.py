"""CPU policy checks exercise observed triggers without claiming motion."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from left_turn_controller import command, steering_to_waypoint


class LeftTurnControllerTests(unittest.TestCase):
    def setUp(self):
        self.config = {"yield_policy": "yield_then_turn", "turn_release_s": 15.0}
        self.observation = {
            "time_s": 16.0,
            "route_target_xy_m": [5.0, 5.0],
            "ego": {"center_xy_m": [0.0, 0.0], "heading_deg": 45.0,
                    "left_turn_progress": 0.0, "speed_mps": 0.0,
                    "inside_intersection": True},
            "oncoming": [
                {"actor_id": "initial", "distance_to_conflict_m": -2.0},
                {"actor_id": "subsequent", "distance_to_conflict_m": 20.0},
            ],
        }

    def test_yield_then_turn_waits_for_measured_initial_passage(self):
        self.observation["oncoming"][0]["distance_to_conflict_m"] = 2.0
        actual = command(self.config, self.observation)
        self.assertEqual(actual["ego"]["phase"], "yield_wait")
        self.assertEqual(actual["ego"]["brake"], 1.0)
        self.observation["oncoming"][0]["distance_to_conflict_m"] = -2.0
        self.assertEqual(command(self.config, self.observation)["ego"]["phase"], "turn")

    def test_early_policy_requests_turn_before_first_passage(self):
        self.config = {"yield_policy": "turn_before_pass", "turn_release_s": 9.0}
        self.observation["time_s"] = 9.0
        self.observation["oncoming"][0]["distance_to_conflict_m"] = 28.0
        self.assertEqual(command(self.config, self.observation)["ego"]["phase"], "turn")

    def test_subsequent_brake_responds_to_measured_commitment(self):
        self.assertFalse(command(self.config, self.observation)["subsequent_yield_requested"])
        self.observation["ego"]["left_turn_progress"] = 0.25
        actual = command(self.config, self.observation)
        self.assertTrue(actual["subsequent_yield_requested"])
        self.assertGreater(actual["subsequent_opponent"]["brake"], 0)
        self.assertFalse(actual["physical_effect_observed"])

    def test_no_brake_after_second_passage(self):
        self.observation["ego"]["left_turn_progress"] = 0.25
        self.observation["oncoming"][1]["distance_to_conflict_m"] = -1
        self.assertFalse(command(self.config, self.observation)["subsequent_yield_requested"])

    def test_missing_second_actor_rejected(self):
        self.observation["oncoming"].pop()
        with self.assertRaisesRegex(ValueError, "subsequent observed opponents"):
            command(self.config, self.observation)

    def test_bad_source_rejected(self):
        bad = copy.deepcopy(self.observation)
        bad["ego"]["speed_mps"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite observed"):
            command(self.config, bad)

    def test_steering_uses_waypoint_heading(self):
        self.assertEqual(steering_to_waypoint([0, 0], 45, [5, 5]), 0)
        self.assertGreater(steering_to_waypoint([0, 0], 0, [5, 5]), 0)
        self.assertLess(steering_to_waypoint([0, 0], 90, [5, 5]), 0)


if __name__ == "__main__":
    unittest.main()
