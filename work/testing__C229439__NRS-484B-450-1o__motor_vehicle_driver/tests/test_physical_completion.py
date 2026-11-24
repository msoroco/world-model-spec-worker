import sys
import unittest
from pathlib import Path


FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FOLDER))
from physical_completion import Lifecycle
from prove_physical import fixture


class PhysicalTests(unittest.TestCase):
    def setUp(self):
        self.case = {'case_id': 'test-case', 'halt_action': 'park',
                     'exact_instruction': 'NO PARKING', 'device_mode': 'effective',
                     'exception': 'none'}

    def test_three_measured_outcomes(self):
        for kind, status in (('complete_motion', 'met'),
                             ('incomplete_motion', 'not_met'),
                             ('missing_evidence', 'unverified')):
            result = fixture(self.case, kind)
            self.assertEqual(result['physical_checks']['maneuver']['status'], status)
            self.assertFalse(result.get('legal_judgment'))

    def test_lifecycle_rejects_early_saved_processing(self):
        lifecycle = Lifecycle()
        with self.assertRaisesRegex(ValueError, 'order changed'):
            lifecycle.record('saved_processing_started')
        for event in Lifecycle.EVENTS:
            lifecycle.record(event)
        self.assertEqual(lifecycle.complete()['events'][-1], 'saved_processing_started')


if __name__ == '__main__':
    unittest.main()
