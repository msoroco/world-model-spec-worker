import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sidewalk_footprint import ASSIGNMENT, measure


class SidewalkFootprintTests(unittest.TestCase):
    def packet(self):
        return {"assignment_id": ASSIGNMENT, "original_trace_id": "synthetic-test-only",
                "vehicle_type": "motor_vehicle", "vehicle_actor_id": "car-a",
                "vehicle_action": "park", "sidewalk_area_id": "sidewalk-a",
                "vehicle_footprint_m": [[0, 0], [2, 0], [2, 2], [0, 2]],
                "sidewalk_patch_m": [[1, 1], [4, 1], [4, 3], [1, 3]],
                "exception_context": {k: "absent" for k in
                                      ("traffic_conflict_necessity", "law_compliance", "officer_direction", "official_device_direction", "subsection_3")}}

    def run_measure(self, packet):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "original.json"
            p.write_text(json.dumps(packet), encoding="utf-8")
            return measure(p)

    def test_partial_overlap(self):
        r = self.run_measure(self.packet())
        self.assertTrue(r["vehicle_footprint_on_sidewalk"])
        self.assertAlmostEqual(r["physical_overlap_area_m2"], 1)

    def test_no_overlap(self):
        p = self.packet()
        p["sidewalk_patch_m"] = [[3, 3], [4, 3], [4, 4], [3, 4]]
        self.assertFalse(self.run_measure(p)["vehicle_footprint_on_sidewalk"])

    def test_boundary_touch_has_zero_area(self):
        p = self.packet()
        p["sidewalk_patch_m"] = [[2, 0], [4, 0], [4, 2], [2, 2]]
        self.assertFalse(self.run_measure(p)["vehicle_footprint_on_sidewalk"])

    def test_bicycle_not_assigned_motor_vehicle_branch(self):
        p = self.packet()
        p["vehicle_type"] = "bicycle"
        with self.assertRaisesRegex(ValueError, "motor vehicle"):
            self.run_measure(p)

    def test_exception_unresolved_retained(self):
        p = self.packet()
        p["exception_context"]["traffic_conflict_necessity"] = "unresolved"
        self.assertEqual(self.run_measure(p)["exception_context"]["traffic_conflict_necessity"], "unresolved")


if __name__ == "__main__":
    unittest.main()
