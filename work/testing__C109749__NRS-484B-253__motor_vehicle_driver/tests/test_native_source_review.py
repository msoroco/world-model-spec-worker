import hashlib
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from native_source_review import review
from test_native_acquisition import waypoint


class WP:
    def __init__(self, x, y):
        self.road_id = 1
        self.lane_id = 1
        self.is_junction = (x, y) == (0.0, 0.0)

    def get_junction(self):
        return type("Junction", (), {"id": 9})()


class Map:
    def __init__(self):
        self.road = "<OpenDRIVE><road id='1'/></OpenDRIVE>"
        self.missing = False

    def to_opendrive(self):
        return self.road

    def get_waypoint(self, location, project_to_road=False):
        if project_to_road:
            raise AssertionError("Projection would hide a mismatched survey")
        return None if self.missing else WP(*location)


class NativeSourceReview(unittest.TestCase):
    def setUp(self):
        self.map = Map()
        self.packet = {"map_sha256": hashlib.sha256(self.map.road.encode()).hexdigest(),
                       "source_ref": "live-map-survey", "junction_id": 9,
                       "intersection_polygon": [[-5, -5], [5, -5], [5, 5], [-5, 5]],
                       "ego_route": [waypoint(0, -10, None), waypoint(0, 0, 9), waypoint(-10, 0, None)],
                       "opposing_route": [waypoint(0, 10, None), waypoint(0, 0, 9), waypoint(0, -10, None)],
                       "ego_blueprint_id": "vehicle.ego", "opponent_blueprint_id": "vehicle.other",
                       "reviewed_original_map": True}

    def run_review(self):
        return review(self.packet, carla_map=self.map, location_factory=lambda x, y: (x, y))

    def test_live_map_waypoints_and_hash_join(self):
        result = self.run_review()
        self.assertEqual(result["checked_waypoints"], 6)
        self.assertEqual(result["physical_motion"], "unverified")

    def test_rejects_flag_only_diagnostic(self):
        self.packet["diagnostic_fixture"] = True
        with self.assertRaisesRegex(ValueError, "reviewed original"):
            self.run_review()

    def test_rejects_map_changed_after_survey(self):
        self.map.road += "<!-- changed -->"
        with self.assertRaisesRegex(ValueError, "OpenDRIVE bytes differ"):
            self.run_review()

    def test_rejects_missing_or_wrong_waypoint(self):
        self.map.missing = True
        with self.assertRaisesRegex(ValueError, "waypoint absent"):
            self.run_review()
        self.map.missing = False
        self.packet["ego_route"][1]["lane_id"] = 2
        with self.assertRaisesRegex(ValueError, "road/lane/junction mismatch"):
            self.run_review()


if __name__ == "__main__":
    unittest.main()
