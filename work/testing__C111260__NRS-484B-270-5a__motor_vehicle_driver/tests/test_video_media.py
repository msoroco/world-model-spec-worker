import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

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
        video = self.root / 'overview.mkv'
        video.write_bytes(video.read_bytes() + b'tampered')
        with self.assertRaisesRegex(ValueError, 'source hash drift'):
            VIDEO.audit_composed(self.root, ref)

    def test_unsealed_archive_rejected_before_encode(self):
        archive = self.root / 'overview.png.zip'
        archive.write_bytes(archive.read_bytes() + b'tampered')
        with self.assertRaisesRegex(ValueError, 'hash drift'):
            VIDEO.compose(self.root, profile=self.profile, diagnostic_fixture=True)
        self.assertFalse((self.root / 'video-media.json').exists())

    def test_independent_pixel_review_binds_original_frames_and_roles(self):
        ref = VIDEO.compose(self.root, profile=self.profile, diagnostic_fixture=True)
        packet_hash = hashlib.sha256((self.root / 'encounter-packet.json').read_bytes()).hexdigest()
        views = {}
        for camera in CAPTURE.CAMERAS:
            with ZipFile(self.root / (camera + '.png.zip')) as archive:
                original_sha = hashlib.sha256(archive.read('00000100.png')).hexdigest()
            views[camera] = [{'frame': 100, 'original_png_sha256': original_sha,
                              'ego_visible': True, 'rider_visible': True,
                              'person_mounted_visible': True,
                              'rider_kind_visible': 'bicycle'}]
        original_views = json.loads(json.dumps(views))
        review = {'format': 'c111260-independent-pixel-review-v1',
                  'case_id': CASE, 'packet_sha256': packet_hash,
                  'video_manifest_sha256': ref['sha256'],
                  'original_frames': 900, 'views': views}
        review_path = self.root.parent / 'independent-pixel-review.json'
        review_path.write_text(json.dumps(review), encoding='utf-8')
        review_hash = hashlib.sha256(review_path.read_bytes()).hexdigest()
        kwargs = {'case_id': CASE, 'packet_sha256': packet_hash,
                  'video_manifest_sha256': ref['sha256'],
                  'pixel_review_path': review_path,
                  'pixel_review_sha256': review_hash}
        self.assertTrue(AUDIT.audit_saved(self.root, **kwargs)['actual_pixels'])
        review['views']['overview'][0]['person_mounted_visible'] = False
        review_path.write_text(json.dumps(review), encoding='utf-8')
        kwargs['pixel_review_sha256'] = hashlib.sha256(review_path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'role or source differs'):
            AUDIT.audit_saved(self.root, **kwargs)
        review['views'].pop('approach')
        review_path.write_text(json.dumps(review), encoding='utf-8')
        kwargs['pixel_review_sha256'] = hashlib.sha256(review_path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'omits a camera'):
            AUDIT.audit_saved(self.root, **kwargs)
        review['views'] = original_views
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi',
                        '-i', 'color=c=red:s=2x2:r=20', '-frames:v', '900',
                        '-c:v', 'ffv1', str(self.root / 'overview.mkv')], check=True)
        manifest_path = self.root / 'video-media.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['camera_videos']['overview']['sha256'] = hashlib.sha256(
            (self.root / 'overview.mkv').read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        kwargs['video_manifest_sha256'] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        review['video_manifest_sha256'] = kwargs['video_manifest_sha256']
        review_path.write_text(json.dumps(review), encoding='utf-8')
        kwargs['pixel_review_sha256'] = hashlib.sha256(review_path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'encoded pixels differ'):
            AUDIT.audit_saved(self.root, **kwargs)


if __name__ == '__main__':
    unittest.main()
