import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import capture
from analysis import finalize
from test_native_capture import CASE, World, control, media_factory, transform


class SavedCliIntegrationTests(unittest.TestCase):
    def test_original_capture_saved_cli_and_missing_source_negative(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            world = World()
            packet = {
                'format': 'c10301-native-site-v1', 'case_id': CASE,
                'cell_id': 'C10301', 'layout': 'alley',
                'control': 'access_aisle', 'actor': 'motor_vehicle_driver',
                'maneuver': 'travel', 'diagnostic_fixture': True,
                'map_name': world.map.name,
                'opendrive_sha256': __import__('hashlib').sha256(
                    world.map.to_opendrive().encode()).hexdigest(),
                'access_aisle_source_ref': 'diagnostic aisle',
                'route_source_ref': 'diagnostic route',
                'route': [{'s_m': 10 * i, 'x_m': 10 * i,
                           'y_m': 0, 'z_m': 0} for i in range(181)],
                'vehicle_blueprint_id': 'vehicle.diagnostic',
                'cameras': {name: {'blueprint_id': 'sensor.camera.rgb',
                                   'x_m': 0, 'y_m': 0, 'z_m': 1.5,
                                   'pitch_deg': 0, 'yaw_deg': 0,
                                   'roll_deg': 0}
                            for name in ('front', 'front_left', 'front_right', 'rear')},
            }
            site = root / 'site.json'
            site.write_text(json.dumps(packet) + '\n')
            attempt = root / 'attempt'
            capture(world, site, attempt, CASE, 'saved-cli-run', 0.05,
                    transform, control, diagnostic_fixture=True,
                    media_factory=media_factory)
            self.assertTrue(world.actor.destroyed)
            selected = finalize(attempt, CASE, allow_diagnostic=True)
            self.assertTrue(selected['full_video_decode'])
            self.assertEqual(selected['measurements']['vehicle_operation']['value']['observed_motion_samples'], 900)
            self.assertEqual(selected['measurements']['sampled_rate_boundary']['value']['sample_count'], 900)
            setup_path = attempt / 'authored-setup.json'
            setup_bytes = setup_path.read_bytes()
            setup_path.unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source: authored-setup.json'):
                finalize(attempt, CASE, allow_diagnostic=True)
            setup_path.write_bytes(setup_bytes)
            command = [sys.executable, str(ROOT / 'saved_speed.py'),
                       '--attempt', str(attempt), '--case-id', CASE,
                       '--output', str(root / 'saved.json'), '--allow-diagnostic']
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            saved = json.loads((root / 'saved.json').read_text())
            self.assertTrue(saved['media_audit']['full_video_decode'])
            self.assertFalse(saved['physical_acceptance_claimed'])
            (attempt / 'rear.mkv').unlink()
            command[command.index(str(root / 'saved.json'))] = str(root / 'rejected.json')
            failure = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(failure.returncode, 0)
            self.assertIn('rear source missing', failure.stderr)
            self.assertFalse((root / 'rejected.json').exists())


if __name__ == '__main__':
    unittest.main()
