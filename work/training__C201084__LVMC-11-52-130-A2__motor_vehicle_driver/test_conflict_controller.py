"""CPU geometry and control checks for the unexecuted lead-traffic probe."""
import unittest

from conflict_controller import decision


class ConflictControllerTest(unittest.TestCase):
    def test_approaching_stopped_lead_requests_brake(self):
        row = decision((10, 1), (4, 0), (18, 1), (0, 0), 0)
        self.assertTrue(row['brake_requested_from_lead_relation'])
        self.assertEqual((row['throttle'], row['brake']), (0.0, 1.0))
        self.assertFalse(row['statutory_necessity_claimed'])

    def test_far_lead_requests_cruise(self):
        row = decision((0, 1), (4, 0), (40, 1), (0, 0), 0)
        self.assertFalse(row['brake_requested_from_lead_relation'])
        self.assertEqual(row['brake'], 0.0)

    def test_lead_speed_reduces_closing_distance(self):
        moving = decision((0, 1), (4, 0), (8, 1), (3, 0), 0)
        stopped = decision((0, 1), (4, 0), (8, 1), (0, 0), 0)
        self.assertLess(moving['engineering_braking_distance_m'],
                        stopped['engineering_braking_distance_m'])

    def test_rejects_other_path_and_rear_traffic(self):
        with self.assertRaisesRegex(ValueError, 'not ahead'):
            decision((0, 1), (4, 0), (8, 4), (0, 0), 0)
        with self.assertRaisesRegex(ValueError, 'not ahead'):
            decision((0, 1), (4, 0), (-8, 1), (0, 0), 0)

    def test_rejects_invalid_source_and_tuning(self):
        with self.assertRaisesRegex(ValueError, 'Invalid ego velocity'):
            decision((0, 1), (float('nan'), 0), (8, 1), (0, 0), 0)
        with self.assertRaisesRegex(ValueError, 'Invalid conflict controller tuning'):
            decision((0, 1), (4, 0), (8, 1), (0, 0), 0, stop_gap_m=0)
