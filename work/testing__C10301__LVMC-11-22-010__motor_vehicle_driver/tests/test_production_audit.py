"""Production commands reject diagnostic originals without creating receipts."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FOLDER))

import production_audit


class ProductionAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = FOLDER.parents[1] / ".runtime-work" / "c10301-production-audit-tests"
        self.scratch.mkdir(parents=True, exist_ok=True)

    def test_diagnostic_case_rejected_without_receipt(self) -> None:
        attempt = FOLDER.parents[1] / ".runtime-work/c10301-010-nov24b/full900-attempt"
        if not attempt.is_dir():
            self.skipTest("diagnostic original attempt scratch absent")
        with tempfile.TemporaryDirectory(dir=self.scratch) as name:
            output = Path(name) / "receipt.json"
            with self.assertRaisesRegex(ValueError, "diagnostic capture cannot be delivered"):
                production_audit.main(["--case", production_audit.STEADY,
                                       "--attempt", str(attempt), "--output", str(output)])
            self.assertFalse(output.exists())

    def test_diagnostic_pair_rejected_without_receipt(self) -> None:
        steady = FOLDER.parents[1] / ".runtime-work/c10301-010-nov24b/full900-attempt"
        variation = FOLDER.parents[1] / ".runtime-work/c10301-010-nov24b/full900-variation-attempt"
        if not steady.is_dir() or not variation.is_dir():
            self.skipTest("diagnostic original attempt scratch absent")
        with tempfile.TemporaryDirectory(dir=self.scratch) as name:
            output = Path(name) / "receipt.json"
            with self.assertRaisesRegex(ValueError, "diagnostic capture cannot be delivered"):
                production_audit.main(["--steady", str(steady), "--variation", str(variation),
                                       "--output", str(output)])
            self.assertFalse(output.exists())

    def test_no_overwrite_and_selected_binding(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.scratch) as name:
            output = Path(name) / "receipt.json"
            output.write_text("retained\n")
            with self.assertRaisesRegex(ValueError, "audit output already exists"):
                production_audit.main(["--case", production_audit.STEADY,
                                       "--attempt", name, "--output", str(output)])
            self.assertEqual(output.read_text(), "retained\n")
        entry = production_audit._selected(production_audit.STEADY)
        self.assertEqual(entry["case_id"], production_audit.STEADY)
        with self.assertRaisesRegex(ValueError, "case absent from selected manifest"):
            production_audit._selected("foreign-case")


if __name__ == "__main__":
    unittest.main()
