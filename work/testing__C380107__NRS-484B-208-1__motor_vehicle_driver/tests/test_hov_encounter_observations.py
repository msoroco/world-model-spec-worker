"""Focused source-integrity and encounter tests; fixtures are not delivery evidence."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("hov_encounter_observations", PACKAGE / "hov_encounter_observations.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASE = MODULE.ASSIGNMENT_ID + "__qualified_hov"


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


class EncounterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.context, self.trace, self.receipt = (root / x for x in ("context.json", "trace.jsonl", "receipt.json"))
        self.context_value = {"case_id": CASE, "same_direction_lane_ids": ["left", "right"],
                              "extreme_left_lane_id": "left", "posted_limit_mps": 25,
                              "hov_designation_state": "active", "hov_compliance_state": "unresolved"}
        for field in ("controlled_access_source", "lane_marking_source", "extreme_left_lane_source",
                      "posted_limit_source", "geographical_boundary_source", "driver_identity_source",
                      "motor_vehicle_source", "hov_designation_source", "hov_hours_source",
                      "hov_occupancy_rule_source", "hov_access_source", "hov_sign_source",
                      "hov_vehicle_category_source", "hov_compliance_source", "knowledge_circumstances_source",
                      "other_exceptions_source"):
            self.context_value[field] = "original-context-ref:" + field
        self.rows = [{"frame": i, "time_s": i / 20, "ego_lane_id": "left", "rear_lane_id": "left",
                      "ego_speed_mps": 20, "rear_speed_mps": 22,
                      "rear_to_ego_signed_gap_m": gap} for i, gap in enumerate((.1, -.01, -.12))]
        self.refresh()

    def refresh(self):
        write_json(self.context, self.context_value)
        self.trace.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in self.rows), encoding="utf-8")
        write_json(self.receipt, {"assignment_id": MODULE.ASSIGNMENT_ID, "case_id": CASE,
                                  "source_kind": "original_native_capture", "diagnostic_fixture": False,
                                  "fps": 20, "frame_count": len(self.rows),
                                  "context_sha256": hashlib.sha256(self.context.read_bytes()).hexdigest(),
                                  "trace_sha256": hashlib.sha256(self.trace.read_bytes()).hexdigest()})

    def measure(self):
        return MODULE.observe(CASE, self.context, self.trace, self.receipt)

    def test_plan_contains_hov_and_core_controls(self):
        plan = json.loads((PACKAGE / "case-plan.json").read_text(encoding="utf-8"))
        self.assertEqual(len(plan["cases"]), 9)
        self.assertEqual(len(plan["comparisons"]), 8)

    def test_source_bound_encounter_keeps_legal_judgments_open(self):
        result = self.measure()
        self.assertEqual(result["first_rear_gap_crossing_frame"], 1)
        self.assertTrue(result["samples"][0]["ego_below_posted_limit"])
        self.assertEqual(result["hov_legal_exception_judgment"], "unresolved")

    def test_diagnostic_source_rejected(self):
        receipt = json.loads(self.receipt.read_text())
        receipt["diagnostic_fixture"] = True
        write_json(self.receipt, receipt)
        with self.assertRaisesRegex(ValueError, "original Native"):
            self.measure()

    def test_changed_trace_rejected(self):
        self.trace.write_text(self.trace.read_text() + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.measure()

    def test_missing_hov_compliance_source_rejected(self):
        del self.context_value["hov_compliance_source"]
        self.refresh()
        with self.assertRaisesRegex(ValueError, "hov_compliance_source"):
            self.measure()

    def test_same_speed_rear_is_not_faster(self):
        for row in self.rows:
            row["rear_speed_mps"] = 20
        self.refresh()
        result = self.measure()
        self.assertIsNone(result["first_rear_gap_crossing_frame"])

    def test_bad_lane_identity_rejected(self):
        self.rows[1]["rear_lane_id"] = "unknown"
        self.refresh()
        with self.assertRaisesRegex(ValueError, "lane identity"):
            self.measure()


if __name__ == "__main__":
    unittest.main()
