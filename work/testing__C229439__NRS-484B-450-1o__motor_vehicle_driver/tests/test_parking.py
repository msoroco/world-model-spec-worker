import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'parking.py'
sys.path.insert(0, str(MODULE.parent))
spec = importlib.util.spec_from_file_location('parking', MODULE)
parking = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parking)
fspec = importlib.util.spec_from_file_location('finalizer', MODULE.parent / 'finalizer.py')
finalizer = importlib.util.module_from_spec(fspec)
fspec.loader.exec_module(finalizer)


class FakeAdapter:
    def __init__(self):
        self.calls = []

    def verify_site(self, site):
        self.calls.append('site')
        return {'map_name': site['map_name'], 'parking_polygon': site['parking_polygon']}

    def install_and_read_device(self, device):
        self.calls.append('device')
        return {k: device[k] for k in ('device_id', 'exact_instruction', 'governed_polygon')}

    def configure_effective_window(self, device_id, mode, intervals):
        self.calls.append(('window', mode))
        self.effective = mode == 'effective'

    def read_device_effective(self, device_id):
        return self.effective

    def spawn_driver_vehicle(self, vehicle, waypoint):
        self.calls.append('spawn')
        return {'actor_id': 'ego-1', 'blueprint': vehicle['blueprint']}

    def configure_parking_route(self, actor, waypoints, polygon, action):
        self.calls.append(('route', actor, action))

    def configure_exception_cause(self, actor, cause):
        self.calls.append(('exception', cause))
        self.exception_cause = cause

    def read_exception_cause(self, actor):
        return self.exception_cause


class ParkingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.polygon = [[0, 0], [10, 0], [10, 10], [0, 10]]
        self.site = {'cell_id': 'C229439', 'layout': 'road', 'map_name': 'source_map',
                     'approach_waypoints': [[-4, 5], [2, 5]], 'parking_polygon': self.polygon}
        self.device = {'device_id': 'sign-1', 'exact_instruction': 'NO PARKING',
                       'authority_source': 'authority-record', 'placement_source': 'placement-record',
                       'traffic_purpose_source': 'purpose-record', 'legal_consistency_source': 'legal-review-record',
                       'governed_polygon': self.polygon, 'effective_intervals': [[0, 100]],
                       'prohibited_actions': ['park']}
        self.vehicle = {'blueprint': 'vehicle.test', 'driver_identity_source': 'actor-record',
                        'vehicle_class_source': 'blueprint-record'}
        self.case = {'case_id': 'case1', 'halt_action': 'park', 'device_mode': 'effective', 'exception': 'none', 'exact_instruction': 'NO PARKING'}

    def tearDown(self):
        self.tmp.cleanup()

    def ref(self, name, data):
        raw = json.dumps(data).encode()
        (self.root / name).write_bytes(raw)
        return {'path': str(self.root / name), 'sha256': hashlib.sha256(raw).hexdigest()}

    def refs(self):
        return self.ref('site.json', self.site), self.ref('device.json', self.device), self.ref('vehicle.json', self.vehicle)

    def rows(self, n=5):
        return [{'frame': i, 'time_s': round(i*0.05, 3), 'case_id': 'case1', 'subject_id': 'ego-1',
                 'device_id': 'sign-1', 'device_instruction': 'NO PARKING', 'device_effective': True,
                 'prohibited_actions': ['park'], 'halt_activity': 'park', 'traffic_conflict': False, 'police_direction': False,
                 'law_direction': False, 'device_direction': False, 'speed_mps': 0.0,
                 'body_corners_xy': [[1, 1], [2, 1], [2, 2], [1, 2]]} for i in range(n)]

    def expected(self, n=5):
        return {'frame_count': n, 'first_frame': 0, 'case_id': 'case1', 'subject_id': 'ego-1',
                'device_id': 'sign-1', 'device_instruction': 'NO PARKING',
                'parking_polygon': self.polygon, 'halt_action': 'park'}

    def test_construct_reads_site_device_and_driver(self):
        adapter = FakeAdapter()
        result = parking.construct_case(adapter, *self.refs(), self.case)
        self.assertEqual(result['subject_id'], 'ego-1')
        self.assertEqual(adapter.calls, ['site', 'device', ('window', 'effective'), 'spawn', ('route', 'ego-1', 'park'), ('exception', 'none')])

    def test_missing_official_source_rejected(self):
        self.device['authority_source'] = ''
        with self.assertRaisesRegex(parking.SourceError, 'authority'):
            parking.construct_case(FakeAdapter(), *self.refs(), self.case)

    def test_mismatched_governed_place_rejected(self):
        self.device['governed_polygon'] = [[20, 0], [30, 0], [30, 10]]
        with self.assertRaisesRegex(parking.SourceError, 'govern'):
            parking.construct_case(FakeAdapter(), *self.refs(), self.case)

    def test_case_specific_instruction_rejected(self):
        self.device['exact_instruction'] = 'NO STOPPING'
        with self.assertRaisesRegex(parking.SourceError, 'case-specific'):
            parking.construct_case(FakeAdapter(), *self.refs(), self.case)

    def test_native_device_readback_rejected(self):
        class Bad(FakeAdapter):
            def install_and_read_device(self, device):
                result = super().install_and_read_device(device)
                result['exact_instruction'] = 'NO STOPPING'
                return result
        with self.assertRaisesRegex(parking.SourceError, 'instruction'):
            parking.construct_case(Bad(), *self.refs(), self.case)

    def test_original_measurement(self):
        result = parking.measure_original_history(self.rows(), self.expected())
        self.assertEqual(result['halt_inside_frames'], 5)
        self.assertEqual(result['effective_prohibition_during_halt_frames'], 5)
        self.assertIsNone(result['legal_judgment'])

    def test_original_rejects_frame_and_clock_gaps(self):
        rows = self.rows(); rows[2]['frame'] = 3
        with self.assertRaisesRegex(parking.SourceError, 'frame gap'):
            parking.measure_original_history(rows, self.expected())
        rows = self.rows(); rows[2]['time_s'] = 0.12
        with self.assertRaisesRegex(parking.SourceError, '20 Hz'):
            parking.measure_original_history(rows, self.expected())

    def test_original_rejects_missing_exception_source(self):
        rows = self.rows(); del rows[0]['police_direction']
        with self.assertRaises(KeyError):
            parking.measure_original_history(rows, self.expected())

    def test_footprint_outside_governed_place(self):
        rows = self.rows(); rows[0]['body_corners_xy'][0] = [20, 20]
        result = parking.measure_original_history(rows, self.expected())
        self.assertEqual(result['halt_inside_frames'], 4)

    def test_halt_activity_must_match(self):
        rows = self.rows(); rows[2]['halt_activity'] = 'travel'
        self.assertEqual(parking.measure_original_history(rows, self.expected())['halt_inside_frames'], 4)

    def test_exception_source_is_measured(self):
        rows = self.rows(); rows[2]['traffic_conflict'] = True
        self.assertEqual(parking.measure_original_history(rows, self.expected())['exception_source_during_halt_frames'], 1)

    def test_comparison_rejects_fixed_change(self):
        a = {'case_id': 'a', 'map': 'A', 'action': 'park'}
        b = {'case_id': 'b', 'map': 'A', 'action': 'stop'}
        self.assertEqual(parking.audit_comparison(a, b, ['map'], ['action'])['differences_checked'], ['action'])
        b['map'] = 'B'
        with self.assertRaisesRegex(parking.SourceError, 'fixed'):
            parking.audit_comparison(a, b, ['map'], ['action'])

    def test_saved_source_audit_and_tamper(self):
        rows = self.rows(900)
        frame_map = [{'frame': r['frame'], 'time_s': r['time_s']} for r in rows]
        def save(name, data):
            raw = json.dumps(data).encode()
            (self.root / name).write_bytes(raw)
            return {'path': name, 'sha256': hashlib.sha256(raw).hexdigest()}
        attempt = {**self.expected(900), 'source_format': 'native_original', 'fps': 20,
                   'actor_rows': save('rows.json', rows), 'frame_map': save('frames.json', frame_map),
                   'cameras': {name: {**save(name + '.txt', {'camera': name}), 'frame_count': 900, 'fps': 20}
                               for name in ('front', 'rear', 'left', 'right')}}
        self.assertEqual(parking.audit_saved_attempt(attempt, self.root)['measurement']['source_frame_count'], 900)
        attempt_path = self.root / 'attempt.json'
        attempt_path.write_text(json.dumps(attempt))
        output = finalizer.finalize(attempt_path, self.root, self.root / 'observations.json')
        self.assertEqual(json.loads(output.read_text())['source_audit']['measurement']['source_frame_count'], 900)
        (self.root / 'rows.json').write_text('[]')
        with self.assertRaisesRegex(parking.SourceError, 'hash mismatch'):
            parking.audit_saved_attempt(attempt, self.root)
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            finalizer.finalize(attempt_path, self.root, self.root / 'rejected.json')
        self.assertFalse((self.root / 'rejected.json').exists())


if __name__ == '__main__':
    unittest.main()
