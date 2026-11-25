import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import CASE, CAMERAS, config_check, survey_check


class BundleTest(unittest.TestCase):
    def test_exact_case(self):
        proof = config_check()
        self.assertEqual(proof['case_id'], CASE)
        self.assertEqual(proof['frames'], 600)
        self.assertEqual(tuple(proof['cameras']), CAMERAS)
        self.assertFalse(proof['physical_acceptance_claimed'])

    def test_survey_requires_authority(self):
        with self.assertRaisesRegex(ValueError, 'map_name'):
            survey_check({})

    def test_survey_geometry(self):
        survey = {'map_name': 'synthetic', 'survey_source': 'test',
                  'zone_establishment_source': 'test', 'installed_sign_source': 'test',
                  'authorized_value_source': 'test', 'zone_boundary_source': 'test',
                  'governing_road_direction_source': 'test', 'ego_blueprint': 'vehicle.test',
                  'spawn_xyz_m': [0, 0, 0], 'spawn_yaw_deg': 0,
                  'camera_world_transforms': {k: {'xyz_m': [0, 0, 0], 'rotation_deg': [0, 0, 0]} for k in CAMERAS},
                  'road_axis_xy': [1, 0], 'zone_station_bounds_m': [20, 200],
                  'authorized_mph': 35.0, 'road_id': 7, 'travel_direction_id': 'east'}
        self.assertEqual(survey_check(survey), survey)
        survey['road_axis_xy'] = [2, 0]
        with self.assertRaisesRegex(ValueError, 'unit length'):
            survey_check(survey)


if __name__ == '__main__':
    unittest.main()
