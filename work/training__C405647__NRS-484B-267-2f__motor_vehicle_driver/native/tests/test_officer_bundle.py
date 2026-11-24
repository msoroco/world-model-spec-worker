"""Offline checks for a materialized officer-direction construction."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner


class NativeOfficerDirection(unittest.TestCase):
    def test_identity_cameras_and_continued_travel_request(self):
        config = runner.config()
        self.assertTrue(config['case_id'].endswith('__officer_direction'))
        self.assertEqual(len(config['cameras']), 4)
        self.assertEqual([runner.source_motion_request(i, config) for i in (99, 100)],
                         [0, -config['requested_subsequent_emergency_speed_mps']])
        self.assertEqual(runner.subject_response(125, config, -60, -1.75, -20)[2],
                         'continued_travel')

    def test_opposing_lanes(self):
        self.assertIn('lane id="1"', runner.road_xml())
        self.assertIn('lane id="-1"', runner.road_xml())


if __name__ == '__main__':
    unittest.main()
