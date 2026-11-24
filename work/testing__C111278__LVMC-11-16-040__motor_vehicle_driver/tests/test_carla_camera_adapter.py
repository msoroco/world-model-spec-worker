import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import carla_camera_adapter as adapter
from native_sight_capture import CaptureError


class Sensor:
    def __init__(self):
        self.callback = None
        self.stopped = False
    def listen(self, callback):
        self.callback = callback
    def stop(self):
        self.stopped = True
    def emit(self, frame=7, timestamp=.35, width=2, height=2, raw=None):
        if raw is None:
            raw = bytes([150, 90, 30, 255]) * (width * height)
        self.callback(SimpleNamespace(frame=frame, timestamp=timestamp,
                                      width=width, height=height, raw_data=raw))


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.profile = {name: (2, 2) for name in adapter.CAMERAS}
        self.patch = patch.object(adapter, "CAMERAS", self.profile)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.sensors = {name: Sensor() for name in self.profile}
        self.bridge = adapter.CameraAdapter(self.sensors, timeout_s=.01)
        self.bridge.start()
        self.addCleanup(self.bridge.stop)
        self.snapshot = SimpleNamespace(timestamp=SimpleNamespace(elapsed_seconds=.35))

    def test_native_bgra_is_converted_to_four_frame_bound_pngs(self):
        from PIL import Image
        from io import BytesIO
        for sensor in self.sensors.values():
            sensor.emit()
        images = self.bridge.read(7, self.snapshot)
        self.assertEqual(set(images), set(self.profile))
        for frame, raw in images.values():
            self.assertEqual(frame, 7)
            with Image.open(BytesIO(raw)) as image:
                image.load()
                self.assertEqual(image.size, (2, 2))
                self.assertEqual(image.getpixel((0, 0)), (30, 90, 150))
        self.bridge.stop()
        self.assertTrue(all(sensor.stopped for sensor in self.sensors.values()))

    def test_wrong_frame_and_timestamp_rejected(self):
        for sensor in self.sensors.values():
            sensor.emit(frame=8)
        with self.assertRaisesRegex(CaptureError, "frame identity"):
            self.bridge.read(7, self.snapshot)
        for sensor in self.sensors.values():
            sensor.emit(timestamp=.36)
        with self.assertRaisesRegex(CaptureError, "timestamp differs"):
            self.bridge.read(7, self.snapshot)

    def test_missing_source_and_queue_overflow_rejected(self):
        with self.assertRaisesRegex(CaptureError, "frame missing"):
            self.bridge.read(7, self.snapshot)
        for _ in range(3):
            self.sensors["overview"].emit()
        with self.assertRaisesRegex(CaptureError, "queue overflow"):
            self.bridge.read(7, self.snapshot)


if __name__ == "__main__": unittest.main()
