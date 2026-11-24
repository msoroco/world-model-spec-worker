import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from driveway_sidewalk import ASSIGNMENT, measure


class DrivewaySidewalkTests(unittest.TestCase):
    def packet(self):
        return {"assignment_id": ASSIGNMENT, "original_trace_id": "synthetic-test-only",
                "vehicle_type": "electric_scooter", "district_type": "residence",
                "district_source_id": "district-a", "access_type": "driveway",
                "sidewalk_area_id": "sidewalk-a",
                "frames": [{"time_s": i * 0.05, "speed_mps": 0.0 if i == 1 else 2.0,
                            "distance_before_sidewalk_edge_m": 2.0 - i,
                            "pedestrian_in_conflict_area": i >= 2,
                            "pedestrian_actor_ids": ["person-a"] if i >= 2 else [],
                            "operator_yield_observed": i == 2} for i in range(4)]}

    def run_measure(self, packet):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "original.json"
            p.write_text(json.dumps(packet), encoding="utf-8")
            return measure(p)

    def test_stop_before_entry_and_pedestrian(self):
        r = self.run_measure(self.packet())
        self.assertEqual(r["entry_bracket_indices"], [1, 2])
        self.assertEqual(r["last_pre_entry_stop_index"], 1)
        self.assertTrue(r["pedestrian_conflict_observed_at_entry"])

    def test_no_stop_kept_distinct(self):
        p = self.packet()
        p["frames"][1]["speed_mps"] = 2.0
        self.assertIsNone(self.run_measure(p)["last_pre_entry_stop_index"])

    def test_no_pedestrian_kept_distinct(self):
        p = self.packet()
        p["frames"][2]["pedestrian_in_conflict_area"] = False
        self.assertFalse(self.run_measure(p)["pedestrian_conflict_observed_at_entry"])

    def test_nonqualifying_vehicle_rejected(self):
        p = self.packet()
        p["vehicle_type"] = "car"
        with self.assertRaisesRegex(ValueError, "qualifying"):
            self.run_measure(p)

    def test_no_edge_crossing_rejected(self):
        p = self.packet()
        for f in p["frames"]:
            f["distance_before_sidewalk_edge_m"] += 5
        with self.assertRaisesRegex(ValueError, "entry bracket"):
            self.run_measure(p)


if __name__ == "__main__":
    unittest.main()
