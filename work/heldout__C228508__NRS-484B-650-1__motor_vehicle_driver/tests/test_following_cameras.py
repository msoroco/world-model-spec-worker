from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from following_cameras import CAMERAS, FollowingCameraCapture


class Blueprint:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class Sensor:
    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class Sink:
    def __init__(self):
        self.frames = []

    def write(self, image):
        self.frames.append(image.frame)


class World:
    def __init__(self):
        self.blueprints = []
        self.sensors = []

    def get_blueprint_library(self):
        def find(name):
            self.blueprints.append((name, Blueprint()))
            return self.blueprints[-1][1]
        return NS(find=find)

    def spawn_actor(self, blueprint, transform, attach_to):
        sensor = Sensor()
        self.sensors.append(sensor)
        return sensor


class CameraTests(unittest.TestCase):
    def test_four_named_original_streams_and_rejection(self):
        world = World()
        carla = NS(Location=lambda *values: values,
                   Rotation=lambda *values: values,
                   Transform=lambda location, rotation: (location, rotation))
        sinks = {name: Sink() for name in CAMERAS}
        capture = FollowingCameraCapture(world, carla, object(), sinks)
        self.assertEqual(len(world.sensors), 4)
        self.assertTrue(all(name == 'sensor.camera.rgb' for name, _ in world.blueprints))
        for sensor, (name, spec) in zip(world.sensors, CAMERAS.items()):
            width, height = spec[2]
            sensor.callback(NS(frame=20, width=width, height=height))
        self.assertEqual(capture.verify([20]), {name: 1 for name in CAMERAS})
        with self.assertRaisesRegex(ValueError, 'Missing or extra'):
            capture.verify([20, 21])
        capture.close()
        self.assertTrue(all(sensor.destroyed and sensor.stopped
                            for sensor in world.sensors))


if __name__ == '__main__':
    unittest.main()
