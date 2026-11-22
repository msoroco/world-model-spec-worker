import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_route import discover_hill_route


class Transform:
    def __init__(self, x, z, direction=1):
        self.location = SimpleNamespace(x=x, y=0, z=z)
        self.direction = direction

    def get_forward_vector(self):
        return SimpleNamespace(x=self.direction, y=0)


class Waypoint:
    def __init__(self, x, z, lane=-1, direction=1):
        self.road_id = 12
        self.lane_id = lane
        self.lane_type = 'Driving'
        self.transform = Transform(x, z, direction)
        self.successor = None
        self.left = None

    def next(self, distance):
        return [self.successor] if self.successor else []

    def get_left_lane(self):
        return self.left

    def get_right_lane(self):
        return None


class Map:
    name = 'fake original Native map'

    def __init__(self, heights, adjacent_direction=1):
        self.points = [Waypoint(i*4, z) for i, z in enumerate(heights)]
        for a, b in zip(self.points, self.points[1:]):
            a.successor = b
        self.points[-2].left = Waypoint(40, heights[-2], -2, adjacent_direction)

    def get_spawn_points(self):
        return [SimpleNamespace(location=self.points[0].transform.location)]

    def get_waypoint(self, location):
        return self.points[0]


class NativeRouteTest(unittest.TestCase):
    def test_map_discovery_uses_actual_elevation_and_forward_lane(self):
        route = discover_hill_route(Map([0,.1,.3,.7,1.1,1.7,2,1.8,1.4,1,.6,.2]), points=12)
        self.assertEqual(route['geometry']['target_lane_id'], -2)
        self.assertEqual(route['map_source'], 'fake original Native map')
        self.assertEqual(len(route['waypoints']), 12)

    def test_flat_and_opposing_adjacent_lane_rejected(self):
        for native_map in (Map([0]*12),
                           Map([0,.1,.3,.7,1.1,1.7,2,1.8,1.4,1,.6,.2], -1)):
            with self.subTest(native_map=native_map), self.assertRaisesRegex(ValueError, 'lacks connected hill crest'):
                discover_hill_route(native_map, points=12)


if __name__ == '__main__':
    unittest.main()
