import unittest
import runner

class TestNative(unittest.TestCase):
    def test_contract(self):
        self.assertEqual(runner.config_check()['law_id'], 'NRS-484B-785-1a')
        self.assertEqual(runner.COUNT, 600)

    def test_requested_speed_and_classification_are_separate(self):
        survey = {
            'map_name': 'diagnostic', 'survey_source': 'diagnostic',
            'device_subtype': 'electric_scooter', 'device_subtype_source': 'diagnostic',
            'rider_identity_source': 'diagnostic', 'path_surface_source': 'diagnostic',
            'path_continuity_source': 'diagnostic', 'path_adjacency_source': 'diagnostic',
            'path_obstruction_source': 'diagnostic', 'path_usability_review_source': 'diagnostic',
            'roadway_boundary_source': 'diagnostic', 'device_blueprint': 'vehicle.scooter',
            'rider_blueprint': 'walker.rider', 'device_spawn_xyz_m': [0, 0, 0],
            'device_spawn_yaw_deg': 0, 'rider_attach_xyz_m': [0, 0, 1],
            'travel_unit_xy': [1, 0], 'target_speed_mps': 12 * .44704,
            'camera_world_transforms': {name: {'xyz_m': [0, 0, 2], 'rotation_deg': [0, 0, 0]}
                                        for name in runner.CAMERAS},
            'scooter_classification_source': 'diagnostic', 'scooter_mass_source': 'diagnostic',
            'scooter_motor_max_speed_source': 'diagnostic', 'ordinance_applicability_source': 'diagnostic',
            'local_path_permission_source': 'diagnostic', 'device_blueprint_source': 'diagnostic',
            'scooter_handlebars_source': 'diagnostic', 'scooter_electric_motor_source': 'diagnostic',
            'scooter_riding_design_source': 'diagnostic', 'scooter_propulsion_source': 'diagnostic',
            'contrary_posting_source': 'diagnostic', 'local_definition_applicability_source': 'diagnostic',
            'assistive_device_intent_source': 'diagnostic',
            'scooter_rider_excluded_mass_lb': 45, 'scooter_motor_only_max_mph': 18,
            'ordinance_exception_reviewed': True,
        }
        runner.survey_check(survey)
        survey['target_speed_mps'] = 15 * .44704
        with self.assertRaisesRegex(ValueError, 'below-15-mph'):
            runner.survey_check(survey)
        survey['target_speed_mps'] = 12 * .44704
        survey['device_blueprint'] = 'vehicle.bicycle'
        with self.assertRaisesRegex(ValueError, 'Bicycle blueprint'):
            runner.survey_check(survey)

if __name__ == '__main__': unittest.main()
