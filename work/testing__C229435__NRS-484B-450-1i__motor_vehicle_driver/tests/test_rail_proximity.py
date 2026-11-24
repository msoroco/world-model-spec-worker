import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rail_proximity import ASSIGNMENT, FIFTY_FEET_M, measure


class RailProximityTests(unittest.TestCase):
    def packet(self):
        return {"assignment_id": ASSIGNMENT, "original_trace_id": "synthetic-test-only",
                "vehicle_action": "park", "vehicle_actor_id": "car-a",
                "vehicle_footprint_m": [[0, 0], [2, 0], [2, 2], [0, 2]],
                "rail_polylines_m": [{"rail_id": "rail-a", "points_m": [[0, 10], [10, 10]]}],
                "exception_context": {k: "absent" for k in
                                      ("traffic_conflict_necessity", "law_compliance", "officer_direction", "official_device_direction")}}

    def run_measure(self, packet):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "original.json"
            p.write_text(json.dumps(packet), encoding="utf-8")
            return measure(p)

    def test_nearest_footprint_not_center(self):
        r = self.run_measure(self.packet())
        self.assertEqual(r["nearest_rail_distance_m"], 8)
        self.assertTrue(r["within_fifty_feet"])
        self.assertAlmostEqual(FIFTY_FEET_M, 15.24)

    def test_far_rail(self):
        p = self.packet()
        p["rail_polylines_m"][0]["points_m"] = [[0, 30], [10, 30]]
        self.assertFalse(self.run_measure(p)["within_fifty_feet"])

    def test_other_vehicle_does_not_prove_exception(self):
        p = self.packet()
        p["exception_context"]["traffic_conflict_necessity"] = "unresolved"
        self.assertEqual(self.run_measure(p)["exception_context"]["traffic_conflict_necessity"], "unresolved")

    def test_second_rail_can_be_nearest(self):
        p = self.packet()
        p["rail_polylines_m"].append({"rail_id": "rail-b", "points_m": [[0, 4], [10, 4]]})
        self.assertEqual(self.run_measure(p)["nearest_rail_id"], "rail-b")

    def test_missing_exception_context_rejected(self):
        p = self.packet()
        del p["exception_context"]["officer_direction"]
        with self.assertRaisesRegex(ValueError, "exception context"):
            self.run_measure(p)


if __name__ == "__main__":
    unittest.main()
