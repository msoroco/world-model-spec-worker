import importlib.util
from pathlib import Path
import types
import unittest


MODULE = Path(__file__).resolve().parents[1] / "native_operation.py"
spec = importlib.util.spec_from_file_location("native_operation", MODULE)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class FakeActor:
    id = 42
    is_alive = True
    type_id = "vehicle.test.ego"

    def __init__(self):
        self.controls = []

    def apply_control(self, control):
        self.controls.append(control)

    def get_transform(self):
        return types.SimpleNamespace(location=types.SimpleNamespace(x=1.0, y=0.5))

    def get_velocity(self):
        return types.SimpleNamespace(x=2.0, y=0.0)

    def get_acceleration(self):
        return types.SimpleNamespace(x=-0.5, y=0.0)

    def get_angular_velocity(self):
        return types.SimpleNamespace(z=3.0)


class FakeWorld:
    def __init__(self):
        self.map = types.SimpleNamespace(name="reviewed_alley_map")
        self.actor = FakeActor()
        self.spawn_calls = []

    def get_map(self):
        return self.map

    def get_blueprint_library(self):
        return types.SimpleNamespace(find=lambda identifier: identifier)

    def try_spawn_actor(self, blueprint, transform):
        self.spawn_calls.append((blueprint, transform))
        return self.actor


CARLA = types.SimpleNamespace(
    Location=lambda **kwargs: kwargs,
    Rotation=lambda **kwargs: kwargs,
    Transform=lambda location, rotation: (location, rotation),
    VehicleControl=lambda **kwargs: kwargs,
)
SITE = {
    "map_name": "reviewed_alley_map",
    "alley_route_source": "source-alley",
    "access_aisle_source": "source-aisle-markings",
    "parking_designation_source": "source-parking-designation",
    "municipal_jurisdiction_source": "source-jurisdiction",
    "ego_blueprint_id": "vehicle.test.ego",
    "ego_spawn_xyz_m": [-18.0, 0.0, 0.2],
    "ego_yaw_deg": 0.0,
    "fps": 20,
}


class NativeOperationTests(unittest.TestCase):
    def test_both_cases_spawn_and_apply_distinct_control(self):
        for case_id in native.CASE_PROFILES:
            with self.subTest(case_id=case_id):
                world = FakeWorld()
                actor = native.spawn_ego(world, CARLA, SITE, case_id)
                self.assertIs(actor, world.actor)
                self.assertEqual(world.spawn_calls[0][0], SITE["ego_blueprint_id"])
                request = native.request_control(actor, CARLA, case_id, 0.5)
                self.assertEqual(actor.controls[-1]["steer"], request["requested_steer"])
                if case_id.endswith("__steady_travel"):
                    self.assertEqual(request["requested_steer"], 0.0)
                else:
                    self.assertGreater(request["requested_steer"], 0.0)

    def test_site_source_and_native_map_are_required(self):
        case_id = next(iter(native.CASE_PROFILES))
        bad = SITE.copy()
        bad.pop("access_aisle_source")
        with self.assertRaisesRegex(ValueError, "access_aisle_source"):
            native.spawn_ego(FakeWorld(), CARLA, bad, case_id)
        world = FakeWorld()
        world.map.name = "wrong_map"
        with self.assertRaisesRegex(ValueError, "map"):
            native.spawn_ego(world, CARLA, SITE, case_id)

    def test_original_sample_and_20hz_history(self):
        case_id = next(iter(native.CASE_PROFILES))
        actor = FakeActor()
        samples = []
        for index in range(4):
            snapshot = types.SimpleNamespace(frame=100 + index,
                timestamp=types.SimpleNamespace(elapsed_seconds=5.0 + index * .05))
            samples.append(native.sample_original(actor, snapshot, case_id, "operator-1"))
        receipt = native.validate_history(samples, case_id)
        self.assertEqual(receipt["original_frames"], 4)
        self.assertFalse(receipt["interior_attention_observed"])
        self.assertEqual(samples[0]["accel_longitudinal_m_s2"], -.5)
        altered = [row.copy() for row in samples]
        altered[2]["native_time_s"] += .01
        with self.assertRaisesRegex(ValueError, "20 Hz"):
            native.validate_history(altered, case_id)
        context = [{"source_kind": "original_native_context_state",
                    "case_id": case_id, "native_frame": row["native_frame"],
                    "source_sha256": "a" * 64, "straddles_marking": False,
                    "time_to_conflict_s": None, "traffic_signal": "unknown"}
                   for row in samples]
        joined = native.assemble_measurement_rows(samples, context, case_id)
        self.assertEqual([row["frame"] for row in joined], list(range(4)))
        self.assertEqual(joined[1]["time_s"], .05)
        missing = [row.copy() for row in context]
        missing[2].pop("straddles_marking")
        with self.assertRaisesRegex(ValueError, "straddles_marking"):
            native.assemble_measurement_rows(samples, missing, case_id)


if __name__ == "__main__":
    unittest.main()
