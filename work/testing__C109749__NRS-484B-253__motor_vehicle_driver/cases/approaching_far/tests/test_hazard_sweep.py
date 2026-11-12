"""Exercise the materialized far-approach controller's measured decision path."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hazard_sweep_policy import HazardSweepPolicy


class FarApproachPolicyTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config.json").read_text())

    def decide(self, distance, speed, inside=False):
        policy = HazardSweepPolicy(
            release_ttc_s=self.config["controller_release_ttc_s"],
            approach_speed_mps=self.config["approach_speed_mps"],
        )
        return policy.step(
            distance_to_hold_m=1.0, ego_speed_mps=0.0,
            oncoming_distance_to_conflict_m=distance,
            oncoming_closing_speed_mps=speed,
            oncoming_in_intersection=inside,
            oncoming_cleared=False,
            turn_complete=False,
        )

    def test_far_approach_can_turn_before_other_body_enters(self):
        command = self.decide(24.0, 2.0)
        self.assertEqual(command["state"], "turn")
        self.assertEqual(command["brake"], 0.0)

    def test_close_approach_and_occupied_junction_yield(self):
        self.assertEqual(self.decide(4.0, 2.0)["state"], "yield")
        self.assertEqual(self.decide(24.0, 2.0, inside=True)["state"], "yield")

    def test_engineering_boundary_is_not_legal_verdict(self):
        release = self.config["controller_release_ttc_s"]
        self.assertEqual(self.decide(release * 2.0 - 0.01, 2.0)["state"], "yield")
        self.assertEqual(self.decide(release * 2.0, 2.0)["state"], "turn")
        self.assertIsNone(self.config["hazard_legal_threshold"])


if __name__ == "__main__":
    unittest.main()
