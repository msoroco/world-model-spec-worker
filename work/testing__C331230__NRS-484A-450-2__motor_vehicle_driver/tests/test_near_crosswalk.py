import importlib.util
from pathlib import Path
import sys
import unittest


spec = importlib.util.spec_from_file_location(
    'near_crosswalk', Path(__file__).resolve().parents[1] / 'near_crosswalk.py')
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def scene(case):
    s = {'cell_id': 'C331230', 'actor': 'motor_vehicle_driver',
         'qualifying_vehicle': True, 'driver_control': True,
         'driver_id': 'd1', 'vehicle_id': 'v1',
         'marked': case.marked, 'halt': case.halt,
         'stop_sign_governs': True,
         'intersection_rect_m': [10., 0., 30., 20.],
         'near_crosswalk_rect_m': [8., 0., 10., 20.],
         'opposing_sidewalk_left_xy': [8., 0.],
         'opposing_sidewalk_right_xy': [8., 20.],
         'vehicle_route_xy': [[0., 10.], [20., 10.]],
         'crosswalk_entry_frame': 200}
    s.update({f + '_source_sha256': f + '-hash' for f in mod.SOURCES})
    return s


def rows(case):
    s = scene(case)
    out = []
    for i in range(900):
        x = 1. if i < 200 else 9. if i < 300 else 15.
        r = {'original_frame': i, 'time_s': i / 20,
             'driver_id': 'd1', 'vehicle_id': 'v1',
             'marked': case.marked, 'stop_sign_governs': True,
             'vehicle_front_xy': [x, 10.],
             'speed_mps': 0. if case.halt and i == 150 else 1.}
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

    def set_stop_sign(self, governs):
        pass

    def set_crosswalk(self, rect, marked):
        pass

    def set_vehicle_route(self, vehicle, route, halt, entry):
        if self.fail:
            raise RuntimeError('route failed')

    def destroy(self, actor):
        self.destroyed.append(actor)


class CrosswalkTests(unittest.TestCase):
    def test_all_cases_construct_and_measure(self):
        for case in mod.CASES:
            with self.subTest(case=case.name):
                self.assertEqual(mod.construct(Adapter(), scene(case), case)['owned'],
                                 ('vehicle',))
                result = mod.measure_original(rows(case), scene(case), case)
                self.assertEqual(result['crosswalk_entry_frame'], 200)
                self.assertEqual(result['stopped_before_entry'], case.halt)
                self.assertIsNone(result['stop_before_crosswalk_judgment'])

    def test_all_sources_required(self):
        case = mod.CASES[0]
        for field in mod.SOURCES:
            s = scene(case)
            del s[field + '_source_sha256']
            with self.subTest(field=field), self.assertRaises(ValueError):
                mod.validate_scene(s, case)

    def test_governance_and_original_speed_change_rejected(self):
        case = mod.CASES[0]
        s = scene(case)
        s['stop_sign_governs'] = False
        with self.assertRaises(ValueError):
            mod.validate_scene(s, case)
        original = rows(case)
        original[150]['speed_mps'] = 1.
        with self.assertRaisesRegex(ValueError, 'stop-versus-rolling'):
            mod.measure_original(original, scene(case), case)

    def test_original_source_and_crossing_change_rejected(self):
        case = mod.CASES[0]
        original = rows(case)
        original[200]['stop_sign_orientation_source_sha256'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'original source changed'):
            mod.measure_original(original, scene(case), case)
        original = rows(case)
        for row in original:
            row['vehicle_front_xy'] = [1., 10.]
        with self.assertRaises(ValueError):
            mod.measure_original(original, scene(case), case)

    def test_failed_route_cleans_vehicle(self):
        case = mod.CASES[0]
        a = Adapter(fail=True)
        with self.assertRaises(RuntimeError):
            mod.construct(a, scene(case), case)
        self.assertEqual(a.destroyed, ['vehicle'])

    def test_near_side_and_sidewalk_geometry_is_real(self):
        case = mod.CASES[2]
        shifted = scene(case)
        shifted['near_crosswalk_rect_m'] = [31., 0., 33., 20.]
        with self.assertRaisesRegex(ValueError, 'near-side'):
            mod.validate_scene(shifted, case)
        disconnected = scene(case)
        disconnected['opposing_sidewalk_left_xy'] = [8., 3.]
        with self.assertRaisesRegex(ValueError, 'sidewalks'):
            mod.validate_scene(disconnected, case)

    def test_spawn_stationary_is_not_a_stop_and_entry_timing_is_observed(self):
        case = mod.CASES[1]
        original = rows(case)
        original[0]['speed_mps'] = 0.
        measured = mod.measure_original(original, scene(case), case)
        self.assertFalse(measured['stopped_before_entry'])
        changed = rows(case)
        changed[200]['vehicle_front_xy'] = [1., 10.]
        changed[201]['vehicle_front_xy'] = [9., 10.]
        self.assertEqual(mod.measure_original(changed, scene(case), case)['crosswalk_entry_frame'], 201)


if __name__ == '__main__':
    unittest.main()
