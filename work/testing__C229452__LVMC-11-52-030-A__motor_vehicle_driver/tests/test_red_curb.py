import importlib.util
from pathlib import Path
import sys
import unittest


path = Path(__file__).resolve().parents[1] / 'red_curb.py'
spec = importlib.util.spec_from_file_location('red_curb', path)
red = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = red
spec.loader.exec_module(red)


def scene(case):
    s = dict(cell_id='C229452', actor='motor_vehicle_driver',
             municipal_jurisdiction=True, red_curb_paint=True,
             vehicle_kind=case.vehicle_kind, sign=case.sign,
             activity=case.activity, purpose=case.purpose,
             mail_dropbox_adjacent=True, curb_segment_id='curb-1',
             parking_route_xy=[[0, 0], [3, 0]])
    for field in ('jurisdiction', 'red_curb', 'governed_location',
                  'parking_position', 'vehicle_classification', 'sign',
                  'activity', 'purpose', 'attendance', 'engine',
                  'traffic_conflict', 'police_direction', 'device_direction',
                  'vehicle_status', 'mail_dropbox', 'mail_activity'):
        s[field + '_source_sha256'] = 'a' * 64
    return s


def events(case, s):
    output = []
    for t in (0, case.duration_s):
        event = dict(vehicle_id='ego', original_time_s=t,
                     vehicle_speed_mps=0, halted=True,
                     activity=case.activity, purpose=case.purpose,
                     attended=False, engine_running=False,
                     red_curb_source_sha256=s['red_curb_source_sha256'])
        for field in ('event', 'vehicle_motion', 'curb_position', 'activity',
                      'attendance', 'engine', 'sign', 'purpose'):
            event[field + '_source_sha256'] = 'a' * 64
        output.append(event)
    return output


class Adapter:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def __getattr__(self, name):
        def invoke(*args):
            self.calls.append((name, args))
            if name == 'spawn_vehicle':
                return None if self.fail else 'vehicle-1'
        return invoke


class RedCurbTests(unittest.TestCase):
    def test_all_cases_construct_and_measure(self):
        for case in red.CASES:
            with self.subTest(case=case.name):
                s = scene(case)
                adapter = Adapter()
                red.construct(adapter, s, case)
                self.assertIn('mark_red_curb', [x[0] for x in adapter.calls])
                self.assertIn('set_halt_activity', [x[0] for x in adapter.calls])
                measured = red.measure_activity(events(case, s), s, case)
                self.assertEqual(measured['original_duration_s'], case.duration_s)
                self.assertIsNone(measured['legal_judgment'])

    def test_missing_original_source_rejected(self):
        case = red.CASES[2]
        s = scene(case)
        source = events(case, s)
        del source[-1]['sign_source_sha256']
        with self.assertRaisesRegex(ValueError, 'source missing'):
            red.measure_activity(source, s, case)

    def test_boundary_and_exception_source_rejected(self):
        case = red.CASES[4]
        s = scene(case)
        source = events(case, s)
        source[-1]['original_time_s'] = 1800
        with self.assertRaisesRegex(ValueError, 'boundary duration'):
            red.measure_activity(source, s, case)
        mail = red.CASES[-1]
        s = scene(mail)
        del s['mail_activity_source_sha256']
        with self.assertRaisesRegex(ValueError, 'mail box/activity'):
            red.validate_scene(s, mail)

    def test_spawn_failure(self):
        case = red.CASES[0]
        with self.assertRaisesRegex(ValueError, 'vehicle spawn failed'):
            red.construct(Adapter(fail=True), scene(case), case)


if __name__ == '__main__':
    unittest.main()
