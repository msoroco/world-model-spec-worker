"""Exact selected diagnostic bundle preflight and source boundary."""
from pathlib import Path
import shutil
import tempfile
import unittest
import sys


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from runner import check_bundle


class RunnerTest(unittest.TestCase):
    def test_exact_inside_bundle_is_diagnostic(self):
        checked = check_bundle(PACKAGE)
        self.assertTrue(checked['diagnostic_fixture'])
        self.assertFalse(checked['original_capture_started'])
        self.assertFalse(checked['physical_acceptance'])
        self.assertFalse(checked['legal_verdict_claimed'])

    def test_changed_device_source_rejected(self):
        scratch = PACKAGE.parents[1] / '.runtime-work' / 'c125763-runner-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            target = Path(temporary)
            for name in ('runner.py', 'config.json', 'site.json'):
                shutil.copy2(PACKAGE / name, target / name)
            shutil.copytree(PACKAGE / 'sources', target / 'sources')
            (target / 'sources/device.txt').write_text('changed diagnostic device\n')
            with self.assertRaisesRegex(ValueError, 'device_source original bytes absent or stale'):
                check_bundle(target)


if __name__ == '__main__':
    unittest.main()
