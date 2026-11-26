import json
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

    def test_survey_requires_source(self):
        with self.assertRaisesRegex(ValueError, 'map_name'):
            survey_check({})

    def test_survey_geometry(self):
        survey = {'map_name': 'synthetic', 'survey_source': 'test',
                  'driveway_boundary_source': 'test', 'ego_blueprint': 'vehicle.test',
                  'spawn_xyz_m': [0, 0, 0], 'spawn_yaw_deg': 0,
                  'camera_world_transforms': {k: {'xyz_m': [0, 0, 0], 'rotation_deg': [0, 0, 0]} for k in CAMERAS},
                  'road_axis_xy': [1, 0], 'stop_centre_xyz_m': [14.2, 0, 0],
                  'driveway_curb_interval_m': [8, 11], 'ego_half_length_m': 2.0,
                  'road_id': 7, 'traffic_device_direction': True, 'traffic_device_direction_source': 'test source'}
        self.assertEqual(survey_check(survey), survey)
        survey['stop_centre_xyz_m'] = [10, 0, 0]
        with self.assertRaisesRegex(ValueError, 'exact driveway gap'):
            survey_check(survey)
        survey['stop_centre_xyz_m'] = [14.2, 0, 0]
        survey['traffic_device_direction'] = False
        with self.assertRaisesRegex(ValueError, 'traffic_device_direction'):
            survey_check(survey)
        survey['traffic_device_direction'] = True
        survey['road_axis_xy'] = [2, 0]
        with self.assertRaisesRegex(ValueError, 'unit length'):
            survey_check(survey)


if __name__ == '__main__':
    unittest.main()
