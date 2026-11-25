import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path.cwd() / '.runtime-work'
SCRATCH.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))
from production_comparison_audit import audit_comparison


class ProductionComparisonAuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.paths = []
        for side in ('left', 'right'):
            attempt = self.base / side
            attempt.mkdir()
            processing = self.base / f'{side}-processing.json'
            review = self.base / f'{side}-pixel-review.json'
            processing.write_text('{}\n')
            review.write_text('{}\n')
            self.paths.extend((attempt, processing, review))
        self.manifests = ({'case_id': 'case-left'}, {'case_id': 'case-right'})
        self.calls = []

    def delivery(self, attempt, processing, review):
        self.calls.append((attempt, processing, review))
        case = 'case-left' if attempt == self.paths[0] else 'case-right'
        return {'case_id': case, 'passed': True, 'source_integrity': True,
                'saved_only_processing': True, 'actual_pixels_reviewed': True,
                'physical_case_completion': True, 'all_participants': True,
                'time_join': True, 'full_video_decode': True}

    def pair(self, left, right, comparison_id, *, attempt_roots):
        self.assertEqual(len(self.calls), 2)
        return {'case_ids': [left['case_id'], right['case_id']],
                'source_integrity': True, 'physical_case_completion': True}

    def run_audit(self, delivery=None):
        return audit_comparison('activity_direction', *self.manifests,
                                self.paths[0], self.paths[3],
                                self.paths[1], self.paths[4],
                                self.paths[2], self.paths[5],
                                delivery_check=delivery or self.delivery,
                                pair_check=self.pair)

    def test_requires_both_independent_delivery_audits(self):
        receipt = self.run_audit()
        self.assertTrue(receipt['passed'])
        self.assertEqual(len(receipt['independent_delivery_audits']), 2)
        self.assertEqual(receipt['legal_conclusion'], 'unresolved')

    def test_rejects_missing_right_pixel_review_before_pair(self):
        self.paths[-1].unlink()
        with self.assertRaisesRegex(ValueError, 'missing pixel review'):
            self.run_audit()
        self.assertEqual(len(self.calls), 1)

    def test_rejects_stale_right_review_from_independent_audit(self):
        def stale(attempt, processing, review):
            if review == self.paths[-1]:
                raise ValueError('pixel review source SHA changed')
            return self.delivery(attempt, processing, review)
        with self.assertRaisesRegex(ValueError, 'pixel review source SHA changed'):
            self.run_audit(delivery=stale)

    def test_rejects_right_receipt_without_pixel_acceptance(self):
        def incomplete(attempt, processing, review):
            result = self.delivery(attempt, processing, review)
            if review == self.paths[-1]:
                result['actual_pixels_reviewed'] = False
            return result
        with self.assertRaisesRegex(ValueError, 'independent delivery audit incomplete'):
            self.run_audit(delivery=incomplete)


if __name__ == '__main__':
    unittest.main()
