from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rider_camera import CAMERAS, RiderCameraCapture


class Sensor:
    def listen(self, callback):
        self.callback = callback

    def stop(self):
        pass

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.sensors = []

    def get_blueprint_library(self):
        return NS(find=lambda _: NS(set_attribute=lambda *args: None))

    def spawn_actor(self, blueprint, transform, attach_to):
        sensor = Sensor()
        self.sensors.append(sensor)
        return sensor


class Sink:
    def __init__(self):
        self.frames = []

    def write(self, image):
        self.frames.append(image.frame)


class CameraTests(unittest.TestCase):
    def test_four_named_frames_and_missing_frame_rejection(self):
        world = World()
        carla = NS(Location=lambda *values: values, Rotation=lambda *values: values,
                   Transform=lambda location, rotation: (location, rotation))
        sinks = {name: Sink() for name in CAMERAS}
        capture = RiderCameraCapture(world, carla, object(), sinks)
        self.assertEqual(len(world.sensors), 4)
        for sensor, (name, spec) in zip(world.sensors, CAMERAS.items()):
            width, height = spec[2]
            sensor.callback(NS(frame=20, width=width, height=height))
        capture.wait_for_frame(20, timeout_s=.01)
        self.assertEqual(capture.verify([20]), {name: 1 for name in CAMERAS})
        with self.assertRaisesRegex(ValueError, 'Missing or extra'):
            capture.verify([20, 21])
        capture.close()
        self.assertTrue(all(sensor.destroyed for sensor in world.sensors))


if __name__ == '__main__':
    unittest.main()
