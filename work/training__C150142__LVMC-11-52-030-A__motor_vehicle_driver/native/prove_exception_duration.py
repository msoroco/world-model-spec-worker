"""Boundary and invalid-grid probes for the requested long capture schedule."""
import json
from pathlib import Path
import unittest
from exception_duration import plan


class CaptureScheduleProof(unittest.TestCase):
    def test_thirty_minute_boundary(self):
        matrix = json.loads((Path(__file__).resolve().parents[1] /
                             'exception-case-matrix.json').read_text())
        cases = {case['case_id'].rsplit('__', 1)[-1]: case
                 for case in matrix['cases']}
        for label, duration, stationary, total in (
                ('below', 1799.95, 36000, 36120),
                ('at', 1800, 36001, 36121),
                ('above', 1800.05, 36002, 36122)):
            schedule = plan(cases['tour_bus_' + label])
            self.assertEqual(schedule['requested_boundary'], label)
            self.assertEqual(schedule['stationary_frames'], stationary)
            self.assertEqual(schedule['capture_frames'], total)
            self.assertEqual((schedule['stationary_last_frame'] -
                              schedule['stationary_first_frame']) / 20, duration)
            self.assertFalse(schedule['original_native_observed'])

    def test_rejects_off_grid_and_invalid_requests(self):
        for duration in (1800.01, -1, 'nan'):
            with self.assertRaises(ValueError):
                plan({'case_id': 'tour_bus',
                      'requested_stationary_duration_s': duration})
        with self.assertRaisesRegex(ValueError, 'approach'):
            plan({'case_id': 'tour_bus',
                  'requested_stationary_duration_s': 1800}, 0)


if __name__ == '__main__':
    unittest.main()
