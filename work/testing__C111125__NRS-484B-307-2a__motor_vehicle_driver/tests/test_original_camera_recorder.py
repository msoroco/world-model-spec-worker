import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as N

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from delivery_audit import VIEWS, _decode, _probe
from original_camera_recorder import OriginalCameraRecorder


PROFILE = {view: (8, 4) for view in VIEWS}


class Sensor:
    def __init__(self):
        self.callback = None
        self.stopped = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True


class OriginalCameraRecorderTests(unittest.TestCase):
    def setUp(self):
        parent = REPO / '.runtime-work/c111125-camera-recorder-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scratch = self.root / 'scratch'; self.scratch.mkdir()
        self.output = self.root / 'output'; self.output.mkdir()
        self.sensors = {view: Sensor() for view in VIEWS}

    def emit(self, frame, *, broken_view=None, wrong_frame=False):
        for view, sensor in self.sensors.items():
            if view == broken_view:
                continue
            image = N(frame=frame + (1 if wrong_frame and view == 'approach' else 0),
                      width=8, height=4,
                      raw_data=bytes((frame, 20, 30, 255)) * 32)
            sensor.callback(image)

    def test_original_four_view_video_encoding_and_full_decode(self):
        recorder = OriginalCameraRecorder(self.sensors, self.scratch,
                                          profile=PROFILE, expected_frames=3,
                                          diagnostic_fixture=True)
        try:
            for frame in (1, 2, 3):
                self.emit(frame)
                self.assertEqual(recorder.read(N(frame=frame)), {v: frame for v in VIEWS})
            refs = recorder.finish(self.output)
            self.assertEqual(set(refs), set(VIEWS))
            for view in VIEWS:
                path = self.output / refs[view]['path']
                self.assertEqual(int(_probe(path)['nb_read_frames']), 3)
                _decode(path)
        finally:
            recorder.close()
        self.assertTrue(all(s.stopped for s in self.sensors.values()))

    def test_stale_or_missing_callback_fails_before_source_publication(self):
        for broken_view, wrong_frame in ((None, True), ('reference_corner', False)):
            with self.subTest(broken_view=broken_view, wrong_frame=wrong_frame):
                fresh = self.root / ('bad-' + str(broken_view) + str(wrong_frame))
                fresh.mkdir()
                sensors = {view: Sensor() for view in VIEWS}
                recorder = OriginalCameraRecorder(sensors, fresh, profile=PROFILE,
                                                  expected_frames=3, diagnostic_fixture=True,
                                                  timeout_s=.01)
                self.sensors = sensors
                self.emit(1, broken_view=broken_view, wrong_frame=wrong_frame)
                with self.assertRaisesRegex(ValueError, 'callback missing|frame or dimensions'):
                    recorder.read(N(frame=1))
                with self.assertRaisesRegex(ValueError, 'complete original'):
                    recorder.finish(self.output)
                recorder.close()
                self.assertFalse(list(self.output.iterdir()))


if __name__ == '__main__':
    unittest.main()
