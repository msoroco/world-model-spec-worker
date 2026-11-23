import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("turn_merge_controller", ROOT / "turn_merge_controller.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeVehicle:
    def __init__(self):
        self.controls = []

    def apply_control(self, value):
        self.controls.append(value)


class RouteTests(unittest.TestCase):
    def test_eastbound_left_turn_and_merge_progression(self):
        follower = MODULE.TurnMergeController([[0, -10], [0, 0], [10, 0], [15, -3], [30, -3]])
        self.assertEqual(follower.command(0, -10, 1.57, 0)["waypoint_index"], 1)
        self.assertEqual(follower.command(0, 0, 0, 3)["waypoint_index"], 2)
        self.assertEqual(follower.command(10, 0, 0, 3)["waypoint_index"], 3)
        self.assertEqual(follower.command(15, -3, 0, 3)["waypoint_index"], 4)
        self.assertTrue(follower.command(30, -3, 0, 3)["route_complete"])

    def test_westbound_left_turn_and_merge_progression(self):
        follower = MODULE.TurnMergeController([[0, 10], [0, 0], [-10, 0], [-15, 3], [-30, 3]])
        for x, y in [(0, 10), (0, 0), (-10, 0), (-15, 3)]:
            follower.command(x, y, 3.14, 3)
        self.assertEqual(follower.command(-20, 3, 3.14, 3)["waypoint_index"], 4)
        self.assertTrue(follower.command(-30, 3, 3.14, 3)["route_complete"])

    def test_steering_and_speed_control(self):
        follower = MODULE.TurnMergeController([[0, 0], [0, 10], [0, 20], [0, 30]])
        cmd = follower.command(0, 0, 0, 0)
        self.assertEqual(cmd["steer"], 1.0)
        self.assertGreater(cmd["throttle"], 0)
        self.assertEqual(cmd["brake"], 0)
        cmd = follower.command(0, 3, 1.57, 8)
        self.assertEqual(cmd["throttle"], 0)
        self.assertGreater(cmd["brake"], 0)

    def test_apply_uses_supplied_factory_without_carla_import(self):
        vehicle = FakeVehicle()
        follower = MODULE.TurnMergeController([[0, 0], [0, 10], [0, 20], [0, 30]])
        follower.apply(vehicle, 0, 0, 1.57, 2, control_factory=lambda **kwargs: kwargs)
        self.assertEqual(len(vehicle.controls), 1)
        self.assertIn("steer", vehicle.controls[0])

    def test_short_route_rejected(self):
        with self.assertRaisesRegex(ValueError, "route needs"):
            MODULE.TurnMergeController([[0, 0], [1, 0]])


if __name__ == "__main__":
    unittest.main()
