import importlib.util
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location("camera_setup", Path(__file__).resolve().parents[1] / "camera_setup.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Blueprint:
    def __init__(self):
        self.attrs = {}

    def set_attribute(self, key, value):
        self.attrs[key] = value


class Sensor:
    def __init__(self):
        self.stopped = self.destroyed = False

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.calls = []
        self.sensors = []

    def get_blueprint_library(self):
        return self

    def find(self, name):
        assert name == "sensor.camera.rgb"
        return Blueprint()

    def spawn_actor(self, blueprint, transform, **kwargs):
        self.calls.append((blueprint.attrs.copy(), transform, kwargs))
        sensor = Sensor()
        self.sensors.append(sensor)
        return sensor


class CameraTests(unittest.TestCase):
    def test_four_native_spawns_profile_and_cleanup(self):
        world, ego = World(), object()
        transforms = {name: name + "-transform" for name in module.SIZES}
        with module.source_cameras(world, ego, transforms) as sensors:
            self.assertEqual(set(sensors), set(module.SIZES))
            self.assertEqual(world.calls[0][0]["image_size_x"], "1920")
            self.assertEqual(world.calls[0][0]["image_size_y"], "1080")
            self.assertEqual(world.calls[3][2], {"attach_to": ego})
            self.assertTrue(all(call[0]["sensor_tick"] == "0.05" for call in world.calls))
        self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in world.sensors))

    def test_missing_view_rejected(self):
        world = World()
        with self.assertRaisesRegex(ValueError, "four named"):
            with module.source_cameras(world, object(), {"overview": "only"}):
                pass
        self.assertFalse(world.calls)


if __name__ == "__main__":
    unittest.main()
