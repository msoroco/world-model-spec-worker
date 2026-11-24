import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as S

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_scene import DestinationController, validate_route
from test_native_acquisition import BOUNDARY, CASE


def route(case_id=CASE, x=5, y=5):
    return {"case_id": case_id, "map_id": "reviewed-map",
            "source_refs": [{"path": "reviewed-native-lane-packet", "sha256": "source-hash"}],
            "approach_lane": "native-lane-1", "lane_direction_reviewed": True,
            "vehicle_blueprint": "vehicle.test", "spawn": {"x": -10, "y": 5},
            "destination": {"x": x, "y": y, "yaw_deg": 0},
            "vehicle_extent": {"half_length_m": 1, "half_width_m": 0.5},
            "speed_limit_mps": 5}


class Actor:
    def __init__(self, x=0, speed=0):
        self.x = x
        self.speed = speed
        self.controls = []

    def get_transform(self):
        return S(location=S(x=self.x, y=5), rotation=S(yaw=0))

    def get_velocity(self):
        return S(x=self.speed, y=0, z=0)

    def apply_control(self, control):
        self.controls.append(control)


class SceneTests(unittest.TestCase):
    def test_inside_and_outside_footprints_use_reviewed_polygon(self):
        inside = validate_route(route(), BOUNDARY, CASE)
        self.assertTrue(inside["destination_contact_predicted"])
        self.assertFalse(inside["physical_contact_verified"])
        outside_case = CASE.replace("inside_stop", "outside_reference")
        outside = validate_route(route(outside_case, x=-4), BOUNDARY, outside_case)
        self.assertFalse(outside["destination_contact_predicted"])
        with self.assertRaisesRegex(ValueError, "inside destination misses"):
            validate_route(route(x=-4), BOUNDARY, CASE)
        with self.assertRaisesRegex(ValueError, "outside/through destination contacts"):
            validate_route(route(outside_case), BOUNDARY, outside_case)

    def test_controller_requests_approach_brake_and_cleanup(self):
        control = DestinationController(route(), BOUNDARY, CASE, lambda **kwargs: kwargs)
        actor = Actor()
        approach = control.step(0, actor)
        self.assertEqual(approach["phase"], "approach")
        self.assertGreater(approach["throttle"], 0)
        actor.x = 4.5
        braking = control.step(1, actor)
        self.assertEqual(braking["phase"], "destination_brake")
        self.assertEqual(actor.controls[-1]["brake"], 1)
        control.stop(actor)
        self.assertEqual(actor.controls[-1]["brake"], 1)
        with self.assertRaisesRegex(ValueError, "already stopped"):
            control.step(2, actor)

    def test_unreviewed_lane_or_map_rejected(self):
        bad = route()
        bad["lane_direction_reviewed"] = False
        with self.assertRaisesRegex(ValueError, "approach lane"):
            validate_route(bad, BOUNDARY, CASE)
        bad = route()
        bad["map_id"] = "another map"
        with self.assertRaisesRegex(ValueError, "case/map"):
            validate_route(bad, BOUNDARY, CASE)


if __name__ == "__main__":
    unittest.main()
