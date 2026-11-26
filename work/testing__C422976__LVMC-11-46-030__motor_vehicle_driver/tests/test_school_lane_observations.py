"""Synthetic unit fixtures test measurement integrity, not physical delivery."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("school_lane_observations", PACKAGE / "school_lane_observations.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASE = MODULE.ASSIGNMENT_ID + "__human_warning_stop_51ft_go"


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


class SchoolLaneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.context, self.trace, self.receipt = (root / name for name in ("context.json", "trace.jsonl", "receipt.json"))
        self.context_value = {"case_id": CASE, "school_lane_nearest_side_station_m": 100,
                              "vehicle_reference_point": "front_body_extent"}
        for field in ("municipal_jurisdiction_source", "school_pedestrian_lane_source",
                      "nearest_side_geometry_source", "ego_connected_approach_source",
                      "road_lane_identity_source", "responsible_person_source", "vehicle_source",
                      "stationed_person_identity_source", "human_warning_source",
                      "children_presence_source", "human_signal_source", "person_location_source",
                      "vehicle_body_reference_source", "driver_view_camera_source"):
            self.context_value[field] = "original-context-ref:" + field
        self.rows = [{"frame": i, "time_s": i / 20, "ego_speed_mps": speed,
                      "ego_reference_station_m": 100 - 51 * .3048,
                      "human_warning_active": True, "person_stationed": True,
                      "children_about_to_cross_or_crossing": True,
                      "human_go_signal": i == 2, "human_left_locality": False,
                      "device_signal_stopped_raised_or_removed": False}
                     for i, speed in enumerate((1, 0, 0))]
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

    def test_plan_has_human_and_device_release_controls(self):
        plan = json.loads((PACKAGE / "case-plan.json").read_text(encoding="utf-8"))
        self.assertEqual((len(plan["cases"]), len(plan["comparisons"])), (15, 12))

    def test_fifty_one_foot_sample_and_release_remain_unjudged(self):
        out = self.observe()
        self.assertAlmostEqual(out["samples"][1]["reference_to_nearest_side_distance_ft"], 51)
        self.assertEqual(out["first_zero_speed_frame"], 1)
        self.assertTrue(out["samples"][2]["human_go_signal"])
        self.assertEqual(out["proceed_after_release_judgment"], "unresolved")

    def test_no_zero_speed_sample(self):
        for row in self.rows:
            row["ego_speed_mps"] = 1
        self.refresh()
        self.assertIsNone(self.observe()["first_zero_speed_frame"])

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

    def test_missing_human_warning_source_rejected(self):
        del self.context_value["human_warning_source"]
        self.refresh()
        with self.assertRaisesRegex(ValueError, "human_warning_source"):
            self.observe()

    def test_missing_release_annotation_rejected(self):
        del self.rows[2]["human_go_signal"]
        self.refresh()
        with self.assertRaisesRegex(ValueError, "human/device annotation"):
            self.observe()


if __name__ == "__main__":
    unittest.main()
