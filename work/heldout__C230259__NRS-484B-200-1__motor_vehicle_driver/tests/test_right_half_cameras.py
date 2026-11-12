from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from right_half_cameras import CAMERAS, RightHalfCameraCapture


class Blueprint:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class Sensor:
    def __init__(self, blueprint):
        self.blueprint = blueprint
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
        return self

    def find(self, name):
        assert name == "sensor.camera.rgb"
        return Blueprint()

    def spawn_actor(self, blueprint, transform, attach_to=None):
        assert attach_to is not None
        sensor = Sensor(blueprint)
        self.sensors.append(sensor)
        return sensor


class Carla:
    @staticmethod
    def Location(*values):
        return values

    @staticmethod
    def Rotation(*values):
        return values

    @staticmethod
    def Transform(location, rotation):
        return location, rotation


class Sink:
    def __init__(self):
        self.frames = 0

    def write(self, image):
        self.frames += 1


class Image:
    def __init__(self, frame, size):
        self.frame = frame
        self.width, self.height = size


class CameraTest(unittest.TestCase):
    def test_four_original_cameras_are_configured_and_joined(self):
        world = World()
        sinks = {name: Sink() for name in CAMERAS}
        capture = RightHalfCameraCapture(world, Carla, object(), sinks)
        self.assertEqual(len(world.sensors), 4)
        for sensor, (name, profile) in zip(world.sensors, CAMERAS.items()):
            self.assertEqual(sensor.blueprint.attributes["image_size_x"],
                             str(profile[2][0]))
            self.assertEqual(sensor.blueprint.attributes["image_size_y"],
                             str(profile[2][1]))
            self.assertEqual(sensor.blueprint.attributes["sensor_tick"], "0.05")
            sensor.callback(Image(100, profile[2]))
        capture.wait_for_frame(100, timeout_s=0.01)
        self.assertEqual(capture.verify([100]), {name: 1 for name in CAMERAS})
        world.sensors[0].callback(Image(100, CAMERAS["overview"][2]))
        with self.assertRaisesRegex(ValueError, "callback failed"):
            capture.wait_for_frame(100, timeout_s=0.01)
        capture.close()
        self.assertTrue(all(sensor.stopped and sensor.destroyed
                            for sensor in world.sensors))

    def test_missing_named_camera_rejected(self):
        with self.assertRaisesRegex(ValueError, "Exactly four"):
            RightHalfCameraCapture(World(), Carla, object(), {"overview": Sink()})


if __name__ == "__main__":
    unittest.main()
