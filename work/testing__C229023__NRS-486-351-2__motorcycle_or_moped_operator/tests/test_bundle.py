"""Offline bundle tests that run both in work/ and materialized Native bundle."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scene_review import construction


class BundleTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'config.json').read_text())
        self.survey = {
            'route_origin_xy': [0, 0], 'route_unit_xy': [1, 0],
            'route_stations_m': [0, 10, 20, 30, 40, 50],
            'lane_width_m': 4.7, 'ego_lane_id': 1, 'other_lane_id': 1,
            'adjacent_lane_id': 2, 'adjacent_lane_center_offset_m': 4.7,
            'abreast_lateral_offsets_m': [-1.3, 0, 1.3],
            'participant_half_widths_m': [0.35, 0.35, 0.35],
            'other_vehicle_class': 'motorcycle',
        }

    def test_exact_case_kinematic_request(self):
        case = self.config['case']
        request = construction(self.survey, case)
        expected = 3 if case['requested_two_wheeler_count'] == 3 else 2
        self.assertEqual(len(request['participants']), expected)
        ego, other = request['participants'][:2]
        self.assertEqual(ego['lane_id'] == other['lane_id'], case['requested_same_lane'])
        if case['requested_pass']:
            self.assertLess(ego['station_m'], other['station_m'])
        else:
            self.assertEqual(ego['station_m'], other['station_m'])

    def test_same_lane_footprint_constraint(self):
        self.survey['lane_width_m'] = 3.5
        self.survey['abreast_lateral_offsets_m'] = [-1.55, 0, 1.55]
        case = dict(self.config['case'], requested_same_lane=True,
                    requested_two_wheeler_count=3, requested_pass=False)
        with self.assertRaisesRegex(ValueError, 'footprint'):
            construction(self.survey, case)


if __name__ == '__main__':
    unittest.main()
