import unittest

from controller import TARGET_X_M, check as controller_check, command
from geometry import check as geometry_check, elevation, open_drive
from runner import survey


class FakeCarla:
    class LaneType:
        Driving = 'driving'

    class Location:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z


class Waypoint:
    def __init__(self, x, y, z):
        self.road_id, self.lane_id = 1, -1
        self.transform = type('T', (), {'location': FakeCarla.Location(x, y, z)})()


class Map:
    def __init__(self, wrong_height=False):
        self.wrong_height = wrong_height

    def get_waypoint(self, location, project_to_road, lane_type):
        z = elevation(location.x) + (4 if self.wrong_height else 0)
        return Waypoint(location.x, location.y, z)


class NativeGeometry(unittest.TestCase):
    def test_bridge_and_common_controller(self):
        self.assertEqual(geometry_check()['elevation_m'], 8)
        self.assertIn('elevationProfile', open_drive())
        self.assertEqual(set(controller_check()['targets_x_m']), {'false', 'true'})
        self.assertEqual(command('true', 0, -75, 0)['phase'], 'approach')
        self.assertEqual(command('true', 200, 50, 0)['phase'], 'hold')
        self.assertEqual(command('false', 200, -25, 0)['phase'], 'hold')
        self.assertLess(TARGET_X_M['false'], 0)
        self.assertGreater(TARGET_X_M['true'], 0)

    def test_native_elevation_readback_and_rejection(self):
        self.assertEqual(len(survey(FakeCarla, Map())), 6)
        with self.assertRaisesRegex(RuntimeError, 'elevation readback differs'):
            survey(FakeCarla, Map(wrong_height=True))

    def test_invalid_control_inputs(self):
        for suffix, frame, x, speed in [('other', 0, 0, 0),
                                         ('true', -1, 0, 0),
                                         ('true', 0, 0, -1)]:
            with self.assertRaises(ValueError):
                command(suffix, frame, x, speed)
