"""Offline bundle check for each exact case without contacting Native."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import check


class BundleSmoke(unittest.TestCase):
    def test_exact_case_and_camera_contract(self):
        config = check()
        self.assertEqual(config["selected_case_id"].rsplit("__", 1)[1], config["variant"])
        self.assertEqual(config["duration_s"] * config["rate_hz"], 900)
        self.assertEqual(len(config["cameras"]), 4)


if __name__ == "__main__":
    unittest.main()
