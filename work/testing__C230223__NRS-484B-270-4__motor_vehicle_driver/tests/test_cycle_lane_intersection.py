import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cycle_lane_intersection import ASSIGNMENT, measure


class CycleLaneIntersectionTests(unittest.TestCase):
    def packet(self):
        return {"assignment_id": ASSIGNMENT, "original_trace_id": "synthetic-test-only",
                "ego_vehicle_type": "motor_vehicle", "ego_actor_id": "car-a",
                "intersection_id": "junction-a", "cycle_lane_id": "cycle-lane-a",
                "cycle_lane_designated_for": "mixed_cycle", "subsection_3_exception_status": "unresolved",
                "frames": [{"time_s": i * 0.05, "ego_body_in_intersection": i >= 1,
                            "ego_body_in_designated_cycle_lane": i <= 1} for i in range(3)]}

    def run_measure(self, packet):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "original.json"
            p.write_text(json.dumps(packet), encoding="utf-8")
            return measure(p)

    def test_overlap_at_intersection(self):
        r = self.run_measure(self.packet())
        self.assertTrue(r["vehicle_in_cycle_lane_within_intersection_observed"])
        self.assertTrue(r["observations"][1]["intersection_and_cycle_lane_overlap"])

    def test_cycle_lane_before_intersection_only(self):
        p = self.packet()
        p["frames"][1]["ego_body_in_designated_cycle_lane"] = False
        self.assertFalse(self.run_measure(p)["vehicle_in_cycle_lane_within_intersection_observed"])

    def test_ordinary_lane_through_intersection(self):
        p = self.packet()
        for f in p["frames"]:
            f["ego_body_in_designated_cycle_lane"] = False
        self.assertFalse(self.run_measure(p)["vehicle_in_cycle_lane_within_intersection_observed"])

    def test_missing_designation_rejected(self):
        p = self.packet()
        p["cycle_lane_designated_for"] = "unknown"
        with self.assertRaisesRegex(ValueError, "designation"):
            self.run_measure(p)

    def test_exception_not_inferred(self):
        r = self.run_measure(self.packet())
        self.assertEqual(r["subsection_3_exception_status"], "unresolved")


if __name__ == "__main__":
    unittest.main()
