"""Synthetic unit fixtures exercise source integrity and geometry only."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("crosswalk_clearance", PACKAGE / "crosswalk_clearance.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASE = MODULE.ASSIGNMENT_ID + "__destination_inside_20ft"


def write(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True) + "\n", encoding="utf-8")


class ClearanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.context, self.trace, self.receipt = (root / x for x in ("context.json", "trace.jsonl", "receipt.json"))
        self.context_value = {"case_id": CASE, "marked_crosswalk_polygon_xy_m": [[0, 0], [2, 0], [2, 2], [0, 2]]}
        for field in ("jurisdiction_source", "marked_crosswalk_source", "vehicle_identity_source",
                      "responsible_person_source", "destination_purpose_source", "service_activity_source",
                      "traffic_conflict_source", "law_compliance_source", "officer_direction_source",
                      "traffic_device_direction_source", "crosswalk_extent_source"):
            self.context_value[field] = "original-context-ref:" + field
        self.rows = [{"frame": i, "time_s": i / 20, "ego_speed_mps": 0,
                      "ego_body_polygon_xy_m": [[8, 0], [10, 0], [10, 2], [8, 2]]} for i in range(2)]
        self.refresh()

    def refresh(self):
        write(self.context, self.context_value)
        self.trace.write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in self.rows), encoding="utf-8")
        write(self.receipt, {"assignment_id": MODULE.ASSIGNMENT_ID, "case_id": CASE,
                             "source_kind": "original_native_capture", "diagnostic_fixture": False,
                             "fps": 20, "frame_count": len(self.rows),
                             "context_sha256": hashlib.sha256(self.context.read_bytes()).hexdigest(),
                             "trace_sha256": hashlib.sha256(self.trace.read_bytes()).hexdigest()})

    def measure(self):
        return MODULE.measure(CASE, self.context, self.trace, self.receipt)

    def test_plan_has_geometry_and_exception_controls(self):
        plan = json.loads((PACKAGE / "case-plan.json").read_text(encoding="utf-8"))
        self.assertEqual((len(plan["cases"]), len(plan["comparisons"])), (9, 8))

    def test_original_body_clearance_preserves_legal_uncertainty(self):
        out = self.measure()
        self.assertAlmostEqual(out["closest_body_to_marked_crosswalk_clearance_m"], 6)
        self.assertEqual(out["legal_measurement_convention"], "unresolved")

    def test_overlap_and_containment(self):
        crosswalk = MODULE.polygon([[0, 0], [2, 0], [2, 2], [0, 2]])
        self.assertEqual(MODULE.clearance(MODULE.polygon([[1, 1], [3, 1], [3, 3], [1, 3]]), crosswalk), 0)
        self.assertEqual(MODULE.clearance(MODULE.polygon([[-1, -1], [3, -1], [3, 3], [-1, 3]]), crosswalk), 0)

    def test_changed_trace_rejected(self):
        self.trace.write_text(self.trace.read_text() + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.measure()

    def test_diagnostic_receipt_rejected(self):
        receipt = json.loads(self.receipt.read_text())
        receipt["diagnostic_fixture"] = True
        write(self.receipt, receipt)
        with self.assertRaisesRegex(ValueError, "original Native"):
            self.measure()

    def test_missing_marking_source_rejected(self):
        del self.context_value["marked_crosswalk_source"]
        self.refresh()
        with self.assertRaisesRegex(ValueError, "marked_crosswalk_source"):
            self.measure()

    def test_invalid_body_geometry_rejected(self):
        self.rows[0]["ego_body_polygon_xy_m"] = [[0, 0], [0, 0], [0, 0]]
        self.refresh()
        with self.assertRaisesRegex(ValueError, "nondegenerate"):
            self.measure()


if __name__ == "__main__":
    unittest.main()
