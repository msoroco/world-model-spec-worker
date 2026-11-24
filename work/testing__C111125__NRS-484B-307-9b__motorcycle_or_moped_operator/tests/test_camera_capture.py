import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from camera_capture import CameraCaptureError, FourViewRecorder, VIEWS
from media_decode import audit_manifest


class Adapter:
    def __init__(self):
        self.bad_frame = None
        self.bad_view = None

    def read_views(self, frame):
        return {name: {'source_kind': 'native_camera_sensor',
                       'frame': frame + (1 if name == self.bad_frame else 0),
                       'width': 16, 'height': 16,
                       'bgra': bytes((frame % 256, 30, 60, 255)) * 256}
                for name in VIEWS if name != self.bad_view}


class CameraCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.adapter = Adapter()

    def test_four_lossless_views_share_all_event_frames(self):
        recorder = FourViewRecorder(self.root, self.adapter, 'exact-case')
        for frame in range(900):
            recorder.record({'frame': frame})
        ref = recorder.finish()
        self.assertEqual(ref['sha256'], hashlib.sha256((self.root / ref['path']).read_bytes()).hexdigest())
        receipt = audit_manifest(self.root, ref, self.root / 'media-receipt.json')
        self.assertEqual(set(receipt['camera_views']), set(VIEWS))
        manifest = json.loads((self.root / ref['path']).read_text())
        for item in manifest['camera_views'].values():
            self.assertEqual((item['first_original_frame'], item['last_original_frame']), (0, 899))
        self.assertEqual(receipt['physical_visibility'], 'unreviewed')

    def test_rejects_frame_and_view_defects(self):
        recorder = FourViewRecorder(self.root, self.adapter, 'exact-case')
        self.adapter.bad_frame = 'approach'
        with self.assertRaisesRegex(CameraCaptureError, 'frame mismatch'):
            recorder.record({'frame': 1})
        recorder.abort()
        self.adapter.bad_frame = None
        self.adapter.bad_view = 'reference_corner'
        recorder = FourViewRecorder(self.root, self.adapter, 'exact-case')
        with self.assertRaisesRegex(CameraCaptureError, 'four original'):
            recorder.record({'frame': 1})
        recorder.abort()

    def test_incomplete_capture_refused(self):
        recorder = FourViewRecorder(self.root, self.adapter, 'exact-case')
        recorder.record({'frame': 10})
        with self.assertRaisesRegex(CameraCaptureError, 'incomplete'):
            recorder.finish()
        recorder.abort()


if __name__ == '__main__':
    unittest.main()
