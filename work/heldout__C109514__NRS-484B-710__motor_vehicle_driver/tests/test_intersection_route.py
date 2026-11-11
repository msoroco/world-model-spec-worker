import importlib.util
from pathlib import Path
import unittest

folder = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('intersection_route', folder / 'intersection_route.py')
route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route)

class Location:
    def __init__(self, x, y=0): self.x, self.y = x, y

class Transform:
    def __init__(self, x, y=0): self.location = Location(x, y)

class Waypoint:
    def __init__(self, x, *, junction=False, road=1, y=0):
        self.transform = Transform(x, y)
        self.is_junction = junction
        self.road_id = road
        self.lane_id = -1
        self.followers = []
    def next(self, _distance): return self.followers

class RouteTests(unittest.TestCase):
    def make_chain(self, junction=True):
        points = [Waypoint(i*5, junction=junction and 12 <= i <= 15,
                           road=1 if i < 12 else 2 if i <= 15 else 3)
                  for i in range(50)]
        for a, b in zip(points, points[1:]): a.followers = [b]
        return points

    def test_constructs_intersection_between_both_actors(self):
        points = self.make_chain()
        selected = route.route_from(points[0])
        self.assertIs(selected['ego'], points[0])
        self.assertIs(selected['junction_entry'], points[12])
        self.assertIs(selected['junction_exit'], points[15])
        self.assertGreater(selected['apparatus'].transform.location.x, points[15].transform.location.x)
        self.assertGreaterEqual(selected['centre_separation_m'], 500/route.FEET_PER_METRE)

    def test_rejects_missing_junction_and_short_runout(self):
        with self.assertRaisesRegex(ValueError, 'lacks a junction'):
            route.route_from(self.make_chain(junction=False)[0])
        points = self.make_chain()
        points[35].followers = []
        with self.assertRaisesRegex(ValueError, 'continuation'):
            route.route_from(points[0])

    def test_rejects_ambiguous_diverging_approach(self):
        points = self.make_chain()
        points[3].followers = [points[4], Waypoint(20, y=0.1)]
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            route.route_from(points[0])

if __name__ == '__main__': unittest.main()
