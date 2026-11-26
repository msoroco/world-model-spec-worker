import json
import unittest
from pathlib import Path
import tempfile

from runner import check


class RootIndex(unittest.TestCase):
    def test_exact_six_case_index(self):
        result = check(Path.cwd())
        self.assertEqual(len(result['case_ids']), 6)
        self.assertFalse(result['native_executed'])

    def test_missing_case_rejected(self):
        root = Path.cwd()
        config = json.loads((root / 'config.json').read_text())
        manifest = json.loads((root / 'execution-manifest.json').read_text())
        config['supported_case_ids'].pop()
        scratch_parent = root.parents[1] / '.runtime-work'
        with tempfile.TemporaryDirectory(dir=scratch_parent) as temporary:
            folder = Path(temporary)
            (folder / 'config.json').write_text(json.dumps(config))
            (folder / 'execution-manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'differs'):
                check(folder)
