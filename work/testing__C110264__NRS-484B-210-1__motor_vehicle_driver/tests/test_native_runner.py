"""CPU checks for the production Native entrypoint source gate and wiring."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import native_runner
from test_pass_right_actor import packet


class RunnerTests(unittest.TestCase):
    def test_requires_original_setup_before_world_use(self):
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / 'map.json'
            path.write_text(json.dumps(packet()) + '\n')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'reviewed original Native setup'):
                native_runner.acquire(N(), N(), packet_path=path, packet_sha256=digest,
                                      variant='left_signal', attempt=Path(scratch) / 'attempt')

    def test_exact_factory_wiring_and_original_frame_map(self):
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / 'map.json'
            source = packet()
            source['native_setup'] = {
                'ego_blueprint_id': 'vehicle.ego', 'target_blueprint_id': 'vehicle.target',
                'ego_start_s_m': 50, 'target_start_s_m': 55,
                'ego_speed_mps': 4, 'target_speed_mps': 2,
                'camera_mounts': {name: {'x': 0, 'y': 0, 'z': 1.5, 'yaw': yaw, 'pitch': 0}
                                  for name, yaw in [('front', 0), ('rear', 180),
                                                    ('left', 90), ('right', -90)]}}
            path.write_text(json.dumps(source) + '\n')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            world = N(get_blueprint_library=lambda: N())
            api = N(Transform=object(), Location=object(), Rotation=object(),
                    VehicleControl=object(), VehicleLightState=N(LeftBlinker=0x20))

            def fake_session(world_arg, **kwargs):
                self.assertIs(world_arg, world)
                self.assertEqual(kwargs['variant'], 'left_turn')
                self.assertEqual(kwargs['left_signal_mask'], 0x20)
                self.assertTrue(callable(kwargs['spawn_actors']))
                self.assertTrue(callable(kwargs['spawn_sensors']))
                self.assertTrue(callable(kwargs['controller_factory']))
                kwargs['frame_map'].append(88, 4.4, camera_frame_ids={name: 88 for name in
                                                                   ('front', 'rear', 'left', 'right')})
                return {'source_bound': True}

            attempt = Path(scratch) / 'attempt'
            attempt.mkdir()
            with mock.patch.object(native_runner, 'run_session', side_effect=fake_session):
                receipt = native_runner.acquire(world, api, packet_path=path, packet_sha256=digest,
                                                variant='left_turn', attempt=attempt)
            self.assertTrue(receipt['source_bound'])
            row = json.loads((attempt / 'frame-map.jsonl').read_text())
            self.assertEqual(row['native_frame_id'], 88)
            self.assertEqual(row['original_index'], 0)


if __name__ == '__main__':
    unittest.main()
