import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('crossing_geometry', ROOT/'crossing_geometry.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def scene(route, context='outside'):
    polygon = [[4, -1], [9, -1], [9, 7], [4, 7]] if context == 'inside' else [[20, -1], [25, -1], [25, 7], [20, 7]]
    return {'actor': 'pedestrian', 'starting_curb_xy_m': [[0, 0], [10, 0]],
            'opposite_curb_xy_m': [[0, 6], [10, 6]], 'route_xy_m': route,
            'crosswalk_boundaries_xy_m': [polygon], 'crosswalk_context': context,
            'jurisdiction_source': 'site survey needed', 'curb_source': 'survey needed',
            'control_context': 'none recorded'}


class CrossingGeometryTests(unittest.TestCase):
    def test_right_angle_and_shortest(self):
        out = m.validate_scene(scene([[5, 0], [5, 6]]))
        self.assertAlmostEqual(out['angle_to_starting_curb_deg'], 90)
        self.assertAlmostEqual(out['route_excess_over_geometric_minimum_m'], 0)
        self.assertEqual(out['legal_route_classification'], 'unresolved')

    def test_oblique_shortest_to_finite_curb_endpoint(self):
        item = scene([[12, 0], [10, 6]])
        out = m.validate_scene(item)
        self.assertLess(out['angle_to_starting_curb_deg'], 90)
        self.assertAlmostEqual(out['route_excess_over_geometric_minimum_m'], 0)
        self.assertEqual(out['shortest_opposite_curb_fraction'], 1)

    def test_oblique_longer_route_preserves_continuous_measurement(self):
        out = m.validate_scene(scene([[5, 0], [8, 3], [7, 6]]))
        self.assertGreater(out['route_excess_over_geometric_minimum_m'], 0)
        self.assertLess(out['angle_to_starting_curb_deg'], 90)

    def test_inside_crosswalk_is_context_not_legal_verdict(self):
        out = m.validate_scene(scene([[5, 0], [8, 6]], 'inside'))
        self.assertEqual(out['legal_route_classification'], 'unresolved')

    def test_crosswalk_flag_without_geometry_rejected(self):
        item = scene([[5, 0], [8, 6]], 'outside')
        item['crosswalk_boundaries_xy_m'] = [[[4, -1], [9, -1], [9, 7], [4, 7]]]
        with self.assertRaisesRegex(ValueError, 'geometry disagree'):
            m.validate_scene(item)

    def test_crosswalk_segment_crosses_polygon_between_sampled_points(self):
        item = scene([[0, 0], [10, 6]], 'outside')
        item['crosswalk_boundaries_xy_m'] = [[[4, 1], [6, 1], [6, 5], [4, 5]]]
        with self.assertRaisesRegex(ValueError, 'geometry disagree'):
            m.validate_scene(item)
        self.assertFalse(m.crosswalk_overlap([[0, 0], [2, 0]], [[[4, 0], [6, 0], [6, 5], [4, 5]]]))

    def test_missing_context_rejected(self):
        item = scene([[5, 0], [5, 6]])
        item.pop('control_context')
        with self.assertRaisesRegex(ValueError, 'control context'):
            m.validate_scene(item)

    def test_original_history_required(self):
        item = scene([[5, 0], [5, 6]])
        with self.assertRaisesRegex(ValueError, 'history missing'):
            m.measure_original_history([], item)
        rows = [{'frame': i, 'source': 'original_native', 'actor_id': 42,
                 'body_center_xy_m': [5, i]} for i in range(7)]
        out = m.measure_original_history(rows, item)
        self.assertEqual(out['original_frame_count'], 7)
        rows[3]['source'] = 'requested_waypoint'
        with self.assertRaisesRegex(ValueError, 'original Native'):
            m.measure_original_history(rows, item)

    def test_duplicate_frame_and_actor_rejected(self):
        item = scene([[5, 0], [5, 6]])
        rows = [{'frame': 1, 'source': 'original_native', 'actor_id': 42,
                 'body_center_xy_m': [5, 0]},
                {'frame': 1, 'source': 'original_native', 'actor_id': 43,
                 'body_center_xy_m': [5, 6]}]
        with self.assertRaisesRegex(ValueError, 'frames invalid'):
            m.measure_original_history(rows, item)
        rows[1]['frame'] = 2
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            m.measure_original_history(rows, item)

    def test_bad_points_rejected(self):
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            m.route_measurement([[0, 0], [float('nan'), 6]], [[0, 0], [1, 0]], [[0, 6], [1, 6]])
        with self.assertRaisesRegex(ValueError, 'zero-length curb'):
            m.route_measurement([[0, 0], [0, 6]], [[0, 0], [0, 0]], [[0, 6], [1, 6]])


if __name__ == '__main__':
    unittest.main()
