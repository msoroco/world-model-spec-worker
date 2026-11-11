import sys
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from categorical_highway_points import select_point


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


def native_map(*, subject_continues):
    subject_exit_road = 1 if subject_continues else 3
    a = [Point(-8, 0, 1, 0, 1), Point(0, 0, 1, 0, 5, True),
         Point(6, 0, 1, 0, subject_exit_road)]
    b = [Point(0, -8, 0, 1, 2), Point(0, 1, 0, 1, 6, True),
         Point(0, 8, 0, 1, 2)]
    for path in (a, b):
        for first, second in zip(path, path[1:]):
            first.successors = [second]
    starts = {id(path[0].transform.location): path[0] for path in (a, b)}
    world = NS(name='SyntheticJunction',
               get_spawn_points=lambda: [NS(location=path[0].transform.location)
                                         for path in (a, b)],
               get_waypoint=lambda location: starts[id(location)])
    return world, a, b


class CategoricalHighwayPointsTests(unittest.TestCase):
    def test_ending_and_continuing_native_successor_categories(self):
        for continuing in (False, True):
            with self.subTest(continuing=continuing):
                world, a, b = native_map(subject_continues=continuing)
                point = select_point(world, subject_continues=continuing)
                self.assertIs(point['subject'][0], a[0])
                self.assertIs(point['other'][0], b[0])
                self.assertEqual(point['subject_highway_continues'], continuing)
                self.assertFalse(point['legal_highway_status_claimed'])

    def test_missing_category_and_nonboolean_rejected(self):
        world, _, _ = native_map(subject_continues=False)
        with self.assertRaisesRegex(ValueError, 'No connected Native'):
            select_point(world, subject_continues=True)
        with self.assertRaisesRegex(ValueError, 'boolean'):
            select_point(world, subject_continues=1)


if __name__ == '__main__':
    unittest.main()
