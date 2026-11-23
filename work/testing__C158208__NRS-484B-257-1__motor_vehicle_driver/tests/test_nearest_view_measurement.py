import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "nearest_view_measurement.py"
spec = importlib.util.spec_from_file_location("nearest_view_measurement", MODULE_PATH)
measurement = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measurement)


def packet():
    context = {name: True for name in (
        "yield_sign_governs_approach", "no_marked_stop_line", "no_near_side_crosswalk",
        "no_sidewalk_derived_crosswalk", "through_highway_confirmed", "no_officer_control",
        "no_signal_control", "viewpoint_reviewed")}
    samples = [
        dict(time_s=0, ego_speed_mps=3, ego_front_station_m=-12,
             through_center_station_m=20, through_traffic_visible=False,
             intersection_entry=False, through_vehicle_within_intersection=False),
        dict(time_s=1, ego_speed_mps=0.3, ego_front_station_m=-6,
             through_center_station_m=12, through_traffic_visible=True,
             intersection_entry=False, through_vehicle_within_intersection=False),
        dict(time_s=2, ego_speed_mps=0.2, ego_front_station_m=0,
             through_center_station_m=4, through_traffic_visible=True,
             intersection_entry=True, through_vehicle_within_intersection=True),
        dict(time_s=3, ego_speed_mps=2, ego_front_station_m=5,
             through_center_station_m=-2, through_traffic_visible=True,
             intersection_entry=False, through_vehicle_within_intersection=True),
    ]
    return {"reviewed_context": context, "samples": samples}


class NearestViewMeasurementTests(unittest.TestCase):
    def test_retains_view_entry_and_full_participant_history(self):
        result = measurement.measure(packet())
        self.assertEqual(result["first_view"]["ego_front_station_m"], -6)
        self.assertEqual(result["intersection_entry"]["time_s"], 2)
        self.assertEqual(result["minimum_approach_speed_mps"], 0.2)
        self.assertEqual(len(result["through_vehicle_history"]), 4)
        self.assertEqual(result["legal_status"], "unresolved")

    def test_rejects_missing_crosswalk_review(self):
        p = packet()
        del p["reviewed_context"]["no_sidewalk_derived_crosswalk"]
        with self.assertRaisesRegex(ValueError, "no_sidewalk_derived_crosswalk"):
            measurement.measure(p)

    def test_rejects_visibility_after_entry(self):
        p = packet()
        p["samples"][1]["through_traffic_visible"] = False
        with self.assertRaisesRegex(ValueError, "first view must precede"):
            measurement.measure(p)

    def test_rejects_missing_occupied_interval(self):
        p = packet()
        for sample in p["samples"]:
            sample["through_vehicle_within_intersection"] = False
        with self.assertRaisesRegex(ValueError, "occupied-through-highway"):
            measurement.measure(p)

    def test_rejects_unordered_time(self):
        p = packet()
        p["samples"][2]["time_s"] = 1
        with self.assertRaisesRegex(ValueError, "times must increase"):
            measurement.measure(p)

    def test_file_receipt_binds_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.json"
            output = Path(directory) / "measurement.json"
            source.write_text(json.dumps(packet()), encoding="utf-8")
            result = measurement.measure_file(source, output)
            self.assertEqual(json.loads(output.read_text())["source"], result["source"])
            self.assertEqual(len(result["source"]["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
