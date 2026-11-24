import unittest
from pathlib import Path
import runner


class OfficialConstruction(unittest.TestCase):
    def test_exact_official_case_config(self):
        if (Path(runner.__file__).resolve().parent / 'config.json').is_file():
            config = runner.config()
            self.assertEqual(config['case_suffix'], 'official_approach')
            self.assertEqual(config['responding_vehicle_kind'], 'regulatory_agency_official')

    def test_official_agency_review_is_required(self):
        survey = {'map_name': 'C405647-two-phase-emergency', 'map_source': 'review',
                  'road_geometry_source': 'authored:runner.road_xml',
                  'ego_blueprint': 'vehicle.tesla.model3',
                  'emergency_blueprint': 'vehicle.tesla.model3',
                  'ego_spawn_xyz_m': [-75, -1.75, .5],
                  'emergency_spawn_xyz_m': [-15, 1.75, .5],
                  'camera_world_transforms': {name: {'xyz_m': [0, 0, 1],
                                                    'rotation_deg': [0, 0, 0]}
                                              for name in runner.CAMERAS},
                  'official_regulatory_agency_source': 'original review',
                  'official_vehicle_reviewed': False,
                  'qualifying_flash_equipment_source': 'original review',
                  'qualifying_flash_equipment_reviewed': True,
                  'officer_direction_review_source': 'original review',
                  'officer_directed_otherwise': False}
        with self.assertRaisesRegex(ValueError, 'Regulatory official identity'):
            runner.survey_check(survey)
        survey['official_vehicle_reviewed'] = True
        self.assertIs(runner.survey_check(survey), survey)

    def test_official_approach_requests_right_edge_stop(self):
        config = {'case_suffix': 'official_approach',
                  'requested_initial_subject_speed_mps': 3,
                  'requested_subsequent_subject_speed_mps': 0,
                  'requested_right_edge_center_y_m': -2.5}
        self.assertEqual(runner.subject_response(220, config, -59, -2.5, -27),
                         (0.0, 0.0, 'stopped_until_passed'))


if __name__ == '__main__':
    unittest.main()
