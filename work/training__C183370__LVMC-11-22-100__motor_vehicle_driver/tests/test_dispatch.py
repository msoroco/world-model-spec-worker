"""CPU checks for the package-level exact-case dispatcher."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
RUNNER = PACKAGE / 'runner.py'
CONFIG = json.loads((PACKAGE / 'config.json').read_text())


class DispatchTest(unittest.TestCase):
    def test_all_selected_bundles_are_source_bound(self):
        for case_id in CONFIG['supported_case_ids']:
            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                checked = subprocess.run(
                    [sys.executable, str(RUNNER), '--case', case_id,
                     '--candidate', candidate, '--check'],
                    capture_output=True, text=True, check=True)
                receipt = json.loads(checked.stdout)
                self.assertEqual(receipt['case_id'], case_id)
                self.assertEqual(receipt['candidate_id'], candidate)
                self.assertFalse(receipt['original_native_observed'])

    def test_unknown_case_rejects(self):
        checked = subprocess.run(
            [sys.executable, str(RUNNER), '--case', 'unknown', '--check'],
            capture_output=True, text=True)
        self.assertNotEqual(checked.returncode, 0)
        self.assertIn('outside this package', checked.stderr)

    def test_primary_materializes_exact_selected_construction(self):
        with tempfile.TemporaryDirectory(prefix='c183370-dispatch-') as temp:
            target = Path(temp) / 'selected'
            case_id = CONFIG['supported_case_ids'][0]
            subprocess.run([sys.executable, str(RUNNER), '--case', case_id,
                            '--output', str(target)],
                           capture_output=True, text=True, check=True)
            receipt = json.loads((target / 'candidate-selection.json').read_text())
            self.assertEqual(receipt['case_id'], case_id)
            self.assertEqual(receipt['candidate_id'], 'primary')
            self.assertTrue((target / 'runner.py').is_file())
            self.assertTrue((target / 'construction.json').is_file())


if __name__ == '__main__':
    unittest.main()
