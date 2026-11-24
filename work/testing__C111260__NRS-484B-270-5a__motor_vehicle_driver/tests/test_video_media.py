import hashlib
import importlib.util
import pathlib
import sys
import tempfile
import unittest

from test_native_capture import CAPTURE, CASE, SITE, callbacks

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location('video_media', ROOT / 'video_media.py')
VIDEO = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VIDEO)
AUDIT_SPEC = importlib.util.spec_from_file_location('delivery_audit', ROOT / 'delivery_audit.py')
AUDIT = importlib.util.module_from_spec(AUDIT_SPEC)
AUDIT_SPEC.loader.exec_module(AUDIT)


class ComposedVideoTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / '.runtime-work/c111260-video-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        tick, sample, camera_png = callbacks()
        CAPTURE.capture_attempt(self.root, case_id=CASE, site=SITE,
                                tick=tick, sample=sample, camera_png=camera_png)
        self.profile = {name: (2, 2) for name in CAPTURE.CAMERAS}

    def test_original_archives_compose_four_lossless_videos_and_decode(self):
        ref = VIDEO.compose(self.root, profile=self.profile, diagnostic_fixture=True)
        receipt = VIDEO.audit_composed(self.root, ref)
        self.assertTrue(receipt['full_video_decode'])
        self.assertEqual(receipt['original_frames'], 900)
        self.assertEqual(receipt['physical_review'], 'pending')
        packet_hash = hashlib.sha256((self.root / 'encounter-packet.json').read_bytes()).hexdigest()
        independent = AUDIT.audit_saved(self.root, case_id=CASE,
                                        packet_sha256=packet_hash,
                                        video_manifest_sha256=ref['sha256'])
        self.assertTrue(independent['full_video_decode'])
        self.assertFalse(independent['actual_pixels'])

    def test_changed_video_bytes_rejected(self):
        ref = VIDEO.compose(self.root, profile=self.profile, diagnostic_fixture=True)
        video = self.root / 'front.mkv'
        video.write_bytes(video.read_bytes() + b'tampered')
        with self.assertRaisesRegex(ValueError, 'source hash drift'):
            VIDEO.audit_composed(self.root, ref)

    def test_unsealed_archive_rejected_before_encode(self):
        archive = self.root / 'front.png.zip'
        archive.write_bytes(archive.read_bytes() + b'tampered')
        with self.assertRaisesRegex(ValueError, 'hash drift'):
            VIDEO.compose(self.root, profile=self.profile, diagnostic_fixture=True)
        self.assertFalse((self.root / 'video-media.json').exists())


if __name__ == '__main__':
    unittest.main()
