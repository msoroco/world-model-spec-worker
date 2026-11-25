import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from test_native_site import Map, request, SITE


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SPEC = importlib.util.spec_from_file_location("native_run", ROOT / "native_run.py")
LIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LIVE)


class Blueprint:
    def __init__(self, name):
        self.id = name

    def set_attribute(self, *_):
        pass


class Actor:
    def __init__(self, actor_id, blueprint, transform):
        self.id = actor_id
        self.type_id = blueprint.id
        self.transform = transform
        self.control = SimpleNamespace(brake=0.0)
        self.bounding_box = SimpleNamespace(extent=SimpleNamespace(x=0.5, y=0.5))
        self.destroyed = False

    def get_location(self):
        return self.transform.location

    def get_transform(self):
        return self.transform

    def get_velocity(self):
        return SimpleNamespace(x=8.0, y=0.0, z=0.0)

    def get_control(self):
        return self.control

    def apply_control(self, control):
        self.control = control

    def destroy(self):
        self.destroyed = True


class Sensor:
    def __init__(self, actor_id, blueprint):
        self.id = actor_id
        self.type_id = blueprint.id
        self.callback = None
        self.destroyed = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        pass

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.settings = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None)
        self.actors = []
        self.sensors = []
        self.frame = 100
        self.person = Actor(42, Blueprint("walker.person"),
                            SimpleNamespace(location=SimpleNamespace(x=0.0, y=-20.0, z=0.0),
                                            rotation=SimpleNamespace(yaw=0.0)))

    def get_map(self):
        return Map()

    def get_blueprint_library(self):
        allowed = {"vehicle.sedan", "vehicle.bicycle", "sensor.camera.rgb", "sensor.other.collision"}
        return SimpleNamespace(find=lambda name: Blueprint(name) if name in allowed else None)

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings

    def try_spawn_actor(self, blueprint, transform):
        actor = Actor(len(self.actors) + 1, blueprint, transform)
        self.actors.append(actor)
        return actor

    def spawn_actor(self, blueprint, transform, attach_to=None):
        sensor = Sensor(len(self.sensors) + 10, blueprint)
        self.sensors.append(sensor)
        return sensor

    def get_actor(self, actor_id):
        return self.person if actor_id == 42 else None

    def tick(self):
        frame = self.frame
        self.frame += 1
        for sensor in self.sensors:
            if sensor.type_id == "sensor.camera.rgb":
                sensor.callback(SimpleNamespace(frame=frame, width=2, height=2,
                                                raw_data=bytes([3, 2, 1, 255] * 4)))
        return frame


CARLA = SimpleNamespace(
    Location=lambda **values: SimpleNamespace(**values),
    Rotation=lambda **values: SimpleNamespace(**values),
    Transform=lambda location=None, rotation=None: SimpleNamespace(location=location, rotation=rotation),
    VehicleControl=lambda **values: SimpleNamespace(**values))


class LiveRunTests(unittest.TestCase):
    def test_mock_native_capture_lifecycle_and_source_gates(self):
        scratch = REPO / ".runtime-work/c111260-native-run-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            base = Path(tmp)
            refs = SITE.survey(World(), CARLA, request(base), base / "survey")
            site = SITE.verify(base / "survey", refs["site"], expected_kind="bicycle")
            case = ROOT.name + "__bicycle_brake"
            pose = {key: 0 for key in ("x", "y", "z", "pitch", "yaw", "roll")}
            plan = {"format": "c111260-reviewed-camera-plan-v1", "case_id": case,
                    "map_sha256": site["map_sha256"],
                    "cameras": {name: {"width": 2, "height": 2, "attachment": "world",
                                       "fov_deg": 90, "transform": pose}
                                for name in LIVE.CAMERAS.PROFILE}}
            path = base / "camera-review.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            original_profile = LIVE.CAMERAS.PROFILE
            original_video_profile = LIVE.VIDEO.PRODUCTION_PROFILE
            LIVE.CAMERAS.PROFILE = {name: (2, 2) for name in original_profile}
            LIVE.VIDEO.PRODUCTION_PROFILE = dict(LIVE.CAMERAS.PROFILE)
            try:
                world = World()
                receipt = LIVE.run(world, CARLA, case_id=case,
                                   site_root=base / "survey", site_ref=refs["site"],
                                   camera_review_path=path, camera_review_sha256=digest,
                                   output_dir=base / "attempt")
                self.assertEqual(receipt["frames"], 900)
                self.assertEqual(receipt["physical_review"], "pending")
                self.assertFalse(world.settings.synchronous_mode)
                self.assertTrue(all(actor.destroyed for actor in world.actors))
                self.assertTrue(all(sensor.destroyed for sensor in world.sensors))
                with self.assertRaisesRegex(ValueError, "hash drift"):
                    LIVE.run(World(), CARLA, case_id=case, site_root=base / "survey",
                             site_ref=refs["site"], camera_review_path=path,
                             camera_review_sha256="0" * 64, output_dir=base / "reject")
            finally:
                LIVE.CAMERAS.PROFILE = original_profile
                LIVE.VIDEO.PRODUCTION_PROFILE = original_video_profile


if __name__ == "__main__":
    unittest.main()
