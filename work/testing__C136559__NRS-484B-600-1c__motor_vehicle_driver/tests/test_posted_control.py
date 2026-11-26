import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from posted_control import command, target_speed


class PostedControlTests(unittest.TestCase):
    def test_requested_relation_and_equivalent_unit(self):
        site = {"rate": 25, "unit": "mph"}
        below = target_speed(site, {"rate_relation": "below"})
        equal = target_speed(site, {"rate_relation": "equal"})
        above = target_speed(site, {"rate_relation": "above"})
        self.assertLess(below, equal)
        self.assertLess(equal, above)
        self.assertAlmostEqual(equal, target_speed({"rate": 40.2336, "unit": "km/h"},
                                                  {"rate_relation": "equal"}))

    def test_fallback_gain_changes_control_not_target(self):
        primary = command(10, 12, 0.3)
        fallback = command(10, 12, 0.45)
        self.assertGreater(fallback[0], primary[0])
        self.assertEqual(primary[1], fallback[1])

    def test_braking_and_invalid_source(self):
        self.assertGreater(command(14, 12, 0.3)[1], 0)
        with self.assertRaises(ValueError):
            target_speed({"rate": 25, "unit": "unknown"}, {"rate_relation": "above"})
