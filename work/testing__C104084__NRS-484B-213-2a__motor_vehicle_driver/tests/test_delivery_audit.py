import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[1] / 'runtime'))

from analysis import analyze
from delivery_audit import audit
from saved_delivery import process
from test_saved_delivery import ASSIGNMENT, CAMERAS, CASE, video_attempt


class IndependentDeliveryAuditTests(unittest.TestCase):
    def prepared(self, root):
        attempt = root / 'attempt'
        attempt.mkdir()
        video_attempt(attempt)
        analyze(attempt, assignment_id=ASSIGNMENT, case_id=CASE,
                expected_frames=3,
                recording_description={'channels': [], 'context_inputs': []})
        receipt = root / 'saved-receipt.json'
        process(attempt, receipt, assignment_id=ASSIGNMENT, case_id=CASE,
                expected_frames=3,
                expected_dimensions={camera: (32, 24) for camera in CAMERAS})
        return attempt, receipt

    def check(self, attempt, receipt):
        return audit(attempt, receipt, assignment_id=ASSIGNMENT, case_id=CASE,
                     expected_frames=3,
                     expected_dimensions={camera: (32, 24) for camera in CAMERAS})

    def test_joins_original_media_saved_receipt_and_derived_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            attempt, receipt = self.prepared(Path(temporary))
            result = self.check(attempt, receipt)
            self.assertEqual(result['verified_frames'], 3)
            self.assertEqual(set(result['decoded_media_sha256']), set(CAMERAS))
            self.assertTrue(result['source_join_passed'])
            self.assertFalse(result['physical_acceptance_claimed'])

    def test_rejects_rewritten_saved_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            attempt, receipt = self.prepared(Path(temporary))
            value = json.loads(receipt.read_text())
            value['physical_visibility_reviewed'] = True
            receipt.write_text(json.dumps(value) + '\n')
            with self.assertRaisesRegex(ValueError, 'saved delivery receipt differs'):
                self.check(attempt, receipt)

    def test_rejects_changed_derived_trace(self):
        with tempfile.TemporaryDirectory() as temporary:
            attempt, receipt = self.prepared(Path(temporary))
            trace = attempt / 'trace.jsonl'
            rows = [json.loads(line) for line in trace.read_text().splitlines()]
            rows[0]['opposing_body_distance_m'] = 999
            trace.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'derived trace differs'):
                self.check(attempt, receipt)


if __name__ == '__main__':
    unittest.main()
