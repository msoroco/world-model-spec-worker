import importlib.util
from pathlib import Path
import sys
import unittest


spec = importlib.util.spec_from_file_location(
    'school_uturn', Path(__file__).resolve().parents[1] / 'school_uturn.py')
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def scene(case):
    s = {'cell_id': 'C255863', 'actor': 'motor_vehicle_driver',
         'qualifying_vehicle': True, 'highway': True,
         'driver_id': 'd1', 'vehicle_id': 'v1',
         'children_present': case.children_present,
         'school_session': case.school_session,
         'operation_window': case.operation_window,
         'beacon_operational': case.beacon_operational,
         'beacon_flashing': case.beacon_flashing,
         'sign_limit_active': case.sign_limit_active,
         'crossing_zone_rect_m': [0., 0., 30., 30.],
         'school_property_rect_m': [50., 50., 80., 80.],
         'nonadjacent_street': True, 'pupil_route_designated': True,
         'reversal_route_xy': [[5., 5.], [10., 10.], [5., 15.]],
         'turn_start_frame': 100, 'turn_end_frame': 200,
         'local_datetime': '2026-11-23T08:15:00-08:00',
         'school_calendar_ref': 'district calendar',
         'operation_schedule_ref': 'school schedule',
         'children': [{'id': 'c1', 'xy': [10., 10.] if case.children_present
                       else [40., 40.]}]}
    s.update({f + '_source_sha256': f + '-hash' for f in mod.SOURCES})
    return s


def rows(case):
    s = scene(case)
    out = []
    for i in range(900):
        r = {'original_frame': i, 'time_s': i / 20,
             'driver_id': 'd1', 'vehicle_id': 'v1',
             'vehicle_xy': [10., 10.],
             'vehicle_heading_deg': 180. * min(1., max(0., (i - 100) / 100)),
             'travel_direction': 'forward',
             'children_xy': {'c1': s['children'][0]['xy']}}
        r.update({n: getattr(case, n) for n in
                  ('children_present', 'school_session', 'operation_window',
                   'beacon_operational', 'beacon_flashing',
                   'sign_limit_active')})
        r.update({f + '_source_sha256': s[f + '_source_sha256']
                  for f in mod.SOURCES})
        out.append(r)
    return out


class Adapter:
    def __init__(self, fail=False):
        self.fail = fail
        self.destroyed = []

    def spawn_vehicle(self, xy):
        return 'vehicle'

    def spawn_child(self, child_id, xy):
        return child_id

    def set_reversal_route(self, actor, route, start, end):
        if self.fail:
            raise RuntimeError('route failed')

    def set_beacon(self, operational, flashing):
        pass

    def destroy(self, actor):
        self.destroyed.append(actor)


class SchoolUTurnTests(unittest.TestCase):
    def test_all_exception_cases_construct_and_measure(self):
        for case in mod.CASES:
            with self.subTest(case=case.name):
                self.assertEqual(mod.construct(Adapter(), scene(case), case)['owned'],
                                 ('vehicle', 'c1'))
                r = mod.measure_original(rows(case), scene(case), case)
                self.assertEqual(r['turn_frames'], 101)
                self.assertGreaterEqual(r['heading_span_deg'], 150.)
                self.assertIsNone(r['uturn_legal_judgment'])

    def test_all_independent_sources_required(self):
        case = mod.CASES[0]
        for field in mod.SOURCES:
            s = scene(case)
            del s[field + '_source_sha256']
            with self.subTest(field=field), self.assertRaises(ValueError):
                mod.validate_scene(s, case)

    def test_calendar_and_children_not_inferred(self):
        case = mod.CASES[0]
        s = scene(case)
        s['school_calendar_ref'] = ''
        with self.assertRaises(ValueError):
            mod.validate_scene(s, case)
        s = scene(case)
        s['children'][0]['xy'] = [40., 40.]
        with self.assertRaises(ValueError):
            mod.validate_scene(s, case)

    def test_original_exception_and_reversal_change_rejected(self):
        case = mod.CASES[0]
        original = rows(case)
        original[150]['beacon_flashing'] = False
        with self.assertRaises(ValueError):
            mod.measure_original(original, scene(case), case)
        original = rows(case)
        for row in original:
            row['vehicle_heading_deg'] = 0.
        with self.assertRaisesRegex(ValueError, 'reversal not realized'):
            mod.measure_original(original, scene(case), case)

    def test_failed_route_cleans_actors(self):
        case = mod.CASES[0]
        a = Adapter(fail=True)
        with self.assertRaises(RuntimeError):
            mod.construct(a, scene(case), case)
        self.assertEqual(a.destroyed, ['c1', 'vehicle'])


if __name__ == '__main__':
    unittest.main()
