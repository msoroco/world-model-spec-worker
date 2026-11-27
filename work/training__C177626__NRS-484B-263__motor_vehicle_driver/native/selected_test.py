"""Offline exact case identity and source plan checks."""

import json
from pathlib import Path
import unittest

import runner


class TestSelectedEntry(unittest.TestCase):
    def test_exact_case_and_source_plan(self):
        config = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())
        proposal = runner.check(config)
        self.assertEqual(proposal["duration_s"], 30)
        self.assertEqual(proposal["rate_hz"], 20)
        self.assertEqual(len(proposal["camera_views"]), 4)
        self.assertEqual(proposal["geometry"]["access_road_ids"], [3, 13])
        self.assertEqual(proposal["geometry"]["highway_road_ids"], [1, 2, 4])
        self.assertFalse(proposal["geometry"]["controlled_access_designation_verified"])
        self.assertFalse(proposal["physical_success_claimed"])


if __name__ == "__main__":
    unittest.main()
