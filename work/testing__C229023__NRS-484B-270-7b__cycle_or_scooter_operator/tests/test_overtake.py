import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overtake import CASES, construct, measure_original, validate_scene


def scene(case):
    x = {'cell_id': 'C229023', 'actor': 'cycle_or_scooter_operator',
         'cycle_kind': case.cycle_kind, 'moped': False,
         'other_is_motor_vehicle': True, 'human_operator': True,
         'other_occupant_count': 2, 'other_occupant_ids': ['driver', 'passenger'],
         'human_powered': case.cycle_kind == 'bicycle', 'wheel_diameter_m': .65,
         'cycle_route_xy': [[-10, 0], [0, 2], [20, 2]],
         'motor_route_xy': [[0, 0], [10, 0], [20, 0]]}
    for field in ('jurisdiction', 'road_geometry', 'cycle_classification',
                  'wheel_arrangement', 'wheel_diameter', 'moped_exclusion',
                  'operator_control', 'motor_vehicle_classification',
                  'motor_vehicle_occupants', 'passing_side', 'route_geometry'):
        x[field + '_source_sha256'] = 'fixture-' + field
    return x


def rows(x, case):
    def rel(i):
        return -10 if i < 100 else (0 if i < 500 else
                                   10 if case.pass_policy == 'complete' else -2)
    return [{'original_frame': 600 + i, 'time_s': i / 20,
             **{field + '_sha256': 'fixture-' + field for field in
                ('source', 'cycle_motion', 'motor_motion', 'body_geometry',
                 'occupants', 'surface_clearance', 'route')},
             'road_geometry_source_sha256': x['road_geometry_source_sha256'],
             'cycle_kind': case.cycle_kind,
             'other_occupant_ids': x['other_occupant_ids'],
             'cycle_id': 'cycle', 'motor_id': 'motor',
             'cycle_station_m': i / 10 + rel(i), 'motor_station_m': i / 10,
             'cycle_speed_mps': 5, 'motor_speed_mps': 3,
             'surface_clearance_m': 1 if case.lateral_offset_m > 2 else .2}
            for i in range(900)]


class Adapter:
    def __init__(self, fail=False):
        self.events = []
        self.fail = fail

    def spawn_cycle(self, xy, kind):
        self.events.append(('spawn', 'cycle', kind))
        return 'cycle'

    def spawn_motor_vehicle(self, xy, occupants):
        self.events.append(('spawn', 'motor', tuple(occupants)))
        return 'motor'

    def set_motor_route(self, motor, route):
        self.events.append(('motor_route', motor))

    def set_pass_route(self, cycle, route, lateral_offset_m, pass_policy):
        self.events.append(('pass_route', pass_policy, lateral_offset_m))
        if self.fail:
            raise RuntimeError('pass route failed')

    def destroy(self, actor):
        self.events.append(('destroy', actor))


class OvertakeTest(unittest.TestCase):
    def test_five_exact_cases(self):
        for case in CASES:
            with self.subTest(case=case.case_id):
                x = scene(case)
                self.assertIsNone(validate_scene(x, case)['legal_judgment'])
                adapter = Adapter()
                self.assertIsNone(construct(adapter, x, case)['legal_judgment'])
                self.assertEqual(adapter.events[-1],
                                 ('pass_route', case.pass_policy, case.lateral_offset_m))
                out = measure_original(rows(x, case), x, case)
                self.assertEqual(out['frame_count'], 900)
                self.assertIsNone(out['safe_pass_judgment'])
                self.assertEqual(out['other_occupant_ids'], ['driver', 'passenger'])

    def test_classification_and_source_rejection(self):
        x = scene(CASES[0]); x['moped'] = True
        with self.assertRaisesRegex(ValueError, 'qualifying actor'):
            validate_scene(x, CASES[0])
        x = scene(CASES[0]); del x['motor_vehicle_occupants_source_sha256']
        with self.assertRaisesRegex(ValueError, 'original passing source'):
            validate_scene(x, CASES[0])

    def test_original_identity_clearance_and_pass_rejection(self):
        x = scene(CASES[0]); a = rows(x, CASES[0]); a[5]['motor_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            measure_original(a, x, CASES[0])
        a = rows(x, CASES[0]); a[5]['surface_clearance_m'] = -1
        with self.assertRaisesRegex(ValueError, 'collision/overlap'):
            measure_original(a, x, CASES[0])
        a = rows(x, CASES[0]); a[-1]['cycle_station_m'] = a[-1]['motor_station_m'] - 2
        with self.assertRaisesRegex(ValueError, 'clear ahead'):
            measure_original(a, x, CASES[0])

    def test_owned_cleanup(self):
        adapter = Adapter(fail=True)
        with self.assertRaisesRegex(RuntimeError, 'pass route failed'):
            construct(adapter, scene(CASES[0]), CASES[0])
        self.assertEqual(adapter.events[-2:], [('destroy', 'motor'), ('destroy', 'cycle')])


if __name__ == '__main__':
    unittest.main()
