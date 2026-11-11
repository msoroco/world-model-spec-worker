import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


spec = importlib.util.spec_from_file_location("route_construction", Path(__file__).resolve().parents[1] / "route_construction.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Waypoint:
    def __init__(self, x, road=4, lane=-1, junction=False):
        self.road_id, self.lane_id, self.is_junction = road, lane, junction
        self.transform = NS(location=NS(x=x, y=0))
        self.following = []

    def next(self, step):
        return self.following


class Map:
    def __init__(self, waypoint):
        self.waypoint = waypoint

    def get_waypoint(self, location, project_to_road=False):
        assert project_to_road is False
        return self.waypoint


class RouteTests(unittest.TestCase):
    def test_selects_real_unbranched_native_waypoints(self):
        nodes = [Waypoint(x) for x in (0, 5, 10, 15, 20)]
        for left, right in zip(nodes, nodes[1:]):
            left.following = [right]
        result = module.select_corridor(Map(nodes[0]), [NS(location=NS(x=0, y=0))],
                                        reviewed_road_id=4, reviewed_lane_id=-1,
                                        minimum_length_m=15)
        self.assertEqual(result["measured_length_m"], 15)
        self.assertEqual(len(result["waypoints"]), 4)

    def test_rejects_junction_wrong_road_and_short_corridor(self):
        start = Waypoint(0)
        start.following = [Waypoint(5, junction=True)]
        args = (Map(start), [NS(location=NS(x=0, y=0))])
        with self.assertRaisesRegex(ValueError, "No source-reviewed"):
            module.select_corridor(*args, reviewed_road_id=4, reviewed_lane_id=-1, minimum_length_m=10)
        with self.assertRaisesRegex(ValueError, "No source-reviewed"):
            module.select_corridor(*args, reviewed_road_id=9, reviewed_lane_id=-1, minimum_length_m=10)


if __name__ == "__main__":
    unittest.main()
