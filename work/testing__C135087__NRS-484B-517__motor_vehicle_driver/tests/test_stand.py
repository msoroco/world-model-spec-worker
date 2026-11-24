import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'stand.py'
spec = importlib.util.spec_from_file_location('stand', MODULE)
stand = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stand)

SITE = dict(kind='taxicab_stand', cell_id='C135087', highway_status_source='road inventory', designation_source='agency order', sign_source='sign survey', map_name='Town', lane_id=3, curb_polygon=[[0, 0], [2, 0], [2, 3]], approach_lane_id=4, access_waypoints=[[0, -10], [0, 0]], stand_waypoint=[1, 1], passenger_waypoint=[2, 1], sign_id='S1')
VEHICLES = dict(subject=dict(kind='passenger_vehicle', compensated_taxicab_use=False, driver_identity_source='registration', blueprint='sedan'), entrant=dict(kind='motor_vehicle', design_capacity_including_driver=5, compensated_passenger_use_source='operator document', blueprint='taxi'))
CASE = dict(case_id='a', entrant_mode='about_to_enter', loading_mode='active', access_mode='open')

class FakeAdapter:
    def __init__(self): self.calls = []
    def verify_site(self, site): self.calls.append('site'); return dict(map_name=site['map_name'], sign_visible=True, sign_id=site['sign_id'], curb_polygon=site['curb_polygon'])
    def spawn_subject(self, vehicle, waypoint): self.calls.append('subject'); return dict(actor_id='ego', blueprint=vehicle['blueprint'])
    def spawn_entrant(self, vehicle, path, mode): self.calls.append(('entrant', tuple(map(tuple, path)), mode)); return dict(actor_id='taxi', blueprint=vehicle['blueprint'])
    def spawn_passenger(self, waypoint): self.calls.append('passenger'); return dict(actor_id='walker')
    def configure_loading(self, *args): self.calls.append(('loading', *args))
    def configure_access(self, *args): self.calls.append(('access', args[-1]))

class StandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        def seal(name, item):
            p = Path(self.temp.name) / name; p.write_text(json.dumps(item)); return dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        self.site = seal('site.json', SITE); self.vehicles = seal('vehicles.json', VEHICLES)
    def test_native_construction(self):
        adapter = FakeAdapter(); out = stand.construct_case(adapter, self.site, self.vehicles, CASE)
        self.assertEqual(out['entrant_id'], 'taxi'); self.assertEqual(adapter.calls[3], 'passenger')
        self.assertEqual(adapter.calls[-1], ('access', 'open'))
    def test_reject_stale_source(self):
        Path(self.site['path']).write_text('{}')
        with self.assertRaisesRegex(stand.SourceError, 'hash mismatch'): stand.construct_case(FakeAdapter(), self.site, self.vehicles, CASE)
    def test_reject_bad_classification(self):
        broken = dict(VEHICLES, entrant=dict(VEHICLES['entrant'], design_capacity_including_driver=7))
        p = Path(self.vehicles['path']); p.write_text(json.dumps(broken)); self.vehicles['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
        with self.assertRaisesRegex(stand.SourceError, 'capacity'): stand.construct_case(FakeAdapter(), self.site, self.vehicles, CASE)
    def test_reject_missing_sign_readback(self):
        class Bad(FakeAdapter):
            def verify_site(self, site): return dict(map_name='Town', sign_visible=False, sign_id='S1', curb_polygon=site['curb_polygon'])
        with self.assertRaisesRegex(stand.SourceError, 'sign readback'): stand.construct_case(Bad(), self.site, self.vehicles, CASE)
    def rows(self):
        return [dict(frame=i, time_s=i*0.05, case_id='a', map_name='Town', subject_id='ego', entrant_id='taxi', passenger_id='walker', subject_speed_mps=0, entrant_speed_mps=2, passenger_loading_active=True, entrant_waiting=False, entrant_about_to_enter=True, access_obstructed=i > 1) for i in range(4)]
    def expected(self): return dict(frame_count=4, first_frame=0, case_id='a', map_name='Town', subject_id='ego', entrant_id='taxi', passenger_id='walker')
    def test_saved_measurement(self):
        out=stand.measure_original_history(self.rows(), self.expected()); self.assertEqual(out['loading_during_stop_frames'], 4); self.assertEqual(out['access_obstructed_during_stop_frames'], 2); self.assertIsNone(out['legal_judgment'])
    def test_reject_frame_gap(self):
        rows=self.rows(); rows[2]['frame']=7
        with self.assertRaisesRegex(stand.SourceError, 'frame gap'): stand.measure_original_history(rows, self.expected())
    def test_reject_time_gap(self):
        rows=self.rows(); rows[2]['time_s'] += .04
        with self.assertRaisesRegex(stand.SourceError, '20 Hz time discontinuity'): stand.measure_original_history(rows, self.expected())
    def test_reject_missing_participant(self):
        rows=self.rows(); rows[2]['entrant_id']='missing'
        with self.assertRaisesRegex(stand.SourceError, 'actor identity'): stand.measure_original_history(rows, self.expected())
    def test_comparison_isolation(self):
        a=dict(CASE, site='S1'); b=dict(a, case_id='b', access_mode='constrained')
        self.assertEqual(stand.audit_comparison(a,b,['site','entrant_mode','loading_mode'],['access_mode'])['differences_checked'], ['access_mode'])
        b['site']='S2'
        with self.assertRaisesRegex(stand.SourceError, 'fixed condition'): stand.audit_comparison(a,b,['site'],['access_mode'])

if __name__ == '__main__': unittest.main()

class SavedAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        def save(name, data):
            p=root/name; p.write_bytes(data); return dict(path=name, sha256=hashlib.sha256(data).hexdigest())
        rows=[dict(frame=i, time_s=i/20, case_id='a', map_name='Town', subject_id='ego', entrant_id='taxi', passenger_id='walker', subject_speed_mps=0, entrant_speed_mps=0, passenger_loading_active=True, entrant_waiting=True, entrant_about_to_enter=False, access_obstructed=False) for i in range(900)]
        frame_map=[dict(frame=i,time_s=i/20) for i in range(900)]
        self.attempt=dict(source_format='native_original',frame_count=900,fps=20,case_id='a',map_name='Town',subject_id='ego',entrant_id='taxi',passenger_id='walker',first_frame=0,
            actor_rows=save('rows.json',json.dumps(rows).encode()),frame_map=save('map.json',json.dumps(frame_map).encode()),
            cameras={name:dict(save(name+'.mp4',b'fake camera source '+name.encode()),frame_count=900,fps=20) for name in ('front','rear','left','right')})
    def test_saved_source_audit(self):
        out=stand.audit_saved_attempt(self.attempt,self.temp.name)
        self.assertEqual(out['measurement']['source_frame_count'],900)
        self.assertEqual(out['full_video_decode'],'pending_pinned_media_auditor')
    def test_reject_stale_camera(self):
        (Path(self.temp.name)/'front.mp4').write_bytes(b'tampered')
        with self.assertRaisesRegex(stand.SourceError,'saved source hash mismatch'): stand.audit_saved_attempt(self.attempt,self.temp.name)
    def test_reject_missing_camera(self):
        del self.attempt['cameras']['rear']
        with self.assertRaisesRegex(stand.SourceError,'four camera'): stand.audit_saved_attempt(self.attempt,self.temp.name)
    def test_reject_missing_actor_row(self):
        p=Path(self.temp.name)/'rows.json'; rows=json.loads(p.read_text()); rows.pop(); p.write_text(json.dumps(rows)); self.attempt['actor_rows']['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
        with self.assertRaisesRegex(stand.SourceError,'frame map and actor rows|incomplete frame count'): stand.audit_saved_attempt(self.attempt,self.temp.name)
    def test_reject_path_escape(self):
        self.attempt['actor_rows']['path']='../outside.json'
        with self.assertRaisesRegex(stand.SourceError,'source escapes'): stand.audit_saved_attempt(self.attempt,self.temp.name)
