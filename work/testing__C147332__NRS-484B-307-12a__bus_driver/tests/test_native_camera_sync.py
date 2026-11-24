"""CARLA-free frame alignment and overflow checks for original camera capture."""
import io
from pathlib import Path
import queue
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import CAMERAS, CameraCapture


def capture_with_frames(frame_lists):
    capture = CameraCapture.__new__(CameraCapture)
    capture.overflow = False
    capture.queues = {}
    capture.encoders = {}
    for name in CAMERAS:
        capture.queues[name] = queue.Queue()
        capture.encoders[name] = SimpleNamespace(stdin=io.BytesIO())
        for frame in frame_lists[name]:
            capture.queues[name].put(SimpleNamespace(frame=frame, raw_data=bytes([frame])))
    return capture


class NativeCameraSyncTests(unittest.TestCase):
    def test_exact_world_frame_is_encoded_from_all_cameras(self):
        capture = capture_with_frames({name: [9, 10] for name in CAMERAS})
        capture.append(10)
        for name in CAMERAS:
            self.assertEqual(capture.encoders[name].stdin.getvalue(), b"\x0a")

    def test_future_frame_rejects_instead_of_mislabeling_video(self):
        capture = capture_with_frames({name: [11] for name in CAMERAS})
        with self.assertRaisesRegex(RuntimeError, "camera/world frame mismatch"):
            capture.append(10)

    def test_overflow_rejects_unsealed_capture(self):
        capture = capture_with_frames({name: [10] for name in CAMERAS})
        capture.overflow = True
        with self.assertRaisesRegex(RuntimeError, "camera queue overflow"):
            capture.append(10)
        self.assertEqual(capture.encoders[CAMERAS[0]].stdin.getvalue(), b"")

    def test_sensor_callback_overflow_is_reported(self):
        class Sensor:
            def listen(self, callback):
                self.callback = callback

            def stop(self):
                pass

            def destroy(self):
                pass

        class Blueprint:
            def set_attribute(self, name, value):
                pass

        class World:
            def __init__(self):
                self.sensors = []

            def get_blueprint_library(self):
                return self

            def find(self, identifier):
                return Blueprint()

            def spawn_actor(self, blueprint, transform, attach_to=None):
                sensor = Sensor()
                self.sensors.append(sensor)
                return sensor

        class Carla:
            @staticmethod
            def Location(**values):
                return values

            @staticmethod
            def Rotation(**values):
                return values

            @staticmethod
            def Transform(location, rotation):
                return location, rotation

        world = World()
        with patch("native_capture.subprocess.Popen", side_effect=lambda *args, **kwargs:
                   SimpleNamespace(stdin=io.BytesIO(), wait=lambda timeout: 0)):
            capture = CameraCapture(world, object(), {}, ROOT, Carla)
        for frame in range(9):
            world.sensors[0].callback(SimpleNamespace(frame=frame, raw_data=b"x"))
        with self.assertRaisesRegex(RuntimeError, "camera queue overflow"):
            capture.append(8)
        capture.close()


if __name__ == "__main__":
    unittest.main()
