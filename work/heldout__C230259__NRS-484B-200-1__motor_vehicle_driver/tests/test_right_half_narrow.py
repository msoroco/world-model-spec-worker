"""Measured narrow-road selector and original body-width controls."""
import sys
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from right_half_narrow import body_width_m, narrow_targets, select_narrow_route


class Point:
    def __init__(self, x, y, z=0):
        self.x, self.y, self.z = x, y, z


class Transform:
    def __init__(self, x, y, direction):
        self.location = Point(x, y)
        self.direction = direction

    def get_forward_vector(self):
        return Point(*self.direction)


class Lane:
    lane_type = 'Driving'
    road_id = 8
    is_junction = False

    def __init__(self, x, y, direction, lane_id, width):
        self.transform = Transform(x, y, direction)
        self.lane_id = lane_id
        self.lane_width = width
        self.other = self.following = None

    def get_left_lane(self):
        return self.other

    def get_right_lane(self):
        return None

    def next(self, spacing):
        return [self.following] if self.following else []


def pair(x, width=3):
    right = Lane(x, -width / 2, (1, 0), -1, width)
    left = Lane(x, width / 2, (-1, 0), 1, width)
    right.other, left.other = left, right
    return right


class Map:
    def __init__(self, width):
        self.route = [pair(i * 2.5, width) for i in range(17)]
        for before, after in zip(self.route, self.route[1:]):
            before.following = after

    def get_spawn_points(self):
        return [self.route[0].transform]

    def get_waypoint(self, location):
        return self.route[0]


class Body:
    def __init__(self):
        self.bounding_box = self

    def get_transform(self):
        return object()

    def get_world_vertices(self, transform):
        return [Point(x, y, z) for z in (0, 1.5)
                for x in (-2.4, 2.4) for y in (-.9, .9)]


class NarrowTest(unittest.TestCase):
    def test_measured_route_and_left_targets(self):
        route = select_narrow_route(Map(3))
        target = narrow_targets(route)
        self.assertEqual(len(target['targets_xy_m']), 17)
        self.assertEqual(target['measured_road_width_m'], [6.] * 17)
        self.assertTrue(all(y == 1.5 for _, y in target['targets_xy_m']))
        self.assertFalse(target['legal_sufficiency_decided'])
        self.assertAlmostEqual(body_width_m(Body()), 1.8)

    def test_wider_road_and_missing_opposite_rejected(self):
        with self.assertRaisesRegex(ValueError, 'No connected measured narrow'):
            select_narrow_route(Map(3.5))
        network = Map(3)
        network.route[5].other = None
        with self.assertRaisesRegex(ValueError, 'No connected measured narrow'):
            select_narrow_route(network)
