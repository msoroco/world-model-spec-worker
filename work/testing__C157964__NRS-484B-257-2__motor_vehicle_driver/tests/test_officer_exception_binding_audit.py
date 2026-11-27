"""CPU checks for the immutable officer exception and compatible sign route."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parents[1] / "officer_exception_binding_audit.py"
SPEC = importlib.util.spec_from_file_location("officer_exception_binding_audit", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OfficerExceptionBindingTests(unittest.TestCase):
    def test_selected_sign_route_and_exception(self):
        receipt = MODULE.audit(REPO)
        self.assertEqual(receipt["fixed_origin_control"], "police_officer")
        self.assertEqual(receipt["target_control"], "yield_sign")
        self.assertEqual(len(receipt["selected_target_case_ids"]), 7)
        self.assertEqual(receipt["original_physical_evidence"], "unverified")

    def test_rejects_lost_statutory_exception(self):
        original = MODULE.read

        def changed(repo, relative):
            data, digest = original(repo, relative)
            if relative.endswith("C157964__NRS-484B-257-2__motor_vehicle_driver/assignment.json"):
                data = copy.deepcopy(data)
                data["law"]["text"] = data["law"]["text"].split(":", 1)[-1]
            return data, digest

        with patch.object(MODULE, "read", changed), self.assertRaisesRegex(ValueError, "officer exception"):
            MODULE.audit(REPO)

    def test_rejects_stale_sign_package(self):
        original = MODULE.read

        def changed(repo, relative):
            data, digest = original(repo, relative)
            if relative.endswith("C158208__NRS-484B-257-2__motor_vehicle_driver/result.json"):
                data = copy.deepcopy(data)
                data["status"] = "partial"
            return data, digest

        with patch.object(MODULE, "read", changed), self.assertRaisesRegex(ValueError, "readiness"):
            MODULE.audit(REPO)

    def test_rejects_missing_occupied_case(self):
        original = MODULE.read

        def changed(repo, relative):
            data, digest = original(repo, relative)
            if relative.endswith("C158208__NRS-484B-257-2__motor_vehicle_driver/execution-manifest.json"):
                data = copy.deepcopy(data)
                data["cases"] = [row for row in data["cases"]
                                 if not row["case_id"].endswith("__occupied_response")]
            return data, digest

        with patch.object(MODULE, "read", changed), self.assertRaisesRegex(ValueError, "within/approaching"):
            MODULE.audit(REPO)


if __name__ == "__main__":
    unittest.main()
