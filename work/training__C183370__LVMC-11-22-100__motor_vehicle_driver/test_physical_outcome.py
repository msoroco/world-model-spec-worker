"""Boundary tests for measured route completion and capture ownership order."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'native'))
from physical_outcome import EVENTS, check_lifecycle, classify
from run_physical_fixture import sample_rows

PAVEMENT = [[-1, -1], [1, -1], [1, 1], [-1, 1]]


class PhysicalOutcomeTests(unittest.TestCase):
    def test_crossing_requires_measured_body_contact(self):
        rows = sample_rows(crossing=True, kind='complete_motion')
        result = classify(rows, PAVEMENT, True)
        self.assertEqual(result['physical_checks']['maneuver']['status'], 'met')
        self.assertGreater(result['realized_observables']['surveyed_contact_frame_count'], 0)
        self.assertFalse(result['physical_or_legal_acceptance_claimed'])

    def test_avoidance_requires_absent_body_contact(self):
        rows = sample_rows(crossing=False, kind='complete_motion')
        self.assertEqual(classify(rows, PAVEMENT, False)['physical_checks']['maneuver']['status'], 'met')
        self.assertEqual(classify(rows, PAVEMENT, True)['physical_checks']['maneuver']['status'], 'not_met')

    def test_incomplete_and_missing_are_distinct(self):
        incomplete = sample_rows(crossing=True, kind='incomplete_motion')
        missing = sample_rows(crossing=True, kind='missing_evidence')
        self.assertEqual(classify(incomplete, PAVEMENT, True)['physical_checks']['maneuver']['status'], 'not_met')
        self.assertEqual(classify(missing, PAVEMENT, True)['physical_checks']['maneuver']['status'], 'unverified')

    def test_broken_frame_join_is_unverified(self):
        rows = sample_rows(crossing=True, kind='complete_motion')
        rows[250]['frame'] = 251
        self.assertEqual(classify(rows, PAVEMENT, True)['physical_checks']['maneuver']['status'], 'unverified')

    def test_ownership_order_and_exit_are_required(self):
        self.assertEqual(check_lifecycle(EVENTS.copy(), 0)['exit_code'], 0)
        with self.assertRaisesRegex(ValueError, 'closed Native ownership'):
            check_lifecycle(EVENTS[:-2] + EVENTS[-1:] + EVENTS[-2:-1], 0)
        with self.assertRaisesRegex(ValueError, 'closed Native ownership'):
            check_lifecycle(EVENTS, 1)


if __name__ == '__main__':
    unittest.main()
