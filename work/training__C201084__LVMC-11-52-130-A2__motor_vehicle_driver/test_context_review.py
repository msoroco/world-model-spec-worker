"""Exercise retained source review bindings without original claims."""
import json
import tempfile
import unittest
from pathlib import Path

from context_review import build
from source_measurement import sha


ROOT = Path(__file__).resolve().parent
ATTEMPT = Path('.runtime-work/c201084-reference-current-primary-compatibility')
EVENT = ROOT / 'current-reference-event-evidence.json'
CASE = ROOT.name + '__reference'


class ContextReviewTest(unittest.TestCase):
    def _review(self):
        frames = [json.loads(line) for line in
                  (ATTEMPT / 'video_frames.jsonl').read_text().splitlines()]
        return {'format': 'c201084-context-source-review-v1',
                'case_id': CASE, 'reviewer': 'diagnostic-fixture-reviewer',
                'review_kind': 'synthetic_annotation',
                'property': {'status': 'private',
                             'basis': 'authored diagnostic survey only',
                             'source': {
                                 'path': 'native-survey-readback.json',
                                 'sha256': sha(ATTEMPT / 'native-survey-readback.json')}},
                'attendance': {'state': 'attended',
                               'basis': 'synthetic video interval annotation',
                               'reviewed_intervals': [{
                                   'camera': 'driver_reference',
                                   'video_sha256': sha(ATTEMPT / 'driver_reference.mkv'),
                                   'first_video_frame': 2,
                                   'last_video_frame': 599,
                                   'first_carla_frame': frames[2]['carla_frame'],
                                   'last_carla_frame': frames[599]['carla_frame'],
                                   'continuous_review': True}]}}

    def _run(self, review):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'review.json'
            path.write_text(json.dumps(review) + '\n')
            return build(ATTEMPT, EVENT, path)

    def test_pending_context_binds_four_cameras(self):
        result = build(ATTEMPT, EVENT)
        self.assertEqual(len(result['camera_source_sha256']), 4)
        self.assertIsNone(result['property_and_attendance_review'])
        self.assertFalse(result['original_context_review_bound'])

    def test_synthetic_review_cannot_be_original(self):
        result = self._run(self._review())
        self.assertTrue(result['property_and_attendance_review']
                        ['continuous_attendance_review_covers_near_zero_events'])
        self.assertFalse(result['original_context_review_bound'])
        self.assertFalse(result['property_legally_verified'])
        review = self._review()
        review['review_kind'] = 'original_source_review'
        with self.assertRaisesRegex(ValueError, 'provenance differs'):
            self._run(review)

    def test_rejects_unbound_property_and_incomplete_attendance(self):
        review = self._review()
        review['property']['source']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Property source file or hash differs'):
            self._run(review)
        review = self._review()
        interval = review['attendance']['reviewed_intervals'][0]
        interval['first_video_frame'] = 3
        interval['first_carla_frame'] += 1
        with self.assertRaisesRegex(ValueError, 'does not cover'):
            self._run(review)


if __name__ == '__main__':
    unittest.main()
