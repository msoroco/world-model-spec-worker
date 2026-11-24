import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import capture
from speed_boundary import compare
from delivery_audit import audit_decoded_media
from comparison_audit import audit
from test_native_capture import World, control, media_factory, transform


class FullComparisonTests(unittest.TestCase):
    def test_three_original_diagnostic_captures_compare_and_reject_site_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            attempts = {}
            for suffix in ('below', 'equal', 'above'):
                case = ROOT.name + '__' + suffix
                world = World()
                packet = {'format': 'c10301-native-site-v1', 'case_id': case,
                          'cell_id': 'C10301', 'layout': 'alley',
                          'control': 'access_aisle', 'actor': 'motor_vehicle_driver',
                          'maneuver': 'travel', 'diagnostic_fixture': True,
                          'map_name': world.map.name,
                          'opendrive_sha256': hashlib.sha256(
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
                                      for name in ('front', 'front_left', 'front_right', 'rear')}}
                site = root / (suffix + '-site.json')
                site.write_text(json.dumps(packet) + '\n')
                attempt = root / suffix
                capture(world, site, attempt, case, 'diagnostic-' + suffix,
                        0.05, transform, control, diagnostic_fixture=True,
                        media_factory=media_factory)
                self.assertTrue(world.actor.destroyed)
                self.assertTrue(audit_decoded_media(attempt, case,
                                allow_diagnostic=True)['full_video_decode'])
                attempts[case] = attempt
            result = compare(ROOT / 'case-plan.json', attempts)
            self.assertTrue(result['fixed_original_site_passed'])
            self.assertTrue(result['observed_order_passed'])
            self.assertTrue(result['diagnostic_fixture'])
            self.assertFalse(result['physical_acceptance_claimed'])
            saved = audit(ROOT / 'case-plan.json', attempts,
                          allow_diagnostic=True)
            self.assertEqual(len(saved['case_measurements']), 3)
            self.assertTrue(all(row['full_video_decode']
                                for row in saved['case_measurements'].values()))
            with self.assertRaisesRegex(ValueError, 'diagnostic fixture cannot enter'):
                audit(ROOT / 'case-plan.json', attempts)
            command = [sys.executable, str(ROOT / 'comparison_audit.py'),
                       '--plan', str(ROOT / 'case-plan.json')]
            for suffix in ('below', 'equal', 'above'):
                command.extend(['--' + suffix, str(root / suffix)])
            command.extend(['--output', str(root / 'comparison.json'),
                            '--allow-diagnostic'])
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0,
                             completed.stdout + completed.stderr)
            self.assertEqual(json.loads((root / 'comparison.json').read_text())['format'],
                             'c10301-saved-comparison-audit-v1')
            changed = root / 'above' / 'native-site-source.json'
            packet = json.loads(changed.read_text())
            packet['route'][-1]['x_m'] = 1900
            changed.write_text(json.dumps(packet) + '\n')
            with self.assertRaisesRegex(ValueError, 'comparison hash differs'):
                audit(ROOT / 'case-plan.json', attempts,
                      allow_diagnostic=True)
            command[command.index(str(root / 'comparison.json'))] = str(root / 'rejected.json')
            rejected = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn('comparison hash differs', rejected.stderr)
            self.assertFalse((root / 'rejected.json').exists())


if __name__ == '__main__':
    unittest.main()
