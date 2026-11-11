from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from narrow_exposure_route import select_route, exposed_position, speed_control


def route_map(width=3.0, direction=1):
    points = []
    for index in range(17):
        loc = NS(x=index * 2.5 * direction, y=0, z=0)
        points.append(NS(road_id=8, lane_id=-1, lane_width=width,
                         is_junction=False,
                         transform=NS(location=loc,
                                      get_forward_vector=lambda: NS(x=direction, y=0))))
    for index, point in enumerate(points):
        point.next = lambda step, index=index: [points[index + 1]] if index < 16 else []
    world_map = NS(get_spawn_points=lambda: [NS(location=points[0].transform.location)],
                   get_waypoint=lambda _: points[0])
    return world_map, points


class NarrowRouteTests(unittest.TestCase):
    def test_selects_connected_narrow_route_and_rejects_wide(self):
        world_map, route = route_map()
        self.assertEqual(select_route(world_map), route)
        world_map, _ = route_map(width=4)
        with self.assertRaisesRegex(ValueError, 'No connected'):
            select_route(world_map)

    def test_participant_placement_follows_travel_direction(self):
        _, east = route_map(direction=1)
        _, west = route_map(direction=-1)
        self.assertGreater(exposed_position(east)[1], 0)
        self.assertLess(exposed_position(west)[1], 0)

    def test_controller_uses_measured_velocity(self):
        slow = speed_control([0, 0], [1, 0], [0, 0], [5, 1], 2)
        fast = speed_control([0, 0], [1, 0], [5, 0], [5, 1], 2)
        self.assertGreater(slow['throttle'], 0)
        self.assertGreater(slow['steer'], 0)
        self.assertEqual(fast['throttle'], 0)
        self.assertGreater(fast['brake'], 0)
        with self.assertRaisesRegex(ValueError, 'collapsed'):
            speed_control([0, 0], [1, 0], [0, 0], [0, 0], 2)


if __name__ == '__main__':
    unittest.main()
