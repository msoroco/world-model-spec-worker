import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from candidate_opendrive import build
from stand_route import make
from taxi_native_motion import RouteController, apply_step, route_points, spawn_taxi, validate_native_map


class FakeBlueprint:
    def __init__(self):
        self.attributes = {}

    def has_attribute(self, key):
        return key == "role_name"

    def set_attribute(self, key, value):
        self.attributes[key] = value


class FakeActor:
    def __init__(self, transform):
        self.transform = transform
        self.command = None

    def get_transform(self):
        return self.transform

    def get_velocity(self):
        return SimpleNamespace(x=0, y=0, z=0)

    def apply_control(self, command):
        self.command = command


class FakeCarla:
    @staticmethod
    def Location(**values):
        return SimpleNamespace(**values)

    @staticmethod
    def Rotation(**values):
        return SimpleNamespace(**values)

    @staticmethod
    def Transform(location, rotation):
        return SimpleNamespace(location=location, rotation=rotation)

    @staticmethod
    def VehicleControl(**values):
        return SimpleNamespace(**values)


class FakeWorld:
    def __init__(self, map_bytes):
        self.map_bytes = map_bytes
        self.blueprint = FakeBlueprint()
        self.actor = None

    def get_map(self):
        return SimpleNamespace(to_opendrive=lambda: self.map_bytes.decode())

    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda ident: self.blueprint if ident == "vehicle.test.taxi" else None)

    def spawn_actor(self, blueprint, transform):
        self.actor = FakeActor(transform)
        return self.actor


class NativeMotionTest(unittest.TestCase):
    def test_both_routes_have_right_turn_and_downstream_exit(self):
        for case in ("near_stand", "far_stand"):
            with self.subTest(case=case):
                points = route_points(make(case))
                self.assertEqual(points[-1], (-1.75, -35))
                self.assertEqual(points[-4], (-1.75, -4))
                self.assertLess(points[0][1], points[1][1])

    def test_straight_attempt_reuses_near_stand_and_commands_east_exit(self):
        near = make("near_stand")
        straight = make("near_stand_straight")
        self.assertEqual(straight["stand"], near["stand"])
        self.assertEqual(straight["departure"], near["departure"])
        self.assertEqual(straight["posted_notice"], near["posted_notice"])
        self.assertEqual(build("near_stand_straight"), build("near_stand"))
        points = route_points(straight)
        self.assertEqual(points[-1], (42, -1.75))
        self.assertTrue(all(abs(y + 1.75) < 1e-8 for x, y in points[1:]))
        controller = RouteController(straight)
        self.assertEqual(controller.points[-1], (42, -1.75))

    def test_spawn_checks_exact_native_map_and_curb_position(self):
        data = build("near_stand")
        world = FakeWorld(data)
        actor = spawn_taxi(world, FakeCarla, make("near_stand"), data, "vehicle.test.taxi")
        self.assertIs(actor, world.actor)
        self.assertEqual((actor.transform.location.x, actor.transform.location.y), (-55, -4.5))
        self.assertEqual(world.blueprint.attributes["role_name"], "c150530_taxi")

    def test_native_map_readback_mismatch_is_rejected(self):
        data = build("near_stand")
        world = FakeWorld(data.replace(b"first street intersection", b"other street intersection"))
        with self.assertRaisesRegex(ValueError, "readback differs"):
            validate_native_map(world, data, "near_stand")

    def test_missing_vehicle_blueprint_is_rejected(self):
        data = build("near_stand")
        with self.assertRaisesRegex(ValueError, "unavailable"):
            spawn_taxi(FakeWorld(data), FakeCarla, make("near_stand"), data, "vehicle.other")

    def test_controller_steps_and_stops(self):
        controller = RouteController(make("near_stand"))
        first = controller.control(-55, -4.5, 0, 0)
        self.assertFalse(first["finished"])
        self.assertGreater(first["throttle"], 0)
        for x, y in controller.points:
            last = controller.control(x, y, 0, 2)
        self.assertTrue(last["finished"])
        self.assertEqual(last["brake"], 1)

    def test_apply_step_sends_vehicle_control(self):
        data = build("near_stand")
        actor = spawn_taxi(FakeWorld(data), FakeCarla, make("near_stand"), data, "vehicle.test.taxi")
        command = apply_step(actor, FakeCarla, RouteController(make("near_stand")))
        self.assertEqual(actor.command.steer, command["steer"])


if __name__ == "__main__":
    unittest.main()
