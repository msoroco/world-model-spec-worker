import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lane_signal_measurement import measure
from bus_route import route


def sample(frame, lateral, longitudinal, symbol="red_x"):
    t = frame / 20
    common = {"frame": frame, "elapsed_seconds": t, "source_sha256": "a" * 64}
    body = {**common, "bus_footprint": [[longitudinal - 5, lateral - 1],
                                          [longitudinal + 5, lateral - 1],
                                          [longitudinal + 5, lateral + 1],
                                          [longitudinal - 5, lateral + 1]]}
    signal = {**common, "governed_lane_id": "red_lane", "lane_lateral_bounds_m": [0, 3.6],
              "symbol": symbol, "faces_bus": True, "official_device_source_sha256": "b" * 64}
    return {"frame": frame, "elapsed_seconds": t, "body": body,
            "lane_signal": signal, "camera_frame": dict(common)}


class RedXLaneMeasurement(unittest.TestCase):
    def test_all_four_routes_construct_distinct_targets(self):
        routes = {kind: route(kind) for kind in
                  ("adjacent_travel", "lateral_entry", "red_lane_stand", "red_lane_drive")}
        self.assertEqual(routes["adjacent_travel"]["waypoint_centers_m"][-1][1], -1.8)
        self.assertEqual(routes["lateral_entry"]["waypoint_centers_m"][-1][1], 1.8)
        self.assertEqual(len(set(map(tuple, routes["red_lane_stand"]["waypoint_centers_m"]))), 1)
        self.assertGreater(len(set(map(tuple, routes["red_lane_drive"]["waypoint_centers_m"]))), 1)

    def test_adjacent_lane_has_no_entry_or_driving(self):
        result = measure([sample(1, -2, 0), sample(2, -2, 3)])
        self.assertEqual(result["red_x_entry_frames"], [])
        self.assertEqual(result["red_x_driving_frames"], [])

    def test_lateral_entry_detected_with_bus_footprint(self):
        result = measure([sample(1, -2, 0), sample(2, -0.8, 0)])
        self.assertEqual(result["red_x_entry_frames"], [2])
        self.assertEqual(result["red_x_driving_frames"], [])

    def test_in_lane_driving_distinct_from_stationary(self):
        result = measure([sample(1, 1.8, 0), sample(2, 1.8, 0), sample(3, 1.8, 3)])
        self.assertEqual(result["red_x_entry_frames"], [])
        self.assertEqual(result["red_x_driving_frames"], [3])

    def test_changed_signal_time_rejected(self):
        frames = [sample(1, -2, 0), sample(2, -0.8, 0)]
        frames[1]["lane_signal"]["elapsed_seconds"] = 9
        with self.assertRaisesRegex(ValueError, "join"):
            measure(frames)

    def test_missing_original_source_rejected(self):
        frames = [sample(1, -2, 0), sample(2, -0.8, 0)]
        frames[1]["camera_frame"]["source_sha256"] = ""
        with self.assertRaisesRegex(ValueError, "source hash"):
            measure(frames)

    def test_unreviewed_facing_rejected(self):
        frames = [sample(1, -2, 0), sample(2, -0.8, 0)]
        frames[1]["lane_signal"]["faces_bus"] = False
        with self.assertRaisesRegex(ValueError, "facing official"):
            measure(frames)

    def test_changed_lane_bounds_rejected(self):
        frames = [sample(1, -2, 0), sample(2, -0.8, 0)]
        frames[1]["lane_signal"]["lane_lateral_bounds_m"] = [0, 4]
        with self.assertRaisesRegex(ValueError, "lane bounds changed"):
            measure(frames)


if __name__ == "__main__":
    unittest.main()
