"""Selected materialized taxi config must match its planned exact case."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner import selected_case


class ExactTaxiCaseConfigTests(unittest.TestCase):
    def test_selected_case_and_source_scope(self):
        config = json.loads((ROOT / "config.json").read_text())
        case = selected_case(config)
        self.assertEqual(case["case_id"], config["selected_case_id"])
        self.assertEqual(case["target_law_id"], config["law_id"])
        self.assertIn(case["location_request"], ("in_stand", "outside_stand"))


if __name__ == "__main__":
    unittest.main()
