import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import media_decode


class MediaDecodeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'camera.mkv'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'color=c=blue:s=32x24:r=20', '-frames:v', '40',
                        '-c:v', 'ffv1', str(self.path)], check=True)
        self.ref = {'path': self.path.name,
                    'sha256': hashlib.sha256(self.path.read_bytes()).hexdigest()}

    def test_full_decode_and_source_seal(self):
        receipt = media_decode.decode_view(self.root, self.ref, 40, 32, 24)
        self.assertEqual(receipt['full_decode_exit_code'], 0)
        self.assertEqual(receipt['physical_visibility'], 'unreviewed')

    def test_rejects_count_hash_and_corrupt_media(self):
        with self.assertRaisesRegex(media_decode.MediaError, 'frame count'):
            media_decode.decode_view(self.root, self.ref, 41, 32, 24)
        with self.assertRaisesRegex(media_decode.MediaError, 'hash mismatch'):
            media_decode.decode_view(self.root, dict(self.ref, sha256='0' * 64), 40, 32, 24)
        self.path.write_bytes(b'not video')
        ref = {'path': self.path.name,
               'sha256': hashlib.sha256(self.path.read_bytes()).hexdigest()}
        with self.assertRaisesRegex(media_decode.MediaError, 'ffprobe rejected'):
            media_decode.decode_view(self.root, ref, 40, 32, 24)

    def test_four_view_inventory(self):
        item = {'source': self.ref, 'width': 32, 'height': 24}
        views = {name: item for name in ('overview', 'approach', 'reference_corner',
                                         'driver_reference')}
        with self.assertRaisesRegex(media_decode.MediaError, 'distinct'):
            media_decode.audit_four_views(self.root, views, 40)
        with self.assertRaisesRegex(media_decode.MediaError, 'four-view'):
            media_decode.audit_four_views(self.root, {'overview': item}, 40)

    def test_saved_manifest_receipt_is_case_bound(self):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'color=c=blue:s=32x24:r=20', '-frames:v', '900',
                        '-c:v', 'ffv1', str(self.path)], check=True)
        ref = {'path': self.path.name,
               'sha256': hashlib.sha256(self.path.read_bytes()).hexdigest()}
        item = {'source': ref, 'width': 32, 'height': 24}
        views = {}
        for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            target = self.root / (name + '.mkv')
            target.write_bytes(self.path.read_bytes())
            views[name] = {'source': {'path': target.name,
                                      'sha256': hashlib.sha256(target.read_bytes()).hexdigest()},
                           'width': 32, 'height': 24}
        manifest = {'case_id': 'exact-case', 'fps': 20, 'duration_frames': 900,
                    'camera_views': views}
        path = self.root / 'media-manifest.json'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        manifest_ref = {'path': path.name,
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        receipt = media_decode.audit_manifest(self.root, manifest_ref,
                                              self.root / 'media-receipt.json')
        self.assertEqual(receipt['case_id'], 'exact-case')
        self.assertEqual(len(receipt['camera_views']), 4)
        self.assertEqual(receipt['physical_visibility'], 'unreviewed')
        with self.assertRaisesRegex(media_decode.MediaError, 'manifest hash'):
            media_decode.audit_manifest(self.root, dict(manifest_ref, sha256='0' * 64),
                                        self.root / 'bad.json')
        manifest['duration_frames'] = 901
        path.write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaisesRegex(media_decode.MediaError, '45 second'):
            media_decode.audit_manifest(self.root,
                                        {'path': path.name,
                                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest()},
                                        self.root / 'bad-duration.json')
