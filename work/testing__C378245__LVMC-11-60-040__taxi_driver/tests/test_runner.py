"""Exact selection and fail-closed source gate without a CARLA import."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
import runner

SCRATCH = REPO / ".runtime-work/c378245-runner-tests"
SCRATCH.mkdir(parents=True, exist_ok=True)


class TaxiRunnerTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config.json").read_text())

    def test_selected_case_matches_frozen_plan(self):
        case = runner.selected_case(self.config)
        self.assertEqual(case["location_request"], "outside_stand")
        self.assertEqual(case["halt_activity_request"], "park")

    def test_unselected_case_rejected(self):
        self.config["selected_case_id"] += "_changed"
        with self.assertRaisesRegex(ValueError, "configuration differs"):
            runner.selected_case(self.config)

    def test_bad_original_site_rejected_before_native_import(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as name:
            path = Path(name) / "site.json"
            path.write_text("{}")
            output = Path(name) / "attempt"
            output.mkdir()
            before = "carla" in sys.modules
            with self.assertRaisesRegex(ValueError, "SHA256"):
                runner.execute(self.config, path, "0" * 64, output, "127.0.0.1", 2000)
            self.assertEqual("carla" in sys.modules, before)


if __name__ == "__main__":
    unittest.main()
