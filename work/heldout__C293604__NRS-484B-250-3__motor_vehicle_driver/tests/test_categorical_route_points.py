import sys
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from categorical_route_points import select_point


class Point:
    def __init__(self, x, y, dx, dy, road, junction=False):
        self.road_id, self.lane_id, self.is_junction = road, -1, junction
        self.transform = NS(location=NS(x=x, y=y),
                            get_forward_vector=lambda: NS(x=dx, y=dy))
        self.successors = []

    def next(self, distance):
        return self.successors

    def get_junction(self):
        return NS(id=42) if self.is_junction else None


def native_map(*, opposite, leftward):
    exit_direction = (0, 1) if leftward else (1, 0)
    a = [Point(-8, 0, 1, 0, 1), Point(0, 0, 1, 0, 2, True),
         Point(6 if not leftward else 0, 5 if leftward else 0,
               *exit_direction, 3)]
    other_direction = (-1, 0) if opposite else (1, 0)
    b = [Point(8 if opposite else -7, 1, *other_direction, 4),
         Point(0, 1, *other_direction, 5, True),
         Point(-6 if opposite else 6, 1, *other_direction, 6)]
    for path in (a, b):
        for first, second in zip(path, path[1:]):
            first.successors = [second]
    starts = {id(path[0].transform.location): path[0] for path in (a, b)}
    world = NS(name='SyntheticJunction',
               get_spawn_points=lambda: [NS(location=path[0].transform.location)
                                         for path in (a, b)],
               get_waypoint=lambda location: starts[id(location)])
    return world, a, b


class CategoricalRoutePointsTests(unittest.TestCase):
    def test_all_four_connected_geometry_categories(self):
        for opposite in (False, True):
            for leftward in (False, True):
                with self.subTest(opposite=opposite, leftward=leftward):
                    world, a, b = native_map(opposite=opposite, leftward=leftward)
                    point = select_point(world, opposite=opposite, leftward=leftward)
                    self.assertIs(point['turning'][0], a[0])
                    self.assertIs(point['other'][0], b[0])
                    self.assertEqual(point['junction_id'], '42')
                    self.assertFalse(point['legal_exception_claimed'])

    def test_rejects_unavailable_category_and_nonboolean_choice(self):
        world, _, _ = native_map(opposite=True, leftward=True)
        with self.assertRaisesRegex(ValueError, 'No connected Native categorical'):
            select_point(world, opposite=False, leftward=False)
        with self.assertRaisesRegex(ValueError, 'booleans'):
            select_point(world, opposite=1, leftward=True)


if __name__ == '__main__':
    unittest.main()
