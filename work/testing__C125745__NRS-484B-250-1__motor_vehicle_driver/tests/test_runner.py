"""Exact offline bundle preflight rejects changed fixed source context."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from runner import check_bundle


class BundleTest(unittest.TestCase):
    def setUp(self):
        scratch = PACKAGE.parents[1] / '.runtime-work' / 'c125745-2501-runner-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('config.json', 'site.json'):
            shutil.copy2(PACKAGE / name, self.root / name)
        shutil.copytree(PACKAGE / 'sources', self.root / 'sources')

    def test_exact_diagnostic_preflight(self):
        result = check_bundle(self.root)
        expected = json.loads((self.root / 'config.json').read_text())['selected_case_id']
        self.assertEqual(result['case_id'], expected)
        self.assertFalse(result['original_capture_started'])
        self.assertFalse(result['physical_acceptance'])

    def test_changed_case_device_and_camera_rejected(self):
        config_path = self.root / 'config.json'
        config = json.loads(config_path.read_text())
        config['selected_case_id'] += '-other'
        config_path.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, 'identity differs'):
            check_bundle(self.root)
        shutil.copy2(PACKAGE / 'config.json', config_path)
        (self.root / 'sources/device.txt').write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'bytes absent or stale'):
            check_bundle(self.root)
        shutil.copy2(PACKAGE / 'sources/device.txt', self.root / 'sources/device.txt')
        site_path = self.root / 'site.json'
        site = json.loads(site_path.read_text())
        site['camera_dimensions']['approach'] = [2, 2]
        site_path.write_text(json.dumps(site))
        with self.assertRaisesRegex(ValueError, 'camera profile differs'):
            check_bundle(self.root)

    def test_delivery_audit_cli_rejects_wrong_exact_case(self):
        command = [sys.executable, str(PACKAGE / 'delivery_audit.py'),
                   '--attempt', str(self.root), '--saved-result', str(self.root / 'missing.json'),
                   '--videos-dir', str(self.root), '--encode-receipt', str(self.root / 'missing.json'),
                   '--probe', 'precedence', '--case-id', PACKAGE.name + '__advance',
                   '--output', str(self.root / 'audit.json')]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('exact delivery audit case differs', result.stderr)


if __name__ == '__main__':
    unittest.main()
