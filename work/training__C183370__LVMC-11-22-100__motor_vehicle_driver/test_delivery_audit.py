"""CPU checks for the independent physical review provenance gate."""
import unittest

import delivery_audit


class PhysicalReviewBindingTests(unittest.TestCase):
    def setUp(self):
        self.reviewed = {'analysis_sha256': 'a' * 64,
                         'annotations_sha256': 'b' * 64,
                         'reviewer_id': 'source reviewer'}
        self.sources = {'overview.mkv': 'c' * 64}
        self.review = {
            'format': 'c183370-independent-physical-review-v1',
            'passed': True,
            'case_id': 'selected-case',
            'candidate_id': 'primary',
            'manifest_sha256': 'd' * 64,
            'processing_sha256': 'e' * 64,
            'source_analysis_sha256': 'a' * 64,
            'source_annotations_sha256': 'b' * 64,
            'original_source_sha256': self.sources,
            'checks': {name: True for name in delivery_audit.CHECKS},
            'reviewer_id': 'independent physical reviewer',
            'legal_verdict_claimed': False,
        }
        self.kwargs = dict(case='selected-case', candidate='primary',
                           manifest_sha256='d' * 64,
                           processing_sha256='e' * 64,
                           reviewed=self.reviewed,
                           source_hashes=self.sources)

    def test_exact_independent_review_passes(self):
        delivery_audit.validate_physical_review(self.review, **self.kwargs)

    def test_stale_processing_is_rejected(self):
        self.review['processing_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'bindings or checks incomplete'):
            delivery_audit.validate_physical_review(self.review, **self.kwargs)

    def test_self_review_is_rejected(self):
        self.review['reviewer_id'] = 'source reviewer'
        with self.assertRaisesRegex(ValueError, 'bindings or checks incomplete'):
            delivery_audit.validate_physical_review(self.review, **self.kwargs)

    def test_missing_pixel_check_is_rejected(self):
        self.review['checks']['actual_pixels'] = False
        with self.assertRaisesRegex(ValueError, 'bindings or checks incomplete'):
            delivery_audit.validate_physical_review(self.review, **self.kwargs)

    def test_legal_verdict_is_rejected(self):
        self.review['legal_verdict_claimed'] = True
        with self.assertRaisesRegex(ValueError, 'bindings or checks incomplete'):
            delivery_audit.validate_physical_review(self.review, **self.kwargs)


if __name__ == '__main__':
    unittest.main()
