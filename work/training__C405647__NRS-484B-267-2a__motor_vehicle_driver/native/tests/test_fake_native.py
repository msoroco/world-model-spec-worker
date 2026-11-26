"""Exercise the capture path with explicit synthetic CARLA substitutes."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[2] / ".runtime-work" / "c405647-fake-native-tests"
for name in ("capture_runner", "observed_speed"):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    globals()[name] = module


class Vector:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z


class Rotation:
    def __init__(self, pitch=0, yaw=0, roll=0):
        self.pitch, self.yaw, self.roll = pitch, yaw, roll


class Transform:
    def __init__(self, location, rotation):
        self.location, self.rotation = location, rotation


class Control:
    def __init__(self, throttle=0, brake=0, steer=0):
        self.throttle, self.brake, self.steer = throttle, brake, steer


class Blueprint:
    def __init__(self, name):
        self.name = name
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class Actor:
    def __init__(self, role, pose, actor_id):
        self.role, self.pose, self.id = role, pose, actor_id
        self.speed = 14.0 if role == "ego" else 2.0
        self.light = 0
        self.destroyed = False

    def get_velocity(self):
        return Vector(self.speed)

    def get_transform(self):
        return self.pose

    def apply_control(self, control):
        if self.role == "ego" and control.brake:
            self.speed = 7.0

    def set_light_state(self, light):
        self.light = light

    def get_light_state(self):
        return self.light

    def destroy(self):
        self.destroyed = True


class Image:
    def __init__(self, frame):
        self.frame = frame

    def save_to_disk(self, path):
        Path(path).write_bytes(b"synthetic-image-only")


class Sensor(Actor):
    def __init__(self, pose, actor_id):
        super().__init__("camera", pose, actor_id)
        self.callback = None
        self.stopped = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True


class World:
    def __init__(self):
        self.actors = []
        self.sensors = []
        self.frame = 1000
        self.settings = types.SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None)

    def get_map(self):
        return types.SimpleNamespace(name="synthetic-road")

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings

    def get_blueprint_library(self):
        return types.SimpleNamespace(find=lambda name: Blueprint(name))

    def try_spawn_actor(self, blueprint, pose):
        role = "ego" if not self.actors else "emergency"
        actor = Actor(role, pose, len(self.actors) + 1)
        self.actors.append(actor)
        return actor

    def spawn_actor(self, blueprint, pose, attach_to=None):
        sensor = Sensor(pose, len(self.actors) + len(self.sensors) + 1)
        self.sensors.append(sensor)
        return sensor

    def tick(self):
        self.frame += 1
        for actor in self.actors:
            actor.pose.location.x += actor.speed / 20
        for sensor in self.sensors:
            sensor.callback(Image(self.frame))
        return self.frame

    def get_snapshot(self):
        return types.SimpleNamespace(timestamp=types.SimpleNamespace(elapsed_seconds=self.frame / 20))


class Client:
    def __init__(self, host, port):
        self.world = WORLD

    def set_timeout(self, timeout):
        pass

    def get_world(self):
        return self.world


class Capture:
    def __init__(self, client, ego, output, case_id, required_observations=()):
        self.frames = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def capture(self, frame, time_s, extra=None):
        self.frames.append(frame)


class FrameMap:
    def __init__(self, path):
        self.path = Path(path)
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.path.write_text("".join(json.dumps(row) + "\n" for row in self.rows))

    def append(self, frame, time_s, **extra):
        self.rows.append({"native_frame": frame, "time_s": time_s, **extra})


def modules():
    carla = types.ModuleType("carla")
    carla.Location = Vector
    carla.Rotation = Rotation
    carla.Transform = Transform
    carla.VehicleControl = Control
    carla.VehicleLightState = types.SimpleNamespace(Special1=1, Special2=2)
    carla.Client = Client
    pipeline = types.ModuleType("pipeline_capture")
    pipeline.PipelineCapture = Capture
    native = types.ModuleType("scenario_pipeline.worker_exchange.native_output")
    native.FrameMap = FrameMap
    restore = types.ModuleType("scenario_pipeline.worker_exchange.world_restore")
    restore.snapshot = lambda client: {"synthetic": True}
    restore.restore = lambda client, original: None
    return {"carla": carla, "pipeline_capture": pipeline,
            "scenario_pipeline.worker_exchange.native_output": native,
            "scenario_pipeline.worker_exchange.world_restore": restore}


class FakeNativeExecutionTest(unittest.TestCase):
    def test_actor_camera_and_source_trace_both_cases(self):
        global WORLD
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as directory:
            for suffix in ("a", "b"):
                with self.subTest(suffix=suffix):
                    WORLD = World()
                    construction = json.loads((ROOT / ("condition_" + suffix + "-construction.json")).read_text())
                    config = json.loads(construction["files"][0]["content"])
                    survey = {"source_kind": "original_native_site_survey",
                              "cell": {"layout": "road", "maneuver": "travel", "control": "emergency_vehicle"},
                              "map_name": "synthetic-road", "ego_blueprint": "synthetic-ego",
                              "emergency_blueprint": "synthetic-emergency",
                              "ego_spawn_xyz_yaw_deg": [-100, 0, 0.5, 0],
                              "emergency_spawn_xyz_yaw_deg": [100, 0, 0.5, 0],
                              "emergency_authorization_source_id": "synthetic-authorization",
                              "flashing_equipment_source_id": "synthetic-equipment",
                              "flashing_qualification_source_id": "synthetic-qualification",
                              "road_context_source_id": "synthetic-road",
                              "weather_context_source_id": "synthetic-weather",
                              "officer_direction_source_id": "synthetic-scene", "officer_direction": None,
                              "camera_poses": {name: [0, 0, 2, 0, 0, 0] for name in capture_runner.VIEWS}}
                    output = Path(directory) / suffix
                    with mock.patch.dict(sys.modules, modules()), \
                            mock.patch.dict(os.environ, {"SCENARIO_PIPELINE_OUTPUT_ROOT": str(SCRATCH)}):
                        capture_runner.execute(config, survey, output, "127.0.0.1", 2000,
                                               diagnostic_fixture=True)
                    self.assertEqual(len(WORLD.actors), 2)
                    self.assertEqual(len(WORLD.sensors), 4)
                    self.assertTrue(all(actor.destroyed for actor in WORLD.actors + WORLD.sensors))
                    self.assertTrue(all(sensor.stopped for sensor in WORLD.sensors))
                    result = observed_speed.measure(output / "emergency_observations.jsonl",
                                                    synthetic=True)
                    self.assertEqual(result["frames"], 600)
                    self.assertTrue(result["fixture_only"])


if __name__ == "__main__":
    unittest.main()
