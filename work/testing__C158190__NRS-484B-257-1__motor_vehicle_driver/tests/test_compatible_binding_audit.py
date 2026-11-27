"""Allocation checks for the fixed stop/yield control conflict."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
MODULE = Path(__file__).resolve().parents[1] / "compatible_binding_audit.py"
SPEC = importlib.util.spec_from_file_location("compatible_binding_audit", MODULE)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class CompatibleBindingAuditTest(unittest.TestCase):
    def test_exact_selected_route(self):
        receipt = AUDIT.audit(REPO)
        self.assertEqual(receipt["target_fixed_control"], "yield_sign")
        self.assertEqual(len(receipt["nearest_view_selected_case_ids"]), 3)
        self.assertEqual(receipt["original_physical_evidence"], "unverified")

    def test_rejects_stale_target_readiness(self):
        original = AUDIT.read

        def changed(repo, name):
            value, digest = original(repo, name)
            if name.endswith("C158208__NRS-484B-257-1__motor_vehicle_driver/result.json"):
                value = copy.deepcopy(value)
                value["status"] = "partial"
            return value, digest

        with patch.object(AUDIT, "read", changed), self.assertRaisesRegex(ValueError, "readiness"):
            AUDIT.audit(REPO)

    def test_rejects_missing_nearest_view_case(self):
        original = AUDIT.read

        def changed(repo, name):
            value, digest = original(repo, name)
            if name.endswith("C158208__NRS-484B-257-1__motor_vehicle_driver/execution-manifest.json"):
                value = copy.deepcopy(value)
                value["cases"] = [row for row in value["cases"]
                                  if not row["case_id"].endswith("__nearest_view_stopped")]
            return value, digest

        with patch.object(AUDIT, "read", changed), self.assertRaisesRegex(ValueError, "selected nearest-view"):
            AUDIT.audit(REPO)


if __name__ == "__main__":
    unittest.main()
