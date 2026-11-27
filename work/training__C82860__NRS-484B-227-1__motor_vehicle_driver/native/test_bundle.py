"""Exact materialized Native request and camera-duration policy."""

import unittest
from pathlib import Path

from runner import check


class ExactBundleTest(unittest.TestCase):
    def test_exact_request(self):
        if not (Path.cwd() / "config.json").is_file():
            self.skipTest("Exact config is materialized in the offline bundle")
        result = check()
        self.assertTrue(result["passed"])
        self.assertEqual(result["frames"], 600)
        self.assertFalse(result["authority_verified"])


if __name__ == "__main__":
    unittest.main()
