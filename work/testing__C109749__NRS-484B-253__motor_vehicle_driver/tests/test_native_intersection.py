import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("native_intersection", ROOT / "native_intersection.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def waypoint(x, y, junction):
    return {"x_m": x, "y_m": y, "road_id": 1, "lane_id": 1,
            "junction_id": junction, "source_ref": "original-map-waypoint"}


def packet():
    return {"map_sha256": "a" * 64, "source_ref": "original-opendrive",
            "junction_id": 9,
            "intersection_polygon": [(-5, -5), (5, -5), (5, 5), (-5, 5)],
            "ego_route": [waypoint(0, -10, None), waypoint(0, 0, 9), waypoint(-10, 0, None)],
            "opposing_route": [waypoint(0, 10, None), waypoint(0, 0, 9), waypoint(0, -10, None)],
            "ego_blueprint_id": "vehicle.carla.ego", "opponent_blueprint_id": "vehicle.carla.other"}


class NativeIntersection(unittest.TestCase):
    def test_left_turn_opposite_route(self):
        self.assertTrue(MODULE.validate(packet())["connected_left_turn"])

    def test_right_turn_rejected(self):
        p = packet()
        p["ego_route"][-1] = waypoint(10, 0, None)
        with self.assertRaisesRegex(ValueError, "turn left"):
            MODULE.validate(p)

    def test_same_direction_rejected(self):
        p = packet()
        p["opposing_route"] = [waypoint(0, -10, None), waypoint(0, 0, 9), waypoint(0, 10, None)]
        with self.assertRaisesRegex(ValueError, "opposite-direction"):
            MODULE.validate(p)

    def test_wrong_junction_rejected(self):
        p = packet()
        p["ego_route"][1]["junction_id"] = 8
        with self.assertRaisesRegex(ValueError, "junction waypoint"):
            MODULE.validate(p)


if __name__ == "__main__":
    unittest.main()
