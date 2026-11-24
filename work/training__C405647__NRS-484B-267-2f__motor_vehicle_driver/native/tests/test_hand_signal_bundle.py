"""Offline checks for a materialized source-driver hand-signal construction."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner


class NativeHandSignal(unittest.TestCase):
    def test_identity_cameras_and_stopped_signal_request(self):
        config = runner.config()
        self.assertTrue(config['case_id'].endswith('__visible_hand_signal'))
        self.assertEqual(len(config['cameras']), 4)
        self.assertEqual([runner.source_motion_request(i, config) for i in (79, 80, 99, 100)],
                         [0, 0, 0, -config['requested_subsequent_emergency_speed_mps']])

    def test_opposing_lanes_and_right_edge_request(self):
        config = runner.config()
        self.assertIn('lane id="1"', runner.road_xml())
        self.assertIn('lane id="-1"', runner.road_xml())
        self.assertEqual(runner.subject_response(125, config, -60, -2.5, -20)[2],
                         'stopped_until_passed')


if __name__ == '__main__':
    unittest.main()
