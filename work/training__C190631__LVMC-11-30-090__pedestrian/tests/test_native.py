import unittest
from geometry import check as geometry_check, open_drive
from runner import check as runner_check, survey


class FakeCarla:
    class LaneType:
        Driving = 'driving'
        Sidewalk = 'sidewalk'

    class Location:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z


class FakeWaypoint:
    def __init__(self, x, y, lane_id, road_id=1, z=8):
        self.lane_id = lane_id
        self.road_id = road_id
        self.lane_type = 'driving' if lane_id == -1 else 'sidewalk'
        self.transform = type('T', (), {'location': FakeCarla.Location(x, y, z)})()


class FakeMap:
    def __init__(self, wrong=False):
        self.wrong = wrong

    def get_waypoint(self, location, project_to_road, lane_type):
        lane_id = -1 if lane_type == FakeCarla.LaneType.Driving else -3
        lower = location.z < 2
        return FakeWaypoint(location.x, location.y, -2 if self.wrong else lane_id,
                            road_id=2 if lower else 1, z=0 if lower else 8)


class FakeWorld:
    def __init__(self, wrong=False):
        self.mapping = FakeMap(wrong)

    def get_map(self):
        return self.mapping


class NativeDraft(unittest.TestCase):
    def test_geometry(self):
        result = geometry_check()
        self.assertEqual(result['lane_types'], ['driving', 'shoulder', 'sidewalk'])
        self.assertIn('a="8"', open_drive())

    def test_plan(self):
        result = runner_check()
        self.assertEqual(result['frames'], 600)
        self.assertEqual(len(result['cameras']), 4)
        self.assertFalse(result['physical_acceptance_claimed'])

    def test_survey_gate(self):
        result = survey(FakeWorld(), FakeCarla)
        self.assertEqual(len(result['roadway']), 3)
        self.assertEqual(len(result['sidewalk']), 3)
        self.assertEqual(len(result['lower_road']), 3)
        with self.assertRaisesRegex(RuntimeError, 'readback failed'):
            survey(FakeWorld(wrong=True), FakeCarla)
