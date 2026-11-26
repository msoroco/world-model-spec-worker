"""Materialized exact-case bundle checks; no Native server is contacted."""

import json
from pathlib import Path
import unittest

from runner import selected
from pass_controller import Observation, command_for_case


ROOT = Path(__file__).resolve().parents[1]


class BundleTests(unittest.TestCase):
    def test_exact_case_config_and_initial_source_policy(self):
        _, case = selected(ROOT)
        count = case["same_direction_lane_count_requested"]
        occupied = case["left_lane_traffic_requested"] == "occupied"
        sample = Observation("right", "right", "left" if count == 2 else None,
                             count, 12.0, 3.0, ("other",) if occupied else (),
                             False, False, 100)
        intent = command_for_case(case, sample)
        self.assertEqual(intent["source_frame"], 100)
        self.assertIsNone(json.loads((ROOT / "config.json").read_text())
                          .get("legal_verdict"))


if __name__ == "__main__":
    unittest.main()
