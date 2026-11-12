import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from three_lane_passing import passing_target, center_clearance
from test_three_lane_route import corridor


class PassingGeometryTests(unittest.TestCase):
    def test_target_and_gap_in_both_travel_directions(self):
        for direction in (1, -1):
            _, route = corridor(direction)
            # Extend the unit route while retaining its original lane geometry.
            point = route[-1]
            for step in range(5, 29):
                from test_three_lane_route import Lane
                next_point = Lane(direction, direction * step * 2.5, 0, direction)
                point.successor = next_point
                route.append(next_point)
                point = next_point
            target = passing_target(route, target_ahead_m=17.5, route_clear_m=65)
            self.assertAlmostEqual(target.transform.location.x, direction * 17.5)
            result = center_clearance((0, 0), (direction, 0), (0, direction * 3.5),
                                      [{'actor_id': 8, 'center_xy': (direction * 17.5, 0),
                                        'half_length_m': 2.2, 'half_width_m': 1}], clear_m=60)
            self.assertTrue(result['engineering_interval_clear'])
            self.assertIsNone(result['legal_safe_distance'])
            self.assertIsNone(result['highway_clearly_visible'])

    def test_near_center_traffic_and_short_route_rejected(self):
        _, route = corridor()
        with self.assertRaisesRegex(ValueError, 'route length'):
            passing_target(route)
        result = center_clearance((0, 0), (1, 0), (0, 3.5),
                                  [{'actor_id': 9, 'center_xy': (14, 3.5),
                                    'half_length_m': 2.2, 'half_width_m': 1}], clear_m=60)
        self.assertEqual(result['blocked_actors'][0]['actor_id'], 9)
        self.assertFalse(result['engineering_interval_clear'])


if __name__ == '__main__':
    unittest.main()
