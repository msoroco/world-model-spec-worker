"""CPU checks for exact source identity and distinct motion requests."""

import unittest

from native_capture import apply_requested_control, case_id, check
from stop_yield_scene import request


class Vector:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z


class Box:
    def get_world_vertices(self, transform):
        x = transform.location.x
        return [Vector(x + sign * 2.25, 0, 0) for sign in (-1, 1)]


class Actor:
    def __init__(self, x, speed):
        self.location = Vector(x, 0, 0)
        self.velocity = Vector(speed, 0, 0)
        self.bounding_box = Box()
        self.last_control = None

    def get_transform(self):
        return type("Transform", (), {"location": self.location})()

    def get_velocity(self):
        return self.velocity

    def apply_control(self, control):
        self.last_control = control


class Carla:
    @staticmethod
    def VehicleControl(**values):
        return values


class NativeCaptureTest(unittest.TestCase):
    def test_exact_case_config_and_camera_plan(self):
        result = check()
        self.assertEqual(result["case_count"], 12)
        self.assertEqual(result["selected_case_id"], case_id("complete_stop_then_yield"))
        self.assertFalse(result["carla_imported"])
        self.assertFalse(result["physical_acceptance_claimed"])
        self.assertIsNone(result["legal_verdict"])

    def test_stop_and_roll_issue_distinct_controls(self):
        stop = request("complete_stop_then_yield")
        roll = request("roll_through_conflict")
        stop_actors = {"ego": Actor(-9.25, 2), "through": Actor(1, 1)}
        roll_actors = {"ego": Actor(-9.25, 2), "through": Actor(1, 1)}
        apply_requested_control(Carla, stop_actors, stop, 100)
        apply_requested_control(Carla, roll_actors, roll, 100)
        self.assertGreater(stop_actors["ego"].last_control["brake"], 0)
        self.assertGreater(roll_actors["ego"].last_control["throttle"], 0)
        self.assertEqual(stop_actors["through"].last_control,
                         roll_actors["through"].last_control)
        apply_requested_control(Carla, stop_actors, stop, 251)
        self.assertGreater(stop_actors["ego"].last_control["throttle"], 0)

    def test_unknown_case_rejected(self):
        with self.assertRaises(ValueError):
            case_id("different_law")


if __name__ == "__main__":
    unittest.main()
