"""CPU checks for the selected two-lane geometry and scripted lane contrast."""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capture import _survey, check, planned_y
from geometry import open_drive


class ConstructionTest(unittest.TestCase):
    def test_two_marked_lanes_and_capture(self):
        receipt = check()
        self.assertEqual(receipt['geometry']['same_direction_marked_lane_count'], 2)
        self.assertEqual(receipt['frames'], 600)
        self.assertEqual(len(receipt['views']), 4)

    def test_only_contrast_exits_left_before_rear_crossing(self):
        self.assertEqual(planned_y('reference', 200), -1.75)
        self.assertEqual(planned_y('contrast', 0), -1.75)
        self.assertEqual(planned_y('contrast', 140), -5.25)
        self.assertEqual(planned_y('contrast', 200), -5.25)
        self.assertEqual((-50 + 1.35 * 200) - (20 + 200), 0)

    def test_native_map_readback_rejects_wrong_width(self):
        class Location:
            def __init__(self, x, y, z):
                self.x, self.y, self.z = x, y, z

        class Carla:
            class LaneType:
                Driving = 'driving'
        Carla.Location = Location

        class Map:
            def to_opendrive(self):
                return open_drive()

            def get_waypoint(self, location, project_to_road, lane_type):
                lane_id = -1 if location.y > -3.5 else -2
                return type('Waypoint', (), {'road_id': 1, 'lane_id': lane_id,
                    'transform': type('T', (), {'location': location})()})()

        self.assertEqual(len(_survey(Map(), Carla)['waypoints']), 2)

        class WrongMap(Map):
            def to_opendrive(self):
                return open_drive().replace('a="3.5"', 'a="4.0"', 1)

        with self.assertRaisesRegex(RuntimeError, 'marked lane readback'):
            _survey(WrongMap(), Carla)


if __name__ == '__main__':
    unittest.main()
