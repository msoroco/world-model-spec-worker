import importlib.util
from pathlib import Path
import sys
import unittest


path = Path(__file__).resolve().parents[1] / 'lamp_direction.py'
spec = importlib.util.spec_from_file_location('lamp_direction', path)
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)


def scene(case):
    s = dict(cell_id='C230294', actor='motor_vehicle_driver',
             nevada_jurisdiction=True, public_highway=True,
             vehicle_class='ordinary_motor_vehicle', parked=False,
             device_directs=case.device_directs,
             lamps_on_request=case.lamps_on, context=case.context,
             official_device=case.device_directs, device_message='use_lamps',
             device_operative=case.device_directs,
             device_governs_route=case.device_directs,
             required_lamp_ids=['headlamp_left', 'headlamp_right'],
             route_xy=[[0, 0], [20, 0]], device_xy=[5, 2],
             sunset_time_s=60000, sunrise_time_s=20000,
             clock_time_s=62000 if case.context == 'night' else 30000,
             visibility_ahead_m=250 if case.context == 'poor_visibility' else 400)
    for field in ('jurisdiction', 'highway', 'vehicle_class', 'parking_status',
                  'required_lamp_provisions', 'device_authority',
                  'device_geometry', 'device_message', 'device_timing',
                  'route', 'sunset_sunrise', 'clock', 'visibility'):
        s[field + '_source_sha256'] = 'a' * 64
    return s


def rows(case, s):
    output = []
    for i in range(900):
        row = dict(original_frame=100+i, time_s=i/20,
                   vehicle_id='ego', speed_mps=5,
                   device_directs=case.device_directs, context=case.context,
                   lamp_states={x: case.lamps_on for x in s['required_lamp_ids']},
                   vehicle_class_source_sha256=s['vehicle_class_source_sha256'])
        for field in ('frame', 'vehicle_motion', 'lamp_state',
                      'device_authority', 'device_message', 'device_timing',
                      'sunset_sunrise', 'clock', 'visibility'):
            row[field + '_source_sha256'] = 'a' * 64
        output.append(row)
    return output


class Adapter:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def __getattr__(self, name):
        def invoke(*args):
            self.calls.append((name, args))
            if name == 'spawn_vehicle':
                return None if self.fail else 'ego'
        return invoke


class LampTests(unittest.TestCase):
    def test_all_cases_construct_and_measure(self):
        for case in probe.CASES:
            with self.subTest(case=case.name):
                s = scene(case)
                adapter = Adapter()
                probe.construct(adapter, s, case)
                self.assertEqual([x[0] for x in adapter.calls].count('set_lamp'), 2)
                measured = probe.measure_original(rows(case, s), s, case)
                self.assertEqual(measured['lamp_on_frame_counts']['headlamp_left'],
                                 900 if case.lamps_on else 0)
                self.assertIsNone(measured['legal_judgment'])

    def test_missing_source_and_lamp_rejected(self):
        case = probe.CASES[0]
        s = scene(case)
        records = rows(case, s)
        del records[2]['device_timing_source_sha256']
        with self.assertRaisesRegex(ValueError, 'source missing'):
            probe.measure_original(records, s, case)
        records = rows(case, s)
        del records[2]['lamp_states']['headlamp_right']
        with self.assertRaisesRegex(ValueError, 'lamp states missing'):
            probe.measure_original(records, s, case)

    def test_unofficial_device_and_spawn_rejected(self):
        case = probe.CASES[0]
        s = scene(case)
        s['official_device'] = False
        with self.assertRaisesRegex(ValueError, 'official lamp direction'):
            probe.validate_scene(s, case)
        with self.assertRaisesRegex(ValueError, 'vehicle spawn failed'):
            probe.construct(Adapter(fail=True), scene(case), case)


if __name__ == '__main__':
    unittest.main()
