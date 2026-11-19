import unittest

from scene_plan import validate


def survey():
    return {'map_name': 'surveyed-map', 'road_id': 8,
            'repair_polygon_xy_m': [[-1, -1], [1, -1], [1, 1], [-1, 1]],
            'warning_person_actor_id': 12, 'warning_person_xy_m': [2, 0],
            'route_over_xy_m': [[-5, 0], [5, 0]],
            'route_avoid_xy_m': [[-5, 0], [-3, 2], [0, 3], [3, 2], [5, 0]],
            'frames': 600, 'ego_blueprint': 'vehicle.example',
            'weather_profile': 'surveyed-clear'}


class ScenePlanTest(unittest.TestCase):
    def test_isolates_crossing_with_shared_scene(self):
        plan = validate(survey(), 'surveyed-map')
        self.assertTrue(plan['cases']['reference']['requested_pavement_crossing'])
        self.assertFalse(plan['cases']['contrast']['requested_pavement_crossing'])
        self.assertEqual(plan['frames'], 600)
        self.assertFalse(plan['physical_completion_claimed'])

    def test_rejects_false_comparison_and_short_capture(self):
        x = survey(); x['route_avoid_xy_m'] = [[-5, 0], [5, 0]]
        with self.assertRaisesRegex(ValueError, 'isolate'):
            validate(x, 'surveyed-map')
        x = survey(); x['frames'] = 599
        with self.assertRaisesRegex(ValueError, '30 seconds'):
            validate(x, 'surveyed-map')


if __name__ == '__main__':
    unittest.main()
