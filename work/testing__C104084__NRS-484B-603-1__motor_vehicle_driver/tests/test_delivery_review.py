"""Production review receipt contract, independent of diagnostic capture fixtures."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from delivery_acceptance import validate_review


class NativeReviewTests(unittest.TestCase):
    def setUp(self):
        self.proof = {
            'source_sha256': {'motion': 'b' * 64, 'frame_map': 'c' * 64},
            'camera_decodes': {name: {'decoded_rgb24_sha256': char * 64}
                               for name, char in [('front', 'd'), ('left', 'e'),
                                                  ('right', 'f'), ('rear', '0')]},
            'crest_crossing': {'crossing_frame_id': 600, 'crossing_time_s': 25.0},
        }
        self.receipt = {
            'case_id': 'exact-case', 'provenance_kind': 'original_native_review',
            'diagnostic_fixture': False, 'reviewer': 'Independent observer',
            'source_binding': {
                'crest_manifest_sha256': 'a' * 64,
                'motion_sha256': 'b' * 64,
                'frame_map_sha256': 'c' * 64,
                'camera_rgb24_sha256': {'front': 'd' * 64, 'left': 'e' * 64,
                                        'right': 'f' * 64, 'rear': '0' * 64},
                'frame_count': 900, 'rate_hz': 20,
            },
            'physical_completion': {'status': 'met', 'crossing_frame_id': 600,
                                    'crossing_time_s': 25.0},
            'visibility_review': {
                'status': 'visible',
                'ego_body': {'camera': 'front', 'video_frame': 600,
                             'visible': True, 'observation': 'body in frame'},
                'opposing_body': {'camera': 'left', 'video_frame': 600,
                                  'visible': True, 'observation': 'body in frame'},
                'crest_approach': {'camera': 'front', 'video_frame': 500,
                                   'visible': True, 'observation': 'grade in frame'},
                'sight_line_observation': 'crest sight line reviewed',
            },
        }

    def validate(self, receipt):
        return validate_review('exact-case', 'a' * 64, self.proof, receipt)

    def test_original_review_passes(self):
        self.assertEqual(self.validate(self.receipt)['physical_completion'], 'met')

    def test_missing_review_fails(self):
        with self.assertRaisesRegex(ValueError, 'review case'):
            self.validate({})

    def test_tampered_source_binding_fails(self):
        receipt = copy.deepcopy(self.receipt)
        receipt['source_binding']['camera_rgb24_sha256']['front'] = '1' * 64
        with self.assertRaisesRegex(ValueError, 'source/time/pixels'):
            self.validate(receipt)

    def test_tampered_crossing_time_fails(self):
        receipt = copy.deepcopy(self.receipt)
        receipt['physical_completion']['crossing_time_s'] = 24.0
        with self.assertRaisesRegex(ValueError, 'crossing time'):
            self.validate(receipt)

    def test_invisible_subject_fails(self):
        receipt = copy.deepcopy(self.receipt)
        receipt['visibility_review']['opposing_body']['visible'] = False
        with self.assertRaisesRegex(ValueError, 'not visible'):
            self.validate(receipt)

    def test_unfinished_passage_fails(self):
        receipt = copy.deepcopy(self.receipt)
        receipt['physical_completion']['status'] = 'not_met'
        with self.assertRaisesRegex(ValueError, 'not met'):
            self.validate(receipt)

    def test_fixture_review_rejected_in_production(self):
        receipt = copy.deepcopy(self.receipt)
        receipt['provenance_kind'] = 'diagnostic_fixture_review'
        receipt['diagnostic_fixture'] = True
        with self.assertRaisesRegex(ValueError, 'original Native physical review'):
            self.validate(receipt)


if __name__ == '__main__':
    unittest.main()
