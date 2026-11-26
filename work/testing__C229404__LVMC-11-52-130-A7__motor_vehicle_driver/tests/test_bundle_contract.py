"""Offline exact identity and source-gated Native import contract."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

import runner
import native_driveway


class BundleContractTest(unittest.TestCase):
    def test_exact_case_and_lazy_native_import(self):
        selected = runner.check()
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "config.json").read_text())
        self.assertEqual(selected, config["selected_case_id"])
        self.assertEqual(config["source_requirements"][0], "reviewed_driveway_packet")
        self.assertTrue(callable(native_driveway.capture))
        self.assertEqual(tuple(config["cameras"][i]["name"] for i in range(4)),
                         native_driveway.CAMERAS)


if __name__ == "__main__":
    unittest.main()
