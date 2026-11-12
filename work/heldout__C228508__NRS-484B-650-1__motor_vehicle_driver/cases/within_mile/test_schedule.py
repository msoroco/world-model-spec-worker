import unittest
from following_construction import PHASES, phase_at, validate_schedule


class WithinScheduleTests(unittest.TestCase):
    def test_both_requests_fit_within_one_mile(self):
        self.assertTrue(validate_schedule())
        first, second = [p for p in PHASES if 'closing_request' in p.label]
        self.assertLess(second.end_m - first.start_m, 1609.344)
        self.assertEqual(phase_at(600).label, 'separate_encounters')
        self.assertEqual(phase_at(1100).label, 'second_closing_request')
