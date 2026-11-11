from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from right_half_route import control_step, select_two_way_route
from test_directed_geometry import lane


def mapped_route(opposite_gap=False, direction=1):
    points = [lane(-1, i * 2.5 * direction, -1.5 * direction, direction) for i in range(14)]
    for i, point in enumerate(points):
        point.is_junction = False
        point.get_left_lane = lambda i=i: lane(1, i * 2.5 * direction,
                                               (3 if opposite_gap else 1.5) * direction,
                                               -direction)
        point.next = lambda step, i=i: [points[i + 1]] if i + 1 < len(points) else []
    world_map = NS(get_spawn_points=lambda: [NS(location=NS(x=0, y=-1.5 * direction))],
                   get_waypoint=lambda _: points[0])
    return world_map, points


class RouteTests(unittest.TestCase):
    def test_connected_route_and_gap_rejection(self):
        world_map, points = mapped_route()
        self.assertEqual(select_two_way_route(world_map), points[:13])
        world_map, _ = mapped_route(opposite_gap=True)
        with self.assertRaisesRegex(ValueError, 'No connected two-way'):
            select_two_way_route(world_map)

    def test_direction_is_bound_to_exact_case(self):
        world_map, points = mapped_route(direction=-1)
        self.assertEqual(select_two_way_route(world_map, desired_direction='west'), points[:13])
        with self.assertRaisesRegex(ValueError, 'No connected'):
            select_two_way_route(world_map, desired_direction='east')
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            select_two_way_route(world_map, desired_direction='north')

    def test_feedback_in_both_travel_directions(self):
        east = control_step([0, 0], [1, 0], [1, 0], [5, 1])
        west = control_step([0, 0], [-1, 0], [-1, 0], [-5, -1])
        self.assertGreater(east['steer'], 0)
        self.assertGreater(west['steer'], 0)
        self.assertGreater(east['throttle'], 0)
        fast = control_step([0, 0], [1, 0], [8, 0], [5, 0])
        self.assertEqual(fast['throttle'], 0)
        self.assertGreater(fast['brake'], 0)
        with self.assertRaisesRegex(ValueError, 'too close'):
            control_step([0, 0], [1, 0], [1, 0], [0, 0])


if __name__ == '__main__':
    unittest.main()
