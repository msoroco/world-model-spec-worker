import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "pass_measure.py"
spec = importlib.util.spec_from_file_location("pass_measure", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def packet():
    def frame(i, lateral, ego_station, oncoming_station):
        return {"original_frame": i, "ray_source_sha256": "ray-hash", "left_side_rays": [
            {"clear_distance_m": 80.0 - i, "censored": i != 1,
             "hit_kind": "opaque_obstacle" if i == 1 else "range_limit"}],
            "actors": {"ego": {"vehicle": True, "direction": 1, "station_m": ego_station,
                               "centerline_signed_body_edge_m": lateral,
                               "rear_station_m": ego_station-2, "speed_mps": 12},
                       "overtaken": {"vehicle": True, "direction": 1, "station_m": 20,
                                     "front_station_m": 22, "speed_mps": 8},
                       "oncoming": {"vehicle": True, "direction": -1,
                                    "station_m": oncoming_station, "speed_mps": 10,
                                    "lateral_m": 0}}}
    return {"format": "nrs-484b-213-1-native-projection",
            "source": {"native_result_sha256": "native", "map_sha256": "map",
                       "frame_map_sha256": "frame-map"},
            "road": {"public_highway": True, "lane_count": 2,
                     "opposite_permitted_directions": True, "undivided": True,
                     "centerline_source": "native-map"},
            "frames": [frame(0, -1, 0, 100), frame(1, 1, 12, 95),
                       frame(2, 1, 23, 90), frame(3, -1, 30, 85)]}


class PassMeasurementTest(unittest.TestCase):
    def test_full_pass_observations_are_descriptive(self):
        result = module.measure(packet())
        self.assertEqual(result["measured_pass_and_return_frame"], 3)
        self.assertEqual(result["left_of_center_frames"], [1, 2])
        self.assertTrue(result["per_frame"][1]["left_ray_any_occluded"])
        self.assertEqual(result["judgments"]["sufficient_distance"], "unresolved")

    def test_missing_source_rejected(self):
        data = packet()
        del data["frames"][1]["ray_source_sha256"]
        with self.assertRaisesRegex(ValueError, "visibility rays"):
            module.measure(data)

    def test_missing_original_frame_rejected(self):
        data = packet()
        data["frames"][2]["original_frame"] = 4
        with self.assertRaisesRegex(ValueError, "frame sequence"):
            module.measure(data)

    def test_wrong_direction_rejected(self):
        data = packet()
        data["frames"][2]["actors"]["overtaken"]["direction"] = -1
        with self.assertRaisesRegex(ValueError, "same-direction"):
            module.measure(data)

    def test_incomplete_pass_stays_unconfirmed(self):
        data = packet()
        data["frames"][-1]["actors"]["ego"]["centerline_signed_body_edge_m"] = 1
        self.assertIsNone(module.measure(data)["measured_pass_and_return_frame"])


if __name__ == "__main__":
    unittest.main()
