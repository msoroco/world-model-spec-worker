import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

source = Path(__file__).resolve().parents[1] / "fire_route.py"
spec = importlib.util.spec_from_file_location("fire_route", source)
route = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = route
spec.loader.exec_module(route)


class Waypoint:
    def __init__(self, points, index, sign):
        self.points, self.index, self.sign = points, index, sign
        x, z = points[index]
        self.transform = SimpleNamespace(location=SimpleNamespace(x=sign*x, y=0., z=z))
        self.road_id, self.section_id, self.lane_id = 7, 0, sign
        self.is_junction = False

    def next(self, step):
        if self.index + 1 == len(self.points):
            return []
        return [Waypoint(self.points, self.index + 1, self.sign)]


def crest_points():
    return [(i*5., min(i, 16)*.2 - max(i-16, 0)*.2) for i in range(50)]


class FireRouteTests(unittest.TestCase):
    def test_both_approach_directions_have_crest_between_actors(self):
        for sign in (1, -1):
            with self.subTest(sign=sign):
                selected = route.route_from(Waypoint(crest_points(), 0, sign))
                self.assertEqual(selected["road_id"], 7)
                self.assertEqual(selected["lane_id"], sign)
                self.assertGreater(selected["centre_separation_m"], 150)
                self.assertLess(selected["chain"].index(selected["crest"]),
                                selected["chain"].index(selected["apparatus"]))

    def test_flat_road_is_rejected(self):
        points = [(i*5., 0.) for i in range(50)]
        with self.assertRaisesRegex(ValueError, "no measured hill crest"):
            route.route_from(Waypoint(points, 0, 1))

    def test_early_end_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "continuous nonjunction lane"):
            route.route_from(Waypoint(crest_points()[:10], 0, 1))


if __name__ == "__main__":
    unittest.main()
