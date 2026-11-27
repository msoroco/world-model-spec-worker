"""Exact Native emergency caution setup and controlled phase tests."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import check, requested_velocities
from road_geometry import check as road_check

class EmergencyCautionTests(unittest.TestCase):
    def test_exact_materialized_case_and_road(self):
        config=json.loads((Path(__file__).resolve().parents[1]/'config.json').read_text())
        self.assertEqual(check(config)['frames'],600)
        self.assertTrue(road_check())
        self.assertEqual(config['requested_role'], 'official_regulatory' if config['case_id'].endswith('probe_03') else 'authorized_emergency')
    def test_controlled_approach_and_preparation(self):
        self.assertEqual(requested_velocities('01',100)['ego'],(4.0,0.0))
        self.assertEqual(requested_velocities('02',100)['ego'],(6.0,0.0))
        self.assertEqual(requested_velocities('04',100)['emergency'],(0.0,0.0))
        self.assertEqual(requested_velocities('05',100)['emergency'],(1.2,0.0))
    def test_frame_rejection(self):
        with self.assertRaisesRegex(ValueError,'Frame outside capture'):
            requested_velocities('01',600)

if __name__=='__main__': unittest.main()
