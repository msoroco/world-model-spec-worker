import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from opposing_left_route import select_opposing_left_routes


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


class OpposingTests(unittest.TestCase):
    def map(self, second_heading=-1):
        a = [Point(-8, 0, 1, 0, 1), Point(0, 0, 1, 0, 2, True),
             Point(0, 5, 0, 1, 3)]
        b = [Point(8, 0, second_heading, 0, 4),
             Point(0, 1, second_heading, 0, 5, True),
             Point(-6, 1, -1, 0, 6)]
        for path in (a, b):
            for first, second in zip(path, path[1:]):
                first.successors = [second]
        starts = {id(path[0].transform.location): path[0] for path in (a, b)}
        return NS(name='SyntheticJunction',
                  get_spawn_points=lambda: [NS(location=path[0].transform.location)
                                            for path in (a, b)],
                  get_waypoint=lambda location: starts[id(location)]), a, b

    def test_selects_connected_opposing_left(self):
        world, a, b = self.map()
        selected = select_opposing_left_routes(world)
        self.assertIs(selected['turning'][0], a[0])
        self.assertIs(selected['opposite'][0], b[0])
        self.assertFalse(selected['legal_exception_claimed'])

    def test_rejects_same_direction_and_right_turn(self):
        world, _, _ = self.map(second_heading=1)
        with self.assertRaisesRegex(ValueError, 'No connected'):
            select_opposing_left_routes(world)
        world, a, _ = self.map()
        a[-1].transform.get_forward_vector = lambda: NS(x=0, y=-1)
        with self.assertRaisesRegex(ValueError, 'No connected'):
            select_opposing_left_routes(world)
