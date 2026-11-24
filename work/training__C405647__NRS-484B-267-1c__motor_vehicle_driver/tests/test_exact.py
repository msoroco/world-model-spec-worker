"""CPU regression checks for source-bound emergency passage timing."""
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'native'))
from emergency_wait import measure

class EmergencyPassageTests(unittest.TestCase):
    def rows(self):
        source = HERE / 'requested-track.jsonl'
        return [json.loads(line) for line in source.read_text().splitlines()]

    def test_whole_body_passage_follows_center(self):
        value = measure(self.rows(), 'authored_native_request')
        self.assertLess(value['requested_center_passage_frame'],
                        value['requested_whole_body_passage_frame'])
        self.assertLess(value['requested_whole_body_passage_frame'],
                        value['requested_first_ego_motion_frame'])
        self.assertTrue(value['requested_waits_through_whole_body_passage'])
        self.assertIsNone(value['legal_verdict'])

    def test_truncated_source_rejected(self):
        with self.assertRaisesRegex(ValueError, '600-frame'):
            measure(self.rows()[:-1], 'authored_native_request')

    def test_missing_full_body_rejected(self):
        rows = self.rows()
        rows[42].pop('emergency_body_xy_m')
        with self.assertRaisesRegex(ValueError, 'body footprints'):
            measure(rows, 'authored_native_request')

if __name__ == '__main__':
    unittest.main()
