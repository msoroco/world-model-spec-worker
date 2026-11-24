import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import original_pixel_audit as pixel


class OriginalPixelAuditTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        self.source = {name + '.mkv': 'a' * 64 for name in pixel.CAMERAS}
        self.saved = {'case_id': 'case', 'diagnostic_fixture': True,
                      'sources_sha256': self.source}
        self.media = {'case_id': 'case', 'diagnostic_fixture': True,
                      'expected_frames': 5,
                      'cameras': {name: {'width': 32, 'height': 32,
                                         'fully_decoded_frames': 5}
                                  for name in pixel.CAMERAS}}
        self.data = bytes([0, 1, 2]) * (8 * 8)
        self.packet = {'case_id': 'case', 'reviewer': 'independent CPU diagnostic',
                       'diagnostic_fixture': True, 'source_sha256': self.source,
                       'observations': [
                           {'camera': name, 'frame_index': 0,
                            'crop_xywh': [0, 0, 8, 8],
                            'rgb24_sha256': hashlib.sha256(self.data).hexdigest(),
                            'walker_body_visible': 'unknown'}
                           for name in pixel.CAMERAS]}
        self.review = self.root / 'review.json'
        self.save()

    def save(self):
        self.review.write_text(json.dumps(self.packet) + '\n')

    def check(self, diagnostic=True):
        with patch.object(pixel, 'read_attempt', return_value=self.saved):
            return pixel.audit(self.root, self.review, 'case', diagnostic=diagnostic,
                               media_auditor=lambda _: self.media,
                               crop_decoder=lambda *_: self.data)

    def test_diagnostic_does_not_pass_physical_delivery(self):
        result = self.check()
        self.assertEqual(result['status'], 'software_diagnostic_only')
        self.assertFalse(result['passed'])

    def test_wrong_original_source_hash_rejected(self):
        self.packet['source_sha256'] = {'overview.mkv': 'b' * 64}
        self.save()
        with self.assertRaisesRegex(ValueError, 'source binding'):
            self.check()

    def test_stale_pixel_or_frame_rejected(self):
        self.packet['observations'][0]['rgb24_sha256'] = 'b' * 64
        self.save()
        with self.assertRaisesRegex(ValueError, 'pixel hash'):
            self.check()
        self.packet['observations'][0]['rgb24_sha256'] = hashlib.sha256(self.data).hexdigest()
        self.packet['observations'][0]['frame_index'] = 5
        self.save()
        with self.assertRaisesRegex(ValueError, 'original frame'):
            self.check()

    def test_missing_camera_review_rejected(self):
        self.packet['observations'].pop()
        self.save()
        with self.assertRaisesRegex(ValueError, 'camera observations'):
            self.check()

    def test_fixture_cannot_claim_native_pixel_acceptance(self):
        with self.assertRaisesRegex(ValueError, 'physical original-pixel review required'):
            self.check(diagnostic=False)

    def native_check(self):
        self.saved['diagnostic_fixture'] = False
        self.media['diagnostic_fixture'] = False
        self.media['expected_frames'] = 400
        for camera in self.media['cameras'].values():
            camera['fully_decoded_frames'] = 400
        self.packet['diagnostic_fixture'] = False
        self.packet['actual_original_pixels'] = True
        self.packet['observations'][0]['walker_body_visible'] = True
        self.packet['observations'][2]['walker_body_visible'] = True
        self.packet['observations'][2]['frame_index'] = 399
        self.save()
        sources = {}
        for name in ('scene.json', 'reviewed-site-audit.json',
                     'native-crosswalk-readback.json', 'walker-body-history.jsonl'):
            path = self.root / name
            path.write_text('{}\n')
            sources[name] = pixel.sha(path)
        (self.root / 'capture-seal.json').write_text(json.dumps({
            'format': 'worker-sealed-capture', 'provenance_kind': 'native',
            'frames': 400, 'restoration': {'restored': True},
            'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
            'sources': sources}) + '\n')
        with patch.object(pixel, 'evaluate_crossing_completion',
                          return_value={'physical_checks': {'maneuver': {'status': 'met'}}}):
            return self.check(diagnostic=False)

    def test_native_source_lifecycle_and_review_join(self):
        result = self.native_check()
        self.assertEqual(result['status'], 'native_sources_reviewed')
        self.assertTrue(result['passed'])
        (self.root / 'native-crosswalk-readback.json').write_text('{"changed": true}\n')
        with self.assertRaisesRegex(ValueError, 'sealed original source differs'):
            self.native_check_after_tamper()

    def native_check_after_tamper(self):
        with patch.object(pixel, 'evaluate_crossing_completion',
                          return_value={'physical_checks': {'maneuver': {'status': 'met'}}}):
            return self.check(diagnostic=False)

    def test_native_missing_independent_visibility_rejected(self):
        self.native_check()
        self.packet['observations'][2]['walker_body_visible'] = 'unknown'
        self.save()
        with self.assertRaisesRegex(ValueError, 'walker pixel visibility missing'):
            self.native_check_after_tamper()


if __name__ == '__main__':
    unittest.main()
