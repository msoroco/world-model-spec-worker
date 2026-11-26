import importlib.util
from pathlib import Path
import sys
import unittest


path = Path(__file__).resolve().parents[1] / 'grade_stand.py'
spec = importlib.util.spec_from_file_location('grade_stand', path)
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)


def scene(case):
    s = dict(cell_id='C276300', actor='motor_vehicle_driver',
             vehicle_qualifies=True, highway_public_access=True,
             highway_dedicated=True, grade_kind=case.grade,
             person_action=case.person_action,
             engine_off_request=case.engine_off,
             brake_set_request=case.brake_set,
             wheels_toward_request=case.wheels_toward,
             grade_percent=4 if case.grade == 'slope' else 0,
             curb_direction_xy=[0, -1],
             ego_route_xy=[[0, 0], [10, 0]],
             other_route_xy=[[20, 0], [30, 0]],
             person_route_xy=[[10, 0], [10, 5]],
             responsible_person_id='person', other_vehicle_id='other')
    for field in ('highway', 'vehicle', 'grade', 'curb_side', 'engine',
                  'brake_mechanics', 'front_wheels', 'responsible_person',
                  'person_actions', 'standing_interval', 'passenger_activity',
                  'other_vehicle_route'):
        s[field + '_source_sha256'] = 'a' * 64
    return s


def rows(case, s):
    output = []
    for i in range(900):
        row = dict(original_frame=100+i, time_s=i/20,
                   ego_id='ego', person_id='person', other_id='other',
                   person_action=case.person_action,
                   ego_speed_mps=2 if i < 100 else 0,
                   engine_rpm=0 if case.engine_off else 600,
                   engine_ignition_on=not case.engine_off,
                   brake_engaged=case.brake_set,
                   brake_torque_nm=100 if case.brake_set else 0,
                   front_wheel_vector_xy=[0, -1 if case.wheels_toward else 1],
                   person_distance_m=3 if i >= 200 and
                   case.person_action == 'depart' else 0,
                   grade_percent=s['grade_percent'], other_speed_mps=3,
                   grade_source_sha256=s['grade_source_sha256'])
        for field in ('frame', 'ego_motion', 'grade', 'curb_side', 'engine',
                      'brake_mechanics', 'front_wheels', 'responsible_person',
                      'person_actions', 'passenger_activity', 'other_vehicle_motion'):
            row[field + '_source_sha256'] = 'a' * 64
        output.append(row)
    return output


class Adapter:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def __getattr__(self, name):
        def invoke(*args):
            self.calls.append((name,args))
            if name == 'spawn_person' and self.fail:
                return None
            if name.startswith('spawn_'):
                return name
        return invoke


class GradeTests(unittest.TestCase):
    def test_all_cases_construct_and_measure(self):
        for case in probe.CASES:
            with self.subTest(case=case.name):
                s = scene(case)
                adapter = Adapter()
                probe.construct(adapter, s, case)
                self.assertIn('set_front_wheels', [x[0] for x in adapter.calls])
                result = probe.measure_original(rows(case,s), s, case)
                self.assertEqual(result['standing_frame_count'], 800)
                self.assertIsNone(result['effective_brake_judgment'])

    def test_missing_source_and_preparation_rejected(self):
        case = probe.CASES[0]
        s = scene(case);data = rows(case,s)
        del data[2]['front_wheels_source_sha256']
        with self.assertRaisesRegex(ValueError, 'source missing'):
            probe.measure_original(data,s,case)
        data = rows(case,s)
        data[120]['brake_engaged'] = False
        with self.assertRaisesRegex(ValueError, 'preparation not measured'):
            probe.measure_original(data,s,case)
        data = rows(case,s)
        data[120]['engine_source_sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'source join differs: engine'):
            probe.measure_original(data,s,case)

    def test_highway_source_and_cleanup(self):
        case = probe.CASES[0]
        s = scene(case)
        s['highway_public_access'] = False
        with self.assertRaisesRegex(ValueError, 'highway vehicle'):
            probe.validate_scene(s,case)
        adapter = Adapter(fail=True)
        with self.assertRaisesRegex(ValueError, 'person spawn failed'):
            probe.construct(adapter,scene(case),case)
        self.assertEqual([x[0] for x in adapter.calls][-2:], ['destroy','destroy'])


if __name__ == '__main__':
    unittest.main()
