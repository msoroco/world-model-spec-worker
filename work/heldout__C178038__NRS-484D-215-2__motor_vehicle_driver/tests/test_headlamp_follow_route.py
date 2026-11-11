from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from headlamp_follow_route import cruise_control, select_follow_route


def road(steps=55, direction=1):
    points = []
    for i in range(steps):
        point = NS(road_id=4, lane_id=1, is_junction=False,
                   transform=NS(location=NS(x=i * 2.5 * direction, y=0)))
        points.append(point)
    for i, point in enumerate(points):
        point.next = lambda step, i=i: [points[i + 1]] if i + 1 < len(points) else []
    world_map = NS(get_spawn_points=lambda: [NS(location=points[0].transform.location)],
                   get_waypoint=lambda _: points[0])
    return world_map, points


class FollowRouteTests(unittest.TestCase):
    def test_selects_long_connected_lane(self):
        world_map, points = road()
        chosen = select_follow_route(world_map)
        self.assertIs(chosen['ego'], points[0])
        self.assertIs(chosen['lead'], points[chosen['lead_index']])
        self.assertEqual(chosen['requested_gap_ft'], 299)
        world_map, _ = road(steps=10)
        with self.assertRaisesRegex(ValueError, 'No connected'):
            select_follow_route(world_map)

    def test_feedback_controls_both_directions(self):
        east = cruise_control([0, 0], [1, 0], [2, 0], [5, 1])
        west = cruise_control([0, 0], [-1, 0], [-2, 0], [-5, -1])
        self.assertGreater(east['steer'], 0)
        self.assertGreater(west['steer'], 0)
        self.assertGreater(east['throttle'], 0)
        fast = cruise_control([0, 0], [1, 0], [9, 0], [5, 0])
        self.assertEqual(fast['throttle'], 0)
        self.assertGreater(fast['brake'], 0)

    def test_adjacent_connected_shoulder_only(self):
        world_map, driving = road()
        shoulder = []
        for i, point in enumerate(driving):
            neighbour = NS(road_id=point.road_id, lane_id=2, is_junction=False,
                           lane_type='Shoulder',
                           transform=NS(location=NS(x=point.transform.location.x, y=4)))
            shoulder.append(neighbour)
        for i, point in enumerate(shoulder):
            point.next = lambda step, i=i: [shoulder[i + 1]] if i + 1 < len(shoulder) else []
        for i, point in enumerate(driving):
            point.get_right_lane = lambda i=i: shoulder[i]
        chosen = select_follow_route(world_map, surface='shoulder')
        self.assertIs(chosen['ego'], shoulder[0])
        self.assertIs(chosen['lead'], shoulder[chosen['lead_index']])
        for point in driving:
            point.get_right_lane = lambda: None
        with self.assertRaisesRegex(ValueError, 'shoulder'):
            select_follow_route(world_map, surface='shoulder')


if __name__ == '__main__':
    unittest.main()
