import importlib.util
from pathlib import Path
import sys
import unittest


path = Path(__file__).resolve().parents[1] / 'one_way_direction.py'
spec = importlib.util.spec_from_file_location('one_way_direction', path)
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)


def scene(case):
    s = dict(cell_id='C147311', actor='motor_vehicle_driver',
             motor_vehicle=True, driver_in_physical_control=True,
             public_highway=True, highway_dedicated=True,
             one_way_designated=True, lane_count=2, lane=case.lane,
             direction=case.direction, sign_authorized=True,
             signposted=True, sign_governs_route=True,
             designated_unit_xy=[1, 0], lane_ids=[1, 2],
             sign_xy=[0, 2], ego_route_xy=[[0, case.lane], [30, case.lane]])
    for field in ('highway', 'vehicle', 'driver_control',
                  'lane_inventory', 'one_way_designation',
                  'sign_authority', 'sign_message', 'sign_orientation',
                  'sign_placement', 'sign_governance', 'ego_route'):
        s[field + '_source_sha256'] = 'a' * 64
    return s


def rows(case, s):
    output = []
    for i in range(900):
        row = dict(original_frame=100+i, time_s=i/20,
                   ego_id='ego', lane=case.lane, sign_governs_route=True,
                   velocity_xy=[5 if case.direction == 'designated' else -5, 0],
                   position_xy=[(5 if case.direction == 'designated' else -5)*i/20,
                                case.lane],
                   one_way_designation_source_sha256=
                   s['one_way_designation_source_sha256'],
                   sign_governance_source_sha256=
                   s['sign_governance_source_sha256'])
        for field in ('frame', 'ego_motion', 'ego_position', 'driver_control',
                      'lane_inventory', 'one_way_designation',
                      'sign_authority', 'sign_message',
                      'sign_orientation', 'sign_governance'):
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
            if name == 'spawn_vehicle':
                return None if self.fail else 'ego'
        return invoke


class OneWayTests(unittest.TestCase):
    def test_all_cases_construct_and_measure(self):
        for case in probe.CASES:
            with self.subTest(case=case.name):
                s = scene(case)
                adapter = Adapter()
                probe.construct(adapter, s, case)
                self.assertIn('place_one_way_sign', [x[0] for x in adapter.calls])
                actual = probe.measure_original(rows(case,s),s,case)
                self.assertEqual(actual['actual_direction'],case.direction)
                self.assertIsNone(actual['legal_judgment'])

    def test_missing_source_and_reverse_rejected(self):
        case = probe.CASES[0]
        s=scene(case);data=rows(case,s)
        del data[5]['sign_message_source_sha256']
        with self.assertRaisesRegex(ValueError,'source missing'):
            probe.measure_original(data,s,case)
        data=rows(case,s)
        for row in data: row['velocity_xy']=[-5,0]
        with self.assertRaisesRegex(ValueError,'position and velocity disagree'):
            probe.measure_original(data,s,case)

    def test_saved_position_and_velocity_must_agree(self):
        case=probe.CASES[0]
        s=scene(case)
        data=rows(case,s)
        data[100]['position_xy'][0] += 2
        with self.assertRaisesRegex(ValueError,'position and velocity disagree'):
            probe.measure_original(data,s,case)
        data=rows(case,s)
        del data[100]['ego_position_source_sha256']
        with self.assertRaisesRegex(ValueError,'source missing'):
            probe.measure_original(data,s,case)

    def test_source_digest_must_be_valid(self):
        case=probe.CASES[0]
        s=scene(case)
        s['sign_authority_source_sha256']='unsealed'
        with self.assertRaisesRegex(ValueError,'original context missing'):
            probe.validate_scene(s,case)

    def test_unauthorized_sign_and_spawn_rejected(self):
        case=probe.CASES[0]
        s=scene(case);s['sign_authorized']=False
        with self.assertRaisesRegex(ValueError,'authorized governing'):
            probe.validate_scene(s,case)
        with self.assertRaisesRegex(ValueError,'ego spawn failed'):
            probe.construct(Adapter(fail=True),scene(case),case)


if __name__ == '__main__':
    unittest.main()
