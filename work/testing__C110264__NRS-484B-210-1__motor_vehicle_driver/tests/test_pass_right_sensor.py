"""CPU fake-world tests of actual Native sensor callback wiring."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pass_right_media import audit_cameras
from pass_right_sensor import capture_native_attempt
from test_pass_right_capture import FakeFrameMap, road, rows


class FakeImage:
    width = 8
    height = 4

    def __init__(self, frame):
        self.frame = frame
        self.raw_data = bytes((frame % 256, 20, 40, 255)) * 32


class FakeSensor:
    def __init__(self):
        self.callback = None

    def listen(self, callback):
        self.callback = callback


class FakeSnapshot:
    def __init__(self, frame, elapsed):
        self.frame = frame
        self.timestamp = type('Timestamp', (), {'elapsed_seconds': elapsed})()


class FakeWorld:
    def __init__(self, sensors, broken=None):
        self.sensors = sensors
        self.broken = broken
        self.index = -1

    def tick(self):
        self.index += 1
        frame = 1420 + self.index
        for name, sensor in self.sensors.items():
            if self.broken == (name, self.index, 'missing'):
                continue
            image_frame = frame + (1 if self.broken == (name, self.index, 'stale') else 0)
            sensor.callback(FakeImage(image_frame))
        return frame

    def get_settings(self):
        return type('Settings', (), {'synchronous_mode': True,
                                     'fixed_delta_seconds': 0.05})()

    def get_snapshot(self):
        return FakeSnapshot(1420 + self.index, 72.5 + self.index / 20)


class TestNativeSensorCapture(unittest.TestCase):
    def capture(self, root, broken=None):
        sensors = {name: FakeSensor() for name in ('front', 'rear', 'left', 'right')}
        world = FakeWorld(sensors, broken)
        originals = rows(count=8)
        frame_map = FakeFrameMap()
        result = capture_native_attempt(
            world, sensors, lambda snapshot: originals[world.index], road(),
            10, 11, frame_map, root, frame_count=8, timeout_s=0.01,
            diagnostic_profile={name: (8, 4) for name in sensors})
        return result, frame_map

    def test_callbacks_join_and_full_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, frame_map = self.capture(root)
            self.assertEqual(len(result['trace']['frames']), 8)
            self.assertEqual(len(frame_map.calls), 8)
            decoded = audit_cameras(root, result['cameras'],
                                    {name: (8, 4) for name in result['cameras']}, 8)
            self.assertEqual(decoded['front']['frame_count'], 8)
            self.assertTrue(result['diagnostic_profile'])
            self.assertFalse(result['physical_acceptance_claimed'])

    def test_missing_callback_discards_partial_archives(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, 'callback missing'):
                self.capture(root, ('right', 3, 'missing'))
            self.assertEqual(list(root.glob('*.zip')), [])

    def test_wrong_callback_frame_discards_archives(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, 'frame mismatch'):
                self.capture(root, ('front', 2, 'stale'))
            self.assertEqual(list(root.glob('*.zip')), [])

    def test_requires_all_sensor_channels(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'all four'):
                capture_native_attempt(FakeWorld({}), {}, lambda s: {}, road(),
                                       10, 11, FakeFrameMap(), Path(tmp), frame_count=8)

    def test_controller_precedes_every_tick_and_wrong_clock_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            sensors = {name: FakeSensor() for name in ('front', 'rear', 'left', 'right')}
            world = FakeWorld(sensors)
            originals = rows(count=8)
            calls = []
            capture_native_attempt(
                world, sensors, lambda snapshot: originals[world.index], road(),
                10, 11, FakeFrameMap(), Path(tmp), frame_count=8,
                diagnostic_profile={name: (8, 4) for name in sensors},
                before_tick=lambda index: calls.append((index, world.index)))
            self.assertEqual(calls, [(i, i - 1) for i in range(8)])
        with tempfile.TemporaryDirectory() as tmp:
            world.get_settings = lambda: type('Settings', (), {
                'synchronous_mode': True, 'fixed_delta_seconds': 0.1})()
            with self.assertRaisesRegex(ValueError, 'synchronous 20 Hz'):
                capture_native_attempt(world, sensors, lambda snapshot: {}, road(),
                                       10, 11, FakeFrameMap(), Path(tmp), frame_count=8)


if __name__ == '__main__':
    unittest.main()
