import json
import hashlib
import tempfile
import unittest
from unittest.mock import patch
from io import StringIO
from pathlib import Path
from geometry import check as geometry_check, open_drive
from runner import check as runner_check, survey, materialized_case, main as runner_main
from measure import measure
from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import record_native_exit

class FakeCarla:
    class LaneType:
        Parking = 'parking'
    class Location:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z

class FakeWaypoint:
    def __init__(self, x, y):
        self.road_id = 1
        self.lane_id = -2
        self.transform = type('T', (), {'location': FakeCarla.Location(x, y, 0)})()

class FakeMap:
    def __init__(self, wrong=False):
        self.wrong = wrong
    def to_opendrive(self):
        return open_drive().replace('BUS ROUTE TERMINUS', 'OTHER MARKER') if self.wrong else open_drive()
    def get_waypoint(self, location, project_to_road, lane_type):
        return FakeWaypoint(location.x, location.y)

class FakeWorld:
    def __init__(self, wrong=False):
        self.mapping = FakeMap(wrong)
    def get_map(self):
        return self.mapping

class NativeDraft(unittest.TestCase):
    def test_capture_seal_and_native_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('trace.jsonl', 'video_frames.jsonl', 'runner.py', 'construction.json'):
                (root / name).write_text('{}\n')
            (root / 'acquisition-provenance.json').write_text(json.dumps({'provenance_kind': 'native', 'diagnostic_fixture': False}))
            with self.assertRaisesRegex(ValueError, 'verified restoration'):
                seal_capture(root, frames=600, restoration={'restored': False}, errors=[], encoder_exit_codes={'overview': 0})
            seal = seal_capture(root, frames=600, restoration={'restored': True}, errors=[], encoder_exit_codes={'overview': 0})
            self.assertEqual(seal['events'], ['capture_finished', 'encoders_closed', 'restoration_verified'])
            self.assertEqual(record_native_exit(root)['event'], 'native_exit')
    def test_exact_runtime_capture_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = 'training__C393261__LVMC-11-60-030-A5__bus_driver__probe_02'
            (root / 'config.json').write_text(json.dumps({'case_id': case, 'selected_case_id': case, 'case': {'case_id': case}}))
            (root / 'candidate-selection.json').write_text(json.dumps({'case_id': case, 'candidate_id': 'primary'}))
            self.assertEqual(materialized_case(root), case)
            with patch('runner.execute', return_value={'captured': True}) as execute, patch('sys.stdout', new_callable=StringIO) as out:
                runner_main(['--output-dir', str(root), '--host', '127.0.0.1', '--port', '2000'])
            execute.assert_called_once_with(case, str(root), '127.0.0.1', 2000)
            self.assertEqual(json.loads(out.getvalue()), {'captured': True})
            (root / 'candidate-selection.json').write_text(json.dumps({'case_id': case + 'wrong', 'candidate_id': 'primary'}))
            with self.assertRaisesRegex(ValueError, 'exact case identity'):
                materialized_case(root)
    def test_geometry_and_survey(self):
        self.assertFalse(geometry_check()['sign_declares_duration'])
        self.assertEqual(len(survey(FakeWorld(), FakeCarla)['parking_lane_samples']), 4)
        with self.assertRaisesRegex(RuntimeError, 'terminus marker'):
            survey(FakeWorld(True), FakeCarla)
    def test_capture_plan(self):
        plan = runner_check()
        self.assertEqual(plan['frames'], 600)
        self.assertEqual(len(plan['cameras']), 4)
    def test_source_bound_duration_and_missing_designation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = {'zone_x_m': [-2.0, 20.0], 'parking_lane_id': -2,
                       'endpoint_id': 'native_road_1_parking_-2_terminus',
                       'native_survey': survey(FakeWorld(), FakeCarla),
                       'designation_verified': False, 'designated_period_s': 12,
                       'designation_authority_source': None}
            cp = root / 'context.json'
            hp = root / 'history.jsonl'
            cp.write_text(json.dumps(context))
            rows = []
            for i in range(600):
                x = 0 if 120 <= i < 480 else (-10 if i < 120 else 30)
                v = [0, 0, 0] if 120 <= i < 480 else [2, 0, 0]
                rows.append({'video_frame': i, 'native_frame': i + 100, 'time_s': i / 20, 'subject_id': 7, 'blueprint_id': 'vehicle.mitsubishi.fusorosa', 'position_xyz_m': [x, -5.25, 0], 'velocity_xyz_mps': v})
            hp.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            unknown = measure(hp, cp)
            self.assertEqual(unknown['longest_complete_interval_s'], 18)
            self.assertIsNone(unknown['dwell_exceeds_verified_period'])
            authority = root / 'authority.json'
            authority.write_text(json.dumps({'endpoint_id': context['endpoint_id'],
                                             'period_s': 12,
                                             'source_kind': 'synthetic_diagnostic'}))
            context.update(designation_verified=True,
                           designation_authority_source={'path': 'authority.json',
                               'sha256': hashlib.sha256(authority.read_bytes()).hexdigest()},
                           designated_period_s=12)
            cp.write_text(json.dumps(context))
            self.assertTrue(measure(hp, cp)['dwell_exceeds_verified_period'])
            authority.write_text(json.dumps({'endpoint_id': context['endpoint_id'],
                                             'period_s': 20,
                                             'source_kind': 'synthetic_diagnostic'}))
            context['designation_authority_source']['sha256'] = hashlib.sha256(authority.read_bytes()).hexdigest()
            context['designated_period_s'] = 20
            cp.write_text(json.dumps(context))
            self.assertFalse(measure(hp, cp)['dwell_exceeds_verified_period'])
            rows[230].pop('velocity_xyz_mps')
            hp.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'velocity missing'):
                measure(hp, cp)
