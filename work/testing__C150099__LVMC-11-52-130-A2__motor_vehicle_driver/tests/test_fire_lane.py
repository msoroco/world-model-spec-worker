import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f'{name}.py')
    out = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = out
    spec.loader.exec_module(out)
    return out

fire_lane = module('fire_lane')
saved_audit = module('saved_audit')


def site(case):
    out = {k: k + '-hash' for k in ('map_sha256', 'jurisdiction_sha256',
        'fire_code_designation_sha256', 'posting_authority_sha256',
        'posted_extent_sha256', 'sign_identity_sha256', 'sign_appearance_sha256',
        'curb_geometry_sha256', 'property_source_sha256', 'one_way_source_sha256',
        'ego_blueprint_sha256', 'camera_plan_sha256')}
    out.update(cell_id='C150099', layout='one_way_road', property_kind=case.property_kind,
               sign_support='spawned_prop', sign_text='FIRE LANE',
               posted_interval_m=[10.0, 30.0], curb_y_m=2.0,
               approach_waypoints=[[0.0, 0.0], [20.0, 0.0]])
    if case.exception != 'none':
        key = {'lawful_traffic_conflict': 'traffic_conflict_source_sha256',
               'police_direction': 'police_direction_source_sha256',
               'traffic_device_direction': 'traffic_device_source_sha256'}[case.exception]
        out[key] = 'exception-hash'
    return out

class Fake:
    def __init__(self, good=True):
        self.calls = []
        self.good = good
        self.destroyed = []
    def spawn_sign(self, *args):
        self.calls.append('spawn_sign'); return 'sign'
    def read_sign(self, sign):
        self.calls.append('read_sign')
        return {'identity_sha256': 'sign_identity_sha256-hash',
                'appearance_sha256': 'sign_appearance_sha256-hash',
                'physically_present': self.good}
    def spawn_vehicle(self, *args):
        self.calls.append('spawn_vehicle'); return 'ego'
    def set_route(self, *args, **kwargs): self.calls.append('route')
    def set_curb_target(self, *args, **kwargs): self.calls.append('curb_target')
    def set_attendance(self, *args): self.calls.append('attendance')
    def set_exception(self, *args): self.calls.append('exception')
    def destroy(self, actor): self.destroyed.append(actor)

class Construction(unittest.TestCase):
    def test_all_cases_and_target_edges(self):
        for case in fire_lane.CASES:
            with self.subTest(case=case.id):
                adapter = Fake()
                built = fire_lane.build_case(adapter, site(case), case, 4.0)
                self.assertEqual(built['case_id'], case.id)
                self.assertEqual(adapter.calls[:3], ['spawn_sign', 'read_sign', 'spawn_vehicle'])
                west, east = built['commanded_body_interval_m']
                self.assertLess(west, east)
                self.assertEqual(east <= 30, case.target_region == 'inside')
    def test_missing_designation_rejected(self):
        case = fire_lane.CASES[0]; s = site(case); del s['fire_code_designation_sha256']
        with self.assertRaisesRegex(ValueError, 'designation'):
            fire_lane.build_case(Fake(), s, case, 4.0)
    def test_missing_physical_sign_rejected_and_cleaned(self):
        case = fire_lane.CASES[0]; adapter = Fake(False)
        with self.assertRaisesRegex(ValueError, 'physical presence'):
            fire_lane.build_case(adapter, site(case), case, 4.0)
        self.assertEqual(adapter.destroyed, ['sign'])
    def test_missing_exception_source_rejected(self):
        case = fire_lane.CASES[-1]; s = site(case); del s['traffic_device_source_sha256']
        with self.assertRaisesRegex(ValueError, 'traffic_device_source'):
            fire_lane.build_case(Fake(), s, case, 4.0)

class Measurements(unittest.TestCase):
    def rows(self, case, count=2):
        s = site(case)
        fixed = {k: s[k] for k in ('map_sha256', 'jurisdiction_sha256', 'fire_code_designation_sha256',
            'posting_authority_sha256', 'posted_extent_sha256', 'sign_identity_sha256',
            'sign_appearance_sha256', 'curb_geometry_sha256', 'property_source_sha256', 'camera_plan_sha256')}
        return [dict(fixed, case_id=case.id, ego_id='ego', sign_id='sign', frame_map_sha256='map',
                    original_frame=i, time_s=i / 20, source_sha256='raw',
                    body_footprint_source_sha256='body', sign_physically_present=True,
                    sign_text_readback='FIRE LANE', body_west_x_m=11.0, body_east_x_m=15.0,
                    body_curb_gap_m=0.2, activity_observation='parked', attended_observation=True,
                    property_kind=case.property_kind, exception_kind=case.exception,
                    exception_source_sha256='exception-hash' if case.exception != 'none' else None)
                for i in range(count)]
    def test_original_overlap(self):
        c = fire_lane.CASES[0]
        out = fire_lane.measure_original_history(self.rows(c), site(c), c)
        self.assertEqual(out['overlap_frames'], 2)
        self.assertIsNone(out['legal_judgment'])
    def test_time_and_source_rejection(self):
        c = fire_lane.CASES[0]; rows = self.rows(c); rows[1]['time_s'] = 0.1
        with self.assertRaisesRegex(ValueError, '20 Hz'):
            fire_lane.measure_original_history(rows, site(c), c)
        rows = self.rows(c); rows[1]['posted_extent_sha256'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'fixed source'):
            fire_lane.measure_original_history(rows, site(c), c)
    def test_comparison_isolation(self):
        fixed = {k: 'same' for k in ('map_sha256', 'jurisdiction_sha256', 'fire_code_designation_sha256',
            'posting_authority_sha256', 'sign_identity_sha256', 'sign_appearance_sha256',
            'curb_geometry_sha256', 'camera_plan_sha256', 'ego_blueprint_sha256',
            'route_sha256', 'weather_sha256')}
        l = dict(case_id='a', frame_count=900, original_history_sha256='a', camera_plan_sha256='same',
                 fixed_sources=fixed, attended=True, property_kind='public', activity='park',
                 target_region='inside', exception='none')
        r = dict(l, case_id='b', attended=False)
        fire_lane.audit_comparison(l, r, 'attended')
        r['fixed_sources'] = dict(fixed, map_sha256='changed')
        with self.assertRaisesRegex(ValueError, 'fixed source changed'):
            fire_lane.audit_comparison(l, r, 'attended')

class SavedAudit(unittest.TestCase):
    def test_sealed_history_and_tampering(self):
        fixed = {k: k + '-hash' for k in ('ego_id', 'sign_id', 'site_sha256', 'map_sha256',
            'jurisdiction_sha256', 'fire_code_designation_sha256', 'posting_authority_sha256',
            'posted_extent_sha256', 'sign_identity_sha256', 'sign_appearance_sha256',
            'property_source_sha256', 'curb_geometry_sha256', 'camera_plan_sha256', 'frame_map_sha256')}
        rows = [dict(fixed, case_id='a', original_frame=i, time_s=i / 20,
                     source_sha256='raw', body_footprint_source_sha256='body',
                     sign_physically_present=True, sign_text_readback='FIRE LANE',
                     activity_observation='parked', attended_observation=True,
                     property_kind='public', posted_interval_m=[10, 30],
                     body_interval_m=[11, 15], camera_frames={'front':'f','rear':'r','left':'l','right':'rt'},
                     exception_kind='none') for i in range(900)]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'history.jsonl'
            def write():
                p.write_text(''.join(json.dumps(r) + '\n' for r in rows))
                return hashlib.sha256(p.read_bytes()).hexdigest()
            digest = write()
            self.assertEqual(saved_audit.audit_original_history(p, digest, 'a', fixed['site_sha256'])['overlap_frames'], 900)
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                saved_audit.audit_original_history(p, '0'*64, 'a', fixed['site_sha256'])
            rows[500]['camera_frames']['front'] = ''
            digest = write()
            with self.assertRaisesRegex(ValueError, 'four-camera'):
                saved_audit.audit_original_history(p, digest, 'a', fixed['site_sha256'])
            rows[500]['camera_frames']['front'] = 'f'
            rows[500]['time_s'] = 30
            digest = write()
            with self.assertRaisesRegex(ValueError, '20 Hz'):
                saved_audit.audit_original_history(p, digest, 'a', fixed['site_sha256'])

if __name__ == '__main__': unittest.main()
