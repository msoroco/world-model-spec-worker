import importlib.util
import sys
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "native_controller.py"
spec = importlib.util.spec_from_file_location("c158196_native_controller", MODULE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class Actor:
    def __init__(self, x=-4, speed=2):
        self.x, self.speed = x, speed

    def get_transform(self):
        loc = type("Location", (), {"x": self.x, "y": 0})()
        rot = type("Rotation", (), {"yaw": 0})()
        return type("Transform", (), {"location": loc, "rotation": rot})()

    def get_velocity(self):
        return type("Velocity", (), {"x": self.speed, "y": 0})()


ROUTE = {"native_waypoints": [{"x": -20, "y": 0}, {"x": 20, "y": 0}]}
BOUNDS = [-2, -2, 2, 2]


def readers(context="stop_sign", other=(0, 0), **updates):
    authority = {"native_frame": 100, "control_context": context,
                 "ego_control_actor_id": 45, "signal_controlling": False,
                 "officer_controlling": False}
    authority.update(updates)
    counterpart = {"native_frame": 100, "x": other[0], "y": other[1],
                   "unobligated": True}
    return lambda: authority, lambda: counterpart


class ControllerTest(unittest.TestCase):
    def test_stop_sign_requires_observed_full_stop_before_entry(self):
        authority, other = readers(other=(20, 20))
        policy = mod.IntersectionController(other, authority)
        devices = {"control_context": "stop_sign", "ego_control_actor_id": 45}
        command = policy("ego", Actor(speed=2), 2.5, ROUTE, BOUNDS, devices)
        self.assertEqual(command["brake"], 0.75)
        self.assertFalse(policy.full_stop_observed)
        command = policy("ego", Actor(speed=0), 2.5, ROUTE, BOUNDS, devices)
        self.assertTrue(policy.full_stop_observed)
        self.assertGreater(command["throttle"], 0)

    def test_yield_holds_for_original_counterpart_occupancy(self):
        authority, other = readers(context="yield_sign", other=(0, 0))
        policy = mod.IntersectionController(other, authority)
        devices = {"control_context": "yield_sign", "ego_control_actor_id": 45}
        self.assertGreater(policy("ego", Actor(), 2.5, ROUTE, BOUNDS, devices)["brake"], 0)

    def test_fallback_throttle_changes_only_engineering_control(self):
        authority, other = readers(context="yield_sign", other=(20, 20))
        primary = mod.IntersectionController(other, authority, 1.0)
        fallback = mod.IntersectionController(other, authority, .75)
        devices = {"control_context": "yield_sign", "ego_control_actor_id": 45}
        first = primary("ego", Actor(speed=0), 2.5, ROUTE, BOUNDS, devices)
        second = fallback("ego", Actor(speed=0), 2.5, ROUTE, BOUNDS, devices)
        self.assertGreater(first["throttle"], second["throttle"])
        self.assertEqual(first["steer"], second["steer"])

    def test_exception_requires_live_authority_and_same_frame_priority(self):
        authority, other = readers(context="officer_exception", other=(20, 20))
        policy = mod.IntersectionController(other, authority)
        devices = {"control_context": "officer_exception", "ego_control_actor_id": 45}
        with self.assertRaisesRegex(ValueError, "officer control"):
            policy("ego", Actor(), 2.5, ROUTE, BOUNDS, devices)
        authority, other = readers(context="officer_exception", other=(20, 20),
                                   officer_actor_visible=True, officer_permission=True)
        policy = mod.IntersectionController(other, authority)
        self.assertGreater(policy("ego", Actor(), 2.5, ROUTE, BOUNDS, devices)["throttle"], 0)
        stale_other = lambda: {"native_frame": 99, "x": 20, "y": 20, "unobligated": True}
        with self.assertRaisesRegex(ValueError, "same-frame"):
            mod.IntersectionController(stale_other, authority)("ego", Actor(), 2.5, ROUTE, BOUNDS, devices)


if __name__ == "__main__":
    unittest.main()
