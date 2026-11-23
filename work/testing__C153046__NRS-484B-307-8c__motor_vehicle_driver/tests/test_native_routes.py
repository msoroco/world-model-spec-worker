"""Check original participant route requests and source gates."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_routes import Routes
from tests.test_source_bound_scene import fixture


class Actor:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.controls = []
    def get_transform(self):
        return NS(location=NS(x=self.x, y=self.y, z=0), rotation=NS(yaw=0))
    def get_velocity(self):
        return NS(x=0, y=0, z=0)
    def apply_control(self, control):
        self.controls.append(control)


class NativeRouteTests(unittest.TestCase):
    def test_waypoint_requests_and_stop(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = fixture(root)
            citation = {"blueprint_id": "synthetic", "source_citation": "CPU source",
                        "reviewer": "CPU test", "route_source_citation": "CPU route",
                        "location_xyz_m": [0, 0, 0], "rotation_rpy_deg": [0, 0, 0],
                        "route_speed_mps": 2.0,
                        "route_points_xyz_m": [[2, 0, 0]]}
            packet["spawn_plan"] = {
                "ego": {**citation, "location_xyz_m": [-1.75, -10, 0],
                        "rotation_rpy_deg": [0, 0, 90], "approach_lane_id": "west"},
                "pedestrians": [dict(citation)], "other_traffic": [dict(citation)]}
            path = root / "site.json"
            path.write_text(json.dumps(packet))
            pedestrian, traffic = Actor(0, 0), Actor(0, 0)
            actors = NS(pedestrians=[pedestrian], traffic=[traffic])
            routes = Routes(path, "stopped_leftmost_clear", actors,
                            lambda **kw: kw, lambda **kw: kw,
                            lambda *xyz: xyz)
            routes.before_tick(0)
            self.assertEqual(pedestrian.controls[0]["direction"], (1.0, 0.0, 0.0))
            self.assertEqual(pedestrian.controls[0]["speed"], 2.0)
            self.assertEqual(traffic.controls[0]["throttle"], .35)
            self.assertEqual(traffic.controls[0]["steer"], 0.0)
            pedestrian.x = traffic.x = 2
            routes.before_tick(1)
            self.assertEqual(pedestrian.controls[1]["speed"], 0.0)
            self.assertEqual(traffic.controls[1]["brake"], 1.0)
            packet["spawn_plan"]["pedestrians"][0].pop("route_speed_mps")
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "route speed missing"):
                Routes(path, "stopped_leftmost_clear", actors,
                       lambda **kw: kw, lambda **kw: kw, lambda *xyz: xyz)


if __name__ == "__main__":
    unittest.main()
