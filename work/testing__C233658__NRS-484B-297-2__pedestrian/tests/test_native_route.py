import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_entry import camera_poses, reviewed_route
from road_geometry import construction_routes


class NativeRouteTests(unittest.TestCase):
    def test_six_exact_route_requests(self):
        for direction in ("east", "west"):
            for side, heading in (("left", "facing"), ("right", "facing"), ("left", "with_traffic")):
                with self.subTest(direction=direction, side=side, heading=heading):
                    vehicle, pedestrian = construction_routes(direction, side, heading)
                    case_id = "example__" + direction + "_" + side + "_" + heading
                    route = {"vehicle_start_xyz_m": [*vehicle.start, 0.2],
                             "vehicle_end_xyz_m": [*vehicle.end, 0.2],
                             "pedestrian_start_xyz_m": [*pedestrian.start, 0.2],
                             "pedestrian_end_xyz_m": [*pedestrian.end, 0.2],
                             "walker_speed_mps": 1.0, "vehicle_speed_mps": 5.0}
                    selected = reviewed_route({"routes": {case_id: route}}, case_id,
                        {"approach_direction": direction, "pedestrian_highway_side": side,
                         "pedestrian_heading": heading})
                    self.assertEqual(selected, route)
                    with self.assertRaisesRegex(ValueError, "route missing"):
                        reviewed_route({"routes": {}}, case_id,
                            {"approach_direction": direction, "pedestrian_highway_side": side,
                             "pedestrian_heading": heading})

    def test_camera_source_must_cover_all_four_views(self):
        with self.assertRaisesRegex(ValueError, "four-camera poses missing"):
            camera_poses({"cameras": {"example": {"overview": {}}}}, "example")


if __name__ == "__main__":
    unittest.main()
