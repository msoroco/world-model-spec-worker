import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outside_crosswalk_entry import ASSIGNMENT, measure


class OutsideCrosswalkTests(unittest.TestCase):
    def packet(self):
        return {"assignment_id": ASSIGNMENT, "original_trace_id": "synthetic-test-only",
                "site": {"roadway_id": "road-a", "crossing_point_id": "point-a",
                         "within_marked_crosswalk": False,
                         "within_unmarked_intersection_crosswalk": False,
                         "prohibited_place_under_11_30_070": False},
                "frames": [{"time_s": i * 0.05, "pedestrian_on_roadway": i >= 2,
                            "pedestrian_yield_observed": i == 2,
                            "vehicles_on_roadway": ["car-a"]} for i in range(4)]}

    def run_measure(self, packet):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "original.json"
            p.write_text(json.dumps(packet), encoding="utf-8")
            return measure(p)

    def test_entry_with_vehicle_and_yield(self):
        r = self.run_measure(self.packet())
        self.assertEqual(r["road_entry_bracket_indices"], [1, 2])
        self.assertEqual(r["vehicles_on_roadway_at_entry"], ["car-a"])
        self.assertTrue(r["pedestrian_yield_observed_at_entry"])

    def test_no_yield_kept_distinct(self):
        p = self.packet()
        p["frames"][2]["pedestrian_yield_observed"] = False
        self.assertFalse(self.run_measure(p)["pedestrian_yield_observed_at_entry"])

    def test_unmarked_crosswalk_rejected(self):
        p = self.packet()
        p["site"]["within_unmarked_intersection_crosswalk"] = True
        with self.assertRaisesRegex(ValueError, "outside this branch"):
            self.run_measure(p)

    def test_prohibited_place_retained(self):
        p = self.packet()
        p["site"]["prohibited_place_under_11_30_070"] = True
        self.assertTrue(self.run_measure(p)["prohibited_place_under_11_30_070"])

    def test_no_entry_rejected(self):
        p = self.packet()
        for f in p["frames"]:
            f["pedestrian_on_roadway"] = False
        with self.assertRaisesRegex(ValueError, "road-entry"):
            self.run_measure(p)


if __name__ == "__main__":
    unittest.main()
