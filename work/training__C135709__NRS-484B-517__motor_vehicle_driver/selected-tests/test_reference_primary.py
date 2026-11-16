"""Exercise the exact request, four-camera plan and raw-to-saved processor."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReferencePrimary(unittest.TestCase):
    def run_script(self, name, *args, parse=True):
        result = subprocess.run([sys.executable, str(ROOT/name), *map(str, args)],
                                cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout) if parse else result.stdout

    def test_current_source_and_four_cameras(self):
        request = self.run_script('check.py', '--bundle', ROOT)
        self.assertEqual(request['frames'], 240)
        plan = self.run_script('capture.py', '--bundle', ROOT, '--check')
        self.assertEqual(plan['camera_names'],
                         ['overview', 'approach', 'reference_corner', 'driver_reference'])
        self.assertEqual(plan['camera_dimensions'],
                         [[1920, 1080], [1280, 720], [1280, 720], [1280, 720]])
        self.assertFalse(plan['original_native_observed'])

    def test_synthetic_raw_to_saved_and_missing_source(self):
        with tempfile.TemporaryDirectory() as temp:
            raw = Path(temp)/'raw'
            prepared = Path(temp)/'prepared'
            self.run_script('fixture_raw.py', '--bundle', ROOT, '--output-dir', raw,
                            parse=False)
            converted = self.run_script('prepare_raw.py', '--bundle', ROOT,
                '--raw-folder', raw, '--output-dir', prepared, '--synthetic-cpu')
            self.assertFalse(converted['delivery_ready'])
            measured = self.run_script('measure_prepared.py', '--bundle', ROOT,
                                       '--saved-dir', prepared)
            self.assertEqual(measured['source_kind'], 'synthetic_cpu')
            self.assertFalse(measured['delivery_ready'])
            saved_row = json.loads((prepared/'native-observed.jsonl').read_text().splitlines()[0])
            self.assertEqual(saved_row['speed_source'], 'synthetic_native_sample')
            raw_path = raw/'native-raw-actors.jsonl'
            rows = raw_path.read_text().splitlines()
            changed = json.loads(rows[0])
            changed['speed_source'] = 'original_native'
            rows[0] = json.dumps(changed)
            raw_path.write_text('\n'.join(rows)+'\n')
            negative = subprocess.run([sys.executable, str(ROOT/'prepare_raw.py'),
                '--bundle', str(ROOT), '--raw-folder', str(raw),
                '--output-dir', str(Path(temp)/'negative'), '--synthetic-cpu'],
                cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertNotEqual(negative.returncode, 0)


if __name__ == '__main__':
    unittest.main()
