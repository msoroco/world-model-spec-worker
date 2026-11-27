import copy
import unittest
from selected_plan import CASES, CELL, compare, request


class SelectedPlanTest(unittest.TestCase):
    def setUp(self):
        self.survey = {
            'source_kind': 'original_native_road_edge_survey',
            'fixed_cell': CELL, 'map_name': 'reviewed_map',
            'roadway_boundary_source_id': 'native_lane_boundary',
            'edge_tangent_source_id': 'native_edge',
            'lawful_traffic_source_id': 'independent_control_inventory',
            'parking_permission_source_id': 'original_traffic_engineer_review',
            'roadway_class_source_id': 'original_map_review',
            'vehicle_identity_source_id': 'native_actor_id',
            'driver_identity_source_id': 'original_operator_review',
            'rest_activity_source_id': 'independent_full_video_review',
            'reviewed_source_sha256': 'a' * 64, 'reviewer': 'independent_review',
            'chapter_exception_status': 'unknown',
            'chapter_exception_source_refs': [],
            'edge_tangent_xy': [1, 0], 'lawful_direction_xy': [1, 0],
            'spawn_xyz_yaw_deg': [0, 0, 0, 0], 'rest_xyz_m': [1, 0, 0],
            'vehicle_blueprint': 'vehicle.reviewed'
        }

    def test_all_six_separated(self):
        plans = {case: request(case, self.survey) for case in CASES}
        self.assertEqual(len(plans), 6)
        self.assertEqual(compare(plans)['requested_activities'],
                         ['standing', 'parking'])
        self.assertEqual(len({p['rest_pose_requested'] for p in plans.values()}), 3)
        self.assertTrue(all(p['legal_result'] is None for p in plans.values()))

    def test_missing_authority_rejected(self):
        survey = copy.deepcopy(self.survey)
        survey['chapter_exception_status'] = 'applicable'
        with self.assertRaisesRegex(ValueError, 'original authority'):
            request(next(iter(CASES)), survey)

    def test_fixed_source_change_rejected(self):
        plans = {case: request(case, self.survey) for case in CASES}
        plans[next(iter(CASES))]['fixed_lawful_direction_source'] = 'different'
        with self.assertRaisesRegex(ValueError, 'fixed source changed'):
            compare(plans)

    def test_request_change_rejected(self):
        plans = {case: request(case, self.survey) for case in CASES}
        plans[next(iter(CASES))]['requested_yaw_offset_deg'] = 9
        with self.assertRaisesRegex(ValueError, 'case setting changed'):
            compare(plans)


if __name__ == '__main__':
    unittest.main()
