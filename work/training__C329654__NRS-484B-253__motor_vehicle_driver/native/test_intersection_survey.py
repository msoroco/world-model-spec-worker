import unittest
from types import SimpleNamespace

from intersection_survey import survey


class Waypoint:
    def __init__(self, identity, x, y, yaw, road, lane, junction=None):
        self.id = identity
        self.road_id = road
        self.lane_id = lane
        self.lane_type = "driving"
        self.is_junction = False
        self.transform = SimpleNamespace(location=SimpleNamespace(x=x, y=y),
                                         rotation=SimpleNamespace(yaw=yaw))
        self.junction = junction
        self.upstream = {}
    def next(self, distance):
        return [SimpleNamespace(is_junction=True, get_junction=lambda: self.junction)] if self.junction else []
    def previous(self, distance):
        return [self.upstream[distance]] if distance in self.upstream else []


class FakeMap:
    def __init__(self, entries): self.entries = entries
    def to_opendrive(self): return "<OpenDRIVE><road/></OpenDRIVE>"
    def generate_waypoints(self, distance): return self.entries


class IntersectionSurveyTest(unittest.TestCase):
    def setUp(self):
        self.ego = Waypoint(1, -4, 0, 0, 1, -1)
        self.opposite = Waypoint(2, 4, 0, 180, 2, -1)
        self.exit = Waypoint(3, 0, 8, 90, 3, -1)
        self.junction = SimpleNamespace(id=5,
            bounding_box=SimpleNamespace(location=SimpleNamespace(x=0, y=0),
                                         extent=SimpleNamespace(x=5, y=5)),
            get_waypoints=lambda lane_type: [(self.ego, self.exit)])
        self.ego.junction = self.junction
        self.opposite.junction = self.junction
        self.ego.upstream[25.0] = Waypoint(4, -29, 0, 0, 1, -1)
        self.opposite.upstream[100.0] = Waypoint(5, 104, 0, 180, 2, -1)
        self.opposite.upstream[140.0] = Waypoint(6, 144, 0, 180, 2, -1)
        self.map = FakeMap([self.ego, self.opposite])

    def test_connected_opposing_left_turn(self):
        record, starts = survey(self.map, "driving")
        self.assertEqual(record["junction_id"], 5)
        self.assertEqual(record["opposing_approach_direction_xy"][0], -1)
        self.assertEqual(starts["subsequent_start"].id, 6)
        self.assertTrue(record["physical_geometry_review_required"])

    def test_missing_second_opponent_road_rejected(self):
        del self.opposite.upstream[140.0]
        with self.assertRaisesRegex(ValueError, "140 m inbound"):
            survey(self.map, "driving")

    def test_wrong_opposing_direction_rejected(self):
        self.opposite.transform.rotation.yaw = 0
        with self.assertRaisesRegex(ValueError, "opposing"):
            survey(self.map, "driving")

    def test_missing_left_exit_rejected(self):
        self.exit.transform.rotation.yaw = -90
        with self.assertRaisesRegex(ValueError, "left-turn"):
            survey(self.map, "driving")


if __name__ == "__main__":
    unittest.main()
