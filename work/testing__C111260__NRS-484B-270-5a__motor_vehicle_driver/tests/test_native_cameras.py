import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from PIL import Image
import io


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("native_cameras", ROOT / "native_cameras.py")
CAMERAS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAMERAS)


class Blueprint:
    id = "sensor.camera.rgb"

    def set_attribute(self, name, value):
        pass


class Sensor:
    def __init__(self, actor_id):
        self.id = actor_id
        self.callback = None
        self.stopped = False
        self.destroyed = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.sensors = []

    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda name: Blueprint() if name == "sensor.camera.rgb" else None)

    def spawn_actor(self, blueprint, transform, attach_to=None):
        sensor = Sensor(len(self.sensors) + 10)
        self.sensors.append(sensor)
        return sensor


CARLA = SimpleNamespace(
    Location=lambda **values: SimpleNamespace(**values),
    Rotation=lambda **values: SimpleNamespace(**values),
    Transform=lambda location, rotation: SimpleNamespace(location=location, rotation=rotation))


def reviewed(case, map_sha):
    pose = {key: 0 for key in ("x", "y", "z", "pitch", "yaw", "roll")}
    return {"format": "c111260-reviewed-camera-plan-v1", "case_id": case,
            "map_sha256": map_sha,
            "cameras": {name: {"width": 2, "height": 2, "attachment": "world",
                               "fov_deg": 90, "transform": pose}
                        for name in CAMERAS.PROFILE}}


class CameraTests(unittest.TestCase):
    def setUp(self):
        self.original = CAMERAS.PROFILE
        CAMERAS.PROFILE = {name: (2, 2) for name in self.original}
        self.addCleanup(lambda: setattr(CAMERAS, "PROFILE", self.original))

    def test_reviewed_source_and_four_frame_callbacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review.json"
            path.write_text(json.dumps(reviewed("exact-case", "a" * 64)), encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            review = CAMERAS.load_review(path, digest, case_id="exact-case", map_sha256="a" * 64)
            world = World()
            with CAMERAS.OriginalCameras(world, CARLA, object(), review) as owned:
                for sensor in world.sensors:
                    sensor.callback(SimpleNamespace(frame=100, width=2, height=2,
                                                    raw_data=bytes([3, 2, 1, 255] * 4)))
                for name in CAMERAS.PROFILE:
                    payload = owned.camera_png(name, 100)
                    with Image.open(io.BytesIO(payload)) as image:
                        self.assertEqual(image.convert("RGB").getpixel((0, 0)), (1, 2, 3))
                with self.assertRaisesRegex(ValueError, "frame missing"):
                    owned.camera_png("overview", 101, timeout_s=0.001)
            self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in world.sensors))
            with self.assertRaisesRegex(ValueError, "hash drift"):
                CAMERAS.load_review(path, "0" * 64, case_id="exact-case", map_sha256="a" * 64)


if __name__ == "__main__":
    unittest.main()
