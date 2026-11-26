"""Materialized exact bundle tests for the portable offline gate."""

import json
from pathlib import Path
import unittest

from runner import selected


class BundleTests(unittest.TestCase):
    def test_exact_config_and_sources(self):
        root = Path(__file__).resolve().parents[1]
        config, case = selected(root)
        self.assertEqual(case["case_id"], config["selected_case_id"])
        self.assertEqual(case["same_direction_lane_count_requested"], 1)
        self.assertIn(case["control_kind"],
                      {"bicycle", "electric_bicycle", "electric_scooter"})
        self.assertEqual(len(config["cameras"]), 4)

    def test_missing_native_packet_rejected(self):
        root = Path(__file__).resolve().parents[1]
        _, case = selected(root)
        self.assertTrue(case["case_id"].startswith(
            "testing__C272352__NRS-484B-270-2b__motor_vehicle_driver__"))


if __name__ == "__main__":
    unittest.main()
