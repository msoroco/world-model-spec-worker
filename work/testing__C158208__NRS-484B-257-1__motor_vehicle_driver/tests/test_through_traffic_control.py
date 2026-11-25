"""Through-highway actor receives a real scheduled Native control command."""

from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from through_traffic_control import control, validate_plan


class ThroughTrafficControlTests(unittest.TestCase):
    def test_scheduled_hold_then_route_motion(self):
        plan = {"target_speed_mps": 5.0, "start_delay_s": 2.0,
                "steering_mode": "follow_reviewed_route_axis"}
        self.assertEqual(control(plan, 1.0, 0.0)["engineering_state"], "scheduled_hold")
        moving = control(plan, 2.0, 0.0)
        self.assertEqual(moving["engineering_state"], "through_route_motion")
        self.assertGreater(moving["throttle"], 0)
        self.assertEqual(moving["steer"], 0)
        self.assertGreater(control(plan, 5.0, 9.0)["brake"], 0)

    def test_no_silent_stationary_or_unsourced_schedule(self):
        with self.assertRaisesRegex(ValueError, "motion plan required"):
            validate_plan(None)
        with self.assertRaisesRegex(ValueError, "engineering capture range"):
            validate_plan({"target_speed_mps": 0, "start_delay_s": 0,
                           "steering_mode": "follow_reviewed_route_axis"})
        with self.assertRaisesRegex(ValueError, "reviewed route axis"):
            validate_plan({"target_speed_mps": 5, "start_delay_s": 0,
                           "steering_mode": "teleport"})


if __name__ == "__main__":
    unittest.main()
