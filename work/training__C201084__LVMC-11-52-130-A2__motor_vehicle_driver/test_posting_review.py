"""Check frame-exact posting review binding and conservative claims."""
import json
import tempfile
import unittest
from pathlib import Path

from posting_review import build, decoded_frame_sha
from source_measurement import sha


ROOT = Path(__file__).resolve().parent
ATTEMPT = Path('.runtime-work/c201084-reference-current-primary-compatibility')
EVENT = ROOT / 'current-reference-event-evidence.json'


class PostingReviewTest(unittest.TestCase):
    def _review(self):
        frame = json.loads((ATTEMPT / 'video_frames.jsonl').read_text().splitlines()[2])
        video = ATTEMPT / 'reference_corner.mkv'
        return {'format': 'c201084-posting-source-review-v1',
                'case_id': ROOT.name + '__reference',
                'reviewer': 'diagnostic-fixture-reviewer',
                'review_kind': 'synthetic_annotation',
                'designation_document': {
                    'description': 'Synthetic survey, not a Fire Code designation',
                    'source': {'path': 'native-survey-readback.json',
                               'sha256': sha(ATTEMPT / 'native-survey-readback.json')}},
                'sign_observations': [{
                    'camera': 'reference_corner',
                    'video_frame': 2,
                    'carla_frame': frame['carla_frame'],
                    'video_sha256': sha(video),
                    'decoded_frame_sha256': decoded_frame_sha(video, 2),
                    'roi_xywh': [0, 0, 16, 16],
                    'review_note': 'Synthetic image anchor only; sign text unverified'}]}

    def _run(self, review):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'review.json'
            path.write_text(json.dumps(review) + '\n')
            return build(ATTEMPT, EVENT, path)

    def test_pending_binds_four_cameras(self):
        binding = build(ATTEMPT, EVENT)
        self.assertEqual(len(binding['camera_source_sha256']), 4)
        self.assertIsNone(binding['posting_review'])
        self.assertFalse(binding['original_posting_review_bound'])

    def test_synthetic_observation_never_verifies_posting(self):
        binding = self._run(self._review())
        self.assertEqual(len(binding['posting_review']['sign_observations']), 1)
        self.assertFalse(binding['original_posting_review_bound'])
        self.assertFalse(binding['fire_code_designation_verified'])
        review = self._review()
        review['review_kind'] = 'original_source_review'
        with self.assertRaisesRegex(ValueError, 'provenance differs'):
            self._run(review)

    def test_rejects_wrong_document_or_image(self):
        review = self._review()
        review['designation_document']['source']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'document source differs'):
            self._run(review)
        review = self._review()
        review['sign_observations'][0]['decoded_frame_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'decoded frame differs'):
            self._run(review)


if __name__ == '__main__':
    unittest.main()
