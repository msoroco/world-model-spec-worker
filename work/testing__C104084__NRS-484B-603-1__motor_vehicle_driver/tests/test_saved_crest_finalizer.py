import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from saved_crest_audit import ASSIGNMENT
from saved_crest_finalizer import profile_witness
from test_saved_crest_media import media_fixture


class SavedCrestFinalizerTests(unittest.TestCase):
    def test_three_measured_profiles_and_wrong_profile_rejected(self):
        base = {'approach_start_m': 100, 'crest_station_m': 250,
                'speed_change_mps': -2, 'first_speed_decrease_station_m': 150}
        self.assertEqual(profile_witness(base, 'early_decrease')['profile'], 'early_decrease')
        with self.assertRaisesRegex(ValueError, 'does not realize'):
            profile_witness(base, 'late_decrease')
        late = dict(base, first_speed_decrease_station_m=210)
        self.assertEqual(profile_witness(late, 'late_decrease')['profile'], 'late_decrease')
        steady = dict(base, first_speed_decrease_station_m=None, speed_change_mps=0)
        self.assertEqual(profile_witness(steady, 'steady_approach')['profile'], 'steady_approach')
        with self.assertRaisesRegex(ValueError, 'does not realize'):
            profile_witness(steady, 'early_decrease')

    def test_cli_finalizes_full_source_decode_and_rejects_changed_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = media_fixture(root)
            source = root / 'manifest.json'
            source.write_text(json.dumps(manifest, sort_keys=True) + '\n', encoding='utf-8')
            output = root / 'finalized.json'
            command = [sys.executable, str(ROOT/'saved_crest_finalizer.py'),
                       '--attempt', str(root), '--manifest', str(source),
                       '--case', ASSIGNMENT+'__early_decrease', '--output', str(output)]
            subprocess.run(command, check=True, capture_output=True, text=True)
            final = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(final['frame_count'], 900)
            self.assertEqual(final['speed_profile_witness']['profile'], 'early_decrease')
            self.assertEqual(len(final['camera_decodes']), 4)
            self.assertFalse(final['checks']['physical_completion'])
            self.assertEqual(final['source_manifest_sha256'],
                             hashlib.sha256(source.read_bytes()).hexdigest())
            command[command.index('--case')+1] = ASSIGNMENT+'__late_decrease'
            command[-1] = str(root/'wrong.json')
            failed = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn('selected exact crest case differs', failed.stderr)
            self.assertFalse((root/'wrong.json').exists())


if __name__ == '__main__':
    unittest.main()
