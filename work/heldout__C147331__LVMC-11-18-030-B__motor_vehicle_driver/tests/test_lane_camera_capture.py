import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lane_camera_capture import CAMERAS, LaneCameraCapture


class Sensor:
    def __init__(self):
        self.callback = None
        self.destroyed = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        pass

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

    def get_blueprint_library(self):
        return NS(find=lambda _: Blueprint())

    def spawn_actor(self, blueprint, transform, attach_to):
        sensor = Sensor()
        self.sensors.append(sensor)
        return sensor


class Sink:
    def __init__(self):
        self.frames = []

    def write(self, image):
        self.frames.append(image.frame)


class CameraCaptureTests(unittest.TestCase):
    def test_four_sources_join_and_missing_source_rejected(self):
        world = World()
        carla = NS(Location=lambda *values: values, Rotation=lambda *values: values,
                   Transform=lambda location, rotation: (location, rotation))
        sinks = {name: Sink() for name in CAMERAS}
        cameras = LaneCameraCapture(world, carla, object(), sinks)
        self.assertEqual(len(world.sensors), 4)
        for sensor, (name, spec) in zip(world.sensors, CAMERAS.items()):
            width, height = spec[2]
            sensor.callback(NS(frame=20, width=width, height=height))
        cameras.wait_for_frame(20, timeout_s=0.01)
        self.assertEqual(cameras.verify([20]), {name: 1 for name in CAMERAS})
        with self.assertRaisesRegex(ValueError, "Missing or extra"):
            cameras.verify([20, 21])
        world.sensors[0].callback(NS(frame=20, width=1920, height=1080))
        with self.assertRaisesRegex(ValueError, "callback failed"):
            cameras.wait_for_frame(20, timeout_s=0.01)
        cameras.close()
        self.assertTrue(all(sensor.destroyed for sensor in world.sensors))


if __name__ == "__main__":
    unittest.main()
