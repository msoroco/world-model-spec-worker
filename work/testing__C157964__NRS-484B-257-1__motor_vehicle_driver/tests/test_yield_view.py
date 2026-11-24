import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from yield_view import CASES, construct, measure_original, validate_site


def site(case):
    x = {'cell_id': 'C157964', 'actor': 'motor_vehicle_driver',
         'yield_sign_present': True, 'stop_line_present': False,
         'near_crosswalk_present': False, 'officer_controls': case.officer_controls,
         'signal_controls': False, 'nearest_view_station_m': 0,
         'physical_reference_station_m': 2, 'route_xy': [[-20, 0], [-4, 0], [4, 0]],
         'through_spawn_xy': [0, -20]}
    for key in ('jurisdiction', 'yield_sign', 'stop_line_absence', 'crosswalk_absence',
                'nearest_view_location', 'through_highway', 'sight_observation',
                'officer_control', 'traffic_signal_control', 'ego_vehicle'):
        x[key + '_source_sha256'] = 'fixture-' + key
    return x


def rows(x, case):
    return [{'original_frame': 300 + i, 'time_s': i / 20,
             **{key + '_sha256': 'fixture-' + key for key in
                ('source', 'ego_motion', 'through_motion', 'body_geometry',
                 'reference', 'sight', 'control')},
             'reference_source_sha256': x['nearest_view_location_source_sha256'],
             'officer_controls': case.officer_controls, 'signal_controls': False,
             'stop_line_present': False, 'near_crosswalk_present': False,
             'ego_id': 'ego', 'through_id': 'through',
             'ego_speed_mps': 8 if i < 80 else (0 if case.approach_policy == 'stop' and i < 110 else 4),
             'through_center_station_m': 12 - i * .01,
             'through_min_vertex_station_m': 9 - i * .01,
             'ego_leading_station_m': -2 if i < 120 else 3,
             'through_phase': case.through_state,
             'ego_across_or_within': i >= 120}
            for i in range(900)]


class Adapter:
    def __init__(self, fail=False):
        self.events = []
        self.fail = fail

    def spawn_vehicle(self, position, role):
        self.events.append(('spawn', role))
        return role

    def set_yield_approach(self, ego, route, reference, policy):
        self.events.append(('approach', policy))
        if self.fail:
            raise RuntimeError('approach failed')

    def set_through_phase(self, through, phase):
        self.events.append(('phase', phase))

    def set_officer_control(self, active):
        self.events.append(('officer', active))

    def destroy(self, actor):
        self.events.append(('destroy', actor))


class YieldViewTest(unittest.TestCase):
    def test_four_exact_cases(self):
        for case in CASES:
            with self.subTest(case=case.case_id):
                x = site(case)
                self.assertIsNone(validate_site(x, case)['legal_judgment'])
                self.assertIsNone(construct(Adapter(), x, case)['legal_judgment'])
                out = measure_original(rows(x, case), x, case)
                self.assertEqual(out['frame_count'], 900)
                self.assertEqual(out['first_physical_reference_crossing_frame'], 420)
                self.assertIsNone(out['immediate_hazard_judgment'])

    def test_hierarchy_and_control_rejection(self):
        case = CASES[0]
        x = site(case)
        x['near_crosswalk_present'] = True
        with self.assertRaisesRegex(ValueError, 'reference hierarchy'):
            validate_site(x, case)
        x = site(case)
        x['officer_controls'] = True
        with self.assertRaisesRegex(ValueError, 'governing-control'):
            validate_site(x, case)

    def test_original_source_identity_and_crossing_rejection(self):
        case = CASES[0]
        x = site(case)
        a = rows(x, case)
        a[5]['through_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            measure_original(a, x, case)
        a = rows(x, case)
        a[5]['sight_sha256'] = ''
        with self.assertRaisesRegex(ValueError, 'original source missing'):
            measure_original(a, x, case)
        a = rows(x, case)
        for row in a:
            row['ego_leading_station_m'] = -2
        with self.assertRaisesRegex(ValueError, 'never crossed'):
            measure_original(a, x, case)

    def test_owned_cleanup(self):
        adapter = Adapter(fail=True)
        with self.assertRaisesRegex(RuntimeError, 'approach failed'):
            construct(adapter, site(CASES[0]), CASES[0])
        self.assertEqual(adapter.events[-2:], [('destroy', 'through'), ('destroy', 'ego')])


if __name__ == '__main__':
    unittest.main()
