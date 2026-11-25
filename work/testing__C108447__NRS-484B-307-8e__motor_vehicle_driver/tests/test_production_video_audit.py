"""Production audit binds original pixels to canonical videos and review."""
import json
import subprocess
import unittest
from pathlib import Path

from test_prepare_delivery import PrepareDeliveryTests, delivery, preparer, sha


class ProductionVideoAuditTests(unittest.TestCase):
    def setUp(self):
        fixture = PrepareDeliveryTests()
        fixture.setUp()
        self.addCleanup(fixture.temp.cleanup)
        self.fixture = fixture
        self.root = fixture.root
        self.attempt = self.root / 'original-attempt'
        fixture.attempt.rename(self.attempt)
        fixture.attempt = self.attempt
        preparer.prepare(self.attempt, fixture.packet_path, fixture.case, 'lot', expected_frames=20)
        rows = [json.loads(line) for line in (self.attempt / 'frame-map.jsonl').read_text().splitlines()]
        mapping = [{'video_frame': i, 'native_frame': row['frame'],
                    'carla_frame': row['frame'], 'time_s': row['time_s']}
                   for i, row in enumerate(rows)]
        (self.root / 'video_frames.jsonl').write_text(''.join(
            json.dumps(row) + '\n' for row in mapping))
        sources = {
            'original-attempt/delivery-bundle.json': sha(self.attempt / 'delivery-bundle.json'),
            'video_frames.jsonl': sha(self.root / 'video_frames.jsonl')}
        videos = {}
        for camera in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            video = self.root / (camera + '.mkv')
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                            'color=c=blue:s=2x2:r=20:d=1', '-frames:v', '20',
                            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video)],
                           check=True, capture_output=True)
            videos[camera] = sha(video)
            sources[video.name] = videos[camera]
        seal = {'format': 'worker-sealed-capture', 'provenance_kind': 'native',
                'diagnostic_fixture': False, 'frames': 20,
                'restoration': {'owner_release_readback': {'readback_passed': True}},
                'sources': sources}
        (self.root / 'capture-seal.json').write_text(json.dumps(seal) + '\n')
        self.review = self.root / 'pixel-review.json'
        self.review_data = {
            'format': 'original-pixel-review-v1', 'decision': 'reviewed',
            'case_id': fixture.case, 'frame_count': 20,
            'bundle_sha256': sha(self.attempt / 'delivery-bundle.json'),
            'capture_seal_sha256': sha(self.root / 'capture-seal.json'),
            'video_sha256': videos, 'reviewer': 'fixture reviewer',
            'source_record_id': 'fixture-only', 'reviewed_at': 'fixture time',
            'reviewed_views': {camera: {'visible_subjects': ['fixture subject'],
                                       'frame_range': [0, 19],
                                       'reviewer_note': 'fixture only'}
                               for camera in videos}}
        self.review.write_text(json.dumps(self.review_data) + '\n')

    def production(self):
        return delivery.audit_production(self.root, self.attempt,
                                         self.attempt / 'delivery-bundle.json',
                                         self.review, expected_frames=20)

    def test_full_video_decode_and_review_binding(self):
        result = self.production()
        self.assertTrue(result['canonical_full_video_decode'])
        self.assertEqual(result['canonical_video_sha256'], self.review_data['video_sha256'])
        self.assertFalse(result['physical_acceptance_claimed'])

    def test_tampered_video_rejected(self):
        with (self.root / 'overview.mkv').open('ab') as stream:
            stream.write(b'tamper')
        with self.assertRaisesRegex(ValueError, 'encoded video seal differs'):
            self.production()

    def test_missing_or_stale_pixel_review_rejected(self):
        self.review.unlink()
        with self.assertRaisesRegex(ValueError, 'pixel review receipt required'):
            self.production()
        self.review_data['capture_seal_sha256'] = '0' * 64
        self.review.write_text(json.dumps(self.review_data) + '\n')
        with self.assertRaisesRegex(ValueError, 'reviewed original pixels'):
            self.production()


if __name__ == '__main__':
    unittest.main()
