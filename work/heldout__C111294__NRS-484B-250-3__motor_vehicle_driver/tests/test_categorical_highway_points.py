import sys
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from categorical_highway_points import select_point, select_controlled_pair
from ending_road_control_inventory import ungoverned_route_pair


class Point:
    def __init__(self, x, y, dx, dy, road, junction=False):
        self.road_id, self.lane_id, self.is_junction = road, -1, junction
        self.transform = NS(location=NS(x=x, y=y),
                            get_forward_vector=lambda: NS(x=dx, y=dy))
        self.successors = []
        self.landmarks = []

    def next(self, distance):
        return self.successors

    def get_junction(self):
        return NS(id=42) if self.is_junction else None

    def get_landmarks(self, distance, stop_at_junction=True):
        return self.landmarks


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
    def test_controlled_pair_fixes_through_route_and_rejects_changed_control(self):
        world, ending, through = native_map(subject_continues=False)
        continuing = [Point(-8, 4, 1, 0, 7),
                      Point(0, 4, 1, 0, 8, True),
                      Point(6, 4, 1, 0, 7)]
        for first, second in zip(continuing, continuing[1:]):
            first.successors = [second]
        starts = {id(path[0].transform.location): path[0]
                  for path in (ending, through, continuing)}
        world.get_spawn_points = lambda: [NS(location=path[0].transform.location)
                                          for path in (ending, through, continuing)]
        world.get_waypoint = lambda location: starts[id(location)]
        selected = select_controlled_pair(world)
        self.assertIs(selected['ending'][0], ending[0])
        self.assertIs(selected['continuing'][0], continuing[0])
        self.assertIs(selected['other'][0], through[0])
        self.assertFalse(selected['legal_highway_status_claimed'])
        with self.assertRaisesRegex(ValueError, 'No controlled'):
            select_controlled_pair(world, route_accept=lambda subject, other:
                                   subject['road_id'] != 7)
        selected = select_controlled_pair(
            world, route_accept=lambda subject, other:
            ungoverned_route_pair(subject, other, []))
        self.assertIs(selected['other'][0], through[0])
        continuing[0].landmarks = [NS(id='control-1', type='206')]
        with self.assertRaisesRegex(ValueError, 'No controlled'):
            select_controlled_pair(
                world, route_accept=lambda subject, other:
                ungoverned_route_pair(subject, other, []))

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

    def test_continuing_point_selects_its_continuing_exit_not_turn_branch(self):
        world, _, through = native_map(subject_continues=False)
        start = Point(-8, 4, 1, 0, 7)
        junction = Point(0, 4, 1, 0, 8, True)
        turn_exit = Point(0, 10, 0, 1, 9)
        straight_exit = Point(8, 4, 1, 0, 7)
        start.successors = [junction]
        junction.successors = [turn_exit, straight_exit]
        starts = {id(path.transform.location): path for path in (start, through[0])}
        world.get_spawn_points = lambda: [NS(location=path.transform.location)
                                          for path in (start, through[0])]
        world.get_waypoint = lambda location: starts[id(location)]
        point = select_point(world, subject_continues=True)
        self.assertIs(point['subject'][-1], straight_exit)

        # The controlled pair must make the same choice even if the turning
        # branch is enumerated first by the Native waypoint API.
        ending = [Point(-8, 0, 1, 0, 1), Point(0, 0, 1, 0, 5, True),
                  Point(6, 0, 1, 0, 3)]
        for first, second in zip(ending, ending[1:]):
            first.successors = [second]
        starts[id(ending[0].transform.location)] = ending[0]
        world.get_spawn_points = lambda: [NS(location=path.transform.location)
                                          for path in (ending[0], start, through[0])]
        pair = select_controlled_pair(world)
        self.assertIs(pair['continuing'][-1], straight_exit)
        self.assertIs(pair['other'][0], through[0])


if __name__ == '__main__':
    unittest.main()
