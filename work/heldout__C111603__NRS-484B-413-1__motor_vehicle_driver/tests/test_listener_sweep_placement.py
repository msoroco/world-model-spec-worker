import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from listener_sweep_placement import listener_points, spawnable_listener_points


class FakeCarla:
    class LaneType:
        Sidewalk = 'sidewalk'

    class Location:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z


class FakeMap:
    def __init__(self, shift=0, missing=False):
        self.shift, self.missing = shift, missing
        self.calls = []

    def get_waypoint(self, location, project_to_road, lane_type):
        self.calls.append((location.x, location.y, project_to_road, lane_type))
        if self.missing:
            return None
        waypoint = type('Waypoint', (), {})()
        transform = type('Transform', (), {})()
        transform.location = FakeCarla.Location(location.x + self.shift,
                                                location.y, location.z)
        waypoint.transform = transform
        waypoint.lane_id, waypoint.road_id = 2, 17
        return waypoint


class ListenerSweepPlacementTests(unittest.TestCase):
    def test_three_route_relative_positions_in_both_directions(self):
        east = listener_points([(-2, 0), (0, 0), (2, 0)])
        west = listener_points([(2, 0), (0, 0), (-2, 0)])
        self.assertEqual([row['point_y_m'] for row in east], [2, 4, 6])
        self.assertEqual([row['point_y_m'] for row in west], [-2, -4, -6])
        self.assertEqual([row['nearest_sampled_route_m'] for row in east], [2, 4, 6])

    def test_rejects_degenerate_route_and_invalid_offsets(self):
        with self.assertRaisesRegex(ValueError, 'tangent is degenerate'):
            listener_points([(0, 0), (0, 0), (0, 0)])
        with self.assertRaisesRegex(ValueError, 'increasing positive offsets'):
            listener_points([(-2, 0), (0, 0), (2, 0)], (2, 2, 6))
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            listener_points([(-2, 0), (0, float('nan')), (2, 0)])

    def test_resolves_three_sidewalk_spawns_in_both_approach_directions(self):
        for route, expected_y in [([(-2, 0), (0, 0), (2, 0)], [2, 4, 6]),
                                  ([(2, 0), (0, 0), (-2, 0)], [-2, -4, -6])]:
            native_map = FakeMap(shift=.25)
            points = spawnable_listener_points(native_map, FakeCarla, route)
            self.assertEqual([point['spawn_y_m'] for point in points], expected_y)
            self.assertEqual([point['sidewalk_projection_m'] for point in points], [.25] * 3)
            self.assertEqual([call[2:] for call in native_map.calls], [(False, 'sidewalk')] * 3)

    def test_rejects_absent_or_distant_sidewalk_spawns(self):
        route = [(-2, 0), (0, 0), (2, 0)]
        with self.assertRaisesRegex(ValueError, 'no Native sidewalk'):
            spawnable_listener_points(FakeMap(missing=True), FakeCarla, route)
        with self.assertRaisesRegex(ValueError, 'exceeds tolerance'):
            spawnable_listener_points(FakeMap(shift=1), FakeCarla, route)


if __name__ == '__main__':
    unittest.main()
