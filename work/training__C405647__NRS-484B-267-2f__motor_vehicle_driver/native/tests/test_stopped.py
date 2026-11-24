import unittest
from pathlib import Path
import runner


class StoppedConstruction(unittest.TestCase):
    def test_exact_stop_request(self):
        if (Path(runner.__file__).resolve().parent / 'config.json').is_file():
            config = runner.config()
            self.assertEqual(config['case_suffix'], 'stopped_referral')
            self.assertEqual(config['requested_emergency_stop_frame'], 200)

    def test_subject_holds_position_when_source_stops(self):
        config = {'case_suffix': 'stopped_referral',
                  'requested_initial_subject_speed_mps': 3,
                  'requested_subsequent_subject_speed_mps': 0,
                  'requested_right_edge_center_y_m': -2.5}
        self.assertEqual(runner.subject_response(220, config, -59, -2.5, -25),
                         (0.0, 0.0, 'stopped_until_passed'))
        self.assertEqual(runner.subject_response(580, config, -59, -2.5, -25),
                         (0.0, 0.0, 'stopped_until_passed'))


if __name__ == '__main__':
    unittest.main()
