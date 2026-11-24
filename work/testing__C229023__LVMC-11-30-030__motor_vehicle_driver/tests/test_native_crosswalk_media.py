import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("native_crosswalk_media", HERE / "native_crosswalk_media.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Image:
    def __init__(self, frame, size=64):
        self.frame = frame
        self.raw_data = bytes([frame % 255]) * size


class Sensor:
    def __init__(self):
        self.callback = None
        self.stopped = False
        self.destroyed = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class Blueprint:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class World:
    def __init__(self):
        self.sensors = []
        self.blueprints = []

    def get_blueprint_library(self):
        return self

    def find(self, name):
        assert name == "sensor.camera.rgb"
        bp = Blueprint()
        self.blueprints.append(bp)
        return bp

    def spawn_actor(self, blueprint, transform):
        sensor = Sensor()
        self.sensors.append(sensor)
        return sensor


class FakeCarla:
    @staticmethod
    def Location(**kwargs):
        return kwargs

    @staticmethod
    def Rotation(**kwargs):
        return kwargs

    @staticmethod
    def Transform(location, rotation):
        return location, rotation


class Encoder:
    def __init__(self):
        self.stdin = io.BytesIO()

    def poll(self):
        return None

    def wait(self, timeout):
        return 0


class NativeCrosswalkMediaTests(unittest.TestCase):
    def setUp(self):
        self.site = {"camera_poses": {name: {"location": [0, 0, 3], "target": [5, 0, 1]}
                                      for name in module.CAMERAS}}
        self.sizes = {name: (4, 4) for name in module.CAMERAS}
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_four_camera_setup_same_tick_and_cleanup(self):
        world = World()
        encoders = []
        def start(*args, **kwargs):
            encoder = Encoder()
            encoders.append(encoder)
            return encoder
        with patch.object(module.subprocess, "Popen", side_effect=start):
            cameras = module.NativeCrosswalkCameras(world=world, carla=FakeCarla,
                                                    site=self.site, output=self.root, sizes=self.sizes)
            self.assertEqual(len(world.sensors), 4)
            self.assertEqual([bp.attributes["image_size_x"] for bp in world.blueprints], ["4"] * 4)
            for sensor in world.sensors:
                sensor.callback(Image(99))
                sensor.callback(Image(100))
            images = cameras.append(100)
            self.assertEqual({name: image.frame for name, image in images.items()},
                             {name: 100 for name in module.CAMERAS})
            self.assertEqual([len(encoder.stdin.getvalue()) for encoder in encoders], [64] * 4)
            with self.assertRaisesRegex(RuntimeError, "incomplete 900-frame"):
                cameras.close()
            self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in world.sensors))

    def test_future_frame_and_queue_overflow_rejected(self):
        world = World()
        with patch.object(module.subprocess, "Popen", side_effect=lambda *a, **kw: Encoder()):
            cameras = module.NativeCrosswalkCameras(world=world, carla=FakeCarla,
                                                    site=self.site, output=self.root, sizes=self.sizes)
            for sensor in world.sensors:
                sensor.callback(Image(101))
            with self.assertRaisesRegex(RuntimeError, "future-frame mismatch"):
                cameras.append(100)
            for index in range(9):
                world.sensors[0].callback(Image(index))
            with self.assertRaisesRegex(RuntimeError, "queue overflow"):
                cameras.append(101)
            cameras.close(require_complete=False)

    def test_unsourced_or_degenerate_pose_rejected(self):
        with self.assertRaisesRegex(ValueError, "four reviewed"):
            module.NativeCrosswalkCameras(world=World(), carla=FakeCarla, site={},
                                          output=self.root, sizes=self.sizes)
        self.site["camera_poses"]["overview"]["target"] = [0, 0, 1]
        with patch.object(module.subprocess, "Popen", side_effect=lambda *a, **kw: Encoder()):
            with self.assertRaisesRegex(ValueError, "horizontal target"):
                module.NativeCrosswalkCameras(world=World(), carla=FakeCarla,
                                              site=self.site, output=self.root, sizes=self.sizes)


if __name__ == "__main__":
    unittest.main()
