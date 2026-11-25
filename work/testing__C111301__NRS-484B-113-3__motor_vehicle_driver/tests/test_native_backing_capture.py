"""Capture-side same-tick source rows for original backing attempts."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[1] / '.runtime-work'
sys.path.insert(0, str(ROOT))
from native_backing_capture import NativeBackingRecorder
from test_saved_backing import fixture


class Actor:
    def __init__(self, actor_id, x, y, reverse=False):
        self.id, self.x, self.y, self.reverse = actor_id, x, y, reverse

    def get_transform(self):
        loc = SimpleNamespace(x=self.x, y=self.y)
        return SimpleNamespace(location=loc,
                               get_forward_vector=lambda: SimpleNamespace(x=1, y=0))

    def get_velocity(self):
        return SimpleNamespace(x=-.2 if self.reverse else 0,
                               y=0 if self.reverse else .2)

    def get_control(self):
        return SimpleNamespace(brake=1.0, reverse=self.reverse)


class NativeBackingCaptureTests(unittest.TestCase):
    def setup_recorder(self, root):
        fixture(root)
        packet = json.loads((root / 'map.json').read_text())
        return NativeBackingRecorder(packet, Actor(7, 5, 0, True), Actor(8, 2, 0))

    def images(self, frame, time_s=None):
        if time_s is None:
            time_s = (frame - 1000) * .05
        return {name: SimpleNamespace(frame=frame, timestamp=time_s)
                for name in ('overview', 'approach', 'reference_corner', 'driver_reference')}

    def test_complete_original_source_rows(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            root = Path(temp)
            recorder = self.setup_recorder(root)
            source_root = root / 'native-source'
            source_root.mkdir()
            with self.assertRaisesRegex(ValueError, '900-frame'):
                recorder.write(source_root)
            for index in range(900):
                recorder.append(1000 + index, index * .05, self.images(1000 + index))
            receipt = recorder.write(source_root)
            self.assertEqual(receipt['frame_count'], 900)
            rows = json.loads((source_root / 'telemetry.json').read_text())
            frames = json.loads((source_root / 'frame-map.json').read_text())
            self.assertEqual(len(rows), 900)
            self.assertEqual(rows[-1]['native_world_frame'], frames[-1]['world_frame'])
            self.assertTrue(rows[0]['pedestrian_in_corridor'])
            with self.assertRaisesRegex(ValueError, 'fresh'):
                recorder.write(source_root)

    def test_rejects_camera_and_time_mismatch_without_row(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            recorder = self.setup_recorder(Path(temp))
            images = self.images(1000)
            images['approach'] = SimpleNamespace(frame=999)
            with self.assertRaisesRegex(ValueError, 'camera and world'):
                recorder.append(1000, 0, images)
            with self.assertRaisesRegex(ValueError, '20 Hz'):
                recorder.append(1000, .5, self.images(1000))
            self.assertEqual(recorder.rows, [])
            recorder.append(1000, 0, self.images(1000))
            with self.assertRaisesRegex(ValueError, 'must be consecutive'):
                recorder.append(1000, .05, self.images(1000))
            with self.assertRaisesRegex(ValueError, 'must be consecutive'):
                recorder.append(1002, .05, self.images(1002))
            self.assertEqual(len(recorder.rows), 1)

    def test_rejects_camera_timestamp_drift(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            recorder = self.setup_recorder(Path(temp))
            images = self.images(1000)
            images['overview'].timestamp = .5
            with self.assertRaisesRegex(ValueError, 'camera timestamp and world tick differ'):
                recorder.append(1000, 0, images)
            self.assertEqual(recorder.rows, [])


if __name__ == '__main__':
    unittest.main()
