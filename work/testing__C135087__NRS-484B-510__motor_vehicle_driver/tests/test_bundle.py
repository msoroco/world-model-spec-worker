"""Bundled exact-construction checks executed by runtime.py offline."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import check


class BundleTests(unittest.TestCase):
    def test_exact_capture_contract(self):
        config = json.loads(Path(__file__).resolve().parents[1].joinpath("config.json").read_text())
        self.assertTrue(check(config))
        with self.assertRaisesRegex(ValueError, "camera"):
            check({**config, "cameras": config["cameras"][:3]})
        with self.assertRaisesRegex(ValueError, "20 Hz"):
            check({**config, "frame_count": 899})


if __name__ == "__main__":
    unittest.main()
