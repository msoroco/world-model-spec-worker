import copy
import importlib.util
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("median_route_control", root / "median_route_control.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def scene():
    return {
        "same_statutory_crossing": True,
        "crossing_polygon_xy_m": [[10,-3],[20,-3],[20,3],[10,3]],
        "approach_relation": "different_highways",
        "stop_sign": {"native_id": 17, "governed_lane_id": "eastbound"},
        "ego_stop_line_xy_m": [8,0],
        "approaches": {
            "ego": {"highway_id": "EW", "lane_id": "eastbound", "forward_xy": [1,0],
                    "route_xy_m": [[0,0],[15,0],[30,0]]},
            "other": {"highway_id": "NS", "lane_id": "northbound", "forward_xy": [0,1],
                      "route_xy_m": [[15,-15],[15,0],[15,15]]}
        }
    }


class MedianRouteTests(unittest.TestCase):
    def test_different_highway_routes_cross_same_polygon(self):
        self.assertEqual(mod.validate_scene(scene())["approaches"]["ego"]["lane_id"], "eastbound")
        bad = scene(); bad["approaches"]["other"]["highway_id"] = "EW"
        with self.assertRaisesRegex(ValueError, "one highway"):
            mod.validate_scene(bad)
        bad = scene(); bad["approaches"]["other"]["route_xy_m"] = [[30,12],[20,12],[0,12]]
        with self.assertRaisesRegex(ValueError, "misses crossing"):
            mod.validate_scene(bad)

    def test_sign_and_stop_line_must_govern_ego_entrance(self):
        bad = scene(); bad["stop_sign"]["governed_lane_id"] = "northbound"
        with self.assertRaisesRegex(ValueError, "govern"):
            mod.validate_scene(bad)
        bad = scene(); bad["ego_stop_line_xy_m"] = [15,0]
        with self.assertRaisesRegex(ValueError, "Stop line"):
            mod.validate_scene(bad)

    def test_opposite_left_turn_requires_opposite_heading_and_intention(self):
        opposite = scene()
        opposite["approach_relation"] = "opposite_directions"
        opposite["other_left_turn_intended"] = True
        opposite["approaches"]["other"].update({"highway_id":"EW", "forward_xy":[-1,0],
            "route_xy_m":[[30,0],[15,0],[15,-15]]})
        mod.validate_scene(opposite)
        bad = copy.deepcopy(opposite); bad["approaches"]["other"]["forward_xy"] = [1,0]
        with self.assertRaisesRegex(ValueError, "Opposite headings"):
            mod.validate_scene(bad)
        bad = copy.deepcopy(opposite); bad["other_left_turn_intended"] = False
        with self.assertRaisesRegex(ValueError, "left-turn intention"):
            mod.validate_scene(bad)

    def test_stop_then_wait_for_clear_conflict(self):
        throttle, brake, stopped = mod.stop_yield_control(5, 5, False, True)
        self.assertEqual((throttle,brake,stopped), (0,1,False))
        self.assertEqual(mod.stop_yield_control(.5, .05, False, True), (0,1,True))
        self.assertEqual(mod.stop_yield_control(.5,0,True,False), (0,1,True))
        throttle,brake,stopped = mod.stop_yield_control(.5,0,True,True)
        self.assertGreater(throttle,0)
        self.assertEqual((brake,stopped),(0,True))
        with self.assertRaisesRegex(ValueError,"passed stop line"):
            mod.stop_yield_control(-1,2,False,True)

if __name__ == "__main__":
    unittest.main()
