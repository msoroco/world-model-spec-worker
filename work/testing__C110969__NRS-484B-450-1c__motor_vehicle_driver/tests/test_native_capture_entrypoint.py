import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_capture_entrypoint as entry


CASE = 'testing__C110969__NRS-484B-450-1c__motor_vehicle_driver__inside_stop'


class EntryTests(unittest.TestCase):
    def test_materialized_dispatch_inventory(self):
        with tempfile.TemporaryDirectory(dir=Path('.runtime-work').resolve()) as tmp:
            attempt = Path(tmp)
            (attempt/'runner.py').write_text('print("source gated")\n')
            construction = {'case_id': CASE, 'files': [
                {'path': 'runner.py', 'content': 'print("source gated")\n'}]}
            source = attempt/'construction.json'
            source.write_text(json.dumps(construction)+'\n')
            selection = {'case_id': CASE, 'construction_sha256':
                         hashlib.sha256(source.read_bytes()).hexdigest()}
            (attempt/'candidate-selection.json').write_text(json.dumps(selection)+'\n')
            self.assertEqual(entry.check_materialized_attempt(attempt, CASE), selection)
            (attempt/'trace.json').write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'prior acquisition'):
                entry.check_materialized_attempt(attempt, CASE)

    def test_pinned_dispatch_reaches_source_gated_native_adapter(self):
        with tempfile.TemporaryDirectory(dir=Path('.runtime-work').resolve()) as tmp:
            base = Path(tmp)
            attempt = base/'attempt'
            attempt.mkdir()
            (attempt/'runner.py').write_text('print("source gated")\n')
            construction = {'case_id': CASE, 'files': [
                {'path': 'runner.py', 'content': 'print("source gated")\n'}]}
            built = attempt/'construction.json'
            built.write_text(json.dumps(construction)+'\n')
            (attempt/'candidate-selection.json').write_text(json.dumps({
                'case_id': CASE, 'construction_sha256':
                hashlib.sha256(built.read_bytes()).hexdigest()})+'\n')
            boundary = {'map_id': 'synthetic-map', 'highway_status': 'reviewed_highway',
                        'joining_roadways': True, 'intersection_polygon':
                        [[-5,-5],[5,-5],[5,5],[-5,5]], 'source_refs': ['CPU synthetic test']}
            route = {'case_id': CASE, 'map_id': 'synthetic-map',
                     'source_refs': ['CPU synthetic test'], 'approach_lane': 'synthetic lane',
                     'lane_direction_reviewed': True, 'vehicle_blueprint': 'vehicle.test',
                     'spawn': {'x':-10,'y':0,'z':0,'yaw_deg':0},
                     'destination': {'x':0,'y':0,'z':0,'yaw_deg':0},
                     'vehicle_extent': {'half_length_m':1, 'half_width_m':0.5},
                     'speed_limit_mps': 5}
            cameras = {'case_id': CASE, 'map_id': 'synthetic-map',
                       'source_refs': ['CPU synthetic test'], 'placement_reviewed': True,
                       'cameras': {name: {'pose': {'x':0,'y':0,'z':2,'yaw_deg':0},
                                         'attach_to': 'ego', 'fov_deg':90,
                                         'source_refs': ['CPU synthetic test']}
                                   for name in ('overview','approach','reference_corner','driver_reference')}}
            packets = {}
            for name, value in (('route',route),('boundary',boundary),('camera',cameras)):
                path = base/(name+'.json')
                path.write_text(json.dumps(value)+'\n')
                packets[name] = {'path': str(path.resolve()),
                                 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            index = base/'index.json'
            index.write_text(json.dumps({'case_id': CASE, 'reviewer':'CPU synthetic test',
                'review_note':'source-shape dispatch test; no official road claim',
                'packet_refs': packets})+'\n')
            env = {'C110969_ROUTE_PACKET': packets['route']['path'],
                   'C110969_BOUNDARY_PACKET': packets['boundary']['path'],
                   'C110969_CAMERA_PACKET': packets['camera']['path'],
                   'C110969_SOURCE_INDEX': str(index)}
            world = types.SimpleNamespace(
                get_map=lambda: types.SimpleNamespace(name='synthetic-map'),
                get_settings=lambda: types.SimpleNamespace(synchronous_mode=False,
                                                         fixed_delta_seconds=None))
            client = types.SimpleNamespace(get_world=lambda: world)
            with patch.dict(os.environ, env), patch.object(entry, 'run_native',
                    return_value={'case_id': CASE, 'frame_count':900}) as invoked, \
                    patch.object(entry, 'finalize_native_capture',
                    return_value={'frame_count':900}):
                result = entry.run_from_environment(CASE, attempt, 'localhost', 2000,
                                                    api=object(), client=client)
            self.assertEqual(result['native_capture']['frame_count'], 900)
            self.assertEqual(invoked.call_args.args[0], world)

    def test_missing_reviewed_sources_fail_before_client(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'reviewed Native route'):
                entry.run_from_environment(CASE, '.runtime-work/unused', 'localhost', 2000)

    def test_wrong_exact_case_fails_before_client(self):
        with tempfile.TemporaryDirectory(dir=Path('.runtime-work').resolve()) as tmp:
            paths = [Path(tmp) / name for name in ('route.json', 'boundary.json', 'camera.json')]
            for path in paths:
                path.write_text(json.dumps({'case_id': CASE + '_wrong'}) + '\n')
            index = Path(tmp) / 'index.json'
            index.write_text(json.dumps({
                'case_id': CASE, 'reviewer': 'fixture-reviewer',
                'review_note': 'synthetic CPU source-shape test only',
                'packet_refs': {kind: {'path': str(path.resolve()),
                                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                                for kind, path in zip(('route', 'boundary', 'camera'), paths)}
            }) + '\n')
            env = dict(zip(('C110969_ROUTE_PACKET', 'C110969_BOUNDARY_PACKET',
                            'C110969_CAMERA_PACKET'), map(str, paths)))
            env['C110969_SOURCE_INDEX'] = str(index)
            with patch.dict(os.environ, env):
                with self.assertRaisesRegex(ValueError, 'exact route case'):
                    entry.run_from_environment(CASE, Path(tmp) / 'attempt', 'localhost', 2000)

    def test_changed_source_packet_rejected_before_client(self):
        with tempfile.TemporaryDirectory(dir=Path('.runtime-work').resolve()) as tmp:
            paths = [Path(tmp) / name for name in ('route.json', 'boundary.json', 'camera.json')]
            for path in paths:
                path.write_text('{}\n')
            index = Path(tmp) / 'index.json'
            index.write_text(json.dumps({
                'case_id': CASE, 'reviewer': 'fixture-reviewer',
                'review_note': 'synthetic CPU source-shape test only',
                'packet_refs': {kind: {'path': str(path.resolve()),
                                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                                for kind, path in zip(('route', 'boundary', 'camera'), paths)}
            }) + '\n')
            paths[0].write_text('{"changed":true}\n')
            env = dict(zip(('C110969_ROUTE_PACKET', 'C110969_BOUNDARY_PACKET',
                            'C110969_CAMERA_PACKET'), map(str, paths)))
            env['C110969_SOURCE_INDEX'] = str(index)
            with patch.dict(os.environ, env):
                with self.assertRaisesRegex(ValueError, 'hash/path differs: route'):
                    entry.run_from_environment(CASE, Path(tmp) / 'attempt', 'localhost', 2000)

    def test_original_motion_observer_leaves_exceptions_unknown(self):
        actor = types.SimpleNamespace(
            get_control=lambda: types.SimpleNamespace(throttle=0.2, brake=0.0,
                                                      hand_brake=False),
            get_velocity=lambda: types.SimpleNamespace(x=1.0, y=2.0, z=0.0))
        observed = entry.OriginalMotionObserver().observe(
            types.SimpleNamespace(frame=72), actor)
        self.assertEqual(observed['source_ref'], 'original_native_frame:72')
        self.assertEqual(observed['activity_observation']['velocity_xyz_mps'], [1.0, 2.0, 0.0])
        self.assertEqual(observed['activity_observation']['stop_stand_park_legal_class'],
                         'unresolved')
        self.assertIsNone(observed['officer_direction_observation'])


if __name__ == '__main__':
    unittest.main()
