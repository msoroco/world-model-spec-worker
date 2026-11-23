import copy
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('departure_geometry', Path(__file__).resolve().parents[1] / 'departure_geometry.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

CASE = 'testing__C109705__NRS-484B-400-2b__motor_vehicle_driver__near_centerline'


def packet(direction=(0, 1), kind='mapped'):
    map_data = {
        'case_id': CASE,
        'road_kind': 'two_directional_intersection',
        'approach_two_directional': True,
        'destination_two_directional': True,
        'approach_highway_status': 'source_verified',
        'destination_highway_status': 'source_verified',
        'centerline_kind': kind,
        'centerline_source': 'original_map.centerline',
        'direction_source': 'original_map.lane_direction',
        'centerline_origin_xy_m': [0, 0],
        'destination_direction_xy': list(direction),
        'approach_road_id': 1,
        'destination_road_id': 4,
    }
    trace = {
        'case_id': CASE,
        'approach_road_id': 1,
        'destination_road_id': 4,
        'maneuver': 'left_turn',
        'driver_control': True,
        'samples': [
            {'frame': 0, 'phase': 'approach'},
            {'frame': 30, 'phase': 'intersection_entry'},
            {'frame': 31, 'phase': 'turning'},
            {'frame': 50, 'phase': 'departure', 'road_id': 4,
             'body_corners_xy_m': [[1, 5], [2, 5], [2, 7], [1, 7]]},
            {'frame': 60, 'phase': 'departure', 'road_id': 4,
             'body_corners_xy_m': [[1.5, 8], [2.5, 8], [2.5, 10], [1.5, 10]]},
        ],
    }
    return map_data, trace


class DepartureGeometryTests(unittest.TestCase):
    def test_east_and_west_of_northbound_centerline(self):
        m, t = packet()
        out = module.measure(m, t, case_id=CASE)
        self.assertEqual(out['observed_right_min_m'], 1)
        self.assertEqual(out['observed_right_max_m'], 2.5)
        self.assertIsNone(out['statutory_position_judgment'])
        t['samples'][3]['body_corners_xy_m'] = [[-2, 5], [-1, 5], [-1, 7], [-2, 7]]
        self.assertLess(module.measure(m, t, case_id=CASE)['observed_right_min_m'], 0)

    def test_reverse_direction_changes_right_side(self):
        m, t = packet(direction=(0, -1), kind='source_derived_imaginary')
        out = module.measure(m, t, case_id=CASE)
        self.assertEqual(out['observed_right_max_m'], -1)
        self.assertEqual(out['centerline_kind'], 'source_derived_imaginary')

    def test_wrong_road_and_missing_body_rejected(self):
        m, t = packet()
        t['samples'][3]['road_id'] = 8
        with self.assertRaisesRegex(ValueError, 'destination road'):
            module.measure(m, t, case_id=CASE)
        m, t = packet()
        del t['samples'][3]['body_corners_xy_m']
        with self.assertRaisesRegex(ValueError, 'body corners'):
            module.measure(m, t, case_id=CASE)

    def test_missing_context_and_broken_order_rejected(self):
        m, t = packet()
        m['destination_two_directional'] = False
        with self.assertRaisesRegex(ValueError, 'both intersecting'):
            module.measure(m, t, case_id=CASE)
        m, t = packet()
        t['samples'][1]['frame'] = 61
        with self.assertRaisesRegex(ValueError, 'strictly increasing'):
            module.measure(m, t, case_id=CASE)
        m, t = packet()
        t['samples'].pop(1)
        with self.assertRaisesRegex(ValueError, 'before intersection entry'):
            module.measure(m, t, case_id=CASE)


if __name__ == '__main__':
    unittest.main()
