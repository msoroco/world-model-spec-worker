import importlib.util
from pathlib import Path
import unittest


MODULE = Path(__file__).resolve().parents[1] / 'assess_statutory.py'
SPEC = importlib.util.spec_from_file_location('assess_statutory', MODULE)
statutory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(statutory)


def rows():
    def body(y):
        return [[x, y + dy, z] for x in (1, 2) for dy in (-1, 1) for z in (0, 1)]
    return [
        {'native_frame': i, 'ego_front_x_m': x, 'ego_center_x_m': x - 2,
         'ego_speed_mps': v,
         'other': {'speed_mps': ov, 'body_xyz_m': body(y)}}
        for i, x, v, ov, y in [
            (1, -12, 4, 0, -10),
            (2, -10, 0, 3, -5),
            (3, -8, 2, 3, -3),
            (4, -6, 2, 3, -1),
            (5, -4, 2, 3, 9),
        ]]


def survey(**kw):
    value = {'stop_line_present': False, 'near_side_crosswalk_present': False,
             'sidewalk_derived_crosswalk_reviewed': True,
             'intersection_entry_front_x_m': -6,
             'intersection_bounds_xy_m': [-6, -6, 6, 6],
             'driver_view_samples': [{'center_x_m': -9,
                                      'approaching_traffic_visible': True}]}
    value.update(kw)
    return value


class StatutoryAlternatives(unittest.TestCase):
    def test_absent_line_and_crosswalk_uses_surveyed_view(self):
        result = statutory.assess(survey(), rows())
        self.assertEqual(result['stop_reference'], 'nearest_surveyed_view')
        self.assertEqual(result['ego_stop_frame'], 2)
        self.assertTrue(result['other_stopped_before_ego'])
        self.assertTrue(result['other_within_intersection_at_ego_entry'])
        self.assertEqual(result['other_clear_frame_at_or_after_ego_entry'], 5)
        self.assertFalse(result['continuous_nearest_view_proven'])
        self.assertFalse(result['yield_judgment_proven'])

    def test_marked_line_has_priority_over_crosswalk_and_view(self):
        value = survey(stop_line_present=True, stop_line_front_x_m=-9,
                       near_side_crosswalk_present=True, crosswalk_near_edge_x_m=-7)
        result = statutory.assess(value, rows())
        self.assertEqual(result['stop_reference'], 'marked_stop_line')
        self.assertEqual(result['reference_x_m'], -9)

    def test_crosswalk_has_priority_over_view(self):
        value = survey(near_side_crosswalk_present=True, crosswalk_near_edge_x_m=-9)
        result = statutory.assess(value, rows())
        self.assertEqual(result['stop_reference'], 'near_side_crosswalk')
        self.assertEqual(result['reference_x_m'], -9)

    def test_missing_original_branches_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'crosswalk review'):
            statutory.assess(survey(near_side_crosswalk_present=True,
                                    sidewalk_derived_crosswalk_reviewed=False), rows())
        broken = rows()
        del broken[0]['other']['body_xyz_m']
        with self.assertRaisesRegex(ValueError, 'body history'):
            statutory.assess(survey(), broken)
        with self.assertRaisesRegex(ValueError, 'stop line'):
            statutory.assess(survey(stop_line_present=True), rows())


if __name__ == '__main__':
    unittest.main()
