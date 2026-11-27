"""Portable static checks for a distinct excavated highway surface."""
import json
import unittest
from pathlib import Path

from runner import check as check_runner, confirm_depressed_surface
from excavation_geometry import check as check_geometry


class ExcavationBundleTests(unittest.TestCase):
    def test_exact_request_and_surface(self):
        cfg = json.loads(Path("config.json").read_text())
        self.assertEqual(cfg["obstruction_kind_request"], "excavation")
        self.assertTrue(check_runner(Path("config.json"))["passed"])
        self.assertTrue(check_geometry()["passed"])

    def test_native_flat_surface_rejected(self):
        self.assertEqual(confirm_depressed_surface({
            "left_before": 0, "left_trench": -1,
            "left_after": 0, "right_parallel": 0})["left_trench"], -1)
        with self.assertRaisesRegex(ValueError, "did not materialize"):
            confirm_depressed_surface({
                "left_before": 0, "left_trench": 0,
                "left_after": 0, "right_parallel": 0})


if __name__ == "__main__":
    unittest.main()
