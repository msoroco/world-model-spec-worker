"""Portable offline checks for either exact obstruction comparison case."""
import json
import unittest
from pathlib import Path

from geometry import check as geometry_check
from runner import check as runner_check


class BundleTests(unittest.TestCase):
    def test_exact_construction(self):
        config = Path("config.json")
        proof = runner_check(config)
        self.assertTrue(proof["passed"])
        self.assertFalse(proof["native_executed"])
        self.assertFalse(proof["physical_acceptance_claimed"])
        self.assertEqual(json.loads(config.read_text())["case_id"], proof["case_id"])

    def test_authored_geometry(self):
        geometry = geometry_check()
        self.assertTrue(geometry["passed"])
        self.assertFalse(geometry["native_readback_observed"])
        self.assertLess(geometry["authored_openings_m"]["condition_a"], 1.8)
        self.assertGreater(geometry["authored_openings_m"]["condition_b"], 1.8)


if __name__ == "__main__":
    unittest.main()
