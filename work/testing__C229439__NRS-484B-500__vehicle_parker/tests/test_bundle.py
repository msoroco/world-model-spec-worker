import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_parking import control
from runner import config


class BundleTests(unittest.TestCase):
    def test_frozen_case_and_halt_control(self):
        value = config()
        self.assertIn(value["case"]["requested_conduct"], ("stop", "stand", "park"))
        self.assertEqual(value["rate_hz"], 20)
        self.assertEqual(control(0.5, 0, "hold", "park"),
                         {"throttle": 0.0, "brake": 1.0, "hand_brake": True})
        self.assertFalse(control(0.5, 0, "hold", "stand")["hand_brake"])

    def test_approach_brakes_from_measured_distance(self):
        self.assertEqual(control(1, 5, "approach", "stop")["brake"], 0.65)
        self.assertGreater(control(20, 0, "approach", "stop")["throttle"], 0)


if __name__ == "__main__":
    unittest.main()
