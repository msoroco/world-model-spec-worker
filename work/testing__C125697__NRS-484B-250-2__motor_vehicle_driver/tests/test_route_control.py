import importlib.util
import unittest
from pathlib import Path


root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('route_control', root / 'route_control.py')
route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route)


POLYGON = [[10, -5], [20, -5], [20, 5], [10, 5]]


class RouteTests(unittest.TestCase):
    def test_orthogonal_approaches_traverse_one_crossing(self):
        east = [[0, 0], [12, 0], [15, 0], [24, 0]]
        north = [[15, -12], [15, -3], [15, 0], [15, 8]]
        self.assertEqual(route.validate_route(east, [0, 0], [12, 0], POLYGON, 'ego'), east)
        self.assertEqual(route.validate_route(north, [15, -12], [15, -3], POLYGON, 'other'), north)
        steer, progress = route.steering_command(0, 0, 0, east)
        self.assertAlmostEqual(steer, 0)
        self.assertEqual(progress, 1)
        plan = {'approaches': {'ego': {'start_xy_m': [0, 0], 'entry_xy_m': [12, 0]},
                               'other': {'start_xy_m': [15, -12], 'entry_xy_m': [15, -3]}},
                'crossing_polygon_xy_m': POLYGON}
        self.assertEqual(route.validate_pair_routes(plan, {'ego': east, 'other': north}),
                         {'ego': east, 'other': north})

    def test_turn_directions_and_progress_are_monotone(self):
        right, _ = route.steering_command(0, 0, 0, [[0, 0], [10, -3], [20, -3]])
        left, _ = route.steering_command(0, 0, 0, [[0, 0], [10, 3], [20, 3]])
        self.assertGreater(right, 0)
        self.assertLess(left, 0)
        _, progress = route.steering_command(9, 0, 0, [[0, 0], [10, 0], [20, 0]], 1)
        self.assertEqual(progress, 2)

    def test_route_that_misses_crossing_or_has_invalid_pose_rejected(self):
        with self.assertRaisesRegex(ValueError, 'crossing interior'):
            route.validate_route([[0, 0], [12, 8], [24, 8]], [0, 0], [12, 8], POLYGON, 'ego')
        with self.assertRaisesRegex(ValueError, 'Finite Native'):
            route.steering_command(float('nan'), 0, 0, [[0, 0], [10, 0]])


if __name__ == '__main__':
    unittest.main()
