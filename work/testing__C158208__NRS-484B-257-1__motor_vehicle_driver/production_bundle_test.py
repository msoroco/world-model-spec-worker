"""Self-check for a materialized production construction."""
import json
from pathlib import Path
import unittest
from runner import check


class ProductionBundleTests(unittest.TestCase):
    def test_exact_source_bound_case_and_capture_profile(self):
        selected = check()
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "config.json").read_text())
        self.assertEqual(selected["case_id"], config["selected_case_id"])
        self.assertEqual(config["rate_hz"] * config["duration_s"], 900)
        self.assertEqual(config["cameras"], ["overview", "approach",
                                              "reference_corner", "driver_reference"])


if __name__ == "__main__":
    unittest.main()
