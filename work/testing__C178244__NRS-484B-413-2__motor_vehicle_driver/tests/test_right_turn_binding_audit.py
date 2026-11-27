"""Reject stale or incomplete cross-cell right-turn CPU allocations."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parents[1] / "right_turn_binding_audit.py"
SPEC = importlib.util.spec_from_file_location("right_turn_binding_audit", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BindingAuditTests(unittest.TestCase):
    def test_current_selected_right_turn_route(self):
        report = MODULE.audit(REPO)
        self.assertEqual(report["frozen_origin_maneuver"], "left_turn")
        self.assertEqual(report["target_maneuver"], "right_turn")
        self.assertEqual(len(report["selected_target_case_ids"]), 5)

    def test_rejects_stale_target_readiness(self):
        original = MODULE.read

        def changed(repo, relative):
            data, digest = original(repo, relative)
            if relative.endswith("C378304__NRS-484B-413-2__motor_vehicle_driver/result.json"):
                data = copy.deepcopy(data)
                data["status"] = "partial"
            return data, digest

        with patch.object(MODULE, "read", changed), self.assertRaisesRegex(ValueError, "readiness"):
            MODULE.audit(REPO)

    def test_rejects_changed_target_selected_branch(self):
        original = MODULE.read

        def changed(repo, relative):
            data, digest = original(repo, relative)
            if relative.endswith("C378304__NRS-484B-413-2__motor_vehicle_driver/assignment.json"):
                data = copy.deepcopy(data)
                data["branches"][0]["branch"] = "Residential-district right-turn signaling"
            return data, digest

        with patch.object(MODULE, "read", changed), self.assertRaisesRegex(ValueError, "target selected branch"):
            MODULE.audit(REPO)

    def test_rejects_changed_origin_selected_branch(self):
        original = MODULE.read

        def changed(repo, relative):
            data, digest = original(repo, relative)
            if relative.endswith("C178244__NRS-484B-413-2__motor_vehicle_driver/assignment.json"):
                data = copy.deepcopy(data)
                data["branches"][0]["branch"] = "Business-district left-turn signaling"
            return data, digest

        with patch.object(MODULE, "read", changed), self.assertRaisesRegex(ValueError, "origin selected branch"):
            MODULE.audit(REPO)

    def test_rejects_missing_100_foot_case(self):
        original = MODULE.read

        def changed(repo, relative):
            data, digest = original(repo, relative)
            if relative.endswith("C378304__NRS-484B-413-2__motor_vehicle_driver/execution-manifest.json"):
                data = copy.deepcopy(data)
                data["cases"] = [row for row in data["cases"]
                                 if not row["case_id"].endswith("__continuous100")]
            return data, digest

        with patch.object(MODULE, "read", changed), self.assertRaisesRegex(ValueError, "selected cases"):
            MODULE.audit(REPO)


if __name__ == "__main__":
    unittest.main()
