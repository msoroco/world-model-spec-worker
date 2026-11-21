import importlib.util
import types
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "native_inoperative_control", Path(__file__).resolve().parents[1] / "native_inoperative_control.py")
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


class Light:
    def __init__(self, ident, lane, state="Green", ignores_off=False, frozen=False):
        self.id, self.lane, self.state, self.frozen, self.ignores_off = ident, lane, state, frozen, ignores_off

    def get_affected_lane_waypoints(self):
        return [types.SimpleNamespace(road_id=self.lane[0], lane_id=self.lane[1])]

    def get_state(self):
        return self.state

    def set_state(self, state):
        if state != "Off" or not self.ignores_off:
            self.state = state

    def freeze(self, value):
        self.frozen = value

    def is_frozen(self):
        return self.frozen


class World:
    def __init__(self, lights):
        self.lights, self.ticks = lights, 0

    def get_actors(self):
        return types.SimpleNamespace(filter=lambda pattern: self.lights)

    def tick(self):
        self.ticks += 1


class Actor:
    def __init__(self, speed):
        self.speed, self.commands = speed, []

    def get_velocity(self):
        return types.SimpleNamespace(x=self.speed, y=0, z=0)

    def apply_control(self, command):
        self.commands.append(command)


class NativeControlTests(unittest.TestCase):
    def test_rolling_comparison_preserves_observed_motion(self):
        carla = types.SimpleNamespace(VehicleControl=lambda: types.SimpleNamespace())
        actor = Actor(2.0)
        planner = control.RollingController(target_speed_mps=3.0, minimum_speed_mps=1.0)
        row = planner.step(carla, actor, 21, -0.1)
        self.assertTrue(row["rolling_comparison"])
        self.assertEqual(row["speed_mps"], 2.0)
        self.assertGreater(row["throttle"], 0)
        self.assertEqual(row["brake"], 0)
        actor.speed = 0.0
        self.assertEqual(planner.step(carla, actor, 22, -0.2)["speed_mps"], 0.0)
        with self.assertRaisesRegex(ValueError, "Bounded rolling"):
            control.RollingController(target_speed_mps=3.0, minimum_speed_mps=4.0)

    def test_all_governed_heads_off_and_restored_after_capture(self):
        lights = [Light(10, (1, -1)), Light(20, (2, -1), "Red", frozen=True)]
        world = World(lights)
        selected = control.governing_lights(world, [[1, -1], [2, -1]])
        with control.all_heads_off(world, selected, types.SimpleNamespace(Off="Off")):
            self.assertEqual([light.state for light in lights], ["Off", "Off"])
            self.assertTrue(all(light.frozen for light in lights))
        self.assertEqual([light.state for light in lights], ["Green", "Red"])
        self.assertEqual([light.frozen for light in lights], [False, True])
        self.assertEqual(world.ticks, 2)

    def test_rejects_duplicate_governance_and_failed_off_readback(self):
        world = World([Light(10, (1, -1)), Light(20, (2, -1), ignores_off=True)])
        with self.assertRaisesRegex(ValueError, "governing Native light"):
            control.governing_lights(world, [[1, -1], [3, -1]])
        lights = control.governing_lights(world, [[1, -1], [2, -1]])
        with self.assertRaisesRegex(ValueError, "Off readback"):
            with control.all_heads_off(world, lights, types.SimpleNamespace(Off="Off")):
                pass
        self.assertEqual([light.state for light in lights], ["Green", "Green"])

    def test_measured_halt_and_order_gate_release(self):
        carla = types.SimpleNamespace(VehicleControl=lambda: types.SimpleNamespace())
        actor = Actor(3)
        planner = control.StopController(release_frame=102, target_speed_mps=5)
        pre = planner.step(carla, actor, 100, 3)
        self.assertFalse(pre["held"])
        hold = planner.step(carla, actor, 101, 0.2)
        self.assertTrue(hold["held"])
        self.assertEqual(hold["brake"], 1)
        actor.speed = 0
        stopped = planner.step(carla, actor, 102, 0.2, release_condition=False)
        self.assertEqual(stopped["full_halt_frame"], 102)
        self.assertTrue(stopped["held"])
        released = planner.step(carla, actor, 103, 0.2, release_condition=True)
        self.assertFalse(released["held"])
        self.assertGreater(released["throttle"], 0)

    def test_rejects_crossing_without_measured_halt(self):
        carla = types.SimpleNamespace(VehicleControl=lambda: types.SimpleNamespace())
        planner = control.StopController(release_frame=0, target_speed_mps=5)
        with self.assertRaisesRegex(ValueError, "without measured full halt"):
            planner.step(carla, Actor(2), 1, -0.1)

    def test_brakes_before_boundary_and_requires_observed_zero(self):
        carla = types.SimpleNamespace(VehicleControl=lambda: types.SimpleNamespace())
        actor = Actor(6)
        planner = control.StopController(release_frame=10, target_speed_mps=6)
        far = planner.step(carla, actor, 0, 12)
        near = planner.step(carla, actor, 1, 1.0)
        self.assertEqual(far["brake"], 0)
        self.assertGreater(near["brake"], 0)
        self.assertEqual(near["throttle"], 0)
        actor.speed = 0.005
        crawl = planner.step(carla, actor, 11, 0.2)
        self.assertIsNone(crawl["full_halt_frame"])
        self.assertTrue(crawl["held"])
        actor.speed = 0
        stopped = planner.step(carla, actor, 12, 0.2)
        self.assertEqual(stopped["full_halt_frame"], 12)
        released = planner.step(carla, actor, 13, 0.2)
        self.assertFalse(released["held"])

    def test_rejects_unbounded_approach_deceleration(self):
        with self.assertRaisesRegex(ValueError, "approach deceleration"):
            control.StopController(10, 5, approach_deceleration_mps2=0)


if __name__ == "__main__":
    unittest.main()
