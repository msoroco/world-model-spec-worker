import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


class RunnerCaptureCliTests(unittest.TestCase):
    def test_missing_original_site_fails_with_native_status(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temp:
            attempt = Path(temp)
            (attempt / 'construction.json').write_text('{}\n')
            env = dict(os.environ)
            for key in ('C108447_ORIGINAL_OPENDRIVE', 'C108447_PARCEL_AUTHORITY',
                        'C108447_SITE_REVIEW', 'C108447_NATIVE_OWNER_MODULE'):
                env.pop(key, None)
            result = subprocess.run(
                [sys.executable, str(BASE / 'runner.py'), '--output-dir', str(attempt),
                 '--host', '127.0.0.1', '--port', '20000'],
                cwd=BASE, env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            status = json.loads((attempt / 'native-run-status.json').read_text())
            self.assertIn('original site files', status['errors'][0]['message'])
            self.assertFalse(status['physical_acceptance_claimed'])
            self.assertFalse((attempt / 'capture-seal.json').exists())


if __name__ == '__main__':
    unittest.main()
