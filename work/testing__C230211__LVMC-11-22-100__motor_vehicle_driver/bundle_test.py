"""Focused materialized-bundle identity and source-gate checks."""

import json
from pathlib import Path
import unittest

from package_spec import AID, ACTOR, CELL, LAW
from pavement_protection import CASES


class BundleTests(unittest.TestCase):
    def test_exact_case_and_capture_contract(self):
        config = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())
        self.assertEqual((config["assignment_id"], config["law_id"],
                          config["cell_id"], config["actor"]),
                         (AID, LAW, CELL, ACTOR))
        self.assertEqual(config["duration_s"] * config["rate_hz"], 900)
        self.assertEqual(len(config["cameras"]), 4)
        self.assertIn(config["selected_case_id"], config["supported_case_ids"])
        self.assertIn(config["selected_case_id"].removeprefix(AID + "__"),
                      [case.name for case in CASES])


if __name__ == "__main__":
    unittest.main()
