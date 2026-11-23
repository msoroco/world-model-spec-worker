from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_recorder import FourStreamRecorder, SIZES
from saved_entry import CAMERAS


class Sensor:
    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True


class Encoder:
    def __init__(self, command, **kwargs):
        self.command = command
        self.stdin = NS(write=lambda data: len(data), close=lambda: None)

    def wait(self, timeout):
        return 0


class RecorderTests(unittest.TestCase):
    def setUp(self):
        safe = Path(__file__).resolve().parents[3] / ".runtime-work"
        safe.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=safe)
        self.sensors = {name: Sensor() for name in CAMERAS}
        self.size_patch = patch.dict(SIZES, {name: (2, 2) for name in CAMERAS})
        self.size_patch.start()

    def tearDown(self):
        self.size_patch.stop()
        self.temp.cleanup()

    def test_four_original_streams_capture_encode_and_close(self):
        recorder = FourStreamRecorder(self.sensors, self.temp.name, encoder_factory=Encoder)
        for sensor in self.sensors.values():
            sensor.callback(NS(frame=7, width=2, height=2, raw_data=bytes(16)))
        images = recorder.capture(7)
        recorder.append(images)
        recorder.close()
        self.assertEqual(recorder.count, 1)
        self.assertTrue(all(sensor.stopped for sensor in self.sensors.values()))
        self.assertTrue(all("ffv1" in encoder.command for encoder in recorder.encoders.values()))

    def test_stale_camera_rejected_before_video_write(self):
        recorder = FourStreamRecorder(self.sensors, self.temp.name, encoder_factory=Encoder)
        for name, sensor in self.sensors.items():
            sensor.callback(NS(frame=6 if name == "overview" else 7,
                               width=2, height=2, raw_data=bytes(16)))
        with self.assertRaisesRegex(ValueError, "stale"):
            recorder.capture(7)
        self.assertEqual(recorder.count, 0)
        recorder.close()


if __name__ == "__main__":
    unittest.main()
