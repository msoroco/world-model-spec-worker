import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_controller import exact_case_target, run_bicycle_route, target_velocity


CARLA = SimpleNamespace(Vector3D=lambda **kw: SimpleNamespace(**kw))


class Bicycle:
    def __init__(self, moving=True, drift=0):
        self.location = SimpleNamespace(x=-30.0, y=-.75)
        self.velocity = CARLA.Vector3D(x=0.0, y=0.0, z=0.0)
        self.command = CARLA.Vector3D(x=0.0, y=0.0, z=0.0)
        self.moving = moving
        self.drift = drift

    def set_target_velocity(self, value):
        self.command = value

    def get_transform(self):
        return SimpleNamespace(location=self.location)

    def get_velocity(self):
        return self.velocity


class World:
    def __init__(self, bicycle):
        self.bicycle = bicycle
        self.frame = 0

    def tick(self):
        self.frame += 1
        if self.bicycle.moving:
            self.bicycle.location.x += self.bicycle.command.x / 20
            self.bicycle.location.y += self.bicycle.drift / 20
            self.bicycle.velocity = self.bicycle.command
        return self.frame

    def get_snapshot(self):
        return SimpleNamespace(frame=self.frame,
                               timestamp=SimpleNamespace(elapsed_seconds=(self.frame - 1) / 20))


class NativeControllerTests(unittest.TestCase):
    def test_all_five_exact_cases_bind_to_controller(self):
        plan = Path(__file__).resolve().parents[1] / "case-plan.json"
        for suffix, expected in (("reference", 3), ("faster", 5),
                                 ("reduced_visibility", 3),
                                 ("pedestrian_near_rack", 3), ("wet_surface", 3)):
            case_id = "testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator__" + suffix
            self.assertEqual(exact_case_target(plan, case_id), expected)
        with self.assertRaisesRegex(ValueError, "unknown exact bicycle case"):
            exact_case_target(plan, "testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator__unknown")

    def test_exact_route_measured_completion(self):
        bike = Bicycle()
        samples = run_bicycle_route(World(bike), CARLA, bike, target_speed_mps=5.0)
        self.assertGreaterEqual(len(samples), 20)
        self.assertGreaterEqual(samples[-1]["x_m"], 30)
        self.assertEqual(samples[0]["time_s"], 0)
        self.assertAlmostEqual(samples[-1]["time_s"], (len(samples)-1)/20)
        self.assertEqual(bike.command.x, 0)

    def test_stalled_static_asset_rejected_and_stopped(self):
        bike = Bicycle(moving=False)
        with self.assertRaisesRegex(ValueError, "failed measured-motion"):
            run_bicycle_route(World(bike), CARLA, bike, target_speed_mps=3.0)
        self.assertEqual(bike.command.x, 0)

    def test_lane_departure_rejected(self):
        bike = Bicycle(drift=2)
        with self.assertRaisesRegex(ValueError, "left checked alley route"):
            run_bicycle_route(World(bike), CARLA, bike, target_speed_mps=3.0)
        self.assertEqual(bike.command.x, 0)

    def test_target_and_start_validation(self):
        with self.assertRaisesRegex(ValueError, "speed target"):
            target_velocity(CARLA, -1)
        bike = Bicycle()
        bike.location.x = -25
        with self.assertRaisesRegex(ValueError, "start outside"):
            run_bicycle_route(World(bike), CARLA, bike, target_speed_mps=3.0)

    def test_original_clock_discontinuity_rejected(self):
        class BadClock(World):
            def get_snapshot(self):
                snapshot = super().get_snapshot()
                snapshot.timestamp.elapsed_seconds *= 2
                return snapshot
        bike = Bicycle()
        with self.assertRaisesRegex(ValueError, "frame/time continuity"):
            run_bicycle_route(BadClock(bike), CARLA, bike, target_speed_mps=3.0)
        self.assertEqual(bike.command.x, 0)


if __name__ == "__main__":
    unittest.main()
