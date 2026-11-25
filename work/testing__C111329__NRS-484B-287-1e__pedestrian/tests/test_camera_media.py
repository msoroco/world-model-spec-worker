import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from camera_media import FourCameraRecorder, audit_original_media
from saved_crossing import CAMERAS


class CameraMediaTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / '.runtime-work/c111329-camera-media-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.attempt = Path(self.temp.name)
        self.profile = {name: (2, 2) for name in CAMERAS}

    def _images(self, frame):
        return {name: SimpleNamespace(frame=frame, width=2, height=2,
                                      raw_data=bytes((frame * 37 % 255, 20, 30, 255)) * 4)
                for name in CAMERAS}

    def test_all_original_video_frames_are_decoded(self):
        recorder = FourCameraRecorder(self.attempt, self.profile, diagnostic=True)
        for frame in range(1, 5):
            recorder.append(frame, self._images(frame))
        recorder.close()
        sources = recorder.source_receipt()
        audit = audit_original_media(self.attempt, sources, 4,
                                     profile=self.profile, diagnostic=True)
        self.assertEqual(set(audit['cameras']), set(CAMERAS))
        self.assertTrue(all(row['frames'] == 4 for row in audit['cameras'].values()))
        self.assertEqual(audit['physical_visibility'], 'unverified')
        with self.assertRaisesRegex(ValueError, 'hash/count mismatch'):
            audit_original_media(self.attempt, sources, 3,
                                 profile=self.profile, diagnostic=True)
        sources['overview']['sha256'] = hashlib.sha256(b'stale').hexdigest()
        with self.assertRaisesRegex(ValueError, 'hash/count mismatch'):
            audit_original_media(self.attempt, sources, 4,
                                 profile=self.profile, diagnostic=True)

    def test_stale_image_rejected_before_tick_write(self):
        recorder = FourCameraRecorder(self.attempt, self.profile, diagnostic=True)
        images = self._images(1)
        images['reference_corner'].frame = 0
        with self.assertRaisesRegex(ValueError, 'original BGRA frame'):
            recorder.append(1, images)
        self.assertEqual(recorder.count, 0)
        recorder.close()

    def test_production_rejects_small_camera_profile(self):
        with self.assertRaisesRegex(ValueError, 'pinned camera dimensions'):
            FourCameraRecorder(self.attempt, self.profile, diagnostic=False)


if __name__ == '__main__':
    unittest.main()
