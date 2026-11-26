import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location('parked_lamps',
    Path(__file__).resolve().parents[1] / 'parked_lamps.py')
mod = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


FIELDS = mod.SCENE_SOURCES
ROW_FIELDS = mod.ROW_SOURCES


def scene(case):
    value = {'cell_id': 'C229398', 'actor': 'motor_vehicle_driver',
             'qualifying_vehicle': True, 'highway': True,
             'vehicle_id': 'v1', 'night': case.night,
             'lawful_park': case.lawful_park,
             'lamp_mode': case.lamp_mode,
             'auxiliary_lamp': case.auxiliary_lamp,
             'parking_route_xy': [[0., 0.], [1., 0.]],
             'curb_distance_m': .2, 'vehicle_width_m': 1.8,
             'park_start_frame': 100}
    value.update({field + '_source_sha256': field + '-source' for field in FIELDS})
    return value


def rows(case):
    base = scene(case)
    out = []
    for i in range(900):
        row = {'original_frame': i, 'time_s': i / 20,
               'vehicle_id': 'v1', 'night': case.night,
               'lawful_park': case.lawful_park,
               'lamp_mode': case.lamp_mode,
               'auxiliary_lamp': case.auxiliary_lamp,
               'speed_mps': 1. if i < 100 else 0.,
               'beam_aim_deg': 2. if case.lamp_mode == 'undimmed' else -2.}
        row.update({field + '_source_sha256':
                    base.get(field + '_source_sha256', field + '-source')
                    for field in ROW_FIELDS})
        out.append(row)
    return out


class Adapter:
    def __init__(self, fail=False):
        self.fail = fail
        self.destroyed = []
        self.calls = []

    def spawn_vehicle(self, point):
        self.calls.append(('spawn', point))
        return 'vehicle'

    def set_parking_route(self, actor, route, start):
        self.calls.append(('route', actor, start))

    def set_displayed_lamps(self, actor, mode):
        self.calls.append(('displayed', actor, mode))
        if self.fail:
            raise RuntimeError('lamp command failed')

    def set_auxiliary_lamps(self, actor, mode):
        self.calls.append(('auxiliary', actor, mode))

    def destroy(self, actor):
        self.destroyed.append(actor)


class ParkedLampsTests(unittest.TestCase):
    def test_all_exact_cases_construct_and_measure(self):
        for case in mod.CASES:
            with self.subTest(case=case.name):
                adapter = Adapter()
                self.assertEqual(mod.construct(adapter, scene(case), case)['owned'],
                                 ('vehicle',))
                result = mod.measure_original(rows(case), scene(case), case)
                self.assertEqual(result['parked_frames'], 800)
                self.assertEqual(result['all_parked_frames_dimmed'],
                                 case.lamp_mode == 'dimmed')
                self.assertIsNone(result['legal_judgment'])

    def test_distinct_prerequisites_are_source_gated(self):
        case = mod.CASES[0]
        for field in FIELDS:
            bad = scene(case)
            bad.pop(field + '_source_sha256')
            with self.subTest(field=field), self.assertRaises(ValueError):
                mod.validate_scene(bad, case)

    def test_no_day_night_or_auxiliary_substitution(self):
        case = mod.CASES[0]
        for changed in ({'night': False}, {'lawful_park': False},
                        {'auxiliary_lamp': 'cowl'}, {'lamp_mode': 'dimmed'}):
            bad = scene(case)
            bad.update(changed)
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                mod.validate_scene(bad, case)

    def test_original_measurement_rejects_moving_parked_vehicle(self):
        case = mod.CASES[0]
        measured = rows(case)
        measured[200]['speed_mps'] = 2.
        with self.assertRaisesRegex(ValueError, 'not physically parked'):
            mod.measure_original(measured, scene(case), case)

    def test_original_measurement_rejects_state_or_source_change(self):
        case = mod.CASES[0]
        for key, value in (('lamp_mode', 'dimmed'),
                           ('nighttime_source_sha256', 'wrong')):
            measured = rows(case)
            measured[200][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                mod.measure_original(measured, scene(case), case)

    def test_failed_lamp_command_cleans_up(self):
        case = mod.CASES[0]
        adapter = Adapter(fail=True)
        with self.assertRaises(RuntimeError):
            mod.construct(adapter, scene(case), case)
        self.assertEqual(adapter.destroyed, ['vehicle'])

    def test_original_parking_interval_relative_to_capture_start(self):
        case = mod.CASES[0]
        measured = rows(case)
        for row in measured:
            row['original_frame'] += 1000
        self.assertEqual(mod.measure_original(measured, scene(case), case)['parked_frames'], 800)


if __name__ == '__main__':
    unittest.main()
