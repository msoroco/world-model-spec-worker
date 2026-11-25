"""Reject missing or diagnostic site authority before any Native adapter call."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from original_runner import construct


class OriginalRunnerTests(unittest.TestCase):
    def test_missing_reviewed_site_rejected(self):
        case_id = HERE.name + '__load_prompt'
        class Adapter:
            def __getattr__(self, _):
                raise AssertionError('adapter must not be called')
        with self.assertRaisesRegex(ValueError, 'reviewed original passenger-zone site source missing'):
            construct(Adapter(), ROOT / '.runtime-work/c150116/no-manifest',
                      ROOT / '.runtime-work/c150116/no-site', case_id)

    def test_synthetic_site_rejected_before_spawn(self):
        case_id = HERE.name + '__load_prompt'
        scratch = ROOT / '.runtime-work/c150116/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            site = root / 'site-context.json'
            site.write_text(json.dumps({'source_kind': 'synthetic_diagnostic_fixture'}))
            manifest = root / 'source-manifest.json'
            manifest.write_text(json.dumps({'source_kind': 'synthetic_diagnostic_fixture',
                'diagnostic_fixture': True, 'reviewer': 'mock-only', 'case_id': case_id,
                'files': {'site-context.json': {'sha256': hashlib.sha256(site.read_bytes()).hexdigest()}}}))
            class Adapter:
                def __getattr__(self, _):
                    raise AssertionError('adapter must not be called')
            with self.assertRaisesRegex(ValueError, 'reviewed original source identity missing'):
                construct(Adapter(), manifest, site, case_id)


if __name__ == '__main__':
    unittest.main()
