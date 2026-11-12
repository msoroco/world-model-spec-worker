import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from three_lane_route import ordered_lanes, section_readback, select_route


class Lane:
    def __init__(self, lane_id, x, y, direction, marked=True):
        self.road_id = 17
        self.lane_id = lane_id
        self.lane_type = 'Driving'
        self.lane_width = 3.5
        self.is_junction = False
        self.transform = NS(location=NS(x=x, y=y),
                            get_forward_vector=lambda: NS(x=direction, y=0))
        marking = NS(type='Solid' if marked else 'None')
        self.left_lane_marking = marking
        self.right_lane_marking = marking
        self.left = self.right = None
        self.successor = None

    def get_left_lane(self):
        return self.left

    def get_right_lane(self):
        return self.right

    def next(self, spacing):
        return [self.successor] if self.successor else []


def corridor(direction=1, marked=True):
    route = []
    for step in range(5):
        x = direction * step * 2.5
        right = Lane(1 * direction, x, 0, direction, marked)
        center = Lane(2 * direction, x, direction * 3.5, direction, marked)
        left = Lane(3 * direction, x, direction * 7, -direction, marked)
        right.left, center.right, center.left, left.right = center, right, left, center
        if route:
            route[-1].successor = right
        route.append(right)
    world_map = NS(get_spawn_points=lambda: [NS(location=route[0])],
                   get_waypoint=lambda location: location)
    return world_map, route


class ThreeLaneRouteTests(unittest.TestCase):
    def test_selects_connected_marked_three_lane_corridor_in_both_directions(self):
        for direction, name in ((1, 'east'), (-1, 'west')):
            world_map, route = corridor(direction)
            self.assertEqual(select_route(world_map, direction=name, steps=4), route)
            readback = section_readback(route[0])
            self.assertEqual(set(readback['lane_ids']), {'right', 'center', 'extreme_left'})
            self.assertIsNone(readback['physical_paint_visible'])
            self.assertIsNone(readback['legal_lane_status'])

    def test_rejects_missing_marking_and_disconnected_route(self):
        world_map, route = corridor(marked=False)
        with self.assertRaisesRegex(ValueError, 'marked'):
            ordered_lanes(route[0])
        with self.assertRaisesRegex(ValueError, 'No connected'):
            select_route(world_map, steps=4)
        world_map, route = corridor()
        route[1].successor = None
        with self.assertRaisesRegex(ValueError, 'No connected'):
            select_route(world_map, steps=4)

    def test_rejects_wrong_lane_order_or_center_direction(self):
        _, route = corridor()
        lane = route[0]
        lane.left.transform.location.y = -3.5
        with self.assertRaisesRegex(ValueError, 'adjacency'):
            ordered_lanes(lane)
        _, route = corridor()
        lane = route[0]
        lane.left.transform.get_forward_vector = lambda: NS(x=-1, y=0)
        with self.assertRaisesRegex(ValueError, 'travel direction'):
            ordered_lanes(lane)

    def test_non_driving_outer_shoulder_does_not_add_a_fourth_lane(self):
        _, route = corridor()
        right = route[0]
        shoulder = Lane(99, 0, -3.5, 1)
        shoulder.lane_type = 'Shoulder'
        right.right = shoulder
        self.assertEqual(ordered_lanes(right)['right'], right)


if __name__ == '__main__':
    unittest.main()
