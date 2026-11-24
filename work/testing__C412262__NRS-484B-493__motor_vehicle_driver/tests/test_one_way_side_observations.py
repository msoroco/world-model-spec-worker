"""Synthetic unit fixtures test source integrity and side geometry only."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("one_way_side_observations", PACKAGE / "one_way_side_observations.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASE = MODULE.ASSIGNMENT_ID + "__park_left_notice"


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


class SideTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.context, self.trace, self.receipt = (root / name for name in ("context.json", "trace.jsonl", "receipt.json"))
        self.context_value = {"case_id": CASE, "one_way_status": "one_way",
                              "notice_state": "erected_applicable",
                              "permitted_direction_centerline_xy_m": [[0, 0], [20, 0]]}
        for field in ("street_legal_status_source", "street_boundary_source", "public_access_source",
                      "city_limits_source", "one_way_order_source", "permitted_direction_source",
                      "centerline_source", "notice_erection_source", "notice_authority_source",
                      "notice_exact_content_source", "notice_conformity_source", "notice_extent_source",
                      "person_identity_source", "vehicle_identity_source", "halt_purpose_source",
                      "service_activity_source", "occupancy_source"):
            self.context_value[field] = "original-context-ref:" + field
        self.rows = [{"frame": i, "time_s": i / 20, "vehicle_speed_mps": 0,
                      "vehicle_center_xy_m": [10, 3],
                      "vehicle_body_polygon_xy_m": [[9, 2], [11, 2], [11, 4], [9, 4]]} for i in range(2)]
        self.refresh()

    def refresh(self):
        write(self.context, self.context_value)
        self.trace.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in self.rows), encoding="utf-8")
        write(self.receipt, {"assignment_id": MODULE.ASSIGNMENT_ID, "case_id": CASE,
                             "source_kind": "original_native_capture", "diagnostic_fixture": False,
                             "fps": 20, "frame_count": len(self.rows),
                             "context_sha256": hashlib.sha256(self.context.read_bytes()).hexdigest(),
                             "trace_sha256": hashlib.sha256(self.trace.read_bytes()).hexdigest()})

    def observe(self):
        return MODULE.observe(CASE, self.context, self.trace, self.receipt)

    def test_plan_has_side_notice_activity_controls(self):
        plan = json.loads((PACKAGE / "case-plan.json").read_text(encoding="utf-8"))
        self.assertEqual((len(plan["cases"]), len(plan["comparisons"])), (9, 8))

    def test_left_offset_measured_without_legal_side_cutoff(self):
        out = self.observe()
        self.assertEqual(out["samples"][0]["vehicle_center_signed_left_offset_m"], 3)
        self.assertEqual(out["samples"][0]["body_signed_left_offset_range_m"], [2, 4])
        self.assertEqual(out["left_hand_side_judgment"], "unresolved")

    def test_reverse_direction_changes_sign(self):
        self.context_value["permitted_direction_centerline_xy_m"] = [[20, 0], [0, 0]]
        self.refresh()
        self.assertEqual(self.observe()["samples"][0]["vehicle_center_signed_left_offset_m"], -3)

    def test_diagnostic_source_rejected(self):
        receipt = json.loads(self.receipt.read_text())
        receipt["diagnostic_fixture"] = True
        write(self.receipt, receipt)
        with self.assertRaisesRegex(ValueError, "original Native"):
            self.observe()

    def test_changed_trace_rejected(self):
        self.trace.write_text(self.trace.read_text() + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.observe()

    def test_missing_notice_content_rejected(self):
        del self.context_value["notice_exact_content_source"]
        self.refresh()
        with self.assertRaisesRegex(ValueError, "notice_exact_content_source"):
            self.observe()

    def test_zero_centerline_segment_rejected(self):
        self.context_value["permitted_direction_centerline_xy_m"] = [[0, 0], [0, 0]]
        self.refresh()
        with self.assertRaisesRegex(ValueError, "nonzero"):
            self.observe()


if __name__ == "__main__":
    unittest.main()
