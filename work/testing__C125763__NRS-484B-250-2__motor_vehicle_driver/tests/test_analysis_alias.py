"""Selected saved staging must retain a sealed Native source alias."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from analysis import _sources  # noqa: E402


class AliasTest(unittest.TestCase):
    def setUp(self):
        scratch = PACKAGE.parents[1] / '.runtime-work' / 'c125763-alias-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        case = PACKAGE / 'cases/entry_inside/diagnostic-sources'
        for name in ('site-context.json', 'ego-body-history.jsonl',
                     'other-body-history.jsonl', 'original-source-manifest.json'):
            shutil.copyfile(case / name, self.root / name)
        shutil.copyfile(PACKAGE / 'diagnostic-sources/road.xodr', self.root / 'road.xodr')

    def test_sealed_native_alias_reconstructs_selected_source(self):
        alias = self.root / 'original-source-manifest.json'
        digest = hashlib.sha256(alias.read_bytes()).hexdigest()
        (self.root / 'capture-seal.json').write_text(json.dumps({
            'provenance_kind': 'native',
            'sources': {'original-source-manifest.json': digest}}) + '\n')
        paths = _sources(self.root)
        self.assertEqual(set(paths), {'site-context.json', 'road.xodr',
            'ego-body-history.jsonl', 'other-body-history.jsonl'})
        self.assertEqual((self.root / 'source-manifest.json').read_bytes(), alias.read_bytes())

    def test_unsealed_alias_rejected(self):
        (self.root / 'capture-seal.json').write_text(json.dumps({
            'provenance_kind': 'native',
            'sources': {'original-source-manifest.json': '0' * 64}}) + '\n')
        with self.assertRaisesRegex(ValueError, 'not sealed'):
            _sources(self.root)


if __name__ == '__main__':
    unittest.main()
