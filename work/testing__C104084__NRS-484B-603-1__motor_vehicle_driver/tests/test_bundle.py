"""Materialized exact-bundle offline checks; no CARLA or claimed footage."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import runner
from crest_speed import crest_station
from saved_crest_audit import ASSIGNMENT, PROFILES


class ExactBundleTests(unittest.TestCase):
    def test_selected_source_case_and_profile(self):
        config = json.loads((ROOT / 'config.json').read_text())
        case = config['selected_case_id']
        self.assertEqual(config['case']['case_id'], case)
        self.assertEqual(case, ASSIGNMENT + '__' + config['case']['profile'])
        self.assertIn(config['case']['profile'], PROFILES)
        self.assertEqual((config['rate_hz'], config['duration_s'], config['frame_count']),
                         (20, 45, 900))
        self.assertEqual(runner.main(['--check']), 0)

    def test_authored_crest_not_flat(self):
        from native_crest_setup import _road_profile
        text = (ROOT / 'candidate-crest-road.xodr').read_text()
        length, coefficients = _road_profile(text)
        self.assertGreater(length, 450)
        self.assertLess(coefficients[2], 0)
        self.assertEqual(crest_station([{'s_m': s, 'z_m': z,
            'source_ref': 'original-map'} for s, z in
            ((0, 0), (10, 2), (20, 4), (30, 2), (40, 0))]), 20)


if __name__ == '__main__':
    unittest.main()
