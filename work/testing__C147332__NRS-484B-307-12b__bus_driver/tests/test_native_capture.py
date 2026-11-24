"""CPU checks for the original four-camera Native capture interface."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import CAMERAS, CameraCapture


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


class Encoder:
    def __init__(self):
        self.stdin = SimpleNamespace(closed=False, writes=[], write=self.write,
                                     close=self.close)

    def write(self, data):
        self.stdin.writes.append(data)

    def close(self):
        self.stdin.closed = True

    def wait(self, timeout):
        return 0


class NativeCameraTest(unittest.TestCase):
    def test_four_original_camera_frames_and_cleanup(self):
        sensors, encoders, commands = [], [], []

        class Blueprint:
            def set_attribute(self, name, value):
                pass

        class World:
            def get_blueprint_library(self):
                return SimpleNamespace(find=lambda name: Blueprint())

            def spawn_actor(self, blueprint, transform, attach_to=None):
                sensor = Sensor()
                sensors.append((sensor, attach_to))
                return sensor

        def popen(command, **kwargs):
            commands.append(command)
            encoder = Encoder()
            encoders.append(encoder)
            return encoder

        carla = SimpleNamespace(
            Location=lambda **kwargs: SimpleNamespace(**kwargs),
            Rotation=lambda **kwargs: SimpleNamespace(**kwargs),
            Transform=lambda location, rotation: (location, rotation),
        )
        bus = object()
        with tempfile.TemporaryDirectory() as directory, patch("native_capture.subprocess.Popen", popen):
            capture = CameraCapture(World(), bus, {}, directory, carla)
            self.assertEqual(len(sensors), 4)
            self.assertEqual([a for _, a in sensors], [None, None, None, bus])
            self.assertEqual([Path(c[-1]).stem for c in commands], list(CAMERAS))
            self.assertIn("1920x1080", commands[0])
            self.assertTrue(all("1280x720" in c for c in commands[1:]))
            self.assertTrue(all("ffv1" in c for c in commands))
            capture.dimensions = {name: (1, 1) for name in CAMERAS}
            for sensor, _ in sensors:
                sensor.callback(SimpleNamespace(frame=42, width=1, height=1, raw_data=b"BGRA"))
            hashes = capture.append(42)
            self.assertEqual(set(hashes), set(CAMERAS))
            self.assertTrue(all(e.stdin.writes == [b"BGRA"] for e in encoders))
            capture.close()
            self.assertTrue(all(s.stopped and s.destroyed for s, _ in sensors))
            self.assertTrue(all(e.stdin.closed for e in encoders))

    def test_world_camera_frame_mismatch_rejected(self):
        sensors = []

        class World:
            def get_blueprint_library(self):
                return SimpleNamespace(find=lambda name: SimpleNamespace(set_attribute=lambda *a: None))

            def spawn_actor(self, *args, **kwargs):
                sensor = Sensor()
                sensors.append(sensor)
                return sensor

        carla = SimpleNamespace(Location=lambda **k: k, Rotation=lambda **k: k,
                                Transform=lambda a, b: (a, b))
        with tempfile.TemporaryDirectory() as directory, patch("native_capture.subprocess.Popen", return_value=Encoder()):
            capture = CameraCapture(World(), object(), {}, directory, carla)
            capture.dimensions = {name: (1, 1) for name in CAMERAS}
            for sensor in sensors:
                sensor.callback(SimpleNamespace(frame=41, width=1, height=1, raw_data=b"BGRA"))
            with self.assertRaisesRegex(RuntimeError, "camera/world frame mismatch"):
                capture.append(42)
            capture.close()

    def test_wrong_raw_shape_rejected_before_encoder_write(self):
        sensors, encoders = [], []

        class World:
            def get_blueprint_library(self):
                return SimpleNamespace(find=lambda name: SimpleNamespace(set_attribute=lambda *a: None))

            def spawn_actor(self, *args, **kwargs):
                sensor = Sensor()
                sensors.append(sensor)
                return sensor

        def popen(*args, **kwargs):
            encoder = Encoder()
            encoders.append(encoder)
            return encoder

        carla = SimpleNamespace(Location=lambda **k: k, Rotation=lambda **k: k,
                                Transform=lambda a, b: (a, b))
        with tempfile.TemporaryDirectory() as directory, patch("native_capture.subprocess.Popen", popen):
            capture = CameraCapture(World(), object(), {}, directory, carla)
            capture.dimensions = {name: (1, 1) for name in CAMERAS}
            for sensor in sensors:
                sensor.callback(SimpleNamespace(frame=42, width=1, height=1, raw_data=b"bad"))
            with self.assertRaisesRegex(RuntimeError, "BGRA shape mismatch"):
                capture.append(42)
            self.assertTrue(all(not encoder.stdin.writes for encoder in encoders))
            capture.close()


if __name__ == "__main__":
    unittest.main()
