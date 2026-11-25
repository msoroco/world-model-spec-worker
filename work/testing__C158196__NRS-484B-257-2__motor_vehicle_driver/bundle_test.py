"""Materialized exact-case CPU checks used by runtime.py offline."""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner import check, run_native


class ExactBundleTest(unittest.TestCase):
    def test_exact_case_and_source_gate(self):
        config = json.loads((ROOT / "config.json").read_text())
        receipt = check(ROOT)
        self.assertEqual(receipt["case_id"], config["selected_case_id"])
        self.assertFalse(receipt["physical_acceptance_claimed"])
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "source-reviewed original"):
                run_native(ROOT, "127.0.0.1", 2000)


if __name__ == "__main__":
    unittest.main()
