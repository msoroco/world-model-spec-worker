import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rail_left import CASES, FOOT_M, construct, measure_original, validate_scene


def scene(case):
    x = {'cell_id': 'C204980', 'actor': 'motor_vehicle_driver',
         'rail_grade_crossing': True,
         'stationary_rail_carrier_person_or_property': True,
         'streetcar_rail': False, 'one_way_highway': case.one_way,
         'crossing_near_station_m': 0, 'crossing_far_station_m': 5,
         'route_xy': [[-60, 0], [-30, 0], [10, 0]],
         'centerline_point_xy': [0, 0], 'centerline_heading_xy': [1, 0]}
    for field in ('jurisdiction', 'highway_status', 'one_way_status', 'vehicle',
                  'driver_control', 'rail_carrier', 'rail_grade', 'streetcar_exclusion',
                  'crossing_near_edge', 'crossing_far_edge', 'centerline',
                  'route', 'body_reference'):
        x[field + '_source_sha256'] = 'fixture-' + field
    return x


def rows(x, case):
    leading = -case.target_leading_distance_ft * FOOT_M
    return [{'original_frame': 900 + i, 'time_s': i / 20,
             **{field + '_sha256': 'fixture-' + field for field in
                ('source', 'body_geometry', 'motion', 'crossing_geometry',
                 'centerline', 'highway_classification', 'rail_carrier')},
             'crossing_near_edge_source_sha256': x['crossing_near_edge_source_sha256'],
             'centerline_source_sha256': x['centerline_source_sha256'],
             'one_way_highway': case.one_way, 'ego_id': 'ego',
             'leading_body_station_m': leading,
             'trailing_body_station_m': leading - 3,
             'body_leftmost_lateral_m': 1 if case.left_side else -1,
             'body_rightmost_lateral_m': -1 if case.left_side else -3,
             'ego_speed_mps': 5}
            for i in range(900)]


class Adapter:
    def __init__(self, fail=False):
        self.events = []
        self.fail = fail

    def spawn_vehicle(self, position, role):
        self.events.append(('spawn', role))
        return role

    def set_rail_route(self, ego, route, station, left_side):
        self.events.append(('route', station, left_side))
        if self.fail:
            raise RuntimeError('route failed')

    def destroy(self, actor):
        self.events.append(('destroy', actor))


class RailLeftTest(unittest.TestCase):
    def test_six_exact_cases(self):
        for case in CASES:
            with self.subTest(case=case.case_id):
                x = scene(case)
                self.assertIsNone(validate_scene(x, case)['legal_judgment'])
                self.assertIsNone(construct(Adapter(), x, case)['legal_judgment'])
                measured = measure_original(rows(x, case), x, case)
                self.assertEqual(measured['frame_count'], 900)
                self.assertAlmostEqual(measured['observed_leading_body_distance_ft'],
                                       case.target_leading_distance_ft)
                self.assertIsNone(measured['legal_left_side_judgment'])

    def test_rail_grade_and_exception_rejections(self):
        x = scene(CASES[0]); x['streetcar_rail'] = True
        with self.assertRaisesRegex(ValueError, 'qualifying railroad'):
            validate_scene(x, CASES[0])
        x = scene(CASES[0]); x['one_way_highway'] = True
        with self.assertRaisesRegex(ValueError, 'one-way exception'):
            validate_scene(x, CASES[0])

    def test_original_identity_distance_and_source_rejections(self):
        x = scene(CASES[0]); a = rows(x, CASES[0]); a[5]['ego_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            measure_original(a, x, CASES[0])
        a = rows(x, CASES[0]); a[5]['rail_carrier_sha256'] = ''
        with self.assertRaisesRegex(ValueError, 'original source missing'):
            measure_original(a, x, CASES[0])
        a = rows(x, CASES[0]); a[100]['leading_body_station_m'] -= 1
        with self.assertRaisesRegex(ValueError, 'observed distance differs'):
            measure_original(a, x, CASES[0])

    def test_owned_cleanup(self):
        adapter = Adapter(fail=True)
        with self.assertRaisesRegex(RuntimeError, 'route failed'):
            construct(adapter, scene(CASES[0]), CASES[0])
        self.assertEqual(adapter.events[-1], ('destroy', 'ego'))


if __name__ == '__main__':
    unittest.main()
