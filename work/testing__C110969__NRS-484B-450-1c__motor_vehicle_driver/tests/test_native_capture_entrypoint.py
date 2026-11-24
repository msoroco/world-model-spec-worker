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
