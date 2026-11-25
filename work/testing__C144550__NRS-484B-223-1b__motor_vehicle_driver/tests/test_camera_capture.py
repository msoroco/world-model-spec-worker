import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from camera_capture import FourCameras
from test_native_construction import reviewed_packet


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

    def set_attribute(self, name, value):
        self.attributes[name] = value


class World:
    def __init__(self):
        self.sensors = []
        self.attached = []

    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda name: Blueprint())

    def spawn_actor(self, blueprint, transform, attach_to=None):
        sensor = Sensor()
        self.sensors.append(sensor)
        self.attached.append(attach_to)
        return sensor


class CameraTests(unittest.TestCase):
    def make(self):
        world = World()
        carla = SimpleNamespace(Location=lambda **kw: kw, Rotation=lambda **kw: kw,
                                Transform=lambda a, b: (a, b))
        ego = object()
        sizes = {name: (2, 1) for name in (
            "overview", "approach", "reference_corner", "driver_reference")}
        cameras = FourCameras(world, carla, reviewed_packet(), ego, sizes=sizes)
        return world, cameras, ego

    def test_four_created_views_join_exact_native_time_and_pixels(self):
        world, cameras, ego = self.make()
        self.assertEqual(world.attached, [None, None, None, ego])
        for sensor in world.sensors:
            sensor.callback(SimpleNamespace(frame=100, timestamp=5.0,
                width=2, height=1, raw_data=bytes([0, 0, 255, 255] * 2)))
        views = cameras.read(100, 5.0)
        self.assertEqual(set(views), set(cameras.sizes))
        self.assertTrue(all(data.startswith(b"\x89PNG") for data in views.values()))
        cameras.close()
        self.assertTrue(all(s.stopped and s.destroyed for s in world.sensors))

    def test_stale_camera_timestamp_rejected_even_on_same_frame(self):
        world, cameras, _ = self.make()
        for sensor in world.sensors:
            sensor.callback(SimpleNamespace(frame=100, timestamp=4.5,
                width=2, height=1, raw_data=bytes(8)))
        with self.assertRaisesRegex(ValueError, "frame/time"):
            cameras.read(100, 5.0)
        cameras.close()


if __name__ == "__main__":
    unittest.main()
