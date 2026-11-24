import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from yield_view_measurement import ASSIGNMENT, measure


class YieldViewTests(unittest.TestCase):
    def packet(self):
        return {"assignment_id": ASSIGNMENT, "original_trace_id": "synthetic-test-only",
                "site": {"control": "yield_sign", "stop_line_present": False,
                         "near_crosswalk_present": False, "police_control_active": False,
                         "traffic_signal_control_active": False,
                         "approach_view_stations": [
                             {"station_id": "far", "distance_to_intersection_m": 12.0, "view_of_through_traffic": True},
                             {"station_id": "near", "distance_to_intersection_m": 3.0, "view_of_through_traffic": True}]},
                "frames": [{"time_s": i * 0.05, "ego_speed_mps": 5.0 - i,
                            "distance_to_intersection_m": 8.0 - i,
                            "ego_within_intersection": i >= 3,
                            "through_vehicle_ids": ["through-a"]} for i in range(5)]}

    def run_measure(self, packet):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "original.json"
            p.write_text(json.dumps(packet), encoding="utf-8")
            return measure(p)

    def test_nearest_view_and_slowdown(self):
        r = self.run_measure(self.packet())
        self.assertEqual(r["nearest_visible_station_id"], "near")
        self.assertEqual(r["entry_bracket_indices"], [2, 3])
        self.assertEqual(r["speed_reduction_before_entry_mps"], 2)

    def test_no_near_view_uses_far_station(self):
        p = self.packet()
        p["site"]["approach_view_stations"][1]["view_of_through_traffic"] = False
        self.assertEqual(self.run_measure(p)["nearest_visible_station_id"], "far")

    def test_crosswalk_rejects_branch(self):
        p = self.packet()
        p["site"]["near_crosswalk_present"] = True
        with self.assertRaisesRegex(ValueError, "no stop line"):
            self.run_measure(p)

    def test_signal_control_rejects_exception(self):
        p = self.packet()
        p["site"]["traffic_signal_control_active"] = True
        with self.assertRaisesRegex(ValueError, "exception"):
            self.run_measure(p)

    def test_missing_view_rejected(self):
        p = self.packet()
        for station in p["site"]["approach_view_stations"]:
            station["view_of_through_traffic"] = False
        with self.assertRaisesRegex(ValueError, "no through-traffic view"):
            self.run_measure(p)


if __name__ == "__main__":
    unittest.main()
