import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nonthrough_yield import CASES, construct, measure_frozen_windows, measure_original, validate_scene


def scene():
    x = {'cell_id': 'C158208', 'actor': 'motor_vehicle_driver',
         'ego_yield_sign': True, 'non_through_highway': True,
         'officer_controls': False, 'signal_controls': False,
         'other_vehicle_obligated_to_stop_or_yield': False,
         'ego_route_xy': [[-20, 0], [-5, 0], [5, 0]],
         'through_spawn_xy': [0, -20], 'stop_reference_station_m': -2,
         'intersection_entry_station_m': 1}
    for key in ('jurisdiction', 'intersection_geometry', 'all_entrance_controls',
                'ego_yield_sign', 'non_through_classification', 'stop_reference',
                'sightlines', 'through_vehicle_exemption', 'officer_control',
                'signal_control', 'ego_vehicle'):
        x[key + '_source_sha256'] = 'fixture-' + key
    return x


def rows(x, case):
    return [{'original_frame': 200 + i, 'time_s': i / 20,
             **{key + '_sha256': 'fixture-' + key for key in
                ('source', 'ego_motion', 'other_motion', 'body_geometry',
                 'controls', 'sightlines', 'entrance_controls')},
             'intersection_geometry_source_sha256': x['intersection_geometry_source_sha256'],
             'all_entrance_controls_source_sha256': x['all_entrance_controls_source_sha256'],
             'ego_id': 'ego', 'other_id': 'other',
             'other_obligated_to_stop_or_yield': False,
             'officer_controls': False, 'signal_controls': False,
             'ego_speed_mps': 8 if i < 90 else (4 if case.approach_policy == 'slow' else 8),
             'ego_leading_station_m': -3 if i < 120 else 2,
             'other_center_station_m': case.traffic_station_m - i * .01,
             'other_min_vertex_station_m': case.traffic_station_m - 2 - i * .01,
             'other_phase': case.through_phase,
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

    def set_other_phase(self, other, phase, station):
        self.events.append(('other', phase, station))

    def destroy(self, actor):
        self.events.append(('destroy', actor))


class NonThroughYieldTest(unittest.TestCase):
    def test_four_exact_cases(self):
        for case in CASES:
            with self.subTest(case=case.case_id):
                x = scene()
                self.assertIsNone(validate_scene(x, case)['legal_judgment'])
                adapter = Adapter()
                self.assertIsNone(construct(adapter, x, case)['legal_judgment'])
                self.assertEqual(adapter.events[-1], ('other', case.through_phase, case.traffic_station_m))
                measured = measure_original(rows(x, case), x, case)
                self.assertEqual(measured['frame_count'], 900)
                self.assertEqual(measured['first_original_entry_frame'], 320)
                self.assertIsNone(measured['immediate_hazard_judgment'])

    def test_scene_and_source_rejections(self):
        x = scene()
        x['other_vehicle_obligated_to_stop_or_yield'] = True
        with self.assertRaisesRegex(ValueError, 'obligation'):
            validate_scene(x, CASES[0])
        x = scene()
        del x['all_entrance_controls_source_sha256']
        with self.assertRaisesRegex(ValueError, 'original scene source'):
            validate_scene(x, CASES[0])

    def test_original_join_and_crossing_rejections(self):
        x = scene()
        a = rows(x, CASES[0]); a[5]['other_id'] = 'other2'
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            measure_original(a, x, CASES[0])
        a = rows(x, CASES[0]); a[5]['sightlines_sha256'] = ''
        with self.assertRaisesRegex(ValueError, 'original source missing'):
            measure_original(a, x, CASES[0])
        a = rows(x, CASES[0])
        for row in a: row['ego_leading_station_m'] = -3
        with self.assertRaisesRegex(ValueError, 'entry absent'):
            measure_original(a, x, CASES[0])

    def test_owned_cleanup(self):
        adapter = Adapter(fail=True)
        with self.assertRaisesRegex(RuntimeError, 'approach failed'):
            construct(adapter, scene(), CASES[0])
        self.assertEqual(adapter.events[-2:], [('destroy', 'other'), ('destroy', 'ego')])

    def test_frozen_measurement_windows_and_missing_clearance(self):
        x = scene()
        case = CASES[1]
        source = rows(x, case)
        for i, row in enumerate(source):
            row['ego_full_body_overlap'] = 120 <= i <= 200
            row['ego_full_body_cleared'] = i >= 201
            row['traffic_reference_event'] = i == 119
        result = measure_frozen_windows(source, x, case)
        self.assertEqual(result['frozen_windows']['first_clear_frame'], 401)
        self.assertEqual(result['frozen_observables']['counterpart_center_station_first_m'],
                         8 - 119 * .01)
        source[201]['ego_full_body_cleared'] = False
        with self.assertRaisesRegex(ValueError, 'containment history'):
            measure_frozen_windows(source, x, case)


if __name__ == '__main__':
    unittest.main()
