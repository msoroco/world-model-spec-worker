import unittest
from following_construction import PHASES, phase_at, validate_schedule


class BeyondScheduleTests(unittest.TestCase):
    def test_second_request_beyond_one_mile(self):
        self.assertTrue(validate_schedule())
        first, second = [p for p in PHASES if 'closing_request' in p.label]
        self.assertGreater(second.start_m - first.end_m, 1609.344)
        self.assertEqual(phase_at(600).label, 'separate_encounters')
        self.assertEqual(phase_at(2000).label, 'second_closing_request')
