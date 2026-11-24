import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_media import NativeMedia

CAMERAS = ('front', 'front_left', 'front_right', 'rear')


class FakeSensor:
    def __init__(self):
        self.callback = None
        self.stopped = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True

    def emit(self, frame, width=2):
        self.callback(SimpleNamespace(frame=frame, width=width, height=1,
                                      raw_data=bytes([0, 0, 0, 255] * width)))


class NativeMediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.attempt = Path(self.temp.name) / 'attempt'
        self.sensors = {name: FakeSensor() for name in CAMERAS}
        self.dimensions = {name: (2, 1) for name in CAMERAS}

    def start(self):
        media = NativeMedia(self.sensors, self.attempt, diagnostic_fixture=True,
                            dimensions=self.dimensions, timeout_s=0.1)
        self.addCleanup(media.abort)
        return media

    def test_original_frames_stream_to_four_lossless_writers(self):
        media = self.start()
        for frame in (101, 102):
            for sensor in self.sensors.values():
                sensor.emit(frame)
            self.assertEqual(media.read(frame), dict.fromkeys(CAMERAS, frame))
        self.assertEqual(len(media.frames), 2)
        with self.assertRaisesRegex(ValueError, '900 original'):
            media.finish()
        media.abort()
        self.assertTrue(all(sensor.stopped for sensor in self.sensors.values()))

    def test_missing_or_misaligned_camera_rejected(self):
        media = self.start()
        for sensor in self.sensors.values():
            sensor.emit(101)
        self.sensors['rear'].callback(SimpleNamespace(frame=102, width=2,
                              height=1, raw_data=bytes([0, 0, 0, 255] * 2)))
        # The first complete frame is valid; the queued duplicate is rejected.
        media.read(101)
        with self.assertRaisesRegex(ValueError, 'front original Native frame missing'):
            media.read(102)

    def test_bad_dimensions_and_profile_override_rejected(self):
        with self.assertRaisesRegex(ValueError, 'cannot be overridden'):
            NativeMedia(self.sensors, self.attempt, dimensions=self.dimensions)
        media = self.start()
        for sensor in self.sensors.values():
            sensor.emit(101)
        self.sensors['front'].callback(SimpleNamespace(frame=102, width=3,
                              height=1, raw_data=bytes([0, 0, 0, 255] * 3)))
        media.read(101)
        for name in ('front_left', 'front_right', 'rear'):
            self.sensors[name].emit(102)
        with self.assertRaisesRegex(ValueError, 'front original Native frame or dimensions differ'):
            media.read(102)


if __name__ == '__main__':
    unittest.main()
