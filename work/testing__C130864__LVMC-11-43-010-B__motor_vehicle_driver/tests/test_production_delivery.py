"""Production gates reject CPU fixtures and missing independent review."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from production_comparison import audit_pair
from production_delivery import audit_original
from roundabout_measurements import ASSIGNMENT_ID


class ProductionDeliveryTests(unittest.TestCase):
    def test_diagnostic_attempt_rejected_before_review(self):
        repo = ROOT.parents[1]
        attempt = repo / ".runtime-work/c130864-compat-selected/connected_enter/primary"
        with self.assertRaisesRegex(ValueError, "missing original saved source"):
            audit_original(attempt, ASSIGNMENT_ID + "__connected_enter", {})

    def test_unsealed_attempt_rejected(self):
        with tempfile.TemporaryDirectory(
                dir=ROOT.parents[1] / ".runtime-work") as directory:
            with self.assertRaisesRegex(ValueError, "missing original saved source"):
                audit_original(Path(directory), ASSIGNMENT_ID + "__connected_enter", {})

    def test_same_attempt_comparison_rejected(self):
        with tempfile.TemporaryDirectory(
                dir=ROOT.parents[1] / ".runtime-work") as directory:
            path = Path(directory)
            with self.assertRaisesRegex(ValueError, "distinct original attempts"):
                audit_pair("connected_entry", path, path, {}, {})

    def test_unknown_comparison_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown exact roundabout comparison"):
            audit_pair("invented", Path("."), Path(".."), {}, {})


if __name__ == "__main__":
    unittest.main()
