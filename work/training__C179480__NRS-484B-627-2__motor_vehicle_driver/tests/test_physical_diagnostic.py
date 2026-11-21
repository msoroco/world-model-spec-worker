import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import physical_diagnostic as physical


class PhysicalDiagnosticTest(unittest.TestCase):
    def test_all_case_outcomes_and_no_legal_acceptance(self):
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}
        for case in physical.EXPECTED_OVERLAP:
            for kind, status in expected.items():
                with self.subTest(case=case, kind=kind):
                    result = physical.evaluate(case, kind)
                    self.assertEqual(result['physical_checks']['maneuver']['status'], status)
                    self.assertEqual(result['maneuver_completed'], status == 'met')
                    self.assertFalse(result['accepted'])
                    self.assertFalse(result['legal_verdict_claimed'])

    def test_missing_source_history_cannot_count_as_complete(self):
        with patch.object(physical, 'load_rows', return_value=[]):
            with self.assertRaisesRegex(ValueError, '600 synchronized samples'):
                physical.evaluate('reference', 'complete_motion')

    def test_misplaced_stop_cannot_count_as_complete(self):
        original = physical.load_rows
        def shifted(*args):
            rows = [dict(row) for row in original(*args)]
            for row in rows:
                row['ego_lane_overlap'] = False
            return rows
        with patch.object(physical, 'load_rows', side_effect=shifted):
            with self.assertRaisesRegex(ValueError, 'expected outcome'):
                physical.evaluate('reference', 'complete_motion')


if __name__ == '__main__':
    unittest.main()
