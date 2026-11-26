import importlib.util
from pathlib import Path
import sys
import unittest


spec = importlib.util.spec_from_file_location(
    'flagger_zone', Path(__file__).resolve().parents[1] / 'flagger_zone.py')
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def scene(case):
    s = {'cell_id': 'C230235', 'actor': 'motor_vehicle_driver',
         'qualifying_vehicle': True, 'highway': True,
         'driver_id': 'd1', 'vehicle_id': 'v1', 'flagger_id': 'f1',
         'designated': case.designated, 'authorized': case.authorized,
         'signal': case.signal, 'response': case.response,
         'zone_rect_m': [0., 0., 50., 10.],
         'stop_line_xy': [10., 5.], 'flagger_xy': [10., 8.],
         'vehicle_route_xy': [[0., 5.], [50., 5.]],
         'signal_frame': 100, 'release_frame': 200}
    s.update({f + '_source_sha256': f + '-hash' for f in mod.SOURCES})
    return s


def rows(case):
    s = scene(case)
    out = []
    for i in range(900):
        r = {'original_frame': i, 'time_s': i / 20,
             'driver_id': 'd1', 'vehicle_id': 'v1', 'flagger_id': 'f1',
             'designated': case.designated, 'authorized': case.authorized,
             'signal': case.signal, 'signal_visible': True,
             'intended_vehicle_id': 'v1',
             'vehicle_speed_mps': 0. if case.response == 'stop' and
             100 <= i < 200 else 2., 'vehicle_xy': [i / 20, 5.]}
        r.update({f + '_source_sha256': s[f + '_source_sha256']
                  for f in mod.SOURCES})
        out.append(r)
    return out


class Adapter:
    def __init__(self, fail=False):
        self.fail = fail
        self.destroyed = []

    def spawn_flagger(self, xy):
        return 'flagger'

    def spawn_vehicle(self, xy):
        return 'vehicle'

    def set_signal(self, actor, signal, start, release):
        if self.fail:
            raise RuntimeError('signal failed')

    def set_route(self, actor, route, response):
        pass

    def destroy(self, actor):
        self.destroyed.append(actor)


class FlaggerZoneTests(unittest.TestCase):
    def test_all_cases_construct_and_measure(self):
        for case in mod.CASES:
            with self.subTest(case=case.name):
                self.assertEqual(mod.construct(Adapter(), scene(case), case)['owned'],
                                 ('flagger', 'vehicle'))
                r = mod.measure_original(rows(case), scene(case), case)
                self.assertEqual(r['active_signal_frames'], 100)
                self.assertIsNone(r['failure_or_refusal_judgment'])

    def test_independent_sources_required(self):
        case = mod.CASES[0]
        for field in mod.SOURCES:
            s = scene(case)
            del s[field + '_source_sha256']
            with self.subTest(field=field), self.assertRaises(ValueError):
                mod.validate_scene(s, case)

    def test_case_and_original_signal_change_rejected(self):
        case = mod.CASES[0]
        s = scene(case)
        s['authorized'] = False
        with self.assertRaises(ValueError):
            mod.validate_scene(s, case)
        original = rows(case)
        original[150]['signal_visible'] = False
        with self.assertRaisesRegex(ValueError, 'signal governance'):
            mod.measure_original(original, scene(case), case)

    def test_stop_and_continue_require_physical_response(self):
        stop = mod.CASES[1]
        original = rows(stop)
        original[150]['vehicle_speed_mps'] = 2.
        with self.assertRaisesRegex(ValueError, 'stop response'):
            mod.measure_original(original, scene(stop), stop)
        cont = mod.CASES[0]
        original = rows(cont)
        for i in range(100, 200):
            original[i]['vehicle_speed_mps'] = 0.
        with self.assertRaisesRegex(ValueError, 'continue response'):
            mod.measure_original(original, scene(cont), cont)

    def test_failed_signal_cleans_up(self):
        case = mod.CASES[0]
        a = Adapter(fail=True)
        with self.assertRaises(RuntimeError):
            mod.construct(a, scene(case), case)
        self.assertEqual(a.destroyed, ['vehicle', 'flagger'])

    def test_signal_interval_is_relative_to_original_start_frame(self):
        case = mod.CASES[1]
        original = rows(case)
        for row in original:
            row['original_frame'] += 1000
        measured = mod.measure_original(original, scene(case), case)
        self.assertEqual(measured['active_signal_frames'], 100)


if __name__ == '__main__':
    unittest.main()
