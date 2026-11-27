"""Synthetic unit fixtures test measurement integrity, not physical delivery."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("emergency_movement_observations", PACKAGE / "emergency_movement_observations.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASE = MODULE.ASSIGNMENT_ID + "__visible_movement_preparation"


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


class MovementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.context, self.trace, self.receipt = (root / n for n in ("context.json", "trace.jsonl", "receipt.json"))
        self.context_value = {"case_id": CASE, "target_vehicle_class": "authorized_emergency",
                              "light_qualification_state": "qualified", "officer_direction_state": "none"}
        for field in ("subject_driver_source", "subject_vehicle_source", "approach_route_source",
                      "emergency_or_official_status_source", "regulatory_agency_source",
                      "flashing_equipment_qualification_source", "light_use_source",
                      "driver_view_camera_source", "visibility_annotation_source",
                      "vehicle_movement_source", "hand_signal_source", "officer_direction_source",
                      "subject_control_source"):
            self.context_value[field] = "original-context-ref:" + field
        self.rows = [{"frame": i, "time_s": i / 20, "ego_position_xy_m": [i * .4, 0],
                      "target_position_xy_m": [20 + shift, 0], "ego_speed_mps": 8,
                      "flashing_lights_active": True, "movement_visible_in_driver_view": True,
                      "hand_signal_visible_in_driver_view": False}
                     for i, shift in enumerate((0, .1, .2))]
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

    def test_plan_controls(self):
        plan = json.loads((PACKAGE / "case-plan.json").read_text(encoding="utf-8"))
        self.assertEqual((len(plan["cases"]), len(plan["comparisons"])), (11, 10))

    def test_visible_movement_is_measured_without_legal_cutoff(self):
        result = self.observe()
        self.assertEqual(result["first_visible_nonzero_movement_frame"], 1)
        self.assertEqual(result["about_to_move_judgment"], "unresolved")
        self.assertEqual(result["reasonable_and_proper_speed_judgment"], "unresolved")

    def test_occluded_movement_not_reported_visible(self):
        for row in self.rows:
            row["movement_visible_in_driver_view"] = False
        self.refresh()
        self.assertIsNone(self.observe()["first_visible_nonzero_movement_frame"])

    def test_diagnostic_receipt_rejected(self):
        value = json.loads(self.receipt.read_text())
        value["diagnostic_fixture"] = True
        write(self.receipt, value)
        with self.assertRaisesRegex(ValueError, "original Native"):
            self.observe()

    def test_changed_trace_rejected(self):
        self.trace.write_text(self.trace.read_text() + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.observe()

    def test_missing_visibility_source_rejected(self):
        del self.context_value["visibility_annotation_source"]
        self.refresh()
        with self.assertRaisesRegex(ValueError, "visibility_annotation_source"):
            self.observe()

    def test_missing_light_state_rejected(self):
        del self.rows[1]["flashing_lights_active"]
        self.refresh()
        with self.assertRaisesRegex(ValueError, "light and driver-view"):
            self.observe()


if __name__ == "__main__":
    unittest.main()
